"""Verify additional demo inputs preserve frozen products, labels and identities."""
import json
from pathlib import Path
import tempfile
import unittest

from common import ROOT
from contracts import sha_file
from prepare_seasonal_queries import prepare, SETS


class SeasonalQueryTests(unittest.TestCase):
    def test_combined_inputs_preserve_labels_and_refuse_changed_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            source, output = Path(temporary)/'source', Path(temporary)/'output'
            source.mkdir()
            product = {'product_id':'p1','title':'control','country':'GB','currency':'GBP','price_minor':100}
            query = {'query_id':'frozen-control','query':'control','country':'GB','currency':'GBP','filters':{}}
            label = {'query_id':'frozen-control','product_id':'p1','grade':3}
            for name, record in [('products.jsonl',product),('queries.jsonl',query),('judgements.jsonl',label)]:
                (source/name).write_text(json.dumps(record)+'\n',encoding='utf-8')
            manifest={'release':'esci-gb-demo-halloween-2026','sha256':{name:sha_file(source/name) for name in
                ('products.jsonl','queries.jsonl','judgements.jsonl')}}
            (source/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            queries=ROOT/'lab/delivery/bootstrap/evaluation/queries'
            result=prepare(source,output,queries)
            self.assertEqual(result['query_count'],27)
            self.assertEqual((output/'products.jsonl').read_bytes(),(source/'products.jsonl').read_bytes())
            self.assertEqual((output/'judgements.jsonl').read_bytes(),(source/'judgements.jsonl').read_bytes())
            self.assertEqual(prepare(source,output,queries),result)
            rows=[json.loads(line) for line in (output/'queries.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len({row['query_id'] for row in rows}),27)
            self.assertEqual(rows[0],query)
            (output/'queries.jsonl').write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Retained seasonal query input differs'):
                prepare(source,output,queries)
            (source/'products.jsonl').write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Frozen seasonal input differs'):
                prepare(source,output,queries)

    def test_report_only_selection_tracks_the_available_sets(self):
        selection=json.loads((ROOT/'lab/delivery/bootstrap/examples/seasonal/selection.json').read_text(encoding='utf-8'))
        self.assertEqual(tuple(row['name'] for row in selection['additional_query_sets']),SETS)
        for row in selection['additional_query_sets']:
            self.assertFalse(row['required'])
            self.assertTrue((ROOT/'lab/delivery/bootstrap'/row['path']).exists())


if __name__ == '__main__':
    unittest.main()
