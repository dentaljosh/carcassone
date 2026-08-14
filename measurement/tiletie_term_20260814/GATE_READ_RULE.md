# TILE-TIE TERM — OFFLINE GATE READ-RULE

> **STATUS AT WRITING: COMMITTED BEFORE THE GATE IS RUN — no term-vs-oracle joint
> statistic has been computed anywhere at the time of this commit.** Feature
> definitions below were smoke-tested for *computability only* (replay + feature
> extraction on a handful of positions, oracle values never joined). The gate
> instrument is `scripts/tiletie/term_gate.py`; its output lands in
> `measurement/tiletie_term_20260814/GATE_READOUT.{md,json}` and is read strictly
> through the branches in §6. The git history is the proof of ordering.

This is the CL-073-shaped gate the J13 pre-gate prescribes verbatim for this
class of lever: **the gate is DISCRIMINATION, not prediction** — a candidate
term must improve within-tied-set move ordering against a deep ruler BEFORE a
single game is played ([j13_pregate READOUT §"If the term is built anyway"](../j13_pregate_20260813/READOUT.md)).
The deep ruler here is free: the pooled tile-tie pricing corpus
([readout_POOLED/VERDICT.md](../tiletie_pricing_20260812/readout_POOLED/VERDICT.md))
— 733 positions over 399 roots where every deduped tied arm was scored under
M=32 CRN clairvoyant worlds (`clair-puct`, sims 100), integrity 0/0/0/0/0/0.

## 1. Corpus — fixed, no additions, no exclusions beyond the rules below

- Positions: exactly the **733** rids of
  `measurement/tiletie_pricing_20260812/readout_POOLED/per_position.jsonl`.
- Arms + oracle values: joined from
  `measurement/tiletie_pricing_20260812/positions_pooled/ARMS.json` and the raw
  leg records under `/mnt/c/carc-shared/tiletie_pricing_20260812/clair-puct/`
  (join verified before this commit: 733/733 full leg coverage, 0 arm
  mismatches, `pick_a == arms[0]` and `pick_b == arms[r]` on every leg).
- Per-arm oracle value **V̄[a] = mean over ALL M=32 CRN worlds** (`values_a`
  for arm 0, `values_b` of leg r for arm r). No parity split is needed here:
  the pricing run's even/odd cross-fit existed because *selection* was made on
  the same oracle draws; the term selects arms without ever seeing oracle
  values at evaluation time, so the world-noise in V̄ is independent of the
  term's pick and the capture statistic below is unbiased at full M.
- **Term pool** at a position = the tie-set arms only: `arms` minus the
  appended champion arm when `champ_outside_tieset` (the deployed term only
  ever fires inside leaf-tie sets). A position whose pool has < 2 arms is
  excluded and counted in the readout.
- Replay: each position replayed under **its own** `rules_profile` (one
  subprocess per profile — `CARCASSONNE_FIX_R9` is import-latched), checksum
  asserted against the position row's `checksum`; any checksum failure is a
  named integrity failure, not a silent drop. Features are computed on the
  **tile afterstate** `game.get_next_state(board, arm_action)` — the same
  keying the transposition census used — from the **root player's** POV.

## 2. The candidate features — hand-crafted, fixed here

CL-065 forbids a learned tie-breaker; these are four hand-designed state
functions of `(state, decomp)`, each invisible to the production leaf by
construction (they price geometry the leaf has no term for; inside an exact
tie set every existing leaf term is equal across arms by definition).

Component ownership = strict weighted-meeple majority (BIG=2), the
`flat_opencity_term` idiom. "Open cells" of an unfinished city/road component
= distinct empty in-bounds cells across its open edges (the same derivation as
`decompose`'s `*_root_emptyadj`). `occ4(e)` = number of occupied in-bounds
orthogonal neighbours of cell `e` (off-board neighbours count 0).

| feature | definition | mechanism |
|---|---|---|
| **D_city** | `wall_city(opp) − wall_city(self)`, where `wall_city(q)` = Σ over city components owned by q, unfinished, open_n > 0, of Σ over open cells e of `(occ4(e) − 1)` | closure-geometry guard: don't brick up the cells your own claimed city still needs; do constrain his. The leaf's `closure_p[open_n]` counts open cells but is blind to how *fillable* they are. |
| **D_road** | same with road components | same, roads |
| **F_perim** | Σ over `state.open_positions` of `occ4(e)` (player-independent) | board-frontier constrainedness: how snug/jagged the whole frontier is |
| **F_lib** | `len(state.open_positions)` (player-independent) | board liberty: count of legal-placement frontier cells |

The term as implemented (`flat_leaf.flat_tiletie_term`) is
`T = t/(1+|t|)` with `t = (w_city·D_city + w_road·D_road + w_perim·F_perim +
w_lib·F_lib) / tiletie_norm` — the bounded map is strictly monotone, so
**within-tie-set ordering depends only on the weighted raw sum**, never on
`tiletie_norm` or the dose.

## 3. The menu and the selection rule — fixed here

Ten variants, each a weight one-hot (or the mechanism bundle) with sign:

`+D_city, −D_city, +D_road, −D_road, +(D_city+D_road), −(D_city+D_road),
+F_perim, −F_perim, +F_lib, −F_lib`

- **Term pick** at a position = argmax of the variant's raw sum over the pool;
  exact ties in the sum broken by **lowest action index** (the incumbent
  convention — a constant feature reproduces arm 0 exactly and captures 0).
- **Selection rule** (inside cross-fit, §4): the variant with the largest mean
  train-fold capture; a selection tie is broken by the fixed preference order
  exactly as listed above (mechanism bundle after the singles purely by list
  position — the order is frozen here, before any number exists).

## 4. The PRIMARY statistic — cross-fit captured headroom

Per position `p` with term pick `a_T`:

```
capture[p]      = V̄[a_T] − V̄[arms[0]]          (pts, vs the incumbent lowest-index convention)
capture_all[p]  = scale_all[p] × capture[p]     (the I2 analytic-zeros rescale of the pricing
                                                 readout: all-transposition plies are exact
                                                 zeros for ANY tie-set-only intervention —
                                                 the term cannot fire across one board)
```

**PRIMARY = the 5-fold root-clustered cross-fit pooled held-out mean of
`capture_all`.** Folds partition `root_id` (seeded shuffle, seed **20260814**);
in each fold the §3 selection rule runs on the other four folds' labels and the
selected variant is evaluated on the held-out fold; the 733 held-out values are
pooled into one mean. Uncertainty: cluster-robust se on `root_id` **and** a
root-resampling bootstrap (10,000 reps, seed 20260814); the bootstrap CI is the
quoted interval, z = mean / cluster-se. (The bootstrap resamples roots and
recomputes the pooled held-out mean with fold assignments held fixed.)

**Ceiling context** (from the pricing readout, quoted with any result): the
oracle best-of-scored-set leaf regret S2b is **+0.2340 pts/ply (all)** /
+0.3236 (discriminable) — no term can capture more in expectation. The gate
therefore convicts only a term capturing a large fraction of a bounded prize;
that is deliberate and stated in advance.

## 5. Secondary reads — reported, never the verdict

1. **Fixed-variant capture**: `+(D_city+D_road)` (the mechanism-preferred
   bundle, named before any number) evaluated on the FULL corpus with no
   selection — unbiased by construction, no cross-fit needed.
2. **Winner's-curse audit** (house-mandatory): the naive best-of-menu
   full-corpus capture (max over the 10 variants, in-sample) printed beside
   the PRIMARY, labelled *audit only, never quoted as a result*.
3. `capture_vs_champ[p] = V̄[a_T] − V̄[champ_arm]` — descriptive only; the
   deployed term rides *inside* the search, so beating the champion's realized
   pick offline neither licenses nor prices a deploy win.
4. Per-phase (early/mid/late) and per-stratum capture — descriptive; the
   pricing run put the spread in mid/late, so the phase profile is a mechanism
   check, not a branch condition.
5. **Expressiveness**: fraction of positions where `a_T ≠ arms[0]`, per
   variant.
6. Per-variant full-corpus captures (descriptive, in-sample, curse-inflated,
   labelled as such).

## 6. Branches — first match wins, conditions mutually exclusive by construction

`z` = PRIMARY mean / cluster-robust se.

| # | condition | read |
|---|---|---|
| **G0** | join/integrity failure: any checksum mismatch, any missing leg, any arm mismatch, or > 5 positions excluded for pool < 2 | **UNREADABLE.** Fix the harness; no number is read, no branch below fires. |
| **G-PASS** | `z ≥ +2.0` | **The term discriminates.** A hand-crafted tie-break term improves within-tied-set ordering against the deep ruler on held-out roots. This licenses (does NOT fund) the deploy prereg draft `DEPLOY_PREREG.md`; the deployed variant = the §3 selection rule run on the FULL corpus, and the quoted effect is the PRIMARY cross-fit number, never the full-corpus in-sample number. |
| **G-HARMFUL** | `z ≤ −2.0` | **The menu discriminates negatively** — record sign and stop; no prereg draft is licensed. |
| **G-FAIL** | otherwise (`|z| < 2.0`) | **No conviction — the gate FAILS.** The term is not fundable on this evidence. Mandatory reporting: the realized 2σ bound in pts/tied-ply and its §4.3-chain elo equivalent (labelled extrapolation, ±1.6× divisor bracket), and the fixed-variant secondary read. Per house rule this is *no conviction at this menu on this corpus*, never "the tie-break axis is dead" — the pricing run's headroom (+0.252 pts/ply, z +3.43) is a ceiling statement that stands regardless. |

**No branch below G-PASS licenses a deploy prereg. No branch anywhere licenses
a game.** 0 games are played by this gate; no `experiments/results.csv` row, no
band claim, no claim id.

## 7. Pre-stated threats

1. **In-family ruler.** The oracle is `clair-puct` over the leaf under test
   (the pricing DESIGN §5 caveat travels here unchanged): systematic leaf
   blindness under-reports spread, so a G-FAIL closes "capture visible to this
   ruler", not "capture in truth".
2. **Chain-granularity** (pricing DESIGN §6 threat 2): features are computed on
   the tile afterstate; the deployed term is also evaluated at meeple-phase
   and deeper nodes. Inherited, direction unknown.
3. **The menu is 10 variants** — multiplicity is handled by held-out
   cross-fitting, not by pretending one variant was pre-ordained; the only
   selection-free number is the §5.1 fixed variant.
4. **Offline capture ≠ deploy elo.** The gate grades the term as a *pick rule
   at the root of tied sets*; deployed, it acts through priors and leaf values
   inside an 11008-sim search that already recovers part of the spread (S2
   headroom +0.252 vs S2b leaf regret +0.234 — similar, but not the same
   object). A G-PASS prices the mechanism, not the deploy cell.
5. **The corpus is 92% `walled` self-play** (677/733) — the rules-epoch
   tension of the pricing design travels here; per-stratum reads are
   descriptive and underpowered.
