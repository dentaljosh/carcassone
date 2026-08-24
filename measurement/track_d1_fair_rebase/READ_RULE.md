> ✅ **FROZEN 2026-08-24.** Prepared 2026-08-23 under
> [`../../docs/TRACK_D_PREP_2026-08-23.md`](../../docs/TRACK_D_PREP_2026-08-23.md) §3.4–3.5. This banner's
> commit is the blind commit (`BLIND_COMMIT` stamps its sha in the follow-up commit, DESIGN.md §0.5). No game
> has been played and no statistic of any kind exists as of this commit. Band changed
> `142000000000` → `145000000000` at freeze (DESIGN.md §0.5) — every reference below is updated to match.

# READ_RULE — fair-ruler re-baseline (the D1 compute item)

> **⚠️ BLIND ORDERING (once this pair is actually committed). This file is meant to be committed BEFORE the
> band is claimed, BEFORE game 1, and BEFORE any statistic of any kind exists.** Its git commit is the proof.
> The branch that fires is taken **VERBATIM**, whatever it is. No owner call adjudicates any outcome; owner
> authorization funds the cell and does not name its answer.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `track_d1_fair_rebase`.

---

## §1 — THE STATISTICS, NAMED BEFORE THEY EXIST

All in **points/game of final-score margin, candidate-minus-rung, deck-paired**, the
`eval_fair_puct._paired_z` convention.

```
PRIMARY  (E2, the ROBUST class — within-band, deck-paired):
  Δ1   = R_1600  − R_800          (pure budget, k4 fixed)
  Δ2   = R_2752  − R_1600         (pure budget, k4 fixed)
  Δ3   = R_5504  − R_2752         (pure budget, k4 fixed)
  Δ4   = R_11008 − R_5504         (⚠️ budget × ALLOCATION, k4→k8 — DESIGN §3.2)
  SPAN = R_11008 − R_800          (the ruler's total usable dynamic range)
  each computed over the n_common decks present in ALL FIVE cells
  se(·)  = from the REALIZED paired per-deck differences, NOT assumed
           (DESIGN §4.2 pre-registers the EXPECTATION, se = 0.885 pts)
  z(·)   = statistic / se_realized

DELIVERABLE (E1):
  R_i    = cell i's deck-paired mean margin vs HeuristicMCTS(h800, c=3.0), i ∈ {800,1600,2752,5504,11008}
           reported with se, z, 95% CI, winrate, and elo ± 1σ

SECONDARY (E3, the COARSE cross-era screen — 3 rungs only):
  D_2752    = R_2752   − 8.6425    (vs fair_ruler_rebase_2752,      G2)
  D_5504    = R_5504   − 10.7825   (vs fair_ruler_rebase_5504,      G2)
  D_11008   = R_11008  − 9.7700    (vs fair_ruler_k8x1376_11008,    G2)
  se_eff(D) = 2 × sqrt( se(R_i)² + se(R_i^G2)² )     ⚠️ CL-068 ×2 CROSS-BAND/CROSS-ERA TAX, MANDATORY
  z_eff(D)  = D / se_eff(D)
  ⛔ NO D EXISTS AT THE 800 AND 1600 RUNGS — no same-allocation post-fix comparator exists in the repo
    (DESIGN §2). Those rungs produce a NEW ABSOLUTE and the readout must say so, not silently compare
    them to G1's leaky k8×{100,200} readings.  [ruled 2026-08-23, DESIGN §0.2 Q4]

ATTRIBUTION (E4, owner-funded 2026-08-23 — DESCRIPTIVE-PLUS-Z, NEVER A BRANCH INPUT TO §4):
  A     = M_C2752(fixed_v1 + R9)  −  M_W2752(walled, R9 OFF)
          deck-paired over n_common(C,W) decks; SAME band, SAME 400 decks, SAME code rev,
          SAME backend, SAME candidate leaf, SAME frozen h800 rung — only rules_profile differs
  se(A) = from the REALIZED paired per-deck differences
          (DESIGN §4.2 pre-registers the EXPECTATION, se = 0.885 pts — the WITHIN-BAND form)
  z_A   = A / se(A)
  ⭐ NO CL-068 TAX ON A. It is a within-band, same-code, deck-paired contrast between two cells of
    THIS run — the robust class, exactly like a spacing. That is why it was worth 17 core-h.
  RESIDUAL = D_2752 − A   (band ⊕ n ⊕ code drift, reported with the ×2-inflated se it inherits;
    ⛔ it is a LEFTOVER, never presented as an estimate of the band effect)
```

⚠️ Every `z` is READ off the analyzer's computed value; a **from-scratch recomputation from the raw per-game
records is printed alongside it**. Disagreement beyond floating-point tolerance is `U-UNREADABLE`. The
recomputation is a WITNESS, never a branch input.

---

## §2 — UNITS

Primary unit: **points/game, candidate-minus-rung, deck-paired.** Elo is a derived DISPLAY quantity, converted
via the realized scale (DESIGN §4.5 pre-registers **13.7 elo/pt**; the readout recomputes it from this run's own
records and prints both). **No bar in this file is ever set in elo.** `n` is in **DECKS** throughout (400 decks
= 800 games per cell) except where a games-count is named explicitly.

---

## §3 — PRECONDITIONS (every one must PASS, else `U-UNREADABLE`)

Fail-closed. **ABSENT IS FAIL.** Each is read at the manifest top level, then at `config.*`, and the adjudicator
reports which address resolved it (the house `G-BAND`/`G-J1` fix precedent).

⚠️ **TWO GROUPS, WITH A ONE-WAY DEPENDENCY, fixed before game 1:**
**§3A** gates the LADDER (E1/E2/E3) — a FAIL there fires `U-UNREADABLE` and voids everything, E4 included.
**§3B** gates the ATTRIBUTION cell (E4) — a FAIL there voids **the attribution read ALONE**; the ladder branch
in §4 is computed and reported exactly as if the attribution cell had never been funded. This asymmetry is
deliberate: a bundled-on extra cell must not be able to put the funded deliverable at risk.

### §3A — LADDER gates (the five `fixed_v1` cells)

⚠️ "ALL FIVE" below means the five ladder cells. **W2752's equivalents are enforced transitively by `GW-PAIR`**
(§3B), which requires every `config` key except `rules_profile` to be identical to C2752.

| id | the adjudicator VERIFIES… | VOIDS on |
|---|---|---|
| `G-BAND` | every cell's `config.seed_start == 145000000000`, `config.n_decks == 400`, `config.seatings_per_deck == 2` | any mismatch |
| `G-DECKS` | the record-derived deck sets are IDENTICAL across all five cells; `n_common == 400` | any mismatch |
| `G-SINGLEVAR` | the five `config` blocks differ ONLY in `champion.k_dets`, `champion.sims_per_det`, `champion.total_sims`, the output path, and `claim_host`. **`code_rev`, `backend.code_rev` and `backend.carc_rs_build` are explicitly IN the must-not-differ set** | any other differing key |
| `G-REV` | all five manifests carry the SAME `code_rev`, equal to the launcher's `PINNED_SRC_REV`; and the launcher's `SRC_CLEAN.jsonl` records `src/ engine/ scripts/` CLEAN at every cell boundary | any mismatch, or any recorded dirty boundary |
| `G-BLIND` | the `BLIND_COMMIT` file holds a 40-hex sha; that sha is an ancestor of HEAD; and it is the commit that introduced this pair's FROZEN banner | placeholder, non-ancestor, or absent |
| `G-LEAF` | `config.cand_leaf_hash == "a36d2e15a3b3d71d"` in ALL FIVE, and `config.rung.leaf_hash == "42af12fce22e1a0f"` in ALL FIVE and identical across them | mismatch or absence |
| `G-RULES` | `rules_profile.name == "fixed_v1"` AND `rules_profile.r9_env_ok == true` in ALL FIVE | anything else |
| `G-BACKEND` | **per leg**: `config.backend.name == "rust"`, `config.backend.requested == "rust"`, `"candidate" ∈ config.backend.converted_sides`, `mixed_builds == false`. **Across legs**: `carc_rs_version`, `carc_rs_binary_sha`, `tile_data_semantic_digest` identical | any leg not rust-resolved; any cross-leg build mismatch |
| `G-RUNG` | ALL FIVE: `config.rung.agent == "HeuristicMCTS"`, `config.rung.c == 3.0`, `config.rung.sims == 800` | any deviation |
| `G-BUDGET` | cell-wise `(k_dets, sims_per_det, total_sims)` == (4,200,800) / (4,400,1600) / (4,688,2752) / (4,1376,5504) / (8,1376,11008), and the product identity holds in each | any deviation |
| `G-TIEARB` | `config.cand_tiearb.enabled == false` in ALL FIVE | any cell with the arbiter armed |
| `G-EXACT` | `config.endgame.exact_k == 2`, `mode == "marginalized"`, `shared_by_both_arms == true`, in ALL FIVE | any deviation |
| `G-N` | 800 games scored in EACH cell; `n_failed == 0` (a nonzero rate **< 2%** is REPORTED, not silently absorbed, and does not by itself void — the b32v64 precedent's 0.100% rust panic class) | short of 800 completed games; or failure rate ≥ 2% |
| `G-SAT-END` | endpoint cells A800 and E11008 each have candidate winrate vs h800 inside `[0.50, 0.90]` | outside — `SPAN` would be a rail reading |

### §3B — ATTRIBUTION gates (cell W2752 only; a FAIL voids E4 alone, never the ladder)

| id | the adjudicator VERIFIES… | VOIDS **E4 only** on |
|---|---|---|
| `GW-RULES` | W2752's `rules_profile.name == "walled"` AND `rules_profile.r9_env_ok == true` — ⚠️⚠️ **for `walled` this means `r9_env_observed == FALSE`; the expectation is INVERTED relative to §3A's `G-RULES`** (DESIGN §3.6; the standing "walled expects R9 OFF" trap) | anything else — in particular a `walled` artifact with `r9_env_observed == true`, which is a launcher that exported R9 at file scope and forgot to unset it for this cell |
| `GW-PAIR` | W2752's and C2752's `config` blocks differ in **exactly** `rules_profile`, the output path, and `claim_host` — every other key identical, **`code_rev` included** | any other differing key; in particular any difference in `cand_leaf_hash`, `rung.*`, `backend.*`, `champion.*`, `endgame.*`, `cand_tiearb.*` |
| `GW-DECKS` | W2752's record-derived deck set equals C2752's; `n_common(C,W) == 400` | any mismatch |
| `GW-N` | 800 games scored in W2752; `n_failed == 0` (same <2% tolerance as `G-N`) | short of 800 completed games; or failure rate ≥ 2% |
| `GW-SAT` | W2752's candidate winrate vs h800 inside `[0.50, 0.90]` | outside — `A` would be a difference of two rail readings |

**WITNESSES — printed on every branch, never voiding:** `G-SAT-MID` (winrates of B1600/C2752/D5504, flagged if
outside `[0.50, 0.90]`), `W-TIMING` (all six `rung_ms_per_move` within ±25% of each other), `W-COST` (realized
s/game per cell vs DESIGN §6's model), `W-SCALE` (realized elo/pt), `W-GAMELEN` (mean moves/game, C2752 vs
W2752 — where the `centered18`+`redraw` rules change shows up).

### §3.1 — the structural test, applied to every gate, BEFORE any outcome is known

*Would this gate fail on every healthy run of this launcher?*

- `G-SINGLEVAR` / `G-BUDGET`: structural — all five argv are built by extending ONE shared `COMMON` array from
  ONE budget table, so the single-axis property cannot fail clerically. ⚠️ **D2 made exactly this argument and
  still failed `G-SINGLEVAR`** — because the argument covers the ARGV and *not the tree moving underneath the
  launcher between sequential cells*. That path is now covered separately by `G-REV`.
- `G-REV`: enforced by the launcher's pre-flight (refuse on a dirty `src/ engine/ scripts/`) **and** by an
  inter-cell re-assertion that aborts the sequence rather than producing a mixed-rev ladder. It cannot fail on a
  healthy run; it fails exactly on the D2 failure mode.
  ⚠️ It deliberately does **NOT** require a non-`-dirty` `code_rev`: every manifest in this repo's history
  carries `-dirty` because `measurement/` artifacts are always modified. A gate demanding a clean whole tree
  would be unsatisfiable. It requires a clean **source** tree and an identical rev.
- `G-BLIND`: satisfiable **only because it reads the launcher artifact and git, never the manifest.**
  `eval_fair_puct.py` has **no `BLIND_COMMIT` stamping path at any address** — D2's manifest-addressed
  `BLIND_COMMIT` sub-clause could not have passed on any healthy run of any launcher, and that is precisely the
  §3.1 miss this bullet exists to not repeat.
  **Forward-compatible, and satisfiable in both worlds:** the launcher probes the harness at `PINNED_SRC_REV`
  for a `--stamp-key`-style manifest stamping path. If it exists the launcher passes it and `G-BLIND` gains an
  **additive** clause (the manifest's stamped value must equal the file's sha); if it does not, the artifact +
  ancestry check stands alone. `BLIND_PROOF.json` records `blind_stamp_mode` as `"manifest"` or `"artifact"`,
  so the readout states which form actually applied rather than leaving it inferred.
- `G-LEAF` / `G-RULES` / `G-BACKEND` / `G-RUNG` / `G-TIEARB` / `G-EXACT`: all are written by
  `eval_fair_puct.py`'s own manifest logic, and **each is asserted against a REAL record by the DESIGN §9 pilot
  before the band is spent.** D2's `G-LEAF` and `G-RULES` failures were both invisible to a pilot that only
  checked timing; this pilot checks the manifest fields themselves.
- `GW-RULES` **gets the test explicitly, because its expectation is INVERTED** and an inverted gate is exactly
  the class a careless reader calls unsatisfiable. `walled` carries `r9_env_expected = False`, so
  `r9_env_ok == true` on a `walled` artifact **requires R9 to be OFF in that process.** The launcher runs W2752
  under `env -u CARCASSONNE_FIX_R9` and the DESIGN §9 pilot's **`walled` arm** proves the inversion on a real
  record ~2 minutes in, before the band is spent. Would it fail on a healthy run of THIS launcher? **NO** — but
  it would fail on a launcher that only exported R9 at file scope, which is the whole reason it is gated.
- `G-N`'s 2% tolerance matches the campaign's own precedent, not an invented number.
- `G-SAT-END`: G2's realized winrates at these budgets were 0.685 (2752) and ~0.67 (11008); G1's at 800 was
  0.53. The interval `[0.50, 0.90]` contains every historical reading with margin at both ends.

**Answer for every gate: NO — none fails on a healthy run.**

---

## §4 — THE BRANCHES

Read **in order**. The FIRST whose condition holds is the branch, taken verbatim.

⛔ **THE ATTRIBUTION STATISTIC `A` IS NOT AN INPUT TO ANY CONDITION BELOW.** Owner condition, 2026-08-23,
carried verbatim: attribution is **descriptive-plus-z, never a branch input to the `FR-*` table.** The branch
that fires is identical whether the attribution cell ran clean, ran dirty, or was never funded — mechanically
so: no `FR-*` condition below references `A`, `z_A`, `W2752`, or any §3B gate.

**⚠️ No branch condition in this table is a dispersion-conditional restatement of another.** Each ladder branch
is keyed on `z_SPAN` (one bar, one statistic) plus, for the bent branch, a bar on a *different* statistic
(Δ₁…Δ₃). There is no branch carrying both a z-bar and a magnitude-bar on the same statistic — so the
`D2-COARSE`/`D2-COMPRESSED` arithmetic-coincidence class that D2 had to name at freeze time **is absent here by
construction.** Recorded before game 1 so a reader can check the claim rather than take it.

### `FR-RESCALED` — the ruler re-bases, and it is a ruler
**Condition:** all §3 gates PASS **AND** `z_SPAN ≥ 2.0` **AND** no pure-budget spacing Δ₁, Δ₂, Δ₃ has
`z ≤ −2.0`.

**Says:** the fair sub-ladder, re-measured on the production instrument (rust + `fixed_v1` + R9), resolves its
own dynamic range and is monotone across its pure-budget rungs. The five `R_i` are the ruler of record's
**absolute readings on the instrument production actually runs.**

**Licenses exactly this:** quoting `R_i` as the fair ladder's absolute readings for `fixed_v1`+rust
measurements taken from here on; and the CL-046 amendment in §5.1.

**Does NOT license:** any re-rating of the champion; any re-grading of any existing claim; any statement about
rungs outside {800,1600,2752,5504,11008}; any pooling with G1/G2 absolutes; and no statement about Δ₄ as a
budget effect (DESIGN §3.2).

### `FR-RESCALED-BENT` — the ruler re-bases but is non-monotone below the top
**Condition:** gates PASS, `z_SPAN ≥ 2.0`, **AND** at least one of Δ₁, Δ₂, Δ₃ has `z ≤ −2.0`.

**Says:** the re-based ladder is usable **only up to the last rung before the bend**, which is NAMED with its
realized Δ and z. Above that rung the ladder is not a scale — a larger budget measures *behind* a smaller one at
2σ on shared decks, and elo quoted against those rungs is not ordered.

**Licenses:** quoting `R_i` up to and including the last pre-bend rung; the CL-046 amendment in §5.1 **with the
bend stated in the amendment text**; and a roadmap note that the fair ladder's top is not a usable scale.

**Does NOT license:** explaining the bend away; a re-run of this cell; or an allocation change. **Pre-registered
follow-up:** DESIGN §6.3(a) — the `k4×2752` cell that decomposes budget from allocation — **not** more n on
this design.

### `FR-BOUNDED-FLAT` — the ruler does not resolve its own range
**Condition:** gates PASS, `|z_SPAN| < 2.0`.

**Says:** a **13.76× sims range** produces no span that resolves at n=400 decks/rung. State the two-sided 95%
bound on `SPAN` in points AND its elo equivalent, and say plainly that this **contradicts CL-046's "fair
strength scales cleanly and is NOT saturating"** read *on the production instrument* — which is a finding about
the ruler, not about the champion.

**This is NOT a zero.** It is consistent with (a) a genuinely compressed ladder under `fixed_v1`, (b) the
CL-068 band draw, and (c) the rung being a *clairvoyant* yardstick whose own behaviour changed under the new
rules profile. This cell **cannot separate these.** Licenses nothing beyond stating the bound and flagging that
every ladder-denominated elo in the program is at risk; the pre-registered path is DESIGN §6.3(c)/(d), unfunded.

### `FR-INVERTED` — the ladder runs backwards
**Condition:** gates PASS, `z_SPAN ≤ −2.0`.

**Says:** the production-allocation top rung measures **behind** the 800-sim bottom rung at 2σ on shared decks.
Report it plainly; do not explain it away in the readout. **Pre-registered follow-up: DESIGN §6.3(a) plus a
direct rung-vs-rung head-to-head — not a re-run of this cell**, and not a PRODUCTION.yaml change of any kind
(§5).

### `U-UNREADABLE`
**Condition:** ANY §3 gate FAILS.

**Says:** no strength, spacing, or era statistic from this run is adjudicated, quoted, or entered in
`experiments/results.csv` as a verdict. The failed gate is named with its realized value and the manifest
address searched. **`U-UNREADABLE` is a fully acceptable outcome** — D2 fired it on this same harness eight
hours before this pair was drafted.

⚠️ **If an instrument defect is found after a first adjudication, the session that writes the fix MUST be a
session that has not seen any `R_i`, `Δ_i`, `SPAN`, `D_i` or any cell's summary statistics** — the jcz/D2
binding instrument-fix discipline, carried here verbatim. Bars do not move. §4 is not edited post hoc.

---

## §4.2 — THE ERA SUB-ADJUDICATION (secondary; runs on every ladder branch except `U-UNREADABLE`)

⚠️ **This never changes which ladder branch fired.** It is adjudicated separately and printed alongside.

### `ERA-SHIFTED`
**Condition:** at least one of `D_2752`, `D_5504`, `D_11008` has `|z_eff| ≥ 2.0` (the ×2-inflated se, §1).

**Says:** the move from the G2 instrument (python, pre-`fixed_v1`, band 24e9) to the production instrument
(rust, `fixed_v1`+R9, band 142e9) shifted the fair ladder's absolute reading at the named rung(s) by the stated
amount, **even after the CL-068 humility tax.**

**Licenses:** the §5.1 annotations, worded to state that G2's absolutes are era-bound. **Does NOT license:** an
attribution to `fixed_v1` specifically — `D_i` bundles rules ⊕ band ⊕ n ⊕ code drift and is **not decomposable
by this design** (DESIGN §4.4). The rules-only attribution cell is §6.3(d), unfunded.

### `ERA-BOUNDED-NULL`
**Condition:** all three `|z_eff| < 2.0`.

**Says:** no era shift resolves at this power. **State the bound: ±4.56 pts ≈ ±62 elo per rung.**

⛔ **This is NOT "the era does not matter," and the readout must say so in those words.** For calibration,
recorded before game 1: the *previous* era shift this cell is the sequel to — G1→G2, the leaky-determinization
fix — was **+53.6 elo at the 2752 rung**, i.e. **inside this bound**. A design that could not have resolved the
last era shift has not shown the next one is absent.

---

## §4.3 — THE COMPANION TABLE (printed on EVERY branch, including `U-UNREADABLE`)

**Per cell — A800, B1600, C2752, D5504, E11008, each:**

1. n games, n decks, seat balance, W/D/L, winrate + its z, elo ± 1σ + 95% CI vs h800, deck-paired margin `R_i`
   ± se and its z, `n_failed`, failure rate (**stated even when zero**), failure classes.
2. `champ_prefix_ms_per_move` (⚠️ **the CANDIDATE side in `eval_fair_puct` — the opposite convention from
   `eval_puct_priors`; a readout that swaps them inverts the timing reading**), `rung_ms_per_move`, realized
   ratio, `solver_secs_per_game`, realized s/game vs DESIGN §6's model.
3. band, `cand_leaf_hash`, `rung.leaf_hash`, `rules_profile.name` + `r9_env_ok`, `backend.name` +
   `carc_rs_version` + `carc_rs_binary_sha`, `code_rev`, `cand_tiearb.enabled`, `(k_dets, sims_per_det,
   total_sims)`.

**Then, once:**

4. The **LADDER**: `R_800 … R_11008` with se and 95% CI, and the four spacings Δ₁…Δ₄ plus `SPAN`, each with
   `se_realized` **printed beside the DESIGN §4.2 pre-registered expectation (0.885 pts)** and its z. **Δ₄ is
   printed with a standing flag: "budget × allocation, k4→k8 — not a pure budget increment."**
5. The **ERA** block: `D_2752`, `D_5504`, `D_11008` with `se_naive`, the ×2 tax, `se_eff`, `z_eff`, and the
   G2 source row cited by name. Beside it, **explicitly: "no cross-era delta exists at 800 or 1600 — those are
   new absolutes"** (§1).
6. Every §3 gate with its realized value and which manifest address resolved it; then every §3 WITNESS.
7. The **ATTRIBUTION** block: `A`, `se(A)` **beside the pre-registered 0.885 pts**, `z_A`, `n_common(C,W)`, the
   elo-equivalent, both cells' own absolutes, and the RESIDUAL `D_2752 − A` with the ×2-inflated se it
   inherits. Printed with a standing flag: **"descriptive; not a branch input (§4.4)."** If §3B voided it, print
   the failed `GW-*` gate here with its realized value and state that the ladder branch is unaffected.
8. The DESIGN §1 generation table (G1 / G2 / G3) reprinted with this run's numbers filled into the G3 row, so a
   reader never has to leave the readout to see what changed.

---

## §4.4 — THE ATTRIBUTION READ (E4) — descriptive-plus-z, NEVER a branch input

Owner condition, 2026-08-23, carried verbatim: **attribution is descriptive-plus-z, never a branch input to the
`FR-*` table.** Adjudicated separately, printed alongside, and **mechanically incapable of changing which
`FR-*` branch fired** (§4's preamble states the check: no `FR-*` condition references `A`, `z_A`, `W2752`, or
any §3B gate).

**Precondition:** all §3A gates PASS **and** all §3B gates PASS. If §3A fails → `U-UNREADABLE` takes everything.
If only §3B fails → `RULES-UNREADABLE`: name the failed `GW-*` gate with its realized value, state that **the
ladder branch stands unaffected**, and stop.

### `RULES-SHIFT`
**Condition:** §3A and §3B PASS, `|z_A| ≥ 2.0`.

**Says:** at the 2752 rung, moving from `walled` (R9 off) to `fixed_v1`+R9 shifts the fair candidate's
deck-paired margin against the frozen h800 rung by `A` pts (± se), on shared decks at one code rev — i.e. **the
2026-08-03 production rules change is not neutral for this measurement.** Report the sign and size plainly.

**Licenses exactly two things:** (i) wording in the §5.1 annotations that the era shift has a *named,
within-band-measured* rules component of size `A` at this rung; (ii) reporting the RESIDUAL `D_2752 − A` as a
leftover.

**Does NOT license:** attributing `A` to any single lever of the `fixed_v1` bundle or to R9 specifically (the
bundle is deliberately non-orthogonal — A3/A4 interact, retail absorbs ~5.6× of A3's blast radius); applying
`A` to the other four rungs; treating `A` as a change in the candidate's *strength* rather than in the
candidate-minus-rung *margin*; or any re-grading of anything.

### `RULES-BOUNDED-NULL`
**Condition:** §3A and §3B PASS, `|z_A| < 2.0`.

**Says:** no rules effect resolves at this power. **State the two-sided 95% bound: ±1.77 pts ≈ ±24 elo at the
2752 rung.** This is a genuinely informative bound — it is 2.6× tighter than the E3 era screen and it is
within-band — but it is **a bound, not a zero**, and the readout must say so in those words.

**Licenses:** stating the bound in the §5.1 annotations. **Does NOT license:** "the rules change is
strength-neutral", or dropping the era caveat from any annotation.

---

## §5 — WHAT NO BRANCH DOES

- No branch flips or edits `governance/PRODUCTION.yaml`. **Nothing in this cell is a strength lever.**
- No branch re-rates the champion. Every `R_i` is a reading against the fixed h800 rung, not a champion rating.
- No branch **re-grades** any existing claim. Re-anchoring a ruler changes what future readings are denominated
  in; it does not retroactively change what a past measurement measured. Existing claims get **ANNOTATED**
  (§5.1), never re-graded, never retracted, never recomputed by arithmetic.
- No branch edits or retires CL-046's published G1 numbers, or the five `fair_ruler_*` G2 rows in
  `experiments/results.csv`. All stand exactly as published.
- No branch licenses a leaf, search, budget, or `k_dets` allocation change.
- No branch pools this band with any other band, or quotes a pooled estimate across bands (CL-068).
- No branch licenses a second band, or extends n beyond 400 decks/cell — that needs a fresh owner funding
  decision against the DESIGN §6.3 priced menu.
- No branch licenses the correction of the five mis-stamped `results.csv` rung-`c` cells (D2 DESIGN §2.3) —
  still an independent owner decision, gated by nothing here.
- No branch unparks **E4** (the human anchor). D0/D1 being E4's remaining gate is a roadmap statement about
  *readiness of the ruler*, not an authorization; unparking E4 is a fresh owner decision.
- No branch licenses the DESIGN §6.3 extensions (a)–(c). ⛔ Specifically: **§6.3(b), the cell that would locate
  the FULL desktop deploy champion (arbiter B=64/J=4 ON) on the re-based ruler, is UNFUNDED by owner/orchestrator
  ruling 2026-08-23 (DESIGN §0.2 Q3).** The arbiter-off gap is accepted and stated, not closed, by this cell.
  §6.3(d) is not an extension any more — it is cell W2752, funded and bundled in.
- **No attribution branch changes a ladder branch, and no ladder branch changes an attribution branch.** The two
  adjudications are independent in one direction only: §3A failing takes both; §3B failing takes E4 alone.
- No branch licenses attributing `A` to a single lever of the `fixed_v1` bundle, or extrapolating `A` beyond the
  2752 rung (DESIGN §3.6).

### §5.1 — CLAIMS THAT GET ANNOTATED, NOT RE-GRADED (enumerated before game 1)

Which rows are touched is fixed **now**, so that no post-hoc reading can widen or narrow the blast radius.

| claim / doc | its relationship to the fair ladder | action on any non-`U-UNREADABLE` branch |
|---|---|---|
| **CL-046** — the D0 fair sub-ladder, THE RULER OF RECORD | **is** the ladder | **AMEND** to carry G3 as the ladder's third generation (G1 leaky → G2 post-fix → G3 production-instrument), with the five `R_i`, the four Δ, and the era block. G1/G2 numbers stand verbatim. `best_evidence` gains the five new rows. |
| **CL-045** — A2 fair-PIMC screen, "tax ≈ 156" | fair leg is a D0-era ladder reading | **ANNOTATE:** era-bound to G1; the fair denominator has been re-based twice since. |
| **CL-047** — the flip transfers to fair play | a *direction* claim (transfer), not a magnitude denominated in ladder units | **ANNOTATE (era note only).** The claim's content is unaffected. |
| **CL-048** — clairvoyance tax persists ~100–150 across a 7× sims range | tax = clair − fair; the **fair leg is G1** | **ANNOTATE:** the fair leg is re-based; the tax's absolute magnitude is era-bound. The "does not close with search" shape is a within-G1 contrast and stands as a contrast. |
| **CL-051** — curve125 leaf, fair confirm | fair confirm was CRN vs the D0 baseline, G1/G2 era | **ANNOTATE:** a within-era deck-matched contrast; stands as a contrast, absolute denomination re-based. |
| **CL-054** — `k_dets` width bracket (+5.18 ± 1.24 pts/deck at 2752) | deck-matched within-era contrast | **ANNOTATE:** the allocation finding stands untouched; only its absolute denomination moves. |
| **CL-068** — budget/elo pareto for the deploy champion | mixes ladder-denominated and h2h readings | **ANNOTATE (era note).** |
| **CL-071 / CL-060** — the k8×1376 budget promotion | **direct head-to-head vs the incumbent**, never ladder-denominated | ⛔ **NO ANNOTATION FOR DENOMINATION.** A ruler re-anchor does not move a head-to-head. An era note only if the owner asks. |
| **CL-023 / LEVEL2 ladder, CL-026 / HYBRID, CL-001/CL-012 / CLEAN_EVAL** | the *heuristic* L2 ladder and the clairvoyant audit — a different instrument | ⛔ **NO ACTION.** Already closed by annotation 2026-08-23 (prep doc §3); this cell does not reopen them. |
| **the B=64 tie-arbiter fold (2026-08-20)** | self-anchored vs the unmodified champion | ⛔ **NO ACTION.** Not ladder-denominated. Rung E is arbiter-off (DESIGN §3.4), so this cell says nothing about it. |
| **`governance/PRODUCTION.yaml`** | — | ⛔ **NOT TOUCHED, on any branch.** |

---

## §6 — THE STATED PRIOR, RECORDED BEFORE GAME 1

**On the ladder's shape.** G1 (leaky, python, walled, band 15e9, k8) read
`+27.9 / +61.4 / +81.4 / +149.3 @ 800/1600/2752/5504` — rising, with the *top* increment the biggest, which is
what CL-046's "NOT saturating" claim rests on. G2 (post-fix, python, walled, band 24e9, k4) read
`+135.0 @ 2752 · +147.2 @ 5504 · +114.3 @ 11008(k4×2752) · +123.0 @ 11008(k8×1376)` — i.e. **G2 already
flattened and then bent** where G1 rose. **The house prior for G3 is therefore: a large, easily-resolved SPAN
driven almost entirely by the 800→2752 stretch, and a flat-to-bending top.** `FR-RESCALED` and
`FR-RESCALED-BENT` are both expected shapes; `FR-BOUNDED-FLAT` would contradict every generation of this ladder
and `FR-INVERTED` would contradict all of them plus CL-060's direct head-to-head.

**On the era delta.** No prior. The rust backend is gated behaviour-identical, so any shift must come from
`fixed_v1`+R9 or from the band draw — and DESIGN §4.4 says this design cannot tell those apart, nor resolve a
shift below ~62 elo. **The honest pre-registered expectation is `ERA-BOUNDED-NULL` at ~62-elo resolution, and
that outcome must be reported as a bound, not as reassurance.**

**On what this cell is for.** It is not a strength experiment. It is the instrument re-calibration the roadmap's
D1 line names as its own successor, held until the fair ladder is next quoted. Its success condition is a
**usable, auditable, production-instrument ruler with five stated rung values** — not a large number anywhere.
