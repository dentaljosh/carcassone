# CUDA-Graph-from-Rust spike — the go/no-go for the net arm

**Status: COMPLETE 2026-08-03. ⚠️ VERDICT = STOP (qualified) — the spike's ENGINEERING
goal succeeded and its DECISION goal failed.** CUDA-Graph capture is now reached from
Rust through `ort`'s `IOBinding`, it is within ~4% of the torch reference, and it passes
T1 faithfulness unchanged. It is nonetheless **not enough**, because re-measuring the
*denominator* on a genuinely quiet box moved it 1.55× and the design lands **outside**
the CL-067 break-even it was supposed to enter. No promotion, no `results.csv` row, no
`PRODUCTION.yaml` change, no strength claim.

Charter: [`docs/RUST_NET_EVAL_DESIGN_20260802.md`](../../docs/RUST_NET_EVAL_DESIGN_20260802.md)
§6.2 / §7.1 (the spike is that memo's own pre-registered next step).
Raw numbers: [`raw_readout_gpu.txt`](raw_readout_gpu.txt) (the GPU legs, rebuilt binary,
every knob row paired with its faithfulness row) and [`raw_readout.txt`](raw_readout.txt)
(the earlier full pass, retained because it contains the census-clean CPU rows and the
denominator sweep — ⚠️ **its CUDA rows are from a stale binary and are superseded**, see
§7). Config: [`manifest.json`](manifest.json).

---

## 1. The one-paragraph answer

`Backend::CudaGraph` panicked in the memo's prototype because ORT can only capture a
graph over **device-resident tensors at stable addresses**, and the prototype handed it
host slices. Binding device tensors once via `IoBinding` and refreshing their contents in
place fixes it: batch-1 goes **1.158 → 0.434 ms (2.67×)** and batch-8 goes
**1.726 → 1.219 ms (1.42×)**, landing at **0.152 ms per leaf**. That **clears the
memo's literal bar of ≤ ~0.18 ms.** But the memo's bar was a *proxy* for `r ≤ ~2.0` and
`cost_ratio ≤ ~2.5`, and those were calibrated against a denominator of 0.0903 ms/sim
that **this box does not reproduce when nothing else is running** — the true quiet-box
figure is **0.0584 ms/sim**. On the internally consistent pair (quiet numerator, quiet
denominator) the design reads **r = 2.61, cost_ratio ≈ 3.06**, against a recorded
break-even of ~2.4–2.6. **The absolute bar passes and the substantive bar fails, and the
gap between them is entirely the denominator.**

## 2. What fixed the build

Nothing in the source. `carc-net` failed to link with
`rust-lld: error: undefined symbol: OrtGetApiBase` for every binary — pre-existing, and
purely an environment gap: the crate deliberately does not enable `ort`'s
`download-binaries` feature, so `ort-sys` had no ONNX Runtime to link against. The fix is
`ORT_LIB_LOCATION` + `ORT_PREFER_DYNAMIC_LINK=1` (the wheel ships shared objects only,
and `ort-sys` defaults to static linking), now checked in as
[`rust/carc/carc-net/tools/ort_cuda_env.sh`](../../rust/carc/carc-net/tools/ort_cuda_env.sh)
with the provisioning recipe in its header so it stops living in a session's shell
history. Enabling `download-binaries` instead would re-arm the memo's §4b trap: that
build wants CUDA 13, this box has CUDA 12, and the mismatch **fails open to the CPU**.

## 3. What made the graph path work

Three things, each of which was individually load-bearing:

1. **`IoBinding` with device-allocated inputs, bound once.** Bound values that already
   live on the target device have their *pointers* recorded rather than their contents
   copied, so in-place refreshes are visible to later runs and the capture stays valid.
2. **`bind_output_to_device`** rather than a host output, so ORT allocates and reuses one
   device buffer and nothing in the captured region touches host memory.
3. **A raw `cudaMemcpy` for the H2D/D2H** ([`src/cudart.rs`](../../rust/carc/carc-net/src/cudart.rs),
   ~60 lines, `dlopen`-resolved). This was not a shortcut but a forced move: `ort`'s own
   `Value::copy_into` is implemented as *an extra ORT session run over an Identity graph*,
   and that helper session sets `GraphOptimizationLevel::Level3`, which **this box's
   `ort` rc.13 / onnxruntime 1.22 pairing rejects** — the same ABI mismatch already
   documented on our own session. Every `copy_into` fails at runtime, inside `ort`, where
   we cannot pass a different option.

⚠️ **A segfault worth remembering.** `ort` ties a `Tensor` to the `Allocator` that made it
by **no lifetime at all** — the tensor keeps a raw pointer, the allocator frees its
`OrtAllocator` on drop. Letting the allocator die at the end of the setup function
segfaults on the next forward. The allocator is now the **last** field of the `Bound`
struct so Rust's field drop order outlives the tensors, with a comment saying why.

## 4. Measured — the numerator

Local box, **quiet** (census clean; no eval, no gen, GPU idle at 0%), RTX 5060 Ti /
5900XT, `taskset -c 24-31`, min over 400–1000 reps, median alongside. Same net, ONNX
export and corpus as the memo (`distill_strong_20260723/ckpt/iter_03.pt`, policy-only,
81ch/42sc, A=2511).

| backend | batch | forward ms (min) | per-leaf ms | vs memo §6.1 |
|---|---|---|---|---|
| ORT CUDA eager, host slices | 1 | 1.158 | 1.158 | 2.018 (contended) |
| ORT CUDA eager, host slices | 8 | 1.726 | 0.2157 | 1.880 (contended) |
| ORT CUDA eager, host slices | 64 | 8.175 | 0.1277 | 9.032 (contended) |
| ORT CUDA + **IOBinding**, eager | 1 | 1.816 | 1.816 | *new* |
| ORT CUDA + **IOBinding**, eager | 8 | 1.861 | 0.2326 | *new* |
| ORT CUDA + **IOBinding**, eager | 64 | 7.138 | 0.1115 | *new* |
| **ORT CUDA + IOBinding + GRAPH** | **1** | **0.434** | **0.434** | **panicked** |
| **ORT CUDA + IOBinding + GRAPH** | **8** | **1.219** | **0.1524** | **panicked** |
| **ORT CUDA + IOBinding + GRAPH** | 64 | 6.800 | 0.1063 | **panicked** |

⚠️ **Provenance of this table:** every row is from the **census-clean window** (roughly
05:55–06:35 local), each reproduced across 3–6 independent runs at 200–1000 reps, all at
ORT's default CUDA-EP knobs. A later re-run under another session's CPU load reproduces
them within ~5% (`raw_readout_gpu.txt` — batch-8 graph reads 1.276 there vs 1.219 here),
which is the expected direction: the GPU is idle in both, but the *launch* side is CPU
work. The clean window is quoted because the denominator was measured in it too.

Reference points: torch in-process with a real `CUDAGraph` read **0.339 / 1.168 / 7.110**
ms at batch 1 / 8 / 64 (memo §2.2). **ORT-from-Rust is within 4.4% of torch at batch 8**
and 1.28× of it at batch 1 — i.e. the Rust path is not leaving anything meaningful on the
table; this is close to what the hardware gives.

Three readings that matter:

* **Graph capture is real and it is the whole win.** Device-resident binding *alone*
  buys nothing at batch 1 (it is *slower*: 1.816 vs 1.158 — `run_binding` carries more
  per-call overhead than `Session::run`). Adding capture takes the same path to 0.434,
  a **4.18×** improvement over its own eager twin.
* **The win shrinks fast with batch**: 2.67× at batch 1 vs eager, 1.42× at batch 8. At
  batch 8 ORT's eager path already amortizes launches across the batch, so capture is
  removing a smaller share of the cost. The memo's 7.1× headline is a **batch-1** figure
  and must not be carried to batch 8.
* **The upload is not free.** Refreshing the device inputs costs ~0.20 ms per batch-8
  round (~0.025 ms/leaf) as a *synchronous* copy from *pageable* memory. Pinned staging
  and an async copy on the EP stream would cut this substantially; it is reported apart
  from the forward because the torch reference excludes it too.

**Control — is the clock honest?** A latency number is only meaningful if it brackets GPU
*completion*, not just launch. Re-running with `CARC_ORT_EXPLICIT_SYNC=1`, which appends
an explicit `SynchronizeBoundOutputs`, moves batch 8 from 1.219 to 1.191–1.238 ms —
**inside run-to-run spread**. ORT's `Run` does synchronize; the timings stand.

## 5. Measured — the denominator, and why the verdict turns on it

**This is the finding that decides the spike, and it is not the one the spike was
looking for.**

`carc-core`'s `examples/evalprobe`, same binary and arguments as the memo, at
`SearchConfig::default().simulations` = 1376:

| ply | 40 | source |
|---|---|---|
| memo §2.1, "contended" | 0.1196 ms/sim | a live 13-worker eval held the box |
| memo §2.1, "quieter earlier run" — **the memo's denominator** | 0.0903 ms/sim | same session |
| **this spike, single-threaded, quiet, 3 repeats** | **0.0571 / 0.0575 / 0.0575** | census-clean box |
| **this spike, 8 concurrent probes** (the k=8 deploy shape) | **0.0580–0.0608, mean 0.0584** | census-clean box |

No `carc-core` change explains it — the memo was measured **at** `3416f87`, which is
itself the perf-pass merge, and no `rust/carc` commit lands between there and the memo
commit. The explanation is box state, and the spread is large: the same probe reads
**2.1× apart** between a loaded and an idle box. The memo's "quieter" reading was still
1.55× above idle.

**The 8-concurrent row is the one to use.** The champion deploys `parallel_workers: 8`
(CL-071), so the honest denominator is what *one world* sees while *eight* are running —
and that is only **+2%** over single-threaded, which also settles a live question: the
Rust search is **not** DRAM-bandwidth-saturated at k=8 on this box, so k-world
parallelism does not hand the net arm a bigger denominator to hide in.

## 6. The verdict, both ways

`cost_ratio ≈ (1 − sweep_fraction) + r` (memo §3); today's measured `sweep_fraction` at
ply 40 is **0.52–0.59**, so the credit is ~0.45. Recorded break-even: **~2.4–2.6×**.

| reading | denominator | `r` at batch 8 | `cost_ratio` | vs break-even |
|---|---|---|---|---|
| memo's arithmetic, memo's denominator | 0.0903 | **1.69** | **2.14** | ✅ inside |
| **same forward, quiet-box denominator** | **0.0584** | **2.61** | **3.06** | ❌ outside |

And the same correction applied to the memo's own §6.3 table is worth stating plainly,
because it retires that table's conclusion:

| forward path | per-leaf ms @ b8 | `r` @ 0.0584 | `cost_ratio` |
|---|---|---|---|
| ORT CUDA eager (the memo's prototype) | 0.2157 | 3.69 | 4.14 |
| **ORT CUDA + Graph from Rust (this spike)** | **0.1524** | **2.61** | **3.06** |
| torch CUDA + Graph (the memo's "achievable" row) | 0.146 | 2.50 | 2.95 |

**Even the aspirational torch row fails once the denominator is measured on a quiet box.**
The memo's §6.3 "inside, for the first time" was an artifact of a contended denominator,
not of the forward path — which means the spike could not have rescued the line no matter
how well it went.

**Pre-registered branch, read honestly.** The memo's §7.1 rule fires two ways: its
literal trigger ("batch-8 per-leaf ≤ ~0.18 ms") **passes** at 0.152 (and still passes at
0.177 with the unoptimized upload folded in), while the parenthetical it was standing in
for ("`r ≤ ~2.0`, `cost_ratio ≤ ~2.5`, i.e. inside the gate's own recorded break-even")
**fails**. A bar stated in absolute milliseconds silently assumed a denominator; when the
denominator moved, the two halves of the same bar stopped agreeing. **The substantive
half governs** — the break-even is what the CL-067 gate actually recorded, and the ms
figure was only ever its shadow.

**Only one measured configuration clears**: batch **64**, at `r` 1.82 / `cost_ratio` 2.27.
A k=8 PIMC search has at most 8 leaves in flight, so reaching it requires batching across
*moves* (pondering) or across *games* — a different lever with its own design, exactly as
the memo said.

## 7. ⚠️ The trap, and the process failure that found it twice

**`fuse_conv_bias=1` is FASTER AND WRONG on this box.** It reads ~3% better at batch 8
and looks like free money. It is not: argmax agreement over the 1168-position corpus
collapses from **100.00% to ~30%** and the max-abs residual goes from 4.9e-4 to **1.0**,
on all three CUDA backends. Nothing raises; ORT reports success. It is left wired up
**default-off**, matching ORT's own default, so the trap stays discoverable and
re-testable after an onnxruntime upgrade rather than being rediscovered by someone
reading the option list and assuming it is free.

`prefer_nhwc=1`, by contrast, is **merely slower** (batch-8 forward 1.276 → 1.361 ms;
batch-64 per-leaf 0.107 → 0.157) and stays 100.00% faithful. Rejected on latency.

⚠️ **Two process failures in this spike are worth more than the finding itself**, because
both produced *plausible* numbers:

1. The knob was briefly given a default of **on**, which silently contaminated the TF32
   control — and the first reading blamed `use_tf32=0` for damage the fusion was doing.
   The corrected, isolated TF32 measurement is in §8 and says the opposite. **Every knob
   row in the readout is now paired with a faithfulness row**; do not benchmark a CUDA-EP
   option here without re-running `faithful`.
2. A driver script measured a **stale binary** because it had no build step, reproducing
   the contaminated result after the fix had already been written. The readout now stamps
   the binary's mtime and the loadavg into its own header.

These sit alongside the memo's original §4b trap (CUDA-13 binaries failing open to the
CPU). Three independent silent-wrongness modes in one dependency is itself a maintenance
signal about adopting `ort` on this box — and the general lesson is the one the project
already writes down as *fail loudly*: **a faster number is not a result until the
correctness check has been re-run beside it.**

## 8. Acceptance tiers (§5 of the memo)

| tier | result |
|---|---|
| **T0** export equivalence | unchanged — same ONNX artifacts as the memo, written under `export_onnx.py`'s bit-identity assertion |
| **T1** ordering faithfulness | ✅ **PASS on the new surface.** `cuda+bound` and `cuda+graph` both read **argmax 100.00%**, top-5 99.40%, n=1168 — and are **identical to the eager CUDA row in every reported digit**, including the bit-exact count (179). A device-resident, graph-captured path introduces **zero** additional drift. |
| **T2** residual magnitude | recorded: max-abs **4.926e-4**, max-TV 4.942e-4, identical to eager CUDA. **The TF32 attribution is now PROVEN rather than inferred**: with `CARC_ORT_TF32=0` the residual drops to **8.196e-7** (a ~600× tightening, into the same class as the CPU path's 6.4e-7 and the ANE's 2.4e-7) and top-5 agreement rises 99.40% → **100.00%**. The price is **~1.6× latency** (batch-8 forward 1.276 → 2.061 ms), which this design cannot afford — but the trade is now measured on both axes instead of assumed on one. |
| **T3** device provenance | ✅ strengthened. `.error_on_failure()` (EP registered) **plus** a runtime assertion that the bound inputs *and* the bound output actually landed on `AllocationDevice::CUDA` — `bind_output_to_device` silently falls back to CPU when the target device has no EP, by ORT's own admission. |

## 9. Recommendation

**STOP, and shelve — do not delete.** The net arm should not be built on this hardware:
`cost_ratio ≈ 3.06` against a break-even of ~2.4–2.6, with the encoder port (days of
work, plus its own bit-exactness sub-project) still entirely ahead of it. The memo's own
branch structure calls this outcome, and it calls it *before* the expensive part.

What the spike bought, and why the code stays:

* The CUDA-Graph-from-Rust question is **answered with a working implementation**, not an
  estimate. If the hardware changes, the answer is a re-run of one bench, not a rebuild.
* The **denominator correction** is the durable finding, and it is not confined to this
  memo: a ~1.55× error in `search_ms_per_sim` propagates to any `r`-shaped or
  cost-ratio-shaped argument measured in that era. Probe the denominator on a
  **census-clean** box, and record the box state next to the number.
* Two silent-wrongness traps are now documented with the measurement that exposes them.

**Re-open bar** (either): a device on which batch-8 per-leaf reaches **≤ ~0.11 ms**
(`r ≤ 2.0` at the *measured* denominator, `cost_ratio ≤ 2.5`); **or** a batching design
that puts ≥64 leaves in flight, which today's numbers already show clears — that is
pondering or cross-game batching, and it is a separate lever with its own gate.

## 10. Reproducing

```bash
export ORT_DIST=/path/to/cuda12-onnxruntime-1.22/lib      # provisioning in the script header
source rust/carc/carc-net/tools/ort_cuda_env.sh
cargo build --release --manifest-path rust/carc/carc-net/Cargo.toml
cargo build --release --example evalprobe -p carc-core --manifest-path rust/carc/Cargo.toml

# denominator — ON A CENSUS-CLEAN BOX, and say so in the artifact
./rust/carc/target/release/examples/evalprobe 12345 10,20,30,40,50,60,70 3

# numerator; 4th arg filters backends, e.g. "cuda,cuda+bound,cuda+graph"
./rust/carc/carc-net/target/release/bench_r   <onnx-dir> 0.0584 1000 cuda+graph
CARC_ORT_EXPLICIT_SYNC=1 ./rust/carc/carc-net/target/release/bench_r <onnx-dir> 0.0584 1000 cuda+graph

# faithfulness — RUN THIS AFTER ANY KNOB CHANGE, see §7
./rust/carc/carc-net/target/release/faithful  <onnx-dir> <positions.bin> 8
```

The ONNX exports and the 1200-position dump are produced by `tools/export_onnx.py` and
`tools/dump_positions.py` as documented in the memo §8; they are ~90 MB and ~258 MB and
are not checked in.
