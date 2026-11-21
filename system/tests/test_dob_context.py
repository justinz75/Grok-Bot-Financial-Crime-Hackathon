"""Invented end-to-end checks for DOB attribution in hit prose and search."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_pipeline import Folder


class DobContext(unittest.TestCase):
    def decision(self, prose, source, country="Germany"):
        f = Folder()
        rid = f.customer("Nolan Varek", "1977-12-13", "Germany")
        alert = f.alert("Nolan Varek", account=f.field("accounts", "customer_id", rid, "account_id"))
        hit = f.hit(alert, "Varek, Nolan", [], [country], category="Enforcement",
                    notes=prose if source == "profile" else "")
        if source == "search":
            f.search("nolan varek", prose + " Subject of enforcement action in " + country + ".")
        return f.run()[hit]

    def assert_not_cleared(self, prose):
        for source in ("profile", "search"):
            with self.subTest(source=source):
                line = self.decision(prose, source)
                self.assertNotEqual(line["decision"], "DIFFERENT_ENTITY", line["reason"])

    def test_birth_cue_separated_from_unrelated_date(self):
        self.assert_not_cleared("Nolan Varek's date of birth is unknown. The hearing took place in 2001.")

    def test_fine_is_not_age(self):
        self.assert_not_cleared("Nolan Varek, 61 million euros in fines imposed in May 2024.")

    def test_count_is_not_age(self):
        self.assert_not_cleared("Nolan Varek, 61 counts of fraud alleged in May 2024.")

    def test_duration_is_not_age(self):
        self.assert_not_cleared("Nolan Varek served a sentence of 61 years imposed in May 2024.")

    def test_another_person_birth_is_not_subject_birth(self):
        self.assert_not_cleared("Nolan Varek's sister Elina was born in 1951.")

    def test_another_person_age_is_not_subject_age(self):
        self.assert_not_cleared("Nolan Varek's sister Elina, aged 61 in May 2024, attended the hearing.")

    def test_discarded_agreeing_birth_still_blocks_country_clearance(self):
        # The broad reader's agreeing DOB must survive as blocking evidence even
        # when it cannot be used to establish a DOB mismatch for clearance.
        for source in ("profile", "search"):
            with self.subTest(source=source):
                line = self.decision("Nolan Varek's sister Elina was born in 1977.", source, "Peru")
                self.assertEqual(line["decision"], "REVIEW", line["reason"])

    def test_control_subject_birth_mismatch_clears(self):
        for source in ("profile", "search"):
            with self.subTest(source=source):
                line = self.decision("Nolan Varek was born in 1951.", source)
                self.assertEqual(line["decision"], "DIFFERENT_ENTITY", line["reason"])
                self.assertEqual(line["reason_code"], "DOB_MISMATCH")

    def test_control_subject_age_mismatch_clears(self):
        for source in ("profile", "search"):
            with self.subTest(source=source):
                line = self.decision("Nolan Varek, aged 61 in May 2024.", source)
                self.assertEqual(line["decision"], "DIFFERENT_ENTITY", line["reason"])
                self.assertEqual(line["reason_code"], "DOB_MISMATCH")

    def test_control_subject_agreeing_birth_does_not_clear(self):
        self.assert_not_cleared("Nolan Varek was born in 1977.")

    def test_control_subject_reached_the_age(self):
        for source in ("profile", "search"):
            with self.subTest(source=source):
                line = self.decision("Investigators questioned Nolan Varek in May 2024, when he reached the age of 61.", source)
                self.assertEqual(line["reason_code"], "DOB_MISMATCH", line["reason"])

    def test_relative_birth_cannot_hide_agreeing_search_and_clear_on_country(self):
        f = Folder()
        rid = f.customer("Nolan Varek", "1977-12-13", "Germany")
        alert = f.alert("Nolan Varek", account=f.field("accounts", "customer_id", rid, "account_id"))
        hit = f.hit(alert, "Nolan Varek", countries=["Peru"], category="Enforcement",
                    notes="Nolan Varek's sister was born in 1951.")
        f.search("nolan varek", "Nolan Varek, subject of enforcement action in Peru, was born in 1977.")
        self.assertNotEqual(f.run()[hit]["decision"], "DIFFERENT_ENTITY")
