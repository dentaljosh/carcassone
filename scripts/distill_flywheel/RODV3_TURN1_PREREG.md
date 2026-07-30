# rodv3 turn 1 — PRE-REGISTRATION (Arm A only, FUNDED, gen launching 2026-07-29 night)

> **STATUS: PRE-REGISTERED 2026-07-29 ~23:50, ARM A FUNDED (gen + ONE train iteration).**
> Committed BEFORE the first gen game of the turn (house rule: prereg before results).
> Authorization (Joshua, 2026-07-29, verbatim): *"once we have w numbers for local, have an
> agent launch the flywheel with work stealing and add the other boxes as they become
> available"*. Derived from
> [RODV3_TURN1_PREREG_SKELETON.md](RODV3_TURN1_PREREG_SKELETON.md) (skeleton left untouched)
> and [FULLBUDGET_GEN_SMOKE_RUNBOOK.md](FULLBUDGET_GEN_SMOKE_RUNBOOK.md). Roadmap: G8.
>
> **NOT funded, needs an explicit human GO:** Arm B (value-unlock) and **the gate eval**
> (candidate vs parent at depth). When the train iteration lands this run STOPS and reports.
>
> ⚠️ **Launch history:** the first launch window was lost — the Claude session died at ~23:55
> before any cell fired (box did NOT reboot; share census showed prep intact, 0 claims, 0 npz).
> Resumed and launched 2026-07-30 00:31 with W\* filled in. No games were affected, and the
> prereg-before-results rule holds: `122e32e` predates the first gen game of the turn.

## The question (one variable)

Does the sighted-flywheel lineage grow when the ONLY change from the refuted 2026-07 run is
the gen budget: `NET_SIMS 200 → 688` (k4×200=800 → k4×688=2752)? The recorded ¼-budget
confound (HANDOFF ½-budget floor; recipe lever 6) is the thing under test; CL-067's
equal-sims +35.7 ± 12.3 supplies the missing premise (operator > teacher at 2752).

## Arm funded

**Arm A only: recipe-identical, full-budget gen.** All 7 recipe levers held; severed value
(frozen curve125 leaf); only the gen budget changes. Arm B (stage-3 value-unlock) is
explicitly NOT funded tonight — a clean resolution of the recorded confound beats a new
combination (skeleton's own ranking).

## Fixed choices (carried from the decided record — not relitigated at launch)

| Item | Value |
|---|---|
| Start / warm-from net | `/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt` (the CL-067 net) |
| Gen agent | `FairHeuristicPriorAgent` + net POLICY priors via carc-orch SHM (severed value loop: FROZEN champion leaf supplies search value) |
| Budget | `--k-dets 4 --sims 688` = **2752 sims/move**, exact endgame ON, `--exact-max-k 2` |
| Leaf | v2.9.2 Bmild cap8 **curve125**, runtime hash `6dfffd57051690f2` (= PRODUCTION.yaml `frozen_config_hash_meeple_k0`, the champ_env/distill dialect of `a36d2e15a3b3d71d`) |
| Representation | SIGHTED 81ch board / 42 scalars; orch **must** be started `--n-ch 81 --n-scalar 42` |
| Within-search leaf batching | `--batch-size 16` (as the smoke; the latency fix) |
| PUCT knobs | `--c-puct 1.5 --tau-p 5.0 --value-norm 15.0` |
| Policy target | pooled root visit counts (`agg_n` summed over k_dets); move played by pooled-Q argmax |
| Value target | game outcome, mover-POV `tanh((p0−p1)/15)` |

## Games, seeds, and where they land

- **300 net-gen games** (`NET_GAMES=300`) — the same per-iter game count the refuted stage-2
  run actually used for iters 04–20 (verified 2026-07-29: every one of those iter dirs holds
  exactly 300 npz, all in the net seed range). Holding 300 keeps the game count from being a
  second variable.
- **ZERO new champion games.** The champion-anchor share of the train mix comes entirely from
  the EXISTING full-budget champion games already on the share (below).
- **Gen seed band: `50000450000 .. 50000450299`** — stage-2's own seed formula
  (`SEED_BASE + it*100000 + NET_SEED_OFF`) applied to the distill_strong lineage
  (`SEED_BASE=50000000000`, `it=4`, `NET_SEED_OFF=50000`). Disjoint from that run's
  iters 00–03 (`…000000–…300599`), from the unused champ slot (`…400000–…400599`), and from
  the smoke's throwaway `9901…`/`9911…` ranges. Gen seeds are NOT eval deck bands — no
  `BAND_CLAIMS.txt` entry is consumed (the gate, when funded, will claim a fresh eval band).
- **Gen out dir (shared-claim pool, all boxes write here):**
  `/mnt/c/carc-shared/rodv3_turn1/iter_04/` (laptop view `/mnt/carc-shared/rodv3_turn1/iter_04/`).
  Run root `/mnt/c/carc-shared/rodv3_turn1/` also holds `ckpt/`, `logs/`, `done/` and
  `MANIFEST_PLAN.json` (this plan, machine-readable, written before launch).
- Work-stealing: `--shared-claim` with a per-box `--claim-host` (`5800x`, `laptop`, `m5`) so
  the pool is one queue across boxes and a dead box's claims are identifiable.

## Train — replicating the stage-2 trainer mechanics exactly

Stage-2's train step is `scripts/train_iter.py --output-root ROOT --iter N --window 12
--warm-from iter_(N−1)`, and `_select_buffer_files` globs `ROOT/iter_{N-11..N}/seed_*.npz`.
The structure is reproduced **exactly** by treating this turn as iter 4 of the distill_strong
lineage:

| | refuted stage-2 iter 4 | rodv3 turn 1 |
|---|---|---|
| root's iters 00–03 | 600 net-free CHAMPION games each | 600 net-free CHAMPION games each |
| new iter | 300 net-prior games @ k4×**200** | 300 net-prior games @ k4×**688** |
| window | 12 → globs iter_00..iter_04 | 12 → globs iter_00..iter_04 |
| warm-from | that lineage's iter_03 | `distill_strong_20260723/ckpt/iter_03.pt` |
| mix | 2400 champ : 300 net | 2400 champ : 300 net |

So the champion-anchor fraction, the window semantics, and the warm start are all
structurally identical; **the gen budget is the only difference.** The four champion iter
dirs are attached to the rodv3 root as symlinks (`rodv3_turn1/iter_00..iter_03` →
`distill_strong_20260723/iter_00..03`; drvfs symlink support verified 2026-07-29), so no data
is copied and the CL-067 run dir is not written to.

Trainer invocation (stage-2 defaults, unchanged):

```
CUDA_VISIBLE_DEVICES=0 nice -n 19 .venv/bin/python -u scripts/train_iter.py \
  --output-root /mnt/c/carc-shared/rodv3_turn1 --iter 4 --window 12 \
  --warm-from /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
  --output /mnt/c/carc-shared/rodv3_turn1/ckpt/iter_04.pt \
  --epochs 3 --batch-size 256 --value-loss-weight 1.5 --aux-weight 0 \
  --stage-local /tmp/rodv3_turn1_stage \
  --prov-value-target outcome --prov-selfplay-leaf v2_9_bmild_cap8_curve125 \
  --prov-seed-range 50000450000-50000450299 --prov-run-tag rodv3_turn1
```

Run under `systemd-run --user --scope -p MemoryHigh=16G -p MemoryMax=20G` if the staged
buffer looks large (WSL VM-teardown guard); `--stage-local` copies the window to WSL ext4
first, so the memmap read does not stream off drvfs.

## Fleet plan (W\* per box = the SETTLED smoke number, never the crude argmax)

| Box | Role | W\* | Status |
|---|---|---|---|
| LOCAL 5900XT (16C/32T, RTX 5060 Ti) | net-prior gen through carc-orch SHM (`rodv3t1`), `OMP_NUM_THREADS=1` on the SERVER, `--max-batch 32 ≥ W*` | **W\* = 16** | **LAUNCHED 2026-07-30 00:31** |
| LAPTOP (24T, 4070m) | joins the SAME shared-claim pool, own orch server | **pending** (its sweep is live; fall back to **W8** — the proven 2-box stage-2 laptop value — if the sweep yields no usable W\*) | joins after (a) its sweep finishes and the box is idle, (b) a **mandatory** git-bundle sync to local HEAD |
| APPLE M5 Air (ANE) | joins ONLY IF a real gen-capable CoreML path is demonstrated | n/a | **expected SKIP** — see below |

**M5 / Air gate:** the Air joins only if the M5 arm demonstrates a *gen* emitter with a CoreML
forward (not the eval-shaped harness). As of 23:45 no `M5_ANE_ARM.md` exists and the M5's only
demonstrated net path is the **eval** harness (`CL-067 EQTIME/ANE` cell, `.mlpackage`
`5883aa7f`). Porting `gen_fair_distill.py` to a CoreML backend is a source change — **forbidden
while cells run** — so the default is documented SKIP; if the Air does join, it needs
`caffeinate -dimsu` and ~25% ETA headroom (fanless throttle).

**W\* = 16 and the ETA are SETTLED** from
[measurement/fullbudget_gen_smoke_20260729/SMOKE_RESULTS.md](../../measurement/fullbudget_gen_smoke_20260729/SMOKE_RESULTS.md):
W16 is the throughput peak (5,367 examples/s on a phase-matched 215 s window) *and* the smallest
W inside the 5–10% tolerance band, so the settle-low rule picks it twice over; the knee is
bracketed on both sides (W12 is 19.8% below peak, so this is an interior optimum, not a ladder
endpoint). Independently re-derived from the raw `carc-orch` counters by this agent before the
smoke doc landed — same ranking, same winner (W12 ~3,700 / W16 ~5,400 / W20 ~5,020 / W28 ~5,270
examples/s; `batches/s` stable 213–239, i.e. **no queue collapse** anywhere on the ladder, which
was the specific hazard the smoke was hunting).

**ETA: ≈7.3 h local-only for 300 games** (87.6 s/game effective at W16, anchored on the ONE
complete cohort — W12's 12/12 wave, 1309.5 s, 109.1 s/game measured — and carried across W by
the measured throughput ratio; never a first-completions rate). Less when the laptop joins. Both
legs of the runbook's naive 3–4.5 h prior are refuted in the smoke doc: the sims200 baseline it
extrapolated from was itself an order-statistic artifact (real rate 23.0–23.7 s/game, not 10.7).

## Ops discipline for the unattended night

- Every cell `nice -n 19`, `setsid … </dev/null &` detached (Mac→Windows→WSL SIGHUP + WSL
  VM-teardown both kill tty-attached jobs; the harness's background flag is NOT enough).
- **`run_watchdog.sh` armed ON each box** next to its gen cell (session-independent: clears
  record-less claims, re-execs the resume-safe driver, 5-relaunch budget) —
  `scripts/measurement_infra/run_watchdog.sh '<out>/seed_*.npz' 300 '<worker pattern>' <log>
  -- <relaunch cmd>`. The 2026-07-28 lesson: the session heartbeat dies with the session.
- Orphaned-claim hygiene: after ANY kill of a `--shared-claim` cell, immediately
  `for c in DIR/*.claim; do [ -f "${c%.claim}.npz" ] || rm -f "$c"; done`. Self-play fails
  CLOSED (loud partial-data refusal), but a stranded claim stalls the pool at `300 − n_killed`.
- Killing an mp main does NOT reap its spawn workers — intervene by EXACT pid.
- LOCAL box has a dirty-reboot history under sustained load: on any post-reboot wake, census,
  clear stranded claims, relaunch; `--shared-claim` makes the completed games lossless.
- Share prefix differs by box: `/mnt/c/carc-shared` locally, `/mnt/carc-shared` inside ssh.
- Remote commands: `ssh laptop-wsl 'bash -s' < script.sh` with `cd` on line 1 (inline `cd` is
  stripped in transit); a detached launch returning rc=124 from `timeout` means **LAUNCHED** —
  never retry.

## Gate (pre-committed 2026-07-29, before any smoke result — UNCHANGED, AWAITING GO)

- **Primary: candidate(turn 1) vs its OWN PARENT (the CL-067 net) at DEPTH (k4×688), n=400
  deck-paired, FRESH band** (claim via share manifests + `BAND_CLAIMS.txt`). POC bar =
  positive derivative, NOT champion supremacy. Branches:
  - **ALIVE:** elo ≥ +2σ AND margin sign agrees → fund turn 2 (same prereg, next band).
  - **DEAD:** both statistics ≤ 0 or sign-split at |z|<1 → lever 6 resolved NEGATIVE; the
    ¼-budget confound was not the limiter; lever 1 (value sever) becomes the last suspect;
    STOP (no turn 2 without a new argument).
  - **AMBIGUOUS:** anything else → ONE extension of the same cell (n→800), then verdict.
- Secondary (context, not gates): vs rod_v2 iter_02 anchor at k4×688; a low-sims cell ONLY as
  a diagnostic, never citable as growth (washout law).
- **The gate is NOT funded tonight.** No eval games run until Joshua says GO.

## PRE-GATE AMENDMENT (2026-07-30 ~01:00 — before any gate game, blind to all strength outcomes; prompted by [BURIED_CAVEATS_AUDIT_20260730.md](../../docs/reviews/BURIED_CAVEATS_AUDIT_20260730.md) F1)

**Pre-registration status of this amendment.** It is written while turn-1 gen is running and
**before a single gate game exists**. Gen shards carry no candidate-vs-parent strength
information — they are self-play trajectories from the PARENT net's own priors, produced before
the candidate exists — so nothing observable at this moment could have informed the re-scoping
below. It is therefore pre-registered with respect to the gate.

**(a) The fact.** The parent net (CL-067 `distill_strong_20260723/ckpt/iter_03.pt`) was distilled
from a corpus generated by the **net-free champion at k8×1376 = 11008 sims/move** — verified
directly in the corpus manifest (`/mnt/c/carc-shared/distill_strong_20260723/iter_03/manifest.json`
→ `config.teacher.{k_dets: 8, sims_per_det: 1376, total_budget_per_move: 11008}`,
`config.net_mode: "net-free (champion)"`; all four of that root's iters 00–03 are the same
net-free champion stream). Turn-1 gen runs at **k4×688 = 2752**, i.e. **¼ of the budget of the
corpus that trained the parent.** This is the *same relative-budget shortfall* lever 6 was
raised to test, reproduced one level up — because the champion's deploy budget quadrupled on
promotion day (CL-071, 2026-07-29, k4×688 → k8×1376).

> ⚠️ **One cited figure is corrected here rather than carried.** The audit's framing attributed
> "**+14.1 elo teacher over its own distillation**" to CL-067's counterevidence field. That is a
> misreading and it is **not** used above. CL-067's `+14.1 ± 24.7 (z = 0.57)` is the elo
> **difference between its two candidate-vs-champion cells** (gate band 52e9 `+42.8` vs
> confirmation band 56e9 `+28.7`), which the row itself reads as winner's-curse shrinkage, *not*
> as reversal — it is in `best_evidence`, not `counterevidence`, and it says nothing about the
> teacher. CL-067's `counterevidence` field is entirely about **deployability/cost** (4.24×
> unloaded prefix ms/move at W=2). In fact **the distilled net has never been measured against
> its own k8×1376 corpus teacher** — no `results.csv` row contains that pair. The amendment
> stands on the manifest fact alone, which is sufficient and is *stronger* stated honestly: the
> teacher-over-distillation gap is **UNMEASURED**, not "+14.1".

**(b) DEAD branch — RE-SCOPED (narrowed).** If the gate reads DEAD (both statistics ≤ 0, or a
sign split at |z| < 1), the claim it licenses is **only**:

> *"Flywheel gen at 2752 sims/move produced no measurable growth over the parent."*

It may **NOT** be reported as "lever 6 resolved NEGATIVE" or "the ¼-budget confound was not the
limiter" in general, because a second, uncontrolled ¼-budget gap — gen at 2752 against a corpus
built at 11008 — is present in exactly the arm being tested. **The surviving discriminator is gen
at the corpus-teacher budget k8×1376 = 11008.** Priced, NOT funded: ~4× tonight's cost ⇒ ~29 h
local-only at W\*=16 (300 games), ~20 h fleet — its own funding decision, and if that also reads
null, lever 6 is resolvable in general.

**(c) ALIVE branch — UNCHANGED, and strictly strengthened by this reading.** Growth measured
*despite* training on gen data a factor of 4 below the parent's own corpus budget is a **stronger**
positive than the original framing assumed: the improvement operator would have overcome data
weaker than what produced it. No re-scoping needed.

**(d) AMBIGUOUS branch — UNCHANGED** (one extension of the same cell, n → 800, then verdict).

Nothing in the original **Gate** section above is struck or edited; this section only narrows what
a DEAD read may be said to have shown.

## Close-out obligations

For tonight's funded scope: `measurement/rodv3_turn1/GEN_TRAIN_REPORT.md` (games by box,
wall-clock by stage, W\* per box, incidents, ckpt path + sha), one STATUS line under
"Right now", roadmap G8 STATE clause flipped. **No `results.csv` row and no `PRODUCTION.yaml`
touch** — gen+train alone produce no strength claim; the results row belongs to the gate.
When the gate is funded and lands: results.csv row · DECISIONS entry · this doc's banner ·
CLAIM_REGISTRY (new CL id) · STATUS top block · roadmap G8 — plus, if it is a null, its
confound indexed in `docs/LEVER_INDEX.md` the same day.
