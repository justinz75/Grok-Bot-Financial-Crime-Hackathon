"""Prove the system gives the same answer every time.

    python tools/repro.py DATA [--runs 5] [--strict]

Runs `system/run` as a fresh process several times, the way the organisers do, and
compares the files it writes. Each run after the first is given a different
PYTHONHASHSEED, so anything that depends on the order of a set or a dict shows up.

It prints the SHA-256 of every scored file and every explain file, how many hits
differ in decision or reason code between runs, and whether a fresh run equals the
committed output/dev.jsonl. Exit code 0 means every run was byte-identical; with
--strict it also means the committed file is what the code produces now.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(ROOT, "system", "run")
COMMITTED = os.path.join(ROOT, "output", "dev.jsonl")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def answers(path):
    """hit_id -> (decision, reason_code), the two fields the organisers compare between runs."""
    out = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                out[row.get("hit_id")] = (row.get("decision"), row.get("reason_code"))
    return out


def one_run(data, folder, index):
    scored = os.path.join(folder, "run%d.jsonl" % index)
    explain = os.path.join(folder, "run%d.explain.jsonl" % index)
    env = dict(os.environ)
    seed = "random" if index == 0 else str(index)
    env["PYTHONHASHSEED"] = seed
    started = time.time()
    done = subprocess.run([sys.executable, RUN, data, scored, explain], env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seconds = time.time() - started
    if done.returncode != 0 or not os.path.isfile(scored):
        sys.stderr.write(done.stderr.decode("utf-8", "replace"))
        raise SystemExit("run %d failed with exit code %d" % (index + 1, done.returncode))
    return {"index": index + 1, "seed": seed, "seconds": seconds, "scored": scored, "explain": explain,
            "scored_sha": sha256(scored), "explain_sha": sha256(explain) if os.path.isfile(explain) else ""}


def main(argv):
    parser = argparse.ArgumentParser(description="Run the system several times and compare the files.")
    parser.add_argument("data", help="the data folder, e.g. screening/dev")
    parser.add_argument("--runs", type=int, default=5, help="how many runs to compare (default 5)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail if output/dev.jsonl is not what the code produces now")
    args = parser.parse_args(argv[1:])
    runs = max(2, args.runs)
    folder = tempfile.mkdtemp(prefix="repro-")
    try:
        results = [one_run(args.data, folder, index) for index in range(runs)]
        print("%-4s %-8s %7s  %-18s %-18s" % ("run", "hashseed", "seconds", "scored file", "explain file"))
        for r in results:
            print("%-4d %-8s %7.1f  %-18s %-18s" % (r["index"], r["seed"], r["seconds"],
                                                     r["scored_sha"][:16], r["explain_sha"][:16]))
        first = answers(results[0]["scored"])
        differing = set()
        for r in results[1:]:
            other = answers(r["scored"])
            differing.update(hit for hit in set(first) | set(other) if first.get(hit) != other.get(hit))
        scored_same = len(set(r["scored_sha"] for r in results)) == 1
        explain_same = len(set(r["explain_sha"] for r in results)) == 1
        print("\nhits decided: %d" % len(first))
        print("hits whose decision or reason code differs between runs: %d" % len(differing))
        print("scored files byte-identical across %d runs: %s" % (runs, "yes" if scored_same else "NO"))
        print("explain files byte-identical across %d runs: %s" % (runs, "yes" if explain_same else "NO"))
        print("scored file SHA-256: %s" % results[0]["scored_sha"])
        committed_same = None
        if os.path.isfile(COMMITTED):
            with open(COMMITTED, "rb") as a, open(results[0]["scored"], "rb") as b:
                committed_same = a.read().replace(b"\r\n", b"\n") == b.read().replace(b"\r\n", b"\n")
            print("committed output/dev.jsonl equals a fresh run: %s" % ("yes" if committed_same else "NO"))
        else:
            print("committed output/dev.jsonl: not found, so not compared")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if not (scored_same and explain_same):
        return 1
    if args.strict and committed_same is not True:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
