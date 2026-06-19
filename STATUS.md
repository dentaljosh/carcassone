# STATUS — live state of in-flight work

> **Current state only.** A fresh thread reads [CLAUDE.md](CLAUDE.md) → here and takes over. The historical "Right now" narrative (carc-orch saga, hardware investigation, cluster-wiring epochs) is frozen in [STATUS_ARCHIVE.md](STATUS_ARCHIVE.md); the durable record is dated [DECISIONS.md](DECISIONS.md) entries + git log. **Do NOT re-stack old epochs here** — update the blocks below in place, and run the 5-touch close-out (CLAUDE.md) when a run concludes.

## Right now (2026-06-19) — Hybrid-handoff experiment, Phase 2 RUNNING
- **Cluster: LOCAL BUSY (Phase 2 self-play eval), laptop idle.** Local (RTX 5060 Ti) running Phase 2 of the hybrid-handoff measurement, orch W=48, `nice -n 19`. Laptop pulled (2 transient mobile-GPU stalls). Xeon idle.
- **Running:** `scripts/level2/run_hybrid_bands_orch.sh` PH=2 (launched by `auto_phase2.sh`). Persistent progress monitor armed. Results in `/mnt/c/carc-shared/level2_hybrid/`.
- **Experiment = measurement only, no training/promotion.** Champion unchanged (iter8, [governance/PRODUCTION.yaml](governance/PRODUCTION.yaml)). Full writeup + resume steps: **[measurement/level2/LEVEL2_HYBRID_VERDICT.md](measurement/level2/LEVEL2_HYBRID_VERDICT.md)**.
- **Phase 1 DONE (verdict: PATCHABLE).** All hybrids (iter8 early/mid → heur@3200 endgame) beat iter8 on paired margin, **monotone in K** (K≤8 = +1.36 pts/game, z=4.68; reproduced n=400 z=5.61). Effect real but modest. results.csv rows `l2hyb_*`.
- **Phase 2 = champion check** (hybrid:{8,5} vs heur@3200 + K5 n=400 topup). The open question: does hybrid *beat* heur@3200 (new champion) or just close iter8's −28.7 gap? **To get the verdict:** `python scripts/level2/report_hybrid.py --root /mnt/c/carc-shared/level2_hybrid`. Done when the two `*_vs__heur3200_*` bands hit 200 each.
- **Phase: measurement-first** (no train / promote / redesign / modify-iter8). Spec: [docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md](docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md).
- **Branch:** `stage-b-wiring`. Harness committed (`d654082`).

## Last verdicts (most recent first — numbers cite results.csv / the verdict doc, not retyped here)
- **Hybrid-handoff Phase 1** (CL-026, [LEVEL2_HYBRID_VERDICT.md](measurement/level2/LEVEL2_HYBRID_VERDICT.md), results.csv `l2hyb_*`): iter8's endgame weakness is **locally PATCHABLE** — replacing iter8's endgame with heur@3200 (handoff at k_remaining≤K) beats iter8 on paired margin, monotone in K (K≤8 +1.36 pts/game z=4.68; n=400 z=5.61). Modest in absolute size; cheap heur@800 endgame captures most of it. **Phase 2 (vs heur@3200 — is it a champion or just gap-closing?) RUNNING.**
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
