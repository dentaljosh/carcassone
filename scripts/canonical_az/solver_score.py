#!/usr/bin/env python3
"""Solver-scoring harness — the NON-CIRCULAR ranker scorer (POST_REVIEW_PLAN §4 / M2 Part A).

The h6400_v2.9 oracle correlates 0.995 with the v2.9 leaf (autopsy F4), so every
offline gate scored against it is circular. The exact K<=4 endgame solver
(scripts/level2/endgame_solver.py) uses the REAL final score-diff (flat_base_score)
as its leaf value -> uncorrelated with the v2.9 leaf -> breaks the circularity.

This harness scores ANY per-child ranker's REGRET AGAINST THE SOLVER (not oracle_q):

  1. Reuse the existing h6400_v2.9 sibling sets (the 10,067 roots CL-033/§3A used;
     qprobe_A/probe.jsonl JOIN pool_A.jsonl on (seed,ply), NO new gen). Reconstruct
     each root via replay_to(seed,ply); compute k_remaining post-replay; filter K<=4.
  2. solve() each K<=4 root -> child_values (exact per-child value). Mode per root:
     marginalized (bag-expectation, the PREFERRED ground truth) at K<=2 where it is
     tractable (== clairvoyant there); clairvoyant+alpha-beta at K=3..4 (marginalized
     intractable there). Flagged per root.
  3. Score the ranker's per-child scores vs the solver child_values using
     step1_train.group_metrics (argmax-regret / top-1 / kendall-tau), oriented to the
     MOVER's perspective so argmax == best move (matches endgame_regret._eval_one /
     regret_of). Regret is in RAW POINTS, >= 0.
  4. Report per-root + aggregate solver-regret / top-1 / tau, split by K and by mode.

Default ranker = the static v2.9 leaf itself (the sanity baseline: its solver-regret
is the reference number). `--checkpoint PATH` (repeatable) adds net VALUE-head rankers
(M2 read-out): each root is solved ONCE and every ranker (baseline + all checkpoints)
is scored on the same SolveResult, so the numbers are per-position comparable.

MEASUREMENT ONLY. Pure CPU, no CUDA (net rankers forward on CPU). No champion/
PRODUCTION change.
"""
from __future__ import annotations

import os
# v2.9 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG reads these
# at import). EXACTLY matches dump_dataset.py (the dump that produced the h6400_v2.9
# sibling labels), so the v2.9-leaf ranker here is bit-identical to that leaf_q.
os.environ.setdefault("CARCASSONNE_V25_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_OPP_CAP", "8")
os.environ.setdefault("CARCASSONNE_V25_DROP_THREE_OPEN", "0")
os.environ.setdefault("CARCASSONNE_V29_MEEPLE_CURVE", "-8,-4,-1,0,2,3,4,5")
os.environ.setdefault("CARCASSONNE_V25_MEEPLE_K", "2.0")
os.environ.setdefault("CARCASSONNE_USE_FLAT_LEAF", "1")
os.environ.setdefault("CARCASSONNE_USE_CY_REPR", "1")
os.environ.setdefault("CARCASSONNE_V25_VALUE_BLEND", "0")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import argparse
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "feature_planes_gate"))

import endgame_solver as S                                # noqa: E402
from gen_endgame_positions import replay_to, k_remaining  # noqa: E402
from step1_train import group_metrics                     # noqa: E402 (argmax-regret/top1/tau core)
from carcassonne_ai.virtual_score_v2 import virtual_score_v2  # noqa: E402
import eval_hybrid_handoff as EH                           # noqa: E402 (_heur_leaf_cfg)

HG = REPO / "measurement" / "high_gap_distillation" / "scaled"
DEFAULT_QPROBE = str(HG / "qprobe_A" / "probe.jsonl")
DEFAULT_POOL = str(HG / "pool_A.jsonl")

# Mode policy by root K (M2_PLAN Part A): marginalized is the preferred ground truth
# but tractable only at K<=2 (== clairvoyant there); K>=3 marginalized is intractable
# -> clairvoyant+alpha-beta labels.
#
# NOTE on the qprobe_A reuse set: its 10,067 roots are sampled at DISCRETE k_remaining
# strata {2,4,6,10,14,22,32,44,56} (per-root k_remaining field; verified post-replay).
# So there are NO K=3 (or any odd-K) roots here: K<=2 = 1,119 roots (all K=2, all
# MARGINALIZED); K<=4 = 2,238 (adds 1,119 K=4 roots, all CLAIRVOYANT+AB). K=4 solves are
# the expensive tail (~21min median per M2_PLAN) -> the full K<=4 read-out is gated/cluster,
# NOT this smoke. (The M2_PLAN's "24.2%/15.0%" figures are a DIFFERENT 120-root fresh-greedy
# replay at all K=2..6; the actual qprobe_A reuse is 22.2%/11.1%.)
MARG_MAX_K = 2


# --------------------------------------------------------------------------- #
# Rankers: callable(child_board, root_player, game) -> float (higher = better  #
# for root_player, i.e. the mover). group_metrics's argmax then = the pick.    #
# --------------------------------------------------------------------------- #
def make_v29_leaf_ranker():
    """The static v2.9 leaf itself (the sanity baseline). Bit-identical to
    dump_dataset.py's leaf_q: tanh(virtual_score_v2(child, root_player, cfg)/15),
    terminal children clamped to [-1,1]."""
    cfg = EH._heur_leaf_cfg(2.0)

    def rank(child, root_player, game):
        ended = game.get_game_ended(child, root_player)
        if ended != 0:
            return max(-1.0, min(1.0, float(ended)))
        return math.tanh(virtual_score_v2(child.state, root_player, cfg) / 15.0)

    return rank


def make_net_ranker(ckpt_path: str):
    """A net checkpoint's VALUE head as a ranker (the M2 non-circular read-out).

    Arch is peeked from the checkpoint exactly like eval_m2_net_vs_net._peek /
    verify_sighted_orch_parity._load_net (n_scalar / in-channels / sighted /
    value_global_pool), the encode Game matches the net's rep (sighted 81ch or
    blind, farm scalars iff n_scalar>10 and not sighted), and the forward runs
    on CPU (CUDA is masked at the top of this file).

    POV (verdict-critical): the ranker contract is MOVER (root_player)
    perspective — same orientation as the v29_leaf ranker's
    virtual_score_v2(child, root_player) and the solver_mover flip in
    score_root. make_single_evaluator returns the value from the CHILD's
    current_player POV. VERIFIED empirically on the qprobe_A roots: they are
    TILES-phase, so a child is a MEEPLES-phase state with the SAME
    current_player (the mover still to move) -> NO flip there; only flip when
    the child's current_player is the opponent (turn-completing children).
    Terminal children short-circuit to get_game_ended(child, root_player),
    exactly like the v29_leaf ranker. Ranking metrics are invariant to
    monotone transforms, so only this orientation matters, not scaling."""
    import torch
    from carcassonne_ai.evaluators import make_single_evaluator
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.network import CarcassonneNet

    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78) or 78)
    n_scalar = int(ck.get("n_scalar_features", 10))
    sighted = bool(ck.get("sighted", False))
    net = CarcassonneNet(
        n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
        n_input_channels=n_ch, n_scalar_features=n_scalar,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    )
    net.load_state_dict(ck["model_state"])
    net.train(False)
    # the encode Game must match the NET's rep, independent of the (blind)
    # replay game — Game is a stateless view over board.state, so encoding a
    # replayed child through this one is safe.
    enc_game = Game(sighted=sighted,
                    include_farm_scalars=(n_scalar > 10) and not sighted)
    ev = make_single_evaluator(net, torch.device("cpu"), enc_game)

    def rank(child, root_player, game):
        ended = game.get_game_ended(child, root_player)
        if ended != 0:
            return max(-1.0, min(1.0, float(ended)))
        _, v_nn = ev(child)
        # v_nn is from the CHILD's current_player POV -> orient to the mover.
        return float(v_nn) if child.state.current_player == root_player else -float(v_nn)

    return rank


def make_g2_ranker(ckpt_path: str):
    """A paper-G2 architecture-control checkpoint's VALUE head as a ranker.

    G2 (measurement/paper_g2_20260803/PREREG.md) trains transformer-trunk and
    from-scratch-ResNet arms whose HEADS are identical code to CarcassonneNet's,
    so the ranker body below is a CHARACTER-FOR-CHARACTER copy of
    make_net_ranker's: same terminal short-circuit to get_game_ended, same
    make_single_evaluator, same mover-POV orientation flip on the child's
    current_player. Only the constructor differs (it dispatches on the
    checkpoint's `g2_arch.arch`). The instrument's arithmetic is untouched;
    the v29_leaf/curve125 arms in the same pass are the integrity proof.
    """
    import torch
    from carcassonne_ai.evaluators import make_single_evaluator
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.network import CarcassonneNet
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper_g2"))
    from g2_transformer import CarcassonneTransformer

    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    arch = ck.get("g2_arch")
    if arch is None:
        raise ValueError(f"{ckpt_path}: not a G2 checkpoint (no g2_arch)")
    n_ch = int(ck.get("n_input_channels", 81))
    n_scalar = int(ck.get("n_scalar_features", 42))
    sighted = bool(ck.get("sighted", True))
    if arch.get("arch") == "transformer":
        net = CarcassonneTransformer(
            window_size=int(arch.get("window_size", 25)),
            n_input_channels=n_ch, n_scalar_features=n_scalar,
            action_size=int(arch.get("action_size", 2511)),
            d_model=int(arch["d_model"]), depth=int(arch["depth"]),
            n_heads=int(arch["n_heads"]), ff_mult=int(arch["ff_mult"]),
            value_global_pool=bool(arch.get("value_global_pool", True)),
        )
    elif arch.get("arch") == "resnet":
        net = CarcassonneNet(
            n_filters=int(arch["n_filters"]), n_blocks=int(arch["n_blocks"]),
            n_input_channels=n_ch, n_scalar_features=n_scalar,
            value_global_pool=bool(arch.get("value_global_pool", True)),
        )
    else:
        raise ValueError(f"{ckpt_path}: unknown g2_arch {arch!r}")
    net.load_state_dict(ck["model_state"])
    net.train(False)
    enc_game = Game(sighted=sighted,
                    include_farm_scalars=(n_scalar > 10) and not sighted)
    ev = make_single_evaluator(net, torch.device("cpu"), enc_game)

    def rank(child, root_player, game):
        ended = game.get_game_ended(child, root_player)
        if ended != 0:
            return max(-1.0, min(1.0, float(ended)))
        _, v_nn = ev(child)
        return float(v_nn) if child.state.current_player == root_player else -float(v_nn)

    return rank


def make_tempo_arm_ranker(ckpt_path: str):
    """A §5A tempo-arm RankNet (step1_train.py --save-model dict) as a ranker —
    the CL-040 fold-in re-adjudication read-out. Returns (label, rank_fn).

    Input build mirrors the CL-037/§5A training rows exactly (step1_dump.py
    _process + emit_tempo.py): blind get_canonical_form(child, root_player)
    (78ch + 12 scalars), + step1_planes.farm_connectivity_planes -> 81ch,
    + bag_histogram -> 44 scalars, + the _tempo_features columns the arm was
    trained with (selected by the saved tempo_names — 14 full or the 10-core
    gate-zero survivors). The arm's drop-flags are applied by ZEROING the
    corresponding blocks, matching step1_train's --drop-farm/--drop-bag/
    --drop-tempo gather-time ablation (the net always sees the full-width
    81ch/n_scalar layout). Features round-trip through float16 to match the
    dataset dtype path (child_obs.f16 / f16 scalars -> float32 at gather).

    POV (verdict-critical): NO flip. The RankNet target was oracle_q in
    absolute mode (step1_train.train_one: tgt = oq for V4_listwise), and
    oracle_q is the h6400 teacher's adjusted-Q in ROOT-PLAYER perspective
    (probe_signal_density.py), with the encode canonicalized to root_player
    — so the net output is already mover-oriented for the roots scored here
    (root_player == the mover). Terminal children short-circuit to
    get_game_ended(child, root_player), exactly like the other rankers.
    Ranking metrics are invariant to monotone transforms, so only this
    orientation matters, not scaling."""
    import torch
    sys.path.insert(0, str(REPO / "scripts"))               # value_ranking_train
    sys.path.insert(0, str(REPO / "scripts" / "probe_5a"))  # emit_tempo
    from value_ranking_train import RankNet
    from emit_tempo import _tempo_features, TEMPO_NAMES
    from step1_planes import (farm_connectivity_planes, bag_histogram,
                              N_FARM_PLANES, N_BAG)
    from carcassonne_ai.game_wrapper import Game

    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    arch = ck["arch"]
    net = RankNet(arch["ranknet_arm"], int(arch["c_in"]), int(arch["w"]),
                  int(arch["n_scalar"]), int(arch["trunk_filters"]),
                  int(arch["trunk_blocks"]))
    net.load_state_dict(ck["model_state"])
    net.train(False)

    drops = ck.get("drop_flags", {})
    drop_farm = bool(drops.get("drop_farm", False))
    drop_bag = bool(drops.get("drop_bag", False))
    drop_tempo = bool(drops.get("drop_tempo", False))
    tempo_names = [str(x) for x in ck.get("tempo_names", [])]
    tempo_idx = [TEMPO_NAMES.index(nm) for nm in tempo_names]
    nt = int(ck.get("tempo_cols", len(tempo_idx)))
    if nt != len(tempo_idx):
        raise ValueError(f"{ckpt_path}: tempo_cols={nt} != len(tempo_names)={len(tempo_idx)}")
    n_farm = int(ck.get("n_farm_planes", N_FARM_PLANES))
    n_bag = int(ck.get("n_bag_scalars", N_BAG))
    c_in, n_scalar = int(arch["c_in"]), int(arch["n_scalar"])
    label = f"arm_{ck.get('arm', Path(ckpt_path).stem)}_s{ck.get('seed', '?')}"
    # blind encode Game — same construction as step1_dump._worker_init
    enc_game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)

    def rank(child, root_player, game):
        ended = game.get_game_ended(child, root_player)
        if ended != 0:
            return max(-1.0, min(1.0, float(ended)))
        obs, sca = enc_game.get_canonical_form(child, root_player)   # (78,W,W), (12,)
        obs = obs.astype(np.float16)
        sca = np.asarray(sca, dtype=np.float16)
        off = child.offset; W = off.size
        if n_farm:
            if drop_farm:
                fp = np.zeros((n_farm, W, W), dtype=np.float16)
            else:
                fp = farm_connectivity_planes(child.state, root_player, off, W).astype(np.float16)
            obs = np.concatenate([obs, fp], axis=0)
        if n_bag:
            if drop_bag:
                bag = np.zeros(n_bag, dtype=np.float16)
            else:
                bag = bag_histogram(child.state).astype(np.float16)
            sca = np.concatenate([sca, bag], axis=0)
        if nt:
            if drop_tempo:
                tv = np.zeros(nt, dtype=np.float16)
            else:
                tempo, _ = _tempo_features(child.state, root_player)
                tv = np.asarray(tempo, dtype=np.float32)[tempo_idx].astype(np.float16)
            sca = np.concatenate([sca, tv], axis=0)
        if obs.shape[0] != c_in or sca.shape[0] != n_scalar:
            raise ValueError(f"arm input mismatch: obs C={obs.shape[0]} (want {c_in}), "
                             f"sca={sca.shape[0]} (want {n_scalar})")
        with torch.no_grad():
            o = torch.from_numpy(obs.astype(np.float32)[None])
            s = torch.from_numpy(sca.astype(np.float32)[None])
            return float(net(o, s).item())

    return label, rank


RANKERS = {"v29_leaf": make_v29_leaf_ranker}


# --------------------------------------------------------------------------- #
# Leaf-variant rankers (v2.10 leaf arc, docs/V210_LEAF_SPEC_2026-07-04.md).    #
# Each --leaf-variant NAME:JSON becomes a ranker identical in shape to        #
# v29_leaf but evaluated under its OWN explicit LeafConfig. NO env mutation:  #
# virtual_score_v2 / flat_virtual_score_v2 / the cy leaf all read the cfg     #
# object PER CALL, so per-variant configs cannot cross-contaminate (the env   #
# only feeds DEFAULT_CONFIG once at import, which we never touch).            #
# --------------------------------------------------------------------------- #
# JSON keys = env-knob names sans the CARCASSONNE_ prefix (values str or num).
LEAF_VARIANT_KNOBS = (
    "V25_CAP", "V25_OPP_CAP", "V25_MEEPLE_K",
    "V25_DROP_THREE_OPEN", "V25_ONE_OPEN_ONLY",
    "V29_MEEPLE_CURVE", "V210_BAG_CLOSE",
    # F6 soft cap (CL-063): linear credit above the cap instead of a hard clamp.
    "SOFT_CAP_SLOPE", "OPP_SOFT_CAP_SLOPE",
)


def leaf_cfg_from_overrides(overrides: dict):
    """Baseline cfg (EH._heur_leaf_cfg(2.0) == the v29_leaf ranker's cfg) with the
    JSON knob overrides applied. Returns (LeafConfig, bag_close: bool | None).

    Semantics mirror virtual_score_v2._config_from_env exactly:
      V25_CAP            -> bonus_cap (and opp_bonus_cap follows unless V25_OPP_CAP
                            is ALSO overridden — the env default OPP_CAP=CAP)
      V25_OPP_CAP        -> opp_bonus_cap
      V25_MEEPLE_K       -> meeple_k  (⚠️ INERT while a v29 curve is set — the curve
                            REPLACES the flat term; pass V29_MEEPLE_CURVE:"" to use it)
      V25_ONE_OPEN_ONLY / V25_DROP_THREE_OPEN -> closure_p schedule (precedence as
                            in _config_from_env; always a FRESH dict, never shared)
      V29_MEEPLE_CURVE   -> v29_meeple_curve ("a,b,..." or list; ""/null -> None)
      V210_BAG_CLOSE     -> NOT a LeafConfig field (the frozen v2.9 config-hash
                            guards pin the dataclass schema); returned separately and
                            routed via flat_leaf.flat_virtual_score_v2(bag_close=...).
    """
    unknown = set(overrides) - set(LEAF_VARIANT_KNOBS)
    if unknown:
        raise ValueError(f"unknown leaf-variant knobs {sorted(unknown)}; "
                         f"supported: {LEAF_VARIANT_KNOBS}")
    import dataclasses
    kw = {}
    if "V25_CAP" in overrides:
        cap = float(overrides["V25_CAP"])
        kw["bonus_cap"] = cap
        if "V25_OPP_CAP" not in overrides:
            kw["opp_bonus_cap"] = cap
    if "V25_OPP_CAP" in overrides:
        kw["opp_bonus_cap"] = float(overrides["V25_OPP_CAP"])
    if "V25_MEEPLE_K" in overrides:
        kw["meeple_k"] = float(overrides["V25_MEEPLE_K"])
    if "V25_ONE_OPEN_ONLY" in overrides or "V25_DROP_THREE_OPEN" in overrides:
        ooo = str(overrides.get(
            "V25_ONE_OPEN_ONLY", os.environ.get("CARCASSONNE_V25_ONE_OPEN_ONLY", "0"))) == "1"
        d3o = str(overrides.get(
            "V25_DROP_THREE_OPEN", os.environ.get("CARCASSONNE_V25_DROP_THREE_OPEN", "0"))) == "1"
        if ooo:
            kw["closure_p"] = {1: 1.0}
        elif d3o:
            kw["closure_p"] = {1: 0.5, 2: 0.2}
        else:
            kw["closure_p"] = {1: 0.5, 2: 0.2, 3: 0.05}
    if "V29_MEEPLE_CURVE" in overrides:
        cv = overrides["V29_MEEPLE_CURVE"]
        if cv is None or cv == "":
            kw["v29_meeple_curve"] = None
        elif isinstance(cv, str):
            kw["v29_meeple_curve"] = tuple(float(x) for x in cv.split(","))
        else:  # list/tuple of numbers
            kw["v29_meeple_curve"] = tuple(float(x) for x in cv)
    # F6 soft cap (CL-063): real LeafConfig fields (unlike V210_BAG_CLOSE); default 0.0
    # == hard clamp == bit-identical champion. Excluded from the frozen/harness hashes
    # while 0.0, so a slope=0.0 variant is byte-identical to the baseline ranker.
    if "SOFT_CAP_SLOPE" in overrides:
        kw["soft_cap_slope"] = float(overrides["SOFT_CAP_SLOPE"])
    if "OPP_SOFT_CAP_SLOPE" in overrides:
        kw["opp_soft_cap_slope"] = float(overrides["OPP_SOFT_CAP_SLOPE"])
    bag_close = None
    if "V210_BAG_CLOSE" in overrides:
        bag_close = str(overrides["V210_BAG_CLOSE"]) in ("1", "true", "True")
    cfg = dataclasses.replace(EH._heur_leaf_cfg(2.0), **kw)
    return cfg, bag_close


def make_variant_leaf_ranker(cfg, bag_close=None):
    """A v29_leaf-shaped ranker under an explicit per-variant LeafConfig.
    Same terminal clamp + tanh(vs2/15) as make_v29_leaf_ranker — with an
    all-default overrides dict this is bit-identical to the baseline ranker.

    bag_close (v2.10 Track B) routes through the flat leaf's explicit
    `bag_close` parameter — again no global/env mutation. Requires the
    bag-close-capable flat_leaf build."""
    from carcassonne_ai import flat_leaf

    if bag_close is None:
        def rank(child, root_player, game):
            ended = game.get_game_ended(child, root_player)
            if ended != 0:
                return max(-1.0, min(1.0, float(ended)))
            return math.tanh(virtual_score_v2(child.state, root_player, cfg) / 15.0)
        return rank

    import inspect
    if "bag_close" not in inspect.signature(flat_leaf.flat_virtual_score_v2).parameters:
        raise RuntimeError(
            "V210_BAG_CLOSE variant needs the v2.10 bag-close flat leaf "
            "(flat_leaf.flat_virtual_score_v2 has no bag_close param in this tree)")
    if not flat_leaf.USE_FLAT_LEAF:
        raise RuntimeError("V210_BAG_CLOSE variant requires CARCASSONNE_USE_FLAT_LEAF=1")

    def rank(child, root_player, game):
        ended = game.get_game_ended(child, root_player)
        if ended != 0:
            return max(-1.0, min(1.0, float(ended)))
        # Direct flat call == virtual_score_v2's redirect for these (curve-only /
        # plain) cfgs under USE_FLAT_LEAF=1, plus the explicit bag_close flag.
        return math.tanh(
            flat_leaf.flat_virtual_score_v2(child.state, root_player, cfg,
                                            bag_close=bag_close) / 15.0)
    return rank


def parse_leaf_variant_arg(spec: str):
    """'NAME:{json}' -> (name, overrides dict). NAME must precede the first ':'."""
    name, sep, payload = spec.partition(":")
    if not sep or not name:
        raise ValueError(f"--leaf-variant expects NAME:JSON, got {spec!r}")
    overrides = json.loads(payload)
    if not isinstance(overrides, dict):
        raise ValueError(f"--leaf-variant {name}: JSON must be an object, got {type(overrides)}")
    return name, overrides


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
def load_sibling_roots(qprobe: str, pool: str):
    """The h6400_v2.9 sibling sets: qprobe_A (has action_q / k_remaining / phase)
    JOINed with pool_A (has checksum) on (seed, ply). Mirrors dump_dataset.py."""
    checks = {}
    for line in open(pool):
        r = json.loads(line)
        checks[(r["seed"], r["ply"])] = r["checksum"]
    recs = []
    for line in open(qprobe):
        r = json.loads(line)
        key = (r["seed"], r["ply"])
        if key in checks:
            r["checksum"] = checks[key]
            recs.append(r)
    return recs


def score_root(rec, rankers, budget, max_k):
    """Reconstruct one root, solve it ONCE, score EVERY ranker's per-child regret
    vs the same SolveResult. Returns a per-root dict (or {'_error': ...} /
    {'_skip': ...}) with a per-ranker metrics sub-dict."""
    seed, ply = int(rec["seed"]), int(rec["ply"])
    try:
        game, board = replay_to(seed, ply)
    except Exception as e:  # noqa
        return {"_error": f"{seed}:{ply} recon {type(e).__name__}: {e}"}
    if game.string_representation(board) != rec["checksum"]:
        return {"_error": f"{seed}:{ply} checksum_mismatch"}

    k = k_remaining(board)                     # k computed POST-replay (authoritative)
    if k > max_k:
        return {"_skip": "k>max_k", "k": k}

    # mode policy: marginalized at K<=2 (preferred, == clairvoyant), else clairvoyant+AB
    if k <= MARG_MAX_K:
        mode, ab = "marginalized", False
    else:
        mode, ab = "clairvoyant", True

    root_player = board.state.current_player
    legal = np.flatnonzero(game.get_valid_moves(board)).astype(int)
    if legal.size < 2:
        return {"_skip": "<2 legal", "k": k}

    t0 = time.perf_counter()
    try:
        res = S.solve(game, board, mode=mode, budget=budget, alphabeta=ab)
    except S.BudgetExceeded:
        return {"_skip": "budget", "k": k, "mode": mode,
                "secs": round(time.perf_counter() - t0, 2)}
    solve_secs = time.perf_counter() - t0
    cv = res.child_values                      # {action: P0-perspective value}
    tm = res.to_move

    # Orient BOTH ranker score and solver value to the mover's perspective so that
    # group_metrics' argmax(target)=best and argmax(score)=pick are consistent, and
    # its regret == points lost vs optimal (== endgame_regret / regret_of). Solver
    # child_values are P0-perspective -> flip sign when the mover is P1.
    actions = list(cv.keys())
    solver_mover = np.array([(cv[a] if tm == 0 else -cv[a]) for a in actions], dtype=np.float64)
    # children built ONCE, scored by every ranker (solve-once-score-many).
    children = [game.get_next_state(board, int(a))[0] for a in actions]

    per_ranker = {}
    for name, ranker in rankers.items():
        score = np.array([float(ranker(child, root_player, game)) for child in children],
                         dtype=np.float64)
        regret, top1, tau = group_metrics(score, solver_mover)
        per_ranker[name] = {
            "solver_regret": round(float(regret), 4),
            "top1": int(top1), "tau": float(tau),
            "pick": int(actions[int(np.argmax(score))]),  # same argmax as group_metrics
        }

    # position-difficulty context (mover-perspective spectrum), mirrors _eval_one
    sm_sorted = np.sort(solver_mover)[::-1]
    gap = float(sm_sorted[0] - sm_sorted[1]) if len(sm_sorted) >= 2 else None
    return {
        "seed": seed, "ply": ply, "phase": rec.get("phase", "?"),
        "k": k, "mode": mode, "n_legal": len(actions), "to_move": tm,
        "nodes": res.nodes, "solve_secs": round(solve_secs, 2),
        "rankers": per_ranker,
        "best_vs_second_gap": round(gap, 4) if gap is not None else None,
        "value_spread": round(float(solver_mover.max() - solver_mover.min()), 4),
    }


def _ranker_rows(scored, name):
    """Flatten one ranker's metrics (+ the shared solve stats) for _agg."""
    return [{**r["rankers"][name], "solve_secs": r["solve_secs"]} for r in scored]


# fork-inherited worker context. A main()-local closure can't be pickled through
# Pool.imap_unordered's task queue (the pre-fix --workers>1 path crashed on
# exactly that); a module-level fn + fork-inherited globals is the standard
# pattern here (cf. eval_m2_net_vs_net._W).
_POOL_CTX: dict = {}


def _pool_worker(rec):
    return score_root(rec, _POOL_CTX["rankers"], _POOL_CTX["budget"], _POOL_CTX["max_k"])


def _agg(rows):
    if not rows:
        return None
    reg = np.array([r["solver_regret"] for r in rows], dtype=np.float64)
    t1 = np.array([r["top1"] for r in rows], dtype=np.float64)
    tau = np.array([r["tau"] for r in rows], dtype=np.float64)
    secs = np.array([r["solve_secs"] for r in rows], dtype=np.float64)
    return {
        "n": len(rows),
        "solver_regret_mean": round(float(reg.mean()), 4),
        "solver_regret_median": round(float(np.median(reg)), 4),
        "solver_regret_max": round(float(reg.max()), 4),
        "top1_rate": round(float(t1.mean()), 4),
        "tau_mean": round(float(np.nanmean(tau)), 4),
        "solve_secs_mean": round(float(secs.mean()), 2),
        "solve_secs_total": round(float(secs.sum()), 1),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qprobe", default=DEFAULT_QPROBE,
                    help="sibling-set source with action_q/k_remaining (qprobe_A/probe.jsonl)")
    ap.add_argument("--pool", default=DEFAULT_POOL,
                    help="sibling-set source with checksum (pool_A.jsonl)")
    ap.add_argument("--max-k", type=int, default=4, help="K filter (root k_remaining <= this)")
    ap.add_argument("--ranker", default="v29_leaf", choices=list(RANKERS),
                    help="baseline per-child ranker (default: the static v2.9 leaf)")
    ap.add_argument("--checkpoint", action="append", default=[], metavar="PATH",
                    help="net checkpoint to score as an ADDITIONAL ranker (repeatable; "
                         "M2 read-out). Named after the file stem (e.g. iter_00). Every "
                         "ranker is scored on the same SolveResult per root.")
    ap.add_argument("--arm-ckpt", action="append", default=[], metavar="PATH",
                    help="§5A tempo-arm RankNet saved by step1_train.py --save-model "
                         "(repeatable; the CL-040 fold-in re-adjudication). Scored as an "
                         "ADDITIONAL ranker on the same SolveResult per root — the "
                         "v29_leaf baseline is untouched.")
    ap.add_argument("--leaf-variant", action="append", default=[], metavar="NAME:JSON",
                    help="leaf-config variant ranker (repeatable; v2.10 leaf arc). JSON "
                         "holds env-knob overrides sans the CARCASSONNE_ prefix, e.g. "
                         '\'cap12:{"V25_CAP":"12"}\'. Each variant is a v29_leaf-shaped '
                         "ranker under its OWN explicit LeafConfig (no env mutation, no "
                         "cross-contamination); the baseline ranker is untouched.")
    ap.add_argument("--g2-checkpoint", action="append", default=[], metavar="NAME:PATH",
                    help="paper-G2 architecture-control checkpoint (repeatable; "
                         "measurement/paper_g2_20260803/PREREG.md). Dispatches on the "
                         "checkpoint's g2_arch (transformer or resnet) and scores its VALUE "
                         "head with the SAME ranker body as --checkpoint. NAME labels the arm.")
    ap.add_argument("--n", type=int, default=0,
                    help="cap #K<=max_k roots to SCORE (0=all). Roots are pre-filtered by the "
                         "records' k_remaining then verified post-replay; --n counts SOLVED roots.")
    ap.add_argument("--budget", type=int, default=5_000_000, help="solver node budget/root")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel solve workers (fork). Keep low alongside running evals.")
    ap.add_argument("--out", default="", help="optional: write full JSON report here")
    ap.add_argument("--seed-shuffle", type=int, default=0,
                    help="shuffle roots with this seed before the --n cap (for a random subset)")
    args = ap.parse_args(argv)

    rankers = {args.ranker: RANKERS[args.ranker]()}
    for ck in args.checkpoint:
        name = Path(ck).stem
        if name in rankers:  # e.g. two iter_00.pt from different runs
            name = f"{Path(ck).resolve().parent.parent.name}_{name}"
        rankers[name] = make_net_ranker(ck)
        print(f"[ranker] {name} <- {ck} (net value head, CPU)", flush=True)
    for spec in args.g2_checkpoint:
        name, sep, path = spec.partition(":")
        if not sep:
            name, path = f"g2_{Path(spec).stem}", spec
        if name in rankers:
            raise SystemExit(f"--g2-checkpoint: duplicate ranker name {name!r}")
        rankers[name] = make_g2_ranker(path)
        print(f"[ranker] {name} <- {path} (G2 arch-control value head, CPU)", flush=True)
    for ck in args.arm_ckpt:
        label, rank = make_tempo_arm_ranker(ck)
        if label in rankers:  # e.g. same arm+seed retrained into two dirs
            label = f"{label}_{Path(ck).resolve().parent.parent.name}"
        rankers[label] = rank
        print(f"[ranker] {label} <- {ck} (§5A tempo-arm RankNet, CPU)", flush=True)
    leaf_variants = {}
    for spec in args.leaf_variant:
        vname, overrides = parse_leaf_variant_arg(spec)
        if vname in rankers:
            raise ValueError(f"--leaf-variant name {vname!r} collides with an existing ranker")
        vcfg, bag_close = leaf_cfg_from_overrides(overrides)
        rankers[vname] = make_variant_leaf_ranker(vcfg, bag_close)
        leaf_variants[vname] = {
            "overrides": overrides, "bag_close": bag_close,
            "resolved": {"closure_p": {str(k): v for k, v in vcfg.closure_p.items()},
                         "bonus_cap": vcfg.bonus_cap, "opp_bonus_cap": vcfg.opp_bonus_cap,
                         "meeple_k": vcfg.meeple_k,
                         "v29_meeple_curve": (list(vcfg.v29_meeple_curve)
                                              if vcfg.v29_meeple_curve else None)},
        }
        print(f"[ranker] {vname} <- leaf variant {overrides} (explicit LeafConfig"
              f"{', bag_close=' + str(bag_close) if bag_close is not None else ''})", flush=True)
    recs = load_sibling_roots(args.qprobe, args.pool)
    print(f"[load] {len(recs)} sibling roots (qprobe ∩ pool)", flush=True)

    # cheap pre-filter on the record's k_remaining (verified post-replay in score_root).
    cand = [r for r in recs if int(r.get("k_remaining", 99)) <= args.max_k]
    if args.seed_shuffle:
        import random
        random.Random(args.seed_shuffle).shuffle(cand)
    else:
        cand.sort(key=lambda r: (int(r.get("k_remaining", 99)), int(r["seed"]), int(r["ply"])))
    kdist = Counter(int(r.get("k_remaining", 99)) for r in cand)
    print(f"[filter] {len(cand)} roots with record k_remaining<={args.max_k} "
          f"({100*len(cand)/max(len(recs),1):.1f}%); K-dist={dict(sorted(kdist.items()))}", flush=True)

    _POOL_CTX.update(rankers=rankers, budget=args.budget, max_k=args.max_k)
    scored, errs, skips = [], [], []
    t0 = time.perf_counter()

    def _handle(out):
        if out is None:
            return
        if "_error" in out:
            errs.append(out)
        elif "_skip" in out:
            skips.append(out)
        else:
            scored.append(out)

    # single-process by default (cheap, safe alongside the running evals); optional pool.
    if args.workers <= 1:
        for rec in cand:
            _handle(_pool_worker(rec))
            if args.n and len(scored) >= args.n:
                break
            if len(scored) and len(scored) % 10 == 0 and (len(scored) + len(skips) + len(errs)) % 10 == 0:
                el = time.perf_counter() - t0
                print(f"  scored={len(scored)} skip={len(skips)} err={len(errs)} "
                      f"({el/max(len(scored),1):.1f}s/scored)", flush=True)
    else:
        from multiprocessing import get_context
        ctx = get_context("fork")
        # when capping with --n we can't stop a pool mid-stream cleanly; just submit the
        # (already small) candidate list and cut after. For the full run this is a no-op.
        sub = cand[: args.n * 3] if args.n else cand   # 3x headroom for skips
        with ctx.Pool(args.workers) as pool:
            for out in pool.imap_unordered(_pool_worker, sub, chunksize=1):
                _handle(out)
                if args.n and len(scored) >= args.n:
                    break

    dt = time.perf_counter() - t0
    print(f"[done] scored={len(scored)} skipped={len(skips)} errors={len(errs)} in {dt:.1f}s", flush=True)
    if errs[:3]:
        print("  sample errors:", [e["_error"] for e in errs[:3]], flush=True)
    if skips:
        print("  skip reasons:", dict(Counter(s["_skip"] for s in skips)), flush=True)

    ks = sorted({r["k"] for r in scored})
    modes = sorted({r["mode"] for r in scored})
    # one entry PER RANKER (all scored on the same solved roots)
    aggregate = {n: _agg(_ranker_rows(scored, n)) for n in rankers}
    by_k = {n: {k: _agg(_ranker_rows([r for r in scored if r["k"] == k], n)) for k in ks}
            for n in rankers}
    by_mode = {n: {m: _agg(_ranker_rows([r for r in scored if r["mode"] == m], n)) for m in modes}
               for n in rankers}
    report = {
        "ranker_baseline": args.ranker, "rankers": list(rankers),
        "checkpoints": [{"path": c, "sha256": _sha256(c)} for c in args.checkpoint]
        + [{"name": s.partition(":")[0], "path": s.partition(":")[2] or s,
            "sha256": _sha256(s.partition(":")[2] or s)} for s in args.g2_checkpoint],
        "arm_ckpts": [{"path": c, "sha256": _sha256(c)} for c in args.arm_ckpt],
        "leaf_variants": leaf_variants,
        "max_k": args.max_k, "budget": args.budget,
        "qprobe": args.qprobe, "pool": args.pool,
        "n_roots_total": len(recs), "n_candidates": len(cand),
        "n_scored": len(scored), "n_skipped": len(skips), "n_errors": len(errs),
        "aggregate": aggregate, "by_k": by_k, "by_mode": by_mode,
        "per_root": scored,
    }
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"[out] wrote {args.out}", flush=True)

    for name in rankers:
        print(f"\n==== SOLVER-SCORE ({name}) ====")
        a = aggregate[name]
        if a:
            print(f"AGG  n={a['n']}  solver_regret mean={a['solver_regret_mean']} "
                  f"median={a['solver_regret_median']} max={a['solver_regret_max']}  "
                  f"top1={a['top1_rate']}  tau={a['tau_mean']}")
        for k, ag in by_k[name].items():
            if ag:
                print(f"  K={k} ({'marg' if k <= MARG_MAX_K else 'clair'})  n={ag['n']}  "
                      f"regret={ag['solver_regret_mean']}  top1={ag['top1_rate']}  "
                      f"tau={ag['tau_mean']}  {ag['solve_secs_mean']}s/solve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
