# Copy this method inside SearchContract in app/test_app.py.
# Paste it alongside the existing methods, not inside another method.
# Keep the four-space indentation and add it only once.
    def test_sneakers_query_rewrite(self):
        # Check the rewrite decision and the query sent to Elasticsearch.
        # Relevance is assessed separately by the lab comparison.
        self.assertEqual(
            app.understand('Sneakers'),
            ('running shoes', 'sneakers-to-running-shoes'),
        )
        body = app.query_body('sneakers', 'GB', 'GBP')
        self.assertEqual(
            body['query']['bool']['must'][0]['multi_match']['query'],
            'running shoes',
        )
