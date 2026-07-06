"""Window-overflow audit — replay archived games, measure drop rates.

Loads one or more games.jsonl files (deck_seed + full action_sequence),
replays each ply-by-ply, and at every decision records how many legal actions
the centered W=25 window drops (n_overflow) and how many placed tiles fall
outside it (n_oow_tiles), via the CARCASSONNE_WINDOW_AUDIT instrumentation in
game_wrapper. Aggregates by phase and game-stage and writes a JSON summary plus
a list of dropped-decision refs for the downstream deep-search check.

Run with the production leaf env set and CARCASSONNE_WINDOW_AUDIT=1.
"""
import argparse
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "scripts" / "measurement_infra"))

from carcassonne_ai.action_space import WindowOverflowError
from carcassonne_ai.game_wrapper import Game, drain_window_audit, window_audit_enabled
from root_replay import GameRecord  # noqa: E402


def tolerant_load(path):
    """Like root_replay.load_games but tolerant of the l23_k4 schema, which uses
    `seed` (not deck_seed) and `gen_id` (not game_id)."""
    out = []
    for i, line in enumerate(Path(path).read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if "deck_seed" in o:
            seed = int(o["deck_seed"])
        elif "seed" in o:
            seed = int(o["seed"])
        elif "source_game_seed" in o:
            seed = int(o["source_game_seed"])
        else:
            raise KeyError(f"no seed field in {path} line {i}: {list(o)[:6]}")
        actions = [int(a) for a in o["actions"]]
        gid = o.get("game_id", o.get("gen_id", i))
        try:
            gid = int(gid)
        except (TypeError, ValueError):
            gid = i
        meta = {k: v for k, v in o.items()
                if k not in ("game_id", "gen_id", "deck_seed", "seed", "actions", "n_plies")}
        out.append(GameRecord(gid, seed, actions, int(o.get("n_plies", len(actions))), meta))
    return out


def _stage(k_remaining: int) -> str:
    if k_remaining >= 49:
        return "opening"
    if k_remaining >= 25:
        return "mid"
    return "endgame"


def audit_games(games, max_plies_cap=None, reservoir_size=400):
    """Replay a list of GameRecord, return an aggregate dict."""
    _res_rng = random.Random(12345)
    dropped_sample = []      # reservoir of dropped decisions WITH full context
    _n_dropped_seen = 0
    n_games = 0
    n_replay_fail = 0
    n_decisions = 0
    n_all_overflow_decisions = 0
    games_with_overflow = 0
    games_with_oow_tile = 0
    decisions_with_drop = 0
    decisions_with_oow_tile = 0
    total_dropped_actions = 0
    total_oow_tiles = 0
    phase_decisions = Counter()          # phase -> total decisions
    phase_drop_decisions = Counter()     # phase -> decisions with >=1 drop
    stage_decisions = Counter()          # stage -> total decisions
    stage_drop_decisions = Counter()     # stage -> decisions with >=1 drop
    noverflow_hist = Counter()           # n_overflow value -> count of decisions
    noow_hist = Counter()                # n_oow_tiles value -> count of decisions
    dropped_refs = []                    # (game_id, deck_seed, ply, phase, k_remaining, n_overflow)

    game = Game(window_size=25, enable_legal_moves_cache=False)

    for rec in games:
        random.seed(int(rec.deck_seed))
        try:
            board = game.get_init_board()
        except Exception:
            n_replay_fail += 1
            continue
        drain_window_audit()  # clear anything stray
        game_had_overflow = False
        game_had_oow = False
        ply = 0
        ok = True
        actions = rec.actions
        for a in actions:
            if game.get_game_ended(board, board.state.current_player) != 0.0:
                break
            try:
                _ = game.get_valid_moves(board)
            except WindowOverflowError:
                # All legal actions overflowed at this decision (should not
                # happen on a real archived game — it would have been dropped).
                n_all_overflow_decisions += 1
                recs = drain_window_audit()
                # still recorded (audit block runs before the raise)
                for r in recs:
                    n_decisions += 1
                break
            recs = drain_window_audit()
            # exactly one record for this decision
            for r in recs:
                n_decisions += 1
                phase = r["phase"]
                stg = _stage(r["k_remaining"])
                phase_decisions[phase] += 1
                stage_decisions[stg] += 1
                noverflow_hist[r["n_overflow"]] += 1
                noow_hist[r["n_oow_tiles"]] += 1
                if r["n_overflow"] > 0:
                    decisions_with_drop += 1
                    total_dropped_actions += r["n_overflow"]
                    phase_drop_decisions[phase] += 1
                    stage_drop_decisions[stg] += 1
                    game_had_overflow = True
                    if len(dropped_refs) < 20000:
                        dropped_refs.append({
                            "game_id": int(rec.game_id),
                            "deck_seed": int(rec.deck_seed),
                            "ply": ply,
                            "phase": phase,
                            "k_remaining": r["k_remaining"],
                            "n_overflow": r["n_overflow"],
                        })
                    # Reservoir-sample dropped decisions WITH full context so the
                    # downstream deep-search check is self-contained.
                    entry = {
                        "game_id": int(rec.game_id),
                        "deck_seed": int(rec.deck_seed),
                        "actions": [int(x) for x in actions],
                        "ply": ply,
                        "phase": phase,
                        "k_remaining": r["k_remaining"],
                        "n_overflow": r["n_overflow"],
                    }
                    _n_dropped_seen += 1
                    if len(dropped_sample) < reservoir_size:
                        dropped_sample.append(entry)
                    else:
                        j = _res_rng.randint(0, _n_dropped_seen - 1)
                        if j < reservoir_size:
                            dropped_sample[j] = entry
                if r["n_oow_tiles"] > 0:
                    decisions_with_oow_tile += 1
                    total_oow_tiles += r["n_oow_tiles"]
                    game_had_oow = True
            # advance
            try:
                board, _ = game.get_next_state(board, int(a))
            except Exception:
                ok = False
                break
            ply += 1
            if max_plies_cap and ply >= max_plies_cap:
                break
        n_games += 1
        if not ok:
            n_replay_fail += 1
        if game_had_overflow:
            games_with_overflow += 1
        if game_had_oow:
            games_with_oow_tile += 1

    return {
        "n_games": n_games,
        "n_replay_fail": n_replay_fail,
        "n_decisions": n_decisions,
        "n_all_overflow_decisions": n_all_overflow_decisions,
        "games_with_overflow": games_with_overflow,
        "games_with_oow_tile": games_with_oow_tile,
        "decisions_with_drop": decisions_with_drop,
        "decisions_with_oow_tile": decisions_with_oow_tile,
        "total_dropped_actions": total_dropped_actions,
        "total_oow_tiles": total_oow_tiles,
        "phase_decisions": dict(phase_decisions),
        "phase_drop_decisions": dict(phase_drop_decisions),
        "stage_decisions": dict(stage_decisions),
        "stage_drop_decisions": dict(stage_drop_decisions),
        "noverflow_hist": {str(k): v for k, v in sorted(noverflow_hist.items())},
        "noow_hist": {str(k): v for k, v in sorted(noow_hist.items())},
        "dropped_refs": dropped_refs,
        "dropped_sample": dropped_sample,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("games", nargs="+", help="games.jsonl file(s)")
    ap.add_argument("--max-games", type=int, default=None)
    ap.add_argument("--out", default="measurement/window_audit/audit_result.json")
    args = ap.parse_args()

    assert window_audit_enabled(), "CARCASSONNE_WINDOW_AUDIT must be 1"

    all_games = []
    for p in args.games:
        gs = tolerant_load(p)
        for g in gs:
            g.meta["_src"] = os.path.basename(p)
        all_games.extend(gs)
        print(f"loaded {len(gs)} games from {p}")
    if args.max_games:
        all_games = all_games[: args.max_games]
    print(f"total games to audit: {len(all_games)}")

    res = audit_games(all_games)
    res["source_files"] = args.games
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    # Trim dropped_refs / dropped_sample from the on-disk summary; keep sidecars.
    refs = res.pop("dropped_refs")
    sample = res.pop("dropped_sample")
    with open(args.out, "w") as fh:
        json.dump(res, fh, indent=2)
    with open(args.out.replace(".json", "_dropped_refs.json"), "w") as fh:
        json.dump(refs, fh)
    with open(args.out.replace(".json", "_dropped_sample.json"), "w") as fh:
        json.dump(sample, fh)
    # Print headline
    nd = res["n_decisions"]
    ng = res["n_games"]
    print("=== WINDOW AUDIT ===")
    print(f"games={ng} decisions={nd}")
    if ng:
        print(f"% games with any overflow: {100*res['games_with_overflow']/ng:.3f}%")
        print(f"% games with any oow tile: {100*res['games_with_oow_tile']/ng:.3f}%")
    if nd:
        print(f"% decisions dropping a legal action: {100*res['decisions_with_drop']/nd:.4f}% "
              f"({res['decisions_with_drop']}/{nd})")
        print(f"% decisions with oow placed tile:    {100*res['decisions_with_oow_tile']/nd:.4f}% "
              f"({res['decisions_with_oow_tile']}/{nd})")
    print(f"total dropped legal actions: {res['total_dropped_actions']}")
    print(f"total oow placed tiles:      {res['total_oow_tiles']}")
    print(f"all-overflow (raise) decisions: {res['n_all_overflow_decisions']}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
