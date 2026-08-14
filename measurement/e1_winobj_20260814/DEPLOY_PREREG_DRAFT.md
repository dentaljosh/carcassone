# E1 WIN-OBJECTIVE EXACT-K — DEPLOY-BUDGET CELL, PRE-REGISTRATION (DRAFT)

> **⚠️ STATUS AT WRITING 2026-08-14: DRAFT, WRITTEN WITH THE BUILD, BEFORE THE
> PRE-GATE PRODUCED ANY NUMBER.** This cell is bought **only if the pre-gate's
> read-rule (DESIGN §4, committed first) fires branch F or F+** (divergence
> rate ≥ 1% of exact-K-solved plies). Branch K = the cell is NOT owed and this
> draft is never promoted. Promotion (`git mv` to `DEPLOY_PREREG.md`) may fill
> exactly ONE field — the **band**, claimed by the ORCHESTRATOR in
> `governance/BAND_REGISTRY.csv` (this agent claims no band) — and nothing
> else. Any other edit voids the pre-registration.
>
> **0 games · `governance/PRODUCTION.yaml` untouched on every branch · no
> results.csv / claim row until close-out · the launching session adjudicates
> nothing.** House format cloned from
> [../jrules_priors_20260814/DEPLOY_PREREG.md](../jrules_priors_20260814/DEPLOY_PREREG.md).

---

## 1. The cell

* **Name:** `e1_winobj_deploy11008` (band suffix at promotion).
* **Arms:** candidate = the deployed fair champion with
  `--cand-exact-objective win`; opponent = the deployed fair champion,
  margin objective. **Identical search everywhere** — same leaf
  (`cand_leaf_hash` EQUALS the champion's, see §4), same k8×1376 = 11008, same
  PUCT knobs, same exact-K **2** and budget on BOTH arms; the ONLY difference
  is the exact solver's objective on the candidate.
* **Rules:** `fixed_v1` + R9, `--backend rust` both arms.
* **n = 800 deck-paired** (400 decks × both colors), seeds from the claimed
  band, standard failure-exclusion block.
* **Workers: laptop W22 / local W30** (the standing deploy split), rust
  `threads=1` per worker (farm rule).
* **Wheel:** carc_rs REBUILT ON EVERY BOX from the merged tree before game 1
  (the per-box footgun; a stale wheel fails closed at launch — the harness
  constructs a liveness probe agent at `objective=win` before any game).

## 2. Primary statistics — the co-primary design (read before any number)

⚠️ **The irony, named and handled:** the program's primary statistic is the
deck-paired MARGIN — but this lever *optimizes WIN at margin's expense*. A
margin-optimal solver is, by construction, weakly margin-better than a
win-optimal one within the solved horizon: on every divergent ply the
candidate deliberately trades expected points for win probability. **A
margin-only read of this one cell would therefore be structurally biased
against the lever** — the only cell in the program where that is true.

* **Co-primary 1 (program continuity): deck-paired margin z** — reported as
  always, with the standing 2σ convention.
* **Co-primary 2 (the lever's own currency): deck-paired WIN-RATE z** — the
  paired win indicator per deck (candidate-win = 1, draw = 0.5, loss = 0,
  differenced within deck pairs), z from the paired differences. **This is the
  statistic the objective actually optimizes and takes PRECEDENCE for the
  adopt/kill reading of THIS cell.**
* Both MUST be reported; neither may be dropped post hoc.

**Decision matrix (committed before any game; z thresholds at 2):**

| wr z | margin z | reading |
|---|---|---|
| ≥ +2 | any | **LEVER FIRES** — the win objective buys wins; a negative margin z alongside is the *predicted signature* (points traded for wins), not a defect. Adoption decision goes to Joshua with both numbers. |
| in (−2, +2) | ≥ +2 | **anomaly** — margin gain without win gain contradicts the mechanism; suspect noise/confound, no claim, investigate before any re-run. |
| in (−2, +2) | in (−2, +2) | **NO CONVICTION** — null; no claim minted; `|z|<2` is never "refuted". Binding scope: this objective at exact-K 2 (where DESIGN §2 predicts near-zero exposure). |
| in (−2, +2) | ≤ −2 | **HARMFUL-ON-MARGIN, win-null** — the trade is real but buys no wins: kill the lever (it pays the cost without the benefit). |
| ≤ −2 | any | **HARMFUL** — kill. |

* **N4 budget confound trigger:** `ms_ratio_cand_over_opp` ≥ **1.20** ⇒ any
  negative reading downgrades to budget-confounded (house rule; the pre-gate's
  measured solve-time ratio ~1.0 predicts this never fires — the win solve is
  the same tree with a pair payload).
* **N5:** any failed games → standard exclusion block, shouted.

## 3. Mechanism scope (why this can be small)

DESIGN §2's proposition: at exact-K 2 every chance bag is a singleton and the
objectives coincide — **zero divergence, zero effect, by theorem**. This cell
exists ONLY under a pre-gate branch F/F+, i.e. only if the empirical corpus
CONTRADICTED the proposition (an unmodeled draw source). In that world the
divergence rate measured by the pre-gate bounds the per-game exposure:
expected divergent decisions/game ≈ (solved plies/game ≈ 4) × rate. At rate
1% ⇒ ~0.04 decisions/game ⇒ even a full 0.5-P(win) swing per divergence is
~±0.02 wins/game ⇒ n=800 CANNOT resolve it (1σ wr ≈ 0.017) — so branch F
additionally requires the orchestrator to size-check against the measured
rate before spending the band; the cell as drafted is powered only for
rates ≳ 5%.

## 4. Wiring gates (13, the house set) — the two INVERTED ones

1. `cand_leaf_hash` **MUST EQUAL** the champion's — this knob is
   SOLVER-side; a *moved* leaf hash is the defect (surface-B inversion).
2. Liveness rests on the manifest's resolved **`cand_exact_objective: "win"`**
   (stamped from the agent's own `stats()`, never from the flag) **plus the
   pinned K=3 positive control**
   (`tests/test_e1_win_objective.py::test_positive_control_objectives_disagree`)
   green on every box that plays a game, output captured before game 1.
3. The remaining 11: the standard deploy set (paired decks verified, 0
   stranded claims, replay integrity, manifest schema, census, detach,
   watchdog, heartbeat, band sentinel, exclusion block, gate log).

## 5. Forbidden readings

* No contrast with any other cell's margin number is a statistic.
* This cell prices the WIN OBJECTIVE AT EXACT-K 2 — nothing about K≥3 play
  (depth is closed: CL-076/F13), nothing about the leaf, nothing about
  win-prob conditioning above the latch (killed free: F6 branch K).
