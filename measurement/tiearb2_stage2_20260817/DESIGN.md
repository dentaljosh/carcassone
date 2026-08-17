# STAGE 2 — PHASE B: THE DECK-PAIRED GAME CELL (DESIGN)

> **STATUS AT WRITING: COMMITTED BEFORE THE INSTRUMENT AND BEFORE ONE GAME IS
> PLAYED.** No rust arbitration knob exists, no runtime tie-detector exists, no
> positive control exists, no band is claimed, `summary.json` does not exist for any
> cell of this run. Git history proves the ordering and every run manifest carries
> this commit's hash. [READ_RULE.md](READ_RULE.md) is committed in the **same
> commit** and is fully mechanical.
>
> Phase A is CLOSED and PASSED → [PHASE_A.md](PHASE_A.md). Its result is the
> precondition for this file existing: `c_tier1_rust` = 0.178232 worker-s/playout
> (15.30× the pilot), so **`B_affordable` = 16** at `rho_wall` 0.6224 — the rung that
> captures is the rung that is affordable, and **the fallback ladder did not fire**.

## 0. Authorization and what it permits

Owner, 2026-08-17, verbatim: **"funded"** — against the `A-COSTLY` licensed step:
**ONE** Stage-2 pre-registration of a deck-paired GAME cell, which must solve cost on
its own terms and may not assume the `B*` = 2 arm. Cost is solved (Phase A). This is
that one prereg. `A-DEPLOYABLE`'s conditions **(a)–(d)** apply verbatim; (d) is
discharged by Phase A, (a)–(c) are discharged here.

### 0.1 Condition (c) — carried verbatim, mandatory, never a branch input

> **arm `C`** — over the **1050** positions where the arbiter changes the champion's
> pick in at least one fold: 511/1033 = **+0.495** with `arb[p] > 0`, exact two-sided
> binomial **p 0.756**; aggregate sign **+1**, per-position majority -1, mean over the
> pick-change positions +0.0414 ⇒ **NO CORROBORATION -- sign agreement is not
> distinguishable from chance**

### 0.2 Condition (b) — carried verbatim, and it is the reason this cell exists

> ⭐ **The arbiter and the pricing judge are both terminal-grounded.** They differ in
> policy (`RuleBasedPlayer` 1-ply argmax vs 100-sim clairvoyant PUCT) and are
> independent in the leaf, but they **share the property under test**. ⇒ **a positive
> here is evidence that terminal grounding at ties is worth points *as measured by a
> terminal-grounded ruler*, which is the estimand — it is NOT yet evidence of deploy
> elo.** This is why a pass licenses only a game-cell prereg, and why that prereg must
> be graded on games.

**This cell is that grading.** Everything Stage 1b measured was priced by a judge that
shares the property under test; nothing here does. The estimand changes from "worth
points under a terminal-grounded ruler" to **"wins games against the champion"**.

## 1. The two cells, and why the control is what condition (a) asks for

**Condition (a) requires a matched-wall-clock control arm.** The naive form — give the
champion extra sims worth the arbiter's added clock — is a *weak* control: it changes
the champion's search config, so it confounds "more sims" with "different config", and
it cannot be run under the inverted liveness gate (§4) that keeps the champion's
identity fixed. This design uses a **strictly sharper** control:

| cell | candidate | opponent | arbiter runs playouts? | selection rule at a tied ply |
|---|---|---|---|---|
| **`ARB`** | champion + arbiter, `B` = 16 | champion, unmodified | **yes**, `Ā × 16` per tied ply | **argmax** of the world-mean playout value |
| **`RND`** | champion + arbiter, `B` = 16 | champion, unmodified | **yes**, identical count, results **discarded** | a **seeded uniform draw** over the same arm set |

`RND` burns **the same wall clock, the same playouts, on the same worlds, at the same
plies, over the same arm set**. It differs from `ARB` in exactly one line: which arm the
argmax returns. It is therefore:

1. **a perfect wall-clock control** — condition (a), and tighter than a sims-matched
   champion, because the compute is not merely equal in magnitude, it is *the same
   compute*; and
2. **the deploy analogue of Stage 1b's `C-RND`** — it prices the "the champion's own
   tie-break is not arm-average" level that Stage 1b measured at `rnd` = −0.1270 and
   printed beside every number. **Any pick-perturbation effect, and any effect of
   spending clock at tied plies, appears in `RND` too.**

⇒ `M_arb − M_rnd` isolates **the mechanism**, net of clock and net of
pick-perturbation. It is the statistic condition (a) exists to make available, and it
is a conjunct of the top branch (READ_RULE §4), not a companion.

**Both cells run on the SAME fresh band and the SAME decks**, so the difference is
deck-paired and the deck draw largely cancels out of it.

⚠️ The N4 in-cell `ms_ratio` still applies to **both** cells independently. The
matched-clock control does not excuse a budget confound against the *opponent*; it
controls the confound between the two candidates.

## 2. The arbiter, specified at runtime

The deployed shape is the **selection half** of Stage 1b's arm `H`. Stage 1b's
cross-fit (select on 16 worlds, price on a disjoint 16) is a *measurement* device; a
deployed arbiter only selects. So `B` = 16 selection worlds, and the cost is
`Ā × 16 × c_tier1_rust` per tied ply, exactly the `rho_wall(16)` = 0.6224 that Phase A
priced.

**Trigger** (fires at most once per tile ply, on the candidate's own seat only):

1. phase == TILES, and the candidate is to move;
2. `n_legal ≥ 2`;
3. the **outer chain value** (tile + its best meeple continuation, the corpus quantity —
   `scripts/tiletie/chain_census.py`) is **exactly equal** (f64 equality, `eps = 0`)
   across at least the top two distinct actions.

**Arm set**, mirroring the corpus construction: the tied set → dedupe by **successor
board** → cap at **`J` = 4** by a *seeded draw* (never index truncation) → append the
champion's own pick if the cap excluded it.

**Worlds**: `B` = 16 CRN determinizations, seeds derived as
`sha256("tiearb2-deploy-v1" | state_digest | ply | j)`, so the same position reached in
replay reproduces the same worlds. **The same 16 worlds are shared by every arm** (that
is the CRN), exactly as Stage 1b.

**Value**: `tier1-greedy` playout to terminal (the Phase-A rust port, bit-identical to
the judge Stage 1b adjudicated), margin from the candidate's seat, mean over the 16
worlds. `ARB` takes the argmax; `RND` discards the values and draws an arm from the
seeded RNG.

### 2.1 Two runtime-vs-corpus mismatches, pre-registered because they are real

Named here so no read-out can present them as discoveries:

- **(i) The corpus predicate was evaluated on a REPLAYED board at the champion's seat.**
  At runtime it is evaluated inside a live search on the candidate's seat. The board
  distribution is the same population; the *evaluation context* is not identical.
- **(ii) The corpus `champ_picks` came from a FRESH search.** CL-070 established that
  **reseeding alone flips picks**. ⇒ the offline firing rate **estimates** the runtime
  rate; it does not equal it.

⇒ **The offline 22.96 tied tile plies/game (E4 census, n = 26) is a prior, not a
prediction.** The realized rate is measured in-cell and reported; §3 states what it may
and may not do to a branch.

## 3. The firing rate, and it is a witness — with one hard floor

`phi` = mean tied tile plies per game at which the arbiter actually fired, measured
in-cell from the candidate's own instrumentation, reported for both cells.

- **Reported always**, beside the offline prior 22.96 and the funnel behind it (65.98%
  exact-tie rate on tile plies; 40.4% deduped scoreable).
- **`phi` is NOT a branch input** except through one hard floor: **`G-FIRE`, a
  precondition — if `phi < 1.0` in either cell, the arbitration surface is effectively
  inert and the cell is `U-UNREADABLE`.** A cell that never fires grades a
  champion-vs-champion null wearing the shape of a real cell, which is precisely the
  J13 failure mode this design is built to refuse.
- A `phi` materially below the prior (say < 10) is **reported prominently** and shrinks
  the effect proportionally — the offline elo bound is *per tied ply* scaled by the
  rate, so a low `phi` makes a null less informative, not more. The read-out must say so.

## 4. The inverted liveness gate — the champion is untouched, the surface is proven live

The champion config itself does not move. What moves is a knob **beside** it.

- **`J1` — EQUALITY, not difference**: the candidate's resolved
  `cand_leaf_hash` must **equal** the champion's `a36d2e15a3b3d71d`. A *difference*
  here is an abort, not a finding. Same k8×1376 = 11,008, same exact-K 2, same
  `c_puct` 1.5, same `tau_p` 5.0.
- **`J4` — the resolved knob is in the manifest**: `config.cand_tiearb` resolves to a
  full dict (`enabled`, `B`, `J`, `mode` ∈ {`argmax`,`random`}, `salt`, `eps`) in
  `manifest.json`, so what ran is readable off disk and not inferred from a flag.
- **`J13` — a TWO-SIDED positive control, passed on THIS box before game 1, per host**
  (`PREFLIGHT_*_${HOST}_FIRST.json`). The arbitration surface must be shown to be
  **live**:
  - **positive side**: at a constructed tied ply, the arbiter **changes the pick**
    relative to the unmodified champion;
  - **negative side**: `root_leaf_value_bits` is **unchanged** — the arbiter must not
    perturb the champion's own evaluation anywhere.

  The J13 lesson, copied verbatim because it is why this gate exists: *"Without this a
  zeroed dose grades a perfect champion-vs-champion null wearing the shape of a real
  cell."*

**Rust-side, not a python wrapper.** The knob lives at the `pooled_q_argmax` root hook
(`rust/carc/carc-core/src/fair/mod.rs`), following surface-C's `root_allow` precedent
("default path byte-identical"). A python-side wrapper was **considered and rejected**:
it would leave the arbiter's cost out of `prefix_secs` and so **silently defeat the N4
cost trigger** — i.e. it would buy a favourable `ms_ratio` by not measuring the thing
being priced.

## 5. Cost — N4, and the field-name trap

`ms_ratio_cand_over_opp = champ_prefix_ms_per_move / rung_ms_per_move`, measured
**in-cell**, per cell. **N4 fires above 1.20**; ≤ 1.05 restores a cost-neutral reading.

⚠️ **The trap, confirmed at live lines 2361/2371/2389 of `eval_fair_puct.py`:
`champ_prefix_ms_per_move` IS THE CANDIDATE SIDE** in this harness (the opposite of
`eval_puct_priors`). Any read-out that swaps them inverts the cost verdict.

**Advance arithmetic, committed before the cell runs.** Phase A's
`rho_amortized(16)` = **0.1985** ⇒ the expected in-cell
`ms_ratio` ≈ **1.1985** at the offline firing rate — **just under the 1.20 bar, and this
design says so before the measurement rather than after.** Consequences, pre-registered:

- The N4 trigger is expected to be **close**. It is a **downgrade trigger, never a
  branch input** for the mechanism question, because `ARB` and `RND` are cost-matched to
  each other by construction — the *mechanism* statistic `M_arb − M_rnd` is immune to
  it. N4 governs only what may be said about `M_arb` **against the champion**.
- If `ms_ratio` exceeds 1.20 in either cell, the read-out **downgrades the against-champion
  reading to cost-confounded** and says so in the branch sentence. It does not void the
  mechanism contrast.
- `phi` below the prior lowers `ms_ratio` proportionally; the two move together and both
  are reported.

## 6. Power — the arithmetic, done before any game

`n` = **800 deck-paired** games per cell (both colours, same deck), on a fresh band.

- House figures: near wr = 0.5, unpaired 1σ ≈ 695·√(0.25/n); deck pairing ~halves the
  variance ⇒ **n = 800 paired ≈ ±8.5 elo (1σ)**, **±17 elo at 2σ**.
- The offline bound chain gives `arb_H` = **+18.09 elo, CI [+6.32, +30.04]**, with a
  ÷5.23 low-end bracket reading **+11.06**. Every caveat travels: the ×1.40 full-set
  extrapolation and the ÷3.2 chain cancel out of `F` but **not** out of an elo number,
  and `NON_ADDITIVITY = 3.2` is **n = 1** with a ±1.6× bracket, not a point.

⇒ **What this cell can and cannot do, stated before it runs:**

- It **can** convict the offline point estimate: +18 elo is ~2.1σ.
- It **cannot** exclude the low end. A null at n = 800 leaves **+11 elo (the ÷5.23
  bracket) comfortably inside the interval.** A null is therefore a **bounded null**,
  and the read-out must print the bound rather than claim the mechanism is dead.
- The **mechanism** contrast `M_arb − M_rnd` is deck-paired across two cells sharing
  decks, so its se is smaller than √2 × the single-cell se — but it is **not** as small
  as a within-cell paired contrast. It is reported with its own paired se, computed the
  same way, never assumed.

## 7. Execution

- Harness `scripts/classical_search/eval_fair_puct.py`,
  `--info fair --opponent fair-champion --backend rust --k-dets 8 --sims 1376
  --opp-k-dets 8 --opp-sims 1376 --exact-k 2 --paired --n 800 --shared-claim`,
  plus the new `--cand-tiearb-*` flags. Driver templated on
  `measurement/jrules_priors_20260814/run_deploy_jrules_priors.sh` + `preflight_surface_b.py`
  (gates J1–J13).
- Primary statistic `summary.json::paired_z` (`_paired_z` — per-deck seat-balanced
  margin). Extraction by `scripts/classical_search/menu_block_summary.py`, run **after**
  the wiring gates.
- **Fresh band `132000000000`**, claimed by `scripts/classical_search/claim_next_band.py`
  **immediately before game 1**, `decision_influenced=pending`. Band identity is
  load-bearing (CLAUDE.md cross-band humility): both cells share the band and the decks,
  and **within-band deck-paired contrasts are the robust class** — which is what both of
  this design's statistics are.
- Boxes: **laptop W22, local W30**. Same rust toolchain on both
  (`RUSTUP_TOOLCHAIN=1.96.0`); a new `carc_rs` wheel ⇒ **rebuild + positive control on
  EACH box**. Git bundle sync before the 2-box launch (a shallow bundle gives a
  parentless `code_rev` — use a full one). Clock-skew guard aborts above 60 s
  (claim-steal). Per-cell content-bearing `DONE_<cell>` / `FAILED_<cell>` markers, the
  90% VOID rule (exit 11), chain with `;` not `&&`.
- Share path is `/mnt/c/carc-shared` locally and `/mnt/carc-shared` inside an ssh.
  Analysis on the local box.

## 8. Threats — stated before the numbers

1. **Deploy washout is real and is the point.** Stage 1b's positive was measured by a
   terminal-grounded ruler on selected positions; games are neither. Memory
   `feedback_sims_washout_net_eval`: gains that read +82.8/z3.48 at low sims read
   +8/z0.34 at 4× sims. **This cell is allowed to wash out, and that is a result.**
2. **`phi` may be far from 22.96.** §2.1 (i) and (ii) both push it in unknown
   directions. §3 handles it: a floor as a precondition, a witness otherwise.
3. **The N4 bar is expected to be brushed** (§5, ≈1.1985 vs 1.20). Pre-registered as a
   downgrade of the against-champion reading only.
4. **n = 800 cannot exclude the low end** (§6). A null is bounded, not fatal.
5. **The `RND` control could itself be positive** — if merely spending clock at tied
   plies, or merely perturbing the pick, wins games. That would be a finding about the
   champion's tie-break, not about terminal grounding, and the branch table has a cell
   for it (`G-ANOMALY`).
6. **Cross-band humility does not apply within this run** — both cells share one band
   and one deck set. It *does* apply to any comparison of these elo numbers against
   figures from other bands, and no such comparison is a branch input.
7. **The champion's tie-break is not arm-average** (Stage 1b: `rnd` = −0.1270, z −2.59,
   and it **flipped sign** between corpora). `RND` measures the deploy analogue directly
   rather than assuming it is zero.

## 9. Governance

- **This cell plays games.** On a terminal branch it therefore writes: an
  `experiments/results.csv` row per cell, the `governance/BAND_REGISTRY.csv` claim
  (flipped from `pending` to the realized `decision_influenced`), and a claim id in
  `governance/CLAIM_REGISTRY.csv`.
- **`governance/PRODUCTION.yaml` is untouched on EVERY branch.** A pass licenses a
  production-flip **decision for the owner**; it never flips anything automatically.
- No branch re-reads, re-labels or re-adjudicates Stage 1 or Stage 1b. They stand as
  adjudicated; their read-rules are spent and their corpora burned.
- `docs/LEVER_INDEX.md` row 217 is flipped at close. `python3 scripts/doc_lint.py` clean.
- **Launch discipline: launch → verify → report → STOP.** The completion watch is the
  orchestrator's; the DONE-marker convention is written into the progress log and handed
  over explicitly.
