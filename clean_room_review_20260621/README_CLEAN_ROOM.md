# Clean-Room Review Packet — Carcassonne AI (2026-06-21)

> **One-page orientation.** This packet is a self-contained snapshot for a fresh external
> reviewer. It is *packaging only* — no new experiments were run, no models trained, no
> scientific claims altered. Every number below cites a file under [sources/](sources/) and/or
> a named row in `experiments/results.csv` (relevant subset:
> [sources/results_csv_relevant_rows.csv](sources/results_csv_relevant_rows.csv)).

## Project goal
Build an AlphaZero-style Carcassonne AI that plays **genuinely superhuman** 2-player
**Base + Farmers** (no River, no expansions). The superhuman target became primary on
2026-05-28, overriding the original prompt (which scoped superhuman *out* and named an
analyzer as the win condition). Two structural blockers gate the goal:
1. **Measurement** — no strong, non-saturated, non-clairvoyant, human-anchored reference exists yet.
2. **The hand-crafted v2.7 leaf evaluation caps learned strength** — superhuman requires the
   *learned* components to exceed the heuristic, which they do not yet.

## Current champion (exact)
| field | value |
|---|---|
| ckpt id | `flywheel2_champion_iter8` |
| path | `flywheel_residual_attempt2/ckpt/iter8.pt` (on the CIFS share) |
| **sha256** | `0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c` |
| arch | 96×6 ResNet, `n_scalar_features=12`, `value_global_pool=False` |
| play config | NeuralMCTS, sims=200, c_puct=3.0, leaf=`virtual_score_v2` ("v2.7"), `RESIDUAL_SCALE=0.25`, `CAP=12`, `DROP_THREE_OPEN=1`, `FLAT_LEAF=1` |
| folded in | 2026-06-11 |

Canonical pointer: [sources/PRODUCTION.yaml](sources/PRODUCTION.yaml). Lineage:
[sources/CHECKPOINT_LINEAGE.csv](sources/CHECKPOINT_LINEAGE.csv).

## Current strongest known *practical* agent / ruler
**`heur@3200`** — plain `HeuristicMCTS` with the v2.7 leaf, search depth 3200 sims, c_puct=1.5.
It (a) **catches the champion full-game** (iter8 vs heur@3200 = −28.7 elo, same-band n=400, paired
z=−0.70 = tie-to-slight-loss; `l22_iter8_vs_heur3200_b310_n400`) and (b) is the **most
endgame-precise** agent on the exact-solver suites. It is the *strongest practical reference we
have*, **not** ground truth and **not** "optimal/superhuman" — deeper heuristic search keeps
climbing (the ladder is not saturated even at @1600), so heur@3200 is just the deepest rung we ran.

## Current major conclusion
The champion (iter8) represents a **real but bounded** strength gain (+67.4 elo / z=2.73 over the
incumbent on a sealed out-of-lineage ruler), but the gain is **~95% policy distillation, bounded by
the v2.7 leaf** — it is **not** a break of the heuristic ceiling and is **not** superhuman. Both
strength levers we tried after it are exhausted:
- **Deeper policy teacher (deepteacher / iter12):** clean powered-null — ties iter8 at both s200
  and s800 (+14.6/z0.65 and +12.4/z0.51).
- **Learned value / action-ranking head:** disfavored — every tested formulation ranks sibling
  moves at ~chance (τ≈0.03) vs the v2.7 leaf (τ=0.58).

iter8's full-game edge over heuristic search **shrinks monotonically with heuristic depth and is
erased by heur@3200** (+40.1 @800 → +24.4 @1600 → −28.7 @3200, same band). Solver-grounded endgame
probes (K=2/3/4) consistently show iter8 is the **least endgame-precise** of all agents. The binding
constraint on any superhuman claim is now **measurement**, not modeling.

## Why this review is requested now
The team is about to open a **tool-augmented / action-ranker branch** (give the agent richer
move/endgame features or a learned action-ranker). Before spending engineering effort on features,
a clean-room reviewer should confirm: (a) what the evidence actually establishes, (b) that no claim
is overstated, and (c) that the proposed branch is the right next bet rather than a goalpost-move or
a re-run of an already-failed lever.

## What the reviewer is asked to decide
1. Are the established facts correctly separated from interpretation and speculation?
2. Are any claims overconfident or unsupported (see [OVERCLAIM_RISKS.md](OVERCLAIM_RISKS.md))?
3. Is **heur@3200** correctly framed as *strongest known practical ruler*, not ground truth?
4. Is **iter8** correctly framed as a learned *search-efficiency / policy* agent whose edge erases
   against deeper heuristic search?
5. Is the **K=4 endgame** result correctly read as *distributional specialization / OOD weakness*,
   not "iter8 is bad at endgames"?
6. Is the **hybrid handoff** correctly read as a *modest patch*, not a new champion?
7. Is the proposed **pre-tool audit** the right step before any feature/tool coding — and what single
   measurement would most reduce uncertainty?

The full reviewer brief is in [REVIEWER_PROMPT.md](REVIEWER_PROMPT.md).

## How to read this packet
| file | purpose |
|---|---|
| [CURRENT_STATE_SUMMARY.md](CURRENT_STATE_SUMMARY.md) | complete scientific state; facts vs interpretation vs speculation |
| [CLAIMS_FOR_REVIEW.md](CLAIMS_FOR_REVIEW.md) | claim-by-claim table (id, status, evidence, caveat, falsifier) |
| [RESULTS_DIGEST.md](RESULTS_DIGEST.md) | numeric tables with exact source citations |
| [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md) | every source file: path, role, claim supported, data type |
| [OPEN_QUESTIONS_AND_NEXT_OPTIONS.md](OPEN_QUESTIONS_AND_NEXT_OPTIONS.md) | live questions + candidate branches |
| [OVERCLAIM_RISKS.md](OVERCLAIM_RISKS.md) | the dangerous overclaims to watch for |
| [REVIEWER_PROMPT.md](REVIEWER_PROMPT.md) | standalone brief for the clean-room reviewer |
| [PACKET_MANIFEST.json](PACKET_MANIFEST.json) | machine-readable manifest (hashes, rows, omissions) |

**Repo state at packet creation:** branch `stage-b-wiring`, commit
`4021698022debd2e1e6b115d25a29575d4c44b19` (`4021698`). A prior, now-superseded review packet
(`outside_review/`, dated 2026-06-07) predates all Level-2 / clairvoyance / endgame work and is
**not** part of this packet.
