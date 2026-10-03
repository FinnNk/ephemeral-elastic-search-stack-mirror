"""Append-only judgement evidence and explicit label selection."""

import json
import math

from core import LABEL_TO_GRADE, canonical, digest


def validate(record):
    if record.get('outcome') not in ('labelled', 'abstain', 'error'):
        raise ValueError('Evidence outcome is invalid.')
    if record['outcome'] == 'labelled' and record.get('label') not in LABEL_TO_GRADE:
        raise ValueError('Evidence ESCI label is invalid.')
    if type(record.get('gate_eligible')) is not bool:
        raise ValueError('Evidence gate eligibility must be explicit.')
    provenance = record.get('provenance', {})
    if provenance.get('kind') not in ('published', 'human', 'model'):
        raise ValueError('Evidence source kind is invalid.')
    if not isinstance(provenance.get('source_id'), str) or not provenance['source_id']:
        raise ValueError('Evidence source identity is required.')
    if provenance['kind'] == 'model':
        model = provenance.get('model', {})
        if set(model) != {'name', 'version', 'artifact_sha256'} or not all(model.values()):
            raise ValueError('Model evidence needs the complete model identity.')
        if not provenance.get('pass_id') or not provenance.get('policy_sha256'):
            raise ValueError('Model evidence needs pass and policy identities.')
    confidence = record.get('confidence')
    if confidence is not None and (isinstance(confidence, bool) or
            not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or
            not 0 <= confidence <= 1):
        raise ValueError('Evidence confidence is invalid.')
    return record


class EvidenceStore:
    def __init__(self, database, scope):
        self.database, self.scope = database, scope
        database.execute("""CREATE TABLE IF NOT EXISTS evidence (
            sequence INTEGER PRIMARY KEY, scope TEXT NOT NULL,
            query_id TEXT NOT NULL, product_id TEXT NOT NULL,
            evidence_sha256 TEXT NOT NULL UNIQUE, record TEXT NOT NULL)""")
        database.execute('CREATE INDEX IF NOT EXISTS evidence_pair '
                         'ON evidence(scope,query_id,product_id)')

    def append(self, query_id, product_id, record):
        validate(record)
        full = {**record, 'scope': self.scope, 'query_id': query_id, 'product_id': product_id}
        payload = canonical(full)
        identity = digest(payload)
        self.database.execute('INSERT OR IGNORE INTO evidence '
            '(scope,query_id,product_id,evidence_sha256,record) VALUES (?,?,?,?,?)',
            (self.scope, query_id, product_id, identity, payload.decode()))
        return identity

    def records(self, query_id, product_id):
        return [{**json.loads(row[1]), 'evidence_sha256': row[0]} for row in
                self.database.execute('SELECT evidence_sha256,record FROM evidence '
                    'WHERE scope=? AND query_id=? AND product_id=? ORDER BY sequence',
                    (self.scope, query_id, product_id))]

    def select(self, query_id, product_id, selection):
        if selection not in ('gate', 'exploratory'):
            raise ValueError('Judgement selection must be gate or exploratory.')
        rows = [row for row in self.records(query_id, product_id)
                if row['outcome'] == 'labelled' and
                (selection == 'exploratory' or row['gate_eligible'])]
        # Authoritative sources win, then the earliest accepted eligible pass.
        priority = {'published': 0, 'human': 1, 'model': 2}
        rows.sort(key=lambda row: priority[row['provenance']['kind']])
        if not rows:
            return None
        row = rows[0]
        return {**row, 'grade': LABEL_TO_GRADE[row['label']],
                'source': row['provenance']['kind']}
