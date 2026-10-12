"""SFX-MARKET-013 DAG, v0 subset: Normalizer -> Synthesizer -> Registry -> Reporter.

Fetchers are replaced by caller-supplied ``RawBundle``s. The Scheduler and AUTO-001A
wiring stay out (gated by WO-AUTO-001A-MARKET). Per-asset branches are independent.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from smse_engine import constants as C
from smse_engine.flags import DEFAULT_FLAGS, EngineFlags
from smse_engine.normalizer import EtfPriceError, NormalizationError, normalize
from smse_engine.registry import InMemoryRegistry, RegistrySink
from smse_engine.reporter import report
from smse_engine.schema import DailyBrief, Normalized, ProvenanceBinding, RawBundle, SMSERecord
from smse_engine.synthesizer import synthesize


@dataclass(frozen=True)
class TraceEvent:
    asset: str
    stage: str
    detail: str


@dataclass(frozen=True)
class PipelineResult:
    records: list[SMSERecord]
    normalized: dict[str, Normalized]
    brief: DailyBrief
    trace: list[TraceEvent] = field(default_factory=list)
    excluded: dict[str, str] = field(default_factory=dict)  # asset -> reason (A1 fail-closed)


def _digest(payload: object) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _provenance(digest: str, flags: EngineFlags) -> ProvenanceBinding:
    return ProvenanceBinding(
        canon_refs=C.CANON_REFS,
        engine_version=C.ENGINE_VERSION,
        schema_version=C.SCHEMA_VERSION,
        input_sha256=digest,
        flags=flags.active(),
    )


def _raw_json(raw: RawBundle) -> object:
    # exclude_none keeps the digest of pre-A1 inputs unchanged now that etf_close/etf_close_date exist.
    return raw.model_dump(mode="json", exclude_none=True)


def run_pipeline(
    raw_by_asset: Mapping[str, RawBundle],
    timestamp: str,
    date: str,
    registry: RegistrySink | None = None,
    flags: EngineFlags = DEFAULT_FLAGS,
) -> PipelineResult:
    if not raw_by_asset:
        raise ValueError("no assets supplied")
    sink = registry if registry is not None else InMemoryRegistry()
    trace: list[TraceEvent] = []
    records: list[SMSERecord] = []
    normalized: dict[str, Normalized] = {}
    excluded: dict[str, str] = {}

    for asset in sorted(raw_by_asset):
        raw = raw_by_asset[asset]
        try:
            norm = normalize(raw, flags)
        except EtfPriceError as exc:
            # A1 fails closed per asset: drop it from the run, keep the reason. Other
            # NormalizationErrors (e.g. R-07) still abort the run, exactly as before.
            excluded[asset] = str(exc)
            trace.append(TraceEvent(asset, "Normalizer", f"excluded: {exc}"))
            continue
        normalized[asset] = norm
        detail = f"z={norm.cot.z_score} | γ={norm.gamma.regime} | flow={norm.flows.flow_bias}"
        trace.append(TraceEvent(asset, "Normalizer", detail))
        smse = synthesize(asset, timestamp, norm, flags)
        trace.append(TraceEvent(asset, "Synthesizer", f"regime={smse.regime.primary}"))
        record = SMSERecord(smse=smse, provenance=_provenance(_digest(_raw_json(raw)), flags))
        stored = sink.put(record)
        trace.append(TraceEvent(asset, "Registry", "stored" if stored else "replay (identical)"))
        records.append(record)

    if not records:
        raise NormalizationError(f"all assets excluded: {excluded}")
    batch_digest = _digest({a: _raw_json(raw_by_asset[a]) for a in sorted(raw_by_asset)})
    brief = report(date, [r.smse for r in records], _provenance(batch_digest, flags))
    stale = sum(r.smse.cot.stale for r in records)
    trace.append(TraceEvent("ALL", "Reporter", f"brief generated · {len(records)} assets · {stale} stale COT"))
    return PipelineResult(records=records, normalized=normalized, brief=brief, trace=trace, excluded=excluded)
