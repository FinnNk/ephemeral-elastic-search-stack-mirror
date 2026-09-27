"""Freeze a deterministic synthetic catalogue and verify Blob and Elasticsearch contracts."""
import base64,hashlib,json,ssl,sys,time,urllib.request,urllib.error
from common import *
sys.path.insert(0,str(STATE/'python-libs'))
from azure.core.exceptions import ResourceExistsError
from blob_config import DEMO_KEY, service, settings
def elastic(path,method='GET',body=None,user='elastic',password=None,raw=False,cluster='shared',port=19200):
    if password is None:
        data=json.loads(k('get','secret',cluster+'-es-elastic-user','-n','platform','-o','json').stdout)
        password=base64.b64decode(data['data']['elastic']).decode()
    ca=json.loads(k('get','secret',cluster+'-es-http-certs-public','-n','platform','-o','json').stdout)
    context=ssl.create_default_context(cadata=base64.b64decode(ca['data']['tls.crt']).decode());context.check_hostname=False
    data=body.encode() if raw else (None if body is None else json.dumps(body).encode())
    req=urllib.request.Request(f'https://127.0.0.1:{port}'+path,method=method,data=data,headers={'Content-Type':'application/x-ndjson' if raw else 'application/json','Authorization':'Basic '+base64.b64encode((user+':'+password).encode()).decode()})
    with urllib.request.urlopen(req,context=context,timeout=60) as r:return json.load(r)
if __name__=='__main__':
    import secrets
    guard();start=time.monotonic()
    categories=['running shoes','cotton shirt','ceramic mug','desk lamp','garden gloves','wireless headphones','linen towel','wooden toy','steel pan','leather bag']
    products=[{'product_id':f'p{i:06d}','title':f'{categories[i%10]} model {i%100}','brand':f'Brand {i%20}','category':categories[i%10],'price_minor':500+(i*37)%20000,'country':'GB','currency':'GBP','available':i%17!=0} for i in range(10000)]
    canonical='\n'.join(json.dumps(p,sort_keys=True,separators=(',',':')) for p in products)+'\n';digest=hashlib.sha256(canonical.encode()).hexdigest()
    manifest={'release':'spike-uk-v1','sha256':digest,'count':len(products),'generator':'research/platform-spike/data_contract.py','fixed_time':'2026-01-01T00:00:00Z','assumptions':['Ten equal-size synthetic categories','Deterministic modular price, availability and brand distributions','Deliberately simple diagnostic fixture; not the realistic retail release']}
    account=service(); _,container,_,_=settings()
    try:account.create_container(container)
    except ResourceExistsError:pass
    blob=account.get_blob_client(container,digest+'/products.jsonl')
    try:blob.upload_blob(canonical,overwrite=False)
    except ResourceExistsError:pass
    assert hashlib.sha256(blob.download_blob().readall()).hexdigest()==digest
    try:blob.upload_blob(b'changed',overwrite=False);raise AssertionError('Immutable create was overwritten')
    except ResourceExistsError:pass
    manifest_blob=account.get_blob_client(container,digest+'/manifest.json')
    manifest_bytes=json.dumps(manifest,sort_keys=True).encode()
    try:manifest_blob.upload_blob(manifest_bytes,overwrite=False)
    except ResourceExistsError:assert manifest_blob.download_blob().readall()==manifest_bytes
    index='spike-frozen-v1'
    elastic('/'+index,'PUT',{'settings':{'number_of_shards':1,'number_of_replicas':0},'mappings':{'properties':{'product_id':{'type':'keyword'},'title':{'type':'text'},'country':{'type':'keyword'},'currency':{'type':'keyword'}}}})
    lines=[]
    for product in products:lines.extend([json.dumps({'index':{'_id':product['product_id']}}),json.dumps(product)])
    result=elastic('/'+index+'/_bulk?refresh=true','POST','\n'.join(lines)+'\n',raw=True);assert not result['errors']
    elastic('/'+index+'/_settings','PUT',{'index.blocks.write':True})
    elastic('/spike-private-b','PUT',{'settings':{'number_of_replicas':0}})
    users={}
    for name,indices in [('spike-a',[index]),('spike-b',[index,'spike-private-b'])]:
        password=secrets.token_urlsafe(24);users[name]=password
        elastic('/_security/role/'+name,'PUT',{'indices':[{'names':indices,'privileges':['read','view_index_metadata']}]})
        elastic('/_security/user/'+name,'PUT',{'password':password,'roles':[name]})
    denied={}
    for label,path,method,body in [('other_index','/spike-private-b/_search','POST',{'query':{'match_all':{}}}),('write','/'+index+'/_doc/forbidden','PUT',{'title':'x'})]:
        try:elastic(path,method,body,user='spike-a',password=users['spike-a']);denied[label]=False
        except urllib.error.HTTPError as e:denied[label]=e.code==403
    assert all(denied.values()),denied
    found=elastic('/'+index+'/_search','POST',{'query':{'match':{'title':'running shoes'}}},user='spike-a',password=users['spike-a'])
    assert found['hits']['total']['value']==1000
    (STATE/'search-users.json').write_text(json.dumps(users),encoding='utf-8')
    record('dataset',manifest)
    record('data-contract',{'blob_roundtrip_sha256':digest,'conditional_overwrite_denied':True,'count':10000,'search_hits':1000,'es_forbidden_operations':denied,'seconds':round(time.monotonic()-start,3)})
    print('Blob round trip and conditional create passed; 10,000 products indexed; cross-index reads and writes denied.')
