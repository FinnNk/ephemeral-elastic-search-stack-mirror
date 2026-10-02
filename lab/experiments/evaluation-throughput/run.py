"""Run isolated, fresh million-product capture experiments in the installed lab."""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'lab'), str(ROOT / 'lab/search-app')]
from common import STATE, apply, guard, k
from compare_search import frozen_suite, immutable_blob
from variants import canonical

IMAGE = 'docker.io/library/relevance-throughput-experiment:20261002'
TRANSPORTS = ('original', 'cached-tls', 'pooled-es', 'pooled-both')


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


class Experiment:
    def __init__(self, directory):
        guard()
        self.directory = directory
        self.metadata = json.loads((directory / 'context.json').read_bytes())
        self.namespace = self.metadata['namespace']
        if not self.namespace.startswith('lab-throughput-'):
            raise ValueError('Use a disposable throughput experiment namespace.')
        namespace = json.loads(k('get', 'namespace', self.namespace, '-o', 'json').stdout)
        if namespace['metadata'].get('labels', {}).get('lab.experiment') != 'evaluation-throughput':
            raise ValueError('Namespace is not owned by this experiment.')
        self.rows, self.suite, self.suite_sha, _ = frozen_suite('retail-gb-1m-v1')
        self.config = self.metadata['variant_configuration']

    @classmethod
    def setup(cls, directory):
        guard()
        directory.mkdir(parents=True, exist_ok=False)
        namespace = 'lab-throughput-' + uuid.uuid4().hex[:8]
        deployment = json.loads(k('get', 'deployment/search', '-n', 'lab-variant-managed', '-o', 'json').stdout)
        pod = deployment['spec']['template']['spec']
        container = pod['containers'][0]
        env = {item['name']: item.get('value') for item in container['env']}
        config = json.loads(env['SEARCH_VARIANTS_JSON'])
        if env['ES_INDEX'] != 'retail-gb-1m-v1':
            raise ValueError('Select the frozen synthetic million-product index.')
        apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace,
               'labels': {'lab.experiment': 'evaluation-throughput'}}})
        for name in ('search-access', 'es-ca'):
            secret = json.loads(k('get', 'secret/' + name, '-n', 'lab-variant-managed', '-o', 'json').stdout)
            apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': namespace},
                   'type': secret['type'], 'data': secret['data']})
        for mode in TRANSPORTS:
            spec = copy.deepcopy(pod)
            spec['nodeSelector'] = {'kubernetes.io/hostname': 'k3d-relevance-lab-server-0'}
            spec.pop('imagePullSecrets', None)
            api = spec['containers'][0]
            api['image'] = IMAGE
            api['imagePullPolicy'] = 'Never'
            api['command'] = ['python', '/experiment/server.py']
            api['env'] += [{'name': 'EXPERIMENT_TRANSPORT', 'value': mode}]
            api['env'] = [item for item in api['env'] if item['name'] != 'LAB_RELEASE_SHA'] + [
                {'name': 'LAB_RELEASE_SHA', 'value': 'evaluation-throughput-20261002-' + mode}]
            api['readinessProbe'] = {'httpGet': {'path': '/health', 'port': 8080}, 'periodSeconds': 2}
            apply({'apiVersion': 'apps/v1', 'kind': 'Deployment',
                'metadata': {'name': mode, 'namespace': namespace},
                'spec': {'replicas': 1, 'selector': {'matchLabels': {'experiment-mode': mode}},
                         'template': {'metadata': {'labels': {'experiment-mode': mode}}, 'spec': spec}}})
            apply({'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': mode, 'namespace': namespace},
                'spec': {'selector': {'experiment-mode': mode}, 'ports': [{'port': 8080, 'targetPort': 8080}]}})
        for mode in TRANSPORTS:
            k('rollout', 'status', 'deployment/' + mode, '-n', namespace, '--timeout=120s')
        pods = json.loads(k('get', 'pods', '-n', namespace, '-o', 'json').stdout)['items']
        identities = {p['metadata']['labels']['experiment-mode']:
                      p['status']['containerStatuses'][0]['imageID'] for p in pods}
        metadata = {'namespace': namespace, 'created_at': datetime.now(timezone.utc).isoformat(),
            'image': IMAGE, 'observed_images': identities, 'variant_configuration': config,
            'api_resources': container['resources'], 'worker_resources': {
                'requests': {'cpu': '100m', 'memory': '64Mi'}, 'limits': {'cpu': '1', 'memory': '256Mi'}},
            'index': env['ES_INDEX'], 'api_source_sha256': digest((ROOT / 'lab/search-app/app.py').read_bytes()),
            'experiment_sources': {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},
            'resources_before': k('top', 'nodes', check=False).stdout}
        (directory / 'context.json').write_bytes(canonical(metadata))
        print('SETUP', namespace, flush=True)
        return cls(directory)

    def capture(self, mode, strategy='thread-query', client='urllib', limit=8, count=1000, variants=2,
                label='screen', seed=20261002):
        if mode not in TRANSPORTS or not 1 <= limit <= 32 or not 1 <= count <= 1000 or variants not in (2, 3):
            raise ValueError('Experiment requires a known transport, 1–32 requests, 1–1,000 queries and 2/3 variants.')
        if strategy not in ('thread-query', 'thread-flat', 'async-query', 'async-flat', 'adaptive'):
            raise ValueError('Unknown experimental scheduler.')
        run_id = uuid.uuid4().hex[:10]
        names = list(self.config['variants'])[:variants]
        targets = {name: {'url': f'http://{mode}.{self.namespace}.svc.cluster.local:8080',
            'selection': 'default' if name == self.config['default_variant'] else 'explicit',
            'configuration_sha256': digest(canonical(self.config['variants'][name]))} for name in names}
        spec = {'strategy': strategy, 'client': client, 'limit': limit, 'variants': targets, 'seed': seed}
        suite = b'\n'.join(self.suite.splitlines()[:count]) + b'\n'
        config_name, job_name = 'input-' + run_id, 'capture-' + run_id
        apply({'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': config_name, 'namespace': self.namespace},
            'data': {'queries.jsonl': suite.decode(), 'specification.json': json.dumps(spec)}})
        job = {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': job_name, 'namespace': self.namespace},
            'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 300, 'template': {'spec': {
                'restartPolicy': 'Never', 'automountServiceAccountToken': False,
                'nodeSelector': {'kubernetes.io/hostname': 'k3d-relevance-lab-agent-0'},
                'containers': [{'name': 'capture', 'image': IMAGE, 'imagePullPolicy': 'Never',
                    'command': ['python', '/experiment/worker.py'],
                    'resources': self.metadata['worker_resources'],
                    'volumeMounts': [{'name': 'input', 'mountPath': '/input', 'readOnly': True}]}],
                'volumes': [{'name': 'input', 'configMap': {'name': config_name}}]}}}}
        started = time.monotonic()
        created = datetime.now(timezone.utc)
        try:
            apply(job)
            k('wait', '--for=condition=complete', 'job/' + job_name, '-n', self.namespace, '--timeout=300s')
            capture_done = time.monotonic()
            raw = k('logs', 'job/' + job_name, '-n', self.namespace).stdout.encode()
            result = json.loads(raw)
            worker_started = datetime.fromisoformat(result['worker_started_at'])
            result['job_startup_seconds'] = (worker_started - created).total_seconds()
            result['job_wait_seconds'] = capture_done - started
            result['log_collection_seconds'] = time.monotonic() - capture_done
            scoring_started = time.monotonic()
            import ir_measures
            labels = STATE / 'releases/retail-gb-1m-v1/judgements-pool-v2.jsonl'
            qrels = [ir_measures.Qrel(row['query_id'], row['product_id'], row['grade'])
                     for row in (json.loads(line) for line in labels.read_bytes().splitlines())]
            metric_values = {}
            if not result['errors']:
                for name in names:
                    ranking = [ir_measures.ScoredDoc(row['query_id'], product, 10 - rank)
                        for row in result['observations'] for rank, product in enumerate(row['results'][name]['ids'])]
                    metric_values[name] = {str(key): value for key, value in
                        ir_measures.calc_aggregate([ir_measures.nDCG@10, ir_measures.Judged@10], qrels, ranking).items()}
            result['scoring_seconds'] = time.monotonic() - scoring_started
            result['proxy_metrics'] = metric_values
            result['run_id'], result['label'], result['specification'] = run_id, label, spec
            result['transport'], result['suite_sha256'] = mode, digest(suite)
            result['variant_count'] = variants
            retention_started = time.monotonic()
            payload = gzip.compress(canonical(result), mtime=0)
            path = self.directory / (run_id + '.json.gz')
            path.write_bytes(payload)
            blob = immutable_blob('runs', 'evaluation-throughput/' + digest(payload) + '.json.gz', payload)
            record = {key: value for key, value in result.items() if key not in ('events', 'observations')}
            record['raw_sha256'], record['raw_blob'] = digest(payload), blob
            record['retention_seconds'] = time.monotonic() - retention_started
            record['end_to_end_seconds'] = time.monotonic() - started
            with (self.directory / 'ledger.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(record, sort_keys=True) + '\n')
            print(json.dumps({key: record[key] for key in ('run_id','label','transport','variant_count',
                'capture_seconds','end_to_end_seconds','errors','retries','semantic_sha256')}), flush=True)
            return record
        finally:
            k('delete', 'job/' + job_name, '-n', self.namespace, '--ignore-not-found', '--wait=true', check=False)
            k('delete', 'configmap/' + config_name, '-n', self.namespace, '--ignore-not-found', check=False)

    def cleanup(self):
        (self.directory / 'resources-after.txt').write_text(k('top', 'nodes', check=False).stdout, encoding='utf-8')
        k('delete', 'namespace/' + self.namespace, '--wait=true')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('setup', 'capture', 'cleanup'))
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--transport', choices=TRANSPORTS, default='original')
    parser.add_argument('--strategy', default='thread-query')
    parser.add_argument('--client', choices=('urllib','httpx'), default='urllib')
    parser.add_argument('--limit', type=int, default=8)
    parser.add_argument('--queries', type=int, default=1000)
    parser.add_argument('--variants', type=int, choices=(2,3), default=2)
    parser.add_argument('--label', default='screen')
    args = parser.parse_args()
    if args.command == 'setup':
        Experiment.setup(args.directory)
    else:
        instance = Experiment(args.directory)
        if args.command == 'cleanup':
            instance.cleanup()
        else:
            instance.capture(args.transport,args.strategy,args.client,args.limit,args.queries,args.variants,args.label)
