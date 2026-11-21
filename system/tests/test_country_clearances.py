"""Invented country-clearance audit through the regular screening pipeline.

Run: python -m unittest discover -s system/tests -p test_country_clearances.py
"""
import unittest

from test_pipeline import Folder


class CountryClearances(unittest.TestCase):
    def setUp(self):
        self.folder = Folder()
        self.name = "Elna Veywick"
        self.dob = "1981-07-23"

    def customer(self, country="Norway", verified=None, kind="Individual"):
        name = self.name if kind == "Individual" else "Veywick Loomworks"
        dob = self.dob if kind == "Individual" else None
        rid = self.folder.customer(name, dob, country, kind=kind, verified=verified)
        account = self.folder.field("accounts", "customer_id", rid, "account_id")
        return rid, self.folder.alert(name, account=account, kind=kind)

    def check(self, hit, rid, decision, code, evidence):
        line = self.folder.run()[hit]
        self.assertEqual(line["decision"], decision, line["reason"])
        self.assertEqual(line["reason_code"], code, line["reason"])
        self.assertEqual(line["customer_record_id"], rid)
        self.assertEqual(line["evidence"], sorted(evidence))

    def location_only_then_shared(self, hit, rid, evidence, add_shared):
        self.check(hit, rid, "DIFFERENT_ENTITY", "LOCATION_MISMATCH", evidence)
        shared_source = add_shared()
        self.check(hit, rid, "REVIEW", "INSUFFICIENT_DATA", [shared_source])

    def test_latest_approved_document_country_and_reason_ids(self):
        rid, alert = self.customer(verified=(self.name, self.dob, "Sweden"))
        applicant = self.folder.field("onboarding", "customer_id", rid, "kyc_applicant_id")
        latest = self.folder.tables["kyc_checks"][0]["check_id"]
        # The older and rejected checks both carry a conflicting legal name and DOB.
        self.folder.check(applicant, "Tilda Marnwick", "1964-11-12", "Norway",
                          checked_at="2021-01-04")
        self.folder.check(applicant, "Tilda Marnwick", "1964-11-12", "Denmark",
                          result="rejected", checked_at="2025-01-04")
        hit = self.folder.hit(alert, self.name, countries=["Denmark"])

        # The added note becomes the deciding source. Neither rejected nor old KYC is cited.
        self.location_only_then_shared(
            hit, rid, [rid, latest],
            lambda: self.folder.note(rid, "The customer lived in Denmark."),
        )

    def test_superseded_document_cannot_confirm_country(self):
        rid, alert = self.customer(verified=(self.name, self.dob, "Sweden"))
        applicant = self.folder.field("onboarding", "customer_id", rid, "kyc_applicant_id")
        old = self.folder.check(applicant, self.name, self.dob, "Denmark", checked_at="2021-01-04")
        latest = self.folder.tables["kyc_checks"][0]["check_id"]
        historical = self.folder.hit(alert, self.name, countries=["Denmark"])
        current = self.folder.hit(alert, self.name, [self.dob], ["Sweden"])
        historical_with_dob = self.folder.hit(alert, self.name, [self.dob], ["Denmark"])
        self.check(current, rid, "SAME_ENTITY", "NAME_DOB_MATCH", [latest])
        self.check(historical, rid, "REVIEW", "INSUFFICIENT_DATA", [rid, latest, old])
        self.check(historical_with_dob, rid, "REVIEW", "INSUFFICIENT_DATA", [latest, rid, old])
        reason = self.folder.run()[historical]["reason"]
        self.assertIn("Denmark", reason)
        self.assertIn(old, reason)
        self.assertNotIn("Nothing in the customer's records contradicts", reason)
        unrelated_without_dob = self.folder.hit(alert, self.name, countries=["Finland"])
        self.check(unrelated_without_dob, rid, "DIFFERENT_ENTITY", "LOCATION_MISMATCH", [rid, latest])
        unrelated = self.folder.hit(alert, self.name, [self.dob], ["Finland"])
        self.check(unrelated, rid, "REVIEW", "INSUFFICIENT_DATA", [latest, rid])

    def test_latest_approved_note_can_supersede_provider_document(self):
        rid, alert = self.customer(verified=(self.name, self.dob, "Norway"))
        latest = self.folder.note(
            rid, "Passport issued in Sweden verified for ELNA VEYWICK. DOB 1981-07-23.",
            channel="kyc", created_at="2025-01-12",
        )
        hit = self.folder.hit(alert, self.name, countries=["Denmark"])
        self.location_only_then_shared(
            hit, rid, [rid, latest],
            lambda: self.folder.note(rid, "The customer lived in Denmark."),
        )

    def test_territory_is_distinct_from_parent_country(self):
        rid, alert = self.customer(country="PRI")
        hit = self.folder.hit(alert, self.name, countries=["USA"])

        def add_shared():
            self.folder.tables["customers"][0].update(nationality="American")
            return rid

        self.location_only_then_shared(hit, rid, [rid], add_shared)

    def test_note_residence_is_a_country_tie(self):
        rid, alert = self.customer()
        note = self.folder.note(rid, "The customer lived in Denmark from 2013 to 2017.")
        hit = self.folder.hit(alert, self.name, countries=["FIN"])

        self.location_only_then_shared(
            hit, rid, [rid, note],
            lambda: self.folder.note(rid, "The customer lives in Finland."),
        )

    def test_travel_is_not_country_agreement_for_company(self):
        rid, alert = self.customer(kind="Company")
        note = self.folder.note(
            rid, "The customer lived in Sweden. The customer travelled to Denmark for a holiday.",
        )
        hit = self.folder.hit(alert, "Veywick Loomworks", countries=["Denmark"], kind="Company")
        self.check(hit, rid, "REVIEW", "INSUFFICIENT_DATA", [rid, note])
        reason = self.folder.run()[hit]["reason"]
        self.assertIn(note, reason)
        self.assertIn("Denmark", reason)
        finland = self.folder.hit(alert, "Veywick Loomworks", countries=["Finland"], kind="Company")
        self.check(finland, rid, "DIFFERENT_ENTITY", "LOCATION_MISMATCH", [rid, note])
        sweden = self.folder.hit(alert, "Veywick Loomworks", countries=["Sweden"], kind="Company")
        self.check(sweden, rid, "SAME_ENTITY", "NAME_LOCATION_MATCH", [note])
        residence = self.folder.note(rid, "The customer lived in Denmark from 2013 to 2017.")
        self.check(hit, rid, "SAME_ENTITY", "NAME_LOCATION_MATCH", [residence])

    def test_matching_name_and_dob_prevent_country_only_clearance(self):
        rid, alert = self.customer(verified="same")
        check = self.folder.tables["kyc_checks"][0]["check_id"]
        hit = self.folder.hit(alert, self.name, [self.dob], ["Denmark"])
        self.check(hit, rid, "REVIEW", "INSUFFICIENT_DATA", [rid, check])
