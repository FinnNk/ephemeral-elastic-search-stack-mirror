"""Named evaluation inputs, independent of environment catalogue selection."""
import json
from pathlib import Path
from azure.core.exceptions import ResourceNotFoundError
from input_selection import DEFAULTS, fetch_manifest


def choices():
    """Offer standard suites and published curated alternatives with matching labels."""
    rows = [{'id': release + '-standard', 'release': release,
             'label': 'Standard suite · ' + release,
             'query_manifest_sha256': refs['query-suite'],
             'judgement_manifest_sha256': refs['judgement-set']}
            for release, refs in DEFAULTS.items()]
    for row in json.loads(Path(__file__).with_name('query-suites.json').read_text(encoding='utf-8')):
        try:
            catalogue = fetch_manifest('catalogue', DEFAULTS[row['release']]['catalogue'])
            queries = fetch_manifest('query-suite', row['query_manifest_sha256'])
            judgements = fetch_manifest('judgement-set', row['judgement_manifest_sha256'])
        except ResourceNotFoundError:
            continue
        if judgements['dependencies'] != {'catalogue': catalogue['content']['sha256'],
                                           'query-suite': queries['content']['sha256']}:
            raise ValueError('Named query suite has incompatible judgement inputs.')
        rows.append(row)
    return rows
