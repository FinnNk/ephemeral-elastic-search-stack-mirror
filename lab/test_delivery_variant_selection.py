"""Release pages show exact source intents and explicit missing-data states."""
import unittest
from unittest.mock import patch

from delivery_variant_selection import selection_summary


class SelectionSummaryTests(unittest.TestCase):
    def test_mixed_intents_are_read_from_the_exact_build_commit(self):
        selected = {'selection_sha256': 'b' * 64,
            'configuration': {'default_variant': 'ranker-a'},
            'selection': [{'variant': 'ranker-a', 'intent': 'ranking-change'},
                          {'variant': 'control', 'intent': 'preserve-results'}]}
        with patch('delivery_variant_selection.source_selection', return_value=selected) as load:
            value = selection_summary('a' * 40)
        load.assert_called_once_with('a' * 40)
        self.assertEqual(value['state'], 'ready')
        self.assertEqual(value['variants'], [
            {'variant': 'ranker-a', 'intent': 'ranking-change', 'default': True},
            {'variant': 'control', 'intent': 'preserve-results', 'default': False}])

    def test_no_candidate_does_not_load_or_invent_a_selection(self):
        with patch('delivery_variant_selection.source_selection') as load:
            self.assertEqual(selection_summary(None), {'state': 'not-selected', 'variants': []})
        load.assert_not_called()

    def test_provider_failure_does_not_fabricate_an_intent(self):
        with patch('delivery_variant_selection.source_selection', side_effect=RuntimeError('offline')):
            value = selection_summary('a' * 40)
        self.assertEqual(value['state'], 'unavailable')
        self.assertEqual(value['variants'], [])


if __name__ == '__main__':
    unittest.main()
