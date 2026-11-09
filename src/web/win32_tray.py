"""Narrow in-box Win32 notification icon and main-thread message pump."""
import ctypes as c
from ctypes import wintypes as w
import os
import uuid

from src.version import VERSION
from .process_identity import InstanceConflict
from .tray_icon import ICON_SIZES, icon_bits

CALLBACK = 0x8001
OPEN, EXIT = 1, 2
COPY = 3


class NotifyData(c.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT),
                ("uFlags", w.UINT), ("uCallbackMessage", w.UINT), ("hIcon", w.HICON),
                ("szTip", w.WCHAR * 128), ("dwState", w.DWORD), ("dwStateMask", w.DWORD),
                ("szInfo", w.WCHAR * 256), ("uVersion", w.UINT),
                ("szInfoTitle", w.WCHAR * 64), ("dwInfoFlags", w.DWORD),
                 ("guidItem", c.c_byte * 16), ("hBalloonIcon", w.HICON)]


class IconId(c.Structure):
    _fields_ = [("cbSize", w.DWORD), ("hWnd", w.HWND), ("uID", w.UINT),
                ("guidItem", c.c_byte * 16)]


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
        self.previous_dpi = None
        self.icon_size = None
        self.dpi_dirty = False
        self.failure = None
        self.events = []
        self.class_name = "CostGuardWeb-" + uuid.uuid4().hex
        self._bindings()
        try:
            # Mixed-mode DPI: this UI thread only, before any HWND/menu. Leave the
            # interpreter's process default (and other tools/threads) untouched.
            self.previous_dpi = self.user.SetThreadDpiAwarenessContext(c.c_void_p(-4))
            if not self.previous_dpi:
                raise InstanceConflict("tray_unavailable")
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
        _bind(u, "SetThreadDpiAwarenessContext", c.c_void_p, [c.c_void_p])
        _bind(u, "GetDpiForWindow", w.UINT, [w.HWND])
        _bind(u, "GetSystemMetricsForDpi", c.c_int, [c.c_int, w.UINT])
        _bind(u, "SetWindowPos", w.BOOL, [w.HWND, w.HWND, c.c_int, c.c_int,
                                        c.c_int, c.c_int, w.UINT])
        _bind(self.shell, "Shell_NotifyIconW", w.BOOL, [w.DWORD, c.POINTER(NotifyData)])
        _bind(self.shell, "Shell_NotifyIconGetRect", c.c_long,
              [c.POINTER(IconId), c.POINTER(w.RECT)])

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
        self.hwnd = self.user.CreateWindowExW(0, self.class_name, "Cost Guard",
                                             0, 0, 0, 0, 0, None, None, self.instance, None)
        if not self.hwnd:
            raise InstanceConflict("tray_unavailable")
        self._refresh_icon()
        self.menu = self.user.CreatePopupMenu()
        if not self.hwnd or not self.icon or not self.menu:
            raise InstanceConflict("tray_unavailable")
        for identifier, text in ((OPEN, "Open Cost Guard"), (COPY, "Copy Cost Guard link"),
                                 (EXIT, "Exit Cost Guard")):
            if not self.user.AppendMenuW(self.menu, 0, identifier, text):
                raise InstanceConflict("tray_unavailable")
        self.data = NotifyData(cbSize=c.sizeof(NotifyData), hWnd=self.hwnd, uID=1,
                               uFlags=7, uCallbackMessage=CALLBACK, hIcon=self.icon,
                                szTip=f"Cost Guard v{VERSION}")

    def install(self):
        if not self.shell.Shell_NotifyIconW(0, c.byref(self.data)):
            raise InstanceConflict("tray_unavailable")
        self.installed = True
        self._position_at_icon()
        self._refresh_icon()

    def _position(self, x, y):
        # Move only the invisible owner, so Windows chooses the popup monitor's
        # DPI. Cursor and menu coordinates both stay physical under PMv2.
        if not self.user.SetWindowPos(self.hwnd, None, x, y, 0, 0, 0x15):
            raise InstanceConflict("tray_unavailable")

    def _position_at_icon(self):
        identifier = IconId(cbSize=c.sizeof(IconId), hWnd=self.hwnd, uID=1)
        rect = w.RECT()
        if self.shell.Shell_NotifyIconGetRect(c.byref(identifier), c.byref(rect)) == 0:
            self._position(rect.left, rect.top)

    def _refresh_icon(self):
        dpi = self.user.GetDpiForWindow(self.hwnd)
        requested = self.user.GetSystemMetricsForDpi(49, dpi) if dpi else 0  # SM_CXSMICON
        if requested <= 0:
            raise InstanceConflict("tray_unavailable")
        size = min(ICON_SIZES, key=lambda value: abs(value - requested))
        if size == self.icon_size:
            return
        mask, pixels = icon_bits(size)
        icon = self.user.CreateIcon(self.instance, size, size, 1, 32, mask, pixels)
        if not icon:
            raise InstanceConflict("tray_unavailable")
        old = self.icon
        if self.installed:
            self.data.hIcon, self.data.uFlags = icon, 2  # NIF_ICON only
            try:
                if not self.shell.Shell_NotifyIconW(1, c.byref(self.data)):
                    self.data.hIcon = old
                    self.user.DestroyIcon(icon)
                    raise InstanceConflict("tray_unavailable")
            finally:
                self.data.uFlags = 7
        self.icon, self.icon_size = icon, size
        if old:
            self.user.DestroyIcon(old)

    def _popup(self):
        point = w.POINT()
        if not self.user.GetCursorPos(c.byref(point)):
            return
        self._position(point.x, point.y)
        self.user.SetForegroundWindow(self.hwnd)
        choice = self.user.TrackPopupMenu(self.menu, 0x100 | 0x2, point.x, point.y,
                                          0, self.hwnd, None)
        self.user.PostMessageW(self.hwnd, 0, 0, 0)
        self._position_at_icon()
        if choice in (OPEN, COPY, EXIT):
            self.events.append(choice)

    def _window_message(self, hwnd, message, first, second):
        # ctypes callbacks must not leak Python exceptions through the OS boundary.
        try:
            if message == self.taskbar_created:
                self.installed = False
                self.install()
                return 0
            if message in (0x2E0, 0x7E, 0x1A):  # DPI/display/settings change
                self.dpi_dirty = True
            if message == CALLBACK:
                if second == 0x203:  # WM_LBUTTONDBLCLK
                    self.events.append(OPEN)
                elif second in (0x205, 0x7B):  # right release / context menu
                    self._popup()
                return 0
            if message == 0x111 and first in (OPEN, COPY, EXIT):  # WM_COMMAND
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
        if self.dpi_dirty:
            self.dpi_dirty = False
            self._position_at_icon()
            self._refresh_icon()
        events, self.events = self.events, []
        return events

    def browser_failed(self):
        self._notify("Browser could not open. Retry Open Cost Guard, or run Diagnostics.", 2)

    def link_copied(self, success):
        message = ("Link copied. Paste into another browser within 2 minutes. It can be used once."
                   if success else "Link could not be copied. Retry Copy Cost Guard link.")
        self._notify(message, 1 if success else 2)

    def _notify(self, message, flags):
        self.data.uFlags = 0x10
        self.data.szInfoTitle = "Cost Guard"
        self.data.szInfo = message
        self.data.dwInfoFlags = flags
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
        if self.previous_dpi:
            self.user.SetThreadDpiAwarenessContext(self.previous_dpi)
            self.previous_dpi = None
