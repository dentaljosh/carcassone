# 22016 vs 11008 BUDGET H2H — AMENDED RE-ADJUDICATION

> **BRANCH FIRED: `H-POSITIVE`** (READ_RULE.md §4, first-match-wins, `VOID` first). **14/14 gates PASS.**
> `adjudicate_amended.py --selftest` **20/20 PASS**; real read on the laptop, same archive,
> same 1400 records. Machine verdict: [`../h2h_22016_prep/ADJUDICATION_AMENDED.json`](../h2h_22016_prep/ADJUDICATION_AMENDED.json).

## ⚠️ PROVENANCE CHAIN — READ BEFORE CITING ANYTHING BELOW

This is a **separate, owner-authorized, post-void adjudication.** It does **not** overwrite,
supersede, or re-label the frozen instrument's verdict. Both readouts stand side by side:

| # | instrument | verdict | status |
|---|---|---|---|
| 1 | `adjudicate.py`, **frozen, unedited**, `e465c8a2` | **`U-UNREADABLE`** (`G-REV`, `G-TIEARB` FAIL) | **the verdict of the frozen instrument. Unchanged. Still true.** → [`ADJUDICATION_READOUT.md`](ADJUDICATION_READOUT.md) |
| 2 | `adjudicate_amended.py` (M1/M2/M3) | **`H-POSITIVE`** | owner-authorized re-read of the **same archive**, 2026-08-25, owner verbatim *"h2h option 1"* |

**Integrity disclosure, carried forward and not softened:** the diagnostic `z` was **visible
before the amendments were authored and before the owner authorized this re-read** — the
frozen `RECON` gate must print the analyzer and witness values in order to compare them, so
adjudicating at all revealed `D` and `z`. The amendments were nonetheless forced by
**archive-independent** facts provable from frozen source and the pre-launch record alone
(`G-TIEARB`'s remedy is pre-registered *verbatim* in READ_RULE §3; `G-REV` compared two
encodings that can never be equal for any archive of this design). Full argument, residual
risks, and the fixture trace: [`../h2h_22016_prep/AMENDMENTS.md`](../h2h_22016_prep/AMENDMENTS.md).
**A reader is entitled to discount this read accordingly.** It is a post-void re-read of a
known statistic, not a blind adjudication.

---

## §1 — THE RESULT

```
D (paired points margin, candidate minus opponent) = +1.2293 pts/deck
SE(D)                                              =  0.48784
z_D                                                = +2.5199        (bar: >= +2.0)
n_common                                           =  700 decks
W / D / L = 714 / 29 / 657 over n_scored = 1400     winrate = 0.5204
```

**`D > 0` means the larger budget won.** Per READ_RULE §4 `H-POSITIVE`: **the doubling above
production still pays** at this rung.

Analyzer and witness (independent from-scratch recomputation over the 1400 raw records) agree
exactly on all five statistics — `RECON` PASS at `rel 1e-6 / abs 1e-9`.

### Elo display — limb: **own-ratio** (`|z| >= 2.0`, per READ_RULE §1)

```
elo_D                     = +14.2 elo
elo_per_point (realized)  = +11.51 elo/pt     ⚠️ OUTSIDE the in-family bracket [16.74, 19.35]
2-sigma bound             = 0.9757 pts  ≈  ±11.2 elo   (through the own ratio)
```

⚠️ **THE ELO SCALE IS A FLAGGED WITNESS ANOMALY.** READ_RULE §1 requires that a realized
`elo_per_point` outside `[16.74, 19.35]` be **flagged and never used as a branch input**. It
is flagged; it was not a branch input (the branch is decided purely in points and `z`).
**This flag must travel with every elo figure this cell ever produces.**

The anomaly is substantive, not cosmetic: **11.51 < 16.74** means this cell converted points
into *wins* less efficiently than every in-family reference. The extra budget buys **score
margin more than it buys victories** — `winrate_z` is only **+1.523** against the deck-paired
**`z = +2.520`**. For scale, through the *pinned bracket* instead the same `D` would read
**+20.6 … +23.8 elo**; through this cell's own ratio it reads **+14.2**. Any elo quotation
must say which scale it used.

### ⚠️ Type-M (magnitude) caveat — mandatory alongside the point estimate

The realized effect **`+1.229 pts` sits BELOW this cell's own 80%-power minimum detectable
effect of `±1.55 pts`** (READ_RULE §2.2). A `z` only just over the bar, on an effect smaller
than the design was 80%-powered for, is the classic **significance-filter regime: the sign is
the reliable part, the magnitude is biased upward.** The project's own standing rule —
*"never promote a finding from a single screen"* — applies. **Cite `D` as "positive, of order
+1 pt/deck", not as a calibrated `+1.23`.**

Countervailing and worth recording: realized **`σ_D = 12.91`** came in *below* every sizing
model (A 13.15 / B 13.60 / C 14.67 — the cell sized on conservative C), so realized
`2σ = ±0.976 pts` against the `±1.109` design claim. The instrument resolved slightly
**tighter** than promised.

---

## §2 — GATE TABLE (14/14 PASS)

| gate | result | note |
|---|---|---|
| `G-BAND` | PASS | `148000000000`, `n_decks=700`, `seatings=2` |
| `G-DECKS` | PASS | `n_common=700`; no out-of-range seed; no single-seat deck |
| `G-SINGLEVAR` | PASS | differs in **exactly** `k_dets` (16/8) + `total_sims` (22016/11008); `sims_per_det=1376` both sides; leaf hash, `c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`, endgame handoff identical |
| `G-REV` | **PASS (M1)** | `rev_hex='e465c8a270'` is prefix of pinned = True; `whole_repo_dirty_flag=True` **recorded**; `SRC_CLEAN.jsonl` 19 boundaries, `dirty=none` |
| `G-BLIND` | PASS | `3a0a631b` 40-hex, ancestor of HEAD, introduced the FROZEN banner, `BLIND_PROOF` agrees |
| `G-LEAF` | PASS | cand == opp == `a36d2e15a3b3d71d` |
| `G-RULES` | PASS | `fixed_v1`, `r9_env_ok`, `r9_env_observed` |
| `G-BACKEND` | PASS | `rust`; `mixed_builds=false`; `converted_sides=["candidate","opponent"]` |
| `G-BUDGET` | PASS | `(16,1376,22016)` / `(8,1376,11008)`; product identity both sides |
| `G-TIEARB` | **PASS (M2)** | `cand_tiearb.enabled=False`; alias `champion.tiearb_enabled=False`; **stray keys (alias excluded) = none** |
| `G-EXACT` | PASS | `exact_k=2`, `marginalized`, identical both sides |
| `G-N` | PASS | `n=1400`, `n_failed=0` (**0.000%**), `n_common=700 ≥ 560` |
| `G-SAT` | PASS | winrate `0.5204` ∈ [0.35, 0.65] |
| `RECON` | PASS | analyzer vs witness exact on all five statistics |

M1 and M2 were verified **tightening-or-preserving by execution**, not by argument:
`--selftest` 20/20, with the `G-REV`, `G-TIEARB-cand-armed` and `G-TIEARB-opp-armed`
fixtures all still failing correctly.

---

## §3 — LICENSED CONSEQUENCES, EXACTLY PER READ_RULE §4

### ✅ Licensed: the decay-closure row amendment

READ_RULE §4 `H-POSITIVE`: *"**re-opens** the budget-headroom axis as a live strength lever
and **falsifies the decay-bound closure's operative reading** (`docs/LEVER_INDEX.md`, MEMO §9)
at this rung — the row **must be amended, not merely annotated**."* Draft text in §4 below,
**for the orchestrator to apply** — main-tree docs are not edited from here (latch conventions).

### ⛔ NOT licensed: anything about deploy

READ_RULE §4, verbatim: *"**It licenses NOTHING about deploy.** F costs **2× the wall-clock
per move** of production by construction; whether that is affordable is an **owner** decision,
and this cell neither makes nor recommends it. **No `PRODUCTION.yaml` change follows from this
branch without a separate owner ruling.**"*

The realized clock confirms the 2× is real and not softened by sublinearity: candidate
**3449.2 ms/move** vs opponent **1721.3 ms/move** = **2.00×** (the pre-launch smoke had
suggested a milder 1.85×). **Do not read `H-POSITIVE` as "deploy k16×1376".**

### ⛔ Still out of scope (READ_RULE §5, unchanged by this branch)

Nothing about **`k8×2752` at 22016** (only one allocation was measured — the allocation
question at 22016 remains open) · nothing about **44032 or the 5504↔11008 rung** · nothing
about **deployability** · nothing about the **tie-arbiter** (OFF both sides by construction) ·
nothing **absolute or superhuman** — this is a self-anchored contrast between one champion
and itself, and it **moves neither structural blocker in `CLAUDE.md`** · the standing
**`walled` R9-off** caveat every `fixed_v1` cell carries.

---

## §4 — DRAFTED ROW AMENDMENT (for the orchestrator to apply; do not apply from here)

Target: `docs/LEVER_INDEX.md` **line 275**, the **budget-headroom decay bound** row. Proposed
insertion immediately after the row's existing *"⚠️ THE +54 ELO CENTRAL IS SUPERSEDED …"*
banner clause, so the amendment is impossible to miss on a grep:

> ⚠️ **THE OPERATIVE READING IS FALSIFIED AT THE 11008→22016 RUNG (2026-08-25,
> `measurement/h2h_22016_20260824/`, band 148e9).** The closure's operative sentence — *"the
> honest bracket ≈ [−35, +49] elo, **SPANS ZERO**"*, and its corollary *"22016 is the first
> rung this bound speaks to, and the bound now says it is **worth ~nothing**"* — was tested
> **directly**, not by extrapolation, on the licensed route the closure itself names: a
> within-band deck-paired head-to-head, `n=700` decks × 2 seatings = 1,400 games, arbiter off
> both sides, single-variable (`k_dets` 16 vs 8 at fixed `sims_per_det=1376`), same leaf
> `a36d2e15a3b3d71d` both sides, rust both sides, `fixed_v1`+R9, `exact_k=2`.
> **RESULT: `D = +1.229 pts/deck`, `SE 0.488`, `z = +2.52`, `n_common = 700` ⇒ branch
> `H-POSITIVE`.** **The sign is now RESOLVED POSITIVE at this rung and zero is excluded at
> 2σ — which the closure's zero-spanning bracket did not do.** The mechanism sentence
> *"above 5504 the deeper pick MOVES but does not IMPROVE"* is **contradicted at 11008→22016
> specifically**: the deeper pick measurably improves. ⚠️ **PRECISION, DO NOT OVERSTATE — the
> closure's +7.1 elo CENTRAL IS NOT ITSELF EXCLUDED.** The closure priced the *entire
> remaining tail* above 11008 at `H = +0.5652 pts/game`; this cell measures `+1.229 ± 0.488`
> for the **first doubling alone**, i.e. ~2.2× the whole-tail central — but that difference is
> only **z ≈ 1.36**, well short of a rejection. What is falsified is the *zero-spanning /
> worth-nothing* reading, **not** the magnitude of the central. ⚠️ **TYPE-M:** the realized
> effect sits **below** the cell's own 80%-power MDE (±1.55 pts), so the **sign is the
> reliable part and the magnitude is biased upward**; do not propagate `+1.229` as calibrated.
> ⚠️ **ELO SCALE FLAGGED:** realized `elo/pt = 11.51`, **outside** the in-family bracket
> `[16.74, 19.35]` — budget bought score margin more than wins (`winrate_z +1.52` vs paired
> `z +2.52`); through its own ratio `D ≈ +14.2 elo`, through the pinned bracket `≈ +20.6…23.8`.
> **⛔ LICENSES NOTHING ABOUT DEPLOY** — realized cost ratio **2.00×** wall-clock/move;
> `PRODUCTION.yaml` untouched; a deploy needs a separate owner ruling. **Scope: ONE doubling,
> ONE allocation (`k16×1376`).** Says nothing about `k8×2752` at 22016, about 44032, or about
> the 5504↔11008 rung below. ⚠️ **PROVENANCE:** the frozen adjudicator returned
> **`U-UNREADABLE`** (two archive-independent instrument defects, `G-REV`/`G-TIEARB`); this
> `H-POSITIVE` is an **owner-authorized post-void re-read of the same archive** under amended
> gates, with the diagnostic `z` visible before authorization — see
> `measurement/h2h_22016_prep/AMENDMENTS.md`. Band **148e9 is SPENT** and retires from
> confirmatory use. → [AMENDED READOUT](ADJUDICATION_READOUT_AMENDED.md)
> · [FROZEN READOUT](ADJUDICATION_READOUT.md)

**Cross-reference also owed** (same grep-reachability argument): the two
**tie-triggered search escalation** rows (lines 214/216) both cite *"uniform deep search above
~5504 sims/det is priced ≈ 0 on average (budget-headroom row)"* as their premise. That premise
is now falsified at this rung. Their **conclusions are unaffected** — they died on
*concentration at tied plies*, a separate claim — but the premise sentence needs a pointer so
a future reader does not inherit a superseded justification.

---

## §5 — REMAINING CLOSE-OUT (orchestrator/owner; nothing applied from here)

Per `DESIGN.md` §10, now on the `H-POSITIVE` branch:

1. `experiments/results.csv` row — proposed `exp_id`
   **`budget_h2h_k16x1376_22016_vs_champ_k8x1376_11008_fixed_v1_n1400_b148e9`**
   (⚠️ `fixed_v1` refuses a row unless the profile name is in the `exp_id`).
2. `DECISIONS.md` index line.
3. Status banners on `DESIGN.md` **and** `READ_RULE.md`.
4. Governance: `BAND_REGISTRY.csv` — band **148e9** `decision_influenced` + **retire** it from
   confirmatory use. A `CLAIM_REGISTRY.csv` row if a claim is minted (**recommend minting**:
   this is the first direct measurement above 11008 on the current instrument).
5. `STATUS.md` top block.
6. Roadmap line in `docs/PROGRAM_ROADMAP_2026-07-07.md`.
7. The §4 `LEVER_INDEX` row amendment above.
8. `python3 scripts/doc_lint.py`.

**Plus the standing lesson from the void** (`AMENDMENTS.md`): the selftest fixture generator
synthesised a manifest the analyzer of record cannot emit, so a 20/20 green certified an
unreadable instrument. The smoke archive already on disk before game 1 carried **both** tells.
**Proposed standing rule for this prereg family: the launcher's smoke step must end by running
the cell's own adjudicator against the smoke archive.** Worth a `REVIEW_LOG` / `LEVER_INDEX`
line independent of this cell's result.
