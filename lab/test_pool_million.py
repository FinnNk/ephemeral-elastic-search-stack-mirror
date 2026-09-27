import unittest

from pool_million import grade_result


class PooledGradeTest(unittest.TestCase):
    def test_all_four_grades_and_held_out_case(self):
        plan = {'kind': 'colour', 'category': 'apparel',
                'product_type': 'cotton shirt', 'value': 'blue'}
        exact = {'category': 'apparel', 'product_type': 'cotton shirt', 'colour': 'blue'}
        self.assertEqual(grade_result(plan, exact), 3)
        self.assertEqual(grade_result(plan, {**exact, 'colour': 'red'}), 2)
        self.assertEqual(grade_result(plan, {**exact, 'product_type': 'linen dress'}), 1)
        self.assertEqual(grade_result(plan, {**exact, 'category': 'garden'}), 0)
        self.assertEqual(grade_result({**plan, 'kind': 'zero'}, exact), 0)


if __name__ == '__main__':
    unittest.main()
