# Evidence Index

Every source file in this packet (copied into [sources/](sources/)) plus the canonical repo paths
and large files referenced but not copied. **Data type** ∈ {governance, verdict doc, raw data,
processed result}. "Commit" = the relevant `code_rev` the artifact was produced at (where recorded).

Packet built at repo commit **`4021698022debd2e1e6b115d25a29575d4c44b19`** (`4021698`), branch
`stage-b-wiring`.

## Governance spine (machine-readable source of truth)
| packet path | canonical repo path | type | why it matters / claim supported | commit |
|---|---|---|---|---|
| [sources/PRODUCTION.yaml](sources/PRODUCTION.yaml) | `governance/PRODUCTION.yaml` | governance | Canonical champion pointer: iter8 path + sha + full play config. CL-005. | folded 2026-06-11 |
| [sources/CLAIM_REGISTRY.csv](sources/CLAIM_REGISTRY.csv) | `governance/CLAIM_REGISTRY.csv` | governance | All claims CL-001…CL-027 with status/evidence/falsifier. Spine of [CLAIMS_FOR_REVIEW.md](CLAIMS_FOR_REVIEW.md). | updated 2026-06-21 |
| [sources/CHECKPOINT_LINEAGE.csv](sources/CHECKPOINT_LINEAGE.csv) | `governance/CHECKPOINT_LINEAGE.csv` | governance | Checkpoint hashes + parentage: iter8 `0d355002`, residual `f1e67cab`, iter12 `059e394c`. Provenance backbone. | — |
| *(not copied — referenced)* | `experiments/results.csv` (90KB) | raw/processed | Source of truth for all elo/wr numbers. Relevant rows extracted below. | — |
| [sources/results_csv_relevant_rows.csv](sources/results_csv_relevant_rows.csv) | (filtered subset) | processed | The 28 `results.csv` rows cited in this packet (header + rows). | — |
| *(not copied — referenced)* | `DECISIONS.md` (386KB) | governance | Dated decision log; grep by date/keyword. Refines/overrides the prompt. | — |
| *(not copied — referenced)* | `STATUS.md` → [sources/STATUS.md](sources/STATUS.md) | governance | Live state at packet time (K=4 COMPLETE; champion unchanged; branch). | — |

## Verdict docs (interpreted conclusions)
| packet path | canonical repo path | type | claim / result supported | commit |
|---|---|---|---|---|
| [sources/LEVEL2_LADDER_VERDICT.md](sources/LEVEL2_LADDER_VERDICT.md) | `measurement/level2/LEVEL2_LADDER_VERDICT.md` | verdict | Heuristic ladder NOT saturated; depth scales it (CL-023). | `6b5b43f` |
| [sources/LEVEL2_L22_VERDICT.md](sources/LEVEL2_L22_VERDICT.md) | `measurement/level2/LEVEL2_L22_VERDICT.md` | verdict | iter8 vs heur@800/1600/3200; edge erased by @3200; transitivity (CL-024). | `efb182c` |
| [sources/LEVEL2_L23_VERDICT.md](sources/LEVEL2_L23_VERDICT.md) | `measurement/level2/LEVEL2_L23_VERDICT.md` | verdict | K=2 (+ partial K=3) endgame regret; iter8 worst (CL-025). | `5406c74` |
| [sources/LEVEL2_K4_PROBE_VERDICT.md](sources/LEVEL2_K4_PROBE_VERDICT.md) | `measurement/level2/LEVEL2_K4_PROBE_VERDICT.md` | verdict | K=4 endgame; iter8 worst; H1 rejected / H2,H3 supported (CL-027). | suite `038f7ec`; key `6f9dd08` |
| [sources/LEVEL2_HYBRID_VERDICT.md](sources/LEVEL2_HYBRID_VERDICT.md) | `measurement/level2/LEVEL2_HYBRID_VERDICT.md` | verdict | Hybrid patchable vs iter8, gap-closing vs heur@3200 (CL-026). | `d654082` |
| [sources/CLAIRVOYANCE_GAP_VERDICT.md](sources/CLAIRVOYANCE_GAP_VERDICT.md) | `measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md` | verdict | Clairvoyance gap +26.6/z−0.9, small (CL-022). | `f7ebec3` + `ad9ad03` |
| [sources/VALUE_RANKING_VERDICT.md](sources/VALUE_RANKING_VERDICT.md) | `value_ranking/VALUE_RANKING_VERDICT.md` | verdict | Learned value/ranking + attention disfavored (CL-021). | 2026-06-18 |
| [sources/DEEPTEACHER_PROVENANCE_AUDIT.md](sources/DEEPTEACHER_PROVENANCE_AUDIT.md) | `deepteacher_audit/DEEPTEACHER_PROVENANCE_AUDIT.md` | verdict | Baseline-provenance defect: deltas vs residual.pt not iter8 (CL-020). | — |
| [sources/ITER8_VS_ITER12_VERDICT.md](sources/ITER8_VS_ITER12_VERDICT.md) | `deepteacher_audit/ITER8_VS_ITER12_VERDICT.md` | verdict | Clean iter12 vs iter8 = TIE both planes (CL-019). | `14739a6` |
| [sources/MEASUREMENT_FIRST_SPEC_2026-06-18.md](sources/MEASUREMENT_FIRST_SPEC_2026-06-18.md) | `docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md` | governance/spec | The current program: why measurement is the binding constraint; the 3 levels + decision gates. | 2026-06-18 |

## Protocols & pre-registration (how each result was scoped before running)
| packet path | canonical repo path | type | claim / result it pre-registers | commit |
|---|---|---|---|---|
| [sources/LEVEL2_LADDER_PROTOCOL.md](sources/LEVEL2_LADDER_PROTOCOL.md) | `measurement/level2/LEVEL2_LADDER_PROTOCOL.md` | protocol | Ladder rungs, bands, pre-registered power-escalation (CL-023). | `6b5b43f` |
| [sources/LEVEL2_L23_PROTOCOL.md](sources/LEVEL2_L23_PROTOCOL.md) | `measurement/level2/LEVEL2_L23_PROTOCOL.md` | protocol | K=2/K=3 endgame-regret protocol + solver validation (CL-025). | `5406c74` |
| [sources/CLAIRVOYANCE_GAP_PROTOCOL.md](sources/CLAIRVOYANCE_GAP_PROTOCOL.md) | `measurement/clairvoyance/CLAIRVOYANCE_GAP_PROTOCOL.md` | protocol | Clairvoyance estimand, arms, ±24 threshold, V1–V3 (CL-022). | `f7ebec3` |
| [sources/ITER8_VS_ITER12_PROTOCOL.md](sources/ITER8_VS_ITER12_PROTOCOL.md) | `deepteacher_audit/ITER8_VS_ITER12_PROTOCOL.md` | protocol | Pre-registered STRONGER/TIE/top-up thresholds for iter12 vs iter8 (CL-019). | `14739a6` |
| [sources/DEEPTEACHER_LINEAGE.csv](sources/DEEPTEACHER_LINEAGE.csv) | `deepteacher_audit/DEEPTEACHER_LINEAGE.csv` | governance | Per-iter parent-hash chain proving iter8-rooted warm-start (CL-020). | — |

## Raw & processed result data
| packet path | canonical repo path | type | what it holds | commit |
|---|---|---|---|---|
| [sources/K4_PROBE_RESULTS.json](sources/K4_PROBE_RESULTS.json) | `measurement/level2/K4_PROBE_RESULTS.json` | processed | K=4 aggregated: overall/decision/by-source/sharpness/difficulty, selection-bias, solve-cost. | `038f7ec` |
| [sources/L23_REGRET_RESULTS.json](sources/L23_REGRET_RESULTS.json) | `measurement/level2/L23_REGRET_RESULTS.json` | processed | K=2 (+partial K=3) per-agent top-1 / regret / blunder rates. | `5406c74` |
| [sources/LADDER_RESULTS.json](sources/LADDER_RESULTS.json) | `measurement/level2/LADDER_RESULTS.json` | processed | Ladder rung W/D/L/elo/z (machine form of CL-023). | `6b5b43f` |
| [sources/GAP_RESULTS.json](sources/GAP_RESULTS.json) | `measurement/clairvoyance/GAP_RESULTS.json` | processed | Clairvoyance clair/nonclair arms + paired gap. | `f7ebec3` |
| [sources/VALUE_RANKING_RESULTS.csv](sources/VALUE_RANKING_RESULTS.csv) | `value_ranking/VALUE_RANKING_RESULTS.csv` | processed | Per-arm held-out Kendall-τ / top1 / high-spread τ. | 2026-06-18 |
| [sources/ITER8_VS_ITER12_RESULTS.csv](sources/ITER8_VS_ITER12_RESULTS.csv) | `deepteacher_audit/ITER8_VS_ITER12_RESULTS.csv` | processed | Four-cell iter8/iter12 × s200/s800 elo. | `14739a6` |

## Large source data NOT copied (referenced by path)
| repo path | type | why not copied |
|---|---|---|
| `measurement/level2/l23_positions.jsonl` (5.2 MB) | raw data | K=2/K=3 endgame suite positions (full provenance). Too large; cited by row. |
| `measurement/level2/l23_k4_multisource.jsonl` (744 KB) | raw data | K=4 multi-source suite positions. |
| `/mnt/c/carc-shared/level2_*/` (per-game JSON + `manifest.json`) | raw data | Per-game eval records + resolved-config manifests for every `l22_*` / `l2hyb_*` / `l2_ladder_*` / clairvoyance row. Off-repo (CIFS share). |
| `/mnt/c/carc-shared/l23_k4_expand_probe/` | raw data | K=4 solver caches + per-position results. Off-repo. |
| `/mnt/c/carc-shared/iter8_vs_iter12/{i8,i12}_s{200,800}` | raw data | iter8-vs-iter12 per-game JSON + manifests (checkpoint sha verified at runtime). |
| `clean_eval/CLEAN_EVAL_AUDIT.md` | verdict | The trustworthy-ruler audit (2026-06-07); R1/R7 provenance guards (CL-013/014/015). |

## Manifests / provenance (deck bands & checkpoint hashes)
- **Checkpoint hashes** are in [sources/CHECKPOINT_LINEAGE.csv](sources/CHECKPOINT_LINEAGE.csv) and
  echoed in each eval's off-repo `manifest.json` (`evaluator.sides[].checkpoint_sha256`). iter8
  `0d355002…`, iter12 `059e394c…`, residual.pt `f1e67cab…`.
- **Deck bands** are recorded per row in `results.csv` (`src_dir` + note) and in each off-repo
  `manifest.json`. Same-band sets used for composition: 3.10e9 (the iter8-vs-heur ladder), b340
  (hybrid), 2.5e9 (iter8-vs-iter12), 2.7e9 (clairvoyance), 3.2e9 (K=2/3 endgame), `038f7ec` suite (K=4).
- Eval provenance is runtime-verified (R1/R7 guards, CL-013): `src/carcassonne_ai/eval_provenance.py`,
  `tests/test_eval_provenance.py` (22 tests).

## Prior packet (superseded — not part of this review)
- `outside_review/` + `outside_review.zip` (dated **2026-06-07**) — a prior external-review packet that
  **predates all Level-2 / clairvoyance / endgame / deepteacher-clean work**. Its strength framing
  (e.g. pre-CL-024 "global-best" language) is stale. Listed for traceability only; intentionally
  excluded from this packet (see [PACKET_MANIFEST.json](PACKET_MANIFEST.json) `omitted`).
