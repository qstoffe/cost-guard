"""Long synthetic layout fixtures; duplicated rows are not valuation assertions."""
from copy import deepcopy
from threading import Event

from development.tests.fixtures.remaining_views import remaining_reports, result, detail_page, NOW, ZONE
from development.tests.fixtures.warning_projections import warning_prompt, warning_watch_projection
from src.analysis.context import PriceWarningSeverity
from src.application.live_projection import project_live


def repeat(rows, count=125):
    return [deepcopy(rows[index % len(rows)]) for index in range(count)]


class ScrollData:
    def __init__(self, test):
        self.reports = {key: result(value) for key, value in remaining_reports(test).items()}
        for key in ('normal', 'all-models'):
            self.reports[key]['view']['model_comparison'] = repeat(self.reports[key]['view']['model_comparison'])
        accounts = self.reports['normal']['view']['accounts_quotas']
        accounts['accounts'] = repeat(accounts['accounts'])
        self.reports['sessions']['view']['session_usage'] = repeat(self.reports['sessions']['view']['session_usage'])
        for key in ('model_token_mix', 'publisher_token_mix'):
            self.reports['token-mix']['view'][key] = repeat(self.reports['token-mix']['view'][key])
        view = project_live(warning_watch_projection(warning_prompt(PriceWarningSeverity.EXCEEDED)), ZONE).to_json()
        view['rows'] = repeat(view['rows'])
        for index, row in enumerate(view['rows']):
            row['prompt']['event_id'] = f'scroll-{index}'
        self.live = dict(state='running', view=view, source_observed_at_ms=NOW)


class ScrollJobs:
    """Finite synthetic results behind the production HTTP boundary, no workers."""
    def __init__(self, data):
        self.data, self.jobs, self.requests = data, {}, []

    def submit(self, request):
        self.requests.append(request.kind.value)
        key = f'{len(self.jobs) + 1:032x}'
        self.jobs[key] = dict(status='complete', result=self.data.reports[request.kind.value])
        return key

    def snapshot(self, key):
        return self.jobs.get(key)

    def readiness(self):
        return dict(http='ready', analysis='ready', source='synthetic', accounts='synthetic')

    def tick(self):
        pass

    def close(self):
        pass


class ScrollDetails:
    def __init__(self, data):
        self.full = data.reports['session']
        self.revision = 1
        self.leases = {}
        self.pending, self.release = Event(), Event()
        self.release.set()

    def open(self, session_id, mode):
        token = str(len(self.leases) + 1)
        self.leases[token] = None if mode == 'live' else (deepcopy(self.full), self.revision)
        return token

    def page(self, token, offset, revision=None, anchor=None):
        self.pending.set()
        if not self.release.wait(4):
            raise RuntimeError('fixture_response_timeout')
        frozen = self.leases[token]
        full, version = frozen if frozen else (self.full, self.revision)
        page = detail_page(full, offset)
        page['revision'] = str(version)
        return page

    def freeze(self, token):
        self.leases[token] = deepcopy(self.full), self.revision

    def close(self, token):
        self.leases.pop(token, None)
