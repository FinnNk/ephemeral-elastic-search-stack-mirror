"""Read-only HTML view of a retained executed notebook; never execute its cells."""
import base64
from html import escape
import json
from urllib.parse import quote

import mistune

CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
STYLE = """
:root{font-family:system-ui,sans-serif;color:#17313a;background:#f4f6f4}
*{box-sizing:border-box}body{margin:0}main{max-width:1040px;margin:auto;padding:2rem 1rem}
a{color:#006e63}nav{display:flex;gap:1.5rem;flex-wrap:wrap}.meta{color:#4e6267;overflow-wrap:anywhere}
.cell{background:white;border:1px solid #d7e0dd;border-radius:10px;padding:1.25rem;margin:1rem 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6f4;padding:1rem;border-radius:6px}
code{font-family:ui-monospace,monospace}summary{cursor:pointer;font-weight:600}
img{max-width:100%;height:auto}table{border-collapse:collapse;display:block;overflow:auto}
th,td{padding:.5rem;border:1px solid #d7e0dd;text-align:left}.output{margin-top:1rem}
"""


def text(value):
    """Notebook text fields can be strings or lists of lines."""
    return ''.join(value) if isinstance(value, list) else str(value or '')


def render(payload, comparison_id, receipt):
    """Render verified saved bytes, escaping code and using only inert output types."""
    notebook = json.loads(payload)
    markdown = mistune.create_markdown(escape=True, plugins=['table'])
    identifier = quote(comparison_id, safe='')
    name = escape(receipt.get('source', 'Executed notebook'))
    pieces = ['<!doctype html><html lang="en-GB"><head><meta charset="utf-8">',
              '<meta name="viewport" content="width=device-width,initial-scale=1">',
              '<title>' + name + '</title><style>' + STYLE + '</style></head><body><main>',
              '<nav><a href="/?comparison=' + identifier + '">Back to comparison</a>',
              '<a href="/api/comparisons/' + identifier + '/notebook" download="' + name + '">Download executed notebook</a></nav>',
              '<h1>' + name + '</h1><p>Saved notebook · read only. These outputs were produced by the completed comparison; opening this page does not run the cells.</p>',
              '<details class="meta"><summary>Saved notebook identity</summary><p>SHA-256: ' + escape(receipt['executed_sha256']) + '</p></details>']
    for cell in notebook.get('cells', []):
        pieces.append('<section class="cell">')
        source = text(cell.get('source', ''))
        if cell.get('cell_type') == 'markdown':
            pieces.append(markdown(source))
        elif cell.get('cell_type') == 'code':
            count = cell.get('execution_count')
            pieces.append('<details><summary>Code' + (' · cell ' + escape(str(count)) if count is not None else '') + '</summary><pre><code>' + escape(source) + '</code></pre></details>')
            for output in cell.get('outputs', []):
                pieces.append('<div class="output">')
                kind = output.get('output_type')
                if kind == 'stream':
                    pieces.append('<pre>' + escape(text(output.get('text'))) + '</pre>')
                elif kind == 'error':
                    pieces.append('<pre>' + escape(output.get('ename', 'Error') + ': ' + output.get('evalue', '')) + '</pre>')
                else:
                    data = output.get('data', {})
                    image_type = next((mime for mime in ('image/png', 'image/jpeg') if mime in data), None)
                    if image_type:
                        image = base64.b64encode(base64.b64decode(text(data[image_type]), validate=True)).decode('ascii')
                        pieces.append('<img alt="Saved notebook figure" src="data:' + image_type + ';base64,' + image + '">')
                    elif 'text/markdown' in data:
                        pieces.append(markdown(text(data['text/markdown'])))
                    elif 'text/plain' in data:
                        pieces.append('<pre>' + escape(text(data['text/plain'])) + '</pre>')
                    else:
                        pieces.append('<p>This rich output is not available in the browser view. Inspect it in the downloaded notebook.</p>')
                pieces.append('</div>')
        else:
            pieces.append('<pre>' + escape(source) + '</pre>')
        pieces.append('</section>')
    pieces.append('</main></body></html>')
    return ''.join(pieces).encode('utf-8')
