#!/bin/zsh
set -u
if [[ -t 1 ]]; then
  printf 'Cost Guard: Checking requirements...'
  export COST_GUARD_LAUNCHER_STATUS=1
else
  printf 'Cost Guard: Checking requirements...\n'
fi
CG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

find_python() {
  typeset -A tested
  for candidate in python3 python /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    local executable="$(command -v "$candidate" 2>/dev/null)"
    [[ -z "$executable" || -n "${tested[$executable]-}" ]] && continue
    tested[$executable]=1
    if "$executable" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(find_python)" || {
  if [[ -t 1 ]]; then printf '\r%40s\r' ''; fi
  unset COST_GUARD_LAUNCHER_STATUS
  echo
  echo "Cost Guard could not find Python 3.11 or newer."
  echo "Install Python 3.11+ and run this launcher again."
  echo
  read -r '?Press Return to close...'
  exit 1
}

"$PYTHON" "$CG_ROOT/cost-guard.py"
status=$?
echo
read -r '?Press Return to close...'
exit $status
