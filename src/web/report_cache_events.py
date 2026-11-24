"""Version hints for finite report frames, published only after commit."""
from threading import Lock


class ReportCacheEvents:
    def __init__(self, hub):
        self.hub = hub
        self.lock = Lock()
        self.revision = 0
        self.views = {}

    def committed(self, views, periods):
        with self.lock:
            self.revision += 1
            for view in views:
                self.views.setdefault(view, {}).update(dict.fromkeys(periods, self.revision))
            self.hub.publish('report_cache', {view: scopes.copy() for view, scopes in self.views.items()})
