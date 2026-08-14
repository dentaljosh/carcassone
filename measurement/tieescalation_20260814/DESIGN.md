# TIE-TRIGGERED SEARCH ESCALATION ("the vart") — PRE-GATE DESIGN

> **STATUS AT WRITING: DESIGN, COMMITTED BEFORE ANY LADDER SEARCH RAN.** The
> read-rule ([READ_RULE.md](READ_RULE.md)) and the instrument
> (`scripts/tiletie/escalation_ladder.py`, `tests/test_tieescalation.py`) are
> committed in the same pre-run commit; git history proves the ordering.
> 0 games this round; `governance/PRODUCTION.yaml`, `BAND_REGISTRY.csv` and
> `experiments/results.csv` untouched; no band claimed.

Proposed by Joshua 2026-08-14, verbatim: *"if theres a tie at search 11k,
search like 10x in those cases?"* This is the **search-side successor** to the
tile-tie leaf-term route, which is closed (two failed menus —
`measurement/tiletie_term_20260814/` G-FAIL and
`measurement/tiletie_mining_20260814/` G2-SCREEN-FAIL — plus the reach bound:
~38% of the oracle spread is invisible to ANY static afterstate function, and
157/522 tie pools are indistinguishable across all 38 mined descriptors).

## 1. The question

At the pricing corpus's leaf-tied tile positions
(`measurement/tiletie_pricing_20260812/readout_POOLED/VERDICT.md`: the
champion's 11,008-sim pick leaves **+0.252 pts/tied ply on the table, z +3.43,
≈ +34.5 elo CI [+14.7, +54.7]** vs the oracle-best tied arm), does escalating
the **champion's own search** capture that headroom?

## 2. The mechanism argument — and its stated weakness

Two prior results constrain this lever (docs/LEVER_INDEX.md rows
"budget-headroom decay bound" and "phase-adaptive k schedule"):

1. **Uniform deep search above ~5504 sims/det moves picks but does not improve
   them.** The budget-headroom tightener oracle-priced the 5504-vs-11008
   disagreement set at **+0.0673 pts/disagreement (z +0.33, CI spans zero)**;
   the restated headroom above deploy is ≈ +7 elo with a bracket [−35, +49].
   Generic compute at the top of the ladder is priced ≈ 0 **on average**.
2. **The tie-pricing corpus says the champion leaves +0.252 pts/ply at
   leaf-tied plies** — a real, positive, z +3.43 residual, concentrated
   mid/late.

The hypothesis: **the residual search value concentrates at tied plies while
the average tail is dead.** If escalation-at-ties captures the headroom, the
win is *not attributable to generic compute* — generic compute is already
priced ≈ 0 on this very ladder. That is this lever's cleanest property: a
positive result here is a statement about *allocation*, not budget (CL-068's
G2 closed total budget, not allocation-within-budget — the same door
phase-adaptive k walked through).

**The weakness, stated up front:** the same top-of-ladder price collapse might
apply *at tied plies too*. The headroom-bound mechanism finding was "the decay
moved from the RATE into the PRICE" — deeper picks MOVE but do not IMPROVE.
If that mechanism is uniform across position classes, the escalated rungs
will change picks inside tie sets without capturing oracle value, and this
pre-gate will read FLAT. **That is exactly what the pre-gate measures** — it
is a direct test of "does the price collapse spare the tied class".

The house pattern (adaptive-k died at its pre-gate because the named mechanism
was flat) applies verbatim: measure the signal offline before building the
trade. 0 games.

## 3. The ladder

For each corpus position: run the production champion search config — fair
PIMC **k8×1376 = 11008, rust, `verify=True`**, profile-matched replay
(`walled` / `fixed_v1` / `app_aug2`, one process per profile since
`CARCASSONNE_FIX_R9` is import-latched) — at escalation rungs

| rung | sims/det | total sims | note |
|---|---|---|---|
| 1× | 1376 | 11,008 | base = production budget |
| 2× | 2752 | 22,016 | |
| 4× | 5504 | 44,032 | |
| 10× | 13,760 | 110,080 | Joshua's "10x" |

**Scale sims-per-det, keep k = 8.** Why: (a) k-width is a *different axis* —
the KWIDTH ladder (CL-054/060/068; KWIDTH_110K_READOUT_20260802) prices
width-at-fixed-depth separately and its optimal-k-grows-~√budget shape would
confound depth with determinization coverage; (b) the fair agent's k world
deals derive from `det_seed_base(seed, move_idx)` — **independent of sims** —
so with the seed convention below the 8 dealt worlds are IDENTICAL across
rungs and any pick change is attributable to per-world depth alone (the CRN
idiom, applied to the ladder axis); (c) the mining's steer is that the tie
signal is deck/lookahead-dependent — per-world *depth* is the axis that sees
deeper tactics.

**Replay + seed conventions — the pricing corpus's, reused exactly** (cloned
from `scripts/tiletie/champ_picks.py`, itself cloned from
`mine_disagreements._search_pick`):

- `make_production_champion("fair", game=game,
  seed=match.agent_seed(deck_seed, seat), verify=True, **ex.factory_kwargs())`
  with `sims=<rung>` as the only override; `k_dets` stays the YAML default.
- `mirror_protocol.reseat(champ, deck_seed=…, actions=actions[:ply],
  move_idx=ply)` — mandatory; per-det seeds derive from `move_idx`.
- `resolve_execution("inherit", profile="desktop", rust_threads=1)` —
  throughput from the outer Pool, never inner threads.
- Root replayed with `root_replay.replay_actions` and checksum-asserted
  against the corpus row BEFORE searching.
- Leaf env = the canonical `_CANON_ENV` block, byte-identical to
  `oracle_score_pilot` / `eval_fair_puct`.

Because seed and worlds are identical to the corpus's `champ_picks.py` run,
the base rung on `selfplay` positions should reproduce the corpus champion
pick bit-exactly — reported as a free integrity witness (not a gate: code-rev
drift since 08-12 could legitimately move it).

## 4. The statistic

Per position `p`, per rung `r`: `pick_r` = the rung's chosen action, resolved
to a scored arm by (i) exact membership in `ARMS.json` arms, else (ii) the
census afterstate transposition map (`action_groups` → surviving
representative — a duplicate arm's oracle value is identical *by board
identity*), else **unresolved** (the escalated search left the scored set).
`oracle[a]` = the arm's mean over all M=32 CRN worlds (the corpus's own
scores; join on arm identity, `term_gate.load_oracle_means` conventions).

- **Numerator (the measured quantity):**
  `capture_pts[p,r] = (oracle[pick_r] − oracle[pick_base]) · scale_all[p]`
  (the corpus's all-plies scale: analytic-zero positions enter as their
  population share, exactly as in the pricing readout). Unbiased: the rung
  searches never see the CRN scoring worlds, so picks cannot select on oracle
  noise.
- **Denominator (the honest base-rung regret):** winner's-curse-corrected via
  the pricing run's parity-split idiom — split the 32 worlds into halves A/B;
  `regret_half = mean_B(argmax over arms of mean_A) − mean_B(pick_base)`;
  symmetrized over both directions and both parity conventions (so the
  I1-parity-base ambiguity cannot matter), × `scale_all`. A naive
  argmax-over-all-32 denominator is curse-inflated ~5× (the pricing run
  measured it) and would deflate capture; the parity split is the corpus's own
  honest-ceiling convention.
- **CAPTURE ratio per rung** = `mean_p(capture_pts[·,r]) /
  mean_p(honest_regret[·])` — ratio of means (per-position ratios are
  unstable at regret ≈ 0), positions pairwise-excluded where `pick_base` or
  `pick_r` is unresolved (coverage reported per rung).
- **Inference on the numerator:** cluster-robust se on `root_id`,
  `z = mean/se`. All aggregation dev-slice-only until the read-rule's holdout
  branch fires.

Also reported per rung: pick-change rate vs base (afterstate-level and raw
action-level), out-of-scored-set rate, raw pts/ply recovered, median + mean
wall secs (⚠️ contended-box caveat: a 6-worker calib job shares the box;
ratios indicative, absolute timings not a bench).

## 5. Dev / holdout discipline

- **Dev slice = the mining's 522 positions / 279 roots** (the corpus minus
  `measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json`, seed 2026081402).
  The full ladder runs on dev only. Nothing is tuned on the holdout.
- **Holdout = the unburned 211 positions / 120 roots.** Opened exactly once,
  only on a dev FUND, only at {base, the single named rung}. The read-rule
  pre-commits the bars, the rung-selection rule (SMALLEST rung clearing the
  bar — the budget-headroom lesson says value concentrates early; never the
  argmax), and the flat branch. See [READ_RULE.md](READ_RULE.md).
- Disclosed: attempt 1's gate read these holdout positions for a *different,
  guessed leaf menu*; the mining firewall protects against *that program's*
  selection. This program (search-side, no feature shopping) has never read
  them, and its dev ladder cannot select on them.

## 6. Cost accounting for a future deploy (informational — no games here)

- Wall-clock per rung measured by the ladder (above).
- **Trigger:** an exact leaf tie among top arms at the root is detectable
  PRE-search for the cost of ~A leaf calls on the afterstates (the census's
  own `tie_exact` computation — negligible vs 11,008 sims). Realized
  frequency: **66.0% of champion tile plies** (census, 2,607 plies), 22.96
  tied tile plies/game.
- **Deploy-time budget multiplier estimate** (to be finalized with realized
  numbers in the readout): with tile-decision search ≈ half a turn's search
  cost (the fair agent's meeple decision runs its own sims) and escalation
  only at detected tile ties: `mult(r) ≈ 1 + 0.66 · 0.5 · (r−1)` → ~1.33× at
  2×, ~2.0× at 4×, ~4.0× at 10×. A deploy design would also weigh phase
  gating (the spread lives mid/late) to cut this.
- **If dev passes**, the deploy sketch (NOT drafted further here) needs a
  **UNIFORM-ESCALATION CONTROL ARM at matched wall-clock** (2 cells): the
  `ms_ratio` confound must be priced by a control, not argued away — a
  tie-escalated champion spends more time, and "more time uniformly" must be
  shown inferior to "more time at ties" at the same clock. Standing workers:
  laptop W22 / local W30.

## 7. Threats

1. **In-family oracle** (inherited verbatim from the pricing design): the
   ruler is `clair-puct` over the same leaf. A FLAT here closes "capture
   visible to this oracle", not "capture in truth" — and a flat would point at
   the oracle's in-family bias, or at k-width/determinization, as the
   remaining explanations of the +0.252 spread. Said explicitly in the
   read-rule's flat branch.
2. **Escaping the scored set:** an escalated search may pick an action with no
   oracle score (outside the deduped tie set ∪ corpus champ arm). Handled by
   pairwise exclusion + a coverage floor in the read-rule; the direction of
   the induced bias is unknown and reported, not argued away.
3. **Selection-on-ties regression to the mean** (pricing §6.5) — protects the
   flat branch, threatens the fund branch; unchanged.
4. **92% `walled` self-play corpus** — inherited.
5. **Offline capture ≠ deploy elo** — a FUND licenses a deploy *prereg* with
   the §6 control arm; it does not price the deploy cell.
6. **Contended box** — pick determinism is unaffected (rust search,
   fixed seeds); wall-clock is indicative only.

## 8. Governance

Measurement only. 0 games; no `results.csv` row, no band claim, no claim id,
`governance/PRODUCTION.yaml` untouched. A LEVER_INDEX row is added regardless
of outcome. Outputs land in this directory: `LADDER_READOUT.{md,json}` (dev),
`HOLDOUT_CONFIRM.{md,json}` (only on a dev FUND), `records/` per-position
search picks, `manifest.json` per phase.
