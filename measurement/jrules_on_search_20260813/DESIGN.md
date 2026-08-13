# J-RULES ON SEARCH — design of record

> **STATUS: 🔨 BUILT-NOT-RUN 2026-08-13 — code only, DEFAULT-OFF.**
> **0 games · 0 evals · 0 calibration · no band claimed · no `results.csv` row · no
> claim minted · [`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml)
> untouched.** Nothing in this document is a strength statement, and no number below
> came from a game. The Rust mirror compiles but the `carc_rs` wheel has **not** been
> rebuilt on any box, so no cell can run yet (§11 gate G3).

Parent verdict: [`../joshuabot_20260812/CONFIRM_VERDICT.md`](../joshuabot_20260812/CONFIRM_VERDICT.md)
§"The design fix this run earns" · primary data:
[`../e4_games/ANCHOR_INTERVIEW_2026-08-12.md`](../e4_games/ANCHOR_INTERVIEW_2026-08-12.md) ·
scripted encoding: [`../joshuabot_20260812/SPEC.md`](../joshuabot_20260812/SPEC.md) ·
pattern cloned from [`../opencity_term_20260812/TERM_SPEC.md`](../opencity_term_20260812/TERM_SPEC.md)
+ its [`CALIB_READ_RULE.md`](../opencity_term_20260812/CALIB_READ_RULE.md) and
[`DEPLOY_PREREG.md`](../opencity_term_20260812/DEPLOY_PREREG.md).

---

## 1. Why this exists — the confound, stated precisely

The 2026-08-13 Joshua-bot tournament measured the owner's self-described strategy
(rules J1–J9) as a **scripted opponent** and it lost to the production champion by
**−16.0 pts/deck (z −24.4)** — *weaker than JCloisterZone's `LegacyAiPlayer`* at
−6.50. The verdict adjudicated the instrument question NO **with power**, and then said
exactly why that answer is not about the strategy:

> the bot applies J1–J9 on top of a **one-ply greedy** base; the champion runs
> 11008-sim PIMC + exact endgame … no amount of n fixes that.

So the tournament priced **encoding + shallow base**, not **strategy**. This build
removes the confound the only way it can be removed: put the J-rules on the champion's
own leaf, at the champion's own budget, so **the only difference between the two arms
is the strategy**.

⚠️ What this build does **not** claim: that this is likely to *win*. See §10.

---

## 2. Rule → surface mapping

Surfaces considered, per the brief: **(A) leaf modifier** — additive terms on the
champion's leaf, the house pattern of `denial_dose` / `opencity_dose`; **(B) policy
prior** — bias the root priors toward J-preferred moves. §4 explains why A is the
surface of record for every rule that fits it at all.

| # | interview quote (compressed) | class | surface | status |
|---|---|---|---|---|
| **J1** | "he tends to build large cities that probably wont close … i will attempt to sneak a meeple in, sometimes late" | value | **A — leaf** | ✅ built · `_jr_j1` |
| **J2c** | "if i see a farm is valuable, i will try to tie it or steal from him" + "i started to count the cities … and surrender a farm" | value | **A — leaf** | ✅ built (partial) · `_jr_j2` |
| **J2a** | "…this requires planning 2–4 tiles in advance, so i look at remaining tiles" | **planning** | **NEITHER** | ❌ **not expressible — §3.1** |
| **J3** | "i try to keep at least 1 meeple in my hand" | policy | **already in the champion leaf** | ⛔ nothing to add — §3.2 |
| **J4** | "if i see he is out of meeple, i am more okay with leaving something juicy unclaimed" | modulator | **A — leaf (multiplier)** | ✅ built · `_jr_urgency` |
| **J5 + J13** | "place it somewhere it doesn't add to anything unclaimed already worth more than a few points" + "if you suspect you have a high chance of claiming later … makes sense to build it up" | value | **A — leaf** | ✅ built · `_jr_unclaimed_value` × `_jr_claim_edge` |
| **J6** | "keep a big city and road as mine… i see his road is getting long and thats my signal to tie it up… generally less bullish on roads" | value | **A — leaf** | ✅ built · `_jr_j6_anchor`, `_jr_j6_road_join` |
| **J7** | "i hesistate if I've already surrendered the farm to him because he gets an easy 3 points there" | value | A — but **calibrated dose is 0** | ⛔ **answered — §3.3** |
| **J8** | "sometimes it takes 2 meeple to secure a city… you have to take chances" | policy → **rewritten as value** | **A — leaf** | ✅ built · `_jr_j8` |
| **J9** | "he is good at blocking my cloister completions. i'm more cautious about grabbing them now" | policy filter | B (root filter) | ⛔ **answered — §3.4** |
| **J10** | preset epoch (`early` vs `current`) | parameterization | — | ✅ `current` adopted (tournament, z +3.68) |
| **J10f** | early-farmer block (`k > 0.55·k0` ⇒ no FARMER claim) | policy filter | **B — root filter** | 🕳 **deferred, second cell — §3.5** |
| **J11 / J12** | champion behaviours he respects | — | — | n/a; J12 = denial, already killed (CL-079) |

Implementation: [`src/carcassonne_ai/flat_leaf.py`](../../src/carcassonne_ai/flat_leaf.py)
`flat_jrules_term` (+ the `_jr_*` helpers and the frozen `_JR_*` parameter block) ·
Rust mirror [`rust/carc/carc-core/src/leaf/mod.rs`](../../rust/carc/carc-core/src/leaf/mod.rs)
`jrules_term` · config `LeafConfig.jrules_dose` / `jrules_mask` · tests
[`tests/test_jrules_term.py`](../../tests/test_jrules_term.py).

### The single knob, and why there aren't 28

The bundle carries **two** LeafConfig fields — `jrules_dose` (the calibration axis;
`0.0` = off, `1.0` = the interview's own point magnitudes) and `jrules_mask` (a
5-bit ablation mask, `JR_J1|JR_J2|JR_J5|JR_J6|JR_J8`, default 31). Every per-rule
*parameter* is a **frozen constant** copied from `joshua_bot.PRESETS["current"]` —
the epoch the tournament selected at z +3.68. Making them LeafConfig fields would add
28 plumbing surfaces (env, `LeafConfigRs` kwargs, the leaf hash, the reconcile gate)
to re-tune an interview this experiment is supposed to *test*, not re-fit.
`test_constants_match_joshua_bot` pins all 27 against the bot so the two renderings
of the same interview cannot silently drift.

---

## 3. The rules we could NOT express, and the deviation we had to make

### 3.0 ⚠️ The largest fidelity deviation: three rules had to drop "he must already be there"

**The search evaluates the leaf from the MOVER's POV at every node and negates on
backup** (`rust/carc/carc-core/src/search/mod.rs`: `let mover = g.state.current_player`).
A leaf term that is not **antisymmetric** (`V(s,p) == −V(s,1−p)`) is therefore not a
coherent zero-sum value function: the value backed up at a node stops being the
negation of what the other seat sees. The house has one precedent for breaking it
(`denial_dose`, `opencity_symmetric=False`) and the open-city spec calls the
asymmetric form "an explicit ablation, not a default". We kept antisymmetry.

That forces a real change of meaning in three rules. The bot writes J1 as *"a JOIN
into HIS city"* — `cnt[me] ≥ 1 AND cnt[opp] ≥ 1 AND cnt[me] ≥ cnt[opp]`. In a signed
differential that predicate is **self-cancelling and carries no gradient at all**:

| state | `j1(me)` | `j1(opp)` | `T = j1(me) − j1(opp)` |
|---|---|---|---|
| he alone in his big open city | 0 (I have no meeple) | 0 (**I** have no meeple, so his "join" predicate fails too) | **0** |
| I sneak in → 1–1 tie | +B | +B | **0** |

⇒ the term would never pay for the join it exists to buy. **Dropping the
opponent-presence requirement** turns each into "credit for holding a *share* of the
object", and the same transition then reads `0 − B → B − B`, i.e. **+B for the
sneak** — the rule's intent, recovered. Applied to:

* **J1** (large open cities) — `test_j1_the_join_pays_exactly_the_bonus`
* **J2's realized steal** (valuable fields) — `test_j2_the_steal_pays_the_potential`
* **J6's road join** (long roads) — `test_j6_the_road_join_pays`

**The honest cost:** each now *also* credits holding such an object outright, not only
stealing one. For J1 that is J6's own anchor logic ("keep a big city as mine even if
there is no plan to close it") and is internally consistent with the interview — but it
is **diametrically opposed** to the pro-guide-endorsed `opencity_dose` term, which
*penalizes* exactly the same object. That tension is real and is one of the more
interesting things this cell could discriminate; it is not a bug, and it must not be
quietly resolved in either direction after the fact.

### 3.1 J2's "planning 2–4 tiles in advance" — deliberately NOT expressed

Two independent reasons, either sufficient:

1. **It needs information outside the leaf contract.** The bot's reach model reads the
   bag composition (`bag_farm_fraction`) and an entry-cell board scan; the leaf must
   stay a pure function of `(state, cfg)` that both the Python and the Rust
   decomposition can compute identically, and the `Decomp` has no farm-side analogue
   of `city_root_open_n`.
2. **It is what the search already does.** Multi-tile planning is the *definition* of an
   11008-sim PIMC search. Encoding it as a static leaf potential would double-count
   depth — which is precisely the confound this whole build exists to remove.

This is a finding, not a gap: **J2a is not a strategy the champion lacks; it is a
strategy the champion already executes, better.**

### 3.2 J3 (own-reserve floor) — already in the champion's leaf

"i try to keep at least 1 meeple in my hand so i can quickly collect on easy to close
vacant cities." The champion's leaf already carries `v29_meeple_curve` = curve125
(`-10, -5, -1.25, 0, 2.5, 3.75, 5, 6.25` by free-meeple count). Going from 1 free
meeple to 0 costs **5 points**; from 2 to 1, **3.75**. That *is* a reserve floor,
priced in points, in production, today. There is nothing to add.

The only part not expressed is the **hard** floor ("never place the last meeple except
on closures/majority swings"), which is a filter, not a value. Adding a hard filter on
top of a curve that already prices it softly is the failure mode that made J8 inert in
the tournament — so it is deferred with J10f (§3.5), not smuggled in.

### 3.3 J7 (close × opponent-farm-majority) — answered, and the answer is "no term"

The tournament measured `j7_weight` **0 > 1 at +5.34 pts/deck, z +3.71** — the single
best-powered axis result in the campaign. `j7_weight = 0` **is the absent term**
(J7's whole content is the extra charge). Carried forward per the brief: not
re-litigated, not implemented. Zero code is the calibrated answer.

### 3.4 J9 (cloister caution) — answered, no conviction, defaults OFF

Tournament: −2.14 pts/deck, z −1.47, point estimate negative ⇒ interview fidelity
default = OFF. ⚠️ Its 0.55 timing threshold was *borrowed* from J10's farm block, so
one encoding was tested, not the idea; that caveat rides forward unchanged and does
not license re-running it here.

### 3.5 J10f (early-farmer block) and J3's hard floor — deferred to a SECOND cell

Both are **hard root filters**: they delete moves the search ranks highest. That is a
categorically different intervention from a leaf potential — it cannot be dosed, it
interacts with the search's own move ordering, and mixing it into the primary contrast
would make a null unattributable between "the strategy is worthless" and "the filter
threw away good moves". If the primary cell is run and read, these are a clean
follow-on cell on their own band. **Not built.**

---

## 4. Why the leaf (A), not the policy prior (B)

1. **Type match.** The bot's own J-terms are already documented as *"potentials of the
   afterstate, in POINTS, signed from the bot's own seat"* — that is the leaf's exact
   type signature. Option B would require inventing a second encoding of rules that are
   natively value statements.
2. **A root prior at 11008 sims is nearly guaranteed to measure null for the wrong
   reason.** This project has measured the washout directly: the same policy change
   read **+82.8 elo (z 3.48) at sims 200 and +8.0 (z 0.34) at sims 800** — and the
   deploy budget is 11008. A prior intervention here would very likely produce a null
   that says nothing about the strategy, which is a *new* version of the confound we are
   trying to delete.
3. **The leaf shapes the whole tree, not just move ordering.** The J-rules are claims
   about which *positions* are good; applied at every node they steer the search's own
   evaluation, which is what "playing his strategy at the champion's depth" means.
4. **The leaf is the surface with a Rust implementation.** The candidate arm must run
   `--backend rust` to be affordable (§9). A Python-only candidate arm is ~9.4× slower
   per move and would roughly quintuple the cell's wall-clock — the reason the Rust
   mirror was built in the same sitting.

---

## 5. What was built, and the off-state proof status

| surface | change |
|---|---|
| `virtual_score_v2.LeafConfig` | `jrules_dose: float = 0.0`, `jrules_mask: int = 31`; env `CARCASSONNE_JRULES_DOSE` / `_MASK`; object-path `NotImplementedError` (fail loud, never a silent J-rule-free score) |
| `flat_leaf.py` | `flat_jrules_term` + 12 `_jr_*` helpers + the frozen `_JR_*` block; `_jrules_off()` capability gate on **both** cy fast paths; `score += dose * T` as a separate gated statement after open-city, before the curve, on both the int and float leaves |
| `heuristic_prior_mcts.leaf_score_float` | same gated add, same fixed order, calls the shared helper |
| `rust_agent.leaf_config_rs` | conditional kwargs — forwarded **only** when the dose is nonzero, so a stale `carc_rs` keeps serving every default-off config and raises `TypeError` on a set dose (**fail-closed loud**) |
| `carc-core/src/leaf/mod.rs` | `jrules_term` + `LeafConfig.jrules_{dose,mask}` + `LeafTerms.jrules_term`; wired in `leaf_terms_with`, the single arithmetic site all four leaf entry points funnel through |
| `carc-py/src/lib.rs` | the two knobs as trailing pyo3 kwargs |
| hash dialects (4 copies) | `jrules_*` added to `_LEAF_HASH_EXCLUDE_IF_DEFAULT` / `_FROZEN_HASH_DEFAULT_OFF` in `c5_leaf_override.py`, `alphabeta_agent.py`, `snapshot.py`, and the three test replicas |
| `reconcile_leaf.py` | `--configs jrules` — 6 cells incl. a dose-0-with-moved-mask identity control and two mask ablations (`j1only`, `noj5`) that localise a divergence to one rule |

### ⚠️ Sign convention — this bundle is ADDED

`denial_dose` and `opencity_dose` are penalties and the leaf **subtracts** them. The
J-rules bundle is a **bonus potential** (the interview says what to seek, not only what
to fear) and the leaf **adds** it: `score += jrules_dose * T`. Both Python and Rust use
`+=`. `test_leaf_moves_by_exactly_plus_dose_times_term` pins it.

### Off-state proof — status

| proof | status |
|---|---|
| champion `_leaf_hash(CHAMP) == a36d2e15a3b3d71d` | ✅ **recomputes unchanged** |
| frozen recipe `158f17ff76adaa02` / `6dfffd57051690f2` | ✅ **recompute unchanged** |
| dose 0.0 (with a MOVED mask) bit-identical on the int **and** `float.hex()` paths, 208-state random-play corpus × both seats | ✅ **0 mismatches** |
| cy fast path refused for a set dose; cy advertises no `SUPPORTS_JRULES` | ✅ |
| object path raises `NotImplementedError` | ✅ |
| `leaf_config_rs` fail-closed against a stale wheel | ✅ (observed: `TypeError: unexpected keyword argument 'jrules_dose'`) |
| **3-way / 2-leg reconcile vs Rust on the golden corpus** | ⛔ **NOT RUN — the `carc_rs` wheel is not rebuilt.** This is gate G3 (§11) and it is a launch blocker, exactly as it was for the open-city term. |

**38 passed, 2 skipped** in `tests/test_jrules_term.py` (40 tests). The 2 skips are the
Rust-parity pair, skipped *because* the installed wheel predates the term — i.e. the
skip is itself the fail-closed guard firing correctly. The 50 tests of
`test_opencity_term.py` + `test_denial_term.py` + `test_frozen_substrates.py` +
`test_v29_flat_curve.py` all still pass.

---

## 6. Expressiveness — measured, and one uncomfortable number

Per-rule firing rate and magnitude at dose 1.0, on a 208-state random-play corpus
(8 seeds, plies 15–140 every 5; `tests/test_jrules_term.py::_states`). **This is
expressiveness, not strength — a firing rule is not a good rule.**

| rule | fires | mean \|T\| | max \|T\| |
|---|---|---|---|
| J6 | 204/208 (98%) | 2.08 | 5.30 |
| J2 | 172/208 (83%) | 1.25 | 7.40 |
| J1 | 48/208 (23%) | 0.43 | 3.29 |
| J5 | 34/208 (16%) | 0.27 | 5.00 |
| **J8** | **6/208 (3%)** | 0.03 | 1.05 |
| bundle | 197/208 (95%) | **3.03** | 12.06 |

Two things follow, both pre-registered here rather than discovered later:

1. **The bundle is a LARGE intervention at dose 1.0** — mean \|T\| ≈ 3 points against a
   leaf whose entire closure-anticipation term is capped at 8. Dose 1.0 is not a gentle
   nudge; it is "the interview's magnitudes, taken literally".
2. **J8 is nearly inert even as a score term (3%).** The tournament found J8-as-a-filter-
   exemption *exactly* inert and `J8EX_INERT_FINDING.md` recommended making it a score
   term — we did, and it is still rare, because its predicate wants a ≥2-meeple lead on
   a feature whose swing both clears 12 points and exceeds the current margin.
   ⇒ **a null on the full bundle must NOT be read as a null on J8.**

An indicative dose readout (greedy leaf-argmax flip rate over 32 mid-game positions,
[`jr_dose_probe.py`](jr_dose_probe.py); mean champion top-2 leaf gap 0.478):
dose 0.1 → 6.2%, 0.25 → 12.5%, 0.5 → 18.8%, 1.0 → 25.0%. ⚠️ **This is a depth-1 proxy
and is NOT the house's flip-rate statistic** — see §7.

---

## 7. Calibration

### Carried forward, not re-litigated (brief's instruction; tournament §"Calibration")

| answer | strength | consequence here |
|---|---|---|
| `j7_weight` **0 > 1** (+5.34, z +3.71) | clears | J7 **not implemented** (§3.3) |
| preset **`current` > `early`** (+5.81, z +3.68) | clears | the frozen `_JR_*` block **is** `current` |
| **J8-as-encoded inert** (exactly 0) | exact | re-cast as a score term (§6 shows it is still rare) |
| **J9 no conviction** (−2.14, z −1.47) | no | **OFF** |

### The one open axis: `jrules_dose`

The house rule is [`CALIB_READ_RULE.md`](../opencity_term_20260812/CALIB_READ_RULE.md)
§2, and it is arithmetic, not taste: a champion makes ~70 decisions/game, so if a term
changes fraction `p` of them, a resolvable n=800 deploy cell needs a mean gain of
`1.32 / (70·p)` points **per changed decision**. **Below p ≈ 5% no dose can produce a
readable result at affordable n, however good the strategy is**; the funding bar used
for the open-city term was **10%**.

**Required pre-step (launch blocker, 0 games):** the E4-replay pick-flip instrument,
which re-runs the *production search* at every champion decision ply under CRN and
records whether the pick changes. The existing instrument
[`scripts/classical_search/opencity_e4_replay.py`](../../scripts/classical_search/opencity_e4_replay.py)
is open-city-specific (`--arm N:S:E:D`); a `jrules` sibling needs the arm tuple to be
`name:dose:mask`. **That extension is NOT built** — it is the one remaining code item.

⚠️ **Do not substitute the §6 greedy proxy for it.** The two are different statistics
and the house has measured the gap: open-city moved 21.9% of *leaf values* and denial's
arm A flipped only **4.45%** of *picks*. Deep search washes leaf perturbations out. The
greedy number is an upper bound at best.

**Pre-registered read-rule (write it down before any arm is read):** ladder
`{0.5, 1.0, 2.0}`; branch **FUND-SMALLEST** — fund the smallest dose whose search
pick-flip rate clears **10%** (Wilson-95 lower bound reported alongside). If **no** dose
≤ 2.0 clears, **do not inflate the dose to force expression**: report "the bundle does
not express at deploy depth" as the finding and stop. A dose above 2.0 is no longer
"the champion's leaf plus his strategy", it is a different evaluator.

---

## 8. Eval design

**Candidate** = the production champion with `jrules_dose` set (leaf hash ≠
`a36d2e15a3b3d71d`). **Opponent** = the **unmodified** production champion, leaf
`a36d2e15a3b3d71d`. Everything else is held identical — this is the entire point.

| | value |
|---|---|
| harness | `scripts/classical_search/eval_fair_puct.py` via `menu_fair_cell.sh` (fair PIMC) |
| budget | **k8 × 1376 = 11008 on BOTH arms** (`--k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376`) |
| backend | `rust` |
| rules | `fixed_v1` + `CARCASSONNE_FIX_R9=1` |
| endgame | `--exact-k 2`, shared by both arms |
| search knobs | `--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits` |
| n | **800 deck-paired = 400 decks × 2 seats** |
| band | a **fresh** band, registered in [`governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) before game 1 (1.25e11 and 1.26e11 are retired — they adjudicated the tournament) |
| **primary statistic** | **deck-paired margin z** (pts/deck). Win rate and elo are secondary and reported, never promoted |

**Per CL-079, a 2750-ablation screen is NOT a verdict and must not be run *instead* of
this cell.** Denial read margin z −2.293 at 2750 and z −0.127 at 11008 on the same
lever; the kill did not transfer in either direction and the two are not poolable. The
deploy budget is the budget we play at, so it is the budget that decides.

If two doses are funded they take **disjoint seed ranges on one band** (`+0..399`,
`+400..799`) and there is **no A−B statistic** — each cell's own margin vs the champion
is its own primary result. (Band 1.23e11 measured CRN across cells at 9.9% of contrast
variance: sharing decks buys almost nothing and creates a standing temptation to read an
unpowered difference.)

**Wiring gates read FROM THE MANIFEST before any strength number is opened** — clone the
open-city O0–O12 block verbatim, substituting `cand_leaf_cfg.jrules_dose` for
`opencity_dose` and adding **O4′**: `jrules_mask` is absent from the cell JSON (i.e. the
default 31), so a mask typo cannot silently ablate rules.

---

## 9. The priced, ready-to-launch command

Three cell JSONs are written, one per ladder rung. Each carries **curve125 verbatim**
alongside the knob because the fair harness's candidate-side gate requires an explicit
8-entry curve under `--allow-cand-curve-drift`; the curve is a **no-op** and gate O0
proves it. Expected `cand_leaf_hash`, computed under the launcher env canon (the
champion resolves to `a36d2e15a3b3d71d` in the same process, which is what proves the
env was not mangled):

| rung | cell JSON | expected `cand_leaf_hash` |
|---|---|---|
| dose 0.5 | [`cells/jrules_d0p5_…json`](cells/jrules_d0p5_deploy_fixed_v1_vs_fairchamp11008.json) | `46a7652670123027` |
| **dose 1.0 (default rung)** | [`cells/jrules_d1p0_…json`](cells/jrules_d1p0_deploy_fixed_v1_vs_fairchamp11008.json) | `a87fb6801b81d588` |
| dose 2.0 | [`cells/jrules_d2p0_…json`](cells/jrules_d2p0_deploy_fixed_v1_vs_fairchamp11008.json) | `56db6c2247dee55f` |

⚠️ Which rung is funded is decided by §7's read-rule **after** the flip-rate ladder is
read, not here. The command below names the dose-1.0 rung only as the concrete form.

```bash
# ── pre-flight, on the box that will run it (all four are launch blockers) ──
#  1. rebuild the wheel:   maturin build/develop for rust/carc/carc-py   (§11 G3)
#  2. reconcile:  .venv/bin/python scripts/rustport/reconcile_leaf.py \
#                    --configs jrules --corpus golden --workers 8      # 0 mismatches
#  3. capability probe (needs a `jrules` mode adding, §11 G4)
#  4. O0: _leaf_hash(cell json) != a36d2e15a3b3d71d, computed ON THAT BOX

BAND=<fresh band from governance/BAND_REGISTRY.csv>
DIR=$REPO/measurement/jrules_on_search_20260813
MENU_OUT_ROOT=/mnt/carc-shared/jrules_deploy_20260813 \
setsid nohup systemd-run --user --scope -p MemoryMax=8G \
  nice -n 19 bash $REPO/scripts/classical_search/menu_fair_cell.sh 22 laptop \
    --sub jrules_d1p0_deploy11008 --n 800 --band $BAND \
    --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 \
    --cand-leaf-json $DIR/cells/jrules_d1p0_deploy_fixed_v1_vs_fairchamp11008.json \
    --drift > $DIR/logs/cell_d1p0.log 2>&1 < /dev/null &
```

**Price.** House reference: a Joshua-bot-vs-champion game cost **84.82 s** (`BENCH.json`,
local box) with only *one* arm searching at 11008. Both arms searching ⇒ ≈**170 s/game**
⇒ n=800 ≈ **37.8 pool-hours**, i.e. ≈ **1.7 h at W22** on one box, ≈ **1.1 h** split
local W14 + laptop W22. **⚠️ Two multipliers on top, both unmeasured:**

* the J-rules term adds a per-leaf cost the other terms don't have — a full meeple
  attribution pass **plus** a scan over every city/road root **plus** a cloister pass over
  every placed tile (the J5 branch; `jrules_mask=27` removes it). The denial/open-city
  terms only walk placed meeples. **Bench one cell before sizing the fleet** — the
  Joshua-bot SPEC's own instruction, and `menu_block_summary`'s `ms_ratio` is the field
  to read (it was NULL on every fair-PIMC cell until 2026-08-12; verify it is populated).
* candidate-side leaf evals leave the Cython fast path by design; on the **rust** backend
  no Python leaf is computed at all, so this multiplier is 1.0 **only if** the wheel is
  actually rebuilt. Without G3 the run is either impossible (fail-closed `TypeError`) or,
  worse, silently champion-vs-champion.

---

## 10. Expectation management — state this before reading any number

**The honest prior is that this LOSES or ties.** The champion's search is strong, and
every hand-crafted leaf term this project has tried has come back null or harmful:
CL-055 (Term R, meeple-return liquidity), CL-063 (F6 soft caps), CL-074, CL-078,
CL-079 (targeted denial — harmful at 2750, bounded-null at deploy), and the farm-growth
rows. There is also a specific mechanism argument *against* the bundle: the interview's
own J12 records the champion already performing targeted denial **emergently, through
search**, and the denial leaf term measured harmful — the consistent read being that a
static leaf bonus for something the search already finds double-counts and distorts.
Several J-rules are in exactly that class.

**The value of this build is that it makes the question answerable, not that it is
likely to win.** A powered null here is worth having: it converts "the anchor's
strategy loses on a greedy base" (which says nothing) into "the anchor's articulated
strategy, at equal depth, is worth ≤ X pts/deck" — which bounds the E4 lean's mechanism
and points the search for it at what he *cannot* articulate.

---

## 11. Launch-blocking gates (none of these are done)

| # | gate | state |
|---|---|---|
| **G1** | worktree merged to the main tree at a quiet window | ⛔ |
| **G2** | `pytest tests/test_jrules_term.py` green **in the main tree** (the 2 Rust skips must become passes after G3; the 2 cy tests need the built `.so`) | partial — 38/40 here |
| **G3** | `carc_rs` wheel rebuilt on every box that will run a cell **and** `reconcile_leaf.py --configs jrules --corpus golden` = **0 mismatches** | ⛔ **not run** |
| **G4** | `chain_capability_probe.py --require jrules` mode added and PASSING on the run box (the "accepted and ignored" trap: a cell that quietly runs champion-vs-champion produces a beautiful, meaningless null) | ⛔ not built |
| **G5** | `jrules` arm added to the E4-replay flip instrument; ladder run; read-rule §7 applied | ⛔ not built |
| **G6** | fresh band registered in `governance/BAND_REGISTRY.csv` | ⛔ |
| **G7** | one benched cell for `ms_ratio` before fleet sizing | ⛔ |

---

## 12. Open design questions

1. **Is the symmetrized J1/J2/J6 still "his strategy"?** §3.0 changed three predicates
   from *steal-only* to *hold-a-share*. It preserves the gradient on the transitions he
   describes, but it also credits building the same objects — and J1 then points the
   opposite way from the pro-endorsed open-city term. An asymmetric variant
   (`denial_dose`-style, own-side-only) is the alternative; it is faithful to the words
   but makes the search's internal opponent model *also* play the J-rules, since the
   leaf is evaluated from the mover's POV at every node. **Worth an explicit owner
   decision before the cell is funded**; it is a different term, not a rung.
2. **Should J8 be dropped from the bundle?** At 3% firing it contributes almost nothing
   and dilutes attribution. Keeping it costs nothing; the argument for dropping it is
   that "the bundle" should mean rules that actually bite.
3. **Is `_JR_K0 = 72.0` the right stand-in for the bot's latched per-game `k0`?** The leaf
   must be a pure function of `(state, cfg)`, so `late_frac` uses a frozen constant. It is
   exact for a full game (verified: `k_remaining` at the init board is 72) and drifts only
   if a cell ever starts mid-game.
4. **J8 reads the margin at the LEAF, not at the root** (the bot reads the decision root).
   A potential has no root. This is the natural analogue but it is a semantic change: deep
   in the tree "the current margin" means something different.
5. **Rust root enumeration is the one inferred mapping.** `jr_unclaimed_value` needs the
   set of component roots, which the Rust `Decomp` does not store; the mirror recovers
   them as `labels[i] == i`. That is exact under today's `label_components_into`, but it
   would break **silently** if the labelling is ever changed to renumber components. G3's
   reconcile is what defends it — which is another reason G3 is a blocker, not a nicety.
6. **Does a dose that expresses at depth 1 still express at 11008 sims?** §7 exists because
   we do not know, and the honest failure mode is an unreadable null.
