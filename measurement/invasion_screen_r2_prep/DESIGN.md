# INVASION-RISK TERM FAMILY — ROUND-2 BRACKET AT 2752 — DESIGN

**STATUS: FROZEN, NOT LAUNCHED (2026-08-27).** No cell has run. No band sentinel exists.
Nothing in this directory has spent a game.

Run id `invasion_screen_r2_prep`. Pair: this file + [`READ_RULE.md`](READ_RULE.md). Launcher:
[`run_cells.sh`](run_cells.sh). Adjudicator: [`analyze_screen.py`](analyze_screen.py). Shared
primitives (the ONE implementation of every bar and every cost figure):
[`screen_lib.py`](screen_lib.py). Band claim: [`BAND_CLAIM.json`](BAND_CLAIM.json).

Spec of record for the thing being screened: [`../invasion_term_build/SHAPES.md`](../invasion_term_build/SHAPES.md).
Implementation: `rust/carc/carc-core/src/leaf/invasion.rs`. Round 1: [`../invasion_screen_prep/DESIGN.md`](../invasion_screen_prep/DESIGN.md)
+ [`../invasion_screen_prep/READ_RULE.md`](../invasion_screen_prep/READ_RULE.md), adjudicated
**MIXED** on band `151000000000`. Mechanism evidence: [`../e4_exploit_grading_20260825/STAGE_B_VERDICT.md`](../e4_exploit_grading_20260825/STAGE_B_VERDICT.md).
Lever row: [`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md), "contested-feature / invasion-risk term".

---

## 0. AUTHORIZATION BLOCK — the sign-off table

| # | sign-off | state | why |
|---|---|---|---|
| (a) | **funding ≈155–177 core-h across TWO boxes / ≈3.7–4.7 h ROUND wall** (§6) | ✅ **GIVEN — OWNER, 2026-08-27** | Verbatim: **"fund them all"**, in response to the offered menu of *B bracket + A bracket + C-vs-B-agent*. That is the whole of §3's cell table and nothing else. ⛔ It funds the **compute**; it does not waive any gate, and it is not a launch authorization on its own — the interlock below still holds |
| (a2) | ⭐ **TWO-BOX EXECUTION** (§6.5) | ✅ **DIRECTED — OWNER, 2026-08-27** | Verbatim: **"get round 2 on both local and laptop"**. The cell→box assignment is **frozen in this prereg** (`screen_lib.CellSpec.box`), **whole cells per box**, and `G-HOST` enforces it against the emitted manifest. ⭐ The assignment keeps **every shape wholly on one box**, so no pre-registered statistic is ever computed across the two machines |
| (b) | **the band claim** — `152000000000` (§5) | ⚙️ **ORCHESTRATOR-PROCEDURAL — DONE at freeze** | All-branches sweep re-run 2026-08-27 (143 refs / 723 registry-and-claim files); `152000000000` free everywhere. The row is in [`BAND_CLAIM.json`](BAND_CLAIM.json) and is appended to [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) in the stamping commit. ⛔ **The row does NOT arm the launcher** |
| (c) | **the seven cells and their weights** (§3) | ✅ **GIVEN — OWNER, 2026-08-27** | Same "fund them all". And the weights are **not re-picked**: every one is `×⅓` or `×3` of a round-1 mid, and **round 1 named all six points in its own §3.4 bracket table before it had an answer**. Shape C's three points are round 1's named gamma ladder, also pre-registered there |
| (d) | **tie-arbiter OFF on both sides** | ⚙️ **ORCHESTRATOR-PROCEDURAL — DONE at freeze** | Unchanged from round 1. The arbiter is a separate, separately-adjudicated lever. The launcher emits **no** `--cand-tiearb-*` flag of any spelling, and the opponent side is **structurally** disarmed (`eval_fair_puct.py` has no `--opp-tiearb-*` flag). `G-TIEARB` records the absence as *verified* |
| (e) | **TENANCY CLASS: NON-EXCLUSIVE, RESULT-SAFE** (§6.3) | ⚙️ **ORCHESTRATOR-PROCEDURAL — DECLARED at freeze** | Unchanged from round 1 and for the same reason: this pair is SIMS-denominated, has no timing bar, and its outcomes are bit-identical under co-tenancy and at any W. It may run beside the 1-core `reconcile_exact_solver.py` suite. ⚠️ **But the BOX is NOT free this round** — see (f) |
| (f) | ⭐ **THE WHEEL IS PINNED AND SHIPPED, NEVER REBUILT** | ⚙️ **ORCHESTRATOR-PROCEDURAL — DECLARED at freeze** | A consequence of §3.1's inherited IDENT. `G-WHEEL-SAME` keys on `carc_rs_binary_sha`, which is **box-local by build** — two boxes *compiling* identical source with an identical toolchain produce different bytes (measured 2026-08-17). ⭐ **So the executor ships the WHEEL FILE rather than rebuilding**: the same `carc_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl` (sha `a9ac686bca1417f9`) is `pip install`ed on **both** boxes, the sha is identical on every cell regardless of host, and the gate passes on both. ⛔ **A laptop-local `maturin build` produces a different sha and the gate REFUSES — correctly**, because a rebuilt wheel is one whose weight-0 identity this program has never checked |

⛔ **THE INTERLOCK, UNCHANGED FROM THE HOUSE PATTERN AND NOT A FORMALITY.** `BAND_CLAIMED` is
**deliberately NOT created at freeze**, and [`run_cells.sh`](run_cells.sh) refuses every real cell
without it. Claiming the registry row protects against a concurrent-session band race; it does
**not** arm the launcher, and the owner's funding does not create the sentinel either.

### ⭐ PRE-LAUNCH CHECKLIST — the EXECUTOR-OWED artifacts

Everything the build could do is done. These are the things it **structurally could not**, and
each is a real launch blocker:

- [x] **(a) funding signed off by the owner** — "fund them all", 2026-08-27
- [x] band claimed in [`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) (`152000000000`, §5), after re-running the all-branches sweep
- [x] this pair (`DESIGN.md` + `READ_RULE.md` + launcher + adjudicator + `screen_lib.py`) frozen and committed
- [ ] `BLIND_COMMIT` stamped with the freeze commit's own sha (the launcher refuses a real cell on the `PENDING` placeholder; a commit cannot name its own hash, hence the stamping commit)
- [ ] ⭐ **`PINNED_SRC_REV` WRITTEN BY THE EXECUTOR AT LAUNCH HEAD — ON *EACH* BOX.** ⚠️ **THIS BIT US ONCE.** It must equal `git rev-parse HEAD` **on that box, at launch**, and a commit cannot contain its own sha — so it is written UNCOMMITTED, immediately before `chmod +x`, **on both machines**:
      ```
      git -C <that box's repo> rev-parse HEAD \
        > <that box's repo>/measurement/invasion_screen_r2_prep/PINNED_SRC_REV
      ```
      SAFE: `measurement/` is excluded from `CODE_PATHS`, so writing it does not dirty the tree the gate checks. **`G-REV` reads "PINNED_SRC_REV ABSENT — ABSENT is FAIL" without it, and ABSENT-is-FAIL is not negotiable.** ⭐ The two boxes' values **must be equal** — the bundle sync below is what guarantees it, and the adjudicator checks that all seven cells report **one `code_rev`** across both machines
- [ ] ⭐ **GIT-BUNDLE SYNC repo → laptop** (the offline pattern, `reference_offline_git_bundle_sync`). ⚠️ **The laptop cannot reach GitHub.** Bundle the launch rev onto the share, `git fetch <bundle>` on the laptop, `git reset --hard` to the launch rev. ⛔ **Without it the laptop runs stale code and the round is mixed-rev across machines** — the `track_d2_prep` defect, with an extra machine
- [ ] ⭐ **WHEEL scp + install on the LAPTOP** — the same file, never a rebuild (§7, §0(f)):
      ```
      scp /home/doctor/carc_wheels/carc_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl laptop-wsl:/tmp/
      ssh laptop-wsl 'bash -s' <<< 'cd ~ && .venv/bin/pip install --force-reinstall --no-deps /tmp/carc_rs-*.whl'
      ```
      then verify `carc_rs_binary_sha == a9ac686bca1417f9` on the laptop — the launcher's own pre-flight asserts it, per box
- [ ] **the `carc_rs` wheel VERIFIED IDENTICAL to round 1's, ON BOTH BOXES** — §7. ⚠️ **Round 2 does NOT want a rebuild anywhere.** The launcher asserts this at pre-flight and `G-WHEEL-SAME` re-asserts it at adjudication, per cell
- [ ] `analyze_screen.py --selftest` GREEN, **seeded from a real manifest** (§9.1)
- [ ] ⭐ **the §9 smoke has run ON EACH BOX** — laptop `C_MID` @ `152999999000`, local `B_LOW` @ `152999999100` — each with `n_failed == 0` **and the adjudicator run against that box's smoke archive, failing only on the pinned allowed set**
- [ ] `chmod +x run_cells.sh` **on both boxes** (tracked at 644, deliberately)
- [ ] `BAND_CLAIMED` dropped **on both boxes** (the launcher refuses every real cell without it, per box)
- [ ] ⭐ **BOTH BOXES LAUNCHED, CONCURRENTLY, EACH WITH ITS OWN `--host`:**
      ```
      # local
      setsid nohup ./measurement/invasion_screen_r2_prep/run_cells.sh --host local </dev/null >/dev/null 2>&1 & disown
      # laptop -- the piped-script ssh pattern, `cd` on line 1 (feedback_remote_ssh_pipe_script_mandatory)
      ssh laptop-wsl 'bash -s' <<'EOF'
      cd /home/doctor/projects/carcassone
      setsid nohup ./measurement/invasion_screen_r2_prep/run_cells.sh --host laptop </dev/null >/dev/null 2>&1 & disown
      EOF
      ```
      ⚠️ A detached ssh launch returns **rc=124 from `timeout` AFTER launching** — treat 124 as LAUNCHED and **never retry** (`feedback_wsl_ssh_launch_pkill_traps`; a retry stacks pools)
- [ ] `RUN_LIVE.json` sentinel dropped for the duration — the launcher does this itself, on each box
- [ ] ⭐ **ADJUDICATION RUNS ON THE LOCAL BOX, over the share-collected archives, once BOTH boxes are done** — `analyze_screen.py --run-dir /mnt/c/carc-shared/invasion_screen_r2_20260827`. It needs all seven cells: `G-WHEEL-SAME` is round-wide, `G-REV` checks one `code_rev` across both boxes, and §4's round table reads every cell

---

## 1. THE QUESTION

Round 1 asked whether *any* invasion shape moved the deck-paired margin at a scale-matched mid
weight. It answered **MIXED**: `B_MID` (`invasion_alpha 0.09 @ cap 11.0`) read **+0.7575 pts/deck,
z 1.265** — a `BRACKET`, the program's **first live leaf-term signal on the clean ruler** — while
`A_MID` read a null so exact it is almost comic (`z = 0.99993`, seven ten-thousandths below its own
`+1σ` bar) and `D_MID` read `−0.291 / z −0.490`. `IDENT` passed. Round 1's own branch table
licensed exactly this: *"the two named round-2 points for that shape, on a fresh band, as one
funding request."*

**Round 2 asks the follow-up question round 1 was built to hand it:**

> Does the signal **SCALE WITH WEIGHT**? And — the question round 1 deliberately declined to
> ask — does the DEFENCE shape pay **against an opponent that actually invades**?

Three sub-questions, one per shape:

1. **A** (`invasion_beta`, contested-value transfer): its mid was a hair under `+1σ`. Does `×3`
   turn it into something, or does `×3` over-correct on top of `opp_bonus_cap` and reverse it?
2. **B** (`invasion_alpha`, stub-claim merge-potential): the one shape that fired. Does `+0.76`
   at `0.09` grow toward `0.27`, or is it a flat effect that the screen cannot resolve at any
   weight?
3. **C** (`invasion_gamma`, dumping-ground discount): **never screened at all.** Round 1 deferred
   it in full on [`SHAPES.md`](../invasion_term_build/SHAPES.md) §3's own rule — *"An H2H-vs-champion
   NULL for C is EXPECTED and is NOT disconfirming (the champion does not invade). Screen C
   against a shape-B agent or against E4, never against the base champion."* Round 2 builds that
   opponent.

**It is still a SCREEN, not a verdict.** §2.4 and `READ_RULE.md` §5 hold: 2752 is the screening
budget, production is 11008, and screens aim rather than verdict.

### 1.1 ⭐ THE E4 OVERFITTING OBJECTION — answered again, because round 2 makes it sharper

Round 1 recorded that the E4 census plays exactly two roles, both upstream of measurement:
**DISCOVERY** (where the mechanism was found) and **SIGN-FIXTURES / SCALE** (where each shape's
direction was unit-tested and where `G` and `M_shape` were measured). No objective function was
optimized on E4 data; no weight was tuned to win an E4 game; no E4 outcome enters any bar.

**Round 2 adds a wrinkle that has to be named before it is discovered.** Shape C's opponent is
not the champion — it is **an agent built out of shape B**, and shape B came from the same census.
So a `C` cell measures *one term from the census against another term from the census*. Two things
follow, both frozen here:

- **It is still not a fit.** The shape-B agent is a fixed, pre-registered, published leaf
  (`42adadc988784b44`, bit-for-bit round 1's `B_MID` candidate) whose weight was derived before
  round 1 had any result. Nothing about it is chosen to make C look good.
- ⛔ **But it narrows what a C result means, and `READ_RULE.md` §4.6 says so in its branch text:**
  a positive C margin says *the defence pays against THIS invader*. It does not say the agent is
  stronger, and it says nothing about play against the champion of record or against Carcasum.
  That is why **no C reading of any size enters the four-link adoption chain.**

---

## 2. THE INSTRUMENT — production leaf, screening budget, both sides rust

Identical to round 1 except where §2.5 says otherwise.

`scripts/classical_search/eval_fair_puct.py`, `--opponent fair-champion` (a `_HEAD_TO_HEAD` mode),
`--backend rust` on **both** sides, deck-paired.

| knob | value | source |
|---|---|---|
| `--info` | `fair` | fair PIMC, not clairvoyant |
| `--opponent` | `fair-champion` | head-to-head mode ⇒ `converted_sides == ["candidate","opponent"]` |
| `--backend` | `rust` | ⛔ **not a speed preference.** The invasion family exists ONLY in rust; both python leaves `raise NotImplementedError` on a nonzero weight ([`SHAPES.md`](../invasion_term_build/SHAPES.md) §"RUST PATH ONLY"). ⭐ **Round 2 needs this on the OPPONENT side as much as the candidate's** — the C cells' opponent carries a nonzero weight |
| `--k-dets` / `--sims` | `4` / `688` (= **2752** total) | the screening budget; `--opp-k-dets`/`--opp-sims` identical |
| `--exact-k` | `2`, marginalized | the fair deployable handoff; K=3/4 are clairvoyant-only |
| `--c-puct` / `--tau-p` | `1.5` / `5` | `governance/PRODUCTION.yaml` champion.search |
| `--leaf-quantize` / `--final-select` | `float` / `visits` | as production |
| `--rules-profile` | `fixed_v1`, with `CARCASSONNE_FIX_R9=1` **exported before the process starts** | R9 is import-latched (a rust `OnceLock`); the preflight runs in a CHILD |
| tie-arbiter | **OFF both sides** | §0(d) |
| candidate leaf | curve125 champion **plus the cell's invasion knob** | §3 |
| opponent leaf | **A/B cells:** the plain curve125 champion, `a36d2e15a3b3d71d`. **C cells:** the SHAPE-B AGENT, `42adadc988784b44` | §2.5 |

### 2.1 — `--cand-leaf-json` is a candidate-side-only knob

Verified in source (`eval_fair_puct.py:3769-3778`), quoted because §2.5 rests on it:

```python
        if _h2h:
            # The OPPONENT is the production champion (or a second production-config
            # net): ALWAYS curve125, never the user's --cand-leaf-json (which is a
            # CANDIDATE-side knob — the reference side must not move with it, exactly
            # as the h800 rung never takes it).
            opp_leaf_cfg = _curve125_leaf_cfg()
```

⚠️ **Every cell's `--cand-leaf-json` MUST carry `v29_meeple_curve` explicitly.** `_load_cand_leaf_cfg`
replaces named fields on the **env** `DEFAULT_CONFIG`, which is **curve100**, and
`_assert_netprior_leaf` hard-fails on a candidate whose curve is not CURVE125 — *even with*
`--allow-leaf-hash-drift`. The seven JSON files in this directory each carry curve125 + the knob,
`screen_lib.LEAF_JSON_BODIES` is the frozen text, and the instrument tests assert the files match
it.

### 2.2 — ⚠️ `--allow-leaf-hash-drift` IS REQUIRED ON ALL SEVEN CELLS, and that COSTS a free check

`_assert_netprior_leaf` (`eval_fair_puct.py:493-536`) checks a side's `_leaf_hash` against the
pinned `a36d2e15a3b3d71d` and `SystemExit`s on a mismatch. **Every round-2 cell carries a nonzero
weight**, so every one moves that hash by design and every one needs the flag.

⛔ **This is a LOSS relative to round 1, and it is why `G-LEAF` got STRICTER rather than looser.**
Round 1's `IDENT` cell ran under the **un-relaxed** assertion and passed it — a free extra gate,
paid for by the fact that an explicit-zero config hashes AS the champion. Round 2 has no such cell.
Worse:

> `--allow-leaf-hash-drift` is a **single** switch that relaxes `_assert_netprior_leaf` on **both**
> sides: `eval_fair_puct.py:3763` (candidate) and **`:3777` (opponent)**.

So on all seven cells the harness's *own* hash assertion enforces **nothing, on either side**.
`G-LEAF` is the only thing left standing between this round and a silently-wrong leaf — and on the
C cells "the opponent leaf drifted" is **expected**, and therefore not a tell. **Only exact
equality against a pre-registered pin distinguishes "drifted to the shape-B agent" from "drifted
to something else."** Hence `READ_RULE.md` §3 `G-LEAF`'s four conjuncts, per cell, both sides,
exact, implemented once in `screen_lib.leaf_gate()` and called by **both** the launcher's per-cell
pre-check and the adjudicator.

### 2.3 — ⚠️ the silent-cap-drop trap, now on BOTH sides

`rust_agent.leaf_config_rs` (`src/carcassonne_ai/rust_agent.py:181-185`) forwards
`invasion_alpha_cap` and `invasion_stub_max_tiles` **only when `invasion_alpha != 0.0`**:

```python
        if float(getattr(leaf_cfg, "invasion_alpha", 0.0)) != 0.0:
            if float(getattr(leaf_cfg, "invasion_alpha_cap", 0.0)) != 0.0:
                invasion["invasion_alpha_cap"] = float(leaf_cfg.invasion_alpha_cap)
```

A side that set a cap **without** a nonzero alpha would have the cap silently dropped by the rust
config while the manifest's leaf dict still showed it — a manifest that lies about the running
leaf. Round 1 checked this biconditional on the candidate. **Round 2 checks it on BOTH sides**,
because the C cells' *opponent* is the only reference leaf in this program's history to carry a
nonzero alpha, and it carries a cap with it.

⚠️ And it is the reason the C candidates' explicit zeros are written as **`invasion_alpha: 0.0`
AND `invasion_alpha_cap: 0.0`** rather than alpha alone: a candidate that zeroed alpha but
inherited the env's `cap 11.0` would trip `G-CAPFWD` — correctly, because rust would drop the cap
and the manifest would not.

### 2.4 — this is NOT a production H2H, and the harness says so out loud

`k4×688 = 2752` is the **screening** budget. `governance/PRODUCTION.yaml`'s champion is
`k8×1376 = 11008`, and the harness prints a non-fatal warning on every cell about the deviation.
**Expected. Do not suppress it.** `READ_RULE.md` §5 forbids any branch from narrating a cell as a
production result.

⭐ **ROUND 2 EXPECTS A SECOND NON-FATAL WARNING, ON THE C CELLS ONLY, AND IT IS ALSO EXPECTED.**
With `--allow-leaf-hash-drift` set, `_assert_netprior_leaf` prints

> `[warn] [head-to-head] opponent leaf hash drift: _leaf_hash 42adadc988784b44 != expected a36d2e15a3b3d71d …`

and stamps `hash_drift_allowed: true` into `config.opponent.curve125_leaf_provenance`. That warning
is **the mechanism working**, not a defect: it is the harness observing exactly the substitution
§2.5 designs. ⛔ **Do not suppress it, and do not "fix" it** — a C cell that did *not* print it
would be a C cell playing the plain champion, which is the one cell SHAPES.md §3 forbids.
A third warning fires on both sides of a C cell from `_assert_cy_float_path`
(`[leaf-override] WARNING: invasion-risk family set … run the cell with --backend rust`) — also
expected, also non-fatal, and true: the cells do run `--backend rust`.

### 2.5 ⭐ HOW THE C CELLS GET A NON-CHAMPION OPPONENT — the mechanism, in full

**The problem.** [`SHAPES.md`](../invasion_term_build/SHAPES.md) §3 requires shape C to be screened
against an invader. But `eval_fair_puct.py:3774` hands every head-to-head opponent
`_curve125_leaf_cfg()` **unconditionally**, and there is **no `--opp-leaf-json` flag of any
spelling** (verified: the harness's only `--opp-*` flags are `--opp-net`, `--opp-orch-shm-name`,
`--opp-sims`, `--opp-k-dets`).

**The mechanism.** `_curve125_leaf_cfg()` is not a constant — it is

```python
def _curve125_leaf_cfg():
    """The production curve125 champion leaf = env DEFAULT_CONFIG with ONLY the
    meeple curve replaced (the --cand-leaf-json mechanism, applied in-process)."""
    return _dc.replace(DEFAULT_CONFIG, v29_meeple_curve=CURVE125)
```

and `DEFAULT_CONFIG` is `virtual_score_v2._config_from_env()`, **resolved from the environment at
import time**, including:

```python
        invasion_alpha=float(os.environ.get("CARCASSONNE_INVASION_ALPHA", "0.0")),
        invasion_alpha_cap=float(os.environ.get("CARCASSONNE_INVASION_ALPHA_CAP", "0.0")),
```

So exporting those two **before the process starts** moves the OPPONENT's leaf. And the candidate
is `_load_cand_leaf_cfg`, which *"replaces ONLY the named fields on the env-resolved
DEFAULT_CONFIG"* — so the candidate takes them back off with **explicit zeros**:

```
  ENV:        CARCASSONNE_INVASION_ALPHA=0.09  CARCASSONNE_INVASION_ALPHA_CAP=11.0
  =>  OPPONENT = curve125 + alpha 0.09 + cap 11.0          = 42adadc988784b44
  JSON:       {"v29_meeple_curve": [...curve125...],
               "invasion_alpha": 0.0, "invasion_alpha_cap": 0.0,
               "invasion_gamma": <g>}
  =>  CANDIDATE = curve125 + gamma <g>                      = <the cell's pin>
  =>  the two sides differ in EXACTLY {alpha, alpha_cap, gamma}
```

**All six hashes were computed at freeze through the harness's own `_load_cand_leaf_cfg` +
`_leaf_hash`, once per env regime**, and the derivation was validated by **reproducing all three of
round 1's frozen hashes exactly** (`0fd1680fa363d65e` / `42adadc988784b44` / `5012569b4e93d559`)
plus the champion pin. ⚠️ Deriving *without* the harness reproduces **none** of them — the harness
installs its own `_CANON_ENV` (v2.9 Bmild_cap8) with `os.environ.setdefault` above every
`carcassonne_ai` import, and `DEFAULT_CONFIG` is resolved from it. `_CANON_ENV` carries **no
invasion key**, so `setdefault` cannot overwrite the two exported values and the two settings
compose by construction.

**Five properties of this route, all load-bearing:**

1. ⭐ **THE OPPONENT LEAF REACHES RUST.** `_make_opponent` builds `opp_cfg = _cfg_from_dict(cfg_dict,
   opp_leaf_cfg)` and hands it to `_make_champion(..., backend="rust")`, which resolves through
   `search_config_rs` → `leaf_config_rs(cfg.resolved_leaf_cfg())`. The same conditional-kwarg path
   the candidate takes. **Nothing in this program has ever exercised that direction**, which is why
   §7's wheel probe now forwards the opponent leaf too and why `WHEEL_PROBE.json` carries an
   `opp_side_forward_ok` key.
2. ⭐ **THE CHAMPION-FACTORY GUARDS DO NOT FIRE.** `build_fair_champion` with an explicit `cfg`
   never calls `_verify_frozen_leaf`, whose fingerprint check *raises* on hash drift. (And even if
   it did, the leaf-VALUE panel is evaluated on an EMPTY board where no component is claimed, so
   every invasion term is identically 0 there — which is why round 1's nonzero *candidates* passed
   the same path.) Established empirically by round 1: three drifted candidates played 2400 games.
3. ⚠️ **THE ENV IS EMITTED INTO EACH ARGV, NEVER EXPORTED PROCESS-WIDE**, and it is emitted on
   **every** cell — pinned to `0.0/0.0` on the A/B cells. A process-wide export would give the A/B
   cells a shape-B opponent too, which is the single most damaging thing this launcher could do;
   and pinning the regime OFF explicitly means a stray `CARCASSONNE_INVASION_*` in the
   orchestrator's shell cannot reach an A/B cell. `float("0.0")` **is** the dataclass default, so a
   pinned-off cell is byte-identical to an unset one.
4. ⚠️ **THE WHEEL PROBE RUNS TWICE, ONCE PER REGIME**, because `DEFAULT_CONFIG` latches at import
   and no single process can observe both opponents. Each regime writes its half of
   `WHEEL_PROBE.json`; the launcher merges them and re-checks the merged artifact through
   `screen_lib.wheel_probe_ok()`.
5. ⛔ **AND IT BREAKS ROUND 1's SINGLE-VARIABLE WORDING, so round 2 restates it.** Round 1 could
   say "the cell's ONE knob". Round 2 says: **the two sides differ in EXACTLY the pre-registered
   term knobs** — one key on an A cell, two on a B cell, **three** on a C cell. `G-SINGLEVAR(b)`
   checks that set equality **two-sided** against the emitted manifest.

---

## 3. THE CELLS

**Seven cells, 400 decks / 800 games each, all at `k4×688 = 2752` both sides, rust both sides,
arbiter OFF both sides, `fixed_v1`+R9, `exact-k 2` marginalized, deck-paired, on band
`152000000000`, each on its OWN DISJOINT deck range (§5).**

| cell | shape | rung | **box** | candidate leaf (curve125 +) | candidate hash | opponent | opponent hash |
|---|---|---|---|---|---|---|---|
| `A_LOW` | A | ×⅓ | local | `{invasion_beta: 0.04}` | `f8c0f04092734f9e` | plain champion | `a36d2e15a3b3d71d` |
| `A_HIGH` | A | ×3 | local | `{invasion_beta: 0.36}` | `f6ce81145cbd5102` | plain champion | `a36d2e15a3b3d71d` |
| `B_LOW` | B | ×⅓ | local | `{invasion_alpha: 0.03, invasion_alpha_cap: 11.0}` | `f5b7a26216794290` | plain champion | `a36d2e15a3b3d71d` |
| `B_HIGH` | B | ×3 | local | `{invasion_alpha: 0.27, invasion_alpha_cap: 11.0}` | `1a42effad7066c0b` | plain champion | `a36d2e15a3b3d71d` |
| `C_LOW` | C | low | **laptop** | `{invasion_alpha: 0.0, invasion_alpha_cap: 0.0, invasion_gamma: 0.08}` | `a6ab04dbb69ad29e` | ⭐ **SHAPE-B AGENT** | `42adadc988784b44` |
| `C_MID` | C | mid | **laptop** | `{… invasion_gamma: 0.23}` | `897c21aca11b6fbd` | ⭐ **SHAPE-B AGENT** | `42adadc988784b44` |
| `C_HIGH` | C | high | **laptop** | `{… invasion_gamma: 0.69}` | `df34cb874fea6273` | ⭐ **SHAPE-B AGENT** | `42adadc988784b44` |

⭐ **The `box` column is FROZEN and GATED** — §6.5, and `G-HOST`.

Every cell runs with `--allow-leaf-hash-drift` (§2.2). The C cells additionally carry
`CARCASSONNE_INVASION_ALPHA=0.09 CARCASSONNE_INVASION_ALPHA_CAP=11.0` in their argv (§2.5); the
A/B cells carry the same two variables pinned to `0.0/0.0`.

### 3.1 ⭐ THERE IS NO IDENT CELL, AND THE INHERITANCE IS MECHANISED

Round 1 spent 400 games proving that an explicit-zero invasion config survives the whole pipeline —
CLI parse → `_load_cand_leaf_cfg` → `leaf_config_rs`'s conditional kwargs → the rust leaf → 400
games of scoring — unchanged. **It PASSED on every conjunct:**

```
|z| = 0.9624  <=  2.0        (D +0.8325, SE 0.8650, n_paired 200)
cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d   (the champion pin)
n_failed == 0                leaf diff EMPTY
cost multiplier 0.997        (the ≈1.0 control)
```

**Round 2 does not re-buy that proof.** At round-2 cell size an IDENT would cost ~15 core-h, about
11% of the round, to re-establish something a clean 400-game cell established three weeks of
nothing ago.

⛔ **BUT THE SAVING IS CONDITIONAL, AND THE CONDITION IS A GATE, NOT A SENTENCE.** What makes a
wiring proof transfer is that the wiring has not moved, and the wiring is *the compiled wheel*.
So `READ_RULE.md` §3 carries **`G-WHEEL-SAME`** in the slot round 1's `G-IDENT` occupied — a
**round-level** gate whose FAIL voids **all seven cells**, exactly as a failed `G-IDENT` voided all
four:

> every manifest's `carc_rs_binary_sha` must equal **`a9ac686bca1417f9`**, the wheel round 1's
> IDENT was measured on. **A CHANGED WHEEL RE-OWES AN IDENT CELL.**

The launcher asserts the same predicate at pre-flight (through the same `screen_lib.wheel_is_r1s()`),
so a rebuilt wheel is caught **before any game**, not at adjudication.

⚠️ **AND THE CONVERSE STAYS TRUE**, exactly as round 1 recorded it: a passing IDENT proves the
plumbing carries a **zero** faithfully. It does **not** prove a nonzero weight reaches the rust
leaf — that is `G-INVASION`'s, `G-CAPFWD`'s and `G-WHEEL`'s job, and `G-LEAF`'s two-sided pins are
the cheap cross-check. Round 2 leans on those *more* than round 1 did, not less.

### 3.1a — ⛔ `carc_rs_build` IS NOT A WHEEL FINGERPRINT. THIS BUILD FOUND OUT BY FAILING.

The first implementation of `G-WHEEL-SAME` required **both** `carc_rs_binary_sha` **and**
`carc_rs_build` to match round 1's. It **failed `--selftest` against round 1's own emitted
archive** — the one archive in existence guaranteed to be the same wheel — because round 1's two
archives disagree:

```
invasion_screen_20260826/smoke_b_mid   build carc_rs-0.1.0+47e7cc0ffb31+rustcunpinned
invasion_screen_20260826/b_mid         build carc_rs-0.1.0+ac709c42c6e2+rustcunpinned
BOTH                                   binary_sha a9ac686bca1417f9
```

`rust_agent.carc_rs_build_id()` composes `carc_rs-<cargo version>+<REPO REV AT CALL TIME>+rustc<tc>`.
**The rev is read off the working tree when the manifest is written; it is not compiled into the
wheel and it does not move when the wheel does.** The smoke and the cells ran the same `.so` from
two different tree HEADs. The source says so itself — `carc_rs_binary_sha`'s docstring is *"the
only thing that can prove the installed wheel actually carries the surface under test"*, and
`carc_rs_build_id`'s is *"⚠️ Why NOT the binary hash … the box-local staleness question is answered
separately, by `carc_rs_binary_sha`"*.

**Consequences, all frozen here:**

- `G-WHEEL-SAME` keys on **`carc_rs_binary_sha` alone**. The build string is reported beside it as
  INFORMATIONAL — it is a code-rev fact, and the code-rev question is `G-REV`'s, which owns
  `PINNED_SRC_REV` and `SRC_CLEAN.jsonl` and answers it properly.
- ⚠️ **It narrows what round 1's inherited `G-WHEEL` ancestry conjunct proves**, and round 2 states
  it rather than repeating round 1's wording: the embedded rev proves **the tree the games ran from**
  carried `invasion.rs`, not that the **wheel** did. Still worth having; largely duplicated by
  `G-REV`; **no round-2 branch may claim it proves a wheel identity.** Round 1's own gate text is
  not amended retroactively — its round is closed.
- ⚠️ **`carc_rs_binary_sha` is BOX-LOCAL**, hence §0(f): round 2 runs on the box round 1 ran on.

**This is what a satisfiability control is for.** `READ_RULE.md` §3.1 question 2 asks *"can a
healthy run pass it?"* — and the honest way to ask it of a brand-new gate is to point it at real
emitted output rather than at a fixture built to agree with it. The gate was wrong; the archive was
right; the gate moved.

### 3.2 ⭐ THE WEIGHTS ARE NOT RE-PICKED — round 1 named all six points before it had an answer

Round 1's [`DESIGN.md` §3.4](../invasion_screen_prep/DESIGN.md), written and committed **before any
game ran**:

> `feedback_bracket_hyperparams`: three well-spread points, and a peak at a ladder endpoint is not
> bracketed. The low/high points are `×⅓` and `×3` of the frozen mid:
>
> | shape | low (×⅓) | mid (RUN in round 1) | high (×3) |
> |---|---|---|---|
> | A `invasion_beta` | 0.04 | 0.12 | 0.36 |
> | B `invasion_alpha` (@ cap 11.0) | 0.03 | 0.09 | 0.27 |
> | D `invasion_delta_farm` | 0.04 | 0.12 | 0.36 |
> | C `invasion_gamma` *(round 2 in full)* | 0.08 | 0.23 | 0.69 |

**Round 2 runs six of those eight unrun points** — A's two, B's two, and all three of C's — and
re-derives nothing. The derivation constants are unchanged and restated by the adjudicator on every
branch: `G = 1.76` leaf points (the champion leaf's own median sibling `p90−p10` over the 93
Stage-A census invasion positions, corroborated at `1.72` by the mean top1−top2 gap from a
completely different definition); `M_A = M_D = 6.0`, `M_B = 8.0`, `M_C = 3.03` (each shape's median
`|T|` when it fires, on the same corpus); target `0.40 × G = 0.704`; `invasion_alpha_cap = 11.0`
(the Stage A census median `invader_gain` over the 51 `mech == "merge"` rows, which binds only the
top decile of the leaf's own view of those features).

⚠️ **What `×3` means in leaf points, stated so no branch is surprised by a reversal.** At
`beta = 0.36`, shape A contributes `0.36 × 6.0 = 2.16` leaf points on this corpus — **123% of `G`,
the champion leaf's entire sibling-move spread.** That is no longer a tilt on the leaf; it is a
re-weighting of it. Round 1's §3.2(iv) made the same point about `beta = 1.0` (341% of G) to
explain why the natural unit weight was outside a screening range. `×3` is inside the range the
skeleton named, and it is also the point where an over-correction on top of `opp_bonus_cap = 8`
becomes a live hypothesis rather than a footnote — which is exactly why `READ_RULE.md` §6's prior
puts `~7%` on a `REVERSED` reading concentrated on `A_HIGH` and `B_HIGH`.

### 3.3 — ⛔ SHAPE D IS NOT RUN

Round 1's `D_MID` read `D −0.291 / z −0.490` — a bounded null **below zero** — and round 1's own
§3.2(v) measured `T_D`'s one-ply sibling-Δ as **~0 at 94.6% of the census positions**, making a D
reading the least informative of the family about its own mechanism. Bracketing a shape that read
below zero at its scale-matched mid buys the least per core-hour on the menu, and **the owner's
funded menu named the B bracket, the A bracket and the C-vs-B-agent cells — not D.**

⛔ **No branch may say anything about shape D at any weight other than round 1's mid.** And
`READ_RULE.md` §5 carries round 1's A/D collinearity rule forward for the one case where it still
bites: a readout that reaches back to round 1's `D_MID` to interpret round 2's A cells must read
them on the `(beta, beta + delta_farm)` basis and must never describe A and D as independent
shapes — `T_A ≡ (cities+roads part) + T_D` exactly, by construction and unit test.

### 3.4 — ⚠️ A AND B ARE **NOT BRACKETED** WITHIN ROUND 2. C IS.

This is the round's most important structural limitation and it is stated before any number.

A's and B's round-2 ladders have **two points** — `×⅓` and `×3` — and their interior point is
round 1's mid, **on another band**, admissible only as a descriptive overlay (§4.5b of the read
rule). **A two-point ladder has no interior**, so:

- ⛔ **EVERY A/B READING SITS AT A LADDER ENDPOINT BY CONSTRUCTION**, and
  `feedback_bracket_hyperparams` says a peak at an endpoint is **not bracketed**. A `PROMOTE` at
  `×3` licenses the production H2H **at that weight** and owes a ladder **extension** before any
  claim about an optimum; a `PROMOTE` at `×⅓` owes an extension **downward**.
- ⛔ **No branch may say "the optimum is at ×3" or "the term is monotone" from two endpoints.**

**Shape C is the exception, and the only shape genuinely bracketed this round:** three points
(`0.08 / 0.23 / 0.69`) on **one band**, so `C_MID` is a real interior rung. Round 1's
noise-signature rule therefore applies to it **literally** — if `C_MID` fires while **both**
`C_LOW` and `C_HIGH` read `>1σ` lower, it is a noise signature and is **re-measured before it is
believed**, never promoted from the single screen. `screen_lib.noise_signature()` computes it and
the adjudicator prints it on every branch.

### 3.5 — ⭐ ADOPTING SHAPE A OR B OWES A CAPS RE-SWEEP

Carried verbatim from round 1 §3.6, and it now applies to B as well because B is the shape most
likely to fire. [`SHAPES.md`](../invasion_term_build/SHAPES.md) §1: shape A *"subtracts from the
same objects the capped opponent-anticipation bonus already discounts (`V25_OPP_CAP` /
`opp_bonus_cap = 8`)"*, and nothing in the build resolves that overlap.

**Stated before any number exists:** if an A or B cell reads `PROMOTE`, the production H2H it earns
is **not** a straight adoption. Per `feedback_bug_fix_shifts_optima`, adoption obliges a
**re-sweep of `bonus_cap` / `opp_bonus_cap` against the new term**, because the incumbent caps were
tuned against a leaf that did not have it. **A promotion funds a sweep, not a
`governance/PRODUCTION.yaml` edit.** `READ_RULE.md` §4's `PROMOTE-<shape>` branch carries the
obligation in its text.

---

## 4. THE PRIMARY STATISTIC AND ITS POWER — arithmetic BEFORE any number

```
Per cell, for each deck d in that cell's OWN range that appears in BOTH seatings:

    D(d) = ( diff(d, a_seat=0) + diff(d, a_seat=1) ) / 2

  where diff is the harness's own final-score margin, CANDIDATE minus OPPONENT
  (eval_fair_puct.py:1603 -- `diff = (s0-s1) if a_seat==0 else (s1-s0)`), in POINTS.

D      = mean( D(d) )  over n_common decks
SE(D)  = stdev( D(d) ) / sqrt(n_common)      -- sample stdev, ddof=1
z_D    = D / SE(D)
```

This is `eval_fair_puct._paired_z`'s own construction (`2371-2383`), and the adjudicator recomputes
it from the raw `seed*_a*.json` records as an independent **witness** (`RECON`).

**Sign convention, load-bearing:** `D > 0` means the **candidate won**. On an A/B cell that means
the invasion term beat the plain champion. ⭐ **On a C cell it means the DEFENCE beat the INVADER**
— a different proposition, and `READ_RULE.md` §4.6 is the mandatory prose.

**Cluster = deck.** Not game, not seat. **Primary unit = POINTS per deck.** Elo is display-only and
is never a branch input.

**Within-band, deck-paired, one instrument ⇒ NO cross-band humility discount** for a cell's own
margin. CL-068's 1.8–2.2× applies to *cross-band* contrasts; each cell here is its own arm played
on its own decks in one launch window, which is the robust class CLAUDE.md exempts. ⛔ **The r1
mids are a different matter entirely — see `READ_RULE.md` §4.5b.**

### 4.1 — σ_D: the frozen model, and what round 1 actually realized

The sizing model is **carried unchanged from round 1**: `σ_D` inverted off seven `n=400`-deck,
deck-paired, `fixed_v1`+R9, rust-backend cells in [`../../experiments/results.csv`](../../experiments/results.csv)
(`SE = |margin| / |z|`, `σ_D = SE × √400`) — median `13.15`, closest analogue `13.60`, **max
`14.67`**. **This pair sizes on the MAX**, as round 1 did.

⭐ **AND ROUND 1 REALIZED TIGHTER THAN THAT, ON THIS EXACT INSTRUMENT:**

| round-1 cell | realized SE | realized σ_D | ratio vs the 14.67 model |
|---|---|---|---|
| `A_MID` | 0.5238 | 10.48 | 0.714 |
| `B_MID` | 0.5987 | 11.97 | 0.816 |
| `D_MID` | 0.5943 | 11.89 | 0.810 |
| `IDENT` | 0.8650 | 12.23 | 0.834 |

**The model is kept anyway, deliberately.** Keeping the conservative figure means the published
power table **under**-states this round's real resolution rather than over-stating it, which is the
direction a screen that decides funding should err in. Both tables are printed, and every bar is
still evaluated at the cell's **own realized SE** — the model is power arithmetic only and is never
a denominator in a branch test.

⚠️ **A LOW-END SE FLAG IS EXPECTED THIS ROUND AND IS NOT AN ANOMALY.** The `[0.70, 1.43]` flag band
is carried verbatim, and round 1's ratios hugged its **floor** (`A_MID` sat 2% above the flag). A
round-2 cell that flags LOW means "tighter than modelled"; the HIGH end is the concerning
direction. The adjudicator prints which. ⛔ The band does not move for that, and the flag is
reported, never a branch input.

### 4.2 — what n=400 buys, at both dispersions

```
SE_D(model 14.67, n=400)     = 0.7335 pts   ->  2 sigma = +-1.467 pts
SE_D(realized ~11.97, n=400) = 0.5987 pts   ->  2 sigma = +-1.197 pts
```

**Power of a cell, computed before any answer exists** (2-sided α=.05):

| true effect | z @ model SE | power | z @ realized SE | power |
|---|---|---|---|---|
| **+0.76 pts/deck** — ⭐ *round 1's own `B_MID` reading* | 1.04 | ~18% | 1.27 | **~24%** |
| +1.20 | 1.64 | ~38% | 2.00 | ~52% |
| +1.47 | 2.00 | ~52% | 2.45 | ~69% |
| +1.68 | 2.29 | ~62% | 2.80 | **80%** |
| +2.06 | 2.80 | **80%** | 3.44 | ~94% |

⛔ **READ THE FIRST ROW BEFORE ANY OTHER LINE IN THIS DOCUMENT.** If shape B's effect is **flat**
at `+0.76` pts/deck — the same size round 1 measured at the mid — then **neither `B_LOW` nor
`B_HIGH` is likely to reach `+2σ`**: the chance is about **24%** per cell even at round 1's realized
dispersion. **THIS ROUND IS POWERED TO DETECT SCALING, NOT TO CONFIRM ROUND 1's MID.** A round that
comes back `FAMILY-PARKS` therefore does **not** refute round 1's `BRACKET`; it bounds the *growth*
of the effect with weight. `READ_RULE.md` §4's `FAMILY-PARKS` branch is required to say so in those
words, and §6's prior is written against it.

### 4.3 — elo is display-only, and the conversion is guarded

Carried verbatim from round 1 §4.3: **if `|z_C| ≥ 2.0`** the cell's own realized `elo/pt` is
reportable (cross-checked against the in-family bracket `[16.74, 19.35]` elo/pt, an anomaly outside
it FLAGGED and never a branch input); **otherwise** the elo display is quoted as a **range through
that pinned bracket** and labelled a bracket conversion, not a measured scale. Under a null `D ≈ 0`
and a cell's own `elo/D` is a quotient of two noisy near-zero quantities: it does not converge and
its sign is not stable. The adjudicator implements the branch-dependent rule and prints which limb
applied.

---

## 5. THE BAND

**Band `152000000000`.** ⛔ The row is in [`BAND_CLAIM.json`](BAND_CLAIM.json) and is appended to
[`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) by the orchestrator in
the stamping commit. **`BAND_CLAIMED` is NOT created** (§0's interlock).

### 5.1 — allocation: one band, seven DISJOINT deck ranges, no reuse

```
A_LOW   152000000000 .. 152000000399    400 decks   800 games
A_HIGH  152000000400 .. 152000000799    400 decks   800 games
B_LOW   152000000800 .. 152000001199    400 decks   800 games
B_HIGH  152000001200 .. 152000001599    400 decks   800 games
C_LOW   152000001600 .. 152000001999    400 decks   800 games
C_MID   152000002000 .. 152000002399    400 decks   800 games
C_HIGH  152000002400 .. 152000002799    400 decks   800 games
                                       ----------  ----------
                                       2800 decks  5600 games

SMOKE   152999999000 .. 152999999007      8 decks    16 games
        THROWAWAY -- disjoint, discarded, never pooled, never claimed, never adjudicated.
        Deliberately far above the cell ranges so no arithmetic slip can reach them.
        Runs C_MID's config (SS9).

NO TOP-UP RANGE IS RESERVED.  READ_RULE.md SS5 carries no top-up branch: a bounded null is a
licensed outcome of a screen, not a failure state to rescue.
```

⚠️ **DISJOINT, NOT SHARED — a deliberate choice with a named cost, and round 2's cost is bigger
than round 1's.** Each cell's primary statistic is its own internal deck-paired margin, which is
fully CRN'd *within* the cell and needs nothing from a sibling; disjoint ranges cost **the primary
read nothing**.

⛔ **What they DO cost is §4.5's contrast.** Had the two cells of a shape shared one 400-deck set,
the low-vs-high difference would have been **deck-matched** and its SE roughly halved. They do not,
so the contrast is an **unmatched** difference of two independent samples with a root-sum-square
SE, and it resolves at 2σ only for `|Δ| ≥ ~1.7` pts/deck at round 1's realized dispersion. **The
price is paid here, before any number, rather than discovered at adjudication.** The funded design
named 7 × 400 disjoint decks and this pair honours it.

And, as in round 1: **shape-vs-shape ranking is a deck-unmatched contrast** and `READ_RULE.md` §1
forbids any branch from taking "A read higher than B" as an input. Each cell is adjudicated against
**zero**, on its own decks.

### 5.2 — the all-branches sweep, re-run for this pair

The procedure of record ([`../carcasum_arb_challenge_prep/DESIGN.md`](../carcasum_arb_challenge_prep/DESIGN.md)
§4.1, as run by [`../track_d2r4_prep/DESIGN.md`](../track_d2r4_prep/DESIGN.md) §5 and
[`../invasion_screen_prep/DESIGN.md`](../invasion_screen_prep/DESIGN.md) §5.2): for **every** ref in
`refs/heads` and `refs/remotes`, read that ref's own `governance/BAND_REGISTRY.csv` **and** every
`measurement/**/BAND_CLAIM*.json` it carries, then take the lowest integer clear of everything
found anywhere. A registry check scoped to the checked-out branch is blind to an unmerged sibling
freeze branch — that is how `143e9` and `144e9` were double-claimed.

**Re-run 2026-08-27 over 143 refs (125 `refs/heads` + 18 `refs/remotes`) / 723
registry-and-claim files.**

| band | status found | source |
|---|---|---|
| `143000000000` | claimed | `carcasum_rung2_prep` |
| `144000000000` | retired | `track_d2r2_prep` |
| `145000000000` | claimed | `track_d1_fair_rebase` (PRIMARY) |
| `146000000000` | **soft-reserved** | `track_d1_fair_rebase` — earmarked for its own n=800 extension |
| `147000000000` | claimed | `carcasum_arb_challenge_prep` |
| `148000000000` (+ top-up) | claimed | `h2h_22016_prep` |
| `149000000000` | ⛔ RETIRED — burn-in-abort void | `track_d2r3_prep` |
| `150000000000` | ⛔ **SPENT** — `D2-BOUNDED-NULL` | `track_d2r4_prep` |
| `151000000000` | ⛔ **SPENT** — invasion round 1, `MIXED` | `invasion_screen_prep` |
| **`152000000000`** | **free everywhere** | verified two ways: a raw-mention sweep over every ref's registry-and-claim files found **no mention of any band at or above 152e9**, and a direct `15[2-9]000000000,` row-start grep over every ref's registry returned **zero hits** |

`146000000000` is **skipped** on exactly the reasoning `carcasum_arb_challenge_prep`,
`h2h_22016_prep`, `track_d2r3_prep`, `track_d2r4_prep` and `invasion_screen_prep` all used: by the
letter it is unclaimed, but a sibling track has spent a committed paragraph earmarking it, and
taking it would manufacture the exact collision the corrected procedure exists to prevent.

Per CL-068, **band identity is load-bearing**: never pool this pair's numbers across bands — and
⛔ **specifically never with `151000000000`**, whose mids are the natural interior points of A's and
B's ladders and therefore the single most tempting cross-band pool this program has been offered.
`152000000000` **retires from confirmatory use** once it has influenced any decision.

⚠️ **`RELEASE-IF-NEVER-LAUNCHED`**: if no cell ever runs, `152000000000` is released. Once **any**
real record exists on it — including under a round that voids on `G-WHEEL-SAME` — the band is
**spent**, on the `149e9` precedent.

⚠️ **The sweep is RE-RUN immediately before the CSV append**, in the stamping commit, and the
append aborts if `152000000000` has appeared anywhere in the interim.

---

## 6. COST

### 6.1 — ⛔ ROUND 1's PROJECTION MODEL IS RETIRED. ROUND 2 USES ROUND 1's REALIZED NUMBERS.

Round 1 priced itself off a two-point fit ported from `track_d2r4_prep`
(`ms/move(N) = 160 + 0.12025·N`, plus a `+25%` candidate-half margin) and published
**≈54–62 core-h** against a **realized ≈64**. Round 2 does not need a model: round 1 measured every
input **on this exact instrument, at this exact budget, at W=22, with the same solver co-tenant.**

**The measured inputs** (`measurement/invasion_screen_20260826/*/summary.json`):

```
plain-champion side    461.4 / 457.8 / 480.7 / 481.6 ms/move   (mean 470.4)
shape-A candidate      693.8 ms/move    multiplier 1.4434
shape-B candidate      626.2 ms/move    multiplier 1.3679
shape-D candidate      679.7 ms/move    multiplier 1.4115
IDENT (both weight-0)  461.4 / 462.8    multiplier 0.997  <- the CONTROL
```

**The model is arithmetic on those:**

```
s/game = MOVES_PER_SIDE x (ms_cand + ms_opp)/1000 x OVERHEAD
       = 69.0 x (...)/1000 x 1.073
```

where `OVERHEAD = 1.073` is round 1's realized worker-seconds divided by its measured move time on
`A_MID` (87.45 realized vs 81.05 of pure move time): harness, claim I/O, solver tail.

⭐ **AND IT REPRODUCES ALL THREE OF ROUND 1's ARMS WITHIN ~1%:**

| round-1 cell | model | realized (wall × W ÷ games) |
|---|---|---|
| `A_MID` | 86.96 s/game | **87.45** |
| `B_MID` | 80.25 s/game | **79.2** |
| `D_MID` | 86.00 s/game | **85.8** |

`screen_lib.sanity_check()` **asserts** that reproduction to 3%, so a typo in any cost constant
cannot survive to launch.

### 6.2 — per cell, and the ONE named uncertainty

| cell | box | ms cand | ms opp | s/game (local-equiv) | s/game (on its box) | core-h | wall @ W=22 |
|---|---|---|---|---|---|---|---|
| `A_LOW` | local | 693.8 | 470.0 | 86.2 | 86.2 | **19.1** | ≈52 min |
| `A_HIGH` | local | 693.8 | 470.0 | 86.2 | 86.2 | **19.1** | ≈52 min |
| `B_LOW` | local | 626.2 | 470.0 | 81.2 | 81.2 | **18.0** | ≈49 min |
| `B_HIGH` | local | 626.2 | 470.0 | 81.2 | 81.2 | **18.0** | ≈49 min |
| `C_LOW` | **laptop** | 686.8\* | 626.2 | 97.2 | 136.1† | **30.2** | ≈82 min |
| `C_MID` | **laptop** | 686.8\* | 626.2 | 97.2 | 136.1† | **30.2** | ≈82 min |
| `C_HIGH` | **laptop** | 686.8\* | 626.2 | 97.2 | 136.1† | **30.2** | ≈82 min |

| box | cells | core-h | wall @ W=22 |
|---|---|---|---|
| local | A_LOW A_HIGH B_LOW B_HIGH | **74.4** | **≈3.38 h** |
| **laptop** | C_LOW C_MID C_HIGH | **90.7** | **≈4.12 h** |
| **ROUND** | 7 cells / 5600 games | **≈165.1 core-h** | ⭐ **≈4.12 h — the MAX, not the sum** |

⭐ **THE TWO BOXES RUN CONCURRENTLY, so the round's wall clock is the MAX over them.** In
local-equivalent compute the round is **139.2 core-h**; a single-box local run would take
**≈6.33 h**, so the split buys **≈2.2 h of wall clock** at the price of ≈26 core-h of laptop
inefficiency. That trade is the whole content of the owner's directive.

⚠️ **`*` — SHAPE C's PER-MOVE COST IS UNMEASURED.** No gamma cell has ever run. `T_C` is a
**per-component** scan over the mover's own claimed components — the same algorithmic class as A
and D (measured 1.443× and 1.412×) and structurally cheaper than B's **ordered-pair** scan with a
merge-distance test (measured 1.368×, lower because B's pair scan is gated on a small stub set).
The point estimate takes the A/D mean; the honest envelope is `[626.2, 763.2]` ms/move.

⚠️ **`†` — THE LAPTOP'S PER-GAME RATIO IS ALSO UNMEASURED**, and it is the second of exactly two
unmeasured inputs. The planning figure is **×1.4**, inside a **1.3–1.5×** envelope. The nearest
datum is `track_d1_fair_rebase`'s laptop W-COST read of **+73% vs calibration** — but that is a
**PYTHON-backend** cell, where the laptop's slower single thread hurts most, and it does not
transfer to a rust-both-sides cell. ⭐ **The §9 laptop smoke prints a first read before any deck is
spent, and the first laptop pass prints its realized worker-s/game.** ⛔ It moves **no bar and no
branch**: this pair is sims-denominated and no gate reads a clock (§6.3).

```
ENVELOPE (both unmeasured inputs compounded):
    154.7 .. 177.2 core-h across both boxes    /    3.65 .. 4.68 h ROUND wall
```

**§0(a)'s funding line is the RANGE, ≈155–177 core-h / ≈3.7–4.7 h round wall.** Plus the §9
smokes (16 games each, one per box): **≤5 min each**.

⚠️ **A NOTE ON A FIGURE THAT WAS SUGGESTED AND IS NOT REPRODUCIBLE HERE.** A "~120 core-h across
both boxes" estimate was floated when two-box execution was directed. It does not follow from round
1's realized per-move costs: those give **139.2 core-h local-equivalent** before any laptop
inflation, and **165.1** after it. This pair publishes what its own calibration produces, and
`screen_lib.sanity_check()` asserts that calibration reproduces round 1's three arms to 3%.

⭐ **AND THE C CELLS ARE THE FIRST IN THIS PROGRAM WHERE BOTH SIDES PAY INVASION ARITHMETIC.**
Round 1 could charge the margin to the candidate half only (its opponents were all weight-0). A C
cell's opponent carries `invasion_alpha`, so its ms/move ratio is **gamma-vs-alpha, not
term-vs-plain**, and `READ_RULE.md` §4.3(6) requires the readout to label it that way. The smoke
leg will produce **the first observation of shape C's per-move cost**, and the launcher prints it
against the assumed 686.8 — as a discrepancy to **report**, never as a reason to re-freeze.

### 6.3 ⭐ TENANCY CLASS: NON-EXCLUSIVE, RESULT-SAFE — unchanged, and the argument is unchanged

**This pair is SIMS-denominated. It has no equal-time gate, no burn-in and no timing bar.**

1. **Every gate and the primary statistic are functions of GAME OUTCOMES only.** `D(d)` is built
   from final-score margins; the eighteen gates in `READ_RULE.md` §3 read manifest identity, config
   identity, seed coverage, wheel fingerprints and failure counts. Not one of them reads a clock.
2. **Game outcomes are bit-identical under co-tenancy.** The harness is deterministic given
   `(deck seed, seat, config)` — `random.seed(seed)` is the only entropy source
   (`eval_fair_puct.py:2200`), determinizations derive from it (`fair_agent.py:947-951`), and the
   rust search is **bit-identical at any thread count** (`rust/carc/carc-core/src/fair/mod.rs:22-32`
   — the determinization merge is a sequential fold after every join). Round 1 verified run-to-run
   byte-stability empirically on this exact instrument. A co-tenant can change **wall clock** and
   nothing else. `W` is throughput-only for the same reason.
3. **Therefore the only quantity a co-tenant can move is the one this pair deliberately does not
   gate on** — §6.2's ms/move ratio, stamped `DESCRIPTIVE-ONLY` in the readout.

**Concretely: this pair MAY run beside `scripts/rustport/reconcile_exact_solver.py --workers 1`**
and beside other non-timing work. `feedback_no_agent_compute_beside_eval` is honoured, not evaded:
that rule's own text scopes exclusivity to a **TIMING** bench. This is not one. The launcher's
census is **ADVISORY**; the only hard tenancy check is a **foreign `RUN_LIVE.json`** (freeze-latch
discipline, not CPU) and **RAM**.

⚠️ **The one real resource risk is RAM, not CPU.** Concurrent solver jobs carry a 30 GB cap; the
launcher keeps the two-tier RAM floor (preflight and between-passes) and fails closed on it,
because a WSL VM teardown kills the run outright (`reference_wsl2_host_memory_teardown`).

⛔ **AND THE WHEEL IS NOT A FREE CHOICE** (§0(f), §7): the same wheel FILE goes on both boxes.

### 6.5 ⭐ TWO BOXES — the frozen assignment, and why it is the one it is

**Owner directive, verbatim: "get round 2 on both local and laptop".**

| box | reach | W | share mount | cells | smoke |
|---|---|---|---|---|---|
| `local` | the 5900XT, 16C/32T | 22 | `/mnt/c/carc-shared` | `A_LOW A_HIGH B_LOW B_HIGH` | `B_LOW` @ `152999999100` |
| `laptop` | `ssh laptop-wsl` (24T, 11 GB) | 22 | `/mnt/carc-shared` | `C_LOW C_MID C_HIGH` | `C_MID` @ `152999999000` |

`W_LAPTOP = 22` is **`h2h_22016_prep`'s own `W_LAPTOP`** — the closest precedent by workload class
(a rust `eval_fair_puct` head-to-head with **both** sides converted), where it was sized *down* from
W26 against the laptop's 11 GB ceiling. ⚠️ **Not** the `W=14` of the carcasum pairs: those run a JVM
opponent process per game and are a different memory shape entirely.

#### (i) ⛔ WHOLE CELLS PER BOX, AND THE ASSIGNMENT IS FROZEN HERE

A cell's records are **never** split across machines. `screen_lib.CellSpec.box` is the frozen
assignment; `run_cells.sh --host <role>` runs **exactly** that box's cells and **refuses** any
other, before a game starts; and `G-HOST` re-checks it after the fact against the emitted manifest.

⚠️ **`G-HOST` CAN ONLY CHECK WHAT THE HARNESS EMITS, AND THAT IS THE MANIFEST'S `host`.** The
per-game records carry **no host field at all** (verified against a real round-1 record at freeze:
seed / a_seat / diff / scores / timings and nothing else). So the gate proves the cell's **sealing
pass** — the one that wrote the pooled summary the adjudicator reads — ran on the assigned box. It
cannot prove every individual record did.

⛔ **WHICH IS WHY THE REAL PROTECTION IS STRUCTURAL RATHER THAN THIS GATE:** the two boxes hold
**disjoint cells** and therefore **disjoint `--out-subdir`s**, so `--shared-claim` has nothing to
race over between them. Two boxes pointed at one cell would race on claims; two boxes pointed at
different cells cannot. `G-HOST` catches the launcher-level version of the mistake — a box handed
the wrong `--host` — and the launcher refuses it a second time up front.

#### (ii) ⭐ EVERY PRE-REGISTERED CONTRAST IS WITHIN ONE BOX — the load-bearing property

**Shapes are assigned WHOLE.** So:

- §4.5's low-vs-high contrast is **within-box** for all three shapes;
- §4.7's noise-signature check across `C_LOW`/`C_MID`/`C_HIGH` is **within-box**;
- and each cell's own margin was **always** a within-cell, within-box, deck-paired statistic — both
  sides of a cell run in the same process, on the same box, at the same budget.

⛔ **THIS IS NOT A CONVENIENCE.** Cross-box float identity is something this program has been
bitten by: the Xeon was **re-retired 2026-08-02** because AVX-512 makes the G0 determinism check
FAIL by default. Shipping one wheel file makes cross-box comparison *plausible* (same `.so`, same
rev, deterministic harness); assigning shapes whole means the round **never has to rely on it**.
`screen_lib.sanity_check()` asserts no shape is split, and the launcher's table pre-flight asserts
it again.

#### (iii) THE ASSIGNMENT IS ALSO THE FASTEST ONE — the arithmetic, and the four rejected splits

At the assumed 1.4× laptop ratio the laptop's throughput is `22/(22×1.4) ≈ 71%` of local's, so it
should take ~42% of the work. Every shape-clean split, computed at freeze:

| laptop takes | local wall | laptop wall | **round wall (max)** |
|---|---|---|---|
| **C (3 cells)** | 3.38 h | 4.12 h | ⭐ **4.12 h** |
| A (2 cells) | 4.58 h | 2.43 h | 4.58 h |
| B (2 cells) | 4.68 h | 2.29 h | 4.68 h |
| A+B (4 cells) | 2.95 h | 4.72 h | 4.72 h |
| *(single box, local only)* | 6.33 h | — | 6.33 h |

**The split that balances wall-clock and the split that keeps shapes whole are the same split.** The
C cells are the round's expensive shape *and* the laptop is the slower box, so handing the laptop
the C cells is what balances the two walls.

⚠️ **This is the one place this design departs from the suggestion it was given**, which offered
local←A/B + laptop←C *or* an adjustment "if your cost table says otherwise". The cost table agrees
with the suggestion; it is recorded here with the alternatives so the choice is auditable rather
than asserted.

⚠️ **AND IT PUTS THE NEW MACHINERY ON THE LESS-PROVEN BOX** — the C cells are simultaneously round
2's new plumbing and the laptop's first sight of it. That is why §9 runs **one smoke per box**, and
why the **laptop's** smoke (`C_MID`'s exact config) is the load-bearing one.

#### (iv) SYNC, PROVENANCE AND ADJUDICATION

- ⭐ **THE OUT-ROOT IS ON THE SHARE**, with the per-box mount spelling (`/mnt/c/carc-shared` local,
  `/mnt/carc-shared` inside the laptop). The **local** box adjudicates over **both** boxes'
  archives and can only see the laptop's cells if they land there. The launcher resolves the
  spelling from `--host` and the table pre-flight cross-checks it against `screen_lib.BOXES`; a
  launcher with the wrong spelling would write outside the share and the archive would be invisible.
- ⭐ **THE REPO IS BUNDLE-SYNCED, NOT PULLED.** The laptop cannot reach GitHub
  (`reference_offline_git_bundle_sync`): bundle the launch rev onto the share, `git fetch <bundle>`,
  `git reset --hard`. ⛔ **Without it the laptop runs stale code and the round is mixed-rev across
  machines** — the `track_d2_prep` defect with an extra machine. The adjudicator checks that all
  seven cells report **one `code_rev`**, which is exactly the property the bundle sync guarantees.
- ⭐ **PER-BOX LAUNCH ARTIFACTS, PUBLISHED TO THE SHARE.** Each box writes its own
  `PINNED_SRC_REV`, `SRC_CLEAN.jsonl`, `BLIND_PROOF.json` and `WHEEL_PROBE.json` into **its own**
  repo checkout — which the local adjudicator cannot see — so each launcher also copies them to
  `<out-root>/_provenance/<role>/`. `G-REV`, `G-BLIND` and `G-WHEEL` then evaluate **every cell
  against its own box's artifacts**, and `SRC_CLEAN`'s per-cell after-boundaries are checked only
  for the cells that box actually ran. The adjudicator falls back to its own directory when no
  per-box copy exists, so a single-box run, the smoke and `--selftest` are unchanged.
- ⚠️ **WSL CLOCK DRIFT** (`reference_wsl_clock_drift_after_sleep`, the F7c class): a WSL2 clock can
  jump hours after a host sleep, and a fast-clocked box silently **steals stale `--shared-claim`
  claims** — no error, just missing games. ⭐ **It cannot cross-contaminate the two boxes here**, and
  that is structural: disjoint cells mean disjoint out-subdirs mean no shared claims to steal. It
  can still disturb a box's **own** resume loop, so `--claim-stale-secs` and the orphan sweep stay,
  and the launcher logs a share-vs-local mtime skew as an advisory.
- **Launch is per box, concurrent, detached** — the laptop via the piped-script `ssh 'bash -s'`
  pattern with `cd` on line 1 (`feedback_remote_ssh_pipe_script_mandatory`) and `setsid`. ⚠️ A
  detached ssh launch returns **rc=124 from `timeout` after launching**: treat 124 as LAUNCHED and
  **never retry** (`feedback_wsl_ssh_launch_pkill_traps` — a retry stacks pools).
- **Each box runs its own census and its own RAM floors.** The tenancy class (§6.3) is unchanged
  and applies per box.

### 6.4 — sequencing, and the per-cell interlock

**Order, PER BOX** (the two run concurrently — §6.5):

```
local :  A_LOW -> A_HIGH -> B_LOW -> B_HIGH
laptop:  C_LOW -> C_MID  -> C_HIGH
```

Within each box the cells run in ladder order. ⭐ **Each box's §9 smoke has already exercised that
box's own most-plumbing config end to end before any of its decks are spent** — and the laptop's
smoke runs `C_MID`'s exact configuration, which is the round's new machinery and the laptop's first
sight of it.

⭐ **THE PER-CELL INTERLOCK — round 2's successor to round 1's IDENT interlock.** Round 1 refused to
start `A/B/D` until `IDENT` had run **and passed its bar**, so a wiring defect cost 8 core-h instead
of 62. Round 2 has no IDENT cell but has **seven cells and ~139 core-h**, so it needs the same shape
of protection and gets a **stricter** one: **after EVERY cell seals, the launcher re-reads that
cell's own EMITTED manifest and refuses to start the next cell unless it passes.** A wiring defect
therefore costs **one cell (~20–30 core-h), not seven**, wherever in the round it appears.

⭐ **AND THE TWO-BOX SPLIT MAKES THE PER-CELL FORM NECESSARY RATHER THAN MERELY BETTER.** With the
A/B cells local and the C cells on the laptop, there is no single sequence in which a "first cell"
could gate the rest: **each box needs its own interlock**, because each box has its own wheel
install, its own checkout and — for the laptop — its own first-ever execution of the shape-B env
regime. Checking after every cell gives each box that protection without either box waiting on the
other.

The pre-check's conjuncts: `screen_lib.leaf_gate()` (both pinned hashes + the curve + the two sides
being different leaves), both sides' invasion blocks equal to the cell's frozen expectations,
`n_failed == 0`, `G-WHEEL-SAME`, and a statistic existing at all.

⚠️ **THE ARITHMETIC IS `screen_lib`'s, NOT THE SHELL'S** — it calls the **same** `leaf_gate()` the
adjudicator's `G-LEAF` calls, so the live check and the post-hoc check cannot drift apart. That is
the `track_d2r2_prep` defect this bar library exists against.

⛔ **AND THE PRE-CHECK IS STATISTICS-BLIND.** It reads no bar and no branch. **It cannot stop the
round for a disappointing result, only for a broken one.** (Round 1's `IDENT` pre-check *did* read
a statistic — the `|z| ≤ 2` identity bar — because an identity cell's whole content is that
statistic. Round 2's cells are arms, and a launcher that could halt an arm on its number would be
peeking.)

⚠️ **AND IT READS `manifest.json` FOR CONFIG, `summary.json` FOR STATISTICS.** Round 1's deviation
**IS-D1** was exactly this reader taking the config block off `summary.json`, getting `{}`, and
fail-closed voiding a **healthy** cell — while a vacuous `{} == {}` made a second conjunct pass and
hid the cause. The fixed address is carried here, and the vacuity is now structurally impossible:
`leaf_gate()` requires the hashes to be present **strings**, not merely equal.

---

## 7. THE WHEEL — a FATAL precondition, and what round 2 wants from it

⛔ **ROUND 2 DOES NOT WANT A REBUILD. IT WANTS ROUND 1's WHEEL.**

This is the inverse of round 1's situation. Round 1 froze against a **stale** venv wheel
(`TypeError: LeafConfigRs.__new__() got an unexpected keyword argument 'invasion_beta'`) and its
§7 told the orchestrator to rebuild. That rebuild happened; the wheel that resulted
(`carc_rs_binary_sha a9ac686bca1417f9`) played round 1's 2800 games **and passed its IDENT cell**.

**Round 2 inherits that IDENT (§3.1), so round 2 needs that wheel.** A rebuild — however
well-intentioned, even from an identical tree — produces a different `.so` and a different sha,
fails `G-WHEEL-SAME`, and **re-owes an IDENT cell**.

⭐ **AND THAT IS WHY THE TWO-BOX ROUND SHIPS A WHEEL FILE INSTEAD OF BUILDING ONE.** The executor
`scp`s
`/home/doctor/carc_wheels/carc_rs-0.1.0-cp312-abi3-manylinux_2_34_x86_64.whl` to the laptop and
`pip install --force-reinstall --no-deps` es it into the laptop's venv. Same file ⇒ same bytes ⇒
**same `carc_rs_binary_sha` on both boxes** ⇒ `G-WHEEL-SAME` passes on every cell regardless of
host. ⛔ **A laptop-local `maturin build` is exactly the thing that breaks this**, and the gate
refuses it — correctly. The launcher's pre-flight asserts the sha **on each box**, so a wrong wheel
is caught before a game rather than at adjudication.

**The launcher's pre-flight therefore does four things, in a CHILD process, before any game, ON
EACH BOX:**

1. `G-WHEEL-SAME` — assert `carc_rs_binary_sha == a9ac686bca1417f9`, through the same
   `screen_lib.wheel_is_r1s()` the adjudicator uses;
2. assert `hasattr(carc_rs.MirrorState, "invasion_terms")`;
3. for **every** cell, build the resolved candidate cfg through the harness's own
   `_load_cand_leaf_cfg`, forward it with `leaf_config_rs` (**the actual nonzero forward, not a
   `hasattr` proxy**), and run `screen_lib.leaf_gate()` against the resolved hashes;
4. ⭐ **forward the OPPONENT leaf too** — `_curve125_leaf_cfg()`, which is literally what the
   harness hands the head-to-head opponent — and record `opp_side_forward_ok`.

⚠️ **AND IT RUNS TWICE, ONCE PER ENV REGIME** (§2.5 item 4). `DEFAULT_CONFIG` latches at import, so
no single process can observe both opponents. Each regime writes its half of `WHEEL_PROBE.json`;
the launcher merges them and re-checks the merged artifact through `screen_lib.wheel_probe_ok()`,
which additionally requires every cell to be present — a half-probed round cannot slip through.

**Why a stale wheel is still the worst failure mode.** `leaf_config_rs` forwards the knobs
**conditionally**, so a build predating the family serves every default-off config **unchanged and
silently** and raises only on a nonzero weight. Round 2 has no weight-0 cell to trip on it, which
makes the live nonzero forward and the binary-sha pin the only two things that can catch it.

---

## 8. WHAT THIS CANNOT SHOW

Stated before launch so no branch can be narrated past them:

1. **It is not a production result.** 2752 is the screening budget; production is 11008 (§2.4).
2. ⭐ **IT CANNOT CONFIRM ROUND 1's MID.** A flat `+0.76` pts/deck effect is caught ~24% of the
   time (§4.2). **The round is powered to detect SCALING.** A `FAMILY-PARKS` bounds the growth of
   the effect with weight; it does not refute round 1's `BRACKET`.
3. ⛔ **A AND B ARE NOT BRACKETED WITHIN IT** (§3.4) — two points, no interior, and the interior
   point is on another band. Every A/B reading is at a ladder endpoint.
4. ⛔ **NO C READING SAYS ANYTHING ABOUT STRENGTH.** C's opponent is a shape-B invader, not the
   champion of record. A positive C margin means the defence pays against the exploit — nothing
   about play against the champion, nothing about an out-of-lineage opponent, and **nothing that
   enters the four-link adoption chain** (`READ_RULE.md` §4.6).
5. **It cannot rank the shapes against each other** — disjoint deck ranges (§5.1). Each cell is
   adjudicated against zero, never against a sibling.
6. ⛔ **It cannot read a three-point ladder for A or B**, because two of the three points are on
   different bands and CL-068 prices that at 1.8–2.2× over-dispersion (§5.2).
7. **It says nothing about shape D** (§3.3), and nothing about the A/D scope contrast beyond what
   round 1 already recorded.
8. **It licenses no `governance/PRODUCTION.yaml` change and no champion-of-record discussion.** An
   A/B `PROMOTE` is **link 1 of a four-link chain**: screen → production H2H → **external
   validation vs Carcasum** → the E4 stream as final holdout. ⛔ **The external link is not
   optional.** An invasion term is by construction a term that exploits a *blindness of the
   incumbent champion*, so a margin measured *against that champion* is consistent with exploiting
   the opponent rather than improving the agent, and nothing inside the lineage can distinguish the
   two (`feedback_anchor_before_scaling`). A firing A or B additionally owes a caps re-sweep (§3.5).
9. **It does not measure whether the E4 opponent's invasions are actually exploitable** — that is
   the Stage A/B census's question, already answered, and the reason this family exists.
10. ⭐ **IT CANNOT COMPARE A LOCAL CELL TO A LAPTOP CELL** (§6.5). No pre-registered statistic
    does: shapes are assigned whole, so every §4.5 contrast and the §4.7 noise check is within-box,
    and §1.1 already forbade cross-cell contrasts as branch inputs. ⛔ **A readout that puts a
    local A cell beside a laptop C cell and reads the difference is doing something this design
    deliberately never validated** — the same wheel and the same rev make it plausible, but the
    round does not rest on it and neither may any branch.

---

## 9. THE SMOKE LEG (pre-blind, mandatory) — ⭐ ONE PER BOX

n=16 games (8 decks × 2 seatings) per box, each on its **own separate throwaway range** — never the
cell band:

| box | config | range |
|---|---|---|
| **laptop** ⭐ | `C_MID` | `152999999000..152999999007` |
| local | `B_LOW` | `152999999100..152999999107` |

⭐ **ONE PER BOX, AND THAT IS FORCED BY THE TWO-BOX SPLIT.** A single-box round could smoke once. A
two-box round cannot: each box has its own wheel install, its own repo checkout, its own share mount
spelling and its own `W`, and the leg's whole purpose is to prove the plumbing **on the machine that
will spend the decks**. Each box therefore smokes **its own most-plumbing cell config**.

⭐ **THE LAPTOP'S IS THE LOAD-BEARING ONE.** Round 1 smoked `B_MID` because B was its cell with the
most plumbing to break. Round 2's most-plumbing config is a C cell by a wide margin — the **shape-B
env regime**, an **opponent leaf that is not the champion**, the **explicit-zero neutralisation** on
the candidate side, a **three-key leaf diff**, **two-sided hash pins** — every one of which is
machinery that has never emitted a manifest **on any box**, and the laptop is the box that will run
it. `C_MID` rather than `C_LOW`/`C_HIGH` because the interior rung is the one §4.7's
noise-signature rule will read.

**The local leg is the cheap one, and deliberately so:** the local box's cells are the A/B
plain-regime configs round 1 already proved *on this exact box with this exact wheel*, so its smoke
is a re-confirmation of the launcher and the wheel install rather than a first sight. `B_LOW`
rather than an A cell because B is the only A/B config with the cap-forwarding biconditional to
break.

**What the smoke leg verifies (all structural):**

(a) `n_failed == 0` and the harness runs clean at this exact invocation — including the two
expected non-fatal warnings §2.4 names (the budget deviation, and the **opponent-side hash drift**
that is the §2.5 mechanism working);

(b) every wheel / leaf / rules / cap-forwarding pre-flight fires against **real records** rather
than against the harness's documented behaviour — on **both** sides;

(c) ⭐ **it produces the REAL MANIFEST the pair's C-cell gates are validated against.** The leg
**ends by running [`analyze_screen.py`](analyze_screen.py) `--smoke-mode` against the smoke
archive** and requires it to fail **only** on the pinned allowed set. This is the standing rule the
`h2h_22016_prep` post-mortem proposed, `track_d2r4_prep` first adopted and round 1 carried;

(d) ⭐ **it produces the FIRST OBSERVATION OF BOTH UNMEASURED COST INPUTS** — shape C's per-move
cost (the laptop leg) and the laptop's per-game ratio (also the laptop leg). The launcher prints
both against their assumptions. **Report the discrepancies; do not re-freeze on either** — this pair
is sims-denominated and no gate reads a clock.

**The pinned allowed set** (`READ_RULE.md` §3.5 — a failure OUTSIDE it is a launch blocker):
`G-BAND`, `G-DECKS`, `G-N`, `G-SAT`, `G-HOST`, `RECON/n_paired`. Everything else — including
**`G-WHEEL-SAME`**, which is **NOT** exempt and which round 1 did not have — **must PASS on a
16-game archive.**

⚠️ **`G-HOST` IS ALLOWED ON A SMOKE, AND ONLY FOR A MECHANICAL REASON:** `--smoke-mode` is handed a
*directory*, and each box smokes a different cell's config on its own range, so the smoke cell's
frozen `box` is not necessarily the box that ran it. ⛔ **The property is not left unchecked** — the
launcher refuses to run any cell not in its `--host`'s set **before a game starts**, and `G-HOST` is
fully enforced on every real cell.

Net of both changes the set is still **strictly smaller** than round 1's, which also excused
`G-IDENT` — a gate round 2 does not carry at all.

**What it explicitly does NOT do:** produce, confirm or influence any statistic. There is no knob
for any leg to re-pick.

### 9.1 — the selftest fixture: round 1's own emitted archive

`analyze_screen.py --selftest` **refuses a synthesized-only fixture** and runs against a manifest
the harness EMITTED. ⛔ **Round 2 runs no games at all**, so it cannot mint one the way round 1 did
(round 1 ran a 2-deck off-band dev probe, disclosed in its §9.1). Instead it seeds from a real
emitted archive **that already exists**: round 1's own §9 smoke archive — 16 real games,
`invasion_screen_20260826/smoke_b_mid/`, throwaway range `151999999000..`, discarded and never
pooled — copied verbatim into [`selftest_fixture/`](selftest_fixture/) and described by
`screen_lib.FIXTURE_SPEC`, which is declared **NOT a round-2 cell**.

⚠️ **What it can and cannot prove.** It is a B-shaped, plain-regime, champion-opponent archive, so
it answers §3.1 question 2 ("can a healthy run pass?") on real output for every shape-invariant
gate — **including `G-WHEEL-SAME`, which passes on it precisely because the fixture IS round 1's
archive**, and which is how §3.1a's defect was found. It does **not** exercise the C cells'
shape-B opponent, the two-sided pins in their interesting direction, or the three-key diff. Those
are covered by `tests/test_invasion_screen_r2_instrument.py` (synthesized manifests are legitimate
in unit tests; it is the **selftest** that refuses synthesis) and, definitively, by the §9 smoke.

---

## 10. CLOSE-OUT (on adjudication, not before)

The six-touch checklist, verbatim from `CLAUDE.md`: (1) [`../../experiments/results.csv`](../../experiments/results.csv)
row **per cell** (seven rows, or `VOID` rows on the `U-UNREADABLE` precedent) · (2)
[`../../DECISIONS.md`](../../DECISIONS.md) index line · (3) status stamp on this `DESIGN.md`,
on [`READ_RULE.md`](READ_RULE.md), **and on [`../invasion_term_build/SHAPES.md`](../invasion_term_build/SHAPES.md)**
· (4) governance row flip ([`../../governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv)
`decision_influenced` + band retirement; **plus a `CLAIM_REGISTRY` row**) · (5)
[`../../STATUS.md`](../../STATUS.md) top block · (6) the roadmap line in
[`../../docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md). Then
`python3 scripts/doc_lint.py`. Commit; do not push without asking.

**Also owed, and specific to this family:** (7) a [`../../docs/LEVER_INDEX.md`](../../docs/LEVER_INDEX.md)
row update for "contested-feature / invasion-risk term" carrying the outcome — including a
`FAMILY-PARKS` outcome, which is exactly the knowledge the index exists to preserve; and (8) a
`governance/CHECKPOINT_LINEAGE.csv`-style lineage note for each nonzero-weight leaf hash produced
(a nonzero weight IS a new leaf), per [`SHAPES.md`](../invasion_term_build/SHAPES.md) §8 — **six new
hashes this round**, plus the shape-B agent's, which already has one from round 1.

**Owed regardless of branch, including `U-UNREADABLE`:** §6.2's measured ms/move ratios, and in
particular ⭐ **the first measured per-move cost of shape C** and ⭐ **the first measured
laptop-vs-local per-game ratio for a rust-both-sides cell** — the two numbers this round produces
whether or not anything fires, and the two any future C work or any future two-box round needs
before it can price itself. Both were carried into this round as **assumptions with stated
envelopes** (§6.2's `*` and `†`); the close-out replaces them with measurements.

**And owed to round 3, whatever fires:** the §4.5 contrasts and their SEs. A round 3 that has to
re-derive how much power an unmatched contrast has is a round 3 that will size itself wrong.
