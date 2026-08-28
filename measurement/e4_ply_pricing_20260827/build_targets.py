#!/usr/bin/env python3
"""E4 PLY-PRICING — build the pre-registered TARGET PLY SET and the K histogram.

JUDGE-FREE by construction. This script computes NO prices. It only:

  1. replays every E4 archive losslessly under its OWN resolved rules profile
     (`ev_loss.resolve_profile_name` + `prepare_env`; R9 is import-latched so the
     driver runs ONE process per profile group),
  2. joins the Stage A census (`measurement/e4_exploit_grading_20260825/rows.jsonl`)
     onto the replay to name the target plies,
  3. records K (= tiles remaining) and the acting seat at each target ply,
  4. writes `targets.jsonl` + `k_histogram.json`.

The K histogram is what the PRICING-MODE CUT is pre-registered against, so it is
computed and frozen BEFORE any price exists.

Target strata (all selection keys are outcome-blind census fields — no `winner`,
`diff`, `margin` or `scores` is read anywhere in this file):

  invasion    every owner DELIBERATE merge-invasion onset (census `contest` rows
              with invader == 0 and actor == 0).
  farm_capture  every late farm majority switch CAUSED BY an owner move (census
              `farm` rows' `late_switches`, filtered to actor == 0 at that ply).
  defense     for each `invasion` ply p, the champion's most recent TILES-phase
              ply q < p with p - q <= DEFENSE_WINDOW_PLIES. One per invasion,
              de-duplicated.
  control     owner TILES-phase plies that are NOT in any of the above, sampled
              per game with a fixed seed, decile-matched to the invasion set.

Every row also names the ARCHIVE ACTION at that ply (the move actually played),
which is the thing the pricer prices. The champion COUNTERFACTUAL is computed by
`price_plies.py`, not here.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

# --- pre-registered constants (frozen; see PREREG.md) ----------------------- #
DEFENSE_WINDOW_PLIES = 8      # champion ply q defends invasion p iff 0 < p-q <= 8
CONTROL_TARGET_N = 50         # owner non-invasion plies
CONTROL_SEED = 20260827

CENSUS = REPO / "measurement" / "e4_exploit_grading_20260825" / "rows.jsonl"
ARCHIVES = REPO / "measurement" / "e4_games"


def load_census():
    by_row = defaultdict(list)
    for line in CENSUS.open():
        r = json.loads(line)
        by_row[r["row"]].append(r)
    return by_row


def replay_trace(archive_path, profile_name):
    """Per-ply (k_remaining, phase, current_player) for one archive.

    Uses the lossless `(deck_seed, actions)` root-replay contract, threading the
    profile's `game_kwargs()` exactly as `root_replay.replay_actions` documents.
    """
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.resolve(profile_name)
    a = json.loads(Path(archive_path).read_text())
    seed, actions = int(a["deck_seed"]), [int(x) for x in a["actions"]]

    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True,
                **prof.game_kwargs())
    board = game.get_init_board()
    trace = []
    for i, act in enumerate(actions):
        st = board.state
        k = len(st.deck) + (1 if st.next_tile is not None else 0)
        trace.append({
            "ply": i,
            "k": int(k),
            "phase": str(getattr(st.phase, "name", st.phase)).lower(),
            "actor": int(st.current_player),
            "action": int(act),
            "n_legal": int(game.get_valid_moves(board).sum()),
        })
        board, _ = game.get_next_state(board, act)
    return trace, a


def build_for_profile(profile_name, games, census, out_rows, integrity):
    for stem in sorted(games):
        path = ARCHIVES / stem
        trace, arc = replay_trace(path, profile_name)
        by_ply = {t["ply"]: t for t in trace}
        n_plies = len(trace)

        # --- integrity: the replay must reproduce the archive's own scores ---
        integrity.append({"game": stem, "profile": profile_name,
                          "n_plies_archive": len(arc["actions"]),
                          "n_plies_replay": n_plies,
                          "plies_match": len(arc["actions"]) == n_plies})

        flagged = {}          # ply -> stratum

        # --- invasion --------------------------------------------------------
        # ⚠️ ONE MOVE CAN CREATE TWO ONSETS. A single merging tile placement can
        # connect the owner's stub to two different incumbent features, so the
        # census's 90 EVENTS live on fewer distinct PLIES. The ply is the unit of
        # pricing (one move, one price), so events are GROUPED per ply and the
        # per-event fields are summed / carried as a list (DEVIATIONS D-4).
        inv_by_ply: dict[int, dict] = {}
        for r in census["contest"]:
            if r["game"] != stem or r["invader"] != 0 or r["actor"] != 0:
                continue
            p = int(r["ply"])
            if by_ply.get(p) is None:
                continue
            ev = {
                "cls": r["cls"], "mech": r["mech"], "outcome": r["outcome"],
                "n_tiles_at_contest": r["n_tiles_at_contest"],
                "incumbent_tiles_pre": r["incumbent_tiles_pre"],
                "invader_gain": r["invader_gain"],
                "incumbent_denied": r["incumbent_denied"],
                "scored_ply": r["scored_ply"], "scored_kind": r["scored_kind"],
                "feature_pts_final": r["feature_pts_final"],
            }
            inv_by_ply.setdefault(p, {"events": []})["events"].append(ev)
        for p, agg in sorted(inv_by_ply.items()):
            evs = agg["events"]
            flagged[p] = "invasion"
            notes = dict(evs[0])
            notes.update({
                "n_events": len(evs),
                "events": evs,
                "invader_gain": sum(e["invader_gain"] for e in evs),
                "incumbent_denied": sum(e["incumbent_denied"] for e in evs),
                "cls": evs[0]["cls"] if len(evs) == 1
                       else sorted({e["cls"] for e in evs}),
            })
            out_rows.append(_row(stem, profile_name, by_ply[p], n_plies,
                                 "invasion", notes))

        # --- farm_capture ----------------------------------------------------
        for r in census["farm"]:
            if r["game"] != stem:
                continue
            for sw in (r.get("late_switches") or []):
                p = int(sw["ply"])
                t = by_ply.get(p)
                if t is None or t["actor"] != 0:
                    continue
                if p in flagged:          # already an invasion ply: no double count
                    continue
                flagged[p] = "farm_capture"
                out_rows.append(_row(stem, profile_name, t, n_plies, "farm_capture", {
                    "cls": "farm", "switch_from": sw["from"], "switch_to": sw["to"],
                    "farm_n_tiles": r["n_tiles"], "farm_pts": r["pts"],
                    "farm_pts_p0": r["pts_p0"], "farm_pts_p1": r["pts_p1"],
                    "final_maj": r["final_maj"],
                }))

        # --- defense ---------------------------------------------------------
        invasion_plies = sorted(p for p, s in flagged.items() if s == "invasion")
        champ_tile_plies = [t["ply"] for t in trace
                            if t["actor"] == 1 and t["phase"] == "tiles"]
        seen_def = set()
        for p in invasion_plies:
            prior = [q for q in champ_tile_plies if q < p]
            if not prior:
                continue
            q = prior[-1]
            if p - q > DEFENSE_WINDOW_PLIES or q in seen_def:
                continue
            seen_def.add(q)
            out_rows.append(_row(stem, profile_name, by_ply[q], n_plies, "defense", {
                "defends_invasion_ply": p, "gap_plies": p - q,
            }))

        # --- control ---------------------------------------------------------
        rng = random.Random(CONTROL_SEED ^ (hash(stem) & 0xFFFFFFFF))
        pool = [t for t in trace
                if t["actor"] == 0 and t["phase"] == "tiles"
                and t["ply"] not in flagged and t["n_legal"] > 1]
        # decile-match to this game's invasion plies; fall back to uniform
        want = max(1, round(CONTROL_TARGET_N / 50.0 * max(1, len(invasion_plies))))
        picks = []
        if invasion_plies and pool:
            for p in invasion_plies:
                dec = min(9, int(10 * p / max(1, n_plies)))
                same = [t for t in pool
                        if min(9, int(10 * t["ply"] / max(1, n_plies))) == dec
                        and t["ply"] not in {x["ply"] for x in picks}]
                cand = same or [t for t in pool
                                if t["ply"] not in {x["ply"] for x in picks}]
                if cand:
                    picks.append(rng.choice(cand))
        elif pool:
            picks = rng.sample(pool, min(want, len(pool)))
        for t in picks:
            out_rows.append(_row(stem, profile_name, t, n_plies, "control", {}))


def _row(stem, profile, t, n_plies, stratum, notes):
    return {
        "game": stem, "profile": profile, "stratum": stratum,
        "ply": t["ply"], "k": t["k"], "phase": t["phase"], "actor": t["actor"],
        "played_action": t["action"], "n_legal": t["n_legal"],
        "n_plies": n_plies, "ply_frac": t["ply"] / max(1, n_plies),
        "notes": notes,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # R9 must be latched BEFORE carcassonne_ai imports the deck.
    from analyzer.ev_loss import prepare_env, resolve_profile_name
    env = prepare_env(args.profile)

    census = load_census()
    games = [r["game"] for r in census["game"]]
    mine = []
    for stem in games:
        arc = json.loads((ARCHIVES / stem).read_text())
        if resolve_profile_name(arc) == args.profile:
            mine.append(stem)

    rows, integrity = [], []
    build_for_profile(args.profile, mine, census, rows, integrity)

    out = Path(args.out)
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    meta = {
        "profile": args.profile, "env": env, "n_games": len(mine),
        "n_rows": len(rows),
        "by_stratum": dict(Counter(r["stratum"] for r in rows)),
        "k_histogram": dict(sorted(Counter(r["k"] for r in rows).items())),
        "defense_window_plies": DEFENSE_WINDOW_PLIES,
        "control_seed": CONTROL_SEED,
        "integrity": integrity,
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: v for k, v in meta.items() if k != "integrity"}, indent=1))


if __name__ == "__main__":
    main()
