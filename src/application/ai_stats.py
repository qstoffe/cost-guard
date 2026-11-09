"""Prepared AI Stats values and stable original trait copy; no acquisition or math."""
from decimal import Decimal, InvalidOperation

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
    robot = amount('robot_day') + '/8h day'
    workday_help = ('Workday: The same tab squeezed into eight-hour days, skipping weekends and configured holidays; HR calls that mercy.'
        if rates['workdays'] else 'Workday: No scheduled workdays to carry the tab; even imaginary payroll gets weekends and holidays off.')
    shift = number(rates['robot_day'])
    robot_help = 'Robot 8h shift: Imagine eight hours of nonstop silicon; the robot wants a charging dock and a promotion.'
    if not number(rates['active_hours']) or not number(rates['total']) or not shift:
        robot_help = "Robot 8h shift: The imaginary shift hasn't started; HR is still writing the robot's job description."
    # Fictional copy tiers in raw reference Credits, not wages or rounded currency.
    elif not reasons:
        if shift < 80:
            robot_help = 'Robot 8h shift: At this imaginary eight-hour bargain, your replacement has already requested your parking spot.'
        elif shift >= 800:
            robot_help = "Robot 8h shift: Imagine eight nonstop hours at this price. Relax, HR just shredded the robot's job application."
    help_text = '\n\n'.join((
        '24h: The same robot tab, spread around the clock; even your beauty sleep gets a budget line.',
        workday_help, robot_help))
    return {'calendar_rate': calendar, 'workday_rate': workday, 'robot_day': robot, 'rate_help': help_text}


def stat_tokens(values):
    if 'metric' not in values:
        return {}
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
