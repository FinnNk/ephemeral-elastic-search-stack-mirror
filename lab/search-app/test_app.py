import unittest
import app


class SearchContract(unittest.TestCase):
    def test_market_and_query_validation(self):
        self.assertEqual(app.validated_query('/search?q=+running++shoes+'), ('running shoes', 'GB', 'GBP'))
        with self.assertRaises(ValueError):
            app.validated_query('/search?q=running+shoes&country=US&currency=USD')
        with self.assertRaises(ValueError):
            app.validated_query('/search?q=')

    def test_query_filters_and_stable_sort(self):
        body = app.query_body('running shoes', 'GB', 'GBP')
        self.assertEqual(body['query']['bool']['filter'], [
            {'term': {'country': 'GB'}}, {'term': {'currency': 'GBP'}}, {'term': {'available': True}}])
        self.assertEqual(body['sort'][-1], {'product_id': 'asc'})

    def test_public_result_shape(self):
        hit = {'_id': 'gb-000001', '_source': {
            'product_id': 'gb-000001', 'title': 'Alder blue shirt', 'brand': 'Alder',
            'category': 'clothing', 'price_minor': 2500, 'currency': 'GBP', 'available': True,
            'description': 'Internal text', 'popularity': .4,
        }}
        response = app.api_response('shirt', 'GB', 'GBP', {'hits': {'total': {'value': 1}, 'hits': [hit]}}, 12.3456)
        self.assertEqual(response['ids'], ['gb-000001'])
        self.assertEqual(response['total'], 1)
        self.assertNotIn('description', response['results'][0])
        self.assertEqual(response['elapsed_ms'], 12.346)

    def test_diagnostics_do_not_change_query_or_result(self):
        self.assertEqual(app.understand('cotton shirt'), ('cotton shirt', 'none'))
        self.assertEqual(app.query_body('cotton shirt', 'GB', 'GBP')['query']['bool']['must'][0]['multi_match']['query'], 'cotton shirt')
        self.assertEqual(app.diagnostic_options('/search?q=shirt&diagnostics=1&request_id=q001-base'), 'q001-base')
        self.assertIsNone(app.diagnostic_options('/search?q=shirt'))
        with self.assertRaises(ValueError):
            app.diagnostic_options('/search?q=shirt&diagnostics=1&request_id=bad%20id')
        hit = {'_source': {'product_id': 'gb-000001'}}
        record = app.diagnostic_record(' shirt ', 'shirt', app.query_body('shirt', 'GB', 'GBP'),
                                       {'hits': {'hits': [hit]}}, 'q001-base', 12.5, 8.1)
        self.assertEqual(record['retrieved_ids'], ['gb-000001'])
        self.assertEqual(record['rewrite'], 'none')
        self.assertEqual(record['unavailable_stages'], ['reranker'])
        self.assertEqual(len(record['elasticsearch_request_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
