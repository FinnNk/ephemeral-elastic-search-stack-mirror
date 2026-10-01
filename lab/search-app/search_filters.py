"""Caller filter contract shared by the Search API and capture clients."""
import json

EXACT_FIELDS = ('category', 'colour', 'material')
MAX_PRICE = 2_147_483_647


def validate_filters(value):
    if not isinstance(value, dict) or set(value) - {*EXACT_FIELDS, 'price_minor'}:
        raise ValueError('Filters must be an object using category, colour, material or price_minor.')
    for field, selected in value.items():
        if field in EXACT_FIELDS:
            if not isinstance(selected, list) or not 1 <= len(selected) <= 20 or any(
                    not isinstance(item, str) or not item or item != item.strip() or len(item) > 128
                    for item in selected):
                raise ValueError(field + ' needs 1–20 exact, non-empty text values.')
            if len(set(selected)) != len(selected):
                raise ValueError(field + ' contains duplicate values.')
        else:
            if not isinstance(selected, dict) or not selected or set(selected) - {'gte', 'lte'} or any(
                    type(bound) is not int or not 0 <= bound <= MAX_PRICE for bound in selected.values()):
                raise ValueError('price_minor needs non-negative integer gte/lte bounds.')
            if selected.get('gte', 0) > selected.get('lte', MAX_PRICE):
                raise ValueError('price_minor gte must not exceed lte.')
    return value


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate filter key: ' + key)
        value[key] = item
    return value


def parse_filters(text):
    if len(text) > 4096:
        raise ValueError('Filter JSON exceeds 4096 characters.')
    try:
        return validate_filters(json.loads(text, object_pairs_hook=unique_object))
    except json.JSONDecodeError:
        raise ValueError('Filters must be valid JSON.') from None


def encode_filters(value):
    return json.dumps(validate_filters(value), sort_keys=True, separators=(',', ':'))


def clauses(value):
    validate_filters(value)
    return [{'terms': {field: value[field]}} for field in EXACT_FIELDS if field in value] + (
        [{'range': {'price_minor': value['price_minor']}}] if 'price_minor' in value else [])


def matches(product, value):
    """Use the same membership rules in the disconnected synthetic demo."""
    validate_filters(value)
    if any(product.get(field) not in selected for field, selected in value.items() if field in EXACT_FIELDS):
        return False
    bounds = value.get('price_minor', {})
    return bounds.get('gte', 0) <= product['price_minor'] <= bounds.get('lte', MAX_PRICE)
