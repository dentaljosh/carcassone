"""Adaptive labeling queue — MEASUREMENT INFRA (not a strength lever).

Turns a pool of recorded games into a queue of ROOTS to deep-label, stratified into the sample types
the post-search-residual pilot (CL-035) showed matter for measuring where shallow search is wrong:

  - ordinary          : a phase-balanced random sample (the baseline distribution)
  - low_top2gap        : "suspicious" roots where HeuristicMCTS(200)'s top-2 backed-up Q are nearly
                         tied (top2_q_gap < tau) — the cheap signal that predicts mis-decided roots
  - opening_heavy      : oversamples the opening, where the pilot found h200 most often wrong
  - close_score        : roots with a small score margin (competitive positions)

"Adaptive" = it runs a cheap h200 probe over candidates and TARGETS labeling at the suspicious /
phase / close-score strata instead of labeling uniformly. The emitted queue (RootRefs + tags +
stratum) feeds a deep-label pass (e.g. the multi-depth snapshot dataset builder).

GOVERNANCE: this is triage/measurement tooling. Adaptive compute is CLOSED as a strength lever
(CL-035 / Decision C); these strata target MEASUREMENT, not play.
"""
from __future__ import annotations
import json
import random
import sys
from pathlib import Path
from multiprocessing import get_context

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from root_replay import load_games, replay_actions          # noqa: E402
from snapshot import make_heuristic_agent, snapshot_search   # noqa: E402
from tagging import _stats                                   # noqa: E402

PHASES = ("opening", "midgame", "late_mid", "pre_endgame", "endgame")
_W: dict = {}


def frac_to_phase(f: float) -> str:
    if f < 0.22: return "opening"
    if f < 0.50: return "midgame"
    if f < 0.70: return "late_mid"
    if f < 0.90: return "pre_endgame"
    return "endgame"


def _k_remaining(state):
    return len(state.deck) + (1 if state.next_tile is not None else 0)


def _worker_init(leaf_cfg, sims, games):
    _W["agent"] = make_heuristic_agent(sims, leaf_cfg)
    _W["sims"] = sims
    _W["games"] = games


def _tag_candidate(cand):
    """cand = {game_id, deck_seed, ply, n_plies}. Reconstruct, run h200, return tags + state feats."""
    try:
        gid = int(cand["game_id"]); seed = int(cand["deck_seed"])
        ply = int(cand["ply"]); npl = int(cand["n_plies"])
        agent = _W["agent"]; sims = _W["sims"]
        agent.clear(); agent.rng = random.Random((seed * 1_000_003 + ply) & 0x7fffffff)
        _, board = replay_actions(seed, _W["games"][gid], ply)
        st = board.state
        cur = int(st.current_player); opp = 1 - cur
        legal_n = int(agent.game.get_valid_moves(board).sum())
        snaps, _ = snapshot_search(agent, board, [sims])
        tags = _stats(snaps[sims])
        return {"game_id": gid, "deck_seed": seed, "ply": ply, "n_plies": npl,
                "phase": frac_to_phase(ply / npl), "k_remaining": int(_k_remaining(st)),
                "score_margin": int(st.scores[cur] - st.scores[opp]),
                "legal_n": legal_n, **tags}
    except Exception as e:
        import traceback
        return {"_error": f"{cand.get('game_id')}:{cand.get('ply')}: {type(e).__name__}: {e}",
                "_tb": traceback.format_exc().splitlines()[-2:]}


class AdaptiveLabelingQueue:
    """Holds h200-tagged candidate roots and samples the four strata."""

    def __init__(self, tagged):
        # keep only decision roots (>=2 legal moves) — forced plies have nothing to label
        self.cands = [c for c in tagged if c.get("legal_n", 0) >= 2]

    # ---- construction ----
    @classmethod
    def from_games(cls, games_path, leaf_cfg, sims=200, candidates_per_game=25,
                   workers=16, seed=0):
        games = load_games(games_path)
        games_dict = {g.game_id: g.actions for g in games}
        rng = np.random.default_rng(seed)
        cands = []
        for g in games:
            lo, hi = 4, g.n_plies - 3
            if hi <= lo:
                continue
            plies = np.arange(lo, hi)
            rng.shuffle(plies)
            for ply in plies[:candidates_per_game]:
                cands.append({"game_id": g.game_id, "deck_seed": g.deck_seed,
                              "ply": int(ply), "n_plies": g.n_plies})
        ctx = get_context("fork")
        tagged, errs = [], 0
        with ctx.Pool(workers, initializer=_worker_init,
                      initargs=(leaf_cfg, sims, games_dict)) as pool:
            for r in pool.imap_unordered(_tag_candidate, cands, chunksize=16):
                if "_error" in r:
                    errs += 1
                else:
                    tagged.append(r)
        if errs:
            print(f"[labeling_queue] {errs} tagging errors (skipped)")
        return cls(tagged)

    # ---- strata ----
    def sample(self, stratum, n, *, tau=0.02, margin=3, opening_weight=0.6, seed=0):
        rng = np.random.default_rng(seed)
        pool = self.cands
        if stratum == "ordinary":
            chosen = self._phase_balanced(pool, n, rng)
        elif stratum == "low_top2gap":
            sus = sorted(pool, key=lambda c: c["top2_q_gap"])      # smallest gap = most suspicious
            sus = [c for c in sus if c["top2_q_gap"] < tau] or sus
            chosen = sus[:n]
        elif stratum == "opening_heavy":
            opening = [c for c in pool if c["phase"] == "opening"]
            rest = [c for c in pool if c["phase"] != "opening"]
            n_open = min(len(opening), int(round(opening_weight * n)))
            chosen = (list(rng.permutation(opening)[:n_open])
                      + list(rng.permutation(rest)[: n - n_open]))
        elif stratum == "close_score":
            close = [c for c in pool if abs(c["score_margin"]) <= margin]
            chosen = list(rng.permutation(close)[:n]) if close else []
        else:
            raise ValueError(f"unknown stratum {stratum!r}")
        return [dict(c, stratum=stratum) for c in chosen]

    @staticmethod
    def _phase_balanced(pool, n, rng):
        per = max(1, n // len(PHASES))
        out = []
        for ph in PHASES:
            sub = [c for c in pool if c["phase"] == ph]
            if sub:
                out += list(rng.permutation(sub)[:per])
        return out[:n]

    def emit(self, path, strata):
        """strata: dict[stratum_name -> list of sampled candidates]. Writes one jsonl row per root
        (deduped by (game_id, ply); a root may satisfy multiple strata -> 'strata' list)."""
        by_root = {}
        for name, rows in strata.items():
            for c in rows:
                key = (c["game_id"], c["ply"])
                if key not in by_root:
                    by_root[key] = {k: v for k, v in c.items() if k != "stratum"}
                    by_root[key]["strata"] = []
                by_root[key]["strata"].append(name)
        p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as fh:
            for rec in by_root.values():
                fh.write(json.dumps(rec) + "\n")
        return len(by_root)

    def summary(self):
        import numpy as _np
        g = _np.array([c["top2_q_gap"] for c in self.cands])
        from collections import Counter
        return {"n_candidates": len(self.cands),
                "phase_counts": dict(Counter(c["phase"] for c in self.cands)),
                "top2_q_gap_median": float(_np.median(g)) if len(g) else None,
                "low_top2gap_lt_0.02": int((g < 0.02).sum()),
                "close_score_le_3": int(sum(1 for c in self.cands if abs(c["score_margin"]) <= 3))}
