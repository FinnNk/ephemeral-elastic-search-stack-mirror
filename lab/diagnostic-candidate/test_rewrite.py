import unittest

import app


class RewriteDiagnostic(unittest.TestCase):
    def test_trainers_rewrite_is_named(self):
        self.assertEqual(app.understand('trainers'), ('running shoes', 'trainers-to-running-shoes'))
        self.assertEqual(app.understand('cotton shirt'), ('cotton shirt', 'none'))
        self.assertEqual(app.query_body('trainers', 'GB', 'GBP')['query']['bool']['must'][0]['multi_match']['query'],
                         'running shoes')
