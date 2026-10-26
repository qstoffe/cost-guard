"""Original bundled 32px shield/bar icon, rendered without image dependencies."""


def icon_bits():
    """Return Win32 CreateIcon AND mask and bottom-up BGRA pixels.

    White outline, navy shield and cyan bars remain distinct on light/dark trays.
    The source artwork is part of Cost Guard, licensed with the repository.
    """
    rows = []
    mask = bytearray()
    for y in range(32):
        row = bytearray()
        transparent = 0
        for x in range(32):
            inside = 4 <= y <= 27 and abs(x - 15.5) <= min(12, (30 - y) * 0.85)
            edge = inside and (y == 4 or abs(x - 15.5) > min(10, (28 - y) * 0.85))
            bar = inside and 10 <= y <= 22 and (
                9 <= x <= 12 and y >= 17 or 14 <= x <= 17 and y >= 13 or 19 <= x <= 22)
            color = (245, 245, 245) if edge else (230, 205, 40) if bar else (70, 37, 15)
            row.extend((*color, 255) if inside else (0, 0, 0, 0))
            transparent = (transparent << 1) | int(not inside)
        rows.append(bytes(row))
        mask.extend(transparent.to_bytes(4, "big"))
    mask_rows = [mask[index:index + 4] for index in range(0, len(mask), 4)]
    return b"".join(reversed(mask_rows)), b"".join(reversed(rows))
