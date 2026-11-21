# Teammate B: more data

Three small jobs, in priority order. Do them one at a time and report after each.
The scored system may read only the hackathon data folder, so none of this goes into `system/`.

**You need:** this repo, Python 3, and your copy of the hackathon data. Below, `DATA` means your
`screening/dev` folder and `ROOM` the `screening` folder above it.

## Rules

- Never commit hackathon data or downloaded lists. Save downloads under `data/public/`, which git ignores.
- Do not change anything under `system/`.
- Work on a branch called `task/data` and open a pull request to `main`.

---

## Job 1: check our country table against the official list (10 minutes)

The system turns country names and codes into one code. That table was typed by hand.

1. Download a CSV of the ISO 3166 country codes that has columns for the name, the two-letter
   code and the three-letter code. Save it as `data/public/iso3166.csv`.
2. Run: `python tools/check_countries.py data/public/iso3166.csv`
3. Copy the full output into your report. Do not fix anything yourself.

**Done when** the tool has run and its output is in your report.

---

## Job 2: more checked answers (45 minutes)

Only 50 hits come with answers. Every clearance you check by hand is one more.

1. Run: `python system/run DATA output/dev.jsonl`
2. Open `tasks/01-audit-clearances.md` and follow it, with one change: keep the first **3** hits
   per reason code instead of 8. That is at most 18 hits.
3. Write the table to `data/audit/clearances.md` (git ignores it).
4. Ask a Diligent mentor at office hours (15:00) whether more practice labels exist. Write down the answer.

**Done when** every sampled hit has one verdict, and every verdict other than `SUPPORTED` is in
your report with the hit ID and the policy principle.

---

## Job 3: a demo on real public lists (45 minutes)

Show the system working on real government list entries, with invented customers.

1. Download the consolidated sanctions list from OpenSanctions as a CSV (the "targets.simple.csv"
   file of the "sanctions" collection, found from https://www.opensanctions.org/datasets/sanctions/).
   Save it as `data/public/sanctions.csv`. It is free for non-commercial use (CC BY-NC 4.0).
2. Write `docs/data-sources.md` with one row per file you downloaded: what it is, the page you got
   it from, its licence, the date, the number of rows, and its column names.
3. Write `tools/make_public_demo.py`. It reads `data/public/sanctions.csv` and writes a data folder
   `data/public_demo/` in the same layout as `DATA` (file and field names are listed at the end of
   `tasks/02-rare-case-tests.md`). Standard library only. It must:
   - sort the rows whose `schema` is `Person` and that have a `birth_date` and a `countries` value
     by `id`, and take the first 6. Using a fixed rule means everyone gets the same 6;
   - write one hit per person: `name`, `aliases` (split on `;`), `dobs` (split on `;`),
     `countries` (split on `;`, in capitals), `entity_type` `Individual`, `categories` `["Sanctions"]`;
   - for each person write three invented customers, each with its own alert and account:
     - **a** same name, same date of birth, same country;
     - **b** same name, date of birth 20 years later, same country;
     - **c** same name, no date of birth, same country;
   - give each customer an approved row in `kyc_checks` (linked through `accounts` and
     `onboarding`) with the same name and date of birth, and link each alert by `account_ref`;
   - copy `DATA/name_variants.json` into the folder;
   - use IDs in the real formats: `A-0000A1`, `H-0000A1`, `CUS-000001`, `ACC-0000A1`, `APP-0000A1`, `KYC-0000A1`.
4. Run: `python tools/make_public_demo.py` then
   `python system/run data/public_demo output/public_demo.jsonl`
5. Check the 18 lines. Expected: every **a** customer is `SAME_ENTITY`, every **b** is
   `DIFFERENT_ENTITY` with `DOB_MISMATCH`, every **c** is `REVIEW` with `INSUFFICIENT_DATA`.
   Report any line that differs, with its reason text. Do not change `system/` to make it pass.
6. Do not commit `output/public_demo.jsonl`: it names real listed people.

**Done when** the script runs from a clean checkout and you have reported the 18 results.

---

## Prompt to paste into your AI assistant

> Read `tasks/teammate-B-data.md` in this repo. Do Job <1, 2 or 3> exactly as written. Do not
> change any file under `system/`. Do not commit anything under `data/` or any downloaded file.
> Stop and tell me if a step fails instead of working around it.

## Report back, after each job

```
TASK: B data, job <n>
STATUS: DONE | PARTIAL | BLOCKED
CHANGED: <files, or "none">
RESULT: <the tool output, the verdict counts, or the 18 decisions>
FINDINGS: <numbered, each with a hit ID or a country>
OPEN QUESTIONS: <or "none">
```
