# RUNBOOK — overnight chain 2026-08-12 (D1 targeted-denial · S1 sims-split)

> **STATUS: LAUNCHED AND COMPLETED 2026-08-12. Six-touch closed out 2026-08-12.**
> The chain ran both blocks to completion — **D1** (2 denial cells, band **1.21e11**, both
> resolved negative at the 2750 ablation instrument; the dose-1.0 cell's pre-registered
> top-up subsequently fired and pooled to n=400, margin z **−2.293**) and **S1** (sims-split
> screen, band **1.22e11**, bounded null, margin z **−1.037**). Both bands are now **retired
> decision-influenced**. Extracts in `verdicts/`. The chain claimed its bands and wrote its
> registry rows *at launch*, one per block; `governance/PRODUCTION.yaml` was never touched,
> by this doc or by any script it describes. **Nothing promoted.** The runbook's own
> post-mortem of the FALSE `BLOCKED_D1` (the two-box cell-table gate) stands as written.

Driver: [`denial_simsplit_chain.sh`](../../scripts/classical_search/denial_simsplit_chain.sh) ·
watchdog: [`denial_simsplit_watchdog.sh`](../../scripts/classical_search/denial_simsplit_watchdog.sh) ·
capability probe: [`chain_capability_probe.py`](../../scripts/classical_search/chain_capability_probe.py) ·
band claim: [`claim_next_band.py`](../../scripts/classical_search/claim_next_band.py) ·
D1 per-box launcher: [`denial_cell_launcher.sh`](../../scripts/classical_search/denial_cell_launcher.sh) ·
S1 per-box launcher: [`menu_fair_cell.sh`](../../scripts/classical_search/menu_fair_cell.sh) ·
tests: [`test_night_chain_helpers.py`](../../tests/test_night_chain_helpers.py)

---

## 1. What it runs

| block | question | instrument | cells × n | budget | prereg |
|---|---|---|---|---|---|
| **D1** | does targeted denial at dose *d* beat the champion leaf? | `eval_puct_priors.py` (the 2750 ablation class), rust both sides | 1–4 × **200** deck-paired | `--cand-sims 2750` both sides, `--exact-k 2` | [denial screen](../denial_screen_20260811/PREREG_DRAFT.md) |
| **S1** | does re-splitting a turn's sims between the tile and the meeple search beat an even split? | `eval_fair_puct.py --info fair --opponent fair-champion`, rust | 1 × **200** deck-paired | production **k8×1376** both arms, split on the candidate only | pre-gate: [simsplit census](../simsplit_census_20260811/PREREG.md) |

Serial, S1 gated on D1. Both blocks: `fixed_v1` + `CARCASSONNE_FIX_R9=1`, deck-paired,
two-box work-stealing via `--shared-claim` (local **W=30**, laptop **W=22**), `nice -n 19`,
everything detached and resumable. Candidate side always carries the knob; the opponent is
always the intact champion leaf `a36d2e15a3b3d71d`.

**The chain adjudicates nothing.** No verdict, no promotion, no `results.csv` row, no top-up.
It writes per-block extracts into `verdicts/` and stops.

Rough cost at these W's: D1 ≈ 0.3 h/cell (ablation class ~1490 g/h two-box), S1 ≈ 0.4 h.

## 2. Parameters — every one is REQUIRED, none has a default

| variable | block | meaning |
|---|---|---|
| `DENIAL_DOSES` | D1 | comma list, 1–4 values, e.g. `"1.0,2.0"`. One cell per dose. `0.0` is refused (it is the identity control, byte-identical to the champion). |
| `DENIAL_SIZE_MIN` | D1 | `LeafConfig.denial_size_min` — the `city_root_delta` threshold. |
| `DENIAL_OPEN_MAX` | D1 | `LeafConfig.denial_open_max` — max open edges for "near-complete". |
| `SIMS_TILE` / `SIMS_MEEPLE` | S1 | per-phase sims per determinization. Must sum to `2 × 1376 = 2752` (fixed per-turn total) or the block refuses. |

Optional overrides: `W_LOCAL` (30), `W_LAPTOP` (22), `D1_N` / `S1_N` (200), `D1_SIMS` (2750),
`S1_KDETS` / `S1_SIMS` (8 / 1376), `CHAIN_REPO`, `CHAIN_PY`, `CHAIN_LAPTOP`, `CHAIN_REGISTRY`.

A missing knob value is a **hard stop**, never a default: a defaulted dose runs a cell nobody
chose. The resolved values are persisted to `PARAMS.env` (assign-if-unset, so a live env always
wins) so a watchdog restart resumes with exactly what game 1 ran under.

## 3. Launch

```bash
# 0. rehearse — prints every command per block, executes none
DENIAL_DOSES="1.0,2.0" DENIAL_SIZE_MIN=5 DENIAL_OPEN_MAX=3 \
  bash scripts/classical_search/denial_simsplit_chain.sh --dry-run

# 1. for real (detached: Mac-sleep SIGHUP and WSL VM teardown both kill tty-attached jobs).
#    The mkdir is not optional — the shell opens the redirect before the script can create it.
mkdir -p measurement/night_chain_20260812/logs
DENIAL_DOSES="1.0,2.0" DENIAL_SIZE_MIN=5 DENIAL_OPEN_MAX=3 \
setsid nohup nice -n 19 bash scripts/classical_search/denial_simsplit_chain.sh \
  >> measurement/night_chain_20260812/logs/chain.log 2>&1 < /dev/null &
```

**Before launch, rebuild + install the combined `carc_rs` wheel on BOTH boxes.** The chain
will refuse to start D1 otherwise (§4), which is the intended behaviour, not a bug.

Arm the watchdog (separate crontab entry; the lever-menu watchdog keeps its own and is
untouched):

```
*/10 * * * * /home/doctor/projects/carcassone/scripts/classical_search/denial_simsplit_watchdog.sh
```

## 4. The capability gate (the reason this chain exists in this shape)

The installed wheel predates both knobs. A candidate arm whose knob the loaded build ignores
still runs, still completes, still writes a clean manifest — and yields a **beautiful,
meaningless null**. So before game 1, on **both boxes**, the probe requires:

1. the knob exists on the Python side (`LeafConfig.denial_*`, `flat_leaf.flat_denial_term`);
2. the caller's env canon really is the champion (`DEFAULT_CONFIG` hashes `a36d2e15a3b3d71d`);
3. every cell's candidate hash differs from the champion's and from every other cell's;
4. the loaded `carc_rs` **accepts** the denial kwargs (`rust_agent.leaf_config_rs` forwards
   them only for a nonzero dose, so a stale wheel raises `TypeError` instead of silently
   serving a default-off leaf);
5. `leaf_terms` exposes `denial_term`; and
6. **the dose actually moves leaf values** — a short scripted playout through the rust mirror
   must produce at least one changed value, while the champion-vs-champion identity control
   stays bit-identical on every sampled value. (5) and (6) are what separate "accepted" from
   "accepted and ignored".

Both boxes' cell tables must **agree** or the chain blocks: differing hashes mean the two
boxes are not computing the same candidate leaf, and their games land in the same dir.

### 4a. Post-mortem — the 2026-08-12 01:23 `BLOCKED_D1` was a FALSE positive

Both probes had in fact PASSED with identical hashes. The gate itself was broken twice over,
and the fix (commit `afc28c5`, `scripts/classical_search/chain_compare_cell_tables.py`) is
worth understanding because the second half is the dangerous one:

1. **It could never pass.** The chain ran `diff -q $SHARE/d1_cells.tsv $LSHARE/d1_cells.tsv`
   *on the local box*. `$LSHARE` (`/mnt/carc-shared`) is the **laptop's** mount prefix; on the
   local box that path is an empty stub directory. `diff` exited 2 on a missing file, the
   `2>&1` swallowed *"No such file or directory"*, and the chain reported "candidate leaf
   hashes disagree" about a table it had never read.
2. **It would have been vacuous if it could.** `$SHARE/x` and `$LSHARE/x` are **one physical
   file** on the CIFS store (verified: identical md5, and a marker written locally is visible
   from the laptop). Both probes wrote that single path — the laptop's write just overwrote
   the local box's — so a prefix-corrected `diff` would have compared the file to **itself**
   and passed unconditionally, including when the boxes genuinely disagreed.

The gate now: each box writes a **box-distinct basename** (`d1_cells.local.tsv` /
`d1_cells.laptop.tsv`), both are read under the **local** prefix, and
`chain_compare_cell_tables.py` hard-blocks with a distinct message on a missing/empty remote
table, a **stale** remote table (deleted before the probe, freshness enforced by mtime), the
two paths sharing a `dev+ino`, a malformed table, or a real hash disagreement (naming both
sides). It compares **parsed rows**, so CRLF / trailing-newline noise cannot fake a block. The
laptop probe now also persists `verdicts/D1_capability_laptop.json`, and a probe that exits 0
without one is a hard block. The canonical `d1_cells.tsv` the launchers read is written only
**after** the gate passes, so a blocked run leaves no table for a launcher to pick up.

**Generalisable trap:** any command that names both mount prefixes runs on exactly one box, so
at most one of those paths is real. Cross-box file comparisons must bring the remote artifact
*under the local prefix* and give it a *different basename*.

Second, independent check at read time: each cell's extract is produced with
`menu_block_summary.py --expect-cand-leaf-hash`, which fails the wiring gate — and stamps
`READ_BLOCK` — if the manifest's `cand_leaf_hash` is not the expected one, calling out
explicitly the case where it *is* the champion's hash.

## 5. S1's hard gate

S1 runs only if **both** hold:

- **(a) `measurement/night_chain_20260812/S1_AUTHORIZED` exists.** Joshua creates it by hand;
  no script ever creates it. It attests the split knob's byte-identity gate came back clean —
  a game-level property this chain cannot verify and must not assume.
- **(b) `eval_fair_puct.py` advertises `--sims-tile` / `--sims-meeple`** on *both* boxes
  (probed from the harness's own `--help`), and the split sums to the fixed per-turn total.

Either missing ⇒ S1 **skips loudly** (`SKIPPED_S1` marker + a chain-log line) and the chain
finishes clean, so D1's result is never held hostage to a knob that did not land. The one
case that is a hard **block**, not a skip: the go-file exists but `SIMS_TILE`/`SIMS_MEEPLE`
are unset — an authorized-but-unparameterized S1 must never be silently passed over.

## 6. Bands

Each block claims **its own** band at **its own** launch, after its gates pass and before
game 1: `claim_next_band.py` takes the next free 1e9-aligned band above the registry's
high-water mark (never a gap below it — unregistered probe bands live there), appends a row
via `csv.writer`, and memoizes the number in `BAND_D1` / `BAND_S1`. A resume re-reads the
sentinel, so a restart cannot burn a second band or split one cell's decks across two bands.
Rows are written with `decision_influenced=pending`; **close-out flips them to yes/no and
appends the verdict to `notes`** (`doc_lint` W4 surfaces live rows on purpose).

At time of writing the registry's high-water mark is 1.20e11, so D1 would take **1.21e11** and
S1 **1.22e11** — but the script reads the file, it does not assume this.

## 7. Reading the output

```
measurement/night_chain_20260812/
  logs/chain.log            the chain's own narration (start here)
  logs/D1_local.log         local launcher; per-pass rc + record counts
  logs/D1_probe*.log        capability probes, both boxes
  logs/laptop_launch.log    remote launch rc (124 == launched-and-detached, NOT a failure)
  verdicts/BLOCK_D1_<cell>.json   per-cell extract: n/W/D/L/elo/paired_z + wiring gates
  verdicts/BLOCK_S1.json
  verdicts/*_capability_*.json    what the probe saw, per box
  BAND_D1 / BAND_S1         the claimed bands
  DONE_D1 / DONE_S1         completion sentinels (a re-run skips these blocks)
  SKIPPED_S1 / BLOCKED_*    why a block stopped
/mnt/c/carc-shared/night_chain_20260812/<cell>/   records, summary.json, manifest.json
```

Read order for any cell: **`wiring_gates_clean` first, numbers second.** If `READ_BLOCK` is
present, the numbers are not readable — verify wiring from the manifest before anything else.
Primary statistic in both blocks is the **deck-paired margin z**; elo is for readability. At
n=200 paired the resolution is ~±35 elo at 2σ — a null is a *bounded* null, never "flat".

## 8. Pause / resume

- **Pause:** kill the chain shell by **exact pid** (`pgrep -f denial_simsplit_chain.sh`), then
  the launcher and its workers by exact pid. Never `pkill -f` from inside the repo — the
  pattern appears in these scripts' own cmdlines. Killing an mp main does **not** reap its
  spawn workers; kill those by pid too, and remember to disarm the watchdog crontab line first
  or it will restart the chain within 10 minutes.
- **Resume:** just re-run the launch command (or let the watchdog do it). Every leg is
  `--shared-claim`, completed blocks skip on their `DONE_` sentinels, the band claim is
  idempotent, and stale claims-without-records older than the grace age are swept on entry.
- **After a crash**, clear any `BLOCKED_*` marker only once you have fixed what it names —
  the watchdog deliberately refuses to relaunch while one exists.

## 9. If it is dead in the morning — check in this order

1. `tail -40 logs/chain.log` — the chain narrates every gate and every block boundary.
2. `ls BLOCKED_* SKIPPED_*` — a `BLOCKED_` file states the exact reason and the resume recipe;
   a `SKIPPED_S1` is a *clean* outcome (S1 declined its hard gate).
3. `tail -20 logs/watchdog.log` — did it restart, refuse (missing `PARAMS.env`), or see the
   "chain dead but workers alive" anomaly (it never relaunches into that; stacked pools).
4. `verdicts/D1_capability_local.json` + `logs/D1_probe_laptop.log` — if the block never
   started, the overwhelmingly likely cause is a box still on the pre-denial wheel.
5. Record counts: `find /mnt/c/carc-shared/night_chain_20260812/<cell> -name 'seed*.json' | wc -l`.
   Under 90% of n at read time ⇒ the cell is VOID by the standing rule.
6. Laptop reachability (`ssh laptop-wsl true`) and rev match — the chain refuses to launch a
   two-box block unless the laptop is at the same commit; a stale remote is contamination.

## 10. Known limits — what I would not trust unattended

- **S1's bit-exactness is a human attestation, not a probe.** The chain proves the flags
  exist, and that the split sums to the fixed total. It cannot prove the split path is
  byte-identical to production at the production setting. That is the go-file's whole job.
- **The denial functional probe samples a scripted playout**, not the cell's own decks. It
  proves the term is live in the loaded build; it does not predict how often it fires in the
  cells (the prereg's E4 replay is the instrument for that question).
- **The two-box verification proves the laptop joined the cell**, not that it stayed. A laptop
  that drops out mid-block shows up only as a slow cell and, at the end, as a completion
  count — the 90% VOID rule is the backstop.
- **n=200 per cell is a screen.** Nothing here promotes anything, and a positive cell is a
  finding to top-up on a fresh band, never a production change.
