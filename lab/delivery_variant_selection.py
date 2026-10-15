"""Resolve the exact source commit's selectable variants for delivery checks."""
import hashlib
import json
import re
import importlib.util
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def source_selection(source_sha):
    """Load immutable per-variant intents and configurations from one source commit."""
    from delivery_source_comparison import source_bytes

    selection_bytes = source_bytes('gate/selection.json', source_sha)
    layout_bytes = source_bytes('gate/evaluation.json', source_sha)
    selection, layout = json.loads(selection_bytes), json.loads(layout_bytes)
    if not isinstance(selection, dict) or not isinstance(layout, dict):
        raise ValueError('The merged source variant files must contain JSON objects.')
    from query_sets import declarations
    extra_sets = declarations(selection)
    choices = selection.get('selected')
    if not isinstance(choices, list) or not choices or any(not isinstance(item, dict) for item in choices):
        raise ValueError('The merged source must select at least one candidate variant.')
    names = [item.get('variant') for item in choices]
    if len(names) != len(set(names)) or any(not isinstance(name, str) or
            not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name) for name in names):
        raise ValueError('The merged source has invalid or duplicate selected variants.')
    if any(item.get('intent') not in ('ranking-change', 'preserve-results') for item in choices):
        raise ValueError('Every selected variant needs its own supported change intent.')
    default = layout.get('default_variant')
    baseline = layout.get('baseline_variant')
    if default not in names or not isinstance(baseline, str) or baseline in names:
        raise ValueError('The source must select its default candidate and name a separate comparison baseline.')

    variants = {}
    for name in names:
        value = json.loads(source_bytes('configurations/' + name + '.json', source_sha))
        settings = value.get('variants', {}).get(name)
        if not isinstance(settings, dict):
            raise ValueError('Configuration for selected variant ' + name + ' is missing.')
        variants[name] = settings
    config = {'default_variant': default, 'variants': variants}
    return {'source_sha': source_sha, 'selection': choices, 'selection_sha256': sha(selection_bytes),
            'evaluation_sha256': sha(layout_bytes), 'configuration': config,
            'additional_query_sets': extra_sets,
            'configuration_sha256': sha(canonical(config)), 'baseline_variant': baseline,
            'configuration_sha256_by_variant': {name: sha(canonical(value))
                                                 for name, value in variants.items()}}


def configured_baseline(deployment):
    """Identify the currently deployed API's default variant and exact config."""
    raw = deployment['fields'].get('variant_config_json')
    if raw:
        config = json.loads(raw)
        name = config['default_variant']
        settings = config['variants'][name]
    else:
        # This is the search API's documented built-in configuration.
        module_path = Path(__file__).resolve().parent / 'search-app' / 'variants.py'
        spec = importlib.util.spec_from_file_location('delivery_default_variants', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        BASE = module.BASE
        name, settings = 'default', {'field_boosts': BASE}
    return {'build_run': deployment['build_run'], 'deployment_fingerprint': deployment['fingerprint'],
            'variant': name, 'configuration_sha256': sha(canonical(settings)), 'settings': settings}


def selection_summary(source_sha):
    """Expose a release's immutable declared intents without inventing missing values."""
    if not source_sha:
        return {'state': 'not-selected', 'variants': []}
    try:
        selected = source_selection(source_sha)
        return {'state': 'ready', 'source_sha': source_sha,
            'selection_sha256': selected['selection_sha256'],
            'variants': [{'variant': row['variant'], 'intent': row['intent'],
                'configuration_sha256': selected.get('configuration_sha256_by_variant', {}).get(row['variant']),
                'default': row['variant'] == selected['configuration']['default_variant']}
                for row in selected['selection']]}
    except (RuntimeError, OSError, ValueError, KeyError, TypeError):
        return {'state': 'unavailable', 'source_sha': source_sha, 'variants': []}


def with_variant(deployment, name, settings):
    """Pin one named setting as the API default for a pair comparison preview."""
    from delivery_runtime import fingerprint
    fields = dict(deployment['fields'])
    fields['variant_config_json'] = canonical({'default_variant': name,
        'variants': {name: settings}}).decode()
    return {'fields': fields, 'fingerprint': fingerprint(fields), 'build_run': deployment['build_run']}
