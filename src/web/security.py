"""Instance-local bootstrap/session protection. Not an OS-user isolation boundary."""
from http.cookies import SimpleCookie, CookieError
import secrets
from threading import Lock
import time

BOOTSTRAP_LIMIT = 16
BOOTSTRAP_SECONDS = 120


class BrowserLinkUnavailable(RuntimeError):
    """The native handoff cannot be issued now; retry without stopping the host."""


class BrowserSession:
    def __init__(self, cookie_scope=None):
        # Cookies are host/path scoped, NOT port scoped. A stable checkout name
        # prevents another checkout's bootstrap from replacing this credential.
        self.cookie_name = "cg_session_" + (cookie_scope or secrets.token_hex(16))
        self._lock = Lock()
        self._bootstrap = None
        self._pending = {}
        self._session = None
        self._csrf = None
        self._until = 0

    def bootstrap(self, *, renew=False):
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            if renew or self._bootstrap not in self._pending:
                # Refuse excess handoffs rather than revoke an unexpired link.
                if len(self._pending) >= BOOTSTRAP_LIMIT:
                    raise BrowserLinkUnavailable("bootstrap_capacity")
                self._bootstrap = secrets.token_urlsafe(32)
                self._pending[self._bootstrap] = now + BOOTSTRAP_SECONDS
            return self._bootstrap

    def _prune(self, now):
        self._pending = {token: until for token, until in self._pending.items() if now < until}

    def discard_bootstrap(self, token):
        with self._lock:
            self._pending.pop(token, None)

    def exchange(self, token):
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            if not isinstance(token, str) or not token.isascii():
                return None
            matched = next((pending for pending in self._pending
                            if secrets.compare_digest(token, pending)), None)
            if matched is None:
                return None
            del self._pending[matched]
            if self._session is None or now >= self._until:
                self._session = secrets.token_urlsafe(32)
                self._csrf = secrets.token_urlsafe(32)
            self._until = now + 8 * 60 * 60
            return self._session, self._csrf

    def authenticated(self, cookie):
        try:
            values = SimpleCookie()
            values.load(cookie or "")
            supplied = values[self.cookie_name].value if self.cookie_name in values else ""
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
