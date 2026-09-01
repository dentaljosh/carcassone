# L2 — exact-solver terminal-scorer swap · BUILD + GATES READOUT

**Status: BUILT, ALL GATES PASS, MERGE BLOCKED on the orchestrator's quiet window.**
Branch: `worktree-agent-a7a240dc0076da818`. Date: 2026-08-31.
Owner funding: "get an agent on the l2 build" (2026-08-31), off the 2026-08-30
eval-perf sweep's Value-3 menu.

---

## 0. TL;DR

| | |
|---|---|
| **What shipped** | The exact solver no longer scores terminals through the object route. `count_final_scores` on the terminal `apply_action` path is deferred; the terminal value comes from `leaf::decompose_into` + `leaf::flat_base_score` over per-thread scratch. |
| **Blast radius** | ZERO on the shared path. `GameState::apply_action` is byte-untouched; the substitution is scoped to the solver via a new `apply_action_unscored` / `advance_unscored`. |
| **Realized factor** | **3.19× on the whole solver at the deployed latch depth K=2** (see §4). The sweep's estimate was **5.57×** — it **deflates**, and the scorer-level premise deflates harder (measured **2.79×**, not the claimed 15.28×). |
| **Gates** | Randomized PRE-vs-POST identity: **520 positions / 2040 checks / 6 surfaces / 0 mismatches**. `cargo test --release --workspace`: **250 passed, 0 failed**. |
| **⚠️ Correction of record** | **The "240/240 gate banked" in the sweep's L2 row does not exist.** 240 is L0's tier1-swap leg count. See §2 — this is the second instance of the same mis-attribution class in this sweep. |

---

## 1. What the code actually does

### 1.1 The two object-scoring sites the solver was paying

Contrary to the L2 row's phrasing, `fair::solver::solve_marginalized` already
called `flat_base_score` at its terminals. The object scoring was one level
down, in the transition:

1. **`GameState::apply_action`** (`engine/mod.rs`) runs `self.count_final_scores()`
   in place on any action that terminates the game — a from-scratch BFS flood
   fill (`find_city` / `find_road` / `find_farm_by_coordinate`) per placed
   meeple, plus `count_farm_points`'s per-farm-node `HashSet<Vec<CoordSide>>`
   dedup. **This is the cost.**
2. **`GameState::flat_base_score`** then *cloned the whole state and ran
   `count_final_scores` again*. By that point step 1 had already drained the
   meeples, so the second pass added nothing — the solver was paying a full
   `GameState::clone` per terminal for a no-op.

### 1.2 The substitution

* `GameState::apply_action_unscored` / `Game::advance_unscored` — identical to
  the scored entry points on every transition **except** the two that terminate
  the game, where the in-place `count_final_scores` is skipped. `scores` stay
  RUNNING and `placed_meeples` stay populated. Both entry points share one
  `apply_action_inner(action, score_final)` body, so `apply_action`'s behaviour
  is unchanged *by construction* rather than by re-derivation.
* `fair::solver::terminal_value` — `decompose_into` + `leaf::flat_base_score`
  (`running + final_award`) over a thread-local `(Decomp, Scratch)` pair, the
  L0 `tier1::SCORER_BUFS` discipline verbatim.
* `fair::solver::with_legacy_terminal_scorer` — the gates-only TLS switch, the
  `tier1::with_legacy_scorer` pattern verbatim (unwind-safe via a `Drop` guard,
  pinned by its own test).

### 1.3 Why it is scoped OFF the shared `apply_action` path

`apply_action` is driven by tier1 playouts, PUCT search, the eval harness and
the phone, several of which read a terminal state's `scores` and
`placed_meeples`. Substituting there would owe a proof that the **meeple drain**
is reproduced exactly, on top of the scores. Scoping to the solver owes only the
score, because nothing downstream of a solver terminal reads anything else:

* `is_terminated()` is `next_tile.is_none()` — score- and meeple-independent;
* the transposition key is only ever taken on NON-terminal nodes (both `value`
  and `value_win` return before keying a terminal), so no key can see the
  deferred state;
* the only other terminal read is the value itself, which is what we replace.

That argument is the whole safety case, and it is pinned by
`advance_unscored_defers_only_the_terminal_scoring`, which asserts every
NON-terminal transition is byte-identical (`state_digest`: repr + legal mask +
both scores + terminal flag) and every terminal still scores to the same number
by **both** routes.

### 1.4 Both solvers

The swap is applied to **both** front doors:

* `fair::solver::solve_marginalized` — the SHIPPED exact-K latch (arb-off
  cells' exact-K, deploy exact-K, the phone's endgame latch), margin AND E1 win
  objectives;
* `endgame::solve` — the measurement solver, `Marginalized` and
  `Clairvoyant`+alpha-beta modes. It shares `fair::solver`'s `step` and
  `terminal_value` so the two cannot drift apart.

### 1.5 R9 / rules-profile handling

Nothing rules-profile-specific was added, and nothing needed to be. The L0
precedent needed explicit R9-flag handling because the *leaf* it swapped takes a
`LeafConfig` (the `farm_off` knockout among others). The terminal scorer does
not: it calls `leaf::flat_base_score`, which is `flat_base_score_farm(..,
farm_off = false)` — full farm scoring, the TRUE final score, exactly what
`count_final_scores` computes. The `farm_base_off` knockout is a heuristic-leaf
ablation and never reaches the exact tail by design. The `fixed_v1` /
`redraw_unplaceable` branch of `apply_action` (F9/A3) is covered: its terminal
`count_final_scores` is gated on the same `score_final` flag, and the gate legs
sample under the default profile with that branch reachable.

---

## 2. ⚠️ Correction: the banked 240-instance gate does not exist

The task brief (quoting the sweep's L2 row) states *"a 240/240 correctness gate
is ALREADY BANKED (value f64 bits + full optimal-action set + every child
value's bits + node count)"*. I looked for it. It is not a solver gate.

**What 240 actually is:** the leg count of **L0's tier1-swap `G-BITEXACT`** —
`scripts/tiletie/verify_tier1_rust.py`, `N_LEGS_EXPECTED = len(CHUNKS) *
len(LEGS) * PER_CELL # 240`, `n_playouts = 240 * 32 * 2 = 15360`. That is the
playout-scorer gate, not the solver.

**What IS banked for the solver:** **G7**,
`scripts/rustport/reconcile_exact_solver.py` →
`measurement/rustport_exact_solver/G7_exact_solver_main.json`. It checks exactly
the four surfaces the brief names — value f64 bits, the whole optimal-action set
in order, every child value bit-for-bit, and the node count (the search *shape*)
— but at **290 positions / 378 checks**, not 240, and it is a **py-vs-rust**
oracle gate rather than a pre/post gate. Its `main` run cost **15,577 s** (4.3 h,
3 workers).

**This is the second instance of the same mis-attribution class in this one
sweep.** The roadmap already records: *"the sweep's 'banked 252-position gate'
NEVER EXISTED (struct shape mis-remembered as a gate) — the spike built the
stronger one."* L2's "240/240" is the same failure with L0's number. Worth a
roadmap line: **the 2026-08-30 perf sweep's cited gates should be treated as
unverified until located.**

**What was done instead** — §3 builds the pre/post gate the change actually
owes, at 520 positions, and it is strictly stronger than a 240-instance
py-vs-rust re-run for *this* change: its PRE arm **is** the incumbent code path,
so no shared-mode error can hide in it.

---

## 3. Gate (b) — the fresh randomized bit-identity gate ✅ PASS

`rust/carc/carc-core/examples/l2_solver_gate.rs` →
[`GATE_RANDOMIZED.json`](GATE_RANDOMIZED.json), [`gate_randomized.log`](gate_randomized.log).

**Positions.** Sampled off **seeded tier-1 (`RuleBasedPlayer`) self-play games** —
real champion-policy late-game boards, not a synthetic descent — taking the first
TILES decision at each `k_remaining` target. 500 games sampled.

**Arms.** Each position solved TWICE from the same `Game`, in the same thread:
PRE under `with_legacy_terminal_scorer` (scored `advance` + engine
`flat_base_score` = the pre-L2 path byte for byte), POST on the shipped flat
route.

**Legs.** `fair/margin`, `fair/win` (E1), `endgame/marg`, `endgame/clair+ab`.

| Surface | Result |
|---|---|
| positions | **520** (k=2: 500, k=3: 20) |
| checks | **2040** |
| `value` raw f64 bits | **2040 / 2040** |
| full optimal-action set (order included) | **2040 / 2040** |
| every child value's bits | **2040 / 2040** |
| node counts | **2040 / 2040** |
| TT entries | **2040 / 2040** |
| win payload (`win_value` + `child_win_values` bits) | **2040 / 2040** |
| **mismatches** | **0** |
| wall | 449.9 s at W=24 |

**Threading by-catch.** The legs fan across 24 threads with both arms inside the
same worker, so the flat route's thread-local buffers were exercised
concurrently throughout — the L0 threading-gate analogue, for free.

**Node counts equal is the load-bearing one.** It proves the traversal, the TT
key stream and the move ordering are untouched, not merely that the answers
agree.

---

## 4. Gate (d) — directional bench

`rust/carc/carc-core/examples/l2_solver_bench.rs` →
[`BENCH_DIRECTIONAL.json`](BENCH_DIRECTIONAL.json), [`bench_directional.log`](bench_directional.log).

Same positions, same process, **arms interleaved per position** at the
production 2,000,000-node budget. Box was an **exclusive tenant** (loadavg
recorded at both ends; see the JSON).

| K | n | PRE µs/solve | POST µs/solve | **factor** | identity mismatches |
|---|---|---|---|---|---|
| **2** (the DEPLOYED latch depth) | 16 | 395,579 | 123,972 | **3.19×** | 0 |
| **3** | 4 | 19,895,658 | 5,989,237 | **3.32×** | 0 |
| **4** (both arms blow the 2M budget) | 2 | 354,253,351 | 157,148,137 | **2.25×** | 0 |

loadavg 0.68 → 1.01 across the run; the box was an exclusive tenant. Node
counts are bit-identical between arms by §3, so this is a pure cost contrast
over identical work. At K=4 both arms hit `BudgetExceeded` at the same node and
returned the *same* error — which is why the K=4 row reports `nodes=0` (only
`Ok` results accumulate) and 0 mismatches.

### 4.1 Where the 3.19× comes from

`solver_component_bench` (quiet box, arms interleaved, 40 captured transitions
at K=3) decomposes the per-node budget:

| component | ns |
|---|---|
| `legal_actions` (per node) | 3,796 |
| `string_repr` + sha256 TT key (per node) | 3,270 |
| clone + `advance`, **non**-terminal | 742 |
| clone + `advance`, **terminal** (`count_final_scores` in place) | **24,131** |
| clone alone | 663 |

So a terminal transition cost **32.5× a non-terminal one**, and near the latch
depth almost every child is terminal — which is why one function owned the
solver. The scorer A/B on **un-drained** late states (the input the terminal
scorer really sees — the drained-state comparison is unfair, since
`apply_action` has already emptied the meeple list):

| route | ns |
|---|---|
| legacy: clone + `count_final_scores` | 22,916 |
| flat: `decompose_into` + `flat_base_score` | 8,013 |
| …of which `decompose_into` alone | 7,685 |
| **scorer factor** | **2.86×** |

40/40 route equality on every captured state. The whole-solver 3.19× slightly
*exceeds* the 2.86× scorer factor because the swap also deletes the redundant
`GameState::clone` that `flat_base_score` was paying per terminal (§1.1 step 2):
the terminal path goes 24,131 ns → ~8,013 ns = 3.01×, and the rest is the
node-level overhead shrinking as a share.

### 4.2 Realized vs the 5.57× estimate — it deflates, and so does the premise

**It deflates.** Stated plainly, as the brief asked:

| claim | sweep estimate | measured |
|---|---|---|
| scorer alone | **15.28×** | **2.86×** (5.3× optimistic) |
| whole solver | **5.57×** | **3.19×** at K=2 (1.7× optimistic) |

**The scorer-level premise deflates much harder than the solver-level one**,
which is worth naming because the sweep derived the second from the first. The
reason: the flat route's cost here is **95.9% `decompose_into`** (7,685 of 8,013
ns), and an exact-K terminal is the single most expensive board in the game for
that function — a full ~70-tile whole-board union-find. L0's tier1 swap measured
7.9–9.9× on the playout scorer because playout afterstates span all phases,
where `decompose_into` is much cheaper; carrying that factor across to
end-of-game boards is what inflated 15.28×. This is the same root cause the L1
spike found for its own refuted estimate (*"the sweep leaned on the PYTHON
flat-leaf 'enumeration ~45%' figure — rust is ~37% and UF+facts dominate"*).

**The K=4 row deflates further still (2.25×)**, and directionally: the deeper
the latch, the smaller the terminal share of the tree and so the smaller the
win. Any deploy projection should use the **K=2 figure, 3.19×**, since
`exact_max_k = 2` is what ships — and should not assume it holds if the latch
depth is ever raised.

**Still a real win.** 3.19× bit-identical on the shipped exact-K latch, for no
strength risk, is worth taking. It is just not 5.57×, and Value-3's deploy
≈3.6× projection deflates accordingly — on top of the deflation L1 already
forced.

### 4.2 The p99-tail claim is NOT verified here

The sweep's L2 row attributes to this lever *"the p99-51s last-wave wall"* / *top
10% of side-games = 59.7% of solver seconds*. **That gets its real verification
at a deployment bench, not here.** This bench prices µs/solve on sampled
positions; it says nothing about how solver seconds distribute across a real
side-game population, and nothing about how a 3× solver buys wall-clock in a
`--backend rust` eval cell where the solver is one term among several. Also
open and unreconciled from the sweep itself (§C-3): *audit-F3's ~34 s/game
exact-K charge vs the 8,400-instance measured ~3.7 s/game — 8× apart.* Until
that is reconciled, no deploy-level multiplier should be quoted off this bench.

---

## 5. Gate (c) — `cargo test --workspace`

`nice -n 19 cargo test --release --workspace` — **250 passed, 0 failed, 6 ignored** ✅
(45.97 s; the other four workspace targets have no tests).

(Release profile, per the house precedent for the heavy solver tests: the dev
profile's `opt-level = 1` makes a k=3 exact solve unusable in a test.)

⚠️ **One real finding, from my own new test.** The first draft of
`advance_unscored_defers_only_the_terminal_scoring` tried ONE ply out of a
`k_remaining <= 2` TILES root and asserted `n_terminal > 0`. It failed: a tile
placement hands off to the MEEPLES phase, so a k≤2 TILES root **cannot**
terminate in one ply. The fixture now walks a bounded sub-tree instead. Recorded
because the coverage assertion is what caught it — a version of this test
without `assert!(n_terminal > 0)` would have passed while exercising **zero**
terminal transitions, i.e. testing nothing of what it claims to test.

New in-suite pins (`fair::solver::tests`):

* `l2_flat_terminal_route_is_bit_identical_to_the_legacy_route` — all six
  surfaces, both objectives, k=2 (×8 seeds) + k=3.
* `advance_unscored_defers_only_the_terminal_scoring` — the §1.3 safety
  argument, asserted.
* `flat_terminal_buffers_are_thread_safe` — single-threaded vs threaded solves.
* `the_legacy_switch_is_restored_on_unwind` — the gate switch cannot leak.

---

## 6. Consumers and what is still owed before deploy

Consumers of the swapped path — **arb-off cells' exact-K, deploy exact-K, the
phone's endgame latch** — are bit-identical-or-nothing, and §3 is the
bit-identity evidence at 520 positions across both solver front doors and both
objectives.

**Still owed before this is deployed:**

1. **Merge at the orchestrator's quiet window** — not taken here. ENGINE-class
   items go through the gated build pipeline per the standing owner ruling; this
   is one.
2. **A `carc_rs` wheel rebuild** (`RUSTUP_TOOLCHAIN=1.96.0`, the CLUSTER_OPS
   recipe) and the standing per-box post-build check, on every box that plays.
   No wheel was built or installed by this work — the shared venv is untouched.
3. **A G7 re-run against the rebuilt wheel** — the *real* banked solver gate
   (§2), py-vs-rust. Not owed by the change's correctness argument (§3's PRE arm
   is the incumbent) but cheap on its `golden`+`v2` legs (11.6 s) and the right
   thing to stamp a wheel with.
4. **A deployment bench** for any wall-clock or tail claim (§4.2).

No strength claim is owed or made: the change is bit-identical, so it cannot
move play.

---

## 7. Files

| Path | What |
|---|---|
| `rust/carc/carc-core/src/engine/mod.rs` | `apply_action_inner` + `apply_action_unscored`; `apply_action` unchanged in behaviour |
| `rust/carc/carc-core/src/game.rs` | `advance_inner` + `advance_unscored` |
| `rust/carc/carc-core/src/fair/solver.rs` | the L2 module comment, `TerminalBufs` TLS, `with_legacy_terminal_scorer`, `step`, `terminal_value`, 4 swapped sites, 4 new tests |
| `rust/carc/carc-core/src/endgame/mod.rs` | the same swap on the measurement solver (marg + clair/ab) |
| `rust/carc/carc-core/examples/l2_solver_gate.rs` | gate (b) |
| `rust/carc/carc-core/examples/l2_solver_bench.rs` | gate (d) |
| `rust/carc/carc-core/examples/solver_component_bench.rs` | the cost decomposition of §4.1 → [`COMPONENT_BENCH.txt`](COMPONENT_BENCH.txt) |
| `rust/carc/carc-core/examples/solver_profile.rs` | per-K solve cost calibration |
