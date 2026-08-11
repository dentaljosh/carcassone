# C5 — Leaf re-tune under PUCT ("v2.11-for-PUCT") — PRE-REGISTERED DESIGN

> **STATUS: DESIGN / PRE-REGISTERED 2026-07-10 — NOT LAUNCHED.** No compute has run.
> Roadmap: [docs/PROGRAM_ROADMAP_2026-07-07.md](../../docs/PROGRAM_ROADMAP_2026-07-07.md) Track C, item C5 (C1–C4 closed → C5 unblocked).
> Design-only; PRODUCTION.yaml untouched by anything in this document.

## Premise

The v2.9.1 `Bmild_cap8` leaf tunables were optimized under **HeuristicMCTS random-expansion UCT**
(the 2026-06-25 four-wave retune, DECISIONS.md "v2.9.1 leaf retune", sims=200, one-random-child/sim,
leaf consumed as **values only**). The consumer changed on 2026-07-07 (CL-043): the champion is now
**PUCT with heuristic-leaf priors** (`governance/PRODUCTION.yaml` — c_puct=1.5, tau_p=5, float leaf,
visits-argmax, ~2750 sims, exact-K≤4), where the leaf **additionally shapes the priors**:
P(a) = softmax(dLeaf(a)/tau_p) over per-child afterstates and value = tanh(leaf/15)
(`src/carcassonne_ai/heuristic_prior_mcts.py:66-114`). Under random expansion only the leaf's
*ranking at the backed-up Q* mattered; under PUCT the leaf's *sibling differences* allocate the
entire visit budget. A tunable optimum under the old consumer may be off under the new one.
The deployable agent is the fair PIMC variant (k_dets=8 × sims=344, pooled-Q, CL-045/046).

**Honest prior:** three of the four 2026-06-25 waves were NULL under the old consumer (curve-scale,
closure-P, tanh-norm), the v2.10 gates were null (`v210_cap6_vs_cap8_h800_n400` +4.3/z0.45,
`v210_bagclose_vs_cap8_h800_n400` −6.1), and value_norm was re-confirmed **under PUCT** by C4
(`rr_puct2750-vn8/-vn30` −24.4/−36.6). The one historical WIN axis is the closure cap
(v2.5: cap 5→12 + drop-3-open = 70→90% wr after the dedup fix; v2.9 Wave B: cap 5→8 = +46.3
`v291_waveB_bmild_cap8_vs_cap5_s200_n400`). C5's EV rests entirely on the consumer-change
mechanism, not on untested axes — expect a null and size the kill gates accordingly.

## No-touch guarantees

- **`governance/PRODUCTION.yaml` is NOT modified** by any stage. A winning result produces a
  *flip proposal doc* for Joshua; only he authorizes promotion.
- All evidence lands as `experiments/results.csv` rows + per-cell `manifest.json` (self-describing
  resolved config incl. **per-side `leaf_cfg` + `leaf_hash`** — see Trap 1 below).
- Champion-side config in every cell is the PRODUCTION.yaml champion verbatim (v2.9 Bmild_cap8,
  env `CARCASSONNE_V25_CAP=8 / V25_OPP_CAP=8 / V25_DROP_THREE_OPEN=0 / V29_MEEPLE_CURVE=-8,-4,-1,0,2,3,4,5`,
  per `scripts/classical_search/run_screen_sweep.sh:79-80`).
- Zero cloud. Local 5900XT + laptop only, `nice -n 19`, pre-launch process census, git-bundle sync
  to the laptop before launch.

## Tunables inventory

Resolved production leaf (verified from `run_screen_sweep.sh:79-80` + PRODUCTION.yaml `leaf_config`
+ `virtual_score_v2._config_from_env` at `src/carcassonne_ai/virtual_score_v2.py:155-192`):

| # | Tunable (LeafConfig field) | Current | Bracket (screen) | Rationale / expected sensitivity |
|---|---|---|---|---|
| 1 | `bonus_cap` + `opp_bonus_cap` tied | 8.0 / 8.0 | **{5, 8*, 12} tied** | HIGH. The only axis that ever fired (v2.5 +20pp; Wave B +46.3, plateau 8–16 under UCT, cap12 padded blowouts). The cap clips exactly the sibling-differences PUCT turns into priors — plateau location plausibly moved. |
| 2 | `opp_bonus_cap` alone (self=8) | 8.0 | **{4, 8*, 12}** | MED. Historically tied to #1, never swept independently under any consumer. PUCT priors are mover-POV afterstate deltas — opponent-threat weighting is where expand-all differs most from random expansion. |
| 3 | `closure_p` schedule | {1:0.5, 2:0.2, 3:0.05} | **×0.8 / ×1.0* / ×1.2 scale** = {1:.4,2:.16,3:.04} / {1:.6,2:.24,3:.06} | MED-HIGH. Wave C tested only ONE up-variant (p060, collapsed 0.557→0.506); never bracketed below. Same mechanism as #1 (shapes the bonus that shapes priors). Env presets can't express these — patch constructs LeafConfig directly. |
| 4 | `v29_meeple_curve` scale | (−8,−4,−1,0,2,3,4,5) | **×0.75 / ×1.0* / ×1.25** | MED. Wave A NULL under UCT (×0.75 −37, ×1.25 −26, inverted-U at ×1.0) — but meeple liquidity enters every placement prior under PUCT; the strongest "consumer changed" story of the null axes. Float leaf → scaled float curves are fine (cy `_curve_lookup_c` takes floats). |
| 5 | curve = None + `meeple_k`=2.0 | curve ON | **1 cell: curve OFF** | LOW-MED. "Is Candidate B still needed under PUCT?" — the curve was adopted under UCT. NB `meeple_k` is INERT while the curve is set (`flat_leaf.py:835-840`, elif); this is the only arm where it does anything. |
| 6 | `bag_close` (v2.10) | False | **1 cell: True** | LOW. Fresh null under h800 UCT (−6.1, `v210_bagclose_*`), cy-supported (`SUPPORTS_V210_BAG_CLOSE`), costs 1 cheap cell to re-check under the new consumer. |

**Excluded axes (pre-registered, with reason):**

- `value_norm` (=15) — **freshly settled UNDER PUCT** (ROADMAP C4 CLOSED, `rr_puct2750-vn8/-vn30`
  both wings negative). Do not re-run.
- `v29_util_tanh_t`, `v29_punish_k`, `v29_farm_access_k` (all 0/off) — lost/not adopted in the
  v2.9 wave AND they force the engine object path (`virtual_score_v2.py:228-246` `_v29_active` /
  `_v29_curve_only`): no Cython float leaf → the PUCT float-leaf candidate would run the ~30×
  slower pure-Python reproduction (`flat_leaf.py:844-855`). Cost-prohibitive at 2750 sims; only
  reconsider if everything else nulls AND Joshua asks.
- `tile_counting_closure`, `closure_continuous_slack` — v2.5-era nulls (`phase3_tc_c3_vs_v27`
  −12.2; optuna trials negative) + force the non-cy path (`flat_leaf_cy.pyx:969`).
- `V_PUNISH`/`V_FARM` module constants (`leaf_v29.py:75,126`) — inert while punish/farm k = 0.
- `meeple_k` as an independent axis — inert under the production curve (see #5).
- Consumer knobs `c_puct`/`tau_p`/`final_select`/`leaf_quantize` — not leaf axes; settled by
  Phase 1.1 R1–R5 + C2. **BUT** see Stage 4: a leaf-scale winner mandates a tau_p re-check
  (bug-fix-shifts-optima rule), and the pre-registered R7 tau bracket {3,8} at 2750 never ran
  (TAU_BRACKET_PROGRESS.tsv empty, no results.csv rows) — Stage 4 subsumes it.

## Screen consumer (pre-registered)

- **Clairvoyant, candidate-leaf PUCT@2750 vs champion-leaf PUCT@2750** via
  `scripts/classical_search/eval_puct_priors.py --candidate puct --opponent puct` (the
  variant-ON-vs-variant-OFF champion-sibling A/B used for C2/C3/C4, reuse OFF both sides,
  exact-K=2 both sides, deck-paired seats). Same template as `rr_puct2750-vn8_vs_puctchamp2750_k2`.
- **Why clairvoyant:** it is the sanctioned *cheap screen* (ROADMAP #4b / D-1 demoted clair to
  exactly this role). **Goodhart caveat carried forward:** clair strength is a bad proxy for fair
  (tax swings 26↔156, agent-dependent; reuse's +39 evaporated fair) → **no leaf change is
  proposed for production on clair evidence alone**; Stage 3 fair re-confirm is mandatory.
- Equal sims both sides is the right control (leaf reweights don't change per-sim cost); the
  harness records `cand/champ_prefix_ms_per_move` — pre-register a parity check
  ms-ratio ∈ [0.9, 1.1] (house style from the reuse confirm), since bag_close/curve-off do
  perturb leaf cost slightly.
- **Seed bands** (fresh, disjoint from every band found in scripts + results.csv:
  4.21e9, 9.0–9.031e9, 9.4e9, 9.5e9, 9.6e9, 9.99e9, 1.1e10, 13/13.1e9 smoke, **15e9 D0 fair**,
  40e9 gen):
  - Screen: **1.20e10**, ONE band shared by all cells (CRN across cells, round-5 pattern).
  - Interaction 2×2: **1.22e10**. Clair confirm: **1.24e10** (fresh). Stage-4 consumer re-check:
    1.20e10 (CRN vs the winner's screen cell).
  - Fair re-confirm: **15e9 deliberately REUSED** = the cached D0 baseline band (CRN-paired via
    `scripts/classical_search/crn_delta_fairnet.py`, whose baseline default is
    `/mnt/c/carc-shared/fair_ladder_s2752_vs_h800_k2`, n=200, band 15e9). Note in the row that
    this is a paired-ruler reuse, not an independent fresh-band verdict.

## Stage 0 — harness patch + mirror validation (blocking prerequisite)

`eval_puct_priors.py` currently passes env-resolved `DEFAULT_CONFIG` to **both** sides
(lines 546/564) — it cannot express a leaf A/B. `HeuristicPriorConfig.leaf_cfg` already exists
(`heuristic_prior_mcts.py:162`, None → DEFAULT_CONFIG), so the patch is small:

1. Add `--cand-leaf-json '{...}'` to `eval_puct_priors.py` (and `eval_fair_puct.py` for Stage 3):
   construct a `LeafConfig` (replace-fields-on-DEFAULT_CONFIG) for the **candidate side only**;
   champion side stays env DEFAULT_CONFIG. Record both sides' resolved leaf_cfg + leaf-hash in
   the manifest (the hash helper exists, `eval_puct_priors.py:422`).
2. **Mirror test (gate):** `--cand-leaf-json` = the champion leaf verbatim, n=20 @ band 1.20e10 →
   must be bit-identical games to the no-flag run (same seeds ⇒ same move sequences), elo 0,
   and reproduce the C4 null template (`rr_puct2750_vs_puctchamp2750_k2` = 0.0). Plus 1 pytest
   asserting cand-side LeafConfig ≠ champ-side when the flag differs and == when absent.
3. Cy-path guard: assert each candidate cfg stays on the Cython float path
   (`_v29_curve_only` true or curve None; bag_close only if `SUPPORTS_V210_BAG_CLOSE`) — all
   10 screen cells qualify by construction.

ETA: ~1–2 h dev + ~0.3 box-h smoke.

## Stage 1 — SCREEN (clairvoyant, n=100/cell, 10 cells)

All cells: deck-paired n=100 (50 decks × 2 seats), K=2, band 1.20e10, opponent = champion sibling.
1σ_paired ≈ ±25 elo at n=100 (n=400 paired ≈ ±12; pairing ≈ halves variance — CLAUDE.md G-M2).

| Cell (results.csv exp_id prefix `c5_`) | Candidate leaf delta |
|---|---|
| c5_cap5_vs_puctchamp2750_k2 | bonus_cap=opp_bonus_cap=5 |
| c5_cap12_vs_puctchamp2750_k2 | bonus_cap=opp_bonus_cap=12 |
| c5_oppcap4_vs_puctchamp2750_k2 | opp_bonus_cap=4 (self 8) |
| c5_oppcap12_vs_puctchamp2750_k2 | opp_bonus_cap=12 (self 8) |
| c5_pclose080_vs_puctchamp2750_k2 | closure_p ×0.8 |
| c5_pclose120_vs_puctchamp2750_k2 | closure_p ×1.2 |
| c5_curve075_vs_puctchamp2750_k2 | curve ×0.75 |
| c5_curve125_vs_puctchamp2750_k2 | curve ×1.25 |
| c5_nocurve_mk2_vs_puctchamp2750_k2 | curve=None, meeple_k=2.0 |
| c5_bagclose_vs_puctchamp2750_k2 | bag_close=True |

Launch order if budget squeezes: caps (1–2) → closure_p (5–6) → opp_cap (3–4) → curve (7–9) → bag (10).

**Timing evidence:** SCREEN_PROGRESS_R5.tsv measured n=100 s2750 cells at 2425–3002 s two-box
(local primary + laptop helper, `run_screen_sweep.sh` shared-claim pattern); the C4 n=200
puct-vs-puct cell logged ~6.46/6.49 s/move/side and solver 25.5 s/game at K=2
(`rr_puct2750-vn8.../summary.json`). Plan at **~45 min two-box wall ≈ 1.5 box-h per n=100 cell**
→ 10 cells ≈ **15 box-h (~7.5 h two-box wall)** — inside the 12–20 box-h screen budget.
K=2 keeps solver RAM trivial (no K≥4 TT blowup; see memory `reference_exact_solver_eval_infra`).

## Stage 2 — clairvoyant CONFIRM (n=400, ≤2 cells)

- Promote the top ≤2 screen cells satisfying the promote gate (below) to n=400 paired, fresh band
  1.24e10, same consumer. ≈ 6 box-h/cell → ≤12 box-h.
- **2b (conditional interaction):** cap and closure_p act on the same bonus term
  (bonus = Σ p·value, then `_capped`, `flat_leaf.py:832-833`). If BOTH axes confirm, run ONE
  combined 2×2 corner cell (winner-cap × winner-p, n=100 @ 1.22e10, ~1.5 box-h); adopt the combo
  only if it ≥ max(single winners) − 1σ. No other factorials.

## Stage 3 — FAIR re-confirm (mandatory before any proposal)

- Candidate leaf inside the **deployable fair config**: `eval_fair_puct.py`, FairHeuristicPriorAgent
  k_dets=8 × sims=344 (=2752), pooled-Q, exact-K≤2 marginalized, vs the **fixed clairvoyant h800
  rung on the champion leaf** (the ruler must not move), n=200 paired, band 15e9 = the D0 band.
- Verdict via CRN-paired Δ against the cached D0 champion-fair baseline
  (`crn_delta_fairnet.py`; D0 = **+81.4 / paired_z 3.57**, `fair_ladder_s2752_vs_h800_k2`).
- ETA ≈ 3–4 box-h (D0 cells ran overnight at this config).

## Stage 4 — consumer re-check at the winner (2 cells, pre-registered cap)

Project rule: a retune in a scored heuristic shifts OTHER hyperparameter optima. Every bracket
axis here rescales leaf magnitudes, and tau_p divides dLeaf directly (leaf-scale ≅ tau shift):

- If the winner changes leaf scale (cap / closure_p / curve-scale — all do): **tau_p ∈ {3, 8}**
  at the winner leaf, n=100 clair screen @ 1.20e10 (CRN vs the winner's screen cell). This also
  discharges the never-run R7 tau bracket.
- If only bag_close wins (shape, not scale): **c_puct ∈ {1.0, 2.5}** instead.
- 2 cells ≈ 3 box-h, NOT a full re-sweep. If a neighbor beats the winner@tau5 by ≥ +35, the flip
  proposal carries the re-tuned knob and Stage 3 is re-run at that knob before proposing.

## Pre-registered decision tree

- **Screen kill (per axis):** no cell in the axis ≥ +35 elo with paired_z ≥ 1.5 → axis dead.
- **Noise-signature guard:** a wing ≥ +35 while its opposite wing is strongly negative and the
  center (champion, by construction 0) sits between = lone-spike signature → re-measure that one
  cell at a fresh sub-band (1.21e10) before promoting (results-discipline rule: a lone value
  beating its parameter-neighbors by >1σ is noise until re-measured).
- **Promote to Stage 2:** ≥ +35 AND paired_z ≥ 1.5, top ≤2 cells overall.
- **Clairvoyant confirm gate:** n=400 paired ≥ +25 elo AND paired_z ≥ 2.0 (n=400 paired 1σ ≈ 12).
  Fail → kill, log the screen as a noise spike.
- **Fair gate (the real one):** CRN-paired Δ vs the cached D0 baseline > 0 with **paired z ≥ 2.0**
  (≈ Δ ≥ +35 at n=200 paired). Pass → write `C5_FLIP_PROPOSAL.md` (leaf `v2_11_forPUCT_<axis>`),
  Joshua decides. Fail after clair fired → grade **CLAIR-ONLY** (the reuse_tree precedent,
  CL-044): record as dev/self-play-ruler knob, do NOT propose for production, note in roadmap.
- **All-null outcome** (expected-plausible): verdict "v2.9 Bmild_cap8 is at its practical ceiling
  under PUCT as well — C5 CLOSED (null)"; six-touch close-out; C5 drops off the roadmap.

## Budget summary

| Stage | Cells | box-h |
|---|---|---|
| 0 patch+mirror | smoke | ~0.5 (+1–2 h dev) |
| 1 screen | 10 × n=100 | ~15 |
| 2 confirm | ≤2 × n=400 (+2b 1 × n=100) | ≤13.5 |
| 3 fair | 1 × n=200 | ~4 |
| 4 consumer re-check | 2 × n=100 | ~3 |
| **Total** | null-case ≈ 16 box-h; full-fire worst case ≈ **36 box-h ≈ 1.8 box-days** | matches roadmap "~1–2 box-days" |

Two-box (local 5900XT primary + laptop helper, `run_screen_sweep.sh`-style shared-claim
work-stealing): null-case ≈ 1 overnight; worst case ≈ 2 nights. Detached launches
(`setsid`/nohup), per-cell resume via shared-claim, laptop synced by git bundle first.

## Traps found while reading (design-relevant)

1. **Env-global leaf config**: both sides read `DEFAULT_CONFIG` resolved from env at import —
   AND the env default is **cap=5 + 3-open** (`virtual_score_v2.py:163`), not production cap8
   (the 2026-06-25 "Finding 0" mislabel). Any worker missing the env exports silently runs cap5.
   Mitigation: manifests record per-side resolved leaf_cfg + leaf_hash; Stage-0 mirror gate.
2. **`meeple_k: 2.0` in PRODUCTION.yaml `leaf_config` is inert** — the curve replaces the flat
   term (`flat_leaf.py:835-840`). Worth a one-line PRODUCTION.yaml comment at close-out (a
   *pointer* fix, not a config change).
3. **`closure_p` is not env-sweepable** (only 3 presets, `virtual_score_v2.py:155-162`) — the
   `--cand-leaf-json` patch is required for axis 3 regardless.
4. **punish/farm/util-tanh v2.9 terms have no Cython float path** — sweeping them under PUCT
   would run ~30× slower pure-Python leaves; excluded on cost (see inventory).
5. **R7 tau bracket never ran** (empty TSV, no rows) — tau_p=5 at 2750 rests on 800-sim data;
   Stage 4 discharges it.

## Close-out checklist (six touches, one sitting — per CLAUDE.md)

results.csv rows (`c5_*`) → DECISIONS.md index line → status stamp on THIS doc →
governance CLAIM_REGISTRY row → STATUS.md top block → roadmap C5 line. Then `scripts/doc_lint.py`.
