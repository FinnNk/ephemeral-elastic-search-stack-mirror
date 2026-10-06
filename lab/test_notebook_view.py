"""Saved notebook content stays readable without executing code or rich scripts."""
import json
import unittest

from notebook_view import render, CSP


class NotebookViewTests(unittest.TestCase):
    def test_saved_cells_outputs_and_identity_are_rendered(self):
        payload = json.dumps({'cells': [
            {'cell_type': 'markdown', 'source': ['# Analysis\n', '**Saved** results']},
            {'cell_type': 'code', 'execution_count': 3, 'source': ['raise RuntimeError("do not run")'],
             'outputs': [{'output_type': 'stream', 'text': ['Queries in report: 50\n']},
                         {'output_type': 'display_data', 'data': {'text/plain': ['Result: 1']}}]}]}).encode()
        page = render(payload, 'comparison-1', {'source': 'example.ipynb', 'executed_sha256': 'a'*64}).decode()
        self.assertIn('<h1>Analysis</h1>', page)
        self.assertIn('<strong>Saved</strong>', page)
        self.assertIn('Queries in report: 50', page)
        self.assertIn('raise RuntimeError', page)
        self.assertIn('Result: 1', page)
        self.assertIn('a'*64, page)
        self.assertIn('/api/comparisons/comparison-1/notebook', page)

    def test_notebook_markup_and_code_do_not_become_active_html(self):
        payload = json.dumps({'cells': [
            {'cell_type': 'markdown', 'source': '<script>alert(1)</script>'},
            {'cell_type': 'code', 'source': '<img src=x onerror=alert(1)>', 'outputs': [
                {'output_type': 'display_data', 'data': {'text/html': '<script>alert(2)</script>', 'text/plain': '<script>alert(3)</script>'}},
                {'output_type': 'display_data', 'data': {'application/javascript': 'alert(4)'}}]}]}).encode()
        page = render(payload, 'id', {'source': '<unsafe>', 'executed_sha256': 'b'*64}).decode()
        self.assertNotIn('<script>', page)
        self.assertNotIn('<img src=x', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('not available in the browser view', page)
        self.assertIn("default-src 'none'", CSP)
        self.assertNotIn('script-src', CSP)

    def test_saved_png_is_embedded_and_invalid_data_is_rejected(self):
        payload = {'cells': [{'cell_type': 'code', 'outputs': [{'output_type': 'display_data', 'data': {'image/png': 'YWJj'}}]}]}
        receipt = {'source': 'plot.ipynb', 'executed_sha256': 'c'*64}
        self.assertIn('data:image/png;base64,YWJj', render(json.dumps(payload).encode(), 'id', receipt).decode())
        payload['cells'][0]['outputs'][0]['data']['image/png'] = '<bad>'
        with self.assertRaises(ValueError):
            render(json.dumps(payload).encode(), 'id', receipt)


if __name__ == '__main__':
    unittest.main()
