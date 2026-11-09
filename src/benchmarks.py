"""Optional public Harbor aggregate adapter; never a pricing or history source.

Harbor explicitly documents unauthenticated leaderboard display on other sites.
Only the fixed Terminal-Bench 4.0 board is read; no task artifacts are downloaded.
"""
from dataclasses import dataclass
from datetime import date as calendar_date
from decimal import Decimal
import http.client
import json
import re
import time
from urllib.parse import urlsplit

SOURCE_URL = 'https://hub.harborframework.com/datasets/terminal-bench/terminal-bench/4'
BOARD_ID = '9f966760-00f1-424e-90f5-c964fb6f6091'
DATASET_ID = '1922072f-a433-429a-8929-350d5e1bcf02'
MAX_BYTES = 2 * 1024 * 1024
MAX_PAGES = 10
MAX_ROWS = 1000


@dataclass(frozen=True, slots=True)
class BenchmarkRow:
    id: str
    model: str
    publisher: str
    publisher_url: str
    model_url: str
    client: str
    client_url: str
    effort: str
    date: str
    client_version: str
    total_cost: Decimal | None
    trials: int
    solved: Decimal

    @property
    def usd_per_task(self):
        return self.total_cost / self.trials if self.total_cost is not None else None


@dataclass(frozen=True, slots=True)
class BenchmarkSnapshot:
    fetched_at_ms: int
    rows: tuple[BenchmarkRow, ...]


def label(value, *, optional=False):
    if optional and value is None:
        return ''
    if (not isinstance(value, str) or len(value) > 300 or not optional and not value.strip()
            or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('benchmark_label')
    return value.strip()


def https_url(value):
    value = label(value)
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('benchmark_url')
    return value


def number(value, *, maximum=Decimal('1e12')):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('benchmark_number')
    result = Decimal(str(value))
    if not result.is_finite() or not 0 <= result <= maximum:
        raise ValueError('benchmark_number')
    return result


def parse_row(value):
    meta, metrics = value['metadata'], value['metrics']
    if value.get('status') != 'display' or value.get('leaderboard_id') != BOARD_ID:
        raise ValueError('benchmark_row_identity')
    identity = label(value['id'])
    if not re.fullmatch(r'[a-f0-9-]{36}', identity):
        raise ValueError('benchmark_row_identity')
    model, client, publisher = (meta[key] for key in ('model_display', 'agent_display', 'model_org'))
    trials = number(metrics['n_trials'], maximum=Decimal(1_000_000))
    if trials < 1 or trials != int(trials) or number(value.get('n_trials', trials)) != trials:
        raise ValueError('benchmark_trials')
    trials = int(trials)
    date = label(meta['date'])
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
        raise ValueError('benchmark_date')
    calendar_date.fromisoformat(date)
    cost = number(metrics['total_cost_usd'])
    # Official display metadata can qualify an otherwise numeric total as partial.
    # Keep the configuration/score, but never divide an incomplete cost by all trials.
    if any('partial' in str(metrics.get(key, '')).casefold() for key in ('display_cost', 'display_total_cost_usd')):
        cost = None
    return BenchmarkRow(identity, label(model['label']), label(publisher['label']), https_url(publisher['url']),
        https_url(model['url']), label(client['label']), https_url(client['url']),
        label(meta.get('reasoning_effort', ''), optional=True), date,
        label(meta.get('agent_version', ''), optional=True), cost, trials, number(metrics['accuracy'], maximum=Decimal(100)))


def parse_pages(pages, fetched_at_ms):
    if type(fetched_at_ms) is not int or fetched_at_ms <= 0 or not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
        raise ValueError('benchmark_snapshot')
    rows, ids, baseline = [], set(), None
    for index, page in enumerate(pages, 1):
        board, pagination = page['leaderboard'], page['pagination']
        if (board['id'] != BOARD_ID or board['package'] != 'terminal-bench/terminal-bench'
                or board['name'] != '4-0-0' or board.get('dataset_version_ids') != [DATASET_ID]
                or board.get('visibility') != 'public'):
            raise ValueError('benchmark_edition')
        # Score scale is part of this board's published schema, not a heuristic.
        score = board['metrics_schema']['properties']['accuracy']
        if score.get('minimum') != 0 or score.get('maximum') != 100:
            raise ValueError('benchmark_score_scale')
        signature = (board, pagination['total'], pagination['total_pages'], pagination['page_size'])
        if baseline is not None and signature != baseline:
            raise ValueError('benchmark_changed_during_pagination')
        baseline = signature
        total, size, count = pagination['total'], pagination['page_size'], pagination['total_pages']
        if (any(type(n) is not int for n in (total, size, count, pagination['page']))
                or not 1 <= total <= MAX_ROWS or not 1 <= size <= 100 or count != len(pages)
                or count != (total + size - 1) // size or pagination['page'] != index
                or not isinstance(page['rows'], list) or len(page['rows']) != min(size, total - (index - 1) * size)):
            raise ValueError('benchmark_incomplete_pages')
        for value in page['rows']:
            row = parse_row(value)
            if row.id in ids:
                raise ValueError('benchmark_duplicate_row')
            ids.add(row.id)
            rows.append(row)
    return BenchmarkSnapshot(fetched_at_ms, tuple(rows))


def read_page(page, remaining, deadline):
    """Fixed HTTPS POST, verified TLS, no redirect, cookie, key or local payload."""
    timeout = min(5, deadline - time.monotonic())
    if timeout <= 0:
        raise TimeoutError('benchmark_deadline')
    connection = http.client.HTTPSConnection('api.harborframework.com', timeout=timeout)
    try:
        body = json.dumps(dict(package='terminal-bench/terminal-bench', name='4-0-0', page=page, page_size=100))
        connection.request('POST', '/functions/v1/leaderboard-read', body=body,
            headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'Cost-Guard public leaderboard reader'})
        response = connection.getresponse()
        if response.status != 200 or response.getheader('Content-Type', '').split(';')[0] != 'application/json':
            raise ValueError('benchmark_response')
        data = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('benchmark_deadline')
            chunk = response.read1(min(65536, remaining - len(data) + 1))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > remaining:
                raise ValueError('benchmark_response_size')
        return json.loads(data, object_pairs_hook=unique_fields, parse_float=source_float), len(data)
    finally:
        connection.close()


def unique_fields(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('benchmark_duplicate_field')
        value[key] = item
    return value


def source_float(value):
    result = float(value)
    if result == 0 and Decimal(value) != 0:
        raise ValueError('benchmark_numeric_underflow')
    return result


def fetch_snapshot(*, reader=read_page, clock=time.time):
    deadline, pages, remaining = time.monotonic() + 20, [], MAX_BYTES
    first, used = reader(1, remaining, deadline)
    pages.append(first)
    remaining -= used
    count = first['pagination']['total_pages']
    if type(count) is not int or not 1 <= count <= MAX_PAGES:
        raise ValueError('benchmark_page_limit')
    for page in range(2, count + 1):
        value, used = reader(page, remaining, deadline)
        remaining -= used
        pages.append(value)
    fetched = int(clock() * 1000)
    snapshot = parse_pages(pages, fetched)
    # Drop upstream user IDs and all unrelated metadata before IPC/disk.
    clean = []
    for page in pages:
        board = page['leaderboard']
        clean.append(dict(leaderboard={key: board[key] for key in
            ('id', 'package', 'name', 'dataset_version_ids', 'visibility', 'updated_at', 'metrics_schema')},
            pagination=page['pagination'], rows=[dict(id=row['id'], leaderboard_id=row['leaderboard_id'],
                status=row['status'], metadata={key: row['metadata'][key] for key in
                    ('model_display', 'agent_display', 'model_org', 'date', 'reasoning_effort', 'agent_version') if key in row['metadata']},
                metrics={key: row['metrics'][key] for key in
                    ('total_cost_usd', 'n_trials', 'accuracy', 'display_cost', 'display_total_cost_usd') if key in row['metrics']})
                for row in page['rows']]))
    return dict(schema=1, fetched_at_ms=snapshot.fetched_at_ms, pages=clean)
