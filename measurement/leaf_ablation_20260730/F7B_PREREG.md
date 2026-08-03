# F7b — FARM-TERM KNOCKOUT ABLATION — PRE-REGISTRATION

> **STATUS: ✅ AUTHORIZED 2026-08-02 (Joshua: "lets do the farm knockout cells"; orchestrator
> ratified the farm-sighted-tail design call — the tail is the RULES, not a heuristic leaf,
> and the toward-null leak is documented in §design). Band `1.00e11` REGISTERED in
> `governance/BAND_REGISTRY.csv` in this same commit, before game 1. Launched two-box
> work-stealing immediately after this commit; W = local 32 / laptop 24 (the 2026-08-02
> W≈threads heuristic, no re-sweep).**
> Launcher: [`scripts/classical_search/leaf_ablation_launcher.sh`](../../scripts/classical_search/leaf_ablation_launcher.sh)
> (F7b addendum: `--backend`, `auto` workers). Cell configs: [`cells/`](cells/).
> Parent run + conventions: [PREREG.md](PREREG.md) (F7, CL-074).
>
> **Nothing in `governance/PRODUCTION.yaml` is touched by this document or this run.**

## The question

F7 measured six leaf components and left one hole. **What is the FARM contribution of the
champion leaf worth, in elo, under the current champion search — and is it one thing or two?**

Farm scoring enters the champion leaf `v2.9.2 Bmild_cap8_curve125` (`a36d2e15a3b3d71d`) in two
structurally separate places, which is exactly why F7 deferred it (PREREG.md §"Deferred cell"):

| # | where | what it does |
|---|---|---|
| 1 | **base term** — the farm award inside `flat_leaf._final_scores`, reached through `flat_base_score` | `3 × (#finished cities adjacent to the field)` to the field majority, at end of game |
| 2 | **anticipation term** — the farm-growth block of `flat_leaf.flat_closure_bonus` | `P(closure) × 3` for every *incomplete* city adjacent to one of the player's fields |

Neither had a `LeafConfig` knob before F7b. They are now `farm_base_off` / `farm_growth_off`,
default OFF, implemented in the **Rust leaf** and the **Python reference** (`flat_leaf.py`).

## Design

Identical to F7 except where flagged in §Deviations. Two cells:

| # | cell | knockout (`--cand-leaf-json`) | candidate leaf hash | what it removes |
|---|---|---|---|---|
| 1 | `farmbaseoff` | `{"farm_base_off": true}` | `b2c20e1452d8e5d4` | **farm points from the leaf's base**: the leaf's end-of-game estimate stops counting fields at all. Cities + roads + cloisters only. |
| 2 | `farmgrowthoff` | `{"farm_growth_off": true}` | `86ecb5375676feae` | **farm growth from the anticipation bonus**: the leaf stops paying for incomplete cities next to its fields. City-closure and cloister anticipation are untouched. |

- **Contrast:** champion-config agent with ONE farm term knocked out (candidate) **vs** the
  intact champion leaf (opponent), identical search config both sides — the ONLY difference is
  the candidate's `LeafConfig`. Champion side is env-`DEFAULT_CONFIG`, hash `a36d2e15a3b3d71d`
  (runtime-verified 2026-08-02, unchanged by the two additive fields).
- **Deck-paired**, same deck played both colors. **n = 400** per cell (200 decks × 2 seats).
- **Sign convention:** elo is **candidate − champion**. A knockout is expected to hurt, so
  **negative elo = the term is worth that much**; the term's value is `−elo`.
- **ONE fresh band for both cells (CRN)** — see below.
- **Prior on the record (queried before launch, per the results-discipline rule).** `results.csv`
  `abl_anticoff_vs_puctchamp2750_k2` removed **all** closure anticipation — city closure,
  cloister completion **and farm growth**, both sides — and read **−7.8 ± 17.4 (z −1.37)**,
  a powered null, while its two *halves* read −88.7 (`selfanticoff`) and −153.4
  (`oppanticoff`): CL-074's "anticipation = BALANCE not information". `farmgrowthoff` is the
  **farm-only slice of `anticoff`** and is *also* symmetric — the candidate's own `LeafConfig`
  drives both the self and the opponent closure-bonus pass, so the farm-growth credit vanishes
  from both sides of the candidate's own differential and the balance CL-074 identified is
  preserved. The F7 record therefore predicts `farmgrowthoff` should be **small**; a large one
  says the farm slice is special — that it is *information*, not balance, which would be a
  genuine amendment to CL-074. `farmbaseoff` has **no prior of any kind**: no leaf experiment in
  this project has ever removed base farm scoring. Both readings against F7 are
  **cross-band** (96e9 is retired) and take the standing ~1.5–2× σ inflation: they are
  *readings*, not verdicts. The within-cell verdicts are within-band deck-paired and unaffected.

### Cell configuration

Byte-identical to F7's table (`--candidate puct --opponent puct`, `--c-puct 1.5 --tau-p 5
--leaf-quantize float --final-select visits`, **sims 2750 both sides**, `--exact-k 2`,
net-free, `CUDA_VISIBLE_DEVICES=""`, `OMP_NUM_THREADS=1`) **except**:

| Knob | F7 | F7b | why |
|---|---|---|---|
| search engine | python | **`--backend rust`** | the port-1/G6 conversion landed 2026-08-02; it is the current default and the only affordable route for these cells (see §Cy decision) |
| workers | W16 both boxes | **local W32 / laptop W24** | Joshua 2026-08-02: assume W\* ≈ threads for the eval class, do not re-sweep. F7d *measured* W\*=30 local / 22 laptop — 32/24 is inside the settle band |
| leaf substrate (candidate) | Cython float fast path | **Rust leaf** (`RustClairvoyantAgent`) | the knockouts have no Cython implementation by design |
| band | 9.60e10 (retired) | **fresh, proposed below** | 96e9 influenced CL-074 and is retired from confirmatory use |

Both cells write a self-describing `manifest.json` into `<SHARE>/leaf_ablation/abl_<cell>/`
carrying `cand_leaf_cfg` + `cand_leaf_hash` (the knockout), `champ_leaf_cfg` + `champ_leaf_hash`
(the intact champion), the per-side `backend` block, and the writer's `workers` + thread pins.

### Proposed band (NOT claimed by this file — the orchestrator registers it)

**`1.00e11` — seeds `100,000,000,000 .. 100,000,000,199`** (200 decks × 2 seats = n=400),
**one band shared by both cells** (CRN: both cells play the same 200 decks against the same
intact champion, so both contrasts are within-band deck-paired — the robust class).

Verified free 2026-08-02 by **both** prescribed checks:
- `governance/BAND_REGISTRY.csv` — highest registered band is `98e9`; no row ≥ `1e11`.
- share-wide census `grep -h seed_start /mnt/c/carc-shared/*/manifest.json
  /mnt/c/carc-shared/*/*/manifest.json` — highest consumed is `99.5e9`; nothing ≥ `1e11`.
  (Note the census surfaces four bands the registry does not carry — `66e9`, `68e9`, `90e9`,
  `91e9`, `96.9e9`, `99e9`, `99.5e9` — which is why both checks are run.)

## The scope decision the orchestrator must ratify

**The knockout reaches the LEAF only. The exact-K endgame tail keeps full farm scoring, on both
sides.** This was a deliberate build decision and it is the one design choice in F7b that a
reviewer could reasonably want inverted.

- `scripts/level2/endgame_solver.py` evaluates its terminal nodes with
  `flat_base_score(state, 0)` — its own docstring: *"Leaf value = the REAL final score
  differential … with exact final (farm) scoring — NOT a heuristic leaf."* It is the **rules**,
  not the heuristic.
- The knockout is threaded as an **explicit argument**, never a global or an env var, so
  `flat_base_score` called without it — every caller in the tree except the flat leaf's own base
  term — is byte-identical to before F7b. The solver therefore cannot be reached by the knob.
- **Why leaf-only is the right ablation:** it keeps F7's property that the exact-K handoff is
  *identical on both sides* and cannot bias the A/B, and it measures "a farm-blind **evaluation
  function**", not "an agent that misplays the last two tiles by rule". A tail-inclusive
  knockout would confound the leaf's contribution with two plies of deliberately wrong scoring.
- **What it costs:** the last ≤2 tile decisions of each game are farm-sighted for the candidate.
  At k≤2 the field majorities are almost entirely settled, so the leak is small — but it is a
  leak, and it biases both cells **towards null** (the candidate is rescued at the very end).
  Read a null accordingly: it is a null *for the leaf*, slightly conservative.

## Gates (all run 2026-08-02, all PASS — the knockouts are proven inert when off)

| gate | what it proves | result |
|---|---|---|
| **(i) knobs-OFF byte identity** | the two additive fields changed nothing | `reconcile_leaf.py --corpus all --configs all` (the G2 three-leg harness: pure-Python flat · Cython flat · Rust) — **3,341,772 values, 0 mismatches**, across all 12 pre-existing config dialects and all 7 corpora. Byte-identical to the pre-F7b G2 total. |
| **(ii) knobs-ON py-vs-rust** | the two implementations of the knockout agree bit-exactly, separately and together | `reconcile_leaf.py --corpus all --configs farmoff` — **2,706,092 values, 0 mismatches**; the three knockout dialects (`farmbaseoff`, `farmgrowthoff`, both) contributed **63,568 positions×POVs each** (int + float-hex ⇒ 127,136 values each, 381,408 total) over 5 corpora. |
| **(ii-b) the knockouts BITE** | an inert knob would produce a null for an uninteresting reason | on the same sample, `farmbaseoff` changes the leaf on **65.7 %** of values, `farmgrowthoff` **76.8 %**, both-off **84.5 %**. |
| **(iii) harness wiring identity, PER KNOCKOUT** | `--backend rust` plays the same games as `--backend python` *on the knocked-out leaf* — so the cell's engine choice is not the measurement | `gate_eval_puct_priors_backend.py --games 4 --cand-sims 2750 --opp-sims 2750 --exact-k 2 --workers 4 --cand-leaf-json <cell>` (the `--cand-leaf-json` passthrough was added for this). Run **under the launcher's champion leaf env**, so the graded pair is exactly the cell's: champion `a36d2e15a3b3d71d`, candidate `b2c20e1452d8e5d4` / `86ecb5375676feae`. **PASS both cells: 4 deck-paired games, 76 field checks, 0 mismatches, manifest provenance OK**; the two legs returned *identical* summaries (`farmbaseoff` 1W/0D/3L, margin −13.0 on both; `farmgrowthoff` 2W/0D/2L, margin −5.25 on both). Artifacts: `F7B_GATE_WIRING_farmbaseoff.json` / `F7B_GATE_WIRING_farmgrowthoff.json`. |
| **hash stability** | the champion's fingerprints did not move under two additive fields | `a36d2e15a3b3d71d` (harness dialect) · `158f17ff76adaa02` / `6dfffd57051690f2` (frozen recipe) all recompute unchanged; the golden fixture was regenerated per the standing rule with a verified diff of **exactly the 4 full-asdict hash fields**, all behaviour values bit-identical. |

**Gate (iii) is doing double duty and it is worth naming.** Its python leg computes the knockout
on the **pure-Python flat leaf**; its rust leg computes it in the **Rust leaf**. If the knob
failed to reach the Rust search — a dropped kwarg in `leaf_config_rs`, a `LeafConfigRs` field
ignored — the rust leg would play the *intact champion leaf* and the two legs would diverge
within a few plies. A PASS is therefore simultaneously (a) the wiring-identity claim and (b) the
end-to-end proof that the ablation actually reaches the engine the cell runs on.

It also *measured* the cy-refusal, unasked. In the python leg the CANDIDATE ran 16947 ms/move
(`farmbaseoff`) against the OPPONENT's 3702 — a 4.6× asymmetry that exists only because the
candidate's knocked-out leaf left the Cython fast path while the intact champion stayed on it.
The same asymmetry appears in the per-side rust speedups (candidate 53.2× vs opponent 11.6×).
That is the ~12.5×-per-leaf penalty showing up end-to-end, and it is precisely the reason the
cells run `--backend rust`, where neither side computes a Python leaf.

Unit coverage: `tests/test_f7b_farm_knockout.py` (13 tests) — default-off inertness, bite,
severability (base-off moves only the base, growth-off only the bonus), the cy-fast-path
refusal, the object-path fail-loud, and the solver-terminal invariance.

### Cy decision (recorded, per the roadmap's repriced route)

`flat_leaf_cy.pyx` **deliberately does not implement the knockouts**, and no `.so` rebuild is
required on either box. Justification:

1. In a `--backend rust` cell **no Python heuristic leaf is computed at all** — both prefixes are
   `RustClairvoyantAgent`, and the exact-K tail computes the TRUE final score (which the
   knockout must not touch, see above). The cy leaf's only in-cell role, `flat_base_score_cy`
   inside the solver, is exactly the call that stays intact.
2. A set knob still cannot silently reach a knockout-blind `.so`: `flat_virtual_score_v2{,_float}`
   route **off** the cy fast path via `_farm_knockout_off(cfg)`, and `flat_base_score` suppresses
   its own cy redirect when `farm_off` — both asserted by the unit tests with the cy entry points
   poisoned.
3. So the only consequence is **speed on the python backend** (~12.5× per leaf, the 2026-07-30
   measurement), which is why `_assert_cy_float_path` **warns** rather than raises for this knob
   family — a raise would make the intended rust cells unlaunchable and would block the wiring
   gate's python reference leg.

This is the roadmap's stated primary route (*"add the default-off knockout to the Rust leaf +
the Python reference, then re-gate with the G2 three-leg bit-exactness harness; the `.pyx` route
is the fallback"*). The `.pyx` fallback was not needed.

## Power and what each outcome reads as

`n=400` deck-paired: **1σ ≈ ±17 elo unpaired, ≈ ±12 elo deck-paired ⇒ a verdict for effects
≳ 35 elo (2σ), a screen below that.** Same table as F7:

| Reading | Interpretation |
|---|---|
| **elo ≪ 0 (≲ −50)** | the farm term is **load-bearing** under the champion search. Phase-6 headroom lives on that axis; its *shape* (the flat `3×finished` award, the flat `P×3` growth credit) is worth re-deriving rather than re-weighting. |
| **elo ≈ 0 (\|elo\| < 25)** | the term is **inert under this search** — a deletion candidate (the leaf is the search hot path; farm decomposition is ~45 % of `decompose`) and a "stop sweeping this axis" signal. Note the tail-leak above makes a null slightly conservative. |
| **elo > 0 significantly** | the term is **actively harmful** — removing it strengthens the agent. Escalate to Joshua as a proposal; **no automatic production change**. Prior plausibility is non-trivial here: the growth credit is a flat `P × 3` that ignores field majority (the `v28_farm_majority` patch existed for exactly this suspicion and was never adopted). |
| `farmbaseoff` ≈ 0 **and** `farmgrowthoff` ≪ 0 | the leaf's farm value is entirely *anticipatory* — it is worth knowing a field will grow, not worth counting it at the end. |
| `farmbaseoff` ≪ 0 **and** `farmgrowthoff` ≈ 0 | the reverse: the end-of-game count carries it, the growth credit is decoration. |
| both ≪ 0 | farms are a first-class leaf component and F7's six-cell table is materially incomplete without them. |

**No promotion, adoption, or `PRODUCTION.yaml` edit follows automatically from either cell.**

## Measured smoke and cost (measured, not extrapolated)

Run 2026-08-02 through the **patched launcher**, local box, `--backend rust`, **W32**, on a
THROWAWAY band `96.98e9` with `--smoke` (no `results.csv` row, no band consumed). Production
knobs otherwise byte-identical to the cells (same launcher, same env, same cell JSON).

| pass | cell | n | W | wall | notes |
|---|---|---|---|---|---|
| 1 | `farmbaseoff` | **32** (a FULL saturated W32 wave) | 32 | **172 s** (repeat run: 174 s) | the throughput number |
| 2 | `farmgrowthoff` | 4 | 32 | 53 s | second knockout end-to-end |

**Throughput (local): 32 games / 172 s = 0.186 games/s = ~670 games/h.** This is a *wave* rate
(all 32 complete), not a first-completion order statistic. Per-cell:

- **local only:** `400 / 670` ≈ **0.60 h/cell** ⇒ both cells ≈ **1.2 h**.
- **two boxes:** laptop at W24 and the CL-067-measured 1.39× clock ratio ⇒ ≈ `670 × (24/32) / 1.39`
  ≈ 360 games/h ⇒ combined ≈ 1030 games/h ⇒ ≈ **0.39 h/cell**, both cells ≈ **0.8 h**.
  The laptop leg is *projected*, not measured — treat the two-box figure as the optimistic bound
  and the local-only 1.2 h as the one to plan against.

For scale: the F7 python-era cells measured **101 games/h local at W16** and took ~2.3 h/cell.
F7b is ~6.6× cheaper per game, which is what retired the roadmap's superseded "~37 h/cell"
figure. The whole F7b run is comfortably a **single sitting**, not an overnight.

Compute neutrality (the A/B fairness check): candidate/champion `ms_per_move` ratio **0.94**
(pass 1) and **0.97** (pass 2) — the knockout makes the leaf marginally *cheaper*, as expected
from deleting work. Equal-sims design, so this is not a confound; it is recorded because a
large ratio would be. Exact-tail cost 20.3 s/game (pass 1) is shared identically by both sides.

⚠️ **The smoke also peeked at the effect, and the prereg is not tuned to it.** Pass 1 returned
`farmbaseoff` **−190.8 ± 70.9 (paired z −4.52)** at n=32 on a throwaway band — 8W/0D/24L. That
is a *screen*, ~2× under-powered relative to this document's own thresholds, on decks that are
not the claim band. It is reported here because operational honesty demands the peek be on the
record, and because it discharges the "is the knockout inert end-to-end?" question. Every
threshold in §Power was written from F7's conventions before pass 1 ran and **none was
adjusted after**. The n=4 pass-2 figure (0W/0D/4L) is not an effect estimate at all.


## Ops

- Both cells on **both boxes**, work-stealing on the same share dir via
  `eval_puct_priors.py --shared-claim` (`--claim-stale-secs 300`); local = primary (aggregates,
  writes `results.csv` + `ABL_PROGRESS.tsv`), laptop = helper.
- **The clock-skew guard stays armed** (`fcf8f1c`, F7 launch incident 2): the launcher writes a
  probe to the share and refuses to start above 60 s skew. Unchanged by the F7b edits.
- Laptop must be **code-synced first** (`git bundle`) — F7b DOES change `src/` and the Rust
  crate, so the laptop needs the bundle **and** a `maturin develop --release` rebuild of
  `carc_rs`. (No Cython rebuild: `.pyx` is untouched.)
- `scripts/measurement_infra/run_watchdog.sh` armed on both boxes.
- Launch (per box):
  ```
  nice -n 19 bash scripts/classical_search/leaf_ablation_launcher.sh auto local  \
      --cells "farmbaseoff farmgrowthoff" --band 100000000000
  nice -n 19 bash scripts/classical_search/leaf_ablation_launcher.sh auto laptop \
      --cells "farmbaseoff farmgrowthoff" --band 100000000000
  ```
  (`auto` → W32 local / W24 laptop; `--backend rust` is the default.)
- Close-out: the six-touch checklist (`results.csv` → DECISIONS index line → status banner on
  this file → `BAND_REGISTRY` row `claimed → retired` → STATUS top block → roadmap F7b line),
  then `python3 scripts/doc_lint.py`.

## Deviations from F7 (flagged, not silent)

1. **`--backend rust`** on both sides (F7 was python). Gated by (iii) above per knockout.
2. **W 32 / 24** instead of W16 (Joshua 2026-08-02; F7d measured 30/22).
3. **Fresh band** — F7's 96e9 is retired, so the F7b↔F7 comparisons are cross-band and get the
   standing ~1.5–2× σ inflation. Within-cell verdicts are unaffected.
4. **Leaf source changed** (F7's headline was "no code change"). That is why gate (i) exists and
   why it is a full 3.34M-value three-leg identity rather than a spot check.
5. **The exact-K tail is farm-sighted for the candidate** — see §The scope decision.
