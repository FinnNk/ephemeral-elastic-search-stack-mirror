"""Resolve the pooled recall set without changing existing judgements."""

import hashlib
import json

LABEL_TO_GRADE = {'I': 0, 'C': 1, 'S': 2, 'E': 3}
GRADE_TO_LABEL = {grade: label for label, grade in LABEL_TO_GRADE.items()}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def metric_depth(specification):
    names = specification.get('metrics')
    if not isinstance(names, list) or not names:
        raise ValueError('Evaluation specification has no metrics.')
    try:
        return max(int(name.split('@', 1)[1].split(':', 1)[0]) for name in names)
    except (ValueError, IndexError, AttributeError) as error:
        raise ValueError('Metric cut-off is invalid.') from error


def pool(observations, specification):
    """Return unique pairs from every variant through the deepest metric cut-off."""
    depth = metric_depth(specification)
    if depth > observations.get('captured_depth', 0):
        raise ValueError('Metric cut-off exceeds captured result depth.')
    required = {}
    variants = observations.get('variants')
    if not isinstance(variants, dict) or len(variants) < 2:
        raise ValueError('A frozen set needs at least two variants.')
    sides = {variant: set() for variant in variants}
    for row in observations.get('observations', []):
        query_id = row['query_id']
        request = row['request']
        if set(row.get('results', {})) != set(sides):
            raise ValueError('Observation does not cover every variant.')
        for side in sides:
            for product_id in row['results'][side]['ids'][:depth]:
                key = (query_id, product_id)
                sides[side].add(key)
                required[key] = {'query_id': query_id, 'product_id': product_id,
                                 'request': request}
    if not required:
        raise ValueError('Observation recall pool is empty.')
    return [required[key] for key in sorted(required)], sides


def validate_labels(rows):
    labels = {}
    for row in rows:
        key = (row['query_id'], row['product_id'])
        grade = row.get('grade')
        if key in labels or type(grade) is not int or grade not in GRADE_TO_LABEL:
            raise ValueError('Duplicate or invalid stored judgement.')
        label = row.get('label')
        if label is not None and label != GRADE_TO_LABEL[grade]:
            raise ValueError('ESCI label disagrees with its numeric grade.')
        if row.get('source') == 'model' and (not row.get('provenance') or
                type(row.get('gate_eligible')) is not bool):
            raise ValueError('Model source labels require provenance and eligibility.')
        labels[key] = dict(row)
    return labels


def selected(row, selection):
    """Keep demo authorisation separate from qualified gate eligibility."""
    if selection not in ('gate', 'exploratory', 'demo'):
        raise ValueError('Judgement selection must be gate, exploratory or demo.')
    return (selection == 'exploratory' or row.get('gate_eligible', True) or
            (selection == 'demo' and row.get('provenance', {}).get('qualification') ==
             'lab-demo-authorised'))


def resolve(observations, specification, source_rows, products, infer, batch_size=64, selection='gate'):
    """Resolve only missing pooled pairs; return frozen rows and an attempt report.

    ``infer`` accepts a list of synthetic query/product records and returns one
    outcome per input. It may return ``labelled``, ``abstain`` or ``error``.
    """
    if selection not in ('gate', 'exploratory', 'demo'):
        raise ValueError('Judgement selection must be gate, exploratory or demo.')
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError('Batch size must be positive.')
    pairs, sides = pool(observations, specification)
    labels = validate_labels(source_rows)
    labels = {key: row for key, row in labels.items()
              if selected(row, selection)}
    missing = [pair for pair in pairs
               if (pair['query_id'], pair['product_id']) not in labels]
    attempts = []
    for start in range(0, len(missing), batch_size):
        batch = missing[start:start + batch_size]
        inputs = []
        for pair in batch:
            product = products.get(pair['product_id'])
            if product is None:
                raise ValueError('Pooled product is absent from the frozen catalogue.')
            if product['country'] != pair['request']['country'] or \
                    product['currency'] != pair['request']['currency']:
                raise ValueError('Pooled product and query market differ.')
            inputs.append({**pair, 'product': product})
        try:
            outcomes = infer(inputs)
            if not isinstance(outcomes, list) or len(outcomes) != len(inputs):
                raise ValueError('Inference returned the wrong number of outcomes.')
        except Exception as error:
            outcomes = [{'outcome': 'error', 'detail': type(error).__name__}
                        for _ in inputs]
        for item, outcome in zip(inputs, outcomes):
            key = (item['query_id'], item['product_id'])
            state = outcome.get('outcome')
            receipt = {'query_id': key[0], 'product_id': key[1],
                       'input_sha256': digest(canonical(item)), 'outcome': state}
            if state == 'labelled':
                label = outcome.get('label')
                if label not in LABEL_TO_GRADE:
                    raise ValueError('Model returned an invalid ESCI label.')
                if type(outcome.get('gate_eligible')) is not bool or not outcome.get('provenance'):
                    raise ValueError('Resolved labels need provenance and explicit gate eligibility.')
                record = {key: value for key, value in outcome.items()
                          if key not in ('outcome', 'scope')}
                record.update(query_id=key[0], product_id=key[1], label=label,
                              grade=LABEL_TO_GRADE[label])
                if selected(outcome, selection):
                    labels[key] = record
                receipt.update(label=label, provenance=outcome['provenance'],
                               gate_eligible=outcome['gate_eligible'])
                if 'confidence' in outcome:
                    receipt['confidence'] = outcome['confidence']
            elif state == 'abstain':
                pass
            elif state == 'error':
                receipt['detail'] = str(outcome.get('detail', 'inference_error'))[:120]
            else:
                raise ValueError('Model returned an unknown outcome.')
            attempts.append(receipt)
    counts = {}
    for side, keys in sides.items():
        judged = sum(key in labels for key in keys)
        contributions = {}
        for key in sorted(keys & labels.keys()):
            provenance = labels[key].get('provenance', {'kind': 'published', 'source_id': 'source'})
            identity = digest(canonical(provenance))
            entry = contributions.setdefault(identity, {'provenance': provenance, 'judged': 0})
            entry['judged'] += 1
        counts[side] = {'required': len(keys), 'judged': judged,
                        'unjudged': len(keys) - judged, 'by_source': contributions}
    counts['pool'] = {'required': len(pairs),
                      'stored': len(pairs) - len(missing),
                      'newly_labelled': sum(row['outcome'] == 'labelled' for row in attempts),
                      'abstained': sum(row['outcome'] == 'abstain' for row in attempts),
                      'failed': sum(row['outcome'] == 'error' for row in attempts)}
    return [labels[key] for key in sorted(labels)], {
        'kind': 'judgement-resolution', 'schema_version': 1,
        'selection': selection,
        'observation_sha256': digest(canonical(observations)),
        'counts': counts, 'attempts': attempts}
