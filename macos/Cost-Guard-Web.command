#!/bin/zsh
set -u
printf 'Launching web… Checking requirements (native macOS validation pending).\n'
CG_ROOT="$(cd "$(dirname "$0")/.." && pwd)" || exit 1
# This display-only child never owns/restarts the detached Web host.
activity() {
  while true; do
    for frame in '|' '/' '-' '\\'; do
      printf '\rLaunching web… [%s]  ' "$frame" >&2
      sleep 0.15
    done
  done
}
SPINNER=''
stop_activity() {
  if [[ -n "$SPINNER" ]]; then
    kill "$SPINNER" 2>/dev/null || true
    wait "$SPINNER" 2>/dev/null || true
    SPINNER=''
    printf '\r                        \r' >&2
  fi
}
trap stop_activity EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ -t 2 ]]; then activity & SPINNER=$!; fi

find_python() {
  typeset -A tested
  for candidate in python3 python /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    local executable="$(command -v "$candidate" 2>/dev/null)"
    [[ -z "$executable" || -n "${tested[$executable]-}" ]] && continue
    tested[$executable]=1
    if "$executable" -c 'import sys; raise SystemExit(0 if sys.platform == "darwin" and sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
      printf '%s' "$executable"
      return 0
    fi
  done
  return 1
}

PYTHON="$(find_python)" || {
  stop_activity
  printf 'Cost Guard Web requires macOS and already-installed Python 3.11+. Nothing was installed.\n'
   printf 'Legacy CLI: macos/Legacy/Cost-Guard.command or python3 cost-guard-cli.py (also requires Python 3.11+).\n'
  if [[ -t 0 ]]; then read -r '?Press Return to close…'; fi
  exit 1
}
"$PYTHON" -u "$CG_ROOT/cost-guard-web.py" --launch-macos
RESULT=$?
stop_activity
if [[ $RESULT -ne 0 && -t 0 ]]; then read -r '?Press Return to close…'; fi
exit $RESULT
