# PHASE-GATED TIE ARBITRATION — SIZING, COST AND ETA

> **DESIGN ONLY. UNLAUNCHED, UNFUNDED, UNBUILT.** 0 games, no band claimed, no governance file
> touched, no source outside `measurement/phasegate_prep/` created or modified.
> Pair: [`DESIGN.md`](DESIGN.md) · [`READ_RULE.md`](READ_RULE.md).

---

## 1. ⭐ THE OPTIONS TABLE

| option | cells | n / cell (decks) | games | **core-h** | **wall, local W14 + laptop W22** | what it buys |
|---|---|---|---:|---:|---:|---|
| **A1** ⭐ *recommended* | `IDENT` + `ARB_FULL` + `ARB_EARLY` | 40 / **400** / **1,200** | 3,280 | **320** | **13.5 h** | The primary, at the funded bar. Early resolved to **±0.80** at 2σ |
| **A2** | same 3 cells, anchor widened | 40 / **1,200** / **1,200** | 4,880 | **518** | **21.9 h** | A1 **plus** a `FULL−EARLY` deck-paired contrast at n=1,200 (2σ ±1.06) |
| **B1** | + `ARB_MID` + `ARB_LATE` | 40 / 400 / **800** ×3 | 5,680 | **534** | **22.6 h** | Full 3-way decomposition, each slice ±0.98 at 2σ |
| **B2** | + `ARB_MID` + `ARB_LATE` | 40 / 400 / **1,600** ×3 | 10,480 | **964** | **40.7 h** | Full 3-way at the brief's **±0.7** slice CI |

**Wall is the box-balanced figure** at the realized fleet rate **23.66 worker-s/wall-s** (§4).
Footnotes, all of which move the numbers in a knowable direction:

- ⭐ **Balanced requires splitting the largest cell into two same-config sub-cells** on disjoint deck
  sub-ranges of one band (`ARB_EARLY_L` local / `ARB_EARLY_R` laptop). Naive whole-cells-per-box on
  A1 gives **15.4 h** instead of 13.5 h — local finishes 4.5 h before the laptop.
- ⭐ **The 23.66 rate is CONSERVATIVE** — it is measured on a *python* self-play job at the DRAM
  wall, not on rust fair PIMC (§4). At 85% fleet efficiency every wall falls ~23%:
  **A1 10.5 h · A2 16.9 h · B1 17.5 h · B2 31.5 h.**
- ⚠️ **The gated cells' cost rests on a biased proxy** (§5) whose bias runs *against* us. Residual
  risk **≈ +5% wall** on `ARB_EARLY`/`MID`/`LATE`. The §9 smoke measures the true value **before**
  the round starts.
- ⛔ **Compute above excludes the build: 15–20 h of agent time, 0 compute (§7).** The instrument
  does not exist.

**Recommendation: A1.** The 3-way decomposition is explicitly secondary in the brief, B2 costs 3×
A1 for it, and B1's ±0.98 slices cannot resolve the +0.80 bar they would be graded on — it buys the
*shape* of a decomposition without the power to read it. If the 3-way is wanted, **B2 or nothing**.

---

## 2. THE BAND

⭐ **PROPOSED: `154000000000`.** ⛔ Not claimed, not registered, not appended to
`governance/BAND_REGISTRY.csv`.

- Highest registered id is `153000000000` (`spent`, 2026-08-27, invasion round 3). `154e9` is the
  next monotone id.
- Tree sweep 2026-08-28: **0 references** to `154000000000` anywhere.
- ⚠️⚠️ **`146000000000` IS A TRAP** — **absent from `BAND_REGISTRY.csv` but carrying 20 references
  in the tree.** A "next free id" search trusting the registry alone would pick it. ⛔ **Do not
  reuse 146e9.** The registry is necessary but not sufficient; the **tree sweep is the binding
  check** and is re-run immediately before the CSV append.
- Also noted: `107000000000` is the only row still marked `active`.

---

## 3. POWER — from realized numbers only

**The sizing constant, derived from Stage-2 Phase B cell `ARB` and nothing else:**

```
M = +3.0700 , paired_z = +4.445 , n_paired = 400 DECKS  (= 800 games)
se(M)   = 3.0700 / 4.445   = 0.6907  pts/game
sigma_D = 0.6907 * sqrt(400) = 13.81 pts/deck
```

⚠️⚠️ **`n` IS 400 DECKS, NOT 800.** The brief's "n=800 paired decks" is the **game** count; the cell
is 400 seat-balanced decks × 2 seatings. The `SE ≈ 0.69` in the brief is correct
(`0.6907`, verified), but sizing on 800 decks would understate every `n` below by **2×**.

| n decks | games | `se(M)` | **2σ MDE (50% pwr)** | resolvable at **80% pwr** |
|---:|---:|---:|---:|---:|
| 400 | 800 | 0.691 | ±1.381 | +1.93 |
| 800 | 1,600 | 0.488 | ±0.977 | +1.37 |
| **1,200** | **2,400** | **0.399** | **±0.798** | **+1.12** |
| **1,600** | **3,200** | **0.345** | **±0.691** | **+0.97** |
| 2,400 | 4,800 | 0.282 | ±0.564 | +0.79 |

**(a) Minimum `ARB_EARLY` distinguishing "early ≥ +0.8" from zero at 2σ:**
`se <= 0.40` ⇒ `n >= (2*13.81/0.80)^2 = 1193` ⇒ **1,200 decks / 2,400 games.**

⚠️ **Stated honestly:** at 1,200 decks a *true* +0.80 gives `z = 2.01` — **50% power**. What the
`n` guarantees is the **bounding** direction, which is what the decision needs: a null returns
`UB95 < +0.80`, a real 95% bound (`E-DEAD`), not an absence of evidence. **80% power on +0.80 needs
2,337 decks / 4,674 games — 1.95× the cost**, and is not recommended.

**(b) 3-way with each slice's 95% CI at ±0.7:**
`se <= 0.35` ⇒ `n >= (13.81/0.35)^2 = 1557` ⇒ **1,600 decks / 3,200 games per slice** (Option B2).
*At the looser 1σ reading it would be 389 decks — a screen, not a verdict.*

**The bar `+0.80`** is 77% of the proportional-share expectation
`0.3380 × 3.07 = +1.038` pts/game — deliberately **below** proportional, so a uniformly-distributed
arbiter's early slice **convicts**. `+1.038` is a pre-registered companion, ⛔ never a branch input.

### 3.1 ⛔ Cross-cell deck-matching buys almost nothing

Realized cross-cell correlation between two arbiter cells on one deck set: **`rho = +0.1237`**
(`b64_cell/verdicts/READOUT_B64.md`).

```
se(FULL - EARLY) = sqrt(2) * (13.81/sqrt(n)) * sqrt(1 - 0.1237) = 18.28 / sqrt(n)
```

`sqrt(1-0.1237) = 0.936` ⇒ a **6.4% SE reduction**, ~12% fewer games for equal resolution. This
replicates `simsplit_alloc_20260812` (*CRN bought only 9.9%*), and the b32v64 cell's own committed
`se(D) = 0.7133` assumed `rho = 0` for the same reason. ⛔ **Never size on an assumed CRN gain.**

⭐ Deck-match anyway — but for the **right** reasons: it kills the deck-draw confound, lets
`G-DECKS` prove one deck set, and keeps every contrast **within-band**, the only robust class under
CL-068. ⛔ The contrast is a **companion**, never the primary (it is ~1.3× noisier and answers a
different question).

---

## 4. COST INPUTS — realized, with the trap named

| quantity | value | source |
|---|---:|---|
| opponent (unmodified champion) | 1,808.2 ms/move | Stage-2 `ARB` `rung_ms_per_move` |
| candidate (champion + arb B=16) | 4,383.6 ms/move | Stage-2 `ARB` `champ_prefix_ms_per_move` |
| `ms_ratio` | 2.4242 | candidate ÷ opponent |
| `phi` (fired tied tile plies/game) | 17.573 | realized in-cell |

⚠️⚠️ **FIELD-NAME TRAP:** in `eval_fair_puct` (lines 2361/2371/2389) `champ_prefix_ms_per_move`
**IS THE CANDIDATE SIDE** — the opposite of `eval_puct_priors`. Swapping them **inverts the cost
verdict**.

```
champion-vs-champion  = 2 * 72 * 1.8082            = 260.4 worker-s/game
ARB_FULL              =     72 * (4.3836 + 1.8082) = 445.8 worker-s/game
arbiter overhead                                    = 185.4 worker-s/game
```

Independent cross-check: `phi 17.573 × 9.57 worker-s/fired ply = 168.2`. The ms/move route is 10%
higher and is **used throughout because it is the conservative one and it is directly measured.**

**Per-cell:**

```
ARB_EARLY = 260.4 + 0.3380*185.4 = 323.1   (27.5% cheaper than FULL)
ARB_MID   = 260.4 + 0.3059*185.4 = 317.1
ARB_LATE  = 260.4 + 0.3561*185.4 = 326.4
IDENT     =                        260.4
```

**Fleet throughput** — the only realized two-box figure for this shape
(`measurement/tiearb2_20260816/PROGRESS.md` §[t4]):

```
combined     98.6 games/h at 864 worker-s/game =  23.66 worker-s / wall-second   (66% of 36 nominal)
  local W14  61.7 s/game  at 864 worker-s/game =  14.00 worker-s/s   (~1.00 x W14)
  laptop W22 23.66 - 14.00                     =   9.66 worker-s/s   (~0.44 x W22)
```

⇒ ⭐ **local W14 is 1.45× laptop W22.** That asymmetry, not the nominal `W`, drives cell→box
assignment. ⚠️ The figure is from a **python k4×688 self-play** job whose own log root-causes it to
the **DRAM wall**; rust fair PIMC is markedly less memory-bound, so the true rate is **likely
higher** — hence the 85%-efficiency alternative in §1.

⛔ No timing statistic is a branch input, so tenancy is result-safe — but census by **FULL ARGS**
(`ps -eo args`), never `-C python`: one niced 1-core DRAM-churner inflated a saturated W=22 eval
~1.8×/move on 2026-08-26.

---

## 5. ⚠️ THE WEAKEST INPUT — the early fired-share proxy

Computed here from `measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl` (corpus
`champ449`, 449 games, 31,827 tile plies), bucketed on each row's own `phase_bucket`:

| phase | tile plies | exact-tied | tie rate | **share** | mean tie size |
|---|---:|---:|---:|---:|---:|
| early | 10,280 | 6,868 | 0.6681 | **0.3380** | 4.12 |
| mid | 10,324 | 6,217 | 0.6022 | **0.3059** | 7.40 |
| late | 11,223 | 7,237 | 0.6448 | **0.3561** | 13.41 |

⛔ **BIASED, AND THE BIAS RUNS AGAINST US:**

1. It is the **raw** exact-tie share; the arbiter fires on the **deduped** arm set (funnel: 65.98%
   exact-tie → 40.4% deduped scoreable). **Mean tie size varies 3.3× across phases**, and large late
   tie-sets are overwhelmingly duplicate placements (69.5% pure-duplicate pooled) ⇒ **dedup cuts LATE
   hardest** ⇒ the true early share is likely **higher** than 0.3380 ⇒ `ARB_EARLY` costs **more**
   than §4 says. Sized residual: **≈ +5% wall**.
2. `tile_gap_rows.jsonl` **carries no repr-dedup column** — the deduped-by-phase split is **not
   recoverable from any artefact on disk.**
3. The census ran `rules_profile: walled`, R9 **off**; the cells run `fixed_v1`, R9 **on**. The
   phase cut itself is rules-independent (a deck count); the fired share is not.

⭐ **THE FIX IS FREE AND IS IN THE BUILD.** Per-phase fire counters in the rust `stats()` (§7 item 1)
mean `ARB_FULL` measures its own exact per-phase split as a by-product, and the **§9 smoke returns
it before the round starts** — so a materially different share revises the ETA up front instead of
being discovered inside the run.

---

## 6. ⛔ THE PLY-GATE KNOB DOES NOT EXIST

Searched `rust/carc/carc-core/src/`, `rust/carc/carc-py/src/`,
`scripts/classical_search/eval_fair_puct.py`, `scripts/tiletie/`.

**What exists** (`rust/carc/carc-core/src/search/mod.rs`): `tiearb_enabled: bool` (`:183`) and
`tiearb_max_plies: usize` (`:201`, default 400).

⛔⛔ **`tiearb_max_plies` IS NOT A FIRE-GATE.** `tiearb.rs:112–116` documents it as the **playout ply
ceiling** — how deep a single `tier1-greedy` *rollout* runs before aborting (a base game is ~144
plies). `carc-py/src/lib.rs:1653` rejects `< 1` with *"it is a GUARD, not a truncation"*. It says
nothing about which **game** plies the arbiter fires at.

**The hook is unconditional** (`rust/carc/carc-core/src/fair/mod.rs:654`): once
`tiearb_enabled`, the arbiter fires at **every** detected tie. No window, no phase test, no min/max
fire-ply, no env var.

⭐ **The good news:** `tiearb_arbitrate` already receives `g`, and `crate::fair::k_remaining(g)`
(`fair/mod.rs:190`) is in scope in the same module and is documented as **identical** to
`fair_agent.k_remaining`. **The gate is a one-line predicate at an existing call site.**

⛔ **Use `crate::fair::k_remaining(g)`, NEVER `g.state.deck_len()`** — `search/window_diag.rs:156`
uses the latter, which omits the tile in hand and is **off by one** against the census axis.

---

## 7. BUILD LINE ITEMS — 15–20 h agent time, 0 compute

| # | item | files | est |
|---|---|---|---:|
| 1 | **rust: `tiearb_phase_gate` + per-phase counters.** New `SearchConfig` field (default `All`); `TiearbPhaseGate` enum + `phase_bucket()` in `tiearb.rs`; gate test in `tiearb_arbitrate`; `fired_/pickchanges_{early,mid,late}` in `stats()` | `carc-core/src/{search/mod.rs, tiearb.rs, fair/mod.rs}` | **4–5 h** |
| 2 | **carc-py plumbing.** kwarg + fail-closed validation + `stats()` export + `__repr__` | `carc-py/src/lib.rs` (`:1533`, `:1653`, `:1700`, `:1816`, `:2588`) | **1.5–2 h** |
| 3 | **python harness.** `--cand-tiearb-phase-gate`; `tiearb` dict key; **telemetry in `_cand_tiearb_telemetry`** — this is `G-GATE`'s address and without it the gate is unwitnessed | `eval_fair_puct.py` (`:1029`, `:2311`, `:3417`) | **1.5 h** |
| 4 | **tests.** gate=`all` byte-identical to today's ungated arb; gate=`none` byte-identical to the champion; **golden boundary table asserted against the python `phase_bucket`**; partition; disjointness; gated-out ≠ error | `tests/test_tiearb_phase_gate.py` | **2–3 h** |
| 5 | **this pair's instrument.** `run_cells.sh`, `analyze_phasegate.py`, `screen_lib.py`, `selftest_fixture/`, `WORKERS.conf`, `BAND_CLAIM.json`, instrument tests | `measurement/phasegate_prep/` | **6–8 h** |

⭐ Item 5 **forks** `invasion_screen_r3_prep/screen_lib.py` — reuse `cross_box_rev_gate()` (`:1141`,
the IS-A1 fold), `paired_margin()`, `rev_matches()`, `is_hex40()`.
⛔ **Two gates must be REWRITTEN, not copied** (an unedited copy voids every healthy cell):
`G-DECKS` (this round's deck ranges **overlap by design**) and `G-LEAF` (here the two sides carry the
**SAME** leaf — the arbiter is a root hook, not a leaf term). Plus one new gate, `G-SUBPOOL`.

**Identity property (the thing that makes the knob safe):** `gate = All` ⟹ bit-exact with today's
ungated arbiter; `gate = None` ⟹ bit-exact with the unmodified champion. **Proved by selftest, not
asserted**, and a hard abort.

⚠️⚠️ **THE RUST CHANGE REBUILDS THE WHEEL ⇒ `carc_rs_binary_sha` CHANGES ⇒ THE PRODUCTION ARBITER'S
`IDENT` INHERITANCE IS RE-OWED** (`G-WHEEL-SAME`: *a changed wheel re-owes an IDENT cell*). This
round carries its own. **Any other live pair inheriting an earlier ident across this wheel change
must be told.** Build in a **worktree**; install the **same wheel file** on both boxes (scp +
`--force-reinstall --no-deps`), ⛔ never a laptop-local `maturin build`.

---

## 8. ⚠️ CONFIG DRIFT — THE ARBITER IS NOW PRODUCTION, AT A DIFFERENT `B`

**The finding that most constrains this design, and it post-dates the +3.07 measurement.**

`governance/PRODUCTION.yaml`:

- `tiearb_folded_in: "2026-08-20"` — desktop, **`B=64`, `J<=4`**, owner *"I'm buying b64"*
- mobile arbiter folded **2026-08-24**; `fair_deploy.tiearb.threads: 8` armed 2026-08-22

⇒ **"the champion" now MEANS champion + arb(B=64).** The +3.07 was measured with the arbiter as a
**candidate at B=16** against an arb-off champion.

⭐ **Design decision: run `B=16` with the opponent arb-OFF — reproduce the Stage-2 contrast
exactly.** The anchor's whole job is to reproduce +3.07, which is a B=16 number. At B=64 the anchor
measures a different and larger quantity (the b64 cell's `WIDE` arm read `+5.3773` vs `NARROW`'s
`+3.6607` against the unmodified champion) and the instrument-validation property is forfeited.

⛔ **The price, carried on every branch:** the answer is about the **B=16** arbiter; transfer to the
**deployed B=64** arbiter is an **assumption, not a measurement**. The offline
`Δ(16→64) = +0.0670 pts/tied ply` ⛔ **may not be projected into game points**
(`offline_ratio_disclaimer`), so the gap cannot be closed by arithmetic either.

---

## 9. THE PHASE THRESHOLDS — PINNED

**Source of record:** `scripts/measurement_infra/sample_agreement_roots.py:96`, copied verbatim into
`scripts/tiletie/chain_census.py:63` (*"NOT redefined independently"*) and used by
`census/CENSUS.md` §6.

```python
PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}
# phase_bucket(k): STRICT inequalities on BOTH ends; falls through to "late"
```

`k_remaining` = **undrawn deck + the tile in hand** (`fair_agent.py:111`;
rust `fair/mod.rs:190`). Range **71 → 0**.

| phase | `k_remaining` ∈ |
|---|---|
| `early` | **[49, 71]** |
| `mid` | **[25, 47]** |
| `late` | **[0, 23]** ⚠️ **plus `k = 48` and `k = 24`** |

⚠️⚠️ **`k=48` and `k=24` match no interval and fall through to `"late"`.** Verified by executing the
canonical function, not inferred:

```
k=71 -> early   k=49 -> early   k=48 -> late    k=47 -> mid
k=25 -> mid     k=24 -> late    k=23 -> late
```

⛔ **Reproduced, not repaired.** Every artefact keyed on `phase_bucket` — the CL-070 root bank,
`split_tiearb2.py`'s strata, CENSUS.md §6, and the Stage-1 cuts table this round is testing —
carries this behaviour. `ARB_EARLY` therefore does **not** fire at `k=48`. Repairing the edge is a
separate, tree-wide change that re-labels prior artefacts and is **out of scope**.

⭐ **The cut is fully online-computable** and requires no new engine work — which is the single
biggest thing that went *right* in this design.

---

## 10. WHAT COULD BLOCK THE ROUND

| # | risk | status |
|---|---|---|
| 1 | ⛔ **The ply-gate knob does not exist** (§6) | **15–20 h build**, specified, not built |
| 2 | ⚠️ **`PRODUCTION.yaml` runs `B=64`; +3.07 is a `B=16` number** (§8) | Resolved by design decision; **price disclosed on every branch** |
| 3 | ⚠️ **Deduped fired-share by phase is unrecoverable from disk** (§5) | Proxy used; **fixed free** by the build's counters + the smoke |
| 4 | ⛔ **The steering-ruler inference has a broken link** — the offline early cut was `+0.1148`, `F = 1.303`, i.e. **positive and unresolved**, not zero; and F4 discredits that judge family in *both* directions | **Riders are mandatory on every branch** (`READ_RULE` §5.1). The honest primary product is the judge-free decomposition |
| 5 | ⚠️ **Anchor may not reproduce** on a fresh band + new wheel | `G-ANCHOR` is a **hard ordering**: a failed anchor prints **no** phase statistic. ⭐ Itself a finding |
| 6 | ⚠️ **New wheel re-owes the production arbiter's `IDENT`** (§7) | This round carries its own; other live pairs must be told |

⛔ **Nothing above is a reason the design cannot be executed. Every one is disclosed rather than
resolved, which is the point of freezing before funding.**
