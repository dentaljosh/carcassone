# REVIEW_R5 — rung3_r5 P1 confirmation round, SECOND REVIEWER (same reviewer as `REVIEW_R2` / `R3` / `R4`). Reviewed: pair `96ee4991` (worktree `agent-a43f00f675fd11b65`) + builder `90a5e982` (worktree `agent-a36aa757d77af3968`). Date 2026-08-19.

> **Reviewer: second reviewer, fresh session, no part in drafting the pair or building the emitters.**
> Scope: the two-sided fix for `REVIEW_R4.md`'s single BLOCKING item (P1), plus the disposition of
> P2/P3. Method unchanged: **re-derive from primitives** — the spec was read against the
> implementation, the emitters were executed, and the refuse paths were exercised.
>
> **This review is the review of record for `96ee4991` + `90a5e982`.**

## VERDICT: **PASS.** No BLOCKING, no REQUIRED. Two cosmetics, neither gating.

**The pair is ready for the blind commit.**

## P1 — spec, implementation, and my measured expectation all agree

**Spec side (`96ee4991`), §R5-FINAL.i.** Both required lines are pinned, and they say what I ruled they had to say:

- **(a) Comparison set pinned** — `{s2_vs_tiletie0812, s2_vs_tiearb2_0816, base_vs_extension, s2_vs_exclude_rids}`, derived in the document as "R4's seven minus the three that require an in-run S1 side". ✓
- **(b) Exclude-rids reference pinned**, "**NEVER a default, NEVER an empty list**" — `sorted(GATE_DISJOINT.json::digest_exclusions.S2.rids)` from `shared_run_r4/GATE_DISJOINT.json`, under §R5-FINAL.j's canonical serialization whose sha `76f9ac58…` already pins it. It carries the expectation explicitly — `n_intersection == 0` on the 1,060 output, **non-zero (1)** on the pre-exclusion 1,064 input — and the test requirement in the strongest form: *"A test MUST assert the comparison FAILS on the pre-exclusion corpus; a reference that cannot fail on the un-cleaned corpus is not a reference."* ✓
- **The `G-BAND`(i) justification is written down** — the +349/+350 split of 135e9, the disjoint 137e9 sub-ranges (S1 `+0…+507`, S2 `+508…+5347`), and the 0-out-of-range verification, concluding that no R5 rid can be an R4-S1 rid so a comparison would be redundant. The *reason* is now on the record rather than a reader seeing only a missing comparison. ✓
- **Band-label mapping declared once**, with `banked_135e9 ≡ 135e9` / `extension_137e9 ≡ 137e9`, and correctly labelled **not** an R8-class hazard (there, one key path had to resolve under a single spelling). ✓
- **`excluded_rids` is now GATED in `G-CORPUS`** against **exactly the four** — `tt_sp_135000000839_p2` plus the later-ordered member of each of the 3 same-band dupe groups — so the *identity* of the exclusions is gated, not only their count. That closes the hole I named: `n_excluded_r5 == 4` was satisfiable by excluding any four rids. ✓

**Implementation side (`90a5e982`).** It matches the spec and is fail-closed at every entry:

- `run_r5_gate(..., exclude_ref_rids, ...)` — **required keyword, no default**; raises `GateInputError` on empty/falsy with the reason stated inline ("an empty/omitted reference makes that comparison pass-always, not a leakage check"). ✓
- `load_r4_exclusion_rids` raises on a missing file, malformed JSON, a missing `digest_exclusions.S2.rids` path, or a non-list value — **never returns a coerced empty list**, which is the precise defect P1 named. ✓
- **One loader, aliased not duplicated**: `build_r5_corpus.load_r4_exclusion_rids = GD.load_r4_exclusion_rids`, so the `r4_exclusion_list_sha256` conjunct and the `s2_vs_exclude_rids` comparison provably cannot read two different lists. ✓

**The 1→0 witness, reproduced verbatim against my own measurement.** `test_real_data_exclude_rids_1_to_0_pattern` runs on the **real** leg and the **real** R4 `GATE_DISJOINT.json`, loads the real 29-rid reference, and asserts on the 1,064-position input `n_intersection == 1` **and** `comparison.passed is False` **and** `report.passed is False`; on the 1,060-position output `n_intersection == 0` and `passed is True`. That is exactly the pattern I measured independently in `REVIEW_R4`, including the gate-level failure, not merely the count. ✓

**Refuse paths exercised — all five present and green:** empty reference, `None` reference, missing reference file (CLI), wrong-shaped reference file (CLI), and `--r5-exclude-ref`'s default verified *loadable and non-empty at 29 rids* rather than merely present. That last one matters: it is the test that stops the default silently degrading back to the P1 defect. ✓

**Suites:** 87 tests green across the three R5-relevant files (`test_rung3_r5_emitters.py`, `test_rung3_calibrate.py`, `test_measurement_infra.py`). I did not re-run the full 373 and do not certify that number; what I ran is green and covers every P1 path.

## Cosmetics — disposition

**P2 — RESOLVED.** `check_a1()` now returns an explicit verdict. Verified in both directions: baseline `passed=True, n_failed=0` over **47 markers**; with `CORPUS_R5.fixture.json` removed, **`passed=False, n_failed=12`**. (The key is `passed`, not the `ok` I suggested — the name is immaterial, the explicit boolean is what P2 asked for. `pass` carries the pass *name* `"A1"`, not a second verdict.)

**P3 — NOT disposed, and correctly judged non-gating.** `build_r5_corpus.py`'s `REPO = Path(__file__).resolve().parents[2]` still resolves the default `--leg` relative to whichever tree it runs from, so from a worktree it cannot find the untracked R4 corpus. I confirmed the behaviour is **fail-closed**: exit 2, a named path in the error, nothing written. With explicit paths it exits 0 and reproduces every pinned value. The default is correct in the merged tree the run will execute from, and the exclude-ref default is unaffected (R4's `GATE_DISJOINT.json` is tracked, so it resolves from any worktree — the test above proves it). One line in §R5-FINAL.i saying the defaults assume the merged tree would close it; it does not gate the commit.

**P4 (new, cosmetic).** The spec line (b) writes the call as `run_r5_gate(exclude_rids=…)` while the implemented signature is **`exclude_ref_rids`**, and it takes a rid *set* rather than paths. A reader following the spec literally gets a loud `TypeError`, not a silent wrong result, and the rename is an improvement on the old paths-based parameter — but the spec line should quote the real kwarg.

---

**Bottom line.** P1 is fixed on both sides and the two sides agree with each other and with my independent measurement: the reference is pinned in the spec, required and fail-closed in the code, loaded through a single shared loader, and proved live by a real-data test that asserts failure on the un-cleaned corpus. The identity of R5's four exclusions is now gated, the G-BAND(i) structural guarantee is on the record, and the band-label coexistence is declared rather than discovered. P2 is resolved; P3 and P4 are cosmetic and non-gating. **PASS — proceed with the blind commit.**
