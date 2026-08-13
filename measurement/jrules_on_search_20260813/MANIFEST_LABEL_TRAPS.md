# Manifest label traps — read this BEFORE evaluating N0 or writing the close-out

**Status: RECORDED WHILE BLIND** (2026-08-13, mid-run, ~470/800 records). Wiring only. No
strength number has been read.

The cell's `manifest.json` contains **three boilerplate labels whose prose contradicts the
numbers in the same file**. All three are template strings emitted by the harness whenever a
code path is *available*, not when it is *exercised*. Each one, read literally, would corrupt
the close-out — and one of them would appear to refute `AMENDMENT_1`.

Verified from the manifest itself, not asserted.

## Trap 1 — `equal_wall_clock_note` says "NOT an equal-sims cell". It is one.

```
"ASYMMETRIC budgets: candidate k_dets=8x1376=11008 total vs opponent
 k_dets=8x1376=11008 total per move — this is NOT an equal-sims cell"
```

The note quotes **11008 vs 11008** and then calls them asymmetric. Measured from
`config.champion` and `config.opponent`:

| arm | k_dets | sims_per_det | total |
|---|---|---|---|
| candidate | 8 | 1376 | **11008** |
| opponent | 8 | 1376 | **11008** |

**Budgets are identical.** The string is generic boilerplate for the asymmetric-budget code
path, which this cell does not use.

⚠️ **This matters for `AMENDMENT_1_N4_DIRECTION.md`.** That amendment rests on both arms
running identical search, so that wall-clock is not a strength variable. A reader who takes
this note at face value would conclude the amendment's premise is false. **The manifest's own
numbers confirm the amendment's premise; only its prose contradicts it.**

## Trap 2 — `cand_curve_drift` says "NOT curve125". It is curve125.

```
"curve": "PRE-REGISTERED candidate curve shape (NOT curve125) — --allow-cand-curve-drift"
```

but

```
curve_values              = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
curve125_reference.curve  = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]   # identical
```

**The two arrays are element-for-element identical**, and both match
`governance/PRODUCTION.yaml:119`. The chain passes `--allow-cand-curve-drift`, which *permits*
drift; it does not *introduce* any. **There is no curve drift in this cell.** The candidate
differs from the champion in exactly one field — `jrules_dose 0.25` — which is why
`cand_leaf_hash 15948beccf3472d3` ≠ `a36d2e15a3b3d71d`.

## Trap 3 — `both_sides_curve125: false`. Both sides are curve125.

Same root cause as trap 2: the flag records "the candidate went through the drift-permitted
path", not "the curves differ". Per trap 2 they do not differ.

## Not traps, but record them

- **`code_rev: 217f0cdbe-dirty`.** The `-dirty` suffix is real but benign: at launch the tree
  carried untracked files only (`measurement/scheduler_20260813/`, two untracked
  `tests/test_opencity_*.py`). Every file the cell depends on — the cell JSON, the launcher,
  the leaf, the gate — is committed in `217f0cdb`. The sha alone does not pin the tree, so
  this note is the pin.
- **`host: laptop-wsl`.** Both legs write `manifest.json` into the one shared-claim dir, so
  this records the **last writer**, not "the box that ran the cell". The cell ran on **both**
  boxes (see `LAPTOP_REJOIN_20260813.md`).
- **`endgame.shared_by_both_arms: true`, `exact_k: 2`** — the endgame solver is common to both
  arms, so it cannot differentiate them. Good; it is not a confound.

## Consequence for N0

N0's checks are all evaluable **provided the right paths are used** — several live at manifest
top level, not under `config`:

| N0 requirement | where it actually lives | observed |
|---|---|---|
| cand leaf hash | `config.cand_leaf_hash` | `15948beccf3472d3` ✓ |
| opp leaf hash | `config.opp_leaf_hash` | `a36d2e15a3b3d71d` ✓ |
| resolved dose (the live-term gate) | `config.cand_leaf_cfg.jrules_dose` | `0.25` ✓ |
| no mask key | `config.cand_leaf_cfg` | absent ⇒ default 31 ✓ |
| no `jrules_*` on opponent | `config.opp_leaf_cfg` | none ✓ |
| k_dets / sims, **both** arms | `config.champion.*` and `config.opponent.*` — **NOT** `config.k_dets` (absent) | 8 / 1376 both ✓ |
| rules profile | **top-level** `rules_profile.name` — not under `config` | `fixed_v1` ✓ |
| R9 | top-level `rules_profile.r9_env_expected` **and** `leaf_env.CARCASSONNE_FIX_R9` (note: the field is `r9_env_expected`, not `r9_env_ok` as the prereg words it) | `True` / `"1"` ✓ |
| backend rust both sides | `config.backend` | `rust` ✓ |
| seed_start / n | `config.seed_start` / `config.n` | `128000000000` / `800` ✓ |
| **single `variant_id`** | **nowhere — `eval_fair_puct` never emits it** | **UNVERIFIABLE AS WRITTEN** |

`variant_id` is a `scripts/joshuabot/h2h.py` field that was carried into this prereg from the
Joshua-bot confirm's integrity line. It is **not** satisfied, and must not be reported as
satisfied. The surrogate is: one manifest, and all records agreeing on
`sims` / `k_dets` / `exact_k` / `opponent` / `info` / `rung_sims`.
