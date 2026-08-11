# Rust-side neural evaluator for `carc_rs` — design, measurements, and the gate

> ## ⚠️ RESOLVED 2026-08-03 — THE SPIKE RAN, AND THE ANSWER IS **STOP**
>
> §7.1's half-day go/no-go spike is **complete**:
> [`measurement/rust_net_cudagraph_spike_20260803/`](../measurement/rust_net_cudagraph_spike_20260803/README.md).
>
> * **§6.2 is superseded.** CUDA-Graph capture **IS** reachable from Rust through `ort`.
>   Binding device-resident tensors via `IoBinding` fixes the panic; batch-1 goes
>   1.158 → **0.434 ms** and batch-8 to **0.152 ms/leaf**, within ~4% of the torch
>   reference. T1 is unaffected (100.00% argmax, byte-identical to the eager CUDA row).
> * **§6.3 is RETIRED, and this is the finding.** Its denominator, 0.0903 ms/sim, was
>   measured on a box holding a live 13-worker eval. The census-clean figure is
>   **0.0584** — 1.55× smaller. Every `r` and `cost_ratio` in §6.1/§6.3 is inflated in
>   the candidate's favour by that factor. Recomputed, this spike's forward reads
>   `r = 2.61` / `cost_ratio ≈ 3.06`, and **even §6.3's aspirational torch+Graph row
>   reads 2.95** — all outside the ~2.4–2.6 break-even. The line could not have been
>   rescued by any forward path here.
> * **§7.1's bar fires both ways and the substantive half governs**: the literal
>   "≤ ~0.18 ms" **passes** at 0.152, while the "`r ≤ ~2.0`, `cost_ratio ≤ ~2.5`" it
>   was standing in for **fails**. A bar in absolute milliseconds silently assumed a
>   denominator.
>
> Nothing below is edited; read §6.1–§7.1 as the 2026-08-02 record and the spike README
> as the verdict.

**Status: DESIGN + BENCHED PROTOTYPE (2026-08-02); SPIKE RESOLVED 2026-08-03 — see the banner above.** No search integration, no strength
claim, no `results.csv` row, `governance/PRODUCTION.yaml` untouched. The deliverable is
this memo plus a working forward path (`rust/carc/carc-net/`) whose `r` is measured
rather than asserted. ⚠️ **Nothing here promotes anything.**

**⚠️ Headline, so nobody reads past it:** on the forward path this prototype achieves
**today**, the design **FAILS its own bar** — `r = 2.60` at the decision-relevant batch 8
(§6.1). It clears the bar only with **CUDA-Graph capture**, which is **measured real in
torch (7.1× at batch 1)** but **panics through `ort` here** (§6.2). The recommendation is
therefore *conditional*, and the ask is a **half-day spike**, not an integration — see
§7.1. Faithfulness, separately, is **already green**: 100% argmax on 1168 real positions
(§6.4).

---

## 1. The question, and the north star

The net arms (`fair-net`, `fair-netprior`, and any future neural-prior search) are
permanently Python because `carc_rs` cannot call a network forward during search. The
question is what it would take to change that, and whether it is worth doing.

The north star is fixed and pre-registered. The CL-067 equal-wall-clock gate
([`NETPRIOR_EQTIME_GATE_20260728.md`](../measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md) §6)
closed the desktop distilled-net line on cost, not strength, and stated the reopen
condition in device-independent form **before anyone built anything**:

> REOPEN the distilled-net line for deploy when the target device's measured
> `r = forward_ms / search_ms_per_sim` is ≤ ~1.5.

The Python-era desktop path measured `r ≈ 3.0` and fired branch C (WASH). The Rust port
then made the *denominator* ~8× smaller (`PRODUCTION.yaml fair_deploy.backend: rust`,
9.55× the Python champion; farm-realised 7.77× / champ-side 9.79× at production budget).
Holding the forward fixed, that inflates `r` ~8× and pushes every previously-measured
forward path — including the ANE's `r ≈ 0.73` — far above the bar. **So a rust-side
evaluator is only worth building if it keeps `r` low.** That is the lens for everything
below.

---

## 2. What was measured, and on what

All numbers were measured on the local box on 2026-08-02, at `android-app` HEAD
(~`3416f87`), in a worktree.

* **CPU** 5900XT, 16C/32T. **GPU** — ⚠️ **RTX 5060 Ti**, not a 4090; the task brief said
  4090 and that is wrong for this box. Every GPU figure below is 5060 Ti.
* ⚠️ **The box was NOT quiet.** A live `eval_fair_puct.py --k-dets 8 --sims 1376` run
  (~13 workers) held ~13 cores throughout. Benches were pinned (`taskset -c 24-31`) and
  every reported figure is the **minimum over reps**, the statistic least contaminated
  by a neighbour's cache and memory-bandwidth pressure; medians are printed alongside so
  the spread is visible. **The CPU rows should be read as upper bounds on a quiet box;
  the GPU rows are much less affected.**
* **Net of record** `distill_strong_20260723/ckpt/iter_03.pt` — the CL-067 checkpoint,
  6×96 ResNet, sighted rep **81ch / 42 scalars**, window 25, action space **2511**,
  `value_global_pool=true`. **Policy-only** forward (`forward_policy_only`), because the
  `fair-netprior` arm never reads the net's value — the value is the frozen champion
  v2.9 `curve125` leaf. ~1.34 GFLOP per batch-1 forward.

### 2.1 The denominator — `search_ms_per_sim`, and the child sweep

`rust/carc/carc-core/examples/evalprobe.rs`, single-threaded, at the champion's own
per-determinization budget (`SearchConfig::default().simulations` = 1376), positions
reached by first-legal replay from seed 12345:

| ply | legal | ms/sim | leaf evals/sim | isolated leaf µs | child (clone+advance+leaf) µs | sweep ms/sim | **sweep fraction** |
|---|---|---|---|---|---|---|---|
| 10 | 10 | 0.0658 | 9.60 | 1.51 | 2.27 | 0.0195 | 0.296 |
| 20 | 28 | 0.0793 | 10.28 | 2.99 | 3.81 | 0.0354 | 0.446 |
| 30 | 33 | 0.0961 | 10.40 | 4.34 | 5.62 | 0.0528 | 0.550 |
| 40 | 25 | 0.1196 | 9.61 | 5.86 | 6.64 | 0.0572 | 0.478 |
| 50 | 36 | 0.1395 | 10.41 | 6.99 | 8.35 | 0.0786 | 0.564 |
| 60 | 54 | 0.2210 | 15.80 | 9.94 | 9.50 | 0.1406 | 0.636 |
| 70 | 37 | 0.0871 | 4.94 | 8.88 | 10.87 | 0.0429 | 0.492 |

⚠️ **Two denominators, and the difference is contention, not disagreement.** The table
above was taken while the ORT bench held 8 cores; an earlier, quieter run of the same
probe read **0.0434 / 0.0651 / 0.0847 / 0.0903 / 0.1156 / 0.1718 / 0.0707** ms/sim across
the same plies. **`0.0903` ms/sim (ply 40, quiet) is the denominator used throughout this
memo** — the conservative choice, since a larger denominator would flatter `r`. The
`sweep fraction` column is a *ratio* of two quantities that inflate together, so it is
the contention-robust number here.

The shape that matters: the classical evaluator builds its PUCT priors from a **child
sweep** — one `Game::clone()` + `advance()` + leaf evaluation per legal action, i.e.
`1 + |legal|` leaf calls per expansion. Measured, that is **~9.6–10.4 leaf evaluations
per simulation**, and the sweep is **~30–64% of all per-simulation cost, ~0.5 mid-game**.
That half of the search is exactly what a net-prior evaluator deletes.

### 2.2 The numerator — torch, in-process (the reference)

`torch` 6×96 policy head, `forward_policy_only`, min over 60 reps:

| device | batch | forward ms (min) | per-leaf ms | note |
|---|---|---|---|---|
| CPU (4 threads) | 1 | 7.963 | 7.963 | |
| CPU (4 threads) | 8 | 43.728 | 5.466 | |
| CPU (4 threads) | 64 | 453.039 | 7.079 | |
| CUDA eager | 1 | 2.396 | 2.396 | cf. carc-orch's 4.199 ms — SHM+IPC adds ~1.7 ms |
| CUDA eager | 8 | 2.184 | 0.273 | batch is nearly free: launch-bound, not FLOP-bound |
| CUDA eager | 64 | 7.191 | 0.112 | |
| **CUDA + CUDA Graph** | **1** | **0.339** | **0.339** | **7.1× over eager — pure launch overhead** |
| **CUDA + CUDA Graph** | **8** | **1.168** | **0.146** | |
| CUDA + CUDA Graph | 64 | 7.110 | 0.111 | compute-bound; graph buys nothing here |

**This is the single most important measurement in this memo.** A 6×96 ResNet at batch 1
is ~1.34 GFLOP — trivial for the GPU. What it costs is ~30 *kernel launches*. Capturing
the graph and replaying it cuts batch-1 from 2.396 ms to **0.339 ms**. CUDA Graph capture
has **zero hits** in `DECISIONS.md`, `BACKLOG.md`, the roadmap, or
[`docs/LEVER_INDEX.md`](LEVER_INDEX.md) — it is an un-indexed lever, and it is worth
roughly 7× on exactly the quantity the CL-067 gate is bottlenecked on.

---

## 3. Why `r` is the wrong statistic for the port — and what replaces it

`r = forward_ms / search_ms_per_sim` models the forward as **purely additive** on top of
an unchanged search: cost ratio `= 1 + r`. In Python that was a fair approximation,
because a 4.2 ms forward dwarfed everything it displaced.

**In Rust it is wrong, and wrong in the candidate's favour.** `fair-netprior` takes its
priors from the net's policy head and its value from the frozen leaf
(`heuristic_prior_mcts._fair_net_prior_leaf_value_fn`), so per expansion it pays
**1 leaf + 1 forward** where the classical evaluator pays **`1 + |legal|` leaf calls plus
`|legal|` game clones**. The net arm **deletes** the child sweep. The honest quantity is
therefore the per-move **cost ratio**

```
cost_ratio  ≈  (1 − sweep_fraction)  +  forward_ms_per_leaf / search_ms_per_sim
```

and `r` is only its **upper bound**. §2.1's `sweep_fraction` column is what makes this
quantitative rather than rhetorical: at the measured mid-game `sweep_fraction ≈ 0.5`,

```
cost_ratio  ≈  0.5 + r        instead of        1 + r
```

so the port buys back **a flat 0.5×** of the cost ratio on top of whatever the forward
costs. Both readings are given in §6 so a reader can apply whichever they trust.

**Why this is decision-relevant rather than cosmetic.** The CL-067 gate recorded its own
break-even: *"Measured break-even is an equal-sims cost ratio of ~2.4–2.6×; the candidate
measures ~4.0×"* (`results.csv`, the arm-A verdict row). The Python netprior failed
because 4.0 > 2.6. The question this memo actually answers is whether the Rust port moves
the candidate from the wrong side of that break-even to the right side — see §6.3.

⚠️ **This is arithmetic with measured inputs, not a measured agent** — exactly the status
the CL-067 gate assigned its own ANE row, and it carries the same caveat: a real agent
interleaves the two costs and may contend for memory bandwidth. The only thing that
settles it is one cell with a real agent.

---

## 4. The four candidate backends

Common constraint, and it dominates: **`carc-core` has zero dependencies and must stay
WASM/iOS-buildable** (its own crate docs say so). No inference runtime may ever enter
`carc-core`. The seam therefore has to be a *trait* in `carc-core` with every
implementation in a crate `carc-core` does not depend on — which is what
`carc_core::eval::PolicyEvaluator` is.

### (a) PyO3 callback into Python/torch

* **Latency** — the forward itself is the best available (§2.2: 0.339 ms batch-1 with a
  CUDA graph, and it *is* torch). On top sits the GIL round-trip. **Measured** (a purpose-
  built PyO3 0.23 extension calling an empty Python callable, 200k iterations, so the
  figure is transition cost and nothing else):

  | pattern | ns per call | what it models |
  |---|---|---|
  | GIL already held | **57.6** | irrelevant — a search thread never holds it |
  | release + re-acquire per call | **190** | one search thread crossing into Python |
  | 2 threads each crossing | **49,744** | |
  | 4 threads each crossing | **105,723** | |
  | **8 threads each crossing** | **254,005** | **the champion's `parallel_workers: 8`** |

  Read the last row carefully: it is the wall-clock for eight world threads to each get
  one callback — **254 µs**, against a per-simulation search cost of **90 µs** and a
  batch-8 forward of **146 µs**. Amortized per call that is ~32 µs, a **~167× inflation**
  over the uncontended 190 ns. This is the GIL convoy effect, and it means **a naive
  per-thread callback evaluator costs more in transitions than the entire search and the
  entire forward combined.**
* **The structural problem is not the round-trip, it is the serialization.**
  `carc_core::fair::search_worlds` runs the k determinization worlds on scoped **OS
  threads**, bit-identically at any thread count. A search thread holds no GIL, so every
  callback must acquire it — and k threads that each want a callback **cannot overlap**.
  The GIL turns the k-world parallelism (the champion's `parallel_workers: 8`, promoted
  2026-07-29 as CL-071 and worth 6.37×) into a queue.
* Worse, it is hostile to the one lever that makes the economics work. The *fix* for the
  convoy is to have exactly **one** thread cross into Python carrying a batch assembled
  from all k worlds — which drops the transition back to the 190 ns row and is perfectly
  affordable. But that is a cross-thread rendezvous plus a batching queue, i.e. **an
  inference server living inside the search** — re-inventing carc-orch, with the GIL
  still on the hot path and `carc-core`'s threading permanently coupled to CPython.
* **Bit-exactness** — the best of any option, because it is literally torch. Only
  marshaling differs.
* **Android/WASM** — none. Chaquopy has no torch.
* **Verdict: reject as a shipping design. Keep it as the faithfulness ORACLE** — it is
  the right way to generate reference outputs, which is exactly how it is used here.

### (b) `tract` or `ort` (ONNX Runtime)

* **`tract`** — pure Rust, no C dependency, builds anywhere including WASM/iOS/Android.
  **CPU only, no CUDA, no graph capture.** For a 1.34 GFLOP conv stack its batch-1 will
  sit in the same class as (or worse than) the ORT CPU numbers in §4b — order 10 ms,
  which is `r` in the tens even before the Rust denominator shrinks it. **Excellent
  portability, disqualifying latency.** Worth keeping in mind only for an on-device
  *analyzer* (Phase 5), never for clocked play.
* **`ort`** — bindings to ONNX Runtime. The only candidate that has **both**
  CUDA-Graph-class batch-1 latency (the CUDA EP exposes `enable_cuda_graph`) **and** an
  Android story (NNAPI / QNN / XNNPACK EPs, plus CoreML and DirectML). ONNX is a neutral
  interchange the project already has three siblings of — TorchScript for carc-orch,
  CoreML for the ANE, LiteRT for the Pixel — so an ONNX export is a fourth flavour of an
  existing, already-asserted-equivalent graph, not a new concept.
* ⚠️ **Maintenance cost, and it is real — I hit it.** `ort` rc.13's `download-binaries`
  feature fetches an onnxruntime built against **CUDA 13**; this box has **CUDA 12** (via
  torch's `nvidia-*` wheels). The version gap does **not** raise: ORT logs a
  provider-load failure and **silently falls back to CPU**. The first run of the bench in
  this very memo reported "cuda" and "cuda+graph" rows that were the CPU — identical to
  each other and no faster than `cpu(8)`, which is the tell. The prototype now passes
  `.error_on_failure()` so the fallback is fatal, and the bench pins an explicit
  `ORT_LIB_LOCATION`. **Any adoption must pin the onnxruntime build and assert the EP
  actually registered**, or it will eventually measure the wrong device — the failure
  `coreml_evaluator.resolve_net_backend` already refuses to permit on the Python side.

### (c) `candle`

* Pure Rust, CUDA via `cudarc`, Metal for Apple. **No CUDA Graph support**, so batch-1 is
  launch-bound in the eager class (~2–4 ms) — it forfeits the 7× that makes this design
  viable at all.
* Its ONNX path (`candle-onnx`) is thin; the realistic route is hand-writing the 6×96
  ResNet in Rust and mapping weights from safetensors. That is easy to write and creates
  a **new bit-exactness surface** (a hand-built graph that must be proven to be the net
  of record) for no latency win.
* **Verdict: reject.** More work, worse latency, extra risk surface.

### (d) `tch-rs` (libtorch)

* Best fidelity after (a) — the same kernels as torch — and libtorch is **already linked
  by `carc-orch`**, so the dependency exists in the repo. The brief correctly forbids
  folding `carc` into `carc-orch`, but that is not the blocker.
* **The blocker is that `tch` does not expose the CUDA Graph API.** libtorch has
  `at::cuda::CUDAGraph`; the Rust bindings do not surface it. Without capture, batch-1 is
  the eager 2.396 ms and batch-8 is 0.273 ms/leaf — `r ≈ 3.0` at batch 8 on the Rust
  denominator, i.e. **the same failing number the Python era already measured**, which is
  the whole point of not doing this.
* ~2 GB dependency, no Android, no WASM, and it would put a heavyweight C++ runtime in
  the dependency graph of the crate family that is deliberately dependency-free.
* **Verdict: reject for shipping.** It becomes the natural choice only if someone exposes
  CUDA Graphs through `tch`, at which point it beats `ort` on fidelity.

---

## 5. Acceptance — tiers, not bit-exactness

**Be honest up front: cross-framework float identity is not achievable.** ORT and torch
choose different convolution algorithms, different reduction orders, and different fusion
boundaries; any one of those moves the last ULP. Demanding equality would fail a correct
backend.

The project has already priced this and set the precedent.
`src/carcassonne_ai/coreml_evaluator.py` accepts its ANE backend on **argmax and top-5
agreement plus a reported max-abs residual** — measured 2.4e-7 max-abs, **bit-identical
0/500**, **argmax and top-5 agreement 100%** — and `verify_coreml_evaluator.py` reports
exactly those fields rather than asserting equality. Its DESIGN DECISION 1 (mask on the
host, raw logits in the graph) exists so that the *only* numerical difference is the
rounding of the logits, keeping the error budget interpretable. **The ORT path reproduces
that decision exactly**, so the two backends are judged on one ruler.

The proposed tiers, to be fixed **before** any strength cell is funded:

| tier | requirement | what it licenses |
|---|---|---|
| **T0 — export equivalence** | The export wrapper is **bit-identical** to `CarcassonneNet.forward_policy_only` on a probe batch, asserted in-process before any artifact is written. | That the ONNX file is the net of record. Already enforced: `tools/export_onnx.py` raises rather than write. |
| **T1 — ordering faithfulness** (the acceptance bar) | On ≥1000 real corpus positions: **argmax agreement ≥ 99.5%** and **top-5 ordered agreement ≥ 99%** vs torch at batch 1, with max-abs and max-TV **reported**. | Using the backend for *search*. PUCT consumes priors as a ranking plus a magnitude; a perturbation that reorders nothing cannot change a selected move except through second-order visit allocation. |
| **T2 — residual magnitude** | max-abs and max-TV **reported**, and any device exceeding **1e-4** must **name its cause**. Explicitly *not* a pass/fail bar. | Comparability across backends, and a visible baseline for later regressions. §6.4 shows why a bright line would be wrong: the CUDA path reads 4.9e-4 for a fully understood reason (TF32) while disagreeing on **zero** argmaxes. |
| **T3 — device provenance** | The EP that actually executed is asserted at construction (`.error_on_failure()`) and stamped into the run manifest. | That a "CUDA" row is CUDA. This tier exists **because it already failed once** (§4b). |

**T1 is the acceptance bar; T0 and T3 are hard preconditions; T2 is recorded, not gated.**
Deliberately *not* proposed: bit-exactness, and any tier defined on the *value* head
(the `fair-netprior` arm severs the net's value — grading a head nobody reads is how
CL-067's confusions started).

**Precedent for pre-registering the fallback branches**, modelled on the eqtime gate's
A/B/C/D structure: the branches in §7 are fixed *before* the cell runs, and the cell is
read off the pre-committed branch that fires, not off whichever framing looks best
afterwards.

---

## 6. Measured `r` — the prototype's numbers

### 6.1 The ORT prototype

`rust/carc/carc-net/src/bin/bench_r.rs`, min over 60 reps, denominator
`search_ms_per_sim = 0.0903` ms (§2.1). `per_leaf_ms = forward_ms / batch`;
`r = per_leaf_ms / 0.0903`:

| backend | batch | forward ms (min) | per-leaf ms | **r** | vs bar 1.5 |
|---|---|---|---|---|---|
| ORT CPU (1 thread) | 1 | 15.435 | 15.435 | 170.9 | fails |
| ORT CPU (1 thread) | 8 | 115.903 | 14.488 | 160.4 | fails |
| ORT CPU (4 threads) | 1 | 4.705 | 4.705 | 52.1 | fails |
| ORT CPU (4 threads) | 8 | 32.261 | 4.033 | 44.7 | fails |
| ORT CPU (4 threads) | 64 | 317.553 | 4.962 | 55.0 | fails |
| ORT CPU (8 threads) | 8 | 24.201 | 3.025 | 33.5 | fails |
| **ORT CUDA (eager)** | **1** | **2.018** | **2.018** | **22.34** | fails |
| **ORT CUDA (eager)** | **8** | **1.880** | **0.235** | **2.60** | fails |
| **ORT CUDA (eager)** | **64** | **9.032** | **0.141** | **1.56** | ~at bar |
| ORT CUDA + graph | any | — | — | — | **panics, see §6.2** |

Two sanity checks pass. ORT CUDA eager (2.018 / 1.880 / 9.032 ms) tracks torch CUDA eager
(2.396 / 2.184 / 7.191 ms) closely, as it should — same device, same graph, different
runtime. And the batch-1→batch-8 curve is nearly flat (2.018 → 1.880 ms for **8× the
work**), which is the signature of a launch-bound workload and the reason batching is the
lever. ⚠️ The `cpu(8)` rows are visibly noisier than `cpu(4)` (8 pinned cores contending
with the live eval); CPU rows are upper bounds, and they fail by two orders of magnitude
anyway, so nothing turns on them.

### 6.2 ⚠️ The CUDA-Graph lever is REAL but NOT REACHED through `ort` here

This is the most important caveat in the memo and it cuts against the recommendation.

* **The lever is real and measured**: §2.2, torch in-process, batch-1 **2.396 → 0.339 ms
  (7.1×)** and batch-8 **0.273 → 0.146 ms/leaf**. That is not a projection.
* **The prototype cannot currently reach it.** `Backend::CudaGraph` panics inside ORT's
  own value layer (`expected 'typeinfo_ptr' to not be null`). The diagnosis is not
  mysterious: ORT captures a CUDA Graph only when inputs and outputs live in **device**
  memory bound via `IOBinding`, and this evaluator hands it host slices, so there is
  nothing stable to capture. **This is an implementation gap in the prototype, not a
  property of ORT** — but it is unfixed, so no ORT graph number is claimed.

**Therefore the honest reading of §6.1 is: on the forward path this prototype actually
achieves today, `r = 2.60` at the decision-relevant batch 8, and the design does NOT
clear its bar.**

### 6.3 Where that leaves the break-even

Applying §3's substitution correction (`cost_ratio ≈ 0.5 + r`) against the gate's own
recorded break-even of **~2.4–2.6×**:

| forward path | per-leaf ms @ batch 8 | `r` | `cost_ratio ≈ 0.5 + r` | vs break-even ~2.4–2.6 |
|---|---|---|---|---|
| Python era, carc-orch batch-1 (measured, CL-067) | 4.199 | — | **~4.0× (measured)** | ❌ the reason the line closed |
| **ORT CUDA eager, batch 8** (this prototype) | 0.235 | 2.60 | **~3.10×** | ❌ still outside |
| **torch CUDA + Graph, batch 8** (achievable, not yet in Rust) | 0.146 | 1.62 | **~2.12×** | ✅ **inside, for the first time** |

**That single row is the finding.** The Rust port plus k-world batching plus CUDA-Graph
capture is, on measured inputs, the first configuration that puts the netprior arm on the
right side of its own break-even — and **all three are required**. Drop graph capture and
it reads 3.10× and fails. ⚠️ It is arithmetic with measured inputs, not a measured agent
(§3), and the `0.5` sweep credit is a mid-game average over a fraction that ranges
0.30–0.64 by ply.

⚠️ **Batch 64 is not available to this search.** A k=8 PIMC search has at most 8 leaves in
flight; the 64 rows are a throughput reference, not a deployable configuration. Reaching
64 would require batching across *moves* (pondering) or across *games*, which is a
different lever with its own design.

### 6.4 Faithfulness — the prototype vs torch on 1200 real positions

`rust/carc/carc-net/src/bin/faithful.rs`, batch 8, against torch batch-1 reference priors
carried inside the position dump. Positions are the champion's own self-play corpus
(`distill_strong_20260723/iter_03/*.npz`, 9 files); **32 of 1200 rows have no legal action
at all** (terminal/aux corpus records) and are excluded and counted rather than silently
scored, leaving **n = 1168**.

| backend | n | argmax | top-5 (ordered) | bit-exact | max abs | max TV |
|---|---|---|---|---|---|---|
| ORT CPU (4 threads) | 1168 | **100.00%** | **100.00%** | 194 | 6.41e-7 | 6.66e-7 |
| ORT CUDA (eager) | 1168 | **100.00%** | **99.40%** | 179 | 4.93e-4 | 4.94e-4 |

**Both clear T1** (argmax ≥ 99.5%, top-5 ≥ 99%). Three things a reader should not
over-read:

1. ⚠️ **The CUDA residual is ~2000× the CoreML/ANE path's 2.4e-7, and the cause is
   identifiable: TF32.** ORT's CUDA EP enables TF32 for conv and matmul by default; TF32
   carries a 10-bit mantissa, which puts relative error right at the observed ~5e-4. It
   cost **zero** argmax disagreements and **0.6%** of top-5 *orderings*. `ort` exposes
   `CUDA::with_tf32(false)` — the trade (tighter residual for slower convs) should be a
   deliberate, benched choice, not a default nobody looked at.
2. ⚠️ **The bit-exact counts (194 / 179) are NOT evidence of fidelity.** The corpus has a
   median of **6** legal moves; a row with one legal action has prior exactly `1.0` under
   any arithmetic. These counts are degenerate rows, and that is precisely why the
   acceptance tiers are built on argmax and top-5 rather than on equality.
3. The CPU row's 6.4e-7 is the same order as `coreml_evaluator`'s measured 2.4e-7 host
   softmax residual, i.e. the fp32 CPU path is as faithful as the project's existing
   accepted backend.

---

## 7. Recommendation, and the gate

### 7.1 The recommendation

**Adopt `ort` (ONNX Runtime) behind `carc_core::eval::PolicyEvaluator` — but the shipping
configuration is `ort` + CUDA-Graph capture + k-world batching, and CUDA-Graph capture is
the one piece that does not work yet (§6.2). So the recommendation is `ort`
CONDITIONALLY, and the first work item is a spike, not an integration.**

Stated as a decision rule rather than a preference:

> **Spike first (≈half a day): get `Backend::CudaGraph` working through `ort` via
> `IOBinding` with device-resident input/output buffers, and re-run `bench_r`.**
> * If batch-8 per-leaf lands **≤ ~0.18 ms** (`r ≤ ~2.0`, `cost_ratio ≤ ~2.5`, i.e. inside
>   the gate's own recorded break-even) → **proceed to §7.4's build and then the §7.3
>   gate.**
> * If it does not → **stop.** `ort` eager is `r = 2.60` / `cost_ratio ≈ 3.10` (§6.3),
>   outside break-even, and the honest conclusion is that the rust net arm is not worth
>   building on this hardware. Record it and leave the net arms in Python.

That spike is cheap and it is genuinely decisive, which is exactly the property worth
buying. One line each on why not the others:

| option | why not |
|---|---|
| **(a) PyO3 → torch** | Best fidelity, but the GIL convoys the k world threads at **254 µs per 8-thread round** (§4a) — more than the search and the forward combined. The fix is an inference server inside the search. **Keep it as the faithfulness ORACLE**, which is how it is used here. |
| **(c) candle** | No CUDA Graphs ⇒ forfeits the 7× that makes this viable; hand-built graph adds a new bit-exactness surface for no latency win. |
| **(d) tch / libtorch** | Same kernels as torch and already in-repo, but **no CUDA-Graph binding** ⇒ stuck at the eager latency that already failed in Python. ~2 GB dep, no Android, no WASM. Becomes the best option the day `tch` exposes graph capture. |
| **(b) tract** | Perfect portability, CPU-only latency two orders too slow for clocked play. Reserve for a Phase-5 on-device *analyzer*, never for search. |

Three properties make `ort` the pick: CUDA-Graph capture (the 7× lever), a genuine
Android story (NNAPI / QNN / XNNPACK EPs), and ONNX being a fourth flavour of a graph the
project already exports three ways — so the export inherits the existing
assert-equivalence-before-writing discipline rather than inventing a new one.

### 7.2 What I am NOT recommending

**Not** funding a strength cell yet, and **not** wiring the evaluator into search on the
strength of this memo. The forward path is proven; the *agent* is not. Two things stand
between here and a net arm, and both are real work (§7.4).

### 7.3 The gate — one cell, branches fixed in advance

Modelled on the CL-067 gate's A/B/C/D structure, which fixed its rules in `df93dcc`
before any result existed. **Precondition:** acceptance tiers T0, T1 and T3 from §5 all
pass, published, before the cell is launched.

The cell: **Rust `fair-netprior` (net policy priors + frozen `curve125` leaf value) vs
the deploy champion, n=400 deck-paired on a fresh band, at a budget whose MEASURED
per-move cost ratio is 1.00 ± 0.10** — sims chosen by a timing probe, never by
arithmetic, exactly as the eqtime gate insisted.

| branch | condition | consequence |
|---|---|---|
| **A** | both statistics ≥ +2σ | Rust net arm is stronger at equal clock ⇒ fund integration + a promotion protocol. |
| **B** | elo ≥ 0 and ≥1 statistic ≥ +1σ | Wall-clock-competitive ⇒ fund integration; no promotion without a confirm on a second band. |
| **C** | both inside ±2σ | **WASH** ⇒ the port did not rescue the line; net arms stay Python and this memo becomes the record of why. |
| **D** | both ≤ −2σ | Kill the rust net arm for deploy. The distilled policy is a Phase-5 analyzer asset. |

**Kill-switch before the cell:** if the measured cost ratio cannot be brought to within
[0.90, 1.10] at any sims setting, the cell does not run — that was the eqtime gate's own
accept rule and it is what makes the result mean anything.

⚠️ **Band discipline applies in full:** claim the band in `governance/BAND_REGISTRY.csv`,
use a within-band deck-paired contrast (the robust class), and do **not** pool across
bands — CL-068's 1.8–2.2× cross-band over-dispersion is live practice.

### 7.4 What a full net-arm port costs from here

| work item | size | note |
|---|---|---|
| **Port `encode_board` to Rust** | **the big one — days, not hours** | 81 planes (16 edge + tile/shield/chapel + 6 road + 6 city + 10 meeple + 8 farmer + 16 reference-tile + 12 reference-pair + last-placed, plus 3 sighted farm-connectivity planes) and 42 scalars incl. the 32-wide bag histogram, plus `compute_window_offset`. Needs its own bit-exactness gate against `flat_repr_cy` — the existing Cython port set the precedent at 28,988 encodes / 0 mismatches. **The prototype deliberately sidesteps this by taking pre-encoded tensors.** |
| **k-world batching + rendezvous** | moderate | The indexed NEVER-TRIED lever *"batch the k determinizations into ONE eval request"*. Worlds reach expansions at different rates, so a strict barrier stalls: gather whatever forwards are pending per round and **pad to k** (fixed-shape CUDA graphs need static batch; padding wastes compute only). Per-world determinism is preserved — batching changes scheduling, not any world's inputs or outputs. |
| **PyO3 surface** (`PolicyEvaluatorRs`) + evaluator plumbing in `search` | small | `evaluate()` gains a prior *source*; the classical path must stay byte-identical when no evaluator is attached (the `Default`-is-today's-behaviour discipline `use_leaf_scratch` and `parallel_workers` already follow). |
| **ONNX export in the release path** + onnxruntime pinning | small, but **recurring** | §4b: the CUDA 12/13 fail-open makes an EP-provenance assert mandatory, and an `ort` upgrade and an onnxruntime upgrade are one change, not two. |
| **CUDA-Graph via `IOBinding`** | **the gating spike, ~half a day** | §6.2/§7.1. Everything below is worthless if this does not land. |
| **Acceptance + gate** (§5, §7.3) | one cell | ~n=400 deck-paired on a fresh band. |

**Honest total: this is a multi-day build with a genuine bit-exactness sub-project inside
it (the encoder), gated on a cell that may well fire branch C.** The prototype exists
precisely so that the cost of finding that out was one session and not one week.

---

## 8. What exists now, and how to reproduce it

**New code (all additive; no existing surface changed).**

| path | what |
|---|---|
| `rust/carc/carc-core/src/eval.rs` | The seam: `PolicyEvaluator` trait, `NetRep`, `masked_softmax`, `legal_argmax`, `FaithfulnessReport`. **Zero dependencies** — `carc-core` stays WASM/iOS-buildable. 5 unit tests. |
| `rust/carc/carc-core/examples/evalprobe.rs` | The denominator probe: ms/sim, leaf evals/sim, isolated leaf µs, child-sweep cost and fraction. |
| `rust/carc/carc-net/` | The ORT backend — **an independent workspace, `exclude`d from `rust/carc`** so the gated `Cargo.lock` is untouched. `OrtPolicyEvaluator`, the `CARCPOS1` position reader, `bench_r`, `faithful`. |
| `rust/carc/carc-net/tools/export_onnx.py` | Policy-only fixed-batch ONNX export with a bit-identity assertion before writing (T0). |
| `rust/carc/carc-net/tools/dump_positions.py` | Real corpus positions + torch reference priors into one flat binary, so both sides see identical inputs. |
| `src/carcassonne_ai/rust_agent.py` | **Additive only:** `NET_ARM_REOPEN_R_BAR`, `net_arm_backend_status()` — a probe that makes "net arms are Python" an asserted fact with a reason, not an accident. |
| `tests/rustport/test_net_seam.py` | 5 contract tests for the probe. |

**Reproduce.** ORT's CUDA EP needs a CUDA-12 onnxruntime on this box (§4b):

```bash
# 1. export the policy graph at fixed batches (needs `onnx` in the venv)
python3 rust/carc/carc-net/tools/export_onnx.py --out-dir <dir> --batches 1 8 64
# 2. dump >=1000 corpus positions + torch reference priors
python3 rust/carc/carc-net/tools/dump_positions.py --out <dir>/positions.bin --n 1200
# 3. the denominator
cargo build --release --example evalprobe -p carc-core --manifest-path rust/carc/Cargo.toml
./rust/carc/target/release/examples/evalprobe 12345 10,20,30,40,50,60,70 3
# 4. the numerator + faithfulness (ORT_LIB_LOCATION must point at a CUDA-12 onnxruntime)
cargo run --release --bin bench_r  --manifest-path rust/carc/carc-net/Cargo.toml -- <dir>
cargo run --release --bin faithful --manifest-path rust/carc/carc-net/Cargo.toml -- <dir> <dir>/positions.bin 8
```

**Owed housekeeping (not done here, to avoid colliding with concurrent sessions):** a
[`docs/LEVER_INDEX.md`](LEVER_INDEX.md) row for **CUDA Graph capture** (currently zero
hits anywhere in the repo) and for **rust-side net evaluation**, and a cross-reference
from the existing never-tried row *"batch the k determinizations into ONE eval request"*,
which this memo gives its first measured number.
