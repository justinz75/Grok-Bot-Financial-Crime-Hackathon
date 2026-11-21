# Task 01: Audit the clearances

**Goal.** Find any `DIFFERENT_ENTITY` in `output/dev.jsonl` that `POLICY.md` does not support.
Clearing a hit that is the customer costs 60 points; twenty correct clearances earn that back.

**Read first.** `tasks/README.md`, `ROOM/POLICY.md`, `system/README.md`.

**You may change.** Nothing in git. Write your working file to `data/audit/clearances.md` (ignored).

## Steps

1. Produce the output: `python system/run DATA output/dev.jsonl`.
2. Build the sample. Take the lines whose decision is `DIFFERENT_ENTITY`, sort them by `hit_id`
   ascending, and for each of the six reason codes keep the first 8. Skip the hits listed in
   `DATA/practice_labels.jsonl`, which are already checked. Write the list of sampled IDs down
   before looking at any of them.
3. For each sampled hit, work through this checklist using the data files and the policy only.
   Do not read the system's reason until step 3g.
   - a. **Alert.** Which link does it carry: `account_ref`, `login_handle`, `email`, or none?
   - b. **Customer.** Resolve them by principles 2 and 3. Follow the link; on a joint account let
     the screened name and date of birth pick the holder; with no link, list the records that fit
     the screened name, date of birth, country and city. Add records that share a phone number and
     the same full date of birth, or a document number on approved checks. Write the record IDs.
   - c. **Verified facts.** Find the person's most recent *approved* identity check: a row in
     `kyc_checks` reached through `onboarding`, or a check written up in `notes`. Write its ID,
     legal name, date of birth and document country. Ignore rejected and expired checks.
   - d. **Customer countries.** Residence and nationality on every record, the approved
     document's country, and countries the notes say they lived in.
   - e. **Hit facts.** Names and aliases; date of birth from `dobs`, else the opening line of
     `profile_notes`, else a search result that describes the same kind of listing in a country
     tied to the hit; countries; the earliest line of the form `According to ...; Month D, YYYY:`;
     `deceased_date`.
   - f. **Policy.** Go through the five bullets of principle 6 in order: time, date of birth,
     location, name, type. Write which one holds, with the two values that contradict.
   - g. **Compare.** Now read the system's line. Give one verdict:
     `SUPPORTED` (a contradiction holds and the system named one that holds),
     `WRONG CODE` (a contradiction holds but not the one named),
     `NOT SUPPORTED` (you find no contradiction), or
     `UNSURE` (the policy text does not settle it; say which sentence).
4. Also check each sampled reason: it has two to four sentences and states the decisive values.
   Note any that do not as `REASON TEXT`.

## Output

`data/audit/clearances.md`, one row per hit:

| hit_id | code | customer records | decisive facts with record IDs | principle | verdict | note |

## Done when

- Every sampled hit has exactly one verdict from the list above.
- Every `NOT SUPPORTED`, `WRONG CODE` and `UNSURE` appears under FINDINGS in your report with its
  hit ID, the policy principle, and the record IDs that show it.

Do not fix anything. A `NOT SUPPORTED` finding is the most valuable thing this task can produce.
