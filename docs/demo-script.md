# Demo script: two minutes

A shot list for the 2-minute video. The commands below are recording cues, not fresh validation evidence. Baseline evidence is in [release-readiness.md](release-readiness.md);
final release validation belongs to the release owner. Use only their confirmed results. `DATA` is the development folder and `ROOM` the folder
above it.

**Do not show the development data on screen.** It is for participants only. The cards in the
third shot come from the viewer's built-in sample, which is invented and decided by the real
system. [system/README.md](../system/README.md) describes one real case of each kind by hit ID,
without names, for anyone who wants to check them against the data.

| Time | On screen | Said | The command that proves it |
|---|---|---|---|
| 0:00 to 0:15 | `viewer/index.html` on its built-in sample: the title "Is this the same person?" and the first card | A bank's screening tool raises a hit whenever a customer shares a name with someone on a watchlist, and somebody has to decide whether it is the same person. | Open `viewer/index.html` in a browser |
| 0:15 to 0:40 | A terminal showing only the run summary, with input and output records hidden | The default system processes the development folder with rules: no model, no network, only the Python standard library. Each hit is cleared, matched or sent to a person. | Use the release owner’s final run summary; runtime depends on the machine. Do not show output records. |
| 0:40 to 1:10 | The viewer, "All alerts". Three sample cards in turn: the first hit of the first alert (cleared), the first hit of the second alert (confirmed), then sample hit `H-000034` (review) with "What would settle it" in view | Every answer shows its work. This hit is cleared: the verified date of birth is twenty-six years from the listed one, and the check behind it is cited. This one is confirmed: name and date of birth agree. This one goes to a person: nothing contradicts it and nothing confirms it, and the card says which single fact would settle it. | `python tools/make_viewer_sample.py --check` prints `the sample is up to date`: the cards are what the system writes for the invented folder |
| 1:10 to 1:30 | The terminal. The validator's last three lines | The labelled practice subset checks our decisions, but cannot establish accuracy on unseen cases. A wrong clearance is the costliest mistake, so when the system is unsure it says review. | `python ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl` prints `practice labels: 50 hits, 50 right decisions, 0 unsafe clearances` and `decision score 100.0` |
| 1:30 to 1:45 | The terminal. The five-run table, then the stress table's last line | We check repeated runs for identical files and test whether harder text creates unsafe clearances. The release owner records the final results. | `python tools/repro.py DATA --runs 5 --strict` prints `scored files byte-identical across 5 runs: yes`. `python tools/stress.py DATA` prints 14 rows and `new clearances caused by harder text: none` |
| 1:45 to 2:00 | The public-list table from `docs/results.md`, then "What is missing" in `system/README.md` | The limits are written down. Public-list testing uses synthetic cases. The optional model layers remain off and unproven, and names in other scripts are compared as written. | See the historical public-list experiment in `docs/results.md` and the limitations in `system/README.md`; do not imply it was rerun for release. |

## Before recording

- Obtain final validation evidence from the release owner; do not rerun heavy checks for recording.
- The public-list result in `docs/results.md` is historical; do not present it as validation of baseline `94b96fc` or the final release.
- Record only summary lines and invented sample cards; hide participant records and paths revealing private details.
- Put the terminal font at a size that reads on a phone.
- In the viewer, the sample loads by itself. Leave the banner that says it is a sample in shot.
- If a number on your screen differs from this script, say the number on your screen.

Spoken text: 197 words in 6 shots (counted by whitespace in the Said column).
