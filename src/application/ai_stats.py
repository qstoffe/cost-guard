"""Prepared AI Stats values and stable original trait copy; no acquisition or math."""
from decimal import Decimal, InvalidOperation

from src.display import duration_text
from src.numbers import ccost_amount, ccost_unit
from .model_help import request_model_help

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


def number(value):
    try:
        result = Decimal(value) if value is not None else Decimal(0)
        return min(Decimal('1e12'), max(Decimal(0), result)) if result.is_finite() else Decimal(0)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


def rate_tokens(raw, reasons=()):
    rates = dict(raw.fields) if hasattr(raw, 'fields') else raw
    def amount(key):
        return ccost_amount(number(rates[key])) + ('' if ccost_unit() == 'usd' else ' CCost')
    calendar = amount('calendar_rate') + '/h'
    workday = amount('workday_rate') + '/h' if rates['workdays'] else 'No workdays'
    active = amount('active_rate') + '/h'
    workday_help = ('The same robot bill, squeezed into ordinary office hours.'
        if rates['workdays'] else "The robot's office calendar is taking a nap.")
    rate = number(rates['active_rate'])
    active_help = "The silicon's hourly appetite when it's actually working."
    if not number(rates['active_hours']) or not number(rates['total']) or not rate:
        active_help = "The silicon's hourly snack break hasn't started."
    # Playful intensity tiers use raw reference Credits, not wages or rounded currency.
    elif not reasons:
        if rate < 10:
            active_help = 'The silicon nibbles through its hourly snack budget.'
        elif rate >= 100:
            active_help = 'The silicon orders the deluxe hourly buffet.'
    help_text = '\n\n'.join((
        'Calendar average: The robot keeps a budget even while you sleep. (Total CCost ÷ (calendar days × 24))',
        f'Workday average: {workday_help} (Total CCost ÷ (workdays × 8))',
        f'Active AI average: {active_help} (Total CCost ÷ active AI hours)'))
    return {'calendar_rate': calendar, 'workday_rate': workday, 'active_rate': active, 'rate_help': help_text}


def compact_volume(value):
    """Round only display, without the fun-cost cap or a binary float conversion."""
    amount = Decimal(value)
    for scale, suffix in ((10**12, 'T'), (10**9, 'B'), (10**6, 'M'), (1000, 'K')):
        if amount >= scale:
            return f'{amount / scale:.1f}'.removesuffix('.0') + suffix
    return f'{amount:.1f}'.removesuffix('.0')


def traffic_tokens(values):
    reasons = values.get('reasons', ())
    if values['metric'] == 'total-tokens':
        total = int(values['value'])
        return {'value': compact_volume(total),
            'trait': 'The robots have been snacking on context again.',
            'token_help': f'{total} observed tokens: Input + Cached input + Cache write + Output '
                '(including reasoning once). Repeated context reads count again. Token traffic, not context size, '
                'billing or quota.' + (' Missing usage, pending requests or source gaps prevent a complete total.' if reasons else '')}
    return {'value': '' if values.get('podium') else
                'The stopwatch is waiting for a timed response.' if values.get('detail') else
                'No races yet. The podium is polished.',
        'trait': 'The silicon sprint podium.',
        'response_help': 'Approximate output tokens per second across sampled model responses. '
            'Output (including reasoning once) ÷ summed response seconds; up to 32 sampled calls per model and effort. '
            'Client-observed response round trip includes network, queueing and time to first token, not just decoding. '
            'Local tool execution is excluded. Newest eight plus identity-spread historical samples; '
            'small samples and historical-window selection are best effort.'}


def response_tokens(row):
    return dict(label=f'{row.provider}/{row.model}' + (f' · {row.variant}' if row.variant else ''),
                model_help=request_model_help(row.provider, row.recorded_models,
                    catalog_model=row.model if row.catalog_estimate else None),
                speed=('<0.1' if row.tokens_per_second < Decimal('.1') else compact_volume(row.tokens_per_second)) + ' tok/s',
                sample=f'{row.sampled_calls} sampled call' + ('s' if row.sampled_calls != 1 else ''))


def stat_tokens(values):
    if 'metric' not in values:
        return {}
    if values['metric'] in ('total-tokens', 'token-rate'):
        return traffic_tokens(values)
    metric, value = values['metric'], number(values['value'])
    if metric in ('original-thinker', 'match-speed-gap'):
        return {'value': 'Original Thinker' if metric == 'original-thinker' else f'{Decimal(value):.1f}×',
                'trait': 'One of a kind. In this period, at least.' if metric == 'original-thinker' else
                    'Same opening move. Very different lap times.'}
    if metric == 'night-owl':
        value = min(100, value)
        line = ('Day-shift citizen. Suspiciously responsible.' if value < 1 else
                'Occasional moonlighting detected.' if value < 35 else
                'Half silicon, half moonlight.' if value < 65 else 'Certified nocturnal operator.')
    else:
        low, high = THRESHOLDS[metric]
        line = COPY[metric][0 if value < low else 2 if value >= high else 1]
        if metric == 'parallel' and not value:
            line = 'The parallel universe is on vacation.'
    if metric in {'hourly-rate', 'total-cost', 'average-cost', 'expensive-session'}:
        text = ccost_amount(value) + ('' if ccost_unit() == 'usd' else ' CCost')
        if metric == 'hourly-rate':
            text += '/h'
    elif metric in {'working-time', 'longest-session', 'busiest-day'}:
        text = duration_text(value)
    elif metric == 'night-owl':
        text = f'{Decimal(value):.0f}%'
    else:
        text = str(int(value)) + (' days' if metric == 'streak' else '')
    return {'value': text, 'trait': line, **(rate_tokens(values['rates'], values.get('reasons', ()))
        if metric == 'hourly-rate' and values.get('rates') else {})}
