# Copy this method into the AppTests class in app/test_app.py.
# It checks the rewrite and the Elasticsearch request; it does not prove that
# the returned products are more relevant. Use a lab comparison for that.
def test_trainers_query_rewrite(self):
    self.assertEqual(app.understand('Trainers'),
                     ('running shoes', 'trainers-to-running-shoes'))
    body = app.query_body('trainers', 'GB', 'GBP')
    self.assertEqual(body['query']['bool']['must'][0]['multi_match']['query'],
                     'running shoes')
