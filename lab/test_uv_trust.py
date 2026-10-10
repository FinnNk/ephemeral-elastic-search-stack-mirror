"""Exercise uv certificate verification against an isolated HTTPS package index."""
from datetime import datetime, timedelta, timezone
import http.server
import ipaddress
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from fresh_install import ca_bundle
from unittest.mock import patch


class UVTrustTests(unittest.TestCase):
    def test_managed_python_without_default_roots_uses_locked_public_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle=Path(temporary)/'public.pem'
            empty=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.assertEqual(empty.get_ca_certs(),[])
            with patch('fresh_install.ssl.create_default_context',return_value=empty):
                context=ca_bundle(bundle,None)
            self.assertGreater(len(context.get_ca_certs()),100)
            self.assertTrue(bundle.exists())

    @unittest.skipUnless(shutil.which('uv'), 'uv executable required')
    def test_uv_rejects_unknown_ca_and_accepts_combined_corporate_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Isolated corporate test CA')])
            now=datetime.now(timezone.utc)
            ca=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
                .not_valid_after(now+timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),True)
                .sign(key,hashes.SHA256()))
            server_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            leaf=(x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]))
                .issuer_name(name).public_key(server_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),False)
                .sign(key,hashes.SHA256()))
            corporate=folder/'corporate.pem';corporate.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
            (folder/'server.pem').write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
            (folder/'server.key').write_bytes(server_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
            combined=folder/'combined.pem';ca_bundle(combined,corporate)
            self.assertGreater(combined.read_bytes().count(b'BEGIN CERTIFICATE'),1)
            self.assertTrue(corporate.read_text(encoding="utf-8") in combined.read_text(encoding="utf-8"))
            requests=[]
            class Index(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    requests.append(self.path)
                    self.send_response(404);self.end_headers()
                def log_message(self,*args):
                    pass
            server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Index)
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(folder/'server.pem',folder/'server.key')
            server.socket=context.wrap_socket(server.socket,server_side=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            req=folder/'requirements.in';req.write_text('isolated-lab-trust-test-package==1.0\n',encoding='utf-8')
            command=[shutil.which('uv'),'pip','compile',str(req),'--no-config','--no-cache',
                '--index-url',f'https://127.0.0.1:{server.server_port}/simple', '--output-file',str(folder/'lock.txt')]
            env={k:v for k,v in os.environ.items() if k not in ('SSL_CERT_FILE','SSL_CERT_DIR','UV_SYSTEM_CERTS','UV_NATIVE_TLS')}
            env.update(UV_HTTP_RETRIES='0',UV_HTTP_TIMEOUT='5',NO_PROXY='127.0.0.1')
            try:
                rejected=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
                self.assertNotEqual(rejected.returncode,0)
                self.assertEqual(requests,[])
                self.assertIn('certificate',rejected.stderr.lower())
                accepted=subprocess.run(command,env={**env,'SSL_CERT_FILE':str(combined)},capture_output=True,text=True,timeout=30)
                # The package is deliberately absent. Reaching the index proves TLS succeeded.
                self.assertNotEqual(accepted.returncode,0)
                self.assertTrue(requests)
                self.assertNotIn('invalid peer certificate',accepted.stderr.lower())
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__ == '__main__':
    unittest.main()
