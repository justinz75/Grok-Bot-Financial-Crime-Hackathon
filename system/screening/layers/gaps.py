"""Deterministic, advisory follow-up for gaps in the scored identity workflow."""

import hashlib
import json
from datetime import date

from .. import dates as D
from ..decide import DIFFERENT, REVIEW, SAME
from ..resolve import is_approved
from ..store import text

TABLE_VERSION = 1
NA = "not_applicable"
ASSESSMENT = ("complete", "unresolved", NA)
QUALITY = ("adequate", "unresolved")
# Each field has a register reference and a closed set of operational values.
FIELDS = {
    "product_custody": ("R13", ("onboarding", "payment", "other")),
    "legal_scope": ("R13", ("assessed", NA)),
    "availability": ("R15", ("imminent", "scheduled", "already_available", NA)),
    "effective_gate": ("R15", (True, False, NA)),
    "recall_available": ("R15", (True, False, NA)),
    "relationship": ("R13", ("direct", "intermediary", "other")),
    "chain_assessment": ("R13", ASSESSMENT),
    "ownership_assessment": ("R12", ASSESSMENT),
    "list_quality": ("R14", QUALITY),
    "identity_quality": ("R14", QUALITY),
    "reviewer_available": ("R15", (True, False)),
    "premise_concern": ("R15", ("none", "R01", "R02", "R03", "R04", "R10", "R11", "R16")),
}

# The row key is the precedence. Keep reasons and actions next to the rule IDs.
ROWS = {
    "T00": ("UNKNOWN_CASE", "The available input has no safe interpretation.",
            "An unhandled case could be overlooked.",
            "Assign a specialist and correct or classify the input."),
    "T01": ("COMPLIANCE_ESCALATION", "The scored match establishes identity for this alert.",
            "Treating identity as authorisation could lead to an incorrect business action.",
            "Ask compliance to assess the listing and applicable obligations."),
    "T02": ("URGENT_SPECIALIST", "Delay may lose effective control given imminent external availability and no verified protection.",
            "Incorrect timing or control assumptions could miss an intervention opportunity or cause unnecessary escalation.",
            "Alert authorised operations and compliance now to assess control options."),
    "T03": ("CONTEXT_REQUIRED", "Unavailable or unverified context cannot support a low-exposure assumption.",
            "Assuming low exposure could select the wrong workflow.",
            "Obtain the missing evidence and assign an accountable reviewer."),
    "T04": ("SPECIALIST_ASSESSMENT", "The identity result does not resolve the documented wider exposure.",
            "An indirect party or unreliable screening control could be overlooked.",
            "Ask the appropriate specialist to resolve the documented assessment or evidence-quality concern."),
    "T05": ("IDENTITY_REVIEW", "The scored evidence leaves the identity unresolved.",
            "Resolving identity without further evidence could miss a true match.",
            "Ask an analyst to resolve the missing or conflicting identity evidence."),
    "T06": ("SECOND_READER", "A documented concern challenges evidence used in this clearance.",
            "Dismissing the concern could create false reassurance.",
            "Ask an authorised independent reviewer to resolve the cited concern."),
    "T07": ("IDENTITY_CLOSED", "The scored clearance and documented assessments support closing this identity case.",
            "An inaccurate completion assertion could conceal unresolved controls.",
            "Record identity closure and any residual caveats."),
    "T08": ("UNKNOWN_CASE", "The decision table does not cover this combination.",
            "Default closure could conceal an unresolved exposure.",
            "Request specialist classification and record why the table did not apply."),
}


def _date(value):
    try:
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except (TypeError, ValueError):
        return None


def _label(value):
    return isinstance(value, str) and bool(value.strip())


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate key")
        obj[key] = value
    return obj


def load_context(path):
    """Load a private snapshot once. Invalid input is reported only in the explain file."""
    if not path:
        return None, None
    try:
        with open(path, encoding="utf-8") as handle:
            context = json.load(handle, object_pairs_hook=_unique_keys)
        if (not isinstance(context, dict) or set(context) - {
                "profile_id", "version", "as_of", "institution_type", "cases"}
                or not _label(context.get("profile_id")) or not _label(context.get("version"))
                or not _date(context.get("as_of")) or not isinstance(context.get("cases"), dict)
                or ("institution_type" in context and not _label(context["institution_type"]))):
            return None, "invalid context snapshot"
        canonical = json.dumps(context, sort_keys=True, separators=(",", ":")).encode("utf-8")
        context["sha256"] = hashlib.sha256(canonical).hexdigest()
        return context, None
    except (OSError, ValueError, RecursionError):
        return None, "unreadable or invalid context snapshot"


def observation(field, value, source, status="observed"):
    return {"field": field, "value": value, "status": status, "source_ref": source}


def _read_field(field, item, allowed, as_of, supplied):
    path = "context." + field
    if not supplied:
        return observation(path, None, None, "missing")
    if not isinstance(item, dict):
        return observation(path, None, None, "invalid")
    source = item.get("source_ref")
    source = source if _label(source) else None
    value = item.get("value")
    status = item.get("status")
    if status in ("declared", "conflicting", "unknown"):
        return observation(path, None, source, status)
    start, end = _date(item.get("valid_from")), _date(item.get("valid_until"))
    if (status != "verified" or not source or not start or not end or end < start
            or not any(type(value) is type(option) and value == option for option in allowed)
            or (value == NA and not _label(item.get("reason")))):
        return observation(path, None, source, "invalid")
    if not start <= as_of <= end:
        return observation(path, None, source, "out_of_period")
    result = observation(path, value, source, "verified")
    if value == NA:
        result["reason"] = item["reason"]
    return result


def _case_context(context, hit_id):
    case = context["cases"].get(hit_id, {}) if context else {}
    if not isinstance(case, dict):
        return {}, ["context.cases entry"]
    as_of = _date(context["as_of"]) if context else None
    observations = {name: _read_field(name, case.get(name), allowed, as_of, name in case)
                    for name, (_, allowed) in sorted(FIELDS.items())}
    invalid = ["context." + name for name in sorted(set(case) - FIELDS.keys())]
    invalid.extend(item["field"] for item in observations.values() if item["status"] == "invalid")
    return observations, invalid


# Evidence markers are observations. Only a separately attested unresolved concern can
# challenge a clearance. For instance, the presence of a death date alone proves no defect.
EVIDENCE = {
    "R01": ("A reproducible tie break does not establish which check is superior.",
            "An incorrect identity fact may be selected.", "Reconcile the tied approved checks."),
    "R02": ("The exercise uses supplied evidence without an explicit as-of cutoff.",
            "A replay could use a fact unavailable at screening.", "Verify the applicable evidence cutoff."),
    "R03": ("Linked declarations can differ even when a verified fact resolves the difference.",
            "An incorrect fallback date could be used.", "Reconcile the customer declarations."),
    "R04": ("An unreadable date is unresolved evidence.",
            "An alternative date could be missed.", "Check the original listing date field."),
    "R05": ("Unrecognised country data leaves some location evidence unresolved.",
            "A shared country could be missed.", "Resolve the unrecognised place."),
    "R06": ("Record lookup failure leaves the customer selection unresolved.",
            "The wrong customer could be screened.", "Recover the customer record."),
    "R07": ("The identity outcome can coexist with unresolved customer selection.",
            "A downstream control could attach to the wrong customer.", "Resolve which customer the alert concerns."),
    "R08": ("The recovered date is attributed to the listed subject.",
            "The date may describe someone else.", "Verify the recovered date against its source."),
    "R09": ("A missing date is unresolved evidence.",
            "A true match could remain undetected.", "Seek a usable date or other admissible evidence."),
    "R10": ("The death metadata is assumed to describe the listed subject.",
            "Incorrect attribution could cause false reassurance.", "Verify death attribution if challenged."),
    "R11": ("The earliest report is assumed to describe relevant activity by the listed subject.",
            "An incorrect attribution could undermine the temporal comparison.", "Verify report attribution if challenged."),
    "R16": ("Additional identifiers require independent authentication.",
            "An unreliable identifier could mislead the reviewer.", "Check provenance before relying on extra identifiers."),
}


def candidate_evidence(store, row, customer, hit, count, alert_id):
    """Collect source-linked indicators from this candidate's supplied records."""
    candidate = customer.primary
    found = []

    def add(gap, field, value, refs):
        assumption, cost, action = EVIDENCE[gap]
        sources = sorted({ref for ref in refs if ref})
        found.append({
            "gap": gap, "candidate_ref": candidate, "assumption": assumption,
            "wrong_assumption_cost": cost, "next_action": action,
            "observations": [observation(field, value, ref, "missing" if value is None else "observed")
                             for ref in sources or [None]],
        })

    dated = []
    declared = {}
    for rid in customer.record_ids:
        dob = D.parse_date(store.customer[rid].get("dob"))
        if dob:
            declared[rid] = D.show(dob)
        for check in store.checks(rid):
            checked_at = D.parse_date(check.get("checked_at"))
            if checked_at and is_approved(check):
                dated.append((checked_at, check))
    if dated:
        def order(item):
            checked_at = item[0]
            return checked_at.year, checked_at.month or 0, checked_at.day or 0

        latest = max(map(order, dated))
        peers = [item[1] for item in dated if order(item) == latest]
        facts = {tuple(text(check.get(field)) for field in
                       ("verified_name", "verified_dob", "document_country")) for check in peers}
        if len(facts) > 1:
            add("R01", "approved_checks.tied_fact_sets", len(facts), [text(c.get("check_id")) for c in peers])
        future = [text(c.get("check_id")) for day, c in dated
                  if customer.screened_at and D.surely_before(customer.screened_at, day)]
        if future:
            add("R02", "approved_checks.after_screening", True, future)
    if len(set(declared.values())) > 1:
        add("R03", "customer.distinct_declared_dates", len(set(declared.values())), declared)
    ref = hit.hit_id
    if D.unread_dates(row.get("dobs")):
        add("R04", "hit.dobs.unreadable", True, [ref])
    if hit.unknown_countries or customer.unknown_countries:
        refs = ([ref] if hit.unknown_countries else []) + (
            customer.record_ids if customer.unknown_countries else [])
        add("R05", "location.unrecognised", True, refs)
    if not count:
        add("R06", "alert.customer_record", None, [alert_id])
    if count > 1:
        add("R07", "alert.candidate_count", count, [alert_id])
    if hit.dob_origin in ("notes", "search"):
        add("R08", "hit.dob_origin", hit.dob_origin, hit.dob_evidence or [ref])
    if not hit.dobs:
        add("R09", "hit.usable_dob", None, [ref])
    if hit.death:
        add("R10", "hit.death", D.show(hit.death), [ref])
    if hit.earliest_report:
        add("R11", "hit.earliest_report", D.show(hit.earliest_report), [ref])
    if row.get("identifiers"):
        add("R16", "hit.identifiers.present", True, [ref])
    return found


def _match(row, gaps, facts, action=None):
    disposition, assumption, cost, default_action = ROWS[row]
    # Different candidate records can refer to the same hit-level observation.
    unique = {json.dumps(fact, sort_keys=True): fact for fact in facts}
    return {
        "row": row, "gaps": sorted(set(gaps)),
        "observations": [unique[key] for key in sorted(unique)],
        "assumption": assumption, "wrong_assumption_cost": cost,
        "authority": "organiser_policy" if row == "T05" else "operating_choice",
        "next_action": action or default_action, "disposition": disposition,
    }


def unavailable(problem):
    """Build a fail-safe explanation without evaluating the decision table."""
    match = _match("T00", ["R15"], [observation("annotation", problem, None, "invalid")])
    return {"table_version": TABLE_VERSION, "context": None, "disposition": match["disposition"],
            "next_action": match["next_action"], "missing_fields": [], "complete": False,
            "matches": [match]}


def annotate(identity, evidence, context, problem=None):
    """Evaluate all matching rows in precedence order against a finalized scored hit."""
    matches = []
    observations, invalid = _case_context(context, identity["hit_id"])
    decision = identity["decision"]
    scored = observation("scored.decision", decision, identity["hit_id"])
    observed_gaps = sorted({item["gap"] for item in evidence})
    concern = observations.get("premise_concern", {}).get("value")
    premise = concern in FIELDS["premise_concern"][1][1:]
    unresolved = [name for name, item in observations.items() if item["status"] != "verified"]

    def match(row, gaps, facts, action=None):
        matches.append(_match(row, gaps, facts, action))

    def value(field):
        return observations.get(field, {}).get("value")

    unknown_gaps = sorted(set(observed_gaps) - EVIDENCE.keys())
    if problem or invalid or unknown_gaps:
        invalid_facts = [item for item in observations.values() if item["field"] in invalid]
        unrepresented = set(invalid) - {item["field"] for item in invalid_facts}
        invalid_facts.extend(observation(field, None, None, "invalid") for field in sorted(unrepresented))
        invalid_facts.extend(observation("gap", gap, None, "unclassified") for gap in unknown_gaps)
        if problem:
            invalid_facts.append(observation("annotation", problem, None, "invalid"))
        match("T00", ["R15"], invalid_facts)
    if decision == SAME:
        match("T01", ["R13", "R15"], [scored])
    if ((decision in (SAME, REVIEW) or (decision == DIFFERENT and premise))
            and value("availability") == "imminent"
            and value("effective_gate") is not True and value("recall_available") is not True):
        timing = [observations[field] for field in ("availability", "effective_gate", "recall_available")]
        match("T02", ["R15"] + ([concern] if decision == DIFFERENT else []),
              [scored, *timing] + ([observations["premise_concern"]] if decision == DIFFERENT else []))
    if unresolved:
        match("T03", [FIELDS[field][0] for field in unresolved], [observations[field] for field in unresolved])
    specialist = [field for field in ("chain_assessment", "ownership_assessment", "list_quality", "identity_quality")
                  if value(field) == "unresolved"]
    if specialist:
        match("T04", [FIELDS[field][0] for field in specialist], [observations[field] for field in specialist])
    if decision == REVIEW:
        review_gaps = [gap for gap in observed_gaps if gap in EVIDENCE and gap not in ("R10", "R11")]
        facts = [fact for item in evidence if item["gap"] in review_gaps for fact in item["observations"]]
        action = None
        if value("effective_gate") is True:
            facts.append(observations["effective_gate"])
            action = "Ask an analyst to resolve identity and authorised operations to assess the existing gate."
        match("T05", review_gaps or ["R15"], [scored, *facts], action)
    if decision == DIFFERENT and premise:
        action = None if value("reviewer_available") is True else (
            "Refer to a designated authorised alternate and leave the concern unresolved.")
        facts = [fact for item in evidence if item["gap"] == concern for fact in item["observations"]]
        match("T06", [concern], [scored, observations["premise_concern"],
                                 observations["reviewer_available"], *facts], action)
    if not matches:
        if decision == DIFFERENT and observations and not {"R06", "R07"} & set(observed_gaps):
            match("T07", ["R13"], [scored, *observations.values()])
        else:
            selection = [item for item in evidence if item["gap"] in ("R06", "R07")]
            match("T08", ["R15", *(item["gap"] for item in selection)],
                  [scored, *(fact for item in selection for fact in item["observations"])])
    return {
        "table_version": TABLE_VERSION,
        "context": ({key: context[key] for key in ("profile_id", "version", "as_of", "sha256")}
                    if context else None),
        "disposition": matches[0]["disposition"],
        "next_action": matches[0]["next_action"],
        "missing_fields": ["context." + field for field in unresolved],
        "complete": not (unresolved or matches[0]["row"] in ("T00", "T08")),
        "matches": matches,
    }
