# G3 VERDICT — `S1-BOUNDED-NULL` (2026-08-31, adjudicated ~00:35 EDT, amended read G3-A1)

**Branch per [READ_RULE_G3.md](READ_RULE_G3.md), read on `AMENDED_VERDICT_G3.json`:**

| arm | scope | M (pts/deck, paired) | se | z | n decks |
|---|---|---:|---:|---:|---:|
| CELL_G3_OPP | opp | **+0.763** | 0.548 | +1.39 | 600 |
| CELL_G3_OWN | own | −0.278 | 0.538 | −0.52 | 600 |
| CELL_G3_ALL | all (control) | +0.219 | 0.642 | +0.34 | 400 |

**P1** (OPP vs champion): +0.763 ± 0.548, z +1.39 — does not clear. **P2** (OPP−OWN per deck,
CRN, ρ 0.164): **+1.042 ± 0.702, z +1.48** — does not clear. Consequence (frozen): record the
bound and close the branch; |z|<2 is never "refuted" — the bound is what's quoted: at the
realized SE, OPP's UB95 ≈ **+1.86 pts/deck**; the decomposition's UB95 ≈ +2.45. Re-opening
needs a MECHANISM argument, not more n. The G1-measured 5.01% expression does not convert to
game points at this resolution. Directional note (descriptive only): opp positive / own
negative / all between — consistent with the design's expectation of where any value would
sit, at sub-2σ everywhere.

**Guards:** every per-cell gate PASS on all three arms — including **G-WITNESS** (play-derived
`jr_expansions`: candidate boosted > 0, opponent all-zeros, on every arm) — and every round
gate PASS on the amended read.

**G3-A1 amendment (execution-layer, statistics-blind — the branch was set before any
statistic was displayed):** the frozen G-REV voided on manifests' `-dirty` code_revs. Ground
truth: `run_manifest.code_rev()` marks dirty on ANY `git status --porcelain` output —
including UNTRACKED files (laptop: untracked-only artifact files, 0 tracked modifications)
and non-code measurement/ churn (local: watchdog-touched logs + the owner-ordered W14→30
conf change, DEVIATIONS G3-D2). The launcher's own `assert_rev` — which checks exactly the
code paths against the pin — recorded `clean: true` at `ec0e52bb` before AND after every
cell on both boxes (`SRC_CLEAN_G3.jsonl`). One rev, code clean, pins match. The frozen
verdict (`S1-VOID-INSTRUMENT`, FROZEN_VERDICT_G3.json) is retained; the amended read used
`--allow-dirty-rev` with the full justification recorded in the gate detail. CHORE FILED:
`code_rev()` should distinguish untracked/non-code dirt from source dirt.

**Program consequence:** with CL-083 (per-move), the five plan-level mechanisms (all killed
or generic), and now S1 (bounded), the steering program's cluster-side instrument space is
exhausted. Remaining live instruments: **E-5** (owner vs Carcasum at matched conditions —
the adaptation/steering discriminator) and **E4 volume**. CL-086 is the claim these feed.
