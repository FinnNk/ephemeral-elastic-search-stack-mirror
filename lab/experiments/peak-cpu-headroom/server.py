"""Run the pinned API with only its Elasticsearch timing method instrumented."""
from pathlib import Path
import sys

sys.path.insert(0, '/app')
import app

namespace = dict(vars(app))
exec(compile(Path('/diagnostic/search_index.py').read_text(),
             '/diagnostic/search_index.py', 'exec'), namespace)
app.Handler.search_index = namespace['search_index']
app.telemetry.configure()
server = app.SearchServer(('0.0.0.0', 8080))
try:
    server.serve_forever()
finally:
    server.server_close()
