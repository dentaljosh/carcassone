# TILE-TIE TIE-BREAK TERM — build + offline discrimination gate

> **STATUS: BUILT, GATED OFFLINE 2026-08-14 — THE GATE FAILED (`G-FAIL`, no
> conviction, leaning harmful). THE TERM STAYS DEFAULT-OFF; NO DEPLOY PREREG IS
> LICENSED AND NONE IS DRAFTED.** The pre-committed read-rule
> ([GATE_READ_RULE.md](GATE_READ_RULE.md), committed before any term-vs-oracle
> number existed — the git history shows the ordering) adjudicated the
> 10-variant hand-crafted menu on the free deep-scored corpus:
> **PRIMARY cross-fit held-out capture −0.0546 pts/tied ply (all-scale), cluster
> se 0.0300, z −1.82, boot CI [−0.1137, +0.0038]** against a measured ceiling of
> **+0.2340** ([GATE_READOUT.md](GATE_READOUT.md) / `.json`). The best variant
> in-sample (`cityroad+`) captures **+0.0196 = 8.4 % of the ceiling, z +0.57**
> — statistically nothing — and the fold-level selections flip sign
> (`city+, road−, cityroad+, cityroad−, perim−`), the signature of noise, not
> mechanism. The realized 2σ resolution was **±0.0599 pts ≈ ±5.8 elo-equiv** —
> the gate had the power to convict a term capturing ≳26 % of the ceiling, and
> none did. **A failed free gate is the process working:** 0 games were spent,
> no band claimed, no results.csv row, no claim id. Per the read-rule this is
> *no conviction for THIS feature menu on THIS corpus* — the pricing run's
> headroom (+0.252 pts/ply, z +3.43) is untouched and still unexplained.

**Lever identity (for the grep that finds this later):** "tile-tie tie-break
term" · "the 55% tile-tie blind spot", the TERM build · `LeafConfig.tiletie_dose`
/ `tiletie_w_city` / `tiletie_w_road` / `tiletie_w_perim` / `tiletie_w_lib` /
`tiletie_norm` · `flat_leaf.flat_tiletie_term` / `flat_leaf._tiletie_wallin` ·
`CARCASSONNE_TILETIE_*` · `scripts/tiletie/term_gate.py` ·
`tests/test_tiletie_term.py` · pre-gate: `measurement/tiletie_pricing_20260812/`.

---

## 1. Why this term was attempted

The pooled tile-tie pricing run ([readout](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md),
n=733 over 399 roots, branch 4) established, with conviction on the components:

- the leaf's exact tile ties carry **real value spread** — S1a σ²_arm z **+4.26**;
- the champion's 11008-sim search leaves headroom on the table — S2
  **+0.252 pts/tied tile ply, z +3.43**, ≈ **+34.5 elo** CI [+14.7, +54.7]
  (§4.3-chain extrapolation, ±1.6× bracket);
- the greedy-leaf regret (S2b, the quantity an offline pick-rule can actually
  chase) is **+0.234 pts/ply (all) / +0.324 (discriminable)**;
- phase structure: early flat, all the spread in **mid/late**; late tie sets are
  the largest (mean ≈ 14 arms) and carry the largest S2b (+0.480, z +4.17).

CL-065 forbids a learned tie-breaker representation-independently, so the term
had to be hand-crafted. The J13 pre-gate ([READOUT](../j13_pregate_20260813/READOUT.md))
prescribes the gate shape for this class verbatim: **discrimination, not
prediction** (CL-073) — the term must improve within-tied-set move ordering
against a deep ruler **before a single game is played**. That gate is free
here, because the pricing corpus already deep-scored every deduped tied arm
under CRN.

## 2. The term, exactly

Implemented in `src/carcassonne_ai/flat_leaf.py::flat_tiletie_term` (python
flat path only — see §3 on rust). For mover `p`:

```
raw = w_city  * (wall_city(opp) − wall_city(p))      # closure-geometry guard
    + w_road  * (wall_road(opp) − wall_road(p))
    + w_perim * F_perim                              # Σ occ4 over open_positions
    + w_lib   * F_lib                                # |open_positions|
T   = t / (1 + |t|),   t = raw / tiletie_norm        # bounded, monotone, no libm
score += tiletie_dose * T
```

`wall_*(q)` = over q's strict-weighted-majority (BIG=2), unfinished, closable
components: Σ over the component's distinct open cells `e` of `occ4(e) − 1`
(occupied in-bounds orthogonal neighbours of the cell the feature still needs
to fill). Mechanism: the leaf's `closure_p[open_n]` counts open cells but is
blind to how *fillable* they are; inside an exact tie set every existing leaf
term is equal across arms by definition, so this is genuinely new signal —
"don't brick up the cells your own claimed city still needs; do constrain his."

**The micro-dose design.** |T| < 1 makes `tiletie_dose` a hard cap on the leaf
perturbation. The census's non-tie top-2 gap has p5 = 0.15 with a coarse
lattice above it, so any dose ≤ ~0.02 reorders **exact and hairline ties
only** — non-tied preferences are untouched. This is what keeps the term out
of the CL-080/jrules failure class (their doses moved non-tied picks, at 10–24 %
flip rates, and lost −53.8 to −190.3 elo). The known tension, stated at design
time: a dose small enough to be tie-break-only may also be too small to steer
an 11008-sim search's pooled-Q/visits argmax — which is why the offline
ordering gate (dose-independent: the bounded map is strictly monotone) had to
convict *first*, and a deploy prereg would additionally have needed an E4-replay
flip-rate calibration. Neither stage was reached: the ordering itself failed.

`w_perim`/`w_lib` are player-independent and would break leaf antisymmetry (the
disclosed `denial_dose`-style wart); the default weights (city 1, road 1,
perim 0, lib 0) keep T antisymmetric (pinned by test).

## 3. What is built, and the off-state proof

| file | change |
|---|---|
| `src/carcassonne_ai/virtual_score_v2.py` | 6 `LeafConfig` fields + doc block; `CARCASSONNE_TILETIE_*` in `_config_from_env`; object-path `NotImplementedError` |
| `src/carcassonne_ai/flat_leaf.py` | `flat_tiletie_term`, `_tiletie_wallin`, `_tiletie_off`, dose-gated adds (int + float paths), cy-dispatch gates |
| `src/carcassonne_ai/heuristic_prior_mcts.py` | the same gated add in the PUCT float leaf (shared helper) |
| `src/carcassonne_ai/rust_agent.py` | `leaf_config_rs` conditional kwargs — **fail-closed `TypeError` on any nonzero dose** (see below) |
| `src/carcassonne_ai/alphabeta_agent.py` · `scripts/classical_search/c5_leaf_override.py` · `scripts/measurement_infra/snapshot.py` · `tests/test_frozen_substrates.py` · `tests/test_v29_flat_curve.py` · `tests/test_t3_optuna.py` | the 6 hash-exclusion sites += the 6 fields; c5 also gains the set-dose WARNING + fatal `tiletie_norm > 0` sanity |
| `tests/test_tiletie_term.py` | **new**, 15 tests (default-off inertness incl. bit-identity `.hex()`; wallin predicate matrix; antisymmetry; norm-invariance of ordering; leaf moves by exactly `+dose·T`; env plumbing; cy refusal; object-path fail-loud; rust fail-closed; `--cand-leaf-json` round-trip) |
| `scripts/tiletie/term_gate.py` | the gate instrument (label-free extraction + pure-arithmetic analysis) |

**Off-state proof — PASS.** Champion fingerprints recompute unchanged and were
runtime-verified in this build: `_leaf_hash(CHAMP) == a36d2e15a3b3d71d`,
`_frozen_config_hash` `158f17ff76adaa02` / `6dfffd57051690f2`; a default-off
cfg with **moved** weights and norm is `.hex()`-bit-identical on both the int
and pre-round-float paths over a random-play corpus. Neighbouring suites
(opencity 25 · denial · frozen-substrates · v29-curve · jrules · t3_optuna)
re-run green.

⚠️ **NO RUST MIRROR — deliberately deferred, loudly.** The offline gate is
python-side (it grades the *ordering* of the exact geometry the python term
computes), so the rust port was deferred until a gate pass would have earned
it. `rust_agent.leaf_config_rs` forwards the knobs as conditional kwargs, so
**today any `carc_rs` build raises `TypeError` on a nonzero dose** — fail-closed,
never a silently tiebreak-blind leaf — and default-off (champion) configs are
served unchanged on any wheel. Had the gate passed, the launch gates would have
been: rust mirror (f64-exact — the bounded map deliberately avoids libm, using
only `/`, `+`, `abs`) → wheel rebuild per box → `reconcile_leaf.py --configs
tiletie` 0 mismatches → `chain_capability_probe.py --require tiletie`. **None of
that is owed now.**

## 4. The offline gate — read-rule first, then the run

Order of record (git): `GATE_READ_RULE.md` committed → implementation + harness
committed → extraction (label-free, checksum-asserted 733/733, 0 errors) →
`--analyze` → [GATE_READOUT.md](GATE_READOUT.md). Corpus join integrity: 733/733
full leg coverage, 0 arm mismatches, 0 pool-<2 exclusions.

**Result: `G-FAIL` (no conviction), leaning harmful.**

| read | value |
|---|---|
| PRIMARY (5-fold root-clustered cross-fit held-out capture, all-scale) | **−0.0546 ± 0.0300, z −1.82**, CI [−0.1137, +0.0038] |
| ceiling (S2b leaf regret, all) | +0.2340 |
| fixed mechanism variant `cityroad+` (unbiased, full corpus) | +0.0196 ± 0.0345, z +0.57 |
| naive best-of-menu (audit only) | +0.0196 — the winner's-curse audit shows the cross-fit machinery mattered: selection noise alone turned +0.02 in-sample into −0.05 held-out |
| capture vs the champion's realized pick (descriptive) | −0.0619 ± 0.0603, z −1.03 |
| realized 2σ resolution | ±0.0599 pts ≈ ±5.8 elo-equiv |

**Plain reading.** None of the four geometry features (closure-cell
constrainedness on cities or roads, frontier constrainedness, frontier size)
explains a resolvable fraction of the oracle spread inside leaf-tied sets —
in a gate powered to see ~26 % of the ceiling. The phase pattern of the
capture (early −0.08, mid −0.01, late −0.07, all n.s.) does not track the
spread's phase pattern (mid/late), which is further evidence the menu missed
the mechanism rather than merely lacking power.

**Scope of the failure (binding on any write-up):** this closes *this
four-feature hand-crafted menu, graded on this corpus through this in-family
`clair-puct` ruler*. It does **not** close the tie-break axis: the +0.252
pts/ply headroom measurement stands, unexplained. It also inherits the pricing
design's caveats verbatim — in-family ruler (systematic leaf blindness
under-reports), chain-granularity, 92 % `walled` self-play corpus.

## 5. Measured leaf cost

Pure-python flat leaf (the rust-multiplier predictor, per the jrules G7
precedent that the leaf multiplier transfers ~1:1 to wall-clock), quiet box,
216 replayed random-play states across phases, candidate = dose 0.02 at the
default (`cityroad+`) weights:

- **median ratio (term on / off): 1.082** — trials 1.007 / 1.010 / 1.082 /
  1.087 / 1.138 (noisy at this scale; phase-split early 1.079 · mid 1.081 ·
  late 0.922, the sub-1 late read is noise).
- ⇒ **predicted deploy `ms_ratio` ≈ 1.08**, under the 1.20 trigger that fired
  on jrules (1.2116) — cost would *probably* not have confounded a deploy cell,
  but 1.08 is close enough to the caution band that the prereg's N4-style
  branch would have been mandatory. Moot under `G-FAIL`.

## 6. The deploy cell that is NOT licensed (recorded for the record only)

Had the gate passed, the prereg (house template
[jrules DEPLOY_PREREG](../jrules_on_search_20260813/DEPLOY_PREREG.md)) would
have been: candidate = champion leaf + `tiletie_dose` 0.02 at the
full-corpus-selected variant vs the unmodified champion `a36d2e15a3b3d71d`;
**n = 800 deck-paired**, fair PIMC **k8×1376 = 11008 both arms**, `fixed_v1` +
R9, **rust both sides**, exact-K 2; primary = deck-paired margin z; branches
incl. the **`ms_ratio` > 1.20 cost-confound downgrade**; band
**CLAIMED-BY-ORCHESTRATOR** (placeholder — no band was claimed and none may be
cited from here); plus two launch gates this build does not discharge: the rust
mirror + reconcile (§3) and an E4-replay pick-flip calibration with its own
pre-committed read-rule (the micro-dose may simply not express through search —
a ~0 % flip rate would make the cell unreadable-by-construction). **None of
this is licensed by anything in this directory.**

## 7. What would change the picture

1. **A better feature, mined not guessed.** The corpus (`features_*.jsonl` +
   the CRN oracle records) is now joined and reusable at zero cost:
   `term_gate.py --analyze` re-grades any new hand-crafted feature menu in
   minutes — but a new menu needs a NEW pre-committed read-rule file first
   (this one is spent on this menu), and repeated menu-shopping against the
   same 733 positions burns the corpus (each pass is a new multiplicity;
   the honest route caps it at one or two more mechanism-argued menus).
2. **The champion-arm mining route** (pricing DESIGN §4.4 branch 2's own
   prescription): characterize what separates the oracle-best arm from arm 0
   *descriptively* (the per-position afterstates are replayable) and only then
   hand-craft — the reverse of what this menu did (name plausible geometry,
   test it). This gate's failure is evidence the plausible-geometry direction
   is the wrong order. **→ EXECUTED 2026-08-14
   ([../tiletie_mining_20260814/MINING_REPORT.md](../tiletie_mining_20260814/MINING_REPORT.md)):
   the mining found the tie sets structurally homogeneous (~38% of the oracle
   spread unreachable by ANY static function of a 38-descriptor afterstate
   space; 30% of pools fully indistinguishable), and the mined 3-candidate
   gate 2 failed at its dev screen (`G2-SCREEN-FAIL`, z +0.06) with the
   30%-root holdout slice deliberately left unburned. Two failed menus + the
   reach bound now point at deck/lookahead-dependent tactics, not cheap
   afterstate geometry.**
3. **More supply**: the pooled run was supply-capped at 733 (the sizing wanted
   896 for the pricing question; the gate's own resolution ±0.06 pts was ample
   for THIS menu, so supply was not the binding constraint here — the features
   were).

## Pointers

- [GATE_READ_RULE.md](GATE_READ_RULE.md) — the pre-committed read-rule (branches, menu, seeds)
- [GATE_READOUT.md](GATE_READOUT.md) / `GATE_READOUT.json` — the adjudicated result
- `features_{walled,fixed_v1,app_aug2}.jsonl` — per-arm features (label-free extraction)
- [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md) + [readout_POOLED/VERDICT.md](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md) — the motivating measurement
- [../j13_pregate_20260813/READOUT.md](../j13_pregate_20260813/READOUT.md) — the gate-shape prescription (CL-073: discrimination, not prediction)
- `docs/LEVER_INDEX.md` — the tile-tie row (updated with this result)
- CL-065 (no learned tie-breaker) · CL-073 (prediction ≠ discrimination) · CL-078 (scale-axis closure, distinct mechanism class) · CL-080 + jrules (why the micro-dose profile was chosen)
