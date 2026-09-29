"""A bounded input-mix shift indicator for frozen evaluation runs."""

from collections import Counter
from math import log2


def query_length_bucket(query):
    words = len(query.split())
    if words <= 1:
        return '0-1'
    if words <= 3:
        return '2-3'
    if words <= 7:
        return '4-7'
    if words <= 15:
        return '8-15'
    return '16+'


def divergence(reference, observed):
    """Jensen-Shannon divergence in [0, 1]; no observed inputs means unknown."""
    if not reference or not observed:
        return None
    left = Counter(reference)
    right = Counter(observed)
    keys = set(left) | set(right)
    left_total, right_total = sum(left.values()), sum(right.values())
    score = 0.0
    for key in keys:
        p = left[key] / left_total
        q = right[key] / right_total
        midpoint = (p + q) / 2
        if p:
            score += p * log2(p / midpoint) / 2
        if q:
            score += q * log2(q / midpoint) / 2
    return round(score, 6)


def input_shift(observations, attempts):
    """Compare one-per-query frozen suite mix with model-attempt pair mix.

    This measures selection shift into the model, not model accuracy or change
    against a training distribution. The current abstaining model has neither.
    """
    queries = {row['query_id']: query_length_bucket(row['request']['query'])
               for row in observations['observations']}
    reference = list(queries.values())
    observed = [queries[row['query_id']] for row in attempts if row['query_id'] in queries]
    return {'feature': 'query_length', 'reference': 'frozen_observation_queries',
            'observed': 'model_attempt_pairs', 'reference_count': len(reference),
            'observed_count': len(observed),
            'js_divergence': divergence(reference, observed)}
