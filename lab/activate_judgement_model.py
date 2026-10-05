"""Connect the judgement APIs to an already loaded, numerically checked KServe model."""
import argparse
import json
from pathlib import Path
import re
import sys

from common import ROOT, STATE, apply, guard, k
sys.path.insert(0, str(ROOT / 'judgements'))
from esci.deployment import render


def api_patch(deployment, image, predictor):
    """Preserve inputs and caches while pinning inference and provenance settings."""
    container = deployment['spec']['template']['spec']['containers'][0]
    args = list(container['args'])
    args[args.index('--predict-url') + 1] = (
        f'http://{predictor}-predictor.lab-models.svc/v1/models/judgement-model:predict')
    for flag, path in (('--inference-identity', '/config/inference.json'),
                       ('--model-policy', '/config/policy.json')):
        if flag in args:
            args[args.index(flag) + 1] = path
        else:
            args.extend((flag, path))
    return {'spec': {'template': {'spec': {'containers': [{
        'name': container['name'], 'image': image, 'args': args,
        'env': [{'name': 'JUDGEMENT_PREDICT_TIMEOUT_SECONDS', 'value': '600'}]}]}}}}


def activate(receipt, qualification, runtime_image, api_image, predictor, output):
    """Check the loaded model before changing either API; keep quality unqualified."""
    guard()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', predictor) or not re.fullmatch(
            r'nexus\.localhost:18185/relevance-judge:[^@\s]+@sha256:[0-9a-f]{64}', api_image):
        raise ValueError('Use a lab predictor name and a digest-pinned judgement API image.')
    output = Path(output)
    if output.exists():
        raise FileExistsError('Use a fresh activation receipt directory.')
    # render validates the matching model, release, runtime and numerical checks.
    generated = render(receipt, runtime_image, qualification)['items']
    expected = next(row for row in generated if row['kind'] == 'InferenceService')['spec']['predictor']['model']
    loaded = json.loads(k('get', 'inferenceservice/' + predictor, '-n', 'lab-models', '-o', 'json').stdout)
    observed_model = loaded['spec']['predictor']['model']
    if any(observed_model.get(key) != value for key, value in expected.items()) or not any(
            c['type'] == 'Ready' and c['status'] == 'True' for c in loaded['status']['conditions']):
        raise ValueError('The selected KServe predictor is not ready with the checked model.')
    runtime = json.loads(k('get', 'servingruntime/' + expected['runtime'], '-n', 'lab-models', '-o', 'json').stdout)
    if runtime['spec']['containers'][0]['image'] != runtime_image:
        raise ValueError('The loaded predictor uses another runtime image.')
    deployments = {}
    for name in ('judgement-service', 'judgement-service-million'):
        found = k('get', 'deployment/' + name, '-n', 'lab-models', '-o', 'json', check=False)
        if found.returncode == 0:
            deployments[name] = json.loads(found.stdout)
    if not deployments:
        raise ValueError('No judgement API is installed.')
    previous = json.loads(k('get', 'configmap/judgement-model-pin', '-n', 'lab-models', '-o', 'json').stdout)
    output.mkdir(parents=True)
    (output / 'before.json').write_text(json.dumps({'pin': previous, 'deployments': deployments}, indent=2), encoding='utf-8')
    pin = next(row for row in generated if row['kind'] == 'ConfigMap')
    # Numerical agreement permits serving, but does not establish label accuracy.
    pin['data']['policy.json'] = json.dumps({'pass_id': 'numerical-' + qualification['evidence_sha256'][:16],
        'policy_sha256': qualification['evidence_sha256'], 'qualification': 'numerical-only',
        'runtime_image': runtime_image, 'release_sha256': receipt['release_sha256'], 'gate_eligible': False})
    apply(pin)
    for name, deployment in deployments.items():
        k('patch', 'deployment/' + name, '-n', 'lab-models', '--type=strategic',
          '-p', json.dumps(api_patch(deployment, api_image, predictor)))
    for name in deployments:
        k('rollout', 'status', 'deployment/' + name, '-n', 'lab-models', '--timeout=180s')
        script = "import json,urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18086/health').read().decode())"
        health = json.loads(k('exec', 'deployment/' + name, '-n', 'lab-models', '-c', name,
                              '--', 'python', '-c', script).stdout)
        if health['model'] != qualification['model'] or health['inference'] != json.loads(pin['data']['inference.json']):
            raise ValueError('Judgement API model or inference identity differs after activation.')
    result = {'model': qualification['model'], 'predictor': predictor, 'runtime_image': runtime_image,
        'api_image': api_image, 'numerical_evidence_sha256': qualification['evidence_sha256'],
        'gate_eligible': False, 'deployments': list(deployments), 'gpu_reloads': 0}
    (output / 'activation.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--qualification', required=True, type=Path)
    parser.add_argument('--runtime-image', required=True)
    parser.add_argument('--api-image', required=True)
    parser.add_argument('--predictor', default='esci-v3-candidate')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(activate(json.loads(args.receipt.read_bytes()), json.loads(args.qualification.read_bytes()),
        args.runtime_image, args.api_image, args.predictor, args.output)))
