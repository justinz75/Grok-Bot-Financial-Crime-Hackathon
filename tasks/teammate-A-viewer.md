# Teammate A: the review viewer (UI)

You are building one web page that shows what the system decided and why. It only displays.
It never decides, never calls a model and never sends data anywhere.

**Time:** about 90 minutes. **You need:** a browser and this repo. You do not need the real data.

## Rules

- Change files under `viewer/` only. Do not touch `system/`, `tools/`, `output/` or `tasks/`.
- One file: `viewer/index.html`, with its CSS and JavaScript inside it. No build step, no
  libraries, no links to the internet. It must work when opened from disk with no connection.
- Never put real data in the repo. `viewer/sample/` already holds invented sample files to build with.
- Work on a branch called `task/viewer` and open a pull request to `main`.

## What the page reads

The user picks two files with file inputs (a page opened from disk cannot fetch files itself):

1. **The scored file** (required). One JSON object per line with `hit_id`, `alert_id`, `decision`,
   `reason_code`, `customer_record_id`, `reason`, `evidence`.
2. **The explain file** (optional). One JSON object per line, same order. Its fields are described
   in `docs/explain-format.md`. Read that file before you start.

Sample files: `viewer/sample/dev.jsonl` and `viewer/sample/dev.explain.jsonl` (5 invented hits).

## What the page shows

Build it in this order. Each step should work before you start the next.

1. **File pickers and summary bar.** After the scored file is loaded show: total hits, and the
   count of `DIFFERENT_ENTITY`, `SAME_ENTITY` and `REVIEW`.
2. **Alert list.** Group hits by `alert_id`, alerts sorted by ID, hits sorted by ID inside each.
   Mark an alert **Closed** only if every hit in it is `DIFFERENT_ENTITY`; otherwise **Open**.
3. **Hit card.** For each hit show, top to bottom:
   - a pill with the decision: `DIFFERENT_ENTITY` reads "Different · cleared", `SAME_ENTITY` reads
     "Same · to compliance", `REVIEW` reads "Needs a person";
   - the `reason_code`;
   - the `reason`, one sentence per line;
   - `customer_record_id` (show "none found" for null);
   - each item of `evidence` as a small chip in a monospace font.
4. **Filters.** A decision filter, a reason-code filter, and a search box for an alert or hit ID.
5. **Explain panel** (only when the explain file is loaded). For the hit's first entry in `people`:
   - two columns, "Our customer" and "List entry", with rows Name, Date of birth, Countries.
     Customer name is `verified_name` if present, else the first of `names`. Put a tag beside each
     row from `states`: `agree` reads "Agrees", `mismatch` reads "Differs", `unknown` reads "Unknown";
   - **Strength of evidence** from `score`: the `band` text, then one bar per item in
     `contributions`. Bars for positive `bits` go right, negative go left. Show `detail` beside each.
     If `conflict` is true show a note: "Cleared by policy, but the evidence leans the other way";
   - **Briefing** from `briefing`: `headline` as a heading, then the lists `decided_by`, `missing`,
     `would_settle` and `caveats`, each under its own label. Hide a list that is empty;
   - **Second opinion** from `review`: the verdict, the reason, and "agreed in N of M runs";
   - if `changed_by` is not null, a banner: "Changed to review by the <layer> layer: <why>";
   - if `people` has more than one entry, tabs "Person 1", "Person 2" to switch between them.
   Any of `score`, `briefing`, `review` can be null. Then leave that section out.
6. **Look.** Follow `research/ui-ux.md`: dark background `#0A0A0A`, light text `#EDEDED`, accent
   `#CC5533`, IDs in a monospace font. Make it readable at a laptop width.

## Prompt to paste into your AI assistant

> Read `tasks/teammate-A-viewer.md` and `docs/explain-format.md` in this repo, then build
> `viewer/index.html` exactly as specified, as one self-contained file with no external
> libraries or network requests. Use the files in `viewer/sample/` to test. Build the six steps in
> order and stop after each one so I can check it in the browser. Do not change any file outside
> `viewer/`.

## Checks before you say it is done

Open `viewer/index.html` from disk and load the two sample files. All of these must be true:

- The summary shows 5 hits: 2 different, 1 same, 2 review.
- Alert `A-0000A1` has two hits and is marked Closed. The other three alerts are Open.
- Hit `H-0000A5` shows the note about the evidence leaning the other way.
- Hit `H-0000A4` has two person tabs, and shows no score, briefing or second opinion.
- Hit `H-0000A3` shows two items under "missing" and one under "would settle".
- Filtering to `REVIEW` leaves 2 hits.
- With only the scored file loaded, the page still works and shows no explain panel.
- The browser's network panel shows no requests after the page has loaded.
- `git status` lists files under `viewer/` only.

With the real output (ask Justin for `output/dev.jsonl`, it is in the repo) the summary must read
819 hits: 464 different, 125 same, 230 review.

## Report back

```
TASK: A viewer
STATUS: DONE | PARTIAL | BLOCKED
CHANGED: <files>
CHECKS: <which of the checks above pass>
OPEN QUESTIONS: <or "none">
```
