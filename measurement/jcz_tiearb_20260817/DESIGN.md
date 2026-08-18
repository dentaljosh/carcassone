# JCZ OUT-OF-LINEAGE PRICING OF THE TIE ARBITER — DESIGN

> **✅ STATUS 2026-08-18 — COMPLETE. RAN, ADJUDICATED, CLOSED. Branch `J-CONFIRMED`** on band
> **134000000000** (tag `b134`), branch `tiearb2-stage2`. The numbers of record — and the ONLY
> place to read them — are [`READOUT_b134.md`](READOUT_b134.md) / [`READOUT_b134.json`](READOUT_b134.json);
> `results.csv` carries the three rows (`jcz_tiearb_CHAMP_deploy11008_…`,
> `jcz_tiearb_ARB_B16J4_deploy11008_…`, `jcz_tiearb_D_ARBminusCHAMP_…`, all `_b134e9`).
> ⚠️ **The FIRST attempt, on band 133000000000, was VOIDED `U-UNREADABLE`** and no statistic from
> it is quotable — audit trail [`DISCLOSURE.md`](DISCLOSURE.md); its artifacts are preserved
> untouched and the `b134` tag keeps the two runs from colliding.
> ⛔ **What the verdict licenses is unchanged from the text below: corroborating evidence for the
> owner's PENDING production-flip decision, and nothing else.** `governance/PRODUCTION.yaml` is
> **untouched**. **The design text below is the committed prereg and is NOT edited by this banner.**

> **Status: DESIGN COMMITTED 2026-08-17, BEFORE the band claim and BEFORE game 1.**
> Owner authorization, verbatim (2026-08-17): **"lets do jcz"** — given in answer to the
> question of whether the freshly `G-CONFIRMED` tie-arbitration edge
> ([`measurement/tiearb2_stage2_20260817/READOUT.md`](../tiearb2_stage2_20260817/READOUT.md):
> +23.92 elo head-to-head vs the champion, deck-paired margin +3.0700 pts/game, `paired_z` +4.445)
> survives against an **out-of-lineage** reference.
>
> ⛔ **This cell INFORMS the owner's pending production-flip decision. It does not gate it and
> does not take it. `governance/PRODUCTION.yaml` is untouched on every branch.**

---

## 0. AUTHORIZATION BLOCK

| field | value |
|---|---|
| authorized by | Joshua (owner), 2026-08-17 |
| verbatim | **"lets do jcz"** |
| question it answered | does the `G-CONFIRMED` tie-arbitration edge survive against an OUT-OF-LINEAGE reference? |
| what it licenses | ONE two-cell match against JCloisterZone's `LegacyAiPlayer`, on ONE fresh band, deck-paired |
| what it does NOT license | a `PRODUCTION.yaml` flip · an on-device deploy (`rho_phone` = 5.520 at B = 16, still unsolved) · a leaf term · a second arbiter rung · any change to B, J, the tie predicate, or the playout |
| inherited constraints | the Stage-2 **anti-gaming clause** (`READ_RULE.md` §0.D) binds here verbatim: permission to spend clock is never licence to reshape the arbiter to look cheaper |

### §0.1 — PRE-LAUNCH AMENDMENT (2026-08-17): TWO BOXES, by OWNER RULING

> **Owner directive, verbatim (2026-08-17):**
> **"make sure its both boxes, w22 and w30 respectively"**
>
> Given in answer to the single-box deviation this design originally recorded at §6.3.
> **It OVERRIDES that deviation.** The ruling was made with the band UNCLAIMED and NO game
> played, so **the blind ordering is intact and no adjudicating bar moves.**

**The JVM gap is solved, not worked around.** §6.3's original reason for going single-box was
that the laptop had no JVM and no `Engine.jar`. Resolved before launch:

| step | result |
|---|---|
| `openjdk-17-jre-headless` via apt | installed; `/usr/bin/java` = OpenJDK **17.0.19**, verified running in a **NON-INTERACTIVE ssh shell** (the Stage-2 "rustup not on PATH" trap class — the launcher uses the absolute `$JAVA_BIN`, never PATH) |
| `Engine.jar` staged via the share | sha256 **`4dc5439d…1190` — equals the pin, verified ON THE LAPTOP** (`G-JCZ` is a per-host gate) |
| AI shim classes | **COPIED, not rebuilt** (10 `.class` files, byte-identical bytecode on both hosts). This is *stronger* provenance than two independent `javac` runs — a JDK on the laptop would have produced a second, unverified binary |
| shim loads on the laptop | ✅ `com.jcloisterzone.ai.AiEngine` starts and dies on stdin EOF — the healthy signature |

⚠️ **Disclosed per-host difference:** the JVM *packaging* differs (`17.0.19+10-1-24.04.2-Ubuntu`
locally, `+10-1-26.04.2-Ubuntu` on the laptop) — same OpenJDK 17.0.19, different distro base. The
pinned artifacts (jar, classes) are byte-identical; only the runtime build differs. §0.1.2 makes
this incapable of touching `D`.

#### §0.1.1 — the execution model: a STATIC deck split

`scripts/jcz_match/match.py` has **no `--shared-claim`** (checked). So each box takes a **disjoint,
contiguous** deck range through `--seed-base` / `--decks`, with `--champ-seat both` on each, so the
union covers all 400 decks × 2 seatings **exactly once per cell**. A merge step verifies exactly
that, and `G-COVER` gates it from the records.

**The deck-paired statistics are unaffected by WHERE a game ran, provided coverage is exact** —
`D` is computed per deck from that deck's two cells, and a deck's identity does not depend on
which box played it.

#### §0.1.2 — ⭐ THE SPLIT IS IDENTICAL ACROSS CELLS, AND IT IS LOAD-BEARING

The previous sentence is true **only** if a given deck runs on the **same box in both cells**.
`D` sums `margin_B(d) − margin_A(d)`. If deck `d` ran on the laptop in CELL A and locally in
CELL B, then every per-box difference — the JVM packaging above, the different `W` and hence
different contention, different RAM pressure — lands **inside the paired difference** and is
arithmetically indistinguishable from the arbiter's effect.

With the split identical across cells, every per-box effect is **common to both terms and cancels
exactly**. This is not left to the launcher behaving well: **`G-SPLIT`** (READ_RULE §3) verifies
from the records that the deck→host assignment is identical across the two cells, and voids if it
is not.

#### §0.1.3 — the split ratio comes from the SMOKE, not from W

The boxes are not equal-throughput (30 vs 22 workers, different cores, 41 GB vs 11 GB). Splitting
by `W` alone would leave one box idle at the tail. The smoke measures per-box **s/game** at the
production `W` on each box, and `DECKS_LOCAL` / `DECKS_LAPTOP` are set from that ratio before
game 1. Provisional values in `WORKERS.conf` are marked as such.

#### §0.1.4 — ⚠️ THE LAPTOP MEMORY RISK, NAMED BEFORE THE SMOKE

The laptop has **11 GB** and `W22` means 22 python+rust workers **and** 22 JVMs. A WSL guest that
balloons past its `.wslconfig` cap is **torn down by Windows**, killing the leg
(`reference_wsl2_host_memory_teardown`). Two mitigations, applied **identically on both boxes and
both cells** so neither can become a box or a cell confound:

1. `_JAVA_OPTIONS="-Xmx256m -Xss1m -XX:+UseSerialGC -XX:TieredStopAtLevel=1"` — caps each heap and
   stops default G1 from spawning per-core GC threads (22 JVMs × N GC threads is a thread
   explosion on a 24T box). The JVM's "Picked up" banner goes to **stderr**, so it cannot corrupt
   JCZ's **stdout** line-JSON protocol. Heap size and GC policy cannot change `LegacyRanking`'s
   deterministic arithmetic, so JCZ's play is untouched.
2. The smoke **measures** per-worker RSS at the production `W` on each box before the long run
   commits.

**If the smoke shows W22 does not fit in 11 GB, that is REPORTED TO THE OWNER, not silently
reduced.** W22 is an owner-set value and this agent does not overrule it.

#### §0.1.5 — the per-host gate roster

`G-J13` (the two-sided arbiter positive control), `G-JCZ` (jar sha + shim + AI class), and the
toolchain witness are **per-host**: each box writes its own
`verdicts/PREFLIGHT_<host>_FIRST.json` **after** any wheel build on that box and **before** its
own game 1. `G-TOOL` returns to its Stage-2 **cross-box** form in the corrected shape — manifests
compared with each other, pre-flights compared with each other — plus the same-box
`carc_rs_binary_sha` witness. The laptop is **bundle-synced to the launch commit** first
(`reference_offline_git_bundle_sync`), and both boxes run rust toolchain `1.96.0`.

#### §0.1.6 — ⛔ THE MERGE STEP IS MANDATORY AND ORDERED BEFORE ADJUDICATION

Two-box execution writes **per-host shards** (`<cell>.<host>.jsonl` + `<cell>.<host>.hostmap.json`).
**`adjudicate.py` reads only the MERGED `<cell>.jsonl` and `<cell>.hostmap.json`** — it does not
discover shards. Adjudicating before merging would silently grade a **half-run**, and `G-COVER` /
`G-N` would fire on volume in a way that looks like a data problem rather than a missing step.

**The post-DONE sequence, in order — all four `DONE_<cell>_<host>` markers must exist first:**

```bash
cd /home/doctor/projects/carcassone/measurement/jcz_tiearb_20260817
./merge_cells.sh jcz_CHAMP_deploy11008        # -> <cell>.jsonl + <cell>.hostmap.json, verifies G-COVER
./merge_cells.sh jcz_ARB_B16J4_deploy11008
# cheap pre-adjudication check: the two ENV pre-flights must agree on carc_rs_build
#   (that IS §0.F.2b conjunct 1 post-§0.F.2c; the binary SHAs will and must differ across hosts)
python3 -c "import json;print([json.load(open(f'verdicts/PREFLIGHT_{h}_ENV.json'))['carc_rs_build'] for h in ('Doctor','laptop-wsl')])"
/home/doctor/projects/carcassone/.venv/bin/python adjudicate.py \
    --cell-a jcz_CHAMP_deploy11008.jsonl \
    --cell-b jcz_ARB_B16J4_deploy11008.jsonl \
    --json READOUT.json | tee READOUT.md
```

`merge_cells.sh` also emits `SPLIT_CHECK.json` (a convenience comparison of the two hostmaps);
`G-SPLIT` gates the same proposition independently inside the adjudicator, so the convenience
check can never substitute for the gate.

⚠️ Minor, recorded and deliberately not fixed: `preflight.sh`'s `run()` keeps only the **first
line** of `java -version`, so the JVM packaging string may be truncated in the ENV witness.
**Nothing branches on it** — `G-JCZ` reports the JVM string and never fails on it (§0.F.1) — so
this is cosmetic.

#### §0.1.7 — revised ETA

Two boxes at 52 combined workers against §6.2's 291,360 worker-s ⇒ **≈1.6 h** if the laptop keeps
pace per worker. It will not exactly — 11 GB and 24T against 41 GB and 32T — so the honest
planning figure is **≈2 h**, and the per-box figure is restated from the smoke before launch
rather than extrapolated (`feedback_eta_before_launch`).

---

## 1. THE QUESTION

Every strength number this program owns is **self-relative** — the champion is measured against
its own lineage. The house anchor-trap rule (auto-memory `feedback_anchor_before_scaling`) is
explicit that chain-vs-prev elo can climb while absolute strength regresses, and that **even a
fixed same-lineage anchor can lie**; the corroboration a promotion-relevant lever needs is a
reference **outside** the training/tuning lineage.

Stage 2 established the arbiter's edge **against the champion**, with its own wall-clock control
(`RND`, −60.09 elo) resolving the mechanism from the clock at 2σ. What Stage 2 cannot establish
is whether that +3.07 pts/game is a **real strength gain** or an **exploitation of
lineage-specific habits at tied plies** — the two are indistinguishable when the opponent is the
champion, because the arbiter's whole surface is *plies where our own leaf cannot separate the
moves*, and the opponent's blind spots at exactly those plies are perfectly correlated with ours.

**The deliverable is the ARBITER'S DELTA MEASURED THROUGH JCZ:**

```
D  =  M(champion+arbiter vs JCZ)  −  M(champion vs JCZ)
```

deck-paired on a shared deck set, within one band. JCZ has no correlated blind spot with us: it
shares no leaf, no search, no engine and no rules implementation.

**Direction is the claim.** A positive `D` says the arbiter buys real points against an opponent
that has never seen our lineage. A `D` at zero says the Stage-2 edge is lineage-specific.

---

## 2. WHY JCZ IS THE RIGHT REFERENCE — AND THE RULES GATE, DISCHARGED

The standing rule (auto-memory `feedback_external_reference_first`) is **"rules agreement gates
the match"**. It is discharged, and it was discharged *before* this design, not for it:

| requirement | status | evidence |
|---|---|---|
| independent implementation exists | ✅ | JCloisterZone rev `29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a`, `LegacyAiPlayer` on the 5.x headless engine |
| tile-set agreement | ✅ | D0 differential tile oracle, promoted to CI as `tests/test_jcz_tile_oracle.py`; `basic:2`; 31/32 kinds byte-equivalent, the 32nd is **R9** |
| the one divergence is FIXED, not tolerated | ✅ | R9 (`city_top_straight_road` claims two field half-edges on its own city edge) — fix built as `CARCASSONNE_FIX_R9`; forced ON here |
| per-ply runtime agreement | ✅ | D1 replay oracle `scripts/jcz_oracle/`, CI `tests/test_jcz_replay_oracle.py` |
| **measured** agreement at match scale | ✅ | **2026-08-09, n=400 games / 56,777 plies: ZERO REAL divergences, final scores agree 400/400** ([`CONFIRM_READOUT.md`](../jcz_match_20260809/CONFIRM_READOUT.md)) |
| non-saturated | ✅ | champion **+111.4 elo (wr 0.6550)** — off both rails; a saturated reference reads ≥0.95 and resolves nothing |

**No rules bridge is improvised by this design.** The driver `scripts/jcz_match/match.py`
hard-codes `PROFILE = "fixed_v1"` and **raises** if `CARCASSONNE_FIX_R9` is not on. Stage 2 ran
under **the identical configuration** (`run_cells.sh`: `--rules-profile fixed_v1`,
`export CARCASSONNE_FIX_R9=1`), so the arbiter is being carried into this match under the same
rules it was confirmed under. Nothing about the rules changes between Stage 2 and here.

### 2.1 The two honest asterisks, carried forward verbatim

* **`WALL_LEGALITY`, measured at 0.5% of games** (2 events in 56,777 plies): the bounded 25×25
  action window running out before the 35×35 grid. It only ever *adds* options on JCZ's side; our
  player picks from our own set, so boards stay identical and both affected games carried
  `final_agree=True`. Real, not zero, far too rare to move a verdict.
* **`UNPLACEABLE_REDRAW` × 23** — benign and a *positive* result: both engines discarded and
  redrew in lockstep. The divergent form `UNPLACEABLE_TURN_LOSS` fired 0 times.

---

## 3. THE TWO CELLS

One band, one deck set, both seatings, one difference.

| | **CELL A** | **CELL B** |
|---|---|---|
| cell id | `jcz_CHAMP_deploy11008` | `jcz_ARB_B16J4_deploy11008` |
| our side | the UNMODIFIED production champion | champion **+ the tie arbiter** |
| arbiter flags | *(absent)* | `--champ-tiearb-enabled --champ-tiearb-b 16 --champ-tiearb-j 4 --champ-tiearb-mode argmax --champ-tiearb-salt tiearb2-deploy-v1 --champ-tiearb-eps 0.0` |
| opponent | `LegacyAiPlayer` (JCZ) | `LegacyAiPlayer` (JCZ) — identical |
| budget | fair PIMC k8×1376 = **11,008**, exact-K 2, rust backend | identical |
| leaf | `a36d2e15a3b3d71d` | `a36d2e15a3b3d71d` — **the arbiter moves no leaf hash** |
| rules | `fixed_v1` + `CARCASSONNE_FIX_R9=1` | identical |
| n | **800 games = 400 decks × 2 seatings** | **800 games = the SAME 400 decks × 2 seatings** |

The two invocations differ in **exactly the six `--champ-tiearb-*` arguments**, which are absent
in CELL A and present in CELL B. This is the exact rung Stage 2 confirmed — B=16, J=4, `argmax`,
salt `tiearb2-deploy-v1`, eps 0.0 — and no other rung is authorized.

### 3.1 ⚠️ THE CELLS ARE **NOT** WALL-CLOCK MATCHED — and why that is the right design here

CELL B spends ≈2.4–2.7× CELL A's per-move wall (§6). **This is a deliberate, disclosed
asymmetry, and it is NOT a hole in the argument**, for one reason stated plainly:

> **The wall-clock control already exists and it already fired.** Stage 2's `RND` cell —
> identical playouts, identical worlds, identical plies, identical arm set, *values discarded and
> the arm drawn by seeded RNG* — is the matched-clock control, and it read **−60.09 elo /
> `paired_z` −6.669**. The clock does not explain the arbiter's edge; spending it *badly* is
> actively harmful. That question is closed and this cell does not reopen it.

This cell asks a **different** question: does the mechanism's edge express against an
out-of-lineage opponent? Re-running the clock control here would cost a third cell (+~60% wall)
to re-answer a question already answered at 2σ on a claim-tier band.

**DECLINED, with reason, before any number exists:** a third `RND vs JCZ` cell. Reason: cost, and
redundancy with Stage 2's `RND`. If a reader wants the matched-clock contrast out-of-lineage,
that is a *new* funded cell, not a reinterpretation of this one.

The owner ruling `tiearb2_stage2_20260817/READ_RULE.md` **§0.D** — *"we can afford some wallclock
during play, especially if its not every tile draw. dont let that be the constraint right now"* —
is cited here as the governing waiver on wall-clock consequence. **`ms_ratio` is measured and
reported on every branch and is NEVER a branch input** (§7 `G-CLOCK-REPORT`).

### 3.2 CELL A is a finding in its own right

The champion's JCZ-facing strength was last read on **2026-08-09**, on band 1.08e11, at code-rev
`9c4bb50`. CELL A re-reads it on a fresh band at today's rev. **Its absolute result is reported
prominently on every branch, whatever `D` does** — including if `D` is null. A champion that
scores materially below +111.4 elo here has lost absolute strength whatever the self-play ladder
says, and that is the single thing an out-of-lineage anchor exists to catch.

⚠️ CELL A vs the 2026-08-09 reading is a **CROSS-BAND** contrast (1.33e11 vs 1.08e11) at a
different code era. Per CLAUDE.md it carries the **1.8–2.2× over-dispersion rider**: σ on that
contrast inflates from ±17.4 to **≈ ±31–38 elo**. It is a regression *tripwire*, not a precision
comparison. `D` — the primary statistic — is **within-band and deck-matched**, i.e. the robust
class, and is unaffected.

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

**Primary:** `D = M_B − M_A`, the **deck-paired** difference of margins over the decks common to
both cells, in points per game. Convention identical to `eval_fair_puct._paired_z`.
**Secondary:** each cell's own elo/wr and paired margin vs JCZ.

### 4.1 The dispersion we are entitled to assume

From the 2026-08-09 n=400 confirm (the only measurement of this population that exists):

```
deck-paired margin      +6.50  ±0.86 pts over 200 decks
=> per-deck paired sd   0.86 x sqrt(200)          = 12.16 pts
unpaired per-game sd    18.39  (pairing bought 0.66x — consistent with 1/sqrt(2))
```

### 4.2 What n = 400 decks per cell buys

```
se per cell (400 decks)     = 12.16 / sqrt(400)            = 0.608 pts
se(D), assuming rho = 0     = sqrt(2) x 0.608              = 0.860 pts
```

`rho = 0` is the **conservative** assumption. Stage 2's realized cross-cell deck correlation was
ρ ≈ 0.09 (se(D) 0.9332 against a quadrature sum of 0.98) — essentially nil, because one changed
move early diverges the whole game. We assume nil here and do not bank a variance reduction that
may not arrive.

| the effect, if it is… | `z_D` at n=400 decks/cell | reading |
|---|---|---|
| **+3.07** (undiminished — the Stage-2 magnitude) | **+3.57** | convicts comfortably |
| **+2.00** (35% attenuated) | +2.33 | convicts |
| **+1.72** | +2.00 | **the 2σ conviction floor** |
| **+1.00** (67% attenuated) | +1.16 | **cannot resolve** — reported as null-bounded |
| **0.00** | 0.00 | null, bounded at ±1.72 |

**So this cell can convict an undiminished or moderately attenuated effect, and it can BOUND a
null at |D| < 1.72 pts/game (≈ 56% of the Stage-2 magnitude). It CANNOT distinguish a small
positive from zero.** That limit is stated here, before launch, and the read-rule has a named
branch for it (`J-NULL-BOUNDED`) so it cannot be narrated as a refutation after the fact.

### 4.3 The n that would resolve smaller effects — recorded now, funded by nobody

```
to convict D = +1.00 at 2sigma:   se(D) <= 0.500  =>  n = 1,183 decks/cell (2,366 games/cell)
to convict D = +1.50 at 2sigma:   se(D) <= 0.750  =>  n =   526 decks/cell (1,052 games/cell)
```

The n = 1,183 figure is ≈ 3× this cell's compute and is **not** authorized. It is written down so
that a future "just add n" proposal has to argue against a number that already exists.

---

## 5. THE BAND

Claimed via `scripts/classical_search/claim_next_band.py` **immediately before game 1**, with a
sentinel for idempotent resume. Registry high-water at design time is **132000000000** (Stage 2's
own band), so the expected allocation is **133000000000**; the claim script takes the lowest
step-aligned band strictly above the high-water mark, never a gap.

Both cells draw from the SAME claimed band: seeds `<band>..<band+399>`, each deck played twice
with the seats swapped. **Band identity is load-bearing** (CLAUDE.md): the deck-matched
within-band contrast is the only statistic here that is not over-dispersed. The band retires from
confirmatory use at close-out.

---

## 6. COST — and what had to be BUILT before this could run

### 6.1 ⚠️ DEVIATION FROM THE TASK BRIEF — the harness could not arm the arbiter

**Found in Phase 1 and flagged loudly.** The task brief assumed the match could be launched
against the existing harness. It could not:

* the arbiter is reachable **only** through `eval_fair_puct.py`'s `--cand-tiearb-*` flags, which
  set six fields on `HeuristicPriorConfig`, consumed by `rust_agent.RustFairAgent`;
* `scripts/jcz_match/match.py` builds its champion through
  `champion_factory.make_production_champion("fair", ...)` → `production_prior_cfg(spec, leaf_cfg)`,
  which has **no path to those fields at all**.

This is a **plumbing gap, not a rules gap** — the Phase-1 stop condition (rules disagreement) did
not fire. The enabling change adds a `tiearb` kwarg to `make_production_champion` /
`production_prior_cfg` and `--champ-tiearb-*` flags to `match.py`, following the existing
`meeple_dedup` precedent exactly: **byte-identical construction and a byte-identical manifest when
the arbiter is absent**, so CELL A is provably the same champion the 2026-08-09 run played. It was
built in a **git worktree** (the main tree had a live `reconcile_exact_solver` leg —
`feedback_worktree_isolation_live_tree`) with unit tests, and is merged at a quiet window before
launch.

### 6.2 Wall-clock

Measured inputs — CELL A from the 2026-08-09 confirm, the arbiter's cost from Stage 2:

```
CELL A  per game                       98.1 worker-s   (measured, n=400, W14)
arbiter per FIRED ply                   9.57 worker-s  (Stage-2 realized; model said 8.561, +11.8%)
phi (fired tied tile plies per game)   17.6            (Stage-2 realized 17.573; offline prior 22.96)
CELL B  per game  = 98.1 + 17.6*9.57 = 266  worker-s   (= 2.71x CELL A)
```

```
CELL A  800 games x  98.1 =  78,480 worker-s
CELL B  800 games x 266   = 212,880 worker-s
TOTAL                     = 291,360 worker-s
```

| W (local, single box) | wall |
|---|---|
| 14 (the 2026-08-09 setting) | 5.8 h |
| 20 | 4.0 h |
| **24 (proposed)** | **3.4 h** |
| 28 | 2.9 h |

The 2026-08-09 run at W14 loaded **~15 of 32 threads** — the box was half idle, because each
worker is one python thread plus a JVM that is busy 38 ms per move. W24 is the proposed setting;
it is **not** extrapolated (`feedback_bug_fix_shifts_optima` / the bench-then-commit rule): a
short smoke measures per-worker RSS and throughput at W24 before the long run commits. Box has
41 GB with 27 GB free.

### 6.3 ⚠️ DEVIATION — the laptop cannot run this cell

`ssh laptop-wsl` has **no JVM** (`java: command not found`) and **no `Engine.jar`**. JCZ is a Java
program; the harness spawns one JVM per worker. Enabling the laptop needs a `sudo apt install
openjdk-17-jdk`, an scp of the pinned jar, and a `javac` of the AI shim — ≈20–30 min of setup plus
a second build to certify.

~~**DECIDED: single box (local)**~~ — ⛔ **OVERRIDDEN BY OWNER RULING, see [§0.1](#01--pre-launch-amendment-2026-08-17-two-boxes-by-owner-ruling).**
Verbatim: *"make sure its both boxes, w22 and w30 respectively"*. The JVM gap described above was
solved (apt JRE + share-staged jar verified against the pin + copied shim classes), not routed
around. **This section is retained as the audit trail of what was true before the ruling; §0.1 is
the operative text.** Two consequences of the original single-box decision that the ruling
reverses: `G-TOOL` returns to its Stage-2 **cross-box** form (in the corrected shape), and the
pre-flight becomes **per-host**. Revised ETA ≈2 h (§0.1.7).

---

## 7. INTEGRITY GATES

Reusing the Stage-2 shapes where they apply. Each is a **precondition**: any FAIL ⇒
`U-UNREADABLE`, no strength statistic is adjudicated. Committed in
[`READ_RULE.md`](READ_RULE.md) §3, which is the binding text; this section is the summary.

| gate | proposition |
|---|---|
| `G-BAND` | both cells carry the SAME band, claimed BEFORE game 1, and the record-derived deck sets agree |
| `G-LEAF` | `cand_leaf_hash` == `a36d2e15a3b3d71d` on BOTH cells — the arbiter moves no leaf |
| `G-ARB` | CELL B's resolved `champ_tiearb` == `{enabled, B:16, J:4, mode:"argmax", salt:"tiearb2-deploy-v1", eps:0.0}`; **CELL A carries no `champ_tiearb` key at all** |
| `G-FIRE` | CELL B's `phi_effective` ≥ 1.0 fired tied tile plies per game (Stage-2 floor, verbatim) |
| `G-J13` | the TWO-SIDED arbiter positive control passes on the box at the launch commit: pick CHANGED **and** root leaf value bits UNCHANGED |
| `G-RULES` | both cells stamp `rules_profile == fixed_v1` and `r9_env == "1"` |
| `G-DIVERGE` | **zero REAL divergences** and `final_agree` on ≥99% of games in BOTH cells; any REAL divergence VOIDS |
| `G-JCZ` | JCZ provenance identical across cells and equal to the pinned values below |
| `G-TOOL` | same-box `carc_rs_binary_sha` equality across both cells; and `git diff --name-only <preflight>..<manifest> -- rust/ src/ engine/ scripts/` is EMPTY. A non-empty wheel-relevant diff VOIDS |
| `G-N` | ≥320 decks common to both cells (the Stage-2 80% floor), and ≥640 games completed per cell |
| `G-PLY` | the ply-granularity witness is carried, per Stage-2 §0.F |
| `G-CLOCK-REPORT` | `ms_ratio` is **measured and reported on every branch and is never a branch input** (§3.1 waiver; the field-name trap is named in the read-rule) |

### 7.1 The pinned JCZ provenance (`G-JCZ`)

```
JCZ revision      29a156154c75ad7bf5a3af6e2e5db3eaeb1af76a   (2023-03-27)
Engine.jar        /home/doctor/jcz_spike/JCloisterZone/build/Engine.jar
Engine.jar sha256 4dc5439dbf228b1360b0b1987f5e90454c4a6ac434a8509be4d2c089f9671190
AI shim source    scripts/jcz_match/java/  (javac'd by build_ai_shim.sh)
AI entry class    com.jcloisterzone.ai.AiEngine
AI player         LegacyAiPlayer  —  1-turn breadth-first enumeration ranked by LegacyRanking
tile set          basic:2
configurability   NONE. LegacyAiPlayer has no depth, budget, temperature or seed knob.
```

**There is no "stronger JCZ" to try.** The rating is against this specific agent, full stop —
recorded here so no later reading implies a difficulty setting was chosen.

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch, so no branch can be narrated past them:

1. **It cannot make the arbiter superhuman.** JCZ sits ≈111 elo *below* the champion. A positive
   `D` says the mechanism generalises off-lineage; it says nothing about the absolute ceiling, and
   structural blocker #2 (the hand-crafted leaf) is untouched.
2. **It cannot separate "the arbiter is good" from "the arbiter is good against weak opponents."**
   One out-of-lineage opponent is one opponent.
3. **It cannot resolve `|D| < 1.72`** (§4.2).
4. **It cannot price the phone.** `rho_phone` = 5.520 at B = 16 is a third currency and is not
   reopened. No branch licenses an on-device deploy.
5. **It is not a wall-clock-matched contrast** (§3.1). The matched control lives in Stage 2.
6. **`fixed_v1` + R9-on ⇒ NOT comparable to walled-era elo.** R9 is built and NOT adopted in
   production; it is forced on here because it is the only configuration in which the two engines
   are provably rules-identical.

---

## 9. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from CLAUDE.md: (1) `experiments/results.csv` rows — one per
cell plus the `D` row · (2) `DECISIONS.md` index line · (3) status banner on this DESIGN and on
`READ_RULE.md` · (4) governance row flips (`CLAIM_REGISTRY.csv`; `BAND_REGISTRY.csv`
`decision_influenced` + **band retirement**) · (5) `STATUS.md` top block · (6) the roadmap line in
`docs/PROGRAM_ROADMAP_2026-07-07.md`. Plus a `docs/LEVER_INDEX.md` row keyed
**"JCZ out-of-lineage pricing"**. Then `python3 scripts/doc_lint.py`. Commit; **do not push**.

`governance/PRODUCTION.yaml` is untouched on every branch.
