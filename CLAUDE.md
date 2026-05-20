# CLAUDE.md — standing context for Claude sessions

If you're starting a new conversation in this repo, read this file first, then [STATUS.md](STATUS.md) for live state.

## What we're building

AlphaZero-style Carcassonne AI + position analyzer for family games. The win condition is **Phase 5 (game review tool that explains where points were lost)**, not raw playing strength.

Full project spec: [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md). Phase structure (0-7) and all original guesses live there.

**Locked scope** (Phases 1-5): 2-player, Base game + River expansion + Farmers, no Inns & Cathedrals, no Abbots, no Big meeples. Don't expand scope without explicit approval.

## Where the truth lives

| Source | What it answers |
|---|---|
| [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) | Original spec, win conditions, phase structure, "known unknowns" to verify |
| [DECISIONS.md](DECISIONS.md) | Every non-trivial decision with options-considered + reason. **Refines or overrides the original prompt.** Read before assuming any prompt number is still current. |
| [BACKLOG.md](BACKLOG.md) | Deferred ideas, optimizations, stretch goals. Don't action without Joshua's approval. |
| [STATUS.md](STATUS.md) | Current branch, last commit, what's running, immediate next action |
| [REVIEW_LOG.md](REVIEW_LOG.md) | Multi-agent code-review findings: fixes applied (F-numbers) and deliberately deferred items (D-numbers) with rationale |
| Git log | What each commit did and why |
| Auto-memory at `~/.claude/projects/-home-doctor-projects-carcassone/memory/` | Workflow feedback (parallelism rules, ETA discipline, hot-path profiling) |

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
- **Not yet deployed:** the WSL host is ready, but the carcassonne repo + Python env still need to be set up there before it can run training.
- The SSH-disconnect / `nohup`-detach rule above applies here too.

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
- **Parallelize CPU-bound jobs by default.** 5800X has 16 SMT threads; full fan-out wins by ~7x on engine simulations. Bench: `scripts/bench_workers.py`.
- **State ETA before launching anything ≥30s.** Use `scripts/bench_quick.py` data to estimate. Verify parallelism with `ps -o %cpu` immediately after launch.
- **Ask which machine before any multi-minute run.** Two boxes are available — the 5800X and the Xeon (192.168.0.110). Before launching anything expected to take more than a few minutes (self-play, evals, sweeps, benches), state the ETA and ask Joshua which box to use, or whether to split across both. The choice depends on each box's current ETA, availability, and what else is queued — don't silently default to the 5800X.
- **Profile components when a hot path is slow.** If a workflow benchmark is >2x slower than its components imply, find the gap before launching long jobs (this saved ~3 hours in Phase 2).
- **Bench, then extrapolate, then commit — don't skip the bench step.** When scaling worker counts or memory caps on a new box: measure real VRAM/CPU load at one known-safe config, subtract a margin (1 worker / 10% mem), then commit to that for the long run. Don't jump from "ran fine at N" to "let's try 2N" without an explicit measurement. The 2026-05-12 carcassone OOM came from extrapolating from prior calculations instead of measuring.
- **Pre-flight smoke must use PRODUCTION knobs, not arbitrary ones.** Smoke at the same sims, batch_size, leaf_eval, worker count, and orchestrator-or-not as the upcoming scaled run. Linear extrapolation from a cheaper smoke is unreliable — per-leaf cost can grow nonlinearly with game length (more placed meeples = more farm/city util calls), batching/orchestrator interactions are config-specific, and cloud workers have different bottleneck profiles than local. On 2026-05-15 a sims=50 smoke extrapolated to sims=200 cloud was 6× off in wallclock; this cost ~$0.30 of contaminated training data before catching it.
- **A bug fix in scored heuristics shifts hyperparameter optima.** When fixing a correctness bug in a leaf eval or scoring function, re-sweep the tunables (caps, weights, thresholds) before trusting old bench numbers. The 2026-05-15 v2.5 farm/city dedup fix dropped wr from 80% → 70% at the previously-tuned cap=5; a re-sweep found cap=12 + drop-3-open → 90%. The old optima were tuned against inflated bonus magnitudes.
- **Fail loudly.** If a result doesn't match the spec, surface it.

## Engine notes

The vendored `engine/` (wingedsheep) is patched. See DECISIONS.md for the full list, but in summary:
- Tied-feature scoring fixed (engine returned None on ties; canonical rules say all tied players score full points)
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
- **Phase 4 (active)** Self-play loop on `phase-4-selfplay` (and `gpu-orchestrator` for the inference-server work). v1-v6 recipes (NN-value leaf) plateaued; the breakthrough was switching to the **v2.7 virtual_score leaf** + retuned caps + dedup fix. Two retrain iterations followed: `checkpoints/v25_retrain/iter_00.pt` (1200 games, +21pp over warmstart_canonical) and `checkpoints/v25_retrain_iter01/iter_00.pt` (+13.3 over iter_00 / n=100, 2026-05-16). Then Option B (`score_diff` value targets) at iter_B1 (`checkpoints/v25_retrain_optionB_iter1/iter_00.pt`): originally called null at n=100 (49% wr), but the **2026-05-20 n=400 re-test recovered it as a real +25.2 elo / 1.5σ gain over iter_01** — **iter_B1 is the current sims=200-plane global-best**. Separately, `checkpoints/v25_retrain_deepsearch/iter_00.pt` (sims=800 teacher) is **the current sims=800-plane global-best** (+35.8 elo vs iter_01 at sims=800 / n=380, 2026-05-20). Choose the checkpoint by your play-time sims setting. The v6 `iter_12.pt` is superseded.

For real-time status see [STATUS.md](STATUS.md).
