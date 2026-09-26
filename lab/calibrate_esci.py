"""Reduce an ESCI-S reference sample to aggregates; never emit source records."""
import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

SAMPLE_SHA256 = 'c88659e2ed4a9c3ed16487ef27a37ae8dc95226723d6b0ed5dcbd422d587eb55'
SAMPLE_URL = 'https://media.githubusercontent.com/media/shuttie/esci-s/master/sample.json.gz'
ESCI_URL = 'https://github.com/amazon-science/esci-data'
ESCI_S_URL = 'https://github.com/shuttie/esci-s'
FIELDS = ('title', 'description', 'bullets', 'attrs', 'category', 'price', 'stars', 'ratings', 'reviews', 'info')


def present(value):
    return value is not None and value != '' and value != [] and value != {}


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def profile(sample):
    data = Path(sample).read_bytes()
    assert hashlib.sha256(data).hexdigest() == SAMPLE_SHA256, 'Reference sample changed'
    sample_count = 0
    eligible = []
    with gzip.open(sample, 'rt', encoding='utf-8') as stream:
        for line in stream:
            sample_count += 1
            row = json.loads(line)
            if row.get('locale') == 'us' and row.get('type') in ('product', 'book'):
                eligible.append(row)
    count = len(eligible)
    assert count > 0
    presence = {field: round(100 * sum(present(row.get(field)) for row in eligible) / count, 1)
                for field in FIELDS}
    text_lengths = {}
    for field in ('title', 'description'):
        lengths = [len(row[field]) for row in eligible if isinstance(row.get(field), str) and row[field]]
        text_lengths[field] = {'p50': percentile(lengths, .5), 'p90': percentile(lengths, .9)}
    list_lengths = {}
    for field in ('bullets', 'attrs', 'category'):
        lengths = [len(row[field]) for row in eligible if isinstance(row.get(field), (list, dict))]
        list_lengths[field] = {'p50': percentile(lengths, .5), 'p90': percentile(lengths, .9)}
    templates = Counter(row.get('template') for row in eligible)
    return {
        'profile_id': 'esci-informed-uk-v1',
        'reference_only': True,
        'sources': {'esci_s': ESCI_S_URL, 'esci': ESCI_URL, 'sample': SAMPLE_URL,
                    'sample_sha256': SAMPLE_SHA256},
        'sample': {'all_rows': sample_count, 'english_product_or_book_rows': count,
                   'filter': 'locale=us and type in {product, book}',
                   'field_presence_percent': presence,
                   'text_characters': text_lengths,
                   'collection_entries': list_lengths,
                   'top_templates': [{'name': name, 'count': n} for name, n in templates.most_common(10)]},
        'published_full_dataset': {
            'products': 1661908,
            'top_template_share_percent': {
                'apparel': 15.06, 'kitchen': 8.33, 'home': 5.86,
                'home_improvement': 5.28, 'sports': 5.24, 'book': 5.12,
                'beauty': 4.68, 'shoes': 4.41, 'health_and_beauty': 4.39, 'toy': 4.39,
            },
            'unlisted_template_share_percent': 37.24,
        },
        'published_esci': {'large_query_count': 130652, 'large_judgement_count': 2621288,
                           'average_judgements_per_query': 20.06,
                           'labels': ['E', 'S', 'C', 'I']},
        'generator_decisions': {
            'market': {'country': 'GB', 'locale': 'en-GB', 'currency': 'GBP'},
            'content': 'Generate all product text, IDs, brands and queries; copy no source records.',
            'categories': 'Use published template shares as a starting distribution, with an explicitly modelled UK retail remainder.',
            'fields': 'Model text lengths, optional metadata and category depth from the English reference aggregates; generate GBP prices and availability independently.',
            'judgements': 'Generate synthetic graded E/S/C/I-style labels with about 20 assessed products per query; never treat unjudged results as irrelevant.',
            'versioning': 'Apply only to a new release profile; retain retail-gb-10k-v1 byte for byte.',
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('lab/profiles/esci-informed-uk-v1.json'))
    args = parser.parse_args()
    result = profile(args.sample)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'Wrote aggregate profile from {result["sample"]["english_product_or_book_rows"]} English product/book rows')


if __name__ == '__main__':
    main()
