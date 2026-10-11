from __future__ import annotations

from typing import Any

import pytest

from smse_engine._num import js_round, js_to_fixed
from smse_engine.normalizer import (
    NormalizationError,
    cot_band,
    normalize,
    normalize_flows,
    normalize_gamma,
    normalize_price,
)
from smse_engine.schema import EtfFlowsRaw, OptionsRaw, PriceRaw

from .conftest import bundle


@pytest.mark.parametrize(
    ("z", "band"),
    [
        (1.51, "StrongLong"),
        (1.5, "Long"),
        (0.51, "Long"),
        (0.5, "Neutral"),
        (0.0, "Neutral"),
        (-0.5, "Neutral"),
        (-0.51, "Short"),
        (-1.5, "Short"),
        (-1.51, "StrongShort"),
    ],
)
def test_cot_bands_strict_boundaries(z: float, band: str) -> None:
    assert cot_band(z) == band


def _force_z(es: dict[str, Any], net: int) -> None:
    es["cot_raw"]["historical_net"] = [-100, 100]  # mean 0, population std 100
    es["cot_raw"]["noncommercial_long"] = net if net > 0 else 0
    es["cot_raw"]["noncommercial_short"] = -net if net < 0 else 0


def test_extreme_long_sets_crowded(es: dict[str, Any]) -> None:
    _force_z(es, 200)
    cot = normalize(bundle(es)).cot
    got = (cot.z_score, cot.bias, cot.extreme_flag, cot.risk_note)
    assert got == (2.0, "StrongLong", "BullishExtreme", "CrowdedLong")


def test_extreme_short_sets_crowded(es: dict[str, Any]) -> None:
    _force_z(es, -200)
    cot = normalize(bundle(es)).cot
    assert (cot.bias, cot.extreme_flag, cot.risk_note) == ("StrongShort", "BearishExtreme", "CrowdedShort")


@pytest.mark.parametrize(("age", "stale"), [(7, False), (8, True)])
def test_stale_boundary(es: dict[str, Any], age: int, stale: bool) -> None:
    es["cot_raw"]["data_age_days"] = age
    assert normalize(bundle(es)).cot.stale is stale


def test_stale_fallback_neutralises_but_keeps_z(es: dict[str, Any]) -> None:
    _force_z(es, 200)
    es["cot_raw"]["data_age_days"] = 30
    cot = normalize(bundle(es)).cot
    assert (cot.bias, cot.extreme_flag, cot.risk_note, cot.stale) == ("Neutral", "None", "Normal", True)
    assert cot.z_score == 2.0  # z still reported, per dry run


def test_stale_fallback_blocks_flow_crowding(es: dict[str, Any]) -> None:
    _force_z(es, 200)
    es["cot_raw"]["data_age_days"] = 30
    assert normalize(bundle(es)).flows.crowding == "NotCrowded"


@pytest.mark.parametrize("hist", [[], [5], [3, 3, 3]])
def test_degenerate_history_fails_closed(es: dict[str, Any], hist: list[int]) -> None:
    es["cot_raw"]["historical_net"] = hist
    with pytest.raises(NormalizationError):
        normalize(bundle(es))


def _chain(*rows: tuple[float, float, float]) -> OptionsRaw:
    # (strike, call_gex, put_gex) with oi=1 so gamma == gex
    return OptionsRaw.model_validate(
        {
            "underlying_price": 100,
            "chain": [
                {"strike": k, "expiry": "x", "call_oi": 1, "put_oi": 1, "call_gamma": c, "put_gamma": p}
                for k, c, p in rows
            ],
        }
    )


def test_gamma_flip_interpolates() -> None:
    g = normalize_gamma(_chain((90, 0, 3), (110, 1, 0)))
    assert (g.gamma_flip_level, g.gamma_flip_source) == (105, "interpolated")


def test_gamma_flip_fallback_when_no_sign_change() -> None:
    g = normalize_gamma(_chain((90, 2, 1), (110, 3, 1)))
    assert (g.gamma_flip_level, g.gamma_flip_source) == (99, "fallback")


def test_gamma_chain_is_sorted_and_aggregated() -> None:
    unsorted = normalize_gamma(_chain((110, 1, 0), (90, 0, 3)))
    assert unsorted.gamma_flip_level == 105
    dup = normalize_gamma(_chain((90, 0, 1), (90, 0, 2), (110, 1, 0)))
    assert dup.gamma_flip_level == 105


@pytest.mark.parametrize(
    ("c", "p", "regime", "note"),
    [(2, 1, "LongGamma", "VolSuppressing"), (1, 2, "ShortGamma", "VolAmplifying"), (1, 1, "Neutral", "Neutral")],
)
def test_gamma_sign_logic(c: float, p: float, regime: str, note: str) -> None:
    g = normalize_gamma(_chain((100, c, p)))
    assert (g.regime, g.volatility_note) == (regime, note)


def test_gamma_magnets_top3_by_abs_then_ascending() -> None:
    g = normalize_gamma(_chain((90, 0, 9), (95, 1, 0), (100, 5, 0), (105, 7, 0), (110, 0, 2)))
    assert g.gamma_magnets == [90, 100, 105]


def _flows(net: float, so: float = 1_000_000) -> EtfFlowsRaw:
    return EtfFlowsRaw(ticker="T", date="d", inflow=max(net, 0), outflow=max(-net, 0), shares_outstanding=so)


@pytest.mark.parametrize(("net", "bias"), [(1001, "FlowLong"), (1000, "Mixed"), (-1000, "Mixed"), (-1001, "FlowShort")])
def test_flow_threshold(net: float, bias: str) -> None:
    f = normalize_flows(_flows(net), "Neutral")
    assert f.flow_threshold == 1000.0
    assert f.flow_bias == bias


@pytest.mark.parametrize(
    ("flow_net", "cot", "crowding"),
    [
        (5000, "Long", "Crowded"),
        (5000, "StrongLong", "Crowded"),
        (-5000, "Short", "Crowded"),
        (5000, "Short", "NotCrowded"),
        (0, "StrongLong", "NotCrowded"),
    ],
)
def test_crowding(flow_net: float, cot: str, crowding: str) -> None:
    assert normalize_flows(_flows(flow_net), cot).crowding == crowding  # type: ignore[arg-type]  # str literal from parametrize


def _price(close: float, ma50: float, ma200: float) -> PriceRaw:
    return PriceRaw.model_validate(
        {
            "close": close,
            "high": close,
            "low": close,
            "open": close,
            "volume": 0,
            "moving_averages": {"ma20": close, "ma50": ma50, "ma200": ma200},
        }
    )


@pytest.mark.parametrize(
    ("close", "ma50", "ma200", "trend"),
    [(110, 100, 90, "Up"), (80, 90, 100, "Down"), (110, 90, 100, "Neutral"), (100, 100, 90, "Neutral")],
)
def test_ma_cascade(close: float, ma50: float, ma200: float, trend: str) -> None:
    assert normalize_price(_price(close, ma50, ma200)).trend == trend


def test_js_rounding_parity() -> None:
    assert js_to_fixed(0.125, 2) == 0.13  # JS toFixed rounds exact ties up
    assert js_to_fixed(-0.125, 2) == -0.13
    assert js_round(2.5) == 3 and js_round(-2.5) == -2  # Math.round ties -> +inf
