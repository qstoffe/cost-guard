"""Canonical first-prompt projection and compact private match-index codec."""
from dataclasses import fields
from decimal import Decimal
import re

from src.analysis.input_identity import first_input, fingerprint
from src.analysis.matched_runs import MatchedRun
from src.analysis.token_mix import MIX_FIELDS
from src.analysis.valuation import comparison_cost, unique_usage
from .prompt_rows import PromptRowProjector

DECIMALS = ('ccost', 'main_ccost', 'subagent_ccost', 'incoming_context_ccost', 'extra_ccost')


def project_run(snapshot, bundle, reference, config):
    message = first_input(snapshot)
    identity = fingerprint(message)
    if identity is None:
        return None
    record = next((prompt for prompt in bundle.prompts if prompt.prompt_id == message.message_id), None)
    if record is None:
        return None
    row = PromptRowProjector(snapshot=snapshot, bundle=bundle, catalog=reference, config=config).prompt(record)
    entries = unique_usage(record.entries)
    valuation = comparison_cost(entries, reference.reference_valuation)
    known = bool(entries) and all(all(name in entry.tokens.known_fields for name in MIX_FIELDS) for entry in entries)
    contributors = {}
    for entry in entries:
        contributors.setdefault((entry.model.provider, entry.model.model, entry.variant or '(Default)'), []).append(entry)
    groups = []
    for key, requests in sorted(contributors.items()):
        cost = comparison_cost(requests, reference.reference_valuation)
        groups.append((*key, len(requests), cost.known_ccost, cost.complete))
    status = ('running' if record.in_progress else 'failed' if record.watch_error else
              'aborted' if record.aborted else 'complete' if record.completed_successfully
              and record.execution_duration_ms is not None else 'unknown')
    duration = record.execution_duration_ms if status != 'running' else None
    selected = record.main_provider_id, record.main_model_id
    mixed = len(contributors) > 1 or any(key[:2] != selected for key in contributors)
    if record.main_variant and record.main_variant.lower() != 'default':
        mixed = mixed or any(key[2] != record.main_variant for key in contributors)
    return MatchedRun(identity, snapshot.root.session_id, record.prompt_time_ms,
        record.prompt_time_ms + duration if duration is not None else None, status,
        record.main_provider_id, record.main_model_id, row.watch_effort, mixed,
        valuation.known_ccost if entries and valuation.priced_requests else None, known and valuation.complete,
        row.main_ccost if entries and not row.main_estimated else None,
        row.subagent_ccost if entries and not row.subagent_estimated else None,
        row.incoming_context_ccost if row.incoming_context_ccost_known else None,
        row.extra_ccost if known else None,
        duration, row.next_context_tokens if status == 'complete' else None, row.token_mix_percent if known else None,
        (record.input_tokens, record.cache_read_tokens, record.cache_write_tokens, record.output_tokens),
        len(entries), row.linked_agent_count, sum(bool(entry.error_name) for entry in entries), tuple(groups))


def encode_run(run):
    if run is None:
        return None
    payload = {field.name: getattr(run, field.name) for field in fields(MatchedRun)
               if field.name not in ('title', 'activity_ms')}
    for name in DECIMALS:
        payload[name] = None if payload[name] is None else str(payload[name])
    payload['contributors'] = [(*group[:4], str(group[4]), group[5]) for group in run.contributors]
    return payload


def decode_run(payload):
    if payload is None:
        return None
    values = dict(payload)
    if set(values) != {field.name for field in fields(MatchedRun)} - {'title', 'activity_ms'}:
        raise ValueError('invalid_match_fields')
    if any(not isinstance(values[name], str) for name in ('session_id', 'provider', 'model', 'effort')):
        raise ValueError('invalid_match_labels')
    for name in DECIMALS:
        values[name] = None if values[name] is None else Decimal(values[name])
        if values[name] is not None and (not values[name].is_finite() or values[name] < 0):
            raise ValueError('invalid_match_cost')
    for name in ('started_at_ms', 'calls', 'linked_agents', 'errors'):
        if type(values[name]) is not int or values[name] < 0:
            raise ValueError('invalid_match_count')
    for name in ('completed_at_ms', 'duration_ms', 'next_context_tokens'):
        if values[name] is not None and (type(values[name]) is not int or values[name] < 0):
            raise ValueError('invalid_match_timing')
    if (not isinstance(values['fingerprint'], str) or not re.fullmatch('[0-9a-f]{64}', values['fingerprint'])
            or values['status'] not in ('complete', 'running', 'failed', 'aborted', 'unknown')
            or type(values['cost_complete']) is not bool or type(values['mixed']) is not bool):
        raise ValueError('invalid_match_identity')
    values['contributors'] = tuple((*group[:4], Decimal(group[4]), group[5]) for group in values['contributors'])
    if any(len(group) != 6 or type(group[3]) is not int or group[3] < 0 or type(group[5]) is not bool
           or not group[4].is_finite() or group[4] < 0 for group in values['contributors']):
        raise ValueError('invalid_match_contributors')
    for name in ('token_mix_percent', 'token_totals'):
        values[name] = None if values[name] is None else tuple(values[name])
        counts = values[name]
        if counts is not None and (len(counts) != 4 or any(type(value) is not int or value < 0 for value in counts)):
            raise ValueError('invalid_match_mix')
    return MatchedRun(**values)
