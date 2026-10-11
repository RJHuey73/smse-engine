from __future__ import annotations

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from smse_engine.pipeline import run_pipeline
from smse_engine.registry import InMemoryRegistry, RegistryConflictError
from smse_engine.reporter import SECTIONS
from smse_engine.schema import ProvenanceBinding

from .conftest import TS, bundle


def _raw(raw_json: dict[str, Any]) -> dict[str, Any]:
    return {k: bundle(v) for k, v in raw_json.items()}


def test_brief_has_all_sections_in_order(raw_json: dict[str, Any]) -> None:
    text = run_pipeline(_raw(raw_json), TS, "2026-04-30").brief.brief_text
    idx = [text.index(f"## {s}") for s in SECTIONS]
    assert idx == sorted(idx)


def test_summary_table_agent_readable(raw_json: dict[str, Any]) -> None:
    rows = run_pipeline(_raw(raw_json), TS, "2026-04-30").brief.summary_table
    assert [(r.asset, r.regime, r.flow_bias) for r in rows] == [
        ("ES", "StableUp", "FlowLong"),
        ("NQ", "VolatileDown", "FlowShort"),
    ]


def test_brief_is_byte_deterministic_and_order_independent(raw_json: dict[str, Any]) -> None:
    a = run_pipeline(_raw(raw_json), TS, "2026-04-30").brief
    rev = dict(reversed(list(_raw(raw_json).items())))
    b = run_pipeline(rev, TS, "2026-04-30").brief
    assert a == b


def test_stale_surfaces_in_regime_map_and_interpretation(raw_json: dict[str, Any]) -> None:
    raw = copy.deepcopy(raw_json)
    raw["ES"]["cot_raw"]["data_age_days"] = 9
    res = run_pipeline(_raw(raw), TS, "2026-04-30")
    text = res.brief.brief_text
    regime_map = text.split("## Market Regime Map")[1].split("##")[0]
    assert "ES: StableUp | risk=Uncrowded ⚠ COT STALE" in regime_map
    assert res.brief.interpretations["ES"].endswith("⚠ COT stale (>7d) — directional bias unreliable.")
    assert res.trace[-1].detail.endswith("1 stale COT")


def test_provenance_is_unratified_t2(raw_json: dict[str, Any]) -> None:
    res = run_pipeline(_raw(raw_json), TS, "2026-04-30")
    for p in [r.provenance for r in res.records] + [res.brief.provenance]:
        assert (p.source_tier, p.ratified) == ("sfx-t2", False)
        assert len(p.input_sha256) == 64
    assert res.brief.trust_state == "T2-FLAGGED"


def test_provenance_cannot_claim_ratified() -> None:
    with pytest.raises(ValidationError):
        ProvenanceBinding(canon_refs=(), engine_version="x", schema_version="y", input_sha256="0", ratified=True)


def test_registry_idempotent_replay_and_conflict(raw_json: dict[str, Any]) -> None:
    reg = InMemoryRegistry()
    run_pipeline(_raw(raw_json), TS, "2026-04-30", registry=reg)
    res = run_pipeline(_raw(raw_json), TS, "2026-04-30", registry=reg)
    assert len(reg) == 2
    assert {t.detail for t in res.trace if t.stage == "Registry"} == {"replay (identical)"}
    changed = copy.deepcopy(raw_json)
    changed["ES"]["price_raw"]["close"] = 4000
    with pytest.raises(RegistryConflictError):
        run_pipeline(_raw(changed), TS, "2026-04-30", registry=reg)


def test_empty_input_rejected() -> None:
    with pytest.raises(ValueError):
        run_pipeline({}, TS, "2026-04-30")
