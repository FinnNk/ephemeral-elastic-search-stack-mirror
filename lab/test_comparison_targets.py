"""Delivery discovery, release identity and notebook comparison contracts."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import comparison_targets as targets
from lifecycle import Lifecycle, Store
from search_target import api_url


class ComparisonTargetsTests(unittest.TestCase):
    def test_production_slots_use_distinct_services(self):
        self.assertEqual(api_url('lab-delivery-production-blue'),
                         'http://search-blue.lab-delivery-production.svc.cluster.local:8080')
        self.assertEqual(api_url('lab-delivery-production-green'),
                         'http://search-green.lab-delivery-production.svc.cluster.local:8080')
        self.assertEqual(api_url('lab-demo'), 'http://search.lab-demo.svc.cluster.local:8080')

    def test_discovery_retains_identity_and_rejects_stale_selection(self):
        def kube(*args, **options):
            if args[1] == 'applications':
                data = {'items': []}
            elif args[1].startswith('configmap'):
                data = {'data': {'active-slot': 'blue'}}
            else:
                data = {'metadata': {'generation': 1}, 'status': {'availableReplicas': 1, 'readyReplicas': 1, 'updatedReplicas': 1, 'observedGeneration': 1}}
            return SimpleNamespace(returncode=0, stdout=json.dumps(data))
        definition = {'fingerprint': 'a'*64, 'source_sha': 'b'*40, 'image': 'image',
                      'dataset_sha256': 'c'*64, 'dataset_release': 'esci-gb-v1',
                      'index': 'index', 'index_recipe_sha256': 'd'*64}
        with TemporaryDirectory() as folder, patch.object(targets, 'STATE', Path(folder)), \
                patch.object(targets, 'k', side_effect=kube), \
                patch('compare_search.definition', return_value=definition):
            rows = targets.available()
            blue = next(r for r in rows if r['name'].endswith('blue'))
            self.assertEqual(blue['slot_role'], 'active')
            self.assertIsNone(blue['browser_url'])
            self.assertEqual(targets.lookup(Mock(), blue['id'], current=True)['fingerprint'], 'a'*64)
            with patch('compare_search.definition', return_value={**definition, 'fingerprint': 'e'*64}):
                with self.assertRaisesRegex(ValueError, 'changed or is not ready'):
                    targets.lookup(Mock(), blue['id'], current=True)
            self.assertEqual(targets.snapshot(blue['id'])['fingerprint'], 'a'*64)
            self.assertIsNone(targets.snapshot('delivery:../../secrets'))

    def test_unready_delivery_targets_are_not_offered(self):
        def kube(*args, **options):
            data = {'items': []} if args[1] == 'applications' else (
                {'data': {'active-slot': 'blue'}} if args[1].startswith('configmap') else
                {'metadata': {'generation': 2}, 'status': {'availableReplicas': 0, 'observedGeneration': 1}})
            return SimpleNamespace(returncode=0, stdout=json.dumps(data))
        with TemporaryDirectory() as folder, patch.object(targets, 'STATE', Path(folder)), \
                patch.object(targets, 'k', side_effect=kube), \
                patch('compare_search.definition', return_value={}):
            self.assertEqual(targets.available(), [])
            self.assertFalse((Path(folder)/'comparison-targets').exists())

    def test_delivery_notebook_preserves_verdict_without_lease_mutation(self):
        from contextlib import nullcontext
        with TemporaryDirectory() as folder:
            store = Store(Path(folder)/'lifecycle.sqlite3')
            controller = Lifecycle(store, Mock())
            controller.comparator = Mock(return_value={'complete': True, 'verdict': 'measured',
                'report_sha256': 'a'*64, 'report_blob': 'runs/report.json'})
            rows = {side: {'id': 'delivery:' + side, 'name': 'lab-delivery-' + side,
                    'managed_by': 'delivery', 'state': 'ready', 'release_id': 'esci-gb-v1',
                    'dataset_sha256': 'a'*64, 'fingerprint': side} for side in ('integration', 'staging')}
            with patch('comparison_targets.lookup', side_effect=lambda _s, key, **kw: rows[key.split(':')[1]]), \
                    patch('delivery_runtime.writer', return_value=nullcontext()), \
                    patch.object(controller, 'activity') as activity, \
                    patch('notebook_task.run', return_value={'state': 'complete'}) as notebook:
                result = controller.compare('delivery:integration', 'delivery:staging', 'relevance',
                                            notebook='comparison-explorer.ipynb', scope='quick')
                self.assertEqual(result['verdict'], 'measured')
                self.assertEqual(result['summary']['notebook']['state'], 'complete')
                activity.assert_not_called()
                notebook.assert_called_once_with('comparison-explorer.ipynb', 'a'*64, 'runs/report.json')


if __name__ == '__main__':
    unittest.main()
