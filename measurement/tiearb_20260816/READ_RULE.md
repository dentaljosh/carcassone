# TERMINAL-GROUNDED TIE ARBITRATION — READ-RULE (Stage 1, offline)

> **STATUS AT WRITING: COMMITTED BEFORE ANY ARBITRATION NUMBER EXISTS ANYWHERE —
> before the instrument, before the cost pilot, before one holdout position is
> scored.** `READOUT.md`, `READOUT.json` and `PILOT.json` do not exist at the
> time of this commit; neither `scripts/tiletie/build_tiearb_plan.py` nor
> `scripts/tiletie/analyze_tiearb.py` exists yet. Git history proves the
> ordering and the run manifest carries this commit's hash. Definitions (corpus,
> slices, arms, judges, CRN convention, the cross-fit, `arb` / `ora`, the
> `scale_all` zero add-back, the ×1.40 full-set extrapolation, the ÷3.2 elo
> chain) are frozen here by reference to [DESIGN.md](DESIGN.md) §2–§6 and to
> [../tiletie_pricing_20260812/DESIGN.md](../tiletie_pricing_20260812/DESIGN.md) §4.

**This read-rule is fully mechanical.** Every branch is a boolean function of
numbers the analyser emits. **No owner call adjudicates any outcome.** It is
spent on this mechanism and this corpus; any successor design needs a fresh one.

---

## 1. Scope

- **Main read: the POOLED 733-position / 399-root tile-tie pricing corpus** —
  the 522-position DEV slice (both judges' records already on disk) **plus** the
  211-position HOLDOUT slice (`../tiletie_mining_20260814/HOLDOUT_ROOTS.json`,
  120 roots), whose `tier1-greedy` records this run produces.
  A partially-completed holdout run is read at its realized `n` because the
  holdout order is a committed seeded permutation cut into 4 sequential chunks,
  so every completed-chunk prefix is a uniform random subsample (DESIGN §5).
- ⚠️ **THE HOLDOUT IS SPENT BY THIS RUN, on every branch.** It is burned and is
  no longer an unburned reserve. Recorded in `docs/LEVER_INDEX.md` and DECISIONS
  regardless of outcome.
- ⚠️ **The branch input is the POOLED read, not the holdout alone** — DESIGN §4.4's
  power arithmetic shows n = 211 cannot convict even a 100% capture. The holdout
  enters `A-CAPTURE` as the blind sign-consistency conjunct `C_h`. This is a
  **declared deviation from the funding brief**, licensed by the brief's own
  instruction to say so in the DESIGN if the holdout is too small.
- **0 games on every branch.** No `experiments/results.csv` row, no band, no
  `governance/BAND_REGISTRY.csv` entry, no claim id, `governance/PRODUCTION.yaml`
  untouched — regardless of outcome.

## 2. The committed quantities

All computed by `scripts/tiletie/analyze_tiearb.py`, reusing
`scripts/tiletie/analyze_tiletie.py`'s `parity_indices`, `crossfit_regret`,
`cluster_robust`, `bootstrap_roots`, `zero_rates` and `pts_to_elo` **unmodified**.
`IF` = `clair-puct` (the pricing records); `ARB` = `tier1-greedy`.

| symbol | definition |
|---|---|
| `arb[p]` | DESIGN §4.1 — arm selected by **argmax of the ARB judge's world-mean on the SELECTION half**, priced as `mean_eva V^IF[a_arb] − mean_eva V^IF[champ]` on the **disjoint EVALUATION half**, symmetrized over both parity folds, scaled by the stratum's `scale_all` [pts/tied tile ply] |
| `ora[p]` | the identical statistic with the arm selected by the **IF** judge's own selection-half argmax — i.e. `analyze_tiletie`'s `headroom_champ`, symmetrized [pts/tied tile ply] |
| **`arb`**, **`ora`** | `mean_p` of the above over the **pooled** analysed positions |
| `se_arb` | cluster-robust se on `root_id` (`analyze_tiletie.cluster_robust`); **`z_arb = arb / se_arb`** |
| **`F`** | **`arb / ora`** — the PRIMARY captured fraction. Both judges' terms under the **same judge (`clair-puct`)**, same positions, same scaling, same champion baseline, same evaluation worlds. 95% CI `[F_lo, F_hi]` from a **root** bootstrap, 20,000 reps, seed **20260816**, recomputing numerator *and* denominator inside each rep |
| **`F_fixed`** | **`arb / 0.2803`** — the cross-programme currency. `0.2803` is the fixed, published *honest base-rung regret* both `E-FLAT` and `W-FLAT` were graded against ([LADDER_READOUT](../tieescalation_20260814/LADDER_READOUT.md)). CI = the root bootstrap of `arb` divided by `0.2803` |
| `arb_holdout` | `mean_p arb[p]` over the **HOLDOUT positions only** |
| `G-BOOT` | fraction of bootstrap reps with `ora ≤ 0`; **fires if > 0.05** |

**The bar is `0.35`** — it is **not a new constant**. It is the capture-ratio bar
`E-FLAT` and `W-FLAT` were both adjudicated against, verbatim
(*"against the committed fund bar (ratio ≥ 0.35 ∧ z ≥ +2 ∧ coverage ≥ 0.85)"*),
so this run's capture is decided at the identical bar in the identical currency
as the two kills it is the successor to. **The `z` bar is `+2.0`**, likewise
theirs. (Coverage is not a conjunct here: the arbiter selects only from the
scored arm set, so its coverage is 1.0 by construction — reported as a witness.)

## 3. Preconditions — checked FIRST, and they void the run

**`U-UNREADABLE` fires, and no other branch may fire, if ANY of:**

| id | condition |
|---|---|
| `G-CRN` | any scored ARB record has `crn_verified != true`, `checksum_ok != true`, or `world_seeds`/`playout_seeds` not **bit-identical** to the `clair-puct` record for the same `rid` |
| `G-ARM` | any record's `pick_a`/`pick_b` disagrees with `ARMS.json` for its leg, in either judge |
| `G-VA` | `values_a` not bit-identical across all legs of a position, within either judge |
| `G-SLICE` | any ARB holdout-leg `root_id` is absent from `HOLDOUT_ROOTS.json`; or any holdout root appears in the DEV leg; or the two legs are not disjoint |
| `G-ARMSET` | the two judges' scored `arm_order` differ on **more than 5%** of analysed positions (positions that differ are excluded and counted in every case) |
| `G-N` | fewer than **650** of 733 pooled positions analysed, **or** fewer than **158** of 211 holdout positions (3 of 4 chunks) |
| `G-DENOM` | `ora ≤ 0`, or `z(ora) < +2.0`, on the pooled read — **there is no headroom to capture and `F` has no meaningful denominator** |

(`G-LEAF` — `run_tiletie` preflight leaf hash `a36d2e15a3b3d71d` — and `G-REPRO`
— the 43/43 bit-reproduction of the OOF pilot records, DESIGN §5 — are
**pre-launch aborts**: if either fails the holdout is never launched and stays
unburned, and the read-out is a harness report.)

`U-UNREADABLE` = report cost, integrity, and whichever gate failed. **Nothing
closes, nothing is licensed, nothing is re-labelled.**

## 4. Branches

Let

```
C_z    ≡  z_arb ≥ +2.0
RBAR   ≡  (F_fixed ≥ 0.35)  ∧  ( (F ≥ 0.35)  ∨  G-BOOT fired )
ANY_R  ≡  (F_fixed ≥ 0.35)  ∨  ( (F ≥ 0.35)  ∧  ¬G-BOOT )
C_h    ≡  arb_holdout ≥ 0.0
```

(`G-BOOT` fired ⇒ `F`'s percentile interval is bimodal and `F` is **void as a
branch input**; the ratio conjunct then rests on `F_fixed` alone and the read-out
says so in the branch sentence. `C_h` is keyed on the holdout **numerator**, not
on `F_holdout`, so a noisy holdout denominator cannot flip the sign of a conjunct.)

| # | condition | read |
|---|---|---|
| **`A-CAPTURE`** | `C_z` **∧** `RBAR` **∧** `C_h` | **TERMINAL-GROUNDED TIE ARBITRATION CAPTURES THE HEADROOM.** An arm chosen by CRN-paired greedy playouts to terminal, on worlds disjoint from the ones it is priced on, is worth **≥ 35% of the oracle headroom** at the identical bar and in the identical currency that `E-FLAT` (0.00/0.18/0.18) and `W-FLAT` (0.11/0.26/0.09/0.09/0.30) failed — and it convicts at 2σ, with the never-before-opened holdout not pointing the other way. **Licenses (does NOT fund) exactly one thing: a fresh Stage-2 pre-registration of a deck-paired GAME cell testing a BUDGET-MATCHED deployable form of the arbiter.** That prereg must (a) name and price the budget-matched form — DESIGN §2.3 measures the honest shape at **100–200× the champion's per-move budget**, so a Stage-2 that does not solve cost is not fundable; (b) carry a **matched-wall-clock control arm**; (c) carry DESIGN §7.1 verbatim (*both judges are terminal-grounded, so this is not yet a deploy-elo claim*); (d) if the §4.5 sign check reads **NO CORROBORATION**, carry that verdict verbatim. ⛔ It does **not** license a game outside that prereg, a band, a deploy, a `PRODUCTION.yaml` change, a leaf term (CL-065 + two dead menus + the 38% reach bound stand), or a claim id. |
| **`P-PARTIAL`** | `¬A-CAPTURE` **∧** `ANY_R` | **PRESENT AT THE MECHANISM BAR BUT NOT CONVICTED — UNRESOLVED.** At least one ratio reading clears 0.35 but the conjunction fails (the `z` bar, or the two ratio readings straddle, or the blind holdout leans negative). **Nothing closes and nothing is licensed** — in particular this does **not** close the mechanism and does **not** fund a Stage-2. Report `arb`, `se_arb`, `z_arb`, `F` with CI, `F_fixed` with CI, `arb_holdout`, **exactly which conjunct failed**, and the `n` that would resolve `F_fixed` to ±0.35 (DESIGN §4.4 projects **≈ 2,200** positions against a total deduped supply of **733**). |
| **`F-FLAT`** | `¬A-CAPTURE` **∧** `¬ANY_R` | **THE MECHANISM DID NOT FIRE AT A MECHANISM-SIZED BAR ON 733 POSITIONS.** Neither ratio reading reaches 0.35 and the mean is not convicted. ⚠️ **The mandatory scope sentence, quoted with the verdict and never separated from it:** *"This is a FUNDING verdict, not an exclusion — the same scope `W-FLAT` carried. DESIGN §4.4 states before the run that this design resolves `F_fixed` only to ±0.46–0.81 at 2σ, so a capture in the 0.18–0.30 band E-FLAT and W-FLAT saw is NOT excluded by this null; the honest claim is 'terminal-grounded tie arbitration did not fire at a mechanism-sized bar on the whole 733-position corpus', NOT 'terminal grounding is worth nothing'."* **Rider, mandatory when it applies:** if `F_fixed_hi < 0.35`, the read-out must **additionally** state that half-capture *is* excluded at 95% and the scope sentence above is superseded in that one respect. **Operative statement of the tile-tie axis** to be recorded on this branch: *neither static afterstate functions, nor deeper same-shape search, nor wider determinization, nor terminal-grounded arbitration at the tied ply expresses the +0.252 pts/ply — while the out-of-family re-pricing says the headroom is real. The axis has no remaining named mechanism.* |
| **`U-UNREADABLE`** | any §3 precondition fails | §3. |

### 4.1 Exclusivity and exhaustiveness — verified in the pre-registration text

Per the pricing DESIGN's §4.4-A rider (*"Any successor design that edits this
table must re-verify that property in the prereg text itself"*):

- §3 is evaluated **first** and `U-UNREADABLE` pre-empts everything, so the
  remaining three are evaluated only on the complement of §3.
- `A-CAPTURE` requires `C_z ∧ RBAR ∧ C_h`; both `P-PARTIAL` and `F-FLAT` require
  `¬A-CAPTURE`. ⇒ `A-CAPTURE` is disjoint from both.
- `P-PARTIAL` requires `ANY_R`; `F-FLAT` requires `¬ANY_R`. `ANY_R` and `¬ANY_R`
  are exact complements by construction. ⇒ they are disjoint.
- Their union is `¬A-CAPTURE`, so together with `A-CAPTURE` they exhaust the
  complement of §3.
- `RBAR ⇒ ANY_R` (proof: `RBAR` contains the conjunct `F_fixed ≥ 0.35`, which is
  the first disjunct of `ANY_R`), so no read can satisfy `A-CAPTURE`'s ratio
  conjunct while `F-FLAT`'s negation would also have matched.

⇒ **exactly one branch matches every possible read, and the match does not depend
on the ordering.** Precedence is presentation, not semantics. This is verified by
a machine sweep over the branch-condition truth table in `tests/test_tiearb.py`.

### 4.2 Mandatory on every branch — the full companion table

The read-out MUST print:

1. `arb`, `se_arb`, `z_arb`, bootstrap CI; `ora`, `se`, `z`; `F` with CI and
   `G-BOOT`'s rate; `F_fixed` with CI — in **both** the `all` (`scale_all`) and
   the `discriminable` scalings, and for **pooled / DEV / HOLDOUT** separately.
2. The **single-fold `parity_base=1`** readings of `arb` and `ora` beside the
   symmetrized ones (the `I1` diagnostic).
3. **`C-RND`** (random-arm arbiter) and **`arb − rnd`**; **`C-ARM0`** (arm-0
   comparator); **`SEC-ARB`** — the arbiter's picks priced by `tier1-greedy`
   itself, in pts with its `z`, labelled ⚠️ **AUDIT-ONLY, CIRCULAR: its capture
   fraction against its own headroom is 1 by construction**, and never a branch
   input.
4. **`R_holdout = H_ARB/H_IF` on the holdout** and **`H_IF_holdout` with its `z`**
   — the free out-of-sample replication of `C-CONFIRM` and of the +0.252. Reported;
   adjudicates nothing (the OOF read-rule is spent).
5. **`PICKCHG`**: the fraction of positions where `a_arb ≠ champ`, and where
   `a_arb = a_ora`; plus coverage (= 1.0 by construction, as a witness).
6. The §4.5 **sign check** — `agreement_rate`, exact two-sided binomial `p`,
   aggregate sign, and the verdict string CORROBORATES / PARTIAL / NO
   CORROBORATION — printed beside the E4 autopsy's committed benchmarks (**80% at
   p 0.0012 = corroboration; 61.9% at p 0.38 = NOT**) and beside the autopsy's own
   Tier-1 result (**62.1% at p 2.8e-05, aggregate sign NEGATIVE ⇒ PARTIAL**), so
   ours is calibrated against a known non-corroboration. **Never a branch input.**
7. The §4.3 **bound chain** in pts and elo with the ÷3.2 / ÷5.23 bracket and the
   σ_game sensitivity, every caveat inherited verbatim
   (`NON_ADDITIVITY = 3.2` is **n = 1**, a ±1.6× bracket, not a point).
8. Realized `n`, roots, and the phase / profile / stratum / capped composition of
   what completed, per slice, and the fraction of the planned 211 holdout
   positions that finished.
9. `c_tier1` (worker-s/playout) realized on the holdout run, and any co-tenant
   found by the process census.
10. **Every §3 gate and every DESIGN §6 integrity counter with its realized
    value**, including `G-REPRO`'s count.
11. The **realized 2σ resolution** of `arb` in pts and in elo, and the `n` that
    would resolve `F_fixed` to ±0.35.
12. Per-stratum (`e4`/`selfplay`), per-profile, per-phase and capped/uncapped
    cuts, **labelled underpowered. No branch is ever adjudicated on a cut.**

## 5. What no branch does

- No branch plays a game, claims a band, writes `experiments/results.csv`, writes
  `governance/BAND_REGISTRY.csv`, or edits `governance/PRODUCTION.yaml`.
- No branch mints a claim id. (An `F-FLAT` is a mechanism closure recorded in
  `docs/LEVER_INDEX.md` + DECISIONS; minting a claim from it is a separate owner
  decision, not this read-rule's to take.)
- No branch changes the production leaf, adds a leaf term, or trains anything.
- No branch re-reads, re-labels or re-adjudicates the finished 2026-08-12
  pricing, 2026-08-14 term / mining / escalation / kwidth, or 2026-08-14
  out-of-family runs. They stand as adjudicated. The `R_holdout` companion is a
  **replication reported beside them**, not a re-adjudication of any of them.
- No branch licenses a second evaluation of anything in this directory. **This
  read-rule is spent when the read-out lands.**
