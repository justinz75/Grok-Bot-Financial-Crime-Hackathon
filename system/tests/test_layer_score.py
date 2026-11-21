"""Tests for the strength-of-evidence score layer.
Run:  python -m unittest discover -s system/tests -p "test_layer_score.py"

Every name here is invented; none comes from the hackathon data.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from screening import dates as D  # noqa: E402
from screening import layers  # noqa: E402
from screening.decide import (  # noqa: E402
    COMPANY, DIFFERENT, PERSON, REVIEW, SAME, Customer, Hit, decide, states,
)
from screening.layers import score as S  # noqa: E402
from screening.names import NameRules  # noqa: E402


class FakeStore(object):
    def __init__(self, customers):
        self.customers = customers
        self.rules = NameRules()


def record(name, country="Germany", kind="Individual", nationality=None):
    return {"entity_type": kind, "full_name": name, "preferred_name": None,
            "residence_country": country, "nationality": nationality or country}


# 200 records: 50 share a common name, one has a rare one, most live in Germany.
CUSTOMERS = ([record("John Smith") for _ in range(50)]
             + [record("Zebedee Quillfeather")]
             + [record("Person Number%s" % chr(65 + i % 26) + chr(65 + i // 26), "Germany") for i in range(139)]
             + [record("Anna Petrova", "Switzerland") for _ in range(10)])
STORE = FakeStore(CUSTOMERS)
LAYER = S.build(STORE, "on")


def d(text):
    return D.parse_date(text)


def person(name, dob=None, countries=(), verified=None, **kw):
    return Customer(PERSON, ["CUS-000001"], verified_name=verified,
                    verified_source="KYC-0000A1" if verified else None,
                    names=[(name, "CUS-000001")] if name else [], dob=d(dob) if dob else None,
                    dob_source="KYC-0000A1" if dob else None,
                    countries=dict((c, ["CUS-000001"]) for c in countries),
                    screened_at=d("2026-11-06"), **kw)


def hit(name, dobs="", countries=(), kind=PERSON, **kw):
    return Hit("H-0000A1", kind, name, dobs=D.parse_dates(dobs), dob_origin="listed" if dobs else None,
               countries=countries, **kw)


def case_for(customer, listed, store=STORE):
    outcome = decide(customer, listed, store.rules)
    return layers.Case(store, {}, {}, customer, listed, outcome, states(customer, listed, store.rules), {})


def note_for(customer, listed, layer=LAYER, store=STORE):
    return layer.annotate(case_for(customer, listed, store))


def by_field(note):
    return dict((item["field"], item) for item in note["contributions"])


class Shape(unittest.TestCase):
    def test_keys_and_field_order(self):
        note = note_for(person("John Smith", "1980-05-01", ["DE"]), hit("Smith, John", "1980", ["DE"]))
        self.assertEqual(sorted(note), ["band", "bits", "conflict", "contributions"])
        self.assertEqual([c["field"] for c in note["contributions"]], ["name", "date of birth", "country"])
        for item in note["contributions"]:
            self.assertEqual(sorted(item), ["bits", "detail", "field", "state"])
            self.assertIsInstance(item["bits"], float)
            self.assertTrue(item["detail"])
        self.assertEqual(note["bits"], round(sum(c["bits"] for c in note["contributions"]), 1))

    def test_extra_fields_only_when_they_apply(self):
        dead = note_for(person("John Smith", None, ["DE"]), hit("John Smith", "", ["DE"], death=d("2022-03")))
        self.assertEqual([c["field"] for c in dead["contributions"]], ["name", "date of birth", "country", "death"])
        self.assertEqual(by_field(dead)["death"]["bits"], -10.0)
        young = note_for(person("John Smith", "2008-01-01", ["DE"]),
                         hit("John Smith", "", ["DE"], earliest_report=d("2020-03-03")))
        self.assertEqual([c["field"] for c in young["contributions"]], ["name", "date of birth", "country", "timing"])
        self.assertEqual(by_field(young)["timing"]["bits"], -10.0)
        other = note_for(person("Mark Baker", None, ["DE"]), hit("Baker Mark Ltd", "", ["DE"], kind=COMPANY))
        self.assertEqual([c["field"] for c in other["contributions"]], ["name", "date of birth", "country", "entity type"])
        self.assertEqual(by_field(other)["entity type"]["bits"], -12.0)
        self.assertEqual(other["bits"], round(sum(c["bits"] for c in other["contributions"]), 1))

    def test_same_input_same_output(self):
        customer, listed = person("Zebedee Quillfeather", "1975-06-02", ["DE"]), hit("Quillfeather, Zebedee", "1975", ["DE"])
        self.assertEqual(note_for(customer, listed), note_for(customer, listed))
        again = S.build(FakeStore(list(CUSTOMERS)), "on")
        self.assertEqual(note_for(customer, listed), note_for(customer, listed, again))


class Name(unittest.TestCase):
    def test_rare_name_weighs_more_than_common(self):
        common = by_field(note_for(person("John Smith"), hit("Smith, John")))["name"]
        rare = by_field(note_for(person("Zebedee Quillfeather"), hit("Quillfeather, Zebedee")))["name"]
        self.assertEqual((common["state"], rare["state"]), ("agree", "agree"))
        self.assertGreater(rare["bits"], common["bits"])
        self.assertGreater(common["bits"], 0)
        self.assertLessEqual(rare["bits"], S.NAME_AGREE_MAX)
        self.assertIn("2 parts match", common["detail"])
        self.assertIn("customer in", rare["detail"])

    def test_verified_mismatch_is_negative(self):
        note = by_field(note_for(person("Rasheed Bello", verified="CHIDI BELLO"), hit("Rasheed, Bello")))["name"]
        self.assertEqual((note["state"], note["bits"]), ("mismatch", -6.0))
        self.assertIn("CHIDI BELLO", note["detail"])

    def test_unknown_name_weighs_nothing(self):
        too_few = by_field(note_for(person("UNKNOWN FAROOQ", verified="FAROOQ N/A"), hit("Muhammad Farooq")))["name"]
        self.assertEqual((too_few["state"], too_few["bits"]), ("unknown", 0.0))
        self.assertIn("fewer than two real parts", too_few["detail"])
        unverified = by_field(note_for(person("Laura Bennett"), hit("Bennett, James Jacob")))["name"]
        self.assertEqual((unverified["state"], unverified["bits"]), ("unknown", 0.0))
        self.assertIn("no verified legal name", unverified["detail"])


class DateOfBirth(unittest.TestCase):
    def bits(self, mine, theirs):
        return by_field(note_for(person("John Smith", mine), hit("John Smith", theirs)))["date of birth"]

    def test_agreement_is_stronger_the_more_exact_it_is(self):
        day = self.bits("1975-06-02", "1975-06-02")
        month = self.bits("1975-06-02", "1975-06")
        year = self.bits("1975-06-02", "1975")
        two_years = self.bits("1975-06-02", "1975; 1976")
        self.assertEqual([x["state"] for x in (day, month, year, two_years)], ["agree"] * 4)
        self.assertGreater(day["bits"], month["bits"])
        self.assertGreater(month["bits"], year["bits"])
        self.assertGreater(year["bits"], two_years["bits"])
        self.assertEqual(day["bits"], S.DOB_AGREE_MAX)
        self.assertGreaterEqual(two_years["bits"], 0.5)

    def test_mismatch_is_negative_and_grows_with_the_gap(self):
        near = self.bits("1979-11-08", "1976; 1977")
        far = self.bits("1977-12-13", "1951")
        self.assertEqual((near["state"], near["bits"]), ("mismatch", -6.0))   # 2 years apart
        self.assertEqual((far["state"], far["bits"]), ("mismatch", -14.0))    # capped at 10 years
        self.assertLess(far["bits"], near["bits"])
        self.assertIn("26 years apart", far["detail"])
        same_year = self.bits("1968-03-17", "1968-02")
        self.assertEqual((same_year["state"], same_year["bits"]), ("mismatch", -4.0))

    def test_unknown_weighs_nothing(self):
        for mine, theirs, words in ((None, "1969", "customer has no date of birth"),
                                    ("1975-06-02", "", "hit gives no date of birth"),
                                    (None, "", "Neither side"),
                                    ("1978-11-08", "1977", "too close to contradict")):
            item = self.bits(mine, theirs)
            self.assertEqual((item["state"], item["bits"]), ("unknown", 0.0), (mine, theirs))
            self.assertIn(words, item["detail"])

    def test_unreadable_check_does_not_weigh_against(self):
        customer = person("John Smith", "1990-01-01", ["DE"], dob_can_clear=False)
        item = by_field(note_for(customer, hit("John Smith", "1950", ["DE"])))["date of birth"]
        self.assertEqual((item["state"], item["bits"]), ("unknown", 0.0))
        self.assertIn("may not clear", item["detail"])


class Country(unittest.TestCase):
    def test_rare_country_weighs_more_than_common(self):
        common = by_field(note_for(person("John Smith", None, ["DE"]), hit("John Smith", "", ["DE"])))["country"]
        rare = by_field(note_for(person("John Smith", None, ["CH"]), hit("John Smith", "", ["CH"])))["country"]
        self.assertEqual((common["state"], rare["state"]), ("agree", "agree"))
        self.assertGreater(rare["bits"], common["bits"])
        self.assertGreaterEqual(common["bits"], 0.3)
        self.assertIn("Switzerland", rare["detail"])
        self.assertIn("1 customer in 20", rare["detail"])

    def test_mismatch_and_unknown(self):
        differs = by_field(note_for(person("Markus Mueller", None, ["DE"]), hit("Markus Müller", "", ["CH"])))["country"]
        self.assertEqual((differs["state"], differs["bits"]), ("mismatch", -3.3))
        self.assertEqual(differs["detail"], "Germany against Switzerland")
        none = by_field(note_for(person("Markus Mueller", None, ["DE"]), hit("Markus Müller", "", [])))["country"]
        self.assertEqual((none["state"], none["bits"]), ("unknown", 0.0))
        unread = by_field(note_for(person("Markus Mueller", None, ["DE"]),
                                   hit("Markus Müller", "", ["CH"], unknown_countries=["Ruritania"])))["country"]
        self.assertEqual((unread["state"], unread["bits"]), ("unknown", 0.0))
        self.assertIn("could not be read", unread["detail"])


class BandsAndConflict(unittest.TestCase):
    def test_band_strings(self):
        self.assertEqual(S.band(8), "strong evidence of the same")
        self.assertEqual(S.band(7.9), "some evidence of the same")
        self.assertEqual(S.band(3), "some evidence of the same")
        self.assertEqual(S.band(2.9), "inconclusive")
        self.assertEqual(S.band(0), "inconclusive")
        self.assertEqual(S.band(-2.9), "inconclusive")
        self.assertEqual(S.band(-3), "some evidence of a different one")
        self.assertEqual(S.band(-7.9), "some evidence of a different one")
        self.assertEqual(S.band(-8), "strong evidence of a different one")

    def test_a_clearance_on_country_alone_is_inconclusive_not_a_conflict(self):
        # every hit shares the name, so an agreeing name must not outweigh the policy's ground
        case = case_for(person("Zebedee Quillfeather", None, ["DE"]), hit("Quillfeather, Zebedee", "", ["CH"]))
        self.assertEqual((case.outcome.decision, case.outcome.code), (DIFFERENT, "LOCATION_MISMATCH"))
        note = LAYER.annotate(case)
        self.assertEqual(note["band"], "inconclusive")
        self.assertFalse(note["conflict"])
        self.assertIsNone(LAYER.guard(case, note))

    def test_conflict_when_all_else_agrees_and_only_the_day_differs(self):
        case = case_for(person("Zebedee Quillfeather", "1968-03-17", ["CH"]), hit("Quillfeather, Zebedee", "1968-03-05", ["CH"]))
        self.assertEqual((case.outcome.decision, case.outcome.code), (DIFFERENT, "DOB_MISMATCH"))
        note = LAYER.annotate(case)
        self.assertTrue(note["conflict"])
        self.assertGreaterEqual(note["bits"], 3)
        why = LAYER.guard(case, note)
        self.assertIn("leans towards the same person", why)
        self.assertIn("%+.1f" % note["bits"], why)

    def test_no_conflict_when_the_evidence_backs_the_clearance(self):
        case = case_for(person("Zebedee Quillfeather", "1977-12-13", ["DE"]), hit("Quillfeather, Zebedee", "1951", ["DE"]))
        self.assertEqual(case.outcome.decision, DIFFERENT)
        note = LAYER.annotate(case)
        self.assertFalse(note["conflict"])
        self.assertIsNone(LAYER.guard(case, note))
        self.assertIsNone(LAYER.guard(case, None))

    def test_conflict_only_on_clearances(self):
        same = case_for(person("Zebedee Quillfeather", "1975-06-02", ["DE"]), hit("Quillfeather, Zebedee", "1975", ["DE"]))
        self.assertEqual(same.outcome.decision, SAME)
        note = LAYER.annotate(same)
        self.assertEqual(note["band"], "strong evidence of the same")
        self.assertFalse(note["conflict"])
        review = case_for(person("Zebedee Quillfeather", None, ["DE"]), hit("Quillfeather, Zebedee", "1975", ["DE"]))
        self.assertEqual(review.outcome.decision, REVIEW)
        self.assertFalse(LAYER.annotate(review)["conflict"])


class OddInput(unittest.TestCase):
    def test_no_customers(self):
        empty = FakeStore([])
        layer = S.build(empty, "on")
        note = note_for(person("John Smith", "1975-06-02", ["DE"]), hit("John Smith", "1975", ["DE"]), layer, empty)
        fields = by_field(note)
        self.assertEqual((fields["name"]["state"], fields["name"]["bits"]), ("agree", 0.0))
        self.assertEqual((fields["country"]["state"], fields["country"]["bits"]), ("agree", 0.0))
        self.assertGreater(fields["date of birth"]["bits"], 0)

    def test_empty_names_and_missing_facts_do_not_raise(self):
        nameless = Customer(PERSON, [], names=[], screened_at=d("2026-11-06"))
        note = note_for(nameless, hit("", "", []))
        self.assertEqual(note["bits"], 0.0)
        self.assertEqual(note["band"], "inconclusive")
        self.assertFalse(note["conflict"])
        self.assertEqual([c["bits"] for c in note["contributions"]], [0.0, 0.0, 0.0])

    def test_company(self):
        store = FakeStore([record("Marisol SA", "Spain", "Company"), record("Harbour Transit Ltd", "Spain", "Company")]
                          + [record("John Smith") for _ in range(8)])
        layer = S.build(store, "on")
        customer = Customer(COMPANY, ["CUS-000002"], verified_name="Marisol SA", verified_source="KYC-0000A2",
                            countries={"ES": ["CUS-000002"]}, dob=d("1960-06-23"), dob_source="KYC-0000A2")
        note = note_for(customer, hit("Marisol, Sociedad Anónima", "", ["ES"], kind=COMPANY), layer, store)
        fields = by_field(note)
        self.assertEqual(fields["name"]["state"], "agree")
        self.assertIn("1 part matches", fields["name"]["detail"])
        self.assertIn("incorporation date", fields["date of birth"]["detail"])
        self.assertGreater(note["bits"], 0)


if __name__ == "__main__":
    unittest.main()
