"""Sanitized current V2 subagent incident, acquired through the normal source."""
from contextlib import contextmanager

from .opencode_v2_service import source_with_current_service


def user(mid, at, text="work", kind="user"):
    return {"id": mid, "type": kind, "text": text, "time": {"created": at}}


def assistant(mid, at, end, *, model="gpt-test", content=None, finish="stop", count=100_000):
    return {"id": mid, "type": "assistant", "agent": "build",
        "model": {"providerID": "github-copilot", "id": model, "variant": "high" if model == "gpt-test" else "low"},
        "time": {"created": at, **({"completed": end} if end else {})},
        "finish": finish if end else None, "cost": 0,
        "tokens": {"input": count, "output": count, "reasoning": 0, "cache": {"read": count, "write": count}},
        "content": content if content is not None else [{"type": "text", "text": "done"}]}


def link(*, name="subagent", key="sessionID", child="ses_current_child", start=3200, end=3900,
         background=False, output=None):
    return {"type": "tool", "id": "link", "callID": "call-link", "name": name,
        "time": {"created": start, "ran": start, **({"completed": end} if end else {})},
        "state": {"status": "completed" if end else "running", "input": {"background": background},
            "metadata": {key: child}, "output": output or f'<subagent sessionID="{child}">done</subagent>'}}


@contextmanager
def incident_source(**link_options):
    with source_with_current_service() as (source, server, _registration):
        server.messages["ses_current"] = [user("u1", 3000),
            assistant("a1", 3100, 4000, content=[link(**link_options)], finish="tool-calls"),
            user("notice", 4100, '<subagent state="completed">done</subagent>', "synthetic"),
            assistant("a2", 4200, 4500)]
        server.messages["ses_current_child"] = [user("cu", 3300),
            assistant("ca", 3400, 3800, model="claude-test")]
        yield source, server
