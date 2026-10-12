"""Ratified constants (SFX-MARKET-012, addendum v8.12.0 ``ratified_constants``).

Changing any value here is a Canon change, not a refactor: T0 GO required.
"""

from typing import Final

ENGINE_VERSION: Final = "smse-engine/0.1.0"
SCHEMA_VERSION: Final = "SMSE_v1.1"  # SFX-MARKET-011 v1.1

# COT z-score bands. Comparisons are strict, so |z| == 0.5 or 1.5 falls to the inner band.
Z_STRONG: Final = 1.5
Z_WEAK: Final = 0.5

# COT staleness. ``data_age_days > STALE_AFTER_DAYS`` triggers fallback neutralisation.
STALE_AFTER_DAYS: Final = 7

# flow_threshold = FLOW_THRESHOLD_COEFF * shares_outstanding.
FLOW_THRESHOLD_COEFF: Final = 0.001

# Dry-run carry-overs (observed in smse-pipeline-dryrun.jsx, not stated in the addendum).
GAMMA_FLIP_FALLBACK_COEFF: Final = 0.99
GAMMA_MAGNET_COUNT: Final = 3
RESISTANCE_COEFFS: Final = (1.01, 1.025)

CANON_REFS: Final = ("SFX-MARKET-011", "SFX-MARKET-012", "SFX-MARKET-013", "SFX-MARKET-014")
