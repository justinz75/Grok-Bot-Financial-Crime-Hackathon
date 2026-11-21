# The hackathon: what is asked and how it is scored

This is our summary, in our own words. The authority is the organisers' full brief, which is
`ROOM/README.md` in the data room (participants only). The public parts are on the event site:
<https://gb-fincrime-hackathon-11-2026.teamdeel.workers.dev/hackathon#track-2> and its `/submit`
page. Read on 21 November 2026. If this page and the brief disagree, the brief wins.

## The event

| | |
|---|---|
| Event | Grok Bot London Financial Crime Hackathon, hosted by SpaceXSI with Diligent |
| Date | Saturday 21 November 2026, 10:00 to 18:00, London |
| Our track | Track 2, sanctions screening ("Is my customer sanctioned?"). Diligent designed it |
| Team size | One to five people. One submission per team |
| Code freeze | **17:00 London time.** The last commit on `main` before it is scored |

## The problem

Banks check every customer's name against watchlists: sanctions lists, politically exposed
persons, enforcement records and adverse media. The matching is loose on purpose, so most hits
are a different person with a similar name. An analyst then has to decide, hit by hit, whether
the listed profile really is the customer. That decision is the whole task.

Only identity matters. How serious the listing is, and whether the bank would keep the customer
anyway, are different questions and must not influence the answer.

Both sides have to be worked out before they can be compared:

- **The customer** is spread over five bank systems that do not share one key. One person can
  have several records, and relatives can share a phone or an address.
- **The listed person's** most useful fact, usually a date of birth, may sit in a field, in a
  sentence of the profile, or only in web search results that are mostly about namesakes.

## The deliverable

Three things, all in a public GitHub repository:

1. **A runnable system**, called as `system/run <data folder> <output file>`.
   - It reads only that folder and writes one JSON line per hit.
   - It may use the Python 3 or Node.js standard libraries, or shell. No installed packages.
   - It may call a language model only through the OpenRouter API, with the key taken from
     `OPENROUTER_API_KEY`. The organisers set their own key when they test.
   - A run should finish in under 30 minutes. Ours takes about 8 seconds.
2. **Predictions on the development set** in `output/dev.jsonl`, made by that system. The
   organisers run the system on the development set once to check the file really came from it,
   so the committed file must be what the current code produces.
3. **A short README in `system/`** covering: the architecture (a diagram helps), how the customer
   and the listed person are found, how evidence is represented, how results stay the same from
   run to run, which model and prompts are used if any, the time and cost of a run, and three
   explained cases: a clear mismatch, a match, and one left for review.

Not allowed in the repo: the development data and any API key.

## One output line

| Field | Content | Format |
|---|---|---|
| `hit_id` | The hit, from `hits.jsonl` | `H-` and six characters, digits or capitals A to F |
| `alert_id` | The hit's alert | `A-` and six characters of the same kind |
| `decision` | `DIFFERENT_ENTITY`, `SAME_ENTITY` or `REVIEW` | |
| `reason_code` | The main ground. It must belong to the decision | see [policy.md](policy.md) |
| `customer_record_id` | The customer record the alert was resolved to | `CUS-` and six digits, or `AMBIGUOUS`, or `null` |
| `reason` | Two to four sentences naming the decisive facts, with this hit's own values | text |
| `evidence` | The IDs of the records that decided it, exactly as they appear in the files | list of strings |

`ROOM/output.schema.json` is the formal version. `ROOM/validate.py` checks a file the way the
organisers do. A hit with no line counts as `REVIEW`.

## How the score is worked out

The system is run **five times on an unseen set of about 550 hits** from the same bank, with new
customers, new hits and free text worded differently. Some situations the policy covers are rare
in the development set.

**Each decision has a cost. Lower is better.**

| The right answer is | We said `DIFFERENT_ENTITY` | We said `SAME_ENTITY` | We said `REVIEW` |
|---|---|---|---|
| `DIFFERENT_ENTITY` | 0 | 3 | 3 |
| `SAME_ENTITY` | **60** | 0 | 2 |
| `REVIEW` | **60** | 2 | 0 |

The decision score is the share of cost saved compared with sending every hit to review.
Sending everything to review scores 0. So does clearing everything, because a score below 0
counts as 0. Some hits are not scored, because their answer depends on information that is not
in the files. They still need a line.

**Reasons are checked on every right decision:** the reason code fits, the evidence cites the
records that decided it and not everything that was looked at, the customer record is right, and
the reason text states the real grounds with this hit's own facts.

**The total, out of 100:**

| Part | Weight | What counts |
|---|---|---|
| Unseen set | 80% | Decisions 75%, reasons 25% |
| Development set | 10% | Decisions 75%, reasons 25% |
| Reproducibility | 10% | The same decision and reason code in all five runs, scaled by the unseen score |

The organisers also report unsafe clearances, the share of false positives cleared, clearance
precision, same-entity recall and the review rate.

### What the scoring means for our work

- **A clearance has to be near certain.** Clearing correctly saves 3 and clearing wrongly costs
  about 60, so a clearance is worth making only above roughly 95% confidence.
- **Confirming is cheap to get wrong.** A wrong `SAME_ENTITY` costs 2 or 3 points, never 60.
  The danger is all on the clearing side.
- **Reviewing everything is not safe either.** It scores 0. Clearing the false positives that the
  policy plainly supports is where every point comes from.
- **The unseen set is 80%.** Code that fits the wording of the development files will miss
  things. Build for the policy's principles.
- **Reason quality is a quarter of each part.** The code, the cited evidence and the customer
  record are scored, not only the decision.
- **Anything that varies between runs loses points.** That is why no model takes part in the
  decision.

## How the judges decide

Every team submits a working prototype and a 2-minute video at code freeze. The judges score
every submission, the top five teams present live for 3 minutes each, and first to third place
are chosen from those five.

- **Criteria, with no weights given:** execution, a working prototype, whether it solves the
  problem, creativity, and UX.
- **Who the judges are:** seven practitioners who work on financial crime. They include heads of
  sanctions compliance and of independent testing and assurance, product managers for financial
  crime and for AI, an engineering manager for machine learning, and Diligent's chief executive
  and chief technology officer. Expect questions about correctness, consistency and measurement.
- **What finalists are asked about:** the README and the architecture. How people are resolved on
  both sides, how evidence is represented, how the result is kept deterministic, and whether the
  explanations are honest about what is missing.
- **The code is read.** Judges read the repository, and an automatic analysis runs on the latest
  commit.

The scored deliverable has no user interface. A visual interface counts only in the video, the
optional live-demo link and the live demo. See [research/ui-ux.md](../../research/ui-ux.md).

## Schedule, London time

| Time | What happens |
|---|---|
| 11:00 | Building begins |
| 13:00 | Lunch, building continues |
| 15:00 | Office hours: mentors coach the teams. Mentors do not score |
| **17:00** | **Code freeze, submission through the portal, first round of judging** |
| 17:30 | Live demos of the top five, 3 minutes each |
| 17:50 | Final judging and awards |
| 18:00 | Close |

## What the submission form needs

One submission per team, sent before 17:00:

- a project name, and the track: Track 2, sanctions screening;
- "What did you build?", between 20 and 1200 characters;
- a contact email, and optionally a team name;
- for each member: full name, Cursor email, and a LinkedIn or X link. GitHub, website and
  Discord are optional;
- the link to the public GitHub repository;
- a link to the 2-minute demo video: YouTube (unlisted is fine), Loom, Vimeo, Google Drive set
  to anyone with the link, or any other public link;
- optionally a live demo link.

The team fills in the personal details. An agent must leave them blank and never invent them.

## What the organisers value

Diligent's own material keeps returning to the same points: every output explainable, auditable
and defensible; structured reasoning with a clear audit trail; people kept in the loop for the
uncertain cases. Their pitch contrasts large teams of analysts (nuanced but slow) with fixed
rules (fast but blind to nuance), and offers language models as the way to get both. Our answer
is that the rules decide and stay reproducible, while the layers on top show strength of
evidence, what is missing and a second opinion. The details are in [decisions.md](decisions.md).
