"""Sample only the probe and its directly owned finite children; numeric Windows IO/RAM."""
import os
import sys
import time
from threading import Lock


class FiniteTimeline:
    """Opt-in scalar transitions; never changes priorities or acquires foreign locks."""
    def __init__(self, jobs, dispatcher):
        self.jobs, self.dispatcher = jobs, dispatcher
        self.started = time.monotonic()
        self.lock = Lock()
        self.events, self.previous, self.ordinals, self.originals = [], {}, {}, []
        self.dropped = 0
        for owner, names, capture in ((jobs, ('submit', '_park', '_start_next', '_receive', 'prioritize'), self.capture_jobs),
                (dispatcher, ('interest', '_collect'), self.capture_dispatcher)):
            for name in names:
                original = getattr(owner, name)

                def observed(*args, _original=original, _name=name, _capture=capture, **kwargs):
                    try:
                        return _original(*args, **kwargs)
                    finally:
                        _capture(_name)

                self.originals.append((owner, name, original))
                setattr(owner, name, observed)

    def record(self, key, trigger, fields):
        signature = tuple(fields.items())
        with self.lock:
            if self.previous.get(key) == signature:
                return
            self.previous[key] = signature
            if len(self.events) < 2500:
                self.events.append(dict(seconds=time.monotonic() - self.started,
                    wall_ms=int(time.time() * 1000), trigger=trigger, **fields))
            else:
                self.dropped += 1

    def capture_jobs(self, trigger):
        with self.jobs._lock:
            for key, job in self.jobs._jobs.items():
                ordinal = self.ordinals.setdefault(key, len(self.ordinals) + 1)
                progress = job.get('progress') or {}
                fields = dict(job=ordinal, kind=job['request'].kind.value, status=job['status'],
                    priority=job.get('priority'), slices=job.get('slices', 0), history_steps=job.get('history_steps', 0),
                    phase=progress.get('phase'), stage=progress.get('stage'), completed=progress.get('completed'),
                    total=progress.get('total'), parked=key in self.jobs._parked,
                    active=bool(self.jobs._active and self.jobs._active[0] == key),
                     queue_ms=job.get('queue_ms', 0), worker_ms=job.get('worker_ms', 0),
                     free=job.get('free'), yield_requested=job.get('yield_requested'),
                     admitted=job.get('admitted'), observation_ms=job.get('observation_ms'), covered=job.get('covered'),
                    not_before=job.get('not_before'), error=bool(job.get('error')))
                self.record(('job', ordinal), trigger, fields)

    def capture_dispatcher(self, trigger):
        with self.dispatcher.lock:
            interests = tuple(sorted({(tab['section'], tab['visible']) for tab in self.dispatcher.tabs.values()}))
            self.record('interest', trigger, dict(interests=interests))
            for request, entry in self.dispatcher.entries.items():
                if request.kind.value == 'token-mix':
                    self.record('token-mix-result', trigger, dict(kind='token-mix',
                        collected=bool(entry.get('result')), requested=entry.get('requested'),
                        job_present=bool(entry.get('job'))))

    def close(self):
        for owner, name, original in reversed(self.originals):
            setattr(owner, name, original)

    def summary(self):
        return dict(events=self.events, dropped=self.dropped,
            limitation='Opt-in wrapper transition times include observer overhead; job worker_ms is not CPU, '
                'queue_ms omits some cooperative waits. No raw IDs, requests, result payloads or scheduling changes.')


class Resources:
    def __init__(self):
        self.high_water = {}
        self.peak_working_set = 0
        self.peak_children = 0

    def sample(self, jobs):
        if sys.platform != 'win32':
            return
        with jobs._lock:
            children = [owner[0] for owner in getattr(jobs, '_parked', {}).values()]
            children += [owner['process'] for owner in getattr(jobs, '_retiring', ())]
            if jobs._active:
                children.append(jobs._active[1])
            pids = {child.pid for child in children if child.pid}
            self.peak_children = max(self.peak_children, len(pids))
            readings = {pid: self._read(pid) for pid in {os.getpid(), *pids}}
        self.peak_working_set = max(self.peak_working_set,
            sum(value['working_set_bytes'] for value in readings.values() if value))
        for pid, reading in readings.items():
            if reading:
                previous = self.high_water.setdefault(pid, {})
                for key, value in reading.items():
                    previous[key] = max(previous.get(key, 0), value)

    def summary(self):
        return dict(sampled_peak_aggregate_working_set_bytes=self.peak_working_set,
            peak_owned_children=self.peak_children,
            sampled_io_bytes={key: sum(value.get(key, 0) for value in self.high_water.values())
                              for key in ('read_bytes', 'write_bytes', 'other_bytes')},
            limitation='Sampled own-process counters; may miss final child IO and between-sample peaks. IO includes network/cache, not source payload content.')

    @staticmethod
    def _read(pid):
        import ctypes
        from ctypes import wintypes

        class Memory(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
                    'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                    'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

        kernel, psapi = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO)]
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
        handle = kernel.OpenProcess(0x410, False, pid)
        if not handle:
            return None
        try:
            memory, io = Memory(), IO()
            memory.cb = ctypes.sizeof(memory)
            if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
                return None
            if not kernel.GetProcessIoCounters(handle, ctypes.byref(io)):
                return None
            return dict(working_set_bytes=memory.WorkingSetSize, read_bytes=io.ReadTransferCount,
                        write_bytes=io.WriteTransferCount, other_bytes=io.OtherTransferCount)
        finally:
            kernel.CloseHandle(handle)
