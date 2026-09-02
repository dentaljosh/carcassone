#!/usr/bin/env python3
"""⭐⭐ THE GOLDEN GATE for GT-M1 risk-asymmetric world pooling — one leg.

Precedent: `measurement/taup_audit_leg_20260901/goldengate/identity_fixture.py`
→ `TAUP_BITEXACT.json`, itself after
`measurement/fpu_resurrection_prep/selftest_fixture/`. Read the τ_p one first;
this is the same instrument pointed at a different knob, and the two deliberate
differences are called out below.

WHAT IS BEING PROVEN
--------------------

  ⭐ **IDENTITY.** With `--cand-pool-mode` unset the candidate's play is
     BIT-IDENTICAL to the pre-change code — the *whole* pre-change code: the OLD
     tree AND the OLD `carc_rs` wheel. Both seats of every cell in the round are
     the deployed champion; if the plumbing perturbed the default path, the
     cells would be grading a moved baseline against a moved candidate.
  ⭐ **THE POSITIVE CONTROL.** At α = 0.25 the play DIFFERS, *and* the agent's
     own play-derived counter says WHY (`pool_pickchanges` > 0). An identity
     result without a positive control is worth nothing — a flag parsed and
     dropped on the floor passes identity perfectly, and "the knob never bound"
     is the exact defect class the 2026-08-29 false-negative audit exists to
     close.
  ⭐⭐ **CANDIDATE-ONLY.** The OPPONENT pools by the deployed visit-weighted mean
     in EVERY leg, including both dosed ones — asserted from the opponent's own
     resolved config AND from its own agent's counters, never from the absence
     of a flag. There is no `--pool-mode` at all, by design: a two-sided pooling
     change is a different CHAMPION, not a cell.
  ⚠️⚠️ **THE α = 1.0 CORRECTION.** The build brief asked for "α = 1.0 ⇒
     bit-exact with mean". **That is false, and the census that licensed this
     lever already measured it false.** α = 1.0 is the EQUAL-WEIGHT-per-world
     mean; the deployed rule is `ΣW / ΣN`, which is VISIT-weighted, and
     `measurement/cl083_mech_censuses_20260830/DEVIATIONS.md` D-1 records the
     two disagreeing on **18.1%** of contest-exposed plies. So this leg exists,
     it is expected to DIVERGE, and `identity_diff.py` adjudicates it as the
     WEIGHTING-CONTROL arm rather than as an identity. The bit-exact statement
     that IS true — `CVaR_{1.0}` == the *sorted-order* equal-weight mean — is
     arithmetic, and it is pinned in
     `carc_core::fair::pool::tests::alpha_one_is_the_sorted_order_equal_weight_mean`,
     where it belongs.

⚠️⚠️ **THE VARIABLE HERE IS A TREE *AND* A WHEEL** — the FPU precedent's shape,
not the τ_p one's. GT-M1 touches `rust/carc/carc-{core,py}`,
`src/carcassonne_ai/{heuristic_prior_mcts,rust_agent,champion_factory}.py` AND
`scripts/classical_search/eval_fair_puct.py`, so the OLD leg swings the whole
`PYTHONPATH`: an OLD source tree extracted by `git archive` plus the `carc_rs`
**already installed in the venv**, which predates the change and is verified to
have no `pool` getter. `OLD-WHEEL-IS-STALE` and `NEW-WHEEL-IS-FRESH` in the
emitted JSON are that claim's witnesses.

⚠️ THE BUDGET IS DELIBERATELY TINY (k4 × 96, not the champion's k16 × 1376). The
proposition is about a CODE PATH, not a budget. ⛔ NOT a strength measurement;
no number in it may be read as one. ⚠️ k=4 rather than the gate-usual k=2
because α = 0.25 at k = 2 selects `ceil(0.5) = 1` world and at k = 4 selects
exactly 1 as well — but k = 4 gives α = 0.5 → 2 and α = 1.0 → 4, so the three
dosed legs exercise three different `j_worlds`, which k = 2 cannot.

USAGE (see run_gate.sh — it drives all four legs and the diff)

    python identity_fixture.py --tree <OLD> --evalmod <OLD>/scripts/.../eval_fair_puct.py \\
        --out OLD.json
    python identity_fixture.py --tree <NEW> --evalmod <NEW>/scripts/.../eval_fair_puct.py \\
        --out NEW.json
    python identity_fixture.py --tree <NEW> --evalmod <NEW>/... \\
        --cand-pool-mode cvar --cand-pool-alpha 0.25 --out NEW_CVAR25.json
    python identity_diff.py OLD.json NEW.json NEW_CVAR25.json NEW_ALPHA1.json \\
        --out ../CVAR_BITEXACT.json
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import platform
import socket
import sys
import time
from pathlib import Path

#: The seeded decks the fixture plays. ⛔ FROZEN: an identity claim over a
#: caller-chosen seed set is not a claim. THROWAWAY sub-range —
#: `THROWAWAY_BASE` (175999999000, WORKERS.conf) + 800, disjoint from the two
#: cells' smoke offsets. No claimed band is touched and none ever will be.
SEEDS = tuple(range(175_999_999_800, 175_999_999_812))
FROZEN_SEED_COUNT = len(SEEDS)

#: ⛔ FROZEN search shape. Deliberately NOT the champion's k16 × 1376; see the
#: module docstring for why k=4 rather than the gate-usual k=2.
K_DETS = 4
SIMS_PER_DET = 96
EXACT_K = 2

_FALLBACK_C_PUCT = 1.5
_FALLBACK_TAU_P = 5.0


def _production_knobs(tree: Path) -> dict:
    """`(c_puct, tau_p)` of the champion of record, READ from PRODUCTION.yaml.

    ⚠️ Read, never hard-coded: a fixture that restates the champion is a fixture
    that can go stale silently. Read from THIS LEG'S tree, so an OLD leg whose
    governance differed would say so rather than borrow the new one's."""
    import re

    txt = (tree / "governance" / "PRODUCTION.yaml").read_text()
    out = {}
    for key, fallback in (("c_puct", _FALLBACK_C_PUCT), ("tau_p", _FALLBACK_TAU_P)):
        m = re.search(rf"^\s+{key}:\s*([0-9.]+)", txt, re.M)
        out[key] = float(m.group(1)) if m else float(fallback)
        out[f"{key}_source"] = ("governance/PRODUCTION.yaml" if m
                                else "FALLBACK (yaml key not found)")
    return out


def load_eval_module(path: Path, tree: Path, name: str):
    """Import ONE `eval_fair_puct.py` by explicit path.

    ⚠️ UNLIKE the τ_p gate, the sibling modules are resolved from THIS LEG'S OWN
    TREE, not from the live worktree. That gate could hold siblings constant
    because its change was one file; this change spans `src/` and the wheel, so
    a leg must be a coherent tree end to end or the A/B has two variables it
    cannot name."""
    siblings = str(tree / "scripts" / "classical_search")
    if siblings not in sys.path:
        sys.path.insert(0, siblings)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:            # pragma: no cover
        raise SystemExit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def flag_expressible(mod) -> bool:
    """Does THIS module's real argparse carry `--cand-pool-mode`?

    ⛔ The parser is built inside `main()`, so the only honest way to ask is to
    drive `main(["--help"])` and read what it prints. Reading a source string
    would prove the characters exist, not that argparse accepts them."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            mod.main(["--help"])
    except SystemExit:
        pass
    return "--cand-pool-mode" in buf.getvalue()


def resolve_configs(mod, mode: str, alpha, knobs) -> dict:
    """The RESOLVED candidate and opponent configs, built by THIS module.

    ⭐ Both are produced by the module's own builders — `_build_champ_cfg` for
    the candidate (with the `cand_search` dict `main()` would have assembled)
    and `_cfg_from_dict(champ_cfg_dict)` for the opponent (the exact call
    `_make_opponent` makes). Nothing here restates a CLI value as if it were an
    observation."""
    cand_search = {"fpu_reduction": None, "c_puct": None, "tau_p": None,
                   "shared_c_puct": float(knobs["c_puct"]),
                   "shared_tau_p": float(knobs["tau_p"]),
                   "pool_mode": mode,
                   "pool_alpha": (None if alpha is None else float(alpha))}
    cand = mod._build_champ_cfg(
        knobs["c_puct"], knobs["tau_p"], "float", "Q",
        mod.HeuristicPriorConfig().value_norm, None, cand_search=cand_search)
    champ_cfg_dict = {"c_puct": knobs["c_puct"], "tau_p": knobs["tau_p"],
                      "leaf_quantize": "float", "final_select": "Q",
                      "value_norm": mod.HeuristicPriorConfig().value_norm,
                      "fpu_reduction": None}
    opp = mod._cfg_from_dict(champ_cfg_dict, None)

    def _pool_of(cfg):
        return {"pool_mode": getattr(cfg, "pool_mode", "MISSING"),
                "pool_alpha": getattr(cfg, "pool_alpha", "MISSING")}

    return {
        "cand_search": cand_search,
        "cand_cfg": {"c_puct": cand.c_puct, "tau_p": cand.tau_p,
                     "fpu_reduction": getattr(cand, "fpu_reduction", None),
                     **_pool_of(cand)},
        # ⭐⭐ THE OPPONENT, from ITS OWN BUILDER. This is the candidate-only
        # proposition, and unlike τ_p's it is unconditional: there is no shared
        # `--pool-mode` that could legitimately move it.
        "opp_cfg": {"c_puct": opp.c_puct, "tau_p": opp.tau_p,
                    "fpu_reduction": getattr(opp, "fpu_reduction", None),
                    **_pool_of(opp)},
        "cand_cfg_obj": cand,
    }


def _rs_pool_readback(cfg) -> dict:
    """What the RUST config actually holds — the readback that turns "the flag
    was accepted" into "the value reached the backend that plays".

    ⛔ `has_pool_getter is False` is the STALE-WHEEL signal, and it is the OLD
    leg's expected state. It is recorded rather than raised: on the OLD leg the
    absence IS the finding."""
    out = {"has_pool_getter": False, "pool": None, "error": None}
    try:
        from carcassonne_ai.rust_agent import search_config_rs
        sc = search_config_rs(cfg, 8)
        got = getattr(sc, "pool", None)
        out["has_pool_getter"] = got is not None
        out["pool"] = (None if got is None else
                       {"mode": str(dict(got).get("mode")),
                        "alpha": (None if dict(got).get("alpha") is None
                                  else float(dict(got)["alpha"]))})
    except Exception as e:                                     # noqa: BLE001
        # A stale wheel raises TypeError on the unexpected kwargs — fail-closed
        # LOUD by design. On the OLD leg with the knob UNSET no kwarg is passed
        # at all, so this stays None and the leg runs.
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def play(seed: int, cfg) -> dict:
    """One SELF-PLAY game at `cfg`: the action sequence is a pure function of
    (seed, cfg, budget, backend).

    ⚠️ Termination and step protocol are COPIED FROM THE PRODUCTION LOOP
    (`eval_fair_puct._play_one_inner`): `get_game_ended(board, 0) == 0.0` while
    live, `get_next_state(board, action)` (2-arg), and `agent.move()` NOT
    `best_action()` — `move()` is what advances the agent's own prefix/mirror
    bookkeeping. A fixture that drives the agent through a DIFFERENT protocol
    than production proves identity of something nobody ships."""
    import random

    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.game_wrapper import Game

    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    agent = CF.build_fair_champion(
        game, cfg=cfg, sims=SIMS_PER_DET, k_dets=K_DETS, seed=seed,
        exact_max_k=EXACT_K, backend="rust", rust_threads=1)
    drives_mirror = hasattr(agent, "start_game") and hasattr(agent, "advance")
    if drives_mirror:
        agent.start_game(board)

    actions: list[int] = []
    plies = 0
    while game.get_game_ended(board, 0) == 0.0 and plies < 400:
        a = int(agent.move(board))
        actions.append(a)
        board, _ = game.get_next_state(board, a)
        if drives_mirror:
            agent.advance(a)
        plies += 1
    # ⭐⭐ THE PLAY-DERIVED WITNESS, read off the agent that actually played.
    # `pool_pickchanges` is the ONLY thing that distinguishes "the rule bound"
    # from "the flag was typed" — this knob moves no leaf hash and the config
    # can only echo the request.
    pool_stats = None
    rs = getattr(agent, "_rs", None)
    if rs is not None:
        try:
            s = rs.stats()
            pool_stats = {k: s[k] for k in
                          ("pool_mode", "pool_alpha", "pool_cvar_plies",
                           "pool_pickchanges", "pool_fallbacks",
                           "pool_eligible_total") if k in s} or None
        except Exception as e:                                 # noqa: BLE001
            pool_stats = {"error": f"{type(e).__name__}: {e}"}
    return {
        "seed": seed,
        "n_actions": len(actions),
        "actions_sha256": hashlib.sha256(
            ",".join(map(str, actions)).encode()).hexdigest(),
        "first_8_actions": actions[:8],
        "final_scores": [int(x) for x in board.state.scores],
        # The resolved knobs, read off the CONFIG THE AGENT WAS BUILT WITH.
        "resolved_pool_mode": getattr(cfg, "pool_mode", "MISSING"),
        "resolved_pool_alpha": getattr(cfg, "pool_alpha", "MISSING"),
        "pool_stats": pool_stats,
    }


def _rs_sha():
    try:
        from carcassonne_ai.rust_agent import carc_rs_binary_sha
        return carc_rs_binary_sha()
    except Exception:                                          # noqa: BLE001
        return "unavailable"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", type=Path, required=True,
                    help="the REPO ROOT this leg runs as (its src/, engine/, "
                         "scripts/ and governance/ are the leg's own)")
    ap.add_argument("--evalmod", type=Path, required=True,
                    help="the eval_fair_puct.py to load for THIS leg")
    ap.add_argument("--cand-pool-mode", choices=("mean", "cvar"), default="mean")
    ap.add_argument("--cand-pool-alpha", type=float, default=None)
    ap.add_argument("--seeds", type=int, default=len(SEEDS),
                    help="how many of the FROZEN seeds to play (fewer is a cheap "
                         "PREVIEW; the gate itself uses all of them)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    tree = args.tree.resolve()
    # ⚠️ The production leaf SHAPE must be frozen BEFORE carcassonne_ai is
    # imported — `virtual_score_v2.DEFAULT_CONFIG` is built once, at that
    # import, from the env. `env_preamble` comes from THIS LEG'S tree.
    sys.path.insert(0, str(tree / "scripts" / "human_anchor"))
    import env_preamble  # noqa: E402,F401

    import carcassonne_ai

    knobs = _production_knobs(tree)
    mod = load_eval_module(args.evalmod.resolve(), tree, "efp_leg")
    expressible = flag_expressible(mod)
    res = resolve_configs(mod, args.cand_pool_mode, args.cand_pool_alpha, knobs)
    cfg = res.pop("cand_cfg_obj")
    rs_pool = _rs_pool_readback(cfg)

    # ⛔ THE AUDITED DEFECT, NAMED RATHER THAN CRASHED THROUGH: on a tree that
    # predates GT-M1 the `pool_mode` key in `cand_search` is simply ignored by
    # `_build_champ_cfg`, so a dosed leg would hash identically to the unset
    # one. That equality would BE the finding, so it is labelled here.
    requested_but_unreachable = bool(
        args.cand_pool_mode != "mean"
        and str(res["cand_cfg"].get("pool_mode")) in ("mean", "MISSING"))
    if requested_but_unreachable:
        print("[cvar_gate] ⛔ this tree IGNORES cand_search['pool_mode'] — the "
              "requested rule CANNOT be expressed. Recording the leg as "
              "REQUESTED-BUT-UNREACHABLE.", flush=True)

    t0 = time.perf_counter()
    games = []
    for s in SEEDS[: max(1, int(args.seeds))]:
        games.append(play(s, cfg))
        ps = games[-1].get("pool_stats") or {}
        print(f"[cvar_gate] seed {s} -> {games[-1]['actions_sha256'][:16]} "
              f"({games[-1]['n_actions']} plies, cvar_plies="
              f"{ps.get('pool_cvar_plies')}, pickchanges="
              f"{ps.get('pool_pickchanges')})", flush=True)

    out = {
        "fixture": "cvar_pool_prep golden gate (GT-M1)",
        "requested_pool_mode": args.cand_pool_mode,
        "requested_pool_alpha": args.cand_pool_alpha,
        "flag_expressible_on_this_module": expressible,
        "requested_but_unreachable": requested_but_unreachable,
        "backend": "rust",
        "tree": str(tree),
        "evalmod": str(args.evalmod.resolve()),
        "evalmod_sha256": hashlib.sha256(
            args.evalmod.resolve().read_bytes()).hexdigest(),
        # ⭐ The TREE witness: unlike the τ_p gate, `src/carcassonne_ai` IS a
        # variable here, so identity_diff asserts OLD != NEW and NEW == the
        # dosed legs.
        "src_tree": str(Path(carcassonne_ai.__file__).resolve().parents[2]),
        "carcassonne_ai_file": str(Path(carcassonne_ai.__file__).resolve()),
        # ⭐ The WHEEL witness. OLD runs the venv's INSTALLED carc_rs (which
        # predates GT-M1); NEW runs the freshly built one.
        "carc_rs_binary_sha": _rs_sha(),
        "carc_rs_file": _carc_rs_file(),
        "rust_pool_readback": rs_pool,
        "production_knobs": knobs,
        **res,
        "budget": {"k_dets": K_DETS, "sims_per_det": SIMS_PER_DET,
                   "exact_k": EXACT_K,
                   "note": "⛔ NOT the champion's k16x1376 — this is a CODE-PATH "
                           "identity fixture, never a strength measurement."},
        "seeds": list(SEEDS[: max(1, int(args.seeds))]),
        "frozen_seed_count": FROZEN_SEED_COUNT,
        "host": socket.gethostname(),
        "python": platform.python_version(),
        "env_flat_leaf": os.environ.get("CARCASSONNE_USE_FLAT_LEAF"),
        "wall_secs": time.perf_counter() - t0,
        "games": games,
        "leg_sha256": hashlib.sha256(
            "|".join(g["actions_sha256"] for g in games).encode()).hexdigest(),
    }
    args.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"[cvar_gate] leg_sha256 = {out['leg_sha256']}")
    print(f"[cvar_gate] wrote {args.out}")
    return 0


def _carc_rs_file() -> str:
    try:
        import carc_rs
        return str(Path(carc_rs.__file__).resolve())
    except Exception:                                          # noqa: BLE001
        return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
