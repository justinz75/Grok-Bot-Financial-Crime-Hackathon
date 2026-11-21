"""The feedback loop: one command that says whether a change made the system safer or worse.

    python tools/loop.py [DATA] [--baseline FILE] [--quick]

DATA is your screening/dev folder. Left out, it is looked for at data/room/screening/dev
and data/screening/dev. With no data at all, only the first step runs: it needs none.

    1 tests       every test, including the wordings that must never clear a hit
                  (system/tests/test_wording.py)
    2 moved       a fresh run against the baseline, which is the committed output/dev.jsonl
                  unless --baseline names another scored file: which hits changed, and how
                  many moved INTO DIFFERENT_ENTITY. That number must be 0: nothing we add
                  may turn a review or a match into a clearance
    3 labels      ROOM/validate.py on the fresh run, scored on the practice labels
    4 stress      tools/stress.py: text taken away or added must never clear a hit
    5 same twice  tools/repro.py: five fresh runs must be byte-identical

--quick stops after step 3. Steps 2 to 5 call the repo's own tools, so they measure
whatever those tools measure today. The exit code is 1 when any step fails.

How to iterate with it:

    1. Find a wording or a situation the system gets wrong. tasks/01-audit-clearances.md
       finds them by hand; the "to rev." and "NEW CLEAR" columns of step 4 find them in bulk.
    2. Write it down with invented names: a test in system/tests/test_wording.py, or a
       case in tools/stress.py when it is a way of wording that applies to every note.
    3. Run this and watch step 1 or step 4 fail.
    4. Fix it in the direction of caution, then run this again. Step 2 lists every hit
       the fix moved; read them before believing the fix.
    5. Regenerate output/dev.jsonl once the code under system/ has stopped changing.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMITTED = os.path.join(ROOT, "output", "dev.jsonl")
CLEARED = "DIFFERENT_ENTITY"
SHOWN = 40  # changed hits listed before the rest are only counted


def find_data(given):
    if given:
        return given
    for folder in (os.path.join(ROOT, "data", "room", "screening", "dev"), os.path.join(ROOT, "data", "screening", "dev")):
        if os.path.isfile(os.path.join(folder, "alerts.jsonl")):
            return folder
    return None


def call(args):
    """Run one of the repo's own commands; returns (exit code, everything it printed)."""
    done = subprocess.run([sys.executable] + args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return done.returncode, done.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def lines_of(text):
    return [line for line in text.splitlines() if line.strip()]


def scored(path):
    """hit_id -> scored line."""
    out = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                out[row.get("hit_id")] = row
    return out


def same_bytes(a, b):
    with open(a, "rb") as one, open(b, "rb") as two:
        return one.read().replace(b"\r\n", b"\n") == two.read().replace(b"\r\n", b"\n")


def step_tests():
    code, text = call(["-m", "unittest", "discover", "-s", "system/tests"])
    tail = lines_of(text)[-2:]
    if code != 0:
        print(text)
    return code == 0, ", ".join(tail)


def step_moved(fresh, baseline):
    if not os.path.isfile(baseline):
        return None, "no baseline at %s" % os.path.relpath(baseline, ROOT)
    new, old = scored(fresh), scored(baseline)
    common = sorted(set(new) & set(old))
    if len(common) < 0.9 * max(len(new), len(old), 1):
        return None, "the baseline is for another data folder (%d of %d hits in common)" % (len(common), len(new))
    moves, changed, into_clear, other_fields = Counter(), [], [], 0
    for hit in common:
        a, b = old[hit], new[hit]
        if (a["decision"], a["reason_code"]) != (b["decision"], b["reason_code"]):
            moves[(a["decision"], b["decision"])] += 1
            changed.append((hit, a, b))
            if b["decision"] == CLEARED and a["decision"] != CLEARED:
                into_clear.append(hit)
        elif a != b:
            other_fields += 1
    for (a, b), count in sorted(moves.items()):
        print("   %-17s -> %-17s %d" % (a, b, count))
    for hit, a, b in changed[:SHOWN]:
        print("   %s  %s %s -> %s %s" % (hit, a["decision"], a["reason_code"], b["decision"], b["reason_code"]))
    if len(changed) > SHOWN:
        print("   ... and %d more" % (len(changed) - SHOWN))
    if into_clear:
        print("   moved INTO %s: %s" % (CLEARED, ", ".join(into_clear[:SHOWN])))
    if baseline == COMMITTED and not same_bytes(fresh, baseline):
        print("   output/dev.jsonl is not what the code produces now. Regenerate it before the freeze:")
        print("   python system/run DATA output/dev.jsonl")
    detail = "%d of %d hits changed decision or reason code, %d moved into %s, %d changed only in reason or evidence" % (
        len(changed), len(common), len(into_clear), CLEARED, other_fields)
    return not into_clear, detail


def step_labels(data, fresh):
    validate = os.path.join(os.path.dirname(os.path.abspath(data)), "validate.py")
    labels = os.path.join(data, "practice_labels.jsonl")
    if not (os.path.isfile(validate) and os.path.isfile(labels)):
        return None, "validate.py or practice_labels.jsonl not found beside the data"
    code, text = call([validate, "--data", data, "--output", fresh, "--score", labels])
    print("\n".join("   " + line for line in lines_of(text)[-8:]))
    unsafe = re.search(r"(\d+) unsafe clearance", text)
    problems = re.search(r"(\d+) problems?\b", text)
    bad = code != 0 or (unsafe and int(unsafe.group(1)) > 0) or (problems and int(problems.group(1)) > 0)
    found = re.search(r"\d+ hits, \d+ right decisions, \d+ unsafe clearances?", text)
    return not bad, found.group(0) if found else (lines_of(text) or ["no output"])[-1]


def step_stress(data):
    code, text = call([os.path.join("tools", "stress.py"), data])
    table = [line for line in lines_of(text) if not line.startswith(("layers:", "note:")) and " hits decided in " not in line]
    print("\n".join("   " + line for line in table))
    return code == 0, (table or ["no output"])[-1]


def step_repro(data):
    code, text = call([os.path.join("tools", "repro.py"), data, "--runs", "5"])
    kept = [line for line in lines_of(text) if "differs between runs" in line or "byte-identical" in line]
    print("\n".join("   " + line for line in kept or lines_of(text)[-5:]))
    return code == 0, "; ".join(kept[:2]) or (lines_of(text) or ["no output"])[-1]


def main(argv):
    parser = argparse.ArgumentParser(description="Run every check in order and say what a change did.")
    parser.add_argument("data", nargs="?", help="the data folder, e.g. screening/dev")
    parser.add_argument("--baseline", default=COMMITTED, help="scored file to compare the fresh run with")
    parser.add_argument("--quick", action="store_true", help="stop after the practice labels")
    args = parser.parse_args(argv[1:])
    data = find_data(args.data)
    results = []

    def record(name, outcome):
        passed, detail = outcome
        results.append((name, "skipped" if passed is None else ("PASS" if passed else "FAIL"), detail))

    print("== 1 tests")
    record("tests", step_tests())
    if data is None:
        for name in ("moved", "labels", "stress", "same twice"):
            results.append((name, "skipped", "no data folder: pass one, or put it at data/room/screening/dev"))
    else:
        folder = tempfile.mkdtemp(prefix="loop-")
        try:
            fresh = os.path.join(folder, "fresh.jsonl")
            print("== 2 moved")
            code, text = call([os.path.join("system", "run"), data, fresh])
            print("\n".join("   " + line for line in lines_of(text)[:2]))
            if code != 0 or not os.path.isfile(fresh):
                print(text)
                record("moved", (False, "system/run failed with exit code %d" % code))
            else:
                record("moved", step_moved(fresh, os.path.abspath(args.baseline)))
                print("== 3 labels")
                record("labels", step_labels(data, fresh))
                if args.quick:
                    results.append(("stress", "skipped", "--quick"))
                    results.append(("same twice", "skipped", "--quick"))
                else:
                    print("== 4 stress")
                    record("stress", step_stress(data))
                    print("== 5 same twice")
                    record("same twice", step_repro(data))
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    print("\n%-11s %-8s %s" % ("step", "result", "what it printed"))
    for name, result, detail in results:
        print("%-11s %-8s %s" % (name, result, detail))
    return 1 if any(result == "FAIL" for _name, result, _detail in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
