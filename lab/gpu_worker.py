"""Build, add, inspect or remove the optional NVIDIA worker; never run inference."""

import argparse
import json
import subprocess

from common import ROOT, STATE, apply, guard, k

NAME = 'relevance-gpu-worker'
NETWORK = 'k3d-relevance-lab'
IMAGE = 'relevance-gpu-worker:v1.35.8-toolkit1.20.1'
OWNER = 'relevance-lab.optional-gpu-worker'
FOLDER = STATE / 'gpu-worker'
PLUGIN = 'nvcr.io/nvidia/k8s-device-plugin:v0.18.2@sha256:b5788e29e7ae5272de8de863ebe386d6611e608421a6ecc5b4e7d5952aba637f'


def docker(*args, check=True):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, encoding='utf-8')
    if check and result.returncode:
        # Commands may contain bootstrap credentials; never echo their arguments.
        raise RuntimeError('Docker operation failed: ' + result.stderr[-1500:])
    return result


def existing():
    result = docker('inspect', NAME, check=False)
    if result.returncode:
        return None
    details = json.loads(result.stdout)[0]
    if details['Config'].get('Labels', {}).get(OWNER) != 'true':
        raise RuntimeError('The worker name belongs to another container.')
    return details


def plugin_manifest():
    return {
        'apiVersion': 'apps/v1', 'kind': 'DaemonSet',
        'metadata': {'name': NAME + '-device-plugin', 'namespace': 'kube-system'},
        'spec': {
            'selector': {'matchLabels': {'app': NAME + '-device-plugin'}},
            'template': {
                'metadata': {'labels': {'app': NAME + '-device-plugin'}},
                'spec': {
                    'nodeSelector': {'lab.relevance/gpu-worker': 'true'},
                    'tolerations': [{'key': 'lab.relevance/gpu', 'operator': 'Exists', 'effect': 'NoSchedule'}],
                    'containers': [{
                        'name': 'device-plugin', 'image': PLUGIN,
                        'env': [{'name': 'FAIL_ON_INIT_ERROR', 'value': 'true'}],
                        'securityContext': {'allowPrivilegeEscalation': False, 'capabilities': {'drop': ['ALL']}},
                        'volumeMounts': [{'name': 'device-plugin', 'mountPath': '/var/lib/kubelet/device-plugins'}],
                    }],
                    'volumes': [{'name': 'device-plugin', 'hostPath': {'path': '/var/lib/kubelet/device-plugins'}}],
                },
            },
        },
    }


def create(memory):
    guard()
    details = existing()
    if details and details['Image'] != docker('image', 'inspect', IMAGE, '--format', '{{.Id}}').stdout.strip():
        raise RuntimeError('The worker uses a different image. Remove it before recreating with the built image.')
    if not details:
        architecture = docker('info', '--format', '{{.Architecture}}').stdout.strip()
        if architecture != 'x86_64':
            raise RuntimeError('This optional NVIDIA worker requires an x86 Linux Docker engine; omit it on Apple silicon.')
        FOLDER.mkdir(parents=True, exist_ok=True)
        # Retain the bootstrap token in ignored local state, never in Git or output.
        token = docker('exec', 'k3d-relevance-lab-server-0', 'cat', '/var/lib/rancher/k3s/server/node-token').stdout.strip()
        (FOLDER / 'join.env').write_text('K3S_URL=https://k3d-relevance-lab-server-0:6443\nK3S_TOKEN=' + token + '\n', encoding='utf-8')
        registry = {'mirrors': {
            'nexus.localhost:18185': {'endpoint': ['http://relevance-nexus:5000']},
            'gitea.localhost:31800': {'endpoint': ['http://k3d-relevance-lab-server-0:30080']},
        }}
        (FOLDER / 'registries.yaml').write_text(json.dumps(registry), encoding='utf-8')
        image = docker('image', 'inspect', IMAGE, '--format', '{{.Id}}').stdout.strip()
        docker('run', '-d', '--name', NAME, '--hostname', NAME,
               '--label', OWNER + '=true', '--network', NETWORK, '--privileged',
               '--gpus', 'all', '--memory', memory, '--restart', 'unless-stopped',
               '--env-file', str(FOLDER / 'join.env'),
               '--mount', f'type=bind,src={FOLDER / "registries.yaml"},dst=/etc/rancher/k3s/registries.yaml,readonly',
               '--mount', f'type=volume,src={NAME}-data,dst=/var/lib/rancher/k3s',
               '--mount', f'type=volume,src={NAME}-kubelet,dst=/var/lib/kubelet',
               '--mount', f'type=volume,src={NAME}-identity,dst=/etc/rancher/node',
               image, 'agent', '--node-name', NAME, '--default-runtime', 'nvidia',
               '--node-label', 'lab.relevance/gpu-worker=true',
               '--node-taint', 'lab.relevance/gpu=reserved:NoSchedule')
    elif not details['State']['Running']:
        docker('start', NAME)
    k('wait', '--for=create', 'node/' + NAME, '--timeout=180s')
    k('wait', '--for=condition=Ready', 'node/' + NAME, '--timeout=180s')
    # Bind the Pod template to this node incarnation when a retained worker is recreated.
    node = json.loads(k('get', 'node', NAME, '-o', 'json').stdout)
    manifest = plugin_manifest()
    manifest['spec']['template']['metadata']['annotations'] = {'lab.relevance/worker-uid': node['metadata']['uid']}
    # No model is deployed here. The taint excludes ordinary lab workloads.
    apply(manifest)
    print(json.dumps({'worker': NAME, 'inference_started': False, 'next': 'Run status; wait for Ready and one allocatable GPU.'}))


def status():
    guard()
    details = existing()
    result = k('get', 'node', NAME, '-o', 'json', check=False)
    node = json.loads(result.stdout) if not result.returncode else None
    report = {
        'worker': NAME, 'container_running': bool(details and details['State']['Running']),
        'image_id': details['Image'] if details else None,
        'node_ready': bool(node and any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions'])),
        'allocatable_gpu': node['status']['allocatable'].get('nvidia.com/gpu', '0') if node else '0',
        'taints': node['spec'].get('taints', []) if node else [],
    }
    print(json.dumps(report, indent=2))


def remove():
    guard()
    if not existing():
        raise RuntimeError('No owned GPU worker exists.')
    k('drain', NAME, '--ignore-daemonsets', '--delete-emptydir-data', '--timeout=180s')
    k('delete', 'daemonset', NAME + '-device-plugin', '-n', 'kube-system', '--ignore-not-found')
    docker('rm', '-f', NAME)
    k('delete', 'node', NAME, '--ignore-not-found')
    print(json.dumps({'removed': NAME, 'retained': 'Worker volumes and ignored bootstrap state; existing nodes unchanged.'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'create', 'status', 'remove'])
    parser.add_argument('--memory', default='28g', help='Docker worker RAM limit; default 28g')
    args = parser.parse_args()
    if args.command == 'build':
        subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '-t', IMAGE, str(ROOT / 'lab/gpu-worker')], check=True)
    elif args.command == 'create':
        create(args.memory)
    elif args.command == 'status':
        status()
    else:
        remove()


if __name__ == '__main__':
    main()
