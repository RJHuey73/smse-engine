"""SMSE-Reporter-Agent — SFX-MARKET-014 Daily Market Brief Template v1.

Zero heuristics: every line is a pure function of SMSE_v1 fields.

PROVISIONAL: the canonical module is reporterAgent.ts v1.1 (cited in MARKET-014), which
has not been recovered. Interpretation strings are verbatim from the T0-authorized dry run.
Section bodies other than the interpretation layer are field renderings only, with no prose,
until v1.1 is recovered and diffed (see docs/RECONCILIATION.md, R-01).
"""

from __future__ import annotations

from collections.abc import Sequence

from smse_engine.schema import DailyBrief, ProvenanceBinding, RegimePrimary, SMSEv1, SummaryRow

INTERPRETATION: dict[RegimePrimary, str] = {
    "StableUp": "Trend intact. Dips likely supported unless price breaks below gamma flip.",
    "StableDown": "Downtrend intact. Rallies likely sold unless flows turn positive.",
    "VolatileUp": "Upside path but unstable. Expect sharp swings around gamma flip.",
    "VolatileDown": "Downside path with amplified volatility. Squeeze risk if flows flip.",
    "Transition": "Regime shift forming. Watch gamma flip and flow direction for confirmation.",
}
CROWDED_LONG = " Crowded long — air-pocket risk if flows reverse."
CROWDED_SHORT = " Crowded short — high squeeze potential."
COT_STALE = " ⚠ COT stale (>7d) — directional bias unreliable."

SECTIONS = (
    "Market Regime Map",
    "Key Levels",
    "Volatility and Liquidity",
    "Positioning Pressure",
    "Shadowfox Interpretation Layer",
    "Summary Table",
)


def interpret(a: SMSEv1) -> str:
    text = INTERPRETATION[a.regime.primary]
    if a.regime.risk_note == "CrowdedLong":
        text += CROWDED_LONG
    if a.regime.risk_note == "CrowdedShort":
        text += CROWDED_SHORT
    if a.cot.stale:
        text += COT_STALE
    return text


def summary_row(a: SMSEv1) -> SummaryRow:
    return SummaryRow(
        asset=a.asset,
        regime=a.regime.primary,
        risk=a.regime.risk_note,
        gamma_flip_level=a.gamma.gamma_flip_level,
        volatility=a.gamma.volatility_note,
        cot_bias=a.cot.bias,
        flow_bias=a.flows.bias,
        cot_stale=a.cot.stale,
    )


def _fmt(values: Sequence[int]) -> str:
    return " · ".join(f"{v:,}" for v in values) if values else "—"


def _stale_mark(a: SMSEv1) -> str:
    return " ⚠ COT STALE" if a.cot.stale else ""


def render_text(date: str, assets: Sequence[SMSEv1], interps: dict[str, str]) -> str:
    out: list[str] = [f"SHADOWFOX DAILY MARKET BRIEF · {date} · SFX-MARKET-014", ""]
    blocks: dict[str, list[str]] = {
        "Market Regime Map": [
            f"{a.asset}: {a.regime.primary} | risk={a.regime.risk_note}{_stale_mark(a)}" for a in assets
        ],
        "Key Levels": [
            f"{a.asset}: support {_fmt(a.key_levels.support)} | resistance {_fmt(a.key_levels.resistance)}"
            f" | gamma magnets {_fmt(a.key_levels.gamma_magnets)} | gamma flip {a.gamma.gamma_flip_level:,}"
            for a in assets
        ],
        "Volatility and Liquidity": [
            f"{a.asset}: {a.gamma.regime} | {a.gamma.volatility_note} | flows {a.flows.bias}" for a in assets
        ],
        "Positioning Pressure": [
            f"{a.asset}: COT {a.cot.bias} (z={a.cot.z_score}) | extreme={a.cot.extreme_flag}"
            f" | crowding={a.flows.crowding}{_stale_mark(a)}"
            for a in assets
        ],
        "Shadowfox Interpretation Layer": [f"{a.asset}: {interps[a.asset]}" for a in assets],
    }
    header = "asset | regime | risk | gamma_flip_level | volatility | cot_bias | flow_bias | cot_stale"
    rows = [
        f"{r.asset} | {r.regime} | {r.risk} | {r.gamma_flip_level} | {r.volatility} | {r.cot_bias}"
        f" | {r.flow_bias} | {str(r.cot_stale).lower()}"
        for r in map(summary_row, assets)
    ]
    blocks["Summary Table"] = [header, *rows]
    for name in SECTIONS:
        out += [f"## {name}", *blocks[name], ""]
    return "\n".join(out).rstrip() + "\n"


def report(date: str, assets: Sequence[SMSEv1], provenance: ProvenanceBinding) -> DailyBrief:
    if not assets:
        raise ValueError("reporter requires at least one SMSE_v1 object")
    names = [a.asset for a in assets]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate assets in report input: {names}")
    ordered = sorted(assets, key=lambda a: a.asset)
    interps = {a.asset: interpret(a) for a in ordered}
    return DailyBrief(
        date=date,
        brief_text=render_text(date, ordered, interps),
        summary_table=[summary_row(a) for a in ordered],
        interpretations=interps,
        provenance=provenance,
    )
