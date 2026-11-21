"""Invented whole-run cases for the unlabelled ambiguity reason code.

Account-linked control alerts show each candidate's decision before the same
records are considered together. Folder also checks byte-identical repeated runs.
"""
import unittest

from test_pipeline import Folder


class UnlabelledAmbiguityTests(unittest.TestCase):
    def candidates(self, dates):
        f = Folder()
        records = [f.customer("Elva Wrenford", dob) for dob in dates]
        controls = []
        for rid in records:
            account = f.field("accounts", "customer_id", rid, "account_id")
            alert = f.alert("Elva Wrenford", account=account)
            controls.append(f.hit(alert, "Elva Wrenford", ["1980"], ["Germany"]))
        alert = f.alert("Elva Wrenford")
        combined = f.hit(alert, "Elva Wrenford", ["1980"], ["Germany"])
        return f, records, controls, combined

    def check_disagreement(self, dates, decisions):
        f, records, controls, combined = self.candidates(dates)
        lines = f.run()
        evidence = set()
        for rid, hit, decision in zip(records, controls, decisions):
            line = lines[hit]
            self.assertEqual(line["decision"], decision, line["reason"])
            self.assertEqual(line["customer_record_id"], rid)
            evidence.update(line["evidence"])
        line = lines[combined]
        self.assertEqual(line["decision"], "REVIEW", line["reason"])
        self.assertEqual(line["reason_code"], "AMBIGUOUS_CUSTOMER_RECORD")
        self.assertEqual(line["customer_record_id"], "AMBIGUOUS")
        self.assertEqual(line["evidence"], sorted(evidence))
        for rid in records:
            self.assertIn(rid, line["reason"])
        for decision in set(decisions):
            self.assertIn(decision, line["reason"])
        return line

    def test_match_and_clearance_require_review(self):
        self.check_disagreement(("1980-02-16", "1950-02-16"),
                                ("SAME_ENTITY", "DIFFERENT_ENTITY"))

    def test_missing_date_and_clearance_require_review(self):
        self.check_disagreement((None, "1950-02-16"),
                                ("REVIEW", "DIFFERENT_ENTITY"))

    def test_match_and_missing_date_require_review(self):
        self.check_disagreement(("1980-02-16", None), ("SAME_ENTITY", "REVIEW"))

    def test_three_different_decisions_require_review(self):
        self.check_disagreement(("1980-02-16", "1950-02-16", None),
                                ("SAME_ENTITY", "DIFFERENT_ENTITY", "REVIEW"))

    def test_unanimous_candidates_keep_their_decision_and_reason_code(self):
        # Multiple possible customers alone do not imply conflicting outcomes.
        for dates, decision, code in (
                (("1980-02-16", "1980-05-17"), "SAME_ENTITY", "NAME_DOB_MATCH"),
                (("1950-02-16", "1960-05-17"), "DIFFERENT_ENTITY", "DOB_MISMATCH"),
                ((None, None), "REVIEW", "INSUFFICIENT_DATA")):
            with self.subTest(decision=decision):
                f, records, controls, combined = self.candidates(dates)
                lines = f.run()
                line = lines[combined]
                self.assertEqual(line["decision"], decision, line["reason"])
                self.assertEqual(line["reason_code"], code)
                self.assertEqual(line["customer_record_id"], "AMBIGUOUS")
                expected = set()
                for hit in controls:
                    self.assertEqual(lines[hit]["decision"], decision)
                    expected.update(lines[hit]["evidence"])
                self.assertEqual(line["evidence"], sorted(expected))


if __name__ == "__main__":
    unittest.main()
