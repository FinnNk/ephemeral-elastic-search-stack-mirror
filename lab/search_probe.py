"""Read a Search API response from the lab cluster."""
import json
import urllib.parse
import urllib.request

from common import IN_CLUSTER, k
from operation_telemetry import inject
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / 'search-app'))
from search_filters import encode_filters, parse_filters


def search(name,query='running shoes',request_id=None,filters=None,country='GB',currency='GBP'):
    params = {'q': query, 'country': country, 'currency': currency,
              'filters': encode_filters(filters if filters is not None else {})}
    url='http://search.'+name+'.svc.cluster.local:8080/search?'+urllib.parse.urlencode(params)
    if request_id is not None:
        url+='&diagnostics=1&request_id='+urllib.parse.quote(request_id)
    if IN_CLUSTER:
        try:
            headers = {}
            inject(headers)
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=3) as response:
                return json.load(response)
        except (OSError,ValueError):
            return None
    code='import urllib.request; print(urllib.request.urlopen('+repr(url)+',timeout=3).read().decode())'
    r=k('exec','search-probe','-n','platform','--','python','-c',code,check=False)
    if r.returncode:return None
    return json.loads(r.stdout)
