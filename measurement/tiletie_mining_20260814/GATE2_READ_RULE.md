# TILE-TIE GATE 2 — READ-RULE (mined candidates, holdout-confirmed)

> **STATUS AT WRITING: COMMITTED BEFORE THE GATE IS RUN — no candidate-vs-oracle
> cross-fit or FINAL-slice statistic has been computed anywhere at the time of
> this commit.** The mining report ([MINING_REPORT.md](MINING_REPORT.md),
> commit `0bd2c3d1`) computed in-sample dev-slice captures for single features
> — those are the numbers that *motivated* this menu and they are disclosed
> there; the cross-fit screen, the fold selections, and everything touching the
> FINAL slice do not exist yet. The gate instrument is
> `scripts/tiletie/term_gate2.py`; output lands in `GATE2_READOUT.{md,json}`
> and is read strictly through §5. Git history proves the ordering.

Attempt 2 of the tile-tie offline discrimination gate (CL-073 shape:
discrimination, not prediction), per DESIGN §7.2 of
[../tiletie_term_20260814/DESIGN.md](../tiletie_term_20260814/DESIGN.md):
this menu was **mined, not guessed** — and because the mining shopped the dev
labels, the dev cross-fit can only ever be a **screen**; conviction is
reserved for the never-touched FINAL slice.

## 1. Corpus and the firewall

- **Dev slice**: the 522 positions / 279 roots of
  [MINING_REPORT.md](MINING_REPORT.md) §0 (the 733-position pricing corpus
  minus holdout roots). Joins, checksums, pool rules, oracle means (all
  M=32 CRN worlds), `scale_all`, and the pool = tie-set-arms-only convention
  are exactly the spent gate's
  ([../tiletie_term_20260814/GATE_READ_RULE.md](../tiletie_term_20260814/GATE_READ_RULE.md)
  §1); the incumbent is `arms[0]` (lowest index).
- **FINAL slice**: the 211 positions / 120 roots of
  [HOLDOUT_ROOTS.json](HOLDOUT_ROOTS.json) (seed 2026081402, committed
  `a2f05436` before any mining number). This attempt's mining never parsed
  their oracle records (filename firewall + analyzer assertion). Disclosed
  honestly: attempt 1's gate DID read these positions for a *different,
  guessed* menu — the firewall protects against THIS attempt's selection;
  what remains shared is the corpus itself (the §7.1 corpus-burn caveat).
- The FINAL slice's oracle records are opened **only** inside the
  screen-passed branch of §5 — a screen fail leaves the slice unburned for
  any future attempt.

## 2. The candidates — exactly three, mined, frozen here

Per-arm features are the mining extractor's, computed on the tile afterstate
diff vs the root from the root player's POV
(`mine_oracle_sep._extract_one_rich`); `None` (no meeple on board) reads as 0.
Pick rule per candidate: **argmax of sign·feature over the pool, exact ties →
lowest action index** (a constant feature reproduces the incumbent and
captures exactly 0).

| # | candidate | definition | mining justification (all in-sample, disclosed) |
|---|---|---|---|
| 1 | **`dist_own_meeple+`** | min Manhattan distance from the placed cell to any own-meeple tile; prefer the FARTHEST | top positive capture +0.0532 (z +1.34); view-A separation Δ +0.129 (z +1.85), mid-heavy; coherent with `cmp_meeplediff` Δ z +2.16 |
| 2 | **`dist_centroid-`** | Manhattan distance from the placed cell to the root-board occupancy centroid; prefer the CLOSEST | capture +0.0476 (z +1.04), the strongest mid-phase candidate (+0.124, z +1.40 mid, where the pricing spread lives) |
| 3 | **`occ4+`** | occupied orthogonal neighbours of the placed cell (root board); prefer the SNUGGEST | reverse of the only convicted-harmful axis (`occ4-` z −2.67); weak positive (+0.0219, z +0.73) |

Frozen preference order for selection ties: 1, 2, 3 as listed.

**The pre-named FINAL candidate is #1, `dist_own_meeple+`** — named here,
before any cross-fit number exists. The FINAL slice is evaluated on this
candidate only, exactly once, regardless of what the dev cross-fit selects.

**Deployment wart, disclosed now:** unlike attempt 1's term these are
functions of *(afterstate, just-placed cell)*, not of the state alone — a
deploy would inject at tile-move ordering/prior level, not inside the leaf
proper. The cost read (§4) prices the feature computation against a leaf
call; the injection point would be specified in the prereg, which only a
G2-PASS licenses.

## 3. Statistics

- `capture[p] = (V̄[a_T] − V̄[arms[0]]) · scale_all[p]` — identical to the
  spent gate's PRIMARY definition (all-transposition plies are analytic
  zeros for any tie-set-only intervention).
- **SCREEN (dev)**: 5-fold root-clustered cross-fit, fold seed **2026081403**
  (fresh; the spent gate's 20260814 and the holdout's 2026081402 are not
  reused), folds partition dev `root_id` by seeded shuffle; per fold the
  selection rule (largest mean train-fold capture, ties by §2 order) is
  applied to the other four folds and the selected candidate scores the
  held-out fold; the 522 held-out values pool into one mean; cluster-robust
  se on `root_id`; `z_dev = mean/se`. ⚠️ **The screen is NOT a confirmatory
  number**: the 3-candidate menu was itself selected on these labels by the
  mining, so `z_dev` is optimistic by construction. It exists to decide
  whether the FINAL slice is worth burning, nothing else.
- **FINAL**: computed only if the screen passes (§5). The pre-named candidate
  `dist_own_meeple+` scores every FINAL-slice position; mean of
  `capture_all`, cluster-robust se on `root_id`, root-resampling bootstrap CI
  (10,000 reps, seed 2026081403), `z_fin = mean/se`. Evaluated **exactly
  once**; no second candidate, no reweighting, no exclusions beyond the §1
  pool<2 rule.
- Power, stated in advance: the FINAL slice is ~40% of dev, so its se will
  land near 0.05–0.07 pts; `z_fin ≥ 2` therefore needs a true capture ≈
  0.10–0.14 pts/ply ≈ 45–60% of the honest ceiling (+0.199 dev / +0.234
  pooled). Only a mechanism-sized effect can pass; that is deliberate — a
  micro-effect could not survive deploy economics anyway.
- Ceiling context to quote with any result: honest dev ceiling +0.1986 ±
  0.0909; pooled S2b +0.2340.

## 4. Cost read (predictor, informational)

Median ratio (leaf call + candidate-feature computation) / (leaf call) over
replayed corpus afterstates, pure-python flat leaf, quiet box — the jrules-G7
"leaf multiplier ≈ wall-clock multiplier" predictor idiom. The features are
O(meeples)+O(1) scans, so the expected ratio is ~1.00–1.01; reported in the
readout either way. The 1.20 deploy trigger from the house prereg template
applies only to a licensed deploy, which only G2-PASS reaches.

## 5. Branches — first match wins

| # | condition | read |
|---|---|---|
| **G2-0** | any checksum mismatch, missing leg, arm mismatch, or > 5 pool<2 exclusions on any slice actually evaluated | **UNREADABLE** — fix the harness; no other branch fires. |
| **G2-HARMFUL** | `z_dev ≤ −2.0` | The mined menu discriminates **negatively** even in-sample-adjacent cross-fit. Record and stop. **FINAL slice NOT evaluated, stays unburned.** |
| **G2-SCREEN-FAIL** | `−2.0 < z_dev < +2.0` | **The gate FAILS at the screen.** FINAL slice NOT evaluated, stays unburned. Mandatory reporting: realized 2σ resolution; the second-failed-menu implication for the MINING_REPORT §1 bound. No prereg licensed. |
| **G2-FAIL-FINAL** | `z_dev ≥ +2.0` and `z_fin ≤ 0` | The dev signal did not survive the untouched slice — dev overfit convicted. Gate FAILS; FINAL slice now burned; no prereg licensed. |
| **G2-WEAK** | `z_dev ≥ +2.0` and `0 < z_fin < +2.0` | Directionally confirmed, under-powered. **No prereg licensed**; the only licensed follow-up is a supply extension sized from the realized FINAL se. FINAL slice burned. |
| **G2-PASS** | `z_dev ≥ +2.0` and `z_fin ≥ +2.0` | **Conviction on a never-touched slice.** Licenses (does NOT fund) the deploy prereg draft `DEPLOY_PREREG.md` per the house template; the deployed candidate is `dist_own_meeple+` and the quoted effect is the FINAL-slice number only. |

**No branch below G2-PASS licenses a deploy prereg. No branch anywhere
licenses a game.** 0 games; no results.csv row, no band claim, no claim id;
`governance/PRODUCTION.yaml` untouched.

## 6. Pre-stated threats

1. **In-family ruler** (unchanged from the pricing design): a fail closes
   "capture visible to `clair-puct` over this leaf", not "capture in truth".
2. **Chain-granularity**: features on the tile afterstate; a deployed rule
   also acts at deeper nodes. Direction unknown.
3. **The dev screen is contaminated by mining** — stated in §3; that is why
   it cannot convict, only spend or protect the FINAL slice.
4. **92% `walled` self-play corpus** — inherited verbatim.
5. **Offline capture ≠ deploy elo** — a G2-PASS prices the mechanism, not a
   deploy cell (priors/leaf injection inside an 11008-sim search that already
   recovers part of the spread).
6. **`None`→0 encoding** of the meeple distances slightly blunts candidate 1
   on no-meeple boards (early plies); accepted, frozen.
