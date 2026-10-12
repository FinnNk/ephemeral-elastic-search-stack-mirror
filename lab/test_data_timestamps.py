"""Dates remain explicit and do not change frozen catalogue/index identities."""
import unittest
from unittest.mock import Mock, patch
import data_timestamps as dates


class DataTimestampTests(unittest.TestCase):
    def test_every_catalogue_has_an_explicit_synthetic_timestamp(self):
        for release in dates.PROFILES['releases']:
            meta = dates.catalogue_metadata(release)
            self.assertTrue(meta['catalogue_timestamp'].endswith('T00:00:00Z'))
            self.assertEqual(meta['catalogue_timestamp_kind'], 'synthetic')
        self.assertEqual(dates.catalogue_metadata('esci-gb-demo-christmas-2026')['catalogue_timestamp'],
                         '2026-12-01T00:00:00Z')

    def test_observed_index_time_is_distinct_from_simulated_catalogue(self):
        actual = {'settings': {'index': {'creation_date': '1791799200000'}}}
        meta = dates.index_metadata('index', 'esci-gb-v1', actual)
        self.assertEqual(meta['index_created_at'], '2026-10-12T10:00:00Z')
        self.assertEqual(meta['index_timestamp_kind'], 'observed')
        self.assertEqual(meta['catalogue_timestamp_kind'], 'synthetic')

    def test_missing_creation_setting_has_explicit_synthetic_fallback(self):
        meta = dates.index_metadata('index', 'esci-gb-v1', {})
        self.assertEqual(meta['index_timestamp_kind'], 'synthetic')
        self.assertEqual(meta['index_created_at'], meta['catalogue_timestamp'])

    def test_recording_preserves_recipe_marker_and_is_idempotent(self):
        actual = {'mappings': {'_meta': {'index_recipe_sha256': 'a'*64}},
                  'settings': {'index': {'creation_date': '1791799200000'}}}
        client = Mock()
        dates.record_index_metadata('index', 'esci-gb-v1', actual, client=client)
        payload = client.call_args.args[2]['_meta']
        self.assertEqual(payload['index_recipe_sha256'], 'a'*64)
        self.assertEqual(payload['index_created_at'], '2026-10-12T10:00:00Z')
        actual['mappings']['_meta'] = payload
        client.reset_mock()
        dates.record_index_metadata('index', 'esci-gb-v1', actual, client=client)
        client.assert_not_called()

    def test_index_choices_filter_by_verified_recipe_catalogue(self):
        actual = {'mappings': {'_meta': {'index_recipe_sha256': 'a'*64}},
                  'settings': {'index': {'creation_date': '1791799200000'}}}
        with patch.object(dates, 'elastic', return_value={'index': actual}), \
                patch('index_recipe.load', return_value={'release_id': 'esci-gb-v1', 'index_kind': 'shared'}):
            self.assertEqual(len(dates.existing_indices('esci-gb-v1')), 1)
            self.assertEqual(dates.existing_indices('esci-gb-demo-v1'), [])
