"""Focused source invariant for Cost Guard's owned human date/time text."""
import ast
from collections import Counter
import re


# These are statement-level exceptions, not exempt modules or functions.
PYTHON_EXCEPTIONS = {
    "src/analysis/account_timeline.py": {"day.isoformat()": 1},  # wire calendar bucket identity
    "src/analysis/valuation.py": {
        "datetime.fromtimestamp(entry.completed_at_ms / 1000, timezone.utc).strftime('%Y-%m-%d')": 1,
    },  # UTC accounting index
    "src/application/live_projection.py": {
        "datetime.fromtimestamp(value.daily_usage.day_start_ms / 1000, tz=resolve_timezone(timezone_id)).date().isoformat()": 1,
    },  # date-range arithmetic, not display
    "src/log_housekeeping.py": {"f'{today:%Y-%m-%d}'": 1, "f'{today:%Y%m%d}'": 1},  # filename matching
    "src/pricing/github_copilot.py": {
        "datetime.fromtimestamp(catalog.retrieved_at_ms / 1000, tz=timezone.utc).strftime('%Y-%m')": 1,
        "datetime.fromtimestamp(now / 1000, tz=timezone.utc).strftime('%Y-%m')": 1,
    },  # UTC cache invalidation
    "src/pricing/metadata_health.py": {
        "datetime.now().astimezone().isoformat()": 1,
        "f'{datetime.now().astimezone():%Y-%m-%d}'": 1,
    },  # diagnostic records and filename
    "src/pricing/release_metadata.py": {
        "parsedate_to_datetime(published).astimezone(timezone.utc).date().isoformat()": 1,
    },  # normalized provider calendar date, upstream of rendering and sorting
    "src/reports/semantics.py": {"value.isoformat(timespec='milliseconds')": 1},  # persisted report data
    "src/runtime_errors.py": {
        "datetime.now().astimezone().isoformat()": 2,
        "f'{datetime.now().astimezone():%Y-%m-%d}'": 1,
        "f'{datetime.now():%Y%m%d-%H%M%S}'": 1,
    },  # diagnostic records and filenames
}

DATE_DIRECTIVE = re.compile(r"%[YymdHIMSfzZbBpaAxXcjuUwWVgG]")
DATE_COMPONENTS = frozenset(("year", "month", "day", "hour", "minute", "second", "microsecond"))


def _python_risk(node):
    if isinstance(node, ast.Attribute) and node.attr in ("strftime", "isoformat"):
        return True
    if isinstance(node, ast.FormattedValue):
        spec = node.format_spec
        return (isinstance(node.value, ast.Attribute) and node.value.attr in DATE_COMPONENTS and spec is not None
                or spec is not None and any(isinstance(part, ast.Constant) and isinstance(part.value, str)
                    and DATE_DIRECTIVE.search(part.value) for part in spec.values))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "format":
        return any(isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                   and DATE_DIRECTIVE.search(arg.value) for arg in node.args[1:])
    return False


def python_bypasses(path, source):
    if path == "src/analysis/timezones.py":
        return []
    tree = ast.parse(source, filename=path)
    calls = {node.func: node for node in ast.walk(tree) if isinstance(node, ast.Call)}
    accepted = Counter(PYTHON_EXCEPTIONS.get(path, {}))
    failures = []
    for node in ast.walk(tree):
        if _python_risk(node):
            expression = ast.unparse(calls.get(node, ast.JoinedStr(values=[node])
                if isinstance(node, ast.FormattedValue) else node))
            if accepted[expression] > 0:
                accepted[expression] -= 1
            else:
                failures.append((node.lineno, expression))
    return failures


# Guard the formatting APIs and Date object conversion/component access, not
# every mention of "date" or numerical timestamp arithmetic in a Web asset.
JS_RISK = re.compile(
    r"\bDateTimeFormat\b|\bDate\s*\(|"
    r"\b(?:to(?:Locale(?:Date|Time)?|UTC|GMT|Date|Time|ISO)?String|"
    r"get(?:UTC)?(?:FullYear|Year|Month|Date|Day|Hours|Minutes|Seconds|Milliseconds|TimezoneOffset))\s*"
    r"(?:\(|['\"]\s*\])"
)
JS_NUMBER_LOCALE = {
    "src/web/assets/report-loading.js": ("completed", "progress.total"),
    "src/web/assets/sessions.js": ("count.completed", "count.total", "current.context_tokens"),
    "src/web/assets/token-mix.js": ("BigInt(mix.observed_total_tokens)",),
    "src/web/assets/watch.js": ("timeout",),
}
JS_OWNER_SITES = (
    "new Date(instant).toISOString()",  # round-trip validation of a calendar value, not display
    "new Intl.DateTimeFormat('en-US',",
    "new Intl.DateTimeFormat('en',",
    "new Intl.DateTimeFormat(language,",
)


def web_bypasses(path, source):
    snippets = [value + ".toLocaleString(" for value in JS_NUMBER_LOCALE.get(path, ())]
    if path == "src/web/assets/render.js":
        snippets.extend(JS_OWNER_SITES)
    allowed = []
    for snippet in snippets:
        match = re.search(r"(?<![\w.])" + re.escape(snippet), source)
        if match is not None:
            allowed.append(match.span())
    return [
        (source.count("\n", 0, match.start()) + 1, match.group().strip())
        for match in JS_RISK.finditer(source)
        if not any(start <= match.start() < end for start, end in allowed)
    ]


def date_display_bypasses(root):
    for directory, glob, check in (("src", "*.py", python_bypasses),
                                   ("src/web/assets", "*.js", web_bypasses)):
        for file in sorted((root / directory).rglob(glob)):
            path = file.relative_to(root).as_posix()
            try:
                for line, evidence in check(path, file.read_text(encoding="utf-8-sig")):
                    yield f"{path}:{line}: {evidence}"
            except SyntaxError as error:
                yield f"{path}:{error.lineno}: source did not parse"
