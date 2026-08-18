# REVIEW_R1 — adversarial review of DESIGN.md/READ_RULE.md draft (commit e788b143)

Reviewer: independent agent, read-only, verified every witness address against the
actual emitters (scripts/tiletie/ at main-tree HEAD; W1 build merged at 7b82610f).
Status: 21 defects. The drafter must fix ALL VOIDS/WRONG-NUMBER/AMBIGUOUS-BRANCH
items and address every PROCESS-RISK before the pair can merge and become binding.

## VOIDS-A-HEALTHY-RUN

1. G-DISJOINT primary address fictional, no fallback. READ_RULE names
   GATE_DISJOINT.json::{ok, overlap_counts, strata_root_overlap}; the emitter
   (gate_disjoint.py:143-181) writes {gate, goal, disclosure_policy, inputs,
   layers{a_root_id,b_rid,c_position_digest}.n_intersection, sha256_*, n_layers_violated,
   passed}. `strata_root_overlap` exists nowhere. Also run_gate compares exactly TWO
   ARMS.json corpora while the gate demands four comparisons, and EXCLUDE_RIDS_all.txt
   is a rid txt that load_rids will raise on. FIX: re-address to passed /
   layers.<layer>.n_intersection; spec W5 to emit ONE merged GATE_DISJOINT.json with
   comparisons:{<name>:{...}} + strata_root_overlap int; write that shape into the rule.

2. G-BITEXACT@HEAD: wrong path + 3/5 key spellings wrong, no fallback. Emitter
   verify_tier1_rust.py writes {gate:"G-BITEXACT", pass, n_playouts_compared,
   n_value_bit_identical, n_value_mismatch, legal_mask_cache, git_rev} and HARDCODES
   OUT_PATH = measurement/tiearb2_stage2_20260817/BITEXACT.json (no --out flag) —
   can never appear at RUN/GATE_BITEXACT_HEAD.json. FIX: add --out (pre-run, before
   band claim) and correct spellings, or address the real path/spellings.

3. G-PREFIX unsatisfiable on primary AND fallback. Real manifest key is
   preflight.seeds (one level deeper); preflight_seeds() returns {ok, salt, m,
   prefix_stable_at, derivation, probe_rid, probe_world_seeds_head,
   probe_playout_seeds_head}. `prefix_ok` exists NOWHERE in the repo; only a 4-entry
   head for a synthetic probe rid is emitted, not 32 entries of run rids. Also
   under-scoped: must hold to 128, and the emitter already asserts ladder
   [1,2,4,8,16,32,64,128] fatally. FIX: address preflight.seeds.{ok,prefix_stable_at};
   conjunct = ok==true AND prefix_stable_at ⊇ {1..128 ladder} at m=128.

4. G-UNCAPPED "arms == arms_full" fails ~16% of rids BY DESIGN: build_positions
   resolve_champion_arm APPENDS the champion pick when its transposition rep isn't in
   the arm list (measured champ_outside_tieset 17.3% / 15.6% on the two banked
   corpora; rust does the identical append — intended behaviour). FIX: restate as
   set(arms_full) ⊆ set(arms) AND cap_j is null (or the exact prefix+append identity).

5. c-remeasure reads the wrong key AND the HALT is bidirectional. DESIGN names
   SMOKE_MANIFEST_S1.json::worker_secs_per_playout — the wall×W figure the emitter's
   own banner says NOT to cost from (inflated ~1.9×); figure of record is
   c_worker_secs_per_playout. A healthy smoke would HALT. Also two-sided HALT fires
   on legs that come in CHEAPER (gen leg already conceded ~2.25× conservative).
   FIX: name c_worker_secs_per_playout; HALT one-sided (only when costlier >25%).

6. Rung 2 branch table NOT TOTAL: the interval [2σ_realized, 0.040) with z(arb_64)≥2
   fires NO branch (live hole given corrected se → 2σ≈0.0357 < 0.040 floor); NaN/
   degenerate se also falls off the table. FIX: add W-INCONCLUSIVE catch-all row 5 =
   "none of 1–4" (and/or repair row 3/4 conjuncts).

## AMBIGUOUS-BRANCH

7. Rung 3: the symmetric below-1.244 hole is open — Δ_ora significant AND
   upper(CI(R_ora)) < 1.244 lands in X-INCONCLUSIVE ("do not adjudicate") though it
   is a resolved value below BOTH predictions, and it is the branch MOST likely to
   fire. FIX: add X-BELOW (triggers I6 amendment with measured R_ora as number of
   record; flags both predictions as over-statements).

8. Two different significance tests for the same quantity: rows 1–3 use point/se
   (Δ_ora ≥ +2σ), row 4 uses percentile-bootstrap CI membership — a skewed bootstrap
   can fire X-CONFIRMED while the CI straddles zero. FIX: define significance ONCE via
   lower(CI95(Δ_ora)) > 0 in rows 1–3 (≤ 0 in row 4); drop the 2σ conjunct from the
   table.

9. X-FREE unreachable at the pessimistic end of the design's own sd bracket
   (at sd_Δ=1.4 it requires a strictly negative point estimate). FIX: state
   reachability; require the read-out to print whether X-FREE was attainable at the
   realized se; or reframe as an equivalence test vs a committed δ independent of se.

10. R_ora has no degenerate-denominator branch (ora_J4 ≤ 0 / replicates crossing
    zero ⇒ ratio CI meaningless). FIX: pre-branch guard — if lower(CI95(ora_J4)) ≤ 0,
    R_ora unreported; rung 3 adjudicates on Δ_ora alone via a committed sub-table.

11. G-DRAW recompute compares wrong objects: _seeded_cap returns (kept, capped,
    dropped) WITHOUT the reference; subset_j4 = [ref] + sub_j4; candidates is
    arms_full[1:]. FIX: identity = [arms_full[0]] + _seeded_cap(rid, arms_full[1:],
    4)[0] == subset_j4.

## WRONG-NUMBER

12. se(Δ(16→64)) does not reproduce: stated model (T=0.19, N=15.4, E=64, n=1350)
    gives se=0.01786, not 0.0198–0.0203 (back-solve implies T≈0.30). E=16 validation
    actually lands 0.02922 (better than the draft claims). z-column is internally
    consistent with se=0.0200; verdicts unchanged at corrected se. FIX: state the
    actual T (≈0.30) or correct se to 0.0179 and re-derive the floor; DESIGN §6 and
    READ_RULE §3 must carry the same number (note: interacts with defect 6's hole).

13. "1.244 resolved: yes (marginal at sd 1.4)" is FALSE at the bracket top:
    0.0842/(1.4/√1100) = 1.9947 < 2.0. FIX: "yes at sd ≤ ~1.39, NO at sd 1.4";
    add to the §11.7 blind-spot list. (All other rung-3 arithmetic reproduces.)

14. Cost roll-up: CLEAN — every leg re-derived and reproduces exactly (total
    1,172.2 wh; ETA 26.4 h). No fix.

## PROCESS-RISK

15. DESIGN §4's instrument-invocation block, run literally, builds the WRONG corpus
    then crashes: missing --e4-dir ''/--limit-e4-games 0/--bank-path ''/--limit-bank 0
    (no --no-e4 flag exists — e4+bank rows would pollute the fresh-band disjointness
    argument); missing --champgames-path (defaults to the SPENT corpus!); missing
    --n-champgames (default 1200 truncates below S1's 1400); PHASES 1/3/4 of the
    working precedent build_tiearb2_corpus.sh absent (collect_action_logs+band verify;
    the shadow-root transposition/afterstate map — without it build_positions silently
    globs the SPENT corpus's map; champ_picks — without --champ-picks the S1 build
    raises KeyError on row 1). FIX: replace §4's block with a pointer to a W6 driver
    that is a parameterised copy of build_tiearb2_corpus.sh (5 phases, empty-stand-in
    switches, shadow-root step), reviewed before band claim.

16. Manifests/legs not written where the rule reads them: bare relative
    --manifest-out paths (CWD-relative) and legs on the share with no copy-back to
    RUN/ — every per-leg fallback address points at a path that won't exist. FIX:
    absolute paths under RUN/; re-address the leg tree at the share or add an rsync
    step to §9's artifact list.

17. Four per-leg fallback keys one level off: config.world_seed_salt →
    resolved_config.world_seed_salt; config.m → resolved_config.m; legal_mask_cache →
    resolved_config.legal_mask_cache; G-LEAF fallback hash key is harness_leaf_hash.
    FIX: correct spellings.

18. G-CRN: run_smoke is single-judge; "both judges" needs TWO smokes and both write
    the SAME --smoke-manifest path (second overwrites first). crn_witness is a
    per-RECORD field, not leg-manifest; only n_ok/n_crn_verified exist there. FIX:
    per-judge smoke manifests SMOKE_MANIFEST_S1_<judge>.json; primary witness at
    READOUT::widening.gates.crn.witness_kinds (W3), per-record jsonl fallback.

19. G-BAND addresses have no emitter; the working analogue is
    CHAMP_GAMES_VERIFY.json::{band_ok, seed_band, n_games_realized, n_out_of_band,
    n_duplicate_seeds, sha256_of_sorted_seeds} which deliberately emits a DIGEST not
    seeds_used (disclosure-discipline choice the draft's fallback reverses). FIX:
    address the analogue's spellings (or commit W6 to the new spelling pre-claim);
    drop seeds_used.

20. Mid-run main-tree writes (the exact JCZ failure): verify_tier1_rust writes into
    the CLOSED tiearb2_stage2 run dir (tracked); WORKERS.conf inside the frozen
    prereg dir is a tuning knob (any W retune = mid-run edit to a frozen file);
    W2/W3/W5/W6 edit scripts/tiletie in the main tree behind a live run contra the
    worktree-isolation rule. FIX: new DESIGN §"freeze and sequence": (a) all W-code in
    a worktree, merged in ONE commit at a quiet window BEFORE the blind DESIGN/
    READ_RULE commit; (b) --out on verify_tier1_rust into RUN/; (c) WORKERS.conf
    outside shared_run/ (or frozen + retunes as numbered §7 deviations).

21. The c-remeasure obligation cannot measure the generation leg it cites (§12.7's
    990-vs-440 resolution names §7, but §7's mechanism prices judge playouts only) —
    the largest single line-item disagreement is never checked. FIX: separate timed
    generation smoke as its own pre-run step, or record accepted-over-budget.

## Dimension verdicts (summary)

- Gates that DID check out: G-SALT, G-M, G-BACKEND, G-LEAF primary, G-DRAW size
  identity, G-COMPLETE thresholds. G-ARMS/G-COMPLETE/G-REPLICATE are contingent on
  W3 being built to those exact spellings — state that as a pre-run acceptance test.
- Blindness: smoke is outcome-free by construction (verified field-by-field). ONE
  contradiction: §"gate-fail prints gate inputs only" vs G-REPLICATE whose gate
  inputs ARE z-statistics — a G-REPLICATE failure must print the z's it forbids.
  FIX: report G-REPLICATE PASS/FAIL only, z's to a sealed file, or move it to a
  non-adjudicating §5 rider. Also state explicitly that G-REPLICATE conditions BOTH
  rungs on the shared cell (one shared dependency, not two confirmations).
- W4/I7: core argument SOUND — both draws force-include the reference and draw j−1=3
  uniformly without replacement from an identically-ordered list (verified in
  tiearb.rs:293-311 vs _seeded_cap): same marginal law at j=4; deployed seed omits j
  so nesting holds there. TWO additions required: (a) the instrument draw is NOT
  nested in j (random.sample switches algorithms on k vs n; the build_positions
  docstring's "pure function… at every J" implied-nesting claim is FALSE — harmless
  at j=4, FATAL to any future J=8 sub-read; write that into I7); (b) the load-bearing
  unverified conjunct is the DEDUPE PARTITION (rust string_representation vs python
  afterstate map) — if the partitions differ the draws are over different supports.
  I7 must read "licensed CONDITIONAL on the python and rust afterstate-dedupe keys
  inducing the same partition of the tie set, which this run does not verify"; fund
  D-DRAW as the reported non-adjudicating magnitude of that conditional.
- COSMETIC: DESIGN §156 salt-table order tiletie-cap|20260812|rid vs code
  tiletie-cap|<rid>|20260812 — fix the spelling in a document whose thesis is
  spellings.

## Note
The W1 merge commit is 7b82610f (the wiring), not 29f3edce (the CI promotion).
