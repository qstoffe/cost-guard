"""Instance-local bootstrap/session protection. Not an OS-user isolation boundary."""
from http.cookies import SimpleCookie, CookieError
import secrets
from threading import Lock
import time


class BrowserSession:
    def __init__(self):
        self._lock = Lock()
        self._bootstrap = secrets.token_urlsafe(32)
        self._bootstrap_until = time.monotonic() + 120
        self._session = None
        self._csrf = None
        self._until = 0

    def bootstrap(self):
        with self._lock:
            return self._bootstrap

    def exchange(self, token):
        with self._lock:
            if (not isinstance(token, str) or not token.isascii() or self._bootstrap is None
                    or time.monotonic() > self._bootstrap_until
                    or not secrets.compare_digest(token, self._bootstrap)):
                return None
            self._bootstrap = None
            self._session = secrets.token_urlsafe(32)
            self._csrf = secrets.token_urlsafe(32)
            self._until = time.monotonic() + 8 * 60 * 60
            return self._session, self._csrf

    def authenticated(self, cookie):
        try:
            values = SimpleCookie()
            values.load(cookie or "")
            supplied = values["cg_session"].value if "cg_session" in values else ""
        except CookieError:
            return False
        with self._lock:
            return (supplied.isascii() and self._session is not None and time.monotonic() < self._until
                    and secrets.compare_digest(supplied, self._session))

    def csrf(self, supplied=None):
        with self._lock:
            if supplied is None:
                return self._csrf
            return (isinstance(supplied, str) and supplied.isascii() and self._csrf is not None
                    and secrets.compare_digest(supplied, self._csrf))
