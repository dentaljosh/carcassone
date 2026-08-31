# OM-D2 — LOCALISED: the rust chain-value port is CORRECT; the banked python census is not

**Status: LOCALISED 2026-08-30. Root cause identified, mechanism proven on a single
position, direction measured. NO production-code change made — the arbiter is deployed
on the phone and any change is the owner's call.**

⛔ **Instrument-only forensics.** Nothing here enters `governance/PRODUCTION.yaml`, a
claim row, or an adoption chain. It re-reads banked artifacts and replays 9 banked
games; it launched no campaign and changed no shipped code.

---

## 0. The two-sentence answer

The OM-M1 build's 0.45 % `G-FIRE` join residual is **not** a bug in
`carc_core::tiearb::chain_values`: on all 10 banked witnesses the rust port is
**bit-identical, action for action, to the python definition of record run with an
HONEST legal mask** — the divergence is entirely on the census side, where
`meeple_tie_census._process_game` builds its `Game` with
`enable_legal_moves_cache=True` and the memo's key (`string_representation`) is
**non-injective for 180°-rotationally-symmetric tiles**, so the *second* rotation of a
tied tile pair is served the *first* rotation's meeple mask and its chain value is
computed off the wrong (and partly illegal) continuation set.

⇒ **The wrong side is the PYTHON CENSUS AS RUN — not the rust port, and not the python
code itself** (`chain_census.chain_values` is correct; the `Game` it was handed was
memoised). The deployed arbiter has therefore **not** been firing on a wider set than
its spec: it fires on the *correct* exact-tie set, and the **banked census
under-counts** ties.

---

## 1. What was measured

Three implementations of the same predicate, on the same states, for each of the 10
banked `(deck_seed, ply)` witnesses from the OM-M1 `G-FIRE` join
(`scripts/omm1/build_fired_plies.py::_g_fire_join`, `FIRE_CENSUS.json ::
G_FIRE_join.disagreement_examples`, branch `worktree-agent-a6de39b2de1b23a94`):

| label | what it is |
|---|---|
| `rust` | `carc_rs.MirrorState.tiearb_probe` → `carc_core::tiearb::chain_values` — the **SHIPPED** trigger, read from the installed wheel (`.venv/…/carc_rs`), i.e. the code the desktop and phone arbiters run. |
| `py_cache` | `scripts/tiletie/chain_census.chain_values` walked exactly as `meeple_tie_census._process_game` walked it — `Game(enable_legal_moves_cache=True)`, chain values computed at every earlier tile ply so the memo is warmed identically. **This is the definition of record AS THE BANK WAS MEASURED.** |
| `py_nocache` | the same python code, memo OFF (honest mask). |

Leaf `a36d2e15a3b3d71d`, profile `walled`, `eps = 0.0`, `J = 4`, salt
`tiearb2-deploy-v1` — the census's own resolved config
(`../tiearb_widening_20260817/census/manifest.json`).

Artifacts (this directory): [`WITNESS_DIFFS.json`](WITNESS_DIFFS.json) (per-action
three-way diff, all 10 witnesses), [`COLLISION_WITNESS.json`](COLLISION_WITNESS.json)
(the key collision, single position), [`TILE_WITNESS.json`](TILE_WITNESS.json) (the
colliding tile), [`DEFECT_RATE.json`](DEFECT_RATE.json) (both-direction census defect
rate on the 9 witness games). Probes: [`probe_witnesses.py`](probe_witnesses.py),
[`probe_collision.py`](probe_collision.py), [`probe_tile.py`](probe_tile.py),
[`probe_rate.py`](probe_rate.py) (+ their `run_*.sh` launchers).

---

## 2. The localisation — the first divergent quantity

**Unanimous across all 10 witnesses, with no exceptions:**

* `rust == py_nocache` — **every** action's chain value bit-identical (`n_cand` 18–38),
  and the action SETS are equal in all three implementations.
* `rust != py_cache` at **exactly ONE action per witness**, and that action is always
  the tie partner of the argmax, always at index **`argmax + 2`** — the same tile
  position at the **other 180° rotation**.
* `py_cache` reproduces the **banked census row exactly** (`gap`, `top1`, `tie_exact`,
  `tie_size_exact` all equal) on all 10 — so the memo is the whole difference between
  the bank and the truth, deterministically.

| deck_seed | ply | tie actions (honest) | rust value | `py_cache` value | meeple chosen: rust / `py_cache` |
|---|---:|---|---:|---:|---|
| 28000000011 | 24 | 949, **951** | −9.75 | −11.5 | 2508 / 2510 |
| 28000000012 | 112 | 741, **743** | 5.75 | 4.1 | 2509 / 2510 |
| 28000000015 | 72 | 1553, **1555** | 15.4 | 14.4 | 2508 / 2510 |
| 28000000017 | 30 | 1061, **1063** | −2.45 | −2.95 | 2508 / 2510 |
| 28000000022 | 66 | 1636, **1638** | −11.55 | −12.3 | 2509 / 2510 |
| 28000000031 | 110 | 1033, **1035** | −15.85 | −16.85 | 2508 / 2510 |
| 28000000031 | 114 | 1033, **1035** | −14.85 | −15.85 | 2508 / 2510 |
| 28000000050 | 24 | 1356, **1358** | 7.6 | 6.5 | 2507 / 2510 |
| 28000000052 | 48 | 848, **850** | 8.6 | 7.0 | 2509 / 2510 |
| 28000000059 | 138 | 964, **966** | 33.7 | 32.7 | 2508 / 2510 |

**The first divergent quantity is not a leaf value at all — it is
`Game.get_valid_moves(s1)` for the second tile action**, i.e. the MEEPLE continuation's
legal set inside `chain_values`. Under the memo the census is served the *other
rotation's* mask, the true best farmer placement is absent from it, and the argmax
falls through to `2510` (**`PassAction`** — decoded in `COLLISION_WITNESS.json`) in
**all ten** cases. The quarter-to-full-point "gaps" are therefore the value of the
farmer the census was never offered.

### The smoking gun (witness 1, `(28000000011, 24)`, [`COLLISION_WITNESS.json`](COLLISION_WITNESS.json))

```
string_representation(s1 after 949) == string_representation(s1 after 951)   ->  TRUE
honest legal meeples after 949:  [2502, 2504, 2507, 2509, 2510]
honest legal meeples after 951:  [2502, 2504, 2506, 2508, 2510]   <- masks DIFFER
2510 = PassAction
```

Two distinct boards, **one memo key**; the farmer-slot actions rotate (2507/2509 ↔
2506/2508) while the outer edges do not. The tile
([`TILE_WITNESS.json`](TILE_WITNESS.json)) is **`straight_road`** — its `farms` read
`[top_right, top_left], [bottom_right, bottom_left]` at one rotation and
`[bottom_left, bottom_right], [top_left, top_right]` at the other. That is exactly the
non-injectivity documented in
[`src/carcassonne_ai/game_wrapper.py`](../../src/carcassonne_ai/game_wrapper.py) L106-140
(`_FIX_LEGAL_CACHE_KEY`), whose banked witness was `city_left_right`; **`straight_road`
is a second witness tile for that parked bug.**

⚠️ Worse than a wrong argmax: because the served mask is a *different board's*, the
census applied meeple actions that are **not legal on the state it applied them to** and
took leaf values off those afterstates. The bank's value for that one action is not a
worse-but-valid alternative — it is garbage.

---

## 3. Classification

**A stale/contaminated MEASUREMENT, not a port bug and not a definitional ambiguity.**

* **Spec status.** `rust/carc/carc-core/src/tiearb.rs` L15-38 names
  `scripts/tiletie/chain_census.py:168,216` as the definition of record, and no
  DECISIONS entry supersedes it (`grep FIX_LEGAL_CACHE_KEY DECISIONS.md` → one line,
  DECISIONS L7888, which *parks* the key; `docs/LEVER_INDEX.md` carries no
  chain-values adoption ruling). The python function **is** the spec — and the rust
  port satisfies it exactly when the spec is evaluated on the mask the rules actually
  give. It is the census's `Game(enable_legal_moves_cache=True)` that departs.
* **Not one of the pre-registered mismatches.** `../tiearb2_stage2_20260817/DESIGN.md`
  §2.1 pre-registers exactly two runtime-vs-corpus mismatches (replayed-board context;
  fresh-search `champ_picks`). This is a **third**, previously unregistered one — and
  unlike those two it is not a context difference, it is a defect in the corpus side.
* **Already-known root cause, new surface.** The non-injective key is the tiearb2
  Stage-2 by-catch of 2026-08-17 (`docs/PROGRAM_ROADMAP_2026-07-07.md` L196, commit
  `05ed019c`, disclosed at 57/15,360 = **0.371 %** of Stage-1b banked playout values).
  OM-D2 is the same defect reaching a **different artifact**: the Stage-1b disclosure
  covers `tier1` playout VALUES; this is the TILE-TIE CENSUS's **trigger predicate**,
  which nothing had audited.
* **The `ULP` class of the OM-M1 write-up dissolves.** `(28000000031, 110)` and
  `(…, 114)` were classified ULP on a banked `gap` of `1.78e-15`; measured here they
  have the same one-action, one-mask cause as the other eight (`py_cache` value 1.00
  point below rust). **All 10 witnesses are ONE class.** The `1.78e-15` is an artifact
  of `tie_report`'s `gap` being the distance to the next *distinct* value, not to the
  runner-up.

---

## 4. Blast radius

### 4.1 Does the ARBITER's fire decision change? — **No. The arbiter is right.**

The deployed trigger is `carc_core::tiearb::chain_values` + `detect_tie` on the rust
`Game`'s own honest `legal_actions()`; the memo-reproducing
[`crate::tier1::LegalMaskCache`] is a *playout* facility and is not on this path
(`tiearb.rs` L284-329 clones the state and calls `legal_actions()` directly). The
python arbiter knobs in `heuristic_prior_mcts.py` L247-275 are **config plumbing only**
— the arbiter itself is rust (`rust_agent.py` L310). Measured here: rust == honest
python on 10/10 witnesses, every action.

⇒ **`DEVIATIONS.md::OM-D2`'s "owed regardless of this gate" worry — *"the deployed
arbiter has been arbitrating a slightly wider set than its spec"* — reads the arrow
backwards.** The arbiter fires on the correct exact-tie set. The **census** recorded a
narrower one.

### 4.2 What IS contaminated: census-derived STATISTICS

Measured on the 9 witness games (biased sample — every game was selected *because* it
carries a witness — so read it as an upper-ish bound, not the population rate;
[`DEFECT_RATE.json`](DEFECT_RATE.json)):

```
639 tile rows · 24 rows moved (3.76%) · tie_exact moved on 16
false_untied 16   (memo says UNTIED, honest says TIED)
false_tied    0   (no spurious ties)
top1_moved    0   (the leaf's best VALUE never moved)
```

**The defect is one-directional in this sample: the memo can only DELETE a tie
partner, never invent one, and it never moved `top1`.** So every census tie statistic
is a **floor**:

* `../tiearb_widening_20260817/census/READOUT.md` L100/L109/L239 — 20,322/31,827 =
  63.85 % exact-tied, **45.26 exact-tied tile plies/game** — are under-counts.
* Anything derived from them: `omm1_lib.BANKED_TIED_TILE_PLIES_PER_GAME`,
  `FIRED_PLIES_PER_GAME_WALLED`, the tile gap CDF, and `POSITIONS_PLAN.json::mean_arms`
  (`= 3.0022`, `omm1_lib.MEAN_ARMS`) if that plan's positions were filtered on the
  census's `tie_exact`.
* The MEEPLE census in the same file builds the same memoised `Game`, so its
  10,896/74,894 = 14.55 % is structurally exposed too — **unmeasured here**.

### 4.3 Adjudicated verdicts — **none flips**

* **tiearb2 Stage-2 Phase B** (`ARB` +3.0700 pts/game z +4.445, `RND` −4.4287,
  `D` +7.4988): game cells, trigger evaluated at RUNTIME by the rust arbiter on both
  arms. The fire SET is the correct one and is identical across arms; nothing about the
  contrast moves. The offline 22.96/45.26 priors are explicitly *priors, not
  predictions* (DESIGN §2.1) and `phi` was measured in-cell.
* **b64 promotion / T-TRANSFER / phasegate**: same story — the trigger is the rust
  runtime path, and the memo lives only in the python census. **Not contaminated.**
* **Stage-1b's banked playout corpus** already carries its own disclosed 57/15,360
  defect (`BITEXACT_DIVERGENCE.json`); OM-D2 adds no new exposure there.
* **OM-M1 itself**: `G-FIRE`(a)'s 0.99550 is now *explained*, and its direction is the
  benign one — the replay fires where the leaf genuinely ties and the census's row is
  wrong. §5's bar does not consume the fire rate (`OM-D1`), so no OM-M1 number moves.
  The `G-FIRE` join threshold should be **restated** (see §5) rather than tightened to
  1.0 against a known-defective bank.

### 4.4 Not audited here (honest gaps)

* The population-wide rate on all 449 games, and the meeple-census direction — both
  need the re-run in §5.
* Whether any *other* consumer of `string_representation` (MCTS transposition key, C2
  aliasing, afterstate maps) is exposed — that is the parked roadmap row's own
  blast-radius question, unchanged by this work.

---

## 5. Proposed fix + its gate (OWNER DECISION — nothing applied)

**Do NOT touch the arbiter.** It is the correct side. Two candidate actions, both on
the measurement side only:

**F1 (recommended, cheap, no semantic risk) — regenerate the tile-tie census with an
honest mask.** One argument in `scripts/tiletie/meeple_tie_census.py:511`
(`enable_legal_moves_cache=True` → `False`), or equivalently run it under
`CARCASSONNE_FIX_LEGAL_CACHE_KEY=1` to keep the memo's speed with an injective key.
Cost: the banked census did 1,299 games in **52.2 s at W=30**; the honest-mask variant
costs ~2× the tile-ply leaf work at most ⇒ **≈ 2 minutes on one box, one process
group, no cluster booking.** Rewrite the READOUT's three headline numbers and stamp the
old ones as superseded.

**F2 (optional, defensive) — make the instrument state its mask.** `chain_census.py`
gets a module-level assertion that the `Game` it is handed has the memo OFF (or the
fixed key), so no future census can silently inherit this. Instrument-only change; no
production path imports it.

**Gate for F1 (pre-register before running, house style):**

1. **`G-HONEST`** — the regenerated census must agree with a fresh
   `tiearb_probe` replay on **1.0000** of joined `(deck_seed, ply)` fired keys
   (currently 0.99550). Anything below 1.0 means a second, unlocalised cause exists.
2. **`G-DIRECTION`** — every moved row must move `tie_exact` `false → true`
   (`false_tied == 0` on the full 449, as it is 0/639 here). A single `false_tied` row
   falsifies the one-directional reading of §4.2 and re-opens the argmax question.
3. **`G-TOP1`** — `top1` unchanged on ≥ 99.9 % of rows (0/639 moved here). `top1`
   moving would mean the memo can change the champion's own pick, which is a strictly
   larger finding than this one.
4. **`G-RATE`** — report the population rate with its Wilson CI, and re-derive
   45.26 / 63.85 % / the gap CDF. **No downstream constant may be quietly edited**:
   `omm1_lib`'s two banked rates are frozen prereg inputs and must be superseded
   explicitly, not patched.

**Cost of the whole fix: ~2 minutes of one-box compute plus the doc touches.** The
expensive thing here is not the fix; it is that until F1 runs, every tie-rate number in
the widening campaign is a floor of unknown tightness.

**Explicitly NOT proposed:** flipping `CARCASSONNE_FIX_LEGAL_CACHE_KEY` to default-on.
That is the parked `05ed019c` decision with its own blast radius (the same key is the
MCTS transposition key and the reproduce-the-bank contract), and OM-D2 gives it no new
licence — only a second witness tile and a second exposed artifact.

---

## 6. Reproduction

```bash
bash measurement/omd2_chain_values_20260830/run_probe.sh      # 10 witnesses, ~20 s
bash measurement/omd2_chain_values_20260830/run_collision.sh  # the key collision, ~5 s
bash measurement/omd2_chain_values_20260830/run_rate.sh       # 9 games both ways, ~90 s
```

All three are read-only, single-process, `nice -19`, and take the leaf of record from
`champion_factory.production_leaf_cfg()` with the `a36d2e15a3b3d71d` assertion armed.
The witness list is the OM-M1 build's own
`FIRE_CENSUS.json :: G_FIRE_join.disagreement_examples`.
