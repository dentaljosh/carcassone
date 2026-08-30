# READ_RULE — S1 GATE G3 (THE THREE-ARM DECOMPOSITION CELL)

> # ⛔ COMMITTED BEFORE ANY G3 STATISTIC EXISTS
>
> **Status: PRE-OUTCOME.** At the moment this file was committed, `0` G3 games
> had been played, no `summary.json` existed under any G3 out-dir, and no band
> had been claimed. This is the house rule (`CL-079`) and `CL-084`'s binding on
> S1 (*"no selecting-then-reporting; doses, arms, band, deck ranges and the
> branch map freeze before game 1"*).
>
> Parent design: [`DESIGN.md`](DESIGN.md) §6.4 (with §4, §5.3–5.5, §6.3, §9.2,
> §10). Sizing: [`SIZING.md`](SIZING.md) §3–§6. Upstream gate:
> [`G1_VERDICT.md`](G1_VERDICT.md) (`G1-EXPRESSES`, **d\* = 0.25**).
> **0 games · 0 band claimed · 0 `results.csv` rows · `PRODUCTION.yaml` untouched.**
>
> ⛔ **THE PAIR IS LAW.** Where this file and `DESIGN.md` §6.4 disagree, DESIGN
> wins and this file is the defect. Where a number here is marked
> *derived at freeze*, DESIGN was silent and the derivation is recorded
> **pre-outcome** so it cannot be reconstructed favourably afterwards.

---

## 1. WHAT G3 IS

G3 asks **two** questions at once, and the second is the reason the cell has
three arms rather than one:

> **P1 — deployability.** At the budget the champion actually deploys, does
> `jrules_prior_scope = "opp"` at `d* = 0.25` **beat the unmodified champion**?
>
> **P2 — asymmetry.** Is `margin(OPP) − margin(OWN)` positive — i.e. does the
> *asymmetry* do work, independent of whether the deployable half does?

⭐ **Why three arms, stated as the arithmetic.** The banked surface-B `all` cell
read a clean null (**−0.0175 pts/deck, z −0.0282**, `N4` did not fire). `all` =
own + opp. So **that null caps the SUM**, and S1 is live only if the components
are opposite-signed: if `effect(own) ≈ −1`, then `effect(opp) ≈ +1`
(DESIGN §4). Therefore:

| arm | what it buys |
|---|---|
| **OPP** | the candidate itself — P1 |
| **OWN** | the other component. ⛔ **Not optional**: without it a null on `opp` alone cannot distinguish *"no asymmetry effect"* from *"both components ≈ 0"* (DESIGN §4.2). It is also §5.4's ruler probe. |
| **ALL** | the in-band symmetric control. The banked `all` cell is on a **retired** band at the **superseded** 11008 budget and `CL-068` forbids differencing it (DESIGN §4.3), so `all` is re-measured **in-band at 22016**. |

⚠️ **The separation rests entirely on the own-component being negative.** The
sims-washout mechanism argument (deep low-visit opponent nodes never converge, so
`P` keeps a permanent share of PUCT's `U` and the boost compounds along a line)
explains why the opp component *might* be non-zero — but `scope=all` **already
contained those nodes**, so it does not by itself separate S1 from the measured
null. **Say it that way in the readout** (DESIGN §4).

---

## 2. THE INSTRUMENT (frozen)

| item | value |
|---|---|
| script | `scripts/classical_search/eval_fair_puct.py` |
| launcher | [`run_g3.sh`](run_g3.sh) + [`WORKERS_G3.conf`](WORKERS_G3.conf) |
| law | [`screen_lib_g3.py`](screen_lib_g3.py) — imported by BOTH the launcher's precondition ladder and the adjudicator, so a launcher/adjudicator drift is impossible by construction |
| adjudicator | [`analyze_g3.py`](analyze_g3.py) (`--selftest` is a pre-launch checklist item) |
| budget, BOTH sides | `--k-dets 16 --sims 1376` and `--opp-k-dets 16 --opp-sims 1376` ⇒ **22,016 per decision**, `PRODUCTION.yaml` `fair_deploy` (the 2026-08-30 promoted desktop champion). Re-asserted against the YAML at launch (`G-PROD`). |
| opponent | `--opponent fair-champion` — the **UNMODIFIED** production champion, every arm |
| leaf | `a36d2e15a3b3d71d`, **both sides, every arm**. ⭐ The hash gate is **INVERTED**. |
| rules | `--rules-profile fixed_v1` + `CARCASSONNE_FIX_R9=1` (env-latched at IMPORT) |
| endgame | `--exact-k 2`, marginalized |
| backend | rust, both sides. ⚠️ `jrules_prior_*` is **rust-only**; a nonzero dose hard-exits on a non-rust backend and a pre-S1 `carc_rs` rejects `scope` at config construction (both fail-closed). |
| tie arbiter | **OFF, BOTH SIDES.** ⚠️ A deliberate deviation — see §8. |
| pairing | `--paired`, seat-balanced, both seatings per deck |
| CRN | **ONE shared deck set across all three arms** |
| config of record | `manifest.json` |
| statistics of record | `summary.json` + the per-game `seed*_a*.json` |

**IS-D1 is binding: config is read from `manifest.json`, statistics from
`summary.json`.** No knob may be quoted from a directory name, and every gate in
the readout prints the address that answered it.

### 2.1 The three arms (frozen; owner-ratified 2026-08-30)

| arm | scope | dose | mask | n games | n decks | box |
|---|---|---:|---:|---:|---:|---|
| `CELL_G3_OPP` | `opp` | 0.25 | 31 | **1,200** | 600 | local (W 30) |
| `CELL_G3_OWN` | `own` | 0.25 | 31 | **1,200** | 600 | laptop (W 22) |
| `CELL_G3_ALL` | `all` | 0.25 | 31 | **800** | 400 | local (W 30) |

⭐⭐ **DOSE AND MASK ARE IDENTICAL ON EVERY ARM. `scope` is the only mover** —
that is what makes the three numbers a decomposition rather than three screens.
The round-level `G-ARMS` gate asserts it from the emitted manifests.

* **Dose 0.25 = `d*` from G1** — the *smallest observable* dose, **not** "the
  right dose" (`READ_RULE_G1` §6.5, carried). It cleared E1's 5% bar by 0.01pp
  and its Wilson interval straddles the bar; that marginality is on the record
  and is **not** re-litigated here.
* **Mask 31** = the frozen `joshua_bot.PRESETS["current"]` J bundle, per the
  owner's adopted answer to DESIGN §11 **Q2**. A J2-only mask is the **licensed
  follow-on**, not an arm of this cell.
* **n = 1,200 on the two gated arms** per SIZING §4.1(b) — the design's own
  arithmetic predicts ≈ +1 pt/deck on `opp`, which at n=800 reads z ≈ 1.6, i.e.
  `S1-BOUNDED-NULL` would be the modal outcome **even if the effect is real**.
  n=800 on the ALL control, which only needs to reproduce a known null.

### 2.2 The shared deck set (CRN)

```
band 161000000000
  OPP : 161000000000 .. 161000000599   (600 decks x 2 seatings = 1,200 games)
  OWN : 161000000000 .. 161000000599   (THE SAME 600 DECKS)
  ALL : 161000000000 .. 161000000399   (a PREFIX SUBSET, 400 decks)
throwaway (smoke only, NEVER in the claim): 161999999000 .. 161999999999
```

⛔ **P2 is a PER-DECK difference on the shared set, not a difference of two
means.** Differencing the means throws away the CRN the shared deck set was
bought for and would price P2 at ρ=0 whatever the true correlation is. The
`tiearb_widening` `WIDE − NARROW` precedent used exactly this statistic as its
primary. The round-level `G-CRN` gate asserts OPP and OWN are deck-identical and
ALL is a prefix subset.

### 2.3 The band

**ONE** band, `161000000000` — **PROPOSED, NOT CLAIMED**
([`BAND_CLAIM_G3.json`](BAND_CLAIM_G3.json); `run_g3.sh` refuses a real arm until
the sibling `BAND_CLAIMED_G3` file exists). One band, not three, because
**DESIGN §6.4 and SIZING §6 require one shared deck set** — three arms on three
bands would break the CRN that P2 is funded on, and would spend three bands'
`decision_influenced` retirement on one verdict.

⚠️ `146e9` is registry-absent but tree-referenced (the trap the claim order
exists for); `158e9` and `160e9` are the same shape and were dropped by the FPU
round; `155/156/157e9` belong to that round. The tree sweep — not the registry —
is the binding check, and it is **re-run immediately before the CSV append**.
The band **retires as decision-influenced the moment any statistic is read.**

---

## 3. THE DUAL PRIMARY (frozen)

* **P1 — deployability.** `margin(OPP vs the unmodified champion)`, **pts/deck**,
  deck-paired: `D(d) = (diff(d, seat 0) + diff(d, seat 1)) / 2`, then the mean
  over decks, on the arm's **own realized SE**. `diff` is candidate minus
  opponent in points, so `D > 0` ⇒ the candidate won.
* **P2 — asymmetry.** `D = margin(OPP) − margin(OWN)`, **per deck**, over the
  decks present in **both** arms.

A deck missing a seating is **DROPPED, never zero-filled**. Both statistics are
recomputed from the raw `seed*_a*.json` with `math.fsum` — deliberately a
*different* computation from the emitter's, because a witness that shares the
emitter's code path agrees by construction and witnesses nothing. `RECON`
compares the two and can only **void**, never move, a number.

**Elo is a COMPANION, never a branch input**, reported on the **deck-paired**
footing with the factor named in the field name, on every branch.

---

## 4. THE BARS — the n-threshold arithmetic, stated pre-outcome

Realized deck-paired sem at n=800 is **0.63 pts/deck** (SIZING §1 I4, from the
two `results.csv` rows `jpriors_d0p5_…` 0.6214 and `jrules_d0p25_…` 0.6460),
which implies a per-deck sd of `0.63 × √400 = 12.6`. Scaling `1/√n`:

| quantity | n | value |
|---|---:|---:|
| sem, P1 (OPP) | 1,200 games / 600 decks | **0.5144** pts/deck |
| sem, ALL control | 800 / 400 | **0.6300** |
| sem, P2 at the frozen ρ=0 | 1,200/arm | **0.7275** |
| 1σ elo, gated arms | 1,200 | **10.03** |
| 1σ elo, ALL control | 800 | **12.285** |

Turned into bars:

| bar | value | note |
|---|---:|---|
| P1, nominal 2σ | **±1.029** pts/deck | reported |
| P1, Holm step 1 (2.2414σ) | **±1.153** pts/deck | the operative bar if P1 is the larger \|z\| |
| P1, Holm step 2 (1.96σ) | **±1.008** pts/deck | the operative bar if P2 is the larger \|z\| |
| P2, nominal 2σ | **±1.455** pts/deck | reported |
| ALL control bound, 2σ | **±1.26** pts/deck | ⛔ a bound, not a bar — no branch reads it |
| P1, 2σ in elo | **±20.06** elo | companion only |

⚠️⚠️ **THE HOUSE THUMB-RULE IS ~1.4× OPTIMISTIC AGAINST THIS INSTRUMENT, and it
is said here rather than discovered in a readout.** CLAUDE.md's results
discipline gives *"n=400 → 1σ ≈ ±17 elo unpaired; deck-pairing ~halves variance
→ n=400 paired ≈ ±12 elo"*, which extrapolates to ≈ ±8.7 elo at n=800. The
**realized** paired 1σ at n=800 in this exact instrument class is **12.285** —
the realized pairing gain is materially weaker than the thumb-rule's assumed
factor of 2 on the variance. ⛔ **Every bar above is stated on the REALIZED
figures.** The thumb-rule is recorded as context and is not used.

⛔⛔ **AND EVERY BAR ABOVE IS POWER ARITHMETIC ONLY.** No branch test uses a
modelled se as its denominator: **each leg is read on its own REALIZED se**,
which prices the true deck dispersion and the true cross-arm ρ automatically. The
modelled/realized ratio is reported and **FLAGGED outside [0.70, 1.43]** —
flagged, never a branch input.

### 4.1 What this cell can and cannot resolve — the uncomfortable line

| hypothesised true effect | P1 | P2 |
|---|---:|---:|
| **+2.0** on `opp` (`CL-083`'s own falsifier bar) | z **3.89** ✅ | — |
| **+1.0 / −1.0** (opp/own), D = **+2.0** — ⭐ *DESIGN §4's own decomposition arithmetic* | z **1.94** ⚠️ | z **2.75** ✅ |
| +0.5 / −0.5, D = +1.0 | z 0.97 ❌ | z 1.37 ❌ |

⭐ **Read this before the result, not after it: at the size the design's own
arithmetic predicts, the PRIMARY is marginal and P2 is the leg with the power.**
That is why P2 exists and why `OWN` is mandatory. Two-sided power against Holm
step 1 at those effects: **P1 ≈ 0.38 at +1.0**, **P2 ≈ 0.69 at +2.0**. A
`S1-BOUNDED-NULL` from this cell is therefore a **real bound on the lever**, and
it is **not** evidence that the effect is zero.

---

## 5. THE READ RULE

> **A dual primary, HOLM step-down, two-sided, family α = 0.05 over {P1, P2}**
> (DESIGN §6.4, "the `c1_pricing_prep` precedent"). The **larger** \|z\| is
> tested at `z ≥ 2.2414` (α/2); only if it clears is the smaller tested at
> `z ≥ 1.9600` (α). A leg that does not clear fires no branch.

DESIGN §6.4's branch table writes the shorthand *"≥ +2σ"*; **2.0 sits inside the
bracket [1.96, 2.2414]**, so the Holm ladder — which DESIGN itself names — is the
operative rule and the shorthand is honoured by it. The **nominal 2σ verdict is
reported per leg** so a marginal case is visible rather than arbitrated.
*Constants derived at freeze, pre-outcome.*

⛔ **The family is exactly two.** G2's signature, the ALL control, the elo, the
saturation and dispersion rails and every `N4` rider are **outside** it by
construction — which is what keeps the correction honest.

### 5.1 Branches

| branch | condition | consequence |
|---|---|---|
| `S1-VOID-INSTRUMENT` | **any** gate in §6 fails | ⛔ the read is VOID. Fix, re-run, read again. **A void is not a null** and may never be quoted as one (IS-A1). Voided artefacts stay on disk UNMODIFIED; the amended re-read is a new document. |
| `S1-FIRES` | P1 clears **positive** **and** the G2 signature bar is met | licences a **confirm at n ≥ 1,600** on a FRESH band + the G4 guards (Carcasum @5000 ms, n=400 — `CL-083`'s own non-regression clause). ⛔ **No adoption on a screen.** |
| `S1-MARGIN-ONLY` | P1 clears **positive**, G2's bar **not met** *or* the census **unavailable** | *derived at freeze from DESIGN §10.4.* Licences **the number, not the mechanism story**. A confirm may be proposed only with the census in hand. |
| `S1-ASYMMETRY-ONLY` | P1 does not clear; P2 clears **positive** | the decomposition is real, the deployable half is not. Report; fund (i-b) or a top-up. ⛔ **Do not adopt** — a positive `opp − own` is compatible with `opp` itself being worthless (it only says `own` is worse). |
| `S1-ASYMMETRY-REVERSED` | P1 does not clear; P2 clears **negative** | *derived at freeze from DESIGN §4, pre-outcome — DESIGN §6.4's table has no row for it, and a branch map with a hole is worse than one with a named floor.* `own` beat `opp` on the shared decks: the decomposition runs the OTHER WAY and this is evidence **against** the mechanism argument. |
| `S1-NEGATIVE` | P1 clears **negative** | opponent-node modelling is harmful at this dose; closes with the `CL-080`/`CL-082` family. ⚠️ If `N4-COST` also fired, the loss is **confounded by budget** and must be reported as surface A's was. |
| `S1-BOUNDED-NULL` | neither leg clears | **record the bound** (±1.03 pts/deck P1, ±1.46 P2 at the modelled se; quote the **realized** one) and close. Re-opening needs a **mechanism** argument, **not more n**. |

### 5.2 Riders that are NOT branches

* **`N4-COST`** — `ms_ratio_cand_over_opp > 1.20`. ⚠️ **Field-name trap:** in
  `eval_fair_puct`'s summary the **candidate** side is
  `champ_prefix_ms_per_move` and the **opponent** side is `rung_ms_per_move`
  (`feedback_verify_numbers_before_reporting`). SIZING §3 predicts **1.078–1.085**
  for `opp`. ⛔ A rider, never a void: its job is to let an `S1-NEGATIVE` say of
  itself what surface A had to be told (realized 1.2116 ⇒ "loss confounded by
  budget"). It is also the **first-block abort option** at launch.
* **`N5-FAIL`** — any failed game or stranded claim voids and the read is re-run
  per the IS-A1 precedent. Enforced inside `G-PAIRED`.
* **Saturation** (winrate outside [0.35, 0.65]) and **dispersion** (realized/
  modelled se outside [0.70, 1.43]) are **flags**. Reported, never inputs.

---

## 6. GUARDS — every one must pass or the read is `S1-VOID-INSTRUMENT`

`ABSENT` is `FAIL` at every gate — never a skip, never a default. Each gate
prints which document and which address answered it.

**Per arm**

| gate | what it asserts |
|---|---|
| ⭐⭐ **`G-WITNESS`** | **the play-derived proof that the scope knob BOUND.** See §6.1. |
| **`G-SCOPE`** | the resolved `config.cand_jrules_prior` is `{dose 0.25, mask 31, scope <this arm's>}`, and the **opponent carries no jrules prior**. ⛔ This resolved dict is the **config-level** wiring gate: surface B moves **no leaf hash**, so a moved-hash check proves nothing here. |
| **`G-SINGLEVAR`** | the candidate differs from the opponent **only** in the scope knob: `k_dets`, `sims_per_det`, `total_sims`, `c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm` all agree. ⚠️ The opponent's knobs live one level down at `config.opponent.champ_cfg.*` and its budget one level **up** at `config.opponent.*`; `fpu_reduction` is emitted **asymmetrically** (opponent-only) and the absent side reads as its documented default `None` — a bare present-on-one-side rule would void every healthy cell (the PG-A1 shape). |
| **`G-BUDGET`** | k16 × 1376 = 22016 on **both** sides, and the product multiplies out. An arm at the superseded 11008 grades against a **stale opponent**, which is worse than a wrong knob because every other gate passes it. |
| **`G-ARB-OFF`** | the tie arbiter is OFF on both sides (`config.cand_tiearb` and the top-level copy; `null` is the positive OFF statement). |
| **`G-LEAF`** | ⭐ **INVERTED** — `cand_leaf_hash` and `opp_leaf_hash` **EQUAL** `a36d2e15a3b3d71d`. A **moved** hash means a leaf change was smuggled into a prior cell. |
| **`G-RULES`** | `rules_profile.name == fixed_v1`, `r9_env_ok`, `r9_env_observed`. ⚠️ argparse's default is `walled` (PG-D8). |
| **`G-PAIRED`** | `n_common > 0` **and** equal to the frozen deck count; every deck at **both** seatings; every seed inside the frozen range; `n_failed == 0`. ⛔ Without `--paired` there is no primary at all (PG-D9): `n_paired = 0` and the arm walks `2n` seeds outside its band, breaking the CRN too. |
| **`G-BACKEND`**, **`G-EXACT`**, **`G-TOOL`**, **`G-HOST`** | rust both sides, no mixed builds; exact-K 2 marginalized; the `carc_rs` build is identified (⚠️ `carc_rs_version` is permanently `0.1.0` and is **not** a discriminator); the arm ran on its assigned box. |
| **`G-BLIND`** | the arm carries the freeze commit's 40-hex sha as a stamp. **A read that was not blind is not a read.** |
| **`RECON`** | the summary's five statistics reproduce from the raw records. |

**Round-level**

| gate | what it asserts |
|---|---|
| **`G-REV`** | every arm ran **one** source rev and it is the pin its box recorded. ⭐ **Load-bearing for the primary**, not hygiene: P2's two arms run on **different boxes** (§8). |
| **`G-CRN`** | OPP and OWN are **deck-identical**; ALL is a **prefix subset**. Without this, `P2` silently computes over whatever intersection exists and is not the statistic the cell was funded for. |
| **`G-ARMS`** | the three arms share **one dose** and **one mask** and carry **distinct scopes** — the decomposition's single variable, asserted from the emitted manifests. |

### 6.1 ⭐⭐ `G-WITNESS` — and why it is the reason this cell has a pre-launch condition

G1's verdict recorded the gap: the rust expansion counters exist
(`carc_core::search::SearchResult::jr_expansions_{total,own_mover,boosted}`,
`search/mod.rs:493-508`, incremented at `:699-704`) but `fair::search_worlds`
**discarded them** at `fair/mod.rs:810-814` (`.map(|r| r.pooled_stats)`) — so a
played `scope='opp'` cell carried **only a config echo**. An arm whose knob never
bound is champion-vs-champion wearing a candidate's name: it moves no leaf hash,
sits inside every rail, and reads as a **clean, credible null**. The
FPU-resurrection round exists because exactly that happened to another knob.

**The emitted contract** (the R7 witness build, final 2026-08-30). `summary.json`
carries the block at **two** addresses and both are tried — a cell must not void
on a key spelling (the `cand_tiearb.fires` precedent):

```
summary["jr_expansions"]["candidate"|"opponent"]
summary["cand_jr_expansions"] / summary["opp_jr_expansions"]
    each == {"total": N, "own_mover": N, "boosted": N}
```

Per-game records carry `cand_jr_expansions` / `opp_jr_expansions` at the same
shape.

⚠️⚠️ **THE UNARMED SIDE READS ALL ZEROS, AND THAT IS THE HEALTHY SHAPE.** The
counters live **inside the `dose != 0` branch**, so the opponent — the unmodified
champion — emits `{total: 0, own_mover: 0, boosted: 0}`, **not** `{T, M, 0}` with
`T > 0`. ⛔ Asserting `opponent.total > 0` would fail **every** healthy cell: that
is PG-A1's shape (a gate written to the reader's expectation rather than the
emitter's real output) and it is excluded by construction.

**HARD checks — any failure voids the arm:**

1. both sides resolve to a mapping carrying all three integer keys;
2. **candidate `total > 0`** — the armed side's census ran;
3. `0 ≤ own_mover ≤ total` on both sides;
4. **candidate `boosted > 0`** — the knob **expressed in play**;
5. **opponent `boosted == 0`** — it is **candidate-side only**;
6. candidate `boosted ≤` this scope's own denominator (`own_mover` for `own`,
   `total − own_mover` for `opp`, `total` for `all`) — the boost never reached a
   node **outside** its scope. This is the machine-checkable half of DESIGN
   §9.2(c) (*"Own and Opp boost disjoint sets whose union is All's"*).

**ADVISORY, flags but never voids:** `coverage = boosted / denominator` below
0.5. A hard equality here would be the PG-A1 shape again — terminal and
no-legal-child expansions legitimately boost nothing. Read a low coverage as
*"the surface is thinner than expected"*, not as a defect.

⛔ **A missing key at BOTH addresses is a VOID, not a pass.** It means the R7
witness build is not on that box.

---

## 7. THE PRE-LAUNCH LADDER (what must be true before game 1)

`run_g3.sh` refuses a real arm unless **all** of these hold, per box:

1. `screen_lib_g3.sanity_check()` is empty.
2. `analyze_g3.py --selftest` exits 0 (branch grid fully reachable, the shaped
   fixture reads `S1-FIRES`, and **every named defect fires its own gate and
   voids the round**).
3. **`G-PROD`** — `governance/PRODUCTION.yaml`'s `fair_deploy` **is** k16×1376.
   The YAML is read; the restatement in `WORKERS_G3.conf` is not trusted.
4. **The scope knob binds on this box** — `HeuristicPriorConfig(scope='opp')`
   constructs and `search_config_rs` carries it.
5. ⭐ **The R7 witness wheel is installed on this box.** ⛔ **G3 MUST NOT LAUNCH
   UNTIL THE `carc_rs` WHEEL IS REBUILT AND INSTALLED ON EVERY PARTICIPATING
   BOX.** An armed candidate on a stale wheel raises `STALE carc_rs wheel`
   loudly rather than banking a config echo — fail-closed and correct, but it
   wastes the launch, and on the laptop it wastes it silently until someone
   reads the log.
   ⚠️ **The launcher's probe is deliberately weaker than the gate, and the smoke
   is the binding check.** The probe walks `dir()` over `carc_rs` and its
   top-level classes; if the R7 build surfaces the census only as a **key in a
   returned dict**, `dir()` cannot see it and a healthy box would be refused
   forever — a launcher-side PG-A1. So a failed probe **refuses a real arm**
   (fail-closed, as `G-PROD` is) but **lets `--smoke` through, loudly**: the
   smoke plays real games and `G-WITNESS` reads `jr_expansions` out of the
   **emitted `summary.json`**, which is the only authoritative answer. **If the
   smoke's `G-WITNESS` fails, the wheel is stale.**
6. `BLIND_COMMIT` is a 40-hex sha, not `PENDING`. *A commit cannot name its own
   hash, so the freeze commit is followed by a stamping commit.*
7. `BAND_CLAIMED_G3` exists — dropped by the orchestrator **only after** a fresh
   tree sweep and the `BAND_REGISTRY.csv` append, **in that order**.
8. `PINNED_SRC_REV_<role>` names this box's `HEAD`, and `src/ engine/ scripts/
   rust/ tests/` are clean — asserted **before** and **after** every arm.
9. **The smoke has passed on this box**, at production knobs, on the throwaway
   sub-range, with **every scope this box will run** exercised. The smoke is
   adjudicated **from its own emitted documents** and exits non-zero on empty
   knobs or a failed witness, so the launcher's `|| DIE` is reachable.
10. A process census **by full args** (`ps -eo args`), never `-C python`.

⛔ `--dry-run` and `--smoke` are exempt from (6) and (7) only: they spend no
blindness and no band, and play the throwaway sub-range alone.

---

## 8. DELIBERATE DEVIATIONS AND STANDING ASSUMPTIONS

1. **Arbiter OFF, both sides**, against a deployed champion that carries
   `tiearb B=64`. Three reasons (DESIGN §6.4): it is the precedent the champion's
   **own** budget promotion was measured under (`h2h_22016_20260824`); the
   arbiter overrides the search's pick at exactly the plies where it fires,
   **diluting** a search intervention; and cost. ⛔ **DEPLOY TRANSFER IS
   THEREFORE AN ASSUMPTION and must be stated in the readout, not buried**
   (DESIGN §10.5).
2. **P2's two arms run on different boxes** (OPP local, OWN laptop) — the
   balanced whole-arm split of 3,200 games at local:laptop ≈ 1.49:1. A mixed-rev
   or mixed-wheel defect would therefore land **asymmetrically on the primary
   contrast**. Disclosed rather than engineered away: games are bit-identical at
   any W, and `G-REV` + `G-TOOL` are the gates that exist for it. The co-located
   variant (all three arms `--role local`, ≈ +2 h wall) changes **no bar, no
   band, no seed** and is available to the orchestrator pre-launch.
3. **R6 — tree-carry contamination does not touch G3.** `eval_fair_puct --info
   fair` uses a **fresh `Searcher` per world per decision** (no session carry),
   so scope boosts cannot survive into an unarmed search; a carried-session guard
   additionally refuses scoped priors (defence in depth). Recorded here because
   G1's verdict named R6 as a pre-launch check.
4. **G2 (the signature census) is a rider on this cell, not a gate on it.** If
   the archive-banking build (DESIGN §6.3) is not in place, `--g2-signature`
   defaults to `unavailable`, which can **never** read as met — so `S1-FIRES` is
   unreachable and the best available branch is `S1-MARGIN-ONLY`. That is the
   intended fail-closed behaviour, not a degradation to be worked around.
5. **W is throughput-only.** Games are bit-identical at any W. The one clock any
   gate reads is the `N4` ms_ratio, a **within-cell** ratio of two sides on the
   same box, hence W-invariant and tenancy-common-mode.

---

## 9. FORBIDDEN READINGS

1. **A flip is not an improvement, and `d*` is not "the right dose."** G1
   measured **expression** (5.01%); expression is not effect. The `CL-080`
   anchor is 10.09% flip → **−53.8 elo** — a bigger flip is a bigger **risk**.
2. **No contrast with the banked surface-B `all` cell is a statistic.**
   Different band (1.30e11, retired), different budget (11008), and `CL-068`
   prices cross-band contrasts at 1.8–2.2× over-dispersion. It is **context**.
   The **in-band ALL arm** is the only differenceable control (DESIGN §10.2).
3. **`|z| < 2` is never "refuted."** *Killed / dead / does nothing* are
   forbidden readings of a bounded null (DESIGN §10.3). **Quote the bound.**
4. **A margin result with a flat G2 signature does not license the mechanism
   story, only the number** (DESIGN §10.4).
5. **Nothing here licenses a `PRODUCTION.yaml` change.** A screen aims; it does
   not verdict (DESIGN §10.6). `S1-FIRES` licences a **confirm**, not adoption.
6. **The three arms' `jr_expansions` censuses are NOT additive across arms.**
   `own` and `opp` boost disjoint sets whose union is `all`'s **within one
   tree**; three separate searches do not build the same trees, so
   `OWN.boosted + OPP.boosted ≈ ALL.boosted` is **not** a check and must not be
   reported as one.
7. **The ALL arm is a control, not a third primary.** It is outside the Holm
   family by construction; no branch reads it and no bar is stated on it.
8. **The selecting observation is never pooled with the confirming one**
   (`CL-084`). A confirm at n ≥ 1,600 runs on a **fresh** band.
9. **Do not re-read this band under a moved bar.** A later argument that a bar
   was mis-set is a **new prereg on a fresh band**, not a re-read of this one.

---

## 10. WHAT WOULD MAKE THIS RULE WRONG

* If `G-WITNESS` passes on every arm but the coverage ratio is **near 1.0 on the
  `opp` arm while P1 and P2 are both flat**, suspect the *mechanism*, not the
  instrument: the boost reached the nodes it was supposed to reach and did
  nothing. That is a real `S1-BOUNDED-NULL` and it is the most informative
  version of one.
* If `G-WITNESS` passes but coverage is **far below the advisory floor on every
  arm**, suspect the *instrument*: the surface may be reaching only a sliver of
  the expansions the design assumed, and the cell is then answering a smaller
  question than it was funded for. Report the coverage beside the bound.
* If the realized SE lands **outside [0.70, 1.43]× the model on the `opp` arm
  only**, the two gated arms are not exchangeable and P2's per-deck footing needs
  saying out loud before its z is quoted.
* If P1 and P2 have **opposite signs at similar magnitude**, the decomposition is
  not behaving additively and neither leg should be narrated as a component —
  report both and say the additivity assumption (DESIGN §4) did not hold.
