"""SMSE Engine v0 — SFX-MARKET-011–014 deterministic core.

Pipeline: raw -> normalize (012) -> synthesize (011 contract) -> register -> report (014).
Fetchers, Scheduler and AUTO-001A (Make.com) wiring are out of scope for v0.
"""

from smse_engine.constants import ENGINE_VERSION
from smse_engine.normalizer import NormalizationError, normalize
from smse_engine.pipeline import PipelineResult, run_pipeline
from smse_engine.reporter import report
from smse_engine.synthesizer import synthesize

__all__ = [
    "ENGINE_VERSION",
    "NormalizationError",
    "PipelineResult",
    "normalize",
    "report",
    "run_pipeline",
    "synthesize",
]
