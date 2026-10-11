from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from smse_engine.schema import RawBundle

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "fixtures" / "dryrun_2026-04-30.raw.json"
GOLDEN_PATH = ROOT / "tests" / "golden" / "dryrun_2026-04-30.golden.json"
TS = "2026-04-30T21:00:00Z"


@pytest.fixture
def raw_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(RAW_PATH.read_text())
    return data


@pytest.fixture
def golden() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLDEN_PATH.read_text())
    return data


@pytest.fixture
def es(raw_json: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(raw_json["ES"])


def bundle(d: dict[str, Any]) -> RawBundle:
    return RawBundle.model_validate(d)
