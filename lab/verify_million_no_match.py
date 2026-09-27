"""Check an additional frozen zero-result request against all three APIs."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, 'research/platform-spike')
from common import record
from compare_search import response

QUERY = Path(__file__).with_name('million-no-match-v1.jsonl')
NAMES = ('lab-million-baseline', 'lab-million-api', 'lab-million-index')


def main():
    payload = QUERY.read_bytes()
    rows = [json.loads(line) for line in payload.splitlines()]
    if len(rows) != 1 or rows[0]['query_id'] != 'q1001':
        raise ValueError('Expected one frozen additional request.')
    results = {name: response(name, rows[0]) for name in NAMES}
    evidence = {'suite_sha256': hashlib.sha256(payload).hexdigest(),
                'query_id': rows[0]['query_id'],
                'totals': {name: item['total'] for name, item in results.items()},
                'ids': {name: item['ids'] for name, item in results.items()}}
    if any(item['total'] != 0 or item['ids'] for item in results.values()):
        raise ValueError('Additional no-match request returned products.')
    record('million-no-match', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
