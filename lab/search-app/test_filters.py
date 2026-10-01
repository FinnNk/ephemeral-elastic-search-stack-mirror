"""Public HTTP filtering, including rejected requests and empty matches."""
import json
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import app
from demo import DemoHandler
from search_filters import clauses, parse_filters, validate_filters


class FilterContract(unittest.TestCase):
    def test_invalid_filters_are_rejected(self):
        for value in (None, [], {'brand': ['Alder']}, {'category': []},
                      {'category': 'home'}, {'colour': ['black', 'black']},
                      {'material': [' cotton']}, {'price_minor': {}},
                      {'price_minor': {'gte': True}}, {'price_minor': {'lte': 1.5}},
                      {'price_minor': {'gte': -1}}, {'price_minor': {'gte': 5, 'lte': 4}},
                      {'price_minor': {'gt': 10}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_filters(value)
        for text in ('', 'not-json', '{"category":["home"],"category":["clothing"]}',
                     '{"price_minor":{"gte":1,"gte":2}}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_filters(text)

    def test_filter_clauses_do_not_enter_scoring_or_override_scope(self):
        filters = {'category': ['home', 'footwear'], 'price_minor': {'gte': 1200, 'lte': 6500}}
        plain = app.query_body('shoes', 'GB', 'GBP')
        filtered = app.query_body('shoes', 'GB', 'GBP', filters=filters)
        self.assertEqual(plain['query']['bool']['must'], filtered['query']['bool']['must'])
        self.assertEqual(filtered['query']['bool']['filter'],
                         plain['query']['bool']['filter'] + clauses(filters))
        self.assertEqual(plain['sort'], filtered['sort'])

    def test_http_demo_applies_filters_and_echoes_them(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), DemoHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}/search?'
        try:
            cases = [({'category': ['footwear'], 'price_minor': {'lte': 6500}}, ['demo-01']),
                     ({'price_minor': {'gte': 7900, 'lte': 7900}}, ['demo-02']),
                     ({'category': ['home']}, []),
                     ({'colour': ['black'], 'material': ['cotton']}, ['demo-01', 'demo-02']),
                     ({}, ['demo-01', 'demo-02'])]
            for filters, expected in cases:
                with self.subTest(filters=filters):
                    url = base + urllib.parse.urlencode({'q': 'running shoes', 'filters': json.dumps(filters)})
                    with urllib.request.urlopen(url) as response:
                        value = json.load(response)
                    self.assertEqual(value['ids'], expected)
                    self.assertEqual(value['total'], len(expected))
                    self.assertEqual(value['filters'], filters)
            with patch.object(DemoHandler, 'search_index', side_effect=AssertionError('Must not search')):
                for suffix in ('filters=null', 'filters=%7B%22available%22%3Afalse%7D',
                               'filters=%7B%7D&filters=%7B%7D', 'filters='):
                    with self.subTest(suffix=suffix), self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(base + 'q=shoes&' + suffix)
                    self.assertEqual(error.exception.code, 400)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
