# The explain file

`system/run` always writes the scored file: one line per hit with the seven required fields.
Given a third argument it also writes an **explain file**, one JSON line per hit in the same order:

```
python system/run DATA output/dev.jsonl output/dev.explain.jsonl
```

The scored file is what gets judged. The explain file is where the extra layers show their
work. A layer that is switched on adds to the explain file; it changes the scored file only
when it is set to `enforce`, and then only by turning a clearance into a review.

## One line

| Field | Type | Meaning |
|---|---|---|
| `hit_id`, `alert_id` | string | Same as the scored file |
| `decision`, `reason_code`, `customer_record_id` | string | The final answer, same as the scored file |
| `rules` | object | `decision` and `reason_code` the rules alone gave |
| `changed_by` | object or null | `{"layer": ..., "why": ...}` when a layer turned a clearance into a review |
| `layers` | object | The mode of each layer for this run, e.g. `{"score": "on", "briefing": "on", "reader": "off", "reviewer": "off"}` |
| `people` | list | One entry per person the alert may be about. Usually one; several when the customer is `AMBIGUOUS` |

## One entry of `people`

| Field | Type | Meaning |
|---|---|---|
| `record_ids` | list of strings | The customer records that are this person. Empty when no record was found |
| `decision`, `reason_code` | string | What the rules decided for this person |
| `all_codes` | list of strings | Every reason code that applies, main one first |
| `customer` | object | `kind` (`person` or `company`), `verified_name`, `verified_source`, `names` (list), `dob`, `dob_source`, `countries` (list of `{code, name, sources}`) |
| `hit` | object | `kind`, `name`, `aliases` (list), `dobs` (list), `dob_origin` (`listed`, `notes`, `search` or null), `countries` (list of `{code, name}`), `earliest_report`, `death` |
| `states` | object | `name`, `dob`, `location`: each `agree`, `mismatch` or `unknown` |
| `score` | object or null | The strength-of-evidence layer, below |
| `briefing` | object or null | The analyst briefing layer, below |
| `review` | object or null | The model reviewer layer, below |

Dates are text: `1965-03-28`, `1965-03` or `1965`. Anything unknown is `null` or an empty list.

### `score`

| Field | Type | Meaning |
|---|---|---|
| `bits` | number | Weight of evidence. Positive means the same person, negative a different one |
| `band` | string | One of: `strong evidence of the same`, `some evidence of the same`, `inconclusive`, `some evidence of a different one`, `strong evidence of a different one` |
| `contributions` | list | `{field, state, bits, detail}` for each of `name`, `date of birth`, `country`, and any of `entity type`, `timing`, `death` that applies |
| `conflict` | true or false | True when the rules cleared the hit but the evidence leans towards the same person |

### `briefing`

| Field | Type | Meaning |
|---|---|---|
| `headline` | string | The outcome in one plain sentence |
| `decided_by` | list of strings | The facts that decided it, each with its values and record IDs |
| `missing` | list of strings | Facts that were not available |
| `would_settle` | list of strings | What one more fact would change. Empty when the hit is decided |
| `strength` | string | How firm the decision is, e.g. `two independent grounds` |
| `caveats` | list of strings | Anything an analyst should know before relying on it |

### `review`

| Field | Type | Meaning |
|---|---|---|
| `verdict` | string | `agree`, `disagree` or `unsure` with the rules' clearance |
| `reason` | string | The model's reason, one sentence |
| `model` | string | The model ID used |
| `runs` | number | How many times it was asked |
| `agreement` | number | Share of runs that gave this verdict, 0 to 1 |

## Example (invented)

```json
{"hit_id": "H-0000A1", "alert_id": "A-0000A1", "decision": "DIFFERENT_ENTITY", "reason_code": "DOB_MISMATCH", "customer_record_id": "CUS-000001", "rules": {"decision": "DIFFERENT_ENTITY", "reason_code": "DOB_MISMATCH"}, "changed_by": null, "layers": {"score": "on", "briefing": "on", "reader": "off", "reviewer": "off"}, "people": [{"record_ids": ["CUS-000001"], "decision": "DIFFERENT_ENTITY", "reason_code": "DOB_MISMATCH", "all_codes": ["DOB_MISMATCH"], "customer": {"kind": "person", "verified_name": "LARS HOLM", "verified_source": "KYC-0000A1", "names": ["Lars Holm"], "dob": "1977-12-13", "dob_source": "KYC-0000A1", "countries": [{"code": "DE", "name": "Germany", "sources": ["CUS-000001", "KYC-0000A1"]}]}, "hit": {"kind": "person", "name": "Holm, Lars", "aliases": [], "dobs": ["1951"], "dob_origin": "listed", "countries": [{"code": "DE", "name": "Germany"}], "earliest_report": null, "death": null}, "states": {"name": "agree", "dob": "mismatch", "location": "agree"}, "score": {"bits": -4.9, "band": "some evidence of a different one", "contributions": [{"field": "name", "state": "agree", "bits": 6.2, "detail": "Both parts match; about 1 customer in 70 shares them"}, {"field": "date of birth", "state": "mismatch", "bits": -12.4, "detail": "1977 against 1951: 26 years apart"}, {"field": "country", "state": "agree", "bits": 1.3, "detail": "Germany, shared by about 2 customers in 5"}], "conflict": false}, "briefing": {"headline": "Different person: born 26 years apart.", "decided_by": ["Verified date of birth 1977-12-13 (KYC-0000A1) against the hit's listed 1951"], "missing": [], "would_settle": [], "strength": "one ground, from a verified identity check", "caveats": ["The name and the country agree; only the date of birth separates them."]}, "review": null}]}
```

## Policy-gap follow-up

The explain file includes a hit-level `gaps` object and a `gaps` list for each candidate in
`people`. The hit object records the table version, the context snapshot ID, version and
SHA-256 (or null), the primary disposition and next action, incomplete context fields, and
all matching rows in precedence order. Each row includes its register IDs, input observations
and source references, the assumption, the consequence if wrong, and the next action.
`complete` means the table had enough context to select a disposition without an unknown
fallback. Analyst completion is tracked outside this file. Candidate indicators retain their
record references even when every candidate yields the same scored identity result.

The built-in viewer sample includes an invented urgent payment for Anna Petrova. Her scored
identity remains `REVIEW`. The viewer displays the primary follow-up and expands its evidence,
assumptions and secondary actions. Older explain files still open.

### Private operating context

Without operating context, missing exposure fields are reported as unknown and the table
retains identity review or compliance escalation where applicable. To provide context, set
`SCREENING_GAP_CONTEXT` to a private JSON file and ask for explain output:

```sh
SCREENING_GAP_CONTEXT=/private/context.json python system/run DATA scored.jsonl run.explain.jsonl
```

Here is a minimal invented snapshot. It can trigger urgency on a `REVIEW` or `SAME_ENTITY`
hit while retaining a secondary action for missing context. The `cases` keys are exact hit IDs.

```json
{
  "profile_id": "example-payments",
  "version": "1",
  "as_of": "2026-11-21",
  "institution_type": "fintech",
  "cases": {
    "H-EXAMPLE": {
      "availability": {
        "status": "verified",
        "value": "imminent",
        "source_ref": "OPS-EXAMPLE",
        "valid_from": "2026-11-21",
        "valid_until": "2026-11-21"
      }
    }
  }
}
```

`institution_type` is optional metadata. The engine validates the structure, reference
presence and date window of source attestations. Operations supplies and verifies the
underlying evidence. Use opaque references with no secrets. The context loader recognises
`declared`, `conflicting` and `unknown` statuses as unresolved. A `not_applicable` value also
requires a sourced `reason`. Invalid input is reported in the explanation.

| Verified field | Values |
|---|---|
| `product_custody` | `onboarding`, `payment`, `other` |
| `legal_scope` | `assessed`, `not_applicable` |
| `availability` | `imminent`, `scheduled`, `already_available`, `not_applicable` |
| `effective_gate`, `recall_available` | boolean or `not_applicable` |
| `relationship` | `direct`, `intermediary`, `other` |
| `chain_assessment`, `ownership_assessment` | `complete`, `unresolved`, `not_applicable` |
| `list_quality`, `identity_quality` | `adequate`, `unresolved` |
| `reviewer_available` | boolean |
| `premise_concern` | `none` or `R01`, `R02`, `R03`, `R04`, `R10`, `R11`, `R16` for a documented unresolved concern |

Follow-up is advisory. Compliance and operations own any action on a payment or listing.
See the [decision table and register](context/policy-gaps.md#deterministic-operational-table).
