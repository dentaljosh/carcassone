# RUNBOOK — CL-067 net forward on the Pixel 9 Pro (Tensor G4), via LiteRT

**STATUS: EXECUTED 2026-07-29.** The Pixel became available and the whole ladder was run — see
[`measurement/PIXEL_NPU_PREP_20260729.md`](../../../measurement/PIXEL_NPU_PREP_20260729.md) for
the numbers and `/mnt/c/carc-shared/pixel_npu_20260729/phone_results/` for the raw logs. This
file remains the runbook: it is what `phone_bench/run_ladder.sh` automates, and it is how you
re-run the ladder on another device or after a model change.

**Headline of the executed run:** the `google-edgetpu` NNAPI accelerator **is** enumerated on a
Pixel 9 Pro but **refuses this model in every precision we can build** (float and dynamic-int8
fall back to CPU silently; full-integer fails hard with `ANEURALNETWORKS_BAD_DATA`). The GPU
delegate is the real ceiling. §0 below was written before the run and its prediction held.

**What this measures:** batch-1 forward latency of the CL-067 distilled net (7.51 M params,
96×6 ResNet, 81ch + 42 scalars) on the Pixel, across CPU / XNNPACK / GPU / NNAPI backends.
**Latency only.** It is not a strength claim, it plays no games, and it touches neither
`governance/PRODUCTION.yaml` nor the shipped Chaquopy app.

**Why we care:** CL-067 confirmed the distilled policy priors beat the deploy champion at equal
sims but REFUTED deployability on cost — the net agent measured ~4.24× the champion's per-move
wall clock, so "the net must get ~4× cheaper per move". The Apple M5's ANE answers that with a
**0.42 ms** batch-1 forward (fp16, all 52 ops on the NPU, zero CPU fallback) vs 2.6 ms torch-CPU
on the same box. This runbook asks the same question of the Pixel, which is the device that
actually ships.

---

## 0. Read this before you plan the session: there is no public Tensor-G4 NPU path

This is the single most important fact in this document, and it was established by desk research
on 2026-07-28 (citations in §6), not by measurement:

> **As of 2026 there is no publicly available delegate that reaches the TPU/EdgeTPU block inside
> a Google Tensor G4.** Google's Tensor ML SDK — the LiteRT-Next `Accelerator.NPU` backend for
> Pixel — went to Beta on 2026-05-19 and its supported-device list is **Pixel 10 / 10 Pro /
> 10 Pro XL / 10 Pro Fold only, i.e. Tensor G5**. Pixel 9 / G4 is not listed. Google's own
> answer on the tracking issue (google-ai-edge/LiteRT#969) is that no separate public TPU
> delegate exists for Pixel Tensor TPUs and that third-party apps should use the **GPU delegate**.

So the honest framing of tonight's Pixel question is **not** "does Tensor's NPU match the ANE's
0.42 ms". It is:

1. **What does the GPU delegate (Mali-G715 on G4) give us?** ← the real, reachable number, and
   the practical ceiling for a third-party app on this phone.
2. **Does the deprecated NNAPI path still route to anything faster than CPU on this device?**
   NNAPI was deprecated in Android 15 but still functions for back-compat. On some Pixels it has
   historically dispatched to the TPU via the `google-edgetpu` driver. **This is the one cheap
   experiment that could still surprise us** — §3 step D exists solely to run it and find out.
3. **What is the XNNPACK CPU baseline?** — the number the shipped app would actually pay today,
   and the denominator for every speedup claim.

If the answer comes back "GPU is the ceiling and it is only ~2× CPU", that is a **complete and
useful result**: it says the ANE's 0.42 ms is an Apple-silicon fact that does not transfer to the
device we ship on, and the CL-067 cost problem stays open on Android. Do not treat that as a
failed session.

---

## 1. What is staged, and where

Everything lives on the share at **`/mnt/c/carc-shared/pixel_npu_20260729/`** (WSL path; from
Windows that is `C:\carc-shared\pixel_npu_20260729\`).

| File | What it is |
|---|---|
| `cl067_iter03_fp32.tflite` | the model, fp32 — the apples-to-apples artifact |
| `cl067_iter03_fp16.tflite` | fp16 weights — what you actually want on the GPU delegate |
| `cl067_iter03_int8dyn_EXPERIMENTAL.tflite` | int8 dynamic weights. **EXPERIMENTAL**, see §4 |
| `benchmark_model_android_aarch64` | prebuilt LiteRT/TFLite benchmark binary, arm64 |
| `benchmark_model.apk` | the same tool as an APK (needed if the raw binary can't load GPU libs) |
| `MANIFEST.json` | converter versions, checkpoint sha256, per-artifact sha256 |
| `verify_agreement_*.json` | the desktop CPU-interpreter agreement result (§5 of the memo) |
| `positions_encoded.npz` | the 60 real encoded positions used for that agreement check |

Exact sha256 for every file is in `MANIFEST.json`. Re-verify after copying to the phone-side
machine — the share is a drvfs mount and a truncated copy is a real failure mode.

---

## 2. Getting adb to the phone from WSL2

WSL2's default NAT'd network cannot see the phone on the LAN, and Android's wireless-debugging
pairing uses mDNS, which does not cross that NAT boundary. `networkingMode=mirrored` is **not** a
reliable fix — it has two live upstream bugs (`adb devices` blocked under mirrored mode,
microsoft/WSL#11397; and a loopback SYN-ACK/ephemeral-port mismatch, microsoft/WSL#40343).

**Use the Windows-side adb server.** This is the path the existing android app already uses
(`android/README.md` §"USB passthrough is awkward from WSL2"):

```bash
# ---- On Windows (PowerShell or cmd), with the phone on the same Wi-Fi ----
# Phone: Settings -> Developer options -> Wireless debugging -> Pair device with pairing code
adb.exe pair 192.168.0.NN:PPPPP        # PAIRING port + the 6-digit code (once per phone)
adb.exe connect 192.168.0.NN:QQQQQ     # the DIFFERENT connect port on the main screen
adb.exe devices                        # expect: <ip>:<port>   device
```

Then, if you want to drive it from inside WSL2, point the WSL client at that server instead of
starting a second one:

```bash
export ADB_SERVER_SOCKET=tcp:$(ip route show default | awk '{print $3}'):5037
adb devices     # should show the same device the Windows server sees
```

Fallbacks, in order: `usbipd-win` to attach the phone's USB device into WSL; or just run every
command below as `adb.exe` from Windows against the `C:\carc-shared\...` copies of the files.

---

## 3. The bench, in the order to run it

**The whole of §3 is automated by `run_ladder.sh` + `parse_ladder.py`** — use those, and read this
section to understand what they do and why each cell exists:

```bash
scripts/pixel_npu/phone_bench/run_ladder.sh            # runs 17 cells, tees raw logs
python3 scripts/pixel_npu/phone_bench/parse_ladder.py \
    --results-dir /mnt/c/carc-shared/pixel_npu_20260729/phone_results
```

`parse_ladder.py` tags every row with the delegate that *actually* executed the graph, parsed
from benchmark_model's own statements — so a silent CPU fallback can never be reported as a
delegate result. That guard is not decorative; it fired on four of the seventeen cells.

The manual commands below are the same thing, one cell at a time. Push once:

```bash
D=/data/local/tmp/carcnpu
adb shell mkdir -p $D
adb push /mnt/c/carc-shared/pixel_npu_20260729/benchmark_model_android_aarch64 $D/benchmark_model
adb push /mnt/c/carc-shared/pixel_npu_20260729/cl067_iter03_fp32.tflite  $D/
adb push /mnt/c/carc-shared/pixel_npu_20260729/cl067_iter03_fp16.tflite  $D/
adb push /mnt/c/carc-shared/pixel_npu_20260729/cl067_iter03_int8dyn_EXPERIMENTAL.tflite $D/
adb shell chmod +x $D/benchmark_model
```

Common flags for every run below — these matter, don't drop them:

```
--num_runs=200 --warmup_runs=50 --report_peak_memory_footprint=true
```

The net is tiny and the phone will DVFS; 200 runs after 50 warmups is enough to get a stable
mean without the run being long enough to thermally throttle. **Record `Inference (avg)` in µs,
and also the min** — the min is the closest thing to an unthrottled number.

### A. CPU baseline, single thread (the honest denominator)

```bash
adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp32.tflite \
  --num_threads=1 --use_xnnpack=false \
  --num_runs=200 --warmup_runs=50
```

This is the "torch-CPU equivalent" rung — compare against the M5's 2.6 ms torch-CPU and the
Pixel's own 1.7 s/move champion figure (`measurement/ANDROID_WALLCLOCK_MEMO_20260728.md`).

### B. CPU with XNNPACK, 1 and 4 threads (what a shipped app would really get)

```bash
adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp32.tflite \
  --num_threads=1 --use_xnnpack=true --num_runs=200 --warmup_runs=50
adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp32.tflite \
  --num_threads=4 --use_xnnpack=true --num_runs=200 --warmup_runs=50
```

⚠️ **The single-thread number is the one that matters for us**, not the 4-thread one. The deployed
evaluator is `make_remote_single_evaluator`: k=1 per request and the worker *blocks*, so there is
no batching and no thread-parallel win to hide behind. Report 4-thread for completeness only.

Also worth one run: `--use_xnnpack=true --xnnpack_force_fp16=true` on the fp32 graph — XNNPACK can
run fp16 arithmetic on ARMv8.2 cores and G4 has them.

### C. GPU delegate — **the number this session exists to get**

```bash
adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp16.tflite \
  --use_gpu=true --gpu_precision_loss_allowed=true \
  --num_runs=200 --warmup_runs=50
```

Then the fp32 graph through the same delegate, so you can separate "fp16 helped" from "GPU
helped":

```bash
adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp32.tflite \
  --use_gpu=true --gpu_precision_loss_allowed=false \
  --num_runs=200 --warmup_runs=50
```

**Expected pitfall:** the standalone binary may fail to bring up the GPU delegate because it
can't load the platform's OpenCL/EGL libraries from `/data/local/tmp` under the app-less SELinux
context. Symptom is a log line like `Failed to load OpenCL library` or `Could not create GPU
delegate`, followed by a *silent fall back to CPU* — which would hand you a CPU number labelled
GPU. **Guard against this:** the run must print `INFO: Created TensorFlow Lite delegate for GPU.`
and a nonzero count of ops delegated. If it doesn't, switch to the APK, which ships its own
`libtensorflowlite_benchmark.so` and runs inside a normal app context:

```bash
adb install -r -d -g /mnt/c/carc-shared/pixel_npu_20260729/benchmark_model.apk
adb push /mnt/c/carc-shared/pixel_npu_20260729/cl067_iter03_fp16.tflite /data/local/tmp/
adb shell am start -S -n org.tensorflow.lite.benchmark/.BenchmarkModelActivity \
  --es args '"--graph=/data/local/tmp/cl067_iter03_fp16.tflite --use_gpu=true --num_runs=200 --warmup_runs=50"'
adb logcat -s tflite   # the results land in logcat, NOT on stdout
```

### D. NNAPI — the "could still surprise us" experiment

NNAPI is deprecated (Android 15) but present. On Pixels it has historically been the only route
to the Tensor TPU, via a `google-edgetpu` NNAPI driver. First enumerate what the device actually
exposes, then pin to each one:

```bash
# What accelerators does this phone advertise to NNAPI?
adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp32.tflite \
  --use_nnapi=true --num_runs=200 --warmup_runs=50 2>&1 | tee /tmp/nnapi_default.log

# Then pin explicitly. Try each name the log above mentions; likely candidates on a Pixel:
for ACC in google-edgetpu google-armnn nnapi-reference; do
  adb shell $D/benchmark_model --graph=$D/cl067_iter03_fp32.tflite \
    --use_nnapi=true --nnapi_accelerator_name=$ACC \
    --num_runs=200 --warmup_runs=50
done
```

Also try `--nnapi_execution_preference=sustained_speed` (the others are `low_power`,
`fast_single_answer`).

**Expected pitfalls, in likelihood order:**
- The named accelerator doesn't exist → hard error naming the accelerator. That is a *clean*
  negative; write it down verbatim, it is evidence about G4's public surface.
- NNAPI initialises but **partitions the graph** and silently runs most of it on CPU. Watch for
  `Replacing N node(s) with delegate` and compare N against the model's total op count from
  §5's `--print_graph=true`-style output. A partial delegation with a good-looking latency is the
  classic trap here.
- NNAPI reports a *worse* number than XNNPACK. Entirely plausible on a deprecated path for a
  small model where per-inference driver overhead dominates. Record it and move on.

### E. LiteRT-Next / `Accelerator.NPU` — expected to be unavailable, confirm and log

Do **not** budget real time for this. The Tensor ML SDK's NPU backend is documented as Pixel
10 / Tensor G5 only, so on a Pixel 9 Pro the expected outcome is "no NPU accelerator available".
There is also no documented `--use_npu` flag on classic `benchmark_model`; the generic escape
hatch is `--external_delegate_path=<.so>` / `--stable_delegate_loader_settings=<json>`, and we
have no G4 delegate `.so` to point them at. Spend five minutes confirming the negative — a
one-line "confirmed unavailable on G4, dated 2026-07-29" is worth having in writing — then stop.

---

## 4. The int8-dynamic artifact is EXPERIMENTAL — treat its latency as unusable until re-verified

`cl067_iter03_int8dyn_EXPERIMENTAL.tflite` quantizes weights to int8 with fp32 activations. It is
included because it is nearly free to produce and because int8 is often the *only* precision a
mobile NPU path will accept, so having it on hand costs nothing.

**But:** its desktop agreement numbers (in `MANIFEST.json` / the memo) are materially worse than
fp16's, as expected for a policy head with 2511 logits. A latency win on this artifact does not
transfer to a deployable win until someone re-runs the argmax-agreement check and, separately,
someone measures whether the policy degradation costs elo. Benchmark it if you have spare minutes,
but **do not put its number in a headline** and do not compare it against fp16 as if they were the
same model.

---

## 5. What to record

For every configuration you run, capture all of:

| Field | Why |
|---|---|
| exact command line | so the run is reproducible; flags silently change meaning |
| `Inference (avg)` µs **and** `Inference (min)` µs | avg is the honest number, min is the unthrottled bound |
| delegate creation line, verbatim | the ONLY proof the delegate actually engaged |
| ops delegated / total ops | catches silent partial delegation (§3 pitfalls) |
| peak memory footprint | GPU/NNAPI paths can balloon; matters for a phone app |
| phone state | plugged in or not, screen on, battery %, roughly how warm |

Then, per configuration, compute and record **speedup vs the §3-A single-thread CPU baseline on
the same phone** — not vs the M5, not vs the 5900XT. Cross-box ratios go in the memo's discussion,
never in the raw table.

Sanity floor: if *every* backend lands within noise of each other, suspect that none of the
delegates engaged and re-read the creation lines before believing the data.

---

## 6. Sources for the claims in §0

Desk research 2026-07-28; these are the load-bearing citations:

- Tensor ML SDK Beta, device list is Pixel 10 / G5 —
  <https://developers.google.com/edge/litert/next/tensor-sdk> and
  <https://developers.googleblog.com/google-tensor-sdk-beta-with-litert/>
- "no publicly available separate TPU delegate for TFLite for Pixel's Tensor TPUs", Google reply —
  <https://github.com/google-ai-edge/LiteRT/issues/969>
- LiteRT-Next NPU / `CompiledModel` + `Accelerator.NPU`, per-vendor backends —
  <https://developers.google.com/edge/litert/next/npu>
- NNAPI deprecated in Android 15, still functional for back-compat —
  <https://developer.android.com/ndk/guides/neuralnetworks/migration-guide>
- `benchmark_model` flags —
  <https://github.com/tensorflow/tensorflow/blob/master/tensorflow/lite/tools/benchmark/README.md>
- WSL2 mirrored-mode adb bugs — <https://github.com/microsoft/WSL/issues/11397>,
  <https://github.com/microsoft/WSL/issues/40343>

The two binaries in §1 were downloaded 2026-07-28 from the still-live nightly bucket
`https://storage.googleapis.com/tensorflow-nightly-public/prod/tensorflow/release/lite/tools/nightly/latest/`
(`android_aarch64_benchmark_model` and `android_aarch64_benchmark_model.apk`). They are *nightly*
builds, so they are not version-pinned upstream — the sha256 in `MANIFEST.json` is the only
identity they have. If you re-download later you will get a different build; record the new hash
rather than assuming it matches.
