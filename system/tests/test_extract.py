"""Tests for reading facts out of free text. Run:  python -m unittest discover -s system/tests

Every name and sentence here is invented; none comes from the hackathon data.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from screening import dates as D  # noqa: E402
from screening import extract as X  # noqa: E402


def years(found):
    return [d.year for d in found]


class DatedReports(unittest.TestCase):
    def test_only_the_exact_form_counts(self):
        notes = "\n".join([
            "According to daily-example.test; November 22, 2015: On November 01, 2015, Pablo Reyes Luna was arrested.",
            "",
            "De acuerdo con daily-example.test; Noviembre 02, 2015: En Noviembre 01, 2015, Pablo Reyes Luna fue arrestado.",
            "According to the Example Investigation Agency; June 2014: The act provided a surveillance mechanism.",
            "According to the Example Regulation Authority: On November 02, 2016, he received a written rebuke.",
            "According to courier-example.test; September 23, 2014: In September 2014, he was sent on trial.",
        ])
        self.assertEqual([D.show(d) for d in X.dated_reports(notes)], ["2014-09-23", "2015-11-22"])
        self.assertEqual(X.dated_reports(""), [])
        self.assertEqual(X.dated_reports(None), [])


class ProfileBirth(unittest.TestCase):
    def test_birth_sentences(self):
        cases = [
            ("Ibrahim Musa Garba was born in 1952.", [1952]),
            ("Kwame Mensah Boateng was born on 17 July 1939.", [1939]),
            ("Formal charges were brought against Marta Lopez Ortega, aged 30, in November 1998.", [1967, 1968]),
            ("November 1998 saw Marta Lopez Ortega, a 30-year-old, face charges.", [1967, 1968]),
            ("Investigators questioned Piotr Adam Nowak in January 2025, when he reached the age of 38.", [1986, 1987]),
            ("In January 2025, investigators questioned 38-year-old Piotr Adam Nowak.", [1986, 1987]),
            ("At the time Luca Marino faced charges in March 1999, he was 24.", [1974, 1975]),
            ("Henry P Dalton was 25 when taken into custody during February 1986.", [1960, 1961]),
            ("November 1981 marked the date Jordi Serra, then 37, was placed under charge.", [1943, 1944]),
            ("Jordi Serra reached 37 years of age by November 1981, the time he was charged.", [1943, 1944]),
            ("Owen T Fraser, at 24, was taken into custody in May 1999.", [1974, 1975]),
            ("Piotr Nowak, at age 31, had charges filed against him in December 2005.", [1973, 1974]),
            ("Questioned in April 2006, Viktor Sokolov was 42 years old.", [1963, 1964]),
            ("The age of Piotr Adam Nowak was 38 when he was questioned in January 2025.", [1986, 1987]),
            ("An indictment naming Erik Lund was issued in October 2004, when the subject was 48.", [1955, 1956]),
        ]
        for text, expected in cases:
            found, _ = X.profile_birth(text + "\n\nCareer:\nDirector, effective from May 11, 2016.")
            self.assertEqual(years(found), expected, text)
        found, kind = X.profile_birth("Kwame Mensah Boateng was born on 17 July 1939.")
        self.assertEqual((found, kind), ([(1939, 7, 17)], "explicit"))

    def test_provider_text_is_not_a_birth_sentence(self):
        for text in [
            "According to news-example.test; November 19, 2018: In November 2018, the agency arrested 11 human "
            "traffickers from various parts of the province. Karim Farooq was one among the arrestees.",
            "184\n22.11.2011\nKARIM FAROOQ HASSAN\nThe State Security Cabinet (SSC)",
            "Description:\nVice President of the Board of Directors of Example University, as of 2008.",
            "Career:\nChief Executive Officer, Example Ferries Inc. (December 10, 2011 - May 02, 2018);",
            "Name: Carter, Leon\nDIN: 00A0000\nDOB: 6/20/1955\nHeight: 5' 10\"",
            "On March 5, 2019, he was sentenced to 5 years in prison and fined 40 thousand.",
            "Liquidated on December 24, 2020.",
            "",
        ]:
            self.assertEqual(X.profile_birth(text), ([], None), text)


class SearchResults(unittest.TestCase):
    def test_listing_phrase(self):
        self.assertEqual(X.listing_phrase("PEP", ""), "politically exposed person")
        self.assertEqual(X.listing_phrase("", "Sanctions; Enforcement"), "sanctioned individual")
        self.assertEqual(X.listing_phrase(None, ["Adverse Media", "PEP"]), "named in adverse media")
        self.assertEqual(X.listing_phrase("SOE", "SOE; Other Segment"), "state owned enterprise official")
        self.assertEqual(X.listing_phrase("Registration", ""), "named on a watchlist")
        self.assertEqual(X.listing_phrase("", ""), "named on a watchlist")

    def test_keys(self):
        self.assertEqual(X.search_keys("Bakare, Tunde")[0], "bakare tunde")
        self.assertEqual(X.search_keys("Owen T Fraser")[0], "fraser owen")
        self.assertEqual(X.search_keys("Nowak, Piotr Michał")[0], "micha nowak piotr")
        self.assertEqual(X.search_keys("O'Connor, Michael")[0], "connor michael")
        self.assertEqual(X.search_keys("Jérôme Lefèvre")[0], "jerome lefevre")

    def test_only_results_about_the_hit_count(self):
        results = [
            ("SR-1", "A public report from May 1982 identified Tunde Bakare, 21, as a sanctioned individual located in Pakistan."),
            ("SR-2", "Tunde Bakare, 48, a university lecturer in Ghana, was quoted in a local news story per May 2015 files."),
            ("SR-3", "Tunde Bakare, 32, the subject of enforcement action in Ghana, appeared in a regulator's notice during January 2025."),
            ("SR-4", "A news outlet featured 53 year old Tunde Bakare, a politically exposed person in Mexico, in January 2000."),
        ]
        found, used = X.search_birth(results, "subject of enforcement action", {"GH"})
        self.assertEqual((years(found), used), ([1992, 1993], ["SR-3"]))
        found, used = X.search_birth(results, "politically exposed person", {"MX", "US"})
        self.assertEqual((years(found), used), ([1946, 1947], ["SR-4"]))
        self.assertEqual(X.search_birth(results, "named in adverse media", {"NG"}), ([], []))   # namesakes only
        self.assertEqual(X.search_birth(results, "sanctioned individual", {"GH"}), ([], []))    # wrong country
        found, used = X.search_birth(
            [("SR-5", "Ireland's Tunde Bakare, 22, was listed as a state-owned enterprise official in December 2024.")],
            "state owned enterprise official", {"IE"})
        self.assertEqual((years(found), used), ([2001, 2002], ["SR-5"]))


class IdentityNotes(unittest.TestCase):
    def read(self, text, created):
        got = X.read_identity_note(text, created)
        return (got["name"], D.show(got["dob"]), got["country"], got["approved"]) if got else None

    def test_wordings(self):
        cases = [
            ("Sumsub completed identity verification for LARS HOLM, born December 13, 1977, using a national ID issued in Germany on 2023-02-19.",
             "2023-02-19", ("LARS HOLM", "1977-12-13", "DE", True)),
            ("GRACE MILLER's identity was successfully verified by Onfido on 2024-07-27, confirming the details on her United States driving licence, including her 26/03/1992 date of birth.",
             "2024-07-27", ("GRACE MILLER", "1992-03-26", "US", True)),
            ("DOB 14 November 1969 confirmed for PAOLO RICCI via driving licence from Spain by Persona on 2025-02-28.",
             "2025-02-28", ("PAOLO RICCI", "1969-11-14", "ES", True)),
            ("On 2024-04-25, Persona verified ANNA SOFIA KELLER (DOB 22 December 1990) using driving licence from Germany.",
             "2024-04-25", ("ANNA SOFIA KELLER", "1990-12-22", "DE", True)),
            ("Verification of HAYES N/A was finalized via Onfido on 2024-11-09. This used a passport from United States and confirms a date of birth of 1974.",
             "2024-11-09", ("HAYES N/A", "1974", "US", True)),
            ("Sumsub confirmed the identity of AMARA OKEKE, born 1988-09-25, via a Nigerian passport on 2024-06-19.",
             "2024-06-19", ("AMARA OKEKE", "1988-09-25", "NG", True)),
            ("KYC check complete: Veriff processed national ID (Bangladesh) for RAFIQ KHAN, DOB 05/12/1992, on 2024-07-12.",
             "2024-07-12", ("RAFIQ KHAN", "1992-12-05", "BD", True)),
            ("JORDAN FRENCH was verified by Veriff on 2024-01-05 using a passport from Italy, born 1990-02-03.",
             "2024-01-05", ("JORDAN FRENCH", "1990-02-03", "IT", True)),
        ]
        for text, created, expected in cases:
            self.assertEqual(self.read(text, created), expected, text)

    def test_failed_check_is_flagged(self):
        got = X.read_identity_note("Onfido rejected the passport submitted by JOHN SMITH on 2024-01-05 (DOB 1990-02-03, United Kingdom).", "2024-01-05")
        self.assertFalse(got["approved"])
        got = X.read_identity_note("The Veriff check for JOHN SMITH (DOB 1990-02-03) expired on 2024-01-05; passport from France.", "2024-01-05")
        self.assertFalse(got["approved"])

    def test_other_notes_are_not_identity_checks(self):
        self.assertIsNone(X.read_identity_note("Customer asked about savings interest rates and was sent the current tariff.", "2024-01-05"))
        self.assertIsNone(X.read_identity_note("Documentation shows the individual resided and held employment within Norway between 2008 and 2011.", "2024-01-05"))
        self.assertIsNone(X.read_identity_note("Customer reported a lost card. Card frozen and a replacement ordered to the address on file.", "2024-01-05"))

    def test_places_lived(self):
        self.assertEqual(X.lived_in("The customer was a resident and employee based in Indonesia during the 2010 to 2011 period."), ["ID"])
        self.assertEqual(X.lived_in("Singapore was the site of the client's work and residency between 2014 and 2019."), ["SG"])
        self.assertEqual(X.lived_in("Customer called to ask how long an international transfer takes. Explained the usual timelines."), [])


if __name__ == "__main__":
    unittest.main()
