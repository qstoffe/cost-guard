#!/bin/zsh
set -u
printf 'Cost Guard Web Beta: Checking requirements (native macOS validation pending)...\n'
CG_ROOT="$(cd "$(dirname "$0")/../.." && pwd)" || exit 1

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
  printf 'Cost Guard Web requires macOS and already-installed Python 3.11+. Nothing was installed.\n'
  printf 'Existing CLI/Watch launchers are unchanged.\n'
  exit 1
}
"$PYTHON" "$CG_ROOT/cost-guard-web.py" --launch-macos
exit $?
