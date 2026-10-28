"""Report concept definitions above the model table: CCost, Token Mix % and Relative CCost.

Each sentence starts its own line; continuation lines hang under the first
sentence. Labels (including the colon) and the user's own live values are
emphasized; explanatory prose stays in the normal color.
"""
from __future__ import annotations
from src.numbers import ccost_unit

from dataclasses import dataclass
import re
from typing import Sequence

from src.analysis.token_mix import TokenMix

from .terminal import AnsiStyler, wrap_prose
from .token_mix import compact_tokens, mix_cells, packed_cells

DEFINITION_WIDTH = 90
LABEL_ROLE = "reportDefinitionLabel"
VALUE_ROLE = "reportDefinitionValue"
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?[KMB]?\b")


@dataclass(frozen=True, slots=True)
class ValueProse:
    """Prose whose numbers are live values; only the numbers are emphasized."""
    text: str


Sentence = str | ValueProse | tuple[str, ...]  # tuple: emphasized cells, never split


def definition_lines(label: str, sentences: Sequence[Sentence], width: int, styler: AnsiStyler,
                     *, gap: int = 1) -> list[str]:
    indent = " " * (len(label) + gap)
    limit = max(len(indent) + 1, min(DEFINITION_WIDTH, int(width)))
    lines: list[str] = []
    for sentence in sentences:
        if isinstance(sentence, tuple):
            lines.extend(indent + styler.apply(line[len(indent):], VALUE_ROLE)
                         for line in packed_cells(sentence, limit, indent=indent))
            continue
        text = sentence.text if isinstance(sentence, ValueProse) else sentence
        wrapped = wrap_prose(text, limit, initial_prefix=indent, continuation_prefix=indent)
        if isinstance(sentence, ValueProse):
            wrapped = [indent + _NUMBER.sub(lambda match: styler.apply(match.group(), VALUE_ROLE), line[len(indent):])
                       for line in wrapped]
        lines.extend(wrapped)
    if lines:
        lines[0] = styler.apply(label, LABEL_ROLE) + lines[0][len(label):]
    return lines


def ccost_sentences() -> tuple[str, ...]:
    return (
        ("CCost displays reference USD: 100 credits = $1.00; small positive values can round to $0.00."
         if ccost_unit() == "usd" else "1 CCost equals 1 Copilot AI credit."),
        "Flat-rate accounts use Copilot's published token rates, not the billed cost.",
        "Unlabeled cost figures in Cost Guard are CCost unless stated otherwise.",
        "Watch Today is CCost, not provider-native Used or actual Billed spend.",
    )


def token_mix_sentences(mix: TokenMix) -> tuple[Sentence, ...]:
    definition = "The I/C/W/O percentage split of your observed token usage."
    if not mix.request_count:
        return definition, "No priced prompts are available yet."
    count = mix.sample_size
    sample = f"Your mix uses the latest {count} priced {'prompt' if count == 1 else 'prompts'}"
    total = mix.total_tokens
    sample += f", totaling {compact_tokens(total)} tokens." if total is not None else "."
    return definition, ValueProse(sample), mix_cells(mix)


def rel_ccost_sentences(sample_size: int) -> tuple[str, ...]:
    if not sample_size:
        return ("No completed priced prompts are available yet.",
                 "Relative CCost stays blank; a hidden 2/96/1/1 mix orders published prices.")
    noun = "prompt" if sample_size == 1 else "prompts"
    return ("Common token-category workload price comparison, not a same-task benchmark or billing.",
            f"One shared I/C/W/O mix from the latest {sample_size} completed priceable {noun} globally (up to 100).",
            "Every model and tier, including untried models, uses those same pooled token shares.",
            "Not a capability/throughput benchmark or a forecast of specialized future jobs.",
            "Every tier uses the same cheapest positive comparable base price as 1.0x.",
            "Arrows show context-tier prices; > or ≥ marks the published input-token boundary.")


def concept_lines(mix: TokenMix, sample_size: int, width: int, styler: AnsiStyler) -> list[str]:
    """The three definition blocks, in order, separated by one blank line."""
    lines = definition_lines("CCost:", ccost_sentences(), width, styler, gap=2)
    lines += ["", *definition_lines("Token Mix %:", token_mix_sentences(mix), width, styler)]
    lines += ["", *definition_lines("Relative CCost:", rel_ccost_sentences(sample_size), width, styler)]
    return lines
