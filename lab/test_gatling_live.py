import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from operation_telemetry import event_sink
from run_gatling_job import wait_for_gatling


class LiveDriverTests(unittest.TestCase):
    def test_job_metrics_keep_side_environment_and_driver_counters(self):
        events = []
        token = event_sink.set(events.append)
        self.addCleanup(event_sink.reset, token)
        def k(*args, **kwargs):
            if args[0] == 'get':return SimpleNamespace(stdout=json.dumps({'status':{'succeeded':1}}))
            return SimpleNamespace(stdout='Unrelated driver text\nLAB_GATLING_METRICS '+json.dumps(
                {'phase':'peak','completed':10,'failed':1,'mean_latency_ms':40,'completed_rps':2})+'\n')
        with patch('run_gatling_job.k', side_effect=k):
            wait_for_gatling('job', {'duration_seconds':1260}, 'candidate', 'candidate-preview')
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['environment'],'candidate-preview')
        self.assertEqual(events[0]['metrics']['failed'],1)
        self.assertTrue(events[0]['provisional'])
        self.assertLessEqual(events[0]['started_ms'], events[0]['observed_ms'])
        self.assertNotIn('Unrelated',json.dumps(events))

    def test_failed_job_cannot_become_complete(self):
        token=event_sink.set(lambda event:None)
        self.addCleanup(event_sink.reset,token)
        def k(*args,**kwargs):
            return SimpleNamespace(stdout=json.dumps({'status':{'failed':1}}) if args[0]=='get' else '')
        with patch('run_gatling_job.k',side_effect=k):
            with self.assertRaisesRegex(RuntimeError,'Job failed'):
                wait_for_gatling('job',{'duration_seconds':10},'baseline','baseline-preview')


if __name__=='__main__':unittest.main()
