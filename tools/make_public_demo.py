"""Build the local OpenSanctions demo from a downloaded CSV and name variants."""

import argparse
import calendar
import csv
import json
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "data"
PERSON_COUNT = 6
TABLES = ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks",
          "notes", "search_results")
REQUIRED_COLUMNS = {"id", "schema", "name", "aliases", "birth_date", "countries"}
SCREENED_AT = "2026-11-21"


def split_values(value):
    return [part.strip() for part in value.split(";") if part.strip()]


def select_people(csv_path):
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(rows.fieldnames or ())
        if missing:
            raise ValueError("sanctions CSV is missing columns: " + ", ".join(sorted(missing)))
        eligible = [row for row in rows if row["schema"] == "Person"
                    and split_values(row["birth_date"]) and split_values(row["countries"])]

    people = sorted(eligible, key=lambda row: row["id"])[:PERSON_COUNT]
    if len(people) != PERSON_COUNT:
        raise ValueError(f"sanctions CSV has only {len(people)} eligible people, need {PERSON_COUNT}")
    return people


def twenty_years_later(dob):
    # OpenSanctions can give a year, a year and month, or a full ISO date.
    parts = dob.split("-")
    year = int(parts[0]) + 20
    parts[0] = f"{year:04d}"
    if len(parts) == 3:
        last_day = calendar.monthrange(year, int(parts[1]))[1]
        parts[2] = f"{min(int(parts[2]), last_day):02d}"
    return "-".join(parts)


def build_tables(people):
    tables = {name: [] for name in TABLES}
    for index, person in enumerate(people):
        name = person["name"]
        aliases = split_values(person["aliases"])
        dobs = split_values(person["birth_date"])
        countries = split_values(person["countries"].upper())
        country = countries[0]

        for offset, dob in enumerate((dobs[0], twenty_years_later(dobs[0]), None)):
            serial = index * 3 + offset
            suffix = f"{0xA1 + serial:06X}"
            alert_id = f"A-{suffix}"
            hit_id = f"H-{suffix}"
            customer_id = f"CUS-{serial + 1:06d}"
            account_id = f"ACC-{suffix}"
            applicant_id = f"APP-{suffix}"

            # The runner emits one decision per hit. Each alert gets its own copy
            # of the selected profile so it can be compared to a different customer.
            tables["hits"].append({
                "hit_id": hit_id, "alert_id": alert_id, "entity_type": "Individual",
                "name": name, "aliases": aliases, "dobs": dobs, "countries": countries,
                "categories": ["Sanctions"], "primary_category": "Sanctions",
            })
            tables["alerts"].append({
                "alert_id": alert_id, "screened_at": SCREENED_AT, "account_ref": account_id,
                "hit_ids": [hit_id],
                "customer": {"name": name, "entity_type": "Individual", "dob": dob,
                             "country": country},
            })
            tables["customers"].append({
                "record_id": customer_id, "entity_type": "Individual", "full_name": name,
                "dob": dob, "residence_country": country,
            })
            tables["accounts"].append({"account_id": account_id, "customer_id": customer_id})
            tables["onboarding"].append({
                "account_id": account_id, "customer_id": customer_id,
                "kyc_applicant_id": applicant_id,
            })
            tables["kyc_checks"].append({
                "check_id": f"KYC-{suffix}", "applicant_id": applicant_id,
                "verified_name": name, "verified_dob": dob, "document_country": country,
                "document_number": f"DEMO-{suffix}", "result": "approved",
                "checked_at": SCREENED_AT,
            })
    return tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev-dir", type=Path, default=DATA / "screening" / "dev",
                        help="screening dev folder containing name_variants.json")
    args = parser.parse_args()
    out = DATA / "public_demo"

    try:
        variants = (args.dev_dir / "name_variants.json").read_bytes()
        tables = build_tables(select_people(DATA / "public" / "sanctions.csv"))
        out.mkdir(parents=True, exist_ok=True)
        for name, rows in tables.items():
            with (out / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        (out / "name_variants.json").write_bytes(variants)
    except (OSError, ValueError, csv.Error) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")

    print(f"Wrote {len(tables['hits'])} demo cases from {PERSON_COUNT} OpenSanctions profiles to {out}")


if __name__ == "__main__":
    main()
