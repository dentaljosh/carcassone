# Pixel 9 Pro / Tensor G4 — LiteRT delegate ladder for the CL-067 distilled net

**STATUS: MEASURED / COMPLETE 2026-07-29. Latency + numerical-agreement only — NO strength claim,
no games played, `governance/PRODUCTION.yaml` untouched, no lever proposed or adopted, the shipped
Android app unchanged.** Every number below is parsed off a file on disk by
[`scripts/pixel_npu/phone_bench/parse_ladder.py`](../scripts/pixel_npu/phone_bench/parse_ladder.py);
none is transcribed from terminal scrollback.

Stage **"Eff Jensen"**. Companion to the Apple side,
[`m5_bench_20260728/M5_BENCH_READOUT_20260728.md`](m5_bench_20260728/M5_BENCH_READOUT_20260728.md),
which measured the same net's batch-1 forward at **0.42 ms on the M5's ANE** (fp16, all 52 ops on
the NPU, zero fallback) vs 2.6 ms torch-CPU on that box. DECISIONS 2026-07-28 named the Android
equivalent route as *"Pixel Tensor NPU via LiteRT (one artifact, per-vendor delegates)"*. This is
that route, built and run.

Raw logs, artifacts and JSON: `/mnt/c/carc-shared/pixel_npu_20260729/`.
Build + bench scripts: [`scripts/pixel_npu/`](../scripts/pixel_npu/).
Runbook: [`scripts/pixel_npu/phone_bench/RUNBOOK_PIXEL.md`](../scripts/pixel_npu/phone_bench/RUNBOOK_PIXEL.md).

---

## 0. Headline

| | |
|---|---|
| **The Tensor G4 NPU is not reachable.** `google-edgetpu` *is* enumerated by NNAPI, but refuses this model in all three precisions we can build | float + dynamic-int8 → **silent fallback to CPU**; full-integer → **hard `ANEURALNETWORKS_BAD_DATA`** |
| Best **faithful** number (argmax-identical to torch on all 60 real positions) | **7.76 ms** — fp16 artifact, GPU delegate, 55/55 nodes, **3.00×** the phone's CPU baseline |
| Best faithful **single-threaded** number (the regime the deployed evaluator is actually in) | **10.99 ms** — fp32 + XNNPACK `force_fp16`, **2.12×** |
| Phone CPU baseline, 1 thread, no XNNPACK | **23.27 ms** |
| Fastest number on the board, but **fidelity-degraded** | 2.00 ms — int8-dynamic, XNNPACK 4-thread, 11.66× (see §4: costs 3/60 argmax flips) |
| vs the M5's ANE (0.42 ms) | the Pixel's best faithful path is **≈18× slower** |
| vs the M5's torch-CPU (2.6 ms) | the Pixel's best faithful path is **≈3× slower** |

**The one-line answer to the question this stage asked:** the ANE's 0.42 ms does **not** transfer
to the device we ship on. It is an Apple-silicon fact. On the Pixel the reachable ceiling for a
third-party app is the GPU delegate at ~7.8 ms, and the accelerator that would plausibly close the
gap is present in the SoC but closed to us.

---

## 1. What was built

`scripts/pixel_npu/convert_litert.py` converts
`/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt`
(sha256 `6e2679908d79a76c…`, verified before and after every copy; 7,509,167 params, 96×6 ResNet,
81ch + 42 scalars, `value_global_pool=True`) into four `.tflite` artifacts.

| artifact | size | ops | role |
|---|---:|---:|---|
| `cl067_iter03_fp32.tflite` | 30.06 MB | 38 | baseline / apples-to-apples |
| `cl067_iter03_fp16.tflite` | 15.06 MB | 64 | **the deployable artifact** — GPU-delegate target |
| `cl067_iter03_int8dyn_EXPERIMENTAL.tflite` | 7.59 MB | 38 | EXPERIMENTAL, see §4 |
| `cl067_iter03_int8full_EXPERIMENTAL.tflite` | 7.64 MB | 43 | EXPERIMENTAL, built only to test the EdgeTPU; **failed, see §4** |

The converter reports 1.346 G arithmetic ops / 0.673 G MACs per forward.

### 1a. Toolchain — `ai-edge-torch` no longer exists under that name

The brief named `ai-edge-torch`. That package is now a **deprecation shim**: PyPI `ai-edge-torch`
0.7.2 is classified `Development Status :: 7 - Inactive`, its only dependency is `litert-torch`,
and its description is *"⚠️ Package Renamed"*. The live converter is **`litert-torch`**. All pins,
from the emitted `MANIFEST.json`:

```
litert-torch      0.9.2        ai-edge-quantizer  0.8.0        jax / jaxlib  0.11.0
litert-converter  0.3.0        torch              2.11.0+cpu   numpy         2.5.1
ai-edge-litert    2.1.6        torchao            0.17.0+cpu   flatbuffers   25.12.19
python 3.12.3     (dedicated uv venv — the project .venv was never touched)
```

### 1b. One conversion failure, fixed exactly — `amax`

The stock module does not convert. `litert-torch`'s NHWC layout pass has no rewriter for the
`x.amax(dim=(2,3))` in the global-pooling value head:

```
RuntimeError: NHWC node rewriter not found: amax
```

`amax` over the spatial dims is global max pooling, so the export wrapper substitutes
`F.max_pool2d(x, kernel_size=(H,W)).flatten(1)`. Max is order-independent, so this is **exact, not
an approximation** — and the converter refuses to export until it has proven so against the
unmodified `CarcassonneNet.forward`. Measured difference: **policy 0.0, value 0.0** (bit-identical,
n=8). Recorded in `MANIFEST.json` as `export_wrapper_equivalence`.

No ONNX/onnx2tf fallback was needed.

---

## 2. Desktop agreement — LiteRT CPU interpreter vs torch fp32

`scripts/pixel_npu/verify_agreement.py`, against 32 random inputs **and 60 real positions**
replayed from the frozen M5 bundle's `positions.jsonl` and encoded through the same sighted
(81ch/42-scalar) encoder the deployed evaluator uses. The real positions carry their **legal-move
masks** — the policy head has 2511 logits but a real position has a median of 11 legal moves, so
argmax over the legal set is the metric that corresponds to the move the agent would actually
play. Full JSON: `verify_agreement_20260729T000840.json`.

| artifact | value max\|Δ\| | policy logit max\|Δ\| | **legal argmax** | top-5 overlap | masked-prob max\|Δ\| |
|---|---:|---:|:--:|---:|---:|
| fp32 | 1.5e-06 | 3.1e-05 | **60/60** | 100.0% | 4.9e-07 |
| fp16 | 6.4e-04 | 2.8e-02 | **60/60** | 100.0% | 4.5e-04 |
| int8dyn | 1.2e-01 | 1.29 | 57/60 | 99.0% | 2.1e-02 |
| int8full | **7.9e-01** | 16.4 | 57/60 | 98.0% | 1.97e-01 |

(Real-position columns; the random-input columns are in the JSON and are uniformly worse, as
expected — a real board is ~93% zeros and N(0,1) noise is far off-distribution.)

**fp16 is free.** Zero argmax changes, identical top-5, value deviation ~6e-4 on a [-1,1] range.
That is the artifact to deploy.

⚠️ **This is CPU-interpreter agreement and nothing else.** A GPU or NPU delegate may reassociate
float arithmetic, accumulate in fp16, or fall back for part of the graph, so **delegate agreement
can only be measured on-device** — by capturing phone-side outputs and re-running this comparison
against them. That was **not** done tonight; only latency was measured on the phone. A clean bill
of health here is necessary, never sufficient.

---

## 3. On-device delegate ladder

**Method.** `scripts/pixel_npu/phone_bench/run_ladder.sh` → 17 cells, each `num_runs=200` after
`warmup_runs=50`, raw output teed per cell; `parse_ladder.py` → `LADDER.json` / `LADDER.md`.
Device: **Pixel 9 Pro** (`caiman`), **Tensor G4**, Android **17**. Reached by **adb over the
tailnet** (`100.64.4.100:38361`) from WSL2 — see RUNBOOK §2.

⚠️ **Thermal / power caveat.** The phone was **on AC power** for the ladder, battery 52→55%, case
temperature **37.5 °C** and already warmed by earlier exploratory runs. These are *warm* numbers.
An earlier cold-ish standalone run of the same `gpu_fp16` cell gave 8.86 ms vs the ladder's 7.76 ms
— so treat cross-cell differences under ~15% as noise, and don't compare these against a
cold-device number from another session.

| config | model | requested | actually executed by | nodes | avg ms | median | min | vs base |
|---|---|---|---|---|---:|---:|---:|---:|
| `cpu1_fp32` | fp32 | CPU builtin | CPU builtin | — | 23.27 | 22.74 | 21.55 | 1.00× |
| `xnn1_fp32` | fp32 | XNNPACK | XNNPACK | 37/37 | 22.81 | 22.39 | 21.28 | 1.02× |
| `xnn4_fp32` | fp32 | XNNPACK | XNNPACK | 37/37 | 8.80 | 8.73 | 8.32 | 2.64× |
| `xnn1_fp32_forcefp16` | fp32 | XNNPACK | XNNPACK | 37/37 | **10.99** | 10.98 | 10.44 | 2.12× |
| `gpu_fp16` | fp16 | GPU | GPU | **55/55** | **7.76** | 7.57 | 5.95 | **3.00×** |
| `gpu_fp32_exact` | fp32 | GPU | GPU | 37/37 | 10.74 | 10.34 | 9.28 | 2.17× |
| `gpu_fp32_lossy` | fp32 | GPU | GPU | 37/37 | 8.21 | 7.86 | 6.78 | 2.83× |
| `nnapi_default_fp32` | fp32 | NNAPI | **XNNPACK — FELL BACK** | 37/37 | 23.43 | 23.64 | 21.15 | 0.99× |
| `nnapi_edgetpu_fp32` | fp32 | NNAPI | **XNNPACK — FELL BACK** | 37/37 | 23.83 | 24.10 | 21.94 | 0.98× |
| `nnapi_reference_fp32` | fp32 | NNAPI | NNAPI (CPU ref) | 37/37 | 32.49 | 32.70 | 30.05 | 0.72× |
| `xnn1_int8dyn` | int8dyn | XNNPACK | XNNPACK | 37/37 | 4.08 | 4.07 | 3.81 | 5.71× |
| `xnn4_int8dyn` | int8dyn | XNNPACK | XNNPACK | 37/37 | **2.00** | 1.95 | 1.81 | 11.66× |
| `gpu_int8dyn` | int8dyn | GPU | GPU | 37/37 | 7.92 | 7.69 | 7.02 | 2.94× |
| `nnapi_edgetpu_int8dyn` | int8dyn | NNAPI | **XNNPACK — FELL BACK** | 37/37 | 4.01 | 4.00 | 3.81 | 5.80× |
| `xnn1_int8full` | int8full | XNNPACK | XNNPACK | 42/42 | 3.84 | 3.83 | 3.65 | 6.06× |
| `gpu_int8full` | int8full | GPU | GPU | 42/42 | 12.40 | 12.44 | 9.96 | 1.88× |
| `nnapi_edgetpu_int8full` | int8full | NNAPI | **REJECTED — hard failure** | — | — | — | — | — |

Four of seventeen cells are silent CPU fallbacks. `parse_ladder.py` labels them from the tool's own
delegate statements — without that guard, `nnapi_edgetpu_int8dyn` at 4.01 ms reads like an EdgeTPU
result, and it is a CPU result.

### 3a. The EdgeTPU verdict, in detail

NNAPI enumerates `[google-edgetpu, nnapi-reference]` — the TPU block **is** advertised. Then:

- **fp32 / fp16 graphs** → `Though NNAPI delegate is explicitly applied, the model graph will not
  be executed by the delegate` → XNNPACK runs it. Same latency as plain CPU.
- **dynamic-int8 graph** → same silent refusal.
- **full-integer int8 graph** (built specifically for this test, activations calibrated on the 60
  real positions) → hard failure:
  ```
  ERROR: NN API returned error ANEURALNETWORKS_BAD_DATA at line 1132 while adding operation.
  ERROR: Failed to apply NNAPI delegate.
  ```

So the negative is not "we didn't feed it the right precision" — we built and fed all three, and
the full-integer attempt is the one that fails *loudly*. This matches the desk research: Google's
Tensor ML SDK (LiteRT-Next `Accelerator.NPU`) is Beta for **Pixel 10 / Tensor G5 only**, and
Google's own answer on google-ai-edge/LiteRT#969 is that there is no public TPU delegate for
Pixel Tensor TPUs and third-party apps should use the GPU delegate. Citations in RUNBOOK §6.

### 3b. Costs the latency column hides

- **GPU delegate init is 2.4–3.2 s** (shader compilation) versus 9–114 ms for every CPU path, and
  6.9 s for `gpu_int8full`. For an app that evaluates a position per move this is amortized; for
  one that starts and stops, it is not.
- **GPU peak memory 261–363 MB** versus 28–73 MB for XNNPACK. The int8 CPU paths are the smallest
  footprint on the board (28.6–30.2 MB).
- The **single-thread** column is the one that matters for the deployed evaluator
  (`make_remote_single_evaluator`: k=1 per request, worker blocks — no batching, no thread-parallel
  win to hide behind). `xnn4_*` rows are reported for completeness only.

---

## 4. The int8 artifacts — one is marginal, one is a failure

**`int8dyn` — marginal, not free.** 5.71× single-thread, but 3 of 60 positions change their
argmax. Mitigating detail: all three flips are near-ties in the reference (logit gaps 0.037,
0.047, 0.039), and top-5 overlap stays at 99%. So the *policy* damage is plausibly small — but
"plausibly small" is not a measurement, and the value head's max deviation of 0.12 on a [-1,1]
range is not obviously ignorable. **Deploying this needs an elo measurement, not an argmax
statistic.**

**`int8full` — a documented negative result, do not use.** Full-integer quantization destroys the
value head: **max |Δ| = 0.787 on a range of [-1, 1]**, mean |Δ| = 0.349. That is not a degraded
value estimate, it is noise. (Its legal-argmax survives at 57/60 only because the policy logits are
comparatively robust; on random inputs argmax agreement is **0.0%**.) It also failed at its one
purpose — the EdgeTPU rejected it anyway. It is retained on the share purely as evidence for §3a.

---

## 5. How this slots into Eff Jensen

CL-067 confirmed the distilled policy priors beat the deploy champion at equal sims (+35.7 elo
pooled, n=800 deck-paired) but refuted deployability on **cost**: the net-prior agent measured
4.24× the champion's per-move wall clock, and the claim's close-out named the open problem as
*"the net must get ~4× cheaper per move"*. The M5/ANE result made that look eminently solvable.
The Pixel result is more sober:

- On the phone's own terms the forward gets **3.00× cheaper** on the GPU delegate with **zero**
  fidelity loss, or **5.71×** single-threaded with a fidelity cost that has not been priced.
- ⚠️ **A speedup on the forward is not the same as a speedup per move**, and nothing here converts
  one into the other. The 4.24× figure is a whole-agent per-move ratio; the fraction of that which
  is net-forward has not been measured on the Pixel. Whether 3× on the forward clears the CL-067
  bar is **an open question this memo does not answer** — and it is the obvious next measurement.
- The Apple-vs-Pixel gap is the durable finding: **0.42 ms → 7.76 ms, ≈18×**, for the identical
  net and equivalent-intent toolchains. Any plan that leaned on "NPUs make this forward nearly
  free" holds on Apple silicon and does not hold on the device we ship on.

**What remains unknowable without further work** (i.e. was *not* measured tonight):
1. **Delegate numerical agreement.** Only latency was taken on-device. Whether the GPU delegate's
   outputs still argmax-match torch is unmeasured — it requires capturing phone-side outputs, not
   just timings. This is the highest-value cheap follow-up, and it gates calling fp16-on-GPU
   "faithful" on the phone rather than merely on the desktop interpreter.
2. **Cold-device numbers.** Everything here is warm and on AC.
3. **Whether Tensor G5 / Pixel 10 changes the answer** — the Tensor ML SDK targets exactly that
   hardware, so the NPU question reopens on a Pixel 10 and stays shut on this phone.
4. **Any elo consequence of anything above.** No games were played.

---

## 6. Files

On the share, `/mnt/c/carc-shared/pixel_npu_20260729/`:

| file | what |
|---|---|
| `cl067_iter03_{fp32,fp16}.tflite` | the artifacts; fp16 is the deployable one |
| `cl067_iter03_int8{dyn,full}_EXPERIMENTAL.tflite` | see §4 — not deploy candidates |
| `MANIFEST.json` | converter versions, checkpoint sha256, per-artifact sha256 + op census, wrapper-equivalence proof |
| `verify_agreement_20260729T000840.json` | §2 in full, incl. per-disagreement detail |
| `positions_encoded.npz` | the 60 real encoded positions + legal masks (also the int8full calibration set) |
| `phone_results/LADDER.{json,md}` | §3, parsed |
| `phone_results/*.log` | the 17 raw `benchmark_model` outputs |
| `phone_results/device_state_{before,after}.txt` | device identity, battery, thermal |
| `benchmark_model_android_aarch64` | sha256 `5d45116eb86e3a23…`, nightly build, arm64 |
| `benchmark_model.apk` | sha256 `2f8e4bd51671013e…`, fallback if the raw binary can't load GPU libs |

In the repo: [`scripts/pixel_npu/`](../scripts/pixel_npu/) —
[`convert_litert.py`](../scripts/pixel_npu/convert_litert.py),
[`verify_agreement.py`](../scripts/pixel_npu/verify_agreement.py),
[`encode_positions.py`](../scripts/pixel_npu/encode_positions.py),
[`phone_bench/run_ladder.sh`](../scripts/pixel_npu/phone_bench/run_ladder.sh),
[`phone_bench/parse_ladder.py`](../scripts/pixel_npu/phone_bench/parse_ladder.py),
[`phone_bench/RUNBOOK_PIXEL.md`](../scripts/pixel_npu/phone_bench/RUNBOOK_PIXEL.md).

Neither `src/carcassonne_ai/` nor `engine/` was touched; the encoder was driven from the frozen
2026-07-28 M5 bundle so no live cluster run could be perturbed.
