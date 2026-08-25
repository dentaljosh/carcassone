# READOUT — Carcasum arbiter-transfer challenge

> ✅ **ADJUDICATED 2026-08-25.** Read under the frozen instrument: branch `carcasum-arb-freeze`,
> tip `bcbce7ca` (blind commit `7cd3aafb` → stamped `21e13f10`; band amendment #1 `fa174be0` →
> stamped `bcbce7ca`). Prereg: [`../carcasum_arb_challenge_prep/READ_RULE.md`](../carcasum_arb_challenge_prep/READ_RULE.md)
> + [`DESIGN.md`](../carcasum_arb_challenge_prep/DESIGN.md), both committed before the band was
> claimed and before game 1. Analyzer: `scripts/carcasum_match/analyze_arb_challenge.py`
> (`--selftest` ALL OK, run immediately before this adjudication). Machine-readable twin:
> [`READOUT.json`](READOUT.json).

---

## §0 — HEADLINE

**Branch `T — TRANSFER` fired, verbatim from `READ_RULE.md` §4.**

> **T — TRANSFER** | `D >= 2.0` pts AND `z_D >= 2.0` | Report: the arbiter's internal gain
> (`+66 elo` desktop) transfers externally. State `D`, `z_D`, and the implied elo-per-point
> conversion from THIS cell's own secondary numbers (not r1's, to avoid a cross-band elo
> scale). This is new evidence for widening the arbiter's authorized use beyond the
> champion-mirror confirmation it currently rests on.

```
D      = +6.1875 pts/deck   (ARM-ON minus ARM-OFF, deck-paired across arms)
SE(D)  =  1.3768 pts/deck
z_D    = +4.4941
n_common_decks = 200        (800 games total; 400 per arm, 200 decks x 2 seats)
```

`D >= 2.0` ✅ and `z_D >= 2.0` ✅ — both conditions of `T` met, and `T` is the first row of the
branch table, so first-match-wins resolves here. **The tie-arbiter's gain is not
champion-mirror-specific: it transfers to an external, out-of-lineage opponent.**

---

## §1 — `D` (void contamination), checked FIRST per §3.1

| arm | n_records | n_scored | `VOID_*` total | REAL-divergence total | void rate | REAL rate | DONE sentinel |
|---|---|---|---|---|---|---|---|
| ARM-OFF | 400 | 400 | **0** | **0** | 0.0% | 0.0% | ✅ `DONE_arm_off` |
| ARM-ON | 400 | 400 | **0** | **0** | 0.0% | 0.0% | ✅ `DONE_arm_on` |

**`D` does not fire.** Zero of either class in either arm, against a 1%-of-games bar — the same
clean result r1 posted on its own 400 games. Both arms reached their own `DONE` sentinel. No
gate failed (§2). The r1 divergence-audit taxonomy (`SCORE_FINAL`, `FARM_SCORE_FINAL`,
`MEEPLE_LEGALITY`, `MEEPLE_SLOT_UNMAPPED`, `LEGALITY_OURS_EXTRA`, `HARNESS_ERROR`,
`DRIVER_REJECT`, `SEAT_DESYNC`, `COORD_FRAME_MISMATCH`) was applied unchanged, as designed —
the arbiter is a search-time knob, not a rules knob.

---

## §2 — STRUCTURAL GATES — 9/9 PASS

| id | verdict | detail |
|---|---|---|
| `G-BINARY` | **PASS** | both arms `carcasum_binary_sha256 = c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968`, cross-checked EQUAL between arms (the r1/rung2 laptop build; this cell also ran on the laptop) |
| `G-RULES` | **PASS** | `rules_manifest.name = "fixed_v1"`, `r9_env_ok = true`, both arms |
| `G-BUDGET` | **PASS** | `{kind:"mcts", budget_ms:5000, playouts:null, cp:0.5, reuse_tree:false, node_priors:false, progressive_widening:false, progressive_bias:false, utility:"portion", playout:"random"}` exactly, byte-identical between arms |
| `G-CHAMP-OFF` | **PASS** | ARM-OFF `harness_leaf_hash = a36d2e15a3b3d71d` (pinned `PROD_LEAF_HASH`); `cand_tiearb = null` — no arbiter leak onto the OFF arm |
| `G-CHAMP-ON` | **PASS** | ARM-ON same leaf hash `a36d2e15a3b3d71d` (the arbiter does not move the leaf); `cand_tiearb = {enabled:true, B:64, J:4, mode:"argmax", salt:"tiearb2-deploy-v1", eps:0.0}` exactly as pinned |
| `G-SINGLEVAR` | **PASS** | `our_git_rev` (`bcbce7caabae5fb96e27b008ea748af4d27408ff`), `rules_profile`, `opponent`, `sims_override` (null), `k_dets_override` (null), `execution.backend` (`rust`) all identical across arms — **`champion_manifest.cand_tiearb` is the only manifest field that differs.** The `track_d2_prep` lesson holds: this was checked, not asserted. |
| `G-N` | **PASS** | ARM-OFF `n_paired = 200`, ARM-ON `n_paired = 200`, both ≥ the 160-deck 80% floor, before intersection |
| `G-SHARED-DECKS` | **PASS** | every realized `deck_seed` in both arms ⊂ `{147000000000..147000000199}`; intersection = **200** decks (perfect — no deck lost from either arm) |
| `G-TIMING` | **PASS** | ARM-OFF median `opp_driver_ms_per_turn = 5006.187` (**+0.124%** off 5000ms, 14,195 pooled opponent turns); ARM-ON `5006.177` (**+0.124%**, 14,190 turns). Both far inside ±10%, and — notably — inside rung 2's tighter ±5% too. |

The arbiter cost the opponent nothing: the two arms' realized opponent budgets agree to
0.01 ms of median. TIME-mode drift under contention, the risk `G-TIMING` was loosened for,
did not materialize.

---

## §3 — PRIMARY: the deck-paired difference-of-differences

Estimator exactly as named in `READ_RULE.md` §1, before any number existed:

```
margin_ARM(d) = (margin_ARM(d, seat0) + margin_ARM(d, seat1)) / 2
D(d)          = margin_ON(d) - margin_OFF(d)
D             = mean(D(d))              = +6.1875 pts/deck
SE(D)         = stdev(D(d)) / sqrt(200) =  1.3768 pts/deck
z_D           = D / SE(D)               = +4.4941
```

Sign convention (load-bearing, r1's own): margin is **champion minus Carcasum**, so `D > 0`
means the arbiter's presence made the champion do **better**. It did.

**Arithmetic cross-check** (the §2 "recomputation is a witness" discipline): the two arms' own
paired margins are `+9.5950` (ON) and `+3.4075` (OFF); `9.5950 − 3.4075 = 6.1875` — identical
to the analyzer's `D` computed over per-deck differences, as it must be at a perfect 200/200
intersection.

**Power, versus what was pre-registered.** `DESIGN.md` §3.1 named two SE models before launch:
Model A (precedent-based) `SE_D = 1.25`, Model B (conservative independent-draw) `SE_D = 1.38`.
The realized `SE_D = 1.3768` lands **on Model B, essentially exactly** (realized `sigma_D =
1.3768·√200 = 19.47` pts/deck vs Model B's pre-registered `19.54`). The conservative model was
the truer one — a clean, pre-registered calibration hit worth recording for the next cell in
this family. It did not cost the read: the realized effect is `D = 6.19`, ~2.5× the `delta=2.5`
bottom-of-range the top-up was reserved against, so `z_D = 4.49` clears 2σ with room to spare
even at the loosest SE.

**The §2 equivalence-region self-check holds as derived:** `|z_D| = 4.49 ≥ 2.0` and
`|D| = 6.19 ≥ 2.0` pts — the promised "no significant-but-below-the-equivalence-bar case can
occur at this n" is confirmed by this cell's own arithmetic, not merely asserted.

---

## §4 — SECONDARY, per arm (witness — never a branch input)

| statistic | ARM-OFF | ARM-ON | delta |
|---|---|---|---|
| games | 400 | 400 | — |
| W / D / L | 235 / 4 / 161 | 271 / 5 / 124 | +36 W, −37 L |
| win rate | 0.59250 | **0.68375** | +0.09125 |
| `elo_from_win_rate` | **+65.02** | **+133.95** | **+68.92** |
| deck-paired margin | +3.4075 pts | +9.5950 pts | +6.1875 |
| `SE(paired margin)` | 1.0190 | 0.9618 | — |
| own-arm `z` | +3.344 | +9.976 | — |
| median `opp_driver_ms_per_turn` | 5006.187 | 5006.177 | −0.01 ms |

Within-band 1σ on the secondary win-rate→elo statistic is ±17.4 elo at n=400
(`695·√(0.25/400)`) — the per-arm elo figures carry that, and are reported for corroboration
only.

**Implied elo-per-point conversion, from THIS cell's own numbers** (as `T` instructs — r1's
scale is deliberately not used, to avoid a cross-band elo conversion):

```
elo_ON - elo_OFF = 133.9467 - 65.0243 = 68.9224 elo
D                =                       6.1875 pts
=> implied scale = 11.14 elo per point of final-score margin, against this opponent
```

**The arbiter is worth ≈ +69 elo against Carcasum@5000ms**, on this cell's own secondary
scale. Compare — carefully, as context and not as a contrast — the arbiter's internal
champion-mirror figure of ≈ +66 elo (`DESIGN.md` §0). The two are strikingly close, but they
are different opponents on different scales and the agreement is *corroborative colour, not a
measurement*; nothing in this readout rests on it.

**ARM-OFF as a cross-band replication of r1.** ARM-OFF is the unmodified champion, byte-identical
config to r1, on band `147e9` where r1 ran on `142e9`:

| | r1 (`b142e9`) | this cell's ARM-OFF (`b147e9`) |
|---|---|---|
| deck-paired margin | +4.08 pts (z +4.18) | +3.41 pts (z +3.34) |
| win rate | 0.56875 | 0.59250 |
| `elo_from_win_rate` | +48.08 | +65.02 |

Same sign, same tier, both comfortably significant. The ~0.67-pt margin gap and the ~17-elo
elo gap are **exactly the size the standing CL-068 cross-band humility discount predicts**
(1.8–2.2× SD inflation on any cross-band contrast) and are read as replication, not as drift.
**This comparison is corroborative only and is never substituted for `D`** — `D` is a
within-band, deck-paired, single-variable contrast and is therefore in the robust class that
CL-068 explicitly exempts.

---

## §5 — TOP-UP DECISION

**The reserved 50-deck top-up is NOT consumed. Seeds `147000000200..147000000249` remain
unspent.**

`READ_RULE.md` §4's top-up row fires on `|z_D| < 2.0 AND |D| > 2.0` — i.e. only on an
inconclusive read. Realized `|z_D| = 4.49`, which is not `< 2.0`, so the condition is false.
Independently, `T` is the first matching row and first-match-wins resolves the table there
before the top-up row is reached. The top-up remains available; it was a guard against Model B
being the truer SE model, and although **Model B was in fact the truer model** (§3), the
realized effect size was large enough that the guard was not needed.

Per the `BAND_REGISTRY.csv` convention, band `147e9` seeds `..000`–`..199` are now **SPENT**
(games exist on them and they influenced a decision — they retire from confirmatory use);
seeds `..200`–`..249` never had a game run on them and fall under the
"RELEASE-IF-NEVER-LAUNCHED" clause.

---

## §6 — ARBITER TELEMETRY (ARM-ON, `champ_tiearb`, all 400 games)

Present in all 400 ARM-ON records; **absent from all 400 ARM-OFF records**, independently
corroborating `G-CHAMP-OFF`/`G-CHAMP-ON` from the game bodies rather than the manifest alone.

| quantity | total (400 games) | per game | note |
|---|---|---|---|
| `tile_plies` | 13,787 | 34.47 | champion's own tile-placement plies |
| `fires` | 7,221 | 18.05 | **52.4% of tile plies had a tie the arbiter resolved** |
| `fired_plies` | 7,221 | 18.05 | equals `fires` — one fire per ply, no double-counting |
| `pickchanges` | 4,206 | 10.52 | **58.2% of fires actually changed the pick** |
| `arms_total` | 24,342 | 60.86 | 3.37 arms per fire (of the B=64 cap) |
| `playouts_total` | 1,557,888 | 3,894.7 | J=4 per arm |
| `errors` | **0** | 0.0 | zero across all 400 games |
| `first_error` | `null` ×400 | — | no game recorded a first error |
| `partial_argmax` | **0** | 0.0 | never degraded to a partial argmax |
| `mode` / `B` / `J` | `argmax` / 64 / 4 ×400 | — | resolved config stable every game |
| `secs` | 142,218.8 s | **355.5 s** | arbiter wall-clock, **sequential** |

**Nothing anomalous.** Zero errors, zero partial-argmax degradations, and a resolved
`mode/B/J` that never drifted across 400 games — the arbiter ran exactly as pinned. The fire
rate (52.4% of tile plies) and the pick-change rate (58.2% of fires) are substantive, not
marginal: the arbiter is actively re-deciding roughly **10.5 tile placements per game**, which
is a plausible mechanism for a +6.19-pt margin swing rather than a statistical accident.

**The 355.5 s/game arbiter cost is latency-only and expected.** ARM-ON ran the arbiter
**sequentially** — threads are not wired into this code path — so this figure is the
single-threaded upper bound, not a property of the arbiter's design. It is a wall-clock cost
only: it does not enter `D`, it does not touch the opponent's budget (`G-TIMING`: the two arms'
median opponent turn times differ by 0.01 ms), and it does not affect any statistic in this
readout. It is exactly why ARM-ON took ~6 h against ARM-OFF's ~4 h.

---

## §7 — WHAT THIS DOES AND DOES NOT LICENSE

Per `READ_RULE.md` §5, unchanged by the outcome:

- **Does not** generalize to Carcasum configurations other than
  `MCTSPlayer<PortionUtility,RandomPlayout>`, `Cp=0.5`, 5000 ms — a different config, or a
  different external engine, is a fresh cell.
- **Does not** re-confirm or revoke the arbiter's DEPLOYED internal authorization
  (`governance/PRODUCTION.yaml tiearb_authorized_by`), which rests on its own closed evidence.
  This cell only widens the *context* in which that authorization can be read.
- **Does not** measure or gate on how the arbiter's firing *rate* differs against a genuinely
  different opponent — §6's rate is descriptive telemetry, not a branch input. (For the
  record: 52.4% of tile plies against Carcasum.)
- **Does not** speak to the R9-off (`walled`) production elo scale — the standing caveat every
  Carcasum cell carries. All numbers here are R9-on.

What it **does** license, per `T` verbatim: this is **new evidence for widening the arbiter's
authorized use beyond the champion-mirror confirmation it currently rests on.** The arbiter's
gain survives contact with an opponent outside our lineage, built by someone else, from a
different codebase — which is precisely the generalization the internal cells could not test.

---

## §8 — PROVENANCE

| item | value |
|---|---|
| run id | `carcasum_arb_challenge` |
| band | `147000000000` (amended pre-launch from `144000000000`; zero games on the original) |
| decks | `147000000000..147000000199` primary (spent) · `..200..249` top-up (unspent) |
| instrument | branch `carcasum-arb-freeze`, tip `bcbce7ca` |
| blind commits | `7cd3aafb` → stamped `21e13f10`; amendment `fa174be0` → stamped `bcbce7ca` |
| `manifest.our_git_rev` (both arms) | `bcbce7caabae5fb96e27b008ea748af4d27408ff` |
| box | laptop (`laptop-wsl`) |
| Carcasum binary | `c090847e1befa007e9b3b3031a9c880a60915e36f143aa6c3c30691599792968` |
| champion leaf | `a36d2e15a3b3d71d` (`PROD_LEAF_HASH`) |
| rules | `fixed_v1`, `CARCASSONNE_FIX_R9=1`, both sides, both arms |
| ARM-OFF finished | 2026-08-24 20:55 (`DONE_arm_off`) |
| ARM-ON finished | 2026-08-25 02:51 (`DONE_arm_on`) |
| analyzer | `scripts/carcasum_match/analyze_arb_challenge.py`, `--selftest` ALL OK |
| games | `arm_off/games.jsonl` (9,611,796 B) · `arm_on/games.jsonl` (9,765,504 B) |
| launcher logs | `../carcasum_arb_challenge_prep/logs/{arm_off,arm_on,run_cells}.log` |

**Launcher hygiene:** the launcher's `EXIT` trap cleared its `RUN_LIVE.json` correctly — a sweep
of `measurement/**/RUN_LIVE.json` on the laptop returns nothing, no `match.py` process remains,
and both `DONE` sentinels are present. No stale sentinel to clean, and the freeze-latch hook is
not blocked by this cell.

---

## §9 — CLOSE-OUT STATE

Adjudication is complete and the branch is fired. The `DESIGN.md` §10 six-touch checklist
(`experiments/results.csv` row → `DECISIONS.md` index line → status banners → governance row
flip in `BAND_REGISTRY.csv` / `CLAIM_REGISTRY.csv` → `STATUS.md` top block → roadmap line →
`docs/LEVER_INDEX.md` row for *"Carcasum arbiter-transfer challenge"*, then
`scripts/doc_lint.py`) touches **main-tree** files, which are under the freeze latch and are
the orchestrator's call — it is deliberately **not** performed here.
