# Phase 5 — Residual / Value-Head Role Audit

> **Measurement only.** Champion unchanged. Isolates the iter8 net **value head** (the
> `residual_scale` lever) from the policy prior and the v2.7 leaf. Two clean comparisons:
> **(root)** the 1000-position root-action audit (resid 0.25 vs resid 0, paired same seed), and
> **(full-game)** a paired pilot `iter8@resid0.25` vs `iter8@resid0` on a fresh band. **FACT** vs
> **INTERPRETATION** kept separate; root teacher-imitation kept distinct from full-game Elo.

## What "residual" is (FACT)
Production leaf value = `clip( tanh(v2.7/15) + residual_scale · v_nn, ±1 )` with `residual_scale =
0.25` ([evaluators.py](../../src/carcassonne_ai/evaluators.py) `make_v25_value_wrapper`;
PRODUCTION.yaml). At `residual_scale = 0` the wrapper returns `tanh(v2.7/15)` and **discards the net
value `v_nn`** → the agent is "net policy prior + pure v2.7 leaf" (= ITER8_NORESID =
ITER8_POLICY_ONLY_LEAF_V27). So the residual head is the *only* place the learned **value** enters
search; the policy prior is untouched by this lever.

PRODUCTION.yaml calls 0.25 "the validated value-head lever, NOW folded in," with the decomposition
note "~95% policy, plateaued iter5" — i.e. iter8's strength is mostly the **policy**, and the
residual was a smaller, separately-validated value add. This audit re-measures it directly on the
iter8 net.

## (root) Does residual improve root-action agreement with the deep teacher? — FACT: no
From [ROOT_ACTION_AUDIT.md](ROOT_ACTION_AUDIT.md) §2 (paired, same seed, n=1000):
- prod==noresid root agreement **0.804** → residual **flips 19.6%** of root picks.
- prod vs teacher **0.487**; **noresid vs teacher 0.503** → removing residual **+0.016**.
- on the **196 flip** positions, noresid is teacher-right **0.219** vs prod **0.138** (≈1.6×).
- residual hurts **most in the endgame** (pre_endgame noresid 0.435 vs prod 0.390).

**INTERPRETATION:** at the per-move level the residual value head is **neutral-to-mildly-harmful**
for matching heur@3200 — it does not sharpen which move iter8 picks, and on the picks it changes it
is more often the worse one (vs the deep teacher). The residual does **not** recover iter8's misses
either (disagreement subset A recovery: noresid 0.084 — deeper search, not the value head, recovers
them).

## (full-game) Does residual improve outcome at equal budget? — pilot (paired, fresh band b360)
The decisive test, because root teacher-imitation is non-transitive with strength (iter8 beats
heur@800 full-game while losing to it on imitation). `iter8@resid0.25` vs `iter8@resid0`, identical
net forward, only the value blend differs (residual_pilot.py via carc-orch, local+laptop).

**Preliminary (n=20, 10 decks — NOISE-DOMINATED, z<0.4, not a verdict):** resid0.25 went 8W/0D/12L,
winrate 0.40, **−1.45 pts/game, paired z=−0.39** — directionally consistent with the root finding
(residual not helping), but n=20 cannot resolve a small effect.

**Verdict (n=200 paired, 100 decks, b360):** iter8@resid0.25 **110W / 0D / 90L**, winrate **0.55**,
**+1.945 pts/game**, **+34.9 elo**, **paired z = 1.518**
([FULLGAME_PILOT_RESULTS.csv](FULLGAME_PILOT_RESULTS.csv); finalize_pilot.py over all 200 per-game
jsons). Seat split: as seat0 +0.34 (elo +6.9), as seat1 +3.55 (elo +63.2) — strong seat/deck
interaction, which the seat-balanced paired statistic (z=1.518) absorbs.

> **FACT:** at the production depth (sims=200), the residual head is a **small POSITIVE full-game
> lever (+35 elo)** — it **reverses** the n=20 noise (−1.45) and is consistent with PRODUCTION.yaml's
> "validated value-head lever." **But z=1.518 is BELOW the 2σ verdict bar** (the project rule: a
> ~35-elo effect needs n=400 to be a verdict; z≈1.5 is "suggestive, inconclusive"). So the honest
> reading is **directionally positive, not statistically conclusive at n=200**.
>
> **INTERPRETATION — the non-transitivity, sharpened:** the residual head **hurts per-move imitation
> of the deep teacher** (root: noresid 0.503 > prod 0.487; flips worse) **yet helps full-game
> outcome** (+35 elo). The value head shapes whole-game play in a way that *wins games without
> matching heur@3200's top-1*. This is the same policy/strength non-transitivity that runs through
> the whole project. ⇒ **do NOT drop the residual** (it is a small net positive full-game), but it is
> **small** — the policy is the load-bearing component (PRODUCTION.yaml "~95% policy").

## Does residual help only at shallow search and wash out deeper? — INTERPRETATION
Not separately tested at deeper sims here (the sims-washout lesson predicts value/policy gains
shrink under deeper MCTS; residual is a *value* lever so the prediction is weaker than for policy).
The production plane is sims=200; the pilot is at 200, the production depth. A sims=800 residual
sweep is logged as optional future work, **not** run (cost; low prior given the root signal).

## Answers (INTERPRETATION)
1. **Does residual improve root-action agreement with the deep teacher?** **No** — it is
   neutral-to-harmful (noresid ≥ prod; flips are worse).
2. **Does residual improve full-game outcome at equal budget?** **Yes, small and suggestive** —
   +1.945 pts/game / +35 elo at n=200, but z=1.518 (sub-2σ; n=400 would confirm). Positive despite
   being neutral/harmful at the root.
3. **Shallow-only / washes out deeper?** Untested at depth; production plane (200) is what the pilot
   measures (positive there).
4. **Should future experiments treat iter8 primarily as policy, not value/residual?** **Yes** — the
   learned **policy** is the load-bearing component (PRODUCTION.yaml "~95% policy"); the residual is
   a **small** positive (+35 elo, inconclusive) that should be **kept, not dropped**, but is **not**
   where strength gains will come from. Future value/superhuman work should target the **leaf/value
   ceiling** directly (the v2.7 cap), not lean harder on the existing residual head — it is small and
   already folded in.
