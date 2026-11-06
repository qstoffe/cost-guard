"""Sample only the probe and its directly owned finite children; numeric Windows IO/RAM."""
import os
import sys


class Resources:
    def __init__(self):
        self.high_water = {}
        self.peak_working_set = 0
        self.peak_children = 0

    def sample(self, jobs):
        if sys.platform != 'win32':
            return
        with jobs._lock:
            children = [owner[0] for owner in jobs._parked.values()]
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
