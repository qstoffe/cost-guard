"""Width-adaptive status rows shown beneath the latest Watch prompt."""
from __future__ import annotations

from src.watch.models import ToolObservation

BASE_ROLE = "watchToolActivity"
FAILED_ROLE = "costQuotaCritical"
SKILL_ROLE = BASE_ROLE  # Compatibility alias; all normal activity uses the unified role.
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
    # Retain both counts before spending scarce columns on words or tool groups.
    if tool.failed_count:
        compact = [(str(tool.tool_count), BASE_ROLE), (" · ", BASE_ROLE), (f"{tool.failed_count} failed", FAILED_ROLE)]
        if _length(compact) <= width:
            return compact
        compact[-1] = (f"{tool.failed_count}!", FAILED_ROLE)
        if _length(compact) <= width:
            return compact
        compact[1] = (" ", BASE_ROLE)
        if _length(compact) <= width:
            return compact
    return [(str(tool.tool_count)[:max(0, width)], BASE_ROLE)]


def _skill_failure_label(count: int) -> str:
    noun = "tool call failure" if count == 1 else "tool call failures"
    return f" [{count} {noun}]" if count else ""


def _skill_prefix_lengths(tool: ToolObservation, with_failures: bool) -> list[int]:
    """Size each whole-skill prefix once; width choice must not build N candidate rows."""
    lengths = [len(f"Skills ({len(tool.skills)}): ")]
    for index, skill in enumerate(tool.skills):
        size = len(skill.skill_id) + (len(SEPARATOR) if index else 0)
        if with_failures:
            size += len(_skill_failure_label(skill.failed_count))
        lengths.append(lengths[-1] + size)
    return lengths


def _skill_candidate(tool: ToolObservation, keep: int, with_failures: bool) -> list[Segment]:
    segments = [(f"Skills ({len(tool.skills)}): ", BASE_ROLE)]
    for index, skill in enumerate(tool.skills[:keep]):
        if index:
            segments.append((SEPARATOR, BASE_ROLE))
        segments.append((skill.skill_id, BASE_ROLE))
        if with_failures and skill.failed_count:
            segments.append((_skill_failure_label(skill.failed_count), FAILED_ROLE))
    omitted = len(tool.skills) - keep
    if omitted:
        segments.extend([(SEPARATOR if keep else "", BASE_ROLE), (f"+{omitted} more", BASE_ROLE)])
    return segments


def skill_summary_segments(tool: ToolObservation, width: int) -> list[Segment]:
    """Whole IDs/indicators only; omit older skills with an exact distinct count."""
    if not tool.skills:
        return []
    for failures in (True, False):
        lengths = _skill_prefix_lengths(tool, failures)
        for keep in range(len(tool.skills), 0, -1):
            omitted = len(tool.skills) - keep
            suffix_size = len(SEPARATOR + f"+{omitted} more") if omitted else 0
            if lengths[keep] + suffix_size <= width:
                return _skill_candidate(tool, keep, failures)
    candidate = _skill_candidate(tool, 0, False)
    if _length(candidate) <= width:
        return candidate
    for label in (f"Skills ({len(tool.skills)})", f"Skills {len(tool.skills)}", str(len(tool.skills))):
        if len(label) <= width:
            return [(label, BASE_ROLE)]
    return [(str(len(tool.skills))[:max(0, width)], BASE_ROLE)]


def background_label(kinds: tuple[str, ...]) -> str:
    """One job names its kind; several summarize as a count, never native IDs."""
    if len(kinds) == 1:
        return kinds[0]
    return f"{len(kinds)}× {kinds[0]}" if len(set(kinds)) == 1 else f"{len(kinds)} jobs"


def status_segments(tool: ToolObservation, width: int, running_duration: str, background_duration: str = "") -> list[Segment]:
    """Optional second row: long-running tool, background wait and/or compact TODO progress and text."""
    if not tool.has_status_row:
        return []
    parts: list[str] = []
    if tool.running_tool:
        parts.append(f"running: {tool.running_tool} {running_duration}")
    if tool.background_kinds:
        parts.append(f"background: {background_label(tool.background_kinds)} {background_duration}".rstrip())
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
