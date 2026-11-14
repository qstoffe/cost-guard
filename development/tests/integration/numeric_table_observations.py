"""Count-only numeric presentation checks on already-authorized Live exports."""
import re


def observe_numeric_tables(value):
    counts = dict(numeric_cost_tokens=0, incomplete_records=0)
    prefix = re.compile(r"\?\s*(?:\$|[<+\-\d])")

    def visit(item):
        if isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, dict):
            if item.get("complete") is False or item.get("unresolved_cost") or item.get("cost_complete") is False:
                counts["incomplete_records"] += 1
            displays = [item.get("display", {}), *item.get("display_units", {}).values()]
            for display in displays:
                for key, text in display.items():
                    if not isinstance(text, str) or not ("cost" in key or key == "total_tokens"):
                        continue
                    # Independent quota reference/estimate notation is outside this audit.
                    if "capacity" in key or "remaining" in key or "help" in key:
                        continue
                    assert not prefix.search(text), "numeric table uncertainty prefix"
                    assert not text.startswith("Partial "), "replacement cost decoration"
                    if re.search(r"\d", text):
                        counts["numeric_cost_tokens"] += 1
            for key, child in item.items():
                if key not in {"display", "display_units", "accounts"}:
                    visit(child)
    visit(value)
    return counts
