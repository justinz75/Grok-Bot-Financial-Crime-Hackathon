"""The assurance pack: the controls a bank puts around automated alert clearing.

    python tools/assure.py DATA [--out FOLDER] [--rate 10] [--floor 5]

The scored system answers one question per hit. A bank that lets a system clear alerts
also has to show how the work is ordered, how the clearances are checked, how the name
rule behaves on spellings it has not seen, and exactly what was run. This tool produces
those things from one run. It reads what the system writes and decides nothing: no hit
changes its decision, and the scored file is never touched.

    1 alerts        every alert as CLOSED, REVIEW or ESCALATE. An alert closes only
                    when every hit in it is DIFFERENT_ENTITY               -> alerts.csv
    2 queue         the reviews and matches in the order to work them: a sanctions
                    listing before any other, evidence that leans towards the same
                    person before evidence that is open                    -> review_queue.csv
    3 QA sample     the clearances a second person should read: every one that
                    carries a risk flag, and a fixed share of the rest     -> qa_sample.csv
    4 reviews       the one missing fact behind each review, counted
    5 name rule     common spelling variations applied to the listed names, and how
                    often the policy's name rule still calls them the same name
    6 unused facts  what a listing holds that the policy does not use (identifiers,
                    gender, other scripts), and dates that cannot be right, counted
    7 manifest      SHA-256 of every input file, of the code and of the output, so a
                    decision can be traced to what produced it             -> manifest.json

Everything here is arithmetic on files: no model, no randomness, no clock. The sample
is chosen by the SHA-256 of each hit ID, so the same folder gives the same sample, and
nobody can tell beforehand which clearances will be read.

The order of work uses how serious a listing is. That is the bank's workload, not the
identity decision: policy principle 1 keeps seriousness out of the decision, and it
stays out. Files go to data/assurance/ by default, which git ignores.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from screening import dates as D  # noqa: E402
from screening import pipeline  # noqa: E402
from screening.names import NameRules  # noqa: E402
from screening.resolve import is_approved  # noqa: E402
from screening.store import find_folder, read_jsonl  # noqa: E402

DIFFERENT, SAME, REVIEW = "DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW"
CLOSED, ESCALATE, NO_HITS = "CLOSED", "ESCALATE", "NO_HITS"
SANCTIONS, OTHER = "sanctions", "other"
STRONG_SAME = "strong evidence of the same"   # the score layer's top band (docs/explain-format.md)
NARROW_GAP_YEARS = 3       # a date-of-birth clearance this close to the one-year tolerance is read
DEFAULT_RATE = 10          # per cent of the unflagged clearances that are read, per reason code
DEFAULT_FLOOR = 5          # and never fewer than this many per reason code
FLAGS = (                  # why a clearance is always read, in the order they are reported
    ("score_conflict", "the strength-of-evidence score leans towards the same person"),
    ("name_near_miss", "name is the only ground, and a looser matcher would call the names the same"),
    ("narrow_date_gap", "date of birth is the only ground, and the years are at most %d apart" % NARROW_GAP_YEARS),
    ("inferred_hit_date", "date of birth is the only ground, and the hit's date was read from notes or a search result"),
    ("declared_date_only", "date of birth is the only ground, and the customer's date is declared, not verified"),
    ("sanctions_one_ground", "a sanctions listing was cleared on a single ground"),
    ("several_people", "more than one customer fits the alert"),
)


# -- reading ------------------------------------------------------------------------
def listing(hit_row):
    """(tier, label) of a hit. The tier is 'sanctions' when any of its categories is a
    sanctions listing; the label is its primary category, or its first."""
    row = hit_row or {}
    categories = row.get("categories")
    if isinstance(categories, str):
        categories = [categories]
    names = [str(c).strip() for c in (categories or []) if str(c or "").strip()]
    primary = str(row.get("primary_category") or "").strip()
    label = primary or (names[0] if names else "unknown")
    tier = SANCTIONS if any(n.lower().startswith("sanction") for n in names + [primary]) else OTHER
    return tier, label


def people_of(explain_line):
    return [p for p in ((explain_line or {}).get("people") or []) if isinstance(p, dict)]


def bits_of(explain_line):
    """The strongest lean towards the same person among the people the alert may be
    about, in bits, or None when the score layer said nothing."""
    found = []
    for person in people_of(explain_line):
        bits = (person.get("score") or {}).get("bits")
        if isinstance(bits, (int, float)) and not isinstance(bits, bool):
            found.append(float(bits))
    return max(found) if found else None


def likely_same(explain_line):
    """Whether the evidence for the same person is strong: the score layer's top band
    when there is a score, otherwise a name and a date of birth that both agree. A name
    and a country alone are not enough: the name is why the hit exists."""
    people = people_of(explain_line)
    bands = [(p.get("score") or {}).get("band") for p in people]
    if any(bands):
        return STRONG_SAME in bands
    for person in people:
        st = person.get("states") or {}
        if st.get("name") == "agree" and st.get("dob") == "agree":
            return True
    return False


# -- 1 and 2: alerts and the order of work ---------------------------------------------
def disposition(decisions):
    """An alert closes only when every hit in it is DIFFERENT_ENTITY. One SAME_ENTITY
    sends it to compliance. Anything else waits for a person."""
    decisions = list(decisions)
    if not decisions:
        return NO_HITS
    if SAME in decisions:
        return ESCALATE
    if all(d == DIFFERENT for d in decisions):
        return CLOSED
    return REVIEW


def priority(decision, tier, strong):
    """P1 to P4: what a wrong answer would cost (a sanctions listing or not) against
    how likely the hit is the customer (a match or strong evidence, or still open)."""
    likely = decision == SAME or bool(strong)
    if tier == SANCTIONS and likely:
        return "P1"
    if tier == SANCTIONS or decision == SAME:
        return "P2"
    if likely:
        return "P3"
    return "P4"


def review_cause(scored_line, explain_line):
    """The one thing that keeps a review open, by a fixed order of questions."""
    explain_line = explain_line or {}
    if explain_line.get("changed_by"):
        return "a layer asked for a person to look at a clearance"
    if scored_line.get("reason_code") == "AMBIGUOUS_CUSTOMER_RECORD":
        return "several customers fit and they lead to different decisions"
    people = people_of(explain_line)
    if not people:
        return "the hit could not be compared"
    person = people[0]
    if not person.get("record_ids"):
        return "no customer record fits the alert"
    st, customer, hit = person.get("states") or {}, person.get("customer") or {}, person.get("hit") or {}
    name, dob, location = st.get("name"), st.get("dob"), st.get("location")
    company = customer.get("kind") == "company"
    if name == "agree" and dob == "agree" and location == "mismatch":
        return "name and date agree but no country is shared"
    if name != "agree":
        return "the name cannot be confirmed against the listing"
    if company:
        return "no country ties the company to the listing"
    if not hit.get("dobs"):
        return "the listing gives no date of birth"
    if not customer.get("dob"):
        return "the customer has no date of birth on file"
    return "the dates of birth neither agree nor contradict"


# -- 3: the clearances a second person reads -------------------------------------------
def _edits(a, b, swaps):
    """Edits between two words. With swaps, two neighbouring letters that change places
    count as one edit; the policy counts them as two."""
    rows = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        rows[i][0] = i
    for j in range(len(b) + 1):
        rows[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            best = min(rows[i - 1][j] + 1, rows[i][j - 1] + 1, rows[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if swaps and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                best = min(best, rows[i - 2][j - 2] + 1)
            rows[i][j] = best
    return rows[len(a)][len(b)]


class Challenger(NameRules):
    """The policy's name rule with the slack an off-the-shelf screening matcher adds: a
    swap of two neighbouring letters is one edit, longer parts get one more edit, and a
    short form matches the name it begins ('alex', 'alexander'). It decides nothing. It
    marks the name clearances that a looser matcher would not have made."""

    def part_match(self, a, b):
        if NameRules.part_match(self, a, b):
            return True
        shorter = min(len(a), len(b))
        if shorter < 4:
            return False
        if a.startswith(b) or b.startswith(a):
            return True
        limit = 1 if shorter <= 6 else 2
        if _edits(a, b, True) <= limit:
            return True
        return shorter >= 5 and _edits(a, b, False) <= limit + 1


def _year(text):
    try:
        return int(str(text)[:4])
    except (TypeError, ValueError):
        return None


def _year_gap(person):
    mine = _year((person.get("customer") or {}).get("dob"))
    theirs = [y for y in (_year(d) for d in ((person.get("hit") or {}).get("dobs") or [])) if y is not None]
    if mine is None or not theirs:
        return None
    return min(abs(mine - y) for y in theirs)


def name_near_miss(person, challenger):
    """True when the verified legal name and one of the hit's names agree under the
    looser matcher. The policy's rule found that none agree, which is why it cleared."""
    customer, hit = person.get("customer") or {}, person.get("hit") or {}
    company = customer.get("kind") == "company"
    mine = challenger.parts(customer.get("verified_name"), company)
    if not mine:
        return False
    for name in [hit.get("name")] + list(hit.get("aliases") or []):
        theirs = challenger.parts(name, company)
        if theirs and challenger.agree(mine, theirs):
            return True
    return False


def qa_flags(scored_line, explain_line, tier, challenger=None):
    """Why this clearance is always read by a second person: the names of its risk
    flags, in the order of FLAGS. Empty when it has none."""
    found = set()
    people = people_of(explain_line)
    if scored_line.get("customer_record_id") == "AMBIGUOUS" or len(people) > 1:
        found.add("several_people")
    for person in people:
        codes = list(person.get("all_codes") or [])
        if not codes and person.get("reason_code"):
            codes = [person["reason_code"]]
        if (person.get("score") or {}).get("conflict"):
            found.add("score_conflict")
        if tier == SANCTIONS and len(codes) == 1:
            found.add("sanctions_one_ground")
        if codes == ["NAME_MISMATCH_VERIFIED"] and challenger is not None and name_near_miss(person, challenger):
            found.add("name_near_miss")
        if codes == ["DOB_MISMATCH"]:
            gap = _year_gap(person)
            if gap is not None and gap <= NARROW_GAP_YEARS:
                found.add("narrow_date_gap")
            if (person.get("hit") or {}).get("dob_origin") in ("notes", "search"):
                found.add("inferred_hit_date")
            source = str((person.get("customer") or {}).get("dob_source") or "")
            if not source.startswith(("KYC-", "NOTE-")):
                found.add("declared_date_only")
    return [name for name, _why in FLAGS if name in found]


def pick(hit_ids, rate, floor):
    """A fixed share of the hits, and never fewer than `floor`, in the order of the
    SHA-256 of each ID: the same hits on every run, with no pattern to them."""
    ordered = sorted(set(hit_ids), key=lambda h: (hashlib.sha256(h.encode("utf-8")).hexdigest(), h))
    want = max(int(floor), int(math.ceil(len(ordered) * float(rate) / 100.0)))
    return ordered[:min(len(ordered), want)]


def qa_sample(scored, explain, hit_rows, challenger=None, rate=DEFAULT_RATE, floor=DEFAULT_FLOOR):
    """[(hit_id, basis, flags)] for every clearance to be read. basis is 'flagged' when
    the clearance carries a risk flag, 'sampled' when it was drawn from the rest."""
    flagged, rest = {}, {}
    for line in scored:
        if line.get("decision") != DIFFERENT:
            continue
        hit_id = line.get("hit_id")
        flags = qa_flags(line, explain.get(hit_id), listing(hit_rows.get(hit_id))[0], challenger)
        if flags:
            flagged[hit_id] = flags
        else:
            rest.setdefault(line.get("reason_code"), []).append(hit_id)
    drawn = set()
    for code in sorted(rest, key=str):
        drawn.update(pick(rest[code], rate, floor))
    out = []
    for line in scored:
        hit_id = line.get("hit_id")
        if hit_id in flagged:
            out.append((hit_id, "flagged", flagged[hit_id]))
        elif hit_id in drawn:
            out.append((hit_id, "sampled", []))
    return out


# -- 5: the name rule under common variations ---------------------------------------------
def _longest(parts):
    return max(range(len(parts)), key=lambda i: (len(parts[i]), -i))


def _swap(word):
    """The word with two neighbouring letters changed over, starting from the middle."""
    middle = len(word) // 2
    for i in sorted(range(1, len(word)), key=lambda k: (abs(k - middle), k)):
        if word[i - 1] != word[i]:
            return word[:i - 1] + word[i] + word[i - 1] + word[i + 1:]
    return None


def _in_longest(change, least):
    """A variation that changes the longest part of a name, when it has `least` letters."""
    def apply(parts):
        i = _longest(parts)
        if len(parts[i]) < least:
            return None
        new = change(parts[i])
        if not new or new == parts[i]:
            return None
        return " ".join(parts[:i] + (new,) + parts[i + 1:])
    return apply


def _split(word):
    half = len(word) // 2
    return word[:half] + " " + word[half:]


VARIATIONS = (  # (what was done to the name, what it does to the parts, or None for "does not apply")
    ("capitals", lambda p: " ".join(p).upper()),
    ("surname first, with a comma", lambda p: "%s, %s" % (p[-1], " ".join(p[:-1]))),
    ("a middle initial added", lambda p: "%s Q. %s" % (p[0], " ".join(p[1:]))),
    ("a title added", lambda p: "Dr. " + " ".join(p)),
    ("first two parts written together", lambda p: " ".join((p[0] + p[1],) + p[2:])),
    ("longest part written apart", _in_longest(_split, 6)),
    ("one letter doubled", _in_longest(lambda w: w[:len(w) // 2] + w[len(w) // 2 - 1] + w[len(w) // 2:], 4)),
    ("one letter changed", _in_longest(lambda w: w[:len(w) // 2] + ("q" if w[len(w) // 2] != "q" else "z") + w[len(w) // 2 + 1:], 4)),
    ("one letter dropped", _in_longest(lambda w: w[:len(w) // 2] + w[len(w) // 2 + 1:], 4)),
    ("two neighbouring letters swapped", _in_longest(_swap, 4)),
    ("two letters dropped", _in_longest(lambda w: w[:len(w) // 2 - 1] + w[len(w) // 2 + 1:], 5)),
    ("first part cut to an initial", lambda p: "%s. %s" % (p[0][0], " ".join(p[1:]))),
    ("one part left out", lambda p: " ".join(p[1:])),
    ("first part replaced by another name", lambda p: " ".join(("zyxquv",) + p[1:])),
)


def name_rule_test(names, rules):
    """[(variation, names it applies to, how many still agree, the same two counts for
    names of exactly two parts)] for person names with at least two real parts. Each
    variation is applied once, in a fixed place.

    Two-part names are counted on their own because they are where one changed part
    decides the answer: a longer name still has two parts that match."""
    seen, pool = set(), []
    for name in names:
        parts = rules.parts(name)
        if len(parts) >= 2 and parts not in seen:
            seen.add(parts)
            pool.append(parts)
    out = []
    for label, vary in VARIATIONS:
        applies = agrees = applies_two = agrees_two = 0
        for parts in pool:
            try:
                changed = vary(parts)
            except (IndexError, ValueError):
                changed = None
            if not changed:
                continue
            same = rules.agree(parts, rules.parts(changed))
            applies += 1
            agrees += 1 if same else 0
            if len(parts) == 2:
                applies_two += 1
                agrees_two += 1 if same else 0
        out.append((label, applies, agrees, applies_two, agrees_two))
    return out


# -- 6: what the listings hold that the policy does not use ----------------------------------
def _plain(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _other_script(value):
    """True when a name has a letter that is not Latin."""
    return any(ch.isalpha() and not unicodedata.name(ch, "LATIN").startswith("LATIN") for ch in str(value or ""))


def _values(value):
    if isinstance(value, (list, tuple)):
        return [v for v in value if v not in (None, "")]
    return [value] if value not in (None, "") else []


def unused_facts(folder, hit_rows, explain):
    """[(what was counted, how many)]: facts a screening engine would weigh that the
    bank's policy leaves out, and data that cannot be right. They are counted so that
    leaving them out of the decision rests on a number and not on an assumption."""
    checks = read_jsonl(os.path.join(folder, "kyc_checks.jsonl"))
    customers = read_jsonl(os.path.join(folder, "customers.jsonl"))
    held = set(_plain(row.get("document_number")) for row in checks)
    held.update(_plain(row.get("registration_number")) for row in customers)
    held = set(n for n in held if len(n) >= 5)
    with_identifier = shared = gender = no_death_date = alias_script = name_script = 0
    for hit in hit_rows.values():
        numbers = [_plain(str(item).partition(":")[2] or item) for item in _values(hit.get("identifiers"))]
        numbers = [n for n in numbers if len(n) >= 5]
        with_identifier += 1 if numbers else 0
        shared += 1 if any(n in held for n in numbers) else 0
        gender += 1 if str(hit.get("gender") or "").strip() else 0
        status = str(hit.get("life_status") or "").lower()
        if ("dece" in status or "dead" in status) and not str(hit.get("deceased_date") or "").strip():
            no_death_date += 1
        alias_script += 1 if any(_other_script(a) for a in _values(hit.get("aliases"))) else 0
        name_script += 1 if _other_script(hit.get("name")) else 0
    impossible = set()
    for row in checks:
        born, checked = D.parse_date(row.get("verified_dob")), D.parse_date(row.get("checked_at"))
        if is_approved(row) and born and checked and not D.surely_before(born, checked):
            impossible.add(str(row.get("check_id")))
    resting = 0
    for line in explain.values():
        for person in people_of(line):
            source = (person.get("customer") or {}).get("dob_source")
            used = (person.get("states") or {}).get("dob") in ("agree", "mismatch") or "TEMPORAL_IMPOSSIBILITY" in (person.get("all_codes") or [])
            resting += 1 if source in impossible and used else 0
    return [
        ("hits that carry an identifier (passport, tax or registration number)", with_identifier),
        ("  of those, equal to a document or registration number the bank holds", shared),
        ("hits that give a gender", gender),
        ("customer records that give a gender", sum(1 for row in customers if str(row.get("gender") or "").strip())),
        ("hits marked deceased that give no date of death", no_death_date),
        ("hits with an alias written in another script", alias_script),
        ("hits whose own name is written in another script", name_script),
        ("verified legal names written in another script", sum(1 for row in checks if _other_script(row.get("verified_name")))),
        ("approved checks whose verified date is not before the check itself", len(impossible)),
        ("  comparisons whose date of birth rests on such a check", resting),
    ]


# -- 7: what was run -----------------------------------------------------------------------
def sha256_file(path, text=False):
    """SHA-256 of a file. For code, line endings are read as Unix so that a Windows
    checkout and a Linux one give the same digest."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        if text:
            digest.update(handle.read().replace(b"\r\n", b"\n"))
        else:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def code_digest(root=None):
    """(one SHA-256 over the code that decides, how many files): system/run, the layer
    settings file when there is one, and everything under system/screening/. The README
    and the tests are left out, so editing them does not change what the code is called."""
    base = os.path.join(root or ROOT, "system")
    paths = [os.path.join(base, name) for name in ("layers.json", "run") if os.path.isfile(os.path.join(base, name))]
    for folder, folders, files in os.walk(os.path.join(base, "screening")):
        folders[:] = sorted(f for f in folders if f != "__pycache__")
        paths += [os.path.join(folder, name) for name in sorted(files) if not name.endswith((".pyc", ".pyo"))]
    digest = hashlib.sha256()
    for path in paths:
        relative = os.path.relpath(path, base).replace(os.sep, "/")
        digest.update(relative.encode("utf-8") + b"\0" + sha256_file(path, text=True).encode("ascii") + b"\n")
    return digest.hexdigest(), len(paths)


def _git(*args):
    try:
        done = subprocess.run(("git",) + args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    return done.stdout.decode("utf-8", "replace").strip() if done.returncode == 0 else None


def manifest(folder, scored_path, explain_path, scored, explain):
    data = {}
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isfile(path) and name.endswith((".jsonl", ".json")):
            entry = {"sha256": sha256_file(path)}
            if name.endswith(".jsonl"):
                entry["rows"] = len(read_jsonl(path))
            data[name] = entry
    digest, count = code_digest()
    commit = _git("rev-parse", "HEAD")
    changed = _git("status", "--porcelain", "--", "system/run", "system/layers.json", "system/screening")
    modes = {}
    for line in explain.values():
        modes = line.get("layers") or {}
        break
    return {
        "data": data,
        "code": {"sha256": digest, "files": count, "git_commit": commit,
                 "matches_commit": None if changed is None else changed == ""},
        "layers": modes,
        "output": {"hits": len(scored), "decisions": dict(Counter(line.get("decision") for line in scored)),
                   "scored_sha256": sha256_file(scored_path), "explain_sha256": sha256_file(explain_path)},
    }


# -- the run -----------------------------------------------------------------------------------
def _share(part, whole):
    return "%.1f%%" % (100.0 * part / whole) if whole else "n/a"


def _csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def _rules_for(folder):
    path = os.path.join(folder, "name_variants.json")
    if not os.path.isfile(path):
        path = os.path.join(os.path.dirname(os.path.abspath(folder)), "name_variants.json")
    return NameRules.from_file(path), Challenger.from_file(path)


def build(folder, scored, explain_rows, rate=DEFAULT_RATE, floor=DEFAULT_FLOOR):
    """Everything the pack reports, from the data folder and the two files of one run.
    Returns (report lines, {file name: (header, rows)}, problems)."""
    hit_rows = dict((str(h.get("hit_id")), h) for h in read_jsonl(os.path.join(folder, "hits.jsonl")))
    alerts = read_jsonl(os.path.join(folder, "alerts.jsonl"))
    explain = dict((line.get("hit_id"), line) for line in explain_rows)
    by_hit = dict((line.get("hit_id"), line) for line in scored)
    rules, challenger = _rules_for(folder)
    out, files, problems = [], {}, []

    missing = sorted(h for h in hit_rows if h not in by_hit)
    extra = sorted(h for h in by_hit if h not in hit_rows)
    if missing:
        problems.append("%d hits have no line in the scored file; they count as REVIEW" % len(missing))
    if extra:
        problems.append("%d scored lines name a hit that is not in hits.jsonl" % len(extra))

    # 1 alerts
    hits_of = {}
    for hit_id in sorted(hit_rows):
        hits_of.setdefault(str(hit_rows[hit_id].get("alert_id")), []).append(hit_id)
    known = [str(a.get("alert_id")) for a in alerts]
    alert_ids = known + sorted(a for a in hits_of if a not in set(known))
    decided = Counter(line.get("decision") for line in scored)
    strong = dict((h, likely_same(explain.get(h))) for h in by_hit)
    rank = dict((h, priority(by_hit[h].get("decision"), listing(hit_rows.get(h))[0], strong[h])) for h in by_hit)
    alert_rows, states = [], Counter()
    for alert_id in alert_ids:
        ids = hits_of.get(alert_id, [])
        decisions = [by_hit[h].get("decision") if h in by_hit else REVIEW for h in ids]
        state = disposition(decisions)
        states[state] += 1
        open_ranks = sorted(rank[h] for h in ids if h in by_hit and by_hit[h].get("decision") != DIFFERENT)
        alert_rows.append([alert_id, state, open_ranks[0] if open_ranks else "", len(ids),
                           decisions.count(DIFFERENT), decisions.count(REVIEW), decisions.count(SAME)])
    files["alerts.csv"] = (["alert_id", "disposition", "priority", "hits", "different", "review", "same"], alert_rows)
    total = len(alert_ids)
    out += ["1 ALERTS", "   %d alerts with %d hits" % (total, len(hit_rows))]
    for state, meaning in ((CLOSED, "every hit is a different entity"), (REVIEW, "a person has to look"),
                           (ESCALATE, "a hit is the customer: to compliance"), (NO_HITS, "no hit to decide")):
        if states[state] or state != NO_HITS:
            out.append("   %-9s %5d  %6s   %s" % (state, states[state], _share(states[state], total), meaning))
    out.append("   hits cleared: %d of %d (%s)" % (decided[DIFFERENT], len(scored), _share(decided[DIFFERENT], len(scored))))

    # 2 the order of work
    queue = [h for h in by_hit if by_hit[h].get("decision") != DIFFERENT]
    queue.sort(key=lambda h: (rank[h], by_hit[h].get("decision") != SAME, -(bits_of(explain.get(h)) or 0.0), h))
    causes, queue_rows, by_rank = Counter(), [], Counter()
    for position, hit_id in enumerate(queue, 1):
        line = by_hit[hit_id]
        review = line.get("decision") == REVIEW
        cause = review_cause(line, explain.get(hit_id)) if review else ""
        if review:
            causes[cause] += 1
        by_rank[(rank[hit_id], line.get("decision"))] += 1
        bits = bits_of(explain.get(hit_id))
        queue_rows.append([position, rank[hit_id], "analyst" if review else "compliance", hit_id, line.get("alert_id"),
                           line.get("decision"), line.get("reason_code"), listing(hit_rows.get(hit_id))[1],
                           "" if bits is None else "%.1f" % bits, cause])
    files["review_queue.csv"] = (["position", "priority", "queue", "hit_id", "alert_id", "decision", "reason_code",
                                  "listing", "bits_towards_same", "what_keeps_it_open"], queue_rows)
    out += ["", "2 THE ORDER OF WORK", "   %d hits need a person: %d reviews and %d matches"
            % (len(queue), decided[REVIEW], decided[SAME])]
    meanings = {"P1": "sanctions listing: a match, or strong evidence of the same",
                "P2": "sanctions listing still open, or a match on another listing",
                "P3": "another listing, strong evidence of the same",
                "P4": "another listing, open"}
    for level in ("P1", "P2", "P3", "P4"):
        out.append("   %s %5d  (%d matches, %d reviews)   %s" % (
            level, by_rank[(level, SAME)] + by_rank[(level, REVIEW)], by_rank[(level, SAME)], by_rank[(level, REVIEW)],
            meanings[level]))

    # 3 the clearances a second person reads
    sample = qa_sample(scored, explain, hit_rows, challenger, rate, floor)
    flag_counts, per_code = Counter(), {}
    for line in scored:
        if line.get("decision") == DIFFERENT:
            per_code.setdefault(line.get("reason_code"), [0, 0, 0])[0] += 1
    sample_rows = []
    for hit_id, basis, flags in sample:
        line = by_hit[hit_id]
        per_code[line.get("reason_code")][1 if basis == "flagged" else 2] += 1
        flag_counts.update(flags)
        sample_rows.append([hit_id, line.get("alert_id"), line.get("reason_code"), listing(hit_rows.get(hit_id))[1],
                            basis, " ".join(flags)])
    files["qa_sample.csv"] = (["hit_id", "alert_id", "reason_code", "listing", "basis", "flags"], sample_rows)
    out += ["", "3 THE CLEARANCES A SECOND PERSON READS",
            "   every flagged clearance, and %d%% of the rest per reason code (never fewer than %d)" % (rate, floor),
            "   %-26s %9s %8s %8s %6s" % ("reason code", "cleared", "flagged", "sampled", "read")]
    sums = [0, 0, 0]
    for code in sorted(per_code, key=str):
        cleared, flagged, drawn = per_code[code]
        sums = [sums[0] + cleared, sums[1] + flagged, sums[2] + drawn]
        out.append("   %-26s %9d %8d %8d %6d" % (code, cleared, flagged, drawn, flagged + drawn))
    out.append("   %-26s %9d %8d %8d %6d  (%s of the clearances)" % (
        "all", sums[0], sums[1], sums[2], sums[1] + sums[2], _share(sums[1] + sums[2], sums[0])))
    for name, why in FLAGS:
        out.append("   %4d  %-21s %s" % (flag_counts[name], name, why))

    # 4 why hits wait for a person
    out += ["", "4 WHAT KEEPS A REVIEW OPEN", "   %d reviews, each counted once, by the first question it fails" % decided[REVIEW]]
    for cause, count in sorted(causes.items(), key=lambda item: (-item[1], item[0])):
        out.append("   %5d  %6s   %s" % (count, _share(count, decided[REVIEW]), cause))

    # 5 the name rule
    people_names = [h.get("name") for h in hit_rows.values() if str(h.get("entity_type") or "").lower() != "company"]
    tested = name_rule_test(people_names, rules)
    out += ["", "5 THE NAME RULE UNDER COMMON VARIATIONS",
            "   listed names of people, each changed once; how often the policy's rule still agrees",
            "   %-36s %17s    %23s" % ("", "every name", "names of two parts"),
            "   %-36s %6s %6s %7s %8s %6s %7s" % ("variation", "names", "agree", "share", "names", "agree", "share")]
    for label, applies, agrees, applies_two, agrees_two in tested:
        out.append("   %-36s %6d %6d %7s %8d %6d %7s" % (
            label, applies, agrees, _share(agrees, applies), applies_two, agrees_two, _share(agrees_two, applies_two)))

    # 6 what the listings hold that the policy does not use
    out += ["", "6 WHAT THE LISTINGS HOLD THAT THE POLICY DOES NOT USE"]
    for label, count in unused_facts(folder, hit_rows, explain):
        out.append("   %6d  %s" % (count, label))
    return out, files, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Alert dispositions, the order of work, a QA sample, and a manifest.")
    parser.add_argument("data", help="the screening/dev folder")
    parser.add_argument("--out", default=os.path.join(ROOT, "data", "assurance"), help="where the files go")
    parser.add_argument("--rate", type=int, default=DEFAULT_RATE, help="per cent of unflagged clearances to read")
    parser.add_argument("--floor", type=int, default=DEFAULT_FLOOR, help="fewest to read per reason code")
    args = parser.parse_args(argv)

    folder = find_folder(args.data)
    scratch = tempfile.mkdtemp(prefix="assure-")
    scored_path, explain_path = os.path.join(scratch, "scored.jsonl"), os.path.join(scratch, "explain.jsonl")
    try:
        pipeline.run(folder, scored_path, explain_path)   # the same entry point system/run calls
        scored, explain_rows = read_jsonl(scored_path), read_jsonl(explain_path)
        report, files, problems = build(folder, scored, explain_rows, args.rate, args.floor)
        record = manifest(folder, scored_path, explain_path, scored, dict((l.get("hit_id"), l) for l in explain_rows))
    finally:
        for path in (scored_path, explain_path):
            if os.path.isfile(path):
                os.remove(path)
        os.rmdir(scratch)

    report += ["", "7 WHAT WAS RUN",
               "   code    system/run and system/screening %s (%d files), commit %s%s" % (
                   record["code"]["sha256"][:16], record["code"]["files"],
                   (record["code"]["git_commit"] or "unknown")[:7],
                   "" if record["code"]["matches_commit"] in (True, None) else ", with uncommitted changes"),
               "   data    %d files, hashed one by one in manifest.json" % len(record["data"]),
               "   output  scored file %s" % record["output"]["scored_sha256"]]
    for problem in problems:
        report.append("PROBLEM: %s" % problem)

    if not os.path.isdir(args.out):
        os.makedirs(args.out)
    for name, (header, rows) in sorted(files.items()):
        _csv(os.path.join(args.out, name), header, rows)
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    with open(os.path.join(args.out, "summary.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(report) + "\n")
    print("\n".join(report))
    print("\nfiles: %s" % ", ".join(sorted(list(files) + ["manifest.json", "summary.txt"])))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
