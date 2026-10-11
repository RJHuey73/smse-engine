"""Typed contracts.

Three layers, per SFX-MARKET-012: raw inputs -> normalized intermediate -> SMSE_v1 output.
``SMSEv1`` is the ratified SFX-MARKET-011 contract and is closed (``extra="forbid"``).
Provenance rides in the ``SMSERecord`` envelope, never inside the contract.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Raw layer (SFX-MARKET-012) -------------------------------------------------


class CotRaw(_Strict):
    report_date: str
    market_code: str
    noncommercial_long: int = Field(ge=0)
    noncommercial_short: int = Field(ge=0)
    commercial_long: int = Field(ge=0)
    commercial_short: int = Field(ge=0)
    open_interest: int = Field(ge=0)
    historical_net: list[int]
    data_age_days: int = Field(ge=0)


class OptionStrike(_Strict):
    strike: float = Field(gt=0)
    expiry: str
    call_oi: int = Field(ge=0)
    put_oi: int = Field(ge=0)
    call_gamma: float = Field(ge=0)
    put_gamma: float = Field(ge=0)


class OptionsRaw(_Strict):
    underlying_price: float = Field(gt=0)
    chain: list[OptionStrike] = Field(min_length=1)


class EtfFlowsRaw(_Strict):
    ticker: str
    date: str
    inflow: float = Field(ge=0)
    outflow: float = Field(ge=0)
    shares_outstanding: float = Field(gt=0)


class MovingAverages(_Strict):
    ma20: float = Field(gt=0)
    ma50: float = Field(gt=0)
    ma200: float = Field(gt=0)


class PriceRaw(_Strict):
    close: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    open: float = Field(gt=0)
    volume: float = Field(ge=0)
    moving_averages: MovingAverages


class RawBundle(_Strict):
    cot_raw: CotRaw
    options_raw: OptionsRaw
    etf_flows_raw: EtfFlowsRaw
    price_raw: PriceRaw


# --- Enumerations ---------------------------------------------------------------

CotBias = Literal["StrongLong", "Long", "Neutral", "Short", "StrongShort"]
ExtremeFlag = Literal["BullishExtreme", "BearishExtreme", "None"]
CotRiskNote = Literal["CrowdedLong", "CrowdedShort", "Normal"]
GammaRegime = Literal["LongGamma", "ShortGamma", "Neutral"]
VolatilityNote = Literal["VolSuppressing", "VolAmplifying", "Neutral"]
FlowBias = Literal["FlowLong", "FlowShort", "Mixed"]
Crowding = Literal["Crowded", "NotCrowded"]
Trend = Literal["Up", "Down", "Neutral"]
RegimePrimary = Literal["StableUp", "StableDown", "VolatileUp", "VolatileDown", "Transition"]
RegimeRiskNote = Literal["CrowdedLong", "CrowdedShort", "Uncrowded"]
GammaFlipSource = Literal["interpolated", "fallback"]


# --- Normalized intermediate (SFX-MARKET-012) -------------------------------------


class NormCot(_Strict):
    net: int
    z_score: float
    bias: CotBias
    extreme_flag: ExtremeFlag
    risk_note: CotRiskNote
    stale: bool


class NormGamma(_Strict):
    total_gamma: float
    net_gamma: float
    regime: GammaRegime
    gamma_flip_level: int
    gamma_flip_source: GammaFlipSource
    gamma_magnets: list[int]
    volatility_note: VolatilityNote


class NormFlows(_Strict):
    net_flow: float
    flow_threshold: float
    flow_bias: FlowBias
    crowding: Crowding


class NormPrice(_Strict):
    trend: Trend
    close: float
    ma20: float
    ma50: float
    ma200: float


class Normalized(_Strict):
    cot: NormCot
    gamma: NormGamma
    flows: NormFlows
    price: NormPrice


# --- SMSE_v1 output contract (SFX-MARKET-011 v1.1) --------------------------------


class SmseCot(_Strict):
    bias: CotBias
    z_score: float
    extreme_flag: ExtremeFlag
    risk_note: CotRiskNote
    stale: bool


class SmseGamma(_Strict):
    regime: GammaRegime
    gamma_flip_level: int
    volatility_note: VolatilityNote
    gamma_magnets: list[int]


class SmseFlows(_Strict):
    bias: FlowBias
    crowding: Crowding
    flow_threshold: float


class SmseRegime(_Strict):
    primary: RegimePrimary
    risk_note: RegimeRiskNote


class SmseKeyLevels(_Strict):
    support: list[int]
    resistance: list[int]
    gamma_magnets: list[int]


class SMSEv1(_Strict):
    """Single asset + timestamp scope."""

    asset: str = Field(min_length=1)
    timestamp: str
    cot: SmseCot
    gamma: SmseGamma
    flows: SmseFlows
    regime: SmseRegime
    key_levels: SmseKeyLevels

    @field_validator("timestamp")
    @classmethod
    def _utc_iso(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("timestamp must be ISO-8601 UTC with a trailing 'Z'")
        return v


# --- Governance envelope ---------------------------------------------------------


class ProvenanceBinding(_Strict):
    canon_refs: tuple[str, ...]
    engine_version: str
    schema_version: str
    input_sha256: str
    source_tier: Literal["sfx-t2"] = "sfx-t2"
    ratified: Literal[False] = False


class SMSERecord(_Strict):
    smse: SMSEv1
    provenance: ProvenanceBinding
    trust_state: Literal["T2-FLAGGED"] = "T2-FLAGGED"


# --- Reporter output (SFX-MARKET-014) --------------------------------------------


class SummaryRow(_Strict):
    asset: str
    regime: RegimePrimary
    risk: RegimeRiskNote
    gamma_flip_level: int
    volatility: VolatilityNote
    cot_bias: CotBias
    flow_bias: FlowBias
    cot_stale: bool


class DailyBrief(_Strict):
    date: str
    brief_text: str
    summary_table: list[SummaryRow]
    interpretations: dict[str, str]
    provenance: ProvenanceBinding
    trust_state: Literal["T2-FLAGGED"] = "T2-FLAGGED"
