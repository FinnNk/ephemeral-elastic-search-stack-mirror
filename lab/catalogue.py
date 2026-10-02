"""Current catalogue profiles; demo size changes require a new frozen release ID."""
import json
from pathlib import Path

PROFILES = json.loads(Path(__file__).with_name('catalogue-profiles.json').read_text(encoding='utf-8'))
DEFAULT_RELEASE = PROFILES['default']
RELEASES = tuple(PROFILES['releases'])
