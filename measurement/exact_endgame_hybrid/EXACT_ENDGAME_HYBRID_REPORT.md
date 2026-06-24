# Exact Endgame-Solver Hybrid — REPORT

> **Status: IN PROGRESS** (branch `exact-endgame-hybrid`, opened 2026-06-24).
> **Measurement / engineering only.** No promote, no PRODUCTION.yaml change, v2.7 frozen,
> v2.8 opt-in. The exact tail is leaf-independent (true terminal score), so nothing here
> touches the production leaf.

## The question (and the conservative prior)

The [iter_08 autopsy](../rod_v28_overnight_flywheel/autopsy/AUTOPSY_RoD_v28_iter08.md)
localized the learned agents' persistent gap vs the deep heuristic to the **endgame**
(all learned nets agree with heur@3200_v2.8 only ~0.51 at the root-move level, *lowest*
in late_mid / pre_endgame). This branch tests the one lever that can *provably exceed* a
heuristic there: hand off the final K placements to an **exact solver**.

**Prior (conservative, pre-registered):** exact handoff patches a *small, real, sub-point*
endgame leak in RoD1; it likely beats RoD1 by a point or two but only *ties* heur@3200_v2.8,
which already plays the K=2 endgame near-optimally. High **diagnostic** value (a source of
truth in the plateau region); low odds of a new champion. Support / falsify / sharpen it.

## Why a clairvoyant exact solver is the FAIR comparison here

Production NeuralMCTS **and** HeuristicMCTS are already **clairvoyant in search** — they
descend the true pre-shuffled deck (`state.deck`), which is exactly what the
[clairvoyance-gap eval](../clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md) measured (+26.6 elo).
So **clairvoyant-exact vs clairvoyant-RoD1/h3200 is a like-for-like, same-information
comparison** — and it is the cheap one (alpha-beta is sound only for minimax). That is the
default arm below, labelled as such. The *marginalized* (fair-information / hidden-bag)
solver is a separate, far more expensive question (no alpha-beta → ~K≤2) and is **never
silently mixed** with clairvoyant-search opponents.

The exact solver is **minimax-optimal vs a worst-case opponent** — NOT a best-response to
the specific (suboptimal) RoD1/h3200 it faces. A conservative, valid endgame policy; not an
oracle exploiter.

## Agents & provenance

| agent | checkpoint / spec | sha256 (16) | leaf | play config |
|---|---|---|---|---|
| **RoD_iter_01** ("RoD1") | `rod_v28_continuation/ckpt/iter_01.pt` | `a8b824df0786284c` | v2.8 (meeple_k=2) | NeuralMCTS s200 c3.0 resid0.25 |
| iter_08 (keep-best, non-promoted) | `rod_v28_overnight_flywheel/ckpt/iter_08.pt` | `5843b3cf0d172f73` | v2.8 | NeuralMCTS s200 c3.0 resid0.25 |
| ITER8_V28_PARENT | `flywheel_residual_attempt2/ckpt/iter8.pt` | `0d355002e26a968e` | v2.8 | NeuralMCTS s200 c3.0 resid0.25 |
| **heur@3200_v2.8** | `heur@3200` + meeple_k=2 | — | v2.8 | HeuristicMCTS 3200 sims, v2_7 leaf+mk2 |
| **exact_hybrid_K:mode** | `exact:K:clair\|marg` (RoD1 prefix) | (uses RoD1) | prefix v2.8; **tail leaf-independent** | RoD1 until first TILES k≤K, then exact solver |

**Baselines that set the bar (from the autopsy's cached deck-paired matches):**
- RoD1 vs heur@3200_v2.8 (n=800): paired **−0.36** (z−0.47) → RoD1 **ties** the ruler.
- iter_08 vs heur@3200_v2.8 (n=800): paired **−0.38** (z−0.48) → also ties.
- RoD1 vs ITER8_V28_PARENT (n=400): **+53.4 elo**, paired +3.68 (z+3.51).

For exact handoff to "exceed h3200" it must show paired margin **clearly > 0** vs h3200
(RoD1 sits at −0.36). For "beats RoD1" it must show paired margin > 0 vs RoD1.

---

## Part A — Engineering (the `exact:K:MODE` agent)

Implemented as a drop-in agent in [`scripts/level2/eval_hybrid_handoff.py`](../../scripts/level2/eval_hybrid_handoff.py)
(`_ExactAgent`), reusing the existing latched-handoff harness (pairing, claim, carc-orch
SHM, manifest) and the existing exact solver
[`scripts/level2/endgame_solver.py`](../../scripts/level2/endgame_solver.py).

- **Latch:** identical trigger to `hybrid:K:N` — first **TILES**-phase decision with
  `k_remaining = len(deck) + (next_tile is not None) ≤ K`. One-way, turn-atomic (the
  boundary tile's meeple stays with the solver). No fall-through back to neural after latch.
- **Choice:** `min(optimal_actions)` from `solve()` — deterministic; value-irrelevant within
  the optimal set under optimal play.
- **Modes:** `clair` → clairvoyant minimax + alpha-beta (default); `marg` → marginalized
  expectiminimax (no AB).
- **Timeout fallback:** a solve exceeding the node budget (`BudgetExceeded`) falls back to
  the **neural** move for that one decision (stays latched, retries next ply on the smaller
  tree); counted as `n_timeouts`, never hidden.
- **Per-handoff logging (in `GameResult`):** `latch_k`, `latch_score` (margin at handoff,
  mover-perspective), `latch_meeples`, `latch_nlegal`, `exact_moves`, `n_timeouts`,
  `solver_secs`, `solver_nodes`, `max_solve_secs` — both seats.

**Verification (GPU integration smoke, exact:2:clair vs RoD1, 2 paired games):** PASSED —
`plumbing + handoff verified`. Latch fires one-way at k≤2 (TILES); exact moves are **legal**
(both games ran to terminal, no illegal-action error); neural prefix (70/game) + exact tail
(2/game) both exercised; 0 timeouts. Per-game solver ~0.2–12 s.

**⚠️ Parity dilution (material for interpreting Part C):** k_remaining counts down by 1 per
draw, alternating players, so whether the exact agent's first sub-threshold TILES decision
lands at k=2 or k=1 is a coin-flip. In ~half the games it latches at **k=1** (a near-forced
last tile → exact ≈ neural); only the other ~half get a meaningful **k=2** solve. So exact:2
changes the agent's play in only ~50% of games — it **structurally halves** the measurable
full-game effect. (exact:3 would always catch ≥k=2, but K=3 is micro-only at 80 s/solve.)

---

## Part B — Micro-validation & solver tractability

### B.1 — Solver cost by K (the full-game feasibility gate)

Clairvoyant + alpha-beta, real L2-3 suite positions
([`scripts/exact_hybrid/bench_solver_by_k.py`](../../scripts/exact_hybrid/bench_solver_by_k.py)):

| K | solved | sec median | sec max | nodes median | full-game verdict |
|---|---|---|---|---|---|
| 2 | 13/13 | **~5 s** | 25.6 s | ~2,200 | **feasible** (~2 solves/game ≈ ~10 s/game) |
| 3 | 3/3 | **80 s** | 119 s | ~26k | **MICRO-ONLY** (~160 s/game tail) |
| 4 | (K4 probe) | ~21 min @1M | 7.4 h | 108k | **infeasible for full games** |

0 illegal moves across the bench — the exact-tail choice path (`min(optimal_actions)`) is
correct. **Implication (depth series):** **K=2 full-game (n=400)** is cheap (~10 s/game);
**K=3 full-game screens (n≤200)** are feasible (~80 s/solve, solver-bound → runs on the
CPU-heavy Xeon / local); **K=4 full-game** is marginal (~21 min/solve, 7.4 h tail → needs a
node-budget cap → ~6–10 % timeout-fallback) and worth it only gated on a K=2→K=3 trend;
**K=5+ needs make/unmake or Rust** (deferred). Feasible full-game series = **K=2 → K=3
(→ small K=4)**; K=4/K=5 regret stays micro-validation. (Parity: for any K the agent latches
at k=K or k=K−1 by turn parity, so deeper K = less dilution — K=3 is a *better-powered* test
than K=2, not just "more depth".)

### B.2 — Endgame regret vs exact (already measured; L2-3 / K4 probe)

The endgame *disagreement* the autopsy localized is real, but its **point value is small**,
and h3200 already plays it near-optimally:

**NEW (this branch — RoD1/iter_08/parent scored at K=2 with their v2.8 leaf, n=150 each):**

| agent (v2.8) | K=2 top-1 | mean regret | worst single error |
|---|---|---|---|
| **RoD1** | 0.673 | 0.57 | 9 |
| iter_08 (keep-best) | 0.687 | 0.69 | **15** |
| parent | 0.687 | 0.61 | 9 |
| **heur@3200** (v2.7 ref) | **0.833** | 0.41 | 8 |

The learned nets (RoD1 ≈ iter_08 ≈ parent, all ~0.68 top-1) play the K=2 endgame
**measurably worse** than h3200 (0.833) — reproducing L2-3 (iter8 0.667 / h3200 0.837) with
the v2.8 agents, and confirming the autopsy's "RoD1 ≈ iter_08 ≈ parent" extends to the
endgame. But mean regret is **sub-point** (0.57–0.69) and h3200 is near-optimal → exact
handoff fixes a **real-but-tiny leak** in RoD1 and has little to fix vs h3200. iter_08 carries
the *worst* endgame (regret 0.69, a 15-pt worst case) — consistent with the autopsy's
"iter_08 moves *away* from the ruler in the endgame".

---

## Part C — Full-game exact-hybrid evaluation

**K=2 (full n=400, deck-paired both seats), v2.8 throughout.** Exact tail = RoD1 prefix until
the first TILES decision with k≤2, then clairvoyant+alpha-beta solve. 0 timeouts,
exact-moves/game = 2.0, latched 400/400, K@latch split 200×k=2 / 200×k=1 (the parity 50/50).

| cell | W/D/L | winrate (z) | winrate-Elo | **paired score margin** |
|---|---|---|---|---|
| exact:2 vs **RoD1** | 198/5/197 | **0.501** (z+0.05) | +0.9 (±17.4) | **+0.645 (z+7.49)** |
| exact:2 vs **heur@3200_v2.8** | 206/9/185 | 0.526 (z+1.05) | +18.3 (±17.4) | +1.09 raw (z+0.99) · **Δ +0.652 (z+4.47)** |

(Δ = paired difference vs the cached RoD1-vs-h3200 run on the *identical* decks — isolates the
exact tail.) **The result is consistent and unambiguous:** the exact K=2 tail adds a real,
highly-significant **~+0.65 pt/game** (z+7.5 vs RoD1; deck-controlled z+4.5 vs h3200) —
exactly recovering RoD1's ~0.57-pt/move endgame regret (Part B) — **but moves the WINRATE by
≈ 0** (vs RoD1 literally 0.501; vs h3200 +18.3 Elo but z+1.05, **not** significant). It
**patches the endgame leak without breaking the ruler.** Deck-neutral, exact:2 lifts RoD1 from
the cached −0.36 margin vs h3200 to ≈ +0.29 — a tie-to-slight-margin-lead, not a winrate win.

**K=3 (full n=400 both opponents).** Latch k∈{2,3} by parity, exact-moves/game 3.0, 0
timeouts, solver ~40–89 s/game (heavy tail to 52 min, all solved):

| cell | winrate (z) | winrate-Elo | **paired score margin** |
|---|---|---|---|
| exact:3 vs **RoD1** (n=400) | 0.525 (z+0.98) | +17.7 (±18.0) | **+1.422 (z+8.08)** |
| exact:3 vs **heur@3200_v2.8** (n=400) | 0.537 (z+1.50) | +26.1 (±17.4) | +1.70 raw · **Δ +1.260 (z+7.29)** |

### Depth series — the headline of this branch

| depth | exact moves/game | margin vs RoD1 | Δ-margin vs h3200 | winrate vs RoD1 | winrate vs h3200 |
|---|---|---|---|---|---|
| K=2 | 2.0 | +0.645 (z+7.5) | +0.652 (z+4.5) | 0.501 | 0.526 (z+1.05) |
| K=3 | 3.0 | +1.422 (z+8.1) | +1.260 (z+7.3) | 0.525 (z+0.98) | 0.537 (z+1.50) |
| K=4 | 4.0 | _(n=12, re-running)_ | **+1.943 (z+2.80)** | — | 0.568 (z+1.44) |

(K=4 vs-h3200 = n=94/100, **0 timeouts**, all solved; winrates are **deck-paired** seat-balanced.
K=4 vs-RoD1 was interrupted by a local OOM at n=12 — re-running. The K=4 z's are lower than K=3
only because n=94 ≪ n=400, not because the effect shrank.)

**Two findings, kept strictly separate — this is the winrate-vs-margin distinction in action:**

1. **The Δ-margin scales cleanly and significantly with depth:** +0.65 → +1.26 → +1.94 raw score
   points/deck (z+4.5 → +7.3 → +2.80). The exact tail demonstrably does *more* the deeper it
   reaches. **Mechanism (Part B regret):** h3200's *own* endgame play degrades with depth —
   top-1 vs the solver drops 0.833 (K=2) → ~0.60 (K=4) — so exact's advantage over the heuristic
   compounds. By K=4, RoD1 and h3200 are *equally* far from optimal (both ~0.60 top-1) and exact
   beats both.

2. **The winrate does NOT track it.** Deck-corrected, it drifts up only weakly (0.526 → 0.537 →
   0.568) and is **non-significant at every depth** (z+1.05 / +1.50 / +1.44). The empirical
   margin→winrate slope is **~1.6% winrate per point** (measured off the K=2 n=400 margin
   distribution, σ≈24), so the ~+1.3-point margin gain K=2→K=4 *should* buy only ~+2% winrate —
   which is about what's seen. (A K=4 n=82 partial briefly showed 0.61 / z+2.09, but that was
   **deck-selection bias**: the fast-completing games sat on A-favouring decks where RoD1 *itself*
   scored +3; once the hard games landed it regressed to 0.568. The deck-paired Δ is the
   trustworthy statistic — the raw winrate of a partial is not.)

**So: exact endgame play sharpens the score margin, and the effect grows with depth — but the
points mostly do not flip outcomes, so it produces no significant winrate edge over the ruler at
any feasible depth.** Digests: [`partCDF_k3_vs_RoD1.md`](partCDF_k3_vs_RoD1.md),
[`partCDF_k3_vs_h3200.md`](partCDF_k3_vs_h3200.md), [`partCDF_k4_vs_h3200.md`](partCDF_k4_vs_h3200.md).

## Part D — Slice analysis (why margin improves but winrate doesn't)

The exact gain does **not** concentrate where it would flip outcomes:
- **vs h3200:** the +0.65 margin lands in **blowouts (paired +2.96)** not **close games
  (−0.44, z−0.51)** — extra endgame points pile up in already-decided games. That is the
  mechanism of the margin/winrate split.
- **vs RoD1:** the gain is ~uniform — close +0.57 (z+5.95), blowout +0.66 (z+4.1) — but +0.57
  pts is too small to flip close games (a flip needs the final margin to cross 0).
- The `margin@latch` slice (already-ahead → 0.84 wr; behind → 0.17 wr) is just "leading at the
  endgame → win", not an exact effect — the paired-Δ controls for it.
- 0 timeouts; solver ~3.4 s/game (vs RoD1) / ~7.6 s/game (vs h3200); nodes/game ~770.
- Full digests: [`partCDF_vs_RoD1.md`](partCDF_vs_RoD1.md), [`partCDF_vs_h3200.md`](partCDF_vs_h3200.md).

## Part E — Endgame mechanism: what the exact tail actually fixes

Top 40 RoD1-suboptimal K=2 positions (from Part B regret), move-types decoded — a striking
single mechanism:

- **Every one is a last-tile *placement* error** (TILES phase, k=2): RoD1 places its final
  tile worse than the exact optimum (`tile_place` vs `tile_place`). **Zero** are meeple
  under-deployment or farmer over-commit — by k=2 the meeples are already placed (meeples
  in hand 0–1), so the leak is pure **scoring-conversion / denial on the last tile**
  (completing a city/road/farm, or denying the opponent), not meeple economy. (Refines the
  L2-3 "iter8 wastes meeples" intuition: at the *very* endgame it's tile placement, not
  meeple deployment, that RoD1 gets wrong.)
- **h3200 already makes the exact fix on 24/40 (60%)** of RoD1's mistakes → little for exact
  to add there. But on **16/40 (40%) h3200 is *also* suboptimal** — on those, exact play
  beats **both** RoD1 and h3200. That 40% is the narrow avenue by which exact endgame play
  can *exceed* the deep heuristic (the autopsy's "one lever that can exceed a heuristic"),
  bounded to the last tile.
- Worst RoD1 error in the set: **9 pts** (seed 3200000129, a 67–64 game decided on the last
  tile). Most are 1–3 pts.

Full table: [`partE_examples_digest.md`](partE_examples_digest.md) / `.csv`.

## Part F — Does exact solve h3200's gap, or just patch RoD?

Against the four pre-registered outcomes:

- **It patches RoD1's endgame leak** — the deck-controlled Δ-margin vs h3200 is positive and
  significant at every depth (+0.65 → +1.26 → +1.94; z+4.5 → +7.3 → +2.80), and Part B/E pin the
  leak to RoD1's last-tile *placement* (sub-point at K=2, ~1.5 pts by K=4).
- **On the score-margin metric it *exceeds* h3200 — and increasingly with depth.** RoD1 ties
  h3200 (cached −0.36); the exact tail lifts it to a clear margin lead by K=4
  (−0.36 + Δ1.94 ≈ **+1.6 pts/deck deck-neutral**). This realises the autopsy's "one lever that
  can exceed a heuristic": where RoD1 *and* h3200 both misplay the deep endgame (Part E: 40% of
  RoD1's K=2 mistakes are shared by h3200; Part B: both ~0.60 top-1 at K=4), exact beats both. So
  "can the learned/heuristic stack be exceeded in the endgame?" → **yes, on margin**, strictly,
  with the gap *widening* as you solve deeper.
- **But it does NOT break the ruler on winrate.** The margin does not convert: deck-paired
  winrate vs h3200 is non-significant at all depths (0.526 / 0.537 / 0.568; z≤1.5). Per Part D
  the extra points land where games are already decided, not in the close games that would flip;
  and the empirical conversion (~1.6%/pt) is too shallow for a sub-2-pt margin to move outcomes.
- **The comparison is clean** — clairvoyant-exact vs clairvoyant-search h3200 (like-for-like
  information), **0 timeouts** at K≤4 (no fallback contamination), no clairvoyance artefact.

**Verdict (Part F):** it is **more than "patches RoD, ties h3200"** — exact genuinely *exceeds*
h3200 on the endgame score-margin, and the excess scales with depth. But it is **less than
"beats h3200"** in the way that makes a champion: the margin never becomes a winrate edge. The
one-liner: **exact endgame play is provably better than the deep heuristic in the endgame — and
more so the deeper you solve — but that superiority is sub-point and outcome-neutral. It sharpens
the ruler; it doesn't beat it where games are won.**

## Part G — Distillation feasibility (exact labels as a training target)

**What the solver can label (free, per position):** the optimal action (policy target), V*
(the true optimal-play value target), and `child_values` — the exact value of *every* legal
action (a dense policy/regret target, far richer than a one-hot).

**Generation cost (measured):** K=2 ~5 s/solve, K=3 ~80 s, K=4 ~21 min. An exact-labeled
endgame set is cheap at k≤2 (~20–50k positions ≈ ~2–5 h at W=14), costly-but-feasible at k=3
(~10k ≈ ~16 h at W=14), prohibitive at k≥4 (needs make/unmake or Rust).

**What it could teach — and the headwinds:**
- *Policy head* (better last-tile placement, the Part-E mechanism): **low EV** — policy gains
  **wash out under deep MCTS** (memory: net improvements wash out at high sims) and the gain
  is **sub-point** (Part B regret 0.57). Unlikely to move play-strength.
- *Value head* (the more promising target): the autopsy showed the value head **degrading**
  through the RoD continuation (0.510→0.40). Exact V* at k≤3 is a clean true-optimal signal to
  **recalibrate** endgame value estimates — an auxiliary endgame-value head / oversampling late
  positions with V* targets could improve endgame *calibration* without the policy-washout
  problem. This is the one distillation angle with a plausible mechanism.

**Upper bound on the upside:** the fix is geometrically confined to the last 1–3 tiles, so even
*perfect* distillation cannot address blocker #2 (the learned net exceeding the heuristic across
the whole game) — it can only sharpen the endgame tail. **Now that Part C is in** — the exact
tail's full-game effect is a real-but-outcome-neutral score-margin gain — **policy-distillation EV
for play-strength is LOW**: the distilled policy gain is the same sub-point, washout-prone,
winrate-neutral margin sharpening. **Recommendation:** do *not* pursue policy distillation for
strength; harvest exact V* at k≤3 as an auxiliary endgame **value-calibration** target *only if*
the value-head's endgame degradation (autopsy) becomes the binding constraint.

## Part H — Verdict

**Did exact handoff produce full-game lift?** On the **score margin, yes** — a real, highly
significant gain that *scales with depth* (Δ vs h3200 +0.65 → +1.26 → +1.94 pts/deck, K=2→K=4,
z up to +8). On the **winrate, no** — deck-paired 0.526 → 0.568, non-significant at every depth.

**Did it exceed h3200?** **On margin, yes, and the excess grows with depth** (by K=4, deck-neutral
≈ +1.6 pts/deck vs the ruler; at K=4 RoD1 and h3200 are equally suboptimal and exact beats both).
**On winrate, no.** So "can the endgame be played provably better than the deep heuristic?" →
**yes** — but the superiority is sub-point and outcome-neutral.

**Broad enough to matter?** No. Confined to the last ~2–4 tiles, and the points accrue mostly in
already-decided games (Part D) — they don't flip outcomes. It sharpens the ruler; it doesn't win
more games.

**Worth engineering K5/K6 / make-unmake / Rust?** **Not for strength.** Winrate is flat at K=2–4
and the margin→winrate slope (~1.6%/pt) means even a +3–4 pt margin at K=6 buys <~6% winrate —
still likely sub-significant — at hours/game solver cost. (Operational frontier: the orchestrated
eval path is **incompatible with K≥4** — long solves starve the SHM server → crash — and
net-on-CPU is **RAM-bound**, W ≤ RAM/~2 GB.) Build it only if a value-calibration use justifies it.

**Is exact-label distillation worth doing?** **Not for play-strength** (the policy gain is the
same washout-prone, outcome-neutral margin sharpening). One surviving angle: exact V* at k≤3 as an
**auxiliary endgame value-calibration** target — and only if the value-head's endgame degradation
becomes the binding constraint.

**Next branch.** Exact endgame play is a clean diagnostic and a real-but-cosmetic margin lever — it
is **not** a path to superhuman strength: blocker #2 (the learned/heuristic stack being exceeded
*across the whole game*, not just the last tile) stands untouched. Recommend (1) a **non-saturated
reference** (h6400/h12800 or a stronger external opponent) to re-open measurement headroom, and
(2) **whole-game** strength levers, not deeper endgame exactness. **No promotion; v2.7 frozen,
PRODUCTION unchanged.**

### 10-line executive summary

1. Built `exact:K:MODE` — a hybrid that plays RoD1 (v2.8) then hands the last K tiles to an exact
   clairvoyant alpha-beta solver (verified, 0 illegal, leaf-independent tail; fair clairvoyant-vs-clairvoyant).
2. Feasible full-game depths: K=2 (~5 s/solve), K=3 (~80 s), K=4 (net-on-CPU only — the
   orchestrator crashes on K≥4's minute-long solves; net-on-CPU is RAM-bound). K≥5 needs make/unmake/Rust.
3. Endgame regret (Part B): RoD1/iter_08 play the K=2 endgame measurably worse than h3200 (top-1
   0.67 vs 0.83), but h3200's edge **vanishes by K=4** (both ~0.60).
4. Mechanism (Part E): RoD1's leak is pure **last-tile placement** (scoring/denial), not meeple
   management; h3200 shares 40% of those exact mistakes.
5. K=2 full-game: exact adds **+0.65 pt/game** (z+7.5 vs RoD1; deck-Δ z+4.5 vs h3200), winrate flat.
6. **Headline: the Δ-margin vs h3200 scales ~linearly with exact depth — +0.65 (K2) → +1.26 (K3)
   → +1.94 (K4), z up to +8.** Exact play does more the deeper it solves.
7. **But the winrate does not follow:** deck-paired 0.526 → 0.537 → 0.568, **non-significant at
   every depth** (slope only ~1.6%/pt). A K=4 partial's 0.61/z+2.09 was deck-selection bias → 0.568.
8. So exact endgame play is **provably better than the deep heuristic on margin (growing with
   depth) but outcome-neutral** — it sharpens the ruler, it doesn't beat it on winrate.
9. Not a champion, not a path to one: confined to the last ~2–4 tiles; blocker #2 (whole-game
   learned strength) stands. Distillation EV low (value-calibration only).
10. **No promotion; v2.7 frozen, PRODUCTION unchanged.** Next: a non-saturated reference + whole-game
    levers, not deeper endgame exactness.

> **Status note:** K=4-vs-h3200 = n=94/100 (tail finishing); K=4-vs-RoD1 re-running after a local
> OOM (the W=18 K=4 net-on-CPU run exceeded 42 GB — fixed at W=6). Numbers above are stable; the
> final 6 + the vs-RoD1 row will be folded in on completion. This report flips to **status:
> COMPLETE** then.
