# The Eff Series — postmortems

> **STATUS: memorial, written 2026-07-31.** Eff Jensen and Eff Linus are CLOSED (verdicts final,
> canonical docs linked — numbers live there, not here). Eff Hans is CHARTERED, not started
> ([BACKLOG 2026-07-30](../BACKLOG.md)). House rule applies: point, don't copy — this file is
> the obituary column, not the coroner's report.

The naming convention: each branch is named for the party whose product we suspected of
taxing us. The verdict records who actually got effed.

## Eff Jensen (2026-07-28 → 07-30) — VERDICT: Jensen effed. ⚰️

**Charge:** the GPU batch-1 inference tax (a ~2.6 ms torch forward for a tiny net) was
strangling every latency-bound use of the learned components.

**Verdict:** the tax was real but it was *dispatch overhead, not compute* — and it is
deletable. The Apple Neural Engine runs the same forward at **0.42 ms, 100% on-NPU,
argmax-faithful** ([M5 bench](../measurement/m5_bench_20260728/M5_BENCH_READOUT_20260728.md)),
and the CoreML path hit its pre-registered reopen bar with room to spare
([EQTIME ANE readout](../measurement/classical_search/EQTIME_ANE_CELL_20260729_READOUT.md)).
Net-on-CPU was refuted as the escape route (5.8× vs a ≲3× bar) and the clean GPU b1 number
turned out to be 2.0 ms, not the contended 19.4
([bench batch](../measurement/EFFJENSEN_BENCH_BATCH_20260729.md)).

**The twist:** the branch's biggest strength outcome needed no GPU at all — the k-parallel
split (6.37× at k8×1376) took the strongest measured config from 91% of the clock to
tournament-legal, and the champion was promoted on it (CL-071,
[PRODUCTION.yaml](../governance/PRODUCTION.yaml)). The house escaped the GPU tax mostly by
not paying it. Jensen will be fine.

## Eff Linus (rounds 1–3, 2026-07-29 → 07-30) — VERDICT: exonerated on all counts. 🕊️

**Charge:** WSL2's virtualization was taxing our CPU-bound search, and bare metal would
set us free.

**Verdict:** refuted with the sign inverted, three times on three configurations. Native
Windows lost every cell on both boxes (round 1: 25% slower;
[round 2 laptop replication](../measurement/eff_linus/LAPTOP_REPLICATION_20260729.md):
1.06–1.19× affinity-controlled), and bare-metal Pop!_OS on the same silicon measured
**parity** (0.973–0.978×, inside the pre-registered band, identical chosen actions —
[round 3](../measurement/eff_linus/POPOS_ROUND3_20260730.md)). WSL2 is a free abstraction
under exactly the workload — sustained DRAM-latency-bound pointer chasing across a VM
boundary — where a hypervisor tax would have been least surprising. Props to Microsoft;
this VM held up under everything we threw at it (including a guest that once ballooned
vmmem to the .wslconfig cap, which is on us, not them).

**The one party convicted:** the *native Windows scheduler*, which parks a windowless
console process on E-cores (1.61× cost) and manufactured the round-2 "divergence." Linux
doesn't do this (pinned-vs-unpinned 0.5%). Standing rule: pin affinity before quoting any
native-Windows cell.

## The Anand thread — never a branch, always the antagonist. 🏆

No "Eff Anand" was ever declared, because AnandTech-style memory-hierarchy analysis is the
one party that kept being *right*. The DRAM-latency wall is the through-line of the whole
performance program: self-play is latency-bound (W optimum ≈14–16 regardless of core
count), the M5's faster cores bought almost nothing at deploy (1.74× clean —
[M5 bench](../measurement/m5_bench_20260728/M5_BENCH_READOUT_20260728.md)), training is
GPU-*launch*-latency-bound, and the flat-leaf rewrite that de-objectified the hot path was
the single biggest engine win precisely because it stopped chasing pointers through DRAM.
Every eff-branch verdict above is downstream of memory latency. Anand Lal Shimpi retired
from reviewing in 2014; the wall he taught a generation to measure is still undefeated
here.

## Eff Hans (chartered 2026-07-30) — pending. ⚖️

Rule-variant exploration to find a better game ([BACKLOG](../BACKLOG.md), AZ-chess-variants
precedent). Not started; queued behind Tier-1. Opening exhibit already in evidence: we ran
an accidental variant for the project's entire life — walled Carcassonne, the row-6
start-tile grid bound affecting 68% of games (2026-07-30 border diagnosis). Hans's game,
it turns out, is one thing we never actually tested.

## Scoreboard

| branch | named party | outcome |
|---|---|---|
| Eff Jensen | NVIDIA | **effed** — tax proven to be deletable dispatch overhead; escaped via ANE + pure-CPU k-parallel |
| Eff Linus | WSL2 (and by extension Microsoft) | **exonerated** — parity on three configurations; Windows scheduler convicted instead |
| (the Anand thread) | DRAM | **undefeated** — every verdict above is a footnote to memory latency |
| Eff Hans | Hans im Glück | **pending** — charges filed, trial not scheduled |
