# READ_RULE — invasion-risk term family, round-1 screen at 2752

**STATUS: FROZEN, NOT AUTHORIZED TO LAUNCH (2026-08-26).** No cell has run.

> ### ⭐ PRE-GAME-1 AMENDMENT — 2026-08-26, ZERO GAMES PLAYED, BAND UNSPENT
>
> Made under the house pre-game-1 amendment pattern: the band `151000000000` is
> unspent, no cell has run, and the pair is still blind, so this is an
> **amendment to the pair**, not a post-blind deviation. Five items, all
> tightening or correcting; **no bar moved and no branch condition changed.**
>
> 1. **The §9 smoke leg now writes its own `PINNED_SRC_REV`, `BLIND_PROOF.json`
>    and `SRC_CLEAN.jsonl` boundaries.** Running the smoke from the main tree
>    exited `11`: `G-REV` read *"PINNED_SRC_REV ABSENT — ABSENT is FAIL"* on
>    **every** smoke, because only a real launch wrote that file. ⛔ The fix
>    SUPPLIES THE WITNESS; it does **not** widen §3.5's allowed set.
>    **ABSENT-is-FAIL stays sacred.**
> 2. **`G-WHEEL` gains its ANCESTRY conjunct** — the embedded rev in
>    `carc_rs_build` must be a rev at which `rust/carc/carc-core/src/leaf/invasion.rs`
>    EXISTS, and an ancestor of the branch tip. This is the only conjunct that
>    catches a stale wheel **post-hoc, from the archive alone**.
> 3. **`G-BLIND` gains its ANCESTRY / BANNER / PROOF conjuncts** — ancestor of
>    HEAD, the commit that introduced the FROZEN banner, and a `BLIND_PROOF.json`
>    that agrees with a **live** re-check. The launcher had always written that
>    artifact; nothing ever read it back.
> 4. **`G-REV` gains its `SRC_CLEAN.jsonl` conjunct** — clean at EVERY recorded
>    boundary, with a `pre-flight` boundary and an `after-…` boundary per cell.
>    Same story: the launcher wrote the file, nothing read it.
> 5. **`G-LEAF(c)` is declared canonical in its STRICTER implemented form** — see
>    the gate row.
>
> The three new conjuncts were latent obligations of §3's own text that the first
> implementation did not enforce. Naming them here, before game 1, is the
> alternative to discovering at adjudication that a gate was decorative.

Pair: [`DESIGN.md`](DESIGN.md) + this file. Adjudicator: [`analyze_screen.py`](analyze_screen.py).
Bars and cost figures have **exactly one implementation**, [`screen_lib.py`](screen_lib.py); this
file is the binding prose and the launcher pins only the band. **The pair is law** — a launcher or
an adjudicator that disagrees with this file is a code defect; the pair does not move.

⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every number below exists before any
game does.

---

## §0 — WHAT THIS ROUND IS, STATED BEFORE THE ANSWER

Four cells at the 2752 screening budget, each a deck-paired head-to-head between the **champion
leaf plus one invasion knob** and the **plain champion leaf**, on band `151000000000`, each on its
own disjoint deck range. It decides **what gets funded next**, and nothing else:

- a shape that fires earns **one** production-budget H2H — a separate pair, a separate band, a
  separate funding decision;
- a round in which **no** shape fires parks the family and hands the ceiling question to the
  solver-pricing instrument (the build-first bargain);
- a broken `IDENT` cell voids the whole round.

⛔ **A NULL IS A BOUND, NOT A ZERO.** [`DESIGN.md`](DESIGN.md) §4.2: this screen has 80% power only
at ≈±2.06 pts/deck. §4's `SCREEN-NULL` branch is required to print the bound and is forbidden from
printing "no effect".

---

## §1 — THE STATISTIC, NAMED BEFORE IT EXISTS

```
Per cell C, for each deck d in C's OWN seed range that appears in BOTH seatings:

    D_C(d) = ( diff(d, a_seat=0) + diff(d, a_seat=1) ) / 2

  diff = the harness's own final-score margin, CANDIDATE minus OPPONENT, in POINTS
         (eval_fair_puct.py:1603 -- `diff = (s0-s1) if a_seat==0 else (s1-s0)`).

D_C      = mean( D_C(d) )                       over n_common(C) decks
SE_C     = stdev( D_C(d) ) / sqrt(n_common(C))  -- sample stdev, ddof=1
z_C      = D_C / SE_C
```

Identical to `eval_fair_puct._paired_z` (`2371-2383`). The adjudicator reads `paired_mean_margin`,
`paired_z`, `n_paired` from each cell's `summary.json` **and** independently recomputes all three
from the raw `seed*_a*.json` records (`RECON`, §3).

**Cluster = deck.** Not game, not seat. **Primary unit = POINTS per deck.**

**Sign:** `D_C > 0` ⇒ the invasion term **won**. `D_C < 0` ⇒ it **lost** — a reportable finding
(`REVERSED-<shape>`), never a gate failure.

⛔ **EVERY BAR IN §4 IS EVALUATED AT THE CELL'S OWN REALIZED `SE_C`.** The `σ_D = 14.67` sizing
model of [`DESIGN.md`](DESIGN.md) §4.1 is used for **power arithmetic only** and never as a
denominator in a branch test. The adjudicator prints realized vs modelled SE per cell and
**FLAGS** a ratio outside `[0.70, 1.43]` as a dispersion anomaly — reported, never a branch input.

**Within-band, deck-paired, one instrument ⇒ NO cross-band humility discount** (CL-068's 1.8–2.2×
applies to cross-band contrasts; this is the robust class CLAUDE.md exempts).

⛔ **NO CROSS-CELL CONTRAST IS A BRANCH INPUT.** The four cells run on **disjoint** deck ranges
([`DESIGN.md`](DESIGN.md) §5.1). `D_A > D_B` is not a finding, is not printed as a ranking, and
cannot promote or demote anything. Each cell is adjudicated **against zero, on its own decks**.

---

## §2 — UNITS AND POWER, STATED BEFORE ANY NUMBER

### §2.1 — the sizing model

`σ_D` is read off seven `n=400`-deck, deck-paired, `fixed_v1`+R9, rust-backend cells in
[`../../experiments/results.csv`](../../experiments/results.csv) by inverting each one's published
margin and `z` (the derivation is [`../h2h_22016_prep/READ_RULE.md`](../h2h_22016_prep/READ_RULE.md)
§2.1, carried here unchanged): **median 13.15 · closest analogue (`b119e9`) 13.60 · max 14.67.**

**This pair sizes on the MAX, `σ_D = 14.67`.**

```
    IDENT   n = 200 decks:  SE = 1.0374 pts    2 sigma = +-2.075 pts
    A/B/D   n = 400 decks:  SE = 0.7335 pts    2 sigma = +-1.467 pts    1 sigma = +-0.734 pts
```

### §2.2 — the honest prior

**Nobody knows the sign, and the mechanism argument does not settle it.** The Stage A/B census
established that the E4 opponent's invasions *pay against the champion*; it did **not** establish
that a depth-0 leaf term is how a search should be told about them. Two named reasons a positive
is not the default expectation:

1. **Shape A overlaps `opp_bonus_cap = 8`** ([`DESIGN.md`](DESIGN.md) §3.6) — the leaf already
   discounts opponent-held value once. A second discount at an untuned weight can over-correct,
   which reads as `REVERSED`.
2. **The one-ply sibling-Δ measurements** ([`DESIGN.md`](DESIGN.md) §3.2 v) show D essentially flat
   within a ply on the census corpus (5.4% of positions carry any variation). A D-null is
   consistent with "the term is right but invisible at this depth".

3. ⛔ **THE R1/R2 OFFLINE FUNNEL FOR THIS EXACT TERM WAS ALREADY CLOSED BY F4**
   ([`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md), row "contested-feature /
   invasion-risk term", 2026-08-26 evening): *"the caveat FIRED — FUNNEL-CLOSED-BY-F4; every R2
   winner incl. `H4_DECISIVE_FARM` is F4-REFUTED (witness −2.10, z −2.57); the R1/R2 corpus
   licenses NOTHING for this term. Its case is now the E4-vs-human record ONLY … Any pricing of
   this term needs an out-of-family strong judge first."* This pair is a **game-play head-to-head**,
   not the offline funnel F4 refuted, so it is a legitimate and different instrument — **but that
   sentence is why §4's `PROMOTE` chain makes external validation mandatory rather than advisory,
   and it is a recorded reason to expect a null here.**

§4's table is therefore **symmetric and two-sided**, not a one-sided confirm.

---

## §3 — PRECONDITIONS (every gate individually fail-closed; ABSENT is FAIL)

Each gate is read at the manifest top level, then at `config.*`; the adjudicator **reports which
address resolved** (house `G-BAND`/`G-J1` precedent). **Any FAIL ⇒ `U-UNREADABLE`** for the
affected cell — and for `G-IDENT`, for the whole round (§3.4).

| id | proposition | address | fail on |
|---|---|---|---|
| `G-BAND` | per cell: `config.band_seed_start` == that cell's frozen `seed_start`; `config.n_decks` == its frozen deck count; `config.seatings_per_deck == 2` | cell `summary.json` → `config.*` (manifest top level as fallback) | any mismatch |
| `G-DECKS` | every realized `deck_seed` lies inside **that cell's own** range; every counted deck carries **both** `a_seat` 0 and 1; `n_common` == the frozen deck count; **and no seed appears in two cells' archives** | adjudicator's own collection over the raw `seed*_a*.json` records, across all four cells | any seed outside its cell's range; any deck counted at one seat only; `n_common` mismatch (short is `G-N`'s business, out-of-range is this gate's); **any cross-cell seed overlap** |
| `G-SINGLEVAR` | **WITHIN each cell**, the candidate and opponent config blocks differ in **NOTHING** except the cell's own invasion key(s). Two conjuncts: **(a)** the alias-aware side-by-side diff of the search/endgame/budget blocks (`config.champion.*` vs `config.opponent.*`, aliased pairwise: `k_dets`↔`k_dets`, `sims_per_det`↔`sims_per_det`, `total_sims`↔`total_sims`, `c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`, `endgame.*`) is **EMPTY**; **(b)** the leaf diff `config.cand_leaf_cfg` vs `config.opp_leaf_cfg` equals **EXACTLY** the cell's frozen key set (`IDENT`: ∅ — the explicit zeros are dropped by `_leaf_dict`'s default-exclusion, so the two dicts are identical; `A_MID`: `{invasion_beta}`; `B_MID`: `{invasion_alpha, invasion_alpha_cap}`; `D_MID`: `{invasion_delta_farm}`) | cross-side diff within one cell's own `summary.json` `config` block | ANY other differing key, in either conjunct. Set equality is **two-sided**: an extra differing key fails, and an expected-but-identical key fails too (a cell whose knob did not reach the leaf). ⚠️ Exact `!=` on flattened values; **no float tolerance** |
| `G-LEAF` | **(a)** `config.opp_leaf_hash` == `a36d2e15a3b3d71d` on **every** cell; **(b)** `config.cand_leaf_cfg.v29_meeple_curve` == `[-10.0,-5.0,-1.25,0.0,2.5,3.75,5.0,6.25]` on every cell; **(c)** ⭐ **THE STRICTER FORM IS CANONICAL (amended 2026-08-26):** `config.cand_leaf_hash` equals that cell's **OWN PINNED HASH, exactly** — `IDENT a36d2e15a3b3d71d` · `A_MID 0fd1680fa363d65e` · `B_MID 42adadc988784b44` · `D_MID 5012569b4e93d559` (computed at freeze through the harness's own `_load_cand_leaf_cfg` + `_leaf_hash`, and re-checked by the launcher's wheel pre-flight and by `tests/test_invasion_screen_instrument.py`). The original wording — *"== the champion hash on IDENT and != it on the arms"* — is the weaker consequence and is **superseded**: mere asymmetry would admit an arm running the WRONG nonzero weight | `summary.json` → `config.cand_leaf_hash`, `config.opp_leaf_hash`, `config.cand_leaf_cfg` | any deviation. ⚠️ **(c)'s asymmetry is deliberate and load-bearing** ([`DESIGN.md`](DESIGN.md) §2.2): an explicit-zero invasion config hashes AS the champion because it IS the champion leaf bit-for-bit; a nonzero weight must not. **An `IDENT` whose candidate hash drifted, or an A/B/D whose candidate hash did not, is a wiring defect** — and it also proves the launcher's `--allow-leaf-hash-drift` asymmetry was applied correctly. ⛔ **(a) IS NOT REDUNDANT WITH THE HARNESS'S OWN CHECK, AND THIS IS WHY IT EXISTS:** `--allow-leaf-hash-drift` is a **single** flag that downgrades `_assert_netprior_leaf` to a warning on **BOTH** sides (`eval_fair_puct.py:3763` candidate, **`:3777` opponent**). So on A/B/D — the three cells that must pass it — the harness's opponent-side hash assertion is **not enforcing anything**, and conjunct (a) re-establishes it at adjudication against the emitted manifest. Without (a), a drifted opponent leaf on an A/B/D cell would pass silently and the cell would not be single-variable at all |
| `G-INVASION` | per cell, in `config.cand_leaf_cfg`: the cell's own knob(s) read back at **exactly** the frozen value (`beta 0.12` / `alpha 0.09` + `alpha_cap 11.0` / `delta_farm 0.12`; `IDENT`: no invasion key present at all), and **every other invasion field at its default** (`beta/alpha/alpha_cap/gamma/delta_farm == 0.0`, `stub_max_tiles == 2`). And in `config.opp_leaf_cfg`: **all six absent or at default** | `summary.json` → `config.cand_leaf_cfg`, `config.opp_leaf_cfg` | any knob at the wrong value; any second nonzero weight; any invasion key on the opponent side. ⚠️ `_leaf_dict` **drops a field while it holds its default**, so "absent" IS "default" and both readings pass |
| `G-CAPFWD` | the **biconditional**: `invasion_alpha_cap` is present-and-nonzero in `config.cand_leaf_cfg` **if and only if** `invasion_alpha` is present-and-nonzero. Likewise `invasion_stub_max_tiles != 2` ⟹ `invasion_alpha != 0` | `summary.json` → `config.cand_leaf_cfg` | either direction violated | 
| `G-WHEEL` | top-level `carc_rs_build` present and non-null; `carc_rs_binary_sha` present; `mixed_builds == false`; the launcher's `WHEEL_PROBE.json` records a **successful NONZERO-kwarg forward**; **AND ⭐ THE ANCESTRY CONJUNCT (amended 2026-08-26)**: the git rev embedded in `carc_rs_build` must satisfy **both** `git cat-file -e <rev>:rust/carc/carc-core/src/leaf/invasion.rs` (the wheel was built from a tree that CARRIES the family) **and** `git merge-base --is-ancestor <rev> <branch tip>` (it is this lineage's build, not an unrelated rev) | `manifest.json` top level (`eval_fair_puct.py:4814-4826`); `WHEEL_PROBE.json`; live `git` | absent; null; `mixed_builds == true`; a `carc_rs_build` with no embedded rev; a rev at which `invasion.rs` does not exist; a non-ancestor rev; a missing or failed wheel probe. ⭐ **THE ANCESTRY CONJUNCT IS THE ONLY ONE THAT CATCHES A STALE WHEEL POST-HOC, FROM THE ARCHIVE ALONE.** `WHEEL_PROBE.json` proves a nonzero forward worked at LAUNCH time; this proves the build that actually PLAYED the games could contain the family. Both halves are needed: `leaf_config_rs` forwards the knobs CONDITIONALLY, so a stale build serves every champion config unchanged and silently, and a stale-wheel cell reads as *"the term is worth nothing"* rather than *"the term never ran"*. ⚠️ **`carc_rs_version` is permanently `"0.1.0"` and is NOT a build discriminator** — the embedded rev is the only fingerprint the manifest carries |
| `G-RULES` | `rules_profile.name == "fixed_v1"` **AND** `rules_profile.r9_env_ok == true` **AND** `r9_env_observed == true` | `summary.json` / `manifest.json` → `rules_profile.*` | anything else. (Non-inverted: `fixed_v1` wants R9 **ON**) |
| `G-BACKEND` | `config.backend.name == "rust"`, `.requested == "rust"`, `mixed_builds == false`, **AND `converted_sides == ["candidate", "opponent"]`** | `summary.json` → `config.backend.*` | any leg not rust-resolved; `converted_sides` missing `"opponent"`. ⚠️ Load-bearing beyond provenance: the invasion family **exists only in rust**, so a python leg would not merely be slower — it would `raise NotImplementedError` on a nonzero weight, or (worse, on a stale-wheel path) serve an invasion-blind leaf that reads as a null |
| `G-BUDGET` | **both** sides `(k_dets, sims_per_det, total_sims) == (4, 688, 2752)`, and the product identity `k × s == total` holds on both | `summary.json` → `config.champion.*` / `config.opponent.*` | any deviation, or a product that does not multiply out. ⚠️ The harness's non-fatal `[warn] … deviates from governance/PRODUCTION.yaml (k_dets=4 …)` is **EXPECTED** ([`DESIGN.md`](DESIGN.md) §2.4) and is not a gate input |
| `G-TIEARB` | the root tie-arbiter is ABSENT/disarmed on BOTH sides. **Three** conjuncts: **(a)** `cand_tiearb.enabled` is absent or `false`; **(a2)** **every terminal key named exactly `tiearb_enabled`, anywhere in either document, is `false`**; **(b)** **no CONTAINER (non-terminal) path segment whose name contains `tiearb` exists outside the `cand_tiearb` subtree** | `manifest.json` / `summary.json` → `cand_tiearb.enabled`, every `*.tiearb_enabled` leaf, plus a container-segment scan of both | `cand_tiearb.enabled == true`; any `tiearb_enabled` leaf true; OR any `tiearb`-named CONTAINER segment outside `cand_tiearb`. ⭐ **(a2) AND THE "CONTAINER" QUALIFIER IN (b) ARE A FREEZE-TIME CORRECTION, MADE AGAINST A REAL EMITTED MANIFEST.** The first draft said "no `tiearb`-named path segment", full stop. A healthy archive emits **`config.champion.tiearb_enabled = false`** — a *terminal* key containing `tiearb` — so the undifferentiated rule would have voided **every healthy cell**. Restricting (b) to containers fixes that, and (a2) is added so the newly-exempted terminal keys are still *checked*, not merely tolerated. Between them the armed cases stay caught: an armed opponent block flattens to `opp_tiearb.enabled` (container `opp_tiearb` → (b)), and an armed champion sets `champion.tiearb_enabled = true` (→ (a2)). ⚠️ The opponent side is **structurally** disarmed (no `--opp-tiearb-*` flag of any spelling exists); this gate records that as verified. A future harness emitting a benign disarmed `tiearb`-named CONTAINER still trips (b) — a **false VOID, the recoverable direction**; the fix is to amend the gate, never to relax it into interpreting armed-ness |
| `G-EXACT` | `config.endgame.exact_k == 2`, `mode == "marginalized"`, identical on both sides | `summary.json` → `config.endgame.*` / `config.opponent.endgame.*` | any deviation. K=3/4 are clairvoyant-only; a fair cell cannot run them |
| `G-REV` | `config.code_rev` **names the same commit as** the launcher's `PINNED_SRC_REV` on **every** cell — ⚠️ **read as a case-insensitive PREFIX match of at least 7 hex, with any `-dirty` suffix an outright FAIL**, NOT as string equality. Verified at freeze: `run_manifest.code_rev()` emits `git rev-parse --short HEAD` (7–12 hex, e.g. `2eca4a92`) while `PINNED_SRC_REV` is written from `git rev-parse HEAD` (40 hex), so literal equality could **never** hold and the gate would void every cell. `screen_lib.rev_matches()` is the one implementation; **AND ⭐ THE `SRC_CLEAN` CONJUNCT, NOW ENFORCED (amended 2026-08-26)**: `SRC_CLEAN.jsonl` records `src/ engine/ scripts/ rust/ tests/ pyproject.toml setup.py` **CLEAN at every recorded boundary**, with a `pre-flight` boundary and an `after-…` boundary for each cell's final pass; and **all four cells share one `code_rev`** | `manifest.json` → `config.code_rev` (top-level `code_rev` as fallback); `SRC_CLEAN.jsonl`; `PINNED_SRC_REV` | rev mismatch; a `-dirty` suffix; `PINNED_SRC_REV` absent; `SRC_CLEAN.jsonl` absent, empty or unparseable; any boundary with `src_clean != true`; a missing `pre-flight` or per-cell `after-…` boundary; **any cross-cell rev disagreement** (the `track_d2_prep` mixed-rev defect). ⚠️ **The launcher has always WRITTEN this file at every pass boundary; until this amendment nothing READ IT BACK.** A mid-round tree move is exactly the `track_d2_prep` defect, and this pair is FOUR cells long, so the window for one is four times wider. ⚠️ On the **§9 smoke** the per-cell requirement relaxes to *"a `pre-flight` and at least one `after-…` boundary"* — a smoke has one cell and no seal — but the CLEAN requirement and the rev match do **not** relax, and the smoke now writes these artifacts itself precisely so this gate can PASS there (it is not in §3.5's allowed set) |
| `G-BLIND` | **Four conjuncts, ALL enforced (amended 2026-08-26 — the last three were stated here from the start but were not implemented):** (a) `BLIND_COMMIT` holds a 40-hex sha and every cell's manifest carries `stamps.BLIND_COMMIT` equal to it; (b) that sha is an **ancestor of HEAD**, by a **live** `git merge-base --is-ancestor`; (c) it is the commit that **introduced this pair's FROZEN banner** — an ADDED `STATUS: FROZEN` line in `DESIGN.md` or `READ_RULE.md` at that commit; (d) `BLIND_PROOF.json` exists, names the SAME blind commit, and its `is_ancestor_of_head` **agrees with the live re-check** | `BLIND_COMMIT`, `BLIND_PROOF.json`, live `git`, `config.stamps` | the literal `PENDING`; a non-ancestor; absent; a commit that did not introduce the banner; a `BLIND_PROOF.json` that is absent, names a different sha, or disagrees with the live re-check; a cell stamped with a different sha. ⚠️ **`run_cells.sh` has always WRITTEN `BLIND_PROOF.json`; until this amendment nothing READ IT BACK**, so a stale or disagreeing proof could sit in the directory unnoticed. The live re-check is what makes the artifact load-bearing rather than decorative |
| `G-N` | per cell: the frozen game count scored; `n_failed == 0`. A nonzero failure rate **< 2%** is **REPORTED, not silently absorbed**, and does not by itself void (the `b32v64` 0.100% rust-panic-class precedent). `n_common >= 80%` of the frozen deck count | `summary.json` → `n`, `n_failed`; adjudicator's own `n_common` | short of the frozen game count; failure rate ≥ 2%; `n_common` below the 80% floor |
| `G-SAT` | per cell, the realized candidate win-rate lies in `[0.35, 0.65]` | `summary.json` → `winrate` | outside. **A RAIL check, not a strength bar.** Both arms are the same champion differing by one leaf term; a win-rate outside this window means the two sides are not the agents this design says they are, and the margin would be a rail reading |
| `G-IDENT` | ⭐ **the round-level gate.** On the `IDENT` cell: **`|z_IDENT| <= 2.0`** at its own realized SE, **AND** `G-LEAF(c)` passed (candidate hash == champion hash), **AND** `n_failed == 0`, **AND** `G-SINGLEVAR(b)` found an **empty** leaf diff | `IDENT` cell's `summary.json` + the gates above | `|z_IDENT| > 2.0`; or any of the conjuncts failing. ⛔ **A FAIL VOIDS ALL FOUR CELLS** — see §3.4 |
| `RECON` | the **analyzer** values (read verbatim off `summary.json`) and the **witness** values (recomputed from scratch from the raw `seed*_a*.json` records by an independent re-implementation in [`screen_lib.py`](screen_lib.py)) agree within `rel 1e-6 / abs 1e-9` on **every** checked statistic, per cell: `paired_mean_margin`, `paired_z`, `n_paired`, `winrate`, `elo` | `summary.json` vs raw records | disagreement beyond tolerance on any statistic. **The recomputation is a WITNESS, never a branch input** — it can only void, never move, the number |

### §3.1 — the structural test, applied to every gate above, BEFORE any outcome is known

Every gate is subjected to four questions, and the answers are **executed, not reasoned**:

1. **Is it readable?** Does the address exist in a manifest the harness actually **emits**? —
   enforced by [`DESIGN.md`](DESIGN.md) §9's rule that the smoke leg ends by running this pair's own
   adjudicator against the emitted smoke archive. *(This is the fix for the `h2h_22016_prep`
   `G-TIEARB` near-miss: a gate written against a manifest the design described, not one the
   harness wrote, would have voided a healthy archive.)*
2. **Is it satisfiable?** Can a healthy run pass it? — every gate outside §3.5's pinned allowed set
   must PASS on the 16-game smoke.
3. **Is it falsifiable?** Is there a real defect it would catch? — recorded per gate in the table's
   "fail on" column; `G-CAPFWD` and `G-WHEEL` exist **because** this build found the two defects
   they catch ([`DESIGN.md`](DESIGN.md) §2.3, §7).
4. **Is ABSENT a FAIL?** — yes, for all eighteen, without exception.

`analyze_screen.py --selftest` executes 1/2/4 against a real manifest read off disk and **refuses
to run against a synthesized-only fixture**.

### §3.2 — the address-resolution rule

A gate's value is looked up at its named address; if `MISSING`, at the declared fallback container
(`config.*`, then manifest top level), and the adjudicator **prints which address resolved** for
every gate. **A value found at NO address is `ABSENT`, and `ABSENT` is `FAIL`** — never a skip,
never a default.

### §3.3 — `G-SINGLEVAR`'s alias table, fixed here

The two sides live at **different manifest addresses**, so a literal key-set diff would be all
noise. The alias pairs, and nothing else, are compared:

⭐ **THE ADDRESSES BELOW WERE VERIFIED AGAINST A REAL EMITTED MANIFEST AT FREEZE, NOT WRITTEN FROM
THE DESIGN.** The first draft of this table named `config.opponent.c` / `.tau_p` /
`.leaf_quantize` / `.final_select`; on a real archive those are `None` or absent, because the
opponent's search knobs are emitted one level down under **`config.opponent.champ_cfg.*`**. A gate
written against a manifest the design *described* would have voided every healthy cell on four
`MISSING` aliases. Corrected here, before the blind commit — the same class of defect the
`h2h_22016_prep` post-mortem raised and §3.1 question 1 exists to catch.

```
candidate address                  opponent address                        must
---------------------------------  --------------------------------------  ----------
config.champion.k_dets             config.opponent.k_dets                  be EQUAL
config.champion.sims_per_det       config.opponent.sims_per_det            be EQUAL
config.champion.total_sims         config.opponent.total_sims              be EQUAL
config.champion.c_puct             config.opponent.champ_cfg.c_puct        be EQUAL
config.champion.tau_p              config.opponent.champ_cfg.tau_p         be EQUAL
config.champion.leaf_quantize      config.opponent.champ_cfg.leaf_quantize be EQUAL
config.champion.final_select       config.opponent.champ_cfg.final_select  be EQUAL
config.champion.value_norm         config.opponent.champ_cfg.value_norm    be EQUAL
config.endgame.exact_k             config.opponent.endgame.exact_k         be EQUAL
config.endgame.mode                config.opponent.endgame.mode            be EQUAL
config.cand_leaf_cfg               config.opp_leaf_cfg                     differ in EXACTLY the frozen key set
```

⚠️ **`config.*` lives in `manifest.json`, not `summary.json`** — verified at freeze on a real
archive. `summary.json` carries the STATISTICS (`paired_mean_margin`, `paired_z`, `n_paired`,
`winrate`, `elo`, `n`, `n_failed`) and no `config` block at all. The adjudicator therefore loads
BOTH documents per cell and resolves every address across them, printing which document and which
address answered.

⚠️ **An alias whose opponent-side address is `MISSING` is a FAIL, not a skip.** If a future harness
renames one of these, the gate voids the cell — the recoverable direction — and the fix is to amend
the alias table in a fresh pair, never to drop the row.

⚠️ **A cross-cell literal config diff is computed and PRINTED (all four cells' `config` blocks,
flattened) as a DIAGNOSTIC.** It is **not** a gate: cells legitimately differ in band seed, deck
count, output path, claim host and leaf knob. It exists so a reader can see the whole delta in one
place.

### §3.4 — `G-IDENT` voids the ROUND, not the cell

If `G-IDENT` fails, **all four cells adjudicate `U-UNREADABLE`** and no `D_C` is reported as a
result for any of them.

**Why the round and not just the cell:** `IDENT` tests the plumbing every other cell depends on —
CLI parse → `_load_cand_leaf_cfg` → `leaf_config_rs`'s conditional kwargs → the rust leaf → 400
games of scoring. A defect that moves a **zero-weight** leaf moves every nonzero one too, and no
A/B/D reading could then be attributed to the term rather than to the wiring. Reading A/B/D past a
broken `IDENT` would be the `track_d2_prep` mistake — asserting single-variability in prose and
never checking it — with a self-inflicted excuse.

⚠️ **The converse is NOT true.** A **passing** `IDENT` proves the plumbing carries a zero
faithfully. It does **not** prove a nonzero weight reaches the rust leaf — that is `G-INVASION`'s,
`G-CAPFWD`'s and `G-WHEEL`'s job, and `G-LEAF(c)`'s hash asymmetry is the cheap cross-check.

⚠️ **`|z_IDENT| <= 2.0` is a null bar, and a null bar is weak by nature.** It can fail by bad luck
about 5% of the time when the wiring is perfect. That is **accepted deliberately**: a false
`U-UNREADABLE` costs a band and is recoverable; a true wiring defect read as a term effect is not.
If `G-IDENT` fails, the readout must report the failure as **ambiguous between defect and draw**
and must not assert a defect — the diagnosis is the leaf-hash conjunct and a re-run, not a
narrative.

### §3.5 — the smoke leg's PINNED ALLOWED SET

On the 16-game throwaway archive, `analyze_screen.py --smoke-mode` **must PASS iff the only
failing gates are these**:

```
G-BAND      G-DECKS      G-N      G-SAT      G-IDENT      RECON/n_paired
```

Everything else — `G-SINGLEVAR`, `G-LEAF`, `G-INVASION`, `G-CAPFWD`, `G-WHEEL`, `G-RULES`,
`G-BACKEND`, `G-BUDGET`, `G-TIEARB`, `G-EXACT`, `G-REV`, `G-BLIND` — **must PASS on 16 games.**
A failure outside the allowed set is a **launch blocker**, not a readout surprise: a gate that
cannot read what the harness emits has to be found before 2800 games are spent, not after.

⛔ **`G-BLIND` AND `G-REV` ARE NOT EXEMPT ON THE SMOKE, AND ARE NOT EXEMPTED BY THIS AMENDMENT.**
An earlier draft of this paragraph suggested the smoke could be excused from the stamping
requirement "insofar as it may run before `PINNED_SRC_REV` exists". **That excuse is withdrawn.**
Running the smoke from the main tree exited `11` on exactly that gap — `G-REV` read
*"PINNED_SRC_REV ABSENT — ABSENT is FAIL"* on every smoke — and the correct fix is the one that
does not touch this allowed set: **the smoke leg now writes its own `PINNED_SRC_REV`,
`BLIND_PROOF.json` and `SRC_CLEAN.jsonl` boundaries** (`run_cells.sh::run_smoke`). The launcher
knows the rev; supplying a witness is always preferable to excusing its absence. The smoke still
claims **no band** and drops **no `BAND_CLAIMED`**.

---

## §4 — THE BRANCHES

**Order of evaluation: `U-UNREADABLE` first (§3), then per cell, first-match-wins.**

### `U-UNREADABLE`

Any gate FAIL on a cell ⇒ that cell is `U-UNREADABLE` and **no `D_C` is reported for it**. A
`G-IDENT` fail ⇒ **all four**.

The readout must still print: which gate(s) failed, at which address, with the observed value;
`n_common` and `n_failed` per cell; and §4.3's companion table in full. **A void still owes its
cost number** (§4.3 item 6).

Band consequence: `151000000000` is **spent** the moment any real record exists on it, including
under a void (the `149e9` precedent — a fifth of one cell was enough).

### `PROMOTE-<shape>` — the shape earns one production-budget H2H

```
FIRES on cell C in {A_MID, B_MID, D_MID} iff
      all gates PASS  (including G-IDENT)
  AND z_C >= +2.0     at the cell's OWN realized SE_C
```

**What it licenses, exactly one thing:** a request to fund **one** head-to-head at the production
budget (`k8×1376 = 11008`), `n >= 400` decks paired, **a separate pair and a separate band**.

#### ⭐ THE FULL ADOPTION CHAIN — all four links, stated before any number

`PROMOTE` is the **first** link of four, and each link licenses only the next:

```
1. THIS SCREEN (2752, vs the champion)          -> licenses a production-budget H2H
2. PRODUCTION H2H (11008, vs the champion)      -> licenses an EXTERNAL VALIDATION cell
3. EXTERNAL VALIDATION (vs CARCASUM, the        -> licenses a champion-of-record /
   out-of-lineage ruler)                           PRODUCTION.yaml DISCUSSION
4. THE ONGOING E4 STREAM (a human opponent      -> the FINAL HOLDOUT
   who ADAPTS)
```

⛔ **LINK 3 IS NOT OPTIONAL AND MAY NOT BE SKIPPED, however large link 2's margin is.**
**Self-play evidence alone never adopts a term.** Two independent reasons, both standing rules of
this program:

- `feedback_anchor_before_scaling` — a self-anchored measurement can climb while absolute strength
  regresses; a verdict needs a reference **outside the training/tuning lineage**, and Carcasum is
  the program's only non-saturated out-of-lineage ruler.
- **The specific hazard of THIS lever:** an invasion term is, by construction, a term that exploits
  a *blindness in the incumbent champion* — the champion demotes the stub claim, so a term that
  promotes it wins games **against that champion** whether or not it is objectively better play.
  A margin at links 1 and 2 is therefore consistent with **exploiting the opponent rather than
  improving the agent**, and the two are indistinguishable inside the lineage. Only an
  out-of-lineage opponent can separate them.

- **And the program has already said so, for this exact term.**
  [`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md)'s invasion row, after F4 closed its
  offline funnel: *"Any pricing of this term needs an out-of-family strong judge first."* Link 3 is
  that judge. A `PROMOTE` here does not retire that requirement — it schedules it.

**Link 4** is the holdout that no amount of fixed-opponent evidence substitutes for: the E4 stream
is a human who **adapts**, so a term that merely exploits a fixed blindness decays there while a
genuine improvement does not.

**What `PROMOTE` does NOT license:**

- ⛔ **no `governance/PRODUCTION.yaml` change, and no champion-of-record discussion at all** — that
  conversation is unlocked by link 3, not by this branch;
- ⛔ no adoption of any kind;
- ⛔ for `PROMOTE-A` or `PROMOTE-D`: the production H2H is **not** a straight adoption test. Shape A
  subtracts from the same objects `opp_bonus_cap = 8` already discounts
  ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §1), so adoption owes a **re-sweep of
  `bonus_cap` / `opp_bonus_cap` against the new term** per `feedback_bug_fix_shifts_optima`. The
  promotion funds a sweep, not an edit. **This obligation is part of the branch, not a footnote.**
- ⛔ no claim about the shape at any other weight. One point is not a bracket (§4.1).

### `BRACKET-<shape>` — real enough to finish bracketing, not enough to promote

```
FIRES on cell C iff  all gates PASS  AND  +1.0 <= z_C < +2.0
```

The skeleton's own rule — *"bracket-complete only shapes whose mid-weight reads >= +1σ"* — read
against a mid that did not reach the promotion bar. **What it licenses:** the two named round-2
points for that shape ([`DESIGN.md`](DESIGN.md) §3.4, `×⅓` and `×3`), on a **fresh band**, as one
funding request. It licenses **no** production H2H and **no** claim that the shape works.

*(Recorded as a refinement: the skeleton states a promote bar at `+2σ` and a family-kill at
`all < +1σ`, which necessarily leaves this middle zone unnamed. Naming it here, before any number,
is the alternative to arguing about it afterwards.)*

### `REVERSED-<shape>` — the term measurably HURTS

```
FIRES on cell C iff  all gates PASS  AND  z_C <= -2.0
```

**A finding, not a failure.** It says the leaf term, at a scale-matched weight, costs points
against the champion. Read it against §2.2's first prior — an over-correction on top of
`opp_bonus_cap` is the leading candidate mechanism and is **testable**, so a `REVERSED-A` or
`REVERSED-D` should be reported **with** the caps-overlap hypothesis named, and specifically does
**not** kill the family: it argues for the caps re-sweep *first*, at a fresh band.

⛔ A `REVERSED` reading does **not** license flipping the term's sign. That is a different shape
and would need its own build, fixtures and pair.

### `SCREEN-NULL-family-parks` — the round-level kill

```
FIRES iff  all gates PASS on all four cells
      AND  z_C < +1.0  on EVERY ONE of A_MID, B_MID, D_MID
      AND  no cell fired REVERSED
```

**The family PARKS.** The verdict, stated in full before any number:

> At the 2752 screening budget, no invasion shape at a scale-matched mid weight moved the
> deck-paired margin against the champion leaf by as much as `+1σ`. The bound is §4.3's table:
> each cell's 95% CI. **The solver-pricing instrument is the funded next step** — the ceiling
> question (does a ceiling exist at all?) is what the build-first bargain hands it, and this
> round's null is the trigger.

⛔ **It is a BOUND, NOT A ZERO, and the readout must say so in those words.** §4.2's power table is
mandatory output on this branch: an effect of `+0.72` pts/deck would be caught only ~16% of the
time. Nothing here licenses "invasion doesn't matter", "the leaf already prices contest", or any
statement about shape C, about the `×3` weights, or about the mechanism the Stage A/B census
measured — which stands on its own evidence and is untouched by this round.

**Also stated before the answer:** `SCREEN-NULL` is a **real, expected, and useful** outcome. It is
what makes the build-first bargain honest — the build was funded on the understanding that a null
here retires the family cheaply and redirects the money, and a readout that treats it as a
disappointment is misreading its own design.

### §4.1 — rules that constrain EVERY firing branch

- ⛔ **A LONE VALUE THAT BEATS ITS NEIGHBOURS BY >1σ IS A NOISE SIGNATURE, NOT A PEAK.** In round 1
  each shape has exactly **one** point, so this rule bites in round 2: a mid that fires while both
  its `×⅓` and `×3` neighbours read >1σ lower is **re-measured before it is believed**, never
  promoted from the single screen. Recorded now so round 2 cannot relitigate it
  (`feedback_results_table_source_of_truth`, `CLAUDE.md` n-thresholds).
- ⛔ **A PEAK AT A LADDER ENDPOINT IS NOT BRACKETED.** If round 2's best reading is at `×⅓` or `×3`,
  the ladder is **extended** before anything is promoted (`feedback_bracket_hyperparams`).
- ⛔ **NEVER PROMOTE A FINDING FROM A SINGLE SCREEN.** `PROMOTE-<shape>` promotes a *funding
  request*, not a finding. The finding, if any, is made by the production H2H it buys.
- ⛔ **QUERY `results.csv` BEFORE DECLARING ANYTHING.** A reading that contradicts a prior
  measurement of the same cell is not a discovery until the contradiction is resolved.

### §4.2 — the joint A/D reading basis (MANDATORY on any A or D branch)

`T_A ≡ (cities+roads part) + T_D` **exactly** ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §4).
So `A_MID` and `D_MID` are **two points on one 2-D surface**, read on the
`(beta, beta + delta_farm)` basis:

```
A_MID  =  (beta, beta+delta_farm)  =  (0.12, 0.12)   -- 0.12 on cities, roads AND farms
D_MID  =  (beta, beta+delta_farm)  =  (0.00, 0.12)   -- 0.12 on farms ONLY
```

| observed | the ONLY licensed reading |
|---|---|
| A fires, D does not | the **cities+roads** part carries the effect; the farm part alone is not enough |
| D fires, A does not | the **farm** part carries it, and applying the same weight to cities+roads **cancels some of it** — a scope finding about where the term should apply, not two shapes |
| both fire | **ONE effect observed twice, on disjoint decks.** ⛔ NOT two independent confirmations, NOT additive, and the two `z`s must **never** be combined, pooled, or described as "consistent evidence from two shapes" |
| neither fires | the contested-value transfer is null at this weight, on both scopes |

⛔ **No branch may describe A and D as independent shapes.** Any readout that does is wrong on the
algebra, not merely on the emphasis.

### §4.3 — THE COMPANION TABLE (printed on EVERY branch, including `U-UNREADABLE`)

Mandatory output, whatever fires:

1. **Per cell:** `n_common`, `n_failed`, `D_C`, realized `SE_C`, `z_C`, the **95% CI** `D_C ± 1.96·SE_C`, `winrate`, `W/L/D`.
2. **Realized vs modelled SE** per cell (`SE_C` vs `σ_D=14.67/√n`), with the `[0.70, 1.43]` anomaly flag.
3. **The elo display**, through §4.4's guarded conversion, with the limb that applied printed.
4. **The power table** ([`DESIGN.md`](DESIGN.md) §4.2) — mandatory on every null.
5. **Every gate's PASS/FAIL, its resolved address, and its observed value** — all eighteen, on every branch.
6. ⭐ **The invasion-arithmetic cost multiplier**: per cell, `champ_prefix_ms_per_move` ÷ `rung_ms_per_move` (candidate ÷ opponent), with `IDENT`'s ratio as the ≈1.0 control, and the realized core-hours. ⛔ **Stamped `DESCRIPTIVE-ONLY — TENANCY-SENSITIVE, NOT A GATE`** ([`DESIGN.md`](DESIGN.md) §6.3). **This is the one deliverable owed on every branch including a void.**
7. **The frozen inputs, restated**: the mid weights and their derivation constants (`G = 1.76`, `M_A = M_D = 6.0`, `M_B = 8.0`, target `0.40·G = 0.704`), `alpha_cap = 11.0`, the band and per-cell deck ranges.
8. **The round-2 bracket**, restated as *not run*.

### §4.4 — the guarded elo conversion

```
IF |z_C| >= 2.0
    elo_per_point := that cell's OWN realized elo_C / D_C. Report it, and the elo display
    through it. Cross-check against the in-family bracket [16.74, 19.35] elo/pt and FLAG a
    reading outside it as a witness anomaly (never a branch input).

ELSE
    the cell's own ratio is NOT reportable and MUST NOT be printed as a scale. The elo display
    is quoted as a RANGE through the pinned bracket:
        2 sigma bound = +-(2 x SE_C) pts = +-(2 x SE_C x 16.74) .. +-(2 x SE_C x 19.35) elo
    and is LABELLED a bracket conversion, not a measured scale.
```

Under a null `D_C ≈ 0`, so a cell's own `elo/D` is a quotient of two noisy near-zero quantities: it
does not converge and its sign is not stable. The bracket endpoints are two in-family cells
(`cl060_h2h_k8x1376_vs_deploy_k4x688` 16.74; `width_k4x2752_…_b119e9` 19.35). Importing another
cell's **effect size** is forbidden; a **unit conversion** whose endpoints are both stated, both
in-family, and carried as a visible range is the honest alternative to dividing by ~zero.

---

## §5 — WHAT NO BRANCH DOES

1. **No branch reports a production result.** 2752 is the screening budget; production is 11008.
   **Screens aim, they don't verdict.**
2. **No branch ranks the shapes against each other.** Disjoint deck ranges (§1, [`DESIGN.md`](DESIGN.md) §5.1).
3. **No branch says anything about shape C** — it is not run ([`DESIGN.md`](DESIGN.md) §3.3), and a
   C-shaped mechanism can be real while every cell here reads null.
4. **No branch treats A and D as independent** (§4.2).
5. **No branch generalizes from the mid weight to the family.** One weight per shape; the `×3`
   points are unrun.
6. **No branch reads a D-null as "farms don't matter".** The measured one-ply sibling-Δ for `T_D` is
   ~0 at 94.6% of the census positions ([`DESIGN.md`](DESIGN.md) §3.2 v): a D-null is
   *"no measurable effect at 2752, from a term that is one-ply-flat on this corpus"* and nothing more.
7. **No branch edits `governance/PRODUCTION.yaml`**, no branch opens a champion-of-record
   discussion, and no firing branch adopts anything. The adoption chain is four links long and
   this screen is link 1 (§4's `PROMOTE-<shape>`).
8. **No branch treats a within-lineage margin as evidence of better PLAY.** An invasion term is
   built to exploit a blindness of the incumbent champion; beating that champion is consistent
   with exploiting it rather than improving on it, and nothing inside the lineage can tell the two
   apart. Only the external-validation link can.
9. **No branch uses the ms/move ratio as evidence of anything but cost** (§4.3 item 6).
10. **No branch pools this band with any other** (CL-068; band identity is load-bearing).
11. **No branch re-derives the weights.** They are frozen in [`DESIGN.md`](DESIGN.md) §3.2 and the
    derivation is reproducible, not revisable, after the blind commit.

---

## §6 — THE STATED PRIOR, RECORDED BEFORE GAME 1

Written down so the readout can be scored against it rather than fitted to it.

- **Most likely single outcome: `SCREEN-NULL-family-parks`.** The program's base rate on leaf-term
  levers is poor, the caps overlap argues for partial cancellation, and the measured one-ply
  sibling-Δs are small at the frozen weights. If forced to a number: **~55%** that no shape reaches
  `+1σ`.
- **~25%** that at least one shape reaches `BRACKET` (`+1σ ≤ z < +2σ`) — the most likely *positive*
  shape is **A**, which has both the largest firing rate (79.6%) and the largest sibling variation
  (1.60) on the census corpus.
- **~12%** that some shape reaches `PROMOTE` (`z ≥ +2σ`).
- **~8%** that some shape reads `REVERSED` — concentrated on A and D, via the `opp_bonus_cap`
  over-correction mechanism (§2.2).
- **D is the least likely of the three to fire**, on §3.2(v)'s one-ply flatness — and, symmetrically,
  a D reading is the **least informative** about its own mechanism.

⚠️ These are priors, not bars. **No branch condition anywhere in §4 depends on them**, and a result
that contradicts them is a result, not an anomaly.

---

## §7 — THE ADJUDICATOR'S CONTRACT

[`analyze_screen.py`](analyze_screen.py) is the only thing that may declare a branch.

```
analyze_screen.py --selftest
    Executes §3.1's structural test against a REAL manifest read off disk (the smoke
    archive's). REFUSES to run against a synthesized-only fixture. Exit 0 == green.

analyze_screen.py --smoke-mode --cell <dir>
    Runs every gate against an emitted 16-game archive. PASSES (exit 0) iff the ONLY
    failures are §3.5's pinned allowed set. Any other failure => nonzero, and that is a
    LAUNCH BLOCKER.

analyze_screen.py --run-dir <root>
    The real read. Loads all four cells, runs all eighteen gates, recomputes every
    statistic from the raw records as a WITNESS, evaluates §4's branches first-match-wins
    with U-UNREADABLE checked first and G-IDENT applied round-wide, and prints §4.3's
    companion table in full on every branch. Writes ADJUDICATION.json.
```

- **Every bar and every constant lives in [`screen_lib.py`](screen_lib.py), imported by both the
  adjudicator and the launcher's precondition ladder**, so the launcher's in-flight `IDENT`
  pre-check and the adjudicator's `G-IDENT` **cannot drift apart**.
- The launcher pins **only the band** as a numeric literal and asserts it equals
  `screen_lib.BAND`; every other constant is read from the library.
- ⛔ **The adjudicator NEVER writes to `experiments/results.csv`** (the launcher passes
  `--no-results-csv`). Close-out rows are a human act on the six-touch checklist.

**The fired branch IS the authorization to report it.** No further sign-off is needed to state the
outcome — but every *action* a branch licenses (a production H2H, a round-2 bracket, the
solver-pricing instrument) is a **fresh funding decision** and a **fresh pair**.
