"""Compare the analyser variant through the APIs, then remove its owned resources."""
import json, time
from common import *
from environments import *
from measure import search, wait_search, remove

guard()
name='spike-analyser';index='spike-analyser-v2'
image=json.loads((EVIDENCE/'baseline-build.json').read_text())['image']
start=time.monotonic()
provision_access(name,index);definition=define(name,image,index);publish('Compare dedicated analyser index')
wait_search(name)
baseline=search('spike-baseline','model');candidate=search(name,'model')
assert len(baseline['ids'])==10 and candidate['ids']==[]
created=round(time.monotonic()-start,3)
start=time.monotonic();remove(name);elastic('/'+index,'DELETE')
record('index-api-comparison',{'definition':definition,'baseline_ids':baseline['ids'],'candidate_ids':candidate['ids'],
    'query':'model','create_seconds':created,'delete_including_index_seconds':round(time.monotonic()-start,3),
    'namespace_and_dedicated_index_removed':True,'sample_size':1})
print('Analyser API comparison and dedicated-index cleanup passed.')
