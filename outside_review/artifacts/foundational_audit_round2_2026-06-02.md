# Foundational audit — ROUND 2 (2026-06-02, 6-agent re-sweep)

Re-run of the morning's foundational audit ([foundational_audit_2026-06-02.md](foundational_audit_2026-06-02.md))
after Phase 0 + Stage A3 + the iter-9 code review, to catch what the first sweep MISSED.
6 read-only agents (engine / MCTS / representation / training-pipeline / **eval-methodology** /
completeness-critic). Ran alongside the Stage-A2 sweep (read-only, no interference).

**Headline:** the first audit was strong on *correctness* and *representation* but BLIND to three
whole areas — **(1) measurement methodology, (2) the training recipe (LR/loss weighting), and
(3) whether Stage B's planned mechanism actually exists in code.** Several findings directly affect
what we do next; one is strategic (the measurement wall). Numbering continues as G-* (gaps) to avoid
colliding with F-* from round 1.

One round-1-adjacent claim was investigated and REJECTED (see bottom).

---

## TIER M — Measurement methodology (highest leverage; the project's #1 blocker, under-audited in round 1)

### G-M1 [CRITICAL] The +25.2 elo re-baseline is NOT statistically significant — and the n-doctrine is wrong
- +25.2 elo = wr 0.536; at n=400 σ_wr=0.0249 → **z=1.45, one-sided p≈0.074**. Below the 2σ bar.
  The re-baseline didn't show "iter_11 = +25 elo"; it showed **iter_11 is statistically
  indistinguishable from the heuristic at n=400/sims=200.**
- **The CLAUDE.md / EXPERIMENTS doctrine "n=400 is a verdict (±9 elo)" is FICTION.** Near wr=0.5,
  σ at n=400 is **±17.4 elo**, not ±9; ±9 needs n≈1500. n=400 is a verdict only for effects ≥~50 elo.
- **Action:** (a) fix the doctrine in CLAUDE.md + EXPERIMENTS (state the real σ(n) curve); (b) re-frame
  the re-baseline as "iter_11 ≈ heuristic (inconclusive)", consistent with the audit thesis anyway;
  (c) size n to the effect we expect, or raise the effect (margin-based estimator G-M8, or pairing G-M2).

### G-M2 [HIGH] Eval does not PAIR decks across colors → first-player advantage uncancelled, variance inflated
- Deck is a pure function of seed. Both eval scripts set `net_player = i%2`, `seed = seed_start+i` →
  net-as-p0 uses EVEN seeds, net-as-p1 uses ODD seeds → **disjoint deck sets per color.** Colors are
  balanced in COUNT but not PAIRED. First-player advantage is averaged over different decks instead of
  cancelled within a deck.
- **Fix (cheap, high-value):** for each base seed play the SAME deck twice with colors swapped
  (`(seed,0)` and `(seed,1)`); tally as matched pairs. Cancels FP advantage exactly + ~halves variance
  → directly mitigates G-M1's power problem at no extra games. `_result_path` already keys on
  `(seed,player)` so the two orientations don't collide.

### G-M6 [HIGH, latent→active] Self-play vs eval seed collision at iter ≳ 60
- Self-play seed = `iter*10_000 + game_idx` from `--seed-start 0`; eval floors are 600k (ladder),
  700k (verify), 800k (anchor-gate), 900k (confirm). At **iter ≥ 60** self-play seeds reach the ladder
  band → the net is evaluated on decks it TRAINED on (train/test contamination, inflates wr). The
  strength-push loop is designed to run many iters → **will** trigger.
- **Fix (cheap, do before the loop climbs past ~iter 50):** move eval floors to 10^9, or namespace
  self-play vs eval seeds by disjoint high bits.

### G-M3 [MED] manifest.json is mandated (CLAUDE.md) but never written or read — zero implementing code
- Config provenance is dirname archaeology; the dirname omits checkpoint identity, leaf variant/cap/blend,
  fair_chance, orchestrator. This is exactly the failure class the rule was meant to prevent (the
  2026-05-28 c=3 noise-spike false production change). **Fix:** dump a manifest (resolved args + ckpt
  sha + git commit + per-side leaf cfg) per eval dir; have the aggregator read it.

### G-M4 [MED] Gate runs c_puct=1.5; ladder runs c=3.0 → gate and ladder measure DIFFERENT agents
- `run_pathb_cluster_loop.sh` gates at `--c-puct 1.5`; the ladder + production default is c=3.0
  (DECISIONS: +47 elo). A checkpoint can win the gate and lose at the ladder's c. **Fix:** pin one
  c_puct across self-play/gate/ladder, or re-confirm adopted checkpoints at the ladder's c.

### G-M5 [MED] n=40 gate ratchets `best_wr` on noise (max-selection bias)
- Adopting "best" on any n=40 `gate_wr > best_wr` inflates best_wr under pure noise (E[max] ≈ 0.62 over
  ~10 true-50% iters) → biases toward premature plateau-stop + never adopting equal/slightly-better iters.
  **Fix:** require ≥1σ improvement at n=40 before adopting, or hold best at a verdict-grade fixed ref.

### G-M7 [LOW] ±800 elo clamp fires silently on n=40 sweeps (score 0/1 → ±800, σ=NaN). Warn + never promote.
### G-M8 [LOW→leverage] Score-margin (`avg_diff`) is collected but unused. A margin effect-size is lower-variance than win/draw/loss → fewer games for the same power. Report it alongside elo (helps G-M1).

**Verified SOUND (trust):** elo formula + σ delta-method (reproduces the 17.4), W/L/D tally, color
COUNT balance, deck determinism (paired WITHIN a game), clairvoyance is symmetric in eval (fair A/B —
but absolute number is *clairvoyant* strength, won't transfer 1:1 to a non-clairvoyant human),
HeuristicMCTS reference is fixed/reproducible (won't drift).

---

## TIER G — Training recipe (entirely un-audited in round 1)

### G-T1 [HIGH] `train_iter.py` has NO learning-rate schedule (flat lr=1e-3 × 3 epochs)
- `train_warmstart.py` uses `CosineAnnealingLR`; the live RL trainer `train_iter.py:329` creates AdamW
  with no scheduler and never steps one. Misses the low-LR refinement phase; some of the "chain
  random-walk" blamed on the gate (F-C3) is likely optimization noise. **Fix:** add cosine (warmup+decay),
  or drop default lr to ~3e-4 for 3-epoch fine-tune. Add the knob in Stage A; sweep in the Stage-B loop.

### G-T2 [HIGH] Value loss is starved 5–10× by unweighted summation — and score_diff_wide makes it WORSE
- `loss = pol_loss + val_loss + aux_weight*own_loss` (train_iter.py:365). Policy CE over 2511 actions is
  O(2–6); value MSE on a tanh target is O(0.1–1) → **policy dominates the gradient ~5–10×.** The value
  head — the exact thing Stage B wants to make load-bearing — is trained as an afterthought. C6's
  de-saturation (/40) SHRINKS value-target magnitude → shrinks value-loss → starves it further.
- **Why it matters:** you could conclude "value-in-loop doesn't beat the leaf" (the Stage-B gate) on a
  loss-weighting artifact and kill Stage C for a non-science reason. **Fix:** add a value-loss
  coefficient (sweep 1–5×), re-introduce when switching to score_diff_wide. Genuine missing axis (F-C2
  was about the target, not the loss weight).

### G-T3 [MED] Warmstart value-currency mismatch: `warmstart.py` hardcodes tanh/15; Stage-B score_diff_wide=/40
- Any `--warmstart-mix-fraction > 0` at Stage B would mix /15 and /40 targets in one MSE. Currently
  mix=0 (latent). **Fix:** parameterize the warmstart value scale to match `--value-target`, or guard.

---

## TIER S — Stage-B / plan readiness (round 1 assumed the plan was buildable; it's partly not)

### G-S1 [CRITICAL for Stage B] The "value_blend ramp" is partly vaporware + wired to the wrong path
- The plan's Stage-B mechanism ("`leaf_eval=nn` with value_blend ramped low→high") does NOT exist as one
  knob: `value_blend` is applied ONLY inside the v2.5 leaf wrapper (`evaluators.py`), reached only when
  `leaf_eval=v2_5`. Setting `--leaf-eval nn` BYPASSES the blend → jumps straight to 100% net value →
  the known −800 calibration cliff. The real on-ramp is `--leaf-eval v2_5` + scheduled
  `CARCASSONNE_V25_VALUE_BLEND`. **There is no ramp scheduler** (no iter-indexed blend anywhere).
- **Latent guard bug:** the policy-only fast-path gates on `DEFAULT_CONFIG.value_blend == 0.0`
  (import-time default), not the env-resolved `eff_cfg.value_blend` → if blend is set via env,
  `use_policy_only` can be True → value head never computed → blend multiplies a stub.
- **Fix BEFORE Stage B:** ramp via `leaf_eval=v2_5` + a scheduled blend (0.1→0.3→0.6→1.0 across iters)
  added to the loop; fix the guard to read the env-resolved blend; smoke-assert the value head runs when
  blend>0. Otherwise Stage B fails for a wiring reason and we wrongly kill Stage C.

### G-S2 [HIGH] No base-only bug-fixed warmstart corpus — hidden A2→regen→B dependency
- All warmstart data on disk is April River-era, pre-farm-fix, 85-tile. Stage-B "warmstart from scratch
  base-only" needs a ~100K-position regen on the FIXED base-only game with the FINAL v2.7 cap — i.e.
  gated on the A2 cap verdict (the heuristic IS the v2.7 leaf). Not in the build spec's task list.
- **Fix:** add "regenerate warmstart corpus (base-only + fixed scoring + final cap)" as Stage-B step 0,
  sequenced after A2's cap verdict; state ETA + pick boxes (multi-hour run).

### G-S3 [HIGH] C7 conditional gate references the IN-LINEAGE iter_11 — the anchor-lies trap, rebuilt
- Even after the "20-line" warm-from-best change, the gate ref is iter_11 (`$WARM`), which is in the
  training lineage and now ≈ the heuristic. The `anchor_before_scaling` 2026-06-02 corollary says a fixed
  same-lineage anchor LIES. **Fix:** gate against HeuristicMCTS (out-of-lineage), AND wire warm_from=best.

### G-S4 [MED] A→B→C re-invalidates the A2 c_puct/FPU sweep (running NOW)
- A2 sweeps c_puct/FPU against the v2.7 leaf; Stage B changes the leaf (net value) + value currency →
  c_puct/FPU optima move (project's own `bug_fix_shifts_optima` rule). The **cap** sweep is leaf-specific
  and DURABLE; the **c_puct/FPU** half is "v2.7-ladder reference only, re-do at Stage B." FPU is the
  sharpest: q=0 is ~fine for the narrow v2.7 band, badly mis-scaled for raw net value. **Action:** scope
  the A2 c_puct/FPU result as v2.7-ladder-only; fix FPU before Stage B; budget a c_puct/FPU re-sweep
  inside Stage B. (Cap sweep stays valid → the running sweep is NOT wasted.)

---

## TIER R — Representation / misc (smaller)

### G-R1 [LOW] `progress` scalar (idx 9) = 1 − `tiles_remaining` scalar (idx 5) EXACTLY (both use 72) → one wasted scalar input. Drop at next clean retrain (width change → checkpoint-shape boundary, like D1/D13).
### G-R2 [LOW] `chapel_or_flowers_points` indexes `board[row][col]` with no bounds check → negative-index wrap near grid edge. Latent (6-row margin). Add a guard.

---

## STRATEGIC — the measurement wall (not an F- or G- bug; the deepest gap)

The goal is "beat the world champion," but there is **no above-amateur reference anywhere in the repo**
(no human corpus, no external engine bridge, only HeuristicMCTS ≈ strong-amateur). Every Stage A/B/C
verdict is "vs HeuristicMCTS." **A model can max out that ladder and we still cannot distinguish
strong-amateur from world-champion — the ruler ends at amateur.** The project can pass all its own gates
and remain unable to verify (or falsify) its win condition. The correction plan's only line on this is an
ownerless TODO. **Recommendation:** make "build an above-amateur reference" a Stage-0 dependency. Cheapest
real options in order: (a) high-sim HeuristicMCTS (2000–8000 sims) as an interim super-amateur rung —
free, no humans; (b) bridge to an external engine (JCloisterZone bot) for an out-of-lineage anchor;
(c) a small expert/championship game corpus for move-match. Without ≥(a), Stage C "success" is
uninterpretable. **Joshua decision needed.**

---

## Investigated and REJECTED (don't action)
- **`count_final_scores` "double-count / ValueError crash" on merged same-player features** (round-2
  engine agent, claimed conf 90): NOT a bug. On the 2nd pop of a merged-feature co-meeple,
  `find_meeples` searches the already-cleared `placed_meeples` (first pop's `remove_meeples` cleared the
  board), returns empty → scores nothing, removes nothing (no `.remove()` call → no ValueError). The
  feature is scored exactly once. The `# TODO` at points_collector.py:198 is about redundant
  re-processing (efficiency), not correctness. Verified by code-trace + empirical cleanliness (re-baseline
  ran 400 games, C1 verifier 150 games, no crashes). Do not churn.
