# Handoff: concurrent work in grokhack, about 15:35 London, 21 November 2026

Written for an AI assistant (ChatGPT) taking over from Claude Code. Read `AGENTS.md` first: its
rules are binding (never make clearing easier, `main` always works, `system/` stays stdlib /
deterministic / Python 3.8, no participant data in git, numbers come from commands).

**Code freeze: 17:00 London. The last commit on `main` before then is scored.**

Run commands from the main checkout `%USERPROFILE%\OneDrive\Desktop\grokhack` unless a
worktree is named. On Windows use `py`. `DATA` = `data/room/screening/dev`, `ROOM` =
`data/room/screening`.

## 1. State of `main`

- HEAD `57ac04c` (15:31) "Count the test that came with the last commit of pull request 5".
  Pull request 5 (teammate's DOB / weak-country / per-candidate-reason work) is merged.
- Working tree is clean. `py -m unittest discover -s system/tests` -> OK (status page says 234 tests).
- `docs/context/status.md` snapshot is 15:30 and is accurate for main: 819 hits,
  DIFFERENT_ENTITY 464 / REVIEW 230 / SAME_ENTITY 125, practice labels 50/50, 0 unsafe
  clearances, 5-run repro byte-identical.
- `gh` CLI is not installed on this machine, so pull requests cannot be read from the terminal.

## 2. Every Claude session was stopped

All four sessions that were running are now idle: each was interrupted mid-task and nothing
finished. Their work is in the git worktrees below, not in the sessions.

| Session (Claude desktop app) | Where it worked | What it was doing |
|---|---|---|
| "Policy gap coverage strategy" | worktree on `task/policy-gaps` | Policy-gap research and design (section 3.1) |
| "Feedback loop for iteration" | worktree on `task/loop-round-2` | Hardening the rules with the stress/loop tools, then merging main (section 3.2) |
| "OpenRouter + Grok approach" | `C:\Projects\Limit-order-book exchange simulator` (another folder) | Model layer via OpenRouter. Its state is unknown. The model layers are blocked anyway: there is no `OPENROUTER_API_KEY` |
| "Grok-Bot-Financial-Crime-Hackathon invites" | same other folder | Team and invite admin. Its state is unknown and it does not touch this repo |

## 3. Open branches and worktrees, most urgent first

### 3.1 `task/policy-gaps`: owner direction of 15:15, marked very important

- Worktree: `%USERPROFILE%\AppData\Local\Temp\claude\deea628a9b2be7e1\6f23451a-c9c4-4ad6-931b-fdce3c1341fc\scratchpad\wt`
- Branch is at main (`57ac04c`), with **no commits and not pushed**. Uncommitted:
  - `docs/context/policy-gaps.md` (new, 241 lines): the gap register G01 to G18 in four kinds
    (Silent, Thin, Premise, Outside), the assumption for each, sources, and a proposed design.
  - `tools/gap_counts.py` (new, 171 lines): counts the gaps on the dev set.
  - `AGENTS.md` (+15 lines, the "Cases the policy does not cover" section) and
    `docs/context/decisions.md` (+19 lines).
- The design, which is **not built and waits for the owner's go-ahead** because it adds
  `system/screening/layers/gaps.py`:
  - Two answers per hit, kept apart. The identity decision stays exactly as now in the scored
    file. A "disposition" (what a bank or a fintech does next) goes only into the explain file,
    the viewer and the README.
  - A decision table with 7 rows (escalate / review first / review / hold / close with a
    second reader / close), profile set by `SCREENING_PROFILE=bank|fintech`, default `bank`.
  - With the layer at its default `on`, the scored file does not change. In `enforce` + `bank`,
    row 4 (premise gap on a clearance) becomes REVIEW, which would move 1 dev hit (the one under G16).
  - To build: `layers/gaps.py`, `system/tests/test_gaps.py` (one invented case per gap, every
    row has an assumption), the explain block `gaps`, a short section in `system/README.md`.
- **Next steps:** (a) commit the four files on the branch now, so the docs are safe even if the
  design is never built. (b) Ask Justin for a go or no-go on building the layer. (c) If it is a
  go, build it so the scored output stays byte-identical, run every check in section 5, and open a PR.

### 3.2 `task/loop-round-2`: a merge of main is half done

- Worktree: `%USERPROFILE%\AppData\Local\Temp\claude\deea628a9b2be7e1\d9bb070a-5502-4d7f-b6b5-4320da12ce7d\scratchpad\wt`
  (git calls it `wt2`).
- The branch commit is `d9b5f72` (15:28) "Stop a date or number that is not the listed person's
  birth date from clearing a hit". **It is not pushed.**
- **A merge of main (`a8d33df`) is in progress**: `MERGE_HEAD` is set, everything is staged,
  there are no conflict markers, and `py -m unittest discover -s system/tests` -> `Ran 240 tests`, `OK`.
- Net change against main: `system/screening/{decide,extract,watchlist}.py`,
  `layers/briefing.py`, `tools/stress.py`, `system/tests/test_wording.py` (+63), and
  `test_decision_evidence.py` (-15 lines: **check why tests were deleted**; it may be a
  duplicate removed by the merge, or a lost test). `output/dev.jsonl` is not in the diff, so it
  must be regenerated and compared.
- **Next steps:** `git -C <worktree> commit` to finish the merge, then run every check in
  section 5 in that worktree. The decision must not move toward DIFFERENT_ENTITY on any hit.
  Then push and open a PR.

### 3.3 `task/reading-gaps`: pushed, needs main merged in

- Worktree: `...\deea628a9b2be7e1\c9347d0b-e6e8-42d0-ad92-34d19555412b\scratchpad\wt`. It is
  clean, at `b7a2630` = `origin/task/reading-gaps`.
- Commit (15:28): "Stop a value that cannot be read from clearing a hit". It touches
  `dates.py`, `decide.py`, `resolve.py`, `watchlist.py`, `layers/briefing.py`, the docs, and
  `system/tests/test_unreadable.py` (+344). On the branch the tests give `Ran 243 tests`, `OK`.
- It is based on `1891ec0`, from before pull request 5, so it must have main merged in.
  **It overlaps 3.2** (`decide.py`, `watchlist.py`, `briefing.py`): merge one into main first,
  then merge main into the other.

### 3.4 `task/unlabelled-codes`: old, with uncommitted work

- Worktree: `%USERPROFILE%\OneDrive\Desktop\grokhack-unlabelled`, branch at `7755807` (14:41). Not pushed.
- Uncommitted: `system/tests/test_unlabelled_codes.py` (new: end-to-end tests for
  ENTITY_TYPE_MISMATCH, DECEASED and AMBIGUOUS_CUSTOMER_RECORD, the three reason codes the
  practice labels never show; invented names), and small edits to `docs/context/{data,decisions,status}.md`.
- **Next steps:** commit, rebase onto or merge current main, and run the tests. Tests only
  (no `system/screening/` change) make this the lowest-risk merge. The status.md edits will
  probably conflict: keep main's version and redo the one line.

### 3.5 Others

- `task/reader-guards` (an extra worktree under `...\060f311134cd4c67\...`) is already merged into
  main and can be removed with `git worktree remove`.
- `origin/task/screening-decision-evidence` has one commit that is not on main: `4c72de0` "Align
  scored screening reasons with their evidence." Its owner and state are unknown, probably a
  teammate. Ask before merging.
- `origin/task/screening-improvements` (pull request 5) is merged.

## 4. Work outside the code, still open (from `docs/context/status.md`)

1. Final `system/README.md` and final `output/dev.jsonl`, planned for 15:30 to 16:15. They come
   after any merge above.
2. The 2-minute video, from the shot list in `docs/demo-script.md`. It needs a person, 16:15 to 16:45.
3. The submission form. The text is in `docs/submission.md`, the fields are in
   `docs/context/hackathon.md`, and the personal details are the team's to fill in.
4. Optional: switch on GitHub Pages for the viewer (repository settings, deploy from `main`, folder `/`).
5. The model layers stay off (no API key). Do not try to switch them on before the freeze.

## 5. Checks before anything reaches `main`

```
py -m unittest discover -s system/tests
py system/run DATA output/dev.jsonl
py ROOM/validate.py --data DATA --output output/dev.jsonl --score DATA/practice_labels.jsonl
py tools/loop.py DATA            # all steps PASS, 0 moved into DIFFERENT_ENTITY
py tools/stress.py DATA          # "new clearances caused by harder text: none"
py tools/repro.py DATA --runs 5 --strict    # exit 0, committed output equals a fresh run
py tools/make_viewer_sample.py --check
```

After the last change under `system/`, regenerate `output/dev.jsonl` and commit it. Update
`docs/context/status.md` with the numbers the commands print, and never type figures by hand.

## 6. Suggested order, given about 85 minutes

1. Commit `task/policy-gaps` (docs only) and `task/unlabelled-codes` (tests only). Both are safe.
2. Finish the loop-round-2 merge and check it. Merge it into main if every check passes.
3. Merge main into `task/reading-gaps`, resolve the overlap, check it, and merge it.
4. Build the gaps layer only if Justin says go and there is time before about 16:15. Otherwise
   ship policy-gaps.md as documentation only.
5. By 16:15: final README, regenerate dev.jsonl, the repro check, push. Then the video and the form before 17:00.
