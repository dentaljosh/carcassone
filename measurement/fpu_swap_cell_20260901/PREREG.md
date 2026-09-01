# PREREG — the FPU-INSTEAD-OF-THE-ARBITER swap cell

Status: **FROZEN AT BUILD, UNLAUNCHED.** 0 games exist. `BAND_CLAIMED` and
`BLIND_COMMIT` are both unspent placeholders — see the sibling files. This
agent did not claim a band, did not touch `governance/`, and did not launch.

> ⚠️ **AMENDED PRE-LAUNCH, zero games run; amended blind commit = the commit
> introducing this line.** Orchestrator review (statistics-blind — no cell
> outcomes exist anywhere in this pair, only a throwaway build-verification
> fixture that plays no role in any real reading) found the original design
> margin-only and therefore mis-targeted: the declined-by-arithmetic case this
> cell exists to test-directly is built on an **ELO-DOMAIN** gap (fpu-alone
> +26 elo vs arb-alone +66/+69 elo, ≈+40 elo) — margin is where the two
> surfaces are closest and most overlap-discounted, which is why the original
> §4.3 table read 57–90% `SWAP-UNRESOLVED`. This amendment adds a **CO-PRIMARY
> elo leg** (deck-paired elo advantage of the arb side, on the cell's own
> REALIZED SE, never a modelled one), Holm-corrected against the margin leg
> for the 2-leg multiple comparison (`HOLM_Z≈2.278` replaces `BRANCH_Z=2.0` as
> the per-leg threshold), a decision-anchored elo bar (`BAR_ELO_LEG=15` elo, ≈7×
> the arbiter's own clock-refund upside), and rewrites `SWAP-KILLED`/
> `SWAP-SURPRISE` to fire if EITHER leg clears its Holm-adjusted bound. Under
> the funding brief's own elo prior (~+40), `SWAP-KILLED` becomes the **modal**
> branch (≈73–79% combined), reversing the pre-amendment table's headline.
> Nothing is retracted: the margin-only figures were correct as far as they
> went, and remain in the ladder as a leg in their own right — they were
> simply the wrong PRIMARY axis for this decision. One numeric correction on
> the way: the coordinator's amendment message cited CLAUDE.md's "n=400 paired
> ≈ ±12 elo" figure, which is the SE at 400 GAMES (200 decks); this cell plays
> **800 games** (400 decks paired), whose own `elo_sigma_paired(0.5, 800)` ≈
> **8.69 elo** — tighter, and it matches this exact cell shape's own banked
> `PRIOR_ART` elo-sigma values (8.69–8.71) rather than being copied from a
> different-n table entry. Using the correct, tighter figure only strengthens
> the elo leg's case. Full detail: §4 below (rewritten in place) and
> `screen_lib.py`'s own "AMENDED PRE-LAUNCH" comment blocks, which carry the
> same content as the executable law.

⛔ **THE PAIR IS LAW.** If `adjudicate_swap_cell.py` or `launch_swap_cell.sh`
disagree with this document, **they are wrong**, not this document — except
where noted `⚠️ LAW LIVES IN screen_lib.py`, for the handful of numeric
constants that must not exist in two places (`SIGMA_D_MODEL`, `BAR_SWAP`,
`DEPLOYED_TIEARB`, the branch ladder). Both the launcher's precondition ladder
and the adjudicator import `screen_lib.py`, so a drift between them is
impossible by construction rather than by review.

## 0. Why this cell, and why now (context, cited not copied)

`docs/LEVER_INDEX.md` (grep `"FPU INSTEAD OF"`) carries the swap as
**NEVER TRIED — DECLINED-BY-ARITHMETIC (2026-09-01)**: the owner asked
*"did we run that experiment?"* and the honest answer was no. The banked
arithmetic:

* fpu-alone (arb off both sides) is **+26.11 elo** / **+2.95125 pts/deck**
  (`results.csv fpu_resurrection_CELL_FPU02_F_RESURRECT_n800paired_b155e9`,
  CONFIRMED, `LB95 +1.586 > BAR_M 1.381`, z +4.32) — a weak margin→win
  conversion.
* arb-alone (arb on, B=64, vs the unmodified champion) is **~+66 elo internal**
  (`results.csv tiearb_widening_..._b140e9`, CELL_B64 vs the common opponent,
  M +5.2123 pts/deck, elo +66.4644 ± 6.4597) and **~+69 elo external**
  (`results.csv carcasum_arbchallenge_D_on_minus_off_n200decks_b147e9`,
  T-TRANSFER, z +4.4941) — corroborated cross-engine.
* fpu's MARGINAL value **on top of** an already-armed arbiter (both seats
  symmetric) collapsed to **+1.0188 pts/deck** (round 1,
  `fpu_h2h_deployed_config_H_UNRESOLVED_n800paired_b168e9`, UNRESOLVED, z
  +1.49) and **+0.8612 pts/deck** (round 2, `n1600paired_b169e9`, UNRESOLVED,
  z +1.89, missing the ADOPT bar by 0.05 at DOUBLE round 1's n) — the overlap
  between the two surfaces is large.

The owner's own gloss: **swap ≈ −40 elo net** for a ~10–12% clock refund
(~+2 elo redeployed). None of the cells above is fpu-alone **against**
arb-alone, head to head — every prior FPU cell measured FPU either against
plain or on top of an already-armed arbiter, never as a substitute for one.
**This cell is that direct read**, funded because the owner wants it on the
record even though it is expected to confirm the decline, not overturn it —
a **KILL-DIRECTION cell**.

## 1. The cell

One cell, one band, one box.

| | candidate | opponent |
|---|---|---|
| base | production champion (`governance/PRODUCTION.yaml`) | production champion, **unmodified** |
| `fpu_reduction` | **0.2** (`--cand-fpu-reduction 0.2`) | `null` (never requested) |
| tie-arbiter | **ABSENT** — no `--cand-tiearb-*` flag is ever passed | **ARMED** at the full deployed spec: `--opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4 --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1 --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all` |
| budget | k16 × 1376 = 22016 (`--k-dets 16 --sims 1376`) | k16 × 1376 = 22016 (`--opp-k-dets 16 --opp-sims 1376`) — **not the variable under test** |
| exact endgame | K≤2 marginalized (`--exact-k 2`) | same |
| leaf | `a36d2e15a3b3d71d` (curve125) | same |
| backend | rust (`--backend rust`) | same |
| rules | `fixed_v1` + `CARCASSONNE_FIX_R9=1` (env-latched at import) | same |

`--opponent fair-champion`, `--n 800 --paired --seed-start <band lo>`,
`--rules-profile fixed_v1`, `--workers 24` (laptop), `--out-root`/
`--out-subdir` naming the archive, `--stamp-key BLIND_COMMIT=<sha>` once
stamped. `run_cell()` in `launch_swap_cell.sh` is the single source of the
real invocation — this table restates it, `screen_lib.py`'s constants are law.

**The asymmetry is the whole point.** This is NOT `fpu_resurrection_prep`'s
arb-off-both-sides shape and NOT `fpu_h2h`'s arb-on-both-sides shape — it is
the third, previously-unbuilt shape the 2026-08-31 `--opp-tiearb-*` plumbing
exists to express (`scripts/classical_search/tiearb_gates.py`, whose
`assert_tiearb_sides`/`check_tiearb_sides`/`tiearb_sides_summary` this pair's
`G-ARB-ASYM` and `G-ARB-FIRED` gates import directly rather than re-derive).

## 2. The band

**Proposed, NOT claimed**: `170_000_000_000` (`screen_lib.PROPOSED_BAND`) —
the next monotone-free id after `fpu_h2h_r2_prep`'s `169_000_000_000`
(`governance/BAND_REGISTRY.csv`, checked 2026-09-01). This is a **fresh-deck
cell**: unlike `e1b_armed_continuation_20260901` (which re-prices an archived
game's tail and spends no band), this cell draws 400 NEW seat-balanced decks
and DOES owe a `governance/BAND_REGISTRY.csv` row. See `BAND_CLAIMED.placeholder`
for the orchestrator's protocol (tree sweep — the `146e9` trap — THEN the
registry append THEN the `BAND_CLAIMED` acknowledgement file THEN the
`BLIND_COMMIT.json` stamp THEN launch). This agent did none of those four.

Throwaway sub-range for the smoke + positive-control legs:
`170_000_999_000 .. 170_000_999_999` (`screen_lib.THROWAWAY_BASE`,
`THROWAWAY_SPAN`) — never inside the 400-deck real range even if the claimed
band ends up shifted, never pooled, never claims a decks_influenced deck.

## 3. The statistics and their sign (AMENDED — two co-primary legs)

`diff` is the harness's own field, **candidate minus opponent, in points**.
**Margin leg**: `M := paired_mean_margin` = fpu-alone(arb-off) minus
arb-alone(arb-on B64), deck-paired over the 400 decks
(`screen_lib.per_deck_margins`/`paired_margin`, an independent `math.fsum`
re-implementation of the harness's own statistic; `se_M` is its REALIZED
empirical SE, never `SE_400`). **Elo leg (AMENDED)**: `elo :=` the candidate's
deck-paired elo vs the opponent (`winrate_elo`'s `elo`, CANDIDATE-referenced —
positive means the fpu-alone candidate is ahead); `se_elo` is its REALIZED
deck-paired SE (`winrate_elo`'s `elo_sig_1sigma_paired`, computed from the
cell's OWN observed win rate — never `SE_ELO_PLANNING`, the planning-time
constant at `wr=0.5` used only for the anomaly ratio, same treatment as
`SE_400`/`SIGMA_D_MODEL`). `RECON` gates any disagreement between the fsum
witness and `summary.json` to a void on EITHER statistic, never arbitrates it.

Define `arb_advantage_margin := -M` (pts/deck) and `arb_advantage_elo := -elo`
(elo) — on each leg's own scale, "how much the arb-on opponent beats the
fpu-alone candidate by". Every branch below is written in terms of these
bounds, because that is the funding brief's own framing ("would the swap ever
be reconsidered?").

**Sign convention is pinned by tests, on BOTH legs independently**:
`screen_lib.sanity_check()` and `test_swap_cell.py` both assert (elo/margin
held neutral in turn): `branch_for_cell(-10.0, 0.3, 0.0, SE_ELO_PLANNING,
gates_ok=True) == "SWAP-KILLED"` (margin leg, arb crushing on points),
`branch_for_cell(0.0, SE_400, -100.0, 3.0, gates_ok=True) == "SWAP-KILLED"`
(elo leg, arb crushing on elo), and the mirror-image `SWAP-SURPRISE` pins for
both legs at strongly positive values. A dedicated test also pins the
CROSS-LEG-DISAGREEMENT resolution order (`SWAP-KILLED` is checked first).

## 4. The bar and the branch map (AMENDED — Holm-corrected, two legs)

### 4.1 Two different bars, on purpose — SAY SO

The decision the funding brief actually asks — *"would the swap ever be
reconsidered?"* — has a real bar: the swap is attractive only if fpu-alone is
**not worse** than arb-alone by **less than the arbiter's own clock cost**
(~+2 elo ≈ ~0.35 pts/deck by the linearized gloss, never a branch input).
**That bar is UNRESOLVABLE at n=400 decks / 800 games on EITHER leg alone** —
`SE_400 ≈ 0.69 pts/deck` and `SE_ELO_PLANNING ≈ 8.69 elo` both comfortably
exceed it, so no realistic point estimate at this n can pin either
`arb_advantage` to within the refund's own margin. This is stated here in the
open, per the 2026-08-30 owner ruling ("bars are set at the effect size the
decision cares about, never 2σ̂ of the instrument") and its corollary that when
the honest answer is "we can only afford the bounding direction", the
read-rule says so rather than silently substituting a coarser bar.

**The affordable reads are the KILL direction, on two legs now:**

* **Margin**: `BAR_SWAP = 1.0 pts/deck` (`screen_lib.BAR_SWAP`) —
  **"the FPU chain's own bar class"**, the identical `LB95 >= +1.0 pts/deck`
  ADOPT bar the `fpu_h2h`/`fpu_h2h_r2` rounds used, reused here for
  cross-round comparability rather than re-derived.
* **Elo (AMENDED, CO-PRIMARY)**: `BAR_ELO_LEG = 15.0 elo`
  (`screen_lib.BAR_ELO_LEG`) — decision-anchored, not `2·σ̂`: the swap's
  ENTIRE upside is the arbiter's own clock refund, ≈+2 elo redeployed; `15` is
  ≈7× that refund, so an arb-side elo edge bounded at or above it makes the
  swap dead on any plausible accounting of the refund's worth, not merely dead
  at this design's own resolution. ⚠️ **NOTE THE DISTINCTION EXPLICITLY**: at
  n=800 games the realized elo SE is typically close to `SE_ELO_PLANNING≈8.69`,
  so `2·σ̂≈17.4` — `BAR_ELO_LEG (15.0) sits BELOW 2·σ̂` here, the reverse of how
  it might look if the bar had been derived FROM `2·σ̂`. It was not: it comes
  from the 7× refund multiple, and landing below `2·σ̂` is a consequence of how
  well-powered this leg is, not the derivation.

Neither is the 0.35 figure, and this document does not pretend otherwise.

### 4.2 THE HOLM CORRECTION — why the per-leg threshold moved from 2σ to `HOLM_Z`

Testing TWO legs instead of one, each capable of independently firing
`SWAP-KILLED`, inflates the family-wise false-fire rate under a true null
unless corrected. `screen_lib.HOLM_Z = Φ⁻¹(1 - (1-Φ(2.0))/2) ≈ 2.2776` replaces
the pre-amendment `BRANCH_Z = 2.0` as the per-leg threshold both legs are
tested at — for a "reject if EITHER leg clears its bound" family test with
m=2, Holm's step-down procedure and plain Bonferroni agree exactly on this
question (both compare the more extreme leg's tail probability to
`alpha/m=alpha/2`), so this is not an approximation of Holm, it IS Holm for
m=2 union rejection. The result: **each leg individually must clear a
STRICTER bound** than the pre-amendment single-leg design would have required,
holding the overall false-fire rate at its original single-leg level.

### 4.3 The branch ladder — first match wins, exhaustive, EITHER leg fires

```
if not gates_ok:                                U-VOID-INSTRUMENT
elif BOTH legs unusable (None/NaN/se<=0):        U-VOID-INSTRUMENT
elif M + HOLM_Z*se_M <= -BAR_SWAP:               SWAP-KILLED   # margin leg
elif elo + HOLM_Z*se_elo <= -BAR_ELO_LEG:        SWAP-KILLED   # elo leg
elif M - HOLM_Z*se_M > 0:                        SWAP-SURPRISE # margin leg
elif elo - HOLM_Z*se_elo > 0:                    SWAP-SURPRISE # elo leg
else:                                            SWAP-UNRESOLVED
```

Within one leg, KILLED/SURPRISE stay mutually exclusive by the same
construction as the pre-amendment single-leg ladder (`screen_lib.
branch_for_cell`'s docstring proves it; `sanity_check()` sweeps a 2D grid of
`(M, elo)` at fixed realistic SEs and independently re-derives every cell's
branch as a witness). **Across legs, a genuine disagreement is possible in
principle** (margin and elo are different statistics of the same 800 games,
not identical ones) — `SWAP-KILLED` is checked first, so it wins any such
disagreement; this is disclosed as a named, tested edge case rather than
assumed away, even though it is not expected in practice (every `PRIOR_ART`
row agrees in sign on both axes already, and the two statistics are strongly
positively correlated by construction — they come from the same games).

* **SWAP-KILLED** — the arb side's advantage resolves clearly above the
  affordable bar on AT LEAST ONE leg. Confirms the existing
  declined-by-arithmetic posture with a direct read; `docs/LEVER_INDEX.md`'s
  row moves to CONFIRMED-BY-DIRECT-READ. Report WHICH leg(s) fired — a
  margin-only fire and an elo-only fire are different evidence and should not
  be merged into one undifferentiated line. No `PRODUCTION.yaml` action either
  way — there was never a proposal to change it.
* **SWAP-SURPRISE** — the fpu-alone side resolves clearly positive on AT LEAST
  ONE leg. This would contradict every other prior arm of this axis (all
  `PRIOR_ART` rows agree in sign) and must be treated as the textbook
  noise-signature case before it is believed — re-check RECON and every gate
  by hand, do not act on a single cell
  (`feedback_noisy_plateau_not_a_conclusion`). If only one leg fired while the
  other's point estimate still points arb-favoring, that CROSS-LEG
  DISAGREEMENT is itself the first thing to review.
* **SWAP-UNRESOLVED** — neither bound clears on either leg. See the power
  table below for how probable this still is, and under which priors.

### 4.4 The expected read distribution — computed, not asserted, BOTH legs

`SE_400 = SIGMA_D_MODEL / sqrt(400) ≈ 0.6905 pts/deck` (unchanged, carried from
`fpu_resurrection_prep`/`fpu_h2h_r2_prep`). `SE_ELO_PLANNING =
elo_sigma_paired(0.5, 800) ≈ 8.686 elo` (AMENDED — the elo leg's planning-time
constant at n=800 GAMES, this cell's real game count; **NOT** the ~±12 elo the
coordinator's amendment message quoted from CLAUDE.md's n=400-GAMES table
entry — see the amendment banner above; the correct, tighter figure matches
this exact cell shape's own banked `PRIOR_ART` elo-sigma values, 8.69–8.71, to
the second decimal). Both are power arithmetic only, never branch
denominators. `screen_lib.power_two_leg(delta_margin, delta_elo)`:

| priors (margin pts/deck, elo) | source | P(margin KILLED) | P(elo KILLED) | **P(combined KILLED)** bounds | P(combined SURPRISE) upper | P(combined UNRESOLVED) bounds |
|---|---|---:|---:|---:|---:|---:|
| (1.0, 15.0) | both bars exactly | 2.3% | 2.3%* | [2.3%, 4.5%] | negligible | [95.5%, 97.7%] |
| **(1.5, 40)** | **funding brief's own priors (margin gloss + elo gap)** | 10.1% | **72.6%** | **[72.6%, 78.6%]** | ~4×10⁻⁶ | [21.4%, 27.4%] |
| **(2.26, 40)** | **this doc's margin reconstruction (§0) + the same elo prior** | 43.0% | **72.6%** | **[72.6%, 100%]†** | ~1.4×10⁻⁸ | [0%, 27.4%] |

\* the elo row at exactly its own bar (15.0) uses `delta_elo=15.0`, shown only
for the "both bars exactly" sanity row, not a funding-brief prior. † the upper
bound saturates at 100% because the naive independence-assumed SUM of the two
legs' individual `P(killed)` exceeds 1 at this row — the bound is CAPPED, not
a claim that KILLED is certain; the honest number is the LOWER bound, 72.6%.

**This is the amendment's headline reversal.** Under the funding brief's own
priors, `P(combined SWAP-KILLED)` jumps from 10–43% (margin-only, the
pre-amendment table) to **72.6–78.6%** (margin+elo combined) — **SWAP-KILLED
becomes the MODAL branch**, driven almost entirely by the elo leg (whose own
`P(killed) = 72.6%` at `delta_elo=40` dwarfs the margin leg's 10.1–43.0%).
This is not a coincidence of the numbers: the funding brief's own arithmetic
(fpu-alone +26 elo vs arb-alone +66/+69 elo) IS an elo-domain gap, and the elo
leg is now testing exactly that gap on a well-powered SE (`≈8.69` elo, vs the
gap's own `≈40` elo — a raw z of ≈4.6 before any correction).

**The correlation caveat, honestly**: `power_two_leg`'s "combined" figure is a
BRACKET, `[max(leg), min(1, sum(legs))]`, not a point estimate, because margin
and elo are computed from the SAME 800 games and are therefore positively
correlated (a game the fpu-alone candidate loses badly on points is
disproportionately also a game it loses outright) — the TRUE joint probability
sits closer to the LOWER bound (the better single leg) than the upper one.
Holm's correction assumes independence for its `alpha/m` derivation, which
under this actual positive correlation is CONSERVATIVE (it slightly
overstates the false-fire risk under a true null, the safe direction for a
bar) rather than anti-conservative — stated here rather than left implicit.

**What is still true, unchanged from the pre-amendment table**: SWAP-SURPRISE
remains negligible under every prior in this table (many orders of magnitude
below SWAP-KILLED on either leg) — if this cell resolves a determinate
direction, it is overwhelmingly likely to be SWAP-KILLED. What CHANGED is the
UNRESOLVED branch's own probability: it was the modal branch pre-amendment
(57–90%); it is now the minority branch (21–27%) under the funding brief's own
priors, because the elo leg gives this design real power on the axis the
declined-by-arithmetic case actually rests on.

## 5. Gates

`adjudicate_swap_cell.py::GATES`, every one printing which document and
address answered (`manifest.json` for config, `summary.json` for statistics —
`summary.json` carries no config block, so a gate that reads config off it
fails closed rather than passing vacuously):

| gate | checks |
|---|---|
| `G-FPU` | the candidate's REQUEST (`config.cand_search.fpu_reduction`) is exactly `0.2` |
| `G-FPU-TWOSIDED` | the RESOLVED config: candidate's `fpu_reduction` bound at 0.2, opponent's reads an explicit `null` |
| `G-ARB-ASYM` | `tiearb_gates.assert_tiearb_sides(cand_expected=None, opp_expected=DEPLOYED_TIEARB_B64)` — candidate unarmed, opponent armed at the full deployed dict, from the manifest |
| `G-ARB-FIRED` | the POSITIVE CONTROL: `tiearb_sides_summary` shows the opponent's arbiter fired on a nonzero count of tied plies IN PLAY, and the candidate's fired on zero — a config gate proves the knob was requested, this proves it bound and bit |
| `G-BUDGET` | both sides k16×1376=22016, product multiplies out |
| `G-EXACT` | `exact_k=2`, `mode=marginalized` |
| `G-RULES` | `rules_profile.name=fixed_v1`, `r9_env_ok`/`r9_env_observed` both `true` |
| `G-BACKEND` | `backend.name=backend.requested=rust`, not mixed |
| `G-WHEEL` | `carc_rs_build`/`carc_rs_binary_sha` present, not mixed |
| `G-LEAF` | both sides `a36d2e15a3b3d71d`, curve125 |
| `G-BAND` | `band_seed_start` matches the CLAIMED band (read from `BAND_CLAIMED`, not the placeholder proposal), `n_decks=400`, `seatings_per_deck=2` |
| `G-DECKS` | every realized seed inside the claimed range, no half-played deck, `n_common == 400` |
| `G-N` | `summary.n == 800`, failure rate `< 2%`, `n_common >= 320` (80% floor) |
| `G-SAT` | winrate inside `(0.30, 0.70)` — wider than a single-variable cell's rail, because two axes move in opposite directions across the seats |
| `G-HOST` | manifest `host` matches the `laptop` role |
| `G-REV` | `code_rev` canonicalizes to the stamped `PINNED_SRC_REV` |
| `RECON` | the independent `math.fsum` re-derivation of `paired_mean_margin`/`paired_z`/`n_paired`/`winrate`/`elo` agrees with `summary.json` |

Round-level (not per-cell, since there is exactly one cell): `G-BLIND` — the
manifest's `BLIND_COMMIT` stamp is a single 40-hex sha matching
`BLIND_COMMIT.json`.

**Any gate failing voids the cell to `U-VOID-INSTRUMENT` — the instrument,
not the world.** No branch statistic is printed as a finding when
`gates_ok` is false; it is printed as a companion table only.

## 6. Smoke + positive-control protocol (§9-style, `--smoke` mode)

Before any real chunk: one smoke cell at the throwaway offset, PRODUCTION
knobs, `SMOKE_GAMES=8` games (per `launch_swap_cell.sh`), with
`--allow-selfplay-seeds` (the throwaway range is outside every registered
clean-eval band on purpose and must bypass `assert_clean_eval_seed_range`).
`adjudicate_swap_cell.py --smoke-mode` reads back the EMITTED manifest and
requires `G-FPU`, `G-FPU-TWOSIDED`, `G-ARB-ASYM` and `G-ARB-FIRED` to all pass
— the four gates whose failure means the LAUNCHER, not the world, is wrong.
**Empty adjudication is a FAILURE, not a silent pass**: `smoke_problems()`
returns a non-empty list on zero cells found, which the launcher turns into a
nonzero exit (`|| DIE`) — the R1 defect this codebase already found once in
`fpu_resurrection_prep` (a `--smoke-mode` that adjudicated zero cells and
still exited 0) is guarded against explicitly here rather than assumed fixed
by inheritance.

`G-ARB-FIRED` is this round's positive control in the sense the funding brief
asked for ("your gates must assert cand arb ABSENT + opp arb ARMED WITH
FIRES... NOT from config echoes"): it reads `summary.json`'s realized
`opp_tiearb_fired_plies_total` / `tiearb_fired_plies_total`
(`tiearb_gates.tiearb_sides_summary`), not the config dict. At `k16×1376`
production budget on a real position the arbiter is expected to fire on a
nontrivial fraction of games (per `tiearb_widening`'s `phi_effective ≈17.5`);
at the tiny 8-game smoke a zero-fire smoke is possible by chance and is
treated as **inconclusive, not proof of failure** — the launcher's own
comment says so and a human review of `SMOKE_laptop.json` is still owed
before a real chunk plays, exactly as `fpu_h2h_r2_prep`'s IDENT legs are
reviewed by hand.

## 7. Non-inference limits (say them before the read, not after)

* **Self-anchored.** Every statistic is this candidate/opponent pair on this
  band. No absolute-strength claim, no pooling with any other band.
* **One cell, one band, no bracket.** Nothing here interpolates or
  extrapolates to any other fpu dose or arbiter width.
* **The affordable bar is not the decision bar** (§4.1) — a SWAP-KILLED
  read licenses confirming the existing decline, not re-deriving a different
  clock-cost threshold this design cannot see.
* **No source change, no `PRODUCTION.yaml` touch, no `governance/` touch on
  any branch of this round.** If a branch's rider suggests a follow-up (§4.3),
  that follow-up needs its own funding and its own prereg.
* **The Holm correction assumes independence it doesn't have** (§4.4) —
  disclosed as CONSERVATIVE (true positive correlation between the two legs
  means the true joint false-fire rate is lower than the nominal, not higher),
  never presented as exact.
* **Cross-band humility** does not apply within this cell (one band, one
  contrast) but DOES apply to every `PRIOR_ART` comparison in `screen_lib.py`
  — none of those rows share this cell's band, and several are budget-
  mismatched (k8×1376 vs this cell's k16×1376) — inflate ~1.5–2× before
  treating any prior-art gap as informative.

## 8. Citations

* `docs/LEVER_INDEX.md` — grep `"FPU INSTEAD OF"` — the funding row.
* `results.csv` — `fpu_resurrection_CELL_FPU02_F_RESURRECT_n800paired_b155e9`,
  `fpu_h2h_deployed_config_H_UNRESOLVED_n800paired_b168e9`,
  `fpu_h2h_r2_deployed_config_H_UNRESOLVED_n1600paired_b169e9`,
  `tiearb_widening_b32v64_gamecell_B64_minus_B32_n1497decks_b140e9`,
  `carcasum_arbchallenge_D_on_minus_off_n200decks_b147e9`.
* `measurement/fpu_resurrection_prep/` — the arb-off-both-sides sibling round
  (`screen_lib.py`/`analyze_fpu.py` pattern this pair forks in construction).
* `measurement/fpu_h2h_r2_prep/` — the arb-on-both-sides sibling round
  (`WORKERS.conf`, `run_cells.sh::run_cell` — this pair's launcher forks its
  `run_cell` shape, minus the multi-chunk/two-box flexible-box machinery,
  which this single-cell single-box round has no use for).
* `scripts/classical_search/tiearb_gates.py` — the asymmetric-arbiter gate
  vocabulary this pair imports rather than re-derives.
* `measurement/e1b_armed_continuation_20260901/` — the `BAND_CLAIMED`/
  `BLIND_COMMIT.json` two-file protocol this pair's sibling files follow.
* `CLAUDE.md` "n-thresholds" — the n=400-GAMES paired ≈±12 elo figure the
  amendment's own funding message quoted; §0's amendment banner and §4.4 both
  disclose why this cell's own `SE_ELO_PLANNING` (n=800 games) is a different,
  tighter number (≈8.69) rather than that table entry.
* `measurement/carcasum_rung2_prep/DESIGN.md` — the house precedent for the
  "AMENDED PRE-LAUNCH, zero games run" banner format this amendment reuses.
