"""An ordinary stack reconciliation must not replace an installed model."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import setup_judgement_stack as stack


class BootstrapModelGuardTests(unittest.TestCase):
    def test_missing_model_allows_bootstrap(self):
        with patch.object(stack, 'k', return_value=SimpleNamespace(returncode=1)):
            stack.guard_bootstrap_model()

    def test_replacement_is_rejected_before_setup_mutates_the_cluster(self):
        service = {'spec': {'predictor': {'model': {
            'storageUri': 'mlflow-registry://synthetic-esci-judge/2?sha256=' + 'a' * 64,
            'runtime': 'esci-v3-abcd'}}}}
        with patch.object(stack, 'guard'), patch.object(stack, 'k', return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(service))), patch.object(stack, 'configure_network') as network:
            with self.assertRaisesRegex(ValueError, 'replacement judgement model'):
                stack.install()
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
