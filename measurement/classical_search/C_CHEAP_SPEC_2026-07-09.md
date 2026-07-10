# C-cheap BUILD SPEC — deck-aware value head to shrink the fair clairvoyance tax

**Status: DESIGN / PRE-REGISTRATION (read-only recon, 2026-07-09).** No code written, no training run.
**Thesis (Fable reframe):** PIMC only *samples* the hidden deck (k_dets determinizations, average Q). A **learned, deck-aware value** could *marginalize* deck uncertainty in its weights — learn `E[value | position, remaining-bag-multiset]` — and thereby raise **FAIR** strength / shrink the ~120-elo clairvoyance tax. Target is **fair play strength**, NOT "beat the heuristic on offline accuracy."

⚠️ **Headline caveat found during recon (this reshapes the recommendation):** the cheap *offline* version of this experiment has **already been run and returned NULL** — see §6. The only un-refuted surface is a **direct fair-play A/B with the value inside the search loop**. Recommendation is therefore a *bounded* cheap shot, sequenced behind E4/A-small, with a hard pre-registered kill. See §7–§9.

---

## 1. Net architecture + input — where deck-awareness lives (ALREADY BUILT)

- **Net:** `CarcassonneNet` — 6×96 ResNet, policy + value + aux ownership heads (`src/carcassonne_ai/network.py:56`). Value head: `value_project` 1×1 conv → flatten → **cat(scalars)** → `value_fc1`→relu→`value_fc2`→tanh (`network.py:108-142`). Optional **KataGo-style global pool** (`value_global_pool`, `network.py:83-90,116-117,136-138`) that injects `cat[trunk.mean, trunk.amax]` into the value head — **exactly the board-global integrator a deck-aware value wants; default OFF, turn it ON for C-cheap.**
- **Board input:** `board_repr.encode_board` → `(N_CHANNELS=78, 25, 25)` (`board_repr.py:107,315`). Scalars: `features.encode_scalars` → **10** floats (`features.py:38`), incl. `tiles_remaining/72` as a **scalar only** (`features.py:13,128`). **No per-tile-type bag histogram in the production path** — confirms foundational_audit F-B3 (`docs/research/foundational_audit_2026-06-02.md`): "only a scalar `tiles_remaining/85`; NO per-tile-type remaining-count vector anywhere. The net cannot represent draw-expectation… even in principle."
- **Deck-aware representation is ALREADY IMPLEMENTED** (built for M2 canonical-AZ, `src/carcassonne_ai/sighted_planes.py`):
  - `bag_histogram(state) -> (32,)` — per-base-tile-type **fraction of that type still in the bag** (deck + next_tile in TILES phase), `[0,1]` (`sighted_planes.py:176-194`). The 72-tile / 32-type census is frozen (`sighted_planes.py:45-87`). **This is a FAIR feature** — the remaining *multiset* is public (deducible by tile-counting); only the *order* is hidden. So it is legal at fair play time.
  - `farm_connectivity_planes -> (3,W,W)` — per-cell live farm ownership (`sighted_planes.py:138-173`).
  - Wired end-to-end via `Game(sighted=True)`: `game_wrapper.py:302-309,354-372,582-595` appends **+3 board planes → 81ch** and **+32 scalars → 42-scalar** (`bag_histogram` concatenated onto scalars, so it feeds the value head directly). `warmstart.py:359,386,434` and the orchestrator (`shm_eval_handles.py:12-18` — "CHANNELS/SCALARS ARE RUNTIME-CONFIGURABLE… sighted 81ch/42-scalar nets get their own exact-fit layout") already accept it → **batched net-value fair eval on the 5900XT via carc-orch is supported.**

**Verdict on Q1:** nothing new to *build* for deck-awareness — the bag histogram + sighted net (81ch/42-scalar) exist and are plumbed. The only arch tweak worth making is `value_global_pool=True` (board-global bag/tiles integration).

---

## 2. Data — what fair labels we need, and cost

C-cheap's genuinely-**new artifact** is a value head trained on **FAIR self-play OUTCOME labels on the deck-aware representation.** This does NOT exist yet:
- §4A (`measurement/probe_b_4a/`) trained sighted heads on **fair@800 matched-depth root-Q** targets (not full-game outcomes) — and found them inert (§6).
- M2 (`CL-042`) trained a full sighted AZ net on `score_diff_wide` outcomes but from **CLAIRVOYANT** self-play (MCTS descends the true deck → the F-B2 train/serve info mismatch: "value labels encode unlearnable information", `foundational_audit` F-B2). τ stayed flat 0.018–0.023.

The new regime removes F-B2: **generate fair (blind-determinization) self-play, so the value learns the fair value function under the same info it is deployed with.**

- **Generator:** the **heuristic** fair champion `FairHeuristicMCTSAgent` / `FairHeuristicPriorAgent` (`fair_agent.py:148,291`) played against itself. This is **NET-FREE** (pure CPU heuristic leaf) → **laptop + xeon fan-out eligible** (`nice -n 19`, work-steal). Record per ply: sighted obs (81ch), scalars-with-bag (42), FAIR game outcome → `score_diff_wide` target `tanh((p0-p1)/40)` (de-saturated per F-C2, `selfplay.py:137,544`).
- **Gen-cost reality check (this is the one real cost):** fair self-play is expensive per game — each move runs `k_dets×sims` searches. At the deployed `k_dets=8×sims=344` that is ~22k sims/move × ~70 moves ≈ **1.5M sims/game**. Keep the *data* config CHEAP (`k_dets=4, sims=128` ≈ 0.36M sims/game — the value target is the game outcome, not a strong move) and cap at **~1–2k games** for the first head. Ballpark a few box-hours net-free across laptop+xeon.
- **Cheaper fallback (near-zero gen):** reuse `measurement/probe_b_4a/shardA.jsonl` (fair@800 root-Q on the 10,067-root pool, already on disk) as value labels via the existing `retarget_4a.py` pipeline. **But §6 shows those exact labels are offline-inert**, so this fallback only makes sense as a plumbing smoke, not the verdict head.

**Scaffolding needed (new):** one small **fair self-play emitter** script (~1 file, `scripts/canonical_az/gen_fair_selfplay.py`): play `FairHeuristicMCTSAgent` self-play, dump `(sighted_obs, scalars+bag, score_diff_wide)` npz. `selfplay.py` is clairvoyant/net-driven and cannot do this directly. Net-free, CPU-parallel.

---

## 3. Plumbing — how the value plugs into fair search, and the A/B swap point

- **Champion (clairvoyant) search core:** `HeuristicPriorAgent` wires a stateless evaluator `Callable[[Board] -> (priors[A], value)]` into `NeuralMCTS` (`heuristic_prior_mcts.py:1-38`). The evaluator is built by `make_heuristic_prior_evaluator` (`heuristic_prior_mcts.py`), whose value is **exactly one line**:
  ```python
  value = math.tanh(leaf_parent / norm)      # heuristic_prior_mcts.py, in evaluator()
  priors = softmax(Δleaf(a)/τ) over legal    # unchanged — priors were never the problem
  ```
- **Fair champion:** `FairHeuristicPriorAgent` (`fair_agent.py:291`) reuses that SAME evaluator across `k_dets` fresh per-determinization `NeuralMCTS` trees (`fair_agent.py:384,417-427`), pooling child (N,W) by pooled-Q (`pooled_q_argmax`). Determinizations reshuffle only the unseen deck order (`fair_agent.py:206,418`).
- **The C-cheap swap = replace the value line, keep the priors.** Build `make_heuristic_prior_evaluator_with_net_value(game, cfg, net)`: identical `_legal_deltas`/softmax priors, but `value = net_value(sighted_encode(board.state, mover))`. Feed that evaluator to `FairHeuristicPriorAgent` (add an `evaluator=` / `net=` param — currently it hard-builds the heuristic evaluator at `fair_agent.py:384`). **Small scaffolding: ~1 evaluator constructor + a `net=`/`evaluator=` hook on `FairHeuristicPriorAgent.__init__`.** Note: the bag histogram is order-invariant, so it is identical across the k_dets determinizations at a given ply — a legitimate fair signal that the deck-blind leaf cannot see.
- **Fair A/B harness EXISTS:** `scripts/classical_search/eval_fair_puct.py` already runs `--info {fair,clair}` for the champion vs a fixed h800 rung, deck-paired, with the marginalized exact-K endgame handoff (its header documents the whole A2 protocol). C-cheap adds a third arm: **fair + deck-aware net value** vs the SAME h800 rung on the SAME decks. Baseline to beat is already measured: **heuristic-value fair champion = fair +49.0 / z2.86 (CL-045)**; clairvoyant +205 → **tax ≈ 156 elo** (`results.csv:281-282`; tax persists ~100–150 across sims 800→5504, CL-048, `results.csv:296-299`).

---

## 4. Cheapest-informative first experiment

**Question:** *does a deck-aware learned value, used as the leaf value inside FAIR PIMC search, raise fair strength above the heuristic-value fair champion (i.e. shrink the tax)?*

**Do NOT re-run an offline sibling-rank gate** — §6 shows it is depth-saturated and burned null. Go straight to a bounded fair-play A/B:

1. **Gen (net-free, laptop+xeon):** `FairHeuristicMCTSAgent` self-play, `k_dets=4 sims=128`, ~1–2k games, dump sighted obs + bag scalars + `score_diff_wide` outcome. (~a few box-hours.)
2. **Train (local 5900XT, GPU-latency-bound):** value-only train of the **81ch/42-scalar** `CarcassonneNet` with `value_global_pool=True`, warm the trunk from `flywheel_residual_attempt2/ckpt/iter8.pt` (re-init the 81ch stem + value head; trunk transfers), `score_diff_wide` MSE. Tiny net, ~0.2 s/batch (memory `reference_training_latency_bound`) → minutes–~1 hr. Don't CPU-shop boxes; bigger batch is the only lever.
3. **Fair A/B (local 5900XT, orch-batched net value):** `eval_fair_puct.py` third arm — fair champion with the net value, `k_dets=8 sims=344 exact-k=2`, **vs h800 rung, n≈100–150 deck-paired**, `nice -n 19`. Compare fair-elo to the heuristic-value fair arm (CL-045 baseline) on the same decks.

**Gate (pre-registered):** deck-aware fair-elo − heuristic-value fair-elo **≥ +35 elo** (≈2σ at n=100 paired; `results.csv` n-threshold rules). 
- **FIRE →** the tax is partly a marginalization gap; escalate to a fair self-play *flywheel* (fresh fair gen with the net in the loop, cloud only if local iter-1 compounds).
- **NULL (|Δ| < ~1σ ≈ ±25) →** close C-cheap on the value-inertness ledger + §6; the tax is genuine missing information, not a marginalization inefficiency. Ship E4/A-small.

---

## 5. Cost, gates, and how this differs from the CLOSED distillation lever

**Cost (all local/LAN, no cloud):** gen a few box-hours (net-free) · train <1 GPU-hr · fair A/B a few GPU-hrs (orch-batched). **Total ≈ 1 cheap cluster-day.** Zero metered spend. Escalation to a fair flywheel (and only then, cloud) is gated on the +35-elo fire.

**Why this is NOT the closed distillation lever:**
- The closed levers were **policy/value DISTILLATION at 7M-warmstart** (`DECISIONS.md`: Option-2 value-head blend closed 2026-05-18 "a weaker evaluator than the hand-tuned v2.7 heuristic"; policy distillation DEAD-END CL-031; distillation-EV-LOW 2026-06-24). All targeted **"the learned net must match/beat the heuristic under CLAIRVOYANT search."** C-cheap's target is **fair strength / the tax**, a different objective the kills never measured — and Fable's premise-expiration audit explicitly reopened the learned track for *this* angle (`PROGRAM_ROADMAP_2026-07-07.md`).
- **The new ingredients:** (a) **deck-aware input** — bag histogram, information the v2.9 leaf *structurally cannot see* (CL-037 confirmed it carries offline signal vs a deep teacher); (b) **fair-outcome labels** — removes the F-B2 clairvoyant train/serve mismatch that the foundational_audit named the biggest value blocker; (c) **measured by fair PLAY**, not offline rank/clairvoyant drive.

**Risks / honest priors (LOW success prior):**
- **The offline gate is already burned null (§6):** at play depth (800), even *clairvoyant* targets give the sighted value **no residual over the v2.9 leaf** — the leaf is a depth-saturated near-perfect *ranker*. CL-037's non-inert signal needed an h6400 teacher. Since PUCT selection only uses *relative* Q, a value that can't out-rank the leaf offline is unlikely to out-play it in the loop. This is the strongest evidence against.
- **Mechanism weakness:** the v2.9 leaf is deck-blind, so within the fair ensemble the value is *identical* across determinizations; deck-averaging already happens via the search dynamics + pooled-Q. A deck-aware value only bites if it improves *absolute* leaf estimates in a way that changes *relative* Q — a narrow window.
- **Ledger:** 6+ independent value-inertness nulls across scalar/structured/clairvoyant/fair regimes (CL-029/032/033/036/038, Probe-A §3A, §4A). C-cheap is testing the *one* remaining un-probed cell (value **in** the fair loop, outcome-labeled), but the base rate is bad.
- **Confound:** "26 vs 156 tax" is partly era/strength-confounded (roadmap's own caveat); the tax magnitude is not a clean target size.

---

## 6. ⚠️ Decisive prior finding — the offline gate is ALREADY NULL (Probe B §4A)

`measurement/probe_b_4a/PROBE_B_4A_RESULTS.md` (CONCLUDED 2026-07-01) ran **exactly the cheap offline version of C-cheap**: train the sighted head (bag + farm) on **fair@800** vs **clair@800** matched-depth targets, same 10,067 sibling sets, same v2.9 leaf, one variable = clairvoyance.
- **FULL-N (n_test=1544): all six arms INERT** — `best_α=0.0, regret_reduction +0.0%, beats_leaf=False` (fair bag-only net-alone τ=0.040). "**§4A is DEPTH-SATURATED and cannot isolate the clairvoyance variable** — at matched *play* depth (800) even clairvoyant targets give the value no residual over the v2.9 leaf." CL-037's non-inert result required the deep h6400 teacher.
- Consequence for C-cheap: **the offline rank/residual gate is useless here** (leaf saturates it) → the ONLY informative test is the fair-PLAY A/B (§4). §4A did NOT test a deck-aware value *in the fair search loop against fair-outcome labels* — that single cell is what remains.

---

## 7. Files to create / modify (nothing written here)

| Action | File | What |
|---|---|---|
| CREATE | `scripts/canonical_az/gen_fair_selfplay.py` | net-free `FairHeuristicMCTSAgent` self-play → npz (sighted obs + bag scalars + `score_diff_wide`). ~1 file. |
| MODIFY | `src/carcassonne_ai/heuristic_prior_mcts.py` | add `make_heuristic_prior_evaluator_with_net_value(game, cfg, net)` — heuristic priors, net value. |
| MODIFY | `src/carcassonne_ai/fair_agent.py` | `FairHeuristicPriorAgent.__init__` accept `net=`/`evaluator=` override (currently hard-builds heuristic evaluator at :384). |
| MODIFY | `scripts/classical_search/eval_fair_puct.py` | third arm `--info fair-net --net <ckpt>` (sighted encode + net value); reuse the deck-paired h800 rung + endgame handoff. |
| REUSE  | `sighted_planes.py`, `game_wrapper.py(sighted=True)`, `warmstart.py(sighted=…)`, orch (`shm_eval_handles.py`) | deck-aware encode + sighted-net train + batched eval — all already exist. |
| REUSE  | value-only training via `warmstart.py`/`selfplay.py` `value_target="score_diff_wide"` | no new trainer. |

**Test coverage to add:** a bit-exact test that the net-value evaluator preserves the heuristic priors and only swaps value; a `sighted=True` encode-parity assert (already pinned by `sighted_planes` parity test). Fair-A/B smoke via `eval_fair_puct.py --smoke`.

---

## 8. Recommendation

**Worth a bounded cheap shot — but sequence it behind E4 and A-small, and pre-register a hard kill.** The full recon says: the deck-aware *input* and sighted net already exist (nothing to build there); the *offline* gate for this idea is already burned null (§4A depth-saturation) and the value-inertness ledger is 6+ deep; so the success prior is **low**. But the *one* un-refuted cell — a fair-outcome-labeled deck-aware value used **inside** the fair PIMC loop, graded on fair PLAY strength — has genuinely never been run, it is what the tax measures, and Fable's reframe explicitly sanctions "can deck-aware learned value beat the heuristic leaf at FAIR settings" as the right cheap experiment. It costs ≈1 cheap local cluster-day and zero metered spend. Do it as a single n≈100–150 fair A/B with the +35-elo pre-registered gate; do NOT stand up a flywheel or touch cloud until it fires. Given the roadmap already orders **E4 (fair exam) → A-small (endgame module) → C-cheap by appetite**, run E4/A-small first (higher EV); pull the C-cheap trigger only if appetite/curiosity remains after them.
