# Deeper-Teacher Experiment — build spec (2026-06-11)

**Status (updated 2026-06-12):** LAUNCHED & RUNNING — this is the live experiment. iter1 NULL
(−2.0/z−0.07); **iter2 CONFIRMED +53.7 elo / z=2.14 over iter8** (n=400 paired, fresh band 1.3e9 —
results.csv `confirm_iter2_vs_heur800_v27_s800_n400`); flywheel RESUMED `START=3` (iters 3→6,
warm-from iter2) to test compounding — **iter3 REJECTED (−81.0/z=−2.36 vs best=iter2)**, iter4
selection in flight. Note: the Phase-0 "null → STOP" gate below was deliberately NOT applied —
iter1 was null but the run continued and iter2 vindicated that. See STATUS.md for live state.
<br>*(original status: DESIGNED, not launched — needs Joshua's go + machine choice + Phase-0 ETA.)*

## Goal

Attack the **policy plateau**. The 2026-06-10 decomposition showed the sims=200 residual
flywheel's gain is **~95% policy distillation** that **plateaus at iter5** (policy-only:
iter0 +10.4 → iter5 +52.5 → iter8 +54.3 vs heur@800; +1.8 after iter5). The residual value
head is static (+22) and locally inert. So the only live ceiling lever on this architecture
is **a stronger gen-time teacher** that distills better policy targets. Single lever:
**gen `SIMS` 200 → 800.**

## Read first — the deepsearch precedent (2026-05-20)

A sims=800 teacher was already tried once, single-shot, from iter_01 (River-era):
- **+35.8 elo / 2.0σ at sims=800 eval** (n=380) — `results.csv: deepsearch_eval_s800`
- **+5.2 elo / NULL at sims=200 eval** (n=400) — `results.csv: deepsearch_v2_n400`

Lesson (DECISIONS 2026-05-19): *"Stronger search refines the policy toward what THIS leaf
considers best; it cannot teach the policy moves the evaluator can't recognize as good."*
The sims=800 gains are **plane-local** — they live at the deep plane and do **not** transfer
down to sims=200.

## Why this is NOT just a deepsearch rerun

1. **deepsearch was single-shot** (one teacher → one retrain). The open question is whether
   **iterating** a deep teacher **compounds to a higher plateau** than the sims=200 flywheel's
   +54. Untested. This is the actual experiment.
2. **We accept the off-plane reality and commit to the deep plane.** Production play would run
   at sims=800. For the project goal (beat strong/expert humans), inference time is ~unconstrained
   — humans are slow — so playing at sims=800 is acceptable. deepsearch's "off-plane null"
   reframes from *failure* to *"just run the whole system at the deeper plane."*
3. **Better starting point.** iter8 (current production champion, clean base-only game) is
   stronger and cleaner than iter_01 (River-era + buggy game) that deepsearch used.

## ⚠️ Ceiling caveat (be honest about what this can and cannot do)

Deeper search is **still scored by the v2.7 leaf.** This lever **raises the plateau toward
"v2.7's best play at depth"** — it does **NOT** break the v2.7-leaf ceiling, which is *the*
foundational blocker to genuinely-superhuman play (`docs/research/foundational_audit_2026-06-02.md`).
Expect this to **approach** the heuristic ceiling faster/higher, not **exceed** it. The
ceiling-break is a different, harder lever — letting the **learned value drive the leaf**
(value-as-leaf), which has historically *cliffed*. Deeper-teacher is the cheap, positive-precedent
policy lever to exhaust first; it is not the superhuman lever.

## Design — single lever, hold everything else

Built on `scripts/run_residual_flywheel_v2.sh` (the attempt#2 launcher; already parameterized).

| Knob | attempt#2 (sims=200) | deeper-teacher | hold? |
|---|---|---|---|
| `SIMS` (gen) | 200 | **800** | **← the lever** |
| `ITER0_CKPT` (warm-from) | residual.pt | **iter8** (new champion) | changed (start from current best) |
| `GAMES`/iter | 400 | 400 | hold |
| `SCALE` (residual) | 0.25 | 0.25 | hold |
| leaf | flat v2.7, CAP=12, DROP_THREE_OPEN=1 | same | hold |
| `VLW` | 1.0 | 1.0 | hold |
| keep-best | external heur@800-v2.7 paired, rotating | same | hold |
| eval plane | 200 | **800** (the gen plane) | matched to gen |

**Eval discipline (the deepsearch correction):** the *verdict* eval runs **at the gen plane
(sims=800)** vs out-of-lineage **heur@800-v2.7**, deck-paired, **n≥400**. ALSO run a sims=200
transfer eval — not as the verdict, but to **characterize** plane-locality (expected null;
documents the trade we're accepting).

## Phases (cheapest-informative-first)

- **Phase 0 — one deep iter + cost bench (cheap).** `ITER0_CKPT=iter8`, gen 400 games at
  `SIMS=800`, retrain, eval at sims=800 vs **iter8@800** (paired, n=200 screen). Dual purpose:
  (a) **replicate** the single-shot deep-teacher gain on the *current* champion + clean game;
  (b) **measure** the real sims=800 gen wall-clock (do NOT extrapolate — sims=800 gen is the
  cost unknown). **Gate:** single-shot ≥ ~+20 elo @800 → Phase 1; null → **STOP** (deeper
  teacher doesn't even help single-shot on iter8 → the leaf is the binding constraint, go to
  the ceiling-break lever instead).
- **Phase 1 — deep flywheel (only if Phase 0 gains).** `SIMS=800 ITERS=3..5`, external
  heur@800 keep-best, distinct decks/iter, sealed held-out confirmation. **Question:** does the
  deep-teacher plateau **exceed the sims=200 flywheel's +54**?
- **Phase 2 — verdict.** Champion vs iter8, both at sims=800, SEALED held-out **n=400** paired.
  Plus the sims=200 transfer eval for the record.

## Cost / ETA — MUST bench, do not extrapolate

- sims=800 gen ≈ **4× per-move MCTS cost** vs sims=200. Phase 0's single iter **is** the bench
  → get the real per-iter wall before committing to Phase 1's 3–5 iters.
- ⚠️ The 2026-06-11 heur-depth finding (heur depth 200→800 ~flat) was measured at **net@200**
  and does **not** transfer to net@800 — re-check the gate/eval cost at the deep plane.
- 3-box cluster (5800x W14, laptop W20, xeon W10), `nice -n 19`, detached (held-ssh for xeon).
  **State ETA + ask which box(es) before launch** (per standing rules).

## Launch (pending go + machine choice — NOT yet run)

```bash
# Phase 0 — one deep iter from iter8, bench the cost:
SIMS=800 ITERS=1 START=1 \
  ITER0_CKPT=/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
  FLYWHEEL_TAG=deepteacher_phase0 \
  nohup nice -n 19 bash scripts/run_residual_flywheel_v2.sh > /tmp/deepteacher_p0.log 2>&1 & disown
```
(Verify the launcher's eval plane is set to 800 for the verdict before Phase 1 — attempt#2
selection used heur@800 already, but `--sims` on the net side of the gate must be 800 too.)

## Alternatives considered (sidebar — if sims=800 cost is prohibitive)

- **Cheaper "deeper teacher" without 4× sims:** higher gen `c_puct` (self-play c_puct A/B was
  never done — only eval-side c=3.0 is confirmed), higher gen **residual scale** (search targets
  reflect the net's learned value more, not pure v2.7 — could teach something the leaf alone
  can't), more Dirichlet. Lower-cost, untested. Screen these first if 800 is too expensive.
- **Opening/deck diversity** — orthogonal to depth; broadens policy coverage. Deferred.
- **The ceiling-break (value-as-leaf)** — the eventual necessity for superhuman; out of scope
  here (historically cliffed; needs its own design).
