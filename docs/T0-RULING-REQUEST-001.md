# T0 Ruling Request 001 — SMSE Engine v0 (R-02, R-04, R-05)

| Field | Value |
|---|---|
| Status | **STAGED. Awaiting T0.** Nothing below is in effect. |
| Requested by | T1 (Claude), 2026-10-11 |
| Scope | SFX-MARKET-012 (mapping rules) and SFX-MARKET-014 ("zero heuristics") |
| Registry state | Unverified. The Airtable Canon ID Registry returned 429. The version, next ID and CF status are **not asserted** here. |
| Evidence | Addendum v8.12.0 (Notion); `smse-pipeline-dryrun.jsx` (Drive `1Shn7KKXBKp744spwcGjR5eJ169xLFrSZ`); engine golden tests |
| TrustState / Provenance | T2-FLAGGED · source_tier `sfx-t2` · ratified `false` |

Engine v0 behavior until a ruling lands: **as ratified / dry-run parity, tagged provisional.**

---

## Ruling A — R-02: `flow_threshold` units

**Defect (observed).** `flow_threshold = 0.001 × shares_outstanding` produces a share count.
`net_flow = inflow − outflow` is in USD. On the dry-run fixture:

| Asset | net_flow (USD) | flow_threshold (shares) | Ratio |
|---|---|---|---|
| ES / SPY | +920,000,000 | 450,000 | ~2,044× |
| NQ / QQQ | −350,000,000 | 248,000 | ~1,411× |

The threshold almost never binds. In practice, `flows.bias` is `sign(net_flow)`.

| Option | Change | Contract impact | Parity |
|---|---|---|---|
| **A1 (recommended)** | `flow_threshold_usd = 0.001 × shares_outstanding × close` | None. `close` is already in `price_raw`. The 011 field keeps its name, and its value becomes USD. | Breaks the golden output and needs a re-baseline. |
| A2 | Keep as ratified. Record the units mismatch as a known limitation. | None | Kept |
| A3 | Feed flows in shares (`net_flow_shares = net_usd / close`) | Changes the 012 `etf_flows_raw` contract | Breaks |

Recommended path: ship A1 as a **config flag that defaults off**. The default flips to A1 only with this ruling plus an addendum. Under A1 the fixture result does not change: SPY's threshold becomes about $2.3M against a $920M flow, so the bias stays `FlowLong`.

- [ ] A1  - [ ] A2  - [ ] A3  - [ ] Other: ________

---

## Ruling B — R-04: gamma-flip fallback

**Conflict (observed).** When no strike interval changes sign, the dry run sets
`gamma_flip_level = round(underlying × 0.99)`. MARKET-014 requires "zero heuristics", and this value is not derived from options data.

| Option | Change | Contract impact |
|---|---|---|
| **B1 (recommended)** | No flip is reported: `gamma_flip_level = null`, plus `gamma_flip_source = "unavailable"`. The reporter prints "no flip in chain". | 011 v1.1 → v1.2: `gamma_flip_level` becomes nullable. **Canon amendment.** |
| B2 | Ratify the 0.99 fallback as a canon rule | 011 unchanged. 014's wording gains an exception. |
| B3 | Fall back to the nearest strike to the zero crossing of cumulative GEX | 011 unchanged, but this is a new rule |

- [ ] B1  - [ ] B2  - [ ] B3  - [ ] Other: ________

---

## Ruling C — R-05: key levels and magnet count

**Conflict (observed).** These rules come from the dry run, not the addendum:
- support = {MA50, MA200} below close
- resistance = close × {1.01, 1.025}
- the top 3 strikes by |net GEX| become gamma magnets

The resistance percentages are the clearest heuristic.

| Option | Change |
|---|---|
| **C1 (recommended)** | Ratify the support rule and the 3-magnet rule, which are both data-derived. Replace fixed-percentage resistance with the gamma magnets above close. |
| C2 | Ratify all of the dry-run formulas as they are |
| C3 | Remove `support` and `resistance` until a key-levels spec exists; keep magnets only |

- [ ] C1  - [ ] C2  - [ ] C3  - [ ] Other: ________

---

## Acknowledged without a ruling (record only)

- **R-07 / R-08:** engine-level hardening. Degenerate COT history fails closed, and the options chain is strike-sorted with duplicate strikes summed.
- **R-01, R-03, R-06, R-11:** queued for T1 triage → T0 gate after the registry quota resets.

## On ratification, T1 will

1. Ship the selected variants behind flags.
2. Re-baseline the golden output and add an oracle-delta test.
3. Draft the addendum (011 v1.2 if B1).
4. Write to the registry only on T0 auth.

**T0 signature:** ____________  **Date:** ________

={∆§/π}™
