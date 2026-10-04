"""Move the installed Gitea outbound allowlist to its supported configuration section."""
import json

import yaml
from common import HELM, STATE, guard, k, run


def install():
    guard()
    values = json.loads(run([HELM, 'get', 'values', 'gitea', '-n', 'platform',
        '--kubeconfig', str(STATE / 'kubeconfig.yaml'), '-o', 'json']).stdout)
    config = values['gitea']['config']
    webhook = config.get('webhook', {})
    previous = webhook.get('ALLOWED_HOST_LIST')
    if previous is None:
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
    print('Gitea uses security.ALLOWED_HOST_LIST with the existing allowlist.')


if __name__ == '__main__':
    install()
