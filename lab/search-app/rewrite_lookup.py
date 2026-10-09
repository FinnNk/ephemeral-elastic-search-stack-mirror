"""Bounded Redis lookup; unavailable or mismatched external data uses local rules."""
from functools import lru_cache
import json
import os

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry


@lru_cache(maxsize=4)
def client(host):
    """Reuse a bounded connection pool without retrying failed search dependencies."""
    return redis.Redis(host=host, port=6379, decode_responses=True,
        socket_connect_timeout=0.1, socket_timeout=0.1, max_connections=16,
        retry=Retry(NoBackoff(), 0), retry_on_error=[])


def lookup(query):
    """Read one immutable rule only when it belongs to this API's catalogue."""
    host, key, catalogue = (os.environ.get(name) for name in
        ('REWRITE_REDIS_HOST', 'REWRITE_REDIS_KEY', 'REWRITE_CATALOGUE_SHA256'))
    if not all((host, key, catalogue)):
        return None
    try:
        raw = client(host).hget(key, query.casefold())
        if not raw or len(raw) > 2048:
            return None
        row = json.loads(raw)
        if row['catalogue_sha256'] != catalogue or \
                not isinstance(row['query'], str) or not 1 <= len(row['query']) <= 150 or \
                not isinstance(row['decision'], str) or not 1 <= len(row['decision']) <= 150:
            return None
        return row['query'], 'redis:' + row['decision']
    except (redis.RedisError, OSError, ValueError, KeyError, TypeError):
        return None
