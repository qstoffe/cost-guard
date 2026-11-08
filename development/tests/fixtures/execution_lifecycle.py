"""Sanitized persisted timeline with two successes and a pending checkpoint."""
import copy


def checkpoint_timeline(native, *, assistant=False, usage=False):
    original = copy.deepcopy(native.messages['ses_current'][1])
    original.update(content=[], tokens={'input': 100, 'output': 10}, cost=1)
    messages = []
    for index, start in enumerate((3000, 6000)):
        answer = copy.deepcopy(original)
        answer.update(id=f'answer_{index}', time={'created': start + 100, 'completed': start + 500})
        messages.extend([
            {'id': f'user_{index}', 'type': 'user', 'text': 'synthetic completed prompt',
             'time': {'created': start}}, answer,
            {'id': f'idle_{index}', 'type': 'idle', 'outcome': 'succeeded',
             'time': {'created': start + 502}}])
    messages.append({'id': 'checkpoint', 'type': 'user', 'text': 'save context then pause',
                     'time': {'created': 6600}})
    if assistant:
        pending = {'id': 'pending', 'type': 'assistant', 'content': [],
                   'model': original['model'], 'time': {'created': 6800}}
        if usage:
            pending.update(tokens={'input': 50, 'output': 2}, cost=0.5)
        messages.append(pending)
    native.sessions = native.sessions[:1]
    native.sessions[0]['time'].update(updated=6900, idle=6502, busy=6596)
    native.sessions[0]['outcome'] = 'succeeded'  # belongs to the preceding run
    native.messages['ses_current'] = messages
