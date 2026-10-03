import importlib.util
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "support_survey", Path(__file__).with_name("support_survey.py")
)
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


class SupportSurveyTests(unittest.TestCase):
    def test_target_never_enters_its_support(self):
        rows = [
            {"query_key": "query", "query_id": "q", "product_id": str(i)}
            for i in range(20)
        ]
        support, targets = survey.support_partition(rows)
        self.assertEqual(len(support["query"]), 6)
        self.assertEqual(len(targets), 14)
        self.assertFalse(set(support["query"]) & set(targets))

    def test_references_cannot_select_supports(self):
        rows = [
            {"query_key": "query", "query_id": "q", "product_id": str(i), "label": "E"}
            for i in range(20)
        ]
        first = survey.support_partition(rows)
        for row in rows:
            row["label"] = "I"
        self.assertEqual(first, survey.support_partition(rows))

    def test_singleton_query_has_no_support(self):
        self.assertEqual(
            survey.support_partition([{"query_key": "q", "product_id": "p"}]), ({}, [])
        )

    def test_number_veto_retains_model_tokens(self):
        self.assertEqual(survey.numbers("iPhone 14 pro 256gb"), {"14", "256gb"})


if __name__ == "__main__":
    unittest.main()
