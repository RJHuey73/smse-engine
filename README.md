# smse-engine

The deterministic core of the Shadowfox SMSE Engine, implementing **SFX-MARKET-011–014**.
It turns raw COT, options, ETF-flow and price inputs into `SMSE_v1` objects and a Daily
Market Brief. No network calls, no model calls, no durable writes.

```
RawBundle ─► normalize (012) ─► synthesize (011 contract) ─► registry ─► report (014)
```

| Module | Canon | Role |
|---|---|---|
| `schema.py` | 011, 012, 014 | Raw → normalized → `SMSEv1` (closed) → `DailyBrief`. Provenance lives in the `SMSERecord` envelope. |
| `constants.py` | 012 | Ratified constants. Editing any of them is a Canon change. |
| `normalizer.py` | 012 | COT z-bands and stale fallback, gamma sign/flip/magnets, `flow_threshold`, MA cascade. |
| `synthesizer.py` | 011, 013 | Regime matrix and key levels. |
| `registry.py` | 013 | In-memory, idempotent, keyed `(asset, timestamp)`. `RegistrySink` is the seam for a durable backend. |
| `reporter.py` | 014 | Six-section brief plus `SummaryRow[]`. **Provisional** until reporterAgent.ts v1.1 is recovered. |
| `pipeline.py` | 013 | The 4-stage v0 subset of the DAG. |

**Out of scope for v0:** the four fetchers, the Scheduler-Agent, AUTO-001A/Make.com wiring
(WO-AUTO-001A-MARKET is gated), the Supabase sink, and SFX-MARKET-015 Active Discovery.

## Use

```bash
pip install -e ".[dev]"
pytest -q                     # 112 tests: rules, contract closure, registry, reporter, JS parity, flagged variants
ruff check . && mypy src tests
smse-engine fixtures/dryrun_2026-04-30.raw.json --timestamp 2026-04-30T21:00:00Z --date 2026-04-30 --text
```

## Flagged variants (T0 IMPLEMENT-approved 2026-10-12, not Canon)

Each one is off by default. With all three off, output is byte-identical to dry-run parity; the brief text and input digest are pinned in tests.

| Flag | CLI | Ruling | Effect |
|---|---|---|---|
| `flow_threshold_usd` | `--flow-threshold-usd` | R-02 / A1 | Threshold = `0.001 × shares_outstanding × etf_close`. It needs `etf_flows_raw.etf_close` and a same-session `etf_close_date`. If either is missing, invalid or stale, that asset fails closed and is excluded with the reason in the trace. |
| `null_gamma_flip` | `--null-gamma-flip` | R-04 / B1 | No sign change in the chain → `gamma_flip_level = null`, rendered "no flip in chain". |
| `magnet_key_levels` | `--magnet-key-levels` | R-05 / C1 | Zero-GEX strikes are not magnets. Resistance = magnets strictly above close. Duplicate MA support levels collapse. |

Active flags are stamped into every `ProvenanceBinding.flags`. Flipping a default needs a RATIFY ruling, an addendum and a verified registry (see `docs/T0-RULING-REQUEST-001.md` §0).

## Parity

`tests/oracle/dryrun_oracle.mjs` is the Normalizer, Synthesizer and interpretation logic,
transcribed verbatim from the T0-authorized `smse-pipeline-dryrun.jsx` (Drive
`1Shn7KKXBKp744spwcGjR5eJ169xLFrSZ`). `tests/golden/` holds its output. Regenerate it with:

```bash
node tests/oracle/dryrun_oracle.mjs fixtures/dryrun_2026-04-30.raw.json > tests/golden/dryrun_2026-04-30.golden.json
```

## Governance

Every output carries `ProvenanceBinding{source_tier: "sfx-t2", ratified: false}` and
`trust_state: "T2-FLAGGED"`. `ratified: true` cannot be constructed. Open conflicts are in
[`docs/RECONCILIATION.md`](docs/RECONCILIATION.md).

={∆§/π}™
