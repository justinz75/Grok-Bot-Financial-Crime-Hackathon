"""Tests for tools/assure.py. Every name and record here is invented.

    python -m unittest discover -s tools/tests

The tool reads what the system writes and decides nothing, so the tests check three
things: each control says what its definition says, the sample is the same on every run,
and a whole run on a small invented folder leaves the decisions exactly as they were.
"""
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "system"))

import assure  # noqa: E402
from screening import pipeline  # noqa: E402
from screening.names import NameRules  # noqa: E402

D, S, R = assure.DIFFERENT, assure.SAME, assure.REVIEW


def person(codes, name="agree", dob="unknown", location="unknown", customer=None, hit=None, score=None, records=("CUS-000001",)):
    base_customer = {"kind": "person", "verified_name": "LARS HOLM", "dob": "1977-12-13", "dob_source": "KYC-0000A1"}
    base_hit = {"kind": "person", "name": "Holm, Lars", "aliases": [], "dobs": [], "dob_origin": None}
    base_customer.update(customer or {})
    base_hit.update(hit or {})
    return {"record_ids": list(records), "all_codes": list(codes), "reason_code": codes[0] if codes else None,
            "customer": base_customer, "hit": base_hit, "states": {"name": name, "dob": dob, "location": location},
            "score": score}


def explain(*people, **extra):
    line = {"people": list(people), "changed_by": None, "layers": {"score": "on"}}
    line.update(extra)
    return line


class Alerts(unittest.TestCase):
    def test_an_alert_closes_only_when_every_hit_is_cleared(self):
        self.assertEqual(assure.disposition([D, D, D]), assure.CLOSED)
        self.assertEqual(assure.disposition([D, R, D]), assure.REVIEW)
        self.assertEqual(assure.disposition([D]), assure.CLOSED)

    def test_one_match_sends_the_alert_to_compliance(self):
        self.assertEqual(assure.disposition([D, R, S]), assure.ESCALATE)

    def test_an_alert_without_hits_is_not_called_closed(self):
        self.assertEqual(assure.disposition([]), assure.NO_HITS)


class OrderOfWork(unittest.TestCase):
    def test_a_sanctions_category_anywhere_makes_it_a_sanctions_listing(self):
        self.assertEqual(assure.listing({"primary_category": "PEP", "categories": ["PEP", "Sanctions"]}), ("sanctions", "PEP"))
        self.assertEqual(assure.listing({"primary_category": "", "categories": ["Adverse Media"]}), ("other", "Adverse Media"))
        self.assertEqual(assure.listing({}), ("other", "unknown"))
        self.assertEqual(assure.listing(None), ("other", "unknown"))

    def test_the_four_levels(self):
        self.assertEqual(assure.priority(S, "sanctions", False), "P1")
        self.assertEqual(assure.priority(R, "sanctions", True), "P1")
        self.assertEqual(assure.priority(R, "sanctions", False), "P2")
        self.assertEqual(assure.priority(S, "other", False), "P2")
        self.assertEqual(assure.priority(R, "other", True), "P3")
        self.assertEqual(assure.priority(R, "other", False), "P4")

    def test_strong_evidence_comes_from_the_score_band(self):
        strong = explain(person([], score={"bits": 9.1, "band": assure.STRONG_SAME}))
        some = explain(person([], score={"bits": 5.0, "band": "some evidence of the same"}))
        self.assertTrue(assure.likely_same(strong))
        self.assertFalse(assure.likely_same(some))

    def test_without_a_score_a_name_and_a_country_are_not_strong_evidence(self):
        self.assertFalse(assure.likely_same(explain(person([], name="agree", location="agree"))))
        self.assertTrue(assure.likely_same(explain(person([], name="agree", dob="agree"))))
        self.assertFalse(assure.likely_same(None))


class WhatKeepsAReviewOpen(unittest.TestCase):
    def cause(self, line, scored=None):
        return assure.review_cause(scored or {"reason_code": "INSUFFICIENT_DATA"}, line)

    def test_each_cause(self):
        self.assertIn("several customers", self.cause(explain(), {"reason_code": "AMBIGUOUS_CUSTOMER_RECORD"}))
        self.assertIn("no customer record", self.cause(explain(person([], records=()))))
        self.assertIn("no country is shared", self.cause(explain(person([], "agree", "agree", "mismatch"))))
        self.assertIn("name cannot be confirmed", self.cause(explain(person([], "unknown", "agree"))))
        self.assertIn("listing gives no date", self.cause(explain(person([], "agree"))))
        self.assertIn("customer has no date", self.cause(explain(person([], "agree", customer={"dob": None}, hit={"dobs": ["1977"]}))))
        self.assertIn("neither agree nor contradict", self.cause(explain(person([], "agree", hit={"dobs": ["1978"]}))))
        self.assertIn("no country ties the company", self.cause(explain(person([], "agree", customer={"kind": "company"}))))
        self.assertIn("could not be compared", self.cause(explain()))
        self.assertIn("a layer asked", self.cause(explain(person([]), changed_by={"layer": "score", "why": "x"})))


class Flags(unittest.TestCase):
    def flags(self, line, tier="other", record="CUS-000001", challenger=None):
        return assure.qa_flags({"customer_record_id": record}, line, tier, challenger)

    def test_a_clearance_on_two_grounds_far_apart_has_no_flag(self):
        line = explain(person(["DOB_MISMATCH", "LOCATION_MISMATCH"], hit={"dobs": ["1951"], "dob_origin": "listed"}))
        self.assertEqual(self.flags(line), [])
        self.assertEqual(self.flags(line, tier="sanctions"), [])

    def test_a_date_only_clearance_close_to_the_tolerance_is_flagged(self):
        near = explain(person(["DOB_MISMATCH"], hit={"dobs": ["1975", "1974"], "dob_origin": "listed"}))
        far = explain(person(["DOB_MISMATCH"], hit={"dobs": ["1951"], "dob_origin": "listed"}))
        self.assertEqual(self.flags(near), ["narrow_date_gap"])
        self.assertEqual(self.flags(far), [])

    def test_a_date_read_from_text_and_a_declared_date_are_flagged(self):
        read = explain(person(["DOB_MISMATCH"], hit={"dobs": ["1951"], "dob_origin": "search"}))
        declared = explain(person(["DOB_MISMATCH"], customer={"dob_source": "CUS-000001"},
                                  hit={"dobs": ["1951"], "dob_origin": "listed"}))
        self.assertEqual(self.flags(read), ["inferred_hit_date"])
        self.assertEqual(self.flags(declared), ["declared_date_only"])

    def test_sanctions_on_one_ground_several_people_and_a_score_conflict(self):
        one = explain(person(["LOCATION_MISMATCH"]))
        self.assertEqual(self.flags(one, tier="sanctions"), ["sanctions_one_ground"])
        self.assertEqual(self.flags(one, record="AMBIGUOUS"), ["several_people"])
        self.assertEqual(self.flags(explain(person(["LOCATION_MISMATCH"]), person(["LOCATION_MISMATCH"]))), ["several_people"])
        conflict = explain(person(["LOCATION_MISMATCH"], score={"bits": 4.0, "band": "x", "conflict": True}))
        self.assertEqual(self.flags(conflict), ["score_conflict"])

    def test_flags_come_out_in_the_order_they_are_listed(self):
        line = explain(person(["DOB_MISMATCH"], hit={"dobs": ["1978-01-02"], "dob_origin": "notes"},
                              score={"bits": 5.0, "band": "x", "conflict": True}))
        self.assertEqual(self.flags(line, tier="sanctions", record="AMBIGUOUS"),
                         ["score_conflict", "narrow_date_gap", "inferred_hit_date", "sanctions_one_ground", "several_people"])


class ChallengerMatcher(unittest.TestCase):
    def setUp(self):
        self.rules, self.loose = NameRules(), assure.Challenger()

    def test_a_swap_of_two_letters_is_two_edits_for_the_policy_and_one_for_the_challenger(self):
        self.assertFalse(self.rules.part_match("holm", "hlom"))
        self.assertTrue(self.loose.part_match("holm", "hlom"))

    def test_the_challenger_never_matches_less_than_the_policy(self):
        for a, b in (("lars", "lars"), ("anthony", "tony"), ("katerina", "katarina"), ("holm", "holme")):
            self.assertTrue(self.rules.part_match(a, b))
            self.assertTrue(self.loose.part_match(a, b))

    def test_short_parts_and_different_names_still_differ(self):
        self.assertFalse(self.loose.part_match("ali", "ala"))
        self.assertFalse(self.loose.part_match("lars", "omar"))
        self.assertFalse(self.loose.part_match("bergstrom", "lindqvist"))

    def test_a_name_clearance_the_challenger_would_not_make_is_a_near_miss(self):
        near = person(["NAME_MISMATCH_VERIFIED"], "mismatch", customer={"verified_name": "LARS HLOM"})
        far = person(["NAME_MISMATCH_VERIFIED"], "mismatch", customer={"verified_name": "OMAR HOLM"})
        self.assertTrue(assure.name_near_miss(near, self.loose))
        self.assertFalse(assure.name_near_miss(far, self.loose))
        self.assertEqual(assure.qa_flags({}, explain(near), "other", self.loose), ["name_near_miss"])
        self.assertEqual(assure.qa_flags({}, explain(far), "other", self.loose), [])

    def test_a_near_miss_is_only_flagged_when_name_is_the_only_ground(self):
        near = person(["DOB_MISMATCH", "NAME_MISMATCH_VERIFIED"], "mismatch", customer={"verified_name": "LARS HLOM"},
                      hit={"dobs": ["1951"], "dob_origin": "listed"})
        self.assertEqual(assure.qa_flags({}, explain(near), "other", self.loose), [])


class Sample(unittest.TestCase):
    IDS = ["H-%06X" % n for n in range(1, 61)]

    def test_the_same_hits_whatever_order_they_arrive_in(self):
        self.assertEqual(assure.pick(self.IDS, 10, 5), assure.pick(list(reversed(self.IDS)), 10, 5))

    def test_the_share_the_floor_and_the_population(self):
        self.assertEqual(len(assure.pick(self.IDS, 10, 5)), 6)
        self.assertEqual(len(assure.pick(self.IDS, 10, 20)), 20)
        self.assertEqual(len(assure.pick(self.IDS[:3], 10, 5)), 3)
        self.assertEqual(assure.pick([], 10, 5), [])

    def test_a_larger_share_keeps_what_a_smaller_one_drew(self):
        small, large = assure.pick(self.IDS, 10, 0), assure.pick(self.IDS, 50, 0)
        self.assertTrue(set(small) <= set(large))

    def test_flagged_clearances_are_all_read_and_the_rest_are_sampled_by_reason_code(self):
        scored = [{"hit_id": h, "decision": D, "reason_code": "LOCATION_MISMATCH", "customer_record_id": "CUS-000001"}
                  for h in self.IDS[:40]]
        scored += [{"hit_id": h, "decision": D, "reason_code": "DOB_MISMATCH", "customer_record_id": "CUS-000001"}
                   for h in self.IDS[40:50]]
        scored += [{"hit_id": h, "decision": R, "reason_code": "INSUFFICIENT_DATA", "customer_record_id": "CUS-000001"}
                   for h in self.IDS[50:]]
        lines = dict((s["hit_id"], explain(person([s["reason_code"]], hit={"dobs": ["1951"], "dob_origin": "listed"})))
                     for s in scored)
        flagged = self.IDS[40]
        lines[flagged] = explain(person(["DOB_MISMATCH"], hit={"dobs": ["1976"], "dob_origin": "listed"}))
        got = assure.qa_sample(scored, lines, {}, rate=10, floor=2)
        self.assertEqual([g for g in got if g[1] == "flagged"], [(flagged, "flagged", ["narrow_date_gap"])])
        drawn = [g[0] for g in got if g[1] == "sampled"]
        self.assertEqual(len([h for h in drawn if h in self.IDS[:40]]), 4)     # 10% of 40
        self.assertEqual(len([h for h in drawn if h in self.IDS[41:50]]), 2)   # the floor, from the 9 unflagged
        self.assertFalse([h for h in drawn if h in self.IDS[50:]])             # a review is never in the sample
        self.assertEqual(got, assure.qa_sample(list(scored), lines, {}, rate=10, floor=2))


class NameRule(unittest.TestCase):
    def test_variations_on_invented_names(self):
        rules = NameRules()
        got = dict((row[0], row[1:]) for row in assure.name_rule_test(
            ["Lars Holm", "Mira Okafor-Lindqvist", "Dana Maria Castellanos", "Lars Holm", "Madonna", None], rules))
        self.assertEqual(got["capitals"], (3, 3, 1, 1))                # the repeat and the one-part name are left out
        self.assertEqual(got["surname first, with a comma"][:2], (3, 3))
        self.assertEqual(got["a middle initial added"][:2], (3, 3))
        self.assertEqual(got["first part replaced by another name"], (3, 2, 1, 0))
        # "holm" swapped to "hlom" is two edits in a four-letter part: the policy says different
        self.assertEqual(got["two neighbouring letters swapped"][2:], (1, 0))

    def test_every_variation_changes_the_name_or_does_not_apply(self):
        for label, vary in assure.VARIATIONS:
            for parts in (("lars", "holm"), ("dana", "maria", "castellanos"), ("aa", "bb")):
                try:
                    changed = vary(parts)
                except (IndexError, ValueError):
                    changed = None
                if changed is not None:
                    self.assertNotEqual(changed, " ".join(parts), label)


class UnusedFacts(unittest.TestCase):
    def test_what_is_counted(self):
        folder = tempfile.mkdtemp(prefix="assure-facts-")
        try:
            tables = {
                "kyc_checks": [
                    {"check_id": "KYC-0000A1", "document_number": "P-1234567", "verified_name": "LARS HOLM",
                     "verified_dob": "1977-12-13", "checked_at": "2024-01-05", "result": "approved"},
                    {"check_id": "KYC-0000A2", "document_number": "X99", "verified_name": "MIRA OKAFOR",
                     "verified_dob": "2025-03-01", "checked_at": "2024-01-05", "result": "approved"},
                    {"check_id": "KYC-0000A3", "document_number": "Z1", "verified_name": "DANA REYES",
                     "verified_dob": "2025-03-01", "checked_at": "2024-01-05", "result": "rejected"}],
                "customers": [{"record_id": "CUS-000001", "registration_number": "HRB 99887"}],
            }
            for name, rows in tables.items():
                with open(os.path.join(folder, name + ".jsonl"), "w", encoding="utf-8", newline="\n") as handle:
                    for row in rows:
                        handle.write(json.dumps(row) + "\n")
            hits = {
                "H-0000A1": {"name": "Lars Holm", "identifiers": ["Passport: p1234567"], "gender": "Male",
                             "life_status": "Deceased", "deceased_date": None, "aliases": ["Ларс Хольм"]},
                "H-0000A2": {"name": "Lars Holm", "identifiers": ["Other: 12"], "gender": "",
                             "life_status": "Deceased", "deceased_date": "2022-03", "aliases": ["L. Holm"]},
                "H-0000A3": {"name": "Holm GmbH", "identifiers": ["BusinessRegistrationNumber: HRB-99887", "LexID: 5550001"]},
            }
            lines = {"H-0000A1": explain(person(["DOB_MISMATCH"], dob="mismatch", customer={"dob_source": "KYC-0000A2"})),
                     "H-0000A2": explain(person([], dob="unknown", customer={"dob_source": "KYC-0000A2"}))}
            counts = [count for _label, count in assure.unused_facts(folder, hits, lines)]
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        # identifiers 2 (a two-character one is not a number), both held by the bank; one gender on a hit,
        # none on a customer; one death with no date; one alias in another script; no name in another
        # script on either side; one approved check dated before the birth it verifies, used by one comparison
        self.assertEqual(counts, [2, 2, 1, 0, 1, 1, 0, 0, 1, 1])


class WholeRun(unittest.TestCase):
    """One closed alert, one that goes to compliance and one that waits for a person."""

    def setUp(self):
        self.folder, self.out = tempfile.mkdtemp(prefix="assure-data-"), tempfile.mkdtemp(prefix="assure-out-")
        tables = dict((name, []) for name in ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks",
                                              "notes", "search_results"))

        def customer(n, name, dob, country):
            rid = "CUS-%06d" % n
            tables["customers"].append({"record_id": rid, "entity_type": "Individual", "full_name": name, "dob": dob,
                                        "nationality": country, "residence_country": country, "city": "Springfield",
                                        "address": "1 Main Street, Springfield", "email": "user%d@mail.example" % n,
                                        "phone": "+49 %07d" % n})
            tables["accounts"].append({"account_id": "ACC-%06X" % n, "customer_id": rid, "login_handle": "login%d" % n,
                                       "phone": "+49 %07d" % n})
            tables["onboarding"].append({"account_id": "ACC-%06X" % n, "customer_id": rid, "kyc_applicant_id": "APP-%06X" % n})
            tables["kyc_checks"].append({"check_id": "KYC-%06X" % n, "applicant_id": "APP-%06X" % n, "verified_name": name.upper(),
                                         "verified_dob": dob, "document_type": "passport", "document_number": "D%d" % n,
                                         "document_country": country, "result": "approved", "checked_at": "2024-01-05"})

        def alert(n, name, account, hits):
            tables["alerts"].append({"alert_id": "A-%06X" % n, "screened_at": "2026-11-06", "account_ref": account,
                                     "login_handle": None, "email": None, "hit_ids": [h["hit_id"] for h in hits],
                                     "customer": {"name": name, "entity_type": "Individual", "dob": None, "country": None, "city": None}})
            for h in hits:
                h["alert_id"] = "A-%06X" % n
                tables["hits"].append(h)

        def hit(n, name, dobs, country, category):
            return {"hit_id": "H-%06X" % n, "entity_type": "Individual", "name": name, "aliases": [], "dobs": dobs,
                    "countries": [country], "categories": [category], "primary_category": category, "profile_notes": None}

        customer(1, "Lars Holm", "1977-12-13", "Germany")
        customer(2, "Mira Okafor", "1988-04-02", "Nigeria")
        alert(1, "Lars Holm", "ACC-000001", [hit(1, "Lars Holm", ["1951"], "Germany", "Sanctions")])
        alert(2, "Mira Okafor", "ACC-000002", [hit(2, "Mira Okafor", ["1988-04-02"], "Nigeria", "PEP"),
                                               hit(3, "Mira Okafor", [], "Nigeria", "Adverse Media")])
        alert(3, "Lars Holm", "ACC-000001", [hit(4, "Lars Holm", [], "Germany", "Sanctions")])
        for name, rows in tables.items():
            with open(os.path.join(self.folder, name + ".jsonl"), "w", encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps(row) + "\n")

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)
        shutil.rmtree(self.out, ignore_errors=True)

    def read(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def run_quietly(self, out=None):
        saved = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = open(os.devnull, "w")
        try:
            return assure.main([self.folder, "--out", out or self.out])
        finally:
            sys.stdout.close()
            sys.stdout, sys.stderr = saved

    def test_the_pack_on_a_small_folder(self):
        self.assertEqual(self.run_quietly(), 0)
        alerts = dict((row["alert_id"], row) for row in self.read("alerts.csv"))
        self.assertEqual(alerts["A-000001"]["disposition"], "CLOSED")
        self.assertEqual(alerts["A-000002"]["disposition"], "ESCALATE")
        self.assertEqual(alerts["A-000003"]["disposition"], "REVIEW")
        self.assertEqual((alerts["A-000001"]["priority"], alerts["A-000002"]["priority"], alerts["A-000003"]["priority"]),
                         ("", "P2", "P2"))

        queue = self.read("review_queue.csv")
        self.assertEqual([(row["hit_id"], row["priority"], row["queue"]) for row in queue],
                         [("H-000002", "P2", "compliance"), ("H-000004", "P2", "analyst"), ("H-000003", "P4", "analyst")])
        self.assertEqual(queue[1]["what_keeps_it_open"], "the listing gives no date of birth")

        sample = self.read("qa_sample.csv")
        self.assertEqual([(row["hit_id"], row["reason_code"], row["basis"], row["flags"]) for row in sample],
                         [("H-000001", "DOB_MISMATCH", "flagged", "sanctions_one_ground")])

        with open(os.path.join(self.out, "manifest.json"), encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(record["data"]["hits.jsonl"]["rows"], 4)
        self.assertEqual(len(record["data"]["hits.jsonl"]["sha256"]), 64)
        self.assertEqual(record["output"]["decisions"], {"DIFFERENT_ENTITY": 1, "SAME_ENTITY": 1, "REVIEW": 2})
        self.assertEqual(len(record["code"]["sha256"]), 64)

    def test_two_runs_write_the_same_bytes(self):
        second = tempfile.mkdtemp(prefix="assure-out2-")
        try:
            self.assertEqual(self.run_quietly(), 0)
            self.assertEqual(self.run_quietly(second), 0)
            for name in ("alerts.csv", "review_queue.csv", "qa_sample.csv", "manifest.json", "summary.txt"):
                with open(os.path.join(self.out, name), "rb") as a, open(os.path.join(second, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)
        finally:
            shutil.rmtree(second, ignore_errors=True)

    def test_the_decisions_are_exactly_what_the_system_alone_gives(self):
        scored = os.path.join(self.out, "scored.jsonl")
        saved = sys.stderr
        sys.stderr = open(os.devnull, "w")
        try:
            pipeline.run(self.folder, scored)
        finally:
            sys.stderr.close()
            sys.stderr = saved
        with open(scored, encoding="utf-8") as handle:
            alone = dict((row["hit_id"], row["decision"]) for row in map(json.loads, handle))
        self.assertEqual(self.run_quietly(), 0)
        with open(os.path.join(self.out, "manifest.json"), encoding="utf-8") as handle:
            record = json.load(handle)
        counted = {}
        for decision in alone.values():
            counted[decision] = counted.get(decision, 0) + 1
        self.assertEqual(record["output"]["decisions"], counted)
        self.assertEqual(record["output"]["scored_sha256"], assure.sha256_file(scored))


if __name__ == "__main__":
    unittest.main()
