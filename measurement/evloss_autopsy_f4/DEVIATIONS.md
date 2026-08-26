# DEVIATIONS — F4 (out-of-family judge) leg

Every departure from `R2_PREREG.md` §7 / `PLAN.md` §6, numbered and dated rather than
edited in silently. D-F4-0 … D-F4-8 were written **before** the blind commit and before any
tier1-greedy value existed; anything numbered D-F4-9 or higher is a run-time deviation and
carries its own timestamp.

---

### D-F4-0 — R2's F4 row names the check but not the arithmetic (2026-08-26, pre-commit)

`R2_PREREG.md` §7 says only *"`tier1-greedy` (out-of-family) agrees on **sign**, and the
category has a **leaf-computable predicate**"*. It fixes the judge, the corpus, the class of
test (sign, never magnitude) and the category set, and it fixes nothing else: not *sign of
what*, not a significance bar, not per-category vs family-wide, not the post-F4 verdict
vocabulary. `F4_PREREG.md` §§4–6 is that missing arithmetic, written by this leg and frozen
by the blind commit before any tier1-greedy value existed. §1 of that file marks, line by
line, which half is quotation and which half is completion.

### D-F4-1 — the sign check CANNOT be run on `R̄_champ` (2026-08-26, pre-commit)

`R_champ = max(0, D_leaf, …, D_sib4)` is **non-negative by construction**, so *"the
out-of-family judge agrees on the sign of `R̄_champ`"* is true for every judge including a
random one. A literal reading of F4 is therefore vacuous. The primary statistic is instead
the **same-arm cross-judge witness** `δ_i = D^T1(i, argmax_a D^clair(i,a))` — unclipped, so
its sign is a genuine test — which is also exactly the construction the 2026-07-28
`tier1-greedy` precedent used (re-score the same `(pick_a, pick_b)` pair out of family, read
the sign; `oracle_score_pilot` header §STATUS 2026-07-28 LATE). `R̄^T1_champ` is still
computed and reported per category, as a **map**, and `test_r_champ_t1_is_a_map_not_a_sign_test`
pins the non-negativity so no later reader mistakes its z-vs-0 for a sign test.

### D-F4-2 — the half-split witness is NEW; no parent prereg raises the confound (2026-08-26, pre-commit)

`a*_i` is selected on clair-puct values measured on the **same 32 CRN worlds** the tier1
judge re-uses, so world-luck that drove the selection is inherited by the evaluation:
**`δ̄` is biased upward, and CRN makes this worse, not better.** Neither `PLAN.md` nor
`R2_PREREG.md` raises this. F4 prices it with a **half-split** — select the arm on worlds
0–15 from the clair record, evaluate on worlds 16–31 from the tier1 record — which is
selection-unbiased and costs nothing (both judges already store `per_world_delta`). It is a
required conjunct of `F4-CONFIRMED`. **This is why the leg scores all four arms** rather
than only the argmax arm: `a†` (the half-split pick) can differ from `a*`.

### D-F4-3 — the `rnd` leg is re-purposed as the NEW judge's own instrument gate (2026-08-26, pre-commit)

`R2_PREREG.md` §5.2 labels `R_rnd` diagnostic-only *for per-category verdicts* (n = 200 is
too thin), and F4 keeps that fence. But `PLAN.md` §7's sanity gate — *"if an uninformative
arm is not worse than the champion, the instrument is broken, not the champion"* — has never
been applied to the **tier1-greedy** judge, which has never scored anything at this scale.
The `rnd` leg is therefore run and read **as gate g6 on the judge**, pooled, not as a
per-category statistic. It costs 200 of 2,838 position-legs.

### D-F4-4 — a pre-stated COST LADDER, not a fixed leg set (2026-08-26, pre-commit)

The tier1-greedy judge has never been priced at this scale (the only precedent is 30
positions on a different corpus). `F4_PREREG.md` §2.1 therefore fixes three rungs (L1 = 5
legs / 2,838 position-legs · L2 = drop `rnd` · L3 = witness-only, 800 rows) and a rule: the
smoke's **mean** worker-seconds per position picks the first rung whose projected wall is
≤ 6.0 h. **This reads no judged value — it is a cost gate, not an outcome gate.** L3 caps
the verdict at `F4-PARTIAL` because the half-split witness (a `F4-CONFIRMED` conjunct) and
every selection-free arm-level statistic need all four arms.

### D-F4-5 — `f4_judge_leg.py` re-expresses `04_run_r1.sh`, it does not source it (2026-08-26, pre-commit)

The R1 launcher's `common.sh` sources `config.env` + `config.local.env`, creates `state/*.done`
stage markers and carries `run_all.sh`'s SHARE-change guard. Sourcing it from F4 would put
R0/R1 stage state and the R1 sentinels in reach of this leg. `f4_judge_leg.py` is therefore a
self-contained python re-expression of `04_run_r1.sh` **plus** `r1_resume_clean.py`, with
every non-judge knob copied verbatim (positions files, `M=32`, salt
`evloss-autopsy-20260824-v1`, `walled`, `--strict-crn`, `--resume`, `nice 19`, wall cap
7200) and the same post-leg gate. It writes only under `<share>/judge_f4_tier1greedy/` and
its own sentinel. The R1 tree, the R2 artifacts, `funnel_holdout_split.json` and the
laptop-side D-L1 quarantine are read-only to it.

### D-F4-6 — the F7 buckets are ruled NOT leaf-computable (2026-08-26, pre-commit)

`R2_READOUT.json.funnel_gate.conditions.F4` asserts the predicate half is *"satisfied by
every pre-registered bucket by construction"*. That is not true of
`f7_cross_world_spread={low,high}`: cross-world argmax spread is a property of the
**champion's own search** (the k per-determinization root tables), not of the afterstate, so
a static leaf term cannot compute it without running the search. `f4_adjudicate.LEAF_COMPUTABLE`
rules both F7 buckets `False` and every other bucket `True`. **This changes no verdict** —
neither F7 bucket is among the 7 F1∧F2∧F3 winners — but the ruling is recorded rather than
inherited, and `test_f7_is_the_one_non_leaf_computable_axis` pins it.

### D-F4-7 — the F7 median cut is READ from the frozen R2 readout, not recomputed (2026-08-26, pre-commit)

`r2_taxonomy.main` computes the F7 median from the loaded rows. F4 instead reads
`R2_READOUT.json.coverage.f7_median_cut` (= 0.25) so category membership is bit-identical to
R2's **by construction** rather than by re-derivation, removing a float-ordering failure
mode. Gate g5 (all 32 estimable per-category clair means reproduced to `1e-9`) is what proves
the whole loader; on the banked corpus it reproduces the pooled mean and every category to
**exactly 0.0**.

### D-F4-8 — `--oracle-sims` is not passed (2026-08-26, pre-commit)

`ORACLE_POLICIES["tier1-greedy"]["uses_oracle_sims"] = False` — the greedy continuation is a
1-ply argmax with no search, and the pilot's own `--oracle-sims` help says it is IGNORED for
this policy. Passing R1's `100` would stamp a meaningless budget into the F4 manifests.
Everything else on the command line is R1's, unchanged.

---

### D-F4-9 — the smoke samples with a STRIDE, not a head (2026-08-26, post-blind-commit, pre-smoke)

Added after the blind commit `83dc92f2ea6e26eeba5fc7a8724842694a7f1e91` and **before any
tier1-greedy value existed**, so the blind property is intact: it is a sampling knob for the
cost probe, and it cannot see an outcome because there is none yet.

The positions files are sorted by `(deck_seed, ply)`, so `--head N` is all opening plies of
the lowest seeds. R1's own head-6 preflight probe averaged **71.0 s/position against a
realized leg mean of 123.0 s** — a 1.73× under-estimate, in the *opposite* direction to the
"worst-case opening" note the probe carries. `--stride` takes the N rows evenly spaced
through the file so the smoke spans every phase and every seed decile, and its mean is an
unbiased ETA input rather than one needing a fudge factor. Both the raw strided mean and the
head-anchored cross-check are reported.

### D-F4-10 — gate g2 read a manifest key the harness never writes (2026-08-26, post-smoke, pre-adjudication)

Found by the smoke, before any adjudication. `f4_adjudicate.manifest_gates` looked for a
**top-level `oracle_policy`**; `oracle_score_pilot.build_manifest` writes the policy at
**`oracle.policy`** and the engine at **`execution.backend`** (`oracle_policy` and
`backend_resolved` are per-position RECORD field names, not manifest ones). A perfectly
correct tier1-greedy manifest would therefore have failed g2 and stamped `F4-BROKEN`.

Fixed by reading the real key with the promoted spelling accepted as a fallback, and
**strengthened** while there: g2 now also requires the harness's own attestation
`oracle.policy_family` to start with `OUT-OF-FAMILY` — the harness stamping, in its own
words, that the judge is not in the champion's family. Two regression tests pin it
(`test_manifest_gate_rejects_a_manifest_with_no_policy_key_at_all`,
`test_manifest_gate_rejects_an_in_family_policy_family`).

This is the memory rule *"read the emitter before writing the parser — and before trusting
a field NAME"* firing exactly as designed. It touches a gate, not a statistic; no F4
category outcome had been computed when it was made.

### D-F4-11 — the smoke was run TWICE, at W=10 and at W=22 (2026-08-26, pre-launch)

The W=10 smoke measured **F4 = 0.501 × R1 per position on the same 10 rids**, flat across
every phase (0.454–0.550). That number cannot be read as "the tier1 judge is 2× cheaper":
it compares F4 at **W=10** against R1's banked leg at **W=22**, so it conflates judge cost
with contention. R1's own preflight (6 concurrent, effectively uncontended) averaged 71.0 s
against a realized W=22 leg mean of 123.0 s — i.e. **contention on this box is worth ~1.7×**,
which is the same order as the "saving". A second smoke at the production W=22 measures the
contended per-position cost directly, so the launch ETA rests on a measurement rather than
on a contention assumption. House rule: bench, then extrapolate, then commit.

