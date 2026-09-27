"""Model a synthetic assessor revision without observing either candidate API."""

import argparse
import hashlib
import json
from pathlib import Path


def revise(source, output, catalogue_manifest, query_manifest):
    source, output = Path(source), Path(output)
    rows = []
    revised = 0
    for line in source.read_bytes().splitlines():
        row = json.loads(line)
        if row.get('assessment') == 'S' and row['grade'] == 2:
            row = {**row, 'assessment': 'E', 'grade': 3}
            revised += 1
        rows.append(row)
    if not revised:
        raise ValueError('Source has no synthetic substitute assessments to revise.')
    payload = b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode()
                       for row in rows)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.read_bytes() != payload:
        raise ValueError('Existing revised judgements differ.')
    if not output.exists():
        output.write_bytes(payload)
    manifest = {'kind': 'synthetic-judgement-revision', 'schema_version': 1,
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'content_sha256': hashlib.sha256(payload).hexdigest(),
                'count': len(rows), 'revised_count': revised,
                'rule': 'Treat every synthetic S/substitute label as E/exact; no API result is consulted.'}
    manifest_bytes = (json.dumps(manifest, sort_keys=True, indent=2) + '\n').encode()
    target = output.with_suffix('.revision.json')
    if target.exists() and target.read_bytes() != manifest_bytes:
        raise ValueError('Existing judgement revision manifest differs.')
    if not target.exists():
        target.write_bytes(manifest_bytes)
    catalogue = json.loads(Path(catalogue_manifest).read_bytes())
    queries = json.loads(Path(query_manifest).read_bytes())
    contract = {'kind': 'judgement-set', 'schema_version': 1,
                'content': {'sha256': manifest['content_sha256'], 'bytes': len(payload),
                            'format': 'jsonl', 'compression': 'none',
                            'object': 'judgement-set/' + manifest['content_sha256'] + '/' + output.name},
                'dependencies': {'catalogue': catalogue['content']['sha256'],
                                 'query-suite': queries['content']['sha256']},
                'producer': {'name': 'synthetic-assessor-revision-v2', 'synthetic': True,
                             'source_release': catalogue['producer']['source_release'],
                             'source_judgement_sha256': manifest['source_sha256']},
                'record_count': len(rows)}
    contract_bytes = (json.dumps(contract, sort_keys=True, separators=(',', ':')) + '\n').encode()
    contract_path = output.with_suffix('.manifest.json')
    if contract_path.exists() and contract_path.read_bytes() != contract_bytes:
        raise ValueError('Existing judgement contract differs.')
    if not contract_path.exists():
        contract_path.write_bytes(contract_bytes)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--catalogue-manifest', required=True, type=Path)
    parser.add_argument('--query-manifest', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(revise(args.source, args.output, args.catalogue_manifest,
                            args.query_manifest), indent=2))
