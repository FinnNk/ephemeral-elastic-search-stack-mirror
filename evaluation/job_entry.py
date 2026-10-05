"""Finite offline evaluator: download exact inputs, score, retain one report."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from azure.storage.blob import BlobServiceClient

from offline import canonical, evaluate
from job_event import emit
from retain import retain

INPUTS = ('observations', 'judgements', 'specification', 'catalogue_manifest',
          'query_manifest', 'judgement_manifest')


def fetch(client, reference, target):
    if not {'sha256', 'bytes', 'blob'} <= set(reference):
        raise ValueError('Evaluator input reference is incomplete.')
    container, object_name = reference['blob'].split('/', 1)
    if container not in ('runs', 'datasets') or not object_name or \
            '..' in object_name.split('/'):
        raise ValueError('Evaluator input is outside retained Blob containers.')
    payload = client.get_blob_client(container, object_name).download_blob().readall()
    if hashlib.sha256(payload).hexdigest() != reference['sha256'] or \
            len(payload) != reference['bytes']:
        raise ValueError('Evaluator input differs from its retained hash and size.')
    target.write_bytes(payload)


def run(inputs, client, workdir, evaluated_at=None):
    if set(inputs) != set(INPUTS):
        raise ValueError('Evaluator requires all six exact input references.')
    paths = {name: workdir / (name + '.json') for name in INPUTS}
    paths['judgements'] = workdir / 'judgements.jsonl'
    for name in INPUTS:
        fetch(client, inputs[name], paths[name])
    result = evaluate(*(paths[name] for name in INPUTS), evaluated_at=evaluated_at)
    output = workdir / 'evaluation-report.json'
    output.write_bytes(canonical(result))
    reference = retain(output, 'evaluation-report', 'runs')
    return {'report': reference, 'complete': result['complete'],
            'query_count': result['query_count'],
            'metrics': result['metrics'], 'delta_from_baseline': result['delta_from_baseline'],
            'ndcg_significance': result['ndcg_significance'],
            'result_changes': result['result_changes'],
            'result_similarity': {name: {key: value for key, value in scores.items()
                                        if key != 'per_query'}
                                 for name, scores in result['result_similarity'].items()}}


def main():
    started = time.monotonic()
    try:
        connection = os.environ['DATA_BLOB_CONNECTION_STRING']
        inputs = json.loads(os.environ['EVALUATION_INPUTS_JSON'])
        client = BlobServiceClient.from_connection_string(connection)
        with tempfile.TemporaryDirectory(prefix='offline-evaluator-') as directory:
            result = run(inputs, client, Path(directory), os.environ.get('EVALUATED_AT'))
    except Exception:
        emit('offline-evaluator', 'evaluation.score', 'failed', started)
        raise
    emit('offline-evaluator', 'evaluation.score', 'complete', started,
         observation_sha256=inputs['observations']['sha256'],
         judgement_manifest_sha256=inputs['judgement_manifest']['sha256'],
         specification_sha256=inputs['specification']['sha256'],
         report_sha256=result['report']['sha256'])
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
