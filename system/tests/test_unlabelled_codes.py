"""Invented end-to-end boundaries for record-independent clearing grounds."""
import unittest

from test_pipeline import Folder


class UnlabelledCodes(unittest.TestCase):
    def check(self, line, decision, code, rid):
        self.assertEqual(line['decision'], decision, line['reason'])
        self.assertEqual(line['reason_code'], code, line['reason'])
        self.assertEqual(line['customer_record_id'], rid, line['reason'])

    def test_type_mismatch_both_directions_with_and_without_record(self):
        for customer_kind, hit_kind, customer_word, hit_word in (
                ('Individual', 'Company', 'person', 'company'),
                ('Company', 'Individual', 'company', 'person')):
            for linked in (True, False):
                with self.subTest(customer=customer_kind, linked=linked):
                    f = Folder()
                    rid = f.customer('Elora Vale', kind=customer_kind) if linked else None
                    account = f.field('accounts', 'customer_id', rid, 'account_id') if linked else None
                    a = f.alert('Elora Vale', account=account, kind=customer_kind)
                    h = f.hit(a, 'Elora Vale', kind=hit_kind)
                    line = f.run()[h]
                    self.check(line, 'DIFFERENT_ENTITY', 'ENTITY_TYPE_MISMATCH', rid)
                    self.assertEqual(line['evidence'], [rid] if linked else [])
                    self.assertIn('customer is a %s' % customer_word, line['reason'])
                    self.assertIn('hit is a %s' % hit_word, line['reason'])

    def test_unknown_hit_type_does_not_create_mismatch(self):
        for kind in (None, 'Unknown'):
            with self.subTest(kind=kind):
                f = Folder()
                rid = f.customer('Elora Vale')
                a = f.alert('Elora Vale', account=f.field('accounts', 'customer_id', rid, 'account_id'))
                h = f.hit(a, 'Elora Vale', kind=kind)
                line = f.run()[h]
                self.check(line, 'REVIEW', 'INSUFFICIENT_DATA', rid)
                self.assertIn(rid, line['evidence'])
                self.assertIn('date of birth', line['reason'])

    def death_case(self, death, screened, clears, linked=True, shown=None):
        f = Folder()
        rid = f.customer('Elora Vale') if linked else None
        account = f.field('accounts', 'customer_id', rid, 'account_id') if linked else None
        a = f.alert('Elora Vale', account=account, screened_at=screened)
        h = f.hit(a, 'Elora Vale', deceased=death)
        line = f.run()[h]
        self.check(line, 'DIFFERENT_ENTITY' if clears else 'REVIEW',
                   'DECEASED' if clears else 'INSUFFICIENT_DATA', rid)
        if clears:
            self.assertEqual(line['evidence'], [h + '#deceased_date'])
            self.assertIn(shown or death, line['reason'])
            self.assertIn(screened, line['reason'])
            self.assertIn('before', line['reason'])
        else:
            self.assertNotIn(h + '#deceased_date', line['evidence'])
            self.assertIn('neither cleared nor confirmed' if linked else 'neither clear nor confirm',
                          line['reason'])
            if linked:
                self.assertIn(rid, line['evidence'])

    def test_strict_day_boundary_with_and_without_record(self):
        for linked in (True, False):
            for death, clears in (('2026-06-14', True), ('2026-06-15', False),
                                  ('2026-06-16', False), (None, False)):
                with self.subTest(linked=linked, death=death):
                    self.death_case(death, '2026-06-15', clears, linked)

    def test_missing_screening_date_cannot_establish_death_before_it(self):
        self.death_case('2020-01-01', None, False)

    def test_partial_death_dates_require_entire_period_before_screening(self):
        for death, clears in (('2025', True), ('2026', False),
                              ('2026-05', True), ('2026-06', False)):
            with self.subTest(death=death):
                self.death_case(death, '2026-06-15', clears)

    def test_ambiguous_numeric_death_crossing_screening_does_not_clear(self):
        self.death_case('04/03/2026', '2026-03-20', False)


if __name__ == '__main__':
    unittest.main()
