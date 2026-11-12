#!/bin/zsh
set -u
if [[ -t 1 ]]; then
  printf 'Cost Guard: Checking requirements...'
  export COST_GUARD_LAUNCHER_STATUS=1
else
  printf 'Cost Guard: Checking requirements...\n'
fi
CG_ROOT="$(cd "$(dirname "$0")/../.." && pwd)" || exit 1

source "$CG_ROOT/src/python_discovery.sh"
cg_find_python || {
  if [[ -t 1 ]]; then printf '\r%40s\r' ''; fi
  unset COST_GUARD_LAUNCHER_STATUS
  cg_python_failure
  if [[ -t 0 && -t 1 ]]; then read -r '?Press Return to close...'; fi
  exit 1
}

exec "$PYTHON" "$CG_ROOT/cost-guard-cli.py" --watch
