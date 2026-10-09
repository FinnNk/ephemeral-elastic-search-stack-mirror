"""Strict SemVer 2.0 parsing and source-controlled delivery versions; stdlib only."""
import re
from pathlib import Path

SEMVER = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
                    r'(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?'
                    r'(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?\Z')


def parse(value):
    """Parse a bounded SemVer, rejecting leading zeroes in numeric prereleases."""
    match = SEMVER.fullmatch(value) if isinstance(value, str) and len(value) <= 160 else None
    if not match:
        raise ValueError('Version must be valid SemVer, for example 1.2.3.')
    pre = tuple((match[4] or '').split('.')) if match[4] else ()
    if any(s.isdigit() and len(s) > 1 and s.startswith('0') for s in pre):
        raise ValueError('Numeric prerelease identifiers cannot have leading zeroes.')
    return tuple(int(match[i]) for i in (1, 2, 3)), pre, match[5]


def compare(left, right):
    """Compare SemVer precedence; build metadata never affects ordering."""
    a, ap, _ = parse(left)
    b, bp, _ = parse(right)
    if a != b:
        return (a > b) - (a < b)
    if not ap or not bp:
        return (not ap) - (not bp)
    for x, y in zip(ap, bp):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return (int(x) > int(y)) - (int(x) < int(y))
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return (x > y) - (x < y)
    return (len(ap) > len(bp)) - (len(ap) < len(bp))


def declared(root):
    """Read a reviewed normal release version, without preview or build suffixes."""
    path = Path(root) / 'VERSION'
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 64:
        raise ValueError('Add a VERSION file containing a release version, for example 1.0.0.')
    value = path.read_text(encoding='utf-8').strip()
    _, pre, metadata = parse(value)
    if pre or metadata:
        raise ValueError('VERSION must contain MAJOR.MINOR.PATCH; CI adds preview/build suffixes.')
    return value


def build_version(version, event, run, attempt, pr=None):
    """Name a published build while retaining the reviewed release version."""
    _, pre, metadata = parse(version)
    if pre or metadata or any(not str(v).isdigit() or int(v) < 1 for v in (run, attempt)):
        raise ValueError('Invalid declared version or build identity.')
    if event == 'pull_request':
        if not str(pr).isdigit() or int(pr) < 1:
            raise ValueError('A preview version requires its source PR number.')
        return f'{version}-pr.{int(pr)}.{int(run)}.{int(attempt)}'
    if event != 'push':
        raise ValueError('Only source pushes and PR builds can publish versions.')
    return f'{version}+build.{int(run)}.{int(attempt)}'


if __name__ == '__main__':
    print(declared(Path.cwd()))
