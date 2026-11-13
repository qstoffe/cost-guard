"""The single tooltip formatter. Visible effort values never pass through here."""
from src.domain.effort import EffortEvidence

NOTES = {
    "request": "Observed in the recorded request; another run's default may differ.",
    "current-configuration": "Inferred from current OpenCode model/provider configuration; historical settings may differ.",
    "current-package": "Inferred from the current OpenCode provider package; historical settings may differ.",
    "documentation": "Likely effort based on provider documentation. Defaults may change and client settings can override them.",
    "unknown": "No supported concrete effort evidence is available for this request and route.",
}


def effort_help(evidence, *, value_cell=False, explicit=""):
    if isinstance(evidence, dict):
        evidence = EffortEvidence(**evidence)
    if evidence.source == "omitted":
        return "Additional request effort evidence omitted"
    if evidence.selected is None:
        return explicit or "N/A"
    if evidence.selected and evidence.selected.lower() != "default":
        return explicit or evidence.selected
    text = f"default ({evidence.effective or 'unknown'})"
    return text + "*\n* " + NOTES.get(evidence.source, NOTES["unknown"]) if value_cell else text


def evidence_record(evidence):
    from .contracts import record
    return record(selected=evidence.selected, effective=evidence.effective,
                  source=evidence.source, revision=evidence.revision)


def evidence_help(values, *, value_cell=False, explicit=""):
    separator = "\n" if value_cell else " / "
    return separator.join(dict.fromkeys(effort_help(value, value_cell=value_cell, explicit=explicit) for value in values))
