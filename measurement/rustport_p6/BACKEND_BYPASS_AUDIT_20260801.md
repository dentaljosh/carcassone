# BACKEND BYPASS AUDIT — who stays on Python after the `backend: rust` flip

> **Status: READ-ONLY AUDIT, 2026-08-01.** No code was changed by this audit. It answers Joshua's
> question — *"no more python eating cpu cycles?"* — with the honest residual list, and it found a
> second problem on the way that is more urgent than the first.
>
> Evidence: `measurement/rustport_p6/G6_backend_deploy_multiplier.json` (the 7.98× / 7.31× / 41.6×
> figures) · DECISIONS 2026-08-01 (P6/G6, P7/G7) · `src/carcassonne_ai/rust_agent.py` (the adapter)
> · `scripts/rustport/reconcile_backend.py` (the reference game loop).

---

## THE ONE-PARAGRAPH ANSWER (read this and stop)

**No — the flip does not move the fleet to Rust, and flipping the default alone is not safe.** The
backend selector lives on exactly one function, `champion_factory.make_production_champion(...)`,
and **six call sites in the whole repo use it** (`play_vs_tier1_gui.py:1077`,
`human_anchor/play_harness.py:127`, `m5_bench/bench_champion.py:300`,
`measurement_infra/kparallel_latency_bench.py:139` and `:268`, `android_bridge.py:867`). Everything
else that plays or scores a champion move — `eval_fair_puct.py` (every elo row we own), the whole
`measurement_infra/` probe family, `gen_fair_distill.py` (the gen driver), `eval_puct_priors.py`
(which never imports the factory at all) — reaches the agent through
`build_fair_champion()` / `build_clairvoyant_champion()` or a direct constructor. **Those have no
`backend` parameter and cannot get one from a YAML edit**, so they keep running 100% Python search,
silently, at 12.7 s/move instead of 1.59 s/move. That is the CPU answer: **the phone flipped, the
desktop fleet did not.** The second finding is the urgent one and it points the other way: of the
six sites that *will* pick up a flipped default, **five drive the agent in a way the Rust agent
does not support**. `RustFairAgent` owns a mirrored game state and requires `start_game(board)` plus
`advance(action)` for every applied action of both seats; `grep` shows `advance:0 start_game:0` in
all four desktop callers. Its sync check is a no-op unless `CARC_RS_RECONCILE=1`, so a full-game
harness would get an agent whose mirror is frozen at the ply it first saw, **returning moves
computed for a stale position with no error raised** — in `play_harness.py` and
`play_vs_tier1_gui.py`, i.e. the human-facing E4 exam path. `kparallel_latency_bench.py:139`
additionally passes `parallel_workers=`, which `make_production_champion` *raises* on when the
backend is Rust. So the sequencing matters: **do not flip the default before the callers are
taught the mirror protocol.** The fix is well-shaped — the adapter was deliberately built to emit
the eval harness's exact counter shape, and the reference loop already exists at
`scripts/rustport/reconcile_backend.py:162-192` — but it is per-harness work, and the entire
clairvoyant/oracle ruler tier has no Rust agent to convert to at all.

---

## 0. Premise correction — what a YAML edit can and cannot reach

The task framing was "`champion_factory` reads `PRODUCTION.yaml` as the backend default". As of
this audit that is **not yet true on disk**, and the distinction drives the whole fix list.

| Surface | Reads a backend? | Effect of the YAML flip |
|---|---|---|
| `make_production_champion(..., backend=...)` | kwarg only; signature default is the literal `"python"` | **none** unless the signature is changed to resolve from the spec, or a caller passes it |
| `deploy_profile(name)` | **yes** — returns `backend` / `rust_threads` (added 2026-08-01 with the mobile unpin) | surfaces the value, **does not apply it**. `PRODUCTION.yaml`'s own "WIRING STATUS" comment says this is deliberate for `parallel_workers`; `backend` inherited the same posture |
| `load_production_spec()` → `ProductionSpec` | **no top-level `backend` field** | a top-level `champion.fair_deploy.backend` key is parsed away silently unless `ProductionSpec` gains the field |
| `build_fair_champion()`, `build_clairvoyant_champion()`, `build_fair_netprior_candidate()` | **no `backend` parameter exists** | **none, ever** — these call `FairHeuristicPriorAgent` / `HeuristicPriorAgent` directly |

⚠️ `governance/PRODUCTION.yaml` and `src/carcassonne_ai/champion_factory.py` were being edited by
another agent during this audit. Treat line numbers in this section as indicative and re-read before
acting; the classification below does not depend on them.

**Load-bearing consequence: "routes through champion_factory" is not the test.** The F1
single-construction-point work routed the harnesses to the *thin builders*, which is a provenance
win but not a backend seam. The test is "calls `make_production_champion`".

---

## 1. ⚠️ THE URGENT HALF — the six sites that DO react, and why five of them break

`RustFairAgent` is not a drop-in for `FairHeuristicPriorAgent` at the *call-protocol* level. It
mirrors the game inside Rust and can only be moved by `advance()`
(`src/carcassonne_ai/rust_agent.py:14-32, 242-298`). `choose_action` auto-seats the mirror the first
time it is called, and thereafter `_check_sync` is a **no-op unless `CARC_RS_RECONCILE=1`**
(`rust_agent.py:330-334`). A caller that never advances therefore gets a frozen mirror and **no
exception**.

| site | drives the mirror? | what happens if the default flips today |
|---|---|---|
| `android/app/src/main/python/android_bridge.py:867` | **yes** — 2 × `start_game`, 2 × `advance`, its own choke point | safe (and it already bypasses the factory for the real Rust path — see §4/A9) |
| `scripts/human_anchor/play_harness.py:127` (loop `:179-211`) | **no** (`advance:0 start_game:0`) | **silent wrong play in a full game.** Mirror freezes at first move; the agent answers for a stale position. This is the E4 human-exam harness |
| `scripts/play_vs_tier1_gui.py:1077` (`pick=` at `:1109`, loop `:564`) | **no** | same — silent wrong play, interactive |
| `scripts/m5_bench/bench_champion.py:300` | **no** | benches a frozen-mirror agent; timings become meaningless rather than merely wrong-engine |
| `scripts/measurement_infra/kparallel_latency_bench.py:139` | **no**, *and* passes `parallel_workers=workers` | **raises `ValueError`** on the parallel rows (the factory rejects `backend="rust"` + `parallel_workers`); on the `workers=None` rows it silently benches Rust-sequential against Python-parallel — a nonsense speedup number |
| `scripts/measurement_infra/kparallel_latency_bench.py:268` | manifest probe only | builds a Rust agent for the manifest; harmless |

**Recommendation: F-1 (flip the default) and F-4 (teach the callers) must land together, or the
default stays `"python"` and each caller opts in explicitly.** The second option is strictly safer
and matches the posture `PRODUCTION.yaml` already takes for `parallel_workers`.

---

## 2. Class A — hot path, actively used, silently stays Python (the CPU answer)

Ordered by CPU actually at risk.

| # | file:line | builds | routes via | why it stays Python | est. share of that run's CPU |
|---|---|---|---|---|---|
| A1 | `scripts/classical_search/eval_fair_puct.py:1004` (`--info fair`), `:1045` (`fair-netprior`), `:1056` (`fair-net`); opponent side via `_make_opponent`→`_make_champion` (`:1159`) | `FairHeuristicPriorAgent` | `champion_factory.build_fair_champion(...)` | no `backend` param on the builder | **~90-95% of a champion-vs-h800 cell; ~100% of a symmetric champ-vs-champ cell.** The flagship strength harness — every elo row in `experiments/results.csv` comes from here. Most-cited file in STATUS, 12+ live `.sh` launchers |
| A2 | `scripts/measurement_infra/kwidth_agreement_probe.py:252, 290, 330, 421` | `FairHeuristicPriorAgent` | `CF.build_fair_champion(...)` | same | **~100%.** ⚠️ **LIVE TODAY** — file touched 2026-08-01; driver behind the pre-registered "champ vs 10× champ" 110k oracle screen (`ca5b571`), launchers `run_kwidth_110k_20260801.sh` / `chain_kwidth_110k_20260801.sh` |
| A3 | `scripts/measurement_infra/oracle_score_pilot.py:503, 554` | `HeuristicPriorAgent` (clairvoyant continuations) | `CF.build_clairvoyant_champion(...)` | same | **~100%.** ⚠️ **LIVE TODAY** — the Phase-2 scorer of the same 110k run. Also Class B (it is a ruler) |
| A4 | `scripts/measurement_infra/move_agreement_probe.py:270, 349, 490` and `sample_agreement_roots.py:178, 190, 266` | `CF.build_fair_champion` + raw per-world `NeuralMCTS` | factory-adjacent | same | ~100% of each probe. Their output bank (`move_agreement_k4_b28e9`) is what today's kwidth run reads — **active via its artifact** |
| A5 | `scripts/distill_flywheel/gen_fair_distill.py:242` | `FairHeuristicPriorAgent` **direct import** | — | never touches the factory; config from a local `_CANON_ENV` dict (`:62-75`) duplicating `champ_env.sh`, plus argparse `--k-dets 4 --sims 688` (`:419-423`) | **~100% of gen wall-clock.** The active rodv3 turn-1 generator (parked 65/300). Also already **stale on budget** (k4×688 vs champion-of-record k8×1376) |
| A6 | `scripts/classical_search/eval_puct_priors.py:884, 1176` (candidate); `:243, 293, 306, 352-353, 595` (opponents/arms) | `HeuristicPriorAgent`, `HeuristicMCTS`, `AlphaBetaAgent`, `NeuralMCTS` | **none — the file never imports `champion_factory`** | structurally cannot see any governance change | ~100% of its own process. Still launched (`leaf_ablation_launcher.sh`, `wsweep_f7d.sh`, 2026-07-30/31). Note it grades against the *pre-2026-07-07 dethroned* champion by design |
| A7 | `scripts/measurement_infra/gate_b_fair_pimc.py:212` (+ raw `NeuralMCTS` `:264, :378`) | agent-as-component-library | `CF.build_fair_champion` | same | ~100% of the probe. Verdict closed 2026-07-21, but the infra is reusable |
| A8 | `scripts/measurement_infra/adaptive_k_census.py:320, 507` (+ raw `NeuralMCTS` `:354, :370`) | same shape | `CF.build_fair_champion` | same | ~100%. Lever died at pre-gate 2026-07-28 |

### A-class semantics notes

**A1 has a wrinkle that is good news.** `eval_fair_puct` builds its prefix with
`exact_endgame=False` and wraps it in a Python `_MarginalizedHandoff` (`:618-667`) that
re-implements the endgame solve via `S.solve(...)`. `RustFairAgent` was *deliberately* built to emit
that wrapper's counter shape — `prefix_moves` / `prefix_secs` / `exact_moves` / `solver_secs` /
`solver_nodes` / `max_solve_secs` / `n_timeouts` / `latch_k` are all present
(`rust_agent.py:34-50, 438-477`), and `FairAgentRs` exposes `solve_marginalized`
(`rust/carc/carc-py/src/lib.rs:1084`). So the correct conversion **replaces the whole
`_MarginalizedHandoff`**, not just its `._prefix`, and moves the endgame solve into Rust too. Two
guards read `getattr(champ, "_prefix")`: `_oracle_telemetry(...)` at `:1611` (oracle-prior overlay,
a Python-only search variant) and an `isinstance(..., FairHeuristicPriorAgent)` assert at
`:1980-1983` (bare-net smoke branch only — widen the tuple).

**A4/A7/A8 are not constructor swaps.** They build the champion and then reach *inside* it —
`agent._evaluator`, `agent._c_puct`, `agent._min_pooled_visits`, `agent.det_seed_base`,
`agent._pimc_move` — and run the per-determinization searches themselves. They use the Python agent
as a **component library**, not as a player. Their Rust route is
`FairAgentRs.determinizations()` → `MirrorState.set_unseen_deck` → `search_single`, not a kwarg.

---

## 3. Class B — instrument / ruler; the "clair-wiring" work item

Clairvoyant and oracle-grade agents. Hot, but **there is no Rust clairvoyant agent** —
`make_production_champion` explicitly raises on `backend="rust"` with `mode="clairvoyant"`.

| # | file:line | builds | note |
|---|---|---|---|
| B1 | `scripts/measurement_infra/oracle_score_pilot.py:554` | `CF.build_clairvoyant_champion` | the oracle scoring ruler (= A3; live today) |
| B2 | `scripts/classical_search/eval_fair_puct.py:1060` (`--info clair`) | `CF.build_clairvoyant_champion` | clairvoyant arm of the flagship harness |
| B3 | `scripts/classical_search/eval_puct_priors.py:293, 352-353, 884, 1176` | `HeuristicPriorAgent` direct | both sides clairvoyant by design (Phase-1.1 matched-mode A/B) |
| B4 | `scripts/measurement_infra/gate_b_depth_transfer.py:219, 292` | `HeuristicPriorAgent` direct (`_CFG` from `CF.production_prior_cfg()` at `:398`) | multi-depth snapshot ladder |
| B5 | `scripts/measurement_infra/snapshot.py:142` | `HeuristicMCTS` on `frozen_v29_cfg()` | the multi-depth snapshot primitive `scripts/measurement_infra/README.md` names as DEFAULT measurement tooling. ⚠️ deliberately the **pre-C5 frozen** substrate `7fc930b8`, not curve125 — converting it must preserve that pinning. Also an infra dependency: `champion_factory._hashers()` imports `snapshot._frozen_config_hash` |
| B6 | the per-world inner loops of A2/A4/A7/A8 | raw `NeuralMCTS` / `search_one_world` | see "component library" above |

### Does the Rust surface support this tier? — mostly YES, with three named gaps

**Present and well-shaped** (`rust/carc/carc-py/src/lib.rs`):

- `MirrorState.search_single(cfg, …)` (`:356`) — documented as *"Equivalent to
  `HeuristicPriorAgent(game, cfg, sims).move(board)` with `reuse_tree=False` on a board whose deck
  is whatever `set_unseen_deck` last installed."* Returns `pooled_stats` = *"`fair_agent.root_stats_list`
  — deduped, N>0, ROOT-POV-signed W"*, i.e. exactly what `search_one_world` returns.
- `set_unseen_deck` (`:339`) / `unseen_deck` (`:333`) — the determinization hook.
- `FairAgentRs.determinizations(move_idx)` (`:1123`) — hands over the k worlds' decks, so B6's
  pooling is reproducible.
- `MirrorState.from_seed` / `from_deck` + `advance` — lossless root replay, the same contract
  `scripts/measurement_infra/root_replay.py` already uses. Reference:
  `scripts/rustport/reconcile_backend.py:291-293`.

**Gap 1 — no seed on the search.** `SearchConfigRs` (`lib.rs:758-830`) has no `seed` field, but B6
passes per-world seeds (`seed=base+100+i`). G3 gated `search_single` only against
`HeuristicPriorAgent(..., seed=None)` (`scripts/rustport/trace_search.py:324`). The seed feeds
`NeuralMCTS._np_rng`, consumed only by temperature sampling (`mcts.py:696`) and Dirichlet root noise
(`:1011`) — neither engaged at champion knobs under `best_action`. **Very likely inert, but not
proven inert for this path.** Prove it before trusting any B6 conversion.

**Gap 2 — no `reuse_tree`.** `search_single` is fresh-tree only. Inert for the champion
(`reuse_tree: true` in the YAML is a documented no-op in fair deploy), but a clairvoyant ruler that
sets it is not reproducible.

**Gap 3 — no evaluator injection, no `meeple_dedup` / `intra_reuse`.** The Rust core carries no net
evaluator, so `--info fair-netprior` / `fair-net` and all of `build_fair_netprior_candidate` are
**out of scope for Rust** and must stay Python.

---

## 4. Class C — legacy, dead path, or deliberately Python (no action)

| group | why |
|---|---|
| `eval_fair_puct.py:675` `_RungPrefix` (`HeuristicMCTS` h800), `:702` `_GreedyPrefix` (`RuleBasedPlayer` tier1), `:839` `_BareNetPrefix` (sighted `NeuralMCTS` RoD-v2 anchor) | **frozen rulers.** Their ratings in `results.csv` are interpretable only because they are bit-for-bit unchanged. Do **not** port |
| `src/carcassonne_ai/fair_agent.py:214/227/237/454`, `heuristic_prior_mcts.py:1027/1296` | these *are* the Python backend's internals |
| `src/carcassonne_ai/alphabeta_agent.py`, `selfplay.py:208/231`; `eval_puct_priors.py:306` `_AbPrefix` | αβ is a clair-only dead end (CL-053, closed 2026-07-13); `selfplay` is the neural Phase-4 loop. No Rust surface, no live use |
| `scripts/measurement_infra/gen_meeple_dedup_fixture.py:81`, `gen_intra_reuse_fixture.py:80` | generate **golden fixtures for the Python agent's own semantics** on the frozen substrate. Converting them destroys the reference |
| `scripts/classical_search/bench_ab_cost.py:344…`, `bench_equal_time{,_cy}.py:129/139`, `optuna_knob_sweep.py` | pre-flip / C6-closed benches; `bench_ab_cost` docstring: *"nothing in production imports it"* |
| `scripts/measurement_infra/meeple_dedup_census.py`, `analyze_kwidth*_oracle.py`, `verify_h12800.py`, and the readers (`kdets_delta.py`, `pareto_curve_tally.py`, `root_replay.py`, …) | build no agent, or are closed self-tests |
| `scripts/level2/*`, `az_zero/*`, `rod_v2/*`, `rod_v28/*`, `step2_pens/*`, `heuristic_v28/*`, `canonical_az/{fair_agent_smoke,gen_fair_selfplay,eval_m2_net_vs_net}.py`, `fair_handoff_audit/audit.py`, `run_selfplay_iter.py`, ~20 top-level `scripts/*.py` diagnostics | pre-2026-07-07-flip tooling on the legacy `NeuralMCTS` / `HeuristicMCTS` / `FairHeuristicMCTSAgent` classes. They never constructed the current champion, so the flip is moot. Closed programs (CL-066, rod_v28, L2 verdicts all COMPLETE) |
| `scripts/bench/bench_fair_batch.py:421, 433` | direct `FairHeuristicPriorAgent`, but a latency microbench predating the factory, superseded by `measurement/EFFJENSEN_BENCH_BATCH_20260729.md` |
| `tests/` — 34 files construct agents directly | they test the Python agent. Leave them; the Rust side has `tests/rustport/` |
| `android/app/src/main/python/carc_p7_probe.py:203-253` | hand-built `carc_rs`, but a G7 device diagnostic; nothing in the app imports it |

### One Class-C-adjacent item that is actually a correctness bug (A9)

`android_bridge._start_rust_mirror` (`:~1008`) builds `carc_rs.FairAgentRs` **by hand**, bypassing
both `rust_agent.RustFairAgent` and the factory, and takes its leaf from
`carc_rs.LeafConfigRs.curve125()` — a compiled-in Rust `#[staticmethod]` preset
(`rust/carc/carc-py/src/lib.rs:122-128`) — instead of `production_leaf_cfg(spec)` →
`rust_agent.leaf_config_rs()`. It stamps the YAML `leaf_hash` into the archived game (`:1619`) but
never verifies it. So the archive records **a label, not the function that executed** — exactly the
R1/R7 anti-pattern `champion_factory.verify_leaf(..., backend="rust")` exists to prevent, and that
guard never runs on the agent the phone actually plays. If the champion leaf is retuned again,
`PRODUCTION.yaml` and the phone diverge **silently**, and the E4 human-game archive becomes wrong
about what played. Correctness, not speed — but it is the highest-value non-CPU finding here.

---

## 5. Class D — fine as is

| file | why |
|---|---|
| `scripts/rustport/*` (`reconcile_backend.py`, `reconcile_fair.py`, `fair_common.py`, `trace_search.py`, …) | already Rust by construction. `fair_common.rs_agent()` and `trace_search.production_knobs()` read the YAML through `load_production_spec()` and cross-assert the leaf against the factory's (`fair_common.assert_same_leaf`) — a **deliberate** independent second path, because a gate sharing the code it grades would be worthless |
| `src/carcassonne_ai/champion_factory.py`, `rust_agent.py` | the seam itself |
| `tests/rustport/test_p6_backend.py` | already exercises `backend="rust"` end to end |
| `scripts/classical_search/c5_leaf_override.py`, `measurement_infra/snapshot.py` (as a hash source) | leaf-hash helpers imported *by* the factory; not agent builders |

**No script anywhere re-parses `governance/PRODUCTION.yaml` directly** (`grep yaml.safe_load` over
`scripts/` = zero hits outside the factory). The only shadow copies are hardcoded knob mirrors:
`eval_fair_puct.py:1172` `PROD_KNOBS` (drift-*detector* only, builds nothing — and it has no
`backend` key, so it cannot warn about this flip), `bench_ab_cost.py:122-127` `CHAMP_*` (dead path),
and `scripts/distill_flywheel/champ_env.sh` (leaf values current, budget stale at k4×688).

---

## 6. Prioritized fix list for the follow-up wiring agent

**F-0 — decide the default posture first (blocking, 5 min of judgement).** Either keep
`make_production_champion(backend=...)` defaulting to `"python"` and make every caller opt in
(safer, matches the `parallel_workers` posture the YAML already documents), **or** flip the default
and land F-4 in the same change. Do not flip it alone — see §1.

**F-1 — make the backend reachable (~30 lines).** Add `backend` / `rust_threads` to
`ProductionSpec` + `load_production_spec()`. Add a `backend=` / `rust_threads=` passthrough to
`build_fair_champion()` that dispatches to `RustFairAgent`, so the harnesses already on the thin
builder need one kwarg rather than a rewrite. Keep the raise on `mode="clairvoyant"`. Guard:
`resolved_manifest` must keep stamping `backend` only when non-default, or every existing manifest
hash drifts.

**F-2 — `eval_fair_puct.py` (A1). Highest CPU payoff in the repo.** Replace
`_MarginalizedHandoff(prefix, …)` with `RustFairAgent(exact_endgame=True, exact_max_k=K,
exact_budget=EXACT_BUDGET)` for `--info fair` (the adapter already emits the wrapper's counters and
moves the solve into Rust). Then:
- `_play_one` (`:1541`): `champ.start_game(board)` after `get_init_board()`; `champ.advance(action)`
  after **both** seats' `get_next_state` (`:1591`).
- smoke loop (`:1900-1911`): the same two lines.
- widen the `isinstance(..., FairHeuristicPriorAgent)` assert at `:1981`; make
  `_oracle_telemetry(getattr(champ, "_prefix", None))` at `:1611` None-safe.
- leave `fair-netprior` / `fair-net` / `clair` and the `h800` / `greedy` / `bare-net` opponents on
  Python (Gap 3 / Class C).
Reference loop: `scripts/rustport/reconcile_backend.py:162-192`.

**F-3 — the four `make_production_champion` desktop callers (§1).** Teach `play_harness.py`,
`play_vs_tier1_gui.py`, `bench_champion.py`, `kparallel_latency_bench.py` the `start_game` /
`advance` protocol, and have them read `deploy_profile(profile)["backend"]` / `["rust_threads"]` and
forward them — exactly as `play_harness.py:105` already does for `parallel_workers`. Note
`backend="rust"` and `parallel_workers` are **mutually exclusive** in the factory; use
`rust_threads`. `kparallel_latency_bench` needs a decision, not a patch: it exists to measure the
*process* split, which Rust replaces with a thread split. Biggest felt win: `play_vs_tier1_gui` /
`play_harness` drop from ~13.8 s/move sequential to ~0.3-0.5 s/move.

**F-4 — `gen_fair_distill.py` (A5).** Add `--backend` and route `:242` through
`build_fair_champion(...)`. While there, decide explicitly whether the k4×688 argparse default moves
to k8×1376 — a pre-existing staleness shared with `PROD_KNOBS` and `champ_env.sh`, and it must not
change as a silent side effect of a backend flip.

**F-5 — close the A9 provenance hole (correctness, not speed).** Make
`android_bridge._start_rust_mirror` derive its leaf from `production_leaf_cfg(spec)` →
`rust_agent.leaf_config_rs()`, or — cheaper — assert the `curve125()` preset equals the resolved
spec leaf at startup and fail closed.

**F-6 — the clair-wiring build (Class B).** A genuine new component: a `RustClairvoyantAgent` (or a
`search_single`-based helper in `rust_agent.py`) over `MirrorState.from_seed` + `advance` +
`set_unseen_deck` + `search_single`. Convert B5 (`snapshot.py`) first — it is the shared primitive
under the whole measurement-infra family — then the B6 per-world loops via
`FairAgentRs.determinizations()`. **Close Gap 1 first** (prove `search_single` is seed-invariant at
champion knobs), and preserve `snapshot.py`'s deliberate frozen-`7fc930b8` pinning.
⚠️ B1/B2 are *reference instruments*: converting them changes the ruler. Any conversion needs its
own identity gate on the G6 pattern (100% action agreement) before a converted ruler grades
anything.

---

## 7. Sizing the residual — the Amdahl caveat

From `G6_backend_deploy_multiplier.json`, production k8×1376 on the local box:

| leg | s/move | vs Python |
|---|---|---|
| Python (deployed Cython leaf), single stream | 12.688 | 1× |
| Rust, 1 thread | 1.590 | **7.98×** |
| Rust, 8 threads | 0.305 | **41.6×** |
| W8 game-parallel pool | — | Rust W8 = **7.31×** |

Two honest deflators on "everything gets 8× faster":

1. **Only the champion side converts in an asymmetric cell.** In champion-vs-h800 the rung is a
   fixed 800-sim `HeuristicMCTS` that must stay Python (frozen ruler). At 800 sims against the
   champion's 11008 the rung is roughly 7% of the pair's move cost today — but once the champion
   side drops ~8×, the unconverted rung becomes ~35-40% of what remains, so realised end-to-end
   speedup on those cells is nearer **~5×, not 8×**. Symmetric champ-vs-champ cells convert fully
   and do get the full multiplier. ⚠️ The 7% is a sims-ratio *estimate*, not a measurement — confirm
   from a real `rung_ms_per_move` field on the first converted run.
2. **Class B does not convert at all until F-6 ships**, and the oracle/ruler tier is a large share
   of recent measurement compute.

**Defensible statement for tonight:** *the phone flipped; the desktop fleet has not, and flipping
the factory default without F-3 would break the human-facing harnesses rather than speed them up.
Landing F-1 + F-2 converts the single largest CPU consumer in the repo (~8× on the champion side,
~5× end-to-end on asymmetric cells). Everything else in this file is still Python until someone does
the work.*
