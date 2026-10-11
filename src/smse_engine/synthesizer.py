"""SMSE-Synthesizer-Agent — normalized -> SMSE_v1 (SFX-MARKET-011 contract)."""

from __future__ import annotations

from smse_engine import constants as C
from smse_engine._num import js_round
from smse_engine.schema import (
    GammaRegime,
    Normalized,
    RegimePrimary,
    RegimeRiskNote,
    SmseCot,
    SmseFlows,
    SmseGamma,
    SmseKeyLevels,
    SmseRegime,
    SMSEv1,
    Trend,
)

# Regime classification matrix. Anything not listed (a Neutral axis) is Transition.
_REGIME_MATRIX: dict[tuple[Trend, GammaRegime], RegimePrimary] = {
    ("Up", "LongGamma"): "StableUp",
    ("Down", "ShortGamma"): "StableDown",
    ("Up", "ShortGamma"): "VolatileUp",
    ("Down", "LongGamma"): "VolatileDown",
}


def classify_regime(trend: Trend, gamma: GammaRegime) -> RegimePrimary:
    return _REGIME_MATRIX.get((trend, gamma), "Transition")


def synthesize(asset: str, timestamp: str, norm: Normalized) -> SMSEv1:
    cot, gamma, flows, price = norm.cot, norm.gamma, norm.flows, norm.price
    risk: RegimeRiskNote = cot.risk_note if cot.risk_note != "Normal" else "Uncrowded"
    support = sorted((js_round(price.ma50), js_round(price.ma200)), reverse=True)
    return SMSEv1(
        asset=asset,
        timestamp=timestamp,
        cot=SmseCot(
            bias=cot.bias,
            z_score=cot.z_score,
            extreme_flag=cot.extreme_flag,
            risk_note=cot.risk_note,
            stale=cot.stale,
        ),
        gamma=SmseGamma(
            regime=gamma.regime,
            gamma_flip_level=gamma.gamma_flip_level,
            volatility_note=gamma.volatility_note,
            gamma_magnets=list(gamma.gamma_magnets),
        ),
        flows=SmseFlows(bias=flows.flow_bias, crowding=flows.crowding, flow_threshold=flows.flow_threshold),
        regime=SmseRegime(primary=classify_regime(price.trend, gamma.regime), risk_note=risk),
        key_levels=SmseKeyLevels(
            support=[v for v in support if v < price.close],
            resistance=[js_round(price.close * k) for k in C.RESISTANCE_COEFFS],
            gamma_magnets=list(gamma.gamma_magnets),
        ),
    )
