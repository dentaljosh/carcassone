# OM-D2 — the honest-mask rerun, adjudicated against the four pre-registered gates

**Verdict: 4/4 gates PASS. No gate failed in a direction the prereg calls impossible
(`false_tied == 0` on 31,827 tile rows and 74,894 meeple rows). One rider and one flag,
both recorded below.**

⛔ Read-only adjudication. No repo writes outside this worktree; no production-code
change; the frozen prereg constants are **superseded in writing here, not patched in
`scripts/omm1/omm1_lib.py`.**

* Gates of record: [`FINDING.md`](FINDING.md) §5.
* Rerun (owner-approved): `…/agent-abfe6c58e4ad5ba70/measurement/legal_cache_key_20260830/rerun_tiletie/`
  — `meeple_tie_census.py` under the **default-ON injective legal-cache key**
  (python-side fix only; wheel/venv unchanged), 1,299 games / both corpora, W=30,
  `tile_gap` on, `git_rev 74f8d520`.
* Bank: [`../tiearb_widening_20260817/census/`](../tiearb_widening_20260817/census/READOUT.md)
  — same script memoised, `git_rev 1627a801`, champ449 tile-gap only.
* **Comparability confirmed:** same leaf `a36d2e15a3b3d71d` (`leaf_hash_assert_ok`),
  same `walled` profile, same `game_kwargs {}`, identical champ449 corpus sha256
  `fa6704df…`, and the join is **total on champ449 — 31,827/31,827 keys, 0 bank-only,
  0 rerun-only** (the rerun's extra 60,233 tile rows are the `tiearb2_850` corpus the
  bank never read, reported separately and never pooled into a comparison).
* Machine-readable: [`RERUN_ADJUDICATION.json`](RERUN_ADJUDICATION.json); probe
  [`adjudicate_rerun.py`](adjudicate_rerun.py).

---

## 1. The gates

| gate | bar (as frozen in FINDING.md §5) | measured | verdict |
|---|---|---|---|
| **`G-HONEST`** | the regenerated census agrees with a fresh `tiearb_probe` replay on **1.0000** of joined FIRED keys (was 0.99550) | **10/10** banked witness keys now read `tie_exact = true`, and **10/10** carry a `top1` bit-equal to the honest-mask replay banked in `WITNESS_DIFFS.json`; independently, **24/24** rows my cache-OFF replay predicted would move reproduce **exactly** (`tie_exact`, `tie_size_exact`, `top1`, `gap`) in the fixed-key rerun — two different fix routes, same answer | **PASS**, with the coverage caveat in §4 |
| **`G-DIRECTION`** | `false_tied == 0` — honest masks may only ADD tie partners | **`false_tied = 0`** of 31,827 tile rows (and 0 of 74,894 meeple rows). `tie_exact` moved on **339** rows, **all** `false → true`. `tie_size_exact` moved on **578**, delta histogram **entirely positive** (+1 ×352, +2 ×119, +3 ×58, +4 ×25, +5 ×7, +6 ×8, +7 ×1, +8 ×3, +9 ×3, +10 ×2) | **PASS** |
| **`G-TOP1`** | `top1` unmoved on ≥ 99.9 % of rows | **99.9937 %** (2 / 31,827 moved) | **PASS** — see the rider |
| **`G-RATE`** | population rate + Wilson CI reported; frozen constants superseded explicitly | table in §2; supersession in §3 | **PASS** |

**Rider on `G-TOP1` (does not change the verdict, but corrects §4.2 of FINDING.md).**
Both moved rows are the *last* tile ply of their game (`k_remaining = 1`) and both moved
**DOWN** under the honest mask: `(28000000099, 142)` −6.75 → −7.00 (tie size 2 → 10),
`(28000000133, 142)` +21.25 → +21.00 (tie size 5 → 8). So the memo did not merely hide
tie partners — at these two plies it **inflated `top1` by 0.25 off an illegal
continuation**. My 639-row witness-game sample read `top1_moved = 0` and FINDING.md §4.2
generalised from it that the defect is purely subtractive; on the full population that
is true of the tie COUNTS (0 `false_tied`, all-positive size deltas) but **not of the
`top1` column**, which is not monotone. Rate 2/31,827 = 0.0063 %. Neither row changed
`tie_exact` (both were and remain tied), so no fire decision moves.

---

## 2. Old → new headline numbers

### 2.1 TILE tie census (champ449, the like-for-like population)

| statistic | banked (memoised) | rerun (honest key) | Δ |
|---|---:|---:|---:|
| tile rows | 31,827 | 31,827 | — |
| exact-tied rows | 20,322 | **20,661** | **+339** |
| exact-tied fraction | 0.63851 [0.63322, 0.64378] | **0.64917 [0.64391, 0.65439]** | +1.066 pp |
| exact-tied tile plies / game (both seats) | **45.26** | **46.016** | +0.755 |
| … per seat | 22.63 | **23.008** | +0.377 |
| rows with any field moved | — | 580 (1.82 %) | — |
| `n_legal` moved | — | **0** | — |

⚠️ The two Wilson intervals overlap, and that is the wrong lens: the comparison is
**exactly paired row-by-row** (same 31,827 keys, same boards, same leaf), the movement
is **one-directional** (339 up, 0 down), so +339 is a **deterministic correction, not a
sampling difference**. Quote it paired; never as "within CI, therefore unchanged".

`n_legal` moved on **zero** rows — the TILE mask was never wrong. This confirms the
localisation: the collision only ever corrupted the **meeple continuation** mask inside
`chain_values`, exactly as [`FINDING.md`](FINDING.md) §2 traced it.

### 2.2 TILE, pooled (rerun only — new population, no banked counterpart)

| statistic | rerun, 1,299 games / both corpora |
|---|---:|
| tile rows | 92,060 |
| exact-tied | 59,717 |
| fraction | 0.64867 [0.64558, 0.65175] |
| per game | 45.972 |

### 2.3 MEEPLE census — **bit-identical, nothing moved**

| statistic | banked | rerun | Δ |
|---|---:|---:|---:|
| meeple rows | 74,894 | 74,894 | — |
| rows with any field moved (`tie_exact`, `tie_size_exact`, `top1`, `top2`, `gap`, `n_legal`, `argmax_action`, `played_is_argmax`) | — | **0** | **0** |
| exact-tied | 10,896 | 10,896 | 0 |
| `phi_meeple_ply` | 0.14549 [0.14298, 0.14803] | **0.14549** (identical) | 0 |
| fired/game · arbitrable/game · arbitrable fraction | 7.236 · 1.410 · 0.195 | 7.236 · 1.410 · 0.195 | 0 |
| `branch_hint` | `M-DEAD` (*"arbitrable_plies_per_game 1.410 < 4.0"*) | **`M-DEAD`**, same `why` string | 0 |

The meeple predicate evaluates one action per chain and never queries a successor's
legal mask, so it has no exposure to the defect — now measured, not assumed.
`MEEPLE_CENSUS.json`'s `groups` and `branch_bars` are equal in every numeric field; the
single byte-level difference in the whole file is the ORDER of two entries with an
identical `count` (1043) inside `groups.tiearb2_850.gap_cdf.gap_top20` — a sort
tie-break, not a value.

---

## 3. Downstream consumers — STANDS / FLAGGED

| consumer | verdict |
|---|---|
| **Meeple-ply widening closure (`M-DEAD`)** — `docs/LEVER_INDEX.md` L220, the widening campaign's terminal state | **STANDS unconditionally.** 0/74,894 rows moved; the branch hint and its arithmetic are byte-identical. |
| **OM-M1 `G-FIRE`, rate half** (`omm1_lib.BANKED_TIED_TILE_PLIES_PER_GAME = 45.26`, bracket [0.60, 1.00]) | **STANDS.** Corrected denominator moves the measured fraction 0.8182 → **0.8047** (champ449) / **0.8055** (pooled) — comfortably inside the bracket. The direction is the benign one: the deployed trigger is a slightly *tighter* subset of a slightly *larger* honest tie set. |
| **OM-M1 `G-FIRE`, join half** (0.99550) | **STANDS, and the residual is now explained rather than tolerated.** Re-running the join against the honest census is expected to read 1.0000; see §4. |
| **OM-M1 bar `BAR_DELTA_FLIP = 0.22`** | **STANDS as frozen** (house rule: frozen rounds keep their frozen bars) and is **structurally immune to this correction** — the bar is `target × P / G_arb` and the fire rate cancels (`OM-D1`). |
| **`omm1_lib.FIRED_PLIES_PER_GAME_WALLED = 45.26` → `R_X_PTS_PER_CHANGED_PICK`** | **SUPERSEDED, reporting-only.** 45.26 → 46.016 moves `R_X` 0.10171 → **0.10004** pts per changed pick. Nothing adjudicates on it. |
| **`omm1_lib.MEAN_ARMS = 3.0022`** (from `tiearb2_20260816/corpus/positions/POSITIONS_PLAN.json`, itself built off an earlier memoised census: `census_rows_n 3400`, `census_qualifying_n 1809`) | ⚠️ **FLAGGED, not superseded.** Honest tie sets are strictly LARGER (+1…+10 partners on 578 rows), so `mean_arms` is an under-estimate of unknown size — I did not recompute it (it needs the afterstate dedupe + the `J = 4` cap, which damps the effect). It is the ONE input the OM-M1 bar does consume: `bar(A) = (1 − 1/A)/G_arb` reads 0.21723 at A = 3.0022, 0.21894 at 3.05, 0.22066 at 3.1, 0.22394 at 3.2. The frozen 0.22 therefore sits within ~2 % of the plausible corrected value; **disclose in the OM-M1 readout, do not re-derive a frozen bar.** |
| **`jcz_tiearb_20260817` `phi` / `G-FIRE`** (READOUT.md L76/L108) | **STANDS.** `phi = 19.19` is measured IN-CELL from the runtime rust instrumentation, with 22.96 carried only as an *offline prior* (`tiearb2_stage2 DESIGN.md` §2.1 fixes it as a prior, not a prediction). No census join. |
| **tiearb2 Stage-2 Phase B / b64 promotion / T-TRANSFER / phasegate** | **STANDS.** Confirmed unchanged from FINDING.md §4.3: the trigger is evaluated at runtime by `carc_core::tiearb` on both arms, and the honest set is what it always fired on. `phasegate_prep/DESIGN.md` cites none of the census constants (its grep hits are log noise). |
| **Composition ledger** | **NOT TOUCHED.** No composition-ledger artifact consumes the tile-tie or meeple-tie census rates — the ledger references live in `hpm1_fieldfate_gate_20260830/PREREG.md`, `e4_exploit_grading_20260825/COMPOSITION.md`, `cl083_redteam_20260830/MECHANISM_MENU.md`, `docs/LEVER_INDEX.md`, `docs/PROGRAM_ROADMAP_2026-07-07.md` and `governance/CLAIM_REGISTRY.csv`, none of which cite 45.26 / 63.85 % / 22.96. |
| **`tiearb_widening_20260817/census/READOUT.md`** L100 / L109 / L239 | **SUPERSEDED by §2.1** (45.26 → 46.016; 63.85 % → 64.92 %). A banner stamp on that READOUT is owed at close-out — a doc touch for the owner, not made here. |

---

## 4. What `G-HONEST` does and does not cover (honest caveat)

The literal `G-HONEST` instrument is a fresh `build_fired_plies.py` replay joined
against the regenerated census. The OM-M1 build's `FIRE_CENSUS.json` caps
`disagreement_examples` at **10**, so **10 of the 20** disagreeing plies from the
120-game slice are individually verifiable — and all 10 now agree. The other 10 keys
were never banked and cannot be recovered without re-running the replay
(leaf-only, ~20 s at W=30 — cheap, but it is compute and the box is spoken for).

What makes the PASS more than those 10 keys:

1. **Both directions of the population are now measured**: 0 `false_tied` on 31,827
   rows, and every one of the 339 `tie_exact` moves is `false → true` — the direction a
   rust fire requires.
2. **Two independent fix routes agree exactly**: my memo-OFF replay (2026-08-30,
   `DEFECT_RATE.json`) and the owner's injective-key rerun produce bit-identical rows on
   all 24 predicted moves and on all 10 witnesses.

**Owed at close-out, cheap:** re-run `build_fired_plies.py --limit 120` against the
regenerated census and record the join as **1.0000/4,443** (or report whatever it is).
Until that runs, `G-HONEST` is PASS **on the banked witness set**, not on the full
fired set — stated so no later reader over-reads it.

---

## 5. One-line summary

The honest-mask rerun confirms the OM-D2 localisation in every particular: **+339
previously-missed exact ties (+1.07 pp, 45.26 → 46.02 tied tile plies/game), zero ties
lost, zero tile-mask errors, and a meeple census that did not move a single row** —
so every census tie statistic was a floor, the arbiter was always firing on the correct
set, and no adjudicated verdict moves.
