# Phase 0 — Evidence-Hygiene Notes (pre-tool audit)

> **Scope:** a claim-language cleanup / issue list, NOT a rewrite. Triggered by the
> clean-room reviews ahead of the pre-tool audit. Every issue cites the offending
> `path:line` and the data that adjudicates it. Each item is marked **PATCHED**
> (a surgical edit was applied this session) or **NOTED** (flagged only; no edit, or
> edit deferred to avoid scope-creep).
>
> **FACTS vs INTERPRETATION:** the numbered findings below are FACTS read off the
> committed verdict docs / result JSONs (cited). The "suggested language" is an
> INTERPRETATION of how to phrase them more defensibly.
>
> Base commit: `1924261`. Audit dir: `measurement/pre_tool_audit/`.

## Adjudicating data (the per-K exact-solver top-1 table)

The single most useful fact for the "heur@3200" language question — exact clairvoyant
solver top-1 (fraction of moves that are solver-optimal), by K:

| agent        | K=2 (n=141) | K=3 (n=68, partial) | K=4 (n=187) |
|--------------|:-----------:|:-------------------:|:-----------:|
| heur@3200    | **0.837** (tied) | **0.618** (2nd-worst) | **0.679** (best) |
| heur@1600    | 0.780       | 0.647               | —           |
| heur@800     | 0.759       | 0.632               | 0.652       |
| heur_v1@200  | **0.837** (tied) | 0.750 (best)    | —           |
| greedy       | 0.759       | 0.750 (best)        | 0.647       |
| **iter8**    | **0.667** (worst) | **0.574** (worst) | **0.561** (worst) |

Sources: K=2 + K=3 → [LEVEL2_L23_VERDICT.md:30-53](../level2/LEVEL2_L23_VERDICT.md);
K=4 → [LEVEL2_K4_PROBE_VERDICT.md:67-83](../level2/LEVEL2_K4_PROBE_VERDICT.md).
**Read:** heur@3200 is best at K=4, *tied*-best at K=2, but **second-worst at K=3** (the
shallow agents top it there). So "most endgame-precise on every suite" is false; "strong
on K=4 and the strongest directly-tested full-game ruler" is true. iter8 is worst at every K.

---

## Item 1 — "heur@3200 most endgame-precise" stated as universal  → **PATCHED**

**FACT.** [LEVEL2_HYBRID_VERDICT.md:12](../level2/LEVEL2_HYBRID_VERDICT.md) — the Question
section says `"heur@3200 most endgame-precise"` (unqualified). [LEVEL2_L23_VERDICT.md:102-103](../level2/LEVEL2_L23_VERDICT.md)
says heur@3200 is `"simultaneously the most endgame-precise (this verdict) AND the heuristic
that catches iter8 full-game"`.

**Why it's an issue.** The per-K table above shows heur@3200 is **second-worst at K=3
(0.618)**, behind heur_v1@200/greedy (0.750), and only *tied*-best at K=2 (0.837 = heur_v1@200).
It is clearly best only at K=4. So "most endgame-precise" is not universally true across the
exact-endgame top-1 suites.

**Suggested / applied language.** heur@3200 = the **strongest known directly-tested practical
full-game ruler/reference** against iter8/hybrid; **strong/robust on K=4** (best top-1 0.679);
**NOT universally best across K=2/K=3/K=4 exact-endgame top-1** (shallow agents top it at K=3).

**Action.** PATCHED both lines with K-qualified language (see "Patches applied" below).

## Item 2 — "iter8 decisively loses to heur@3200" / "hybrid clearly better than iter8" → **PATCHED (one line)**

**FACT.** iter8 vs heur@3200 = **−28.7 Elo, 180W/7D/213L, paired z=−0.70**
([STATUS.md:16](../../STATUS.md), [LEVEL2_L23_VERDICT.md:100](../level2/LEVEL2_L23_VERDICT.md),
results.csv `l22_iter8_vs_heur3200_b310_n400`). [LEVEL2_HYBRID_VERDICT.md:57](../level2/LEVEL2_HYBRID_VERDICT.md)
says the hybrids are `"clearly better than plain iter8 (−28.7 Elo, z=−0.70 vs heur@3200)"`.

**Why it's an issue.** The headline loss is a **point estimate negative with a modest paired z
(|z|<1) = a tie-to-slight-loss on margin**, not a decisive loss. And the "clearly better than
plain iter8" comparison stacks two |z|<1 cross-results (hybrid −13.9/−19.1 vs iter8 −28.7),
so "clearly" overstates. Most of the doc already phrases this correctly (STATUS.md:16
"tie on margin"; HYBRID:56 "|z|<1 a statistical tie-to-slight-loss").

**Suggested / applied language.** iter8 **fails to beat** heur@3200 (tie-to-slight-loss);
point estimate ≈ −28.7 Elo, paired z ≈ −0.70 (modest). The hybrids reduce that gap
(−13.9/−19.1, |z|<1) but do not surpass heur@3200.

**Action.** PATCHED HYBRID_VERDICT:57 ("clearly better" → "modestly closer to … (still |z|<1)").

## Item 3 — Missing final heur@3200 rung in the L2-2 ladder table → **PATCHED (row added)**

**FACT.** [LEVEL2_L22_VERDICT.md:18-21](../level2/LEVEL2_L22_VERDICT.md) tabulates only
iter8 vs heur@800 (+40.1) and iter8 vs heur@1600 (+34.9 fresh band / +24.4 same-band 3.10).
The completing rung **iter8 vs heur@3200 = −28.7 (z−0.70)** appears only in
[LEVEL2_L23_VERDICT.md:99-100](../level2/LEVEL2_L23_VERDICT.md) and STATUS.md:16, not in the
L2-2 results table where the same-band ladder lives.

**Why it's an issue.** The same-band ladder **+40.1 (@800) → +24.4 (@1600) → −28.7 (@3200)**
is the headline "iter8's edge shrinks with heuristic depth and is erased at @3200" finding;
omitting the @3200 row from the L2-2 table makes that table look like iter8 wins the whole
ladder.

**Action.** PATCHED — added a cross-reference row + note for the @3200 rung to the L2-2 table.

## Item 4 — Clairvoyant numbers "transfer" to honest play → **NOTED (already ~qualified)**

**FACT.** [CLAIRVOYANCE_GAP_VERDICT.md](../clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md) reports
the deck-order clairvoyance gap ≈ **+27 Elo, z≈−0.9** (a minor contributor) and phrases the
conclusion as clairvoyant numbers "**~transfer** to honest, deployable play" (note the `~`).

**Why it's a (minor) issue.** The measured gap is for the **sims=200 / root-determinization**
setup only; it bounds *deck-order* clairvoyance, not full fair-information equivalence. The
exact K-solver labels (K=2/K=3/K=4) are **clairvoyant** (perfect future-deck knowledge); the
only fair-information labels that exist are **marginalized K=2** (see FAIR_INFORMATION_LABELS_NOTE.md).

**Suggested language.** A large (≥100 Elo) clairvoyance inflation is **NOT supported** in the
tested sims=200/root-determinization setup; full fair-information transfer is **not fully proven**.
Keep exact-K clairvoyant labels verbally distinct from fair-information/bag-expectation labels.

**Action.** NOTED only (the verdict already uses "~transfer"); no edit. Carried as a standing
caveat into the audit's clairvoyance handling.

## Item 5 — Learned value/ranking "cannot work" → **NOTED (already correctly bounded)**

**FACT.** [value_ranking/VALUE_RANKING_VERDICT.md:54-55](../../value_ranking/VALUE_RANKING_VERDICT.md)
explicitly states the result `"does NOT prove 'value-as-leaf is categorically impossible' — it
proves the *tested* swing (relational arch + ranking loss, this scale) is disfavored."`

**Why it matters here.** The pre-tool audit's premise is exactly the untested cell: a
**tool-augmented / action-ranker** formulation has NOT been tested. The existing kill-test
covers learned **scalar value / sibling-action ranking / attention swing** only.

**Suggested language.** Tested scalar-value / ranking / attention-swing formulations FAILED
(near-zero learned sibling ranking vs strong v2.7 leaf ranking); a tool-augmented action-ranker
remains **untested**.

**Action.** NOTED only (verdict is already bounded). This framing is adopted in PRE_TOOL_AUDIT.md.

## Item 6 — K=4 pilot source split (0.92/0.36) presented before its caveat → **NOTED (self-corrected)**

**FACT.** [LEVEL2_K4_PROBE_VERDICT.md:50-56](../level2/LEVEL2_K4_PROBE_VERDICT.md) shows the
n=12/cell pilot source split (iter8 0.92 own / 0.36 greedy). The same doc corrects it at
lines 97-111 / 143-145: the pilot's 0.92/0.36 was **n=12 noise**; the balanced 200-position
expansion gives the real, tamer effect **0.65 own / 0.44 greedy** (same direction).

**Why it's a (minor) issue.** The pilot table at line 50-56 is labeled "PILOT … Small n
(10–12/cell) → EXPANSION underway" and is explicitly superseded later, so a careful reader is
warned — but a reader quoting line 52 in isolation could carry the stale 0.92/0.36.

**Action.** NOTED only — the doc is self-correcting (line 97 "NOT supported as stated (the
pilot's 0.92 was n=12 noise)"). No edit; flagged so downstream docs cite the **0.65/0.44**
expansion numbers, never the pilot's 0.92/0.36.

## Item 7 — "~95% policy" decomposition claim → **NOTED (cite the decomposition source)**

**FACT.** The "~95% policy, plateaued iter5" decomposition of iter8's +67.4 Elo gain lives in
[governance/PRODUCTION.yaml:46-48](../../governance/PRODUCTION.yaml) (and is echoed in CLAUDE.md),
**not** in the level2 verdict docs. The clean-room asked for the supporting Stage-B decomposition
rows wherever this claim is retained.

**Action.** NOTED only. Recommendation: where the "~95% policy / ~5% value" split is asserted,
cite the Stage-B / decomposition evidence row (governance) so the number is traceable, or
qualify it as "decomp 2026-06-10, single estimate." Not patched here (governance-file edit is
out of this audit's claim-language scope).

---

## Checks that found NOTHING (already clean)

- **Hybrid K≤5 / K≤8 n=400 z mismatch:** consistent. HYBRID_VERDICT:62 gives K≤5 z=+6.23,
  K≤8 z=+5.79 (n=400); HYBRID_VERDICT:42 gives the n=200 values (z=4.68 at K≤8). The z
  regression at higher n tracks the small point-estimate regression — no contradiction.
- **±12 vs ±17.5 Elo:** the L2-2 verdict tables consistently use **±17.5** for n=400
  ([LEVEL2_L22_VERDICT.md:20-21,86,117](../level2/LEVEL2_L22_VERDICT.md)), which matches the
  current CLAUDE.md standard for an *unpaired* n=400 1σ. The "±12 paired" figure appears only
  in protocol docs as the *optimistic* paired estimate. **Minor note:** the verdict tables
  label these "n=400 paired" yet cite ±17.5 (the unpaired σ); the realized paired correlation
  did not halve variance, so ±17.5 is the honest band. No correction needed — the conservative
  ±17.5 is the right number to carry; just don't claim the ±12 paired ideal was achieved.

---

## Patches applied this session

All edits are surgical claim-language / completeness fixes; logged here for the close-out trail.
Run `python3 scripts/doc_lint.py` after review.

1. `measurement/level2/LEVEL2_HYBRID_VERDICT.md:12` — qualified "heur@3200 most endgame-precise".
2. `measurement/level2/LEVEL2_HYBRID_VERDICT.md:57` — "clearly better than plain iter8" → tie-aware.
3. `measurement/level2/LEVEL2_L23_VERDICT.md:102-103` — K-qualified the "most endgame-precise" summary.
4. `measurement/level2/LEVEL2_L22_VERDICT.md` — added the missing iter8-vs-heur@3200 rung row + note.
