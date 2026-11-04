"""Instance-local bootstrap/session protection. Not an OS-user isolation boundary."""
from dataclasses import dataclass
from http.cookies import SimpleCookie, CookieError
import secrets
from threading import Lock
import time

BOOTSTRAP_LIMIT = 16
BOOTSTRAP_SECONDS = 120
SESSION_SECONDS = 7 * 24 * 60 * 60
COOKIE_RENEW_SECONDS = 60 * 60
# Storage grace prevents throttling from shortening the seven-day idle window.
# It grants no authorization: the per-browser server deadline remains decisive.
COOKIE_SECONDS = SESSION_SECONDS + COOKIE_RENEW_SECONDS


@dataclass
class _Browser:
    until: float
    cookie_at: float


class BrowserLinkUnavailable(RuntimeError):
    """The native handoff cannot be issued now; retry without stopping the host."""


class BrowserSession:
    def __init__(self, cookie_scope=None, *, clock=None):
        # Cookies are host/path scoped, NOT port scoped. A stable checkout name
        # prevents another checkout's bootstrap from replacing this credential.
        self.cookie_name = "cg_session_" + (cookie_scope or secrets.token_hex(16))
        self._lock = Lock()
        self._clock = clock or time.time
        self._bootstrap = None
        self._pending = {}
        self._browsers = {}
        self._csrf = secrets.token_urlsafe(32)

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

    def exchange(self, token, cookie=None):
        supplied = self._credential(cookie)
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
            # Wall time includes suspend on every supported OS, like cookie age.
            now = self._clock()
            self._browsers = {key: browser for key, browser in self._browsers.items() if now < browser.until}
            if supplied not in self._browsers:
                supplied = secrets.token_urlsafe(32)
            self._browsers[supplied] = _Browser(now + SESSION_SECONDS, now)
            return supplied, self._csrf

    def _credential(self, cookie):
        try:
            values = SimpleCookie()
            values.load(cookie or "")
            supplied = values[self.cookie_name].value if self.cookie_name in values else ""
            return supplied if supplied.isascii() else ""
        except CookieError:
            return ""

    def authenticated(self, cookie):
        supplied = self._credential(cookie)
        with self._lock:
            browser = self._browsers.get(supplied)
            return browser is not None and self._clock() < browser.until

    def activity(self, cookie):
        """Successful protected API response only; checks/SSE never renew activity."""
        supplied = self._credential(cookie)
        with self._lock:
            now = self._clock()
            browser = self._browsers.get(supplied)
            if browser is None or now >= browser.until:
                return None
            browser.until = now + SESSION_SECONDS
            if now - browser.cookie_at >= COOKIE_RENEW_SECONDS:
                browser.cookie_at = now
                return supplied
            return None

    def csrf(self, supplied=None):
        with self._lock:
            if supplied is None:
                return self._csrf
            return (isinstance(supplied, str) and supplied.isascii() and self._csrf is not None
                    and secrets.compare_digest(supplied, self._csrf))
