"""Signed Gitea delivery probe. No deployment decisions are made by this receiver."""
import hashlib,hmac,json,os
from http.server import BaseHTTPRequestHandler,HTTPServer
EVENTS=[];SEEN=set()
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        expected=hmac.new(os.environ['SECRET'].encode(),body,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(self.headers.get('X-Gitea-Signature',''),expected):self.send_error(401);return
        delivery=self.headers.get('X-Gitea-Delivery','');duplicate=delivery in SEEN
        if delivery:SEEN.add(delivery)
        data=json.loads(body)
        EVENTS.append({'delivery':delivery,'event':self.headers.get('X-Gitea-Event'),'duplicate':duplicate,'body_sha256':hashlib.sha256(body).hexdigest(),'source_revision':data.get('after'),'repository':data.get('repository',{}).get('full_name')})
        self.send_response(204);self.end_headers()
    def do_GET(self):
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+os.environ['SECRET']):self.send_error(403);return
        body=json.dumps(EVENTS).encode();self.send_response(200);self.end_headers();self.wfile.write(body)
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
