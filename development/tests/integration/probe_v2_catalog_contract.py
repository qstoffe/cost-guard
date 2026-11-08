"""Read-only numeric pagination evidence through the selected V2 transport."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.sources.selection import SourceSelector
from src.sources.opencode_v2_wire import parse_page


def listing(client, *, continuation_limit):
    cursor, seen, ids, sizes = None, set(), set(), []
    started = time.monotonic()
    while True:
        query = {'cursor': cursor} if cursor else {'limit': 500, 'order': 'desc'}
        if cursor and continuation_limit:
            query['limit'] = 500
        values, following, _contract = parse_page(client.json('/api/session', query=query), label='contract probe')
        sizes.append(len(values))
        ids.update(value['id'] for value in values)
        if not values or not following:
            break
        if following in seen or len(sizes) > 10000:
            raise RuntimeError('invalid_catalog_continuation')
        seen.add(following)
        cursor = following
    digest = hashlib.sha256('\n'.join(sorted(ids)).encode()).hexdigest()
    return dict(continuation_limit=continuation_limit, pages=len(sizes), page_sizes=sizes,
        unique_sessions=len(ids), membership_sha256=digest, seconds=time.monotonic() - started)


def scoped_tree(source):
    """One small inactive tree: compare documented scoped membership with global."""
    from src.sources.opencode_v2 import _NativeSession
    from src.sources.opencode_v2_catalog import V2CatalogIndex
    from src.sources.opencode_v2_wire import session_directory
    source.refresh_observation_epoch()
    epoch = source.observation_epoch
    catalog = source._list_native_sessions(refresh=True)
    index = V2CatalogIndex(catalog)
    expected = next((tree for item in catalog if not item.data.get('parentID')
        and 2 <= len(tree := index.tree(item.data['id'])) <= 8
        and all(member.active is False for member in tree)), None)
    if expected is None:
        return dict(status='no_small_inactive_tree', tested=False)
    client = source._client()
    root_id = str(expected[0].data['id'])
    root = client.json('/api/session/' + quote(root_id, safe=''))['data']
    values, pending, pages = {root_id:root}, [root_id], 0
    while pending:
        parent = pending.pop(0)
        cursor, seen = None, set()
        while True:
            query = {'limit':500, **({'cursor':cursor} if cursor else {'parentID':parent, 'order':'desc'})}
            children, following, _contract = parse_page(client.json('/api/session', query=query), label='tree contract probe')
            pages += 1
            for child in children:
                if child.get('parentID') != parent or child['id'] in values or len(values) >= 64:
                    raise RuntimeError('scoped_membership_not_supported_or_changed')
                values[child['id']] = child
                pending.append(child['id'])
            if not children or not following:
                break
            if following in seen or len(seen) >= 10000:
                raise RuntimeError('invalid_scoped_continuation')
            seen.add(following)
            cursor = following
    active = client.json('/api/session/active')['data']
    actual = [_NativeSession(value, session_directory(value), key in active) for key, value in values.items()]
    source.refresh_observation_epoch()
    return dict(status='observed', tested=True, expected_members=len(expected), scoped_members=len(actual),
        equal_membership=set(values) == {member.data['id'] for member in expected},
        equal_canonical_revision=source._revision(actual) == source._revision(expected),
        same_observed_epoch=epoch is not None and epoch == source.observation_epoch,
        scoped_session_gets=1, scoped_child_pages=pages,
        limitation='One small stable observed tree, not mutation/move/pagination/restart proof or a production adapter.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tree', action='store_true', help='Also compare one small inactive tree via documented parentID and session GET')
    args = parser.parse_args()
    source = SourceSelector(inspect_migration_gap=False).select('v2').source
    try:
        client = source._client()
        specification = client.json('/openapi.json')
        operation = specification['paths']['/api/session']['get']
        parameters = operation['parameters']
        declared = {value['name'] for value in parameters if value['in'] == 'query'}
        if not {'limit', 'order', 'cursor'} <= declared:
            raise RuntimeError('required_pagination_parameters_not_documented')
        sizes = []
        for limit in (1, 50, 500):
            values, _cursor, _contract = parse_page(client.json('/api/session',
                query={'limit': limit, 'order': 'desc'}), label='contract probe')
            sizes.append(dict(requested_limit=limit, returned=len(values)))
        observations = [listing(client, continuation_limit=False), listing(client, continuation_limit=True)]
        result = dict(kind='supported_v2_catalog_contract', query_parameters=sorted(declared),
            schema_descriptions={value['name']:value['schema'].get('description') for value in parameters
                if value['name'] in ('limit', 'cursor', 'order')}, first_pages=sizes,
            traversals=observations, equal_membership=observations[0]['membership_sha256'] == observations[1]['membership_sha256'],
            limitation='Read-only evolving real source. Equal membership is observed, not a global transaction guarantee. '
                'No payload, raw ID, cursor, registration, endpoint or credentials are exported.')
        if args.tree:
            if 'parentID' not in declared or '/api/session/{sessionID}' not in specification['paths']:
                raise RuntimeError('scoped_membership_parameters_not_documented')
            result['scoped_tree'] = scoped_tree(source)
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))
    finally:
        source.close_reads()


if __name__ == '__main__':
    main()
