# PROTOCOL_001 — Residual value-head marginal + leaf non-transitivity top-up

> **Fill and commit this BEFORE running the experiment.** Store separately from results so the hypothesis cannot be rewritten after the outcome is known. One filled protocol per material experiment.
>
> This is the WORKED EXAMPLE for [`../PROTOCOL_TEMPLATE.md`](../PROTOCOL_TEMPLATE.md). It documents the clean-eval top-up **running right now** (see RESULT — PENDING).

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

## RESULT (PENDING — run in flight, ~ETA 02:30 UTC 2026-06-08)

Fill ONLY this section at completion. Do not edit the hypothesis/thresholds above. Record the primary metric with z, which threshold was met, and the CL-004/CL-005 (and CL-012) status transitions.

| cell | run dir | design | metric | value | z | notes |
|---|---|---|---|---|---|---|
| r4 — residual scale 0 | `r4_residual_rs0_*` | n=1200 paired, vs matched v2.7 | absolute elo | _pending_ | — | residual baseline |
| r5 — residual scale 0.25 | `r5_residual_rs025_*` | n=1200 paired, vs matched v2.7 | absolute elo | _pending_ | — | residual treatment |
| **marginal (r5 − r4)** | — | deck-paired Δ | **elo ± σ (z)** | _pending_ | _pending_ | primary metric → CL-004 verdict |
| t1 — iter_11 × {v1, v2.7} | `t1_iter11_vs_heurv1_*` | n=400 paired | v1↔v2.7 gap (elo) | _pending_ | — | non-transitivity → CL-012 |
| t2 — Stage-B iter_01 × {v1, v2.7} | `t2_stageb_iter01_vs_heurv1_*` | n=400 paired | v1↔v2.7 gap (elo) | _pending_ | — | non-transitivity → CL-012 |

**Top-up fired?** _pending_ (yes/no — only if 1.3 < z < 2 at n=1200).

**Verdict:** _pending_ →
- if marginal ≥ +35 elo / 2σ: CL-004 → **Supported**, CL-005 → **live production-gate question** (still FORBIDS auto-fold-in; out-of-lineage check required).
- if marginal < 2σ: CL-004 → **Disfavored / Inconclusive-capped**, CL-005 → **stays Untested**.

**Final summaries:** _pending_ (link `scripts/summarize_clean_eval.py` / `scripts/analyze_nontransitivity.py` output + `clean_eval/CLEAN_RESULTS.csv` rows).
