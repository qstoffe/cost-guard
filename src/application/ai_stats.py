"""Prepared AI Stats values and stable original trait copy; no acquisition or math."""
from decimal import Decimal

from src.display import duration_text
from src.numbers import ccost_amount, ccost_unit

COPY = {
    'hourly-rate': ('Budget build. Dangerous potential.', 'Standard-issue silicon. Surprisingly functional.', 'Premium silicon has expensive tastes.'),
    'total-cost': ('The token furnace is on vacation.', 'The ledger has a side quest.', 'The token furnace demands tribute.'),
    'working-time': ('The silicon crew took a nap.', 'A short shift for the silicon crew.', 'Silicon overtime. No coffee required.'),
    'average-cost': ('Tiny adventures. Tiny tab.', 'A modest toll at the gate.', 'Every conversation has a cover charge.'),
    'expensive-session': ('A boss fight on a budget.', 'One quest kept the receipt.', 'That boss fight came with a receipt.'),
    'longest-session': ('A quick quest. Refreshing.', 'A respectable silicon expedition.', 'That escalated into a full campaign.'),
    'busiest-day': ('A perfectly peaceful calendar.', 'The calendar has a favorite.', 'The bots earned imaginary overtime.'),
    'streak': ('The calendar awaits its first quest.', 'The calendar learned a new habit.', 'The calendar fears you.'),
    'parallel': ('One lane. Very civilized.', 'A small party of silicon.', 'A miniature parallel universe.'),
}
THRESHOLDS = {'hourly-rate': (Decimal('.3'), 3), 'total-cost': (Decimal('.1'), 20),
    'average-cost': (Decimal('.1'), 2), 'expensive-session': (Decimal('.1'), 10),
    'working-time': (1, 8 * 3_600_000), 'longest-session': (600_000, 3_600_000),
    'busiest-day': (600_000, 8 * 3_600_000), 'streak': (1, 7), 'parallel': (2, 3)}
REASONS = {
    'source-incomplete': 'Historical source coverage is incomplete.',
    'unknown-duration': 'Some executions have unknown start or end times; full execution time cannot be verified.',
    'unpriced-requests': 'Reference-price evidence is missing for some requests.',
    'missing-token-usage': 'Some requests have incomplete token-category telemetry.',
    'pending-usage': 'Some in-progress executions have not yet reported usage.',
    'running-executions': 'Some executions are still in progress; timing observations are provisional.',
    'no-requests': 'No recorded requests in this completely observed period.',
    'no-execution-time': 'No positive execution time in this completely observed period.',
}


def explanation(values):
    status = values['status']
    reason = ' '.join(REASONS[code] for code in dict.fromkeys(values.get('reasons', ())) if code in REASONS)
    if status == 'partial':
        return 'Observed subtotal only. ' + (reason or 'The reason for incomplete evidence is unknown.')
    if reason:
        return reason
    return '' if status == 'complete' and values['value'] is not None else 'The reason for missing evidence is unknown.'


def stat_tokens(values):
    if 'metric' not in values:
        return {}
    metric, value = values['metric'], values['value']
    if metric in ('original-thinker', 'match-speed-gap'):
        return {'value': 'Original Thinker' if metric == 'original-thinker' else f'{Decimal(value):.1f}×',
                'trait': 'One of a kind. In this period, at least.' if metric == 'original-thinker' else
                    'Same opening move. Very different lap times.'}
    known = value is not None and values['status'] == 'complete'
    line = explanation(values)
    if known:
        number = Decimal(value)
        if metric == 'night-owl':
            line = ('Day-shift citizen. Suspiciously responsible.' if number < 1 else
                    'Occasional moonlighting detected.' if number < 35 else
                    'Half silicon, half moonlight.' if number < 65 else 'Certified nocturnal operator.')
        else:
            low, high = THRESHOLDS[metric]
            line = COPY[metric][0 if number < low else 2 if number >= high else 1]
            if metric == 'parallel' and not number:
                line = 'The parallel universe is on vacation.'
    if value is None:
        text = 'No data' if values['status'] == 'no-data' else 'Unavailable'
    elif metric in {'hourly-rate', 'total-cost', 'average-cost', 'expensive-session'}:
        text = ccost_amount(Decimal(value)) + ('' if ccost_unit() == 'usd' else ' CCost')
        if metric == 'hourly-rate':
            text += '/h'
    elif metric in {'working-time', 'longest-session', 'busiest-day'}:
        text = duration_text(value)
    elif metric == 'night-owl':
        text = f'{Decimal(value):.0f}%'
    else:
        text = str(value) + (' days' if metric == 'streak' else '')
    return {'value': text, 'trait': line, 'explanation': explanation(values),
            'state': {'partial': 'Partial', 'provisional': 'Provisional', 'no-data': 'No data',
                      'unavailable': 'Unavailable'}.get(values['status'], '')}
