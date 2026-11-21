"""Tests for the layer framework. Run:  python -m unittest discover -s system/tests

Uses a tiny invented data folder. The guarantees checked here hold for any layer:
the scored file does not change unless a layer enforces, and enforcing can only
turn a clearance into a review.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from screening import layers  # noqa: E402
from screening import pipeline  # noqa: E402

TABLES = {
    "customers": [
        {"record_id": "CUS-000001", "entity_type": "Individual", "full_name": "Lars Holm", "dob": "1977-12-13",
         "nationality": "Germany", "residence_country": "DE", "email": "lars.holm@mail.example", "phone": "+49 1000001"},
    ],
    "accounts": [{"account_id": "ACC-0000A1", "customer_id": "CUS-000001", "login_handle": "holml1", "phone": "+49 1000001"}],
    "onboarding": [{"account_id": "ACC-0000A1", "customer_id": "CUS-000001", "kyc_applicant_id": "APP-0000A1"}],
    "kyc_checks": [{"check_id": "KYC-0000A1", "applicant_id": "APP-0000A1", "verified_name": "LARS HOLM",
                    "verified_dob": "1977-12-13", "document_type": "passport", "document_number": "X1",
                    "document_country": "Germany", "result": "approved", "checked_at": "2024-01-05"}],
    "notes": [],
    "search_results": [],
    "alerts": [{"alert_id": "A-0000A1", "screened_at": "2026-11-06",
                "customer": {"name": "Lars Holm", "entity_type": "Individual", "dob": None, "country": None, "city": None},
                "account_ref": "ACC-0000A1", "login_handle": None, "email": None,
                "hit_ids": ["H-0000A1", "H-0000A2", "H-0000A3"]}],
    "hits": [
        {"hit_id": "H-0000A1", "alert_id": "A-0000A1", "entity_type": "Individual", "name": "Holm, Lars",
         "dobs": ["1951"], "countries": ["Germany"], "categories": ["PEP"]},          # cleared: born 26 years apart
        {"hit_id": "H-0000A2", "alert_id": "A-0000A1", "entity_type": "Individual", "name": "Lars Holm",
         "dobs": [], "countries": ["Germany"], "categories": ["PEP"]},                 # review: no date to compare
        {"hit_id": "H-0000A3", "alert_id": "A-0000A1", "entity_type": "Individual", "name": "Lars Holm",
         "dobs": ["1977"], "countries": ["Germany"], "categories": ["PEP"]},           # same: name and date agree
    ],
}


class Marker(object):
    """A stand-in layer: notes every case and, when enforcing, objects to every clearance."""

    def annotate(self, case):
        return {"saw": case.hit.hit_id, "decision": case.outcome.decision}

    def guard(self, case, note):
        return "the marker layer objects"


class Broken(object):
    def annotate(self, case):
        raise ValueError("boom")

    def guard(self, case, note):
        raise ValueError("boom")


class Framework(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="layers-")
        for name, rows in TABLES.items():
            with open(os.path.join(self.folder, name + ".jsonl"), "w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
        self._load = layers.load

    def tearDown(self):
        layers.load = self._load
        shutil.rmtree(self.folder, ignore_errors=True)

    def run_with(self, mode, layer=None, explain=True):
        if layer is not None:
            layers.load = lambda store, modes, problems=None: [("score", mode, layer)]
        out = os.path.join(self.folder, "out.jsonl")
        note = os.path.join(self.folder, "out.explain.jsonl") if explain else None
        modes = dict((n, "off") for n in layers.NAMES)
        modes["score"] = mode
        pipeline.run(self.folder, out, note, modes)
        with open(out, encoding="utf-8") as handle:
            lines = [json.loads(line) for line in handle]
        notes = []
        if note:
            with open(note, encoding="utf-8") as handle:
                notes = [json.loads(line) for line in handle]
        return lines, notes

    def test_rules_alone(self):
        lines, notes = self.run_with("off")
        self.assertEqual([l["decision"] for l in lines], ["DIFFERENT_ENTITY", "REVIEW", "SAME_ENTITY"])
        self.assertEqual([l["reason_code"] for l in lines], ["DOB_MISMATCH", "INSUFFICIENT_DATA", "NAME_DOB_MATCH"])
        self.assertEqual(len(notes), 3)
        self.assertEqual(notes[0]["rules"], {"decision": "DIFFERENT_ENTITY", "reason_code": "DOB_MISMATCH"})
        self.assertEqual(notes[0]["people"][0]["states"], {"name": "agree", "dob": "mismatch", "location": "agree"})
        self.assertNotIn("reason", notes[0])

    def test_a_layer_that_is_on_changes_nothing_scored(self):
        plain, _ = self.run_with("off")
        with_layer, notes = self.run_with("on", Marker())
        self.assertEqual(plain, with_layer)
        self.assertEqual(notes[0]["people"][0]["score"], {"saw": "H-0000A1", "decision": "DIFFERENT_ENTITY"})
        self.assertIsNone(notes[0]["changed_by"])

    def test_enforcing_only_turns_clearances_into_reviews(self):
        plain, _ = self.run_with("off")
        lines, notes = self.run_with("enforce", Marker())
        self.assertEqual([l["decision"] for l in lines], ["REVIEW", "REVIEW", "SAME_ENTITY"])
        self.assertEqual(lines[0]["reason_code"], "INSUFFICIENT_DATA")
        self.assertIn("the marker layer objects", lines[0]["reason"])
        self.assertEqual(notes[0]["changed_by"], {"layer": "score", "why": "the marker layer objects"})
        self.assertEqual(notes[0]["rules"]["decision"], "DIFFERENT_ENTITY")   # what the rules said is kept
        self.assertEqual(lines[1:], plain[1:])                                  # nothing else moved
        self.assertFalse(any(a["decision"] != "DIFFERENT_ENTITY" and b["decision"] == "DIFFERENT_ENTITY"
                             for a, b in zip(plain, lines)))                    # no layer can clear

    def test_enforcing_works_without_an_explain_file(self):
        lines, _ = self.run_with("enforce", Marker(), explain=False)
        self.assertEqual([l["decision"] for l in lines], ["REVIEW", "REVIEW", "SAME_ENTITY"])

    def test_a_failing_layer_leaves_the_rules_standing(self):
        plain, _ = self.run_with("off")
        lines, notes = self.run_with("enforce", Broken())
        self.assertEqual(lines, plain)
        self.assertIsNone(notes[0]["people"][0]["score"])

    def test_a_missing_layer_is_simply_off(self):
        order, problems = layers.ORDER, []
        layers.ORDER = ("no_such_layer",)
        try:
            self.assertEqual(self._load(None, {"no_such_layer": "on"}, problems), [])
        finally:
            layers.ORDER = order
        self.assertEqual(len(problems), 1)
        self.assertIn("no_such_layer layer is off", problems[0])


class Config(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(layers.config("none"), {"score": "off", "briefing": "off", "reviewer": "off", "reader": "off"})
        got = layers.config("none,score=enforce,reviewer=shadow,reader=trust")
        self.assertEqual(got, {"score": "enforce", "briefing": "off", "reviewer": "on", "reader": "enforce"})
        self.assertEqual(layers.config("none,briefing")["briefing"], "on")
        self.assertEqual(layers.config("score=nonsense,unknown=on")["score"], layers.config("")["score"])


if __name__ == "__main__":
    unittest.main()
