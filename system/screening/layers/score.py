"""Strength-of-evidence score: how much the facts point to the same person, in bits.

The rules say whether a contradiction or an agreement exists. This layer says how much
each one weighs. It is the classic record-linkage sum (Fellegi and Sunter): every field
adds log2(m / u), where m is how often the field agrees for the same person and u how
often it agrees by chance. Chance is measured on the bank's own customers, so a rare
name that agrees counts for far more than a common one.

Positive bits point to the same person, negative to a different one. The score never
decides anything: it is shown beside the decision, and when set to enforce it can only
ask for a person to look at a clearance that the evidence leans against.

Pure arithmetic: no model, no randomness, no clock. The same folder gives the same bits.
"""
import math

from .. import countries as C
from .. import dates as D
from ..decide import COMPANY, DIFFERENT
from ..resolve import kind_of

NAME_FIELDS = ("full_name", "preferred_name")
COUNTRY_FIELDS = ("residence_country", "nationality")

BAND_STRONG_SAME = "strong evidence of the same"
BAND_SOME_SAME = "some evidence of the same"
BAND_INCONCLUSIVE = "inconclusive"
BAND_SOME_DIFFERENT = "some evidence of a different one"
BAND_STRONG_DIFFERENT = "strong evidence of a different one"

CONFLICT_AT = 3.0            # a clearance with at least this many bits for "same" is a conflict
# The most an agreement can weigh. These three numbers are the calibration.
#
# A hit exists because the name is similar, so an agreeing name is the normal state
# of every hit and can only say so much. Uncapped (14 bits for a rare name) it
# outweighed a country difference and flagged 284 of the 504 clearances on the
# development set, 19 of them among the 28 clearances the practice labels confirm.
# At 4 and 3 no confirmed clearance is flagged, and what is left to flag is the case
# that deserves it: everything agrees and the contradiction is a small one.
NAME_AGREE_MAX = 4.0
DOB_AGREE_MAX = 12.0
COUNTRY_AGREE_MAX = 3.0
NAME_MISMATCH_BITS = -6.0
COUNTRY_MISMATCH_BITS = -3.3
ENTITY_TYPE_BITS = -12.0
TIMING_BITS = -10.0
DEATH_BITS = -10.0
YEARS_OF_BIRTH = 60.0        # the spread of birth years among adults, for chance agreement


def band(bits):
    """The words for a total."""
    if bits >= 8:
        return BAND_STRONG_SAME
    if bits >= 3:
        return BAND_SOME_SAME
    if bits > -3:
        return BAND_INCONCLUSIVE
    if bits > -8:
        return BAND_SOME_DIFFERENT
    return BAND_STRONG_DIFFERENT


def _round(value):
    value = round(float(value), 1)
    return 0.0 if value == 0 else value  # never "-0.0"


def _clamp(value, low, high):
    return max(low, min(high, value))


def _one_in(u):
    """'1 customer in K' for a chance u."""
    k = int(round(1.0 / u)) if u > 0 else 0
    return "{:,}".format(max(k, 1))


def _item(field, state, bits, detail):
    return {"field": field, "state": state, "bits": _round(bits), "detail": detail}


def _shown(values, limit=4):
    values = list(values)
    return ", ".join(values[:limit]) + (" and %d more" % (len(values) - limit) if len(values) > limit else "")


class Score(object):
    def __init__(self, store, mode="on"):
        self.mode = mode
        self.rules = getattr(store, "rules", None)
        self.n = 0
        self.part_share = {}      # name part -> share of customer records that carry it
        self.country_share = {}   # country code -> share of customer records tied to it
        part_count, country_count, resolved = {}, {}, {}
        for row in (getattr(store, "customers", None) or []):
            if not isinstance(row, dict):
                continue
            self.n += 1
            company = kind_of(row.get("entity_type")) == COMPANY
            parts = set()
            for field in NAME_FIELDS:
                value = row.get(field)
                if value and self.rules is not None:
                    parts.update(self.rules.parts(value, company))
            for part in parts:
                part_count[part] = part_count.get(part, 0) + 1
            codes = set()
            for field in COUNTRY_FIELDS:
                value = row.get(field)
                if not value:
                    continue
                if value not in resolved:
                    resolved[value] = C.resolve(value)
                code = resolved[value]
                if code and code != C.IGNORED:
                    codes.add(code)
            for code in codes:
                country_count[code] = country_count.get(code, 0) + 1
        if self.n:
            n = float(self.n)
            self.part_share = dict((part, count / n) for part, count in part_count.items())
            self.country_share = dict((code, count / n) for code, count in country_count.items())

    # -- name ---------------------------------------------------------------------
    def _agreeing_names(self, case, company):
        """The customer name and the hit name that agree, as part lists, found in the
        order the rules look: the verified legal name first, then the declared names."""
        rules, customer, hit = case.rules, case.customer, case.hit
        need = 1 if company else 2
        hit_parts = [p for p in (rules.parts(n, company) for n in (getattr(hit, "names", None) or [])) if p]
        candidates = []
        if getattr(customer, "verified_name", None):
            candidates.append(customer.verified_name)
        candidates += [name for name, _source in (getattr(customer, "names", None) or []) if name]
        first = None
        for name in candidates:
            parts = rules.parts(name, company)
            if not parts:
                continue
            first = first or parts
            if len(parts) < need:
                continue
            for other in hit_parts:
                if rules.agree(parts, other):
                    return parts, other
        return first, None

    def _name(self, case, company):
        state = case.states.get("name", "unknown")
        customer = case.customer
        if state == "mismatch":
            return _item("name", state, NAME_MISMATCH_BITS,
                         "The verified legal name %s agrees with none of the hit's names"
                         % (getattr(customer, "verified_name", None) or ""))
        if state != "agree":
            return _item("name", "unknown", 0.0, self._name_unknown(case, company))
        parts, other = self._agreeing_names(case, company)
        if not parts:
            return _item("name", state, 0.0, "The names agree, but the matching parts could not be listed")
        if not self.n:
            return _item("name", state, 0.0, "The names agree; there are no customer records to say how common the name is")
        matched = [p for p in parts if other and any(case.rules.part_match(p, q) for q in other)] or list(parts)
        floor = 1.0 / self.n
        u = 1.0
        for part in matched:
            u *= max(self.part_share.get(part, 0.0), floor)
        u = min(u, 0.5)
        bits = _clamp(math.log(0.9 / u, 2), 0.5, NAME_AGREE_MAX)
        count ="%d part%s match%s" % (len(matched), "" if len(matched) == 1 else "s", "es" if len(matched) == 1 else "")
        pronoun = "it" if len(matched) == 1 else "them"
        if u < floor:
            detail = "%s; fewer than 1 customer in %s would share %s by chance" % (count, "{:,}".format(self.n), pronoun)
        else:
            detail = "%s; about 1 customer in %s shares %s" % (count, _one_in(u), pronoun)
        return _item("name", state, bits, detail)

    def _name_unknown(self, case, company):
        rules, customer, hit = case.rules, case.customer, case.hit
        need = 1 if company else 2
        if not any(rules.parts(n, company) for n in (getattr(hit, "names", None) or [])):
            return "The hit has no usable name to compare"
        names = [customer.verified_name] if getattr(customer, "verified_name", None) else []
        names += [name for name, _source in (getattr(customer, "names", None) or []) if name]
        if not names:
            return "The customer has no name on record to compare"
        if all(len(rules.parts(n, company)) < need for n in names):
            return "The customer's name has fewer than two real parts, so it can neither confirm nor clear"
        if getattr(customer, "verified_name", None) and not getattr(customer, "name_can_clear", True):
            return ("No declared name agrees with the hit's, and the legal name was read by a model or from a note "
                    "that cannot be believed, which may not clear a hit")
        if getattr(customer, "verified_name", None):
            return "The verified name has too few real parts to compare, and no other name agrees with the hit's"
        return "No name on the customer's records agrees with the hit's, and there is no verified legal name to rule it out"

    # -- date of birth ----------------------------------------------------------------
    def _dob(self, case, company):
        state = case.states.get("dob", "unknown")
        mine = getattr(case.customer, "dob", None)
        theirs = [d for d in (getattr(case.hit, "dobs", None) or []) if d]
        noun = "incorporation date" if company else "date of birth"
        if state == "agree" and mine and theirs:
            agreeing = [h for h in theirs if D.agrees(mine, h)]
            if mine.day and any(h.day for h in agreeing):
                u = 1.0 / (365.25 * YEARS_OF_BIRTH)
                detail = "%s is the hit's full %s" % (D.show(mine), noun)
            elif mine.month and any(h.month for h in agreeing):
                u = 1.0 / (12 * YEARS_OF_BIRTH)
                detail = "%s agrees with the hit's %s to the month" % (D.show(mine), noun)
            else:
                years = sorted(set(h.year for h in theirs))
                u = min(len(years) / YEARS_OF_BIRTH, 1.0)
                if len(years) == 1:
                    detail = "%d is the hit's year" % mine.year
                else:
                    detail = "%d is one of the hit's %d possible years (%s)" % (
                        mine.year, len(years), _shown(str(y) for y in years))
            return _item("date of birth", state, _clamp(math.log(0.95 / u, 2), 0.5, DOB_AGREE_MAX), detail)
        if state == "mismatch" and mine and theirs:
            gap = min(abs(mine.year - h.year) for h in theirs)
            shown = _shown(D.show(h) for h in theirs)
            if gap == 0:
                detail = "%s against %s: the same year, but the month or day differs" % (D.show(mine), shown)
            else:
                detail = "%s against %s: %d year%s apart" % (D.show(mine), shown, gap, "" if gap == 1 else "s")
            return _item("date of birth", state, -(4 + min(gap, 10)), detail)
        if not mine and not theirs:
            detail = "Neither side gives a %s" % noun
        elif not mine:
            detail = "The customer has no %s on file" % noun
        elif not theirs:
            detail = "The hit gives no %s" % noun
        elif D.compare(mine, theirs) == "mismatch":
            detail = ("The dates differ (%s against %s), but the customer's is not from a readable identity "
                      "check, so it may not clear a hit" % (D.show(mine), _shown(D.show(h) for h in theirs)))
        else:
            detail = "%s against %s: too close to contradict, not equal enough to agree" % (
                D.show(mine), _shown(D.show(h) for h in theirs))
        return _item("date of birth", "unknown", 0.0, detail)

    # -- country ----------------------------------------------------------------------
    def _country(self, case):
        state = case.states.get("location", "unknown")
        mine = sorted(getattr(case.customer, "countries", None) or {})
        theirs = sorted(getattr(case.hit, "countries", None) or [])
        if state == "agree":
            shared = sorted(case.states.get("shared") or (set(mine) & set(theirs)))
            if not shared:
                return _item("country", state, 0.0, "The countries agree, but the shared one could not be listed")
            if not self.n:
                return _item("country", state, 0.0,
                             "%s in common; there are no customer records to say how common it is" % C.name_of(shared[0]))
            floor = 1.0 / self.n
            code = max(shared, key=lambda c: (self.country_share.get(c, 0.0), c))
            u = max(self.country_share.get(code, 0.0), floor)
            more = " (and %d more in common)" % (len(shared) - 1) if len(shared) > 1 else ""
            detail = "%s, shared by about 1 customer in %s%s" % (C.name_of(code), _one_in(u), more)
            return _item("country", state, _clamp(math.log(0.9 / u, 2), 0.3, COUNTRY_AGREE_MAX), detail)
        if state == "mismatch":
            return _item("country", state, COUNTRY_MISMATCH_BITS, "%s against %s" % (
                _shown(sorted(C.name_of(c) for c in mine)), _shown(sorted(C.name_of(c) for c in theirs))))
        if not mine and not theirs:
            detail = "Neither side is tied to a country"
        elif not mine:
            detail = "The customer is tied to no country"
        elif not theirs:
            detail = "The hit is tied to no country"
        else:
            detail = "A country on one side could not be read, so the countries cannot be compared"
        return _item("country", "unknown", 0.0, detail)

    # -- the whole score ----------------------------------------------------------------
    def annotate(self, case):
        """{"bits", "band", "contributions", "conflict"} for one person against one hit."""
        company = getattr(case.customer, "kind", None) == COMPANY
        contributions = []
        for field, make in (("name", lambda: self._name(case, company)),
                            ("date of birth", lambda: self._dob(case, company)),
                            ("country", lambda: self._country(case))):
            try:
                contributions.append(make())
            except Exception:  # an odd record weighs nothing; it must not stop the run
                contributions.append(_item(field, "unknown", 0.0, "This could not be weighed"))
        codes = list(getattr(case.outcome, "codes", None) or [])
        if "ENTITY_TYPE_MISMATCH" in codes:
            contributions.append(_item("entity type", "mismatch", ENTITY_TYPE_BITS, "The customer is a %s and the hit is a %s" % (
                getattr(case.customer, "kind", None) or "customer", getattr(case.hit, "kind", None) or "listed entity")))
        if "TEMPORAL_IMPOSSIBILITY" in codes:
            report = D.show(getattr(case.hit, "earliest_report", None))
            what = "The customer was not yet incorporated" if company else "The customer was too young"
            contributions.append(_item("timing", "mismatch", TIMING_BITS, "%s at the hit's earliest dated report%s" % (
                what, ", " + report if report else "")))
        if "DECEASED" in codes:
            death = D.show(getattr(case.hit, "death", None))
            contributions.append(_item("death", "mismatch", DEATH_BITS, "The hit's profile gives a date of death%s, before the customer was screened" % (
                " of " + death if death else "")))
        bits = _round(sum(item["bits"] for item in contributions))
        conflict = getattr(case.outcome, "decision", None) == DIFFERENT and bits >= CONFLICT_AT
        return {"bits": bits, "band": band(bits), "contributions": contributions, "conflict": bool(conflict)}

    def guard(self, case, note):
        """Why a clearance needs a person: the evidence leans the other way."""
        if note and note.get("conflict"):
            return "the strength-of-evidence score leans towards the same person (%+.1f bits)" % note["bits"]
        return None


def build(store, mode):
    return Score(store, mode)
