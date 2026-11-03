"""Canonical original CG pixel artwork shared by Windows and the browser favicon.

The 16-unit grid deliberately uses open counters and a solid dark tile with a pale
rim: the cyan monogram stays legible on both light and dark notification areas.
No installed font, image library, download or independent copy of the design.
"""
import struct

ICON_SIZES = (16, 20, 24, 32, 48)
C_LETTER = ("01111", "11000", "11000", "11000", "11000", "11000", "01111")
G_LETTER = ("01110", "11001", "11000", "11011", "11001", "11001", "01110")


def _pixel(x, y):
    if not (1 <= x <= 14 and 1 <= y <= 14) or (x in (1, 14) and y in (1, 14)):
        return (0, 0, 0, 0)
    if x in (1, 14) or y in (1, 14):
        return (191, 235, 240, 255)
    if 5 <= y < 12:
        for left, letter in ((2, C_LETTER), (8, G_LETTER)):
            if left <= x < left + 5 and letter[y - 5][x - left] == "1":
                return (120, 220, 232, 255)
    return (16, 33, 37, 255)


def icon_bits(size=32):
    """Return word-aligned AND mask and bottom-up BGRA for Win32 CreateIcon.

    Snap the canonical cells to each physical pixel grid, rather than asking the
    shell to shrink one 32px icon. All channels are opaque or fully transparent.
    """
    if size not in ICON_SIZES:
        raise ValueError("unsupported_icon_size")
    rows, masks = [], []
    stride = ((size + 15) // 16) * 2
    for y in range(size):
        row = bytearray()
        mask = bytearray(stride)
        for x in range(size):
            red, green, blue, alpha = _pixel(x * 16 // size, y * 16 // size)
            row.extend((blue, green, red, alpha))
            if not alpha:
                mask[x // 8] |= 0x80 >> (x % 8)
        rows.append(bytes(row))
        masks.append(bytes(mask))
    return b"".join(reversed(masks)), b"".join(reversed(rows))


def favicon_bytes():
    """Multi-resolution ICO from the exact tray pixels; checked-in asset is tested."""
    entries, images = [], []
    offset = 6 + 16 * len(ICON_SIZES)
    for size in ICON_SIZES:
        mask, pixels = icon_bits(size)
        # ICO DIB masks use DWORD alignment; CreateIcon masks use WORD alignment.
        stride = ((size + 15) // 16) * 2
        mask = b"".join(mask[i:i + stride].ljust(((size + 31) // 32) * 4, b"\0")
                        for i in range(0, len(mask), stride))
        header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(pixels), 0, 0, 0, 0)
        image = header + pixels + mask
        entries.append(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), offset))
        images.append(image)
        offset += len(image)
    return struct.pack("<HHH", 0, 1, len(entries)) + b"".join(entries + images)
