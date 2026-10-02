"""Keep dashboard coverage tied to the whole frozen recall pool."""

import unittest

from telemetry import Telemetry


class Gauge:
    def __init__(self):
        self.values = []

    def set(self, value, attributes):
        self.values.append((value, attributes))


class Counter:
    def __init__(self):
        self.values = []

    def add(self, value, attributes):
        if any(item is None for item in attributes.values()):
            raise TypeError('OTLP attributes cannot contain null.')
        self.values.append((value, attributes))


class TelemetryTests(unittest.TestCase):
    def test_abstention_and_label_are_both_counted_with_exportable_attributes(self):
        telemetry = Telemetry()
        telemetry.predictions = Counter()
        telemetry.count_predictions('2', [
            {'outcome': 'abstain', 'label': None},
            {'outcome': 'labelled', 'label': 'E'},
        ], 12)
        self.assertEqual(len(telemetry.predictions.values), 2)
        self.assertEqual([attrs['lab.model.label']
                          for _, attrs in telemetry.predictions.values], ['none', 'E'])


    def test_pool_coverage_includes_stored_and_new_model_labels(self):
        telemetry = Telemetry()
        telemetry.coverage = Gauge()
        telemetry.record_coverage('2', {'required': 10, 'stored': 4,
                                         'newly_labelled': 1, 'abstained': 5})
        self.assertEqual(telemetry.coverage.values,
                         [(50, {'lab.model.version': '2'})])
        telemetry.record_coverage('2', {'required': 0, 'stored': 0,
                                         'newly_labelled': 0})
        self.assertEqual(len(telemetry.coverage.values), 1)


if __name__ == '__main__':
    unittest.main()
