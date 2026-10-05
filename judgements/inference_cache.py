"""Retain successful inference attempts separately from label acceptance."""

import json
import re
from datetime import datetime, timezone

from core import canonical, digest


def validate_identity(identity):
    """Require the runtime and input protocol used to produce reusable scores."""
    if not isinstance(identity, dict) or set(identity) != {
            'runtime_image', 'protocol_sha256', 'input_contract'} or \
            identity['input_contract'] != 'judgement-pair-v1' or \
            not re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', identity['runtime_image']) or \
            not re.fullmatch('[0-9a-f]{64}', identity['protocol_sha256']):
        raise ValueError('Inference identity requires a pinned image, protocol digest and input contract.')
    return identity


class InferenceCache:
    """Append attempts; ordinary lookups reuse the first successful outcome."""

    def __init__(self, database, model, identity, rubric):
        self.database, self.model = database, model
        self.identity = validate_identity(identity)
        self.rubric = rubric
        database.execute('''CREATE TABLE IF NOT EXISTS inference_attempts (
            sequence INTEGER PRIMARY KEY, cache_key TEXT NOT NULL,
            attempt_sha256 TEXT NOT NULL UNIQUE, record TEXT NOT NULL)''')
        database.execute('CREATE INDEX IF NOT EXISTS inference_key '
                         'ON inference_attempts(cache_key,sequence)')

    def key(self, pair):
        return digest(canonical({'input': pair, 'model': self.model,
                                 'inference': self.identity, 'rubric': self.rubric}))

    def get(self, pair):
        row = self.database.execute('SELECT record,attempt_sha256 FROM inference_attempts '
            'WHERE cache_key=? ORDER BY sequence LIMIT 1', (self.key(pair),)).fetchone()
        return {**json.loads(row[0]), 'attempt_sha256': row[1]} if row else None

    def append(self, pair, prediction):
        if prediction.get('outcome') not in ('labelled', 'abstain'):
            raise ValueError('Only successful predictions or abstentions are reusable.')
        if prediction['outcome'] == 'labelled' and prediction.get('label') not in ('E', 'S', 'C', 'I'):
            raise ValueError('Prediction has an invalid ESCI label.')
        if 'probabilities' in prediction:
            from esci.contract import probabilities
            probabilities(prediction['probabilities'])
        record = {'cache_key': self.key(pair), 'model': self.model,
                  'rubric': self.rubric,
                  'inference': self.identity, 'input_sha256': digest(canonical(pair)),
                  'recorded_at': datetime.now(timezone.utc).isoformat(),
                  'prediction': prediction}
        payload = canonical(record)
        identity = digest(payload)
        self.database.execute('INSERT INTO inference_attempts '
            '(cache_key,attempt_sha256,record) VALUES (?,?,?)',
            (record['cache_key'], identity, payload.decode()))
        return {**record, 'attempt_sha256': identity}
