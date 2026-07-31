"""rustport **P4** quirk-mutation probe — is G4's "0 mismatches" informative?

A gate that cannot go red is not a gate.  P1 and P3 each ran this: regress a
ported quirk and check the gate NOTICES.  Here the mutations are applied to the
PYTHON ORACLE (never to the Rust production path), so nothing has to be rebuilt
and no debug switch leaks into the shipped agent.

⚠️ **Run at LOW sims.**  P3's standing lesson: ordering-quirk sensitivity DECAYS
with budget — its `sqrt(max(N,1))` mutation showed 31 mismatches at 8 sims and
**0 at >=344**.  A high-budget probe is blind to exactly the class of quirk this
phase is full of (world merge order, tiebreaks, pool insertion order).

The mutations, each a one-line regression of a documented P4 quirk:

  merge_reversed   fold each world's root stats in REVERSE action order (float
                   addition is not associative -> the pooled W bits move).  The
                   same associativity property that makes the k-world merge
                   order load-bearing.
  no_deck_sort     drop the CL-056 canonicalization (sort the unseen deck by
                   description BEFORE the reshuffle) -> different worlds
  tiebreak_plus_a  pooled-Q final tiebreak `+action` instead of `-action`
  no_min_visits    drop the min_pooled_visits floor (1-visit noise picks become
                   eligible)
  no_pov_sign      harvest the child's OWN W instead of root-POV-signed W —
                   the gap P3 named and P4 closed
  no_dedup         drop the id(child) dedup in the harvest (rotation aliases
                   pooled once per alias)
  latch_any_phase  latch on a MEEPLES decision too, not only TILES (breaks the
                   turn-atomic boundary).  ⚠️ MEASURED NO-OP, and provably so:
                   `k_remaining` = undrawn deck + the tile in hand, and the
                   engine draws only at the END of the meeple phase, so k is
                   CONSTANT across a turn's (TILES, MEEPLES) pair and drops only
                   at the MEEPLES->TILES boundary.  The first decision with
                   k <= K is therefore always a TILES decision.  Verified on the
                   whole record: 463/463 recorded games, first k<=2 decision is
                   'tiles', 0 exceptions.  Same shape as P1's `find_roads`
                   non-dedup and P3's alias-skip: ported because the source says
                   so, not because it is reachable.
  solver_max_only  the solver always maximizes (ignores `to_move`)

Usage:
    .venv/bin/python scripts/rustport/probe_fair_mutations.py --sims 8 --k-dets 4
"""
from __future__ import annotations

import argparse
import contextlib
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "rustport"))

import fair_common as F  # noqa: E402  (leaf env preamble; must precede carcassonne_ai)

import reconcile_fair as R  # noqa: E402
from carcassonne_ai import fair_agent  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402

OUTDIR = REPO / "measurement" / "rustport_p4"


# --------------------------------------------------------------------------- #
# The mutations (context managers over the PYTHON oracle)                      #
# --------------------------------------------------------------------------- #
@contextlib.contextmanager
def _patch(obj, name, new):
    old = getattr(obj, name)
    setattr(obj, name, new)
    try:
        yield
    finally:
        setattr(obj, name, old)


@contextlib.contextmanager
def merge_reversed():
    orig = fair_agent._merge_root_stats

    def mut(stats, agg_n, agg_w):
        orig(list(reversed(list(stats))), agg_n, agg_w)

    with _patch(fair_agent, "_merge_root_stats", mut):
        yield


@contextlib.contextmanager
def no_deck_sort():
    import copy

    def mut(board, rng):
        b = copy.deepcopy(board)
        rng.shuffle(b.state.deck)          # NO canonical sort first
        b._str_repr_cache = None
        return b

    with _patch(fair_agent.FairHeuristicMCTSAgent, "reshuffled_determinization",
                staticmethod(mut)):
        yield


@contextlib.contextmanager
def tiebreak_plus_a():
    def mut(agg_n, agg_w, min_visits=2):
        eligible = [a for a, n in agg_n.items() if n >= min_visits] or list(agg_n)
        return int(max(eligible, key=lambda a: (agg_w[a] / agg_n[a], agg_n[a], a)))

    with _patch(fair_agent, "pooled_q_argmax", mut):
        yield


@contextlib.contextmanager
def no_min_visits():
    orig = fair_agent.pooled_q_argmax
    with _patch(fair_agent, "pooled_q_argmax",
                lambda n, w, min_visits=2: orig(n, w, 0)):
        yield


@contextlib.contextmanager
def no_pov_sign():
    def mut(root):
        out, seen = [], set()
        for a in sorted(root.children):
            ch = root.children[a]
            if ch.N <= 0 or id(ch) in seen:
                continue
            seen.add(id(ch))
            out.append((a, ch.N, ch.W))       # child POV, NOT root POV
        return out

    with _patch(fair_agent, "root_stats_list", mut):
        yield


@contextlib.contextmanager
def no_dedup():
    def mut(root):
        out = []
        for a in sorted(root.children):
            ch = root.children[a]
            if ch.N <= 0:
                continue
            sw = ch.W if ch.player_to_move == root.player_to_move else -ch.W
            out.append((a, ch.N, sw))         # every alias pooled again
        return out

    with _patch(fair_agent, "root_stats_list", mut):
        yield


@contextlib.contextmanager
def latch_any_phase():
    """Latch on the first decision with k_remaining <= EXACT_MAX_K regardless of
    phase — i.e. allow the turn-atomic tile/meeple boundary to be split."""
    cls = fair_agent.FairHeuristicPriorAgent
    orig = cls.choose_action

    def mut(self, board):
        if self._exact_endgame and not self._latched:
            k = fair_agent.k_remaining(board.state)
            if k <= self._exact_max_k:        # phase check REMOVED
                self._latched = True
                self.latch_k = k
        return orig(self, board)

    with _patch(cls, "choose_action", mut):
        yield


@contextlib.contextmanager
def solver_max_only():
    S = F.solver_module()
    orig = S._Solver._value

    def mut(self, board):
        saved = board.state.current_player
        try:
            board.state.current_player = 0    # always maximize
            return orig(self, board)
        finally:
            board.state.current_player = saved

    with _patch(S._Solver, "_value", mut):
        yield


MUTATIONS = {
    "merge_reversed": merge_reversed,
    "no_deck_sort": no_deck_sort,
    "tiebreak_plus_a": tiebreak_plus_a,
    "no_min_visits": no_min_visits,
    "no_pov_sign": no_pov_sign,
    "no_dedup": no_dedup,
    "latch_any_phase": latch_any_phase,
    "solver_max_only": solver_max_only,
}


# --------------------------------------------------------------------------- #
# The probe                                                                    #
# --------------------------------------------------------------------------- #
def run_one(name, ctx, args) -> dict:
    n_bad = n_dec = 0
    first = None
    t0 = time.time()
    for deck_seed, agent_seed in args.games:
        job = {"leg": "game", "label": f"{name}/{deck_seed}", "deck_seed": deck_seed,
               "agent_seed": agent_seed, "sims": args.sims, "k_dets": args.k_dets,
               "threads": 1, "max_moves": args.max_moves}
        with (ctx() if ctx is not None else contextlib.nullcontext()):
            out = R._game_job(job)
        n_dec += out["decisions"]
        n_bad += len(out["mismatches"])
        if first is None and out["mismatches"]:
            first = out["mismatches"][0]
    return {"mutation": name, "decisions": n_dec, "mismatches": n_bad,
            "discriminated": n_bad > 0, "secs": round(time.time() - t0, 1),
            "first": first}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sims", type=int, default=8,
                    help="LOW on purpose — see the P3 decay lesson in the docstring")
    ap.add_argument("--k-dets", type=int, default=4)
    ap.add_argument("--max-moves", type=int, default=None)
    ap.add_argument("--n-games", type=int, default=2)
    ap.add_argument("--tag", default="run")
    args = ap.parse_args(argv)
    args.games = [(7, 101), (23, 202), (41, 303)][:args.n_games]

    rows = [run_one("CONTROL(none)", None, args)]
    if rows[0]["mismatches"]:
        print("!! the UNMUTATED control is already red — fix G4 before reading this")
    for name, ctx in MUTATIONS.items():
        rows.append(run_one(name, ctx, args))
        r = rows[-1]
        print(f"  {name:18} decisions={r['decisions']:<5} mismatches={r['mismatches']:<5} "
              f"{'DISCRIMINATED' if r['discriminated'] else 'no-op (EXPLAIN IT)'}"
              f"  ({r['secs']}s)", flush=True)

    n_disc = sum(1 for r in rows[1:] if r["discriminated"])
    payload = {"probe": "P4/fair-quirk-mutation", "args": vars(args),
               "n_mutations": len(MUTATIONS), "n_discriminated": n_disc,
               "rows": rows}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    path = OUTDIR / f"P4_mutation_probe_{args.tag}.json"
    path.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\ncontrol: {rows[0]['mismatches']} mismatches over "
          f"{rows[0]['decisions']} decisions (must be 0)")
    print(f"{n_disc}/{len(MUTATIONS)} mutations discriminated at sims={args.sims} "
          f"k={args.k_dets} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
