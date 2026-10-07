"""Import a configured ESCI catalogue; this producer runs independently of search."""
import argparse
import json
from pathlib import Path
import sys
from common import STATE
from catalogue import DEFAULT_RELEASE, PROFILES, RELEASES
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'data'))
from import_esci import build

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release',choices=RELEASES,default=DEFAULT_RELEASE)
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args()
    if args.download:
        from esci_sources import restore
        restore(STATE/'esci-upstream')
    profile=PROFILES['releases'][args.release]
    print(json.dumps(build(STATE/'esci-upstream',STATE/'releases'/args.release,args.release,
                           profile['queries'],profile['products'],args.download),indent=2))
