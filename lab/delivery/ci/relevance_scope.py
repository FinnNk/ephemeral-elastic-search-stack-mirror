"""Classify a complete Git raw diff using the protected branch's allowlist."""

import re

DOCUMENTATION = frozenset({'README.md', 'gate/README.md'})


def classify(payload):
    if not payload:
        return {'documentation_only': False, 'files': [], 'reason': 'No changed files.'}
    fields = payload.split(b'\0')
    if fields[-1] != b'' or len(fields) % 2 != 1:
        raise ValueError('Expected a complete NUL-delimited Git raw diff.')
    files = []
    documentation_only = True
    for offset in range(0, len(fields) - 1, 2):
        header = re.fullmatch(rb':([0-7]{6}) ([0-7]{6}) [0-9a-f]{40} [0-9a-f]{40} ([AMDTU])',
                              fields[offset])
        if header is None or not fields[offset + 1]:
            raise ValueError('Unexpected Git diff record; evaluation is required.')
        path = fields[offset + 1].decode('utf-8', errors='surrogateescape')
        files.append(path)
        old_mode, new_mode, status = header.groups()
        documentation_only &= (path in DOCUMENTATION and status in (b'A', b'M', b'D')
                               and old_mode in (b'000000', b'100644')
                               and new_mode in (b'000000', b'100644'))
    return {'documentation_only': bool(documentation_only), 'files': files,
            'reason': 'Documentation-only change; evaluation not required.' if documentation_only
            else 'Change can affect search behaviour; evaluation is required.'}
