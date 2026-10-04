"""Compare ordered result lists without relevance labels."""


def jaccard(first, second):
    """Return set overlap: one for equal empty lists, zero for disjoint lists."""
    left, right = set(first), set(second)
    return len(left & right) / len(left | right) if left or right else 1.0


def rbo(first, second, persistence=0.9, depth=10):
    """Return finite extrapolated rank overlap; short lists retain their lengths."""
    if not 0 < persistence < 1 or depth < 1:
        raise ValueError('RBO needs persistence between zero and one and a positive depth.')
    first, second = first[:depth], second[:depth]
    if first == second:
        return 1.0
    if not first or not second:
        return 0.0
    # Extend a exhausted list's overlap denominator only with the longer list.
    # Missing ranks never become synthetic matching products.
    weighted = 0.0
    overlap = 0.0
    for rank in range(1, depth + 1):
        denominator = max(min(rank, len(first)), min(rank, len(second)))
        overlap = len(set(first[:rank]) & set(second[:rank])) / denominator
        weighted += (1 - persistence) * overlap * persistence ** (rank - 1)
    return weighted + overlap * persistence ** depth


def summarise(observations, baseline):
    """Return equally weighted per-query similarities for every frozen variant."""
    rows = observations['observations']
    values = {}
    for variant in observations['variants']:
        cases = {}
        for row in rows:
            first, second = row['results'][baseline]['ids'], row['results'][variant]['ids']
            cases[row['query_id']] = {
                'rbo_at_10_p_0_9': round(rbo(first, second), 6),
                'jaccard_at_10': round(jaccard(first[:10], second[:10]), 6),
                'equal_top_10': first[:10] == second[:10],
            }
        values[variant] = {
            'rbo_at_10_p_0_9': round(sum(v['rbo_at_10_p_0_9'] for v in cases.values()) / len(cases), 6),
            'jaccard_at_10': round(sum(v['jaccard_at_10'] for v in cases.values()) / len(cases), 6),
            'unchanged_queries': sum(v['equal_top_10'] for v in cases.values()),
            'query_count': len(cases), 'per_query': cases,
        }
    return values
