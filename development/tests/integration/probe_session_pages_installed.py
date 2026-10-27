"""Read-only real installation page/bounds probe; no browser, model or service stop."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from src.web.composition import application
from src.web.jobs import parse_report


def capture(value):
    request = parse_report(value)
    start = time.monotonic()
    result = application(request).execute(request).to_json()
    return result, round(time.monotonic() - start, 3)


def main():
    first, first_seconds = capture(dict(kind='sessions', session_page_size=50))
    assert first['error'] is None, first['error']
    page = first['view']['session_page']
    rows = first['view']['session_usage']
    assert len(rows) == min(50, page['total'])
    assert first['view']['request_identities'] == []
    evidence = dict(outcome='PASS', source=first['source']['generation'], source_status=first['source']['status'],
        total=page['total'], first_rows=len(rows), first_seconds=first_seconds,
        first_bytes=len(json.dumps(first, separators=(',', ':')).encode()), account_acquisitions=0)
    if page['total'] > 50:
        second, seconds = capture(dict(kind='sessions', session_page_size=50, session_offset=50,
            session_catalog_revision=page['catalog_revision']))
        if second['error']:
            assert second['error']['code'] == 'session_catalog_changed', second['error']
            evidence.update(second='catalog_changed_explicitly_rejected', second_seconds=seconds)
        else:
            older = second['view']['session_usage']
            assert not {r['session_id'] for r in rows} & {r['session_id'] for r in older}
            evidence.update(second='distinct_older_page', second_rows=len(older), second_seconds=seconds)
    output = Path(sys.argv[1])
    output.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
