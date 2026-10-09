"""Paired restore selection and simulated membership changes keep data consistent."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

from common import ROOT
sys.path.insert(0,str(ROOT/'data'))
from demo_timeline import build
from contracts import canonical, validate_records, input_files
import data_versions as versions


class Timeline(unittest.TestCase):
    def test_names_dates_and_membership_with_unchanged_labels(self):
        self.assertEqual(versions.resolve_name('2026-02-15'),'esci-gb-demo-2026-02')
        self.assertEqual(versions.resolve_name('2026-03-01'),'esci-gb-demo-2026-03')
        self.assertEqual(versions.resolve_name('esci-gb-v1'),'esci-gb-v1')
        with self.assertRaises(ValueError): versions.resolve_name('2025-12-31')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'base';source.mkdir()
            products=[{'product_id':str(i),'title':'Product '+str(i),'country':'GB','currency':'GBP','price_minor':100} for i in range(100)]
            (source/'products.jsonl.gz').write_bytes(gzip.compress(b''.join(canonical(row) for row in products),mtime=0))
            (source/'queries.jsonl').write_bytes(canonical({'query_id':'q','query':'product','country':'GB','currency':'GBP'}))
            (source/'judgements.jsonl').write_bytes(b''.join(canonical({'query_id':'q','product_id':str(i),'grade':2}) for i in range(100)))
            (source/'manifest.json').write_bytes(b'{}')
            memberships=[]
            for month,count in ((1,80),(2,90),(3,85)):
                folder=root/str(month); manifest=build(source,folder,month)
                self.assertEqual(manifest['count'],count)
                self.assertEqual((folder/'products.jsonl.gz').read_bytes()[9],255)
                self.assertEqual(build(source,folder,month),manifest)
                counts=validate_records(input_files(folder)); self.assertEqual(counts['judgement-set'],count)
                memberships.append({json.loads(line)['product_id'] for line in gzip.decompress((folder/'products.jsonl.gz').read_bytes()).splitlines()})
            self.assertTrue(memberships[0]<memberships[1])
            self.assertTrue(memberships[1]-memberships[2]); self.assertTrue(memberships[2]-memberships[1])

    def test_catalogue_and_redis_pair_cannot_be_mixed(self):
        name='esci-gb-demo-2026-01';pair=versions.PAIRS[name];sha=pair['rewrite']['catalogue_sha256']
        with patch('input_selection.fetch_manifest',return_value={'content':{'sha256':sha}}):
            self.assertEqual(versions.verified_binding(name,sha)['rewrite_redis_key'],pair['rewrite_redis_key'])
            with self.assertRaises(ValueError): versions.verified_binding(name,'a'*64)
        fields={'dataset_release':name,'dataset_sha256':sha,**versions.binding(sha,1)}
        with patch.object(versions,'verified_binding',return_value=versions.binding(sha,1)),patch('common.k',return_value=Mock(stdout='other')):
            with self.assertRaisesRegex(ValueError,'Redis dataset'): versions.verify_materialised(fields)
