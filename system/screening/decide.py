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
                 confirmable=True, name_can_clear=True, possible_countries=None,
                 precautionary_countries=None):
        self.kind = kind
        self.dob_can_clear = dob_can_clear        # False when an identity check could not be read
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
        self.precautionary_countries = dict(precautionary_countries or {})  # code -> source IDs
        self.screened_at = screened_at


class Hit(object):
    """One watchlist profile, with its facts gathered from wherever they are."""

    def __init__(self, hit_id, kind, name, aliases=(), dobs=(), dob_origin=None,
                 dob_evidence=(), countries=(), unknown_countries=(),
                 earliest_report=None, death=None, clearance_dobs=None, clearance_dob_evidence=()):
        self.hit_id = hit_id
        self.kind = kind
        self.name = name
        self.names = [name] + [a for a in aliases if a]
        self.dobs = list(dobs)
        self.dob_origin = dob_origin              # 'listed', 'notes' or 'search'
        self.dob_evidence = list(dob_evidence)
        # Dates available before the recovery expansion define the clearance baseline.
        self.clearance_dobs = self.dobs if clearance_dobs is None else list(clearance_dobs)
        self.clearance_dob_evidence = [source for source in clearance_dob_evidence if source]
        self.countries = set(countries)
        self.unknown_countries = list(unknown_countries)
        self.earliest_report = earliest_report
        self.death = death


class Outcome(object):
    def __init__(self, decision, codes, sentences, evidence, record_id=None, grounds=None, candidate_fact=None):
        self.decision = decision
        self.codes = list(codes)                  # every code that applies, main one first
        self.sentences = list(sentences)          # one sentence per decisive fact
        self.evidence = sorted(set(e for e in evidence if e))
        self.record_id = record_id
        self._grounds = grounds
        self.candidate_fact = candidate_fact

    @property
    def code(self):
        return self.codes[0]

    @property
    def reason(self):
        return " ".join(self.sentences)

    def scored_facts(self, code=None):
        """Return the text and citations together, reserving one sentence for resolution.

        A candidate in a unanimous clearance needs just one contradiction. The
        full set of facts remains available to the optional layers.
        """
        if not self._grounds:
            return self.sentences[:3], self.evidence
        selected = [code] if code else self.codes[:3]
        facts = [self._grounds[c] for c in selected]
        evidence = sorted({source for _, sources in facts for source in sources if source})
        return [sentence for sentence, _ in facts], evidence


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
    if (customer.unknown_countries or hit.unknown_countries
            or hit.countries.intersection(customer.precautionary_countries)):
        return "unknown", shared
    return "mismatch", shared


def _dob_state(customer, hit):
    dob = D.compare(customer.dob, hit.dobs)
    clearance_dob = D.compare(customer.dob, hit.clearance_dobs)
    if dob == "mismatch" and (not customer.dob_can_clear or clearance_dob != "mismatch"):
        dob = "unknown"
    return dob, clearance_dob


def _location(customer, hit, name, dob):
    """location_state, with one more caution. A country difference that would clear the
    hit is 'unknown' when a note about the customer mentions one of the hit's countries.
    Nothing else changes: where name and date of birth agree, a country difference never
    cleared, so a mention has nothing to block and the difference stands."""
    location, shared = location_state(customer, hit)
    if location == "mismatch" and not (name == "agree" and dob == "agree") and mentioned_ties(customer, hit):
        return "unknown", shared
    return location, shared


def states(customer, hit, rules):
    """The three comparisons behind every decision, exactly as decide() makes them:
    name, dob and location are each 'agree', 'mismatch' or 'unknown'."""
    name, name_source = name_state(customer, hit, rules)
    dob, _ = _dob_state(customer, hit)
    location, shared = _location(customer, hit, name, dob)
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

    dob, clearance_dob = _dob_state(customer, hit)
    if dob == "mismatch":
        subject = "The customer was incorporated on %s" if company else "The customer's date of birth is %s"
        claim = (subject + "%s but the hit's %s") % (
            D.show(customer.dob), _cite(customer.dob_source), _hit_dob_claim(hit, company))
        baseline_sources = sorted(set(hit.clearance_dob_evidence) - set(hit.dob_evidence))
        if baseline_sources:
            dates = ", ".join(D.show(date) for date in hit.clearance_dobs)
            claim += ", and the original search results (%s) also give a conflicting date (%s)" % (
                ", ".join(baseline_sources), dates)
        grounds["DOB_MISMATCH"] = (claim + ".", [customer.dob_source] + hit.dob_evidence + baseline_sources)

    name, name_source = name_state(customer, hit, rules)
    if name == "mismatch":
        grounds["NAME_MISMATCH_VERIFIED"] = (
            "The customer's verified name is %s%s, which does not match the hit's name %s."
            % (customer.verified_name, _cite(name_source), hit.name.rstrip(".")), [name_source])

    location, shared = _location(customer, hit, name, dob)
    # a note mentions one of the hit's countries, and that alone is why the difference does not clear
    mentioned = mentioned_ties(customer, hit) if location != location_state(customer, hit)[0] else []
    name_and_dob_agree = name == "agree" and dob == "agree"
    # Weak geographic evidence can block a clearance without establishing
    # agreement when all countries established by the policy differ.
    precautions = hit.countries.intersection(customer.precautionary_countries)
    disjoint_with_precaution = (
        location == "unknown" and precautions
        and not customer.unknown_countries and not hit.unknown_countries
        and customer.countries
    )
    # A one-part name can stop a location clearance when either DOB comparison agrees.
    short_name_match = (name == "unknown" and "agree" in (dob, clearance_dob)
                        and short_name_agrees(customer, hit, rules))
    short_agree = short_name_match and dob == "agree"
    baseline_agreement = (name == "agree" or short_name_match) and clearance_dob == "agree"
    if location == "mismatch" and not (name_and_dob_agree or short_agree or baseline_agreement):
        sources = [s for ids in customer.countries.values() for s in ids]
        grounds["LOCATION_MISMATCH"] = (
            "The customer is linked only to %s but the hit is linked only to %s."
            % (_country_names(customer.countries), _country_names(hit.countries)), sources)

    if grounds:
        codes = [c for c in CLEARING_ORDER if c in grounds]
        evidence = [e for c in codes for e in grounds[c][1]]
        return Outcome(DIFFERENT, codes, [grounds[c][0] for c in codes], evidence, record_id, grounds)

    # No contradiction: confirm on agreement, otherwise review.
    sentences, evidence = [], []
    dob_sources = [customer.dob_source] + hit.dob_evidence
    country_sources = [s for code in shared for s in customer.countries[code]]
    if dob == "agree":
        subject = "The customer's incorporation date %s%s" if company else "The customer's date of birth %s%s"
        sentences.append((subject + " agrees with the hit's %s.")
                         % (D.show(customer.dob), _cite(customer.dob_source), _hit_dates_text(hit)))
        evidence += dob_sources
    if location == "agree":
        sentences.append("Both the customer and the hit are linked to %s." % _country_names(shared))
        evidence += country_sources
    if name == "agree":  # agreement on name is stated, not cited: it rests on no single record
        sentences.append("The customer's name agrees with the hit's name %s." % hit.name.rstrip("."))
    elif short_name_match and location == "mismatch":
        sentences.append("The customer's name has fewer than two real parts, so it can neither confirm nor clear "
                         "the hit, but what there is of it agrees with the hit's name %s." % hit.name.rstrip("."))

    if customer.confirmable:
        if company and name == "agree" and location == "agree":
            fact = ("The name matches and both are linked to %s." % _country_names(shared), country_sources)
            return Outcome(SAME, ["NAME_LOCATION_MATCH"], sentences, evidence, record_id, candidate_fact=fact)
        if not company and name_and_dob_agree and location != "mismatch" and not disjoint_with_precaution:
            codes = ["NAME_DOB_MATCH"]
            if location == "agree":
                codes.append("NAME_DOB_LOCATION_MATCH")
            fact = ("The name matches and birth dates agree (%s and %s)%s."
                    % (D.show(customer.dob), _hit_dates_text(hit), _cite(customer.dob_source)), dob_sources)
            return Outcome(SAME, codes, sentences, evidence, record_id, candidate_fact=fact)

    review_fact, review_sources = None, []
    country_ties = [s for ids in customer.countries.values() for s in ids]
    if not customer.confirmable:
        sentences = sentences[:2] + [
            "The screened details are unverified and belong to no known record, so they can "
            "neither clear nor confirm the hit and a person has to review it."]
    elif disjoint_with_precaution:
        notes = sorted({s for code in precautions for s in customer.precautionary_countries[code] if s})
        sources = " (%s)" % ", ".join(notes) if notes else ""
        sentences.append(
            "The customer's established countries (%s) differ from the hit's (%s), but an earlier approved "
            "check or travel note%s mentions %s for the customer, so a person has to review the hit."
            % (_country_names(customer.countries), _country_names(hit.countries), sources, _country_names(precautions)))
        review_sources = country_ties + notes
    elif location == "mismatch":
        review_sources = country_ties
        if name_and_dob_agree or short_agree:
            sentences.append(
                "Every country tied to the customer (%s) differs from every country tied to the hit (%s), "
                "and a country difference does not clear a hit whose name and date of birth agree, "
                "so a person has to review it."
                % (_country_names(customer.countries), _country_names(hit.countries)))
        else:
            baseline_dates = ", ".join(D.show(date) for date in hit.clearance_dobs)
            baseline_sources = sorted(set(hit.clearance_dob_evidence) - set(hit.dob_evidence))
            if hit.dobs and baseline_sources:
                sentences.append(
                    "The names agree, but the customer's birth date agrees with the original search results "
                    "(%s, %s) while the hit's %s, so the country difference still requires review."
                    % (", ".join(baseline_sources), baseline_dates, _hit_dob_claim(hit, company)))
            else:
                sentences.append(
                    "The customer's name agrees with the hit, but the birth-date sources give different results "
                    "and their countries differ, so a person has to review it.")
            review_sources = country_ties + dob_sources + hit.clearance_dob_evidence
    else:
        if mentioned:
            notes = sorted(set(s for code in mentioned for s in customer.possible_countries[code]))
            review_fact = ("A note about the customer (%s) mentions %s, a country tied to the hit, "
                           "so the countries cannot be said to differ." % (", ".join(notes), _country_names(mentioned)))
            sentences.append(review_fact)
            review_sources = notes
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
    evidence += review_sources
    if not evidence:
        evidence = list(customer.record_ids)
    return Outcome(REVIEW, ["INSUFFICIENT_DATA"], sentences, evidence, record_id,
                   candidate_fact=(review_fact or sentences[-1], review_sources or customer.record_ids))


def _candidate_facts(outcomes, codes, budget):
    """Select one decision-bearing fact per candidate and group identical facts."""
    by_fact = {}
    evidence = []
    for outcome, code in zip(outcomes, codes):
        if outcome.candidate_fact:
            sentence, sources = outcome.candidate_fact
        else:
            sentences, sources = outcome.scored_facts(code)
            sentence = sentences[0]
        by_fact.setdefault(sentence, []).append(outcome.record_id)
        evidence.extend(sources)

    clauses = []
    for sentence, records in by_fact.items():
        known = [record for record in records if record]
        if known:
            label = "record" if len(known) == 1 else "records"
            scope = "%s %s" % (label, ", ".join(known))
            if len(known) != len(records):
                scope += " and the unverified details"
        else:
            scope = "the unverified details"
        # The reasons start with ordinary determiners. Preserve any proper name or acronym.
        first, _, rest = sentence.rstrip(".").partition(" ")
        if first in {"A", "An", "Both", "Every", "Nothing", "The"}:
            first = first.lower()
        clauses.append("for %s, %s" % (scope, " ".join(filter(None, (first, rest)))))

    # Keep the sentences similar in length when there are more distinct facts than slots.
    sentences = []
    slots = min(len(clauses), budget)
    for slot in range(slots):
        start = slot * len(clauses) // slots
        end = (slot + 1) * len(clauses) // slots
        sentence = ", while ".join(clauses[start:end])
        sentences.append(sentence[0].upper() + sentence[1:] + ".")
    return sentences, evidence


def combine(outcomes):
    """Several people fit the alert: one decision if they all lead to it, otherwise
    REVIEW with AMBIGUOUS_CUSTOMER_RECORD. Either way the customer is AMBIGUOUS."""
    if len(outcomes) == 1:
        return outcomes[0]
    decisions = sorted({o.decision for o in outcomes})
    if len(decisions) == 1:
        first = outcomes[0]
        shared_codes = [c for c in first.codes if all(c in o.codes for o in outcomes)]
        codes = shared_codes or first.codes
        selected = [None] * len(outcomes)
        if first.decision == DIFFERENT:
            selected = [shared_codes[0] if shared_codes else o.code for o in outcomes]
        details, evidence = _candidate_facts(outcomes, selected, budget=3)
        if first.decision == REVIEW:
            evidence = [source for outcome in outcomes for source in outcome.evidence]
        return Outcome(first.decision, codes, details, evidence, AMBIGUOUS)
    summary = "The candidates lead to different decisions (%s), so a person has to review the hit." % ", ".join(decisions)
    details, evidence = _candidate_facts(outcomes, [o.code if o.decision == DIFFERENT else None
                                                    for o in outcomes], budget=2)
    return Outcome(REVIEW, ["AMBIGUOUS_CUSTOMER_RECORD"], [summary] + details, evidence, AMBIGUOUS)
