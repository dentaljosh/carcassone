#!/usr/bin/env python3
"""End-to-end smoke for the remote-opponent server — no phone required.

Plays a whole game against a running `scripts/carcasum_remote/server.py` the way
the phone does: our engine is the game of record on this side too, the client
picks RANDOM LEGAL moves for the human seat, and every opponent move comes back
over HTTP. It then proves three things that the unit tests cannot:

1. **The game completes** — every opponent move inverted onto one of our legal
   actions, no `VOID_UNMAPPABLE`, no stall.
2. **The log is lossless** — the final `(deck_seed, actions)` pair replays to the
   same scores through `match.replay_actions`, i.e. what the phone would archive
   is exactly what was played (the root_replay contract the E4 archives rest on).
3. **Retry is idempotent** — `--blip-every N` re-sends every Nth request verbatim
   before applying anything and asserts byte-identical answers. That is the
   network-failure property, tested rather than asserted.

    scripts/carcasum_remote/smoke_client.py --url http://100.109.88.103:8971 \
        --deck-seed 4242 --human-seat 0 --blip-every 5

⚠️ At the calibrated 5000 ms budget one smoke game costs ~35 opponent turns x
5 CPU-seconds ~= 3 minutes of thinking plus our own moves. For a plumbing check
use the server's `--budget-ms 50`; for a CONDITIONS check use 5000 and say which
you ran.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _post(url: str, path: str, body: dict, timeout: float) -> tuple[int, dict]:
    req = urllib.request.Request(                                # noqa: S310
        url.rstrip("/") + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as fh:  # noqa: S310
            return fh.status, json.loads(fh.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def _get(url: str, path: str, timeout: float) -> dict:
    with urllib.request.urlopen(                                  # noqa: S310
            url.rstrip("/") + path, timeout=timeout) as fh:
        return json.loads(fh.read().decode())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", required=True)
    ap.add_argument("--deck-seed", type=int, default=4242)
    ap.add_argument("--human-seat", type=int, default=0, choices=(0, 1))
    ap.add_argument("--game-id", default=None)
    ap.add_argument("--policy-seed", type=int, default=7)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--blip-every", type=int, default=0,
                    help="re-send every Nth /move verbatim first and require an "
                         "identical answer (0 = off)")
    ap.add_argument("--max-plies", type=int, default=400)
    args = ap.parse_args(argv)

    for p in (SCRIPTS, SCRIPTS / "carcasum_match"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import match as M                                             # noqa: PLC0415

    M.export_profile_env()
    from carcassonne_ai import rules_profile                      # noqa: PLC0415
    from carcassonne_ai.game_wrapper import Game                  # noqa: PLC0415

    health = _get(args.url, "/health", timeout=30)
    print(f"server: gate={health['gate']['state']} sha={health['gate']['sha256'][:12]} "
          f"probe_city={health['gate']['probe']['tiny_city_score']} "
          f"opponent={health['opponent']['budget_ms']}ms "
          f"profile={health['profile']}")

    prof = rules_profile.activate(M.PROFILE)
    random.seed(int(args.deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()

    rng = random.Random(int(args.policy_seed))
    human, ai = int(args.human_seat), 1 - int(args.human_seat)
    game_id = args.game_id or f"smoke-{args.deck_seed}-{int(time.time())}"
    actions: list[int] = []
    n_remote = 0
    n_blips = 0
    t0 = time.time()

    while game.get_game_ended(board, 0) == 0 and len(actions) < args.max_plies:
        if int(board.state.current_player) == human:
            mask = game.get_valid_moves(board)
            legal = [i for i, v in enumerate(mask) if v]
            if not legal:
                raise SystemExit(f"no legal action for the human at ply {len(actions)}")
            a = int(rng.choice(legal))
            board, _ = game.get_next_state(board, a)
            actions.append(a)
            continue

        body = {"game_id": game_id, "deck_seed": int(args.deck_seed),
                "human_seat": human, "actions": list(actions)}
        n_remote += 1
        first = None
        if args.blip_every and n_remote % args.blip_every == 0:
            # Simulate a lost RESPONSE: the server has already decided and
            # committed the move; the client never saw it and asks again.
            code, first = _post(args.url, "/move", body, args.timeout)
            if code != 200:
                raise SystemExit(f"blip probe failed {code}: {first}")
            n_blips += 1
        code, resp = _post(args.url, "/move", body, args.timeout)
        if code != 200:
            raise SystemExit(f"/move failed {code}: {json.dumps(resp)}")
        if first is not None and first != resp:
            raise SystemExit("RETRY NOT IDEMPOTENT — two identical requests got "
                             f"different answers:\n {json.dumps(first)}\n "
                             f"{json.dumps(resp)}")
        if resp.get("game_over") and resp.get("action") is None:
            print("server says game_over before our board ended:", json.dumps(resp))
            break
        a = int(resp["action"])
        if int(resp["seat"]) != ai:
            raise SystemExit(f"server returned a seat-{resp['seat']} action at "
                             f"ply {len(actions)}; expected seat {ai}")
        mask = game.get_valid_moves(board)
        if not (0 <= a < len(mask)) or not mask[a]:
            raise SystemExit(f"server returned action {a}, illegal on our board at "
                             f"ply {len(actions)}")
        board, _ = game.get_next_state(board, a)
        actions.append(a)

    wall = time.time() - t0
    ended = game.get_game_ended(board, 0) != 0
    scores = list(board.state.scores)
    rp = M.replay_actions(int(args.deck_seed), actions, M.PROFILE)
    replay_ok = bool(rp["ok"] and rp["scores"] == scores)

    # The final log goes with /end: when OUR side plays the terminating ply
    # there is no further /move, so this is how the server learns about it and
    # gets to finish (and audit) the game.
    code, fin = _post(args.url, "/end",
                      {"game_id": game_id, "actions": actions}, timeout=120)
    rec = (fin or {}).get("record") or {}

    out = {
        "ok": bool(ended and replay_ok and not rec.get("void")),
        "game_id": game_id, "deck_seed": int(args.deck_seed), "human_seat": human,
        "ended": ended, "n_actions": len(actions), "scores": scores,
        "human_score": scores[human] if scores else None,
        "carcasum_score": scores[ai] if scores else None,
        "margin_human_minus_carcasum": (scores[human] - scores[ai]) if scores else None,
        "replay_ok": replay_ok, "replay_scores": rp.get("scores"),
        "remote_calls": n_remote, "idempotence_probes": n_blips,
        "wall_s": round(wall, 1),
        "server_scores": rec.get("scores"),
        "server_carcasum_reported_scores": rec.get("carcasum_reported_scores"),
        "server_final_agree": rec.get("final_agree"),
        "server_void": rec.get("void"), "server_void_detail": rec.get("void_detail"),
        "server_real_divergences": rec.get("real"),
        "server_counts": rec.get("counts"),
        "opp_driver_playouts_per_turn": rec.get("opp_driver_playouts_per_turn"),
        "opp_driver_ms_per_turn": rec.get("opp_driver_ms_per_turn"),
    }
    if rec.get("scores") is not None and list(rec["scores"]) != scores:
        out["ok"] = False
        out["error"] = "client and server disagree on the final scores"
    print(json.dumps(out, indent=1))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
