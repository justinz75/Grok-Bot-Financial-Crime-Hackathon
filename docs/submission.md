# Submission text

For the form on the event site's submit page. The team fills in the personal details: they are
left blank here on purpose.

## Project name

Same Person? Sanctions screening that shows its work

## Track

Track 2, sanctions screening

## What did you build?

A screening engine that decides, for every watchlist hit, whether the listed person is the bank's customer, a different person, or a case for an analyst. It runs the bank's identity policy as code: it finds the customer across the bank's systems, gathers the listed person's facts from fields, profile text and search results, then clears only on a contradiction, confirms only on agreement and otherwise asks for review. Every decision names the rule that decided it and cites the records behind it. The rules decide, with no model, no network and only the Python standard library. On the 819 development hits it clears 464, confirms 125 and sends 230 to review in about 7 seconds, gets 50 of 50 practice labels right with 0 unsafe clearances, and writes identical files in 5 fresh runs. Damaging the text 14 ways creates no clearance. On a real public sanctions list, 232142 known-answer cases, none is wrongly cleared. A viewer shows each hit as a side-by-side card and queues the reviews with the one fact that would settle each.

## Links

- Public repository: https://github.com/justinz75/Grok-Bot-Financial-Crime-Hackathon
- Demo video (2 minutes): 
- Live demo (optional): the viewer, once GitHub Pages is switched on for the repository (deploy
  from `main`, folder `/`). Its address is then the Pages address followed by `/viewer/`.

## Still needed from the team

- [ ] Contact email:
- [ ] Team name (optional):
- [ ] Member 1: full name, Cursor email, LinkedIn or X link
- [ ] Member 2: full name, Cursor email, LinkedIn or X link
- [ ] Member 3: full name, Cursor email, LinkedIn or X link
- [ ] Member 4: full name, Cursor email, LinkedIn or X link
- [ ] The video link, set so that anyone with the link can watch it
- [ ] Send the form before 17:00 London time

## Where each number comes from

| Number | Command | What it printed |
|---|---|---|
| 819, 464, 125, 230, about 7 seconds | `python system/run DATA output/dev.jsonl` | `819 hits decided in 6.9s: DIFFERENT_ENTITY 464, REVIEW 230, SAME_ENTITY 125` |
| 50 of 50, 0 unsafe | `python ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl` | `practice labels: 50 hits, 50 right decisions, 0 unsafe clearances` |
| 5 runs | `python tools/repro.py DATA --runs 5 --strict` | `scored files byte-identical across 5 runs: yes` |
| 14 ways | `python tools/stress.py DATA` | 14 rows, then `new clearances caused by harder text: none` |
| 232142 | `python tools/public_test.py --people 30000 --companies 30000` | `232142 hits`, then `cleared when it should not be: 0` |

The description is 1033 characters long (the form takes 20 to 1200).
