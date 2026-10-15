import hashlib
import io
import json
import unittest
import zipfile
from unittest.mock import Mock, patch

import gatling_view as view


class NativeGatlingReports(unittest.TestCase):
    def setUp(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('index.html', '<html>Gatling report</html>')
            archive.writestr('js/stats.js', 'var stats = {};')
        self.payload = stream.getvalue()
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.performance = {'kind': 'paired-api-performance', 'candidate': {
            'native_report_sha256': self.sha,
            'native_report_blob': f'runs/{self.sha}/gatling-report.zip'}}
        self.root = {'checks': [{'variant': 'ranker-a', 'evidence': {'blob': 'variant'}}]}
        self.parent = {'reports': {'performance': {'blob': 'performance'}}}
        self.operation = {'result': {'report': {'blob': 'root'}}}
        self.documents = {'root': self.root, 'variant': self.parent, 'performance': self.performance}
        self.read = patch.object(view, 'read', side_effect=lambda ref: self.documents[ref['blob']])
        self.read.start()
        self.client = Mock()
        self.client.get_blob_properties.return_value.size = len(self.payload)
        self.client.download_blob.return_value.readall.return_value = self.payload
        self.service = patch.object(view, 'service')
        self.service.start().return_value.get_blob_client.return_value = self.client
        self.addCleanup(self.read.stop)
        self.addCleanup(self.service.stop)

    def test_variant_html_assets_and_download_follow_retained_chain(self):
        body, mime, headers = view.response(self.operation, 'ranker-a', 'candidate', 'index.html')
        self.assertIn(b'Gatling report', body)
        self.assertEqual(mime, 'text/html; charset=utf-8')
        self.assertIn("connect-src 'none'", headers['Content-Security-Policy'])
        self.assertIn("form-action 'none'", headers['Content-Security-Policy'])
        self.assertEqual(view.response(self.operation, 'ranker-a', 'candidate', 'js/stats.js')[0], b'var stats = {};')
        download = view.response(self.operation, 'ranker-a', 'candidate', 'download.zip')
        self.assertEqual(download[0], self.payload)
        self.assertIn('attachment;', download[2]['Content-Disposition'])

    def test_missing_side_variant_and_asset_are_explicit(self):
        for variant, side, asset in [('other', 'candidate', 'index.html'),
                                     ('ranker-a', 'baseline', 'index.html'),
                                     ('ranker-a', 'candidate', 'absent.html')]:
            with self.subTest(variant=variant, side=side, asset=asset), self.assertRaises(view.ReportUnavailable):
                view.response(self.operation, variant, side, asset)

    def test_traversal_and_double_encoding_are_rejected(self):
        for asset in ['../secret', '%2e%2e/secret', '/index.html', 'js//stats.js',
                      'js\\stats.js', '%252e%252e/secret', 'C:/secret', 'a%00b']:
            with self.subTest(asset=asset), self.assertRaises(ValueError):
                view.response(self.operation, 'ranker-a', 'candidate', asset)

    def test_archive_hash_and_size_are_checked(self):
        self.client.download_blob.return_value.readall.return_value = b'corrupt'
        with self.assertRaisesRegex(ValueError, 'hash or size'):
            view.response(self.operation, 'ranker-a', 'candidate', 'download.zip')
        self.client.get_blob_properties.return_value.size = view.MAX_ARCHIVE + 1
        with self.assertRaisesRegex(ValueError, 'size limit'):
            view.response(self.operation, 'ranker-a', 'candidate', 'index.html')

    def test_legacy_pair_report(self):
        self.documents['root'] = self.parent
        self.assertIn(b'Gatling', view.response(self.operation, 'pair', 'candidate', 'index.html')[0])
        self.documents['root'] = self.performance
        self.assertIn(b'Gatling', view.response(self.operation, 'pair', 'candidate', 'index.html')[0])

    def test_each_evidence_document_is_verified(self):
        from delivery_gates import read
        contents = {}

        def retain(document):
            payload = json.dumps(document).encode()
            sha = hashlib.sha256(payload).hexdigest()
            name = sha + '/report.json'
            contents[name] = payload
            return {'blob': 'runs/' + name, 'sha256': sha}

        performance = retain(self.performance)
        evidence = retain({'reports': {'performance': performance}})
        root = retain({'checks': [{'variant': 'ranker-a', 'evidence': evidence}]})
        store = Mock()
        store.get_blob_client.side_effect = lambda container, name: Mock(
            download_blob=lambda: Mock(readall=lambda: contents[name]))
        with patch.object(view, 'read', side_effect=read), patch('delivery_gates.service', return_value=store):
            operation = {'result': {'report': root}}
            self.assertIn(b'Gatling', view.response(operation, 'ranker-a', 'candidate', 'index.html')[0])
            for name in contents:
                saved = contents[name]
                contents[name] = b'{}'
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'hash'):
                    view.response(operation, 'ranker-a', 'candidate', 'index.html')
                contents[name] = saved

    def test_member_size_limit_is_enforced_before_expansion(self):
        with patch.object(view, 'MAX_MEMBER', 4):
            with self.assertRaisesRegex(ValueError, 'asset exceeds'):
                view.response(self.operation, 'ranker-a', 'candidate', 'index.html')


if __name__ == '__main__':
    unittest.main()
