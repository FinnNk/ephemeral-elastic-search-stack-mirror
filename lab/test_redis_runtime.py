"""Optional real Redis verification; creates and removes its own Docker container."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from data_versions import PAIRS
import install_redis


@unittest.skipUnless(os.environ.get('LAB_VERIFY_REDIS') == '1', 'Explicit Docker verification only')
class RedisRuntime(unittest.TestCase):
    def test_seed_read_permissions_and_dependency_fallback(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent / 'search-app'))
        import redis
        import rewrite_lookup
        resources = []
        def manifest(_kind, digest):
            pair = next(pair for pair in PAIRS.values() if pair['inputs']['catalogue'] == digest)
            return {'content': {'sha256': pair['rewrite']['catalogue_sha256']}}
        with patch('input_selection.fetch_manifest', side_effect=manifest), \
                patch.object(install_redis, 'fetch_manifest', side_effect=manifest), \
                patch.object(install_redis, 'guard'), \
                patch.object(install_redis, 'apply', side_effect=resources.append), \
                patch.object(install_redis, 'k', return_value=SimpleNamespace(stdout='')):
            install_redis.install()
        deployment = next(row for row in resources if row['kind'] == 'Deployment')
        container = deployment['spec']['template']['spec']['containers'][0]
        secret = next(row['stringData'] for row in resources if row['kind'] == 'Secret')
        seed = next(row['binaryData']['data.resp'] for row in resources if row['kind'] == 'ConfigMap')
        name = 'lab-redis-verification-' + uuid.uuid4().hex[:12]
        def docker(*args, **kwargs):
            return subprocess.run(['docker', *args], check=True, capture_output=True, text=True, **kwargs).stdout.strip()
        import base64
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'users.acl').write_text(secret['users.acl'])
            (root/'data.resp').write_bytes(base64.b64decode(seed))
            docker('create', '--name', name, '--memory', '96m', '--user', '999:999', '-p', '127.0.0.1::6379',
                   '-e', 'REDISCLI_AUTH=' + secret['password'], '--entrypoint', 'sh',
                   install_redis.IMAGE, '-ec', container['command'][2].replace('/auth/users.acl', '/tmp/users.acl').replace('/seed/data.resp', '/tmp/data.resp'))
            try:
                docker('cp', str(root/'users.acl'), name+':/tmp/users.acl')
                docker('cp', str(root/'data.resp'), name+':/tmp/data.resp')
                docker('start', name)
                port = int(docker('port', name, '6379').rsplit(':', 1)[1])
                client = redis.Redis(host='127.0.0.1', port=port, decode_responses=True,
                                     socket_timeout=.1, socket_connect_timeout=.1)
                pair = PAIRS['esci-gb-demo-2026-01']
                for attempt in range(40):
                    try:
                        if client.hget(pair['rewrite_redis_key'], '__manifest'): break
                    except redis.RedisError: pass
                    time.sleep(.1)
                else: self.fail('Redis seed did not become readable')
                with self.assertRaises(redis.ResponseError):
                    client.hset(pair['rewrite_redis_key'], 'unapproved', 'value')
                env = {'REWRITE_REDIS_HOST': '127.0.0.1', 'REWRITE_REDIS_KEY': pair['rewrite_redis_key'],
                       'REWRITE_CATALOGUE_SHA256': pair['rewrite']['catalogue_sha256']}
                with patch.dict(os.environ, env), patch.object(rewrite_lookup, 'client', return_value=client):
                    self.assertEqual(rewrite_lookup.lookup('Trainers'), ('running shoes', 'redis:trainers-to-running-shoes'))
                    self.assertIsNone(rewrite_lookup.lookup('unknown'))
                    with patch.dict(os.environ, {'REWRITE_CATALOGUE_SHA256': 'a'*64}):
                        self.assertIsNone(rewrite_lookup.lookup('trainers'))
                    docker('stop', '-t', '1', name)
                    self.assertIsNone(rewrite_lookup.lookup('trainers'))
            finally:
                docker('rm', '-f', name)
