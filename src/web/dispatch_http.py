"""Validated demand/lookup routes, called only after cookie, Origin and CSRF checks."""
import re

from src.reports import ReportKind
from .dispatch import FINITE, SECTIONS
from .jobs import ReportWorkerStopError, parse_report

SECTION_KIND = {'models': ReportKind.NORMAL, 'token-mix': ReportKind.TOKEN_MIX,
                'ai-stats': ReportKind.AI_STATS, 'comparisons': ReportKind.COMPARISONS}


def handle(handler, value):
    if handler.path not in {'/api/interest', '/api/data'}:
        return False
    owner = handler.server.lifecycle
    dispatcher = getattr(owner, 'dispatcher', None)
    if dispatcher is None:
        handler.reply(503, {'error': 'dispatcher_unavailable'})
        return True
    try:
        if handler.path == '/api/interest':
            if (set(value) not in ({'tab', 'section', 'visible', 'request'}, {'tab', 'section', 'visible', 'request', 'history'})
                    or not isinstance(value['tab'], str) or not re.fullmatch(r'[a-f0-9-]{32,36}', value['tab'])
                    or value['section'] not in SECTIONS or type(value['visible']) is not bool):
                raise ValueError('invalid_interest')
            request = parse_report(value['request']) if value['request'] is not None else None
            if request is not None and SECTION_KIND.get(value['section']) is not request.kind:
                raise ValueError('invalid_interest')
            if 'history' in value and (type(value['history']) is not bool or value['section'] != 'watch' or request is not None):
                raise ValueError('invalid_interest')
            handler.reply(200, dispatcher.interest(value['tab'], value['section'], value['visible'], request,
                history=value.get('history', False)))
            housekeeping = getattr(owner, 'cache_housekeeping', None)
            if housekeeping and value['visible'] and handler.headers.get('X-CG-Viewed') == '1':
                if request:
                    with dispatcher.lock:
                        result = dispatcher.entries.get(request, {}).get('result')
                    housekeeping.delivered(owner, '/api/data', {'result': result})
                elif value['section'] == 'watch':
                    housekeeping.use_watch(owner, history=value.get('history', False))
        else:
            if set(value) != {'request', 'retry'} or type(value['retry']) is not bool:
                raise ValueError('invalid_request')
            request = parse_report(value['request'])
            if request.kind not in FINITE:
                raise ValueError('invalid_request')
            startup = getattr(owner, 'source_startup', None)
            if startup is not None:
                status = startup.report_status()
                if not status['ready']:
                    handler.reply(503, {'error': status['error'], 'retryable': status['retryable']})
                    return True
            if not dispatcher.identity:
                handler.reply(503, {'error': 'source_starting', 'retryable': True})
                return True
            result = dispatcher.lookup(request, retry=value['retry'])
            if not result['id'] and not result['terminal']:
                handler.reply(503, {'error': result['error'] or 'busy', 'retryable': True})
            else:
                handler.reply(200, result)
    except (ValueError, TypeError):
        handler.reply(400, {'error': 'invalid_request'})
    except ReportWorkerStopError:
        raise
    except RuntimeError:
        handler.reply(429, {'error': 'busy'})
    return True
