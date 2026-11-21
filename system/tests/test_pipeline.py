"""End-to-end tests for situations the policy covers but the development set barely shows.

Each test builds the smallest invented data folder that shows one situation, runs the
whole system on it and checks the decision, the reason code and the customer record.
Run:  python -m unittest discover -s system/tests
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

TABLES = ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks", "notes", "search_results")
RULES_ONLY = dict((name, "off") for name in layers.NAMES)
VARIANTS = {"groups": [["tony", "anthony"], ["muhammad", "mohammed"]], "company_legal_forms": ["ltd", "gmbh", "sa"]}


class Folder(object):
    """A small invented data folder, built record by record."""

    def __init__(self):
        self.tables = dict((name, []) for name in TABLES)
        self.n = 0

    def _id(self, prefix, width=6):
        self.n += 1
        return "%s-%s" % (prefix, ("%X" % self.n).zfill(width) if prefix != "CUS" else str(self.n).zfill(width))

    def customer(self, name, dob=None, country="Germany", kind="Individual", phone=None, verified="same",
                 result="approved", checked_at="2024-01-05", document=None, account=None, nationality=None):
        """A customer record with an account and, unless verified is None, one identity check.
        verified: 'same' copies the record, or (legal name, date of birth, document country)."""
        rid, app = self._id("CUS"), self._id("APP")
        account = account or self._id("ACC")
        email = "user%d@mail.example" % self.n
        self.tables["customers"].append({
            "record_id": rid, "entity_type": kind, "full_name": name, "preferred_name": None, "login_name": None,
            "dob": dob, "nationality": nationality or country, "residence_country": country, "city": "Springfield",
            "address": "1 Main Street, Springfield", "email": email, "phone": phone or "+49 %07d" % self.n})
        self.tables["accounts"].append({"account_id": account, "customer_id": rid, "login_handle": "login%d" % self.n,
                                        "phone": phone or "+49 %07d" % self.n})
        self.tables["onboarding"].append({"account_id": account, "customer_id": rid, "kyc_applicant_id": app})
        if verified is not None:
            legal, born, issued = (name, dob, country) if verified == "same" else verified
            self.check(app, legal, born, issued, result, checked_at, document)
        return rid

    def check(self, applicant, legal, born, issued, result="approved", checked_at="2024-01-05", document=None):
        check_id = self._id("KYC")
        self.tables["kyc_checks"].append({
            "check_id": check_id, "applicant_id": applicant, "provider": "Example", "verified_name": legal,
            "verified_dob": born, "document_type": "passport", "document_number": document or "D%d" % self.n,
            "document_country": issued, "result": result, "checked_at": checked_at})
        return check_id

    def field(self, table, key, record_id, name):
        return [row for row in self.tables[table] if row[key] == record_id][0][name]

    def alert(self, name, account=None, login=None, email=None, dob=None, country=None, city=None,
              kind="Individual", screened_at="2026-11-06"):
        alert_id = self._id("A")
        self.tables["alerts"].append({
            "alert_id": alert_id, "screened_at": screened_at,
            "customer": {"name": name, "entity_type": kind, "dob": dob, "country": country, "city": city},
            "account_ref": account, "login_handle": login, "email": email, "hit_ids": []})
        return alert_id

    def hit(self, alert_id, name, dobs=(), countries=(), kind="Individual", category="PEP", notes=None,
            deceased=None, aliases=()):
        hit_id = self._id("H")
        self.tables["hits"].append({
            "hit_id": hit_id, "alert_id": alert_id, "entity_type": kind, "name": name, "aliases": list(aliases),
            "dobs": list(dobs), "place_of_birth": None, "deceased_date": deceased, "nationality": [],
            "citizenship": [], "countries": list(countries), "addresses": [], "categories": [category],
            "primary_category": category, "profile_notes": notes})
        for alert in self.tables["alerts"]:
            if alert["alert_id"] == alert_id:
                alert["hit_ids"].append(hit_id)
        return hit_id

    def note(self, record_id, text, channel="phone", created_at="2024-02-01"):
        note_id = self._id("NOTE")
        self.tables["notes"].append({"note_id": note_id, "requester_email": self.field("customers", "record_id", record_id, "email"),
                                     "created_at": created_at, "channel": channel, "text": text})
        return note_id

    def search(self, query, snippet):
        result_id = self._id("SR")
        self.tables["search_results"].append({"result_id": result_id, "query": query, "title": "x", "snippet": snippet,
                                              "source": "news.example"})
        return result_id

    def run(self):
        folder = tempfile.mkdtemp(prefix="pipeline-")
        try:
            for name, rows in self.tables.items():
                with open(os.path.join(folder, name + ".jsonl"), "w", encoding="utf-8") as handle:
                    for row in rows:
                        handle.write(json.dumps(row) + "\n")
            with open(os.path.join(folder, "name_variants.json"), "w", encoding="utf-8") as handle:
                json.dump(VARIANTS, handle)
            outputs = []
            for attempt in (1, 2):
                path = os.path.join(folder, "out%d.jsonl" % attempt)
                pipeline.run(folder, path, None, RULES_ONLY)
                with open(path, "rb") as handle:
                    outputs.append(handle.read())
        finally:
            shutil.rmtree(folder, ignore_errors=True)
        assert outputs[0] == outputs[1], "two runs gave different files"
        lines = [json.loads(line) for line in outputs[0].decode("utf-8").splitlines()]
        assert [l["hit_id"] for l in lines] == [h["hit_id"] for h in self.tables["hits"]], "one line per hit, in order"
        known = set(row[key] for table, key in (("customers", "record_id"), ("kyc_checks", "check_id"), ("notes", "note_id"),
                                                 ("search_results", "result_id")) for row in self.tables[table])
        for line in lines:
            for item in line["evidence"]:
                assert item in known or "#" in item, "evidence %s is not a record in the folder" % item
        return dict((line["hit_id"], line) for line in lines)


class RareCases(unittest.TestCase):
    def check(self, line, decision, code=None, record="unset"):
        self.assertEqual(line["decision"], decision, line["reason"])
        if code:
            self.assertEqual(line["reason_code"], code, line["reason"])
        if record != "unset":
            self.assertEqual(line["customer_record_id"], record, line["reason"])

    def test_01_account_link_and_verified_date_of_birth(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", ["1951"], ["Germany"])
        self.check(f.run()[h], "DIFFERENT_ENTITY", "DOB_MISMATCH", rid)

    def test_02_joint_account_screened_details_pick_the_holder(self):
        f = Folder()
        first = f.customer("Greta Holm", "1980-02-02", account="ACC-JOINT1")
        second = f.customer("Lars Holm", "1977-12-13", account="ACC-JOINT1")
        a = f.alert("Lars Holm", account="ACC-JOINT1", dob="1977-12-13")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH", second)
        self.assertNotEqual(first, second)

    def test_03_verified_name_beats_the_record_name(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", verified=("GRETA HOLM", "1977-12-13", "Germany"))
        a = f.alert("Lars Holm", login=f.field("accounts", "customer_id", rid, "login_handle"))
        h = f.hit(a, "Holm, Lars", [], ["Germany"])
        self.check(f.run()[h], "DIFFERENT_ENTITY", "NAME_MISMATCH_VERIFIED", rid)

    def test_04_email_link_name_and_date_agree(self):
        f = Folder()
        rid = f.customer("Li Wei", "1975-06-02", "Singapore")
        a = f.alert("Li Wei", email=f.field("customers", "record_id", rid, "email"))
        h = f.hit(a, "Wei Li", ["1975"], ["Singapore"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH", rid)

    def test_05_no_link_search_then_location(self):
        f = Folder()
        rid = f.customer("Marta Ortega", "1968-03-05", "Spain")
        f.customer("Marta Ortega", "1990-01-01", "Spain")       # same name, another date of birth: does not fit
        a = f.alert("Marta Ortega", dob="1968-03-05", country="Spain")
        h = f.hit(a, "Ortega, Marta", [], ["Brazil"])
        self.check(f.run()[h], "DIFFERENT_ENTITY", "LOCATION_MISMATCH", rid)

    def test_06_two_people_fit_and_disagree(self):
        f = Folder()
        f.customer("Chen Ming", "1988-03-14", "China", verified=("CHEN MING", "1988-03-14", "China"))
        f.customer("Chen Ming", "1988-03-14", "China", verified=("CHEN MING", "1958-03-14", "China"))
        a = f.alert("Chen Ming", dob="1988-03-14", country="China")
        h = f.hit(a, "Ming Chen", ["1988"], ["China"])
        self.check(f.run()[h], "REVIEW", "AMBIGUOUS_CUSTOMER_RECORD", "AMBIGUOUS")

    def test_07_two_people_fit_and_agree(self):
        f = Folder()
        f.customer("Chen Ming", "1988-03-14", "China")
        f.customer("Chen Ming", "1988-03-14", "China")
        a = f.alert("Chen Ming", dob="1988-03-14", country="China")
        h = f.hit(a, "Ming Chen", [], ["Peru"])
        self.check(f.run()[h], "DIFFERENT_ENTITY", "LOCATION_MISMATCH", "AMBIGUOUS")

    def test_08_no_record_fits(self):
        f = Folder()
        f.customer("Somebody Else", "1970-01-01")
        a = f.alert("Lars Holm", dob="1977-12-13", country="Germany")
        h = f.hit(a, "Holm, Lars", ["1930"], ["Peru"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA", None)

    def test_09_same_phone_and_date_of_birth_is_one_person(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", "Germany", phone="+49 5550001")
        other = f.customer("Lars Holm", "13/12/1977", "Peru", phone="+49 5550001")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", [], ["Peru"])
        line = f.run()[h]
        self.assertNotEqual(line["decision"], "DIFFERENT_ENTITY", line["reason"])
        self.assertIn(line["customer_record_id"], (rid, other))

    def test_10_same_phone_alone_is_family(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", "Germany", phone="+49 5550001")
        f.customer("Lars Holm", "2001-05-05", "Peru", phone="+49 5550001")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", [], ["Peru"])
        self.check(f.run()[h], "DIFFERENT_ENTITY", "LOCATION_MISMATCH", rid)

    def test_11_rejected_check_is_not_evidence(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13")
        applicant = f.field("onboarding", "customer_id", rid, "kyc_applicant_id")
        f.check(applicant, "LARS HOLM", "1940-01-01", "Germany", result="rejected", checked_at="2025-06-01")
        f.check(applicant, "LARS HOLM", "1940-01-01", "Germany", result="expired", checked_at="2025-07-01")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH", rid)

    def test_12_approved_check_written_only_as_a_note(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1990-01-01", verified=None)
        note = f.note(rid, "The provider verified the passport of LARS HOLM, born 1977-12-13, issued in Germany, on 2024-03-01.",
                      channel="kyc", created_at="2024-03-01")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", ["1951"], ["Germany"])
        line = f.run()[h]
        self.check(line, "DIFFERENT_ENTITY", "DOB_MISMATCH", rid)
        self.assertEqual(line["evidence"], [note])
        self.assertIn("1977-12-13", line["reason"])

    def test_13_company_name_and_country(self):
        f = Folder()
        rid = f.customer("Marisol SA", "2001-01-01", "Spain", kind="Company")
        a = f.alert("Marisol SA", account=f.field("accounts", "customer_id", rid, "account_id"), kind="Company")
        h = f.hit(a, "Marisol, Sociedad Anonima", [], ["Spain"], kind="Company")
        self.check(f.run()[h], "SAME_ENTITY", "NAME_LOCATION_MATCH", rid)

    def test_14_company_incorporated_after_the_report(self):
        f = Folder()
        rid = f.customer("Marisol SA", "2021-05-05", "Spain", kind="Company")
        a = f.alert("Marisol SA", account=f.field("accounts", "customer_id", rid, "account_id"), kind="Company")
        h = f.hit(a, "Marisol SA", [], ["Spain"], kind="Company",
                  notes="According to news.test; March 3, 2015: The company was fined.")
        self.check(f.run()[h], "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY", rid)

    def test_15_person_against_company(self):
        f = Folder()
        rid = f.customer("Mark Baker", "1980-01-01")
        a = f.alert("Mark Baker", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Baker Mark Ltd", [], ["Germany"], kind="Company")
        self.check(f.run()[h], "DIFFERENT_ENTITY", "ENTITY_TYPE_MISMATCH", rid)

    def test_16_died_before_screening(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", [], ["Germany"], deceased="2025-10")
        line = f.run()[h]
        self.check(line, "DIFFERENT_ENTITY", "DECEASED", rid)
        self.assertIn("%s#deceased_date" % h, line["evidence"])

    def test_17_died_after_screening_does_not_clear(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", [], ["Germany"], deceased="2027-01-01")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA", rid)

    def test_18_country_difference_does_not_clear_name_and_date(self):
        f = Folder()
        rid = f.customer("Li Wei", "1975-06-02", "Singapore")
        a = f.alert("Li Wei", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Wei Li", ["1975"], ["China"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA", rid)

    def test_19_one_real_name_part_neither_clears_nor_confirms(self):
        f = Folder()
        rid = f.customer("Unknown Farooq", "1968-08-20", "Pakistan", verified=("UNKNOWN FAROOQ", "1968-08-20", "Pakistan"))
        a = f.alert("UNKNOWN FAROOQ", account=f.field("accounts", "customer_id", rid, "account_id"))
        clear = f.hit(a, "Ghani Khan", [], ["Pakistan"])
        confirm = f.hit(a, "Muhammad Farooq", ["1968"], ["Pakistan"])
        lines = f.run()
        self.check(lines[clear], "REVIEW", "INSUFFICIENT_DATA", rid)
        self.check(lines[confirm], "REVIEW", "INSUFFICIENT_DATA", rid)

    def test_20_search_result_about_the_hit_not_a_namesake(self):
        f = Folder()
        rid = f.customer("Tunde Bakare", "1990-04-04", "Nigeria")
        a = f.alert("Tunde Bakare", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Bakare, Tunde", [], ["Nigeria"], category="Enforcement")
        f.search("bakare tunde", "Tunde Bakare, 34, a university lecturer in Nigeria, was quoted in May 2024.")
        f.search("bakare tunde", "Tunde Bakare, 34, the subject of enforcement action in Ghana, was named in May 2024.")
        right = f.search("bakare tunde", "Tunde Bakare, 61, the subject of enforcement action in Nigeria, was named in May 2024.")
        line = f.run()[h]
        self.check(line, "DIFFERENT_ENTITY", "DOB_MISMATCH", rid)
        self.assertEqual([e for e in line["evidence"] if e.startswith("SR-")], [right])

    def test_21_too_young_at_the_earliest_report(self):
        f = Folder()
        rid = f.customer("Tom Okafor", "2008-02-02", "Nigeria")
        a = f.alert("Tom Okafor", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Thomas Okafor", [], ["Nigeria"], category="Adverse Media",
                  notes="According to news.test; June 9, 2020: He was charged with fraud.\n\nAccording to news.test; May 1, 2022: He was convicted.")
        self.check(f.run()[h], "DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY", rid)

    def test_22_a_note_about_where_they_lived_blocks_a_location_clearance(self):
        f = Folder()
        rid = f.customer("Marta Ortega", "1968-03-05", "Spain")
        f.note(rid, "The client said they lived and worked in Brazil from 2010 to 2014.")
        a = f.alert("Marta Ortega", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Ortega, Marta", [], ["Brazil"])
        line = f.run()[h]
        self.assertNotEqual(line["decision"], "DIFFERENT_ENTITY", line["reason"])
        self.assertEqual(line["customer_record_id"], rid)

    def test_23_same_document_number_is_one_person(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", "Germany", document="P123")
        f.customer("Lars Holm", "1977-12-13", "Peru", document="P123")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", [], ["Peru"])
        self.assertNotEqual(f.run()[h]["decision"], "DIFFERENT_ENTITY")

    def test_24_a_link_that_leads_nowhere_falls_back_to_the_search(self):
        f = Folder()
        rid = f.customer("Marta Ortega", "1968-03-05", "Spain")
        a = f.alert("Marta Ortega", account="ACC-NOSUCH", dob="1968-03-05", country="Spain")
        h = f.hit(a, "Ortega, Marta", ["1968"], ["Spain"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH", rid)

    def test_25_a_hit_whose_alert_is_missing_goes_to_review(self):
        f = Folder()
        f.customer("Lars Holm", "1977-12-13")
        f.tables["hits"].append({"hit_id": "H-00FFFF", "alert_id": "A-00FFFF", "entity_type": "Individual",
                                 "name": "Holm, Lars", "dobs": ["1951"], "countries": ["Germany"]})
        self.check(f.run()["H-00FFFF"], "REVIEW", "INSUFFICIENT_DATA", None)

    def test_26_a_failed_check_in_a_note_is_not_evidence(self):
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", verified=None)
        f.note(rid, "The provider rejected the passport of GRETA HOLM, born 1940-01-01, issued in Germany, on 2024-03-01.",
               channel="kyc", created_at="2024-03-01")
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH", rid)


if __name__ == "__main__":
    unittest.main()
