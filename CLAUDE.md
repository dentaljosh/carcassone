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
| [docs/INDEX.md](docs/INDEX.md) | **Full doc index** — every `docs/`, `measurement/`, `clean_eval/`, `governance/` file with a one-liner + status (current / superseded). Start here to find a doc instead of grepping the tree. |
| [docs/ORIGINAL_PROMPT.md](docs/ORIGINAL_PROMPT.md) | Original spec, win conditions, phase structure, "known unknowns" to verify |
| [DECISIONS.md](DECISIONS.md) | Every non-trivial decision with options-considered + reason. **Refines or overrides the original prompt.** Read before assuming any prompt number is still current. (386KB — grep by date/keyword, don't read whole.) |
| [BACKLOG.md](BACKLOG.md) | Deferred ideas, optimizations, stretch goals. Don't action without Joshua's approval. |
| [STATUS.md](STATUS.md) | Current branch, what's running, last verdicts, immediate next action (one screen). Frozen history → [STATUS_ARCHIVE.md](STATUS_ARCHIVE.md). |
| [docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md](docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md) | **The current program** — measurement-first (both strength levers exhausted; the gate is a non-saturated reference) |
| [measurement/ verdicts](measurement/level2/LEVEL2_L23_VERDICT.md) | Solver-grounded strength verdicts: Level-2 elo ladder (L2-1/L2-2), L2-3 endgame regret, the clairvoyance gap (full list in docs/INDEX.md). Each has a `*_VERDICT.md`. |
| [docs/research/foundational_audit_2026-06-02.md](docs/research/foundational_audit_2026-06-02.md) | **Why the learned value can't beat the v2.7 heuristic** — 6 root causes + 2 live bugs (the 2026-06-02 reframe; the evidence) |
| [docs/CORRECTION_PLAN_2026-06-02.md](docs/CORRECTION_PLAN_2026-06-02.md) | Master fix sequence (phases 0–3). **Supersedes the old leaf/afterstate/anchor-fraction plan.** |
| [docs/PHASE1_BUILD_SPEC_2026-06-02.md](docs/PHASE1_BUILD_SPEC_2026-06-02.md) | Concrete staged build (A→B→C, cheapest-informative-first) executing the correction plan |
| [experiments/results.csv](experiments/results.csv) | **Source of truth for experiment numbers** (elo/wr). STATUS/EXPERIMENTS/DECISIONS cite it; don't carry authoritative numbers that drift from it. (90KB — grep the row, don't read whole.) |
| [governance/](governance/README.md) | Claim registry, checkpoint lineage, evidence epochs, experiment protocols, `PRODUCTION.yaml` (the champion+config) — the machine-readable governance spine (raw→interpretation→decisions) |
| [REVIEW_LOG.md](REVIEW_LOG.md) | Multi-agent code-review findings: fixes applied (F-numbers) and deliberately deferred items (D-numbers) with rationale |
| [clean_eval/CLEAN_EVAL_AUDIT.md](clean_eval/CLEAN_EVAL_AUDIT.md) | **The trustworthy-ruler audit (2026-06-07).** Runtime-verified evaluator provenance (`src/carcassonne_ai/eval_provenance.py`, R1/R7 guards) + 11 semantic contracts + 5 clean reruns re-judging every old vs-HeuristicMCTS claim. Use this ruler for any new strength eval; absolutes are NOT blanket-discountable (the leaf effect is non-transitive). |
| [docs/CLUSTER_OPS.md](docs/CLUSTER_OPS.md) | **Cluster runbook** — 3-box hardware, reach/ssh, worker counts, share mounts, detached-launch rules, vast.ai bootstrap, pause/resume |
| [scripts/measurement_infra/](scripts/measurement_infra/README.md) | **DEFAULT measurement tooling** (not a strength lever). Building a dataset that needs roots at multiple search depths, a deep reference + shallow diagnostics, or reproducible non-greedy positions? Use this, don't roll your own: **multi-depth snapshot search** (one deep search → all sim levels, bit-exact to standalone h_L, **measured ~2× cheaper** for a full ladder, h12800-verified) · **lossless (deck-seed+action-sequence) root replay** (any policy, not just greedy) · **h200 top-2-gap tagging** · **adaptive 4-strata labeling queue**. `tests/test_measurement_infra.py`. |
| Git log | What each commit did and why |
| Auto-memory at `~/.claude/projects/-home-doctor-projects-carcassone/memory/` | Workflow feedback (parallelism rules, ETA discipline, hot-path profiling, context discipline) |

## Cluster & long-run operations → [docs/CLUSTER_OPS.md](docs/CLUSTER_OPS.md)

Three boxes are available — the 5900XT-box (local, hostnames still say "5800x") · the Xeon (192.168.0.110) · the laptop (`ssh laptop`). The full runbook — per-box hardware, reach/ssh patterns, worker counts, share mounts, the vast.ai bootstrap babysit-pattern, pause/resume — lives in **[docs/CLUSTER_OPS.md](docs/CLUSTER_OPS.md)** (read it before any cluster launch; live W-counts/modes are in memory `feedback_worker_count_by_bottleneck` + `reference_carc_orch_verdict`). The two safety invariants worth holding in head:

- **⚠️ The share mount path differs by box:** local commands use `/mnt/c/carc-shared`; anything inside an `ssh xeon/laptop` uses `/mnt/carc-shared`. (The PreToolUse lint hook blocks the two unambiguous misuses; `# allow-path` overrides.)
- **⚠️ Detach any run >~1 min** (`nohup … & disown`, or `setsid`) — Joshua's Mac→Windows→WSL setup means Mac-sleep SIGHUP *and* WSL VM-teardown both kill tty-attached jobs. The harness's `run_in_background=true` alone is NOT enough — the python child must be explicitly detached.

## Remote command rule — Claude Code drops `cd` in SSH (known failure mode)

Claude Code **silently omits `cd /path &&` from SSH Bash-tool commands** — a documented failure mode (it over-applies the Bash-tool "avoid `cd`" guidance to remote SSH, where each call starts fresh in `$HOME`). The omission is at *token generation*, upstream of the tool, so it persists through CLAUDE.md, explicit correction, and even Claude admitting it (proven 2026-06-23: a plain non-ssh `echo` of the phrase drops it too). **Retrying or "copying carefully" the inline `cd` form cannot work — don't try.**

**So never rely on `cd` in an SSH command. Use a path-stable form:**
- Git → `ssh HOST 'git -C /home/doctor/projects/carcassone <subcmd>'`
- Python → absolute paths: `ssh HOST '/home/doctor/projects/carcassone/.venv/bin/python /home/doctor/projects/carcassone/scripts/x.py'`
- Cargo → `cargo … --manifest-path /home/doctor/projects/carcassone/rust/<crate>/Cargo.toml`
- Docker → `docker compose -f /absolute/path/docker-compose.yml …`
- **Multi-step / needs the repo CWD →** a remote wrapper script that does its own `cd`, then just `ssh HOST '/home/doctor/projects/carcassone/scripts/whatever.sh'` (or `ssh HOST 'bash -s' < /tmp/x.sh` with `cd` on line 1).

Before any SSH command, verify it does NOT depend on the remote shell's starting directory. The PreToolUse lint hook blocks repo-relative SSH commands that lack a path-stable form (`# allow-nocd` overrides). Memory: `feedback_remote_ssh_pipe_script_mandatory`.

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
- **Context discipline — keep per-turn growth low (the context fills to ~400K fast; measured 2026-06-19).** grep the big source-of-truth files (`results.csv` 90KB, `DECISIONS.md` 386KB, the governance CSVs) instead of whole-file reads; delegate fan-out "read across many files" tasks to a subagent so the file dumps stay out of the main window; match reasoning effort to the task. The PreToolUse hook advises on whole-file reads >50KB. See memory `feedback_context_discipline`.
- **Self-knowledge / doc freshness.** Recurring "where are we / why did it stop / what happened to iters N–M" churn (raised 39× in a week) = state not captured. Keep STATUS.md answer-ready (what's running, why it stopped, last verdict) and results.csv + per-run `manifest.json` authoritative, so a fresh thread doesn't reconstruct from scratch.
- **Point, don't copy (added 2026-06-12 after the 3-agent doc review).** Facts that change — champion, production config knobs, elo numbers, W counts — live in exactly ONE canonical file (`governance/PRODUCTION.yaml`, `experiments/results.csv`, `governance/CHECKPOINT_LINEAGE.csv`); prose *cites* them. If you're typing a number or a superlative ("current best") into a markdown file, stop and link the canonical source instead. (The review found CLAUDE.md itself crowning a river-era net "current global-best" two evidence-epochs after it was superseded.)
- **Experiment close-out checklist — six touches, one sitting.** When a run concludes (verdict lands, fold happens, lever killed): (1) results.csv row → (2) DECISIONS index line → (3) **status stamp on the spec doc** (the house style is PATH_B.md's banner) → (4) **governance row flip** (CLAIM_REGISTRY / CHECKPOINT_LINEAGE) → (5) STATUS top block → (6) **roadmap line** ([docs/PROGRAM_ROADMAP_2026-07-07.md](docs/PROGRAM_ROADMAP_2026-07-07.md) — the single work queue; new findings/levers land there the moment they exist, added 2026-07-07 after queued work kept falling through cracks). Touches 3+4 are the historical leaks (9 unstamped docs + a 4-day CL-005 lag found 2026-06-12). Then run `python3 scripts/doc_lint.py` — it catches broken/untracked links (E, blocks commits via the PreToolUse hook), missing status banners, stale "running/pending" markers, and dead pointers (W, advisory).
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
