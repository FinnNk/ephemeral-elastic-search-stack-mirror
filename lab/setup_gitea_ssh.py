"""Configure loopback SSH and a dedicated encrypted Mac key for the fresh lab."""
import argparse
import getpass
import json
from pathlib import Path
import subprocess
import sys

from common import STATE
import gitea_ssh_client as client
import gitea_ssh_server as server


def install(server_only=False, prompt_password=False):
    tools = None if server_only else client.mac_tools()
    if prompt_password and not sys.stdin.isatty():
        raise ValueError('Run the private Gitea password prompt in an interactive Terminal.')
    # Validate the local key paths/terminal before restarting a service.
    uid = server.identity()
    paths = client.layout(Path.home(), uid)
    account = None
    if tools:
        client.preflight(paths)
        account = json.loads((STATE / 'user-credentials.json').read_text(encoding='utf-8'))
        if prompt_password:
            account['gitea_password'] = getpass.getpass('Current Gitea password (not the Control password): ')
        if client.user_api(account, '/user')['login'] != account['username']:
            raise ValueError('Gitea authenticated a different account.')
    if server.install() != uid:
        raise ValueError('Lab identity changed during setup; retry after the cluster settles.')
    if server_only:
        print('Gitea SSH is enabled at 127.0.0.1:31822; no workstation keys were created.')
        return
    host = server.host_key(tools['ssh-keyscan'])
    public = client.key_pair(paths, tools, account['username'])
    key_id = client.register(account, uid, public)
    client.configure(Path.home(), paths, uid, host)
    client.load_key(paths, tools, public)
    source = client.verify(tools)
    (STATE / 'git-ssh.json').write_text(json.dumps({
        'cluster_uid': uid, 'username': account['username'], 'gitea_key_id': key_id,
        'host_fingerprint': server.fingerprint(host), 'key_fingerprint': server.fingerprint(public),
        'identity_file': str(paths['key']), 'source_head': source, 'verified': True}, indent=2) + '\n',
        encoding='utf-8')
    print('Clone: git clone ' + client.ALIAS + ':elastic-agent/delivery-source.git')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'verify'))
    parser.add_argument('--server-only', action='store_true', help='Enable SSH without touching workstation keys')
    parser.add_argument('--prompt-gitea-password', action='store_true',
                        help='Read a changed Gitea password privately for key registration; do not save it')
    args = parser.parse_args()
    if args.server_only and (args.action != 'install' or args.prompt_gitea_password):
        parser.error('--server-only applies only to install without a workstation password prompt')
    try:
        if args.action == 'install':
            install(args.server_only, args.prompt_gitea_password)
        else:
            server.identity()
            client.verify(client.mac_tools())
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + '\n')
    except subprocess.SubprocessError:
        parser.exit(1, 'SSH key or Keychain command did not complete. Retained keys were not replaced; rerun setup in Terminal.\n')


if __name__ == '__main__':
    main()
