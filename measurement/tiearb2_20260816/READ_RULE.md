# TERMINAL-GROUNDED TIE ARBITRATION — READ-RULE (Stage 1b, the funded successor)

> **ADJUDICATED 2026-08-17 — branch `A-COSTLY` ([READOUT.md](READOUT.md)).**
> All seven §3 preconditions passed. For arm **`H`** (honest, B = 16) `C_z`
> (z +3.01 ≥ +2.0), `RBAR` (`F_fixed` 0.514 ∧ `F` 0.800, `G-BOOT` not fired) and
> `C_split` (both slices INFORMATIVE and non-negative) **all fired ⇒ `PASS(H)`**.
> For arm **`C`** (cheap, B\* = 2) `C_z` (z +0.65), `RBAR` (`F_fixed` 0.115) and
> `C_split` (S2 `arb_C` −0.0322, and `BASELINE_DRIFTED` false so no escape was
> available) **all failed ⇒ `¬PASS(C)`**. `DEPLOY` = true (`rho_wall(B*)` 1.191 ≤
> 1.20). ⇒ `p` true, `q = PASS(C) ∧ DEPLOY` false ⇒ **(T,F) ⇒ `A-COSTLY`**.
> Licenses exactly one Stage-2 game-cell prereg that **must solve cost on its own
> terms and may not assume the B\*=2 arm**, and which must carry arm `C`'s **NO
> CORROBORATION** sign-check verdict verbatim.
> **THIS READ-RULE IS SPENT; the 1,350-position corpus is BURNED; any successor
> design needs a fresh one of each.**

> **STATUS AT WRITING: COMMITTED BEFORE ANY ARBITRATION, HEADROOM OR PRICING
> NUMBER EXISTS ANYWHERE ON THE SUCCESSOR CORPUS** — before the instrument
> (`scripts/tiletie/analyze_tiearb2.py`), before the cost pilot, before one
> position of the fresh corpus is scored by either judge. `READOUT.md`,
> `READOUT.json`, `PILOT.json`, `SPLIT.json` and `DISJOINTNESS.json` do not exist
> at the time of this commit. Only corpus substrate precedes it (850 fresh
> self-play games + the mining that turns them into roots), which the funding
> brief permits, restricted to selection metadata. Git history proves the ordering
> and every run manifest carries this commit's hash. Definitions (corpus, slices,
> arms, judges, CRN convention, the cross-fit, `arb`/`ora`, the selection budget
> `B`, the `scale_all` zero add-back, the ×1.40 full-set extrapolation, the ÷3.2
> elo chain) are frozen here by reference to [DESIGN.md](DESIGN.md) §4–§9 and to
> [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md) §4.

**This read-rule is fully mechanical.** Every branch is a boolean function of
numbers the analyser emits. **No owner call adjudicates any outcome.** It is spent
on this mechanism and this corpus; any successor design needs a fresh one.

---

## 1. Scope

- **Main read: the FRESH 1,400-target tile-tie corpus** — 100% `walled` champion
  self-play mined from 850 games in deck-seed band 28100000000..28100000849,
  **root-disjoint, rid-disjoint and position-digest-disjoint** from the spent
  733-position corpus (DESIGN §4.4, `G-DISJOINT`, a pre-launch abort).
- **The branch input is the POOLED read.** Unlike Stage 1 this is not a deviation:
  DESIGN §6 sizes the corpus so the pooled read **resolves the bar it is graded
  at** (2σ = 0.302 in `F_fixed` units at n = 1,400 against a 0.35 bar).
- The **stratified symmetric half-split** `S1`/`S2` (DESIGN §5.4) enters as the
  consistency conjunct `C_split`, with an **informativeness guard** and a
  **baseline-drift gate input**. It is not a dev/holdout carve: on a fresh corpus
  with a zero-free-parameter estimator both halves are equally blind.
- **Two arbiter arms are adjudicated**: `H` (honest, selection budget `B = 16`) and
  `C` (cheap, `B = B*`, fixed by the cost-only rule of DESIGN §7.2 and written to
  `PILOT.json` before any fresh-corpus statistic exists).
- A partially-completed run is read at its realized `n` because the position order
  is a committed seeded permutation cut into 4 sequential chunks, so every
  completed-chunk prefix is a uniform random subsample (DESIGN §10).
- **0 strength games on every branch.** The 850 self-play games are corpus
  substrate. No `experiments/results.csv` row, no band, no
  `governance/BAND_REGISTRY.csv` entry, no claim id,
  `governance/PRODUCTION.yaml` untouched — regardless of outcome.

## 2. The committed quantities

All computed by `scripts/tiletie/analyze_tiearb2.py`, reusing `analyze_tiletie.py`'s
`parity_indices`, `crossfit_regret`, `cluster_robust`, `bootstrap_roots`,
`zero_rates`, `aggregate` and `pts_to_elo`, and `analyze_tiearb.py`'s
`paired_ratio_bootstrap`, `rnd_arm_position`, `sign_check` and `binom_two_sided`,
**unmodified**. `IF` = `clair-puct`; `ARB` = `tier1-greedy`.

| symbol | definition |
|---|---|
| `B` | the **selection budget** — how many CRN worlds the arbitration argmax sees. For a fold whose selection half is `sel` (16 ascending indices), the budget-`B` arbiter selects on `sel[:B]` and is priced on the **full 16-world evaluation half**. Prefix-stable seeds make every `B` a sub-read of the same records (DESIGN §5.2) |
| `H` / `C` | the **honest** arm (`B = 16`) and the **cheap** arm (`B = B*`) |
| `arb_x[p]` | DESIGN §5.1 — arm selected by the ARB judge's argmax on the selection worlds at budget `B(x)`, priced as `mean_eva V^IF[a_arb] − mean_eva V^IF[champ]` on the **disjoint** evaluation half, symmetrized over both parity folds, scaled by `scale_all` [pts/tied tile ply] |
| `ora[p]` | the identical statistic with the arm selected by the **IF** judge's own selection-half argmax — the headroom, symmetrized. **One `ora` for both arms** |
| `rnd[p]` | the random-arm arbiter, `a_rnd` drawn by `Random(sha256(rid) ⊕ 20260816)` over `arm_order`, priced identically — the null level |
| **`arb_x`**, **`ora`**, **`rnd`** | `mean_p` of the above over the pooled analysed positions |
| `se_x` | cluster-robust se on `root_id` (`analyze_tiletie.cluster_robust`, `G/(G−1)` corrected); **`z_x = arb_x / se_x`** |
| **`F(x)`** | **`arb_x / ora`** — the PRIMARY captured fraction. Both terms under the **same judge**, same positions, same scaling, same champion baseline, same evaluation worlds. 95% CI from a **root** bootstrap, 20,000 reps, seed **20260816**, recomputing numerator *and* denominator inside each rep |
| **`F_fixed(x)`** | **`arb_x / 0.2803`** — the cross-programme currency. `0.2803` is the fixed published honest base-rung regret both `E-FLAT` and `W-FLAT` were graded against. CI = the root bootstrap of `arb_x` ÷ 0.2803 |
| `G-BOOT(x)` | fraction of bootstrap reps with `ora ≤ 0`; **fires if > 0.05** |
| `arb_s(x)`, `ora_s`, `rnd_s` | the same means restricted to slice `s ∈ {S1, S2}` |
| **`rho_wall(B)`** | `Ā × B × c_tier1 / 13.7552` — DESIGN §7.1. `Ā` = realized mean arm count; `c_tier1` = the pilot's measured worker-s/playout; `13.7552` = the champion at k8×1376 sequential on this box (PRODUCTION.yaml) |
| **`B*`** | `max { B ∈ {1,2,4,8,16} : rho_wall(B) ≤ 1.20 }`, else `1`. **Frozen in `PILOT.json` from cost alone, before any fresh-corpus statistic** |

**The bars are `0.35` (ratio), `+2.0` (z) and `1.20` (cost).** The first two are
**not new constants** — they are `E-FLAT`'s and `W-FLAT`'s own committed fund bar
verbatim ("*ratio ≥ 0.35 ∧ z ≥ +2 ∧ coverage ≥ 0.85*") and Stage 1's. The third is
the house **N4 trigger currency**, applied at tied plies as the funding brief
specifies. Coverage is not a conjunct: the arbiter selects only from the scored arm
set, so its coverage is 1.0 by construction — reported as a witness.

## 3. Preconditions — checked FIRST, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of:**

| id | condition |
|---|---|
| `G-CRN` | any scored ARB record has `crn_verified != true`, `checksum_ok != true`, or `world_seeds`/`playout_seeds` not **bit-identical** to the `clair-puct` record for the same `rid` |
| `G-ARM` | any record's `pick_a`/`pick_b` disagrees with `ARMS.json` for its leg, in either judge |
| `G-VA` | `values_a` not bit-identical across all legs of a position, within either judge |
| `G-ARMSET` | the two judges' scored `arm_order` differ on **more than 5%** of analysed positions (differing positions are excluded and counted in every case; denominator = analysed + armset-mismatched) |
| `G-SPLIT` | `S1 ∪ S2` is not the analysed corpus, or `S1 ∩ S2 ≠ ∅` at the **root** level, or any of the 18 stratification cells is off-balance by more than 1 root |
| `G-N` | fewer than **1,040** analysed positions pooled, **or** fewer than **400** in either slice |
| `G-DENOM` | `ora ≤ 0`, or `z(ora) < +2.0`, on the pooled read — **there is no headroom to capture and `F` has no meaningful denominator** |

(`G-DISJOINT`, `G-LEAF`, `G-REPRO` and `G-GEN` are **pre-launch aborts**, DESIGN
§9: if any fails the fresh corpus is never scored and the read-out is a harness
report.)

`U-UNREADABLE` = report cost, integrity, and whichever gate failed. **Nothing
closes, nothing is licensed, nothing is re-labelled.**

## 4. Branches

Let, for each arm `x ∈ {H, C}`:

```
C_z(x)   ≡  z_x ≥ +2.0
RBAR(x)  ≡  (F_fixed(x) ≥ 0.35)  ∧  ( (F(x) ≥ 0.35)  ∨  G-BOOT(x) fired )
ANY_R(x) ≡  (F_fixed(x) ≥ 0.35)  ∨  ( (F(x) ≥ 0.35)  ∧  ¬G-BOOT(x) )

INFORMATIVE(s)    ≡  z(ora_s) ≥ +2.0
BASELINE_DRIFTED  ≡  |rnd_S1 − rnd_S2| ≥ 0.20

C_split(x) ≡  ( at least one slice is INFORMATIVE )
              ∧  ∀ slices s with INFORMATIVE(s):
                     arb_s(x) ≥ 0
                     ∨ ( BASELINE_DRIFTED ∧ (arb_s(x) − rnd_s) ≥ 0 )

PASS(x)  ≡  C_z(x) ∧ RBAR(x) ∧ C_split(x)
DEPLOY   ≡  rho_wall(B*) ≤ 1.20
```

- `G-BOOT(x)` fired ⇒ `F(x)`'s percentile interval is bimodal and `F(x)` is **void
  as a branch input**; the ratio conjunct then rests on `F_fixed(x)` alone and the
  read-out says so in the branch sentence.
- `C_split` is keyed on the slice **numerators**, never on a slice `F`, so a noisy
  slice denominator cannot flip a conjunct.
- **A slice that is not INFORMATIVE reads UNINFORMATIVE, never FAIL** — it has no
  resolved headroom to capture, so a null on it is not evidence. ⚠️ The guard is
  **not free**: `C_split` requires at least one INFORMATIVE slice, so a corpus in
  which nothing is resolvable cannot satisfy it.
- The `BASELINE_DRIFTED` escape clause opens **only** when the random-arm baseline
  demonstrably moved between the slices. The read-out **must state explicitly**
  whether it was used, and for which slice and arm.

| # | condition | read |
|---|---|---|
| **`A-DEPLOYABLE`** | `PASS(H)` **∧** `PASS(C)` **∧** `DEPLOY` | **TERMINAL-GROUNDED TIE ARBITRATION CAPTURES THE HEADROOM, AND IT DOES SO AT A DEPLOYABLE COST.** On a corpus no programme has ever touched, root-disjoint from the spent one and powered to resolve the bar, an arm chosen by CRN-paired greedy playouts to terminal — on worlds disjoint from the ones it is priced on — is worth **≥ 35% of the oracle headroom** at the identical bar and in the identical currency that `E-FLAT` (0.00/0.18/0.18) and `W-FLAT` (0.11/0.26/0.09/0.09/0.30) failed; it convicts at 2σ; **both** stratified half-slices agree; **and the same holds at a selection budget `B*` whose measured per-tied-ply cost is ≤ 1.20× the champion's per-move budget.** **Licenses (does NOT fund) exactly one thing: a fresh Stage-2 pre-registration of a deck-paired GAME cell testing the budget-matched arbiter — and that prereg MAY use the `B*` cheap arm as its deployable form.** The prereg must (a) carry a **matched-wall-clock control arm**; (b) carry DESIGN §12.1 verbatim (*both judges are terminal-grounded, so this is not yet a deploy-elo claim*); (c) carry the §5.6 sign-check verdict verbatim if it reads **NO CORROBORATION**; (d) re-derive cost against a **rust** continuation rather than inheriting `rho_wall`'s python upper bound. ⛔ It does **not** license a game outside that prereg, a band, a deploy, a `PRODUCTION.yaml` change, a leaf term (CL-065 + two dead menus + the 38% reach bound stand), or a claim id. |
| **`A-COSTLY`** | `PASS(H)` **∧** `¬( PASS(C) ∧ DEPLOY )` | **THE MECHANISM CAPTURES, BUT NO DEPLOYABLE SHAPE OF IT HAS BEEN DEMONSTRATED.** The honest arm clears every conjunct on a fresh, powered, root-disjoint corpus — the strongest reading this axis has ever produced — but the budget-legal arm does not (or no budget in the ladder is legal). **Licenses (does NOT fund) exactly one thing: a fresh Stage-2 pre-registration of a deck-paired GAME cell**, which **MUST solve cost on its own terms and MAY NOT assume the `B*` arm**: DESIGN §7.2 measures the honest shape at ~7–9× the champion's per-move budget, so a Stage-2 that does not solve cost is not fundable. Conditions (a)–(d) of `A-DEPLOYABLE` apply verbatim. The read-out must print the full B-ladder so the cost/capture crossing is visible. |
| **`B-ANOMALY`** | `¬PASS(H)` **∧** `PASS(C)` **∧** `DEPLOY` | **ORDERING ANOMALY — REPORTED, AND IT LICENSES NOTHING.** The cheap arm's selection worlds are a strict **subset** of the honest arm's, so the cheap arm cannot be better in expectation; a read in which it passes where the honest arm fails is a noise signature, not a finding. Report both arms in full, the B-ladder, `AGREE_HC`, and the difference `arb_H − arb_C` with its paired cluster-robust se. **Nothing closes and nothing is licensed.** |
| **`P-PARTIAL2`** | `¬PASS(H)` **∧** `¬( PASS(C) ∧ DEPLOY )` **∧** `( ANY_R(H) ∨ ANY_R(C) )` | **PRESENT AT THE MECHANISM BAR BUT NOT CONVICTED — UNRESOLVED.** At least one ratio reading clears 0.35 but the conjunction fails (the `z` bar, or the two ratio readings straddle, or a slice disagrees). **Nothing closes and nothing is licensed** — in particular this does **not** close the mechanism and does **not** fund a Stage-2. Report, for **both** arms: `arb`, `se`, `z`, `F` with CI, `F_fixed` with CI, both slice reads with their `ora` z and their `rnd`, **exactly which conjunct failed**, whether the `BASELINE_DRIFTED` clause was available and used, and the `n` that would resolve `F_fixed` to ±0.35 at the realized dispersion. |
| **`F-FLAT2`** | `¬PASS(H)` **∧** `¬( PASS(C) ∧ DEPLOY )` **∧** `¬ANY_R(H)` **∧** `¬ANY_R(C)` | **THE MECHANISM DID NOT FIRE AT A MECHANISM-SIZED BAR ON A FRESH, POWERED, ROOT-DISJOINT CORPUS.** Neither arm's ratio reading reaches 0.35 and neither mean is convicted. ⚠️ **The mandatory scope sentence, quoted with the verdict and never separated from it:** *"This is a FUNDING verdict, not an exclusion — the same scope `W-FLAT` and Stage 1's `F-FLAT` carried. DESIGN §6 states before the run that this design resolves `F_fixed` to ±0.30 at 2σ, so a capture below ~0.30 is NOT excluded by this null; the honest claim is 'terminal-grounded tie arbitration did not fire at a mechanism-sized bar on a fresh 1,400-position corpus', NOT 'terminal grounding is worth nothing'."* **Rider, mandatory when it applies:** if `F_fixed_hi(H) < 0.35`, the read-out must **additionally** state that a 35% capture *is* excluded at 95% and the scope sentence is superseded in that one respect. ⚠️ **Second rider, mandatory always on this branch:** Stage 1 read `F_fixed = 0.737` (z +3.75) on the spent corpus, so an `F-FLAT2` is a **direct contradiction of a published result** and must be reported as such — the read-out must print the Stage-1 value beside this one, the difference with its se, and must NOT present the contradiction as resolved. **Operative statement of the tile-tie axis** to be recorded on this branch: *neither static afterstate functions, nor deeper same-shape search, nor wider determinization, nor terminal-grounded arbitration expresses the +0.252 pts/ply on a fresh corpus — while the out-of-family re-pricing says the headroom is real. The axis has no remaining named mechanism.* |
| **`U-UNREADABLE`** | any §3 precondition fails | §3. |

### 4.1 Exclusivity and exhaustiveness — verified in the pre-registration text

Per the pricing DESIGN's §4.4-A rider (*"Any successor design that edits this table
must re-verify that property in the prereg text itself"*):

- §3 is evaluated **first** and `U-UNREADABLE` pre-empts everything, so the
  remaining five are evaluated only on the complement of §3.
- Let `p ≡ PASS(H)` and `q ≡ ( PASS(C) ∧ DEPLOY )`. The five branches partition the
  `(p, q)` grid **exactly**:

  | `p` | `q` | branch |
  |---|---|---|
  | T | T | `A-DEPLOYABLE` |
  | T | F | `A-COSTLY` |
  | F | T | `B-ANOMALY` |
  | F | F | `P-PARTIAL2` if `ANY_R(H) ∨ ANY_R(C)`, else `F-FLAT2` |

  `A-DEPLOYABLE` requires `p ∧ q`; `A-COSTLY` requires `p ∧ ¬q`; `B-ANOMALY`
  requires `¬p ∧ q`; both `P-PARTIAL2` and `F-FLAT2` require `¬p ∧ ¬q`. The four
  cells are mutually exclusive and cover the grid.
- Within the `(F, F)` cell, `P-PARTIAL2` requires `ANY_R(H) ∨ ANY_R(C)` and
  `F-FLAT2` requires its exact negation ⇒ they are disjoint and exhaust the cell.
- ⇒ **exactly one branch matches every possible read, and the match does not depend
  on the ordering.** Precedence is presentation, not semantics.
- `RBAR(x) ⇒ ANY_R(x)` (proof: `RBAR(x)` contains the conjunct `F_fixed(x) ≥ 0.35`,
  which is the first disjunct of `ANY_R(x)`), so no read can satisfy a passing
  branch's ratio conjunct while `F-FLAT2`'s negation would also have matched.
- This is verified by a machine sweep over the branch-condition truth table in
  `tests/test_tiearb2.py`, which re-transcribes this section **independently of the
  implementation** and asserts exactly one branch fires on every cell, including
  `NaN` in every position.

### 4.2 Mandatory on every branch — the full companion table

The read-out MUST print:

1. For **both arms** and for **pooled / `S1` / `S2`**: `arb`, `se`, `z`, bootstrap
   CI; `ora`, `se`, `z`; `F` with CI and `G-BOOT`'s rate; `F_fixed` with CI — in
   **both** the `all` (`scale_all`) and the `discriminable` scalings.
2. The **single-fold `parity_base=1`** readings beside the symmetrized ones (the
   `I1` diagnostic).
3. **`C-RND` per slice and pooled**, and **`arb − rnd`** for both arms; `D_rnd` and
   whether `BASELINE_DRIFTED` fired; **which slices were INFORMATIVE**, with their
   `z(ora_s)`; and **explicitly whether the escape clause was used**.
4. **`C-ARM0`**; **`SEC-ARB`** in pts with its `z`, labelled ⚠️ **AUDIT-ONLY,
   CIRCULAR: its capture fraction against its own headroom is 1 by construction**,
   and never a branch input.
5. **The full B-ladder** — `arb`, `z`, `F`, `F_fixed`, `rho_wall`, `rho_amortized`
   and `rho_phone` at `B ∈ {1,2,4,8,16}` — **labelled a reported ladder, never a
   branch input except at `B = 16` and `B = B*`**; plus `B*`, `Ā`, `c_tier1` and
   the `PILOT.json` commit that froze them.
6. **`PICKCHG`** (`a_arb ≠ champ`; `a_arb = a_ora`), coverage as a witness, and
   **`AGREE_HC`** (honest/cheap arm selection agreement).
7. The §5.6 **sign check** — `agreement_rate`, exact two-sided binomial `p`,
   aggregate sign, verdict — printed beside the E4 autopsy's committed benchmarks
   (80% at p 0.0012 = corroboration; 61.9% at p 0.38 = NOT) and beside the
   autopsy's own Tier-1 result (62.1% at p 2.8e-05, aggregate sign NEGATIVE ⇒
   PARTIAL). **Never a branch input.**
8. The **bound chain** in pts and elo with the ÷3.2 / ÷5.23 bracket and the
   `σ_game` sensitivity, every caveat inherited verbatim (`NON_ADDITIVITY = 3.2` is
   **n = 1**, a ±1.6× bracket, not a point).
9. Realized `n`, roots, positions-per-root, and the phase / arm-count / capped
   composition **per slice**, plus the fraction of the planned corpus that finished
   and the 18-cell balance witness.
10. **Every §3 gate and every DESIGN §9 integrity counter with its realized value**,
    including `G-DISJOINT`'s three intersection counts and `G-REPRO`'s count.
11. `c_tier1` realized on the main run, the realized **2σ resolution** of `arb_H` in
    pts and elo, the `n` that would resolve `F_fixed` to ±0.35, and any co-tenant
    found by the process census.
12. Per-phase, per-arm-count and capped/uncapped cuts, **labelled underpowered. No
    branch is ever adjudicated on a cut.**
13. **A direct comparison to Stage 1** — `arb_H` here vs `+0.2065` there, `F_fixed`
    here vs `0.737` there, with the se of the difference — labelled a
    **cross-corpus** contrast and therefore subject to the CLAUDE.md cross-band
    ~1.5–2× humility rule. **Never a branch input.**

## 5. What no branch does

- No branch plays a strength game, claims a band, writes `experiments/results.csv`,
  writes `governance/BAND_REGISTRY.csv`, or edits `governance/PRODUCTION.yaml`.
- No branch mints a claim id.
- No branch changes the production leaf, adds a leaf term, or trains anything.
- No branch re-reads, re-labels or re-adjudicates the finished 2026-08-12 pricing,
  2026-08-14 term / mining / escalation / kwidth / out-of-family, or 2026-08-16
  Stage-1 runs. They stand as adjudicated. The §4.2(13) comparison is a
  **replication reported beside them**, not a re-adjudication of any of them.
- No branch licenses a second evaluation of anything in this directory. **This
  read-rule is spent when the read-out lands.**
