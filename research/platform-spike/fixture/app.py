"""Small real Elasticsearch-backed search surface for the delivery spike."""
import base64,json,os,ssl,time,urllib.parse,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
NORMALISE=False

def query_body(query):
    if NORMALISE:query=query.replace('trainers','running shoes')
    return {'size':10,'query':{'match':{'title':query}},'sort':[{'_score':'desc'},{'product_id':'asc'}]}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        start=time.monotonic()
        if self.path=='/health':return self.reply(200,{'ready':True})
        parsed=urllib.parse.urlparse(self.path)
        if parsed.path!='/search':return self.reply(404,{'error':'not found'})
        params=urllib.parse.parse_qs(parsed.query)
        if params.get('country',['GB'])[0]!='GB' or params.get('currency',['GBP'])[0]!='GBP':return self.reply(400,{'error':'unsupported market'})
        query=params.get('q',[''])[0]
        auth=base64.b64encode((os.environ['ES_USER']+':'+os.environ['ES_PASSWORD']).encode()).decode()
        req=urllib.request.Request(os.environ['ES_URL']+'/'+os.environ['ES_INDEX']+'/_search',data=json.dumps(query_body(query)).encode(),headers={'Content-Type':'application/json','Authorization':'Basic '+auth})
        try:
            with urllib.request.urlopen(req,context=ssl.create_default_context(cafile='/es-ca/tls.crt'),timeout=10) as r:result=json.load(r)
            self.reply(200,{'query':query,'ids':[h['_id'] for h in result['hits']['hits']],'index':os.environ['ES_INDEX'],'normalise':NORMALISE,'elapsed_ms':round((time.monotonic()-start)*1000,3)})
        except Exception as error:self.reply(502,{'error':type(error).__name__})
    def reply(self,status,value):
        body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body)
if __name__=='__main__':ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
