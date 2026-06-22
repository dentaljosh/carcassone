# v2.8 leaf-swap battery — neural / deep-heuristic / hybrid (2026-06-22)

> Follow-up to [HEURISTIC_V28_REPORT.md](HEURISTIC_V28_REPORT.md): does the v2.8 flat meeple-economy
> leaf (`meeple_k=2`, == the legacy knob, flat/Cython path) generalize beyond pure heuristic search —
> to the **neural production policy** and against the **deep-heuristic ruler**? Run via the carc-orch
> SHM orchestrator (2-box local 5060 Ti + laptop 4070), deck-paired, both seats. **v2.7 frozen;
> nothing promoted; production + PRODUCTION.yaml unchanged.** Numbers cite results.csv `iter8_v28_*`,
> `v28_meeple_flat_*`.

## Results

| # | matchup (same net/sims/c_puct/residual 0.25/decks/seats; only leaf differs) | n | result | signal |
|---|---|---|---|---|
| 1 | **iter8+v2.8 vs iter8+v2.7** (leaf-swap in the neural value) | 400 | **+154.5 elo** (z=9.82) | VERDICT |
| 2 | iter8+v2.8 vs **heur@3200_v2.7** (out-of-lineage anchor) | 200 | **+153.4 elo** (z=5.87) | VERDICT |
| 3 | iter8+v2.8 vs **heur@3200_v2.8** (EQUAL leaf — the disambiguator) | 200 | **−38.4 elo** (z=−1.56) | tie→loss |
| — | (reference) iter8+v2.7 vs heur@3200_v2.7 — Joshua #8 | 400 | −28.7 elo | tie→loss |
| 4 | hybrid:8:800 v2.8 vs hybrid:8:800 v2.7 (leaf in neural value + heur endgame) | 200 | **+153.4 elo** (z=5.87) | VERDICT |

k-sensitivity (heur@200, flat term vs v2.7): **inverted-U, peak at k=2** — k1 +75.9, **k2 +179.5**,
k3 +159.8, k4 +34.9 (washing). k=2 is near-optimal, not an edge value (`HEURISTIC_VALUE_NORM=15` →
k=4 over-weights). **Terminal-hoarding diagnostic (n=60):** NO pathology — terminal in-hand 7=7 both
(engine returns meeples at final scoring, metric degenerate); the informative last-5-plies in-hand is
v2.8 **0.26** vs v2.7 **0.05** — a small benign reserve tendency, not wasteful hoarding (v2.8 still
wins 0.717). The flat term's lack of endgame decay does not strand meeples.

**Consistency:** the leaf gives ~+150–180 to *every* consumer — neural (+154.5), heuristic (+179 @200),
AND hybrid (+153.4) — confirming a genuine leaf-quality gain, uniform across agent types.

## Interpretation (FACT → INTERP, clearly separated)

**FACT.** (1) The meeple leaf helps the **neural production policy** by +154.5 elo (z=9.82) — not just
heuristic search. (2) iter8+v2.8 beats heur@3200 *when the heuristic runs the v2.7 leaf* (+153.4).
(3) BUT when the deep heuristic runs the **same v2.8 leaf**, iter8+v2.8 **loses** to it (−38.4) — the
same relative position iter8+v2.7 had vs heur@3200_v2.7 (−28.7).

**INTERP — the load-bearing read.** The +153.4 vs heur@3200_v2.7 was **entirely the leaf gap** (v2.8 >
v2.7), not the neural agent exceeding deep search. At **equal leaf**, deep heuristic search still beats
the neural agent by ~the same margin as before. So:
- **v2.8 is a real, large CLASSICAL-ENGINE leaf improvement** that lifts BOTH the heuristic and the
  neural agent ~uniformly (~+150–180 each over their v2.7 selves).
- **v2.8 is NOT an ML/superhuman lever.** The learned components (iter8's policy) still do **not exceed
  the heuristic** — they are still capped by deep search at equal leaf. The program's structural
  blocker #2 (CLAUDE.md: "superhuman requires the learned components to EXCEED the heuristic, which they
  don't yet") **remains** — v2.8 raises the ceiling for everyone; it does not change who is on top.
- **Silver lining (measurement-first):** heur@3200_**v2.8** is a **stronger non-saturated reference
  ruler** than heur@3200_v2.7 (it still beats the strongest neural agent). That is exactly the better
  anchor the measurement-first program is gated on.

This directly answers the task's "separate classical-engine gains from ML gains": **classical = yes,
large; ML/superhuman = no.**

## Recommendation (unchanged framing, now firmly evidenced)

**v2.8 = v2.7 + `meeple_k=2`: promote to EXPERIMENTAL reference / stronger ruler — NOT production, NOT a
v2.7 replacement, NOT a superhuman lever.** It is the program's new strongest heuristic baseline and a
better measurement anchor. v2.7 stays the frozen historical reference. Next levers are unchanged by
this: the learned components still need to *exceed* a (now stronger) heuristic — distillation-from-v2.8
or a fundamentally stronger learned value, measured against the heur@3200_v2.8 ruler.

## Ops note
Disambiguator (#3) hit the shared-claim orphan-stall: the laptop's mobile-4070 carc-orch threw
`BrokenServerError` (60s SHM timeout) → `set -e` aborted its client → 38 stranded `.claim`s with no
result. Recovered per the standard playbook: cleaned the 38 stale claims, finished on the stable local
box. (Reinforces `feedback_shared_claim_orphan_stall` + the laptop-4070 instability note.)
