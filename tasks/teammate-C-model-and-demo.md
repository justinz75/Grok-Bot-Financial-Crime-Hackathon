# Teammate C: the model check, the results table and the demo

The system decides with rules. Three optional layers sit on top, and two of them use a language
model. Your job is to find out, with numbers, whether the model layers help and whether they give
the same answer every time. Then you write the demo.

**You need:** this repo, Python 3, your copy of the hackathon data, and an OpenRouter account.
Below, `DATA` means your `screening/dev` folder and `ROOM` the `screening` folder above it.

## Rules

- Never commit an API key. Never paste it into a file in the repo, a chat or a screenshot.
- Do not change anything under `system/`. If a tool fails, report the error.
- Work on a branch called `task/results` and open a pull request to `main`.

---

## Job 1: get a key (10 minutes)

1. Create an account at openrouter.ai and make an API key. Add a few dollars of credit.
2. Put the key in your shell for this session only.
   PowerShell: `$env:OPENROUTER_API_KEY = "paste-it-here"`
   bash or zsh: `export OPENROUTER_API_KEY="paste-it-here"`
3. Tell Justin you have a key. Do not send him the key.

**Done when** `python -c "import os; print(bool(os.environ.get('OPENROUTER_API_KEY')))"` prints `True`.

---

## Job 2: pick a model that answers the same way twice (20 minutes)

`tools/model_check.py` is on `main` now: pull first. The system's default model ID is
`openai/gpt-4o-mini`; nobody has confirmed OpenRouter still offers it, so check the model list on
openrouter.ai and pick three IDs that exist.

1. Run it for three small, cheap models, one at a time:
   `python tools/model_check.py <model id>`
   It asks the same question five times and prints whether the five answers were identical, and
   how long each took.
2. Keep the cheapest model whose five answers were identical. If none was identical, keep the one
   with the fewest different answers and say so.

**Done when** you can name one model ID and its result.

---

## Job 3: the results table (30 minutes)

`tools/ablate.py` is on `main` now.

1. Run: `python tools/ablate.py DATA --runs 5 --stress --model <the model ID from job 2>`
   It runs the system with each layer off and on and prints one row per setting, first on the
   data as given and then on a copy whose identity notes have lost their capitals. With a key
   set, this sends note text and customer and hit facts to OpenRouter, which the brief allows.
   Expect a few minutes and a small cost.
2. Copy the whole table into `docs/results.md`, under a heading with the date, the time and the
   model ID. Add nothing and change no number.
3. Under the table write three plain sentences:
   - which settings changed any decision compared with rules only, and how many;
   - which settings gave a different answer between runs, and on how many hits;
   - which settings created a new clearance. This should be none. If it is not none, tell Justin at once.

**Done when** `docs/results.md` holds the table and the three sentences.

---

## Job 4: demo script and submission text (40 minutes)

Follow `tasks/06-demo-and-submission.md` exactly. Use only numbers that a command printed for you.
Then record the 2-minute video from the script and upload it somewhere with a public link.

**Done when** `docs/demo-script.md` and `docs/submission.md` exist and you have a video link.

---

## Prompt to paste into your AI assistant

> Read `tasks/teammate-C-model-and-demo.md` in this repo. Do Job <n> exactly as written. Run the
> commands and show me their output. Do not change any file under `system/`. Do not write the API
> key into any file. Do not change, round or invent any number: copy what the commands print.

## Report back, after each job

```
TASK: C results, job <n>
STATUS: DONE | PARTIAL | BLOCKED
CHANGED: <files, or "none">
RESULT: <the command output, the model ID, or the link>
OPEN QUESTIONS: <or "none">
```
