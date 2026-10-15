"""Readable Git documents; release and evidence hashing keeps canonical bytes."""
import json


def write_json(path, value):
    """Write stable, indented UTF-8 JSON with a final Unix newline."""
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
                    encoding='utf-8', newline='\n')
