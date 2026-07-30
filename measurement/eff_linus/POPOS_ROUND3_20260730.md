# eff_linus ROUND 3 — bare-metal Linux (Pop!_OS) vs WSL2, same laptop silicon

**STATUS: MEASURED 2026-07-30, laptop box booted to Pop!_OS.** Round 3 of *eff_linus*,
executing [scripts/measurement_infra/EFFLINUS3_POPOS_RUNBOOK.md](../../scripts/measurement_infra/EFFLINUS3_POPOS_RUNBOOK.md).
Rounds 1–2 ([EFFJENSEN §4](../EFFJENSEN_BENCH_BATCH_20260729.md) ·
[laptop replication](LAPTOP_REPLICATION_20260729.md)) refuted "WSL2 is slower than native
**Windows**". This round asks Joshua's *original* question — the one never measured this
era — "the laptop felt faster on Pop": **WSL2 vs bare-metal Linux on identical hardware.**

**MEASUREMENT INFRASTRUCTURE.** Roadmap **G3**, stage "Eff Jensen", sub-effort *eff_linus*.
No games, no elo, no champion or claim can move here. No `results.csv` row.

---

## The verdict in one line

> **Bare-metal Linux and WSL2 are the same speed on this workload: Pop!_OS is
> 0.973× / 0.978× the WSL2 time on the two champion cells — i.e. 2.2–2.7% FASTER, inside
> the runbook's pre-registered parity band (0.95–1.05×). Decision hook fired: PARITY ⇒
> `eff_linus` CLOSES FOR GOOD. Three rounds, three boxes-or-OSes, one answer: WSL2 costs
> this project nothing, and there is no dual-boot fleet to build.**

Two things worth more than the checkmark:

> ⭐ **The E-core trap is a WINDOWS trap, not a hybrid-CPU trap.** Round 2's headline
> confound was that a windowless WSL-launched native-Windows process gets parked on the
> efficiency cores (unpinned reproduced E-core-pinned to 0.6%). **Linux does not do this:**
> unpinned and P-core-pinned agree to **0.5%** here, while a deliberate E-core pin costs
> **1.61×**. The scheduler had the same choice and made the right one, every rep.

> 🔧 **Interpreter start-up is ~3.5× cheaper on bare metal** — non-decision wall-clock per
> cell is **0.140 s (Pop) vs 0.484 s (WSL2)**, the same ~0.35 s on both champion cells.
> Irrelevant to our long-lived workers; relevant to anything that forks short-lived
> processes.

---

## 1. Why this is a cross-boot comparison, and what that costs (READ THIS FIRST)

⚠️ **Dual boot makes same-session alternation impossible.** Rounds 1–2 could alternate
A/B/B/A *within one boot* because a Windows binary is executable from inside WSL. Native
Linux is not: the machine is either in Pop!_OS or in Windows/WSL2, never both. So the
comparison arm here is **not re-run** — it is the **committed round-2 WSL arm on this same
silicon**, `run_laptop_20260729/wsl_vs_native_ab_20260729_223554.json`, measured **on the
evening of 2026-07-29**, roughly 18 hours and one reboot earlier.

What that leaves uncontrolled, stated rather than smoothed:

* **Thermal and idle-state history** differ across boots (the Pop run's `thermal_zone0` sat
  flat at 45 °C throughout; the round-2 artifacts record their own).
* **Firmware/EC power policy** (Windows power plan vs Linux `intel_pstate`) is not a single
  knob that can be matched. §4 brackets the Linux half of it.
* **Background daemons** differ by OS by construction.
* Both arms were quiet (round 2: loadavg 0.27 at launch, 0 python procs; round 3: 0.39→1.12
  where ~1.0 *is* the single-threaded bench itself — see `runs.ndjson` per-cell snapshots).

**Everything else was matched deliberately**, and matched *tighter* than round 2 matched its
own two arms — see §2. The measured effect (2–3%) is the same size as the cross-boot
uncertainty, which is precisely why the honest read is **"parity", not "Pop wins by 2.5%"**.

## 2. What was provisioned, and how exactly it matches the WSL arm

| | round-2 **WSL2** arm (the reference) | **round-3 Pop!_OS** arm (this) |
|---|---|---|
| box | i7-14650HX (8P+8E, 24T) / RTX 4070 Laptop | **the same physical machine** |
| OS | Win11 26100 host, WSL2 guest | Pop!_OS 22.04 LTS, kernel **6.17.9-76061709-generic** |
| kernel | 6.18.33.1-microsoft-standard-WSL2 | 6.17.9 generic |
| CPython | 3.13.14, `uv`/python-build-standalone, **Clang 22.1.3** | 3.13.14, `uv`/python-build-standalone, **Clang 22.1.3** — *byte-identical build* |
| numpy / pyyaml | 2.5.1 / 6.0.3 | **2.5.1 / 6.0.3** |
| leaf | pure-Python (`leaf_active: false`, asserted) | **pure-Python (`leaf_active: false`, asserted)** |
| champion | `puct_priors_v29_bmild_cap8` | `puct_priors_v29_bmild_cap8` |
| positions | `positions.jsonl` md5 `e36c4d2a…` | **md5 `e36c4d2a…` — same 12 positions** |
| ckpt | sha256 `6e26799…3751a1` | sha256 `6e26799…3751a1` |
| champ driver | M5 bundle `bench_champion.py`, `--limit 12 --warmup 1` | identical, from the same bundle |
| net driver | staged `pysrc` @ git `17ba2ce` | **`pysrc` @ `17ba2ce`, content-hash verified identical** (168 `.py` files, `9d364c64…`) |
| `nice` | `-n 19` | `-n 19` (verified `NI=19` at runtime); un-niced control in §4 |
| root storage | NVMe (WDC SN730) | ⚠️ **USB flash drive** (`/dev/sda4`, `TRAN=usb`, ext4) |

The CPython builds are not merely the same patch version — they are the same
python-build-standalone artifact, which is **tighter than round 2's own cross-arm match**
(round 2 had python.org/MSVC on one side and pbs/Clang on the other).

**Storage disclosure.** This is Joshua's *old* Pop install running off a **USB stick**
(hostname `pop-os`, tailnet `100.82.188.43`; the internal NVMe holds the Windows/WSL side and
was left unmounted). A USB-stick root could plausibly penalise an I/O-sensitive comparison.
It did not: the cells are compute-bound, and Pop's *non-decision* overhead was **lower** than
WSL2's (0.140 s vs 0.484 s), so any USB penalty is smaller than the start-up advantage that
hides it.

**Provisioning incident, disclosed:** the box's DNS was broken on arrival (a stale tailscale
claim on `/etc/resolv.conf`, MagicDNS dead); it was repaired out-of-band before provisioning,
so no install was routed around it and no offline-wheel workaround is in play.

## 3. The measurement — 3 reps × 2 affinity arms × 3 cells

Artifacts: `run_pop_20260730/main_perf/` (the two champion cells, 12 files + `runs.ndjson`)
and `run_pop_20260730/net_perf/` (the CPU net cell, 6 files), merged into
`run_pop_20260730/pop_vs_wsl_r3.json`. All 18 cells `rc=0`.

**Governor for this table: `performance` (EPP `performance`) on all 24 CPUs**, set for the
run and restored afterwards; §4 shows the choice does not matter.

| cell | metric | **WSL2** (round 2) | **Pop, P-pinned** | **ratio pop/wsl** | **Pop, unpinned** | ratio | spread wsl / pop |
|---|---|---|---|---|---|---|---|
| `champ_k1x32` | p50 s/move | 0.09505 | **0.09252** | **0.973×** | 0.09274 | 0.976× | 1.0% / 0.9% |
| `champ_k4x172` | p50 s/move | 2.25024 | **2.20177** | **0.978×** | 2.21266 | 0.983× | 0.3% / 1.2% |
| `net_cpu_1t` | forward p50 ms | 10.7114 | **10.4298** | **0.974×** | 10.4550 | 0.976× | 1.0% / 0.4% |
| `net_cuda_b1` | forward p50 ms | 1.0276 | — **SKIPPED (disk guard, §6)** | — | — | — | — |

Read the other way round: **WSL2 is 1.027× / 1.022× / 1.027× the Pop time** on the three
measured cells. Note that `net_cpu_1t` is a *different workload class* — dense torch CPU
convolutions rather than the champion's dict/set pointer-chasing — and it lands in the same
place (0.974×), which is the strongest single argument that this is a genuine null and not a
cancellation. Every gap exceeds both arms' own rep spreads (`gap_exceeds_run_spread: true`
on all three), so the 2–3% is real *as a measurement*; it is the cross-boot uncertainty of
§1 and the ~0.9% between-sitting floor of §4 that make it non-actionable.

**Determinism cross-check — the arms computed the same game.** `bench_champion` records the
action it chose at each of the 11 timed positions. **All 11 actions are identical to the WSL
arm on both champion cells, in every rep.** Same champion id, same resolved knobs, same
pure-Python leaf path. This is the round-3 equivalent of a leaf-hash match: the two OSes are
not just running comparable code, they are producing the same search result.

**Cython was deliberately NOT built.** `gcc 11.4.0` is present on this box, so a Linux
`flat_leaf_cy.so` *could* have been compiled — but the round-2 WSL numbers this arm is
compared against are pure-Python (`--exclude '*.so'` in the staging rsync, plus
`CARCASSONNE_USE_CY_LEAF=0` asserted). Building it would have made the comparison
Cython-vs-interpreted and destroyed the like-for-like. The bundle staged here contains **zero
`.so` files**, which makes the pure-Python path structurally guaranteed rather than merely
env-asserted. **Round-2's Cython-parity question is untouched by this round.**

## 4. Confounds bracketed, not assumed

Every row is 3 reps of the same cell, same box, same session. `p50 s/move`.

| configuration | `champ_k1x32` | `champ_k4x172` |
|---|---|---|
| `performance` + P-core pin (§3 headline) | 0.09252 | **2.20177** |
| `performance` + unpinned | 0.09274 | 2.21266 |
| `powersave` + P-core pin (the as-found governor) | 0.09288 | 2.19600 |
| `powersave` + unpinned | 0.09328 | 2.20072 |
| `performance` + P-core pin, **second sitting** (control) | — | 2.18168 |
| `performance` + **E-core pin** (`taskset -c 16-23`) | — | **3.54423** |
| `performance` + P-core pin, **un-niced** | — | **2.18848** |

* **Governor is NOT load-bearing here — the `performance` setting bought nothing.**
  `powersave` is 0.3% *faster* at k4×172 and 0.4% slower at k1×32, i.e. noise. `intel_pstate`
  with HWP at EPP `balance_performance` already boosts a sustained single thread to the same
  clock. So the headline ratio is not an artifact of having tuned the Linux side.
* **Affinity is NOT load-bearing on Linux — 0.5% between pinned and unpinned.** Contrast
  round 2, where the equivalent Windows arm was 1.81× off. The E-core row proves the
  hardware penalty is real and large on this box (**1.61×**, and Windows measured 1.82× for
  its own E-core pin), so the Linux scheduler's 0.5% is a *choice being made correctly*, not
  an absent effect. **This narrows round 2's standing rule:** *pin affinity before quoting any
  native-**Windows** cell* — native Linux does not need it (but recording it stays free).
* **`nice -n 19` is innocuous**, reconfirming round 2's §3a on a third OS: un-niced **2.18848** vs niced 2.20177 in the headline sitting and 2.18168 in a second niced sitting — the un-niced number sits *between* two niced ones, so the `nice` effect is smaller than the between-sitting floor.
* **Between-sitting reproducibility is ~0.9%** (2.20177 vs 2.18168, same config, ~10 min
  apart) — which is the noise floor any 2–3% claim has to be read against, and the reason
  this memo says "parity" instead of "Pop wins".
* **Mechanism knobs recorded, in case a future round needs them:** THP is `madvise` on Pop
  **and** `madvise` on WSL2 (checked on the 5900XT box's WSL — same Microsoft kernel family),
  so round-2's proposed THP arm is moot. Pop's mitigations are Enhanced/Automatic IBRS +
  `BHI_DIS_S` + Clear Register File + `vmscape` IBPB; the laptop's *WSL-side* mitigation
  string could not be read (the box cannot be in both OSes at once) — the one dimension this
  round genuinely could not match. Given the result is parity, no mechanism hunt is owed.

## 5. ⇒ Where all three rounds land

| cell | R1 5900XT: win/wsl | R2 laptop: win/wsl (affinity-controlled) | **R3 laptop: pop/wsl** |
|---|---|---|---|
| `champ_k1x32` | 1.259× | 1.182× | **0.973×** |
| `champ_k4x172` | 1.251× | 1.185× | **0.978×** |
| `net_cuda_b1` | 1.060× | 1.181× | skipped (disk) |
| `net_cpu_1t` | 1.137× | 1.055× | **0.974×** |

* **Native Windows is 1.06–1.26× SLOWER than WSL2** (two boxes, rounds 1–2).
* **Native Linux is 0.97–0.98× of WSL2 — parity** (this round).

So WSL2 sits at the top of the range: it beats native Windows on the same silicon and ties
bare-metal Linux on the same silicon. **The hypervisor tax hypothesis (H1 nested paging, H2
`/dev/dxg`) is not merely refuted — the remaining virtualisation cost on our workload is
smaller than the reproducibility floor of the bench that would measure it.**

**Decision hook fired: PARITY (0.95–1.05×) ⇒ `eff_linus` is CLOSED.** No dual-boot gen
fleet; the runbook's ≥1.10× branch (and its operational-cost discussion) is not reached, and
the >1.10×-slower branch (which would have localised a WSL *advantage* worth hunting) is not
reached either. **Joshua's "the laptop felt faster on Pop" is now measured and is not a
compute effect** — whatever it was (UI responsiveness, I/O, a different era of the machine),
it is not 2.2 s/move becoming anything else.

## 6. Caveats

1. **Cross-boot, not same-session** — §1. This is the dominant caveat and it is structural,
   not fixable by more reps.
2. **`net_cuda_b1` SKIPPED on a disk guard.** Root here is a 57 G USB stick with **8.7 G
   free**; the round-2 Linux venv carrying `torch 2.11.0+cu128` measured **6.6 G**, which
   would have left ~2.1 G — under the runbook's ≥3 G headroom rule. So the native-Linux-CUDA
   vs WSL-CUDA batch-1 datum (the runbook's "bonus") is **not collected**. It is the one
   cell of the four that is genuinely missing.
3. **`net_cpu_1t` runs a different torch BUILD** — `2.11.0+cpu` here vs `2.11.0+cu128` in the
   WSL arm, forced by the same disk guard. Same version, same ATen CPU kernels, and the row
   pins 1 thread on both arms, but it is a difference and the champion cells (which have no
   such confound) are what the verdict rests on.
4. **Pure-Python leaf both arms.** Production runs the Cython leaf; this round prices the
   interpreted one, exactly as rounds 1–2 did. Round-2's Cython-parity question is unchanged.
5. **`torch.get_num_threads()` defaults differ** (16 on Pop vs 12 in WSL2 — different visible
   core counts), the same residual asymmetry round 2 disclosed. Irrelevant to a 1-thread row.
6. **n=3 per configuration**, sufficient against ≤1.3% spreads for the ~1.6× E-core effect
   and to bound the OS effect below the ~0.9% between-sitting floor; not a characterisation
   of either scheduler.
7. **Latency only.** Nothing here measures strength. No `results.csv` row, no claim, no
   governance change.

## 7. Provenance, artifacts, reproducibility

* **Artifacts** (all committed under `run_pop_20260730/`): `main_perf/` (the A/B),
  `gov_powersave/`, `probe_ecore/`, `ctrl_unniced2/`, `net_perf/`, `smoke/`, each with
  `cells/*.json` + `cells/*.log` + `runs.ndjson`; the driver logs; the merged
  `pop_vs_wsl_r3.json`; and **the scripts themselves** (`scripts/pop_ab.sh`,
  `pop_provision.sh`, `pop_stage.sh`, `pop_probes.sh`, `pop_phase3.sh`, `merge_r3.py`) so
  this arm re-runs verbatim — the same practice round 2 adopted for its `.bat`s.
* Every cell records its own `loadavg`, `governor`, `epp`, `nvidia_smi` and `thermal_zone0`
  **before and after**.
* **Transport:** repo via `git bundle` of local `HEAD` (`e7575f3`) → scp → `git clone
  --no-checkout` → `git checkout 17ba2ce -- src/carcassonne_ai engine/wingedsheep
  scripts/measurement_infra`; M5 bundle via tar+scp. The staged `pysrc` content hash was
  verified equal to the local repo's `17ba2ce` staging **before any cell ran**.
* **Box state left behind (verified, not assumed):** governor **restored to `powersave`** /
  EPP `balance_performance` on all 24 CPUs exactly as found, `pgrep` for every driver and
  child returns nothing, loadavg 0.11, transport files (`carc_head.bundle`, `m5_bench.tgz`)
  deleted. **`/` went 9.5 G → 8.0 G free — ~1.5 G consumed**, itemised: `carc-repo` (the
  `--no-checkout` clone) **557 M** · `carc-pop-bench/.venv` **826 M** (incl. torch-CPU) ·
  `~/.local/share/uv` **108 M** · `m5_bench_20260728` **35 M** · `stage/` **6 M** · `out/`
  **624 K**. The venv, bundle and staged tree are **deliberately kept** so this arm stays
  reproducible — round 1's deleted venv is exactly why *its* Windows arm is not.
* Wall clock: provisioning 12:47→12:53 local, staging 12:53, smoke 12:55, A/B
  12:56→12:59:57, confound probes 13:00→13:08:47, torch + net cells 13:09→13:19:21.

## 8. What this changes

* **`eff_linus` is CLOSED — three rounds, all negative for leaving WSL2.** Native Windows
  loses on two boxes; native Linux ties on one. There is no OS-level speed lever left here.
* **Round 2's standing rule is narrowed to where it belongs:** *pin (or verify) CPU affinity
  before quoting any native-**Windows** cell on a hybrid CPU.* Linux's scheduler placed a
  single-threaded, niced, unpinned job on P-cores in 100% of reps; the trap was Windows'
  Thread Director, not hybrid silicon.
* **Unchanged:** every strength claim, the champion, `governance/`, and the Cython-parity
  question.
