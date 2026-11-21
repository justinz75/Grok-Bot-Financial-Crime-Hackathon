# Demo script: two minutes

A shot list for the 2-minute video. Every number in it was printed by the command in the last
column, run on `main` on 21 November 2026. `DATA` is the development folder and `ROOM` the folder
above it.

**Do not show the development data on screen.** It is for participants only. The cards in the
third shot come from the viewer's built-in sample, which is invented and decided by the real
system. [system/README.md](../system/README.md) describes one real case of each kind by hit ID,
without names, for anyone who wants to check them against the data.

| Time | On screen | Said | The command that proves it |
|---|---|---|---|
| 0:00 to 0:15 | `viewer/index.html` on its built-in sample: the title "Is this the same person?" and the first card | A bank's screening tool raises a hit whenever a customer shares a name with someone on a watchlist, and somebody has to decide whether it is the same person. | Open `viewer/index.html` in a browser |
| 0:15 to 0:40 | A terminal. The run, then its first line of output | Our system decides all 819 development hits in about seven seconds. The rules decide: no model, no network, only the Python standard library. 464 are cleared, 125 are confirmed and 230 go to a person. | `python system/run DATA output/dev.jsonl` prints `819 hits decided in 6.9s: DIFFERENT_ENTITY 464, REVIEW 230, SAME_ENTITY 125` |
| 0:40 to 1:10 | The viewer, "All alerts". Three sample cards in turn: the first hit of the first alert (cleared), the first hit of the second alert (confirmed), then the review queue's third row (review) with "What would settle it" in view | Every answer shows its work. This hit is cleared: the verified date of birth is twenty-six years from the listed one, and the check behind it is cited. This one is confirmed: name and date of birth agree. This one goes to a person: nothing contradicts it and nothing confirms it, and the card says which single fact would settle it. | `python tools/make_viewer_sample.py --check` prints `the sample is up to date`: the cards are what the system writes for the invented folder |
| 1:10 to 1:30 | The terminal. The validator's last three lines | On the fifty hits the organisers labelled, fifty are right and none is an unsafe clearance. A wrong clearance is the costliest mistake, so when the system is unsure it says review. | `python ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl` prints `practice labels: 50 hits, 50 right decisions, 0 unsafe clearances` and `decision score 100.0` |
| 1:30 to 1:45 | The terminal. The five-run table, then the stress table's last line | Five fresh runs give five identical files. And when we damage the text fourteen different ways, including adding misleading sentences, no hit becomes a clearance. | `python tools/repro.py DATA --runs 5 --strict` prints `scored files byte-identical across 5 runs: yes`. `python tools/stress.py DATA` prints 14 rows and `new clearances caused by harder text: none` |
| 1:45 to 2:00 | The public-list table from `docs/results.md`, then "What is missing" in `system/README.md` | We also ran it on a real public sanctions list: 232,142 cases with known answers, none wrongly cleared. Its limits are written down: the optional model layers are unproven without an API key, and names in other scripts are compared as written. | `python tools/public_test.py --people 30000 --companies 30000` prints `232142 hits` and `cleared when it should not be: 0` |

## Before recording

- Run the six commands once, so that each has just printed what the script says.
- Put the terminal font at a size that reads on a phone.
- In the viewer, the sample loads by itself. Leave the banner that says it is a sample in shot.
- If a number on your screen differs from this script, say the number on your screen.

Spoken text: 224 words in 6 shots (the limit is 300).
