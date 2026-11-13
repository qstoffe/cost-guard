"""Session Effort value help; raw selected identifiers remain the sort identity."""
from .effort_help import effort_help


def session_effort_help(item):
    lines = [f"{part.provider}/{part.model}: {effort_help(part.evidence, value_cell=True)}"
             f"\n{part.requests} observed request{'s' if part.requests != 1 else ''}."
             for part in item.effort_contributors]
    if not item.effort_details_complete:
        lines.append("Some request effort attribution is unavailable or additional contributors were omitted.")
    return "\n\n".join(lines) or "No attributable executed request effort is available."
