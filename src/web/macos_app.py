"""First-launch AppleScript applet creation with only macOS's in-box osacompile."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import stat
import subprocess
import sys
import tempfile

from src.version import VERSION
from .instance_state import _private, _safe
from .process_identity import InstanceConflict

SOURCES = ("macos/Beta/launcher.applescript", "macos/Beta/Cost-Guard-Web.command",
           "cost-guard-web.py", "src/web/macos_app.py", "src/web/macos_launch.py",
           "src/web/native_macos.py", "src/web/macos_status.py", "src/web/objc_bridge.py")


def app_source(root):
    command = shlex.join([sys.executable, str(root / "cost-guard-web.py"), "--launch-macos"])
    literal = command.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "\\r").replace("\n", "\\n")
    template = (root / SOURCES[0]).read_text(encoding="utf-8")
    if template.count("{{LAUNCH_COMMAND}}") != 1:
        raise InstanceConflict("app_preparation_failed")
    return template.replace("{{LAUNCH_COMMAND}}", literal)


def fingerprint(root):
    facts = [str(root), sys.executable, sys.version, VERSION, platform.mac_ver()[0], platform.machine(),
             platform.release()]
    digest = hashlib.sha256(json.dumps(facts).encode("utf-8"))
    for name in SOURCES:
        digest.update(name.encode("utf-8"))
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def app_inventory(path):
    """Refuse links/special files; cached artifacts are bounded and hash-checked."""
    result = {}
    total = entries = 0
    for parent, directories, files in os.walk(path, followlinks=False):
        entries += len(directories) + len(files)
        if entries > 256:
            raise InstanceConflict("app_preparation_failed")
        for name in directories + files:
            item = Path(parent) / name
            info = _safe(item)
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                raise InstanceConflict("app_preparation_failed")
            total += info.st_size
            if total > 20 * 1024 * 1024:
                raise InstanceConflict("app_preparation_failed")
            result[item.relative_to(path).as_posix()] = {
                "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
                "mode": stat.S_IMODE(info.st_mode),
            }
    if "Contents/MacOS/applet" not in result or "Contents/Info.plist" not in result:
        raise InstanceConflict("app_preparation_failed")
    return result


def prepare_app(root, store):
    root = Path(root).resolve(strict=True)
    key = fingerprint(root)
    destination = store.directory / ("finder-" + key)
    app = destination / "Cost Guard Web.app"
    # Same transition lock as restart, but released before launch acquires it.
    with store.lock(timeout=35):
        if destination.exists() or destination.is_symlink():
            _private(destination)
            _private(app)
            manifest = destination / "manifest.json"
            info = _safe(manifest)
            if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                raise InstanceConflict("app_preparation_failed")
            saved = json.loads(manifest.read_text(encoding="utf-8"))
            if saved != {"fingerprint": key, "files": app_inventory(app)}:
                # Never overwrite an unverifiable artifact (or follow its links).
                raise InstanceConflict("app_preparation_failed")
            print("Cost Guard: Reusing locally prepared Finder app.", flush=True)
            return app
        print("Cost Guard: Preparing Finder app with macOS osacompile (no downloads)...", flush=True)
        # Atomic publication: failed/partial compiles are confined to this owned temp.
        with tempfile.TemporaryDirectory(prefix="finder-build-", dir=store.directory) as temporary:
            build = Path(temporary)
            _private(build)
            script = build / "launcher.applescript"
            script.write_text(app_source(root), encoding="utf-8")
            _private(script)
            generated = build / app.name
            try:
                result = subprocess.run(["/usr/bin/osacompile", "-o", str(generated), str(script)],
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired):
                raise InstanceConflict("app_preparation_failed") from None
            if result.returncode:
                raise InstanceConflict("app_preparation_failed")
            _private(generated)
            manifest = {"fingerprint": key, "files": app_inventory(generated)}
            if key != fingerprint(root):
                raise InstanceConflict("app_preparation_failed")
            script.unlink()
            record = build / "manifest.json"
            record.write_text(json.dumps(manifest), encoding="utf-8")
            _private(record)
            # A distinct content-keyed destination; never overwrite an existing app.
            if destination.exists() or destination.is_symlink():
                raise InstanceConflict("app_preparation_failed")
            build.rename(destination)
        print("Cost Guard: Finder app compiled locally.", flush=True)
        return app
