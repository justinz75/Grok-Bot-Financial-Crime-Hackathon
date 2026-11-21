# Tasks for delegation

## Start here: one handoff per teammate

Each handoff is written to be followed step by step, with a prompt to paste into an AI assistant
and checks that say when it is done. They touch different files, so all three can run at once.

| Who | Handoff | Builds | Needs the real data? |
|---|---|---|---|
| Teammate A | [The review viewer](teammate-A-viewer.md) | `viewer/index.html` | no, sample files are provided |
| Teammate B | [More data](teammate-B-data.md) | country check, more checked answers, a demo on public lists | yes |
| Teammate C | [Model check, results table and demo](teammate-C-model-and-demo.md) | `docs/results.md`, demo script, video | yes, plus an OpenRouter key |

The viewer reads two files: the scored output and the explain file described in
[docs/explain-format.md](../docs/explain-format.md).

## The wider task list

Six independent tasks. Each can be given to a different AI agent or teammate, and each touches its
own files, so they can run at the same time. Hand an agent this file plus one task file.
Tasks 01, 04 and 06 are already covered by the handoffs above.

| # | Task | Owns | Needs the data? | Why it matters |
|---|---|---|---|---|
| [01](01-audit-clearances.md) | Audit the clearances | nothing in git (local report) | yes | A wrong clearance costs 60; this is the second opinion |
| [02](02-rare-case-tests.md) | End-to-end tests for rare policy cases | `system/tests/test_pipeline.py` | no | The unseen set has cases the dev set barely shows |
| [03](03-reproducibility-ci.md) | Reproducibility proof and CI | `tools/repro.py`, `.github/workflows/` | partly | 10% of the score is "same answer in all five runs" |
| [04](04-review-viewer.md) | Review viewer for the demo | `viewer/` | to view only | UX criterion, the 2-minute video |
| [05](05-traceability.md) | Policy-to-code traceability matrix | `docs/traceability.md` | no | Shows every decision follows one line of reasoning |
| [06](06-demo-and-submission.md) | Demo script and submission text | `docs/demo-script.md`, `docs/submission.md` | no | Required to submit |

## What "good" means here

These come from how the industry judges this kind of system, and they are the bar for every task.

1. **Explainable.** Every decision names the rule that decided it and the records it rests on.
2. **Reproducible.** The same folder gives the same file, byte for byte. Variance is measured, not assumed.
3. **Cautious where it counts.** Uncertain hits go to a person. Reading less may cost a review; it must never cost a clearance.
4. **Accountable.** Claims are backed by a command anyone can run, and limits are written down.
5. **Proportionate.** No model where a rule does the job.

The system is rule-only by choice: no language model, no randomness, no clock, no network. Do not
add one. If a later decision brings a model in, it may only *read* text into facts, never decide;
it runs at temperature 0 with a pinned model ID; every value it returns must appear in the source
text; five runs must agree before a fact is used; and anything else becomes `REVIEW`.

## Rules for every task

**One line of reasoning.** `POLICY.md` is the only authority on what is right. The decision logic
lives in `system/screening/` and has one owner. Do not edit `system/screening/*.py` or
`system/run`. If you find a bug, prove it with a failing test or a hit ID and report it.

**Same procedure every time.** Follow the numbered steps in your task in order. Where a task says
which items to sample, use exactly that rule. Use the fixed words the task gives for verdicts and
statuses. Two agents doing the same task should produce the same result.

**Data.** `DATA` below means your local copy of the `screening/dev` folder, and `ROOM` the
`screening` folder above it. Never commit either, never paste records into a public place, and
use invented names in tests and examples. `data/` and `dev/` are git-ignored: keep local files there.

**Code.** Anything under `system/` uses the Python 3 standard library only and must run on
Python 3.8. No randomness without a fixed seed, no network, no dependence on the time or on the
order rows happen to be in.

**Git.** Work on a branch named `task/NN-short-name` and open a pull request to `main`. `main`
must always pass the tests, because the last commit before 17:00 is what gets scored. Never force-push.

## Commands

```
python -m unittest discover -s system/tests                      # unit tests, no data needed
python system/run DATA output/dev.jsonl                          # the run, about 6 seconds
python ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl
python tools/stress.py DATA                                      # damaged-text stress test
```

The results to expect are in [docs/context/status.md](../docs/context/status.md), which is kept
current: the test count, the decision counts and the practice-label score. The stress test must
report no new clearances.

## Report format

End every task with this, and nothing else:

```
TASK: NN
STATUS: DONE | PARTIAL | BLOCKED
CHANGED: <files, or "none">
CHECKS: <each command you ran and its last line of output>
FINDINGS: <numbered; each with a hit ID or test name and the policy principle it concerns>
OPEN QUESTIONS: <or "none">
```
