# RoD — Revenge of Demis · v2.8 Continuation Probe — FINAL REPORT (Phase 7)

**Branch:** `rod_v28_continuation_probe` (from `stage-b-wiring` @ `ccc33c2`) · **Date:** 2026-06-22
**Status banner:** ✅ COMPLETE · **MEASUREMENT ONLY** — no promotion, `PRODUCTION.yaml` UNCHANGED, champion still `flywheel2_champion_iter8`, v2.7 leaf bit-identical, v2.8 opt-in. No checkpoint promoted.

## Verdict: **RoD POSITIVE** (closed the equal-leaf gap to parity; not superhuman)

One continuation iteration under the v2.8 leaf produced a checkpoint (`RoD_iter_01`) that **beats the frozen `ITER8_V28_PARENT` by +53.4 Elo (paired z = 3.51, n=400)** in same-leaf, deck-paired, both-seats eval — a credible margin. This is the **first** continuation in the project to beat its parent; every v2.7-substrate attempt (deeper-teacher, residual-flywheel plateau) was a powered null. RoD also **closed the equal-leaf gap to deep heuristic search** (parent `iter8+v2.8` was −38.4 vs `heur@3200_v28`; `RoD_iter_01` is a statistical **tie**, n=800) — reaching **parity**, the first time the learned agent attains deep-heuristic strength at equal leaf. It does **not exceed** the heuristic, and there is **no human/external anchor**, so this is **not** a superhuman claim.

## Evidence summary (all cited)

| measurement | result | n | artifact |
|---|---|---|---|
| `RoD_iter_01+v2.8` vs frozen `ITER8_V28_PARENT` | **+53.4 Elo, paired z 3.51** (227W/7D/166L) | 400 | [PARENT_MATCHUPS](PARENT_MATCHUPS.md) · `v28_rod_probe/nvn_iter_01_mk20_vs_iter8_mk20_s200_rs025` |
| (pilot) same | +70.4 Elo, z 2.91 | 200 | (regressed to +53 at n=400) |
| `RoD_iter_01+v2.8` vs `heur@3200_v28` | **TIE** — winrate Elo +16.5 (z1.34), paired margin −0.36 (z−0.47) | 800 | [RULER_MATCHUPS](RULER_MATCHUPS.md) · `v28_rod_probe/rod_iter01_vs_heur3200_v28` |
| anchor: `iter8+v2.8` vs `heur@3200_v28` | −38.4 | 200 | `measurement/heuristic_v28` battery |
| root-move agreement with `heur@3200_v28` | RoD 0.511 vs parent 0.520 (Δ −0.009) | 1000 pos | [ROOT_AUDIT_V28](ROOT_AUDIT_V28.md) |

**Provenance:** `RoD_iter_01` = `rod_v28_continuation/ckpt/iter_01.pt`, sha `a8b824df…`, warm-from iter8 (sha `0d355002…`, verified unchanged). 1000 v2.8 self-play games (0 failed, 2.12M positions), trained batch256/3ep, VLW 1.5. Commits `dbdd4b3`→`b39dd27`. Full config in [CHECKPOINT_MANIFEST.json](CHECKPOINT_MANIFEST.json), [BASELINE_CONFIGS.json](BASELINE_CONFIGS.json).

## The seven questions

**1. Did v2.8 continuation beat frozen `ITER8_V28_PARENT`?** **YES** — +53.4 Elo / paired z 3.51 (n=400), credible. RoD POSITIVE.

**2. Did it close the gap to `HEUR_3200_V28`?** **YES, to parity.** Parent −38.4 → RoD ~0 (tie at n=800). Closed the gap; did **not** exceed the ruler. Transitivity holds (−38.4 + 53.4 = +15 predicted; +16.5 winrate measured), so the parent-beating is a real strength gain, not a non-transitive artifact.

**3. Policy-, value-, or residual-driven?** **Policy reshaping.** residual_scale was held at 0.25 (not a free lever here), and the project's value head ranks siblings at chance (CL-021); the gain is a genuine change in the learned *policy* (~35% of root choices changed) under the stronger v2.8 leaf. The root audit shows it is **NOT teacher-imitation** of heur@3200 (root-move agreement flat, Δ−0.009) — it is a phase-dependent reshaping (more heuristic-aligned in the endgame where the meeple term bites; less in the opening).

**4. Does it justify a larger v2.8 flywheel?** **Qualified YES.** The probe proves the v2.8 substrate **unsticks the flywheel** the v2.7 leaf had pinned (a +53 continuation gain v2.7 could not produce). BUT compounding-past-parity is **untested** (iter2 not run), and iter1 reached parity by *reshaping, not out-searching*, so there is no mechanistic guarantee further iters exceed the heuristic. A **dedicated multi-iteration v2.8 flywheel** is the right way to resolve compounding (one iter would be too noisy). Moderate justification — worth a deliberate run, not a foregone win.

**5. Does it justify distillation-from-`heur@3200_v28`?** **Plausible, not clearly superior.** RoD reached parity with heur@3200_v28 via self-play *without* converging onto its moves (root audit). Explicit distillation-from-heur@3200_v28 is a coherent alternative lever (directly teach the deep-search policy), but the non-imitation result suggests the heuristic's per-move choices are not obviously the thing to clone. Worth a small A/B against another v2.8 self-play iter, not a clear priority over (4).

**6. Was the old flywheel failure substrate-caused or unresolved?** **Substrate-caused — partially.** The v2.7 leaf was a *real* ceiling: swapping to v2.8 unstuck a significant continuation gain that v2.7's flywheel and deeper-teacher could not produce. So the "v2.7 leaf caps learned strength" hypothesis is **confirmed as A blocker**, now moved one notch (learned reaches the heuristic at equal leaf). BUT the **deeper blocker — exceeding the heuristic — is unresolved**: RoD only reached parity. Raising the leaf raised the floor to the heuristic's level; it did not by itself put the learned agent above it.

**7. What next?** In priority order:
   - **Primary: a dedicated larger v2.8 flywheel** (multi-iter, warm-from `RoD_iter_01`, v2.8 leaf, low-sim plane) to test whether the gain **compounds past parity** — the decisive open question for the superhuman thread. New branch, deliberate run.
   - **Secondary: distillation-from-`heur@3200_v28`** as an A/B lever inside that flywheel.
   - **Further heuristic v2.8.x improvements** — since raising the leaf raised both heuristic *and* learned strength, and the leaf is still the shared substrate, a stronger v2.8.x leaf is a parallel lever (but a classical-engine gain, not an ML one — see the heuristic-v28 close-out).
   - **The unaddressed measurement gap: an external/human anchor.** "Parity with deep search under a hand-crafted leaf" is NOT superhuman. Any superhuman claim still requires a reference outside the heuristic family (strong human / solver-grounded). This remains the binding blocker the strength levers cannot resolve.
   - **Production: HOLD.** No promotion. Champion stays iter8 (v2.7 production). v2.8 remains an experimental reference/leaf.

## Honest caveats
- **Not superhuman; not even "beats the heuristic."** Parity at equal leaf, no external anchor.
- **One iteration, one seed band.** Compounding, robustness across bands, and behavior at the play (low-sim) vs deep-search planes are not characterized.
- **The "parity" rests on a tie** (n=800 winrate +16.5/z1.34 vs margin −0.36/z−0.47) — the *gap-closure* is rigorous (via the +53/z3.51 parent matchup); "reaches the heuristic's level" is the fair phrasing, "matches it" is borderline.
- v2.8 itself is a stronger **ruler**, not a production change; this probe does not alter that.

**Recommended next branch:** `rod_v28_flywheel` — a dedicated multi-iteration v2.8 flywheel from `RoD_iter_01`, to test compounding past parity.
