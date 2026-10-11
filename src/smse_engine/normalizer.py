"""Normalizer-Agent — SFX-MARKET-012 raw -> normalized transform.

Every rule below is either stated in the v8.12.0 addendum or carried over verbatim
from the T0-authorized dry run (``smse-pipeline-dryrun.jsx``). Parity is pinned by
``tests/test_parity.py`` against a JS oracle built from that file.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from itertools import pairwise

from smse_engine import constants as C
from smse_engine._num import js_round, js_to_fixed
from smse_engine.schema import (
    CotBias,
    CotRaw,
    CotRiskNote,
    EtfFlowsRaw,
    ExtremeFlag,
    FlowBias,
    GammaRegime,
    Normalized,
    NormCot,
    NormFlows,
    NormGamma,
    NormPrice,
    OptionsRaw,
    PriceRaw,
    RawBundle,
    Trend,
    VolatilityNote,
)


class NormalizationError(ValueError):
    """Input cannot be normalized deterministically. Fail closed; never coerce."""


def z_score(net: int, history: list[int]) -> float:
    """Population z-score of ``net`` against ``history``, rounded like ``toFixed(2)``."""
    if len(history) < 2:
        raise NormalizationError("historical_net needs at least 2 observations")
    mean = sum(history) / len(history)
    std = math.sqrt(sum((h - mean) ** 2 for h in history) / len(history))
    if std == 0:
        raise NormalizationError("historical_net has zero variance; z-score undefined")
    return js_to_fixed((net - mean) / std, 2)


def cot_band(z: float) -> CotBias:
    if z > C.Z_STRONG:
        return "StrongLong"
    if z > C.Z_WEAK:
        return "Long"
    if z < -C.Z_STRONG:
        return "StrongShort"
    if z < -C.Z_WEAK:
        return "Short"
    return "Neutral"


def normalize_cot(raw: CotRaw) -> NormCot:
    net = raw.noncommercial_long - raw.noncommercial_short
    z = z_score(net, raw.historical_net)
    stale = raw.data_age_days > C.STALE_AFTER_DAYS
    bias: CotBias
    extreme: ExtremeFlag
    risk: CotRiskNote
    if stale:
        bias, extreme, risk = "Neutral", "None", "Normal"
    else:
        bias = cot_band(z)
        extreme = "BullishExtreme" if z > C.Z_STRONG else "BearishExtreme" if z < -C.Z_STRONG else "None"
        risk = ("CrowdedLong" if z > 0 else "CrowdedShort") if abs(z) > C.Z_STRONG else "Normal"
    return NormCot(net=net, z_score=z, bias=bias, extreme_flag=extreme, risk_note=risk, stale=stale)


def _net_gex_by_strike(raw: OptionsRaw) -> list[tuple[float, float, float, float]]:
    """(strike, net_gex, call_gex, put_gex), ascending strike, same-strike rows summed."""
    agg: OrderedDict[float, list[float]] = OrderedDict()
    for row in sorted(raw.chain, key=lambda r: r.strike):
        cg = row.call_gamma * row.call_oi
        pg = row.put_gamma * row.put_oi
        acc = agg.setdefault(row.strike, [0.0, 0.0])
        acc[0] += cg
        acc[1] += pg
    return [(k, cg - pg, cg, pg) for k, (cg, pg) in agg.items()]


def gamma_flip(rows: list[tuple[float, float, float, float]]) -> int | None:
    """First strike interval where net GEX changes sign, linearly interpolated."""
    for (sa, ga, _, _), (sb, gb, _, _) in pairwise(rows):
        if (ga <= 0 < gb) or (ga >= 0 > gb):
            return js_round(sa + (sb - sa) * (abs(ga) / (abs(ga) + abs(gb))))
    return None


def normalize_gamma(raw: OptionsRaw) -> NormGamma:
    rows = _net_gex_by_strike(raw)
    call_gex = sum(r[2] for r in rows)
    put_gex = sum(r[3] for r in rows)
    net_gamma = js_to_fixed(call_gex - put_gex, 4)
    total_gamma = js_to_fixed(call_gex + put_gex, 4)

    flip = gamma_flip(rows)
    source = "interpolated"
    if flip is None:
        flip = js_round(raw.underlying_price * C.GAMMA_FLIP_FALLBACK_COEFF)
        source = "fallback"

    regime: GammaRegime = "LongGamma" if net_gamma > 0 else "ShortGamma" if net_gamma < 0 else "Neutral"
    vol: VolatilityNote = (
        "VolSuppressing" if regime == "LongGamma" else "VolAmplifying" if regime == "ShortGamma" else "Neutral"
    )
    by_abs = sorted(rows, key=lambda r: abs(r[1]), reverse=True)[: C.GAMMA_MAGNET_COUNT]
    magnets = sorted(js_round(r[0]) for r in by_abs)
    return NormGamma(
        total_gamma=total_gamma,
        net_gamma=net_gamma,
        regime=regime,
        gamma_flip_level=flip,
        gamma_flip_source=source,
        gamma_magnets=magnets,
        volatility_note=vol,
    )


def normalize_flows(raw: EtfFlowsRaw, cot_bias: CotBias) -> NormFlows:
    threshold = C.FLOW_THRESHOLD_COEFF * raw.shares_outstanding
    net_flow = raw.inflow - raw.outflow
    bias: FlowBias = "FlowLong" if net_flow > threshold else "FlowShort" if net_flow < -threshold else "Mixed"
    crowded = (bias == "FlowLong" and cot_bias in ("StrongLong", "Long")) or (
        bias == "FlowShort" and cot_bias in ("StrongShort", "Short")
    )
    return NormFlows(
        net_flow=net_flow,
        flow_threshold=threshold,
        flow_bias=bias,
        crowding="Crowded" if crowded else "NotCrowded",
    )


def normalize_price(raw: PriceRaw) -> NormPrice:
    ma = raw.moving_averages
    trend: Trend
    if raw.close > ma.ma50 > ma.ma200:
        trend = "Up"
    elif raw.close < ma.ma50 < ma.ma200:
        trend = "Down"
    else:
        trend = "Neutral"
    return NormPrice(trend=trend, close=raw.close, ma20=ma.ma20, ma50=ma.ma50, ma200=ma.ma200)


def normalize(raw: RawBundle) -> Normalized:
    cot = normalize_cot(raw.cot_raw)
    return Normalized(
        cot=cot,
        gamma=normalize_gamma(raw.options_raw),
        flows=normalize_flows(raw.etf_flows_raw, cot.bias),
        price=normalize_price(raw.price_raw),
    )
