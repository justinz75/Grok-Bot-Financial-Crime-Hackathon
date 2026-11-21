"""Date rules (POLICY.md principles 5 to 7).

Dates are partial: a year, a year and month, or a full date. A missing part is
unknown, never a mismatch.
"""
import calendar
import re
from collections import namedtuple

PDate = namedtuple("PDate", "year month day")

_MONTH_NAMES = (
    "january february march april may june july august september october november december".split()
)
MONTHS = {}
for _i, _name in enumerate(_MONTH_NAMES, 1):
    MONTHS[_name] = _i
    MONTHS[_name[:3]] = _i
MONTHS["sept"] = 9

MON = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"


MIN_YEAR, MAX_YEAR = 1800, 2100  # a year outside these is not a date of birth or of a report


def make(year, month=None, day=None):
    """A PDate, or None when the parts are not a real date."""
    try:
        year = int(year)
        month = int(month) if month else None
        day = int(day) if day else None
    except (TypeError, ValueError):
        return None
    if not MIN_YEAR <= year <= MAX_YEAR:
        return None
    if month is None:
        return PDate(year, None, None)
    if not 1 <= month <= 12:
        return None
    if day is None:
        return PDate(year, month, None)
    if not 1 <= day <= calendar.monthrange(year, month)[1]:
        return None
    return PDate(year, month, day)


class Ambiguous(PDate):
    """A numeric date whose day and month could be either way round, such as 04/03/1980.

    As a tuple it is the day-first reading, so it sorts, prints, indexes and agrees as
    before. `other` is the month-first reading. A contradiction, and a date surely before
    another, must hold under both readings: reading a date the wrong way round must never
    clear a hit."""


def _ambiguous(first, second):
    d = Ambiguous(*first)
    d.other = second
    return d


def readings(d):
    """Every way a date can be read: one for most dates, two for an ambiguous one."""
    other = getattr(d, "other", None)
    if other is None:
        return (d,)
    return (PDate(*d), other)


def _day_first(a, b, year):
    """Numeric dates are day first; month first only when day first is impossible.
    When both readings are possible and differ, the date is Ambiguous."""
    a, b = int(a), int(b)
    if a <= 12 < b:
        return make(year, a, b)
    first = make(year, b, a)
    if first is not None and a <= 12 and b <= 12 and a != b:
        return _ambiguous(first, make(year, a, b))
    return first


_NUMERIC = [
    (re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[T ]\d.*)?$"), lambda m: make(m.group(1), m.group(2), m.group(3))),
    (re.compile(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$"), lambda m: _day_first(m.group(1), m.group(2), m.group(3))),
    (re.compile(r"(\d{4})[-/.](\d{1,2})$"), lambda m: make(m.group(1), m.group(2))),
    (re.compile(r"(\d{1,2})[-/.](\d{4})$"), lambda m: make(m.group(2), m.group(1))),
    (re.compile(r"(\d{4})$"), lambda m: make(m.group(1))),
]
_TEXTUAL = [
    (re.compile(r"(\d{1,2}) (%s) (\d{4})$" % MON), lambda m: make(m.group(3), MONTHS[m.group(2)], m.group(1))),
    (re.compile(r"(%s) (\d{1,2}) (\d{4})$" % MON), lambda m: make(m.group(3), MONTHS[m.group(1)], m.group(2))),
    (re.compile(r"(%s) (\d{4})$" % MON), lambda m: make(m.group(2), MONTHS[m.group(1)])),
]


def parse_date(value):
    """Parse one date written in any of the bank's or the provider's formats."""
    if value is None:
        return None
    if isinstance(value, PDate):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return make(int(value)) if float(value).is_integer() else None
    text = str(value).strip()
    if not text:
        return None
    for pattern, build in _NUMERIC:
        m = pattern.match(text)
        if m:
            return build(m)
    text = text.lower()
    text = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", text)
    text = re.sub(r"\bof\b", " ", text)
    text = re.sub(r"[,.\-/]", " ", text)
    text = " ".join(text.split())
    for pattern, build in _TEXTUAL:
        m = pattern.match(text)
        if m:
            return build(m)
    return None


def _items(value):
    """The items of a multi-valued field such as a hit's dobs, given as a list or as
    one string ('1996; 1997')."""
    if value is None:
        return []
    return value if isinstance(value, (list, tuple)) else re.split(r"[;|\n]", str(value))


def parse_dates(value):
    """Every date in a multi-valued field such as a hit's dobs ('1996; 1997')."""
    out, seen = [], []
    for item in _items(value):
        d = parse_date(item)
        # an ambiguous date is kept beside the plain date it equals as a tuple
        if d and readings(d) not in seen:
            out.append(d)
            seen.append(readings(d))
    return out


_FOUR_DIGITS = re.compile(r"(?<!\d)\d{4}(?!\d)")


def unread_dates(value):
    """The items of a multi-valued date field that could not be read and may still be
    the date that agrees. parse_dates leaves them out; such a date is unknown, not absent.

    Two kinds of item are not listed, because they cannot agree with any date held here:
    one with no digit in it, which gives no date, and one whose only four-digit numbers
    are years no date here can have, such as 1340, a year from another calendar."""
    out = []
    for item in _items(value):
        shown = "" if item is None else str(item).strip()
        if not shown or shown in out or parse_date(item) is not None:
            continue
        if not any(ch.isdigit() for ch in shown):
            continue
        years = [int(y) for y in _FOUR_DIGITS.findall(shown)]
        if years and not any(MIN_YEAR <= y <= MAX_YEAR for y in years):
            continue
        out.append(shown)
    return out


# -- dates inside sentences ---------------------------------------------------
_IN_TEXT = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda m: make(m.group(1), m.group(2), m.group(3))),
    (re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b"), lambda m: _day_first(m.group(1), m.group(2), m.group(3))),
    (re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b"), lambda m: _day_first(m.group(1), m.group(2), m.group(3))),
    (re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s+of)?\s+(%s)\.?,?\s+(\d{4})\b" % MON, re.I),
     lambda m: make(m.group(3), MONTHS[m.group(2).lower()], m.group(1))),
    (re.compile(r"\b(%s)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b" % MON, re.I),
     lambda m: make(m.group(3), MONTHS[m.group(1).lower()], m.group(2))),
    (re.compile(r"\b(%s)\.?,?\s+(?:of\s+)?(\d{4})\b" % MON, re.I), lambda m: make(m.group(2), MONTHS[m.group(1).lower()])),
]
_BARE_YEAR = re.compile(r"(?<![\d,.])\b(1[89]\d{2}|20\d{2})\b(?![\d]|,\d{3})")


def find_dates(text, bare_years=False):
    """Dates written inside a sentence, as (PDate, start, end), left to right."""
    found, taken = [], []
    patterns = list(_IN_TEXT)
    if bare_years:
        patterns.append((_BARE_YEAR, lambda m: make(m.group(1))))
    for pattern, build in patterns:
        for m in pattern.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            d = build(m)
            if d:
                found.append((d, m.start(), m.end()))
                taken.append((m.start(), m.end()))
    return sorted(found, key=lambda item: item[1])


# -- comparison ---------------------------------------------------------------
def contradicts(customer, hit):
    """A hit birth date is contradicted when the customer's year is more than 1 year
    outside it, or both give a month in the same year and the months (or days) differ.
    An ambiguous date contradicts only when every reading does."""
    return all(_contradicts(c, h) for c in readings(customer) for h in readings(hit))


def _contradicts(customer, hit):
    if abs(customer.year - hit.year) > 1:
        return True
    if customer.year == hit.year and customer.month and hit.month:
        if customer.month != hit.month:
            return True
        if customer.day and hit.day and customer.day != hit.day:
            return True
    return False


def agrees(customer, hit):
    """Dates agree when the years are equal and every part both give is equal.
    An ambiguous date is compared as read, day first: agreement never clears a hit."""
    if customer.year != hit.year:
        return False
    if customer.month and hit.month:
        if customer.month != hit.month:
            return False
        if customer.day and hit.day and customer.day != hit.day:
            return False
    return True


def compare(customer, hit_dates):
    """'agree' if one hit date agrees, 'mismatch' if every hit date is contradicted,
    otherwise 'unknown'."""
    if customer is None or not hit_dates:
        return "unknown"
    if any(agrees(customer, h) for h in hit_dates):
        return "agree"
    if all(contradicts(customer, h) for h in hit_dates):
        return "mismatch"
    return "unknown"


def birth_years_from_age(age, when):
    """Someone aged 45 in March 2019 was born in 1973 or 1974."""
    return [make(when.year - age - 1), make(when.year - age)]


def max_age_on(birth, when):
    """The oldest the person can have been on `when`, given what the dates leave open."""
    return max(_max_age_on(b, w) for b in readings(birth) for w in readings(when))


def _max_age_on(birth, when):
    b = (birth.month or 1, birth.day or 1)
    w = (when.month or 12, when.day or 31)
    return when.year - birth.year - (1 if w < b else 0)


def surely_before(a, b):
    """True when partial date a is before b whatever the missing parts are, and
    whichever way round an ambiguous date is read."""
    return all(_surely_before(x, y) for x in readings(a) for y in readings(b))


def _surely_before(a, b):
    latest_a = (a.year, a.month or 12, a.day or 31)
    earliest_b = (b.year, b.month or 1, b.day or 1)
    return latest_a < earliest_b


def show(d):
    if d is None:
        return ""
    if d.day:
        return "%04d-%02d-%02d" % (d.year, d.month, d.day)
    if d.month:
        return "%04d-%02d" % (d.year, d.month)
    return "%04d" % d.year
