"""Build a deterministic, wholly synthetic UK retail release and query judgements."""
import hashlib
import json
import math
import random
from pathlib import Path

SEED = 20260926
COUNT = 10_000
RELEASE = 'retail-gb-10k-v1'
FIXED_TIME = '2026-01-01T00:00:00Z'

# name, share of catalogue, product types, synthetic brands, typical price in pence
CATEGORIES = (
    ('clothing', 25, ('cotton shirt', 'linen dress', 'denim jeans', 'wool jumper', 'rain jacket'), ('Alder', 'Mallow', 'Vela', 'Haven'), 3200),
    ('electronics', 18, ('wireless headphones', 'bluetooth speaker', 'tablet', 'smart watch', 'usb c charger'), ('Cirrus', 'Nexel', 'Pavo', 'Sora'), 8500),
    ('home', 16, ('desk lamp', 'cotton bedding', 'bath towel', 'storage basket', 'throw blanket'), ('Harbour', 'Linden', 'Rook', 'Tilia'), 3000),
    ('beauty', 12, ('face moisturiser', 'shampoo', 'hand cream', 'body wash', 'sunscreen'), ('Bloomwell', 'Cove', 'Mira', 'Petal'), 1400),
    ('footwear', 10, ('running shoes', 'walking boots', 'sandals', 'slippers', 'leather shoes'), ('Stridely', 'Trailmere', 'Velora', 'Wend'), 6400),
    ('sports', 7, ('yoga mat', 'football', 'water bottle', 'resistance bands', 'running shorts'), ('Altis', 'Fielden', 'Noro', 'Pacewell'), 2600),
    ('garden', 5, ('garden gloves', 'watering can', 'plant pot', 'pruning shears', 'solar lights'), ('Briar', 'Fernley', 'Grove', 'Orchard'), 2100),
    ('toys', 3, ('wooden puzzle', 'building blocks', 'plush bear', 'craft kit', 'toy train'), ('Acorn', 'Kite', 'Pipkin', 'Tinker'), 1900),
    ('kitchen', 3, ('steel saucepan', 'ceramic mug', 'cutlery set', 'chopping board', 'glass storage jar'), ('Bramble', 'Cairn', 'Elm', 'Sable'), 2700),
    ('books', 1, ('cookbook', 'travel guide', 'children storybook', 'gardening book', 'crime novel'), ('Beacon', 'Fable', 'Leaf', 'Morrow'), 1100),
)
COLOURS = ('black', 'blue', 'green', 'grey', 'red', 'white')
MATERIALS = ('cotton', 'recycled', 'premium', 'lightweight')


def jsonl(records):
    return ''.join(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n' for row in records).encode()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def products():
    rng = random.Random(SEED)
    rows = []
    for category, share, types, brands, typical_price in CATEGORIES:
        for local_id in range(COUNT * share // 100):
            product_type = types[local_id % len(types)]
            brand = brands[(local_id // len(types)) % len(brands)]
            colour = COLOURS[rng.randrange(len(COLOURS))]
            material = MATERIALS[rng.randrange(len(MATERIALS))]
            variant = 1 + local_id // (len(types) * len(brands) * len(COLOURS))
            price = max(199, min(50_000, round(rng.lognormvariate(math.log(typical_price), .38) / 25) * 25))
            available = rng.random() >= .07
            rows.append({
                'product_id': f'gb-{len(rows):06d}', 'sku': f'{category[:3].upper()}-{local_id:05d}',
                'title': f'{brand} {colour} {product_type} {variant}',
                'description': f'{material.capitalize()} {product_type} by {brand}. {colour.capitalize()} finish for everyday use.',
                'brand': brand, 'category': category, 'product_type': product_type,
                'colour': colour, 'material': material, 'price_minor': price,
                'available': available, 'country': 'GB', 'currency': 'GBP',
                'popularity': round(min(1.0, (1 + local_id) ** -.34 + rng.random() * .05), 4),
            })
    assert len(rows) == COUNT
    return rows


def queries_and_judgements(catalogue):
    by_category = {}
    for product in catalogue:
        if product['available']:
            by_category.setdefault(product['category'], []).append(product)
    queries, judgements = [], []
    for category, _share, types, brands, _price in CATEGORIES:
        selected_type = types[0]
        cases = (
            (selected_type, 'product type'),
            ('black ' + selected_type, 'colour and type'),
            (brands[0] + ' ' + selected_type, 'brand and type'),
            ('recycled ' + selected_type, 'material and type'),
            (types[1], 'second product type'),
        )
        for phrase, intent in cases:
            query_id = f'q{len(queries) + 1:03d}'
            queries.append({'query_id': query_id, 'query': phrase, 'country': 'GB', 'currency': 'GBP', 'intent': intent})
            type_name = types[1] if intent == 'second product type' else selected_type
            relevant = [p for p in by_category[category] if p['product_type'] == type_name]
            for product in relevant[:30]:
                grade = 3 if (
                    (intent == 'colour and type' and product['colour'] == 'black') or
                    (intent == 'brand and type' and product['brand'] == brands[0]) or
                    (intent == 'material and type' and product['material'] == 'recycled') or
                    intent in ('product type', 'second product type')
                ) else 2
                judgements.append({'query_id': query_id, 'product_id': product['product_id'], 'grade': grade})
    assert len(queries) == 50
    assert all(sum(j['query_id'] == q['query_id'] and j['grade'] == 3 for j in judgements) > 0 for q in queries)
    return queries, judgements


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    catalogue = products()
    queries, judgements = queries_and_judgements(catalogue)
    payloads = {'products.jsonl': jsonl(catalogue), 'queries.jsonl': jsonl(queries), 'judgements.jsonl': jsonl(judgements)}
    manifest = {
        'release': RELEASE, 'country': 'GB', 'currency': 'GBP', 'fixed_time': FIXED_TIME,
        'seed': SEED, 'count': len(catalogue), 'query_count': len(queries), 'judgement_count': len(judgements),
        'sha256': {name: sha256(content) for name, content in payloads.items()},
        'assumptions': [
            'All products, brands, queries, prices, popularity and judgements are synthetic.',
            'Ten categories have fixed, unequal shares; type and brand rotation makes recurring variants.',
            'Prices follow bounded category-specific log-normal distributions rounded to 25p.',
            'Availability is a seeded 7% out-of-stock sample; each product has one GB/GBP market.',
            'Query judgements are rules-based positive examples on available products, not human assessment or exhaustive negatives.',
            'Popularity is a synthetic decreasing score with seeded noise, not observed traffic.',
        ],
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    for name, content in {**payloads, 'manifest.json': manifest_bytes}.items():
        path = output / name
        if path.exists():
            assert path.read_bytes() == content, f'{path} already exists with different content'
        else:
            path.write_bytes(content)
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='.lab/releases/' + RELEASE)
    args = parser.parse_args()
    print(json.dumps(build(args.output), indent=2))
