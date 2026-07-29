# Apple M5 — champion single-stream latency + CoreML/ANE net-forward probe

**STATUS: MEASURED / COMPLETE 2026-07-28. Latency only — NO strength claim, no games played,
`governance/PRODUCTION.yaml` untouched, no lever proposed or adopted.** Executed the run book in
[`scripts/m5_bench/README_M5.md`](../../scripts/m5_bench/README_M5.md) on Joshua's Apple M5 while the
CL-067 equal-wall-clock gate owned local + laptop. Every number below is read off a JSON in this
directory; none is transcribed from terminal scrollback.

Package built by `scripts/m5_bench/build_bundle.py` at git `0d9c479` (`MANIFEST.json` on the share).
Raw JSON + logs: this directory, and `/mnt/c/carc-shared/m5_bench_20260728/results/m5/`.

---

## 0. Headline

| | |
|---|---|
| M5, champion of record, deploy budget k4×688 (2752 sims/move) | **1.576 s/move** |
| M5 vs the LOADED 5900XT, k1×32 (the only rung both boxes ran) | **2.85× faster** — caveat in §3 |
| M5 vs Pixel 9 Pro at k4×688 (1.7 s/move, `ANDROID_WALLCLOCK_MEMO_20260728`) | **0.93×** — a wash |
| CL-067 net, batch-1 forward, fp16 on the Neural Engine | **0.420 ms** vs 2.598 ms torch-CPU = **6.19×** |
| ANE partitioning | **all 52 executable ops on the ANE, zero fallback** |

The unified-memory hypothesis as posed in the run book ("a DRAM-latency-bound pointer-chasing leaf is
the shape a unified-memory part could win on") is **not settled by this run** — the only rung with a
matched local measurement was taken on a contended box (§3). What *is* settled: a 10-core M5 running
the production champion single-stream lands within 8% of a Pixel 9 Pro at the same budget.

---

## 1. Champion ladder — Apple M5

Source: [`bench_champion_Mac_20260728T225752.json`](bench_champion_Mac_20260728T225752.json)
(`tag="m5 idle full ladder repeat3"`, `--repeat 3`, 60 positions × 3 passes, seed 101, `verify=True`).

**Machine** (from the JSON's `machine` block): Apple M5, `macOS-26.5.2-arm64-arm-64bit`, 10 cores,
32.0 GiB, CPython 3.12.13. Box otherwise idle.

**`cython.leaf_active` = `true`, `cython.leaf_path` = `"cython"`** — the native arm64 extensions built
from the bundled `.pyx` on the Mac itself (`cython_build_m5.log`). This is the mandatory reporting flag:
the local reference is also `leaf_active: true`, so the 4.5× Cython-vs-pure-Python confound is
controlled and the two boxes are comparable.

**Champion identity** (JSON `champion` + `agent_manifest`): `puct_priors_v29_bmild_cap8`, leaf hashes
`a36d2e15a3b3d71d` / `6dfffd57051690f2` / `158f17ff76adaa02` — all three dialects match
`governance/PRODUCTION.yaml`, checked at construction by `verify=True`.

| budget | sims/move | mean s/move | p50 | p90 | min | max | n | exact_latches | wall s |
|---|---|---|---|---|---|---|---|---|---|
| k1×32 | 32 | **0.0135** | 0.0135 | 0.0183 | 0.0041 | 0.0238 | 178 | 0 | 2.7 |
| k4×172 | 688 | **0.3705** | 0.3618 | 0.4884 | 0.1990 | 0.6185 | 178 | 0 | 66.9 |
| k4×344 | 1376 | **0.7937** | 0.7662 | 1.0377 | 0.4374 | 1.3775 | 178 | 0 | 142.9 |
| k4×688 | 2752 | **1.5756** | 1.5224 | 1.9769 | 0.9265 | 2.6228 | 178 | 0 | 283.4 |

`exact_latches: 0` on every rung, as the corpus design requires — no position fell through to the
endgame solver, so these are PIMC-search costs throughout.

### By phase

| budget | meeples mean | tiles mean | meeple/tile |
|---|---|---|---|
| k1×32 | 0.0146 | 0.0124 | 1.18× |
| k4×172 | 0.3741 | 0.3668 | 1.02× |
| k4×344 | 0.8276 | 0.7599 | 1.09× |
| k4×688 | 1.6596 | 1.4916 | 1.11× |

The meeple half costs more than the tile half at every rung despite choosing among 2–5 actions instead
of 16–30 — the same sign `ANDROID_WALLCLOCK_MEMO_20260728` §2 found on the phone and the local
reference found at k1×32. Third independent box, same direction. Note the *magnitude* is much smaller
here (1.02–1.18×) than the memo's phone figure; this is a different budget and a different device, so
the ratio is not directly transferable, but the ordering is robust.

### Cost per sim

| budget | µs per sim |
|---|---|
| k1×32 | 422.7 |
| k4×172 | 538.4 |
| k4×344 | 576.8 |
| k4×688 | 572.5 |

Flat from k4×344 upward — the ladder is essentially linear in total sims at deploy width, which is what
the run book's extrapolation assumed. The cheaper k1×32 rung is a different shape (1 determinization,
shallow tree), not a discount available at the deploy budget.

---

## 2. ANE / CoreML net-forward probe

Checkpoint: CL-067 `distill_iter_03.pt`, sha256
`6e2679908d79a76cd2d66789d992676a5bfa85946a1543968982b308873751a1` — re-verified on the Mac after
transfer against `MANIFEST.json`. 7,509,167 params, 96×6, `n_input_channels` 81, `n_scalar_features` 42,
`value_global_pool` true. torch 2.13.0, coremltools 9.0, batch 1, 100 iterations, 10 warmup,
`torch.set_num_threads(1)`.

Sources: [`bench_ane_Mac_20260728T230704.json`](bench_ane_Mac_20260728T230704.json) (fp16),
[`bench_ane_Mac_20260728T230739.json`](bench_ane_Mac_20260728T230739.json) (fp32),
[`ane_coverage_Mac_20260728T230834.json`](ane_coverage_Mac_20260728T230834.json) (fp16 coverage +
agreement), [`ane_coverage_Mac_20260728T231003.json`](ane_coverage_Mac_20260728T231003.json) (fp32).

### Latency (ms, batch-1)

| backend | fp16 mean | fp16 p50 | fp16 p90 | fp32 mean | fp32 p50 | fp32 p90 |
|---|---|---|---|---|---|---|
| torch CPU, 1 thread | 2.598 | 2.601 | 2.633 | 2.615 | 2.595 | 2.699 |
| CoreML `CPU_ONLY` | 1.013 | 1.011 | 1.024 | 1.619 | 1.608 | 1.681 |
| CoreML `CPU_AND_NE` | **0.420** | 0.417 | 0.429 | 1.622 | 1.613 | 1.671 |
| CoreML `ALL` | 0.416 | 0.413 | 0.431 | 1.383 | 1.129 | 2.091 |

* fp16 ANE vs torch CPU: **6.19×**. fp16 ANE vs CoreML CPU: **2.41×**.
* fp32 `CPU_AND_NE` / `CPU_ONLY` = **1.002×** — no gain at all.
* fp32 `ALL` has a p50 of 1.129 against a p90 of 2.091: bimodal, i.e. GPU dispatch that sometimes wins
  and sometimes does not. The fp16 rows are tight (p90/p50 = 1.03) and are the trustworthy ones.

### Partitioning — did it actually run on the ANE?

`bench_ane_forward.py` reports latency only; it records **no** partitioning information and performs
**no** output-agreement check. Both were added here as a supplement,
`scripts/m5_bench/ane_coverage_probe.py`, which reads the `.mlpackage` files the bench already saved,
compiles them, and walks `MLComputePlan` per operation.

| precision | executable ops | on Neural Engine | on CPU | `const` (no device) |
|---|---|---|---|---|
| fp16 | 52 | **52 (100%)** | 0 | 125 |
| fp32 | 48 | **0** | 48 (100%) | 121 |

At fp16 every executable op — 15 `conv`, 16 `relu`, 6 `add`, 4 `cast`, 3 `linear`, 2 `reshape`,
2 `concat`, `reduce_mean`, `reduce_max`, `tanh`, `squeeze` — is assigned to
`MLNeuralEngineComputeDevice`. **The graph runs fully on the ANE with zero partitioning and zero CPU
fallback.** The 125 "unknown" entries are all `const` ops (weights and literals), which have no compute
device — they are not a partition boundary.

At fp32 the plan assigns **every** op to `MLCPUComputeDevice`. That is the mechanism behind the
1.002× fp32 row: the ANE does not execute this graph in fp32 at all, so `CPU_AND_NE` silently *is*
`CPU_ONLY`. The two measurements corroborate each other exactly.

⚠️ One honest limitation of the coverage numbers: `MLComputePlan.load_from_path` is called with
`compute_units=CPU_AND_NE` for all three packages, so the table answers "how does this graph partition
when the ANE is offered", not "what did each saved package do". Since all three packages are the same
traced graph, this is the question of interest, but the three rows are not independent evidence.

### Output agreement vs torch fp32 CPU

Not checked by the bundled bench; added by the supplement. Same seeded input fed to torch and to each
CoreML package; policy logits span ±88.14 on this input.

| precision | policy max abs diff | policy mean abs diff | as fraction of logit range | value max abs diff | argmax agrees | top-10 overlap |
|---|---|---|---|---|---|---|
| fp32 | 3.05e-05 | — | 3.5e-07 | **0.0** | yes | 10/10 |
| fp16 | 0.2077 | 0.0359 | 2.4e-03 | 6.20e-05 | yes | 10/10 |

The fp32 conversion is numerically faithful (value head bit-identical), so the fp16 deviation is
**precision, not a conversion bug**. On this input the fp16 argmax and the top-10 prior set are
unchanged.

⚠️ This is a numerics sanity check, **not** a play-identity gate: the input is `torch.randn`, not a real
encoded board, so it is out-of-distribution for the BatchNorm statistics and it is a single sample.
Anything that would actually deploy the fp16 CoreML net needs an agreement run over real positions with
a pre-registered tolerance, in the style of `scripts/reconcile_cy_leaf.py`.

### What this means for CL-067's cost problem

CL-067's close-out puts the requirement at ~4× cheaper per move, and a batch-1 forward is the atom of
that cost. On the M5 that atom is **6.19× cheaper on the ANE than on torch CPU** and 2.41× cheaper than
the same graph on CoreML CPU. Converting that into a per-move claim requires the forwards-per-move
count and the non-forward search cost, **neither of which this bench measured** — so no deployability
conclusion follows from this document. It is one input to that arithmetic, not the arithmetic.

---

## 3. M5 vs the local 5900XT — the ratio, with its caveat

Only **k1×32** was measured on both boxes; the local box never ran the larger rungs.

| | mean s/move at k1×32 | leaf path | n | condition |
|---|---|---|---|---|
| Apple M5 | 0.013526 | cython | 178 | idle |
| 5900XT (grand mean of 4 runs) | 0.038546 | cython | 58 each | **LOADED** |

**Ratio: 2.85× in the M5's favour.**

⚠️ **This ratio is an upper bound on the M5's advantage and must not be quoted bare.** The 5900XT was
running the CL-067 equal-wall-clock gate throughout its reference run — `loadavg` 13.93 / 12.83 / 11.63
on 32 threads, recorded in the JSON's own `machine.loadavg` field. The four local run-means span
0.03586–0.04056 (±6%), so the contention is not wild, but a single-stream latency measurement on a box
with 16 busy workers is systematically pessimistic. **A quiet-window 5900XT rerun of the same bundle is
owed**, and until it lands the honest statement is "the M5 is somewhere up to ~2.85× faster than a
contended 5900XT at k1×32", not "the M5 is 2.85× a 5900XT".

The k4×688 comparison does not exist at all. The run book's ~3.4 s/move figure for the loaded 5900XT is
an *extrapolation from the k1×32 rung*, not a measurement, and nothing here upgrades it.

### The comparison that is clean: M5 vs Pixel 9 Pro

| | k4×688 s/move | source |
|---|---|---|
| Apple M5 | 1.576 | this run, `bench_champion_Mac_20260728T225752.json` |
| Pixel 9 Pro | 1.7 | `measurement/ANDROID_WALLCLOCK_MEMO_20260728.md`, memory `reference_android_app` |

**0.93× — a 10-core desktop-class M5 is within 8% of the phone at the deploy budget.** Different
harnesses (the phone runs through `android_bridge` under Chaquopy) and different corpora, so this is an
order-of-magnitude comparison rather than a controlled one. But it is the same champion at the same
budget on the same leaf path, and it says the champion's search cost is dominated by something that
does not care much about the host being a phone or a workstation — consistent with the standing
"DRAM-latency-bound pointer-chasing" diagnosis, and a reason not to expect a big win from throwing a
faster single core at it.

---

## 4. What this does and does not say

**It says:** on an idle Apple M5, the champion of record — verified at construction against
`PRODUCTION.yaml`, running the native-arm64 Cython leaf — decides a move in 1.576 s at the deploy budget
k4×688, on 60 positions the champion itself reached (30 tile / 30 meeple, all `k_remaining > 2`, zero
endgame latches), with 178 samples per rung across 3 passes. And: the CL-067 net's batch-1 forward runs
entirely on the Neural Engine in fp16 at 0.420 ms, 6.19× the torch-CPU baseline, with the fp32 control
confirming the mechanism.

**It does not say:**

* **Anything about strength.** No games were played, no elo was estimated, no position was scored for
  quality. `governance/PRODUCTION.yaml` was not touched and no lever is proposed here.
* **That the M5 is 2.85× a 5900XT.** The local side was contended; that number is an upper bound and
  the clean rerun is owed (§3). No M5-vs-5900XT claim should be made from this document alone.
* **Anything about throughput.** This is one process making one decision at a time. The cluster
  question — how many concurrent workers an M5 sustains, where its memory bandwidth saturates — is a
  different measurement that was not run.
* **That CL-067 is deployable.** §2 measures a forward-pass atom. Turning 6.19× per forward into a
  per-move cost needs the forwards-per-move count and the search cost around them; neither was measured.
* **That the fp16 CoreML net is play-identical.** One random-normal input agreed to 2.4e-03 of the logit
  range with the same argmax. That is a numerics sanity check, not a gate.

---

## 5. Deviations from the run book

1. **macOS ships `openrsync`**, which rejects `--info=progress2`; the run book's §0 command fails with a
   usage dump and `code 12`. Plain `-a --stats` works. The excludes were kept exactly as specified and
   verified after transfer: no `.so`, no `.c`, no `.venv` reached the Mac.
2. **`--python` had to be pinned.** Non-interactive ssh has no `~/.local/bin` on `PATH`, so the
   interpreter search in `setup_m5.sh` step 1 would have found the system 3.9.6 and aborted. Ran
   `setup_m5.sh --python $HOME/.local/bin/python3.12`. Everything downstream then worked unmodified and
   the Cython build succeeded on the first try (Xcode clang 21.0.0 present).
3. **The ladder is much faster than budgeted.** One `--repeat 3` pass took 8.3 min wall against the run
   book's ~18 min estimate, because the M5 beat the extrapolation the estimate was built on.
4. **torch/coremltools installed with `uv`, not the venv's `pip`** (`uv pip install --python
   <venv-python>`), per the task's guidance; resolved torch 2.13.0 + coremltools 9.0. coremltools warns
   it has only been tested to torch 2.7.0 — conversion nonetheless succeeded for all six
   package/precision combinations with no error, and the fp32 agreement check (value head bit-identical)
   is direct evidence the untested pairing did not corrupt the graph.
5. **Added `scripts/m5_bench/ane_coverage_probe.py`.** The task asked for ANE coverage and any
   output-agreement check; the bundled `bench_ane_forward.py` provides neither. The supplement supplies
   both from the artefacts the bench already writes. Implementation note for whoever reuses it:
   `MLComputePlan.load_from_path` requires a *compiled* `.mlmodelc` — handed an `.mlpackage` the CoreML
   C++ layer raises an uncaught `ios_base::failure` and **aborts the process**, taking any unwritten
   results with it. The probe therefore calls `coremltools.models.utils.compile_model` first and
   persists its JSON before touching the compute-plan API.
