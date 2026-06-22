#!/usr/bin/env python3
"""Pre-tool audit (Phase 2) — build a unified action-level audit dataset.

Reconstructs each EXACT-SOLVER-LABELLED endgame position (K=2/K=3 greedy suite +
K=4 multi-source expansion), enumerates legal actions, computes CHEAP per-action
quantities that already exist (no new feature engineering, no net), and attaches
the per-position solver labels (per-agent move/regret/match + difficulty) that the
solver runs already persisted.

Sources (all committed data / committed-run share artifacts; cited in the manifest):
  K2/K3 : /mnt/c/carc-shared/l23_regret/g*_k{2,3}.json   (seed+ply+moves+gt, both modes for K2)
  K4    : /mnt/c/carc-shared/l23_k4_expand_probe/*_k4.json (moves+gt) joined by gen_id with
          /mnt/c/carc-shared/l23_k4_expand.jsonl            (state w/ `actions` for replay)

Per-action quantities (mover = player to move at the position):
  imm_score_delta_mover/opp : child.scores - position.scores (captures completion scoring)
  score_diff_after          : child.scores[mover] - child.scores[opp]
  meeple_delta_mover        : child.meeples[mover] - position.meeples[mover] (>=+returns, <=-placed)
  completion_scored         : total board score increased this action (proxy for "completed a feature")
  v27_score                 : virtual_score_v2(child.state, mover) — the v2.7 leaf point-diff estimate
  action_type               : tile / tile_pass / meeple_normal / meeple_farmer / meeple_pass

Solver regret per action is filled ONLY for actions that some agent chose (the only ones
the persisted files scored); other actions get null. (Full per-action regret needs a re-solve.)

Output: ACTION_AUDIT_DATASET.jsonl (one line per position) + ACTION_AUDIT_MANIFEST.json.
"""
from __future__ import annotations

import os

# v2.7 production leaf knobs — MUST be set before importing carcassonne_ai.
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_V25_CAP", "12")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")

import argparse
import glob
import json
import sys
from multiprocessing import Pool

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts", "level2"))

from gen_endgame_positions import replay_to              # noqa: E402
from gen_endgame_multisource import replay_actions        # noqa: E402
from carcassonne_ai.virtual_score_v2 import virtual_score_v2, DEFAULT_CONFIG  # noqa: E402
from carcassonne_ai.action_space import (                 # noqa: E402
    tile_pass_index, meeple_normal_base, DEFAULT_WINDOW_SIZE, tile_action_count,
)

W = DEFAULT_WINDOW_SIZE
TILE_PASS = tile_pass_index(W)         # 2500
MEEPLE_BASE = meeple_normal_base(W)    # 2501
MEEPLE_PASS = MEEPLE_BASE + 9          # 2510


def _action_type(a: int) -> str:
    if a < tile_action_count(W):
        return "tile"
    if a == TILE_PASS:
        return "tile_pass"
    if a == MEEPLE_PASS:
        return "meeple_pass"
    if a < MEEPLE_BASE + 5:
        return "meeple_normal"
    return "meeple_farmer"


def _per_action_features(game, board):
    """Enumerate legal actions; return {action: feature-dict} for the position."""
    mover = board.state.current_player
    opp = 1 - mover
    s0 = list(board.state.scores)
    m0 = list(board.state.meeples)
    legal = np.flatnonzero(game.get_valid_moves(board))
    out = {}
    for a in legal:
        a = int(a)
        child, _ = game.get_next_state(board, a)
        cs = child.state.scores
        out[a] = {
            "action": a,
            "action_type": _action_type(a),
            "imm_score_delta_mover": int(cs[mover] - s0[mover]),
            "imm_score_delta_opp": int(cs[opp] - s0[opp]),
            "score_diff_after": int(cs[mover] - cs[opp]),
            "meeple_delta_mover": int(child.state.meeples[mover] - m0[mover]),
            "completion_scored": bool((cs[0] + cs[1]) > (s0[0] + s0[1])),
            "v27_score": int(virtual_score_v2(child.state, mover, DEFAULT_CONFIG)),
        }
    return mover, out


def _process(task):
    """task = (position_record_dict). Returns the assembled JSONL line dict or {'_error':..}."""
    rec = task
    try:
        if rec["_recon"] == "ply":
            game, board = replay_to(rec["seed"], rec["ply"])
        else:
            game, board = replay_actions(rec["seed"], rec["actions"])
        mover, feats = _per_action_features(game, board)
    except Exception as e:  # reconstruction / scoring failure — record, don't crash the pool
        return {"_error": f"{rec.get('gen_id')}: {type(e).__name__}: {e}", "gen_id": rec.get("gen_id")}

    file_legal = rec.get("legal_n")
    recon_legal = len(feats)
    # attach per-mode agent regrets onto the matching action
    gt = rec["gt"]
    modes_out = {}
    chosen_by = {}            # action -> [agents]
    regret = {"clairvoyant": {}, "marginalized": {}}  # action -> regret
    for mode, g in gt.items():
        if not g or not g.get("solved"):
            modes_out[mode] = None
            continue
        pa = g.get("per_agent", {})
        modes_out[mode] = {
            "value": g.get("value"),
            "n_optimal": g.get("n_optimal"),
            "n_legal": g.get("n_legal"),
            "nodes": g.get("nodes"),
            "secs": g.get("secs"),
            "difficulty": g.get("difficulty"),  # may be None for K2/K3 files
            "per_agent": pa,
        }
        for ag, info in pa.items():
            mv = info.get("move")
            if mv is None:
                continue
            chosen_by.setdefault(int(mv), [])
            if ag not in chosen_by[int(mv)]:
                chosen_by[int(mv)].append(ag)
            regret[mode][int(mv)] = info.get("regret")

    actions = []
    for a in sorted(feats):
        f = dict(feats[a])
        f["chosen_by"] = chosen_by.get(a, [])
        f["solver_regret_clair"] = regret["clairvoyant"].get(a)
        f["solver_regret_marg"] = regret["marginalized"].get(a)
        actions.append(f)

    label_modes = [m for m in ("clairvoyant", "marginalized") if modes_out.get(m)]
    line = {
        "position_id": rec["gen_id"] + f"_k{rec['k_remaining']}",
        "source_bucket": rec["source_bucket"],
        "source_game_seed": rec["seed"],
        "ply": rec.get("ply"),
        "k_remaining": rec["k_remaining"],
        "tiles_remaining": rec.get("bag_size"),
        "to_move": rec.get("to_move", mover),
        "scores": list(board.state.scores),
        "score_diff_mover": int(board.state.scores[mover] - board.state.scores[1 - mover]),
        "in_hand_tile": rec.get("in_hand_tile"),
        "legal_n_file": file_legal,
        "legal_n_recon": recon_legal,
        "recon_ok": (file_legal is None) or (recon_legal == file_legal),
        "label_modes": label_modes,
        "label_kind": "clairvoyant_exact" if label_modes == ["clairvoyant"]
                      else ("clairvoyant+marginalized_exact" if "marginalized" in label_modes else "none"),
        "labels": modes_out,
        "n_actions": len(actions),
        "actions": actions,
    }
    return line


def _load_k23(regret_dir):
    tasks = []
    for f in sorted(glob.glob(os.path.join(regret_dir, "g*_k*.json"))):
        d = json.load(open(f))
        if not d.get("gt"):
            continue
        d["_recon"] = "ply"
        d["source_bucket"] = "greedy_selfplay"
        tasks.append(d)
    return tasks


def _load_k4(probe_dir, state_jsonl):
    # state records keyed by gen_id give us the `actions` replay list
    state = {}
    with open(state_jsonl) as fh:
        for ln in fh:
            r = json.loads(ln)
            state[r["gen_id"]] = r
    tasks = []
    for f in sorted(glob.glob(os.path.join(probe_dir, "*_k4.json"))):
        d = json.load(open(f))
        gid = d.get("gen_id")
        st = state.get(gid)
        if st is None or not d.get("gt"):
            continue
        # only positions the solver actually solved carry usable labels
        if not any(g and g.get("solved") for g in d["gt"].values()):
            continue
        d["_recon"] = "actions"
        d["actions"] = st["actions"]
        d["source_bucket"] = d.get("source_agent", st.get("source_agent")) + "_selfplay"
        tasks.append(d)
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", default="/mnt/c/carc-shared")
    ap.add_argument("--out", default=os.path.join(REPO, "measurement", "pre_tool_audit"))
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    regret_dir = os.path.join(args.share, "l23_regret")
    probe_dir = os.path.join(args.share, "l23_k4_expand_probe")
    state_jsonl = os.path.join(args.share, "l23_k4_expand.jsonl")

    tasks = _load_k23(regret_dir) + _load_k4(probe_dir, state_jsonl)
    print(f"[build] {len(tasks)} labelled positions to reconstruct", flush=True)

    with Pool(args.workers) as p:
        results = p.map(_process, tasks, chunksize=4)

    errors = [r for r in results if "_error" in r]
    lines = [r for r in results if "_error" not in r]
    out_path = os.path.join(args.out, "ACTION_AUDIT_DATASET.jsonl")
    with open(out_path, "w") as fh:
        for ln in sorted(lines, key=lambda x: (x["k_remaining"], x["position_id"])):
            fh.write(json.dumps(ln) + "\n")

    # manifest / coverage
    from collections import Counter
    by_k = Counter(l["k_remaining"] for l in lines)
    by_src = Counter(l["source_bucket"] for l in lines)
    by_label = Counter(l["label_kind"] for l in lines)
    recon_bad = [l["position_id"] for l in lines if not l["recon_ok"]]
    n_actions = sum(l["n_actions"] for l in lines)

    print(f"[build] wrote {len(lines)} positions, {n_actions} action rows -> {out_path}", flush=True)
    print(f"[build] by_k={dict(by_k)} by_src={dict(by_src)}", flush=True)
    print(f"[build] by_label={dict(by_label)}", flush=True)
    print(f"[build] recon mismatches: {len(recon_bad)} {recon_bad[:10]}", flush=True)
    if errors:
        print(f"[build] ERRORS ({len(errors)}): {[e['_error'] for e in errors[:10]]}", flush=True)

    return lines, by_k, by_src, by_label, recon_bad, errors, n_actions


if __name__ == "__main__":
    main()
