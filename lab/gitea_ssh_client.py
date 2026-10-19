"""Install a dedicated, encrypted Mac Git key without replacing other SSH keys."""
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

from common import STATE
from gitea_ssh_server import HOST_PORT, fingerprint, public_key

ALIAS = 'relevance-lab-gitea'
API_URL = 'http://127.0.0.1:31800/api/v1'


def mac_tools():
    if platform.system() != 'Darwin':
        raise ValueError('Workstation key and Keychain setup currently supports macOS only.')
    tools = {name: '/usr/bin/' + name for name in ('ssh', 'ssh-keygen', 'ssh-keyscan', 'ssh-add', 'git')}
    if any(not Path(path).is_file() for path in tools.values()):
        raise ValueError('Install the macOS SSH and Git command-line tools first.')
    agent = subprocess.run([tools['ssh-add'], '-l'], capture_output=True, timeout=15)
    if agent.returncode not in (0, 1):
        raise ValueError('The SSH agent is unavailable. Run setup in your normal macOS Terminal session.')
    return tools


def safe_path(path):
    if path.is_symlink():
        raise ValueError('Refusing to replace a symbolic link: ' + str(path))


def retain(path, content):
    """Create private files once; an unexpected existing file is never overwritten."""
    safe_path(path)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError('Existing SSH file differs; inspect it before retrying: ' + str(path))
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)
    path.chmod(0o600)


def layout(home, uid):
    directory = Path(home) / '.ssh' / 'relevance-lab'
    return {'directory': directory, 'key': directory / ('id_ed25519-' + uid),
            'config': directory / ('config-' + uid),
            'known_hosts': directory / ('known-hosts-' + uid)}


def preflight(paths):
    safe_path(paths['directory'].parent)
    safe_path(paths['directory'].parent / 'config')
    for path in paths.values():
        safe_path(path)
    key = paths['key']
    public = key.with_suffix('.pub')
    safe_path(public)
    if key.exists() != public.exists():
        raise ValueError('Only half of the lab key pair exists; recover it before retrying.')
    if not key.exists() and not sys.stdin.isatty():
        raise ValueError('Run SSH setup in macOS Terminal to choose a key passphrase; '
                         'use --skip-git-ssh only for an intentionally unattended installation.')
    configuration(paths, 'preflight')


def key_pair(paths, tools, username):
    key = paths['key']
    directory = paths['directory']
    directory.parent.mkdir(mode=0o700, exist_ok=True)
    directory.mkdir(mode=0o700, exist_ok=True)
    if not key.exists():
        print('Choose a non-empty passphrase for the dedicated lab key. '
              'It will be stored by macOS SSH in Keychain.', flush=True)
        # OpenSSH reads the passphrase from the terminal. It is never put in
        # arguments, installer state, environment variables or captured output.
        subprocess.run([tools['ssh-keygen'], '-t', 'ed25519', '-a', '64', '-f', str(key),
                        '-C', 'relevance-lab:' + username], check=True)
    check = subprocess.run([tools['ssh-keygen'], '-y', '-P', '', '-f', str(key)],
                           capture_output=True, timeout=15)
    if check.returncode == 0:
        raise ValueError('The lab key has no passphrase. Add one with ssh-keygen -p -f '
                         + shlex.quote(str(key)) + ', then rerun setup. The existing key was retained.')
    if key.stat().st_mode & 0o077:
        raise ValueError('The lab private key must be readable only by its owner (chmod 600).')
    public = key.with_suffix('.pub').read_text(encoding='utf-8').strip()
    normal = public_key('local ' + public)
    details = subprocess.run([tools['ssh-keygen'], '-l', '-E', 'sha256', '-f', str(key)],
                             capture_output=True, text=True, check=True, timeout=15).stdout
    if fingerprint(normal) not in details.split():
        raise ValueError('The existing lab public and private keys do not match.')
    return normal


def user_api(account, path, method='GET', body=None):
    # Bootstrap uses the named user's existing local endpoint, not a service
    # account key. Redirects must not forward credentials to another host.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    auth = base64.b64encode((account['username'] + ':' + account['gitea_password']).encode()).decode()
    request = urllib.request.Request(API_URL + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError('Named Gitea account request failed (HTTP ' + str(error.code) + '). '
                         'No password or existing key was changed.') from None


def register(account, uid, key):
    user = user_api(account, '/user')
    if user['login'] != account['username']:
        raise ValueError('Gitea authenticated a different account.')
    title = 'relevance-lab-' + uid
    for page in range(1, 21):
        rows = user_api(account, '/user/keys?limit=50&page=' + str(page))
        for row in rows:
            if ' '.join(row['key'].split()[:2]) == key:
                return row['id']
            if row['title'] == title:
                raise ValueError('This lab key title already identifies another key; nothing was replaced.')
        if len(rows) < 50:
            return user_api(account, '/user/keys', 'POST',
                            {'title': title, 'key': key, 'read_only': False})['id']
    raise ValueError('Too many existing Gitea keys to reconcile automatically.')


def configuration(paths, uid, mac=True):
    def quoted(path):
        value = path.as_posix()
        if any(c in value for c in ('"', '\n', '\r')):
            raise ValueError('Unsupported quote or newline in SSH path.')
        return '"' + value + '"'
    text = ('# Managed by relevance-lab; existing user settings are retained.\n'
            'Host ' + ALIAS + ' gitea.localhost\n'
            '  HostName 127.0.0.1\n  User git\n  Port ' + str(HOST_PORT) + '\n'
            '  IdentityFile ' + quoted(paths['key']) + '\n'
            '  IdentitiesOnly yes\n  StrictHostKeyChecking yes\n'
            '  ProxyCommand none\n  ProxyJump none\n'
            '  HostKeyAlias relevance-lab-' + uid + '\n'
            '  UserKnownHostsFile ' + quoted(paths['known_hosts']) + '\n'
            '  AddKeysToAgent yes\n')
    if mac:
        text += '  UseKeychain yes\n'
    # Reset matching before returning to the user's original global settings.
    return (text + 'Host *\n').encode()


def configure(home, paths, uid, host_key):
    retain(paths['known_hosts'], ('relevance-lab-' + uid + ' ' + host_key + '\n').encode())
    retain(paths['config'], configuration(paths, uid))
    config = Path(home) / '.ssh' / 'config'
    safe_path(config)
    before = config.read_bytes() if config.exists() else b''
    include = ('Include "' + paths['config'].as_posix() + '"\n').encode()
    if include.rstrip() in before.splitlines():
        return
    if re.search(rb'^\s*Host\s+[^\r\n]*\b(?:relevance-lab-gitea|gitea\.localhost)\b', before, re.M | re.I):
        raise ValueError('The SSH alias already has user settings; nothing was replaced.')
    if before:
        retain(paths['directory'] / ('config-before-' + hashlib.sha256(before).hexdigest()), before)
    temporary = config.with_name('config.relevance-lab.tmp')
    retain(temporary, include + before)
    current = config.read_bytes() if config.exists() else b''
    if current != before:
        raise ValueError('SSH configuration changed during setup; user edits were retained.')
    safe_path(config)
    temporary.replace(config)


def load_key(paths, tools, public):
    # Apple's client stores/reuses the passphrase using its native Keychain API.
    loaded = subprocess.run([tools['ssh-add'], '-l', '-E', 'sha256'],
                            capture_output=True, text=True, timeout=15)
    if loaded.returncode == 0 and fingerprint(public) in loaded.stdout.split():
        return
    subprocess.run([tools['ssh-add'], '--apple-use-keychain', str(paths['key'])], check=True)


def verify(tools):
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('GIT_SSH', 'GIT_SSH_COMMAND', 'GIT_SSH_VARIANT')}
    environment['GIT_TERMINAL_PROMPT'] = '0'
    result = subprocess.run([tools['git'], '-c', 'core.sshCommand=' + tools['ssh'] +
                             ' -o BatchMode=yes -o ConnectTimeout=10', 'ls-remote',
                             ALIAS + ':elastic-agent/delivery-source.git', 'HEAD'],
                            env=environment,
                            capture_output=True, text=True, timeout=30)
    if result.returncode or not re.fullmatch(r'[0-9a-f]{40}\s+HEAD\s*', result.stdout):
        raise ValueError('SSH Git verification failed. Check the SSH agent/Keychain and rerun setup. '
                         'Existing keys and server evidence were retained.')
    print('Verified password-free Git access to delivery-source over SSH.', flush=True)
    return result.stdout.split()[0]
