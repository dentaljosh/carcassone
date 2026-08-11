# Async flywheel — taking heur@800 selection off the per-iter critical path

> **🕰️ STATUS: NEVER BUILT — AND ITS PREMISE HAS EXPIRED (stamped 2026-08-03).** This design optimises the
> *throughput* of the learned self-play flywheel, and the flywheel program is closed: the value route
> (CL-039/CL-042), capacity (CL-064), representation (CL-065), tabula-rasa (CL-066) and the mechanism
> (CL-073 — outcome prediction is not move discrimination) all read out negative, and the program-level
> synthesis is [FLYWHEEL_POSTMORTEM_2026-07-24.md](FLYWHEEL_POSTMORTEM_2026-07-24.md). The champion has
> been **classical** since 2026-07-07. ⇒ **do not build this without a live flywheel to accelerate.** The
> two hardware premises are also dead: the 5800x VRM box was replaced by the 5900XT (2026-06-09) and the
> Xeon is retired. What survives is the measured phase split, which is a reusable fact. *(Original status
> follows.)*
>
> **Status (as written 2026-06-10):** DESIGN ONLY. Not built, not approved. Needs Joshua sign-off + the 5800x VRM
> fix first (any W-retune underneath this is untrustworthy on a throttling box).
**Date:** 2026-06-10. **Supersedes** the BACKLOG stub "Train alongside self-play (async)"
(that was a generic v1-v6-era note; this is the developed version with the measured phase
split + the attempt-#2 philosophy-preservation).
**Author context:** came out of the 2026-06-09 flat-leaf deploy discussion — Joshua asked
"training is GPU-bound, gen+eval are CPU-bound, how hard to run them in parallel? this is
how we push into gigawatts of compute." Measuring the phase split repriced the lever.

---

## 1. The measured phase split (this is what reprices the lever)

Reconstructed from the live attempt-#2 run on the share
(`/mnt/c/carc-shared/flywheel_residual_attempt2`), iters 1–5, **pre-flat** (flat-leaf was
deployed at the iter5 boundary). Method, fully auditable from durable artifacts:
- **gen complete** = content of `done/gen$it` (the launcher writes `date` there, L235)
- **train complete** = mtime of `ckpt/iter$it.pt`
- **gen span** = first→last `*.npz` mtime in `iter${it}_data/iter_00/`
- **eval span** = `ckpt/iter$it.pt` mtime → first `*.npz` mtime of iter $((it+1)) (i.e.
  train-complete → next-gen-start = the selection + telemetry-gate window)

| Phase | Duration (avg, n=4 clean iters) | Share of cycle | Bound by | Idle resource |
|---|---|---|---|---|
| **gen** | ~22.1 min | **14.6%** | CPU-MCTS (3 boxes) + GPU priors | — |
| **train** | ~31.6 min | **20.8%** | GPU (5800x only) | all CPUs idle |
| **eval** | ~97.7 min | **64.4%** | CPU-MCTS heur@800 (3 boxes) | GPU ~idle |

Full cycle ~151.6 min/iter, dead steady: train per iter = 30m54s / 31m26s / 32m32s /
31m42s / 31m31s; gen ~22 min; eval (ckpt→next-gen) = 96.8 / 97.4 / 98.3 / 98.2 min.

**The headline:** the GPU sits idle ~78% of the cycle (gen+eval); the CPUs sit idle ~21%
(train). And the dominant phase is **eval (64%)** — the *in-loop* heur@800 selection gate —
not train (21%) or gen (15%). The naive "overlap GPU-train against CPU-phases" lever has a
ceiling of ~21% (the whole train phase). The prize is the eval barrier.

Why eval is so heavy: `selection` re-plays **both** new-vs-heur@800 **and**
best-vs-heur@800 every iter, n=200 paired each, on a fresh band (L256-257), plus the n=300
telemetry gate (L271). The heur@800 opponent runs 800 MCTS sims/move → it is the most
leaf-call-dense thing in the whole loop (~4× the leaf calls of net@200 gen — which is also
why flat's +8% lands hardest exactly here).

> Post-flat these shrink ~8% on the two CPU-MCTS phases (gen, eval); train (GPU) is
> untouched, so train's *share* rises slightly. Re-measure after the VRM fix.

---

## 2. Why heur@800 is in the critical path today

`gen(N+1)` warms from `best.pt` (L213), and `best.pt` is set by the selection verdict
(L262). So the loop has a true serial chain:

```
gen(N) → train(N) → selection(N) [heur@800] → best.pt → gen(N+1) → train(N+1) → ...
```

You cannot start `gen(N+1)` until the heur@800 verdict for iter N lands, because you do not
yet know what to warm from. That is the *only* reason the 64% phase blocks everything.

## 3. The distinction that unlocks it

Two things are conflated in `best.pt`:

- **warm-from** — operational: which checkpoint the next gen builds on. Slightly stale is
  harmless — the candidates are near-equal strength, and self-play from a near-best net is
  just *more good data*.
- **promotion authority** — scientific: which checkpoint is crowned champion and enters the
  lineage. This is the thing attempt #1 got fatally wrong (cheap in-lineage heur@200 proxy
  crowned iter1, discarded the stronger iter3), and the thing attempt #2 exists to protect.

**The trap to avoid:** "let the cheap proxy decide warm-from so we don't wait." That
reintroduces attempt #1's failure through the back door. The correct decoupling is the
opposite:

> **warm-from is ALWAYS the latest heur@800-CONFIRMED best. The pipeline never waits for the
> verdict — it keeps producing candidates from the confirmed best until heur@800 blesses a
> new one.** The "wasted" work while a verdict cooks is extra self-play from a confirmed-
> strong net on fresh decks — exactly the "distinct decks per iter" the philosophy wants.

## 4. The design — three async services instead of a barriered loop

Re-wiring of existing pieces, not a rewrite.

**(1) Producer pipeline (gen→train, continuous).** Loop forever: warm from
`confirmed_best.pt` → `_gen_launch` on a fresh deck band → `train_iter.py` → emit
`cand_<k>.pt` to a candidate queue, recording parent id + deck band. Always reads the
*current* `confirmed_best.pt`; never blocks on the judge. = existing gen+train with the eval
barrier removed.

**(2) heur@800 odometer (the authority, async, single-flight).** Repeat: pick the
*freshest* unjudged candidate → run the existing deck-paired `_run_eval` selection
(new-vs-`confirmed_best`, heur@800, fresh rotating band, `odo_paired_tally`) → append
`selection.csv`. If paired Δelo > margin → **atomically** promote (`confirmed_best.pt` ←
cand, append lineage, bump `best_id.txt`). Then pick the next *freshest* candidate,
**dropping any that piled up** (backpressure: judge always works on the latest; skipped
candidates' data still lives in the training window). = `_run_eval` + `_paired` + the
promote block, lifted out of the `for it` loop into its own process.

**(3) Telemetry gate (heur@200, async, zero authority).** Unchanged role — logged to
`telemetry_gate.csv` for discordance-watching; runs on spare capacity; never gates.

Plus the **sealed held-out confirmation** at the end — unchanged (L282-287).

## 5. Philosophy preservation (every attempt-#2 invariant)

| Invariant (launcher header L2-27) | Preserved? |
|---|---|
| Promotion decided ONLY by external, out-of-lineage, deck-paired heur@800 | ✅ The odometer is the sole promoter; the cheap proxy keeps zero crowning power. |
| warm-from never built on a proxy-crowned base (attempt #1's bug) | ✅ **Stronger** — `confirmed_best.pt` advances only on a heur@800 verdict; nothing un-blessed becomes a training base. |
| Distinct self-play decks per iter; rotating selection bands | ✅ Fresh gen band per candidate; fresh selection band per judgment. |
| Fixed-length run, no cheap-gate plateau-stop | ✅ Run to a candidate-count / wall-clock budget; the odometer never terminates the lineage. |
| All checkpoints retained; sealed confirmation always runs | ✅ Unchanged. |

**The one genuinely new wrinkle — candidate/parent skew:** a candidate may be judged against
a `confirmed_best` *newer* than the parent it trained from (if a promotion landed
mid-flight). This is mild off-policy lag, and it is **conservative**: the candidate must beat
a possibly-*stronger* champ to be promoted, so it can only make promotion *harder*, never
easier — it cannot inflate the lineage. Record it in the run's provenance; otherwise safe.

## 6. Honest throughput accounting (correcting an earlier overstatement)

Moving eval async does **not** make its work vanish. gen, the heur@800 judge, and the
telemetry gate all compete for the same 3 CPU boxes; eval is ~294 box-min/iter of CPU work
(heur@800, n=200 paired ×2) that still has to run somewhere.

- **On the current 3 boxes:** async packing reclaims mainly the train-shaped CPU hole (~31
  min/cycle of all-CPU-idle during GPU training) → **~20%**, NOT 3×. (An earlier "3×" claim
  in chat was a resourcing error — retracted here.)
- **The real multiple needs cutting eval WORK, not just moving it:**
  1. **Stop re-playing `best` from scratch each band** — keep a persistent reference record
     for the confirmed champion; extend it only when it changes (best is unchanged most
     iters → ~halves selection cost). Still deck-paired, still heur@800.
  2. **Accumulate-paired-until-significant** instead of fixed n=200 bursts — same heur@800
     authority, but stop early on clear verdicts, spend big only on close calls. Naturally
     fills idle eval capacity.
  3. Single-flight judge + drop-stale backpressure (don't judge every piled-up candidate).
- **The real "gigawatts" payoff is that async lets ADDED boxes pay off.** In the barriered
  loop a 4th box only helps the parallel phases and idles through train; in the async design
  it joins whichever pool is deepest → scaling goes from barrier-limited to ~linear.

## 7. Resource partition (avoids the gotcha the CPU/GPU framing hides)

gen and eval are **not** CPU-only — both hit the GPU for NN priors (policy-only net). Do
**not** co-locate a continuous learner with actors on the same GPU (train's big batches add
latency to prior-serving and stall the CPU-MCTS workers). Partition **by box**, which maps
onto the existing topology: **5800x = dedicated learner (GPU)**, **xeon + laptop = actors /
judges (CPU + their GPUs for priors)**. Bonus: this removes 5800x CPU-MCTS gen from the
bandwidth-bound DDR4 bus and lowers its heat (mild synergy with the VRM-throttle problem).

## 8. What actually changes in code (build sketch — when approved)

- Split `scripts/run_residual_flywheel_v2.sh`'s `for it` loop into 3 launchers sharing state
  via the share: `confirmed_best.pt` / `best_id.txt` / a `cand_queue/` dir / `selection.csv`.
  Promotion = atomic rename into `confirmed_best.pt` (writer is single-flight, so no lock
  needed beyond rename-atomicity).
- Producer: existing `_gen_launch` + `train_iter.py`, in a `while` over a candidate budget,
  always re-reading `confirmed_best.pt` before each gen.
- Odometer: existing `_run_eval` + `_paired` + the promote block (L256-267), in its own
  `while`, freshest-unjudged-candidate selection + drop-stale.
- Telemetry + sealed confirmation: lift verbatim.
- **No imported-code change to the leaf / net / MCTS** → cannot contaminate a running
  experiment; it's pure orchestration.

## 9. Gating

1. **Joshua approval** — this changes attempt #2's *operational* shape (not its philosophy);
   it is a deliberate run-design decision.
2. **VRM fix first** — the per-box W-retune (and the producer/judge box partition) needs
   trustworthy 5800x throughput numbers; worthless on a throttling box. Bundle the W-sweep
   with the post-VRM-fin clean 5800x re-sweep so we bench once.
3. **Measure first (already done for the split; redo post-flat)** — re-confirm the phase
   shares post-flat before sizing the effort.

See also: [BACKLOG.md](../BACKLOG.md) "Train alongside self-play (async)" (now a pointer
here); the attempt-#2 thesis in [scripts/run_residual_flywheel_v2.sh](../scripts/run_residual_flywheel_v2.sh) L2-27;
the flat-leaf deploy context in [docs/FLAT_LEAF_BENCH_DEPLOY_RUNBOOK_2026-06-09.md](FLAT_LEAF_BENCH_DEPLOY_RUNBOOK_2026-06-09.md).
