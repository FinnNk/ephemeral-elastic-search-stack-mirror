"""Inspect a fresh installation; explicitly delete only the installer's recorded cluster."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

from fresh_install import CLUSTER, NODES, ROOT, execute, inspect_nodes


def inventory(state):
    """List the named cluster and possible leftovers without changing Docker or host DNS."""
    print('Fresh-install record: ' + ('present' if (state / 'fresh-install.json').exists() else 'absent'))
    print('Recorded state directory: ' + str(state))
    print('Matching node identities: ' + json.dumps(inspect_nodes(), indent=2))
    containers = execute(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    volumes = execute(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
    record_path = state / 'fresh-install.json'
    recorded = json.loads(record_path.read_text(encoding='utf-8')).get('volumes', []) if record_path.exists() else []
    print('Cluster containers: ' + json.dumps([name for name in containers
          if name.startswith('k3d-' + CLUSTER + '-')]))
    print('Possible cluster volumes: ' + json.dumps([name for name in volumes
          if name.startswith('k3d-' + CLUSTER + '-') or name in recorded]))
    print('External lab stores (not removed): ' + json.dumps([name for name in containers
          if name in ('relevance-nexus', 'relevance-nexus-db', 'relevance-snapshot-store')]))
    print('Resolver files (not removed): ' + json.dumps([str(path) for path in
          (Path('/etc/resolver/localhost'), Path('/etc/resolver/preview.relevance.test')) if path.exists()]))


def verify_ownership(state):
    """Refuse foreign clusters, changed Docker identities and unsafe state targets."""
    if state.resolve() != (ROOT / '.lab').resolve() or state.is_symlink():
        raise ValueError('Cleanup is restricted to this checkout\'s real .lab directory.')
    if (state / 'worktrees').exists():
        raise ValueError('State contains worktrees; refusing cleanup of a development lab.')
    if (state / 'fresh-install.lock').exists():
        raise ValueError('Installer lock exists; stop the installer before cleanup.')
    path = state / 'fresh-install.json'
    if not path.exists():
        raise ValueError('No installer ownership record. Use the documented manual reset for older attempts.')
    record = json.loads(path.read_text(encoding='utf-8'))
    if record.get('format') != 1 or record.get('root') != str(ROOT.resolve()) or record.get('cluster') != CLUSTER:
        raise ValueError('Ownership record does not describe this fresh installation.')
    if any(not re.fullmatch(r'[0-9a-f]{64}|k3d-relevance-lab-images', name)
           for name in record.get('volumes', [])):
        raise ValueError('Unexpected volume name in the ownership record.')
    current = inspect_nodes()
    # Missing nodes are acceptable after an interrupted delete; different identities are not.
    if any(record.get('nodes', {}).get(name) != identity for name, identity in current.items()):
        raise ValueError('Docker identities differ from the ownership record; nothing will be deleted.')
    containers = execute(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    expected = set(NODES) | {'k3d-' + CLUSTER + '-serverlb'}
    if any(name.startswith('k3d-' + CLUSTER + '-') and name not in expected for name in containers):
        raise ValueError('Additional lab nodes found; cleanup will not delete an extended installation.')
    return bool(current)


def verify_stores(state):
    """Validate all external store identities before deleting any cluster resource."""
    path = state / 'fresh-services.json'
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding='utf-8'))
    stores = {'relevance-nexus', 'relevance-nexus-db', 'relevance-snapshot-store'}
    if record.get('format') != 1 or record.get('root') != str(ROOT.resolve()) or \
            set(record.get('volumes', [])) != stores or not set(record.get('containers', {})) <= stores:
        raise ValueError('External store ownership record is invalid; nothing will be deleted.')
    for name in stores:
        identity = execute(['docker', 'inspect', '--format', '{{.Id}}', name], check=False).strip()
        if identity and record['containers'].get(name) != identity:
            raise ValueError('External store identity changed; nothing will be deleted: ' + name)
    return record


def cleanup(state, purge=False, include_stores=False):
    """Delete the recorded fresh cluster, then archive or explicitly purge its host state."""
    has_cluster = verify_ownership(state)
    record = json.loads((state / 'fresh-install.json').read_text(encoding='utf-8'))
    stores = verify_stores(state) if include_stores else None
    if has_cluster:
        execute(['k3d', 'cluster', 'delete', CLUSTER], live=True)
    remaining = execute(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
    if any(name.startswith('k3d-' + CLUSTER + '-') for name in remaining):
        raise RuntimeError('Cluster containers remain; host state retained for diagnosis.')
    volumes = execute(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
    for name in record.get('volumes', []):
        if name in volumes:
            # Docker refuses removal of any volume still attached to a container.
            execute(['docker', 'volume', 'rm', name], live=True)
    if stores:
        existing = execute(['docker', 'ps', '-a', '--format', '{{.Names}}']).splitlines()
        for name in ('relevance-nexus', 'relevance-nexus-db', 'relevance-snapshot-store'):
            if name in existing:
                execute(['docker', 'rm', '-f', name], live=True)
        volumes = execute(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
        for name in stores['volumes']:
            if name in volumes:
                execute(['docker', 'volume', 'rm', name], live=True)
    if purge:
        # Recheck the absolute target immediately before recursive deletion.
        verify_ownership(state)
        shutil.rmtree(state.resolve())
        print('Removed fresh-install host state, including generated credentials and CA keys.')
    else:
        destination = state.with_name('.lab-archived-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        state.rename(destination)
        print('Archived secret-bearing host state at: ' + str(destination))
    inventory(state)
    print('Cached images, host certificate trust and resolver files were retained.')
    if not include_stores:
        print('External stores were retained. Use --include-stores for a complete owned reset.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delete', action='store_true', help='Delete the recorded fresh cluster and archive host state')
    parser.add_argument('--confirm', help='Required with --delete: relevance-lab')
    parser.add_argument('--include-stores', action='store_true', help='Also remove installer-owned Nexus and snapshot containers/volumes')
    parser.add_argument('--purge-state', action='store_true', help='Also permanently remove generated host state')
    args = parser.parse_args()
    if args.include_stores and not args.delete:
        parser.error('--include-stores requires --delete')
    if args.purge_state and not args.delete:
        parser.error('--purge-state requires --delete')
    if args.delete and args.confirm != CLUSTER:
        parser.error('--delete requires --confirm relevance-lab')
    state = ROOT / '.lab'
    try:
        if args.delete:
            cleanup(state, args.purge_state, args.include_stores)
        else:
            inventory(state)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
