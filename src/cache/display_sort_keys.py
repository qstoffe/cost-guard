"""Order exact numeric values with ordinary SQLite BLOB indexes."""
from decimal import Decimal


def decimal_key(value: Decimal | None) -> bytes | None:
    if value is None:
        return None
    if not value.is_finite():
        raise ValueError("invalid_cost")
    if not value:
        return b"\x01"
    sign, digits, _ = value.as_tuple()
    end = len(digits)
    while digits[end - 1] == 0:
        end -= 1
    rank = (value.adjusted() + (1 << 63)).to_bytes(8, "big")
    magnitude = rank + bytes(digit + 1 for digit in digits[:end]) + b"\x00"
    if sign:
        return b"\x00" + bytes(255 - byte for byte in magnitude)
    return b"\x02" + magnitude


def whole_key(value: int) -> bytes:
    """Unsigned, prefix-free integer encoding ordered by magnitude."""
    size = (value.bit_length() + 7) // 8
    return size.to_bytes(2, "big") + value.to_bytes(size, "big")


def fraction_key(numerator: int, denominator: int) -> bytes:
    """Exact ratio order, including distinct shares with the same displayed %."""
    # Continued fractions compare their first unequal quotients in alternating
    # directions. The terminal marker sorts as a zero fractional remainder.
    key = bytearray()
    reverse = False
    while True:
        quotient, remainder = divmod(numerator, denominator)
        digits = whole_key(quotient)
        key.extend(bytes(255 - byte for byte in digits) if reverse else digits)
        if not remainder:
            key.append(255 if reverse else 0)
            return bytes(key)
        key.append(128)
        numerator, denominator = denominator, remainder
        reverse = not reverse
