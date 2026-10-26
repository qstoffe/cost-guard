"""Foreground-only Beta host; no auto-browser, restart or instance discovery."""
from pathlib import Path
import sys

from src.config import ConfigError, load_configuration

from .http import LoopbackServer
from .jobs import ReportJobs


def main():
    if sys.argv[1:] == ["--help"]:
        print("Usage: python cost-guard-web.py\nForeground loopback Web Beta. Ctrl+C stops owned report work.")
        return 0
    if sys.argv[1:]:
        print("Cost Guard Web: unsupported arguments. Use --help.")
        return 2
    try:
        load_configuration(Path(__file__).resolve().parents[2])
    except ConfigError:
        print("Cost Guard Web: configuration unavailable. Check local configuration.")
        return 1
    jobs = ReportJobs()
    try:
        with LoopbackServer(jobs) as server:
            print(f"Cost Guard Web Beta ready: {server.origin}/", flush=True)
            # This one-use fragment is intentionally shown only to the foreground owner.
            # Never an access-log/query parameter or persistent control credential.
            print(f"Open within 120 seconds: {server.origin}/#bootstrap={server.session.bootstrap()}", flush=True)
            print("Keep this console open; Ctrl+C stops Web. No browser opens automatically.", flush=True)
            while True:
                server.handle_request()
                jobs.tick()
    except KeyboardInterrupt:
        print("Cost Guard Web stopped.")
        return 0
    finally:
        jobs.close()
