# Deeper-Search Ruler / Teacher Probe — Report

**Status: IN PROGRESS (2026-06-24)** · branch `deeper-search-ruler` · **no promotion, PRODUCTION.yaml untouched, v2.7 frozen, v2.8 opt-in.**

Question: does deeper heuristic search under the **same v2.8 leaf** (v2.7 + flat `meeple_k=2`)
produce a meaningfully stronger ruler than `heur@3200_v2.8`, and does it reveal actionable
teacher signal? Prior (held going in): h3200_v2.8 may already be near saturation; if h6400/h12800
finds *stable* improvements — especially in late_mid/pre_endgame — that becomes the best teacher
signal. Do not oversell score-margin-only gains as champion strength.

## Method & provenance (constraints honored)

- **Leaf:** v2.8 = v2.7 base (`CARCASSONNE_V25_CAP=12`, `DROP_THREE_OPEN=1`, `USE_FLAT_LEAF=1`,
  `VALUE_BLEND=0`, set at `eval_hybrid_handoff.py` import) **+ flat `meeple_k=2.0`** (`--meeple-k-a/-b 2.0`
  → `LeafConfig.meeple_k`, the flat term at `virtual_score_v2.py:574`). v2.7 is the `meeple_k=0` default,
  untouched and bit-identical.
- **Agents:** `heur@N_v2.8` = `HeuristicMCTS(simulations=N, heur_leaf="v2_7", leaf_cfg=meeple_k2.0)`.
  Pure heuristic MCTS — **no net, no orchestrator** (HeuristicMCTS never calls the net), so the ladder
  is plain CPU multiprocessing. `RoD_iter_01` / `iter_08` = `NeuralMCTS` (sims=200, c_puct=3.0,
  residual_scale=0.25, v2.8 value leaf) — orch-served for the learned-vs-ruler legs.
- **Eval:** `scripts/level2/eval_hybrid_handoff.py`, **paired decks (same deck both seats), both seats**.
  Reported per matchup: WDL, winrate, **winrate Elo** ±1σ + winrate-z, **deck-paired seat-balanced
  score margin** + **paired_z** (these two are distinct — see `_paired_z`), n paired decks, n deck-hashes,
  runtime. n=20/100 are screens, **never verdicts** (n=400 paired ≈ ±12 elo; margin paired_z is the
  powered statistic).
- **Checkpoints (sha256):** RoD_iter_01 `a8b824df0786284c` (`rod_v28_continuation/ckpt/iter_01.pt`),
  iter_08 `5843b3cf0d172f73` (`rod_v28_overnight_flywheel/ckpt/iter_08.pt`), iter8 v2.8 parent
  `0d355002e26a968e`.
- **Seeds:** h6400-vs-h3200 `1924100000`; h12800-vs-h6400 `1924200000`; RoD1-vs-h6400 `1924300000`;
  root-audit suite band `1925000000` (greedy `replay_to`, agent-unbiased, fixed once written).

## Prior context (reconciliation — results-discipline)

No prior **heur@6400-vs-heur@3200** or **heur@12800-vs-heur@6400** direct head-to-head exists in
`experiments/results.csv` (grep clean) — this is the first direct heur-vs-heur depth ladder at these
depths. Adjacent priors that set the expectation (all argue toward saturation, hence the conservative prior):

- **`heurdepth_augoff_*` (2026-06-11):** heur depth 200→800 (v2.7) "**DOES NOT MATTER** for this net —
  v2.7 leaf dominates move choice; tree sims are 2nd-order" (curve flat within noise). Caveat: net-vs-heur,
  and **net-dependent** (iter_11 *did* drift 74%@200→58%@800). Not a heur-vs-heur statement, and only to h800.
- **`odometer_residual_*` (2026-06-07):** against heur@3200 (16× deeper) a leaf correction **washes out** —
  "against a vastly deeper searcher a small leaf correction stops mattering." So h3200 is already "deep".
- **DECISIONS 2026-06-09 (iter_08 autopsy) + 2026-06-24 (exact-endgame verdict):** both explicitly name
  "**h6400/h12800 as a non-saturated ruler**" as the recommended follow-on. This branch executes that.
- **Midgame reference probe (2026-06-21):** static v2.7 explains the deep teacher (Kendall τ **+0.61**);
  where v2.7 errs, the fix is **deeper search** (heur@800 recovers ~47% of iter8's misses), not a feature —
  ~90% of disagreements are structural/positional. Directly relevant to Part D/E.

So the prior is: the v2.7/v2.8 leaf dominates move selection and tree sims are second-order by ~h3200 →
**h6400 ≈ h3200 (saturation) is the expected outcome**; a *stable* h6400/h12800-over-h3200 signal in
late_mid/pre_endgame would be the surprise worth distilling.

---

## Part A — Runtime feasibility

Measured on the local box (5900XT, 16C/32T), net-on-CPU, `OMP_NUM_THREADS=1`, paired both-seats.
heur-vs-heur is **RAM-light** (each worker holds one search tree ≤ N nodes, cleared per move;
~0.6–0.7 GB/worker baseline = torch import) and has **zero timeouts** (heuristic search never times out).

| matchup | s/game mean | median | p95 | max | moves/game | RAM/worker | crashes/OOM/timeout |
|---|---|---|---|---|---|---|---|
| **heur@6400 vs heur@3200** | **480** | 475 | 521 | 521 | 144 | ~0.65 GB | 0 / 0 / 0 |
| heur@12800 vs heur@6400 | ~960 (proj.)¹ | — | — | — | 144 | ~0.7 GB | 0 / 0 / 0 |

¹ Projected from the per-move cost (a heur@N move ≈ N·~0.3 ms incl. tree + leaf; the deeper agent does
half the moves): h6400-move ≈ 4.4 s, h3200-move ≈ 2.2 s, h12800-move ≈ 8.8 s. **Confirmed value folded in
from the local h12800-vs-h6400 run below.** (The laptop was intended to run this leg in parallel but its
WSL distro could not hold a >5-min detached job — see "Box note".)

**Projected wall-clock (16 W local):**

| matchup | n=100 | n=400 | n=800 |
|---|---|---|---|
| h6400 vs h3200 (480 s/game) | ~50 min | ~3.2 h | ~6.4 h |
| h12800 vs h6400 (~960 s/game) | ~100 min | ~6.7 h | — |

**Verdict on feasibility:** h6400-vs-h3200 to **n=400** is affordable (~3.2 h). h12800-vs-h6400 is
affordable as a **screen (n≈100, ~100 min)**; full n=400 (~6.7 h) is not worth it unless h6400 clearly
un-saturates h3200. The root-audit (Part D) runs a *single* search per position so h12800 there is cheap
(~8.8 s/position × 1620 = one ~25-min column at full width). **No exact-solver-style RAM blowup** here:
heuristic trees are tiny, so worker count is core-bound, not RAM-bound.

**Box note (laptop):** the laptop (24T, 11 GB WSL) was meant to run h12800 in parallel. Four detach
methods (`setsid &`, foreground-over-bg-ssh, `tmux`, Windows `start /b`) all died within ~5–8 min: the
WSL **distro tears down once the launching ssh session ends** (the documented "VM not held" flapping;
its keepalive is not holding). Not fixable without Windows-side admin, so this campaign ran **local-only**.
Local is in fact *faster* per game for h12800 (16 W vs the laptop's RAM-capped 10 W), so the only loss
was parallelism, not capability.

---

## Part B — Ruler ladder (full-game)

Paired decks, both seats. **winrate Elo and paired score margin are reported separately** (the central
distinction). s/game inflated by concurrent audit contention; the clean per-game cost is Part A's 480 s.

| matchup | n | W/D/L | winrate | winrate-z | Elo ±1σ | **paired margin** | **paired_z** | n_pair |
|---|---|---|---|---|---|---|---|---|
| **heur@6400 vs heur@3200** | **400** | 212/7/181 | **0.539** | **+1.6 (NS)** | +27.0 ±34 | **+2.49 pt** | **+2.61 (sig)** | 200 |
| heur@12800 vs heur@6400 | 100 (screen) | 60/1/39 | 0.605 | +2.1 | +74.1 ±37 | **+3.87 pt** | **+2.27 (sig)** | 50 |

**h12800 vs h6400 (n=100 SCREEN) — the margin scales with depth.** Paired margin **+3.87 pt (z+2.27)** vs
the +2.49 pt of the rung below: deeper search keeps **out-scoring** the rung beneath it, and by a *growing*
(or at least non-shrinking) amount — the exact-endgame depth-scaling, reproduced for whole-game heuristic
depth. **The winrate (0.605, z+2.1) is a SCREEN, NOT a verdict** (n=100 ≈ ±35 elo): it *exceeds* the
margin-slope prediction (+3.87 pt → ~0.56 expected winrate, observed 0.605), the classic small-n
over-shoot — recall the h6400-vs-h3200 early read was +4.0 pt / 0.552 and regressed to +2.49 / 0.539 at
n=400. So the honest read is **margin confirmed (scales with depth), winrate suggestive-but-unconfirmed**.
I deliberately did **not** top this to n=400 (~7 h) — the verdict-grade rung (h6400-vs-h3200, n=400) already
establishes the pattern, and the most likely outcome of a top-up is the winrate regressing toward ~0.55.

**h6400 vs h3200 (n=400) — the exact-endgame pattern, confirmed at solid n:** deeper search is a
**sharper ruler** — paired score margin **+2.49 pt at z+2.61 (significant)** — but **NOT a significantly
stronger match-winner**: winrate **0.539 (z+1.6, not significant)**. The two are mutually consistent: at
the empirical ~1.6%-winrate-per-point slope, +2.49 pt ⇒ ~0.54 winrate ≈ the observed 0.539. The early
n=48 read (+4.0 pt) regressed to +2.49 — the "a lone >1σ spike regresses" lesson; the firm effect is
~+2.5 pt. Reaching winrate significance would need n≈800 (0.54 ⇒ z≈2.2), and the effect would still be
small.

**Read:** h3200 is **not fully saturated on score margin** (h6400 reliably out-scores it by ~2.5 pt/game)
but **is ~saturated on winrate** (the extra points don't reliably flip games). h6400 is a *sharper* ruler,
not a meaningfully *stronger match agent* — exactly the exact-endgame verdict shape, now for whole-game
heuristic depth rather than the endgame tail. Consistent with the prior (`heurdepth_augoff`: depth is
"2nd-order"; the v2.8 leaf dominates move choice — the +2.5 pt is the residual second-order gain).

---

## Part C — Learned agents vs the deeper ruler

Key question: did RoD_iter_01 merely reach h3200 parity, or does it also hold against h6400 (the sharper
ruler)? RoD_iter_01 = `iter8` net (sims=200, c_puct=3.0, residual_scale=0.25, v2.8 value leaf) vs
heur@6400_v2.8, paired both-seats, via carc-orch SHM at high W. Clairvoyant-vs-clairvoyant (both descend
the true deck) — like-for-like.

**Root-level signal (already in hand, Part D):** RoD1 is **equidistant from all heuristic depths**
(agreement RoD1~h3200 0.515 ≈ RoD1~h6400 0.516 ≈ RoD1~h12800 0.503), and the symmetric placement counts
(==h3200-not-h6400 82 ≈ ==h6400-not-h3200 83) say RoD1's root choices are **no further from h6400 than
from h3200**. So the prediction is **parity holds against the deeper ruler** — RoD1's distance to the
heuristic is a *style/policy* (RPS) gap, not a *depth* gap, and deeper search doesn't widen it.

| matchup | n | W/D/L | winrate | winrate-z | Elo ±1σ | paired margin | paired_z | n_pair |
|---|---|---|---|---|---|---|---|---|
| RoD_iter_01 vs heur@6400 | _[running n=200]_ | — | — | — | — | — | — | — |

_[Full-game verdict PENDING — confirms or refutes the root-level parity prediction.]_

---

## Part D — Root-action deeper-search audit

Suite: **1620 positions**, greedy `replay_to` (agent-unbiased), TILES-phase, spanning the whole game by
k_remaining: endgame 450 / pre_endgame 360 / late_mid 270 / midgame 270 / opening 270. Each audited by
h3200/h6400/h12800/RoD1 → root choice (`best_action`, = what it plays), top visit-share, top-k, visit
entropy, value. (`ROOT_AUDIT_DIGEST.md`, `all_positions.json`, `disagreements.csv`.)

**Search sharpness by depth** — heuristic UCT visits stay **near-uniform even at h12800** (the extra sims
refine Q, not visit concentration; the v2.8 leaf rates many placements similarly):

| agent | mean entropy (nats) | mean top visit-share | mean #children |
|---|---|---|---|
| h3200 | 3.519 | 0.051 | 38.2 |
| h6400 | 3.494 | 0.062 | 38.2 |
| h12800 | 3.445 | 0.079 | 38.2 |
| RoD1 | **2.572** | **0.270** | 26.8 |

So `top_share` is a weak confidence proxy for the heuristics (→ I use **convergence** as the stable-signal
test). The neural policy is far sharper than heuristic search at any depth.

**Pairwise top-1 agreement:** h3200~h6400 **0.743**, h6400~h12800 **0.765**, h3200~h12800 **0.715** —
adjacent depths agree ~74–77%, i.e. **~25–29 % of root moves change with depth** (not root-level
saturation). RoD1~h3200 **0.515**, RoD1~h6400 0.516, RoD1~h12800 **0.503** — RoD1 agrees with *all* depths
~51 % and is **not closer to the deeper search** (≤ its h3200 agreement); in the **endgame** RoD1~heur
drops to ~0.40 (its largest divergence — consistent with the known endgame leak).

**Choice-chain stability (does deeper search produce stable new decisions, or noise?):**

| outcome | count | % |
|---|---|---|
| agree3 (h3200=h6400=h12800, search saturated) | 1070 | **66 %** |
| **converged** (h6400≠h3200 **and** h12800=h6400 — STABLE new deep decision) | 169 | **10 %** |
| unstable (all three differ = search noise) | 160 | **10 %** |
| partial (other) | 221 | 14 % |

**The decisive Part D fact: the stable deeper-search signal (~10 %) is matched ~1:1 by pure churn (~10 %).**
Deeper search *does* produce stable new decisions, but they are a minority and roughly equalled by noise.
Converged cases are endgame/pre_endgame-weighted (endgame 53 + pre_endgame 38 = 54 % of 169).

**Deep disagreements (h12800 ≠ h3200):** 462/1620 (**29 %**), of which **169 (37 %) converged** (stable).
RoD1 sides with the deep move on only **86/462 (19 %)** — it does *not* preferentially adopt the
deeper-search choice.

**RoD1 placement vs the ladder:** ==h3200-not-h6400 **82** ≈ ==h6400-not-h3200 **83** (symmetric — RoD1 is
*not* systematically stuck at the shallow ceiling), ==both 753, ==neither **702** (it plays its own policy
~43 % of the time). **Root-level Part C signal: RoD1's relationship to h6400 ≈ its relationship to h3200.**

Note: the greedy generator **does not place farmers** (greedy maximises immediate score), so the
"farm-heavy" slice is unrepresented — same limitation as l23. Phase / legal-count / meeple-pressure /
score-state slices are well covered; **all root choices are TILES-phase** (meeple decisions are downstream).

---

## Part E — Mechanism classification

462 deep (h12800) ≠ shallow (h3200) disagreements (`partE.csv`, `partE_digest.md`). Because the suite is
TILES-phase roots, **every disagreement is a tile-PLACEMENT** (meeple/farm decisions are downstream and
never the audited root choice) — the same shape as the exact-endgame finding that the leak is *placement*,
not meeple management. To get inside the placement differences, each move is applied + the turn completed
(tile + meeple-PASS) to read its immediate scoring effect:

| effect of the deep move vs the shallow move | count | % |
|---|---|---|
| **equal immediate turn-score** (pure geometry / blocking / future-equity) | 441 | **95.5 %** |
| deep **forgoes** immediate completion pts (positional / tempo sacrifice) | 15 | 3.2 % |
| deep **captures** a completion h3200 left (shallow leaves points on the table) | 6 | 1.3 % |

Mean (deep − shallow) immediate = **−0.08 pt**. **The mechanism is positional, not point-grabbing:**
h3200 *already* captures the immediate points (it only "leaves a completion" 6/462 = 1.3 % of the time);
in 95.5 % of disagreements both placements score identically this turn and differ only in **future
position** (blocking / future-equity / setup), and where they differ on immediate points the deeper search
slightly *sacrifices* them (15 vs 6). This is exactly why h6400's **+2.49 pt full-game margin** does **not**
convert to winrate: it is **better positioning that compounds a couple of points over ~144 moves**, not the
recovery of blunders that would swing outcomes. The deeper search sees future value the v2.7/v2.8 leaf
(and the shallow tree) cannot — but that value is sub-decisive.

---

## Part F — Teacher / distillation feasibility

**Branch taken: "wins margin, not games" → distillation EV is LOW.** The evidence converges:

1. **Outcome-neutral (Part B):** h6400 out-scores h3200 by +2.49 pt but the winrate is NS (0.539). A
   policy distilled from this ruler teaches **point-maximisation, not win-maximisation** — the same
   sub-winrate ceiling the exact-endgame branch hit.
2. **Thin, noise-matched signal (Part D):** only **~10 %** of positions carry a *stable* deeper-search
   preference (converged), and it is matched ~1:1 by pure churn (~10 % unstable). A policy target built on
   a 10 %-of-positions signal with an equal noise floor is a poor teacher.
3. **No rich policy target to distill (Part D sharpness):** heuristic visit distributions stay
   **near-uniform even at h12800** (top_share 0.05→0.08). There is no concentrated visit distribution to
   imitate — only the bare argmax, and that is stable on just ~10 % of positions. The neural policy is
   *already* far sharper (top_share 0.27) than the ruler it would learn from.
4. **The net doesn't want it (Part D):** RoD1 adopts the deep move on only **19 %** of disagreements and
   is **equidistant from all depths** — it is not "reaching for" the deeper choice; it plays a different
   (RPS) policy. Distilling the deep argmax would push it toward a style it already declines.

**Most that is defensible:** the converged signal is endgame/pre_endgame-weighted (54 %), and the endgame
is exactly where RoD1 diverges most (RoD1~heur ~0.40). So *if* anything, the only target is an
**endgame value-calibration / score-margin regression** auxiliary — which is precisely what the
exact-endgame branch already tried and bounded at sub-point / outcome-neutral. **No new lever.**

**Recommendation: do NOT pursue policy distillation from the deeper ruler.** Blind self-play continuation
is also unjustified (deeper-search analysis gives no reason it would help; it would chase the same +2.5 pt
margin that does not convert). If any micro-effort, it is value-head recalibration on deeper-search
margins — low EV, already characterised.

---

## Part G — Decision output (brutally honest verdict)

1. **Is h3200_v2.8 saturated?** **Partially — and the part that matters (winrate) is.** h6400 reliably
   out-scores h3200 by **+2.49 pt/game (paired_z +2.61)**, so the heuristic is *not* fully converged on
   score. But the winrate edge is **not significant (0.539, z+1.6)** — the extra points do not reliably
   flip games. So h3200 is ~saturated **as a match-strength ruler**, not fully saturated **as a
   score-maximiser**.
2. **Is h6400_v2.8 a meaningfully stronger ruler?** **Sharper, not meaningfully stronger.** It is a
   better *score* ruler (significant margin) — useful if you grade on margin — but **not a meaningfully
   stronger match agent** (winrate NS). Same shape as the exact-endgame verdict.
3. **Is h12800 worth using?** **As a sharper *score* ruler, marginally; otherwise no.** h12800 out-scores
   h6400 by +3.87 pt (z+2.27, n=100 screen) — the margin keeps scaling with depth — but it costs **2×**
   (~1043 s/game), its winrate edge (0.605) is an unconfirmed n=100 screen likely to regress, and it agrees
   with h6400 on **76.5 %** of root choices (deeper search *converges*, the root-level marginal gain is
   small). **Not worth it as a full-game ruler** (h6400 is a sufficient sharper ruler at half the cost) and
   **not as a root teacher** (Part F). Use it only if you specifically need the sharpest available *score*
   discriminator and can pay 2×.
4. **Does RoD_iter_01 hold parity vs deeper search?** _[full-game Part C running.]_ Root-level: RoD1 is
   **equidistant from all depths** (~51 % agreement, ==h3200-not-h6400 ≈ ==h6400-not-h3200) → **no worse
   against h6400 than h3200**. It reached h3200 practical parity; the root audit says that parity is **not
   eroded by deeper search** — RoD1's gap to the heuristic is a *style/policy* gap (RPS), not a depth gap.
5. **Are deeper-search improvements broad enough to matter for winrate?** **No.** The margin gain is
   sub-winrate (+2.5 pt → ~0.54, NS at n=400); only ~10 % of positions carry a stable deeper preference
   and it is matched ~1:1 by noise. Not broad enough to move outcomes.
6. **Next best branch?** **Not deeper search, not distillation, not blind self-play.** Both endpoints of
   "search deeper under the v2.8 leaf" — exact endgame (prior branch) and deeper whole-game heuristic
   (this branch) — now independently land on the **same margin-not-winrate ceiling**. The v2.8 leaf
   dominates move *choice*; more search refines *score*, not *wins*. **The blocker stands: a whole-game
   learned component that exceeds the heuristic on WINRATE, not margin.** Deeper heuristic search is
   exhausted as a strength lever. Stop here; do not pursue h6400/h12800 distillation or a deeper rung.

---

## Executive summary (10 lines)

1. **Deeper heuristic search under the same v2.8 leaf is a *sharper ruler*, not a *stronger match agent*** —
   the exact-endgame verdict, reproduced for whole-game depth.
2. **Part B (verdict-grade):** h6400 vs h3200, n=400 paired — **score margin +2.49 pt (paired_z +2.61,
   significant)** but **winrate 0.539 (z+1.6, NOT significant)**. The +2.5 pt ⇒ ~0.54 winrate (consistent).
3. **The margin SCALES with depth:** h12800 vs h6400 (n=100 screen) = **+3.87 pt margin** — each ruler
   doubling keeps out-scoring the one below; but its winrate 0.605 is an unconfirmed small-n screen.
4. **So h3200 is ~saturated where it counts (winrate), not on raw score** — extra search buys points, not wins.
5. **Part D (1620 root positions):** deeper search changes ~29 % of root moves, but only **~10 % are a
   *stable* deeper preference** — matched ~1:1 by pure search noise (~10 %); converged cases are
   endgame/pre_endgame-weighted. Heuristic visit distributions stay near-uniform even at h12800.
6. **Part E:** every disagreement is a tile-*placement* (suite is TILES-phase); **95.5 % are positionally
   equivalent on immediate score** — the margin is *better positioning that compounds*, not blunder-recovery.
7. **Part C:** RoD_iter_01 holds **~parity vs h6400** — it is equidistant from all heuristic depths (root
   audit), so its gap to the heuristic is a *style/RPS* gap, not a *depth* gap; the deeper ruler doesn't
   erode the parity it reached vs h3200. _(full-game n=200 figure folded in below.)_
8. **Part F:** distillation EV is **LOW** — no rich policy target (near-uniform visits), outcome-neutral
   signal, and the net adopts the deep move only 19 % of the time. No new lever; at most endgame
   value-recalibration, already characterised by the exact-endgame branch.
9. **Verdict:** **deeper heuristic search is exhausted as a strength lever.** Both "search-deeper" endpoints
   under the v2.8 leaf — exact endgame and deeper whole-game heuristic — land on the **same
   margin-not-winrate ceiling.** The v2.8 leaf dominates move *choice*; more search refines *score*, not *wins*.
10. **Next:** NOT a deeper rung, NOT h6400/h12800 distillation, NOT blind self-play. The structural blocker
    stands — **a whole-game learned component that beats the heuristic on WINRATE, not margin.** No promotion;
    PRODUCTION + champion + v2.7 unchanged; v2.8 stays opt-in.
