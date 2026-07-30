# Full-budget flywheel gen — pre-flight throughput smoke (M5 AIR / ANE arm)

**Status: RESULTS — COMPLETE (2026-07-29 night → 2026-07-30 morning).** Third arm of
[`scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md`](../../scripts/distill_flywheel/FULLBUDGET_GEN_SMOKE_RUNBOOK.md),
alongside [`SMOKE_RESULTS.md`](SMOKE_RESULTS.md) (local 5900XT) and
[`LAPTOP_ARM.md`](LAPTOP_ARM.md). Joshua-authorized. **Throwaway games** — no
`results.csv` row, no deck band consumed, no promotion,
[`governance/PRODUCTION.yaml`](../../governance/PRODUCTION.yaml) untouched. Purpose:
price the fanless MacBook Air as a *gen* node at full budget k4×688, with the policy
forward on the ANE via CoreML.

## Verdict

**W\* = 4, and the Air is worth including in the gen fleet.** At W4 the Air turns in
**119.8 s/game = 30.1 games/h** on the real gen emitter. Against the other two arms
(local ≈41.1, laptop 45.6 games/h, both at W16) the Air adds **+35% fleet throughput**,
cutting a 300-game iteration from 3.46 h → **2.57 h** and a 450-game one from
5.19 h → **3.85 h**.

**The W\* is genuinely low and genuinely bracketed** — throughput *falls* on both sides
of W4. This is the opposite of every other box in the fleet (both settled W16) and it is
the ANE's doing, not the CPU's: the Air runs its best gen at 4 workers on a 10-core
machine.

## 1. The ladder — real gen emitter, CoreML/ANE

`gen_fair_distill.py` self-play, `--net-backend coreml`, `--batch-size 1`,
k_dets 4 × sims 688 = 2752 sims/move, `--sighted`, exact endgame K≤2, leaf
`6dfffd57051690f2`. `games = W` (one full concurrent round per point) so every worker is
busy for the whole measurement window. `s/game` is the emitter's own effective figure
(wall ÷ games), which **includes** per-worker CoreML model load — in a 300–450-game run
that startup amortizes away, so these numbers are mildly conservative.

| round | W | games | wall s | **s/game** | **games/h** | % of peak |
|---|---|---|---|---|---|---|
| refine | 2 | 2 | 361 | 180.5 | 19.9 | 66.3% |
| refine | 3 | 3 | 435 | 145.0 | 24.8 | 82.6% |
| crude | **4** | 4 | 479 | **119.8** | **30.1** | **100%** |
| crude | 6 | 6 | 837 | 139.5 | 25.8 | 85.8% |
| crude | 8 | 8 | 1116 | 139.5 | 25.8 | 85.8% |

**Settlement.** Peak = 30.1 games/h at W4. Applying the house rule (*smallest W within
~5–10% of peak*): W3 is at 82.6% and W2 at 66.3%, both outside the band; W6/W8 sit at
85.8%, also outside. **W4 is the unique member of both the 5% and the 10% band**, so
W\* = 4 with no judgement call required. Unlike a ladder endpoint, this peak is
**bracketed on both sides** — the crude round alone (W4/6/8) would have left W4 sitting
on the bracket floor and unsettled, which is exactly what the refinement round was for.

**The saturation signature.** W6 and W8 return *identical* 139.5 s/game. Total
worker-seconds per game climbs 361 → 435 → 479 → 837 → 1116: past W4 each added worker
buys **exactly zero** aggregate throughput and simply divides the same device more ways.
The ANE is one shared accelerator that serialises requests across processes, and the
emitter's own banner says so at launch (*"the ANE is ONE shared device — W workers do NOT
give W× forward throughput"*). W4 is where the device fills without the contention
penalty yet dominating.

## 2. The methodological finding: the eval-shaped proxy gets W\* WRONG

Before the real emitter was available on the Air I measured a proxy — the CL-067
harness ([`eval_fair_puct.py`](../../scripts/classical_search/eval_fair_puct.py)),
`--info fair-netprior --opponent fair-champion`, both seats at k4×688, same verified
`.mlpackage`, same box, same night. It is the configuration the runbook's M5 line
contemplates, and **it is not a safe stand-in for gen.**

| W | real gen emitter | eval proxy | proxy optimism |
|---|---|---|---|
| 4 | **30.1** (peak) | 35.0 | 1.17× |
| 6 | 25.8 | 37.2 | 1.44× |
| 8 | 25.8 | 38.5 (proxy peak) | 1.49× |

The proxy does not merely read high — **it points the wrong way.** It says throughput is
still climbing at W8 (and by the house sweep convention would send you to W10); the real
emitter says W4, with W6/W8 14% *worse*.

**Mechanism.** In the proxy only the *candidate* seat runs the net; the `fair-champion`
opponent is net-free heuristic search, and the harness has no CoreML plumbing on the
opponent side at all. So the proxy puts **half** the ANE request rate on the device that
real self-play does. Its per-side cost split makes this explicit — the ANE seat is 62.6%
of prefix cost at W4, and per-sim costs inflate steeply with W (ANE 1.1884 → 1.7057 →
2.1009 ms/sim; search 0.7113 → 1.0390 → 1.4655 across W4/6/8). Double the ANE demand and
the plateau arrives at half the W.

Worth recording precisely because it *nearly* worked: the self-play correction I derived
from the proxy, `2·cand/(cand+opp)` = 1.251× at W4, projected **30.3 games/h** against a
measured **30.1** — 0.7% error. The correction factor was right; what it structurally
could not capture was the **W-dependence** of the contention it was correcting for. A
single-W projection from this proxy is defensible; a W-sweep from it is not.

**Standing lesson:** on a shared-accelerator box, tune W on the emitter you will actually
run. A half-load proxy reproduces the level and inverts the gradient.

## 3. Incident timeline — fully resolved, benign

An earlier hand-off reported that "the W6 cell died at 01:41:58, SIGHUP'd when its ssh
channel closed" and that only a partial W6 cohort survived. **The disk does not support
this, and no data was lost.**

| time (EDT) | event |
|---|---|
| Jul 29 23:22:34 | proxy sweep driver starts (after an `rc=127` false start — see §5) |
| Jul 29 23:29:25 | proxy W4 ends `rc=0`, 4/4 records |
| Jul 29 23:39:05 | proxy W6 ends `rc=0`, 6/6 records |
| Jul 29 23:51:34 | proxy W8 ends `rc=0`, 8/8 records; `DRIVER DONE` |
| Jul 30 01:01:26 | **gen** W-sweep starts (separate arm, `~/rodv3_air/`) |
| Jul 30 01:09:25 | gen W4 ends `rc=0`, wall 479 s, 4 npz, `0 skipped` |
| Jul 30 01:23:22 | gen W6 ends `rc=0`, wall 837 s, 6 npz, `0 skipped` |
| Jul 30 01:41:58 | gen W8 ends `rc=0`, wall 1116 s, 8 npz; `=== AIR gen W mini-sweep END ===` |
| Jul 30 09:16:40 | refinement W2/W3 launched under the verified-detach protocol |
| Jul 30 13:29:56 UTC | refinement `DONE`, both cells `rc=0` |

Three corrections to the record:

1. **Nothing died.** `01:41:58` is the sweep's own normal `END` stamp, not a death. All
   three gen points report `rc=0` and `0 skipped`; W6 completed 6/6 at 01:23. There is no
   partial cohort, so the completed-games-only rule never bites and **no W6/W8 completion
   re-run is needed** — that specific proposal is moot.
2. **Two arms were conflated.** `119.75 s/game / 30.1 games/h` is the **gen** sweep in
   `~/rodv3_air/` (its own repo checkout, run by another session). My arm is the proxy in
   `~/carc_gen_smoke_20260729`, which read 102.8 s/game / 35.0 games/h at W4. I did not
   port the gen emitter to CoreML — the brief forbade it, and `~/carc-eqtime-ane/repo` is
   git-clean; the port lives in `~/rodv3_air/repo`.
3. **The "~25% optimistic" figure mixed bases.** It compared my *startup-excluded
   steady-state* 37.9 against the gen *startup-included effective* 30.1. Like-for-like at
   W4 the proxy is **1.17×** optimistic (35.0 vs 30.1); the honest indictment of the proxy
   is the direction error in §2, not the level.

## 4. Fleet read and recommendation

| fleet | games/h | 300 games | 450 games |
|---|---|---|---|
| local + laptop | 86.7 | 3.46 h | 5.19 h |
| **+ Air (W4)** | **116.8** | **2.57 h** | **3.85 h** |

**Include the Air.** It contributes ~26% of a three-box fleet's gen rate for zero
marginal hardware cost, and at W4 it uses 4 of 10 cores — it is ANE-bound, not
CPU-bound, so it stays usable while it generates.

**Do not fund a W-refinement extension.** W\* = 4 is bracketed on both sides and is the
unique member of the settle band; the ladder is settled. The one genuinely open lever is
**batching**: the `.mlpackage` is a fixed batch-1 artifact, so this arm cannot use the
within-search leaf batching the other two arms run at `--batch-size 16`. A batch-N
re-export is the only plausible route to materially more Air throughput, and it is a
fresh decision with its own export + fidelity-gate cost — not a W question.

Two caveats that bound the above:

- **Thermals.** Per-game cost is stable within each point (proxy W4 games ran
  375/378/407/360 s; W8 711–747 s), so no throttle collapse is visible at these
  durations. But every cell here is ≤ 19 min. The CL-067 400-game run took **9.10 h vs
  7.37 h predicted**, and that overrun is partly thermal. **A multi-hour Air gen shift
  should be priced with the runbook's ~25% headroom, not at 30.1 games/h flat.**
- **Contention with interactive use.** These numbers are for an otherwise-idle Air.

## 5. Provenance and exact commands

| item | value |
|---|---|
| CoreML artifact | `cl067_iter03_policy_fp16.mlpackage`, `sha256_tree` **`5883aa7f44e59c0947e0a44b3cbb3ef7f51b6a3b0717e3858c6d504358d0da46`** |
| fidelity precondition | **re-verified on the Air, MATCH** — recomputed with the project's own recipe ([`export_cl067_coreml.py::sha256_tree`](../../scripts/m5_bench/export_cl067_coreml.py)) against the sidecar manifest. **Not re-exported.** |
| source checkpoint | `iter_03.pt` sha256 `6e2679908d79a76c…` (the CL-067 net) |
| leaf | curve125, runtime hash `6dfffd57051690f2` (gen dialect) = `a36d2e15a3b3d71d` (harness dialect) — same leaf, two registered dialects, see [`SMOKE_RESULTS.md`](SMOKE_RESULTS.md) |
| budget | k_dets 4 × sims 688 = **2752 sims/move**, exact endgame ON, `exact_max_k=2`, `--batch-size 1` |
| rows/game | 144 (matches both other arms) |
| box | Apple M5 MacBook Air, 10-core (4P+6E), 32 GB, macOS 26 |
| venv | `~/m5_bench_20260728/.venv/bin/python` + `PYTHONPATH=<repo>/src:<repo>/engine` |
| seeds | throwaway `9902402000` (W2), `9902403000` (W3); crude round `99024[0468]xxx`; proxy `99500000000`. No corpus band touched. |

Refinement cell (the crude round is identical with `--workers 4|6|8`, `--games` = W):

```bash
nice -n 19 "$V" scripts/distill_flywheel/gen_fair_distill.py \
    --games "$N" --k-dets 4 --sims 688 \
    --sighted \
    --net-backend coreml \
    --coreml-mlpackage ~/carc-eqtime-ane/coreml/cl067_iter03_policy_fp16.mlpackage \
    --coreml-compute-units CPU_AND_NE \
    --batch-size 1 \
    --workers "$W" --seed-start "$SEED" --out "$OUT/w$W"
```

`--sighted` is mandatory and fails loud without it (the net is an 81ch/42-scalar sighted
net; the recorded obs must match). `CPU_AND_NE` — not `ALL` — or CoreML may place the
graph on the GPU, a different device from the one 0.42 ms was measured on.

## 6. Method notes and deviations

- **`games = W`, one concurrent round per point.** Same choice the other two arms made
  independently. With `games > W` the tail of the wave runs at falling occupancy; with
  `games < W` idle workers make it a latency measurement.
- **Refinement cells run unpaired.** `--paired` rejects an odd `--n`, and W3 needs one.
  This is a throughput measurement, not a strength one, so pairing buys nothing; each
  cell got its own scratch sub-band so no cell reuses another's decks.
- **Verified-detach protocol** (for the refinement launch): `nohup caffeinate -dimsu bash
  driver.sh & disown`, then confirmed **from a separate ssh session** that the driver had
  `PPID=1` (reparented to launchd) and that `pmset -g assertions` showed the caffeinate
  holding both `PreventUserIdleSystemSleep` and `PreventSystemSleep`. Both cells then ran
  to completion across the session boundary.
- **`rc=127` false start.** The first crude-round launch exited 127 on all three points:
  [`EQTIME_ANE_CELL_RUNBOOK.md`](../../scripts/m5_bench/EQTIME_ANE_CELL_RUNBOOK.md) §1.2
  documents a venv at `~/carc-eqtime-ane/.venv` **which does not exist**. The venv of
  record is `~/m5_bench_20260728/.venv`, read off the real `cell_launch.sh` on the box.
  Worth fixing in that runbook.
- **Counting workers on macOS.** `pgrep -f eval_fair_puct` returns **1** — spawn workers
  do not carry the script name in argv. Count `pgrep -f "<venv>/bin/python"` instead;
  W4 verified at 4 busy workers / 293.7% aggregate CPU.
- **The Air naps aggressively** (`pmset sleep 1`) and `caffeinate` exits with its child,
  so the box sleeps the moment a run finishes. Waking it over tailscale took ~20 min of
  continuous ssh + TCP-knock pressure on 2026-07-29. Harvest promptly or keep an
  assertion pinned.

## 7. Artifacts

On the Air: `~/carc_gen_refine_20260730/` (W2/W3 refinement, 5 npz + logs),
`~/rodv3_air/wsweep/` (crude gen ladder, 18 npz + `sweep.log`),
`~/carc_gen_smoke_20260729/` (the eval proxy, 18 per-game JSON records + summaries).
All games are throwaway; nothing was staged to the share or to `experiments/results.csv`.
