# Where things stand

**Snapshot: 13:44 London time, 21 November 2026. The code under `system/` last changed at commit
`e3cf06a`.**

This page goes out of date quickly. The live picture is always in git:

```
git fetch origin
git log --oneline origin/main     # what is on main
git branch -r                     # which task branches have been pushed
```

If you change the state of a task, update this page in the same pull request.

## Numbers to expect

Every figure below was printed by a command run on `main` at `e3cf06a`. If you see something
different on the same commit, stop and report it.

| Command | What it printed |
|---|---|
| `python -m unittest discover -s system/tests` | `Ran 169 tests`, `OK` |
| `python system/run DATA <file>` | `819 hits decided in 6.6s: DIFFERENT_ENTITY 464, REVIEW 230, SAME_ENTITY 125` |
| the same run, second line | `layers: score=on, reviewer=off, briefing=on, reader=off` |
| the run twice, files compared | byte-identical |
| a fresh run compared with the committed `output/dev.jsonl` | byte-identical |
| `python ROOM/validate.py --data DATA --output <file>` | `819 lines read, 0 problems` |
| the same with `--score DATA/practice_labels.jsonl` | `50 hits, 50 right decisions, 0 unsafe clearances`, `decision score 100.0`, `reason code 100%, customer record 100%` |
| evidence list compared with the reference list on the practice labels | equal on 50 of 50 |
| `python tools/repro.py DATA --runs 5 --strict` | 5 fresh processes with hash seeds `random`, 1, 2, 3, 4: `hits whose decision or reason code differs between runs: 0`, scored and explain files `byte-identical across 5 runs: yes`, `committed output/dev.jsonl equals a fresh run: yes`, exit code 0 |
| the scored file's SHA-256, from the same command | `28b0b35d1d11abe5e65cdeca9b9f174d7cee16f09272f437910f3d277fd3c91d` |
| `python tools/check_countries.py <the ISO 3166 list>` | `249 countries checked, 0 problems`. It also prints `EXTRA CODE XK (Kosovo)`: Kosovo is not on the ISO list and is kept on purpose, because watchlists use it |
| the test workflow on GitHub, read at 13:30 for commit `9ae3d90` | 8 jobs, all `success`: Linux, Windows and macOS with Python 3.10 and 3.12, Linux with Python 3.8, and the check that `system/run` is executable, has the `python3` line and Unix line endings |

The committed predictions, by reason code:

| Decision | Hits | By reason code |
|---|---|---|
| `DIFFERENT_ENTITY` | 464 | `LOCATION_MISMATCH` 264, `DOB_MISMATCH` 95, `NAME_MISMATCH_VERIFIED` 79, `TEMPORAL_IMPOSSIBILITY` 21, `DECEASED` 4, `ENTITY_TYPE_MISMATCH` 1 |
| `SAME_ENTITY` | 125 | `NAME_DOB_MATCH` 85, `NAME_LOCATION_MATCH` 40 |
| `REVIEW` | 230 | `INSUFFICIENT_DATA` 214, `AMBIGUOUS_CUSTOMER_RECORD` 16 |

The stress test and the layer comparison are reported in [system/README.md](../../system/README.md).

## Done and on `main`

| What | Commit |
|---|---|
| UI and UX research for the viewer and the video | `916efdf` |
| The policy rules as code: names, dates, countries, the decision table, with tests | `ba40ffa` |
| The end-to-end run: customer lookup, hit facts, output writer, `system/README.md` | `325d70d` |
| Hardening for unseen wording, and the stress test | `426d08a` |
| Six task briefs in `tasks/` | `c51bd77` |
| Predictions on the development set, `output/dev.jsonl` | `7e90dd5` |
| Three teammate handoffs, the explain file format, invented viewer samples | `9304cf4` |
| The plug-in layer framework, the explain file, the layer comparison tool | `dc22837` |
| The `score` and `briefing` layers, and 26 whole-run tests for rare policy cases (task 02) | `0dff5b7` |
| The model layers (`reader`, `reviewer`, the OpenRouter client), `tools/model_check.py`, and a 27th whole-run test | `38e0b75` |
| The five-run reproducibility check `tools/repro.py` and the test workflow `.github/workflows/tests.yml` (task 03) | `9ae3d90` |
| Country names the official list writes back to front, found by Teammate B's country check | `e3cf06a` |
| Teammate B's demo on public sanctions lists, `tools/make_public_demo.py` and `docs/data-sources.md` (pull request 2), with the three review fixes | `dedc2f7` |

## In progress

The model layers are on `main` but off by default. They have only run against a stand-in model:
no API key was available, so a real model is still unmeasured. That measurement is Teammate C's job.

| What | Who | Where | State at the snapshot |
|---|---|---|---|
| The review viewer, `viewer/index.html` | Teammate A | pull request 1, branch `task/viewer` | Open, not merged. The owner's review found no blocking bug and five small ones; they are not fixed yet. Not opened in a browser by the owner |
| Model check, results table, demo script, submission text, video | Teammate C | branch `task/results`, not pushed yet | Handed off at 12:52. `tools/model_check.py` and `tools/ablate.py` are on `main`, so every job can start |

The handoffs are `tasks/teammate-A-viewer.md`, `tasks/teammate-B-data.md` and
`tasks/teammate-C-model-and-demo.md`.

Teammate B's handoff is finished and merged. Two things about it are unverified: the demo has not
been re-run on the real public list since the review fixes (it was tested on invented lists, and
profiles with one birth date give byte-identical output to before), and the clearance audit, which
reports 16 of 16 sampled clearances supported, has not been re-checked row by row.

## Not started, with nobody recorded against them

| Task | What it would give us |
|---|---|
| [05, traceability matrix](../../tasks/05-traceability.md) | One table showing every policy rule has a place in the code and a test |

Ask the owner before starting it.

## The plan for the rest of the day

This is the owner's timeline, set at 11:33. The first working version landed early, at 12:23.

| Time | Work |
|---|---|
| until about 14:30 | Layers, viewer and data jobs, as listed above |
| 14:30 to 15:30 | Measure the model layers. Keep one only if it helps and five runs agree. Confirm a run stays under 30 minutes |
| 15:00 | Office hours with the mentors. Bring the open questions from [decisions.md](decisions.md) |
| 15:30 to 16:15 | Final `system/README.md` and final `output/dev.jsonl` |
| 16:15 to 16:45 | Record the 2-minute video, push, submit |
| **17:00** | **Code freeze** |

## What must be true at 17:00

- [ ] `main` passes `python -m unittest discover -s system/tests`.
- [ ] `output/dev.jsonl` is byte-identical to a fresh run of the final code. The organisers
      re-run the system on the development set to check this, so regenerate the file after the
      last change under `system/`. `python tools/repro.py DATA --strict` checks it and exits 0
      only when it holds.
- [ ] The test workflow is green on the last commit.
- [ ] `validate.py` reports 0 problems on it.
- [ ] `system/run` is executable in git, starts with `#!/usr/bin/env python3` and has Unix line
      endings. All three were true at the snapshot.
- [ ] `system/README.md` covers what the brief asks for: architecture, how each side is found,
      how evidence is represented, run-to-run stability, model and prompts, time and cost, and
      three explained cases. All were present at the snapshot.
- [ ] No data file and no API key is tracked.
- [ ] The 2-minute video is uploaded and its link is public.
- [ ] The submission form is sent before 17:00. Its fields are listed in
      [hackathon.md](hackathon.md).

## Known limits

They are listed honestly at the end of [system/README.md](../../system/README.md), under "What
is missing". Read them before claiming the system does something.
