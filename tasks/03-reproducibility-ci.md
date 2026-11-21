# Task 03: Reproducibility proof and CI

**Goal.** Show, with commands anyone can run, that the system gives the same answer every time
and runs on the machines the judges are likely to use. Ten percent of the score is "the same
decision and reason code in all five runs".

**Read first.** `tasks/README.md`, `system/run`, `system/screening/pipeline.py`.

**You may change.** `tools/repro.py` (new), `.github/workflows/tests.yml` (new).

## Steps

1. Write `tools/repro.py`, standard library only:
   `python tools/repro.py DATA [--runs 5]`
   - Runs `system/run DATA <temp file>` as a subprocess `--runs` times, each into a new file.
   - Prints the SHA-256 of each output file and the time each run took.
   - Compares the runs line by line on `hit_id`, `decision` and `reason_code`, and prints how many
     hits differ between any two runs.
   - If `output/dev.jsonl` exists, prints whether it equals the fresh output.
   - Exits 0 only when every run's file is byte-identical. Otherwise exits 1.
2. Run it on your `DATA` with `--runs 5`. Record the hash.
3. Run it again with the environment variable `PYTHONHASHSEED` set to `1`, then to `2`. The hash
   must not change. If it does, something depends on set or dict order: report the file and line.
4. Write `.github/workflows/tests.yml`. On every push and pull request, for the matrix
   `os: [ubuntu-latest, windows-latest, macos-latest]` by `python: ['3.8', '3.10', '3.12']`:
   - `python -m compileall -q system`
   - `python -m unittest discover -s system/tests`
   On `ubuntu-latest` also check:
   - `test -x system/run`
   - the first line of `system/run` is `#!/usr/bin/env python3`
   - `system/run` contains no carriage returns
   The workflow must not need the data, and must not download anything except Python itself.
5. Push your branch and read the workflow result. Fix only your own two files.

## Done when

- `python tools/repro.py DATA --runs 5` exits 0 and prints five equal hashes, with
  `PYTHONHASHSEED` unset, `1` and `2`.
- The workflow is green in all nine cells, or each red cell is reported under FINDINGS with the
  failing line of its log.

## Report addition

Add a table to your report: operating system, Python version, tests passed (yes or no). Add the
hash and the three `PYTHONHASHSEED` results.
