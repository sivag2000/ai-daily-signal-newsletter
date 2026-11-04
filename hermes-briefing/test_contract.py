import unittest
from contract import validate_bundle,normalize_gaps


class ContractTests(unittest.TestCase):
    def test_non_boolean_coverage_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_bundle(dict(items=[],gaps=[],coverage_complete='true'))

    def test_non_object_candidate_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_bundle(dict(items=['invented'],gaps=[],coverage_complete=False))

    def test_structured_gap_is_normalized(self):
        self.assertEqual(normalize_gaps([dict(category='ai',issue='Missing date')]),['ai: Missing date'])

    def test_gap_detail_variant_preserves_uncertainty(self):
        self.assertEqual(normalize_gaps([dict(type='date_uncertainty',detail='No exact time')]),
                         ['date_uncertainty: No exact time'])
