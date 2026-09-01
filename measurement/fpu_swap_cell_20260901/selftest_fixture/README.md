# selftest_fixture/ provenance

**A REAL emitter's output, not hand-authored** (the FIXTURE-TRAP the build
brief names explicitly). Generated 2026-09-01 in the build worktree
(`agent-a939b800681c0c28c`) by:

```bash
CARCASSONNE_FIX_R9=1 PYTHONPATH=./src:./engine \
  /home/doctor/projects/carcassone/.venv/bin/python3 \
  scripts/classical_search/eval_fair_puct.py \
  --backend rust --info fair \
  --k-dets 2 --sims 32 --opp-k-dets 2 --opp-sims 32 \
  --exact-k 2 \
  --opponent fair-champion \
  --n 4 --paired --seed-start 170000999000 \
  --workers 4 --out-root /tmp/fpu_swap_smoke_fixture --out-subdir SMOKE_fixture \
  --rules-profile fixed_v1 \
  --opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4 \
  --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1 \
  --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all \
  --cand-fpu-reduction 0.2 \
  --allow-selfplay-seeds
```

Tiny budget (k2×32=64 sims, NOT the production k16×1376=22016) and n=4 games
(2 seat-balanced decks, NOT the real cell's 400) — this is a **verification
fixture, not a strength measurement**. Seeds `170000999000`/`170000999001`
sit inside `screen_lib.THROWAWAY_BASE`'s span, are never pooled into any real
cell, and claim no band (no `governance/BAND_REGISTRY.csv` row was touched to
produce this fixture).

## What it proves, and what it doesn't

* **Proves**: the exact CLI shape `launch_swap_cell.sh::run_cell` builds
  (`--cand-fpu-reduction 0.2`, no `--cand-tiearb-*` flag at all, the full
  `--opp-tiearb-*` deployed spec) really does land on the manifest as
  candidate-unarmed / opponent-armed, and the opponent's arbiter really did
  fire in play (`opp_tiearb_fired_plies_total = 77` over 4 tiny-budget games —
  the positive control the build brief asked for, not a config echo).
* **Does NOT prove**: anything about the real cell's strength question. The
  fixture's own `paired_mean_margin = -29.5`, `elo = -800.0` (0/4 losses for
  the fpu-alone candidate) is a single tiny-budget, tiny-n data point and is
  never cited as evidence for or against any branch of `PREREG.md` §4 — it
  happens to point the same direction the funding brief's own arithmetic
  predicts, which is expected under that prior and not confirmatory at n=2
  decks, tiny budget.

## Files

* `manifest.json`, `summary.json` — copied verbatim from the run above.
* `seed170000999000_a0.json` / `_a1.json` / `seed170000999001_a0.json` /
  `_a1.json` — the four per-game records (2 decks × 2 seatings).
* `PINNED_SRC_REV` — `afbc424c6e4389da460820f7c16c583653d2805d`, the exact
  commit the fixture was generated at (`manifest.json`'s `code_rev` is the
  7-char prefix `afbc424c`; `screen_lib.rev_matches` canonicalizes against
  this file).
* `CLAIMED_BAND` — `170000999000`, the throwaway seed-start this fixture
  actually used (NOT a real claimed band — `adjudicate_swap_cell.py`'s
  selftest reads it only so `gate_band`/`gate_decks` have something
  self-consistent to check; a real fixture-band mismatch would otherwise show
  up as a permanent, uninformative `G-BAND`/`G-DECKS` failure on every
  selftest run).

Regenerate by re-running the command above (bump `--seed-start` if reusing the
throwaway range matters) and `cp`-ing the five files + updating
`PINNED_SRC_REV`/`CLAIMED_BAND` if the seed-start or commit changed.
