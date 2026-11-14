"""Plain-English copy from bounded reason facts; no model matching or valuation."""
from src.domain.reference_cost import ReferenceCostIssue, bounded_issues
from .contracts import record

FALLBACK = "CCost cannot be calculated from the available model pricing and usage information. Display zero is not proof of zero cost."


def issue_records(issues):
    return tuple(record(reason=item.reason, model=item.model, detail=item.detail) for item in bounded_issues(issues))


def unavailable_help(issues):
    lines = []
    for issue in issues:
        values = dict(issue.fields)
        reason, model, detail = (values.get(key, "") for key in ("reason", "model", "detail"))
        if reason == "model_absent" and model:
            line = f"{model} has no listed reference price in the available GitHub Copilot model price list."
        elif reason == "identity":
            line = "A contributing model could not be matched to a verified reference price."
        elif reason == "rate":
            line = "A required reference rate is unavailable" + (f" ({detail})" if detail else "") + "."
        elif reason == "usage":
            line = "Required usage information is missing or unsupported" + (f" ({detail})" if detail else "") + "."
        elif reason == "catalog":
            line = "Reference price data cannot currently be checked; the catalog is unavailable, unverified or retained after a failed refresh."
        else:
            line = "Available model pricing and usage information cannot establish all contributing costs."
        lines.append(line)
    return ("CCost can't be calculated: " + " ".join(dict.fromkeys(lines)) + " Display zero is not proof of zero cost.") if lines else FALLBACK


def cost_help_tokens(values):
    issues = values.get("ccost_unavailable")
    if issues is None:
        comparison = values.get("comparison_cost")
        issues = dict(comparison.fields).get("ccost_unavailable", ()) if comparison else None
    # Empty reason sets need no repeated boilerplate on every fully priced row.
    # Consumers still have a generic explanation for genuinely missing amounts.
    return {} if not issues else {"ccost_unavailable_help": unavailable_help(issues)}
