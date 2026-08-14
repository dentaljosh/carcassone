# k-WIDTH / DETERMINIZATION AT TIED PLIES ("the wart") — PRE-GATE DESIGN

> **OUTCOME STAMP (post-hoc, 2026-08-14): the ladder ran and fired
> [READ_RULE.md](READ_RULE.md) branch `W-FLAT` —
> [LADDER_READOUT.md](LADDER_READOUT.md): no rung clears the committed bars
> (ratio ≥ 0.35 ∧ z ≥ +2 ∧ coverage ≥ 0.85). Expansion R1/R2/R3 read
> +0.114 / +0.257 / +0.090 of the base regret at z +0.73 / +1.67 / +0.51; the
> **ISO-BUDGET** controls C1/C2 read +0.093 / +0.303 at z +0.50 / +1.44. The
> ladder is **not monotone in budget** — the budget-matched C2 carries the
> largest central of any rung, larger than R3 at 8× the budget, and changes
> the most picks (36%) — the signature of noise around a small positive
> rather than of a budget mechanism. §2's stated weakness is what the data
> shows: extra worlds MOVE picks at tied plies without IMPROVING them, just
> as extra depth did. ⚠️ Scope: a funding verdict, NOT an exclusion — no
> rung's 95% ratio interval sits below the bar. The 30% holdout was NEVER
> opened and stays unburned. The axis closes per the read-rule.**

> **STATUS AT WRITING: DESIGN, COMMITTED BEFORE ANY LADDER SEARCH RAN.** The
> read-rule ([READ_RULE.md](READ_RULE.md)) is committed in the same commit; the
> instrument (`scripts/tiletie/kwidth_ladder.py`, `tests/test_kwidth_ladder.py`)
> in the commit immediately after, still before any search. Git history proves
> the ordering. 0 games this round; `governance/PRODUCTION.yaml`,
> `governance/BAND_REGISTRY.csv` and `experiments/results.csv` untouched; no
> band claimed; no claim id.

This is the **second and last named explanation** of the tile-tie headroom,
run under the same corpus, the same statistic and the same bars as its sibling
the **vart** (tie-triggered search escalation,
`measurement/tieescalation_20260814/`), which closed **E-FLAT** earlier today.

## 1. The question

At the pricing corpus's leaf-tied tile positions
(`measurement/tiletie_pricing_20260812/readout_POOLED/VERDICT.md`: the
champion's 11,008-sim pick leaves **+0.252 pts/tied ply on the table, z +3.43,
≈ +34.5 elo CI [+14.7, +54.7]** vs the oracle-best tied arm), does giving the
champion's search **more determinization WORLDS** capture that headroom —
and specifically, does it do so **at the SAME total budget**?

## 2. The mechanism argument

Three prior results box this in.

1. **The leaf-term route is closed.** Two failed menus
   (`measurement/tiletie_term_20260814/` G-FAIL,
   `measurement/tiletie_mining_20260814/` G2-SCREEN-FAIL) plus the reach bound:
   ~38% of the oracle spread is invisible to ANY static afterstate function,
   and 157/522 tie pools are indistinguishable across all 38 mined descriptors.
2. **Deeper SAME-SHAPE search is closed** (the vart, today,
   `measurement/tieescalation_20260814/LADDER_READOUT.md`): scaling sims/det at
   fixed k = 8 to 2× / 4× / 10× captures **−0.034 / +0.176 / +0.179** of the
   base rung's honest regret at z **−0.26 / +1.00 / +0.84** — saturating, never
   near the 0.35 ∧ z +2 bar. Deeper search MOVES picks at tied plies
   (18 / 24 / 31 % pick-change) but does not IMPROVE them. Its close-out names
   **k-width / determinization** as a remaining explanation.
3. **Generic budget at the top of the ladder is priced ≈ 0 on average**
   (docs/LEVER_INDEX.md "budget-headroom decay bound": +0.0673
   pts/disagreement, z +0.33, CI spans zero for 5504-vs-11008).

The hypothesis this pre-gate tests: **the oracle SEES the deck; the champion
marginalizes over only 8 sampled worlds. The missing ingredient may be WHICH
WORLDS, not how deeply each is searched.** At a leaf-tied ply the arms are by
construction indistinguishable to the static evaluator, so the pooled decision
rests entirely on what the k sampled futures happen to contain — exactly the
place where an 8-world sample should be thinnest.

### 2.1 The prior that must be confronted: phase-adaptive k

docs/LEVER_INDEX.md row **"phase-adaptive k schedule"** died at its own
pre-gate 2026-07-28 with a directly adjacent finding: over all 898 CL-070 roots
at the production budget, the across-world VALUE SPREAD is flat by phase
(0.092 / 0.096 / 0.092, every |z| < 0.6) and — the decision-relevant version —
**worlds 3–4 change the POOLED pick only 7.0 / 6.1 / 8.4 % of the time
(z −0.59)**. It also measured **0.00 % duplicate worlds for every
k_remaining ≥ 8**.

**That census's finding was ON AVERAGE, over all live decisions. This
pre-gate's hypothesis is specifically AT LEAF-TIED PLIES, which that census
did not condition on.** A class that is 66.0 % of champion tile plies and
carries a +0.252 pts/ply oracle residual can host a width effect that averages
away in the pooled population — that is precisely the allocation logic the
vart was built on (CL-068's G2 closed TOTAL budget, not
allocation-within-budget). It is also the reason the adaptive-k row's own
re-open bar ("a DIFFERENT per-decision statistic … shown to move the POOLED
pick") is not violated here: this is a different conditioning set and a
different statistic (oracle capture, not value spread).

**The weakness, stated up front:** adaptive-k's flat pooled-pick-change census
is a real prior *against* this lever, and the vart's own reading — that at
tied plies extra search MOVES picks without IMPROVING them — may be a property
of the tied class rather than of the depth axis, in which case extra worlds
will move picks and capture nothing. **That is exactly what this pre-gate
measures.**

## 3. The ladder — and the load-bearing iso-budget control

Same search conventions as the vart, clone-for-clone (§3.2). The ONE axis that
changes vs the vart: **scale k at fixed sims/det**, plus **iso-budget
reallocation controls**.

| rung | k_dets | sims/det | total sims | role |
|---|---|---|---|---|
| **R0** | 8 | 1376 | **11,008** | **base = production champion of record** |
| R1 | 16 | 1376 | 22,016 | width expansion (2× budget) |
| R2 | 32 | 1376 | 44,032 | width expansion (4× budget) |
| R3 | 64 | 1376 | 88,064 | width expansion (8× budget) |
| **C1** | 16 | 688 | **11,008** | **ISO-BUDGET control** — pure reallocation |
| **C2** | 32 | 344 | **11,008** | **ISO-BUDGET control** — the pre-named attribution rung |

**Why the iso-budget rungs are the design's point.** With the vart's result in
hand, the 2×2 of "more compute, how spent" is completed by this run:

| | more total budget | same total budget |
|---|---|---|
| **via depth** (sims/det) | **FLAT** — the vart, today | (that is the base) |
| **via width** (k_dets) | R1 / R2 / R3 — measured here | **C1 / C2 — measured here** |

R1–R3 confound "more worlds" with "more budget via worlds"; the vart already
priced "more budget via depth" as flat, so a win confined to R1–R3 would be a
budget statement in width's clothing. **C1/C2 are the separator**: they buy
worlds by *selling depth*, at exactly the champion's 11,008 sims. A capture at
C1/C2 is a statement about ALLOCATION — deployable at **zero extra
wall-clock** — and is the only reading this program will call a fundable
mechanism. C2 (k32 × 344) is the pre-named rung; **C1 (k16 × 688) is included
so the iso-budget axis is BRACKETED rather than settled from one off-baseline
sample** (standing rule: never settle an axis from a single point). Both are
committed here, before any number; neither is a menu to shop from — the
read-rule's attribution test names them jointly in advance.

### 3.1 CRN along k: the worlds are NESTED (a free, exact property)

Read off `fair_agent._pimc_move` (and mirrored by `rust_agent`), not assumed —
the same three facts `scripts/measurement_infra/kwidth_agreement_probe.py`
documents:

1. the determinization worlds come from ONE stream,
   `det_rng = random.Random(det_seed_base(move_idx) + 1)`, consumed by k
   sequential `reshuffled_determinization` calls, and `det_seed_base` depends
   on **(agent seed, move_idx) only** — not on k, not on sims;
2. world *i*'s search seed is `det_seed_base + 100 + i` — also
   k-independent and sims-independent in its derivation;
3. pooling is `_merge_root_stats` in world order 0..k−1 with a constant
   `min_pooled_visits`.

Therefore **at fixed sims/det, the k=16/32/64 runs contain the base's 8 worlds
as an exact prefix** — R1/R2/R3 are strict evidence supersets of R0, and any
pick change is attributable to the ADDED worlds alone. This is the CRN idiom
applied along k, and it is stronger than the vart's (whose rungs shared worlds
but re-searched them).

⚠️ **C1/C2 are deliberately NOT nested with the base**: they hold the same
world *stream* (worlds 0..15 / 0..31 of the same sequence, so R0's 8 worlds are
still a prefix of the world set) but search each world at 688 / 344 sims
instead of 1376. C1/C2-vs-base therefore confounds "+8 (+24) worlds" with
"−½ (−¾) depth per world" **by construction — that confound IS the trade being
priced**, and its two halves are separately identified by the vart (depth) and
R1/R2 (width-with-budget).

### 3.2 Replay + seed conventions — the vart's, reused exactly

- `make_production_champion("fair", game=game,
  seed=match.agent_seed(deck_seed, seat), verify=True, **ex.factory_kwargs())`
  with `sims=<rung sims/det>` **and `k_dets=<rung k>`** the only overrides
  (the factory stamps `runtime_budget_override`; `fair_deploy` stays the
  PRODUCTION.yaml intent).
- `mirror_protocol.reseat(champ, deck_seed=…, actions=actions[:ply],
  move_idx=ply)` — mandatory; per-det seeds derive from `move_idx`.
- `resolve_execution("inherit", profile="desktop", rust_threads=1)` —
  throughput from the outer Pool, never inner threads.
- Root replayed with `root_replay.replay_actions` and checksum-asserted
  against the corpus row BEFORE searching.
- One process per rules profile (`walled` / `fixed_v1` / `app_aug2`;
  `CARCASSONNE_FIX_R9` is import-latched).

**Two free integrity witnesses, reported, neither a gate:** (i) the R0 pick vs
the corpus champ pick on `selfplay` (the vart read 485/485); (ii) the R0 pick
vs **the vart's own R0 record for the same rid** — identical code path,
identical seeds, so any disagreement is a harness alarm.

## 4. The statistic — the vart's, unchanged

Per position `p`, per rung `r`: `pick_r` resolved to a scored arm by (i) exact
membership in `ARMS.json` arms, else (ii) the census afterstate transposition
map (a duplicate arm's oracle value is identical *by board identity*), else
**unresolved**. `oracle[a]` = the arm's mean over all M=32 CRN worlds.

- **Numerator:** `capture_pts[p,r] = (oracle[pick_r] − oracle[pick_base]) ·
  scale_all[p]` (the corpus's all-plies scale). Unbiased: the rung searches
  never see the CRN scoring worlds, so picks cannot select on oracle noise.
- **Denominator:** the symmetrized parity-split honest regret of the base pick
  (winner's-curse-corrected; a naive argmax-over-32 denominator is
  curse-inflated ~5×), × `scale_all`.
- **`capture_ratio_r`** = ratio of means; positions pairwise-excluded where
  `pick_base` or `pick_r` is unresolved (coverage reported per rung).
- **Inference:** cluster-robust se on `root_id`, `z = mean/se`.

The instrument imports these routines from `scripts/tiletie/escalation_ladder.py`
rather than re-deriving them, so the two programs' numbers are commensurable
by construction.

Also per rung: pick-change rate vs base (arm-level and raw action-level),
out-of-scored-set rate, median/mean wall secs, and the deploy multiplier
(≡ **1.00** for C1/C2 by construction).

## 5. Dev / holdout discipline

- **Dev slice = the vart's, the mining's 522 positions / 279 roots** (the
  corpus minus `measurement/tiletie_mining_20260814/HOLDOUT_ROOTS.json`,
  seed 2026081402). The full ladder runs on dev only.
- **The 211-position / 120-root holdout is NOT OPENED BY THIS PROGRAM UNDER
  ANY BRANCH.** It survived the vart unburned and it survives this run
  unburned. On a fund branch, the one-shot holdout confirm is *named as the
  licensed next step* and left for a fresh read-rule with owner
  authorization — it is not executed tonight. The instrument has no holdout
  code path at all.
- Corpus reuse framing, as the vart framed it: this is a **pre-named single
  intervention** (scale k at fixed sims/det, with iso-budget reallocation
  controls), committed in full before any number, not a menu shopped after
  seeing the data. The corpus has now served two search-side pre-gates with
  the same statistic and the same bars; the multiplicity that carries is
  2 programs × their pre-registered rungs, disclosed here.

## 6. Cost — priced BEFORE the run, from the vart's realized numbers

The vart's realized dev manifest (`manifest_search_walled_dev.json`): **487
positions × 4 rungs in 1008.2 s wall at W22**, with realized per-position
medians 2.4 / 4.8 / 9.4 / 24.9 s = **41.5 s/position serial** ⇒ ~20.0×
effective parallelism at W22.

This ladder's aggregate sims per position is
11,008 + 22,016 + 44,032 + 88,064 + 11,008 + 11,008 = **187,136** — which is
**exactly** the vart's aggregate (11,008 + 22,016 + 44,032 + 110,080 =
187,136). At the vart's realized throughput the honest ETA for all 522 dev
positions across the three profiles is therefore **≈ 18–19 minutes at W22**.

**Decision on k = 64, recorded before any number: it STAYS.** The arithmetic
above prices the full 6-rung ladder at one vart-equivalent. Even carrying a
2× safety surcharge for per-world overhead (k=64 pays 64 determinization
deepcopy+reshuffles, and C2 pays 32 of them against only 344 sims each, so
cost is super-linear in k at fixed total sims) the run lands **≤ 40 minutes**,
far inside the overnight window. If the surcharge were to prove worse than
that, the resume-able per-position records mean k=64 could be dropped by
re-analysing on the remaining rungs without re-running anything — but on the
priced arithmetic no such drop is expected and none is planned.

**Deploy-cost note (informational, no games here):** for R1–R3 the
tie-triggered deploy multiplier follows the vart's formula
`mult ≈ 1 + 0.660 · 0.5 · (total/11008 − 1)` → ~1.33× / 2.0× / 3.3×. **For
C1/C2 it is exactly 1.00×** — an iso-budget win costs nothing at deploy,
which is why the read-rule treats C1/C2 as the only fundable reading.

## 7. Threats

1. **In-family oracle** (inherited verbatim from the pricing design): the
   ruler is `clair-puct` over the same leaf. A FLAT here closes "capture
   visible to this oracle", not "capture in truth". With the term route and
   the depth route already closed, a flat here narrows the remaining
   explanation of the +0.252 pts/ply to **judge artifact** (the oracle's
   in-family bias) — said explicitly in the read-rule's flat branch, and the
   out-of-family re-pricing running in parallel is the instrument that would
   settle it.
2. **Escaping the scored set:** a wider search may pick an action with no
   oracle score. Handled by pairwise exclusion + a coverage floor; the
   direction of the induced bias is unknown and is reported, not argued away.
   ⚠️ This is expected to bite HARDER here than in the vart (whose
   outside-scored rate rose 9 % → 20 % across its ladder): more worlds is a
   pick-diversifying axis, and the coverage floor is the guard.
3. **World duplication at high k:** the adaptive-k census measured 0.00 %
   duplicate worlds for k_remaining ≥ 8 but 26 % at k_remaining = 5 and 100 %
   at 3. Late-game positions therefore saturate: k = 64 cannot deal 64
   distinct worlds from a 5-tile unseen deck. This makes R3 (and to a lesser
   extent R2/C2) a *weakly* increasing evidence set late, biasing this
   pre-gate toward FLAT at the top of the ladder. Reported, not corrected.
4. **Selection-on-ties regression to the mean** (pricing §6.5) — protects the
   flat branch, threatens the fund branch; unchanged.
5. **92 % `walled` self-play corpus** — inherited.
6. **Offline capture ≠ deploy elo** — a fund licenses a *prereg*, not a deploy.
7. **Contended box** — pick determinism is unaffected (rust search, fixed
   seeds); wall-clock is indicative only.

## 8. Governance

Measurement only. 0 games; no `experiments/results.csv` row, no band claim, no
claim id, `governance/PRODUCTION.yaml` and `governance/BAND_REGISTRY.csv`
untouched, under every branch. A docs/LEVER_INDEX.md row is added regardless
of outcome. Outputs land in this directory: `LADDER_READOUT.{md,json}`,
`records/` per-position picks, `manifest_search_*.json` per profile.
