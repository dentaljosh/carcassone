# INVASION-RISK TERM FAMILY — ROUND-3 FINE LADDERS + JOINT AT 2752 — DESIGN

> **STATUS: FROZEN** (2026-08-27). This document and [`READ_RULE.md`](READ_RULE.md) are **the
> pair**, and the pair is law. Nothing in either moves after the blind commit. If the launcher, the
> adjudicator or the bar library disagrees with the pair, **it is the code that is wrong.**
>
> ⛔ **NOT LAUNCHED at this commit.** `run_cells.sh` is tracked at mode 644 and refuses every real
> cell without `BAND_CLAIMED`, which this build deliberately does not create.

**Band:** `153000000000` · **Cells:** 8 · **Decks:** 3200 (6400 games) · **Budget:** k4×688 = 2752
total sims, both sides · **Boxes:** local (W=14) + laptop (W=22), concurrent
**Bar library:** [`screen_lib.py`](screen_lib.py) · **Adjudicator:** [`analyze_screen.py`](analyze_screen.py)
**Launcher:** [`run_cells.sh`](run_cells.sh) · **Tests:** `tests/test_invasion_screen_r3_instrument.py`

---

## 0. AUTHORIZATION BLOCK — the sign-off table

| # | Condition | State |
|---|---|---|
| (a) | **FUNDING.** The owner funded the round-3 menu, verbatim **"fund that shit"** (2026-08-27), against the licensed menu: *small-weight fine ladders for A and C plus the joint A+C partnered cell*. The realized plan is **~165–179 core-h across both boxes / ~4.7–5.3 h round wall concurrent** (§6.2). | ✅ FUNDED |
| (b) | **BAND.** `153000000000` free everywhere per the all-branches sweep of 2026-08-27 (147 refs / 808 registry-and-claim files, §5.2), re-verified immediately before the CSV append. | ✅ |
| (c) | **⭐ OWNER W CONSTRAINT.** Verbatim **"limit local to w14 starting at 11am"** (2026-08-27). `W_LOCAL` is **FROZEN AT 14 FOR THE WHOLE ROUND** — see §6.5(0). It moves wall clock and the cell→box assignment and **nothing else**. | ✅ FOLDED IN |
| (d) | **TIE-ARBITER OFF** on both sides of every cell. No `--cand-tiearb-*` flag is emitted anywhere; the opponent side is structurally disarmed. | ✅ |
| (e) | **TENANCY.** Non-exclusive, result-safe on both boxes (§6.3). RAM is the only hard check. | ✅ |
| (f) | **EXECUTOR INTERLOCK.** `BAND_CLAIMED` is **NOT** created by this build. | ⛔ DELIBERATELY ABSENT |

### ⭐ PRE-LAUNCH CHECKLIST — the EXECUTOR-OWED artifacts

These cannot be produced inside the freeze ceremony and are the executor's own acts. **The round
does not start until every line is done, on the box it names.**

| # | Artifact | Where | Who |
|---|---|---|---|
| 1 | **⛔⛔ `PINNED_SRC_REV` — OWED ON *BOTH* BOXES, AND THE TWO MUST BE BYTE-IDENTICAL.** `git -C <repo> rev-parse HEAD > measurement/invasion_screen_r3_prep/PINNED_SRC_REV`, run **separately on local and on the laptop**, *after* the bundle sync. **This is the artifact round 2's IS-A1 defect turned on.** `G-REV`'s cross-box clause now canonicalizes every emitted short rev **against this pin** and **requires the two boxes' pin files to agree** — so a laptop that was never bundle-synced fails here, loudly, on the right proposition, instead of the round reading fine and voiding at adjudication. ⚠️ Written UNCOMMITTED; `measurement/` is excluded from the clean-code check, so it does not dirty the tree. | each box's repo | executor |
| 2 | `BLIND_COMMIT` stamped with the freeze commit's own 40-hex sha (a commit cannot name its own hash), and `WORKERS.conf::BLIND_COMMIT` moved off `PENDING` to match. | repo, committed | orchestrator |
| 3 | **Bundle-sync the laptop** to the same commit (`reference_offline_git_bundle_sync`), then re-run step 1 there. | share → laptop | executor |
| 4 | **Install the SAME WHEEL FILE on both boxes** — `$WHEEL_FILE`, scp + `pip install --force-reinstall --no-deps`. ⛔ **NEVER a laptop-local `maturin build`**: different bytes, different `carc_rs_binary_sha`, and `G-WHEEL-SAME` refuses (correctly — §7). | both boxes | executor |
| 5 | **§9 smoke on EACH box**, at that box's **own frozen W** — local `C_MID` @ `153999999000`, laptop `J_HIGH` @ `153999999100`. Each leg ends by running this pair's own adjudicator in `--smoke-mode`. **Both must PASS before any real deck.** | both boxes | executor |
| 6 | `python3 analyze_screen.py --selftest` → exit 0. | local | executor |
| 7 | Append `BAND_CLAIM.json`'s `_csv_row` to `governance/BAND_REGISTRY.csv`, **after re-running the §5.2 sweep** and aborting if `153000000000` has appeared anywhere in the interim. | repo | orchestrator |
| 8 | **THEN** drop `BAND_CLAIMED` and `chmod +x run_cells.sh`. | each box | orchestrator |
| 9 | Launch **detached** on both boxes (`setsid nohup … & disown`; laptop via the piped-script ssh pattern — §6.5(iv)) and **arm a completion Monitor on each**. | both boxes | executor |

---

## 1. THE QUESTION

Round 2 answered the **scaling** question for this family and closed the large-weight end. Round 3
asks the **dosing** question, and one new question that round 2's own read rule licensed.

**What round 2 established** (band `152000000000`, all figures the amended re-read's — see
[`AMENDMENTS.md`](AMENDMENTS.md) IS-A1):

| cell | knob | weight | D (pts/deck) | z | branch |
|---|---|---|---|---|---|
| `A_LOW` | `invasion_beta` | 0.04 | **+0.93625** | **+1.633** | **BRACKET** |
| `A_HIGH` | `invasion_beta` | 0.36 | **−3.36375** | **−5.772** | ⚠️ **REVERSED** |
| `B_LOW` | `invasion_alpha` | 0.03 | −0.6175 | −1.000 | NULL |
| `B_HIGH` | `invasion_alpha` | 0.27 | +0.0225 | +0.037 | NULL |
| `C_LOW` | `invasion_gamma` | 0.08 | **+0.9975** | **+1.632** | **BRACKET** (vs the invader) |
| `C_MID` | `invasion_gamma` | 0.23 | +0.195 | +0.333 | NULL |
| `C_HIGH` | `invasion_gamma` | 0.69 | −1.01375 | −1.562 | NULL |

Three facts fall out, and they set this round:

1. ⚠️ **THE FAMILY IS COUPLED TO PLAY, AND OVER-DOSING PUNISHES HARD.** `A_HIGH` at β=0.36 read
   z **−5.77** — the pre-registered over-correction, and the only REVERSED reading this family has
   ever produced. At that weight the term contributes 0.36 × M_A 6.0 = **2.16 leaf points, 123% of
   G**, which is no longer a tilt on the leaf but a re-weighting of it.
2. ⭐ **THE SIGNALS LIVE AT LIGHT WEIGHTS** — and **both sat at the LOW ENDPOINT of their ladder**
   (`A_LOW` β=0.04, `C_LOW` γ=0.08), which `feedback_bracket_hyperparams` says is **NOT
   BRACKETED**. That is precisely what round 3 is funded to fix.
3. ⛔ **SHAPE B IS DEMOTED AS A CANDIDATE.** Round 1's `B_MID` (+0.7575) sat between two round-2
   rungs reading −0.6175 and +0.0225 — a lone interior value beating both its neighbours, i.e. the
   **NOISE SIGNATURE** `feedback_results_table_source_of_truth` names, not a peak. **Round 3 runs no
   B candidate cell.** ⚠️ **B remains the C cells' INVADER-GENERATOR INSTRUMENT** — see §2.5.

**So round 3 asks:**

> **(i)** Where in the small-weight region do A and C peak? — a genuine three-point bracket for
> each, on one band, with a real interior rung.
>
> **(ii)** ⭐⭐ **Does a light A+C COMBINATION beat the champion?** — two JOINT cells, each ONE leaf
> carrying BOTH knobs, screened against the **champion of record**.

### 1.1 ⭐ WHY THE JOINT CELLS EXIST, AND WHAT THEY ARE FOR

Round 2's read rule said a firing C cell licenses exactly one thing: *"a PARTNERED follow-up …
a joint cell pairing C with a surviving offence weight so the pair can be screened against the
champion as one leaf."* `C_LOW` bracketed. **Round 3 is that follow-up**, and it is running it
alongside the fine ladders rather than after them, because the two questions share a band, a wheel
and a launch window.

⭐ **AND THE JOINT CELLS ARE THE ONLY ADOPTION-CHAIN-ELIGIBLE ONES IN THE ROUND'S HEADLINE SENSE.**
Link 1 of the frozen four-link chain is *a screen against the champion of record*. The A cells
satisfy that too — they always have. But the A cells ask about β alone, and round 2 already
bracketed β alone; the joint cells ask the question the family has never been able to ask: **is the
package worth a production H2H?**

⛔ **AND THE JOINT READ DOES NOT ATTRIBUTE.** This is stated here, in §3.5, in §4.6b of the read
rule, in `screen_lib.JOINT_ATTRIBUTION_BAN`, in the launcher's dry-run and beside every J result the
adjudicator prints, because it is round 3's headline over-read:

> A joint cell moves **two knobs at once**, so its margin is a property of the **PAIR** and carries
> **no information about which knob supplies it**. A firing J cell is consistent with "β does all of
> it", with "γ does all of it", and with every mixture — including one where a term that is negative
> alone is carried by a partner that is strongly positive.
>
> ⭐ **Attribution is a later question and it has a named answer: a two-cell ABLATION pair on a
> fresh band** — the joint leaf with β zeroed, and the joint leaf with γ zeroed, both against the
> champion, deck-matched. That is a fresh pair, a fresh band and a fresh funding decision. **It is
> not what this round bought.**

### 1.2 ⭐ THE E4 OBJECTION, answered again

The invasion family exists because of a mechanism **measured on-device**: the owner's farm-steal
play, characterised in Stage A, with the champion behind the owner at phone conditions and one
missing leaf term named (`reference_android_app`). ⚠️ That record is **not** what this round tests
and **not** what a `FAMILY-PARKS` would refute. This round tests **an arithmetic parameterisation**
of that mechanism, at screening budget, against a champion — and §4.8 states in advance that a park
parks the **formulas**, never the mechanism.

---

## 2. THE INSTRUMENT — production leaf, screening budget, both sides rust

| axis | value | why |
|---|---|---|
| harness | `scripts/classical_search/eval_fair_puct.py`, `--opponent fair-champion` | a `_HEAD_TO_HEAD` mode ⇒ `converted_sides == [candidate, opponent]` |
| budget | **k4 × 688 = 2752** total sims, **identical on both sides** | the SCREENING budget. ⚠️ production is k8×1376 = 11008; the harness prints a non-fatal `[warn]` about the `PRODUCTION.yaml` deviation on every cell — **EXPECTED, do not suppress it** |
| backend | **rust, both sides** | ⛔ not a speed preference: the invasion family exists **only** in rust and both python leaves RAISE on a nonzero weight. ⚠️ needed on the OPPONENT side too — the C cells' opponent carries a nonzero weight |
| info | `fair` PIMC, not clairvoyant | |
| rules | `fixed_v1` + `CARCASSONNE_FIX_R9=1` (exported before any import — R9 is import-latched behind a Rust `OnceLock`) | |
| endgame | exact-K 2, `marginalized`, both sides | K=3/4 are clairvoyant-only |
| search | `c_puct` 1.5 · `tau_p` 5 · `float` quantize · `visits` final-select | identical both sides |
| tie-arbiter | **OFF both sides** | §0(d) |
| pairing | deck-paired, both seatings, `--paired` | |
| candidate leaf | champion curve125 **plus this cell's frozen invasion knob(s)** | §2.1 |
| opponent leaf | **A and J cells:** the plain curve125 champion, `a36d2e15a3b3d71d`. **C cells:** the SHAPE-B INVADER, `42adadc988784b44` | §2.5 |

### 2.1 — `--cand-leaf-json` is a candidate-side-only knob

`eval_fair_puct.py:3769-3778` gives the head-to-head opponent `_curve125_leaf_cfg()`
**unconditionally**, and there is no `--opp-leaf-json` flag of any spelling. `_load_cand_leaf_cfg`
does `dataclasses.replace` of the named fields on the env-resolved `DEFAULT_CONFIG`. So within a
cell the **only** asymmetric inputs are the candidate JSON and — on the C cells only — the env that
moves `_curve125_leaf_cfg()` itself.

⚠️ **Every candidate JSON carries `v29_meeple_curve` EXPLICITLY.** `DEFAULT_CONFIG` is CURVE100, and
`_assert_netprior_leaf` **hard-fails** on a candidate whose curve is not curve125 — even with
`--allow-leaf-hash-drift`.

### 2.2 — ⚠️ `--allow-leaf-hash-drift` IS REQUIRED ON ALL EIGHT CELLS, and it COSTS a free check

Every round-3 cell carries a nonzero weight, so every one moves the candidate hash off
`CURVE125_LEAF_HASH` and needs the flag. ⛔ **It is a SINGLE switch that downgrades
`_assert_netprior_leaf` to a warning on BOTH sides** (`:3763` candidate, `:3777` opponent). So the
harness's own hash assertion enforces **nothing, anywhere, this round**, and `G-LEAF`'s two-sided
exact pins are the only thing left standing. That is why `G-LEAF` is EXACT rather than "not the
champion":

- on a **C** cell the opponent leaf is *supposed* to drift, so "it drifted" is not a tell;
- on a **J** cell the candidate carries two knobs, so "it moved off the champion" is satisfied by a
  leaf carrying only one of them.

### 2.3 — ⚠️ the silent-cap-drop trap, on both sides

`rust_agent.leaf_config_rs` (`rust_agent.py:181-185`) forwards `invasion_alpha_cap` and
`invasion_stub_max_tiles` **only when `invasion_alpha != 0.0`**. A side that set a cap without a
nonzero alpha would have it **silently dropped by the rust config while the manifest still showed
it** — a manifest that lies about the running leaf. `G-CAPFWD` checks the biconditional on **both**
sides; the launcher's wheel pre-flight checks it before a game runs.

### 2.4 ⭐⭐ THE TWO-KNOB FORWARD — the one genuinely new wiring risk in round 3

The same conditional-kwargs mechanism creates a failure mode **nothing in rounds 1 or 2 exercised**:
`leaf_config_rs` forwards **each invasion knob as its own conditional kwarg**. A wheel that forwarded
β and dropped γ would produce **a manifest that LOOKS like a joint cell and a GAME that is a
single-term cell** — and no downstream gate could unpick that from the numbers, on the only cells in
this round that can license a production H2H.

⛔ So the wheel probe **counts the nonzero invasion knobs that survive the forward on every J cell
and requires exactly TWO** (`joint_two_knob_forward_ok`, §7), and the merged contract key is FALSE
rather than vacuously true if no J cell was probed. And the §9 **laptop smoke runs `J_HIGH`'s exact
config** so the two-knob path emits a real manifest before any deck is spent.

### 2.5 ⭐ HOW THE C CELLS GET A NON-CHAMPION OPPONENT — carried verbatim from round 2

`_curve125_leaf_cfg()` is `dataclasses.replace(DEFAULT_CONFIG, v29_meeple_curve=CURVE125)`, and
`DEFAULT_CONFIG` is resolved **from the environment at `virtual_score_v2` import time**. So
exporting

```
CARCASSONNE_INVASION_ALPHA=0.09
CARCASSONNE_INVASION_ALPHA_CAP=11.0
```

before the process starts moves the **OPPONENT's** leaf to the shape-B agent — and the CANDIDATE,
built by replacing named fields on that same `DEFAULT_CONFIG`, takes them back off with **EXPLICIT
ZEROS** in its own JSON:

```
  ENV      => OPPONENT  = curve125 + alpha 0.09 + cap 11.0   = 42adadc988784b44
  JSON     => CANDIDATE = curve125 + gamma <w>, alpha 0.0, cap 0.0
```

⚠️ **THE EXPLICIT ZEROS ARE LOAD-BEARING.** Without them the candidate would INHERIT the env's
shape-B knobs and the cell would be "B **and** C vs B", not "C vs B" — a cell that is not
single-variable and that no gate downstream could unpick from the numbers. `G-SINGLEVAR(b)` and
`G-INVASION` both check it.

⚠️ The harness's own `_CANON_ENV` is installed with `os.environ.setdefault` and carries **no**
invasion key, so the two settings compose by construction.

⛔ **The launcher emits BOTH variables on EVERY cell**, pinned to `0.0`/`0.0` on the A and J cells,
rather than relying on absence — so a stray export in the orchestrator's shell cannot silently give
a **champion-opponent** cell a shape-B opponent. On a J cell that is the single most damaging thing
this launcher could do, because it would license nothing while looking like the round's headline
result.

### 2.6 ⭐ SHAPE B IS AN INSTRUMENT, NOT A CANDIDATE

Round 2 demoted B as a candidate (§1). Round 3 nevertheless uses **alpha 0.09 @ cap 11.0** as the C
cells' opponent, bit-for-bit round 1's `B_MID` candidate and bit-for-bit round 2's C opponent.

⛔ **This is not a contradiction, and no branch may treat it as a claim about B.** `SHAPES.md` §3
makes shape C **defence-only and not antisymmetric**: a C-vs-champion cell is a
guaranteed-uninformative null, because the champion does not invade in the tuned way C defends
against. A C cell needs an opponent that **invades**, and B is the only invader this program has
built. **The C cells ask "does γ defend against this exploit", which is a well-posed question
whether or not the exploit is worth playing.**

⭐ And because it is the **same** instrument round 2 used, the C ladders of the two rounds differ in
γ and in **band** and in nothing else.

### 2.7 — this is NOT a production H2H, and the harness says so out loud

2752 is the screening budget. Screens **aim**; they do not verdict. Every branch in
[`READ_RULE.md`](READ_RULE.md) §4 is a licence to spend more compute or to stop, never a production
claim, and `§5` says so on every branch.

---

## 3. THE CELLS

| cell | shape | rung | box | dose | candidate leaf | opponent | opponent leaf | chain? |
|---|---|---|---|---|---|---|---|---|
| `A_LOW` | A | low | laptop | `invasion_beta 0.02` | `e62afec3a84dfabd` | champion | `a36d2e15a3b3d71d` | ⭐ yes |
| `A_MID` | A | mid | laptop | `invasion_beta 0.05` | `9da236cf49065a21` | champion | `a36d2e15a3b3d71d` | ⭐ yes |
| `A_HIGH` | A | high | laptop | `invasion_beta 0.1` | `1fed3422b67be1d5` | champion | `a36d2e15a3b3d71d` | ⭐ yes |
| **`J_LOW`** | **J** | low | laptop | **`invasion_beta 0.02` + `invasion_gamma 0.03`** | `9e2764605c0b2fff` | **champion** | `a36d2e15a3b3d71d` | ⭐⭐ **yes** |
| **`J_HIGH`** | **J** | high | laptop | **`invasion_beta 0.05` + `invasion_gamma 0.07`** | `d193865634f14543` | **champion** | `a36d2e15a3b3d71d` | ⭐⭐ **yes** |
| `C_LOW` | C | low | local | `invasion_gamma 0.03` | `86a6efb793a40ef2` | ⭐ **shape-B invader** | `42adadc988784b44` | ⛔ never |
| `C_MID` | C | mid | local | `invasion_gamma 0.07` | `f05d8576b7a6cc23` | ⭐ **shape-B invader** | `42adadc988784b44` | ⛔ never |
| `C_HIGH` | C | high | local | `invasion_gamma 0.15` | `a8e9083b102a52cf` | ⭐ **shape-B invader** | `42adadc988784b44` | ⛔ never |

Every cell: 400 decks / 800 games, its own disjoint range (§5.1), `--allow-leaf-hash-drift`.

**Deck ranges** — contiguous and disjoint, in execution order:

| cell | seeds |
|---|---|
| `A_LOW` | `153000000000` .. `153000000399` |
| `A_MID` | `153000000400` .. `153000000799` |
| `A_HIGH` | `153000000800` .. `153000001199` |
| `J_LOW` | `153000001200` .. `153000001599` |
| `J_HIGH` | `153000001600` .. `153000001999` |
| `C_LOW` | `153000002000` .. `153000002399` |
| `C_MID` | `153000002400` .. `153000002799` |
| `C_HIGH` | `153000002800` .. `153000003199` |

### 3.1 ⭐ THERE IS NO IDENT CELL, AND THE INHERITANCE IS MECHANISED — for the second time

Round 1's IDENT cell (400 games, band `151000000000`) asked the game-level weight-0 identity
question and **PASSED**: |z| = 0.9624 ≤ 2.0, `cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d`,
`n_failed == 0`, leaf diff empty. **Round 2 inherited it and the inheritance HELD** — all seven of
its cells reported `carc_rs_binary_sha a9ac686bca1417f9`, across both boxes, and every
`G-WHEEL-SAME` passed.

⛔ **Round 3 inherits it again, on the identical condition:** `G-WHEEL-SAME` refuses the round unless
the emitted manifest's `carc_rs_binary_sha` is byte-identical to `a9ac686bca1417f9`. **A changed
wheel — or a different box, since the sha is box-local — RE-OWES AN IDENT CELL** (400 decks / 800
games on a fresh sub-range, ~21 core-h at this round's cell size). A fail on **any** cell voids
**every** cell.

⚠️ **And the converse stays true:** a passing IDENT proves the plumbing carries a **zero**
faithfully. It does **not** prove a nonzero weight reaches the rust leaf, and it certainly does not
prove **two** do — that is `G-INVASION`'s, `G-CAPFWD`'s and `G-WHEEL`'s job, and §2.4's
`joint_two_knob_forward_ok` is the round-3 addition to it.

### 3.2 ⭐⭐ THE WEIGHT DERIVATION — round 3 is the first round that PICKS

Rounds 1 and 2 could say *"the weights are not re-picked"*: round 1 named all six of its bracket
points in its own DESIGN before it had an answer, and round 2 ran exactly ×1/3 and ×3 of round 1's
mids. **Round 3 cannot say that.** The owner funded *fine ladders in the small-weight region*, which
is by definition a re-pick.

⛔ **So the derivation is disclosed in full, it lives IN CODE
(`screen_lib.WEIGHT_DERIVATION`, recomputed at import so the documented peaks cannot drift from the
arithmetic that produced them), and `sanity_check()` REFUSES a pair whose ladders do not actually
bracket what the derivation says they bracket.**

⚠️ **Its inputs are cross-band overlays, and that is allowed HERE AND ONLY HERE.** Choosing *where
to measure* is a **design act**; *combining readings* is a statistical one. This section does the
first and never the second, and **no round-3 branch reaches back into it** (§5 of the read rule).

#### (i) shape A — anchored on a structural zero

The load-bearing input is not an overlay at all: **D(β = 0) ≡ 0 exactly, by construction.** At weight
zero the candidate *is* the champion — which is precisely the identity round 1's IDENT cell measured
and passed. Two small-weight readings complete a local quadratic:

| β | D | source |
|---|---|---|
| 0.00 | 0.00000 | ⭐ **STRUCTURAL** — round 1's IDENT |
| 0.04 | +0.93625 | round 2 `A_LOW`, band 152e9 — ⛔ overlay |
| 0.12 | +0.52375 | round 1 `A_MID`, band 151e9 — ⛔ overlay |

Exact interpolation through those three points gives

```
D(β) = 32.9271·β − 238.0208·β²        PEAK at β* = 0.06917
```

⚠️ **Its limits, stated rather than hidden.** (a) It is a **local, small-weight** fit and does **not**
extrapolate: it predicts −18.99 at β = 0.36 against a realized −3.36, which is a reason to trust it
near zero and not far from it. (b) The β = 0.12 point is cross-band and read z = 1.00, i.e. it is
consistent with anything from ~0 to ~1.6, so the peak location is **soft**. (c) It is used to
**choose points**, never as a prediction to be scored.

⭐ **Chosen ladder: {0.02, 0.05, 0.10}** (log ratios 2.50, 2.00).

- brackets round 2's empirical best (0.04) **on both sides** — 0.02 | 0.05;
- brackets the fit peak (0.0692) **on both sides** — 0.05 | 0.10;
- entirely inside the licensed **[0.01, 0.12]**, leaving **[0.01, 0.02]** and **[0.10, 0.12]** as
  round-4 headroom, so an endpoint peak has somewhere to be extended INTO without re-opening the
  licence;
- **repeats no prior point** (0.04, 0.12, 0.36), so no round-3 A cell is poolable with a predecessor.

⚠️ **Residual risk, named:** if the true optimum is **below 0.02** the ladder peaks at its own low
endpoint again and round 4 owes a further extension. The structural anchor argues against it —
D(0) = 0 exactly, so a peak below 0.02 needs a rise-and-fall sharper than the 0.04 and 0.12 readings
suggest — but it is not excluded, and §4.7's endpoint rule is what catches it.

#### (ii) shape C — TWO readings that DISAGREE, and a ladder that brackets both

⛔ **This is the honest case, and both readings are published.**

**Reading (i), round-2 rungs only.** Exact interpolation through (0.08, +0.9975), (0.23, +0.195),
(0.69, −1.01375) is **CONVEX**: `b = +4.4628`, so its vertex at γ = 0.7544 is a **MINIMUM**, outside
the measured range. Over [0.08, 0.69] the derivative is negative throughout — the three rungs are
consistent with **monotone decreasing**, which puts the peak **at or below 0.08**, i.e. at round 2's
own low endpoint. **Unbracketed below.**

**Reading (ii), anchored at γ = 0.** At γ = 0 the C candidate is the plain champion facing the
invader — which is round 1's `B_MID` cell viewed from the other seat, so D(0) ≈ **−0.7575**.
Interpolating (0, −0.7575), (0.08, +0.9975), (0.23, +0.195) is **CONCAVE**: `b = −118.64`, a genuine
interior **PEAK at γ* = 0.13246** — *above* round 2's best point rather than below it.

⛔ **The γ = 0 anchor is the WEAKEST input in this whole document** and is labelled as such in code:
cross-band **and** sign-flipped **and** z = 1.27.

⭐ **Chosen ladder: {0.03, 0.07, 0.15}** (log ratios 2.33, 2.14).

- 0.03 sits **below** anything either reading suggests;
- 0.07 sits between them, near round 2's best point **without repeating it**;
- 0.15 sits **above** the anchored peak (0.1325);
- so it brackets the **whole contested region** rather than betting on either reading;
- inside the licensed **[0.02, 0.23]**, leaving **[0.02, 0.03]** and **[0.15, 0.23]** as round-4
  headroom;
- repeats no prior point (0.08, 0.23, 0.69);
- log-uniform spacing matching shape A's (2.2 ± 0.3), so the two ladders have the same design
  language and the same resolution per rung.

#### (iii) ⭐⭐ the JOINT points — rung-matched, not separately picked

| cell | β | γ | construction |
|---|---|---|---|
| `J_LOW` | 0.02 | 0.03 | exactly (`A_LOW`'s β, `C_LOW`'s γ) |
| `J_HIGH` | 0.05 | 0.07 | exactly (`A_MID`'s β, `C_MID`'s γ) |

Each joint cell **is** the pair of leaves this round is separately measuring, combined — which is the
only construction under which a later ABLATION pair could be posed against cells this round actually
ran. ⚠️ **That is a design convenience for round 4, NOT a licence to attribute in round 3** (§3.5).

`J_HIGH` takes each ladder's **MID** rung — the best current guess of each term's own optimum —
rather than either ladder's high end, because the joint's job is to price the package at **plausible**
doses and round 2 showed this family punishes over-dosing hard. `J_LOW` takes both LOW rungs, ~0.4×
of `J_HIGH` on each knob, to price whether the joint optimum sits **below** the marginal optima —
the usual finding when two terms push the same direction through the same argmax.

**Relation to the funded menu.** The menu named `{β 0.04, γ 0.08}` as an example joint point — round
2's two BRACKET weights. Round 3 runs the near-but-not-equal rung-matched pair `{0.05, 0.07}`
instead, for the same reason the ladders avoid prior points: it keeps every round-3 cell structurally
unpoolable with a predecessor, and it makes the joint cells coincide with rungs this round measures.

#### (iv) what did NOT move

⛔ Round 1's scale constants are **unchanged and not re-derived**: G = 1.76 leaf points (median
sibling p90−p10, corroborated within 3% by the mean top1−top2 gap of 1.72, from a different
definition), target = 0.40 × G = 0.704 pts, M_A 6.0 / M_B 8.0 / M_C 3.03 / M_D 6.0, `alpha_cap`
11.0, `stub_max_tiles` 2. **Round 3 re-picks WHERE ON THE LADDER to measure, not what a leaf point
is worth.**

### 3.3 — ⛔ SHAPE D IS STILL NOT RUN

Round 1's `D_MID` read D −0.291 / z −0.490 — a bounded null — and the measured one-ply sibling-delta
for `T_D` is ~0 at 94.6% of census positions, so a D reading is the least informative about its own
mechanism. Round 2 declined it; round 3's funded menu names no D point. **No branch may say anything
about shape D at any weight other than round 1's mid.**

### 3.4 — ⭐ BOTH A AND C ARE GENUINELY BRACKETED THIS ROUND, and that is new

Each runs **three points on ONE band**, so each has a real INTERIOR rung, §4.5b's interior-lift
statistic is computable for both, and §4.7's noise-signature rule applies to both **literally**.
Round 2 could say that of C only — its A and B ladders had two points and no interior, so every A/B
reading sat at an endpoint by construction.

⛔ **The endpoint rule has not been repealed; it has been given something to bite on.** A peak at
`A_LOW` (0.02), `A_HIGH` (0.10), `C_LOW` (0.03) or `C_HIGH` (0.15) is **still at an endpoint and
still not bracketed** — which is why §3.2 leaves headroom at both ends of both licensed intervals.

⛔ **AND THE JOINT LADDER HAS TWO POINTS AND THEREFORE NO INTERIOR.** Every J reading sits at an
endpoint by construction. A PROMOTE at `J_HIGH` licenses the production H2H **at that weight pair**
and owes a ladder extension **upward** before any claim about a joint optimum; a PROMOTE at `J_LOW`
owes one **downward**. ⚠️ And the two J points move **both** knobs together, so even a resolved J
low-vs-high contrast prices the **dose of the pair** and cannot say which knob's dose mattered.

### 3.5 ⭐⭐ WHAT A FIRING JOINT CELL LICENSES — and the ATTRIBUTION BAN

**A joint cell is ONE LEAF, not two terms.** Its candidate is the champion curve125 leaf with
`invasion_beta` **and** `invasion_gamma` both set, evaluated as a single `LeafConfig` with a single
leaf hash; its opponent is the champion of record. It asks exactly one question — *does this leaf
beat the champion at 2752* — and its deck-paired margin against zero answers exactly that question
and no other.

⭐ **A J cell at z ≥ +2.0 fires `PROMOTE-JOINT` and licenses the production-budget H2H**, per the
frozen four-link chain, because its opponent **is** the champion and link 1 is defined as a screen
against the champion. ⛔ **It licenses ONE thing: a production H2H of THAT LEAF, AT THAT WEIGHT PAIR,
AS ONE LEAF.** Not a `PRODUCTION.yaml` edit. Not a champion-of-record discussion. Not an H2H of
either knob alone. And the H2H itself is a fresh pair, a fresh band and a fresh funding decision.

⛔⛔ **THE ATTRIBUTION BAN, in full.** Forbidden, explicitly:

1. reading a J margin as evidence for shape A **or** for shape C **separately**;
2. subtracting an A cell's margin from a J cell's to "recover" γ, or vice versa — those cells are on
   **disjoint deck ranges** and §1 of the read rule forbids cross-cell contrasts as branch inputs,
   so that difference is not even a pre-registered statistic, let alone an attribution;
3. reading a **NULL** joint as evidence **against** either term;
4. describing a joint margin as the **SUM** of the two marginal margins, in either direction.

⚠️ **On (4), and it cuts both ways.** §4.2's power table publishes an "additive" row (Δ = +1.94
pts/deck, the arithmetic sum of round 2's two BRACKET readings) as **the effect size the joint cell
is SIZED against** — because sizing needs a number and that is the honest one to size against. ⛔
**Publishing it as a sizing target is not predicting it, and observing it would not confirm
additivity**: one cell at n = 400 cannot distinguish additive from sub-additive-plus-noise from a
single dominant term.

⚠️ **And an honest expectation, stated before any number exists.** γ's +0.998 was measured against an
agent **tuned** to invade. The champion invades in the ordinary course of play but is **not tuned
to**, so γ's contribution against it should be **smaller** — possibly null, possibly negative if the
term's cost outweighs its rarer benefit. **So the joint's realistic best case is "β's gain, not
diluted by carrying γ".**

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

**PRIMARY, per cell:** the deck-paired margin `D = mean over decks of (diff(a_seat=0) +
diff(a_seat=1)) / 2`, in POINTS, candidate minus opponent, adjudicated **against ZERO** at the
cell's **own realized SE**. `D > 0` ⇒ the candidate won. Bars: **BRACKET ≥ +1σ, PROMOTE ≥ +2σ,
REVERSED ≤ −2σ** — carried verbatim through three rounds, not one bar moved.

⛔ **The sizing model is NEVER a denominator in a branch test.** Every bar is evaluated at the cell's
own realized SE; `SIGMA_D_MODEL = 14.67` exists for the power arithmetic below and nothing else.

### 4.1 — σ_D: the frozen model, and what two rounds have realized

| | σ_D | SE at n=400 | ratio vs model |
|---|---|---|---|
| frozen model (this pair sizes on it) | **14.67** | **0.7335** | 1.00 |
| round 1 realized | 10.48 – 12.23 | 0.524 – 0.612 | 0.714 – 0.834 |
| **round 2 realized** (7 cells) | **11.47 – 12.98**, mean **12.0591** | **0.6030** at the mean | 0.782 – 0.885 |

⚠️ Round 3 keeps **14.67** even though both prior rounds realized tighter. Keeping the conservative
model means the published power table **under-states** this round's real resolution rather than
over-stating it, which is the direction a screen that decides funding should err in. Every figure
below is published at **both** dispersions.

⚠️ A round-3 SE flag at the **LOW** end of `SE_ANOMALY_BAND [0.70, 1.43]` is therefore **EXPECTED**
and means "tighter than modelled"; the HIGH end is the concerning direction. The band does not move
for that, and the flag is **reported, never a branch input**.

### 4.2 — what n=400 buys, and ⛔ THE HEADLINE POWER CAVEAT

Power to clear the +2σ PROMOTE bar, `Φ(Δ/SE − 2)`:

| Δ (pts/deck) | z @ model | power @ model | z @ realized | power @ realized | note |
|---|---|---|---|---|---|
| **+0.94** | 1.28 | **24%** | 1.56 | **33%** | ⭐ round 2's `A_LOW` reading |
| **+1.00** | 1.36 | **26%** | 1.66 | **37%** | ⭐ round 2's `C_LOW` reading |
| +1.47 | 2.00 | 50% | 2.44 | 67% | |
| **+1.71** | 2.33 | 63% | 2.84 | **80%** | the 80%-power MDE at round 2's REALIZED dispersion |
| **+1.94** | 2.64 | 74% | 3.22 | **89%** | ⭐⭐ **THE JOINT SIZING TARGET** — the arithmetic sum of round 2's two BRACKET readings. ⛔ a SIZING TARGET, **not a prediction** (§3.5) |
| **+2.08** | 2.84 | **80%** | 3.45 | 93% | the 80%-power MDE at the FROZEN conservative model |

> ⛔ **THIS ROUND IS POWERED TO RESOLVE ~1.7 PTS/DECK AT 80%, AND THE TWO SIGNALS IT IS CHASING READ
> +0.94 AND +1.00 IN ROUND 2.** So if the fine ladders' peaks are no larger than round 2's best
> points, **each single A or C cell resolves only ~33–37% of the time** even at round 2's realized
> dispersion, and ~24–26% at the frozen model.
>
> ⭐ **THAT IS THE DESIGN REASON THE JOINT CELLS EXIST:** if β and γ are even weakly additive, the
> package is sized at ~+1.94, where power is ~89% realized / ~74% modelled.
>
> ⛔ **AND IT IS WHY A `FAMILY-PARKS` MUST NOT BE READ AS A REFUTATION OF ROUND 2.** This round is
> powered to resolve a **peak**, not to confirm a +1.0 effect. A readout that says round 3 "failed to
> replicate" round 2 is **wrong on the power arithmetic**, not merely on the emphasis.

### 4.3 — the TWO pre-registered ladder statistics, and what they cost

Both are **unmatched** differences of independent same-band cells (the rungs are on **disjoint** deck
ranges, §5.1), so root-sum-square SEs are the right ones. CRN within a shape would have tightened
them and was **deliberately not taken**: the primary statistic is each cell's own margin against
zero, disjoint ranges cost that nothing, and the funded design named 8 × 400 disjoint decks. **The
price is paid here and is stated before any number.**

| statistic | formula | SE | 2σ-resolvable at (model / realized) |
|---|---|---|---|
| **§4.5 SCALING** | `Δ = D_high − D_low` | `√(SE_hi² + SE_lo²)` = √2·SE | **2.075** / **1.705** pts/deck |
| ⭐ **§4.5b INTERIOR LIFT** | `lift = D_mid − (D_low + D_high)/2` | `√(SE_mid² + (SE_lo² + SE_hi²)/4)` = √1.5·SE | **1.796** / **1.477** pts/deck |

⭐ **The interior lift is new in round 3, and it is the statistic a fine ladder actually owes.**
Round 2's A and B ladders had two points and therefore no interior at all; round 3's A and C ladders
have three points on ONE band, so *"is there a peak strictly inside the bracket?"* is finally a
question the data can answer. A **positive resolved** lift says the optimum is INTERIOR and §4.7's
endpoint rule is satisfied for that shape; an unresolved lift leaves the endpoint rule **in force**.
It is also **tighter** than the scaling contrast at the same dispersion, because averaging the two
neighbours halves their variance contribution.

⛔ **NEITHER IS EVER A PROMOTION INPUT.** Promotion is per-cell, against zero, at the cell's own
realized SE. Both are SHAPE readings and round-4 inputs.

⛔ **The lift is NOT the noise-signature check.** That one asks whether a lone interior rung beats
**both** neighbours by >1σ in z — a **RE-MEASURE trigger**, not an estimate. They can disagree, and
**where they do the re-measure obligation wins**.

⚠️ **No cross-band humility discount applies to either.** Every rung is on band `153000000000`, in
one launch window, on ONE box per shape. CL-068's 1.8–2.2× is a **cross-band** figure, and the
per-deck SEM already prices the deck draw.

### 4.4 — elo is display-only, and the conversion is guarded

Under a null `D ≈ 0`, so a cell's own `elo/D` is a quotient of two independently-noisy near-zero
quantities: it does not converge and its **sign is not stable**. So the conversion has two limbs —
at `|z| ≥ 2.0` the cell's own realized `elo/pt` is reportable and cross-checked against the in-family
bracket `[16.74, 19.35]` (a reading outside it is FLAGGED as a witness anomaly and is **never** a
branch input); otherwise the cell's own ratio is **not reportable** and only a bracket-converted 2σ
bound may be printed, labelled as such.

---

## 5. THE BAND

### 5.1 — allocation: one band, EIGHT DISJOINT deck ranges, no reuse

3200 decks × 2 seatings = **6400 games**, 400 decks / 800 games per cell, ranges as tabulated in §3.
**Disjoint by design** — each cell's primary statistic is its own internal deck-paired margin, so
shared decks buy the primary read nothing. The cost is that §4.3's two ladder statistics are
**unmatched**, and §4.3 states that price before any number exists.

**No top-up range is reserved.** [`READ_RULE.md`](READ_RULE.md) §5 carries no top-up branch: a
bounded null is the **licensed outcome** of a screen, not a failure state.

The §9 smoke uses **disjoint throwaway sub-ranges** far above every cell — local
`153999999000..153999999007`, laptop `153999999100..153999999107` — discarded, never pooled, never
themselves claimed.

### 5.2 — the all-branches sweep, re-run for this pair

The procedure of record: for **every** ref in `refs/heads` and `refs/remotes`, read that ref's own
`governance/BAND_REGISTRY.csv` **and** every `measurement/**/BAND_CLAIM*.json` it carries, then take
the lowest integer clear of everything found anywhere. A registry check scoped to the checked-out
branch is blind to an unmerged sibling freeze branch — that is how `143e9` and `144e9` were
double-claimed.

**Re-run 2026-08-27 over 147 refs (127 `refs/heads` + 20 `refs/remotes`) / 808
registry-and-claim files.**

| band | status found | source |
|---|---|---|
| `146000000000` | **soft-reserved** | `track_d1_fair_rebase` — skipped, as six prior pairs skipped it |
| `149000000000` | ⛔ RETIRED — burn-in-abort void | `track_d2r3_prep` |
| `150000000000` | ⛔ **SPENT** — `D2-BOUNDED-NULL` | `track_d2r4_prep` |
| `151000000000` | ⛔ **SPENT** — invasion round 1, `MIXED` | `invasion_screen_prep` |
| `152000000000` | ⛔ **SPENT** — invasion round 2, `BRACKET-CONTINUE` (amended) | `invasion_screen_r2_prep` |
| **`153000000000`** | **free everywhere** | verified two ways: a raw-mention sweep over every ref's registry-and-claim files found **every** mention at or above 152e9 to be round 2's OWN, and a direct `^15[3-9]000000000,` row-start grep over every ref's registry returned **ZERO hits** |

Per CL-068, **band identity is load-bearing**: never pool this pair's numbers across bands — and ⛔
**specifically never with `151000000000` or `152000000000`**, whose readings are the natural interior
points of this round's own ladders and therefore the two most tempting cross-band pools this program
has been offered. `153000000000` **retires from confirmatory use** once it has influenced any
decision.

⚠️ **`RELEASE-IF-NEVER-LAUNCHED`**: if no cell ever runs, `153000000000` is released. Once **any**
real record exists on it — including under a round that voids on `G-WHEEL-SAME` — the band is
**spent**, on the `149e9` precedent.

⚠️ **The sweep is RE-RUN immediately before the CSV append**, in the stamping commit, and the append
aborts if `153000000000` has appeared anywhere in the interim.

---

## 6. COST

### 6.1 — ⛔ ROUND 2's INPUTS ARE RETIRED; ITS ARITHMETIC IS KEPT

Round 2 built its model on round **1**'s realized ms/move and carried **two** unmeasured inputs.
**Round 2 measured both.** Round 3's inputs are round 2's realized numbers:

```
plain-champion side   475.87 / 480.86 / 464.28 / 465.23  -> 471.56  (local)
shape-A candidate     685.50 / 683.57                    -> 684.53  (local)
shape-B side          632.20 / 634.63                    -> 633.42  (local)
shape-C candidate     671.00 / 683.78 / 690.45           -> 681.74  (laptop)
shape-B side          696.84 / 687.37 / 693.78           -> 692.66  (laptop)
```

⭐ **The last two lines are the SAME LEAF on DIFFERENT BOXES**, which is where the **measured** box
ratio comes from — see §6.5(i). Shape C's local-equivalent cost then follows: 681.74 / 1.0935 =
**623.43** ms/move.

⚠️ **Note how little the weight matters to cost:** shape A read 685.50 ms/move at β = 0.36 and 683.57
at β = 0.04 — a **9× weight ratio for a 0.3% cost difference**. The invasion arithmetic is a
per-component **scan** whose cost is set by the board, not by the coefficient. That is why round 3's
much smaller weights are projected at round 2's per-move costs without apology.

The arithmetic is unchanged: `s/game(local-equiv) = 69.0 × (ms_cand + ms_opp)/1000 × 1.073`, and
`sanity_check()` requires it to reproduce **each of round 2's three realized shapes without ever
UNDER-predicting and by no more than +5%** — a **directional** assertion, because a cost model that
decides funding should err **dear**. Realized: A **+1.00%**, B **+3.23%**, C-on-laptop **+1.08%**.

### 6.2 — per cell, and the ONE named uncertainty

| cell | box | ms cand | ms opp | s/game | core-h | wall @ its box's W |
|---|---|---|---|---|---|---|
| `A_LOW` / `A_MID` / `A_HIGH` | laptop | 684.5 | 471.6 | 93.6 | 20.8 each | ~57 min each |
| `J_LOW` / `J_HIGH` | laptop | **836.4** ⚠️ | 471.6 | 105.9 | 23.5 each | ~64 min each |
| `C_LOW` / `C_MID` / `C_HIGH` | local | 623.4 | 633.4 | 93.1 | 20.7 each | ~89 min each |

| | core-h | wall |
|---|---|---|
| **LOCAL** (3 C cells, W=14) | **62.0** | **4.43 h** |
| **LAPTOP** (3 A + 2 J cells, W=22) | **109.5** | **4.98 h** |
| **ROUND** | **171.5** | ⭐ **4.98 h — the MAX, not the sum** |
| envelope | 164.5 – 178.5 | 4.66 – 5.30 h |
| *(single-box local at W=14 would be)* | *162.1 local-equiv* | *11.58 h — the split buys **6.6 h*** |

⚠️ **ONE unmeasured input, named:** the **JOINT leaf's per-move cost**. No leaf carrying two invasion
terms has ever run. The point estimate is **ADDITIVE** in the two measured increments (β +212.97,
γ +151.87 over the champion side ⇒ 836.40 ms/move), and **additive is the conservative (dear)
direction** — the mechanism says so, because `T_A` and `T_C` both walk the mover's own claimed
components and therefore **share** the contested-feature decomposition. The envelope runs from a
sub-additive floor (760.5, the two scans sharing their walk) to a super-additive ceiling (872.9).

⭐ Round 2's **other** unmeasured input, the laptop ratio, is now **MEASURED** — §6.5(i).

### 6.3 ⭐ TENANCY CLASS: NON-EXCLUSIVE, RESULT-SAFE

This pair is **sims-denominated**: no equal-time gate, no burn-in, no timing bar. Every gate and the
primary statistic are functions of **game outcomes**, and outcomes are **bit-identical under
co-tenancy and at any W** (the determinization merge is a sequential post-join fold —
`rust/carc/carc-core/src/fair/mod.rs:22-32`). A co-tenant can move **wall clock and nothing else**,
so the process census is **advisory**. `feedback_no_agent_compute_beside_eval` is honoured, not
evaded: that rule's own text scopes exclusivity to a **timing bench**, and this is not one.

⚠️ **THE EXCEPTION IS RAM, WHICH IS A HARD, FAIL-CLOSED CHECK** on both boxes: a WSL guest OOM tears
down the **whole VM**, not one worker (`reference_wsl2_host_memory_teardown`), and the reconcile
solver the local box may legitimately share with carries a 30 GB job cap. Floors: 4000 MB to start,
1500 MB between passes.

### 6.4 — sequencing, and the per-cell interlock

Within a box, cells run in the §3 order. **On the laptop that puts the three A cells — a one-knob,
plain-regime, champion-opponent configuration rounds 1 and 2 have both already run clean — BEFORE
the two JOINT cells**, so the instrument is confirmed three times on proven plumbing before the
round's genuinely new machinery spends a deck.

⭐ **After EVERY cell seals, the launcher re-reads that cell's own EMITTED manifest** and refuses to
start the next unless it passes: `leaf_gate()` on both pinned hashes, both invasion blocks equal to
the frozen ones, `n_failed == 0`, `G-WHEEL-SAME`, and a computable statistic. A wiring defect
therefore costs **ONE cell (~21 core-h), not eight (~171)**.

⚠️ **The arithmetic is `screen_lib`'s, not the shell's** — it calls the **same** `leaf_gate()` the
adjudicator's `G-LEAF` calls, so the live check and the post-hoc check cannot drift apart. And it
reads **`manifest.json` for config, `summary.json` for statistics** — round 1's `IS-D1` deviation was
exactly this reader taking config off `summary.json`, getting `{}`, and fail-closed voiding a healthy
cell.

⛔ **The pre-check is STATISTICS-BLIND.** It reads no bar and no branch. It cannot stop the round for
a **disappointing** result, only for a **broken** one.

### 6.5 ⭐ TWO BOXES — the frozen assignment, and why it is the one it is

#### (0) ⛔⛔ THE OWNER'S W CONSTRAINT, AND WHY IT IS FROZEN RATHER THAN SCHEDULED

> **"limit local to w14 starting at 11am"** — owner, 2026-08-27

The round straddles 11:00 EDT / 15:00Z, which is the owner's interactive-use window, and
`feedback_desktop_friendly_selfplay` is the standing rule for it. ⛔ **So `W_LOCAL` is FROZEN AT 14
FOR EVERY LOCAL CELL OF THE WHOLE ROUND — not 22-then-14.** Three reasons, all structural:

1. **`--workers` is a PER-INVOCATION argv value**, and a cell runs in bounded resumable **passes**. A
   mid-round change would run one cell's passes at two different W, so the launcher's own realized
   `worker-s/game` log would stop being comparable across the passes of a single cell — the one
   operational number this round is trying to measure honestly.
2. **A frozen pair does not move after the blind commit**, and `W` is a frozen operational constant
   of it. "Change W at 11:00" is a mid-round edit to a frozen constant, which the ceremony has no
   mechanism for and which no gate could witness after the fact.
3. **The cheap direction is obvious.** At this split the **laptop is the critical path either way**
   (4.98 h vs local's 4.43 h), so 14-for-the-whole-round costs **~0 h of ROUND wall** and buys
   certainty that no local cell ever competes with the desktop.

⚠️ **AND IT MOVES NO BAR.** `W` is **throughput-only**: games are bit-identical at any W and no gate
in this pair reads a clock. It moves **wall clock** and the **cell→box assignment** — and nothing
else. The assignment change is priced in (iii), computed at `W_LOCAL=14` rather than inherited.

#### (i) ⭐ THE LAPTOP RATIO IS **MEASURED** THIS ROUND, NOT ASSUMED

Round 2 carried the laptop's per-game cost as an **assumed 1.4×** inside a 1.3–1.5× envelope,
because no cell had ever run the same configuration on both boxes.

⭐ **It had, by accident of design.** The **shape-B leaf** (`invasion_alpha 0.09 @ cap 11.0`) ran on
the LOCAL box as the B cells' **candidate** and on the LAPTOP as the C cells' **opponent** — same
leaf, same budget, same wheel, same code rev:

```
local  (B_LOW / B_HIGH candidate)   632.20 / 634.63 ms/move  ->  633.42
laptop (C_LOW / C_MID / C_HIGH opp) 696.84 / 687.37 / 693.78 ->  692.66
ratio  692.66 / 633.42                                       =   1.0935
```

⛔ **So the 1.4× assumption was ~28% too pessimistic**, and round 2's published laptop ETA
over-stated its wall by that factor. Round 3 uses **1.0935** inside a narrow 1.05–1.15 measurement
band.

⚠️ **What it is NOT:** a shape-matched ratio on **one workload class** (a rust both-sides
`eval_fair_puct` head-to-head at 2752). It does **not** transfer to python-backend cells, where
`track_d1_fair_rebase` read +73%, and no branch may quote it as a general laptop-vs-local figure.
⚠️ And it moves no bar — it is a wall-clock number.

#### (ii) ⛔ WHOLE CELLS PER BOX, AND THE ASSIGNMENT IS FROZEN HERE

A cell's records are **never** split across boxes: a mixed-host archive is a provenance smell with no
recovery, and the manifest's `host` is the **only** host witness the harness emits (the per-game
records carry no host field at all). So the unit of assignment is the whole cell, and `G-HOST`
enforces it against the emitted manifest. The launcher **also** refuses a foreign cell up front.

⭐ **AND EVERY PRE-REGISTERED STATISTIC IS COMPUTED WITHIN ONE BOX** — the load-bearing property.
Shapes are assigned **whole**, so §4.5's scaling contrast is within-box for all three shapes,
§4.5b's interior lift is within-box for A and for C, and §4.7's noise-signature check on **both**
interior rungs is within-box too. **This is not a convenience:** it is what lets the round avoid
relying on cross-box float identity, which this program **has** been bitten by (the Xeon was
RE-RETIRED 2026-08-02 because AVX-512 makes the G0 determinism check FAIL by default).

⭐ **Why outcomes are comparable across the two boxes at all** — and round 2 is now the **evidence**
rather than the argument: ONE wheel FILE installed on both boxes made `carc_rs_binary_sha`
**identical on all seven of its cells across both machines**. Round 3 ships the same file. ⛔ Never a
laptop-local rebuild: different bytes, different sha, and `G-WHEEL-SAME` refuses — correctly.

#### (iii) ⛔ THE ASSIGNMENT IS THE **OPPOSITE** OF ROUND 2's, AND THE ARITHMETIC SAYS WHY

At `W_LOCAL = 22` the fastest whole-shape split put the expensive shape on the laptop — round 2's
arrangement. The owner's `W_LOCAL = 14` cuts local throughput by **36%** and moves the balance point
**past the flip**. All **six** whole-shape partitions, re-priced at W_LOCAL=14 / W_LAPTOP=22
(`screen_lib.split_table()`, printed by the launcher's dry-run):

| # | LOCAL (W=14) | core-h | wall | LAPTOP (W=22) | core-h | wall | **ROUND WALL** |
|---|---|---|---|---|---|---|---|
| **1** | **C** | **62.04** | **4.43 h** | **A, J** | **109.46** | **4.98 h** | ⭐ **4.98 h — FROZEN** |
| 2 | A | 57.06 | 4.08 h | J, C | 114.90 | 5.22 h | 5.22 h |
| 3 | J | 43.04 | 3.07 h | A, C | 130.23 | 5.92 h | 5.92 h |
| 4 | A, J | 100.10 | 7.15 h | C | 67.84 | 3.08 h | 7.15 h *(round 2's pattern)* |
| 5 | J, C | 105.07 | 7.51 h | A | 62.40 | 2.84 h | 7.51 h |
| 6 | A, C | 119.10 | 8.51 h | J | 47.06 | 2.14 h | 8.51 h |

The chosen split sits **4.7% off the unconstrained ideal** of 4.75 h (= 162.1 local-equiv core-h ÷
(14 + 22/1.0935) effective local-equivalent workers), which is as close as a whole-shape constraint
allows. ⛔ **`screen_lib.sanity_check()` REFUSES a pair whose frozen assignment is not rank 1**, so
this table cannot go stale silently.

⭐ It also happens to be regime-clean: the three shape-B-env cells sit together on local, and the
five champion-opponent cells together on the laptop.

#### (iv) SYNC, PROVENANCE AND ADJUDICATION

- **Sync:** the repo is bundle-synced to the laptop (`reference_offline_git_bundle_sync`) and **all
  eight cells must report ONE code_rev**, canonicalized against **both boxes' pins** — §7.1.
- **Provenance:** each box writes `PINNED_SRC_REV`, `SRC_CLEAN.jsonl`, `BLIND_PROOF.json` and
  `WHEEL_PROBE.json` into **its own** repo checkout, which the local adjudicator cannot see — so each
  launcher **also copies them to `<out-root>/_provenance/<role>/` on the SHARE**, and `G-REV`,
  `G-BLIND` and `G-WHEEL` evaluate each cell against **its own box's** artifacts. The adjudicator
  falls back to its own directory when a per-box copy is absent, so a single-box run and the §9 smoke
  keep working unchanged.
- **⚠️ The share mount spelling differs by box:** local `/mnt/c/carc-shared`, laptop
  `/mnt/carc-shared`. A box that used the wrong one would write outside the share and the adjudicator
  would never see the archive. The launcher picks it from `--host`.
- **Launch:** the laptop is launched via the piped-script ssh pattern
  (`ssh laptop-wsl 'bash -s' < /tmp/x.sh`, `cd` on line 1) with `setsid` detach — never the inline
  `ssh host 'cd … && …'` form, whose `cd` is stripped in transit
  (`feedback_remote_ssh_pipe_script_mandatory`).
- **Adjudication** runs on the LOCAL box over the share-collected archives, **once BOTH boxes are
  done**. ⛔ The round is not readable until then: `G-WHEEL-SAME` is round-wide, `G-REV`'s cross-box
  clause needs both pins, and §4's round table reads every cell.
- **⚠️ WSL clock drift** (`reference_wsl_clock_drift_after_sleep`) is a **within-box** concern here
  and not a cross-box one: the boxes hold **disjoint cells** and therefore **disjoint
  `--out-subdir`s**, so there are no shared claims to steal. It can still bite inside a box's own
  pass-resume loop, which is what `--claim-stale-secs` and the orphan sweep are for.

---

## 7. THE WHEEL — a FATAL precondition

`rust_agent.leaf_config_rs` forwards the invasion knobs as **conditional kwargs**, so a `carc_rs`
build predating the family serves every default-off (champion) config **unchanged and silently** — a
stale-wheel cell would read as *"the term is worth nothing"* rather than *"the term never ran"*. So
the launcher does not probe with `hasattr`; it performs the **actual nonzero forward**, in a child
process, on the real cell configs, **once per env regime** (`DEFAULT_CONFIG` is resolved at
`virtual_score_v2` import time and never re-read, so one process cannot observe both opponent
regimes). `WHEEL_PROBE.json` must record every one of:

| key | what it catches |
|---|---|
| `invasion_terms_attr` | `carc_rs.MirrorState` has `invasion_terms` at all |
| `nonzero_kwarg_forward_ok` | every cell's candidate leaf reached rust |
| `cap_biconditional_ok` | §2.3's cap-forwarding biconditional holds on both sides |
| `opp_side_forward_ok` | the C cells' **shape-B opponent** leaf reached rust |
| ⭐ `joint_two_knob_forward_ok` | **NEW** — every J cell forwarded **exactly TWO** nonzero invasion knobs (§2.4). ⛔ FALSE, not vacuously true, if no J cell was probed |
| `wheel_is_round_1s` | `G-WHEEL-SAME`, asserted at pre-flight rather than at adjudication |

⚠️ **`carc_rs_version` is permanently "0.1.0" and can never discriminate. Neither can
`carc_rs_build`** — it embeds the **repo rev at call time**, not a compiled-in value. Round 1's own
smoke and cell archives carry different build strings (`47e7cc0ffb31` vs `ac709c42c6e2`) with the
**same** binary sha, and round 2's seven cells carry a third (`240626a31fee`) with that same sha
again. **`G-WHEEL-SAME` keys on `carc_rs_binary_sha` ALONE**, in all three rounds.

### 7.1 ⭐⭐ `G-REV`'s CROSS-BOX CLAUSE — the IS-A1 fold

Round 2's **frozen** adjudicator asked *"are the boxes' EMITTED SHORT REVS equal as strings?"* and
**falsely voided a healthy single-rev round**: `git rev-parse --short` picks its length **per clone**,
so the two boxes at the **identical** commit emitted `240626a3-dirty` and `240626a31f-dirty`. Frozen
verdict `U-UNREADABLE`; owner-authorised re-read; amended branch `BRACKET-CONTINUE`. Full write-up in
[`AMENDMENTS.md`](AMENDMENTS.md).

> **The lesson, verbatim: *canonicalize revs against the pin, never rev-vs-rev.***

⛔ Round 3 folds it into the **bar library** as `screen_lib.cross_box_rev_gate()`, and goes further:

1. **THE PINS AGREE** — every box that published a `PINNED_SRC_REV` must publish the **same** 40-hex
   sha. ⭐ The conjunct the amendment script did not have; it states the proposition **directly**
   instead of inferring it from a local file the boxes never wrote.
2. **EVERY EMITTED REV CANONICALIZES TO THAT PIN** — strip `-dirty`, require ≥ 7 hex, require a
   **prefix** match.

⚠️ It cannot degenerate into "any prefix passes" (the 7-hex floor and the 40-hex pin are both
enforced), and the instrument suite drives it **in both directions** plus an eight-distinct-spellings
control proving the verdict is a function of each rev **separately**.

---

## 8. WHAT THIS PAIR CANNOT SHOW

1. **A production result.** 2752 is the screening budget; production is 11008. Screens aim.
2. **⛔ WHICH KNOB CARRIES A JOINT MARGIN.** §3.5. Attribution needs an ABLATION pair on a fresh
   band, and that is not what this round bought.
3. **A ranking of the shapes.** The eight deck ranges are disjoint and §1 of the read rule forbids
   cross-cell contrasts as branch inputs. The two ladder statistics are the **only** pre-registered
   exceptions and neither is a branch input.
4. **Anything about B as a candidate**, at any weight. It is an instrument here.
5. **Anything about D**, at any weight other than round 1's mid.
6. **That a C margin means STRENGTH.** C's opponent is an invader.
7. **Confirmation of round 2's +1.0 readings.** §4.2 — this round is powered to resolve a **peak**,
   not to confirm a +1.0 effect.
8. **A general laptop-vs-local cost ratio.** §6.5(i) — shape-matched, workload-scoped.

---

## 9. THE SMOKE LEG (pre-blind, mandatory) — ⭐ ONE PER BOX, AT THAT BOX'S OWN W

16 games (8 decks × 2 seatings) per box on a **throwaway** range placed far above every cell range,
so no arithmetic slip can reach a real deck. **Discarded, never pooled, never claimed, never
adjudicated as a result.** It spends **no band** and drops **no `BAND_CLAIMED`** — but it **does**
write its own `PINNED_SRC_REV` / `BLIND_PROOF.json` / `SRC_CLEAN` boundaries and carries the
`--stamp-key BLIND_COMMIT` exactly as a real cell does, because `G-REV` and `G-BLIND` are **NOT** in
§3.5's pinned allowed set and must **PASS** on the smoke archive.

| box | cell config | range | why |
|---|---|---|---|
| **laptop** | **`J_HIGH`** | `153999999100..107` | ⛔ **THE LOAD-BEARING LEG.** The JOINT candidate leaf — TWO invasion knobs on ONE leaf, a two-key leaf diff, and the round's only adoption-chain-eligible novelty — has **never emitted a manifest on any box, in any round**. `J_HIGH` rather than `J_LOW` because it carries the larger dose of both knobs, so a forwarding failure on either has the most room to show. |
| **local** | `C_MID` | `153999999000..007` | the local box owns the three C cells, whose shape-B env regime round 2 proved end to end — so this leg re-confirms the launcher, the wheel install and the env regime **on this box** rather than seeing any of it for the first time. `C_MID` because the interior rung is the one §4.7's noise-signature rule reads. ⚠️ It is also this box's first run at W=14, which is a wall-clock fact and nothing more. |

⛔ **AND EACH LEG RUNS AT ITS BOX'S OWN FROZEN W** — there is no separate smoke W this round. Round 2
smoked at W=8; round 3 does not, because **uniformity beats speed** here: the leg's job is to prove
the plumbing **in the configuration that will spend the decks**, `W_LOCAL` is itself an owner
constraint rather than a free choice, and a 16-game leg does not saturate W either way — so the cost
of uniformity is ~nothing and the benefit is that the smoke cannot pass at a W the real cells never
use.

⭐ **The standing rule, carried:** each smoke leg **ENDS** by running this pair's own adjudicator in
`--smoke-mode` against the archive the harness just emitted, and requires it to fail **only** on the
pinned allowed set a 16-game throwaway cannot satisfy by construction (`G-BAND`, `G-DECKS`, `G-N`,
`G-SAT`, `G-HOST`, `RECON/n_paired`). ⛔ `G-WHEEL-SAME` is **not** in that set: the smoke runs the
same wheel the cells will.

### 9.1 — the selftest fixture

`--selftest` runs against `selftest_fixture/` — **round 1's own §9 smoke archive**, 16 real games the
harness emitted, carried through round 2. ⛔ **It refuses a synthesized fixture**: a gate "validated"
against a manifest the DESIGN *described* rather than one the harness *wrote* is exactly the defect
this rule exists to prevent.

⚠️ **What it cannot prove:** it is a plain-regime, one-knob archive, so it does not exercise the C
cells' shape-B opponent or the J cells' two-knob leaf. Those are covered by
`tests/test_invasion_screen_r3_instrument.py` (synthesized manifests are legitimate in unit tests; it
is the **selftest** that refuses synthesis) and, definitively, by the §9 smoke.

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, in one sitting: (1) `experiments/results.csv` row → (2) `DECISIONS.md` index
line → (3) status stamp on this doc → (4) governance row flip (`BAND_REGISTRY` `pending` →
the verdict; `CLAIM_REGISTRY` if a claim moved) → (5) `STATUS.md` top block → (6) the roadmap line.
Then `python3 scripts/doc_lint.py`.

⛔ **The adjudicator NEVER writes `experiments/results.csv`** — close-out rows are a human act on the
checklist.

⛔ **And every ACTION a branch licenses is a fresh funding decision and a fresh pair.** The fired
branch is the authorization to **report** it, not to spend the next round's compute.
