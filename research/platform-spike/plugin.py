"""Minimal ApplicationSet plugin adapter for a failure-semantics spike only."""
import hmac,json,os
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+os.environ['TOKEN']):self.send_error(403);return
        if self.path!='/api/v1/getparams.execute':self.send_error(404);return
        try:
            state=json.loads(Path('/state/desired.json').read_text())
            if state.get('fail'):raise RuntimeError('injected unavailable source')
            parameters=state['environments']
            if not isinstance(parameters,list):raise ValueError('invalid desired state')
        except Exception:self.send_error(503,'Desired state unavailable');return
        result=json.dumps({'output':{'parameters':parameters}}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(result)
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
