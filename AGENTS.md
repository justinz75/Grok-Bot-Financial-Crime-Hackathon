# Context for AI agents

Read this file first. It is written for any AI coding assistant, and any teammate, picking up
work in this repo with no other context. It says what the project is, which rules you must not
break, where things are, and what to read next.

## What this is

Our team's entry for **Track 2 (sanctions screening)** of the Grok Bot London Financial Crime
Hackathon on Saturday 21 November 2026. The track was designed by Diligent.

A bank's screening system has flagged possible matches ("hits") between its customers and the
people and companies on watchlists. Most hits share a name and nothing else. For every hit the
system answers one question: is this the same entity as our customer?

| Decision | Meaning |
|---|---|
| `DIFFERENT_ENTITY` | A fact contradicts the match. The hit is cleared |
| `SAME_ENTITY` | Name and date of birth agree (name and country for a company) and nothing contradicts |
| `REVIEW` | Anything else. A person decides |

The organisers call `system/run <data folder> <output file>` five times on data we never see.
They score the decisions, the reasons behind them, and whether all five runs agree.

**Deadline: code freeze at 17:00 London time on 21 November 2026. The last commit on `main`
before then is what gets scored.**

## Rules you must not break

Each rule has its reason, so you can judge the cases it does not spell out.

1. **`main` always works.** It is scored exactly as it stands at 17:00. Run the tests before
   every push. Everyone except the repo owner (Justin) works on a branch named `task/<name>` and
   opens a pull request. Never force-push.
2. **Never make clearing easier.** A wrong `DIFFERENT_ENTITY` costs 60 points and a right one
   saves 3, so one bad clearance wipes out twenty good ones. When the evidence is unclear the
   answer is `REVIEW`. Nothing you add may turn a `REVIEW` or a `SAME_ENTITY` into a
   `DIFFERENT_ENTITY`.
3. **The rules decide, and they have one owner.** Do not edit `system/run` or anything under
   `system/screening/` unless the owner gave you that file. If you find a bug, prove it with a
   failing test or a hit ID and report it. One owner keeps one line of reasoning.
4. **`system/` stays standard library, deterministic and offline.** Python 3 standard library
   only, and it must run on Python 3.8. No installed packages, no randomness, no clock and no
   network in the decision path. The same folder must give the same file, byte for byte: 10% of
   the score is run-to-run agreement. A language model may be called only through OpenRouter
   (key in `OPENROUTER_API_KEY`), only inside the optional layers, and those are off by default.
5. **No participant data in git.** This repo is public and the brief forbids committing the
   data. Never commit or paste the data files, the text of the policy or the brief, a real name
   or record from the data, or an API key. Tests and examples use invented names. `data/`,
   `dev/`, `.env` and `*.explain.jsonl` are git-ignored: keep local files there.
6. **Stay in your own files.** Every task names the files it owns. Several people and agents
   work here at once, so touching anything else causes merge conflicts close to the deadline.
7. **Numbers come from commands.** Never invent, round or reuse a figure in a document. Run the
   command and copy what it prints.
8. **Keep the context true.** If your change makes a file under `docs/context/` wrong, fix that
   file in the same pull request.

## Where things are

| Path | What it is | Who changes it |
|---|---|---|
| `system/run` | The entry point the judges call | owner |
| `system/screening/` | The decision logic: load the data, find the customer, find the listed person, compare, decide | owner |
| `system/screening/layers/` | Optional layers on top of the rules: `score`, `briefing`, `reviewer`, `reader` | owner |
| `system/tests/` | Unit tests and whole-run tests. They need no data and every name in them is invented | owner |
| `system/README.md` | The README the brief asks for: architecture, evidence, determinism, three cases, results | owner |
| `output/dev.jsonl` | Our predictions on the development set, required by the brief. It must be what the current code produces | owner |
| `tools/` | Checks that are not part of the scored system: stress test, layer comparison, country check | per task |
| `viewer/` | A static page that displays decisions for the demo. It never decides | Teammate A |
| `docs/` | `explain-format.md`, the background in `context/`, and task outputs | per task |
| `tasks/` | Handoffs and task briefs. The index is `tasks/README.md` | owner |
| `research/` | UI and UX research for the viewer and the video | |
| `data/` | Your local copy of the hackathon data. Git-ignored, never committed | nobody |

## Commands

`ROOM` is your copy of the data room's `screening` folder and `DATA` is `ROOM/dev`. In the
owner's checkout they are `data/room/screening` and `data/room/screening/dev`. The data is not
in this repo: see [docs/context/data.md](docs/context/data.md) for how to get it.

```
python -m unittest discover -s system/tests                        # every test, no data needed
python system/run DATA output/dev.jsonl                            # the scored run, about 6 seconds
python system/run DATA output/dev.jsonl output/dev.explain.jsonl   # also write the explain file
python ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl
python tools/stress.py DATA                                        # reworded-text stress test
python tools/loop.py DATA                                          # every check in order, and which hits a change moved
python tools/ablate.py DATA --stress                               # compare every layer setting
```

On Windows use `py` in place of `python` if `python` opens the Microsoft Store. The results to
expect are in [docs/context/status.md](docs/context/status.md).

## What to do first

1. **You were given a task file** (`tasks/teammate-*.md` or `tasks/NN-*.md`): read
   `tasks/README.md`, then your task file, and follow its steps in order. It says which files you
   may change and how to tell when you are done.
2. **You were not given a task:** do not pick one yourself. Ask the person you are working for
   which task is theirs. [docs/context/status.md](docs/context/status.md) lists what is taken.
3. **You were asked a question about the project:** the answer is probably in one of the files
   below. Say so when it is not, instead of guessing.

## What to read next

| File | Read it when you need |
|---|---|
| [docs/context/hackathon.md](docs/context/hackathon.md) | The deliverable, the scoring, the judges, the schedule, the submission form |
| [docs/context/policy.md](docs/context/policy.md) | The rules that decide a hit, in our own words, and where each lives in the code |
| [docs/context/data.md](docs/context/data.md) | The data files, their fields, how they link, the ID formats and the traps |
| [docs/context/decisions.md](docs/context/decisions.md) | What the team has decided and why. Read it before proposing a change of approach |
| [docs/context/status.md](docs/context/status.md) | What is done, what is in progress, what is open, and the numbers to expect |
| [system/README.md](system/README.md) | How the system works, its layers, its results and its limits |
| [docs/explain-format.md](docs/explain-format.md) | The explain file the layers write and the viewer reads |
| [tasks/README.md](tasks/README.md) | The task list, the rules for every task and the report format |
| [research/ui-ux.md](research/ui-ux.md) | How the viewer and the demo video should look, and what Diligent values |

## Words used here

| Word | Meaning |
|---|---|
| Hit | One watchlist profile that the screening system matched to a customer by name |
| Alert | One customer as screened, with all of that customer's hits. It closes only when every hit is `DIFFERENT_ENTITY` |
| Clearance | A `DIFFERENT_ENTITY` decision. An unsafe clearance is one where the hit really was the customer, or was unclear |
| Scored file | The output file `system/run` writes: one JSON line per hit with seven fields |
| Explain file | An optional second file showing what each layer found. It is never scored |
| Layer | An optional add-on that annotates a decision. In `enforce` mode it may turn a clearance into a review, and nothing else |
| Development set | The data we were given, about 820 hits. It comes without answers |
| Practice labels | The 50 development hits that do come with answers |
| Unseen set | About 550 hits from the same bank that only the organisers have. It decides 80% of the score |
| `DATA`, `ROOM` | Your local data folder (`screening/dev`) and the folder above it |
| Owner | Justin, who owns the repo, the decision logic and `main` |

## When you finish

Report in the format at the end of `tasks/README.md`. Write commit messages as one imperative
sentence that says what changed, like the ones already in `git log`.
