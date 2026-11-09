"""Separate, bounded, disposable last-good public benchmark cache."""
import json
import os
from pathlib import Path
import tempfile

MAX_BYTES = 2 * 1024 * 1024


class BenchmarkCache:
    def __init__(self, root):
        self.path = Path(root) / 'cache' / 'terminal-bench-4-v1.json'

    def read(self):
        try:
            with self.path.open('rb') as stream:
                data = stream.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                return None
            value = json.loads(data)
            return value if value.get('schema') == 1 else None
        except (OSError, ValueError, AttributeError, RecursionError):
            return None

    def put(self, value):
        data = json.dumps(value, allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(data) > MAX_BYTES:
            raise ValueError('benchmark_cache_size')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='benchmark-', suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
