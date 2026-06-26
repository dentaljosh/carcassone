# V29.1 RETUNE — pre-registered plan (Bmild anchor, local knob re-tune)

**Status: RUNNING (Wave A live, 3-box) — 2026-06-25.** Pre-registered before reading
results to avoid Goodharting. The core v2.9 result (nonlinear meeple curve beats the
flat-k2 baseline, ~+30–50 elo, depth-robust) is DONE — see [V29_DECISION.md](V29_DECISION.md).
This asks the follow-up: now that meeple economy changed, are the *old* production knobs
(cap, closure-P, tanh-norm) — tuned around flat k=2 — still locally optimal around Bmild?

## The anchor (read this — it is NOT documented-v2.8)

**Bmild anchor** = `LeafConfig(v29_meeple_curve=(-8,-4,-1,0,2,3,4,5))` on the v29 harness
baseline, which resolves from env defaults to:
- `bonus_cap = opp_bonus_cap = 5.0`  (NOT 12)
- `closure_p = {1:0.5, 2:0.2, 3:0.05}`  (3-open — NOT drop-three-open)
- flat `meeple_k=2.0` present but INERT (the curve replaces it).

⚠️ **Doc-label discrepancy (found 2026-06-25):** every prior v29 run (Wave-1/2, washout,
h6400) used this cap5/3-open base, but V29_CANDIDATE_TERMS / V29_DECISION call it
"v2.8 = cap=12, drop-three-open". The label is wrong; the comparisons are still valid
(both sides shared the base), but "Bmild beats v2.8" really means "beats cap5/3-open +
flat-k2." **Real production v2.8** = cap=12 + drop-three-open + FLAT_LEAF + residual.
→ a final "vs TRUE production" check is queued (Wave F below); it needs no new code:
`Bmild_cap12_p050-020` composes the cap12+drop-three-open base.

## Success criterion (binding)
A cell ships only if it **beats the Bmild anchor** (not merely beats v2.8). The core
result is already found; this hunts a v2.9.1 *on top* of Bmild.

## Screen protocol (per wave)
sims=200 n=200 paired vs Bmild → flag cells >0.53 → sims=200 n=400 on top 2–3 →
winner → h6400 n≥300. Same seed-start (1e9) so decks are reused/comparable. 3-box
shared-claim (local W30 / laptop W22 / xeon W10), CPU-vs-CPU HeuristicMCTS.

## Waves (sequential, NOT a grid). Best-of-prev-wave feeds the next.

| wave | knob | candidate strings (parser-verified) | prior |
|---|---|---|---|
| **A** | meeple-curve SCALE | `Bmild_x075`, `Bmild_x125` (anchor=x100); +`Bmild_x150` if x125 wins | **highest** |
| B | closure cap | `Bmild_cap8`, `Bmild_cap12`, `Bmild_cap16` (+`Bmild_cap20` if 16 wins), on best scale | moderate |
| C | closure-P schedule | `Bmild_p040-015`, `Bmild_p060-025`, `Bmild_p050-010` (+structure note ↓) | moderate-low |
| D | tanh-norm | diff/{12,15,18,24} — **HeuristicMCTS knob, not a LeafConfig field**; needs mcts.py wiring | low-moderate |
| E/F | 1–2 combos + vs-TRUE-production | best-scale+best-cap+best-P; then `Bmild_cap12_p050-020` vs real v2.8 | — |

Composable: `Bmild_x125_cap16`, etc. (verified).

⚠️ **Wave-C structure gotcha:** the parser's `p050-020` → `{1:0.5,2:0.2}` (2 entries) —
it DROPS the anchor's `3:0.05` ticket. So `Bmild_p050-020` is NOT a no-op vs the anchor;
it conflates "drop the 3-open lottery" with the P magnitudes. When C runs: either keep
the 3-entry structure (extend parser to `p050-020-005`) or test the schedule-drop as its
own explicit cell. Do NOT read a `p050-020` win as a pure magnitude effect.

## Pre-registered priors / null
Most likely outcome: the curve SHAPE already captured the magnitude → scale ≈ null vs
anchor, and the retune finds at most a small cap/P refinement. Take the null seriously:
if every wave ties the anchor, the honest verdict is "Bmild is locally optimal; lock it."
Do NOT promote a lone >1σ cell — confirm at n=400 (the c=3 +47 lesson).

## Results log (appended as waves land)

### Wave A — meeple-curve SCALE @ sims=200 n=200 paired vs Bmild — DONE 2026-06-25
| cell | scale | wr vs anchor | elo | z(margin) | verdict |
|---|---|---|---|---|---|
| Bmild_x075 | ×0.75 | 0.448 | −37 | −1.71 | loses |
| Bmild (anchor) | ×1.00 | — | 0 | — | reference |
| Bmild_x125 | ×1.25 | 0.463 | −26 | −0.99 | loses |

**Verdict: NULL — anchor magnitude is locally optimal.** Both directions lose (inverted-U
peak at ×1.00); x075's damage concentrates in the *behind* bucket (wr 0.156) — shrinking
meeple values worsens management when struggling. The curve SHAPE already captured the
right magnitude. No x150 (x100→x125 trends down). **Scale locked at ×1.00.** This is the
pre-registered most-likely outcome.

### Wave B — closure cap @ sims=200 n=200 paired vs Bmild — SCREEN DONE 2026-06-25
| cell | cap | wr vs anchor | elo | z(margin) | even | verdict |
|---|---|---|---|---|---|---|
| Bmild_cap8 | 8 | **0.557** | +40 | +0.88 | 0.661 | flag → n400 (favorite) |
| Bmild_cap12 | 12 | 0.550 | +35 | +0.64 | 0.545 | flag → n400 (prod-std) |
| Bmild_cap16 | 16 | 0.555 | +36 | +0.36 | 0.567 | drop (≈cap12, worse z) |

**SIGNAL (first non-null lever): cap > 5 helps, ~+40 elo, flat plateau 8–16.** All three
beat the anchor (cap=5, 0.50); they are tied with each other. cap8 is the marginal favorite
(best wr + best margin-z + best even-bucket); margin-z DECLINES as cap rises ⇒ higher cap
just pads blowouts. No upward trend → no cap20. The anchor's cap=5 (env default) was too low;
documented production's 12 sits on the plateau. **n=400 confirm cap8 + cap12 next.** All
n=200 (~1.6σ) — flags, not verdicts.

## Standing constraints
v2.7 frozen/bit-identical · v2.8 stays production · v2.9 opt-in · no RoD2 training on
these results · no PRODUCTION.yaml edit / checkpoint change without Joshua's explicit call.
