# Sourced by zsh launchers; no Python, package manager or interactive shell setup needed.
# Policy: PATH, framework versions, Homebrew opt formulas, then bounded user installs.
cg_python_candidates() {
  local name executable
  for name in python3 python; do
    executable="$(whence -p -- "$name" 2>/dev/null)"
    [[ -n "$executable" ]] && print -r -- "$executable"
  done
  local -a candidates
  candidates=(
    /opt/homebrew/bin/python3 /usr/local/bin/python3
    /Library/Frameworks/Python.framework/Versions/{Current,<->.<->}/bin/python3(N)
    "$HOME"/Library/Frameworks/Python.framework/Versions/{Current,<->.<->}/bin/python3(N)
    /opt/homebrew/opt/python@3.*/bin/python3.<->(N)
    /usr/local/opt/python@3.*/bin/python3.<->(N)
    "$HOME"/.local/bin/python3
    "$HOME"/.pyenv/versions/*/bin/python3(N)
    "$HOME"/.local/share/mise/installs/python/*/bin/python3(N)
    "$HOME"/.local/share/uv/python/cpython-3.*-macos-*/bin/python3(N)
  )
  print -rl -- "${candidates[@]}"
}

cg_stop_python_probe() {
  if [[ -n "${CG_PROBE_PID-}" ]]; then
    kill -KILL "$CG_PROBE_PID" 2>/dev/null || true
    wait "$CG_PROBE_PID" 2>/dev/null || true
    CG_PROBE_PID=''
  fi
  if [[ -n "${CG_PROBE_FILE-}" ]]; then /bin/rm -f -- "$CG_PROBE_FILE"; fi
  CG_PROBE_FILE=''
}

cg_probe_python() {
  local executable="$1" temporary probe result tick
  CG_PROBE='broken'
  CG_REAL=''
  temporary="$(/usr/bin/mktemp "${TMPDIR:-/tmp}/cost-guard-python.XXXXXXXX")" || return
  CG_PROBE_FILE="$temporary"
  {
    # The exact child has a wall deadline and a small output-file limit.
    ( ulimit -f 16; exec "$executable" -I -S -c 'import sys,sqlite3,ssl,ctypes; print("CGPY|%s|%s|%s|%s" % (sys.version_info[0],sys.version_info[1],sys.platform,sys.executable))' ) >"$temporary" 2>/dev/null &
    probe=$!
    CG_PROBE_PID="$probe"
    for tick in {1..20}; do
      kill -0 "$probe" 2>/dev/null || break
      (( SECONDS >= CG_DEADLINE )) && break
      /bin/sleep 0.1
    done
    if kill -0 "$probe" 2>/dev/null; then kill -KILL "$probe" 2>/dev/null; fi
    wait "$probe" 2>/dev/null
    result=$?
    probe=''
    CG_PROBE_PID=''
    [[ $result -eq 0 ]] || return
    local marker major minor platform real extra
    IFS='|' read -r marker major minor platform real extra <"$temporary"
    [[ "$marker" == CGPY && "$major" == <-> && "$minor" == <-> && "$platform" == darwin && -z "$extra" && "$real" == /* && -x "$real" && -f "$real" ]] || return
    if (( major < 3 || (major == 3 && minor < 11) )); then
      CG_PROBE='old'
    else
      CG_PROBE='ready'
      CG_REAL="${real:A}"
    fi
  } always {
    cg_stop_python_probe
  }
}

cg_find_python() {
  setopt localtraps
  trap 'cg_stop_python_probe; exit 130' INT
  trap 'cg_stop_python_probe; exit 143' TERM
  local -A tested
  local candidate real old=0 broken=0 count=0
  local -a candidates
  local CG_DEADLINE=$(( SECONDS + 20 ))
  candidates=("${(@f)$(cg_python_candidates)}")
  PYTHON=''
  CG_PYTHON_FAILURE='missing'
  for candidate in "${candidates[@]}"; do
    [[ "$candidate" == /* && -f "$candidate" ]] || continue
    candidate="${candidate:A}"
    [[ -n "${tested[$candidate]-}" ]] && continue
    tested[$candidate]=1
    (( count++ ))
    if (( count > 128 || SECONDS >= CG_DEADLINE )); then broken=1; break; fi
    cg_probe_python "$candidate"
    if [[ "$CG_PROBE" == ready ]]; then
      real="$CG_REAL"
      if [[ "$real" != "$candidate" ]]; then
        cg_probe_python "$real"
        [[ "$CG_PROBE" == ready && "$CG_REAL" == "$real" ]] || { broken=1; continue; }
      fi
      PYTHON="$real"
      return 0
    elif [[ "$CG_PROBE" == old ]]; then old=1
    else broken=1
    fi
  done
  if (( broken )); then CG_PYTHON_FAILURE='broken'
  elif (( old )); then CG_PYTHON_FAILURE='old'
  fi
  return 1
}

cg_python_failure() {
  local reason
  case "$CG_PYTHON_FAILURE" in
    old) reason='Only Python versions older than 3.11 were usable.' ;;
    broken) reason='Discovered Python candidates could not run correctly or timed out.' ;;
    *) reason='No usable Python 3.11+ installation could be located.' ;;
  esac
  printf 'COST GUARD COULD NOT START\n\nReason: %s\n\n' "$reason"
  printf 'Next step: Use an installed Python 3.11+ executable directly (see README), or install Python 3.11+.\n\n'
  printf 'Diagnostics: development/user-tools/diagnostics/macos/Cost-Guard-Diagnostics.command\n'
}
