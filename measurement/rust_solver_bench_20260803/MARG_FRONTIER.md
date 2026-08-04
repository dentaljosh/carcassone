# Marginalized-solver frontier read — "is fair K=5/6 an option?"

> **STATUS: VERDICT IN (2026-08-04 morning). Fair K=5 is NOT a practical option (~26%
> under a 1 h cap, clean); fair K=4 is the offline-labeling frontier (75–80% under 1 h);
> no K≥4 marg is a play candidate. K6 probe re-running (WSL teardown ate the original).**
> §3 is the verdict table (clean desktop run, exclusive tenant); §2 is the confounded
> laptop run, kept as corroboration — notably the clean run REPRODUCES it, so the
> contention turned out not to bias the answer.

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

Final (run exited ~01:55; `render_marg_frontier.py` over the rows jsonl — 41 EXCEPTION
rows dropped):

| cell | ok / n | timeouts | ok wall s (min/med/p90/max) | rss_peak MB (med/max) | nodes med |
|---|---|---|---|---|---|
| marg K4 | 16/20 | 4 (1 clean, 3 ambiguous) | 9 / 474 / 1841 / 2662 | 187 / 1237 | 2,634,691 |
| marg K5 | 5/20 | 15 (all ambiguous) | 278 / 2380 / 3226 / 3226 | 637 / 637 | 9,831,203 |
| marg K6 probe | — | — | — | — | — |

Two closing footnotes: (a) **the K6 probe never re-ran after the wheel fix** — its only row
is the stale-wheel EXCEPTION, so the laptop contributes nothing on K6 (§3's local run covers
it); (b) **the driver crashed in its final aggregation** (JSONDecodeError) *after* writing
all 40 real rows — the rows jsonl is clean (0 bad lines) and authoritative; ignore the
run's summary JSON.

Floor read: K4 marg ≥80% under 1 h **even contended**; K5 marg ≥25% contended, with
completions hugging the cap (med ~40 min, max at the cap) — K5 looks marginal-at-best
before the clean run.

## 3. Clean local run (2026-08-04, desktop box) — THE VERDICT TABLE

Exclusive tenant, W4, 3600 s caps, same seeded positions as §2. Ran 00:02→06:39; the WSL
VM was torn down between 06:39 and 08:37 (host event; [reference_local_box_dirty_reboots]
pattern), killing the last two in-flight jobs: **one K5 position (censored — 19/20 stands)
and the K6 probe (re-fired standalone 08:58, 1 job, ≤1 h)**. 39/41 rows survived; jsonl
authoritative.

| cell | ok / n | timeouts | ok wall s (min/med/p90/max) | rss_peak MB (med/max) | nodes med |
|---|---|---|---|---|---|
| marg K4 | 15/20 | 5 | 8 / 457 / 2135 / 3101 | 183 / 1233 | 2,577,291 |
| marg K5 | 5/19 | 14 | 316 / 1706 / 1931 / 1931 | 633 / 633 | 9,831,203 |
| marg K6 probe | *(re-run in flight)* | | | | |

**The clean run reproduces the contended run** (K4 15/20 vs 16/20; K5 5/19 vs 5/20; ok
medians within noise). The §2 confound was real but not binding — the K5 timeouts were
"too slow", not "starved".

## 4. Verdict

- **Fair K=5: NOT an option.** ~26% of positions solve under a 1 h cap on the clean
  desktop run, and the completions themselves are expensive (med ~28 min). A usable cell
  would need multi-hour caps with an unmeasured tail — that is not labeling economics,
  it's a lottery. (Per-position node medians: K5 ≈ 3.8× K4.)
- **Fair K=6: no** (probe result pending, but it is bounded below by K5's 3.8× step;
  the 300 s desktop probe already put marg K5 strictly over its cap).
- **Fair K=4 is the frontier, with a caveat.** 75–80% under 1 h, ok-median ~8 min — but
  the pre-stated ≥~80% bar is only *grazed*, and the 20–25% timeout tail means any K4
  labeling campaign needs the F13-style K−1 fallback (conservative censoring) or bigger
  caps. For *play*, nothing changes: no K≥4 marg is remotely interactive; the in-game
  latch stays K≤2.
- **W4 was over-conservative for throughput** (the python-era RAM rules that motivated it
  are dead: rust rss_peak max is 1.23 GB, not 1–2 GB/worker × python's 19× multiplier),
  but W4 remains correct for *timing* cells — the two uses now have different W defaults
  (see §5; the RAM guard puts local W ≤ 12, laptop W ≤ 5 at the measured max).

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
    --k 4 --mode marginalized --w-points 4 8 12 --n 20 --timeout-s 3600 \
    --ram-cap-mb 24000 --rss-max-mb 1233 \
    --out measurement/rust_solver_bench_20260803/wsweep_k4_local

# laptop (12 GB WSL VM)
.venv/bin/python scripts/rustport/wsweep_exact_solver.py \
    --k 4 --mode marginalized --w-points 2 4 5 --n 20 --timeout-s 3600 \
    --ram-cap-mb 11000 --rss-max-mb 1233 \
    --out measurement/rust_solver_bench_20260803/wsweep_k4_laptop
```

Ladders finalized 2026-08-04 from §3's measured K4 `rss_peak` max (1233 MB): the guard
(`W × 1233 × 1.5 ≤ cap`) allows local W ≤ 12 and laptop W ≤ 5, so the original 4/12/30 and
4/8/16 ladders lost their top rungs (trimmed, caps NOT raised — the tail multiplier is
there because timeouts' RSS at kill was never observed). Both ladders now peak at their
RAM ceiling, so a peak at the top rung is expected and the "endpoint — extend" note does
not apply upward; it would mean "buy RAM", a Joshua call.

**Gating:** fires only after the frontier verdict AND a funded consumer of the labels
(Joshua's call); sweep the K tier the verdict supports.
