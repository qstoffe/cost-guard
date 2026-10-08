#!/bin/zsh
set -u
CG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

find_python() {
  for candidate in python3 python /opt/homebrew/bin/python3 /usr/local/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(find_python)" || {
  echo
  echo "Cost Guard could not find Python 3.11 or newer."
  echo "Install Python 3.11+ and run this launcher again."
  echo
  read -r '?Press Return to close...'
  exit 1
}

exec "$PYTHON" "$CG_ROOT/cost-guard.py" --watch
