import unittest,app
class QueryContract(unittest.TestCase):
    def test_baseline_retains_original_query(self):
        app.NORMALISE=False
        self.assertEqual(app.query_body('trainers')['query']['match']['title'],'trainers')
    def test_candidate_rewrites_before_retrieval(self):
        app.NORMALISE=True
        self.assertEqual(app.query_body('trainers')['query']['match']['title'],'running shoes')
    def test_stable_tie_break(self):
        self.assertEqual(app.query_body('shoes')['sort'],[{'_score':'desc'},{'product_id':'asc'}])
if __name__=='__main__':unittest.main()
