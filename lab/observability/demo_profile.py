"""Small SigNoz demo settings; preserve the pinned backend and full metric stream."""
import copy
import json
from pathlib import Path
import re

import yaml


def resources(request, limit, cpu='1'):
    return {'requests': {'cpu': '100m', 'memory': request},
            'limits': {'cpu': cpu, 'memory': limit}}


def storage_bytes(value):
    """Compare PVC requests; refuse quantities this profile cannot interpret."""
    match = re.fullmatch(r'(\d+)(Ki|Mi|Gi|Ti)', value)
    if not match:
        raise ValueError('Unsupported PVC storage quantity: ' + value)
    return int(match[1]) * 1024 ** {'Ki': 1, 'Mi': 2, 'Gi': 3, 'Ti': 4}[match[2]]


def values(here, state):
    """Build one complete values file without the dedicated-worker selectors."""
    result = yaml.safe_load((here / 'signoz-values.yaml').read_text(encoding='utf-8'))
    clickhouse = result['clickhouse']
    for item in (clickhouse, clickhouse['zookeeper'], clickhouse['clickhouseOperator'],
                 result['signoz'], result['otelCollector'], result['telemetryStoreMigrator']):
        item.pop('nodeSelector', None)
    clickhouse['persistence']['size'] = '10Gi'
    clickhouse['resources'] = resources('512Mi', '2Gi', '2')
    clickhouse['profiles'] = {'default/max_memory_usage': '1073741824'}
    clickhouse.setdefault('settings', {})['max_server_memory_usage'] = '1610612736'
    zk = clickhouse['zookeeper']
    zk.update(replicaCount=1, resources=resources('128Mi', '384Mi'),
              heapSize=128, persistence={'enabled': True, 'size': '1Gi'})
    result['signoz'].update(replicaCount=1, resources=resources('128Mi', '384Mi'))
    result['otelCollector'].update(replicaCount=1, resources=resources('128Mi', '512Mi'))
    result['telemetryStoreMigrator']['resources'] = resources('128Mi', '512Mi')
    # A pre-upgrade migration blocks repairs to an unavailable ClickHouse.
    # Run it as a normal Job so Helm applies dependencies before waiting.
    result['telemetryStoreMigrator']['upgradeHelmHooks'] = False
    collector = result['otelCollector'].setdefault('config', {})
    collector['processors'] = {
        'memory_limiter': {'check_interval': '1s', 'limit_mib': 384, 'spike_limit_mib': 96},
        'batch': {'send_batch_size': 512, 'send_batch_max_size': 1024, 'timeout': '1s'}}
    # The pinned chart supplies the remaining processors. Put the limiter first
    # without removing its span metrics, mapping or metering processors.
    import tarfile
    archive = state / 'artifacts/signoz/signoz-0.143.0.tgz'
    with tarfile.open(archive) as chart:
        defaults = yaml.safe_load(chart.extractfile('signoz/values.yaml'))
    pipelines = copy.deepcopy(defaults['otelCollector']['config']['service']['pipelines'])
    for pipeline in pipelines.values():
        pipeline['processors'] = ['memory_limiter'] + [
            name for name in pipeline.get('processors', []) if name != 'memory_limiter']
    collector['service'] = {'pipelines': pipelines}
    # Use the already-built native control image for the histogram download.
    # It supplies curl and the corporate CA bundle; the stock Alpine init image
    # does not trust the corporate HTTPS proxy.
    image = json.loads((state / 'control-image.json').read_text(encoding='utf-8'))['image']
    match = re.fullmatch(r'nexus.localhost:18185/lab-control@sha256:([a-f0-9]{64})', image)
    if not match:
        raise ValueError('Demo setup requires the retained native control image digest.')
    udf = clickhouse['initContainers']['udf']
    udf['image'] = {'registry': 'nexus.localhost:18185', 'repository': 'lab-control',
                    'tag': 'latest@sha256:' + match[1]}
    # fresh_images.trusted_dockerfile installs this bundle in the native image.
    # Embedding the bundle in bash -c exceeds Linux's per-argument size limit.
    udf['command'][2] = udf['command'][2].replace(
        'wget -O histogram-quantile.tar.gz',
        'curl --cacert /usr/local/share/ca-certificates/fresh-lab.crt '
        '-fsSL -o histogram-quantile.tar.gz')
    clickhouse['imagePullSecrets'] = ['nexus-read']
    return result


def operator_patch():
    """The pinned operator chart has no resource values; bound its two containers."""
    return {'spec': {'template': {'spec': {'containers': [
        {'name': 'operator', 'resources': resources('64Mi', '128Mi', '500m')},
        {'name': 'metrics-exporter', 'resources': resources('32Mi', '64Mi', '250m')}]}}}}


def agents(here):
    """Bound queues and sample traces; application and Gatling metrics stay complete."""
    documents = []
    for filename in ('gateway.yaml', 'log-agent.yaml'):
        for resource in yaml.safe_load_all((here / filename).read_text(encoding='utf-8')):
            if resource['kind'] in ('Deployment', 'DaemonSet'):
                pod = resource['spec']['template']['spec']
                pod.pop('nodeSelector', None)
                limit = '256Mi' if resource['kind'] == 'Deployment' else '128Mi'
                pod['containers'][0]['resources'] = resources('64Mi', limit, '500m')
            if resource['kind'] == 'ConfigMap':
                config = yaml.safe_load(resource['data']['config.yaml'])
                config['processors']['memory_limiter'].update(limit_mib=96 if filename == 'log-agent.yaml' else 192,
                                                               spike_limit_mib=24 if filename == 'log-agent.yaml' else 48)
                for exporter in config['exporters'].values():
                    exporter['sending_queue'].update(queue_size=128)
                if filename == 'gateway.yaml':
                    config['processors']['probabilistic_sampler/demo'] = {'sampling_percentage': 20}
                    pipeline = config['service']['pipelines']['traces']['processors']
                    pipeline.insert(pipeline.index('batch'), 'probabilistic_sampler/demo')
                resource['data']['config.yaml'] = yaml.safe_dump(config, sort_keys=False)
            documents.append(resource)
    return documents
