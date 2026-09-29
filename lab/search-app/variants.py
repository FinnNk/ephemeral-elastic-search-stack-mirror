"""Pinned runtime ranking choices; explicit selection is for offline capture."""

from functools import lru_cache
import hashlib
import json
import os
import re


FIELDS = ('title', 'product_type', 'brand', 'description')
BASE = {'title': 4, 'product_type': 3, 'brand': 2, 'description': 1}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


@lru_cache(maxsize=8)
def configuration(raw):
    value = json.loads(raw) if raw else {'default_variant': 'default',
                                        'variants': {'default': {'field_boosts': BASE}}}
    variants = value.get('variants')
    if not isinstance(variants, dict) or not variants or value.get('default_variant') not in variants:
        raise ValueError('Exactly one named default is required in the variant configuration.')
    for name, settings in variants.items():
        boosts = settings.get('field_boosts') if isinstance(settings, dict) else None
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name) or \
                not isinstance(boosts, dict) or set(boosts) != set(FIELDS) or \
                any(type(boosts[field]) not in (int, float) or not 0 < boosts[field] <= 16
                    for field in FIELDS):
            raise ValueError('Variant names and four bounded field boosts must be explicit.')
    return value


def select(headers):
    settings = configuration(os.environ.get('SEARCH_VARIANTS_JSON', ''))
    name = headers.get('X-Lab-Variant') or settings['default_variant']
    if name not in settings['variants']:
        raise ValueError('Unknown search variant.')
    variant = settings['variants'][name]
    return name, variant, hashlib.sha256(canonical(variant)).hexdigest()
