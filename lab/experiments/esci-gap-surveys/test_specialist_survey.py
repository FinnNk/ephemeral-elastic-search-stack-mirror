import importlib.util
from pathlib import Path
import unittest

import numpy as np
import role_specialist_survey as roles
import project_recalibrator_gaps as projection

spec = importlib.util.spec_from_file_location(
    "specialist_survey", Path(__file__).with_name("specialist_survey.py")
)
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


class SurveyChecks(unittest.TestCase):
    def test_normalised_query_groups_cannot_split(self):
        self.assertEqual(
            survey.query_partition("iPhone Case", "seed"),
            survey.query_partition("  IPHONE-case  ", "seed"),
        )

    def test_identifiers_and_synthetic_fields_are_excluded(self):
        row = {
            "request": {"query": "iphone"},
            "product": {
                "title": "iphone case",
                "brand": "",
                "product_id": "secret-a",
                "price_minor": 999,
            },
            "base_probabilities": [0.1, 0.2, 0.6, 0.1],
        }
        before = survey.relation_features(row, categories=True, probabilities=True)
        row["product"].update(
            {"product_id": "secret-b", "price_minor": 1, "colour": "red"}
        )
        self.assertEqual(
            before, survey.relation_features(row, categories=True, probabilities=True)
        )
        self.assertEqual(before["accessory_product_only"], 1.0)

    def test_no_support_means_abstention(self):
        probabilities = np.array([[0.1, 0.1, 0.1, 0.7]])
        choices = survey.choose_thresholds(np.array([3]), probabilities)
        self.assertTrue(all(choice["threshold"] is None for choice in choices.values()))
        self.assertFalse(survey.apply_thresholds(probabilities, choices)[1].any())

    def test_zero_events_do_not_establish_zero_risk(self):
        self.assertGreater(survey.upper_binomial(0, 100), 0.0)
        self.assertIsNone(survey.upper_binomial(0, 0))

    def test_broad_accessory_department_does_not_make_phone_an_accessory(self):
        row = {
            "request": {"query": "iphone"},
            "product": {
                "title": "iphone",
                "category_path": ["Cell Phones & Accessories", "Cell Phones"],
            },
            "base_probabilities": [0.7, 0.1, 0.1, 0.1],
        }
        self.assertEqual(roles.category_role_features(row)["role_leaf_accessory"], 0.0)
        row["product"]["category_path"] = [
            "Cell Phones & Accessories",
            "Cases, Holsters & Sleeves",
            "Basic Cases",
        ]
        self.assertEqual(
            roles.category_role_features(row)["role_accessory_product_only"], 1.0
        )

    def test_projection_counts_only_selected_pairs_and_normalised_query_groups(self):
        rows = [
            {"request": {"query": query}}
            for query in ("IPHONE case", "iphone-case", "camera")
        ]
        counts = projection.selection_counts(
            rows, np.array([0, 1, 3]), np.array([True, True, False])
        )
        self.assertEqual(
            counts, {"accepted": 2, "queries": 1, "classes": {"E": 1, "S": 1}}
        )


if __name__ == "__main__":
    unittest.main()
