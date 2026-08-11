"""h200 tagging — attach shallow-search diagnostics to every root. MEASUREMENT INFRA.

The post-search-residual pilot (CL-035) found that the single most useful "is this root hard for
shallow search?" signal is the **h200 top-2 Q gap**: roots where HeuristicMCTS(200)'s top two
backed-up Q values are nearly tied are exactly the roots most likely to be mis-decided vs a deep
reference (it captured the predictable escalation signal that learned models could not robustly
beat). So every root the infra produces carries a `top2_q_gap` tag (+ supporting diagnostics).

NOTE (governance): these tags are a *measurement/triage* signal, NOT a strength lever — adaptive
compute was CLOSED for strength (CL-035 / Decision C). Use them to TARGET labeling, not to play.
"""
from __future__ import annotations
import math

DEFAULT_TAG_LEVEL = 200


def _stats(levelmap):
    Ns = [n for (n, q) in levelmap.values()]
    Qs = [q for (n, q) in levelmap.values()]          # root-POV
    tot = sum(Ns)
    if tot <= 0:
        return dict(top2_q_gap=0.0, entropy=0.0, top_share=0.0, n_visited=0)
    ps = [n / tot for n in Ns if n > 0]
    entropy = float(-sum(p * math.log(p) for p in ps))
    top_share = float(max(Ns) / tot)
    qs = sorted(Qs, reverse=True)
    top2_q_gap = float(qs[0] - qs[1]) if len(qs) >= 2 else float(qs[0])
    return dict(top2_q_gap=top2_q_gap, entropy=entropy, top_share=top_share,
                n_visited=int(sum(1 for n in Ns if n > 0)))


def tag_from_snaps(snaps, level: int = DEFAULT_TAG_LEVEL) -> dict:
    """Derive h200-style tags from an existing snapshot dict (no extra search)."""
    lm = snaps.get(level) or snaps.get(str(level))
    if lm is None:
        raise KeyError(f"level {level} not in snapshot (have {sorted(snaps)})")
    # snapshot values may be tuple or list (after json round-trip)
    lm = {int(a): (int(v[0]), float(v[1])) for a, v in lm.items()}
    return _stats(lm)


def tag_root(agent, board, sims: int = DEFAULT_TAG_LEVEL) -> dict:
    """Run a fresh `sims`-sim search on `agent` and return the h200-style tags. Caller is responsible
    for agent.clear() + rng seeding if reproducibility matters. Uses the agent's configured leaf."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from snapshot import snapshot_search
    snaps, _ = snapshot_search(agent, board, [sims])
    return _stats(snaps[sims])


def is_low_top2gap(tags: dict, tau: float) -> bool:
    """The 'suspicious' predicate: h200 reports its top two moves as nearly tied in value."""
    return tags["top2_q_gap"] < tau
