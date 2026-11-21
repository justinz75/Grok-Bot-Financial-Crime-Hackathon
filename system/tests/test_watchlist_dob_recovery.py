import unittest
from types import SimpleNamespace

from test_pipeline import Folder
from screening.watchlist import build_hit


class WatchlistDobRecovery(unittest.TestCase):
    def setUp(self):
        self.folder = Folder()
        self.name = "Mira Q Selwick"
        self.dob = "1982-06-14"
        self.customer = self.folder.customer(self.name, self.dob)
        account = self.folder.field("accounts", "customer_id", self.customer, "account_id")
        self.alert = self.folder.alert(self.name, account=account)

    def test_later_normalized_search_key_recovers_dob(self):
        hit = self.folder.hit(self.alert, self.name, countries=("Germany",))
        namesake = self.folder.search(
            "mira selwick",
            "Mira Selwick, a politically exposed person in Canada, was born in 1960.",
        )
        wrong_listing = self.folder.search(
            "mira q selwick",
            "Mira Q Selwick, a sanctioned individual in Germany, was born in 1970.",
        )
        source = self.folder.search(
            "mira q selwick",
            "Mira Q Selwick, a politically exposed person in Germany, was born on 14 June 1982.",
        )
        line = self.folder.run()[hit]
        self.assertEqual(line["decision"], "SAME_ENTITY", line["reason"])
        self.assertEqual(line["customer_record_id"], self.customer)
        self.assertIn(source, line["evidence"])
        self.assertNotIn(namesake, line["evidence"])
        self.assertNotIn(wrong_listing, line["evidence"])

    def test_search_gathers_all_keys_and_deduplicates_by_result_id(self):
        self.folder.hit(self.alert, self.name, countries=("Germany",))
        row = self.folder.tables["hits"][0]
        first = {"result_id": "SR-1", "snippet": "A politically exposed person in Germany, born in 1982."}
        second = {
            "result_id": "SR-2", "snippet": "A politically exposed person in Germany, born on 14 June 1982.",
        }
        store = SimpleNamespace(search_by_query={"mira selwick": [first], "mira q selwick": [first, second]})
        hit = build_hit(row, store)
        self.assertEqual(hit.dob_evidence, ["SR-1", "SR-2"])
        self.assertEqual(hit.dobs, [(1982, None, None), (1982, 6, 14)])

    def test_wrapped_opening_paragraph_recovers_explicit_dob(self):
        hit = self.folder.hit(
            self.alert, self.name, countries=("Germany",),
            notes="Mira Q Selwick joined the commission in 2013.\nDate of birth: 14 June\n1982.",
        )
        lower_priority = self.folder.search(
            "mira selwick", "A politically exposed person in Germany, born in 1970.",
        )
        line = self.folder.run()[hit]
        self.assertEqual(line["decision"], "SAME_ENTITY", line["reason"])
        self.assertIn(self.dob, line["reason"])
        self.assertIn(hit + "#profile_notes", line["evidence"])
        self.assertNotIn(lower_priority, line["evidence"])

    def test_birthplace_and_inline_profile_dates_keep_search_precedence(self):
        for notes in (
            "Mira Q Selwick was born in Oslo on 14 June 1982.",
            "Mira Q Selwick was born in Oslo in 1982.",
            "Name: Mira Q Selwick; DOB: 14 June 1982.",
        ):
            self.folder.hit(self.alert, self.name, countries=("Germany",), notes=notes)
            self.folder.hit(self.alert, self.name, countries=("Canada",), notes=notes.replace("1982", "1962"))
        lower_priority = [
            self.folder.search("mira selwick", "A politically exposed person in Germany, born in 1962."),
            self.folder.search("mira selwick", "A politically exposed person in Canada, born in 1982."),
        ]
        for row, line in zip(self.folder.tables["hits"], self.folder.run().values()):
            with self.subTest(notes=row["profile_notes"]):
                expected = "NAME_DOB_MATCH" if "1982" in row["profile_notes"] else "DOB_MISMATCH"
                self.assertEqual(line["reason_code"], expected, line["reason"])
                self.assertTrue(set(lower_priority).isdisjoint(line["evidence"]))

    def test_wrapped_profile_clearance_cites_supporting_baseline_search(self):
        hit = self.folder.hit(
            self.alert, self.name, countries=("Germany",),
            notes="Mira Q Selwick served on the commission.\nDate of birth: 6 March 1962.",
        )
        source = self.folder.search("mira selwick", "A politically exposed person in Germany, born in 1963.")
        line = self.folder.run()[hit]
        self.assertEqual(line["reason_code"], "DOB_MISMATCH", line["reason"])
        self.assertIn(hit + "#profile_notes", line["evidence"])
        self.assertIn(source, line["evidence"])
        self.assertIn("1963", line["reason"])
        self.assertIn(source, line["reason"])

    def test_one_search_key_can_supply_year_and_full_birth_date(self):
        hit = self.folder.hit(self.alert, self.name, countries=("Germany",))
        year = self.folder.search(
            "mira selwick", "A politically exposed person in Germany, born in 1982.",
        )
        full = self.folder.search(
            "mira selwick", "A politically exposed person in Germany, born on 14 June 1982.",
        )
        line = self.folder.run()[hit]
        self.assertEqual(line["decision"], "SAME_ENTITY", line["reason"])
        self.assertTrue({year, full}.issubset(line["evidence"]))

    def test_report_and_unrelated_dates_do_not_supply_a_profile_dob(self):
        hit = self.folder.hit(self.alert, self.name, countries=("Germany",))
        row = self.folder.tables["hits"][0]
        for notes in (
            "Mira Q Selwick was born in Germany and appointed in 2013.",
            "Mira Q Selwick served on the commission.\n"
            "According to example.test; March 10, 2020: A witness was born in 1982.",
            "Mira Q Selwick served on the commission.\n\nDate of birth: 14 June 1982.",
            "Mira Q Selwick was 42 years old.\nThe commission began operations in 2024.",
        ):
            with self.subTest(notes=notes):
                row["profile_notes"] = notes
                line = self.folder.run()[hit]
                self.assertEqual(line["decision"], "REVIEW", line["reason"])
                self.assertNotIn(hit + "#profile_notes", line["evidence"])

    def test_listed_dob_takes_precedence_over_wrapped_profile(self):
        hit = self.folder.hit(
            self.alert, self.name, dobs=(self.dob,), countries=("Germany",),
            notes="Mira Q Selwick served on the commission.\nDate of birth: 6 March 1962.",
        )
        line = self.folder.run()[hit]
        self.assertEqual(line["decision"], "SAME_ENTITY", line["reason"])
        self.assertNotIn(hit + "#profile_notes", line["evidence"])

    def test_company_incorporation_date_comes_only_from_listed_field(self):
        folder = Folder()
        name = "Selwick Beacon GmbH"
        customer = folder.customer(name, "2002-08-24", kind="Company")
        account = folder.field("accounts", "customer_id", customer, "account_id")
        alert = folder.alert(name, account=account, kind="Company")
        hit = folder.hit(
            alert, name, countries=("Germany",), kind="Company",
            notes="Listed company.\nDate of birth: 6 March 1962.",
        )
        line = folder.run()[hit]
        self.assertEqual(line["decision"], "SAME_ENTITY", line["reason"])
        self.assertEqual(line["reason_code"], "NAME_LOCATION_MATCH")
        self.assertNotIn(hit + "#profile_notes", line["evidence"])

    def test_recovered_conflicting_dob_does_not_clear_a_review(self):
        profile_hit = self.folder.hit(
            self.alert, self.name, countries=("Germany",),
            notes="Mira Q Selwick served on the commission.\nDate of birth: 6 March 1962.",
        )
        search_hit = self.folder.hit(self.alert, self.name, countries=("Germany",))
        self.folder.search("mira selwick", "A politically exposed person in Canada, born in 1982.")
        self.folder.search("mira q selwick", "A politically exposed person in Germany, born in 1962.")
        lines = self.folder.run()
        for hit in (profile_hit, search_hit):
            self.assertEqual(lines[hit]["decision"], "REVIEW", lines[hit]["reason"])

    def test_new_profile_dob_cannot_remove_the_location_exception(self):
        hit = self.folder.hit(
            self.alert, self.name, countries=("Canada",),
            notes="Mira Q Selwick served on the commission.\nDate of birth: 6 March 1962.",
        )
        source = self.folder.search("mira selwick", "A politically exposed person in Canada, born in 1982.")
        line = self.folder.run()[hit]
        self.assertEqual(line["decision"], "REVIEW", line["reason"])
        self.assertIn(hit + "#profile_notes", line["evidence"])
        self.assertIn(source, line["evidence"])
        self.assertIn(source, line["reason"])
