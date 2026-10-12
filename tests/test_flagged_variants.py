"""T0 IMPLEMENT-approved flagged variants (Ruling Request 001 rev 2): A1, B1, C1.

Each section mirrors the "Tests required for IMPLEMENT" list in docs/T0-RULING-REQUEST-001.md.
"""

from __future__ import annotations

import copy
import hashlib
import math
from typing import Any

import pytest
from pydantic import ValidationError

from smse_engine.flags import EngineFlags
from smse_engine.normalizer import (
    EtfPriceError,
    NormalizationError,
    normalize,
    normalize_flows,
    normalize_gamma,
)
from smse_engine.pipeline import run_pipeline
from smse_engine.reporter import NO_FLIP, interpret, report
from smse_engine.schema import EtfFlowsRaw, OptionsRaw, ProvenanceBinding, RawBundle, SMSEv1
from smse_engine.synthesizer import synthesize

from .conftest import TS, bundle

A1 = EngineFlags(flow_threshold_usd=True)
B1 = EngineFlags(null_gamma_flip=True)
C1 = EngineFlags(magnet_key_levels=True)
ALL = EngineFlags(flow_threshold_usd=True, null_gamma_flip=True, magnet_key_levels=True)
DATE = "2026-04-30"

# Illustrative ETF closes from the ruling request (hypothetical, not market data).
ETF_CLOSE = {"ES": 511.0, "NQ": 435.0}


def _with_etf_close(raw_json: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(raw_json)
    for asset, close in ETF_CLOSE.items():
        out[asset]["etf_flows_raw"].update(etf_close=close, etf_close_date=DATE)
    return out


def _raw(raw_json: dict[str, Any]) -> dict[str, RawBundle]:
    return {k: bundle(v) for k, v in raw_json.items()}


# --- Flag-off invariance (all three rulings, test "flag-off bit-identical") --------


FLAG_OFF_INPUT_SHA = "66f30bcb186609d01fd06f431fc4ff5b50c8de71ef2303b060a97b7d365fde1d"
FLAG_OFF_BRIEF_SHA = "e82656425dc3e516ed3fe9847e516c7c022446bafd1cd5fd0be26eed69444e9f"


def test_flag_off_brief_and_digest_pinned(raw_json: dict[str, Any]) -> None:
    res = run_pipeline(_raw(raw_json), TS, DATE)
    assert res.brief.provenance.input_sha256 == FLAG_OFF_INPUT_SHA
    assert hashlib.sha256(res.brief.brief_text.encode()).hexdigest() == FLAG_OFF_BRIEF_SHA
    assert res.brief.provenance.flags == ()


def test_flag_off_ignores_etf_close_fields(raw_json: dict[str, Any], golden: dict[str, Any]) -> None:
    raw = _with_etf_close(raw_json)
    raw["ES"]["etf_flows_raw"].update(etf_close=-1.0, etf_close_date="1999-01-01")  # garbage is ignored
    for asset in ("ES", "NQ"):
        smse = synthesize(asset, TS, normalize(bundle(raw[asset])))
        assert smse.model_dump(mode="json") == golden[asset]["smse"]


def test_provenance_records_active_flags(raw_json: dict[str, Any]) -> None:
    res = run_pipeline(_raw(_with_etf_close(raw_json)), TS, DATE, flags=ALL)
    expected = ("flow_threshold_usd", "null_gamma_flip", "magnet_key_levels")
    assert res.brief.provenance.flags == expected
    assert all(r.provenance.flags == expected and r.provenance.ratified is False for r in res.records)


# --- A1: USD flow threshold ------------------------------------------------------


def _flows(net: float, *, close: float | None = 10.0, close_date: str | None = DATE) -> EtfFlowsRaw:
    return EtfFlowsRaw(
        ticker="T",
        date=f"{DATE}T00:00:00Z",
        inflow=max(net, 0),
        outflow=max(-net, 0),
        shares_outstanding=1_000_000,
        etf_close=close,
        etf_close_date=close_date,
    )


@pytest.mark.parametrize(
    ("net", "bias"),
    [(10_001, "FlowLong"), (10_000, "Mixed"), (9_999, "Mixed"), (-10_000, "Mixed"), (-10_001, "FlowShort")],
)
def test_a1_threshold_boundary(net: float, bias: str) -> None:
    f = normalize_flows(_flows(net), "Neutral", A1)
    assert (f.flow_threshold, f.flow_threshold_basis, f.flow_bias) == (10_000.0, "usd", bias)


def test_a1_fixture_thresholds_and_biases_unchanged(raw_json: dict[str, Any]) -> None:
    raw = _with_etf_close(raw_json)
    es = normalize(bundle(raw["ES"]), A1).flows
    nq = normalize(bundle(raw["NQ"]), A1).flows
    assert es.flow_threshold == pytest.approx(229_950_000.0)
    assert nq.flow_threshold == pytest.approx(107_880_000.0)
    assert (es.flow_bias, nq.flow_bias) == ("FlowLong", "FlowShort")
    assert nq.crowding == "Crowded"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"close": None},
        {"close": 0.0},
        {"close": -5.0},
        {"close": math.nan},
        {"close": math.inf},
        {"close_date": None},
        {"close_date": "2026-04-29"},
        {"close_date": "not-a-date"},
    ],
    ids=["absent", "zero", "negative", "nan", "inf", "date-absent", "date-stale", "date-garbage"],
)
def test_a1_fails_closed(kwargs: dict[str, Any]) -> None:
    with pytest.raises(EtfPriceError):
        normalize_flows(_flows(5_000, **kwargs), "Neutral", A1)


def test_a1_same_session_accepts_iso_datetime_close_date() -> None:
    f = normalize_flows(_flows(5_000, close_date=f"{DATE}T20:00:00Z"), "Neutral", A1)
    assert f.flow_threshold_basis == "usd"


def test_a1_never_reads_price_raw_close(raw_json: dict[str, Any]) -> None:
    raw = _with_etf_close(raw_json)
    base = normalize(bundle(raw["ES"]), A1).flows.flow_threshold
    raw["ES"]["price_raw"]["close"] = 1.0
    assert normalize(bundle(raw["ES"]), A1).flows.flow_threshold == base


def test_a1_pipeline_excludes_asset_and_traces_reason(raw_json: dict[str, Any]) -> None:
    raw = _with_etf_close(raw_json)
    raw["NQ"]["etf_flows_raw"]["etf_close_date"] = "2026-04-29"
    res = run_pipeline(_raw(raw), TS, DATE, flags=A1)
    assert [r.smse.asset for r in res.records] == ["ES"]
    assert "stale etf_close" in res.excluded["NQ"]
    assert any(t.asset == "NQ" and t.detail.startswith("excluded:") for t in res.trace)
    assert "NQ" not in res.brief.interpretations


def test_a1_all_assets_excluded_raises(raw_json: dict[str, Any]) -> None:
    with pytest.raises(NormalizationError, match="all assets excluded"):
        run_pipeline(_raw(raw_json), TS, DATE, flags=A1)  # fixture carries no etf_close


def test_a1_does_not_widen_r07_handling(raw_json: dict[str, Any]) -> None:
    raw = _with_etf_close(raw_json)
    raw["ES"]["cot_raw"]["historical_net"] = [1, 1, 1]
    with pytest.raises(NormalizationError) as exc:
        run_pipeline(_raw(raw), TS, DATE, flags=A1)
    assert not isinstance(exc.value, EtfPriceError)


# --- B1: null gamma flip -----------------------------------------------------------


def _chain(*rows: tuple[float, float, float]) -> OptionsRaw:
    return OptionsRaw.model_validate(
        {
            "underlying_price": 100,
            "chain": [
                {"strike": k, "expiry": "x", "call_oi": 1, "put_oi": 1, "call_gamma": c, "put_gamma": p}
                for k, c, p in rows
            ],
        }
    )


@pytest.mark.parametrize(
    "rows",
    [
        ((90, 2, 1), (110, 3, 1)),  # all positive
        ((90, 1, 2), (110, 1, 3)),  # all negative
        ((100, 2, 1),),  # single strike
        ((90, 1, 1), (110, 2, 2)),  # all exactly zero
    ],
    ids=["all-positive", "all-negative", "single-strike", "all-zero"],
)
def test_b1_no_crossing_is_null(rows: tuple[tuple[float, float, float], ...]) -> None:
    g = normalize_gamma(_chain(*rows), B1)
    assert (g.gamma_flip_level, g.gamma_flip_source) == (None, "unavailable")


def test_b1_off_keeps_fallback() -> None:
    g = normalize_gamma(_chain((90, 2, 1), (110, 3, 1)))
    assert (g.gamma_flip_level, g.gamma_flip_source) == (99, "fallback")


@pytest.mark.parametrize("zero_first", [True, False])
def test_b1_zero_net_strike_is_the_flip(zero_first: bool) -> None:
    rows = ((90, 1, 1), (110, 3, 1)) if zero_first else ((90, 1, 1), (110, 1, 3))
    assert normalize_gamma(_chain(*rows), B1).gamma_flip_level == 90


def test_b1_first_crossing_wins() -> None:
    g = normalize_gamma(_chain((90, 0, 1), (100, 1, 0), (110, 0, 1), (120, 1, 0)), B1)
    assert (g.gamma_flip_level, g.gamma_flip_source) == (95, "interpolated")


def _null_flip_smse(es: dict[str, Any], **regime: str) -> SMSEv1:
    es["options_raw"]["chain"] = [
        {"strike": 5000, "expiry": "x", "call_oi": 10, "put_oi": 1, "call_gamma": 0.01, "put_gamma": 0.01}
    ]
    smse = synthesize("ES", TS, normalize(bundle(es), B1), B1)
    if regime:
        smse = smse.model_copy(update={"regime": smse.regime.model_copy(update=regime)})
    return smse


def test_b1_reporter_renders_null_flip(es: dict[str, Any]) -> None:
    smse = _null_flip_smse(es)
    assert smse.gamma.gamma_flip_level is None
    prov = ProvenanceBinding(canon_refs=(), engine_version="t", schema_version="t", input_sha256="0", flags=B1.active())
    brief = report(DATE, [smse], prov)
    assert "gamma flip — (no flip in chain)" in brief.brief_text
    table = brief.brief_text.split("## Summary Table")[1]
    assert "ES | StableUp | Uncrowded | — |" in table
    assert brief.summary_table[0].gamma_flip_level is None


def test_b1_suffix_order_regime_then_noflip_then_crowding_then_stale(es: dict[str, Any]) -> None:
    es["cot_raw"]["data_age_days"] = 9
    smse = _null_flip_smse(es, risk_note="CrowdedLong")
    text = interpret(smse)
    i_noflip, i_crowd, i_stale = text.index(NO_FLIP.strip()), text.index("Crowded long"), text.index("COT stale")
    assert text.startswith("Trend intact.")
    assert i_noflip < i_crowd < i_stale


@pytest.mark.parametrize("bad", [5015.5, "x"])
def test_b1_contract_rejects_non_integer_non_null_flip(golden: dict[str, Any], bad: object) -> None:
    d = copy.deepcopy(golden["ES"]["smse"])
    d["gamma"]["gamma_flip_level"] = bad
    with pytest.raises(ValidationError):
        SMSEv1.model_validate(d)


# --- C1: magnet-derived key levels -------------------------------------------------


@pytest.mark.parametrize(
    ("rows", "magnets"),
    [
        (((100, 1, 1), (110, 2, 2)), []),  # zero non-zero strikes
        (((100, 1, 1), (110, 3, 1)), [110]),  # one
        (((100, 1, 1), (110, 3, 1), (120, 1, 4)), [110, 120]),  # two
        (((100, 2, 1), (110, 3, 1), (120, 1, 5)), [100, 110, 120]),  # three
        (((100, 2, 1), (110, 5, 1), (120, 1, 9), (130, 7, 1)), [110, 120, 130]),  # four
    ],
    ids=["zero", "one", "two", "three", "four"],
)
def test_c1_magnet_count(rows: tuple[tuple[float, float, float], ...], magnets: list[int]) -> None:
    assert normalize_gamma(_chain(*rows), C1).gamma_magnets == magnets


def test_c1_off_keeps_zero_gex_magnets() -> None:
    assert normalize_gamma(_chain((100, 1, 1), (110, 3, 1))).gamma_magnets == [100, 110]


def test_c1_tie_keeps_lower_strike() -> None:
    g = normalize_gamma(_chain((100, 3, 1), (110, 1, 3), (120, 3, 1), (130, 3, 1)), C1)
    assert g.gamma_magnets == [100, 110, 120]  # four-way |2| tie: the highest strike drops


def _c1(es: dict[str, Any], magnets_at: list[float], close: float, ma50: float, ma200: float) -> SMSEv1:
    es["options_raw"]["chain"] = [
        {"strike": k, "expiry": "x", "call_oi": 1, "put_oi": 0, "call_gamma": 1.0, "put_gamma": 0.0} for k in magnets_at
    ]
    es["price_raw"].update(close=close)
    es["price_raw"]["moving_averages"].update(ma50=ma50, ma200=ma200)
    return synthesize("ES", TS, normalize(bundle(es), C1), C1)


def test_c1_no_magnet_above_close_gives_empty_resistance(es: dict[str, Any]) -> None:
    s = _c1(es, [90, 95], close=100, ma50=95, ma200=90)
    assert s.key_levels.resistance == []


def test_c1_magnet_at_close_is_in_neither_list(es: dict[str, Any]) -> None:
    s = _c1(es, [100, 110], close=100, ma50=95, ma200=90)
    assert s.key_levels.resistance == [110]
    assert 100 not in s.key_levels.support
    assert 100 in s.key_levels.gamma_magnets


def test_c1_equal_mas_collapse(es: dict[str, Any]) -> None:
    assert _c1(es, [110], close=100, ma50=95, ma200=95).key_levels.support == [95]


def test_c1_ma_equal_to_magnet_kept_in_both(es: dict[str, Any]) -> None:
    s = _c1(es, [95, 110], close=100, ma50=95, ma200=90)
    assert 95 in s.key_levels.support and 95 in s.key_levels.gamma_magnets
    assert s.key_levels.resistance == [110]


def test_c1_support_and_resistance_disjoint(es: dict[str, Any]) -> None:
    s = _c1(es, [90, 100, 105, 110], close=100, ma50=105, ma200=95)
    assert all(v < 100 for v in s.key_levels.support)
    assert all(v > 100 for v in s.key_levels.resistance)


def test_c1_fixture_deltas(raw_json: dict[str, Any], golden: dict[str, Any]) -> None:
    expected_resistance = {"ES": [5150, 5200], "NQ": [18000, 18250]}
    for asset, resistance in expected_resistance.items():
        s = synthesize(asset, TS, normalize(bundle(raw_json[asset]), C1), C1)
        g = golden[asset]["smse"]
        assert s.key_levels.resistance == resistance
        assert s.key_levels.support == g["key_levels"]["support"]
        assert s.gamma.gamma_magnets == g["gamma"]["gamma_magnets"]
