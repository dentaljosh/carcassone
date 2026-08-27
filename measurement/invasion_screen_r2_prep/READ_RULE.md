# READ_RULE — invasion-risk term family, round-2 bracket at 2752

**STATUS: FROZEN, NOT LAUNCHED (2026-08-27).** No cell has run.

Pair: [`DESIGN.md`](DESIGN.md) + this file. Adjudicator: [`analyze_screen.py`](analyze_screen.py).
Bars and cost figures have **exactly one implementation**, [`screen_lib.py`](screen_lib.py); this
file is the binding prose and the launcher pins only the band. **The pair is law** — a launcher or
an adjudicator that disagrees with this file is a code defect; the pair does not move.

⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every number below exists before any
game does.

**Inheritance.** This is round 1's read rule ([`../invasion_screen_prep/READ_RULE.md`](../invasion_screen_prep/READ_RULE.md))
adapted. Every bar is carried **verbatim** — `PROMOTE` at `+2σ`, `BRACKET` at `+1σ`, `REVERSED` at
`−2σ`, `G-SAT [0.35, 0.65]`, `G-N` at 2%, the `[0.70, 1.43]` dispersion flag, the
`[16.74, 19.35]` elo/pt bracket, `RECON` at rel 1e-6 / abs 1e-9. **Not one bar moved.** What
changed is what round 2's shape forced: a per-cell two-sided `G-LEAF`, a per-cell `G-INVASION` and
`G-CAPFWD`, `G-WHEEL-SAME` in `G-IDENT`'s slot, `G-HOST` for the frozen two-box assignment, a
bracket read with a pre-registered contrast, and a defence reading for shape C. **Nineteen gates,
not round 1's eighteen.**

---

## §0 — WHAT THIS ROUND IS, STATED BEFORE THE ANSWER

Seven cells at the 2752 screening budget on band `152000000000`, each on its own disjoint 400-deck
range. **Four** bracket the OFFENCE shapes at `×⅓` and `×3` of round 1's frozen mids, against the
**plain champion**. **Three** screen the DEFENCE shape C at `gamma 0.08 / 0.23 / 0.69` against a
**SHAPE-B AGENT** — because [`SHAPES.md`](../invasion_term_build/SHAPES.md) §3 says a C cell against
an opponent that does not invade is a guaranteed-uninformative null.

⭐ **THE ROUND RUNS ON TWO BOXES, CONCURRENTLY, AND THE ASSIGNMENT IS FROZEN HERE**
([`DESIGN.md`](DESIGN.md) §6.5): the **local** box runs the four A/B cells, the **laptop** runs the
three C cells, whole cells per box, `G-HOST` enforcing it. ⭐ **Shapes are assigned WHOLE, so every
pre-registered statistic in this document is computed WITHIN one box** — no branch, no contrast and
no check ever compares a local cell to a laptop cell.

It decides **what gets funded next**, and nothing else:

- an A or B cell that fires earns **one** production-budget H2H — a separate pair, a separate band,
  a separate funding decision;
- ⛔ **a C cell that fires earns something DIFFERENT and strictly smaller** (§4.6): a partnered
  follow-up inside its own family. **C never enters the adoption chain**, because its opponent is
  not the champion of record;
- a round in which nothing reaches `+1σ` **parks the family** — with the bound stated, and with
  §2.3's power caveat attached, because this round is powered to detect **scaling**, not to confirm
  round 1's mid;
- a wheel that is not round 1's **voids the round** (§3.4).

⛔ **A NULL IS A BOUND, NOT A ZERO**, and §4's `FAMILY-PARKS` branch is required to print the bound
and is forbidden from printing "no effect".

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

**Sign:** `D_C > 0` ⇒ the **candidate won**. On an A/B cell that is the invasion term beating the
plain champion. ⭐ **On a C cell it is the DEFENCE beating the INVADER** — a different proposition,
and §4.6 is the mandatory prose. `D_C < 0` is a reportable finding (`REVERSED`), never a gate
failure.

⛔ **EVERY BAR IN §4 IS EVALUATED AT THE CELL'S OWN REALIZED `SE_C`.** The `σ_D = 14.67` sizing
model of [`DESIGN.md`](DESIGN.md) §4.1 is used for **power arithmetic only** and never as a
denominator in a branch test. The adjudicator prints realized vs modelled SE per cell and **FLAGS**
a ratio outside `[0.70, 1.43]` as a dispersion anomaly — reported, never a branch input.

⚠️ **A LOW-END FLAG IS EXPECTED AND IS NOT AN ANOMALY.** Round 1 realized `0.714 / 0.816 / 0.810 /
0.834` against this model, hugging its floor. A low flag means "TIGHTER than modelled"; the HIGH
end is the concerning direction, and the adjudicator prints which. The band does not move for that.

### §1.1 — cross-cell contrasts

⛔ **NO CROSS-CELL CONTRAST IS A BRANCH INPUT.** The seven cells run on **disjoint** deck ranges
([`DESIGN.md`](DESIGN.md) §5.1). `D_{A_HIGH} > D_{B_HIGH}` is not a finding, is not printed as a
ranking, and cannot promote or demote anything. Each cell is adjudicated **against zero, on its own
decks**.

⭐ **ONE PRE-REGISTERED EXCEPTION, AND IT IS NOT A BRANCH INPUT EITHER:** the within-shape
low-vs-high contrast of §4.5. It is a SHAPE reading and a round-3 input.

### §1.2 — ⛔ ROUND 1's MIDS ARE A DESCRIPTIVE OVERLAY. FULL STOP.

Round 1's `A_MID` (+0.5238, z 0.99993), `B_MID` (+0.7575, z 1.2653) and `D_MID` (−0.2913,
z −0.4900) were played on band **`151000000000`**. This round is on **`152000000000`**.

⛔ **NEVER POOLED. ⛔ NEVER z-COMBINED. ⛔ NEVER A BRANCH INPUT.** CL-068 measured **1.8–2.2×
over-dispersion** on cross-band contrasts, in **both** the elo and the deck-paired-margin
statistics, with an identity control exonerating the harness and the "different decks" explanation
arithmetically excluded (the per-deck SEM already prices the deck draw). An r1-mid-vs-r2-endpoint
contrast is exactly that class — and it is the single most tempting cross-band pool this program
has been offered, because the r1 mids are precisely the interior points A's and B's ladders are
missing.

**They are PLOTTED on the ladder (§4.5b) and nothing more.** The scaling question is answered
**within round 2** by §4.5's contrast.

---

## §2 — UNITS AND POWER, STATED BEFORE ANY NUMBER

### §2.1 — the sizing model, carried unchanged

`σ_D` inverted off seven `n=400`-deck, deck-paired, `fixed_v1`+R9, rust-backend cells in
[`../../experiments/results.csv`](../../experiments/results.csv): median `13.15` · closest analogue
`13.60` · **max `14.67`**. **This pair sizes on the MAX**, as round 1 did.

```
    n = 400 decks:  SE(model)    = 0.7335 pts    2 sigma = +-1.467 pts
    n = 400 decks:  SE(realized) = 0.5987 pts    2 sigma = +-1.197 pts
```

Round 1 realized `σ_D` of `10.48 / 11.97 / 11.89` on its three arms. The conservative model is kept
anyway, deliberately: it **under**-states this round's resolution rather than over-stating it,
which is the direction a screen that decides funding should err in. Both are published.

### §2.2 — ⭐ THE MOST IMPORTANT SENTENCE IN THIS DOCUMENT

**THIS ROUND IS POWERED TO DETECT SCALING, NOT TO CONFIRM ROUND 1's MID.**

If shape B's effect is **flat** at `+0.76` pts/deck — the size round 1 measured at `alpha 0.09` —
then a round-2 B cell reaches `+2σ` with probability **~24%** even at round 1's realized dispersion
(`~18%` at the frozen model). [`DESIGN.md`](DESIGN.md) §4.2's table is mandatory output.

⛔ **CONSEQUENCE, FROZEN HERE:** a `FAMILY-PARKS` outcome **does not refute round 1's `BRACKET`**.
It bounds the **growth** of the effect with weight. Any readout that says round 2 "failed to
replicate" round 1 is wrong on the power arithmetic, not merely on the emphasis.

### §2.3 — the honest prior on each shape

1. **A overlaps `opp_bonus_cap = 8`** ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §1) — the
   leaf already discounts opponent-held value once. At `beta = 0.36` shape A contributes `2.16`
   leaf points, **123% of `G`**, the champion leaf's entire sibling-move spread. That is not a tilt
   on the leaf; it is a re-weighting of it, and an over-correction reads as `REVERSED`.
2. **B is the one shape that fired**, and `×3` is where a real effect would show if it scales at
   all. It is also where B's cap starts to matter differently: at `alpha 0.27` a qualifying pair
   contributes up to `0.27 × 11.0 = 2.97` points.
3. **C has never been screened**, and its own build measured a caveat that constrains the read:
   `frac = open_n / edges` makes the charge a **rate × a value**, so shape C does **not** rank a
   large open city above a small fully-open feature (false in 8 of 23 one-sided census cases at the
   side aggregate, 15 of 23 per-feature). A C null or reversal is consistent with the term being
   right in kind and wrong in normalisation.
4. ⛔ **THE R1/R2 OFFLINE FUNNEL FOR THIS TERM WAS CLOSED BY F4**
   ([`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md)): *"every R2 winner incl.
   `H4_DECISIVE_FARM` is F4-REFUTED (witness −2.10, z −2.57); the R1/R2 corpus licenses NOTHING for
   this term. Its case is now the E4-vs-human record ONLY … Any pricing of this term needs an
   out-of-family strong judge first."* This pair is a **game-play head-to-head**, not the offline
   funnel F4 refuted, so it is a legitimate and different instrument — **but that sentence is why
   §4's `PROMOTE` chain makes external validation mandatory rather than advisory, and it is a
   recorded reason to expect a null here.**

§4's table is therefore **symmetric and two-sided**, not a one-sided confirm.

---

## §3 — PRECONDITIONS (every gate individually fail-closed; ABSENT is FAIL)

Each gate is read at the manifest top level, then at `config.*`; the adjudicator **reports which
address resolved**. **Any FAIL ⇒ `U-UNREADABLE`** for the affected cell — and for `G-WHEEL-SAME`,
for the whole round (§3.4).

⚠️ **`config.*` lives in `manifest.json`, not `summary.json`** — verified on a real archive, and
the subject of round 1's execution-layer deviation **IS-D1**, in which a launcher-side reader took
the config block off `summary.json`, got `{}`, and fail-closed voided a **healthy** cell while a
vacuous `{} == {}` made a second conjunct pass and hid the cause. The adjudicator and the
launcher's per-cell pre-check both carry the fixed address.

| id | proposition | address | fail on |
|---|---|---|---|
| `G-BAND` | per cell: `config.band_seed_start` == that cell's frozen `seed_start`; `config.n_decks == 400`; `config.seatings_per_deck == 2` | cell `summary.json` → `config.*` (manifest top level as fallback) | any mismatch |
| `G-DECKS` | every realized `deck_seed` lies inside **that cell's own** range; every counted deck carries **both** `a_seat` 0 and 1; `n_common == 400`; **and no seed appears in two cells' archives** | adjudicator's own collection over the raw `seed*_a*.json` records, across all seven cells | any seed outside its cell's range; any deck counted at one seat only; `n_common` mismatch; **any cross-cell seed overlap** |
| `G-SINGLEVAR` | **WITHIN each cell**, the candidate and opponent config blocks differ in **NOTHING** except that cell's pre-registered term knobs. Two conjuncts: **(a)** the alias-aware side-by-side diff of the search/endgame/budget blocks (`config.champion.*` vs `config.opponent.*`, aliased pairwise — see §3.3) is **EMPTY**; **(b)** the leaf diff `config.cand_leaf_cfg` vs `config.opp_leaf_cfg` equals **EXACTLY** the cell's frozen key set: `A_*` → `{invasion_beta}`; `B_*` → `{invasion_alpha, invasion_alpha_cap}`; ⭐ `C_*` → **`{invasion_alpha, invasion_alpha_cap, invasion_gamma}`** | cross-side diff within one cell's own `manifest.json` `config` block | ANY other differing key, in either conjunct. Set equality is **two-sided**: an extra differing key fails, and an expected-but-identical key fails too. ⭐ **ROUND 2's STATEMENT OF THE SINGLE-VARIABLE PROPERTY IS "the two sides differ in EXACTLY the pre-registered term knobs", NOT round 1's "the cell's ONE knob"** — on a C cell the candidate carries gamma and the OPPONENT carries alpha + cap, so the set has three members and a two-member diff there means the env regime did not reach the harness. ⚠️ Exact `!=` on flattened values; **no float tolerance** |
| `G-LEAF` | ⭐ **PER-CELL AND TWO-SIDED.** Four conjuncts, all from the cell's own frozen spec, implemented ONCE in `screen_lib.leaf_gate()`: **(a)** `config.opp_leaf_hash` == that cell's **pinned opponent hash** — `a36d2e15a3b3d71d` on A/B, **`42adadc988784b44` on C**; **(b)** `config.cand_leaf_cfg.v29_meeple_curve` == `[-10.0,-5.0,-1.25,0.0,2.5,3.75,5.0,6.25]`; **(c)** `config.cand_leaf_hash` == that cell's **OWN PINNED HASH, exactly** — `A_LOW f8c0f04092734f9e` · `A_HIGH f6ce81145cbd5102` · `B_LOW f5b7a26216794290` · `B_HIGH 1a42effad7066c0b` · `C_LOW a6ab04dbb69ad29e` · `C_MID 897c21aca11b6fbd` · `C_HIGH df34cb874fea6273`; **(d)** the two sides are **DIFFERENT leaves** | `manifest.json` → `config.cand_leaf_hash`, `config.opp_leaf_hash`, `config.cand_leaf_cfg` | any deviation. ⛔ **THIS GATE IS THE ONLY THING LEFT STANDING, AND THAT IS WHY IT IS EXACT.** `--allow-leaf-hash-drift` is a **single** flag that downgrades `_assert_netprior_leaf` to a warning on **BOTH** sides (`eval_fair_puct.py:3763` candidate, **`:3777` opponent**), and **round 2 passes it on all seven cells** — so the harness's own hash assertion enforces nothing anywhere. Round 1 kept a free extra check by withholding the flag on its IDENT cell; round 2 has no such cell. **And on a C cell "the opponent leaf drifted" is EXPECTED and therefore not a tell** — only exact equality against a pre-registered pin distinguishes "drifted to the shape-B agent" from "drifted to something else". Conjunct (d) exists because on a C cell BOTH pins are nonzero-invasion leaves, so "not the champion" is no longer a proxy for "the swap happened" |
| `G-INVASION` | ⭐ **BOTH SIDES, per cell.** In `config.champion.leaf_cfg` (the candidate's FULL asdict): that cell's own knob at **exactly** the frozen value and **every other invasion field at its default**. In `config.cand_leaf_cfg`: the non-default invasion fields equal the cell's frozen candidate set. In `config.opp_leaf_cfg`: the non-default invasion fields equal the cell's frozen **opponent** set — **`{}` on A/B, `{invasion_alpha: 0.09, invasion_alpha_cap: 11.0}` on C** | `manifest.json` → `config.champion.leaf_cfg`, `config.cand_leaf_cfg`, `config.opp_leaf_cfg` | any knob at the wrong value; any second nonzero weight; an invasion key on an A/B opponent; ⭐ **an EMPTY opponent block on a C cell** — that means the env regime did not reach the harness and the cell played the plain champion, which is the one cell SHAPES.md §3 forbids. ⚠️ `_leaf_dict` **drops a field while it holds its default**, so "absent" IS "default" and both readings pass |
| `G-CAPFWD` | ⭐ **BOTH SIDES.** The **biconditional**, on each side independently: `invasion_alpha_cap` is present-and-nonzero **iff** `invasion_alpha` is present-and-nonzero; likewise `invasion_stub_max_tiles != 2` ⟹ `invasion_alpha != 0` | `manifest.json` → `config.champion.leaf_cfg` + `config.opp_leaf_cfg` | either direction violated on either side. ⚠️ **ROUND 2 CHECKS THE OPPONENT TOO** because the C cells' opponent is the only reference leaf in this program's history to carry a nonzero alpha — and it carries a cap with it. `rust_agent.leaf_config_rs` (`rust_agent.py:181-185`) forwards the cap ONLY when alpha is nonzero, so a side with a cap and no alpha runs a leaf the manifest does not describe |
| `G-WHEEL` | top-level `carc_rs_build` present and non-null; `carc_rs_binary_sha` present; `mixed_builds == false`; the launcher's `WHEEL_PROBE.json` records **every** required-true key (§7 — including ⭐ `opp_side_forward_ok`, new in round 2, and `wheel_is_round_1s`); **AND the ANCESTRY conjunct**: the git rev embedded in `carc_rs_build` must satisfy `git cat-file -e <rev>:rust/carc/carc-core/src/leaf/invasion.rs` **and** `git merge-base --is-ancestor <rev> HEAD` | `manifest.json` top level; `WHEEL_PROBE.json`; live `git` | absent; null; `mixed_builds == true`; a missing or failed wheel probe; a rev at which `invasion.rs` does not exist; a non-ancestor rev. ⚠️ **ROUND 2 STATES WHAT THE ANCESTRY CONJUNCT ACTUALLY PROVES, and it is less than round 1 claimed** ([`DESIGN.md`](DESIGN.md) §3.1a): the embedded rev is the **repo rev at manifest-write time**, not a compiled-in value, so it proves **the tree the games ran from** carried the family — not that the **wheel** did. Still worth having; largely duplicated by `G-REV`; ⛔ **no branch may claim it proves a wheel identity**. The wheel identity question is `G-WHEEL-SAME`'s |
| `G-WHEEL-SAME` | ⭐ **THE ROUND-LEVEL GATE — round 1's `G-IDENT`, in the slot it vacated.** Every manifest's `carc_rs_binary_sha` == **`a9ac686bca1417f9`**, the wheel round 1's IDENT cell PASSED on — **on BOTH boxes** | `manifest.json` → `carc_rs_binary_sha` | any other value; ABSENT. ⛔ **A FAIL ON ANY CELL VOIDS ALL SEVEN** — see §3.4. ⛔ Keyed on `carc_rs_binary_sha` **alone**: `carc_rs_build` embeds the repo rev at call time and is NOT a wheel discriminator (round 1's own smoke and cell archives carry different build strings and the same binary sha — [`DESIGN.md`](DESIGN.md) §3.1a). It is reported beside it as INFORMATIONAL. ⭐ **AND THIS IS WHY THE TWO-BOX ROUND SHIPS A WHEEL FILE RATHER THAN BUILDING ONE** ([`DESIGN.md`](DESIGN.md) §0(f), §7): the sha is box-local *by build* — two boxes COMPILING identical source produce different bytes — so the executor `scp`s and `pip install`s **the same `.whl`** on both, the sha is identical on every cell regardless of host, and this gate passes on both. ⛔ **A laptop-local `maturin build` produces a different sha and the gate REFUSES — correctly**, because a rebuilt wheel is one whose weight-0 identity this program has never checked |
| `G-HOST` | ⭐ **THE FROZEN CELL→BOX ASSIGNMENT (NEW IN ROUND 2).** The manifest's `host` must be the box this cell is frozen to: `A_LOW A_HIGH B_LOW B_HIGH` → **local**, `C_LOW C_MID C_HIGH` → **laptop** ([`DESIGN.md`](DESIGN.md) §6.5). Matched as a normalised-substring test, not an equality against a pinned string — this program's boxes report different hostnames under Windows vs WSL vs Pop!\_OS on the *same* machine (`laptop` / `laptop-wsl` / `laptop-pop`), and pinning one spelling would void a healthy cell for a dual-boot reason that has nothing to do with the measurement | `manifest.json` → `host` (`config.host` as fallback) | any cell whose `host` names the other box; ABSENT. ⚠️ **THE MANIFEST'S `host` IS THE ONLY HOST WITNESS THE HARNESS EMITS** — the per-game records carry no host field at all (verified against a real round-1 record at freeze). So this gate proves the cell's SEALING PASS ran on the assigned box; it cannot prove every individual record did. ⛔ **The real protection is structural:** the two boxes hold DISJOINT CELLS and therefore DISJOINT `--out-subdir`s, so `--shared-claim` has nothing to race over between them, and the launcher refuses a foreign cell before a game starts. This gate catches the launcher-level version — a box handed the wrong `--host` |
| `G-RULES` | `rules_profile.name == "fixed_v1"` **AND** `r9_env_ok == true` **AND** `r9_env_observed == true` | `summary.json` / `manifest.json` → `rules_profile.*` | anything else. (Non-inverted: `fixed_v1` wants R9 **ON**) |
| `G-BACKEND` | `config.backend.name == "rust"`, `.requested == "rust"`, `mixed_builds == false`, **AND `converted_sides == ["candidate", "opponent"]`** | `manifest.json` → `config.backend.*` | any leg not rust-resolved; `converted_sides` missing `"opponent"`. ⚠️ **ROUND 2 NEEDS THE OPPONENT LEG AS MUCH AS THE CANDIDATE'S**: the C cells' *opponent* carries a nonzero weight, so an unconverted opponent leg would either raise `NotImplementedError` or (on a stale-wheel path) silently play the plain champion — the cell SHAPES.md §3 forbids, reading as a null |
| `G-BUDGET` | **both** sides `(k_dets, sims_per_det, total_sims) == (4, 688, 2752)`, and `k × s == total` on both | `manifest.json` → `config.champion.*` / `config.opponent.*` | any deviation, or a product that does not multiply out. ⚠️ The harness's non-fatal `[warn] … deviates from governance/PRODUCTION.yaml` is **EXPECTED** and is not a gate input |
| `G-TIEARB` | the root tie-arbiter is ABSENT/disarmed on BOTH sides. **Three** conjuncts: **(a)** `cand_tiearb.enabled` absent or `false`; **(a2)** **every terminal key named exactly `tiearb_enabled`, anywhere in either document, is `false`**; **(b)** **no CONTAINER (non-terminal) path segment whose name contains `tiearb` exists outside the `cand_tiearb` subtree** | `manifest.json` / `summary.json` | `cand_tiearb.enabled == true`; any `tiearb_enabled` leaf true; OR any `tiearb`-named CONTAINER segment outside `cand_tiearb`. ⚠️ **(a2) AND THE "CONTAINER" QUALIFIER IN (b) ARE ROUND 1's FREEZE-TIME CORRECTION**, made against a real emitted manifest: a healthy archive emits `config.champion.tiearb_enabled = false` (a *terminal* key containing `tiearb`), so an undifferentiated rule would have voided every healthy cell. Carried verbatim |
| `G-EXACT` | `config.endgame.exact_k == 2`, `mode == "marginalized"`, identical on both sides | `manifest.json` → `config.endgame.*` / `config.opponent.endgame.*` | any deviation. K=3/4 are clairvoyant-only |
| `G-REV` | `config.code_rev` **names the same commit as** ⭐ **THAT CELL'S OWN BOX's** `PINNED_SRC_REV` — a case-insensitive PREFIX match of at least 7 hex; **AND** that box's `SRC_CLEAN.jsonl` records `src/ engine/ scripts/ rust/ tests/ pyproject.toml setup.py` **CLEAN at every recorded boundary**, with a `pre-flight` boundary and an `after-…` boundary for **each cell that box ran**; **AND ⭐ ALL SEVEN CELLS SHARE ONE `code_rev` ACROSS BOTH BOXES** | ⭐ `<out-root>/_provenance/<box>/` (falling back to the adjudicator's own dir for a single-box run or the smoke): `PINNED_SRC_REV`, `SRC_CLEAN.jsonl`; plus `manifest.json` → `config.code_rev` (top-level `code_rev` as fallback) | rev mismatch; `PINNED_SRC_REV` absent; `SRC_CLEAN.jsonl` absent, empty or unparseable; any boundary with `src_clean != true`; a missing `pre-flight` or per-cell `after-…` boundary; **any cross-cell rev disagreement — INCLUDING ACROSS THE TWO BOXES**. ⭐ **THE CROSS-BOX CONJUNCT IS WHAT MAKES SEVEN CELLS ONE ROUND RATHER THAN TWO.** The laptop cannot reach GitHub, so its tree is synced by `git bundle` + `git reset --hard` to the launch rev (`reference_offline_git_bundle_sync`); this conjunct is the check that the sync actually happened. Without it the laptop could run stale code and the round would be mixed-rev across machines — the `track_d2_prep` defect with an extra machine. ⭐ **THE `-dirty` SUFFIX IS INFORMATIONAL, NOT FATAL** (round 1's amendment round 2): `run_manifest.code_rev()` computes dirtiness over the **WHOLE TREE**, and the main tree is perpetually dirty with measurement logs, so a fatal reading voided every healthy run. Per `track_d2r4_prep`'s `G-TOOL` precedent the whole-tree marker is reported and the FATAL, code-path-scoped judgment is `SRC_CLEAN.jsonl`'s. ⚠️ **A mid-round tree move is the `track_d2_prep` defect and this round is SEVEN cells long** — the window is nearly twice round 1's |
| `G-BLIND` | Four conjuncts, evaluated per cell against ⭐ **that cell's own box's** `BLIND_PROOF.json`: (a) `BLIND_COMMIT` holds a 40-hex sha and every cell's manifest carries `stamps.BLIND_COMMIT` equal to it; (b) that sha is an **ancestor of HEAD**, by a **live** `git merge-base --is-ancestor`; (c) it is the commit that **introduced this pair's FROZEN banner**; (d) `BLIND_PROOF.json` exists, names the SAME blind commit, and its `is_ancestor_of_head` **agrees with the live re-check** | `BLIND_COMMIT`, `BLIND_PROOF.json`, live `git`, `config.stamps` | the literal `PENDING`; a non-ancestor; absent; a commit that did not introduce the banner; a proof that is absent, names a different sha, or disagrees with the live re-check; a cell stamped with a different sha |
| `G-N` | per cell: **800** games scored; `n_failed == 0`. A nonzero failure rate **< 2%** is **REPORTED, not silently absorbed**, and does not by itself void (the `b32v64` 0.100% rust-panic-class precedent). `n_common >= 80%` of 400 | `summary.json` → `n`, `n_failed`; adjudicator's own `n_common` | short of 800; failure rate ≥ 2%; `n_common` below the floor |
| `G-SAT` | per cell, the realized candidate win-rate lies in `[0.35, 0.65]` | `summary.json` → `winrate` | outside. **A RAIL check, not a strength bar.** Both sides are the same search differing only by the pre-registered leaf terms; a win-rate outside this window means the two sides are not the agents this design says they are, and the margin would be a rail reading |
| `RECON` | the **analyzer** values (read verbatim off `summary.json`) and the **witness** values (recomputed from scratch from the raw records by an independent re-implementation in [`screen_lib.py`](screen_lib.py)) agree within `rel 1e-6 / abs 1e-9` on **every** checked statistic, per cell: `paired_mean_margin`, `paired_z`, `n_paired`, `winrate`, `elo` | `summary.json` vs raw records | disagreement beyond tolerance on any statistic. **The recomputation is a WITNESS, never a branch input** — it can only void, never move, the number |

### §3.1 — the structural test, applied to every gate above, BEFORE any outcome is known

Every gate is subjected to four questions, and the answers are **executed, not reasoned**:

1. **Is it readable?** Does the address exist in a manifest the harness actually **emits**? —
   enforced by [`DESIGN.md`](DESIGN.md) §9's rule that the smoke leg ends by running this pair's own
   adjudicator against the emitted smoke archive.
2. **Is it satisfiable?** Can a healthy run pass it? — every gate outside §3.5's pinned allowed set
   must PASS on the 16-game smoke.
3. **Is it falsifiable?** Is there a real defect it would catch? — recorded per gate in the "fail
   on" column.
4. **Is ABSENT a FAIL?** — yes, for all eighteen, without exception.

⭐ **AND QUESTION 2 EARNED ITS KEEP AGAIN AT THIS FREEZE.** `analyze_screen.py --selftest` runs
against a REAL emitted archive and **refuses a synthesized-only fixture** — and it **failed** the
first implementation of `G-WHEEL-SAME`, which had required `carc_rs_build` to match as well as the
binary sha. Round 1's own two archives disagree on the build string and agree on the sha
([`DESIGN.md`](DESIGN.md) §3.1a). **The gate was wrong; the archive was right; the gate moved.**
That is what a satisfiability control is for, and it is why a brand-new gate must be pointed at
real emitted output rather than at a fixture built to agree with it.

### §3.2 — the address-resolution rule

A gate's value is looked up at its named address; if `MISSING`, at the declared fallback container
(`config.*`, then manifest top level), and the adjudicator **prints which address resolved** for
every gate. **A value found at NO address is `ABSENT`, and `ABSENT` is `FAIL`** — never a skip,
never a default.

### §3.3 — `G-SINGLEVAR`'s alias table, fixed here

⭐ **VERIFIED AGAINST A REAL EMITTED MANIFEST, NOT WRITTEN FROM THE DESIGN.** Round 1's first draft
named `config.opponent.c` / `.tau_p` / `.leaf_quantize` / `.final_select`; on a real archive those
are `None` or absent, because the opponent's search knobs are emitted one level down under
**`config.opponent.champ_cfg.*`**. A gate written against a manifest the design *described* would
have voided every healthy cell on four `MISSING` aliases. Carried corrected.

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
config.cand_leaf_cfg               config.opp_leaf_cfg                     differ in EXACTLY the cell's frozen key set
```

⚠️ **An alias whose opponent-side address is `MISSING` is a FAIL, not a skip.** If a future harness
renames one, the gate voids the cell — the recoverable direction — and the fix is to amend the
table in a fresh pair, never to drop the row.

⚠️ **A cross-cell literal config diff is computed and PRINTED as a DIAGNOSTIC.** It is **not** a
gate: cells legitimately differ in band seed, output path, claim host, leaf knob and — new in round
2 — the invasion env and therefore the opponent leaf.

### §3.4 — `G-WHEEL-SAME` voids the ROUND, not the cell

If `G-WHEEL-SAME` fails on **any** cell, **all seven cells adjudicate `U-UNREADABLE`** and no `D_C`
is reported as a result for any of them.

**Why the round and not just the cell:** the proposition is about **the wheel the round ran on**,
not about one archive. Round 2 carries **no IDENT cell** — it inherits round 1's game-level
weight-0 identity proof ([`DESIGN.md`](DESIGN.md) §3.1) — and that inheritance is valid only while
the wheel that proved it is the wheel that plays. A rebuilt wheel is exactly the event that could
move a zero-weight leaf, and no A/B/C reading could then be attributed to the term rather than to
the plumbing. Reading past it would be round 1's `track_d2_prep` mistake with an extra step.

⛔ **A CHANGED WHEEL RE-OWES AN IDENT CELL.** The remedy is not to relax the gate: it is to add an
identity cell (400 decks / 800 games at round-2 cell size, ≈15 core-h) on a fresh sub-range and
re-freeze, **or** to reinstall the wheel round 1 ran. The launcher asserts the same predicate at
pre-flight, so this is normally caught before a single game.

⚠️ **THE CONVERSE IS NOT TRUE.** A passing `G-WHEEL-SAME` carries forward a proof that the plumbing
transmits a **zero** faithfully. It does **not** prove a nonzero weight reaches the rust leaf —
that is `G-INVASION`'s, `G-CAPFWD`'s and `G-WHEEL`'s job, and `G-LEAF`'s two-sided pins are the
cheap cross-check. **Round 2 leans on those more than round 1 did, not less**, because round 2
passes `--allow-leaf-hash-drift` on every cell (§3's `G-LEAF` row).

### §3.5 — the smoke leg's PINNED ALLOWED SET

On the 16-game throwaway archive, `analyze_screen.py --smoke-mode` **must PASS iff the only failing
gates are these**:

```
G-BAND      G-DECKS      G-N      G-SAT      G-HOST      RECON/n_paired
```

Everything else — `G-SINGLEVAR`, `G-LEAF`, `G-INVASION`, `G-CAPFWD`, `G-WHEEL`, **`G-WHEEL-SAME`**,
`G-RULES`, `G-BACKEND`, `G-BUDGET`, `G-TIEARB`, `G-EXACT`, `G-REV`, `G-BLIND` — **must PASS on 16
games, on each box's own smoke.** A failure outside the allowed set is a **launch blocker**, not a
readout surprise.

⭐ **THIS SET IS STILL SMALLER THAN ROUND 1's, AND THAT IS DELIBERATE.** Round 1's set also excused
`G-IDENT`, a gate round 2 does not carry at all. Round 2's replacement, `G-WHEEL-SAME`, is **NOT**
excused: each box's smoke runs on the same wheel that box's cells will, so it must pass there — and
it is the check that carries round 1's IDENT PASS forward in place of an identity cell.

⚠️ **`G-HOST` IS EXCUSED FOR A MECHANICAL REASON, NOT A SUBSTANTIVE ONE.** `--smoke-mode` is handed
a *directory*, and each box smokes a **different** cell's config (laptop `C_MID`, local `B_LOW`), so
the smoke cell's frozen `box` is not necessarily the box that ran the archive. ⛔ **The property is
not left unchecked:** `run_cells.sh` refuses to run any cell outside `cells_of_box(--host)` **before
a game starts**, the table pre-flight cross-checks the box/W/share-mount/smoke assignment against
`screen_lib`, and `G-HOST` is fully enforced on every **real** cell.

⛔ **AND EACH BOX SMOKES SEPARATELY.** Two boxes, two wheel installs, two checkouts, two share
mounts — one smoke cannot speak for both. [`DESIGN.md`](DESIGN.md) §9 has the table.

⛔ **`G-BLIND` AND `G-REV` ARE NOT EXEMPT ON THE SMOKE.** Round 1 discovered the hard way that a
smoke run before `PINNED_SRC_REV` exists fails `G-REV` on *"ABSENT — ABSENT is FAIL"*, and that an
unstamped smoke fails `G-BLIND` on *"stamp mismatch"*. **Both were fixed by supplying the witness,
never by widening this set**: `run_cells.sh::run_smoke` writes its own `PINNED_SRC_REV`,
`BLIND_PROOF.json` and `SRC_CLEAN.jsonl` boundaries, and passes `--stamp-key BLIND_COMMIT=<sha>`
exactly as a real cell does. Both fixes are carried here verbatim. **ABSENT-is-FAIL stays sacred.**

---

## §4 — THE BRANCHES

**Order of evaluation: `U-UNREADABLE` first (§3), then the round-level table below,
first-match-wins.**

Per cell, the raw ladder position is:

```
U-UNREADABLE   any gate FAIL on the cell (or a round-wide G-WHEEL-SAME fail), or no z at all
PROMOTE        z_C >= +2.0
BRACKET        +1.0 <= z_C < +2.0
REVERSED       z_C <= -2.0
NULL           everything else  (-2.0 < z_C < +1.0)
```

⛔ **THE LABEL MEANS SOMETHING DIFFERENT ON A C CELL** — `PROMOTE` there is not a promotion into
the adoption chain. §4.6 is the mandatory reading and the round-level table re-labels it.

### The ROUND-LEVEL table, first-match-wins

```
U-UNREADABLE      any cell unreadable; G-WHEEL-SAME voids all seven
PROMOTE-<shape>   some A or B cell reads z >= +2.0
DEFENDS-C         no A/B promote, but some C cell reads z >= +2.0
BRACKET-CONTINUE  nothing reaches +2.0, but something reads z >= +1.0
REVERSED-<shape>  nothing reaches +1.0, but some cell reads z <= -2.0
FAMILY-PARKS      every cell reads z < +1.0 and nothing REVERSED
```

Multiple shapes may appear in a `PROMOTE-` or `REVERSED-` label, comma-separated in cell order.
⛔ **Two shapes listed is NOT two confirmations of one effect and NOT an additive claim** — each
cell was adjudicated against zero, on its own disjoint decks, and §1.1 forbids any cross-cell
contrast as a branch input.

### `PROMOTE-<shape>` — an A or B shape earns one production-budget H2H

```
FIRES on a cell C in {A_LOW, A_HIGH, B_LOW, B_HIGH} iff
      all gates PASS  (including G-WHEEL-SAME, round-wide)
  AND z_C >= +2.0     at the cell's OWN realized SE_C
```

**What it licenses, exactly one thing:** a request to fund **one** head-to-head at the production
budget (`k8×1376 = 11008`), `n ≥ 400` decks paired, **a separate pair and a separate band**,
**at the weight that fired**.

#### THE FULL ADOPTION CHAIN — all four links, stated before any number

```
1. THIS SCREEN (2752, vs the champion)          -> licenses a production-budget H2H
2. PRODUCTION H2H (11008, vs the champion)      -> licenses an EXTERNAL VALIDATION cell
3. EXTERNAL VALIDATION (vs CARCASUM, the        -> licenses a champion-of-record /
   out-of-lineage ruler)                           PRODUCTION.yaml DISCUSSION
4. THE ONGOING E4 STREAM (a human who ADAPTS)   -> the FINAL HOLDOUT
```

⛔ **LINK 3 IS NOT OPTIONAL AND MAY NOT BE SKIPPED, however large link 2's margin is.**
**Self-play evidence alone never adopts a term.** Two independent reasons, both standing rules:

- `feedback_anchor_before_scaling` — a self-anchored measurement can climb while absolute strength
  regresses; a verdict needs a reference **outside the tuning lineage**, and Carcasum is this
  program's only non-saturated out-of-lineage ruler.
- **The specific hazard of THIS lever:** an invasion term is by construction a term that exploits a
  *blindness in the incumbent champion*, so a term that beats that champion is consistent with
  **exploiting the opponent rather than improving the agent**, and the two are indistinguishable
  inside the lineage.
- **And the program has already said so, for this exact term** — the LEVER_INDEX line quoted in
  §2.3(4). A `PROMOTE` here does not retire that requirement; it schedules it.

**What `PROMOTE` does NOT license:**

- ⛔ no `governance/PRODUCTION.yaml` change and no champion-of-record discussion — link 3 unlocks
  that conversation, not this branch;
- ⛔ **no claim about the shape at any other weight** (§4.7): A and B are **not bracketed** within
  round 2, so a `PROMOTE` at `×3` owes a ladder **extension** before any optimum claim;
- ⛔ the production H2H is **not** a straight adoption test: shape A subtracts from the same objects
  `opp_bonus_cap = 8` already discounts, so adoption owes a **re-sweep of `bonus_cap` /
  `opp_bonus_cap` against the new term** per `feedback_bug_fix_shifts_optima`
  ([`DESIGN.md`](DESIGN.md) §3.5). **The promotion funds a sweep, not an edit. This obligation is
  part of the branch, not a footnote.**

### `DEFENDS-C` — the defence pays against an invader

```
FIRES iff  all gates PASS
       AND no A/B cell reached +2.0
       AND some C cell reads z >= +2.0
```

**Read it as §4.6 requires**, and license only what §4.6 licenses: a **partnered follow-up inside
the C family**, never the adoption chain.

### `BRACKET-CONTINUE` — real enough to keep going, not enough to promote

```
FIRES iff  all gates PASS  AND nothing reaches +2.0  AND some cell reads z >= +1.0
```

**What it licenses:** one round 3, on a **fresh band**, as one funding request. ⛔ It licenses no
production H2H and no claim that any shape works.

**The branch is REQUIRED to name what a round 3 would need and what it would cost**, from the
numbers this round produced — not from an argument afterwards:

1. **Which point**, and why. If the firing cell is at a ladder endpoint (which for A and B it
   always is, §4.7), the named round 3 is an **extension** past that endpoint, not a re-run. If it
   is `C_MID`, the named round 3 is a **re-measure** if §4.7's noise-signature fired, and a finer
   gamma otherwise.
2. **What n**, from `screen_lib`'s own power arithmetic at the **realized** SE, sized to the effect
   actually observed rather than to a hoped-for one. ⚠️ If the observed effect is `≈+0.76`
   pts/deck, honest sizing needs `n ≈ 1500` decks paired for `2σ`, not 400 — and **that number
   should be stated even though it is uncomfortable**, because §2.2 is exactly the trap of
   re-running an underpowered screen and calling the second null a replication.
3. **What it costs**, through `screen_lib.project_cell_cost()` at the realized ms/move — including,
   for a C follow-up, the now-**measured** shape-C figure this round produces.
4. **Whether a round 3 is the right instrument at all.** ⛔ The `BRACKET-CONTINUE` branch is
   explicitly permitted to conclude **"no"** — the family's kill rule hands the ceiling question to
   the solver-pricing instrument, and a third bracket round at 400 decks is not obviously better
   value than that. Recording this option inside the branch is the alternative to discovering the
   argument afterwards.

### `REVERSED-<shape>` — the term measurably HURTS

```
FIRES iff  all gates PASS  AND nothing reaches +1.0  AND some cell reads z <= -2.0
```

**A finding, not a failure.** Read it against §2.3's priors, with the mechanism named:

- **A/B at `×3`** — over-correction on top of `opp_bonus_cap` is the leading candidate and is
  **testable**, so a reversal argues for the caps re-sweep **first**, at a fresh band. It does not
  kill the family.
- **C** — [`SHAPES.md`](../invasion_term_build/SHAPES.md) §3's **normalisation caveat** is the
  leading candidate: `frac = open_n/edges` makes the charge a rate × a value, so C does not rank a
  large open city above a small fully-open feature. The named first follow-up is the
  **un-normalised** variant — which is **A DIFFERENT SHAPE** needing its own build, fixtures and
  pair, not a re-parameterisation of this one.

⛔ A `REVERSED` reading does **not** license flipping the term's sign. That is a different shape.

### `FAMILY-PARKS` — the round-level kill

```
FIRES iff  all gates PASS on all seven cells
      AND  z_C < +1.0 on EVERY cell
      AND  no cell fired REVERSED
```

**The family PARKS.** The verdict, stated in full before any number:

> At the 2752 screening budget, no invasion shape reached `+1σ` at `×⅓` or `×3` of its
> scale-matched mid, and the defence shape reached `+1σ` at no gamma against a shape-B invader.
> The bound is §4.3's table: each cell's 95% CI. **The solver-pricing instrument is the funded next
> step** — the ceiling question is what the build-first bargain hands it.

⛔ **IT IS A BOUND, NOT A ZERO, AND THE READOUT MUST SAY SO IN THOSE WORDS.** §2.1's power table is
mandatory output on this branch.

⛔ **AND IT DOES NOT REFUTE ROUND 1 (§2.2).** A flat `+0.76` pts/deck effect is caught ~24% of the
time here. **`FAMILY-PARKS` bounds the GROWTH of the effect with weight.** Any readout that says
round 2 "failed to replicate" round 1 is wrong on the power arithmetic. What it *does* license
saying: at these weights, on this band, the family did not produce a fundable signal — which is
what the round was bought to find out.

**Also stated before the answer:** `FAMILY-PARKS` is a **real, expected, and useful** outcome. §6's
prior puts it at ~45%.

### §4.5 — ⭐ THE PRE-REGISTERED WITHIN-ROUND LOW-vs-HIGH CONTRAST (MANDATORY OUTPUT)

The round's question is *"does the signal SCALE with weight?"*, and the honest way to ask it is a
contrast between two cells **this round measured, on one band** — never against round 1's mid on
another one (§1.2).

```
Per shape S with cells LOW and HIGH:

    Delta_S = D_HIGH - D_LOW
    SE_S    = sqrt( SE_HIGH^2 + SE_LOW^2 )        -- UNMATCHED, root-sum-square
    z_S     = Delta_S / SE_S

    verdict:  |z_S| >= 2.0  ->  SCALING RESOLVED   (and its sign)
              otherwise     ->  SCALING UNRESOLVED
```

⭐ **BOTH CELLS OF EVERY SHAPE ARE ON THE SAME BOX** ([`DESIGN.md`](DESIGN.md) §6.5). That is the
whole reason shapes are assigned whole: a contrast between a local cell and a laptop cell would rest
on cross-box float identity, which this program has been bitten by (the Xeon was re-retired
2026-08-02 because AVX-512 makes the G0 determinism check FAIL). Shipping one wheel file makes such
a comparison *plausible*; assigning shapes whole means **no statistic here has to rely on it**.

⚠️ **THE TWO CELLS ARE ON DISJOINT DECK RANGES** ([`DESIGN.md`](DESIGN.md) §5.1), so this is an
unmatched difference of two independent samples and the root-sum-square SE is the correct one. CRN
within a shape would have halved it and was deliberately not taken; the price is stated here rather
than discovered:

```
SE(Delta) at the frozen model 14.67   = 1.0374 pts  ->  2 sigma resolvable at |Delta| >= 2.075
SE(Delta) at round 1's realized 11.97 = 0.8467 pts  ->  2 sigma resolvable at |Delta| >= 1.693
```

⛔ **IT IS NOT A PROMOTION INPUT.** Promotion is per-cell, against zero, at the cell's own realized
SE. This contrast is a **SHAPE reading** and a **round-3 input**, and `BRACKET-CONTINUE`'s
obligations above are written against it.

⚠️ **NO CROSS-BAND HUMILITY DISCOUNT APPLIES.** Both cells are on band `152000000000`, in one launch
window, on one instrument. CL-068's 1.8–2.2× is a **cross-band** figure; the deck draw differs
between the two ranges and the per-deck SEM already prices exactly that.

⚠️ **SHAPE C's CONTRAST USES `C_LOW` vs `C_HIGH`** — its interior rung `C_MID` does not enter the
contrast, and is instead read by §4.7's noise-signature check.

### §4.5b — ⛔ ROUND 1's MIDS: THE OVERLAY, AND ITS FENCE

The adjudicator prints each shape's ladder with round 1's mid in place:

```
A invasion_beta:  0.04 = r2:<D,z>  |  0.12 = r1:+0.5238 (z +0.99993)  |  0.36 = r2:<D,z>
B invasion_alpha: 0.03 = r2:<D,z>  |  0.09 = r1:+0.7575 (z +1.26532)  |  0.27 = r2:<D,z>
D invasion_delta_farm: NOT RUN     |  0.12 = r1:-0.2913 (z -0.49005)  |  NOT RUN
```

⛔ **This is a PICTURE, not a statistic.** The r1 column is on band `151000000000` and is **never
pooled, never z-combined, never a branch input** (§1.2). A reader may look at the three numbers and
form an impression; **no branch may fit a line through them**, quote a three-point trend, or
describe the ladder as monotone.

### §4.6 — ⭐ SHAPE C READS DEFENCE, NOT STRENGTH (MANDATORY on every C result)

⛔ **C'S OPPONENT IS AN INVADER, NOT THE CHAMPION OF RECORD.** The three C cells play the champion
curve125 leaf **plus** `invasion_alpha 0.09 @ cap 11.0` (leaf `42adadc988784b44`) — bit-for-bit
round 1's `B_MID` candidate. [`SHAPES.md`](../invasion_term_build/SHAPES.md) §3 requires it: shape C
is DEFENCE-ONLY and not antisymmetric, so a C-vs-champion cell is a guaranteed-uninformative null.

**A POSITIVE C MARGIN THEREFORE MEANS: THE DEFENCE PAYS AGAINST THE EXPLOIT.** It does **not** mean
the agent is stronger, and it says **nothing** about play against the champion of record or against
any out-of-lineage opponent.

⛔ **C NEVER PROMOTES PAST ITS OWN FAMILY WITHOUT AN OFFENSE PARTNER.** A firing C cell does not
enter the four-link adoption chain, because link 1 of that chain is defined as a screen **against
the champion** and C's opponent is not the champion. What a firing C licenses is **exactly one
thing**: a **partnered follow-up** — either

  (i) a **C-vs-E4** cell, against the human invader the mechanism was discovered in (the stream
      that adapts, and the only opponent whose invasions were never designed by us); or
  (ii) a **joint cell** pairing C with a surviving offence weight, so the pair can be screened
       against the champion **as one leaf** — at which point the ordinary chain applies to the
       pair, from link 1.

Both are a fresh pair, a fresh band and a fresh funding decision. ⛔ **No C reading of any size
licenses a production H2H, a `governance/PRODUCTION.yaml` change, or a champion-of-record
discussion.**

**And a C NULL is informative here, unlike round 1's deferral.** Round 1 declined to run C because
a vs-champion null was expected **by construction**. Here the opponent **does** invade — so a null
says the defence bought nothing measurable against the very exploit it was built for, at that
gamma, at 2752, at this n. That is a real bound, and the readout states it as one.

### §4.7 — ⭐ THE LADDER RULES (MANDATORY on every branch)

⛔ **A PEAK AT A LADDER ENDPOINT IS NOT BRACKETED** (`feedback_bracket_hyperparams`). Shapes A and B
measure only `×⅓` and `×3` within round 2 — their interior mid is round 1's, on another band, and
enters as a descriptive overlay only. **A two-point ladder has no interior, so every A/B reading is
at an endpoint by construction.** A `PROMOTE` at `×3` licenses the production H2H **at that weight**
and owes a ladder **extension**; a `PROMOTE` at `×⅓` owes an extension **downward**. ⛔ No branch
may say "the optimum is at `×3`" or "the term is monotone" from two endpoints.

⭐ **SHAPE C IS THE ONLY SHAPE BRACKETED WITHIN ROUND 2** — three points on one band, so `C_MID` is
a genuine interior rung. Therefore:

⛔ **A LONE VALUE THAT BEATS ITS NEIGHBOURS BY >1σ IS A NOISE SIGNATURE, NOT A PEAK.** If `C_MID`
fires while **both** `C_LOW` and `C_HIGH` read `>1σ` lower, it is **RE-MEASURED before it is
believed**, never promoted from the single screen (`feedback_results_table_source_of_truth`,
`CLAUDE.md` n-thresholds). `screen_lib.noise_signature()` computes it and the adjudicator prints it
on **every** branch, fired or not. Symmetrically, a C peak at `C_LOW` or `C_HIGH` is at an endpoint
and is not bracketed — extend the ladder first.

⛔ **NEVER PROMOTE A FINDING FROM A SINGLE SCREEN.** `PROMOTE-<shape>` promotes a *funding request*,
not a finding. The finding, if any, is made by the production H2H it buys.

⛔ **QUERY `results.csv` BEFORE DECLARING ANYTHING.** A reading that contradicts a prior measurement
of the same cell is not a discovery until the contradiction is resolved.

### §4.3 — THE COMPANION TABLE (printed on EVERY branch, including `U-UNREADABLE`)

Mandatory output, whatever fires:

1. **Per cell:** `n_common`, `n_failed`, `D_C`, realized `SE_C`, `z_C`, the **95% CI**
   `D_C ± 1.96·SE_C`, `winrate`, `W/L/D`, **and BOTH observed leaf hashes against BOTH pins**.
2. **Realized vs modelled SE** per cell, with the `[0.70, 1.43]` flag **and its direction**.
3. **The elo display**, through §4.4's guarded conversion, with the limb that applied printed.
4. **The power table**, at BOTH dispersions — mandatory on every null.
5. **Every gate's PASS/FAIL, its resolved address, and its observed value** — all eighteen, on every
   cell, on every branch.
6. ⭐ **The invasion-arithmetic cost multiplier**: per cell, `champ_prefix_ms_per_move` ÷
   `rung_ms_per_move`, with round 1's `IDENT` ratio (`0.997`) as the ≈1.0 control and the projected
   s/game beside it. ⛔ **Stamped `DESCRIPTIVE-ONLY — TENANCY-SENSITIVE, NOT A GATE`.** ⚠️ **On a C
   cell BOTH sides pay invasion arithmetic**, so the ratio there is **gamma-vs-alpha, not
   term-vs-plain**, and must be labelled that way. **This is the one deliverable owed on every
   branch including a void**, and it carries the **first measured per-move cost of shape C**.
7. **The frozen inputs, restated**: `G = 1.76`, `M_A = M_D = 6.0`, `M_B = 8.0`, `M_C = 3.03`, target
   `0.40·G = 0.704`, `alpha_cap = 11.0`, the ladder rule (`low = mid/3`, `high = mid × 3`, named in
   round 1's own §3.4), the band and per-cell deck ranges.
8. **The ladder as run**, with each mid's source labelled.
9. ⭐ **§4.5's contrast per shape**, with its Δ, SE, z, 95% CI and verdict — and §4.5b's overlay.
10. ⭐ **§4.7's noise-signature check** on `C_MID`.
11. ⭐ **§3.4's inherited-IDENT block**: round 1's IDENT numbers and `G-WHEEL-SAME`'s observed sha.
12. ⭐ **[`DESIGN.md`](DESIGN.md) §6.5's TWO-BOX block**: the frozen assignment; each box's `W`,
    share mount, cells and provenance directory; each box's `PINNED_SRC_REV`; the **one-`code_rev`-
    across-both-boxes** verdict; the assumed laptop ratio beside each box's **realized** mean
    ms/move. Every cell's line in item 1 carries its `box`.

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
2. **No branch ranks the shapes against each other** — the seven ranges are DISJOINT (§1.1). The
   one pre-registered cross-cell statistic is §4.5's within-shape contrast, and it is not a branch
   input either.
3. ⛔ **No branch pools, z-combines or averages an r2 cell with round 1's mid** (§1.2, §4.5b).
   Different bands; CL-068; 1.8–2.2×.
4. ⛔ **No branch says "the optimum is at ×3" or "the term is monotone" from A's or B's two
   endpoints** (§4.7).
5. ⛔ **No branch reads a C margin as evidence of STRENGTH** (§4.6). C's opponent is a shape-B
   invader, not the champion of record.
6. ⛔ **No C reading of any size enters the four-link adoption chain, licenses a production H2H,
   edits `governance/PRODUCTION.yaml`, or opens a champion-of-record discussion** (§4.6).
7. **No branch says anything about shape D at any weight other than round 1's mid** — D is not run
   ([`DESIGN.md`](DESIGN.md) §3.3).
8. **No branch treats A and D as independent** — `T_A ≡ (cities+roads part) + T_D` exactly. Round 2
   runs no D cell, so this bites only if a readout reaches back to round 1's `D_MID`; if it does, it
   must read them on the `(beta, beta + delta_farm)` basis.
9. **No branch uses the ms/move ratio as evidence of anything but COST** (§4.3 item 6).
10. **No branch pools this band with any other** (CL-068; band identity is load-bearing, and
    `152000000000` retires from confirmatory use once it has influenced a decision).
11. **No branch re-derives the weights** — they are `×⅓` and `×3` of round 1's frozen mids, named in
    round 1's own `DESIGN.md` §3.4 before round 1 had an answer.
12. ⛔ **No branch reads this round past a failed `G-WHEEL-SAME`** (§3.4). Round 2 carries no IDENT
    cell; it inherits round 1's, and the inheritance is valid only while the wheel that proved it is
    the wheel that plays.
13. ⛔ **No branch reads a `FAMILY-PARKS` as a refutation of round 1** (§2.2). It bounds the growth
    of the effect with weight.
14. ⭐ **No branch compares a LOCAL cell to a LAPTOP cell** ([`DESIGN.md`](DESIGN.md) §6.5). None
    needs to: shapes are assigned whole, so every §4.5 contrast and the §4.7 noise check is
    within-box, and §1.1 already forbids cross-cell contrasts as branch inputs. The same wheel file
    and the same `code_rev` make such a comparison plausible, but **this round deliberately never
    validated it and no branch may rest on it.**
15. ⛔ **No branch treats the laptop's realized per-game ratio, or shape C's realized per-move cost,
    as anything but COST.** Both were carried as assumptions with stated envelopes; the round
    measures them and reports them. Neither moves a bar, and no gate reads a clock (§4.3 item 6).

---

## §6 — THE STATED PRIOR, RECORDED BEFORE GAME 1

Written down so the readout can be **scored against it** rather than fitted to it.

- **~45% `FAMILY-PARKS`** (nothing reaches `+1σ`). The program's base rate on leaf-term levers is
  poor, and §2.2's power arithmetic means even a real flat effect usually lands here.
- **~25% `BRACKET-CONTINUE`.**
- **~15% `PROMOTE-B`.** `B_HIGH` is the single most likely firing cell: B is the only shape that
  reached `BRACKET` in round 1 (z 1.265) and `×3` is where a scaling effect would show.
- **~8% `DEFENDS-C`.** C has never been measured against anything, so this is the widest prior in
  the table — it could as easily be a reversal.
- **~7% a `REVERSED` reading**, concentrated on `A_HIGH` and `B_HIGH` via the `opp_bonus_cap`
  over-correction mechanism: `beta 0.36` contributes `2.16` leaf points, **123% of `G`**.
- ⭐ **THE SINGLE MOST IMPORTANT PRIOR:** this round is powered to detect **SCALING**, not to
  confirm round 1's mid. An effect that stays flat at `+0.76` pts/deck is caught only ~24% of the
  time even at round 1's realized dispersion.

⚠️ These are priors, not bars. **No branch condition anywhere in §4 depends on them**, and a result
that contradicts them is a result, not an anomaly.

---

## §7 — THE ADJUDICATOR'S CONTRACT

[`analyze_screen.py`](analyze_screen.py) is the only thing that may declare a branch.

```
analyze_screen.py --selftest
    Executes §3.1's structural test against a REAL manifest read off disk
    (selftest_fixture/ -- round 1's own emitted §9 smoke archive, described by
    screen_lib.FIXTURE_SPEC and declared NOT a round-2 cell). REFUSES to run against
    a synthesized-only fixture. Exit 0 == green.

analyze_screen.py --smoke-mode --cell <dir>
    Runs every gate against an emitted 16-game archive at C_MID's config. PASSES
    (exit 0) iff the ONLY failures are §3.5's pinned allowed set. Any other failure
    => nonzero, and that is a LAUNCH BLOCKER.

analyze_screen.py --smoke-mode --cell <dir>       [PER BOX -- each box runs its own]

analyze_screen.py --run-dir <root>
    The real read. ⭐ RUN ON THE LOCAL BOX, over the SHARE-collected archives, once
    BOTH boxes are done -- it needs all seven cells. Loads them, runs all NINETEEN
    gates (each cell's G-REV / G-BLIND / G-WHEEL against ITS OWN BOX's artifacts under
    <root>/_provenance/<role>/), recomputes every statistic from the raw records as a
    WITNESS, applies G-WHEEL-SAME round-wide, checks ONE code_rev across BOTH boxes,
    evaluates §4's branches first-match-wins with U-UNREADABLE checked first, computes
    §4.5's contrasts and §4.7's noise-signature check, and prints §4.3's companion
    table in full on every branch. Writes ADJUDICATION.json.
```

- **Every bar and every constant lives in [`screen_lib.py`](screen_lib.py), imported by both the
  adjudicator and the launcher's precondition ladder** — so the launcher's per-cell pre-check and
  the adjudicator's `G-LEAF` **cannot drift apart**. They call the same `leaf_gate()`.
- The launcher pins **only the band** as a numeric literal and asserts it equals `screen_lib.BAND`;
  every other constant is read from the library, and the launcher's cell table is cross-checked
  field by field — **including the opponent hash and the env regime**, both new in round 2 and both
  the kind of field a shell table can drift on silently.
- ⛔ **The launcher's per-cell pre-check is STATISTICS-BLIND.** It reads no bar and no branch. **It
  cannot stop the round for a disappointing result, only for a broken one.** (Round 1's IDENT
  pre-check *did* read a statistic, because an identity cell's whole content is that statistic.
  Round 2's cells are arms, and a launcher that could halt an arm on its number would be peeking.)
- ⛔ **The adjudicator NEVER writes to `experiments/results.csv`** (the launcher passes
  `--no-results-csv`). Close-out rows are a human act on the six-touch checklist.

**The fired branch IS the authorization to report it.** No further sign-off is needed to state the
outcome — but every *action* a branch licenses (a production H2H, a round 3, a C-family partnered
cell, the solver-pricing instrument) is a **fresh funding decision** and a **fresh pair**.
