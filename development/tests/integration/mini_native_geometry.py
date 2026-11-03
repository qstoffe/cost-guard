"""Opt-in own-PID Windows PiP geometry/capture; never reads unrelated window data."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import struct
import time
import zlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=3)
    args = parser.parse_args()
    if not 0 < args.seconds <= 10:
        parser.error('measurement must be bounded to ten seconds')
    user = C.WinDLL('user32', use_last_error=True)
    dwm = C.WinDLL('dwmapi')
    gdi = C.WinDLL('gdi32')
    user.SetProcessDpiAwarenessContext.argtypes = [C.c_void_p]
    if not user.SetProcessDpiAwarenessContext(C.c_void_p(-4)):
        raise C.WinError(C.get_last_error())
    callback_type = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    user.EnumWindows.argtypes = [callback_type, W.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    user.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.GetClientRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    user.IsWindowVisible.argtypes = [W.HWND]
    user.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    user.GetDpiForWindow.argtypes = [W.HWND]
    dwm.DwmGetWindowAttribute.argtypes = [W.HWND, W.DWORD, C.c_void_p, W.DWORD]
    user.GetWindowDC.argtypes = [W.HWND]
    user.GetWindowDC.restype = W.HDC
    user.ReleaseDC.argtypes = [W.HWND, W.HDC]
    user.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    gdi.CreateCompatibleDC.argtypes = [W.HDC]
    gdi.CreateCompatibleDC.restype = W.HDC
    gdi.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
    gdi.CreateCompatibleBitmap.restype = W.HBITMAP
    gdi.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    gdi.SelectObject.restype = W.HGDIOBJ
    gdi.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p, C.c_void_p, W.UINT]
    gdi.DeleteObject.argtypes = [W.HGDIOBJ]
    gdi.DeleteDC.argtypes = [W.HDC]

    def rectangle(hwnd, method):
        value = W.RECT()
        if method == 'dwm':
            if dwm.DwmGetWindowAttribute(hwnd, 9, C.byref(value), C.sizeof(value)):
                return None
        elif not getattr(user, method)(hwnd, C.byref(value)):
            raise C.WinError(C.get_last_error())
        return [value.left, value.top, value.right, value.bottom]

    def windows():
        result = []

        @callback_type
        def visit(hwnd, _):
            pid = W.DWORD()
            user.GetWindowThreadProcessId(hwnd, C.byref(pid))
            if pid.value == args.pid and user.IsWindowVisible(hwnd):
                title = C.create_unicode_buffer(512)
                user.GetWindowTextW(hwnd, title, len(title))
                result.append({'hwnd': int(hwnd), 'title': title.value,
                    'dpi': user.GetDpiForWindow(hwnd), 'window': rectangle(hwnd, 'GetWindowRect'),
                    'visibleFrame': rectangle(hwnd, 'dwm'), 'client': rectangle(hwnd, 'GetClientRect')})
            return True

        user.EnumWindows(visit, 0)
        return result

    def capture(item):
        hwnd = item['hwnd']
        left, top, right, bottom = item['window']
        width, height = right - left, bottom - top
        dc = user.GetWindowDC(hwnd)
        memory = gdi.CreateCompatibleDC(dc)
        bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
        previous = gdi.SelectObject(memory, bitmap)
        try:
            printed = bool(user.PrintWindow(hwnd, memory, 2))
            gdi.SelectObject(memory, previous)
            header = C.create_string_buffer(struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0))
            pixels = C.create_string_buffer(width * height * 4)
            if gdi.GetDIBits(memory, bitmap, 0, height, pixels, header, 0) != height:
                raise C.WinError(C.get_last_error())
            bgra = pixels.raw
            rgba = bytearray(len(bgra))
            rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = bgra[2::4], bgra[1::4], bgra[0::4], b'\xff' * (width * height)

            def chunk(kind, content):
                return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind + content))

            scanlines = b''.join(b'\x00' + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
            image = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
            image += chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b'')
            name = args.output.with_name(args.output.stem + f'-{hwnd}.png')
            name.write_bytes(image)
            return {'file': name.name, 'widthPhysical': width, 'heightPhysical': height, 'printWindowSucceeded': printed,
                'distinctSampledColors': len(set(bgra[i:i + 3] for i in range(0, len(bgra), 160)))}
        finally:
            gdi.DeleteObject(bitmap)
            gdi.DeleteDC(memory)
            user.ReleaseDC(hwnd, dc)

    initial_handles = {item['hwnd'] for item in windows()}
    print('{"ready":true}', flush=True)
    start = time.monotonic()
    samples, previous = [], None
    while time.monotonic() - start < args.seconds:
        current = windows()
        if current != previous:
            samples.append({'elapsedMs': round((time.monotonic() - start) * 1000), 'windows': current})
            previous = current
        time.sleep(.02)
    final = windows()
    for item in final:
        item['openedAfterStart'] = item['hwnd'] not in initial_handles
        if item['openedAfterStart'] and item['window'][3] - item['window'][1] > 100:
            item['capture'] = capture(item)
    result = {'units': 'physical screen pixels; DPI-aware Win32/DWM', 'pid': args.pid, 'samples': samples, 'final': final}
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
