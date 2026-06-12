# Track-B Flywheel — ATTEMPT #2 spec (FROZEN 2026-06-08)

Built per Joshua's recipe after attempt #1 ended **CL-011 = NULL** (the residual value head is
a confirmed *static* asset, +37.6 marginal, but did not **compound** via self-play co-adaptation).
Launcher: [`scripts/run_residual_flywheel_v2.sh`](../scripts/run_residual_flywheel_v2.sh).
**Status: COMPLETED 2026-06-10/11** — sealed verdict **champion iter8 +67.4 elo / z=2.73 SIGNIFICANT** vs incumbent iter0 (n=400 paired heur@800-v2.7, sealed band 1.7e9); folded to production 2026-06-11 (governance/PRODUCTION.yaml). Gain decomposed ~95% policy distillation, plateaued iter5 — see [PLATEAU_DECOMP_2026-06-10.md](PLATEAU_DECOMP_2026-06-10.md); follow-on lever = [DEEPER_TEACHER_SPEC_2026-06-11.md](DEEPER_TEACHER_SPEC_2026-06-11.md). *(Original status: LAUNCHED 2026-06-09 at ITERS=12 — Joshua bumped 3→12 after launch; the "fixed 3-iter" framing below was the original recipe.)*

## Why attempt #2 looks different — the attempt-#1 failure mode

The #1 lesson of attempt #1: the **in-lineage heur@200 gate is a DISCORDANT proxy.** iter1 was
**+30 in-lineage** but **−12 out-of-lineage** vs iter0; the +15 keep-margin therefore **crowned
iter1 (+40.1 out-of-lineage) and discarded the stronger iter3 (+66.8).** If the selection signal
itself lies, no amount of iterating fixes it. Attempt #2 changes *who decides*.

## Frozen choices (pre-flight, both settled by cheap measurement — no cluster spent)

| choice | value | evidence |
|---|---|---|
| **Leaf** | **v2.7** (`--heur-leaf v2_7`, `CAP=12`, `DROP_THREE_OPEN=1`) | Clean ruler (2026-06-07, n=400 paired): pure leaf gap v2.7-vs-v1 = **−24.4 ± 16.5 (1.5σ, inconclusive)**. v1 nominally stronger but unresolved; net beats both leaves at matched compute; v2.7 is the tuned ecosystem. v1-switch = a separate re-tune fork. |
| **Residual output** | **raw Δ + tanh head** (unchanged) | S-R3-1 (tanh saturation) is **empirically dead**: Δ across 2.6M positions has std 0.071, p99 0.27, **\|Δ\|>1 in 0.00%** of rows → saturation = 0.013% of the MSE budget. Clipping/linearizing changes nothing. |
| **Residual scale** | **0.25** | Confirmed **+37.6 elo marginal** (clean r4 scale0 +62.0 → r5 scale0.25 +99.6, n=1200, ~3σ). No sweep (Joshua). |

## The recipe (what attempt #2 USES)

- **the empirically selected leaf** → v2.7
- **the empirically selected residual-output formulation** → raw Δ + tanh head, scale 0.25
- **distinct self-play seeds each iteration** → `SEED_START = it·GAMES` (400 / 800 / 1200), all < 1e9
- **heur@800 external evaluation every iteration** → the selection odometer (out-of-lineage)
- **rotating selection decks + sealed confirmation** → per-iter band `SEL_SEED_BASE(1.2e9)+it·stride`; a held-out **sealed** band (1.7e9, n=400) evaluated only on the final champion
- **all checkpoints retained** → `$OUT/ckpt/iter*.pt` (best.pt is a copy)
- **external keep-best** → promote iff deck-paired Δelo(new − best) vs heur@800-v2.7 > `KEEP_MARGIN` (default 0)
- **fixed 3-iter run regardless of cheap-gate wobble** → no plateau-stop
- **the heur@200 gate = telemetry only** → logged each iter (to watch in-lineage-vs-external discordance), **no authority** to crown or terminate

## Per-iter loop (it = 1..3)

1. **gen** — 3-box residual self-play on the rotating band `SEED_START=it·GAMES` → `iter${it}_data` (400 games, shared-claim, self-heal).
2. **train** — residual head on the co-adapted data → `ckpt/iter${it}.pt` (warm from best).
3. **selection (external keep-best)** — band `1.2e9 + it·1000`. Run **both** `iter${it}.pt` and the current `best.pt` vs **heur@800-v2.7**, deck-paired → `odo_paired_tally.py` → Δelo(new−best), z. Promote if Δ > `KEEP_MARGIN`. → `selection.csv`.
4. **telemetry gate** — `iter${it}.pt` vs heur@200-v2.7 (in-lineage), logged only → `telemetry_gate.csv`.

After the loop — **sealed confirmation:** champion **and** iter0 vs heur@800-v2.7 on the held-out 1.7e9 band, n=400 paired → `SEALED_VERDICT.txt`. This is the attempt-#2 out-of-lineage verdict: Δelo(champion − iter0).

## Seed-band map (no overlaps; eval ≥ 1e9, self-play < 1e9)

| use | band | n (games) | decks consumed |
|---|---|---|---|
| self-play gen | `it·400` → 400/800/1200 | 400 | `[start, start+400)` |
| telemetry gate (heur@200) | `1.0e9` (fixed) | 300 | `[1e9, 1e9+150)` |
| selection (heur@800, rotating) | `1.2e9 + it·1000` | 200 | `[band, band+100)` |
| sealed confirm (heur@800, held out) | `1.7e9` | 400 | `[1.7e9, 1.7e9+200)` |

## Knobs (env-overridable)

`ITERS=12 START=1 SCALE=0.25 GAMES=400 SIMS=200 KEEP_MARGIN=0 TELEMETRY_GATE=1` (ITERS bumped 3→12 on 2026-06-09)
`N_GATE=300 ODO_N=200 CONFIRM_N=400 ODO_HEUR_SIMS=800 DURATION_HOURS=0`
`W_5800X=14 W_LAPTOP=20 W_XEON=10` · `FLYWHEEL_TAG=flywheel_residual_attempt2`

## Pass/fail (charter bar to flip CL-011)

≥3 non-regressing iters with **cumulative out-of-lineage ≥ +45 elo (+15/iter)** vs iter0. The sealed
Δelo(champion − iter0) is the headline; the per-iter `selection.csv` + `telemetry_gate.csv` show the
trajectory and whether the in-lineage/external discordance recurred.

## Launch (ONLY when told)

```bash
nohup nice -n 19 bash scripts/run_residual_flywheel_v2.sh > /tmp/flywheel2.log 2>&1 & disown
```
