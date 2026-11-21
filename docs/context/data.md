# The data: files, fields, links and traps

The hackathon data is **not in this repo and must never be**. The brief forbids committing it
and the repo is public. This page describes its shape so that code and tests can be written
without it. It contains no records.

## Getting it and where to put it

The data room is shared through the event's participant access. Ask Justin or a teammate for
the link. It is left out of this page on purpose.

Unpack it under `data/`, which git ignores. Two names are used everywhere:

| Name | What it is | In the owner's checkout |
|---|---|---|
| `ROOM` | The data room's `screening` folder | `data/room/screening` |
| `DATA` | The development set, `ROOM/dev` | `data/room/screening/dev` |

`system/run` also accepts `ROOM`: it looks for a `dev` folder inside the folder it is given.

## What the data room holds

| File | What it is |
|---|---|
| `ROOM/README.md` | The organisers' full brief: deliverable, scoring, judging |
| `ROOM/POLICY.md` | The bank's identity procedure. The authority on every decision |
| `ROOM/validate.py` | Checks an output file the way the organisers do, and scores the practice labels |
| `ROOM/output.schema.json` | The formal shape of one output line |
| `ROOM/screening-dev-browse.xlsx` | The development set as a spreadsheet, for browsing by eye only |
| `ROOM/dev/` | The development set: the files below |

There are three sets of hits:

- **Development set:** what we were given. 440 alerts with 819 hits. No answers.
- **Practice labels:** 50 of those hits, with answers: 28 different, 12 same, 10 review.
- **Unseen set:** about 550 hits from the same bank, held by the organisers, in the same file
  format with new customers, new hits and differently worded free text.

## The files in `DATA`

Every `.jsonl` file is JSON Lines: one JSON object per line. Row counts are for the development set.

| File | Rows | One row is | Key |
|---|---|---|---|
| `alerts.jsonl` | 440 | A customer as screened, with a link if there is one, and the IDs of the hits | `alert_id` |
| `hits.jsonl` | 819 | One watchlist profile matched to that customer. **We decide each of these** | `hit_id` |
| `customers.jsonl` | 72,265 | A customer record in the bank's system of record | `record_id` |
| `accounts.jsonl` | 86,659 | An account holder: one account, one customer, a login and a phone | `account_id` |
| `onboarding.jsonl` | 72,265 | The link from a customer and account to a KYC applicant | `kyc_applicant_id` |
| `kyc_checks.jsonl` | 54,488 | One identity check by the KYC provider | `check_id` |
| `notes.jsonl` | 31,895 | A support or onboarding note, filed by email address | `note_id` |
| `search_results.jsonl` | 16,882 | One web search result for a name | `result_id` |
| `name_variants.json` | | 55 groups of name forms that count as the same, and 30 company legal forms | |
| `practice_labels.jsonl` | 50 | An answered hit, with the path through the files to the answer | `hit_id` |
| `POLICY.md` | | A copy of the policy | |

## How the files link

The bank's systems do not share one key. Each arrow is one hop.

```
alerts.hit_ids       -> hits.hit_id              (hits.alert_id points back)

alerts.account_ref   -> accounts.account_id   -> accounts.customer_id -> customers.record_id
alerts.login_handle  -> accounts.login_handle -> accounts.customer_id -> customers.record_id
alerts.email         -> customers.email
(no link at all)     -> search customers by the screened name, date of birth, country and city

customers.record_id  -> onboarding.customer_id -> onboarding.kyc_applicant_id -> kyc_checks.applicant_id
customers.email      -> notes.requester_email
hits.name            -> search_results.query
```

- An alert carries at most one link. In the development set 170 alerts have an account
  reference, 70 a login handle, 54 an email and **146 none at all**.
- One `account_id` can have two rows in `accounts.jsonl`. That is a joint account with two holders.
- `search_results.query` is the name's lowercase words in alphabetical order.

`system/screening/store.py` builds one index per hop.

## Fields

Fields the system reads are in **bold**. The rest are listed so nobody is surprised by them.

- **alerts:** **`alert_id`**, **`screened_at`**, **`customer`** (an object: **`name`**,
  **`entity_type`**, **`dob`**, **`country`**, **`city`**), **`account_ref`**, **`login_handle`**,
  **`email`**, **`hit_ids`** (a list).
- **hits:** **`hit_id`**, **`alert_id`**, **`entity_type`** (`Individual` or `Company`),
  **`name`**, **`best_matching_name`**, **`aliases`** (list), **`dobs`** (list),
  **`place_of_birth`**, **`deceased_date`**, **`nationality`**, **`citizenship`**,
  **`countries`**, **`addresses`** (lists), **`categories`** (list), **`primary_category`**,
  **`profile_notes`**. Also present: `match_score`, `first_name`, `middle_name`, `last_name`,
  `gender`, `life_status`, `identifiers`, `subcategories`, `position_or_allegation`, `details`,
  `relationships`, `sources`, `source_urls`.
- **customers:** **`record_id`**, **`entity_type`**, **`full_name`**, **`preferred_name`**,
  **`login_name`**, **`dob`**, **`nationality`**, **`residence_country`**, **`city`**,
  **`address`**, **`email`**, **`phone`**. Also present: `occupation`, `employer`,
  `registration_number`, `onboarded_at`, `status`, `last_kyc_refresh`.
- **accounts:** **`account_id`**, **`customer_id`**, **`login_handle`**, **`phone`**. Also
  present: `opened_at`, `status`.
- **onboarding:** `account_id`, **`customer_id`**, **`kyc_applicant_id`**. Also present: `onboarded_at`.
- **kyc_checks:** **`check_id`**, **`applicant_id`**, **`verified_name`**, **`verified_dob`**,
  `document_type`, **`document_number`**, **`document_country`**, **`result`** (`approved`,
  `rejected` or `expired`), **`checked_at`**. Also present: `provider`.
- **notes:** **`note_id`**, **`requester_email`**, **`created_at`**, **`channel`** (`kyc`,
  `phone`, `email` or `app`), **`text`**.
- **search_results:** **`result_id`**, **`query`**, `title`, **`snippet`**, `source`.
- **name_variants.json:** `groups` (lists of name forms that count as the same),
  `company_legal_forms` (a list), and a `description`.
- **practice_labels:** `hit_id`, `alert_id`, `decision`, `reason_codes` (every accepted code),
  `customer_record_ids` (every accepted record), `evidence` (the reference list),
  `reference_reason`, `path` (the steps through the files).

## ID formats

| Record | Looks like |
|---|---|
| Alert | `A-0000A1`: six characters, digits or capitals A to F |
| Hit | `H-0000A1`: the same |
| Customer record | `CUS-000001`: six digits |
| Account, KYC applicant, KYC check, note, search result | `ACC-0000A1`, `APP-0000A1`, `KYC-0000A1`, `NOTE-0000A1`, `SR-0000A1` |

An `evidence` item must be an ID that exists in the data folder, or a hit's own field written
`H-0000A1#deceased_date`, or a web address. `validate.py` rejects anything else.

Use IDs in these formats when you invent test data, and never reuse a real one.

## Traps we already found

1. **A third of alerts carry no link** (146 of 440). The customer has to be found by searching.
2. **Most hits have no date of birth in the field** (only 152 of 819 do). The rest need the
   profile notes or the search results, and many have none anywhere.
3. **Many hits have no primary category** (345 of 819). The first category is used instead.
4. **Dates come in several formats, and many are partial**: a year alone, or a year and month.
   Use `dates.parse_date`. A partial date is never padded.
5. **Countries appear as names, as codes and as nationalities.** Use `countries.resolve`.
6. **Numbers in a profile are usually not ages.** A count of people or of years in a sentence
   about an offence was once read as an age, which would have produced wrong clearances. Only a
   genuine birth sentence counts.
7. **Identity checks written as notes** are in the `kyc` channel (22,575 notes). In the
   development set every one prints the legal name in capitals, and the reader relies on that.
   If the unseen set does not, those customers fall back to review. They are never cleared on a guess.
8. **Rejected and expired checks sit beside approved ones** (2,481 and 2,433 against 49,574).
   They are not evidence.
9. **Relatives share phones and addresses.** Only a phone with the same full date of birth, or a
   shared document number on approved checks, makes two records one person.
10. **`customers.login_name` is empty in every development record.** The policy still names it,
    so the code compares it when it is there.
11. **The practice labels cover only 8 of the 11 reason codes.** None is `DECEASED`,
    `ENTITY_TYPE_MISMATCH` or `AMBIGUOUS_CUSTOMER_RECORD`, and one is `TEMPORAL_IMPOSSIBILITY`.
    Those paths are checked by `system/tests/test_pipeline.py` instead.
12. **Some hits cannot be scored**, because their answer depends on information that is not in
    the files. They still need a line.
13. **The spreadsheet is for browsing only.** It cuts long text short. The system reads the
    JSON Lines files.
14. **The public event page quotes smaller row counts** than the data room has. The data room is right.

## Checking an output file

```
python ROOM/validate.py --data DATA --output output/dev.jsonl
python ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl
```

It reports a problem for: a line that is not JSON, an unknown or repeated `hit_id`, an
`alert_id` that is not the hit's, a reason code that does not belong to the decision, a
`customer_record_id` that is not in `customers.jsonl`, an empty reason, and an evidence item that
does not exist in the folder. A hit with no line counts as `REVIEW`. With `--score` it prints the
right decisions, the unsafe clearances and the decision score on the practice labels.

## Handling rules

- Never commit anything from the data room, and never paste a record into a public place.
- Tests and examples use invented names and invented IDs.
- `output/dev.jsonl` is committed on purpose: the brief requires it. Its reasons name hits by
  design.
- The explain file carries far more of each record than the scored file, so `*.explain.jsonl`
  is git-ignored. Only the invented samples in `viewer/sample/` are committed.
- Keep other local files under `data/` too: downloads of public lists in `data/public/`, audit
  notes in `data/audit/`.
