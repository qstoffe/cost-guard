"""Request identity copy from recorded selectors, never labels or pricing guesses."""
from src.domain.model_identity import CATALOG_ESTIMATE_HELP, catalog_display_name
from src.reports.model_details import selected_effort

from .effort_help import effort_help


def linked_selection_help(item):
    if not item.linked_model_selections:
        return ""
    return ("Selected/attempted subagents\n" + "\n".join("• " + line for line in item.linked_model_selections)
        + "\nRecorded selection only; not a confirmed executed contributor.")


def fixture_help(provider, model):
    return "Local scripted fixture; not a billed model consultation." if (provider, model) == ("fixture", "scripted") else ""


def attribution_label(basis):
    return {"inferred": "Linked by prompt timing",
            "mixed": "Verified and timing-inferred work"}.get(basis, "")


def prompt_display_help(row):
    """Consumer identity copy from structured row facts, not cost-help text."""
    label = row.watch_model or row.model_effort or "N/A"
    if row.watch_effort and row.watch_effort != "N/A":
        label += " · " + row.watch_effort
    if row.recorded_selections:
        label += "\nSelected model · no request usage recorded"
    lines = [label]
    for part in row.cost_parts[:24]:
        role = "Main prompt" if not part.agent else f"Subagent {part.agent}"
        if 0 < part.agent <= len(row.agent_coverage):
            if basis := attribution_label(row.agent_coverage[part.agent - 1].attribution):
                role += f" ({basis})"
        name = catalog_display_name(part.provider_id, part.model)
        identity = f"{part.provider_id}/{name}" if part.provider_id else name
        efforts = " / ".join(dict.fromkeys(effort_help(e) for e in part.effort_evidence))
        effort = efforts or part.effort
        lines.append(f"{role} — {identity}" + (f" · {effort}" if effort and effort != "N/A" else ""))
        if fixture_help(part.provider_id, part.model_id):
            lines.append(fixture_help(part.provider_id, part.model_id))
    if row.linked_model_selections:
        lines.append(linked_selection_help(row))
    elif row.linked_agent_count and not any(part.agent for part in row.cost_parts):
        lines.append("Subagents — model unknown")
    return "\n".join(dict.fromkeys(lines))


def session_display_help(item):
    main, agents = [], []
    remaining = 32_000
    for models, lines in ((item.main_models, main), (item.subagent_models, agents)):
        omitted = False
        for part in models:
            label = f"{part.provider}/{part.display_model or part.model}"
            if part.display_model and part.display_model != part.model:
                label += f" [recorded: {part.model}]"
            efforts = {}
            for evidence in part.efforts:
                key = selected_effort(evidence.selected)
                if key == "default":
                    text = evidence.effective or "unknown"
                else:
                    text = evidence.selected or "Effort unknown"
                efforts.setdefault(key, {})[text] = None
            for key, details in efforts.items() or [(None, ("Effort unknown",))]:
                if key == "default":
                    effort = "Default (" + ", ".join(details) + ")"
                else:
                    effort = next(iter(details))
                bullet = f"• {label} — {effort}"
                if note := fixture_help(part.provider, part.model):
                    bullet += " (" + note + ")"
                if len(bullet) + 1 > remaining:
                    omitted = True
                    continue
                lines.append(bullet)
                remaining -= len(bullet) + 1
        if omitted:
            lines.append("Additional observed combinations are not shown.")
    if not item.main_models:
        if item.selected_display_model:
            main.append(f"Selected: {item.selected_model_id} {item.selected_effort}".rstrip()
                        + " — no request usage recorded.")
        else:
            main.append("No executed session model is verified.")
    if not item.subagent_models:
        agents.append("No subagent model was used." if item.contributor_models_complete and not item.linked_agent_count
                      else "No executed subagent model is verified.")
    agents.extend(f"Selected/attempted: {selection} — execution not verified."
                  for selection in item.linked_model_selections)
    if not item.contributor_models_complete:
        for lines in (main, agents):
            lines.append("Observed model coverage may be incomplete.")
    return "Session Models:\n" + "\n".join(main) + "\n\nSub Agents:\n" + "\n".join(agents)


def request_model_help(provider, recorded, *, catalog_model=None):
    identities = tuple(sorted({f'{provider}/{model}' for model in recorded if provider and model}))
    text = ', '.join(identities[:64]) or 'Unrecorded model — provider/model identity unavailable'
    if len(identities) > 64:
        text += f'\n{len(identities) - 64} additional recorded selections not shown.'
    if catalog_model:
        text += f'\nCatalog modelID: {catalog_model}\n{CATALOG_ESTIMATE_HELP}'
    return text


def session_model_tokens(values):
    if 'model_help' in values:
        return {'model_help': values['model_help']}
    if 'contributor_models' not in values:
        return {}
    models = values['contributor_models']
    text = '\n'.join(models) or 'Contributing model identities are not available.'
    if not values.get('contributor_models_complete'):
        text += '\nObserved so far; contributing model coverage may be incomplete.'
    return {'model_help': text}


def session_model_help(item):
    sections = []
    remaining = 32_000
    omitted = False
    for heading, models in (("Main models used in session", item.main_models),
                            ("Sub-agents used in session", item.subagent_models)):
        if not models:
            continue
        lines = []
        for part in models:
            text = request_model_help(part.provider, (part.model,), catalog_model=part.catalog_model)
            if fixture_help(part.provider, part.model):
                text += "\n" + fixture_help(part.provider, part.model)
            details = [effort_help(evidence) for evidence in part.efforts if evidence.selected is not None]
            if details:
                text += "\nEffort: " + "; ".join(dict.fromkeys(details))
            bullet = "• " + text.replace("\n", "\n  ")
            if len(bullet) > remaining:
                omitted = True
                continue
            lines.append(bullet)
            remaining -= len(bullet) + 1
        if lines:
            sections.append(heading + "\n" + "\n".join(lines))
    if not item.main_models:
        if item.selected_display_model:
            effort = f" · {item.selected_effort.capitalize()}" if item.selected_effort else ""
            sections.insert(0, f"Selected model: {item.selected_display_model}{effort}"
                f"\nRecorded selection: {item.selected_model_id}\nNo request usage recorded for this selection.")
        else:
            sections.insert(0, "No attributable executed main-thread model is available.")
    if item.linked_model_selections:
        sections.append(linked_selection_help(item))
    elif item.linked_agent_count and not item.subagent_models:
        sections.append("Linked subagents\n• Model/effort unreported; execution and usage unverified.")
    if omitted:
        sections.append("Additional model details omitted at the bounded help limit.")
    if not item.contributor_models_complete or omitted:
        sections.append("Observed so far; contributing model coverage may be incomplete.")
    return "\n\n".join(sections)
