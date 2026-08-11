# Prior top-1 / policy-fidelity calibration for the distill-flywheel probe

**Date:** 2026-07-16 · **Author:** calibration pass (read-only + /tmp-scoped probe reruns; running job untouched)
**Question:** how does our new distill-flywheel `top1` (raw net prior argmax == teacher visit-distribution argmax, no search, frozen probe) compare to prior distillation / policy-training attempts?

**Metric under test** (`scripts/distill_flywheel/probe_metrics.py`): pure forward pass, `top1` = fraction of aux/full-policy probe rows where `argmax(net masked-softmax prior) == argmax(π_teacher)`; also `probe_ce` = −Σ π_teacher·log p_net and value `mse`/`r`. Teacher = the **FairHeuristicPriorAgent** (classical PUCT + heuristic priors, **blind PIMC**, k=4 dets × 688 sims = 2752 budget/move, exact-endgame K2). n_aux_rows = 3356 over 24 frozen probe games — rows are correlated within game, so treat sub-~3pp deltas as within noise.

## 1. Current run numbers (the thing being calibrated)

Non-sighted (78ch/10-scalar), `distill_flywheel_20260715/probe_metrics.jsonl`:

| iter | top1 | probe_ce | value_r | note |
|---|---|---|---|---|
| −1 (warmstart_canonical, untrained) | **0.322** | 2.320 | 0.281 | cold net |
| 0 | **0.561** | 1.737 | 0.358 | +1 distill iter |
| 1 | **0.592** | 1.718 | 0.369 | |
| 2 | **0.597** | 1.706 | 0.286 | plateau ≈0.60 |

Sighted (81ch/42-scalar), `distill_flywheel_sighted_20260716/probe_metrics.jsonl` — run started today, only warmstart probed so far:

| iter | top1 | probe_ce | value_r |
|---|---|---|---|
| −1 (sighted warmstart) | **0.364** | 2.225 | 0.468 |

## 2. Comparison table — prior attempts

Sources: L = logged on disk; R = **retroactively computed here** against these frozen fair probes; approx = best-effort (see §3 caveat).

| Prior attempt | Teacher (reference) | Fidelity metric | top-1 | Source |
|---|---|---|---|---|
| **Warmstart distillation** (`train_warmstart.py`, `warmstart_canonical.pt`) | heuristic tau05 leaf policy | **policy cross-entropy only — NO top-1 ever logged** (`val_pol_loss`) | — | L: `train_warmstart.py:44-79,403`; ckpt provenance |
| — same net, retro vs FAIR champion | FairHeuristicPriorAgent | top-1 | **0.322** | R (= run's own iter −1, reproduced exactly) |
| **Flywheel attempt2 / deepteacher / rod_v2 / rod_v28** self-play | the net's OWN clairvoyant self-play visits (not a fixed external teacher) | `val_pol_loss` (CE ≈ 0.24–0.26), `policy_entropy` (≈1.42–1.55) — **NO top-1, KL, or accuracy** | — | L: e.g. `flywheel_residual_attempt2/ckpt/iter8.metrics.json` |
| **Old NEURAL CHAMPION iter8** (`flywheel_residual_attempt2/ckpt/iter8.pt`, clairvoyant-trained, 12-scalar) | FairHeuristicPriorAgent | top-1 (approx) | **≈0.371** | R, approx (§3); value_r **0.093** |
| rod_v2_flywheel iter06 (12-scalar) | FairHeuristicPriorAgent | top-1 (approx) | **≈0.499** | R, approx; value_r −0.065 |
| rod_v28_overnight iter10 (12-scalar) | FairHeuristicPriorAgent | top-1 (approx) | **≈0.476** | R, approx; value_r −0.029 |
| **m2_sighted** warmstart (81ch/42, prior sighted attempt) | FairHeuristicPriorAgent (sighted probe) | top-1 | **0.366** | R (clean rep match) |
| m2_sighted iter_00 | " | top-1 | **0.405** | R; value_r 0.234 |
| m2_sighted iter_02 | " | top-1 | **0.397** | R |
| m2_sighted iter_04 | " | top-1 | **0.391** | R — peaks iter0, slight regress |
| **RoD-v2 nets, raw prior** (autopsy) | deep heuristic h3200/h6400 | top-1 (all-positions) | **0.225–0.280** | L: `measurement/rod_v2_flywheel/autopsy/POLICY_ROOT_AUDIT.md` |
| RoD-v2 nets **+ MCTS@200** | h3200/h6400 | top-1 | **0.46–0.52** | L: same |
| high_gap_distillation, raw prior | h6400 high-Q-gap soft targets | top-1 | **0.00 → 0.18** | L: `measurement/high_gap_distillation/` |
| iter8 + NMCTS@200 vs heur@3200 move | heur@3200 (search) | top-1 | **0.487** | L: `measurement/midgame_reference/REFERENCE_LABELS_MANIFEST.md` |
| **teacher-vs-teacher CEILING** (h3200~h6400 / h6400~h12800) | another deep search | top-1 | **0.743 / 0.765** | L: `measurement/deeper_search_ruler/root_audit/` |

## 3. ⚠️ Caveat on the retro iter8 / rod numbers (approximate)

iter8, rod_v2, rod_v28 were trained with `include_farm_scalars` **ON → n_scalar_features = 12** (base 10 + 2 appended farm scalars; DECISIONS.md line 499). The fair probe uses the default **10-scalar** schema, so these nets are **NOT a clean rep match** — the stock `probe_metrics.py` errors (linear shape mismatch). The board rep (78ch) IS shared and unchanged (warmstart_canonical, same board rep, reproduces its logged 0.322 exactly), so the ONLY delta is those 2 farm scalars. The retro numbers **zero-pad the 2 missing farm scalars** (`scratchpad/padded_probe.py`, /tmp-scoped, stock metric otherwise). Since the net learned to use those scalars, feeding 0 is OOD → the top-1 values are a **mild underestimate**. They are honest best-effort approximations, not clean matches. No prior 78ch/12 net can be scored cleanly without regenerating a 12-scalar probe.

## 4. Headline — is ~60% good, mediocre, or unknown-because-novel?

**Good in absolute and same-kind terms, with one honesty caveat.** Our probe measures the **raw net prior** (no search) agreeing with a strong teacher's visit-argmax. The only prior "raw prior top-1 vs a strong search teacher" numbers on record are **0.18–0.28** (RoD-v2 nets vs h3200/h6400; high_gap 0.00→0.18). Our **0.56–0.60 is roughly 2–2.6× that** — the strongest raw-prior/teacher agreement in the program.

Two caveats keep it from being a pristine comparison:
1. **Different teacher and probe set** — prior raw-prior numbers used a *pure deep heuristic* (h3200/h6400) as reference; ours is the FairHeuristicPriorAgent (blind PIMC). Not identical rulers.
2. **We are the only run that actually distilled its comparison teacher.** The RoD/high_gap nets were trained on a *different* objective (their own clairvoyant self-play visits) and merely *measured against* h3200 — so their low agreement is partly "wrong objective," not "bad fit." A net explicitly imitating teacher X *should* agree with X more. So the cleanest apples-to-apples ("a net distilled directly onto this exact teacher") has **no prior instance → that part is genuinely unknown-because-novel.**

**Ceiling context makes ~60% look near-plateau, not broken:** two *different* strong searches only agree **0.74–0.77** on top-1 (argmax agreement between distinct strong policies has a soft ceiling well below 1.0). At 0.60 the raw prior is ~80% of the way to that ceiling, so the plateau at ~60% is plausibly close to a practical ruler ceiling — limited headroom, not a stalled fit. (Value fidelity is the weaker half: `value_r` sits at only 0.29–0.37 across iters — the policy imitates far better than the value head.)

**Sighted side:** current run has only the warmstart (0.364) so far. The best prior sighted comparator is **m2_sighted**: 0.366 (warmstart) → 0.405 (iter0) → 0.397 → 0.391 — it peaked at iter0 (~0.40) and *slightly regressed*, i.e. the prior sighted training barely beat its warmstart. If the current sighted distillation climbs materially above ~0.40 it will already exceed that prior attempt. (Note: the current sighted warmstart sha `1e38ac` ≠ m2_sighted's `c576e2` — different nets, same ~36% tier.)

## 5. Did the clairvoyant neural champion (iter8) ever get a top-1 vs a champion teacher?

**No — never logged.** The whole clairvoyant flywheel/deepteacher lineage logged only policy **cross-entropy vs its OWN self-play visits** (`val_pol_loss` ≈0.24) plus `policy_entropy` — no top-1, no external-teacher agreement, in any `*.metrics.json`.

**Retroactively (approx, §3 caveat):** iter8 agrees with the FAIR champion at only **top-1 ≈ 0.371** — barely above the cold warmstart (0.322) and far below the fair-distilled iter0 (0.561) — with a **value correlation of essentially zero (r ≈ 0.093)**. rod_v2 iter06 ≈ 0.499 and rod_v28 iter10 ≈ 0.476 sit higher on policy but also show ~0 / negative value_r. **Takeaway:** a clairvoyant-trained net does **not** naturally agree with the blind fair champion (policy ~37–50%, value ~0); the direct fair distillation is exactly what lifts top-1 to ~60% and is a genuinely distinct objective from the old clairvoyant training — not a reproduction of it.
