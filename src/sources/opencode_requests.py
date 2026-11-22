"""Missing counters on an observed response are unknown usage, never zero."""
from src.domain import TokenUsage


def response_tokens(message):
    if message.tokens is not None:
        return message.tokens
    # Text/reasoning proves response execution, including an aborted partial
    # response. An empty failed/in-flight assistant does not prove dispatch.
    if any(part.kind in {"text", "reasoning"} and part.data.get("text") for part in message.parts):
        return TokenUsage(known_fields=())
    return None
