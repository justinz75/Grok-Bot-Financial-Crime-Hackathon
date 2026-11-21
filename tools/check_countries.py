"""Check the system's country table against an official ISO 3166 list.

    python tools/check_countries.py <iso3166.csv>

The CSV needs a header row with a name column, a two-letter code column and a
three-letter code column (any common naming: name, alpha-2, alpha-3, ...).
Prints every country the table lacks or resolves differently. Changes nothing.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "system"))

from screening import countries as C  # noqa: E402


def find_column(header, wanted):
    for index, name in enumerate(header):
        key = "".join(ch for ch in name.lower() if ch.isalnum())
        if any(key == w or key.startswith(w) for w in wanted):
            return index
    return None


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: python tools/check_countries.py <iso3166.csv>\n")
        return 2
    with open(argv[1], encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    header, rows = rows[0], rows[1:]
    name_col = find_column(header, ("name", "countryname", "englishshortname"))
    a2_col = find_column(header, ("alpha2", "iso2", "code2", "alpha2code"))
    a3_col = find_column(header, ("alpha3", "iso3", "code3", "alpha3code"))
    if None in (name_col, a2_col, a3_col):
        sys.stderr.write("could not find name, two-letter and three-letter columns in: %s\n" % header)
        return 2

    problems = 0
    for row in rows:
        if len(row) <= max(name_col, a2_col, a3_col):
            continue
        name, a2, a3 = row[name_col].strip(), row[a2_col].strip().upper(), row[a3_col].strip().upper()
        if not a2:
            continue
        if a2 not in C.ISO2:
            print("MISSING CODE   %s (%s) is not in our table" % (a2, name))
            problems += 1
            continue
        if C.ISO3.get(a3) != a2:
            print("THREE-LETTER   %s should be %s, we have %s" % (a3, a2, C.ISO3.get(a3)))
            problems += 1
        got = C.resolve(name)
        if got != a2:
            print("NAME           %r should be %s, we resolve it to %s" % (name, a2, got))
            problems += 1
    official = set(row[a2_col].strip().upper() for row in rows if len(row) > a2_col)
    for code in sorted(set(C.ISO2) - official):
        print("EXTRA CODE     %s (%s) is in our table but not in the list" % (code, C.name_of(code)))
    print("\n%d countries checked, %d problems" % (len(rows), problems))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
