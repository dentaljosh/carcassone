# F1 — P0-lite release integrity build spec (2026-07-19)

**Status: DRAFT, ready to delegate.** Track-F item F1 ([REVIEW_ADOPTION_20260719.md](REVIEW_ADOPTION_20260719.md)); implements the review's Priority 0 at pragmatic scope. Gate for all future headline claims: **zero semantic/configuration divergences.** Est. ~1-2 engineering days (subagent-friendly) + CPU-hours for replay. No GPU, no box contention.

## 1. Executable champion factory
`src/carcassonne_ai/champion_factory.py`:
- `make_production_champion(mode: "fair"|"clairvoyant") -> agent` — reads `governance/PRODUCTION.yaml` (single source), instantiates `FairHeuristicPriorAgent` (curve125 leaf, c=1.5, τ_p=5, float, pooled-Q selector, k_dets=4, sims_per_det=688, exact-K≤2 marginalized handoff, CL-056 canonical deck sort).
- Emits a **resolved runtime manifest** at construction: leaf hash computed on real boards at runtime (assert == `a36d2e15` harness-dialect; note PRODUCTION.yaml's `158f17ff` is a STALE fingerprint — assert curve VALUES per the 2026-07-17 ruler-trap note, then fix the YAML field as part of this work), config hash, code rev, reshuffle semantics flag. Hash mismatch = raise, never warn.
- Integrate with the existing `eval_provenance.py` R1/R7 guards — extend, don't duplicate.
- Migrate call sites to the factory: `eval_fair_puct.py` `--opponent fair-champion` path, `scripts/human_anchor/play_harness.py`, any driver that hand-builds the champion config (grep for `FairHeuristicPriorAgent(` and champ-config dict literals).

## 2. Fix the stale human harness (E4 unblocker; parked ≠ broken)
`scripts/human_anchor/play_harness.py` still wires the PRE-FLIP `FairHeuristicMCTSAgent` + old leaf (roadmap parking-lot flag, 2026-07-13). Rewire through the factory; smoke one scripted game headless; leave E4 itself parked.

## 3. Semantic/property suite — `tests/release/`
One pytest module per property, all runnable via `scripts/release_audit.sh`:
- dual-farm/same-city scoring (adopt/extend the F0a fixture `tests/test_farm_multifield_city_p1l5.py` once landed);
- crop boundary: a **strict mode** where any legal action outside the window RAISES (today `get_valid_moves` silently drops unless ALL overflow — the review's P1-R1); release audit runs strict; production behavior unchanged until measured;
- legal-cache/state-key collision checker ON + assert zero collisions over the replay corpus (P1-R7/S6);
- rotation-alias canonicalization invariants (alias fold = same child, prior mass conserved);
- deck canonicalization: CL-056 sort is identity-independent of the true hidden order (regression for the 07-14 leak);
- current-tile/bag invariants (counts sum, no negative, discard path);
- `won_by_champ`/diff sign golden (the inverted-semantics scar);
- factory manifest golden: resolved manifest == PRODUCTION.yaml intent, byte-stable across two constructions.

## 4. Adversarial state replay
Extend the Phase-0.2 window-audit tooling (don't build new infra): ≥100k states = production-distribution replay (deck-seed + action-sequence via measurement_infra lossless replay) + adversarial synthetics (long/bifurcated boards near window edges, farm-heavy, endgame-K bands). Hard assertions: no dropped legal action (strict mode), no key collision with differing masks, no manifest drift mid-run. CPU-only, parallel W≤14 local when boxes free.

## 5. Runner + report
`scripts/release_audit.sh` → runs suite + replay, writes `measurement/release_audit_<date>/REPORT.md` (pass/fail per property, corpus sizes, hashes). Wire a one-line status into STATUS on completion. Re-run required after any leaf/search/config change that touches the champion (cheap by design).

## Out of scope (per adoption doc)
Full-board/no-crop rework, dynamic action head, representation changes — F1 only *measures and guards*; it changes no production behavior except the human-harness rewire and YAML fingerprint correction.
