# STATUS — live state of in-flight work

> **Current state only.** A fresh thread reads [CLAUDE.md](CLAUDE.md) → here and takes over. The historical "Right now" narrative (carc-orch saga, hardware investigation, cluster-wiring epochs) is frozen in [STATUS_ARCHIVE.md](STATUS_ARCHIVE.md); the durable record is dated [DECISIONS.md](DECISIONS.md) entries + git log. **Do NOT re-stack old epochs here** — update the blocks below in place, and run the 5-touch close-out (CLAUDE.md) when a run concludes.

## Right now (2026-06-19) — Hybrid-handoff DONE; building solver-grounded K=4 endgame probe
- **Hybrid-handoff experiment COMPLETE** (Phase 1 + Phase 2). VERDICT: iter8's endgame is locally **PATCHABLE** (hybrid beats iter8, reproduced n=400 z≈+6) but **gap-closing, NOT a new champion** — neither hybrid:5/8 beats heur@3200 (lose at |z|<1). Champion unchanged. Writeup: **[measurement/level2/LEVEL2_HYBRID_VERDICT.md](measurement/level2/LEVEL2_HYBRID_VERDICT.md)**; numbers in results.csv `l2hyb_*`.
- **Active task: solver-grounded late-game probe** — measure how close iter8/heur@800/heur@3200/hybrid are to EXACT solved play at K=4 (+ K=5 feasibility). Scaffolding built+committed: exact **alpha-beta** clairvoyant solver ([scripts/level2/endgame_solver.py](scripts/level2/endgame_solver.py), 0-mismatch vs oracle on K2/K3), **multi-source generator** ([scripts/level2/gen_endgame_multisource.py](scripts/level2/gen_endgame_multisource.py), greedy/iter8/heur/hybrid, action-replay reconstruction bit-exact), regret harness wired. User chose make/unmake+alpha-beta first, Rust deferred (port = ~1–1.5k LOC of vendored engine + validation gauntlet for ~+1 K; alpha-beta is exact, language-independent, reuses trusted engine).
- **Cluster:** local free (Phase 2 done); **K=4 AB feasibility running on Xeon** (`/mnt/c/carc-shared/l23_ab_feas_xeon.log`). Laptop DOWN (431M bundle thrash / :2222 flap). Key open number: does alpha-beta crack K=4 clairvoyant, or is make/unmake also needed (marginalized needs it regardless — died at K=2).
- **Branch:** `stage-b-wiring`. Solver commits `6e3aa5e`/`597ccf8`/`113a247`.

## Last verdicts (most recent first — numbers cite results.csv / the verdict doc, not retyped here)
- **Hybrid-handoff COMPLETE** (CL-026, [LEVEL2_HYBRID_VERDICT.md](measurement/level2/LEVEL2_HYBRID_VERDICT.md), results.csv `l2hyb_*`): iter8's endgame weakness is **locally PATCHABLE** — handoff to heur@3200 at k_remaining≤K beats iter8 on paired margin, monotone in K (n=400: K≤5 z=+6.23, K≤8 z=+5.79; cheap heur@800 endgame captures most of it). **But gap-closing, NOT a new champion:** hybrid:5/8 both *lose* to heur@3200 (−13.9/−19.1 Elo, |z|<1) — better than iter8's −28.7 but don't surpass the deep heuristic. Nothing promoted. Effect real but modest (small raw-Elo, large paired-z = reliable small per-game margin).
- **L2-3 endgame regret** (CL-025, [measurement/level2/LEVEL2_L23_VERDICT.md](measurement/level2/LEVEL2_L23_VERDICT.md)): exact minimax/expectiminimax solver over the final K tiles = the program's first non-circular ground truth. **iter8 plays the K=2 AND K=3 endgame the WORST** (top-1 0.667 / 0.574) — endgame precision is **decoupled from full-game Elo** (the weakest full-game agent, heur_v1@200, ties heur@3200 for best endgame). Exact solving caps at K=2 (K=3 partial 74/150, W=20 OOM'd; K≥4 needs a make/unmake solver). Blunders rare/small.
- **Joshua #8 — iter8 vs heur@3200** (results.csv `l22_iter8_vs_heur3200_b310_n400`): −28.7 elo, 180W/7D/213L, paired z=−0.70 (tie on margin; loses more games by small margins). Completes the same-band (3.10e9) ladder **+40.1 (@800) → +24.4 (@1600) → −28.7 (@3200)** — iter8's edge shrinks with heuristic depth, erased by the deepest rung.
- **Level-2 Elo block** (CL-023/024, [LEVEL2_LADDER_VERDICT.md](measurement/level2/LEVEL2_LADDER_VERDICT.md) + [LEVEL2_L22_VERDICT.md](measurement/level2/LEVEL2_L22_VERDICT.md)): ruler NOT saturated (deep heur search keeps climbing); iter8 beats heur@800 & heur@1600 same-band; the elo ladder is transitive (the scary "non-transitivity" was cross-band noise; n=400 σ≈±17.5). Band-variance disproven — orch+CY == orch-off bit-identically.
- **Deepteacher CLOSED** (clean powered-null): a stronger/deeper teacher does NOT break the plateau — policy iteration is a dead end for deep-search strength. Champion stays iter8.
- **Value-ranking kill-test** (CL-021, [value_ranking/VALUE_RANKING_VERDICT.md](value_ranking/VALUE_RANKING_VERDICT.md)): learned value/ranking formulations DISFAVORED (not probe-limited) — the value head still can't beat the v2.7 leaf.
- **Clairvoyance gap** (CL-022, [measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md](measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md)): deck-order clairvoyance is a minor contributor (~+27 elo, z−0.9); a non-clairvoyant agent is NOT mandatory for Level-2 measurement.

## Next / open (awaiting Joshua's direction — measurement gate)
- Continue the measurement-first program: build a reference that isn't saturated above v2.7 (the gate on any superhuman claim).
- **Optional:** complete the K=3 endgame suite (76 remaining positions) at low **W≤8** (the W=20 OOM lesson, banked in `feedback_worker_count_by_bottleneck`) for the full 150 — the partial already settles the qualitative finding.
- **Future tooling:** a make/unmake (no-deepcopy) endgame solver unlocks exact K=3–6.

## Reference (stable)
- **Production config:** [governance/PRODUCTION.yaml](governance/PRODUCTION.yaml) (canonical pointer).
- **Cluster hardware / per-box worker counts / launch + ssh patterns:** [docs/CLUSTER_OPS.md](docs/CLUSTER_OPS.md) + memory (`feedback_worker_count_by_bottleneck`, `reference_carc_orch_verdict`, `reference_laptop_cluster_access`).
- **Where every other fact lives:** the **"Where the truth lives"** index in [CLAUDE.md](CLAUDE.md).

## Hooks active
- **PreToolUse** `scripts/hooks/pretooluse_lint.py` (Bash + Read lint) + **PostToolUse** `posttooluse_log.py` — project-scoped in `.claude/settings.local.json` ([scripts/hooks/README.md](scripts/hooks/README.md)).
- **Stop** hook `~/.claude/hooks/idle_check_with_bg_tasks.sh` (global) — nudges active inspection during background-task waits.
