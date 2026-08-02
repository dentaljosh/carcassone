#!/usr/bin/env python3
"""Phase 1.1 deck-paired A/B: PUCT-with-heuristic-priors (candidate) vs the
production champion (HeuristicMCTS @ h6400 + exact-K endgame), search-only.

Pre-registration: measurement/classical_search/PLAN.md (H1.1).

Both sides are CLAIRVOYANT (descend the true deck) — this is an internal
algorithm A/B, matched-mode per the plan. Deck-paired: the same shuffled deck is
played from both seats (seats swapped), so the paired-margin z removes deck
variance. BOTH sides get the IDENTICAL exact-K<=4 clairvoyant endgame handoff
(latched on the first TILES decision with k_remaining<=K), so the ONLY difference
measured is the SEARCH prefix: PUCT+heuristic-priors (candidate) vs
random-expansion UCT h6400 (champion). The exact tail is leaf-independent (true
terminal score), so it cannot bias the comparison.

Candidate = HeuristicPriorAgent(c_puct, tau_p, leaf_quantize, final_select) @ cand_sims.
Champion  = HeuristicMCTS(heur_leaf="v2_7", c=3.0) @ champ_sims (default 6400),
            leaf = env-built v2.9 Bmild_cap8 (DEFAULT_CONFIG).

Pure CPU, net-free (no GPU/orchestrator) -> keep --workers <= threads, nice -n 19.

Usage:
  # plumbing + handoff smoke (single process, fast):
  nice -n 19 .venv/bin/python scripts/classical_search/eval_puct_priors.py \
      --c-puct 1.5 --tau-p 5 --cand-sims 800 --exact-k 2 --games 4 --smoke

  # one screen cell (n=100 deck-paired), the sweep launches these across boxes:
  nice -n 19 .venv/bin/python -u scripts/classical_search/eval_puct_priors.py \
      --c-puct 1.5 --tau-p 5 --leaf-quantize float --final-select Q \
      --cand-sims 800 --champ-sims 6400 --exact-k 4 --n 100 --paired \
      --seed-start 9000000000 --workers 14 \
      --out-root /mnt/c/carc-shared/classical_search --shared-claim

Phase 1.1b transitivity round-robin (measurement/classical_search/ROUND_ROBIN_PLAN.md)
adds two OPTIONAL flags (legacy invocations are byte-identical without them):
  --candidate {puct|h<sims>}   h<sims> = plain HeuristicMCTS candidate (same v2.9 leaf
                               + exact-K handoff as the champion side); puct = default.
  --opponent {h<sims>|net:<ckpt.pt>}
                               h<sims> = HeuristicMCTS opponent (+ exact-K handoff).
                               net:<ckpt> = NeuralMCTS opponent, play knobs PINNED to
                               the rod_v2 anchor harness (scripts/level2/
                               eval_hybrid_handoff.py ITER8_*): sims=200, c_puct=3.0,
                               v2.9 leaf + residual_scale=0.25, BARE (no exact tail —
                               the anchor rows were played bare). Net-on-CPU per worker
                               by default; pass --shm-eval-server <NAME> to attach the
                               workers to a running carc-orch SHM orchestrator.
  New-flag cells get rr_* out-subdirs (e.g. rr_puct2750_vs_net-iter02_k2); seat pairing,
  deck seeds, claims, aggregation and summary.json ride the existing machinery.

ENGINE (rustport P6). ``--backend rust`` runs BOTH clairvoyant PUCT prefixes -- the
candidate AND the ``--opponent puct`` champion sibling -- on ``carc_rs`` via
``rust_agent.RustClairvoyantAgent`` (mirror protocol: ``start_game`` once, ``advance``
on EVERY applied action of BOTH seats, hard sync check per decision). Identity gates:
``scripts/rustport/gate_clairvoyant.py`` (candidate knobs) and
``scripts/rustport/gate_clairvoyant_opponent.py`` (champion flag-OFF knobs). The
``h<sims>`` HeuristicMCTS opponent, the net arms, and the exact-K clairvoyant tail have
no Rust surface and stay Python; the tail is shared identically by both sides, so it
caps the speedup without biasing the A/B. Every config the Rust surface cannot express
fails CLOSED at argparse -- there is no silent Python fallback.
"""
from __future__ import annotations

import os

# v2.9 Bmild_cap8 leaf env — MUST precede the carcassonne_ai imports (DEFAULT_CONFIG
# reads these at import). Matches production / scripts/bench_phone_budget.py.
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    # ⚠️ The installed numpy is scipy-OpenBLAS (DYNAMIC_ARCH), NOT MKL — so the
    # OMP/MKL pins above are INERT for the real BLAS backend. Left unpinned,
    # OpenBLAS spawns a busy-waiting thread POOL sized to the box (32 on the
    # 5900XT) in EVERY worker. With W30(local)+W22(laptop) that is 30×32 threads
    # spin-waiting on 32 cores → the whole box thrashes and forward progress
    # stalls ("54 workers at 100% CPU, R state, no game completes for hours" —
    # the curve175 n=400 hang, 2026-07-06). Pinning to 1 makes each net-free CPU
    # worker truly single-threaded; numerics are UNCHANGED (BLAS thread count is
    # result-neutral). MUST precede `import numpy` (below) — OpenBLAS reads these
    # at first BLAS call; forked Pool workers inherit the env.
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

import argparse
import csv
import dataclasses as dc
import hashlib
import json
import math
import socket
import sys
import time
from dataclasses import asdict, dataclass
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))  # endgame_solver
sys.path.insert(0, str(Path(__file__).resolve().parent))  # c5_leaf_override (sibling)

from carcassonne_ai import eval_provenance as ep  # noqa: E402
from carcassonne_ai.alphabeta_agent import (  # noqa: E402
    AlphaBetaAgent,
    AlphaBetaConfig,
)
from carcassonne_ai.claim import try_claim as _try_claim  # noqa: E402
from carcassonne_ai.eval_provenance import deck_hash  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.heuristic_prior_mcts import (  # noqa: E402
    HeuristicPriorAgent,
    HeuristicPriorConfig,
)
from carcassonne_ai.mcts import HeuristicMCTS  # noqa: E402
from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

import endgame_solver as S  # noqa: E402

# C5 candidate-leaf override helpers — SHARED with eval_fair_puct.py (see
# c5_leaf_override.py); imported (not copy-pasted) so the two harnesses can never
# diverge on the --cand-leaf-json parse/coercion/cy-guard semantics.
from c5_leaf_override import (  # noqa: E402
    _assert_cy_float_path,
    _leaf_dict,
    _leaf_hash,
    _load_cand_leaf_cfg,
)

try:
    from wingedsheep.carcassonne.objects.game_phase import GamePhase  # noqa: E402
    _TILES_PHASE = GamePhase.TILES
except Exception:  # pragma: no cover
    _TILES_PHASE = None

EVAL_ROOT = REPO / "data" / "classical_search"
CHAMP_C = 3.0  # production UCT exploration constant for HeuristicMCTS
EXACT_BUDGET = int(os.environ.get("CARCASSONNE_EXACT_BUDGET", "2000000"))

# Per-game wall-clock watchdog (safety net). A single game that runs longer than
# this many seconds is ABANDONED and recorded as a `game_timeout` (excluded from
# win/elo/paired stats, counted+printed separately) so one pathological/stuck deck
# can never wedge a Pool worker indefinitely and stall the whole eval — mirrors the
# solver's BudgetExceeded→timeout accounting, one level up. The check is between
# moves (each move is individually bounded), so it fires within one move of the
# deadline. Default 3600s is a safety net far above any legitimate game (the
# heaviest observed c5 game ~1370s wall, ~525s single-thread); it only ever bites a
# genuine hang, so it is a no-op when nothing hangs. Set CARCASSONNE_GAME_WALL_SECS=0
# to disable, or lower it to tighten. Independent of the OpenBLAS pin above (which is
# the actual fix for the 2026-07-06 oversubscription hang); this bounds the residual
# tail risk of a genuinely expensive deck.
GAME_WALL_SECS = float(os.environ.get("CARCASSONNE_GAME_WALL_SECS", "3600"))

# Neural-opponent play knobs — PINNED to the rod_v2 anchor construction
# (scripts/level2/eval_hybrid_handoff.py: ITER8_SIMS / ITER8_CPUCT /
# ITER8_RESIDUAL_SCALE + _make_iter8_mcts), the harness behind the rod_v2 iter_02
# anchor rows (results.csv rodv2_iter02_vs_heur6400_v29_n200 /
# rodv2_iter02_vs_heur3200_v29_n200, launched via scripts/rod_v2/run_heur_eval_v29.sh).
# NET_MEEPLE_K matches that wrapper's --meeple-k-a 2.0 (inert under the v2.9 curve —
# the curve replaces the flat term — kept for byte-parity with the anchor harness).
NET_SIMS = 200
NET_CPUCT = 3.0
NET_RESIDUAL_SCALE = 0.25
NET_MEEPLE_K = 2.0
NET_N_CH = 78   # iter_02-family input planes; MUST match the orch server export (n_ch=78)


# --------------------------------------------------------------------------- #
# Handoff (mirrors scripts/level2/eval_hybrid_handoff._ExactAgent, generalized  #
# over the prefix agent so BOTH sides share the SAME exact-K endgame).          #
# --------------------------------------------------------------------------- #
def k_remaining(state) -> int:
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def _should_latch(state, K: int) -> bool:
    """Latch on the first TILES-phase decision with k_remaining<=K (turn-atomic,
    one-way: k is monotone non-increasing). IDENTICAL trigger to eval_hybrid_handoff."""
    return (_TILES_PHASE is not None and state.phase == _TILES_PHASE
            and k_remaining(state) <= K)


class _ExactHandoff:
    """A prefix agent, then EXACT clairvoyant-solver play once latched.

    `prefix` is any object exposing `.move(board) -> int` (candidate or champion).
    Latching + timeout-fallback semantics match eval_hybrid_handoff._ExactAgent:
    on BudgetExceeded the prefix plays THAT move (stays latched, retries next ply)."""

    def __init__(self, prefix, game_plain, K: int, budget: int = EXACT_BUDGET):
        self._prefix = prefix
        self._game = game_plain
        self._K = K
        self._budget = budget
        self._latched = False
        self.latch_k = None
        self.prefix_moves = 0
        self.exact_moves = 0
        self.n_timeouts = 0
        self.solver_secs = 0.0
        self.solver_nodes = 0
        self.max_solve_secs = 0.0
        self.prefix_secs = 0.0

    def move(self, board) -> int:
        if not self._latched and _should_latch(board.state, self._K):
            self._latched = True
            self.latch_k = k_remaining(board.state)
        if not self._latched:
            t0 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t0
            self.prefix_moves += 1
            return mv
        t0 = time.perf_counter()
        try:
            res = S.solve(self._game, board, mode="clairvoyant",
                          budget=self._budget, alphabeta=True)
            dt = time.perf_counter() - t0
            self.solver_secs += dt
            self.max_solve_secs = max(self.max_solve_secs, dt)
            self.solver_nodes += res.nodes
            self.exact_moves += 1
            return int(min(res.optimal_actions))
        except S.BudgetExceeded:
            self.solver_secs += time.perf_counter() - t0
            self.n_timeouts += 1
            t1 = time.perf_counter()
            mv = int(self._prefix.move(board))
            self.prefix_secs += time.perf_counter() - t1
            self.prefix_moves += 1
            return mv


class _ChampPrefix:
    """Champion prefix: HeuristicMCTS(heur_leaf='v2_7') @ champ_sims, c=3.0."""

    def __init__(self, game, sims, seed, leaf_cfg):
        self._m = HeuristicMCTS(game=game, simulations=sims, c=CHAMP_C, seed=seed,
                                heur_leaf="v2_7", leaf_cfg=leaf_cfg)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def _champ_puct_cfg(shared: dict, reuse: bool = False,
                    pin_champion: bool = False) -> "HeuristicPriorConfig":
    """Build the flag-OFF champion PUCT-heuristic-priors config, taking only the
    SHARED axes (c_puct/tau_p/leaf_quantize) from `shared` (the candidate's
    cand_cfg_dict) and forcing every variant knob to its champion-off value. This
    is the --opponent puct sibling of the variant candidate.

    `reuse` (default False = byte-for-byte the flag-OFF sibling) is the C6
    --opp-reuse-tree relaxation: the Stage-2 confirm runs vs the champion OF RECORD,
    which is reuse_tree=True (CL-044). Left False for the Stage-1 screen.

    `pin_champion` (default False = byte-identical legacy: the c_puct/tau_p/
    leaf_quantize "shared axes" copy from the candidate) is the T3 --opp-pin-champion
    fix for the JOINT knob sweep: when a sweep moves --c-puct/--tau-p the shared-axis
    copy would silently move BOTH sides (the A/B measures nothing). With it set the
    opponent sibling takes the champion CONSTANTS (CHAMP_PUCT_C_PUCT/TAU_P/
    LEAF_QUANTIZE) instead, so the candidate's search knobs are isolated. See
    OPTUNA_KNOB_SWEEP_DESIGN.md §3/§5(a)."""
    if pin_champion:
        c_puct = CHAMP_PUCT_C_PUCT
        tau_p = CHAMP_PUCT_TAU_P
        leaf_quantize = CHAMP_PUCT_LEAF_QUANTIZE
    else:
        c_puct = shared["c_puct"]
        tau_p = shared["tau_p"]
        leaf_quantize = shared["leaf_quantize"]
    return HeuristicPriorConfig(
        c_puct=c_puct, tau_p=tau_p,
        leaf_quantize=leaf_quantize,
        final_select=CHAMP_PUCT_FINAL_SELECT, value_norm=CHAMP_PUCT_VALUE_NORM,
        c_lcb=CHAMP_PUCT_C_LCB, reuse_tree=bool(reuse),
        root_select="puct",   # the flag-OFF baseline: PUCT root, never Gumbel
        leaf_cfg=DEFAULT_CONFIG,
    )


class _PuctPrefix:
    """Champion PUCT-heuristic-priors prefix (flags OFF) — the --opponent puct
    baseline for a variant-ON-vs-variant-OFF A/B. HeuristicPriorAgent already
    clear()s its tree each move (reuse_tree=False), so a fresh .move() per ply."""

    def __init__(self, game, cfg, sims, seed):
        self._a = HeuristicPriorAgent(game, cfg, simulations=sims, seed=seed)

    def move(self, board) -> int:
        return int(self._a.move(board))


def _rust_clairvoyant(cfg, sims, seed):
    """The Rust route for a CLAIRVOYANT PUCT-heuristic-priors prefix — used by BOTH
    sides of this harness (candidate since 2026-08-02, opponent since the port below).

    ⚠️ `RustClairvoyantAgent` is a MIRROR agent: it owns its own `MirrorState` seated
    on the true deck, so every prefix built here MUST be `start_game()`d on the real
    initial board and `advance()`d with EVERY applied action of BOTH seats. `_play_one`
    / `_smoke` do that by discovering `.advance` on the prefix — which is why this
    returns the agent itself rather than a `_PuctPrefix`-style wrapper (a wrapper would
    hide the mirror protocol and the agent would answer from a frozen mirror).

    Refuses nothing here: the config-level refusals (reuse_tree, evaluator injection,
    gumbel root) live in `rust_agent`/`search_config_rs` and RAISE rather than
    silently running a different search; the CLI fails closed ahead of them so an
    operator sees an argparse error, not a worker traceback."""
    from carcassonne_ai.rust_agent import RustClairvoyantAgent

    return RustClairvoyantAgent(Game(enable_legal_moves_cache=True), cfg,
                                simulations=int(sims), seed=seed)


class _AbPrefix:
    """C6 ID-alpha-beta candidate prefix (design §8). Wraps AlphaBetaAgent for
    _ExactHandoff — exposes `.move`, clear()s the TT once at construction (game
    start; the TT then PERSISTS across the game's moves, §3). The search game is
    cache-free (the agent builds its own if handed a cached game)."""

    def __init__(self, game, cfg: "AlphaBetaConfig", seed=None):
        self.agent = AlphaBetaAgent(game, cfg, seed=seed)
        self.agent.clear()

    def move(self, board) -> int:
        return int(self.agent.move(board))


# --------------------------------------------------------------------------- #
# Track-F Gate A: oracle-prior production-depth headroom probe (F2, 2026-07-19). #
# docs/reviews/INTEGRATED_REVIEW_20260719.md §"Candidate 2 / Gate A". Measures   #
# whether a NEAR-ORACLE root prior (the champion's OWN visit distribution at a    #
# larger budget) buys anything at production depth — the cheapest test of whether #
# ANY policy-learning spend is rational. Default OFF (--oracle-prior-mult unset)  #
# → byte-identical to the plain champion path.                                    #
# --------------------------------------------------------------------------- #
# The visits->prior extraction (alias-fold + eps-floor) + the leaf counter now live
# in the SINGLE-SOURCE library module ``carcassonne_ai.oracle_prior`` so the CLAIRVOYANT
# screen (this harness) and the FAIR confirm (eval_fair_puct.py via the library
# FairHeuristicPriorAgent) can NEVER diverge on them. Re-exported under the historical
# private names so this module's callers + tests/test_oracle_prior.py are unchanged.
from carcassonne_ai.oracle_prior import (  # noqa: E402
    LeafCounter as _LeafCounter,
    oracle_prior_from_visits as _oracle_prior_from_visits,
    root_action_groups as _root_action_groups,
)


class _OraclePriorPrefix:
    """Gate A oracle-prior candidate prefix (Track-F F2). Per root move:

      1. PRE-SEARCH: an IDENTICAL champion search at ``mult × sims`` on a FRESH
         tree; read its transposition-deduped root visit distribution.
      2. Convert that distribution to a prior over legal root actions
         (``_oracle_prior_from_visits``: visits/total, epsilon-floored, alias-folded).
      3. MAIN SEARCH: the normal production-budget (``sims``) search with the ROOT
         priors REPLACED by that distribution — deeper node priors stay the
         heuristic evaluator's (this probe measures ROOT-prior headroom, the
         dominant prior effect).

    The pre-search tree is NOT reused into the main search (fresh clear() each);
    reuse would conflate deeper search with better priors — the probe isolates the
    prior channel. Both agents run reuse_tree=OFF (the harness enforces this) so each
    move lands the override on a freshly expanded root. Exposes ``.move(board)`` so it
    drops into ``_ExactHandoff`` exactly like a plain HeuristicPriorAgent."""

    def __init__(self, game_main, game_pre, cfg, sims, mult, eps_coef, seed):
        self._main = HeuristicPriorAgent(game_main, cfg, simulations=sims, seed=seed)
        self._pre = HeuristicPriorAgent(game_pre, cfg, simulations=sims * int(mult),
                                        seed=seed)
        # count leaf/root expansions per phase (cost writeup)
        self._main.mcts.evaluator = _LeafCounter(self._main.mcts.evaluator)
        self._pre.mcts.evaluator = _LeafCounter(self._pre.mcts.evaluator)
        self._mult = int(mult)
        self._eps_coef = float(eps_coef)
        # per-game cost accounting (read off by _oracle_telemetry)
        self.oracle_moves = 0
        self.presearch_secs = 0.0
        self.mainsearch_secs = 0.0
        self.presearch_leaf_calls = 0
        self.mainsearch_leaf_calls = 0
        self.last_reached_root = False  # smoke/functional-check: override reached root

    def move(self, board) -> int:
        m_pre = self._pre.mcts
        # 1. PRE-SEARCH on a fresh tree (mult × sims), read deduped root visits.
        self._pre.clear()
        m_pre.evaluator.n = 0
        t0 = time.perf_counter()
        m_pre.search(board)
        counts, actions = m_pre.root_visit_distribution(board)
        self.presearch_secs += time.perf_counter() - t0
        self.presearch_leaf_calls += m_pre.evaluator.n
        # 2. Build the oracle root-prior distribution (visits -> prior).
        counts_by_action = {int(a): float(c) for a, c in zip(actions, counts)}
        groups = _root_action_groups(self._main.game, board)
        override = _oracle_prior_from_visits(groups, counts_by_action, self._eps_coef)
        # 3. MAIN SEARCH at production sims with the ROOT priors replaced.
        m_main = self._main.mcts
        m_main.set_root_prior_override(override)   # survives the move()'s clear()
        m_main.evaluator.n = 0
        t1 = time.perf_counter()
        mv = self._main.move(board)                # clear() -> search(applies override)
        self.mainsearch_secs += time.perf_counter() - t1
        self.mainsearch_leaf_calls += m_main.evaluator.n
        self.oracle_moves += 1
        self.last_reached_root = bool(override)
        return int(mv)


def _oracle_telemetry(prefix) -> dict:
    """Per-game oracle cost telemetry read off an _OraclePriorPrefix (empty for any
    other candidate). Feeds the GameResult cost fields + the summary aggregation."""
    if not isinstance(prefix, _OraclePriorPrefix):
        return {}
    return {
        "oracle_prior_moves": int(prefix.oracle_moves),
        "oracle_presearch_secs": round(prefix.presearch_secs, 3),
        "oracle_mainsearch_secs": round(prefix.mainsearch_secs, 3),
        "oracle_presearch_leaf_calls": int(prefix.presearch_leaf_calls),
        "oracle_mainsearch_leaf_calls": int(prefix.mainsearch_leaf_calls),
    }


# --------------------------------------------------------------------------- #
# Round-robin extension: candidate/opponent specs + the neural opponent         #
# (measurement/classical_search/ROUND_ROBIN_PLAN.md). Torch is imported lazily  #
# so the legacy pure-CPU cells never pay for it.                                #
# --------------------------------------------------------------------------- #
def _parse_candidate(tok: str):
    """'puct' -> ("puct", None); 'h<sims>' -> ("heur", sims); 'ab' -> ("ab", None)."""
    tok = tok.strip()
    if tok == "puct":
        return ("puct", None)
    if tok == "ab":                       # C6 ID-alpha-beta candidate (design §8)
        return ("ab", None)
    if tok.startswith("h") and tok[1:].isdigit() and int(tok[1:]) > 0:
        return ("heur", int(tok[1:]))
    raise ValueError(f"bad --candidate {tok!r}; expected puct|h<sims>|ab (e.g. h6400)")


# The champion PUCT-heuristic-priors config (flags OFF), used as the --opponent
# puct baseline for a variant-ON-vs-variant-OFF A/B (task 2026-07-06). "visits" is
# the champion-of-record final selector; value_norm 15 / c_lcb 1.0 / reuse_tree off
# are the flag-off defaults. Only the SHARED axes (c_puct/tau_p/leaf_quantize/sims)
# are taken from the candidate so the sole measured difference is the variant flag.
CHAMP_PUCT_FINAL_SELECT = "visits"
CHAMP_PUCT_VALUE_NORM = 15.0
CHAMP_PUCT_C_LCB = 1.0
# T3 --opp-pin-champion (OPTUNA_KNOB_SWEEP_DESIGN.md §3): the champion's SHARED-axis
# values (c_puct/tau_p/leaf_quantize). Legacy default copies these from the candidate
# ("shared axes" — correct for C2–C7 which never swept them); the joint knob sweep
# pins them to these constants so moving --c-puct/--tau-p isolates the candidate side.
CHAMP_PUCT_C_PUCT = 1.5
CHAMP_PUCT_TAU_P = 5.0
CHAMP_PUCT_LEAF_QUANTIZE = "float"


def _parse_opponent(tok: str):
    """'h<sims>' -> ("heur", sims, None); 'net:<ckpt>' -> ("net", NET_SIMS, path);
    'puct' -> ("puct", None, None) (sims resolved to cand_sims in _resolve_specs)."""
    tok = tok.strip()
    if tok == "puct":
        return ("puct", None, None)
    if tok.startswith("net:"):
        path = tok[len("net:"):]
        if not path:
            raise ValueError("net: opponent needs a checkpoint path (net:/abs/iter.pt)")
        return ("net", NET_SIMS, path)
    if tok.startswith("h") and tok[1:].isdigit() and int(tok[1:]) > 0:
        return ("heur", int(tok[1:]), None)
    raise ValueError(f"bad --opponent {tok!r}; expected h<sims>|net:<ckpt.pt>|puct")


def _resolve_specs(args):
    """Resolve --candidate/--opponent -> (cand_kind, opp_kind, opp_sims, net_ckpt,
    new_mode). Sets args.cand_sims from an h<sims> candidate token (the token wins).
    Raises ValueError on a bad/missing spec (callers map it to an argparse error)."""
    cand_kind, cand_tok_sims = _parse_candidate(args.candidate)
    if cand_kind == "heur":
        args.cand_sims = cand_tok_sims
    elif cand_kind == "ab":
        pass                                   # αβ has no sims axis (child-step budget)
    elif args.cand_sims is None:
        raise ValueError("--cand-sims is required for --candidate puct")
    if args.opponent is None:
        # legacy champion side: HeuristicMCTS h<champ-sims> (default 6400).
        opp_kind = "heur"
        opp_sims = args.champ_sims if args.champ_sims is not None else 6400
        net_ckpt = None
    else:
        opp_kind, opp_sims, net_ckpt = _parse_opponent(args.opponent)
        if opp_kind == "puct":
            if cand_kind == "puct":
                # champion PUCT opponent plays at the SAME nominal sims as the
                # candidate (equal-sims variant A/B); --champ-sims is ignored.
                opp_sims = args.cand_sims
            elif cand_kind == "ab":
                # C6: ab candidate vs the champion-of-record PUCT sibling. αβ has no
                # cand_sims, so the champion budget comes from --champ-sims (mandatory).
                if args.champ_sims is None:
                    raise ValueError("--champ-sims is required for "
                                     "--candidate ab --opponent puct")
                opp_sims = args.champ_sims
            else:
                raise ValueError("--opponent puct requires --candidate puct or ab "
                                 "(it is the flag-OFF sibling of the search candidate)")
    if args.champ_sims is None:                # backfill for downstream tags/display
        args.champ_sims = 6400
    new_mode = (args.candidate != "puct") or (args.opponent is not None)
    return cand_kind, opp_kind, opp_sims, net_ckpt, new_mode


def _variant_sig(args) -> str:
    """Compact signature of the candidate's ACTIVE variant knobs vs the champion
    (final_select "visits", value_norm 15, c_lcb 1.0, reuse off). Empty when the
    candidate IS the champion. Keeps distinct variant A/Bs from sharing an out-dir
    (which would silently MIX their per-seed result json)."""
    parts = []
    # final_select is a no-op under Gumbel (Gumbel IS the final choice) -> only
    # tag it on the PUCT-root path so a gumbel cell tag stays clean.
    if args.root_select == "puct" and args.final_select != CHAMP_PUCT_FINAL_SELECT:
        parts.append(args.final_select
                     + (f"clcb{args.c_lcb:g}" if args.final_select == "lcb" else ""))
    if args.reuse_tree:
        parts.append("reuse")
    if args.value_norm != CHAMP_PUCT_VALUE_NORM:
        parts.append(f"vn{args.value_norm:g}")
    if args.root_select != "puct":
        g = f"gumbel{args.gumbel_m}"
        if not args.gumbel_retain_g:
            g += "ng"   # g-dropped-in-elimination variant (paper-exact = default, no tag)
        if args.gumbel_c_visit != 50.0:
            g += f"cv{args.gumbel_c_visit:g}"
        if args.gumbel_c_scale != 1.0:
            g += f"cs{args.gumbel_c_scale:g}"
        parts.append(g)
    # T3 --opp-pin-champion: c_puct/tau_p normally ride BOTH sides (shared axes) so they
    # are never tagged; when the opponent is pinned they genuinely differ between sides,
    # so tag them (only when they diverge from the champion constant) — defense-in-depth
    # against two pinned c/τ cells auto-colliding on one out-dir (design §3(1)).
    if getattr(args, "opp_pin_champion", False):
        if args.c_puct != CHAMP_PUCT_C_PUCT:
            parts.append(f"c{args.c_puct:g}")
        if args.tau_p != CHAMP_PUCT_TAU_P:
            parts.append(f"tp{args.tau_p:g}")
    # Track-F Gate A oracle-prior overlay (CANDIDATE only) — tag so an oracle cell
    # never shares an auto out-dir with the plain champion. Empty when OFF.
    if getattr(args, "oracle_prior_mult", None):
        parts.append(f"oracle{args.oracle_prior_mult}")
    return "".join("-" + p for p in parts)


def _ab_variant_sig(args) -> str:
    """Compact signature of the C6 ab candidate's ACTIVE variant knobs vs the v1
    defaults (asp 3.0, pvs on, killers 2, lmr off, futility off). Empty at defaults;
    rides on the cand token so Stage-1.5 knob cells never collide (design §8)."""
    parts = []
    if args.cand_ab_lmr:
        parts.append("lmr")
    if args.cand_ab_asp != 3.0:
        parts.append(f"asp{args.cand_ab_asp:g}")
    if args.cand_ab_no_pvs:
        parts.append("nopvs")
    if args.cand_ab_killers != 2:
        parts.append(f"k{args.cand_ab_killers}")
    if args.cand_ab_futility != 0.0:
        parts.append(f"fut{args.cand_ab_futility:g}")
    return "".join("-" + p for p in parts)


def _cell_tag(args, cand_kind, opp_kind, opp_sims, net_ckpt, new_mode) -> str:
    """Out-subdir cell tag. LEGACY invocations (no --candidate/--opponent) keep the
    historical naming byte-identical; round-robin invocations get rr_* names
    (e.g. rr_puct2750_vs_net-iter02_k2, rr_h6400_vs_h12800_k2,
    rr_ab28000_vs_puctchamp2750_k2, rr_ab28000_vs_puctchampreuse2750_k2)."""
    if not new_mode:
        return (f"puct_c{args.c_puct:g}_tau{args.tau_p:g}_{args.leaf_quantize}_{args.final_select}"
                f"_s{args.cand_sims}_vs_h{args.champ_sims}_k{args.exact_k}")
    if cand_kind == "ab":
        cand_tok = f"ab{args.cand_ab_steps}"
    elif cand_kind == "puct":
        cand_tok = f"puct{args.cand_sims}"
    else:
        cand_tok = f"h{args.cand_sims}"
    if opp_kind == "heur":
        opp_tok = f"h{opp_sims}"
    elif opp_kind == "puct":
        # the candidate's variant signature rides on the cand token so
        # variant-ON-vs-champion cells never collide.
        cand_tok += _ab_variant_sig(args) if cand_kind == "ab" else _variant_sig(args)
        opp_tok = f"puctchamp{'reuse' if args.opp_reuse_tree else ''}{opp_sims}"
    else:
        opp_tok = "net-" + Path(net_ckpt).stem.replace("_", "")
    return f"rr_{cand_tok}_vs_{opp_tok}_k{args.exact_k}"


class _NetPrefix:
    """Neural opponent prefix: NeuralMCTS @ NET_SIMS, c_puct=NET_CPUCT, priors+value
    from the net with the value replaced by the v2.9 leaf + net-value residual at
    NET_RESIDUAL_SCALE. Construction mirrors eval_hybrid_handoff._make_iter8_mcts
    (the rod_v2 anchor) byte-for-byte: dataclasses.replace(DEFAULT_CONFIG,
    residual_scale, meeple_k) -> make_v25_value_wrapper -> NeuralMCTS."""

    def __init__(self, base_eval, game_farm, seed):
        from carcassonne_ai.evaluators import make_v25_value_wrapper
        from carcassonne_ai.mcts import NeuralMCTS
        cfg = dc.replace(DEFAULT_CONFIG, residual_scale=NET_RESIDUAL_SCALE,
                         meeple_k=NET_MEEPLE_K)
        leaf = make_v25_value_wrapper(base_eval, cfg)
        self._m = NeuralMCTS(game=game_farm, evaluator=leaf, simulations=NET_SIMS,
                             seed=seed, c_puct=NET_CPUCT)

    def move(self, board) -> int:
        self._m.clear()
        return int(self._m.best_action(board))


def _read_ckpt_meta(ckpt_path: str) -> dict:
    """Checkpoint architecture metadata (parent-side; needed for SHM connect width,
    the farm-scalar flag and the manifest)."""
    import torch
    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    meta = {"n_filters": int(ck["n_filters"]), "n_blocks": int(ck["n_blocks"]),
            "n_scalar_features": int(ck.get("n_scalar_features", 10)),
            "value_global_pool": bool(ck.get("value_global_pool", False))}
    del ck
    return meta


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_net_cpu(ckpt_path: str):
    """Load the checkpoint into a CPU CarcassonneNet (eval mode). Mirrors
    eval_hybrid_handoff._worker_init's non-orch path. -> (net, device, n_scalar)."""
    import torch
    from carcassonne_ai.network import CarcassonneNet
    torch.set_num_threads(1)
    dev = torch.device("cpu")
    ck = torch.load(ckpt_path, map_location=dev, weights_only=False)
    ns = int(ck.get("n_scalar_features", 10))
    net = CarcassonneNet(n_filters=ck["n_filters"], n_blocks=ck["n_blocks"],
                         n_scalar_features=ns,
                         value_global_pool=bool(ck.get("value_global_pool", False))).to(dev)
    net.load_state_dict(ck["model_state"])
    net.train(False)
    return net, dev, ns


def _make_net_prefix(seed: int) -> "_NetPrefix":
    """Per-game neural opponent from worker state: fresh farm-width Game + a base
    evaluator over the worker's local CPU net OR its carc-orch SHM handles."""
    farm = _W["net_ns"] > 10
    gf = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
    if _W.get("net_handles") is not None:
        from carcassonne_ai.remote_evaluators import make_remote_single_evaluator
        base = make_remote_single_evaluator(_W["net_handles"], gf)
    else:
        from carcassonne_ai.evaluators import make_single_evaluator
        base = make_single_evaluator(_W["net"], _W["net_dev"], gf)
    return _NetPrefix(base, gf, seed)


# _leaf_dict / _leaf_hash / _load_cand_leaf_cfg / _assert_cy_float_path now live in
# the shared c5_leaf_override module (imported above) — kept identical for both
# harnesses. eval_fair_puct.py (Stage 3) imports the same four helpers.


# --------------------------------------------------------------------------- #
@dataclass
class GameResult:
    seed: int
    a_seat: int            # seat the CANDIDATE plays this game
    cand_sims: int
    champ_sims: int
    score_p0: int
    score_p1: int
    diff: int              # candidate - champion
    won_by_cand: bool
    drew: bool
    elapsed_s: float
    moves: int
    deck_hash: str = ""
    # per-side instrumentation
    cand_prefix_moves: int = 0
    cand_exact_moves: int = 0
    cand_prefix_secs: float = 0.0
    cand_solver_secs: float = 0.0
    cand_timeouts: int = 0
    champ_prefix_moves: int = 0
    champ_exact_moves: int = 0
    champ_prefix_secs: float = 0.0
    champ_solver_secs: float = 0.0
    champ_timeouts: int = 0
    latch_k: int | None = None
    game_timeout: bool = False   # True = abandoned by the per-game wall watchdog
                                 # (partial board; excluded from win/elo/paired stats)
    # C6 ab-candidate per-game telemetry (0 unless the candidate is --candidate ab;
    # depth_completed feeds the §9 depth-truncation gate). Defaulted so every legacy
    # cell serializes byte-identically.
    cand_ab_depth_med: float = 0.0
    cand_ab_depth_min: int = 0
    cand_ab_nodes: int = 0
    cand_ab_steps: int = 0
    cand_ab_tt_probes: int = 0
    cand_ab_tt_exact_hits: int = 0
    cand_ab_tt_cross_parent_hits: int = 0
    cand_ab_moves: int = 0
    # Track-F Gate A oracle-prior per-game cost telemetry (0 unless the candidate is
    # an _OraclePriorPrefix). OMITTED from the serialized JSON for non-oracle cells so
    # every legacy cell stays byte-identical (the default-OFF / result-neutral gate).
    oracle_prior_moves: int = 0
    oracle_presearch_secs: float = 0.0
    oracle_mainsearch_secs: float = 0.0
    oracle_presearch_leaf_calls: int = 0
    oracle_mainsearch_leaf_calls: int = 0


def _result_path(out: Path, seed: int, a_seat: int) -> Path:
    return out / f"seed{seed:012d}_a{a_seat}.json"


def _try_load(p: Path):
    if p.exists():
        try:
            return GameResult(**json.load(open(p)))
        except Exception:
            p.unlink(missing_ok=True)
    return None


# C6 ab-candidate telemetry fields — OMITTED from the serialized per-game JSON for
# non-ab cells (all zero there) so every legacy/non-ab cell stays byte-identical to
# today's schema (the default-OFF / result-neutral gate). _try_load re-fills them from
# the dataclass defaults, so a reload is lossless either way.
_AB_RESULT_FIELDS = (
    "cand_ab_depth_med", "cand_ab_depth_min", "cand_ab_nodes", "cand_ab_steps",
    "cand_ab_tt_probes", "cand_ab_tt_exact_hits", "cand_ab_tt_cross_parent_hits",
    "cand_ab_moves",
)

# Track-F Gate A oracle-prior cost fields — OMITTED from the serialized per-game
# JSON for non-oracle cells (all zero there) so every legacy/non-oracle cell stays
# byte-identical to today's schema. _try_load re-fills them from the dataclass
# defaults, so a reload is lossless either way.
_ORACLE_RESULT_FIELDS = (
    "oracle_prior_moves", "oracle_presearch_secs", "oracle_mainsearch_secs",
    "oracle_presearch_leaf_calls", "oracle_mainsearch_leaf_calls",
)


def _save(p: Path, r: GameResult):
    p.parent.mkdir(parents=True, exist_ok=True)
    d = asdict(r)
    if not d.get("cand_ab_moves"):          # non-ab cell -> omit ab keys (schema-identical)
        for k in _AB_RESULT_FIELDS:
            d.pop(k, None)
    if not d.get("oracle_prior_moves"):     # non-oracle cell -> omit oracle keys (schema-identical)
        for k in _ORACLE_RESULT_FIELDS:
            d.pop(k, None)
    tmp = p.with_name(f".{p.stem}.{socket.gethostname()}.{os.getpid()}.partial.json")
    json.dump(d, open(tmp, "w"))
    tmp.replace(p)


_W: dict = {}


def _ab_telemetry(prefix) -> dict:
    """Per-game C6 ab-candidate telemetry read off the AlphaBetaAgent behind an
    _AbPrefix (design §8). depth_completed -> per-game median/min feeds the §9
    depth-truncation gate. Empty for non-ab candidates."""
    ag = getattr(prefix, "agent", None)
    if ag is None:
        return {}
    dcs = list(ag.depth_completed)
    return {
        "cand_ab_depth_med": float(np.median(dcs)) if dcs else 0.0,
        "cand_ab_depth_min": int(min(dcs)) if dcs else 0,
        "cand_ab_nodes": int(ag.nodes),
        "cand_ab_steps": int(ag.steps_used),
        "cand_ab_tt_probes": int(ag.tt_probes),
        "cand_ab_tt_exact_hits": int(ag.tt_exact_hits),
        "cand_ab_tt_cross_parent_hits": int(ag.tt_cross_parent_hits),
        "cand_ab_moves": len(dcs),
    }


def _worker_init(cand_cfg_dict, cand_sims, champ_sims, exact_k,
                 shared_claim, claim_host, claim_stale,
                 cand_kind="puct", opp_kind="heur", opp_sims=None,
                 net_ckpt="", net_ns=10, shm_name="", id_q=None,
                 cand_leaf_cfg=None, ab_cfg_dict=None, opp_reuse=False,
                 opp_pin_champion=False, oracle_prior_mult=None,
                 oracle_prior_eps_coef=1e-3,
                 backend="python"):
    _W["cand_cfg_dict"] = cand_cfg_dict
    # ENGINE (rustport P6). ⚠️ FARM RULE: this is a GAME-PARALLEL pool, and the
    # clairvoyant Rust ruler is single-threaded by construction (search_single takes
    # no thread count) -- so a worker here can never oversubscribe the box. The rule
    # is satisfied structurally rather than by a knob; there is no rust_threads to set.
    _W["backend"] = backend
    _W["oracle_prior_mult"] = oracle_prior_mult  # Track-F Gate A (None = OFF)
    _W["oracle_prior_eps_coef"] = oracle_prior_eps_coef
    # candidate-side leaf override (None -> DEFAULT_CONFIG); champion stays DEFAULT.
    _W["cand_leaf_cfg"] = cand_leaf_cfg
    _W["ab_cfg_dict"] = ab_cfg_dict            # C6 AlphaBetaConfig knobs (None unless ab)
    _W["opp_reuse"] = bool(opp_reuse)          # --opp-reuse-tree (Stage-2 confirm only)
    _W["opp_pin_champion"] = bool(opp_pin_champion)  # T3 --opp-pin-champion (§3 shared-axis fix)
    _W["cand_sims"] = cand_sims
    _W["champ_sims"] = champ_sims
    _W["exact_k"] = exact_k
    _W["shared_claim"] = shared_claim
    _W["claim_host"] = claim_host
    _W["claim_stale"] = claim_stale
    _W["cand_kind"] = cand_kind
    _W["opp_kind"] = opp_kind
    _W["opp_sims"] = opp_sims if opp_sims is not None else champ_sims
    _W["net"] = None
    _W["net_dev"] = None
    _W["net_handles"] = None
    _W["net_ns"] = net_ns
    if opp_kind == "net":
        import torch
        torch.set_num_threads(1)
        if shm_name:
            # carc-orch SHM orchestrator: the server owns the only net copy; this
            # worker is CPU-only and gets forwards over SHM (== eval_hybrid_handoff).
            from carcassonne_ai.shm_eval_handles import connect_shm
            _W["net_handles"] = connect_shm(shm_name, id_q.get(), net_ns, NET_N_CH)
        else:
            _W["net"], _W["net_dev"], _W["net_ns"] = _load_net_cpu(net_ckpt)


def _make_ab_cfg():
    """Rebuild the C6 AlphaBetaConfig from the worker's ab knob dict. The leaf is the
    candidate override (--cand-leaf-json) or DEFAULT_CONFIG (env curve125) — the SAME
    resolution the champion side uses, so a valid A/B (design §6 row 12)."""
    d = _W["ab_cfg_dict"]
    leaf_cfg = _W.get("cand_leaf_cfg") or DEFAULT_CONFIG
    return AlphaBetaConfig(
        step_budget=d["step_budget"], max_depth=d["max_depth"], asp=d["asp"],
        pvs=d["pvs"], tt_cap=d["tt_cap"], killers=d["killers"], lmr=d["lmr"],
        futility=d["futility"], leaf_cfg=leaf_cfg)


def _make_cand_cfg():
    d = _W["cand_cfg_dict"]
    # rebuild the LeafConfig — the cfg dict only carries the agent knobs; the leaf
    # is the candidate override (--cand-leaf-json) or DEFAULT_CONFIG (env-resolved
    # Bmild_cap8) when no override was passed (byte-identical to the legacy path).
    leaf_cfg = _W.get("cand_leaf_cfg") or DEFAULT_CONFIG
    return HeuristicPriorConfig(
        c_puct=d["c_puct"], tau_p=d["tau_p"],
        leaf_quantize=d["leaf_quantize"], final_select=d["final_select"],
        value_norm=d["value_norm"], leaf_cfg=leaf_cfg,
        c_lcb=d.get("c_lcb", 1.0), reuse_tree=d.get("reuse_tree", False),
        root_select=d.get("root_select", "puct"), gumbel_m=d.get("gumbel_m", 16),
        gumbel_c_visit=d.get("gumbel_c_visit", 50.0),
        gumbel_c_scale=d.get("gumbel_c_scale", 1.0),
        gumbel_retain_g=d.get("gumbel_retain_g", True),
    )


def _play_one(args) -> GameResult | None:
    out_str, seed, a_seat = args
    out = Path(out_str)
    p = _result_path(out, seed, a_seat)
    cached = _try_load(p)
    if cached is not None:
        return cached
    if _W.get("shared_claim"):
        if not _try_claim(p.with_suffix(".claim"), _W["claim_host"], _W["claim_stale"]):
            return None

    import random
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)  # referee / deck driver
    board = game.get_init_board()
    dh = deck_hash(board)

    K = _W["exact_k"]
    cand_kind = _W.get("cand_kind", "puct")
    # candidate side (prefix = PUCT+heur priors, plain HeuristicMCTS for h<sims>, or
    # the C6 ID-alpha-beta agent for ab). ab gets a cache-free search game (§2).
    if cand_kind == "heur":
        cand_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), _W["cand_sims"],
                                   seed, DEFAULT_CONFIG)
    elif cand_kind == "ab":
        cand_prefix = _AbPrefix(Game(enable_legal_moves_cache=False), _make_ab_cfg(),
                                seed=seed)
    elif _W.get("oracle_prior_mult"):
        # Track-F Gate A oracle-prior candidate (its own main + pre-search games).
        cand_prefix = _OraclePriorPrefix(
            Game(enable_legal_moves_cache=True), Game(enable_legal_moves_cache=True),
            _make_cand_cfg(), sims=_W["cand_sims"], mult=_W["oracle_prior_mult"],
            eps_coef=_W["oracle_prior_eps_coef"], seed=seed)
    else:
        cfg = _make_cand_cfg()
        # ENGINE (rustport P6, wired 2026-08-02). This file never imported
        # champion_factory at all (Class A6 of BACKEND_BYPASS_AUDIT_20260801), so it
        # was structurally unable to see any governance change. ⚠️ BOTH SIDES OF THIS
        # HARNESS ARE CLAIRVOYANT by design (module docstring), so the candidate is
        # the true-deck ruler, NOT the fair PIMC champion -- its Rust route is
        # RustClairvoyantAgent over MirrorState.search_single, gated bit-exact by
        # scripts/rustport/gate_clairvoyant.py, not the fair backend.
        if _W.get("backend", "python") == "rust":
            cand_prefix = _rust_clairvoyant(cfg, _W["cand_sims"], seed)
        else:
            cand_prefix = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                              simulations=_W["cand_sims"], seed=seed)
    # opponent side (prefix = HeuristicMCTS, the flag-OFF champion PUCT sibling, or
    # the pinned rod_v2-anchor NeuralMCTS)
    opp_kind = _W.get("opp_kind", "heur")
    if opp_kind == "net":
        champ_prefix = _make_net_prefix(seed + 1)
        opp_K = 0   # BARE net (pinned anchor config): K=0 never latches the exact tail
    elif opp_kind == "puct":
        # ENGINE (rustport P6, opponent side wired 2026-08-02). The --opponent puct
        # sibling is the SAME clairvoyant single-tree search as the candidate, only at
        # the champion's flag-OFF knobs -- so it takes the SAME Rust route, gated by
        # scripts/rustport/gate_clairvoyant_opponent.py (the champion-knob twin of the
        # candidate's gate_clairvoyant.py). The CLI has already refused every opponent
        # config the Rust surface cannot express (--opp-reuse-tree, net arms).
        opp_cfg = _champ_puct_cfg(_W["cand_cfg_dict"],
                                  reuse=_W.get("opp_reuse", False),
                                  pin_champion=_W.get("opp_pin_champion", False))
        if _W.get("backend", "python") == "rust":
            champ_prefix = _rust_clairvoyant(opp_cfg, _W["opp_sims"], seed + 1)
        else:
            champ_prefix = _PuctPrefix(Game(enable_legal_moves_cache=True), opp_cfg,
                                       _W["opp_sims"], seed + 1)
        opp_K = K
    else:
        champ_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), _W["opp_sims"],
                                    seed + 1, DEFAULT_CONFIG)
        opp_K = K
    cand = _ExactHandoff(cand_prefix, Game(enable_legal_moves_cache=True), K)
    champ = _ExactHandoff(champ_prefix, Game(enable_legal_moves_cache=True), opp_K)
    # Seat EVERY Rust mirror (candidate and/or opponent) on the real initial board.
    # Both mirrors see EVERY applied action of BOTH seats -- a mirror that only saw its
    # own moves would answer from a frozen board, which `check_sync` turns into a hard
    # MirrorDesync rather than a silently wrong move. The EXACT tail stays Python for
    # both sides: FairAgentRs.solve_marginalized is the FAIR marginalized solve, not
    # this harness's clairvoyant exact-K solve, and both sides share the tail
    # identically -- so leaving it Python cannot bias the A/B.
    _mirrors = [p for p in (cand_prefix, champ_prefix) if hasattr(p, "advance")]
    for _m in _mirrors:
        _m.start_game(board)

    t0 = time.perf_counter()
    moves = 0
    game_timed_out = False
    while game.get_game_ended(board, 0) == 0.0:
        # Per-game wall watchdog: abandon (don't wedge the worker) if this single
        # game blows past the budget. Checked between moves — each move is
        # individually bounded — so it fires within one move of the deadline.
        if GAME_WALL_SECS > 0 and (time.perf_counter() - t0) > GAME_WALL_SECS:
            game_timed_out = True
            break
        cur = board.state.current_player
        agent = cand if cur == a_seat else champ
        action = agent.move(board)
        board, _ = game.get_next_state(board, action)
        for _m in _mirrors:
            _m.advance(int(action))          # EVERY applied action, BOTH seats
        moves += 1
    elapsed = time.perf_counter() - t0
    s0, s1 = board.state.scores
    # On a watchdog abandon the board is NON-terminal: scores/diff are partial and
    # MUST NOT be scored as an outcome. game_timeout=True flags it out of every stat.
    diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
    latch_k = cand.latch_k if cand.latch_k is not None else champ.latch_k
    if game_timed_out:
        print(f"[watchdog] seed={seed} a_seat={a_seat} ABANDONED after "
              f"{elapsed:.0f}s / {moves} moves (>{GAME_WALL_SECS:.0f}s); recorded as "
              f"game_timeout", flush=True)
    r = GameResult(
        seed=seed, a_seat=a_seat, cand_sims=_W["cand_sims"], champ_sims=_W["opp_sims"],
        score_p0=int(s0), score_p1=int(s1), diff=int(diff),
        won_by_cand=(diff > 0), drew=(diff == 0), elapsed_s=round(elapsed, 3), moves=moves,
        deck_hash=dh,
        cand_prefix_moves=cand.prefix_moves, cand_exact_moves=cand.exact_moves,
        cand_prefix_secs=round(cand.prefix_secs, 3), cand_solver_secs=round(cand.solver_secs, 3),
        cand_timeouts=cand.n_timeouts,
        champ_prefix_moves=champ.prefix_moves, champ_exact_moves=champ.exact_moves,
        champ_prefix_secs=round(champ.prefix_secs, 3), champ_solver_secs=round(champ.solver_secs, 3),
        champ_timeouts=champ.n_timeouts, latch_k=latch_k, game_timeout=game_timed_out,
        **(_ab_telemetry(cand_prefix) if cand_kind == "ab" else {}),
        **_oracle_telemetry(cand_prefix),
    )
    _save(p, r)
    return r


# --------------------------------------------------------------------------- #
def _paired_z(results):
    """Paired z on per-deck seat-balanced margin (= eval_hybrid_handoff._paired_z /
    ladder_rung_eval)."""
    by_seed = {}
    for r in results:
        by_seed.setdefault(r.seed, {})[r.a_seat] = r.diff
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    if len(ds) < 2:
        return None, None, 0
    mean = sum(ds) / len(ds)
    var = sum((d - mean) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    z = mean / se if se > 0 else float("nan")
    return mean, z, len(ds)


def _summary(results, cand_sims, champ_sims, cand_label=None, opp_label=None):
    # Watchdog-abandoned games carry a partial (non-terminal) board — drop them from
    # every strength stat (win/elo/paired) and report the count separately.
    game_timeouts = sum(1 for r in results if getattr(r, "game_timeout", False))
    results = [r for r in results if not getattr(r, "game_timeout", False)]
    if not results:
        print(f"\n(no completed games to summarize; {game_timeouts} game_timeouts)")
        return {"n": 0, "W": 0, "D": 0, "L": 0, "winrate": float("nan"),
                "winrate_z": float("nan"), "elo": float("nan"),
                "elo_sig_1sigma": float("nan"), "avg_diff": float("nan"),
                "paired_mean_margin": None, "paired_z": None, "n_paired": 0,
                "cand_prefix_ms_per_move": float("nan"),
                "champ_prefix_ms_per_move": float("nan"),
                "cand_latched_games": 0, "solver_secs_per_game": float("nan"),
                "game_timeouts": game_timeouts}
    n = len(results)
    w = sum(1 for r in results if r.won_by_cand)
    d = sum(1 for r in results if r.drew)
    losses = n - w - d
    avg = sum(r.diff for r in results) / n
    wr = (w + 0.5 * d) / n
    wr_se = math.sqrt(0.25 / n)
    wr_z = (wr - 0.5) / wr_se if wr_se > 0 else float("nan")
    if 0 < wr < 1:
        elo = 400.0 * math.log10(wr / (1 - wr))
        elo_sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, elo_sig = math.copysign(800.0, wr - 0.5), float("nan")
    mean_d, z, npair = _paired_z(results)
    cand_latched = sum(1 for r in results if r.cand_exact_moves > 0)
    cand_ms = (sum(r.cand_prefix_secs for r in results) /
               max(1, sum(r.cand_prefix_moves for r in results))) * 1e3
    champ_ms = (sum(r.champ_prefix_secs for r in results) /
                max(1, sum(r.champ_prefix_moves for r in results))) * 1e3
    solver_pergame = sum(r.cand_solver_secs + r.champ_solver_secs for r in results) / n
    print()
    cl = cand_label or f"PUCT-heur-priors(cand s{cand_sims})"
    ol = opp_label or f"champion(heur h{champ_sims})"
    print(f"=== {cl} vs {ol} ===")
    print(f"games: {n}   candidate: {w}W / {d}D / {losses}L   winrate {wr:.3f} (z={wr_z:+.2f})")
    print(f"avg score diff (cand - champ): {avg:+.2f}")
    print(f"ELO: {elo:+.1f}  (+/- {elo_sig:.1f} 1sigma)")
    if mean_d is not None:
        print(f"PAIRED: {npair} decks   mean seat-balanced margin {mean_d:+.2f}   z = {z:+.2f}")
    print(f"prefix ms/move: candidate {cand_ms:.0f}  champion {champ_ms:.0f}  "
          f"(ratio {cand_ms/max(1e-9,champ_ms):.2f}x)")
    print(f"exact endgame: latched {cand_latched}/{n} games, {solver_pergame:.2f}s solver/game, "
          f"timeouts cand={sum(r.cand_timeouts for r in results)} champ={sum(r.champ_timeouts for r in results)}")
    if game_timeouts:
        print(f"game_timeouts: {game_timeouts} game(s) ABANDONED by the wall watchdog "
              f"(>{GAME_WALL_SECS:.0f}s) — excluded from the stats above")
    if abs(elo) <= 35 and not math.isnan(elo_sig):
        print(f"  POWER NOTE: |elo|<=35 at n={n} (1σ≈±{elo_sig:.0f}); a >=35-elo verdict needs n>=400.")
    # C6 ab-candidate depth/TT aggregation (design §8/§9 telemetry into summary.json).
    ab_summary = {}
    ab_games = [r for r in results if getattr(r, "cand_ab_moves", 0) > 0]
    if ab_games:
        med_depths = [r.cand_ab_depth_med for r in ab_games]
        ab_probes = sum(r.cand_ab_tt_probes for r in ab_games)
        ab_summary = {
            "ab_depth_med": float(np.median(med_depths)),
            "ab_depth_p10": float(np.percentile(med_depths, 10)),
            "ab_depth_min": int(min(r.cand_ab_depth_min for r in ab_games)),
            "ab_nodes_per_game": sum(r.cand_ab_nodes for r in ab_games) / len(ab_games),
            "ab_steps_per_move": (sum(r.cand_ab_steps for r in ab_games)
                                  / max(1, sum(r.cand_ab_moves for r in ab_games))),
            "ab_tt_exact_hit_frac": (sum(r.cand_ab_tt_exact_hits for r in ab_games)
                                     / ab_probes) if ab_probes else 0.0,
            "ab_tt_cross_parent_frac": (sum(r.cand_ab_tt_cross_parent_hits for r in ab_games)
                                        / ab_probes) if ab_probes else 0.0,
        }
        print(f"ab telemetry: median depth {ab_summary['ab_depth_med']:.0f} "
              f"(p10 {ab_summary['ab_depth_p10']:.0f}, min {ab_summary['ab_depth_min']}), "
              f"{ab_summary['ab_steps_per_move']:.0f} steps/move, "
              f"cross-parent hit frac {ab_summary['ab_tt_cross_parent_frac']:.4f}")
    # Track-F Gate A oracle-prior cost aggregation (pre-search vs main-search cost per
    # move — the probe's cost accounting for the writeup). Empty for non-oracle cells.
    oracle_summary = {}
    oracle_games = [r for r in results if getattr(r, "oracle_prior_moves", 0) > 0]
    if oracle_games:
        om = sum(r.oracle_prior_moves for r in oracle_games)
        pre_s = sum(r.oracle_presearch_secs for r in oracle_games)
        main_s = sum(r.oracle_mainsearch_secs for r in oracle_games)
        pre_lc = sum(r.oracle_presearch_leaf_calls for r in oracle_games)
        main_lc = sum(r.oracle_mainsearch_leaf_calls for r in oracle_games)
        oracle_summary = {
            "oracle_games": len(oracle_games),
            "oracle_presearch_ms_per_move": (pre_s / max(1, om)) * 1e3,
            "oracle_mainsearch_ms_per_move": (main_s / max(1, om)) * 1e3,
            "oracle_total_ms_per_move": ((pre_s + main_s) / max(1, om)) * 1e3,
            "oracle_leaf_ratio": pre_lc / max(1, main_lc),
            "oracle_cost_multiple": (pre_s + main_s) / max(1e-9, main_s),
        }
        print(f"oracle-prior: {len(oracle_games)} games — pre "
              f"{oracle_summary['oracle_presearch_ms_per_move']:.0f} + main "
              f"{oracle_summary['oracle_mainsearch_ms_per_move']:.0f} ms/move "
              f"(total {oracle_summary['oracle_total_ms_per_move']:.0f}, "
              f"{oracle_summary['oracle_cost_multiple']:.2f}x main-only; "
              f"leaf ratio {oracle_summary['oracle_leaf_ratio']:.2f}x)")
    return {
        "n": n, "W": w, "D": d, "L": losses, "winrate": wr, "winrate_z": wr_z,
        "elo": elo, "elo_sig_1sigma": elo_sig, "avg_diff": avg,
        "paired_mean_margin": mean_d, "paired_z": z, "n_paired": npair,
        "cand_prefix_ms_per_move": cand_ms, "champ_prefix_ms_per_move": champ_ms,
        "cand_latched_games": cand_latched, "solver_secs_per_game": solver_pergame,
        "game_timeouts": game_timeouts,
        **ab_summary,
        **oracle_summary,
    }


def _build_work(seed_start, n, paired):
    if not paired:
        return [(seed_start + i, i % 2) for i in range(n)]
    work = []
    for i in range(n // 2):
        work.append((seed_start + i, 0))
        work.append((seed_start + i, 1))
    return work


def _append_results_csv(csv_path: Path, row: dict):
    header = ["exp_id", "date", "game", "code_rev", "n", "new_ckpt", "new_c", "new_cap",
              "new_var", "new_sims", "old_ckpt", "old_c", "old_cap", "old_var", "old_sims",
              "W", "L", "D", "elo", "sigma", "avg_diff", "src_dir", "confidence", "note"]
    exists = csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=header)
        if not exists:
            wtr.writeheader()
        wtr.writerow({k: row.get(k, "") for k in header})


# --------------------------------------------------------------------------- #
def _smoke(args, cand_kind="puct", opp_kind="heur", opp_sims=None, net_ckpt=None,
           new_mode=False, backend="python") -> int:
    """Single-process plumbing + handoff-fires proof: play 2 paired games, print
    move/handoff counts, assert both sides latched to the exact endgame, exit.
    Honors --candidate/--opponent/--backend; a net: opponent is loaded on CPU (no
    orch). ⚠️ `backend` is honored HERE too (2026-08-02): a smoke that silently ran
    the Python route while `--backend rust` was on deck would preflight the wrong
    plumbing -- and the mirror protocol (start_game/advance on both sides) is exactly
    the plumbing a smoke exists to prove."""
    if opp_sims is None:
        opp_sims = args.champ_sims
    cand_leaf_cfg = _load_cand_leaf_cfg(getattr(args, "cand_leaf_json", None))
    if cand_leaf_cfg is not None:
        _assert_cy_float_path(cand_leaf_cfg)
    cfg = ab_cfg = None
    if cand_kind == "puct":
        cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                                   leaf_quantize=args.leaf_quantize, final_select=args.final_select,
                                   value_norm=args.value_norm,
                                   leaf_cfg=(cand_leaf_cfg if cand_leaf_cfg is not None else DEFAULT_CONFIG),
                                   c_lcb=args.c_lcb, reuse_tree=args.reuse_tree,
                                   root_select=args.root_select, gumbel_m=args.gumbel_m,
                                   gumbel_c_visit=args.gumbel_c_visit,
                                   gumbel_c_scale=args.gumbel_c_scale,
                                   gumbel_retain_g=args.gumbel_retain_g)
    elif cand_kind == "ab":
        ab_cfg = AlphaBetaConfig(
            leaf_cfg=(cand_leaf_cfg if cand_leaf_cfg is not None else DEFAULT_CONFIG),
            step_budget=args.cand_ab_steps, max_depth=args.cand_ab_max_depth,
            asp=args.cand_ab_asp, pvs=not args.cand_ab_no_pvs, tt_cap=args.cand_ab_tt_cap,
            killers=args.cand_ab_killers, lmr=args.cand_ab_lmr, futility=args.cand_ab_futility)
    net = net_dev = net_ns = None
    if opp_kind == "net":
        net, net_dev, net_ns = _load_net_cpu(net_ckpt)
    import random
    _knob_extra = (f" c_lcb={args.c_lcb}" if args.final_select == "lcb" else "") + \
                  (" reuse_tree=ON" if args.reuse_tree else "") + \
                  (f" value_norm={args.value_norm}" if args.value_norm != 15.0 else "") + \
                  (f" root_select=gumbel(m={args.gumbel_m},retain_g={args.gumbel_retain_g})" if args.root_select != "puct" else "")
    if not new_mode:
        print(f"[smoke] cand: c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
              f"select={args.final_select}{_knob_extra} sims={args.cand_sims} | champ h{args.champ_sims} | exact-K={args.exact_k}")
    else:
        if cand_kind == "puct":
            cand_desc = (f"puct c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
                         f"select={args.final_select}{_knob_extra} sims={args.cand_sims}")
        elif cand_kind == "ab":
            cand_desc = (f"ID-alpha-beta steps={args.cand_ab_steps} asp={args.cand_ab_asp:g} "
                         f"pvs={not args.cand_ab_no_pvs} killers={args.cand_ab_killers} "
                         f"lmr={args.cand_ab_lmr}")
        else:
            cand_desc = f"heur h{args.cand_sims}"
        if opp_kind == "heur":
            opp_desc = f"heur h{opp_sims}"
        elif opp_kind == "puct":
            _pin = (f" PINNED(c={CHAMP_PUCT_C_PUCT:g} tau={CHAMP_PUCT_TAU_P:g} "
                    f"quant={CHAMP_PUCT_LEAF_QUANTIZE})" if args.opp_pin_champion else "")
            opp_desc = (f"puct-CHAMPION(select={CHAMP_PUCT_FINAL_SELECT} "
                        f"value_norm={CHAMP_PUCT_VALUE_NORM:g} "
                        f"reuse={'ON' if args.opp_reuse_tree else 'off'}){_pin} sims={opp_sims}")
        else:
            opp_desc = f"net:{net_ckpt}@{NET_SIMS} c{NET_CPUCT} rs{NET_RESIDUAL_SCALE} (CPU, bare)"
        print(f"[smoke] cand: {cand_desc} | opp: {opp_desc} | exact-K={args.exact_k} "
              f"| backend={backend}")
    t0 = time.perf_counter()
    for a_seat in (0, 1):
        seed = args.seed_start
        random.seed(seed)
        game = Game(enable_legal_moves_cache=True)
        board = game.get_init_board()
        if cand_kind == "heur":
            cand_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), args.cand_sims,
                                       seed, DEFAULT_CONFIG)
        elif cand_kind == "ab":
            cand_prefix = _AbPrefix(Game(enable_legal_moves_cache=False), ab_cfg, seed=seed)
        elif getattr(args, "oracle_prior_mult", None):
            cand_prefix = _OraclePriorPrefix(
                Game(enable_legal_moves_cache=True), Game(enable_legal_moves_cache=True),
                cfg, sims=args.cand_sims, mult=args.oracle_prior_mult,
                eps_coef=args.oracle_prior_eps_coef, seed=seed)
        elif backend == "rust":
            cand_prefix = _rust_clairvoyant(cfg, args.cand_sims, seed)
        else:
            cand_prefix = HeuristicPriorAgent(Game(enable_legal_moves_cache=True), cfg,
                                              simulations=args.cand_sims, seed=seed)
        opp_K = args.exact_k
        if opp_kind == "net":
            farm = net_ns > 10
            gf = Game(enable_legal_moves_cache=True, include_farm_scalars=farm)
            from carcassonne_ai.evaluators import make_single_evaluator
            champ_prefix = _NetPrefix(make_single_evaluator(net, net_dev, gf), gf, seed + 1)
            opp_K = 0   # bare net (pinned anchor config)
        elif opp_kind == "puct":
            shared = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                      "leaf_quantize": args.leaf_quantize}
            opp_cfg = _champ_puct_cfg(shared, reuse=args.opp_reuse_tree,
                                      pin_champion=args.opp_pin_champion)
            if backend == "rust":
                champ_prefix = _rust_clairvoyant(opp_cfg, opp_sims, seed + 1)
            else:
                champ_prefix = _PuctPrefix(Game(enable_legal_moves_cache=True), opp_cfg,
                                           opp_sims, seed + 1)
        else:
            champ_prefix = _ChampPrefix(Game(enable_legal_moves_cache=True), opp_sims,
                                        seed + 1, DEFAULT_CONFIG)
        cand = _ExactHandoff(cand_prefix, Game(enable_legal_moves_cache=True), args.exact_k)
        champ = _ExactHandoff(champ_prefix, Game(enable_legal_moves_cache=True), opp_K)
        # Same mirror protocol as _play_one (see the comment there).
        mirrors = [p for p in (cand_prefix, champ_prefix) if hasattr(p, "advance")]
        for m in mirrors:
            m.start_game(board)
        moves = 0
        while game.get_game_ended(board, 0) == 0.0:
            cur = board.state.current_player
            mask = game.get_valid_moves(board)
            agent = cand if cur == a_seat else champ
            act = agent.move(board)
            assert mask[act], f"illegal action {act}"
            board, _ = game.get_next_state(board, act)
            for m in mirrors:
                m.advance(int(act))
            moves += 1
        s0, s1 = board.state.scores
        diff = (s0 - s1) if a_seat == 0 else (s1 - s0)
        print(f"[smoke] a_seat={a_seat}: {s0}-{s1} diff(cand-champ)={diff:+d} moves={moves} | "
              f"cand prefix/exact={cand.prefix_moves}/{cand.exact_moves} latch_k={cand.latch_k} "
              f"solver={cand.solver_secs:.1f}s to={cand.n_timeouts} ; "
              f"champ prefix/exact={champ.prefix_moves}/{champ.exact_moves} latch_k={champ.latch_k} "
              f"solver={champ.solver_secs:.1f}s")
        if args.reuse_tree and cand_kind == "puct":
            hp = cand._prefix  # the HeuristicPriorAgent behind the exact handoff
            print(f"[smoke]   reuse_tree: hits={hp.reuse_hits} fresh={hp.reuse_fresh} "
                  f"collide={hp.reuse_collide}")
            assert hp.reuse_hits + hp.reuse_fresh + hp.reuse_collide == hp.neural_moves, \
                "reuse counters must account for every prefix move"
        if getattr(args, "oracle_prior_mult", None) and cand_kind == "puct":
            op = cand._prefix  # the _OraclePriorPrefix behind the exact handoff
            assert op.oracle_moves > 0, "oracle prefix never played a move"
            assert op.last_reached_root, "oracle prior distribution never reached the root"
            assert op.presearch_leaf_calls > op.mainsearch_leaf_calls, \
                "pre-search must run MORE leaf calls than the main search (mult>1)"
            print(f"[smoke]   oracle-prior mult={args.oracle_prior_mult}: "
                  f"moves={op.oracle_moves} presearch={op.presearch_secs:.1f}s/"
                  f"{op.presearch_leaf_calls} leaves main={op.mainsearch_secs:.1f}s/"
                  f"{op.mainsearch_leaf_calls} leaves "
                  f"(leaf ratio {op.presearch_leaf_calls/max(1,op.mainsearch_leaf_calls):.2f}x)")
        if args.exact_k > 0:
            assert cand.exact_moves > 0, "candidate never reached the exact endgame (K too small?)"
        if opp_K > 0:
            assert champ.exact_moves > 0, "champion never reached the exact endgame"
        assert cand.prefix_moves > 0 and champ.prefix_moves > 0, "prefix search never ran (K too big?)"
    print(f"[smoke] OK — plumbing + exact handoff verified ({time.perf_counter()-t0:.1f}s for 2 games)")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="eval_puct_priors")
    ap.add_argument("--c-puct", type=float, default=1.5)
    ap.add_argument("--tau-p", type=float, default=5.0)
    ap.add_argument("--leaf-quantize", choices=("int", "float"), default="float")
    ap.add_argument("--final-select", choices=("Q", "visits", "lcb"), default="Q")
    ap.add_argument("--c-lcb", type=float, default=1.0,
                    help="LCB exploration penalty coefficient; ONLY used with "
                         "--final-select lcb: score(a)=Q(a)-c_lcb*sqrt(ln(ΣN)/N(a)) "
                         "(default 1.0)")
    ap.add_argument("--value-norm", type=float, default=15.0)
    ap.add_argument("--reuse-tree", action="store_true",
                    help="candidate persists+re-roots the PUCT tree across moves "
                         "(keeps the played subtree's statistics; falls back to a "
                         "fresh search when the next board isn't in the retained "
                         "tree or on a rotation-key collision). Default OFF "
                         "(byte-for-byte the champion).")
    ap.add_argument("--root-select", choices=("puct", "gumbel"), default="puct",
                    help="candidate root-action selection: 'puct' (default; the "
                         "champion path) or 'gumbel' (Gumbel-root / sequential-halving, "
                         "Track C1). Gumbel overrides --final-select.")
    ap.add_argument("--gumbel-m", type=int, default=16,
                    help="Gumbel top-m candidate count (clamped to n_legal); "
                         "ONLY used with --root-select gumbel. Default 16.")
    ap.add_argument("--gumbel-c-visit", type=float, default=50.0,
                    help="Gumbel σ-transform visit constant (mctx default 50).")
    ap.add_argument("--gumbel-c-scale", type=float, default=1.0,
                    help="Gumbel σ-transform value scale (mctx default 1.0).")
    ap.add_argument("--gumbel-retain-g", action=argparse.BooleanOptionalAction, default=True,
                    help="retain the Gumbel noise g through sequential-halving "
                         "elimination (--gumbel-retain-g, default = paper-exact / "
                         "Danihelka 2022) vs use g only for the initial top-m draw "
                         "(--no-gumbel-retain-g). ONLY used with --root-select gumbel.")
    ap.add_argument("--cand-sims", type=int, default=None,
                    help="candidate PUCT sims (from the equal-time bench match); required "
                         "for --candidate puct, ignored for --candidate h<sims>")
    ap.add_argument("--champ-sims", type=int, default=None,
                    help="champion/opponent sims (default 6400 for a heur opponent). "
                         "MANDATORY for --candidate ab --opponent puct (the ab child-step "
                         "budget has no sims axis, so the champion budget is set here).")
    ap.add_argument("--oracle-prior-mult", type=int, default=None,
                    help="Track-F Gate A oracle-prior probe (CANDIDATE side, --candidate "
                         "puct only). When set to N, each candidate root move first runs a "
                         "PRE-SEARCH with the IDENTICAL champion config at N x --cand-sims on "
                         "a FRESH tree, converts its root VISIT distribution to a prior, and "
                         "runs the normal --cand-sims search with the ROOT priors REPLACED by "
                         "it (DEEPER node priors stay the heuristic evaluator's — this measures "
                         "ROOT-prior production-depth headroom, the dominant prior effect). The "
                         "pre-search tree is NOT reused into the main search (isolates priors "
                         "from depth). Default None = OFF = byte-identical to the plain champion. "
                         "Requires reuse_tree OFF.")
    ap.add_argument("--oracle-prior-eps-coef", type=float, default=1e-3,
                    help="epsilon-floor coefficient for --oracle-prior-mult: each root move's "
                         "per-group prior is floored at eps = coef / n_groups (a 1e-3/n_actions "
                         "-style floor keeping PUCT exploration of pre-search-unvisited moves "
                         "alive), then renormalized. Default 1e-3. Ignored unless "
                         "--oracle-prior-mult is set.")
    ap.add_argument("--cand-leaf-json", type=str, default=None,
                    help="override ONLY the CANDIDATE side's leaf LeafConfig — inline "
                         "JSON (a '{...}' object of field->value, replace-fields on the "
                         "env DEFAULT_CONFIG) or a path to such a JSON file. The champion/"
                         "opponent side always keeps env DEFAULT_CONFIG (v2.9 Bmild_cap8). "
                         "Absent -> byte-identical to today (all new paths default-OFF). "
                         "closure_p keys are coerced to int, v29_meeple_curve to a tuple "
                         "(null -> curve OFF). e.g. '{\"bonus_cap\": 5, \"opp_bonus_cap\": 5}'. "
                         "The candidate must stay on the Cython float leaf (curve-only or "
                         "curve-None, bag_close ok); object-forcing terms are rejected.")
    ap.add_argument("--candidate", type=str, default="puct",
                    help="candidate side: 'puct' (default; PUCT-heur-priors @ --cand-sims) or "
                         "'h<sims>' (plain HeuristicMCTS @ <sims>, same v2.9 leaf + exact-K "
                         "handoff as the champion side; puct flags ignored/recorded null)")
    ap.add_argument("--opponent", type=str, default=None,
                    help="opponent side (default: h<champ-sims>, the legacy champion). "
                         "'h<sims>' = HeuristicMCTS @ <sims> (+ exact-K handoff). "
                         "'puct' = the flag-OFF CHAMPION PUCT-heur-priors sibling of the "
                         f"candidate (select={CHAMP_PUCT_FINAL_SELECT}, value_norm="
                         f"{CHAMP_PUCT_VALUE_NORM:g}, reuse off; shares c_puct/tau_p/"
                         "leaf-quantize/cand-sims; + same exact-K handoff) — use this for a "
                         "variant-ON-vs-variant-OFF A/B. "
                         "'net:<ckpt.pt>' = NeuralMCTS opponent pinned to the rod_v2 anchor "
                         f"config (sims={NET_SIMS}, c_puct={NET_CPUCT}, v2.9 leaf + residual "
                         f"{NET_RESIDUAL_SCALE}, bare/no exact tail); net-on-CPU unless "
                         "--shm-eval-server is given")
    ap.add_argument("--shm-eval-server", type=str, default=None,
                    help="carc-orch SHM orchestrator name for the net: opponent (workers "
                         "attach to /dev/shm/carc_<NAME>); omit for net-on-CPU per worker")
    # --- C6 ID-alpha-beta candidate knobs (--candidate ab; design §6/§8) -------- #
    ap.add_argument("--cand-ab-steps", type=int, default=None,
                    help="child-step (get_next_state) budget per DECISION for the ab "
                         "candidate — the equal-wall-clock normalizer (calibrated Stage 0). "
                         "REQUIRED with --candidate ab.")
    ap.add_argument("--cand-ab-max-depth", type=int, default=64,
                    help="ab ID ply safety cap (the budget binds first; default 64)")
    ap.add_argument("--cand-ab-tt-cap", type=int, default=2_000_000,
                    help="ab transposition-table entry cap (freeze-at-cap; default 2e6)")
    ap.add_argument("--cand-ab-asp", type=float, default=3.0,
                    help="ab aspiration half-width in points (0 = off; default 3.0)")
    ap.add_argument("--cand-ab-no-pvs", action="store_true",
                    help="ab: disable principal-variation search (value-preserving ablation)")
    ap.add_argument("--cand-ab-killers", type=int, default=2,
                    help="ab killer slots per ply level (0 = off; default 2)")
    ap.add_argument("--cand-ab-lmr", action="store_true",
                    help="ab: enable late-move reductions (move-changing; default OFF)")
    ap.add_argument("--cand-ab-futility", type=float, default=0.0,
                    help="ab frontier futility margin in points (0 = off; default OFF)")
    ap.add_argument("--opp-pin-champion", action="store_true",
                    help="T3 JOINT-SWEEP shared-axis fix (default OFF = byte-identical legacy). "
                         "Requires --opponent puct. When set, the champion PUCT sibling takes the "
                         "champion CONSTANTS c_puct=%(default_cpuct)s/tau_p=%(default_taup)s/"
                         "leaf_quantize=%(default_quant)s instead of copying the candidate's "
                         "shared axes — so a sweep of --c-puct/--tau-p isolates the candidate "
                         "side (OPTUNA_KNOB_SWEEP_DESIGN.md §3). value_norm/final_select/reuse are "
                         "already pinned; opponent sims stays = cand sims." % {
                             "default_cpuct": CHAMP_PUCT_C_PUCT,
                             "default_taup": CHAMP_PUCT_TAU_P,
                             "default_quant": CHAMP_PUCT_LEAF_QUANTIZE})
    ap.add_argument("--opp-reuse-tree", action="store_true",
                    help="let the --opponent puct sibling run reuse_tree=True (the "
                         "champion OF RECORD; C6 Stage-2 confirm). Default OFF = the "
                         "flag-OFF sibling used by the Stage-1 screen (byte-for-byte today).")
    ap.add_argument("--exact-k", type=int, default=4, help="exact clairvoyant endgame handoff at k_remaining<=K")
    # --- ENGINE (rustport P6, wired 2026-08-02) ---
    ap.add_argument("--backend", choices=("python", "rust", "auto"), default="python",
                    help="which ENGINE runs the CLAIRVOYANT PUCT prefixes -- BOTH "
                         "sides since 2026-08-02 (the candidate, and the --opponent "
                         "puct champion sibling). `python` (default) is "
                         "byte-identical to every row already on record. `rust` runs "
                         "rust_agent.RustClairvoyantAgent over "
                         "MirrorState.search_single -- gated bit-exact against "
                         "HeuristicPriorAgent (chosen action + root N/W + every root "
                         "child edge, raw f64 bits) by "
                         "scripts/rustport/gate_clairvoyant.py (candidate knobs) and "
                         "scripts/rustport/gate_clairvoyant_opponent.py (champion "
                         "flag-OFF knobs). ⚠️ THIS IS AN INSTRUMENT: converting a "
                         "ruler changes the ruler, so cite those gates before "
                         "comparing a rust-leg row to a python-leg one. What does NOT "
                         "convert: the h<sims> HeuristicMCTS opponent (frozen ruler, "
                         "no Rust port), the ab and oracle-prior candidates, every "
                         "net arm, --opp-reuse-tree (all of which FAIL CLOSED with an "
                         "argparse error rather than silently staying Python), and "
                         "the exact-K clairvoyant tail, which stays Python on BOTH "
                         "sides and therefore caps the realised cell speedup.")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--games", type=int, default=None, help="alias for --n (convenience)")
    ap.add_argument("--paired", action="store_true")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed-start", type=int, default=9_000_000_000)
    ap.add_argument("--allow-selfplay-seeds", action="store_true")
    ap.add_argument("--out-root", type=str, default=None)
    ap.add_argument("--out-subdir", type=str, default=None)
    ap.add_argument("--shared-claim", action="store_true")
    ap.add_argument("--claim-stale-secs", type=int, default=5400)
    ap.add_argument("--claim-host", type=str, default=socket.gethostname())
    ap.add_argument("--summary-only", action="store_true")
    ap.add_argument("--no-results-csv", action="store_true")
    ap.add_argument("--exp-id", type=str, default=None,
                    help="override the results.csv exp_id (default: the auto cell tag, "
                         "incl. any -leaf<hash8> suffix). Use for PRE-REGISTERED ids — "
                         "e.g. the C5 leaf-retune cells c5_*_vs_puctchamp2750_k2 "
                         "(measurement/classical_search/C5_LEAF_RETUNE_DESIGN.md). Also "
                         "recorded in the manifest; no effect on out-dir naming "
                         "(--out-subdir owns that) or on play.")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    if args.games is not None:
        args.n = args.games
    if args.paired and args.n % 2 != 0:
        ap.error("--paired requires an even --n")

    try:
        cand_kind, opp_kind, opp_sims, net_ckpt, new_mode = _resolve_specs(args)
    except ValueError as e:
        ap.error(str(e))
    # ENGINE (rustport P6). Resolved ONCE so workers and manifest cannot disagree.
    from carcassonne_ai import champion_factory as _CF

    _backend = str(args.backend)
    if _backend == "auto":
        _backend = str(_CF.load_production_spec().backend)
    if _backend not in _CF.KNOWN_BACKENDS:
        ap.error(f"--backend must be one of {sorted(_CF.KNOWN_BACKENDS)} or 'auto'; "
                 f"got {args.backend!r}")
    if _backend == "rust":
        # Only the plain PUCT candidate has a Rust route. The ab candidate is a dead
        # C6 lever with no port, the oracle-prior candidate is a python-only overlay
        # (it presearches with the true deck), and every net arm needs an evaluator
        # carc_rs does not have. Fail closed rather than silently staying Python on a
        # run whose manifest would then say "rust".
        if cand_kind != "puct":
            ap.error(f"--backend rust supports the puct candidate only; got "
                     f"--candidate {args.candidate} (kind={cand_kind})")
        if args.oracle_prior_mult:
            ap.error("--oracle-prior-mult is a python-only search overlay; "
                     "run it with --backend python")
        # --- OPPONENT side (wired 2026-08-02) ------------------------------------
        # The --opponent puct sibling converts (it is the same clairvoyant single-tree
        # search at the champion's flag-OFF knobs). Everything the Rust surface cannot
        # express fails CLOSED here rather than silently staying Python under a
        # manifest that says "rust".
        if opp_kind == "net":
            ap.error("--backend rust cannot run a net opponent: the Rust core carries "
                     "no evaluator (Gap 3 of BACKEND_BYPASS_AUDIT_20260801 §3), so the "
                     "opponent would silently stay Python. Run the net arms with "
                     "--backend python.")
        if args.opp_reuse_tree:
            ap.error("--opp-reuse-tree has no carc_rs implementation "
                     "(MirrorState.search_single is FRESH-TREE only -- Gap 2 of "
                     "BACKEND_BYPASS_AUDIT_20260801 §3). The Stage-2 confirm vs the "
                     "champion OF RECORD must run with --backend python.")
        # --opp-pin-champion is EXPRESSIBLE and therefore allowed: it only swaps the
        # shared c_puct/tau_p/leaf_quantize axes for the champion constants, all three
        # of which SearchConfigRs carries. No refusal needed.
    if args.shm_eval_server and opp_kind != "net":
        ap.error("--shm-eval-server requires --opponent net:<ckpt.pt>")
    if cand_kind == "ab" and (args.cand_ab_steps is None or args.cand_ab_steps <= 0):
        ap.error("--cand-ab-steps INT (>0) is required for --candidate ab")
    if args.opp_reuse_tree and opp_kind != "puct":
        ap.error("--opp-reuse-tree only applies to --opponent puct")
    if args.opp_pin_champion and opp_kind != "puct":
        ap.error("--opp-pin-champion only applies to --opponent puct")
    if args.oracle_prior_mult is not None:
        if cand_kind != "puct":
            ap.error("--oracle-prior-mult requires --candidate puct")
        if args.oracle_prior_mult < 2:
            ap.error("--oracle-prior-mult must be >= 2 (a pre-search LARGER than production)")
        if args.reuse_tree:
            ap.error("--oracle-prior-mult requires reuse_tree OFF (drop --reuse-tree); a "
                     "reused root would conflate deeper search with the injected priors")
        if args.root_select != "puct":
            ap.error("--oracle-prior-mult requires --root-select puct (the champion root)")

    # candidate-side leaf override (--cand-leaf-json). None -> DEFAULT_CONFIG both
    # sides (byte-identical to today). The champion/opponent side NEVER takes it.
    try:
        cand_leaf_cfg = _load_cand_leaf_cfg(args.cand_leaf_json)
        if cand_leaf_cfg is not None:
            _assert_cy_float_path(cand_leaf_cfg)
    except ValueError as e:
        ap.error(str(e))                       # messages already carry the flag name
    except (OSError, json.JSONDecodeError) as e:
        ap.error(f"--cand-leaf-json: {e}")

    if args.smoke:
        return _smoke(args, cand_kind, opp_kind, opp_sims, net_ckpt, new_mode,
                      backend=_backend)

    if not args.summary_only and not args.allow_selfplay_seeds:
        ep.assert_clean_eval_seed_range(args.seed_start, args.n)

    net_meta = net_sha = None
    if opp_kind == "net" and not args.summary_only:
        if not Path(net_ckpt).is_file():
            ap.error(f"net opponent checkpoint not found: {net_ckpt}")
        net_meta = _read_ckpt_meta(net_ckpt)
        net_sha = _file_sha256(net_ckpt)

    cfg = HeuristicPriorConfig(c_puct=args.c_puct, tau_p=args.tau_p,
                               leaf_quantize=args.leaf_quantize, final_select=args.final_select,
                               value_norm=args.value_norm,
                               leaf_cfg=(cand_leaf_cfg if cand_leaf_cfg is not None else DEFAULT_CONFIG),
                               c_lcb=args.c_lcb, reuse_tree=args.reuse_tree,
                               root_select=args.root_select, gumbel_m=args.gumbel_m,
                               gumbel_c_visit=args.gumbel_c_visit,
                               gumbel_c_scale=args.gumbel_c_scale,
                               gumbel_retain_g=args.gumbel_retain_g)
    cand_cfg_dict = {"c_puct": args.c_puct, "tau_p": args.tau_p,
                     "leaf_quantize": args.leaf_quantize, "final_select": args.final_select,
                     "value_norm": args.value_norm,
                     "c_lcb": args.c_lcb, "reuse_tree": args.reuse_tree,
                     "root_select": args.root_select, "gumbel_m": args.gumbel_m,
                     "gumbel_c_visit": args.gumbel_c_visit,
                     "gumbel_c_scale": args.gumbel_c_scale,
                     "gumbel_retain_g": args.gumbel_retain_g}
    # C6 ID-alpha-beta candidate config (None unless --candidate ab). The leaf is the
    # candidate override or env DEFAULT_CONFIG (curve125) — same as the champion side.
    ab_cfg_dict = ab_cfg = None
    if cand_kind == "ab":
        ab_cfg_dict = {"step_budget": args.cand_ab_steps, "max_depth": args.cand_ab_max_depth,
                       "asp": args.cand_ab_asp, "pvs": not args.cand_ab_no_pvs,
                       "tt_cap": args.cand_ab_tt_cap, "killers": args.cand_ab_killers,
                       "lmr": args.cand_ab_lmr, "futility": args.cand_ab_futility}
        ab_cfg = AlphaBetaConfig(
            leaf_cfg=(cand_leaf_cfg if cand_leaf_cfg is not None else DEFAULT_CONFIG),
            **ab_cfg_dict)

    tag = _cell_tag(args, cand_kind, opp_kind, opp_sims, net_ckpt, new_mode)
    if cand_leaf_cfg is not None:
        # a leaf A/B: keep the auto exp_id / default out-dir distinct per candidate
        # leaf so cells never silently share a directory (Trap 1). An explicit
        # --out-subdir (the Stage-1 launcher path) still owns the on-disk dir name.
        tag = f"{tag}-leaf{_leaf_hash(cand_leaf_cfg)[:8]}"
    sub = args.out_subdir or tag
    root = Path(args.out_root) if args.out_root else EVAL_ROOT
    out = root / sub
    out.mkdir(parents=True, exist_ok=True)

    tasks = [(str(out), seed, a_seat)
             for seed, a_seat in _build_work(args.seed_start, args.n, args.paired)]

    # summary labels: legacy None -> byte-identical header; rr cells name both sides.
    cand_label = opp_label = None
    if new_mode:
        if cand_kind == "puct":
            cand_label = f"PUCT-heur-priors(cand s{args.cand_sims}{_variant_sig(args)})"
        elif cand_kind == "ab":
            cand_label = f"ID-alpha-beta(cand ab{args.cand_ab_steps}{_ab_variant_sig(args)})"
        else:
            cand_label = f"candidate(heur h{args.cand_sims})"
        if opp_kind == "heur":
            opp_label = f"opponent(heur h{opp_sims})"
        elif opp_kind == "puct":
            opp_label = (f"opponent(PUCT-champion{' reuse' if args.opp_reuse_tree else ' flags-OFF'}"
                         f" s{opp_sims})")
        else:
            opp_label = f"opponent(net:{Path(net_ckpt).stem}@{NET_SIMS})"

    if args.summary_only:
        results = [r for t in tasks if (r := _try_load(_result_path(out, t[1], t[2]))) is not None]
        if results:
            summ = _summary(results, args.cand_sims, args.champ_sims, cand_label, opp_label)
            json.dump(summ, open(out / "summary.json", "w"), indent=2)
        else:
            print("no cached results yet")
        return 0

    leaf_cfg = cfg.resolved_leaf_cfg()          # candidate side (override or DEFAULT_CONFIG)
    champ_leaf_cfg = DEFAULT_CONFIG             # champion/opponent side is ALWAYS env default
    man_cfg = {"candidate": cfg.as_manifest(),
               "cand_sims": args.cand_sims, "champ_sims": args.champ_sims,
               "champion": {"agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                            "c": CHAMP_C, "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)"},
               "exact_k": args.exact_k, "exact_mode": "clairvoyant",
               "exact_budget": EXACT_BUDGET,
               "game_wall_secs": GAME_WALL_SECS,
               "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
               "exp_id": args.exp_id or tag,
               "n": args.n, "paired": args.paired, "seed_start": args.seed_start,
               "leaf_hash": _leaf_hash(leaf_cfg), "code_rev": code_rev(),
               # C5 S0 per-side leaf provenance (Trap 1: a worker missing the env
               # exports silently runs the wrong leaf — the per-side leaf_hash is the
               # mitigation). cand_leaf_json is the raw override spec (None if absent).
               "cand_leaf_json": args.cand_leaf_json,
               "cand_leaf_cfg": _leaf_dict(leaf_cfg),
               "cand_leaf_hash": _leaf_hash(leaf_cfg),
               "champ_leaf_cfg": _leaf_dict(champ_leaf_cfg),
               "champ_leaf_hash": _leaf_hash(champ_leaf_cfg),
               "env": {k: os.environ.get(k) for k in _CANON_ENV}}
    # Track-F Gate A oracle-prior provenance — added ONLY when the probe is ON, so
    # a plain (OFF) manifest stays byte-identical to the pre-change harness output.
    oracle_block = None
    if args.oracle_prior_mult is not None:
        oracle_block = {
            "oracle_prior_mult": args.oracle_prior_mult,
            "presearch_sims": args.cand_sims * args.oracle_prior_mult,
            "main_sims": args.cand_sims,
            "eps_coef": args.oracle_prior_eps_coef,
            "scope": "ROOT priors only (deeper node priors = heuristic evaluator); "
                     "pre-search tree NOT reused into the main search",
            "applies_to": "candidate",
        }
        man_cfg["oracle_prior"] = oracle_block
    # ENGINE provenance (rustport P6). Recorded for EVERY cell, legacy or round-robin
    # (it moved out of the new_mode branch 2026-08-02 — a legacy `--backend rust` cell
    # used to record nothing at all). PER SIDE, because the two sides convert
    # independently: the clairvoyant PUCT search converts on either side, the h<sims>
    # HeuristicMCTS opponent and every net arm do not.
    _cand_engine = _backend if cand_kind == "puct" and not args.oracle_prior_mult \
        else "python"
    _opp_engine = _backend if opp_kind == "puct" else "python"
    man_cfg["backend"] = {
        "name": _backend,
        "default": "python",
        "candidate_engine": _cand_engine,
        "opponent_engine": _opp_engine,
        "applies_to": "the CLAIRVOYANT PUCT search on either side "
                      "(RustClairvoyantAgent over MirrorState.search_single)",
        "unconverted": "the h<sims> HeuristicMCTS opponent (frozen ruler, no Rust "
                       "port), every net arm (Gap 3: the Rust core carries no "
                       "evaluator), and the exact-K clairvoyant tail on BOTH sides "
                       "(carc_rs exposes only FairAgentRs.solve_marginalized, the "
                       "FAIR marginalized solve, not this harness's true-deck "
                       "clairvoyant solve) stay Python. The tail is shared "
                       "identically by both sides, so leaving it Python cannot bias "
                       "the A/B -- it only caps the realised speedup.",
        "candidate_agent_class": ("RustClairvoyantAgent" if _cand_engine == "rust"
                                  else "HeuristicPriorAgent"),
        "opponent_agent_class": ("RustClairvoyantAgent" if _opp_engine == "rust"
                                 else "HeuristicPriorAgent" if opp_kind == "puct"
                                 else "HeuristicMCTS" if opp_kind == "heur"
                                 else "NeuralMCTS"),
        "identity_gate": "measurement/rustport_p6/GATE_CLAIRVOYANT.json",
        "opponent_identity_gate":
            "measurement/rustport_p6/GATE_CLAIRVOYANT_OPPONENT.json",
        "wiring_gate": "measurement/rustport_p6/G6_eval_puct_priors_wiring.json",
        "seed_gate": "measurement/rustport_p6/GAP1_SEED_INVARIANCE.json",
        "instrument_warning": "this harness is a RULER (both sides clairvoyant by "
                              "design); converting an instrument changes the "
                              "instrument -- cite the identity gate before "
                              "comparing a rust-leg row to a python-leg one",
    }
    if new_mode:
        # Round-robin cell: resolved candidate + opponent specs (ROUND_ROBIN_PLAN.md).
        if cand_kind == "puct":
            cand_block = {"kind": "puct", "agent": "HeuristicPriorAgent",
                          "sims": args.cand_sims, "exact_k": args.exact_k,
                          **cfg.as_manifest()}
            if oracle_block is not None:
                cand_block["agent"] = "OraclePriorPrefix(HeuristicPriorAgent)"
                cand_block["oracle_prior"] = oracle_block
        elif cand_kind == "ab":
            # C6 ID-alpha-beta candidate: the FULL resolved AlphaBetaConfig + leaf_hash
            # (design §8; per-side leaf_hash is the Trap-1 wrong-leaf mitigation).
            cand_block = {"kind": "ab", "agent": "AlphaBetaAgent",
                          "step_budget": args.cand_ab_steps, "exact_k": args.exact_k,
                          **ab_cfg.as_manifest()}
        else:
            # puct-specific knobs ignored for an h<sims> candidate -> recorded as null.
            cand_block = {"kind": "heur", "agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                          "c": CHAMP_C, "sims": args.cand_sims,
                          "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)",
                          "exact_k": args.exact_k,
                          "c_puct": None, "tau_p": None, "leaf_quantize": None,
                          "final_select": None, "value_norm": None}
        if opp_kind == "heur":
            opp_block = {"kind": "heur", "agent": "HeuristicMCTS", "heur_leaf": "v2_7",
                         "c": CHAMP_C, "sims": opp_sims,
                         "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG)",
                         "exact_k": args.exact_k}
        elif opp_kind == "puct":
            # flag-OFF champion PUCT sibling (shares c_puct/tau_p/leaf_quantize; variant
            # knobs forced to champion). --opp-reuse-tree -> the champion OF RECORD
            # (reuse_tree=True, CL-044) for the C6 Stage-2 confirm.
            opp_block = {"kind": "puct", "agent": "HeuristicPriorAgent",
                         "role": ("champion of record (reuse_tree ON)"
                                  if args.opp_reuse_tree else "champion (variant flags OFF)"),
                         "sims": opp_sims, "exact_k": args.exact_k,
                         "reuse_tree": bool(args.opp_reuse_tree),
                         # T3 --opp-pin-champion (§3/§5a): whether the shared c/τ/quant axes
                         # were pinned to the champion constants (True) or copied from the
                         # candidate (False = legacy shared-axis leak). The as_manifest() below
                         # already reflects the RESOLVED (pinned or leaked) c_puct/tau_p.
                         "pinned_champion_knobs": bool(args.opp_pin_champion),
                         "pinned_c_puct": (CHAMP_PUCT_C_PUCT if args.opp_pin_champion else None),
                         "pinned_tau_p": (CHAMP_PUCT_TAU_P if args.opp_pin_champion else None),
                         "pinned_leaf_quantize": (CHAMP_PUCT_LEAF_QUANTIZE
                                                  if args.opp_pin_champion else None),
                         **_champ_puct_cfg(cand_cfg_dict, reuse=args.opp_reuse_tree,
                                           pin_champion=args.opp_pin_champion).as_manifest()}
        else:
            opp_block = {"kind": "net", "agent": "NeuralMCTS",
                         "ckpt": str(net_ckpt), "ckpt_sha256": net_sha,
                         "sims": NET_SIMS, "c_puct": NET_CPUCT,
                         "residual_scale": NET_RESIDUAL_SCALE, "meeple_k": NET_MEEPLE_K,
                         "leaf": "v2.9 Bmild_cap8 (DEFAULT_CONFIG) + net value residual "
                                 "(make_v25_value_wrapper)",
                         "exact_k": 0,   # bare prefix: NO exact tail (anchor rows were bare)
                         "include_farm_scalars": net_meta["n_scalar_features"] > 10,
                         "orch_shm": args.shm_eval_server,
                         "net_n_ch": NET_N_CH,
                         "pinned_from": "scripts/level2/eval_hybrid_handoff.py ITER8_SIMS/"
                                        "ITER8_CPUCT/ITER8_RESIDUAL_SCALE (rod_v2 anchor "
                                        "harness; results.csv rodv2_iter02_vs_heur*_v29_n200)",
                         **net_meta}
        man_cfg.update({"rr_cell": tag,
                        "candidate_spec": args.candidate,
                        "opponent_spec": args.opponent or f"h{args.champ_sims}",
                        "candidate": cand_block,
                        "opponent": opp_block,
                        "champ_sims": opp_sims})
        del man_cfg["champion"]   # replaced by the resolved "opponent" block
    write_manifest(out, kind="eval_puct_priors", game=game_tag(Game()),
                   config=man_cfg, overwrite=True)

    todo = [t for t in tasks if not _result_path(out, t[1], t[2]).exists()]
    workers = args.workers or min(os.cpu_count() or 1, len(todo) or 1)
    print(f"puct-priors[{tag}]: n={args.n} paired={args.paired} | "
          f"{len(tasks)-len(todo)} cached, {len(todo)} to play, {workers} workers, out={out}")
    sys.stdout.flush()

    results = []
    if todo:
        t0 = time.perf_counter()
        id_q = None
        if args.shm_eval_server:
            from multiprocessing import Queue
            id_q = Queue()
            for w in range(workers):
                id_q.put(w)
            print(f"  [orch] SHM eval-server '{args.shm_eval_server}': {workers} CPU workers "
                  f"attach to /dev/shm/carc_{args.shm_eval_server} "
                  f"(n_scalar={net_meta['n_scalar_features']})", flush=True)
        with Pool(processes=workers, initializer=_worker_init,
                  initargs=(cand_cfg_dict, args.cand_sims, args.champ_sims, args.exact_k,
                            args.shared_claim, args.claim_host, args.claim_stale_secs,
                            cand_kind, opp_kind, opp_sims, net_ckpt or "",
                            (net_meta or {}).get("n_scalar_features", 10),
                            args.shm_eval_server or "", id_q, cand_leaf_cfg,
                            ab_cfg_dict, args.opp_reuse_tree,
                            args.opp_pin_champion, args.oracle_prior_mult,
                            args.oracle_prior_eps_coef, _backend)) as pool:
            done = 0
            for r in pool.imap_unordered(_play_one, todo, chunksize=1):
                if r is None:
                    continue
                results.append(r)
                done += 1
                if done % 10 == 0 or done == len(todo):
                    el = time.perf_counter() - t0
                    print(f"  {done}/{len(todo)} played ({el/done:.1f}s/game, "
                          f"~{(len(todo)-done)*el/done/60:.0f} min left)", flush=True)
    for t in tasks:
        p = _result_path(out, t[1], t[2])
        if p.exists() and not any(r.seed == t[1] and r.a_seat == t[2] for r in results):
            c = _try_load(p)
            if c:
                results.append(c)

    if not results:
        print("no results")
        return 0
    summ = _summary(results, args.cand_sims, args.champ_sims, cand_label, opp_label)
    json.dump(summ, open(out / "summary.json", "w"), indent=2)

    if not args.no_results_csv:
        if not new_mode:
            note = (f"Phase 1.1 PUCT-heur-priors vs champion (search-only, both exact-K<={args.exact_k}). "
                    f"c_puct={args.c_puct} tau_p={args.tau_p} quant={args.leaf_quantize} "
                    f"select={args.final_select}. cand ms/move {summ['cand_prefix_ms_per_move']:.0f} "
                    f"vs champ {summ['champ_prefix_ms_per_move']:.0f}. paired_z={summ['paired_z']}.")
            row = {
                "new_ckpt": f"puct_prior_{args.leaf_quantize}_{args.final_select}",
                "new_c": args.c_puct, "new_var": "puct_heur_prior",
                "old_ckpt": "heur_h6400_champion", "old_c": CHAMP_C,
                "old_var": "v2_9_champion", "old_sims": args.champ_sims,
            }
        else:
            if cand_kind == "puct":
                cand_desc = (f"PUCT-heur-priors(c_puct={args.c_puct} tau_p={args.tau_p} "
                             f"quant={args.leaf_quantize} select={args.final_select}"
                             f"{_variant_sig(args)} s{args.cand_sims})")
            elif cand_kind == "ab":
                cand_desc = (f"ID-alpha-beta(steps={args.cand_ab_steps} "
                             f"max_depth={args.cand_ab_max_depth} asp={args.cand_ab_asp:g} "
                             f"pvs={not args.cand_ab_no_pvs} killers={args.cand_ab_killers} "
                             f"lmr={args.cand_ab_lmr} futility={args.cand_ab_futility:g}"
                             f"{_ab_variant_sig(args)})")
            else:
                cand_desc = f"HeuristicMCTS h{args.cand_sims}"
            if opp_kind == "heur":
                opp_desc = f"HeuristicMCTS h{opp_sims} (exact-K<={args.exact_k})"
            elif opp_kind == "puct":
                opp_desc = (f"PUCT-heur-priors CHAMPION "
                            f"(select={CHAMP_PUCT_FINAL_SELECT} value_norm={CHAMP_PUCT_VALUE_NORM:g} "
                            f"reuse={'ON' if args.opp_reuse_tree else 'off'}) s{opp_sims} "
                            f"(exact-K<={args.exact_k})")
            else:
                opp_desc = (f"NeuralMCTS {Path(net_ckpt).stem}@{NET_SIMS} c{NET_CPUCT} "
                            f"rs{NET_RESIDUAL_SCALE} (bare, rod_v2 anchor cfg"
                            f"{', orch ' + args.shm_eval_server if args.shm_eval_server else ', net-on-CPU'})")
            head = (f"pre-registered cell {args.exp_id} [auto tag {tag}]" if args.exp_id
                    else f"Phase 1.1b transitivity round-robin cell {tag} "
                         f"(measurement/classical_search/ROUND_ROBIN_PLAN.md)")
            note = (f"{head}: candidate {cand_desc} "
                    f"exact-K<={args.exact_k} vs opponent {opp_desc}. "
                    f"cand ms/move {summ['cand_prefix_ms_per_move']:.0f} vs opp "
                    f"{summ['champ_prefix_ms_per_move']:.0f}. paired_z={summ['paired_z']}.")
            if opp_kind == "heur":
                old_ckpt, old_c, old_var = f"heur_h{opp_sims}", CHAMP_C, "v2_9_champion"
            elif opp_kind == "puct":
                # for the ab candidate the opponent variant sig is only reuse (the PUCT
                # _variant_sig reflects the candidate's PUCT knobs, meaningless for ab).
                reuse_sig = "_reuse" if args.opp_reuse_tree else ""
                old_ckpt = (f"puct_prior_champion{reuse_sig}" if cand_kind == "ab"
                            else f"puct_prior_champion{_variant_sig(args)}{reuse_sig}")
                old_c, old_var = args.c_puct, "puct_heur_prior_champion"
            else:
                old_ckpt, old_c, old_var = str(net_ckpt), NET_CPUCT, "v2_9_rodv2_anchor"
            if cand_kind == "puct":
                new_ckpt = f"puct_prior_{args.leaf_quantize}_{args.final_select}{_variant_sig(args)}"
                new_c, new_var = args.c_puct, "puct_heur_prior"
            elif cand_kind == "ab":
                new_ckpt = f"ab{args.cand_ab_steps}{_ab_variant_sig(args)}"
                new_c, new_var = "", "ab_idalphabeta"
            else:
                new_ckpt, new_c, new_var = f"heur_h{args.cand_sims}_champion", CHAMP_C, "v2_9_champion"
            row = {
                "new_ckpt": new_ckpt,
                "new_c": new_c,
                "new_var": new_var,
                "old_ckpt": old_ckpt,
                "old_c": old_c,
                "old_var": old_var,
                "old_sims": opp_sims,
            }
        if summ.get("game_timeouts"):
            note += f" game_timeouts={summ['game_timeouts']}."
        row.update({
            "exp_id": args.exp_id or tag, "date": time.strftime("%Y-%m-%d"), "game": "base",
            "code_rev": code_rev(), "n": summ["n"],
            "new_cap": leaf_cfg.bonus_cap,
            "new_sims": (args.cand_ab_steps if cand_kind == "ab" else args.cand_sims),
            "old_cap": champ_leaf_cfg.bonus_cap,   # champion side = env DEFAULT_CONFIG
            "W": summ["W"], "L": summ["L"], "D": summ["D"],
            "elo": round(summ["elo"], 1), "sigma": round(summ["elo_sig_1sigma"], 1),
            "avg_diff": round(summ["avg_diff"], 2), "src_dir": str(out),
            "confidence": "screen" if summ["n"] < 400 else "high", "note": note,
        })
        _append_results_csv(REPO / "experiments" / "results.csv", row)
        print(f"[results.csv] appended row exp_id={args.exp_id or tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
