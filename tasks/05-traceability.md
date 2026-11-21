# Task 05: Policy-to-code traceability matrix

**Goal.** One table showing that every rule in the policy has one place in the code and at least
one test. This is the evidence that the system follows the same line of reasoning every time.

**Read first.** `tasks/README.md`, `ROOM/POLICY.md`, every file in `system/screening/`, both test
files in `system/tests/`.

**You may change.** `docs/traceability.md` only (new file).

## Steps

1. List the rules to trace, in this fixed order:
   - Principles 1 to 9 of the policy. Split principle 6 into its five bullets (time, date of
     birth, location, name, type) and principle 8 into its clauses (what is ignored; initials;
     variants; written together or apart; edit limits; when names agree; placeholders; legal forms).
   - The eleven reason codes in `ROOM/output.schema.json`.
2. For each rule, find the function that implements it. Confirm it exists with a search, and
   record `file` and function name. If a rule is implemented in more than one place, list each.
3. For each rule, find the tests that exercise it and record their names. Confirm each name exists.
4. Give each rule one status: `COVERED` (code and test), `CODE ONLY` (no test), or `MISSING`
   (no code found).
5. Describe each rule in your own words in at most 15 words. Do not paste policy text: the
   policy file is part of the participant-only data.
6. Under the table, list every `CODE ONLY` and `MISSING` row again as a short gap list.

## Output

`docs/traceability.md`:

| # | Rule (own words) | Code | Tests | Status |

## Done when

- The table has a row for each principle, each bullet of principle 6, each clause of principle 8
  and each of the eleven reason codes.
- Every function and test named in the table is found by a search of the repo.
- The gap list matches the statuses in the table.
- `git status` shows `docs/traceability.md` only.
