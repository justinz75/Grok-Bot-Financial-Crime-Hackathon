# Task 06: Demo script and submission text

**Goal.** The words for the 2-minute video and the submission form. Every claim must be something
a viewer can watch a command prove.

**Read first.** `tasks/README.md`, `system/README.md`, `research/ui-ux.md`, and the submit page of
the event site for the form's fields.

**You may change.** `docs/demo-script.md` and `docs/submission.md` only (new files).

## Steps

1. Run the four commands in `tasks/README.md` and copy the last line of each output. These are
   the only numbers you may use. If a number in this task differs from what you see, use what you
   see and report the difference.
2. Write `docs/demo-script.md`: a shot list for exactly 2 minutes, as a table with columns
   time, what is on screen, what is said, and the command that proves it. Use this order:
   - 0:00 to 0:15. The problem: a customer shares a name with a listed person. One sentence.
   - 0:15 to 0:40. The run: `system/run`, 819 hits in about 6 seconds, no model, no network.
   - 0:40 to 1:10. One cleared hit, one confirmed hit, one sent to review, each with its reason
     and evidence IDs on screen. Use the three cases in `system/README.md`.
   - 1:10 to 1:30. `validate.py`: 50 of 50 practice labels, 0 unsafe clearances.
   - 1:30 to 1:45. Same answer every time: two runs, identical files.
   - 1:45 to 2:00. Honest limits, from the "What is missing" section of `system/README.md`.
   Spoken text must fit: at most 300 words in total.
3. Write `docs/submission.md` with:
   - a project name;
   - "What did you build?", between 20 and 1200 characters, plain sentences, no claim that is
     not in step 1;
   - the track: Track 2, sanctions screening;
   - a checklist of what the form still needs from the team: each member's name, Cursor email
     and LinkedIn or X link, the contact email, the public repo link, the video link.
   Leave the personal details blank for the team to fill in. Do not invent them.
4. Count the characters of the description and the words of the spoken text, and write both
   counts at the bottom of the files.

## Done when

- `docs/demo-script.md` covers 0:00 to 2:00 with no gap, and its spoken text is at most 300 words.
- The description in `docs/submission.md` is between 20 and 1200 characters.
- Every number in both files appears in a command output you recorded in step 1.
- `git status` shows the two files under `docs/` only.
