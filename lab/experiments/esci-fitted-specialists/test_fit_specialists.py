import unittest

import fit_specialists as survey
import numpy as np


class FittingContract(unittest.TestCase):
    def test_canonical_query_aliases_cannot_split(self):
        first = {"request": {"query": "PHONE &amp; case"}}
        second = {"request": {"query": " <b>ＰＨＯＮＥ</b> & case  "}}
        self.assertEqual(survey.group(first), survey.group(second))

    def test_frozen_query_key_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            survey.group({"query_key": "wrong", "request": {"query": "phone"}})

    def test_new_queries_are_wholly_disjoint(self):
        partitions = survey.split_queries({str(i) for i in range(1000)})
        self.assertEqual(sum(value == "fit" for value in partitions.values()), 700)
        self.assertEqual(
            sum(value == "calibration" for value in partitions.values()), 300
        )

    def test_labels_identifiers_and_synthetic_fields_are_not_features(self):
        row = {
            "query_id": "one",
            "label": "I",
            "request": {"query": "iphone case"},
            "product": {
                "product_id": "one",
                "title": "iphone case",
                "description": None,
                "category_path": None,
                "price_minor": 50,
                "popularity": 99,
            },
        }
        before = survey.input_features(row)
        row.update({"query_id": "two", "label": "E"})
        row["product"].update(
            {"product_id": "two", "price_minor": 999, "popularity": 0}
        )
        self.assertEqual(before, survey.input_features(row))
        self.assertIsNone(row["product"]["description"])

    def test_no_class_support_means_no_threshold(self):
        selected = survey.thresholds(
            np.array([3]), np.array([[0.01, 0.01, 0.01, 0.97]])
        )
        self.assertTrue(all(row["threshold"] is None for row in selected.values()))

    def test_zero_event_bootstrap_does_not_certify_zero_pair_risk(self):
        rows = [{"request": {"query": "a"}}, {"request": {"query": "b"}}]
        result = survey.statistics(
            rows, np.array([3, 0]), np.array([3, 0]), np.array([True, True])
        )
        self.assertIsNone(
            result["risks"]["irrelevant_to_exact"]["usable_pair_risk_upper"]
        )
        self.assertGreater(
            result["risks"]["irrelevant_to_exact"][
                "pair_independence_CP_upper_one_sided_95_descriptive_only"
            ],
            0,
        )
        self.assertIsNone(
            result["risks"]["irrelevant_to_exact"]["whole_query_bootstrap_interval_95"]
        )


if __name__ == "__main__":
    unittest.main()
