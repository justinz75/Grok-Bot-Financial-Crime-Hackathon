"""Numeric dates whose day and month could be either way round.

04/03/1980 is 4 March day first and 3 April month first. The rules read numeric dates day
first, and agreement, display and record search still use that reading. A date written the
other way round must never clear a hit, so a contradiction, and a date surely before
another, must hold under both readings. Every name and record is invented.
Run:  python -m unittest discover -s system/tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screening import dates as D  # noqa: E402
from test_pipeline import Folder  # noqa: E402


def d(text):
    return D.parse_date(text)


class Reading(unittest.TestCase):
    def test_both_readings_possible(self):
        got = d("04/03/1980")
        self.assertEqual(got, (1980, 3, 4))                       # day first, as before
        self.assertEqual(D.readings(got), ((1980, 3, 4), (1980, 4, 3)))
        self.assertEqual(D.show(got), "1980-03-04")
        self.assertEqual(D.readings(d("04-03-1980")), ((1980, 3, 4), (1980, 4, 3)))

    def test_only_one_reading_possible(self):
        for text, want in (("19/05/2004", (2004, 5, 19)), ("05/19/2004", (2004, 5, 19)),
                           ("05/05/1980", (1980, 5, 5)), ("1980-04-03", (1980, 4, 3))):
            got = d(text)
            self.assertEqual(D.readings(got), (want,), text)
            self.assertEqual(D.show(got), D.show(D.make(*want)), text)

    def test_inside_a_sentence(self):
        found = [x for x, _, _ in D.find_dates("Passport checked, born 04/03/1980.")]
        self.assertEqual([D.readings(x) for x in found], [((1980, 3, 4), (1980, 4, 3))])

    def test_kept_beside_the_plain_date_it_equals(self):
        self.assertEqual(len(D.parse_dates("1980-03-04; 04/03/1980")), 2)
        self.assertEqual(len(D.parse_dates("04/03/1980; 04/03/1980")), 1)


class Comparing(unittest.TestCase):
    def test_contradicted_only_when_both_readings_are(self):
        hit = D.parse_dates("04/03/1980")
        self.assertEqual(D.compare(d("1980-04-03"), hit), "unknown")   # the month-first reading agrees
        self.assertEqual(D.compare(d("1980-07-09"), hit), "mismatch")  # neither reading is July
        self.assertEqual(D.compare(d("1975-04-03"), hit), "mismatch")  # years apart

    def test_agreement_uses_the_day_first_reading_as_before(self):
        hit = D.parse_dates("04/03/1980")
        self.assertEqual(D.compare(d("1980-03-04"), hit), "agree")
        self.assertEqual(D.compare(d("1980"), hit), "agree")
        self.assertEqual(D.compare(d("04/03/1980"), [d("04/03/1980")]), "agree")

    def test_either_side_can_be_ambiguous(self):
        self.assertEqual(D.compare(d("04/03/1980"), D.parse_dates("1980-04-03")), "unknown")
        self.assertEqual(D.compare(d("04/03/1980"), D.parse_dates("1980-07")), "mismatch")

    def test_surely_before_whichever_way_round(self):
        self.assertFalse(D.surely_before(d("04/03/2020"), d("2020-03-20")))  # 3 April is after
        self.assertTrue(D.surely_before(d("04/03/2020"), d("2020-05-01")))
        self.assertFalse(D.surely_before(d("2020-03-20"), d("04/03/2020")))  # 4 March is before

    def test_max_age_takes_the_older_reading(self):
        # born 3 April or 4 March 1980; on 20 March 2000 they were 19 or 20
        self.assertEqual(D.max_age_on(d("04/03/1980"), d("2000-03-20")), 20)


class WholeRun(unittest.TestCase):
    def check(self, line, decision, code=None, record="unset"):
        self.assertEqual(line["decision"], decision, line["reason"])
        if code:
            self.assertEqual(line["reason_code"], code, line["reason"])
        if record != "unset":
            self.assertEqual(line["customer_record_id"], record, line["reason"])

    def linked(self, f, dob):
        rid = f.customer("Lars Holm", dob)
        return rid, f.alert("Lars Holm", account=f.field("accounts", "customer_id", rid, "account_id"))

    def test_hit_date_either_way_round_does_not_clear(self):
        f = Folder()
        rid, a = self.linked(f, "1980-04-03")
        h = f.hit(a, "Holm, Lars", ["04/03/1980"], ["Germany"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA", rid)

    def test_verified_date_either_way_round_does_not_clear(self):
        f = Folder()
        rid, a = self.linked(f, "04/03/1980")
        h = f.hit(a, "Holm, Lars", ["1980-04-03"], ["Germany"])
        self.check(f.run()[h], "REVIEW", "INSUFFICIENT_DATA", rid)

    def test_contradicted_both_ways_still_clears(self):
        f = Folder()
        rid, a = self.linked(f, "1980-04-03")
        h = f.hit(a, "Holm, Lars", ["04/09/1980"], ["Germany"])    # 4 September or 9 April
        self.check(f.run()[h], "DIFFERENT_ENTITY", "DOB_MISMATCH", rid)

    def test_day_first_agreement_still_confirms(self):
        f = Folder()
        rid, a = self.linked(f, "1980-03-04")
        h = f.hit(a, "Holm, Lars", ["04/03/1980"], ["Germany"])
        self.check(f.run()[h], "SAME_ENTITY", None, rid)

    def test_died_before_screening_whichever_way_round_still_clears(self):
        f = Folder()
        rid, a = self.linked(f, "1980-03-04")
        h = f.hit(a, "Holm, Lars", ["1980"], ["Germany"])
        f.tables["hits"][-1]["deceased_date"] = "04/03/2020"
        self.check(f.run()[h], "DIFFERENT_ENTITY", "DECEASED", rid)


if __name__ == "__main__":
    unittest.main()
