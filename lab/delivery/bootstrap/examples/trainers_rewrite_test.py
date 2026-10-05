# Copy this method into the SearchContract class in app/test_app.py.
# It is already indented by four spaces: paste it after an existing method,
# before the final `if __name__ == '__main__':` block, not inside another method.
# It checks the rewrite and the Elasticsearch request; it does not prove that
# the returned products are more relevant. Use a lab comparison for that.
    def test_trainers_query_rewrite(self):
        self.assertEqual(app.understand('Trainers'),
                         ('running shoes', 'trainers-to-running-shoes'))
        body = app.query_body('trainers', 'GB', 'GBP')
        self.assertEqual(body['query']['bool']['must'][0]['multi_match']['query'],
                         'running shoes')
