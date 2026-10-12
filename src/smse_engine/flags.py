"""Engine feature flags for T0-approved IMPLEMENT variants (Ruling Request 001 rev 2).

Every flag defaults to off. With all flags off, output is identical to dry-run parity.
None of these is Canon: flipping a default needs a RATIFY ruling and an addendum.
"""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class EngineFlags:
    flow_threshold_usd: bool = False  # R-02 / A1: threshold = 0.001 × shares × etf_close
    null_gamma_flip: bool = False  # R-04 / B1: no sign change -> flip is null, not 0.99 × price
    magnet_key_levels: bool = False  # R-05 / C1: resistance from magnets, zero-GEX strikes excluded

    def active(self) -> tuple[str, ...]:
        return tuple(f.name for f in fields(self) if getattr(self, f.name))


DEFAULT_FLAGS = EngineFlags()
