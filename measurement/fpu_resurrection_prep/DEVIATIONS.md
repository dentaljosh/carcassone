# FPU RESURRECTION — DEVIATIONS FROM THE FUNDING BRIEF

> **STATUS: FROZEN** (2026-08-30), with the pair. Every item here is a place where the **build
> departs from the brief as written**, why, and what was done instead. ⛔ Recorded before game 1.

---

## D1 ⛔⛔ "CELL_CPUCT10 needs NO new plumbing" — **FALSE**

**The brief said:** *"CELL_CPUCT10 (cand c_puct 1.0 — needs NO new plumbing; verify the existing flag
reaches the manifest)."*

**What is actually true.** `--c-puct` is a **SHARED** flag, not a candidate-side one. Traced:

```
main()          : champ_cfg_dict = {"c_puct": args.c_puct, ...}          (:4312)
_play_one_inner : cfg  = _cfg_from_dict(_W["champ_cfg_dict"], ...)       (:2212)  <- CANDIDATE
                  rung = _make_opponent(..., _W["champ_cfg_dict"], ...)  (:2234)  <- OPPONENT
_make_opponent  : opp_cfg = _cfg_from_dict(cfg_dict, opp_leaf_cfg)       (:1464)
```

Both sides are built from the **same dict**. `--c-puct 1.0` therefore moves **BOTH SIDES**, and a
"candidate c_puct 1.0 vs the unmodified champion" cell built on it would have been
**champion-vs-champion at c_puct 1.0** — a cell that plays 800 games, passes every gate that existed,
and reads as a clean null.

⚠️ **That is the same failure class the round was funded to fix, in a second location.** The audited
`fpu_reduction` defect made the knob unreachable; the `--c-puct` shape makes it reach *too far*.

**What was built instead.** A candidate-only override seam, `cand_search`:

- `_build_champ_cfg(..., cand_search=None)` / `_cfg_from_dict(..., cand_search=None)` —
  `None` is byte-identical to the pre-round function, and it is what the **opponent builder always
  passes**.
- `--cand-c-puct` (and `--cand-fpu-reduction`) resolve into that dict in `main()` and reach the
  **candidate construction site only**.
- `G-TWOSIDED` asserts the opponent's `c_puct` did **not** move, so a future cell built on `--c-puct`
  by mistake voids at adjudication instead of producing a credible null.
- `tests/test_fpu_knob.py::test_cand_c_puct_is_not_a_duplicate_of_c_puct` pins the distinction.

⭐ **Consequence for the τ pair:** `tau_p` has the **identical defect** — it rides `champ_cfg_dict`
too. A τ round needs `--cand-tau-p`. `READ_RULE.md` §6 records that as a build item and it is
**deliberately not built** here.

---

## D2 ⭐ THE BUDGET MOVED MID-BUILD: `k8 × 1376 = 11008` → `k16 × 1376 = 22016`

**The brief said:** *"fair PIMC k8×1376=11008 both sides."* The owner then promoted the desktop
champion to `k16 × 1376 = 22016` (2026-08-30) and directed the round to the current champion.

**What was done.** The pair is frozen at **22016 both sides**, and the launcher carries a **new
gate**, `G-PROD`, that reads `governance/PRODUCTION.yaml` at launch and refuses if `fair_deploy`
disagrees. ⛔ Hard abort for a real cell and for the smoke; loud-but-continue for `--dry-run`.

⚠️⚠️ **The build worktree PREDATES the promotion commit.** Its `PRODUCTION.yaml` still reads desktop
`k_dets: 8` (`k16` appears only under the *mobile* profile, explicitly labelled "desktop
UNTOUCHED"). **So `run_cells.sh --role local --dry-run` from this worktree emits the `G-PROD`
mismatch, by design.** That is the gate working, not a defect. The executor's bundle sync to the
promoted-champion `HEAD` clears it.

⛔ **A `G-PROD` failure is NEVER resolved by editing `WORKERS.conf` or `screen_lib.py`.** The
opponent of every cell **is** the champion of record.

⭐ **Mechanism note, in the round's favour:** the promotion is pure **width**. `sims_per_det` is
unchanged at 1376 and FPU acts *inside* one determinization tree, so per-tree first-visit behaviour
at 22016 is **identical** to 11008; `k_dets` only changes how many trees are pooled. The mechanism
argument is budget-agnostic (DESIGN §1.2) — but it stays an **argument**, and it rides as a rider on
`F-RESURRECT`, never as a licence to transfer a result downward in `k`.

---

## D3 ⚠️ COST: the brief's ETA was for the pre-promotion budget

**The brief said:** *"~800 games ≈ 1.5 h two-box at W30/W22."*

That is **correct at 11008 for a single cell split across both boxes** — realized rates give
`0.114 + 0.078 = 0.192` games/s → **1.16 h**. After the promotion and with **whole cells per box**
(the brief's own `G-HOST` requirement), the round is:

| | |
|---|---|
| one cell (800 games), local only | **3.9 h** |
| one cell (800 games), laptop only | **5.7 h** |
| **the round** (2 cells local + 1 laptop) | **≈ 7.8 h wall, ≈ 363 core-h** |

Re-priced from the realized `phasegate_a1/IDENT` cell (263.2 worker-s/game, local W30, 11008,
arbiter never fired) ×2.0 for the doubled `k`. ⚠️ `×2.0` is a **conservative upper bound** — the
exact-endgame tail and engine stepping do not scale with `k_dets`. Full derivation: `DESIGN.md` §6.

⭐ **Whole-cells-per-box costs ~0.9 h** (the laptop idles for the last ~2.1 h). Splitting one cell
into `_L`/`_R` sub-cells would give **≈ 6.9 h** at the price of a `G-SUBPOOL` gate and a pooled
primary. ⛔ **Not taken** — the brief specified whole cells, and the imbalance is disclosed rather
than engineered away.

---

## D4 ⭐ NO `IDENT` PREFLIGHT CELL — decided, with the argument

**The brief invited the decision:** *"An IDENT preflight cell is NOT needed if the golden gate covers
the None-identity — decide and justify."*

**Decision: no `IDENT` cell.** The phasegate precedent carried one **because its wheel moved** — a
stale `carc_rs` would have served a gate-blind arbiter, and only games could prove the new binary
reproduced old behaviour where it should.

**This round makes NO rust change.** `carc_rs` already accepted `Option<f64>` in the slot
(`carc-py/src/lib.rs:1580`) and `carc_core::search` already implemented the rule (`search/mod.rs:816`);
the fix is python plumbing. So:

- the wheel is a **constant of the comparison** — `ONE-WHEEL` asserts it inside the golden gate
  (all three legs on `carc_rs_binary_sha f6316d42838574de`), and `G-WHEEL-SAME` asserts it across the
  round;
- the golden gate covers **the only thing that moved**, over 20 seeded games, and it covers it
  *harder* than an `IDENT` cell would: an `IDENT` cell shows a null, while the golden gate shows
  **bit-identical action sequences**.

⭐ **Saving: ~11 core-h and one fewer band-adjacent archive.**
⚠️ **The substitution is valid ONLY because the wheel does not move.** If a future round in this
family touches rust, the `IDENT` cell comes back.

⭐ **What replaced it as the live risk, and what covers that:** the risk here is the **python rev**,
not the binary — a box on stale source serves a knob-free candidate with a perfectly healthy wheel.
`G-REV`'s cross-box clause covers it at adjudication, and `run_cells.sh` adds a **pre-compute knob
probe** (import this box's source, assert `fpu=Some(0.2)` in `repr(SearchConfigRs)`) so it is caught
before anything is spent.

---

## D5 ⚠️ THE TIE ARBITER IS OFF — a deviation from the DEPLOYED champion, per the brief

The brief specified *"tie-arbiter OFF both sides (single-variable discipline)"*, and that is what was
built. Recorded here because it is a **deviation from `governance/PRODUCTION.yaml`**, which has
carried `B=64` since 2026-08-20, and the price rides on every branch: the answer is about the
**arbiter-free** champion. `READ_RULE.md` §5.1 rider 3 carries it. `run_cells.sh` contains no
`--cand-tiearb-*` flag anywhere, by construction, and `G-ARB-OFF` walks the whole manifest.

---

## D6 ⭐ THE LEVER INDEX ALREADY RECORDS THIS AXIS AS **CLOSED** — the brief did not say so

`docs/LEVER_INDEX.md:146` reads: *"FPU / first-play urgency … TRIED twice … M3 later ran the full
curve → **peaks at parity, axis CLOSED**"*. CLAUDE.md requires checking that index **before**
proposing a lever, so the round cannot proceed as if the axis were untouched.

**Prior art found that the brief did not cite** (`results.csv` rows 233–236, 2026-07-02/03): a full
FPU curve at `0.4 / 0.6 / 0.8 / 1.0` against the pure-v2.9 anchor gave winrates
`0.391 / 0.496 / 0.4825 / 0.476` — **peaking at parity and rolling off**. Recorded reading: *"FPU
removes the weak value's HARM but cannot make it EXCEED"* the anchor.

**Why the reopening still stands**, stated narrowly in `DESIGN.md` §0.2 and `READ_RULE.md` §1.3:
every prior FPU cell measured a **neural or value-blended** agent, and **none of them could have
measured the classical champion**, because the knob was structurally unreachable on the champion's
backend. The prior evidence is not wrong; it is about a different agent.

⛔ **It is also the strongest reason to expect `F-REKILL`**, and that expectation is written into the
READ RULE before any number exists. `PRIOR_ART` in `screen_lib.py` carries all three prior cells with
their agents named, as **descriptive overlays only**.

---

## D7 ⚠️ `champion_factory._config_hash` MOVES — for every config, both sides alike

`fpu_reduction` is emitted **unconditionally** by `HeuristicPriorConfig.as_manifest()`, so the
`search.config_hash` in `champion_factory.resolved_manifest()` changes by exactly one key for every
config.

**Why unconditional.** `ABSENT is FAIL` is the house rule this whole family of rounds runs on, and
`null` must be a **positive statement** ("the champion's legacy optimistic q=0") rather than a
missing key. Every sibling knob in that dict (`jrules_prior_dose`, `tiearb_enabled`,
`tiearb_phase_gate`) is emitted unconditionally for the same reason.

**Why it is safe.** The search `config_hash` is **never pinned to a literal** anywhere in the repo —
grepped: its only consumers (`tests/test_carcasum_match_tiearb.py`, `tests/test_jcz_match_tiearb.py`)
compare **two live configs to each other**, and both sides move together. ⚠️ The *leaf* hashes
(`7fc930b8…`, `158f17ff…`, `a36d2e15…`) are a **different function** and are untouched.
`tests/test_frozen_substrates.py` and the full `test_carcasum_match_tiearb` /
`test_jcz_match_tiearb` / `test_frozen_substrates` / `test_semantic_eval_contracts` /
`test_neural_mcts` / `test_heuristic_prior_mcts` / `test_eval_provenance` suites pass unchanged.

---

## D8 ⭐ THE KNOB IS THREADED ON **BOTH** BACKENDS, not rust-only

The three precedent surfaces (`jrules_prior`, `jrules_filter`, `tiearb`) are **rust-only** and the
python search path raises `NotImplementedError` on them. `fpu_reduction` is **not** made rust-only:

- `carc_core::search/mod.rs:816` and `mcts.py:1225` implement the **identical rule** — `q = node_q − r`
  with no sign flip — verified line-by-line before threading;
- `NeuralMCTS` has accepted `fpu_reduction` since the round-2 audit, so the python side cost 4 lines
  (`HeuristicPriorAgent`, `make_heuristic_prior_mcts`, `fair_agent.search_one_world` and its
  `_world_kw` for the k-parallel split).

⭐ **The consequence is that a python-backend cell would be a REAL cell**, not a silently knob-free
one — which is a strictly safer failure mode than the rust-only surfaces have.
⚠️ `G-BACKEND` still requires `rust` on both sides: the champion of record plays on rust, and a
mixed-backend round is not one round.

---

## D9 ⚠️ `SearchConfigRs` HAS NO `fpu_reduction` GETTER — and none was added

The readback in `main()`'s fail-fast block parses `repr(SearchConfigRs)`, which prints
`fpu={:?}` of the stored `Option<f64>` (`carc-py/src/lib.rs:1875`). That is a genuine readback of what
the **Rust side holds**, not a restatement of what python sent.

⛔ **A getter was deliberately NOT added**, even though it would be tidier: adding one is a rust
change, which would rebuild the wheel, which would break the "the wheel is a constant" property that
`D4`'s no-`IDENT`-cell decision rests on. The `repr` parse costs three lines and preserves the
argument.

⚠️ The `c_puct` half of the readback is **parsed and compared numerically, never as a substring** —
rust's `Display` for `f64` prints `1.0` as `"1"`, so a naive `f"c_puct={_want_c}" in repr` check
would refuse a perfectly healthy config. Caught during the build.
