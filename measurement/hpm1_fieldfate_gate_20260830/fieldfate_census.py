#!/usr/bin/env python3
"""HP-M1 KILL GATE -- bag-conditioned field-fate census (row extraction).

Prereg: measurement/hpm1_fieldfate_gate_20260830/PREREG.md (frozen 2026-08-30).

WHAT THIS DOES
    One row per FARMER deployment, with
      * the FATE label  (realized_pts > 0) -- from the BANKED Stage-A union-find
        replay kernel (`stage_a_census.census_game`, imported VERBATIM, not
        forked), so the award attribution and its per-ply reconciliation against
        the engine's own `state.scores` are bit-identical to the banked census;
      * the BAG-CONDITIONED features at the CLAIM PLY -- from a SECOND,
        deterministic replay of the same action sequence that stops at exactly
        the plies pass 1 identified as farmer claims.

    Two passes rather than one modified pass is deliberate: it means the fate
    label comes out of unmodified banked code, so this instrument cannot
    silently diverge from the census the 46.2%/5.4% numbers came from.
    `tests/test_hpm1_fieldfate.py` asserts the two passes agree.

JUDGE-FREE: no search, no net, no evaluator scoring positions. The only "judge"
is the engine's own realized end-of-game award (CL-085).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

REPO = os.environ.get("HPM1_REPO", "/home/doctor/projects/carcassone")
STAGE_A = os.environ.get(
    "HPM1_STAGE_A", REPO + "/measurement/e4_exploit_grading_20260825")

# production leaf knobs FIRST (pure os.environ; touches no carcassonne_ai module)
sys.path.insert(0, REPO + "/scripts/human_anchor")
import env_preamble  # noqa: E402,F401

sys.path.insert(0, REPO + "/scripts/analyzer")
import ev_loss  # noqa: E402  -- MUST precede any carcassonne_ai-touching import

sys.path.insert(0, STAGE_A)
import stage_a_census as SA  # noqa: E402  -- the BANKED kernel, unmodified


# --------------------------------------------------------------------------- #
# tile classes -- derived mechanically from the engine's own tile set          #
# --------------------------------------------------------------------------- #
def tile_class_table() -> dict:
    """description -> {count, ce, fr, ch}. See PREREG 3.2. No hand curation."""
    from wingedsheep.carcassonne.objects.side import Side
    from wingedsheep.carcassonne.tile_sets.base_deck import (base_tile_counts,
                                                             base_tiles)
    card = (Side.TOP, Side.RIGHT, Side.BOTTOM, Side.LEFT)
    out = {}
    for name, cnt in base_tile_counts.items():
        t = base_tiles[name]
        cs = set()
        for grp in (t.city or []):
            for s in grp:
                if s in card:
                    cs.add(s)
        out[name] = {"count": int(cnt), "ce": len(cs),
                     "fr": len(t.farms or []), "ch": int(bool(t.chapel))}
    return out


def class_key(a: dict) -> str:
    return f"CE{a['ce']}_FR{a['fr']}_CH{a['ch']}"


# --------------------------------------------------------------------------- #
# feature names -- FROZEN ORDER (PREREG 3.3)                                   #
# --------------------------------------------------------------------------- #
def feature_names(tct: dict) -> list:
    classes = sorted({class_key(a) for a in tct.values()})
    names = ["bag_n"]
    names += [f"bag_ce{k}" for k in range(5)]
    names += [f"bag_fr{k}" for k in range(5)]
    names += ["bag_chapel"]
    names += [f"bag_cls_{c}" for c in classes]
    names += [f"bag_ge{k}" for k in range(1, 5)]
    names += ["field_tiles", "field_adj_cities", "field_finished_cities",
              "field_unfinished_cities", "field_unfin_open_edges",
              "field_entry_cells", "own_w", "opp_w",
              "own_meeples_left", "opp_meeples_left", "ply_frac"]
    names += ["bag_closable_unfin", "bag_closable_pts", "proj_finished_cities",
              "entry_supply", "invade_risk", "invade_pressure"]
    return names


# --------------------------------------------------------------------------- #
# the bag                                                                       #
# --------------------------------------------------------------------------- #
def board_counts(state) -> Counter:
    c = Counter()
    for row in state.board:
        for tile in row:
            if tile is not None:
                c[tile.description] += 1
    return c


def full_multiset(state) -> Counter:
    """The game's COMPLETE tile multiset, read once at ply 0.

    = tiles already on the board (the start tile, incl. the retail pre-placed one
    that was never drawn) + the deck + the in-hand tile. Only the MULTISET is
    read, never the order: the distribution of tiles in a Carcassonne box is
    public knowledge, the shuffle is not. Deriving it from the game rather than
    from `base_tile_counts` makes it correct under every rules profile
    (`fixed_start_tile` places a 73rd tile that was never in the deck)."""
    c = board_counts(state)
    for tile in state.deck:
        c[tile.description] += 1
    if state.next_tile is not None:
        c[state.next_tile.description] += 1
    return c


def bag_features(bag: Counter, tct: dict, classes: list) -> dict:
    """Exact remaining counts by farm-relevant tile class (PREREG 3.2/3.3)."""
    f = {"bag_n": 0}
    for k in range(5):
        f[f"bag_ce{k}"] = 0
        f[f"bag_fr{k}"] = 0
    f["bag_chapel"] = 0
    for c in classes:
        f[f"bag_cls_{c}"] = 0
    for k in range(1, 5):
        f[f"bag_ge{k}"] = 0
    for desc, n in bag.items():
        if n <= 0:
            continue
        a = tct[desc]
        f["bag_n"] += n
        f[f"bag_ce{a['ce']}"] += n
        f[f"bag_fr{a['fr']}"] += n
        f["bag_chapel"] += n * a["ch"]
        f[f"bag_cls_{class_key(a)}"] += n
        for k in range(1, 5):
            if a["ce"] >= k:
                f[f"bag_ge{k}"] += n
    return f


def bag_ge_tuple(f: dict) -> tuple:
    """(n, ge1, ge2, ge3, ge4) in `flat_leaf._bag_stats` shape, but computed from
    the BOARD-DERIVED bag (PREREG 3.1) rather than from `state.deck`."""
    return (f["bag_n"], f["bag_ge1"], f["bag_ge2"], f["bag_ge3"], f["bag_ge4"])


# --------------------------------------------------------------------------- #
# field geometry + the bag x field interaction                                 #
# --------------------------------------------------------------------------- #
def field_features(state, decomp, flat_leaf, froot, player, bagf) -> dict:
    board = state.board
    H = len(board)
    W = len(board[0]) if H else 0

    coords = set()
    for (r, c, _side), root in decomp.farm_anypos_root.items():
        if root == froot:
            coords.add((r, c))

    entry = set()
    for (r, c) in coords:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < H and 0 <= cc < W and board[rr][cc] is None:
                entry.add((rr, cc))

    adj = decomp.farm_root_adj_city_roots.get(froot, frozenset())
    fin = [cr for cr in adj if decomp.city_root_finished[cr]]
    unfin = [cr for cr in adj if not decomp.city_root_finished[cr]]
    open_edges = sum(int(decomp.city_root_open_n.get(cr, 0)) for cr in unfin)

    # the incumbent bag_close primitive, pointed at the FARM's cities
    bag = bag_ge_tuple(bagf)
    closable = 0
    for cr in unfin:
        faces = flat_leaf._city_faces_ge(decomp, board, H, W, cr)
        if flat_leaf._bag_city_ok(int(decomp.city_root_open_n.get(cr, 0)), faces, bag):
            closable += 1

    # farmer weight on this field, post-placement
    w = [0, 0]
    for p in range(state.players):
        for mp in state.placed_meeples[p]:
            cws = mp.coordinate_with_side
            rt = decomp.farm_pos0_root.get(
                (cws.coordinate.row, cws.coordinate.column, cws.side))
            if rt is None:
                rt = decomp.farm_anypos_root.get(
                    (cws.coordinate.row, cws.coordinate.column, cws.side))
            if rt == froot:
                w[p] += flat_leaf._meeple_weight(mp.meeple_type)

    opp = 1 - player
    n_entry = len(entry)
    bag_n = max(int(bagf["bag_n"]), 1)
    fr_ge1 = bagf["bag_n"] - bagf["bag_fr0"]
    opp_left = int(state.meeples[opp])
    pressure = n_entry * opp_left / bag_n

    return {
        "field_tiles": len(coords),
        "field_adj_cities": len(adj),
        "field_finished_cities": len(fin),
        "field_unfinished_cities": len(unfin),
        "field_unfin_open_edges": open_edges,
        "field_entry_cells": n_entry,
        "own_w": w[player],
        "opp_w": w[opp],
        "own_meeples_left": int(state.meeples[player]),
        "opp_meeples_left": opp_left,
        "bag_closable_unfin": closable,
        "bag_closable_pts": 3 * closable,
        "proj_finished_cities": len(fin) + closable,
        "entry_supply": n_entry * fr_ge1 / bag_n,
        "invade_risk": min(1.0, pressure),
        "invade_pressure": pressure,
    }


# --------------------------------------------------------------------------- #
# baselines -- the leaf's own valuation of THIS farmer                         #
# --------------------------------------------------------------------------- #
def leaf_marginal(state, player, flat_leaf, cfg, meeple_obj, bag_close: bool):
    """leaf(s) - leaf(s with this farmer not deployed), from `player`'s POV.

    The counterfactual removes exactly that meeple and returns it to the seat's
    reserve (the leaf's free-meeple curve reads `state.meeples`), then restores
    the state exactly. try/finally so an exception cannot leave the replay state
    mutated -- a corrupted state would silently poison every later row."""
    lst = state.placed_meeples[player]
    idx = lst.index(meeple_obj)
    with_ = flat_leaf.flat_virtual_score_v2_float(state, player, cfg, bag_close)
    lst.pop(idx)
    state.meeples[player] += 1
    try:
        without = flat_leaf.flat_virtual_score_v2_float(state, player, cfg, bag_close)
    finally:
        state.meeples[player] -= 1
        lst.insert(idx, meeple_obj)
    return float(with_) - float(without)


# --------------------------------------------------------------------------- #
# pass 2 -- feature replay                                                     #
# --------------------------------------------------------------------------- #
def feature_pass(deck_seed, actions, profile_name, want, tct, classes, cfg):
    """`want`: {ply: [(player, r, c, side_name, mtype_name), ...]} from pass 1.
    Returns {(ply, player, r, c, side_name): featuredict}."""
    from carcassonne_ai import flat_leaf, rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.activate(profile_name)
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    FULL = full_multiset(board.state)
    FULL_TOTAL = sum(FULL.values())

    out = {}
    n_plies = len(actions)
    for ply, a in enumerate(actions):
        board, _ = game.get_next_state(board, int(a))
        if ply not in want:
            continue
        st = board.state
        bc = board_counts(st)
        bag = FULL - bc
        bagf = bag_features(bag, tct, classes)
        # Self-validating gate, two independent checks:
        #  (1) the bag must account for every unplaced tile. `Counter.__sub__`
        #      DROPS non-positive entries, so a board tile outside FULL would
        #      silently shrink the bag -- this catches exactly that.
        #  (2) it must agree with the engine's own deck to within the one tile
        #      already drawn into `next_tile`. MEASURED: the wrapper draws the
        #      next tile at the END of the meeple action, so at the post-claim
        #      state `bag_n == len(deck) + 1` -- and treating that tile as
        #      UNKNOWN is the correct knowledge state, because the actor chose
        #      the meeple before it was drawn.
        n_board = sum(bc.values())
        delta_deck = bagf["bag_n"] - len(st.deck)
        bag_ok = (bagf["bag_n"] == FULL_TOTAL - n_board) and delta_deck in (0, 1)
        decomp = flat_leaf.decompose(st)
        for (player, r, c, sname, mtype) in want[ply]:
            from wingedsheep.carcassonne.objects.side import Side
            side = getattr(Side, sname)
            froot = decomp.farm_pos0_root.get((r, c, side))
            via = "pos0"
            if froot is None:
                froot = decomp.farm_anypos_root.get((r, c, side))
                via = "anypos"
            if froot is None:
                out[(ply, player, r, c, sname)] = {"_error": "no_farm_root"}
                continue
            f = dict(bagf)
            f.update(field_features(st, decomp, flat_leaf, froot, player, bagf))
            f["ply_frac"] = ply / n_plies
            mp = None
            for m in st.placed_meeples[player]:
                cws = m.coordinate_with_side
                if (cws.coordinate.row == r and cws.coordinate.column == c
                        and SA._sname(cws.side) == sname):
                    mp = m
                    break
            if mp is None:
                f["_b_leaf"] = None
                f["_b_bag"] = None
            else:
                f["_b_leaf"] = leaf_marginal(st, player, flat_leaf, cfg, mp, False)
                f["_b_bag"] = leaf_marginal(st, player, flat_leaf, cfg, mp, True)
            f["_bag_ok"] = bool(bag_ok)
            f["_bag_minus_deck"] = int(delta_deck)
            f["_root_via"] = via
            out[(ply, player, r, c, sname)] = f
    return out


# --------------------------------------------------------------------------- #
# per-game driver                                                              #
# --------------------------------------------------------------------------- #
def leaf_cfg():
    """The champion leaf config of record + its provenance hashes.

    Uses `champion_factory.production_leaf_cfg()` + `verify_leaf()` (the R1/R7
    provenance guard) rather than hand-building a LeafConfig, so a mis-exported
    env fails loudly here instead of silently grading B-LEAF under a leaf that
    is not the champion's."""
    from carcassonne_ai import champion_factory as CF

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    try:
        hashes = dict(CF.resolved_manifest("clairvoyant", verify=True)
                      .get("leaf_hashes") or {})
    except Exception as e:  # noqa: BLE001 -- provenance is recorded, not required
        hashes = {"_error": str(e)}
    return cfg, hashes


def census_one(corpus, gid, path_or_rec, profile_name, tct, classes, cfg,
               meta_extra=None):
    """Pass 1 (banked kernel) -> fate; pass 2 -> claim-ply features."""
    if corpus == "E4":
        g = SA.census_game(str(path_or_rec), profile_name)
        deck_seed = g["arch"]["deck_seed"]
        actions = g["arch"]["actions"]
        human_player = g["arch"]["human_player"]
        recorded = g["recorded_scores"]
    else:
        g = census_selfplay_game(path_or_rec, profile_name)
        deck_seed = path_or_rec["deck_seed"]
        actions = path_or_rec["actions"]
        human_player = None
        recorded = g["recorded_scores"]

    rows = []
    if not g["recon_ok"]:
        return rows, {"game": gid, "corpus": corpus, "profile": profile_name,
                      "recon_ok": False, "notes": g["recon_notes"][:5],
                      "n_farm_commits": 0}

    n_plies = g["n_plies"]
    want = {}
    farm_uids = []
    for uid in sorted(g["meeples"]):
        m = g["meeples"][uid]
        if m["cloister"] or m["feature_key"] is None:
            continue
        if m["feature_key"][0] != "F":
            continue
        farm_uids.append(uid)
        r, c, sname = m["pos"]
        want.setdefault(m["placed_ply"], []).append(
            (m["player"], r, c, sname, m["type"]))

    feats = feature_pass(deck_seed, actions, profile_name, want, tct, classes, cfg)

    for uid in farm_uids:
        m = g["meeples"][uid]
        r, c, sname = m["pos"]
        f = feats.get((m["placed_ply"], m["player"], r, c, sname))
        if f is None or "_error" in f:
            rows.append({"row": "farm_deploy", "corpus": corpus, "game": gid,
                         "uid": uid, "ok": False,
                         "err": (f or {}).get("_error", "no_feature")})
            continue
        seat_role = ("owner" if (human_player is not None
                                 and m["player"] == human_player)
                     else ("champion" if human_player is not None else "champion"))
        rec = {
            "row": "farm_deploy", "corpus": corpus, "game": gid, "uid": uid,
            "ok": True, "profile": profile_name,
            "player": m["player"], "seat_role": seat_role,
            "human_player": human_player,
            "claim_ply": m["placed_ply"], "n_plies": n_plies,
            "realized_pts": m["realized_pts"],
            "y": int(m["realized_pts"] > 0),
            "size_at_claim": m.get("size_at_claim"),
            "size_at_score": m.get("size_at_score"),
            "b_leaf": f.get("_b_leaf"), "b_bag": f.get("_b_bag"),
            "bag_ok": f.get("_bag_ok"), "root_via": f.get("_root_via"),
            "bag_minus_deck": f.get("_bag_minus_deck"),
        }
        if meta_extra:
            rec.update(meta_extra)
        rec["x"] = {k: f[k] for k in feature_names(tct)}
        rows.append(rec)

    return rows, {"game": gid, "corpus": corpus, "profile": profile_name,
                  "recon_ok": True, "n_plies": n_plies,
                  "final_scores": g["final_scores"], "recorded_scores": recorded,
                  "human_player": human_player,
                  "n_farm_commits": len(farm_uids)}


# --------------------------------------------------------------------------- #
# self-play corpus: same kernel, different loader                              #
# --------------------------------------------------------------------------- #
def census_selfplay_game(rec, profile_name):
    """`SA.census_game` reads its archive off disk; the self-play corpus is one
    JSONL record. Rather than fork the kernel, hand it a shim archive through
    the same `ev_loss.load_archive` shape by monkey-patching ONLY the two IO
    functions the kernel calls, then restore them. The replay/attribution code
    itself is untouched."""
    arch = {"path": f"selfplay::{rec['game_id']}",
            "deck_seed": int(rec["deck_seed"]),
            "actions": [int(a) for a in rec["actions"]],
            "human_player": 0,
            "recorded_scores": [int(rec["score_p0"]), int(rec["score_p1"])],
            "provenance": {}}
    orig_load = ev_loss.load_archive
    ev_loss.load_archive = lambda p: arch
    try:
        return SA.census_game(arch["path"], profile_name)
    finally:
        ev_loss.load_archive = orig_load


# --------------------------------------------------------------------------- #
# fork-pool worker (module level so it is picklable; state via _G, inherited)  #
# --------------------------------------------------------------------------- #
_G: dict = {}


def _work(job):
    gid, src, extra = job
    try:
        return census_one(_G["corpus"], gid, src, _G["profile"], _G["tct"],
                          _G["classes"], _G["cfg"], extra)
    except Exception as e:  # noqa: BLE001 -- one bad game must not kill the run
        import traceback
        return [], {"game": gid, "corpus": _G["corpus"], "profile": _G["profile"],
                    "recon_ok": False,
                    "notes": [f"EXC {e}", traceback.format_exc()[-800:]],
                    "n_farm_commits": 0}


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, choices=("E4", "SP449"))
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--games-dir", default=REPO + "/measurement/e4_games")
    ap.add_argument("--jsonl", default=REPO + "/measurement/champ_action_logs/champ_games.jsonl")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()

    r9 = ev_loss.prepare_env(args.profile)
    tct = tile_class_table()
    classes = sorted({class_key(a) for a in tct.values()})
    cfg, leaf_hashes = leaf_cfg()
    _G.update(corpus=args.corpus, profile=args.profile, tct=tct,
              classes=classes, cfg=cfg)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "TILE_CLASSES.json").write_text(json.dumps(
        {"by_description": tct, "classes": classes,
         "class_totals": {c: sum(v["count"] for v in tct.values()
                                 if class_key(v) == c) for c in classes},
         "n_kinds": len(tct), "n_tiles": sum(v["count"] for v in tct.values())},
        indent=1))
    (out / "FEATURES.json").write_text(json.dumps(
        {"order": feature_names(tct)}, indent=1))

    jobs = []
    if args.corpus == "E4":
        for p in sorted(Path(args.games_dir).glob("*.json")):
            a = json.loads(p.read_text())
            if not a.get("ok", True):
                continue
            if ev_loss.resolve_profile_name(a) != args.profile:
                continue
            jobs.append((p.name, str(p), {
                "rules_profile_resolved": args.profile,
                "finished_at": a.get("finished_at"),
                "tiearb_enabled": bool(a.get("tiearb_enabled")),
                "budget_note": a.get("budget_note")}))
    else:
        for line in Path(args.jsonl).read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            jobs.append((str(r["game_id"]), r, {
                "rules_profile_resolved": args.profile,
                "leaf": r.get("leaf"), "gen": r.get("gen")}))
    if args.limit:
        jobs = jobs[: args.limit]

    print(f"[hpm1] corpus={args.corpus} profile={args.profile} games={len(jobs)}",
          flush=True)

    t0 = time.time()
    results = []
    if args.workers > 1:
        import multiprocessing as mp
        # FORK, deliberately: the R9 latch and the resolved leaf cfg live in
        # already-imported module state, and only fork inherits them. A spawn
        # worker would re-import carcassonne_ai with an unlatched R9 and grade
        # the wrong farms (ev_loss.prepare_env's own failure mode).
        with mp.get_context("fork").Pool(args.workers) as pool:
            for i, res in enumerate(pool.imap_unordered(_work, jobs)):
                results.append(res)
                if (i + 1) % 25 == 0:
                    print(f"  [{i+1}/{len(jobs)}] {time.time()-t0:.1f}s", flush=True)
    else:
        for i, job in enumerate(jobs):
            results.append(_work(job))
            if (i + 1) % 25 == 0:
                print(f"  [{i+1}/{len(jobs)}] {time.time()-t0:.1f}s", flush=True)

    name = f"rows_{args.corpus}_{args.profile}"
    with (out / f"{name}.jsonl").open("w") as fh:
        for rows, _ in results:
            for r in rows:
                fh.write(json.dumps(r, default=str) + "\n")
    gsum = [g for _, g in results]
    (out / f"{name}_games.json").write_text(json.dumps(gsum, indent=1, default=str))

    n_ok = sum(1 for g in gsum if g["recon_ok"])
    n_rows = sum(len(r) for r, _ in results)
    (out / f"{name}_manifest.json").write_text(json.dumps({
        "instrument": "hpm1_fieldfate_census",
        "prereg": "measurement/hpm1_fieldfate_gate_20260830/PREREG.md",
        "corpus": args.corpus, "profile": args.profile,
        "r9": r9, "leaf_hashes": leaf_hashes,
        "prod_env": env_preamble.RESOLVED,
        "n_games_offered": len(jobs), "n_games_reconciled": n_ok,
        "n_rows": n_rows, "wall_s": time.time() - t0,
        "source": (args.games_dir if args.corpus == "E4" else args.jsonl),
        "feature_order": feature_names(tct),
    }, indent=1, default=str))
    print(f"[hpm1] done corpus={args.corpus} profile={args.profile} "
          f"reconciled={n_ok}/{len(gsum)} rows={n_rows} "
          f"{time.time()-t0:.1f}s -> {out/name}.jsonl", flush=True)


if __name__ == "__main__":
    main()
