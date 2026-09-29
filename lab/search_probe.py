"""Read a Search API response from the lab cluster."""
import json
import urllib.parse
import urllib.request

from common import IN_CLUSTER, k
from operation_telemetry import inject


def search(name,query='running shoes',request_id=None):
    url='http://search.'+name+'.svc.cluster.local:8080/search?country=GB&currency=GBP&q='+urllib.parse.quote(query)
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
