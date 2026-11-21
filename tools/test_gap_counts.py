"""Invented research-tool cases. Run: python -m unittest discover -s tools -p test_gap_counts.py"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gap_counts as G


class GapCountsTests(unittest.TestCase):
    def fixture(self, folder):
        rows = {table: [] for table in G.TABLES}
        rows['alerts'] = [{'alert_id': 'A-FA0001', 'screened_at': '2025-01-01',
                           'email': 'madeup@example.invalid', 'hit_ids': ['H-FA0001'],
                           'customer': {'name': 'Invented Willow', 'entity_type': 'Individual'}}]
        rows['customers'] = [{'record_id': 'CUS-990001', 'full_name': 'Invented Willow',
                              'entity_type': 'Individual', 'email': 'madeup@example.invalid',
                              'dob': '1980-01-01', 'residence_country': 'GB'}]
        rows['hits'] = [{'hit_id': 'H-FA0001', 'alert_id': 'A-FA0001',
                         'name': 'Invented Willow', 'entity_type': 'Individual',
                         'dobs': ['unreadable-date'], 'countries': ['unmapped-place'],
                         'identifiers': [{'value': 'invented-secret-marker'}]}]
        for table, data in rows.items():
            (folder / (table + '.jsonl')).write_text(''.join(json.dumps(row) + '\n' for row in data), encoding='utf-8')
        (folder / 'name_variants.json').write_text('{"groups": [], "company_legal_forms": []}', encoding='utf-8')

    def test_aggregate_privacy_unknown_and_environment_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder)
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            with patch.dict('os.environ', {'SCREENING_LAYERS': 'reader=enforce,reviewer=enforce', 'OPENROUTER_API_KEY': 'invented'}):
                first = G.count_gaps(folder)
            self.assertEqual(first, G.count_gaps(folder))
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})
            self.assertEqual(first['hits'], 1)
            self.assertEqual(first['hits_with_measured_indicator'], 1)
            for key in ('R04', 'R05', 'R09', 'R16'):
                self.assertEqual(first['gaps'][key]['hits'], 1)
            self.assertIsNone(first['unknown']['R12']['hits'])
            output = json.dumps(first)
            for private in ('Invented', 'CUS-990001', 'H-FA0001', 'example.invalid', 'invented-secret-marker', tmp):
                self.assertNotIn(private, output)
            self.assertEqual(sum(first['baseline_decisions'].values()), first['hits'])

    def test_structured_tie_and_future_are_proxies(self):
        base = {'result': 'approved', 'checked_at': '2026-01-01', 'verified_name': 'Invented Alder'}
        other = dict(base, verified_name='Invented Birch')
        self.assertEqual(G.structured_check_flags([base, other], G.D.parse_date('2025-01-01')), (True, True))
        self.assertEqual(G.structured_check_flags([base, dict(other, result='rejected')], None), (False, False))

    def test_future_check_not_hidden_by_duplicate_check_ids_or_row_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder)
            (folder / 'onboarding.jsonl').write_text(json.dumps({
                'customer_id': 'CUS-990001', 'kyc_applicant_id': 'APP-FA0001'}), encoding='utf-8')
            base = {'check_id': 'KYC-FA0001', 'applicant_id': 'APP-FA0001',
                    'result': 'approved', 'verified_name': 'Invented Willow',
                    'verified_dob': '1980-01-01', 'document_country': 'GB'}
            rows = [dict(base, checked_at='2026-01-01'), dict(base, checked_at='2024-01-01')]
            path = folder / 'kyc_checks.jsonl'
            reports = []
            for order in (rows, list(reversed(rows))):
                path.write_text(''.join(json.dumps(row) + '\n' for row in order), encoding='utf-8')
                reports.append(G.count_gaps(folder))
            self.assertEqual(reports[0]['gaps']['R02']['hits'], 1)
            self.assertEqual(reports[0]['gaps'], reports[1]['gaps'])
            self.assertEqual(reports[0]['baseline_decisions'], reports[1]['baseline_decisions'])

    def test_bad_input_fails_without_leaking_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder)
            (folder / 'hits.jsonl').write_text('private-broken-row', encoding='utf-8')
            output, error = io.StringIO(), io.StringIO()
            with patch('sys.argv', ['gap_counts.py', tmp]), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                self.assertEqual(G.main(), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertNotIn('private-broken-row', error.getvalue())
            self.assertNotIn(tmp, error.getvalue())

    def test_missing_table_duplicate_id_and_missing_alert_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder)
            path = folder / 'hits.jsonl'
            path.write_text(path.read_text() * 2, encoding='utf-8')
            with self.assertRaises(ValueError):
                G.count_gaps(folder)
            self.fixture(folder)
            (folder / 'accounts.jsonl').unlink()
            with self.assertRaises(OSError):
                G.count_gaps(folder)
            self.fixture(folder)
            row = json.loads(path.read_text())
            row['alert_id'] = 'A-FA0002'
            path.write_text(json.dumps(row), encoding='utf-8')
            with self.assertRaises(ValueError):
                G.count_gaps(folder)


if __name__ == '__main__':
    unittest.main()
