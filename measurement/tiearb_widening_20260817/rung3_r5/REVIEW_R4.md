# REVIEW_R4 — rung3_r5 pair rev R5.2 + the R5 emitters, SECOND REVIEWER (same reviewer as `REVIEW_R2.md` / `REVIEW_R3.md`). Reviewed: pair `bed67165` (worktree `agent-a43f00f675fd11b65`) + builder `97b496a6` (worktree `agent-a36aa757d77af3968`). Date 2026-08-19.

> **Reviewer: second reviewer, fresh session, no part in drafting the pair or building the emitters.**
> Final pass, two pieces together: the R5.2 amendment's disposition of `REVIEW_R3.md`'s N1–N8, and
> the emitter build that backs its addresses. Method unchanged: **re-derive from primitives** —
> every number below was recomputed from the artifacts and the emitters were executed, not read.
>
> **This review is the review of record for `bed67165` + `97b496a6`.**

## VERDICT: **FAIL** — 1 BLOCKING, 0 REQUIRED, 2 COSMETIC.

One item, narrow and one-line-fixable. Everything else in both commits is verified correct and ready. Of the builder's three flagged inferences, **(a) is right, (c) is right, (b) is the blocking one.**

## First — a reviewer error, conceded

**My `REVIEW_R3.md` N2/N5 was half wrong, and the drafter's pushback is correct.** `tier1_rust_leg.py:396–412` does emit `resolved_config.{m, m_max, world_seed_salt, legal_mask_cache, arb_backend, oracle_sims, …}`, and I confirmed it in three real `tier1-greedy` leg manifests (`m=128`, `world_seed_salt=tiletie-v1`, `legal_mask_cache=True`). My check had sampled only **`clair-puct`** leg manifests — a different emitter, which has no `resolved_config` key — and I generalised from the wrong judge. Since `G-M`, `G-SALT` and `G-BACKEND` all bind `<judge>` to `tier1-greedy`, **their leg fallbacks resolve and always did.** Only the *smoke* half of N2 was a real defect, and R5.2 fixes it correctly (`SMOKE_R5.json::m_worlds`, top level — `run_tiletie`'s smoke manifest does carry `m_worlds` at top level, verified). Rejecting a reviewer claim with emitter evidence was the right call.

## Verified GOOD — re-derived and executed

**The builder reproduces every pinned value end-to-end.** Run against the real R4 leg (exit 0): `n_in=1064`, `n_excluded_r5=4`, **`n_positions=1060`**, `n_distinct_seeds=980`, `max_positions_per_seed=3`, `n_out_of_band=0`, `n_seeds_136e9=0`, `leg_sha256=92ba1ee2…` ✓, `r4_exclusion_list_sha256=76f9ac58…` ✓, and `excluded_rids = [tt_sp_135000000839_p2, tt_sp_137000002154_p2, tt_sp_137000003379_p2, tt_sp_137000004174_p2]` — the 1 residual plus exactly the three later-ordered dupe members I computed independently. `GATE_INTERNAL_DUPE`: `n_dupe_groups=3`, `n_dupe_positions=6`, `d_internal=0.002819548872180451`, `ply_histogram={2:6}`, `band_pairs=3× "137e9<->137e9"` ✓. Run without explicit paths it **fails closed** (exit 2, nothing written) rather than guessing.

**N1 fixed well.** `n_duplicate_seeds == 0` is deleted, and `max_positions_per_seed ≤ 3` replaces it — a real, falsifiable invariant (the leg's true max is 3, and a mis-set mining ceiling or a double-counted union would break it), evaluated at the positions level where it belongs, while the range conjuncts moved to the seed level (980 distinct seeds). The address field list matches the emitter's output exactly, all five keys.

**N3 fixed.** §R5-FINAL.i's five-artifact emitter table is specific enough to build from, and 9 fixtures are committed. **N4 fixed exactly**: §R5-FINAL.j pins `sha256(json.dumps(sorted(<GATE_DISJOINT.json>::digest_exclusions.S2.rids)))`, default separators, no `sort_keys`, UTF-8, no trailing newline — identical to the serialization I reverse-engineered in `REVIEW_R3.md`, and it explicitly warns the value is none of the four `EXCLUDE_RIDS_*.txt` files. **N6, N7, N8 folded** (identity-derived relabel; the old ≈197–309 wh table struck through and pointed at §R5-FINAL.g's ≈211.4–299.6; the k-table now reads "3 GROUPS of 2 = 6 positions involved").

**A1 verified in the failing direction, which is the direction that matters.** Baseline: **47 markers, 0 failed.** Delete `CORPUS_R5.fixture.json` → **12 markers FAIL** ✓ — it iterates the marker list, not the fixtures directory, so a missing fixture cannot pass silently. Delete a non-marker key (`design_doc`) → 0 failures, which is correct: A1 audits only the addresses `READ_RULE` actually names.

## Ruling on the builder's three flagged inferences

**(a) The comparison set — CORRECT.** `{s2_vs_tiletie0812, s2_vs_tiearb2_0816, base_vs_extension, s2_vs_exclude_rids}` is the right reading of "R4 §2b(i) with one stratum": R4's seven minus the three that require an in-run S1 side (`s1_vs_tiletie0812`, `s1_vs_tiearb2_0816`, `s1_vs_s2`), with the exclude-rids comparison renamed. The one substantive question — that R4's S1 is now itself a spent neighbour and gets no comparison — resolves in the pair's favour: **rid/root disjointness from R4's S1 is guaranteed by `G-BAND`(i)'s range conjunct in both bands.** R4-6 split 135e9 at +349/+350 (S2 gets +350…+849) and the 137e9 sub-ranges are disjoint (S1 `+0…+507`, S2 `+508…+5347`), and I verified all 1,064 seeds lie inside R5's two committed ranges with **0 out-of-range**. No R5 rid can be an R4-S1 rid. The inference is sound and its justification should be written down.

**(b) The empty exclude-list default — NOT SOUND. This is the blocking item.** With `exclude_rids=()`, `compare_rid_list` computes `len(new_rids & set()) = 0` **unconditionally**, reports `passed: true`, and counts as one of the four comparisons in the gate's conjunction. That is pass-always — a conjunct structurally incapable of failing, shipped as a leakage check, which is the exact disease of B1/B2 and of the campaign's three prereg deaths.

It is not merely vacuous — **the correct reference makes it the only live check of something nothing else gates.** Measured against the real 29-rid R4 S2 exclusion list: `n_intersection = 1` on the 1,064-position **input** (it would FAIL, correctly, because `tt_sp_135000000839_p2` is still physically present) and `n_intersection = 0` on the 1,060-position **output** (it PASSES). So with a real reference this comparison verifies that **R5's own four exclusions were actually applied** — and today nothing does: `excluded_rids` is emitted by the builder but is **not** in `G-CORPUS`'s gated address list, and `n_excluded_r5 == 4` is satisfied by excluding any four rids. The reference is already sha-pinned by §R5-FINAL.j, so the fix costs one path argument plus one spec line.

Root cause is joint, not the builder's alone: **§R5-FINAL.i's `GATE_DISJOINT_R5.json` row specifies neither the comparison set nor the exclude reference**, so both had to be inferred. Fix the spec row and the default together.

**(c) The band-label spelling split — CONSISTENT, not an R8-class hazard.** Short `"137e9<->137e9"` lives in `GATE_INTERNAL_DUPE.band_pairs`, long `banked_135e9` / `extension_137e9` in `CORPUS_R5.seed_ranges`. Each artifact's vocabulary matches the conjunct that reads it: `READ_RULE`'s `G-INTERNAL-DUPE` (ii) says "137e9↔137e9 same-band" (short) and `G-BAND` names its ranges **numerically**, never by key label. No conjunct resolves a band label across the two vocabularies, so nothing fails closed — unlike R8, where one key path had to resolve under a single spelling. Recommend one line declaring the mapping; not a defect.

## BLOCKING

**P1. `s2_vs_exclude_rids` is pass-always as configured, and §R5-FINAL.i does not specify otherwise.** See (b) above for the derivation and the proof that a real reference is live (1 on the input, 0 on the output). **Fix:** name the reference in §R5-FINAL.i — `sorted(GATE_DISJOINT.json::digest_exclusions.S2.rids)`, the list §R5-FINAL.j already pins the sha of — pass it to `run_r5_gate(exclude_rids=…)`, and add a test asserting the comparison **fails** on the pre-exclusion corpus. Also add `excluded_rids` to `G-CORPUS`'s gated address list so the *identity* of the four exclusions is gated, not just their count.

## COSMETIC

**P2.** `check_a1()` returns no explicit pass/fail boolean — its verdict is implicit in `n_failed`, and the docstring promises a `missing_files` key the returned dict does not carry. A caller that truth-tests the dict reads PASS on a failing audit. Return an explicit `ok`.

**P3.** `build_r5_corpus.py`'s default paths resolve repo-relative to whichever tree it runs from, so it cannot find the R4 corpus from a worktree. Correct after the blind commit lands on `tiearb2-stage2`, and it fails closed meanwhile — worth one line in §R5-FINAL.i saying the defaults assume the merged tree.

---

**Bottom line.** R5.2 disposes of N1–N8 correctly, rejects one reviewer claim with evidence and is right to, and the emitter build reproduces every pinned value against the real leg with a marker-driven A1 that fails in the right direction. Two of the builder's three flagged inferences are correct. The third — an empty exclude-list reference — is a pass-always conjunct in a gate table whose credibility rests on not having any, and the correct reference happens to close the one hole nothing else covers. **One spec line, one argument, one test. Fix P1 and this pair is ready for the blind commit.**
