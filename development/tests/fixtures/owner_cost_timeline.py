"""Opt-in bounded stage aggregates and a short owner-thread function profile.

No arguments, return values, exceptions, frames or source identities are evidence.
Exclusive CPU is additive only within the observed thread/stage coverage, not a
whole-process estimate. Wall spans on different threads may overlap.
"""
from functools import wraps
from pathlib import Path
from profile import Profile
from threading import Lock, current_thread, local
from types import SimpleNamespace
import time


def thread_role():
    name = current_thread().name
    for prefix, role in (
            ('cost-guard-live', 'owner'), ('cost-guard-cards', 'card'),
            ('cost-guard-v2-history', 'inner_hydration'),
            ('cost-guard-account-history', 'account_history'),
            ('cost-guard-detail', 'detail'), ('cost-guard-session-index', 'session_index'),
            ('cost-guard-session-cost', 'session_cost')):
        if name.startswith(prefix):
            return role
    return 'other_host'


class OwnerCostTimeline:
    def __init__(self, root, *, clock=time.monotonic, cpu=time.thread_time, functions=True):
        self.root = Path(root).resolve()
        self.clock, self.cpu = clock, cpu
        self.started = clock()
        self.current = local()
        self.lock = Lock()
        self.stages = {}
        self.originals = []
        self.functions = {}
        self.function_profile_enabled = functions
        self.profile_calls = 0
        self.profile_wall = self.profile_cpu = 0.0

    def wrap(self, owner, name, stage, *, profile=False, outer_only=False):
        original = getattr(owner, name)
        had_attribute = name in vars(owner)

        @wraps(original)
        def measured(*args, **kwargs):
            if outer_only and getattr(self.current, 'converting_dto', False):
                return original(*args, **kwargs)
            if outer_only:
                self.current.converting_dto = True
            stack = getattr(self.current, 'stack', None)
            if stack is None:
                stack = self.current.stack = []
            frame = [self.clock(), self.cpu(), 0.0, 0.0]
            stack.append(frame)
            role = thread_role()
            sample = (self.function_profile_enabled and profile and role == 'owner' and
                5 <= frame[0] - self.started < 8 and not getattr(self.current, 'profiling', False))
            if sample:
                self.current.profiling = True
                # Python3.14 cProfile observes concurrent threads, which makes
                # a thread-local CPU timer invalid (even negative durations).
                # The standard Python profiler uses this thread's setprofile.
                # Construct/finalize in this same thread, not the main thread.
                profiler = Profile(timer=time.thread_time, bias=0)
            try:
                if sample:
                    return profiler.runcall(original, *args, **kwargs)
                return original(*args, **kwargs)
            finally:
                if sample:
                    profiler.create_stats()
                    for key, (_, calls, own, inclusive, _) in profiler.stats.items():
                        filename, line, function = key
                        if line <= 0:
                            continue  # Builtins and profiler's repr(function) pseudo frames.
                        row = self.functions.setdefault(key, [0, 0.0, 0.0])
                        row[0] += calls
                        row[1] += own
                        row[2] += inclusive
                    self.current.profiling = False
                wall, cpu = self.clock() - frame[0], self.cpu() - frame[1]
                stack.pop()
                if outer_only:
                    self.current.converting_dto = False
                if stack:
                    stack[-1][2] += wall
                    stack[-1][3] += cpu
                with self.lock:
                    row = self.stages.setdefault((stage, role), dict(stage=stage, thread_role=role,
                        calls=0, wall_seconds=0.0, thread_cpu_seconds=0.0,
                        exclusive_wall_seconds=0.0, exclusive_thread_cpu_seconds=0.0,
                        max_wall_seconds=0.0))
                    row['calls'] += 1
                    row['wall_seconds'] += wall
                    row['thread_cpu_seconds'] += cpu
                    row['exclusive_wall_seconds'] += max(0, wall - frame[2])
                    row['exclusive_thread_cpu_seconds'] += max(0, cpu - frame[3])
                    row['max_wall_seconds'] = max(row['max_wall_seconds'], wall)
                    if sample:
                        self.profile_calls += 1
                        self.profile_wall += wall
                        self.profile_cpu += cpu

        setattr(owner, name, measured)
        self.originals.append((owner, name, original, had_attribute))

    def attach(self, runtime, driver):
        from src.pricing.github_copilot import GitHubCopilotPricingProvider
        from src.application import live, live_projection
        from src.application.contracts import ObjectValue
        from src.reports.service import ReportService
        from src.sources import opencode_v2_snapshot
        from src.web import events

        owner = driver.coordinator
        cards = owner.cards
        for name in ('catalog', 'accept', '_tick_costs', '_ranked_ids', 'project'):
            self.wrap(cards, name, 'cards' + name if name.startswith('_') else 'cards_' + name)
        self.wrap(cards, 'tick', 'cards_tick')
        self.wrap(cards.workers, 'drain', 'card_drain_with_observer')
        if cards.guidance is not None:
            for name in ('tick', '_refresh', '_produce'):
                self.wrap(cards.guidance, name, 'guidance_' + name.lstrip('_'))
        for name in ('_build_projection', '_refresh_quota', 'tick_catalog', 'tick_details',
                'service_completed', '_account_history', '_catalog_capture', '_detail_capture'):
            self.wrap(owner, name, 'coordinator_' + name.lstrip('_'), profile=True)
        self.wrap(driver, 'tick', 'driver_tick', profile=True)
        self.wrap(runtime, '_publish_frame', 'export_and_publication', profile=True)
        self.wrap(owner.source, '_list_native_sessions', 'owner_source_catalog')
        self.wrap(opencode_v2_snapshot, '_read_tree', 'tree_hydration')
        for name in ('_analyze_snapshot', '_load_catalog', '_load_comparison_catalog', 'project_watch_accounts'):
            self.wrap(ReportService, name, 'report_' + name.lstrip('_'))
        self.wrap(GitHubCopilotPricingProvider, 'cached_catalog', 'cached_pricing_catalog')
        self.wrap(live, 'project_live', 'project_live')
        self.wrap(live_projection, 'with_display', 'top_display')
        # Only one clock/CPU observation for each outer DTO conversion. Recursive
        # records bypass measurement (a thread-local guard check only).
        self.wrap(ObjectValue, 'to_json', 'dto_conversion', outer_only=True)
        self.wrap(events.EventHub, '_encode', 'event_encode')
        self.wrap(events.EventHub, 'snapshot', 'event_snapshot')
        original_json = events.json
        events.json = SimpleNamespace(dumps=original_json.dumps, loads=original_json.loads)
        self.originals.append((events, 'json', original_json, True))
        self.wrap(events.json, 'dumps', 'event_json_dumps')
        self.wrap(events.json, 'loads', 'event_json_loads')

    def summary(self):
        # Called only after owned threads have joined. Never export .prof files:
        # those include physical paths. Retain bounded sanitized function rows.
        functions = []
        for (filename, line, function), (calls, own, inclusive) in self.functions.items():
            path = Path(filename)
            try:
                module = path.resolve().relative_to(self.root).as_posix() if path.is_absolute() else '<runtime>'
            except ValueError:
                module = '<runtime>'
            functions.append(dict(module=module, function=function,
                line=line if module != '<runtime>' else 0,
                calls=calls, own_thread_cpu_seconds=own,
                inclusive_thread_cpu_seconds=inclusive))
        functions.sort(key=lambda row: row['own_thread_cpu_seconds'], reverse=True)
        with self.lock:
            return dict(stages=[dict(row) for row in self.stages.values()],
                function_profile=dict(enabled=self.function_profile_enabled, start_after_seconds=5, stop_after_seconds=8,
                    sampled_calls=self.profile_calls, sampled_wall_seconds=self.profile_wall,
                    sampled_thread_cpu_seconds=self.profile_cpu, functions=functions[:60]),
                limitation='Opt-in observer overhead, including existing card observer when enabled. '
                    'Exclusive CPU covers wrapped stages only; unwrapped work remains unknown. '
                    'Nested inclusive CPU/wall and cross-thread wall must not be summed. '
                    'Function profile samples owner turns only in the short window, not the entire host. '
                    'Finite-child process CPU is separately reported by the existing probe.')

    def close(self):
        for owner, name, original, had_attribute in reversed(self.originals):
            if had_attribute:
                setattr(owner, name, original)
            else:
                delattr(owner, name)
        self.originals.clear()
