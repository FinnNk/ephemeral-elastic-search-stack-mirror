"""Build, verify and optionally publish the three small dated catalogue fixtures."""
import argparse
import json
from pathlib import Path
import sys

from common import ROOT, STATE
sys.path.insert(0, str(ROOT / 'data'))
from demo_timeline import build
from publish import publish


def prepare(publish_blobs=False):
    """Retain deterministic compressed products and unchanged subset judgements."""
    options = {}
    if publish_blobs:
        from blob_config import settings, service
        options = {'blob_url': settings()[0], 'container': settings()[1], 'blob_service': service()}
    result = {}
    for month in (1, 2, 3):
        release = f'esci-gb-demo-2026-{month:02}'
        print('Preparing ' + release, flush=True)
        folder = STATE / 'releases' / release
        manifest = build(STATE / 'releases/esci-gb-demo-v1', folder, month)
        refs = publish(folder, STATE / 'artifacts-reference' / release,
                       'esci-demo-timeline-v1', release, provenance=manifest['producer'], **options)
        result[release] = {kind: ref['manifest_sha256'] for kind, ref in refs.items()}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--record-pins', action='store_true', help='Producer maintenance: record deterministic input pins')
    args = parser.parse_args()
    values = prepare(args.publish)
    path = ROOT / 'lab/default_inputs.json'
    defaults = json.loads(path.read_text(encoding='utf-8'))
    if args.record_pins:
        defaults = {**defaults, **values}
        path.write_text(json.dumps(defaults, indent=2) + '\n', encoding='utf-8')
        from data_versions import rewrite_data, binding, month_for
        pairs = {}
        for name, refs in defaults.items():
            manifest = json.loads((STATE/'releases'/name/'manifest.json').read_text(encoding='utf-8'))
            product_name = 'products.jsonl.gz' if manifest.get('compression') == 'gzip' else 'products.jsonl'
            sha = manifest['sha256'][product_name]
            pairs[name] = {'name': name, 'effective_date': manifest.get('effective_date'),
                           'inputs': refs, 'rewrite': rewrite_data(sha, month_for(name)),
                           **binding(sha, month_for(name))}
        (ROOT/'lab/paired-data.json').write_text(json.dumps(pairs, indent=2)+'\n', encoding='utf-8')
    elif any(defaults.get(name) != refs for name, refs in values.items()):
        raise ValueError('Generated dated catalogue differs from its committed input pins.')
    if args.publish:
        from data_versions import publish_pairs
        publish_pairs()
    print(json.dumps(values, indent=2))
