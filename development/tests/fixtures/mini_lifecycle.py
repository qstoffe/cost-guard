"""Synthetic canonical membership/outcomes for Mini foreground browser acceptance."""
from dataclasses import replace
from src.domain.models import OngoingStatus

from src.watch.running import running_prompts


def lifecycle_frame(frame, phase):
    base = frame.active_cards[0]
    history = []
    for index in range(5):
        session = f'mini-lifecycle-{index}'
        prompt = replace(base.rows[0].prompt, event_id=f'old-{index}',
            at_ms=frame.now_ms - 200000 + index, completed_at_ms=frame.now_ms - 100000 + index,
            in_progress=False, execution_unverified=False, completed_successfully=True,
            aborted=False, watch_error=False, abort_reason='')
        history.append(replace(base, session_id=session, title=f'Lifecycle session {index}', focal_id='', ongoing=None,
            rows=(replace(base.rows[0], session_id=session, prompt=prompt),)))
    active = ()
    if phase not in {'cold', 'pending', 'retry', 'invalidated'}:
        historical = phase.startswith('history-')
        outcome = phase.removeprefix('history-')
        assert outcome in {'running', 'background', 'waiting', 'success', 'aborted', 'error', 'unverified'}
        last = history[-1]
        prompt = replace(last.rows[0].prompt, event_id='next', prompt_number=24,
            at_ms=frame.now_ms - 1000, completed_at_ms=None if outcome in {'running', 'unverified'} else frame.now_ms,
            in_progress=outcome == 'running', execution_unverified=outcome == 'unverified',
            completed_successfully=outcome == 'success', aborted=outcome == 'aborted',
            watch_error=outcome == 'error', abort_reason='user' if outcome == 'aborted' else '')
        ongoing = {"running": OngoingStatus("running"), "background": OngoingStatus("background", awaits="A descendant shell"),
                   "waiting": OngoingStatus("waiting", wake_at_ms=1796123700000)}.get(outcome)
        terminal = {"success": "completed", "aborted": "aborted"}.get(outcome)
        last = replace(last, focal_id='' if historical else 'next', rows=(replace(last.rows[0], prompt=prompt),),
                       ongoing=None if historical else ongoing, terminal_status=None if historical else terminal,
                       terminal_until_ms=frame.now_ms+30_000 if terminal and not historical else None)
        history[-1] = last
        if not historical:
            active = (last,)
            history.pop()
    return replace(frame, active_cards=active, history_cards=() if phase == 'invalidated' else tuple(history),
        cards_state='unavailable' if phase == 'retry' else 'observed',
        history_state='loading' if phase in {'pending', 'invalidated'} else 'refreshing' if phase == 'retry' else 'observed',
        history_epoch=0 if phase in {'pending', 'invalidated'} else 1,
        history_scope='invalidated-source' if phase == 'invalidated' else 'mini-lifecycle',
        running=running_prompts(active, 'observed'))
