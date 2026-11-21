"""Test the system on real public sanctions profiles, with answers known by construction.

    python tools/public_test.py [--people 2000] [--companies 1000] [--out data/public_test]

The development set is 819 hits written for the hackathon. This runs the same system on
profiles from a real consolidated sanctions list: names in many scripts and orders, partial
birth dates, several dates and countries on one profile. The list is the OpenSanctions export
described in docs/data-sources.md, saved as data/public/sanctions.csv. It stays local.

Profiles are taken at even steps through the list in ID order, so the same list gives the same
sample. For each one the script invents customers whose right answer follows from how they
were built, then runs `system/run` on the folder and counts how many came out as built:

    people      same            the profile's own name, first birth date and first country
                other date      born twenty years after the latest date the profile lists
                no date         the customer has no date of birth
                other country   same name and date, a country the profile does not list
                dateless hit    the profile with its dates removed, customer in another country
                dateless, home  the profile with its dates removed, customer in the same country
                other name      the verified legal name of an unrelated profile
    companies   same            the profile's own name and first country
                other country   same name, a country the profile does not list
                a person        a person of the same name against the listed organisation

A person's name must have two real parts before the policy can confirm it, so profiles with a
one-part name are counted apart: their customers may be cleared on a date and never confirmed.

Some profiles list a birth year from another calendar, or an impossible one, before the usual
one. A bank would not hold such a date, and the system does not read it as a date of birth, so
the invented customer gets the first date between 1900 and the screening year. The hit keeps
every date the profile lists. A profile with no such date is left out and counted.

The number that matters is the last column. A customer built to be the listed person, or one
the policy cannot decide, must never come out as DIFFERENT_ENTITY. Exit code 1 if one does.
"""
import argparse
import calendar
import csv
import json
import os
import subprocess
import sys
import time
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "system"))

from screening.names import NameRules  # noqa: E402  (the system's own count of real name parts)
from screening.textutil import fold  # noqa: E402

RUN = os.path.join(ROOT, "system", "run")
LIST = os.path.join(ROOT, "data", "public", "sanctions.csv")
TABLES = ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks", "notes", "search_results")
ORGANISATIONS = ("Company", "Organization", "LegalEntity")
ELSEWHERE = ("IS", "NZ", "UY", "BW", "MN")   # a country to move a customer to: the first the profile does not list
SCREENED_AT = "2026-11-21"
SAME, DIFFERENT, REVIEW = "SAME_ENTITY", "DIFFERENT_ENTITY", "REVIEW"

# scenario -> (what was built, the answer that follows)
PEOPLE = OrderedDict([
    ("same", (SAME, "NAME_DOB_MATCH")),
    ("other date", (DIFFERENT, "DOB_MISMATCH")),
    ("no date", (REVIEW, "INSUFFICIENT_DATA")),
    ("other country", (REVIEW, "INSUFFICIENT_DATA")),
    ("dateless hit", (DIFFERENT, "LOCATION_MISMATCH")),
    ("dateless, home", (REVIEW, "INSUFFICIENT_DATA")),
    ("other name", (DIFFERENT, "NAME_MISMATCH_VERIFIED")),
])
# With a one-part name the policy can neither confirm nor clear on the name.
ONE_PART = OrderedDict([
    ("same", (REVIEW, "INSUFFICIENT_DATA")),
    ("other date", (DIFFERENT, "DOB_MISMATCH")),
    ("no date", (REVIEW, "INSUFFICIENT_DATA")),
    ("other country", (REVIEW, "INSUFFICIENT_DATA")),
    ("dateless hit", (DIFFERENT, "LOCATION_MISMATCH")),
    ("dateless, home", (REVIEW, "INSUFFICIENT_DATA")),
])
COMPANIES = OrderedDict([
    ("same", (SAME, "NAME_LOCATION_MATCH")),
    ("other country", (DIFFERENT, "LOCATION_MISMATCH")),
    ("a person", (DIFFERENT, "ENTITY_TYPE_MISMATCH")),
])


def values(text):
    return [part.strip() for part in (text or "").split(";") if part.strip()]


def spread(rows, count):
    """`count` rows at even steps through the list, which is in ID order."""
    if count >= len(rows):
        return list(rows)
    return [rows[int(index * len(rows) / float(count))] for index in range(count)]


def latest(dobs):
    return max(dobs, key=lambda dob: tuple(int(part) for part in dob.split("-")))


def twenty_years_later(dob):
    parts = dob.split("-")
    year = int(parts[0]) + 20
    parts[0] = "%04d" % year
    if len(parts) == 3:
        parts[2] = "%02d" % min(int(parts[2]), calendar.monthrange(year, int(parts[1]))[1])
    return "-".join(parts)


def is_date(text):
    parts = text.split("-")
    return 1 <= len(parts) <= 3 and all(part.isdigit() for part in parts) and len(parts[0]) == 4


def usable(dob):
    """A date a bank could hold for a living customer."""
    return 1900 <= int(dob.split("-")[0]) <= int(SCREENED_AT[:4])


def words(name):
    return set(fold(name).replace(",", " ").split())


def read_list(path):
    csv.field_size_limit(10 ** 9)
    people, companies = [], []
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            countries = [code.upper() for code in values(row["countries"])]
            if not row["name"].strip() or not countries:
                continue
            profile = {"id": row["id"], "name": row["name"].strip(), "aliases": values(row["aliases"]),
                       "countries": countries, "dobs": [d for d in values(row["birth_date"]) if is_date(d)]}
            if row["schema"] == "Person" and profile["dobs"]:
                people.append(profile)
            elif row["schema"] in ORGANISATIONS:
                companies.append(profile)
    key = lambda profile: profile["id"]  # noqa: E731
    return sorted(people, key=key), sorted(companies, key=key)


class Builder(object):
    def __init__(self):
        self.tables = dict((name, []) for name in TABLES)
        self.cases = OrderedDict()   # hit ID -> (group, scenario, expected decision, expected code)
        self.serial = 0

    def case(self, group, scenario, expected, profile, kind, name, dob, country, hit_kind=None, hit_dobs=None):
        """One alert, one hit, one customer with an approved identity check."""
        self.serial += 1
        suffix = "%06X" % self.serial
        hit_id, alert_id, customer_id = "H-" + suffix, "A-" + suffix, "CUS-%06d" % self.serial
        account_id, applicant_id = "ACC-" + suffix, "APP-" + suffix
        self.tables["hits"].append({
            "hit_id": hit_id, "alert_id": alert_id, "entity_type": hit_kind or kind, "name": profile["name"],
            "aliases": profile["aliases"], "dobs": profile["dobs"] if hit_dobs is None else hit_dobs,
            "countries": profile["countries"], "categories": ["Sanctions"], "primary_category": "Sanctions"})
        self.tables["alerts"].append({
            "alert_id": alert_id, "screened_at": SCREENED_AT, "account_ref": account_id, "hit_ids": [hit_id],
            "customer": {"name": name, "entity_type": kind, "dob": dob, "country": country}})
        self.tables["customers"].append({"record_id": customer_id, "entity_type": kind, "full_name": name,
                                         "dob": dob, "residence_country": country})
        self.tables["accounts"].append({"account_id": account_id, "customer_id": customer_id})
        self.tables["onboarding"].append({"account_id": account_id, "customer_id": customer_id,
                                          "kyc_applicant_id": applicant_id})
        self.tables["kyc_checks"].append({
            "check_id": "KYC-" + suffix, "applicant_id": applicant_id, "verified_name": name, "verified_dob": dob,
            "document_country": country, "document_number": "TEST-" + suffix, "result": "approved",
            "checked_at": SCREENED_AT})
        self.cases[hit_id] = (group, scenario) + expected

    def person(self, profile, stranger, two_parts):
        name, home = profile["name"], profile["countries"][0]
        held = [d for d in profile["dobs"] if usable(d)]
        dob = held[0]
        away = [code for code in ELSEWHERE if code not in profile["countries"]][0]
        group, plan = ("people", PEOPLE) if two_parts else ("people, one-part name", ONE_PART)
        built = {
            "same": (name, dob, home, None),
            "other date": (name, twenty_years_later(latest(held)), home, None),
            "no date": (name, None, home, None),
            "other country": (name, dob, away, None),
            "dateless hit": (name, dob, away, []),
            "dateless, home": (name, dob, home, []),
            "other name": (stranger, dob, home, None),
        }
        for scenario, expected in plan.items():
            who, born, country, hit_dobs = built[scenario]
            if who is not None:
                self.case(group, scenario, expected, profile, "Individual", who, born, country, hit_dobs=hit_dobs)

    def company(self, profile):
        name, home = profile["name"], profile["countries"][0]
        away = [code for code in ELSEWHERE if code not in profile["countries"]][0]
        self.case("companies", "same", COMPANIES["same"], profile, "Company", name, None, home)
        self.case("companies", "other country", COMPANIES["other country"], profile, "Company", name, None, away)
        self.case("companies", "a person", COMPANIES["a person"], profile, "Individual", name, "1980-01-01", home,
                  hit_kind="Company")

    def write(self, folder, variants):
        os.makedirs(folder, exist_ok=True)
        for name, rows in self.tables.items():
            with open(os.path.join(folder, name + ".jsonl"), "w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "name_variants.json"), "wb") as handle:
            handle.write(variants)


def unrelated(profiles, index):
    """The name of another sampled profile that shares no word with this one's names."""
    mine = set()
    for name in [profiles[index]["name"]] + profiles[index]["aliases"]:
        mine |= words(name)
    for step in range(1, 12):
        other = profiles[(index + step * 7) % len(profiles)]
        if other is not profiles[index] and not (words(other["name"]) & mine):
            return other["name"]
    return None


def default_dev_dir():
    for folder in (os.path.join(ROOT, "data", "room", "screening", "dev"), os.path.join(ROOT, "data", "screening", "dev")):
        if os.path.isfile(os.path.join(folder, "name_variants.json")):
            return folder
    return os.path.join(ROOT, "data", "room", "screening", "dev")


def main(argv):
    parser = argparse.ArgumentParser(description="Run the system on real public sanctions profiles.")
    parser.add_argument("--people", type=int, default=2000, help="person profiles to sample (default 2000)")
    parser.add_argument("--companies", type=int, default=1000, help="organisation profiles to sample (default 1000)")
    parser.add_argument("--out", default=os.path.join(ROOT, "data", "public_test"), help="where to build the folder")
    parser.add_argument("--dev-dir", default=default_dev_dir(), help="the folder holding name_variants.json")
    args = parser.parse_args(argv[1:])
    if not os.path.isfile(LIST):
        parser.exit(1, "no data/public/sanctions.csv: see docs/data-sources.md\n")
    variants_path = os.path.join(args.dev_dir, "name_variants.json")
    with open(variants_path, "rb") as handle:
        variants = handle.read()
    rules = NameRules.from_file(variants_path)

    people, companies = read_list(LIST)
    listed = len(people)
    people = [profile for profile in people if any(usable(d) for d in profile["dobs"])]
    sample, firms = spread(people, args.people), spread(companies, args.companies)
    other_calendar = sum(1 for profile in sample if not usable(profile["dobs"][0]))
    builder = Builder()
    one_part = 0
    for index, profile in enumerate(sample):
        two_parts = len(rules.parts(profile["name"], False)) >= 2
        one_part += 0 if two_parts else 1
        builder.person(profile, unrelated(sample, index) if two_parts else None, two_parts)
    for profile in firms:
        builder.company(profile)
    folder = os.path.join(args.out, "folder")
    builder.write(folder, variants)

    scored = os.path.join(args.out, "scored.jsonl")
    env = dict(os.environ, SCREENING_LAYERS="none")
    started = time.time()
    done = subprocess.run([sys.executable, RUN, folder, scored], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    seconds = time.time() - started
    if done.returncode != 0 or not os.path.isfile(scored):
        sys.stderr.write(done.stderr.decode("utf-8", "replace"))
        return 1
    with open(scored, encoding="utf-8") as handle:
        lines = [json.loads(line) for line in handle if line.strip()]
    if [line["hit_id"] for line in lines] != list(builder.cases):
        print("the scored file does not hold one line per hit, in order")
        return 1

    print("list: %d people with a birth date and a country, %d organisations with a country"
          % (listed, len(companies)))
    print("left out: %d people with no birth date between 1900 and %s. Of those sampled, %d list another date first"
          % (listed - len(people), SCREENED_AT[:4], other_calendar))
    print("sampled: %d people (%d with a one-part name) and %d organisations, %d hits, decided in %.1fs"
          % (len(sample), one_part, len(firms), len(lines), seconds))
    table, others, wrong = OrderedDict(), {}, []
    for line in lines:
        group, scenario, decision, code = builder.cases[line["hit_id"]]
        row = table.setdefault((group, scenario), {"expected": "%s %s" % (decision, code), "cases": 0, "built": 0,
                                                    "review": 0, "match": 0, "cleared": 0})
        row["cases"] += 1
        if line["decision"] == decision:
            row["built"] += 1
            if line["reason_code"] != code:
                others.setdefault((group, scenario), Counter())[line["reason_code"]] += 1
        elif line["decision"] == REVIEW:
            row["review"] += 1
        elif line["decision"] == SAME:
            row["match"] += 1
        else:
            row["cleared"] += 1
            wrong.append(line["hit_id"])
    print("\n%-22s %-15s %-38s %6s %8s %9s %8s %8s" % ("", "built as", "the answer that follows", "cases", "as built",
                                                         "to review", "to match", "CLEARED"))
    for (group, scenario), row in table.items():
        print("%-22s %-15s %-38s %6d %8d %9d %8d %8d" % (group, scenario, row["expected"], row["cases"], row["built"],
                                                          row["review"], row["match"], row["cleared"]))
    for (group, scenario), codes in others.items():
        print("as built, with another reason code: %s, %s: %s"
              % (group, scenario, ", ".join("%s %d" % item for item in sorted(codes.items()))))
    with open(os.path.join(args.out, "not_as_built.jsonl"), "w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            group, scenario, decision, code = builder.cases[line["hit_id"]]
            if line["decision"] != decision:
                handle.write(json.dumps(dict(line, built=[group, scenario, decision, code]), ensure_ascii=False) + "\n")
    total = len(lines)
    built = sum(row["built"] for row in table.values())
    print("\n%d of %d came out as built; %d went to review instead, %d to a match"
          % (built, total, sum(row["review"] for row in table.values()), sum(row["match"] for row in table.values())))
    print("cleared when it should not be: %d" % len(wrong))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
