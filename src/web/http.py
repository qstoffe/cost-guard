"""Fixed-route, bounded loopback HTTP shell. No generic filesystem handler."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import socket
from threading import BoundedSemaphore, Timer

from .jobs import parse_report
from .security import BrowserSession

ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/app.css": ("app.css", "text/css; charset=utf-8")}
JOB_PATH = re.compile(r"/api/jobs/([a-f0-9]{32})(/cancel)?\Z")
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
       "img-src 'none'; font-src 'none'; object-src 'none'; base-uri 'none'; "
       "frame-ancestors 'none'; form-action 'none'; worker-src 'none'")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


class HeaderReader:
    def __init__(self, stream):
        self.stream = stream
        self.remaining = 16384

    def readline(self, size=-1):
        line = self.stream.readline(min(size if size >= 0 else 4096, 4096))
        self.remaining -= len(line)
        if self.remaining < 0 or len(line) >= 4096 or (line and not line.endswith(b"\r\n")):
            raise ValueError("invalid_headers")
        return line

    def read(self, size):
        return self.stream.read(size)

    def close(self):
        self.stream.close()


class LoopbackServer(HTTPServer):
    request_queue_size = 8
    allow_reuse_address = False

    def __init__(self, jobs):
        self.jobs = jobs
        self.session = BrowserSession()
        self.assets = {}
        root = Path(__file__).parent / "assets"
        for name, content_type in ASSETS.values():
            path = root / name
            if any(p.is_symlink() or p.is_junction() if hasattr(p, "is_junction") else p.is_symlink()
                   for p in (path, root, root.parent, root.parent.parent)):
                raise ValueError("unsafe_assets")
            self.assets[name] = path.read_bytes(), content_type
        self._slots = BoundedSemaphore(8)
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="cost-guard-http")
        try:
            super().__init__(("127.0.0.1", 0), RequestHandler)
        except BaseException:
            self._pool.shutdown(wait=True, cancel_futures=True)
            raise
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.host = f"127.0.0.1:{self.server_port}"
        self.timeout = 0.05

    def process_request(self, request, address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        request.settimeout(2)
        try:
            self._pool.submit(self._serve, request, address)
        except BaseException:
            self._slots.release()
            self.shutdown_request(request)
            raise

    def _serve(self, request, address):
        def expire():
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        # Socket timeouts alone permit an indefinitely dripping slowloris.
        deadline = Timer(5, expire)
        deadline.start()
        try:
            self.finish_request(request, address)
        except (OSError, ValueError):
            pass  # Invalid/abandoned wire request; never log request text or secrets.
        finally:
            deadline.cancel()
            deadline.join()
            self.shutdown_request(request)
            self._slots.release()

    def handle_error(self, request, address):
        pass  # Base implementation prints raw exception/request context.

    def server_close(self):
        super().server_close()
        self._pool.shutdown(wait=True, cancel_futures=True)


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "CostGuard"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.rfile = HeaderReader(self.rfile)

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.reply(code, {"error": "invalid_request"})

    def handle_expect_100(self):
        self.reply(417, {"error": "invalid_request"})
        return False

    def handle_one_request(self):
        self.close_connection = True
        try:
            self.raw_requestline = self.rfile.readline(2049)
            if not self.raw_requestline:
                return
            if len(self.raw_requestline) > 2048:
                self.request_version = "HTTP/1.0"
                self.reply(414, {"error": "invalid_request"})
                return
            if not re.fullmatch(rb"[A-Z]+ /[^\x00-\x20\x7f]* HTTP/1\.[01]\r\n", self.raw_requestline):
                self.request_version = "HTTP/1.0"
                self.reply(400, {"error": "invalid_request"})
                return
            if not self.parse_request():
                return
            self.close_connection = True
            self.route()
        except (ValueError, TimeoutError, ConnectionError, OSError):
            return

    def reply(self, status, value, *, content_type="application/json; charset=utf-8", cookie=None):
        data = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode("utf-8")
        self.send_response_only(status)
        for key, val in {"Content-Type": content_type, "Content-Length": str(len(data)),
                         "Connection": "close", "Cache-Control": "no-store", "Content-Security-Policy": CSP,
                         "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                         "X-Frame-Options": "DENY", "Cross-Origin-Resource-Policy": "same-origin",
                         "Permissions-Policy": "camera=(), microphone=(), geolocation=()"}.items():
            self.send_header(key, val)
        if cookie:
            self.send_header("Set-Cookie", f"cg_session={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")
        self.end_headers()
        self.wfile.write(data)

    def route(self):
        headers = self.headers
        if (any(len(headers.get_all(k, [])) != 1 for k in set(headers.keys()))
                or headers.defects or any("\r" in v or "\n" in v for v in headers.values())
                or headers.get("Host") != self.server.host
                or headers.get("Origin") not in (None, self.server.origin)
                or headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none")
                or headers.get("Transfer-Encoding") is not None or headers.get("Expect") is not None):
            self.reply(403, {"error": "request_denied"})
            return
        if self.command not in {"GET", "POST"}:
            self.reply(405, {"error": "method_not_allowed"})
            return
        # No URL decoding, query strings, absolute-form targets or generic path parameters.
        if not self.path.startswith("/") or any(c in self.path for c in "%?#\\") or ".." in self.path:
            self.reply(400, {"error": "invalid_request"})
            return
        length = headers.get("Content-Length", "0")
        if not re.fullmatch(r"[0-9]{1,5}", length) or int(length) > 4096:
            self.reply(413, {"error": "request_too_large"})
            return
        if self.command == "GET" and int(length):
            self.reply(400, {"error": "invalid_request"})
            return
        if self.command == "GET" and self.path in ASSETS:
            data, content_type = self.server.assets[ASSETS[self.path][0]]
            self.reply(200, data, content_type=content_type)
            return
        if self.path == "/health" and self.command == "GET":
            self.reply(200, {"http": "ready"})
            return
        if self.command == "POST" and (headers.get("Origin") != self.server.origin
                or headers.get("Content-Type") != "application/json"):
            self.reply(403, {"error": "request_denied"})
            return
        if self.path != "/api/bootstrap" and not self.server.session.authenticated(headers.get("Cookie")):
            self.reply(401, {"error": "authentication_required"})
            return
        if self.command == "POST":
            if self.path != "/api/bootstrap" and not self.server.session.csrf(headers.get("X-CG-CSRF", "")):
                self.reply(403, {"error": "csrf_required"})
                return
            try:
                body = self.rfile.read(int(length))
                if len(body) != int(length):
                    raise ValueError("short_body")
                value = json.loads(body, object_pairs_hook=unique_object)
                if not isinstance(value, dict):
                    raise ValueError("invalid_body")
            except (ValueError, UnicodeError, RecursionError):
                self.reply(400, {"error": "invalid_request"})
                return
            if self.path == "/api/bootstrap":
                session = self.server.session.exchange(value.get("credential")) if set(value) == {"credential"} else None
                if session is None:
                    self.reply(401, {"error": "bootstrap_expired_or_used"})
                else:
                    self.reply(200, {"csrf": session[1]}, cookie=session[0])
                return
            if self.path == "/api/reports":
                try:
                    request = parse_report(value)
                except (ValueError, TypeError):
                    self.reply(400, {"error": "invalid_request"})
                    return
                try:
                    key = self.server.jobs.submit(request)
                except RuntimeError:
                    self.reply(429, {"error": "busy"})
                    return
                self.reply(202, {"id": key})
                return
            match = JOB_PATH.fullmatch(self.path)
            if match and match[2] and not value:
                found = self.server.jobs.cancel(match[1])
                self.reply(200 if found else 404, {"status": "cancel_requested" if found else "not_found"})
                return
        else:
            if self.path == "/api/status":
                self.reply(200, self.server.jobs.readiness())
                return
            if self.path == "/api/session":
                self.reply(200, {"csrf": self.server.session.csrf()})
                return
            match = JOB_PATH.fullmatch(self.path)
            if match and not match[2]:
                result = self.server.jobs.snapshot(match[1])
                self.reply(200 if result else 404, result or {"error": "not_found"})
                return
        self.reply(404, {"error": "not_found"})
