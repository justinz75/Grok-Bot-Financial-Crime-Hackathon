"""The decision table (POLICY.md principles 6 and 7).

Clear only on a contradiction, confirm only on agreement, otherwise REVIEW.
Every outcome carries the facts that decided it and the record IDs they came from.
"""
from . import countries as C
from . import dates as D

DIFFERENT, SAME, REVIEW = "DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW"
PERSON, COMPANY = "person", "company"
AMBIGUOUS = "AMBIGUOUS"

# Contradictions, in the order the reasons are written.
CLEARING_ORDER = [
    "ENTITY_TYPE_MISMATCH", "DECEASED", "TEMPORAL_IMPOSSIBILITY",
    "DOB_MISMATCH", "LOCATION_MISMATCH", "NAME_MISMATCH_VERIFIED",
]
MIN_AGE = 16  # younger than this at the earliest dated report is impossible


class Customer(object):
    """One person or company in the bank: every record that is them, as one picture."""

    def __init__(self, kind, record_ids=(), verified_name=None, verified_source=None,
                 names=(), dob=None, dob_source=None, countries=None,
                 unknown_countries=(), screened_at=None, primary=None, dob_can_clear=True,
                 confirmable=True, name_can_clear=True, possible_countries=None, dob_in_doubt=False):
        self.kind = kind
        self.dob_can_clear = dob_can_clear        # False when an identity check could not be read
        self.dob_in_doubt = dob_in_doubt          # True when a check gives a date that could not be read with confidence
        self.confirmable = confirmable            # False when no customer record was found
        self.name_can_clear = name_can_clear      # False when the legal name was read by a model, or from a note that cannot be believed
        self.possible_countries = dict(possible_countries or {})  # code -> notes that only mention it
        self.record_ids = sorted(record_ids)
        self.primary = primary or (self.record_ids[0] if self.record_ids else None)  # the record first found
        self.verified_name = verified_name        # legal name on the latest approved check
        self.verified_source = verified_source    # the KYC check or note it came from
        self.names = list(names)                  # declared names: (name, source id)
        self.dob = dob                            # PDate (incorporation date for a company)
        self.dob_source = dob_source
        self.countries = dict(countries or {})    # code -> source ids
        self.unknown_countries = list(unknown_countries)
        self.screened_at = screened_at


class Hit(object):
    """One watchlist profile, with its facts gathered from wherever they are."""

    def __init__(self, hit_id, kind, name, aliases=(), dobs=(), dob_origin=None,
                 dob_evidence=(), countries=(), unknown_countries=(),
                 earliest_report=None, death=None, unread_dobs=()):
        self.hit_id = hit_id
        self.kind = kind
        self.name = name
        self.names = [name] + [a for a in aliases if a]
        self.dobs = list(dobs)
        self.unread_dobs = list(unread_dobs)      # listed dates that could not be read, as written
        self.dob_origin = dob_origin              # 'listed', 'notes' or 'search'
        self.dob_evidence = list(dob_evidence)    # search result IDs, when from search
        self.countries = set(countries)
        self.unknown_countries = list(unknown_countries)
        self.earliest_report = earliest_report
        self.death = death


class Outcome(object):
    def __init__(self, decision, codes, sentences, evidence, record_id=None):
        self.decision = decision
        self.codes = list(codes)                  # every code that applies, main one first
        self.sentences = list(sentences)          # one sentence per decisive fact
        self.evidence = sorted(set(e for e in evidence if e))
        self.record_id = record_id

    @property
    def code(self):
        return self.codes[0]

    @property
    def reason(self):
        return " ".join(self.sentences)


def _cite(source):
    return " (%s)" % source if source else ""


def _country_names(codes):
    return ", ".join(sorted(C.name_of(c) for c in codes))


def _hit_dates_text(hit):
    shown = [D.show(d) for d in hit.dobs]
    if hit.dob_origin == "listed" or len(shown) != 2:
        return ", ".join(shown)
    return " or ".join(sorted(shown))


def _hit_dob_claim(hit, company):
    dates = _hit_dates_text(hit)
    full = any(d.month for d in hit.dobs)
    if hit.dob_origin == "notes":
        return "profile notes %s %s" % ("give its date of birth as" if full else "put its birth year at", dates)
    if hit.dob_origin == "search":
        return "search results %s %s" % ("give its date of birth as" if full else "put its birth year at", dates)
    if len(hit.dobs) > 1:
        return "listed %s are %s" % ("incorporation dates" if company else "dates of birth", dates)
    return "listed %s is %s" % ("incorporation date" if company else "date of birth", dates)


def name_state(customer, hit, rules):
    """('agree' | 'mismatch' | 'unknown', source id). Only a verified legal name can
    give 'mismatch'; a person with fewer than two real name parts gives 'unknown'."""
    company = customer.kind == COMPANY
    hit_parts = [p for p in (rules.parts(n, company) for n in hit.names) if p]
    if not hit_parts:
        return "unknown", None
    need = 1 if company else 2
    if customer.verified_name:
        parts = rules.parts(customer.verified_name, company)
        if len(parts) >= need:
            if any(rules.agree(parts, hp) for hp in hit_parts):
                return "agree", customer.verified_source
            if customer.name_can_clear:
                return "mismatch", customer.verified_source
    for name, source in customer.names:
        parts = rules.parts(name, company)
        if len(parts) >= need and any(rules.agree(parts, hp) for hp in hit_parts):
            return "agree", source
    return "unknown", None


def short_name_agrees(customer, hit, rules):
    """True for a person whose names all have fewer than two real parts when one of them
    still agrees with a name of the hit: every part of the shorter name matches. Such a
    customer can be neither confirmed nor cleared on name, but the names do agree, and
    that matters to the one rule that asks whether name and date of birth agree."""
    if customer.kind == COMPANY:
        return False
    held = [customer.verified_name] + [name for name, _ in customer.names]
    mine = [p for p in (rules.parts(n, False) for n in held if n) if p]
    theirs = [p for p in (rules.parts(n, False) for n in hit.names) if p]
    if not mine or not theirs or any(len(p) >= 2 for p in mine):
        return False
    return any(rules.agree(p, hp) for p in mine for hp in theirs)


def mentioned_ties(customer, hit):
    """The hit's countries that a note about the customer mentions without tying the
    customer to them: a nationality word, or a note set aside as a failed check."""
    return sorted(set(getattr(customer, "possible_countries", None) or {}) & hit.countries)


def location_state(customer, hit):
    """'agree' when they share a country, 'mismatch' when every country differs and
    none is unreadable, otherwise 'unknown'."""
    shared = set(customer.countries) & hit.countries
    if shared:
        return "agree", shared
    if not customer.countries or not hit.countries:
        return "unknown", shared
    if customer.unknown_countries or hit.unknown_countries:
        return "unknown", shared
    return "mismatch", shared


def unread_dobs(hit):
    """The dates the hit lists that could not be read, as written."""
    return list(getattr(hit, "unread_dobs", None) or [])


def dob_state(customer, hit):
    """'agree' when one of the hit's dates agrees, 'mismatch' when every one is
    contradicted, otherwise 'unknown'. A contradiction counts only when the customer's
    date may clear and every date the hit lists was read: an unread one may be the date
    that agrees."""
    dob = D.compare(customer.dob, hit.dobs)
    if dob == "mismatch" and (not customer.dob_can_clear or unread_dobs(hit)):
        return "unknown"
    return dob


def dates_may_agree(customer, hit):
    """True when the two dates of birth cannot be said to differ because one of them could
    not be read: the hit lists a date that could not be read, or a check gives the
    customer a date that could not be read with confidence, so the date held here may
    not be the one the bank verified."""
    if unread_dobs(hit) and customer.dob:
        return True
    return bool((hit.dobs or unread_dobs(hit)) and getattr(customer, "dob_in_doubt", False))


def _location(customer, hit, name, dob, rules):
    """location_state, with two more cautions. A country difference that would clear the
    hit is 'unknown' when a note about the customer mentions one of the hit's countries,
    and when the name agrees and the dates of birth may agree: a country difference does
    not clear a hit whose name and date of birth agree. A name with fewer than two real
    parts counts as agreeing here when what there is of it matches. Nothing else changes:
    where name and date of birth agree, a country difference never cleared, so there is
    nothing to block and the difference stands."""
    location, shared = location_state(customer, hit)
    if location == "mismatch" and not (name == "agree" and dob == "agree"):
        if mentioned_ties(customer, hit):
            return "unknown", shared
        if dates_may_agree(customer, hit) and (
                name == "agree" or (name == "unknown" and short_name_agrees(customer, hit, rules))):
            return "unknown", shared
    return location, shared


def states(customer, hit, rules):
    """The three comparisons behind every decision, exactly as decide() makes them:
    name, dob and location are each 'agree', 'mismatch' or 'unknown'."""
    name, name_source = name_state(customer, hit, rules)
    dob = dob_state(customer, hit)
    location, shared = _location(customer, hit, name, dob, rules)
    return {"name": name, "name_source": name_source, "dob": dob, "location": location, "shared": sorted(shared)}


def decide(customer, hit, rules):
    """Decide one hit against one resolved customer."""
    company = customer.kind == COMPANY
    record_id = customer.primary

    if customer.kind and hit.kind and customer.kind != hit.kind:
        sentence = "The customer is a %s but the hit is a %s." % (customer.kind, hit.kind)
        return Outcome(DIFFERENT, ["ENTITY_TYPE_MISMATCH"], [sentence], customer.record_ids, record_id)

    grounds = {}  # code -> (sentence, evidence)

    if hit.death and customer.screened_at and D.surely_before(hit.death, customer.screened_at):
        grounds["DECEASED"] = (
            "The hit's profile gives a date of death of %s, before the customer was screened on %s."
            % (D.show(hit.death), D.show(customer.screened_at)), ["%s#deceased_date" % hit.hit_id])

    if hit.earliest_report and customer.dob and customer.dob_can_clear:
        report = D.show(hit.earliest_report)
        if company:
            if D.surely_before(hit.earliest_report, customer.dob):
                grounds["TEMPORAL_IMPOSSIBILITY"] = (
                    "The customer was incorporated on %s%s, after the hit's profile reports activity on %s."
                    % (D.show(customer.dob), _cite(customer.dob_source), report), [customer.dob_source])
        else:
            # the oldest they can have been, from the birth year alone: never an
            # overstatement of how young they were
            age = hit.earliest_report.year - customer.dob.year
            if age < 0:
                grounds["TEMPORAL_IMPOSSIBILITY"] = (
                    "The customer was born in %d%s, after the hit's profile reports activity on %s."
                    % (customer.dob.year, _cite(customer.dob_source), report), [customer.dob_source])
            elif age < MIN_AGE:
                grounds["TEMPORAL_IMPOSSIBILITY"] = (
                    "The customer was born in %d%s, so they were at most %d when the hit's profile reports activity on %s."
                    % (customer.dob.year, _cite(customer.dob_source), age, report), [customer.dob_source])

    dob = dob_state(customer, hit)
    if dob == "mismatch":
        subject = "The customer was incorporated on %s" if company else "The customer's date of birth is %s"
        grounds["DOB_MISMATCH"] = (
            (subject + "%s but the hit's %s.") % (D.show(customer.dob), _cite(customer.dob_source), _hit_dob_claim(hit, company)),
            [customer.dob_source] + hit.dob_evidence)

    name, name_source = name_state(customer, hit, rules)
    if name == "mismatch":
        grounds["NAME_MISMATCH_VERIFIED"] = (
            "The customer's verified name is %s%s, which does not match the hit's name %s."
            % (customer.verified_name, _cite(name_source), hit.name.rstrip(".")), [name_source])

    location, shared = _location(customer, hit, name, dob, rules)
    # a note mentions one of the hit's countries, and that alone is why the difference does not clear
    mentioned = mentioned_ties(customer, hit) if location != location_state(customer, hit)[0] else []
    name_and_dob_agree = name == "agree" and dob == "agree"
    # A name with fewer than two real parts cannot confirm or clear, but it can agree. With
    # the date of birth agreeing too, a country difference does not clear the hit.
    short_agree = name == "unknown" and dob == "agree" and short_name_agrees(customer, hit, rules)
    if location == "mismatch" and not name_and_dob_agree and not short_agree:
        sources = [s for ids in customer.countries.values() for s in ids]
        grounds["LOCATION_MISMATCH"] = (
            "The customer is linked only to %s but the hit is linked only to %s."
            % (_country_names(customer.countries), _country_names(hit.countries)), sources)

    if grounds:
        codes = [c for c in CLEARING_ORDER if c in grounds]
        evidence = [e for c in codes for e in grounds[c][1]]
        return Outcome(DIFFERENT, codes, [grounds[c][0] for c in codes], evidence, record_id)

    # No contradiction: confirm on agreement, otherwise review.
    sentences, evidence = [], []
    if dob == "agree":
        subject = "The customer's incorporation date %s%s" if company else "The customer's date of birth %s%s"
        sentences.append((subject + " agrees with the hit's %s.")
                         % (D.show(customer.dob), _cite(customer.dob_source), _hit_dates_text(hit)))
        evidence += [customer.dob_source] + hit.dob_evidence
    if location == "agree":
        sentences.append("Both the customer and the hit are linked to %s." % _country_names(shared))
        evidence += [s for code in shared for s in customer.countries[code]]
    if name == "agree":  # agreement on name is stated, not cited: it rests on no single record
        sentences.append("The customer's name agrees with the hit's name %s." % hit.name.rstrip("."))
    elif short_agree and location == "mismatch":
        sentences.append("The customer's name has fewer than two real parts, so it can neither confirm nor clear "
                         "the hit, but what there is of it agrees with the hit's name %s." % hit.name.rstrip("."))

    if customer.confirmable:
        if company and name == "agree" and location == "agree":
            return Outcome(SAME, ["NAME_LOCATION_MATCH"], sentences, evidence, record_id)
        if not company and name_and_dob_agree and location != "mismatch":
            codes = ["NAME_DOB_MATCH"]
            if location == "agree":
                codes.append("NAME_DOB_LOCATION_MATCH")
            return Outcome(SAME, codes, sentences, evidence, record_id)

    if not customer.confirmable:
        sentences = sentences[:2] + [
            "The screened details are unverified and belong to no known record, so they can "
            "neither clear nor confirm the hit and a person has to review it."]
    elif location == "mismatch":  # name and date of birth agree, the countries do not
        sentences.append(
            "Every country tied to the customer (%s) differs from every country tied to the hit (%s), "
            "and a country difference does not clear a hit whose name and date of birth agree, "
            "so a person has to review it."
            % (_country_names(customer.countries), _country_names(hit.countries)))
        evidence += [s for ids in customer.countries.values() for s in ids]
    else:
        if mentioned:
            notes = sorted(set(s for code in mentioned for s in customer.possible_countries[code]))
            sentences.append("A note about the customer (%s) mentions %s, a country tied to the hit, "
                             "so the countries cannot be said to differ." % (", ".join(notes), _country_names(mentioned)))
            evidence += notes
        unread = unread_dobs(hit)
        a_date = "an incorporation date" if company else "a date of birth"
        if unread and customer.dob and dob != "agree":
            sentences.append("The hit lists %s that could not be read (%s), so its dates cannot be said to "
                             "contradict the customer's." % (a_date, ", ".join(unread)))
        elif (hit.dobs or unread) and dob != "agree" and getattr(customer, "dob_in_doubt", False):
            sentences.append("A check on file gives the customer %s that could not be read with confidence, "
                             "so it cannot be said to differ from the hit's." % a_date)
        missing = []
        if name != "agree":
            missing.append("the name cannot be matched to the hit")
        if company:
            if location != "agree":
                missing.append("no country ties the customer to the hit")
        elif dob != "agree":
            missing.append("the date of birth cannot be compared with it")
        sentences.append(
            "Nothing in the customer's records contradicts the hit, and %s, "
            "so the hit can be neither cleared nor confirmed." % " and ".join(missing))
    if not evidence:
        evidence = list(customer.record_ids)
    return Outcome(REVIEW, ["INSUFFICIENT_DATA"], sentences, evidence, record_id)


def combine(outcomes):
    """Several people fit the alert: one decision if they all lead to it, otherwise
    REVIEW with AMBIGUOUS_CUSTOMER_RECORD. Either way the customer is AMBIGUOUS."""
    if len(outcomes) == 1:
        return outcomes[0]
    evidence = [e for o in outcomes for e in o.evidence]
    if len(set(o.decision for o in outcomes)) == 1:
        first = outcomes[0]
        shared_codes = [c for c in first.codes if all(c in o.codes for o in outcomes)]
        sentences = ["Each of them leads to the same decision."] + first.sentences[:2]
        return Outcome(first.decision, shared_codes or first.codes, sentences, evidence, AMBIGUOUS)
    sentence = "They lead to different decisions (%s), so a person has to review it." % ", ".join(
        sorted(set(o.decision for o in outcomes)))
    return Outcome(REVIEW, ["AMBIGUOUS_CUSTOMER_RECORD"], [sentence], evidence, AMBIGUOUS)
