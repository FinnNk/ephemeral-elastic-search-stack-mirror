"""Recover only verified fresh-install outputs made by the old LF checkout."""
import hashlib
import json
from pathlib import Path

from data.contracts import canonical, sha_file

IMPORTER = 'dc6f175d8cf737a8ab8f7df84a374a88824e4fb7fe524303b6092d09a3db758e'
LF_IMPORTER = '40cfc8e4e08aeeb63b18ffdbd494f1a4fd31a19408a86edc82886c38c79faa4f'
MANIFESTS = {
    'esci-gb-v1': '2e8a35766e21d176218fe16c33f7d8c86f1da3eada4fbc3ae5baa8dec3a12d8a',
    'esci-gb-demo-v1': 'ab4a620e175dd17b750e3db497cc8d8771c0b9353c9601d7ed020fd41bf998a1',
}
DERIVED = ('esci-gb-demo-2026-01', 'esci-gb-demo-2026-02', 'esci-gb-demo-2026-03',
           'esci-gb-demo-halloween-2026', 'esci-gb-demo-christmas-2026')


def checked_files(folder, manifest):
    """Verify original bytes; never accept a new product/query/label hash."""
    if set(manifest['sha256']) != {'products.jsonl.gz', 'queries.jsonl', 'judgements.jsonl'}:
        raise ValueError('Unexpected catalogue files: ' + str(folder))
    for name, expected in manifest['sha256'].items():
        if sha_file(folder / name) != expected:
            raise ValueError('Retained catalogue bytes differ: ' + str(folder / name))


def reconcile(state, importer):
    """Keep frozen identities; retain superseded local outputs for inspection.

    The fresh installer calls this only within its owned catalogue stage. A
    repair is allowed solely when replacing the known old LF importer hash
    yields the exact original Windows manifest, and every data hash verifies.
    """
    state = Path(state)
    if sha_file(importer) != IMPORTER:
        raise ValueError('Frozen importer bytes differ; pull the accepted portability fix before resuming.')
    repairs = []
    legacy = set()
    for name, expected in MANIFESTS.items():
        path = state / 'releases' / name / 'manifest.json'
        if not path.exists():
            continue
        raw = path.read_bytes()
        manifest = json.loads(raw)
        if manifest.get('importer_sha256') not in (IMPORTER, LF_IMPORTER):
            continue  # The frozen importer diagnoses other revisions normally.
        fixed = {**manifest, 'importer_sha256': IMPORTER}
        if hashlib.sha256(canonical(fixed)).hexdigest() != expected:
            raise ValueError('Catalogue differs beyond checkout line endings: ' + name)
        checked_files(path.parent, manifest)
        legacy.add(hashlib.sha256(canonical({**fixed, 'importer_sha256': LF_IMPORTER})).hexdigest())
        if raw != canonical(fixed):
            repairs.append((path, raw, canonical(fixed)))

    # Verify everything before the first write. Derived files are rebuilt from
    # the verified source, never re-pinned or edited to match expected hashes.
    retained = []
    for name in DERIVED:
        folder = state / 'releases' / name
        path = folder / 'manifest.json'
        if path.exists():
            manifest = json.loads(path.read_bytes())
            producer = manifest.get('producer', {})
            if legacy.intersection(producer.get(key) for key in
                                   ('source_manifest_sha256', 'base_manifest_sha256')):
                if producer.get('name') not in ('esci-demo-timeline-v1', 'esci-demo-seasons-v1'):
                    raise ValueError('Unexpected derived catalogue producer: ' + name)
                checked_files(folder, manifest)
                retained.append(folder)
        artifacts = state / 'artifacts-reference' / name
        if artifacts.exists():
            values = [json.loads(p.read_bytes()).get('producer', {})
                      for p in artifacts.glob('*.json')]
            old = [bool(legacy.intersection(value.get(key) for key in
                                           ('source_manifest_sha256', 'base_manifest_sha256')))
                   for value in values]
            if any(old):
                if not all(old):
                    raise ValueError('Mixed retained artifact provenance: ' + str(artifacts))
                retained.append(artifacts)

    if not repairs and not retained:
        return
    backup = state / 'portability-recovery'
    for folder in retained:
        destination = backup / (folder.parent.name + '-' + folder.name)
        if destination.exists():
            raise ValueError('Recovery directory exists; inspect before resuming: ' + str(destination))
    backup.mkdir(exist_ok=True)
    for path, raw, fixed in repairs:
        saved = backup / (path.parent.name + '-' + hashlib.sha256(raw).hexdigest() + '.manifest.json')
        if saved.exists() and saved.read_bytes() != raw:
            raise ValueError('Recovery backup differs: ' + str(saved))
        saved.write_bytes(raw)
        temporary = path.with_suffix('.portability.tmp')
        temporary.write_bytes(fixed)
        temporary.replace(path)
        print('Restored original frozen manifest identity: ' + path.parent.name, flush=True)
    for folder in retained:
        destination = backup / (folder.parent.name + '-' + folder.name)
        if destination.exists():
            raise ValueError('Recovery directory exists; inspect before resuming: ' + str(destination))
        folder.rename(destination)
        print('Retained LF-derived output for regeneration: ' + str(destination), flush=True)
