"""Hosted Chromium Token Mix regression; real five-minute cadence on manual Full."""
import json
import os
from pathlib import Path
import subprocess
import sys


def browser_command(browser, output):
    command = ['node', 'development/tests/integration/probe_token_mix.cjs', browser, str(output)]
    # Ordinary checks exercise the existing overdue-clock path, including slow
    # coherent replacement. Do not spend five real minutes twice per release.
    # Manual Full retains actual elapsed-time proof, not an equivalent ordinary PASS.
    if os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        command.append('--wall-clock')
    return command


def main():
    root = Path(__file__).resolve().parents[3]
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise SystemExit('Requires a disposable standard GitHub-hosted runner.')
    # The existing common workflow owns affected-source admission. Do not add a
    # second checkout/Git gate that can prevent the required browser evidence.
    from playwright.sync_api import sync_playwright
    output = root / 'ci-results/token-mix.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.executable_path
    environment = {**os.environ, 'COST_GUARD_TEST_PYTHON': sys.executable, 'COST_GUARD_CI_BROWSER': '1'}
    result = subprocess.run(browser_command(browser, output), cwd=root, env=environment,
                            timeout=450, check=False, capture_output=True, text=True)
    evidence = (json.loads(output.read_text(encoding='utf-8')) if output.exists() else
                dict(outcome='FAIL', error=result.stderr[-7000:]))
    summary = {key: evidence.get(key) for key in ('outcome', 'checks', 'error', 'errors', 'retained', 'cadence_ms', 'limitations')}
    print('::notice title=Token Mix browser::' + json.dumps(summary).replace('%', '%25'), flush=True)
    result.check_returncode()
    if evidence.get('outcome') != 'PASS':
        raise SystemExit('Token Mix browser evidence did not pass')
    measured = subprocess.run([sys.executable, 'development/tests/integration/probe_token_mix_baseline.py',
                              '--synthetic'], cwd=root, env=environment, timeout=120, check=True,
                              capture_output=True, text=True)
    (output.parent / 'token-mix-performance.json').write_text(measured.stdout, encoding='utf-8')
    print('::notice title=Token Mix performance::' + measured.stdout.strip().replace('%', '%25'), flush=True)
    print(measured.stdout)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        diagnostic = json.dumps(dict(outcome='FAIL', diagnostic=traceback.format_exc()[-7000:]))
        print('::error title=Token Mix failure::' + diagnostic.replace('%', '%25'), flush=True)
        raise
