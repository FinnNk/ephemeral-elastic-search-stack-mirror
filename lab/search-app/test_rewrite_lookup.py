"""External rewrite lookup handles misses, dependency failures and foreign data."""
import json
import os
import unittest
from unittest.mock import Mock, patch
import redis
import rewrite_lookup


class RewriteLookup(unittest.TestCase):
    def test_hit_miss_failure_and_catalogue_mismatch(self):
        env={'REWRITE_REDIS_HOST':'redis.test','REWRITE_REDIS_KEY':'rewrite:fixture','REWRITE_CATALOGUE_SHA256':'a'*64}
        row={'query':'running shoes','decision':'trainers-to-running-shoes','catalogue_sha256':'a'*64}
        with patch.dict(os.environ,env),patch.object(rewrite_lookup,'client') as client:
            client.return_value.hget.return_value=json.dumps(row)
            self.assertEqual(rewrite_lookup.lookup('Trainers'),('running shoes','redis:trainers-to-running-shoes'))
            client.return_value.hget.assert_called_with('rewrite:fixture','trainers')
            for value in (None,'{}','broken',json.dumps({**row,'catalogue_sha256':'b'*64})):
                client.return_value.hget.return_value=value; self.assertIsNone(rewrite_lookup.lookup('trainers'))
            client.return_value.hget.side_effect=redis.ConnectionError('offline')
            self.assertIsNone(rewrite_lookup.lookup('trainers'))

    def test_actual_local_rewrite_is_used_on_failure(self):
        import app
        with patch.object(rewrite_lookup,'lookup',return_value=None),patch.object(app,'local_understand',return_value=('fallback','local-rule')):
            self.assertEqual(app.understand('query'),('fallback','local-rule'))
