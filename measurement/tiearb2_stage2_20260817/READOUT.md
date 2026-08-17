# STAGE 2 — PHASE B READ-OUT: the deck-paired GAME cell

> Adjudicates `measurement/tiearb2_stage2_20260817/READ_RULE.md` mechanically. No owner call adjudicates any outcome.
>
> Text adjudicated: **READ_RULE.md §0 — §0.A-C (PRE-RUN AMENDMENT) commit 6c281f9e; §0.D (OWNER RULING, N4 downgrade waived) commit a81b8c72; §0.E (PRE-LAUNCH ACCEPTANCES: arbiter FAILS SOFT, G-FIRE binds on phi_effective; G-TOOL witness corrected) commit c36055a7; §0.F (G-PLY, the ply-granularity witness) commit ef07768c; §0.G (THE COST MODEL MISSED, NOT THE ARBITER) commit edd3deab; §0.H (ms_ratio NOT graded against the smoke) commit d39c8a03; §0.I (POST-HOC annotation + blindness disclosure) commit 369ac884** — a PRE-RUN amendment, applied before the band claim and before game 1. **No adjudicating bar moved.**

## ⚠️ DISCLOSURE — the post-run instrument fixes (the audit trail)

The FIRST adjudication of these cells fired U-UNREADABLE on THREE §3 preconditions: G-J1, G-BAND and G-TOOL. All three were INSTRUMENT defects. No bar was moved, no gate was relaxed, no branch condition changed, and §4 was not edited — the byte-equality proof over §4 is re-run and still passes.

⚠️ §4.3 mandates the full companion table on EVERY branch, including U-UNREADABLE, so running the first adjudication PRINTED THE STRENGTH STATISTICS. The orchestrating session therefore became NON-BLIND at fix time and did not touch the adjudicator. The session that wrote these fixes was BLIND: it read manifests, pre-flight witnesses and provenance keys only, never summary.json's strength fields, never paired_z, elo or any margin — and it re-adjudicated by reading `branch` and `failed_preconditions` out of READOUT.json without rendering the statistics. Every fix below is decidable from gate inputs alone.

### `G-J1`

- **Defect:** read `cand_leaf_hash` at manifest TOP LEVEL only; the witness is at `config.cand_leaf_hash` and was present and correct on both cells.
- **Fix:** read BOTH addresses and REPORT which resolved, exactly as G-J4 does — no hard-coded path was swapped for another hard-coded path.
- **Faithful-implementation justification:** A gate that fails to read the witness the committed sentence names is not implementing that sentence. The two manifest levels are split by HOW a key was written (`config=` at write_manifest vs `patch_manifest`'s top-level merge), not by what it means, so reading one level asks a plumbing question. ABSENT AT BOTH LEVELS STILL FAILS.

### `G-BAND`

- **Defect:** same class — `band_seed_start` / `seed_start` / `n` are under `config` on both cells; the independent record-derived deck-set check had already read TRUE.
- **Fix:** same both-level lookup, reporting which address resolved.
- **Faithful-implementation justification:** identical to G-J1; absent at both levels still fails, and a nested-but-WRONG band still fails.

### `G-TOOL`

- **Defect:** folded manifests and pre-flights into ONE build-id equality set. `carc_rs_build_id()` embeds `git rev-parse HEAD` AT CALL TIME, and BOTH sides call the SAME function, so the comparison answered 'did HEAD move between the pre-flight and the manifest write?' — not 'was it the same build?'.
- **⭐ Structural test:** Would this gate fail on EVERY HEALTHY RUN of this launcher? ANSWER: YES — recorded before any outcome was known. launch_both.sh does census -> full bundle sync -> wheel rebuild on each box -> detached launch, and contains NO pre-flight step, so HEAD moves between pre-flight and manifest on every run BY DESIGN. Unsatisfiable in practice: the same defect class as the pre-launch G-N deck floor.
- **Fix:** compare the CROSS-BOX proposition §3 actually states (manifests with each other, pre-flights with each other — the pair §0.E.2 declared authoritative), and report the pre-flight-vs-manifest delta as its OWN line with mechanical evidence, DISPOSITIVE IN ONE DIRECTION: a NON-EMPTY or UNRESOLVED wheel-relevant diff across the commit range VOIDS the run. Additionally witness 'did this box play the wheel its own pre-flight validated?' by SAME-BOX carc_rs_binary_sha, which is a stronger witness than the build id because it hashes the binary.
- **Faithful-implementation justification:** §3 is a cross-box proposition. Reading a time-varying repo-checkout stamp across two different moments as a build difference is a false positive by construction; removing that conjunct implements the committed sentence rather than relaxing it, and every comparison §0.E.2 declared authoritative is retained and still fail-closed.

The re-adjudicated branch is taken VERBATIM, whatever it is. U-UNREADABLE standing was and is a fully acceptable outcome; a NON-EMPTY wheel-relevant diff would have kept it, with no discussion.

For the record, NOT done here and NOT to be done under a live tree: launch_both.sh should regenerate the pre-flight AFTER the wheel rebuild so no pre-flight/manifest gap exists in future runs. Parked on the roadmap for a quiet window; no driver was edited.

### The pre-flight-vs-manifest delta — its own proposition, with evidence

- pre-flight commit(s) ['c48216460325'] · manifest commit(s) ['46537745023c'] · differs: True
- **command:** `git diff --name-only c48216460325..46537745023c -- rust/ src/ engine/ scripts/classical_search/`
- **output:** *(empty — no output)*
- **verdict:** EMPTY — no wheel-relevant path changed across the range, so the pre-flight describes what ran


## BRANCH: `G-CONFIRMED`

**⭐ TERMINAL-GROUNDED TIE ARBITRATION WINS GAMES AGAINST THE CHAMPION, AND IT IS THE MECHANISM RATHER THAN THE CLOCK.**

The candidate convicts at 2σ on a fresh band, its wall-clock-matched control does not, and the two are RESOLVED against each other at 2σ. This is the first deploy-elo evidence on this axis and the only reading that discharges DESIGN §12.1's caveat. LICENSES (does NOT do) exactly one thing: a production-flip DECISION for the owner. ⛔ It does not flip PRODUCTION.yaml, does not license a leaf term (CL-065 + two dead menus + the 38% reach bound stand), does not license an on-device deploy (rho_phone = 5.520 at B = 16 — the phone currency was never solved), and does not license a second cell.

## §4.3 (1) — both cells

| | ARB (argmax) | RND (random, wall-clock control) |
|---|---|---|
| n games completed | 800 | 800 |
| decks seat-balanced | 400 | 400 |
| n_paired (summary) | 400 | 400 |
| M (pts/game, paired) | +3.0700 | -4.4287 |
| paired_z ⭐ PRIMARY | +4.445 | -6.669 |
| elo | +23.92 | -60.09 |
| elo 1σ | 12.31 | 12.47 |
| winrate | 0.5344 | 0.4144 |
| winrate z | +1.94 | -4.84 |
| n_failed | 0 | 0 |
| failure_rate | 0.00000 | 0.00000 |
| elo 95% CI | [-0.21, +48.06] | [-84.53, -35.65] |
| seat balance (a_seat = CANDIDATE's seat) | {'a_seat_0': 400, 'a_seat_1': 400, 'balanced': True} | {'a_seat_0': 400, 'a_seat_1': 400, 'balanced': True} |
| n_common (decks in BOTH cells) | 400 | 400 |

Witness (never a branch input) — our own recomputation of each cell's paired z from the records: ARB +4.445, RND -6.669. `z_arb`/`z_rnd` in the branch are READ off `summary.json::paired_z`, never recomputed.

## §4.3 (2) — `D`, its paired se, `z_D`, and the `n` that resolves it

- **`D` = M_arb − M_rnd, deck-paired over n_common = 400 decks: +7.4988 pts/game**
- paired se(`D`) = 0.9332
- **`z_D` = +8.036**  (same convention as `eval_fair_puct._paired_z`)
- M_arb / M_rnd restricted to the common decks: +3.0700 / -4.4287; the naive difference of the two summaries is +7.4987 (a diagnostic — the branch uses the DECK-PAIRED `D`)
- **the `n` that would resolve `D` to 2σ at the realized dispersion: 25** (DECKS (a paired statistic; each deck is 2 games))
- **the `n` that would convict `z_arb` at 2σ: 81** (decks)

## §4.3 (3) — the firing rate `phi`, beside the offline prior

- `phi_arb` = 17.573 · `phi_rnd` = 17.865 tied tile plies/game
- ⭐ **`phi_effective` (the quantity `G-FIRE` binds on, §0.E.1 cond. 2) — ARB 17.573 · RND 17.864** = `phi × (1 − error_rate_on_fired)`; a ply whose arbitration errored reverted to the champion's pick and was NOT arbitrated
- offline prior **22.96** (E4 census, n = 26); funnel: 65.98% exact-tie rate on tile plies, 40.4% deduped scoreable
- `G-FIRE` floor 1.0 (a precondition, the ONLY way phi touches a branch)

**DESIGN §2.1's two runtime-vs-corpus mismatches, restated verbatim:**

> **(i) The corpus predicate was evaluated on a REPLAYED board at the champion's seat.**
> At runtime it is evaluated inside a live search on the candidate's seat. The board
> distribution is the same population; the *evaluation context* is not identical.

> **(ii) The corpus `champ_picks` came from a FRESH search.** CL-070 established that
> **reseeding alone flips picks**. ⇒ the offline firing rate **estimates** the runtime
> rate; it does not equal it.

> ⇒ **The offline 22.96 tied tile plies/game (E4 census, n = 26) is a prior, not a
> prediction.** The realized rate is measured in-cell and reported; §3 states what it may
> and may not do to a branch.

DESIGN §3: a phi materially below the prior (say < 10) shrinks the effect proportionally — the offline elo bound is PER TIED PLY scaled by the rate, so a low phi makes a null LESS informative, not more.

**Fail-soft arbiter errors — REPORT-ONLY, on every branch.** On a deep playout error the arbiter falls back to the champion's own pick and counts it, so the ply is un-arbitrated rather than lost:

- `ARB`: `tiearb_errors_total` 0 · `tiearb_error_rate_on_fired` 0.00000 · `phi` 17.573 → `phi_effective` 17.573 — no fail-soft arbiter errors
  - `tiearb_first_error`: none
- `RND`: `tiearb_errors_total` 1 · `tiearb_error_rate_on_fired` 0.00007 · `phi` 17.865 → `phi_effective` 17.864 — fail-soft errors present
  - `tiearb_first_error`: `All 4 legal actions fall outside the 25x25 window centered at (3, 4)`

§0.E.1 ACCEPTS the fail-soft behaviour: propagating would kill the GAME and the exclusion would be CANDIDATE-CORRELATED (the `capoff` pattern) — a biased exclusion is far worse than a diluted effect. The bias runs TOWARD THE CHAMPION, so a positive read is UNDERSTATED, and it is symmetric across ARB and RND by construction, so `D` is diluted but never biased. Never a branch input EXCEPT through G-FIRE's phi_effective floor (§0.E.1 cond. 2 and 4).

## §4.3 (4) — `ms_ratio` for both cells, with the field-name trap named

- `ms_ratio_arb` = 2.4242 · `ms_ratio_rnd` = 2.4163 (bar 1.2)
- ⭐ **PREDICTION vs REALIZED — DESIGN §5 predicted ≈ 1.1985 BEFORE the measurement; realized ARB 2.4242 (Δ +1.2257), RND 2.4163 (Δ +1.2178).** evidence about the COST MODEL, and its value does not depend on whether the bar is enforced — it is the only way a wrong cost model becomes visible. DESIGN §5 pre-registered ≈1.1985 before the measurement.
- **N4 FIRED: True** — but the §4.2 DOWNGRADE IS WAIVED (§0.D); the against-champion reading stands AT FACE VALUE
- waiver authorised by **READ_RULE.md §0.D (OWNER RULING), commit a81b8c72** — owner, verbatim: *"we can afford some wallclock during play, especially if its not every tile draw. dont let that be the constraint right now"*
- ARB `champ_prefix_ms_per_move` (CANDIDATE) 4383.6 / `rung_ms_per_move` (OPPONENT) 1808.2; RND 4458.5 / 1845.2

⚠️ THE FIELD-NAME TRAP: `champ_prefix_ms_per_move` IS THE CANDIDATE SIDE in `eval_fair_puct` (confirmed at live lines 2361/2371/2389), the opposite of `eval_puct_priors`. `ms_ratio = champ_prefix_ms_per_move / rung_ms_per_move` is candidate-over-opponent. A read-out that swaps them INVERTS the verdict.

§4.2: `ms_ratio` is a DOWNGRADE TRIGGER, never a branch input. It does NOT touch the mechanism contrast D / z_D: ARB and RND are cost-matched to each other by construction, so D is immune to a budget confound. DESIGN §5 predicts ms_ratio ≈ 1.1985 — just under the bar — and says so BEFORE the measurement, so a reading either side of 1.20 was anticipated and is not a surprise; ms_ratio ≤ 1.05 is a fully cost-neutral reading.

### ⭐ §0.G — THE COST MODEL MISSED, NOT THE ARBITER.

_READ_RULE §0.G, from the SMOKE — laptop W22, 22 games/cell, throwaway band 900000100000, production knobs. Band 132000000000 unclaimed and no strength number of any kind existed when this was recorded, so the framing cannot have been reconstructed after margins existed._

| quantity | DESIGN §5 predicted | realized (smoke) |
|---|---|---|
| `ms_ratio` (`ARB`) | **≈ 1.1985** | **≈ 2.42** |
| `ms_ratio` (`RND`) | **≈ 1.1985** | **≈ 2.33** |

**The decomposition — it EXONERATES the arbiter: the NUMERATOR model was right and the DENOMINATOR was a category error.**

- **Numerator — ACCURATE WITHIN 12% — the arbiter cost what Phase A said it would.** `Ā × B × c_tier1_rust = 3.0022 × 16 × 0.178232` = **8.561** worker-s per fired ply; realized **9.57** (**+11.8%**).
- **Denominator — A CATEGORY ERROR — the wrong CURRENCY.** DESIGN §5 divided by t_champ = 13.7552 s/move — a SEQUENTIAL, single-box, UNCONTENDED measurement, while the in-cell `ms_ratio` divides by the opponent's per-move wall under W-WAY CONTENTION, ≈ 1.7 s/move — ≈ 8× apart. DESIGN §5's sentence equating `rho_wall` with the in-cell `ms_ratio` is WITHDRAWN. They are not the same currency.
- **The reconciliation closes.** `1 + (9.57 × phi / 72) / 1.7` gives **2.33** at `phi` = 17.05 and **2.4** at `phi` = 17.95, against realized **2.42 / 2.33**. the cell-to-cell assignment inverts within noise at n = 22 games; the LEVEL is what reconciles, and it does. The residual after correcting the denominator is the +11.8% numerator error and the realized phi being 74–78% of the 22.96 prior — both already reported.

⇒ **THE COST MODEL MISSED, NOT THE ARBITER.** ⛔ No re-tuning of B, the trigger, or the playout is implied or permitted — §0.D's anti-gaming clause stands.

- No branch moves: `ms_ratio` was never a branch input (§4.2) and §0.D waived its consequence. ⭐ But the MEASUREMENT was always mandatory precisely so a wrong cost model would become visible, and it did — THIS IS THAT MECHANISM WORKING, NOT FAILING.
- ⚠️ Phase A's `rho_wall` is NOT invalidated. It is a correct statement in its own SEQUENTIAL currency, and B_affordable = 16 was graded on that currency against the N4 bar as the programme has always defined it. What is now known is that `rho_wall` and in-cell `ms_ratio` MUST NEVER AGAIN BE EQUATED, and any future design quoting one as a prediction of the other is repeating this error.
- ⚠️ DEPLOY-RELEVANT, AND IT MUST NOT BE BURIED: the honest realized figure for a deployed arbiter under contention is ≈ 2.3–2.4× the champion's per-move wall, NOT ≈ 1.2×. The owner ruling (§0.D) stands and governs this cell's READING — but the owner is entitled to know the number is ≈ 2.4×, not ≈ 1.2×, when the production-flip decision is put to him.
- `rho_phone` is untouched and still NOT SOLVED (5.520 at B = 16) — and it is a THIRD currency again, so it may NOT be inferred from either figure above.
- This is a COST-MODEL miss and must never be presented as an arbiter defect: the numerator — the arbiter's own cost — was right within 12%.


⚠️ THE §4.2 DOWNGRADE IS WAIVED FOR THIS CELL (READ_RULE §0.D, an OWNER RULING made BEFORE the band claim and BEFORE any game, with no ms_ratio and no statistic of any kind in existence — blind to every number it affects). G-CONFIRMED / G-DEPLOYS / G-CLOCK are read AT FACE VALUE against the champion whatever ms_ratio lands at. WAIVED: the consequence. NOT WAIVED: the measurement — ms_ratio is still measured and reported for both cells on every branch, with the field-name trap named, and DESIGN §5's prediction (≈1.1985) is still printed against the realized value, because that comparison is the only way a wrong cost model becomes visible and its value does not depend on whether the bar is enforced. NO BRANCH CONDITION MOVES: §4.2's committed text already calls ms_ratio 'a downgrade trigger, not a conjunct' and 'NEVER a branch input', so waiving it cannot change which branch fires. §4 is left BYTE-IDENTICAL by the amendment — the override lives in §0.D — so the instrument's old-vs-new byte-equality proof over §4 still holds and is re-run as evidence. ⛔ ANTI-GAMING (binding): permission to SPEND clock, never licence to reshape the arbiter to look cheaper — B stays 16 (and may not be expanded), the tie predicate is not narrowed, and no playout truncation for cost reasons. rho_phone is NOT reopened (5.520 at B = 16) and no branch licenses an on-device deploy.

## §4.3 (5) — every §3 gate with its realized value

| gate | PASS | realized |
|---|---|---|
| `G-J1` | PASS | {"expected_equal": "a36d2e15a3b3d71d", "observed": {"ARB": {"cand_leaf_hash": "a36d2e15a3b3d71d", "resolved_at": "config.cand_leaf_hash"}, "RND": {"cand_leaf_hash": "a36d2e15a3b3d71d", "resolved_at": "config.cand_leaf_hash"}}, "read_at": "top level, then config.* (see _manifest_get)", "semantics": "EQUALITY gate \u2014 a difference ABORTS the run; ABSENT at both levels also fails"} |
| `G-J4` | PASS | {"ARB": {"resolved_at": "cand_tiearb", "cand_tiearb": {"enabled": true, "B": 16, "J": 4, "mode": "argmax", "salt": "tiearb2-deploy-v1", "eps": 0.0}, "expected_mode": "argmax", "expected_B": 16, "expected_J": 4, "ok": true}, "RND": {"resolved_at": "cand_tiearb", "cand_tiearb": {"enabled": true, "B": 16, "J": 4, "mode": "random", "salt": "tiearb2-deploy-v1", "eps": 0.0}, "expected_mode": "random", "expected_B": 16, "expected_J": 4, "ok": true}} |
| `G-J13` | PASS | {"hosts": {"Doctor": {"all_preflight_pass": true, "pick_changed": true, "root_leaf_value_bits_unchanged": true, "first_on_host": true, "path": "measurement/tiearb2_stage2_20260817/verdicts/PREFLIGHT_Doctor_FIRST.json", "ok": true}, "laptop-wsl": {"all_preflight_pass": true, "pick_changed": true, "root_leaf_value_bits_unchanged": true, "first_on_host": true, "path": "measurement/tiearb2_stage2_20260817/verdicts/PREFLIGHT_laptop-wsl_FIRST.json", "ok": true}}, "expected_hosts": ["Doctor", "laptop-wsl"], "missing_hosts": [], "semantics": "TWO-SIDED: pick CHANGED and root_leaf_value_bits UNCHANGED,… |
| `G-FIRE` | PASS | {"phi_arb": 17.5725, "phi_rnd": 17.865, "error_rate_on_fired": {"ARB": 0.0, "RND": 6.996431819771916e-05}, "phi_effective": {"ARB": 17.5725, "RND": 17.863750087455397}, "binds_on": "phi_effective (AMENDED \u00a70.E.1 cond. 2)", "floor": 1.0, "prior": 22.96, "formula": "phi_effective = phi x (1 - error_rate_on_fired)"} |
| `G-BAND` | PASS | {"expected_band": 132000000000, "band_claim": {"band": 132000000000, "claimed_before_game_1": true, "raw": "132000000000\nTIE-ARBITRATION STAGE 2 PHASE B: two deck-paired cells on ONE band and ONE deck set -- ARB (arbiter mode=argmax, B=16, J=4, salt tiearb2-deploy-v1) and RND (identical playouts/worlds/plies/arm set, values DISCARDED, arm drawn by seeded RNG = the matched-wall-clock control of A-DEPLOYABLE condition (a)). Candidate = the production champion + the tie arbiter; opponent = the UNMODIFIED production champion. BOTH arms FAIR PIMC k8x1376=11008, exact-K 2, rust both sides. cand_lea… |
| `G-N` | PASS | {"n_common": 400, "n_common_floor": 320, "n_common_units": "DECKS (READ_RULE \u00a72)", "n_games": {"ARB": 800, "RND": 800}, "cell_games_floor": 640, "cell_games_planned": 800, "both_clauses_are_the_same_80pct_bar": "640 games IS 320 decks", "deck_clause_independently_binding": "two cells can each clear 640 games while overlapping on fewer than 320 COMMON decks \u2014 that weakens D and still voids", "read_rule_amendment": "READ_RULE.md \u00a70 \u2014 \u00a70.A-C (PRE-RUN AMENDMENT) commit 6c281f9e; \u00a70.D (OWNER RULING, N4 downgrade waived) commit a81b8c72; \u00a70.E (PRE-LAUNCH ACCEPTANCE… |
| `G-TOOL` | PASS | {"preflight_vs_manifest_delta": {"preflight_commits": ["c48216460325"], "manifest_commits": ["46537745023c"], "differs": true, "evidence": {"applicable": true, "empty": true, "command": "git diff --name-only c48216460325..46537745023c -- rust/ src/ engine/ scripts/classical_search/", "output": "", "reason": "EMPTY \u2014 no wheel-relevant path changed across the range, so the pre-flight describes what ran"}}, "stamps": {"ARB": {"rust_toolchain": "1.96.0", "carc_rs_build": "carc_rs-0.1.0+46537745023c+rustc1.96.0", "mixed_builds": false, "build_witness": "carc_rs_build (cargo version + commit[:1… |
| `G-STAT` | PASS | {"observed": {"z_arb": 4.445372594625194, "z_rnd": -6.668940989778436, "z_D": 8.035923731082935}, "nan_or_absent": []} |
| `G-PLY` | PASS | {"cells": {"ARB": {"tiearb_partial_argmax_total": 0, "from_records_cross_check": 0, "agrees_with_records": true, "ok": true, "why": "PASS \u2014 every argmax was taken over all B = 16 completed worlds"}, "RND": {"tiearb_partial_argmax_total": 0, "from_records_cross_check": 0, "agrees_with_records": true, "ok": true, "why": "PASS \u2014 every argmax was taken over all B = 16 completed worlds"}}, "witness": "summary.json::tiearb_partial_argmax_total (both cells)", "condition": "READ_RULE \u00a70.E.1 condition 1 (ply granularity), witnessed per \u00a70.F", "records_sum_is_a_cross_check_not_a_fall… |

**J13 two-sided witness, per host** (the arbiter must CHANGE THE PICK at a constructed tied ply AND leave `root_leaf_value_bits` UNCHANGED):

- `Doctor`: pick_changed=True, root_leaf_value_bits_unchanged=True, all_preflight_pass=True (measurement/tiearb2_stage2_20260817/verdicts/PREFLIGHT_Doctor_FIRST.json)
- `laptop-wsl`: pick_changed=True, root_leaf_value_bits_unchanged=True, all_preflight_pass=True (measurement/tiearb2_stage2_20260817/verdicts/PREFLIGHT_laptop-wsl_FIRST.json)

## §4.3 (6) — carried verbatim, on EVERY branch

**Condition (b) — Stage 1b DESIGN §12.1:**

> ⭐ **The arbiter and the pricing judge are both terminal-grounded.** They differ in
> policy (`RuleBasedPlayer` 1-ply argmax vs 100-sim clairvoyant PUCT) and are
> independent in the leaf, but they **share the property under test**. ⇒ **a positive
> here is evidence that terminal grounding at ties is worth points *as measured by a
> terminal-grounded ruler*, which is the estimand — it is NOT yet evidence of deploy
> elo.** This is why a pass licenses only a game-cell prereg, and why that prereg must
> be graded on games.

**Condition (c) — arm `C`'s NO CORROBORATION sign-check verdict:**

> **arm `C`** — over the **1050** positions where the arbiter changes the champion's
> pick in at least one fold: 511/1033 = **+0.495** with `arb[p] > 0`, exact two-sided
> binomial **p 0.756**; aggregate sign **+1**, per-position majority -1, mean over the
> pick-change positions +0.0414 ⇒ **NO CORROBORATION -- sign agreement is not
> distinguishable from chance**

## §4.3 (7) — the Phase-A cost facts that licensed this cell

- `c_tier1_rust` = 0.178232 worker-s/playout, 15.3× the pilot
- `rho_wall(16)` = 0.6224 · `rho_amortized(16)` = 0.1985
- **`rho_phone(16)` = 5.52 — NOT SOLVED.** NOT SOLVED — the phone currency was never brought under 1.20 above B = 2; Phase A stamped it *reported, unadjudicated*. NO BRANCH LICENSES AN ON-DEVICE DEPLOY.

## §4.3 (8) — the realized band, the deck range, the registry claim

- band `132000000000` · common deck range [132000000000, 132000000399] · registry `governance/BAND_REGISTRY.csv`
- claim artefact: `{"band": 132000000000, "claimed_before_game_1": true, "raw": "132000000000\nTIE-ARBITRATION STAGE 2 PHASE B: two deck-paired cells on ONE band and ONE deck set -- ARB (arbiter mode=argmax, B=16, J=4, salt tiearb2-deploy-v1) and RND (identical playouts/worlds/plies/arm set, values DISCARDED, arm drawn by seeded RNG = the matched-wall-clock control of A-DEPLOYABLE condition (a)). Candidate = the production champion + the tie arbiter; opponent = the UNMODIFIED production champion. BOTH arms FAIR PI`

## Power, and what this cell can and cannot do (DESIGN §6)

- n = 800 deck-paired ≈ ±8.5 elo (1σ), ±17.0 at 2σ
- offline bound chain: +18.09 elo CI [+6.32, +30.04], ÷5.23 low-end bracket +11.06
- realized 95% upper bound on `E_arb`: +48.06
- Stage 1b carried (NEVER a branch input): `arb_H` = +0.1441 pts/tied ply at z +3.01

## Partial-run status

- planned 800 games/cell; realized {'ARB': 800, 'RND': 800}; seat-balanced decks {'ARB': 400, 'RND': 400}; `n_common` 400 decks
- Every statistic is at the REALIZED n. G-N still voids below the committed thresholds — a partial run is read, then declared U-UNREADABLE if it is short. Nothing is extrapolated.

## Which text was adjudicated

- **READ_RULE.md §0 — §0.A-C (PRE-RUN AMENDMENT) commit 6c281f9e; §0.D (OWNER RULING, N4 downgrade waived) commit a81b8c72; §0.E (PRE-LAUNCH ACCEPTANCES: arbiter FAILS SOFT, G-FIRE binds on phi_effective; G-TOOL witness corrected) commit c36055a7; §0.F (G-PLY, the ply-granularity witness) commit ef07768c; §0.G (THE COST MODEL MISSED, NOT THE ARBITER) commit edd3deab; §0.H (ms_ratio NOT graded against the smoke) commit d39c8a03; §0.I (POST-HOC annotation + blindness disclosure) commit 369ac884**
- This read-out adjudicates the AMENDED read-rule: READ_RULE.md §0 (PRE-RUN AMENDMENT), commit 6c281f9e, applied BEFORE the band claim and BEFORE game 1, with no band claimed and no summary.json / manifest.json in existence. §0.B set G-N's deck floor to n_common >= 320 — the exact 80% analogue of the committed 640/800 games clause, because a paired n = 800 cell yields at most 400 decks (eval_fair_puct.py:3924), which made the original 600-deck floor unreachable on a PERFECTLY COMPLETE run. §0.C.1 named the +1.0 presentation split in §2; §0.C.2 corrected the knob's manifest location to top-level `cand_tiearb`. §0.D (OWNER RULING, commit a81b8c72, also before the band claim and before any game and blind to every number it affects) WAIVES §4.2's COST-CONFOUNDED downgrade for this cell — the consequence, never the measurement. ⚠️ NO ADJUDICATING BAR MOVED: +2.0, +1.0 and 1.20 are unchanged and every §4 branch condition is unchanged — §4 is left BYTE-IDENTICAL by BOTH amendments, which is why the byte-equality proof against b2faa238 still runs and now covers two of them.
- +1.0 is NOT an adjudicating bar (READ_RULE §2 as amended, §0.C.1): the two branches it separates — G-PRESENT and G-FLAT — are alike NON-LICENSING, so it selects a LABEL and the mandatory rider that travels with it, never a permission. The two bars that gate a licence remain +2.0 and 1.20.

## What no branch does (READ_RULE §5)

- No branch edits governance/PRODUCTION.yaml. A pass licenses a production-flip DECISION for the owner and nothing more.
- No branch licenses an on-device / phone deploy (rho_phone(16) = 5.520).
- No branch adds a leaf term, changes the production leaf, or trains anything.
- No branch re-reads, re-labels or re-adjudicates Stage 1, Stage 1b or Phase A.
- No branch licenses a second game cell. This read-rule is SPENT when the read-out lands, on every branch.

