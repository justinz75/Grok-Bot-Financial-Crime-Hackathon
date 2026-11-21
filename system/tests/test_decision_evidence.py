"""Scored reasons and evidence describe the same facts."""
import unittest

from screening.decide import REVIEW, SAME, Outcome, combine

from test_pipeline import Folder


class DecisionEvidenceTests(unittest.TestCase):
    def test_unprinted_contradiction_does_not_contribute_evidence(self):
        f = Folder()
        rid = f.customer("Mira Dunwick", "2004-07-10", verified=("Mira Dunwick", "2004-07-10", None))
        check = f.tables["kyc_checks"][0]["check_id"]
        account = f.field("accounts", "customer_id", rid, "account_id")
        alert = f.alert("Mira Dunwick", account=account)
        hit = f.hit(alert, "Mira Dunwick", ["1961"], ["Japan"], deceased="2020-02-01",
                    notes="According to Example News; May 2, 2011: A report named Mira Dunwick.")

        line = f.run()[hit]
        self.assertEqual(line["decision"], "DIFFERENT_ENTITY")
        self.assertEqual(line["reason_code"], "DECEASED")
        self.assertEqual(line["evidence"], [hit + "#deceased_date", check])
        for fact in ("2020-02-01", "2011-05-02", "1961"):
            self.assertIn(fact, line["reason"])
        self.assertNotIn("Japan", line["reason"])
        self.assertEqual(line["reason"].count(". "), 3)

    def test_clearance_explains_each_candidate_with_a_different_ground(self):
        f = Folder()
        first = f.customer("Tessa Bramwell", "1972-06-12", country="Japan")
        second = f.customer("Tessa Bramwell", None, country="Germany", verified=None)
        check = f.tables["kyc_checks"][0]["check_id"]
        alert = f.alert("Tessa Bramwell")
        hit = f.hit(alert, "Tessa Bramwell", ["1951"], ["Japan"])

        line = f.run()[hit]
        self.assertEqual(line["decision"], "DIFFERENT_ENTITY")
        self.assertEqual(line["reason_code"], "DOB_MISMATCH")
        self.assertEqual(line["customer_record_id"], "AMBIGUOUS")
        self.assertEqual(line["evidence"], [second, check])
        self.assertIn("For record " + first + ", the customer's date of birth is 1972-06-12", line["reason"])
        self.assertIn("For record " + second + ", the customer is linked only to Germany", line["reason"])

    def test_clearance_prefers_a_ground_shared_by_all_candidates(self):
        f = Folder()
        first = f.customer("Sera Windell", "1978-03-15", country="Germany", verified=None)
        second = f.customer("Sera Windell", None, country="Canada", verified=None)
        alert = f.alert("Sera Windell")
        hit = f.hit(alert, "Sera Windell", ["1951"], ["Japan"])

        line = f.run()[hit]
        self.assertEqual(line["decision"], "DIFFERENT_ENTITY")
        self.assertEqual(line["reason_code"], "LOCATION_MISMATCH")
        self.assertEqual(line["evidence"], [first, second])
        self.assertIn("For record " + first + ", the customer is linked only to Germany", line["reason"])
        self.assertIn("For record " + second + ", the customer is linked only to Canada", line["reason"])
        self.assertNotIn("1978-03-15", line["reason"])

    def test_confirmation_names_every_candidate_within_the_sentence_budget(self):
        f = Folder()
        candidates = [
            (f.customer("Nadia Corven", dob, country=country), dob)
            for dob, country in [
                ("1984-02-26", "Japan"),
                ("1984-03-18", None),
                ("1984-05-23", "Japan"),
                ("1984-09-24", "Japan"),
            ]
        ]
        checks = [row["check_id"] for row in f.tables["kyc_checks"]]
        alert = f.alert("Nadia Corven")
        hit = f.hit(alert, "Nadia Corven", ["1984"], ["Japan"])

        line = f.run()[hit]
        self.assertEqual(line["decision"], "SAME_ENTITY")
        self.assertEqual(line["reason_code"], "NAME_DOB_MATCH")
        self.assertEqual(line["customer_record_id"], "AMBIGUOUS")
        # Each candidate is decided alone and the hit cites what any of them cites: the check
        # behind every date of birth, and the records that tie three of them to Japan.
        in_japan = [rid for (rid, _), country in zip(candidates, ("Japan", None, "Japan", "Japan")) if country]
        self.assertEqual(line["evidence"], sorted(checks + in_japan))
        for rid, dob in candidates:
            self.assertIn("record %s, the name matches and birth dates agree (%s" % (rid, dob), line["reason"])
        self.assertEqual(line["reason"].count(". "), 3)

    def test_non_ground_reasons_reserve_a_sentence_for_resolution(self):
        outcome = Outcome(REVIEW, ["INSUFFICIENT_DATA"], ["One.", "Two.", "Three.", "Four."], [])
        self.assertEqual(outcome.scored_facts()[0], ["One.", "Two.", "Three."])

    def test_unknown_record_is_described_as_unverified_details(self):
        missing = Outcome(REVIEW, ["INSUFFICIENT_DATA"], ["The date is unknown."], [])
        known = Outcome(SAME, ["NAME_DOB_MATCH"], ["The name and birth date match."], [], "CUS-000001")
        outcome = combine([missing, known])
        self.assertIn("For the unverified details, the date is unknown.", outcome.reason)
        self.assertIn("For record CUS-000001, the name and birth date match.", outcome.reason)
