#!/usr/bin/env python3
"""OM-D2 localisation probe — rust `tiearb::chain_values` vs its python
definition of record, on the 10 banked `G-FIRE` join witnesses.

⛔ READ-ONLY / INSTRUMENT ONLY. Touches no production code and writes nothing
outside `measurement/omd2_chain_values_20260830/`.

For each witness `(deck_seed, ply)` it replays the banked champion game three
ways and diffs the per-action OUTER CHAIN values:

* ``rust``      — `carc_rs.MirrorState.tiearb_probe`, i.e. the SHIPPED
  `carc_core::tiearb::chain_values` the deployed arbiter triggers on.
* ``py_cache``  — `scripts/tiletie/chain_census.chain_values` walked exactly as
  `meeple_tie_census._process_game` walked it, i.e. with
  ``Game(enable_legal_moves_cache=True)`` — the setting the banked census ran
  under, and therefore the definition of record AS MEASURED.
* ``py_nocache`` — the same python code with the legal-mask memo OFF (the
  HONEST mask).

The three-way split is the discriminator: if `py_nocache == rust != py_cache`,
the divergence is the known non-injective `string_representation` legal-cache
collision (`game_wrapper._FIX_LEGAL_CACHE_KEY` docstring, tiearb2 Stage-2
by-catch 2026-08-17) contaminating the CENSUS, not a port bug.
"""
from __future__ import annotations

import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

WITNESSES = [
    (28000000011, 24),
    (28000000012, 112),
    (28000000015, 72),
    (28000000017, 30),
    (28000000022, 66),
    (28000000031, 110),
    (28000000031, 114),
    (28000000050, 24),
    (28000000052, 48),
    (28000000059, 138),
]

SALT_OF_RECORD = "tiearb2-deploy-v1"
ARM_CAP_J = 4
EPS = 0.0
PROFILE = "walled"
CORPUS = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
CENSUS = REPO / "measurement" / "tiearb_widening_20260817" / "census" / "tile_gap_rows.jsonl"


def prepare_env(profile: str = PROFILE) -> dict:
    for p in (REPO / "scripts", REPO / "scripts" / "jcz_match",
              REPO / "scripts" / "human_anchor", REPO / "scripts" / "tiletie"):
        if str(p) not in sys.path and p.exists():
            sys.path.insert(0, str(p))
    import match as JM

    env = JM.export_profile_env(profile)
    import env_preamble  # noqa: F401

    return {**env, "leaf_env": dict(env_preamble.RESOLVED)}


def bits(x: float) -> str:
    return struct.pack(">d", x).hex()


def load_corpus() -> dict:
    out = {}
    with CORPUS.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            out[int(r["deck_seed"])] = [int(a) for a in r["actions"]]
    return out


def census_rows() -> dict:
    want = set(WITNESSES)
    out = {}
    with CENSUS.open() as fh:
        for line in fh:
            d = json.loads(line)
            k = (d["deck_seed"], d["ply"])
            if k in want:
                out[k] = d
    return out


# --------------------------------------------------------------------------- #
# python side                                                                   #
# --------------------------------------------------------------------------- #
def python_chain(actions, deck_seed: int, target_ply: int, *, cache: bool, leaf):
    """`chain_values` at `target_ply`, replayed the way the census replayed it.

    With `cache=True` the walk reproduces `meeple_tie_census._process_game`
    exactly — including calling `chain_values` at every earlier TILE ply, since
    those calls are what POPULATE the memo whose key is not injective.
    """
    import random

    import numpy as np
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    import chain_census as CC
    from carcassonne_ai.game_wrapper import Game

    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=cache, include_farm_scalars=True)
    board = game.get_init_board()
    hit = None
    for ply, played in enumerate(actions):
        st = board.state
        seat = int(st.current_player)
        if ply == target_ply:
            vals = CC.chain_values(game, board, seat, lambda s: leaf(s, seat))
            rep = CC.tie_report(vals)
            hit = {"seat": seat, "values": vals, "report": rep,
                   "cache_stats": dict(game.legal_cache_stats())
                   if hasattr(game, "legal_cache_stats") else {}}
            break
        # faithful census work at earlier plies (cache-warming is the point)
        if cache:
            if st.phase == GamePhase.MEEPLES:
                pass
            else:
                n_legal = int(np.count_nonzero(game.get_valid_moves(board)))
                if n_legal >= 2:
                    CC.chain_values(game, board, seat, lambda s: leaf(s, seat))
        board, _ = game.get_next_state(board, int(played))
    return hit


# --------------------------------------------------------------------------- #
# rust side                                                                     #
# --------------------------------------------------------------------------- #
def rust_chain(actions, deck_seed: int, target_ply: int, leaf_rs):
    import carc_rs

    g = carc_rs.MirrorState.from_seed(str(deck_seed))
    for t, a in enumerate(actions):
        if t == target_ply:
            return g.tiearb_probe(leaf_rs, champ_pick=int(a), j=ARM_CAP_J,
                                  eps=EPS, salt=SALT_OF_RECORD, ply=t)
        g.advance(int(a))
    return None


def main() -> int:
    prepare_env()
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import flat_leaf
    from carcassonne_ai.rust_agent import leaf_config_rs

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    hashes = dict(CF.resolved_manifest("clairvoyant", verify=True).get("leaf_hashes") or {})
    assert hashes.get("harness_leaf_hash") == "a36d2e15a3b3d71d", hashes
    bag_close = bool(getattr(cfg, "bag_close", False))
    leaf_rs = leaf_config_rs(cfg)

    def leaf(state, seat):
        return float(flat_leaf.flat_virtual_score_v2_float(state, int(seat), cfg, bag_close))

    corpus = load_corpus()
    rows = census_rows()
    out = []
    for seed, ply in WITNESSES:
        t0 = time.time()
        actions = corpus[seed]
        r = rust_chain(actions, seed, ply, leaf_rs)
        rv = {int(a): struct.unpack(">d", b.to_bytes(8, "big"))[0]
              for a, b, _m in r["chain_values"]}
        rm = {int(a): m for a, _b, m in r["chain_values"]}
        p_on = python_chain(actions, seed, ply, cache=True, leaf=leaf)
        p_off = python_chain(actions, seed, ply, cache=False, leaf=leaf)
        pv_on = {int(a): v for a, v, _c in p_on["values"]}
        pm_on = {int(a): (c[1] if len(c) > 1 else None) for a, _v, c in p_on["values"]}
        pv_off = {int(a): v for a, v, _c in p_off["values"]}
        pm_off = {int(a): (c[1] if len(c) > 1 else None) for a, _v, c in p_off["values"]}

        acts = sorted(set(rv) | set(pv_on) | set(pv_off))
        diffs = []
        for a in acts:
            vr, vo, vf = rv.get(a), pv_on.get(a), pv_off.get(a)
            if not (vr == vo == vf):
                diffs.append({
                    "action": a,
                    "rust": vr, "py_cache": vo, "py_nocache": vf,
                    "rust_bits": bits(vr) if vr is not None else None,
                    "py_cache_bits": bits(vo) if vo is not None else None,
                    "py_nocache_bits": bits(vf) if vf is not None else None,
                    "meeple_rust": rm.get(a),
                    "meeple_py_cache": pm_on.get(a),
                    "meeple_py_nocache": pm_off.get(a),
                })
        rec = {
            "deck_seed": seed, "ply": ply,
            "seat_rust": int(r["seat"]), "seat_py": p_on["seat"],
            "n_legal_rust": int(r["n_legal"]),
            "n_cand_rust": len(rv), "n_cand_py_cache": len(pv_on),
            "n_cand_py_nocache": len(pv_off),
            "action_set_equal_rust_vs_py_cache": set(rv) == set(pv_on),
            "action_set_equal_rust_vs_py_nocache": set(rv) == set(pv_off),
            "rust_fired": bool(r.get("fired")),
            "rust_tie_actions": list(r.get("tie_actions", [])),
            "rust_arms": list(r.get("arms", [])),
            "py_cache_top1": p_on["report"]["top1"],
            "py_cache_top2": p_on["report"]["top2"],
            "py_cache_gap": p_on["report"]["gap"],
            "py_cache_tie_exact": p_on["report"]["tie_exact"],
            "py_cache_tie_actions": p_on["report"]["tie_actions_exact"],
            "py_nocache_top1": p_off["report"]["top1"],
            "py_nocache_top2": p_off["report"]["top2"],
            "py_nocache_gap": p_off["report"]["gap"],
            "py_nocache_tie_exact": p_off["report"]["tie_exact"],
            "py_nocache_tie_actions": p_off["report"]["tie_actions_exact"],
            "banked_census_gap": rows.get((seed, ply), {}).get("gap"),
            "banked_census_tie_exact": rows.get((seed, ply), {}).get("tie_exact"),
            "banked_census_n_legal": rows.get((seed, ply), {}).get("n_legal"),
            "n_value_diffs": len(diffs),
            "value_diffs": diffs,
            "py_cache_reproduces_bank": (
                rows.get((seed, ply), {}).get("gap") == p_on["report"]["gap"]
            ),
            "rust_equals_py_nocache": rv == pv_off,
            "rust_equals_py_cache": rv == pv_on,
            "secs": round(time.time() - t0, 2),
        }
        out.append(rec)
        print(json.dumps({k: rec[k] for k in (
            "deck_seed", "ply", "rust_fired", "banked_census_gap",
            "py_cache_gap", "py_nocache_gap", "py_nocache_tie_exact",
            "rust_equals_py_cache", "rust_equals_py_nocache",
            "py_cache_reproduces_bank", "n_value_diffs",
            "action_set_equal_rust_vs_py_cache",
            "action_set_equal_rust_vs_py_nocache", "secs")}), flush=True)

    (HERE / "WITNESS_DIFFS.json").write_text(json.dumps({
        "schema": "carcassonne-omd2-localisation/v1",
        "leaf_hashes": hashes,
        "profile": PROFILE,
        "salt": SALT_OF_RECORD,
        "eps": EPS,
        "arm_cap_j": ARM_CAP_J,
        "carc_rs": __import__("carc_rs").__file__,
        "witnesses": out,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
