> ✅ **FROZEN 2026-08-24.** Prepared 2026-08-23 under
> [`../../docs/TRACK_D_PREP_2026-08-23.md`](../../docs/TRACK_D_PREP_2026-08-23.md) §3.4–3.5 on the owner's
> funding directive ("take the orchestrator's recommendation on the morning-packet decision"; owner funding of
> both cells recorded verbatim in §0.1). This banner's commit IS the blind commit (`BLIND_COMMIT` stamps its
> sha in a follow-up commit per the house two-commit choreography — DESIGN §0.5). No game has been played and
> no statistic of any kind exists as of this commit. **Band changed from the draft's `142000000000` to
> `145000000000`** — §5 and §0.5 record why (a same-morning collision with an already-claimed band, caught at
> freeze time rather than at launch time). §0.4 records the pre-freeze reconciliation against
> `measurement/track_d2r2_prep/run_cells.sh`, owed by §7.1.1 at draft time and executed here.

# FAIR-RULER RE-BASELINE: THE RULER OF RECORD, RE-MEASURED ON THE PRODUCTION INSTRUMENT — DESIGN (DRAFT)

Run id `track_d1_fair_rebase`. Pair: this file + [`READ_RULE.md`](READ_RULE.md). Launcher (drafted,
non-executable): [`run_cells_DRAFT.sh`](run_cells_DRAFT.sh). Band claim (drafted, NOT appended):
[`BAND_CLAIM_DRAFT.json`](BAND_CLAIM_DRAFT.json).

Roadmap item: the **named successor to D1**
([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md) line 110 — *"the one
part that genuinely owes compute: a `fixed_v1` + rust re-baseline of the full fair ladder, 5 rungs"*).

Style precedent: [`../track_d2_prep/DESIGN.md`](../track_d2_prep/DESIGN.md) /
[`READ_RULE.md`](../track_d2_prep/READ_RULE.md) and
[`../jcz_tiearb_20260817/DESIGN.md`](../jcz_tiearb_20260817/DESIGN.md) — read for shape, not copied for content.

---

## 0. AUTHORIZATION BLOCK

**FUNDED (owner, Joshua, 2026-08-23) — NOT YET AUTHORIZED TO LAUNCH.** Six questions were put to the owner and
the orchestrator on this draft's first pass; all six are now ruled. The remaining gate is mechanical (freeze,
band, blind commit, pilot), not a decision.

### 0.1 Owner rulings, recorded verbatim

> **Joshua, 2026-08-23: "1 and 2 I'm funding both. add to queue"**

Taken against the two funding asks put to him:

| ask | ruling |
|---|---|
| **Q1 — the re-priced base cell, ≈102 core-h** (not the prep doc's 84; §6 re-derives it from *this week's* realized records, where the prep doc's rung ms/move came from the July python-era laptop cells at W12) | ✅ **FUNDED at the re-priced figure.** The ~21% overrun is confirmed, not absorbed silently. |
| **Q5 — bundle the rules-attribution cell, +≈17 core-h** (same band, one rung, `walled` vs `fixed_v1`, the tightener for the ≳62-elo era screen) | ✅ **FUNDED and BUNDLED** as a sixth cell, §3.6. Owner condition, carried into `READ_RULE.md` §4.4 verbatim: **attribution is descriptive-plus-z, NEVER a branch input to the `FR-*` table.** |

⇒ **Total funded: ≈118.8 core-h** (§6.1), queued.

### 0.2 Orchestrator rulings on the remaining four

| # | question | ruling |
|---|---|---|
| **Q2** | top-rung allocation — keep k8×1376, or restore a pure-budget k4×2752? | **KEEP k8×1376 exactly as drafted.** Δ₄ is a budget × allocation increment; monotonicity is judged on Δ₁–Δ₃ only (§3.2). The k4×2752 variant stays unfunded, §6.3(a). |
| **Q3** | the arbiter-off gap — rung E is the production *search* config, not the full deploy champion | **ACCEPTED.** The 6th full-champion cell (§6.3(b), ~74 core-h) **stays unfunded and is named as such in the scope fences** (§8 item 3, `READ_RULE.md` §5). |
| **Q4** | 800/1600 have no same-allocation cross-era comparator | **ACCEPTED.** They produce **new absolutes**; the readout says so plainly and never compares them to G1's leaky k8×{100,200} readings (§2 E3, `READ_RULE.md` §1). |
| **Q6** | which box | **DECIDED AT LAUNCH BY AVAILABILITY.** The launcher is already parameterized `local` / `laptop`; the §9 pilot's fail-loud wall re-projection covers the laptop unknown (§6.2). |

### 0.3 What is still owed before game 1 — mechanical only

| # | owed | why |
|---|---|---|
| (a) | **the band claim** — 145000000000 (§5) | `governance/BAND_REGISTRY.csv` is a source of truth the orchestrator edits, not a builder |
| (b) | **freeze + blind commit + `BLIND_COMMIT`/`PINNED_SRC_REV` stamped** | the pre-registration is only a pre-registration once it is committed before game 1 |
| (c) | **the §9 pilot PASSES its full structural gate sweep** on the chosen box | D2 (2026-08-23) went `U-UNREADABLE` on four launcher defects a timing-only pilot could not see (§7.1) |
| (d) | **process census clean** on the target box | standing repo rule; this is a ~5.4–8.5 h exclusive tenant carrying a timing witness |

**Pre-launch checklist** (all must be true before any real cell fires):

- [ ] band claimed in [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) (145000000000, per §5)
- [ ] this pair (`DESIGN.md` + `READ_RULE.md`) frozen and committed to `main`
- [ ] `BLIND_COMMIT=<sha>` written into `BLIND_COMMIT` (the launcher refuses to run on the placeholder)
- [ ] `PINNED_SRC_REV=<sha>` written into `PINNED_SRC_REV`, and `git status --porcelain -- src engine scripts` is **EMPTY** (§7.1 fix 3 — the D2 mixed-rev defect)
- [ ] the §9 pilot has run and its **structural gate sweep** has PASSED on real records (R9 latched, curve125 leaf hash, rust backend, `fixed_v1`, arbiter off, wall re-projection)
- [ ] the §9 pilot's **`walled` arm** has run and confirmed `rules_profile.name == "walled"` with `r9_env_ok == true` **while R9 is OFF** (§3.6 — the attribution cell inverts the R9 expectation, and a launcher that exports R9 at file scope will fail this if it does not unset it per-cell)
- [ ] process census clean on the target box (standing repo rule)
- [ ] `RUN_LIVE.json` sentinel dropped for the whole 6-cell sequence (freeze-latch discipline)

---

## 0.4 PRE-FREEZE RECONCILIATION vs `measurement/track_d2r2_prep/run_cells.sh` — EXECUTED

§7.1.1 (below) named this OWED at draft time because `track_d2r2_prep` did not exist on disk. It exists now
(committed on the unmerged `d2r2-freeze` branch, tip `4105baed`) and this reconciliation is executed against it
at freeze time, 2026-08-24, before `BLIND_COMMIT` is stamped. `run_cells.sh`'s own header carries the
launcher-level version of this table verbatim; this is the pair-level record.

| # | mechanism | disposition | where |
|---|---|---|---|
| 1 | **leaf injection via file route** | ✅ **ADOPTED.** `--cand-leaf-json` now points at a FILE (`champion_leaf_curve125.json`, byte-identical curve to the draft's inline string), and a `preflight_leaf` function — built through the harness's own module, exactly d2r2's route — asserts both `cand_leaf_hash` and `rung.leaf_hash` before game 1, on EVERY leg (not just the pilot's post-hoc manifest read, which the draft was limited to). | `run_cells.sh` `preflight_leaf`, called at the top of `main` |
| 2 | **R9 structural assertion on every leg** | ⚠️ **ADOPTED IN SPIRIT, NOT VERBATIM.** d2r2's `assert_r9_env` is a single top-of-`main` check because ALL its cells want R9 ON. This pair's cells want BOTH directions (`fixed_v1` ON, `walled` OFF), so a single check cannot serve both cells. `assert_r9_argv` is the per-invocation, per-profile, fail-loud, both-directions-explicit replacement, called immediately before every real cell and every pilot arm — closing a gap the DRAFT actually had (its `--pilot` path never asserted R9 direction at all). | `run_cells.sh` `assert_r9_argv` |
| 3 | **per-cell rev guards** | ✅ **ALREADY STRICTER than d2r2** (before AND after every cell, vs d2r2's before-only) — kept. `CODE_PATHS` **broadened** to d2r2's set (`src engine scripts rust tests pyproject.toml setup.py` — the draft covered only `src engine scripts`, which misses a `rust/` change even though this cell runs the rust backend). d2r2's tolerant `LAUNCH_DIRTY=1` override is **NOT adopted** — this pair's own `G-REV` text (§7.1/READ_RULE §3.1) already commits to a clean tree with no override, and introducing one now would be a silent weakening, not a reconciliation. | `run_cells.sh` `CODE_PATHS`, `assert_rev_pinned` |
| 4 | **dual-address `--stamp-key`** | ✅ **ALREADY DONE at draft time** (auto-detect + `BLIND_PROOF.json` mode recording) — **CONFIRMED live**: `--stamp-key` now exists in `scripts/classical_search/eval_fair_puct.py` (added for d2r2, verified by grep at freeze time), so `detect_stamp_key` resolves `blind_stamp_mode=manifest` on a real run, no launcher edit needed. | `run_cells.sh` `detect_stamp_key` (unchanged) |
| 5 | **REPO self-resolution** | ✅ **ADOPTED — load-bearing for THIS pair's own LAUNCH step.** The draft hardcoded `REPO=/home/doctor/projects/carcassone`; d2r2 resolves it from the script's own location (`git -C "$DIR" rev-parse --show-toplevel`). The launch step runs this launcher from an **isolated worktree on the laptop** — a hardcoded path would silently point the launch worktree's launcher at the MAIN tree's git history, band registry and `BLIND_COMMIT`, exactly the class of defect this whole reconciliation exists to close. `CARC_PY` override adopted alongside (dry-run from a build worktree with no `.venv`). | `run_cells.sh` top-of-file `REPO=`/`PY=` resolution |
| 6 | **PYTHONPATH / venv identity check** | ⭐ **NEW, not present in either prior launcher.** Added per the standing worktree-isolation rule (`CLAUDE.md` / memory `feedback-worktree-isolation-live-tree`): `PYTHONPATH` pinned to THIS repo's own `src`/`engine` (correct per-worktree once (5) resolves `REPO`), and `preflight_leaf`'s child process prints `carcassonne_ai.__file__`, asserting it resolves inside `REPO` — so a launch log states which tree's package actually loaded instead of leaving it inferred. | `run_cells.sh` `export PYTHONPATH=`, `preflight_leaf` |

**Also hardened at freeze time, owed by the executor's brief rather than by either prior launcher:**

7. **Per-cell DONE/FAILED sentinels.** The draft touched `DONE_cell_$NAME` **unconditionally** after logging a
   nonzero rc — a failed cell was indistinguishable from a completed one to anything reading sentinels alone.
   Fixed: `DONE_cell_$NAME` only on `rc==0`; a nonzero rc touches `FAILED_cell_$NAME` (cleared on a later clean
   rc, so a resumed-and-now-clean cell doesn't carry a stale marker).
8. **VOID-RATE ABORT — a launcher safety, NOT a statistical gate.** If any cell's realized void rate
   (`n_failed / games`) reaches ≥10%, the launcher **aborts the whole sequence** immediately. This is
   deliberately distinct from `READ_RULE.md`'s `G-N` gate (a <2% **adjudication** threshold, applied after the
   fact to a frozen record) — the 10% figure here is a **pre-adjudication** circuit breaker to stop burning
   core-hours against a plainly broken instrument, and is recorded here so no future reader mistakes it for a
   bar on any statistic. It never appears in `READ_RULE.md` and never voids or licenses anything there.
9. **chmod-as-launch-act.** `run_cells.sh` is committed at mode 644 (non-executable), matching the draft's own
   convention. `chmod +x` is a LAUNCH act performed by the executor immediately before a real launch, never
   baked into the freeze commit.

### 0.5 Band substitution — `142000000000` → `145000000000`, and why (caught at freeze, not at launch)

The draft priced band `142000000000` as "the next free step-aligned start" at draft time (2026-08-23 morning,
§5 as originally written). At freeze time (2026-08-24) `governance/BAND_REGISTRY.csv` on `tiearb2-stage2` shows
**both `142000000000` and `143000000000` already claimed and retired** by an unrelated concurrent track
(`CARCASUM RATED MATCH rung 1` / `RUNG-2 BUDGET LADDER`, claimed 2026-08-23) — the exact class of same-morning
race `measurement/track_d2r2_prep/` itself hit and resolved by re-pinning (`143000000000` → `144000000000`,
commit `70501f74`). That re-pin lives on the **unmerged** `d2r2-freeze` branch, so `144000000000` does not yet
appear in `tiearb2-stage2`'s own registry either — but claiming it here would create a certain future collision
the moment `d2r2-freeze` merges. **This pair therefore claims `145000000000`** — one step past every band
visible on `tiearb2-stage2` AND every band any sibling in-flight branch is known to have claimed, verified
immediately before the band-claim commit (not merely at draft time). The reserved n-extension row moves
`143000000000` → `146000000000` for the same reason. Every reference to the old numbers throughout this pair
(§1–§9, `READ_RULE.md`, `run_cells.sh`, `BAND_CLAIM.json`) is updated to match; nothing about the DESIGN
changes except the seed values.

---

## 1. THE QUESTION

**The fair sub-ladder (D0 / CL-046) is the ruler of record.** Every human / superhuman / champion / learned-value
claim in this program is graded on it. Its provenance has now drifted **twice**:

| generation | when | candidate side | rung side | backend | rules | band | n | reading @2752 |
|---|---|---|---|---|---|---|---|---|
| **G1 — CL-046 (D0)** | 2026-07-09 | fair PIMC, k8×sims/det, **pre-CL-056 leaky determinization** | clairvoyant `HeuristicMCTS(h800, c=3.0)` | python | pre-`fixed_v1` (walled) | 15e9 | 200 decks | **+81.4** |
| **G2 — F5 rebase** | 2026-07-19/20 | fair PIMC, k4/k8, **post-CL-056 fixed**, curve125 leaf `a36d2e15` | same | **python** | **pre-`fixed_v1`** (`rules_profile` key absent entirely) | 24e9 | 200 decks | **+135.0** |
| **G3 — THIS CELL** | — | same agent family, same leaf, same rung | same | **rust** | **`fixed_v1` + R9** | 142e9 | **400 decks** | ? |

G1→G2 moved the 2752 rung by **+53.6 elo** — the leaky-determinization fix alone. `DECISIONS.md` 2026-07-14
states the rule that produced G2: *"any FUTURE fair eval must re-establish its own fair baseline with the fixed
code."* G2 was never folded into CL-046's row (that annotation landed 2026-08-23, prep doc §3.4).

**G2 is now stale on a second, independent axis.** Every `fair_ruler_*` manifest carries no `backend` block and
no `rules_profile` key of any kind — verified directly on all five
(`/mnt/c/carc-shared/classical_search/fair_ruler_*/manifest.json`) — which is the signature of **python backend,
pre-`fixed_v1` rules**. Production has been **rust since 2026-08-01** and **`fixed_v1` since 2026-08-03**
(`governance/PRODUCTION.yaml`). ⇒ **the ruler of record grades a rules profile and an engine the champion no
longer plays.**

**This cell measures G3: the five-rung fair ladder, re-measured with the production execution.**

⚠️ **One half of the era shift is provenance, not strength.** The rust backend is gated *behaviour-identical*
to python (rustport G4/G6; the harness manifest says so in its own words: *"It is an ENGINE, not a player — no
strength claim moves with it"*). So the strength-relevant era axis is **`fixed_v1` + R9 rules**, not the
backend. The backend is nonetheless load-bearing for **provenance** (a ruler whose artifacts cannot state their
engine is not auditable) and for **cost** (§6). §4.4 states what this cell can and cannot decompose.

### 1.1 The second gap the prep doc named: the ladder has a hole at the bottom

G2 re-based only **2752 / 5504 / 11008**. The **800** and **1600** rungs — the bottom of the ladder, the part
that anchors "how much is a doubling worth" — have **never** been measured post-CL-056, in any backend, under
any rules profile. Their only readings are G1's leaky `+27.9` and `+61.4`. This cell fills that hole.

---

## 2. THE ESTIMANDS — named before any number exists

Four, in priority order. Every one is a **deck-paired margin in points/game, candidate-minus-rung**, the
`eval_fair_puct._paired_z` convention. Elo is a derived display quantity throughout (§4.5).

**E1 — THE RE-BASED RUNG VALUES (the deliverable).**
`R_i` = the deck-paired mean margin of rung-budget *i* against the fixed clairvoyant `HeuristicMCTS(h800,
c=3.0)`, for *i* ∈ {800, 1600, 2752, 5504, 11008}, on band 142e9, `fixed_v1`+R9, rust. These five numbers ARE
the re-anchored ruler.

**E2 — THE WITHIN-RUN RUNG SPACINGS (the ROBUST class).**
`Δ₁ = R_1600 − R_800`, `Δ₂ = R_2752 − R_1600`, `Δ₃ = R_5504 − R_2752`, `Δ₄ = R_11008 − R_5504`, and
`SPAN = R_11008 − R_800`. All computed **deck-paired on the SAME decks** (CRN by design, §5).

⭐ **Per CL-068 these are the only statistics in this cell that carry no cross-band humility tax.** The standing
rule (`CLAUDE.md`): *"Within-band deck-paired contrasts are unaffected — that is the robust class."* E2 is that
class. **The readout leads with E2.**

**E3 — THE CROSS-ERA DELTA PER RUNG (the coarse screen).**
`D_i = R_i − R_i^{G2}` for the three rungs that have a **same-allocation** G2 counterpart:

| rung | G2 cell | G2 reading | same allocation? |
|---|---|---|---|
| 2752 = k4×688 | `fair_ruler_rebase_2752` | +135.0 elo / **+8.6425 pts** (z 9.51) | ✅ k4×688 |
| 5504 = k4×1376 | `fair_ruler_rebase_5504` | +147.2 elo / **+10.7825 pts** (z 11.30) | ✅ k4×1376 |
| 11008 = k8×1376 | `fair_ruler_k8x1376_11008` | +123.0 elo / **+9.77 pts** (z 9.87) | ✅ k8×1376 |
| 1600 = k4×400 | — | *none* (G1 only, leaky, and k8×200) | ❌ |
| 800 = k4×200 | — | *none* (G1 only, leaky, and k8×100) | ❌ |

⚠️ **STATED BEFORE GAME 1: E3 exists at only 3 of the 5 rungs.** The 800 and 1600 rungs have **no
same-allocation post-fix comparator anywhere in the repo** — G1's `fair_ladder_s800/s1600` ran **k8**×{100,200}
*and* on the leaky determinization, so a delta against them would confound three changes at once. For those two
rungs this cell produces a **new absolute, not a delta.** That is the §1.1 hole being filled, and it is a
feature of the manifest, not a defect discovered later.

⚠️⚠️⚠️ **E3 IS CROSS-BAND AND CROSS-ERA, SO IT TAKES THE CL-068 HUMILITY TAX.** Band 24e9 → 142e9, python →
rust, walled → `fixed_v1`+R9, n=200 → n=400 decks, code rev `7d129c41e` → HEAD. **`se(D_i)` is inflated ×2**
before any z is formed (§4.4). The consequence, in one line, recorded now: **at n=400/rung the per-rung era
delta resolves only shifts ≳ 60 elo.** A null `D_i` is a bound, never "the era does not matter."

**E4 — THE RULES-ONLY ATTRIBUTION (owner-funded 2026-08-23, §0.1; the E3 tightener).**

```
A = R_2752(fixed_v1 + R9)  −  R_2752(walled, R9 OFF)
```

deck-paired over the **same 400 decks, same band, same code rev, same backend, same candidate leaf, same
frozen h800 rung** — cell C2752 minus cell W2752 (§3.6). **Everything except the rules profile is held
identical**, so:

⭐ **A carries NO CL-068 tax.** It is a within-band, same-code, deck-paired contrast — the robust class. Its
`se` is the E2 form, **0.885 pts ⇒ 2σ MDE ≈ 24 elo.** That is the point of funding it: it converts one axis of
E3's un-decomposable ≳62-elo bundle into a **24-elo reading**, and leaves the residual `D_2752 − A`
attributable to band ⊕ n ⊕ code drift.

⚠️ **What A is NOT.** (i) It is the rules profile's effect on the **candidate-minus-rung margin at this rung** —
the clairvoyant h800 rung's own play also changes under `fixed_v1`, so A is not "the rules made the champion
stronger by A". (ii) It is measured at **one rung (2752)** and does not license extrapolation to the other
four. (iii) ⛔ **Per the owner's condition it is DESCRIPTIVE-PLUS-Z and is NEVER a branch input to the `FR-*`
ladder table** (`READ_RULE.md` §4.4) — the ladder branch is computed identically whether or not this cell ran,
or whether it ran clean.

---

## 3. THE CELLS — FIVE LADDER RUNGS + ONE ATTRIBUTION CELL

All six run [`../../scripts/classical_search/eval_fair_puct.py`](../../scripts/classical_search/eval_fair_puct.py)
on the same band and the same 400 decks.

**The five LADDER cells (A–E)** differ in **exactly two experimental arguments — `--k-dets` and `--sims`**
(which jointly name one thing, the candidate's total per-move budget) plus `--out-subdir` / `--claim-host`,
which are BOOKKEEPING (cells cannot share one output directory or one `--shared-claim` tag without corrupting
each other).

| | **A800** | **B1600** | **C2752** | **D5504** | **E11008** |
|---|---|---|---|---|---|
| cell id | `fr_a800` | `fr_b1600` | `fr_c2752` | `fr_d5504` | `fr_e11008` |
| `--k-dets` | 4 | 4 | 4 | 4 | **8** |
| `--sims` | 200 | 400 | 688 | 1376 | 1376 |
| total sims | 800 | 1600 | 2752 | 5504 | **11008** |
| rules | `fixed_v1` + R9 | ← | ← | ← | ← |
| lineage | — | — | **pre-07-29 deploy / current MOBILE profile** (CL-071) | — | **current DESKTOP deploy budget+allocation** (CL-071) |
| n | 400 decks × 2 seatings = 800 games | ← | ← | ← | ← |

**The ATTRIBUTION cell (W)** — §3.6, owner-funded §0.1 — is cell C2752 **with one argument changed**:

| | **W2752** |
|---|---|
| cell id | `fr_w2752` |
| `--k-dets` / `--sims` | 4 / 688 (= C2752, identical) |
| rules | **`walled`, R9 OFF** |
| n | 400 decks × 2 seatings = 800 games, the SAME decks |

### 3.1 Frozen and identical in all five LADDER cells (and in W2752 except `--rules-profile`)

```
--info fair --opponent h800 --backend rust --exact-k 2
--c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits
--rung-sims 800
--cand-leaf-json '{"v29_meeple_curve": [-10,-5,-1.25,0,2.5,3.75,5,6.25]}'
--rules-profile fixed_v1          (with CARCASSONNE_FIX_R9=1 EXPORTED — §7.1)
--n 800 --paired --seed-start 145000000000
```

Tie-arbiter **OFF** (no `--cand-tiearb-*` flag anywhere — §3.4).

- **The rung is the fixed yardstick and never moves:** `HeuristicMCTS(h800)`, `c = 3.0` (the module default;
  prep doc §2.2 / D2 DESIGN §2 established there was never a `c=1.5` rung), leaf `42af12fce22e1a0f` (v2.9
  Bmild_cap8 `DEFAULT_CONFIG`), CL-022 provenance. Identical in **all six** cells — that identity is what makes
  the five `R_i` comparable to each other and `A` a clean rules contrast, and it is gated (`G-RUNG` for the
  ladder, `GW-PAIR` for W2752).
- **The candidate leaf is the champion's:** curve125, `cand_leaf_hash == a36d2e15a3b3d71d`
  (`champion_factory.LEAF_HASH_HARNESS`), passed exactly as the five G2 cells passed it. The rung keeps env
  `DEFAULT_CONFIG` — the harness enforces this ("the h800 rung ALWAYS keeps env DEFAULT_CONFIG; the CL-022
  ruler must not move").
- **`--n 800` counts GAMES.** `--paired` gives 2 seatings per deck ⇒ 800 games = **400 decks**. Do not "fix"
  this to 400 — that would halve the deck set §4/§6 costed and gated.

### 3.2 ⚠️ THE ALLOCATION BREAK AT THE TOP RUNG — named, with its consequence

Rungs A–D hold `k_dets = 4` fixed and vary only depth: **Δ₁, Δ₂, Δ₃ are pure budget contrasts.** Rung E moves
to `k8×1376`, so **Δ₄ = R_11008 − R_5504 is a BUDGET × ALLOCATION increment, not a pure budget one.**

This is deliberate, for one reason: **a ruler re-anchor must place the agent we actually run.** `k8×1376` is
the desktop deploy allocation of record (CL-071 / `PRODUCTION.yaml` `budget_folded_in: 2026-07-29`); `k4×2752`
is a configuration nobody deploys. The pure-budget curve at 11008 is a *different* question, already owned by
CL-060/CL-068.

**Consequences, all pre-registered:**

1. `READ_RULE.md` §4's monotonicity condition is evaluated on **Δ₁…Δ₃ only** (the pure-budget spacings). Δ₄ is
   reported with its z on every branch and enters `SPAN`, but never fires the bent branch on its own.
2. `SPAN` is therefore correctly read as **"the ruler's total usable dynamic range, from its bottom rung to the
   production agent"** — not as "what 13.8× more sims buys."
3. The choice is what makes E3 available at 11008 (G2's `fair_ruler_k8x1376_11008`, +123.0, is same-allocation).
   Had the top rung been `k4×2752`, the comparator would have been `fair_ruler_rebase_11008` (+114.3) instead —
   **also** same-allocation, so E3 is available either way; the choice is about *which agent the ladder tops out
   at*, not about comparability. Priced alternative in §6.1(a).

### 3.3 Why these five budgets

They are the exact five in the prep doc's §3.5 manifest, and every one is a config the program has already run
at least once (G1, G2, or both) — **not a config assembled for this cell.** 800/1600 close the §1.1 hole; 2752
is the mobile profile and the historical deploy budget; 5504 is G2's measured peak; 11008 is the desktop
champion.

### 3.4 ⚠️ SCOPE DECISION: the tie-arbiter stays OFF, and the top rung is therefore NOT the full deploy champion

The desktop deploy champion has carried a **root tie-arbiter B=64 / J=4 since 2026-08-20**
(`PRODUCTION.yaml` `tiearb_folded_in`). This cell runs **arbiter-off on every rung**, for three reasons:

1. **The ladder must be one axis.** The arbiter is a post-search root behaviour on already-resolved ties; folding
   it in would make the ladder a budget × arbiter surface.
2. **Comparability with G2.** No `fair_ruler_*` cell had an arbiter — E3 would confound the era delta with the
   arbiter's own effect.
3. **`PRODUCTION.yaml` already says rulers stay unmodified:** *"Rulers/anchors are NOT re-anchored by this fold
   (fixed eval sides stay unmodified-champion)."*

⛔ **The consequence, stated so no readout can narrate past it: rung E prices the production *search* configuration,
arbiter-off. It does NOT locate the full desktop deploy champion on the ruler.** That would be a sixth cell,
priced and unfunded in §6.1(b) at ~74 core-h (the arbiter's own measured ρ_wall(64) = 2.4897).

### 3.5 ⚠️ NOT POOLABLE WITH G1 OR G2 — and not with D2 either

- **vs G1/G2:** different band, different rules profile, different backend, different n. Only E3's explicitly
  ×2-inflated delta crosses that line, and only at 3 rungs.
- **vs D2 (`track_d2_prep`, band 141e9, 2026-08-23):** D2's probe ran the **wrong leaf** (`42af12fce22e1a0f`,
  the rung's own default, not curve125) **without the R9 latch** — that is why it fired `U-UNREADABLE`. D2's
  numbers are not a comparator for anything here. Its *timing* records are, and are used in §6 — timing is not
  a gated statistic and no branch of D2's pair adjudicated it.

---

### 3.6 THE ATTRIBUTION CELL W2752 — owner-funded, and the one place R9 is deliberately OFF

**What it is:** cell C2752, re-run on the same 400 decks with `--rules-profile walled` and
**`CARCASSONNE_FIX_R9` UNSET**. Everything else — band, decks, seatings, `k4×688`, rust backend, curve125
candidate leaf `a36d2e15a3b3d71d`, the frozen `HeuristicMCTS(h800, c=3.0)` rung and its leaf `42af12fce22e1a0f`,
`exact-k 2`, arbiter off, code rev — is byte-identical to C2752. Its statistic is **E4's `A`** (§2).

⚠️⚠️ **THE R9 INVERSION IS A LAUNCHER TRAP, NAMED HERE BEFORE GAME 1.** The five ladder cells need
`CARCASSONNE_FIX_R9=1` exported *before process start* (R9 is import-latched — `base_deck` derives farm data at
import and the Rust registry latches a `OnceLock`). **W2752 needs it OFF.** `walled` carries
`r9_env_expected = False`, so `r9_env_ok == true` on the W cell means **`r9_env_observed == false`** — the gate
field is the same, the expectation is inverted (this is the standing `reference_evloss_grader` trap: *"walled
expects R9 OFF"*). A launcher that exports R9 at file scope and forgets to unset it for this one cell produces a
`walled` artifact with `r9_env_ok == false`, which voids the attribution read — and does so *silently* as far as
the ladder is concerned. The launcher therefore runs W2752 under `env -u CARCASSONNE_FIX_R9`, and the §9 pilot
runs a **`walled` arm** that asserts the inversion on a real record before the band is spent.

**What A bundles:** `fixed_v1` is the **Phase-B four-lever bundle** (centered18 grid + retail start tile + fixed
cloister scan + redraw-on-unplaceable) **⊕ the R9 farm fix**. A is the *joint* effect of all five LEVERS, exactly the
production rules change of 2026-08-03. It does **not** decompose them — `rules_profile.py` states the bundle is
deliberately non-orthogonal (A3 and A4 interact; retail absorbs ~5.6× of A3's blast radius), so a single-flag
attribution ladder is a different, larger design and is not proposed here.

⛔ **Gate isolation, stated before game 1:** the attribution cell's gates are in a **separate group**
(`READ_RULE.md` §3B) and **a failure there voids ONLY the attribution read, never the ladder.** Conversely a
ladder `U-UNREADABLE` voids the attribution read too (it depends on C2752). This asymmetry is deliberate and is
what keeps a bundled-on extra cell from putting the funded deliverable at risk.

## 4. POWER — arithmetic BEFORE any number

### 4.1 The dispersion we are entitled to assume

Realized `paired_mean_margin / paired_z ⇒ se(M)` at `n_paired = 200` decks, from four independent cells across
two eras and two boxes:

```
fair_ruler_rebase_2752     8.6425 / 9.5101  = 0.909 pts   (G2, python, laptop W12)
fair_ruler_rebase_5504    10.7825 / 11.3029 = 0.954 pts   (G2)
fair_ruler_k8x1376_11008   7.9350 / 8.4547  = 0.939 pts   (G2)
d2_rung800                 6.9500 / 7.6170  = 0.912 pts   (2026-08-23, rust, fixed_v1, local W22)
```

Remarkably stable across era and box. Take **se(M) ≈ 0.93 pts at n_paired = 200** ⇒ at this cell's
**n_paired = 400**:

```
se(R_i) = 0.93 / sqrt(2) = 0.66 pts      [COMMITTED]
```

### 4.2 CRN across cells, and se of the spacings

All six cells share one deck set and both seatings (§5). Per CL-068 the measured cross-cell CRN benefit on a
comparable contrast was only **~9.9%** of contrast variance (the jcz DESIGN §4.1 precedent, carried by D2).
Assume **ρ = 0.10 — do not bank more:**

```
se(Δ) = se(SPAN) = se(A) = 0.66 × sqrt(2 × (1 − 0.10)) = 0.885 pts      [COMMITTED]
2σ MDE on any spacing, on SPAN, or on A                = 1.77 pts
```

⭐ **`A` (E4, the attribution statistic) takes this same form and NOT the §4.4 form** — it is a within-band,
same-code, same-band-deck-paired contrast between two cells of this run, exactly like a spacing. That is the
entire reason it is worth 17 core-h.

### 4.3 What n=400 decks/rung buys — E1 and E2

| statistic | committed se | 2σ MDE (pts) | 2σ MDE (elo @ 13.7 elo/pt, §4.5) |
|---|---|---|---|
| `R_i` (each rung's absolute) | 0.66 | ±1.32 (95% half-width) | **±18 elo** |
| `Δ_i` (each spacing) | 0.885 | 1.77 | **≈24 elo** |
| `SPAN` | 0.885 | 1.77 | **≈24 elo** |

**Reachability, checked against the priors, before game 1:**

- `SPAN`: G1's leaky ladder ran +27.9 → +149.3 over 800→5504 (~8 pts). Even heavily attenuated, `SPAN` should
  land at z ≈ 5–9. **The "flat" branch is a low-probability branch by design** — it is in the table because a
  ruler that fails to resolve its own dynamic range is the single most consequential thing this cell could
  find, not because it is expected.
- `Δ_i`: G2's realized deck-matched increments were **+2.14 pts (z 1.66)** for 2752→5504 and **−2.85 pts
  (z −2.23)** for the k4 5504→11008 sag. At this cell's `se(Δ) = 0.885`, a **+2.14** reads z ≈ 2.4 and a
  **−2.85** reads z ≈ −3.2. **Both the "spacing resolves" and the "bent" branches are genuinely reachable at
  the committed dispersion.**

### 4.4 What n=400 decks/rung buys — E3, the cross-era delta

```
se_naive(D_i) = sqrt(0.66² + 0.93²)          = 1.14 pts
se_eff(D_i)   = 2 × se_naive   [CL-068 tax]  = 2.28 pts      [COMMITTED]
2σ MDE(D_i)                                  = 4.56 pts  ≈  62 elo  (@13.7)  /  71 elo (@15.6)
```

⛔ **STATE IT BLUNTLY, BEFORE GAME 1: the per-rung era delta is a ≳60-elo screen and nothing better.** For
scale, the G1→G2 shift it is the sequel to was **+53.6 elo at 2752** — i.e. **this cell could not have resolved
the last era shift either.** A null `D_i` is a bound of ≤~62 elo on the (rules ⊕ band ⊕ n ⊕ code-drift) bundle,
not evidence that `fixed_v1` is strength-neutral.

⚠️ **E3 is NOT DECOMPOSABLE by this design *alone*.** `D_i` bundles: `fixed_v1`+R9 rules, the 24e9→142e9 band
draw (CL-068 says this alone is worth 1.8–2.2× the nominal sigma), the n=200→400 change, and ~6 weeks of code
drift.

### 4.4.1 What the funded attribution cell buys — E4

The owner funded (§0.1) exactly the cell §4.4 named as missing: **same band, same code, `walled` vs `fixed_v1`,
one rung.**

```
se(A)        = 0.885 pts     [the §4.2 within-band form — NO CL-068 tax]
2σ MDE(A)    = 1.77 pts  ≈  24 elo
```

| axis of the era bundle | resolved to | by |
|---|---|---|
| **rules** (`fixed_v1` bundle ⊕ R9) | **±24 elo**, at the 2752 rung | E4's `A` — within-band, same-code, deck-paired |
| band ⊕ n ⊕ code drift (residual) | `D_2752 − A`, at the ±62-elo E3 resolution | arithmetic, reported as a residual with its own se |

⇒ **the un-decomposable ≳62-elo bundle becomes a 24-elo reading on its one strength-relevant axis, plus a
named residual.** The residual is NOT separately resolvable and the readout must not present it as an estimate
of the band effect — it is a leftover, reported with the ×2-inflated se it inherits.

⛔ Still true after the bundle: **`A` is measured at ONE rung and does not extrapolate to the other four**, and
it is the rules effect **on the candidate-minus-rung margin**, not on the candidate's strength (§3.6).

### 4.5 The elo scale

Elo is a **display** quantity, converted from points via the realized per-run scale. Pre-registered anchors:
G2's `fair_ruler_rebase_2752` realized **+135.0 elo ↔ +8.6425 pts = 15.6 elo/pt**; D2's `d2_rung800` realized
**+81.4 elo ↔ +6.95 pts = 11.7 elo/pt**. **The committed anchor for all pre-registered MDEs above is
13.7 elo/pt** (the midpoint); the readout **recomputes the scale from this run's own records and prints both.**
No bar in `READ_RULE.md` is ever set in elo.

---

## 5. THE BAND

**Band `145000000000`** — the next free step-aligned start in
[`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv), **re-derived at freeze time
(§0.5)**, not the draft's `142000000000`. Registry high-water on `tiearb2-stage2` at freeze time is
**143000000000** (`CARCASUM RUNG-2 BUDGET LADDER`, claimed 2026-08-23) — `142000000000` and `143000000000` were
BOTH already claimed and retired by that unrelated concurrent track by the time this pair reached freeze, and
`144000000000` is spoken for on the unmerged `d2r2-freeze` branch (commit `70501f74`), so `145000000000` is the
next value clear of every band visible on `tiearb2-stage2` and every in-flight sibling branch's own claim.

**Seeds `145000000000 .. 145000000399` — 400 decks, used by ALL SIX cells** (the five ladder rungs **and** the
`walled` attribution cell). CRN across all six is the design: it is what makes E2 **and E4** (§2) the robust
class and what allows `n_common == 400` to gate.

**Claimed at freeze (§0.5).** The row is finalized in [`BAND_CLAIM.json`](BAND_CLAIM.json) and appended to
`governance/BAND_REGISTRY.csv` in the same freeze sequence that stamps `BLIND_COMMIT` — the house two-commit
choreography (`BAND_CLAIM_DRAFT.json` is retained as the historical plan, superseded by `BAND_CLAIM.json`).

**Pilot band (disjoint, never claimed, never pooled):** `145999999000 .. 145999999007` — 8 decks, run **twice**:
once in cell A800's `fixed_v1` config and once in the `walled` config (§9). Discarded on completion.

**Reserved (DRAFTED, NOT LICENSED):** `146000000000` — a top-up range for the §6.3(c) n-extension, so a future
"just add n" ask does not have to re-plan the band. Reserving costs nothing and licenses nothing; the row is in
`BAND_CLAIM_DRAFT.json` marked `RESERVED-NOT-LICENSED`, exactly the 136e9/138e9 precedent.

Per CL-068, **band identity is load-bearing**: never pool this band's numbers with any other band, and this band
**retires from confirmatory use** once it has influenced a decision.

---

## 6. COST — re-derived from THIS WEEK's realized records

⚠️ **The prep doc's ≈84 core-h is an underestimate.** It priced the h800 rung at **387 ms/move**, taken from the
G2 cells (laptop, W=12, python era). The same rung on the **production instrument under production farm
contention** realized **624.3 ms/move** (`d2_rung800`, local 5900XT, W=22, rust candidate, `fixed_v1`,
2026-08-23). Cost is re-derived below from that record set.

**Facts (all measured 2026-08-23, `/mnt/c/carc-shared/track_d2_prep/*/summary.json`):**

```
rung h800  (python, frozen ruler)          624.3 ms/move        [d2_rung800]
rung h1600 (control, ≈2× — sanity)        1255.6 ms/move        [d2_rung1600]
probe, rust, total 4128 sims               608.6 ms/move   ⇒   0.1474 ms per total-sim
exact-K=2 marginalized solver, rust          1.11 s/game
moves/game                                 ≈70 probe-side / ≈71 rung-side
```

**Model:** `s/game = 0.070 × probe_ms_per_move + 0.071 × 624.3 + 1.11`, with
`probe_ms_per_move ≈ 0.1474 × total_sims`.

**Model validation against realized wall (not a fit — a check):**

| cell | model s/game | realized s/game | error |
|---|---|---|---|
| `d2_rung800` (400 games, 1623 s wall @ W22) | 88.0 | 89.3 | −1.5% |
| `d2_rung1600` (400 games, 2452 s wall @ W22) | 132.8 | 134.9 | −1.5% |

A uniform **+2%** calibration is applied below.

### 6.1 The funded roll-up — five ladder cells + the attribution cell

| cell | rules | total sims | probe s/game | + rung 44.3 s | + solver 1.1 s | **s/game** | × 800 games | **core-h** |
|---|---|---|---|---|---|---|---|---|
| A800 | `fixed_v1` | 800 | 8.3 | | | **54.7** | 43,760 s | **12.2** |
| B1600 | `fixed_v1` | 1600 | 16.5 | | | **63.2** | 50,560 s | **14.0** |
| C2752 | `fixed_v1` | 2752 | 28.4 | | | **75.3** | 60,240 s | **16.7** |
| D5504 | `fixed_v1` | 5504 | 56.8 | | | **104.2** | 83,360 s | **23.2** |
| E11008 | `fixed_v1` | 11008 | 113.6 | | | **162.2** | 129,760 s | **36.0** |
| **ladder subtotal** | | | | | | | 367,680 s | **≈102.1 core-h** |
| **W2752** (attribution, §3.6) | **`walled`, R9 OFF** | 2752 | 28.4 | | | **75.3** | 60,240 s | **16.7** |
| **TOTAL, FUNDED** | | | | | | | **427,920 s** | **≈118.8 core-h** |

Total games: **6 × 800 = 4,800**.

⚠️ **W2752 is priced identically to C2752** — the rules profile changes board geometry and a scoring rule, not
the search budget. Second-order timing differences (the `centered18` grid and the `redraw` rule change game
length slightly) are inside the model's own ±1.5% validation error and are not modelled. The pilot's `walled`
arm re-measures it anyway.

⚠️ **The ladder is RUNG-DOMINATED at the bottom.** At A800 the frozen python rung is **81%** of the cell's cost
and the rust probe is 15%. The ~8× rust speedup buys nothing on the rung side — the h800/greedy/bare-net rungs
are frozen Python **by design** (the harness manifest's own words). This is why the bottom two rungs, which the
prep doc treated as the cheap ones, still cost 26 core-h between them.

### 6.2 Wall-clock, by box

| box | W | wall (funded 118.8 core-h) | note |
|---|---|---|---|
| local 5900XT | 22 | **≈5.4 h** | the D2 configuration, measured — the calibration above IS this box at this W |
| local 5900XT | 14 | **≈8.5 h** | |
| laptop | 22 | **≈5.4 h *if* per-core speed matches local** | ⚠️ NOT MEASURED — pilot-gated, see below |

**Box is decided at launch by availability** (§0.2 Q6). The launcher is parameterized for both.

⚠️ **`core-h` is not box-portable here.** Every ms/move above is a *local* measurement. The laptop's per-core
speed and its DRAM behaviour under W=22 are unmeasured for this workload, and W is per-box by standing rule.
**The §9 pilot re-measures `rung_ms_per_move` and `champ_prefix_ms_per_move` on whichever box is chosen and the
launcher prints a re-projected wall before any real cell fires.** A laptop leg whose pilot rung ms/move exceeds
the local 624.3 by >25% should be re-costed and re-confirmed with the owner before launch, not absorbed.

⚠️ **W=22 on the local box was measured with a python-rung/rust-probe mix at these budgets and is not a
generic W.** At E11008 the mix shifts hard toward the rust probe; the memory rule (`worker_count_by_bottleneck`)
says re-bench after any code-era change. The pilot's timing print is the cheap version of that check.

### 6.3 Optional extensions — priced, unfunded, authorized by nothing here

| ext | what it buys | cost | status |
|---|---|---|---|
| (a) an extra cell at `k4×2752 = 11008` | restores the **pure-budget** axis at the top rung and gives a second same-allocation E3 comparator (`fair_ruler_rebase_11008`, +114.3); lets Δ₄ be decomposed into budget vs allocation | ≈36 core-h | ⛔ **UNFUNDED** — Q2 ruled: keep k8×1376 as drafted |
| (b) an extra cell = rung E **with the deploy tie-arbiter B=64/J=4 ON** | locates the **full** desktop deploy champion on the re-based ruler (§3.4's stated gap) | ≈74 core-h (probe side × ρ_wall(64) = 2.4897) | ⛔ **UNFUNDED** — Q3 ruled: the arbiter-off gap is ACCEPTED and named in the scope fences |
| (c) n=800 decks/cell | halves every se: `se(R)` 0.47, `se(Δ)` `se(A)` 0.63, and drops the E3 screen from ~62 elo to ~44 elo — still not enough to resolve a G1→G2-sized shift cleanly | ≈238 core-h (2× the funded cell) | ⛔ **UNFUNDED** |
| (d) rules-only attribution at one rung | decomposes E3's rules axis from the band draw | ≈17 core-h | ✅ **FUNDED 2026-08-23 and BUNDLED IN** — this is now cell **W2752**, §3.6, and is counted in §6.1 |

Only (d) is funded, and it is no longer an extension — it is in the cell. (a)–(c) are authorized by nothing here.

---

## 7. INTEGRITY GATES

Each is a PRECONDITION. Any FAIL ⇒ `U-UNREADABLE` (`READ_RULE.md` §4). This section is the summary;
**`READ_RULE.md` §3 is the binding text.**

### 7.1 ⭐ THE FOUR D2 INSTRUMENT FIXES — this cell's reason to exist as a separate launcher

D2 (`track_d2_prep`, same harness, same week) fired `U-UNREADABLE` on four defects. Every one is a launcher
defect, not a harness defect, and every one is fixed here **before** game 1:

| D2 defect | what went wrong | fix in this launcher |
|---|---|---|
| **`G-LEAF`** — probe ran the *rung's* leaf | `run_cells.sh` passed no `--cand-leaf-json`; `cand_leaf_hash` read `42af12fce22e1a0f`, not curve125 `a36d2e15a3b3d71d` | `--cand-leaf-json '{"v29_meeple_curve": [-10,-5,-1.25,0,2.5,3.75,5,6.25]}'` in the shared `COMMON` array (§3.1), and the **pilot verifies the realized hash on a real record** before any cell band is touched |
| **`G-RULES`** — `fixed_v1` stamped, R9 never latched | R9 cannot live in the profile (`base_deck` derives farm data at import; the Rust registry latches a `OnceLock`) — `CARCASSONNE_FIX_R9` must be **exported before the process starts**; D2's launcher exported nothing ⇒ `r9_env_ok: false` | `export CARCASSONNE_FIX_R9=1` at the top of the launcher **plus** a pre-flight assertion that `rules_profile.r9_env_on()` is True in a child process, **plus** the pilot's record check |
| **`G-TOOL`/`G-SINGLEVAR`** — mixed-rev cell pair | the main tree moved between the two sequential cells (`ce235373-dirty` vs `513a509d-dirty`); the `RUN_LIVE` latch did not prevent it | `PINNED_SRC_REV` file + pre-flight refusal if `git status --porcelain -- src engine scripts` is non-empty + **re-assertion of `git rev-parse HEAD` and source cleanliness between every cell**, aborting the sequence rather than producing a mixed-rev ladder |
| **`G-TOOL`** — `BLIND_COMMIT` clause was **structurally unsatisfiable** | `eval_fair_puct.py` has **no `BLIND_COMMIT` stamping path at all**, so a gate reading it *from the manifest* could not pass on any healthy run | `G-BLIND` here is deliberately defined against the **launcher artifact + git** (the `BLIND_COMMIT` file holds a 40-hex sha that is an ancestor of HEAD and is the commit that froze this pair), **never** against the manifest. Named in `READ_RULE.md` §3.1 as the reason. **Forward-compatible:** if a `--stamp-key`-style manifest stamping path exists at `PINNED_SRC_REV`, the launcher auto-detects it, passes it, and `G-BLIND` gains an ADDITIVE manifest clause — §7.1.1. |

### 7.1.1 ✅ Reconciliation against the D2-R2 launcher — EXECUTED at freeze, see §0.4

This section is preserved as the DRAFT-TIME record (below, unedited) of what was owed and why it could not be
done then. **The reconciliation itself now lives in §0.4**, executed 2026-08-24 once
`measurement/track_d2r2_prep/run_cells.sh` existed (committed on the unmerged `d2r2-freeze` branch, tip
`4105baed`) — both rows this section marked OWED were closed there: leaf injection moved to the file route with
a `preflight_leaf` check on every leg, and the R9 assertion was extended to every invocation including the pilot
path (a gap this draft's own text below did not yet know it had). `run_cells.sh`'s per-cell rev guard was
already stricter than D2-R2's and is unchanged in posture, only broadened in `CODE_PATHS`; `--stamp-key` is now
confirmed present in the harness and resolves automatically. See §0.4 for the full table and the two items (7-9)
that are new hardening owed by the freeze itself rather than by either prior launcher.

<details>
<summary>Draft-time text (2026-08-23, preserved verbatim for the record)</summary>

The orchestrator asked this draft to compare its mechanisms against
`measurement/track_d2r2_prep/run_cells.sh` and adopt four named ones verbatim where they differ.
**`measurement/track_d2r2_prep/` does not exist on disk at draft time**, and `--stamp-key` / `stamp_key` appear
nowhere in `scripts/`, `src/`, or `measurement/`. The comparison could not be made. Stated plainly rather than
silently skipped, with this draft's position on each named mechanism:

| D2-R2 mechanism | this draft | reconciliation owed |
|---|---|---|
| **R9 file-scope export** | ✅ **same** — `export CARCASSONNE_FIX_R9=1` at file scope, before any function, plus a child-process pre-flight assertion. ⚠️ **But this draft must go further:** cell W2752 (§3.6) needs R9 **OFF**, so the launcher runs that one cell under `env -u CARCASSONNE_FIX_R9`. A pure file-scope export is *insufficient* for a design that carries a `walled` arm. | none — but if D2-R2 adopts a `walled` arm it inherits this trap |
| **in-process leaf injection** | ⚠️ **DIFFERS.** This draft injects curve125 via the harness's own documented CLI path, `--cand-leaf-json`, byte-identical to the string the five G2 `fair_ruler_*` cells passed (verified against their manifests' `config.cand_leaf_json`). It is verified end-to-end by the realized `cand_leaf_hash` in the pilot and by `G-LEAF` in every cell. | **OWED:** if D2-R2's in-process injection is materially different (e.g. it defends against an env-ordering hazard the CLI path does not), adopt it. The CLI path is chosen here because it has five successful precedent cells; it should not be swapped for an unread mechanism on assertion alone. |
| **per-cell rev guard** | ✅ **same, and stricter** — `assert_rev_pinned` runs **before AND after every cell**, comparing `git rev-parse HEAD` to `PINNED_SRC_REV` and re-checking `src/ engine/ scripts/` cleanliness, appending to `SRC_CLEAN.jsonl`, and **aborting the sequence** rather than producing a mixed-rev ladder | none |
| **`--stamp-key` blind stamping** | ⚠️ **NOT AVAILABLE at draft time.** The launcher **auto-detects** it (`--help` probe) and, if present, passes `--stamp-key BLIND_COMMIT=<sha>`; `BLIND_PROOF.json` records `blind_stamp_mode` as `"manifest"` or `"artifact"`. `G-BLIND` verifies artifact + git ancestry **always**, and the manifest value **additionally** when the mode is `"manifest"`. | none — the gate is satisfiable in both worlds and records which applied |

⛔ **Whoever freezes this pair must re-run this comparison once `track_d2r2_prep` exists.** The two rows marked
OWED are the only places this draft could be behind, and both are launcher-level, not pair-level: they can be
fixed in `run_cells_DRAFT.sh` without touching a bar in `READ_RULE.md`.

</details>

### 7.2 The gate table

⚠️ **The gates are in TWO GROUPS.** §7.2A gates the **ladder** (E1/E2/E3) and voids it. §7.2B gates the
**attribution read** (E4) and voids **only that** — a W2752 failure never touches the funded ladder deliverable
(§3.6). The dependency runs one way: a ladder `U-UNREADABLE` also voids E4, because E4 needs C2752.

#### 7.2A — LADDER gates (the five `fixed_v1` cells)

⚠️ "ALL FIVE" below means the five ladder cells. **W2752's equivalents are enforced transitively by `GW-PAIR`**
(§7.2B), which requires every `config` key except `rules_profile` to be identical to C2752 — so the leaf, rung,
backend, budget, arbiter and endgame properties are pinned on the attribution cell too, without duplicating six
gate rows.

| id | the adjudicator VERIFIES… | VOIDS on |
|---|---|---|
| `G-BAND` | every cell's `config.seed_start == 145000000000`, `config.n_decks == 400`, `config.seatings_per_deck == 2` | any mismatch |
| `G-DECKS` | the **record-derived** deck sets are identical across all five cells; `n_common == 400` | any mismatch |
| `G-SINGLEVAR` | the five `config` blocks differ ONLY in `champion.k_dets`, `champion.sims_per_det`, `champion.total_sims`, the output path, and `claim_host` — **`code_rev` is explicitly in the must-not-differ set** | any other differing key |
| `G-REV` | all five manifests carry the SAME `code_rev`, equal to `PINNED_SRC_REV`; the launcher's per-cell source-cleanliness log records `src/ engine/ scripts/` clean at every cell boundary | any mismatch or any recorded dirty boundary |
| `G-BLIND` | the `BLIND_COMMIT` file holds a 40-hex sha, that sha is an ancestor of HEAD, and it is the commit that introduced this pair's FROZEN banner | placeholder, non-ancestor, or absent |
| `G-LEAF` | `config.cand_leaf_hash == a36d2e15a3b3d71d` in ALL five; `config.rung.leaf_hash == 42af12fce22e1a0f` in ALL five and identical across them | mismatch or absence |
| `G-RULES` | `rules_profile.name == "fixed_v1"` AND `rules_profile.r9_env_ok == true` in ALL five | anything else |
| `G-BACKEND` | **per leg**: `config.backend.name == "rust"`, `requested == "rust"`, `"candidate" in converted_sides`, `mixed_builds == false`; and `carc_rs_version` + `carc_rs_binary_sha` + `tile_data_semantic_digest` identical **across** all five | any leg not rust-resolved, or any cross-cell build mismatch |
| `G-RUNG` | ALL five: `config.rung.agent == "HeuristicMCTS"`, `rung.c == 3.0`, `rung.sims == 800` | any deviation |
| `G-BUDGET` | cell-wise `(k_dets, sims_per_det, total_sims)` == (4,200,800) / (4,400,1600) / (4,688,2752) / (4,1376,5504) / (8,1376,11008), and `k_dets × sims_per_det == total_sims` | any deviation |
| `G-TIEARB` | `config.cand_tiearb.enabled == false` in ALL five | any cell with the arbiter armed |
| `G-EXACT` | `config.endgame.exact_k == 2`, `mode == "marginalized"`, `shared_by_both_arms == true`, in ALL five | any deviation |
| `G-N` | 800 games scored in EACH cell; `n_failed == 0` (a nonzero rate **< 2%** is reported, not silently absorbed, and does not by itself void — the b32v64 precedent's 0.100% rust panic class) | short of 800 completed games, or a failure rate ≥ 2% |
| `G-SAT-END` | the **endpoint** cells A800 and E11008 each have candidate winrate vs h800 inside `[0.50, 0.90]` | outside — `SPAN` would be a rail reading, not a range reading |

#### 7.2B — ATTRIBUTION gates (cell W2752 only; a FAIL voids E4 alone)

| id | the adjudicator VERIFIES… | VOIDS (E4 only) on |
|---|---|---|
| `GW-RULES` | W2752's `rules_profile.name == "walled"` AND `rules_profile.r9_env_ok == true` — ⚠️ **which for `walled` means `r9_env_observed == false`**, the inverted expectation (§3.6) | anything else; in particular a `walled` artifact with `r9_env_observed == true` is a launcher that forgot to unset R9 |
| `GW-PAIR` | W2752 and C2752 differ in **exactly** `rules_profile`, the output path, and `claim_host` — **every other `config` key identical, `code_rev` included** | any other differing key; in particular any difference in `cand_leaf_hash`, `rung.*`, `backend.*`, `champion.*`, `endgame.*` |
| `GW-DECKS` | W2752's record-derived deck set equals C2752's; `n_common(C,W) == 400` | any mismatch |
| `GW-N` | 800 games scored; `n_failed == 0` (same <2% tolerance) | short of 800, or ≥2% |
| `GW-SAT` | W2752's candidate winrate vs h800 inside `[0.50, 0.90]` | outside — `A` would be a rail difference |

**Printed WITNESSES — never voiding** (`READ_RULE.md` §4.3): `G-SAT-MID` (the winrate of C2752/D5504/B1600, flagged
if outside `[0.50, 0.90]`), `W-TIMING` (all six `rung_ms_per_move` within ±25% of each other — the rung is the
same agent in all six, so a larger drift means box contention moved mid-run and the §6 cost read is not
comparable across cells), `W-COST` (realized s/game per cell vs §6's model), `W-SCALE` (the realized elo/pt),
`W-GAMELEN` (mean moves/game in C2752 vs W2752 — the `centered18`+`redraw` rules change game length a little,
and this is where that shows up).

⚠️ **`W-TIMING` is deliberately a witness, not a gate.** Voiding a 119-core-h ladder for a box-contention
reason would be a bad trade; the reading it protects is the *cost* model, not the strength statistic.

### 7.3 The structural test — every gate, before game 1

*Would this gate fail on every healthy run of this launcher?* Answered per gate in `READ_RULE.md` §3.1. Summary:
`G-SINGLEVAR`/`G-BUDGET` are structural (one shared `COMMON` array, one budget table); `G-LEAF`/`G-RULES`/
`G-BACKEND`/`G-RUNG`/`G-TIEARB`/`G-EXACT` are all written by `eval_fair_puct.py`'s own manifest logic and are
**each verified against a real record by the §9 pilot before any cell band is touched** — that pilot sweep is
the direct remediation of the D2 miss; `G-BLIND` is satisfiable **only because** it reads the launcher artifact
and git rather than the manifest (§7.1); `G-REV` is enforced by the launcher's own pre-flight and inter-cell
re-assertion, so a healthy run cannot fail it.

⚠️ **`GW-RULES` gets the test explicitly, because its expectation is INVERTED and an inverted gate is exactly
the class that looks unsatisfiable to a careless reader.** `walled` carries `r9_env_expected = False`, so
`r9_env_ok == true` on a `walled` artifact requires R9 to be **off** in that process. The launcher runs W2752
under `env -u CARCASSONNE_FIX_R9`, and the §9 pilot's `walled` arm proves the inversion on a real record before
the band is spent. Would `GW-RULES` fail on a healthy run of this launcher? **NO** — but it *would* fail on a
launcher that only exported R9 at file scope, which is why it is gated at all.

**Answer for every gate: NO.**

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch so no branch can be narrated past them:

1. **It does not re-rate the champion.** Every `R_i` is a reading *against the fixed h800 rung*. The champion's
   own strength claims (CL-060/CL-071) are direct head-to-heads and are **not** ladder-denominated — they do not
   move when the ladder is re-based.
2. **It does not touch `governance/PRODUCTION.yaml`.** This is instrument calibration, not a strength lever.
3. **It does not locate the full desktop deploy champion** — arbiter-off, §3.4. ⛔ Ruled 2026-08-23 (§0.2 Q3):
   this gap is **ACCEPTED**, and the cell that would close it (§6.3(b), ~74 core-h) **stays unfunded**.
4. **It does not fully decompose the era delta.** The funded attribution cell (§3.6) resolves the **rules**
   axis at one rung to ±24 elo (§4.4.1); the residual `D_2752 − A` (band ⊕ n ⊕ code drift) is a leftover at the
   ±62-elo E3 resolution and is **not** an estimate of the band effect. At the other four rungs nothing is
   decomposed, and no era shift smaller than ~62 elo resolves anywhere.
5. **It gives no cross-era reading at the 800 and 1600 rungs** (§2, E3) — those are new absolutes.
6. **Δ₄ is not a pure budget increment** (§3.2).
7. **It does not tell you whether the fair ladder is the RIGHT ruler** — only what it reads on the instrument
   production actually runs. The clairvoyant-rung caveat CL-046 has always carried (the rung is a *fixed
   yardstick*, not a fair opponent) is untouched by this cell and survives it verbatim.
8. **`A` does not extrapolate.** It is the rules effect on the candidate-minus-rung margin **at the 2752 rung
   only**, and it does not decompose the `fixed_v1` bundle's four levers from each other or from R9 (§3.6).
9. **A null on any statistic is a bound, not a zero.** The easiest thing for a later reader to get backwards.

---

## 9. THE PILOT (pre-blind, mandatory, ~15 minutes)

**n=8 decks (`--n 16 --paired`) on the DISJOINT range `145999999000..145999999007`, run TWICE: once in cell
A800's `fixed_v1` config, once in the `walled` config (the W2752 arm).** Both arms are required; the `walled`
arm is ~2 minutes and is the only thing that can catch the §3.6 R9-inversion trap before the band is spent.

**Purpose — a full STRUCTURAL GATE SWEEP against real records, which is what D2 lacked:**

(a) assert on a real `manifest.json` that **`cand_leaf_hash == a36d2e15a3b3d71d`**, **`r9_env_ok == true`**,
`rules_profile.name == "fixed_v1"`, `backend.name == "rust"`, `cand_tiearb.enabled == false`,
`rung.c == 3.0 / rung.sims == 800 / rung.leaf_hash == 42af12fce22e1a0f`, `endgame.exact_k == 2` —
i.e. **every §7.2 gate that is a property of the invocation, checked before the band is spent**;

(b) print `rung_ms_per_move`, `champ_prefix_ms_per_move`, `solver_secs_per_game` on **this box**, re-project §6's
wall-clock, and FAIL LOUD if the rung ms/move exceeds the local-calibrated 624.3 by >25% (a re-cost + owner
re-confirm, not an absorb);

(c) confirm `n_failed == 0` in both arms;

(d) ⭐ **the `walled` arm** asserts `rules_profile.name == "walled"` AND `r9_env_ok == true` AND
`r9_env_observed == FALSE` — the inverted expectation (§3.6 / §7.2B `GW-RULES`). A launcher that exported R9 at
file scope and forgot `env -u` for this cell FAILS here, ~2 minutes in, instead of 17 wasted core-h later.

⛔ **The pilot is the only place anything may move, and only the BOX and W may move — no experimental knob is
re-pickable here.** (D2's pilot was permitted a one-time `--sims` re-pick because its probe budget was defined
by an *equal-time* target; this cell's five budgets are named production/lineage configs, so there is nothing to
re-pick.) The pilot band is DISCARDED and never pooled. After the blind commit, nothing moves.

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) `experiments/results.csv` — **six rows**, one per cell,
with the four spacings, `SPAN`, and `A` recorded in the notes; ⚠️ **`fixed_v1` refuses a results.csv row unless
the profile name is in the `exp_id`** (`rules_profile.py` spec A0) — the exp_ids are therefore
`fair_ruler_g3_fixed_v1_{800,1600,2752,5504,11008}` plus `fair_ruler_g3_walled_2752` for the attribution cell
(`walled` is the default profile and carries no such constraint, but the name is in the exp_id anyway so the
pair is greppable as a pair) · (2) `DECISIONS.md` index line · (3) status stamp on this
`DESIGN.md` and on `READ_RULE.md` · (4) governance: **CL-046 amended** to carry G3 as its third generation
(numbers of G1/G2 stand), `BAND_REGISTRY.csv` `decision_influenced` + band retirement · (5) `STATUS.md` top
block · (6) the roadmap D1 line
([`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md) line 110 — its
"named successor" clause is this cell). Then `python3 scripts/doc_lint.py`. Commit; do not push without asking.
