"""The viewer's built-in sample is real output, and the page carries the same lines.

The sample is what the system writes for the invented folder in tools/make_viewer_sample.py.
If a change to the system changes that output, run `python tools/make_viewer_sample.py`.
Run:  python -m unittest discover -s system/tests
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_viewer_sample as sample  # noqa: E402

HOW = "the viewer sample is out of date: run python tools/make_viewer_sample.py"


def rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class ViewerSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fresh = dict(zip((name for name, _ in sample.BLOCKS), sample.build()))
        cls.page = sample.read(sample.PAGE)

    def test_the_sample_files_are_what_the_system_writes_now(self):
        for name, filename in sample.BLOCKS:
            stored = sample.read(os.path.join(sample.SAMPLE, filename))
            self.assertEqual(rows(stored), rows(self.fresh[name]), HOW)

    def test_the_page_carries_the_same_lines_as_the_sample_files(self):
        for name, filename in sample.BLOCKS:
            stored = sample.read(os.path.join(sample.SAMPLE, filename))
            self.assertEqual(sample.embedded(self.page, name), sample.for_page(stored), HOW)
            self.assertEqual(rows(sample.embedded(self.page, name)), rows(stored), HOW)

    def test_the_sample_shows_every_kind_of_outcome(self):
        hits = rows(self.fresh["sample-scored"])
        self.assertEqual(set(hit["decision"] for hit in hits), {"DIFFERENT_ENTITY", "SAME_ENTITY", "REVIEW"})
        codes = set(hit["reason_code"] for hit in hits)
        for code in ("DOB_MISMATCH", "LOCATION_MISMATCH", "NAME_MISMATCH_VERIFIED", "ENTITY_TYPE_MISMATCH",
                     "TEMPORAL_IMPOSSIBILITY", "DECEASED", "NAME_DOB_MATCH", "NAME_LOCATION_MATCH",
                     "INSUFFICIENT_DATA", "AMBIGUOUS_CUSTOMER_RECORD"):
            self.assertIn(code, codes)

    def test_the_sample_is_invented(self):
        """Every record in the sample comes from the builder: no file of real data is read."""
        for hit in rows(self.fresh["sample-explain"]):
            for person in hit["people"]:
                for record in person["record_ids"]:
                    self.assertRegex(record, r"^CUS-000\d{3}$")


if __name__ == "__main__":
    unittest.main()
