"""Stress test: reword the free text in a data folder and see what the decisions do.

    python tools/stress.py <dev folder> [<scratch folder>]

The unseen set has "free text worded differently". We cannot see it, so we damage
our own: names in identity notes lose their capitals, ages and countries are
rewritten, rows are shuffled. The test that matters is the last column: a hit that
was REVIEW or SAME_ENTITY must never turn into DIFFERENT_ENTITY because text became
harder to read. Reading less may cost reviews; it must not cost a clearance.

The last five cases add text instead of taking it away: capitals that are not the
legal name, a year that is not a birth date, words that make a support note read like
a failed check, a country written as a nationality. Reading wrong must not cost a
clearance either. The same wordings, on invented records, are in
system/tests/test_wording.py.
"""
import json
import os
import random
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system"))

from screening import countries as C  # noqa: E402
from screening import extract as X  # noqa: E402
from screening.pipeline import Run  # noqa: E402
from screening.store import TABLES, read_jsonl  # noqa: E402


def decisions(folder):
    job = Run(folder)
    return dict((row["hit_id"], job.decide_hit(row)) for row in job.store.hits)


def write(folder, tables):
    os.makedirs(folder, exist_ok=True)
    for name, rows in tables.items():
        with open(os.path.join(folder, name + ".jsonl"), "w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def reword_name(change):
    def apply(tables):
        for note in tables["notes"]:
            if note.get("channel") == "kyc":
                name = X._upper_name(note["text"])
                if name:
                    note["text"] = note["text"].replace(name, change(name))
    return apply


def drop_birth_words(tables):
    for note in tables["notes"]:
        if note.get("channel") == "kyc":
            note["text"] = re.sub(r"\b(born( on| in)?|DOB|date of birth|birth date)\b", "", note["text"], flags=re.I)


def blank_checks(tables):
    for note in tables["notes"]:
        if note.get("channel") == "kyc":
            note["text"] = "Onboarding team completed the identity check; details are on file."


def unlabel_checks(tables):
    for note in tables["notes"]:
        if note.get("channel") == "kyc":
            note["channel"] = "onboarding"


def reword_ages(tables):
    def swap(text):
        text = re.sub(r", (\d{2}), ", r" (aged \1) ", text)
        text = re.sub(r"\b(\d{2})[- ]year[- ]old\b", r"\1 yrs old", text)
        text = re.sub(r"\bwas (\d{2})\b", r"had reached the age of \1", text)
        return text
    for result in tables["search_results"]:
        result["snippet"] = swap(result["snippet"])
    for hit in tables["hits"]:
        if hit.get("profile_notes"):
            hit["profile_notes"] = swap(hit["profile_notes"])


def reword_countries(tables):
    swaps = [("United States", "USA"), ("United Kingdom", "UK"), ("Cote D'Ivoire", "Ivory Coast"),
             ("Netherlands", "Holland"), ("Russia", "Russian Federation"), ("South Korea", "Republic of Korea")]
    for note in tables["notes"]:
        for old, new in swaps:
            note["text"] = note["text"].replace(old, new)
    for result in tables["search_results"]:
        for old, new in swaps:
            result["snippet"] = result["snippet"].replace(old, new)


def shuffle_rows(tables):
    rng = random.Random(20261121)
    for rows in tables.values():
        rng.shuffle(rows)


def drop_optional_fields(tables):
    for row in tables["customers"]:
        for field in ("preferred_name", "login_name", "occupation", "employer", "last_kyc_refresh"):
            row.pop(field, None)
    for row in tables["hits"]:
        for field in ("best_matching_name", "first_name", "middle_name", "last_name", "details", "relationships", "subcategories"):
            row.pop(field, None)


# -- text that can be misread: these add words, where the cases above take them away --
def _support_notes(tables):
    return [note for note in tables["notes"] if note.get("channel") != "kyc" and note.get("text")]


def add_to_support_notes(sentence):
    def apply(tables):
        for note in _support_notes(tables):
            note["text"] = note["text"].rstrip() + " " + sentence
    return apply


def label_checks_in_capitals(tables):
    for note in tables["notes"]:
        if note.get("channel") == "kyc" and note.get("text"):
            note["text"] = "CHECK PASSED. " + note["text"]


def _nationality_words():
    """(pattern for a country's main name, its nationality word) for every country that
    has a nationality word the system reads in a sentence."""
    out = []
    for code, name in sorted(C.DISPLAY.items()):
        words = [d for d, c in C.DEMONYMS.items() if c == code and C.find_in_text(d, demonyms=True) == [code]]
        if words:
            out.append((re.compile(r"\b%s\b" % re.escape(name)), words[0].title()))
    return out


def countries_as_nationalities(tables):
    """'worked in Norway' becomes 'worked in Norwegian territory'."""
    swaps = _nationality_words()
    for note in _support_notes(tables):
        for pattern, word in swaps:
            note["text"] = pattern.sub(word + " territory", note["text"])


def add_unrelated_birth(tables):
    for hit in tables["hits"]:
        notes = hit.get("profile_notes") or ""
        if not X.profile_birth(notes)[0]:
            hit["profile_notes"] = "The listed person's sister was born in 1951.\n\n" + notes
    for result in tables["search_results"]:
        if not X.birth_from_text(result.get("snippet"), loose=True)[0]:
            result["snippet"] = (result.get("snippet") or "") + " The listed person's sister was born in 1951."


def add_unrelated_number(tables):
    for result in tables["search_results"]:
        if not X.birth_from_text(result.get("snippet"), loose=True)[0]:
            result["snippet"] = (result.get("snippet") or "") + " A fine of 61 million was imposed in May 2024."


CASES = [
    ("names in Title Case", [reword_name(lambda n: n.title())]),
    ("names in lower case", [reword_name(lambda n: n.lower())]),
    ("Title Case, no birth words", [reword_name(lambda n: n.title()), drop_birth_words]),
    ("checks say nothing", [blank_checks]),
    ("checks filed under another channel", [unlabel_checks]),
    ("ages reworded", [reword_ages]),
    ("countries reworded", [reword_countries]),
    ("rows shuffled", [shuffle_rows]),
    ("optional fields dropped", [drop_optional_fields]),
    ("support notes gain capitals", [add_to_support_notes("ATM PIN reset requested; identity confirmed on the call.")]),
    ("checks gain a status in capitals", [label_checks_in_capitals]),
    ("support notes gain a year", [add_to_support_notes("Date of birth on file confirmed; customer since 2019.")]),
    ("support notes read as failed checks", [add_to_support_notes("Could not finish the identity verification by SMS OTP.")]),
    ("countries as nationalities", [countries_as_nationalities]),
    ("prose gains a relative's birth", [add_unrelated_birth]),
    ("search gains a fine amount", [add_unrelated_number]),
]


def main(argv):
    source = argv[1]
    scratch = argv[2] if len(argv) > 2 else tempfile.mkdtemp(prefix="stress-")
    base = decisions(source)
    print("%-36s %8s %8s %8s %10s" % ("case", "same", "to rev.", "other", "NEW CLEAR"))
    worst = 0
    for label, steps in CASES:
        tables = dict((name, read_jsonl(os.path.join(source, name + ".jsonl"))) for name in TABLES)
        for step in steps:
            step(tables)
        folder = os.path.join(scratch, re.sub(r"\W+", "_", label))
        write(folder, tables)
        shutil.copy(os.path.join(source, "name_variants.json"), folder)
        got = decisions(folder)
        same = to_review = other = new_clear = 0
        for hit_id, before in base.items():
            a, b = before["decision"], got[hit_id]["decision"]
            if a == b:
                same += 1
            elif b == "DIFFERENT_ENTITY":
                new_clear += 1
            elif b == "REVIEW":
                to_review += 1
            else:
                other += 1
        worst = max(worst, new_clear)
        print("%-36s %8d %8d %8d %10d" % (label, same, to_review, other, new_clear))
        shutil.rmtree(folder, ignore_errors=True)
    print("\nnew clearances caused by harder text: %s" % ("none" if worst == 0 else "UP TO %d, investigate" % worst))
    return 1 if worst else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
