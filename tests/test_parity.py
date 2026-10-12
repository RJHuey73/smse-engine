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
        assert norm[block] == pytest.approx(exp[block]), block


@pytest.mark.parametrize("asset", ["ES", "NQ"])
def test_interpretation_matches_dryrun(asset: str, raw_json: dict[str, Any], golden: dict[str, Any]) -> None:
    smse = synthesize(asset, TS, normalize(bundle(raw_json[asset])))
    assert interpret(smse) == golden[asset]["interpretation"]
