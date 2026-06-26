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

#### Wave B — n=400 VERDICT — DONE 2026-06-25
| cell | wr vs anchor | elo | z(margin) | even-bucket | verdict |
|---|---|---|---|---|---|
| **Bmild_cap8** | **0.566** | +46 | +1.92 | **0.669** | **WINNER** (competitive-state gain) |
| Bmild_cap12 | 0.559 | +41 | +2.17 | 0.453 | confirmed but even<0.5 = padding |

**cap8 WINS.** Both confirm cap>5 (~+45 elo, winrate held from n=200), but the even-bucket
splits them decisively: cap8 0.669 (competitive win) vs cap12 0.453 (below coinflip — its
margin-z is blowout padding, the A32 trap). cap=12 over-values fantasy closures and misleads
in tight games; cap=8 prices real threats without the fantasy. **NEW ANCHOR = `Bmild_cap8`
(cap=8 + MILD curve + 3-open).** Depth-verify (h6400) deferred to the final combined config.

### Wave C — closure-P @ sims=200 n=200 paired vs **Bmild_cap8** — SCREEN DONE 2026-06-25
| cell | change | wr | z(margin) | even | verdict |
|---|---|---|---|---|---|
| p040-015-005 | lower P | 0.485 | −0.48 | 0.471 | null |
| p060-025-005 | higher P | **0.557** | +1.73 | **0.450** | flag, padding-suspect → n400 |
| p050-010-005 | lower 2-open | 0.495 | +0.03 | 0.514 | null |
| p050-020 | drop 3-open | 0.525 | −0.75 | 0.683 | even↑ but overall null → skip |

Messy (matches the moderate-low prior). The lone winrate flag (p060, higher closure prob)
carries the A32/cap12 PADDING signature — even-bucket 0.450 (<coinflip), winrate from
non-competitive buckets. Mechanistically: higher closure-P over-values closures like cap12
did. Drop-3-open (p050-020) has the opposite profile (even 0.683, overall null, n=30 noisy).
**→ n=400 confirm p060-025-005, even-bucket is the decider** (same lens as cap8-vs-cap12).
Expect: padding → kill → Wave C null → Bmild_cap8 holds.

#### Wave C — n=400 VERDICT — DONE 2026-06-25: **NULL (padding confirmed)**
p060-025-005 vs Bmild_cap8 collapsed 0.557 (n200) → **0.506 (n400)**, elo +4.3, even-bucket
0.385 (deep <coinflip). The n=200 flag was selection-inflation + blowout padding; higher
closure-P pads blowouts and loses tight games (same trap as cap12). The closure schedule
(0.5/0.2/0.05) is already well-tuned. **Wave C NULL → `Bmild_cap8` holds as the anchor.**

### Wave D — tanh value-norm @ sims=200 n=200 paired vs **Bmild_cap8** — SCREEN DONE 2026-06-25
| cell | squash | wr | z(margin) | even | verdict |
|---|---|---|---|---|---|
| n12 | diff/12 (sharper) | **0.542** | +1.39 | 0.549 | flag (not padding) → n400 |
| n18 | diff/18 (gentler) | 0.438 | −1.40 | 0.516 | loses |
| n24 | diff/24 (gentler) | 0.522 | +0.35 | 0.588 | null overall |

Weak signal toward a SHARPER squash (diff/12 > diff/15; gentler hurts). n12's even-bucket
(0.549) is healthy — not the padding trap. Plausible (curve+cap8 changed the leaf-diff
scale). But weak (~1.2σ) and the norm is a search-balance knob (depth-sensitive). **→ n=400
confirm n12** (per-side value_norm; runs on c21f751, no re-sync). Then the throne test.

#### Wave D — n=400 VERDICT — DONE 2026-06-25: **NULL**
n12 regressed 0.542 → **0.515** (elo +10.4, even 0.533) — the diff/12 edge was n=200 noise.
tanh-norm at 15 is already fine. **Wave D NULL.**

## RETUNE COMPLETE — final v2.9.1 config = `Bmild_cap8`
| wave | knob | verdict |
|---|---|---|
| A | meeple scale | null (magnitude already right) |
| **B** | **closure cap** | **cap8 — the single win (+46 elo vs cap5, competitive-state gain)** |
| C | closure-P | null (p060 padding) |
| D | tanh-norm | null |

`Bmild_cap8` = MILD curve (-8,-4,-1,0,2,3,4,5) + cap=8 + 3-open schedule + diff/15 norm.
The pre-registered most-likely outcome: the curve shape captured the magnitude; the one
genuine refinement was the anchor's cap=5 being too low (env default). **Next: the throne
test the whole audit skipped — `Bmild_cap8` vs REAL production `v28prod` (cap12 +
drop-3-open + flat-k2), sims=200 n=400 → h6400 depth arbiter.**

### THRONE TEST — Bmild_cap8 vs REAL production v28prod @ sims=200 n=400 — DONE 2026-06-25
| | wr | elo | z(margin) | even | behind | ahead | blowout |
|---|---|---|---|---|---|---|---|
| **Bmild_cap8 vs v28prod** | **0.579** | +55 | **+3.94** | **0.636** | 0.13 | 0.84 | 0.95 |

**🏆 The v2.9.1 stack BEATS actual production v2.8 (cap12 + drop-3-open + flat-k2) by ~+55
elo, gain in the competitive even-bucket (0.636 — not padding), z+3.94 significant.** This is
the comparison the whole v2.9 audit skipped (it used the cap5/3-open env default as "v2.8").
Margin ≈ the original Bmild-vs-cap5/3-open win (0.581) ⇒ the CURVE (meeple economy) is the
bulk; cap8 adds a bit. Production's cap=12 vs our cap=8 didn't save it — the curve dominates.

**Depth ladder (cost-disciplined):** sims=800 washout (DONE, below) → h6400 arbiter
(~3-5 hr, **Joshua's call** — h6400 is ~37 min/game under cluster contention).

| depth | Bmild_cap8 vs v28prod | elo | z(margin) | even |
|---|---|---|---|---|
| sims=200 n=400 | 0.579 | +55 | +3.94 | 0.636 |
| sims=800 n=200 | **0.550** | +35 | +1.84 | 0.569 |

**Washout check PASSED — depth-robust.** Gain shrinks +55→+35 but stays positive +
competitive-favorable (even 0.569) at sims=800, mirroring the original Bmild ladder (which
recovered to 0.581 at h6400). n=200@s800 is ±25 elo (coarse). `Bmild_cap8` is a confirmed,
depth-robust win over actual production v2.8. h6400 arbiter pending Joshua's compute call.

## Standing constraints
v2.7 frozen/bit-identical · v2.8 stays production · v2.9 opt-in · no RoD2 training on
these results · no PRODUCTION.yaml edit / checkpoint change without Joshua's explicit call.
