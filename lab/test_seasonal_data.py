"""Seasonal membership, shared controls and event rewrites remain reproducible."""
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

from common import ROOT
sys.path.insert(0, str(ROOT/'data'))
from contracts import canonical, input_files, rows, validate_records
from demo_seasons import build_pair
from data_versions import rewrite_data, resolve_name


class SeasonalData(unittest.TestCase):
    def test_shared_controls_event_membership_and_unmodified_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); base=root/'base'; full=root/'full'
            base.mkdir(); full.mkdir()
            ordinary=[{'product_id':'B-control-'+str(i),'title':'Ordinary shirt '+str(i),
                       'country':'GB','currency':'GBP','price_minor':100} for i in range(10)]
            events=[{**ordinary[0],'product_id':'B-'+theme+'-'+str(i),'title':theme+' decorations '+str(i)}
                    for theme in ('Halloween','Christmas') for i in range(4)]
            labels=[{'query_id':'q','product_id':row['product_id'],'grade':2} for row in ordinary]
            for path, products in ((base,ordinary),(full,ordinary+events)):
                (path/'manifest.json').write_bytes(b'{}')
                (path/'products.jsonl.gz').write_bytes(gzip.compress(b''.join(canonical(row) for row in products),mtime=0))
            (base/'queries.jsonl').write_bytes(canonical({'query_id':'q','query':'shirt','country':'GB','currency':'GBP'}))
            (base/'judgements.jsonl').write_bytes(b''.join(canonical(row) for row in labels))
            results=build_pair(full,base,root/'output',themed_count=3,common_count=5)
            self.assertEqual(results,build_pair(full,base,root/'output',themed_count=3,common_count=5))
            memberships=[]
            for theme,manifest in results.items():
                path=root/'output'/manifest['release']
                counts=validate_records(input_files(path))
                self.assertEqual(counts,{'catalogue':8,'query-suite':5,'judgement-set':5})
                products=list(rows(path/'products.jsonl.gz'))
                memberships.append({row['product_id'] for row in products})
                themed=[row for row in products if not row['product_id'].startswith('B-control')]
                self.assertEqual(len(themed),3)
                self.assertTrue(all(theme in row['title'].casefold() for row in themed))
                self.assertTrue(all(row in labels for row in rows(path/'judgements.jsonl')))
                self.assertEqual((path/'products.jsonl.gz').read_bytes()[9],255)
                original_queries=(path/'queries.jsonl').read_bytes()
                (path/'queries.jsonl').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'Retained seasonal file'):
                    build_pair(full,base,root/'output',themed_count=3,common_count=5)
                (path/'queries.jsonl').write_bytes(original_queries)
            self.assertEqual(len(memberships[0]&memberships[1]),5)

    def test_date_and_redis_lookup_select_the_event(self):
        for theme,date in [('halloween','2026-10-31'),('christmas','2026-12-24')]:
            self.assertEqual(resolve_name(date),f'esci-gb-demo-{theme}-2026')
            data=rewrite_data('a'*64,10,theme)
            self.assertEqual(data['rules']['seasonal decorations'][0],theme+' decorations')
        with self.assertRaises(ValueError): rewrite_data('a'*64,0,'unknown')
