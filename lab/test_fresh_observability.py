"""Check new-install telemetry and dashboard registration without a live lab."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
import setup_delivery
import observability_links
import setup_dashboards
import demo_profile


class FreshObservability(unittest.TestCase):
    def test_seeded_source_contains_instrumentation_and_chart_wiring(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup_delivery, 'api', return_value={'empty':True}), patch.object(setup_delivery,'git'):
            root=Path(folder); setup_delivery.seed_source(root)
            self.assertEqual((root/'app/telemetry.py').read_bytes(), (setup_delivery.ROOT/'lab/search-app/telemetry.py').read_bytes().replace(b'\r\n',b'\n'))
            chart=(root/'chart/templates/environment.yaml').read_text(encoding='utf-8')
            for setting in ('OTEL_EXPORTER_OTLP_ENDPOINT','LAB_RELEASE_SHA','LAB_DEPLOYMENT_TIER','port: 4318'):
                self.assertIn(setting,chart)

    def test_both_profiles_keep_log_correlation_transform(self):
        here=Path(__file__).resolve().parent/'observability'
        standard=list(yaml.safe_load_all((here/'log-agent.yaml').read_text(encoding='utf-8')))
        for docs in (standard,demo_profile.agents(here)):
            cm=next(d for d in docs if d['kind']=='ConfigMap' and d['metadata']['name']=='lab-log-agent')
            config=yaml.safe_load(cm['data']['config.yaml'])
            self.assertIn('transform/lab',config['service']['pipelines']['logs']['processors'])
            self.assertIn('trace',config['receivers']['filelog/lab']['operators'][1])

    def test_dashboard_setup_registers_public_ids_in_runtime_and_host(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); remote=root/'runtime';remote.mkdir()
            def command(*args,body):
                script=args[-1]
                with patch.dict(os.environ,{'LAB_STATE_DIR':str(remote)}), patch('sys.stdin',io.StringIO(json.dumps(body))):
                    exec(compile(script,'runtime-registration','exec'),{})
            with patch.object(setup_dashboards,'STATE',root), patch.object(setup_dashboards,'guard'), patch.object(setup_dashboards.dashboard,'apply',return_value='new-search'), patch.object(setup_dashboards.model_dashboard,'apply',return_value='new-model'), patch.object(setup_dashboards,'k',side_effect=command):
                value=setup_dashboards.setup('http://localhost:18090','session-secret')
            self.assertEqual(json.loads((remote/'observability-dashboards.json').read_text()),value)
            with patch.object(observability_links,'STATE',root):
                self.assertEqual(observability_links.links()['search_dashboard_url'],'https://signoz.localhost:34443/dashboard/new-search')
            self.assertNotIn('session-secret',(root/'observability-dashboards.json').read_text())

    def test_unconfigured_links_never_reuse_another_installation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(observability_links,'STATE',Path(folder)):
            self.assertEqual(observability_links.links(),{})
            (Path(folder)/'observability-dashboards.json').write_text('{"search":"https://untrusted.test"}')
            self.assertEqual(observability_links.links(),{})

    def test_registration_failure_is_not_reported_as_complete(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(setup_dashboards,'STATE',Path(folder)), patch.object(setup_dashboards,'guard'), patch.object(setup_dashboards.dashboard,'apply',return_value='search'), patch.object(setup_dashboards.model_dashboard,'apply',return_value='model'), patch.object(setup_dashboards,'k',side_effect=RuntimeError('unavailable')):
            with self.assertRaises(RuntimeError): setup_dashboards.setup('http://localhost','secret')
            self.assertFalse((Path(folder)/'observability-dashboards.json').exists())


if __name__=='__main__': unittest.main()
