# Governance — the experiment-governance spine

This directory is the **machine-readable governance layer** for the project: it
turns scattered numbers, prose verdicts, and checkpoint folders into one
discoverable spine that separates *evidence* from *interpretation* from
*decisions*. New strength/mechanism claims and checkpoint provenance go **here**,
not into narrative docs.

It is the live layer. The frozen review-time snapshot of the same material lives
in [`../outside_review/`](../outside_review/README.md) (assembled at a fixed
commit, not maintained live).

## The 3-layer model

Every governance and experiment artifact states which layer it sits in. A claim
links DOWN to raw evidence; a decision links DOWN to claims.

1. **RAW (append-only evidence)** — numbers, never interpretations.
   - `experiments/results.csv` (the canonical raw ledger)
   - per-run `manifest.json` (resolved config / provenance per eval)
   - raw per-game JSON
   - `clean_eval/CLEAN_RESULTS.csv` (the clean-ruler subset)
2. **INTERPRETATION** — what the numbers mean, with an explicit status.
   - `governance/CLAIM_REGISTRY.csv` (claims + status + evidence links)
   - `governance/CHECKPOINT_LINEAGE.csv` (checkpoint provenance + lineage)
   - `governance/EVIDENCE_EPOCHS.md` (which raw eras are trustworthy)
3. **DECISIONS** — what we chose to do, justified by claims.
   - `PROJECT_CHARTER.md` (repo root — tracks, goals, success criteria, pivots)
   - `DECISIONS.md` (repo root — dated rationale)

**The invariant:** raw is append-only; interpretations may change but history
stays visible; generated summaries are not raw evidence. Generated summaries
(STATUS verdicts, `clean_eval/CLEAN_EVAL_AUDIT.md` prose) are NOT raw evidence
and say so — they are downstream readings that can be revised without rewriting
the ledger.

## Files in this spine

| File | Layer | What it holds |
|---|---|---|
| `governance/README.md` | (index) | this file — the spine index |
| `governance/CLAIM_REGISTRY.csv` | Interpretation | every strength/mechanism/measurement/infra/decision claim with a controlled status + evidence links |
| `governance/CLAIM_REGISTRY_SCHEMA.json` | Interpretation | column + enum schema for the registry |
| `governance/CHECKPOINT_LINEAGE.csv` | Interpretation | per-checkpoint provenance (sha256, parent, code commit, train config, associated clean evals, status) |
| `governance/CHECKPOINT_LINEAGE_SCHEMA.json` | Interpretation | column schema for the lineage registry |
| `governance/EVIDENCE_EPOCHS.md` | Interpretation | the 7 fixed evidence epochs (E0–E6) — which raw eras are trustworthy and what each invalidates |
| `governance/TRAINING_OBSERVABILITY_SPEC.md` | Interpretation | Phase-B telemetry spec: the checkpoint-provenance stamp (DONE) + prioritized have/cheap/needs-engineering metrics; gates the next training run |
| `governance/PROTOCOL_TEMPLATE.md` | (template) | blank pre-registration template for an experiment protocol |
| `governance/protocols/` | Interpretation | pre-registered experiment protocols (e.g. `PROTOCOL_001_residual_marginal_topup.md`) |
| `PROJECT_CHARTER.md` (repo root) | Decisions | the two tracks, goals, success criteria, pivot/abandonment conditions |

Raw-layer files (`experiments/results.csv`, per-run `manifest.json`,
`clean_eval/CLEAN_RESULTS.csv`) live outside this directory but are the evidence
the registry links to.

## The three overlapping experiment CSVs (reconciled)

There are three experiment tables in the repo. They are NOT duplicates — they sit
at different points in the spine. Use this map to pick the right one:

| CSV | Role | Maintain? |
|---|---|---|
| `experiments/results.csv` | **Canonical RAW spine** — append-only, authoritative numbers. Everything else cites it. | Yes — append only, never edit historical rows |
| `clean_eval/CLEAN_RESULTS.csv` | **Clean-ruler subset** — the runtime-verified clean reruns that feed the claim registry. | Yes — append clean reruns |
| `outside_review/EXPERIMENT_LEDGER.csv` | **Frozen review-time snapshot** — derived, enriched ledger captured for the external review bundle at a fixed commit. | No — do NOT maintain live; it is a point-in-time copy |

When two of these disagree, `experiments/results.csv` wins; the others are
derived views of it.

## Quickstart — how to add a claim / a checkpoint / a protocol

- **Add a claim:** append a row to `governance/CLAIM_REGISTRY.csv` (follow
  `CLAIM_REGISTRY_SCHEMA.json`; use the controlled status vocabulary; link
  `evidence_files_or_run_ids` to `experiments/results.csv` exp_ids and/or
  `clean_eval/` paths).
- **Add a checkpoint:** append a row to `governance/CHECKPOINT_LINEAGE.csv`
  (`sha256sum` the `.pt`, fill what's recoverable, write `unknown@train` for
  fields never persisted; set `status` ∈ {active, historical, superseded,
  quarantined}).
- **Add a protocol:** copy `governance/PROTOCOL_TEMPLATE.md` to
  `governance/protocols/PROTOCOL_NNN_<slug>.md`, pre-register it BEFORE running,
  and fill the RESULT section only at the target sample size.
