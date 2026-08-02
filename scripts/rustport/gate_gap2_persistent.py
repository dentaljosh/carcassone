#!/usr/bin/env python3
"""GATE (b) — the GAP-2 THREE-WAY, reproduced with the persistent tree added.

WHY THIS EXISTS.  `measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json`
established that the oracle pilot's continuation is a PERSISTING-TREE search, and
a sibling's attribution leg then named the mechanism exactly: run ONE world's
continuation three ways and

    python-as-shipped              (`best_action`, the tree ACCUMULATES)
    python-with-a-clear-per-ply    (`ag.clear()` before every `best_action`)
    rust `search_single`           (fresh tree per search — all carc_rs had)

the CLEARED python leg matches rust bit-for-bit while the SHIPPED one does not.
That is the whole reason `oracle_score_pilot` and the clairvoyant builder failed
closed: the Rust ruler was a different player, and converting it would have
silently changed the instrument that priced +0.7375 pts/disagreement.

WHAT THIS GATE ADDS.  A FOURTH leg — rust WITH the persistent tree
(`rust_agent.RustCarryClairvoyantAgent`, `carc_rs.PersistentSearcher`) — and it
requires the two families to close in BOTH directions:

    rust-carry  ==  python-as-shipped           <- the feature's whole claim
    rust-fresh  ==  python-cleared-per-ply      <- and the OLD behaviour is intact

Identity is the ACTION STREAM, ply by ply, not just the terminal margin: two
different players can land on the same score by accident, and this gate exists
precisely because a same-margin/different-stream world (row 1 of the GAP2
artifact: margin_delta 0.0, yet 66 divergent plies) would otherwise read as a
pass.  The terminal margin, ply count and per-ply carried-visit counts are
compared too.

ANTI-VACUITY.  A world where the shipped and cleared legs agree does not
discriminate, so the gate FAILS if no cell separates them — a green run has to
have watched the two players actually diverge.

CELLS.  Same source the sibling's attribution used: the live 110k oracle bank's
own scored records joined to their root action sequences, falling back to the
recorded champion games when no share is mounted.

    .venv/bin/python scripts/rustport/gate_gap2_persistent.py --positions 2
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

# MUST precede any carcassonne_ai import (import-frozen DEFAULT_CONFIG).
import oracle_score_pilot as O  # noqa: E402

import root_replay as RR  # noqa: E402
from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai.fair_agent import FairHeuristicMCTSAgent  # noqa: E402
from carcassonne_ai.rust_agent import RustCarryClairvoyantAgent  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GATE_GAP2_PERSISTENT.json"


def _share(rel: str) -> str:
    """⚠️ The share mount path differs by box (local vs inside an ssh)."""
    for root in ("/mnt/c/carc-shared", "/mnt/carc-shared"):
        if Path(root).is_dir():
            return f"{root}/{rel}"
    return f"/mnt/carc-shared/{rel}"


DEFAULT_BANK = _share("oracle_110k_20260801")
DEFAULT_ROOTS_RUN = _share("classical_search/move_agreement_k4_b28e9")


def load_items(bank: Path, roots_run: Path, n: int) -> list:
    """`n` scored bank cells joined to their action sequences (the sibling's
    `_load_items(..., "score")`), else champion-game roots with pick = legal[0]."""
    recs_dir = bank / "score" / "records"
    roots_path = roots_run / "roots.jsonl"
    if recs_dir.is_dir() and roots_path.is_file():
        roots = {}
        for line in roots_path.read_text().splitlines():
            if line.strip():
                o = json.loads(line)
                roots[f"s{int(o['deck_seed'])}_p{int(o['ply'])}"] = o
        items = []
        for p in sorted(recs_dir.glob("s*.json"))[: n * 4]:
            d = json.loads(p.read_text())
            if not d.get("ok") or d.get("pick_a") is None:
                continue
            r = roots.get(d["root_id"])
            if r is None:
                continue
            it = dict(d)
            it["actions"] = [int(a) for a in r["actions"]]
            it["source"] = "bank"
            items.append(it)
            if len(items) >= n:
                break
        if items:
            return items
    out = []
    if not CHAMP_GAMES.is_file():                     # pragma: no cover
        return out
    for g in [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()]:
        acts = [int(a) for a in g["actions"]]
        for ply in (40, 72, 104):
            if ply < len(acts) and len(out) < n:
                out.append({"rid": f"s{g['deck_seed']}_p{ply}_r1",
                            "root_id": f"s{g['deck_seed']}_p{ply}",
                            "deck_seed": int(g["deck_seed"]), "ply": int(ply),
                            "actions": acts, "pick_a": None, "root_player": None,
                            "world_seed_salt": "oracle-pilot-v1", "source": "champ"})
        if len(out) >= n:
            break
    return out


def setup(item: dict):
    """Replay the root, draw world 0 with the pilot's own CRN seed, resolve the pick."""
    game, board = RR.replay_actions(item["deck_seed"], item["actions"], item["ply"])
    salt = item.get("world_seed_salt") or "oracle-pilot-v1"
    ws = O.world_seed(item["rid"], 0, salt)
    ps = O.playout_seed(item["rid"], 0, salt)
    world = FairHeuristicMCTSAgent.reshuffled_determinization(board, random.Random(ws))
    pick = item.get("pick_a")
    if pick is None:
        import numpy as np

        pick = int(np.flatnonzero(game.get_valid_moves(board))[0])
    rp = item.get("root_player")
    if rp is None:
        rp = int(board.state.current_player)
    return game, board, world, int(pick), int(rp), int(ps)


# --------------------------------------------------------------------------- #
# The four legs. ONE loop shape; the tree policy is the ONLY variable.          #
# --------------------------------------------------------------------------- #
def py_leg(game, world, pick, rp, seed, *, sims, max_plies, clear_each_ply: bool):
    b = copy.deepcopy(world)
    b, _ = game.get_next_state(b, int(pick))
    ag = O.build_continuation_agent(game, policy="clair-puct", sims=int(sims),
                                    seed=int(seed))
    actions, carried, plies = [], [], 0
    while not b.state.is_terminated():
        if plies >= max_plies:
            raise RuntimeError(f"playout exceeded max_plies={max_plies}")
        if clear_each_ply:
            ag.clear()
        pre = ag.mcts._nodes.get(game.string_representation(b))
        carried.append(int(pre.N) if pre is not None else 0)
        a = int(ag.best_action(b))
        actions.append(a)
        b, _ = game.get_next_state(b, a)
        plies += 1
    return {"actions": actions, "carried_in": carried, "plies": plies,
            "margin": float(b.state.scores[rp] - b.state.scores[1 - rp])}


def rs_leg(game, board, item, world, pick, rp, seed, *, sims, max_plies, carry: bool):
    b = copy.deepcopy(world)
    b, _ = game.get_next_state(b, int(pick))
    # ⚠️ `reuse_tree=False` EXPLICITLY. The production clairvoyant cfg carries
    # reuse_tree=True, and this leg's `move()` must be the FRESH-tree transition
    # (== `MirrorState.search_single`, == python-with-a-clear-per-ply), not the
    # re-rooting one — which, measured, behaves almost exactly like the carry
    # (a re-root keeps the retained root's visits; it only drops unreachable
    # nodes), so leaving it at the config default would have made the "fresh"
    # leg a second carry leg and the gate vacuous.
    ag = RustCarryClairvoyantAgent(game, CF.production_prior_cfg(), simulations=int(sims),
                                   seed=int(seed), auto_advance=True, reuse_tree=False)
    ag.seat(item["deck_seed"], item["actions"][:item["ply"]], board=board)
    ag.set_world(world)                       # the SAME determinized deck python drew
    ag.advance(int(pick))
    actions, carried, plies = [], [], 0
    while not b.state.is_terminated():
        if plies >= max_plies:
            raise RuntimeError(f"playout exceeded max_plies={max_plies}")
        carried.append(ag.root_n() if carry else 0)
        # carry -> best_action (the tree persists);  else -> move() with
        # reuse_tree=False, i.e. clear-then-search == MirrorState.search_single.
        a = int(ag.best_action(b) if carry else ag.move(b))
        actions.append(a)
        b, _ = game.get_next_state(b, a)      # the agent advances its own mirror
        plies += 1
    return {"actions": actions, "carried_in": carried, "plies": plies,
            "margin": float(b.state.scores[rp] - b.state.scores[1 - rp])}


def diff(a: dict, b: dict) -> dict | None:
    """Identity is the ACTION STREAM first; margin alone can agree by accident."""
    n = min(len(a["actions"]), len(b["actions"]))
    first = next((i for i in range(n) if a["actions"][i] != b["actions"][i]), None)
    if (first is None and a["actions"] == b["actions"]
            and a["plies"] == b["plies"] and a["margin"] == b["margin"]):
        return None
    return {"first_divergent_ply": first,
            "n_divergent_plies": sum(1 for i in range(n)
                                     if a["actions"][i] != b["actions"][i]),
            "plies": [a["plies"], b["plies"]],
            "margin": [a["margin"], b["margin"]]}


def _cell(job: tuple) -> dict:
    """One (position, world 0, pick) cell — all FOUR legs, in ONE process.

    Both engines share the process so the leaf env, the import-frozen
    DEFAULT_CONFIG and the libm flavour are identical by construction; only the
    tree policy and the engine differ.
    """
    item, sims, max_plies = job
    game, board, world, pick, rp, ps = setup(item)
    kw = dict(sims=sims, max_plies=max_plies)
    t0 = time.perf_counter()
    shipped = py_leg(game, world, pick, rp, ps, clear_each_ply=False, **kw)
    cleared = py_leg(game, world, pick, rp, ps, clear_each_ply=True, **kw)
    t_py = time.perf_counter() - t0
    t1 = time.perf_counter()
    carry = rs_leg(game, board, item, world, pick, rp, ps, carry=True, **kw)
    fresh = rs_leg(game, board, item, world, pick, rp, ps, carry=False, **kw)
    return {"item": item, "pick": pick, "root_player": rp,
            "shipped": shipped, "cleared": cleared, "carry": carry, "fresh": fresh,
            "python_secs": t_py, "rust_secs": time.perf_counter() - t1}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_gap2_persistent")
    ap.add_argument("--positions", type=int, default=2)
    ap.add_argument("--workers", type=int, default=1,
                    help="POSITION-parallel fork pool. ⚠️ the two python legs are ~100x "
                         "the two rust legs' wall clock; size W to the box.")
    ap.add_argument("--oracle-sims", type=int, default=100,
                    help="the pilot's own continuation budget")
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--bank", default=DEFAULT_BANK)
    ap.add_argument("--roots-run", default=DEFAULT_ROOTS_RUN)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    O._G["cfg"] = CF.production_prior_cfg()
    items = load_items(Path(args.bank), Path(args.roots_run), int(args.positions))
    if not items:
        print("FAIL: no cells resolved — a gate that ran on an empty set has gated "
              "nothing")
        return 1

    jobs = [(it, int(args.oracle_sims), int(args.max_plies)) for it in items]
    if int(args.workers) > 1:
        import multiprocessing as mp

        with mp.get_context("fork").Pool(min(args.workers, len(jobs))) as pool:
            cells = list(pool.imap_unordered(_cell, jobs))
    else:
        cells = [_cell(j) for j in jobs]

    rows, mism, discriminating = [], [], 0
    for c in cells:
        item, pick, rp = c["item"], c["pick"], c["root_player"]
        shipped, cleared = c["shipped"], c["cleared"]
        carry, fresh = c["carry"], c["fresh"]
        t_py, t_rs = c["python_secs"], c["rust_secs"]

        d_carry = diff(shipped, carry)          # THE claim
        d_fresh = diff(cleared, fresh)          # the old behaviour, unbroken
        separates = diff(shipped, cleared) is not None
        discriminating += bool(separates)
        # The carried-visit streams must agree too: same actions off different
        # trees would be a coincidence, not an identity.
        d_visits = (None if shipped["carried_in"] == carry["carried_in"]
                    else {"first": next(i for i, (x, y) in
                                        enumerate(zip(shipped["carried_in"],
                                                      carry["carried_in"])) if x != y)})
        for tag, d in (("rust_carry_vs_python_as_shipped", d_carry),
                       ("rust_fresh_vs_python_cleared", d_fresh),
                       ("carried_visit_stream", d_visits)):
            if d is not None:
                mism.append({"rid": item["rid"], "leg": tag, "detail": d})
        row = {
            "rid": item["rid"], "deck_seed": item["deck_seed"], "ply": item["ply"],
            "source": item.get("source"), "pick": pick, "root_player": rp,
            "oracle_sims": int(args.oracle_sims),
            "python_as_shipped": {"margin": shipped["margin"], "plies": shipped["plies"],
                                  "max_carried_in": max(shipped["carried_in"]),
                                  "plies_with_preexisting_root":
                                      sum(1 for x in shipped["carried_in"] if x > 0)},
            "python_cleared_per_ply": {"margin": cleared["margin"],
                                       "plies": cleared["plies"]},
            "rust_carry": {"margin": carry["margin"], "plies": carry["plies"],
                           "max_carried_in": max(carry["carried_in"])},
            "rust_fresh": {"margin": fresh["margin"], "plies": fresh["plies"]},
            "carry_matches_shipped": d_carry is None,
            "fresh_matches_cleared": d_fresh is None,
            "carried_visits_match": d_visits is None,
            "world_discriminates": separates,
            "shipped_vs_cleared": diff(shipped, cleared),
            "python_secs": round(t_py, 2), "rust_secs": round(t_rs, 2),
            "speedup": (round(t_py / t_rs, 2) if t_rs > 0 else None),
        }
        rows.append(row)
        print(f"  {item['rid']:<26} shipped={shipped['margin']:+.1f} "
              f"cleared={cleared['margin']:+.1f} | rust-carry={carry['margin']:+.1f} "
              f"rust-fresh={fresh['margin']:+.1f} | carry==shipped "
              f"{'YES' if d_carry is None else 'NO'} | fresh==cleared "
              f"{'YES' if d_fresh is None else 'NO'} | discriminates "
              f"{'YES' if separates else 'no'} | py {t_py:.1f}s rs {t_rs:.1f}s",
              flush=True)

    if not discriminating:
        mism.append({"leg": "anti-vacuity",
                     "error": "no cell separated the shipped and cleared legs, so this "
                              "run proved nothing about the carry — try more positions "
                              "or a deeper root"})
    ok = bool(rows) and not mism
    out = {
        "gate": "rustport P6 / Gap 2 — the persistent tree, three-way reproduced",
        "why": "GAP2_ORACLE_CONTINUATION_TREE.json showed the oracle continuation is a "
               "PERSISTING-TREE search and a sibling's attribution leg named the "
               "mechanism (cleared-python == rust, shipped-python != rust). This gate "
               "adds the fourth leg — rust WITH the persistent tree — and requires the "
               "two families to close in both directions.",
        "identity_surface": "the per-ply ACTION STREAM (not just the terminal margin — "
                            "row 1 of the GAP2 artifact diverges on 66 plies at "
                            "margin_delta 0.0), plus ply count, terminal margin and the "
                            "per-ply CARRIED-IN root visit counts",
        "oracle_sims": int(args.oracle_sims),
        "positions": len(rows),
        "discriminating_positions": discriminating,
        "mismatches": mism,
        "verdict": "PASS" if ok else "FAIL",
        "scope": "the clairvoyant continuation at these knobs, net-free. The persistent "
                 "tree closes Gap 2; Gap 3 (evaluator injection) and the snapshot/UCT "
                 "family remain OPEN and still fail closed.",
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(rows)} positions, {discriminating} discriminating, "
          f"{len(mism)} mismatches -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
