"""One reusable native V2 catalog topology and memoized tree revisions."""
from __future__ import annotations

from collections import deque
from typing import Any, Callable, Sequence

from .errors import SourceDataError


class V2CatalogIndex:
    def __init__(self, sessions: Sequence[Any]) -> None:
        self.by_id = {str(item.data["id"]): item for item in sessions}
        self.children: dict[str, list[str]] = {}
        self.revisions: dict[str, str] = {}
        for session_id, item in self.by_id.items():
            parent = item.data.get("parentID")
            if parent not in (None, ""):
                self.children.setdefault(str(parent), []).append(session_id)
        for children in self.children.values():
            children.sort()

    def tree(self, root_id: str) -> list[Any]:
        if root_id not in self.by_id:
            raise SourceDataError("OpenCode V2 session does not exist")
        result = []
        pending = deque((root_id,))
        seen: set[str] = set()
        while pending:
            session_id = pending.popleft()
            if session_id in seen:
                continue
            seen.add(session_id)
            result.append(self.by_id[session_id])
            pending.extend(self.children.get(session_id, ()))
        return result

    def revision(self, root_id: str, calculate: Callable[[Sequence[Any]], str]) -> str:
        if root_id not in self.revisions:
            self.revisions[root_id] = calculate(self.tree(root_id))
        return self.revisions[root_id]
