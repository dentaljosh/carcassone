# Level-2 saturated-ruler ladder — PROTOCOL (pre-registered 2026-06-18)

> **Measurement gate only (Joshua's standing guardrail).** No train / promote / redesign /
> modify-iter8 follows from this build. It executes §5 + §8.3 of
> [docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md](../../docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md).
> Level 1 (clairvoyance gap) is settled: gap **+26.6 elo** = minor contributor (CL-022,
> [CLAIRVOYANCE_GAP_VERDICT.md](CLAIRVOYANCE_GAP_VERDICT.md) — snapshot copy; repo original at
> [measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md](../../measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md)) ⇒
> the clairvoyant production agent is an acceptable Level-2 baseline; we **skip the K×
> non-clairvoyant search** on the ladder rungs.

## Why this experiment
The binding constraint on the superhuman goal is **measurement**, not modeling. Two
structural blockers (CLAUDE.md): (A) clairvoyance — now bounded small — and (B) **a
saturated ruler**. Our only out-of-lineage reference is HeuristicMCTS-v2.7 @ heur_sims=800
(R4). If nothing in the ecosystem genuinely exceeds R4, the elo scale **tops out at the
heuristic** and "superhuman" is literally unmeasurable. This ladder asks two questions and
nothing else:

1. **Is the strength scale monotone** from random up to the heuristic ruler? (sanity — the
   ladder must be a ruler, i.e. each rung beats the one below with non-overlapping CIs.)
2. **Does any rung above R4 exist?** — does deeper heuristic search (R5/R6) actually beat
   R4, giving the scale headroom *above* v2.7@800, or is the full-game ruler **saturated**?

This is the §8.3 gate: "If no rung exceeds v2.7 (saturation persists), the honest
conclusion is we have no supra-heuristic agent yet."

## FROZEN champion under test (do not modify)
From [governance/PRODUCTION.yaml](../../governance/PRODUCTION.yaml) (folded 2026-06-11):

| field | value |
|---|---|
| ckpt_id | `flywheel2_champion_iter8` |
| path (local / remote) | `…/flywheel_residual_attempt2/ckpt/iter8.pt` (`/mnt/c/carc-shared` ‖ `/mnt/carc-shared`) |
| **sha256** | `0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c` |
| arch | 96×6 ResNet, n_scalar_features=12, value_global_pool=False |
| agent | NeuralMCTS, sims=200, c_puct=3.0 |
| leaf | virtual_score_v2 ("v2.7") |
| env knobs | `CARCASSONNE_V25_RESIDUAL_SCALE=0.25 CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1 CARCASSONNE_V25_VALUE_BLEND=0 CARCASSONNE_USE_FLAT_LEAF=1` |

iter8 enters the ladder only at **Phase L2-2** (vs R4 / strongest validated higher rung).
L2-1 is a pure-CPU heuristic/rule ladder with no net.

## Rung definitions (FROZEN)
All heuristic rungs use the **production v2.7 leaf env** so they are byte-identical to the
established ruler: `CARCASSONNE_V25_CAP=12 CARCASSONNE_V25_DROP_THREE_OPEN=1
CARCASSONNE_USE_FLAT_LEAF=1` (no residual/blend — those are net-only knobs). Harness:
`scripts/ladder_rung_eval.py` (pure-CPU fork pool, paired, seat-balanced, shared-claim,
deck-hash, manifest). Rung spec strings are the harness `--rung-a/--rung-b` tokens.

| rung | spec token | agent | leaf | sims |
|---|---|---|---|---|
| **R0** | `random` | uniform random over legal actions (seeded) | — | — |
| **R1** | `greedy` | `RuleBasedPlayer` — 1-ply virtual_score argmax + endgame/no-early-farmer rules, **no tree search** | v1 (1-ply) | — |
| **R2** | `heur_v1@200` | `HeuristicMCTS(heur_leaf="v1")` | v1 base virtual_score | 200 |
| **R3** | `heur_v2_7@200` | `HeuristicMCTS(heur_leaf="v2_7")` | v2.7 | 200 |
| **R4** | `heur_v2_7@800` | `HeuristicMCTS(heur_leaf="v2_7")` — **the current ruler** | v2.7 | 800 |
| **R5** | `heur_v2_7@1600` (then `@3200` if R5 beats R4) | `HeuristicMCTS(heur_leaf="v2_7")` | v2.7 | 1600 / 3200 |
| **R6** | `portfolio` — **deferred, not implemented** | root-determinization ensemble / IS-MCTS over the heur leaf | v2.7 | — |

**R6 note:** a "portfolio / deep variant" rung (determinization ensemble, the Level-1
machinery applied to the heuristic) is *deferred*. It is built ONLY if R5 shows the ladder
has headroom above R4 (i.e. saturation is refuted) — there is no point engineering a higher
rung if deeper plain search already shows the full-game ruler is saturated. The existing
heur-depth probe (results.csv `heurdepth_*`, 2026-06-11) already found heur depth 200→800
buys ≈0 resolving power *for a fixed net opponent*; R4-vs-R5 is the **pure heur-vs-heur**
restatement of that question and is the load-bearing saturation test.

## Seed bands (FRESH, disjoint — pre-allocated)
Bands 1.2e9–2.7e9 are spent (results.csv). Level 2 uses 3.0e9+. Each L2-1 adjacent
comparison gets its own disjoint 10M-wide slot so they are independently re-runnable and
never share decks across the matrix:

| comparison | `--seed-start` | n (paired) |
|---|---|---|
| R1 vs R0 | `3_000_000_000` | 200 |
| R2 vs R1 | `3_010_000_000` | 200 |
| R3 vs R2 | `3_020_000_000` | 200 |
| R4 vs R3 | `3_030_000_000` | 200 |
| **R5 vs R4** (saturation gate) | `3_040_000_000` | 200 (top up to 400 if z∈[1.5,2.5]) |
| R6 vs R4/R5 (only if built) | `3_050_000_000` | 200 |
| **L2-2** iter8 vs R4 | `3_100_000_000` | 400 |
| L2-2 iter8 vs R5* (if R5 validated) | `3_110_000_000` | 400 |
| L2-3 endgame suite | `3_200_000_000` | (positions, not games) |

All paired (each deck played both seats), seed floor ≫ 1e9 self-play namespace, deck hash
recorded per game.

## Decision rules (pre-registered)
σ near wr=0.5: n=100 → 1σ≈±35 elo; n=200 paired → 1σ≈±17–24 elo; n=400 paired → ±12 elo
(CLAUDE.md results-discipline table). z = paired mean_d / se_d.

**V4 — monotonicity (ladder sanity).** The ladder is a valid ruler iff each rung beats the
one immediately below with a **positive elo and z ≥ 2** (≈non-overlapping CIs):
`R0 < R1 < R2 < R3 < R4`. A non-monotone step (z ≤ −2 anywhere, i.e. a lower rung *beats* a
higher one) is a **harness/leaf bug** — investigate before trusting any rung. A within-noise
tie (|z|<2) at an adjacent step is reported as "compressed here", not a failure, but flags a
rung pair the scale can't resolve.

**Saturation gate (the headline).**
- **R5 (and R6 if built) do NOT beat R4** — elo(R5 vs R4) ≤ 0 OR z < 2 (CI includes 0):
  declare the **full-game ruler SATURATED at R4 = heur@800-v2.7**. Do **not** spend large
  compute on deeper heuristic rungs pretending they are a higher ruler. Report the σ so the
  smallest gain we *could* have detected is on record (a null at n=200 means "no gain ≥ ~2σ
  ≈ ±34–48 elo", not "exactly equal").
- **R5 (or R6) BEATS R4** — elo > 0 with z ≥ 2 and non-overlapping CI: **promote** the
  strongest validated rung as the candidate higher ruler; carry it into L2-2.

**Power escalation (R5 vs R4 only).** If the R5-vs-R4 result lands z ∈ [1.5, 2.5]
(ambiguous), top up that one comparison to n=400 before declaring; do NOT top up the others.

## Phases
- **L2-0 (this doc):** freeze champion / config / rungs / bands / rules. ✅
- **L2-1:** the adjacent-rung sanity matrix (R1vR0 … R5vR4), n=200 paired each. Report
  W/D/L, elo, CI/z, manifests, deck hashes, **monotonicity verdict** + **saturation verdict**.
  **✅ DONE 2026-06-18** — saturation **REFUTED** (R5 heur@1600 > R4 heur@800, +55.2/z3.23
  @n400); depth drives the ruler, mid-rungs compressed. See `LEVEL2_LADDER_VERDICT.md`,
  CL-023. (Follow-on R5'@3200-vs-@1600 running.)
- **L2-2:** iter8 vs R4 (and vs strongest validated higher rung), fresh band, n=400 paired.
  Top up only if it changes interpretation. (iter8 vs R4 ≈ the published +58/+72 cell — this
  re-grounds iter8 on the *validated* ladder; V6 reproduce-check.)
- **L2-3:** small near-solved endgame suite (≤6–8 tiles left): compare move choice / regret
  for iter8, R4, and the strongest deep/portfolio rung against a deep-search reference move
  (flagged as an internal-consistency gauge, NOT ground truth — see spec §4 circular-labels).

## Validation tests (pre-registered, checked post-run)
- **V4** monotonicity (above).
- **V6 (reproduce):** L2-2 iter8-vs-R4 reproduces the known clean cell (iter8 vs heur@800
  sealed +58.7 / published +72.2 @ s200) within CI — proves the ladder harness agrees with
  the existing apparatus.
- **V7 (determinization sanity):** N/A here (no determinized rungs unless R6 is built).
- **Provenance smoke:** each heuristic rung asserts at runtime that the claimed leaf actually
  ran (`HeuristicMCTS.counters`: v2.7 rungs ⇒ `v2_7_calls>0 and v1_calls==0`, v1 rung the
  inverse) before the matrix launches.

## Deliverables (in `measurement/level2/`)
`LEVEL2_LADDER_PROTOCOL.md` (this) · `LADDER_RESULTS.json` (per-comparison W/D/L, elo, z,
deck-hash count, manifest path) · `LEVEL2_LADDER_VERDICT.md` (the 5-point final verdict) ·
raw per-game JSON + manifests under each comparison dir on the share · a `results.csv` row
per comparison · a CLAIM_REGISTRY entry for the saturation verdict.

## Final deliverable — the 5-point verdict
1. is the ladder **monotone** (V4)?
2. does a **stronger ruler than heur@800-v2.7** exist (saturation gate)?
3. where does **iter8** sit on the validated ruler (L2-2)?
4. does **measurement remain saturated** (the §8.3 honest conclusion)?
5. the **next recommended action**.
