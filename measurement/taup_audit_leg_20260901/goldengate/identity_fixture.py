#!/usr/bin/env python3
"""⭐⭐ THE GOLDEN GATE for `--cand-tau-p` — "bit-exact when unset, and it BINDS".

Precedent and shape: `measurement/fpu_resurrection_prep/selftest_fixture/
identity_fixture.py` + `identity_diff.py` -> `FPU_BITEXACT.json`. Read that first;
this is the same instrument pointed at a different knob, and the differences below
are deliberate.

WHAT IS BEING PROVEN, AND WHAT IS NOT
-------------------------------------

`measurement/taup_audit_leg_20260901` adds `--cand-tau-p` to
`scripts/classical_search/eval_fair_puct.py` as an exact mirror of
`--cand-c-puct`. Three propositions must hold before a single deck is spent:

  ⭐ **IDENTITY.** With the flag unset, the candidate's play is BIT-IDENTICAL to
     the pre-change code. Both seats of every cell in this leg are the deployed
     champion; if the plumbing perturbed the default path, the cells would be
     grading a moved baseline against a moved candidate.
  ⭐ **THE POSITIVE CONTROL.** With `--cand-tau-p` set to a non-default value the
     play DIFFERS. ⛔ An identity result WITHOUT a positive control is worth
     nothing — a flag parsed and then dropped on the floor would pass identity
     perfectly, and "the knob never bound" is the exact defect class the
     2026-08-29 false-negative audit exists to close.
  ⭐⭐ **CANDIDATE-ONLY.** The OPPONENT's resolved `HeuristicPriorConfig` carries
     the SHARED `--tau-p` in every leg, including the control. This is the
     proposition `--tau-p` itself fails: it builds `champ_cfg_dict`, which
     `_make_opponent` feeds through the SAME `_cfg_from_dict`, so it moves BOTH
     SIDES and a "candidate tau_p" cell built on it is champion-vs-champion.
     THIS check is why the flag had to be built at all, so it is a first-class
     leg of the gate rather than a footnote.

⚠️⚠️ **THE VARIABLE HERE IS ONE FILE, NOT ONE TREE** — and that is STRONGER than
the FPU precedent, not weaker. The FPU fix edited `src/carcassonne_ai/
rust_agent.py`, so its gate had to swing a whole `PYTHONPATH`. This change is
confined to `scripts/classical_search/eval_fair_puct.py`: `src/`, `engine/` and
the `carc_rs` wheel are BYTE-IDENTICAL across the legs, so the OLD leg loads
`git show HEAD:scripts/classical_search/eval_fair_puct.py` (extracted to a scratch
dir by `run_gate.sh`) while every sibling module, every package and the wheel are
held constant by construction. `ONE-WHEEL` and `ONE-SRC` in the emitted JSON are
that claim's witnesses.

⚠️ THE BUDGET IS DELIBERATELY TINY (k2 x 96, not the champion's k16 x 1376). The
proposition is about a CODE PATH, not a budget: `tau_p` is the softmax
denominator over every root/interior expansion's Δleaf vector, so a 96-sim search
reads it thousands of times per move. ⛔ NOT a strength measurement; no number in
it may be read as one.

USAGE (see run_gate.sh — it drives all three legs and the diff)

    python identity_fixture.py --evalmod <OLD>/eval_fair_puct.py --out OLD.json
    python identity_fixture.py --evalmod <NEW>/eval_fair_puct.py --out NEW.json
    python identity_fixture.py --evalmod <NEW>/eval_fair_puct.py \
        --cand-tau-p 2.5 --out NEW_TAU25.json
    python identity_diff.py OLD.json NEW.json NEW_TAU25.json --out ../TAUP_BITEXACT.json
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

# ⚠️ The production leaf SHAPE must be frozen BEFORE carcassonne_ai is imported —
# `virtual_score_v2.DEFAULT_CONFIG` is built once, at that import, from the env.
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "scripts" / "human_anchor"))
import env_preamble  # noqa: E402,F401

#: The seeded decks the fixture plays. ⛔ FROZEN: an identity claim over a
#: caller-chosen seed set is not a claim. THROWAWAY sub-range — `THROWAWAY_BASE`
#: (171999999000, WORKERS.conf) + 800, disjoint from the smoke offsets. No
#: claimed band is touched and none ever will be.
SEEDS = tuple(range(171_999_999_800, 171_999_999_812))
FROZEN_SEED_COUNT = len(SEEDS)

#: ⛔ FROZEN search shape. Deliberately NOT the champion's k16 x 1376; see the
#: module docstring.
K_DETS = 2
SIMS_PER_DET = 96
EXACT_K = 2

#: The shared knobs the legs resolve against — the production champion's, so the
#: "unset == the champion" claim is made at the value that actually ships.
#: ⚠️ Read from PRODUCTION.yaml by `_production_knobs()`, never hard-coded: a
#: fixture that restates the champion is a fixture that can go stale silently.
_FALLBACK_C_PUCT = 1.5
_FALLBACK_TAU_P = 5.0


def _production_knobs() -> dict:
    """`(c_puct, tau_p)` of the champion of record, READ from PRODUCTION.yaml."""
    import re

    txt = (_REPO / "governance" / "PRODUCTION.yaml").read_text()
    out = {}
    for key, fallback in (("c_puct", _FALLBACK_C_PUCT), ("tau_p", _FALLBACK_TAU_P)):
        m = re.search(rf"^\s+{key}:\s*([0-9.]+)", txt, re.M)
        out[key] = float(m.group(1)) if m else float(fallback)
        out[f"{key}_source"] = ("governance/PRODUCTION.yaml" if m
                                else "FALLBACK (yaml key not found)")
    return out


def load_eval_module(path: Path, name: str):
    """Import ONE `eval_fair_puct.py` by explicit path.

    ⚠️ Its sibling modules (`c5_leaf_override`, `endgame_solver`, `tiearb_gates`,
    …) are resolved from the LIVE worktree in every leg, deliberately: they are
    byte-identical across this change, so holding them constant is what makes the
    single-file A/B a single-VARIABLE A/B."""
    live_siblings = str(_REPO / "scripts" / "classical_search")
    if live_siblings not in sys.path:
        sys.path.insert(0, live_siblings)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:            # pragma: no cover
        raise SystemExit(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def flag_expressible(mod) -> bool:
    """Does THIS module's real argparse carry `--cand-tau-p`?

    ⛔ The parser is built inside `main()`, so the only honest way to ask is to
    drive `main(["--help"])` and read what it prints. Reading a source string
    would prove the characters exist, not that argparse accepts them."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            mod.main(["--help"])
    except SystemExit:
        pass
    return "--cand-tau-p" in buf.getvalue()


def resolve_configs(mod, tau_p, knobs) -> dict:
    """The RESOLVED candidate and opponent configs, built by THIS module.

    ⭐ Both are produced by the module's own builders — `_build_champ_cfg` for the
    candidate (with the `cand_search` dict main() would have assembled) and
    `_cfg_from_dict(champ_cfg_dict)` for the opponent (the exact call
    `_make_opponent` makes). Nothing here restates a CLI value as if it were an
    observation."""
    cand_search = {"fpu_reduction": None, "c_puct": None,
                   "shared_c_puct": float(knobs["c_puct"]),
                   "shared_tau_p": float(knobs["tau_p"])}
    if tau_p is not None:
        # ⛔ On the OLD module this key is simply IGNORED by `_build_champ_cfg` —
        # which is the audited defect, reproduced as a number rather than raised
        # through. The leg records it as REQUESTED-BUT-UNREACHABLE.
        cand_search["tau_p"] = float(tau_p)
    cand = mod._build_champ_cfg(
        knobs["c_puct"], knobs["tau_p"], "float", "Q",
        mod.HeuristicPriorConfig().value_norm, None, cand_search=cand_search)
    champ_cfg_dict = {"c_puct": knobs["c_puct"], "tau_p": knobs["tau_p"],
                      "leaf_quantize": "float", "final_select": "Q",
                      "value_norm": mod.HeuristicPriorConfig().value_norm,
                      "fpu_reduction": None}
    opp = mod._cfg_from_dict(champ_cfg_dict, None)
    return {
        "cand_search": cand_search,
        "cand_cfg": {"c_puct": cand.c_puct, "tau_p": cand.tau_p,
                     "fpu_reduction": getattr(cand, "fpu_reduction", None)},
        "opp_cfg": {"c_puct": opp.c_puct, "tau_p": opp.tau_p,
                    "fpu_reduction": getattr(opp, "fpu_reduction", None)},
        "cand_cfg_obj": cand,
    }


def play(seed: int, cfg) -> dict:
    """One SELF-PLAY game at `cfg`: the action sequence is a pure function of
    (seed, cfg, budget, backend).

    ⚠️ Termination and step protocol are COPIED FROM THE PRODUCTION LOOP
    (`eval_fair_puct._play_one_inner`): `get_game_ended(board, 0) == 0.0` while
    live, `get_next_state(board, action)` (2-arg), and `agent.move()` NOT
    `best_action()` — `move()` is what advances the agent's own prefix/mirror
    bookkeeping. A fixture that drives the agent through a DIFFERENT protocol than
    production proves identity of something nobody ships."""
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
    return {
        "seed": seed,
        "n_actions": len(actions),
        "actions_sha256": hashlib.sha256(
            ",".join(map(str, actions)).encode()).hexdigest(),
        "first_8_actions": actions[:8],
        "final_scores": [int(x) for x in board.state.scores],
        # The resolved knobs, read off the CONFIG THE AGENT WAS BUILT WITH.
        "resolved_tau_p": cfg.tau_p,
        "resolved_c_puct": cfg.c_puct,
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
    ap.add_argument("--evalmod", type=Path, required=True,
                    help="the eval_fair_puct.py to load for THIS leg")
    ap.add_argument("--cand-tau-p", type=float, default=None,
                    help="candidate-side tau_p; unset == the shared --tau-p")
    ap.add_argument("--seeds", type=int, default=len(SEEDS),
                    help="how many of the FROZEN seeds to play (fewer is a cheap "
                         "PREVIEW; the gate itself uses all of them)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    import carcassonne_ai

    knobs = _production_knobs()
    mod = load_eval_module(args.evalmod.resolve(), "efp_leg")
    expressible = flag_expressible(mod)
    res = resolve_configs(mod, args.cand_tau_p, knobs)
    cfg = res.pop("cand_cfg_obj")

    requested_but_unreachable = bool(
        args.cand_tau_p is not None
        and res["cand_cfg"]["tau_p"] == float(knobs["tau_p"]))
    if requested_but_unreachable:
        # ⛔ THE AUDITED DEFECT, NAMED RATHER THAN CRASHED THROUGH. On the
        # pre-change module the `tau_p` key in `cand_search` is ignored, so the
        # leg hashes identically to the unset leg. That equality IS the finding.
        print("[taup_gate] ⛔ this eval_fair_puct IGNORES cand_search['tau_p'] — "
              "the requested knob CANNOT be expressed. Recording the leg as "
              "REQUESTED-BUT-UNREACHABLE.", flush=True)

    t0 = time.perf_counter()
    games = []
    for s in SEEDS[: max(1, int(args.seeds))]:
        games.append(play(s, cfg))
        print(f"[taup_gate] seed {s} -> {games[-1]['actions_sha256'][:16]} "
              f"({games[-1]['n_actions']} plies)", flush=True)

    out = {
        "fixture": "taup_audit_leg golden gate",
        "requested_cand_tau_p": args.cand_tau_p,
        "flag_expressible_on_this_module": expressible,
        "requested_but_unreachable": requested_but_unreachable,
        "backend": "rust",
        "evalmod": str(args.evalmod.resolve()),
        "evalmod_sha256": hashlib.sha256(
            args.evalmod.resolve().read_bytes()).hexdigest(),
        # ⭐ ONE-SRC's witness: `src/carcassonne_ai` is NOT the variable here, so
        # identity_diff refuses unless all three legs resolved the SAME package.
        "src_tree": str(Path(carcassonne_ai.__file__).resolve().parents[2]),
        "carcassonne_ai_file": str(Path(carcassonne_ai.__file__).resolve()),
        # ⭐ ONE-WHEEL's witness.
        "carc_rs_binary_sha": _rs_sha(),
        "production_knobs": knobs,
        **res,
        "budget": {"k_dets": K_DETS, "sims_per_det": SIMS_PER_DET,
                   "exact_k": EXACT_K,
                   "note": "⛔ NOT the champion's k16x1376 — this is a CODE-PATH "
                           "identity fixture, never a strength measurement."},
        "seeds": list(SEEDS[: max(1, int(args.seeds))]),
        # ⭐ So `identity_diff` can tell a PREVIEW subset from the frozen gate
        # WITHOUT importing this module (and without re-deriving the constant).
        "frozen_seed_count": FROZEN_SEED_COUNT,
        "host": socket.gethostname(),
        "python": platform.python_version(),
        "env_flat_leaf": os.environ.get("CARCASSONNE_USE_FLAT_LEAF"),
        "wall_secs": time.perf_counter() - t0,
        "games": games,
        "leg_sha256": hashlib.sha256(
            "|".join(g["actions_sha256"] for g in games).encode()).hexdigest(),
    }
    args.out.write_text(json.dumps(out, indent=2))
    print(f"[taup_gate] leg_sha256 = {out['leg_sha256']}")
    print(f"[taup_gate] wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
