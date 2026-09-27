"""Hash durable environment and comparison identities across state migration."""

import hashlib
import json
from pathlib import Path
import sqlite3
import sys


QUERIES = {
    'environments': ('SELECT id, owner, source_sha, dataset_sha256, fingerprint, '
                     'index_recipe_sha256 FROM environments ORDER BY id'),
    'comparisons': ('SELECT id, baseline_id, candidate_id, report_sha256, '
                    'report_blob FROM comparisons ORDER BY id'),
}


def digest(path):
    with sqlite3.connect(path) as database:
        rows = {name: database.execute(query).fetchall() for name, query in QUERIES.items()}
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


if __name__ == '__main__':
    print(digest(Path(sys.argv[1])))
