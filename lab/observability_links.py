"""Public observability links belonging to this lab installation."""
import json
import re
from common import STATE


def links():
    path = STATE / 'observability-dashboards.json'
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        value = {}
    if not isinstance(value, dict):
        value = {}
    result = {}
    for name in ('search', 'model'):
        identifier = value.get(name)
        if isinstance(identifier, str) and re.fullmatch(r'[a-zA-Z0-9-]{1,80}', identifier):
            result[name + '_dashboard_url'] = 'https://signoz.localhost:34443/dashboard/' + identifier
    return result
