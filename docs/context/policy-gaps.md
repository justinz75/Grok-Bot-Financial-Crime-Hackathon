# Policy gaps: reconstructed research register

This is a **new reconstruction**, not the missing register. It is documentation and an
aggregate research tool only. No runtime layer, environment profile, explain field or viewer
behavior is implemented by this work. Justin's explicit go-ahead is still required before
any proposed runtime work.

## Provenance and recovery limits

The source for the lost work's existence is [handoff §3.1](../../tasks/handoff-chatgpt.md).
It describes uncommitted files in a Windows temporary worktree, a register labelled G01–G18,
and a disposition design. That description does not preserve the entries themselves.

Recovery checks in this assigned Linux checkout found no originals:

- `git fetch origin`, `git ls-remote --heads --tags origin` and
  `git ls-remote origin 'refs/pull/*/head'`: no advertised policy-gaps branch/tag or original
  file on the inspected PR heads.
- `git log --all --oneline -- docs/context/policy-gaps.md tools/gap_counts.py`: no history.
- A filename search under `/home/kenar/.t3`, `/home/kenar/Documents` and `/tmp`: neither file
  existed before reconstruction. No other checkout was changed.

These checks do not recover uncommitted Windows files or rule out inaccessible backups,
deleted remote objects or another machine. G01–G18 mappings, original predicates, original
sources and original counts remain **unknown**. In particular, the handoff's G16 / one-hit
claim is unverified and must not be attached to any entry here. Reconstruction IDs use **R**;
there is no crosswalk to G IDs.

The baseline inspected was `94b96fc` (also `origin/main` when fetched). Concurrent branches
may subsequently change it; refresh counts after an owner-approved runtime merge. Unrelated
draft PR #4 was left alone.

## Sources and authority

- **P:** private `ROOM/POLICY.md`, read directly for this reconstruction, principles 1–9.
  The [public digest](policy.md) gives navigation; the private procedure remains the scoring
  authority. Descriptions below are original paraphrases, with no participant records.
- **C:** current source in `system/screening/`, linked at each entry. Implementation choices
  are evidence of behavior, not additional policy authority.
- **H:** [handoff §3.1](../../tasks/handoff-chatgpt.md), evidence of an unbuilt proposal only.
- **O:** [OFSI general guidance, identity matches and ownership/control](https://www.gov.uk/government/publications/financial-sanctions-general-guidance/uk-financial-sanctions-general-guidance),
  sections 2.3 and 4, consulted 21 November 2026. It separates a name match from a target match
  and explains that restrictions can extend to entities owned or controlled by designated
  persons. Identity clearance alone therefore cannot establish permission to transact.
- **F:** [FCA sanctions controls findings](https://www.fca.org.uk/publications/good-and-poor-practice/sanctions-systems-and-controls-our-firms-our-findings),
  sections 6.8–6.9, consulted 21 November 2026. It identifies list maintenance, data ingestion,
  matching calibration and ownership/control screening as operational control concerns.
- **B:** [FCA Handbook FCG 7.2](https://handbook.fca.org.uk/handbook/fcg7/fcg7s2), consulted
  21 November 2026. Calibration should suit the firm's needs and risks. This does not validate
  a bank/fintech split in legal duties or the proposed disposition table.

External guidance supplies operational context; it does not amend P or validate new scoring
rules. All proposed responses below are research judgments awaiting owner decisions.

## Register and assumptions

**Silent:** no explicit procedure for the edge case. **Thin:** a rule exists, but evidence or
operational detail is limited. **Premise:** a stated rule depends on a premise that may fail
outside the exercise. **Outside:** intentionally outside identity adjudication. These kinds
are reconstructed working definitions; even their original entry membership is unknown.

A proxy measures exposure to a question, not a defect, wrong decision or required escalation.
A zero proxy does not establish the absence of the underlying gap.

| ID / kind | Question, source and current behavior | Assumption and proposed research response | Measured indicator / limitation |
|---|---|---|---|
| R01 Silent | What if the latest approved checks conflict at the same recorded time? P4 specifies recency; [C: picture](../../system/screening/resolve.py) breaks ties by source ID. | Assumption: an ID order is sufficient for reproducibility, but does not establish evidential superiority. Ask the owner about explicit conflict review. | Per candidate, structured approved checks at the latest parsed date with distinct raw name/DOB/document-country tuples. Notes excluded; harmless formatting differences can flag. |
| R02 Silent | Can evidence created after screening be used? P4 gives no explicit as-of cutoff; C `picture` reads approved checks without one. | Assumption: all supplied evidence is admissible in the exercise. A production replay needs an explicit time basis. Do not add a cutoff here. | Any structured approved check in a candidate group definitely later than screening under `dates.surely_before`. Excludes notes and incomplete/ambiguous timing. |
| R03 Thin | What if linked records disagree on declared DOB? P3 joins records; P4 ranks verified facts. C falls back through declared DOBs if verification gives none. | Assumption: the merge links are trustworthy and a fallback DOB is usable. Reconcile conflicts before treating them as operationally settled. | Any candidate group with distinct nonempty parsed declared DOB renderings, even if a verified DOB resolves it; differing precision can flag. |
| R04 Thin | What if a populated listed DOB cannot be read? P5/P6 require evidence, not guessed dates; [C: build_hit](../../system/screening/watchlist.py) parses available values. | Assumption: reading failures do not justify a contradiction. Audit unreadable alternatives with the owner; do not infer new clearance grounds. | Any nonempty raw `dobs` item returning no parsed date. Does not detect dates parsed with the wrong meaning or all ambiguous dates. |
| R05 Thin | What if a country is present but unrecognised? P6 requires all ties; C already blocks location clearance on unknown countries. | Assumption: unresolved places are uncertainty. Retain that safeguard; improve coverage only with evidence. | Unknown hit countries or resolved customer unknown countries. Does not find omitted or incorrectly recognised ties. |
| R06 Thin | What if no customer record resolves? P2 requires the correct customer's records. [C: screened_only](../../system/screening/resolve.py) limits what can decide. | Assumption: a failed join is not proof of a different identity. Route for record recovery; type/death behavior remains the owner's rule. | No distinct customer candidate; missing primary alerts abort the tool instead of being counted as clean. |
| R07 Thin | Multiple people fit. P3 expressly covers agreement/disagreement; [C: combine](../../system/screening/decide.py) applies it. | Assumption: unanimous outcomes can settle identity despite unresolved customer selection. Keep this explicit in handoff to operations. This is a covered case, not a claim of policy silence. | More than one distinct candidate person, including unanimous outcomes; does not assert ambiguity in the final decision. |
| R08 Thin | Hit DOB comes from prose/search. P5 authorises bounded recovery; C `build_hit` implements it. | Assumption: the recovered date refers to this hit rather than another subject. Preserve provenance; inspect extraction stress evidence before expansion. | Final DOB origin `notes` or `search`. Does not assess correctness or count both sources if one wins. |
| R09 Thin | Hit DOB remains absent. P7 sends insufficient evidence to review, unless another rule settles it. | Assumption: absence is not contradiction. Seek additional evidence without inventing dates. | No final parsed hit DOB after recovery. Includes companies and hits settled on other grounds. |
| R10 Premise | A deceased profile can clear. P6 explicitly authorises this; [C: decide](../../system/screening/decide.py) applies its time test. | Assumption: death metadata is accurate and the exercise's customer semantics justify exclusion. Production fraud/estate scenarios need separate treatment; do not override P here. | Any parsed hit death date, not merely a death-based clearance. Does not establish that the premise fails. |
| R11 Premise | Age/incorporation relative to a report can clear. P6 explicitly sets this rule; C uses the earliest accepted report. | Assumption: the report date is a meaningful temporal constraint on the listed subject. Production narratives may need human attribution checks. | Any parsed earliest report, not a count of temporal clearances, premise failures or ages below threshold. |
| R12 Outside | Ownership/control exposure can survive a different-name identity result. P1 restricts this task to identity; O §4 covers wider scope. | Assumption: another control examines ownership and control, including indirect/control routes. Do not label identity clearance as business permission. | Unknown: supplied relationships are not a complete ownership/control assessment. |
| R13 Outside | Which jurisdiction, regime, restriction or licence applies? P1 excludes acceptability; O discusses restrictions and licences. | Assumption: compliance determines applicability and next action separately. A listing category alone cannot answer that question. | Unknown: operational/legal context and applicable permissions are not established by the supplied identity fields. |
| R14 Outside | Are lists and customer facts current, and are matching thresholds effective? P is a fixed snapshot; F discusses operational controls. | Assumption: the exercise snapshot is sufficient for scoring. Offline reproducibility does not prove freshness or coverage. | Unknown: a snapshot cannot establish ongoing ingestion, rescreening or tuning effectiveness. |
| R15 Outside | Who owns escalation, deadlines, holds, approval and audit completion? P defines referral, not a full case workflow; F/B provide control context. | Assumption: authorised compliance staff own these actions. Document workflow before implementation. | Unknown: no operational action log or SLA evidence is established here. |
| R16 Silent | How should extra hit identifiers affect adjudication? P5–P8 give no general identifier-comparison clearance rule; C does not use hit `identifiers` to decide. | Assumption: identity rules remain exhaustive. Extra identifiers may prompt investigation, never a new clearance reason in this task. | Nonempty hit `identifiers` only; no comparison with customer documents, accuracy or uniqueness claim. |

## Counting method and reproducible snapshot

Run from the repo root, with private `ROOM` set locally:

```sh
python tools/gap_counts.py "$ROOM"
python -m unittest discover -s tools -p test_gap_counts.py
```

The tool opens source files read-only and emits aggregate JSON to stdout. It does not emit IDs,
names, free text, paths, scored rows or explain files. It uses the current resolver and decision
code with every optional layer explicitly off, independently of environment settings. It
requires each input table and the variants file, rejects malformed JSON/non-object rows,
empty primary tables, duplicate primary IDs and missing primary hit-alert links. This is not
full schema validation. An input/analysis error exits nonzero without a partial report or row
contents. It does not silently treat an unmeasurable question as zero.

Each predicate counts a hit at most once across candidate people. Predicates overlap; never
sum their counts as distinct hits. The by-decision columns mean the **existing rule outcome**
for flagged hits, not decisions a gaps layer would change. They are not accuracy measures.
The hashes in the JSON identify input, tool and runtime source bytes for reruns; row order can
change the input hash. The tool performs no network requests or API/model calls.

Snapshot below was generated by the command above on the private validation ROOM with runtime
baseline `94b96fc`. No original historical counts were reused.

| Indicator | Hits | Existing DIFFERENT_ENTITY | Existing REVIEW | Existing SAME_ENTITY |
|---|---:|---:|---:|---:|
| R01 | 0 | 0 | 0 | 0 |
| R02 | 0 | 0 | 0 | 0 |
| R03 | 0 | 0 | 0 | 0 |
| R04 | 0 | 0 | 0 | 0 |
| R05 | 0 | 0 | 0 | 0 |
| R06 | 0 | 0 | 0 | 0 |
| R07 | 35 | 9 | 23 | 3 |
| R08 | 122 | 72 | 10 | 40 |
| R09 | 545 | 306 | 199 | 40 |
| R10 | 4 | 4 | 0 | 0 |
| R11 | 214 | 144 | 26 | 44 |
| R16 | 212 | 110 | 38 | 64 |

Input: **440 alerts, 819 hits**. Existing decisions: DIFFERENT_ENTITY 464, REVIEW 230, SAME_ENTITY 125. Distinct hits with any measured indicator: **711**.

```text
data_sha256: 8cde76f432cbdcb57eb96b7c9dde60a04b425cd130f8f64fa3dab8a3f77b5b4b
runtime_sha256: 23d2dbe71eef554b08c2b26f9717ded5031182ad9acdd6a8738628085848ac73
tool_sha256: 14bbea5348b86386b6bc14067c22f4061defc7a9e65ffcefaea1d42d5f284948
```

Unknown entries R12–R15 remain null, not zero. In particular there is no measured equivalent
of historical G16, no proof of a single affected hit, and no estimate of runtime-layer impact.

## Assumption review: justification, disproof and analyst action

This completes the register's review obligations under
[the direction note](../../tasks/policy-gap-direction.md). “Defensible” here means a bounded
research assumption, not proof that the resulting identity or business decision is correct.
P remains the identity authority. The actions below are our operating proposals.

| Gap | Why the assumption is defensible within its limit | Evidence that would change it | Consequence if wrong; next analyst action |
|---|---|---|---|
| R01 | P ranks recency, while ID order only makes C repeatable. | Authoritative correction, timestamp precision or a documented source hierarchy resolving the tie. | Wrong verified facts could settle identity incorrectly; obtain both originals and an independent reconciliation. |
| R02 | P describes supplied evidence without an as-of restriction. | A requirement to reconstruct knowledge at screening time, or proof a later check supersedes an error. | Look-ahead bias or stale identity; establish the required time basis and obtain dated evidence. |
| R03 | P authorises merging, but verified precedence can resolve declared disagreement. | Corrected records, verified DOB or proof the records belong to different people. | False linkage or arbitrary fallback; verify links before using the combined picture operationally. |
| R04 | An unreadable date does not establish a contradiction under P6. | Provider clarification or independently verified reading of every alternative. | An agreeing DOB might be lost; have a reviewer read the raw field and report any decision risk to the owner. |
| R05 | An unresolved place cannot support exhaustive disjointness under P6. | Authoritative country/territory mapping or reliable correction to the source. | A shared country might be missed; retain the existing block and reconcile the place. |
| R06 | Missing records cannot identify a different person. | Verified account/onboarding links and the missing customer picture. | Screening the wrong subject; ask the record owner to repair the link. |
| R07 | P3 explicitly permits unanimous per-person outcomes. | Missing candidate, corrected links or new evidence causing disagreement. | Premature operational closure despite ambiguous subject; record every candidate and seek resolution where wider controls need a definite customer. |
| R08 | P5 permits recovery through specified source constraints. | Source text about another subject, contradictory provider DOB or failed extraction stress case. | Wrong recovered date; inspect attribution and report the bounded failing case. |
| R09 | P7 provides REVIEW when no other fact settles identity. | Verified DOB or another admissible deciding fact. | Missing true match; seek evidence and preserve uncertainty. |
| R10 | The death-based identity rule is explicit in P6. | Provider correction, estate context, identity fraud evidence or incorrect death attribution. | Operational false reassurance despite a rule clearance; refer the premise concern to compliance without rewriting the scored answer. |
| R11 | P6 explicitly supplies the age/incorporation premise. | Report concerns another subject or describes a different event/time relationship. | An alleged temporal impossibility may not hold in reality; inspect attribution and event meaning. |
| R12 | P1 intentionally limits the identity task; O supplies the wider exposure. | Verified ownership/control structure, applicable regime and specialist determination. | Exposure through another entity; request beneficial-owner/control evidence and assign compliance assessment. |
| R13 | Identity fields cannot determine all applicable restrictions. | Legal entity permissions, booking location, parties/corridors, regime and licence scope. | Wrong legal workflow; request jurisdictional assessment before giving operational advice. |
| R14 | A fixed input is adequate to rerun an exercise, not to demonstrate ongoing controls. | Provider timestamps, list ingestion tests, authoritative updates and rescreening history. | Missed/new designation; verify update and coverage controls separately. |
| R15 | P refers unsettled cases to humans, without defining a complete workflow. | Named accountable reviewer, authority, deadline and case/action audit trail. | Unowned alert or unauthorised action; assign an owner and track unresolved status. |
| R16 | P enumerates clearance grounds without a generic extra-identifier rule. | Authenticated identifiers and an owner-approved comparison procedure. | Misuse of unreliable identifiers; investigate them as additional evidence and never invent a new clearance ground. |

## Operating settings: evidence before institution labels

Additional primary research, consulted 21 November 2026:

- **E:** [EBA final guidelines on restrictive measures](https://www.eba.europa.eu/sites/default/files/2024-11/eaeae49d-81a5-4154-8af9-5014f6ee8881/Final%20Report%20Guidelines%20restrictive%20measures%20.pdf),
  [Regulator-hosted copy](https://fi.ee/sites/default/files/2025-05/Final%20Report%20Guidelines%20restrictive%20measures%20.pdf).
  EBA/GL/2024/15 §4.1.5 paragraphs 19–22 and 26 (pages 34–35), and EBA/GL/2024/14
  paragraph 11(b) (page 15). The guidance addresses funds becoming available, payment parties
  and intermediaries, outsourcing responsibility and independence of controls. It is EU
  supervisory guidance; it does not impose a universal two-reader rule or establish UK scope.
- **M:** [FATF risk-based approach for money/value transfer services](https://www.fatf-gafi.org/content/dam/fatf-gafi/guidance/Guidance-RBA-money-value-transfer-services.pdf),
  paragraphs 4 and 7–9 (pages 4–6). Non-binding AML/CFT guidance supports assessment of the
  actual provider and its exposures rather than treating an entire sector alike. This is
  contextual risk methodology, not a sanctions exception.
- **U:** [Regulation (EU) 2024/886, Article 1 inserting Article 5d](https://eur-lex.europa.eu/eli/reg/2024/886/oj).
  Covered instant euro transfers have a specific customer-verification regime, including
  periodic checks and rules concerning transaction-time verification. Applicability must be
  established before recommending a screening workflow. Speed alone cannot determine it.

The following fields are proposed operational inputs, **not available facts inferred from the
development set**. Each value must carry an evidence reference, an as-of date supplied by the
caller, an accountable owner, and status `verified`, `declared`, `unknown` or `conflicting`.
Only verified values qualify for a less urgent disposition. An explicit, verified `not_applicable`
needs a reason and source; omission is always unknown. Historical evaluation uses the supplied
as-of date, never the wall clock. These rules are our design choices, not source mandates.

| Exposure | Required evidence; source context | Defensible interim assumption / what changes it | Proposed action and wrong-assumption cost |
|---|---|---|---|
| Institution type and permissions | Regulated legal entity, permissions and actual business model; B/M. “Bank” or “fintech” alone is descriptive metadata. | No exposure level from the label. Verified products, jurisdiction and controls change routing. | Request permissions/context; a label-based shortcut could miss the same exposure in either type. |
| Products and custody | Product, asset, transaction purpose and who controls availability; E/M. | Product risk unknown until its actual mechanism is evidenced. Contracts and rail/control records change it. | Determine release/custody boundary; an assumed gate may not exist. |
| Jurisdictions | Booking entity, parties, corridors, applicable regimes and legal-scope assessment; O/U. | Scope unresolved, rather than automatically UK or EU. Legal assessment changes it. | Route to jurisdiction specialist; wrong scope may choose the wrong screening/action procedure. |
| Payment speed | Availability timestamp or explicit phase and evidence of imminent external availability; E/U. | Speed unknown without rail/custody evidence. Settlement is not automatically customer availability. | Prioritise confirmed imminent loss of control; a timing error could leave no chance for assessment. |
| Reversibility | Tested cancellation/recall rights, cutoffs and effective release gate; E informs the availability boundary, not recall guarantees. | Do not assume recall works. Test/contract evidence changes it. | Ask operations about actual control; a mistaken recall assumption could permit unrecoverable movement. |
| Customer relationship | Direct vs intermediary relationship, record linkage and authority to obtain underlying-party data; E/M. | Underlying visibility unknown without evidence. Verified payment/customer records change it. | Name the relationship owner and obtain missing subject data; otherwise the wrong party may be assessed. |
| Intermediaries | Payment-chain identifiers, roles, underlying parties and outsourced-control assurance; E. | Outsourcing or a familiar correspondent does not prove complete visibility. Message fields and assurance change it. | Request missing chain details; an unseen relevant party may remain unchecked. |
| Ownership/control | Beneficial ownership, control rights and specialist assessment under the applicable regime; O §4. | Identity clearance does not settle this. Verified structure and control analysis change it. | Commission separate assessment; indirect exposure may survive name clearance. |
| List quality | Provider/list scope, versions, updates, ingestion results and calibration evidence; F. | Freshness and coverage unknown from a deterministic snapshot. Tested update lineage changes it. | Verify list controls; reproducible stale input can still miss designations. |
| Identity quality | Source authority, record links, conflicts and extraction provenance; P2–P5, F. | Treat R proxies as questions, not confirmed defects. Originals and reconciled evidence change it. | Request originals or independent attribution; false certainty may settle the wrong person. |
| Independent review | Named competent reviewer, independence from the case originator, availability and authority; E/F. | No assumed second reader. Roster and delegation evidence change it. | Assign an authorised alternate if absent; conflicted/unavailable review cannot complete a control. |

A bank with instant cross-border payments and a fintech with scheduled domestic transfers can
have the reverse of a label-based risk ordering. The examples below vary evidenced conditions;
no legal relief is inferred from institution type. The actual assignment's operating inputs
are unknown. None of these exposure fields is counted by `gap_counts.py` as established data.

## Explain integration

The explain runtime implements version 1 of the table below. It evaluates the finalized
scored row, source-linked candidate indicators, and the optional private operating context.
The first matching row selects the primary disposition and the explain file retains secondary
actions. See the [explain schema and context format](../explain-format.md#policy-gap-follow-up).

The implementation records attestations for each hit. It validates context shape, values,
references and validity windows. Actual operational facts and the underlying sources remain
with operations. Reviewer availability and completed review are separate facts. A different-entity result with unresolved customer selection cannot lead to identity
closure. Invalid attestations, unknown gap IDs and annotation exceptions produce UNKNOWN_CASE.

## Deterministic operational table

All dispositions below are advisory queue states. The engine does not execute a payment hold,
freeze assets, send a report or authorise a transaction. “Preserve gate” means ask authorised
operations to assess an evidenced existing gate under the applicable legal workflow. U means
that an additional transaction-screening step must never be inferred merely from speed.

Rows are evaluated in the fixed order shown, **all matches are retained**, and the first match
is the primary disposition. The set `operational_required` comprises verified product/custody,
legal scope, availability, reversibility, relationship/chain, ownership applicability/assessment,
list quality, identity quality and reviewer status. Institution label alone is not required to
choose routing. Required data that is explicitly not applicable must have verified reasons.

| Row | Predicate / gap | Chosen assumption and source of observations | Primary disposition / next action; consequence if wrong |
|---|---|---|---|
| T00 | Annotation exception, invalid context structure, unclassified gap or unsupported enum; R15 | No safe interpretation exists; parser result or unmatched input field is the source. | `UNKNOWN_CASE`: assign specialist and repair context; silently accepting it could hide a novel failure. |
| T01 | Scored SAME_ENTITY; R13/R15 | P7 establishes identity only; scored row is the source. | `COMPLIANCE_ESCALATION`: assess applicable listing/obligations; treating identity as authorisation could cause an incorrect business action. |
| T02 | Scored SAME_ENTITY or REVIEW, or a clearance with a verified unresolved premise concern R10/R11; plus verified imminent external availability and no verified effective gate/recall | Waiting may lose effective control; use payment/custody evidence, not institution label. | `URGENT_SPECIALIST`: alert authorised operations/compliance now to assess control options; wrong timing assumptions could lose intervention opportunity. |
| T03 | Any operational_required field unknown, declared-only, conflicting, invalid or past its supplied validity period; R12–R15 and any relevant R01–R11/R16 | Missing context cannot justify low exposure; use exact missing/invalid field paths. | `CONTEXT_REQUIRED`: obtain evidence and named owner; false low exposure could select the wrong workflow. |
| T04 | Verified unresolved ownership/control, chain, list-quality or identity-quality assessment; R12–R14 | Identity alone cannot settle wider exposure; use verified structure or chain assessment. | `SPECIALIST_ASSESSMENT`: obtain ownership/chain specialist determination; indirect or hidden-party exposure could persist. |
| T05 | Scored REVIEW; R01–R09/R16 as observed, or R15 if no classified reason | P requires uncertainty referral; scored row and observed gap evidence are the sources. | `IDENTITY_REVIEW`: resolve the identity evidence under existing gate if evidenced and legally appropriate; wrong resolution could miss the customer. |
| T06 | Clearance with a verified unresolved evidence conflict or premise concern; R01–R04/R10/R11/R16 | A concern requires explicit evidence beyond a proxy count; originals and analyst attribution are sources. | `SECOND_READER`: route to an independent authorised reviewer if verified available, otherwise designated alternate/unresolved queue; a proxy must never masquerade as an adjudicated defect. |
| T07 | Clearance, no earlier match, complete verified/not-applicable context and all relevant controls assessed complete | Identity closure is local to this alert; scored row and completed assessments are sources. | `IDENTITY_CLOSED`: record closure and residual caveats; this is not transaction permission. An inaccurate completion assertion could conceal unresolved controls. |
| T08 | Any case not matched above; R15 | Coverage is incomplete; unmatched case itself is the source. | `UNKNOWN_CASE`: request specialist classification and extend the approved table; never default to close. |

T08 is a fallback, not an extra match when another row succeeded. T00 outranks all ordinary
rows. T01 retains urgency/context matches as secondary actions. T02 outranks T03 because a
known timing concern should not disappear behind missing context; T03's missing-evidence task
is still retained. T06 records reviewer availability and cannot mark a second read complete
just because the profile asks for it. Availability alone never closes a review. Ordering
within a row is lexical; no weights, hidden thresholds or sorting by free-text descriptions.
No claim is made that the proposed predicates have been validated on real operating context.

## Worked examples and counterexamples (all invented)

These invented examples illustrate the table. In every paired example, the scored JSON
bytes stay fixed while the `gaps` annotation varies. Sources `OPS-*` and `SYN-*` below are invented.

**`payment_availability_boundary`: same REVIEW, different follow-up.** Invented customer
Aster Vale and hit Aster Vale share a name but have no decisive DOB. Identity is REVIEW under
P7 in both settings. In setting A, `OPS-A` verifies a scheduled transfer remains behind an
effective release gate, a recall mechanism, complete scope/context and an independent reviewer.
R09 is present; T05 selects `IDENTITY_REVIEW`, requesting DOB evidence and review under that
existing gate. Assumption: operations' tested gate prevents external availability; a failed
control test or changed payment phase would disprove it. In setting B, `OPS-B` verifies
imminent beneficiary availability, no effective gate and no recall. T02 selects
`URGENT_SPECIALIST`, with T05 retained. Assumption: delay could lose control; confirmed retained
custody changes it. The wrong assumption costs either unnecessary urgency or lost intervention.
Neither result says to freeze, execute or reject the transfer automatically. Speed does not
establish U's legal applicability; legal scope is verified separately in each setting.

**`premise_review_boundary`: same DIFFERENT_ENTITY, different follow-up.** An invented profile
has death metadata before screening; the existing P6 identity result is DIFFERENT_ENTITY.
R10 presence alone does not prove a problem. In setting A, verified complete context and
`SYN-C` establish no unresolved premise concern: T07 records `IDENTITY_CLOSED`. In setting B,
`SYN-D` supplies an unresolved provider correction suggesting the death belongs to a namesake.
R10's assumption is challenged; verified context says an independent reviewer is available.
T06 selects `SECOND_READER`, citing `SYN-D` and the metadata source. The action is to obtain the
provider's authoritative correction. Cost if the concern is dismissed incorrectly: false
operational reassurance. The identity bytes stay unchanged; any evidence-backed runtime bug
must go to the decision owner separately. If setting B also has imminent external availability
and no effective gate/recall, T02 wins and T06 remains in the audit trail.

**`intermediary_visibility`: same clearance, hidden-party question.** An invented company hit
is a different entity by an existing verified name contradiction. Setting A has direct-customer
visibility, verified applicable-scope assessment and all controls complete: T07. Setting B
has the same identity facts but `OPS-E` documents an intermediary relationship and incomplete
underlying-party assessment: T04 requests specialist evidence even with the matched company
cleared. If the underlying-party field is simply absent, use T03 with R13 and a null source,
not T04's affirmative concern. Assuming visibility incorrectly could miss a relevant party;
complete underlying-party records and specialist sign-off change the assumption.

**`same_entity_urgency_overlap`: identity escalation retains urgency.** An invented person
Cedar Fen has matching verified name/DOB and no contradiction: SAME_ENTITY. `OPS-F` verifies
imminent external availability and no effective gate/recall. T01 is primary compliance escalation;
T02 is an explicit secondary urgency action with those source references. T03 is also retained
if any required context is unknown. Matching identity must not conceal an urgent operating
exposure, and urgency must not rewrite the identity result.

**`institution_label_invariance`: label is not evidence.** Swap “bank” and “fintech” in setting
B of the payment example without changing any verified exposure. T02 and all secondary matches
must be identical. Conversely, a bank behind a verified scheduled gate can use setting A and
a fintech with verified imminent external availability can use setting B, or vice versa.
Neither type inherits a risk level or weaker sanctions duties.

**`independent_reader_unavailable`: a request is not completed review.** Reuse the premise
example's setting B. A verified reviewer roster now says no independent reader is available.
T06 still records the concern, routes to a designated authorised alternate and leaves it
unresolved; it cannot output completed closure. If availability is unknown instead, T03 wins
and requests the roster. A documented independent completion could resolve the task, but it
must not silently rewrite the scored identity. This is a proposed operating control, not a
claim that E mandates a second reader for every hit.

**`unknown_and_overlap`: information failure remains visible.** A clearance has a verified
ownership concern R12 and a conflicting legal-scope field R13. T03 is primary, T04 secondary;
both assumptions, evidence references and actions survive. An unrecognised new gap `RX` also
appears: T00 becomes primary `UNKNOWN_CASE`, retaining T03/T04. A complete, valid classification
and resolved context are the evidence needed to change it. The cost of defaulting to T07 is
closing over a novel concern. No ownership percentage or listing category alone resolves it.

## Research snapshot and runtime validation

Completed for this docs/tool scope: the system tests, invented tool tests, repeated aggregate
counts, fresh scored run equal to committed bytes, private validator and viewer sample check.
The private validator reports no output problems, all practice decisions correct and no unsafe
clearances. The aggregate snapshot above records the actual measured counts. Only new
research/tool files and context guidance are changed; no runtime layer has been tested or built.

The runtime suite covers payment urgency, label invariance, overlapping matches, ownership
and premise concerns, unavailable reviewers, invalid or stale context, unresolved customer
selection, and annotation failure. The paired pipeline test compares scored bytes across
operating settings. These are synthetic checks. Operational adoption still requires validated
context sources, applicable legal scope and workflow ownership.
