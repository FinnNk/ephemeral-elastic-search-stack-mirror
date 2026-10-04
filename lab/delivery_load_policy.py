"""Require completed normal and sustained-peak load before production deployment."""
import hashlib
import json
from pathlib import Path

from compare_gatling import BUDGETS, measure_phase

PROFILE = 'production-load'
RECIPE = Path(__file__).with_name('traffic') / 'production-load-v1.json'


def validate(report):
    """Check both runs against the trusted recipe and absolute performance budgets."""
    payload = RECIPE.read_bytes()
    if report.get('profile') != PROFILE or report.get('recipe_sha256') != hashlib.sha256(payload).hexdigest():
        raise ValueError('Production requires fresh production-load evidence from the pinned recipe.')
    phases = json.loads(payload)['profiles'][PROFILE]
    if set(report.get('measured_phases', {})) != {'normal', 'peak'}:
        raise ValueError('Production requires measured normal and sustained-peak phases.')
    for side in ('baseline', 'candidate'):
        run = report[side]
        if (run.get('profile') != PROFILE or run.get('recipe_sha256') != report['recipe_sha256'] or
                not run.get('complete') or not run.get('valid') or
                not run.get('arrival', {}).get('valid') or
                run.get('duration_seconds') != sum(p['seconds'] for p in phases)):
            raise ValueError('Production load run is incomplete or uses a different recipe.')
        for phase in phases:
            metrics = run.get('phases', {}).get(phase['name'], {})
            if (metrics.get('planned_seconds') != phase['seconds'] or
                    metrics.get('requests') != phase['seconds'] * phase['rate'] or
                    metrics.get('offered_rps') != phase['rate']):
                raise ValueError('Production load phase duration, arrivals or rate differs.')
            if phase['name'] == 'warmup':
                if metrics.get('failed') != 0:
                    raise ValueError('Production warmup failed.')
            elif not measure_phase(metrics, BUDGETS[phase['name']])['within_budget']:
                raise ValueError('Production load phase missed its latency or error budget.')
