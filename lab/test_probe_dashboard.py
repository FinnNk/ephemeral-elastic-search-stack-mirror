"""Probe panels remain separate from normal SLOs and match committed dashboard JSON."""
import json
from pathlib import Path
import unittest
from observability import dashboard


class ProbeDashboardTests(unittest.TestCase):
    def test_committed_definition_matches_builder(self):
        self.assertEqual(json.loads(dashboard.SPEC.read_text(encoding='utf-8')),dashboard.build())

    def test_probe_panels_are_visible_and_filter_the_selected_environment(self):
        panels=dashboard.build()['spec']['panels']
        for key in ('probe_requests','probe_failures','probe_responsive'):
            queries=panels[key]['spec']['queries'][0]['spec']['plugin']['spec']['queries']
            builder=[q['spec'] for q in queries if q['type']=='builder_query']
            self.assertTrue(builder)
            self.assertTrue(all("lab.traffic_class = 'probe'" in q['filter']['expression'] and
                'deployment.environment.name IN $environment' in q['filter']['expression'] for q in builder))
            self.assertTrue(any(q['type']=='builder_formula' or not q['spec']['disabled'] for q in queries))
        for key in ('eligible','success_ratio','responsive_ratio','success_remaining'):
            queries=panels[key]['spec']['queries'][0]['spec']['plugin']['spec']['queries']
            self.assertTrue(all("lab.traffic_class = 'normal'" in q['spec']['filter']['expression']
                for q in queries if q['type']=='builder_query'))
        self.assertIn('warm-up',panels['guidance']['spec']['plugin']['spec']['text'])


if __name__=='__main__':unittest.main()
