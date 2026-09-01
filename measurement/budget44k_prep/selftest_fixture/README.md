# `selftest_fixture/` provenance

**REAL emitter output, not hand-authored** — the FIXTURE-TRAP the build brief
names explicitly. Two fixtures, one per cell shape, generated 2026-09-01 in the
build worktree (`agent-a81935f593cde650e`, HEAD `51164b2d`) by the exact CLI
shape `launch_budget44k.sh::run_chunk` builds:

```bash
CARCASSONNE_FIX_R9=1 PYTHONPATH=./src:./engine \
  nice -n 19 /home/doctor/projects/carcassone/.venv/bin/python \
  scripts/classical_search/eval_fair_puct.py \
  --backend rust --info fair \
  --k-dets <CK> --sims <CS> --opp-k-dets 2 --opp-sims 32 \
  --exact-k 2 --opponent fair-champion \
  --n 4 --paired --seed-start <SEED> \
  --workers 4 --out-root <tmp> --out-subdir SMOKE_tiny_<CELL>__c1 \
  --rules-profile fixed_v1 \
  --cand-tiearb-enabled --cand-tiearb-b 64 --cand-tiearb-j 4 \
  --cand-tiearb-mode argmax --cand-tiearb-salt tiearb2-deploy-v1 \
  --cand-tiearb-eps 0.0 --cand-tiearb-phase-gate all \
  --opp-tiearb-enabled --opp-tiearb-b 64 --opp-tiearb-j 4 \
  --opp-tiearb-mode argmax --opp-tiearb-salt tiearb2-deploy-v1 \
  --opp-tiearb-eps 0.0 --opp-tiearb-phase-gate all \
  --allow-selfplay-seeds
```

| fixture | `<CK>x<CS>` (candidate) | opponent | `<SEED>` | shape |
|---|---|---|---|---|
| `CELL_K32/` | `k4 × 32 = 128` | `k2 × 32 = 64` | `173000999100` | **double WIDTH at the held depth** |
| `CELL_SIMS/` | `k2 × 64 = 128` | `k2 × 32 = 64` | `173000999200` | **double DEPTH at the held width** |

## Why the budgets are TINY but RATIO-PRESERVING

The real cells run `44032` vs `22016` — far too expensive for a fixture. These
run `128` vs `64`: **the same 2× ratio and the same allocation shape**, scaled
down ~344×. That is what lets the magnitude-free gate **`G-BUDGET-RATIO`** be
genuinely exercised on a real emitter's manifest — and `G-BUDGET-RATIO` is the
gate that catches the failure an operator would actually introduce (omitting
`--opp-k-dets`/`--opp-sims`, which does not error and silently produces a
symmetric cell).

⛔ **`G-BUDGET` (the frozen `44032`/`22016` magnitudes) is EXPECTED to FAIL on
these fixtures**, and the selftest **asserts that it fails**. If it ever passes,
either the fixture has silently become a real cell or `G-BUDGET` has stopped
pinning magnitudes.

## What they prove, and what they do not

* **Prove** — the launcher's CLI shape really does land on the manifest and the
  summary as an asymmetric-budget cell (`config.champion.*` /
  `config.opponent.*`, plus the second witness
  `summary.asymmetric_budgets=true` with its `candidate_*`/`opp_*` triples);
  that **both** seats resolve to `DEPLOYED_TIEARB_B64`; and — the *positive
  control* — that **both** arbiters actually **fired in play**
  (`tiearb_fired_plies_total` 65 / 76 candidate, 65 / 71 opponent over 4 games
  each), not merely that two healthy-looking dicts were written.
* **Do NOT prove** anything about the real cells' strength question. Four
  tiny-budget games on two decks per fixture is a plumbing check. Their margins
  and elo are **never** cited as evidence for or against any branch of
  `PREREG.md` §4, and their seeds sit inside `screen_lib.THROWAWAY_BASE`'s
  span — outside every registered clean-eval band, claiming no band, touching
  no `governance/BAND_REGISTRY.csv` row.

## Files, per cell

* `manifest.json`, `summary.json` — copied verbatim from the run above.
* `seed…_a0.json` / `_a1.json` × 2 decks — the four per-game records.
* `PINNED_SRC_REV` — `51164b2daaa857ca75f5dcae4b4724e92d296438`, the exact
  commit the fixtures were generated at (`manifest.code_rev` is the 8-char
  prefix `51164b2d`; `screen_lib.rev_matches` canonicalizes against this file).
* `CLAIMED_BAND` — the throwaway seed-start this fixture actually used. **NOT a
  real claimed band**: the selftest reads it only so `G-BAND`/`G-DECKS` have
  something self-consistent to check against, rather than showing a permanent,
  uninformative failure on every run.

## Regenerating

```bash
./launch_budget44k.sh --smoke      # writes SMOKE_tiny_<CELL>__c1 archives
                                   # under $SHARE/budget44k_smoke and
                                   # self-adjudicates each
```
then copy `manifest.json`, `summary.json` and the `seed*_a*.json` files into
the matching `selftest_fixture/<CELL>/`, and update `PINNED_SRC_REV` /
`CLAIMED_BAND` if the commit or seed-start moved. `--smoke` derives the tiny
ratio-preserving budgets from `screen_lib.CELLS` itself, so they cannot drift
from the cells they stand in for.
