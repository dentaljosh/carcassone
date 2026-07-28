# The clairvoyant champion as a fixed strength reference — scoping memo

**Question posed:** "We're not exactly sure of the knee of sims above our champion. But we
do have a clairvoyant version of our champ — maybe he'd make a good reference." I.e. play
fair champions at increasing budgets against a *fixed* clairvoyant champion and watch where
the win-rate curve flattens.

**Verdict up front: CONDITIONAL — and the conditional part is not the one you'd expect.**
The idea is sound, is already 80% built, and is *not* a duplicate of anything on record.
But as a **game-playing opponent** it is ~5× underpowered for the knee question, and that
is measured, not guessed (CL-060 ran exactly this design shape and got z=0.86 on a real
effect). The version of the idea that is worth funding is the **same agent used as a
move-scoring oracle rather than an opponent** — which is precisely the "stronger reference"
the move-agreement pre-registration already named as its successor, and for which the
clairvoyant champion is the best available instrument.

---

## 1. Prior art

### 1.1 Has a clairvoyant agent been used as a strength REFERENCE before? — YES, extensively, but never *this* clairvoyant agent.

The program's **ruler of record** since 2026-07-09 is literally "fair candidate vs a fixed
clairvoyant opponent". It just uses a *weak* clairvoyant opponent (HeuristicMCTS h800),
not the champion.

- `docs/LEVER_INDEX.md:138` — *"fair PIMC vs clairvoyant play · `--fair` · `FairHeuristicPriorAgent`
  · `eval_fair_puct.py` · 'the clairvoyance tax' — TRIED … the fair sub-ladder is the **ruler of record**"*
- The ladder itself, `experiments/results.csv:291-294` (`fair_ladder_s{800,1600,2752,5504}_vs_h800_k2`,
  CL-046, n=200 paired each, band 15e9): fair champion at 800/1600/2752/5504 vs a **fixed
  clairvoyant h800 rung** → **+27.9 / +61.4 / +81.4 / +149.3 elo.**
- The companion clairvoyant ladder, `results.csv:296-299` (CL-048): **+177 / +153 / +210 / +249**
  against the same fixed rung.

So the design pattern "fair ladder vs a fixed clairvoyant reference" is the house standard.
The new content in the user's idea is **swapping the rung up from h800-clair to
champion-clair** (~+210 elo stronger on the h800 ruler).

### 1.2 Has *the clairvoyant champion* specifically been proposed as the reference? — NO. This is genuinely new.

Greps of `docs/LEVER_INDEX.md`, `DECISIONS.md`, `BACKLOG.md`, `experiments/results.csv`, and
`docs/PROGRAM_ROADMAP_2026-07-07.md` (parking lot included) find the clairvoyant champion in
**four** roles, none of them "fixed reference":

| role | where |
|---|---|
| **candidate / dev ruler** — clairvoyant strength ladder, later demoted as a Goodhart trap | `results.csv:283-285`, `results.csv:296-299`; DECISIONS 2026-07-09 |
| **screen stage** — clair screen → mandatory fair confirm (T3/Optuna, F2/oracle-priors, C5 leaf) | `docs/LEVER_INDEX.md:92,148`; CL-051/054/057/059 |
| **tax denominator** — clair minus fair = the ~128–156 elo clairvoyance tax | CL-045/CL-048 |
| **snapshot substrate** — Gate-B depth transfer used the clairvoyant champion core because snapshot search is bit-exact for it | `results.csv:369` |

The nearest miss is `eval_fair_puct.py:2238-2244`, which *anticipates* a clairvoyant-vs-fair
head-to-head and warns about how to read it — but no such cell has ever been run.

### 1.3 The measured clairvoyance gap — is there headroom?

`measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md` (CL-022, 2026-06-18) measured the gap
at **+26.6 elo** — but that is a **stale number for a dead agent** (the neural iter8 at
sims=200, K=12). It has been superseded twice:

- **CL-045** (`results.csv:281-282`, 2026-07-07): clair **+205.0** vs fair **+49.0** on the
  same rung ⇒ **tax ≈ 156 elo**, ~6× the CL-022 figure.
- **CL-048** (`results.csv:296-299`, 2026-07-09), n=200 CRN, tax at each budget:
  **+149.4 @800 · +92.0 @1600 · +128.5 @2752 · +99.8 @5504** ⇒ *"the tax PERSISTS ~100–150
  across a 7× sims range, does NOT close with search."*

**Headroom answer: good.** At the deploy budget the fair champion is ~**−128 elo** against a
clairvoyant version of itself ⇒ expected **wr ≈ 0.325**. That is comfortably off both
saturation ends. (Contrast the ruler that is currently in use: fair champ vs RoD-v2 sighted
sits at wr 0.675, and vs tier-1 greedy at wr 0.940 where σ blows up to ±51.7 —
`results.csv luckfloor_champ_k4x688_vs_greedy_n200_b54e9`.)

### 1.4 Is the harness already capable? — YES, zero code required.

`scripts/classical_search/eval_fair_puct.py`:
- `:1056` `OPPONENT_MODES = ("h800", "greedy", "fair-champion", "net", "bare-net")` — there is
  **no** `clair-champion` opponent mode.
- **But the seats can be swapped.** `:1047-1049` builds the *candidate* as the clairvoyant
  champion under `--info clair` (via `champion_factory.build_clairvoyant_champion`,
  `src/carcassonne_ai/champion_factory.py:402`), and `--opponent fair-champion` +
  `--opp-sims` / `--opp-k-dets` (`:1187`, `:1198`) lets the *opponent* run any budget/width.
- `:2238-2244` explicitly blesses the combination:
  > `if args.opponent in _HEAD_TO_HEAD and args.info == "clair":` … *"a clairvoyant candidate
  > vs a fair opponent is a legitimate DIRECT tax measurement"*

So the cell is expressible **today** as:
```
--info clair --sims 688 --k-dets 4          # the FIXED clairvoyant reference (2752 total)
--opponent fair-champion --opp-k-dets K --opp-sims S   # the fair ladder rung
```
and the fair rung's elo is the **negation** of the reported candidate elo. Both sides ride
the same `cfg_dict` search knobs and the curve125 leaf, so the *only* difference is
information — a cleaner single-variable contrast than either instrument now in use.

### 1.5 The two queued alternatives

- **`scripts/classical_search/blind_curve_width11008.sh`** — never launched. It is **not** a
  knee probe: its own header says *"THIS IS A DIFFERENT QUESTION FROM THE CURVE … it is the
  k4 arm of a width contrast"* (CL-060's named #1 open test: k8×1376 vs k4×2752 at fixed 11008).
- **The solver/deeper-reference move-scoring probe** — named in
  `measurement/classical_search/MOVE_AGREEMENT_PREREG.md:405-410`: *"take the positions where
  2752 and 11008 disagree and score **both** picks against a stronger reference (the exact
  solver where `k_remaining` allows, **or a much deeper search**)."* Note the second clause —
  the clairvoyant champion is a candidate for exactly that role (§4.2).

---

## 2. Validity analysis

### 2.1 Is fair-vs-clairvoyant win-rate a usable monotone ruler? Yes — monotonicity is proven, and the floor is far away.

- **Monotonicity has been verified, not assumed.** `CLAIRVOYANCE_GAP_VERDICT.md` pre-registered
  V1 (*"nonclair ≤ clair, perfect info can't hurt"*) and it **held**.
- **The floor is not binding.** The pure hidden-information floor is the tax, ~128 elo at
  deploy ⇒ wr 0.325. Even at 4× budget the fair rung would sit around wr 0.36 on the most
  optimistic reading. Nowhere near an asymptote.
- **Statistical-compression worry is essentially void, and this cuts BOTH ways.** Using
  `se(elo) ≈ 173.7/√(n·wr(1−wr))` — which reproduces the harness's own reported σ exactly
  (n=200, wr 0.94 → 51.7, matching the luckfloor row) — the cost of sitting at wr 0.325
  instead of 0.5 is **σ 26.2 vs 24.6**. A 6% penalty. Conversely, the *current* RoD-v2 ruler
  at wr 0.675 costs only 26.2 as well.
  **⇒ The "elo compression" story (H2 in the move-agreement prereg) is NOT a statistical-ceiling
  story at these win rates.** Under a probit outcome model, dElo/dStrength at wr 0.675 is
  within ~3% of its value at wr 0.5. If the RoD-v2 curve is compressed, the mechanism must be
  **blindness** (the opponent cannot be punished by the specific mistakes budget fixes), not
  saturation — and swapping in a stronger reference **does not fix that by being stronger**,
  only by being *differently* blind.

### 2.2 The reference's own budget — a real but manageable problem.

Clairvoyant strength **scales strongly with sims and is not saturated**: `results.csv:283-285`
gives +149 / +193 / +215 at 1375 / 2750 / 5500 vs h6400, and `:296-299` gives
+177 / +153 / +210 / +249 vs h800. So the reference *must* be pinned by fiat. Pin it at
**k4×688 = 2752** (deploy budget). Two consequences to state in the pre-registration:

1. It is an **arbitrary** pin. Nothing about 2752 makes it the right reference budget; a
   different pin shifts every rung by a constant. Only *shape* (the knee), never *level*, is
   interpretable.
2. **Contamination check needed:** the reference is a fixed CPU cost, so the ms/move ratio
   swings from ~1× at the 2752 rung to ~4× at the 11008 rung. Not cost-matched — same caveat
   as the blind curve. Fine for a knee probe (budget is the axis), but it must be stated.

### 2.3 The serious objection: the clairvoyant champion is IN-LINEAGE.

This is the weakness the user should hear loudest. `governance/CLAIM_REGISTRY.csv:70` (CL-069)
states the principle: *"a self-anchored comparison structurally CANNOT see a weakness both
sides share."* The clairvoyant champion is the **same agent with one boolean flipped**:
identical curve125 leaf, identical PUCT priors, identical `c_puct`/`tau_p`/`value_norm`,
identical search code. It is out-of-lineage on **exactly one axis — information.**

So it sits *between* the two instruments already run, not beyond them:

| instrument | shares leaf? | shares search? | shares info? | verdict on the top |
|---|---|---|---|---|
| **self-anchored** (CL-068 Pareto) | yes | yes | yes | flat 1376→5504 (+12.2, z 0.70) |
| **clairvoyant champ** (proposed) | **yes** | **yes** | no | *unknown* |
| **RoD-v2 sighted** (CL-069 blind curve) | no | no | no | flat above 2064 |

If the flat top is caused by a **leaf ceiling** — the most-cited hypothesis in this repo
(`CLAUDE.md`: *"the hand-crafted leaf eval caps learned strength near strong-human by
construction"*) — a clairvoyant reference built on that same leaf **will not see it either.**
That is a substantial fraction of the hypothesis space this probe would fail to test.

### 2.4 The decisive objection: power. This exact design shape has already failed once, measurably.

`governance/CLAIM_REGISTRY.csv:61` (CL-060), on precisely the question at issue:

> *"The closure statistic (+1.12 pts/deck z=0.86 vs the deploy config) was a **delta-of-deltas
> THROUGH the fixed h800 clairvoyant rung**, which BOTH arms beat by ~9 pts/deck: **the design
> is ceiling-compressed and cannot resolve the effect.** … Re-computed correctly as a paired
> diff-of-deltas over the shared 24e9 band it is +1.123 pts/deck **se 1.304 z=0.861** in the
> candidate's favour"* — while the **direct head-to-head** of the same two agents gave
> **+49.85 ± 17.55, z 3.48.**

Read the arithmetic. To reach z=2 on a +1.123 pts/deck effect you need se ≤ 0.56 — a **5.4×
increase in games over n=400/cell**, i.e. **~2,100 games per rung.** Swapping h800-clair for
champion-clair does not buy a 5.4× variance reduction. It plausibly buys 20–30% (the margin
statistic is genuinely cleaner against a near-peer: garbage-time farm blowouts against a weak
rung inflate per-deck σ without carrying decision information). 20–30% is not 440%.

**⇒ A third-party-referenced ladder is intrinsically ~2× less powerful than the direct
head-to-head, because differencing two independent cells forfeits the deck-pairing between
the two candidates.** You buy validity with power, at a bad exchange rate.

### 2.5 And the effect you are hunting is small.

Best current estimates of the true fair strength gain above deploy:
- 2752 → 5504: **+12.2 ± 17.4** (CL-068 direct H2H, `results.csv:401`)
- 2752 → 11008: **+49.85 ± 17.55** direct H2H (CL-060), of which **budget alone = +27.85
  ± 12.43** once the k8-vs-k4 width change is separated out.
- CL-046's fair ladder (the *existing* clairvoyant-referenced instrument) claimed the top step
  2752→5504 was **+68 elo**, its biggest. CL-068 refuted that: *"This REFUTES THE SHAPE of
  CL-046's low-budget ladder … its LEVELS were already known not to transfer (k_dets=8), and
  its SHAPE does not either."* **Do not use CL-046's +68 to argue this probe will see a big
  signal — that number is the artifact this probe would be re-creating.**

So the knee, in fair elo, is roughly: flat-to-+12 at 2×, +28 (budget-only) at 4×. Resolving
±12 elo needs n ≈ 800 paired **per cell in a direct H2H**, and ~4× that through a third party.

---

## 3. Comparison to the queued alternatives

| | **clairvoyant-champ ladder** (proposed) | **blind_curve_width11008.sh** (queued) | **solver / deeper-reference move scoring** (queued) |
|---|---|---|---|
| what it measures | game-level strength vs a fixed near-peer | k8×1376 vs k4×2752 **width**, not budget | did the deeper pick *improve*, per move |
| needs an opponent? | yes | yes | **no** |
| unit of n | games (≈100–400 decks) | games (100 decks) | **positions** (265 budget-disagreements already identified) |
| elo compression | none at wr 0.33 (§2.1) | present (vs RoD-v2) | **not applicable** |
| lineage contamination | leaf + search shared | full | exact solver = **none**; deeper-search reference = partial |
| power on the real effect | **z ≈ 0.5–1.0 at n=400/cell** (§2.4) | n/a — answers a different question | z ≈ 1–2.2 depending on CRN efficiency (§4.2) |
| cost | ~7–9 h at W32 for 2 cells n=400 | ~3–4 h | dominated by oracle depth; tunable |
| code needed | **none** | none (script written) | read-out + oracle driver |
| answers "where is the knee?" | shape only, underpowered | no | **yes, directly and per-move** |

**The width script is not a competitor** — it answers CL-060's width question, not the knee.
Run it or don't on its own merits.

**The solver-scored probe strictly dominates the clairvoyant *opponent* probe** on the knee
question: no opponent means no compression confound at all, the ground truth is
non-circular where the solver reaches, and it converts "the move moved" (CL-070's finding)
into "the move improved" (the thing nobody has measured). Its one real weakness is coverage —
the exact solver only reaches the endgame region, and the move-agreement probe deliberately
**excluded 25 solver-region roots** for that reason. Midgame needs "a much deeper search",
which reintroduces lineage.

**And that is where the user's idea earns its keep.** See §4.2.

---

## 4. Probe design

### 4.1 If run as an opponent ladder — the cheapest informative form is 2 cells, not a curve

Do **not** buy a 4-rung curve. At n=200/rung the adjacent-step z's would land ~0.3–0.8 and
you would learn nothing you don't already know. The only affordable question with real
decision value is: **does the +49.85 self-anchored 4× gain survive an out-of-information
reference, in sign and rough size?**

**Cells** (both on ONE fresh shared band ⇒ deck-matched CRN; the reference is byte-identical
in both, so the delta-of-deltas is as tight as this design can be):

| cell | fair rung | reference (FIXED) | n |
|---|---|---|---|
| A | `--opp-k-dets 4 --opp-sims 688` (2752, deploy) | `--info clair --k-dets 4 --sims 688` (2752) | 400 paired (200 decks) |
| B | `--opp-k-dets 8 --opp-sims 1376` (11008, 4×) | *identical* | 400 paired (200 decks) |

**Invocation shape** (path-stable, both boxes via `--shared-claim`, `nice -n 19`, detached):
```
.venv/bin/python scripts/classical_search/eval_fair_puct.py \
  --info clair --k-dets 4 --sims 688 --exact-k 2 \
  --opponent fair-champion --opp-k-dets 4 --opp-sims 688 \
  --cand-leaf-json <curve125> --n 400 --paired --seed-start 74000000000 \
  --shared-claim --out-root /mnt/c/carc-shared/classical_search --out-subdir clairref_A_2752_b74e9
```

**Band:** `results.csv` burned bands enumerate to `{1.9, 2.0, 2.5, 2.7, 3.0-3.13, 4.2, 5.0,
6.0, 8.8, 9.4, 9.5, 12.7, 13.0-13.2, 15, 17, 17.0001, 20.2, 22, 24, 26, 28, 32, 44, 46, 52,
54, 56, 60, 62, 64, 66, 68, 70}e9`. **Use 74e9** (re-enumerate at launch; the house rule from
`PARETO_CURVE_PREREG.md:61` is *"chosen by ENUMERATION of every band in results.csv"*). One
band for both cells — that is the point of the design.

**Cost (measured, not extrapolated).** From `pareto_k4x1376_5504_vs_deploy/summary.json`:
candidate 7,580 ms/move at 5504 sims, opponent 3,789 ms/move at 2752 — i.e. ~1.38 ms per sim
per move under load, and the Pareto run did 2,000 games in ~9 h at W16+W16. Normalising:
**≈10 worker-min per 2752-vs-2752 game**, scaling ~linearly in the *sum* of both sides' sims.

| cell | sims/move-pair | worker-min/game | ×400 games |
|---|---:|---:|---:|
| A (2752 + 2752) | 5,504 | ~10 | 4,000 |
| B (11008 + 2752) | 13,760 | ~25 | 10,000 |
| | | **total** | **14,000 worker-min = 233 worker-h** |

**At W32 across the two boxes: ≈7.3 h wall-clock.** One overnight. (Local W16 + laptop W16 is
the configuration the Pareto run used; W is per-box and should be re-verified with `ps` after
launch per the standing rule. Xeon is retired.)

**What counts as a result:**
- Read-out is the **deck-matched delta-of-deltas** B−A, in **pts/deck** (the paired statistic),
  via `scripts/classical_search/crn_delta_fairnet.py` — *not* the unpaired elo point estimates,
  which is the exact error CL-060 flagged and retracted.
- **Expected under "the +49.85 is real":** B−A ≈ **+2.9 pts/deck**. With CL-060's measured
  se 1.304 at n=400 through a rung, optimistically 1.0 with a near-peer reference ⇒
  **z ≈ 2.2–2.9.** Under "the self-anchored gain is an artifact": B−A ≈ 0, and n=400 bounds
  it at roughly ±2.0 pts/deck (2σ) ⇒ **rules out a large gain, cannot rule out a moderate one.**
- **⚠️ Pre-register that a null is NOT evidence of a knee.** With this power, a null is
  "underpowered", not "flat" — that is the single most important line in the pre-registration,
  and the mistake CL-060 made and had to retract.
- **⚠️ Cell B changes allocation (k8) as well as budget.** Same caveat as the blind curve's top
  rung. If width matters, add a k4×2752 arm on the same band (+10,000 worker-min, +5 h) — that
  arm doubles as the `blind_curve_width11008.sh` question, so it is not wasted.

**Pre-flight asserts (all cheap, all mandatory):**
1. Both sides resolve leaf `a36d2e15` (curve125) — `--cand-leaf-json` on the candidate,
   `opp_leaf_cfg` on the opponent. A mismatch silently turns this into a leaf A/B.
2. `_prod_deviations` prints **empty** for the shared knobs (c_puct 1.5, tau_p 5.0,
   value_norm 15, leaf float).
3. The `[warn] --info clair vs a FAIR head-to-head opponent` line **appears** in the log —
   its absence means the cell is not the one you think.
4. `deck_hash` mismatches = 0 across the two cells (the CRN pairing is the whole design).
5. Worktree isolation: `src/` is currently dirty on `android-app` with C3-intra and
   meeple-dedup **built but unscreened** — both flag-gated default OFF, but confirm
   `CARCASSONNE_INTRA_TURN_REUSE`/`CARCASSONNE_MEEPLE_DEDUP` are unset and pin a worktree
   if anything else is live.

### 4.2 The version I would actually fund: clairvoyant champion as a MOVE-SCORING ORACLE

`MOVE_AGREEMENT_PREREG.md:405-410` already asks for "a much deeper search" as a reference to
score the disagreement positions. The clairvoyant champion is the natural instrument, and used
this way it fixes every problem §2.4–2.5 raises:

- **The unit of n becomes positions, not games.** CL-070 already produced and stored the
  material: 873 analysable roots, `D_cross` 0.3039 ⇒ **≈265 positions where 2752 and 11008
  actually pick different moves**, with the full replay infrastructure
  (`scripts/measurement_infra/`, lossless deck-seed+action-sequence root replay,
  `measurement/champ_action_logs/champ_games.jsonl`) already verified bit-exact for this agent.
- **No opponent ⇒ no compression, no non-transitivity, no ruler at all.**
- **The estimator is paired at the world level.** Score both candidate moves under the **same**
  M sampled deck completions with a deep clairvoyant search each, and average. That is not a
  clairvoyant *judgement* (which would be biased — the best move under a known deck is not the
  best move under uncertainty, and would systematically punish the fair agent's correct hedges);
  averaged over M consistent worlds it is a **high-M PIMC value oracle**, i.e. the right target
  for a PIMC agent, estimated far more precisely than the k=4 agent can estimate it.
- **Coverage:** works in the midgame where the exact solver cannot reach, so it complements
  rather than duplicates the solver arm. Where `k_remaining ≤ 4` the exact solver should be
  used instead and the two cross-validated on the overlap — that overlap check is what
  licenses the oracle for the midgame.
- **Conversion to elo is direct**: mean gain per disagreed move × 0.30 disagreement rate ×
  ~70 moves = pts/game, and `results.csv luckfloor_champ_k4x688_vs_greedy_n200_b54e9` supplies
  the pts→elo exchange (+27.40 pts/deck ↔ +478 elo).

**Honest power estimate:** if the true 2752→11008 gain is +50 elo, that is ~0.07 pts per
disagreed move. With 265 positions and world-level CRN driving the per-position sd of the
paired oracle delta to ~0.5 pts, **z ≈ 2.2**; at sd 1.5 (no effective CRN) it is z ≈ 0.75.
**The whole probe lives or dies on the CRN efficiency of the world sampling** — that should be
measured on ~20 positions before committing the full run. That 20-position pilot is the true
cheapest informative step in this entire memo (~30–60 min).

---

## 5. Verdict

**On the literal proposal (clairvoyant champion as a game opponent for a sims ladder):**
**CONDITIONAL — worth 2 cells, not a curve, and only if a ~z 2 confirmation of CL-060's
+49.85 through an independent-on-information instrument is judged worth ~7 h of both boxes.**
It is cheap, needs no code, and the harness already anticipates it. It is *not* a knee-finder:
the effect is +12 to +28 elo per doubling-to-quadrupling and a third-party design has ~2× the
variance of the direct head-to-head that already measured it.

**On the underlying instinct ("we have a much stronger version of ourselves; use it"):
CORRECT, and under-exploited.** But its highest-value use is as a **move-scoring oracle**, not
an opponent — where n is positions rather than games, there is no ruler to compress, and it
answers the question CL-070 explicitly left open ("agreement is stability, not quality").

**What I would do, in order:**
1. **20-position CRN pilot** of the oracle scorer (~30–60 min) — measures the only unknown
   that decides whether §4.2 is powered.
2. If the pilot is good → the full **oracle-scored disagreement probe** (§4.2), cross-validated
   against the exact solver on the endgame overlap.
3. The **2-cell clairvoyant-opponent contrast** (§4.1) only as an independent-instrument
   validity check on CL-060, pre-registered with "a null means underpowered" stated up front.
4. `blind_curve_width11008.sh` on its own merits (width, not knee) — or fold its question in as
   the optional k4×2752 arm of cell B.

## 6. Open risks

1. **Shared-leaf blindness (§2.3).** If the flat top is a leaf ceiling, a reference built on
   the same leaf cannot see it. This is the single biggest validity limit, and it applies to
   §4.2 as well as §4.1.
2. **Underpowered-null misread.** CL-060 already made this error once and retracted it. A null
   here must be pre-registered as uninformative.
3. **CL-046's +68 top step is a known artifact** (refuted by CL-068). If it is quoted as the
   prior for this probe's expected effect, the design will be sized ~5× too small.
4. **Clairvoyant-oracle bias in §4.2** — a single-world clairvoyant score is the *wrong*
   objective and would systematically mis-rank hedging moves. Only the M-world average is
   valid, and M must be large enough that the averaging bias is below the effect. Untested.
5. **Reference-budget arbitrariness (§2.2)** — only curve *shape* is interpretable, never level.
6. **Allocation confound in cell B** (k8 vs k4) — mixes width with budget, exactly as the blind
   curve's top rung does.
7. **Cost asymmetry** — 1× at the bottom rung to 4× at the top. Not an equal-wall-clock design;
   any "is 4× worth it" claim needs the cost arm separately.
8. **Live-tree hazard** — `src/` on `android-app` carries two built-but-unscreened flag-gated
   features (C3-intra, meeple-dedup). Verify both resolve OFF, and pin a worktree if anything
   is running.
9. **Pooling temptation.** Two cells on one band cannot be pooled with anything else post hoc;
   `PARETO_CURVE_PREREG.md` rule 3 blocked exactly that and should be carried over.
