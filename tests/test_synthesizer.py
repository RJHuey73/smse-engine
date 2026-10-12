from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from smse_engine.normalizer import normalize
from smse_engine.schema import SMSEv1
from smse_engine.synthesizer import classify_regime, synthesize

from .conftest import TS, bundle


@pytest.mark.parametrize(
    ("trend", "gamma", "primary"),
    [
        ("Up", "LongGamma", "StableUp"),
        ("Down", "ShortGamma", "StableDown"),
        ("Up", "ShortGamma", "VolatileUp"),
        ("Down", "LongGamma", "VolatileDown"),
        ("Neutral", "LongGamma", "Transition"),
        ("Up", "Neutral", "Transition"),
        ("Neutral", "Neutral", "Transition"),
    ],
)
def test_regime_matrix(trend: str, gamma: str, primary: str) -> None:
    assert classify_regime(trend, gamma) == primary  # type: ignore[arg-type]  # str literal from parametrize


def test_risk_note_vocab_maps_normal_to_uncrowded(es: dict[str, Any]) -> None:
    smse = synthesize("ES", TS, normalize(bundle(es)))
    assert smse.cot.risk_note == "Normal"
    assert smse.regime.risk_note == "Uncrowded"


def test_support_filters_levels_above_close(es: dict[str, Any]) -> None:
    es["price_raw"]["moving_averages"].update(ma50=6000, ma200=4000)  # ma50 above close
    smse = synthesize("ES", TS, normalize(bundle(es)))
    assert smse.key_levels.support == [4000]


def test_contract_is_closed(es: dict[str, Any]) -> None:
    d = synthesize("ES", TS, normalize(bundle(es))).model_dump()
    d["extra"] = 1
    with pytest.raises(ValidationError):
        SMSEv1.model_validate(d)


def test_timestamp_must_be_utc(es: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        synthesize("ES", "2026-04-30T21:00:00+02:00", normalize(bundle(es)))


def test_deterministic(es: dict[str, Any]) -> None:
    a = synthesize("ES", TS, normalize(bundle(es)))
    b = synthesize("ES", TS, normalize(bundle(es)))
    assert a == b
