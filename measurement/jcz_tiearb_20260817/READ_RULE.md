# READ_RULE — JCZ out-of-lineage pricing of the tie arbiter

> **⚠️ BLIND ORDERING. This file is committed BEFORE the band is claimed, BEFORE game 1, and
> BEFORE any statistic of any kind exists.** Its git commit is the proof. The branch that fires
> is taken **VERBATIM**, whatever it is. No owner call adjudicates any outcome; the owner's
> authorization ("lets do jcz") funds the cell and does not name its answer.
>
> Design: [`DESIGN.md`](DESIGN.md). Run id `jcz_tiearb_20260817`.

---

## §0 — STANDING RULINGS CARRIED IN FROM STAGE 2

These are **inherited**, not re-decided. Each names its origin commit in
`measurement/tiearb2_stage2_20260817/READ_RULE.md`.

**§0.A — the wall-clock waiver (from Stage-2 §0.D, an OWNER RULING).** Owner, verbatim:
*"we can afford some wallclock during play, especially if its not every tile draw. dont let that
be the constraint right now."* ⇒ `ms_ratio` and every wall-clock quantity are **measured and
reported on every branch** and are **NEVER a branch input**. WAIVED: the consequence. NOT WAIVED:
the measurement.

⛔ **ANTI-GAMING (binding, inherited verbatim):** permission to spend clock is never licence to
reshape the arbiter to look cheaper. **B stays 16 and may not be expanded. The tie predicate is
not narrowed. There is no playout truncation for cost reasons.** Any such change makes this a
different lever requiring its own design.

**§0.B — the arbiter FAILS SOFT (from Stage-2 §0.E).** On a deep-playout error the arbiter falls
back to the champion's own pick and counts it: the ply is un-arbitrated, not lost. Accepted,
because propagating would kill the GAME and the exclusion would be **candidate-correlated** — a
biased exclusion is far worse than a diluted effect. **The bias runs toward the champion, so a
positive read is UNDERSTATED.** Never a branch input EXCEPT through `G-FIRE`'s `phi_effective`.

⚠️ **Here the fail-soft asymmetry is NOT symmetric across cells** — CELL A has no arbiter to fail.
Consequence, stated now: fail-soft dilutes `D` **toward zero**. A positive `D` is therefore a
**lower bound** on the mechanism's true delta, and a null is correspondingly weaker evidence of
absence. This is reported on every branch (§4.3 item 6).

**§0.C — the field-name trap.** In `eval_fair_puct`, `champ_prefix_ms_per_move` is the
**CANDIDATE** side, the opposite of `eval_puct_priors`. In `scripts/jcz_match/`, OUR side is
`champ` and JCZ is the opponent. Any read-out that swaps them inverts the reading. The adjudicator
**prints which field it read for each side**.

**§0.D — the cost model is measured, never re-tuned.** Stage 2's DESIGN §5 predicted
`ms_ratio ≈ 1.1985` and realized **2.42**; the miss was in the DENOMINATOR's currency (a
sequential `t_champ` divided into a contended per-move wall), and the arbiter's own cost — the
numerator — was accurate within 11.8%. This design's §6.2 prediction (**CELL B ≈ 2.71× CELL A per
game, 266 worker-s**) is printed against the realized value on every branch, because that
comparison is the only way a wrong cost model becomes visible. It moves no bar.

**§0.E — `PRODUCTION.yaml` is untouched on every branch.** This cell INFORMS the owner's pending
flip decision. It does not take it and does not gate it.

---

## §0.F — PRE-LAUNCH AMENDMENT (2026-08-17). NO BAR MOVES.

Made with the band **UNCLAIMED**, **no game played**, and **no statistic of any kind in
existence**. The blind ordering is intact: this amendment cannot have been written to fit a
result, because no result exists. **No adjudicating bar moves and §4 is left BYTE-IDENTICAL.**

### §0.F.1 — TWO BOXES (owner ruling), and the two gates it adds

Owner directive, verbatim: **"make sure its both boxes, w22 and w30 respectively"**. Execution
model in DESIGN §0.1. Two gates are **ADDED** to §3. Both are **tightenings** — they can only turn
a readable run unreadable, never the reverse:

* **`G-SPLIT`** — the deck→host assignment is **IDENTICAL across both cells**, verified from the
  records. **Rationale (DESIGN §0.1.2):** `D` is deck-paired, so if a deck ran on different boxes
  in the two cells, every per-box difference (the JVM packaging differs `24.04.2` vs `26.04.2`;
  `W` and hence contention differ; RAM differs) lands *inside* the paired difference and is
  arithmetically indistinguishable from the arbiter's effect. With the split identical, all of it
  cancels. VOIDS on any deck whose host differs between cells, or on an absent host stamp.
* **`G-COVER`** — the union of the per-box ranges covers **all `DECKS` decks × 2 seatings exactly
  once per cell**: no gap, no duplicate, no deck outside the band. VOIDS otherwise.

### §0.F.2 — TWO GATES WERE UNSATISFIABLE BY CONSTRUCTION. Fixed BEFORE launch, not after.

Stage 2 lost an adjudication to three gates that could not pass on a healthy run, and had to fix
them *after* the statistics had been printed. The §3.1 structural test was applied again here
against the actual harness, **before** the band was claimed, and it caught two of the same class.
Fixing them now costs nothing and preserves blindness completely.

* **`G-PLY` was unsatisfiable.** §3 said the ply witness must be "present for **both** cells", but
  Stage-2 §0.F's witness is `tiearb_partial_argmax_total`, which CELL A **cannot** carry — and
  `G-ARB` positively **forbids** a `champ_tiearb` key on CELL A. The two committed sentences
  contradicted each other and every healthy run would have voided.
  **AMENDED READING:** both cells must carry the harness's own ply accounting
  (`moves_by_seat`/`moves` + `n_actions`); **CELL B must additionally** carry the arbiter ply
  witness with `partial_argmax` **present on every game** and `partial_argmax_total == 0`
  (Stage-2 §0.F verbatim: **absent is unknown-not-zero and FAILS**; non-zero FAILS). Strictly
  fail-closed on the side that can carry it.
* **`G-LEAF`'s witness name was `eval_fair_puct`'s spelling.** §3 names `cand_leaf_hash`;
  `scripts/jcz_match/match.py` writes the same quantity at
  `champion_manifest.leaf_hashes.harness_leaf_hash` and has **no** `cand_leaf_hash` at all.
  **AMENDED READING:** read top level → `config.*` → the harness-native address, and **report
  which resolved**. **ABSENT AT EVERY ADDRESS STILL FAILS**; a present-but-different hash still
  fails. This implements the committed *proposition* ("the arbiter moves no leaf") rather than a
  spelling borrowed from a different harness.

⭐ **The structural test, answered for every §3 gate including the two new ones, recorded before
any outcome is known: would this gate fail on EVERY healthy run of this launcher? ANSWER: NO.**

### §0.F.2b — a THIRD unsatisfiable conjunct: `G-TOOL`'s `carc_rs_binary_sha`

Caught by the same structural test, before the band was claimed. **`scripts/jcz_match/match.py`
does not stamp `carc_rs_binary_sha` anywhere**, and neither does the champion manifest it embeds —
verified against the real 2026-08-09 archive, whose manifest carries `our_git_rev`,
`champion_manifest.code_commit`, and `champion_manifest.backend.carc_rs_version` (`"0.1.0"`, a
package version, not a build) and nothing else. A conjunct requiring a key the harness never
writes fails closed on **every healthy run** — the exact defect class this amendment exists to
catch.

**AMENDED READING — the same proposition, witnessed by artifacts that exist.** `G-TOOL` asserts
*"both boxes and both cells ran the same wheel"*. It is now discharged by three conjuncts:

1. **cross-HOST build identity** — the `carc_rs` build id **and** binary sha256 recorded in each
   host's `verdicts/PREFLIGHT_<host>_ENV.json` are equal across hosts. This is the Stage-2
   corrected shape: **pre-flights compared with pre-flights**, never a pre-flight against a
   manifest (`carc_rs_build_id()` embeds `git rev-parse HEAD` at call time, so that cross-comparison
   answers *"did HEAD move between two moments?"* and is a false positive by construction).
2. **cross-CELL code identity** — `our_git_rev` (falling back to `champion_manifest.code_commit`)
   is equal across CELL A and CELL B, and consistent within each cell (no mixed-rev cell).
3. **the commit-range conjunct, unchanged** — `git diff --name-only <preflight>..<manifest> --
   rust/ src/ engine/ scripts/` is EMPTY, or the range is degenerate. Non-empty or UNRESOLVED
   VOIDS.

`carc_rs_binary_sha` is still read from the manifest **when present** and still binds when
present; it simply may not be the *only* witness, because it does not exist in this harness.
**ABSENT AT EVERY SOURCE INCLUDING THE PRE-FLIGHTS STILL FAILS** — the fail-closed direction is
preserved exactly.

📌 Parked, not done (it would mean editing a driver under a live tree): `match.py` should stamp
`carc_rs_binary_sha` into its manifest, so a future run's build witness travels with the data
instead of with the pre-flight. Roadmap item, not a launch blocker.

### §0.F.3 — instrument-fix discipline, restated and now binding on a SECOND session

The §4 rule stands: if a defect is found **after** a first adjudication, the session writing the
fix must be one that has **not** seen the strength statistics, and every fix must be decidable
from gate inputs alone. The fixes in §0.F.2 were made **before any run existed**, so no session
was ever non-blind — which is the outcome that discipline exists to produce.

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

**PRIMARY — `D`, and its `z_D`:**

```
D    = M_B - M_A,  deck-paired over the decks common to BOTH cells, in points per game
       M_B = mean margin of (champion+arbiter) vs JCZ
       M_A = mean margin of (champion)          vs JCZ
       margin = OUR final score - JCZ final score
se(D)  = paired standard error over n_common decks
z_D    = D / se(D)        (convention: eval_fair_puct._paired_z)
```

Each deck contributes ONE paired observation per cell: the mean of its two seatings. `D` is the
deck-wise difference of those, so seat effects cancel twice over.

**SECONDARY, reported on every branch, never a branch input except where §3 names it:** each
cell's W/D/L, win rate, elo with its within-band 1σ, its own deck-paired margin vs JCZ and that
margin's `z`, per-seat means, `phi` / `phi_effective` / `pickchanges` for CELL B, `ms_ratio`, the
divergence ledger, and CELL A's absolute elo against the 2026-08-09 reading of +111.4.

⚠️ **`z_D` is READ off the analyzer's computed value; the adjudicator ALSO recomputes it from the
records and prints both. A disagreement beyond floating-point tolerance is `U-UNREADABLE`.** The
recomputation is a WITNESS, never a branch input.

---

## §2 — UNITS

`n` in every bar below is in **DECKS** (a paired statistic; each deck is 2 games), except
`cell_games_floor`, which is in games. 400 decks = 800 games per cell.

---

## §3 — PRECONDITIONS (every one must PASS, else `U-UNREADABLE`)

Fail-closed. **ABSENT is FAIL.** Each gate is read at the manifest top level, then at `config.*`,
and the adjudicator **reports which address resolved** (the Stage-2 `G-J1`/`G-BAND` fix, adopted
here as the shipped behaviour rather than re-discovered).

| id | proposition | VOIDS on |
|---|---|---|
| `G-BAND` | both cells carry the SAME band; band was claimed BEFORE game 1 (sentinel timestamp precedes the first record); record-derived deck sets agree with the declared band | any mismatch |
| `G-LEAF` | the champion leaf hash == `a36d2e15a3b3d71d` on BOTH cells, read top level → `config.*` → `champion_manifest.leaf_hashes.harness_leaf_hash`, reporting which resolved (**§0.F.2**) | difference, or absence at EVERY address |
| `G-SPLIT` | **(added §0.F.1)** the deck→host assignment is IDENTICAL across both cells | any deck whose host differs between cells; an absent host stamp |
| `G-COVER` | **(added §0.F.1)** the union of per-box ranges covers all `DECKS` decks × 2 seatings EXACTLY ONCE per cell | any gap, duplicate, or out-of-band deck |
| `G-ARB` | CELL B resolves `champ_tiearb` == `{"enabled":true,"B":16,"J":4,"mode":"argmax","salt":"tiearb2-deploy-v1","eps":0.0}` **AND CELL A carries NO `champ_tiearb` key** | any other rung; a key present on CELL A |
| `G-FIRE` | CELL B `phi_effective` ≥ **1.0** fired tied tile plies per game, where `phi_effective = phi × (1 − error_rate_on_fired)` | below floor |
| `G-J13` | **PER-HOST (§0.F.1).** The TWO-SIDED arbiter positive control passed on **EVERY host that played** — **pick CHANGED** and **root leaf value bits UNCHANGED** — recorded in `verdicts/PREFLIGHT_<host>_FIRST.json`, generated AFTER any wheel build on that host and BEFORE that host's game 1. Expected hosts: `Doctor`, `laptop-wsl` | either side failing on any host; a host that played with no pre-flight |
| `G-RULES` | BOTH cells stamp `rules_profile == "fixed_v1"` and `r9_env == "1"` | anything else |
| `G-DIVERGE` | **REAL divergence count == 0** in BOTH cells, and `final_agree` on ≥ 99% of scored games in BOTH cells | any REAL divergence |
| `G-JCZ` | **PER-HOST (§0.F.1).** JCZ provenance identical across cells AND across hosts, and equal to DESIGN §7.1 (rev `29a1561…`, jar sha256 `4dc5439d…` verified ON EACH HOST, `LegacyAiPlayer`, `basic:2`, ai class `com.jcloisterzone.ai.AiEngine`, 10 shim classes). ⚠️ The JVM *packaging* differs by host (`24.04.2` vs `26.04.2`, same OpenJDK 17.0.19) — **REPORTED, and it cannot touch `D` because `G-SPLIT` holds the deck→host map identical across cells** | any difference in the pinned artifacts on any host |
| `G-TOOL` | **(amended §0.F.2b)** three conjuncts: (1) cross-HOST — `carc_rs` build id + binary sha equal across hosts, read from each `PREFLIGHT_<host>_ENV.json` (pre-flights compared with pre-flights, NEVER against a manifest); (2) cross-CELL — `our_git_rev` / `champion_manifest.code_commit` equal across cells and consistent within each; (3) `git diff --name-only <preflight>..<manifest> -- rust/ src/ engine/ scripts/` EMPTY or degenerate. Manifest `carc_rs_binary_sha` binds WHEN PRESENT (this harness does not write it) | a NON-EMPTY or UNRESOLVED wheel-relevant diff; mixed builds across hosts; mixed revs across cells; absent at EVERY source |
| `G-N` | `n_common` ≥ **320 decks** AND each cell has ≥ **640 games** scored | either floor |
| `G-PLY` | **(amended §0.F.2)** BOTH cells carry the harness ply accounting (`moves_by_seat`/`moves` + `n_actions`); **CELL B additionally** carries `partial_argmax` on EVERY game with `partial_argmax_total == 0` | absent accounting on either cell; absent `partial_argmax` on CELL B (unknown ≠ zero); non-zero `partial_argmax` |

**`G-CLOCK-REPORT` is NOT in this table.** `ms_ratio` and every cost figure are reported on every
branch and can void nothing (§0.A).

### §3.1 — the structural test, applied to every gate above, BEFORE any outcome is known

Stage 2 lost an adjudication to three gates that were **unsatisfiable by construction**. Each gate
above was checked against the question **"would this gate fail on EVERY healthy run of this
launcher?"** — recorded here, before launch:

* `G-TOOL`'s commit-range conjunct: **the launcher generates its pre-flight AFTER the wheel build
  and BEFORE the detached launch**, so the range is degenerate or empty on a healthy run. (Stage 2
  had no pre-flight step in `launch_both.sh` and therefore moved HEAD on every healthy run; that
  ordering defect is fixed here rather than inherited.)
* `G-ARB`'s "CELL A carries NO key": guaranteed by the enabling change's byte-identity contract
  (DESIGN §6.1) and unit-tested.
* `G-N`'s floors: 320/640 are 80% of planned, matching Stage 2.
* `G-FIRE`'s floor of 1.0 against an offline prior of 22.96 and a Stage-2 realized 17.573.

Answer for every gate: **NO** — none fails on a healthy run.

---

## §4 — THE BRANCHES

Read **in order**. The FIRST whose condition holds is the branch, taken verbatim.

Let `z_D` and `D` be as defined in §1, and `z_A` be CELL A's own deck-paired `z` vs JCZ.

### `J-CONFIRMED` — the arbiter's edge SURVIVES out of lineage
**Condition:** all §3 gates PASS **AND** `z_D ≥ +2.0` **AND** `D > 0`.

**Says:** terminal-grounded tie arbitration buys real points against an opponent that shares no
leaf, no search, no engine and no rules implementation with us. The Stage-2 edge is **not** an
artefact of playing our own lineage at its own blind spots.

**LICENSES exactly one thing:** it is *corroborating evidence* the owner may weigh in the pending
production-flip decision. ⛔ It does NOT flip `PRODUCTION.yaml`, does NOT license an on-device
deploy (`rho_phone` 5.520 at B=16, unsolved), does NOT license a leaf term (CL-065 and the two
dead menus stand), does NOT license a second cell or a larger B, and does NOT make anything
superhuman (DESIGN §8.1).

### `J-SIGN` — the direction resolves but not at the bar
**Condition:** gates PASS, `+1.0 ≤ z_D < +2.0`, `D > 0`.

**Says:** the delta points the same way as Stage 2 and this cell could not convict it. The honest
deliverable is a **sign**, in the precedent of the OOF sign check. **NOT a confirmation** and it
may not be quoted as one. It does not license a bigger-n follow-up by itself — DESIGN §4.3 already
prices that at ~3× this cell's compute, unfunded.

### `J-NULL-BOUNDED` — no effect detected, and the bound is stated
**Condition:** gates PASS, `|z_D| < 1.0`.

**Says:** the arbiter's out-of-lineage delta is **bounded at |D| < 1.72 pts/game at 2σ** (DESIGN
§4.2) — that is ≈56% of the Stage-2 magnitude. ⚠️ **This is NOT a refutation of Stage 2 and must
never be written as one.** It is consistent with (a) a lineage-specific edge, (b) an edge
attenuated below this cell's resolution, and (c) fail-soft dilution (§0.B), and this cell
**cannot separate them**. It is a material negative datum for the flip decision and must be
reported to the owner as prominently as a positive would be.

### `J-REVERSED` — the delta convicts NEGATIVE
**Condition:** gates PASS, `z_D ≤ −2.0`.

**Says:** the arbiter *costs* points out of lineage at 2σ. This is a **strong negative** for the
flip and is reported as the headline. It also makes the Stage-2 result a lineage-specific effect
by direct evidence, which is a finding in its own right and goes in `LEVER_INDEX` as such.

### `J-INDETERMINATE`
**Condition:** gates PASS, `−2.0 < z_D ≤ −1.0`.
**Says:** negative-leaning, unresolved. Reported as such. Licenses nothing.

### `U-UNREADABLE`
**Condition:** ANY §3 gate FAILS.
**Says:** no strength statistic from this run is adjudicated, quoted, or entered in
`results.csv` as a verdict. The failed gate is named with its realized value. `U-UNREADABLE` is a
fully acceptable outcome.

⚠️ **§4.3's companion table is printed on EVERY branch INCLUDING `U-UNREADABLE`.** Stage 2
learned that this makes the orchestrating session **non-blind** at fix time. Therefore, binding
here: **if an instrument defect is found after a first adjudication, the session that writes the
fix MUST be a session that has not seen the strength statistics**, and every fix must be decidable
from gate inputs alone. Bars do not move. §4 is not edited.

---

## §4.3 — THE COMPANION TABLE (printed on every branch, including `U-UNREADABLE`)

1. Per cell: n games, n decks, seat balance, W/D/L, win rate + its z, elo + 1σ + 95% CI, own
   deck-paired margin ± se and its z, per-seat mean margins, n_failed, failure rate.
2. `D`, its paired se, `z_D`, `n_common`; the naive difference of the two summaries as a
   diagnostic; and **the `n` (in decks) that would resolve `D` to 2σ at the realized dispersion**.
3. CELL B: `phi`, `error_rate_on_fired`, `phi_effective`, `pickchanges`, `arms_total`,
   `playouts_total`, `tiearb_errors_total`, `tiearb_first_error` — beside the offline prior 22.96
   and the Stage-2 realized 17.573.
4. `ms_ratio` for both cells with the §0.C field-name trap named and the fields printed;
   **DESIGN §6.2's prediction (CELL B ≈ 2.71× CELL A, 266 worker-s/game) against the realized
   value** (§0.D).
5. Every §3 gate with its realized value and which manifest address resolved it.
6. **§0.B's dilution statement, verbatim**, whenever CELL B's `tiearb_errors_total` > 0.
7. ⭐ **CELL A's ABSOLUTE result against JCZ, stated prominently** — elo, wr, deck-paired margin —
   beside the 2026-08-09 reading (+111.4 elo, wr 0.6550, +6.50 ± 0.86 over 200 decks, band
   1.08e11, rev `9c4bb50`), **with the cross-band over-dispersion rider applied** (σ inflates
   ≈1.8–2.2×, so ±17.4 → ≈±31–38 elo on that contrast). This is printed on EVERY branch including
   `U-UNREADABLE`, because the champion's out-of-lineage strength is a finding independent of `D`.
8. The divergence ledger for both cells by class, with `WALL_LEGALITY` and `UNPLACEABLE_REDRAW`
   named as the two classified-benign classes and any REAL divergence as a void.

---

## §5 — WHAT NO BRANCH DOES

No branch flips `governance/PRODUCTION.yaml`. No branch licenses an on-device deploy. No branch
licenses a change to B, J, the tie predicate, the salt, or the playout. No branch licenses a
second cell. No branch makes any claim about superhuman strength.
