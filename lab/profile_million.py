"""Sample generated product shape without reading the full compressed release."""
import bisect
import json
import random
import statistics

from release_million import category_ranges, product_at


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def measure(sample_size=20_000):
    ranges = category_ranges(1_000_000)
    ends = [row['start'] + row['count'] for row in ranges]
    rng = random.Random(20260927)
    records = []
    for _ in range(sample_size):
        number = rng.randrange(1_000_000)
        category = ranges[bisect.bisect_right(ends, number)]
        records.append(product_at(category, number - category['start']))
    def lengths(field):
        values = [len(row[field]) for row in records if row.get(field)]
        return {'present_percent': round(len(values) / sample_size * 100, 2),
                'p50': percentile(values, .5), 'p90': percentile(values, .9)}
    return {'sample_size': sample_size, 'seed': 20260927,
            'title': lengths('title'), 'description': lengths('description'),
            'bullets': lengths('bullets'), 'attrs': lengths('attrs'),
            'category_path': lengths('category_path'),
            'available_percent': round(sum(row['available'] for row in records) / sample_size * 100, 2),
            'price_minor_p50': statistics.median(row['price_minor'] for row in records)}


if __name__ == '__main__':
    print(json.dumps(measure(), indent=2))
