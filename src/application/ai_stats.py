"""Prepared AI Stats values and stable original trait copy; no acquisition or math."""
from decimal import Decimal, InvalidOperation

from src.display import duration_text
from src.numbers import ccost_amount, ccost_unit, exact_number

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


def rate_tokens(raw):
    rates = dict(raw.fields) if hasattr(raw, 'fields') else raw
    def amount(key):
        return ccost_amount(number(rates[key])) + ('' if ccost_unit() == 'usd' else ' CCost')
    calendar = amount('calendar_rate') + '/h'
    workday = amount('workday_rate') + '/h' if rates['workdays'] else 'No workdays'
    robot = amount('robot_day') + '/8h day'
    hours = exact_number(number(rates['active_hours']))
    workday_help = (f"Workday: the same total ÷ {rates['workday_hours']} scheduled hours = {workday}."
                   if rates['workdays'] else 'Workday: No workdays, so no scheduled hours to spread the tab over.')
    help_text = ('24h lets the robots burn credits around the clock. Workday squeezes the same tab into '
        'eight scheduled hours per workday. Robot day imagines eight full hours at their active-hour burn rate: '
        'a hypothetical shift, not a historical invoice.\n'
        f"24h: {amount('total')} ÷ {rates['calendar_hours']} nominal calendar hours = {calendar}. "
        'Rolling 7/30-day views use local date slots ending today; cost keeps its trailing-hour window.\n'
        f'{workday_help}\n')
    help_text += (f"Robot: {amount('total')} ÷ {hours} active hours = {amount('active_rate')}/h; "
        f"× 8 = {robot}. {rates['workdays']} such shifts = {amount('robot_period')}."
        if rates['active_hours'] else 'Robot clock is taking a nap. No active-hour basis for a shift yet.')
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
    return {'value': text, 'trait': line, **(rate_tokens(values['rates'])
        if metric == 'hourly-rate' and values.get('rates') else {})}
