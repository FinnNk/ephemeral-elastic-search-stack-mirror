"""Require the trusted relevance workflow after its accepted revision is on main."""

from common import ROOT
from delivery_provider import SOURCE, api, endpoint, git


def install():
    git(SOURCE, 'fetch', 'origin', 'main')
    files = {
        '.github/workflows/relevance.yaml': ROOT / 'lab/delivery/workflows/relevance.yaml',
        '.github/workflows/release.yaml': ROOT / 'lab/delivery/workflows/release.yaml',
        '.github/workflows/delivery.yaml': ROOT / 'lab/delivery/workflows/delivery.yaml',
        'ci/lab_delivery.py': ROOT / 'lab/delivery/ci/lab_delivery.py',
        'gate/evaluation.json': ROOT / 'lab/delivery/bootstrap/gate/evaluation.json',
        'ci/relevance_scope.py': ROOT / 'lab/delivery/ci/relevance_scope.py',
        'ci/relevance_gate.py': ROOT / 'lab/delivery/ci/relevance_gate.py',
        'ci/variant_gate_store.py': ROOT / 'lab/delivery/ci/variant_gate_store.py',
        'ci/variant_gate.py': ROOT / 'lab/variant_gate.py',
        'gate/policy.json': ROOT / 'lab/delivery/policies/variant-merge-v1.json',
    }
    for name, expected in files.items():
        try:
            deployed = git(SOURCE, 'show', 'origin/main:' + name)
        except RuntimeError:
            raise ValueError('Merge the accepted gate implementation into delivery-source main first: ' + name) from None
        if deployed != expected.read_text(encoding='utf-8').strip():
            raise ValueError('Merge the accepted gate implementation into delivery-source main first: ' + name)
    rules = api(endpoint(SOURCE, '/branch_protections'))
    current = next((rule for rule in rules if rule.get('rule_name', rule.get('branch_name')) == 'main'), None)
    contexts = list(dict.fromkeys([*(current or {}).get('status_check_contexts', []),
                                  'Reference release CI / release (pull_request)',
                                  'Offline relevance gate / relevance (pull_request_target)',
                                  'relevance-lab/merge-gate']))
    rule = {**(current or {}), 'branch_name': 'main', 'rule_name': 'main',
            'enable_push': False, 'enable_force_push': False,
            'enable_status_check': True, 'status_check_contexts': contexts,
            'required_approvals': (current or {}).get('required_approvals', 0),
            'block_on_rejected_reviews': True, 'block_on_outdated_branch': True,
            'dismiss_stale_approvals': True, 'block_admin_merge_override': True}
    api(endpoint(SOURCE, '/branch_protections' + ('/main' if current else '')),
        'PATCH' if current else 'POST', rule)
    print('delivery-source main requires build checks and the trusted offline relevance gate; '
          f"required approvals: {rule['required_approvals']}.")


if __name__ == '__main__':
    install()
