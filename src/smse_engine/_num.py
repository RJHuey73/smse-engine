"""JS-parity rounding. The reference dry run is JavaScript, so match its semantics exactly."""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal


def js_to_fixed(x: float, digits: int) -> float:
    """``parseFloat(x.toFixed(digits))`` — half-up on the exact binary value."""
    q = Decimal(1).scaleb(-digits)
    return float(Decimal(x).quantize(q, rounding=ROUND_HALF_UP))


def js_round(x: float) -> int:
    """``Math.round`` — ties go toward +infinity."""
    return math.floor(x + 0.5)
