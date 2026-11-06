"""Opt-in child-process report timings; numeric metadata only, never source rows."""
from contextlib import ExitStack
import json
import sys
import time
from unittest.mock import patch

from development.tests.integration.web_live_observations import ProbeObservations


def peak_memory():
    """Own-process numeric Windows high-water marks, not a logical-job memory sum."""
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
            'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
            'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

    kernel, psapi = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return None
    return dict(working_set_bytes=counters.PeakWorkingSetSize, commit_bytes=counters.PeakPagefileUsage)


def measured_report(sender, request):
    from src.reports.service import ReportService
    from src.sources.opencode_v2 import OpenCodeV2Source
    from src.web.jobs import ProgressRelay, run_report

    observations = ProbeObservations()
    services = []
    original_init = ReportService.__init__
    original_observe = ProgressRelay.observe
    last = [float('-inf')]
    cpu_started = time.process_time()

    def report(event=None):
        now = time.monotonic()
        if event is not None and now - last[0] < 10:
            return
        last[0] = now
        metrics = services[-1].metrics.snapshot() if services else None
        source = services[-1].source if services else None
        print(json.dumps(dict(report_observation=request.kind.value,
            seconds=round(now - observations.started, 3), progress=event,
            cpu_seconds=round(time.process_time() - cpu_started, 3),
             metrics=metrics, operations=dict(observations.completed),
             max_seconds=dict(observations.maximum),
             process_peak_memory=peak_memory(),
            source_stage=getattr(source, '_diagnostics', {}).get('last_snapshot_stage'))), flush=True)

    def initialize(service, *args, **kwargs):
        original_init(service, *args, **kwargs)
        services.append(service)

    def observe(relay, event):
        original_observe(relay, event)
        report(event.to_json())

    def measured(original, name):
        wrapped = observations.wrapper(original, name)

        def operation(*args, **kwargs):
            try:
                return wrapped(*args, **kwargs)
            finally:
                report(dict(phase='source_observation', operation=name,
                            completed=observations.completed[name]))
        return operation

    with ExitStack() as stack:
        stack.enter_context(patch.object(ReportService, '__init__', initialize))
        stack.enter_context(patch.object(ProgressRelay, 'observe', observe))
        for owner, methods in ((OpenCodeV2Source, ('_list_native_sessions', '_load_messages')),
                               (ReportService, ('prepare_roots', '_prompt_block'))):
            for method in methods:
                stack.enter_context(patch.object(owner, method,
                    measured(getattr(owner, method), owner.__name__ + '.' + method)))
        try:
            run_report(sender, request)
        finally:
            report()
