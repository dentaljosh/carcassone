#!/usr/bin/env python3
"""F-3 CALLER GATE — the four desktop `make_production_champion` callers, on Rust.

⚠️ NEW GATE SCRIPT (2026-08-02) — flagged for merge review, sibling of
`gate_clairvoyant.py` / `gap1_seed_invariance.py`.

WHAT IT PROVES, per caller (BACKEND_BYPASS_AUDIT_20260801 §1 / §6 F-3):

  (a) IDENTITY — the caller driven at `backend=rust` produces BYTE-IDENTICAL actions to
      the same caller at `backend=python`, on the same deck seed / the same replayed
      roots. Deterministic by construction on both legs, so ANY difference is a bug,
      not noise. This is the G6 pattern applied at the HARNESS level rather than the
      agent level: G6 proved the engine, this proves the wiring around it.
  (b) NO DESYNC — zero `MirrorDesync` raised across every ply of every gate game.
  (c) THE GUARD STILL FIRES — a deliberately SKIPPED `advance()` at each caller's own
      choke point must raise `MirrorDesync`. A gate that only shows green when the
      wiring is right is worthless if the wiring being wrong is also green; this is the
      half that proves the check was not weakened to make (a) pass.

The four callers, and the shape each one is exercised in:

  play_harness.py       full fair-vs-fair game (BOTH seats mirrored) AND a scripted
                        human-vs-champion game (ONE mirrored agent, which must advance
                        on the OTHER seat's actions too — the E4 exam shape)
  play_vs_tier1_gui.py  the GUI's own `_seat_mirror` / `_advance_mirror` / `_apply_action`
                        choke point, driven headlessly (no Tk)
  m5_bench/bench_champion.py     its `reseat` + `replay` mid-game entry, root by root
  measurement_infra/kparallel_latency_bench.py   its `time_row`, python-processes vs
                        rust-threads, on the same replayed roots

Usage:
    python scripts/rustport/gate_f3_callers.py \
        --out measurement/rustport_p6/F3_CALLER_GATES_20260802.json
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
for _p in ("src", "scripts/human_anchor", "scripts/measurement_infra", "scripts",
           "scripts/m5_bench"):
    sys.path.insert(0, str(_REPO / _p))

import env_preamble  # noqa: E402,F401  production leaf env BEFORE carcassonne_ai

# Gate budget: tiny, because this gate is about WIRING, not strength. Identity is
# exact at any budget (both legs are deterministic), and a k2x24 game exercises every
# ply, both phases, the latch and the exact-endgame handoff just as a k8x1376 one does.
SIMS, K_DETS = 24, 2


def _rev() -> str:
    try:
        return subprocess.run(["git", "-C", str(_REPO), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                           # pragma: no cover
        return "unknown"


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _execution(backend: str):
    from carcassonne_ai.mirror_protocol import resolve_execution

    # profile=None: the gate compares ENGINES, so it must not also pick up the desktop
    # profile's parallel_workers on the python leg (behaviour-identical, but it would
    # spawn 8 processes for a k2x24 smoke).
    return resolve_execution(backend, profile=None)


class ScriptedHuman:
    """A deterministic stand-in for `HumanCLIAgent`: always takes the FIRST legal
    action. Owns no mirror — which is the point: the champion sharing the game with it
    must still advance on THIS seat's actions."""

    neural_moves = heur_moves = exact_moves = n_timeouts = 0
    solver_secs = solver_nodes = 0
    latch_k = None

    def __init__(self, game):
        self._game = game

    def choose_action(self, board) -> int:
        import numpy as np

        return int(np.flatnonzero(self._game.get_valid_moves(board))[0])


# --------------------------------------------------------------------------- #
# 1. play_harness.py                                                           #
# --------------------------------------------------------------------------- #
def gate_play_harness(seed: int) -> dict:
    import play_harness as PH
    from carcassonne_ai.game_wrapper import Game

    out = {"caller": "scripts/human_anchor/play_harness.py", "shapes": {}}

    for shape in ("fair_vs_fair", "scripted_human_vs_champion"):
        legs = {}
        for backend in ("python", "rust"):
            ex = _execution(backend)
            game = Game(enable_legal_moves_cache=True)

            def champ(s):
                return PH._make_fair_agent(game, SIMS, K_DETS, seed=s, execution=ex)

            if shape == "fair_vs_fair":
                agents = {0: champ(101), 1: champ(202)}
                labels = {0: "fairA", 1: "fairB"}
            else:
                agents = {0: ScriptedHuman(game), 1: champ(303)}
                labels = {0: "scripted_human", 1: "champion"}
            t0 = time.perf_counter()
            rec = PH.play_game(game, seed, agents, labels,
                               {"sims": SIMS, "k_dets": K_DETS, "gate": True})
            legs[backend] = {
                "actions": [m["action"] for m in rec["moves"]],
                "n_moves": rec["result"]["n_moves"],
                "scores": rec["result"]["scores"],
                "paths": [m["path"] for m in rec["moves"]],
                "secs": round(time.perf_counter() - t0, 3),
            }
        out["shapes"][shape] = _compare(legs)
    return out


def _compare(legs: dict) -> dict:
    p, r = legs["python"], legs["rust"]
    mism = [i for i, (x, y) in enumerate(zip(p["actions"], r["actions"])) if x != y]
    return {
        "n_action_checks": len(p["actions"]),
        "identical": (p["actions"] == r["actions"]
                      and p.get("scores") == r.get("scores")
                      and p.get("paths") == r.get("paths")),
        "first_divergence_ply": (mism[0] if mism else None),
        "n_mismatches": len(mism) + abs(len(p["actions"]) - len(r["actions"])),
        "python": {k: v for k, v in p.items() if k != "actions"},
        "rust": {k: v for k, v in r.items() if k != "actions"},
        "speedup_x": (round(p["secs"] / r["secs"], 2)
                      if r.get("secs") else None),
    }


# --------------------------------------------------------------------------- #
# 2. play_vs_tier1_gui.py — the real choke point, headless                     #
# --------------------------------------------------------------------------- #
class _FakeGUI:
    """Enough of `GameGUI` to run its UNBOUND mirror methods and its move loop.

    Deliberately calls `GameGUI._seat_mirror` / `_advance_mirror` / `_apply_action`
    themselves rather than reimplementing them — a gate that reimplements the code it
    grades proves nothing about the shipped file. `_apply_action` also touches
    `selected_cell` / `rotation_options` / `rotation_idx` and calls `_advance`, which
    are stubbed here (they are pure Tk chrome)."""

    def __init__(self, game, opponent, human_seat: int):
        import play_vs_tier1_gui as GUI

        self._GUI = GUI
        self.game = game
        self.ai = opponent
        self.human = human_seat
        self.board = game.get_init_board()
        self.actions: list[int] = []
        GUI.GameGUI._seat_mirror(self)

    # the Tk chrome `_apply_action` touches, stubbed
    def _advance(self) -> None:
        pass

    # the SHIPPED method, called through this object exactly as `_apply_action` does
    def _advance_mirror(self, idx: int) -> None:
        self._GUI.GameGUI._advance_mirror(self, idx)

    def apply(self, idx: int) -> None:
        self.actions.append(int(idx))
        self._GUI.GameGUI._apply_action(self, int(idx))

    def play(self, skip_advance_at: int | None = None) -> list[int]:
        import numpy as np

        while not self.board.state.is_terminated():
            if self.board.state.current_player == self.human:
                idx = int(np.flatnonzero(self.game.get_valid_moves(self.board))[0])
            else:
                idx = int(self.ai.pick(self.board,
                                       self.game.get_valid_moves(self.board)))
            if skip_advance_at is not None and len(self.actions) == skip_advance_at:
                # INJECTION: apply to the authoritative board but NOT to the mirror.
                self.actions.append(idx)
                self.board, _ = self.game.get_next_state(self.board, idx)
                continue
            self.apply(idx)
        return self.actions


def gate_gui(seed: int) -> dict:
    import play_vs_tier1_gui as GUI
    from carcassonne_ai.game_wrapper import Game

    legs = {}
    for backend in ("python", "rust"):
        random.seed(seed)                 # the GUI seeds immediately before get_init_board
        game = Game(enable_legal_moves_cache=True)
        opp = GUI.build_opponent("champion", seed=seed, sims=SIMS, k_dets=K_DETS,
                                 verbose=False, backend=backend, profile=None)
        t0 = time.perf_counter()
        gui = _FakeGUI(game, opp, human_seat=0)
        acts = gui.play()
        legs[backend] = {
            "actions": acts,
            "n_moves": len(acts),
            "scores": list(gui.board.state.scores),
            "agent_class": type(opp.agent).__name__,
            "secs": round(time.perf_counter() - t0, 3),
        }
    res = _compare(legs)
    res["caller"] = "scripts/play_vs_tier1_gui.py"
    return res


# --------------------------------------------------------------------------- #
# 3. m5_bench/bench_champion.py — mid-game entry by replay                     #
# --------------------------------------------------------------------------- #
def _bench_rows(n_rows: int, stride: int = 23) -> list[dict]:
    """`positions.jsonl` rows, in `make_positions.py` shape, off real champion games."""
    src = _REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
    rows = []
    with open(src) as fh:
        for line in fh:
            if not line.strip():
                continue
            g = json.loads(line)
            n = len(g["actions"])
            for ply in range(int(n * 0.35), int(n * 0.75), stride):
                rows.append({"pos_id": len(rows), "deck_seed": int(g["deck_seed"]),
                             "actions": [int(a) for a in g["actions"][:ply]],
                             "ply": ply, "phase": "n/a", "k_remaining": -1,
                             "n_legal": -1})
                if len(rows) >= n_rows:
                    return rows
    return rows


def gate_bench_champion(n_rows: int = 6) -> dict:
    import bench_champion as BC
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.game_wrapper import Game

    rows = _bench_rows(n_rows)
    legs = {}
    for backend in ("python", "rust"):
        agent = CF.make_production_champion(
            "fair", game=Game(enable_legal_moves_cache=True), seed=101, sims=SIMS,
            k_dets=K_DETS, exact_endgame=True, verify=False,
            # PINNED in BOTH directions (2026-08-03): the factory default is now
            # "auto", so an omitted kwarg on the python leg would build a Rust agent
            # and this gate would compare rust against rust.
            backend=backend)
        acts, t0 = [], time.perf_counter()
        for i, row in enumerate(rows):
            _g, board = BC.replay(Game, row)
            BC.reseat(agent, row, i)              # the shipped mid-game entry
            agent._latched = False
            acts.append(int(agent.choose_action(board)))
        legs[backend] = {"actions": acts, "n_roots": len(rows),
                         "secs": round(time.perf_counter() - t0, 3)}
    res = _compare(legs)
    res["caller"] = "scripts/m5_bench/bench_champion.py"
    res["note"] = ("mid-game entry: start_game_from_seed + advance(prefix) + seated "
                   "_move_idx, at every root, on ONE reused agent")
    return res


# --------------------------------------------------------------------------- #
# 4. measurement_infra/kparallel_latency_bench.py                              #
# --------------------------------------------------------------------------- #
def gate_kparallel(n_moves: int = 6) -> dict:
    import kparallel_latency_bench as KP

    roots = KP.load_roots(KP.DEFAULT_GAMES, n_moves, 0.35, 0.70, 11)
    legs = {}
    rows = []
    for backend, workers in (("python", None), ("rust", None), ("rust", 2)):
        t0 = time.perf_counter()
        secs, acts, _t = KP.time_row(roots, K_DETS, SIMS, workers, 90_000,
                                     backend=backend)
        label = (f"rust_t{1 if workers is None else workers}" if backend == "rust"
                 else "sequential")
        rows.append({"mode": label, "backend": backend, "workers": workers,
                     "mean_s_per_move": round(sum(secs) / len(secs), 4)})
        if backend == "python":
            legs["python"] = {"actions": acts, "secs": round(time.perf_counter() - t0, 3)}
        elif workers is None:
            legs["rust"] = {"actions": acts, "secs": round(time.perf_counter() - t0, 3)}
        else:
            legs["rust_t2"] = {"actions": acts}
    res = _compare(legs)
    res["caller"] = "scripts/measurement_infra/kparallel_latency_bench.py"
    res["rows"] = rows
    res["rust_t2_matches_python"] = (legs["rust_t2"]["actions"] == legs["python"]["actions"])
    res["note"] = ("on rust the worker list is OS THREADS, not spawn processes — the "
                   "factory raises on backend=rust + parallel_workers")
    return res


# --------------------------------------------------------------------------- #
# 5. THE GUARD STILL FIRES — deliberate desync injection, per caller shape     #
# --------------------------------------------------------------------------- #
def gate_desync_injection(seed: int) -> dict:
    """Skip ONE `advance()` at each caller's choke point; demand `MirrorDesync`."""
    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.rust_agent import MirrorDesync

    out = {}

    # --- play_harness: neuter the advance() call the play loop makes -----------
    import play_harness as PH

    real_advance = MP.advance
    game = Game(enable_legal_moves_cache=True)
    ex = _execution("rust")
    agents = {0: PH._make_fair_agent(game, SIMS, K_DETS, seed=101, execution=ex),
              1: PH._make_fair_agent(game, SIMS, K_DETS, seed=202, execution=ex)}
    MP.advance = lambda *a, **k: 0                 # the pre-F-3 behaviour, exactly
    try:
        PH.play_game(game, seed, agents, {0: "a", 1: "b"}, {"gate": "injection"})
        out["play_harness"] = {"raised": False, "error": "NO MirrorDesync — the guard "
                               "did not fire on a frozen mirror"}
    except MirrorDesync as exc:
        out["play_harness"] = {"raised": True, "exc": type(exc).__name__,
                               "at": str(exc).splitlines()[0]}
    finally:
        MP.advance = real_advance

    # --- the GUI: skip _advance_mirror at one ply -----------------------------
    import play_vs_tier1_gui as GUI

    random.seed(seed)
    g2 = Game(enable_legal_moves_cache=True)
    opp = GUI.build_opponent("champion", seed=seed, sims=SIMS, k_dets=K_DETS,
                             verbose=False, backend="rust", profile=None)
    try:
        _FakeGUI(g2, opp, human_seat=0).play(skip_advance_at=1)
        out["gui"] = {"raised": False, "error": "NO MirrorDesync at the GUI choke point"}
    except MirrorDesync as exc:
        out["gui"] = {"raised": True, "exc": type(exc).__name__,
                      "at": str(exc).splitlines()[0]}

    # --- mid-game entry: reseat WITHOUT replaying the prefix -------------------
    import bench_champion as BC
    from carcassonne_ai import champion_factory as CF

    row = _bench_rows(1)[0]
    agent = CF.make_production_champion(
        "fair", game=Game(enable_legal_moves_cache=True), seed=7, sims=SIMS,
        k_dets=K_DETS, verify=False, backend="rust")
    _g, board = BC.replay(Game, row)
    agent.start_game_from_seed(int(row["deck_seed"]))      # ply 0, prefix NOT replayed
    try:
        agent.choose_action(board)
        out["midgame_entry"] = {"raised": False,
                                "error": "NO MirrorDesync on an unreplayed root"}
    except MirrorDesync as exc:
        out["midgame_entry"] = {"raised": True, "exc": type(exc).__name__,
                                "at": str(exc).splitlines()[0]}

    out["all_fired"] = all(v.get("raised") for v in out.values() if isinstance(v, dict))
    return out


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=777_000_001)
    ap.add_argument("--roots", type=int, default=6)
    a = ap.parse_args(argv)

    from carcassonne_ai import rust_agent

    t0 = time.perf_counter()
    result = {
        "gate": "F3_CALLER_GATES",
        "what": "the four make_production_champion desktop callers, driven on the Rust "
                "mirror protocol: identical actions vs python, zero MirrorDesync, and "
                "the guard still fires when an advance() is deliberately skipped",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_rev": _rev(),
        "budget": {"k_dets": K_DETS, "sims_per_det": SIMS,
                   "note": "WIRING gate — identity is exact at any budget (both legs "
                           "deterministic); the seconds here are NOT a latency claim "
                           "(tiny sims, shared box)"},
        "carc_rs": rust_agent.backend_provenance(),
        "leaf_env": dict(env_preamble.RESOLVED),
        "callers": {},
    }

    print("[1/5] play_harness.py ...", flush=True)
    result["callers"]["play_harness"] = gate_play_harness(a.seed)
    print("[2/5] play_vs_tier1_gui.py ...", flush=True)
    result["callers"]["play_vs_tier1_gui"] = gate_gui(a.seed)
    print("[3/5] m5_bench/bench_champion.py ...", flush=True)
    result["callers"]["bench_champion"] = gate_bench_champion(a.roots)
    print("[4/5] measurement_infra/kparallel_latency_bench.py ...", flush=True)
    result["callers"]["kparallel_latency_bench"] = gate_kparallel(a.roots)
    print("[5/5] desync injection ...", flush=True)
    result["desync_injection"] = gate_desync_injection(a.seed)

    checks = []
    for name, r in result["callers"].items():
        subs = r.get("shapes", {name: r})
        for shape, s in subs.items():
            checks.append((f"{name}/{shape}", bool(s["identical"]), s["n_action_checks"]))
    result["summary"] = {
        "action_checks": sum(n for _, _, n in checks),
        "identical_legs": sum(1 for _, ok, _ in checks if ok),
        "total_legs": len(checks),
        "mirror_desyncs_raised_in_wired_runs": 0,
        "guard_fires_when_advance_skipped": bool(result["desync_injection"]["all_fired"]),
        "PASS": (all(ok for _, ok, _ in checks)
                 and bool(result["desync_injection"]["all_fired"])),
    }
    result["wall_s"] = round(time.perf_counter() - t0, 1)

    print()
    for name, ok, n in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<48s} {n:>5d} action checks")
    inj = result["desync_injection"]
    for k in ("play_harness", "gui", "midgame_entry"):
        print(f"  {'PASS' if inj[k]['raised'] else 'FAIL'}  injection/{k:<38s} "
              f"{'MirrorDesync raised' if inj[k]['raised'] else inj[k].get('error')}")
    s = result["summary"]
    print(f"\n  {s['action_checks']} action checks, {s['identical_legs']}/"
          f"{s['total_legs']} legs byte-identical, guard fires: "
          f"{s['guard_fires_when_advance_skipped']}  -> "
          f"{'PASS' if s['PASS'] else 'FAIL'}  ({result['wall_s']}s)")

    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=2, default=str))
        print(f"wrote {a.out}")
    return 0 if result["summary"]["PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
