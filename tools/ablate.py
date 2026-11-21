"""Which layer helps? Run the system with each layer off, on and enforcing, and compare.

    python tools/ablate.py DATA [ROOM] [--runs 5] [--model ID] [--stress]

One row per setting, each measured against the rules alone:

    changed    hits whose decision differs from the rules-only run
    to review  clearances the layer turned into reviews
    NEW CLEAR  hits that became a clearance. Must be 0: no layer may create one
    right, unsafe, score   on the practice labels (score: 0 = all review, 100 = perfect)
    unstable   hits whose decision or reason code differed between the runs
    secs       seconds per run

--stress repeats the table on a copy of the data whose identity notes have lost their
capitals, which is where a model that reads text should earn its place.
Settings that need a language model are skipped unless OPENROUTER_API_KEY is set
(or SCREENING_MODEL=fake, for a dry run with a stand-in).
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "system"))
sys.path.insert(0, HERE)

from screening import layers  # noqa: E402
from screening.pipeline import Run  # noqa: E402
from screening.store import TABLES, read_jsonl  # noqa: E402

COST = {
    "DIFFERENT_ENTITY": {"DIFFERENT_ENTITY": 0, "SAME_ENTITY": 3, "REVIEW": 3},
    "SAME_ENTITY": {"DIFFERENT_ENTITY": 60, "SAME_ENTITY": 0, "REVIEW": 2},
    "REVIEW": {"DIFFERENT_ENTITY": 60, "SAME_ENTITY": 2, "REVIEW": 0},
}
SETTINGS = [  # (label, layer modes, needs a model)
    ("rules only", "none", False),
    ("score on", "none,score=on", False),
    ("score enforce", "none,score=enforce", False),
    ("briefing on", "none,briefing=on", False),
    ("reviewer on (shadow)", "none,reviewer=on", True),
    ("reviewer enforce", "none,reviewer=enforce", True),
    ("reader on (cautious)", "none,reader=on", True),
    ("reader enforce (trusted)", "none,reader=enforce", True),
    ("all on", "score=on,briefing=on,reviewer=on,reader=on", True),
]


def model_available():
    return bool(os.environ.get("OPENROUTER_API_KEY")) or os.environ.get("SCREENING_MODEL") == "fake"


def one_run(folder, modes):
    started = time.time()
    job = Run(folder, modes)
    job.warm(True)
    lines, notes = {}, {}
    for row in job.store.hits:
        line, note = job.process(row, explain=True)
        lines[line["hit_id"]] = line
        notes[line["hit_id"]] = note
    return lines, notes, time.time() - started, job


def label_score(lines, labels):
    cost = sum(COST[l["decision"]][lines.get(l["hit_id"], {}).get("decision", "REVIEW")] for l in labels)
    base = sum(COST[l["decision"]]["REVIEW"] for l in labels)
    right = sum(1 for l in labels if lines.get(l["hit_id"], {}).get("decision") == l["decision"])
    unsafe = sum(1 for l in labels if l["decision"] != "DIFFERENT_ENTITY"
                 and lines.get(l["hit_id"], {}).get("decision") == "DIFFERENT_ENTITY")
    return right, unsafe, (100.0 * max(0.0, 1 - cost / float(base)) if base else 0.0)


def table(folder, labels, runs, baseline=None, title=""):
    print("\n%s" % title)
    print("%-26s %4s %4s %4s | %7s %9s %9s | %5s %6s %5s | %8s %5s" % (
        "setting", "diff", "same", "rev", "changed", "to review", "NEW CLEAR", "right", "unsafe", "score", "unstable", "secs"))
    details, worst = [], 0
    for label, text, needs_model in SETTINGS:
        if needs_model and not model_available():
            print("%-26s skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)" % label)
            continue
        modes = layers.config(text)
        results = [one_run(folder, modes) for _ in range(runs if needs_model else 1)]
        lines, notes, _secs, job = results[0]
        if baseline is None:
            baseline = lines  # the first setting is the rules alone
        counts = Counter(l["decision"] for l in lines.values())
        changed = to_review = new_clear = 0
        for hit_id, before in baseline.items():
            a, b = before["decision"], lines[hit_id]["decision"]
            if a != b:
                changed += 1
                to_review += a == "DIFFERENT_ENTITY" and b == "REVIEW"
                new_clear += b == "DIFFERENT_ENTITY"
        unstable = sum(1 for hit_id in lines if len(set(
            (r[0][hit_id]["decision"], r[0][hit_id]["reason_code"]) for r in results)) > 1)
        right, unsafe, score = label_score(lines, labels)
        worst = max(worst, new_clear)
        print("%-26s %4d %4d %4d | %7d %9d %9d | %5d %6d %5.1f | %8s %5.1f" % (
            label, counts["DIFFERENT_ENTITY"], counts["SAME_ENTITY"], counts["REVIEW"], changed, to_review,
            new_clear, right, unsafe, score, unstable if len(results) > 1 else "-",
            sum(r[2] for r in results) / len(results)))
        people = [p for note in notes.values() if note for p in note["people"]]
        extra = []
        scored = [p["score"] for p in people if p.get("score")]
        if scored:
            bands = Counter(s["band"] for s in scored)
            extra.append("score bands: " + ", ".join("%s %d" % kv for kv in bands.most_common()))
            extra.append("clearances where the score leans the other way: %d" % sum(1 for s in scored if s.get("conflict")))
        briefed = [p["briefing"] for p in people if p.get("briefing")]
        if briefed:
            extra.append("briefings written: %d, with a caveat: %d" % (len(briefed), sum(1 for b in briefed if b.get("caveats"))))
        reviews = [p["review"] for p in people if p.get("review")]
        if reviews:
            extra.append("reviewer verdicts: " + ", ".join("%s %d" % kv for kv in Counter(r["verdict"] for r in reviews).most_common()))
        reader = job.resolver.read_note
        if hasattr(reader, "client"):
            try:
                extra.append("reader model calls: %s" % json.dumps(reader.client.stats(), sort_keys=True))
            except Exception:
                pass
        if job.problems:
            extra.append("notes: " + "; ".join(sorted(set(job.problems))[:3]))
        if extra:
            details.append((label, extra))
    for label, extra in details:
        print("  %s" % label)
        for item in extra:
            print("      %s" % item)
    print("new clearances created by any layer: %s" % ("none" if worst == 0 else "UP TO %d, investigate" % worst))
    return baseline


def damaged_copy(folder):
    """A copy of the data whose identity notes print the legal name in Title Case."""
    import stress
    tables = dict((name, read_jsonl(os.path.join(folder, name + ".jsonl"))) for name in TABLES)
    stress.reword_name(lambda name: name.title())(tables)
    out = tempfile.mkdtemp(prefix="ablate-")
    stress.write(out, tables)
    shutil.copy(os.path.join(folder, "name_variants.json"), out)
    return out


def main(argv):
    parser = argparse.ArgumentParser(description="Compare the layers, one setting per row.")
    parser.add_argument("data", help="the data folder, e.g. screening/dev")
    parser.add_argument("room", nargs="?", help="not needed; accepted so the two-folder form works")
    parser.add_argument("--runs", type=int, default=1, help="runs per model setting, to measure stability")
    parser.add_argument("--model", help="OpenRouter model ID for the model layers")
    parser.add_argument("--stress", action="store_true", help="also compare on notes that lost their capitals")
    args = parser.parse_args(argv[1:])
    if args.model:
        os.environ["SCREENING_MODEL"] = args.model
    labels = read_jsonl(os.path.join(args.data, "practice_labels.jsonl"))
    print("model: %s" % (os.environ.get("SCREENING_MODEL") or "default") if model_available() else "model: none available")
    clean = table(args.data, labels, args.runs, title="DATA AS GIVEN (compared with the rules alone)")
    if args.stress:
        folder = damaged_copy(args.data)
        try:
            table(folder, labels, args.runs, baseline=clean,
                  title="IDENTITY NOTES WITHOUT CAPITALS (compared with the rules on the data as given)")
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
