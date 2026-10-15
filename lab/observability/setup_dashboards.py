"""Apply both dashboards and register this installation's public links."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import STATE, guard, k
import dashboard
import model_dashboard


def setup(url, token):
    if not token:
        raise ValueError('Set a short-lived administrator SIGNOZ_ACCESS_TOKEN outside Git.')
    guard()
    value = {'search': dashboard.apply(url, token), 'model': model_dashboard.apply(url, token)}
    # Register only public IDs. Credentials never enter the runtime or receipt.
    script = r"""import json,os,sys
from pathlib import Path
p=Path(os.environ.get('LAB_STATE_DIR','/state'))/'observability-dashboards.json'
t=p.with_suffix('.tmp'); t.write_text(json.dumps(json.load(sys.stdin),indent=2)+'\n',encoding='utf-8'); t.replace(p)
"""
    k('exec', '-i', 'deployment/lab-control', '-n', 'lab-control', '-c', 'api',
      '--', 'python', '-c', script, body=value)
    path = STATE / 'observability-dashboards.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:18090')
    args = parser.parse_args()
    print(json.dumps(setup(args.url, os.environ.get('SIGNOZ_ACCESS_TOKEN')), indent=2))
