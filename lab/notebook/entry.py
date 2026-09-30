"""Download one immutable comparison report and execute its packaged notebook."""

import base64
import hashlib
import json
import os
from pathlib import Path
import urllib.request

import papermill

ROOT = Path('/work')


def main():
    ROOT.mkdir(exist_ok=True)
    with urllib.request.urlopen(os.environ.pop('LAB_REPORT_URL'), timeout=30) as response:
        report = response.read(8_000_001)
    if len(report) > 8_000_000 or hashlib.sha256(report).hexdigest() != os.environ.pop('LAB_REPORT_SHA256'):
        raise ValueError('Comparison report differs from the selected frozen report.')
    input_path = ROOT / 'comparison.json'
    input_path.write_bytes(report)
    output_path = ROOT / 'executed.ipynb'
    papermill.execute_notebook('/input/source.ipynb', str(output_path),
                               parameters={'comparison_path': str(input_path)},
                               kernel_name='python3', progress_bar=False, cwd=str(ROOT))
    result = output_path.read_bytes()
    if len(result) > 1_500_000:
        raise ValueError('Executed notebook exceeds the retention limit.')
    json.loads(result)
    print('LAB_NOTEBOOK_RESULT=' + base64.b64encode(result).decode(), flush=True)


if __name__ == '__main__':
    main()
