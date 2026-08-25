> ⛔→✅ **FROZEN 2026-08-24 (branch-freeze: the blind commit is THE COMMIT INTRODUCING THIS
> BANNER, on branch `h2h22k-freeze`, cut from `tiearb2-stage2`'s tip `ecbbc616` — local main
> is latched under a live `carcasum_arb_challenge` run; a committed sha is a provable freeze
> on any branch, same precedent as `carcasum-arb-freeze` / `d1-rebase-freeze`). Owner
> directive, verbatim: **"fund it"** 2026-08-24, after the menu discussion. No game on band
> `148000000000` exists at freeze time. **NOT LAUNCHED** — this is a build-only deliverable;
> the orchestrator fires it with its own monitors. `WORKERS.conf::BLIND_COMMIT` cannot be
> stamped with this commit's own sha inside this same commit — a small follow-up commit stamps
> the real sha (and `PINNED_SRC_REV`) before any real launch; `run_cells.sh` refuses a real
> (non-dry-run, non-smoke) launch while either reads `PENDING`.**

# READ_RULE — 22016 vs 11008 direct budget head-to-head

> **⚠️ BLIND ORDERING.** This file is committed BEFORE the band is claimed, BEFORE game 1, and
> BEFORE any statistic of this cell exists. The branch that fires is taken **VERBATIM**,
> whatever it is. Owner authorization funds the cell and does not name its answer — same
> discipline as `carcasum_arb_challenge_prep/READ_RULE.md` §0 and
> `track_d1_fair_rebase/READ_RULE.md` §0.
>
> Design: [`DESIGN.md`](DESIGN.md). Constants: [`WORKERS.conf`](WORKERS.conf). Launcher:
> [`run_cells.sh`](run_cells.sh). Band claim: [`BAND_CLAIM.json`](BAND_CLAIM.json).
> Adjudicator: [`adjudicate.py`](adjudicate.py) (built alongside this pair, §7).

---

## §0 — WHAT THIS CELL IS RE-TESTING, STATED BEFORE THE ANSWER

This cell **re-opens a CLOSED axis**: *"how much raw-search-budget headroom is left above
11008?"* — closed 2026-08-09 by the **budget-headroom decay bound**
(`docs/LEVER_INDEX.md` row *"budget-headroom decay bound · geometric extrapolation · how much
is left above 11008 · decay ratio r · `next-gain/(1−r)` · convergent-sum headroom"*;
[MEMO](../budget_headroom_bound_20260809/MEMO.md) §9). That row's closure reads, verbatim in
substance: **measured price ⇒ ≈ +7 elo, honest bracket ≈ [−35, +49] elo, SPANS ZERO** — and
its mechanism finding is that *"above 5504 the deeper pick MOVES but does not IMPROVE."*

It is re-opened by the **licensed route the closure itself names**: not more extrapolation,
but a **direct instrument that resolves well below the old bounds**. This cell's realized
2σ is **≈ ±1.11 pts ≈ ±19–21 elo** (§2) — roughly **half the half-width** of the closure's own
`[−35, +49]` bracket. That is the entire justification for spending 1,400 games on a question
already answered by desk arithmetic.

**Therefore, stated before any number exists:**

- **A NULL RATIFIES THE CLOSURE AT THE TIGHTER BOUND.** `H-NULL-BOUND` (§4) is not a failed
  experiment and not an inconclusive one. It is the licensed, *expected* outcome under the
  closure's own central estimate, and it replaces `[−35, +49]` with this cell's own realized
  2σ interval as the bound of record on headroom above 11008.
- **THIS CELL IS NOT POWERED TO SEE THE CLOSURE'S CENTRAL.** At the closure's own point
  estimate (+7.1 elo ≈ +0.41 pts) this instrument reads **z ≈ 0.7, power ≈ 11%** (§2.2). A
  null is what the closure predicts. Nobody may later read `H-NULL-BOUND` as "we looked hard
  and found nothing at +7 elo" — the honest statement is "we bounded it at ±20 elo."
- **A POSITIVE LICENSES NOTHING ABOUT DEPLOY.** `H-POSITIVE` says the doubling *pays in
  strength*. It costs **2× wall-clock per move** by construction. Whether that trade is worth
  making is an **owner affordability question**, not a measurement one, and this read rule
  does not answer it, recommend it, or pre-authorize it.

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

```
For each deck d in 148000000000..148000000699 that appears in BOTH seatings:

    D(d) = ( diff(d, a_seat=0) + diff(d, a_seat=1) ) / 2

  where diff is the harness's own final-score margin, CANDIDATE minus OPPONENT,
  i.e. F(k16x1376 = 22016) minus E(k8x1376 = 11008), in POINTS.

D      = mean( D(d) ) over n_common decks
SE(D)  = stdev( D(d) ) / sqrt(n_common)     -- decks are the i.i.d. unit; this is
                                               eval_fair_puct._paired_z's own
                                               per-deck seat-balanced construction
z_D    = D / SE(D)
```

**Sign convention, load-bearing:** `D > 0` means the **larger budget won** — one more doubling
above production still pays. `D < 0` means the larger budget **lost** — a real, reportable
finding (§4's `H-REVERSED`), not a gate failure.

**Cluster = deck.** Not game, not seat. The two seatings of one deck are the same random
draw played twice and are averaged into one observation before any variance is taken.

**Primary unit: POINTS of final-score margin per deck.** Elo is a **display quantity only** and
is **never a branch input** — the branch table in §4 is stated entirely in points and `z`.

⚠️ **THE ELO CONVERSION IS GUARDED, and the guard is load-bearing.** The natural definition —
this cell's own realized `elo_per_point = elo_D / D` — is **numerically unusable exactly where
this cell most expects to land.** Under `H-NULL-BOUND`, `D ≈ 0` by definition, so that ratio is
a quotient of two independently-noisy near-zero quantities: it does not converge, it is not
bounded, and its sign is not even stable. Quoting a 2σ elo bound through it would produce a
headline number that is an artifact of division. The rule, fixed here before any number exists:

```
IF |z_D| >= 2.0   (i.e. the branch is H-POSITIVE or H-REVERSED, D is well away from zero)
    elo_per_point := this cell's OWN realized elo_D / D.
    Report it, and report the elo display through it.
    Cross-check it against the in-family bracket [16.74, 19.35] (SS2.2) and FLAG any
    reading outside that bracket as a witness anomaly (never a branch input).

ELSE  (H-NULL-BOUND)
    this cell's own ratio is NOT reportable and MUST NOT be printed as a scale.
    The elo display is quoted as a RANGE through the PINNED in-family bracket:
        2 sigma bound = +-(2 x SE_D) pts  =  +-(2 x SE_D x 16.74) .. +-(2 x SE_D x 19.35) elo
    and is LABELLED as a bracket conversion, not a measured scale.
```

The bracket endpoints are the two in-family cells pinned in §2.2 (`cl060_h2h_k8x1376_vs_deploy_k4x688`
16.74 elo/pt; `width_k4x2752_..._b119e9` 19.35 elo/pt). **This is not "importing another cell's
number" in the sense §1 forbids** — the forbidden move is importing another cell's *effect
size*; a unit conversion whose two endpoints are both stated, both in-family, and both carried
as a visible range is the honest alternative to a division by ~zero. The adjudicator implements
this branch-dependent rule directly and prints which limb applied.

**Within-band, deck-paired, single instrument ⇒ NO cross-band humility discount.** Both arms
are the same games on the same decks in the same launch window; `CLAUDE.md`'s CL-068 1.8–2.2×
over-dispersion applies to *cross-band* contrasts and this is the robust class it exempts.
(The old-era priors quoted in `DESIGN.md` §2.1 **are** cross-band and **do** carry the full
discount — that asymmetry is the point of running this cell at all.)

---

## §2 — UNITS AND POWER, STATED BEFORE ANY NUMBER

### §2.1 — σ_D, from seven in-family cells on the current instrument

`σ_D` is **not assumed** — it is read off seven `n=400`-deck, deck-paired, `fixed_v1`+R9,
rust-backend cells already in `experiments/results.csv`, by inverting each one's own published
`paired margin` and `paired z` (`SE = |margin| / |z|`, `σ_D = SE × √400`):

```
cell (results.csv exp_id)                                          SE(n=400)   sigma_D
width_k4x2752_vs_k8x1376_fixed11008_n800_b119e9                     0.68005     13.60   <- closest analogue
simsplit_alloc_a_split_t2752_m1376_..._n800_b123e9                  0.73330     14.67   <- max
simsplit_alloc_b_uniform2064_..._n800_b123e9                        0.65740     13.15
denial_d1_s5o3_deploy_..._n800_b124e9                               0.66192     13.24
joshuabot_confirm_j7zero_..._n799_b126e9                            0.65669     13.13
jrules_d0p25_deploy_..._n800_b128e9                                 0.64598     12.92
jpriors_d0p5_deploy_..._n800_b130e9                                 0.62057     12.41   <- min
                                                    median 13.15 | mean 13.30 | max 14.67
```

`b119e9` is the **structurally closest** cell: a *direct* head-to-head between two production
champions differing **only** in budget allocation at fixed total 11008, same leaf both sides,
`fixed_v1`+R9, rust, `exact-k 2`, deck-paired. Its `σ_D = 13.60`.

```
MODEL A -- median of the seven      sigma_D = 13.15
MODEL B -- b119e9, closest analogue sigma_D = 13.60
MODEL C -- max of the seven         sigma_D = 14.67   <- THIS CELL SIZES ON MODEL C
```

**This cell sizes on Model C** (the conservative bound), by the same reasoning
`carcasum_arb_challenge_prep/DESIGN.md` §3.1 states: a false positive from an underpowered
cell is the worse failure mode, and there is no cheap follow-up queued to catch it.

### §2.2 — n = 700 decks

```
SE_D = sigma_D / sqrt(700) = sigma_D / 26.458

    Model A: SE_D = 0.4970 pts    2 sigma = +-0.994 pts
    Model B: SE_D = 0.5141 pts    2 sigma = +-1.028 pts
    Model C: SE_D = 0.5545 pts    2 sigma = +-1.109 pts   <- the sizing bound

elo-per-point, in-family bracket (display only, NEVER a branch input):
    cl060_h2h_k8x1376_vs_deploy_k4x688 :  49.85 elo / 2.9775 pts = 16.74 elo/pt
    width_k4x2752_..._b119e9           : -19.56 elo / 1.01125 pts = 19.35 elo/pt
    => 2 sigma (Model C) = 1.109 pts  ~=  +-18.6 .. +-21.5 elo
```

**Resolution claim of record: 2σ ≈ ±1.11 pts ≈ ±20 elo.**

**Power against the alternatives that matter, computed before the answer exists:**

```
alternative                                       delta(pts)   z@SE=0.5545   power(2-sided a=.05)
closure CENTRAL (+7.1 elo, MEMO SS9)                  +0.41         0.73             ~11%
closure UPPER bracket (+49.3 elo)                     +2.82         5.08            ~100%
old-era cross-band point read (-14.3 elo, SS2.3)      -0.82        -1.48             ~32%
80%-POWER MINIMUM DETECTABLE EFFECT                   +-1.55       +-2.80              80%
                                                  ( ~= +-26 .. +-30 elo )
```

⚠️ **Read those two lines together and do not conflate them.** This cell **resolves** (2σ) at
±20 elo and has **80% power** only at ±27–30 elo. It is *blind by design* to the closure's own
+7 elo central. §0 already binds the read of a null accordingly.

### §2.3 — the honest prior: it is NOT obviously positive

The only existing reads on this exact contrast are **cross-band** and point *down*:

```
curve_k16x1376_22016_vs_deploy_k4x688  = +35.58 elo   (band 48e9, 2026-07-23, n=196)
cl060_h2h_k8x1376_vs_deploy_k4x688     = +49.85 elo   (a DIFFERENT band, 2026-07-22, n=400)
  naive difference, F minus E           = -14.27 elo
```

That difference is a **cross-band contrast between two separate cells** and therefore carries
the full CL-068 1.8–2.2× SD inflation (nominal 1σ ≈ ±24.7 pooled → inflated ≈ ±44–54 elo). It
is **not** evidence of a negative; it is evidence that **nobody knows the sign**, which is why
§4 is a symmetric two-sided table and not a one-sided confirm. `governance/PRODUCTION.yaml`'s
own `budget_authorized_by` block cites the k16×1376 row as *"plateau context"* and reads it as
*8× being strictly dominated (2× the clock for ~0 elo)* — **this cell is the direct test of
that reading, on a band and an instrument that did not exist when it was written.**

---

## §3 — PRECONDITIONS (every gate individually fail-closed; ABSENT is FAIL)

Each gate is read at the manifest top level, then at `config.*`; the adjudicator **reports
which address resolved** (house `G-BAND`/`G-J1` precedent). Gate set ported from
`track_d1_fair_rebase/READ_RULE.md` §3A, adapted from a five-rung ladder to a one-cell
two-champion head-to-head.

| id | proposition | address | fail on |
|---|---|---|---|
| `G-BAND` | `config.seed_start == 148000000000`, `config.n_decks == 700`, `config.seatings_per_deck == 2` | cell `summary.json` → `config.*` | any mismatch |
| `G-DECKS` | every realized `deck_seed` lies in `148000000000..148000000699`; every counted deck has **both** `a_seat` 0 and 1; `n_common == 700` | adjudicator's own collection over the raw `seed*_a*.json` records | any seed outside the range; any deck present at only one seat and still counted; `n_common != 700` (short is `G-N`'s business, out-of-range is this gate's) |
| `G-SINGLEVAR` | the candidate and opponent config blocks differ in **EXACTLY** `k_dets` (16 vs 8) and the derived `total_sims` (22016 vs 11008), and in **nothing else** — same `cand_leaf_hash` and opponent leaf hash, same `c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`, same `endgame.*`, same `rules_profile`, same `backend.*`, same `code_rev`. **`sims_per_det` is 1376 on BOTH sides and is IN the must-not-differ set** | cross-side diff within the cell's own `summary.json` `config` block | ANY other differing key. (This is the `track_d2_prep` lesson ported: `results.csv d2_rung_compression_U_UNREADABLE...b141e9` asserted single-variability in prose and never checked it.) |
| `G-REV` | `config.code_rev` equals the launcher's `PINNED_SRC_REV`; and `SRC_CLEAN.jsonl` records `src/ engine/ scripts/ rust/ tests/` **CLEAN at every recorded boundary**, with a `pre-flight` boundary and an `after-pass-N` boundary for the final pass | `summary.json` `config.code_rev`; `SRC_CLEAN.jsonl` | rev mismatch; any boundary with `src_clean != true`; a missing pre-flight or final boundary |
| `G-BLIND` | `BLIND_COMMIT` holds a 40-hex sha; that sha is an **ancestor of HEAD**; and it is the commit that introduced this pair's FROZEN banner; `BLIND_PROOF.json` records `is_ancestor_of_head == true` | `BLIND_COMMIT`, `BLIND_PROOF.json`, `git merge-base --is-ancestor` | the literal `PENDING`; a non-ancestor; absent; a `BLIND_PROOF.json` disagreeing with a live re-check |
| `G-LEAF` | `config.cand_leaf_hash == "a36d2e15a3b3d71d"` **AND** `config.opponent.leaf_hash` equal to the SAME value — the pinned `PROD_LEAF_HASH` (`scripts/classical_search/analyze_curvephase.py`; `governance/PRODUCTION.yaml champion.leaf_hash`). **Both sides are full 16-hex hashes**, verified in source at build time: for `--opponent fair-champion` (neither `h800` nor `greedy`) the harness writes the opponent block's `leaf_hash` as `_leaf_hash(opp_leaf_cfg)`, the complete hash. (The sibling `curve125_leaf_provenance` field IS `None` on this path — it is only populated for `net`/`bare-net` — but that is a provenance extra, not the hash, and nothing here depends on it.) | `summary.json` → `config.cand_leaf_hash` and `config.opponent.leaf_hash` | either side mismatching or absent. ⚠️ Structural backstop, not a substitute for the gate: `--opponent fair-champion` is a `_HEAD_TO_HEAD` mode, and the harness's own definition of that set is that **both sides resolve curve125** from the same in-process injection — the two leaves cannot diverge without a harness defect |
| `G-RULES` | `rules_profile.name == "fixed_v1"` **AND** `rules_profile.r9_env_ok == true` **AND** `r9_env_observed == true` | `summary.json` → `rules_profile.*` | anything else. ⚠️ Note this is the **non-inverted** expectation (`fixed_v1` wants R9 **ON**); d1-rebase's `GW-RULES` inversion applies to `walled` cells only and there is no `walled` cell here |
| `G-BACKEND` | `config.backend.name == "rust"`, `config.backend.requested == "rust"`, `mixed_builds == false`, **AND `converted_sides == ["candidate", "opponent"]`** — i.e. BOTH sides ran rust, not just ours | `summary.json` → `config.backend.*` | any leg not rust-resolved; `converted_sides` missing `"opponent"`; `mixed_builds == true`. ⚠️ **The `"opponent"` half is load-bearing and is a STRENGTHENING over d1-rebase's own `G-BACKEND`** (which only required `"candidate"`, because its opponent was the frozen Python `h800` rung by design). Here the opponent IS a production champion; a Python opponent against a rust candidate would be a different, slower, un-preregistered instrument |
| `G-BUDGET` | candidate `(k_dets, sims_per_det, total_sims) == (16, 1376, 22016)` and opponent `== (8, 1376, 11008)`, and the product identity `k × s == total` holds on **both** sides | `summary.json` → `config.champion.*` / opponent budget block | any deviation, or a product that does not multiply out |
| `G-TIEARB` | **the root tie-arbiter is ABSENT on BOTH sides.** Two conjuncts: (a) `cand_tiearb.enabled` is absent or `false`; (b) **NO `tiearb`-named path segment exists anywhere in the flattened manifest or summary outside the `cand_tiearb` subtree.** ⚠️ Conjunct (b) scans **every path segment, not the leaf**, and this is load-bearing: an armed opponent block flattens to `opp_tiearb.enabled` / `opp_tiearb.B` / …, whose LEAF names are `enabled`, `B`, `J`, `mode`, `salt`, `eps` — only the *middle* segment carries the tell-tale name, so a leaf-only scan would let an armed `opp_tiearb` through. ⚠️ (b) is deliberately strict: it fails on the PRESENCE of any such key, armed or not, rather than trying to interpret its state. That is safe here and verified in source: on a disarmed run `eval_fair_puct.py` emits **no** `tiearb`-named key at all — its `tiearb_summary` block is built only `if _ta:` (games with an armed arbiter) and is splatted as `**tiearb_summary`, so an empty dict contributes nothing. A future harness that starts emitting a benign disarmed `tiearb`-named field would therefore trip this gate; that is a **false `VOID`, which is the recoverable direction**, and the fix is to amend the gate, never to relax it into interpreting armed-ness | `summary.json` / `manifest.json` → `cand_tiearb.enabled`, plus a full flattened-key scan of BOTH documents | `cand_tiearb.enabled == true`; OR any `tiearb`-named path segment outside the `cand_tiearb` subtree. ⚠️ **The opponent side is STRUCTURALLY disarmed** — `eval_fair_puct.py` exposes `--cand-tiearb-*` and **no `--opp-tiearb-*` flag of any spelling** (the arbiter is candidate-side-only, rust-only). This gate exists so that structural fact is *recorded as verified*, not merely believed |
| `G-EXACT` | `config.endgame.exact_k == 2`, `mode == "marginalized"`, and the handoff is identical on both sides | `summary.json` → `config.endgame.*` | any deviation. See `WORKERS.conf::EXACT_K` — K=3/4 are clairvoyant-only and a fair cell cannot run them; this is production, not a knob choice |
| `G-N` | **1,400 games scored**; `n_failed == 0`. A nonzero failure rate **< 2%** is REPORTED, not silently absorbed, and does not by itself void (the `b32v64` 0.100% rust-panic-class precedent). `n_common >= 560` (`WORKERS.conf::N_COMMON_FLOOR`) | `summary.json` → `n_scored`, `n_failed`; adjudicator's own `n_common` | short of 1,400 completed games; failure rate ≥ 2%; `n_common < 560` |
| `G-SAT` | the realized candidate win-rate lies in `[0.35, 0.65]` | `summary.json` → `winrate` | outside. **This is a RAIL check, not a strength bar.** Both arms are the same champion at two budgets; a win-rate outside this window means the two sides are not the agents this design says they are (a saturated or mis-wired cell), and the margin would be a rail reading. ⚠️ Deliberately WIDER and SYMMETRIC vs d1-rebase's one-sided `[0.50, 0.90]`, because that cell graded a champion against a deliberately weaker frozen rung and this one grades a champion against **itself** |
| `RECON` | the **analyzer** value (read verbatim off `summary.json`) and the **witness** value (recomputed from scratch from the raw `seed*_a*.json` records by an independent re-implementation) agree within `rel 1e-6 / abs 1e-9` on **every** checked statistic: `paired_mean_margin`, `paired_z`, `n_paired`, `winrate`, `elo` | `summary.json` vs raw records, both read by `adjudicate.py` | disagreement beyond tolerance on any statistic. **The recomputation is a WITNESS, never a branch input** — it can only void, never move, the number |

### §3.1 — `VOID` — checked FIRST, before any branch below

**`VOID` fires** (first-match-wins over everything else) if:

- **ANY** gate in the §3 table fails; **OR**
- the run did not reach its `DONE_cell` sentinel (`run_cells.sh`); **OR**
- the launcher tripped its own void-rate circuit breaker (`WORKERS.conf::VOID_RATE_ABORT_PCT`
  = 10%, a *pre-adjudication* compute-saving abort, distinct from `G-N`'s post-hoc <2% bar);
  **OR**
- the launcher aborted on `RUNTIME_RAM_FLOOR_MB`, on a moved `PINNED_SRC_REV`, or on
  `MAX_PASSES` exhaustion.

`VOID` → **`U-UNREADABLE`.** No `D` is published. Diagnose, patch, re-run on the **SAME band**
(the band is not spent by a `U-UNREADABLE` outcome unless real game records exist on it — the
`BAND_REGISTRY.csv` `RELEASE-IF-NEVER-LAUNCHED` clause precedent).

---

## §4 — BRANCH TABLE (first-match-wins; `VOID` §3.1 checked first)

| branch | condition | action |
|---|---|---|
| **`U-UNREADABLE`** | §3.1 `VOID` fired | No `D` published. Report which gate(s) failed and at which manifest address. Both sides' raw archives are kept and are re-adjudicable after a fix. Not a finding about budget. |
| **`H-POSITIVE`** | `z_D >= +2.0` | **The doubling above production still pays.** Report `D`, `SE_D`, `z_D`, `n_common`, and the elo display via this cell's own realized scale. This **re-opens** the budget-headroom axis as a live strength lever and **falsifies the decay-bound closure's operative reading** (`docs/LEVER_INDEX.md`, MEMO §9) at this rung — the row must be amended, not merely annotated. ⚠️ **It licenses NOTHING about deploy.** F costs **2× the wall-clock per move** of production by construction; whether that is affordable is an **owner** decision, and this cell neither makes nor recommends it. No `PRODUCTION.yaml` change follows from this branch without a separate owner ruling. |
| **`H-REVERSED`** | `z_D <= -2.0` | **The larger budget measurably LOSES.** A real, adjudicable finding, not a gate failure. Report it as such: at 22016 the k16×1376 allocation is *worse* than production's k8×1376, which would make the 2026-07-23 old-era `+35.58` read a cross-band artifact and would **strengthen** the closure beyond ratification. Log a `docs/LEVER_INDEX.md` amendment and flag it in any future budget-ladder proposal. Does not by itself argue for reducing production's budget — that is a different contrast (11008 vs 5504) this cell does not run. |
| **`H-NULL-BOUND`** | neither of the above (`\|z_D\| < 2.0`) | **The bound tightens; the closure is RATIFIED.** Report: headroom above 11008 is **capped at this cell's realized 2σ** — `± 2 × SE_D` **points**, which is the interval of record, plus its elo display quoted as a BRACKET per §1's guarded rule (`± 2 × SE_D × [16.74, 19.35]`), because at `D ≈ 0` this cell's own elo-per-point ratio is a division by ~zero and is NOT reportable. That points interval replaces the decay bound's `[−35, +49]` elo as the interval of record on headroom above 11008. State §0's honesty clause **in the read-out, not just here**: this cell had ~11% power against the closure's own +7.1 elo central, so a null **bounds** the headroom, it does not **locate** it. **No top-up.** There is no reserved extension range and no second read (§3.4 of `DESIGN.md`) — a bounded null IS the licensed deliverable of this purchase, and buying n to chase a +7 elo central would need `n ≈ 5,220` decks (7.5× this purchase), a fresh funding decision, and a fresh band. |

**Read-rule discipline:** the fired branch **is** the authorization to report it — a fired
trigger gets run and reported, not re-litigated (house convention, every prereg in this
family).

---

## §5 — WHAT THIS CELL CANNOT SHOW

- **Anything about `k8×2752` at 22016.** Only one allocation is measured. `k8×2752` read
  `+3.51` in the old era against a common baseline where `k16×1376` read `+35.58`
  (same band 48e9), so this design takes the measured winner and runs **one** arm. If
  `H-POSITIVE` fires, it fires for `k16×1376`, and the allocation question at 22016 remains
  open on the current instrument (`DESIGN.md` §2.1).
- **Anything about budgets other than 22016** — not 44032, not the 5504↔11008 rung below it.
  The decay bound speaks to the whole tail; this cell speaks to exactly one doubling.
- **Anything about DEPLOYABILITY**, at any branch. Wall-clock affordability is an owner
  question (§4, `H-POSITIVE`).
- **Anything about the tie-arbiter.** It is OFF on both sides by construction (`G-TIEARB`).
  A budget effect measured with the arbiter armed could differ and is a separate cell.
- **Anything absolute or superhuman.** This is a self-anchored search contrast between one
  champion and itself. It does not move either structural blocker in `CLAUDE.md`.
- **The `walled` R9-off comparison** — same standing caveat every `fixed_v1` cell carries.

---

## §6 — CLOSE-OUT

Read with `adjudicate.py` (§7), not by hand and not with a sibling cell's `summarize()`. Apply
§4 **exactly as written** — the fired branch IS the authorization to report it. Then the
six-touch checklist (`DESIGN.md` §10).

---

## §7 — THE ADJUDICATOR'S CONTRACT

`adjudicate.py` is committed **in this same blind commit**, before any game. It:

1. reads the cell's `summary.json` (the **ANALYZER** of record is
   `scripts/classical_search/eval_fair_puct.py`, which wrote it);
2. independently recomputes every primary statistic **from scratch** from the raw
   `seed*_a*.json` records (the **WITNESS** path, a separate re-implementation of
   `eval_fair_puct._paired_z`'s per-deck seat-balanced margin) and folds the comparison in as
   the `RECON` gate of §3;
3. evaluates every §3 gate, printing for each: id, PASS/FAIL, the **manifest address that
   resolved**, and the observed value;
4. fires exactly one §4 branch, first-match-wins, `VOID` first;
5. writes `ADJUDICATION.json` (machine verdict) and prints a human read-out;
6. supports **`--selftest`**, which runs the whole gate + branch + witness machinery against
   **synthetic fixtures** with no real archive present — a passing archive, one fixture per
   §3 gate that fails exactly that gate, an analyzer/witness disagreement fixture, and one
   fixture per §4 branch (`H-POSITIVE` / `H-REVERSED` / `H-NULL-BOUND` / `U-UNREADABLE`) —
   and exits nonzero if any fixture does not produce its expected verdict. **`--selftest`
   must be run and must pass before the real adjudication is trusted**; it touches no band,
   spends no blindness, and reads no real record.
