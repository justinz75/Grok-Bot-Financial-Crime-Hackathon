"""Wordings that must never clear a hit.

`tools/stress.py` takes text away and checks that reading less never clears a hit. These
tests do the opposite: they add text that can be misread. Capitals that are not the legal
name, a year that is not a birth date, a country written as a nationality. Each test
builds the smallest invented data folder that shows one wording, runs the whole system and
checks that the hit is not cleared. The controls check that a real check still clears.
Run:  python -m unittest discover -s system/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_pipeline import Folder  # noqa: E402

CLEARED = "DIFFERENT_ENTITY"


class Wording(unittest.TestCase):
    def person(self, f, verified="same", dob="1977-12-13", country="Germany"):
        """Lars Holm, with an approved check on file unless verified is None."""
        rid = f.customer("Lars Holm", dob, country, verified=verified)
        alert = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        return rid, alert

    def check(self, line, decision, code=None):
        self.assertEqual(line["decision"], decision, line["reason"])
        if code:
            self.assertEqual(line["reason_code"], code, line["reason"])


class CapitalsThatAreNotTheLegalName(Wording):
    def test_capitals_in_a_support_note(self):
        f = Folder()
        rid, a = self.person(f)
        f.note(rid, "Customer rang about an ATM PIN reset. Identity confirmed over the phone.")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        line = f.run()[h]
        self.check(line, "SAME_ENTITY", "NAME_DOB_MATCH")
        self.assertNotIn("ATM PIN", line["reason"])

    def test_field_labels_in_capitals(self):
        f = Folder()
        rid, a = self.person(f, verified=None)
        f.note(rid, "FULL NAME: LARS HOLM. DATE OF BIRTH: 13 December 1977. Document: German passport. Result: approved.",
               channel="kyc")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_a_status_in_capitals(self):
        f = Folder()
        rid, a = self.person(f, verified=None)
        f.note(rid, "CHECK PASSED for LARS HOLM, born 13 December 1977, German passport.", channel="kyc")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_a_name_the_bank_does_not_hold_supports_but_never_clears(self):
        f = Folder()
        rid, a = self.person(f, verified=None)
        f.note(rid, "The provider verified the passport of MARTA ORTEGA, born 1977-12-13, issued in Germany, on 2024-03-01.",
               channel="kyc", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.assertNotEqual(f.run()[h]["decision"], CLEARED)

    def test_control_a_legal_name_the_bank_holds_still_clears(self):
        f = Folder()
        rid, a = self.person(f, verified=None)
        note = f.note(rid, "The provider verified the passport of GRETA HOLM, born 1977-12-13, issued in Germany, on 2024-03-01.",
                      channel="kyc", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        line = f.run()[h]
        self.check(line, CLEARED, "NAME_MISMATCH_VERIFIED")
        self.assertEqual(line["evidence"], [note])

    def test_control_a_check_filed_under_another_channel_still_clears(self):
        f = Folder()
        rid, a = self.person(f, verified=None, dob="1990-01-01")
        f.note(rid, "The provider verified the passport of LARS HOLM, born 1977-12-13, issued in Germany, on 2024-03-01.",
               channel="onboarding", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", ["1951"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")


class YearsThatAreNotBirthDates(Wording):
    # In the two support-note cases the hit is the customer. The later note is not
    # believed and the real check keeps its place, so the answer is the one the real
    # check gives.
    def test_a_year_beside_birth_words_in_a_support_note(self):
        f = Folder()
        rid, a = self.person(f)
        f.note(rid, "Customer asked us to confirm the date of birth we hold for him. Account open since 2019.")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        line = f.run()[h]
        self.check(line, "SAME_ENTITY", "NAME_DOB_MATCH")
        self.assertNotIn("2019", line["reason"])

    def test_a_year_beside_capitals_in_a_support_note(self):
        f = Folder()
        rid, a = self.person(f)
        f.note(rid, "Passport re-verified by phone. Customer since 2019. NEW CARD issued.")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        line = f.run()[h]
        self.assertNotEqual(line["decision"], CLEARED, line["reason"])
        self.assertNotIn("NEW CARD", line["reason"])

    def test_a_later_support_note_does_not_hide_a_date_of_birth_that_agrees(self):
        # Found on real data by tools/stress.py. The real check's date agrees with the hit,
        # so a country difference must not clear it. Hidden behind the note, it did.
        f = Folder()
        rid, a = self.person(f, dob="1999-05-10", country="Nigeria")
        f.note(rid, "Card delivery address updated. Date of birth on file confirmed; customer since 2019.")
        h = f.hit(a, "Holm, Lars", ["1999"], ["United Kingdom"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn("1999-05-10", line["reason"])

    def test_a_later_support_note_does_not_hide_a_verified_name(self):
        # The same displacement turned a clearance into a match: the real check's legal
        # name was hidden, and the name on the record then agreed with the hit.
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", verified=("GRETA HOLM", "1977-12-13", "Germany"))
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        f.note(rid, "Card delivery address updated. Date of birth on file confirmed; customer since 2019.")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], CLEARED, "NAME_MISMATCH_VERIFIED")

    def test_a_doubtful_note_in_the_check_channel_keeps_its_place(self):
        # A newer identity check read with doubt is still the newer check. The older
        # check's legal name must not clear what the newer one may deny.
        f = Folder()
        rid = f.customer("Lars Holm", "1977-12-13", verified=("GRETA HOLM", "1977-12-13", "Germany"))
        a = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))
        f.note(rid, "The provider verified the passport of MARTA ORTEGA, born 1977-12-13, issued in Germany, on 2024-03-01.",
               channel="kyc", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", [], ["Germany"])
        self.assertNotEqual(f.run()[h]["decision"], CLEARED)

    def test_a_document_date_in_a_check_is_not_a_birth_date(self):
        f = Folder()
        rid, a = self.person(f, verified=None, dob="1977-12-13")
        f.note(rid, "The provider verified the passport of LARS HOLM, issued in Germany on 2019-05-01.",
               channel="kyc", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.assertNotEqual(f.run()[h]["decision"], CLEARED)

    def test_control_a_company_incorporated_shortly_before_its_check_still_clears(self):
        f = Folder()
        rid = f.customer("Marisol SA", "2001-01-01", "Spain", kind="Company", verified=None)
        f.note(rid, "Registry extract checked for MARISOL SA, incorporated 2021-05-05, Spain.",
               channel="kyc", created_at="2024-03-01")
        a = f.alert("Marisol SA", account=f.field("accounts", "customer_id", rid, "account_id"), kind="Company")
        h = f.hit(a, "Marisol SA", [], ["Spain"], kind="Company",
                  notes="According to news.test; March 3, 2015: The company was fined.")
        self.check(f.run()[h], CLEARED, "TEMPORAL_IMPOSSIBILITY")


class CountriesANoteOnlyMentions(Wording):
    def test_a_support_note_that_reads_like_a_failed_check(self):
        f = Folder()
        rid, a = self.person(f)
        note = f.note(rid, "Customer lived in Nigeria until 2019. Could not finish the identity verification by SMS OTP.")
        h = f.hit(a, "Holm, Lars", [], ["Nigeria"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn(note, line["evidence"])
        self.assertIn("Nigeria", line["reason"])

    def test_a_nationality_word_in_a_support_note(self):
        f = Folder()
        rid, a = self.person(f)
        note = f.note(rid, "Customer says he is a Nigerian national and moved to Berlin for work.")
        h = f.hit(a, "Holm, Lars", [], ["Nigeria"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn(note, line["evidence"])

    def test_a_mention_does_not_turn_a_review_into_a_match(self):
        # name and date of birth agree and the countries differ: a review before, a review now
        f = Folder()
        rid, a = self.person(f)
        f.note(rid, "Customer says he is a Nigerian national and moved to Berlin for work.")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Nigeria"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_control_a_nationality_of_some_other_country_does_not_block(self):
        f = Folder()
        rid, a = self.person(f)
        f.note(rid, "Customer says he is a Nigerian national and moved to Berlin for work.")
        h = f.hit(a, "Holm, Lars", [], ["Brazil"])
        self.check(f.run()[h], CLEARED, "LOCATION_MISMATCH")

    def test_a_mention_blocks_a_company_clearance_and_does_not_confirm_it(self):
        f = Folder()
        rid = f.customer("Marisol SA", "2001-01-01", "Spain", kind="Company")
        f.note(rid, "The client asked about paying a Brazilian supplier.")
        a = f.alert("Marisol SA", account=f.field("accounts", "customer_id", rid, "account_id"), kind="Company")
        h = f.hit(a, "Marisol SA", [], ["Brazil"], kind="Company")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")


if __name__ == "__main__":
    unittest.main()
