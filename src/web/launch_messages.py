"""Fixed, shared console/dialog text; never interpolate subprocess exceptions."""
import json
from pathlib import Path
from .process_identity import InstanceConflict

_MESSAGES = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))


def messages(platform):
    return {code: value[platform] if isinstance(value, dict) else value
            for code, value in _MESSAGES.items()}


def failure_text(code, platform):
    reason = messages(platform)[code]
    title = 'COST GUARD COULD NOT START'
    action = 'Preserve Web state; run Diagnostics, then retry. Legacy CLI remains available.'
    if code == 'configuration_unavailable':
        action = 'Check config/user-config.jsonc, then retry.'
    elif code == 'browser_open_failed':
        title = 'COST GUARD WEB IS RUNNING'
        menu = 'tray' if platform == 'windows' else 'menu-bar'
        action = f'Use {menu} Open Cost Guard to retry the browser.'
    diagnostics = f'development/user-tools/diagnostics/{platform}/Cost-Guard-Diagnostics.'
    diagnostics += 'cmd' if platform == 'windows' else 'command'
    return f'{title}\n\nReason: {reason}\n\nNext step: {action}\n\nDiagnostics: {diagnostics}'


def record_failure(store, code):
    try:
        store.log(code)
        return True
    except (OSError, InstanceConflict):
        return False


def print_failure(code, platform, store=None):
    recorded = record_failure(store, code) if store else True
    if platform == 'windows':
        # The PowerShell wrapper accepts a known code only, not arbitrary child text.
        print('Cost Guard failure: ' + code, flush=True)
    print(failure_text(code, platform), flush=True)
    if not recorded:
        print('\nPrivate startup diagnostic could not be recorded.', flush=True)
