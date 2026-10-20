"""Small run-local time/work estimate, not a promise of remaining wall time.

Budgets reflect different acquisition scopes, not analysis-call counts. Known
work replaces the phase estimate with completed units and bounded interpolation
inside the next unit. Unknown phases have no numeric completion claim. Nothing
is persisted and no work is delayed to let the display catch up.
"""
from __future__ import annotations

from src.domain.progress import WorkProgress


class StartupEstimate:
    def __init__(self, mode: str, now: float) -> None:
        history = {"Report": 2.0, "All Models": 2.0, "Sessions": 4.0, "Session": 1.0,
                   "Date": 4.0, "Date Range": 6.0, "Token Mix": 8.0,
                   "Watch": 1.5, "Watch Session": 1.0}.get(mode, 2.0)
        self.budgets = dict(source=.3, cache=.05, pricing=.7, catalog=.2, history=history,
                            projection=.3, availability=.4, quotas=.8 if mode == "Report" else 0, finalizing=.15)
        self.phase = ""
        self.started = now
        self.unit_started = now
        self.completed = 0
        self.total: int | None = None
        self.unit_seconds: float | None = None
        self.high_water = 0.0
        self.known = False

    def update(self, observation: str, now: float) -> None:
        if not isinstance(observation, WorkProgress):
            self.known = False
            return
        phase = observation.phase
        if phase not in self.budgets:
            self.known = False
            return
        phases = tuple(self.budgets)
        if self.phase and phases.index(phase) < phases.index(self.phase):
            return  # a lazy dependency/overlapped worker is not a new phase
        self.known = True
        if phase != self.phase:
            self.phase, self.started, self.unit_started = phase, now, now
            self.completed, self.total, self.unit_seconds = 0, None, None
        if observation.total != self.total:
            self.unit_started, self.unit_seconds = now, None
        if observation.completed > self.completed:
            seconds = (now - self.unit_started) / (observation.completed - self.completed)
            self.unit_seconds = max(.001, seconds)
            self.unit_started = now
        self.completed, self.total = observation.completed, observation.total

    def percent(self, now: float) -> int:
        if not self.phase:
            return int(self.high_water)
        budget = self.budgets[self.phase]
        before = sum(value for phase, value in self.budgets.items()
                     if tuple(self.budgets).index(phase) < tuple(self.budgets).index(self.phase))
        elapsed = max(0.0, now - self.started)
        fraction = elapsed / (elapsed + max(.001, budget))
        if self.total:
            unit = self.unit_seconds or budget / self.total
            since_unit = max(0.0, now - self.unit_started)
            interpolation = .9 * since_unit / (since_unit + unit)
            fraction = min(1.0, (self.completed + interpolation) / self.total)
        self.high_water = max(self.high_water, min(99.0, 100 * (before + budget * fraction) / sum(self.budgets.values())))
        return int(self.high_water)
