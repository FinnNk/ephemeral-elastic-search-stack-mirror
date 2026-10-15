"""Live counters are bounded, private and cannot replace capture evidence."""
import io
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from concurrent.futures import ThreadPoolExecutor

from capture_progress import Progress
from operation_telemetry import event_sink
import evaluation_job as job
import evaluation_worker
import common


class EvaluationProgressTests(unittest.TestCase):
    def test_command_timeout_preserves_in_cluster_configuration_and_completed_job(self):
        token=event_sink.set(lambda event:None);self.addCleanup(event_sink.reset,token)
        completed=SimpleNamespace(returncode=0,stdout=json.dumps({'status':{'succeeded':1}}))
        with patch.object(common.subprocess,'run',return_value=completed) as run:
            job.wait_for_capture('evaluate-safe',4)
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.kwargs['timeout'],10)
        command=run.call_args.args[0]
        self.assertEqual(command,common.KUBE+['get','job/evaluate-safe','-n','lab-evaluation','-o','json'])
        self.assertFalse(any(arg.startswith('--request-timeout') for arg in command))

    def test_status_read_failures_are_bounded_and_not_reported_as_worker_waits(self):
        events=[];token=event_sink.set(events.append);self.addCleanup(event_sink.reset,token)
        for failure in (SimpleNamespace(returncode=1,stdout='',stderr='private connection detail'),
                        subprocess.TimeoutExpired('kubectl',10)):
            with self.subTest(failure=type(failure).__name__):
                result={'side_effect':failure} if isinstance(failure,Exception) else {'return_value':failure}
                with patch.object(job,'k',**result) as command,patch.object(job.time,'sleep'):
                    with self.assertRaisesRegex(RuntimeError,'status could not be read after three attempts'):
                        job.wait_for_capture('evaluate-safe',4)
                self.assertEqual(command.call_count,3)
        self.assertTrue(all(e['phase']=='Waiting for Kubernetes Job status' for e in events))
        self.assertNotIn('private',json.dumps(events))

    def test_log_timeout_does_not_hide_job_completion(self):
        token=event_sink.set(lambda event:None);self.addCleanup(event_sink.reset,token)
        outcomes=[SimpleNamespace(returncode=0,stdout='{"status":{}}'),
                  subprocess.TimeoutExpired('kubectl',10),
                  SimpleNamespace(returncode=0,stdout='{"status":{"succeeded":1}}')]
        with patch.object(job,'k',side_effect=outcomes) as command,patch.object(job.time,'sleep'):
            job.wait_for_capture('evaluate-safe',4)
        self.assertEqual(command.call_count,3)

    def test_concurrent_worker_counters_are_accurate_and_do_not_log_requests(self):
        pacer=Mock();pacer.summary.return_value={'retries':2,'wait_seconds':.5}
        stream=io.StringIO()
        with patch('sys.stdout',stream):
            tracker=Progress(20,{'baseline':pacer,'candidate':pacer},interval=999)
            with ThreadPoolExecutor(max_workers=8) as workers:
                list(workers.map(tracker.completed,[{'query_id':'private-'+str(i),**({'error':{'detail':'private'}} if i%2 else {})} for i in range(20)]))
        lines=stream.getvalue().splitlines()
        self.assertEqual(len(lines),2)
        self.assertNotIn('private',stream.getvalue())
        self.assertEqual(json.loads(lines[-1].split(' ',1)[1]),
            {'total':20,'completed':20,'failed':10,'retries':4,'pacing_wait_seconds':1})

    def test_capture_keeps_result_order_when_progress_is_enabled(self):
        rows=[{'query_id':str(i),'query':'private','country':'GB','currency':'GBP'} for i in range(12)]
        def response(side,row,pacer):
            if row['query_id']=='3':raise ValueError('failed')
            return {'ids':['product'],'total':1}
        output=io.StringIO()
        with patch('sys.stdout',output),patch.object(evaluation_worker,'request',side_effect=response):
            result=evaluation_worker.run(rows,'baseline','candidate',progress=True)
        self.assertEqual([r['query_id'] for r in result],[r['query_id'] for r in rows])
        self.assertEqual(json.loads(output.getvalue().splitlines()[-1].split(' ',1)[1])['failed'],1)
        self.assertNotIn('private',output.getvalue())

    def test_polling_tolerates_missing_and_malformed_logs_then_keeps_last_sample(self):
        events=[];token=event_sink.set(events.append);self.addCleanup(event_sink.reset,token)
        states=iter([{}, {}, {}, {'succeeded':1}])
        logs=iter(['unrelated private text\nLAB_EVALUATION_PROGRESS []\nLAB_EVALUATION_PROGRESS null', 'LAB_EVALUATION_PROGRESS '+json.dumps({'total':4,'completed':2,'failed':1,'retries':1,'query':'private'}), 'truncated', ''])
        def kubectl(*args,**kwargs):
            return SimpleNamespace(returncode=0,stdout=json.dumps({'status':next(states)}) if args[0]=='get' else next(logs))
        with patch.object(job,'k',side_effect=kubectl),patch.object(job.time,'sleep'):
            with job.capture_scope('sneakers'):job.wait_for_capture('evaluate-safe',4)
        self.assertEqual(events[0]['phase'],'Waiting for capture worker')
        self.assertEqual(events[1]['metrics']['completed'],2)
        self.assertEqual(events[2]['metrics']['completed'],2)
        self.assertTrue(events[2]['metrics_stale'])
        self.assertEqual(events[1]['suite'],'sneakers')
        self.assertNotIn('private',json.dumps(events))
        self.assertNotIn('query',events[1]['metrics'])

    def test_job_failure_and_deadline_still_fail(self):
        token=event_sink.set(lambda event:None);self.addCleanup(event_sink.reset,token)
        def kubectl(*args,**kwargs):
            return SimpleNamespace(returncode=0,stdout=json.dumps({'status':{'failed':1}}) if args[0]=='get' else '')
        with patch.object(job,'k',side_effect=kubectl):
            with self.assertRaisesRegex(RuntimeError,'Job failed'):job.wait_for_capture('evaluate-safe',4)
        with patch.object(job.time,'monotonic',side_effect=[0,301]):
            with self.assertRaises(TimeoutError):job.wait_for_capture('evaluate-safe',4)

    def test_cli_without_sink_keeps_existing_wait_and_finish_counts_are_provisional(self):
        token=event_sink.set(None)
        try:
            with patch.object(job,'k') as kubectl:job.wait_for_capture('job',4)
            self.assertIn('--timeout=300s',kubectl.call_args.args)
        finally:event_sink.reset(token)
        events=[];token=event_sink.set(events.append);self.addCleanup(event_sink.reset,token)
        job.completed_capture([{}, {'error':{'kind':'ValueError'}}],job.time.monotonic(),'job')
        self.assertEqual(events[0]['metrics'],{'total':2,'completed':2,'failed':1})
        self.assertTrue(events[0]['provisional'])


if __name__=='__main__':unittest.main()
