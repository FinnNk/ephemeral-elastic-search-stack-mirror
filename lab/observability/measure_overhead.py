"""Run one frozen normal Gatling workload against paired Search API endpoints.

The caller must supply two otherwise identical, already running APIs. Each run
keeps its native report and actual-arrival ledger under ignored lab state.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[2]
STATE = Path(os.environ.get('LAB_STATE_DIR', ROOT / '.lab'))
sys.path.insert(0, str(STATE / 'python-libs'))
sys.path.insert(0, str(ROOT / 'lab'))
from gatling_report import summarise  # noqa: E402
from run_gatling import IMAGE, SIMULATION  # noqa: E402
from traffic import compile_profile  # noqa: E402

def one(label, base_url, workload, parent):
    folder = parent / (label + '-' + uuid.uuid4().hex[:8])
    project = folder / 'project'
    results = folder / 'results'
    project.mkdir(parents=True)
    results.mkdir()
    source = ROOT / 'lab/gatling'
    shutil.copy2(source / 'pom.xml', project / 'pom.xml')
    java = project / 'src/test/java/lab/relevance/SyntheticSearchSimulation.java'
    java.parent.mkdir(parents=True)
    shutil.copy2(SIMULATION, java)
    command = ['docker', 'run', '--rm', '--cpus=2', '--memory=2g',
               '-v', str(project.resolve()) + ':/workspace',
               '-v', str(Path(workload['directory']).resolve()) + ':/workload:ro',
               '-v', str(results.resolve()) + ':/results',
               '-v', str((STATE / 'm2').resolve()) + ':/root/.m2',
               '-w', '/workspace', IMAGE, 'mvn', '-B', 'gatling:test',
               '-Dgatling.simulationClass=lab.relevance.SyntheticSearchSimulation',
               '-Dlab.workload=/workload', '-Dlab.arrivals=/results/arrivals.csv',
               '-Dlab.baseUrl=' + base_url, '-Dlab.profile=normal']
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace',
                            timeout=workload['duration_seconds'] + 300)
    (folder / 'runner.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(label + ' Gatling run failed; inspect ' + str(folder / 'runner.log'))
    reports = list((project / 'target/gatling').glob('syntheticsearchsimulation-*'))
    if len(reports) != 1:
        raise RuntimeError('Expected one Gatling report in ' + str(folder))
    summary = summarise(reports[0], Path(workload['directory']), results / 'arrivals.csv')
    phase = summary['phases']['normal']
    output = {'label': label, 'base_url': base_url,
              'workload_sha256': workload['workload_sha256'],
              'simulation_sha256': hashlib.sha256(SIMULATION.read_bytes()).hexdigest(),
              'runner_image': IMAGE, 'requests': phase['requests'],
              'failed': phase['failed'], 'p95_ms': phase['p95_ms'],
              'p99_ms': phase['p99_ms'], 'arrival': summary['arrival'],
              'valid': summary['valid'] and phase['failed'] == 0,
              'report_directory': str(reports[0]),
              'arrivals': str(results / 'arrivals.csv')}
    (folder / 'summary.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--on', required=True, help='Telemetry-enabled Search API URL')
    parser.add_argument('--off', required=True, help='Same image and index without telemetry')
    parser.add_argument('--order', default='off,on,on,off',
                        help='Comma-separated paired run order')
    args = parser.parse_args()
    order = args.order.split(',')
    if len(order) < 2 or set(order) != {'on', 'off'}:
        raise ValueError('Run both on and off endpoints.')
    workload = compile_profile('normal', 'retail-gb-1m-v1')
    parent = STATE / 'observability-overhead' / uuid.uuid4().hex[:12]
    parent.mkdir(parents=True)
    runs = []
    for label in order:
        run = one(label, args.on if label == 'on' else args.off, workload, parent)
        runs.append(run)
        print('RUN', label, run['requests'], run['p95_ms'], flush=True)
    on = [row['p95_ms'] for row in runs if row['label'] == 'on' and row['valid']]
    off = [row['p95_ms'] for row in runs if row['label'] == 'off' and row['valid']]
    overhead = ((statistics.median(on) / statistics.median(off)) - 1) * 100 if on and off else None
    result = {'runs': runs, 'workload_sha256': workload['workload_sha256'],
              'relative_p95_percent_by_medians': overhead,
              'hypothesis_percent': 5, 'sample_count_on': len(on),
              'sample_count_off': len(off),
              'status': 'measured' if on and off else 'inconclusive'}
    (parent / 'comparison.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('COMPARISON', parent / 'comparison.json', flush=True)


if __name__ == '__main__':
    main()
