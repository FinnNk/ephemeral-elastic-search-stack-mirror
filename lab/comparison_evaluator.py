"""Own judgement resolution and frozen scoring for one captured comparison.

The SDLC supplies captured rankings and frozen input bytes. Metric calculations
stay in the pure offline scorer; this boundary owns optional API calls.
"""
from pathlib import Path
import tempfile
from offline import evaluate
from query_sets import assemble, score_extra
from additional_judgements import resolve_extra
from variant_gate import canonical, sha


def evaluate_comparison(standard_inputs, extra_observations, extra_sets, catalogue,
                        specification, standard_queries, selection, retain,
                        progress=lambda message: None, *, resolve_missing=True):
    """Use one label snapshot per suite for every variant, or reuse retained labels.

    The standard suite already has its published frozen snapshot. New additional
    suites optionally resolve their pooled gaps before freezing labels. Replaying
    a retained comparison passes those frozen suites with resolve_missing=False:
    it makes no judgement-service calls and does not acquire newer labels.
    """
    expected = {item['name'] for item in extra_sets}
    if set(extra_observations) != expected:
        raise ValueError('Captured suites differ from the selected frozen suites.')
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        for name, payload in standard_inputs.items():
            (folder / name).write_bytes(payload)
        standard = evaluate(*(folder / name for name in (
            'observations', 'judgements', 'specification', 'catalogue', 'queries', 'manifest')))
    frozen, reports = [], {}
    for item in extra_sets:
        name = item['name']
        observed = extra_observations[name]
        if resolve_missing:
            progress('Resolving judgement gaps and freezing labels: ' + name)
            item = resolve_extra(item, observed, specification, catalogue, retain)
        else:
            reference = item.get('resolved_references', {}).get('judgements')
            payload = item.get('judgement_bytes')
            if reference is None or payload is None or sha(payload) != reference['sha256'] or \
                    payload != b''.join(canonical(row) for row in item['judgements_rows']):
                raise ValueError('Recalculation requires the unchanged retained judgement snapshot.')
        reports[name] = score_extra(item, observed, specification, canonical(catalogue))
        frozen.append(item)
    return assemble(standard, reports, frozen, standard_queries, selection), frozen
