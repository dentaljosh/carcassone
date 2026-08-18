# MEEPLE-PLY TIE KILL-CENSUS — READ-OUT (rung (1), widening campaign)

> **Status: ADJUDICATED 2026-08-18. Branch `M-DEAD` fires. Rung (1) is closed; rung (4)'s
> banked kill is corroborated on a fresh read.** Adjudicates
> [`PLAN_meeple_ties.md`](../PLAN_meeple_ties.md) §5 mechanically, plus the gap-CDF piggyback
> [`PLAN_eps_near_ties.md`](../PLAN_eps_near_ties.md) §3 asked rung (1) to carry. No owner call
> adjudicates any outcome here; the bars below were committed before the instrument existed
> (plans at commit `0efdbefb`, instrument at `bfa2f591`, run at `1627a801`).
>
> This is a census. It counts and never scores: no search, no playouts, no outcome statistic,
> **no strength claim, no `experiments/results.csv` row, `governance/PRODUCTION.yaml` untouched.**

---

## 1. THE BARS, AS WRITTEN — before any number

### Rung (1), [`PLAN_meeple_ties.md`](../PLAN_meeple_ties.md) §5

The supply bar is derived there from the tile rung's own realized transfer: 22.96 fired
plies/game × 0.1441 pts/tied ply = 3.309 predicted vs **3.0700 realized** ⇒ τ = 0.928; a
game cell at n=800 deck-paired has se ≈ 0.691 pts/game ⇒ resolves only effects ≥ 1.381
pts/game ⇒ required `f × v ≥ 1.488` ⇒ `f ≥ 10.3` arbitrable plies/game at v = 0.1441
(`f ≥ 8.3` even at the tile *oracle* value 0.1801). The branch table, verbatim:

| Branch | Condition (on `MEEPLE_CENSUS.json`, pooled over both corpora, reported per corpus) | Action |
|---|---|---|
| **M-DEAD** | `arbitrable_plies_per_game < 4.0` | Rung closed. No pricing, no code touch. LEVER_INDEX row + roadmap row + DECISIONS line. |
| **M-MARGINAL** | `4.0 ≤ arbitrable_plies_per_game < 8.0` | **No pricing funded.** Hand the class to rung (4) `eps>0` … |
| **M-DUP-BOUND** | `fired_meeple_plies_per_game ≥ 8.0` **and** `arbitrable_fraction < 0.40` | Not a pricing campaign. Propose the cheap hygiene change instead: dedupe arms by **board-region key** … gated on rung (3)'s own read-rule. |
| **M-PRICE** | `arbitrable_plies_per_game ≥ 8.0` **and** `arbitrable_fraction ≥ 0.40` | Fund the §6 offline pricing on a **fresh** corpus + **fresh** read-rule. |
| **M-VOID** | C5 duplicate-invariance FAILS, or `phi` differs between the two corpora by > 2× | No branch is adjudicated. Report the discrepancy; re-census on one homogeneous stratum. |

Plus: *"Ties between branches resolve to the **more conservative** (lower-spend) row. The census
is adjudicated **once**, on the pooled read, with the per-corpus split shown but never used to
pick a branch."*

Cost bar, §4: *"**≤ 0.5 worker-h total**; **< 5 min wall at W30 local** … **Bar: if it exceeds
30 min wall, stop and report — the instrument is wrong, not the lever.**"*

### Rung (4), [`PLAN_eps_near_ties.md`](../PLAN_eps_near_ties.md) §3

> **`K-DEAD` (the cheap kill):** *if the first lattice rung above float noise (`eps = 0.05`) adds
> **< 5% relative** fired plies, the rung dies for free.*

> **`K-STRUCTURAL` (the second, independent kill):** the rung needs an eps satisfying **both**
> (i) `m(eps) ≥ 0.30` (§4's affordability floor) and (ii) the added plies are *near*-ties …
> **These are mutually unsatisfiable on the banked distribution:** `m ≥ 0.30` requires
> `eps ≳ 1.5–2.0` points.

Both were pre-fired on banked data (`+0.99%` tiletie / `+0.68%` tiearb2 at eps=0.05). This
census's tile leg is the fresh read against those two numbers.

---

## 2. FIRED BRANCH — verbatim

> | **M-DEAD** | `arbitrable_plies_per_game < 4.0` | Rung closed. No pricing, no code touch. LEVER_INDEX row + roadmap row + DECISIONS line. |

**Fires on:** pooled `arbitrable_plies_per_game` = **1.410** < 4.0. The bar is missed by **2.84×**
on the reported (both-seats) convention and by **5.67×** on the arbiter-side convention (§4).

**No other branch fires.** `M-MARGINAL` needs ≥ 4.0. `M-PRICE` needs ≥ 8.0 **and** fraction ≥ 0.40:
neither conjunct holds (1.410; 0.195). `M-DUP-BOUND` splits — its *fraction* conjunct **holds**
(0.195 < 0.40) and its *supply* conjunct **fails** (`fired_meeple_plies_per_game` 7.236 < 8.0), so
the hygiene rider is **NOT licensed by this census as written**; the duplicate-crowding evidence in
§6 is recorded and licenses nothing. `M-VOID` does not fire (§7).

---

## 3. THE DECISION STATISTICS, WITH THEIR BARS

Pooled over both corpora, 1,299 games, leaf `a36d2e15a3b3d71d` (assert OK), profile `walled`.

| statistic | bar | realized (POOLED) | champ449 | tiearb2_850 |
|---|---|---|---|---|
| `arbitrable_plies_per_game` (fired ∧ `equiv_groups_board ≥ 2`) | **M-DEAD < 4.0**; M-PRICE ≥ 8.0 | **1.410** (1,832 plies) | 1.394 | 1.419 |
| `arbitrable_fraction` | M-PRICE ≥ 0.40 | **0.195** | 0.193 | 0.196 |
| `fired_meeple_plies_per_game` (`repr_arms ≥ 2`) | M-DUP-BOUND ≥ 8.0 | **7.236** (9,400 plies) | 7.218 | 7.246 |
| `phi_meeple_ply` (tied / meeple plies with ≥2 legal) | prior 16.5% (JCZ meta) | **14.55% [14.30, 14.80]** (10,896/74,894) | 14.43% | 14.61% |
| `phi_meeple_move` (tied / 72-move denominator) | — | 11.65% [11.45, 11.86] | 11.54% | 11.71% |
| tied meeple plies/game | prior 4.82/game | 8.388 | 8.31 | 8.43 |

Precision: the plan projected *"~6,000 tied meeple plies expected ⇒ se on any reported fraction
≤ 0.7 pp"*; realized 10,896 tied plies, se on `arbitrable_fraction` = **0.41 pp**, so the M-PRICE
fraction bar (0.40) sits 50 se away. On supply: 1,832 arbitrable plies observed against
4.0 × 1,299 = **5,196 required** to clear M-DEAD, a shortfall of 3,364 plies against a counting
se of ~43. Not a precision-limited call at either bar.

Phase cut (pooled, both seats): early `arbitrable/game` 0.819 (fraction 0.189), mid 0.249 (0.158),
late 0.343 (0.256). No bucket reaches 4.0; the highest arbitrable *fraction* is late-game 0.256,
still below M-PRICE's 0.40.

---

## 4. THE SEAT CONVENTION — the census counts BOTH seats, the tile rung's 22.96 does not

The census's per-game denominators are whole games (both seats). The tile rung's `22.96 fired tile
plies/game` and Stage-2's realized `phi` 17.5725 are **candidate-side** counts — the arbiter only
fires inside the searching player's own search. The census's own tile leg pins the factor:
20,322 exact-tied tile plies / 449 games = **45.26 both-seats** = **22.63 per seat**, which
reproduces 22.96.

So, on the arbiter-side convention the bar is stated in:

| | both seats (as reported) | per seat (arbiter-side) |
|---|---:|---:|
| meeple `fired/game` | 7.236 | **3.618** |
| meeple `arbitrable/game` | 1.410 | **0.705** |
| tile exact-tied/game (this census, champ449) | 45.26 | 22.63 |

The M-DEAD bar is missed under both conventions; the reported number is the **larger** of the two,
so the kill is stated in the rung's favour. Per-seat meeple fired supply is 3.618 vs the tile
rung's ~17.6 realized fired plies/game = **20.6%**, which reproduces the plan's §2 free prior
("~21% of the tile rung's 22.96") from a measurement instead of arithmetic.

---

## 5. DUPLICATE vs GENUINELY TIED — both sides of the split

Of 10,896 exact-tied meeple plies (pooled):

| class | definition | count | share |
|---|---|---:|---:|
| pure DUPLICATE | `repr_arms ≥ 2`, `equiv_groups_board == 1` | 7,568 | 69.5% |
| single-arm | `repr_arms < 2` — the arbiter never fires | 1,496 | 13.7% |
| pure DISTINCT | `equiv_groups_board ≥ 2` and `repr_arms == equiv_groups_board` | 1,443 | 13.2% |
| mixed | `equiv_groups_board ≥ 2` and `repr_arms > equiv_groups_board` | 389 | 3.6% |

Both sides, stated: **1,832 of 9,400 fired plies (19.5%) carry ≥2 distinct board regions and are
arbitrable in principle** — the arbiter could separate them, and this instrument deliberately says
nothing about whether a playout would. **7,568 of 9,400 (80.5%) are game-equivalent duplicates**:
same connected feature, different recorded meeple `side`, guaranteed leaf tie, identical world-means
under CRN, decided by lowest-index fallback.

Mean tied-set sizes: raw 2.201 → repr arms 2.057 → intra-tile groups 1.187 → **board regions
1.182**. The July intra-tile census's key and the board-level key agree to 0.003 groups/ply on this
corpus (mean `intratile − board` = 0.003), i.e. cross-tile farm merging adds almost nothing at the
tied sets — the July lower bound was nearly tight here.

---

## 6. THE `J ≤ 4` CAP AND THE ARM-DEDUP INEFFICIENCY — recorded, licenses nothing

- mean(`repr_arms − equiv_groups_board`) over fired plies = **1.029** — about one redundant arm per
  fired ply;
- **84.6%** of fired plies carry ≥1 redundant arm;
- `repr_arms > 4` (the `J ≤ 4` truncation the plan asked for) = **0.22% [0.15, 0.34]** (21/9,400);
  `equiv_groups_board > 4` = **0.00%** (0/9,400).

Read together: on meeple plies the duplicate arms are real (1.03/ply) but the cap they would crowd
against is essentially never binding (0.22%), so the `M-DUP-BOUND` hygiene rider would buy nothing
on this ply class even if its supply conjunct had fired. Whether the same dedupe pays on the **tile**
class is a rung-(3) question and is untouched by this census.

---

## 7. INTEGRITY ITEMS

**Manifest.** `manifest.json` carries the resolved config: `git_rev 1627a801` (the instrument's own
build commit `bfa2f591` plus two non-instrument commits; `git diff 1627a801 -- scripts/tiletie/meeple_tie_census.py`
is empty), `leaf_hash_of_record a36d2e15a3b3d71d` with `leaf_hash_assert_ok true`, profile `walled`
with `r9_env_ok true`, full leaf env, both corpus paths with sha256, `tie_eps_grid [0.0, 0.05, 0.2,
0.5, 1.0]` (the tile census's grid, unchanged), per-corpus counters, `aborted: null`.

**Cost vs the ≤0.5 worker-h bar.** Total **0.4266 worker-h** (1,535.8 worker-s) — under the bar for
the whole run, including the piggyback. Split: meeple census leg **152.8 s**, tile-gap piggyback leg
**1,300.4 s**, replay residual 82.6 s. **52.2 s wall at W=30**, against a *"< 5 min at W30"*
projection and a 30-min abort bar. The meeple leg alone is 0.042 worker-h; the piggyback is 8.5× the
leg it rode on, because a tile chain is ~50–70 leaf calls against a meeple chain's ~3.5.

**M-VOID, cross-corpus consistency.** `phi_meeple_ply` 14.43% (champ449) vs 14.61% (tiearb2_850) —
ratio **1.012**, against a > 2× void bar. Every headline statistic agrees between corpora to within
2%: `arbitrable/game` 1.394 vs 1.419, `arbitrable_fraction` 0.193 vs 0.196, `fired/game` 7.218 vs
7.246. The two corpora are different generations (k4×688 vs the Stage-1b deployed budget) and are
reported separately per the plan; neither was used to pick the branch.

**M-VOID, C5 — the deviation.** The plan's §4 put C5 (duplicate CRN bit-invariance, ≤200 plies,
M=8 playouts per arm) inside the census. **It was not run.** The builder's stated reason, in the
script docstring and in `manifest.json::blind_discipline.note`: *"C5 … is DELIBERATELY NOT
IMPLEMENTED HERE — it needs tier1 playouts and therefore world-mean margins, which is exactly the
outcome-statistic class this instrument is forbidden to touch."* M-VOID's trigger is *"C5
duplicate-invariance FAILS"*; not-run is not a fail, so M-VOID does not fire on this ground and
M-DEAD stands on its own conjunct. **Recorded as a plan deviation, not adjudicated around:** the
sub-claim the plan wanted verified (duplicate arms return bit-identical CRN margins) remains
**unverified by measurement** on this ply class, resting on the code argument in PLAN §1 and on
`crn_worlds_are_shared_by_every_arm` (`tiearb.rs:673-691`). It is only load-bearing if meeple
arbitration is ever revived, in which case it must be run first.

**Blind discipline.** `_GAME_FIELDS_READ = ("game_id", "deck_seed", "actions", "n_plies")`;
`score_p0` / `score_p1` / `sentinel` exist in both corpus files and are dropped at load. The
tiearb2 corpus's **tile** positions are burned, and the tile-gap leg was run with
`--tile-gap-corpora champ449` accordingly — so the burned corpus contributed **meeple** rows only
(§8's tile CDF is champ449-only).

**Independent recount.** Every headline number in `CENSUS.md` was recomputed from
`meeple_rows.jsonl` / `tile_gap_rows.jsonl` by this adjudication, off the summary JSON: phi
0.14548561967580848, fired/game 7.236335642802156, arbitrable/game 1.4103156274056967, fraction
0.19489361702127658, split (7,568 / 389 / 1,443 / 1,496), `repr>4` 21/9,400, tile 20,322/31,827
tied, and the eps CDF at every reported rung — all bit-equal to the published values.

### The conservative biases, in the direction they push

All three documented biases inflate the arbitrable count, i.e. they push **toward keeping the rung
alive**, and the kill fires anyway:

1. **Undescribed slots get a PRIVATE group.** `dense_group_ids` maps a `None` region key to
   `("solo", action)` — *"never merged with another `None`"* — so a slot the tile model cannot
   describe is counted as its own distinct region, never as a duplicate.
2. **PASS is its own arbitrable option.** `PASS_KEY = ("pass",)` under both groupings. Its weight is
   not small: **639 of the 1,832 arbitrable plies (34.9%)** have PASS in the tied set, and **all 639
   have exactly 2 board groups** — their entire arbitrability is "place here vs pass". Dropping them
   takes `arbitrable/game` from 1.410 to **0.918**. Keeping them is correct (pass is game-distinct)
   and is the reading adjudicated.
3. **`arbitrable ⊆ fired`.** The script computes arbitrable as `[r for r in fired if
   r["equiv_groups_board"] >= 2]` (`meeple_tie_census.py:644`), where PLAN §5's prose defines
   arbitrable on `equiv_groups_board ≥ 2` without restating the fired conjunct. The looser,
   plan-literal reading gives **1.517 arbitrable plies/game** (fraction 0.210). Same branch, missed
   by 2.64× instead of 2.84×.

The difference between readings is 139 tied plies (0.107/game) with `repr_arms == 1` and
`equiv_groups_board == 2`. Adjudication reproduced one (`champ449` game 28000000017, ply 11, tied
actions 2502/2503): the two actions claim **different** features — knight on `right` vs knight on
`bottom` — and both features **complete on placement**, so the meeple is scored and returned
immediately and the two successor states are byte-identical in the afterstate repr (same board, same
meeples, same scores, same supply). The rust arm builder keys on the same `(meeple_type, row, col,
side)` per **placed** meeple, so it too would see one arm. The tighter reading is therefore the
faithful one, and the board-region key alone over-counts arbitrability by ~7% on this corpus.

---

## 8. THE EPS PIGGYBACK — corroboration and one contradiction

`gap = top1 − top2` (top2 = next DISTINCT leaf value) was emitted per row, upgrading rung (4)'s
5-point grid into a full CDF, for zero extra leaf calls, as
[`PLAN_eps_near_ties.md`](../PLAN_eps_near_ties.md) §8 asked.

### TILE class — `K-DEAD` and `K-STRUCTURAL` both corroborated

31,827 tile plies (champ449, all tile plies of all 449 games), exact-tied **63.85%** (20,322),
smallest nonzero gap 2.22e-16.

| eps | banked tiletie | banked tiearb2 | **this census (tile)** |
|---:|---:|---:|---:|
| 1e-9 | +0.58% (10/887 untied) | +0.32% (7/1209 untied) | **+0.44%** (90 plies) |
| **0.05** | **+0.99%** | **+0.68%** | **+0.66%** (134 plies) |
| 0.25 | +6.40% | +5.93% | +5.64% |
| 1.00 | +21.28% | +21.77% | +22.69% |
| 1.50 | — | — | +29.93% |
| 2.00 | +31.40% | +34.37% | +35.04% |

**`K-DEAD` is corroborated:** +0.66% at eps=0.05, against the < 5% bar — 7.6× below it. The fresh
curve sits within 0.8 pp of both banked corpora at every rung to eps=0.25 and within 1.5 pp at
eps=1.0; at eps=2.0 it is 0.7 pp from the tiearb2 corpus and 3.6 pp above tiletie's.
**`K-STRUCTURAL` is corroborated:**
`m ≥ 0.30` first arrives at eps ≈ 1.5 (0.2993) / 2.0 (0.3504), i.e. exactly the plan's *"`eps ≳
1.5–2.0` points"* — a full-to-double point of leaf preference being overridden.

⚠️ **Not an independent third corpus.** The banked tiletie census's `selfplay|champ_games|walled`
stratum (1,200 rows, `max_per_game 4`) was sampled from **this same file**
(`measurement/champ_action_logs/champ_games.jsonl`). This leg is a ~26× denser read of the same
games (31,827 of 31,827 eligible tile plies, no sampling), not a new draw. It corroborates by
removing the sampling, not by adding a corpus; the genuinely independent corroborant remains the
tiearb2 corpus census, unchanged on disk.

### MEEPLE class — `K-DEAD` corroborated, `K-STRUCTURAL`'s conjunct (i) CONTRADICTED

74,894 meeple plies, exact-tied 14.55% (10,896), untied-with-gap 63,998, smallest nonzero gap
1.11e-16.

| eps | new plies | rel growth vs fired |
|---:|---:|---:|
| 1e-9 | 79 | +0.73% |
| **0.05** | **378** | **+3.47%** |
| 0.10 | 828 | +7.60% |
| 0.20 | 1,603 | +14.71% |
| **0.25** | **6,134** | **+56.30%** |
| 1.00 | 15,940 | +146.29% |

**`K-DEAD` fires on the meeple class too** (+3.47% < 5%), but with 5.3× less margin than the tile
class's +0.66% — it clears the bar by 1.4×, not by 7.6×.

**The contradiction, stated plainly:** `K-STRUCTURAL`'s conjunct (i) — *"`m ≥ 0.30` requires
`eps ≳ 1.5–2.0` points"* — is a **tile-class** statement and does **not** transfer to meeple plies.
On the meeple distribution `m ≥ 0.30` arrives between eps 0.20 (+14.7%) and eps 0.25 (+56.3%),
driven by an atom of **4,144 untied plies at gap exactly 0.25**. At a quarter-point of leaf
preference the "these are still near-ties" conjunct (ii) is not obviously false, so the two
conjuncts are **not** mutually unsatisfiable on this ply class the way they are on the tile class.

What that does and does not change:

- It does **not** revive rung (4). `K-DEAD` is derived from power arithmetic that is independent of
  any census (PLAN_eps §4: ~5% relative growth needs n ≈ 10⁵ games/cell), and it fires on both
  classes on this fresh read.
- It does **not** revive rung (1). `M-DEAD` closes the meeple class on **supply**, and M-MARGINAL —
  the only branch that hands the class to rung (4) — did not fire.
- The eps-widened meeple sets' **arbitrable fraction is unmeasured**. This census groups by board
  region only over the *exact*-tied set; nothing here says the 6,134 plies added at eps=0.25 are any
  less duplicate-dominated than the 80.5% duplicates at eps=0. Any revival needs that measurement
  plus a new mechanism argument, not a re-read of this file.

---

## 9. WHAT THIS MEANS FOR THE CAMPAIGN

- **Rung (1) meeple plies: CLOSED** on `M-DEAD`. No pricing, no corpus, no code touch. The §7 code
  scope (`tiearb_phases` knob, ~60–90 LoC behaviour + ~150 LoC test/telemetry, the meeple parity
  gate) is not built. Rung (1) leaves the shared prereg, which makes the rung-(2)+(3) bank cheaper,
  not dearer — the plan's §8 stated reason for running this census first.
- **Rung (4) eps>0: CLOSED**, `K-DEAD` + `K-STRUCTURAL` on tile, `K-DEAD` on meeple, now corroborated
  on a fresh 31,827-ply read after being pre-fired on banked data. The one contradiction (§8) is
  recorded against the meeple class and changes no branch.
- **The campaign narrows to the shared rung-(2) `B>16` + rung-(3) `J>4` run**, on the tile class, per
  [`CAMPAIGN.md`](../CAMPAIGN.md) sequencing item 2. Nothing in this census touches either rung's
  design: the `J ≤ 4` truncation numbers here are **meeple**-class (0.22%) and say nothing about the
  tile-class cap that funds rung (3).
- Free hygiene observation, unfunded and unlicensed: the float-noise band is 79/63,998 untied meeple
  plies and 90/11,505 untied tile plies below 1e-9. PLAN_eps §9 Q1's recommendation stands —
  *"document, do not deploy"*.

---

## 10. ARTIFACTS

| file | what |
|---|---|
| [`CENSUS.md`](CENSUS.md) | the instrument's own rendered tables (advisory branch hint `M-DEAD`) |
| [`MEEPLE_CENSUS.json`](MEEPLE_CENSUS.json) | pooled + per-corpus + per-phase statistics, both gap CDFs |
| [`manifest.json`](manifest.json) | resolved config, corpus sha256s, leaf assert, worker-seconds |
| [`run.log`](run.log) | run provenance |
| `meeple_rows.jsonl` (74,894 rows, 65 MB) | per-ply rows — **untracked**, regenerable from the manifest |
| `tile_gap_rows.jsonl` (31,827 rows, 15 MB) | per-ply tile gap rows — **untracked**, regenerable |
| [`scripts/tiletie/meeple_tie_census.py`](../../../scripts/tiletie/meeple_tie_census.py) | the instrument (built `bfa2f591`, unchanged at run time) |
| `measurement/tiearb_widening_20260817/census_smoke/` | the pre-flight smoke at `--limit-games`, same knobs |
