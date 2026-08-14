# J-RULES SURFACE C — DEPLOY-BUDGET CELL, PRE-REGISTRATION **(DRAFT)**

> **⚠️ STATUS 2026-08-14 — NEVER PROMOTED, BY THE RULE'S OWN BRANCH.** The
> calibration ran the same day ([`CALIB_READOUT.md`](CALIB_READOUT.md)) and
> **`NO-EXPRESSION` fired**: every pre-registered mask reads an exclusion rate
> of 2.80–7.76%, below the committed 10% resolvability bar (the largest mask's
> Wilson-95 upper bound is 9.07%). Per the banner above, a NO-EXPRESSION
> outcome means **no promotion ever happens and no cell is bought** — this
> draft is retained as the record of what WOULD have run. No band was claimed;
> nothing below was filled.

> **⚠️ STATUS AT WRITING 2026-08-14: DRAFT. NOT the pre-registration of record until
> promoted.** Written with the build, BEFORE the calibration had produced any exclusion
> rate and BEFORE any band was claimed. **Exactly two fields are open and are filled at
> promotion (`git mv` to `DEPLOY_PREREG.md`), nothing else may be touched:**
> 1. the **mask** — `FILLED-AT-PROMOTION` — named mechanically by
>    [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) §3 `FUND-SMALLEST`, applied in
>    [`CALIB_READOUT.md`](CALIB_READOUT.md) (the read-rule was committed before any rate
>    existed). A `NO-EXPRESSION` / `OVER-WINDOW` / all-`SAFETY` outcome means **no
>    promotion ever happens and no cell is bought**.
> 2. the **band** — `CLAIMED-BY-ORCHESTRATOR` — claimed by the owner/orchestrator in
>    `governance/BAND_REGISTRY.csv` (sentinel `BAND_CLAIMED.json`), never by the build
>    session.
>
> No threshold, branch, statistic or gate may change at promotion; the cell's name is
> fixed from the funded mask (`jfilter_m{mask}_deploy11008`). `git log --follow` is the
> audit trail; any other edit voids the pre-registration.
>
> **0 games · 0 strength numbers read · `governance/PRODUCTION.yaml` untouched on every
> branch · no `results.csv` / claim row until close-out · the launching session
> adjudicates nothing.**
>
> Cloned from the adjudicated surface-B prereg
> ([`../jrules_priors_20260814/DEPLOY_PREREG.md`](../jrules_priors_20260814/DEPLOY_PREREG.md))
> with the surface-C differences marked ⚠️ throughout. Design of record:
> [`DESIGN.md`](DESIGN.md).

---

## 1. Why this cell exists

Surface A (static leaf terms) lost with the loss confounded by budget (`ms_ratio` 1.2116);
surface B (PUCT priors) read a MEASURED CLEAN NULL — the sims-washout: 11,008 sims wash out
a demonstrably-live 13% pick-flip prior perturbation. This cell prices the SAME strategy on
the one surface the washout cannot reach: the bot's HARD FILTERS applied to the champion's
ROOT candidate set (DESIGN §1–§2). A filter is not advisory — an excluded action gets zero
visits in every determinization and cannot win the pooled-Q argmax at any sims. The
double-count mechanism of the two leaf-term losses does not apply (a filter adds no score);
the new, pre-registered risk is the opposite one: **when the filter is wrong, the champion's
evidence about the excluded move is thrown away, not outvoted** — the honest directional
prior for this cell is therefore a LOSS.

## 2. How the mask gets named

By [`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) — committed BEFORE any exclusion rate was
read — ladder `j10:2 · j3:8 · current:11 · all:15` (the mask lattice IS the ladder; a
filter has no dose), **SAFETY first** (guard-yield rate > 5% ⇒ malformed, struck),
then `FUND-SMALLEST` in the exclusion-rate window [10%, 25%], `NO-EXPRESSION` /
`OVER-WINDOW` = stop, no cell. The funded arm's exclusion rate and yield rate ride here
verbatim at promotion, with `marginal` if the Wilson-95 lower bound is under 10%.

**FILLED AT PROMOTION from [`CALIB_READOUT.md`](CALIB_READOUT.md):** `FILLED-AT-PROMOTION`.

## 3. The cell

Exactly **one** cell.

| | `jfilter_m{MASK}_deploy11008` *(name fixed at promotion from the funded mask)* |
|---|---|
| candidate | the production champion — **UNMODIFIED LEAF `a36d2e15a3b3d71d`** — with `jrules_filter_mask` **`FILLED-AT-PROMOTION`**, `jrules_filter_min_keep` **1** |
| opponent | the **UNMODIFIED** production champion (no leaf override, no prior knobs, no filter knobs) |
| harness | `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion` (FAIR PIMC) |
| budget | **k8 × 1376 = 11008 on BOTH arms** (`--k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376`) |
| backend | `--backend rust`, both sides |
| rules | `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1` |
| endgame | `--exact-k 2`, shared |
| search knobs | `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits` |
| the knob | `--cand-jrules-filter-mask {MASK}` (candidate side ONLY; `--cand-jrules-filter-min-keep 1`; no `--cand-leaf-json` at all — ⚠️ this cell overrides NO leaf) |
| run flags | `--paired --shared-claim --no-results-csv`, `nice -n 19`, detached |
| **n** | **800 deck-paired = 400 decks × 2 seats**, CRN |
| band | **`CLAIMED-BY-ORCHESTRATOR`** — fresh, claimed in `governance/BAND_REGISTRY.csv` before game 1 (1.25e11–1.30e11 are retired, decision-influenced) |
| workers | **laptop W22 / local W30** (the surface-B deploy split; census + wheel rebuild per box first — DESIGN §6 footgun) |
| **primary statistic** | **deck-paired margin in pts/deck, with its z.** Elo secondary, reported, never promoted |

## 4. PRE-STATED PRIOR — recorded before any number

**Expectation: a LOSS, with an unresolvable-small-effect null the second most likely.**
(i) Every binding event substitutes a one-ply-calibrated hard rule for an 11,008-sim search
verdict, and the whole hand-crafted record (CL-055/063/074/078/079/080, A, B) is null-or-
harmful. (ii) Unlike surface B there is no washout escape: the perturbation cannot be
searched away, so a genuinely wrong rule MUST show as a loss. (iii) Against that: the
filters encode pure caution the champion may already mostly obey (the calibration prices
exactly how often it doesn't), the double-count mechanism is absent, and F-END is plausibly
strictly good. This prior licenses no branch reading and does not soften §7.

## 5. Read rules — pre-committed

Identical to surface B's §5 (gates before numbers; `|z| < 2` is never "refuted"; a null
states its realized 2σ bound in both units; winner's-curse paragraph on any positive; no
pooling — not with A's or B's cells, not with the calibration, not across bands; cross-band
contrasts get 1.8–2.2× σ inflation; the exclusion rate is not a result). Additions:

8. **No contrast with surface A's or B's cells is a statistic.** Same strategy, different
   encoding, different band, different candidate — "the filter did better/worse than the
   prior" may be written only as an observation about design, never differenced, never
   given a z.
9. **The triptych reading is licensed only as prose**: with A = confounded loss and B =
   clean null, this cell completes evaluation/advice/constraint — but no cross-cell number
   may be computed.

## 6. Branch map — evaluated in order

| # | branch | condition | reading — pre-committed |
|---|---|---|---|
| **N0** | **WIRING GATE — BLOCKS ALL READING** | any of the **14 checks** below fails | **VOID: no number is read**; re-run on a fresh band or abandon. |
| **N1** | REFUTED | margin **z ≤ −2.0** | The anchor's hard rules, encoded as root filters at the funded mask, hurt the champion at its own depth — the excluded moves were worth more than the rules' caution. The knobs stay default-off permanently; **§7's scope clause binds the write-up.** Subject to N4 downgrade. |
| **N2** | POSITIVE SIGNAL, NOT A PROMOTION | margin **z ≥ +2.0** | The first live positive on a hand-crafted surface — still not a promotion, not a champion change; requires a fresh-band confirm at n=800 (named, not funded); curse-calibrate to ~half face value. `PRODUCTION.yaml` untouched on this branch as on every branch. |
| **N3** | NO CONVICTION | **\|z\| < 2.0** | Recorded as no-conviction at this mask with sign, lean and realized bound in both units. No cheaper rung exists; no top-up without a mechanism argument, a new prereg and a fresh band (CL-079 binding). ⚠️ Unlike surface B, a null here is NOT a washout reading — the perturbation is unwashable — so the pre-committed interpretation is "the excluded moves and the rules' substitutes were near-equivalued at n=800 resolution". |
| **N4** | COST CONFOUND | measured `ms_ratio_cand_over_opp` | **Benched prediction ≈ 1.00 (DESIGN §7 — the filter runs once per meeple move; a live drop can even cheapen the move), but cost prediction quality is known-poor on this family (A: predicted 1.12–1.14, realized 1.2116).** Read off the FIRST block and confirmed at close-out. **If > 1.20: N1 downgrades to "loss, confounded by budget"** — no claim at Refuted. If ≤ 1.05: the cost-neutral reading is stated explicitly. Between: the reading stands with the ratio quoted. A first-block ratio already > 1.20 is grounds to ABORT before the band is spent — the owner's call, made blind to any strength field. Surface A's AMENDMENT_1 remains recorded dissent, not adopted. |
| **N5** | VALIDITY TRIGGER | failed games **> 0.5%** of n | Stop and investigate before reading any statistic. |

### The 14 wiring gates (N0), read from `manifest.json` + records before any strength number

⚠️ Gates 1–2 are **INVERTED** relative to every leaf-term cell (no leaf hash moves on this
surface), and gates 4 + 13 + 14 are the ones that actually prove the filter live.

1. `config.cand_leaf_hash` **EQUALS** `a36d2e15a3b3d71d` (a DIFFERING hash means a leaf
   change was smuggled into a filter cell ⇒ VOID).
2. `config.opp_leaf_hash` == `a36d2e15a3b3d71d`.
3. `config.cand_leaf_json` is null (nothing overrode the candidate leaf).
4. **`config.cand_jrules_filter.mask` == the funded mask (nonzero)** — the resolved-knob
   liveness gate.
5. `config.cand_jrules_filter.min_keep` == 1.
6. `config.cand_jrules_prior` is null (surface B may not ride along) and no `jrules_*` key
   in `config.cand_leaf_cfg` (surface A may not ride along).
7. No `jrules*` key of any kind on the opponent side.
8. `k_dets` 8 and `sims_per_det` 1376 (`total_sims` 11008) on **BOTH** `config.champion`
   and `config.opponent` (read the numbers, not boilerplate labels —
   [MANIFEST_LABEL_TRAPS](../jrules_on_search_20260813/MANIFEST_LABEL_TRAPS.md) applies).
9. Top-level `rules_profile.name` == `fixed_v1`, `rules_profile.r9_env_expected` true,
   `leaf_env.CARCASSONNE_FIX_R9` == `"1"`.
10. `config.backend` == `rust` (both sides).
11. **800 records, 800 unique `(deck_seed, seat)`, 0 missing, 0 extra, all 400 decks fully
    paired.**
12. Surrogate variant-id: ONE manifest, all 800 records agreeing on
    `(sims, k_dets, exact_k, opponent, info, rung_sims)`.
13. The surface-C **positive control** (`jrules_filter_e4_replay._assert_surface_c_live`,
    or the pinned-root probe run standalone) ran and PASSED on **every box that played a
    game**, under the launcher env canon, with output captured **before game 1**.
14. **THE FILTER FIRED: `sum(cand_jf.dropped_total)` over the cell's 800 records ≥ 1** —
    a live-mask cell where the filter never dropped anything is champion-vs-champion and
    is VOID, not a null. (Reported alongside: the per-game distribution, the per-filter
    fire totals, and the total yield count — the guard-yield rate at deploy is a
    first-class close-out number.)

**Reported alongside on every branch:** W/D/L · elo ± 1σ · paired margin + realized se ·
`ms_ratio_cand_over_opp` · sign agreement elo/margin · `n_paired_decks` · realized
throughput + worker count · failed-game count and family · `cand_jf` totals
(dropped/fires/yields/applicable).

## 7. Scope of refutation — binding on the write-up of N1

A loss refutes **"this strategy, as root filters, at this mask, with this min_keep, inside
the champion's fair-PIMC root"**. It does NOT refute the strategy, and it does not touch:
the other mask configurations · `min_keep > 1` variants · the `j8brk` exemption variant ·
the `early`-epoch parameters · per-game-latched `k0` · a TILE-phase filter surface (never
built — the bot has none) · an in-tree filter surface (never built, deliberately) · J7 ·
J9-as-term · the anchor's actual play. ⚠️ With surfaces A and B measured, a clean negative
here DOES close the last of the three named encoding surfaces — the write-up may say "all
three encoding surfaces are measured; none transferred" but must attribute per-surface
scopes, not "the strategy is refuted".

## 8. Honesty items — recorded before the run

1. **No leaf hash can prove this filter live** — gates 4, 13, 14 carry that load alone.
2. **The exclusion rate is a lower bound on behavioural change** (visit reallocation among
   kept actions is uncounted at calibration; the cell measures the full effect).
3. **The `JF_*` constants are frozen copies of `joshua_bot.PRESETS["current"]`** with `k0`
   frozen at 72 and `j8_break_reserve_floor` frozen OFF (pinned by
   `test_constants_match_joshua_bot`); this cell tests the interview as the tournament
   selected it, not a re-fit.
4. **F-J3's tags read the child afterstate through the same engine the search uses**; the
   rust and python mirrors are parity-gated, but the bot's original runs on the python
   object engine — any engine-level divergence is bounded by the replay parity suite.
5. **Cost prediction quality is known-poor on this family** (A predicted 1.12–1.14,
   realized 1.2116) — hence N4's first-block abort option despite the ≈1.00× expectation.
6. **The filter binds only on meeple-phase PIMC roots** (~half of decisions; fewer after
   the exact latch); the calibration's applicable-share is reported so the cell's
   perturbation is interpretable.

## 9. What this cell cannot say

One mask, one min_keep, root-only, meeple-only, filter surface only; nothing about other
masks, doses that do not exist, prior/leaf surfaces, or the anchor's unarticulated play.
Not poolable with anything (§5). Nothing is deployable from any branch, including N2.

## 10. Standing constraints

`governance/PRODUCTION.yaml` untouched on every branch · no promotion on any branch · no
`results.csv` / `CLAIM_REGISTRY` row until close-out · no adjudication by the launching
session · band row written at claim time with `decision_influenced = not yet`, flipped at
close-out · six-touch close-out in one sitting, then `python3 scripts/doc_lint.py`.
