"""Count validated published invocation identities without exporting private text."""
import json


def observe_invocations(view):
    seen = set()
    base = {"identity", "revision", "text", "qualification"}
    for card in view.get("active_cards", []):
        for row in card["rows"]:
            activity = row.get("tool") or {}
            for mode in ("running", "background"):
                plural = activity.get(mode + "_invocations") or []
                singular = activity.get(mode + "_invocation")
                for detail in plural or ([singular] if singular else []):
                    assert card["state"] == "observed" and row["prompt"]["in_progress"]
                    assert not row["prompt"]["execution_unverified"]
                    expected = base | {"kind", "started_at_ms", "mode", "display"} if plural else base
                    assert set(detail) == expected
                    assert len(detail["identity"]) == len(detail["revision"]) == 64
                    assert len(json.dumps(detail)) < 10_000
                    assert isinstance(detail["text"], str) and isinstance(detail["qualification"], str)
                    assert detail["text"] or detail["qualification"], "input or factual absence reason"
                    if plural:
                        assert isinstance(detail["kind"], str)
                        assert detail["mode"] in {"foreground", "background"}
                        assert type(detail["started_at_ms"]) is int and detail["started_at_ms"] >= 0
                        assert set(detail["display"]) == {"started_at_ms"}
                    seen.add((card["session_id"], detail["identity"]))
    return len(seen)
