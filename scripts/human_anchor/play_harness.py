"""4.2 — Logged human-vs-agent play harness (production FAIR agent).

A minimal, fully-logged interface for a human (or another agent) to play the
DEPLOYABLE fair-play champion — the audited-honest, non-clairvoyant PIMC + K<=2
marginalized-exact-endgame agent (Phase 0.1/0.4 are green, so the fair agent is
audited honest: it never peeks at the real deck).

⚠️ REWIRED 2026-07-19 (F1): the champion is now built by
``carcassonne_ai.champion_factory.make_production_champion("fair")`` — the CURRENT
champion, ``FairHeuristicPriorAgent`` (PUCT heuristic priors + curve125 leaf,
c_puct=1.5/tau_p=5/float/visits) at whatever budget PRODUCTION.yaml names — since the
2026-07-29 promotion that is k8x1376 = 11008 sims/move, resolved automatically below.
⚠️ FOLLOW-UP OWED: this harness does NOT yet read the deploy execution profile
``fair_deploy.deploy_profiles.desktop.parallel_workers`` (=8), so it runs the champion's
SEQUENTIAL k-loop at ~13.8 s/move instead of the split's ~2.2 s/move. Same player either
way (the split is behavior-identical, tests/test_kparallel.py) — it is purely a clock cost.
It previously wired the PRE-FLIP
``FairHeuristicMCTSAgent`` (random-expansion UCT + the old curve100 leaf), which the
2026-07-07 champion flip and the 2026-07-13 curve125 adopt never propagated here — so
this harness did NOT run the current champion (PRODUCTION.yaml stale_path_flag). The
factory PROVES the leaf on real boards at construction and records a runtime manifest
into every game log. E4 (the human exam) itself stays PARKED (Joshua).

Enforces the locked 2p Base+Farmers ruleset (the wingedsheep engine already
constrains this; we assert `state.players == 2`). No ELO math lives here — this
just produces trustworthy game records for the human-anchor program to score.

Records per game:
  * every action (seat, phase, k_remaining, action id + description),
  * per-move agent telemetry: which path (pimc / exact / forced), latch_k,
    solver secs & nodes for that move, wall-clock ms, wall timestamp,
  * a signed MANIFEST: agent version = git rev, resolved leaf env, config hash,
    leaf hash, deck seed + deck hash, final result, and a content signature
    (sha256 over the canonical manifest+moves — tamper-evident, NOT a keyed sig).

Paired-deck rematch: `play_paired(seed, ...)` plays the SAME shuffled deck twice
with seats swapped (A in seat0 / B in seat1, then B in seat0 / A in seat1). The
deck is reproduced by `random.seed(deck_seed)` before `get_init_board` (the
root_replay contract); both games carry an identical `deck_hash` proving it.

Usage:
  # prove the pipeline (RUNS one full fair-vs-fair game + a paired rematch, low sims):
  .venv/bin/python scripts/human_anchor/play_harness.py --self-test

  # a human (seat 0) vs the fair champion (seat 1), production sims:
  .venv/bin/python scripts/human_anchor/play_harness.py --human 0 --sims 400 --k-dets 4 \
      --seed 12345 --out measurement/human_anchor/games
"""
from __future__ import annotations

import env_preamble  # noqa: F401  MUST precede carcassonne_ai import
import argparse
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import _common as C

# telemetry counters snapshotted per move on the fair agent
_COUNTERS = ("heur_moves", "exact_moves", "n_timeouts", "solver_secs",
             "solver_nodes", "neural_moves")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def deck_hash(state) -> str:
    """Order-sensitive digest of the initial deck ([next_tile]+deck). Identical
    across a paired rematch iff the same shuffle was reproduced."""
    tiles = ([state.next_tile] if state.next_tile is not None else []) + list(state.deck)
    h = hashlib.sha256()
    h.update("\x1f".join(t.description for t in tiles).encode())
    return h.hexdigest()[:16]


def _snapshot(agent) -> dict:
    return {k: getattr(agent, k, 0) for k in _COUNTERS} | {"latch_k": agent.latch_k}


def _make_fair_agent(game, sims, k_dets, seed, exact_endgame=True):
    """The PRODUCTION fair champion, built + runtime-verified by the champion factory
    (F1, 2026-07-19). Rewired from the PRE-FLIP FairHeuristicMCTSAgent (random-expansion
    UCT + old leaf) to the current champion: FairHeuristicPriorAgent (PUCT heuristic
    priors, curve125 leaf, c_puct=1.5/tau_p=5/float/visits) via
    champion_factory.make_production_champion, which reads governance/PRODUCTION.yaml and
    PROVES the leaf on real boards at construction (raises on mismatch). The returned
    agent carries a runtime manifest (`agent.manifest`) recorded into every game log.
    c_puct is no longer a knob here — the champion's c_puct=1.5 is factory-owned."""
    from carcassonne_ai.champion_factory import make_production_champion
    return make_production_champion("fair", game=game, seed=seed, sims=sims,
                                    k_dets=k_dets, exact_endgame=exact_endgame)


class HumanCLIAgent:
    """A keyboard player: prints the board + enumerated legal moves, reads a pick.
    Same interface (`choose_action(board) -> int`) as the fair agent, so the play
    loop is agent-agnostic. Carries the fair-agent telemetry attrs (all 0) so the
    logger treats it uniformly."""

    def __init__(self, game):
        self._game = game
        self.latch_k = None
        for k in _COUNTERS:
            setattr(self, k, 0)

    def choose_action(self, board) -> int:
        legal = C.legal_action_ids(self._game, board)
        print(C.render_board(board.state))
        s = board.state
        tile_desc = getattr(s.next_tile, "description", None)
        print(f"  you are player {s.current_player}   scores(p0,p1)={list(s.scores)}"
              f"   phase={s.phase.value}   K={C.k_remaining(s)}")
        # Without this the move list is bare coordinates and the human cannot tell WHICH
        # tile they are placing / which tile they just placed a meeple on.
        print(f"  tile in hand: {tile_desc}   meeples left(p0,p1)={list(s.meeples)}")
        for i, a in enumerate(legal):
            print(f"    [{i:>3}] a={a:<5} {C.describe_action(board, a)}")
        while True:
            raw = input("  pick move # : ").strip()
            try:
                idx = int(raw)
                if 0 <= idx < len(legal):
                    return legal[idx]
            except ValueError:
                pass
            print("  invalid; try again.")


def play_game(game, deck_seed: int, agents: dict, agent_labels: dict,
              config: dict) -> dict:
    """Play one full 2p game. `agents` = {seat: agent} (seat -> object with
    choose_action(board)->int + the telemetry attrs). Returns a game record
    {manifest, moves, result}. Never records a peek at the true deck."""
    random.seed(int(deck_seed))          # fixes the engine shuffle (root_replay contract)
    board = game.get_init_board()
    assert board.state.players == 2, "locked scope: 2-player only"
    dh = deck_hash(board.state)
    moves = []
    t_start = time.time()
    move_idx = 0
    while game.get_game_ended(board, 0) == 0.0:
        seat = board.state.current_player
        agent = agents[seat]
        legal = C.legal_action_ids(game, board)
        before = _snapshot(agent)
        t0 = time.perf_counter()
        a = int(agent.choose_action(board))
        ms = (time.perf_counter() - t0) * 1000.0
        after = _snapshot(agent)
        if len(legal) == 1:
            path = "forced"
        elif after["exact_moves"] > before["exact_moves"]:
            path = "exact"
        else:
            path = "pimc"
        moves.append({
            "move_idx": move_idx,
            "seat": seat,
            "agent": agent_labels[seat],
            "phase": board.state.phase.value,
            "k_remaining": C.k_remaining(board.state),
            "n_legal": len(legal),
            "action": a,
            "desc": C.describe_action(board, a),
            "path": path,
            "latch_k": after["latch_k"],
            "solver_secs_move": round(after["solver_secs"] - before["solver_secs"], 6),
            "solver_nodes_move": after["solver_nodes"] - before["solver_nodes"],
            "timeout": after["n_timeouts"] > before["n_timeouts"],
            "ms": round(ms, 2),
            "ts": time.time(),
        })
        board, _ = game.get_next_state(board, a)
        move_idx += 1

    scores = list(board.state.scores)
    winner = 0 if scores[0] > scores[1] else 1 if scores[1] > scores[0] else -1
    result = {"scores": scores, "winner_seat": winner,
              "margin_seat0_minus_seat1": scores[0] - scores[1], "n_moves": move_idx,
              "wall_secs": round(time.time() - t_start, 2)}

    manifest = {
        "kind": "human_anchor_game",
        "agent_version": C.git_rev(),
        "leaf_hash": C.leaf_hash(),
        "leaf_env": env_preamble.RESOLVED,
        "deck_seed": int(deck_seed),
        "deck_hash": dh,
        "agent_labels": agent_labels,
        # F1: the runtime-verified champion factory manifest for every factory-built
        # agent seat (curve125 leaf proven on real boards at construction).
        "champion_manifests": {
            str(seat): m for seat, a in agents.items()
            if (m := getattr(a, "manifest", None)) is not None
        },
        "config": config,
        "config_hash": C.sha256_of(config)[:16],
        "utc": _now_iso(),
        "result": result,
    }
    record = {"manifest": manifest, "moves": moves, "result": result}
    # content signature (tamper-evident): sha256 over canonical manifest(-sig)+moves
    manifest["signature"] = C.sha256_of({"manifest": manifest, "moves": moves})
    return record


def write_record(record: dict, out_dir: Path, tag: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = record["manifest"]["deck_seed"]
    p = out_dir / f"game_seed{seed}_{tag}.json"
    p.write_text(json.dumps(record, indent=1))
    return p


def play_paired(game, deck_seed, ctor_a, ctor_b, label_a, label_b, config,
                out_dir=None) -> list[dict]:
    """Play the same deck twice, seats swapped: (A@0,B@1) then (B@0,A@1).
    Fresh agent instances per game (no cross-game state leak). Returns both records."""
    recs = []
    for tag, seats, labels in (
        ("a0", {0: ctor_a(), 1: ctor_b()}, {0: label_a, 1: label_b}),
        ("a1", {0: ctor_b(), 1: ctor_a()}, {0: label_b, 1: label_a}),
    ):
        rec = play_game(game, deck_seed, seats, labels, config | {"seat_layout": tag})
        if out_dir:
            write_record(rec, out_dir, tag)
        recs.append(rec)
    return recs


# --------------------------------------------------------------------------- #
def self_test() -> int:
    print("=== play_harness self-test ===")
    from carcassonne_ai.game_wrapper import Game
    game = Game(enable_legal_moves_cache=True)
    seed = 777_000_001
    sims, k_dets = 48, 2   # LIGHT smoke config (NOT production strength)
    print(f"[1] one full fair-vs-fair game  seed={seed} sims={sims} k_dets={k_dets} ...")
    t0 = time.time()

    def ctor_a():
        return _make_fair_agent(game, sims, k_dets, seed=101)

    def ctor_b():
        return _make_fair_agent(game, sims, k_dets, seed=202)

    config = {"sims": sims, "k_dets": k_dets,
              "champion": "puct_priors_v29_bmild_cap8 (champion_factory)",
              "exact_endgame": True, "ruleset": "2p_base_farmers"}
    out_dir = C.REPO_ROOT / "measurement/human_anchor/_selftest_games"
    recs = play_paired(game, seed, ctor_a, ctor_b, "fairA", "fairB", config,
                       out_dir=out_dir)
    dt = time.time() - t0
    r0, r1 = recs
    print(f"    played 2 games in {dt:.1f}s   "
          f"g0 result={r0['result']['scores']} winner_seat={r0['result']['winner_seat']}   "
          f"g1 result={r1['result']['scores']}")

    print("[2] logs + manifests written:")
    for p in sorted(out_dir.glob("game_seed*_a*.json")):
        rec = json.loads(p.read_text())
        m = rec["manifest"]
        paths = {mv["path"] for mv in rec["moves"]}
        print(f"    {p.name}: {len(rec['moves'])} moves  paths={sorted(paths)}  "
              f"agent_version={m['agent_version']}  leaf_hash={m['leaf_hash']}  "
              f"sig={m['signature'][:12]}...")

    print("[3] assertions:")
    # (a) paired rematch reproduced the deck
    assert r0["manifest"]["deck_hash"] == r1["manifest"]["deck_hash"], "deck NOT reproduced!"
    print(f"    deck reproduced: both games deck_hash={r0['manifest']['deck_hash']} OK")
    # (b) both games ran the full game (144 moves for a full base game)
    assert r0["result"]["n_moves"] > 100 and r1["result"]["n_moves"] > 100
    print(f"    full games: n_moves={r0['result']['n_moves']}, {r1['result']['n_moves']} OK")
    # (c) the exact-endgame handoff fired (a latch + >=1 exact move near the end)
    latched = any(mv["path"] == "exact" for mv in r0["moves"])
    print(f"    exact-endgame handoff fired in game0: {latched} "
          f"(latch_k seen: {sorted({mv['latch_k'] for mv in r0['moves'] if mv['latch_k']})})")
    # (d) signature verifies (recompute over manifest-minus-sig + moves)
    m = dict(r0["manifest"])
    sig = m.pop("signature")
    recomputed = C.sha256_of({"manifest": m, "moves": r0["moves"]})
    assert recomputed == sig, "signature does not verify!"
    print("    signature verifies OK")
    # (e) no clairvoyant leak: fair agent's neural_moves stays 0 (harness symmetry)
    assert all(getattr(a(), "neural_moves", 0) == 0 for a in (ctor_a, ctor_b))
    print("=== self-test PASSED ===")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="play_harness")
    ap.add_argument("--self-test", action="store_true", help="RUN one fair-vs-fair game + rematch")
    ap.add_argument("--human", type=int, choices=(0, 1), default=None,
                    help="play as this seat vs the fair champion")
    ap.add_argument("--seed", type=int, default=None, help="deck seed (random if unset)")
    ap.add_argument("--sims", type=int, default=None,
                    help="sims per determinization. DEFAULT = the PRODUCTION.yaml budget "
                         "(fair_deploy.sims_per_det, currently 688). Lower it (e.g. --sims 200) "
                         "ONLY to speed the AI up — that plays a WEAKER-than-champion agent and "
                         "the game log records a runtime_budget_override.")
    ap.add_argument("--k-dets", type=int, default=None,
                    help="determinizations per move. DEFAULT = the PRODUCTION.yaml budget "
                         "(fair_deploy.k_dets, currently 4).")
    ap.add_argument("--c-puct", type=float, default=3.0,
                    help="DEPRECATED / IGNORED (F1): the champion's exploration constant "
                         "(c_puct=1.5) is owned by champion_factory/PRODUCTION.yaml, not this "
                         "flag. Kept only so old invocations do not error.")
    ap.add_argument("--paired", action="store_true", help="play a seat-swapped rematch too")
    ap.add_argument("--out", type=Path, default=C.REPO_ROOT / "measurement/human_anchor/games")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    from carcassonne_ai.champion_factory import load_production_spec
    from carcassonne_ai.game_wrapper import Game
    # Resolve the budget from governance/PRODUCTION.yaml unless the caller overrode it,
    # so a bare `--human 0` plays the CHAMPION budget (k8x1376=11008 since 2026-07-29,
    # was k4x688) and not a weaker stand-in. NOTE: the champion budget got 4x more
    # expensive on that date, and this path is still SEQUENTIAL (see the module docstring's
    # parallel_workers follow-up) — expect ~13.8 s/move, not the deploy split's ~2.2 s.
    _spec = load_production_spec()
    if args.sims is None:
        args.sims = _spec.sims_per_det
    if args.k_dets is None:
        args.k_dets = _spec.k_dets
    game = Game(enable_legal_moves_cache=True)
    seed = args.seed if args.seed is not None else random.randint(1, 2_000_000_000)
    config = {"sims": args.sims, "k_dets": args.k_dets,
              "champion": "puct_priors_v29_bmild_cap8 (champion_factory)",
              "exact_endgame": True, "ruleset": "2p_base_farmers"}

    if args.human is None:
        print("no --human seat and no --self-test: playing fair-vs-fair "
              f"(seed={seed}, sims={args.sims})")

        def ctor_a():
            return _make_fair_agent(game, args.sims, args.k_dets, seed=101)

        def ctor_b():
            return _make_fair_agent(game, args.sims, args.k_dets, seed=202)

        if args.paired:
            play_paired(game, seed, ctor_a, ctor_b, "fairA", "fairB", config, out_dir=args.out)
        else:
            rec = play_game(game, seed, {0: ctor_a(), 1: ctor_b()},
                            {0: "fairA", 1: "fairB"}, config)
            print("wrote", write_record(rec, args.out, "a0"))
        return 0

    # human vs fair champion
    human_seat = args.human
    ai_seat = 1 - human_seat
    human = HumanCLIAgent(game)
    ai = _make_fair_agent(game, args.sims, args.k_dets, seed=303)
    agents = {human_seat: human, ai_seat: ai}
    labels = {human_seat: "human", ai_seat: f"fair@{args.sims}"}
    rec = play_game(game, seed, agents, labels, config)
    p = write_record(rec, args.out, f"human{human_seat}")
    print(f"\n=== GAME OVER === scores={rec['result']['scores']} "
          f"winner_seat={rec['result']['winner_seat']}")
    print("wrote", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
