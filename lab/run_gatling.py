"""Run one pinned Gatling profile against a pinned public API in a local container."""
import argparse
import hashlib
import io
import json
import subprocess
import time
import uuid
import zipfile
from pathlib import Path

from common import ROOT, STATE, record
from compare_search import definition, immutable_blob
from gatling_report import summarise
from traffic import compile_profile

IMAGE = 'maven:3.9.11-eclipse-temurin-21@sha256:6fdc855a6ed81d288ca7ca37ac6ff5e9308b612485c0801d70b25a858c83d237'
TARGETS = {'baseline': ('retail-baseline', 18080), 'candidate': ('retail-candidate', 18081)}
REPORTS = ROOT / 'lab/gatling/target/gatling'
SIMULATION = ROOT / 'lab/gatling/src/test/java/lab/relevance/SyntheticSearchSimulation.java'


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, payload in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(info, payload)
    return output.getvalue()


def retain_workload(workload):
    directory = STATE / 'workloads' / workload['workload_sha256']
    files = {path.name: path.read_bytes() for path in directory.glob('*.csv')}
    source_path = Path(workload['source_path'])
    recipe_path = Path(workload['recipe_path'])
    files[source_path.name] = source_path.read_bytes()
    recipe_bytes = recipe_path.read_bytes()
    if hashlib.sha256(recipe_bytes).hexdigest() != workload['recipe_sha256']:
        raise ValueError('Active recipe differs from the compiled workload.')
    files[recipe_path.name] = recipe_bytes
    payload = archive(files)
    digest = hashlib.sha256(payload).hexdigest()
    return {'workload_archive_sha256': digest,
            'workload_archive_blob': immutable_blob('runs', digest + '/compiled-workload.zip', payload)}


def run(profile, target, release_id='retail-gb-10k-v1'):
    if target not in TARGETS:
        raise ValueError('Target must be baseline or candidate.')
    environment, port = TARGETS[target]
    pinned = definition(environment)
    workload = compile_profile(profile, release_id)
    run_id = uuid.uuid4().hex[:12]
    run_dir = STATE / 'gatling-runs' / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    arrivals = run_dir / 'arrivals.csv'
    before = set(REPORTS.glob('syntheticsearchsimulation-*')) if REPORTS.exists() else set()
    command = ['docker', 'run', '--rm', '--cpus=2', '--memory=2g',
        '-v', str(ROOT) + ':/workspace', '-v', str(STATE / 'm2') + ':/root/.m2',
        '-w', '/workspace/lab/gatling', IMAGE, 'mvn', '-B', 'gatling:test',
        '-Dgatling.simulationClass=lab.relevance.SyntheticSearchSimulation',
        '-Dlab.workload=/workspace/.lab/workloads/' + workload['workload_sha256'],
        '-Dlab.arrivals=/workspace/.lab/gatling-runs/' + run_id + '/arrivals.csv',
        '-Dlab.profile=' + profile,
        '-Dlab.baseUrl=http://host.docker.internal:' + str(port)]
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, text=True, encoding='utf-8', errors='replace',
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=workload['duration_seconds'] + 300)
    (run_dir / 'runner.log').write_text(result.stdout, encoding='utf-8')
    candidates = set(REPORTS.glob('syntheticsearchsimulation-*')) - before
    if len(candidates) != 1:
        raise RuntimeError('Expected one new Gatling native report; inspect ' + str(run_dir))
    report_dir = candidates.pop()
    summary = summarise(report_dir, STATE / 'workloads' / workload['workload_sha256'], arrivals)
    summary.update({'run_id': run_id, 'target': target, 'environment': environment,
        'release_id': release_id,
        'fingerprint': pinned['fingerprint'], 'index': pinned['index'], 'image': pinned['image'],
        'runner_image': IMAGE, 'gatling_version': '3.15.1', 'maven_plugin': '4.21.12',
        'simulation_sha256': hashlib.sha256(SIMULATION.read_bytes()).hexdigest(),
        'duration_wall_seconds': round(time.monotonic() - started, 3), 'runner_exit_code': result.returncode,
        'runner_limits': {'cpu': 2, 'memory': '2g'}, 'host': 'Windows 11 / Docker Desktop / local k3d'})
    summary.update(retain_workload(workload))
    report_files = {str(path.relative_to(report_dir)).replace('\\', '/'): path.read_bytes()
                    for path in report_dir.rglob('*') if path.is_file()}
    report_files['arrivals.csv'] = arrivals.read_bytes()
    report_files['runner.log'] = result.stdout.encode()
    report_files['simulation.java'] = SIMULATION.read_bytes()
    report_files['pom.xml'] = (ROOT / 'lab/gatling/pom.xml').read_bytes()
    payload = archive(report_files)
    digest = hashlib.sha256(payload).hexdigest()
    summary['native_report_sha256'] = digest
    summary['native_report_blob'] = immutable_blob('runs', digest + '/gatling-report.zip', payload)
    record('gatling-' + profile + '-' + target + '-' + run_id, summary)
    record('gatling-' + profile + '-' + target, summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=('probe', 'smoke', 'normal', 'peak', 'stress',
                                            'normal-full', 'sustained-peak', 'stress-full'))
    parser.add_argument('target', choices=TARGETS)
    parser.add_argument('--release', default='retail-gb-10k-v1')
    args = parser.parse_args()
    print(json.dumps(run(args.profile, args.target, args.release), indent=2))
