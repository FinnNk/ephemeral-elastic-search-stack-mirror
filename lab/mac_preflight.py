"""Read-only host and running-lab inventory for a Mac transfer; never stops services."""
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))


def command(args, timeout=30):
    """Return bounded diagnostic output without shell expansion or credential logging."""
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
        return result.returncode, result.stdout, result.stderr[-500:]
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, '', str(error)


def tool(name):
    """Prefer retained host tools only when they match this operating system."""
    bundled = STATE / 'tools' / (name + ('.exe' if os.name == 'nt' else ''))
    return str(bundled) if bundled.is_file() else shutil.which(name)


def platforms(document):
    """Read index platforms or Docker's verified single-image descriptor."""
    entries = document if isinstance(document, list) else document.get('manifests', [])
    if isinstance(document, dict) and 'Descriptor' in document:
        entries = [document['Descriptor']]
    return sorted({p['os'] + '/' + p['architecture']
                   for entry in entries
                   for p in [entry.get('platform', entry.get('Descriptor', {}).get('platform', {}))]
                   if p.get('os') in ('linux', 'windows') and p.get('architecture')})


def image_platforms(image):
    """Inspect exact manifests. Unknown support is never reported as portable."""
    if image.startswith('nexus.localhost:18185/'):
        # The lab registry has an explicitly configured loopback HTTP endpoint.
        args = ['docker', 'manifest', 'inspect', '--verbose', '--insecure', image.replace('nexus.localhost:18185/', '127.0.0.1:18185/', 1)]
        env = os.environ.copy()
        config = STATE / 'control-docker-config'
        if config.is_dir():
            env['DOCKER_CONFIG'] = str(config)
        try:
            r = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', timeout=40, env=env)
            code, output = r.returncode, r.stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
    else:
        code, output, _ = command(['docker', 'buildx', 'imagetools', 'inspect', '--raw', image], 40)
    if code:
        return []
    try:
        return platforms(json.loads(output))
    except (ValueError, KeyError):
        return []


def inventory(server=None, inspect_images=False, target='arm64'):
    """Collect non-secret metadata and architecture blockers from the named lab only."""
    kubectl = tool('kubectl')
    if not kubectl:raise ValueError('kubectl is unavailable.')
    kube = [kubectl, '--kubeconfig', str(STATE / 'kubeconfig.yaml')]
    if server:kube += ['--server', server]
    def get(resource):
        code, value, _ = command(kube + ['get', resource, '-A', '-o', 'json'])
        if code:raise ValueError('Could not read ' + resource + ' from the lab.')
        return json.loads(value)['items']
    code, output, _ = command(kube + ['config', 'current-context'])
    if code or output.strip() != 'k3d-relevance-lab':raise ValueError('Select the retained relevance-lab kubeconfig.')
    nodes, pods, pvcs = get('nodes'), get('pods'), get('persistentvolumeclaims')
    images = sorted({c['image'] for p in pods if p.get('status', {}).get('phase') not in ('Succeeded','Failed')
                     for c in p['spec'].get('containers', []) + p['spec'].get('initContainers', [])})
    def inspect(image):
        support = image_platforms(image) if inspect_images else []
        return {'image':image,'platforms':support,
                'target_support':'yes' if 'linux/'+target in support else 'no' if support else 'unknown'}
    external = []
    code, output, _ = command(['docker', 'network', 'inspect', 'k3d-relevance-lab'])
    if code == 0:
        names = sorted(c['Name'] for c in json.loads(output)[0].get('Containers', {}).values())
        for name in names:
            if not (name.startswith('k3d-') or name.startswith('relevance-')):continue
            code, value, _ = command(['docker', 'inspect', name])
            if code:continue
            obj = json.loads(value)[0]
            external.append({'name':name,'image':obj['Config']['Image'],'memory_limit_bytes':obj['HostConfig']['Memory'],
                'mounts':[{'type':m['Type'],'name':m.get('Name'),'source':m['Source'],'destination':m['Destination']}
                          for m in obj.get('Mounts', [])]})
    with ThreadPoolExecutor(max_workers=4) as pool:
        image_records = list(pool.map(inspect, sorted(set(images + [c['image'] for c in external]))))
    return {'nodes':[{'name':n['metadata']['name'],'architecture':n['status']['nodeInfo']['architecture'],
                     'allocatable_memory':n['status']['allocatable']['memory']} for n in nodes],
            'persistent_volumes':[{'namespace':p['metadata']['namespace'],'name':p['metadata']['name'],
                 'capacity':p.get('status', {}).get('capacity', {}).get('storage'),'volume':p['spec'].get('volumeName')}
                for p in pvcs], 'images':image_records, 'docker_containers':external,
            'gpu_workloads':[{'namespace':p['metadata']['namespace'],'name':p['metadata']['name']}
                            for p in pods if any(c.get('resources', {}).get('limits', {}).get('nvidia.com/gpu')
                                                 for c in p['spec'].get('containers', []))]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=('arm64','amd64'), default='arm64')
    parser.add_argument('--cluster', action='store_true', help='Read the existing named cluster and volumes')
    parser.add_argument('--images', action='store_true', help='Inspect exact workload manifests; requires --cluster')
    parser.add_argument('--server', help='Optional retained Kubernetes API endpoint override')
    parser.add_argument('--output', type=Path, help='New diagnostic JSON file; never overwrites a previous inventory')
    args = parser.parse_args()
    if args.images and not args.cluster:parser.error('--images requires --cluster')
    if args.output and args.output.exists():parser.error('Output already exists; choose a new file.')
    checks = []
    for name, arguments in [('git',['--version']),('docker',['info','--format','{{.OSType}} {{.Architecture}} {{.MemTotal}}']),
                            ('k3d',['version']),('kubectl',['version','--client','-o','json']),('helm',['version','--short'])]:
        executable = tool(name)
        code, output, error = command([executable,*arguments]) if executable else (1,'','Not installed')
        checks.append({'tool':name,'available':code==0,'result':output.strip() if code==0 else error})
    report = {'observed_at':datetime.now(timezone.utc).isoformat(),'host':platform.system(),
              'host_architecture':platform.machine(),'python':platform.python_version(),'target':args.target,
              'python_supported':sys.version_info >= (3,12),'tools':checks,
              'native_mac_verified':False,'note':'This inventory is not a restore or native Mac acceptance test.'}
    if args.cluster:report['lab'] = inventory(args.server,args.images,args.target)
    value = json.dumps(report,indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            output.write(value)
        print('Inventory saved: '+str(args.output))
    else:print(value)
    if not report['python_supported'] or any(not c['available'] for c in checks):return 1
    return 0


if __name__ == '__main__':sys.exit(main())
