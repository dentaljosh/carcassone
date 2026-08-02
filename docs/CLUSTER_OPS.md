# CLUSTER_OPS — cluster hardware, reach/ssh, worker counts, long-run launch runbook

> Extracted from CLAUDE.md on 2026-06-19 to keep the always-loaded CLAUDE.md small. This is
> the operational runbook for the 3-box cluster (5900XT-box local · Xeon · laptop) — read it
> before any cluster launch. **Live W-counts / mode verdicts evolve; the authoritative current
> figures are in memory** (`feedback_worker_count_by_bottleneck`, `reference_carc_orch_verdict`,
> `reference_laptop_cluster_access`, `reference_xeon_direct_ssh`, `reference_offline_git_bundle_sync`)
> — this doc is the stable hardware/topology + launch-pattern reference.

## Cluster share paths — ⚠️ THE MOUNT POINT DIFFERS BY BOX

The CIFS share has **different mount paths per box.** Using the wrong one was the #1 cause of "No such file" errors in ad-hoc commands (27 in the 2026-06-02 transcript audit).

| Box | Share mount | Use it in… |
|---|---|---|
| 5800x (local) | `/mnt/c/carc-shared` | commands run locally on the 5800x |
| xeon | `/mnt/carc-shared` | inside `ssh xeon "…"` |
| laptop | `/mnt/carc-shared` | inside `ssh laptop "…"` |

**Rule:** local commands use `/mnt/c/carc-shared`; anything inside an `ssh xeon/laptop` uses `/mnt/carc-shared`. In scripts, resolve a per-box `$SHARE` (the launchers do this via a sed `SHARE_LOCAL`→`SHARE_REMOTE` substitution). The project PreToolUse lint hook (`scripts/hooks/pretooluse_lint.py`) blocks the two unambiguous misuses (local cmd using `/mnt/carc-shared`, or `ssh`-to-remote using `/mnt/c/carc-shared`); add `# allow-path` to override.

## Worker counts — ⚠️ GEN W ≠ EVAL W (the distinction that bites)

**The durable rule (never goes stale):** a **GEN (self-play) worker is RAM-heavier than an EVAL worker** — it carries a live `sims` MCTS search tree **plus** the game's accumulated position buffer (~0.9 GB/worker at sims=200). An eval worker just plays/scores. **So the per-box gen W is LOWER than the eval W. Do NOT use the eval worker count for generation — it OOMs.** (This is *why* there are two numbers per box; mixing them up cost a relaunch on 2026-06-23.)

Current per-box maxes, **orchestrator-ON** (carc-orch SHM, the deployed mode — [[reference_carc_orch_verdict]]); values as of **2026-06-23**, re-bench after any code-era change:

| Box | **GEN W** (self-play) | **EVAL W** (net-vs-heur / net-vs-net) | live RAM headroom at gen W |
|---|---|---|---|
| 5800x / 5900XT (42 GB RAM, 16 GB GPU) | **28** | **48** single-ctx · ~32 two-ctx net-vs-net | W28 → ~17 GB free (W48 gen hit ~38 GB RSS → **OOM**) |
| laptop (11 GB WSL, 8 GB GPU) | **8** | **26** single-ctx · 16 two-ctx | W8 → ~4 GB free (W26 gen → **131 MB free, sshd wedge**) |
| xeon (retired 2026-06-17) | 18 | 12 | — |

**Third profile — fair-netprior eval (`fair_net_vs_net_orch.sh` / `eval_fair_puct --info fair-netprior`: CPU PUCT + net-prior SHM round-trips + K=2 solver): local W=32 / laptop W=20** (2026-07-19 micro-sweep + high-W n=96 extension: local knee at W32 = full SMT width — W40 adds steady-state on paper but +20% per-game contention and ~flat wall; laptop still mildly rising at W20, adopted per shrinking steps. **~2.2×/~1.6× over the old 12/10 defaults.** Details in memory `feedback_worker_count_by_bottleneck`). ⚠️ **k2×200-measured ONLY — the 2026-07-19 #3 pre-flight PROVED it does not transfer to net-heavy configs:** at k4×376 net-sims, W32 hit orch **queue COLLAPSE** (net 25,659 ms/move; orch throughput FELL 209→97 batches/s — thrashing, not saturation), and even W20@k4×250 was queue-bound (ratio 1.71×). For heavy-net evals drop W until workers hold >50% CPU (W16 worked at k4×395), and remember: **harvest load never affects the games (strength = sims), only wall-clock and any wall-clock-derived calibration** — never pin a cost ratio from a loaded run; measure unloaded (W2 probe pattern, CHECKLOG 2026-07-19 18:15).

**Fourth profile — Rust-era classical ablation/eval cells (`eval_puct_priors --backend rust`: rust clairvoyant candidate + python PUCT opponent + python exact-K tail): local W\*=30 / laptop W\*=22** (F7d sweep 2026-08-02, full ladders with endpoint-bracketing — peaks W32/W26, i.e. ~full thread count; the python-era "W≈14–16 DRAM wall" does NOT apply to this class). Data `measurement/classical_search/WSWEEP_F7D_{local,laptop}.tsv`; DECISIONS 2026-08-02 (afternoon). ⚠️ Farm rule travels with it: each worker runs the rust agent at threads=1 (enforced with a hard-error; W×t oversubscription is the failure mode).

**Fifth profile — Rust-era classical GEN (`gen_fair_distill --backend rust`, net-free champion self-play at k8×1376): local W\*=48 / laptop W\*=24** (gen W-sweep 2026-08-02; local ladder to W=64 — the curve only flattens at 2× threads; ~328/~260 games/h at the settle points). **RAM is no longer the binding axis for this profile** (≤10G/4G total box-wide) — the python-era gen caps (28/8, ~0.9G/worker) apply only to the python/orch profiles above. Farm threads=1 enforced. Data `measurement/classical_search/WSWEEP_GEN_RUST_{local,laptop}.tsv`; DECISIONS 2026-08-02 (late afternoon).

**Canonical source (point, don't copy):** the gen defaults are `gen_flywheel.sh` `_OWD` (≈line 49: `5800x=28; xeon=18; laptop=8`); the eval defaults are `run_residual_flywheel_v2.sh` `EVAL_W_*` (≈line 57: `5800x=48; laptop=26; xeon=12`). Those script defaults are the runtime source of truth; this table just makes the **gen-vs-eval split** discoverable. Both are throughput-optima too (gen is GPU-dispatch-bound past these W; pushing higher only adds RAM/contention). **orch-OFF self-play is a different profile** (CPU-thread-bound, see [[feedback_worker_count_by_bottleneck]]). Confirm with `free -g` + `ps`, not just loadavg — a WSL OOM restarts the whole VM.

## SSH-disconnect resilience (Mac→Windows→WSL setup)

Joshua connects via SSH from a Mac to Windows, then to WSL2. **When the Mac sleeps, SSH disconnects and SIGHUP propagates to any tty-attached process** — this killed two long runs on 2026-04-28 (warmstart gen at 125/500, T2 at 16/100). Per-game checkpoints saved the work but compute was lost.

**Rule: any script expected to run more than ~1 minute must launch detached.** Use this pattern:

```bash
nohup python -u scripts/<thing>.py [args] > /tmp/<name>.log 2>&1 &
disown
PID=$!
# To get a completion notification, follow up with run_in_background=true:
tail --pid=$PID -f /dev/null
```

`nohup` makes the process ignore SIGHUP. `disown` removes it from the bash job table so a bash exit (also caused by SSH death) doesn't kill it. `setsid` is an equivalent alternative. The harness's `run_in_background=true` parameter alone is NOT sufficient — that tracks the bash invocation, which still gets SIGHUP'd when SSH dies; the python child must be explicitly detached.

## Second machine — Xeon training box (192.168.0.110)

> ⚠️ **RETIRED — do not use the Xeon for cluster work (reaffirmed 2026-07-17).** It's just too slow to be worth the wiring/contention risk: Quadro RTX 4000 (Turing, 8 GB) + a 6C/12T Skylake-X give roughly ½–⅔ of the 5900XT's throughput, and in the current GPU-dispatch-latency-bound gen/eval regime it adds far more orchestration fragility than useful compute. **Standing decision: local (5900XT) + laptop only; the Xeon is not part of the default cluster.** Only revisit if a job is embarrassingly CPU-parallel *and* both other boxes are saturated. Everything below is kept for historical reference / the one-off exception.

A second always-on machine is available for training runs (set up 2026-05-18).

- **Reach it:** `ssh xeon` — configured in `~/.ssh/config` on the carcassonne box, key-only auth (no password). That lands in a Windows shell as user `VATECH`; `wsl -d Ubuntu-24.04` enters Linux. (Direct WSL2 ssh now available — `ssh xeon-wsl` lands in bash, see memory `reference_xeon_direct_ssh`.)
- **Hardware:** Intel Xeon W-2135, 6 cores / 12 threads @ 3.7GHz, 32 GB RAM, Windows 11 Pro for Workstations. Static LAN IP 192.168.0.110, runs 24/7, sleep disabled, High-performance power plan.
- **GPU:** NVIDIA Quadro RTX 4000 (8 GB GDDR6, Turing). WSL2 CUDA passthrough confirmed working (`/dev/dxg` present, the WSL-injected `nvidia-smi` sees the card) — it can run its own GPU eval-server; install a CUDA-enabled torch in the venv.
- **WSL:** WSL2 2.7.3, Ubuntu 24.04 LTS, user `doctor`, systemd on. `.wslconfig` caps it at 26 GB RAM / 8 GB swap / 12 procs.
- **Capacity reality:** smaller than the 5800X (12 threads vs 16, older Skylake-X cores) — expect roughly ½–⅔ of the 5800X's self-play throughput. Use it as a **parallel 2nd worker**, not a faster box. Bench before trusting any estimate.
- **Worker count depends on the BOTTLENECK, not just the 12 threads (clarified 2026-05-31):** in **orchestrator mode** the workers BLOCK on GPU-server IPC (priors/value over a socket/queue) — they're latency-bound, not CPU-bound — so oversubscribing the 12 threads is fine and even helps keep the GPU fed. Proven Xeon self-play W=**18** (1b rebench: throughput FLAT for W≥10); a 2026-05-31 ceiling-probe eval at W=16 sat at loadavg ~6/12 (half-idle, NOT oversubscribed — don't reflexively drop it to 10). **CPU-bound work is the opposite:** a per-worker leaf with NO orchestrator (the ladder gauntlet `eval_net_vs_heuristic.py`, or pure-CPU MCTS) runs the full `virtual_score` on the worker → W should be **≤ threads (≤10–12, leave headroom)**, else it thrashes. Rule of thumb: **orchestrator → W≈18; no-orchestrator / CPU-leaf → W≤10**. **REFINED 2026-06-01 (bench → DECISIONS):** production *self-play* now runs **orch-OFF** for the CPU v2.7 leaf — the orchestrator's single GIL-bound dispatch thread was the limiter, so bypassing it wins where net×W fits VRAM. **RE-BENCHED 2026-06-03 (supersedes the 06-01 W figures — the old "+87% mixed-mode" numbers were river-era):** orch-off wins ALL 3 boxes by ~2×; production per-box self-play W = **laptop 20 / 5800x 14 / xeon 10** (per-box, NOT uniform; fine sweep `sweep_w.sh`; at blend>0 self-play is GPU-bound at moderate W). The CPU-leaf gate eval (`eval_net_vs_heuristic`, no orch) is a different profile: W≤threads. Re-bench after any code-era change (the flat-leaf deploy 2026-06-09 is one). Wired into `selfplay_mode()`/`gate_workers()` in `run_pathb_cluster_loop.sh`. **(Note: orch-vs-off has since flipped again with CUDA streams — see memory `reference_carc_orch_verdict` for the current per-box mode/W.)**
- **Deployed (2026-05-18+):** repo + CUDA-torch venv live at `/home/doctor/projects/carcassone`; runs self-play/eval routinely via the held-ssh pattern below.
- The SSH-disconnect / `nohup`-detach rule above applies here too.
- **⚠️ WSL2 VM teardown kills detached jobs (learned 2026-05-29):** `nohup`/`disown` is NOT enough on the Xeon. When the `wsl.exe` that launched a job exits, WSL2 tears down the distro VM and kills even nohup'd background processes (different failure mode than SIGHUP). **For long Xeon jobs, run the worker in the FOREGROUND over a held ssh** (`nohup ssh -o ServerAliveInterval=60 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_X.sh'" &` on the 5800x side — the held connection keeps the VM alive; the remote launcher runs python in the foreground). This is the proven `maximalist_sequencer.sh`/`run_pathb_cluster_loop.sh` pattern.
- **⚠️ Launcher chicken-egg:** a launcher script that self-mounts the CIFS share can't live ONLY on the share (unreadable when unmounted). Use `/home/doctor/stage_launcher.sh <name>` (LOCAL on Xeon) which mounts the share + copies `code_sync/launch_xeon_<name>.sh` to a local path first, THEN the held ssh runs the local copy.
- **⚠️ cmd.exe mangles shell operators:** `ssh xeon "wsl … -- bash -lc 'a && b | c'"` — the `&& | ; > ||` get interpreted by the Windows shell, not bash (see also memory `feedback_xeon_ssh_quoting`). Keep operators inside a real `.sh` file run by a single operator-free invocation; for `pkill` use `wsl … -- pkill -TERM -f X` (no `bash -lc`, no inner redirects). (Largely superseded by `ssh xeon-wsl` direct access — `reference_xeon_direct_ssh`.)
- **GPU read:** the WSL-native `nvidia-smi` may throw `NVML: Function Not Found` (version mismatch); the Windows interop `nvidia-smi.exe` works from WSL and isn't fooled. (Windows Task Manager's default GPU graph shows the **3D** engine — CUDA compute is under a separate **Compute/Cuda** engine you must select, else WSL torch looks idle.)

## Third machine — laptop (REBUILT 2026-06-15 → Windows 11 + WSL2 Ubuntu)

> ⚠️ **REBUILT 2026-06-15: the laptop is NO LONGER pop-os.** It's now **Windows 11 + WSL2 Ubuntu 26.04** at LAN **192.168.0.221** (on the LAN, not Tailscale — like the xeon). Reach it via `ssh laptop` (Windows cmd.exe, user `Doctor`) or `ssh laptop-wsl` (direct WSL2 bash :2222, user `doctor`); passwordless key + sudo. Mirrored WSL networking (Hyper-V firewall rule, no portproxy). WSL idle-shuts-down but a scheduled-task keepalive (`WSL-KeepAlive`, onlogon) keeps it up. Mirrored WSL has full internet → pip-from-PyPI (no offline wheels). **Worker stack SET UP 2026-06-15:** Python 3.14, **torch 2.11.0+cu128 (cp314)** on the RTX 4070m (CUDA passthrough via `/dev/dxg`), repo at `/home/doctor/projects/carcassone` + `.venv`, CIFS share at `/mnt/carc-shared` (fstab), parity-verified vs local (fp32/TF32 arch-noise). **Current details: memory `reference_laptop_cluster_access`.** Everything below is the OLD pop-os setup (historical).

A third cluster box — a pop-os laptop — joined for self-play/eval (first used over Shabbos 2026-05-29).

- **Reach it:** `ssh laptop` — Tailscale, key-only, **native Ubuntu/pop-os** (user `pop`; NO WSL/cmd.exe layer, so it's simpler than the Xeon — plain bash, operators work). Repo at `/home/pop/carcassone`. GPU: RTX 4070m (8 GB).
- **⚡ Passwordless sudo:** the laptop has `(ALL) NOPASSWD: ALL` — `ssh laptop "sudo …"` works with **no password** (don't hunt for a login password; sudo never prompts for one). Standing permission to use it for cluster ops (Joshua, 2026-05-31). The 2026-05-31 "permission denied" mount confusion was a phantom sudo-password prompt — sudo didn't need one; the real issue was the share being unmounted.
- **CIFS share:** `//192.168.0.195/carc-shared` → `/mnt/carc-shared`, creds already at `/home/pop/.carc-smb.creds`. Manual mount: `sudo mount -t cifs //192.168.0.195/carc-shared /mnt/carc-shared -o credentials=/home/pop/.carc-smb.creds,uid=1000,gid=1000,forceuid,forcegid,file_mode=0644,dir_mode=0755,vers=3.1.1,nobrl,actimeo=1,noserverino`. **Now in `/etc/fstab` (`_netdev,nofail`, added 2026-05-31) → auto-mounts at boot.** Before that, a restart dropped the share (left an empty root-owned `/mnt/carc-shared` mountpoint) and crashed a run with `PermissionError` on the first write. **If a laptop run dies with a share permission / NoSuchFile error, check `mountpoint -q /mnt/carc-shared` FIRST.**
- **Network:** Tailscale over wifi/usb-tether → intermittent `ssh rc=255` jitter (high latency, dup packets). Launch detached (native Linux → plain `nohup` survives, no WSL-teardown failure mode) or held-ssh with `ServerAliveInterval=60`; **retry a 255 once or twice before concluding the box is down.**
- **Throughput:** historically W=24 for orchestrator self-play (fastest single box on the 1b rebench, 4.34 g/min). Work-stealing (`--shared-claim`) lets it hot-join a running multi-box eval/self-play mid-flight — just launch its worker pointed at the same shared output folder.

## Vast.ai box bootstrap is fragile — babysit it actively

Renting a box and waiting for it to boot is **not reliable**. We've seen two failure modes that don't surface until you actively check:

1. **Docker pull stalls indefinitely.** Vast.ai's docker daemon gets stuck "Verifying Checksum / Download complete" on a layer and never recovers. Status stays "loading" forever. Sunk $1.13 on 2026-05-13 across two boxes before catching it.
2. **SSH-ready ≠ usable.** The status flips to "running" but the actual sshd / image config can still fail (e.g. the 2026-05-12 openssh-server missing-from-image bug).

**Rule: when waiting for a cloud box to bootstrap, use ACTIVE polling, not passive "wait for status=running".** A naive `until [status == running]; do sleep 25; done` will sit forever on a stalled pull.

Pattern (use a Monitor):

```bash
# In the Monitor command — polls every 5 min, emits the current status_msg,
# flags "stuck" if the same message persists 3 polls (~15 min).
prev=""
stuck=0
while true; do
  msg=$(vastai show instance <id> --raw | python3 -c "import json,sys; d=json.load(sys.stdin); print((d.get('status_msg','') or '').split(chr(10))[0])")
  if [ "$(vastai show instance <id> --raw | python3 -c "import json,sys; print(json.load(sys.stdin).get('actual_status','?'))")" = "running" ]; then
    echo "READY"; break
  fi
  [ "$msg" = "$prev" ] && stuck=$((stuck+1)) || stuck=0
  echo "poll: msg=$msg stuck=$stuck"
  [ "$stuck" -ge 3 ] && echo "STUCK: destroy + retry recommended"
  prev=$msg
  sleep 300
done
```

**Idle-hook firings during a cloud box wait are SIGNAL, not noise.** If the harness says "background task running 10+ minutes", that's the prompt to actively inspect the box's status_msg, not to silence the alert. Two consecutive failures with identical status_msg → destroy + retry on a different physical machine.

Budget: each stuck-box costs ~$0.40-0.70 before you notice. With active polling you catch it inside 15 min ≈ $0.10. Cheap savings; do it every time.

## Pause / resume long-running parallel jobs

For embarrassingly-parallel jobs (tournaments, measurement sweeps, self-play), use **per-game checkpoint files** so we can pause or apply optimizations without losing work.

`scripts/play_mcts_vs_random.py` is the reference implementation. Each completed game writes to `data/tournament/s<sims>_seed<seed>_p<player>.json`. Reruns with the same `(--n, --sims, --seed-start)` skip cached seeds and resume from where they stopped.

Workflow when you want to test an optimization mid-run:

```bash
# 1. Kill the running tournament (Ctrl-C or SIGTERM)
pkill -f play_mcts_vs_random
# 2. Apply your optimization, run any quick benches on idle CPU
python scripts/bench_quick.py
# 3. Resume — only remaining games are played
python -u scripts/play_mcts_vs_random.py --n 100 --sims 50
# Or restart from scratch if the optimization invalidates earlier results
python -u scripts/play_mcts_vs_random.py --reset --n 100 --sims 50
# Just read what's already on disk
python scripts/play_mcts_vs_random.py --summary-only --n 100 --sims 50
```

For **brief pauses** (free up CPU for a quick bench, then resume with the same code), `kill -STOP <pid>` / `kill -CONT <pid>` on the worker PIDs is sufficient and instant — no checkpoint needed since you're not changing code.

When writing new parallel scripts: always launch with `python -u` for unbuffered stdout (otherwise progress prints don't flush until script exit), and adopt the same per-item checkpoint pattern if the job runs more than a few minutes.
