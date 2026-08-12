# SIMS-SPLIT SCREEN — fixed-total phase reallocation vs the champion, PRE-REGISTRATION (DRAFT)

> **STATUS: DRAFT — NOT LAUNCHED. X now PROPOSED from the census readout; the band is still
> unfilled and the launch decision is OPEN.** Written with the play-time knob build
> (2026-08-12). Before game 1, in the same commit as the launch: **(1) confirm X** (§2 now
> carries a census-derived proposal, not a blank) and **(2) claim the fresh deck band** in
> `governance/BAND_REGISTRY.csv`. `governance/PRODUCTION.yaml` is untouched on every branch
> of this document; a screen licenses a *confirm*, never a promotion.
>
> ⚠️ **THE CENSUS RAN (2026-08-11 late) AND FIRED BRANCH `U` — PARK-WITH-DECISION, NOT S1.**
> Launching this screen is therefore an ORCHESTRATOR CALL, not an automatic consequence of
> the gate. What the census established
> (`measurement/simsplit_census_20260811/READOUT.md` — landed on `android-app` in `f0845a3`,
> one commit ahead of this build branch, so the link is written as a path until the merge):
> * **S1 did NOT fire.** Its confound-immune half was the absolute meeple bar `M344 ≤ 5%`;
>   actual **M344 = 13.07%, CI95 [10.10, 16.73]** — missed ~2.6×. **The "free lunch" framing
>   is refuted**: a 4× meeple cut moves one meeple decision in eight, so there is no wasted
>   budget simply lying there.
> * **The comparative claim survived, strongly.** Tiles are hungrier than meeples and it is
>   not the action-count confound: the tile flip rate exceeds the meeple rate in **all four
>   gap-matched bins at every rung** (344-rung bin z's 1.67 / 3.59 / 4.32 / 2.09 — direction
>   unanimous, but the lowest-gap bin does not clear 2σ; quote the bins, not a blanket claim).
> * **The meeple flips are overwhelmingly coin-flips** (secondary read): 71% of them (37/52)
>   sit in the near-tied `[0, 0.02)` gap bin, and above gap 0.05 the meeple search produces
>   5 flips in 225 roots. The meeple flip rate is nearly flat across an 8× budget range
>   (14.07 → 13.07 → 11.56%) while the tile rate falls steeply (35.21 → 27.71 → 18.54%).
>
> ⇒ The lever is no longer a free lunch; it is a **TRADE**, and this screen exists to price
> it. The census cannot (ladder descends only; flip rate ≠ regret).

Pre-gate census: [PREREG.md](../simsplit_census_20260811/PREREG.md) ·
`measurement/simsplit_census_20260811/READOUT.md`. The lever: docs/LEVER_INDEX.md §5
*"phase-asymmetric sims split (tile vs meeple budget within a turn)"*.

## 1. The knob (built, gated — 2026-08-12)

`FairHeuristicPriorAgent(sims_tile=, sims_meeple=)` and `RustFairAgent(sims_tile=,
sims_meeple=)` via `champion_factory.build_fair_champion`, exposed as
`eval_fair_puct.py --sims-tile / --sims-meeple` (CANDIDATE side only; `_make_opponent`
never forwards). Rust implementation = a **stateless per-call `sims_override`** on
`FairAgentRs.choose_action` (config never mutated; mirror protocol untouchable by
construction; `last_move()["sims_used"]` is the per-move evidence). Gate:
`tests/test_simsplit_knob.py` — knobs-unset full-game byte-identity vs the pre-change
golden (`tests/golden/simsplit_off.json`, python AND rust, latch included), per-phase
equality against uniform-budget control agents, python↔rust full-game parity with the
knobs SET, and the exact-K≤2 latch invariance.

## 2. Cells

| side | config |
|---|---|
| **candidate** | production champion (curve125 leaf a36d2e15, c1.5/τ5/float/visits, fair PIMC k_dets=8, exact-K≤2 marginalized) with **(sims_tile, sims_meeple) = (1376+X, 1376−X)** |
| **baseline** | the UNMODIFIED champion: k8×1376 symmetric (`PRODUCTION.yaml fair_deploy`) |

**X = 1032 PROPOSED ⇒ (sims_tile, sims_meeple) = (2408, 344).** Not a blank and not a free
choice: it is the census readout's own sizing recommendation (§4b, *"the reallocation ladder
should be sized aggressively (meeple → 344), because the marginal meeple sim demonstrably
buys the least where the search is least decided"*), and it is the readout's arithmetic —
344 is the census's ¼ rung, and the meeple decision's ~58% share of turn time is what turns
that cut into 1376 → ~2400 on the tile side. Candidate per-turn total =
8×2408 + 8×344 = **22016 = the champion's own per-turn total (8×1376 + 8×1376)** — the
reallocation is exactly budget-neutral by construction, which is why no equal-wall-clock
caveat is owed (§4).

⚠️ **Confirm X before launch.** It is the aggressive end of the ladder, chosen on a
SECONDARY (gap-stratified) read; the PRIMARY statistic says the cut costs 13.07% of meeple
picks. A milder rung (X = 688 ⇒ 2064 / 688, the census's ½ rung, meeple cost 11.56%) is the
conservative alternative and is the natural second cell if the aggressive one reads
negative. Pick ONE for the screen — this is a screen, not a sweep.

Backend: **rust both sides** (`--backend rust`, the champion's execution backend of
record); `--rust-threads` unset (farm rule: threads=1 per worker). Rules profile:
**fixed_v1** (the profile of record for new confirmatory work). Both sides the same leaf,
same endgame, same k_dets; the ONLY difference is the candidate's within-turn budget shape.

## 3. Design

- **n = 200 deck-paired** (100 fresh decks × 2 seats), one band, within-band — the robust
  contrast class. Band: **TODO-AT-LAUNCH** (fresh, claimed in BAND_REGISTRY.csv in the
  launch commit; retired from confirmatory use after this screen).
- **Primary statistic: deck-paired margin z** (points/deck, paired by deck+seat-swap).
  Elo is reported but the margin resolves (the CL-072 lesson).
- Harness: `eval_fair_puct.py --info fair --opponent fair-champion --paired`, candidate
  knobs `--sims-tile 1376+X --sims-meeple 1376−X`; manifest auto-stamps the `sims_split`
  block (both raw knob values + effective budgets + per-turn totals).

**Branch map (house):**

| condition | verdict | action |
|---|---|---|
| paired-margin \|z\| ≥ 2 | resolved at screen resolution | sign + → fund an n=400 confirm on a second fresh band (still no promotion without it); sign − → lever dies, LEVER_INDEX → measured-dead |
| 1.5 ≤ \|z\| < 2 | suggestive | top-up to n=400 on the SAME band (pre-registered here, so no garden-of-forking-paths), then re-read this map once |
| \|z\| < 1.5 | null at screen resolution | park; LEVER_INDEX row records the bound (~±35 elo unpaired / ~±25 paired at n=200, 2σ) — a small true effect is NOT excluded |

## 4. Cost + clock note

**No equal-wall-clock caveat is owed**: the candidate does the SAME total sims per turn as
the baseline by construction (§2). **But the measured ms/move ratio must still be
reported** (`champ_prefix_ms_per_move` both sides, from the manifests/summary): per-sim
cost is not phase-symmetric (meeple positions have fewer legal actions per expansion), so
budget-neutral in sims is only approximately clock-neutral, and the readout must say by
how much (report the ratio; if it leaves [0.9, 1.1] the readout owes a wall-clock
paragraph, house convention from the reuse_tree adopt).

Cost estimate: both sides ≈ champion-budget fair games (~22016 sims/turn/side). Use the
lever-menu campaign's per-game figures on the current two-box envelope for the ETA at
launch; n=200 is the same shape as the menu screens that ran 2026-08-10/11.

## 5. What this screen cannot say (carried into the readout)

1. **Self-anchored** — a head-to-head vs our own champion; it moves neither structural
   blocker and licenses no absolute claim.
2. **One split value** — X is a single point, not a swept axis; a null kills THIS X, not
   the lever (though a census-guided X failing is strong discouragement); a win licenses
   an X-bracket before any fold (the bracketing rule: a peak at an untested neighbour is
   not a peak). The census's own branch was **`U` (park-with-decision)**, so this screen is
   a priced-trade probe of a parked lever, not the discharge of a fired gate.
5. **The knob is exclusive with three neighbours** (`parallel_workers`, `intra_reuse`,
   `oracle_prior_mult`) — each rejected loudly at construction. In particular the split
   candidate cannot ride the python spawn split; on `--backend rust` this costs nothing
   (the farm runs threads=1 per worker anyway).
3. **Flip-rate ≠ elo** (census §4): the census licensed this *measurement*, nothing more.
4. **Within-turn shape only** — no adaptivity (per-position budgets are the adaptive-k
   lever's territory, killed separately; see LEVER_INDEX).
