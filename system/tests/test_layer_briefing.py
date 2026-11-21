"""Tests for the analyst briefing layer.

    python -m unittest discover -s system/tests -p "test_layer_briefing.py"

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
from screening.layers import briefing  # noqa: E402
from screening.names import NameRules  # noqa: E402


class FakeStore(object):
    rules = NameRules()


STORE = FakeStore()
LAYER = briefing.build(STORE, "on")
KEYS = ("headline", "decided_by", "missing", "would_settle", "strength", "caveats")


def d(text):
    return D.parse_date(text)


def person(name="Lars Holm", dob=None, countries=("DE",), verified=None, records=("CUS-000001",),
           dob_source="KYC-0000A1", **kw):
    return Customer(PERSON, list(records), verified_name=verified,
                    verified_source="KYC-0000A1" if verified else None,
                    names=[(name, records[0] if records else None)] if name else [],
                    dob=d(dob) if dob else None, dob_source=dob_source if dob else None,
                    countries=dict((c, [records[0] if records else None]) for c in countries),
                    screened_at=d("2026-11-06"), **kw)


def company(name="Marisol SA", inc=None, countries=("ES",), verified=True, **kw):
    return Customer(COMPANY, ["CUS-000002"], verified_name=name if verified else None,
                    verified_source="KYC-0000A2" if verified else None, names=[(name, "CUS-000002")],
                    dob=d(inc) if inc else None, dob_source="KYC-0000A2" if inc else None,
                    countries=dict((c, ["CUS-000002", "KYC-0000A2"]) for c in countries),
                    screened_at=d("2026-11-06"), **kw)


def hit(name="Holm, Lars", dobs="", countries=("DE",), kind=PERSON, origin="listed", **kw):
    return Hit("H-0000A1", kind, name, dobs=D.parse_dates(dobs), dob_origin=origin if dobs else None,
               countries=countries, **kw)


def brief(customer, the_hit, notes=None):
    outcome = decide(customer, the_hit, STORE.rules)
    case = layers.Case(STORE, {}, {}, customer, the_hit, outcome, states(customer, the_hit, STORE.rules),
                       notes if notes is not None else {})
    return LAYER.annotate(case), outcome


class Shape(unittest.TestCase):
    def check(self, note):
        self.assertEqual(sorted(note), sorted(KEYS))
        self.assertIsInstance(note["headline"], str)
        self.assertIsInstance(note["strength"], str)
        self.assertTrue(note["headline"].endswith("."))
        for key in ("decided_by", "missing", "would_settle", "caveats"):
            self.assertIsInstance(note[key], list, key)
            for item in note[key]:
                self.assertIsInstance(item, str)
                self.assertTrue(item.strip().endswith((".", "!", "?")), item)

    def test_every_outcome_has_the_six_fields(self):
        cases = [
            (person(dob="1977-12-13", verified="LARS HOLM"), hit(dobs="1951")),
            (person(dob="1977-12-13"), hit(dobs="1977")),
            (person(), hit()),
            (person(countries=("DE",)), hit(countries=("CH",))),
            (company(), hit("Marisol, Sociedad Anónima", countries=("ES",), kind=COMPANY)),
            (person(), hit("Holm Lars Ltd", kind=COMPANY)),
        ]
        for customer, the_hit in cases:
            note, _ = brief(customer, the_hit)
            self.check(note)

    def test_same_input_same_text(self):
        customer, the_hit = person(dob="1977-12-13", verified="LARS HOLM"), hit(dobs="1951")
        self.assertEqual(brief(customer, the_hit)[0], brief(customer, the_hit)[0])

    def test_odd_input_never_raises(self):
        class Odd(object):
            pass
        case = layers.Case(STORE, {}, {}, Odd(), Odd(), None, None, None)
        note = LAYER.annotate(case)
        self.check(note)
        self.assertEqual((note["decided_by"], note["missing"], note["would_settle"], note["caveats"]), ([], [], [], []))


class Different(unittest.TestCase):
    def test_date_of_birth(self):
        note, outcome = brief(person(dob="1977-12-13", verified="LARS HOLM"), hit(dobs="1951"))
        self.assertEqual((outcome.decision, outcome.code), (DIFFERENT, "DOB_MISMATCH"))
        self.assertEqual(note["headline"], "Different person: born 26 years apart.")
        self.assertEqual(note["strength"], "one ground, from a verified identity check")
        self.assertEqual(note["would_settle"], [])
        self.assertEqual(note["missing"], [])
        self.assertTrue(any("KYC-0000A1" in s for s in note["decided_by"]))
        self.assertEqual(note["caveats"], [])

    def test_declared_date_of_birth_is_weaker(self):
        note, _ = brief(person(dob="1977-12-13", dob_source="CUS-000001"), hit(dobs="1951"))
        self.assertEqual(note["strength"], "one ground, from a declared date of birth")
        self.assertIn("There is no approved identity check, so the legal name and date of birth are unverified.",
                      note["missing"])

    def test_same_year_different_month(self):
        note, outcome = brief(person(dob="1968-03-17", verified="LARS HOLM"), hit(dobs="1968-02"))
        self.assertEqual(outcome.code, "DOB_MISMATCH")
        self.assertEqual(note["headline"], "Different person: born in the same year but on a different date.")
        self.assertIn("The years are the same; only the month or day differs.", note["caveats"])

    def test_small_gap_is_a_caveat(self):
        note, _ = brief(person(dob="1979-11-08", verified="LARS HOLM"), hit(dobs="1976; 1977"))
        self.assertEqual(note["headline"], "Different person: born 2 years apart.")
        self.assertIn("The dates are only 2 years apart, close to the one-year tolerance.", note["caveats"])

    def test_location(self):
        note, outcome = brief(person(verified="LARS HOLM"), hit(countries=("CH",)))
        self.assertEqual((outcome.decision, outcome.code), (DIFFERENT, "LOCATION_MISMATCH"))
        self.assertEqual(note["headline"], "Different person by policy: no country in common.")
        self.assertEqual(note["strength"], "one ground, country only")
        self.assertIn("The hit gives no date of birth in its field, its profile notes or search results about it.",
                      note["missing"])
        self.assertIn("The customer has no date of birth on any record.", note["missing"])
        self.assertIn("The name agrees and no date of birth could be compared, so this clearance rests on country alone.",
                      note["caveats"])
        self.assertEqual(note["would_settle"], [])

    def test_verified_name(self):
        note, outcome = brief(person("Rasheed Bello", verified="CHIDI BELLO", countries=("NG",)),
                              hit("Rasheed, Bello", countries=("NG",)))
        self.assertEqual(outcome.code, "NAME_MISMATCH_VERIFIED")
        self.assertEqual(note["headline"], "Different person: the verified legal name is not the listed name.")
        self.assertEqual(note["strength"], "one ground, the verified legal name")

    def test_too_young(self):
        note, outcome = brief(person("Tom Okafor", dob="2008-05-01", countries=()),
                              hit("Thomas Okafor", countries=(), earliest_report=d("2020-06-01")))
        self.assertEqual(outcome.code, "TEMPORAL_IMPOSSIBILITY")
        self.assertEqual(note["headline"], "Different person: too young when the earliest report was published.")
        self.assertEqual(note["strength"], "one ground, timing")
        note, _ = brief(person("Tom Okafor", dob="2022-05-01", countries=()),
                        hit("Thomas Okafor", countries=(), earliest_report=d("2020-06-01")))
        self.assertEqual(note["headline"], "Different person: born after the earliest report was published.")

    def test_company_incorporated_later(self):
        note, outcome = brief(company(inc="2021-11-14"),
                              hit("Marisol, Sociedad Anónima", countries=("ES",), kind=COMPANY,
                                  earliest_report=d("2015-03-03")))
        self.assertEqual(outcome.code, "TEMPORAL_IMPOSSIBILITY")
        self.assertEqual(note["headline"], "Different company: incorporated after the earliest report.")

    def test_deceased(self):
        note, outcome = brief(person("John Smith", countries=("US",)),
                              hit("John Smith", countries=("US",), death=d("2022-03")))
        self.assertEqual(outcome.code, "DECEASED")
        self.assertEqual(note["headline"], "Different person: the listed person died before this customer was screened.")
        self.assertEqual(note["strength"], "one ground, date of death")

    def test_entity_type(self):
        note, outcome = brief(person("Mark Baker"), hit("Baker Mark Ltd", kind=COMPANY))
        self.assertEqual(outcome.code, "ENTITY_TYPE_MISMATCH")
        self.assertEqual(note["headline"], "Different: one is a person and the other a company.")
        self.assertEqual(note["strength"], "one ground, entity type")

    def test_two_grounds(self):
        note, outcome = brief(person("Mohammed Ali", dob="1988-03-14", countries=("GB",), verified="MOHAMMED ALI"),
                              hit("Mohamed Ali", dobs="1952", countries=("EG",)))
        self.assertEqual(outcome.codes, ["DOB_MISMATCH", "LOCATION_MISMATCH"])
        self.assertEqual(note["strength"], "two independent grounds")
        self.assertEqual(len(note["decided_by"]), 2)


class Same(unittest.TestCase):
    def test_person_with_country(self):
        note, outcome = brief(person("Li Wei", dob="1975-06-02", countries=("SG",), verified="LI WEI"),
                              hit("Wei Li", dobs="1975", countries=("SG",)))
        self.assertEqual(outcome.decision, SAME)
        self.assertEqual(note["headline"], "Same person: name and date of birth agree, and so does the country.")
        self.assertEqual(note["strength"], "name, date of birth and country agree")
        self.assertEqual(note["missing"], ["The hit gives a birth year only, so the day and month could not be compared."])
        self.assertEqual(note["would_settle"], [])
        self.assertEqual(len(note["decided_by"]), 3)

    def test_person_without_shared_country(self):
        note, outcome = brief(person("Li Wei", dob="1975-06-02", countries=("SG",), verified="LI WEI"),
                              hit("Wei Li", dobs="1975-06-02", countries=()))
        self.assertEqual(outcome.decision, SAME)
        self.assertEqual(note["headline"], "Same person: name and date of birth agree.")
        self.assertEqual(note["strength"], "name and date of birth agree; no shared country is known")
        self.assertEqual(note["missing"], ["No country is tied to the hit."])

    def test_company(self):
        note, outcome = brief(company(inc="1960-06-23"),
                              hit("Marisol, Sociedad Anónima", countries=("ES",), kind=COMPANY))
        self.assertEqual((outcome.decision, outcome.code), (SAME, "NAME_LOCATION_MATCH"))
        self.assertEqual(note["headline"], "Same company: name and country agree.")
        self.assertEqual(note["strength"], "name and country agree")
        self.assertIn("The hit gives no incorporation date.", note["missing"])


class Review(unittest.TestCase):
    def test_hit_has_no_date_of_birth(self):
        note, outcome = brief(person("Anna K. Petrova", dob="1969-04-02", countries=("RU",), verified="ANNA PETROVA"),
                              hit("Anna Petrova", countries=("RU",)))
        self.assertEqual((outcome.decision, outcome.code), (REVIEW, "INSUFFICIENT_DATA"))
        self.assertEqual(note["headline"],
                         "Needs a person: name and country agree, but there is no date of birth to compare.")
        self.assertEqual(note["strength"], "open")
        self.assertEqual(len(note["would_settle"]), 1)
        for value in ("1969", "1967 or earlier", "1971 or later", "listed person"):
            self.assertIn(value, note["would_settle"][0])
        self.assertFalse(any(s.startswith("Nothing in the customer's records") for s in note["decided_by"]))
        self.assertEqual(len(note["decided_by"]), 2)

    def test_customer_has_no_date_of_birth(self):
        note, _ = brief(person("Anna K. Petrova", countries=("RU",)), hit("Anna Petrova", dobs="1987; 1988", countries=("RU",)))
        self.assertIn("The customer has no date of birth on any record.", note["missing"])
        self.assertIn("There is no approved identity check, so the legal name and date of birth are unverified.",
                      note["missing"])
        self.assertEqual(len(note["would_settle"]), 1)
        for value in ("The customer's date of birth", "1987 or 1988", "1985 or earlier", "1990 or later"):
            self.assertIn(value, note["would_settle"][0])

    def test_neither_has_a_date_of_birth(self):
        note, _ = brief(person("Anna K. Petrova", countries=("RU",)), hit("Anna Petrova", countries=()))
        self.assertEqual(note["headline"], "Needs a person: the name agrees, but there is no date of birth to compare.")
        self.assertIn("No country is tied to the hit.", note["missing"])
        self.assertIn("neither has one", note["would_settle"][0])

    def test_years_one_apart(self):
        note, outcome = brief(person("Li Wei", dob="1989-02-07", countries=("SG",), verified="LI WEI"),
                              hit("Wei Li", dobs="1990", countries=("SG",)))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertEqual(note["headline"], "Needs a person: name and country agree, but the birth years are one year apart.")
        self.assertIn("one year apart (1989 against 1990)", note["would_settle"][0])

    def test_name_and_date_agree_but_not_the_country(self):
        note, outcome = brief(person("Li Wei", dob="1975-03-02", countries=("SG",), verified="LI WEI"),
                              hit("Wei Li", dobs="1975", countries=("CN",)))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertEqual(note["headline"], "Needs a person: name and date of birth agree, but no country is shared.")
        self.assertIn("China", note["would_settle"][0])
        self.assertIn("cannot clear", note["would_settle"][0])
        self.assertTrue(any(s == "Every country tied to the customer (Singapore) differs from every country tied "
                                 "to the hit (China)." for s in note["decided_by"]))

    def test_too_few_name_parts(self):
        note, outcome = brief(person("UNKNOWN FAROOQ", dob="1968-08-20", countries=("PK",), verified="FAROOQ N/A"),
                              hit("Muhammad Farooq", dobs="1968", countries=("PK",)))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertEqual(note["headline"], "Needs a person: the date of birth agrees, but the name cannot be confirmed.")
        self.assertIn("The customer's name has fewer than two real parts, so it can neither confirm nor clear the hit.",
                      note["missing"])
        self.assertEqual(len(note["would_settle"]), 1)
        self.assertIn("at least two parts", note["would_settle"][0])

    def test_unverified_name_that_does_not_agree(self):
        note, outcome = brief(person("Laura Bennett", countries=("US",)), hit("Bennett, James Jacob", countries=("US",)))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertEqual(note["headline"], "Needs a person: the name cannot be confirmed against the listing.")
        self.assertEqual(len(note["would_settle"]), 2)  # the name, and the date of birth
        self.assertIn("A verified legal name would settle the name", note["would_settle"][0])

    def test_no_customer_record(self):
        customer = Customer(PERSON, [], names=[("Lars Holm", None)], dob=d("1977-12-13"),
                            screened_at=d("2026-11-06"), dob_can_clear=False, confirmable=False)
        note, outcome = brief(customer, hit(dobs="1977"))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertEqual(note["headline"], "Needs a person: no customer record fits the alert.")
        self.assertEqual(note["missing"][0], "No customer record was found, so only the screened details were compared.")
        self.assertEqual(len(note["would_settle"]), 1)
        self.assertIn("system of record", note["would_settle"][0])
        self.assertFalse(any(s.startswith("The screened details are unverified") for s in note["decided_by"]))

    def test_company_without_a_hit_country(self):
        note, outcome = brief(company(), hit("Marisol, Sociedad Anónima", countries=(), kind=COMPANY))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertEqual(note["headline"], "Needs a person: the name agrees, but no country ties the company to the listing.")
        self.assertIn("A country for the listed company would settle it: Spain would confirm the match",
                      note["would_settle"][0])

    def test_unreadable_country_is_named(self):
        note, outcome = brief(person(verified="LARS HOLM", unknown_countries=["Ruritania"]), hit(countries=("CH",)))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertIn("The customer country \"Ruritania\" could not be read.", note["missing"])
        note, _ = brief(person(verified="LARS HOLM"), hit(countries=("CH",), unknown_countries=["Freedonia [Business]"]))
        self.assertIn("The hit location \"Freedonia [Business]\" could not be read.", note["missing"])

    def test_unread_identity_check(self):
        note, outcome = brief(person(dob="1977-12-13", dob_source="CUS-000001", dob_can_clear=False), hit(dobs="1951"))
        self.assertEqual(outcome.decision, REVIEW)
        self.assertIn("An identity check on file could not be read with confidence, so what it says can support a "
                      "match but cannot clear one.", note["missing"])
        self.assertEqual(note["headline"],
                         "Needs a person: name and country agree, but the customer's date of birth could not be verified.")
        self.assertIn("A readable approved identity check would settle it", note["would_settle"][0])


class Caveats(unittest.TestCase):
    def test_score_conflict_and_reviewer(self):
        notes = {"score": {"bits": 2.9, "band": "some evidence of the same", "conflict": True, "contributions": []},
                 "reviewer": {"verdict": "disagree", "reason": "The name is rare and the countries are neighbours",
                              "model": "example/small-model", "runs": 3, "agreement": 1.0}}
        note, _ = brief(person(verified="LARS HOLM"), hit(countries=("CH",)), notes)
        self.assertIn("The strength-of-evidence score leans the other way (+2.9 bits): towards the same person.",
                      note["caveats"])
        self.assertIn("The model reviewer disagreed with the rules, saying: The name is rare and the countries "
                      "are neighbours.", note["caveats"])

    def test_quiet_layers_add_nothing(self):
        notes = {"score": {"bits": -8.0, "conflict": False}, "reviewer": {"verdict": "agree", "reason": "Clear."}}
        note, _ = brief(person(dob="1977-12-13", verified="LARS HOLM"), hit(dobs="1951"), notes)
        self.assertEqual(note["caveats"], [])
        note, _ = brief(person(dob="1977-12-13", verified="LARS HOLM"), hit(dobs="1951"), {"score": None, "reviewer": None})
        self.assertEqual(note["caveats"], [])

    def test_unsure_reviewer(self):
        notes = {"reviewer": {"verdict": "unsure", "reason": "No date of birth to compare."}}
        note, _ = brief(person(verified="LARS HOLM"), hit(countries=("CH",)), notes)
        self.assertIn("The model reviewer was unsure, saying: No date of birth to compare.", note["caveats"])

    def test_merged_records(self):
        note, _ = brief(person(dob="1977-12-13", verified="LARS HOLM", records=("CUS-000001", "CUS-000009")),
                        hit(dobs="1951"))
        self.assertIn("The customer is 2 records treated as one person: CUS-000001 and CUS-000009.", note["caveats"])

    def test_where_the_hit_birth_years_came_from(self):
        customer = person("Aleksandr Petrov", dob="1979-04-17", countries=("RU",), verified="ALEKSANDR PETROV")
        searched = Hit("H-0000A1", PERSON, "Petrov, Aleksandr", dobs=[d("1972"), d("1973")], dob_origin="search",
                       dob_evidence=["SR-0000A9"], countries=["RU"])
        note, _ = brief(customer, searched)
        self.assertIn("The hit's birth years come from a web search result (SR-0000A9), not from the listing itself.",
                      note["caveats"])
        from_notes = Hit("H-0000A1", PERSON, "Petrov, Aleksandr", dobs=[d("1972"), d("1973")], dob_origin="notes",
                         countries=["RU"])
        note, _ = brief(customer, from_notes)
        self.assertIn("The hit's birth years are worked out from an age given in its profile notes.", note["caveats"])
        listed = hit("Petrov, Aleksandr", dobs="1972", countries=("RU",))
        note, _ = brief(customer, listed)
        self.assertFalse(any("search result" in c or "profile notes" in c for c in note["caveats"]))


if __name__ == "__main__":
    unittest.main()
