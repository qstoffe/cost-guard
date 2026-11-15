"""Prepared AI Stats values and stable original trait copy; no acquisition or math."""
from decimal import Decimal, InvalidOperation

from src.display import duration_text
from src.numbers import ccost_amount, ccost_unit

COPY = {
    'hourly-rate': ('Budget build. Dangerous potential.', 'Standard-issue silicon. Surprisingly functional.', 'Premium silicon has expensive tastes.'),
    'total-cost': ('The token furnace is on vacation.', 'The ledger has a side quest.', 'The token furnace demands tribute.'),
    'subagent-cost': ('The helpers are on a snack break.', 'The boss delegated. The bots sent the bill.', 'The silicon helpers have expensive taste.'),
    'working-time': ('The silicon crew took a nap.', 'A short shift for the silicon crew.', 'Silicon overtime. No coffee required.'),
    'average-cost': ('Tiny adventures. Tiny tab.', 'A modest toll at the gate.', 'Every conversation has a cover charge.'),
    'expensive-session': ('A boss fight on a budget.', 'One quest kept the receipt.', 'That boss fight came with a receipt.'),
    'longest-session': ('A quick quest. Refreshing.', 'A respectable silicon expedition.', 'That escalated into a full campaign.'),
    'busiest-day': ('A perfectly peaceful calendar.', 'The calendar has a favorite.', 'The bots earned imaginary overtime.'),
    'streak': ('The calendar awaits its first quest.', 'The calendar learned a new habit.', 'The calendar fears you.'),
    'parallel': ('One lane. Very civilized.', 'A small party of silicon.', 'A miniature parallel universe.'),
}
THRESHOLDS = {'hourly-rate': (Decimal('.3'), 3), 'total-cost': (Decimal('.1'), 20),
    'subagent-cost': (Decimal('.001'), 20),
    'average-cost': (Decimal('.1'), 2), 'expensive-session': (Decimal('.1'), 10),
    'working-time': (1, 8 * 3_600_000), 'longest-session': (600_000, 3_600_000),
    'busiest-day': (600_000, 8 * 3_600_000), 'streak': (1, 7), 'parallel': (2, 3)}


def number(value, *, cap=Decimal('1e12')):
    try:
        result = Decimal(value) if value is not None else Decimal(0)
        if not result.is_finite():
            return Decimal(0)
        result = max(Decimal(0), result)
        return min(cap, result) if cap is not None else result
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(0)


def rate_tokens(raw, reasons=()):
    return {'rate_help': 'Average cost across all AI work: total CCost for every model ÷ total active AI hours. '
            'Overlapping work counts once. Individual models can have higher or lower hourly rates.'}


def compact_volume(value):
    """Round only display, without the fun-cost cap or a binary float conversion."""
    amount = Decimal(value)
    for scale, suffix in ((10**12, 'T'), (10**9, 'B'), (10**6, 'M'), (1000, 'K')):
        if amount >= scale:
            return f'{amount / scale:.1f}'.removesuffix('.0') + suffix
    return f'{amount:.1f}'.removesuffix('.0')


def traffic_tokens(values):
    if values['metric'] == 'total-tokens':
        total = int(values['value'])
        return {'value': compact_volume(total),
            'trait': 'The robots have been snacking on context again.',
            'token_help': 'The robots have eaten the entire context buffet.'}
    return {'value': speed_text(values['value']) if values.get('podium') else
                'The stopwatch is waiting for a timed response.' if values.get('detail') else
                'No races yet. The podium is polished.',
        'trait': 'The silicon sprint podium.',
        'response_help': 'The silicon sprinters are racing for snacks.\n\n'
            'Approximate output tokens divided by sampled response time. Includes waiting and network time.'}


def speed_text(value):
    value = Decimal(value)
    return ('<0.1' if value < Decimal('.1') else compact_volume(value)) + ' tok/s'


def effort_amount(value, metric):
    if metric == 'token-rate':
        return speed_text(value)
    if metric == 'total-tokens':
        return compact_volume(value) + ' tokens'
    if metric == 'working-time':
        return duration_text(value)
    amount = ccost_amount(number(value, cap=None) if metric == 'hourly-rate' else number(value))
    return amount + ('' if ccost_unit() == 'usd' else ' CCost') + ('/h' if metric == 'hourly-rate' else '')


def model_tooltip(provider, model, efforts, metric):
    return f'{provider}/{model}\n\nBy Effort:' + ''.join(
        f'\n• {effort} — {effort_amount(value, metric)}' for effort, value in efforts)


def response_tokens(row):
    return dict(label=short_model(row),
                model_help=model_tooltip(row.provider, short_model(row), row.by_effort, 'token-rate'),
                speed=speed_text(row.tokens_per_second),
                sample=f'{row.sampled_calls} sampled call' + ('s' if row.sampled_calls != 1 else ''))


def short_model(row):
    return (row.display_name or row.model).removeprefix(row.provider + '/').split('/')[-1]


def standing_tokens(row, metric):
    return dict(label=short_model(row),
                model_help=model_tooltip(row.provider, short_model(row), row.by_effort, metric))


def stat_tokens(values):
    if 'podium_metric' in values:
        metric, value = values['podium_metric'], values['podium_value']
        amount = (effort_amount(value, metric) if metric == 'hourly-rate' else
                  compact_volume(value) if metric == 'total-tokens' else duration_text(value)
                  if metric == 'working-time' else ccost_amount(number(value)) +
                  ('' if ccost_unit() == 'usd' else ' CCost'))
        efforts = [dict(item.fields) for item in values.get('by_effort', ())]
        return {'amount': amount, 'model_help': model_tooltip(values['provider'], values['label'],
                ((item['effort'], item['value']) for item in efforts), metric)}
    if 'metric' not in values:
        return {}
    if values['metric'] in ('total-tokens', 'token-rate'):
        return traffic_tokens(values)
    metric = values['metric']
    value = number(values['value'], cap=None) if metric == 'hourly-rate' else number(values['value'])
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
    if metric in {'hourly-rate', 'total-cost', 'subagent-cost', 'average-cost', 'expensive-session'}:
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
