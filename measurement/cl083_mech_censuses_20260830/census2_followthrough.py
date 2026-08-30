#!/usr/bin/env python3
"""CENSUS 2 (CF-M1): does the champion ABANDON its own setups more than the owner?

Pure rules replay of `measurement/e4_games/*.json` -- BOTH seats. No search, no net,
no judge (CL-085: this census is judge-free by construction).

Definitions are FROZEN in PREREG.md, committed before this file ran:

  SETUP      a meeple claim, at its claim ply, of an UNFINISHED (open_n >= 1)
             CITY or ROAD component. Farms (no completion move) and cloisters
             (completed by neighbours, not by a directed extension) are excluded.
  WINDOW     N = 12 plies after the claim (primary); N = 6 and N = 20 declared
             in advance as robustness rungs.
  OWN FOLLOW-THROUGH   >=1 tile ply INSIDE the window whose actor is the claimer
             and at which the component's tile count increases. Exactly one tile is
             placed per tile ply, so the attribution is exact.
  ABANDONED  no own follow-through AND the component never finished inside the
             window AND it still has >=1 open edge at the end of the window.
  CENSORED   window would run past the last ply -> dropped from the primary.

FEATURE IDENTITY ACROSS MERGES: a global union-find is built over the WHOLE game
first (pass 1), then every ply's components are re-grouped by their final UF id
(pass 2), so a component that later merges is one feature throughout. Tile counts
are the size of the coordinate SET of the group -- never a sum of part sizes, which
would double-count a tile hosting two segments that later merge.

R9 is import-latched -> ONE PROFILE GROUP PER PROCESS (`--profile`).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

#: Overridable so the script can be SHIPPED to a box without being written into
#: that box's pinned checkout (see PREREG "shared inputs").
REPO = Path(os.environ.get("CARC_REPO") or Path(__file__).resolve().parents[2])
for sub in ("scripts/analyzer", "scripts/measurement_infra",
            "measurement/e4_exploit_grading_20260825"):
    sys.path.insert(0, str(REPO / sub))

import ev_loss  # noqa: E402  -- MUST be the first carcassonne_ai-touching import

SCHEMA = "carcassonne-cl083-census2/v1"
WINDOWS = (6, 12, 20)          # PREREG: 12 primary, 6 and 20 declared robustness rungs
PRIMARY_N = 12


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        r = x
        while self.p[r] != r:
            r = self.p[r]
        while self.p[x] != r:
            self.p[x], x = r, self.p[x]
        return r

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def _sname(side) -> str:
    return getattr(side, "name", str(side))


def ply_components(state, flat_leaf):
    """CITY and ROAD components of one state.

    Returns rep -> {cls, keys, coords, finished, open_n}. Reps and key naming match
    `stage_a_census.snapshot` so the two censuses speak the same feature language.
    Farms are deliberately absent (PREREG: out of scope for follow-through).
    """
    decomp = flat_leaf.decompose(state)
    out = {}

    for cls, side_root, root_coords, root_fin, root_open, tag in (
        ("city", decomp.city_side_root, decomp.city_root_coords,
         decomp.city_root_finished, decomp.city_root_open_n, "C"),
        ("road", decomp.road_side_root, decomp.road_root_coords,
         decomp.road_root_finished, decomp.road_root_open_n, "R"),
    ):
        keys_by_root = defaultdict(list)
        for (r, c, side), root in side_root.items():
            keys_by_root[root].append((tag, r, c, _sname(side)))
        for root, keys in keys_by_root.items():
            kk = sorted(keys)
            out[kk[0]] = {
                "cls": cls, "keys": kk,
                "coords": {(r, c) for (r, c) in root_coords[root]},
                "finished": bool(root_fin[root]),
                "open_n": int(root_open.get(root, 0)),
            }
    return out


def meeple_keys(state, flat_leaf):
    """positional meeple keys -> (player, feature positional key or None)."""
    import stage_a_census as SAC
    decomp = flat_leaf.decompose(state)
    out = {}
    for p in range(state.players):
        for mp in state.placed_meeples[p]:
            cws = mp.coordinate_with_side
            k = (p, cws.coordinate.row, cws.coordinate.column,
                 _sname(cws.side), mp.meeple_type.name)
            out[k] = (p, SAC.meeple_component_key(mp, state, decomp, flat_leaf))
    return out


def census_game(path, profile_name):
    from carcassonne_ai import flat_leaf, rules_profile
    from carcassonne_ai.game_wrapper import Game

    arch = ev_loss.load_archive(path)
    prof = rules_profile.activate(profile_name)
    actions = arch["actions"]
    deck_seed = arch["deck_seed"]
    human = int(arch["human_player"])

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()

    n_plies = len(actions)
    per_ply = []          # ply -> {"actor","phase","comps","mkeys"}
    uf = UF()
    prev_mkeys = set()

    # ---------------- pass 1: replay, snapshot, accumulate the global UF -------- #
    for ply, a in enumerate(actions):
        st = board.state
        actor = int(st.current_player)
        phase = st.phase.value
        board, _ = game.get_next_state(board, int(a))
        comps = ply_components(board.state, flat_leaf)
        for rec in comps.values():
            base = rec["keys"][0]
            for k in rec["keys"][1:]:
                uf.union(base, k)
        mk = meeple_keys(board.state, flat_leaf)
        per_ply.append({"actor": actor, "phase": phase, "comps": comps, "mkeys": mk})
        prev_mkeys = set(mk)

    rec_scores = arch.get("recorded_scores")
    recon_ok = (rec_scores is None
                or list(board.state.scores) == list(rec_scores))

    # ---------------- pass 2: regroup every ply by FINAL UF id ------------------ #
    grouped = []          # ply -> gid -> {cls, coords, finished, open_n}
    for rec in per_ply:
        g = {}
        for comp in rec["comps"].values():
            gid = uf.find(comp["keys"][0])
            e = g.setdefault(gid, {"cls": comp["cls"], "coords": set(),
                                   "finished": True, "open_n": 0})
            e["coords"] |= comp["coords"]
            e["finished"] = e["finished"] and comp["finished"]
            e["open_n"] += comp["open_n"]
        for e in g.values():
            e["n_tiles"] = len(e["coords"])
        grouped.append(g)

    # ---------------- setups: newly placed meeples on unfinished city/road ------ #
    setups = []
    prev = set()
    for ply, rec in enumerate(per_ply):
        cur = set(rec["mkeys"])
        for k in sorted(cur - prev):
            player, fk = rec["mkeys"][k]
            if fk is None or fk[0] not in ("C", "R"):
                continue                      # cloister / farm -> out of scope
            gid = uf.find(fk)
            e = grouped[ply].get(gid)
            if e is None or e["finished"] or e["open_n"] < 1:
                continue                      # not a setup: already complete/closed
            setups.append({
                "ply": ply, "player": player, "gid": gid, "cls": e["cls"],
                "size_at_claim": e["n_tiles"], "open_at_claim": e["open_n"],
            })
        prev = cur

    # ---------------- evaluate each setup in each declared window --------------- #
    rows = []
    for s in setups:
        row = {
            "row": "setup", "game": Path(path).name, "profile": profile_name,
            "n_plies": n_plies, "human_player": human,
            "seat": ("owner" if s["player"] == human else "champion"),
            "ply": s["ply"], "ply_frac": s["ply"] / n_plies,
            "player": s["player"], "cls": s["cls"],
            "size_at_claim": s["size_at_claim"], "open_at_claim": s["open_at_claim"],
            "rules_profile": profile_name,
            "budget_note": arch["provenance"].get("budget_note"),
            "sims_effective": arch.get("sims_effective"),
            "k_dets_effective": arch.get("k_dets_effective"),
        }
        for N in WINDOWS:
            end = s["ply"] + N
            censored = end >= n_plies
            own = opp = 0
            finished_in_window = False
            live_at_end = None
            for u in range(s["ply"] + 1, min(end, n_plies - 1) + 1):
                e_now = grouped[u].get(s["gid"])
                e_prev = grouped[u - 1].get(s["gid"])
                if e_now is None:
                    continue
                if e_now["finished"]:
                    finished_in_window = True
                grew = (e_prev is None) or (e_now["n_tiles"] > e_prev["n_tiles"])
                if grew and e_prev is not None:
                    if per_ply[u]["actor"] == s["player"]:
                        own += 1
                    else:
                        opp += 1
                live_at_end = e_now
            if live_at_end is None:
                live_at_end = grouped[s["ply"]].get(s["gid"])
            still_open = bool(live_at_end and not live_at_end["finished"]
                              and live_at_end["open_n"] >= 1)
            row[f"w{N}"] = {
                "censored": bool(censored),
                "own_growth": own, "opp_growth": opp,
                "finished_in_window": bool(finished_in_window),
                "still_open_at_end": still_open,
                "eligible": bool(not censored),
                "abandoned": bool(not censored and own == 0
                                  and not finished_in_window and still_open),
            }
        rows.append(row)

    return {"rows": rows, "recon_ok": recon_ok, "n_plies": n_plies,
            "game": Path(path).name, "human_player": human,
            "final_scores": list(board.state.scores),
            "recorded_scores": (list(rec_scores) if rec_scores else None),
            "n_setups": len(setups)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games-dir", default=str(REPO / "measurement/e4_games"))
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    paths = sorted(Path(a.games_dir).glob("*.json"))
    keep = []
    for p in paths:
        arch = json.loads(p.read_text())
        if not arch.get("ok", True):
            continue
        if ev_loss.resolve_profile_name(arch) == a.profile:
            keep.append(p)
    if a.limit:
        keep = keep[: a.limit]
    print(f"[census2] profile={a.profile} archives={len(keep)}", flush=True)
    ev_loss.prepare_env(a.profile)

    t0 = time.time()
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    n_bad = 0
    with outp.open("w") as fh:
        for i, p in enumerate(keep, 1):
            g = census_game(str(p), a.profile)
            n_bad += int(not g["recon_ok"])
            fh.write(json.dumps({"row": "game", "schema": SCHEMA,
                                 "game": g["game"], "profile": a.profile,
                                 "recon_ok": g["recon_ok"], "n_plies": g["n_plies"],
                                 "human_player": g["human_player"],
                                 "final_scores": g["final_scores"],
                                 "recorded_scores": g["recorded_scores"],
                                 "n_setups": g["n_setups"]}) + "\n")
            for r in g["rows"]:
                fh.write(json.dumps(r) + "\n")
            print(f"[census2] {i}/{len(keep)} {g['game']} setups={g['n_setups']} "
                  f"recon_ok={g['recon_ok']}", flush=True)
    print(f"[census2] DONE recon_failures={n_bad} in {time.time()-t0:.1f}s -> {outp}",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
