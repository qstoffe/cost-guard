"""Width-adaptive status rows shown beneath a running Watch prompt."""
from __future__ import annotations

from src.watch.models import ToolObservation

BASE_ROLE = "watchToolActivity"
FAILED_ROLE = "costQuotaCritical"
SEPARATOR = " · "
_MIN_TODO_TEXT_SLOT = 7  # separator excluded: at least four characters plus "..."

Segment = tuple[str, str]


def _length(segments: list[Segment]) -> int:
    return sum(len(text) for text, _role in segments)


def _clip(segments: list[Segment], width: int) -> list[Segment]:
    if _length(segments) <= width:
        return segments
    keep = max(0, width - 3)
    clipped: list[Segment] = []
    for text, role in segments:
        if keep <= 0:
            break
        clipped.append((text[:keep], role))
        keep -= len(text[:keep])
    clipped.append(("..."[:max(0, width)], clipped[-1][1] if clipped else BASE_ROLE))
    return clipped


def _tool_candidate(tool: ToolObservation, noun: str, keep: int) -> list[Segment]:
    """Compose the total, the `keep` largest tool groups, an `other` call bucket and failures."""
    ordered = sorted(tool.tool_counts, key=lambda item: (-item[1], item[0]))
    groups = [(f"{count}× {name}", count, 0) for name, count in ordered[:keep]]
    hidden = sum(count for _name, count in ordered[keep:]) if keep else 0
    if hidden:
        groups.append((f"{hidden}× other", hidden, 1))
    groups.sort(key=lambda item: (-item[1], item[2]))
    text = SEPARATOR.join([f"{tool.tool_count} {noun}"] + [label for label, _count, _rank in groups])
    segments: list[Segment] = [(text, BASE_ROLE)]
    if tool.failed_count > 0:
        segments += [(SEPARATOR, BASE_ROLE), (f"{tool.failed_count} failed", FAILED_ROLE)]
    return segments


def tool_summary_segments(tool: ToolObservation, width: int) -> list[Segment]:
    """First status row: total, failures, then as much per-tool breakdown as fits.

    Hidden tool *calls* (not tool types) are aggregated into a sorted `N× other` group
    so the displayed groups always add up to the total.
    """
    noun = "tool call" if tool.tool_count == 1 else "tool calls"
    for keep in range(len(tool.tool_counts), 0, -1):
        candidate = _tool_candidate(tool, noun, keep)
        if _length(candidate) <= width:
            return candidate
    for short in (noun, "calls"):
        candidate = _tool_candidate(tool, short, 0)
        if _length(candidate) <= width:
            return candidate
    return _clip(_tool_candidate(tool, noun, 0), width)


def status_segments(tool: ToolObservation, width: int, running_duration: str) -> list[Segment]:
    """Optional second row: long-running tool and/or compact TODO progress and text."""
    if not tool.has_status_row:
        return []
    parts: list[str] = []
    if tool.running_tool:
        parts.append(f"running: {tool.running_tool} {running_duration}")
    if tool.has_open_todo:
        parts.append(f"TODO {tool.todo_completed}/{tool.todo_total} done")
    text = SEPARATOR.join(parts)
    if tool.has_open_todo and tool.active_todo:
        slot = width - len(text) - len(SEPARATOR)
        if slot >= len(tool.active_todo):
            text += SEPARATOR + tool.active_todo
        elif slot >= _MIN_TODO_TEXT_SLOT:
            text += SEPARATOR + tool.active_todo[: slot - 3].rstrip() + "..."
    return _clip([(text, BASE_ROLE)], width)
