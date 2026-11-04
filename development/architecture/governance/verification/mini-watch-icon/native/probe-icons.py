"""Read icons/capture only windows belonging to the explicit owned test browser PID."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--pid', type=int, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--icon', type=Path, required=True)
p.add_argument('--case', required=True)
a = p.parse_args()
u, g, d = C.WinDLL('user32', use_last_error=True), C.WinDLL('gdi32'), C.WinDLL('dwmapi')
u.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
u.SetProcessDpiAwarenessContext(C.c_void_p(-4))
cb = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
u.EnumWindows.argtypes = [cb, W.LPARAM]
u.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
u.IsWindowVisible.argtypes = [W.HWND]
u.GetDpiForWindow.argtypes = [W.HWND]
u.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
u.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
u.GetClassLongPtrW.argtypes = [W.HWND, C.c_int]
u.GetClassLongPtrW.restype = C.c_size_t
u.SendMessageTimeoutW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM, W.UINT, W.UINT, C.POINTER(C.c_size_t)]
u.SendMessageTimeoutW.restype = W.LPARAM
u.LoadImageW.argtypes = [W.HINSTANCE, W.LPCWSTR, W.UINT, C.c_int, C.c_int, W.UINT]
u.LoadImageW.restype = W.HICON
u.DestroyIcon.argtypes = [W.HICON]
u.DrawIconEx.argtypes = [W.HDC, C.c_int, C.c_int, W.HICON, C.c_int, C.c_int, W.UINT, W.HBRUSH, W.UINT]
u.GetWindowDC.argtypes = [W.HWND]
u.GetWindowDC.restype = W.HDC
u.ReleaseDC.argtypes = [W.HWND, W.HDC]
u.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
g.CreateCompatibleDC.argtypes = [W.HDC]
g.CreateCompatibleDC.restype = W.HDC
g.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
g.CreateCompatibleBitmap.restype = W.HBITMAP
g.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
g.SelectObject.restype = W.HGDIOBJ
g.PatBlt.argtypes = [W.HDC, C.c_int, C.c_int, C.c_int, C.c_int, W.DWORD]
g.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT]
g.DeleteObject.argtypes = [W.HGDIOBJ]
g.DeleteDC.argtypes = [W.HDC]
d.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, C.c_void_p, W.DWORD]


def png(name, width, height, rgba):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    content = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    content += chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
    (a.output / name).write_bytes(content)
    return {'file': name, 'pixelSha256': hashlib.sha256(rgba).hexdigest()}


def render(hwnd, name, width=32, height=32, icon=None):
    dc = u.GetWindowDC(hwnd)
    memory = g.CreateCompatibleDC(dc)
    bitmap = g.CreateCompatibleBitmap(dc, width, height)
    old = g.SelectObject(memory, bitmap)
    try:
        g.PatBlt(memory, 0, 0, width, height, 0x00FF0062)  # white background
        success = u.DrawIconEx(memory, 0, 0, icon, width, height, 0, None, 3) if icon else u.PrintWindow(hwnd, memory, 2)
        g.SelectObject(memory, old)
        header = C.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0))
        raw = C.create_string_buffer(width * height * 4)
        if g.GetDIBits(memory, bitmap, 0, height, raw, header, 0) != height:
            raise C.WinError(C.get_last_error())
        rgba = bytearray(len(raw.raw))
        rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = raw.raw[2::4], raw.raw[1::4], raw.raw[0::4], b'\xff' * (width * height)
        return {**png(name, width, height, rgba), 'drawSucceeded': bool(success)}
    finally:
        g.DeleteObject(bitmap)
        g.DeleteDC(memory)
        u.ReleaseDC(hwnd, dc)


items = []


@cb
def visit(hwnd, _):
    pid = W.DWORD()
    u.GetWindowThreadProcessId(hwnd, C.byref(pid))
    if pid.value != a.pid or not u.IsWindowVisible(hwnd):
        return True
    title, rect, frame = C.create_unicode_buffer(512), W.RECT(), W.RECT()
    u.GetWindowTextW(hwnd, title, len(title))
    u.GetWindowRect(hwnd, C.byref(rect))
    d.DwmGetWindowAttribute(hwnd, 9, C.byref(frame), C.sizeof(frame))
    item = {'hwnd': int(hwnd), 'title': title.value, 'dpi': u.GetDpiForWindow(hwnd),
            'rect': [rect.left, rect.top, rect.right, rect.bottom],
            'visibleFrame': [frame.left, frame.top, frame.right, frame.bottom], 'icons': {}}
    for kind, value in [('small', 0), ('large', 1), ('small2', 2)]:
        handle = C.c_size_t()
        C.set_last_error(0)
        ok = u.SendMessageTimeoutW(hwnd, 0x7F, value, item['dpi'], 2, 400, C.byref(handle))
        result = {'querySucceeded': bool(ok), 'error': C.get_last_error(), 'nonNull': bool(handle.value)}
        if ok and handle.value:
            result.update(render(hwnd, f'{a.case}-{int(hwnd)}-{kind}.png', icon=handle.value))
        item['icons'][kind] = result
    for kind, index in [('classLarge', -14), ('classSmall', -34)]:
        handle = u.GetClassLongPtrW(hwnd, index)
        result = {'nonNull': bool(handle)}
        if handle:
            result.update(render(hwnd, f'{a.case}-{int(hwnd)}-{kind}.png', icon=handle))
        item['icons'][kind] = result
    if 100 < rect.right - rect.left < 1100 and 100 < rect.bottom - rect.top < 600:
        item['capture'] = render(hwnd, f'{a.case}-{int(hwnd)}-frame.png', rect.right - rect.left, rect.bottom - rect.top)
    items.append(item)
    return True


u.EnumWindows(visit, 0)
canonical = u.LoadImageW(None, str(a.icon), 1, 32, 32, 0x10)
if not canonical:
    raise C.WinError(C.get_last_error())
try:
    canonical_result = render(items[0]['hwnd'] if items else None, f'{a.case}-canonical.png', icon=canonical)
finally:
    u.DestroyIcon(canonical)  # only the icon this helper loaded; never borrowed handles
v = sys.getwindowsversion()
result = {'case': a.case, 'os': {'major': v.major, 'minor': v.minor, 'build': v.build},
          'ownedPid': a.pid, 'windows': items, 'canonical': canonical_result,
          'limitation': 'Read-only native HICON metadata and owned-window captures, not taskbar/Alt+Tab shell pixels.'}
(a.output / f'{a.case}-native.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
