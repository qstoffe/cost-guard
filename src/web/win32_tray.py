"""Narrow in-box Win32 notification icon and main-thread message pump."""
import ctypes as c
from ctypes import wintypes as w
import os
import uuid

from src.version import VERSION
from .process_identity import InstanceConflict
from .tray_icon import icon_bits

CALLBACK = 0x8001
OPEN, EXIT = 1, 2


class NotifyData(c.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT),
                ("uFlags", w.UINT), ("uCallbackMessage", w.UINT), ("hIcon", w.HICON),
                ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD),
                ("szInfo", w.WCHAR * 256), ("uVersion", w.UINT),
                ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
                ("guidItem", c.c_byte * 16), ("hBalloonIcon", w.HICON)]


def _bind(library, name, result, arguments):
    function = getattr(library, name)
    function.restype, function.argtypes = result, arguments
    return function


class Tray:
    def __init__(self):
        if os.name != "nt":
            raise InstanceConflict("tray_unavailable")
        self.user = c.WinDLL("user32", use_last_error=True)
        self.shell = c.WinDLL("shell32", use_last_error=True)
        self.kernel = c.WinDLL("kernel32", use_last_error=True)
        self.hwnd = self.icon = self.menu = self.atom = None
        self.installed = False
        self.failure = None
        self.events = []
        self.class_name = "CostGuardWeb-" + uuid.uuid4().hex
        self._bindings()
        try:
            self._create()
        except BaseException:
            self.close()
            raise

    def _bindings(self):
        u = self.user
        self.proc_type = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        _bind(self.kernel, "GetModuleHandleW", w.HMODULE, [w.LPCWSTR])
        _bind(u, "DefWindowProcW", c.c_ssize_t, [w.HWND, w.UINT, w.WPARAM, w.LPARAM])
        _bind(u, "CreateWindowExW", w.HWND, [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
              c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p])
        _bind(u, "CreateIcon", w.HICON, [w.HINSTANCE, c.c_int, c.c_int, w.BYTE, w.BYTE,
                                        c.c_void_p, c.c_void_p])
        _bind(u, "CreatePopupMenu", w.HMENU, [])
        _bind(u, "AppendMenuW", w.BOOL, [w.HMENU, w.UINT, c.c_size_t, w.LPCWSTR])
        _bind(u, "DestroyIcon", w.BOOL, [w.HICON])
        _bind(u, "DestroyWindow", w.BOOL, [w.HWND])
        _bind(u, "DestroyMenu", w.BOOL, [w.HMENU])
        _bind(u, "UnregisterClassW", w.BOOL, [w.LPCWSTR, w.HINSTANCE])
        _bind(u, "RegisterWindowMessageW", w.UINT, [w.LPCWSTR])
        _bind(u, "PeekMessageW", w.BOOL, [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT])
        _bind(u, "TranslateMessage", w.BOOL, [c.POINTER(w.MSG)])
        _bind(u, "DispatchMessageW", c.c_ssize_t, [c.POINTER(w.MSG)])
        _bind(u, "GetCursorPos", w.BOOL, [c.POINTER(w.POINT)])
        _bind(u, "SetForegroundWindow", w.BOOL, [w.HWND])
        _bind(u, "TrackPopupMenu", w.UINT, [w.HMENU, w.UINT, c.c_int, c.c_int,
                                           c.c_int, w.HWND, c.c_void_p])
        _bind(u, "PostMessageW", w.BOOL, [w.HWND, w.UINT, w.WPARAM, w.LPARAM])
        _bind(self.shell, "Shell_NotifyIconW", w.BOOL, [w.DWORD, c.POINTER(NotifyData)])

    def _create(self):
        class WindowClass(c.Structure):
            _fields_ = [("style", w.UINT), ("lpfnWndProc", self.proc_type),
                        ("cbClsExtra", c.c_int), ("cbWndExtra", c.c_int),
                        ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                        ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH),
                        ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR)]

        self.instance = self.kernel.GetModuleHandleW(None)
        self.taskbar_created = self.user.RegisterWindowMessageW("TaskbarCreated")
        self.callback = self.proc_type(self._window_message)  # Keep alive until window destroyed.
        definition = WindowClass(lpfnWndProc=self.callback, hInstance=self.instance,
                                 lpszClassName=self.class_name)
        _bind(self.user, "RegisterClassW", w.ATOM, [c.POINTER(WindowClass)])
        self.atom = self.user.RegisterClassW(c.byref(definition))
        if not self.atom or not self.taskbar_created:
            raise InstanceConflict("tray_unavailable")
        # Hidden top-level window receives Explorer's TaskbarCreated broadcast.
        self.hwnd = self.user.CreateWindowExW(0, self.class_name, "Cost Guard Web Beta",
                                             0, 0, 0, 0, 0, None, None, self.instance, None)
        mask, pixels = icon_bits()
        self.icon = self.user.CreateIcon(self.instance, 32, 32, 1, 32, mask, pixels)
        self.menu = self.user.CreatePopupMenu()
        if not self.hwnd or not self.icon or not self.menu:
            raise InstanceConflict("tray_unavailable")
        for identifier, text in ((OPEN, "Open Cost Guard"), (EXIT, "Exit Cost Guard")):
            if not self.user.AppendMenuW(self.menu, 0, identifier, text):
                raise InstanceConflict("tray_unavailable")
        self.data = NotifyData(cbSize=c.sizeof(NotifyData), hWnd=self.hwnd, uID=1,
                               uFlags=7, uCallbackMessage=CALLBACK, hIcon=self.icon,
                               szTip=f"Cost Guard Web Beta v{VERSION}")

    def install(self):
        if not self.shell.Shell_NotifyIconW(0, c.byref(self.data)):
            raise InstanceConflict("tray_unavailable")
        self.installed = True

    def _popup(self):
        point = w.POINT()
        if not self.user.GetCursorPos(c.byref(point)):
            return
        self.user.SetForegroundWindow(self.hwnd)
        choice = self.user.TrackPopupMenu(self.menu, 0x100 | 0x2, point.x, point.y,
                                          0, self.hwnd, None)
        self.user.PostMessageW(self.hwnd, 0, 0, 0)
        if choice in (OPEN, EXIT):
            self.events.append(choice)

    def _window_message(self, hwnd, message, first, second):
        # ctypes callbacks must not leak Python exceptions through the OS boundary.
        try:
            if message == self.taskbar_created:
                self.installed = False
                self.install()
                return 0
            if message == CALLBACK:
                if second == 0x203:  # WM_LBUTTONDBLCLK
                    self.events.append(OPEN)
                elif second in (0x205, 0x7B):  # right release / context menu
                    self._popup()
                return 0
            if message == 0x111 and first in (OPEN, EXIT):  # WM_COMMAND
                self.events.append(first)
                return 0
        except Exception as error:
            self.failure = error
            return 0
        return self.user.DefWindowProcW(hwnd, message, first, second)

    def poll(self):
        message = w.MSG()
        while self.user.PeekMessageW(c.byref(message), None, 0, 0, 1):
            if message.message == 0x12:  # WM_QUIT
                self.events.append(EXIT)
            else:
                self.user.TranslateMessage(c.byref(message))
                self.user.DispatchMessageW(c.byref(message))
        if self.failure:
            raise InstanceConflict("tray_unavailable") from self.failure
        events, self.events = self.events, []
        return events

    def browser_failed(self):
        self.data.uFlags = 0x10
        self.data.szInfoTitle = "Cost Guard Web Beta"
        self.data.szInfo = "Browser could not open. Retry Open Cost Guard, or run Diagnostics."
        self.data.dwInfoFlags = 2
        self.shell.Shell_NotifyIconW(1, c.byref(self.data))
        self.data.uFlags = 7

    def close(self):
        if self.installed:
            self.shell.Shell_NotifyIconW(2, c.byref(self.data))
            self.installed = False
        for attribute, destroy in (("menu", self.user.DestroyMenu),
                                   ("hwnd", self.user.DestroyWindow),
                                   ("icon", self.user.DestroyIcon)):
            handle = getattr(self, attribute)
            if handle:
                destroy(handle)
                setattr(self, attribute, None)
        if self.atom:
            self.user.UnregisterClassW(self.class_name, self.instance)
            self.atom = None
