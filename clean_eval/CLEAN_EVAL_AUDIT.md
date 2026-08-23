# CLEAN_EVAL_AUDIT — old headline claims re-judged on the repaired ruler

> **⚠️ SCOPE SPLIT (D1, 2026-08-23, TRACK_D_PREP_2026-08-23 §3.2):** the
> instrument claims (CL-013/014/015 — provenance, seed namespace, semantic
> contracts) stand Confirmed and era-independent. The strength ABSOLUTES
> (CL-001/CL-012 rows) are denominated against a clairvoyant, non-top,
> matched-v2.7 opponent: NOT blanket-discountable (the leaf effect is
> non-transitive — this file's own finding) but NOT comparable to fair-ladder
> numbers, and their checkpoints are retired lineage. No re-run — it would
> price retired checkpoints.

> **⚠️ UPDATE 2026-06-08 — the n=1200 top-up (PROTOCOL_001) resolved the two open items, and one REVERSES a Phase-3 read:**
> 1. **Residual value-head marginal RESOLVED POSITIVE:** +37.6 elo / z=2.98 at n=1200 (was +26/z=1.30 "inconclusive" at n=400 — underpowered, not wrong). The old "+45 robust" largely survives clean. **CL-004 → Supported.**
> 2. **Non-transitivity OVERTURNED:** clean net-vs-v1 cells give iter_11 +35.7 / Stage-B +24.4 (old Stage-B-vs-v1 +86.9 was a 62-elo contamination inflation). Clean Δ(v2.7−v1) is **same-sign for both nets** (iter_11 +54, Stage-B +10) — NOT sign-varying. The "leaf effect is non-transitive" reframe was a contamination artifact → **CL-016 Disfavored; CL-012 strengthened.** What stands: no single universal discount (magnitudes differ per net), and old unmatched-leaf absolutes are not comparable to clean ones.
>
> Body below is the original Phase-3 (n=400) read, with the two superseded spots marked inline. Numbers: `CLEAN_RESULTS.csv` (7 rows), `governance/CLAIM_REGISTRY.csv`, `governance/protocols/PROTOCOL_001_*` (RESULT).

This audit re-evaluates the project's headline strength claims on the
**provenance-verified** evaluation ruler built in Phases 1–2 (runtime-asserted
leaf identity, clean 1e9 seed namespace + deck hashes, full both-sides manifests,
deterministic semantic contracts). **No training was done.** Phase-3 reruns are
evaluation only.

Each old claim is classified as one of:

| Class | Meaning |
|---|---|
| **survives** | clean number agrees within ~1σ; the claim stands |
| **directionally survives (magnitude changes)** | sign/direction holds but the magnitude moves materially (e.g. the leaf-gap discount) |
| **inconclusive** | the clean n cannot resolve the effect; report σ + required top-up, do not call it |
| **invalidated** | the clean number contradicts the claim (sign flip or effect vanishes) |
| **not reproducible** | the cell could not be re-run cleanly (missing ckpt/config) |

The two structural defects the ruler now blocks:
- **R1** — the strength yardstick (`HeuristicMCTS`) ran the **v1** leaf while the
  agent ran **v2.7**; every vs-yardstick *absolute* was inflated by the v1→v2.7
  leaf gap. Now the opponent leaf is recorded + runtime-asserted (`--heur-leaf`).
- **R7** — a residual eval (`residual_scale>0`) could silently fall back to pure
  v2.7 with `v_nn=0`. Now `assert_provenance_consistent` fails unless the residual
  path actually fired.

---

## Clean reruns (source of the new numbers)

All cells: **n=400 deck-paired, balanced seats, `--seed-start 1e9` (clean namespace),
sims=200, matched v2.7 opponent (`CAP=12 DROP_THREE_OPEN=1`), runtime-verified
provenance**. Raw per-game JSON + full manifests under
`/mnt/c/carc-shared/clean_eval_runs/<rerun>/`; aggregated in `CLEAN_RESULTS.csv`.

| # | Rerun | What it isolates |
|---|---|---|
| 1 | HeuristicMCTS-v2.7 vs HeuristicMCTS-v1 | the PURE leaf gap (no net) |
| 2 | iter_11 vs matched v2.7 | iter_11 policy at a matched leaf |
| 3 | Stage-B iter_01 vs matched v2.7 | clean rerun of the +48.1 cell |
| 4 | residual net scale 0 vs 0.25 | the value-head MARGINAL |
| 5 | residual net scale 0.25 vs v2.7 | residual ABSOLUTE (shares #4's cell) |

### Clean numbers (from `CLEAN_RESULTS.csv`, all at commit `1973fc1`, dirty=False, provenance recorded)

| # | Cell (A vs B) | n (decks) | W/L/D | wr | **elo ± σ** | z | avg_diff | verdict at n=400 |
|---|---|---|---|---|---|---|---|---|
| 1 | heur-**v2.7** vs heur-**v1** (pure leaf) | 400 (200) | 181/209/10 | 0.465 | **−24.4 ± 16.5** | 1.5 | −1.9 | inconclusive (leans v2.7-WEAKER) |
| 2 | **iter_11** vs matched v2.7 | 400 (200) | 248/147/5 | 0.626 | **+89.7 ± 17.2** | 5.2 | +5.0 | **resolved (strong)** |
| 3 | **Stage-B iter_01** vs matched v2.7 | 400 (200) | 216/176/8 | 0.550 | **+34.9 ± 17.8** | 2.0 | +2.2 | resolved (marginal, ~2σ) |
| 4a | **residual** scale-0 vs v2.7 | 400 (200) | 231/167/2 | 0.580 | **+56.1 ± 16.6** | 3.4 | +3.5 | **resolved** |
| 5 | **residual** scale-0.25 vs v2.7 | 400 (200) | 242/148/10 | 0.618 | **+83.2 ± 16.9** | 4.9 | +5.3 | **resolved** |

**Residual value-head MARGINAL** (scale-0.25 − scale-0, deck-paired):
- **[n=400 screen]** Δwr = +0.0375 (SE 0.0289, z = 1.30) → inconclusive.
- **✅ [n=1200 top-up — PROTOCOL_001, 2026-06-08]** Δwr = **+0.0512 (SE 0.0172, z = 2.98) ≈ +37.6 elo → RESOLVED:** the value head adds real strength (**CL-004 → Supported**). The n=400 read below was UNDERPOWERED, not wrong; the old "+45 robust" largely survives clean. (Production fold-in still gated — CL-005 — on a head-to-head + clean out-of-lineage check.)

> ⚠ **Two contradictions resolved before declaring** (per results-discipline):
> 1. The **pure leaf gap is NEGATIVE** (v2.7 −24.4 vs v1), not the **+39 inflation** implied by R1's
>    `+86.9 (v1 opp) → +48.1 (v2.7 opp)`. These measure different things: −24.4 is **leaf-vs-leaf
>    pure search**; the +38.8 was an **agent-vs-opponent margin shift**, which folds in policy
>    interaction. They are reconciled by **non-transitivity** (next point), not by a fixed leaf discount.
> 2. ⚠️ **[SUPERSEDED 2026-06-08 — non-transitivity OVERTURNED; the caveat below was right.]** This box
>    originally read non-transitivity from `iter_11 +25.2(v1)→+89.7(v2.7)` (v2.7 easier) vs
>    `Stage-B +86.9(v1)→+34.9(v2.7)` (v2.7 *harder*) — but those v1 numbers were CONTAMINATED. The clean
>    net-vs-v1 top-up (PROTOCOL_001) gives **iter_11 v1 = +35.7, Stage-B v1 = +24.4** (the old Stage-B
>    +86.9 was a **62-elo inflation**). Clean Δ(v2.7−v1): iter_11 **+54 (z=2.29)**, Stage-B **+10 (z=0.46,
>    n.s.)** — **SAME sign for both**. So the leaf effect is **NOT sign-varying / non-transitive**; both
>    nets simply beat the **weaker v2.7-leaf opponent** (corroborating r1's −24.4) by more than the v1
>    opponent, by a net-specific magnitude. There is still no single universal discount (magnitudes
>    differ), but the dramatic sign-flip framing was a contamination artifact. → **CL-016 *Disfavored*,
>    CL-012 *strengthened***.

---

## Claim-by-claim classification

| # | Old claim (source) | Old number | Clean number | Class | Note |
|---|---|---|---|---|---|
| A | Stage-B iter_01 vs HeuristicMCTS (A8) | +86.9 (v1) → +48.1 (v2.7, 700k) | **+34.9 ± 17.8** (#3) | **directionally survives (magnitude down)** | the learned-policy edge is REAL (~2σ) but ~40% of the +86.9 v1-headline; consistent with the +48.1 correction within noise. The matched-leaf correction stands. |
| B | iter_11 vs HeuristicMCTS base s200 (A1) | +25.2 / z=1.45 (v1, inconclusive) | **+89.7 ± 17.2** (#2) | **survives — strengthened** | vs the MATCHED v2.7 yardstick the edge is large + strongly significant (z=5.2). The old +25.2 was vs v1 AND inconclusive; the clean matched number is the trustworthy one. |
| C | iter_11 vs HeuristicMCTS s800 | +56.7 | not re-run (s200 pass) | **carry-forward** | s800 plane not in this pass; #2 (s200, +89.7) is the clean matched-depth anchor. |
| D | iter_11 +181.7 / 9.2σ (River+buggy, A1) | +181.7 | superseded by #2 | **invalidated** | River + farm-bug artifact; base-only clean is +89.7 vs the matched yardstick, nowhere near +181.7. |
| E | residual value-head marginal (lever-1, A6) | +46.5 pooled (z≈2.29) | **+26 ± 20 / z=1.30** (#4 marginal) | **inconclusive (not cleanly reproduced)** | on the repaired ruler (R7 now GUARANTEES the residual path fired) the deck-paired marginal is smaller and not resolved at n=400. Propose top-up (see below). The old "+45 robust" does not survive as a clean verdict. |
| F | residual absolute vs yardstick | (various) | **+83.2 ± 16.9** (#5) abs; **+56.1** (#4a) policy-only | **survives (absolute)** | the residual net beats the matched v2.7 yardstick strongly; its scale-0 (policy-only) is already +56.1, scale-0.25 +83.2. |
| G | the v1→v2.7 leaf gap (R1) | ~+39 (implied inflation) | **−24.4 ± 16.5** (#1) | **invalidated (as stated) / reframed** | the PURE leaf gap is NEGATIVE (v2.7 weaker, z=1.5 inconclusive). The "+39 universal discount" is not supported; the leaf effect is non-transitive (see box above). |
| H | c=3.0 = +47.2 / 2.8σ (A6) | +47.2 → +18.5 (n=1600) | not re-run | **directionally survives** | already a known noise spike corrected to +18.5; not a Phase-3 cell. |
| I | value-as-leaf cliff λ0.5≈−24..−38, λ1.0≈−552..−604 (A2) | large negative | not re-run | **survives (qualitative)** | a separate, repeatedly-reproduced finding; not a Phase-3 cell. |
| J | odometer 588/325 crossover | — | not re-run | **carry-forward** | not in the Phase-3 set; flagged for a later clean pass on the repaired ruler. |

### Power discipline (applied)
n=400 paired ≈ ±16–18 elo here, so a verdict needs ≥ ~35 elo (2σ). Cells **#2/#4a/#5** clear it
(resolved); **#3** sits right at 2σ (real but marginal); **#1** (−24.4, z=1.5) and the **residual
marginal** (+26, z=1.30) are **inconclusive** — both in the gray zone. **Proposed top-ups** (deck-paired,
clean): to resolve the residual value-head marginal (~+26 elo) and the leaf gap (~−24 elo) at 2σ needs
**≈ n=900–1500 paired** each. Do NOT pool these screens into a confirmatory claim.

---

## What changes in the strategic narrative

1. **The learned policy edge is REAL on a trustworthy ruler.** Every net beats the *matched-leaf*
   v2.7 yardstick: iter_11 **+89.7**, Stage-B iter_01 **+34.9**, residual **+56–83**. The central
   worry — "our results are all based on a lie" — is **not** the story: the policy advantage survives
   the R1 correction. It is *real*, just **in-ecosystem** (vs our own HeuristicMCTS), and **net-specific
   in magnitude**.
2. **The "leaf gap = universal +45% inflation" framing is OVERTURNED.** The pure v2.7 leaf is *weaker*
   than v1 in standalone search (−24.4), and the opponent-leaf change moves different nets in opposite
   directions. So the earlier guidance ("mentally discount every vs-HeuristicMCTS absolute ~45%") was
   itself an over-generalization. Absolutes must be re-measured per-net at a matched leaf, which is now
   exactly what the repaired ruler does — not blanket-discounted.
3. **The residual value head is NOT a clean win on the repaired ruler.** With R7 closed (the residual
   path is now runtime-guaranteed to fire), the value-head marginal drops to **+26 ± 20 (z=1.30,
   inconclusive)** from the old "+45 robust." The residual net is strong *as a whole* (+83.2), but how
   much of that is the value head vs the policy is **unresolved at n=400** — a top-up is required before
   any production fold-in. This is the single most consequential downgrade from the clean pass.
4. **The ruler itself is now trustworthy.** Provenance is runtime-verified (R1/R7 guards), seeds are in
   the clean 1e9 namespace with deck hashes, manifests record both sides' full config, and 11 semantic
   contracts + the provenance suite are green. Future strength claims rest on this, not on
   dirname archaeology.

_Source of every number: `clean_eval/CLEAN_RESULTS.csv` + per-cell `manifest.json` under
`/mnt/c/carc-shared/clean_eval_runs/`. No training was performed in this task._
