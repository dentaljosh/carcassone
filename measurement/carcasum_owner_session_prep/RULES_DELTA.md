# RULES_DELTA — what the owner will experience in Carcasum vs what his phone plays

> **Status: PREP, 2026-08-30.** Cited, not asserted: every row below points at the audit,
> patch list, or profile definition it comes from. Companions:
> [`SETUP.md`](SETUP.md) · [`PROTOCOL.md`](PROTOCOL.md).

---

## 0. The one-line answer

**The owner's phone games and a patched-Carcasum game are the same rules.** Both are
`fixed_v1` + R9. That is not an assumption — it is a 50-game corpus with **exact
final-score agreement 50/50, exact farm agreement 50/50, farms exercised in 50/50 games,
and zero REAL divergences** ([`../carcasum_audit_20260823/AUDIT_READOUT.md`](../carcasum_audit_20260823/AUDIT_READOUT.md)).

Three residual deltas survive that audit and are named in §3. None of them is a scoring
rule; two are cosmetic and one is a rare board-geometry asymmetry that *favours the owner*.

---

## 1. The rule set the owner will be playing, stated plainly

**`fixed_v1` + R9, 2-player, Base game + Farmers, no expansions, 7 meeples, retail start
tile, 72 tiles.**

`fixed_v1` is the four-lever Phase-B bundle
([`src/carcassonne_ai/rules_profile.py`](../../src/carcassonne_ai/rules_profile.py)):

| lever | value | what it means at the table |
|---|---|---|
| `grid_rule` | `centered18` | the *app's* board window (a phone-UI constraint, see §3.1) |
| `start_rule` | `retail` | the retail 'D' start tile — city-top / straight-road (`RCr` in Carcasum's vocabulary, and **their start tile too**) |
| `cloister_scan` | `fixed` | cloister completion scans the correct 8 neighbours |
| `unplaceable_tile` | `redraw` | a tile with no legal placement is discarded and redrawn |

plus **R9** — the farm half-edge convention on the start tile — which is env-latched
(`CARCASSONNE_FIX_R9=1`) rather than a profile field. Carcasum's own 2014 JCZ `basic.xml`
declares `RCr` as `<farm city="N">EL WR</farm>`, i.e. **R9 recurs verbatim in their data**,
which is why our side runs R9-on for every Carcasum cell
([`vendor/README.md`](../../vendor/README.md), "Two facts a reader needs").

⚠️ **The standing R9 caveat travels with this session too.** Every number produced here is
an **R9-on** number and is *not* on the `walled` production elo scale, on which every
historical elo of record was measured. The owner's E4 phone archives are also R9-on
(`farm_rule: "r9"`), so **the two sides of the comparison agree** — which is the only
thing this session needs. Do not carry either number onto a `walled` ladder.

---

## 2. Divergences that were found and FIXED before any match

### 2.1 The tiny-city exception — patched (R1)

Upstream Carcasum deliberately implements the **original-2000** rule from the thesis
(§2.3 "Rules Used"): a completed city of exactly two tiles scores **2 points, not 4**.
That is a material divergence from `fixed_v1` and from every modern edition.

It is patched in the vendored tree, in **both** `Game::cityClosed` and
`Game::cityUnclosed` — as a pair, because `cityUnclosed` is the undo path the MCTS
simulation rolls its own board back with, and a scored/unscored mismatch of 2 points
would corrupt the search rather than merely mis-score the game
([`vendor/carcasum/CARCASUM_PATCHES.md`](../../vendor/carcasum/CARCASUM_PATCHES.md), R1).

The patch is **not taken on faith from a diff**: gate 6 of
[`../carcasum_match_prep/AUDIT_PLAN.md`](../carcasum_match_prep/AUDIT_PLAN.md) requires a
constructed plain two-tile city to *positively complete and score 4*, and
[`tests/test_carcasum_rules_patch.py`](../../tests/test_carcasum_rules_patch.py) is that
test. ✅ PASS.

> ⛔ **This is the reason `SETUP.md` §3 forbids the upstream Windows binary.** That build
> is unpatched — it scores 2. Nothing else in this document survives if the wrong binary
> is used.

### 2.2 Two stale `> 2` sites deliberately NOT patched

Recorded so a future reader's grep does not think they were missed
([`CARCASUM_PATCHES.md`](../../vendor/carcasum/CARCASUM_PATCHES.md)):

* `Game::calcUpperScoreBound` carries the same stale rule but is read **only** by the
  *normalising* (Heyden-style) utility providers. Our opponent is
  `MCTSPlayer<PortionUtility, RandomPlayout>`, whose `utility()` is
  `scores[me] / sum(scores)` and never touches `upperScoreBound`. **Inert for this
  configuration.** ⚠️ It stops being inert the moment anyone selects a *normalised*
  utility in the GUI — one more reason `PROTOCOL.md` pins the utility to **Portion**.
* `jczplayer.cpp:417` is inside their port of the JCloisterZone AI's *evaluator*. It is AI
  code, in a player we are not using. Irrelevant unless someone picks "JCloisterZone AI"
  from the player list — **don't**.

### 2.3 The endgame-terrain class that was demoted, and why it is not a rules finding

`ENDGAME_TERRAIN_MISMATCH` fired on 8/50 in the first audit pass and was demoted out of
`REAL` on measurement, not judgement: Carcasum runs `endGame()` *inside* the terminating
`Game::step()`, so the last `ev_move.score_detail` already contains the endgame sweep and
differencing against the *previous* ply over-reports by that ply's mid-game closures. The
delta against the terminating ply is **exactly zero on every terrain**, and those same 8
games had exact final-score *and* exact farm agreement
([`AUDIT_READOUT.md`](../carcasum_audit_20260823/AUDIT_READOUT.md) §3). No table-visible
consequence.

---

## 3. The three deltas that REMAIN — what to tell the owner

### 3.1 ⚠️ Board bounds: Carcasum is effectively unbounded; his phone is not

Carcasum's board is **145×145 with offset 72** — from their side a wall-escape is
impossible, and the audit measured **zero `WALL_LEGALITY`** events. The constraint is
**ours**: `fixed_v1` carries `grid_rule: centered18`
([`AUDIT_READOUT.md`](../carcasum_audit_20260823/AUDIT_READOUT.md) check 7).

So: **in Carcasum the owner may legally place tiles that his phone app would refuse**,
in the rare game whose layout runs long in one direction. This is a *real* asymmetry,
it is low-frequency (zero fires in 50 audit games, and 400 rated games produced zero
`WALL_LEGALITY`), and its direction is **toward the human** — a wider board is one
constraint fewer. Note it; do not correct for it.

### 3.2 Cosmetic: the tiles look different, and there are 24 kinds not 32

Carcasum's pack is the **2014, pre-garden JCloisterZone `basic.xml`: 24 kinds, 72 tiles.**
Ours is `basic:2`: **32 kinds, 72 tiles.** The difference is the eight C3
"garden"/flowers *graphic* variants, which the 2014 pack folds back into their non-garden
counterparts. The OUR-kind → THEIR-id map is total and many-to-one, and **the deck-count
multiset agrees exactly** ([`vendor/README.md`](../../vendor/README.md); mapping in
`tests/data/carcasum/`).

**Zero gameplay consequence — the deck is the same deck.** But the artwork is JCZ's, not
the phone app's, and the board/meeple rendering is a 2014 Qt widget rather than the phone
UI. Tell him so a strange-looking tile is not read as a rule change.

### 3.3 Cosmetic-ish: no legal-move affordances he may be used to

Carcasum's board view offers the legal placements for the drawn tile and the legal meeple
nodes for the placed tile (`getTileMove` / `getMeepleMove` are handed `placements` /
`possible`), so it will not let him make an illegal move. But the *presentation* differs
from the phone app, and **Help ▸ Controls** is worth reading once before game 1
(it auto-opens on first launch).

Two menu items are hazards rather than deltas, and belong in the protocol, not here:
**Game ▸ Choose Tiles** (lets the human pick the drawn tile — a cheat switch) and
**Game ▸ Undo** (takebacks). Both must stay unused; see [`PROTOCOL.md`](PROTOCOL.md) §3.

---

## 4. Rules items that were *checked and agree* — do not re-litigate

| item | evidence |
|---|---|
| final totals | 50/50 exact, both seats, every game |
| per-ply totals | no `SCORE_FINAL`, no `SCORE_TIMING` — never parted mid-game either |
| **farm scoring**, computed independently on both sides | **50/50 exact** — ours from `aux_targets.extract_terminal_ownership`, theirs from `score_detail["field"]`. Not inferred from agreeing totals. |
| farms actually exercised | 50/50 = **100%** (the check wanted >80%) |
| modern per-field farm rule (3 pts per completed city) | Carcasum uses the *current* rule, not a variant — [`EXTERNAL_INVENTORY_R2_2026-08-23.md`](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md) §3.1 item 4 ("Field scoring itself is fine") |
| legality inversion | zero `VOID_UNMAPPABLE`, zero `LEGALITY_OURS_EXTRA` — every Carcasum move mapped onto exactly one of our legal actions |
| unplaceable-tile redraw (A3) | exercised 4× in the corpus, **agreeing**, classified non-REAL |
| tiny-city = 4 | positively proven on a constructed case (§2.1) |
| start tile | retail `RCr` on both sides |
| meeples | `MEEPLE_COUNT 7` (`static.h:32`) |
| replay determinism of the archive | 50/50 |

**Known blind spot, unchanged from the JCZ oracle:** tie-break and majority-ownership
semantics are inferred from score agreement only and have never been diffed at feature
level ([`EXTERNAL_INVENTORY_R2`](../../docs/research/EXTERNAL_INVENTORY_R2_2026-08-23.md)
§3.3 item (d)). 50/50 exact agreement over a farm-heavy corpus makes a live divergence
unlikely, but it is not proven.

**Audit coverage limit:** 50 games of *cheap* play (greedy vs a 50 ms opponent). It
exercises farms heavily and redraw lightly; it does **not** exercise deep-endgame or
meeple-contested states at champion strength
([`AUDIT_READOUT.md`](../carcasum_audit_20260823/AUDIT_READOUT.md) §5).

---

## 5. One non-rules asymmetry worth naming: Carcasum is not reproducible

Carcasum's RNG seed is **compile-time only**, so its MCTS is not reproducible even on an
identical deck — the gate-6 smoke ran *the same 4 decks twice* and got 3/0/1 then 2/0/2
([`../carcasum_smoke_20260823/SMOKE_READOUT.md`](../carcasum_smoke_20260823/SMOKE_READOUT.md) §4).

For the owner session this is **convenient**: there is no seed to control, no deck to
pin, and no risk of him meeting the same game twice. For the statistics it means **no
CRN / deck pairing is available** — the session is an unpaired sample, which is exactly
how [`PROTOCOL.md`](PROTOCOL.md) prices it.
