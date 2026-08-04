# Marginalized-solver frontier read — "is fair K=5/6 an option?"

> **STATUS: DRAFT — clean local re-run in flight (2026-08-04 overnight).** The laptop run
> below is confounded (W18 farm co-tenant 19:09→00:05) and serves as feasibility
> corroboration only; the verdict table comes from `marg_bench_20260804_local`
> (same positions — `pick_positions` seed 4242 — same W4 / 3600 s-cap protocol, on the
> deployment-relevant desktop box, exclusive tenant). Fill §3 and flip this banner on close-out.

**Question (Joshua 2026-08-03):** "sounds like we might as well try fair play k. is 6 an
option? only 5?" — i.e. can the *fair* (marginalized) exact solver run at K=5 or K=6 at
practical per-position cost? Production today: clairvoyant K≤4 eval / fair marginalized K≤2.
Context: the marginalized mode has **no alpha-beta** (it needs exact expectations over draws,
so no cutoffs) — the cost wall is the MODE, not the depth
([BENCH.md](BENCH.md), DECISIONS 2026-08-03 solver entry).

## 1. Design

- Cells: rust marginalized K=4 (n=20), K=5 (n=20), K=6 probe (n=1); corpus endgame
  positions (`pick_positions(k, 20, seed=4242)` — identical position sets across runs).
- Cap 3600 s/solve, W4, `bench_exact_solver.py --tag marg_frontier[_localclean]`.
- Decision rule (pre-stated): a K is "an option" for offline labeling if ≥~80% of positions
  solve under the 1 h cap with p90 wall compatible with batch labeling economics; it is an
  option for *play* only at orders of magnitude less — no K≥4 marg is a play candidate on
  current evidence.

## 2. Laptop run (2026-08-03 overnight) — CONFOUNDED, feasibility floor only

Confound: the W18 CL-074 component-remeasure farm shared the box from +4740 s (19:09) to
+22500 s (00:05). One K4 timeout (job 9, pre-farm) is clean-genuine; the other 3 K4 and all
12+ K5 timeouts are farm-era → **ambiguous (too slow, or starved?)**. Completions bias
one-sided (a contended completion would only be faster clean), so ok-counts are floors.
Also: the first launch ran against a stale wheel (no `solve_endgame`) → 41 instant
EXCEPTION rows in the jsonl; ignore `status=="EXCEPTION"` (the relaunch appended the real rows).

Interim (as of ~00:45, 36/41 real jobs done):

| cell | ok / done | timeouts | ok wall s (min/med/max) | rss_peak MB (med/max) |
|---|---|---|---|---|
| marg K4 | 16/20 | 4 (1 clean, 3 ambiguous) | 9 / 474 / 2662 | 187 / 1237 |
| marg K5 | 4/16 | 12 (all ambiguous) | 1486 / 2798 / 3226 | 637 / 637 |
| marg K6 probe | 0/0 | — | — | — |

Floor read: K4 marg ≥80% under 1 h **even contended**; K5 marg ≥25% contended, with clean
completions already hugging the cap (med ~47 min) — K5 looks marginal-at-best before the
clean run.

## 3. Clean local run (2026-08-04, desktop box) — THE VERDICT TABLE

*(fill on close-out from `/mnt/c/carc-shared/marg_bench_20260804_local/`)*

| cell | ok / n | timeouts | ok wall s (min/med/p90/max) | rss_peak MB (med/max) | nodes med |
|---|---|---|---|---|---|
| marg K4 | | | | | |
| marg K5 | | | | | |
| marg K6 probe | | | | | |

## 4. Verdict

*(fill: is K5 an option, is K6 an option, for what use — offline labeling vs play; fold
into DECISIONS + the LEVER_INDEX exact:K row; note the RSS column vs the W4-was-conservative
question — rust RSS is ~19× smaller than the python-era rules that motivated low W.)*

## 5. W sweep (teed up 2026-08-04) — NOT FIRED

The feasibility bench prices *one solve*. The follow-on question is throughput: **W4 was
inherited from the python-era RAM rules, and rust RSS is ~19× smaller** — so how many
workers should a labeling batch actually carry? Driver built and tested, not launched:
`scripts/rustport/wsweep_exact_solver.py` (+ `tests/test_wsweep_exact_solver.py`, 20 tests).
It runs the W points sequentially, one cell per point (the empty-flag trick suppresses
`bench_exact_solver.py`'s seven default cells), and emits `WSWEEP_SUMMARY.md` with
solved/h per W plus the house recommendation — **smallest W within 10% of peak, never the
argmax**, with an "extend before adopting" note if the peak lands on a ladder endpoint.

Guards, all fail-loud before any wall clock is spent: exclusive-tenant census (rc=2 — a
throughput bench beside another job measures the other job; this is exactly the confound
that voided §2), RAM `W × rss_max × 1.5 ≤ cap` (rc=3), and a `solve_endgame` capability
probe on `sys.executable` (rc=4 — the stale-wheel trap that produced §2's 41 instant
EXCEPTION rows). EXCEPTION rows in a point's jsonl abort the sweep (rc=5).

**Ready to fire (fill `--rss-max-mb` from §3's measured `rss_peak MB max` for the K being
swept):**

```bash
# local desktop box (5900XT, 16C/32T)
.venv/bin/python scripts/rustport/wsweep_exact_solver.py \
    --k 4 --mode marginalized --w-points 4 12 30 --n 20 --timeout-s 3600 \
    --ram-cap-mb 24000 --rss-max-mb <TO-BE-FILLED> \
    --out measurement/rust_solver_bench_20260803/wsweep_k4_local

# laptop (12 GB WSL VM)
.venv/bin/python scripts/rustport/wsweep_exact_solver.py \
    --k 4 --mode marginalized --w-points 4 8 16 --n 20 --timeout-s 3600 \
    --ram-cap-mb 11000 --rss-max-mb <TO-BE-FILLED> \
    --out measurement/rust_solver_bench_20260803/wsweep_k4_laptop
```

The RAM guard is what makes the ladders provisional: at §2's laptop-measured K4 max of
1237 MB, local W30 wants 55.7 GB (refused, rc=3) and the laptop tops out below W6. Those
ladders assume the clean run's max lands near ~500 MB (local W30 ⇒ ≤533 MB, laptop
W16 ⇒ ≤458 MB); if §3 comes in high, trim the top rung rather than raising the cap.

**Gating:** fires only after the frontier verdict AND a funded consumer of the labels
(Joshua's call); sweep the K tier the verdict supports.
