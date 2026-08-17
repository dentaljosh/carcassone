#!/usr/bin/env python
"""TIE ARBITER — the TWO-SIDED liveness assert (`J13`).

`measurement/tiearb2_stage2_20260817/DESIGN.md` §4, READ_RULE `G-J13`.

⚠️ WHY THIS EXISTS AND WHY NO HASH CHECK REPLACES IT. The arbiter's knobs live on
`SearchConfig`, NOT `LeafConfig`, so a LIVE arbiter moves **no leaf hash**: the
candidate's `cand_leaf_hash` EQUALS the champion's `a36d2e15a3b3d71d` (`J1` is an
EQUALITY gate here — a *difference* is an abort, not a finding). Every moved-hash
wiring gate from the surface-A / opencity / denial campaigns is therefore INERT.
A stale `carc_rs`, a dropped kwarg, or a trigger that never fires would grade a
perfect champion-vs-champion null wearing the exact shape of a real cell.

The J13 lesson, carried verbatim from the surface-B driver:

    "Without this a zeroed dose grades a perfect champion-vs-champion null
     wearing the shape of a real cell."

Two sides, and BOTH are asserted:

  * **POSITIVE** — on a constructed tied ply the arbiter **changes the pick**
    relative to the unmodified champion (same agent seed, same move index, same
    board: the ONLY difference is the knob).
  * **NEGATIVE** — `root_leaf_value_bits` is **unchanged**: the arbiter must not
    perturb the champion's own evaluation anywhere. Pinned on the raw f64 bits,
    together with the whole pooled-stats vector, so a one-ULP drift cannot hide.

Importable (`_assert_surface_tiearb_live`) and runnable (`python tiearb_live.py`
prints the witness as JSON). ADJUDICATES NOTHING, plays no cell, reads no
strength number.
"""
from __future__ import annotations

import json
import sys

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"
SALT_OF_RECORD = "tiearb2-deploy-v1"

# The pinned control line. Deep enough that the tier1 continuations are short
# (the arbiter is the expensive half of this assert) and wide enough that the
# exact-tie trigger fires often.
CONTROL_DECK_SEED = "28000000000"
CONTROL_START_PLY = 30


def _leaf_and_cfgs(sims: int, k_dets: int, b: int, j: int, salt: str):
    import carc_rs

    from carcassonne_ai.rust_agent import leaf_config_rs
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG

    lc = leaf_config_rs(DEFAULT_CONFIG)
    off = carc_rs.SearchConfigRs(lc, sims, 1.5, 5.0, 15.0)
    on = carc_rs.SearchConfigRs(lc, sims, 1.5, 5.0, 15.0,
                                tiearb_enabled=True, tiearb_b=b, tiearb_j=j,
                                tiearb_mode="argmax", tiearb_salt=salt,
                                tiearb_eps=0.0)
    return carc_rs, lc, off, on


def _assert_negative_side(carc_rs, lc, off, on, plies: int = 30) -> dict:
    """The arbiter must not move the champion's own evaluation ANYWHERE.

    The single-world `Searcher` never reads the tiearb knobs at all (the arbiter
    is an agent-level, once-per-move intervention at the `pooled_q_argmax` root
    hook), so this is the assert that PROVES it rather than assuming it.
    """
    ms_a = carc_rs.MirrorState.from_seed(CONTROL_DECK_SEED)
    ms_b = carc_rs.MirrorState.from_seed(CONTROL_DECK_SEED)
    for _ in range(plies):
        la = ms_a.legal_actions()
        a = int(la[len(la) // 2])
        ms_a.advance(a)
        ms_b.advance(a)
    ra = ms_a.search_single(off)
    rb = ms_b.search_single(on)
    if ra["root_leaf_value_bits"] != rb["root_leaf_value_bits"]:
        raise AssertionError(
            "NEGATIVE SIDE FAILED: the tie arbiter moved root_leaf_value_bits "
            f"({ra['root_leaf_value_bits']} -> {rb['root_leaf_value_bits']}). The "
            "arbiter must not perturb the champion's own evaluation anywhere.")
    if ra["pooled_stats"] != rb["pooled_stats"] or ra["chosen_action"] != rb["chosen_action"]:
        raise AssertionError(
            "NEGATIVE SIDE FAILED: the tie arbiter moved the single-world search "
            "(pooled_stats or chosen_action). It binds at the fair agent's root "
            "hook and must leave the search itself byte-identical.")
    return {
        "root_leaf_value_bits": int(ra["root_leaf_value_bits"]),
        "chosen_action": int(ra["chosen_action"]),
        "n_pooled": len(ra["pooled_stats"]),
        "plies": plies,
    }


def _assert_positive_side(carc_rs, lc, off, on, *, k_dets: int, seed: int,
                          max_fired: int, start_ply: int) -> dict:
    """On a constructed tied ply the arbiter must CHANGE the pick.

    Both agents are seeded identically, walk the identical pinned line, and are
    asked at the identical `move_idx` — so the returned action can differ ONLY
    because the knob is live.
    """
    def mk(cfg):
        a = carc_rs.FairAgentRs(cfg, k_dets, seed, threads=1, exact_endgame=False)
        a.start_game_from_seed(CONTROL_DECK_SEED)
        return a

    a_off, a_on = mk(off), mk(on)
    for _ in range(start_ply):
        la = a_off.legal_actions()
        act = int(la[len(la) // 2])
        a_off.advance(act)
        a_on.advance(act)

    probe_ms = carc_rs.MirrorState.from_seed(CONTROL_DECK_SEED)
    for _ in range(start_ply):
        la = probe_ms.legal_actions()
        probe_ms.advance(int(la[len(la) // 2]))

    fired = 0
    examined = []
    move_idx = 0
    for ply in range(start_ply, start_ply + 200):
        if a_off.is_terminal():
            break
        probe = probe_ms.tiearb_probe(lc, -1, 4, 0.0, SALT_OF_RECORD, move_idx)
        if probe.get("fired"):
            x = int(a_off.choose_action(move_idx))
            y = int(a_on.choose_action(move_idx))
            st = a_on.stats()["last_move"]
            fired += 1
            examined.append({
                "ply": ply, "move_idx": move_idx,
                "champ_pick": x, "arbiter_pick": y,
                "arms": [int(v) for v in st["tiearb_arms"]],
                "tiearb_fired": bool(st["tiearb_fired"]),
                "playouts": int(st["tiearb_playouts"]),
                "secs": round(float(st["tiearb_secs"]), 3),
            })
            if not st["tiearb_fired"]:
                raise AssertionError(
                    f"POSITIVE SIDE FAILED at ply {ply}: the probe says the trigger "
                    "fires here but the ARMED AGENT reports tiearb_fired=False — the "
                    "knob did not reach the agent (stale carc_rs wheel?).")
            if y != x:
                return {
                    "changed_at_ply": ply, "move_idx": move_idx,
                    "champ_pick": x, "arbiter_pick": y,
                    "arms": [int(v) for v in st["tiearb_arms"]],
                    "fired_plies_examined": fired,
                    "examined": examined,
                    "agent_fired_plies": int(a_on.stats()["tiearb_fired_plies"]),
                    "agent_pickchanges": int(a_on.stats()["tiearb_pickchanges"]),
                }
            if fired >= max_fired:
                break
        la = a_off.legal_actions()
        act = int(la[len(la) // 2])
        a_off.advance(act)
        a_on.advance(act)
        probe_ms.advance(act)
        move_idx += 1
    raise AssertionError(
        f"POSITIVE SIDE FAILED: the arbiter agreed with the champion on all "
        f"{fired} fired plies examined on the pinned control line. It is NOT proven "
        "live. Do not play a game on this box: without this control a dead arbiter "
        "grades a perfect champion-vs-champion null wearing the shape of a real "
        f"cell. (examined: {examined})")


def _assert_surface_tiearb_live(*, b: int = 16, j: int = 4, sims: int = 64,
                                k_dets: int = 4, seed: int = 101,
                                max_fired: int = 12,
                                start_ply: int = CONTROL_START_PLY,
                                salt: str = SALT_OF_RECORD) -> dict:
    """Run BOTH sides. Raises `AssertionError` on either failure; returns the
    witness dict on success."""
    carc_rs, lc, off, on = _leaf_and_cfgs(sims, k_dets, b, j, salt)
    if not bool(on.tiearb["enabled"]):
        raise AssertionError("the ON config resolved to tiearb_enabled=False")
    if bool(off.tiearb["enabled"]):
        raise AssertionError("the OFF config resolved to tiearb_enabled=True")
    neg = _assert_negative_side(carc_rs, lc, off, on)
    pos = _assert_positive_side(carc_rs, lc, off, on, k_dets=k_dets, seed=seed,
                                max_fired=max_fired, start_ply=start_ply)
    return {
        "salt": salt, "B": b, "J": j, "eps": 0.0,
        "control_deck_seed": CONTROL_DECK_SEED,
        "sims": sims, "k_dets": k_dets, "agent_seed": seed,
        "positive_side": pos,
        "negative_side": neg,
        "resolved_on": dict(on.tiearb),
        "resolved_off": dict(off.tiearb),
    }


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--b", type=int, default=16)
    ap.add_argument("--j", type=int, default=4)
    ap.add_argument("--sims", type=int, default=64)
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--max-fired", type=int, default=12)
    a = ap.parse_args(argv)
    try:
        w = _assert_surface_tiearb_live(b=a.b, j=a.j, sims=a.sims, k_dets=a.k_dets,
                                        max_fired=a.max_fired)
    except AssertionError as e:
        json.dump({"ok": False, "error": str(e)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1
    json.dump({"ok": True, **w}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
