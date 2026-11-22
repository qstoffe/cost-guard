"""Exact subtotal accumulation shared by local historical reducers."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class ExactCost:
    """Use integer coefficients, independent of Decimal's ambient context."""
    coefficient: int = 0
    exponent: int = 0

    def add(self, value):
        if not value.is_finite() or value < 0:
            raise ValueError("invalid_archive_category_cost")
        _, digits, exponent = value.as_tuple()
        if not any(digits):
            return
        contribution = int("".join(map(str, digits)))
        if not self.coefficient:
            self.coefficient, self.exponent = contribution, exponent
        else:
            common = min(self.exponent, exponent)
            self.coefficient = (self.coefficient * 10 ** (self.exponent - common) +
                                contribution * 10 ** (exponent - common))
            self.exponent = common

    def amount(self):
        return Decimal((0, tuple(map(int, str(self.coefficient))), self.exponent))
