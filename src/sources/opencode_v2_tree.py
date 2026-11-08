"""Web-card-only, job-local tree brackets from the documented V2 parent filter.

Complete global discovery still owns global membership and revision hints. This
owner retains only a capability bit per observed epoch between exclusive jobs;
scoped metadata lives for one job and can never populate the global catalog.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import time
from urllib.parse import quote

from .errors import (FailureCode, SourceConcurrentChangeError, SourceDataError,
                     SourceError, SourceSchemaError)
from .opencode_v2_catalog import V2CatalogIndex
from .opencode_v2_snapshot import global_bracket
from .opencode_v2_wire import fetch_active_ids, parse_page, session_directory


_SHARED_ERRORS = frozenset({FailureCode.AUTH, FailureCode.VERSION,
    FailureCode.REGISTRATION_INVALID, FailureCode.REGISTRATION_MISSING,
    FailureCode.REGISTRATION_UNREADABLE})


def _supports_tree(specification):
    if (not isinstance(specification, Mapping)
            or not isinstance(specification.get('openapi'), str)
            or not isinstance(specification.get('paths'), Mapping)):
        raise SourceSchemaError('OpenCode V2 capability specification is malformed', phase='capability')
    paths = specification['paths']
    operations = []
    for path in ('/api/session', '/api/session/{sessionID}'):
        item = paths.get(path, {})
        if not isinstance(item, Mapping):
            raise SourceSchemaError('OpenCode V2 capability path is malformed', phase='capability')
        operation = item.get('get')
        if operation is not None and not isinstance(operation, Mapping):
            raise SourceSchemaError('OpenCode V2 capability operation is malformed', phase='capability')
        operations.append(operation)
    if any(operation is None for operation in operations):
        return False
    parameters = operations[0].get('parameters', [])
    if not isinstance(parameters, list) or any(not isinstance(value, Mapping) for value in parameters):
        raise SourceSchemaError('OpenCode V2 capability parameters are malformed', phase='capability')
    for value in parameters:
        if '$ref' not in value and (not isinstance(value.get('name'), str) or not isinstance(value.get('in'), str)):
            raise SourceSchemaError('OpenCode V2 capability parameter is malformed', phase='capability')
    declared = {value.get('name') for value in parameters if value.get('in') == 'query'
                and isinstance(value.get('name'), str)}
    return {'parentID', 'limit', 'cursor'} <= declared


def _session(value, expected_id=None):
    if (not isinstance(value, Mapping) or not isinstance(value.get('id'), str) or not value['id']
            or (value.get('parentID') is not None and not isinstance(value['parentID'], str))):
        raise SourceDataError('OpenCode V2 scoped session has invalid identity or parent', phase='snapshot')
    if expected_id is not None and value['id'] != expected_id:
        raise SourceDataError('OpenCode V2 scoped session identity does not match', phase='snapshot')
    return dict(value)


def _children(source, parent):
    cursor, seen = None, set()
    while True:
        query = {'limit': 500, **({'cursor': cursor} if cursor else {'parentID': parent, 'order': 'desc'})}
        raw = source._client().json('/api/session', query=query, phase='snapshot')
        source.metrics.add('scoped_child_pages')
        values, following, _contract = parse_page(raw, label='scoped child list')
        for value in values:
            child = _session(value)
            if child.get('parentID') != parent:
                raise SourceConcurrentChangeError('OpenCode V2 scoped parent changed during listing', phase='snapshot')
            yield child
        if not values or not following:
            return
        if following in seen:
            raise SourceDataError('OpenCode V2 scoped pagination repeated a cursor', phase='snapshot')
        seen.add(following)
        cursor = following


def _tree(source, root_id):
    source.metrics.add('scoped_session_gets')
    try:
        response = source._client().json('/api/session/' + quote(root_id, safe=''), phase='snapshot')
    except SourceError as error:
        if error.code == FailureCode.HTTP and error.http_status == 404:
            raise SourceConcurrentChangeError('History root left the scoped catalog', phase='snapshot') from error
        raise
    root = _session(response.get('data') if isinstance(response, Mapping) else None, root_id)
    values, pending = {root_id: root}, deque((root_id,))
    while pending:
        parent = pending.popleft()
        for child in _children(source, parent):
            key = child['id']
            if key in values:
                ancestor = parent
                while ancestor in values:
                    if ancestor == key:
                        raise SourceDataError('OpenCode V2 scoped topology contains a cycle', phase='snapshot')
                    ancestor = values[ancestor].get('parentID')
                raise SourceConcurrentChangeError('OpenCode V2 scoped membership repeated during listing', phase='snapshot')
            values[key] = child
            pending.append(key)
    return values


class CardTreeBrackets:
    def __init__(self, source, *, reuse_seconds):
        self.source = source
        self.reuse_seconds = reuse_seconds
        self.epoch = None
        self.supported = None
        self.trees = {}

    def reset_job(self):
        self.trees.clear()

    def _capable(self):
        source = self.source
        client = source._client()
        epoch = source.observation_epoch
        if epoch is None:
            raise SourceConcurrentChangeError('Unknown service epoch during capability detection', phase='capability')
        if epoch == self.epoch and self.supported is not None:
            return self.supported
        self.reset_job()
        source.metrics.add('scoped_capability_fetches')
        try:
            supported = _supports_tree(client.json('/openapi.json', phase='capability'))
        except SourceError as error:
            # Only explicitly absent/unsupported spec routes permit compatibility.
            if error.code != FailureCode.HTTP or error.http_status not in (404, 405, 501):
                raise
            supported = False
        source.refresh_observation_epoch()
        if epoch != source.observation_epoch:
            raise SourceConcurrentChangeError('Service epoch changed during capability detection', phase='capability')
        self.epoch, self.supported = epoch, supported
        return supported

    def bracket(self, root_ids, *, allow_reuse, failures=None):
        source = self.source
        if not self._capable():
            return global_bracket(source, root_ids, allow_reuse=allow_reuse, failures=failures)
        cached, index = source._catalog_cache, source._catalog_index
        if (allow_reuse and cached is not None and index is not None
                and time.monotonic() - source._catalog_listed_at <= self.reuse_seconds
                and all(root in index.by_id for root in root_ids)):
            source.metrics.add('snapshot_catalog_reuses')
            source._diagnostics['snapshot_catalog_reuses'] += 1
            # Even a valid global before observation must not acquire scoped
            # memoized revisions or masquerade as a refreshed global index.
            return V2CatalogIndex(cached), True
        with source.metrics.measure('scoped_catalog'):
            index = self._acquire(root_ids, failures)
        for root in root_ids:
            self.trees[root] = {item.data['id']: item for item in index.tree(root)} if root in index.by_id else {}
        return index, False

    def _acquire(self, root_ids, failures):
        from .opencode_v2 import _NativeSession
        source = self.source
        source.metrics.add('scoped_catalog_brackets')
        values = {}
        for root in root_ids:
            try:
                tree = _tree(source, root)
            except SourceError as error:
                if failures is None or error.code in _SHARED_ERRORS:
                    raise
                failures[root] = error
            else:
                for key, value in tree.items():
                    if key in values and values[key] != value:
                        raise SourceConcurrentChangeError('OpenCode V2 overlapping trees changed', phase='snapshot')
                    values[key] = value
        active = fetch_active_ids(source._client())
        return V2CatalogIndex([_NativeSession(value, session_directory(value),
            None if active is None else key in active) for key, value in values.items()])

    def directory(self, session_id):
        self.source.refresh_observation_epoch()
        if self.epoch != self.source.observation_epoch:
            return ''
        for tree in self.trees.values():
            if session_id in tree:
                return tree[session_id].directory
        return ''
