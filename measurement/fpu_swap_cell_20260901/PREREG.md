# PREREG — the FPU-INSTEAD-OF-THE-ARBITER swap cell

Status: **FROZEN AT BUILD, UNLAUNCHED.** 0 games exist. `BAND_CLAIMED` and
`BLIND_COMMIT` are both unspent placeholders — see the sibling files. This
agent did not claim a band, did not touch `governance/`, and did not launch.

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

## 3. The statistic and its sign

`diff` is the harness's own field, **candidate minus opponent, in points**.
`M := paired_mean_margin` = fpu-alone(arb-off) minus arb-alone(arb-on B64),
deck-paired over the 400 decks (`screen_lib.per_deck_margins`/`paired_margin`,
an independent `math.fsum` re-implementation of the harness's own statistic —
`RECON` gates any disagreement to a void, never arbitrates it).

Define `arb_advantage := -M` — "how many points/deck the arb-on opponent beats
the fpu-alone candidate by". Every branch below is written in terms of
`arb_advantage`'s bound, because that is the funding brief's own framing
("would the swap ever be reconsidered?").

**Sign convention is pinned by a test**: `screen_lib.sanity_check()` asserts
`branch_for_cell(-10.0, 0.3, gates_ok=True) == "SWAP-KILLED"` (a strongly
negative `M`, i.e. arb crushing, must read KILLED) and
`branch_for_cell(+10.0, 0.3, gates_ok=True) == "SWAP-SURPRISE"` (a strongly
positive `M`, fpu crushing, must read SURPRISE). `test_swap_cell.py` repeats
both assertions independently of `sanity_check` so a change to one cannot
silently un-pin the other.

## 4. The bar and the branch map

### 4.1 Two different bars, on purpose — SAY SO

The decision the funding brief actually asks — *"would the swap ever be
reconsidered?"* — has a real bar: the swap is attractive only if fpu-alone is
**not worse** than arb-alone by **less than the arbiter's own clock cost**
(~+2 elo ≈ ~0.35 pts/deck by the linearized gloss `BAR_ELO` uses, never a
branch input). **That bar is UNRESOLVABLE at n=400 decks** — `SE_400 ≈ 0.69
pts/deck` alone is roughly double it, so no realistic point estimate at this n
can pin `arb_advantage` to within 0.35 either side of anything. This is stated
here in the open, per the 2026-08-30 owner ruling ("bars are set at the effect
size the decision cares about, never 2σ̂ of the instrument") and its corollary
that when the honest answer is "we can only afford the bounding direction",
the read-rule says so rather than silently substituting a coarser bar.

**The affordable read is the KILL direction.** `BAR_SWAP = 1.0 pts/deck`
(`screen_lib.BAR_SWAP`) is **"the FPU chain's own bar class"** — the identical
`LB95 >= +1.0 pts/deck` ADOPT bar the `fpu_h2h`/`fpu_h2h_r2` rounds used for
their (symmetric) cell, reused here for cross-round comparability rather than
re-derived. It is a real, decision-adjacent bar (roughly the affordable clock
cost times a small safety multiple, and comfortably inside what a confirmed
CELL_FPU02-class effect could produce) — but it is **not** the 0.35 figure,
and this document does not pretend otherwise.

### 4.2 The branch ladder — first match wins, exhaustive

```
if not gates_ok:                       U-VOID-INSTRUMENT
elif M + 2*SE <= -BAR_SWAP:            SWAP-KILLED      # LB95(arb_advantage) >= +1.0
elif M - 2*SE >  0:                    SWAP-SURPRISE    # LB95(M) > 0
else:                                  SWAP-UNRESOLVED
```

Mutually exclusive by construction (`screen_lib.branch_for_cell`'s docstring
proves it; `sanity_check()` sweeps a 400×6 grid of `(M, se)` and asserts every
cell lands on exactly one known branch).

* **SWAP-KILLED** — the arb side's advantage resolves clearly above the
  affordable bar. Confirms the existing declined-by-arithmetic posture with a
  direct read; `docs/LEVER_INDEX.md`'s row moves to
  CONFIRMED-BY-DIRECT-READ. No `PRODUCTION.yaml` action either way — there was
  never a proposal to change it.
* **SWAP-SURPRISE** — the fpu-alone side resolves clearly positive. This would
  contradict every other prior arm of this axis (all four cells above agree in
  sign) and must be treated as the textbook noise-signature case before it is
  believed — re-check RECON and every gate by hand, do not act on a single
  cell (`feedback_noisy_plateau_not_a_conclusion`).
* **SWAP-UNRESOLVED** — neither bound clears. **This is the branch the
  funding brief's own arithmetic predicts is MOST PROBABLE at n=400** — see
  the power table below. An unresolved read here is not evidence against the
  arb side; it is what an underpowered direct measurement of an
  already-strongly-primed direction looks like.

### 4.3 The expected read distribution — computed, not asserted

`SE_400 = SIGMA_D_MODEL / sqrt(400) ≈ 0.6905 pts/deck` (the same
`SIGMA_D_MODEL = 13.81` sizing constant carried, unmodified, from
`fpu_resurrection_prep` / `fpu_h2h_r2_prep` — power arithmetic only, never a
branch denominator). `screen_lib.power_at(true_arb_advantage, SE_400)`:

| true `arb_advantage` (pts/deck) | source | P(SWAP-KILLED) | P(SWAP-SURPRISE) | P(SWAP-UNRESOLVED) |
|---:|---|---:|---:|---:|
| 1.0 (= BAR_SWAP) | the bar itself | 2.3% | 0.03% | 97.7% |
| **1.5** | **the funding brief's own arithmetic gloss** | **10.1%** | ~0.002% | **89.9%** |
| 2.0 | intermediate | 29.1% | ~0.00005% | 70.9% |
| **2.26** | **this doc's additive reconstruction (§0)** | **43.0%** | ~0.00001% | **57.0%** |
| 3.0 | optimistic (near arb-alone's own +5.2 minus a large overlap discount) | 81.5% | ~0.0000001% | 18.5% |

**Read this honestly, not hopefully.** Under the funding brief's own stated
prior (~+1.5 pts/deck), **SWAP-UNRESOLVED is the single most probable
outcome (~90%)**, not SWAP-KILLED. Under this document's own additive
reconstruction (~+2.26 pts/deck — itself an upper-bound-ish estimate, since
the fpu_h2h rounds directly demonstrate the two surfaces overlap rather than
add), SWAP-KILLED and SWAP-UNRESOLVED are close to a coin flip. **What is true
under every prior in the table**: SWAP-SURPRISE is negligible (four to six
orders of magnitude below SWAP-KILLED), so *if* this cell resolves a
determinate direction, it is overwhelmingly likely to be SWAP-KILLED, not
SWAP-SURPRISE. The honest summary is: **KILLED is the only plausible
non-null branch, but UNRESOLVED — not KILLED — is the modal single outcome
at this n.** A round that reads SWAP-UNRESOLVED is not a wasted round: it
narrows the arb-side arithmetic prior (§0) the same way the two `fpu_h2h`
rounds did, on the record, at the direct-comparison shape nobody had played.

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
  any branch of this round.** If a branch's rider suggests a follow-up (§4.2),
  that follow-up needs its own funding and its own prereg.
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
