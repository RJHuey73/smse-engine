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
pytest -q                     # 65 tests: rules, contract closure, registry, reporter, JS parity
ruff check . && mypy src tests
smse-engine fixtures/dryrun_2026-04-30.raw.json --timestamp 2026-04-30T21:00:00Z --date 2026-04-30 --text
```

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
