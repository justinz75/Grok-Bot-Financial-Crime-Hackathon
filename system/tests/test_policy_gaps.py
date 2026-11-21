"""Verify the explain-only policy-gap layer with invented records and context."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_pipeline import Folder, RULES_ONLY, VARIANTS
from screening import pipeline
from screening.decide import DIFFERENT, REVIEW, SAME
from screening.layers import gaps


def verified(value, **extra):
    return dict(status="verified", value=value, source_ref="OPS-1",
                valid_from="2026-11-01", valid_until="2026-11-30", **extra)


def complete_case():
    return {field: verified(value) for field, value in {
        "product_custody": "payment", "legal_scope": "assessed", "availability": "scheduled",
        "effective_gate": True, "recall_available": True, "relationship": "direct",
        "chain_assessment": "complete", "ownership_assessment": "complete", "list_quality": "adequate",
        "identity_quality": "adequate", "reviewer_available": True, "premise_concern": "none",
    }.items()}


class PolicyGaps(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.snapshot = self.folder / "context.json"

    def context(self, cases, label="bank"):
        self.snapshot.write_text(json.dumps({"profile_id": "ops", "version": "1",
                                            "institution_type": label, "as_of": "2026-11-21",
                                            "cases": cases}), encoding="utf-8")
        return gaps.load_context(self.snapshot)

    def assess(self, decision, case, evidence=()):
        context, problem = self.context({"H-1": case})
        self.assertIsNone(problem)
        return gaps.annotate({"hit_id": "H-1", "decision": decision}, evidence, context)

    def test_overlap_keeps_urgency_and_missing_context(self):
        case = {"availability": verified("imminent")}
        result = self.assess(SAME, case)
        self.assertEqual([m["row"] for m in result["matches"]], ["T01", "T02", "T03"])
        self.assertIn("context.legal_scope", result["missing_fields"])
        self.assertFalse(result["complete"])
        case["effective_gate"] = verified(True)
        self.assertEqual([m["row"] for m in self.assess(SAME, case)["matches"]], ["T01", "T03"])

    def test_clearance_needs_complete_context_and_no_unresolved_assessments(self):
        case = complete_case()
        self.assertEqual(self.assess(DIFFERENT, case)["disposition"], "IDENTITY_CLOSED")
        case["ownership_assessment"] = verified("unresolved")
        case["legal_scope"] = {"status": "conflicting", "source_ref": "OPS-2"}
        result = self.assess(DIFFERENT, case)
        self.assertEqual([m["row"] for m in result["matches"]], ["T03", "T04"])
        case["legal_scope"] = verified("assessed")
        self.assertEqual(self.assess(DIFFERENT, case)["disposition"], "SPECIALIST_ASSESSMENT")

    def test_documented_premise_and_unavailable_reviewer(self):
        case = complete_case()
        case["premise_concern"] = verified("R10")
        case["reviewer_available"] = verified(False)
        evidence = [{"gap": "R10", "observations": [gaps.observation("hit.death", "2011", "H-1")]}]
        result = self.assess(DIFFERENT, case, evidence)
        self.assertEqual(result["disposition"], "SECOND_READER")
        self.assertIn("alternate", result["next_action"])
        self.assertEqual(result["matches"][0]["gaps"], ["R10"])

    def test_invalid_stale_and_unclassified_context_cannot_close(self):
        case = complete_case()
        case["effective_gate"] = verified(1)
        case["legal_scope"]["valid_until"] = "2026-11-20"
        result = self.assess(DIFFERENT, case, [{"gap": "R99", "observations": []}])
        self.assertEqual(result["disposition"], "UNKNOWN_CASE")
        self.assertIn("context.legal_scope", result["missing_fields"])
        self.assertIn("context.effective_gate", result["missing_fields"])
        self.assertFalse(result["complete"])
        self.snapshot.write_text('{"cases": {}, "cases": {}}', encoding="utf-8")
        context, problem = gaps.load_context(self.snapshot)
        self.assertIsNone(context)
        self.assertIsNotNone(problem)

    def test_complete_context_cannot_hide_unresolved_candidate_selection(self):
        evidence = [{"gap": "R07", "observations": [gaps.observation("candidate_count", 2, "A-1")]}]
        result = self.assess(DIFFERENT, complete_case(), evidence)
        self.assertEqual(result["matches"][0]["row"], "T08")
        self.assertIn("R07", result["matches"][0]["gaps"])

    def test_run_preserves_scored_bytes_and_uses_operating_exposure(self):
        data = Folder()
        rid = data.customer("Aster Vale", "1980-01-01")
        alert = data.alert("Aster Vale", account=data.field("accounts", "customer_id", rid, "account_id"))
        hit = data.hit(alert, "Aster Vale", countries=["Germany"])
        for name, rows in data.tables.items():
            (self.folder / (name + ".jsonl")).write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        (self.folder / "name_variants.json").write_text(json.dumps(VARIANTS), encoding="utf-8")
        scored, explain = self.folder / "scored.jsonl", self.folder / "out.explain.jsonl"
        pipeline.run(self.folder, scored, modes=RULES_ONLY)
        baseline = scored.read_bytes()
        self.assertEqual(json.loads(baseline)["decision"], REVIEW)
        case = complete_case()
        with patch.dict(os.environ, {"SCREENING_GAP_CONTEXT": str(self.snapshot)}):
            schedules = (("bank", "scheduled", True, "IDENTITY_REVIEW"),
                         ("bank", "imminent", False, "URGENT_SPECIALIST"),
                         ("fintech", "imminent", False, "URGENT_SPECIALIST"))
            matched = []
            for label, timing, gate, disposition in schedules:
                case.update(availability=verified(timing), effective_gate=verified(gate),
                            recall_available=verified(gate))
                self.context({hit: case}, label)
                pipeline.run(self.folder, scored, explain, RULES_ONLY)
                self.assertEqual(scored.read_bytes(), baseline)
                note = json.loads(explain.read_bytes())
                self.assertEqual(note["gaps"]["disposition"], disposition)
                self.assertIn("R09", [item["gap"] for item in note["people"][0]["gaps"]])
                matched.append(note["gaps"]["matches"])
            self.assertEqual(matched[1], matched[2])
            first = explain.read_bytes()
            pipeline.run(self.folder, scored, explain, RULES_ONLY)
            self.assertEqual(explain.read_bytes(), first)
            with patch.object(gaps, "annotate", side_effect=RuntimeError):
                pipeline.run(self.folder, scored, explain, RULES_ONLY)
            self.assertEqual(scored.read_bytes(), baseline)
            self.assertEqual(json.loads(explain.read_bytes())["gaps"]["disposition"], "UNKNOWN_CASE")
