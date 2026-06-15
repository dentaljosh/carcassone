# CLAUDE.md — standing context for Claude sessions

If you're starting a new conversation in this repo, read this file first, then [STATUS.md](STATUS.md) for live state.

## What we're building

AlphaZero-style Carcassonne AI. **Goal (changed 2026-05-28): attempt genuinely superhuman play — beat strong/expert humans, aspirationally the world champion, at 2-player Base+Farmers.** (River was DROPPED 2026-06-02 — competitive/WC play is base-only; see DECISIONS.md 2026-06-02.)

⚠️ **This OVERRIDES the original prompt.** [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) explicitly scoped superhuman *out* ("This is not a 'build superhuman Carcassonne AI' project... We're not going to either") and named the **analyzer (Phase 5)** as the win condition. Joshua changed the goal on 2026-05-28: superhuman strength is now primary; the analyzer (Phase 5) and heuristic research (Phase 6) are **downstream**, pursued after strength milestones, not the target. See [DECISIONS.md](DECISIONS.md) 2026-05-28 "Goal change". Pursue clear-eyed — this is the research-grade goal the prompt deliberately avoided (academic attempts since 2020 stalled). Two structural blockers gate it: (1) **measurement** — no strong non-saturated reference exists yet (Tier-1 is saturated; self-anchored elo can climb while absolute strength regresses), and (2) the **hand-crafted v2.7 leaf eval caps learned strength near strong-human by construction** — superhuman requires the *learned* components to exceed the heuristic, which they don't yet.

Full original spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md). Phase structure (0-7) and original guesses live there — but treat the win-condition framing as superseded.

**Locked scope:** 2-player, Base game + Farmers, no River (dropped 2026-06-02), no Inns & Cathedrals, no Abbots, no Big meeples. Don't expand the *rule* scope without explicit approval.

## Where the truth lives

| Source | What it answers |
|---|---|
| [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) | Original spec, win conditions, phase structure, "known unknowns" to verify |
| [DECISIONS.md](DECISIONS.md) | Every non-trivial decision with options-considered + reason. **Refines or overrides the original prompt.** Read before assuming any prompt number is still current. |
| [BACKLOG.md](BACKLOG.md) | Deferred ideas, optimizations, stretch goals. Don't action without Joshua's approval. |
| [STATUS.md](STATUS.md) | Current branch, last commit, what's running, immediate next action |
| [docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md) | **Why the learned value can't beat the v2.7 heuristic** — 6 root causes + 2 live bugs (the 2026-06-02 reframe; the evidence) |
| [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) | Master fix sequence (phases 0–3). **Supersedes the old leaf/afterstate/anchor-fraction plan.** |
| [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md) | Concrete staged build (A→B→C, cheapest-informative-first) executing the correction plan |
| [experiments/results.csv](experiments/results.csv) | **Source of truth for experiment numbers** (elo/wr). STATUS/EXPERIMENTS/DECISIONS cite it; don't carry authoritative numbers that drift from it. |
| [governance/](governance/README.md) | Claim registry, checkpoint lineage, evidence epochs, experiment protocols — the machine-readable governance spine (raw→interpretation→decisions) |
| [REVIEW_LOG.md](REVIEW_LOG.md) | Multi-agent code-review findings: fixes applied (F-numbers) and deliberately deferred items (D-numbers) with rationale |
| [clean_eval/CLEAN_EVAL_AUDIT.md](clean_eval/CLEAN_EVAL_AUDIT.md) | **The trustworthy-ruler audit (2026-06-07).** Runtime-verified evaluator provenance (`src/carcassonne_ai/eval_provenance.py`, R1/R7 guards) + 11 semantic contracts + 5 clean reruns re-judging every old vs-HeuristicMCTS claim. Use this ruler for any new strength eval; absolutes are NOT blanket-discountable (the leaf effect is non-transitive). |
| Git log | What each commit did and why |
| Auto-memory at `~/.claude/projects/-home-doctor-projects-carcassone/memory/` | Workflow feedback (parallelism rules, ETA discipline, hot-path profiling) |

## Cluster share paths — ⚠️ THE MOUNT POINT DIFFERS BY BOX

The CIFS share has **different mount paths per box.** Using the wrong one was the #1 cause of "No such file" errors in ad-hoc commands (27 in the 2026-06-02 transcript audit).

| Box | Share mount | Use it in… |
|---|---|---|
| 5800x (local) | `/mnt/c/carc-shared` | commands run locally on the 5800x |
| xeon | `/mnt/carc-shared` | inside `ssh xeon "…"` |
| laptop | `/mnt/carc-shared` | inside `ssh laptop "…"` |

**Rule:** local commands use `/mnt/c/carc-shared`; anything inside an `ssh xeon/laptop` uses `/mnt/carc-shared`. In scripts, resolve a per-box `$SHARE` (the launchers do this via a sed `SHARE_LOCAL`→`SHARE_REMOTE` substitution). The project PreToolUse lint hook (`scripts/hooks/pretooluse_lint.py`) blocks the two unambiguous misuses (local cmd using `/mnt/carc-shared`, or `ssh`-to-remote using `/mnt/c/carc-shared`); add `# allow-path` to override.

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

A second always-on machine is available for training runs (set up 2026-05-18).

- **Reach it:** `ssh xeon` — configured in `~/.ssh/config` on the carcassonne box, key-only auth (no password). That lands in a Windows shell as user `VATECH`; `wsl -d Ubuntu-24.04` enters Linux.
- **Hardware:** Intel Xeon W-2135, 6 cores / 12 threads @ 3.7GHz, 32 GB RAM, Windows 11 Pro for Workstations. Static LAN IP 192.168.0.110, runs 24/7, sleep disabled, High-performance power plan.
- **GPU:** NVIDIA Quadro RTX 4000 (8 GB GDDR6, Turing). WSL2 CUDA passthrough confirmed working (`/dev/dxg` present, the WSL-injected `nvidia-smi` sees the card) — it can run its own GPU eval-server; install a CUDA-enabled torch in the venv.
- **WSL:** WSL2 2.7.3, Ubuntu 24.04 LTS, user `doctor`, systemd on. `.wslconfig` caps it at 26 GB RAM / 8 GB swap / 12 procs.
- **Capacity reality:** smaller than the 5800X (12 threads vs 16, older Skylake-X cores) — expect roughly ½–⅔ of the 5800X's self-play throughput. Use it as a **parallel 2nd worker**, not a faster box. Bench before trusting any estimate.
- **Worker count depends on the BOTTLENECK, not just the 12 threads (clarified 2026-05-31):** in **orchestrator mode** the workers BLOCK on GPU-server IPC (priors/value over a socket/queue) — they're latency-bound, not CPU-bound — so oversubscribing the 12 threads is fine and even helps keep the GPU fed. Proven Xeon self-play W=**18** (1b rebench: throughput FLAT for W≥10); a 2026-05-31 ceiling-probe eval at W=16 sat at loadavg ~6/12 (half-idle, NOT oversubscribed — don't reflexively drop it to 10). **CPU-bound work is the opposite:** a per-worker leaf with NO orchestrator (the ladder gauntlet `eval_net_vs_heuristic.py`, or pure-CPU MCTS) runs the full `virtual_score` on the worker → W should be **≤ threads (≤10–12, leave headroom)**, else it thrashes. Rule of thumb: **orchestrator → W≈18; no-orchestrator / CPU-leaf → W≤10**. **REFINED 2026-06-01 (bench → DECISIONS):** production *self-play* now runs **orch-OFF** for the CPU v2.7 leaf — the orchestrator's single GIL-bound dispatch thread was the limiter, so bypassing it wins where net×W fits VRAM. **RE-BENCHED 2026-06-03 (supersedes the 06-01 W figures — the old "+87% mixed-mode" numbers were river-era):** orch-off wins ALL 3 boxes by ~2×; production per-box self-play W = **laptop 20 / 5800x 14 / xeon 10** (per-box, NOT uniform; fine sweep `sweep_w.sh`; at blend>0 self-play is GPU-bound at moderate W). The CPU-leaf gate eval (`eval_net_vs_heuristic`, no orch) is a different profile: W≤threads. Re-bench after any code-era change (the flat-leaf deploy 2026-06-09 is one). Wired into `selfplay_mode()`/`gate_workers()` in `run_pathb_cluster_loop.sh`.
- **Deployed (2026-05-18+):** repo + CUDA-torch venv live at `/home/doctor/projects/carcassone`; runs self-play/eval routinely via the held-ssh pattern below.
- The SSH-disconnect / `nohup`-detach rule above applies here too.
- **⚠️ WSL2 VM teardown kills detached jobs (learned 2026-05-29):** `nohup`/`disown` is NOT enough on the Xeon. When the `wsl.exe` that launched a job exits, WSL2 tears down the distro VM and kills even nohup'd background processes (different failure mode than SIGHUP). **For long Xeon jobs, run the worker in the FOREGROUND over a held ssh** (`nohup ssh -o ServerAliveInterval=60 xeon "wsl -d Ubuntu-24.04 -- bash -lc '/home/doctor/launch_xeon_X.sh'" &` on the 5800x side — the held connection keeps the VM alive; the remote launcher runs python in the foreground). This is the proven `maximalist_sequencer.sh`/`run_pathb_cluster_loop.sh` pattern.
- **⚠️ Launcher chicken-egg:** a launcher script that self-mounts the CIFS share can't live ONLY on the share (unreadable when unmounted). Use `/home/doctor/stage_launcher.sh <name>` (LOCAL on Xeon) which mounts the share + copies `code_sync/launch_xeon_<name>.sh` to a local path first, THEN the held ssh runs the local copy.
- **⚠️ cmd.exe mangles shell operators:** `ssh xeon "wsl … -- bash -lc 'a && b | c'"` — the `&& | ; > ||` get interpreted by the Windows shell, not bash (see also [feedback_xeon_ssh_quoting]). Keep operators inside a real `.sh` file run by a single operator-free invocation; for `pkill` use `wsl … -- pkill -TERM -f X` (no `bash -lc`, no inner redirects).
- **GPU read:** the WSL-native `nvidia-smi` may throw `NVML: Function Not Found` (version mismatch); the Windows interop `nvidia-smi.exe` works from WSL and isn't fooled. (Windows Task Manager's default GPU graph shows the **3D** engine — CUDA compute is under a separate **Compute/Cuda** engine you must select, else WSL torch looks idle.)

## Third machine — laptop (REBUILT 2026-06-15 → Windows 11 + WSL2 Ubuntu)

> ⚠️ **REBUILT 2026-06-15: the laptop is NO LONGER pop-os.** It's now **Windows 11 + WSL2 Ubuntu 26.04** at LAN **192.168.0.221** (on the LAN, not Tailscale — like the xeon). Reach it via `ssh laptop` (Windows cmd.exe, user `Doctor`) or `ssh laptop-wsl` (direct WSL2 bash :2222, user `doctor`); passwordless key + sudo. Mirrored WSL networking (Hyper-V firewall rule, no portproxy). WSL idle-shuts-down but a scheduled-task keepalive (`WSL-KeepAlive`, onlogon) keeps it up. CUDA/torch/repo/CIFS NOT yet set up. **Current details: memory `reference_laptop_cluster_access`.** Everything below is the OLD pop-os setup (historical).

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

## Operating norms (learned the hard way — don't violate)

- **Test as you go.** Don't ship code without pytest coverage of the contract.
- **Branch per phase.** `phase-0-setup`, `phase-1-engine-wrapper`, `phase-2-mcts`, … kept separate; merging to `main` is a separate decision per phase.
- **Parallelize CPU-bound jobs by default.** The local box (CPU swapped to a **5900XT, 16C/32T**, 2026-06-09; paths/hostnames still say "5800x") fans out big on engine simulations — but self-play is DRAM-latency-bound, so the W optimum stays ≈14–16 regardless of core count. Bench: `scripts/bench_workers.py`.
- **State ETA before launching anything ≥30s.** Use `scripts/bench_quick.py` data to estimate. Verify parallelism with `ps -o %cpu` immediately after launch.
- **Ask which machine before any multi-minute run.** Three boxes are available — the 5800x-box (5900XT), the Xeon (192.168.0.110), and the laptop (`ssh laptop`). Before launching anything expected to take more than a few minutes (self-play, evals, sweeps, benches), state the ETA and ask Joshua which box to use, or whether to split. Don't silently default to the 5800x. (For self-play/RL *loops* the standing default is ALL 3 boxes with work-stealing — see auto-memory `feedback_use_all_cluster_boxes`.)
- **Profile components when a hot path is slow.** If a workflow benchmark is >2x slower than its components imply, find the gap before launching long jobs (this saved ~3 hours in Phase 2).
- **Bench, then extrapolate, then commit — don't skip the bench step.** When scaling worker counts or memory caps on a new box: measure real VRAM/CPU load at one known-safe config, subtract a margin (1 worker / 10% mem), then commit to that for the long run. Don't jump from "ran fine at N" to "let's try 2N" without an explicit measurement. The 2026-05-12 carcassone OOM came from extrapolating from prior calculations instead of measuring.
- **Pre-flight smoke must use PRODUCTION knobs, not arbitrary ones.** Smoke at the same sims, batch_size, leaf_eval, worker count, and orchestrator-or-not as the upcoming scaled run. Linear extrapolation from a cheaper smoke is unreliable — per-leaf cost can grow nonlinearly with game length (more placed meeples = more farm/city util calls), batching/orchestrator interactions are config-specific, and cloud workers have different bottleneck profiles than local. On 2026-05-15 a sims=50 smoke extrapolated to sims=200 cloud was 6× off in wallclock; this cost ~$0.30 of contaminated training data before catching it.
- **A bug fix in scored heuristics shifts hyperparameter optima.** When fixing a correctness bug in a leaf eval or scoring function, re-sweep the tunables (caps, weights, thresholds) before trusting old bench numbers. The 2026-05-15 v2.5 farm/city dedup fix dropped wr from 80% → 70% at the previously-tuned cap=5; a re-sweep found cap=12 + drop-3-open → 90%. The old optima were tuned against inflated bonus magnitudes.
- **Results discipline — `experiments/results.csv` is the source of truth for experiment numbers** (added 2026-05-28 after disorganization caused a false production change — the "c=3 +47 elo" that was a noise spike; see DECISIONS 2026-05-28). Rules:
  - STATUS / EXPERIMENTS / DECISIONS *cite* results.csv; they must not carry authoritative numbers that drift out of sync with it.
  - **Before declaring any finding, query the table for prior measurements of the same cell.** A new result that contradicts a prior one is not a discovery until the contradiction is resolved.
  - **n-thresholds (CORRECTED 2026-06-02, round-2 audit G-M1 — old figures were ~2× too optimistic):** near wr=0.5, σ_elo ≈ 695·√(0.25/n) for an UNPAIRED head-to-head → **n=100 → 1σ ≈ ±35 elo**, **n=400 → 1σ ≈ ±17 elo**, **±9 elo needs n ≈ 1500**. So **n=100 is a coarse screen; n=400 is a verdict ONLY for effects ≥ ~35 elo (2σ)** — it CANNOT resolve a +20 elo gain. Deck-PAIRING (same deck both colors, G-M2) ~halves variance → n=400 paired ≈ ±12 elo; prefer it. The 2026-06-02 re-baseline "+25.2 ± 17.4" was z=1.45 = **inconclusive**, NOT a verdict. Size n / pair / use a margin estimator to the effect you expect. Never promote a finding from a single screen. **A lone value that beats its parameter-neighbors by >1σ is a noise signature, not a peak** — re-measure before believing it.
  - Every eval must write a self-describing `manifest.json` (full resolved config) so results never again require dirname archaeology to interpret.
- **Pre-launch process census — do it BY DEFAULT, don't wait to be asked.** Before any cluster launch, census what's already running (`ps -o pid,etime,%cpu,comm -C python --sort=-etime`, plus the dashboard `scripts/cluster_status.py --share /mnt/c/carc-shared`, plus `ssh xeon/laptop` equivalents). Joshua asked for this census 31× in one week (2026-06-02 audit) — make it a reflex, not a response. Remember a killed mp main does NOT reap its spawn workers (kill by exact pid).
- **Don't block-poll with foreground `sleep`.** The #1 wall-clock + interrupt sink (447 sleeps / ~2.8h in one week). Use the Monitor tool with an until-loop, or `run_in_background=true` and wait for the completion notification. Short poll sleeps (`do sleep 2; done`) are fine; a foreground `sleep ≥10s` is the smell. The project PreToolUse hook blocks it (`# allow-sleep` overrides).
- **Self-knowledge / doc freshness.** Recurring "where are we / why did it stop / what happened to iters N–M" churn (raised 39× in a week) = state not captured. Keep STATUS.md answer-ready (what's running, why it stopped, last verdict) and results.csv + per-run `manifest.json` authoritative, so a fresh thread doesn't reconstruct from scratch.
- **Point, don't copy (added 2026-06-12 after the 3-agent doc review).** Facts that change — champion, production config knobs, elo numbers, W counts — live in exactly ONE canonical file (`governance/PRODUCTION.yaml`, `experiments/results.csv`, `governance/CHECKPOINT_LINEAGE.csv`); prose *cites* them. If you're typing a number or a superlative ("current best") into a markdown file, stop and link the canonical source instead. (The review found CLAUDE.md itself crowning a river-era net "current global-best" two evidence-epochs after it was superseded.)
- **Experiment close-out checklist — five touches, one sitting.** When a run concludes (verdict lands, fold happens, lever killed): (1) results.csv row → (2) DECISIONS index line → (3) **status stamp on the spec doc** (the house style is PATH_B.md's banner) → (4) **governance row flip** (CLAIM_REGISTRY / CHECKPOINT_LINEAGE) → (5) STATUS top block. Touches 3+4 are the historical leaks (9 unstamped docs + a 4-day CL-005 lag found 2026-06-12). Then run `python3 scripts/doc_lint.py` — it catches broken/untracked links (E, blocks commits via the PreToolUse hook), missing status banners, stale "running/pending" markers, and dead pointers (W, advisory).
- **Fail loudly.** If a result doesn't match the spec, surface it.

## Engine notes

The vendored `engine/` (wingedsheep) is patched. See DECISIONS.md for the full list, but in summary:
- Tied-feature scoring fixed (engine returned None on ties; canonical rules say all tied players score full points)
- **Farmer-adjacency / farm-scoring fix (2026-05-29):** `opposite_farmer_side` had a non-bijective typo (`TRT→BRR`) that made farmer adjacency asymmetric, so `FarmUtil.find_farm` returned start-dependent regions → farm scores were nondeterministic across processes (~2.2% of games) and double-counted same-player farmers on one field. Fixed to `TRT→BRB` (involution) + rewrote `find_farm` as a complete connected-component traversal. `find_farm` is now start-independent. See DECISIONS 2026-05-29.
- **⚠️ The object `find_farm` path is NO LONGER the production leaf hot path (2026-06-09):** production gen/eval runs the de-objectified **`flat_leaf.py`** (`CARCASSONNE_USE_FLAT_LEAF=1`, deployed mid-attempt-2, bit-exact under canonical fsum, ~2.26× per leaf / ~+8% cross-box — DECISIONS 2026-06-09 leaf-deploy). It computes the v2.7 leaf from an int union-find decomposition with no deepcopy / no Farm/City objects / no `count_final_scores`. The old "find_farm pointer-chasing = the DRAM wall" story applies only to the legacy object path (`USE_FLAT_LEAF=0`); don't profile or optimize that path expecting production wins. (`compact_leaf.py`/`USE_COMPACT_LEAF` is a separate, superseded attempt — stays OFF.) Remaining flat-leaf profile (2026-06-12, /tmp/profile_leaf.py): `decompose` enumeration ~45%, union-find dict/set bookkeeping ~22%, `_label_components`+`find` ~9%, residual enum-hashing ~8% — no single easy lever left.
- Numpy 2.x compatibility fixes
- `state.open_positions` adjacency tracking added — `TilePositionFinder` no longer scans the full 35×35 board
- `StateUpdater.apply_action_inplace` added for MCTS rollouts (avoids deepcopy)
- Lazy tkinter import (was breaking headless WSL)
- Verbose-flag-gated debug prints (CARCASSONNE_VERBOSE=1 to restore)

Don't `git pull` upstream into `engine/` — we vendored specifically to keep these patches. Re-extract from upstream only if you also re-apply the patches.

## Current scope of completed work (point-in-time)

- **Phase 0 ✅** scaffolding, sanity checks, measurements, vendor + patches. On `phase-0-setup`.
- **Phase 1 ✅** AlphaZero-style game wrapper (Game, Board, action_space, board_repr, features, eta, legal-moves cache). On `phase-1-engine-wrapper`. 39 tests pass. 1000-game fuzz clean.
- **Phase 2 ✅** Vanilla MCTS + state-mutation rollout optimization. MCTS(s=20) won 96/100 vs random. On `phase-2-mcts`.
- **Phase 3 ✅** Network (6×96 ResNet, 7M params) + heuristic warmstart at 100K positions, tau=0.5. `checkpoints/warmstart_canonical.pt` is the canonical baseline. Closure decision: skip remaining warmstart iteration, proceed to Phase 4. See DECISIONS.md "2026-04-29 — Phase 3 closure".
- **Phase 4 (active)** Self-play loop on `phase-4-selfplay` (and `gpu-orchestrator` for the inference-server work). v1-v6 recipes (NN-value leaf) plateaued; the breakthrough was switching to the **v2.7 virtual_score leaf** + retuned caps + dedup fix. Two retrain iterations followed: `checkpoints/v25_retrain/iter_00.pt` (1200 games, +21pp over warmstart_canonical) and `checkpoints/v25_retrain_iter01/iter_00.pt` (+13.3 over iter_00 / n=100, 2026-05-16). Then Option B (`score_diff` value targets) at iter_B1, and the sims=800-teacher `v25_retrain_deepsearch` — both **river-era, historical only** (their "global-best" claims were invalidated by the 2026-06-02 base-only reframe + the 2026-06-07 clean ruler; see governance/CHECKPOINT_LINEAGE.csv). **The champion of record lives in `governance/PRODUCTION.yaml`** (as of 2026-06-11: `flywheel_residual_attempt2/ckpt/iter8.pt` + RESIDUAL_SCALE=0.25 + FLAT_LEAF=1); everything earlier in this paragraph is lineage history, not a checkpoint-picking guide. The v6 `iter_12.pt` is superseded.

For real-time status see [STATUS.md](STATUS.md).
