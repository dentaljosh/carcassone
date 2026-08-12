"""G2 — the rustport leaf gate.  0 mismatches, full stop.

Compares the Rust leaf (`carc_rs.MirrorState.leaf_value{,_float}`) against
**both** Python leaf paths on every position of every corpus:

  * `carcassonne_ai.flat_leaf` with ``USE_CY_LEAF = False`` — the pure-Python
    flat leaf;
  * `carcassonne_ai.flat_leaf_cy` — the compiled Cython twin, called directly
    (not through the dispatcher, so a capability-flag fallback cannot silently
    turn this leg into the Python one).

Both the ``int`` leaf (`flat_virtual_score_v2`) and the **pre-round float** leaf
(`flat_virtual_score_v2_float`, which is what `leaf_quantize: float` in
`governance/PRODUCTION.yaml` makes the champion actually use) are compared
**bit-exactly** — floats via `float.hex()`, so a 1-ulp or a signed-zero
difference is a mismatch.

Also checked, at every position:

  * `flat_base_score` three ways — pure-Python flat, Cython flat, and the Rust
    flat decomposition — plus the Rust **engine** route (P1's clone +
    `count_final_scores`), which makes the decomposition's partition an
    independent invariant rather than a self-consistency check.

Corpora (`--corpus`, repeatable, or `all`):

  golden   `tests/golden/golden_fixture.json` — the 12 recorded games replayed
           per ply, **plus** every leaf value frozen on disk: the 56 positions'
           ``vs`` triple (v27/v28/v29 dialects x both POVs) and their
           ``flat_base_score`` pair, compared against the FILE, not against a
           live Python re-computation.
  midgame  `measurement/midgame_reference/MIDGAME_POSITION_SAMPLE.jsonl`
           (1000 snapshots; `source_game_seed` + `prefix`).
  k3       `measurement/f3_public_state_oracle/roots_k3_suite.jsonl` (354
           K=3 endgame roots from greedy self-play; reconstructed by replaying
           `RuleBasedPlayer(seed=GEN_PLAYER_SEED)` exactly as
           `gen_endgame_positions.replay_to` does, capturing the action ints so
           the Rust mirror can be driven by the same wire format).
  distill  `measurement/utility_calibration_20260721/gen_games_champ125.jsonl`
           — champion-generated (curve125) games; replayed per ply at `--stride`.
  champ    all 449 games of `measurement/champ_action_logs/champ_games.jsonl`.
  e4       both `measurement/e4_games/*.json` phone archives.
  panel    the `champion_factory._LEAF_VALUE_PANEL` semantic guard, reproduced
           against `carc_rs` (empty board, explicit free-meeple counts).

Config matrix (`--configs`): `core` = the production curve125 leaf + the three
fixture dialects; `all` adds the off-production stressors that
`scripts/reconcile_cy_leaf.py` uses (pre-v2.7 caps, a weird schedule, the two C7
wave-2 terms, the F6 soft caps, the v2.10 bag-close gate); `farmoff` = `core` plus
the three **F7b farm knockouts** (`farm_base_off`, `farm_growth_off`, both); `phase`
= `core` plus seven **Part C phase-multiplier** cells (`v29_phase_beta` /
`v29_phase_norm`, prereg `measurement/curve_shape_scope_20260809/PREREG_DRAFT.md` §4)
including a beta=0 identity control and two betas large enough to exercise the
`clip(., 0, 2)` clamp at both deck ends. `phase` is a full THREE-leg family
(py == cy == rust) — unlike `farmoff`, the Cython leaf implements it. `denial` =
`core` plus four **targeted-denial** cells (`denial_dose` / `denial_size_min` /
`denial_open_max`, LEVER_INDEX "targeted denial", building 2026-08-11) including
a dose=0 identity control with MOVED thresholds (must reproduce `prod-curve125`
exactly — the dose gates the whole term).

⚠️ The `farmoff` and `denial-d*` configs are the families compared on **two** legs, not three:
`flat_leaf_cy.pyx` deliberately does not implement them (roadmap F7b — the ablation
cells run `--backend rust`, so no Python leaf is computed in-cell, and the exact-K
tail scores the TRUE final score with farms intact by design). For those configs the
Cython leg is skipped and the identity reduces to **pure-Python == Rust**;
`tests/test_f7b_farm_knockout.py` separately proves the dispatcher refuses the cy
fast path for them, so a stale `.so` can never serve an intact-farm leaf.

Usage:
    .venv/bin/python scripts/rustport/reconcile_leaf.py --corpus all --workers 12
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "level2", REPO / "scripts" / "rustport"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

# ⚠️ BEFORE any carcassonne_ai import. This script builds every LeafConfig
# explicitly and never reads DEFAULT_CONFIG — but it is imported by
# tests/rustport/test_p2_leaf.py, so if it wins the DEFAULT_CONFIG freeze race in
# a full-tree pytest it would leave the session-global default at the bare cap-5
# shape and every later verify=True champion build would raise ProvenanceError.
import prod_leaf_env  # noqa: E402,F401

import carc_rs  # noqa: E402
from _g0_common import environment  # noqa: E402
from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai import flat_leaf_cy as cyleaf  # noqa: E402
from carcassonne_ai.virtual_score_v2 import LeafConfig  # noqa: E402
from root_replay import replay_actions  # noqa: E402

# The pure-Python leg must never be routed to the .so.  Flip once, at import,
# and call the Cython entry points directly for the other leg.
flat_leaf.USE_CY_LEAF = False

OUTDIR = REPO / "measurement" / "rustport_p2"
GOLDEN = REPO / "tests" / "golden" / "golden_fixture.json"
CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4DIR = REPO / "measurement" / "e4_games"
MIDGAME = REPO / "measurement" / "midgame_reference" / "MIDGAME_POSITION_SAMPLE.jsonl"
K3 = REPO / "measurement" / "f3_public_state_oracle" / "roots_k3_suite.jsonl"
DISTILL = REPO / "measurement" / "utility_calibration_20260721" / "gen_games_champ125.jsonl"

CORPORA = ["golden", "midgame", "k3", "distill", "champ", "e4", "panel"]


# ---------------------------------------------------------------------------
# Config matrix
# ---------------------------------------------------------------------------
_CLOSURE = {1: 0.5, 2: 0.2, 3: 0.05}          # the Bmild schedule (DROP_THREE_OPEN=0)
_CURVE_V29 = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)
_CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)   # governance/PRODUCTION.yaml


# F7b farm-knockout + targeted-denial configs. These are the TWO knob families the
# Cython leaf deliberately does not implement (roadmap F7b / the denial build
# 2026-08-11: the candidate cells run `--backend rust`, where no Python leaf is
# computed at all), so for these the gate runs TWO legs — pure-Python flat vs Rust —
# and asserts separately that the DISPATCHER refuses the cy fast path for them
# (tests/test_f7b_farm_knockout.py / tests/test_denial_term.py).
CY_UNSUPPORTED = frozenset({"farmbaseoff", "farmgrowthoff", "farmbothoff",
                            "denial-d0.5", "denial-d1.0", "denial-d2.0-s6-o3"})


def _cfgs(which: str) -> dict[str, LeafConfig]:
    core = {
        # the leaf of record: v2_9_2_Bmild_cap8_curve125 (leaf_hash a36d2e15a3b3d71d)
        "prod-curve125": LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                                    meeple_k=2.0, v29_meeple_curve=_CURVE125),
        # the three dialects golden_fixture.json is frozen on (tests/golden/_golden_common.py)
        "v27": LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0),
        "v28": LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                          meeple_k=2.0),
        "v29": LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                          meeple_k=2.0, v29_meeple_curve=_CURVE_V29),
    }
    if which == "core":
        return core
    if which == "phase":
        # Part C phase multiplier (prereg curve_shape_scope_20260809 §4). Built on the
        # champion leaf so the ONLY difference from `prod-curve125` is the phase weight.
        # Betas are the pre-registered ladder's rungs; two cells carry a NON-1.0 norm so
        # the divide is exercised too. `phase-b0-norm1` is the IDENTITY control — it must
        # reproduce `prod-curve125` exactly on every leg.
        prodp = dict(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                     meeple_k=2.0, v29_meeple_curve=_CURVE125)
        core.update({
            "phase-b0-norm1": LeafConfig(**prodp, v29_phase_beta=0.0, v29_phase_norm=1.0),
            "phase-b+0.3": LeafConfig(**prodp, v29_phase_beta=0.3, v29_phase_norm=1.0),
            "phase-b-0.3": LeafConfig(**prodp, v29_phase_beta=-0.3, v29_phase_norm=1.0),
            "phase-b+0.6-n1.07": LeafConfig(**prodp, v29_phase_beta=0.6, v29_phase_norm=1.0723),
            "phase-b-0.6-n0.93": LeafConfig(**prodp, v29_phase_beta=-0.6, v29_phase_norm=0.9277),
            # beta big enough that clip(.,0,2) BITES at both deck ends (k=0 -> 1-3 < 0,
            # k=71 -> 1+3.09 > 2), so the clamp is covered by the 3-way gate as well.
            "phase-b+3.0-clip": LeafConfig(**prodp, v29_phase_beta=3.0, v29_phase_norm=1.0),
            "phase-b-3.0-clip": LeafConfig(**prodp, v29_phase_beta=-3.0, v29_phase_norm=1.0),
        })
        return core
    if which == "denial":
        # Targeted denial (LeafConfig.denial_dose/_size_min/_open_max). Built on the
        # champion leaf so the ONLY difference from `prod-curve125` is the denial
        # term. `denial-d0-identity` is the IDENTITY control — dose 0.0 with the
        # thresholds MOVED must reproduce `prod-curve125` exactly on every leg (the
        # dose gates the whole term; thresholds are inert while it is 0.0). The
        # d0.5/d1.0 cells are the prereg screen doses at the default (8, 2) knobs;
        # the d2.0 cell moves ALL THREE knobs so size_min/open_max are exercised.
        prodd = dict(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                     meeple_k=2.0, v29_meeple_curve=_CURVE125)
        core.update({
            "denial-d0-identity": LeafConfig(**prodd, denial_dose=0.0,
                                             denial_size_min=4.0, denial_open_max=3),
            "denial-d0.5": LeafConfig(**prodd, denial_dose=0.5),
            "denial-d1.0": LeafConfig(**prodd, denial_dose=1.0),
            "denial-d2.0-s6-o3": LeafConfig(**prodd, denial_dose=2.0,
                                            denial_size_min=6.0, denial_open_max=3),
        })
        return core
    if which == "farmoff":
        # The two F7b cells, plus both-off (the joint knockout: a farm-blind leaf).
        # Built on the champion leaf so the ONLY difference from `prod-curve125` is
        # the knocked-out farm term — the same contrast the ablation cells play.
        prod = dict(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                    meeple_k=2.0, v29_meeple_curve=_CURVE125)
        core.update({
            "farmbaseoff": LeafConfig(**prod, farm_base_off=True),
            "farmgrowthoff": LeafConfig(**prod, farm_growth_off=True),
            "farmbothoff": LeafConfig(**prod, farm_base_off=True, farm_growth_off=True),
        })
        return core
    c7 = dict(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0, meeple_k=2.0,
              v29_meeple_curve=_CURVE_V29)
    soft = dict(closure_p={1: 1.0, 2: 0.5, 3: 0.25}, bonus_cap=1.0, opp_bonus_cap=1.0)
    core.update({
        "pre-v2.7": LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=5.0, opp_bonus_cap=5.0),
        "weird": LeafConfig(closure_p={1: 1.0}, bonus_cap=3.0, opp_bonus_cap=7.5,
                            meeple_k=0.35),
        "c7-R1.0": LeafConfig(**c7, v29_meeple_return_k=1.0),
        "c7-F0.5": LeafConfig(**c7, v29_farm_flip_k=0.5),
        "c7-both": LeafConfig(**c7, v29_meeple_return_k=1.0, v29_farm_flip_k=0.5),
        "f6-soft0.5/0.25": LeafConfig(**soft, soft_cap_slope=0.5, opp_soft_cap_slope=0.25),
        "f6-soft1.0": LeafConfig(**soft, soft_cap_slope=1.0, opp_soft_cap_slope=1.0),
        "bag-close": LeafConfig(closure_p=dict(_CLOSURE), bonus_cap=8.0, opp_bonus_cap=8.0,
                                meeple_k=2.0, v29_meeple_curve=_CURVE125, bag_close=True),
    })
    return core


def leaf_provenance() -> dict:
    """Prove the config we grade against IS the champion leaf of record.

    `governance/PRODUCTION.yaml` says to assert the curve VALUES first (robust to
    LeafConfig shape drift) and the fingerprint second; both are done here, and
    the run is refused if either fails — a green gate against the wrong leaf is
    worse than a red one.
    """
    from carcassonne_ai.alphabeta_agent import _leaf_hash

    cfg = _cfgs("core")["prod-curve125"]
    curve = tuple(float(x) for x in cfg.v29_meeple_curve)
    got = _leaf_hash(cfg)
    if curve != _CURVE125:
        raise SystemExit(f"prod-curve125 curve is {curve!r}, expected {_CURVE125!r}")
    if got != "a36d2e15a3b3d71d":
        raise SystemExit(f"prod-curve125 _leaf_hash is {got!r}, expected a36d2e15a3b3d71d")
    return {"leaf": "v2_9_2_Bmild_cap8_curve125", "leaf_hash": got,
            "curve125": list(curve), "bonus_cap": cfg.bonus_cap,
            "opp_bonus_cap": cfg.opp_bonus_cap,
            "closure_p": {str(k): v for k, v in sorted(cfg.closure_p.items())},
            "source": "governance/PRODUCTION.yaml champion.leaf_config"}


def _to_rs(cfg: LeafConfig):
    curve = cfg.v29_meeple_curve
    return carc_rs.LeafConfigRs(
        sorted((int(k), float(v)) for k, v in cfg.closure_p.items()),
        float(cfg.bonus_cap),
        float(cfg.opp_bonus_cap),
        float(cfg.meeple_k),
        [float(x) for x in curve] if curve else None,
        float(getattr(cfg, "soft_cap_slope", 0.0)),
        float(getattr(cfg, "opp_soft_cap_slope", 0.0)),
        float(cfg.v29_meeple_return_k),
        float(cfg.v29_farm_flip_k),
        bool(getattr(cfg, "bag_close", False)),
        bool(cfg.tile_counting_closure),
        float(cfg.closure_continuous_slack),
        bool(getattr(cfg, "farm_base_off", False)),
        bool(getattr(cfg, "farm_growth_off", False)),
        float(getattr(cfg, "v29_phase_beta", 0.0)),
        float(getattr(cfg, "v29_phase_norm", 1.0)),
        # Targeted denial — passed unconditionally here (the gate always runs a
        # denial-capable carc_rs build; production's conditional-kwarg tolerance
        # for a stale .so lives in rust_agent.leaf_config_rs, not in the gate).
        float(getattr(cfg, "denial_dose", 0.0)),
        float(getattr(cfg, "denial_size_min", 8.0)),
        int(getattr(cfg, "denial_open_max", 2)),
    )


# ---------------------------------------------------------------------------
# The three leaf legs
# ---------------------------------------------------------------------------
def _py(state, p: int, cfg) -> tuple[int, float]:
    """Pure-Python flat leaf (USE_CY_LEAF is False, set at import)."""
    return (int(flat_leaf.flat_virtual_score_v2(state, p, cfg)),
            float(flat_leaf.flat_virtual_score_v2_float(state, p, cfg)))


def _cy(state, p: int, cfg) -> tuple[int, float]:
    """Cython flat leaf, called directly (no dispatcher, no capability fallback)."""
    bag = bool(getattr(cfg, "bag_close", False))
    return (int(cyleaf.flat_virtual_score_v2_cy(state, p, cfg, bag)),
            float(cyleaf.flat_virtual_score_v2_cy_float(state, p, cfg, bag)))


def _rs(ms, p: int, rcfg) -> tuple[int, float]:
    return int(ms.leaf_value(p, rcfg)), float(ms.leaf_value_float(p, rcfg))


def _hx(x: float) -> str:
    """Bit-exact float identity (distinguishes +0.0 from -0.0)."""
    return float(x).hex()


# ---------------------------------------------------------------------------
# One position, all configs, three legs
# ---------------------------------------------------------------------------
def check_position(state, ms, cfgs, rcfgs, tag: str, out: dict) -> None:
    out["positions"] += 1

    # --- flat_base_score: 4 routes ---
    for p in (0, 1):
        b_py = int(flat_leaf.flat_base_score(state, p))
        b_cy = int(cyleaf.flat_base_score_cy(state, p))
        b_rs = int(ms.flat_base_score_decomp(p))
        b_eng = int(ms.flat_base_score(p))
        out["values"] += 4
        if not (b_py == b_cy == b_rs == b_eng):
            out["mismatches"].append({
                "kind": "flat_base_score", "where": tag, "pov": p,
                "python": b_py, "cython": b_cy, "rust_flat": b_rs, "rust_engine": b_eng})

    # --- the leaf itself ---
    for name, cfg in cfgs.items():
        rcfg = rcfgs[name]
        # F7b farm knockouts: two legs (see CY_UNSUPPORTED). `cy` is set to the
        # python leg so the identity below reduces to python==rust WITHOUT weakening
        # the comparison for every other config.
        two_leg = name in CY_UNSUPPORTED
        for p in (0, 1):
            py_i, py_f = _py(state, p, cfg)
            cy_i, cy_f = (py_i, py_f) if two_leg else _cy(state, p, cfg)
            rs_i, rs_f = _rs(ms, p, rcfg)
            out["values"] += 2
            out["by_config"][name] = out["by_config"].get(name, 0) + 2
            if not (py_i == cy_i == rs_i):
                out["mismatches"].append({
                    "kind": "leaf_int", "where": tag, "cfg": name, "pov": p,
                    "python": py_i, "cython": cy_i, "rust": rs_i})
            hpy, hcy, hrs = _hx(py_f), _hx(cy_f), _hx(rs_f)
            if not (hpy == hcy == hrs):
                out["mismatches"].append({
                    "kind": "leaf_float", "where": tag, "cfg": name, "pov": p,
                    "python": hpy, "cython": hcy, "rust": hrs,
                    "python_repr": repr(py_f), "rust_repr": repr(rs_f),
                    "rust_terms": dict(ms.leaf_terms(p, rcfg))})
            # A knockout that never changes a value would produce a null cell for a
            # boring reason. Count how often it actually bites vs the champion leaf.
            if two_leg and "prod-curve125" in cfgs:
                prod_f = _py(state, p, cfgs["prod-curve125"])[1]
                out["knockout_seen"][name] = out["knockout_seen"].get(name, 0) + 1
                if _hx(prod_f) != _hx(py_f):
                    out["knockout_bites"][name] = out["knockout_bites"].get(name, 0) + 1


def _new_out() -> dict:
    return {"positions": 0, "values": 0, "mismatches": [], "by_config": {},
            "disk_values": 0, "plies": 0, "knockout_seen": {}, "knockout_bites": {}}


def _merge(a: dict, b: dict) -> None:
    a["positions"] += b["positions"]
    a["values"] += b["values"]
    a["disk_values"] += b["disk_values"]
    a["plies"] += b["plies"]
    a["mismatches"].extend(b["mismatches"])
    for k, v in b["by_config"].items():
        a["by_config"][k] = a["by_config"].get(k, 0) + v
    for key in ("knockout_seen", "knockout_bites"):
        for k, v in b.get(key, {}).items():
            a[key][k] = a[key].get(k, 0) + v


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
def _replay_job(job: dict) -> dict:
    """A (deck_seed, actions) game replayed in lockstep; leaf-checked at the
    plies named by `check_plies` (or every `stride`-th ply)."""
    cfgs = _cfgs(job["configs"])
    rcfgs = {n: _to_rs(c) for n, c in cfgs.items()}
    out = _new_out()
    seed, actions = job["deck_seed"], job["actions"]
    want = job.get("check_plies")
    stride = job.get("stride", 1)

    game, board = replay_actions(seed, actions, 0)
    ms = carc_rs.MirrorState.from_seed(str(seed))
    for i in range(len(actions) + 1):
        hit = (i in want) if want is not None else (i % stride == 0)
        if hit:
            check_position(board.state, ms, cfgs, rcfgs, f"{job['label']}@{i}", out)
        if i < len(actions):
            board, _ = game.get_next_state(board, int(actions[i]))
            ms.advance(int(actions[i]))
            out["plies"] += 1
    game.clear_caches()
    return out


def _greedy_job(job: dict) -> dict:
    """A K3 record: replay the deterministic greedy generator policy, capturing
    the action ints so the Rust mirror can be driven by the same wire format.
    Mirrors `gen_endgame_positions.replay_to` exactly."""
    import gen_endgame_positions as GEP
    from carcassonne_ai.rule_based_player import RuleBasedPlayer

    cfgs = _cfgs(job["configs"])
    rcfgs = {n: _to_rs(c) for n, c in cfgs.items()}
    out = _new_out()

    seed, ply = job["deck_seed"], job["ply"]
    random.seed(seed)                       # fixes the deck shuffle
    game = GEP._new_game()
    board = game.get_init_board()
    player = RuleBasedPlayer(seed=GEP.GEN_PLAYER_SEED)
    ms = carc_rs.MirrorState.from_seed(str(seed))
    for _ in range(ply):
        mask = game.get_valid_moves(board)
        a = int(player.choose_action(game, board, mask))
        board, _ = game.get_next_state(board, a)
        ms.advance(a)
        out["plies"] += 1
    # provenance: the mirror must be on the same position before we grade it
    if game.string_representation(board) != ms.string_repr():
        out["mismatches"].append({"kind": "greedy_replay_desync", "where": job["label"]})
        return out
    check_position(board.state, ms, cfgs, rcfgs, job["label"], out)
    game.clear_caches()
    return out


def _golden_disk_job(job: dict) -> dict:
    """Re-judge the leaf values FROZEN ON DISK in golden_fixture.json against
    Rust: the 56 positions' `vs` triple (3 dialects x 2 POVs) and their
    `flat_base_score` pair.  Does not trust the live Python."""
    cfgs = _cfgs("core")
    rcfgs = {n: _to_rs(c) for n, c in cfgs.items()}
    out = _new_out()
    seed, actions = job["deck_seed"], job["actions"]
    frozen = {int(p["ply"]): p for p in job["frozen"]}

    game, board = replay_actions(seed, actions, 0)
    ms = carc_rs.MirrorState.from_seed(str(seed))
    for i in range(len(actions) + 1):
        fp = frozen.get(i)
        if fp is not None:
            out["positions"] += 1
            want_base = [int(x) for x in fp["flat_base_score"]]
            got_base = [int(ms.flat_base_score_decomp(0)), int(ms.flat_base_score_decomp(1))]
            out["disk_values"] += 2
            if got_base != want_base:
                out["mismatches"].append({
                    "kind": "golden_disk_flat_base_score", "position_id": fp["id"],
                    "where": f"{job['label']}@{i}", "disk": want_base, "rust": got_base})
            for dialect, want in fp["vs"].items():
                rcfg = rcfgs[dialect]
                got = [int(ms.leaf_value(0, rcfg)), int(ms.leaf_value(1, rcfg))]
                out["disk_values"] += 2
                out["by_config"][dialect] = out["by_config"].get(dialect, 0) + 2
                if got != [int(x) for x in want]:
                    out["mismatches"].append({
                        "kind": "golden_disk_leaf", "position_id": fp["id"], "cfg": dialect,
                        "where": f"{job['label']}@{i}", "disk": [int(x) for x in want],
                        "rust": got})
        if i < len(actions):
            board, _ = game.get_next_state(board, int(actions[i]))
            ms.advance(int(actions[i]))
            out["plies"] += 1
    game.clear_caches()
    return out


def _panel_job(job: dict) -> dict:
    """The `_LEAF_VALUE_PANEL` semantic guard, reproduced against carc_rs.

    The panel is `champion_factory`'s deepest leaf guard: an empty board with
    explicit free-meeple counts, so the leaf value reduces to the curve
    differential and any cap/term/curve change flips it.
    """
    from carcassonne_ai.champion_factory import _LEAF_VALUE_PANEL

    out = _new_out()
    cfg = _cfgs("core")["prod-curve125"]
    rcfg = _to_rs(cfg)
    for label, (meeples, kind, golden) in _LEAF_VALUE_PANEL.items():
        ms = carc_rs.MirrorState.from_seed("1")
        ms.make_empty_panel_state(int(meeples[0]), int(meeples[1]))
        got = float(ms.leaf_value_float(0, rcfg)) if kind == "float" \
            else int(ms.leaf_value(0, rcfg))
        out["positions"] += 1
        out["disk_values"] += 1
        ok = (_hx(got) == _hx(golden)) if kind == "float" else (got == golden)
        if not ok:
            out["mismatches"].append({
                "kind": "leaf_value_panel", "where": label, "meeples": list(meeples),
                "golden": golden, "rust": got})
    return out


# ---------------------------------------------------------------------------
# Corpus -> jobs
# ---------------------------------------------------------------------------
def build_jobs(corpora: list[str], configs: str, limit: int | None, stride: int) -> list[dict]:
    jobs: list[dict] = []

    if "golden" in corpora:
        fx = json.loads(GOLDEN.read_text())
        by_seed: dict[int, list[dict]] = {}
        for p in fx["positions"]:
            by_seed.setdefault(int(p["deck_seed"]), []).append(p)
        for seed_s, g in sorted(fx["games"].items(), key=lambda kv: int(kv[0])):
            seed = int(g.get("deck_seed", seed_s))
            acts = [int(a) for a in g["actions"]]
            jobs.append({"fn": "replay", "corpus": "golden", "label": f"golden/{seed}",
                         "deck_seed": seed, "actions": acts, "stride": 1,
                         "configs": configs})
            jobs.append({"fn": "golden_disk", "corpus": "golden_disk",
                         "label": f"goldendisk/{seed}", "deck_seed": seed, "actions": acts,
                         "frozen": by_seed.get(seed, []), "configs": "core"})

    if "midgame" in corpora:
        recs = [json.loads(l) for l in MIDGAME.open() if l.strip()]
        if limit:
            recs = recs[:limit]
        for r in recs:
            pre = [int(a) for a in r["prefix"]]
            jobs.append({"fn": "replay", "corpus": "midgame",
                         "label": f"midgame/{r['position_id']}",
                         "deck_seed": int(r["source_game_seed"]), "actions": pre,
                         "check_plies": {len(pre)}, "configs": configs})

    if "k3" in corpora:
        recs = [json.loads(l) for l in K3.open() if l.strip()]
        if limit:
            recs = recs[:limit]
        for r in recs:
            jobs.append({"fn": "greedy", "corpus": "k3",
                         "label": f"k3/{r['source_agent']}/{r['seed']}@{r['ply']}",
                         "deck_seed": int(r["seed"]), "ply": int(r["ply"]),
                         "configs": configs})

    if "distill" in corpora:
        recs = [json.loads(l) for l in DISTILL.open() if l.strip()]
        if limit:
            recs = recs[:limit]
        for r in recs:
            jobs.append({"fn": "replay", "corpus": "distill",
                         "label": f"distill/{r['game_id']}",
                         "deck_seed": int(r["deck_seed"]),
                         "actions": [int(a) for a in r["actions"]],
                         "stride": stride, "configs": configs})

    if "champ" in corpora:
        recs = [json.loads(l) for l in CHAMP.open() if l.strip()]
        if limit:
            recs = recs[:limit]
        for g in recs:
            jobs.append({"fn": "replay", "corpus": "champ", "label": f"champ/{g['game_id']}",
                         "deck_seed": int(g["deck_seed"]),
                         "actions": [int(a) for a in g["actions"]],
                         "stride": 1, "configs": "core"})

    if "e4" in corpora:
        for path in sorted(E4DIR.glob("*.json")):
            d = json.loads(path.read_text())
            if d.get("schema") != "carcassonne-android-archive/v1":
                raise SystemExit(f"{path}: unexpected schema {d.get('schema')!r}")
            jobs.append({"fn": "replay", "corpus": "e4", "label": f"e4/{path.stem}",
                         "deck_seed": int(d["deck_seed"]),
                         "actions": [int(a) for a in d["actions"]],
                         "stride": 1, "configs": configs})

    if "panel" in corpora:
        jobs.append({"fn": "panel", "corpus": "panel", "label": "panel"})

    return jobs


_DISPATCH = {"replay": _replay_job, "greedy": _greedy_job,
             "golden_disk": _golden_disk_job, "panel": _panel_job}


def run_job(job: dict) -> dict:
    out = _DISPATCH[job["fn"]](job)
    out["corpus"] = job["corpus"]
    return out


# ---------------------------------------------------------------------------
# Throughput
# ---------------------------------------------------------------------------
def bench(n_positions: int, repeats: int) -> dict:
    """us/leaf for the three legs over the SAME positions (both POVs per eval).

    Positions are sampled across the depth of one recorded champion game, so the
    mix of board sizes is realistic rather than all-endgame or all-opening.
    """
    cfg = _cfgs("core")["prod-curve125"]
    rcfg = _to_rs(cfg)
    g = json.loads(next(iter(CHAMP.open())))
    seed, acts = int(g["deck_seed"]), [int(a) for a in g["actions"]]
    step = max(1, len(acts) // n_positions)
    plies = list(range(0, len(acts), step))[:n_positions]

    states, mirrors = [], []
    game, board = replay_actions(seed, acts, 0)
    ms = carc_rs.MirrorState.from_seed(str(seed))
    for i in range(len(acts)):
        if i in set(plies):
            states.append(board.state)
            m = carc_rs.MirrorState.from_seed(str(seed))
            for a in acts[:i]:
                m.advance(int(a))
            mirrors.append(m)
        board, _ = game.get_next_state(board, int(acts[i]))
        ms.advance(int(acts[i]))

    def timeit(fn):
        t0 = time.perf_counter()
        for _ in range(repeats):
            for s in states:
                fn(s)
        return time.perf_counter() - t0

    # ONE leaf computation per (state, pov) on every leg — the float variant, which
    # is what `leaf_quantize: float` makes the champion actually call.  (`_py`/`_cy`
    # above do int AND float, i.e. two leaf computations; using them here would
    # double-charge the Python legs.)
    n_leaf = repeats * len(states) * 2
    t_py = timeit(lambda s: [flat_leaf.flat_virtual_score_v2_float(s, p, cfg)
                             for p in (0, 1)])
    t_cy = timeit(lambda s: [cyleaf.flat_virtual_score_v2_cy_float(s, p, cfg, False)
                             for p in (0, 1)])
    t_rs = 0.0
    for m in mirrors:
        t, _ = m.bench_leaf(rcfg, repeats)
        t_rs += t
    return {
        "positions": len(states), "repeats": repeats, "leaf_evals_per_leg": n_leaf,
        "python_us_per_leaf": 1e6 * t_py / n_leaf,
        "cython_us_per_leaf": 1e6 * t_cy / n_leaf,
        "rust_us_per_leaf": 1e6 * t_rs / n_leaf,
        "rust_vs_python": t_py / t_rs, "rust_vs_cython": t_cy / t_rs,
        "note": "python leg includes the pre-round float call, i.e. 2 leaf "
                "computations per (state,pov); all three legs are charged identically",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", action="append", default=None,
                    choices=CORPORA + ["all"])
    ap.add_argument("--configs", default="all",
                    choices=["core", "all", "farmoff", "phase", "denial"])
    ap.add_argument("--limit", type=int, default=None,
                    help="cap records per corpus (screening only)")
    ap.add_argument("--stride", type=int, default=8,
                    help="ply stride for the distill corpus")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--bench", type=int, default=0, help="bench over N positions")
    ap.add_argument("--bench-repeats", type=int, default=200)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    corpora = args.corpus or ["all"]
    if "all" in corpora:
        corpora = list(CORPORA)

    jobs = build_jobs(corpora, args.configs, args.limit, args.stride)
    t0 = time.perf_counter()
    if args.workers > 1:
        import multiprocessing as mp

        with mp.get_context("spawn").Pool(args.workers) as pool:
            results = pool.map(run_job, jobs, chunksize=1)
    else:
        results = [run_job(j) for j in jobs]
    elapsed = time.perf_counter() - t0

    per_corpus: dict[str, dict] = {}
    for r in results:
        per_corpus.setdefault(r["corpus"], _new_out())
        _merge(per_corpus[r["corpus"]], r)

    mismatches = [m for c in per_corpus.values() for m in c["mismatches"]]
    total_values = sum(c["values"] + c["disk_values"] for c in per_corpus.values())
    ok = not mismatches

    # F7b: per-knockout "does it bite" tally (values that differ from the champion
    # leaf on the same position). Empty unless --configs farmoff.
    knockout_bites: dict[str, dict] = {}
    for c in per_corpus.values():
        for k, seen in c["knockout_seen"].items():
            e = knockout_bites.setdefault(
                k, {"values_compared": 0, "values_changed_vs_champion": 0})
            e["values_compared"] += seen
            e["values_changed_vs_champion"] += c["knockout_bites"].get(k, 0)
    for e in knockout_bites.values():
        e["frac_changed"] = round(e["values_changed_vs_champion"]
                                  / max(1, e["values_compared"]), 4)

    payload = {
        "gate": "G2/leaf",
        "verdict": "PASS" if ok else "FAIL",
        "env": environment(),
        "args": vars(args),
        "leaf_of_record": leaf_provenance(),
        "configs": sorted(_cfgs(args.configs)),
        "legs": ["carcassonne_ai.flat_leaf (USE_CY_LEAF=False)",
                 "carcassonne_ai.flat_leaf_cy (direct)",
                 "carc_rs.MirrorState.leaf_value{,_float}"],
        "checks_per_position": ["flat_base_score x4 routes",
                                "leaf int (py|cy|rust)",
                                "leaf float bit-exact (py|cy|rust)"],
        "per_corpus": {k: {"positions": v["positions"], "plies": v["plies"],
                           "values_compared": v["values"],
                           "disk_values_compared": v["disk_values"],
                           "by_config": v["by_config"],
                           "mismatches": len(v["mismatches"])}
                       for k, v in sorted(per_corpus.items())},
        "cy_unsupported_configs": sorted(CY_UNSUPPORTED & set(_cfgs(args.configs))),
        "knockout_bites": knockout_bites,
        "total_values_compared": total_values,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "wallclock_s": elapsed,
    }
    if args.bench:
        payload["throughput"] = bench(args.bench, args.bench_repeats)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    tag = "_".join(corpora) if len(corpora) < len(CORPORA) else "all"
    if args.configs in ("farmoff", "phase", "denial"):   # never overwrite the standing G2 artifact
        tag = f"{args.configs}_{tag}"
    out = Path(args.out) if args.out else OUTDIR / f"G2_leaf_{tag}.json"
    out.write_text(json.dumps(payload, indent=2, default=str))

    for name, c in payload["per_corpus"].items():
        print(f"G2/leaf[{name}]: {c['positions']} positions, {c['plies']} plies, "
              f"{c['values_compared']} live values, {c['disk_values_compared']} on-disk "
              f"values, {c['mismatches']} mismatches")
    if "throughput" in payload:
        t = payload["throughput"]
        print(f"G2/leaf: throughput — python {t['python_us_per_leaf']:.2f} us/leaf, "
              f"cython {t['cython_us_per_leaf']:.2f}, rust {t['rust_us_per_leaf']:.2f} "
              f"({t['rust_vs_python']:.1f}x py, {t['rust_vs_cython']:.1f}x cy)")
    print(f"G2/leaf: {'PASS' if ok else 'FAIL'}  {total_values} values compared, "
          f"{len(mismatches)} mismatches, {elapsed:.1f}s")
    print(f"G2/leaf: result -> {out}")
    for m in mismatches[:5]:
        print("  MISMATCH", json.dumps(m, default=str)[:600])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
