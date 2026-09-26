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


if __name__ == '__main__':
    unittest.main()
