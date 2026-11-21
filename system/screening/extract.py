"""Gathering facts from free text (POLICY.md principles 4 and 5).

Everything here reads text and returns facts. Nothing here decides a hit, and a
passage that cannot be read with confidence yields nothing: unknown stays unknown.
"""
import re
import unicodedata

from . import countries as C
from . import dates as D
from .textutil import fold

# -- the kind of listing a search result must describe -------------------------
LISTING_PHRASES = {
    "sanctions": "sanctioned individual",
    "pep": "politically exposed person",
    "enforcement": "subject of enforcement action",
    "adverse media": "named in adverse media",
    "soe": "state owned enterprise official",
}
OTHER_LISTING = "named on a watchlist"


def listing_phrase(primary_category, categories=None):
    """The phrase for the hit's primary category, or its first category."""
    category = (primary_category or "").strip()
    if not category:
        items = C.split_values(categories)
        category = items[0] if items else ""
    key = fold(category).strip()
    if key.startswith("sanction"):
        key = "sanctions"
    return LISTING_PHRASES.get(key, OTHER_LISTING)


def _flat(text):
    return " ".join(fold(text).replace("-", " ").split())


# -- dated reports -------------------------------------------------------------
_REPORT = re.compile(r"^\s*According to .*?; ([A-Z][a-z]+ \d{1,2}, \d{4}): ", re.M)


def dated_reports(profile_notes):
    """Dates of the English lines 'According to ...; September 10, 2025: ...'.
    Other wordings do not count."""
    out = []
    for m in _REPORT.finditer(profile_notes or ""):
        d = D.parse_date(m.group(1))
        if d and d.day:
            out.append(d)
    return sorted(out)


# -- birth dates in prose --------------------------------------------------------
_BORN = re.compile(r"\b(?:born|date of birth|birth ?date|year of birth|birth year|d\.?o\.?b\.?)\b", re.I)
_NOT_AGE = r"(?!\s*(?:%|percent|per\b|years?\s+(?:in|of\s+(?!age)|after|before|later|ago|imprison)|months?|days?|weeks?|hours?|times|counts?)|[.,/-]\d|\w)"
_AGE_PATTERNS = [re.compile(p, re.I) for p in (
    r"(?<![\d.,/$-])(\d{1,3})[\s-]*(?:years?|yrs?)[\s-]*old\b",
    r"(?<![\d.,/$-])(\d{1,3})\s+years?\s+of\s+age\b",
    r"\bage[d]?\s+(?:of\s+|was\s+|is\s+)?(\d{1,3})" + _NOT_AGE,
    r",\s*(?:an?\s+)?(\d{1,3})\s*,",
    r"\b(?:was|is|turned|then|reached|at)\s+(\d{1,3})" + _NOT_AGE,
)]
_SMALL_NUMBER = re.compile(r"(?<![\w.,/$£€-])(\d{1,3})(?![\w%/-]|[.,]\d)")
MIN_LISTED_AGE, MAX_LISTED_AGE = 16, 100   # outside this a number is not read as an age


def first_paragraph(text):
    return re.split(r"\n\s*\n", (text or "").strip(), maxsplit=1)[0]


def _mask(text, spans):
    chars = list(text)
    for start, end in spans:
        for i in range(start, end):
            chars[i] = " "
    return "".join(chars)


def find_age(text, loose=False):
    """An age stated in a passage, or None when there is none or more than one reading.
    Only wordings that state an age count ('aged 30', '30-year-old', 'he was 24');
    loose=True also accepts the only small number in a one-line search snippet."""
    masked = _mask(text, [(s, e) for _, s, e in D.find_dates(text, bare_years=True)])
    for pattern in _AGE_PATTERNS:
        ages = set(int(m.group(1)) for m in pattern.finditer(masked))
        ages = set(a for a in ages if MIN_LISTED_AGE <= a <= MAX_LISTED_AGE)
        if len(ages) == 1:
            return ages.pop()
        if len(ages) > 1:
            return None
    if not loose:
        return None
    ages = set(int(m.group(1)) for m in _SMALL_NUMBER.finditer(masked))
    return ages.pop() if len(ages) == 1 and MIN_LISTED_AGE <= min(ages) <= MAX_LISTED_AGE else None


def birth_from_text(text, loose=False):
    """Birth dates a passage gives: (dates, 'explicit') for a stated date of birth,
    (two years, 'age') for an age at a date, ([], None) otherwise."""
    text = text or ""
    for sentence in re.split(r"(?<=[.!?;])\s+", text):
        m = _BORN.search(sentence)
        if m:
            found = D.find_dates(sentence[m.end():], bare_years=True) or D.find_dates(sentence, bare_years=True)
            if found:
                return [found[0][0]], "explicit"
    for passage in re.split(r"(?<=[.!?])\s+", text) + [text]:
        age = find_age(passage, loose)
        if age is None:
            continue
        when = D.find_dates(passage) or D.find_dates(passage, bare_years=True)
        when = [w[0] for w in when]
        if len(set(w.year for w in when)) == 1:
            return D.birth_years_from_age(age, when[0]), "age"
    return [], None


def profile_birth(profile_notes, opening_line_only=False):
    """Read birth facts from the opening prose, including wrapped lines."""
    opening = first_paragraph(profile_notes)
    if opening_line_only:
        # Retain the original extraction for the clearance comparison.
        line = opening.splitlines()[0].strip() if opening else ""
        if not line or len(line) > 400 or re.match(r"according\b", line, re.I):
            return [], None
        return birth_from_text(line)

    # A provider's structured record or a report belongs to a separate source.
    if re.match(r"name\s*:", opening, re.I):
        return [], None
    opening = re.split(r"(?:^|\n|(?<=[.!?]) +)\s*according\b", opening, maxsplit=1, flags=re.I)[0]
    opening = " ".join(opening.split())

    for cue in _BORN.finditer(opening):
        after = opening[cue.end():]
        if cue.group().replace(".", "").lower() == "dob":
            after = after.lstrip(".")
        after = re.sub(r"^\s*(?:[:=–-]\s*)?(?:(?:is|was|on|in|at)\b\s+)*", "", after)
        dates = D.find_dates(after, bare_years=True)
        if dates and dates[0][1] == 0:
            return [dates[0][0]], "explicit"

    for sentence in re.split(r"(?<=[.!?;])\s+", opening):
        age = find_age(sentence)
        if age is None:
            continue
        dates = D.find_dates(sentence, bare_years=True)
        if len({date.year for date, _, _ in dates}) == 1:
            return D.birth_years_from_age(age, dates[0][0]), "age"
    return [], None


# -- web search results ----------------------------------------------------------
def search_keys(name):
    """Keys a name's search results may be filed under: its lowercase words in
    alphabetical order (accents dropped, initials left out)."""
    plain = unicodedata.normalize("NFKD", str(name or "").lower())
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    keys = []
    for tokens in (re.findall(r"[a-z]+", plain),
                   re.findall(r"[a-z]+", fold(name or "")),
                   re.findall(r"[a-z]+", fold(name or "").replace("'", "").replace("’", ""))):
        for keep_initials in (False, True):
            key = " ".join(sorted(t for t in tokens if keep_initials or len(t) > 1))
            if key and key not in keys:
                keys.append(key)
    return keys


def result_about_hit(snippet, phrase, hit_countries):
    """A search result is about the hit only if it describes the same kind of listing
    in a country tied to the hit."""
    if phrase not in _flat(snippet):
        return False
    return any(code in hit_countries for code in C.find_in_text(snippet, demonyms=True))


def search_birth(results, phrase, hit_countries):
    """Birth years from the search results that are about the hit.
    `results` are (result id, snippet). Returns (dates, ids of the results used)."""
    found, used = [], []
    for result_id, snippet in results:
        if not result_about_hit(snippet, phrase, hit_countries):
            continue
        dates, _ = birth_from_text(snippet, loose=True)
        if dates:
            used.append(result_id)
            for d in dates:
                if d not in found:
                    found.append(d)
    return sorted(found, key=D.show), used


# -- identity checks written up as notes -------------------------------------------
_IDENTITY = re.compile(
    r"passport|licen[cs]e|national id|identity|id card|\bkyc\b|verif|validat|authenticat|document|\bdob\b|date of birth", re.I)
_FAILED = re.compile(
    r"reject|fail|declin|expire|unsuccessful|not successful|could not|couldn.t|unable|not verified|"
    r"unverified|denied|invalid|did not pass|didn.t pass|refus|not approved|mismatch|fraudulent|forged|"
    r"inconclusive|abandon|cancel|incomplete|not match|no match", re.I)
_NAME_STOP = frozenset("DOB KYC ID UK US USA UAE EU OK PEP AML NIN SSN ISO PDF MRZ".split())
_EDGE = "([{\"'‘“"
_TAIL = ")]}\"'’”,.;:!?"


def _upper_name(text):
    """The longest run of upper-case words: how checks print the verified name.
    Placeholders inside the run (N/A, 0000) and initials stay part of it."""
    runs, run = [], []
    for token in text.split():
        if token[:1] in _EDGE and run:      # an opening bracket or quote ends the run
            runs.append(run)
            run = []
        core = token.lstrip(_EDGE)
        possessive = re.search(r"['’]s[,.;:!?)]*$", core, re.I)
        if possessive:
            core = core[:possessive.start()]
        word = core.rstrip(_TAIL)
        letters = sum(1 for ch in word if ch.isalpha())
        is_name = (
            (letters >= 2 and word == word.upper() and word not in _NAME_STOP)
            or re.match(r"^0{2,}$", word) is not None
            or (bool(run) and letters == 1 and len(word) == 1 and word.isupper())
        )
        if is_name:
            run.append(word)
        if run and (not is_name or possessive is not None or word != core):
            runs.append(run)                # a lower-case word or punctuation ends the run
            run = []
    if run:
        runs.append(run)
    runs = [r for r in runs if any(sum(1 for c in w if c.isalpha()) >= 2 for w in r)]
    if not runs:
        return None
    return " ".join(max(runs, key=lambda r: sum(len(w) for w in r)))


_CODE_AFTER = re.compile(r"\b(?:ctry|country|issued in|issued by|from)[:\s]+([A-Z]{2,3})\b")


def read_identity_note(text, created_at=None, is_check=False):
    """Read an identity check that was only written up as a note. Returns None when
    the note is not readable as an identity check, otherwise a dict with the verified
    name, date of birth, document country and whether the check passed.

    The legal name is the run of capitals. A note without one is still read for its
    date of birth when it says outright that the date is a birth date; its name then
    stays unknown, which can never clear a hit."""
    text = text or ""
    if not (is_check or _IDENTITY.search(text)):
        return None
    name = _upper_name(text)
    if name is None and not _BORN.search(text):
        return None
    if name:
        # the name is masked so that a name such as JORDAN or FRENCH is not read as a country
        text = text.replace(name, " ")
    found = [d for d, _, _ in D.find_dates(text, bare_years=True)]
    checked = D.parse_date(created_at)
    others = [d for d in found if d != checked]
    if checked is None and len(others) > 1:
        # the check is the latest date in the note; the birth date comes before it
        latest = max(others, key=lambda d: (d.year, d.month or 0, d.day or 0))
        others = [d for d in others if d != latest]
    dob = None
    if len(set(others)) == 1:
        dob = others[0]
    elif len(set(others)) > 1:
        earliest = min(others, key=lambda d: (d.year, d.month or 0, d.day or 0))
        if all(d.year > earliest.year + 10 for d in set(others) if d != earliest):
            dob = earliest
    codes = C.find_in_text(text, demonyms=True)
    if not codes:
        m = _CODE_AFTER.search(text)
        if m:
            code = C.resolve(m.group(1))
            if code and code != C.IGNORED:
                codes = [code]
    if dob is not None and checked is not None and not D.surely_before(dob, checked):
        dob = None  # a birth date cannot follow the check
    return {
        "name": name,
        "dob": dob,
        "country": codes[0] if len(codes) == 1 else None,
        "countries": codes,
        "approved": not _FAILED.search(text),
    }


def lived_in(text):
    """Countries a support note names. Any country named in a note about the customer
    counts as a place they lived: missing one could clear a hit that should not clear."""
    return C.find_in_text(text or "")
