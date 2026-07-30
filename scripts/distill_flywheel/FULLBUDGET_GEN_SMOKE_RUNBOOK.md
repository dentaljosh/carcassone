# Full-budget flywheel gen — pre-flight smoke runbook

> **STATUS: DRAFTED 2026-07-29 (late night), NOT LAUNCHED.** Prep for the lever-6
> resolution Joshua re-derived 2026-07-29 (LEVER_INDEX §7 "full-budget flywheel gen",
> standing-list item 15). Nothing here runs without his word; the smoke exists to turn
> the "~4–6 h/iter" guess into a schedulable number before any funding decision.

## What is being de-risked

One flywheel turn at **k4×688 = 2752** net-prior fair gen (vs the historical
`NET_SIMS=200` = 800 total, the ¼-budget confound). Two unknowns gate the ETA:

1. **Local orch throughput at net-heavy s688.** The only gen W-sweep is sims200-scoped
   (flat ~5,200 fwd/s W20→W44, latency-capped) and the one measured transfer attempt
   (W32 s200→s376, 2026-07-19) hit **queue collapse** — throughput fell 209→97
   batches/s. Expect the s688 optimum BELOW the s200 plateau.
2. **Whether the M5/ANE can join gen at all.** Zero gen history; classical W-ladder said
   W10 but net workers serialise on the ONE shared ANE (the ANE cell ran W6).

## Smoke design (per the pre-flight-smoke rule: production knobs, only game count differs)

**Cell grid — local (primary):** `gen_fair_distill.py`-lineage emitter, teacher block =
PRODUCTION.yaml fair profile except sims: `--k-dets 4 --sims 688`, curve125 leaf
(hash a36d2e15), exact_endgame K≤2, sighted 81ch/42 rep, `--batch-size 16`,
net-ckpt = `distill_strong_20260723/ckpt/iter_03.pt` (the CL-067 net — the operator
whose +35.7 motivates the lever). 10 games per W point, **W ∈ {12, 20, 28}**
(bracket below the s200 plateau per the collapse signature; extend down to W8 if 12
wins). Record: games/h effective, fwd/s, orch batches/s (the collapse tell), per-move ms.

**Cell grid — M5 (optional, only if the Air is granted):** CoreML backend
(`--net-backend coreml`, mlpackage sha 5883aa7f), **W ∈ {4, 6, 8}**, 6 games per point.

**Config traps (all from memory, all mandatory):**
- `OMP_NUM_THREADS=1` **to the orch server** (unpinned it owns the box at ~2574% CPU).
- orch `max_batch >= W` (k=1 blocking workers).
- `nice -n 19`, detached (`setsid … </dev/null &`), band/claim hygiene if sharded.
- ETA from the **mean over completed games**, never first completions (order-statistic trap).
- Air runs need `caffeinate -dimsu` + ~25% ETA headroom.

## Decision arithmetic the smoke feeds

- s/game(W*) × 300–450 games → gen wall per iter; + ~1 h train → **iter wall**.
- Naive linear prior: sims200 gen was ~10.7 s/game effective ⇒ ×3.44 ≈ 37 s/game
  ⇒ 300–450 games ≈ 3–4.5 h local-only. The smoke replaces this, it does not confirm it.
- If the turn is funded, the gate is pre-committed: new net vs anchor **AT DEPTH on a
  FRESH band** (CL-058 trigger b); a low-sims win alone is NOT a result (washout law).

## Cost of the smoke itself

~30 games local ≈ 20–40 min at plausible throughputs; M5 arm ~15 min. Total well under
an hour, no bands consumed (smoke games are not results-bearing; no results.csv rows).
