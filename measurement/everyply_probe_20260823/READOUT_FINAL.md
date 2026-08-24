# EVERY-PLY ROLLOUT ARBITRATION (SIZE-1) — FINAL READOUT (post-EP-D5 re-adjudication)

Run `everyply_probe_20260823` · design [`DESIGN.md`](https://github.com/) (blind commit `c946eae7`) ·
read-rule `READ_RULE.md` (same commit) · analyze code rev `414aa0d5` · corpus `champ449`.

Adjudicator: fresh session, has not previously seen κ̂/z_κ/per-stratum estimates before this
adjudication. Main tree LATCHED throughout — no commits, checkouts, or writes made to the repo;
all reads were `git show`/`git diff` (no working-tree mutation); this readout and all working
files live in scratchpad only.

---

## VERDICT

> # `E-UNRESOLVED`

Branch text, taken **verbatim** from READ_RULE.md §4, row 5 (the branch fired — first match in
read-order after E-HARM, E-CLEAN, E-FUND, E-FLATNULL all failed their conditions):

> | # | branch | condition | what it licenses |
> |---|---|---|---|
> | 5 | **`E-UNRESOLVED`** | anything else | **Nothing closes, nothing is licensed.** The read-out **MUST** print the `n` that would resolve the observed `κ̂` at the **realized** dispersion (the `tiearb` READ_RULE's own discipline). |

And the §0.A kill-only-interim rider (READ_RULE §0.A, binding, quoted because κ̂ is positive):

> ⚠️ **This is a declared limit of the funded size, NOT a discovered one, and it must not be
> narrated after the fact as "the probe found nothing positive."** A positive κ̂ at SIZE-1 is an
> *unresolved* reading, and the readout must say so in those words.

`E-FUND` (κ̂ ≥ +0.15 ∧ z ≥ +2.0 ∧ ≥2/3 strata ≥0 ∧ κ̂_holdout ≥ 0) and `E-CLEAN` (κ̂ ≥ +0.35 ∧
z ≥ +2.0 ∧ ≥2/3 strata ≥0) are **structurally unreachable at SIZE-1** per §0.A regardless of their
conjuncts' truth values — carried below only as the record of which conjuncts held.

**Branch-condition table (READOUT.json `adjudication.conjuncts`, all four candidate branches):**

| branch | condition | held? |
|---|---|---|
| `E-HARM` | κ̂ ≤ −0.15 ∧ z ≤ −2.0 | **NO** (κ̂ = +0.0135 le -0.15 → false; z = +0.122 le -2 → false) |
| `E-CLEAN` ⛔unreachable | κ̂ ≥ +0.35 ∧ z ≥ +2.0 ∧ ≥2/3 strata ≥0 | κ̂≥0.35 **false**, z≥2 **false**, strata≥0 count=2/3 **true** |
| `E-FUND` ⛔unreachable | κ̂ ≥ +0.15 ∧ z ≥ +2.0 ∧ ≥2/3 strata ≥0 ∧ κ̂_holdout≥0 | κ̂≥0.15 **false**, z≥2 **false**, strata≥0 **true** (holdout not needed to decide) |
| `E-FLATNULL` | UB95(κ̂) < +0.15 ∧ ¬E-HARM | UB95 = 0.2346 **≥ 0.15 → false** |
| **`E-UNRESOLVED`** | anything else | **FIRES** |

---

## 1. All §3 gates — realized value and address (10 named gates + the WITNESS)

Fail-closed, absent-is-fail. All PASS this run (contrast: the first adjudication attempt at
rev `f77aaa66` FAILED `G-KNOWNGOOD` and returned `U-UNREADABLE` — see §5 history below).

| id | ok | address that resolved it | realized |
|---|---|---|---|
| `G-KNOWNGOOD` | **true** | `probe_pickers.py knowngood` → `KNOWNGOOD.json['ok']==true`; `require_knowngood` pins `arb=+0.2065`, `N=733`, `n_roots=399`, tol 1e-9 vs `tiearb_20260816/READOUT.json`; roots threaded via `--knowngood-if-records`/`--knowngood-arb-records` (EP-D5 fix) | `rc=0`, reproduced `arb=0.20645928315484208`, `ora=0.2545233140066622`, `F=0.8111605962722847`, `n=733`, `n_roots=399`; all deltas `0.0` |
| `G-CRN` | **true** | `oracle_score_pilot._process` fields `crn_verified`/`checksum_ok`/`world_seeds`/`playout_seeds`; cross-leg via `run_tiletie.verify_leg_records`; cross-judge per rid | 0 integrity violations (arb + if), `compared_rids=307`, 0 seed mismatches |
| `G-COVER` | **true** (pass-always by design, declared acceptable in READ_RULE §3.1 since its only failure mode is a build defect) | `ARMS.json[rid]['champ_pos']==0` and `arm_order[0]==champ_action` | `champ_not_arm0=0` of 450 |
| `G-ARMSET` | **true** | IF arm list is an order-preserving subset of the ARB arm list per rid; both folds' `a_arb` were actually priced | `not_a_subset=0`, `order_disagreement=0`, `a_arb_not_priced=0` |
| `G-ZEROFILL` | **true** | `n_priced + n_zero == n_analysed`; every zero-filled rid has exactly 1 arm to price | `307 + 143 == 450`; `singleton_ok=true`, `zerofill_defect=0` |
| `G-DISTINCT` | **true** | `n_dropped_lt2_distinct / n_planned <= 0.10` | `0 / 450 = 0.0` (bar 0.10) |
| `G-FRAME` | **true** | `max_abs_f_deviation_pp <= 3.0`; `population_weights_w == census w` | `0.111 pp` (≈27× margin); `w_plan == w_census` bit-identical (A .0997/B .4290/C .4713) |
| `G-N` | **true** | `n_analysed >= 340` | `450 ≥ 340` |
| `G-EPOCH` | **true** (dialect-named per READ_RULE §3.1's ⚠️ SHARPENED row — a literal string gate would be fail-always) | `champ_leaf_hash == a36d2e15a3b3d71d` (harness dialect); `rules_profile == walled` | leaf hashes seen: `{a36d2e15a3b3d71d}`; profiles seen: `{walled}` |
| `G-CHAMP` | **true** | resolved `fair_deploy.k_dets`/`.sims_per_det` + `tiearb` block, stamped per row, constant | `k_dets={8}`, `sims_per_det={1376}`, `tiearb={"B":64,"J":4,"enabled":true,"eps":0.0,"mode":"argmax","salt":"tiearb2-deploy-v1"}` |
| `G-BLIND` | **true** | commit introducing DESIGN+READ_RULE precedes first pricing leg; `BLIND_COMMIT` matches; §4 byte-identical since | `blind_commit=c946eae78abf...`, `revisions_since_blind_commit=0`, `problems=[]` |
| `WITNESS` (READ_RULE §1, never a branch input) | **true** | from-scratch recompute of κ and cluster sandwich, independent of `analyze_tiletie` | analyser κ=0.013517910014821369 / witness κ=0.01351791001482137 — agree to tol 1e-9 |

**Independent cross-checks performed this session** (not merely re-reading the JSON):

- `per_position.jsonl` scanned directly: `priced=307`, `zero=143`, `total=450` — matches `G-ZEROFILL` exactly.
- Stratum counts recomputed from `gap_stratum` field: `A=112`, `B=169`, `C=169` — matches `per_stratum.*.n` exactly.
- Unique `root_id` count recomputed: `311` — matches `n_roots` exactly.
- `KNOWNGOOD.json` read directly: `ok=true`, `arb/ora/F` deltas all `0.0` against `tiearb_20260816/READOUT.json`.
- The first (pre-EP-D5) adjudication's own independent from-scratch recompute (in `SIZE1_READOUT_DRAFT.md` §5, done a *third* way — hand-rolled `cluster_robust`, not imported) reports bit-identical κ̂/se/z/sd to the analyser's own witness. Cited, not re-derived here.

---

## 2. The statistics, with uncertainty (READ_RULE §4.3 A, all required prints)

**Primary (READ_RULE §1):**

```
kappa_hat = +0.013517910014821369   pts per non-tied tile ply, root seat
se        =  0.11051875949025253    cluster-robust on root_id := game_id
z_kappa   = +0.12231326226579312
UB95      = kappa_hat + 2.0*se = +0.23455542899532641
n_analysed = 450  (n_priced 307 + n_zero 143)   n_roots = 311
bootstrap 95% (roots, 20000 reps): [-0.2029, +0.2309]
sd(positions) = 2.2849966719045938
```

⚠️ **Currency (READ_RULE §4.3 A rail 5, printed verbatim as required):** `scale_all ≡ 1.0`.
**κ is NOT directly comparable to the tied-ply `arb = +0.2065`** — that number is
`scale_all`-scaled and this one is not (its unscaled discriminable sibling is +0.2844).

**Per-stratum (all three labelled UNDERPOWERED — SIGN READ AT BEST, per READ_RULE §4.3 A.2):**

| stratum | gap band | n | n_roots | κ̂_s | se (within, no reweight penalty) | z |
|---|---|---:|---:|---:|---:|---:|
| A — near-tie | 0<gap≤0.25 | 112 | 106 | +0.1677 | 0.1997 | +0.840 |
| B — mid-gap | 0.25<gap≤1.5 | 169 | 146 | +0.2119 | 0.1720 | +1.232 |
| C — clear-gap | gap>1.5 | 169 | 152 | −0.1997 | 0.1676 | −1.192 |

2 of 3 strata read non-negative (A, B); C reads negative. None individually clears |z|=2.

**`q` (pickchg), realized (READ_RULE §4.3 A.3):**

```
pooled  = 0.6822222222222222     (planning-central was 0.76)
fold1   = 0.5288888888888889     fold2 = 0.5288888888888889
by stratum: A=0.75, B=0.7338, C=0.5858
```

Realized `se` at this `q`: 0.11051875949025253 (realized, includes the §2.3 reweighting price
inside `w_scale`). Planning-se at realized (n,q): 0.07476543726083235 (a **planning** figure,
not double-penalized).

**`phi_nontied`:** 25.624 non-tied plies/game after dedupe (12.812 per game per seat); kept
fraction after dedupe = 1.0 (0 positions dropped, consistent with `G-DISTINCT`).

**`n_cell` — implied game-cell size at both NA ends (READ_RULE §4.3 A.4):**

| NA | pts/game | elo image | n_cell |
|---|---:|---:|---:|
| 0.31 (conservative) | +0.0537 | +0.42 | 528,533 |
| 0.85 (optimistic) | +0.1472 | +1.15 | 70,300 |

Both are absurd relative to the corpus's own maximum constructible supply (449 games × cap 2 =
898 positions) — this is the mechanical face of "unresolved," not a rounding artifact.

**`n` that would resolve the observed κ̂ at the realized dispersion (READ_RULE §4.3 A.5, required
on `E-UNRESOLVED`):**

```
n = 120,316.56  ->  n_ceil = 120,317 positions
```
(such that |κ̂|/se(n) = 2.0 at the realized dispersion, se(n) = se_realized·√(n_realized/n)).
⚠️ A top-up is a **fresh owner funding decision** (DESIGN §5.4), and 120,317 positions vastly
exceeds the corpus's maximum constructible supply of 898 — this screen's own arithmetic states
plainly that *this exact κ̂* cannot be resolved by any top-up of this corpus; only a much larger
realized effect (or a different corpus) could clear 2σ affordably.

**`κ̂_holdout` (READ_RULE §4.3 A.6 — reported on every branch, conjunct only for E-FUND, which
cannot fire at SIZE-1):**

```
mean = +0.1808449074074074   n = 108 positions, 75 roots
se_cluster = 0.22838766214674697   se_boot = 0.22542410107518251   z = +0.7918
boot 95% [-0.2655, +0.6205]   frac(boot <= 0) = 0.2106
reads_before_decision = 0
```

Positive, sub-2σ, and **inert** — the conjunct it belongs to (E-FUND) cannot fire at SIZE-1.

**Arm-builder, dedup, code/config (READ_RULE §4.3 A.7–8):**

- Arm-builder that ran: **`leaf_topk`** — the §3.1 pre-committed fallback (pooled-Q unreachable
  through the rust seam), per the pre-freeze orchestrator ruling stamped in both DESIGN.md and
  READ_RULE.md's banner.
- Distinct-afterstate drop: 0 / 450 (rate 0.0), well inside the 10% `G-DISTINCT` bar.
- Resolved champion: `fair_deploy` k_dets=8 × sims_per_det=1376 (11,008-sim PUCT); `tiearb`
  `{B:64, J:4, enabled:true, eps:0.0, mode:argmax, salt:tiearb2-deploy-v1}` — constant across all
  450 rows (`G-CHAMP`); leaf hash `a36d2e15a3b3d71d` (harness dialect of the corpus games'
  `6dfffd57051690f2` runtime dialect — same leaf, named per `G-EPOCH`'s ⚠️ SHARPENED row); rules
  profile `walled`; band `28000000000`; corpus `champ449`; code rev `414aa0d5`.

---

## 3. The honesty rails — all nine, verbatim (READ_RULE §4.3 B, required on every branch)

1. **PRIOR-AGAINST 1 — the mass desert.** No gentle widening exists between exact ties and
   eps≈1.5–2.0: 90% of non-tied tile plies sit above a quarter-point of leaf preference. The plies
   this probe adds are ones where the leaf has a real opinion.
2. **PRIOR-AGAINST 2 — "the vart".** Tie-triggered search escalation died at its pre-gate
   (E-FLAT): more search moves tied-ply picks but does not improve them. At a non-tied ply the
   arbiter must beat an 11,008-sim PUCT search, not silence.
3. **PRIOR-AGAINST 3 — the RND control.** Stage-2's matched-compute control read −4.4287 pts/game
   (−60.09 elo): a leaf-tied set is not a set of interchangeable moves, and the champion's own
   tie-break is far better than arm-average.
4. **INCUMBENT ASYMMETRY.** The champion's pick IS one of the arms; κ is capture-vs-incumbent and
   negative-capable; κ=0 means "no better than the champion," not "no signal."
5. **CURRENCY.** `scale_all ≡ 1.0`; κ is NOT directly comparable to the tied-ply `arb=+0.2065`.
6. **OFFLINE CAPTURE HAS UNDER-READ THE GAME CELL ON THIS EXACT AXIS.** At tied plies the offline
   instrument returned P-PARTIAL with a negative blind holdout (−0.0051), yet the Stage-2 game
   cell fired G-CONFIRMED at z_D +8.04. ⇒ E-FLATNULL (had it fired) would be a funding verdict,
   never an exclusion — and this run didn't even reach E-FLATNULL.
7. **BUDGET-EPOCH MISMATCH.** Corpus games were generated by the k4×688/2752-budget champion; the
   incumbent priced is whatever PRODUCTION.yaml resolves at run time.
8. **NO DEPLOY IS LICENSED ON ANY BRANCH.** `rho_phone`=5.520 at B=16 is unsolved for the tied-ply
   arbiter already; every-ply arbitration roughly doubles the fire rate and therefore roughly
   doubles it again. Desktop-only at best.
9. **`SEC-ARB` is circular by construction** and may never be a branch input (not computed here).

**Scope fence (DESIGN §4.5, binding, restated):** a near-tie-only deployment would need
κ_A ≥ 1.38/(1.277×0.31) = 3.49 pts/ply against a tied-ply oracle ceiling of +0.2545 — ~14× the
entire oracle headroom of the adjacent ply class. **No branch, and no successor design, may rescue
a pooled null by carving out stratum A, a phase bucket, or any other sub-population** — and this
run's own stratum C read (−0.1997) is exactly the kind of number that fence exists to keep from
being cherry-picked away.

**Governance (READ_RULE §0 / §5, restated):** 0 games on this branch. No `results.csv` row, no
deck band, no `BAND_REGISTRY.csv` entry, no claim id, `PRODUCTION.yaml` untouched — regardless of
outcome. No branch here authorizes SIZE-2/SIZE-3 — a top-up is a fresh owner funding decision.

---

## 4. Byte-identity witness (STEP 1)

```
$ git diff c946eae7..414aa0d5 -- measurement/everyply_probe_20260823/DESIGN.md \
                                  measurement/everyply_probe_20260823/READ_RULE.md
(empty — exit 0)
```

**Confirmed EMPTY.** The frozen pair (DESIGN.md + READ_RULE.md) is byte-identical from the blind
commit `c946eae7` through the analyze-stage rev `414aa0d5` — i.e. across every one of EP-D1
through EP-D5. No execution-layer fix touched the pre-registered text.

Independently triple-confirmed this session (not merely trusting the diff):

```
git show 414aa0d5:.../READ_RULE.md | sha256sum = fd3b873a...18cf8
git show 414aa0d5:.../DESIGN.md    | sha256sum = cec01c1c...aaa0
```
Both match the `local_shas.txt` sha256 list generated when the pair was fetched off the laptop
share for the (first, U-UNREADABLE) adjudication attempt at rev `f77aaa66` — i.e. the committed
git blob, the laptop's on-disk copy, and this session's independent re-derivation all agree
bit-for-bit.

`G-BLIND`'s own realized payload corroborates from the harness side: `revisions_since_blind_commit
= 0`, `problems = []`, `section4_bytes = 7426` (constant).

---

## 5. EP-D1..D5 deviation table (execution-layer only; BLIND_COMMIT unchanged throughout)

All five are launcher/builder/analyzer **execution-layer** fixes made **statistics-blind** (zero
priced legs existed at each fix time), on branch `everyply-freeze`, per the standing
instrument-fix doctrine (READ_RULE's own "the session that writes the fix must not have seen κ"
rule, carried from the jcz precedent).

| id | sha | what | statistics-blind? |
|---|---|---|---|
| EP-D1 | `9ab8be07` | route `--arm-builder leaf_topk` into `stage_corpus` argv per the pair's own §3.1 pre-committed fallback ruling (rust backend exposes pooled N, not Q) | yes — pre-launch |
| EP-D2 | `49ee9183` | `stage_pilot()` missed the same argv fix; pilot fail-closed at builder preflight (0/20 coverage, DESIGN §12 ABORT); fix = argv parity + rc fail-close parity with sibling stages (previously a false-success sentinel) | yes — failed pilot ran 0 legs, archived at `failed_pilot_20260823_rev9ab8be07/` |
| EP-D3 | `cd9cfd79` | `check_arm_builder_backend()` read nonexistent attributes off the `Execution` dict-subclass (`.rust_threads`/`.source`); latent, unreachable before EP-D2; 2-line fix + real-`Execution` test added (118/118 pass) | yes — second failed pilot archived at `failed_pilot_20260823_rev49ee9183/` |
| EP-D4 | `f77aaa66` | full launch refused at pre-flight `G-KNOWNGOOD`: `probe_pickers.py` hardcodes `DEFAULT_IF_RECORDS` on the local-box share path; fix = thread `--if-records`/`--arb-records` from the launcher's existing role-resolved `$SHARE` var; audited all 7 box-specific-path sites (2 live/fixed, 5 dead-from-launcher) | yes — zero legs had run; smoke reproduced the published arb F bit-exact (Δ=0.0) both locally and on the laptop |
| EP-D5 | `414aa0d5` | **first full adjudication attempt (rev f77aaa66) returned `U-UNREADABLE`**: `analyze_everyply.py` internally re-invokes `probe_pickers knowngood` at a SECOND call site EP-D4 didn't cover (same hardcoded-local-share-path bug class); fix threads the same records-root args at that call site, aligned to the frozen READ_RULE's documented gate address | yes — the fixing agent + orchestrator were both disqualified from adjudicating (had seen the quarantined U-UNREADABLE numbers); a fresh statistics-blind agent wrote the fix; the fresh session reading this readout is the first to read the resulting statistics |

Every deviation confirmed via `git show -s --format="%H %ci %s" <sha>` this session; commit
messages self-declare statistics-blindness. `git diff c946eae7..414aa0d5` for the frozen pair is
empty (§4 above), so none of the five touched pre-registered text.

**Pattern note carried from the deviation draft:** EP-D2's rc fail-close is what made EP-D3 loud
instead of a silent false success — the guard-parity fix paid for itself on the very next run.

---

## 6. Data provenance

**Record roots (share, laptop box):**

```
arb: /mnt/c/carc-shared/everyply_probe_20260823/arb/chunk{1..4}/tier1-greedy::walled/leg{1..3}
     (12 leg dirs, 112/111/111/113/113/113/112/112/112/113/112/112 records = 1348 total)
if:  /mnt/c/carc-shared/everyply_probe_20260823/if/chunk{1..4}/clair-puct::walled/leg{1..2}
     (8 leg dirs, 81/17/74/22/76/19/76/21 records = 386 total)
```

**Sha-verified input list (fetch performed for the first, U-UNREADABLE, adjudication attempt at
rev `f77aaa66`; `local_shas.txt` in the fetch dir, sha256 of each file):** `BLIND_COMMIT`,
`DESIGN.md`, `READ_RULE.md`, `FRAME.json`, `PLAN_SUMMARY.json`, `HOLDOUT_GAMES.json`,
`KNOWNGOOD.json`, `READOUT.json`, `READOUT.md`, `per_position.jsonl`, `SELECTION.jsonl`,
`RUN_MANIFEST_pilot.json`, `RUN_MANIFEST_{arb,if}_chunk{1..4}.json`, `ZEROFILL_chunk{1..4}.json`,
`logs/all.log`, `logs/analyze.log` — 27 files, all sha256-recorded.

**Cross-run identity confirmed this session (the load-bearing check for step 4):**

```
sha256(everyply_fetch/per_position.jsonl)     = ac0192b4...d1d8b
sha256(ep-d5-reanalyze2/per_position.jsonl)   = ac0192b4...d1d8b   <- IDENTICAL
diff of the two files: empty (450/450 lines identical)
```

**This is the strongest available provenance statement: the EP-D5 re-analyze consumed the
byte-identical 450-position corpus that the first (`U-UNREADABLE`) adjudication attempt already
fetched and sha-verified off the laptop share.** No leg data was regenerated, re-drawn, or
re-priced between the two adjudication attempts — only the `analyze_everyply.py` `G-KNOWNGOOD`
call site changed (EP-D5), and only the gate's own pass/fail flipped as a result.

**RUN_MANIFEST provenance for the underlying legs** (git_clean checks stamped at leg-generation
time, before EP-D5 existed): pilot manifest stamps `git_rev=cd9cfd79dc`, `git_clean.ok=true`,
`dirty_paths=[]`; arb-chunk manifests stamp `git_rev=f77aaa6690`, `git_clean.ok=true`,
`dirty_paths=[]`; all stamp `leaf_hash.ok=true` against the expected `a36d2e15a3b3d71d` and a
passing `gate_oracle_pilot_backend.py` backend-parity recheck (376 field checks, 0 mismatches) at
each chunk.

### ⚠️ FLAGGED, NOT RESOLVED — step 4 admissibility check

Per the task's step 4, the frozen text was checked for anything that would make a *scratchpad/
worktree-run* analyze inadmissible. Findings, flagged rather than resolved:

1. **The frozen pair is silent on adjudication-time execution location.** `G-BLIND`'s address text
   governs only the ordering of the DESIGN/READ_RULE commit relative to the first pricing leg, and
   requires §4 byte-identity (both independently confirmed, §4 above). Nothing in READ_RULE.md or
   DESIGN.md's §11 gate summary says the `analyze` stage must run from the main-tree `HEAD`, or
   from any particular working copy, to be adjudicable.
2. **DESIGN §6.3's "Neither may be built in the MAIN TREE while a run is live" clause governs the
   *build* of the two owed scripts** (`build_everyply_corpus.py`, `analyze_everyply.py`) at
   drafting time, when a `reconcile_backend` run was live — it is not a statement about where a
   completed script may later be *invoked* to re-adjudicate banked records. It is the closest
   textual match to a worktree-isolation rule in the pair, and it does not on its face reach the
   EP-D5 re-run.
3. **No RUN_MANIFEST-style `git_clean`/`git_rev` stamp is visible for the EP-D5 analyze invocation
   itself** (only for the earlier pilot/arb/if leg-generation runs, at `cd9cfd79`/`f77aaa66`). The
   `code_rev: "414aa0d5"` field in `READOUT.json` is the only self-reported execution-rev evidence
   for the analyze step; this session corroborated it independently by confirming (a) `414aa0d5`
   is a real, checked-in commit on `everyply-freeze` whose diff against the frozen pair is empty,
   and (b) the analyze step's *input* (`per_position.jsonl`) is byte-identical to the independently
   sha-verified banked corpus. Neither of those substitutes for a first-party git-clean stamp at
   analyze time, which this session could not locate.

None of these three items caused this adjudicator to withhold or discount the verdict — the
corroborating evidence assembled independently (byte-identical inputs, byte-identical frozen text,
a real commit on the pre-registered branch) is strong circumstantial provenance even without a
first-party manifest for the analyze step. They are named here per the task's explicit
"flag, don't resolve" instruction, for a future statistics-blind session to close if the
close-out checklist calls for it.

---

## 7. History (one paragraph)

The SIZE-1 every-ply probe launched at rev `f77aaa66` (attempt 4, after EP-D1..D3 fixed three
earlier execution-layer defects in the launcher/builder, all statistics-blind) and completed all
four chunks, but its **first adjudication returned `U-UNREADABLE`**: 10 of 11 §3 gates passed, but
`analyze_everyply.py`'s own internal `G-KNOWNGOOD` re-invocation failed at a second, previously-
unaudited hardcoded-local-share-path call site (the same bug class EP-D4 had just fixed at the
launcher's pre-flight call site, one level up) — a real, mechanical gate failure that the first
adjudicator correctly read as `U-UNREADABLE` per READ_RULE's unconditional "ABSENT IS FAIL." That
adjudicator, having seen the quarantined κ̂/z_κ/per-stratum numbers, was disqualified from writing
the fix; a fresh statistics-blind agent applied **EP-D5** (`414aa0d5`) — threading the same
records-root arguments into the analyze-stage call site — and re-ran `analyze_everyply.py` locally
against the identical, already-sha-verified banked corpus (confirmed §6 above: byte-identical
`per_position.jsonl`, 450/450 lines). This fresh adjudication, reading the EP-D5 outputs for the
first time, finds all 11 gates PASS (including `G-KNOWNGOOD` now, `rc=0`) and fires **`E-UNRESOLVED`**:
κ̂ = +0.0135 pts/non-tied-ply (se 0.1105, z +0.122) is neither harmful enough for `E-HARM` nor low
enough for `E-FLATNULL`'s marginal bar, and is far below the unreachable-at-SIZE-1 `E-FUND`/`E-CLEAN`
thresholds — so nothing closes and nothing is licensed; a top-up remains a fresh owner funding
decision, and the corpus's own maximum constructible supply (898 positions) is roughly 134× short
of the ~120,317 positions that would resolve this exact κ̂ at 2σ.

---

## What this readout does NOT do (READ_RULE §5, restated)

No branch here flips `PRODUCTION.yaml`. No branch licenses a leaf, search, `B`, `M`,
`--oracle-sims`, or arbiter change. No branch re-rates the champion. No branch licenses an
on-device or desktop deploy. No branch writes a strength row to `experiments/results.csv`. No
branch claims a deck band or touches `BAND_REGISTRY.csv`. No branch authorizes SIZE-2 or SIZE-3 —
a top-up is a fresh owner funding decision, re-priced by the measured `q` (0.6822, below the
planning-central 0.76). No branch licenses a near-tie-only or other sub-population deployment.
