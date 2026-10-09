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
    if profile.get('simulated'):
        if profile.get('theme'):
            from demo_seasons import build_pair
            result = build_pair(STATE/'releases/esci-gb-v1', STATE/'releases/esci-gb-demo-v1',
                                STATE/'releases')[profile['theme']]
            print(json.dumps(result, indent=2))
            sys.exit(0)
        from demo_timeline import build as build_timeline
        result = build_timeline(STATE/'releases/esci-gb-demo-v1', STATE/'releases'/args.release,
                                int(profile['effective_date'][5:7]))
        print(json.dumps(result, indent=2))
        sys.exit(0)
    print(json.dumps(build(STATE/'esci-upstream',STATE/'releases'/args.release,args.release,
                           profile['queries'],profile['products'],args.download),indent=2))
