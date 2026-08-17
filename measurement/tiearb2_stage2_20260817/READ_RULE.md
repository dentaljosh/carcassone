# STAGE 2 — PHASE B: THE DECK-PAIRED GAME CELL (READ-RULE)

> **STATUS AT WRITING: COMMITTED BEFORE THE INSTRUMENT AND BEFORE ONE GAME EXISTS.**
> No rust arbitration knob, no runtime tie-detector, no positive control, no band
> claim, no `summary.json`, no `manifest.json` for any cell of this run exists at the
> time of this commit. It is committed in the **same commit** as
> [DESIGN.md](DESIGN.md). Git history proves the ordering and every run manifest
> carries this commit's hash. Definitions are frozen here by reference to DESIGN §1–§7.
>
> **This read-rule is fully mechanical.** Every branch is a boolean function of numbers
> the harness emits. **No owner call adjudicates any outcome.** It is spent on this
> mechanism and this band; any successor needs a fresh one of each.

## 1. Scope

- Two cells, **`ARB`** and **`RND`** (DESIGN §1), **n = 800 deck-paired games each**,
  on the **same fresh band `132000000000`** and the **same decks**, at production
  budget k8×1376 = 11,008, exact-K 2, against the unmodified champion.
- **The branch input is the pair of within-band deck-paired reads.** Cross-band
  comparison is not a branch input anywhere (CLAUDE.md cross-band humility); the robust
  class is exactly what is used.
- The arbiter is `B` = 16, `J` = 4, salt `tiearb2-deploy-v1` (DESIGN §2), i.e. the
  selection half of Stage 1b's arm `H` — the rung that captured *and*, after Phase A,
  the rung that is affordable (`rho_wall` 0.6224).
- **`governance/PRODUCTION.yaml` is untouched on every branch.** A pass licenses a
  production-flip **decision for the owner**, never an automatic flip.

## 2. The committed quantities

| symbol | definition |
|---|---|
| `M_arb`, `M_rnd` | the per-deck **seat-balanced paired margin** (points/game) of the cell's candidate vs the champion, `summary.json` |
| `z_arb`, `z_rnd` | `summary.json::paired_z` (`_paired_z`, `eval_fair_puct.py`) — **the primary statistic** |
| `E_arb`, `E_rnd` | the same in elo, by the harness's own conversion |
| **`D`** | `M_arb − M_rnd`, **deck-paired over the decks completed in BOTH cells** |
| **`z_D`** | `D` over its own paired se, computed the same way as `paired_z` |
| `ms_ratio_x` | `champ_prefix_ms_per_move / rung_ms_per_move`, in-cell, per cell. ⚠️ **`champ_prefix_ms_per_move` IS THE CANDIDATE SIDE** in `eval_fair_puct` |
| `phi_x` | realized tied tile plies per game at which the arbiter fired, per cell |
| `n_common` | decks completed in **both** cells (the denominator of `D`) |

**The bars are `+2.0` (z) and `1.20` (the N4 cost trigger).** Neither is a new constant:
`+2.0` is Stage 1's, Stage 1b's, `E-FLAT`'s and `W-FLAT`'s verbatim; `1.20` is the house
N4 trigger currency, the same bar Phase A's `rho_wall` was graded at.

## 3. Preconditions — checked FIRST, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of:**

| id | condition |
|---|---|
| `G-J1` | either cell's resolved `cand_leaf_hash` **differs** from the champion's `a36d2e15a3b3d71d`. ⚠️ **Inverted gate: a difference is an ABORT, not a finding** |
| `G-J4` | `config.cand_tiearb` is absent or unresolved in either `manifest.json`, or its `mode` is not `argmax` for `ARB` and `random` for `RND`, or its `B` ≠ 16 or `J` ≠ 4 |
| `G-J13` | the **two-sided** positive control did not pass on **each** host before that host's game 1 (`PREFLIGHT_*_${HOST}_FIRST.json`): the arbiter must **change the pick** at a constructed tied ply **and** leave `root_leaf_value_bits` **unchanged** |
| `G-FIRE` | `phi_arb < 1.0` **or** `phi_rnd < 1.0` — the surface is inert and the cell would grade a champion-vs-champion null wearing the shape of a real cell |
| `G-BAND` | band `132000000000` was not claimed before game 1, or the two cells did not run on the same band and the same decks |
| `G-N` | `n_common < 600`, **or** either cell completed fewer than 640 of its 800 paired games |
| `G-TOOL` | the two boxes did not run the same rust toolchain / the same `carc_rs` build, or a cell mixed builds |
| `G-STAT` | `z_arb`, `z_rnd` or `z_D` is `NaN` or absent |

`U-UNREADABLE` = report cost, integrity, firing rates, and whichever gate failed.
**Nothing closes, nothing is licensed, nothing is re-labelled.**

## 4. Branches

**Evaluated in this order. `U-UNREADABLE` (§3) pre-empts everything.**

**Then, pre-emptively:**

```
G-ANOMALY  ≡  z_rnd ≥ +2.0
```

Let, on the complement (so `z_rnd < +2.0` below):

```
p ≡ C_arb ≡ z_arb ≥ +2.0        # the arbiter beats the champion
q ≡ C_ctl ≡ D ≥ 0               # ...and is not below its own cost-matched control
r ≡ C_res ≡ z_D ≥ +2.0          # ...and the two are RESOLVED against each other
```

`r ⇒ q` (a `z_D ≥ +2.0` requires `D > 0`), so the cell `p ∧ ¬q ∧ r` is vacuous; `G-CLOCK`
is defined as `p ∧ ¬q` irrespective of `r` so the table stays total.

| # | condition | read |
|---|---|---|
| **`G-ANOMALY`** | `z_rnd ≥ +2.0` | **THE COST-MATCHED CONTROL ITSELF BEATS THE CHAMPION — THE FRAME IS WRONG AND NOTHING ELSE IN THIS TABLE MEANS WHAT IT SAYS.** A *random* arm chosen at tied plies, after burning the identical playouts, wins games. That is a finding about the champion's own tie-break (or about spending clock at tied plies), **not** about terminal grounding. Report both cells in full, `D`, `z_D`, both `phi`, both `ms_ratio`. **Nothing closes and nothing is licensed.** |
| **`G-CONFIRMED`** | `p ∧ q ∧ r` | ⭐ **TERMINAL-GROUNDED TIE ARBITRATION WINS GAMES AGAINST THE CHAMPION, AND IT IS THE MECHANISM RATHER THAN THE CLOCK.** The candidate convicts at 2σ on a fresh band, its wall-clock-matched control does not, and the two are **resolved against each other at 2σ**. This is the first deploy-elo evidence on this axis and the only reading that discharges DESIGN §12.1's caveat. **Licenses (does NOT do) exactly one thing: a production-flip DECISION for the owner.** ⛔ It does not flip `PRODUCTION.yaml`, does not license a leaf term (CL-065 + two dead menus + the 38% reach bound stand), does not license an on-device deploy (**`rho_phone` = 5.520 at `B` = 16 — the phone currency was never solved**), and does not license a second cell. |
| **`G-DEPLOYS`** | `p ∧ q ∧ ¬r` | **THE CANDIDATE BEATS THE CHAMPION AND THE CONTROL DOES NOT — BUT THE TWO ARE NOT RESOLVED AGAINST EACH OTHER.** `z_arb ≥ +2` and `D ≥ 0` and `z_rnd < +2`, yet `z_D < +2`. **DESIGN §6 states before the run that n = 800 cannot resolve `D` to 2σ at the expected effect size** (se(`D`) ≈ 1.41× the single-cell se ⇒ a true +18 elo reads `z_D` ≈ 1.5), so this branch is *expected* on a real effect and is **not** a demerit. **Licenses (does NOT do) a production-flip DECISION for the owner, explicitly labelled as resting on an unresolved control.** The read-out must print `z_D` and the `n` that would resolve `D` to 2σ. |
| **`G-CLOCK`** | `p ∧ ¬q` | **THE CANDIDATE BEATS THE CHAMPION, BUT ITS WALL-CLOCK-MATCHED CONTROL IS NOT EXCLUDED — THE WIN CANNOT BE ATTRIBUTED TO THE MECHANISM.** `RND` burns the identical playouts on the identical worlds at the identical plies and picks at random, and it did at least as well. ⇒ what is being measured is clock, or pick perturbation, not terminal grounding. **Nothing closes and nothing is licensed**, and in particular this does **not** license a deploy decision. |
| **`G-PRESENT`** | `¬p ∧ ( z_arb ≥ +1.0 ∨ z_D ≥ +1.0 )` | **PRESENT BUT NOT CONVICTED — UNRESOLVED.** The direction is there and the bar is not met. **Nothing closes and nothing is licensed.** Report both cells, `D`, `z_D`, both `phi`, both `ms_ratio`, and **the `n` that would convict at the realized dispersion.** |
| **`G-FLAT`** | `¬p ∧ ¬( z_arb ≥ +1.0 ∨ z_D ≥ +1.0 )` | **THE MECHANISM DID NOT EXPRESS AS DEPLOY ELO ON A FRESH BAND AT n = 800.** ⚠️ **Mandatory scope sentence, quoted with the verdict and never separated from it:** *"This is a BOUNDED null, not an exclusion. DESIGN §6 states before the run that n = 800 deck-paired resolves ≈ ±8.5 elo at 1σ (±17 at 2σ), while the offline bound chain reads +18.09 elo CI [+6.32, +30.04] with a ÷5.23 low-end bracket at +11.06 — so a null here does NOT exclude the low end of the offline estimate. The honest claim is 'terminal-grounded tie arbitration did not express as deploy elo at n = 800 on band 132000000000', NOT 'terminal grounding is worth nothing in games'."* **Rider, mandatory when it applies:** if the 95% upper bound on `E_arb` is below +6.32 elo, the read-out must **additionally** state that the offline CI is excluded at 95% and the scope sentence is superseded in that one respect. **Second rider, mandatory always on this branch:** Stage 1b read `arb_H` = +0.1441 pts/tied ply at z +3.01 with the sign check CORROBORATING, so a flat game read is a **tension with a published result** and must be reported as such — print both, and do **not** present the tension as resolved. The operative statement to record: *the mechanism is real under a terminal-grounded ruler and did not survive the transfer to games at this power; DESIGN §12.1's caveat is therefore **not** discharged.* |
| **`U-UNREADABLE`** | any §3 precondition fails | §3. |

### 4.1 Exclusivity and exhaustiveness — verified in the pre-registration text

- §3 is evaluated **first** and pre-empts everything. `G-ANOMALY` is evaluated **second**
  and pre-empts the rest, so the remaining five are evaluated only where
  `z_rnd < +2.0`.
- On that complement the five partition `(p, q, r)` exactly: `p∧q∧r` → `G-CONFIRMED`;
  `p∧q∧¬r` → `G-DEPLOYS`; `p∧¬q` → `G-CLOCK` (total in `r`, and `r ⇒ q` makes `p∧¬q∧r`
  vacuous); `¬p` splits into `G-PRESENT` and its **exact negation** `G-FLAT`.
- ⇒ **exactly one branch matches every possible read, and the match does not depend on
  presentation order.** Any `NaN` in `z_arb`/`z_rnd`/`z_D` is caught by `G-STAT` in §3
  before a comparison is taken, so no branch is entered on a `NaN` comparison.
- This is verified by a machine sweep over the branch-condition truth table in
  `tests/test_tiearb2_stage2.py`, which **re-transcribes this section independently of
  the implementation** and asserts exactly one branch fires on every cell, `NaN`
  included.

### 4.2 The N4 cost rider — applied to every branch, and it is NEVER a branch input

`ms_ratio` is a **downgrade trigger**, not a conjunct:

- If `ms_ratio_arb > 1.20` or `ms_ratio_rnd > 1.20`, the read-out **downgrades the
  against-champion reading to COST-CONFOUNDED** and says so **in the branch sentence**.
- It does **not** touch the mechanism contrast `D` / `z_D`: `ARB` and `RND` are
  cost-matched to each other by construction, so `D` is immune to a budget confound.
- ⚠️ **DESIGN §5 predicts `ms_ratio` ≈ 1.1985 — just under the bar — and says so before
  the measurement.** A reading either side of 1.20 was therefore anticipated and is not
  a surprise; `ms_ratio ≤ 1.05` restores a fully cost-neutral reading.
- ⚠️ **The field-name trap**: `champ_prefix_ms_per_move` is the **CANDIDATE** side in
  `eval_fair_puct` (confirmed at live lines 2361/2371/2389). A read-out that swaps them
  inverts the verdict.

### 4.3 Mandatory on every branch — the full companion table

The read-out MUST print:

1. Both cells: `n` completed, `n_common`, `M`, `paired_z`, elo with CI, wr, and the
   seat balance.
2. `D`, its paired se, `z_D`, and the `n` that would resolve `D` to 2σ at the realized
   dispersion.
3. `phi_arb` and `phi_rnd` beside the offline prior **22.96** and its funnel (65.98%
   exact-tie rate on tile plies, 40.4% deduped scoreable), with **DESIGN §2.1's two
   runtime-vs-corpus mismatches restated verbatim** — the offline rate *estimates*, and
   does not equal, the runtime rate.
4. `ms_ratio` for both cells with the field-name trap named, and the §4.2 rider.
5. Every §3 gate with its realized value, including the two-sided J13 witness per host.
6. **DESIGN §12.1 of Stage 1b carried verbatim** (condition (b)) and **arm `C`'s NO
   CORROBORATION sign-check verdict carried verbatim** (condition (c)) — on every
   branch, including the passing ones.
7. The Phase-A cost facts that licensed this cell: `c_tier1_rust` 0.178232 worker-s/
   playout, 15.30× the pilot, `rho_wall(16)` 0.6224 — and **`rho_phone(16)` = 5.520,
   labelled NOT SOLVED**.
8. The realized band, the deck range, and the `BAND_REGISTRY` claim row.

## 5. What no branch does

- No branch edits `governance/PRODUCTION.yaml`. **A pass licenses a production-flip
  DECISION for the owner and nothing more.**
- No branch licenses an **on-device / phone** deploy: `rho_phone` was never brought
  under 1.20 above `B` = 2, and Phase A stamped it *reported, unadjudicated*.
- No branch adds a leaf term, changes the production leaf, or trains anything.
- No branch re-reads, re-labels or re-adjudicates Stage 1, Stage 1b, or Phase A. They
  stand as adjudicated; the Stage-1b read-rule is spent and its corpus burned.
- No branch licenses a second game cell. **This read-rule is spent when the read-out
  lands**, on every branch.
