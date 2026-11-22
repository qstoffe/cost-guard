"""Source-free, paged physical requests and root causal edges from a V1 pin."""
from collections import deque
from dataclasses import dataclass

from src.cache.display_requests import DisplayRequest
from src.sources.errors import SourceDataError

from .request_archive_projection import physical_request_key, project_request
from .v1_scoped_calls import CALL_ROWS


@dataclass(frozen=True, slots=True)
class ProjectionPage:
    requests: tuple[DisplayRequest, ...] = ()
    attribution: tuple[tuple[bytes, str], ...] = ()


_WORKING = ProjectionPage()


class V1ArchiveProjection:
    """Consume a fresh captured trace; only None seals this stream as exhausted.

    Each turn advances one bounded operation. A skipped/empty page is not EOF.
    This stream deliberately carries no Detail, Stats, or completeness claims.
    """
    def __init__(self, trace, reference):
        self._root, self._source = trace.acquisition_scope()
        self._trace, self._reference = trace, reference
        self._phase = "prepare"
        self._prompts = deque()
        self._after_prompt = None
        self._prompt = None
        self._calls = None
        self._edges = []

    def turn(self):
        if self._phase == "invalid":
            raise SourceDataError("V1 request projection is incomplete", phase="archive")
        try:
            if self._phase == "prepare":
                if self._trace.prepare_turn():
                    self._phase = "requests"
                return _WORKING
            if self._phase == "requests":
                return self._requests()
            if self._phase == "launches":
                if self._trace.qualify_child_launch_turn():
                    self._phase = "attribution"
                return _WORKING
            if self._phase == "attribution":
                return self._attribution()
            return None
        except BaseException:
            self._phase = "invalid"
            raise

    def _requests(self):
        page = self._trace.trace_turn()
        if page is None:
            self._phase = "launches"
            return _WORKING
        requests = []
        for row in page:
            entry = row.entry
            request = project_request(entry, self._key(entry), self._reference,
                                      prompt=row.executing_prompt_id, tree=self._root)
            if request is None:
                raise SourceDataError("V1 request projection has invalid valuation", phase="archive")
            requests.append(request)
        return ProjectionPage(requests=tuple(requests))

    def _attribution(self):
        if self._calls is not None:
            calls = self._calls.turn()
            if calls is None:
                self._calls = None
                return _WORKING
            self._edges.extend((self._key(call), self._prompt) for call in calls)
            return self._emit_edges() if len(self._edges) >= CALL_ROWS else _WORKING
        if not self._prompts:
            self._prompts.extend(self._trace.root_prompt_page(self._after_prompt))
            if not self._prompts:
                self._phase = "done"
                return self._emit_edges() if self._edges else None
        self._after_prompt = self._prompts.popleft()
        _, self._prompt = self._after_prompt
        self._calls = self._trace.root_prompt_calls(self._prompt)
        return _WORKING

    def _emit_edges(self):
        edges = tuple(self._edges[:CALL_ROWS])
        del self._edges[:CALL_ROWS]
        return ProjectionPage(attribution=edges)

    def _key(self, call):
        key = physical_request_key(call, source_instance=self._source)
        if key is None:
            raise SourceDataError("V1 request projection has no physical identity", phase="archive")
        return key
