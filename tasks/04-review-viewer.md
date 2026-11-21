# Task 04: Review viewer for the demo

**Goal.** A page an analyst (and a judge watching a 2-minute video) can use to see what the system
decided and why. It displays; it never decides.

**Read first.** `tasks/README.md`, `research/ui-ux.md`, `system/README.md`,
`ROOM/output.schema.json`.

**You may change.** Files under `viewer/` only.

## Rules specific to this task

- One static page that opens from disk (`viewer/index.html`), with no build step and no network
  requests. It must work offline.
- No data in the repo. The user picks files with a file input: `output/dev.jsonl` always, and
  optionally the data folder's `alerts.jsonl`, `hits.jsonl`, `customers.jsonl`, `kyc_checks.jsonl`,
  `notes.jsonl`, `search_results.jsonl`. Nothing is uploaded anywhere.
- No model calls and nothing random. The same files always give the same screen.
- The viewer shows the system's own `reason` and `evidence`. It must not rewrite, summarise or
  re-derive a decision.

## Steps

1. Load and parse `output/dev.jsonl`. Show a summary bar: number of hits, and how many are
   `DIFFERENT_ENTITY`, `SAME_ENTITY` and `REVIEW`.
2. List alerts in `alert_id` order, each with its hits in `hit_id` order. An alert is shown as
   closed only when every hit in it is `DIFFERENT_ENTITY`; otherwise open.
3. Each hit card shows, in this order: the decision as one pill (wording below), the reason code,
   the reason text split into its sentences, the `customer_record_id`, and each evidence ID as a chip.
   - `DIFFERENT_ENTITY` reads "Different · cleared"
   - `SAME_ENTITY` reads "Same · to compliance"
   - `REVIEW` reads "Needs a person"
4. Add filters for decision and reason code, and a search box for an alert or hit ID.
5. When data files are loaded, clicking an evidence chip shows that record's fields, and the card
   gains a two-column comparison, "Our customer" and "List entry": name, date of birth, countries.
   Fill the customer column only from the records named in `evidence` and `customer_record_id`.
6. Follow the look in `research/ui-ux.md`. IDs in a monospace font.

## Done when

- Opening `viewer/index.html` from disk and choosing `output/dev.jsonl` shows 819 hits:
  464 different, 125 same, 230 review.
- Filtering to `REVIEW` shows 230 hits; filtering to `AMBIGUOUS_CUSTOMER_RECORD` shows 16.
- The browser's network panel shows no requests after the page loads.
- `git status` shows changes under `viewer/` only, and no data file.
