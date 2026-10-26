"""Allowlisted launcher progress, independent of source/report readiness or secrets."""
import time


STAGES = {
    "config": "Checking safe configuration",
    "preflight": "Checking native tray support",
    "helper": "Preparing optional local Finder helper (first launch may take longer)",
    "arbitration": "Checking existing instance; overlapping launches wait here",
    "restart": "Stopping the verified previous Web host",
    "host": "Starting detached Web host and tray; waiting for validated readiness",
    "browser": "Opening authenticated browser; source and accounts may still be loading",
    "handoff": "Browser handoff complete; loading continues in Cost Guard",
}


class StartupProgress:
    def __init__(self):
        self.started = time.monotonic()

    def __call__(self, stage):
        # Never interpolate URLs, tokens, paths or exception messages.
        message = STAGES[stage]
        elapsed = time.monotonic() - self.started
        print(f"Cost Guard startup: {message} ({elapsed:.1f}s elapsed)", flush=True)
