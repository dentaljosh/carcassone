# FPU RESURRECTION — THE UNREACHABLE-KNOB ROUND — DESIGN

> **STATUS: FROZEN** (2026-08-30). This document and [`READ_RULE.md`](READ_RULE.md) are **the pair**,
> and the pair is law. ⛔ **NOTHING IN EITHER FILE MOVES AFTER THE BLIND COMMIT.**
>
> ⛔ **0 games have been played at this commit. No band is claimed at this commit.** The instrument
> exists, `analyze_fpu.py --selftest` is `PASS` (13 defect variants), and
> [`FPU_BITEXACT.json`](FPU_BITEXACT.json) — the **golden gate** — is `PASS`.
>
> ⚠️ **THIS ROUND IS UNLAUNCHABLE FROM THE TREE IT WAS BUILT ON.** `run_cells.sh`'s `G-PROD` gate
> refuses because the build worktree predates the 2026-08-30 champion promotion. See §0.1.

---

## 0. THE ONE-PARAGRAPH VERSION

A false-negative audit found that **the champion could not express `fpu_reduction`**.
`carc_rs` has accepted `Option<f64>` in that `SearchConfigRs` slot since the rustport
(`rust/carc/carc-py/src/lib.rs:1580`) and `carc_core::search` has implemented the rule
(`search/mod.rs:816`) — but `src/carcassonne_ai/rust_agent.py::search_config_rs` passed a
**hard-coded `None`** into it. No `HeuristicPriorConfig` value could reach the Rust leg, and a caller
who set the knob got a **python leg that honoured it and a Rust leg that did not** — two different
agents wearing one config. The knob is now threaded end-to-end, the bit-exact-when-`None` property is
proven (§9), and **three cells** ask the question that could never previously be asked of the
champion: `fpu 0.2`, `fpu 0.4`, and `c_puct 1.0`, each `n=800` deck-paired against the **unmodified
champion**, each on **its own fresh band**.

### 0.1 ⛔⛔ THE BUDGET MOVED UNDER THIS ROUND — READ THIS FIRST

The owner promoted the **desktop** champion budget `11008 → 22016` (`k16 × 1376`) on **2026-08-30**,
during this build. The pair is frozen at the **new** budget: **both sides of every cell run
`k16 × 1376 = 22016`.**

⚠️ **The build worktree predates that commit** — its `governance/PRODUCTION.yaml` still reads
`fair_deploy: k_dets 8 / sims_per_det 1376` for desktop (`k16` appears only in the *mobile* profile,
labelled "desktop UNTOUCHED"). So:

- `run_cells.sh` carries **`G-PROD`**: it reads `governance/PRODUCTION.yaml` **at launch** and
  **REFUSES** if `fair_deploy` is not the frozen `k16 × 1376`. It is a hard abort for a real cell and
  for the smoke; a `--dry-run` prints the mismatch loudly and continues, because a dry-run spends
  nothing.
- ⭐ **The fix is the bundle sync, never an edit.** The executor syncs the box to the
  promoted-champion `HEAD`, re-pins `PINNED_SRC_REV`, and `G-PROD` then passes on its own.
- ⛔ **Do not "resolve" a `G-PROD` failure by editing `WORKERS.conf` or `screen_lib.py`.** The
  opponent of every cell **is** the champion of record; a frozen budget that disagrees with the YAML
  means the round would grade the knob against a **stale champion**, and every other gate would pass.

### 0.2 ⚠️ THE LEVER INDEX SAYS THIS AXIS IS CLOSED

[`docs/LEVER_INDEX.md:146`](../../docs/LEVER_INDEX.md) reads:

> **FPU / first-play urgency** · `--fpu` · `fpu_reduction` · fpu02…fpu10 — TRIED twice — a Stage-A2
> screen fired but **its n=400 confirm was never run** (mooted by expand-all); M3 later ran the full
> curve → **peaks at parity, axis CLOSED**

**This round is a deliberate reopening, and the argument is narrow.** Every prior FPU cell measured
FPU on a **neural or value-blended agent**:

| prior | what it measured | reading |
|---|---|---|
| `verdict_fpu02_paired_n200` (results.csv:68) | NeuralMCTS, `pathb_loop/iter_11` priors + **v2.7** leaf value, `c=3.0`, sims 200 | `+45.4` elo, **z 1.85 — a SCREEN, never confirmed** |
| `verdict_fpu04_paired_n200` (results.csv:69) | same, fpu 0.4 | `+31.4` elo, **z 1.28 — a SCREEN** |
| M3 FPU curve (results.csv:233–236) | `iter_02+warmstart` **additive value-blend β=0.27** vs the pure-v2.9 anchor, sims 100 | wr `0.391 / 0.496 / 0.4825 / 0.476` at fpu `0.4 / 0.6 / 0.8 / 1.0` — **peaks at PARITY and rolls off** |

⭐ **None of them could have measured the classical champion**, because the knob was structurally
unreachable on the champion's backend until 2026-08-29. The M3 reading is explicitly about FPU as a
**rescue for a bad learned value** ("FPU removes the weak value's HARM but cannot make it EXCEED"),
which is a different proposition from "does a pessimistic FPU help a well-tuned heuristic-prior PUCT
search". ⛔ **The prior evidence is not wrong; it is about a different agent.** It is also the
strongest reason to expect `F-REKILL`, and `READ_RULE.md` §5 says so before any number exists.

### 0.3 ⛔ WHAT WOULD MAKE THIS ROUND WORTHLESS, AND WHAT STOPS IT

A cell whose knob **never bound** plays champion-vs-champion. It moves **no leaf hash** (neither knob
is a leaf term), its winrate sits comfortably inside `G-SAT`'s rail, its budget and rules and backend
and wheel all check out, and it reads as a **clean, credible null**. That is not a hypothetical: it
is exactly what every FPU cell would have produced on the champion's backend before 2026-08-29.

Four independent things stop it:

1. ⭐⭐ **The golden gate** (§9) — `fpu=None` is bit-identical to the pre-change code over 20 seeded
   games, **and** `fpu=0.2` differs on 20/20 of them. The second half is what makes the first half
   worth anything.
2. ⭐⭐ **`G-FPU` / `G-CPUCT`** — the RESOLVED request on disk (`config.cand_search`), `ABSENT` is
   `FAIL`, and `null` is distinguished from absent.
3. ⭐⭐ **`G-TWOSIDED`** — the two sides' **resolved `HeuristicPriorConfig` blocks**, which is the
   witness that does not come from the flag.
4. ⭐ **The launcher's own knob probe** — `run_cells.sh` imports this box's source and asserts
   `fpu=Some(0.2)` in `repr(SearchConfigRs)` **before spending anything**.

---

## 1. WHAT IS BEING ASKED

**On the classical champion, at the deployed budget, does a pessimistic first-play urgency (or a
lower PUCT exploration constant) beat the unmodified champion in games?**

⚠️ It is a **strength** question, judge-free, decided by game outcomes — not by an offline ruler.
`feedback_evloss_grader`'s F4 lesson binds on any temptation to grade this with a judge: judged
headroom is family-relative and a `+1.49` in-family ceiling read `−0.64` at z `−3.8` out-of-family on
the same CRN worlds. Game outcomes outrank any judged number and this round uses nothing else.

### 1.1 Why FPU is a plausible lever *here* specifically

The champion's priors are a **heuristic softmax over Δleaf** at `τ_p = 5`, which is deliberately
flat. A flat prior plus the legacy optimistic FPU (`q = 0` for every unvisited child) means the
search spends visits **breadth-first** across a wide root: every unvisited sibling scores `0 + U`,
and `U` is large while `N` is small. A pessimistic FPU (`q = parent.Q − r`) makes an unexplored
sibling look *worse* than the parent's current estimate, concentrating visits on children the priors
already like. Whether that helps is exactly what a well-tuned search makes uncertain — which is why
it is a measurement and not a deploy.

### 1.2 ⭐ Why the budget promotion does not disturb the mechanism

`k_dets 8 → 16` is **pure width**. `sims_per_det` is **unchanged at 1376**, and FPU acts *inside* one
determinization tree — it is read on that tree's PUCT descent, on that tree's unvisited children.
**Per-tree first-visit behaviour at 22016 is identical to 11008**; `k_dets` only changes how many such
trees are pooled before the argmax. So the mechanism argument transfers across the promotion
unchanged, and the round measures the same thing it would have at 11008 with ~half the variance per
unit wall-clock spent on trees rather than depth.

⚠️ That is an **argument**, not a measurement, and `READ_RULE.md` §5.1 carries it as a rider on
`F-RESURRECT` rather than as a licence to transfer a positive result downward in `k`.

---

## 2. THE CELLS

| cell | box | knob | value | band | n |
|---|---|---|---|---|---|
| `CELL_FPU02` | local | `fpu_reduction` | **0.2** | `155000000000` | 400 decks × 2 = 800 games |
| `CELL_FPU04` | local | `fpu_reduction` | **0.4** | `156000000000` | 800 games |
| `CELL_CPUCT10` | laptop | `c_puct` | **1.0** | `157000000000` | 800 games |

Opponent, all three: the **UNMODIFIED champion**. Both sides:

- fair PIMC **`k16 × 1376 = 22016`** (§0.1)
- `rules_profile = fixed_v1`, `CARCASSONNE_FIX_R9=1` (env-latched at import)
- `exact_k = 2`, mode `marginalized`
- backend `rust`
- leaf `a36d2e15a3b3d71d` (curve125) — **the same leaf on both sides**
- **tie-arbiter OFF** (§2.3)

### 2.1 Why two fpu doses and not a ladder

The two doses are exactly the two that were screened in 2026-06-02 and never confirmed. Two points
give a **direction across the axis**. ⛔ They are **not a bracket**: `feedback_bracket_hyperparams`
requires ≥3 well-spread points and treats an endpoint peak as unbracketed, so **no interpolation
between 0.2 and 0.4 is licensed** and neither cell's result may be read as locating an optimum. If a
dose fires, the follow-up is a bracket on a fresh band — not a reading of this round's two points.

### 2.2 Why `c_puct 1.0` rides along

The champion is `c_puct = 1.5`. It is the same *kind* of knob (a PUCT selection constant that no cell
has varied on the classical champion at deploy budget), it is nearly free to add once `cand_search`
exists, and — the funded reason — **it is the trigger for the conditional τ pair** (`READ_RULE.md`
§6). A null on `c_puct` re-kills τ.

### 2.3 ⚠️ THE TIE ARBITER IS OFF, AND THAT IS A DEVIATION FROM THE DEPLOYED CHAMPION

`governance/PRODUCTION.yaml` has carried `tiearb B=64` since 2026-08-20. It is **disabled on both
sides here**. The reason: the arbiter is a **stochastic post-search root hook** that fires on exact
ties and runs CRN determinization playouts. Leaving it on would inject fire-driven variance on both
sides, orthogonal to the knob under test, for no gain — and it interacts with the search's visit
distribution, which is precisely what FPU changes, so an armed arbiter would confound the mechanism
rather than merely add noise.

⛔ **The price rides on every branch:** the answer is about the **arbiter-free** champion, and its
transfer to the deployed `B=64` one is an **assumption**, not a measurement. `run_cells.sh` contains
no `--cand-tiearb-*` flag anywhere, by construction, and `G-ARB-OFF` walks the whole manifest to
prove nothing armed it.

### 2.4 ⛔ Single-variable discipline, and where it bends

Every cell changes **exactly one** knob. `G-SINGLEVAR` asserts it — but it is **rewritten** for this
round, because unlike phasegate (whose variable lived in a separate `cand_tiearb` container) **the
variable here IS a search knob**. On `CELL_CPUCT10` the candidate's `c_puct` *must* differ from the
opponent's. So the gate asserts the cell's own alias **DIFFERENT** and every other alias **EQUAL**.
An unedited copy of phasegate's clause would have voided the very cell it was written to protect.

---

## 3. SIZING AND POWER — from realized numbers only

The sizing constant is carried from the Stage-2 Phase B cell `ARB` and nothing else
(`M +3.0700`, `paired_z +4.445`, `n_paired 400 DECKS`):

```
se(M)   = 3.0700 / 4.445    = 0.6907  pts/deck at n=400
sigma_D = 0.6907 * sqrt(400) = 13.81  pts/deck
```

⛔ **POWER ARITHMETIC ONLY.** `READ_RULE.md` §1: `sigma_D` is never a denominator in a branch test —
every branch is adjudicated at the cell's **own realized SE**.

| n decks | games | `se(M)` | **2σ resolution** | resolvable at 80% power |
|---:|---:|---:|---:|---:|
| **400** | **800** | **0.691** | **±1.381 pts/deck** | +1.93 |
| 800 | 1,600 | 0.488 | ±0.977 | +1.37 |
| 1,200 | 2,400 | 0.399 | ±0.798 | +1.12 |

**The funded shape is 400 decks / 800 games per cell**, whose 2σ resolution is **±1.381 pts/deck**
and, on the secondary, **±17.4 elo** — the brief's "~±17.5 elo", and it checks out:
`σ_elo(unpaired, n=800) = 695·√(0.25/800) = 12.3`; deck-pairing halves the variance
(`×0.707`) → `8.7` elo at 1σ → **±17.4 at 2σ**.

⚠️ **STATED HONESTLY:** at 400 decks a *true* `+1.381` gives `z = 2.00` — **50% power**. What the `n`
guarantees is the **bounding** direction: `F-REKILL` returns a real 95% upper bound. Given
`LEVER_INDEX`'s CLOSED verdict (§0.2), the bounding direction **is** the decision-relevant one — the
question this round can actually settle is whether the reopening survives.

⛔ **`n` IS IN DECKS, NOT GAMES.** `--paired --n 800` is 400 decks × 2 seatings. Every bar above is
in decks.

---

## 4. THE PRIMARY STATISTIC, AND THE AWKWARD SECONDARY

**Primary: the deck-paired margin**, `D(deck) = (diff(a_seat=0) + diff(a_seat=1)) / 2`, in POINTS,
candidate minus opponent. `M > 0` ⇒ the candidate won. That is house doctrine and it carries every
branch.

**Secondary: elo**, reported beside it with its own CI on every branch.

⚠️ The funding brief states the bar **in elo** (`~±17.5` at 2σ) because the **prior art is in elo**
(`+45.4` / `+31.4`). House doctrine is that **`elo` may never be quoted bare** — Stage-2's own elo
secondary did not convict at `+23.92`, CI `[−0.21, +48.06]`, winrate z `+1.94`. This design resolves
the tension by pre-registering **both**: `BAR_M = 1.381` carries the branch, `BAR_ELO = 17.4` is
reported alongside, and ⭐ **a disagreement between the two is DISCLOSED, never arbitrated.**

---

## 5. THE BANDS — THREE, AND WHY

⭐ **PROPOSED: `155000000000`, `156000000000`, `157000000000`.** ⛔ Not claimed, not registered, not
appended to `governance/BAND_REGISTRY.csv`.

- Highest registered id is `154000000000` (phasegate, 2026-08-28). These are the next three monotone
  ids.
- **Tree sweep 2026-08-29: 0 references** to any of the three, anywhere in the repo.
- ⚠️⚠️ **`146000000000` IS THE TRAP THIS ORDER EXISTS FOR** — absent from the registry but carrying
  references in the tree. The registry is **necessary and not sufficient**; the **tree sweep is the
  binding check** and is re-run immediately before the CSV append.
- ⭐ **`158000000000` and `160000000000` WERE DROPPED** for exactly that reason: 0 registry rows but
  live tree hits (`measurement/probe_b_fair_targets/`, `measurement/e4_exploit_grading_20260825/`,
  `measurement/leaf_residual_mining_20260721/`). They are recorded here so the next reader does not
  rediscover them as "free".

**Why three bands and not one.** Nothing in this round is pooled or deck-matched across cells: three
independent questions, three independent verdicts. One shared band would buy no deck-matching that
any gate reads, and would spend **one** band's `decision_influenced` retirement on **three** verdicts.
Three bands keep every contrast within-band (the only robust class under CL-068) and retire cleanly.

⭐ The consequence for the instrument: **`G-DECKS` is rewritten again, in the opposite direction from
phasegate.** Phasegate's ranges overlapped *by design*; here they are **disjoint** and disjointness is
assertable again. A copied phasegate clause would have skipped the check entirely.

**Throwaway sub-range: `157999999000`+** (the §9 smoke). ⛔ Never in any claim.

---

## 6. COST AND ETA — re-priced from a realized cell, post-promotion

⭐ **Anchored on the realized `IDENT` cell of `measurement/phasegate_prep`**, which is the right
reference precisely because its arbiter was gated to `none` and therefore never fired: it is a
champion-vs-champion cell at `k8 × 1376 = 11008` with no arbiter cost.

| realized reference | box | W | worker-s / game | budget |
|---|---|---:|---:|---|
| `phasegate_a1/IDENT` (n=80) | local | 30 | **263.2** | 11008, arbiter never fired |
| `phasegate_a1/SMOKE_EARLY` (n=22) | local | 30 | 278.0 | 11008, early-gated arbiter |
| `phasegate_a1/ARB_EARLY_R` (n=326) | laptop | 22 | 297.9 | 11008, early-gated arbiter |

The laptop has no arbiter-free reference, so it is derived: the local early-gate arbiter costs
`278.0 / 263.2 = 1.056×`, giving a laptop arbiter-free figure of `297.9 / 1.056 ≈ 282.1` worker-s per
game at 11008.

**At `k16 × 1376 = 22016` the per-move search doubles.** ⚠️ `×2.0` is used as a **conservative upper
bound**: the exact-endgame tail (`exact_k 2`, marginalized) and the engine stepping do **not** scale
with `k_dets`, so the true factor is slightly below 2 and every wall below is correspondingly
pessimistic.

```
local   263.2 x 2 = 526.4 worker-s/game   ->  W30 / 526.4 = 205.2 games/h
laptop  282.1 x 2 = 564.2 worker-s/game   ->  W22 / 564.2 = 140.4 games/h
```

| | games | local wall | laptop wall |
|---|---:|---:|---:|
| one cell (800 games) on one box | 800 | **3.9 h** | **5.7 h** |
| `CELL_FPU02` + `CELL_FPU04` (local) | 1,600 | **7.8 h** | — |
| `CELL_CPUCT10` (laptop) | 800 | — | **5.7 h** |
| **THE ROUND (whole cells per box)** | **2,400** | **7.8 h** (2 cells, serial) | **5.7 h** (1 cell) |

⭐ **Round wall = `max(7.8, 5.7)` = 7.8 h.**

**Core-hours: ≈ 359 worker-h** (2,400 games × 539 worker-s mean = (2 × 526.4 + 564.1) ÷ 3).

⚠️ **The funding brief's estimate was `~800 games ≈ 1.5 h two-box at W30/W22`.** That is correct
**at 11008 with a single cell split across both boxes** (`0.114 + 0.078 = 0.192` games/s → 1.16 h).
The round is ~2× that per cell after the promotion, and it does **not** split cells:

- ⭐ **`G-HOST` whole-cells-per-box is a design choice from the brief, and it costs ~0.9 h.** The
  best a 3-cell / 2-box whole-cell split admits is 2 local + 1 laptop → **7.8 h**, with the laptop
  idle for the last ~2.1 h. Splitting one cell into `_L`/`_R` sub-cells (the phasegate shape) would
  bring the round to **≈ 6.9 h** at the cost of a `G-SUBPOOL` gate and a pooled primary.
- ⛔ **Not taken.** The brief specified whole cells; the imbalance is **disclosed, not engineered
  away**; and a pooled primary is a strictly more complicated object to adjudicate for a 12%
  wall-clock saving.

⚠️ Every figure here is **wall-clock only**. ⛔ **No gate in this pair reads a clock**, `W` is
throughput-only, and games are bit-identical at any `W`.

---

## 7. THE INSTRUMENT — what was forked, what was rewritten

`screen_lib.py` is a fork of `measurement/phasegate_prep/screen_lib.py`. **Carried verbatim in
construction:** `cross_box_rev_gate` (the IS-A1 fold), `rev_matches`, `is_hex40`,
`host_matches_box`, `paired_margin`, `winrate_elo`, `recon_close`, `resolve`/`gate`, `se_anomaly`.

### 7.1 ⛔ REWRITTEN, and why a copy would have been wrong

| gate | phasegate's version | here |
|---|---|---|
| `G-DECKS` | asserted the cells' ranges **OVERLAP** (one deck set, decomposed) | asserts they are **DISJOINT** (three bands). A copy would skip the check entirely |
| `G-SINGLEVAR` | **every** search knob equal on both sides | the cell's **own** alias must **DIFFER**, every other must be equal. A copy would **void `CELL_CPUCT10`** |
| `G-SUBPOOL` | pooled `_L` + `_R` into one cell | **deleted** — nothing is pooled |
| `G-ANCHOR` | a hard ordering: the anchor had to convict or nothing was read | **deleted** — three independent questions, no anchor, no ordering |
| `G-TIEARB-ARM` | asserted the arbiter was **ON** at the frozen rung | **inverted** to `G-ARB-OFF`: it must be **off on both sides** |
| `G-BUDGET` | `k8 × 1376 = 11008` | **`k16 × 1376 = 22016`**, plus the new `G-PROD` launcher guard (§0.1) |

### 7.2 ⭐ NEW — and an honest note on what the second witness can and cannot be

`G-FPU` / `G-CPUCT` read the **request** (`config.cand_search`, written from the CLI). `G-TWOSIDED`
reads the **resolved `HeuristicPriorConfig` of each side** (`config.champion.*` vs
`config.opponent.champ_cfg.*`) and proves the value landed on the candidate and nowhere else.

⚠️ **This is weaker than phasegate's `G-PHI`, and the design says so rather than overclaiming.**
`G-PHI` was derived from **play** — per-ply fire counters that only a bound arbiter could produce. A
PUCT constant has no fire counter. `G-TWOSIDED` is derived from the **constructed agents' configs**,
which is one step closer to play than the flag but is still not play. ⭐ The play-derived evidence in
this round is the **golden gate** (§9): 20/20 seeded games diverge at `fpu = 0.2`. That is what
closes the gap, and it is why the golden gate is a hard launch precondition rather than a nicety.

### 7.3 `G-PROD` — new, launcher-side

The only gate that reads `governance/PRODUCTION.yaml`. §0.1 states it in full.

---

## 8. PRE-LAUNCH ACTS — the executor's checklist

1. **Merge** the build branch; **bundle-sync** every box to the promoted-champion `HEAD`
   (`reference_offline_git_bundle_sync`). ⚠️⚠️ **This is the round's primary provenance risk:** the
   fpu plumbing is **python-only**, so a box on stale source serves a knob-free candidate with a
   healthy wheel, a healthy `carc_rs_build` and the correct leaf hash.
2. `git -C <repo> rev-parse HEAD > measurement/fpu_resurrection_prep/PINNED_SRC_REV` **on each box,
   after its sync**. ⛔ Never committed (`.gitignore`) — a committed pin lets one box's rev
   masquerade as the other's, the exact IS-A1 confusion `cross_box_rev_gate` refuses.
3. **Stamp `BLIND_COMMIT`** — a follow-up commit writes the freeze commit's 40-hex sha into
   `WORKERS.conf`. A commit cannot name its own hash.
4. **Claim the three bands**: re-run the tree sweep, then append the three rows from
   `BAND_CLAIM.json::_csv_rows` to `governance/BAND_REGISTRY.csv`, **then** drop `BAND_CLAIMED`.
   ⚠️ In that order — 146e9 is the trap it exists for.
5. **Smoke each box** (§9) and **read `SMOKE_<role>.json` by hand**.
6. Launch detached, `nice -n 19`, whole cells per box.

`run_cells.sh` enforces 2–5 mechanically and refuses without them.

---

## 9. THE GOLDEN GATE AND THE SMOKE

### 9.1 ⭐⭐ The golden gate — [`FPU_BITEXACT.json`](FPU_BITEXACT.json), verdict **PASS**

Three real legs of `selftest_fixture/identity_fixture.py`, 20 frozen seeded self-play games each
(`k2 × 96`, 144 plies per game), adjudicated by `identity_diff.py`:

| leg | tree | `fpu` | `leg_sha256` |
|---|---|---|---|
| `OLD` | pre-change source (`git archive HEAD src engine`) | unset | `623d02ee…` |
| `NEW` | post-change source | unset | `623d02ee…` |
| `CTRL` | post-change source | **0.2** | `26134a93…` |

- ⭐ `IDENTITY` — `OLD == NEW`. The plumbing did not move the champion's play **by one action**.
- ⭐ `POSITIVE` — `CTRL != NEW`, and **20/20 games diverge**. The knob **binds**.
- ⭐⭐ `AUDIT-ADJUDICATED` — `HeuristicPriorConfig` has **no `fpu_reduction` field at all** on the
  OLD tree, and has one on the NEW tree where `POSITIVE` shows it reaching play. The audit's finding
  is adjudicated as a pair of numbers, not asserted.
- `ONE-WHEEL` — all three legs on `carc_rs_binary_sha f6316d42838574de`.
- `TWO-TREES` — `OLD` and `NEW` resolved different source trees (or the A/B tested nothing).

⛔ **An identity result WITHOUT the positive control is worth nothing:** the hard-coded `None` this
round removes would have passed `IDENTITY` perfectly, every time.

### 9.2 ⛔ WHY THERE IS NO `IDENT` PREFLIGHT **CELL**

`measurement/phasegate_prep` carried one — 40 throwaway decks of `gate=none` — and it was right to.
**Its wheel moved.** A stale `carc_rs` would have served a gate-blind arbiter, and only games could
prove the new binary reproduced the old behaviour where it should.

**This round makes NO rust change.** `carc_rs` already accepted `Option<f64>` in that slot and
`carc_core::search` already implemented the rule; the fix is python plumbing. The wheel is therefore
a **constant of the comparison** — `ONE-WHEEL` asserts it in the golden gate, and `G-WHEEL-SAME`
asserts it across the round — and the golden gate covers **the only thing that did move**, over 20
games at a tiny budget instead of 80 games at 22016.

⭐ **The saving is ~11 core-hours and, more importantly, one fewer band-adjacent archive.** ⚠️ The
substitution is only valid *because* the wheel does not move; if a future round in this family
touches rust, the `IDENT` cell comes back.

### 9.3 The smoke — 8 games per box, throwaway range, production knobs

⛔ **Emits no outcome key.** Its one substantive job beyond liveness: it drives the **real argparse**
and the adjudicator reads the **resolved knob back out of the emitted `manifest.json`**.

⭐ That framing is the PG-D7…D9 lesson in one line: three separate launcher defects — an ambiguous
`--out`, a silently-defaulted `walled` rules profile, and a **missing `--paired`** that would have
zeroed `n_paired` on every cell — all survived review and were caught only by a smoke adjudicated
against **emitted output**.

⚠️ **The local box smokes the FPU flag and the laptop smokes the C-PUCT flag**, because they are
different code paths in `_build_champ_cfg` and each box must exercise the one it will actually run.

---

## 10. WHAT THIS ROUND DOES NOT DO

- ⛔ It does not touch `governance/PRODUCTION.yaml` on any branch.
- ⛔ It does not build the τ pair. `READ_RULE.md` §6 freezes its trigger and its shape; the plumbing
  it would need (`--cand-tau-p`) does not exist and is deliberately not built.
- ⛔ It does not measure the owner-hole. No branch touches `measurement/e4_games/`.
- ⛔ It does not bracket either axis (§2.1).
- ⛔ It says nothing about the arbiter-armed champion (§2.3).
