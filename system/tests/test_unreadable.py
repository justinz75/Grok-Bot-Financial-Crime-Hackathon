"""Values that cannot be read must never clear a hit.

`test_wording.py` adds text that can be misread. These tests hand the system a value it
cannot read at all, or a date that no record backs: one of a hit's listed dates, the
date of birth on an approved check, an approved check that reads like a failed one, a
date of birth that only the alert gives. Unknown stays unknown, so none of them may
clear a hit. The controls check that what can be read still decides.
Run:  python -m unittest discover -s system/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screening import dates as D  # noqa: E402
from screening import layers  # noqa: E402
from screening.decide import COMPANY, PERSON, Customer, Hit, combine, decide, states  # noqa: E402
from screening.layers import briefing  # noqa: E402
from screening.names import NameRules  # noqa: E402
from test_pipeline import Folder  # noqa: E402

CLEARED = "DIFFERENT_ENTITY"
UNREADABLE = "02-Mar-85"  # a date as a person reads it and the date rules do not


class Unreadable(unittest.TestCase):
    def person(self, f, dob="1985-03-02", verified="same", screened_dob=None):
        """Lars Holm in Germany, with an approved check on file unless verified is None."""
        rid = f.customer("Lars Holm", dob, "Germany", verified=verified)
        alert = f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"), dob=screened_dob)
        return rid, alert

    def check(self, line, decision, code=None):
        self.assertEqual(line["decision"], decision, line["reason"])
        if code:
            self.assertEqual(line["reason_code"], code, line["reason"])


class AListedDateThatCannotBeRead(Unreadable):
    def test_the_dates_that_can_be_read_do_not_clear(self):
        # the unread date may be the one that agrees, so the others cannot contradict alone
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["1950", "abt. 1985"], ["Germany"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn("abt. 1985", line["reason"])

    def test_a_listed_date_that_agrees_still_confirms(self):
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["abt. 1950", "1985"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_a_date_found_elsewhere_does_not_clear_either(self):
        # the field gives a date that cannot be read, so a search result may not stand in for it
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["abt. 1985"], ["Germany"], category="Enforcement")
        f.search("holm lars", "Lars Holm, 61, the subject of enforcement action in Germany, was named in May 2024.")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_a_country_difference_does_not_clear_either(self):
        # a country difference does not clear a hit whose name and date of birth agree,
        # and the unread date may be the one that agrees
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["1950", "abt. 1985"], ["Peru"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn("abt. 1985", line["reason"])

    def test_control_a_country_difference_still_clears_a_customer_with_no_date(self):
        # with no date of birth for the customer there is nothing the unread date could agree with
        f = Folder()
        rid, a = self.person(f, dob=None, verified=None)
        h = f.hit(a, "Holm, Lars", ["abt. 1985"], ["Peru"])
        self.check(f.run()[h], CLEARED, "LOCATION_MISMATCH")

    def test_another_ground_still_clears(self):
        f = Folder()
        rid, a = self.person(f, verified=("GRETA HOLM", "1985-03-02", "Germany"))
        h = f.hit(a, "Holm, Lars", ["1950", "abt. 1985"], ["Germany"])
        self.check(f.run()[h], CLEARED, "NAME_MISMATCH_VERIFIED")

    def test_control_listed_dates_that_are_all_read_still_clear(self):
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["1950", "1951"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")

    def test_control_a_year_from_another_calendar_blocks_nothing(self):
        # 1340 cannot agree with any date the bank holds, so it takes no part, as before
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["1340", "1961"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")

    def test_a_one_part_name_that_agrees_is_held_back_the_same_way(self):
        f = Folder()
        rid = f.customer("Unknown Farooq", "1968-08-20", "Pakistan", verified=("UNKNOWN FAROOQ", "1968-08-20", "Pakistan"))
        a = f.alert("UNKNOWN FAROOQ", account=f.field("accounts", "customer_id", rid, "account_id"))
        h = f.hit(a, "Muhammad Farooq", ["1950", "abt. 1968"], ["Peru"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_unread_dates_lists_what_may_still_agree(self):
        listed = ["1950", "abt. 1985", "", None, 1977, "1985-00-00", "03/05/61", "1340", "1402-03-21", "unknown"]
        self.assertEqual(D.unread_dates(listed), ["abt. 1985", "1985-00-00", "03/05/61"])
        self.assertEqual(D.unread_dates("1996; 1997"), [])
        self.assertEqual(D.unread_dates("1996; born about 1997"), ["born about 1997"])
        self.assertEqual(D.unread_dates("1996; sometime in the sixties"), [])
        self.assertEqual(D.unread_dates(None), [])
        self.assertEqual(D.unread_dates([]), [])
        self.assertEqual([D.show(d) for d in D.parse_dates(["1950", "abt. 1985"])], ["1950"])


class AVerifiedDateThatCannotBeRead(Unreadable):
    def test_the_declared_date_does_not_clear(self):
        # verified beats declared: the verified date exists and may be the one that agrees
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", UNREADABLE, "Germany"))
        h = f.hit(a, "Holm, Lars", ["1985"], ["Germany"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_the_declared_date_does_not_clear_on_age_either(self):
        f = Folder()
        rid, a = self.person(f, dob="2010-01-01", verified=("LARS HOLM", UNREADABLE, "Germany"))
        h = f.hit(a, "Holm, Lars", [], ["Germany"], notes="According to news.test; June 9, 2020: He was charged with fraud.")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_the_declared_date_may_still_agree(self):
        f = Folder()
        rid, a = self.person(f, dob="1985-03-02", verified=("LARS HOLM", UNREADABLE, "Germany"))
        h = f.hit(a, "Holm, Lars", ["1985"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_a_country_difference_does_not_clear_either(self):
        # the verified date may agree with the hit's, and a country difference does not
        # clear a hit whose name and date of birth agree
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", UNREADABLE, "Germany"))
        h = f.hit(a, "Holm, Lars", ["1985"], ["Peru"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn("could not be read with confidence", line["reason"])

    def test_control_a_country_difference_still_clears_a_hit_that_gives_no_date(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", UNREADABLE, "Germany"))
        h = f.hit(a, "Holm, Lars", [], ["Peru"])
        self.check(f.run()[h], CLEARED, "LOCATION_MISMATCH")

    def test_control_a_verified_date_that_is_read_still_clears(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", "1985-03-02", "Germany"))
        h = f.hit(a, "Holm, Lars", ["1950"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")

    def test_control_a_later_check_that_is_read_still_clears(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", UNREADABLE, "Germany"))
        applicant = f.field("onboarding", "customer_id", rid, "kyc_applicant_id")
        later = f.check(applicant, "LARS HOLM", "1985-03-02", "Germany", checked_at="2025-02-02")
        h = f.hit(a, "Holm, Lars", ["1950"], ["Germany"])
        line = f.run()[h]
        self.check(line, CLEARED, "DOB_MISMATCH")
        self.assertEqual(line["evidence"], [later])

    def test_control_a_rejected_check_is_not_evidence_whatever_its_date(self):
        f = Folder()
        rid, a = self.person(f, dob="1985-03-02", verified=None)
        applicant = f.field("onboarding", "customer_id", rid, "kyc_applicant_id")
        f.check(applicant, "LARS HOLM", UNREADABLE, "Germany", result="rejected")
        h = f.hit(a, "Holm, Lars", ["1950"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")


class AnApprovedCheckThatReadsAsFailed(Unreadable):
    PASSED = "Identity check passed on the passport of LARS HOLM, born 2 March 1985, issued in Germany."

    def test_control_the_check_as_written_decides(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=None)
        f.note(rid, self.PASSED, channel="kyc")
        h = f.hit(a, "Holm, Lars", ["1985"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_an_expiry_date_does_not_let_the_declared_date_clear(self):
        # "expires" reads as a failed check. The check passed and its date agrees with the hit.
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=None)
        f.note(rid, self.PASSED + " The document expires in 2031.", channel="kyc")
        h = f.hit(a, "Holm, Lars", ["1985"], ["Germany"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_nothing_found_wrong_does_not_let_the_declared_date_clear(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=None)
        f.note(rid, self.PASSED + " No mismatch was found.", channel="kyc")
        h = f.hit(a, "Holm, Lars", ["1985"], ["Germany"])
        self.assertNotEqual(f.run()[h]["decision"], CLEARED)

    def test_its_country_blocks_a_location_clearance_and_does_not_confirm(self):
        f = Folder()
        rid, a = self.person(f, verified=None)
        note = f.note(rid, "Identity check passed on the Nigerian passport of LARS HOLM, born 2 March 1985. "
                           "The document expires in 2031.", channel="kyc")
        h = f.hit(a, "Holm, Lars", [], ["Nigeria"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertIn(note, line["evidence"])

    def test_a_rejected_check_is_still_not_evidence_for_a_match(self):
        # what it says is ignored, as before: the declared date agrees with the hit
        f = Folder()
        rid, a = self.person(f, dob="1977-12-13", verified=None)
        f.note(rid, "The provider rejected the passport of GRETA HOLM, born 1940-01-01, issued in Germany, on 2024-03-01.",
               channel="kyc", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", ["1977"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", "NAME_DOB_MATCH")

    def test_what_the_caution_costs_a_truly_rejected_check_sends_the_declared_date_to_review(self):
        # the rules cannot tell this note from the two above, so the declared date may agree and not clear
        f = Folder()
        rid, a = self.person(f, dob="1977-12-13", verified=None)
        f.note(rid, "The provider rejected the passport of LARS HOLM, born 1977-12-13, issued in Germany, on 2024-03-01.",
               channel="kyc", created_at="2024-03-01")
        h = f.hit(a, "Holm, Lars", ["1951"], ["Germany"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_control_a_real_check_beside_it_still_clears(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", "1985-03-02", "Germany"))
        f.note(rid, "The provider rejected the passport of LARS HOLM, born 1985-03-02, issued in Germany, on 2023-03-01.",
               channel="kyc", created_at="2023-03-01")
        h = f.hit(a, "Holm, Lars", ["1950"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")

    def test_a_country_difference_does_not_clear_either(self):
        # the check's own date agrees with the hit, so the policy's answer here is a review
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=None)
        f.note(rid, self.PASSED + " The document expires in 2031.", channel="kyc")
        h = f.hit(a, "Holm, Lars", ["1985"], ["Peru"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_control_a_country_difference_still_clears_a_hit_that_gives_no_date(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=None)
        f.note(rid, self.PASSED + " The document expires in 2031.", channel="kyc")
        h = f.hit(a, "Holm, Lars", [], ["Peru"])
        self.check(f.run()[h], CLEARED, "LOCATION_MISMATCH")

    def test_control_a_support_note_that_reads_like_a_failed_check_changes_nothing(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=None)
        f.note(rid, "Customer could not log in after the app update. Password reset declined twice.")
        h = f.hit(a, "Holm, Lars", ["1985"], ["Germany"])
        self.check(f.run()[h], CLEARED, "DOB_MISMATCH")


class ADateOnlyTheAlertGives(Unreadable):
    def test_the_screened_date_does_not_clear(self):
        f = Folder()
        rid, a = self.person(f, dob=None, verified=None, screened_dob="1990-05-05")
        h = f.hit(a, "Holm, Lars", ["1950"], ["Germany"])
        line = f.run()[h]
        self.check(line, "REVIEW", "INSUFFICIENT_DATA")
        self.assertEqual(line["customer_record_id"], rid)
        self.assertEqual(line["evidence"], [rid])

    def test_the_screened_date_does_not_clear_on_age_either(self):
        f = Folder()
        rid, a = self.person(f, dob=None, verified=None, screened_dob="2010-05-05")
        h = f.hit(a, "Holm, Lars", [], ["Germany"], notes="According to news.test; June 9, 2020: He was charged with fraud.")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_control_a_country_difference_still_clears(self):
        # no check is hiding another date, so the countries decide as they always did
        f = Folder()
        rid, a = self.person(f, dob=None, verified=None, screened_dob="1990-05-05")
        h = f.hit(a, "Holm, Lars", ["1950"], ["Peru"])
        line = f.run()[h]
        self.check(line, CLEARED, "LOCATION_MISMATCH")
        self.assertEqual(line["evidence"], [rid])

    def test_control_a_date_on_the_record_still_clears_and_is_cited(self):
        f = Folder()
        rid, a = self.person(f, dob="1990-05-05", verified=None, screened_dob="1990-05-05")
        h = f.hit(a, "Holm, Lars", ["1950"], ["Germany"])
        line = f.run()[h]
        self.check(line, CLEARED, "DOB_MISMATCH")
        self.assertEqual(line["evidence"], [rid])


class TheBriefingSaysWhy(unittest.TestCase):
    """The explain file must name the real reason a contradicting date did not clear."""
    class Store(object):
        rules = NameRules([["tony", "anthony"]], ["ltd"])

    RULES = Store.rules
    LAYER = briefing.build(Store(), "on")

    def brief(self, customer, hit):
        outcome = decide(customer, hit, self.RULES)
        case = layers.Case(self.Store(), {}, {}, customer, hit, outcome, states(customer, hit, self.RULES), {})
        return self.LAYER.annotate(case), outcome

    def customer(self, **kw):
        return Customer(PERSON, ["CUS-000001"], names=[("Lars Holm", "CUS-000001")], dob=D.parse_date("1985-03-02"),
                        countries={"DE": ["CUS-000001"]}, screened_at=D.parse_date("2026-11-06"), **kw)

    def test_an_unread_listed_date_is_named(self):
        hit = Hit("H-0000A1", PERSON, "Holm, Lars", dobs=D.parse_dates(["1950"]), dob_origin="listed",
                  countries=["DE"], unread_dobs=["abt. 1985"])
        note, outcome = self.brief(self.customer(dob_source="KYC-0000A1", verified_name="LARS HOLM", verified_source="KYC-0000A1"), hit)
        self.assertEqual(outcome.decision, "REVIEW")
        self.assertIn("could not be read", note["headline"])
        self.assertNotIn("could not be verified", note["headline"])
        self.assertIn('The hit date "abt. 1985" could not be read.', note["missing"])
        self.assertTrue(any("abt. 1985" in line for line in note["would_settle"]), note["would_settle"])
        self.assertFalse(any("identity check" in line for line in note["would_settle"]), note["would_settle"])

    def test_a_date_only_the_alert_gives_is_named(self):
        hit = Hit("H-0000A1", PERSON, "Holm, Lars", dobs=D.parse_dates(["1950"]), dob_origin="listed", countries=["DE"])
        note, outcome = self.brief(self.customer(dob_source=None, dob_can_clear=False), hit)
        self.assertEqual(outcome.decision, "REVIEW")
        self.assertTrue(any("only the alert gives" in line for line in note["missing"]), note["missing"])
        self.assertFalse(any("could not be read with confidence" in line for line in note["missing"]), note["missing"])

    def test_a_company_hit_with_an_unread_date_is_not_cleared_on_it(self):
        company = Customer(COMPANY, ["CUS-000002"], names=[("Marisol SA", "CUS-000002")], dob=D.parse_date("2001-01-01"),
                           dob_source="CUS-000002", countries={"ES": ["CUS-000002"]}, screened_at=D.parse_date("2026-11-06"))
        hit = Hit("H-0000A2", COMPANY, "Marisol SA", dobs=D.parse_dates(["1950"]), dob_origin="listed",
                  countries=["ES"], unread_dobs=["est. 2001"])
        outcome = decide(company, hit, self.RULES)
        self.assertNotEqual(outcome.decision, CLEARED)
        self.assertNotIn("DOB_MISMATCH", outcome.codes)


class ReadingGapIntegration(Unreadable):
    def test_unread_date_blocks_wrapped_profile_and_baseline_search_clearance(self):
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", ["abt. 1985"], ["Germany"], category="Enforcement",
                  notes="Lars Holm served on a committee.\nDate of birth: 6 March 1962.")
        f.search("holm lars", "Lars Holm, the subject of enforcement action in Germany, was born in 1963.")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_recovered_date_never_gains_clearance_power(self):
        f = Folder()
        rid, a = self.person(f)
        h = f.hit(a, "Holm, Lars", [], ["Germany"],
                  notes="Lars Holm served on a committee.\nDate of birth: 6 March 1962.")
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")

    def test_unread_check_preserves_precautionary_country(self):
        f = Folder()
        rid, a = self.person(f, dob="1970-01-01", verified=("LARS HOLM", UNREADABLE, "Germany"))
        f.note(rid, "The customer visited Peru.")
        h = f.hit(a, "Holm, Lars", [], ["Peru"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA")


class CandidateReadingGapExplanation(unittest.TestCase):
    def test_ambiguous_review_preserves_unread_date_guard_reason(self):
        rules = NameRules()
        hit = Hit("H-0000A1", PERSON, "Lars Holm", dobs=D.parse_dates(["1950"]),
                  countries=["DE"], unread_dobs=["abt. 1985"])
        outcomes = []
        for record, country in [("CUS-000001", "DE"), ("CUS-000002", "PE")]:
            customer = Customer(PERSON, [record], names=[("Lars Holm", record)],
                                dob=D.parse_date("1985-03-02"), dob_source=record,
                                countries={country: [record]})
            outcomes.append(decide(customer, hit, rules))
        outcome = combine(outcomes)
        self.assertEqual(outcome.decision, "REVIEW")
        self.assertEqual(outcome.record_id, "AMBIGUOUS")
        self.assertEqual(outcome.evidence, ["CUS-000001", "CUS-000002"])
        self.assertIn("abt. 1985", outcome.reason)
        self.assertIn("could not be read", outcome.reason)


if __name__ == "__main__":
    unittest.main()
