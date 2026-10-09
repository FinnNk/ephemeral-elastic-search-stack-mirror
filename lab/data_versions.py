"""Pair named catalogue releases with immutable Redis rewrite datasets."""
from datetime import date
import hashlib
import json
from pathlib import Path

HOST = 'lab-redis.platform.svc.cluster.local'
PAIRS = json.loads(Path(__file__).with_name('paired-data.json').read_text(encoding='utf-8'))
RULES = {'trainers': ['running shoes', 'trainers-to-running-shoes'],
         'sneakers': ['running shoes', 'sneakers-to-running-shoes'],
         'earbuds': ['wireless headphones', 'earbuds-to-wireless-headphones'],
         'couch': ['sofa', 'couch-to-sofa'], 'tee': ['t shirt', 'tee-to-t-shirt'],
         'cell phone': ['mobile phone', 'cell-phone-to-mobile-phone']}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def rewrite_data(product_sha, month=0):
    """Bind every lookup value to the exact catalogue it accompanies."""
    rules = dict(RULES)
    if month >= 2:
        rules['gym shoes'] = ['running shoes', 'gym-shoes-to-running-shoes']
    if month >= 3:
        rules.pop('tee')
        rules['hoodie'] = ['hooded sweatshirt', 'hoodie-to-hooded-sweatshirt']
    return {'format': 1, 'catalogue_sha256': product_sha, 'rules': rules}


def binding(product_sha, month=0):
    """Return the shared host and content-addressed key for one paired dataset."""
    digest = hashlib.sha256(canonical(rewrite_data(product_sha, month))).hexdigest()
    return {'rewrite_dataset_sha256': digest, 'rewrite_redis_key': 'rewrite:' + digest}


def resolve_name(value):
    """Select an exact name or the most recent simulated release on/before a date."""
    from catalogue import PROFILES, RELEASES
    if value in RELEASES:
        return value
    try:
        selected = date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('Choose a configured catalogue name or an ISO date (YYYY-MM-DD).') from None
    dated = [(date.fromisoformat(profile['effective_date']), name)
             for name, profile in PROFILES['releases'].items() if profile.get('effective_date')]
    eligible = [(day, name) for day, name in dated if day <= selected]
    if not eligible:
        raise ValueError('No simulated catalogue exists on or before that date.')
    return max(eligible)[1]


def month_for(release):
    from catalogue import PROFILES
    return int(PROFILES['releases'][release].get('effective_date', '2000-00-01')[5:7])


def verified_binding(release, product_sha):
    """Prevent a named release from using another catalogue's Redis key."""
    from input_selection import DEFAULTS, fetch_manifest
    catalogue = fetch_manifest('catalogue', DEFAULTS[release]['catalogue'])
    if catalogue['content']['sha256'] != product_sha:
        raise ValueError('Redis dataset and Elasticsearch catalogue differ.')
    pair = PAIRS[release]
    if pair['inputs'] != DEFAULTS[release] or pair['rewrite']['catalogue_sha256'] != product_sha or \
            hashlib.sha256(canonical(pair['rewrite'])).hexdigest() != pair['rewrite_dataset_sha256'] or \
            pair['rewrite_redis_key'] != 'rewrite:' + pair['rewrite_dataset_sha256']:
        raise ValueError('Paired data manifest differs from its catalogue or rewrite identity.')
    return {key: pair[key] for key in ('rewrite_dataset_sha256', 'rewrite_redis_key')}


def verify_materialised(fields):
    """Verify the shared Redis seed before admitting a paired restored environment."""
    if not fields.get('rewrite_dataset_sha256'):
        return
    from common import k, IN_CLUSTER
    name = fields.get('dataset_release') or fields['release_id']
    sha = fields['dataset_sha256']
    expected = verified_binding(name, sha)
    if any(fields.get(key) != value for key, value in expected.items()):
        raise ValueError('Restored Redis binding differs from the named catalogue.')
    if IN_CLUSTER:
        import redis
        from redis.retry import Retry
        from redis.backoff import NoBackoff
        with redis.Redis(host=HOST, decode_responses=True, socket_connect_timeout=2,
                         socket_timeout=2, retry=Retry(NoBackoff(), 0)) as client:
            actual = client.hget(expected['rewrite_redis_key'], '__manifest')
    else:
        actual = k('exec', 'deployment/lab-redis', '-n', 'platform', '--', 'sh', '-c',
                   'REDISCLI_AUTH= redis-cli --raw HGET "$1" __manifest', 'sh', expected['rewrite_redis_key']).stdout.strip()
    if actual != canonical(PAIRS[name]['rewrite']).decode():
        raise ValueError('Redis dataset is absent or differs. Run the paired data installer before restoring.')


def publish_pairs():
    """Retain each named pairing immutably alongside the content-addressed inputs."""
    from blob_config import service, settings
    from data.publish import upload
    client = service()
    for name, pair in PAIRS.items():
        verified_binding(name, pair['rewrite']['catalogue_sha256'])
        payload = canonical(pair)
        upload(client, settings()[1], 'data-environments/' + name + '.json', payload,
               hashlib.sha256(payload).hexdigest(), len(payload))
