# TRACK D PREP — D1 / D2 / D3, prepared 2026-08-23

> ⚠️ **Status: PREP ONLY — NOTHING LAUNCHED, NOTHING CLAIMED, NOTHING COMMITTED.**
> No games were played, no band was claimed, no governance row was written, no
> source file was edited. This document prices three open Track-D items and hands
> the orchestrator a ready-to-launch package for one of them. Every number below is
> either quoted off disk or derived from realized per-game records — where a figure
> is an extrapolation, the arithmetic and its base measurement are shown.
>
> Scope: [docs/PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md) Track D,
> framed by [docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md](MEASUREMENT_FIRST_SPEC_2026-06-18.md).
> D2 prereg drafts live in `measurement/track_d2_prep/` (untracked by design — they
> are DRAFT, not blind-committed; the blind commit is the orchestrator's call).

---

## 0. Headline

| item | ready to launch? | cost | buys | recommendation |
|---|---|---|---|---|
| **D1 — annotation batch** (4 HIGH rows + CL-046) | ✅ yes, **0 games** | ~1 session of doc work | stops four HIGH governance rows silently overstating by ~156 elo; closes the roadmap's D1 as written | **DO FIRST** |
| **D2 — rung compression** | ✅ yes, **no build needed** | **16.1 core-h · ≈0.75 h wall @ W22** | the only Track-D item that buys new measurement; resolves a live 2.8× contradiction in the ladder's own spacing | **DO SECOND** |
| **D1 — fair-ladder re-baseline** (the part that genuinely owes games) | ⚠️ scoped, not drafted | **84.0 core-h · ≈3.8 h wall @ W22** (n=400 decks × 5 rungs) | a `fixed_v1` + rust ruler of record; today's ruler is python + pre-`fixed_v1` | **ONLY IF the fair ladder gets quoted again** (E4 gate) |
| **D3 — K=3 bulk + K=4 subset + TAU_VS_K** | ⚠️ runnable, **no consumer** | 44.5 core-h · ≈3.5–4.3 h wall | nothing anyone is waiting for — see §4 | **DO NOT RUN. Close by annotation.** |

Two findings arrived during prep that change what these items cost:

1. **The "c=1.5-rungs vs c=3.0-champion inconsistency" (D2) is a documentation
   defect with zero configuration content.** Every heuristic rung this program has
   ever run has been at UCT `c = 3.0`. This removes an entire experimental arm from
   D2 and halves its cost. Evidence chain in §2.2.
2. **The ruler of record is staler than D1 assumes, in a direction D1 did not
   name.** CL-046's fair ladder was already re-baselined post-CL-056 by F5
   (`fair_ruler_rebase_*`, 2026-07-19/20) — but that re-baseline ran on the
   **python** backend under **pre-`fixed_v1` (walled)** rules, while production has
   been `fixed_v1` + rust since 2026-08-01/03. So the D1 re-anchor has a second,
   unnamed axis. §3.5.

---

## 1. Framing — what Track D is for

[docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md](MEASUREMENT_FIRST_SPEC_2026-06-18.md)
is the diagnosis of record: both strength levers were exhausted and the binding
constraint is **blocker #1 — no strong non-saturated reference exists**. Track D is
the work that keeps the ruler honest. D0 (the fair sub-ladder) and D-recon are ✅
done. D1, D2, D3 are what is left, and all three are *measurement-validity* items:
none of them makes the agent stronger, and none of them should be sold as if it
might.

That framing sets the bar for this document. A Track-D item earns compute only if
some claim currently being quoted would read differently after it runs. D1 and D2
clear that bar. D3 does not, and §4 says so plainly rather than dressing it up.

---

## 2. D2 — Rung-compression cell

### 2.1 The item, and what it actually asks

Roadmap line, verbatim
([docs/PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md) line 111):

> **D2. Rung-compression cell** (audit #5): PUCT rung @equal-time-h800 vs h800/h1600
> rungs, shared decks, n=200 each (~2h) — are ladder *spacings* denominated in
> weak-search units? Fix the c=1.5-rungs vs c=3.0-champion inconsistency in the same
> pass.

Every strength number this program quotes against the heuristic ladder is
denominated in one unit: the gap between adjacent h-rungs. The program has measured
that gap twice and **the two measurements disagree by 2.8×**:

| source | contrast | n | band | result |
|---|---|---|---|---|
| `measurement/level2/LEVEL2_LADDER_VERDICT.md` (CL-023, 2026-06-18) | heur_v2_7@1600 vs @800 | 400 paired | fresh 3.0e9+ | **+55.2 ± 17.6 elo, paired z 3.23** |
| `experiments/results.csv` → `l22_ctrl_heur1600_vs_heur800_b310_n400` (2026-06-19) | same | 400 | 3.10e9 | **+20.0 elo**, σ 17.4, z 3.285 |

Same contrast, same n, one day apart, different bands. That is inside CL-068's
measured 1.8–2.2× cross-band over-dispersion envelope — but it is *unresolved*, and
the project's own results-discipline rule says a contradiction is not a discovery
until it is resolved. Worse, neither measurement was taken on the rung the **ruler
of record** actually uses (see §2.2 for why that matters less than it sounds, and
§2.4 for what does differ).

So D2's question is sharper than "are spacings compressed": **is the unit the fair
ladder is denominated in large enough to be a unit at all, and which of the two
prior readings is right?**

### 2.2 The c=1.5 / c=3.0 inconsistency — named, and resolved at zero games

This is the finding that reshapes D2. The evidence chain, all verified on disk:

- `src/carcassonne_ai/mcts.py:36` — `DEFAULT_C = 3.0  # Ameneyro et al. 2020 — UCT
  exploration constant`. `MCTS.__init__` (line ~82) takes `c: float = DEFAULT_C`.
  `HeuristicMCTS.__init__` (line 315) forwards `**kwargs` to `super().__init__()`
  and defines no `c` of its own.
- `git log -L 30,40:src/carcassonne_ai/mcts.py` — `DEFAULT_C` was introduced at
  **3.0** in `534043a4` ("phase 2: vanilla MCTS with state-mutation rollout
  optimization") and has never been changed. It has never been 1.5.
- Every `HeuristicMCTS(` construction site in `scripts/` and `src/` was enumerated.
  The ladder-relevant rung constructors pass **no** `c` — `scripts/ladder_rung_eval.py:89`
  (the L2 ladder's rung) and `scripts/level2/eval_hybrid_handoff.py:203,238` (the
  hybrid cells) — so they run at 3.0. The sites that do pass `c` pass 3.0:
  `scripts/classical_search/eval_fair_puct.py:762` (`c=RUNG_C`, with line 421
  `RUNG_C = DEFAULT_C  # 3.0`), `scripts/classical_search/eval_puct_priors.py:330`,
  `scripts/f3_public_state_oracle/mine_roots.py:118`,
  `scripts/canonical_az/fairness_decision_probe.py:144`.

⇒ **Every heuristic rung this program has ever run — the L2 ladder, the hybrid
cells, and the CL-022 rung inside `eval_fair_puct.py` — ran at UCT `c = 3.0`.** The
champion's `c_puct = 1.5` is a *different parameter of a different algorithm* (PUCT's
prior-weighted exploration term, `governance/PRODUCTION.yaml:101`, re-swept at 2750
sims). There is no configuration inconsistency to fix.

The inconsistency is real but it lives in the paperwork, in two places:

1. `measurement/level2/LEVEL2_LADDER_VERDICT.md`, section "Config note — the heur
   rungs run at the PRODUCTION ruler's actual c_puct", asserts *"All heuristic rungs
   use `HeuristicMCTS` at the module default **c_puct = 1.5**"* and then infers that
   the `old_c=3.0` in older results.csv rows is "the net-side c". **The module
   default is 3.0. The note is inverted**, and its inference is backwards.
2. `experiments/results.csv` stamps `old_c=1.5` on the *rung* side of the five F5
   fair-ruler rows (`fair_ruler_rebase_2752/5504/11008`, `fair_ruler_k8x688_5504`,
   `fair_ruler_k8x1376_11008`) while those cells' own `manifest.json` records
   `config.rung.c = 3.0`. The older D0 rows (`fair_ladder_s*_vs_h800_k2`) correctly
   carry `old_c=3.0`, so this is drift, not a convention.

**Cost to resolve: zero games.** It is a correction to one verdict doc and five CSV
cells. ⚠️ It is *not* a correction a subagent should make unilaterally —
`experiments/results.csv` is a declared source of truth. Flagged for owner sign-off,
listed in §5 as a free action.

What this saves: a literal reading of the roadmap line funds a 2×2 design
(`rung_sims` × `rung_c`) at double the cost, plus a harness change (`RUNG_C` is a
module constant with no CLI flag), plus a worktree build and merge window — for an
arm with no experimental content. **D2 is 2 cells, not 4, and needs no build.**

### 2.3 The design

Two cells, one band, one deck set, differing in **exactly one experimental
argument** — `--rung-sims`.

| | CELL R800 | CELL R1600 |
|---|---|---|
| probe (identical) | fair PIMC k4×688 = 2752 total sims, rust, `fixed_v1`, exact-K 2, c_puct 1.5, τ_p 5, float leaf, visits, tie-arbiter **OFF** | same |
| rung | `HeuristicMCTS(h800, c=3.0)` | `HeuristicMCTS(h1600, c=3.0)` |
| decks | seeds `141000000000..141000000199`, 200 decks × 2 seatings = 400 games | **the same 200 decks** (CRN) |

**PRIMARY statistic** = the deck-paired spacing `S = M_R800 − M_R1600`, where
`M_cell` is the cell's deck-paired mean margin in points/game over the decks present
in both cells. `S` *is* the h800→h1600 rung gap, expressed in probe-margin points.
Elo is secondary and reported only for continuity with CL-023.

**Why the probe is k4×688 = 2752** — three reasons, all measured:

1. It **is** the roadmap's "PUCT rung @equal-time-h800". The h800 rung measures
   `rung_ms_per_move` = 383.8 / 384.9 / 387.0 / 388.6 / 443.5 ms across the five F5
   fair-ruler cells (median 387.0). The rust champion measures ≈1,700 ms/move at
   11008 total sims (1466.5 / 1676.4 / 1721.0 / 1861.6 across four deploy-11008
   cells) ⇒ ≈0.154 ms per total-sim ⇒ equal-time ≈ **2,507 total sims**. k4×688 =
   2752 is within 10% of that, and the design pre-registers a 5-minute pilot that
   verifies the realized ratio on the actual box and re-picks once if it lands
   outside [0.85, 1.20].
2. It is a **named production-lineage config**, not an invented one: k4×688 = 2752
   was the desktop deploy champion from 2026-07-13 to 2026-07-29 (`fair_kdets_folded_in`
   / `budget_folded_in` in `governance/PRODUCTION.yaml`), and it is still what the
   **mobile** profile runs as its floor. The program has already run this exact total
   five times.
3. It is **measured non-saturating**: `fair_ruler_rebase_2752` at exactly this budget
   scored wr 0.685 / +135.0 elo / paired margin +8.6425 against h800, so the margin
   statistic has headroom in both directions against both rungs.

⚠️ **Deviation, named in the design.** "Equal-time" here is equal wall-clock *in the
deployed implementations* — a rust candidate against a rung that is frozen Python by
construction (`eval_fair_puct.py`'s own manifest note: *"the h800 / greedy / bare-net
rungs are FROZEN RULERS and stay Python by design"*). That is a deployable-value
statement, not an algorithmic "PUCT beats UCT X× per node" statement. The realized
ratio is reported from the cells, not assumed.

⚠️ **Not poolable with the F5 ladder.** The F5 rows ran python + pre-`fixed_v1`
(their manifests carry `rules_profile: null` and no backend block). D2 runs
`fixed_v1` + rust. D2 claims only its internal cell-vs-cell contrast.

### 2.4 Power — the honest part

At n_paired = 200, the F5 cells realize se(M) = `paired_mean_margin / paired_z`:
8.6425/9.5101 = 0.909, 10.7825/11.3029 = 0.954, 7.935/8.4547 = 0.939 ⇒ **se(M) ≈ 0.93
pts**. CRN across cells is used, but CL-068 measured the cross-cell CRN benefit at
only ~9.9% of contrast variance in the comparable case, so assume ρ ≈ 0.10:

`se(S) = 0.93 · √(2·(1−0.10)) = 1.25 pts` ⇒ **2σ MDE = 2.50 pts ≈ 39 elo**
(realized scale from `fair_ruler_rebase_2752`: +135.0 elo ↔ +8.6425 pts ⇒ 15.6
elo/pt).

| prior | in points | z at n=200 |
|---|---|---|
| CL-023's +55.2 elo | ≈3.5 | ≈2.8 ✅ resolves |
| results.csv's +20.0 elo | ≈1.3 | ≈1.0 ❌ does not resolve |

**So the roadmap's n=200 is a screen for the large reading, not an adjudication
between the two priors, and a null at n=200 is a ≤39-elo bound — not a zero.** That
is written into the READ_RULE's `D2-BOUNDED-NULL` branch rather than left for the
readout to discover. Separating +55 from +20 needs n ≈ 800 decks/cell (≈64
core-hours); n=400 gets the MDE to ≈28 elo for ≈32 core-hours. Both are priced in
§2.6 and neither is funded.

### 2.5 Ready-to-launch status

**READY. No build, no harness change, no worktree, no merge window.** The harness
already exposes everything the design needs: `--opponent h800` is the fixed CL-022
rung and `--rung-sims` sets its depth freely (the mode name is a misnomer the help
text acknowledges).

Owner sign-off is owed on four things before launch: the ~16 core-hours; the band
claim; the probe-budget choice; and tie-arbiter OFF (the production champion carries
`tiearb` B=64 since 2026-08-20, but a probe must be a *stable yardstick* and the
arbiter's own adjudication is recent — the design argues for OFF and flags it).

Box state at prep time (2026-08-23): **both boxes free** — local `ps -C python`
empty, `ssh laptop-wsl` `ps -C python` empty, and no `measurement/**/RUN_LIVE.json`
sentinel anywhere in the tree, so the freeze-latch hook is not armed. Re-census
immediately before launch regardless; this is a snapshot.

Pre-launch checklist, in the drafts: claim band `141000000000` in
`governance/BAND_REGISTRY.csv` → freeze and commit the pair → stamp `BLIND_COMMIT`
→ run the §9 pilot and pass its gate → process census → drop `RUN_LIVE.json`.

**Launch commands** (from `measurement/track_d2_prep/run_cells_DRAFT.sh`; the script
refuses to start unless `BLIND_COMMIT` and `BAND_CLAIMED` exist in the cell dir —
`--dry-run` and `--pilot` are exempt, since neither spends blindness). ⚠️ The script
ships **mode 644, deliberately non-executable**: the orchestrator `chmod +x`es it as
part of authorizing, so until then invoke it as `bash <path>`.

```bash
# 0. cost + argv only, starts nothing
/home/doctor/projects/carcassone/measurement/track_d2_prep/run_cells_DRAFT.sh local --dry-run

# 1. the pre-blind pilot (8 decks, throwaway seed range, ~5 min)
/home/doctor/projects/carcassone/measurement/track_d2_prep/run_cells_DRAFT.sh local --pilot

# 2. the two cells (after BLIND_COMMIT + BAND_CLAIMED exist)
/home/doctor/projects/carcassone/measurement/track_d2_prep/run_cells_DRAFT.sh local --band 141000000000
```

The underlying per-cell invocation, for the record:

```bash
/home/doctor/projects/carcassone/.venv/bin/python \
  /home/doctor/projects/carcassone/scripts/classical_search/eval_fair_puct.py \
  --info fair --opponent h800 --backend rust \
  --k-dets 4 --sims 688 --exact-k 2 \
  --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select visits \
  --n 400 --paired --seed-start 141000000000 \
  --rules-profile fixed_v1 --workers 22 \
  --out-root /mnt/c/carc-shared/track_d2 --out-subdir d2_rung800 \
  --shared-claim --claim-host d2-rung800-$(hostname) --claim-stale-secs 1800 \
  --no-results-csv \
  --rung-sims 800          # ← CELL R1600 differs here, and only here: --rung-sims 1600
```

⚠️ `--n 400` is **400 games = 200 decks** under `--paired` (2 seatings/deck). This
matches `fair_ruler_rebase_2752`, whose manifest records `n: 400` with `n_paired:
200`. Do not "fix" it to 200.

### 2.6 Cost — from realized per-game records, not a model

Base measurements, all from real game records and summaries on the share:

- a game is ~143 moves; ~70 probe decisions (`champ_prefix_moves` 68–70) and ~71
  rung decisions (`rung_moves` 70–72)
- probe @ 2752 rust: 2752 × 0.154 ms = 0.425 s/move ⇒ **29.8 s/game**
- rust exact-K=2 solver: **1.3 s/game** (measured `solver_secs_per_game` 1.1–1.4 in
  four rust deploy cells; the python-era figure was 12.9–18.7 s — do not use it)
- rung h800: 0.387 s/move ⇒ **27.5 s/game**; h1600: 0.774 s/move ⇒ **55.0 s/game**

| cell | s/game | × 400 games | core-h |
|---|---|---|---|
| R800 | 58.6 | 23,440 s | **6.5** |
| R1600 | 86.1 | 34,440 s | **9.6** |
| **total** | | | **16.1 core-h** |

Wall-clock: local 5900XT at W=22 ⇒ **≈0.75 h**; at W=16 ⇒ ≈1.0 h. Inside the
roadmap's ~2h sketch. Note R1600 is **rung-dominated** — the ~8× rust speedup
applies to the probe side only, so buying a deeper rung costs full python price.

Priced and **unfunded** extensions:

| option | extra cost | buys |
|---|---|---|
| third cell at `--rung-sims 3200` | +15.7 core-h | CL-023's third rung; shows whether spacing keeps shrinking (+75.9 / +55.2 / +34.9 was the L2 sequence) |
| same pair with the **current** deploy champion k8×1376=11008 as probe | 35.8 core-h (replaces, not adds) | the production-agent reading instead of the equal-time reading |
| n=400 decks/cell | 32.2 core-h | 2σ MDE ≈28 elo |
| n=800 decks/cell | 64.4 core-h | 2σ MDE ≈19 elo — the only sizing that separates +55 from +20 |

### 2.7 What D2 cannot show

It does not measure h1600-vs-h800 **head-to-head**: `eval_fair_puct.py`'s candidate
side is always a PIMC agent, so there is no rung-vs-rung mode. That direct cell would
be both cheaper (no probe side, no solver) and ~1.4× more powerful, and is the right
build if this question recurs. D2 also does not re-rate the champion, license any
`governance/PRODUCTION.yaml` change, transfer to the walled/python F5 absolutes, or
say whether the ladder is the *right* ruler — only how coarse its unit is.

---

## 3. D1 — Ruler re-anchor of the HIGH governance rows

### 3.1 What D1 actually names

Roadmap line 110: *"**D1. Ruler re-anchor of the HIGH governance rows** (flip
proposal §3: CL-041/LADDER/HYBRID/CLEAN_EVAL) — re-grade against the new champion +
the FAIR ladder so the old clairvoyant numbers stop silently overstating (~156 elo)."*

The "flip proposal §3" is
`measurement/classical_search/PHASE1.1_FLIP_PROPOSAL_DRAFT.md` §3 ("Ruler re-anchor
scope — THE LOAD-BEARING PART"), a table grading re-anchor *need* as HIGH/MED/LOW.

⚠️ **Precision that matters for scoping: "HIGH" in D1 is the flip proposal's
re-anchor-need column, not the claim registry's `confidence` column.** 65 of the 81
rows in `governance/CLAIM_REGISTRY.csv` carry `confidence: high`; only four
doc/claim clusters carry re-anchor-need HIGH. Two of those four (CL-023, CL-026) are
in fact `confidence: mid` in the registry. Anyone scoping D1 off the registry's
`confidence` column will scope ~16× too much work.

§3's own closing instruction: *"(a) re-draw the ladder top so the PUCT-priors agent
is the reference rung above h6400; (b) for HIGH rows, re-run the key contender vs the
new top agent (don't rescale by arithmetic…); (c) for LOW rows, a one-line 'strongest
practical ruler superseded' annotation."*

### 3.2 Run manifest, per row

| row | rests on | status today | re-grade needed? | manifest |
|---|---|---|---|---|
| **CL-041** — S1 flip: v2.9.1 Bmild_cap8 leaf + deep-classical (h6400–h12800 + exact K≤4) as production champion | `results.csv v291_THRONE_bmild_cap8_vs_v28prod_h6400_n399`; clairvoyant h6400 opponent; n=399 paired; +64.3 elo / z 3.77 / wr 0.591 | registry already says **`status: SUPERSEDED`**, by CL-043 (2026-07-07, +148.2 / z 10.17 / n=400, transitivity-verified). `governance/PRODUCTION.yaml` already flipped. | ❌ **NO GAMES.** The supersession already happened; what is missing is the *wording*. | **ANNOTATION.** Amend the CL-041 row's `claim` text to state the clairvoyant denomination and point at CL-043; re-word `PRODUCTION.yaml`'s `notes` per the flip proposal's own ask. |
| **LADDER = CL-023** — `measurement/level2/LEVEL2_LADDER_VERDICT.md` + `LADDER_RESULTS.json` | heur-vs-heur depth ladder, `HeuristicMCTS` at c=3.0 (the doc says 1.5 — see §2.2), v2_7 leaf env, n=200–400 paired, fresh bands 3.0e9+ | never superseded by any later claim; its *top rung* is stale (CL-043 put a PUCT rung above h6400) and its *spacings* are contradicted by `l22_ctrl_heur1600_vs_heur800_b310_n400` | ⚠️ **PARTLY.** The "top rung is no longer the strongest classical agent" half is annotation — CL-043 already proves it, and §3(b)'s "re-run the contender vs the new top agent" was *already executed* by the flip cell itself. The *spacing* half is what **D2** measures. | **ANNOTATION + D2.** (i) stamp the verdict doc: top rung superseded by CL-043; (ii) correct the c=1.5 config note (§2.2); (iii) carry D2's `S` onto the row when it lands. **0 additional games beyond D2.** |
| **HYBRID = CL-026** — `measurement/level2/LEVEL2_HYBRID_VERDICT.md`, `results.csv l2hyb_*` | iter8 neural policy handed off to `HeuristicMCTS@N` at k_remaining ≤ K; clairvoyant; n=200–400; band 3.4e9. Verdict: hybrid patches iter8's endgame but still loses to heur@3200 (−13.9 / −19.1) ⇒ *"deep heuristic remains strongest"* | never superseded. But its **subject is dead**: iter8 is two evidence-epochs back, the champion has been classical since 2026-07-07, and "deep heuristic remains strongest" is falsified as a top-of-ecosystem claim by CL-043 | ❌ **NO.** Re-running it would price a dead agent against a dead top rung. | **ANNOTATE → SUPERSEDED.** One line: "'deep heuristic remains strongest' falsified as a classical-top claim by CL-043; the hybrid's subject (iter8) is retired lineage. Not re-run — no live consumer." **0 games.** |
| **CLEAN_EVAL = CL-001 / CL-012** — `clean_eval/CLEAN_EVAL_AUDIT.md` | **entirely clairvoyant, no PIMC anywhere** (the file contains no occurrence of "fair", "PIMC" or "determin\*"): n=400 deck-paired, `--seed-start 1e9`, sims=200, matched-v2.7 opponent (`CAP=12 DROP_THREE_OPEN=1`). Carries iter_11 +89.7/z5.2, Stage-B iter_01 +34.9/z2.0, residual s0 +56.1/z3.4, residual s0.25 +83.2/z4.9, leaf gap v2.7-vs-v1 −24.4/z1.5 | not superseded; every absolute is anchored to a now-non-top opponent | ⚠️ **SPLIT THE FILE.** The audit's *ruler/provenance* claims (CL-013 eval provenance runtime-verified, CL-014 clean seed namespace, CL-015 semantic contracts) are unaffected — they are about the instrument, not about strength, and remain `Confirmed`. The *strength absolutes* (CL-001, CL-012) are era-bound to river/neural-era checkpoints that no longer exist in any live decision. | **ANNOTATION.** Banner the audit: "absolutes are denominated against a clairvoyant, non-top opponent; the leaf effect is non-transitive so they are NOT blanket-discountable, but they are NOT comparable to fair-ladder numbers." Recommend **not** re-running: a fair re-grade would price retired checkpoints. **0 games.** |

### 3.3 So what does D1 cost?

**As the roadmap words it: zero games.** All four named rows close by annotation. The
one that looked like it needed compute (LADDER) is answered by D2 plus a stamp.

That is a real finding and it should be said out loud: **D1 has been sitting open for
six weeks as a compute item when it was a paperwork item.** The reason it looked
expensive is §3.1's HIGH-column conflation.

### 3.4 CL-046 — the fifth row nobody listed

D1 names four rows. There is a fifth that matters more than three of them: **CL-046,
the fair sub-ladder, is the ruler D1 wants to re-anchor everything else *against*.**
Its own provenance:

- CL-046's numbers (+27.9 / +61.4 / +81.4 / +149.3 @ 800/1600/2752/5504, n=200 CRN,
  band 15e9) were measured on the **pre-CL-056 leaky determinization**. `DECISIONS.md`
  2026-07-14 states it directly: *"Every past FAIR number in this repo — the k_dets
  CL-054 +136 anchor, the curve125 fair confirm (CL-051), the D0 fair ladder (CL-046)
  — was measured on the leaky determinization… any FUTURE fair eval must re-establish
  its own fair baseline with the fixed code."*
- ✅ **That re-baseline already happened** and was not folded back into the CL-046
  row: F5 / Track-F, 2026-07-19/20, code_rev `7d129c41e`, n=400 each —
  `fair_ruler_rebase_2752` **+135.0** (margin +8.64, paired z 9.51),
  `fair_ruler_rebase_5504` **+147.2** (+10.78, z 11.30), `fair_ruler_rebase_11008`
  **+114.3** (+7.94, z 8.45), plus the width discriminators `fair_ruler_k8x688_5504`
  +135.0 and `fair_ruler_k8x1376_11008` +123.0.

⇒ **CL-046's row is stale by annotation, not by measurement.** Free action: amend
CL-046 to cite the F5 rebase rows as its post-fix restatement, and note that the
pre-fix ladder read ~54 elo *low* at the 2752 rung (+81.4 → +135.0).

### 3.5 The part that genuinely owes games

Two gaps survive the annotations:

1. **The F5 rebase covers only 2752 / 5504 / 11008.** The 800 and 1600 rungs — the
   bottom of the ladder, the part that anchors "how much is a doubling worth" — were
   never re-measured post-fix.
2. ⚠️ **The re-baseline is itself on the wrong instrument now.** Every `fair_ruler_*`
   manifest carries `rules_profile: null` and no `backend` block ⇒ **python backend,
   pre-`fixed_v1` (walled) rules**. Production has been rust since 2026-08-01 and
   `fixed_v1` since 2026-08-03 (`governance/PRODUCTION.yaml`). So the ruler of record
   grades a rules profile and an engine the champion no longer plays. D1's brief
   ("re-grade against the new champion + the FAIR ladder") silently assumes the FAIR
   ladder is current. It is not.

**Manifest for the one real D1 compute item — a `fixed_v1` + rust re-baseline of the
full fair ladder vs the fixed h800 rung**, five rungs, n=400 decks (800 games) each,
same harness and flags as D2's probe with `--sims` varying:

| rung (total sims) | probe s/game | + solver | + h800 rung | s/game | ×800 games | core-h |
|---|---|---|---|---|---|---|
| k4×200 = 800 | 8.6 | 1.3 | 27.5 | 37.4 | 29,920 s | **8.3** |
| k4×400 = 1600 | 17.3 | 1.3 | 27.5 | 46.1 | 36,880 s | **10.2** |
| k4×688 = 2752 | 29.8 | 1.3 | 27.5 | 58.6 | 46,880 s | **13.0** |
| k4×1376 = 5504 | 59.5 | 1.3 | 27.5 | 88.3 | 70,640 s | **19.6** |
| k8×1376 = 11008 | 119.0 | 1.3 | 27.5 | 147.8 | 118,240 s | **32.8** |
| **total** | | | | | | **84.0 core-h** |

⇒ **≈3.8 h wall at W=22, ≈5.2 h at W=16.** At n=200 decks/cell it halves to 42.0
core-h / ≈1.9 h, at the §2.4 power cost.

**Recommendation: do not fund this yet.** It is the right thing to run *the moment
the fair ladder is quoted again* — which per the roadmap means when **E4 (human
anchor)** unparks, since D0/D1 is E4's stated remaining gate. Until then it produces
a better ruler for measurements nobody is taking. Flagged, priced, queued.

---

## 4. D3 — K=3 bulk + K=4 subset + TAU_VS_K

### 4.1 What it is

Roadmap line 112: *"**D3. Original Phase 3 scope:** solve K=3 bulk + K=4 subset,
TAU_VS_K doc (was 'fix the ruler' MT-2)."*

⚠️ **The strings "TAU_VS_K" and "MT-2" appear exactly once in the entire repo — in
that roadmap line.** `git log --all -S"TAU_VS_K"` and `-S"MT-2"` return only the
commit that introduced it (`a3be42e3`, 2026-07-07). There is no earlier spec, no
`MT-` task list, no `TAU_VS_K.md`. **This item was never specced.** (Note also a
naming collision: `docs/PHASE3_NOTES.md`'s "Phase 3" is the ResNet warm-start, an
unrelated item.)

Reconstructed from converging evidence in `docs/POST_REVIEW_PLAN.md` §"THE
THROUGH-LINE FIX" and `measurement/classical_search/TEACHER_TAU_PLAN.md`:

- **"the ruler"** = the exact-K endgame solver, *"the only non-circular ground truth
  in the project"*.
- **"tau"** = Kendall's τ between an evaluator's ranking of sibling root actions and
  the exact solver's ranking of the same actions. Not a search temperature (that is
  `τ_p`), not a calibration constant. Measured values: v2.9 leaf τ = 0.615, M2 value
  head τ ≈ 0.02, puct_q τ = 0.567, puct_visits τ = 0.578 — all against a bank of
  **1,119 K≤2 marginalized exact roots**.
- **"TAU_VS_K"** = plot τ as a function of solve depth K ∈ {2,3,4}, from a bulk K=3
  solve plus a sampled K=4 subset, to check whether the K≤2 ruler's verdicts survive
  a deeper look.

### 4.2 The consumer — honestly, it is gone

Three independent checks, all pointing the same way:

1. **CL-076 / F13 closed the depth question.** `measurement/exact_k_ladder_20260803/READOUT.md`:
   marginal Δ margin per +1 K = K2→K3 **+0.31**, K3→K4 **+0.76**, K4→K5 **+0.11**,
   K5→K6 **−0.01**; winrate flat at every rung (0.484/0.484/0.501/0.505 against a
   ±35-elo 2σ MDE). Registry: `CL-076`, `status: Established`.
2. **The endgame net that would have consumed a deeper solve is stillborn.**
   `docs/LEVER_INDEX.md:162` — *"specialized endgame net … ☠️ STILLBORN 2026-08-05 —
   KILLED ON A CEILING ARGUMENT, never built."* Named 2026-08-03, killed 2026-08-05,
   never a line of code.
3. **The learners τ was invented to grade are dead.** M2 "KILL — FINAL 2026-07-03"
   (CL-039/CL-042), Stage-0 teacher-τ KILL-CONFIRM 2026-07-07, CL-073 learned value
   offline-dead. The production champion is classical with no net anywhere. The one
   surviving policy thread (B2, net-prior-in-PUCT) is explicitly deferred.

`docs/BACKLOG_REAUDIT_2026-07-13.md:60` even names D3 only as a *contingent*
prerequisite: *"Make/unmake survives only as a K≥5 measurement prerequisite **if
Track-D D3 ever needs it**"* — and the K≥5 question it would have served is closed by
`MARG_FRONTIER.md` §4 by inference.

⇒ **D3 is an orphaned line item whose premises expired underneath it before it was
ever run.** A prepared run with no consumer is exactly that, and it should not be
dressed up as measurement hygiene. It is not blocked on compute — it was never priced
out; it was superseded.

### 4.3 Cost anyway — re-derived against CURRENT rust economics

Memory's "20.8× faster / 19× smaller RSS" figure is **confirmed** against
`measurement/rust_solver_bench_20260803/BENCH.md`: position-paired K=4 clairvoyant,
n=5 — median ×20.77, aggregate ×22.11, node counts agree 5/5, values agree 5/5; RSS
87.7 MB (rust) vs 1,669.7 MB (python) ≈ ×19.0. ⚠️ **But that ratio is for the
clairvoyant alpha-beta mode. D3 runs the marginalized (fair) mode, where the cost wall
is the MODE, not the depth** — marginalized has no alpha-beta.

Marginalized numbers actually to size against, from
`measurement/rust_solver_bench_20260803/MARG_FRONTIER.md` (2026-08-04, clean local
run, exclusive tenant, W4, 3600 s cap, n=20/cell) and `BENCH.md`:

| cell | ok/n | wall min/med/p90/max | RSS med/max | notes |
|---|---|---|---|---|
| marg K3 (`BENCH.md`, n=6, 300 s cap) | 6/6 | — / 94.4 s / 205.9 s / 288.9 s | — / 115.1 MB | 0 timeouts |
| marg K4 (`MARG_FRONTIER.md`, n=20) | 15/20 | 8 / 457 / 2,135 / 3,101 s | 183 / **1,233 MB** | 5 timeouts at 1 h |
| marg K5 | 5/19 | 316 / 1,706 / 1,931 / 1,931 s | 633 MB | **not an option** |

Corpora (the ones the bench itself draws from): K=3 bulk = 436 positions
(`measurement/f3_public_state_oracle/roots_k3_champion.jsonl`); K=4 subset = 96
positions (`measurement/level2/l23_k4_multisource.jsonl`).

| leg | arithmetic | core-h | wall |
|---|---|---|---|
| K=3 bulk, 436 pos | 436 × 94.4 s (median) = 41,141 s → 436 × 205.9 s (p90) = 89,781 s | **11.4 – 24.9** | 0.71–1.56 h at W=16 (CPU-bound; RSS 115 MB) |
| K=4 subset, 96 pos | 72 completing × 457 s = 32,904 s; 24 censored × 3,600 s **floor** = 86,400 s | **33.1** (with an open-ended censored tail) | ≈2.76 h at **W=12** — RAM-bound: 24 GB ÷ (1,233 MB × 1.5) ≈ 12 |
| **total** | | **≈44.5 core-h** | **≈3.5–4.3 h** |

⚠️ Two caveats that must travel with these numbers: (i) they extrapolate from n=6 and
n=20 samples onto 436- and 96-position corpora, and `BENCH.md`'s own warning is *"per-position
variance is large and is the headline risk, not the median"*; (ii) the K=4 leg's 25%
censored fraction uses the 3,600 s cap as a **floor** — the true cost of running those
to completion is unmeasured.

Invocation, for the record — `scripts/rustport/bench_exact_solver.py`, which natively
batches a corpus by K and by mode:

```bash
/home/doctor/projects/carcassone/.venv/bin/python \
  /home/doctor/projects/carcassone/scripts/rustport/bench_exact_solver.py \
  --n 436 --workers 16 --k-clair --k-marg 3 \
  --budget 200000000 --tt-cap 0 --timeout-s 900 --as-limit-mb 6000 \
  --out /home/doctor/projects/carcassone/measurement/d3_tau_vs_k --tag k3_bulk
```

⚠️ **Neither `bench_exact_solver.py` nor `wsweep_exact_solver.py` takes a `--corpus`
path** — both are hard-wired to three committed corpus files via `pick_positions()`.
A genuinely new bulk corpus needs a small wrapper. And the τ computation itself — the
half of D3 that turns solved roots into a TAU_VS_K curve — **does not exist as a
script**; only the K≤2 τ values exist as prior results.

### 4.4 Recommendation

**Do not run. Close by annotation.** Add a D3 line to the roadmap stating: consumer
retired (CL-076 depth saturation + stillborn endgame net + CL-073/CL-039/CL-042
learned-value closure); never specced; priced at ≈44.5 core-h if it is ever revived.
Add a `docs/LEVER_INDEX.md` row keyed on `TAU_VS_K` / `MT-2` so the next reader's grep
finds the closure instead of the line item.

**What would revive it:** a new learner that needs solver-graded *sibling ranking* at
depth ≥3, or a deploy path at K≥3. Both are currently closed — the first by CL-073's
"prediction ≠ discrimination", the second by CL-076. Revival needs a mechanism
argument, not more compute.

---

## 5. Free actions (0 games, owner sign-off only)

Batched here so they can be done in one sitting:

1. Correct `measurement/level2/LEVEL2_LADDER_VERDICT.md`'s "Config note" — the rungs
   ran at UCT c = 3.0, not 1.5 (§2.2).
2. Correct the rung-`c` cell in the five F5 `fair_ruler_*` rows of
   `experiments/results.csv` (1.5 → 3.0), matching their own manifests. ⚠️ source of
   truth — owner decision.
3. Amend **CL-041** (clairvoyant denomination + pointer to CL-043) and re-word
   `governance/PRODUCTION.yaml`'s `notes` per flip-proposal §3.
4. Amend **CL-046** to cite the F5 post-fix rebase rows, and record that the pre-fix
   ladder read ~54 elo low at the 2752 rung (§3.4).
5. Flip **CL-026** to SUPERSEDED with a one-line reason (§3.2).
6. Banner `clean_eval/CLEAN_EVAL_AUDIT.md` with its clairvoyant denomination, keeping
   CL-013/014/015 untouched (§3.2).
7. Stamp `measurement/level2/LEVEL2_LADDER_VERDICT.md` — top rung superseded by CL-043.
8. Roadmap: mark D3 closed-by-annotation; add the `TAU_VS_K` / `MT-2` row to
   `docs/LEVER_INDEX.md`.
9. Add a `docs/LEVER_INDEX.md` row for **rung-vs-rung head-to-head in
   `eval_fair_puct.py`** — a NEVER-BUILT capability, named here so the next reader's
   grep finds it (§2.7).

---

## 6. Recommended ordering

1. **D1 annotation batch** — 0 games. Four HIGH rows plus CL-046 are currently
   quotable at clairvoyant denomination with no caveat attached; fixing that costs
   nothing and is the single highest value-per-unit-cost action in Track D.
2. **D2** — 16.1 core-h, ≈0.75 h wall, no build. The only Track-D item that buys new
   measurement, and it resolves a live 2.8× contradiction in the unit every ladder
   number is denominated in.
3. **D1 fair-ladder re-baseline** (`fixed_v1` + rust, 5 rungs) — 84.0 core-h, ≈3.8 h.
   Hold until the fair ladder is about to be quoted again; today's ruler grades an
   engine and a rules profile the champion no longer plays, which matters the moment
   E4 unparks and not before.
4. **D3** — do not run. Consumer retired before the item was ever specced; close it by
   annotation and record the ≈44.5 core-h price for a revival that needs a mechanism
   argument, not compute.
