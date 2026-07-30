# eff_linus — LAPTOP replication of the WSL-vs-native-Windows A/B

**STATUS: MEASURED 2026-07-29 (late evening), laptop box.** Second-box replication of
[EFFJENSEN_BENCH_BATCH_20260729.md](../EFFJENSEN_BENCH_BATCH_20260729.md) §4, which ran on
the 5900XT and found the hypervisor tax refuted **with the sign inverted** (native Windows
25% slower). Every number below is read off a committed JSON on disk. `audit.ab_valid:
true`, 24/24 cells `rc=0`.

**MEASUREMENT INFRASTRUCTURE.** Roadmap **G3**, stage "Eff Jensen", sub-effort *eff_linus*.
No games, no elo, no champion or claim can move here.

---

## The verdict in one line

> **The 5900XT result REPLICATES on a second, architecturally different machine: native
> Windows is slower than WSL2 on all four cells, on both boxes. WSL2 is costing this
> project nothing, and "move the hot path to native Windows" is dead on two machines
> rather than one.**

And one genuinely new thing, which is the reason this run was worth more than a checkmark:

> ⚠️ **On a hybrid P-core/E-core CPU, a windowless native-Windows console process launched
> from WSL gets scheduled onto the E-cores and pays an EXTRA ~1.8–2.8× on top of the
> virtualisation delta.** Uncontrolled, the laptop reads 2.16×/2.93× — which would have
> looked like a spectacular divergence from the 5900XT's 1.25×/1.14×. It is not a
> divergence: pin the native arm to P-cores and the laptop lands at **1.06–1.19×**,
> i.e. *the same place as the 5900XT*.

---

## 1. What was provisioned, and how it differs from the 5900XT run

| | 5900XT run (§4) | **laptop run (this)** |
|---|---|---|
| CPU | Ryzen 5900XT, 16C/32T, **homogeneous** | **i7-14650HX, 8 P + 8 E, 24T — HYBRID** |
| GPU | RTX 5060 Ti | RTX 4070 Laptop (8 GB) |
| Windows | 11 build 26200 | 11 build **26100** |
| WSL kernel | 6.6.87.2 | **6.18.33.1** |
| WSL CPython | 3.13.**12** (miniforge) | 3.13.**14** (`uv`/python-build-standalone, Clang 22.1.3) |
| Windows CPython | 3.13.**14** (python.org, MSC v.1944) | 3.13.**14** (python.org, MSC v.1944) |
| CPython patch match across arms | ✗ (a patch apart) | ✅ **exact** |
| numpy / pyyaml | — | **2.5.1 / 6.0.3 on both arms** |
| torch | 2.11.0+cu128 both arms | 2.11.0+cu128 both arms |
| git rev | `c6f0f96` | `17ba2ce` |

Three laptop-specific obstacles, all recorded in the driver header so the next reader does
not rediscover them:

1. **No `winget`** (App Installer absent) — the Windows interpreter came from python.org's
   silent user-scope installer (`/quiet InstallAllUsers=0 PrependPath=0
   Include_launcher=0`, no elevation), which is what winget's `Python.Python.3.13` package
   wraps anyway. The WSL arm came from `uv python install 3.13.14`, pinned explicitly.
2. **The laptop's WSL does not append the Windows PATH**, so the driver's bare `cmd.exe`
   was "command not found". Unfixed, this would have failed *every* win-arm cell.
3. **The share mounts at `/mnt/carc-shared`, not `/mnt/c/carc-shared`** — and a latency
   bench must not read over CIFS anyway, so the M5 bundle and the checkpoint were copied
   to the laptop's own `C:`. `positions.jsonl` md5 **`e36c4d2a…`** verified identical to
   the 5900XT run's, so both boxes searched the same 12 positions.

The driver was made path-portable for this (`EFFL_*` env overrides, commit `17ba2ce`);
the 5900XT invocation is byte-unchanged.

⚠️ **One residual asymmetry, disclosed:** on `net_cuda_b1` the default
`torch_num_threads` is 12 (WSL) vs 16 (Windows), because the two see different core
counts. Irrelevant to a batch-1 CUDA forward (no CPU GEMM on that path) and the `cpu_1t`
cell pins 1 thread on both arms — but it is a difference, so it is stated.

---

## 2. The A/B as run (3 reps × 2 arms × 4 cells, alternating A/B/B/A)

Artifact: `run_laptop_20260729/wsl_vs_native_ab_20260729_223554.json` (48 cell files,
24 ndjson rows). `ab_valid: true`, zero failures — the merger's own check that the arms
differ only by virtualisation. Pure-Python leaf asserted on **both** arms
(`leaf_active: false`), same champion `puct_priors_v29_bmild_cap8`, same ckpt sha
`6e26799…3751a1`.

| cell | metric | WSL2 | native Windows | **ratio (win/wsl)** | spread wsl / win |
|---|---|---|---|---|---|
| `champ_k1x32` | p50 s/move | 0.0950 | 0.1123 | **1.182×** | 1.0% / 1.0% |
| `champ_k4x172` | p50 s/move | 2.2502 | 4.8568 | **2.158×** | 0.3% / 3.9% |
| `net_cuda_b1` | forward p50 ms | 1.0276 | 2.7855 | **2.711×** | 2.7% / 1.7% |
| `net_cpu_1t` | forward p50 ms | 10.7114 | 31.3486 | **2.927×** | 1.0% / 0.4% |

`gap_exceeds_run_spread: true` on all four. Spreads are tight (≤3.9%), so none of these
gaps is noise.

**Native Windows loses every cell — the same direction as the 5900XT, at 1.7–2.6× the
magnitude.** That magnitude gap is what the rest of this memo is about, because taken at
face value it would have been a failed replication.

---

## 3. Two confounds tested before the number was believed

### 3a. `nice -n 19` — REJECTED as the cause

The runbook launches the driver niced. If that priority propagated into the NT child, a
hybrid CPU would demote it. **Tested by re-running the champion cell un-niced, 3 reps,
both arms** (`control_unniced/wsl_vs_native_ab_20260729_225457.json`):

| | wsl | win | ratio |
|---|---|---|---|
| niced (the A/B) | 2.2502 | 4.8568 | 2.158× |
| **un-niced control** | 2.2375 | 4.9272 | **2.202×** |

Identical within noise. **`nice` is not the mechanism** — and note the 5900XT run was
niced too, so this also clears its numbers.

### 3b. It is not thermal, throttling, or time-dependent drift either

The champion cells record **per-decision** samples, and the positions are paired across
arms, so the ratio can be tracked *within* a cell. Across all three reps it is **flat at
~2.14 from the first decision (4 s in) to the last (67 s in)** — no ramp. A thermal or
EcoQoS story predicts a ramp; there is none.

What *does* vary is work per decision. Converting both champion cells to µs/sim:

| box | arm | µs/sim @ k1×32 | µs/sim @ k4×172 | growth |
|---|---|---|---|---|
| 5900XT | wsl | 3547 | 3931 | 1.11× |
| 5900XT | win | 4465 | 4917 | 1.10× |
| laptop | wsl | 2970 | 3271 | 1.10× |
| **laptop** | **win** | **3510** | **7059** | **2.01×** |

**Three of the four arms scale identically; exactly one — laptop native Windows —
blows up.** That is a per-decision *work/footprint* effect, not a clock effect, and it
localised the anomaly to one arm on one box.

---

## 4. ⭐ The mechanism: E-core placement (probe, n=3)

`champ_k4x172`, native-Windows arm only, same 12 positions, varying **only** the CPU
affinity mask (`start /affinity`). `ecore_probe/aff_*.json`:

| native-Windows affinity | p50 s/move |
|---|---|
| one P-core (`0x3`) | 2.746 |
| **all 8 P-cores (`0xFFFF`)** | **2.665** |
| the 8 E-cores (`0xFF0000`) | 4.843 |
| **unpinned — what the A/B measured** | **4.815** |

**The unpinned arm reproduces the E-core-pinned number to within 0.6%.** Windows' Thread
Director is putting this single-threaded, windowless, WSL-launched console process on the
efficiency cores. The WSL arm does not suffer it (its work runs on the VM's vCPU threads).

Re-measured with the native arm pinned to all P-cores, n=3 (median cited, spread in
brackets):

| cell | WSL2 | native Windows **@P-cores** | **controlled ratio** | E-core factor removed |
|---|---|---|---|---|
| `champ_k4x172` | 2.2502 | **2.6654** [0.6%] | **1.185×** | 1.822× |
| `net_cuda_b1` | 1.0276 | **1.2136** [0.9%] | **1.181×** | 2.295× |
| `net_cpu_1t` | 10.7114 | **11.3037** [1.8%] | **1.055×** | 2.773× |

⚠️ `champ_k1x32` was **not** probed pinned. Its as-run ratio (1.182×) already sits in the
controlled band, and its µs/sim growth is the normal 1.10×, so it appears never to have
been demoted — decisions are 0.095 s, evidently too short to trigger migration. That is an
**inference from the scaling table, not a measurement**; it is the one loose end here.

---

## 5. ⇒ The replication, controlled

| cell | 5900XT ratio | laptop ratio (as run) | **laptop ratio (P-core-controlled)** |
|---|---|---|---|
| `champ_k1x32` | 1.259× | 1.182× | 1.182× (unprobed — see above) |
| `champ_k4x172` | 1.251× | 2.158× | **1.185×** |
| `net_cuda_b1` | 1.060× | 2.711× | **1.181×** |
| `net_cpu_1t` | 1.137× | 2.927× | **1.055×** |

**Both boxes land in 1.06–1.26×, native Windows always the loser.** H1 (the CPU/DRAM
nested-paging tax, predicted WSL2 5–20% *slower*) and H2 (the `/dev/dxg` batch-1 tax) are
both refuted on a second machine, sign inverted again.

**Two ways to read the laptop, both true and both useful:**

* **Controlled (1.06–1.19×)** is the *virtualisation* answer, and it agrees with the
  5900XT. This is the number that replicates §4.
* **Uncontrolled (1.18–2.93×)** is what a native-Windows process launched this way
  *actually gets by default on this box*. For the lever's purposes this is the operative
  figure, and it makes the lever worse, not better: a hypothetical native-Windows
  deployment would also have to fight the scheduler.

Either way **the conclusion is unchanged and now doubly supported: nothing to reclaim by
leaving WSL2.** Third forward-tax route (after the Pixel NPU and the Apple ANE) closes
negative on two boxes.

---

## 6. Caveats

1. **Pure-Python leaf on both arms**, as on the 5900XT (`leaf_active: false`, asserted).
   The bundle ships Linux `.so`s and there is no Windows `.pyd`. **Round-2 Cython parity
   is still blocked on MSVC Build Tools (admin — open question for Joshua)** and is
   unchanged by this run.
2. **The WSL CPython build differs across boxes** (pbs/Clang here, miniforge there). Within
   this run both arms are exact-patch-matched 3.13.14, which is *tighter* than §4 — but it
   means the laptop-vs-5900XT *absolute* comparison below is build-confounded.
3. **Not a deliverable, flagged for someone else's five minutes:** the laptop's WSL arm
   beats the 5900XT's WSL arm on every cell (champion 2.2502 vs 2.7045 s/move; `cuda_b1`
   1.028 vs 2.104 ms; `cpu_1t` 10.71 vs 11.25 ms) on the same bundle and the same
   md5-verified positions. Suggestive that the laptop is the faster *single-stream* box,
   but confounded by caveat 2 and by GPU model — **do not quote it as a box ranking**
   without a build-matched rerun.
4. **The E-core probe is n=3 on one cell type per configuration**, sufficient for a 1.8×
   effect against ≤2% spreads, not a characterisation of Windows scheduling.
5. Latency only. Nothing here measures strength.

---

## 7. Provenance, artifacts, reproducibility

* **Box was quiet:** loadavg 0.27 at launch, 0 python processes, GPU 6.6 W / 0% / no
  compute apps; re-censused between phases. Every cell records its own `loadavg` +
  `nvidia_smi` before and after.
* **Windows-side probe** (the native driver's own view): `NVIDIA GeForce RTX 4070 Laptop
  GPU, 610.62, 6.28 W, 0%, 365 MiB / 8188 MiB`, rc=0.
* Wall clock: provisioning ~22:24→22:34, smoke 22:34 (8/8 green, `audit: OK`), the A/B
  22:35:54→22:52:43, un-niced control 22:54:57, E-core probes to ~23:05. ~40 min total.
* **Artifacts** (103 files, 1.0 MB, all committed): `run_laptop_20260729/` — merged JSON +
  `cells/` (48) + `runs.ndjson` + driver log; `control_unniced/`; `ecore_probe/` (JSONs,
  logs **and the generated `.bat`s**, so the affinity probes are re-runnable verbatim).
* **⚠️ Unlike the 5900XT arm, the laptop's Windows venv was NOT deleted.** C: has
  **118.77 GiB free** (`Get-PSDrive`, authoritative), so there was no reason to trade
  reproducibility for space — §4's win arm became non-reproducible when its venv was
  removed, and this one deliberately does not repeat that. Kept on the laptop:
  `C:\Users\Doctor\carc-win-bench\.venv` (4.4 G), `/home/doctor/carc-wsl-bench/.venv`
  (6.6 G), `C:\carc-bench-eff_linus\` (206 M, bundle + ckpt + staging + `.bat`s), plus the
  exact-rev worktree `/home/doctor/eff_linus_wt` @ `17ba2ce` and the wrapper
  `/home/doctor/eff_linus_run.sh`.
* Results also on the share at `/mnt/carc-shared/eff_linus_laptop_20260729/`.

## 8. What this changes

* **eff_linus: CLOSED NEGATIVE on two boxes.** Same verdict as §4, now with a second
  architecture (Intel hybrid + mobile Ada) and an exact CPython-patch match across arms.
* **A reusable trap is now on record:** *benchmark anything on native Windows from WSL and
  you may be measuring E-cores.* Any future Windows-side cell in this project must pin
  affinity (or verify placement) before its ratio is quoted. This one would have shipped a
  2.16× "divergence" otherwise.
* **Unchanged:** the round-2 Cython question, and every strength claim.
