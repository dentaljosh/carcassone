# E4 — human-vs-champion games (phone archives)

Pulled from the Pixel via adb (`run-as com.jishal.carcassonne cat files/games/*.json`),
schema `carcassonne-android-archive/v1`: lossless `(deck_seed, actions)` per the
root_replay contract, plus result summary, per-move AI latencies, and provenance
(champion id, leaf hash, effective budget).

**⚠️ Grading context: the phone plays the k4×688 mobile carve-out** (~50 elo below the
k8×1376 desktop champion of record — see PRODUCTION.yaml `deploy_profiles`); E4 stats
grade against that budget, and each archive records `sims_effective`/`k_dets_effective`.

**Replay verification (2026-07-30, desktop, PROD_ENV + project venv):** both archives
replay to termination and the desktop-recomputed final scores match the phone's recorded
scores exactly (111–113 and 73–108) — phone→desktop replay is lossless and
cross-platform (ARM/Pixel → x86/WSL) deterministic.

| file | date | result (human first) | note |
|---|---|---|---|
| `1785205383_867966.json` | 2026-07-27 | **111–113 L** | Joshua's 2nd-ever game; 2-pt loss |
| `1785466497_161583.json` | 2026-07-30 | **73–108 L** | the invisible-border game (top-row wall); farms won 27–3, during-play lost 44–89 |

Joshua's overall E4 record: 0–3 (game 1 predates the archiving feature — unrecorded by
design, not an archive bug).
