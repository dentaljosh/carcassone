# J-RULES ON SEARCH — **DEPLOY-BUDGET** CELL, PRE-REGISTRATION

> **STATUS: WRITTEN AND COMMITTED BEFORE THE BAND WAS CLAIMED AND BEFORE GAME 1 (2026-08-13).
> NOT RUN — 0 games, 0 numbers read.**
> One cell, one dose, no ladder. The dose was named by a rule committed before any flip rate
> existed (`bf0f94cf`, `552c7fe0`); the band is claimed in the same commit as this file.
> [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) is untouched on **every**
> branch, no `results.csv` row and no claim row is owed until close-out, and the launching
> session adjudicates nothing.
>
> ⚠️ **The dose is the LADDER'S FLOOR, not a gentle dose.** `jrules_dose = 0.25` is the
> smallest rung the pre-registered rule is permitted to name. It flips **23.65 %** of champion
> picks — ~**2.3×** the open-city rung that cost **−53.8 elo** (CL-080). There is no cheaper
> rung to retreat to (§6 N3).
>
> ⚠️ **This cell is NOT cost-neutral** (predicted `ms_ratio` ≈ 1.12–1.14), unlike both CL-080
> arms (~1.01). The cost confound is pre-registered as its own branch (§6 N4), not discovered
> at read time.
>
> **Pre-stated expectation: a LOSS (§4).** Recorded before the number so that a loss cannot be
> retro-fitted as "expected" and a win cannot be under-credited.

Design of record: [`DESIGN.md`](DESIGN.md) §8 (what the eval must be) + §5/§6 (what was built,
what it expresses) + §11 (launch gates). Dose selection:
[`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) (committed `bf0f94cf`, applier `552c7fe0`, **both
before any arm's flip rate was read**) → branches **`FINER-RUNG` then `FUND-SMALLEST`** →
[`CALIB_READOUT.md`](CALIB_READOUT.md). Motivating verdict:
[`../joshuabot_20260812/CONFIRM_VERDICT.md`](../joshuabot_20260812/CONFIRM_VERDICT.md)
§"The design fix this run earns (named, not funded)" — **this prereg funds it.**

---

## 1. Why this cell exists

The 2026-08-13 Joshua-bot tournament measured the anchor's self-described strategy (rules
J1–J9) as a **scripted opponent** on a **one-ply greedy base** and it lost to the production
champion by **−16.0 pts/deck (z −24.4)**. The confirm verdict adjudicated the *instrument*
question NO with power and then said exactly why that is not an answer about the strategy: the
bot plays greedy, the champion plays 11008-sim PIMC + exact endgame, and **no amount of n fixes
that**. The tournament therefore priced **encoding + shallow base**, not **strategy**.

This cell removes the confound the only way it can be removed: the J-rules ride on the
**champion's own leaf, at the champion's own budget**, against the **unmodified champion**, so
the only difference between the two arms is the strategy. Per **CL-079** a 2750-ablation screen
is *not* a substitute and must not be run instead of this cell (denial read margin z −2.293 at
2750 and z −0.127 at 11008 on the same leaf; the kill did not transfer in either direction and
the two are not poolable). **The deploy budget is the budget we play at, so it is the budget
that decides.**

## 2. How the dose was named — load-bearing, and it is NOT "we picked a gentle one"

[`CALIB_READ_RULE.md`](CALIB_READ_RULE.md) fixed the ladder `{0.5, 1.0, 2.0}`, the 10 % funding
bar on the **point estimate**, the `FINER-RUNG` trigger at `f(1.0) > 0.20`, and the
`FUND-SMALLEST` funding branch — and was **committed to git before the instrument was ever run
against an archive** (`bf0f94cf`; the mechanical applier `make_calib_readout.py` at `552c7fe0`).

Measured champion-ply search pick-flip rates, 26 banked E4 archives, **1,556 champion plies per
rung**, CRN, replay checksum 26/26, 91.9 % of graded plies replayed at the **deploy** budget
k8×1376:

| rung | `jrules_dose` | flip rate | flips / n | Wilson-95 |
|---|---|---|---|---|
| **0.25 — NAMED, FUNDED HERE** | **0.25** | **23.65 %** | 368 / 1556 | 21.61 – 25.83 % |
| 0.5 | 0.5 | 30.46 % | 474 / 1556 | 28.23 – 32.80 % |
| 1.0 | 1.0 | 38.88 % | 605 / 1556 | 36.49 – 41.33 % |
| 2.0 | 2.0 | 46.47 % | 723 / 1556 | 44.00 – 48.95 % |

**Branches fired mechanically, in order:** `FINER-RUNG` — `f(1.0) = 38.88 %` is strictly above
the pre-committed 20 % trigger, so the pre-committed 0.25 rung had to be measured **before
anything could be funded** — then `FUND-SMALLEST`, which names the **smallest** dose clearing
the bar.

⇒ **0.25 is the ladder's FLOOR — the smallest dose the rule authorises — not a dose chosen
because it is gentle.** Read-rule §3.1 permits no rung below it (a `d0p125` is a *new*
calibration, not an extension). The named rung is **not** `marginal`: its Wilson-95 lower bound
(21.61 %) clears the 10 % bar outright.

⚠️ Every rung on this ladder — including the floor — expresses **harder** than either open-city
arm that lost: 23.65 % against the **10.09 %** that cost −53.8 elo, and dose 1.0's 38.88 %
against the **18.89 %** that cost −190.3 elo. Clearing the bar buys **resolvability, not
safety.**

## 3. The cell

Exactly **one** cell. `CALIB_READ_RULE.md` §3.2 explicitly declines DESIGN §8's two-dose
provision, and neither this document nor the readout may be quoted to justify a second.

| | `jrules_d0p25_deploy11008` |
|---|---|
| candidate | production champion leaf **+ `jrules` term**, `jrules_dose` **0.25**, `jrules_mask` **31** (`JR_ALL` = J1\|J2\|J5\|J6\|J8) |
| expected `cand_leaf_hash` | **`15948beccf3472d3`** |
| opponent | the **UNMODIFIED** production champion, `opp_leaf_hash` **`a36d2e15a3b3d71d`** |
| harness | `scripts/classical_search/eval_fair_puct.py --info fair --opponent fair-champion` (FAIR PIMC), via `menu_fair_cell.sh` |
| budget | **k8 × 1376 = 11008 on BOTH arms** — `--k-dets 8 --sims 1376` *and* `--opp-k-dets 8 --opp-sims 1376` |
| backend | `--backend rust`, **both sides** |
| rules | `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1` |
| endgame | `--exact-k 2`, shared by both arms |
| search knobs | `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits` |
| run flags | `--paired --shared-claim --no-results-csv`, `nice -n 19`, detached |
| **n** | **800 deck-paired = 400 decks × 2 seats**, CRN |
| band | **1.28e11**, fresh — claimed in `governance/BAND_REGISTRY.csv` in the same commit as this file |
| deck seeds | `128000000000 .. 128000000399` |
| out subdir | `jrules_d0p25_deploy11008` |
| **primary statistic** | **deck-paired margin in pts/deck, with its z.** Elo is **secondary**, reported, never promoted (CL-072: elo alone failed to resolve where the margin did) |

**Band freshness.** 1.25e11 and 1.26e11 are retired (they adjudicated the Joshua-bot tournament,
which is the run that *motivated* this design) and 1.27e11 is retired (it adjudicated CL-080).
All three are decision-influenced and therefore out of confirmatory use. 1.28e11 is untouched.

**The cell JSON.** The knobs reach the candidate arm via `--cand-leaf-json` +
`--allow-cand-curve-drift`. The drift flag is **not** a curve claim: the fair harness's
candidate-side gate asserts the candidate hash *equals* curve125's, which a modified leaf cannot
satisfy, and `_stamp_cand_leaf` requires the cell JSON to carry an explicit 8-entry finite
curve. The dose-0.25 cell JSON is therefore pre-registered here **by content**, at
`cells/jrules_d0p25_deploy_fixed_v1_vs_fairchamp11008.json`, as exactly:

```json
{"jrules_dose": 0.25, "v29_meeple_curve": [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]}
```

— i.e. **curve125 verbatim** (a no-op, proved by gate O0, not assumed) and **no
`jrules_mask` key**, so the mask holds its default 31 and a mask typo cannot silently ablate
rules. Any other content is a different cell and voids this pre-registration.

**Per-box launch gates still owed** (DESIGN §11, unchanged by this document and **not** waived
by it): **G3** — the `carc_rs` wheel rebuilt and `reconcile_leaf.py --configs jrules --corpus
golden` = 0 mismatches **on every box that plays a game** (cleared on the local box only as of
writing) — and **G4** — `chain_capability_probe.py --require jrules` PASS **on that box, under
the launcher env canon**. A stale wheel is fail-closed (`TypeError`), but a launcher that
swallowed it would produce a champion-vs-champion cell that reads as a beautiful, meaningless
null — and here it would read as *"the anchor's strategy is worth nothing"* rather than *"it
never ran"*.

## 4. PRE-STATED PRIOR — recorded before any number, and labelled as pre-stated

**The stated expectation is a LOSS.** Three grounds, all known now:

1. **The floor dose is hot.** 23.65 % flip is ~**2.3×** the 10.09 % open-city rung that cost
   **−53.8 elo** at this exact budget on this exact statistic (CL-080). The only anchor mapping
   flip rate to outcome that this program owns says a term expressing at ~10 % is quite capable
   of costing 50+ elo.
2. **The safety assumption already failed, in the unsafe direction.** DESIGN §6's depth-1 greedy
   proxy read 25.0 % at dose 1.0 and was *assumed* to be an upper bound on the search flip rate;
   the true search rate at dose 1.0 is 38.88 %, i.e. the proxy **understated** it by ~**1.6×**.
   The one prior we had about how gentle the doses were was wrong the dangerous way.
3. **Every hand-crafted leaf term this program has measured has failed to clear** — CL-055
   (Term R), CL-063 (F6 soft caps), CL-074, CL-078 (meeple scale axis), CL-079 (targeted denial:
   harmful at 2750, bounded-null at deploy), the farm-growth rows, and now **CL-080**, in which
   the *most externally endorsed* hand-crafted leaf term in the program's history (four
   independent strategy guides) became its **largest resolved negative**. Nothing about the
   J-rules bundle earns a softer prior than that; DESIGN §3.6's double-count rider argues the
   opposite, since that mechanism is about **staticness, not sign**.

**This prior is recorded before the number so that a loss cannot be retro-fitted as "expected"
and a win cannot be under-credited.** It is a prior, not a branch: it does not license reading
any branch differently, and it does not soften the §7 scope clause if the loss arrives.

**The value of this cell is that it makes the question answerable, not that it is likely to
win.** A powered negative converts *"the anchor's strategy loses on a greedy base"* (which says
nothing) into *"the anchor's articulated strategy, encoded as static leaf terms at equal depth,
is worth ≤ X pts/deck"* — which bounds the E4 lean's mechanism and points the search for it at
what he *cannot* articulate.

## 5. Read rules — pre-committed

**Primary: the deck-paired margin z. Elo is secondary and weaker.** House map:
`|z| ≥ 2.0` resolves with sign · `|z| < 2.0` is **no conviction** (§6 N3).

1. **Gates before numbers, always.** §6 **N0** is read from `manifest.json` *before* the summary
   file is opened. A cell that fails any wiring check is **UNREADABLE** — no number from it is
   quoted anywhere, including "for context".
2. **`|z| < 2` is NEVER "refuted".** No branch here licenses "killed", "dead", or "does nothing"
   under 2σ. The house has a measured ~50 % underpowered-kill error rate; this is the rule that
   pays it down.
3. **A null must state its bound in BOTH units** — the cell's **realized** 2σ resolution as
   *both* pts/deck *and* elo, computed from the realized `se`, never from a nominal power figure.
   (Nominal at n=800: se ≈ 0.45–0.7 pts/deck ⇒ 2σ ≈ ±0.9–1.4 pts/deck ≈ ±24.6 elo. The
   **realized** number is the one that gets written.)
4. **Winner's-curse paragraph on any positive.** This campaign has **four confirmed winner's-
   curse instances** (a lean that shrank or vanished on extension) against **one** that held. A
   first look is curse-calibrated to roughly **half** its face value until replicated on a fresh
   band. A single cell **never** promotes anything (§6 N2).
5. **No pooling.** Not with any 2750-instrument number (CL-079), not with the calibration (0
   games), not with the Joshua-bot tournament cells (a different candidate, a greedy base, retired
   bands), and not across bands at all.
6. **Cross-band contrasts get 1.8–2.2× σ inflation** (CL-068). Nothing here may be contrasted
   against a number from another band without that inflation.
7. **The flip rate is not a result.** 23.65 % says the pick changes, not that it improves. It is
   the reason this cell is readable at all, never evidence for either sign.

## 6. Branch map — evaluated in order

| # | branch | condition | reading — pre-committed |
|---|---|---|---|
| **N0** | **WIRING GATE — BLOCKS ALL READING** | any check below fails | Before any statistic is read, the run's `manifest.json` must show: `config.cand_leaf_hash` = **`15948beccf3472d3`** · `config.opp_leaf_hash` = **`a36d2e15a3b3d71d`** · `config.cand_leaf_cfg.jrules_dose` = **`0.25`** · **no `jrules_mask` key** in `cand_leaf_cfg` (absence ⇒ the default **31**) · **no `jrules_*` key** in `config.opp_leaf_cfg` · `k_dets` **8** and `sims_per_det` **1376** (`total_sims` 11008) on **BOTH** `config.champion` and `config.opponent` · `rules_profile.name` **`fixed_v1`**, `rules_profile.r9_env_ok` **true**, `leaf_env.CARCASSONNE_FIX_R9` **`"1"`** · `config.backend.requested` **`rust`** on **both** sides · a **single `variant_id`** · **800 records, 800 unique `(deck_seed, seat)` cells, 0 missing, 0 extra**. **Any failure ⇒ VOID: NO NUMBER IS READ**, and the cell is re-run on a **fresh** band or abandoned. ⚠️ **A moved candidate hash is NOT sufficient** — `_LEAF_HASH_EXCLUDE_IF_DEFAULT` drops a field only while it holds its default, so a `{dose 0.0, mask 27}` leaf hashes to `92ac0da996e1b37b` ≠ the champion and would pass a hash-moved check while running **champion-vs-champion**. The gate that proves the dose is live is the **resolved `jrules_dose` value in the manifest**. |
| **N1** | **REFUTED** | margin **z ≤ −2.0** | **The anchor's articulated strategy, encoded as static leaf terms at the smallest authorized dose, does not survive inside the champion's own search.** Mint claim **CL-081** at status **Refuted**. The `jrules` term stays **default-off permanently**, and the *"encode the anchor's strategy as static leaf terms"* route **closes**. ⚠️ Read §7 before writing a single word of this up — the scope of what a loss refutes is narrower than the sentence above sounds, and §7 is binding. ⚠️ Subject to downgrade by **N4** if the cell is not cost-neutral. |
| **N2** | **POSITIVE SIGNAL, NOT A PROMOTION** | margin **z ≥ +2.0** | **A live positive on a hand-crafted leaf term — the first this campaign.** It is **not** a promotion and **not** a champion change: `governance/PRODUCTION.yaml` is untouched on this branch as on every other. It **requires a fresh-band confirm at n = 800** before any `PRODUCTION.yaml` discussion may begin. The house has **4 confirmed winner's-curse instances**; a single cell does not promote. That confirm is **named here, not funded here** — funding it is Joshua's separate, documented decision and needs its own pre-registration and its own fresh band. Read rule 4 (curse-calibrate to ~half face value) applies to every sentence written about this branch. |
| **N3** | **NO CONVICTION** | **\|z\| < 2.0** | **Recorded as no-conviction at this dose**, with the sign, the lean, and the realized bound in **both** units (read rule 3). ⚠️ **There is no cheaper rung to retreat to**: `FUND-SMALLEST` named the **floor** of the authorized ladder, and `CALIB_READ_RULE.md` §3.1 permits no rung below 0.25 — a `d0p125` would be a **new calibration**, not an extension of this one. ⚠️ **No top-up branch is pre-registered.** Do **not** re-run at higher n without a **mechanism** argument. **CL-079 precedent is binding: more n on a dead axis is not evidence.** Extending this cell requires a new prereg, a fresh band, and Joshua's explicit funding decision. |
| **N4** | **COST CONFOUND** | measured `ms_ratio_cand_over_opp` | Benched **prediction: `ms_ratio` ≈ 1.12–1.14** (DESIGN §11 G7: the term costs ≈1.14× per rust leaf, and CL-080 showed the leaf multiplier transfers to wall-clock ≈1:1). **This cell is NOT cost-neutral**, unlike **both** CL-080 opencity arms (1.0110 / 1.0135). Pre-registered, read off `menu_block_summary` on the first block and confirmed at close-out: **if `ms_ratio` > 1.20**, branch **N1 downgrades from REFUTED to "loss, confounded by budget"** — time-vs-strategy is not separable at that point, no claim is minted at Refuted, and the write-up says so. **If `ms_ratio` ≤ 1.05**, record explicitly that **the cost-neutral reading is restored** and the loss (or gain) is not bought with time. Between 1.05 and 1.20 the reading stands as written with the measured ratio quoted alongside. |
| **N5** | **VALIDITY TRIGGER** | failed games **> 0.5 %** of n | **Stop and investigate BEFORE reading any statistic.** 0.5 % is the house reference. The **bounded-action-window crash family is known** and ran at **0.125 %** (1 game in 800) in the Joshua-bot confirm; **that rate is acceptable, a 4× rise is not.** A trigger firing does not automatically void the cell — it suspends the read until the failures are attributed, and only then does N0's completeness requirement decide VOID vs proceed. |

**Reported alongside on every branch (cross-checks, never verdicts):** W/D/L · elo ± 1σ · paired
margin + realized `se` · `ms_ratio_cand_over_opp` · sign agreement between elo and the margin ·
`n_paired_decks` · realized throughput and the worker count it was realized at · the failed-game
count and its family.

## 7. Scope of refutation — what a loss DOES and DOES NOT refute

**This section is the point of the document. It is binding on the write-up of branch N1.**

A loss refutes **"this strategy, as static leaf terms, at this dose, inside the champion's
search"**. It does **NOT** refute **"this strategy"**. Two independent reasons, both of which
must be stated wherever the result is:

1. **The J-rules are adaptive and contextual; a static leaf term cannot express that
   conditioning.** The anchor's own account is full of state-dependent reasoning the leaf has no
   access to — **bag counting** ("this requires planning 2–4 tiles in advance, so i look at
   remaining tiles"), **opponent meeple state** ("if i see he is out of meeple, i am more okay
   with leaving something juicy unclaimed"), and **phase-dependent farm surrender** ("i started
   to count the cities … and surrender a farm"). DESIGN §3.1 records that J2's planning clause
   was **deliberately not expressed** at all, and §3.0 records that three rules (J1, J2's steal,
   J6's road join) had to **drop the "he must already be there" predicate** to keep the leaf
   antisymmetric — so they now credit *holding a share* rather than *stealing*. **The encoding is
   strictly weaker than the strategy it is named after**, by construction and by disclosure.
   ⇒ A negative here bounds **the encoding**, and is evidence about the strategy only to the
   extent the encoding is faithful — which §3.0 and §3.1 say it is not, in named places.

2. **J1's negation already lost, so J1 is NOT vindicated by that failure — and nobody may read
   it that way.** J1 **credits** large open cities you hold. The `opencity` term **penalized**
   exactly the same object, and measured **−53.8 elo** (z −5.86) and **−190.3 elo** (z −19.38) at
   this same budget on this same harness (**CL-080**). The **sign is opposite; the mechanism is
   the same** — a *static* leaf term double-counting something the search already prices through
   its own closure schedule. The double-count argument is about **staticness, not sign**, so a
   static *bonus* on that object is exposed to it exactly as much as a static *penalty* was.
   ⇒ **"The guides' direction lost, therefore J1's direction wins" is a FORBIDDEN reading**, in
   both directions: CL-080 does not support J1, and a J1 loss does not resurrect open-city
   (whose own binding scope covers arm A at two doses only — not arm B, not arm C, not the
   asymmetric variant).

**Also NOT refuted by any branch of this cell**, and to be named as such in the write-up:
**J8** (fires on only 3 % of states, DESIGN §6 — a null on the bundle is not a null on J8) ·
the **per-rule mask ablations** (the mask is pinned at 31 throughout; every mask is a fresh
multiple comparison and a **new** calibration) · **J10f and J3's hard floor** (root filters,
DESIGN §3.5, deliberately deferred to a separate cell and **not built**) · the
**asymmetric / own-side-only variant** (`jrules_symmetric = False`, DESIGN §12 Q1 — a named,
unexercised option that tests **opponent modelling**, a different hypothesis, and needs its own
prereg and its own fresh band) · **J7** (answered by the tournament at `j7_weight` 0 > 1, +5.34,
z +3.71; zero code is the calibrated answer) · **J9** (tournament no-conviction, −2.14, z −1.47,
one encoding tested, defaults off) · and the **policy-prior surface (B)**, which this design
declined on the grounds that a root prior at 11008 sims very likely measures null for the wrong
reason (the measured washout: +82.8 elo / z 3.48 at sims 200 → +8.0 / z 0.34 at sims 800).

## 8. Honesty items — recorded before the run, not discovered after it

1. ⚠️ **Rust parity for this term rests on `reconcile_leaf.py` ALONE.**
   `tests/test_jrules_term.py` is **39 passed / 1 skipped**, and **the skip is STRUCTURAL, not
   staleness**: `test_rust_parity_spot_check` skips because `carc_rs` **exposes no direct leaf
   entry point** (no `leaf_value_float[_py]`) for the test to call. It will not become a pass on
   any rebuilt box. ⇒ **There is no second, independent Rust-parity check for this term.**
   `reconcile_leaf.py --configs jrules --corpus golden` (83 824 values compared, 0 mismatches,
   6 cells including a dose-0 moved-mask identity control) is the sole guard — including on
   DESIGN §12 Q5's **inferred** Rust root-enumeration mapping (`labels[i] == i`), which would
   break **silently** if `label_components_into` ever renumbered components. This promotes G3
   from a nicety to the single load-bearing parity gate, **per box**.
2. **The candidate arm runs a leaf the champion has never played with.** The caps/curve optima
   were tuned against the **intact** leaf (the 2026-05-15 lesson: a scored-heuristic change
   shifts hyperparameter optima). Nothing here re-sweeps them, and nothing here may claim the
   term was given its best configuration.
3. **The J-rules constants are frozen copies of `joshua_bot.PRESETS["current"]`**, pinned by
   `test_constants_match_joshua_bot`. This cell tests the interview **as selected by the
   tournament** (preset `current` > `early`, +5.81, z +3.68); it does not re-fit it, and a loss
   is not evidence that some *other* parameterization of the same rules would lose.
4. **The dose-0.25 rung was measured in a fresh output directory**, not as an added `--arm` over
   the calibration's directory as `CALIB_READ_RULE.md` §3.1 literally says — because the
   instrument's resume is **per-ply**, so a late-added arm would have rolled up as **0.00 %**, a
   silent null. **No rule text was edited after the fact**; the instrument now refuses that path,
   and `merge_calib_dirs.py` *proves* the two runs searched identical worlds by diffing the
   champion's own pick ply-by-ply (**1,556 / 1,556 identical**, `SystemExit` on any
   disagreement). The deviation is disclosed here so it rides with the result.
5. **`_JR_K0 = 72.0`** stands in for the bot's latched per-game `k0` because the leaf must be a
   pure function of `(state, cfg)`. Exact for a full game; it would drift if a cell ever started
   mid-game. This cell does not.
6. **J8 reads the margin at the LEAF, not at the decision root** (a potential has no root). That
   is the natural analogue, but it is a **semantic change** from the bot's own rule.

## 9. What this cell CANNOT say

1. **One dose, one mask, one predicate set.** `jrules_dose = 0.25`, `jrules_mask = 31`,
   antisymmetric. Nothing is priced for any other dose, any mask ablation, the own-side-only
   variant, or the deferred root filters.
2. **Expressiveness ≠ strength.** The 23.65 % flip rate is why the cell is readable, not
   evidence for either sign.
3. **Not poolable** — with the 2750 instrument (CL-079), with the tournament, with the
   calibration, or across bands.
4. **`fixed_v1` + R9 on both sides** ⇒ not comparable to walled-era elo and not comparable to the
   E4 app epoch's games.
5. **Nothing is deployable from this cell.** Even **N2** is information, not a promotion.
6. **Throughput figures are conditional on the worker count and the box**, which must be recorded
   with them; only the deck-paired statistic is first-order insensitive to them.

## 10. Standing constraints

`governance/PRODUCTION.yaml` untouched on **every** branch · no promotion on any branch · no
`results.csv` row and no `CLAIM_REGISTRY` row until close-out · **no adjudication by the
launching session** · band row written at claim time with `decision_influenced = not yet`,
flipped only at close-out · the six-touch close-out checklist (results.csv → DECISIONS index →
status banner on this doc → governance row flip → STATUS top block → roadmap line) followed in
one sitting, then `python3 scripts/doc_lint.py`.
