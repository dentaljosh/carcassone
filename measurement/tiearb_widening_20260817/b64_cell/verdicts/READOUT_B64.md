# `B = 64` GAME CELL — READ-OUT

generated: 2026-08-20T21:41:08Z

## BRANCH: `B-COSTKILL`

**⛔ THE WIDENING WINS AND THE RUNG IS UNAFFORDABLE — A WIN THAT CANNOT BE BOUGHT.**

⭐ THE EXPECTED BRANCH ON A WIN (§4.0). z_D ≥ +2.0, and rho_wall(64) = 2.4897, 2.07× the house N4 bar of 1.20, with no owner waiver on the record predating game 1. LICENSES NOTHING DEPLOYABLE. It licenses exactly two things, both needing a fresh preregistration or a fresh owner ruling: (i) a fresh owner wall-clock ruling on whether the N4 bar moves above B = 16; and (ii) a ladder question this cell DID NOT MEASURE in game points and which no branch may infer from two points. ⛔ AND THE LADDER IS NOT A CHEAPER ROUTE: rho_wall(32) = 1.2449 ALSO EXCEEDS 1.20 (by 3.7%), so a B = 32 win would ALSO be B-COSTKILL. ⛔ On-device is dead at this rung regardless (rho_phone(64) ≈ 24, a third currency, out of scope).

## §4.0 — the reachable branch set, stated BEFORE the run

- `W` = **False** · reachable ['B-REVERSED', 'B-COSTKILL', 'B-PRESENT', 'B-FLAT', 'U-UNREADABLE']
- unreachable: **['B-CONFIRMED']**
- ⛔ B-CONFIRMED is UNREACHABLE: A is decided entirely by W, and rho_wall(64) = 2.4897 > 1.20 makes A's first disjunct FALSE before game 1. A z_D ≥ +2.0 win fires B-COSTKILL and licenses nothing deployable.

## §3 gates — ALL of them, never short-circuited

| gate | ok |
|---|---|
| `G-BAND` | PASS |
| `G-DIVERGE` | PASS |
| `G-FAILED` | PASS |
| `G-FIRE` | PASS |
| `G-J1` | PASS |
| `G-J13` | PASS |
| `G-J4` | PASS |
| `G-N` | PASS |
| `G-NEST` | PASS |
| `G-PLY` | PASS |
| `G-SMOKE` | PASS |
| `G-STAT` | PASS |
| `G-TOOL` | PASS |

## The `D` block — THE PRIMARY

- `D` = +1.7167 · `se_D` = 0.6463 · **`z_D` = +2.6561** · `n_common` = 750 decks
- realized `rho` = +0.1237 · committed `se(D)` = 0.7133 · committed 2σ floor = +1.427 pts/game
- `n` to convict at the REALIZED dispersion: 426 decks

## §4.3 item 3 — the divergence block

- `f0` = 0.0160 · `1 − f0` = 0.9840 vs floor 0.1 — **and beside the EXPECTED ≈1.0**
- dilution `√(1−f0)` = 0.9920 · headroom ≈10×
- (not flagged anomalous)
- f0 is measured as 'D_i exactly 0.0', which OVERCOUNTS identity (two different games can coincide on margin) ⇒ 1 − f0 UNDERCOUNTS divergence ⇒ the floor is CONSERVATIVE: it can only fire early, never late.

## Cost — reported on every branch, a branch input NOWHERE

- `rho_wall(16)` 0.6224 (measured) · `rho_wall(64)` **2.4897** vs the N4 bar **1.2** · `rho_wall(32)` 1.2449 (ALSO above the bar)
- `rho_phone(64)` [23.9, 22.08] — **NOT SOLVED — a third currency**
- ⚠️ champ_prefix_ms_per_move IS THE CANDIDATE SIDE in eval_fair_puct (lines 2361/2371/2389). A read-out that swaps them inverts the cost verdict.
- WIDE and NARROW are NOT cost-matched to each other, but neither candidate's SEARCH BUDGET moves: both run the identical champion at k8×1376 and the arbiter fires AFTER the search, at the root, on an already-resolved tie ⇒ the extra cost buys no extra search. It is a WALL-CLOCK ASYMMETRY and is disclosed as one on every branch.

## Carried VERBATIM

- **W-RISING**: lower(CI)>0, d>=0.04, arb_64 convicts, arb(64)>arb(16) — Δ(16→64) = 0.0670 CI95 [0.0215, 0.1111]
- **W-RISING_scope_fence**: a null here would have meant 'no rung above 16 is worth ≥ +0.04 pts/tied ply', NOT Δ = 0 … the saturating-exp (+0.017) and √B-noise (+0.021) models are NOT resolved by this design
- **translation_caveat**: Stage 1b's +0.1441 pts/tied ply predicts +0.79 pts/game … Phase B realized +3.07 — a 3.9× under-prediction. So Δ(16→64) = +0.064 maps to anywhere from +0.35 (naive) to +1.4 (realized-ratio) pts/game.
- **translation_caveat_both_ways**: the offline→game map is unestablished and +0.0670 × 3.9 is not a projection either
- **offline_ratio_disclaimer**: ⛔ arb64/arb16 = 0.2015/0.1345 = 1.498 may be printed as a DESCRIPTION of the offline ladder and MUST NOT be presented as a projection of the game effect.

## ⚠️ SPEC-vs-BUILDABLE mismatches — REPORTED, never resolved here

- **READ_RULE §3 G-FAILED clause 3 / DESIGN §8 clause 3** — the diagnostic class of a failed GAME has no named address in the pair: §2's table routes n_failed to summary.json but no key is named for the per-failure CLASS, and eval_fair_puct's summary does not emit one today.
  - adjudicator: reads `summary.json::failed_classes` if present; with n_failed == 0 the clause is vacuous and the gate passes. With n_failed > 0 and no class field, clause 3 CANNOT be evaluated — REPORTED here, not resolved.
  - resolution: ⭐ RULED 2026-08-19 (RULING 3): clause 3 NARROWED to verbatim disclosure + an escalation HALT before adjudication; the class field is carried to rung3_r5 rather than commissioned after sign-off. IMPLEMENTED.
- **READ_RULE §3 G-J13 / DESIGN §3** — the pair requires the two-sided control at BOTH B values per host, but names ONE file per host (PREFLIGHT_*_${HOST}_FIRST.json) and names NO address for the B value inside it. On the known-good artefact B sits at `j13_witness.B` / `expected.B`, at neither of the two levels §2's manifest rule would suggest. ⚠️ And ONE file per host cannot carry TWO B values without a shape the pair does not specify.
  - adjudicator: reads the PINNED j13_witness.B and expected.B; an absent B FAILS, never coerced.
  - resolution: ⭐ RULED 2026-08-19 (RULING 2): the key path is PINNED to j13_witness.B / expected.B plus the two booleans, and an ABSENT B FAILS — a documented resolution order is explicitly NOT enough for the one gate that proves the instrument is live. IMPLEMENTED.
- **READ_RULE §3 G-SMOKE / DESIGN §9.2** — ⭐ FOUND BY THE KNOWN-GOOD EVALUATION. §9.2 states TWO rules on TWO surfaces — the EMITTER 'is whitelisted to the keys above and must fail closed on an unlisted key', while the G-SMOKE row fires on 'any forbidden OUTCOME key'. Read as ONE whitelist over the artefact, the row FAILS a known-good smoke: Stage 2's SMOKE.json carries structural keys (headline, kind, cells, throwaway_band, cost_reference, production_knobs, eta_for_the_real_cells, phi_reference, cell_band_untouched) and suffixes the field-name-trap keys (champ_prefix_ms_per_move_IS_THE_CANDIDATE). NONE is an outcome key. This is DESIGN §13.1's own class: a fail-closed rule that fails a healthy run.
  - adjudicator: the GATE fires on forbidden OUTCOME keys at any depth; the EMITTER whitelist is evaluated and REPORTED beside it, never as the gate verdict.
  - resolution: ⭐ RULED 2026-08-19 (RULING 1): the builder's reading is CONFIRMED — the emitter whitelist is a WRITE surface, the G-SMOKE row a READ surface that fires only on forbidden OUTCOME keys at any depth. Structural keys never fire it. IMPLEMENTED.
- **RULING 2's pinned addresses vs the known-good artefact** — ⚠️ RESIDUAL, reported for the emitter. Ruling 2 pins FOUR addresses; on Stage 2's known-good preflight the two BOOLEANS sit at `two_sided.pick_changed` / `two_sided.root_leaf_value_bits_unchanged`, not under `j13_witness.*`. `B` itself IS at the pinned `j13_witness.B` / `expected.B`.
  - adjudicator: B is read STRICTLY at the pinned path and an absent B FAILS. The two booleans are read at the pinned path FIRST and fall back to the older `two_sided.*` house shape — so a B64 run emitting the pinned shape passes strictly, and the known-good evaluation still exercises the machinery instead of failing a healthy run.
  - resolution: the B64 preflight emitter should write the two booleans at the PINNED `j13_witness.*` path before game 1. NOTED for the executor; the pair is not changed.

*PRODUCTION.yaml untouched on every branch. This read-rule is SPENT when the read-out lands, on every branch, and the band retires from confirmatory use.*
