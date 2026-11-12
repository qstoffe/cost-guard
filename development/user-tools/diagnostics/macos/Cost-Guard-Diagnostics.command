#!/bin/zsh
set -u
CG_ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

source "$CG_ROOT/src/python_discovery.sh"
cg_find_python || {
  cg_python_failure
  if [[ -t 0 && -t 1 ]]; then read -r '?Press Return to close...'; fi
  exit 1
}

"$PYTHON" "$CG_ROOT/development/tools/collect_diagnostics.py" --test-service-start
RESULT=$?
echo
if [[ -t 0 && -t 1 ]]; then read -r '?Press Return to close...'; fi
exit $RESULT
