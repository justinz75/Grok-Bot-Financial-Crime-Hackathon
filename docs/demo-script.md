# Two-minute sanctions screening demo

Use the [architecture overview](demo-overview.md) for the diagram and the [viewer](../viewer/index.html) for the invented cases. Read the narration column aloud.

| Time | On screen | Narration | Recording cue |
|---|---|---|---|
| 0:00–0:15 | Viewer title and the first sample alert | A customer shares a name with someone on a watchlist. Is it the same person? A wrong clearance can hide a genuine match, so we require a specific contradiction before clearing a hit. | Open the viewer with its built-in sample. Select **All alerts**. |
| 0:15–0:38 | Architecture diagram, from customer and watchlist inputs to scored output | We resolve the customer and the watchlist profile separately. Each fact keeps its source. Then the policy rules compare the facts and write a decision, a reason code and the evidence behind it. The default Python run works offline and gives the same answer from the same inputs. | Trace both paths into the policy comparison, then point to the scored output and the optional explanations that feed the viewer. |
| 0:38–1:02 | Clear and match cards | Here, an approved identity check gives a birth date that contradicts the listed year, so we clear the hit. The card cites the check. On this next hit, the identity check is written in a note. We recover the birth date, and the name and year agree, so we confirm the match. | Show `H-000026` and its cited check `KYC-000024`. Then show `H-00002D` and its cited note `NOTE-00002B`. |
| 1:02–1:25 | Two review cards | The next hit has the same name and birth year but a different country. We leave it for an analyst. Public-list testing exposed a version of this bug with one-part names, so we made that safeguard cover them too. Here, the reviewer needs one thing: the listed person's birth date. | Show `H-00002E` under the same alert, then `H-000034` with **What would settle it** in view. |
| 1:25–1:43 | Date-parsing regression and its passing output | We also fixed a parsing failure: a date about the listed person's relative could be read as the person's own birth date. Now a date from prose can justify a clearance only when the wording ties it to the listed person. | Show the invented example in `test_another_person_birth_is_not_subject_birth`, then the passing output of `python -m unittest discover -s system/tests -p test_dob_context.py`. |
| 1:43–2:00 | Aggregate baseline results, then back to the review card | On the recorded development baseline, we got all fifty practice labels right, and five fresh runs wrote identical results. Those figures cover the practice data. The judges hold the unseen cases. Every decision gives an analyst the evidence to check it. | Show only the practice and reproducibility rows in [release readiness](release-readiness.md), labelled with baseline revision `94b96fc`. |

## Before recording

- Run `python tools/make_viewer_sample.py --check` and keep the sample banner visible. The viewer search accepts hit IDs.
- Show only the invented sample and aggregate results. Keep participant records, local data paths and credentials off screen.
- Use the recorded baseline figures with their revision label. Use figures for the submitted revision only after the release owner confirms them.
- Rehearse the switches between tabs and leave the final review card on screen through 2:00.

Spoken text: 265 words across six shots.
