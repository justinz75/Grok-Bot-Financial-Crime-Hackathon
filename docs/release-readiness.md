# Release readiness: handoff sections 4–6

**Baseline evidence only. Final release sign-off is pending.** Work is confined to
`task/handoff-release`; no decision code, tracked predictions, viewer or `main` was changed.
The team owns integration, recording, publishing and submission before **17:00 London,
21 November 2026**.

## Live refs and evidence scope

`git fetch origin`, `git ls-remote --heads origin` and `gh pr list --state open` were checked
on 21 November 2026. Baseline `origin/main` and this checkout's HEAD were both
`94b96fc4eccbd7736bf53ad4eb8e1cf64885dbb6`. Only draft PR #4 was open; it was excluded
from this assignment. The old handoff's branch descriptions are not proof of current integration.
No other checkout was changed. The supplied private ROOM was read only; generated predictions
went into a temporary directory and were deleted. Logs and downloaded fixtures remain ignored
under `data/`, with no participant rows included in this document.

Checks ran with Python 3.14.10 and explicit modes
`score=on,briefing=on,reader=off,reviewer=off`, with the OpenRouter key removed from the
validation subprocess environment. Initial attempts failed or were interrupted before completion. T3's inherited
`PYTHONEXECUTABLE` pointed at Electron in the first attempt. Clearing `PYTHONEXECUTABLE` and
`__PYVENV_LAUNCHER__` fixed subprocess execution; those launcher failures are not gate results.

## Baseline gate results

Completed on 21 November 2026 against the baseline SHA above, before this documentation commit.

| Gate | Observed result |
|---|---|
| `python -m unittest discover -s system/tests` | `Ran 234 tests`, `OK` |
| `python system/run DATA <temporary file>` | `819 hits decided in 5.8s: DIFFERENT_ENTITY 464, REVIEW 230, SAME_ENTITY 125` |
| Official validator on temporary output with practice labels | `819 lines read, 0 problems`; `practice labels: 50 hits, 50 right decisions, 0 unsafe clearances`; `decision score 100.0 (0 = all REVIEW, 100 = perfect)`; `on right decisions: reason code 100%, customer record 100%` |
| `python tools/loop.py DATA` | All six steps `PASS`, exit 0; `0 of 819 hits changed decision or reason code, 0 moved into DIFFERENT_ENTITY, 0 changed only in reason or evidence`; `18 of 18 demo cases came out as built` |
| `python tools/stress.py DATA` (called by the full loop) | `new clearances caused by harder text: none`; every `NEW CLEAR` entry is 0 |
| `python tools/repro.py DATA --runs 5 --strict` | `hits whose decision or reason code differs between runs: 0`; `scored files byte-identical across 5 runs: yes`; `explain files byte-identical across 5 runs: yes`; `committed output/dev.jsonl equals a fresh run: yes`; exit 0 |
| `python tools/make_viewer_sample.py --check` | `the sample is up to date`; exit 0 |

Scored SHA-256 from strict repro: `4835e16dfcb7cd76d5a302535a7e0ffb7c60fe68b94f5538ada8efe4e8977749`.
The full loop invokes the actual stress command, so it was not repeated separately.


Additional check: `python -m unittest discover -s tools/tests` printed `Ran 28 tests`, `OK`.
The [CI run for the baseline](https://github.com/justinz75/Grok-Bot-Financial-Crime-Hackathon/actions/runs/44920214922)
completed successfully in all eight jobs, including Python 3.8 and the executable entry-point
check. This does not attest to later commits.

The public demo was built locally from the pinned OpenSanctions export in
[data-sources.md](data-sources.md), whose downloaded SHA-256 was checked:
`769583d92843fc1b2d442008b46dbc364ccad660248a5e60b6f8e8f7197b1e82`.
`tools/make_public_demo.py --dev-dir "$DATA"` printed `18 demo cases from 6 OpenSanctions profiles`.
The full public-list test and layer ablation were **not rerun** for this baseline. Their
existing tables in [results.md](results.md) remain historical measurements.

## Materials review and owner actions

- [x] `system/README.md` contains architecture, customer and hit resolution, evidence,
  determinism, model/prompt disclosure, time/cost, three cases and limitations. Its required
  sections exist; that is a coverage check, not approval of every historical statistic.
- [ ] **Owner: update the README after integration.** The layer-comparison table still refers
  to a stand-in agreeing with `504` clearances, whereas the current baseline's scored total is
  in the gate table above. Preserve historical experiment provenance or remeasure; do not
  describe the stand-in as a real model. Refresh counts, tests, caveats and examples affected
  by the reading/wording/gap work. Review the existing development-case descriptions against
  the no-participant-record rule; use invented cases for public demonstration.
- [x] Demo script now uses invented sample cards, avoids a machine-independent runtime promise,
  and separates historical public-list testing from final-release evidence. The sample card
  cues were checked against sample files, without browser verification in this assignment.
- [x] Submission copy avoids unverified final metrics. Its length was counted by command;
  the public form was fetched read-only and its description range, team size, public-repo
  confirmation and mandatory link fields were checked. No form was filled or sent.
- [ ] **Recorder: rehearse and record exactly two minutes** from [demo-script.md](demo-script.md).
  Use the built-in sample, keep its sample banner, and show only aggregate terminal summaries.
  Hide participant rows, private paths, shell history and credentials. Verify readability and
  audio, upload to a supported service, and test access while signed out.
- [ ] **Team: fill contact email and every actual member's name, Cursor email and LinkedIn/X
  link** (one to five people). Verify project name, Track 2 and public repository URL, tick the
  public-repository confirmation, paste the accessible video link, submit once before freeze
  and retain the confirmation. Personal details remain blank in git.
- [ ] **Optional owner action:** publish the viewer with GitHub Pages only if desired. Verify
  the actual deployed `/viewer/` URL before adding it to the form; leave the optional field
  blank otherwise. No hosting settings were changed here.
- [ ] **Integrator: record the final merged SHA and run the final verification below.**
  Baseline success cannot certify a later merge. Keep model layers off; no model experiment
  or key is needed for release.

## Integration dependencies and exact commands

Run from the team's authorized integration checkout on a `task/*` branch. Do not run a merge
or commit directly on `main`. Keep the earlier tracked predictions as a baseline until the
movement check has passed. The owner coordinates overlapping decision-code branches; this
release task does not merge them. Check live refs again instead of following the stale branch
order in the handoff blindly. Finish the decision changes first, regenerate the sample after
any change affecting it, then regenerate predictions and update documentation from measured output.

The examples below use Bash syntax. `ROOM` must be the supplied private screening folder and
`DATA` its `dev` child, readable without copying data into tracked paths. Set the path locally:

```sh
set -eu
ROOM=/absolute/private/path/to/screening
DATA="$ROOM/dev"
unset PYTHONEXECUTABLE __PYVENV_LAUNCHER__ OPENROUTER_API_KEY
export SCREENING_LAYERS=score=on,briefing=on,reader=off,reviewer=off
PYTHON=/usr/bin/python3
"$PYTHON" -c 'import sys; print(sys.version); print(sys.executable)'
git fetch origin
git rev-parse HEAD origin/main
BASELINE_SHA=$(git rev-parse origin/main)  # capture BEFORE integrating decision changes
```

`tools/loop.py` needs `data/public_demo/hits.jsonl` for its last gate. If absent, obtain the
pinned CSV named in [data-sources.md](data-sources.md), save it as `data/public/sanctions.csv`,
and verify it before building. A different export is not the same experiment:

```sh
printf '%s  %s\n' \
  769583d92843fc1b2d442008b46dbc364ccad660248a5e60b6f8e8f7197b1e82 \
  data/public/sanctions.csv | sha256sum -c -
"$PYTHON" tools/make_public_demo.py --dev-dir "$DATA"
```

Run preflight with temporary predictions, before replacing the tracked baseline. All six
loop rows must say `PASS`; exit zero alone is insufficient because missing fixtures are skipped.
Use the pre-integration `BASELINE_SHA`, not a branch artifact already regenerated by a contributor.
Logs may contain private hit IDs or errors; keep them local and do not attach them to the PR.

```sh
RELEASE_TMP=$(mktemp -d)
trap 'rm -rf "$RELEASE_TMP"' EXIT
git show "$BASELINE_SHA:output/dev.jsonl" > "$RELEASE_TMP/baseline.jsonl"
"$PYTHON" -m unittest discover -s system/tests
"$PYTHON" system/run "$DATA" "$RELEASE_TMP/dev.jsonl"
"$PYTHON" "$ROOM/validate.py" --data "$DATA" --output "$RELEASE_TMP/dev.jsonl" \
  --score "$DATA/practice_labels.jsonl"
"$PYTHON" tools/loop.py "$DATA" --baseline "$RELEASE_TMP/baseline.jsonl"
"$PYTHON" tools/stress.py "$DATA"
"$PYTHON" tools/make_viewer_sample.py --check
```

If the sample is stale, its owner runs `"$PYTHON" tools/make_viewer_sample.py` and reviews the
invented sample changes before repeating `--check`. Never edit the built-in sample by hand.
Require no newly created clearance in the loop and stress outputs. A movement failure must be
resolved by the decision owner before regeneration; replacing the baseline must not hide it.

After the last decision change, the owner regenerates and validates the required artifact:

```sh
"$PYTHON" system/run "$DATA" output/dev.jsonl
"$PYTHON" "$ROOM/validate.py" --data "$DATA" --output output/dev.jsonl \
  --score "$DATA/practice_labels.jsonl"
"$PYTHON" tools/repro.py "$DATA" --runs 5 --strict
"$PYTHON" tools/make_viewer_sample.py --check
sha256sum output/dev.jsonl
git diff --check
git diff --stat
```

The strict repro gate checks run agreement and agreement with the tracked artifact (normalizing
CRLF); it does not replace the official schema/labels validator. Review the file list to keep
private inputs, explain files and local logs out of commits. Update `docs/context/status.md`,
README and demo/form claims from the new command outputs, naming the tested code revision.
If assurance or public-test figures are promoted to current claims, rerun the corresponding
`tools/assure.py`, `tools/ablate.py` or `tools/public_test.py` command first and label model
stand-ins separately. This is not a dependency for keeping those tables explicitly historical.
Run tests before every push, push the task branch and open a PR; the owner handles integration.

## Final merged SHA sign-off (team completes)

After the owner merges all accepted changes, run in an authorized checkout of that exact merged
`origin/main` SHA, without modifying `main` or regenerating files there. Record `git rev-parse
HEAD` and verify the tracked output equals a fresh temporary run. Repeat every section-5 gate:
unit tests, temporary scored run, official validator with practice labels, full loop (six PASS
rows), standalone stress, five-run strict repro, and sample check. Verify CI for that same SHA.
Use the setup above, then run this block in that checkout (there is no artifact write on `main`):

```sh
FINAL_SHA=$(git rev-parse HEAD)
test "$FINAL_SHA" = "$(git rev-parse origin/main)"
FINAL_TMP=$(mktemp -d)
trap 'rm -rf "$FINAL_TMP"' EXIT
printf 'Tested final candidate: %s\n' "$FINAL_SHA"
"$PYTHON" -m unittest discover -s system/tests
"$PYTHON" system/run "$DATA" "$FINAL_TMP/dev.jsonl"
"$PYTHON" "$ROOM/validate.py" --data "$DATA" --output "$FINAL_TMP/dev.jsonl" \
  --score "$DATA/practice_labels.jsonl"
cmp output/dev.jsonl "$FINAL_TMP/dev.jsonl"
"$PYTHON" tools/loop.py "$DATA"
"$PYTHON" tools/stress.py "$DATA"
"$PYTHON" tools/repro.py "$DATA" --runs 5 --strict
"$PYTHON" tools/make_viewer_sample.py --check
git diff --exit-code
sha256sum output/dev.jsonl
test "$FINAL_SHA" = "$(git ls-remote origin refs/heads/main | cut -f1)"
```

Save aggregate results with `FINAL_SHA`, the artifact hash, interpreter and layer modes.
Check the GitHub Actions run for that same SHA; do not reuse an earlier green run.

If any result changes, make the fix on a task branch, revalidate, obtain owner integration and
restart this sign-off on the new SHA. If `origin/main` advances during sign-off, the earlier SHA
is no longer the final candidate. Only after the exact submitted SHA has passed may its results
be labelled **final**.

- [ ] Final merged SHA: pending
- [ ] Exact SHA's gates and CI: pending
- [ ] Required tracked predictions match fresh output: pending for final SHA
- [ ] README and demo/form claims agree with that evidence: pending
- [ ] Video public access, human details and submission confirmation: team-owned, pending
