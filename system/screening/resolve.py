"""Working out who the customer is (POLICY.md principles 2 to 4).

An alert shows the customer only as screened. This module follows the alert's link
(or searches the system of record when there is none), gathers every record that is
the same person, and builds one picture of them: declared names, the verified legal
name and date of birth from the latest approved identity check, and every country
tied to them. Each fact keeps the ID of the record it came from.
"""
import re

from . import countries as C
from . import dates as D
from . import extract as X
from .decide import COMPANY, PERSON, Customer
from .store import key, text
from .textutil import fold

APPROVED = frozenset("approved passed pass clear cleared verified accepted success successful".split())
# The policy lists the screened city among the details a record must fit.
CITY_REQUIRED = True
NAME_FIELDS = ("full_name", "preferred_name", "login_name")
COUNTRY_FIELDS = ("residence_country", "nationality")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
_TRAVEL_SENTENCE = re.compile(
    r"(?:the )?(?:customer|client) (?:only )?"
    r"(?:visited|travelled to|traveled to|went on (?:a )?holiday to) "
    r"(?P<place>[\w .’'&,-]+?)(?: for (?:a |the )?(?:short )?(?:holiday|vacation|visit|trip))?[.!?]?",
    re.IGNORECASE,
)


def _travel_only_countries(body):
    """Find countries mentioned only in clear, standalone travel statements."""
    travel, other = set(), []
    for sentence in _SENTENCE_BREAK.split(body):
        match = _TRAVEL_SENTENCE.fullmatch(sentence.strip())
        code = C.resolve(match["place"]) if match else None
        if code not in (None, C.IGNORED) and C.find_in_text(sentence) == [code]:
            travel.add(code)
        else:
            other.append(sentence)
    return travel.difference(C.find_in_text(" ".join(other))) if travel else travel


def kind_of(value):
    v = key(value)
    if v in ("individual", "person", "natural person"):
        return PERSON
    if v in ("company", "organisation", "organization", "entity", "business", "corporate", "corporation", "legal entity"):
        return COMPANY
    return None


def is_approved(check):
    return key(check.get("result")) in APPROVED


def phone_key(value):
    digits = "".join(ch for ch in text(value) if ch.isdigit())
    return digits if len(digits) >= 6 else None


def _order(d):
    return (d.year, d.month or 0, d.day or 0) if d else (0, 0, 0)


def _login(value):
    """A login name without its digits: 'j.smith88' is compared as 'j.smith'."""
    return "".join(ch for ch in text(value) if not ch.isdigit())


class Screened(object):
    """The customer as the alert shows them."""

    def __init__(self, alert, rules):
        c = alert.get("customer")
        if not isinstance(c, dict):  # flat layout: the fields sit on the alert itself
            c = {"name": alert.get("customer_name"), "entity_type": alert.get("entity_type"),
                 "dob": alert.get("dob"), "country": alert.get("country"), "city": alert.get("city")}
        self.name = text(c.get("name"))
        self.kind = kind_of(c.get("entity_type"))
        self.parts = rules.parts(self.name, self.kind == COMPANY)
        self.dob = D.parse_date(c.get("dob"))
        self.country = text(c.get("country"))
        code = C.resolve(self.country) if self.country else None
        self.code = code if code and code != C.IGNORED else None
        self.city = text(c.get("city"))
        self.at = D.parse_date(alert.get("screened_at"))


class Resolver(object):
    def __init__(self, store, note_reader=None):
        self.store = store
        self.rules = store.rules
        # how an identity check written as a note is read; the reader layer can replace it
        self.read_note = note_reader or X.read_identity_note
        self._features = {}
        self._pools = None
        self.by_phone_dob = {}   # (phone digits, full date of birth) -> record IDs
        self.by_document = {}    # document number on an approved check -> record IDs
        for rid, row in store.customer.items():
            dob, phone = D.parse_date(row.get("dob")), phone_key(row.get("phone"))
            if phone and dob and dob.day:
                self.by_phone_dob.setdefault((phone, dob), []).append(rid)
            for number in self._documents(rid):
                self.by_document.setdefault(number, []).append(rid)

    # -- one person, one picture -------------------------------------------------
    def _documents(self, rid):
        out = []
        for check in self.store.checks(rid):
            number = text(check.get("document_number")).upper()
            if number and is_approved(check) and number not in out:
                out.append(number)
        return out

    def person_of(self, rid):
        """Every record that is the same person: same phone and full date of birth, or
        the same document number on approved checks, followed transitively."""
        seen, queue = [rid], [rid]
        while queue:
            current = queue.pop()
            row = self.store.customer.get(current, {})
            linked = []
            dob, phone = D.parse_date(row.get("dob")), phone_key(row.get("phone"))
            if phone and dob and dob.day:
                linked += self.by_phone_dob.get((phone, dob), [])
            for number in self._documents(current):
                linked += self.by_document.get(number, [])
            for other in linked:
                if other not in seen:
                    seen.append(other)
                    queue.append(other)
        return sorted(seen)

    # -- records that fit what was screened ---------------------------------------
    def features(self, rid):
        got = self._features.get(rid)
        if got is None:
            row = self.store.customer[rid]
            kind = kind_of(row.get("entity_type"))
            names = [p for p in (self.rules.parts(_login(row.get(f)) if f == "login_name" else row.get(f), kind == COMPANY)
                                 for f in NAME_FIELDS) if p]
            codes = set()
            for f in COUNTRY_FIELDS:
                code = C.resolve(row.get(f))
                if code and code != C.IGNORED:
                    codes.add(code)
            place = fold(text(row.get("city")) + " | " + text(row.get("address")))
            got = (names, D.parse_date(row.get("dob")), codes, place, kind)
            self._features[rid] = got
        return got

    def fits(self, rid, screened, strict_kind=False):
        """A record fits when its name agrees with the screened name, its date of birth
        equals the screened one in every part both give, the screened country is its
        residence or nationality, and the screened city is in its city or address."""
        names, dob, codes, place, kind = self.features(rid)
        if strict_kind and kind and screened.kind and kind != screened.kind:
            return False
        if screened.dob and dob and not D.agrees(dob, screened.dob):
            return False
        if screened.code and screened.code not in codes:
            return False
        if CITY_REQUIRED and screened.city and fold(screened.city) not in place:
            return False
        if not screened.parts:
            return False
        return any(self.rules.agree(screened.parts, parts) for parts in names)

    def _build_pools(self):
        by_year, by_code, by_token = {}, {}, {}
        for rid in self.store.customer:
            names, dob, codes, _place, _kind = self.features(rid)
            by_year.setdefault(dob.year if dob else None, []).append(rid)
            for code in codes:
                by_code.setdefault(code, []).append(rid)
            tokens = set(t for parts in names for t in parts)
            for parts in names:  # parts written apart here may be written together when screened
                for i in range(len(parts) - 1):
                    tokens.add(parts[i] + parts[i + 1])
            for token in tokens:
                by_token.setdefault(token, []).append(rid)
        self._pools = (by_year, by_code, by_token)

    def search(self, screened):
        """No link: every record in the system of record that fits what was screened."""
        if not screened.parts:
            return []
        if self._pools is None:
            self._build_pools()
        by_year, by_code, by_token = self._pools
        if screened.dob:
            pool = by_year.get(screened.dob.year, []) + by_year.get(None, [])
        elif screened.code:
            pool = by_code.get(screened.code, [])
        else:
            wanted = list(screened.parts) + [a + b for a, b in zip(screened.parts, screened.parts[1:])]
            pool = set()
            for token, rids in by_token.items():
                if any(self.rules.part_match(part, token) for part in wanted):
                    pool.update(rids)
            pool = sorted(pool)
        return sorted(rid for rid in pool if self.fits(rid, screened, strict_kind=True))

    def candidates(self, alert, screened):
        """Record IDs the alert points at, and how they were found."""
        store = self.store
        found, how = [], ""
        ref, login, email = text(alert.get("account_ref")), key(alert.get("login_handle")), key(alert.get("email"))
        if ref and ref in store.accounts_by_id:
            found += [text(r.get("customer_id")) for r in store.accounts_by_id[ref]]
            how = "account reference %s" % ref
        if login and login in store.accounts_by_login:
            found += [text(r.get("customer_id")) for r in store.accounts_by_login[login]]
            how = how or "login handle %s" % text(alert.get("login_handle"))
        if email and email in store.customers_by_email:
            found += [text(r.get("record_id")) for r in store.customers_by_email[email]]
            how = how or "email %s" % text(alert.get("email"))
        unique = []
        for rid in found:
            if rid in store.customer and rid not in unique:
                unique.append(rid)
        if unique:
            if len(unique) > 1:  # a link can lead to several people: the screened details pick
                fitting = [rid for rid in unique if self.fits(rid, screened)]
                if fitting:
                    unique = fitting
            return unique, how
        used = ["name"] + [label for label, value in (("date of birth", screened.dob), ("country", screened.code), ("city", screened.city)) if value]
        details = used[0] if len(used) == 1 else ", ".join(used[:-1]) + " and " + used[-1]
        return self.search(screened), "screened " + details

    def people(self, alert):
        """The distinct people an alert may be about. Returns (screened details, how the
        records were found, [(record IDs of one person, the record first found)])."""
        screened = Screened(alert, self.rules)
        found, how = self.candidates(alert, screened)
        people, seen = [], set()
        for rid in found:
            if rid in seen:
                continue
            group = self.person_of(rid)
            seen.update(group)
            people.append((group, rid))
        return screened, how, people

    # -- the picture -----------------------------------------------------------------
    def picture(self, group, first, screened):
        """Everything known about one person, with the record each fact came from."""
        store = self.store
        kind = self.features(first)[4] or screened.kind
        names, countries, unknown = [], {}, []
        precautionary = set()

        def tie(code, source, raw=None):
            if code is None:
                if raw:
                    unknown.append(text(raw))
            elif code != C.IGNORED and source not in countries.setdefault(code, []):
                countries[code].append(source)

        checks = []  # (date, source ID, legal name, date of birth, [country codes], unread country)
        unread_check = False
        for rid in group:
            row = store.customer[rid]
            for f in NAME_FIELDS:
                if text(row.get(f)):
                    names.append((_login(row.get(f)) if f == "login_name" else text(row.get(f)), rid))
            for f in COUNTRY_FIELDS:
                if text(row.get(f)):
                    tie(C.resolve(row.get(f)), rid, row.get(f))
            for check in store.checks(rid):
                if not is_approved(check):
                    continue  # rejected or expired checks are not evidence
                raw = text(check.get("document_country"))
                code = C.resolve(raw) if raw else C.IGNORED
                checks.append((_order(D.parse_date(check.get("checked_at"))), text(check.get("check_id")),
                               text(check.get("verified_name")), D.parse_date(check.get("verified_dob")),
                               [code] if code and code != C.IGNORED else [], raw if code is None else None, False))
            for note in store.notes_of(rid):
                note_id, body = text(note.get("note_id")), text(note.get("text"))
                looks_like_check = key(note.get("channel")) == "kyc"
                got = self.read_note(body, note.get("created_at"), is_check=looks_like_check)
                if got is None:
                    unread_check = unread_check or looks_like_check
                    travel = _travel_only_countries(body) if not looks_like_check else ()
                    precautionary.update(travel)
                    for code in C.find_in_text(body, demonyms=looks_like_check):
                        if code not in travel:
                            tie(code, note_id)
                elif got["approved"]:
                    if got.get("dob") is None:
                        # the check was found but its date of birth was not: the declared
                        # date may differ from the verified one, so it must not clear a hit
                        unread_check = True
                    checks.append((_order(D.parse_date(note.get("created_at"))), note_id,
                                   got.get("name") or "", got.get("dob"), got.get("countries") or [], None,
                                   bool(got.get("soft"))))
        if screened.name:
            names.append((screened.name, None))

        verified_name = verified_source = None
        dob = dob_source = None
        soft_source = None  # a check read by the model in its cautious mode: supports, never clears
        if checks:
            latest = max(checks, key=lambda item: (item[0], item[1]))
            verified_name, verified_source = latest[2] or None, latest[1]
            if latest[6]:
                soft_source = latest[1]
            if latest[3]:
                dob, dob_source = latest[3], latest[1]
            for code in latest[4]:
                tie(code, latest[1])
            if latest[5]:
                unknown.append(latest[5])
            for check in checks:
                if check is not latest:
                    precautionary.update(check[4])
        if dob is None:
            for rid in [first] + [r for r in group if r != first]:
                declared = D.parse_date(store.customer[rid].get("dob"))
                if declared:
                    dob, dob_source = declared, rid
                    break
        if dob is None and screened.dob:
            dob = screened.dob
        # An identity check exists but could not be read: the declared date of birth may
        # not be the verified one, so it can agree with a hit but must not clear one.
        dob_can_clear = not (unread_check and dob_source not in [c[1] for c in checks])
        if soft_source is not None and dob_source == soft_source:
            dob_can_clear = False
        return Customer(kind, group, verified_name, verified_source, names, dob, dob_source,
                        countries, unknown, screened.at, primary=first, dob_can_clear=dob_can_clear,
                        name_can_clear=soft_source is None, precautionary_countries=precautionary.difference(countries))

    def screened_only(self, screened):
        """No record fits: the screened details are all there is. They are declared,
        unverified and tied to no record, so they can neither clear nor confirm a hit;
        only the entity type and a date of death, which need no record, still decide."""
        names = [(screened.name, None)] if screened.name else []
        return Customer(screened.kind, [], None, None, names, screened.dob, None, {}, [], screened.at,
                        dob_can_clear=False, confirmable=False)
