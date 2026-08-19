# REVIEW_R3 — rung3_r5 pair rev R5.1, SECOND REVIEWER (same reviewer as `REVIEW_R2.md`). Reviewed commit `bb11dbbd`. Date 2026-08-19.

> **Reviewer: second reviewer, fresh session, no part in drafting the pair.** Re-review round: the
> drafter amended the pair against [`REVIEW_R2.md`](REVIEW_R2.md) (FAIL: 6 BLOCKING, 11 REQUIRED,
> 5 COSMETIC). Scope: `DESIGN.md`, `READ_RULE.md`, `FLOORS_R5.json` at `bb11dbbd` in worktree
> `agent-a43f00f675fd11b65`, read read-only, against `CALIBRATION.json`, `../shared_run_r4/`,
> `../shared_run/`, `../DEVIATIONS.md`, and the physical S2 leg file.
> Method unchanged: **re-derive from primitives** — every number below was recomputed from the
> artifacts, not read off the prose.
>
> **This review is the review of record for `bb11dbbd`.**

## RE-REVIEW — `rung3_r5` pair rev R5.1 (worktree `agent-a43f00f675fd11b65`, commit `bb11dbbd`). **VERDICT: FAIL** — 3 BLOCKING, 3 REQUIRED, 2 COSMETIC.

All three blocking items are narrow and mechanical (one denominator, one key path, one build gap), but each fails a healthy run, so the pair must not merge as the blind commit yet.

## Verified GOOD — re-derived from primitives

**The n₂ = 1,060 correction is right, and it is better than my own review.** On the leg: **3 dupe groups, each of size 2 = 6 positions involved, 3 later members excluded.** The extra exclusion is the R4 residual collider `tt_sp_135000000839_p2` — I confirmed it **is** present in the leg, is band 135e9, and is **not** a member of any dupe group (all three groups are 137e9↔137e9), so there is no double-count. **1064 − 3 − 1 = 1060**; ⌈0.95 × 1060⌉ = ⌈1007.0⌉ = **1007** ✓. This also closes my B4(b) (the residual collider that no gate removed). My own figure would have been 1,061; the drafter's is correct.

Also verified exact: **leg sha256 `92ba1ee2dfbfed91f4853173e16e6e008d430ebf708055f4c8a76258eacbb7df`** byte-for-byte ✓. Power at n=1,060: se ∈ [0.02764, 0.04300] and bars 2.2497 / 1.3707 / 0.8790 → printed 2.250 / 1.371 / 0.879 ✓. Cost: 1060 × 0.275 = **291.5** ✓, realized 0.191824 × 1060 + 8.1 = **211.4** ✓ — R3's currency fix folded exactly. **G-DISJOINT's restored address is schema-valid** — `layers.{a_root_id,b_rid}.n_intersection` exists in the real artifact ✓. **G-INTERNAL-DUPE (ii) passes on the healthy corpus** — 3 groups / 6 positions / all ply 2 / all 137e9↔137e9 matches the file exactly, so it is not fail-always ✓. G-BAND's range conjuncts hold: **0 out-of-range seeds, 0 from 136e9** ✓. The **A1/A2/A3 logic is sound** — the union covers all three markers and no pass demands an address its position makes impossible ✓. B3/B5/B6, R2, R5–R11 and the R4 second reversal are all fixed at their sites ✓. **Main tree is clean of the stray `FLOORS_R5.json`** — `rung3_r5/` on main holds only `CALIBRATION.json` and the old `DESIGN.md` ✓.

## BLOCKING

**N1. `G-BAND`'s `n_duplicate_seeds == 0` is FAIL-ALWAYS at the positions denominator.** Measured on the leg: **1,064 positions over 980 distinct game seeds — 82 seeds occur more than once, max 3 per seed** — which is mandated by `--max-per-game 3`. R4's G-BAND read *game*-level `CHAMP_GAMES_VERIFY*.json` (one row per game, where 0 is correct); R5.1 re-points the conjunct at `CORPUS_R5.json`, a positions artifact, without re-basing the denominator. This is the same currency class as the original B1, reintroduced by the restoration.

**N2. `G-M`'s new pre-leg primary does not exist in any emitter's schema.** `RUN/SMOKE_R5.json::resolved_config.m` — the R4 smoke manifest has **no `resolved_config` key at all** (top-level `m_worlds`), and neither does the leg manifest (also top-level `m_worlds`), so the row's fallback `legs/…/manifest.json::resolved_config.m` is unresolvable too. R1 asked for a pre-leg halt so the M=32 constant is checked before ~300 wh; as written the halt gate cannot resolve at either address. (R3.3 carried the same wrong key latently behind a working primary; R5.1 promotes it to load-bearing.)

**N3. Five new run-time artifacts have no builder and no fixtures.** `CORPUS_R5.json`, `GATE_INTERNAL_DUPE.json`, `GATE_DISJOINT_R5.json`, `SMOKE_R5.json`, `MERGE_REPORT_s2.json` are addressed by nine conjuncts; the pair's only W-item is `R5-W1` (`--min-ply`), made moot by k=0. A1 is defined as a static audit "against committed fixtures" and **no fixture set is committed** — precisely the leak R5-6.1 diagnosed in R4 ("R4's covered the leg manifest and the smoke manifest but not `RUN_MANIFEST`"), now five-fold. A1 cannot pass, so the blind commit cannot be certified.

## REQUIRED

**N4. `r4_exclusion_list_sha256` has no named referent.** It matches none of the four `EXCLUDE_RIDS_*.txt` files. I reproduced it in one of four guesses: it is `sha256(json.dumps(sorted(GATE_DISJOINT.json::digest_exclusions.S2.rids)))` = `76f9ac58e2694a54…` ✓ — **the value is correct**, but the key path and canonical serialization are unwritten, so no verifier can reproduce it. Name both in `FLOORS_R5.json`.

**N5. `resolved_config.*` fallbacks in `G-SALT` and `G-BACKEND` are unresolvable** for the same reason as N2 (no such key in either emitter). Their primaries resolve, so not blocking — but they will fail A1's static audit.

**N6. `G-INTERNAL-DUPE` (i) is labeled "LIVE" and contradicts §2.1 two rows later.** Because `G-CORPUS` sha-pins the leg, `d_internal` is a deterministic function of a pinned file — (i) cannot fail unless the sha check already did. §2.1 says this honestly and I accept the disclosure; the conjunct column should say "identity-derived", leaving (ii) to carry the falsifiable content.

## COSMETIC

**N7.** C5 unfixed: §R5-5's old cost table (≈197–309 wh at N=700/1,100) still stands beside §R5-FINAL.g's 211.4–299.6 at n₂=1,060.

**N8.** §R5-FINAL.a's k-table still reads "collisions at governed scale **3**" without the group/position qualifier the rest of the document now carries.

---

**Bottom line.** The amendment fixes all six BLOCKING and all eleven REQUIRED items from REVIEW_R2 at their sites, and the n₂=1,060 correction is a real catch the review missed. What remains is a third instance of the campaign's signature failure — the restoration itself introduced one fail-always denominator (N1) and one unresolvable primary (N2) — plus the build/fixture gap the new addresses opened (N3). None is deep; all three are checkable against artifacts already on disk. **Do not merge or launch on this revision.**
