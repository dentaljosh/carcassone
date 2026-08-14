# J-RULES SURFACE B — DEPLOY-BUDGET CELL, PRE-REGISTRATION

> **⚠️ STATUS 2026-08-14 — RAN AND CLOSED (six-touch). BRANCH `N3 NO CONVICTION` FIRED, AND
> AT |z| = 0.03 IT IS A NULL AT THE VERY TIGHTEST END OF THAT BAND — essentially a perfect
> tie.** `jpriors_d0p5_deploy11008`, band **1.30e11** (`+0..+399`), n=800 deck-paired:
> W389/D15/L396, wr 0.4956, **PRIMARY STATISTIC deck-paired margin −0.0175 pts/deck** (sem
> 0.6214), **z −0.0282**, elo **−3.04 ± 24.57** (2σ). **Realized 2σ bound, both units per read
> rule 2: ±1.2427 pts/deck and ±24.57 elo.** 400/400 decks fully paired, **0 failed games**
> (`N5` did not fire), 0 stranded claims, **13/13 wiring gates PASS**.
>
> ⭐ **`N4` DID NOT FIRE — `ms_ratio_cand_over_opp` 1.1751, below the 1.20 trigger ⇒ THIS IS A
> CLEAN NULL, NOT CONFOUNDED BY BUDGET.** Surface A realized 1.2116 and had its loss
> downgraded; this cell did not, which makes it **more** informative than surface A's, not
> less.
> ✅ **The §6 INVERTED gate passed and its pass is correct:** `cand_leaf_hash` **equals** the
> champion `a36d2e15a3b3d71d` because surface-B knobs are `SearchConfig`, not `LeafConfig` —
> **no leaf moves**, so a *moved* hash would have been the defect. Liveness rests on the
> resolved `config.cand_jrules_prior` (dose 0.5 / mask 31 / scope `all`) plus the
> `_assert_surface_b_live` control, which ran and passed on **every box that played a game**
> with its output captured before game 1.
> ⭐ **This is the PRE-REGISTERED SIMS-WASHOUT OUTCOME** named in [DESIGN §1](DESIGN.md)
> before game 1: **11,008 sims of PUCT wash out a 13.05 %-pick-flip perturbation entirely**
> (the calibration measured 203/1556 champion picks flipped on real E4 games, Wilson-95
> 11.46–14.81 %, *not* marginal). **CL-051's counter-precedent did NOT repeat.**
> ⛔ **NO CLAIM IS MINTED** — a non-conviction mints none (house precedent: the joshuabot
> confirm); `governance/CLAIM_REGISTRY.csv` gains no row, and **`CL-081` (reserved but unused
> by the surface-A prereg) is left untouched and available**. **`|z| < 2` is NEVER "refuted"**
> (§5 read rule 1): *"killed"*, *"dead"* and *"does nothing"* are FORBIDDEN readings.
> ⛔ **§7 and §9 bind:** this prices **this encoding at dose 0.5 / mask 31 / scope `all`**. It
> does **not** refute the anchor's strategy or his actual play, and leaves untouched the
> per-rule mask ablations · `scope=own` · J7 · J9 · the root filters J10f/J3's hard floor · the
> other dose rungs · and the static leaf surface. **No contrast with surface A is a statistic**
> (§5 read rule 8).
>
> Band **1.30e11** retired `decision_influenced=yes`; `results.csv`
> `jpriors_d0p5_deploy_fixed_v1_vs_champ11008_n800_b130e9`; DECISIONS 2026-08-14. Nothing
> promoted; `governance/PRODUCTION.yaml` **untouched**. Everything below this banner is the
> pre-registration exactly as committed before game 1, unedited.

> **⚠️ STATUS AT WRITING 2026-08-14: THIS IS THE PRE-REGISTRATION OF RECORD. COMMITTED BEFORE GAME 1.**
> Promoted (`git mv`) from `DEPLOY_PREREG_DRAFT.md`, which was written 2026-08-14 with the
> build, BEFORE the calibration had produced any flip rate and BEFORE any band was claimed.
> **Exactly two fields were filled at promotion and nothing else was touched:**
> 1. the **dose** — `0.5` — named mechanically by [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md)
>    §3.2 `FUND-SMALLEST`, applied in [`CALIB_READOUT.md`](CALIB_READOUT.md) (the read-rule was
>    committed before any flip rate existed);
> 2. the **band** — `130000000000` — claimed in `governance/BAND_REGISTRY.csv`
>    (sentinel [`BAND_CLAIMED.json`](BAND_CLAIMED.json)).
>
> No threshold, no branch, no statistic, no gate was changed. The cell's name was fixed from
> the funded dose as §3 already provided for. `git log --follow` on this path is the audit
> trail; any other edit voids the pre-registration.
>
> **0 games · 0 numbers read · `governance/PRODUCTION.yaml` untouched on every branch · no
> `results.csv` / claim row until close-out · the launching session adjudicates nothing.**
>
> Cloned from the adjudicated surface-A prereg
> ([`../jrules_on_search_20260813/DEPLOY_PREREG.md`](../jrules_on_search_20260813/DEPLOY_PREREG.md))
> with the surface-B inversions marked ⚠️ throughout. Design of record:
> [`DESIGN.md`](DESIGN.md).

---

## 1. Why this cell exists

Surface A (the same interview as ADDITIVE STATIC LEAF TERMS at the champion's own budget)
lost −2.4912 pts/deck (z −3.8564, elo −33.98, n=800) with the loss **confounded by budget**
(`ms_ratio` 1.2116 > 1.20 ⇒ N1 downgraded; no claim minted) — and its §7 discloses the
encoding as strictly weaker than the strategy (dropped join predicates, no planning clause,
no bag/phase/opponent-reserve conditioning). This cell prices the SAME strategy on the
surface those disclaimers do not reach: **policy priors at every expansion of the champion's
own PUCT search** — the rules in the bot's original forms (DESIGN §3), biasing where visits
go while every backed-up value stays the unmodified champion's. The double-count mechanism
that CL-080 and surface A share (a static term re-pricing what the search prices emergently)
does not apply to a prior; the pre-registered risk here is instead the **sims-washout null**
(DESIGN §1), which the calibration's flip-rate gate must clear before this cell is bought.

## 2. How the dose gets named

By [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) — committed BEFORE any flip rate was read —
ladder {0.5, 1.0, 2.0} + pre-committed 0.25 FINER-RUNG, `FUND-SMALLEST` at the 10%
point-estimate bar, `NO-EXPRESSION` = stop, no cell. The named rung's flip rate rides here
verbatim, with `marginal` if its Wilson-95 lower bound is under 10%.

**FILLED AT PROMOTION** from [`CALIB_READOUT.md`](CALIB_READOUT.md) (1,556 graded champion
plies per arm, 26 archives, `all_replay_scores_match: true`): FINER-RUNG did **not** fire
(`f(1.0) = 0.17095`, not `> 0.20` strictly); **`FUND-SMALLEST` fired** and names
**dose `0.5`**, whose flip rate rides here verbatim: **`f = 13.05 %` (203/1556), Wilson-95
[11.46 %, 14.81 %]**. The lower bound `0.1146 ≥ 0.10`, so this cell is **NOT `marginal`** and
no marginal caveat rides into this prereg. ⚠️ The flip rate is **not a result** (§5) and
clearing the bar buys resolvability, not safety.

## 3. The cell

Exactly **one** cell.

| | `jpriors_d0p5_deploy11008` *(name fixed at promotion from the funded dose)* |
|---|---|
| candidate | the production champion — **UNMODIFIED LEAF `a36d2e15a3b3d71d`** — with `jrules_prior_dose` **`0.5`**, `jrules_prior_mask` **31**, `jrules_prior_scope` **`all`** |
| opponent | the **UNMODIFIED** production champion (no leaf override, no prior knobs) |
| harness | `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion` (FAIR PIMC) via `menu_fair_cell.sh` |
| budget | **k8 × 1376 = 11008 on BOTH arms** (`--k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376`) |
| backend | `--backend rust`, both sides |
| rules | `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1` |
| endgame | `--exact-k 2`, shared |
| search knobs | `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits` |
| the knob | `--cand-jrules-prior-dose 0.5` (candidate side ONLY; no `--cand-leaf-json` at all — ⚠️ this cell overrides NO leaf) |
| run flags | `--paired --shared-claim --no-results-csv`, `nice -n 19`, detached |
| **n** | **800 deck-paired = 400 decks × 2 seats**, CRN |
| band | **`130000000000`** (seeds `130000000000..130000000399`) — fresh, claimed in `governance/BAND_REGISTRY.csv`, sentinel [`BAND_CLAIMED.json`](BAND_CLAIMED.json) (1.25e11–1.28e11 are retired, decision-influenced) |
| **primary statistic** | **deck-paired margin in pts/deck, with its z.** Elo secondary, reported, never promoted |

## 4. PRE-STATED PRIOR — recorded before any number

**Expectation: a LOSS or a NULL, with the null the distinctive risk.** (i) The washout
argument (DESIGN §1) predicts a prior intervention at 11008 sims can read null; a null here
is the honest measured form of that argument, not a surprise. (ii) Every hand-crafted term in
the record has read null or harmful. (iii) Against that: the double-count mechanism does not
apply to priors, CL-051 is a genuine same-surface precedent of a win, and this encoding is
strictly more faithful than surface A's. This prior licenses no branch reading and does not
soften §7.

## 5. Read rules — pre-committed

Identical to surface A's §5 (gates before numbers; `|z| < 2` is never "refuted"; a null
states its realized 2σ bound in both units; winner's-curse paragraph on any positive; no
pooling — not with surface A's cell, not with the calibration, not across bands; cross-band
contrasts get 1.8–2.2× σ inflation; the flip rate is not a result). One addition:

8. **No contrast with surface A's cell is a statistic.** Same strategy, different encoding,
   different band, different candidate — "B lost by less than A" or "B ≥ A" may be written
   only as an observation about design, never differenced, never given a z.

## 6. Branch map — evaluated in order

| # | branch | condition | reading — pre-committed |
|---|---|---|---|
| **N0** | **WIRING GATE — BLOCKS ALL READING** | any of the **13 checks** below fails | **VOID: no number is read**; re-run on a fresh band or abandon. |
| **N1** | REFUTED | margin **z ≤ −2.0** | The anchor's articulated strategy, encoded as expansion-time policy priors at the smallest authorized dose, does not survive inside the champion's own search. The knob stays default-off permanently; **§7's scope clause binds the write-up.** Subject to N4 downgrade. |
| **N2** | POSITIVE SIGNAL, NOT A PROMOTION | margin **z ≥ +2.0** | The first live positive on a hand-crafted surface — still not a promotion, not a champion change; requires a fresh-band confirm at n=800 (named, not funded); curse-calibrate to ~half face value. `PRODUCTION.yaml` untouched on this branch as on every branch. |
| **N3** | NO CONVICTION | **\|z\| < 2.0** | Recorded as no-conviction at this dose with sign, lean and realized bound in both units. No cheaper rung exists (`FUND-SMALLEST` names the floor); no top-up without a mechanism argument, a new prereg and a fresh band (CL-079 binding). |
| **N4** | COST CONFOUND | measured `ms_ratio_cand_over_opp` | **Benched prediction ≈ 1.15 (scope all; min-of-reps under shared tenancy — DESIGN §7), and surface A's bench UNDERSHOT its realized 1.2116.** Read off `menu_block_summary` on the FIRST block and confirmed at close-out. **If > 1.20: N1 downgrades to "loss, confounded by budget"** — no claim at Refuted. If ≤ 1.05: the cost-neutral reading is restored explicitly. Between: the reading stands with the ratio quoted. ⚠️ Surface A's AMENDMENT_1 (equal-sims makes wall-clock strength-neutral; the discount belongs on N2, not N1) is **recorded dissent, not adopted** — the owner's "default" ruling governs here too unless the owner rules otherwise BEFORE unblinding. ⚠️ A first-block ratio already > 1.20 is grounds to ABORT before the band is spent — that decision is the owner's and must be made blind to any strength field. |
| **N5** | VALIDITY TRIGGER | failed games **> 0.5%** of n | Stop and investigate before reading any statistic (house reference; the bounded-action-window family is known at ~0.125%). |

### The 13 wiring gates (N0), read from `manifest.json` before any strength number

⚠️ Gates 1–2 are **INVERTED** relative to every leaf-term cell, and gate 4 is the one that
actually proves the term live — surface B moves NO leaf hash, so a moved-hash check proves
nothing here (DESIGN §4).

1. `config.cand_leaf_hash` **EQUALS** `a36d2e15a3b3d71d` (the candidate's leaf is the
   champion's — a DIFFERING hash means a leaf change was smuggled into a prior cell ⇒ VOID).
2. `config.opp_leaf_hash` == `a36d2e15a3b3d71d`.
3. `config.cand_leaf_json` is null (nothing overrode the candidate leaf).
4. **`config.cand_jrules_prior.dose` == the funded dose (nonzero)** — THE liveness gate.
5. `config.cand_jrules_prior.mask` == 31.
6. `config.cand_jrules_prior.scope` == `"all"`.
7. No `jrules_*` key in `config.cand_leaf_cfg` and no `jrules*` key of any kind on the
   opponent side (neither the static bundle nor prior knobs may ride along).
8. `k_dets` 8 and `sims_per_det` 1376 (`total_sims` 11008) on **BOTH** `config.champion` and
   `config.opponent` (⚠️ read the numbers, not the `equal_wall_clock_note` boilerplate —
   [MANIFEST_LABEL_TRAPS](../jrules_on_search_20260813/MANIFEST_LABEL_TRAPS.md) applies).
9. Top-level `rules_profile.name` == `fixed_v1`, `rules_profile.r9_env_expected` true,
   `leaf_env.CARCASSONNE_FIX_R9` == `"1"`.
10. `config.backend` == `rust` (both sides run it — the python path fail-louds, but the gate
    reads the stamp).
11. **800 records, 800 unique `(deck_seed, seat)`, 0 missing, 0 extra, all 400 decks fully
    paired.**
12. Surrogate variant-id (the `variant_id` field does not exist in `eval_fair_puct` — learned
    from surface A): ONE manifest, and all 800 records agreeing on
    `(sims, k_dets, exact_k, opponent, info, rung_sims)`.
13. The surface-B **positive control** (`jrules_priors_e4_replay._assert_surface_b_live`) ran
    and PASSED on **every box that played a game**, under the launcher env canon, with its
    output captured in the cell's logs **before game 1** — the per-box stale-wheel /
    zeroed-dose guard that no hash can provide on this surface.

**Reported alongside on every branch:** W/D/L · elo ± 1σ · paired margin + realized se ·
`ms_ratio_cand_over_opp` · sign agreement elo/margin · `n_paired_decks` · realized throughput
+ worker count · failed-game count and family.

## 7. Scope of refutation — binding on the write-up of N1

A loss refutes **"this strategy, as expansion-time policy priors, at this dose/mask/scope,
inside the champion's search"**. It does NOT refute the strategy. But note what a loss here
means that surface A's could not: the named encoding disclaimers of A's §7 — the dropped
join predicates, the unexpressed planning clause, the missing bag/reserve/margin conditioning
— are **removed** on this surface (DESIGN §3). A clean (non-N4-confounded) negative here
therefore bounds the *articulated strategy at the champion's depth* far more tightly. Still
untouched by every branch: the per-rule mask ablations · the `scope=own` variant (a different
hypothesis — opponent modelling — needing its own prereg) · J10f/J3's hard floor (root
filters, never built) · J7 · J9 · dose rungs other than the funded one · and any statement
about the anchor's actual play (which includes everything he cannot articulate).

## 8. Honesty items — recorded before the run

1. **No leaf hash can prove this term live** (DESIGN §4) — gates 4 and 13 carry that load
   alone. A reader who verifies only hashes has verified nothing about this cell.
2. **The candidate searches with priors the champion was never tuned under.** `c_puct`/
   `tau_p` optima were swept against the unboosted priors; nothing here re-sweeps them, and
   no branch may claim the surface was given its best configuration.
3. **The `JP_*` constants are frozen copies of `joshua_bot.PRESETS["current"]`** (pinned by
   `test_constants_match_joshua_bot`); this cell tests the interview as the tournament
   selected it, not a re-fit.
4. **Cost prediction quality is known-poor on this family:** surface A predicted 1.12–1.14
   and realized 1.2116. §6 N4's first-block abort option exists because of exactly that.
5. **The §7-of-DESIGN bench was taken on a shared-tenancy box** (min-of-reps); the ratio of
   record is the cell's own `ms_ratio`, never the bench.
6. **J8 still reads rarely**; a bundle result is not a J8 result.
7. The 6-ply wiring smoke of the instrument (0/6 flips at d0.25, `partial`, VOID by rule) is
   the only flip-shaped number that existed when this draft was written.

## 9. What this cell cannot say

One dose, one mask (31), one scope (`all`), prior surface only; nothing about other rungs,
ablations, `scope=own`, root filters, the static surface (whose route stays open per its own
downgrade), or the anchor's unarticulated play. Not poolable with anything (§5). Nothing is
deployable from any branch, including N2.

## 10. Standing constraints

`governance/PRODUCTION.yaml` untouched on every branch · no promotion on any branch · no
`results.csv` / `CLAIM_REGISTRY` row until close-out · no adjudication by the launching
session · band row written at claim time with `decision_influenced = not yet`, flipped at
close-out · six-touch close-out in one sitting, then `python3 scripts/doc_lint.py`.
