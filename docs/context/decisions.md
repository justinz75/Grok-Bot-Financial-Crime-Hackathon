# Decisions the team has made, and why

Read this before proposing a change of approach. Each entry says what was decided, the reason,
and what it rules out. Times are London time on 21 November 2026. If you think a decision is
wrong, say so with evidence (a failing test, a hit ID, a number from a command) and let the
owner decide. Do not quietly work around it.

## 1. The rules decide. No model takes part in a scored decision

**Decided** 11:33, confirmed 12:24 ("stay rule-only") and kept at 12:41 when the layers were added.

**Why.**
- The policy is close to a decision table. Its rules are explicit enough to run as code.
- 10% of the score is the same decision and reason code in all five runs. Code gives that for free.
- One wrong clearance costs 60 points, so a clearance only pays above roughly 95% certainty.
  A model's mistakes are not predictable enough to rely on that.
- Rules alone score 50 of 50 on the practice labels with no unsafe clearance.

**Rules out.** A model that decides or overrides a decision. This was considered as an option
and rejected.

## 2. Both sides are resolved before anything is compared

**Decided** 11:33.

The system first builds a picture of the customer and a picture of the listed entity. Each
picture is a set of facts, and each fact carries the ID of the record it came from. The decision
step sees only the two pictures. It never reads raw text.

**Why.** It mirrors how the policy and an analyst work. It makes the evidence list fall out of
the decision, and it keeps free-text reading in one place where it can be tested and hardened.

## 3. When something cannot be read, it is unknown, and unknown means review

**Decided** 12:03, widened 12:35 and 13:20.

- A note the reader cannot read gives no fact. It does not give a guess.
- An identity check that is found but whose date of birth cannot be read does not let the
  declared date of birth clear a hit. The declared date may differ from the verified one.
- A country string that cannot be resolved blocks a location clearance.
- A customer who cannot be found in the system of record cannot be cleared or confirmed on the
  screened details.
- A hit that crashes the run still gets a `REVIEW` line.

**Why.** The unseen set words its free text differently. Reading less must be able to cost a
review and must never be able to cost a clearance. `tools/stress.py` damages the development
text nine ways to prove it: some decisions change, and none becomes a new clearance.

## 4. Evidence lists only what decided the hit

**Decided** 11:44, after reading how the practice labels cite evidence.

**Why.** The scoring checks that the evidence cites the deciding records and not everything that
was looked at. Name agreement is stated in the reason but cited to no record, because it rests on
no single one. See the table at the end of [policy.md](policy.md).

## 5. More nuance comes from layers on top, not from changing the rules

**Decided** 12:41 to 12:57, after the team asked for more nuance and explainability than rule
checks alone give.

Four optional layers sit on top of the rules:

| Layer | What it adds | Uses a model | Default |
|---|---|---|---|
| `score` | Strength of evidence in bits, field by field. A rare name or country that agrees counts for more | no | on |
| `briefing` | What decided the hit, what was missing, and the one fact that would settle it | no | on |
| `reviewer` | A model's second opinion on every clearance | yes | off |
| `reader` | A model reads identity notes that the patterns cannot | yes | off |

Each layer is `off`, `on` or `enforce`, set by the `SCREENING_LAYERS` environment variable or
`system/layers.json`. Three guarantees hold, and `system/tests/test_layers.py` checks them:

1. With no layer enforcing, the scored file is exactly what the rules alone produce.
2. No layer can create a clearance. The only change a layer can make is clearance to review.
3. A layer that fails says nothing, and the rules' answer stands.

**Why this shape.** Anything new must either leave the decision and the reason code alone, or
only make them more cautious. Layers write to a separate explain file, which is not scored, so
they can say as much as they like at no risk. Every layer can be switched on its own so its
effect can be measured: `tools/ablate.py`.

**Rules out.** A layer that turns a review into a clearance or into a match. A layer whose
output changes between runs while it is enforcing.

## 6. A model may read, and only under these conditions

**Decided** 12:35, built from 12:57.

- It turns text into facts, or gives an opinion. It never decides.
- It runs at temperature 0, with a fixed seed and a pinned model ID (`SCREENING_MODEL`).
- Every value it returns must appear in the source text as written, or it is dropped.
- A failure of any kind (no key, timeout, bad reply) means "no answer". It never stops the run.
- A fact read by a model may support a match but may not clear a hit, unless the reader is set
  to `enforce`.
- The model layers stay off until `tools/ablate.py --runs 5` shows that they help and that five
  runs agree.

**Why.** These are the conditions under which a model cannot cost a clearance or a
reproducibility point.

**Built stricter than decided** (on `main` at `38e0b75`, 13:23).
- A name the model reads must share a part with a name the bank already holds for that customer.
- A date of birth the model reads must fall at least 14 years before the check.
- A note outside the identity-check channel reaches the model only if it also names a document.
- A check counts as read only when its date of birth was read. An earlier version counted a
  name alone, and on damaged notes that turned 15 matches into clearances.

**Measured so far, against a stand-in and not a real model.** On the data as given no model
setting changes a decision, and the reader makes no calls because the rules read every note.
On a copy whose identity notes lost their capitals, the rules alone differ from the clean run on
35 of 819 hits (practice score 97.2), the reader set to `on` is the same, and the reader set to
`enforce` differs on 1 (practice score 100). No setting created a clearance. The stand-in only
reads capitalised words, so this shows the plumbing works, not that a model does.

## 7. The strength-of-evidence score caps the weight of a name

**Decided** about 13:05, after measuring.

The first version weighed an agreeing name by its rarity with no cap, as textbook record linkage
does. A hit exists because the name is similar, so that weight was large on almost every hit.
It called 284 of 504 clearances evidence of the same person. Enforcing it turned 274 clearances
into reviews and dropped the practice score from 100 to 47. The name is now capped at 4 bits and
the country at 3, which removed every false flag.

**Lesson for any new signal.** Name agreement is nearly worthless as evidence here, because it is
the reason the hit exists. Measure a new signal with `tools/ablate.py` before trusting it.

## 8. No outside data in the scored system

**Decided** 12:45.

**Why.**
- The brief says the system reads only the data folder. The one network call allowed is a model
  through OpenRouter.
- The answers come from the files. A real-world date of birth could contradict the one planted
  in a profile and cause a wrong clearance.
- The customers are invented. No outside database has them.

**Still allowed, outside `system/`.** Checking our country table against the official ISO list.
A demo that screens invented customers against real public sanctions lists. Both are Teammate
B's jobs, and their downloads stay in `data/public/`.

## 9. No tuning against the 50 practice labels

**Decided** 12:41.

An optimiser fitted to 50 labelled hits would overfit, and the unseen set is 80% of the score.
The labels are used to check the system, not to fit it. More checked answers come from the
clearance audit (task 01).

## 10. The repo holds no participant data

**Decided** 11:25, applied to the tests at 12:23.

- `data/`, `dev/`, `.env` and `*.explain.jsonl` are git-ignored.
- Tests use invented names and invented IDs.
- The policy and the brief are described in our own words, never pasted.
- `output/dev.jsonl` is the one exception, because the brief requires it.

**Why.** The repo is public, the brief says the data is for participants only, and the watchlist
profiles come from a screening provider, so they may describe real people.

## 11. The viewer only displays

**Decided** 12:35, specified 12:52.

One static file, `viewer/index.html`, with no build step, no libraries and no network requests.
It shows the system's own reason and evidence. It never rewrites, summarises or re-derives a
decision, and it never calls a model.

**Why.** The scored deliverable has no interface, so the viewer exists for the 2-minute video and
the live demo. A viewer that changed or re-derived anything would be a second line of reasoning.

## 12. One owner for the decision logic and for `main`

**Decided** 12:35.

The owner's session pushes to `main`. Everyone else works on a `task/...` branch and opens a
pull request. Nobody else edits `system/screening/` or `system/run`: a bug is reported with a
failing test or a hit ID.

**Why.** `main` is scored at 17:00 as it stands, and two people changing the decision logic at
once is the fastest way to break it.

## Open questions

| Question | Who can answer | Why it matters |
|---|---|---|
| Do more practice labels exist? | The mentors, at office hours (15:00) | Only 50 hits are answered, and only 8 of the 11 reason codes appear among them |
| Do the model layers help, and are five runs identical? | Teammate C, with an OpenRouter key and `tools/ablate.py --runs 5` | They stay off until this is measured |
| Should `names.py` keep its built-in fallback list of name variants? | The owner | It is generic spelling knowledge, used only if the variants file is missing, but it started as a copy of a data-room file |
