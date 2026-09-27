"""Stream a wholly synthetic, ESCI-informed UK million-product release."""
import gzip
import hashlib
import json
import math
import os
import random
from pathlib import Path

RELEASE = 'retail-gb-1m-v1'
SEED = 20260927
FIXED_TIME = '2026-01-01T00:00:00Z'
PROFILE = Path(__file__).with_name('profiles') / 'esci-informed-uk-v1.json'

# Published ESCI-S template shares are only category-shape references. The
# remaining 37.24% is allocated to five named synthetic UK departments.
CATEGORIES = (
    ('apparel', 1506, ('cotton shirt', 'linen dress', 'denim jeans', 'wool jumper', 'rain jacket')),
    ('beauty', 468, ('face moisturiser', 'shampoo', 'hand cream', 'body wash', 'sunscreen')),
    ('books', 512, ('cookbook', 'travel guide', 'children storybook', 'gardening book', 'crime novel')),
    ('wellness', 439, ('vitamin tablets', 'first aid kit', 'sleep mask', 'heat pad', 'electric toothbrush')),
    ('home', 586, ('desk lamp', 'cotton bedding', 'bath towel', 'storage basket', 'throw blanket')),
    ('home improvement', 528, ('cordless drill', 'paint brush', 'tool box', 'wall shelf', 'work gloves')),
    ('kitchen', 833, ('steel saucepan', 'ceramic mug', 'cutlery set', 'chopping board', 'glass storage jar')),
    ('footwear', 441, ('running shoes', 'walking boots', 'sandals', 'slippers', 'leather shoes')),
    ('sports', 524, ('yoga mat', 'football', 'water bottle', 'resistance bands', 'running shorts')),
    ('toys', 439, ('wooden puzzle', 'building blocks', 'plush bear', 'craft kit', 'toy train')),
    ('electronics', 1000, ('wireless headphones', 'bluetooth speaker', 'tablet', 'smart watch', 'usb c charger')),
    ('grocery', 850, ('breakfast oats', 'ground coffee', 'herbal tea', 'pasta sauce', 'olive oil')),
    ('garden', 650, ('garden gloves', 'watering can', 'plant pot', 'pruning shears', 'solar lights')),
    ('pets', 600, ('dog lead', 'cat toy', 'pet bowl', 'bird feeder', 'pet blanket')),
    ('stationery', 624, ('notebook', 'ballpoint pens', 'desk organiser', 'sketch pad', 'sticky notes')),
)
assert sum(row[1] for row in CATEGORIES) == 10000
BRANDS = ('Alder', 'Harbour', 'Linden', 'Vela')
COLOURS = ('black', 'blue', 'green', 'grey', 'red', 'white')
MATERIALS = ('cotton', 'recycled', 'premium', 'lightweight')
FEATURES = ('durable', 'compact', 'comfortable', 'versatile', 'easy-care', 'everyday')


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def category_ranges(count):
    shares = [count * row[1] // 10000 for row in CATEGORIES]
    remainder = count - sum(shares)
    order = sorted(range(len(CATEGORIES)),
                   key=lambda i: (-(count * CATEGORIES[i][1] % 10000), i))
    for index in order[:remainder]:
        shares[index] += 1
    start = 0
    result = []
    for category, share in zip(CATEGORIES, shares):
        result.append({'name': category[0], 'types': category[2], 'share_bp': category[1],
                       'start': start, 'count': share})
        start += share
    assert start == count
    return result


def stretch(seed, target):
    if not seed or target <= 0:
        return ''
    repeated = (seed * math.ceil(target / len(seed)))[:target]
    return repeated.rsplit(' ', 1)[0] if len(repeated) == target else repeated


def product_at(category, local_id):
    rng = random.Random(SEED + category['start'] * 37 + local_id)
    product_type = category['types'][local_id % len(category['types'])]
    brand = BRANDS[(local_id // len(category['types'])) % len(BRANDS)]
    colour = COLOURS[rng.randrange(len(COLOURS))]
    material = MATERIALS[rng.randrange(len(MATERIALS))]
    feature = FEATURES[rng.randrange(len(FEATURES))]
    variant = 1 + local_id // (len(category['types']) * len(BRANDS))
    short_title = f'{brand} {colour} {product_type} {variant} | {material} {feature} UK edition. '
    title_target = 70 + rng.randrange(55) if rng.random() < .80 else 130 + rng.randrange(80)
    title = stretch(short_title, title_target).strip(' |.')
    price_base = 900 + (category['share_bp'] % 17) * 450
    price = max(199, min(150000, round(rng.lognormvariate(math.log(price_base), .65) / 25) * 25))
    description = None
    if rng.random() < .834:
        point = rng.random()
        length = (800 + int(point * 1600) if point < .5 else
                  1600 + int((point - .5) * 5250) if point < .9 else
                  3700 + int((point - .9) * 8000))
        prose = (f'{brand} {product_type} in {colour} is made for everyday UK use. '
                 f'The {material} finish and {feature} form suit home, travel and gifting. '
                 f'Explore dimensions, care instructions and practical details before choosing a variant. ')
        description = stretch(prose, length)
    row = {'product_id': f"gb-{category['start'] + local_id:07d}",
           'sku': f"{category['name'][:3].upper()}-{local_id:07d}",
           'title': title, 'description': description, 'brand': brand,
           'category': category['name'], 'product_type': product_type,
           'colour': colour, 'material': material, 'price_minor': price,
           'available': rng.random() >= .07, 'country': 'GB', 'currency': 'GBP',
           'popularity': round(min(1., (1 + local_id) ** -.22 + rng.random() * .08), 5),
           'rating': round(2.5 + rng.random() * 2.5, 1),
           'review_count': int(rng.lognormvariate(3, 1.2))}
    if rng.random() < .848:
        count = 3 + rng.randrange(13)
        row['bullets'] = [f'{feature.capitalize()} {product_type}; {material} {colour} finish, detail {i + 1}.'
                          for i in range(count)]
    if rng.random() < .577:
        row['attrs'] = [{'name': 'property-' + str(i + 1),
                         'value': (feature, material, colour, brand, 'UK', category['name'], product_type)[i]}
                        for i in range(5 + rng.randrange(3))]
    if rng.random() < .947:
        row['category_path'] = ['retail', 'UK', category['name'], product_type,
                                'assortment-' + str(1 + local_id % 5)]
    return row


def query_plans(ranges):
    type_rows = [(category, type_name) for category in ranges for type_name in category['types']]
    assert len(type_rows) == 75
    plans = []
    for index in range(1000):
        if index >= 980:
            plans.append({'query_id': f'q{index + 1:04d}',
                          'query': f'archived lunar model {index - 979}',
                          'country': 'GB', 'currency': 'GBP', 'intent': 'held-out zero result',
                          'category': type_rows[index % 75][0]['name'], 'kind': 'zero'})
            continue
        category, product_type = type_rows[index % 75]
        pattern = index // 75
        if pattern == 0:
            phrase, kind, value = product_type, 'type', None
        elif pattern <= 6:
            value = COLOURS[pattern - 1]
            phrase, kind = f'{value} {product_type}', 'colour'
        elif pattern <= 10:
            value = BRANDS[pattern - 7]
            phrase, kind = f'{value} {product_type}', 'brand'
        else:
            value = MATERIALS[pattern - 11]
            phrase, kind = f'{value} {product_type}', 'material'
        plans.append({'query_id': f'q{index + 1:04d}', 'query': phrase,
                      'country': 'GB', 'currency': 'GBP', 'intent': kind,
                      'category': category['name'], 'product_type': product_type,
                      'kind': kind, 'value': value})
    assert len({row['query'] for row in plans}) == 1000
    return plans


def judgement_rows(plans, ranges):
    by_name = {category['name']: category for category in ranges}
    for plan in plans:
        category = by_name[plan['category']]
        seen = set()
        if plan['kind'] == 'zero':
            other = ranges[(ranges.index(category) + 1) % len(ranges)]
            for offset in range(20):
                product = product_at(other, offset)
                yield {'query_id': plan['query_id'], 'product_id': product['product_id'],
                       'grade': 0, 'assessment': 'I'}
            continue
        start = int(plan['query_id'][1:]) * 97 % category['count']
        exact, substitute, complement = [], [], []
        for step in range(category['count']):
            product = product_at(category, (start + step) % category['count'])
            if product['product_id'] in seen or not product['available']:
                continue
            if product['product_type'] == plan['product_type']:
                matches = (plan['kind'] == 'type' or product[plan['kind']] == plan['value'])
                if matches and len(exact) < 12:
                    exact.append(product['product_id'])
                elif len(exact) + len(substitute) < 16:
                    substitute.append(product['product_id'])
            elif len(complement) < 2:
                complement.append(product['product_id'])
            seen.add(product['product_id'])
            if len(exact) + len(substitute) == 16 and len(complement) == 2:
                break
        if (len(exact) + len(substitute), len(complement)) != (16, 2):
            raise ValueError(f"Could not build graded pool for {plan['query_id']}: "
                             f'{len(exact)}/{len(substitute)}/{len(complement)}')
        other = ranges[(ranges.index(category) + 1) % len(ranges)]
        irrelevant = [product_at(other, offset)['product_id'] for offset in (0, 1)]
        for grade, label, ids in ((3, 'E', exact), (2, 'S', substitute),
                                  (1, 'C', complement), (0, 'I', irrelevant)):
            for product_id in ids:
                yield {'query_id': plan['query_id'], 'product_id': product_id,
                       'grade': grade, 'assessment': label}


def write_jsonl(path, rows):
    with path.open('xb') as output:
        count = 0
        for row in rows:
            output.write((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode())
            count += 1
    return count


def build(output, count=1_000_000, release=RELEASE):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    profile_sha = sha_file(PROFILE)
    generator_sha = sha_file(__file__)
    manifest_path = output / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if (manifest['release'], manifest['count'], manifest['profile_sha256'],
                manifest['generator_sha256']) != (release, count, profile_sha, generator_sha):
            raise ValueError('Existing frozen release has different inputs.')
        if any(sha_file(output / name) != digest for name, digest in manifest['sha256'].items()):
            raise ValueError('Existing frozen release bytes differ from its manifest.')
        return manifest
    if any((output / name).exists() for name in
           ('products.jsonl.gz', 'queries.jsonl', 'judgements.jsonl')):
        raise ValueError('Incomplete release directory; inspect it before retrying.')
    ranges = category_ranges(count)
    temporary = output / 'products.jsonl.gz.tmp'
    with temporary.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=6) as zipped:
            for category in ranges:
                for local_id in range(category['count']):
                    row = product_at(category, local_id)
                    zipped.write((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode())
    os.replace(temporary, output / 'products.jsonl.gz')
    plans = query_plans(ranges)
    write_jsonl(output / 'queries.jsonl', plans)
    judgement_count = write_jsonl(output / 'judgements.jsonl', judgement_rows(plans, ranges))
    assert judgement_count == 20_000
    files = ('products.jsonl.gz', 'queries.jsonl', 'judgements.jsonl')
    manifest = {'release': release, 'count': count, 'query_count': len(plans),
                'judgement_count': judgement_count, 'seed': SEED, 'fixed_time': FIXED_TIME,
                'country': 'GB', 'currency': 'GBP', 'locale': 'en-GB',
                'profile_id': 'esci-informed-uk-v1', 'profile_sha256': profile_sha,
                'generator_sha256': generator_sha,
                'categories': {row['name']: row['count'] for row in ranges},
                'compression': 'gzip',
                'sha256': {name: sha_file(output / name) for name in files},
                'bytes': {name: (output / name).stat().st_size for name in files},
                'assumptions': [
                    'All records and judgements are synthetic; ESCI aggregates inform only the shape.',
                    'Published top template shares total 62.76%; five modelled UK departments fill the remainder.',
                    'Text length/presence bands approximate sample aggregates with generated repetitive prose.',
                    'GBP price, stock, popularity, ratings and review counts are independent synthetic assumptions.',
                    'Each query has a 20-product rule-based E/S/C/I pool; unjudged products remain unknown.',
                    'Twenty held-out phrases have no intended match and twenty explicit irrelevant assessments.',
                ]}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='.lab/releases/' + RELEASE)
    parser.add_argument('--count', type=int, default=1_000_000)
    parser.add_argument('--release', default=RELEASE)
    args = parser.parse_args()
    print(json.dumps(build(args.output, count=args.count, release=args.release), indent=2))
