# Task 02: End-to-end tests for rare policy cases

**Goal.** Prove the whole run handles situations the policy covers but the development set barely
shows. The unseen set is said to contain them.

**Read first.** `tasks/README.md`, `system/README.md`, `system/tests/test_rules.py` (for style),
`system/screening/pipeline.py` and `store.py` (for the file layout the run expects).

**You may change.** `system/tests/test_pipeline.py` only (new file).

## Steps

1. Write a helper that creates a temporary data folder with these files, from Python lists of
   dicts: `alerts.jsonl`, `hits.jsonl`, `customers.jsonl`, `accounts.jsonl`, `onboarding.jsonl`,
   `kyc_checks.jsonl`, `notes.jsonl`, `search_results.jsonl`, `name_variants.json`.
   Field names are listed at the end of this file. Every name must be invented.
   IDs must look real: `A-0000A1`, `H-0000A1`, `CUS-000001`, `ACC-0000A1`, `APP-0000A1`,
   `KYC-0000A1`, `NOTE-0000A1`, `SR-0000A1`.
2. For each scenario below build the smallest folder that shows it, call
   `screening.pipeline.run(folder, output_path)`, and assert the decision, the reason code and
   the `customer_record_id` of the hit.
3. Add three checks that apply to every scenario: one output line per hit in `hits.jsonl` order;
   two runs give byte-identical files; every evidence item is an ID present in the folder
   (or `H-xxxxxx#field`).
4. Run `python -m unittest discover -s system/tests`.
5. If a scenario fails, do not change `system/screening/`. Keep the test, mark it
   `@unittest.expectedFailure` with a comment starting `BUG:`, and report it.

## Scenarios and expected results

| # | Situation | Decision | Reason code | customer_record_id |
|---|---|---|---|---|
| 1 | `account_ref`, one holder; verified date of birth 20 years from the hit's | DIFFERENT_ENTITY | DOB_MISMATCH | the holder |
| 2 | Joint account; screened name and date of birth fit the second holder only, who matches the hit | SAME_ENTITY | NAME_DOB_MATCH | the second holder |
| 3 | `login_handle`; record name agrees with the hit, approved check shows a different legal name | DIFFERENT_ENTITY | NAME_MISMATCH_VERIFIED | the record |
| 4 | `email`; name and date of birth agree, same country | SAME_ENTITY | NAME_DOB_MATCH | the record |
| 5 | No link; one record fits name, date of birth and country; hit lists a country no record has | DIFFERENT_ENTITY | LOCATION_MISMATCH | the record |
| 6 | No link; two different people fit; one agrees with the hit, the other is 30 years older | REVIEW | AMBIGUOUS_CUSTOMER_RECORD | `AMBIGUOUS` |
| 7 | No link; two different people fit; both are in a country the hit is not | DIFFERENT_ENTITY | LOCATION_MISMATCH | `AMBIGUOUS` |
| 8 | No link; no record fits | REVIEW | INSUFFICIENT_DATA | `null` |
| 9 | Two records with the same phone and the same full date of birth; only the second lives in the hit's country | not DIFFERENT_ENTITY | not LOCATION_MISMATCH | either record |
| 10 | Two records with the same phone but different dates of birth; only the second lives in the hit's country | DIFFERENT_ENTITY | LOCATION_MISMATCH | the linked record |
| 11 | A rejected check dated after the approved one, with a different date of birth that would clear | not cleared on the rejected date | | the record |
| 12 | The approved check exists only as a note (legal name in capitals, date of birth, country) | per the note's facts | | the record; evidence has the `NOTE-` ID |
| 13 | Company customer; hit company with the same name and country | SAME_ENTITY | NAME_LOCATION_MATCH | the record |
| 14 | Company incorporated in 2021; hit has `According to x.test; March 3, 2015: ...` | DIFFERENT_ENTITY | TEMPORAL_IMPOSSIBILITY | the record |
| 15 | Person customer, company hit | DIFFERENT_ENTITY | ENTITY_TYPE_MISMATCH | the record |
| 16 | Hit `deceased_date` one year before `screened_at` | DIFFERENT_ENTITY | DECEASED | the record |
| 17 | Hit `deceased_date` one year after `screened_at`, name and country agree, no dates of birth | REVIEW | INSUFFICIENT_DATA | the record |
| 18 | Name and date of birth agree; every customer country differs from every hit country | REVIEW | INSUFFICIENT_DATA | the record |
| 19 | Verified name is `UNKNOWN FAROOQ`; hit name shares no part; same country; no dates | REVIEW | INSUFFICIENT_DATA | the record |
| 20 | Hit has no `dobs`; two search results for its name: one a namesake in another country, one with the hit's listing phrase and country, giving an age that clears | DIFFERENT_ENTITY | DOB_MISMATCH | the record; evidence has only the right `SR-` ID |
| 21 | Customer born 2008; hit's earliest dated report is in 2020 | DIFFERENT_ENTITY | TEMPORAL_IMPOSSIBILITY | the record |
| 22 | As scenario 5, plus a support note saying the customer lived in the hit's country | not DIFFERENT_ENTITY | | the record |

The listing phrases are: Sanctions "a sanctioned individual"; PEP "a politically exposed person";
Enforcement "the subject of enforcement action"; Adverse Media "named in adverse media".

## Field names

- `alerts`: `alert_id`, `screened_at`, `customer` {`name`, `entity_type`, `dob`, `country`, `city`}, `account_ref`, `login_handle`, `email`, `hit_ids` (list)
- `hits`: `hit_id`, `alert_id`, `entity_type` (`Individual` or `Company`), `name`, `aliases` (list), `dobs` (list), `place_of_birth`, `deceased_date`, `nationality`, `citizenship`, `countries`, `addresses` (lists), `categories` (list), `primary_category`, `profile_notes`
- `customers`: `record_id`, `entity_type`, `full_name`, `preferred_name`, `login_name`, `dob`, `nationality`, `residence_country`, `city`, `address`, `email`, `phone`
- `accounts`: `account_id`, `customer_id`, `login_handle`, `phone`
- `onboarding`: `account_id`, `customer_id`, `kyc_applicant_id`
- `kyc_checks`: `check_id`, `applicant_id`, `verified_name`, `verified_dob`, `document_type`, `document_number`, `document_country`, `result` (`approved`, `rejected`, `expired`), `checked_at`
- `notes`: `note_id`, `requester_email`, `created_at`, `channel` (`kyc`, `phone`, `email`, `app`), `text`
- `search_results`: `result_id`, `query` (the name's lowercase words in alphabetical order), `title`, `snippet`, `source`
- `name_variants.json`: `{"groups": [["tony", "anthony"]], "company_legal_forms": ["ltd", "gmbh", "sa"]}`

## Done when

- `python -m unittest discover -s system/tests` passes, with expected failures allowed.
- All 22 scenarios have a test whose name contains its number, e.g. `test_06_two_people_disagree`.
- Every expected failure is listed under FINDINGS with its scenario number and the policy principle.
