# Gate B — FAIR-PIMC depth transfer (VERDICT)

> **Status: CLOSED 2026-07-21. Verdict: the depth-decay of the prior channel REPLICATES
> under fair PIMC** — same direction, same magnitude, higher significance. The clairvoyant
> Gate-B result (`measurement/gate_b_depth_transfer/SUMMARY.json`) SURVIVES the
> clairvoyant→fair transfer that killed Gate A's oracle-prior screen (CL-059).
> Measurement gate only — no train / promote / redesign follows.
> Harness `scripts/measurement_infra/gate_b_fair_pimc.py`; canonical numbers in
> `SUMMARY.json` + `manifest.json` here; per-root records in `records/`.

## Apparatus

| | Clairvoyant Gate B (the record) | **This run (fair PIMC)** |
|---|---|---|
| harness | `scripts/measurement_infra/gate_b_depth_transfer.py` | `scripts/measurement_infra/gate_b_fair_pimc.py` |
| agent | `HeuristicPriorAgent` — clairvoyant champion core | **`FairHeuristicPriorAgent`** via `champion_factory.build_fair_champion` (the DEPLOYED agent) |
| info | descends the TRUE deck | k4 reshuffled determinizations (canonical-sorted unseen deck), fresh tree per world, pooled aggregation |
| roots | 354 × `measurement/f3_public_state_oracle/roots_k3_suite.jsonl` | **the same 354** (full suite, no subset) |
| levels | 200 / 344 / 688 sims | **the same, PER WORLD** (total 800 / 1376 / 2752) |
| final pick | `final_select="visits"` | `pooled_q_argmax` (**pooled-Q**, `min_pooled_visits=2`) — *and* pooled-visits recorded alongside for like-for-like comparison |
| snapshot | one deep search, bit-exact at every level | one deep search **per world**, bit-exact **within** each world |
| result | 354/354 ok | **354/354 ok, 0 errors** |

**Correctness.** (1) `--verify-bit-exact` ran on **all 354 roots** — every world's snapshot at
every level equals a standalone L-sim search of that same world (`bit_exact_within_world_all_match:
true`). Bit-exactness is claimed *within* a world only; the k4 worlds themselves are drawn once
from the production rng stream and held fixed across levels (a production agent at sims=200 draws
the same worlds, since the stream depends on seed+move index, not the sim budget). (2) A parity
test asserts the harness's deepest-level pooled-Q pick and pooled visit counts equal what a real
`FairHeuristicPriorAgent.choose_action` returns on the same root/seed
(`tests/test_gate_b_fair_pimc.py`, 6/6 pass). (3) `prior_favored` is identical to the clairvoyant
run on **354/354** roots (the reshuffle changes only unseen deck ORDER; the heuristic prior is a
function of the board) — so "prior survival" means the same thing in both columns.
(4) `n_exact_latch = 0`: the k3 suite sits at k_remaining=3, above the fair K≤2 marginalized
handoff, so the decision under test is **pure PIMC** — the endgame solver never fires.

**Cost.** 50.1 s/root mean (max 100.8 s) at W=8 *including* the 3× bit-exact re-verification;
≈17 700 core-seconds ≈ 4.9 core-hours, ~57 min wall on the local 5900XT. Without verification
≈ 6–20 s/root. ~4× the clairvoyant run's per-root work (k4 worlds), NOT the 20–60× feared — the
K≤2 solver never runs at k=3.

## Headline — side by side (n=354, same roots, paired)

| metric | level | clairvoyant (visits) | fair PIMC (visits) | **fair PIMC (pooled-Q = DEPLOYED)** |
|---|---|---|---|---|
| **agree shallowest_vs_deepest** (200v688) | — | 0.8475 | 0.8220 | **0.6864** |
| all_agree (200∧344∧688) | — | 0.8362 | 0.8079 | **0.6469** |
| **prior_survival** | 200 | 0.8588 | 0.8531 | **0.7006** |
| | 344 | 0.8333 | 0.8249 | **0.6554** |
| | 688 | 0.7599 | 0.7373 | **0.5763** |
| **mean top2_q_gap** | 200 | 0.05635 | 0.05953 | 0.05953 |
| | 344 | 0.05903 | 0.06587 | 0.06578 |
| | 688 | 0.06821 | 0.07496 | 0.07496 |
| **played_eq_q_argmax** | 200 | 0.8023 | 0.8164 | — |
| | 344 | 0.7768 | 0.7712 | — |
| | 688 | 0.7655 | 0.7599 | — |

Paired McNemar, prior survival 200 → 688:

| regime / rule | 200 | 688 | Δ | lost/gained | χ² | p |
|---|---|---|---|---|---|---|
| clairvoyant (visits) | 0.8588 | 0.7599 | −0.0989 | 40 / 5 | 25.7 | 4e−7 |
| fair (visits) | 0.8531 | 0.7373 | −0.1158 | 48 / 7 | 29.1 | 7e−8 |
| **fair (pooled-Q = deployed)** | 0.7006 | 0.5763 | **−0.1243** | 56 / 12 | 27.2 | 2e−7 |

## The selector-controlled comparison (the one that decides it)

The deployed fair rule is **pooled-Q**; the clairvoyant harness's headline rule is **visits**.
A naive read of the table above ("0.847 → 0.686 agreement!") confounds REGIME with SELECTOR.
Recomputing the clairvoyant run under **its own recorded Q-argmax rule** removes the confound:

| | 200 | 344 | 688 | agree 200v688 | McNemar 200→688 |
|---|---|---|---|---|---|
| clairvoyant, Q rule | 0.6921 | 0.6497 | 0.5763 | 0.6808 | 53/12, χ²=24.6 |
| **fair, pooled-Q rule** | 0.7006 | 0.6554 | 0.5763 | 0.6864 | 56/12, χ²=27.2 |

The two regimes are **indistinguishable under a matched selector** (they land on the identical
0.5763 at 688). So the entire apparent "fair is much worse" gap is the **visits-vs-Q selector**,
not clairvoyance. Fair PIMC neither rescues nor worsens the depth-decay; it inherits it.

## Read — mechanism split in the FAIR regime

* **Q-convergence — CONFIRMED, and STRONGER than clairvoyant.** The pooled top1–top2 Q-gap
  WIDENS with depth: +0.0193 mean paired change 200→688 (sd 0.098, **t = +3.10**, n=248), vs the
  clairvoyant +0.0104 (t = +1.99). Deeper search does not converge the top two moves together —
  it pulls one away, and the prior's pick is increasingly the loser.
* **Selector — NOT the driver.** `played_eq_q_argmax` drifts 0.8164 → 0.7599 in fair, essentially
  the same mild drift as clairvoyant (0.8023 → 0.7655). Visits and Q do not increasingly disagree
  with depth in either regime.
* **Early discovery — partly present.** Of the 111/354 roots where the deployed pick flips
  200 → 688, only 40 (36%) promote a move that was already in the shallow top-3 by pooled visits;
  the other 71 (64%) promote a move the shallow search had barely visited. So the fair regime has
  more genuine late surfacing than the clairvoyant read suggested, layered on top of Q-convergence.
* **The fair regime barely changes the SEARCH.** Fair-visits and clairvoyant-visits pick the same
  move on 0.9463 / 0.9322 / 0.9068 of roots at 200 / 344 / 688 — reshuffling the unseen deck and
  pooling 4 worlds moves the visit-based conclusion very little. What differs is the *final rule*:
  clairvoyant-visits vs fair-deployed-pooled-Q agree only 0.7825 / 0.7542 / **0.7175**.

**Bottom line.** The Gate-B NULL-leaning conclusion — *the heuristic prior channel's influence on
the final decision decays with depth, via Q-convergence* — **replicates under the deployed fair
PIMC agent, at the same magnitude and with higher significance.** Unlike Gate A, this finding is
not a clairvoyance artifact. A shallow policy/prior improvement should still be expected to wash
out at production depth in the fair regime.

## Caveats a skeptic should raise

1. **The deployed pooled-Q rule is intrinsically noisier than visits, and that alone lowers its
   depth stability.** The `min_pooled_visits=2` floor is effectively inert here (mean 29.2 pooled
   children at 688, 29.2 of them eligible), so a 2-visit action with a lucky Q *can* win. The
   deployed pick sits outside the pooled-visits top-3 on ~12% of roots (rank-1 on 76–82%). Some of
   the deployed rule's 0.686 depth agreement is that noise, not re-evaluation. The
   selector-controlled table above is the honest comparison; the raw headline is not.
2. **Worlds are held fixed across levels by design.** This isolates depth, but it means the run
   does not measure the *other* fair-mode variance channel (a different k4 draw). A production
   agent at a given seed/move draws the same worlds regardless of budget, so this is faithful —
   but "how much does the fair pick move if you redraw the worlds?" is a separate, unmeasured
   question, and it is plausibly comparable in size to the depth effect.
3. **One root band only.** All 354 roots are k_remaining=3 late endgame boards from greedy L2-3
   self-play. Depth-transfer at mid-game k≈20 is not measured, and the k3 band is exactly where
   Q-values are sharpest. The endgame solver never fires here, so nothing is said about the
   deployed agent's K≤2 behaviour.
4. **`top2_q_gap` is not identically defined across the columns** — clairvoyant pools nothing
   (single tree), fair averages Q across 4 worlds, which compresses per-world extremes. The
   direction (widening) and the paired t are comparable; the absolute levels are only roughly so.
5. **This measures a decision, not strength.** "The prior's pick survives less often at depth" is
   a mechanism claim. It does not by itself price how much elo a prior improvement would be worth
   at production depth.
