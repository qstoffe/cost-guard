"""Legacy cache demand bookkeeping; the Web host never ages out history."""
import time

from src.cache.database import CacheDatabase
from src.cache.lifecycle import CacheLifecycle
from src.cache.session_scope import root_key


class CacheHousekeeping:
    def __init__(self, root, *, clock=time.monotonic, lifecycle=None):
        self.clock = clock
        self.touch_due = 0
        self.lifecycle = lifecycle or CacheLifecycle(CacheDatabase(root))

    def delivered(self, host, path, value):
        """Only the visible shipped UI marks this boundary; probes/API reads do not."""
        if not isinstance(value, dict) or not host.live:
            return
        if path == '/api/interest':
            return  # Interest is handled with its validated request by dispatch_http.
        result = value.get('result')
        if path.startswith('/api/jobs/') or path == '/api/data':
            if (isinstance(result, dict) and result.get('view') and not result.get('error')
                    and result.get('source', {}).get('identity') == host.dispatcher.identity):
                self.use_roots(host, (row['session_id'] for row in result.get('source', {}).get('revisions', ())))
        elif path == '/api/sessions':
            self.use_roots(host, (row['session_id'] for row in value.get('view', {}).get('session_usage', ())
                if row.get('has_summary')))
        elif path == '/api/detail' and isinstance(result, dict):
            self.use_roots(host, (row['session_id'] for row in result.get('view', {}).get('prompt_blocks', ())))

    def use_roots(self, host, ids):
        catalog = host.live.catalog
        with catalog.lock:
            roots = [root_key(catalog.roots[key].provenance, key) for key in ids if key in catalog.roots]
        self.lifecycle.note_use(roots)

    def use_watch(self, host, *, history=False):
        driver = host.live.driver if host.live else None
        frame = driver.frame if driver else None
        if frame is not None:
            cards = (*frame.active_cards, *(frame.history_cards if history else ()))
            self.use_roots(host, (card.session_id for card in cards))

    def tick(self):
        now = self.clock()
        if now >= self.touch_due:
            self.lifecycle.flush()
            self.touch_due = now + 1
