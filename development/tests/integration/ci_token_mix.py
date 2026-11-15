"""Hosted-only real Chromium Token Mix regression with numeric scale evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys


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
    subprocess.run(['node', 'development/tests/integration/probe_token_mix.cjs',
                    browser, str(output), '--wall-clock'], cwd=root, env=environment, timeout=450, check=True)
    evidence = json.loads(output.read_text(encoding='utf-8'))
    if evidence.get('outcome') != 'PASS':
        raise SystemExit('Token Mix browser evidence did not pass')
    measured = subprocess.run([sys.executable, 'development/tests/integration/probe_token_mix_baseline.py',
                              '--synthetic'], cwd=root, env=environment, timeout=120, check=True,
                              capture_output=True, text=True)
    (output.parent / 'token-mix-performance.json').write_text(measured.stdout, encoding='utf-8')
    print(measured.stdout)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        diagnostic = json.dumps(dict(outcome='FAIL', diagnostic=traceback.format_exc()[-7000:]))
        print('::error title=Token Mix failure::' + diagnostic.replace('%', '%25'), flush=True)
        raise
