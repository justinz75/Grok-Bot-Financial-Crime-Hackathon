# Where things stand

**Snapshot: 15:13 London time, 21 November 2026. The decision code under `system/screening/` last
changed at commit `73ed186`.**

This page goes out of date quickly. The live picture is always in git:

```
git fetch origin
git log --oneline origin/main     # what is on main
git branch -r                     # which task branches have been pushed
```

If you change the state of a task, update this page in the same pull request.

## Numbers to expect

The tests, the run, the validator, the practice-label score, the five-run check and the stress
test below were run on the commit named above. The
country check and the workflow line are from the commits they name. If you see something
different, stop and report it.

| Command | What it printed |
|---|---|
| `python -m unittest discover -s system/tests` | `Ran 208 tests`, `OK` |
| `python tools/make_viewer_sample.py --check` | `the sample is up to date` |
| `python system/run DATA <file>` | `819 hits decided in 6.9s: DIFFERENT_ENTITY 464, REVIEW 230, SAME_ENTITY 125` |
| the same run, second line | `layers: score=on, reviewer=off, briefing=on, reader=off` |
| the run twice, files compared | byte-identical |
| a fresh run compared with the committed `output/dev.jsonl` | byte-identical |
| `python ROOM/validate.py --data DATA --output <file>` | `819 lines read, 0 problems` |
| the same with `--score DATA/practice_labels.jsonl` | `50 hits, 50 right decisions, 0 unsafe clearances`, `decision score 100.0`, `reason code 100%, customer record 100%` |
| evidence list compared with the reference list on the practice labels | equal on 50 of 50 |
| `python tools/repro.py DATA --runs 5 --strict` | 5 fresh processes with hash seeds `random`, 1, 2, 3, 4: `hits whose decision or reason code differs between runs: 0`, scored and explain files `byte-identical across 5 runs: yes`, `committed output/dev.jsonl equals a fresh run: yes`, exit code 0 |
| the scored file's SHA-256, from the same command | `c23adcc75543dca9c8534cfe3b613edfa28a0e4921856885596c610dd9e97bc1` |
| `python tools/stress.py DATA` | 14 cases, `NEW CLEAR` 0 on every row, ending `new clearances caused by harder text: none`. The five cases that add misleading text printed 129, 10, 28, 41 and 40 before pull request 3, and 0, 0, 2, 0, 0 at its merge |
| `python tools/loop.py DATA` | all six steps `PASS`, exit code 0: `0 of 819 hits changed decision or reason code, 0 moved into DIFFERENT_ENTITY, 0 changed only in reason or evidence`, and `18 of 18 demo cases came out as built` |
| `python tools/public_test.py --people 30000 --companies 30000` on the same export | `sampled: 22772 people (21 with a one-part name) and 24265 organisations, 232142 hits, decided in 260.0s`, then `231992 of 232142 came out as built; 138 went to review instead, 12 to a match` and `cleared when it should not be: 0` |
| `python tools/make_public_demo.py` on the OpenSanctions export in [data-sources.md](../data-sources.md), SHA-256 checked | `Wrote 18 demo cases from 6 OpenSanctions profiles` |
| `python tools/assure.py DATA`, at `ada0873` | exit code 0. `440 alerts with 819 hits`: 175 `CLOSED`, 157 `REVIEW`, 108 `ESCALATE`. `355 hits need a person: 230 reviews and 125 matches`, of which 25 are P1, 109 P2, 4 P3 and 217 P4. Of the 464 clearances, 73 are flagged and 49 sampled for a second reader, 122 in all. The scored file it reports has the SHA-256 above. The tables are in [assurance.md](../assurance.md) |
| `python -m unittest discover -s tools/tests`, at `ada0873` | `Ran 28 tests`, `OK`. They test the assurance tool. The workflow compiles `tools/` and runs only `system/tests`, so it does not run them |
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
| A numeric date that can be read two ways (day first or month first) no longer clears a hit unless both readings contradict it, with 14 tests. It changed no decision on the development set | `7259c05` |
| Pull request 3: a check read out of a note clears a hit only when the note can be believed, a country a support note only mentions blocks a location clearance against it, 15 wording tests, five stress cases that add misleading text, and `tools/loop.py`. On the development set it changed no decision and the wording of one reason, so `output/dev.jsonl` was regenerated in the merge | `10b7575` |
| A support note that is read as a check and not believed no longer stands in front of another check, with 3 tests. Found by the stress test on real data: it had turned 2 reviews into clearances and 11 clearances into matches. It changed nothing in `output/dev.jsonl` | `f91cb9e` |
| The assurance pack, `tools/assure.py`: every alert as closed, for review or for compliance; the reviews and matches in the order to work them; the clearances a second person should read; the name rule tried on 14 variations of every listed name; counts of what the listings hold that the policy does not use; and a manifest of what was run. 28 tests in `tools/tests/`, and [assurance.md](../assurance.md) compares it with what a bank's screening function has. It reads what the system writes and changes no decision | `ada0873` |
| A one-part name that agrees with the hit's, with an agreeing date of birth, is no longer cleared on a country difference: 3 tests. Found by the run on the public sanctions list. It changed nothing in `output/dev.jsonl` | `73ed186` |
| `tools/public_test.py`: the system run on every person and organisation of a real public sanctions list, with answers known by construction. Results in [results.md](../results.md) | `73ed186` |
| The traceability matrix, [traceability.md](../traceability.md) (task 05): 31 rules, each with its code and tests, no gaps | `73ed186` |
| The results page, [results.md](../results.md): the layer comparison, the stress test and the public-list test, as the commands printed them | `73ed186` |
| Teammate B's demo on public sanctions lists, `tools/make_public_demo.py` and `docs/data-sources.md` (pull request 2), with the three review fixes | `dedc2f7` |
| Teammate A's review viewer, `viewer/index.html` (pull request 1), with the five review fixes | `395a9af` |
| The viewer redesign: a built-in sample made by the real system (`tools/make_viewer_sample.py`, 4 tests), side-by-side cards, a review queue | `dcc67c1` |

## In progress

At 14:30 the owner asked the owner's session to finish the remaining team tasks itself. The
traceability matrix, the results page, the demo script and the submission text are on `main`
(see the table above). What is still open:

| What | State at the snapshot |
|---|---|
| The model layers against a real model (`tools/model_check.py`, the model rows of `tools/ablate.py`) | Blocked: there is no OpenRouter key on the owner's machine. The layers stay off, and the scored run uses no model |
| The 2-minute video | Not recorded. The shot list is [demo-script.md](../demo-script.md). It needs a person |
| The submission form | Not sent. The text is in [submission.md](../submission.md); the personal details are the team's to fill in |
| A hosted copy of the viewer | Needs GitHub Pages switched on in the repository settings, which only the repository's owner can do |

**Two draft pull requests from a teammate are open and not merged.** Pull request 4 writes the
scored reason and its evidence from the same grounds. Pull request 5 includes 4, reads the listed
person's date of birth from more of the profile and from every search key, and treats a
superseded document's country and a holiday as weak country evidence. The owner's session
measured 5 with the data at commit `463f981`, at 15:12:

- `python tools/loop.py DATA --baseline <main's output/dev.jsonl>`: `Ran 229 tests`, `0 of 819
  hits changed decision or reason code, 0 moved into DIFFERENT_ENTITY, 35 changed only in reason
  or evidence`, `50 hits, 50 right decisions, 0 unsafe clearances`, the same stress table as
  `main` with `new clearances caused by harder text: none`, and five byte-identical runs.
- All 35 changed reasons are on hits with several possible customers. They now describe each
  candidate.
- The cited evidence equals the reference list on 48 of the 50 practice labels. `main` has 50
  of 50. The two that differ are the labelled hits whose customer is `AMBIGUOUS`: the reference
  cites the identity checks that tie each candidate to the shared country, and the branch cites
  the customer records only.
- The branch was cut before `73ed186`, so it does not have the one-part-name rule, and
  `system/screening/decide.py` will conflict. `python tools/public_test.py --people 30000
  --companies 30000` on the branch prints the same table as on `main` except for that rule:
  `cleared when it should not be: 21`, all 21 in the row for one-part names in another country.

It should not be merged until the evidence equals the reference on 50 of 50 again and
`output/dev.jsonl` has been regenerated on top of the current `main`. Whoever merges it must run
`python tools/loop.py DATA` on the merged code first.

The handoffs were `tasks/teammate-A-viewer.md`, `tasks/teammate-B-data.md` and
`tasks/teammate-C-model-and-demo.md`.

The viewer was redesigned by the owner at 14:20 (decision 11 in [decisions.md](decisions.md)).
Checked in a browser at 1280 and 375 pixels wide, with no console errors:

- On the built-in sample: 14 hits (7 different, 2 same, 5 review) in 12 alerts, and every kind
  of card: date of birth, country, verified name, person against company, timing, death, a
  company, no record found, and two possible customers.
- On the real output: 819 hits (464 different, 125 same, 230 review) in 440 alerts, all 819
  cards drawn without an error, the review queue holding 230 hits in order of evidence,
  `REVIEW` filtering to 230 hits in 163 alerts and `AMBIGUOUS_CUSTOMER_RECORD` to 16.
- A scored file with no explain file, an explain file from another run (it warns), and a file
  with an invalid line (it names the line and shows nothing).

Those checks used a served copy of the page. Opening the file straight from disk has not been
checked since the redesign. A hosted copy needs GitHub Pages switched on in the repository
settings (deploy from `main`, folder `/`); the page would then be at `/viewer/` under the
site's address. Only the owner of the repository can do that.

Teammate B's handoff is finished and merged. The demo was run again at 14:40 on the real public
list, the OpenSanctions export named in [data-sources.md](../data-sources.md) with its SHA-256
checked: 18 demo cases from 6 profiles, and all 18 came out as built. One thing is still
unverified: the clearance audit, which reports 16 of 16 sampled clearances supported, has not
been re-checked row by row.

## The plan for the rest of the day

This is the owner's timeline, set at 11:33. The first working version landed early, at 12:23.

| Time | Work |
|---|---|
| until about 14:30 | Layers, viewer and data jobs, as listed above. Done |
| 14:30 to 15:30 | Measure the model layers. Not done: no API key. Used instead for the stress test on real data, the public-list test and the fixes they led to |
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
