# T3 — Joint Optuna knob sweep over the classical PUCT champion ("interaction insurance") — PRE-REGISTERED DESIGN

> **STATUS: DESIGN / PROPOSED 2026-07-14 — NOT LAUNCHED.** No code written, no compute run.
> Charter: [docs/BACKLOG_REAUDIT_2026-07-13.md](../../docs/BACKLOG_REAUDIT_2026-07-13.md) item **T3**
> ("Joint Optuna/TPE over the champion's knobs, clair-screen + fair-confirm gate, ~2 box-days").
> Design-only; `governance/PRODUCTION.yaml` untouched by anything in this document.
> Scope: ONE joint 7-knob Optuna/TPE screen (clairvoyant, CRN, successive-halving) →
> n=400 fresh-deck clair confirm of the top-3 → mandatory fair gate, the CL-051/CL-054 template.

---

## ORCHESTRATOR RESOLUTION OF THE OPEN QUESTIONS (2026-07-14, pre-launch verification)

Recorded before coding so the pre-registration is auditable. Fable authored the design (no write
tool → returned inline); the orchestrator materialized it and verified its load-bearing claims:

1. **Sequencing prereq SATISFIED.** The design pre-registered "launch after C7 closes." **C7 is
   already CLOSED NULL (CL-055, 2026-07-14)** — both terms tested, nothing adopted. So the champion
   baseline is the curve125 champion (leaf `v2_9_2_Bmild_cap8_curve125`, hash `158f17ff…`) exactly
   as §2 assumes; no rebase needed. §5(e)'s champion-hash gate stands unchanged.
2. **The shared-axis leak is REAL — CONFIRMED at the source.** `eval_puct_priors.py` builds
   `shared = {c_puct, tau_p, leaf_quantize}` from the *candidate's* args (line ~988) and
   `_champ_puct_cfg(shared)` (lines 251-262) copies them onto the `--opponent puct` sibling.
   Moving `--c-puct` today moves BOTH sides. The `--opp-pin-champion` Stage-0 flag (§3/§5a) is
   mandatory, not optional. This is the one real plumbing item.
3. **Bands 2.00e10 / 2.009e10 / 2.01e10 / 2.02e10 / 2.03e10 VERIFIED FREE.** Word-boundary scan of
   results.csv + scripts/ + measurement/ found zero 11-digit `20…` seeds in the whole 2.0e10
   decade (an earlier substring grep false-positived on probe_b, which actually seeds at 1.925e9,
   NOT 1.9e10 — so even Fable's "1.9e10 taken" note was conservative). The decade is clean.
4. **Seed-namespace guard is a FLOOR only** (`assert_clean_eval_seed_range`, eval_provenance.py:379
   — raises only if `seed_start < EVAL_SEED_FLOOR`, no ceiling). The 2.0e10 bands sit far above the
   floor → accepted trivially. No guard change needed.
5. **Optuna 4.8.0 is already in `.venv`** → S0(f) install step is a no-op; the readiness check
   still runs but should pass immediately. Driver runs local-only (laptop never imports optuna).
6. **eval_fair_puct knob wiring (Q3), S2 opponent variant (Q5, keep reuse-OFF), trial-0 tolerance
   (Q6):** left as Fable pre-registered — S0(d) is a blocking smoke that verifies the fair wiring;
   reuse-OFF both sides is the C5/C7 screen convention and matches the fair currency (reuse is a
   no-op in PIMC deploy, CL-044). No changes.

**All six open questions resolved → design is GO for coding.** PRODUCTION.yaml untouched.

**AMENDMENT 2026-07-14 (pre-data, no rankings observed):** rung-A n 40→52 to match the 52-worker capacity (30 local + 22 laptop; at n=40, 12 workers sat idle). One wave either way, ~0 wall-clock cost, tightens rung-A σ ±38→±33. Rung B(120)/C(240), keep-counts (top-10/top-4), and the +30/z≥2.0 gate UNCHANGED.

---

## Premise

Every champion knob was tuned **one axis at a time**: c_puct (Phase 1.1 R-sweeps, interior
plateau at 1.5, re-confirmed by C5-S5), tau_p (C5-S4 τ∈{3,5,8} statistically indistinguishable),
value_norm (C4: vn8 −24.4 / vn30 −36.6, 15 optimal), meeple curve (C5/S1b: clean plateau
×1.25–×1.75, ×1.25 adopted as CL-051), caps (C5: cap5 0.0 / cap12 −13.9 flat; oppcap4 −59.6
pz−2.99 / oppcap12 −66.8 — 8 sharply interior), closure_p (C5: pclose080 +10.4 pz+0.99 /
pclose120 +34.9 but pz+0.17 — a deck-noise-inflated elo, honest read ≈ null). All 1-D-at-a-time,
and three of them were measured **before curve125 landed** — the joint surface around the current
champion has never been sampled. The ONLY things a joint sweep adds are **interaction effects**,
and there are exactly two documented hints:

1. **c_puct × curve** (C5-S5): the curve125 gain attenuates at high c — leaf-Δ(c1.0) +36.6/z1.84,
   leaf-Δ(c1.5) +66.8/z4.59, leaf-Δ(c2.25) +8.7/z1.09 (~1.9σ vs center). Logged in
   C5_CURVE125_PROPOSAL.md as "if c_puct is ever re-tuned, re-check the curve, and vice versa."
2. **closure_p × curve** (untested): pclose120 screened pre-curve125 and never since (the T3
   charter names this explicitly).

**Honest prior (pre-registered): MED-LOW.** Every axis is individually flat-to-mild around the
champion; there is no prior signal of a LARGE interaction pocket, only the two ~1-2σ hints above.
Estimate ~20–25% that Stage 1 fires, ~60% of fires survive the fresh-deck Stage-2 (winner's-curse
attrition), ~50% of those survive fair → **~10% end-to-end adoption probability**. The likely and
fully acceptable outcome is a CONCLUSIVE null: "the champion's knobs are jointly — not just
marginally — locally optimal at the ±tight-range scale." Design is sized cheap accordingly, and
the null is pre-registered to be citable (§9).

## No-touch guarantees

- **`governance/PRODUCTION.yaml` is NOT modified** by any stage. A winner produces a flip-proposal
  doc for Joshua (`T3_OPT_FLIP_PROPOSAL.md`), exactly like C5_CURVE125_PROPOSAL.md. This sweep
  PROPOSES; only Joshua adopts.
- **Zero new LeafConfig fields, zero .pyx changes** — the sweep uses only existing leaf fields
  (`v29_meeple_curve`, `closure_p`, `bonus_cap`, `opp_bonus_cap`), all already accepted by
  `--cand-leaf-json` (`c5_leaf_override.py::_load_cand_leaf_cfg`) and all on the Cython float
  path. **The C7 hash-churn trap does not apply** (no dataclass schema change; frozen hashes
  `7fc930b8…` / production `158f17ff…` cannot move).
- Champion side of every cell = the PRODUCTION.yaml champion verbatim (curve125 env per the
  c7_s1_launcher.sh pattern — NOT the harness's stale curve100 `_CANON_ENV` setdefault; see §5(e)).
- All evidence lands as `experiments/results.csv` rows (`t3_opt_*`) + per-cell `manifest.json`
  with per-side `leaf_cfg` + `leaf_hash`. **Stage-1 trials do NOT write results.csv rows**
  (`--no-results-csv`; 46 harness invocations would flood the table with sub-screen numbers) —
  trials live in `measurement/classical_search/T3_OPTUNA_PROGRESS.tsv` + the study storage +
  per-cell manifests; ONE summary row (`t3_opt_study_s1`) is written at Stage-1 close-out, and
  Stage-2/3 cells write normal rows. Pre-registered here so the omission is a design, not a leak.
- Zero cloud. Local 5900XT + laptop, `nice -n 19`, pre-launch process census, git-bundle sync
  before any two-box run, detached (`setsid`) launches, shared-claim work-stealing.
- k_dets=4 × sims_per_det=688 (CL-054) is **FIXED, out of scope**. exact-K=2 both sides (screen
  convention). Equal sims 2750 both sides (knob changes are compute-neutral — same leaf machinery,
  different constants; per-trial ms-ratio parity gate ∈ [0.9, 1.1] recorded anyway).

---

## 1. THE CENTRAL DESIGN PROBLEM — a noisy argmax converges on the luckiest noise

An optimizer that maximizes a noisy elo objective returns the **luckiest-noise configuration**,
not the strongest — this repo's documented "c=3 +47 elo" false peak, and the results-discipline
rule ("a lone value beating its parameter-neighbors by >1σ is a noise signature"). Noise floor:
unpaired n=100 ≈ ±35 elo 1σ; deck-paired (CRN) ≈ halves it. Calibration used throughout this doc:
**σ_paired(D decks) ≈ 170/√D elo** (matches the house numbers: 50 decks → ±24, 200 decks → ±12).

Five structural defenses, all mandatory:

1. **Objective in the right currency.** Every trial is a deck-paired double-CRN A/B **vs the
   pinned champion sibling on ONE shared band** (`eval_puct_priors.py --candidate puct
   --opponent puct`, seats swapped per deck). The Optuna objective = **`paired_mean_margin`**
   (seat-balanced pts/deck, candidate − champion) — the highest-resolution CRN statistic (elo
   quantizes through W/D/L). All trials share the same decks → deck luck cancels within each
   trial's delta AND correlates out of cross-trial comparisons. Absolute elo is never optimized.
2. **Per-trial power vs trial count — resolved by nested successive halving on the SAME decks.**
   A single trial resolving +35 elo at 2σ needs D = (2·170/35)² ≈ 95 decks (n≈190) — unaffordable
   ×32 trials. So: rung A n=40/trial (20 decks, σ≈38 — RANKING only), rung B n=120 (60 decks,
   σ≈22), rung C n=240 (120 decks, σ≈15.5 — the only rung read against a gate: +30 ≈ 1.9σ,
   +35 ≈ 2.25σ). Rungs are nested extensions of the same cell on the same band (the harness's
   per-seed cache makes an extension replay 0 games). Exact counts + promotion rules in §6.
3. **Sampler: TPE** (`TPESampler(multivariate=True, n_startup_trials=12, seed=20260714)`).
   Justification for ~7 continuous knobs, noisy objective, ~32-trial budget: CMA-ES needs
   population×generations ≥ 60–100 evaluations and degrades badly under σ≈1-effect-size noise
   without resampling; Optuna's GPSampler is sample-efficient but assumes small homoscedastic
   noise (violated at rung-A σ≈38 elo) and integrates poorly with our rung scheme; TPE is robust
   to noise (density-ratio, not surface-fit), handles the mixed/tight box natively, and benefits
   from strictly-sequential trials (§4). TPE only needs to beat random coverage — with 12
   quasi-random startup trials it degrades gracefully TO random coverage in the worst case.
4. **Anti-noise-chasing gate: the Optuna winner is NOT a verdict.** Under the global null, the
   selection cascade (top-10-of-32, then top-4-of-10) hands the "winner" an expected **+10–20 elo
   of selection bias** at rung C (its rung-A/B games are inside the rung-C read: 40 of 240 games
   were selected ON). Therefore: (a) the driver additionally reports the winner's **fresh-slice
   delta** (decks 60–119 only — never used in any promotion decision) as a bias-free diagnostic;
   (b) Stage-2 is a **separate n=400 paired confirm on a FRESH band** of the top-3 (not just
   top-1 — the true best config is as likely #2/#3 as #1 under winner's curse), gate ≥ +25 elo
   AND paired_z ≥ 2.0, exactly the C5/C7 convention; (c) Stage-3 fair confirm before any
   proposal. A winner that doesn't replicate at n=400 on fresh decks is noise — killed, logged.
5. **Anchors inside the study.** Trial 0 (enqueued) = the champion config exactly — by
   construction its games are bit-identical to a no-override run (leaf JSON == champion leaf,
   pinned opponent == candidate) and its delta must read ≈0 (standing in-band mirror). Trial 1
   (enqueued) = curve_scale 1.4-relative (base ×1.75, the known clair-plateau point, expected
   ≈ +11 vs the curve125 champion from the C5-S1b n=400s) — a weak positive/plateau control.

**Pre-registered false-fire estimate:** with the +30/z2.0 rung-C gate on a selection-biased read,
the global-null false-fire probability is ~15–25%; Stage-2 (fresh band, zero selection bias,
n=400) is the instrument that catches it. Passing Stage-1 alone means NOTHING and is worded as
"screen fired, unconfirmed" everywhere.

---

## 2. Parameter space (exact ranges, all anchored at the champion)

Champion values from `governance/PRODUCTION.yaml` (verified 2026-07-14): c_puct=1.5, tau_p=5.0,
value_norm=15.0, final_select=visits, leaf_quantize=float, reuse_tree=true (clair-only),
curve125 = (−10, −5, −1.25, 0, 2.5, 3.75, 5, 6.25), bonus_cap=8.0, opp_bonus_cap=8.0,
closure_p = {1: 0.5, 2: 0.2, 3: 0.05}.

**ONE joint space, 7 continuous knobs** (decision: joint, NOT search-first-then-leaf — the only
two documented interaction hints are CROSS-group (c×curve, pclose×curve), which sequential groups
structurally cannot see; and cross-group interactions are this sweep's entire EV):

| # | Knob | Champion | Range (suggest) | Rounding | Anchor evidence for the tightness |
|---|---|---|---|---|---|
| 1 | `c_puct` | 1.5 | uniform **[1.0, 2.25]** | 2 dp | R-sweep interior plateau; S5 wings c1.0/c2.25 both attenuate the curve gain — the range spans exactly the measured bracket |
| 2 | `tau_p` | 5.0 | log-uniform **[3.0, 8.0]** | 2 dp | S4 bracket {3,8} flat; τ=2 known-bad (~−38); don't leave the measured-safe interval |
| 3 | `value_norm` | 15.0 | log-uniform **[10.0, 22.0]** | 2 dp | C4 wings {8, 30} both negative; stay well inside them |
| 4 | `curve_scale` (× champion curve125, per-entry) | 1.0 | uniform **[0.8, 1.45]** | 3 dp | = base ×1.0–×1.81; S1b: base×1.0 ≡ −66.8 rel, plateau ×1.25–1.75, ×2.0 falloff — range covers the full plateau + a shade past |
| 5 | `pclose_scale` (× {0.5, 0.2, 0.05}) | 1.0 | uniform **[0.8, 1.3]** | 3 dp | pclose080/pclose120 wings mild/noisy; the ONLY axis never re-tested post-curve125 (T3 charter) |
| 6 | `bonus_cap` | 8.0 | uniform **[5.0, 12.0]** | 2 dp | C5 cap axis flat across exactly this bracket — flatness means the joint optimum could sit anywhere in it |
| 7 | `opp_bonus_cap` | 8.0 | uniform **[6.5, 10.0]** | 2 dp | C5 wings at 4/12 the WORST cells (−59.6 pz−2.99 / −66.8) → sharply interior optimum; tight range only |

**FIXED (pre-registered, not swept):** `final_select=visits` and `leaf_quantize=float` (both
confirmed champion choices; two categoricals would cost more trials than their reopen-value);
`root_select=puct` (Gumbel is closed Track-C1 territory); `c_lcb` (inert unless lcb);
`reuse_tree=OFF both sides` — the C5/C7 screen convention, AND the deployable currency is fair
PIMC where reuse is structurally a no-op (`FairHeuristicPriorAgent` has no reuse; CL-044) — so
sweeping under reuse-OFF matches the currency that matters. Caveat pre-registered: a knob optimum
under reuse-OFF could shift under reuse-ON clairvoyant dev play; not this sweep's problem.
`sims=2750` equal both sides; `exact_k=2`; `k_dets/sims_per_det` (CL-054, out of scope).
**Excluded axes:** `bag_close` (3× dead), v2.8/v2.9 object-path terms (30× cost), C7 term k's
(inherited from DEFAULT_CONFIG whatever C7 decides — NOT re-swept here), `closure_p` shape
(scale only — shape changes are a term-shape wave, T2's turf).

**Emission rules (driver):** at scale==1.0 emit the champion list/dict VERBATIM (no float-repr
drift → trial-0's leaf hash must equal the champion hash exactly). Rounded values ARE the trial
(recorded in manifest/TSV before play). Leaf JSON per trial:
`{"v29_meeple_curve": [...], "closure_p": {"1": ..., "2": ..., "3": ...}, "bonus_cap": ...,
"opp_bonus_cap": ...}` — replace-fields on env DEFAULT_CONFIG, everything else inherited.

---

## 3. Knob → CLI map (verified against `eval_puct_priors.py` @ HEAD; what Opus must add)

| Knob | CLI today | Candidate-only? | Sweep status |
|---|---|---|---|
| c_puct | `--c-puct` | ❌ **LEAKS to the opponent** — `_champ_puct_cfg(shared)` copies `c_puct` from the candidate (line ~261) | **NEEDS Stage-0 plumbing** |
| tau_p | `--tau-p` | ❌ same leak | **NEEDS Stage-0 plumbing** |
| leaf_quantize | `--leaf-quantize` | ❌ same leak | fixed at champion `float` → leak harmless, but pin anyway |
| value_norm | `--value-norm` | ✅ (opponent pinned `CHAMP_PUCT_VALUE_NORM=15`) | ready |
| final_select | `--final-select` | ✅ (opponent pinned `visits`) | FIXED, not swept |
| curve / closure_p / caps | `--cand-leaf-json` | ✅ (champion side always env DEFAULT_CONFIG) | ready — all 4 fields already parse+coerce in `_load_cand_leaf_cfg`, all cy-float-path (`_assert_cy_float_path` passes by construction) |
| reuse_tree | `--reuse-tree` / `--opp-reuse-tree` | ✅ each side | FIXED OFF both sides |
| sims / exact_k / paired / band | `--cand-sims/--exact-k/--paired/--seed-start` | n/a | fixed 2750 / 2 / on / §6 band |

**⚠️ THE SHARED-AXIS LEAK IS THE ONE REAL HARNESS TRAP (orchestrator-confirmed 2026-07-14).**
Today, `--opponent puct` builds the champion sibling with the CANDIDATE's c_puct/tau_p/
leaf_quantize ("shared axes" — correct for C2–C7, which never swept those). A joint sweep that
moves `--c-puct` would silently move BOTH sides → the A/B measures nothing. **Stage-0 plumbing
(Opus):**

1. `eval_puct_priors.py`: add `--opp-pin-champion` (default OFF = byte-identical legacy).
   When set (requires `--opponent puct`): the opponent sibling takes module constants
   `CHAMP_PUCT_C_PUCT=1.5`, `CHAMP_PUCT_TAU_P=5.0`, `CHAMP_PUCT_LEAF_QUANTIZE="float"` instead of
   the candidate's shared dict (opponent sims stays = cand_sims; every other pinned knob
   unchanged). Manifest opponent block records `"pinned_champion_knobs": true` + the resolved
   values. Extend `_variant_sig` (or the cand token in `_cell_tag`) to append `-c{c_puct:g}` /
   `-tp{tau_p:g}` when pinning is on and the value differs from champion, so auto-tagged cells
   can never collide (the driver always passes explicit `--out-subdir`/`--exp-id`, this is
   defense-in-depth).
2. `scripts/classical_search/optuna_knob_sweep.py` — the driver (§4).
3. `scripts/classical_search/optuna_knob_helper.sh` — the laptop helper loop (§4).
4. `eval_fair_puct.py`: flags `--c-puct/--tau-p/--value-norm/--final-select/--leaf-quantize/
   --cand-leaf-json` already exist (verified lines 736–750) — Stage-0(d) verifies they actually
   reach the fair candidate agent's `HeuristicPriorConfig` (they should; assert in a smoke).
   No new fair-side flags expected.

---

## 4. Optimizer mechanics, storage, and the two-box pattern

- **Strictly sequential trials, ONE driver, game-level (not trial-level) parallelism.** The May
  precedent (`scripts/optuna_eval_search.py`) ran per-box Optuna workers against a shared SQLite
  study on the CIFS share. REJECTED here: (a) SQLite-over-CIFS locking is corruption-prone;
  (b) trial-level parallelism halves the information TPE has at each suggestion; (c) the harness
  ALREADY spreads one cell across both boxes via `--shared-claim` (the C5/C7/kdets pattern) —
  strictly-sequential trials + two-box game fan-out gives full-information TPE at identical
  hardware utilization, deterministic and auditable.
- **Storage:** `optuna.storages.RDBStorage` on **LOCAL disk**:
  `sqlite:////home/doctor/projects/carcassone/data/classical_search/t3_optuna/study.db`
  (never the CIFS share). Human-readable journal: one TSV row per (trial, rung) appended to
  `measurement/classical_search/T3_OPTUNA_PROGRESS.tsv` (git-tracked, the C7 PROGRESS pattern):
  `trial  rung  params_json  n  W/D/L  elo  sigma  paired_margin  paired_z  ms_ratio  secs  ts`.
  Per-trial `RUNGS.json` under the study dir records promotions. Resume: driver restart reloads
  the study (completed trials intact); the harness's per-seed cache makes any half-played cell
  resume for free; a re-seeded TPE after resume won't replay the identical suggestion stream —
  accepted and noted (trials already played are unaffected).
- **Optuna trial value = the rung-A objective only** (uniform fidelity → unbiased TPE
  comparisons). Rung-B/C extensions and promotions are DRIVER logic reading `summary.json`, not
  Optuna pruners. Optuna's ASHA/Hyperband pruners were considered and REJECTED: asynchronous
  promotion is arrival-order-dependent (non-reproducible) and buys nothing over a deterministic
  batch schedule when trials are sequential anyway. **Consequence (pre-registered):
  `study.best_trial` is NOT the sweep verdict — the rung-C table in the TSV is.**
- **Two-box execution:** driver runs LOCAL (primary, W≈30), aggregates, owns the TSV. Before each
  harness invocation it atomically writes `<share>/classical_search/t3_optuna/CURRENT_CELL.json`
  = the exact harness argv + target n; the laptop helper loop polls it, joins the same cell with
  `--workers 22 --shared-claim --no-results-csv`, and idles when the pointer is stale or reads
  `{"status": "done"}`. Both invocations use the c7 launcher's iterate-until-count-reached +
  `clean_stale_claims` loop. Net-free CPU cells: W≈30 local / W≈22 laptop, `nice -n 19`, setsid,
  census first, git-bundle sync + `OPENBLAS_NUM_THREADS=1` (already pinned in both harnesses).
- **Trial hygiene:** a trial with `game_timeouts` > 2% of games or missing decks after one
  re-invoke is flagged UNRELIABLE and excluded from promotion (logged in TSV). Expected ~0 at K=2.

**Seed bands (orchestrator-verified FREE 2026-07-14):** the 2.00e10 decade — no 11-digit `20…`
seed anywhere in results.csv/scripts/measurement; the seed guard is floor-only so it accepts them:
- **S0 smoke = 2.009e10** · **S1 = 2.00e10** (one band, ALL trials, CRN; consumes seeds
  20,000,000,000..+119) · **S2 confirm = 2.01e10** · **S3 fair = 2.02e10** · **S2b attribution =
  2.03e10**. Re-verify at launch (house discipline); Stage-0's first harness call also checks
  `ep.assert_clean_eval_seed_range` acceptance.

---

## 5. Stage 0 — plumbing + readiness gates (blocking; GO/NO-GO)

~2–4 h dev (no leaf code, no .pyx) + ~1 box-h smoke. All parts must pass before S1.

- **(a) Pin-flag mirror (the leak fix proof).** n=20 @ 2.009e10, candidate at champion knobs +
  full champion leaf JSON + `--opp-pin-champion`: games **bit-identical** to the same run without
  the flag and without the JSON (hash the per-seed jsons), elo 0, paired Δ 0. Then n=20 with
  candidate `--c-puct 2.0` pinned: manifest shows cand c2.0 / opp c1.5 (and the SAME run UNpinned
  shows opp c2.0 — the leak, demonstrated once for the record); games differ from mirror.
  Plus one pytest: pinned opponent cfg == champion constants whenever candidate knobs differ.
- **(b) Driver micro-study.** 3 trials × n=8 @ 2.009e10 (enqueued: champion, curve1.4rel, 1 TPE):
  study.db rows + TSV rows + per-cell manifests correct (per-side leaf_cfg/leaf_hash present);
  kill the driver mid-trial-2 and restart → no duplicate suggestion damage, cached games reused,
  cell completes. Helper loop smoke: laptop joins trial-3's cell via CURRENT_CELL.json and
  contributes ≥1 game.
- **(c) Emission exactness.** Unit tests: curve_scale=1.0 / pclose_scale=1.0 / caps=8.0 emit the
  champion leaf verbatim → `_leaf_hash(cand)` == `_leaf_hash(DEFAULT_CONFIG)`; scale≠1 hashes
  differ; closure_p keys survive the str→int coercion round-trip.
- **(d) Fair-side knob wiring.** `eval_fair_puct.py --smoke` with `--c-puct 2.0 --tau-p 4
  --value-norm 12` + a non-champion leaf JSON: assert the fair candidate agent's resolved
  `HeuristicPriorConfig` carries all four (read off the manifest). This clears the Stage-3 path
  early (it's the one piece of plumbing this design assumes rather than verified line-by-line).
- **(e) Env/provenance gate.** The launcher exports the curve125 champion env (c7_s1_launcher.sh
  lines 80–83 verbatim — the harness `_CANON_ENV` still setdefaults the OLD curve100, so a missing
  export silently runs the WRONG champion side). Proof: any S0 manifest must show
  `champ_leaf_hash == a36d2e15a3b3d71d` (the curve125 eval-manifest hash). **⚠️ CORRECTION
  (orchestrator + Opus, 2026-07-14):** the design originally cited `96d2c075f85e9583` here — that
  was a STALE mis-citation from the C5 proposal prose; the actual current-code eval-manifest hash
  for curve125 is `a36d2e15a3b3d71d`, ground-truthed against every real C7 curve125 manifest
  (`/mnt/c/carc-shared/classical_search/c7_s1_*/manifest.json`, all show champ_leaf_hash a36d2e15)
  + direct HEAD computation. curve100 = `42af12fce22e1a0f` (distinct → the gate still discriminates
  the wrong-champion trap). Hard-coded as `EXPECTED_CHAMP_LEAF_HASH` in the driver + pytest. C7
  adopted nothing (CL-055), so curve125 stands as the baseline.
- **(f) Optuna availability.** ✅ Already satisfied — `.venv` has optuna 4.8.0 (orchestrator
  verified 2026-07-14). The check runs and passes; no install. Driver runs local-only; the laptop
  never imports optuna.

GO = all six clean. Any failure = NO-GO, fix before compute.

---

## 6. Stage 1 — Optuna screen (clairvoyant, CRN successive halving, 32 trials, ≈38 box-h)

**Consumer (identical to C5/C7 cells):** candidate PUCT@2750 vs **pinned champion sibling**
PUCT@2750 (`--candidate puct --opponent puct --opp-pin-champion`), champion side c1.5/τ5/float/
visits/vn15/reuse-OFF + env curve125 leaf; candidate = trial knobs via CLI + `--cand-leaf-json`;
reuse OFF both sides; exact-K=2 both sides; deck-paired; band **2.00e10** for every trial (CRN).
Out-dirs `<share>/classical_search/t3_optuna/t###`; exp_id `t3_opt_t###` (TSV only, no
results.csv rows per §"No-touch").

**Schedule (deterministic, pre-registered):**

| Rung | Who | n/trial (decks) | σ_paired | New games | box-h |
|---|---|---|---|---|---|
| A | all 32 trials (2 enqueued anchors + 10 QMC startup + 20 TPE) | 40 (20) | ±38 elo | 1280 | 19.2 |
| B | top 10 of 32 by rung-A `paired_mean_margin` | extend to 120 (60) | ±22 elo | 800 | 12.0 |
| C | top 4 of 10 by rung-B margin | extend to 240 (120) | ±15.5 elo | 480 | 7.2 |

Totals: 2560 games ≈ **38.4 box-h ≈ ~19 h two-box wall** (C5 calibration: n=100 s2750 K=2 cell =
2425–3002 s two-box; ~6 s/move/side; +~1.5 h for 46 invocation overheads) — one long two-box
day/overnight. Anchor sanity reads (non-gates): trial-0 (champion) rung-A |Δ| within 2σ of 0;
if trial-0 lands outside ±2σ, STOP and investigate the harness before believing anything else.

**Stage-1 verdict read (rung C, best trial):**
- **FIRE** = paired Δelo ≥ **+30** AND paired_z ≥ **2.0** at n=240. Also report (diagnostic, not
  a gate): the winner's fresh-slice delta (decks 60–119 only, the never-selected-on slice) — a
  fresh-slice ≤ 0 alongside a full-read fire is the noise signature; note it in the row and let
  Stage-2 arbitrate.
- **NULL** = anything less → STOP. No Stage 2. Write the close-out (§9). Expected-likely outcome.
- **Coherence note:** if the top-4 rung-C configs cluster in one knob region, say so in the
  close-out (it strengthens a fire and makes a Stage-2 pass more credible); a top-4 scattered
  across the box with one lone spike is the classic noise picture.

## 7. Stage 2 — fresh-band clair CONFIRM (top-3, n=400 each) + S2b attribution

- **S2 (fires only if Stage-1 fires):** the **top-3** rung-C configs (winner's-curse insurance —
  the true best is as likely #2/#3), each n=400 paired (200 decks) on FRESH band **2.01e10**,
  same consumer, exp_ids `t3_opt_s2_top{1,2,3}_n400`, normal results.csv rows. σ ≈ ±12 elo.
  **Gate per config: ≥ +25 elo AND paired_z ≥ 2.0.** None pass → the Stage-1 fire was selection
  noise → NULL-after-fire close-out (log the S1 winner as a noise spike, exactly the C5 kill
  wording). ≈ 6 box-h/cell → 18 box-h.
- **Adoption candidate = the best S2 passer** (NOT the best S1 trial).
- **S2b (conditional attribution, diagnostic):** decompose the S2 winner into (i) search-knobs-
  only (leaf = champion) and (ii) leaf-knobs-only (search = champion), n=200 each @ 2.03e10
  (`t3_opt_s2b_searchonly_n200` / `t3_opt_s2b_leafonly_n200`, ≈6 box-h). Reads: winner ≈
  (i)+(ii) → additive marginals (suspicious given flat 1-D priors — re-examine); winner ≫
  (i)+(ii) → a genuine interaction (the thing this sweep exists to find; say which axes moved).
  Feeds the proposal doc; also arms the §8 contingency.

## 8. Stage 3 — FAIR confirm (mandatory before any proposal; the CL-051/CL-054 template)

Clair-only wins are graded clair-only (CL-044/CL-048 rule) — no proposal on clair evidence.

- **Transfer prior (argued, pre-registered):** leaf knobs transfer by construction (same
  LeafConfig in every PIMC determinization — the C7 argument). Search knobs (c_puct/tau_p/
  value_norm) are **agent-internal** — they act inside each determinization's PUCT search, with
  NO deck-exploiting mechanism (unlike reuse_tree, whose +39 amortized the fixed true deck and
  died fair). The one honest attenuator: fair builds k4 × 688-sim trees, not one 2752-sim tree —
  exploration-knob optima are budget-dependent, so expect attenuation, not sign-flip.
  Net: MED transfer prior, better for leaf-dominant winners.
- **Protocol:** two FRESH arms @ band 2.02e10, **450 paired decks each** (n=900/arm; the C7/CL-051
  sizing — n=200 was underpowered there), read ONCE at completion (no optional stopping):
  candidate arm = `eval_fair_puct.py`, FairHeuristicPriorAgent **k_dets=4 × sims=688** (CL-054,
  fixed) with the winner's search knobs + winner leaf JSON; baseline arm = identical champion
  config (champion leaf via explicit `--cand-leaf-json`, the kdets config-B pattern), same
  decks/seats; both vs the FROZEN clairvoyant h800 curve100 rung (leaf_hash 4f2a93e7 — the ruler
  must not move).
- **Ruler-reproduction sanity gate (blocking):** baseline arm within 2σ of the CL-054 k4 confirm
  anchor (**+136.0 ± 18.7 vs h800**, results.csv `kdets_k4x688_..._confirm`). Fail → the ruler
  moved; STOP, investigate, do not read the delta. **⚠️ Re-baseline caveat (CL-056):** the PIMC
  deck-sort fairness fix (249f5b9) changed the fair agent AFTER the +136 anchor was measured —
  the baseline arm re-establishes the fair baseline on the FIXED agent; if it lands outside the
  old ±18.7 that may be the fix, not a bug. Read the fresh baseline arm as truth; the +136 is a
  loose sanity band, not an exact target.
- **Verdict = deck-matched CRN delta** candidate-vs-baseline (crn_delta tooling), rows
  `t3_opt_s3_fair_*`. ≈ 10–12 box-h.

---

## 9. Pre-registered decision tree

- **S0 NO-GO:** any §5 gate fails → fix before compute; no partial launches.
- **S1 NULL** (best rung-C < +30 elo OR paired_z < 2.0): verdict — **"T3 CLOSED (null): within
  ±(§2 ranges) of the champion, the joint knob surface contains no ≥+30-elo pocket at 120-deck
  power; the two interaction hints (c×curve, pclose×curve) did not materialize; the champion's
  knobs are jointly locally optimal at this scale."** Six-touch close-out; T3 off the shortlist.
  Explicitly NOT claimed: anything about <+25-elo fine structure (unresolvable at this budget) or
  regions outside the tight box. No re-dose, no "10 more trials" — a bigger sweep needs a new
  premise and a new doc.
- **S2 kill** (no top-3 config ≥ +25 / z ≥ 2.0 at n=400 fresh): verdict — "S1 fire was
  selection noise" (the failure mode §1 exists for; say so verbatim in the row). CLOSED (null).
- **S2 pass → S3 gates (read once at 450 paired decks):**
  - **PASS** = win-paired Δ ≥ +35 elo with z ≥ 2.0 **AND** margin CRN Δ > 0 pts/deck with
    z ≥ 2.0 (both parts) → write `T3_OPT_FLIP_PROPOSAL.md` (exact PRODUCTION.yaml diff; leaf-name
    bump only if leaf knobs moved, hash recomputed via the frozen recipe, never pasted from
    manifests); **Joshua decides.**
  - **KILL** = margin Δ ≤ 0 → if the S2b decomposition was search-dominant: grade **CLAIR-ONLY /
    budget-mismatch** (tuned for 2752-sim trees, doesn't survive 688/det; the CL-044 grading),
    record as a dev/clair-ruler config only, do NOT propose. **Contingency (pre-registered):** if
    S2b's leaf-only cell was independently positive (≥ +25/z ≥ 1.5 at n=200), that leaf-only
    config MAY be promoted to its own S3 (one extra fair run, ~11 box-h) before closing — leaf
    knobs have no clair-only excuse, so a leaf-only fair test is decisive either way.
  - **POSITIVE-UNRESOLVED** = Δ > 0, z < 2.0 → present to Joshua with the exact power math
    (σ ≈ 18 pts/deck; n needed for the observed Δ at z=2); extend-or-stop is his call. Not a
    pass; nothing proposed on it.
- **Never:** adopt on Stage-1/Stage-2 evidence; touch PRODUCTION.yaml; re-read a completed stage
  with a different threshold.

## 10. Budget summary

| Stage | Cells / games | box-h |
|---|---|---|
| 0 plumbing + gates | smokes | ~1 (+2–4 h dev) |
| 1 Optuna screen | 32 trials, 2560 games (rungs 40/120/240) | ~38.5 |
| 2 confirm | ≤3 × n=400 | ≤18 |
| 2b attribution | ≤2 × n=200 | ≤6 |
| 3 fair | 2 arms × 450 paired decks | ~10–12 |
| **Total** | **null-case ≈ 40 box-h ≈ 2.0 box-days (matches the T3 charter "~2 box-days"); full-fire worst case ≈ 74 box-h ≈ 3.7 box-days** | |

Two-box: null ≈ one long day/overnight (~19 h wall); worst case ≈ 2 days. NOTE (honest): unlike
C5/C7, the NULL case here costs the FULL Stage-1 — there is no cheap early exit from a joint
sweep. Hard cap (pre-registered): if Stage-1 exceeds 50 box-h (stalls/timeouts), stop, read what
is complete, close out on it.

## 11. Risks / what could make this a dead end (pre-registered honesty)

1. **The likely outcome is null (~75–80%).** Every axis individually flat; the two interaction
   hints are 1–2σ. This is interaction-insurance priced accordingly — the null is designed to be
   conclusive and citable, and it retires T3 permanently.
2. **Winner's curse survives the defenses in attenuated form** — quantified in §1/§6; Stage-2
   fresh-band n=400 is the backstop; the residual risk is a ~15–25% wasted-S2 (18 box-h) branch.
3. **32 trials cannot map 7-D.** The design finds LARGE coherent pockets only; a narrow ridge
   (e.g. a c×τ trade-off line) can be missed. Accepted: a pocket too small for 32 tight-range
   trials is also too small to matter at our noise floors.
4. **TPE partially fits rung-A noise** (σ≈38 vs expected effects ≤35) — accepted; with CRN decks
   + 12 quasi-random startup trials it lower-bounds at random coverage, and verdicts never rest
   on the sampler's opinion.
5. **Champion drift:** RESOLVED — C7 closed null (CL-055), champion = curve125 at launch; §5(e)
   anchors the hash. If anything ELSE changes the champion mid-sweep, STOP and rebase (a moved
   baseline invalidates CRN comparability across trials).
6. **Fair budget-mismatch** (2752-sim clair trees vs 4×688 fair trees) is the main S3 attrition
   mechanism for search-knob winners — pre-graded in §8/§9, with the leaf-only contingency.
7. **Opportunity cost:** ~2 box-days against a MED-LOW prior; E4 remains the standing NEXT — this
   fills box-idle time, it does not preempt anything Joshua has queued.

## 12. Build order (engineer runbook)

1. `--opp-pin-champion` in `eval_puct_priors.py` (+ constants, manifest fields, tag suffix,
   pytest for the pin + the leak-demo test). Commit.
2. Driver `scripts/classical_search/optuna_knob_sweep.py`: space (§2, incl. emission-exactness
   rules), TPE config (§4), rung schedule (§6), CURRENT_CELL.json protocol, TSV/RUNGS.json
   journaling, resume, `--dry-run` (prints all 32-cell argv without compute). Commit.
3. Helper `scripts/classical_search/optuna_knob_helper.sh` (laptop; c7-launcher loop skeleton).
   Commit.
4. Stage-0 gates (§5 a–f), including the eval_fair_puct wiring check. Git-bundle sync laptop
   (code only — no .so rebuild needed, no leaf changes). Run S0. Commit results.
5. Launch S1 (band verified free by the orchestrator first; census both boxes; ETA stated in
   chat; setsid + nice -n 19). Dev estimate 1–8: **~0.5–1 day** (no Cython, no LeafConfig).

## Close-out checklist (six touches, one sitting — per CLAUDE.md)

results.csv rows (`t3_opt_*`: the study summary row + any S2/S2b/S3 rows) → DECISIONS.md index
line → status stamp on THIS doc → governance CLAIM_REGISTRY row (fire or null both get one) →
STATUS.md top block → roadmap/backlog T3 line (FIRED / CLOSED-null). Then
`python3 scripts/doc_lint.py`.
