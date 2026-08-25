#!/usr/bin/env python3
"""Differential gate: the Rust deep exact-K endgame solver vs the Python ORACLE.

`carc_core::endgame` (exposed as `carc_rs.MirrorState.solve_endgame`) is a port
of `scripts/level2/endgame_solver.py`.  This replays real corpus endgame
positions through BOTH solvers and asserts, per position and per mode:

  * `value`            — raw f64 BITS, never decimal
  * `optimal_actions`  — the whole SET, in order
  * `child_values`     — every legal root action's exact value, bit-for-bit
  * `nodes`            — the node count, i.e. the SEARCH SHAPE, not just the
                         answer.  A TT-key, move-ordering or chance-node
                         difference trips this even when the values agree.

Exit discipline (the house convention, `reconcile_fair.py`):

    ok = (mismatches == 0) and (checks > 0)

— zero mismatches over zero checks is the sha-of-empty shape and never PASSes.

## Legs

  golden  the 14 frozen solver blocks in `tests/golden/golden_fixture.json`
          (marginalized, K<=2, budget 500_000).  Rust is compared against the
          FROZEN DISK values *and* against a live Python re-solve.
  v2      V2 from `tests/test_endgame_solver.py`: at K=1 there is no hidden
          future, so clairvoyant == marginalized exactly — checked on BOTH
          implementations and cross-wise.
  l23     `measurement/level2/l23_positions.jsonl` (750 rows, K=2..6, greedy
          replay) + `l23_k4_multisource.jsonl` (96 rows, K=4/5, action replay).
  f3      `measurement/f3_public_state_oracle/roots_k3_{suite,champion}.jsonl`
          (354 + 436 rows, K=3).
  synth   positions generated ON THE FLY under the ACTIVE rules profile by a
          deterministic mid-index policy.  This is the only leg that can run
          under `--rules-profile fixed_v1`: the committed corpora were generated
          `walled`, so replaying them under a different geometry produces a
          different board (the checksum guard below would — correctly — reject
          every row).  Under `fixed_v1` the `draw_rule=redraw` branch of
          `_drew_a_tile` becomes live, which is exactly what needs covering.

## The two guards that make a PASS mean something

1. **Checksum**: every replayed position is compared to the record's own
   `checksum` (`game.string_representation(board)`) before it is solved.  A
   replay that lands somewhere else is a `replay_checksum` MISMATCH, not a skip.
2. **Desync**: the Rust mirror's `string_repr()` is compared to the Python
   board's at the same ply.  A divergence is a `replay_desync` mismatch.

## Cost

The Python marginalized solver is the expensive side (it is what gates K).
`--max-k-marg` (default 3) bounds which K the marginalized comparison is run at
at all, and `--per-k` samples each (corpus, K) cell.  Everything is reported —
the JSON records exactly which cells were sampled and at what N, so a partial
run cannot be read as a full one.

## Per-job memory isolation (added 2026-08-23, after two whole-scope OOM kills)

`reconcile_exact_solver` run `run2` was OOM-killed inside its systemd scope
TWICE: first at workers=3/28G, then at workers=2/34G — dmesg showed ONE
worker's Python marginalized solve at 27.6 GB RSS and STILL GROWING (its
transposition table has no bound). Both times the WHOLE scope died, taking
every sibling worker's in-flight job with it, even though only one job was
pathological.

Each job now runs in its OWN forked subprocess with its OWN `RLIMIT_AS` cap
(`--job-mem-cap-gb`, default 26). A job that exceeds its cap dies alone —
either it raises a catchable `MemoryError` (the common case for a Python dict
blowing its bound) or the OS/allocator kills the subprocess outright (Rust's
default allocator aborts on OOM rather than raising) — and either way the
POOL WORKER that owns it survives, because the worker only forked a child and
joined it; it never allocated the memory itself. The dead job is recorded as
one extra row with `"status": "OOM_SKIPPED"` (checks=0, no mismatches — an
OOM is not a correctness finding) so `--resume` will not replan it forever,
and the run's summary reports the skip count and job keys LOUDLY — see
`run_job_capped` and the `oom_skipped`/`oom_job_keys` fields below. Set
`--job-mem-cap-gb 0` to disable isolation and go back to running jobs inline
(useful for a debugger, or for the unit tests that call `run_job` directly).

## Per-job TIME cap (added 2026-08-24, owner-authorized "2hr cutoff")

Memory is not the only way one job eats a run. On the same `run2` campaign one
job ran **9 hours** before finally hitting its memory cap (so the 9 hours bought
nothing), and a second was killed at 2 h by the operator — killed, therefore
NOT recorded, therefore replanned forever by `--resume`. `--job-time-cap-secs`
(default 0 = off; the campaign runs it at 7200) puts a hard per-job cap on the
same isolated child, and a job that blows it is RECORDED as
`"status": "TIME_SKIPPED"` — the exact shape of an `OOM_SKIPPED` row (checks=0,
zero mismatches — a timeout is not a correctness finding), so it is
resume-compatible and fail-loud in the summary, and never inflates the gate's
mismatch count.

**Mechanism, and why this one** (`_isolated_job_target` / `run_job_capped`):

* the child arms `RLIMIT_CPU` at `(cap, cap + CPU_HARD_GRACE_S)` and leaves
  `SIGXCPU` at its DEFAULT disposition, so the kernel terminates it the moment
  it burns `cap` seconds of CPU and the parent reads an **unambiguous kill
  signature**: `exitcode == -signal.SIGXCPU` (-24), which nothing else in this
  gate produces (an OOM shows up as `MemoryError`, `-SIGKILL` or `-SIGABRT`).
  These jobs are CPU-pinned at ~100 %, so CPU time ≈ wall time.
* deliberately NOT `signal.alarm`: `_timed_py_solve` already owns `SIGALRM` for
  the per-solve `--solve-timeout-s` cap and clears it in a `finally`, so a
  job-level alarm would be silently disarmed by the first Python solve.
* deliberately NOT a Python-level `SIGXCPU` handler raising an exception: a
  Python signal handler only runs at a bytecode boundary, so a child parked
  inside a long **Rust** `solve_endgame` would ignore it for as long as the
  solve lasts. Default disposition kills from Rust and Python alike.
* because there is no in-child Python exception, a timeout CANNOT fall through
  `run_job`'s broad `except Exception` into the legacy `EXCEPTION` mismatch
  path — the bug fixed at 9ca3ce44 for `MemoryError` is structurally impossible
  here. (`_JobTimeCapExceeded` exists as a `BaseException` and is re-raised at
  both of `run_job`'s chokepoints anyway, so that a future in-child timeout
  path cannot regress into that bug either.)
* the parent adds a WALL backstop (`parent_conn.poll(timeout=cap +
  WALL_GRACE_S)`) for the one case `RLIMIT_CPU` cannot see: a child blocked on
  I/O or swapping, burning wall clock without burning CPU. It SIGKILLs the
  child and records the same `TIME_SKIPPED` row with `kill_reason: "wall"`.

Every `TIME_SKIPPED` row carries `kill_reason`, `exitcode`, `child_cpu_s`
(measured via `RUSAGE_CHILDREN`, not assumed) and `elapsed_s`, so which branch
fired is auditable from the rows file alone. Like `oom_skipped`, `time_skipped`
does NOT flip the verdict: a resource cutoff is a documented hole in coverage,
not a correctness finding.

Usage:
  python scripts/rustport/reconcile_exact_solver.py --leg all --per-k 25 \\
      --workers 3 --out measurement/rustport_exact_solver
"""
from __future__ import annotations

import argparse
import functools
import json
import multiprocessing as mp
import multiprocessing.pool as mp_pool
import os
import random
import resource
import signal
import sys
import time
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# The greedy generator's policy is a `RuleBasedPlayer`, whose leaf reads the
# environment at IMPORT time — so the replay env has to be seated before any
# `carcassonne_ai` import.  This block is `endgame_regret.py`'s, verbatim: that
# is the harness of record for the l23 suite, so it is the env under which the
# corpus replays are known to reproduce.  `setdefault`, so a caller wins; the
# `checksum` guard below is what actually PROVES the choice was right.
for _k, _v in {
    "CARCASSONNE_V25_CAP": "12",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "1",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "OMP_NUM_THREADS": "1",
    "CUDA_VISIBLE_DEVICES": "",
}.items():
    os.environ.setdefault(_k, _v)

for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "level2",
           REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import carc_rs  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.rule_based_player import RuleBasedPlayer  # noqa: E402
from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402

import endgame_solver as S  # noqa: E402  (scripts/level2)

GEN_PLAYER_SEED = 70123          # gen_endgame_positions.GEN_PLAYER_SEED
GOLDEN_BUDGET = 500_000          # tests/golden/_golden_common.SOLVER_BUDGET

L23_POSITIONS = REPO / "measurement/level2/l23_positions.jsonl"
L23_K4_MULTI = REPO / "measurement/level2/l23_k4_multisource.jsonl"
F3_SUITE = REPO / "measurement/f3_public_state_oracle/roots_k3_suite.jsonl"
F3_CHAMP = REPO / "measurement/f3_public_state_oracle/roots_k3_champion.jsonl"
GOLDEN = REPO / "tests/golden/golden_fixture.json"

SOLVER_FIELDS = ("value_bits", "to_move", "optimal_actions", "child_values", "nodes")


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def ubits(x: float) -> int:
    """Raw IEEE-754 bits of a float — the only float comparison this gate makes."""
    import struct
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def k_remaining(board) -> int:
    return len(board.state.deck) + (1 if board.state.next_tile is not None else 0)


def load_jsonl(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def geometry_kwargs(game) -> dict:
    """Rust mirror geometry for a Python `Game` (`rust_agent.mirror_geometry_kwargs`).

    Under the default `walled` profile this is `{}` and the mirror is the
    engine of record; under `fixed_v1` it carries the recentred grid, the retail
    start tile, the cloister-scan fix and `draw_rule="redraw"`.
    """
    from carcassonne_ai.rust_agent import mirror_geometry_kwargs
    return mirror_geometry_kwargs(game)


def py_result_dict(res) -> dict:
    """`endgame_solver.SolveResult` in the Rust binding's wire shape."""
    return {
        "value_bits": ubits(res.value),
        "to_move": int(res.to_move),
        "optimal_actions": [int(a) for a in res.optimal_actions],
        "child_values": sorted((int(a), ubits(v)) for a, v in res.child_values.items()),
        "nodes": int(res.nodes),
    }


def rs_result_dict(d) -> dict:
    return {
        "value_bits": int(d["value_bits"]),
        "to_move": int(d["to_move"]),
        "optimal_actions": [int(a) for a in d["optimal_actions"]],
        "child_values": sorted((int(a), int(b)) for a, b in d["child_values"]),
        "nodes": int(d["nodes"]),
    }


def compare(tag: str, py: dict, rs: dict, extra: dict) -> list[dict]:
    bad = []
    for f in SOLVER_FIELDS:
        if py[f] != rs[f]:
            rec = {"tag": tag, "field": f, "py": py[f], "rs": rs[f]}
            if f == "child_values":
                # a full 50-action dump is unreadable; name the first divergence
                pv, rv = dict(py[f]), dict(rs[f])
                diff = [(a, pv.get(a), rv.get(a)) for a in sorted(set(pv) | set(rv))
                        if pv.get(a) != rv.get(a)]
                rec = {"tag": tag, "field": f, "n_diff": len(diff), "first": diff[:5]}
            rec.update(extra)
            bad.append(rec)
    return bad


# --------------------------------------------------------------------------
# seating: (python game, python board, rust mirror) in LOCKSTEP
# --------------------------------------------------------------------------

def _new_game():
    """`gen_endgame_positions._new_game` — farm scalars OFF.

    The feature tensor is the only thing that knob touches; the legal mask, the
    `string_representation` and every solver value are unaffected.  Pinned
    explicitly so a cross-harness digest comparison can never drift on it.
    """
    return Game(enable_legal_moves_cache=True)


def seat_actions(seed: int, actions, ply: int | None):
    """Replay a recorded action sequence into both implementations."""
    acts = [int(a) for a in actions]
    if ply is not None:
        acts = acts[:ply]
    random.seed(int(seed))                    # fixes the deck shuffle
    game = _new_game()
    board = game.get_init_board()
    ms = carc_rs.MirrorState.from_seed(str(int(seed)), **geometry_kwargs(game))
    for a in acts:
        board, _ = game.get_next_state(board, a)
        ms.advance(a)
    return game, board, ms


def seat_greedy(seed: int, ply: int):
    """`gen_endgame_positions.replay_to`, with the Rust mirror driven in lockstep."""
    random.seed(int(seed))
    game = _new_game()
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED)
    ms = carc_rs.MirrorState.from_seed(str(int(seed)), **geometry_kwargs(game))
    for _ in range(int(ply)):
        mask = game.get_valid_moves(board)
        a = int(player.choose_action(game, board, mask))
        board, _ = game.get_next_state(board, a)
        ms.advance(a)
    return game, board, ms


def greedy_action_prefix(seed: int, ply: int) -> list[int]:
    """The greedy generator's action sequence for game `seed`, first `ply` moves.

    `RuleBasedPlayer.choose_action` is BY FAR the most expensive thing in this
    gate — it evaluates every legal move with the object leaf, ~140 times per
    position.  The l23 suite stores five rows per seed (one per K), so paying
    that walk once per SEED and replaying the recorded actions for each row is a
    5x saving on the dominant cost; `seat_actions` then reproduces the exact
    same board (the checksum guard proves it).
    """
    random.seed(int(seed))
    game = _new_game()
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEN_PLAYER_SEED)
    acts: list[int] = []
    for _ in range(int(ply)):
        mask = game.get_valid_moves(board)
        a = int(player.choose_action(game, board, mask))
        acts.append(a)
        board, _ = game.get_next_state(board, a)
    return acts


def seat_midindex(seed: int, k_target: int, max_plies: int = 400):
    """Walk a fresh game with a deterministic mid-index policy to `k_target`.

    No RNG, no leaf — so the position depends only on (deck seed, rules
    profile), which is what the `synth` leg needs in order to be meaningful
    under a profile the committed corpora were never generated under.
    """
    random.seed(int(seed))
    game = _new_game()
    board = game.get_init_board()
    ms = carc_rs.MirrorState.from_seed(str(int(seed)), **geometry_kwargs(game))
    for _ in range(max_plies):
        if (board.state.phase == GamePhase.TILES
                and k_remaining(board) <= k_target
                and board.state.next_tile is not None):
            return game, board, ms
        legal = np.flatnonzero(game.get_valid_moves(board))
        if len(legal) == 0:
            return None
        a = int(legal[len(legal) // 2])
        board, _ = game.get_next_state(board, a)
        ms.advance(a)
    return None


# --------------------------------------------------------------------------
# one position, both modes, both implementations
# --------------------------------------------------------------------------

class _PySolveTimeout(Exception):
    """The PYTHON oracle blew its wall cap — a SKIP, never a mismatch.

    The cap exists because the oracle's cost explodes with K (measured: ~4.5 s
    at K=2, ~122 s at K=3, and hours at K=4), and an un-capped K=4 row would
    park a worker for the length of the run.  It applies to the PYTHON side
    ONLY: a Rust solve that outran the budget while Python finished is a real
    divergence and is reported as one.
    """


class _JobTimeCapExceeded(BaseException):
    """A whole JOB blew its `--job-time-cap-secs` cap — a SKIP, never a mismatch.

    Distinct from `_PySolveTimeout` above, which caps ONE Python solve and is a
    per-cell skip inside an otherwise healthy job; this caps the entire job and
    discards it.

    Derives from `BaseException`, not `Exception`, ON PURPOSE: the failure mode
    fixed at 9ca3ce44 was a resource-limit signal (`MemoryError`) being caught
    by a broad `except Exception` and recorded as a fabricated correctness
    mismatch.  A `BaseException` cannot be caught that way by `run_job`'s
    firewall, by `check_position`, or by anything inside `endgame_solver`, so
    the misclassification is impossible by construction rather than by
    remembering to add a re-raise clause at every layer (they are added anyway).

    NOTE: the shipped mechanism (see the module docstring) kills the isolated
    child from the kernel via `RLIMIT_CPU`/`SIGXCPU`, so in production this
    exception is never actually raised — the parent classifies from the child's
    exit signature.  It is kept as the typed contract for the in-child path.
    """


def _timed_py_solve(game, board, mode, budget, ab, cap_s: int):
    if cap_s <= 0:
        return S.solve(game, board, mode, budget=budget, alphabeta=ab)
    import signal as _sig

    def _fire(*_):
        raise _PySolveTimeout()

    old = _sig.signal(_sig.SIGALRM, _fire)
    _sig.alarm(cap_s)
    try:
        return S.solve(game, board, mode, budget=budget, alphabeta=ab)
    finally:
        _sig.alarm(0)
        _sig.signal(_sig.SIGALRM, old)


def check_position(tag: str, game, board, ms, *, budget: int, modes, extra: dict,
                   solve_timeout_s: int = 0) -> dict:
    """Solve one position on both sides in every requested mode."""
    out = {"checks": 0, "skipped": 0, "mismatches": [], "cells": {}}
    if game.string_representation(board) != ms.string_repr():
        out["mismatches"].append({"tag": tag, "field": "replay_desync", **extra})
        return out
    for mode, ab in modes:
        # K-TAGGED: "how many positions did this gate actually compare at each
        # K" is the number a reader needs, and an untagged cell name cannot
        # answer it from the rows file alone.
        cell = f"k{extra.get('k', '?')}:{mode}{'+ab' if ab else ''}"
        try:
            py = _timed_py_solve(game, board, mode, budget, ab, solve_timeout_s)
        except (S.BudgetExceeded, _PySolveTimeout):
            out["skipped"] += 1
            out["cells"][cell] = out["cells"].get(cell, 0)
            continue
        rs = ms.solve_endgame(mode=mode, budget=budget, alphabeta=ab)
        if rs is None:
            # Python completed inside the budget and Rust did not: the node
            # counts have diverged, which IS the failure this gate hunts.
            out["mismatches"].append(
                {"tag": tag, "field": "rust_budget_exceeded", "cell": cell,
                 "py_nodes": int(py.nodes), **extra})
            continue
        out["mismatches"].extend(
            compare(tag, py_result_dict(py), rs_result_dict(rs), {"cell": cell, **extra}))
        out["checks"] += 1
        out["cells"][cell] = out["cells"].get(cell, 0) + 1
    return out


def blank() -> dict:
    # `oom_skipped`/`oom_job_keys` and `time_skipped`/`time_job_keys` are
    # additive, like the resume bookkeeping fields below — a row written by an
    # OLDER version of this script simply lacks them, and
    # `merge()`/`rebuild_from_rows()` read them with `.get(..., default)`, so
    # old rows stay valid without a rewrite.  That matters concretely here:
    # the live `run2` rows file already holds 121 rows written before the time
    # cap existed, and a resume must keep reading them.
    return {"checks": 0, "skipped": 0, "positions": 0, "mismatches": [], "cells": {},
            "oom_skipped": 0, "oom_job_keys": [],
            "time_skipped": 0, "time_job_keys": []}


def merge(dst: dict, src: dict) -> None:
    dst["checks"] += src.get("checks", 0)
    dst["skipped"] += src.get("skipped", 0)
    dst["positions"] += src.get("positions", 0)
    dst["mismatches"].extend(src.get("mismatches", []))
    dst["oom_skipped"] = dst.get("oom_skipped", 0) + src.get("oom_skipped", 0)
    dst.setdefault("oom_job_keys", []).extend(src.get("oom_job_keys", []))
    dst["time_skipped"] = dst.get("time_skipped", 0) + src.get("time_skipped", 0)
    dst.setdefault("time_job_keys", []).extend(src.get("time_job_keys", []))
    for k, v in src.get("cells", {}).items():
        dst["cells"][k] = dst["cells"].get(k, 0) + v


# --------------------------------------------------------------------------
# jobs
# --------------------------------------------------------------------------

def modes_for(k: int, limits: dict) -> list[tuple[str, bool]]:
    """Which (mode, alphabeta) cells to run at this K, given the cost knobs.

    Both clairvoyant paths are compared — the no-prune oracle AND alpha-beta —
    because they are different code with different TT contents, and a port can
    be right on one and wrong on the other.
    """
    ms: list[tuple[str, bool]] = []
    if k <= limits["max_k_clair_noprune"]:
        ms.append(("clairvoyant", False))
    if k <= limits["max_k_clair"]:
        ms.append(("clairvoyant", True))
    if k <= limits["max_k_marg"]:
        ms.append(("marginalized", False))
    return ms


def run_job(job: dict) -> dict:
    """Exception-firewalled: one bad position must not kill the batch."""
    out = blank()
    try:
        kind = job["kind"]
        if kind == "golden":
            out = job_golden(job)
        elif kind == "corpus":
            out = job_corpus(job)
        elif kind == "synth":
            out = job_synth(job)
        elif kind == "v2":
            out = job_v2(job)
        else:
            raise ValueError(f"unknown job kind {kind!r}")
    except _JobTimeCapExceeded:
        # Same contract as the MemoryError clause below, for the per-job WALL
        # cap (`--job-time-cap-secs`): a cutoff is a TIME_SKIPPED row, never an
        # `EXCEPTION` mismatch.  Belt AND braces: `_JobTimeCapExceeded` derives
        # from `BaseException` precisely so that no broad `except Exception`
        # anywhere in the solver call tree (here, in `check_position`, or deep
        # inside `endgame_solver`) can swallow it in the first place — this
        # clause is the explicit, greppable statement of the rule so that
        # re-parenting the class later cannot silently reintroduce 9ca3ce44's
        # bug.  In the shipped mechanism the child is killed by the kernel and
        # this exception never fires; it exists for any future in-child
        # timeout path.
        raise
    except MemoryError:
        # MUST propagate, never become a mismatch row (fixed 2026-08-24, after
        # job corpus:l23:l23_positions:3200000129's OOM — hit its RLIMIT_AS
        # cap deep in the solver call tree, `job_corpus` -> `check_position`
        # -> `_timed_py_solve` -> `endgame_solver._value_ab` (recursing) ->
        # `_key` -> `game_wrapper.string_representation` — surfaced through
        # THIS `except Exception` below, and got recorded as an EXCEPTION
        # mismatch instead of OOM_SKIPPED, falsely inflating the gate's
        # mismatch count. `run_job` is always called from inside
        # `_isolated_job_target` in production (workers>1 or workers=1 with
        # `--job-mem-cap-gb` > 0, i.e. every real run — see `run_job_capped`),
        # whose OWN `except MemoryError` clause exists specifically to catch
        # this and report it as OOM_SKIPPED via `_oom_row`. That clause is
        # dead code unless this one re-raises rather than swallows. When
        # isolation is OFF (`--job-mem-cap-gb 0`, the debugger/unit-test path)
        # or `run_job` is called directly, this simply propagates as a real
        # MemoryError — the honest signal, and the pre-existing behavior for
        # that path is unchanged.
        raise
    except Exception as exc:  # noqa: BLE001 — a crash IS a mismatch here
        import traceback
        out = blank()
        out["mismatches"].append({
            "tag": job.get("tag", "?"), "field": "EXCEPTION",
            "error": f"{type(exc).__name__}: {exc}",
            "tb": traceback.format_exc()[-1500:],
        })
    out["leg"] = job["leg"]
    # Identity, so an interrupted run can be resumed job-by-job rather than
    # only rebuilt as a partial. Additive: `merge()` reads only the counter
    # keys, and `rebuild_from_rows` pops `leg` and ignores everything else.
    # Defensive like the body above: a row that cannot be keyed still has to be
    # RECORDED (it carries a mismatch), so keying must never raise here — EXCEPT
    # a MemoryError, which must keep propagating for the same reason as above
    # (job_key() is cheap and unlikely to be where a cap is actually hit, but
    # if it somehow is, it is still an OOM, never a fabricated UNKEYABLE row).
    try:
        out["job_key"] = job_key(job)
    except _JobTimeCapExceeded:
        raise
    except MemoryError:
        raise
    except Exception:  # noqa: BLE001
        out["job_key"] = f"UNKEYABLE:{job.get('kind')!r}:{job.get('tag', '?')}"
    return out


# --------------------------------------------------------------------------
# per-job memory isolation
# --------------------------------------------------------------------------
#
# `run_job` above is already exception-firewalled against ordinary Python
# exceptions — a bad position becomes an `EXCEPTION` mismatch, never a dead
# pool worker.  It CANNOT firewall against unbounded memory growth: a
# transposition table that keeps growing past what the box can hold gets the
# whole PROCESS killed (by the kernel OOM-killer, or — under an outer
# systemd-run scope, which is how this gate is launched — the cgroup's
# MemoryMax), and multiprocessing.Pool's `imap_unordered` has no way to tell
# "one worker died" from "the whole run died" from the consumer side. That is
# exactly what happened twice (see the module docstring's "Per-job memory
# isolation" section).
#
# The fix is to give each JOB — not each pool worker, which serves many jobs
# in sequence — its own address-space cap, in its own subprocess, so a job
# that blows the cap dies ALONE and the pool worker that forked it (and never
# itself allocated the memory) lives to serve the next job.


# How much CPU grace the child gets between the RLIMIT_CPU SOFT limit (which
# terminates it via SIGXCPU, the signature the parent classifies on) and the
# HARD limit (SIGKILL, uncatchable).  Only reachable if SIGXCPU were somehow
# blocked; it is a backstop, not the mechanism.
CPU_HARD_GRACE_S = 60
# How much WALL grace the PARENT gives beyond the job's CPU cap before it
# SIGKILLs the child itself.  This is the branch that catches a child burning
# wall clock without burning CPU (blocked on I/O, swapping) — RLIMIT_CPU is
# blind to that.  Module-level so the tests can shrink it.
WALL_GRACE_S = 120


def _arm_job_caps(cap_bytes: int, time_cap_secs: int) -> None:
    """Arm this (already forked) process's per-job resource caps.

    Each cap is armed independently: a box that refuses one must still get the
    other.  Both fail OPEN (a cap that cannot be set is a cap that cannot be
    enforced) — for the time cap the parent's wall backstop still applies, so
    failing open here is not the same as having no cutoff at all.
    """
    if cap_bytes > 0:
        try:
            resource.setrlimit(resource.RLIMIT_AS, (cap_bytes, cap_bytes))
        except (ValueError, OSError):
            pass
    if time_cap_secs > 0:
        try:
            # SIGXCPU's default action is terminate-with-core, and a core dump
            # of a 30 GB solver child would be catastrophic on a box that is
            # already short of disk.  Refuse the core, keep the termination.
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (ValueError, OSError):
            pass
        try:
            # SOFT = the cap (SIGXCPU, default disposition => the child dies
            # here, and `exitcode == -SIGXCPU` is the parent's signature).
            # HARD = cap + grace (SIGKILL) purely as a backstop.
            resource.setrlimit(
                resource.RLIMIT_CPU,
                (int(time_cap_secs), int(time_cap_secs) + CPU_HARD_GRACE_S))
        except (ValueError, OSError):
            pass


def _isolated_job_target(job: dict, cap_bytes: int, conn,
                         time_cap_secs: int = 0) -> None:
    """Runs in a freshly forked child: cap this process's address space AND its
    CPU time, run the job, and report back over the pipe. Never raises past
    this function — an uncaught exception here would leave the parent's
    `poll()` waiting on a pipe the child closes without sending anything, which
    the parent already reads correctly as an OOM-shaped death, but a real
    (non-memory) crash should say so honestly rather than pretend to be an OOM.

    The TIME cap is enforced by the kernel, not by this function: `RLIMIT_CPU`
    is armed above and SIGXCPU keeps its default disposition, so a job over the
    cap is terminated wherever it is — including inside a multi-hour Rust
    `solve_endgame`, where a Python-level signal handler would never get to
    run.  The `except _JobTimeCapExceeded` clause below therefore does not fire
    in production; it is the typed in-child path, kept symmetric with the
    `except MemoryError`/`"OOM"` path so a future in-child cutoff cannot land
    anywhere but `TIME_SKIPPED`.
    """
    _arm_job_caps(cap_bytes, time_cap_secs)
    try:
        result = run_job(job)
    except _JobTimeCapExceeded:
        try:
            conn.send(("TIMEOUT", None))
        except Exception:  # noqa: BLE001 — the pipe itself may be gone
            pass
        return
    except MemoryError:
        # The common case: a Python dict/list allocation hit the RLIMIT_AS
        # ceiling cleanly and CPython raised, rather than the OS killing the
        # process outright. Report it as the same OOM shape either way — the
        # parent tells cap_bytes and job identity, this just says "hit it".
        try:
            conn.send(("OOM", None))
        except Exception:  # noqa: BLE001 — the pipe itself may be gone
            pass
        return
    except Exception as exc:  # noqa: BLE001 — a crash here must not vanish
        try:
            conn.send(("ERROR", f"{type(exc).__name__}: {exc}"))
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        conn.send(("OK", result))
    except Exception:  # noqa: BLE001 — result too big to pickle etc: treat
        # like any other child-side failure; the parent's poll+EOF path below
        # will read this as a dead child with no usable payload.
        pass


class _NoDaemonProcess(mp.get_context("fork").Process):
    """A fork-context `Process` whose `daemon` flag is pinned to `False`.

    `run_job_capped` needs to fork a per-job child FROM WITHIN a pool worker,
    but `multiprocessing.pool.Pool` creates its own workers as daemon
    processes, and daemon processes are hard-blocked from having children —
    `AssertionError: daemonic processes are not allowed to have children`,
    raised at `Process.start()`, unconditionally. Without this, `run_job_capped`
    would ALWAYS hit that assertion when called from a pool worker (every
    real run, since `--workers 1` is not the production path) and its own
    `except Exception: return run_job(job)` fallback would swallow it and
    fail OPEN — every job would run uncapped and isolation would silently do
    nothing. Measured, not assumed: this exact failure mode was caught by
    `test_pool_survives_one_oom_job_among_several` before this class existed.
    """
    @property
    def daemon(self) -> bool:
        return False

    @daemon.setter
    def daemon(self, value) -> None:
        pass  # refuse to become a daemon, whatever Pool asks for


class _NoDaemonForkContext(type(mp.get_context("fork"))):
    Process = _NoDaemonProcess


class NestablePool(mp_pool.Pool):
    """`multiprocessing.pool.Pool`, but its own workers are NOT daemons.

    The standard, widely-used recipe for a pool whose workers may themselves
    hold child processes (ours do: one isolated grandchild per job). Every
    other `Pool` behavior (task queue, `imap_unordered`, worker respawn on
    `maxtasksperchild`) is untouched — this only changes the ONE flag that
    blocks nesting.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("context", _NoDaemonForkContext())
        super().__init__(*args, **kwargs)


def _row_key(job: dict) -> str:
    """`job_key(job)`, with the UNKEYABLE fallback both skip-row builders use.

    A row that cannot be keyed still has to be RECORDED (it documents a hole in
    coverage), so keying must never raise out of a skip-row builder.
    """
    try:
        return job_key(job)
    except Exception:  # noqa: BLE001
        return f"UNKEYABLE:{job.get('kind')!r}:{job.get('tag', '?')}"


def _oom_row(job: dict, cap_bytes: int, exitcode) -> dict:
    """The recorded row for a job that died to its memory cap (or crashed
    without sending anything usable — same shape, see `run_job_capped`)."""
    out = blank()
    out["leg"] = job.get("leg", "?")
    out["job_key"] = _row_key(job)
    out["status"] = "OOM_SKIPPED"
    out["cap_bytes"] = cap_bytes
    out["exitcode"] = exitcode
    out["oom_skipped"] = 1
    out["oom_job_keys"] = [out["job_key"]]
    return out


def _time_row(job: dict, time_cap_secs: int, exitcode, kill_reason: str,
              elapsed_s: float | None = None,
              child_cpu_s: float | None = None) -> dict:
    """The recorded row for a job cut off by its WALL cap.

    Deliberately the SAME shape as `_oom_row`: recorded (so `--resume` never
    replans it), keyed, zero checks, zero mismatches — a cutoff is a resource
    limitation, not a correctness finding, and must never inflate the gate's
    mismatch count (the 9ca3ce44 lesson).  `kill_reason`/`exitcode`/
    `child_cpu_s`/`elapsed_s` record WHICH branch fired so the classification
    is auditable from the rows file alone:

      "rlimit_cpu"  the child burned `time_cap_secs` of CPU and the kernel
                    terminated it with SIGXCPU (`exitcode == -24`)
      "cpu_budget"  the child died by some other signal having ALREADY spent
                    its whole CPU budget (measured via RUSAGE_CHILDREN) — the
                    RLIMIT_CPU hard-limit SIGKILL backstop
      "wall"        the parent's wall-clock backstop SIGKILLed a child that was
                    over its deadline without burning the CPU to prove it
    """
    out = blank()
    out["leg"] = job.get("leg", "?")
    out["job_key"] = _row_key(job)
    out["status"] = "TIME_SKIPPED"
    out["time_cap_secs"] = time_cap_secs
    out["kill_reason"] = kill_reason
    out["exitcode"] = exitcode
    if elapsed_s is not None:
        out["elapsed_s"] = round(float(elapsed_s), 1)
    if child_cpu_s is not None:
        out["child_cpu_s"] = round(float(child_cpu_s), 1)
    out["time_skipped"] = 1
    out["time_job_keys"] = [out["job_key"]]
    return out


def _children_cpu_s() -> float:
    """Total CPU seconds this process's REAPED children have consumed.

    Differenced across one `start()`/`join()` it is that child's own CPU time —
    measured, not inferred from wall clock.  Jobs run one-at-a-time inside a
    given pool worker, so nothing else lands in the delta.
    """
    ru = resource.getrusage(resource.RUSAGE_CHILDREN)
    return float(ru.ru_utime) + float(ru.ru_stime)


def run_job_capped(job: dict, cap_bytes: int, time_cap_secs: int = 0) -> dict:
    """`run_job(job)`, isolated in its own subprocess under an RLIMIT_AS cap
    and an RLIMIT_CPU (wall) cap.

    Both caps off (`cap_bytes <= 0` and `time_cap_secs <= 0`) disables
    isolation entirely and calls `run_job` inline — the pre-2026-08-23
    behavior, kept for the unit tests and for a debugger session where
    subprocess isolation just gets in the way.  Either cap ON forks a child:
    a time cap cannot be enforced inline without killing the pool worker that
    owns the job.

    Detects an OOM three ways, because a runaway allocation can fail in any
    of them depending on WHERE it happens (measured, not assumed — see the
    three-mode probe in the commit that added this):
      1. the child raises `MemoryError` and says so cleanly (`_isolated_job_target`)
      2. the child is killed by a signal (SIGKILL from the OOM-killer, SIGABRT
         from Rust's default alloc-error handler, ...) — `proc.exitcode < 0`
      3. the child's write end of the pipe closes without ever sending
         anything (any of the above, or a segfault) — `conn.poll()` returns
         True and `conn.recv()` raises `EOFError`
    Cases 2 and 3 are folded into the same OOM_SKIPPED row: from the outside,
    "died before reporting, while capped" IS what an OOM job looks like, and
    a job dying for some OTHER hard-crash reason while under a memory cap is
    not a distinction this gate needs to make — `run_job`'s own exception
    firewall already reports every recoverable failure as a normal mismatch,
    so anything reaching this path is, by construction, not recoverable.
    """
    time_cap_secs = int(time_cap_secs or 0)
    if cap_bytes <= 0 and time_cap_secs <= 0:
        return run_job(job)

    ctx = mp.get_context("fork")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_isolated_job_target,
                       args=(job, cap_bytes, child_conn, time_cap_secs))
    cpu0 = _children_cpu_s()
    t0 = time.time()
    try:
        proc.start()
    except Exception:  # noqa: BLE001 — could not even fork (e.g. box out of
        # memory for the fork itself): the isolation layer failed open, so
        # fall back to running the job inline rather than losing it silently.
        # NOTE the time cap is NOT enforced on this fallback path: arming
        # RLIMIT_CPU here would cap the POOL WORKER, not the job, and killing
        # the worker is exactly what isolation exists to avoid. A fork failure
        # is already an exceptional, loud condition.
        parent_conn.close()
        child_conn.close()
        try:
            return run_job(job)
        except _JobTimeCapExceeded:
            # Cannot happen on this path today (nothing arms an in-child
            # timeout inline), but if it ever does it is a TIME_SKIPPED row for
            # the same reason the MemoryError clause below is an OOM one:
            # letting it propagate would kill the pool worker.
            return _time_row(job, time_cap_secs, None, "inline_fallback")
        except MemoryError:
            # Couldn't even fork a child to isolate this job — itself often a
            # symptom of memory pressure — AND the inline fallback then also
            # hit the wall. Still an OOM, not a correctness mismatch, and
            # letting this propagate uncaught here would crash the POOL
            # WORKER (unlike the isolated-child path, there is no subprocess
            # boundary to contain it), taking every in-flight sibling job's
            # `imap_unordered` iteration down with it.
            return _oom_row(job, cap_bytes, None)
    child_conn.close()  # only the child should hold the write end open

    # WALL BACKSTOP: RLIMIT_CPU is blind to a child that is over its deadline
    # without burning CPU (blocked on I/O, or thrashing swap). Give the kernel
    # cap first crack — it produces the clean `-SIGXCPU` signature — and only
    # step in `WALL_GRACE_S` later.
    wall_cap = (time_cap_secs + WALL_GRACE_S) if time_cap_secs > 0 else None
    status, payload = None, None
    wall_timeout = False
    try:
        if parent_conn.poll(timeout=wall_cap):
            try:
                status, payload = parent_conn.recv()
            except EOFError:
                status = "EOF"
        elif wall_cap is not None:
            wall_timeout = True
    finally:
        parent_conn.close()
    if wall_timeout:
        try:
            proc.kill()
        except Exception:  # noqa: BLE001 — already gone is fine
            pass
        proc.join(timeout=30)
    else:
        proc.join()
    elapsed_s = time.time() - t0
    child_cpu_s = max(0.0, _children_cpu_s() - cpu0)

    if wall_timeout:
        return _time_row(job, time_cap_secs, proc.exitcode, "wall",
                         elapsed_s, child_cpu_s)
    if status == "OK":
        return payload
    if status == "TIMEOUT":
        # The typed in-child path (see `_isolated_job_target`). Not reachable
        # with the shipped kernel-kill mechanism; classified first regardless,
        # so it can never fall through to the OOM row below.
        return _time_row(job, time_cap_secs, proc.exitcode, "in_child",
                         elapsed_s, child_cpu_s)
    if status == "ERROR":
        # A real (non-memory) crash inside the isolated child. Still record
        # it — as a mismatch, matching what `run_job`'s own firewall would
        # have produced had the exception fired outside isolation — rather
        # than folding it into OOM_SKIPPED, which would misreport a genuine
        # bug as a resource limitation.
        out = blank()
        out["leg"] = job.get("leg", "?")
        out["job_key"] = _row_key(job)
        out["mismatches"].append({
            "tag": job.get("tag", out["job_key"]), "field": "EXCEPTION",
            "error": f"isolated child: {payload}"})
        return out
    # TIME before OOM: a child killed by SIGXCPU is UNAMBIGUOUSLY the CPU cap
    # (nothing else in this gate raises that signal), and a child killed by
    # anything else having already spent its whole CPU budget is the RLIMIT_CPU
    # hard-limit SIGKILL backstop. Both would otherwise be swallowed by the
    # `died without a payload => OOM` rule below and misreported as memory.
    if time_cap_secs > 0 and status in (None, "EOF"):
        if proc.exitcode == -int(signal.SIGXCPU):
            return _time_row(job, time_cap_secs, proc.exitcode, "rlimit_cpu",
                             elapsed_s, child_cpu_s)
        if proc.exitcode is not None and proc.exitcode < 0 \
                and child_cpu_s >= time_cap_secs:
            return _time_row(job, time_cap_secs, proc.exitcode, "cpu_budget",
                             elapsed_s, child_cpu_s)
    # status in ("OOM", "EOF", None): the child hit the cap, was killed, or
    # otherwise died without a usable payload — all the same OOM shape.
    return _oom_row(job, cap_bytes, proc.exitcode)


def job_golden(job: dict) -> dict:
    """Rust vs the FROZEN disk block, and Rust vs a live Python re-solve."""
    out = blank()
    pos, actions = job["pos"], job["actions"]
    tag = f"golden#{pos['id']}(seed{pos['seed']},ply{pos['ply']},k{pos['k']})"
    game, board, ms = seat_actions(pos["seed"], actions, pos["ply"])
    out["positions"] = 1
    if game.string_representation(board) != ms.string_repr():
        out["mismatches"].append({"tag": tag, "field": "replay_desync"})
        return out
    rs = ms.solve_endgame(mode="marginalized", budget=GOLDEN_BUDGET, alphabeta=False)
    if rs is None:
        out["mismatches"].append({"tag": tag, "field": "rust_budget_exceeded"})
        return out
    frozen = pos["solver"]
    # frozen-vs-rust: the fixture stores a decimal value, so this leg compares
    # value at 1e-9 and the SET + node count exactly.
    if abs(float(frozen["value"]) - float(rs["value"])) > 1e-9:
        out["mismatches"].append({"tag": tag, "field": "frozen_value",
                                  "py": frozen["value"], "rs": rs["value"]})
    if [int(a) for a in frozen["optimal_actions"]] != [int(a) for a in rs["optimal_actions"]]:
        out["mismatches"].append({"tag": tag, "field": "frozen_optimal_actions",
                                  "py": frozen["optimal_actions"],
                                  "rs": rs["optimal_actions"]})
    if int(frozen["nodes"]) != int(rs["nodes"]):
        out["mismatches"].append({"tag": tag, "field": "frozen_nodes",
                                  "py": frozen["nodes"], "rs": rs["nodes"]})
    out["checks"] += 1
    out["cells"]["frozen_marginalized"] = 1
    # live python re-solve, full bit comparison including child_values
    py = S.solve(game, board, "marginalized", budget=GOLDEN_BUDGET, alphabeta=False)
    out["mismatches"].extend(
        compare(tag, py_result_dict(py), rs_result_dict(rs), {"cell": "live_marginalized"}))
    out["checks"] += 1
    out["cells"]["live_marginalized"] = 1
    return out


def job_v2(job: dict) -> dict:
    """V2 — at K=1 clairvoyant == marginalized, on both sides and cross-wise."""
    out = blank()
    pos, actions = job["pos"], job["actions"]
    tag = f"v2#{pos['id']}(seed{pos['seed']},ply{pos['ply']})"
    game, board, ms = seat_actions(pos["seed"], actions, pos["ply"])
    out["positions"] = 1
    pc = py_result_dict(S.solve(game, board, "clairvoyant", budget=GOLDEN_BUDGET))
    pm = py_result_dict(S.solve(game, board, "marginalized", budget=GOLDEN_BUDGET))
    rc = rs_result_dict(ms.solve_endgame(mode="clairvoyant", budget=GOLDEN_BUDGET))
    rm = rs_result_dict(ms.solve_endgame(mode="marginalized", budget=GOLDEN_BUDGET))
    # the V2 identity, on each implementation independently...
    for name, a, b in (("py_clair_vs_marg", pc, pm), ("rs_clair_vs_marg", rc, rm)):
        for f in ("value_bits", "optimal_actions", "child_values"):
            if a[f] != b[f]:
                out["mismatches"].append({"tag": tag, "field": name + ":" + f})
        out["checks"] += 1
        out["cells"][name] = out["cells"].get(name, 0) + 1
    # ...and across them
    out["mismatches"].extend(compare(tag, pc, rc, {"cell": "v2_clairvoyant"}))
    out["mismatches"].extend(compare(tag, pm, rm, {"cell": "v2_marginalized"}))
    out["checks"] += 2
    for c in ("v2_clairvoyant", "v2_marginalized"):
        out["cells"][c] = out["cells"].get(c, 0) + 1
    return out


def job_corpus(job: dict) -> dict:
    """One job = every sampled row of ONE (source, seed) — see `greedy_action_prefix`."""
    out = blank()
    src, args, recs = job["source"], job["args"], job["recs"]
    prefix = None
    if not job["has_actions"]:
        prefix = greedy_action_prefix(job["seed"], max(int(r["ply"]) for r in recs))
    for rec in recs:
        tag = f"{src}:k{rec['k_remaining']}(seed{job['seed']},ply{rec['ply']})"
        if src == "l23_k4_multisource":
            # gen_endgame_multisource.replay_actions replays the WHOLE list (the
            # recorded sequence is already truncated to the root).
            game, board, ms = seat_actions(rec["seed"], rec["actions"], None)
        elif job["has_actions"]:
            # roots_k3_champion — root_replay.replay_actions(deck_seed, actions, ply)
            game, board, ms = seat_actions(rec["deck_seed"], rec["actions"], rec["ply"])
        else:
            game, board, ms = seat_actions(job["seed"], prefix, int(rec["ply"]))
        out["positions"] += 1
        if game.string_representation(board) != rec["checksum"]:
            out["mismatches"].append({"tag": tag, "field": "replay_checksum"})
            continue
        k = k_remaining(board)
        if k != int(rec["k_remaining"]):
            out["mismatches"].append({"tag": tag, "field": "replay_k",
                                      "py": k, "rec": int(rec["k_remaining"])})
            continue
        merge(out, check_position(tag, game, board, ms, budget=args["budget"],
                                  modes=modes_for(k, job["modes_args"]),
                                  extra={"k": k},
                                  solve_timeout_s=args["solve_timeout_s"]))
    return out


def job_synth(job: dict) -> dict:
    out = blank()
    seat = seat_midindex(job["seed"], job["k"])
    if seat is None:
        out["mismatches"].append({"tag": job["tag"], "field": "synth_unreachable"})
        return out
    game, board, ms = seat
    out["positions"] = 1
    k = k_remaining(board)
    merge(out, check_position(job["tag"], game, board, ms, budget=job["args"]["budget"],
                              modes=job["modes"], extra={"k": k, "profile": job["profile"]},
                              solve_timeout_s=job["args"]["solve_timeout_s"]))
    return out


# --------------------------------------------------------------------------
# job building
# --------------------------------------------------------------------------

def sample(rows: list, n: int, seed: int) -> list:
    """Deterministic sub-sample — reproducible across runs and boxes."""
    if n <= 0 or n >= len(rows):
        return list(rows)
    rng = random.Random(seed)
    idx = sorted(rng.sample(range(len(rows)), n))
    return [rows[i] for i in idx]


def cell_seed(source: str, k: int) -> int:
    """Stable per-(corpus, K) sampling seed.

    ⚠️ FIXED 2026-08-23. This used to be `abs(hash((source, k))) % 100_000`,
    which does NOT honour the contract `sample()` advertises ("reproducible
    across runs and boxes"): CPython salts `hash()` of a str per PROCESS unless
    PYTHONHASHSEED is pinned, so every invocation drew a DIFFERENT sub-sample.

    Measured, not reasoned — the same `--leg all --per-k 25` plan built under
    four hash seeds yields 179 / 186 / 182 / 177 jobs (jobs are grouped by deck
    seed, so a different row sample is a different job COUNT). That is exactly
    why the historical logs disagree with each other: the 2026-08-17 partial
    logged `jobs=186` and the 2026-08-19 run logged `jobs=179` from identical
    arguments on the same box.

    The consequence that forced the fix: a gate whose job set is not
    reproducible cannot be RESUMED (see `--resume`), and this gate is a
    multi-hour run that has now been killed twice mid-flight.

    `zlib.crc32` is stable across processes, boxes and Python versions. The
    seeds it produces differ from any given hash-salted draw, so the sampled
    population changes — that is a change of WHICH rows are compared, never of
    what a comparison means, and no banked verdict is retroactively affected
    (`G7_exact_solver_main.json` etc. are already written and keep their own
    recorded `args`).
    """
    return zlib.crc32(f"{source}\x00{k}".encode()) % 100_000


def job_key(job: dict) -> str:
    """Stable identity for one job — the unit `--resume` skips.

    It must be derivable identically at plan time and from a recorded row, and
    must not collide between two jobs that do different work.
    """
    kind = job["kind"]
    if kind in ("golden", "v2"):
        pos = job["pos"]
        return f"{kind}:{pos['seed']}:k{pos['k']}"
    if kind == "corpus":
        return f"corpus:{job['leg']}:{job['source']}:{job['seed']}"
    if kind == "synth":
        return f"synth:{job['tag']}"
    raise ValueError(f"unknown job kind {kind!r}")


def recorded_job_keys(rows_path: Path) -> set[str]:
    """The job keys already present in an incremental rows file.

    Fails LOUDLY on a rows file written before job keys existed: silently
    treating an unkeyed row as "nothing recorded" would re-run work the file
    already paid for, and silently treating it as "everything recorded" would
    skip comparisons that never ran. Neither is an honest resume.
    """
    keys: set[str] = set()
    unkeyed = 0
    for line in rows_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        k = row.get("job_key")
        if k is None:
            unkeyed += 1
        else:
            keys.add(k)
    if unkeyed:
        raise SystemExit(
            f"--resume: {rows_path} has {unkeyed} row(s) with no `job_key` "
            f"(written before 2026-08-23). A resume cannot tell which jobs "
            f"they were. Move the file aside and start a fresh rows file, or "
            f"rebuild the partial verdict from it with --from-rows.")
    return keys


def build_jobs(args) -> list[dict]:
    legs = set(args.leg)
    if "all" in legs:
        legs = {"golden", "v2", "l23", "f3", "synth"}
    jobs: list[dict] = []
    argd = {"budget": args.budget, "solve_timeout_s": args.solve_timeout_s}
    limits = {"max_k_clair": args.max_k_clair,
              "max_k_clair_noprune": args.max_k_clair_noprune,
              "max_k_marg": args.max_k_marg}

    if legs & {"golden", "v2"}:
        fx = json.loads(GOLDEN.read_text())
        games = fx["games"]
        solver_pos = [p for p in fx["positions"] if p.get("solver")]
        for p in solver_pos:
            acts = games[str(p["seed"])]["actions"]
            if "golden" in legs:
                jobs.append({"kind": "golden", "leg": "golden", "pos": p, "actions": acts})
            if "v2" in legs and int(p["k"]) == 1:
                jobs.append({"kind": "v2", "leg": "v2", "pos": p, "actions": acts})

    def corpus_jobs(path: Path, source: str, leg: str) -> None:
        rows = load_jsonl(path)
        has_actions = "actions" in rows[0]
        by_k: dict[int, list] = {}
        for r in rows:
            by_k.setdefault(int(r["k_remaining"]), []).append(r)
        picked: list[dict] = []
        for k in sorted(by_k):
            if k > args.max_k or not modes_for(k, limits):
                continue
            # deterministic sub-sample, seeded by the CELL so a re-run picks the
            # same rows on any box
            picked += sample(by_k[k], args.per_k, seed=cell_seed(source, k))
        # Group by seed: one greedy walk serves every K of that game.
        by_seed: dict[int, list] = {}
        for r in picked:
            by_seed.setdefault(int(r.get("seed", r.get("deck_seed"))), []).append(r)
        for seed, recs in sorted(by_seed.items()):
            jobs.append({"kind": "corpus", "leg": leg, "source": source,
                         "seed": seed, "recs": recs, "has_actions": has_actions,
                         "modes_args": limits, "args": argd})

    if "l23" in legs:
        corpus_jobs(L23_POSITIONS, "l23_positions", "l23")
        corpus_jobs(L23_K4_MULTI, "l23_k4_multisource", "l23")
    if "f3" in legs:
        corpus_jobs(F3_SUITE, "f3_roots_k3_suite", "f3")
        corpus_jobs(F3_CHAMP, "f3_roots_k3_champion", "f3")

    if "synth" in legs:
        from carcassonne_ai import rules_profile as rp
        prof = rp.active().name
        for k in range(1, args.synth_max_k + 1):
            mods = modes_for(k, limits)
            if not mods:
                continue
            for i in range(args.synth_n):
                seed = args.synth_seed_base + i
                jobs.append({"kind": "synth", "leg": "synth", "seed": seed, "k": k,
                             "modes": mods, "args": argd, "profile": prof,
                             "tag": f"synth[{prof}]k{k}#seed{seed}"})
    return jobs


# --------------------------------------------------------------------------

def _announce_skip(out: dict) -> None:
    """Fail-loud, on STDOUT, the moment a skip row lands.

    An operator tailing the log must not have to open the JSON to learn that a
    job was dropped — and must be able to tell WHICH cap dropped it.
    """
    status = out.get("status")
    if status == "OOM_SKIPPED":
        print(f"  ⚠️ OOM_SKIPPED {out.get('job_key')} "
              f"(cap={out.get('cap_bytes')}B "
              f"exitcode={out.get('exitcode')})", flush=True)
    elif status == "TIME_SKIPPED":
        print(f"  ⚠️ TIME_SKIPPED {out.get('job_key')} "
              f"(cap={out.get('time_cap_secs')}s "
              f"reason={out.get('kill_reason')} "
              f"cpu={out.get('child_cpu_s')}s "
              f"elapsed={out.get('elapsed_s')}s "
              f"exitcode={out.get('exitcode')})", flush=True)


def rebuild_from_rows(rows_path: Path, args) -> int:
    """Rebuild the verdict from an incremental rows file.

    A partial record is still a real record: every row in it is a comparison
    that actually ran.  It is reported as `partial: true` so nobody can read an
    interrupted run as a complete one, and the SAME exit discipline applies —
    zero mismatches over zero checks is never a PASS.
    """
    totals = blank()
    per_leg: dict[str, dict] = {}
    n_rows = 0
    for line in rows_path.read_text().splitlines():
        if not line.strip():
            continue
        out = json.loads(line)
        n_rows += 1
        leg = out.pop("leg", "?")
        per_leg.setdefault(leg, blank())
        merge(per_leg[leg], dict(out))
        merge(totals, out)
    n_bad = len(totals["mismatches"])
    ok = n_bad == 0 and totals["checks"] > 0
    payload = {
        "gate": "G7/exact_solver",
        "verdict": "PASS" if ok else "FAIL",
        "partial": True,
        "rebuilt_from": str(rows_path),
        "jobs_recorded": n_rows,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "carc_rs_version": carc_rs.__version__,
        "positions": totals["positions"],
        "checks": totals["checks"],
        "skipped_budget": totals["skipped"],
        "cells": totals["cells"],
        "n_mismatches": n_bad,
        "mismatches": totals["mismatches"][: args.max_mismatch_report],
        "oom_skipped": totals["oom_skipped"],
        "oom_job_keys": totals["oom_job_keys"],
        "time_skipped": totals["time_skipped"],
        "time_job_keys": totals["time_job_keys"],
        "per_leg": {k: {"positions": v["positions"], "checks": v["checks"],
                        "skipped": v["skipped"], "cells": v["cells"],
                        "n_mismatches": len(v["mismatches"]),
                        "oom_skipped": v.get("oom_skipped", 0),
                        "time_skipped": v.get("time_skipped", 0)}
                    for k, v in sorted(per_leg.items())},
    }
    out_path = rows_path.with_name(rows_path.name.replace("_rows.jsonl", "_partial.json"))
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps({k: payload[k] for k in
                      ("verdict", "partial", "jobs_recorded", "positions",
                       "checks", "skipped_budget", "n_mismatches",
                       "oom_skipped", "time_skipped", "per_leg", "cells")}, indent=2))
    print(f"-> {out_path}")
    if totals["oom_skipped"]:
        print(f"  ⚠️ {totals['oom_skipped']} job(s) OOM_SKIPPED in this "
              f"partial record: {totals['oom_job_keys']}")
    if totals["time_skipped"]:
        print(f"  ⚠️ {totals['time_skipped']} job(s) TIME_SKIPPED in this "
              f"partial record: {totals['time_job_keys']}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leg", action="append", default=None,
                    choices=["all", "golden", "v2", "l23", "f3", "synth"])
    ap.add_argument("--per-k", type=int, default=25,
                    help="positions sampled per (corpus, K) cell; 0 = all")
    ap.add_argument("--budget", type=int, default=4_000_000)
    ap.add_argument("--solve-timeout-s", type=int, default=0,
                    help="wall cap on each PYTHON solve (0 = none). A cap hit "
                         "is a SKIP, counted and reported, never a PASS")
    ap.add_argument("--max-k", type=int, default=6,
                    help="skip corpus rows above this k_remaining entirely")
    ap.add_argument("--max-k-clair", type=int, default=4,
                    help="run the clairvoyant ALPHA-BETA comparison up to this K")
    ap.add_argument("--max-k-clair-noprune", type=int, default=3,
                    help="run the clairvoyant NO-PRUNE comparison up to this K "
                         "(it is the expensive oracle path)")
    ap.add_argument("--max-k-marg", type=int, default=3,
                    help="run the marginalized comparison up to this K "
                         "(the Python side is the cost wall)")
    ap.add_argument("--synth-n", type=int, default=6)
    ap.add_argument("--synth-max-k", type=int, default=3)
    ap.add_argument("--synth-seed-base", type=int, default=880000)
    ap.add_argument("--rules-profile", default=None,
                    help="activate a rules profile (e.g. fixed_v1) — corpus legs "
                         "are walled-only by construction, so use with --leg synth")
    ap.add_argument("--workers", type=int, default=3,
                    help="fork workers; keep low, a GPU run may own the box")
    ap.add_argument("--job-mem-cap-gb", type=float, default=26.0,
                    help="per-JOB RLIMIT_AS cap in GiB, applied in a forked "
                         "subprocess so one pathological job (unbounded "
                         "transposition-table growth) dies alone instead of "
                         "OOM-killing the whole run. 0 disables isolation "
                         "and runs jobs inline (pre-2026-08-23 behavior).")
    ap.add_argument("--job-time-cap-secs", type=int, default=0,
                    help="per-JOB wall cap in SECONDS (0 = off; the campaign "
                         "runs 7200). Armed as RLIMIT_CPU inside the same "
                         "isolated subprocess as the memory cap — these jobs "
                         "are CPU-pinned, so CPU time == wall time — with a "
                         "parent-side wall backstop for a child that blocks "
                         "instead of computing. A job that exceeds it is "
                         "recorded TIME_SKIPPED: never silent, never a "
                         "mismatch, and skipped by --resume thereafter.")
    ap.add_argument("--out", default=None, help="directory for the verdict JSON")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--max-mismatch-report", type=int, default=200)
    ap.add_argument("--plan-only", action="store_true",
                    help="print the sampling plan (positions per source and "
                         "per K) and exit, without solving anything")
    ap.add_argument("--from-rows", default=None,
                    help="rebuild the verdict from an incremental rows file "
                         "instead of running (an interrupted gate's record)")
    ap.add_argument("--resume", action="store_true",
                    help="skip jobs already recorded in this tag's rows file "
                         "and append the rest. OFF by default: it is only "
                         "sound when the plan is identical, so it re-checks "
                         "that and refuses on an unkeyed (pre-2026-08-23) "
                         "rows file rather than guess")
    args = ap.parse_args()
    if not args.leg:
        args.leg = ["all"]

    if args.from_rows:
        return rebuild_from_rows(Path(args.from_rows), args)

    if args.plan_only:
        from carcassonne_ai import rules_profile as rp
        if args.rules_profile:
            rp.activate(args.rules_profile)
        plan: dict[str, int] = {}
        for job in build_jobs(args):
            if job["kind"] == "corpus":
                for r in job["recs"]:
                    key = f"{job['source']}:k{r['k_remaining']}"
                    plan[key] = plan.get(key, 0) + 1
            elif job["kind"] == "synth":
                key = f"synth[{job['profile']}]:k{job['k']}"
                plan[key] = plan.get(key, 0) + 1
            else:
                plan[job["kind"]] = plan.get(job["kind"], 0) + 1
        by_k: dict[str, int] = {}
        for key, n in plan.items():
            if ":k" in key:
                by_k[key.split(":k")[1]] = by_k.get(key.split(":k")[1], 0) + n
        print(json.dumps({"per_source": dict(sorted(plan.items())),
                          "positions_per_k": dict(sorted(by_k.items()))}, indent=2))
        return 0

    from carcassonne_ai import rules_profile as rp
    if args.rules_profile:
        rp.activate(args.rules_profile)
    profile = rp.active()

    # R9 rides OUTSIDE the profile: it is env-latched at IMPORT on the Python
    # side and in a OnceLock on the Rust side, so it cannot be switched here.
    # A `fixed_v1` leg that forgot `CARCASSONNE_FIX_R9=1` would silently grade
    # two different rule sets — fail loudly instead.
    manifest = profile.as_manifest()
    if not manifest["r9_env_ok"]:
        raise SystemExit(
            f"profile {profile.name!r} expects {rp.R9_ENV_VAR}="
            f"{profile.r9_env_expected} but the process observed "
            f"{manifest['r9_env_observed']} — export it BEFORE starting python")
    if rp.r9_env_on() != carc_rs.r9_enabled():
        raise SystemExit(
            f"R9 latch disagreement: python={rp.r9_env_on()} "
            f"rust={carc_rs.r9_enabled()}")
    if args.rules_profile and args.rules_profile != "walled" and (
            set(args.leg) - {"synth"}):
        print(f"  NOTE: the committed corpora were generated 'walled'; legs "
              f"other than 'synth' will fail their checksum guard under "
              f"{profile.name!r}.", flush=True)

    t0 = time.time()
    jobs = build_jobs(args)
    print(f"[reconcile_exact_solver] profile={profile.name} jobs={len(jobs)} "
          f"workers={args.workers} budget={args.budget}", flush=True)

    out_dir = Path(args.out) if args.out else REPO / "measurement" / "rustport_exact_solver"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"G7_exact_solver_{args.tag}.json"
    # INCREMENTAL: append each finished job the moment it lands.  A long gate
    # that is interrupted before its final write would otherwise lose every
    # comparison it paid for (measured: a 50/102 run, ~30 min of K=3 solves,
    # zero mismatches, no artifact).  `--from-rows` rebuilds the verdict from
    # this file, and it is the honest partial record either way.
    rows_path = out_dir / f"G7_exact_solver_{args.tag}_rows.jsonl"

    # RESUME: the rows file is opened in APPEND mode, so a re-run with the same
    # --tag adds to whatever is already there. Without --resume that DOUBLE
    # COUNTS every job the previous attempt finished (observed: the `run` tag's
    # rows file carries 28 golden + 24 v2 rows for a 14-golden + 12-v2 plan —
    # two attempts' worth — so a --from-rows rebuild of it over-reports checks).
    # With --resume we read the recorded keys and plan only the remainder.
    n_planned = len(jobs)
    n_skipped_resume = 0
    if args.resume and rows_path.exists():
        done_keys = recorded_job_keys(rows_path)
        jobs = [j for j in jobs if job_key(j) not in done_keys]
        n_skipped_resume = n_planned - len(jobs)
        orphan = done_keys - {job_key(j) for j in build_jobs(args)}
        print(f"[resume] {n_skipped_resume}/{n_planned} jobs already recorded "
              f"in {rows_path.name}; {len(jobs)} to run", flush=True)
        if orphan:
            # Recorded work that this plan does not contain: the arguments or
            # the corpora moved. Loud, not fatal — the rows are still honest
            # records, but the run is no longer the plan it is resuming.
            print(f"  ⚠️ {len(orphan)} recorded job(s) are NOT in the current "
                  f"plan (args or corpora changed): "
                  f"{sorted(orphan)[:5]}{' …' if len(orphan) > 5 else ''}",
                  flush=True)
    elif args.resume:
        print(f"[resume] no rows file at {rows_path} — running the full plan",
              flush=True)

    rows_fh = rows_path.open("a")

    def _record(out: dict) -> None:
        rows_fh.write(json.dumps(out, sort_keys=True, default=str) + "\n")
        rows_fh.flush()

    cap_bytes = int(args.job_mem_cap_gb * (1024 ** 3)) if args.job_mem_cap_gb > 0 else 0
    time_cap_secs = max(0, int(args.job_time_cap_secs or 0))
    if cap_bytes > 0:
        print(f"[reconcile_exact_solver] per-job memory cap: "
              f"{args.job_mem_cap_gb:g} GiB (RLIMIT_AS, isolated subprocess "
              f"per job) — a job that exceeds it is recorded OOM_SKIPPED, "
              f"never silently, and the pool keeps going", flush=True)
    if time_cap_secs > 0:
        print(f"[reconcile_exact_solver] per-job time cap: {time_cap_secs}s "
              f"(RLIMIT_CPU in the same isolated subprocess, +{WALL_GRACE_S}s "
              f"parent wall backstop) — a job that exceeds it is recorded "
              f"TIME_SKIPPED, never silently, and the pool keeps going",
              flush=True)

    totals = blank()
    per_leg: dict[str, dict] = {}
    done = 0
    if jobs:
        if args.workers > 1:
            worker_fn = functools.partial(run_job_capped, cap_bytes=cap_bytes,
                                          time_cap_secs=time_cap_secs)
            # NestablePool, not ctx.Pool: run_job_capped forks a per-job child
            # FROM the pool worker, and a plain Pool's workers are daemons —
            # daemons cannot have children — see _NoDaemonProcess above.
            with NestablePool(args.workers) as pool:
                for out in pool.imap_unordered(worker_fn, jobs, chunksize=1):
                    done += 1
                    _record(out)
                    _announce_skip(out)
                    leg = out.pop("leg")
                    per_leg.setdefault(leg, blank())
                    merge(per_leg[leg], dict(out))
                    merge(totals, out)
                    if done % 10 == 0:
                        print(f"  {done}/{len(jobs)} jobs, "
                              f"{totals['checks']} checks, "
                              f"{len(totals['mismatches'])} mismatches, "
                              f"{totals['oom_skipped']} OOM-skipped, "
                              f"{totals['time_skipped']} TIME-skipped "
                              f"({time.time() - t0:.0f}s)", flush=True)
        else:
            for job in jobs:
                out = run_job_capped(job, cap_bytes, time_cap_secs)
                done += 1
                _record(out)
                _announce_skip(out)
                leg = out.pop("leg")
                per_leg.setdefault(leg, blank())
                merge(per_leg[leg], dict(out))
                merge(totals, out)
                # `--workers 1` is the production shape for this campaign, so
                # it gets the same periodic progress line as the pool branch —
                # without it a single-worker multi-hour run logs nothing
                # between skips.
                if done % 10 == 0:
                    print(f"  {done}/{len(jobs)} jobs, "
                          f"{totals['checks']} checks, "
                          f"{len(totals['mismatches'])} mismatches, "
                          f"{totals['oom_skipped']} OOM-skipped, "
                          f"{totals['time_skipped']} TIME-skipped "
                          f"({time.time() - t0:.0f}s)", flush=True)
    rows_fh.close()

    n_ran = done
    if n_skipped_resume:
        # THE VERDICT IS OVER THE WHOLE PLAN, NOT OVER THIS PROCESS'S SHARE.
        # Without this, a resume that had only 3 jobs left would report 3 jobs'
        # worth of checks, and a resume with NOTHING left would report zero
        # checks and therefore FAIL a gate that had actually finished. The rows
        # file now holds every job of the plan, so re-derive from it.
        totals = blank()
        per_leg = {}
        for line in rows_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            leg = row.pop("leg", "?")
            per_leg.setdefault(leg, blank())
            merge(per_leg[leg], dict(row))
            merge(totals, row)

    n_bad = len(totals["mismatches"])
    # POSITIVE EVIDENCE REQUIRED: zero mismatches over zero checks is the
    # sha-of-empty shape. No comparisons => no PASS, ever.
    ok = n_bad == 0 and totals["checks"] > 0
    payload = {
        "gate": "G7/exact_solver",
        "verdict": "PASS" if ok else "FAIL",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
        "carc_rs_version": carc_rs.__version__,
        "rules_profile": profile.name,
        "r9_enabled": carc_rs.r9_enabled(),
        "args": vars(args),
        # Resume bookkeeping (additive; both 0 on a plain full run).
        "jobs_planned": n_planned,
        "jobs_ran_this_process": n_ran,
        "jobs_skipped_resume": n_skipped_resume,
        "rows_file": str(rows_path),
        "positions": totals["positions"],
        "checks": totals["checks"],
        "skipped_budget": totals["skipped"],
        "cells": totals["cells"],
        "n_mismatches": n_bad,
        "mismatches": totals["mismatches"][: args.max_mismatch_report],
        # Fail-loud: a job that died to its memory cap is a documented hole in
        # the run, never a silent one — the count AND the job keys, both in
        # the payload and echoed to stdout below, so an operator scanning the
        # log (not just the JSON) cannot miss it. It does NOT flip `verdict`:
        # an OOM is a resource limitation, not a correctness finding, and a
        # gate that could never PASS again once one pathological tail job
        # exists would defeat the point of isolating it.
        "job_mem_cap_gb": args.job_mem_cap_gb,
        "oom_skipped": totals["oom_skipped"],
        "oom_job_keys": totals["oom_job_keys"],
        # Same fail-loud contract as the OOM fields above, for the per-job WALL
        # cap: counted, keyed, echoed to stdout, and — like an OOM — NOT a
        # verdict flip. A cutoff is a documented hole in coverage, not a
        # correctness finding, and a gate that could never PASS again once one
        # pathological tail job exists would defeat the point of capping it.
        "job_time_cap_secs": time_cap_secs,
        "time_skipped": totals["time_skipped"],
        "time_job_keys": totals["time_job_keys"],
        "per_leg": {k: {"positions": v["positions"], "checks": v["checks"],
                        "skipped": v["skipped"], "cells": v["cells"],
                        "n_mismatches": len(v["mismatches"]),
                        "oom_skipped": v.get("oom_skipped", 0),
                        "time_skipped": v.get("time_skipped", 0)}
                    for k, v in sorted(per_leg.items())},
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    print(json.dumps({k: payload[k] for k in
                      ("verdict", "positions", "checks", "skipped_budget",
                       "n_mismatches", "oom_skipped", "time_skipped",
                       "per_leg", "cells")},
                     indent=2))
    print(f"-> {out_path}")
    if totals["oom_skipped"]:
        print(f"  ⚠️ {totals['oom_skipped']} job(s) OOM_SKIPPED at "
              f"{args.job_mem_cap_gb:g} GiB/job: {totals['oom_job_keys']}")
    if totals["time_skipped"]:
        print(f"  ⚠️ {totals['time_skipped']} job(s) TIME_SKIPPED at "
              f"{time_cap_secs}s/job: {totals['time_job_keys']}")
    for m in totals["mismatches"][:20]:
        print("  MISMATCH", json.dumps(m)[:400])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
