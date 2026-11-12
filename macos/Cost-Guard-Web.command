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
if [[ -t 0 && -t 1 && -t 2 ]]; then activity & SPINNER=$!; fi

source "$CG_ROOT/src/python_discovery.sh"
cg_find_python || {
  stop_activity
  cg_python_failure
  if [[ -t 0 && -t 1 ]]; then read -r '?Press Return to close…'; fi
  exit 1
}
# Stop the display-only row before Python can print a multi-line failure.
stop_activity
"$PYTHON" -u "$CG_ROOT/cost-guard-web.py" --launch-macos
RESULT=$?
stop_activity
if [[ $RESULT -ne 0 && -t 0 && -t 1 ]]; then read -r '?Press Return to close…'; fi
exit $RESULT
