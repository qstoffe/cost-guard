"""Bounded Unicode clipboard handoff; never read or log clipboard contents."""
import ctypes as c
from ctypes import wintypes as w
import time


def _allocate(kernel, payload):
    memory = kernel.GlobalAlloc(0x2, len(payload))  # GMEM_MOVEABLE
    if not memory:
        raise OSError("clipboard_unavailable")
    pointer = kernel.GlobalLock(memory)
    if not pointer:
        kernel.GlobalFree(memory)
        raise OSError("clipboard_unavailable")
    try:
        c.memmove(pointer, payload, len(payload))
    finally:
        kernel.GlobalUnlock(memory)
    return memory


def copy_text(hwnd, text):
    user = c.WinDLL("user32", use_last_error=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    for library, name, result, arguments in (
            (user, "OpenClipboard", w.BOOL, [w.HWND]),
            (user, "CloseClipboard", w.BOOL, []),
            (user, "EmptyClipboard", w.BOOL, []),
            (user, "SetClipboardData", w.HANDLE, [w.UINT, w.HANDLE]),
            (user, "RegisterClipboardFormatW", w.UINT, [w.LPCWSTR]),
            (kernel, "GlobalAlloc", w.HGLOBAL, [w.UINT, c.c_size_t]),
            (kernel, "GlobalLock", c.c_void_p, [w.HGLOBAL]),
            (kernel, "GlobalUnlock", w.BOOL, [w.HGLOBAL]),
            (kernel, "GlobalFree", w.HGLOBAL, [w.HGLOBAL])):
        function = getattr(library, name)
        function.restype, function.argtypes = result, arguments
    payload = text.encode("utf-16-le") + b"\0\0"
    memory = _allocate(kernel, payload)
    opened = False
    try:
        # Retry only brief contention, on the native host's clipboard worker.
        for attempt in range(5):
            opened = bool(user.OpenClipboard(hwnd))
            if opened:
                break
            if attempt < 4:
                time.sleep(0.02)
        if not opened or not user.EmptyClipboard():
            raise OSError("clipboard_unavailable")
        # The clipboard contains a bearer secret, not a roaming/history bookmark.
        for name in ("CanIncludeInClipboardHistory", "CanUploadToCloudClipboard"):
            identifier = user.RegisterClipboardFormatW(name)
            if not identifier:
                raise OSError("clipboard_unavailable")
            flag = _allocate(kernel, bytes(4))
            if not user.SetClipboardData(identifier, flag):
                kernel.GlobalFree(flag)
                raise OSError("clipboard_unavailable")
        if not user.SetClipboardData(13, memory):  # CF_UNICODETEXT
            raise OSError("clipboard_unavailable")
        memory = None  # Windows owns the allocation after SetClipboardData succeeds.
    finally:
        if opened:
            user.CloseClipboard()
        if memory:
            kernel.GlobalFree(memory)
