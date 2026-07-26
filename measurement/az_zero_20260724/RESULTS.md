# az_zero — RESULTS + PREREG READ (2026-07-24)

**VERDICT: FLATLINE.** The pre-registered ALIVE bars were not reached on either criterion, and the
curve is non-monotone. Run complete: 12 iterations, 09:18 → 19:16 EDT, 3,600 self-play games.
MEASUREMENT ONLY — champion and `governance/PRODUCTION.yaml` untouched throughout.

Governing pre-registration: [PREREG.md](PREREG.md) (written before any game was played).
Build/config: [DESIGN.md](DESIGN.md). Mechanism probe: [PROBE_OFFDIST_20260724.md](PROBE_OFFDIST_20260724.md).

## The question

Every prior kill of a learned component in this project was measured inside a
**heuristic-warmstarted** lineage, leaving one live objection — AlphaGo Zero's thesis — that nets
fail here only because they are raised in the heuristic's basin. az_zero removes that confound: a
random-init sighted net, pure self-play, **no heuristic anywhere in the loop** (the net's own value
head is the leaf), evaluated against a same-architecture heuristic-taught anchor.

## The curve (n=50/point, deck-matched, same seed band 770000000 every screen)

vs `m2_sighted/warmstart_sighted.pt` — same arch (81ch/42), same sims (128), same rep:

| iter | W–D–L | winrate | margin (pts/game) | paired z |
|---|---|---|---|---|
| 0 | 0–0–50 | 0.00 | −47.12 | −22.32 |
| 2 | 1–0–49 | 0.02 | −32.78 | −12.12 |
| 4 | 3–1–46 | 0.07 | −27.46 | −8.94 |
| 6 | 3–0–47 | 0.06 | −34.60 | −14.53 |
| 8 | 3–1–46 | 0.07 | −36.08 | −10.75 |
| 10 | 6–0–44 | 0.12 | **−26.86** (best) | −10.68 |
| 11 | 5–0–45 | 0.10 | −29.84 | −10.72 |

vs a uniform-random mover: 0.85 → 0.98 → 1.00 → 0.98 → 0.98 → 0.92 → 0.99.

## Read against the pre-registered bars

| PREREG bar | required | achieved | result |
|---|---|---|---|
| half the anchor gap closed | ≤ −23.55 | best −26.86 (43% closed), final −29.84 (37%) | **not met** |
| winrate vs anchor | ≥ 0.35 | best 0.12, final 0.10 | **not met** |
| monotone-ish over iters 4→12 | trend | oscillates −27 to −36, no trend | **not met** |

**All three fail ⇒ FLATLINE.** The random floor was solved by iter 2 and never converted into
anything further. The iter-10 bounce to −26.86 is noted explicitly rather than buried: it is the
best single point, but it is statistically indistinguishable from iter 4's −27.46 six iterations
earlier and is followed by a regression at iter 11 — i.e. oscillation, and precisely the
"lone value beating its neighbours" signature this project has been burned by before.

## Mechanism (measured, not inferred)

The trainer's per-iter `value↔outcome corr` rose 0.161 → 0.855, which **looks** like the value head
overtaking the heuristic's 0.61 reference. It does not: that statistic is computed on a split of
the *training window*, and the off-distribution probe shows what it hides —

| probe set | az_zero iter_06 | neutral control (warmstart) |
|---|---|---|
| games inside its training window | 0.906 / 0.891 | 0.646 / 0.731 |
| games from its own **next** policy generation | **0.530** | 0.717 |
| a stronger agent's games | **0.437** | 0.620 |

The control is flat across all four sets, so they are equally predictable and the collapse belongs
to the net. Cause: **the value head's effective sample size is the number of GAMES, not positions**
— ~144 positions share one outcome label, so a window-4 × 300-game buffer is ~1,200 independent
labels for a 7M-parameter head, and memorising them is the cheapest available fit. AlphaGo hit this
exact wall and solved it by sampling one position per game across **30 million** games.

## Interpretation bounds (from PREREG, restated so nobody over-reads this)

1. **Clairvoyant regime.** This self-play path builds `NeuralMCTS(fair_chance=False)`: search sees
   the true tile order. Both sides of every screen share the regime so the comparison is fair, but
   **no number here transfers to blind-PIMC deployment strength.**
2. **A null here is compute-bounded** — 3,600 games against AlphaGo Zero's millions. This does not
   show tabula rasa is impossible in Carcassonne; it shows it does not happen at our scale.
3. The anchor is a v2.7-era distillation, so it measures *scaffolding*, not current champion strength.

## What it settles

**The scaffolding-trap hypothesis is answered: the chains were not the binding constraint.** With
the heuristic entirely removed from the loop, the zero-start net hits the same wall from the other
side. Combined with the prior kills — all of which were inside the warmstarted lineage — the failure
is a property of *learned value in this game at this scale*, not of the training scaffold.

**Do not fund an az_zero v2 on the obvious levers.** All were checked against the record after the
result: `search_value` targets (tried, corr 0.29→0.47, no strength), `search_value_tree` interior
targets (tried, "one-shot is not enough"), ownership aux (tried in Path B at 600 games/iter — reached
held-out corr **0.81** and the value-in-leaf A/B still hurt), ranking loss / STEP B.1 (tried, "HELPS
but INSUFFICIENT", no positive marginal), anchor-fraction opponent mixing (tried, +39 overturned to a
tie), capacity/regularisation (C4a). Symmetry augmentation is untried but attacks the wrong quantity
(it multiplies views of the *same* label, adding no independent information). Full index:
[docs/LEVER_INDEX.md](../../docs/LEVER_INDEX.md).

## Cost

~10 h wall, 3,600 games, both boxes shared with the live distill gen (which paid ~28% throughput).
Byproducts kept: the laptop work-stealing joiner (`scripts/az_zero/laptop_joiner.sh`), the GPU
orch-SHM path for anchor screens (`scripts/az_zero/screen_orch.sh`, ~1 h → ~5 min per screen point),
and the off-distribution probe method.
