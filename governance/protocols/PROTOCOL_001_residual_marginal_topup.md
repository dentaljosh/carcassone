# PROTOCOL_001 — Residual value-head marginal + leaf non-transitivity top-up

> **Fill and commit this BEFORE running the experiment.** Store separately from results so the hypothesis cannot be rewritten after the outcome is known. One filled protocol per material experiment.
>
> This is the WORKED EXAMPLE for [`../PROTOCOL_TEMPLATE.md`](../PROTOCOL_TEMPLATE.md). It documents the clean-eval top-up — **COMPLETE 2026-06-08** (see RESULT: marginal +37.6 elo / z=2.98 at n=1200 → CL-004 PASS).

**Layer:** DECISIONS-support / INTERPRETATION (see [../README.md](../README.md)). Pre-registered ahead of the run; the `RESULT` section is the only part to be filled at completion.

---

## experiment_id
`PROTOCOL_001` / `cleaneval_topup_residual_marginal_nontransitivity`

## decision
Two coupled decisions, both read against [`../CLAIM_REGISTRY.csv`](../CLAIM_REGISTRY.csv):
- Whether residual scale 0.25's value head is a **real strength lever** → resolves **CL-004** (the value-head marginal) and gates **CL-005** (use residual scale 0.25 in production).
- Whether the **v1 ↔ v2.7 leaf non-transitivity** holds on a fully-clean ruler → corroborates **CL-012** (historical unmatched-leaf Elo is non-comparable; already Invalidated).

## primary hypothesis
The residual value-head marginal — `scale0.25 − scale0`, deck-paired at matched v2.7 leaf — is a **real ≥ +35 elo / 2σ gain**.

## competing hypotheses
- **H0 (null):** the marginal is null / `< 2σ` noise.
- **H-small:** the marginal is real but `< 35 elo` — production-irrelevant (a mechanism finding, not a strength lever).

## single variable changed
Two pre-registered questions, **one run**:
- **Residual cells:** `--residual-scale` ∈ {0, 0.25}. The marginal is `scale0.25 − scale0`.
- **Non-transitivity cells:** opponent `--heur-leaf` ∈ {v1, v2_7}, holding the agent checkpoint fixed.

## held fixed
`residual.pt` checkpoint; `sims=200`; deck set (seed `1e9` namespace); env `CAP=12`, `DROP_THREE_OPEN=1`; matched-v2.7 opponent for the residual cells; paired seats (same deck both colors).

## primary metric
Deck-paired Δ winrate → elo ± σ (with z). Deck-pairing (same seed both seats) ~halves variance vs an unpaired head-to-head.

## secondary metrics
- Per-cell absolute elo.
- The clean **non-transitivity 2×2**: {iter_11, Stage-B iter_01} × {heur v1, heur v2.7}.

## sample size
- **Residual cells:** extended 400 → **1200 paired each**. At the observed effect (+0.0375 wr), `n_paired ≈ 1200 → z ≈ 2.25` if the effect holds.
- **Non-transitivity cells:** `n = 400 paired`. The v1↔v2.7 gaps are 50–65 elo `= > 2σ at n=400`, so n=400 paired is a verdict for them.

(Calibration: near wr=0.5, σ_elo ≈ 695·√(0.25/n) unpaired; deck-pairing ~halves it. n=400 paired ≈ ±12 elo; n=1200 paired resolves the +26 elo marginal to ~2σ.)

## pairing / seed design
Deck-paired — same seed on both seats. `--seed-start 1e9` clean namespace (above the self-play seed floor, so no overlap-seed / E4 contamination). Deck hashes recorded per game.

## top-up rule
**PRE-REGISTERED:** if the residual marginal lands `1.3 < z < 2` at n=1200, escalate to **n ≈ 1500 ONCE**. Do **not** peek-and-extend repeatedly. This is the only sanctioned extension; any other n change voids the pre-registration.

## stopping rule
Fixed n. **No optional stopping.** Summarize only at the target n (1200, or 1500 if the one-shot top-up fires).

## success threshold
Marginal `≥ +35 elo (2σ)` → **CL-004 → Supported**, and **CL-005 becomes a live production-gate question** (a follow-on production-gate eval is licensed).

## failure threshold
Marginal `< 2σ` at n=1200 (→ 1500 after the one-shot top-up) → **CL-004 → Disfavored / Inconclusive-capped**, and **CL-005 stays Untested** (drop residual scale 0.25 as a production lever; retain it only as a studied mechanism).

## what each outcome PERMITS
- **Success (≥ +35 elo / 2σ):** PERMITS opening a production-gate eval for residual scale 0.25 (the CL-005 question goes live).
- **Null (< 2σ):** PERMITS keeping the residual value head as a **studied mechanism** (telemetry / Phase-B observability), even though it is not a strength lever.
- **H-small (real but < 35 elo):** PERMITS recording a mechanism-level positive marginal; does not license a production change.

## what each outcome FORBIDS
- **A Supported marginal FORBIDS auto-fold-in into production.** Supported is in-ecosystem (vs our own matched v2.7); folding residual scale 0.25 into the production agent still REQUIRES an **out-of-lineage check** first (out-of-lineage ladder / human-anchored, per CL-001/CL-010). CL-005 stays gated until that check passes.
- **A null FORBIDS claiming the value head adds strength.** It may NOT be reported as a strength gain, may NOT be used to justify CL-005, and may NOT be cited to upgrade CL-004 above Disfavored/Inconclusive.
- **Either way:** FORBIDS treating any per-cell absolute (secondary metric) as cross-epoch comparable to historical unmatched-leaf numbers (E3) — those remain Invalidated under CL-012.

## estimated compute cost
~2400 new games, 3-box cluster, ~3.75 hr wall, **EVAL ONLY (no training).**

## links to manifests / raw outputs
- Run dirs (RAW, append-only):
  - `/mnt/c/carc-shared/clean_eval_runs/r4_residual_rs0_*` — residual scale 0
  - `/mnt/c/carc-shared/clean_eval_runs/r5_residual_rs025_*` — residual scale 0.25
  - `/mnt/c/carc-shared/clean_eval_runs/t1_iter11_vs_heurv1_*` — non-transitivity, iter_11 × v1
  - `/mnt/c/carc-shared/clean_eval_runs/t2_stageb_iter01_vs_heurv1_*` — non-transitivity, Stage-B iter_01 × v1
- Analysis: `scripts/summarize_clean_eval.py`, `scripts/analyze_nontransitivity.py`
- Launcher: `scripts/run_clean_eval_topup.sh` (commit `4d43c79`)
- Per-run `manifest.json` lands in each run dir; clean rows land in `clean_eval/CLEAN_RESULTS.csv`.

---

## RESULT (COMPLETE — 2026-06-08, all cells at target n; commit `4d43c79`)

| cell | run dir | design | metric | value | z | notes |
|---|---|---|---|---|---|---|
| r4 — residual scale 0 | `r4_residual_rs0_*` | n=1200 paired, vs matched v2.7 | absolute elo | **+62.0 ± 10** | 6.2 | residual baseline (policy only) |
| r5 — residual scale 0.25 | `r5_residual_rs025_*` | n=1200 paired, vs matched v2.7 | absolute elo | **+99.6 ± 10** | 10.0 | residual treatment (value head ON) |
| **marginal (r5 − r4)** | — | deck-paired Δ (n=1200) | **Δwr / elo (z)** | **+0.0512 wr ≈ +37.6 elo** | **2.98** | **primary → CL-004 PASS** |
| t1 — iter_11 vs heur-v1 | `t1_iter11_vs_heurv1_*` | n=400 paired | absolute elo | **+35.7 ± 17** | 2.1 | clean v1 (old contaminated: +25.2) |
| t2 — Stage-B iter_01 vs heur-v1 | `t2_stageb_iter01_vs_heurv1_*` | n=400 paired | absolute elo | **+24.4 ± 17** | 1.4 | clean v1 (old contaminated: **+86.9**) |

**Top-up fired?** No — the marginal cleared 2σ at the pre-registered n=1200 (z=2.98 > 2), so the n→1500 escalation was not triggered.

**Primary verdict — residual value-head marginal:** **+37.6 elo, z=2.98 ≥ 2σ → SUCCESS.** Per the pre-registered rule:
- **CL-004 → Supported** (the residual value head adds real strength; the old "+45 robust" largely survives clean at +37.6, just properly powered — the n=400 screen at z=1.30 was underpowered, not wrong).
- **CL-005 → live production-gate question** (no longer auto-dropped). Per the pre-registered FORBIDS, this still does NOT license auto-fold-in: a clean **out-of-lineage** check is required (the 2026-06-07 odometer validated it out-of-lineage but at seed 950k, which is in the E4 overlap namespace — a clean-seed odometer rerun is the rigorous final gate). Joshua chose a **residual@0.25-vs-iter_11 head-to-head** (PROTOCOL_002) to crown the production agent + resolve CL-002/CL-005.

**Secondary verdict — non-transitivity: OVERTURNED on the clean ruler.** Clean 2×2:

| net | vs heur-v1 (clean) | vs heur-v2.7 (clean) | Δ(v2.7−v1) | old contaminated v1 |
|---|---|---|---|---|
| iter_11 | +35.7 | +89.7 | **+54 elo (z=2.29)** | +25.2 |
| Stage-B iter_01 | **+24.4** | +34.9 | +10 elo (z=0.46, n.s.) | **+86.9** |

`analyze_nontransitivity.py` verdict: **SAME sign for both nets** → non-transitivity NOT supported. The earlier "sign-varying / Stage-B finds v2.7 harder" reframe was an **artifact of the contaminated Stage-B-vs-v1 (+86.9)** — clean it is **+24.4** (a 62-elo contamination gap). Coherently, **both** nets beat the v2.7-leaf opponent by more than the v1-leaf opponent (net-specific magnitude: iter_11 +54, Stage-B +10) because **v2.7 is the weaker standalone opponent leaf** (corroborates r1's −24.4). So absolutes don't sign-flip per-net; they were just unevenly *inflated* in the contaminated era. → **CL-012 STRENGTHENED** (old unmatched-leaf numbers incomparable — Stage-B-vs-v1 +86.9→+24.4 is the sharpest single example); **the non-transitivity reframe is Disfavored** (new CL-016).

**Final summaries:** `clean_eval/CLEAN_RESULTS.csv` (7 rows), `clean_eval/CLEAN_EVAL_AUDIT.md`, `experiments/results.csv: cleaneval_{r4,r5}_n1200, cleaneval_t1, cleaneval_t2`. Marginal: `scripts/summarize_clean_eval.py`; 2×2: `scripts/analyze_nontransitivity.py`.
