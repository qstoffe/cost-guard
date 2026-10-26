"""Explicit developer host and private native-launcher child entry."""
import importlib
from pathlib import Path
import re
import sys

from src.config import ConfigError, load_configuration
from src.runtime_errors import RuntimeErrors
from .host import WebHost
from .instance_state import InstanceStore
from .lifecycle import GUI_MODULES


def managed(root, nonce, module):
    store = InstanceStore(root)
    try:
        with store.lock(timeout=0, lifetime=True):
            store.log("starting")

            def run():
                # Missing native host fails before HTTP startup. No icon-free fallback.
                gui = importlib.import_module(module).create_host()
                owner = WebHost(root, store=store, nonce=nonce)
                owner.run_gui(gui)
                if owner.failure:
                    raise owner.failure
                return 0 if owner.ready else 1

            # Reuse existing sanitized fault machinery, rooted outside tracked source.
            return RuntimeErrors(store.directory, mode="Web Beta").run(run)
    except Exception:
        store.log("runtime_fault")
        return 1


def main():
    arguments = sys.argv[1:]
    if arguments == ["--help"]:
        print("Usage: python cost-guard-web.py --foreground\n"
              "Developer loopback Web Beta. Ctrl+C or runtime changes stop owned work.\n"
              "Native detached launchers are supplied separately; no browser opens here.")
        return 0
    is_managed = (len(arguments) == 3 and arguments[0] == "--managed"
                  and re.fullmatch(r"[a-f0-9]{32}", arguments[1]) and arguments[2] in GUI_MODULES)
    if arguments != ["--foreground"] and not is_managed:
        print("Cost Guard Web: use --foreground for developer mode or --help.")
        return 2
    root = Path(__file__).resolve().parents[2]
    try:
        load_configuration(root)
    except ConfigError:
        print("Cost Guard Web: configuration unavailable. Check local configuration.")
        return 1
    if is_managed:
        return managed(root, arguments[1], arguments[2])
    owner = WebHost(root)
    try:
        owner.start()
        owner.publish_ready()
        print(f"Cost Guard Web Beta ready: {owner.server.origin}/", flush=True)
        print(f"Open within 120 seconds: {owner.browser_url()}", flush=True)
        print("Developer mode; keep console open. Ctrl+C or runtime changes stop Web.", flush=True)
        owner.stopped.wait()
    except KeyboardInterrupt:
        owner.stop("menu")
    finally:
        owner.close()
    if owner.failure:
        raise owner.failure
    return 1 if owner.reason == "runtime_fault" else 0
