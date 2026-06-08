# experiments/

`results.csv` is the **canonical RAW, append-only experiment ledger** — the
authoritative source of every elo/wr number in the project. Do not edit historical
rows; only append new ones (each eval script auto-appends, and every eval also
writes a self-describing per-run `manifest.json` that carries the resolved config
and provenance). Numbers live here; **interpretations do not** — claims, their
status, and what each number means live in
[`../governance/CLAIM_REGISTRY.csv`](../governance/CLAIM_REGISTRY.csv) (see
[`../governance/README.md`](../governance/README.md) for the full raw →
interpretation → decisions spine). `clean_eval/CLEAN_RESULTS.csv` is the
clean-ruler subset that feeds the registry; `outside_review/EXPERIMENT_LEDGER.csv`
is a frozen, derived review-time snapshot (not maintained live).
