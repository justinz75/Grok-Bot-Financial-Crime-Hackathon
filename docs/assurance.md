# Assurance: what a bank puts around automated clearing

The scored system answers one question for each hit. A bank that lets software clear alerts is
expected to show more than the answers: how the open work is ordered, who checks the clearances,
how the name matching behaves on spellings it has not seen, and exactly what produced each
answer. This page says which of those the industry has, which we had, and what
`tools/assure.py` now adds.

```
python tools/assure.py DATA                  # about 13 seconds; files go to data/assurance/, which git ignores
python -m unittest discover -s tools/tests   # 28 tests, every name invented
```

The tool reads what the system writes and decides nothing. No hit changes its decision and the
scored file is never touched. It uses no model, no randomness and no clock: two runs on the same
folder write the same five files, byte for byte.

## What the industry has, and where we stood

The middle column is the state of `main` at commit `f5f66de`, before this tool.

| What a bank's screening function has | What we had | What the tool adds |
|---|---|---|
| **A decision for the alert, not only the hit.** Case tools work alerts. An alert closes only when every hit in it is cleared | The viewer counts alerts as closed, waiting for a person or with compliance, on screen. No file says which alert is which | `alerts.csv`: every alert as `CLOSED`, `REVIEW` or `ESCALATE` |
| **Work ordered by risk.** A sanctions hit is worked before an adverse-media hit, and a likely match before an open one | The viewer orders its review queue by the strength-of-evidence score. It cannot see what kind of listing a hit is, and matches are not in the queue | `review_queue.csv`: every review and match with a priority from P1 to P4, sanctions listings first |
| **A second person on automated clearances.** Four-eyes checks, and quality sampling of what the first line closed | Task 01, a hand audit of 16 clearances | `qa_sample.csv`: every clearance that carries a risk flag, plus a fixed share of the rest |
| **A challenger to the matcher.** Model risk practice compares the model in use with a second one | The model reviewer layer, which is off and unmeasured | A looser name matcher that marks the name clearances it would not have made |
| **Tests of the name matching with made-up variations.** Swapped letters, dropped letters, initials, name order | `tools/stress.py` rewords free text. Nothing ran the name rule over the listed names | Fourteen variations of every listed name, and how often the policy's rule still agrees |
| **Numbers on why work is manual.** Management information on what causes reviews | The briefing says it for one hit at a time | The one missing fact behind each review, counted |
| **Lineage.** Which data and which code produced a decision | `tools/repro.py` prints the hash of the output | `manifest.json`: SHA-256 of every input file, of the deciding code and of the output |
| **Checks on the data itself.** Identifiers, dates that cannot be right | The rule that unknown stays unknown | Counts of what the listings hold that the policy does not use |

These expectations are set out in, among others, the Wolfsberg Group's guidance on sanctions
screening (testing the screening tool, data integrity, alert handling, management information),
the New York DFS rule on transaction monitoring and filtering programs (testing the matching
logic and the data going in and out), and the US supervisory guidance on model risk management
(independent challenge and comparison with another model). They are named here from memory of
what they cover. Read the source before quoting one to a judge.

## What one run shows on the development set

Every figure below was printed by `python tools/assure.py DATA` on the development set, with
the code of commit `f5f66de`. The scored file it reports has the SHA-256
`c23adcc75543dca9c8534cfe3b613edfa28a0e4921856885596c610dd9e97bc1`, the same hash
`tools/repro.py` gives for that commit.

### 1. Alerts

440 alerts hold 819 hits. 464 of the 819 hits are cleared (56.7%).

| Alert | Count | Share | Meaning |
|---|---|---|---|
| `CLOSED` | 175 | 39.8% | Every hit is a different entity. Nobody has to open it |
| `REVIEW` | 157 | 35.7% | A person has to look |
| `ESCALATE` | 108 | 24.5% | A hit is the customer. The alert goes to compliance |

The hit clearance rate overstates the saving. One open hit keeps the whole alert open, so
39.8% of alerts close, against 56.7% of hits.

### 2. The order of work

355 hits need a person: 230 reviews and 125 matches. The priority crosses two questions: what a
wrong answer would cost (is any category of the hit a sanctions listing), and how likely the hit
is the customer (a match, or the score layer's top band, `strong evidence of the same`).

| Priority | Hits | Matches | Reviews | Meaning |
|---|---|---|---|---|
| P1 | 25 | 25 | 0 | Sanctions listing: a match, or strong evidence of the same |
| P2 | 109 | 100 | 9 | Sanctions listing still open, or a match on another listing |
| P3 | 4 | 0 | 4 | Another listing, strong evidence of the same |
| P4 | 217 | 0 | 217 | Another listing, open |

Inside a priority, matches come first, then the hits with the most bits towards the same person.

**This does not touch a decision.** Policy principle 1 keeps the seriousness of a listing out of
the identity decision, and it stays out. The priority only says which open hit an analyst reads
first. Which listings count as serious is the bank's choice; the tool uses one line, sanctions
or not.

### 3. The clearances a second person reads

A wrong clearance is the costly mistake, so the clearances are the ones to check. Every
clearance that carries a risk flag is read. Of the rest, 10% per reason code are read, and never
fewer than 5. The sample is the hits whose ID has the lowest SHA-256, so it is the same on every
run and cannot be predicted from the hit.

| Reason code | Cleared | Flagged | Sampled | Read |
|---|---|---|---|---|
| `DECEASED` | 4 | 0 | 4 | 4 |
| `DOB_MISMATCH` | 95 | 57 | 5 | 62 |
| `ENTITY_TYPE_MISMATCH` | 1 | 0 | 1 | 1 |
| `LOCATION_MISMATCH` | 264 | 13 | 26 | 39 |
| `NAME_MISMATCH_VERIFIED` | 79 | 3 | 8 | 11 |
| `TEMPORAL_IMPOSSIBILITY` | 21 | 0 | 5 | 5 |
| All | 464 | 73 | 49 | 122 |

122 of the 464 clearances are read: 26.3%.

| Flag | Clearances | A clearance gets it when |
|---|---|---|
| `score_conflict` | 0 | The strength-of-evidence score leans towards the same person |
| `name_near_miss` | 1 | Name is the only ground, and the looser matcher would call the names the same |
| `narrow_date_gap` | 30 | Date of birth is the only ground, and the years are at most 3 apart |
| `inferred_hit_date` | 43 | Date of birth is the only ground, and the hit's date was read from notes or a search result |
| `declared_date_only` | 0 | Date of birth is the only ground, and the customer's date is declared, not verified |
| `sanctions_one_ground` | 23 | A sanctions listing was cleared on a single ground |
| `several_people` | 9 | More than one customer fits the alert |

One clearance can carry several flags, so the flags add up to more than the 73 flagged hits.

**The looser matcher** is the policy's name rule with three allowances a screening engine
usually makes: two neighbouring letters that change places count as one edit, a part of five
letters or more gets one more edit, and a short form matches the name it begins. It never
decides. It marks the one name clearance on the development set that a looser matcher would
not have made, so a person can read it.

### 4. What keeps a review open

Each of the 230 reviews is counted once, under the first question it fails.

| Reviews | Share | What keeps it open |
|---|---|---|
| 187 | 81.3% | The listing gives no date of birth |
| 16 | 7.0% | Several customers fit and they lead to different decisions |
| 12 | 5.2% | Name and date agree but no country is shared |
| 9 | 3.9% | The name cannot be confirmed against the listing |
| 6 | 2.6% | The dates of birth neither agree nor contradict |

Four reviews in five wait for one fact: the listed person's date of birth. That is where a bank
would spend to cut the manual work, by buying a richer list or by reading more sources.

### 5. The name rule under common variations

A screening engine's matching is tested by changing listed names in known ways and counting
what still matches. The same test was run on the policy's name rule, on the 367 distinct names
of listed people with at least two parts. Each name is changed once, in a fixed place. Names of
exactly two parts are shown on their own, because in a longer name two other parts still match.

| Variation | Names | Still agree | Two-part names | Still agree |
|---|---|---|---|---|
| Capitals | 367 | 100.0% | 179 | 100.0% |
| Surname first, with a comma | 367 | 100.0% | 179 | 100.0% |
| A middle initial added | 367 | 100.0% | 179 | 100.0% |
| A title added | 367 | 100.0% | 179 | 100.0% |
| First two parts written together | 367 | 100.0% | 179 | 100.0% |
| Longest part written apart | 333 | 100.0% | 157 | 100.0% |
| One letter doubled | 365 | 100.0% | 177 | 100.0% |
| One letter changed | 365 | 100.0% | 177 | 100.0% |
| One letter dropped | 365 | 99.5% | 177 | 98.9% |
| Two neighbouring letters swapped | 365 | 84.4% | 177 | 67.8% |
| Two letters dropped | 357 | 62.2% | 175 | 22.9% |
| First part cut to an initial | 367 | 100.0% | 179 | 100.0% |
| One part left out | 367 | 100.0% | 179 | 100.0% |
| First part replaced by another name | 367 | 51.2% | 179 | 0.0% |

What it says about the policy's rule:

- **It is strict about swapped letters.** The policy counts a swap as two edits, and only parts
  of seven letters or more are allowed two. A two-part legal name with two letters swapped in a
  shorter part does not agree with the listed name, so a verified name written that way is
  cleared with `NAME_MISMATCH_VERIFIED`. That is the rule working as written. It is also the
  case the `name_near_miss` flag sends to a second reader.
- **It is generous about missing parts.** A name with a part left out, or cut to an initial,
  always still agrees, because every part of the shorter name matches.
- **A long name survives one wrong part.** With three parts or more, replacing the first part
  with a different name still leaves two that match. No two-part name survives it.

None of this is a bug. The name rule is the policy's and the answers are scored against it. The
table shows where a person would disagree with the rule, which is what a second reader needs.

### 6. What the listings hold that the policy does not use

A screening engine weighs more than name, date and country. These were counted before deciding
to leave them out.

| Count | What |
|---|---|
| 207 | Hits that carry an identifier (a passport, tax or registration number) |
| 0 | Of those, equal to a document or registration number the bank holds |
| 605 | Hits that give a gender |
| 0 | Customer records that give a gender |
| 2 | Hits marked deceased that give no date of death |
| 125 | Hits with an alias written in another script |
| 0 | Hits whose own name is written in another script |
| 0 | Verified legal names written in another script |
| 33 | Approved checks whose verified date is not before the check itself |
| 0 | Comparisons whose date of birth rests on such a check |

So on this data: an identifier never matches, gender has nothing to be compared with, every
name that gets compared is in Latin script, and no decision rests on a date that cannot be
right. None of them was built into the decision. Each is a line to watch on new data: the tool
prints the same counts for any folder.

### 7. What was run

`manifest.json` records the SHA-256 and row count of every file in the data folder, one SHA-256
over the code that decides (`system/run` and everything under `system/screening/`), the git
commit and whether that code matches it, the layer settings, and the SHA-256 of the scored and
explain files. Given a decision, it says which data and which code produced it.

## What is still missing

- **Nothing records what the analyst then decides.** The queue and the sample are lists. A case
  tool would hold the second reader's verdict and feed disagreements back into the rules.
- **Nothing remembers a cleared pair.** A bank keeps a list of customer and listing pairs it has
  already cleared, and asks again only when either side changes. Every run here starts fresh.
- **The priority knows one distinction**, sanctions or not. A bank would set the order from its
  own risk appetite.
- **The looser matcher is ours.** It is not a commercial engine and has no phonetic or
  transliteration matching.
- **The sampling rate is a default**, 10% with a floor of 5. It was not derived from a target
  confidence level.
- **The viewer does not read these files.** They are CSV and JSON. The viewer keeps its own
  review queue, ordered by the score alone.
