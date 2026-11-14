"""Validated whole-session cost groups, shared with Mini's canonical observation."""
from decimal import Decimal

from src.analysis.session_cost import SessionCostGroup
from src.domain.effort import EffortEvidence


def decode_cost_groups(values):
    groups = []
    for part in values:
        group = SessionCostGroup(**dict(part, known_ccost=Decimal(part["known_ccost"]),
            selected_models=tuple(part["selected_models"]),
            effort_evidence=tuple(EffortEvidence(**value) for value in part["effort_evidence"])))
        if (type(group.agent) is not int or group.agent not in (0, 1)
                or not group.known_ccost.is_finite() or group.known_ccost < 0
                or type(group.priced_requests) is not int or group.priced_requests < 0
                or type(group.complete) is not bool
                or len(group.selected_models) > 64 or len(group.effort_evidence) > 64
                or any(not isinstance(text, str) or len(text) > 256 or text and not text.isprintable()
                       for text in (group.provider_id, group.model_id, group.effort, *group.selected_models))
                or any(e.selected is not None and not isinstance(e.selected, str) or
                       any(not isinstance(t, str) or len(t) > 256 or t and not t.isprintable()
                           for t in (e.selected or "", e.effective, e.source, e.revision))
                       for e in group.effort_evidence)):
            raise ValueError("invalid_session_cost_group")
        groups.append(group)
    return tuple(groups)
