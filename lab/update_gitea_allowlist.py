"""Move the installed Gitea outbound allowlist to its supported configuration section."""
import base64
import json

import yaml
from common import HELM, STATE, guard, k, run


def remove_persisted_fallback():
    """Remove the obsolete entry left by the chart's additive INI updates."""
    # Helm renders stringData, but the API stores data. Removing a rendered
    # section can therefore leave its old data key in the generated Secret.
    secret = json.loads(k('get', 'secret/gitea-inline-config', '-n', 'platform', '-o', 'json').stdout)
    encoded = secret.get('data', {}).get('webhook')
    if encoded:
        lines = base64.b64decode(encoded).decode('utf-8').splitlines(keepends=True)
        retained = [line for line in lines if not line.lstrip().startswith('ALLOWED_HOST_LIST=')]
        if retained != lines:
            patch = [{'op': 'replace', 'path': '/data/webhook',
                      'value': base64.b64encode(''.join(retained).encode()).decode()}] if retained else [
                          {'op': 'remove', 'path': '/data/webhook'}]
            k('patch', 'secret/gitea-inline-config', '-n', 'platform', '--type=json', '-p', json.dumps(patch))
    script = r'''set -eu
path=/data/gitea/conf/app.ini
awk '/^\[/{section=$0}
     /^ALLOWED_HOST_LIST[[:space:]]*=/{value=$0; sub(/^[^=]*=[[:space:]]*/, "", value);
       if(section=="[webhook]") old=value;
       if(section=="[security]") supported=value}
     END {if(old!="" && (supported=="" || old!=supported)) exit 1}' "$path"
tmp=$(mktemp "${path}.XXXXXX")
trap 'rm -f "$tmp"' EXIT
cp -p "$path" "$tmp"
awk '/^\[/{section=$0}
     !(section=="[webhook]" && /^ALLOWED_HOST_LIST[[:space:]]*=/)' "$path" > "$tmp"
if ! cmp -s "$path" "$tmp"; then
  mv "$tmp" "$path"
  echo changed
fi
'''
    changed = k('exec', 'deployment/gitea', '-n', 'platform', '--', 'sh', '-ec', script).stdout.strip()
    if changed == 'changed':
        k('rollout', 'restart', 'deployment/gitea', '-n', 'platform')
        k('rollout', 'status', 'deployment/gitea', '-n', 'platform', '--timeout=180s')


def install():
    guard()
    values = json.loads(run([HELM, 'get', 'values', 'gitea', '-n', 'platform',
        '--kubeconfig', str(STATE / 'kubeconfig.yaml'), '-o', 'json']).stdout)
    config = values['gitea']['config']
    webhook = config.get('webhook', {})
    previous = webhook.get('ALLOWED_HOST_LIST')
    if previous is None:
        remove_persisted_fallback()
        print('Gitea already uses the supported allowlist configuration.')
        return
    security = config.setdefault('security', {})
    if security.get('ALLOWED_HOST_LIST', previous) != previous:
        raise ValueError('The two allowlists differ. Resolve their intended value before updating Gitea.')
    security['ALLOWED_HOST_LIST'] = previous
    del webhook['ALLOWED_HOST_LIST']
    if not webhook:
        config.pop('webhook', None)
    path = STATE / 'gitea-supported-settings.yaml'
    path.write_text(yaml.safe_dump(values), encoding='utf-8')
    run([HELM, 'upgrade', 'gitea', 'gitea', '--repo', 'https://dl.gitea.com/charts/',
         '--version', '12.7.0', '-n', 'platform', '-f', str(path), '--wait', '--timeout', '5m',
         '--kubeconfig', str(STATE / 'kubeconfig.yaml')])
    k('rollout', 'status', 'deployment/gitea', '-n', 'platform', '--timeout=180s')
    remove_persisted_fallback()
    print('Gitea uses security.ALLOWED_HOST_LIST with the existing allowlist.')


if __name__ == '__main__':
    install()
