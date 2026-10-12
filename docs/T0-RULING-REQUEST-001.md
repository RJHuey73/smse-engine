# T0 Ruling Request 001 (rev 2) — SMSE Engine v0 (R-02, R-04, R-05)

| Field | Value |
|---|---|
| Status | **STAGED. Awaiting T0.** Nothing below is in effect. |
| Requested by | T1 (Claude). Rev 1 on 2026-10-11; rev 2 on 2026-10-12, after the T0 review of rev 1. |
| Scope | SFX-MARKET-011 (output contract), 012 (mapping rules), 014 ("zero heuristics") |
| Registry state | **Unverified.** The Airtable Canon ID Registry returned 429. The version, next ID and CF status are not asserted here. |
| Evidence | Addendum v8.12.0 (Notion); `smse-pipeline-dryrun.jsx` (Drive `1Shn7KKXBKp744spwcGjR5eJ169xLFrSZ`); the engine's golden tests |
| TrustState / Provenance | T2-FLAGGED · source_tier `sfx-t2` · ratified `false` |

Engine v0 behavior until a ruling lands: **as ratified / dry-run parity, tagged provisional.**

## 0. What a signature on this document means

Each ruling has **two separate approval boxes**. They grant different things.

| Box | Grants | Does not grant |
|---|---|---|
| **IMPLEMENT (flagged)** | T1 may build the variant behind a config flag that is **off by default**, with tests. Default engine output stays bit-identical to dry-run parity. | Any Canon change. Flipping the default. Any 011/012/014 amendment. |
| **RATIFY (Canon)** | The variant becomes Canon. T1 drafts the addendum, the default flips in a separate PR, and the registry is written **only on T0 auth**. | Nothing beyond that one ruling. |

**RATIFY can't be ticked until both of these hold:**
1. The Airtable registry is reachable again and the session-open queries have been re-run: version, next clean ID, Active Queue, and T0 Decision Log entries for MARKET-011–014.
2. An IMPLEMENT build of the same option has shipped with CI green.

**Signing this document does NOT:**
- approve merging PR #1;
- approve the reporter, which stays provisional until reporterAgent.ts v1.1 is recovered (R-01);
- approve any live-path use (the Sunday outlook stays on the `.jsx` flow);
- approve fetchers, the Scheduler, AUTO-001A/Make.com, the Supabase sink, or SFX-MARKET-015;
- resolve R-03, R-06, R-11 or R-12.

---

## Ruling A — R-02: `flow_threshold` units

**Defect (observed).** `flow_threshold = 0.001 × shares_outstanding` is a share count, but
`net_flow = inflow − outflow` is in USD. On the dry-run fixture, SPY compares 450,000 shares with
+$920M and QQQ compares 248,000 shares with −$350M. The threshold almost never binds, so
`flows.bias` is effectively `sign(net_flow)`.

**Rejected: using `price_raw.close`.** That field is the underlying's price (ES at 5118), not the
ETF's (SPY at roughly 511). Using it overstates the threshold about 10×, which flips both
fixture assets to `Mixed`.

### Option A1 (recommended): `flow_threshold_usd = 0.001 × shares_outstanding × etf_close`

**Input contract (012, additive).** `etf_flows_raw` gains two fields:

| Field | Type | Rule |
|---|---|---|
| `etf_close` | float > 0 | The ETF's own official closing price, for the `etf_flows_raw.ticker` ETF |
| `etf_close_date` | ISO date | The trading session that `etf_close` belongs to |

**Source.** `etf_close` comes from the same ETF-flows fetch as `inflow`/`outflow`: the same
ticker, the same vendor call, and the same session. It is never derived from `price_raw`, from
another asset, or from intraday prints. If the flows vendor doesn't supply a close, the
ETF-Flows-Fetcher must fetch the official close for that ticker and session separately and record
the source.

**Freshness.** `etf_close_date` must equal the session of `etf_flows_raw.date`, comparing the
UTC calendar date. Anything else counts as stale. No staleness window is allowed; the
flows-vs-price lag has to be zero sessions.

**Missing or invalid inputs, flag ON.**

| Condition | Engine behavior |
|---|---|
| `etf_close` absent, ≤ 0 or non-finite | `NormalizationError` for that asset (fails closed). The asset is excluded from the run and the trace records the reason. |
| `etf_close_date` absent or ≠ the flows session | Same: fails closed. |
| `shares_outstanding` absent or ≤ 0 | Already rejected by the raw schema. |

Fail-closed is recommended so the engine never silently mixes units. The alternative (A1-alt)
falls back to the share-count threshold and tags `flows.threshold_basis = "shares_legacy"`. That
keeps the asset in the brief, but it reintroduces the defect for that row.

**Missing inputs, flag OFF.** The new fields are optional and ignored, and output is identical to v0.

**Contract surface.**
- 011 keeps the field name `flows.flow_threshold`. Under A1 its value is in USD.
- The normalized layer gains `flow_threshold_basis: "usd" | "shares_legacy"`. This field is internal and not part of 011.
- RATIFY requires a 012 amendment covering the new raw fields and the formula, plus a 011 note on the units.

**Tests required for IMPLEMENT.**
1. Threshold boundary: exactly at, just above, and just below.
2. Fixture result with illustrative ETF closes (SPY 511, QQQ 435, *hypothetical*): thresholds of about $230M and $108M, and biases unchanged.
3. Each fail-closed row above.
4. Flag-off output is bit-identical to golden.
5. `price_raw.close` is never read by the flow path. The test asserts this by mutating `price_raw.close` and checking the threshold doesn't change.

| Option | Summary |
|---|---|
| **A1** | USD threshold from `etf_close`, failing closed on missing or stale price (above) |
| A1-alt | As A1, but missing or stale price falls back to `shares_legacy` with a tag |
| A2 | Keep as ratified, and record the units mismatch as a known limitation |
| A3 | Convert flows to shares (`net_usd / etf_close`). It needs the same price input and changes the meaning of 012 `inflow`/`outflow`. |

- IMPLEMENT (flagged): [x] A1  [ ] A1-alt  [ ] A3  [ ] none. **T0 approved 2026-10-12. Built.**
- RATIFY (Canon): [ ] A1  [ ] A1-alt  [ ] A2  [ ] A3. *Blocked until the §0 preconditions hold.*

---

## Ruling B — R-04: gamma-flip fallback

**Conflict (observed).** When no adjacent strike pair changes net-GEX sign, the dry run sets
`gamma_flip_level = round(underlying × 0.99)`. That value is not derived from options data, and
MARKET-014 says "zero heuristics".

### Option B1 (recommended): report "no flip" explicitly

**Crossing rule (unchanged, now written down).**
- Strikes are ascending and same-strike rows are summed (R-08).
- A flip exists in the first adjacent pair (a, b) where `net_gex(a) ≤ 0 < net_gex(b)` or `net_gex(a) ≥ 0 > net_gex(b)`.
- The flip is linearly interpolated, rounded with `Math.round` semantics.
- A strike whose net GEX is exactly 0, next to a non-zero strike, therefore yields that strike as the flip.

**No-crossing cases, all handled the same way:** every strike positive, every strike negative, a
single strike, every strike exactly zero.

**Contract changes (amendments required for RATIFY):**

| Layer | Change |
|---|---|
| 011 `gamma.gamma_flip_level` | `int` → `int \| null`. Proposed 011 v1.1 → v1.2. |
| Normalized `gamma_flip_source` | `"interpolated" \| "unavailable"`. The `"fallback"` value is removed. |
| 014 Key Levels line | `gamma flip — (no flip in chain)` |
| 014 Summary Table | `gamma_flip_level` cell renders `—`. `SummaryRow.gamma_flip_level` becomes `int \| null`. |
| 014 Interpretation | The ratified regime strings are **not edited**. When the flip is null, append ` Gamma flip unavailable (no sign change in chain).` after the regime string, before the crowding and stale suffixes. |

**Unchanged by B1:** `gamma.regime`, `volatility_note` and magnets come from net and total GEX, not the flip.

**Tests required for IMPLEMENT.**
1. Each no-crossing case above returns null and `"unavailable"`.
2. Zero-net strike adjacent to a non-zero strike: the flip equals that strike.
3. Crossing in the first interval vs. a later one, to confirm the first crossing wins.
4. Reporter output for a null flip: Key Levels, Summary Table and the interpretation suffix.
5. The 011 contract still rejects a non-integer, non-null flip.
6. Flag-off output is bit-identical to golden.

| Option | Summary |
|---|---|
| **B1** | Nullable flip, rendered as "no flip in chain" (above) |
| B2 | Ratify the 0.99 fallback as a named exception to "zero heuristics" |
| B3 | Fall back to the cumulative-GEX zero crossing. This is a new rule and needs its own spec. |

- IMPLEMENT (flagged): [x] B1  [ ] B3  [ ] none. **T0 approved 2026-10-12. Built.**
- RATIFY (Canon): [ ] B1  [ ] B2  [ ] B3. *Blocked until the §0 preconditions hold.*

---

## Ruling C — R-05: key levels and magnets

**Conflict (observed).** These rules come from the dry run, not the addendum:
- support = {MA50, MA200} below close
- resistance = close × {1.01, 1.025}
- gamma magnets = the top 3 strikes by |net GEX|

The fixed resistance percentages are not data-derived.

### Option C1 (recommended)

**Magnets (written down, one change):**
1. Candidates are strikes after the R-08 aggregation. **Strikes with net GEX exactly 0 are excluded.** This is the one change from the dry run: a strike carrying no gamma is not a magnet.
2. Rank by |net GEX| descending. Ties go to the lower strike, which is deterministic and matches the current stable sort.
3. Take the top `min(3, number of candidates)`. **With fewer than three candidates, return all of them. With none, return an empty list.** Nothing is padded or invented.
4. The output is sorted ascending. `key_levels.gamma_magnets` equals `gamma.gamma_magnets`.

**Support (data-derived, otherwise unchanged).** {round(MA50), round(MA200)} **strictly below**
close, sorted descending, with duplicates collapsed. Magnets are **not** added to support. That
keeps support MA-based and avoids double counting.

**Resistance (replaces the percentages).** Magnets **strictly above** close, ascending. **If no
magnet is above close, resistance is `[]`**, rendered `—`. There is no fallback to percentages or
to MAs.

**Overlap rules (guaranteed by construction):**
- A level can't be in both support and resistance: support is strictly below close and resistance strictly above.
- A magnet exactly at close is in neither list, but stays in `gamma_magnets`.
- A level can appear in both `support` and `gamma_magnets` (for example, MA50 coinciding with a strike). Both lists are kept, because they mean different things.

**Contract surface.** 011 field shapes are unchanged. All are `list[int]`, and empty lists were
already valid. RATIFY requires a 011/014 amendment stating these derivation rules.

**Tests required for IMPLEMENT.**
1. Zero, one, two, three and four or more non-zero strikes.
2. All strikes at net GEX 0, giving empty magnets.
3. A tie on |net GEX|: the lower strike wins.
4. No magnet above close, giving empty resistance.
5. A magnet exactly at close.
6. MA50 == MA200, collapsing to one support level.
7. An MA equal to a magnet strike: both lists keep it.
8. Fixture deltas documented: ES resistance becomes [5150, 5200] and NQ becomes [18000, 18250]. Supports and magnets are unchanged on the fixture.
9. Flag-off output is bit-identical to golden.

| Option | Summary |
|---|---|
| **C1** | Data-derived support and resistance with explicit edge rules (above) |
| C2 | Ratify all dry-run formulas as they are, including the +1% / +2.5% resistance |
| C3 | Remove `support`/`resistance` until a key-levels spec exists; keep magnets only |

- IMPLEMENT (flagged): [x] C1  [ ] C3  [ ] none. **T0 approved 2026-10-12. Built.**
- RATIFY (Canon): [ ] C1  [ ] C2  [ ] C3. *Blocked until the §0 preconditions hold.*

---

## Acknowledged without a ruling (record only)

- **R-07 / R-08:** engine-level hardening. A degenerate COT history fails closed, and the options chain is sorted by strike with duplicate strikes summed.
- **R-01, R-03, R-06, R-11:** queued for T1 triage → T0 gate once the registry quota resets.

## What T1 does on each box

| Box ticked | T1 action |
|---|---|
| IMPLEMENT | A flag per ruling (default off), the tests listed above, and a golden-parity check with flags off. No doc changes to 011/012/014. *As built:* all three landed in one commit on the PR #1 branch, because this session may push only to its designated branch. Each flag is independent and separately testable. |
| RATIFY | 1. Re-run the session-open registry queries. 2. Draft the addendum, STAGED. 3. T0 approves the addendum. 4. Flip the default in a separate PR, re-baseline the golden, and add an oracle-delta test. 5. Write to the registry only on T0 auth. |

**T0 signature (IMPLEMENT boxes):** T0, A1 + B1 + C1 approved in session ("IMPLEMENT A1, B1, C1 approved — build flagged variants").  **Date:** 2026-10-12

**T0 signature (RATIFY boxes):** ____________  **Date:** ________ *(not before the §0 preconditions)*

={∆§/π}™
