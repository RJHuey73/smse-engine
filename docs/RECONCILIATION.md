# SMSE Engine v0 — Reconciliation Log

The status of everything below is **STAGED**: T1 findings that await T0. Nothing here is ratified.

## Evidence base

| Source | Label |
|---|---|
| Notion: Canon Addendum v8.12.0 (2026-04-30), SFX-MARKET-011–014 | observed |
| Notion: Canon Addendum v8.13.0 (2026-05-10), SFX-MARKET-015 | observed |
| Drive: `smse-pipeline-dryrun.jsx.pdf` (T0-authorized 2026-04-30) | observed. This is the behavioural reference. |
| Airtable Canon ID Registry | **unavailable**: HTTP 429, quota exhausted on 2026-10-11. Canon status is unverified against the registry. |
| reporterAgent.ts v1.1 and reporterAgent.test.ts v1.1 | **not found** (2026-10-11): Notion keyword search; Drive full-text for `reporterAgent`, `reporterAgent.test`, `SummaryRow` and `T2 bundle`; the dry run's parent folder `19lcpre8…`; all local repos. **Not searched:** Drive subfolders, T2 chat logs (Copilot session). |

## Open items for T0

| ID | Severity | Finding | v0 behaviour |
|---|---|---|---|
| R-01 | High | reporterAgent.ts v1.1 is missing, and MARKET-014 cites "3 defects patched" that can't be verified. | The reporter follows the dry-run strings. The text in non-interpretation sections is a plain rendering of fields. Diff the two once v1.1 is recovered. |
| R-02 | **High** | **Units mismatch.** `flow_threshold = 0.001 × shares_outstanding` is a share count, but `net_flow = inflow − outflow` is in USD in the dry run. For SPY the threshold is 450,000 against a $920M flow, so the threshold almost never binds and `flow_bias` reduces to the sign of `net_flow`. | Implemented as ratified, unchanged. Two fixes are possible: convert the threshold to $ (× price), or feed flows in shares. Either one is a Canon change. |
| R-03 | Medium | There are two crowding vocabularies. `flows.crowding` (COT+flow) can be `Crowded` while `regime.risk_note` (COT-only) is `Uncrowded`. The dry-run fixture does this for NQ. | Both are kept as observed. The reporter shows both. |
| R-04 | Medium | The gamma flip falls back to `underlying × 0.99` when no sign change exists. That is a heuristic, which conflicts with MARKET-014's "zero heuristics" rule. | Kept for parity. Exposed as `gamma_flip_source: "fallback"` in the normalized layer only, so the 011 contract is unchanged. |
| R-05 | Medium | The key levels (support from MA50/MA200, resistance at +1%/+2.5%) and the 3 gamma magnets are dry-run behaviour, not addendum text. | Kept for parity. Constants are named in `constants.py`. |
| R-06 | Medium | Agent count. The addendum lists 8 agents (4 fetchers, Normalizer, Synthesizer, Registry, Reporter) and also names a Scheduler-Agent, which would make 9. | v0 implements 4 stages. The Scheduler is excluded because of the AUTO gate. |
| R-07 | Low | The z-score is undefined for empty or zero-variance history. In JS this yields `±Infinity`, so a zero-variance history can print `StrongLong`. | **Deviation.** Fails closed with `NormalizationError` (inferred). |
| R-08 | Low | The dry run assumes the options chain is sorted and has one expiry. | **Deviation.** The chain is sorted by strike and same-strike rows are summed. Output is identical on the canonical fixture. |
| R-09 | Low | The z-score uses population σ (÷n), the dry-run choice. The addendum is silent. | Kept as ÷n. |
| R-10 | Low | The dry-run trace hardcodes "0 stale COT flags". | Computed. |
| R-11 | Info | MARKET-015 was ratified under a blanket "Ratify everything" directive, and its sweep thresholds are qualitative ("High", "Low"). | Not implemented. Not computable as written. |
| R-12 | Info | `TrustState` values come from `shadowfox-sweep`; there is no CANON-204 enum source. | `T2-FLAGGED` (inferred). |

## Status of T1 GO order (2026-10-11)

1. Repo: **blocked**. The GitHub App gets a 403 on `create_repository` (same as Shadowfox-systems B-1). T0 creates `RJHuey73/smse-engine` (private, empty) by hand.
2. Rulings: `docs/T0-RULING-REQUEST-001.md` is now rev 2 (2026-10-12), after T0's review of rev 1. It adds edge-case rules, separates IMPLEMENT (flagged) from RATIFY (Canon), and states what a signature does not cover. Awaiting T0.
3. Flagged variants: **IMPLEMENT approved by T0 for A1, B1 and C1 (2026-10-12)** and built behind default-off flags, with the full test lists from rev 2. Flag-off output is unchanged and pinned. RATIFY is still blocked by the §0 preconditions.
4. reporterAgent.ts v1.1: not found (see evidence table). R-01 stays open, and the reporter stays provisional.
5. Registry triage: blocked by the Airtable 429. Retry after the quota resets, and re-run the session-open queries first.

## Gates honoured

- No Canon/Airtable/Supabase writes. The Registry is in-memory only.
- No Make.com wiring: WO-AUTO-001A-MARKET is OPEN and gated.
- CI: `ci.yml` (ruff, mypy strict, pytest on 3.11–3.13, JS-oracle golden diff) + `canon-lint.yml` running the vendored `.canon/canon_lint.py` (CANON_REVISION 2026.07.04, copied from the Spec repo source of truth).

={∆§/π}™
