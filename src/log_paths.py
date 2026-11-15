"""Installation-local generated output; never application-private instance state."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import stat
import threading

WRITE_LOCK = threading.RLock()
LOG_PATTERNS = {
    "errors": re.compile(r"cost-guard-(?:errors|metadata)-\d{4}-\d{2}-\d{2}\.log\Z"),
    "crashes": re.compile(r"cost-guard-crash-\d{8}-\d{6}-\d+(?:-\d+)?\.txt\Z"),
    "recovery": re.compile(r"(?:(?:watch-recovery|watch-observations|model-metadata)\.json|cost-guard-metadata-\d{4}-\d{2}-\d{2}\.log)\Z"),
}
LIVE_STATE = frozenset({"model-metadata.json", "watch-observations.json", "watch-recovery.json"})
BUNDLE_PATTERN = re.compile(r"cost-guard-diagnostics(?:-\d{8}-\d{6})?\.zip\Z")


def log_root(root: Path) -> Path:
    return Path(root) / "development" / "logs"


def log_bases(root: Path) -> tuple[Path, ...]:
    """Preferred output followed by the two supported read-only legacy layouts."""
    return log_root(root), Path(root) / "logs", Path(root) / "diagnostics"


def safe(info) -> bool:
    return not (stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400)


def safe_path(root: Path, path: Path) -> bool:
    """Existing paths only; reject every link/reparse ancestor and device crossing."""
    try:
        base = Path(root).absolute()
        current = base
        device = base.lstat().st_dev
        for part in (".", *Path(path).absolute().relative_to(base).parts):
            current /= part
            info = current.lstat()
            if not safe(info) or info.st_dev != device:
                return False
        return True
    except (OSError, ValueError):
        return False


@contextmanager
def directory_handle(root: Path, directory: Path):
    """POSIX operations stay relative to no-follow directory handles, even on rename."""
    if not safe_path(root, directory):
        raise OSError("Unsafe generated-output directory")
    if os.name == "nt":
        yield None  # Windows reparse/identity checks plus native sharing rules.
        return
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        device = os.fstat(descriptor).st_dev
        for part in directory.relative_to(root).parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            if os.fstat(descriptor).st_dev != device:
                raise OSError("Generated output crosses device")
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def file_lock(target, *, blocking=True):
    """Coordinate our appenders/cleaner across processes without persistent lock files."""
    position = target.tell()
    if os.name == "nt":
        import msvcrt
        target.seek(0)
        msvcrt.locking(target.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(target.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
    try:
        target.seek(position)
        yield
    finally:
        if os.name == "nt":
            target.seek(0)
            msvcrt.locking(target.fileno(), msvcrt.LK_UNLCK, 1)
            target.seek(position)
        else:
            fcntl.flock(target.fileno(), fcntl.LOCK_UN)


def owned_directories(root: Path):
    for base in log_bases(root):
        for folder in LOG_PATTERNS:
            yield base / folder, folder
    yield log_root(root) / "diagnostics", "bundles"
    yield Path(root) / "diagnostics", "bundles"


def owned_name(name: str, kind: str, *, disposable=False) -> bool:
    if kind == "bundles":
        return bool(BUNDLE_PATTERN.fullmatch(name))
    return bool(LOG_PATTERNS[kind].fullmatch(name)) and not (disposable and name in LIVE_STATE)


def owned_files(root: Path):
    """Bounded read inventory, preferred layout first; no recursive unknown trees."""
    for directory, kind in owned_directories(root):
        try:
            with directory_handle(root, directory) as descriptor:
                with os.scandir(descriptor if descriptor is not None else directory) as entries:
                    for index, entry in enumerate(entries):
                        if index >= 2048:
                            break
                        info = ((directory / entry.name).lstat() if descriptor is None
                                else entry.stat(follow_symlinks=False))
                        if (owned_name(entry.name, kind) and safe(info) and stat.S_ISREG(info.st_mode)
                                and info.st_nlink == 1):
                            yield directory / entry.name, kind
        except OSError:
            continue


def legacy_events_file(path: Path) -> Path:
    """Only installation-local new paths have a legacy fallback; test overrides don't."""
    parts = path.parts
    if len(parts) >= 4 and parts[-4:-1] == ("development", "logs", "recovery"):
        return path.parents[3] / "logs" / "recovery" / path.name
    return path


def read_events(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return legacy_events_file(path).read_text(encoding="utf-8")
