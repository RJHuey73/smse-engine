"""Golden parity with the T0-authorized JS dry run (tests/oracle/dryrun_oracle.mjs)."""

from __future__ import annotations

from typing import Any

import pytest

from smse_engine.normalizer import normalize
from smse_engine.reporter import interpret
from smse_engine.synthesizer import synthesize

from .conftest import TS, bundle


@pytest.mark.parametrize("asset", ["ES", "NQ"])
def test_smse_matches_dryrun(asset: str, raw_json: dict[str, Any], golden: dict[str, Any]) -> None:
    smse = synthesize(asset, TS, normalize(bundle(raw_json[asset])))
    assert smse.model_dump(mode="json") == golden[asset]["smse"]


@pytest.mark.parametrize("asset", ["ES", "NQ"])
def test_normalized_matches_dryrun(asset: str, raw_json: dict[str, Any], golden: dict[str, Any]) -> None:
    norm = normalize(bundle(raw_json[asset])).model_dump(mode="json")
    norm["gamma"].pop("gamma_flip_source")  # engine-only fields, not in the dry run
    norm["flows"].pop("flow_threshold_basis")
    exp = golden[asset]["norm"]
    for block in ("cot", "gamma", "flows", "price"):
        _assert_approx(norm[block], exp[block], block)


def _assert_approx(actual: Any, expected: Any, path: str) -> None:
    """Same keys and lengths, numbers within pytest.approx, everything else equal.

    pytest 9 refuses pytest.approx() on a dict that holds lists (gamma_magnets),
    so walk the structure and apply approx() to each leaf instead.
    """
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert actual.keys() == expected.keys(), path
        for key, value in expected.items():
            _assert_approx(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            _assert_approx(a, e, f"{path}[{i}]")
    else:
        assert actual == pytest.approx(expected), path


@pytest.mark.parametrize("asset", ["ES", "NQ"])
def test_interpretation_matches_dryrun(asset: str, raw_json: dict[str, Any], golden: dict[str, Any]) -> None:
    smse = synthesize(asset, TS, normalize(bundle(raw_json[asset])))
    assert interpret(smse) == golden[asset]["interpretation"]
