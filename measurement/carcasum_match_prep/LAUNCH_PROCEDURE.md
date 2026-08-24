# Carcasum rated match — launch procedure

> **Status: DOCUMENTED, NOT EXECUTED.** Nothing in this file has been run. The build agent
> stops at the smoke; **the orchestrator freezes the prereg pair, claims the band, and fires
> the match with its own monitors.** This file exists so that firing it is a checklist rather
> than an act of authorship at 2 a.m.
>
> Gate order: [`PREREG.md`](PREREG.md) frozen → band 1.42e11 claimed →
> launch → monitor → close out.

---

## 0. Pre-flight — refuse to launch if any of these is false

| # | check | how |
|---|---|---|
| 1 | **Prereg frozen** and blind-committed; the config in §2 matches what the command below actually sends. | read it |
| 2 | **Band 1.42e11 still free**, and no live run anywhere has a `--seed-start` in `142000000000..142000000299`. | `grep '^142000000000' governance/BAND_REGISTRY.csv` **and** a process census on every box — a band can be in flight before its registry row lands, which is exactly how 1.41e11 was lost. |
| 3 | **Laptop is an exclusive tenant.** | `ssh laptop-wsl 'bash -s' <<< 'cat /proc/loadavg; pgrep -af python \| head'` — loadavg should be ~0. A timing bench tolerates no co-tenant. |
| 4 | **Driver present and its sha256 recorded.** | the manifest stamps it automatically; note it in the readout as the primary provenance witness. |
| 5 | **Tests green** on the launching rev. | `pytest tests/test_carcasum_match.py tests/test_carcasum_tile_oracle.py tests/test_carcasum_rules_patch.py -q` |
| 6 | **Laptop synced** to the frozen rev via git bundle (remotes cannot reach GitHub). | else the match runs mixed-rev code |

## 1. The command

Run it **detached** — Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs, and
`run_in_background` alone is not enough; the python child must be explicitly detached.

Ship as a script and pipe it (`ssh laptop-wsl 'bash -s' < launch.sh`) — the inline
`ssh host 'cd … && …'` form gets the `cd` **stripped in transit**, a documented failure mode.

```sh
cd /home/doctor/projects/carcassone            # MUST be line 1
export CARCASSONNE_FIX_R9=1                    # latched at import; not a knob
CELL=measurement/carcasum_match_20260823
mkdir -p "$CELL"

setsid nohup nice -n 19 .venv/bin/python -u scripts/carcasum_match/match.py \
  --opp-kind mcts --opp-budget-ms 5000 \
  --decks 200 --champ-seat both --workers 14 \
  --seed-base 142000000000 \
  --binary vendor/carcasum/build-driver/carcasum_driver \
  --out "$CELL"/games.jsonl --resume \
  >> "$CELL"/driver.log 2>&1 &
disown
```

`--decks 200 --champ-seat both` = **n=400** (200 decks × 2 seatings, deck-paired CRN).
`--workers 14` per [`PREREG.md`](PREREG.md) §4.3 — the smallest W within ~10 % of
practical peak. **W is a throughput knob, not a strength knob**: the opponent's budget is
thread CPU-time, so contention cannot shrink its search.

⚠️ **`--resume` is mandatory, not optional.** A ~2 h run that dies at 90 % must not restart
from zero. `load_done` keys on `(deck_seed, champ_seat, replicate)`.

⚠️ Do **not** pass `--sims` or `--k-dets`. They are smoke-only overrides; the champion must
run at the `governance/PRODUCTION.yaml` deploy budget.

## 2. Verify the launch, immediately

The next command after launching, always:

```sh
pgrep -af 'carcasum_match/match.py' | head
pgrep -c -f carcasum_driver          # expect ~= workers
cat /proc/loadavg
head -3 "$CELL"/driver.log
```

A detached `ssh` launch can return **rc=124 from `timeout` after having launched**. Treat
124 as LAUNCHED and verify by census — **never retry**, because retries stack pools.

## 3. Monitor

Arm a completion watch on the on-disk signal; the watchdog only restarts a **dead** chain, it
never announces a finished one.

```sh
until [ -f "$CELL"/DONE ]; do sleep 30; done
```

**Re-project the wall after ~20 games** rather than trusting the 4-game estimate:

```sh
python3 -c "import json,statistics as st;
r=[json.loads(l) for l in open('$CELL/games.jsonl')];
w=[x['wall_secs'] for x in r if x.get('wall_secs')];
print(len(r),'games, mean wall',round(st.mean(w),1),'s ->',
      round(400*st.mean(w)/14/3600,2),'h total at W=14')"
```

Watch for, and stop on:
- **any `VOID_*` at all** in the first 20 games — the audit was clean, so a void now means
  something changed (a stale binary, a mixed-rev laptop, a co-tenant);
- `COORD_FRAME_MISMATCH` — a coordinate-frame problem, never a rules one;
- `opp_driver_ms_per_turn` drifting well above 5000 — contention, i.e. a co-tenant appeared.

## 4. Close out

Read with `scripts/carcasum_match/match.py`'s own `summarize()` (or `jcz_match/analyze.py`,
whose shapes it deliberately mirrors), then apply **§5 of the prereg exactly as written** —
the fired branch *is* the authorisation; a fired trigger gets run and reported, not
re-litigated.

Then the six touches: `experiments/results.csv` → `DECISIONS.md` index line → status banner on
the prereg → governance rows (`BAND_REGISTRY.csv` status, `CLAIM_REGISTRY`) →
`STATUS.md` → `docs/PROGRAM_ROADMAP_2026-07-07.md`. Then `python3 scripts/doc_lint.py`.

Plus, regardless of outcome, the `docs/LEVER_INDEX.md` rows the inventory asked for:
**"Carcasum external reference"**, and DECLINED rows for *Carcassonne-SGE*, *SYNCS Bot
Battle*, *Asmodee Conqueror*, *OpenSpiel / Ludii — game absent*.

## 5. What must appear in the readout

- The **realized** budget both sides (`champ_ms_per_move_mean`,
  `opp_driver_ms_per_turn_mean`, `opp_driver_playouts_per_turn_mean`) — a strength number
  against a budgeted opponent is meaningless without it.
- **Median, not mean, for playouts/turn.** The distribution is skewed ~35× by endgame plies;
  the mean is an artefact ([`SMOKE_READOUT.md`](../carcasum_smoke_20260823/SMOKE_READOUT.md) §2).
- The **deck-paired margin** as the estimator of record, win-rate/elo alongside.
- Void counts by class, and the divergence counts — **zero REAL is the bar**, matching the
  audit.
- The standing caveats: **R9-on, so not comparable to `walled` production elo**; the opponent
  is **non-CRN**; and the transitive **+188 is not a prediction** and is not to be compared
  against.
