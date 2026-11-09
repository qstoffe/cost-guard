"""Hidden synthetic DOM/restart proof using canonical projections and shipped assets."""
import argparse
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from development.tests.fixtures.claude_alias import LABEL, service
from src.application.projection import project
from src.reports import ReportKind, ReportRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('browser', type=Path)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    assert args.browser.is_file() and args.evidence.parent.is_dir()
    test = unittest.TestCase()
    try:
        original = service(test)
        result = dict(view=project(original.build(ReportRequest(ReportKind.COMPARISONS))).to_json())
    finally:
        test.doCleanups()
    assets = ROOT / 'src/web/assets'
    scripts = ''.join('<script>' + (assets / name).read_text(encoding='utf-8') + '</script>'
        for name in ('help.js', 'render.js', 'comparisons.js'))
    checks = []
    with tempfile.TemporaryDirectory(dir=args.evidence.parent, prefix='alias-dom-') as directory:
        root = Path(directory)
        page = root / 'alias.html'
        page.write_text('<!doctype html><meta charset="utf-8"><body>' + scripts + '''<script>
const result = ''' + json.dumps(result).replace('<', '\\u003c') + ''';
const view = new ComparisonsView.View(() => {});
view.attach(document.body);
view.update({result, withheld:false, loading:false});
const row = document.querySelector('tr[data-session="root-0000"]');
const before = row.children[2].textContent;
view.update({result:structuredClone(result), withheld:false, loading:false});
row.children[2].firstChild.focus();
setTimeout(() => {
  const output = document.createElement('pre'); output.id = 'probe-result';
  output.textContent = JSON.stringify({label:row.children[2].textContent,
    stable:before===row.children[2].textContent && row.isConnected,
    help:document.getElementById('context-help')?.textContent || ''});
  document.body.append(output);
}, 1000);
</script>''', encoding='utf-8')
        for _restart in range(2):
            completed = subprocess.run([str(args.browser), '--headless=new', '--no-first-run',
                '--no-default-browser-check', '--disable-extensions', '--disable-background-networking',
                '--user-data-dir=' + str(root / 'profile'), '--virtual-time-budget=2000',
                '--dump-dom', page.as_uri()], capture_output=True, text=True, encoding='utf-8',
                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
            assert completed.returncode == 0, 'browser_failed'
            match = re.search(r'<pre id="probe-result">(.*?)</pre>', completed.stdout, re.S)
            assert match, 'missing_dom_result'
            value = json.loads(html.unescape(match[1]))
            assert value['label'] == 'claude-agent/' + LABEL and value['stable'], value
            assert LABEL in value['help'] and '[sonnet]' in value['help'], value
            assert 'Claude Sonnet 4' not in value['label'] + value['help'], value
            checks.append(value)
    args.evidence.write_text(json.dumps(dict(outcome='PASS', restarts=checks), indent=2), encoding='utf-8')
    print(json.dumps(dict(outcome='PASS', browser_restarts=len(checks), stable_alias_label=True,
        raw_identity_help=True, source='synthetic canonical V2; shipped renderer/help assets')))


if __name__ == '__main__':
    main()
