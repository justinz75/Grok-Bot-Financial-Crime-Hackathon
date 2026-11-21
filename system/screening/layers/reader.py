"""Reader layer: a language model reads identity checks the patterns cannot.

The rules read first and win: a note whose legal name they can read never reaches the
model. For the rest the model is asked to copy four things out of the note, and nothing
it says is believed until it has been checked:

    the name     must be written in the note, must not be a role, a provider, a month or
                 a country, and must share a name part with a name the bank already holds
                 for the customer the note is filed under;
    the date     must be written in the note, must be a real date, and must fall at least
                 14 years before the check (the day of the check is not a birth date);
    the country  must be written in the note and resolve to a country.

Anything that fails is dropped, not guessed.

    mode "on"       what the model reads is marked soft: it may support a match, it can
                    never clear a hit. A note the model thinks failed, or whose date of
                    birth the rules already read, is left exactly as the rules had it.
    mode "enforce"  what the model reads counts in full, and only when it gave a name
                    that passed every check above.

In both modes a check counts as read only when its date of birth was read. A note that
yields a name and no date stays unread, because an unread check is what stops the
customer's own declared date of birth from clearing a hit.

build(store, mode) returns a function with the signature of extract.read_identity_note.
"""
import hashlib
import re

from .. import countries as C
from .. import dates as D
from .. import extract as X
from .model import Client

SYSTEM = (
    "You copy facts out of a bank's internal note about an identity check. "
    "Copy text exactly as it is written in the note: do not correct, translate, reformat, complete or guess. "
    "Use null for anything the note does not say. "
    "Reply with one JSON object and nothing else, with exactly these keys: "
    '{"legal_name": string or null, "date_of_birth": string or null, '
    '"document_country": string or null, "outcome": "passed" or "failed" or "unclear"}. '
    "legal_name is the full name of the person or company whose identity was checked, "
    "never the checking provider or a member of staff, and null if the note names nobody. "
    "date_of_birth is that person's birth date, or a company's incorporation date, exactly as written; "
    "it is never the date the check was made. "
    "document_country is the country that issued the document, exactly as written. "
    "outcome is failed when the check was rejected, expired, failed or could not be completed, "
    "passed when it succeeded, and unclear otherwise."
)

# A note outside the identity-check channel must name a document before the model is
# asked: words like "verified" or "documentation" also turn up in ordinary support notes.
_DOCUMENT = re.compile(
    r"passport|licen[cs]e|national id|identity card|id card|identity document|residence permit|"
    r"registry extract|certificate of incorporation|\bkyc\b|identity (?:check|verification)", re.I)
# Words a model may hand back as a "name" that name nobody: roles, document words and
# the companies that run identity checks.
_NOT_A_NAME = frozenset(
    "customer client user holder applicant individual subject person account the a an of and "
    "mr mrs ms miss dr sir madam company business entity owner member staff agent team "
    "provider document passport licence license record records note identity check kyc id "
    "national driving card verification onboarding "
    "sumsub veriff persona onfido jumio trulioo idnow yoti socure mitek".split())
MIN_YEARS_BEFORE_CHECK = 14  # a date closer to the check than this is a document date, not a birth date


def _is_country(text):
    code = C.resolve(text)
    return code is not None and code != C.IGNORED


def _names_nobody(token):
    """True for a word that cannot be a name on its own: a role, a month, a country."""
    return not token or token in _NOT_A_NAME or token in D.MONTHS or _is_country(token)


def _flat(text):
    return " ".join(str(text).split()).casefold()


def _without(body, name):
    """The note with the legal name blanked, so a name such as Jordan is not read as a country."""
    if not name:
        return body
    pattern = r"\s+".join(re.escape(part) for part in name.split())
    return re.sub(pattern, " ", body, flags=re.I)


def question(body, created_at=None):
    """The user prompt for one note."""
    written = D.show(D.parse_date(created_at)) or "unknown"
    return "The note was written on %s.\nNote:\n<<<\n%s\n>>>" % (written, body)


def verify(answer, body, created_at=None):
    """Keep only what is really written in the note. Returns
    {"name", "dob", "code", "outcome"}, each None when it could not be confirmed."""
    flat = _flat(body)
    checked = D.parse_date(created_at)

    name = answer.get("legal_name")
    if isinstance(name, str):
        name = " ".join(name.split()).strip(" ,.;:")
        letters = sum(1 for ch in name if ch.isalpha())
        tokens = [t.strip(".,;:'’").casefold() for t in name.split()]
        if (letters < 2 or len(tokens) > 8 or _flat(name) not in flat
                or any(ch.isdigit() for ch in name)
                or _is_country(name)
                or all(_names_nobody(t) for t in tokens)):
            name = None
    else:
        name = None

    dob = None
    raw = answer.get("date_of_birth")
    if isinstance(raw, str) and raw.strip() and _flat(raw) in flat:
        dob = D.parse_date(raw.strip())
        if dob is None:
            inside = D.find_dates(raw, bare_years=True)
            dob = inside[0][0] if len(inside) == 1 else None
        if dob is not None and checked is not None and (
                not D.surely_before(dob, checked) or dob.year > checked.year - MIN_YEARS_BEFORE_CHECK):
            dob = None  # the day of the check, or a document's own date, is not a birth date

    code = None
    raw = answer.get("document_country")
    if isinstance(raw, str) and raw.strip() and _flat(raw) in flat:
        code = C.resolve(raw.strip())
        if code is None or code == C.IGNORED:
            found = C.find_in_text(raw, demonyms=True)
            code = found[0] if len(found) == 1 else None

    outcome = answer.get("outcome")
    outcome = outcome.strip().lower() if isinstance(outcome, str) else None
    if outcome not in ("passed", "failed", "unclear"):
        outcome = None
    return {"name": name, "dob": dob, "code": code, "outcome": outcome}


def _digest(body):
    return hashlib.sha1(body.encode("utf-8", "replace")).hexdigest()


class Owners(object):
    """Which names the bank already holds for the customer a note is filed under."""

    def __init__(self, store):
        self.store = store
        self._index = None

    def names(self, body):
        """Names on the records the note belongs to; [] when it belongs to none; None
        when there is no loaded data folder to look in."""
        notes = getattr(self.store, "notes", None)
        by_email = getattr(self.store, "customers_by_email", None)
        if notes is None or by_email is None:
            return None
        if self._index is None:
            index = {}
            for note in notes:
                email = str(note.get("requester_email") or "").strip().lower()
                if email:
                    index.setdefault(_digest(str(note.get("text") or "").strip()), set()).add(email)
            self._index = index
        found = []
        for email in sorted(self._index.get(_digest(body.strip()), ())):
            for row in by_email.get(email, []):
                for field in ("full_name", "preferred_name", "login_name"):
                    value = str(row.get(field) or "").strip()
                    if value and value not in found:
                        found.append(value)
        return found

    def support(self, name, body):
        """True when the name shares a name part with a name the bank holds for the
        note's customer, by the bank's own name rules."""
        known = self.names(body)
        if known is None:
            return True                       # nothing to check against
        rules = self.store.rules
        mine = rules.parts(name)
        return any(rules.part_match(a, b) for held in known for a in mine for b in rules.parts(held))


def build(store, mode, client=None):
    client = client or Client()
    soft = mode != "enforce"
    owners = Owners(store)

    def needs_model(body, created_at, is_check, got):
        """True when the rules could not read this note and the model may be asked."""
        if got is not None and got.get("name"):
            return False                      # the rules read the legal name: they win
        if not client.available or not body:
            return False
        if not (is_check or (X._IDENTITY.search(body) and _DOCUMENT.search(body))):
            return False                      # not an identity check
        if soft and got is not None and got.get("dob"):
            return False                      # cautious mode: keep the date of birth the rules read at full weight
        return True

    def read(body, created_at=None, is_check=False):
        body = body or ""
        got = X.read_identity_note(body, created_at, is_check)
        if not needs_model(body, created_at, is_check, got):
            return got
        try:
            answer, _agreement = client.consensus(SYSTEM, question(body, created_at))
        except Exception:
            answer = None
        if not isinstance(answer, dict):
            return got                        # no answer, or the runs disagreed: nothing learned
        try:
            facts = verify(answer, body, created_at)
            name = facts["name"]
            if name and not owners.support(name, body):
                return got                    # the bank's own records do not know this name: believe none of it
        except Exception:
            return got
        if name is None and not (soft and is_check):
            return got                        # full weight needs a name; a date alone is only ever soft
        dob = (got or {}).get("dob") or facts["dob"]
        if dob is None:
            # A check whose date of birth nobody could read stays unread. Calling it read
            # would hand the customer's declared date of birth the power to clear a hit.
            return got
        failed = facts["outcome"] == "failed" or bool(X._FAILED.search(body))
        if failed and soft:
            return got                        # cautious mode never lets the model set a check aside
        codes = list((got or {}).get("countries") or [])
        if not codes:
            # cautious mode keeps every country the note could mean, even one inside the name
            codes = C.find_in_text(body if soft else _without(body, name), demonyms=True)
        if facts["code"] and facts["code"] not in codes:
            codes.append(facts["code"])
        return {
            "name": name, "dob": dob,
            "country": codes[0] if len(codes) == 1 else None, "countries": codes,
            "approved": not failed, "soft": soft, "read_by": "model",
        }

    def warm(items):
        """Ask about every note that needs the model at once, so read() finds the answers
        already there. items are (body, created_at, is_check)."""
        asks, seen = [], set()
        for body, created_at, is_check in items:
            body = body or ""
            try:
                got = X.read_identity_note(body, created_at, is_check)
            except Exception:
                continue
            if needs_model(body, created_at, is_check, got):
                prompt = question(body, created_at)
                if prompt not in seen:
                    seen.add(prompt)
                    asks.extend((SYSTEM, prompt, run) for run in range(client.runs))
        if asks:
            client.ask_all(asks)
        return len(asks)

    read.warm = warm
    read.client = client
    read.mode = mode
    return read
