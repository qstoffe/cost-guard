"""Approval-only headless browser capture of the synthetic offline design gallery.

This optional evidence tool grants no UI authority. Supply an installed browser
and an isolated current-owned scratch profile; no downloads or user profiles.
"""
import argparse
import html
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--browser', type=Path, required=True)
parser.add_argument('--profile', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
output = args.output.resolve()
evidence = []
for view in ('overview', 'watch', 'sessions', 'models', 'accounts'):
    for theme, width in (('light', '1440px'), ('dark', '1440px'), ('light', '360px'), ('dark', '360px')):
        name = view + '-' + theme + '-' + width
        page = output.joinpath('index.html').as_uri() + '?view=' + view + '&theme=' + theme + '&width=' + width
        result = subprocess.run([
            str(args.browser),
            '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
            '--user-data-dir=' + str(args.profile.resolve()), '--allow-file-access-from-files',
            '--window-size=' + ('3100,1400' if width == '1440px' else '1600,1400'),
            '--force-prefers-reduced-motion', '--virtual-time-budget=2000', '--dump-dom',
            '--screenshot=' + str(output / (name + '.png')), page],
            capture_output=True, timeout=40)
        assert result.returncode == 0, (name, result.returncode)
        match = re.search(r'<pre id="audit">(.*?)</pre>', result.stdout.decode('utf-8'), re.S)
        assert match, name
        facts = json.loads(html.unescape(match[1]))
        assert facts['tableParity'], (name, facts)
        assert facts['facts'][1]['scrollWidth'] <= facts['facts'][1]['width'], (name, facts)
        expected = '#0c1422' if theme == 'dark' else '#eef2f8'
        assert facts['facts'][1]['background'] == expected, (name, facts)
        assert facts['facts'][1]['focusVisible'], (name, facts)
        assert facts['facts'][1]['reducedMotion'], (name, facts)
        assert facts['facts'][1]['transition'] == '0s', (name, facts)
        assert facts['facts'][1]['stickyHeading'] == 'sticky', (name, facts)
        if width == '360px':
            assert facts['facts'][1]['width'] <= 360, (name, facts)
        evidence.append(dict(view=view, theme=theme, facts=facts))
        print(name, 'PASS', flush=True)
(output / 'rendered-facts.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
