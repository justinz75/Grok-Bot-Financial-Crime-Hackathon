"""Tests for the policy rules. Run from the repo root:  python -m unittest discover -s system/tests

Every name here is invented; none comes from the hackathon data.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from screening import countries as C  # noqa: E402
from screening import dates as D  # noqa: E402
from screening.decide import (  # noqa: E402
    AMBIGUOUS, COMPANY, DIFFERENT, PERSON, REVIEW, SAME, Customer, Hit, combine, decide,
)
from screening.names import NameRules  # noqa: E402

R = NameRules()


def d(text):
    return D.parse_date(text)


class Names(unittest.TestCase):
    def test_parts(self):
        self.assertEqual(R.parts("Okoro, Daniel"), ("okoro", "daniel"))
        self.assertEqual(R.parts("Hartley, Corinne D."), ("hartley", "corinne"))
        self.assertEqual(R.parts("Marta Velazco Ortega (AKA)"), ("marta", "velazco", "ortega"))
        self.assertEqual(R.parts("Jérôme Lefèvre"), ("jerome", "lefevre"))
        self.assertEqual(R.parts("O'Brien-Smith"), ("obrien", "smith"))
        self.assertEqual(R.parts("Ali Ali Khan"), ("ali", "khan"))  # each distinct part once

    def test_placeholders_are_not_parts(self):
        self.assertEqual(R.parts("MICHAŁ N/A N/A"), ("michal",))
        self.assertEqual(R.parts("BELLO 0000 0000"), ("bello",))
        self.assertEqual(R.parts("UNKNOWN FAROOQ"), ("farooq",))
        self.assertEqual(R.parts("HAYES NA"), ("hayes",))
        self.assertEqual(R.parts("Test XXX None"), ())

    def test_company_legal_forms(self):
        self.assertEqual(R.parts("K9 Bank AG", True), ("k9", "bank"))
        self.assertEqual(R.parts("QX Bank, N.A.", True), ("qx", "bank"))
        self.assertEqual(R.parts("Nordvik Bank A/S", True), ("nordvik", "bank"))
        self.assertEqual(R.parts("Harbour Transit Authority, Inc. (HTA)", True), ("harbour", "transit", "authority"))
        self.assertEqual(R.parts("Bank SA"), ("bank", "sa"))  # legal forms only drop for companies

    def test_part_match(self):
        self.assertTrue(R.part_match("muhammad", "mohamed"))       # listed together
        self.assertTrue(R.part_match("katarina", "katerina"))      # 1 edit, long part
        self.assertTrue(R.part_match("ortiga", "ortega"))          # 1 edit
        self.assertTrue(R.part_match("muller", "mueller"))
        self.assertFalse(R.part_match("smiht", "smith"))           # a swap is two edits
        self.assertFalse(R.part_match("lin", "lim"))               # under 4 letters: identical only
        self.assertFalse(R.part_match("mark", "markus"))           # 2 edits, shorter part is 4 letters
        self.assertFalse(R.part_match("john", "jonathan"))
        self.assertFalse(R.part_match("yusuf", "jose"))            # variant groups do not chain

    def test_agree(self):
        yes = [
            ("Abdulsalam Khan", "Abdul Salam Khan"), ("Abdulsalam", "Abdul Salam"),
            ("Muhammad Ali", "Mohamed Ali"), ("Li Wei", "Wei Li"),
            ("Marta Lopez Ortiga", "Marta Lopez Ortega"),
            ("Katarina Novak", "Katerina Novak"), ("Jerome Lefevre", "Jérôme Lefèvre"),
            ("SILVA PEDRO HENRIQUE", "SILVA, PEDRO HENRIQUE"), ("Al Karim", "Karim, Md Al"),
            ("AbdulKarim Ibrahim Musa", "Musa, Abdul Karim Ibrahim"),
            ("Zainab Bello", "Zainab"),                     # a single-part alias can agree
            ("Anna K. Petrova", "Anna Petrova"), ("Tom Okafor", "Thomas Okafor"),
        ]
        for a, b in yes:
            self.assertTrue(R.names_agree(a, b), (a, b))
        no = [  # one shared part is not enough when the shorter name has two
            ("CHIDI BELLO", "Rasheed, Bello"), ("Jonathan Cruz Hartley", "John Hartley"),
            ("MARKUS DIETER SCHMIDT", "Mark Schmidt"), ("LAURA BENNETT", "Bennett, James Jacob"),
            ("FARHANA RAHIM UDDIN", "Uddin, Md Saiful"), ("Joseph navarro", "Navarro, Bartolo Diego"),
            ("SAMUEL ORTIZ", "Ramirez Ortiz, Jesus Amable"), ("Lin Mei", "Lim Mei"),
        ]
        for a, b in no:
            self.assertFalse(R.names_agree(a, b), (a, b))

    def test_company_agree(self):
        self.assertTrue(R.names_agree("Marisol SA", "Marisol, Sociedad Anónima", True))
        self.assertTrue(R.names_agree("K9 Bank AG", "K9 Bank SE", True))
        self.assertFalse(R.names_agree("K9 Bank AG", "QX Bank, N.A.", True))

    def test_variants_file(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "variants_sample.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"description": "x", "groups": [["tony", "anthony"]], "company_legal_forms": ["ltd", "oy"]}')
        try:
            rules = NameRules.from_file(path)
        finally:
            os.remove(path)
        self.assertTrue(rules.part_match("tony", "anthony"))
        self.assertFalse(rules.part_match("muhammad", "mohd"))   # only the file's groups apply
        self.assertEqual(rules.parts("Kallio Oy", True), ("kallio",))
        self.assertTrue(NameRules.from_file("no-such-file.json").part_match("muhammad", "mohd"))  # built-in copy


class Dates(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(d("1989-02-07"), (1989, 2, 7))
        self.assertEqual(d("19/05/2004"), (2004, 5, 19))
        self.assertEqual(d("February 19, 2002"), (2002, 2, 19))
        self.assertEqual(d("20 August 1968"), (1968, 8, 20))
        self.assertEqual(d("Mar 5, 1990"), (1990, 3, 5))
        self.assertEqual(d("5th of March 1990"), (1990, 3, 5))
        self.assertEqual(d("1968-02"), (1968, 2, None))
        self.assertEqual(d("Mar 1990"), (1990, 3, None))
        self.assertEqual(d("1996"), (1996, None, None))
        self.assertEqual(d("1996.0"), None)
        self.assertEqual(d("31/02/1990"), None)
        self.assertEqual(d(""), None)
        self.assertEqual(D.parse_dates("1996; 1997"), [(1996, None, None), (1997, None, None)])
        self.assertEqual(D.parse_dates(["1996", "1997"]), [(1996, None, None), (1997, None, None)])
        self.assertEqual(len(D.parse_dates("1987-03-01; 1987-12-31; 1986-01-01; 1986; 1987; 1987-03-21")), 6)

    def test_compare(self):
        self.assertEqual(D.compare(d("1968-03-05"), D.parse_dates("1967; 1968")), "agree")
        self.assertEqual(D.compare(d("1979-11-08"), D.parse_dates("1976; 1977")), "mismatch")
        self.assertEqual(D.compare(d("1978-11-08"), D.parse_dates("1976; 1977")), "unknown")  # within 1 year
        self.assertEqual(D.compare(d("1968-02-17"), D.parse_dates("1968-02")), "agree")
        self.assertEqual(D.compare(d("1968-03-17"), D.parse_dates("1968-02")), "mismatch")    # months differ
        self.assertEqual(D.compare(d("1965-03-28"), D.parse_dates("1962-09-10")), "mismatch")
        self.assertEqual(D.compare(d("1975"), D.parse_dates("1975-06-01")), "agree")          # a year alone can agree
        self.assertEqual(D.compare(d("1994-05-14"), D.parse_dates("1994-05-14; 1995-04-28")), "agree")
        self.assertEqual(D.compare(d("1994-05-15"), D.parse_dates("1994-05-14; 1995-04-28")), "unknown")
        self.assertEqual(D.compare(None, D.parse_dates("1975")), "unknown")
        self.assertEqual(D.compare(d("1975"), []), "unknown")

    def test_age(self):
        self.assertEqual([y.year for y in D.birth_years_from_age(45, d("March 2019"))], [1973, 1974])
        self.assertEqual(D.max_age_on(d("2007"), d("2020-01-08")), 13)
        self.assertEqual(D.max_age_on(d("2004-06-30"), d("2020-06-29")), 15)
        self.assertEqual(D.max_age_on(d("2004-06-30"), d("2020-06-30")), 16)
        self.assertTrue(D.surely_before(d("2022-03"), d("2026-11-06")))
        self.assertFalse(D.surely_before(d("2026"), d("2026-11-06")))

    def test_find_in_sentences(self):
        found = D.find_dates("Formal charges were brought against Marta Lopez Ortega, aged 30, in November 1998.")
        self.assertEqual([f[0] for f in found], [(1998, 11, None)])
        found = D.find_dates("Kwame Mensah Boateng was born on 17 July 1939.")
        self.assertEqual([f[0] for f in found], [(1939, 7, 17)])
        found = D.find_dates("On 2024-03-16, the provider validated the national ID of ADA OBI, DOB 22/09/1956, from Nigeria.")
        self.assertEqual([f[0] for f in found], [(2024, 3, 16), (1956, 9, 22)])
        found = D.find_dates("Ibrahim Musa Garba was born in 1952.", bare_years=True)
        self.assertEqual([f[0] for f in found], [(1952, None, None)])


class Countries(unittest.TestCase):
    def test_resolve(self):
        for text, code in [("United States", "US"), ("US", "US"), ("GB", "GB"), ("British", "GB"),
                           ("Nigerian", "NG"), ("Cote D'Ivoire", "CI"), ("Côte d'Ivoire", "CI"),
                           ("Macao Special Administrative Region of China", "MO"), ("Palestina", "PS"),
                           ("Northern Mariana Islands", "MP"), ("Puerto Rico", "PR"), ("Jersey", "JE"),
                           ("The Netherlands", "NL"), ("Russian Federation", "RU"), ("USA", "US")]:
            self.assertEqual(C.resolve(text), code, text)
        self.assertEqual(C.resolve("International"), C.IGNORED)
        self.assertEqual(C.resolve("Europe"), C.IGNORED)
        self.assertEqual(C.resolve("NA"), C.IGNORED)
        self.assertEqual(C.resolve(""), C.IGNORED)
        self.assertEqual(C.resolve(None), C.IGNORED)
        self.assertIsNone(C.resolve("Atlantis"))

    def test_places(self):
        self.assertEqual(C.resolve_place("Calle Mayor, 3, Madrid, Madrid, 28071, Spain [Business]"), "ES")
        self.assertEqual(C.resolve_place("United States [Associated]"), "US")
        self.assertEqual(C.resolve_place("San Blas, Quito, Pichincha, Ecuador"), "EC")
        self.assertEqual(C.resolve_place("Saipan, Northern Mariana Islands"), "MP")
        self.assertEqual(C.resolve_place("International [Associated]"), C.IGNORED)
        self.assertIsNone(C.resolve_place("Springfield"))

    def test_in_sentences(self):
        self.assertEqual(C.find_in_text("Employment and residency in Bangladesh were reported for 2015 to 2019."), ["BD"])
        self.assertEqual(C.find_in_text("The account holder reported activity in the United States covering 2008 until 2018."), ["US"])
        self.assertEqual(C.find_in_text("Ireland's Tunde Bakare, 22, was employee of the month."), ["IE"])
        self.assertEqual(C.find_in_text("He served as a university lecturer in Cote D'Ivoire."), ["CI"])
        self.assertEqual(C.find_in_text("A sanctioned individual in the People's Republic of China."), ["CN"])
        self.assertEqual(C.find_in_text("She moved from Niger to Nigeria."), ["NE", "NG"])
        self.assertEqual(C.find_in_text("They lived in New Mexico and Benin City."), [])
        self.assertEqual(sorted(C.find_in_text("Worked in the UK and the U.S. for USD 500.")), ["GB", "US"])
        self.assertEqual(C.find_in_text("Verified with a Nigerian passport."), [])
        self.assertEqual(C.find_in_text("Verified with a Nigerian passport.", demonyms=True), ["NG"])


def person(name=None, dob=None, countries=None, verified=None, **kw):
    return Customer(PERSON, ["CUS-1"], verified_name=verified, verified_source="KYC-1" if verified else None,
                    names=[(name, "CUS-1")] if name else [], dob=d(dob) if dob else None,
                    dob_source="KYC-1" if dob else None,
                    countries=dict((c, ["CUS-1"]) for c in (countries or [])),
                    screened_at=d("2026-11-06"), **kw)


def hit(name, dobs="", countries=(), kind=PERSON, **kw):
    return Hit("H-1", kind, name, dobs=D.parse_dates(dobs), dob_origin="listed" if dobs else None,
               countries=countries, **kw)


class Decisions(unittest.TestCase):
    def test_brief_examples(self):
        o = decide(person("Mohammed Ali", "14 Mar 1988", ["GB"]), hit("Mohamed Ali", "1952", ["EG"]), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "DOB_MISMATCH"))
        self.assertIn("LOCATION_MISMATCH", o.codes)
        o = decide(person("Li Wei", "1975", ["SG"]), hit("Wei Li", "1975", ["SG"]), R)
        self.assertEqual((o.decision, o.code), (SAME, "NAME_DOB_MATCH"))
        self.assertIn("NAME_DOB_LOCATION_MATCH", o.codes)
        o = decide(person("Anna K. Petrova", None, ["RU"]), hit("Anna Petrova", "1969", ["RU"]), R)
        self.assertEqual((o.decision, o.code), (REVIEW, "INSUFFICIENT_DATA"))
        o = decide(person("Tom Okafor", "2004"), hit("Thomas Okafor", earliest_report=d("2011-05-02")), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "TEMPORAL_IMPOSSIBILITY"))

    def test_country_difference_does_not_clear_name_and_dob(self):
        o = decide(person("Li Wei", "1975-03-02", ["SG"]), hit("Wei Li", "1975", ["CN"]), R)
        self.assertEqual((o.decision, o.code), (REVIEW, "INSUFFICIENT_DATA"))

    def test_location_mismatch(self):
        o = decide(person("Markus Mueller", None, ["DE"]), hit("Markus Müller", "", ["CH"]), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "LOCATION_MISMATCH"))
        self.assertEqual(o.evidence, ["CUS-1"])
        self.assertIn("linked only to Germany but the hit is linked only to Switzerland", o.reason)

    def test_unreadable_country_blocks_location_clearance(self):
        o = decide(person("Markus Mueller", None, ["DE"]), hit("Markus Müller", "", ["CH"], unknown_countries=["Ruritania"]), R)
        self.assertEqual(o.decision, REVIEW)
        o = decide(person("Markus Mueller", None, ["DE"], unknown_countries=["Ruritania"]), hit("Markus Müller", "", ["CH"]), R)
        self.assertEqual(o.decision, REVIEW)

    def test_verified_name_beats_record_name(self):
        c = person("Rasheed Bello", None, ["NG"], verified="CHIDI BELLO")
        o = decide(c, hit("Rasheed, Bello", "", ["NG"]), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "NAME_MISMATCH_VERIFIED"))
        self.assertEqual(o.evidence, ["KYC-1"])

    def test_unverified_name_never_clears(self):
        o = decide(person("Laura Bennett", None, ["US"]), hit("Bennett, James Jacob", "", ["US"]), R)
        self.assertEqual(o.decision, REVIEW)

    def test_too_few_name_parts(self):
        c = person("UNKNOWN FAROOQ", "1968-08-20", ["PK"], verified="FAROOQ N/A")
        o = decide(c, hit("Muhammad Farooq", "1968", ["PK"]), R)
        self.assertEqual(o.decision, REVIEW)  # cannot confirm on name
        o = decide(c, hit("Ghani Khan", "", ["PK"]), R)
        self.assertEqual(o.decision, REVIEW)  # cannot clear on name either
        o = decide(c, hit("Muhammad Farooq", "1940", ["PK"]), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "DOB_MISMATCH"))  # other grounds still clear

    def test_dob_mismatch_evidence(self):
        c = person("Aleksandr Petrov", "1979-04-17", ["RU"])
        h = Hit("H-1", PERSON, "Petrov, Aleksandr", dobs=[d("1972"), d("1973")], dob_origin="search",
                dob_evidence=["SR-9"], countries=["RU"])
        o = decide(c, h, R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "DOB_MISMATCH"))
        self.assertEqual(o.evidence, ["KYC-1", "SR-9"])
        self.assertIn("search results put its birth year at 1972 or 1973", o.reason)

    def test_deceased(self):
        o = decide(person("John Smith", None, ["US"]), hit("John Smith", "", ["US"], death=d("2022-03")), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "DECEASED"))

    def test_entity_type(self):
        o = decide(person("Mark Baker"), hit("Baker Mark Ltd", kind=COMPANY), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "ENTITY_TYPE_MISMATCH"))

    def test_company(self):
        c = Customer(COMPANY, ["CUS-2"], verified_name="Marisol SA", verified_source="KYC-2",
                     countries={"ES": ["CUS-2", "KYC-2"]}, dob=d("1960-06-23"), dob_source="KYC-2")
        o = decide(c, hit("Marisol, Sociedad Anónima", "", ["ES"], kind=COMPANY), R)
        self.assertEqual((o.decision, o.code), (SAME, "NAME_LOCATION_MATCH"))
        self.assertEqual(o.evidence, ["CUS-2", "KYC-2"])
        o = decide(c, hit("Marisol, Sociedad Anónima", "", [], kind=COMPANY), R)
        self.assertEqual(o.decision, REVIEW)  # a company needs name and country
        o = decide(c, hit("Marisol, Sociedad Anónima", "", ["ES"], kind=COMPANY, earliest_report=d("1950-01-01")), R)
        self.assertEqual((o.decision, o.code), (DIFFERENT, "TEMPORAL_IMPOSSIBILITY"))

    def test_several_people(self):
        same = decide(person("Li Wei", "1975", ["SG"]), hit("Wei Li", "1975", ["SG"]), R)
        other = decide(person("Li Wei", "1990", ["SG"]), hit("Wei Li", "1975", ["SG"]), R)
        o = combine([same, other])
        self.assertEqual((o.decision, o.code, o.record_id), (REVIEW, "AMBIGUOUS_CUSTOMER_RECORD", AMBIGUOUS))
        o = combine([other, other])
        self.assertEqual((o.decision, o.code, o.record_id), (DIFFERENT, "DOB_MISMATCH", AMBIGUOUS))


if __name__ == "__main__":
    unittest.main()
