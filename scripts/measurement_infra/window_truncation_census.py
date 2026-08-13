#!/usr/bin/env python3
"""Window-truncation census — how often does the champion's OWN search lose LEGAL
actions to the 25x25 centroid action window?

MEASUREMENT INFRASTRUCTURE (not a strength lever). READ-ONLY: this script imports
`carc_rs` and `carcassonne_ai` and changes nothing about either. No env flag, no
patched module, no rebuilt extension. Everything it needs is already on the public
pyo3 surface (`MirrorState.mask_counts`, `MirrorState.search_single(trace_path=...)`,
`FairAgentRs.determinizations`).

=============================================================================
THE DEFECT
=============================================================================
`carc-core/src/action_space.rs::encode` returns `None` for a TILE placement whose
coordinate falls outside the 25x25 window centred on the placed-tile centroid.
Meeple actions and `Pass` are window-independent and ALWAYS encode (verified in
`encode`: only the `Action::Tile` arm can return `None`).

`carc-core/src/game.rs::legal_mask` counts those as `n_overflow` and **drops them
silently** -- unlike Python's `game_wrapper._compute_mask`, which raises
`WindowOverflowError` at exactly this condition. So `Game::legal_actions()` can
return a STRICT SUBSET of the engine's own legal move list, with no error.

LEGAL vs ILLEGAL -- the distinction this census exists to keep straight.
`legal_mask` iterates `state.possible_actions()`, which in TILES phase is built
from `possible_playing_positions(base)` -- the engine's own legality enumeration.
Every action it emits is LEGAL by construction. Therefore **every `n_overflow`
event is a legal action dropped by the window**; there is no route through
`encode` by which an illegal action is filtered out. `n_overflow` is a pure
window-truncation counter, not a legality counter. This census verifies that
claim at runtime as well as by reading the source: on every truncated node it
re-derives the node under a provably-overflow-free window and asserts

    set(legal_actions_wide) == set(legal_actions_narrow) + dropped
    len(legal_actions_wide) - len(legal_actions_narrow) == n_overflow

(`--verify-dropped-are-legal`, on by default, rare-path cost only).

=============================================================================
WHY THE PLAYED-LEVEL RATE DOES NOT BOUND THE SEARCH-INTERNAL RATE
=============================================================================
The measured ~0.5%-of-games figure (JCZ `WALL_LEGALITY`) is a rate over positions
that ACTUALLY OCCURRED. The champion is PIMC: at every decision it draws k
determinized decks and runs a full PUCT search in each. Those searches descend
into hypothetical continuations that no real game ever reached, and a
continuation is free to sprawl further from the centroid than real play does.
The 2026-08-13 crash cell (`measurement/joshuabot_20260812/CONFIRM_EXCLUSIONS.md`)
is the existence proof: at the failing ply the PLAYED position had 5 legal
actions, 0 outside the window, 0 placed tiles outside -- and the search still hit
a node whose entire legal move list was out-of-window. The played-level rate is a
measurement of a DIFFERENT population; it neither upper- nor lower-bounds this one.

=============================================================================
WHAT IS MEASURED
=============================================================================
For each banked root, the champion's own per-determinization PUCT searches are
re-run (`MirrorState.set_unseen_deck` + `search_single`, the exact seam
`fair::search_worlds` uses) with the trace sink ON. The trace's `sim` records
carry the descent's action sequence, so every expanded node is reconstructed
losslessly by replaying that sequence from the seated root. At each reconstructed
node we read `mask_counts() -> (n_total, n_overflow)`.

  * fraction of expanded interior nodes with >= 1 dropped LEGAL action
  * the distribution of dropped-action counts
  * rate by SEARCH DEPTH (the mechanism predicts it rises with depth)
  * rate by game phase / k_remaining bucket / node phase (tiles vs meeples)
  * fraction of nodes with an EMPTY mask -- the crash case
    (`SearchError::NoLegalActionsAtInterior`); a world search that actually
    raises is caught and recorded rather than aborting the census
  * visit-weighted versions of the above (a node the search visited 900 times
    matters more than one it visited once)
  * ROOT-level truncation, i.e. the played-level rate re-measured on this set

=============================================================================
THE DECISION-RELEVANT LEG (`--wide-window`, default ON)
=============================================================================
"How often would the root's chosen action change if the dropped actions had been
available?" is EXACTLY computable here, not merely proxyable, because the search
is provably ISOMORPHIC under a change of window size:

  1. `string_representation` -- the transposition key -- is a pure function of
     `GameState` (`repr_key.rs:154`); it does not mention the window.
  2. The action ordering is window-invariant. Tile index = (wr*W + wc)*4 + rot
     with wr = row - origin_row, so ordering by (row, col, rot) is preserved
     under ANY (origin, W) that contains both cells; tile-Pass sorts after all
     tile actions at every W; the 10 meeple slots keep their relative order.
     `valid_actions` is index-sorted, so the search enumerates the same actions
     in the same order.
  3. Priors are `softmax(dLeaf(a)/tau_p)` over `legal` IN THAT ORDER
     (`search/mod.rs::evaluate`), and the leaf is a function of the board, not of
     the window. Same order + same values => bit-identical priors.
  4. `pooled_q_argmax`'s tie-break is `-action`, and the remap is order-preserving.

=> With a window big enough that NO truncation is possible, the search is the
same computation, and any difference in the pooled root stats or the chosen
action is attributable to truncation and to nothing else. This is verified on
every clean root as a built-in null control (`iso_ok`): when the census finds 0
dropped actions anywhere in a root's k searches, the narrow and wide pooled stats
MUST be bit-identical, and the script flags it loudly if they are not.

A window of 71 is provably overflow-free: the engine board is 35x35
(`engine/mod.rs:43`), the centroid lies inside the board, so no legal coordinate
is more than 34 rows/cols from it, and W=71 covers centroid +/- 35.

=============================================================================
SCOPE / KNOWN GAPS
=============================================================================
  * The exact-K<=2 marginalized endgame latch (`FairAgent::choose_action_with_sims`)
    decides a move WITHOUT any PUCT search. Those roots run no census; they are
    counted and reported as `solver_region`. NOTE the solver reads
    `legal_actions()` too, so it is exposed to the same truncation -- that is a
    separate measurement, deliberately not folded in here.
  * Forced roots (exactly 1 encoded legal action) short-circuit before the k
    searches; counted as `forced`.
  * A root whose narrow search RAISES `NoLegalActionsAtInterior` is the crash
    itself. It is caught per world, recorded in `world_errors`, and the trace
    written up to that point is still parsed.

Usage
-----
    .venv/bin/python -u scripts/measurement_infra/window_truncation_census.py \
        --roots /mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl \
        --out-dir measurement/window_truncation_20260813/pilot \
        --n 30 --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "scripts" / "human_anchor", REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env_preamble  # noqa: F401,E402  -- production leaf env, MUST precede carcassonne_ai

BANK_DEFAULT = "/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl"
#: Provably overflow-free: board is 35x35 and the centroid is inside it, so no
#: legal coordinate is further than 34 from the window centre.
WIDE_WINDOW_DEFAULT = 71
NARROW_WINDOW = 25
SCHEMA = "carcassonne-window-truncation-census/v1"


# --------------------------------------------------------------------------- #
# The window remap -- pure, and the only piece of index arithmetic here.       #
# --------------------------------------------------------------------------- #
def remap_action(a: int, off_from, off_to, phase: str) -> int:
    """A flat action index under window `off_from` -> the SAME action under `off_to`.

    `off_*` are `(origin_row, origin_col, size)` as `MirrorState.window_offset()`
    returns them; `phase` is `MirrorState.phase()` ("tiles" / "meeples").

    Layout (action_space.rs): tiles occupy `(wr*W + wc)*4 + rot` for `W*W*4`
    indices, then tile-Pass, then 5 NORMAL slots, 4 FARMER slots, meeple-Pass.
    Only the tile block depends on the window, so a meeple/Pass index is a pure
    base shift.
    """
    r0a, c0a, wa = off_from
    r0b, c0b, wb = off_to
    tp_a, tp_b = wa * wa * 4, wb * wb * 4
    if str(phase).lower().startswith("tile"):
        if a == tp_a:
            return tp_b
        if not (0 <= a < tp_a):
            raise ValueError(f"action {a} is not a TILES-phase index at W={wa}")
        cell, rot = divmod(a, 4)
        wr, wc = divmod(cell, wa)
        nr, nc = wr + r0a - r0b, wc + c0a - c0b
        if not (0 <= nr < wb and 0 <= nc < wb):
            raise ValueError(f"action {a} (engine {wr + r0a},{wc + c0a}) escapes W={wb} at {off_to}")
        return (nr * wb + nc) * 4 + rot
    slot = a - (tp_a + 1)
    if not (0 <= slot <= 9):
        raise ValueError(f"action {a} is not a MEEPLES-phase index at W={wa}")
    return tp_b + 1 + slot


def digest16(s: str) -> str:
    """The trace-harness node identity (`search/mod.rs:51`)."""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Root seating                                                                 #
# --------------------------------------------------------------------------- #
class RootSeat:
    """Seats fresh `MirrorState`s at a banked root, narrow or wide.

    The narrow seat is byte-equal to `root_replay.replay_actions`
    (`random.seed(deck_seed); Game().get_init_board()` + the same actions) -- the
    same construction `rust_world_search.RustWorldSearcher` uses; `checksum` from
    the bank proves it rather than assuming it.

    The wide seat replays the SAME moves under a different window, which needs the
    prefix remapped step by step (the recorded indices live in the W=25 space).
    """

    def __init__(self, deck_seed: int, prefix, *, geom: dict, wide_window: int,
                 narrow_window: int = NARROW_WINDOW):
        import carc_rs

        self._rs = carc_rs
        self.deck_seed = int(deck_seed)
        self.prefix = [int(a) for a in prefix]   # indices in the W=25 RECORDED space
        self.geom = dict(geom)
        self.wide_window = int(wide_window)
        self.narrow_window = int(narrow_window)
        self._wide_prefix = None
        self._narrow_prefix = None

    # -- narrow ------------------------------------------------------------- #
    def narrow_prefix(self):
        """The prefix in the window UNDER TEST's index space (== `prefix` at W=25)."""
        if self.narrow_window == NARROW_WINDOW:
            return self.prefix
        if self._narrow_prefix is None:
            self._narrow_prefix = self._remap_prefix(self.narrow_window)
        return self._narrow_prefix

    def seat(self):
        pre = self.narrow_prefix()
        ms = self._rs.MirrorState.from_seed(str(self.deck_seed),
                                            window_size=self.narrow_window, **self.geom)
        for a in pre:
            ms.advance(a)
        return ms

    # -- wide --------------------------------------------------------------- #
    def _remap_prefix(self, target_w: int):
        """Remap the RECORDED (W=25) prefix into window `target_w`, in lockstep.

        Asserts at every step that the two mirrors describe the SAME position
        (`string_repr` is window-independent), so a remap bug cannot pass silently.
        """
        g_n = self._rs.MirrorState.from_seed(str(self.deck_seed),
                                             window_size=NARROW_WINDOW, **self.geom)
        g_w = self._rs.MirrorState.from_seed(str(self.deck_seed),
                                             window_size=int(target_w), **self.geom)
        out = []
        for a in self.prefix:
            aw = remap_action(a, g_n.window_offset(), g_w.window_offset(), g_n.phase())
            out.append(aw)
            g_n.advance(a)
            g_w.advance(aw)
            if g_n.string_repr() != g_w.string_repr():
                raise RuntimeError(
                    f"W={target_w}/W=25 lockstep diverged during prefix replay")
        return out

    def seat_wide(self):
        if self._wide_prefix is None:
            self._wide_prefix = self._remap_prefix(self.wide_window)
        ms = self._rs.MirrorState.from_seed(str(self.deck_seed),
                                            window_size=self.wide_window, **self.geom)
        for a in self._wide_prefix:
            ms.advance(a)
        return ms


# --------------------------------------------------------------------------- #
# Trace parsing                                                                #
# --------------------------------------------------------------------------- #
def parse_trace(path: str):
    """-> (sims, n_exp, n_exp_empty). `sims` = [(sim_idx, path_digests, acts)].

    `exp` lines are matched by a byte prefix so the (large) priors array is never
    JSON-decoded; only `va`'s emptiness is needed from them.
    """
    sims = []
    n_exp = 0
    n_exp_empty = 0
    with open(path, "r") as fh:
        for line in fh:
            if line.startswith('{"t":"exp"'):
                n_exp += 1
                if '"va":[]' in line:
                    n_exp_empty += 1
                continue
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("t") != "sim":
                continue
            sims.append((int(d["i"]), d["path"], [int(x) for x in d["acts"]]))
    return sims, n_exp, n_exp_empty


# --------------------------------------------------------------------------- #
# The per-root census                                                          #
# --------------------------------------------------------------------------- #
def _phase_bucket_k(k_rem: int) -> str:
    if k_rem is None:
        return "unknown"
    return "early" if k_rem >= 48 else ("mid" if k_rem >= 24 else "late")


def census_root(root: dict, opt) -> dict:
    """Run the champion's k searches on one root and census every expanded node."""
    import carc_rs
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import search_config_rs

    t_start = time.time()
    deck_seed = int(root["deck_seed"])
    ply = int(root["ply"])
    actions = [int(a) for a in root["actions"]]
    prefix = actions[:ply]

    spec = _SPEC or CF.load_production_spec()
    cfg = _CFG or CF.production_prior_cfg(spec)
    k_dets = int(opt.k_dets or spec.k_dets)
    sims = int(opt.sims or spec.sims_per_det)
    scfg_n = search_config_rs(cfg, sims)
    scfg_w = search_config_rs(cfg, sims)

    rec: dict = {
        "schema": SCHEMA,
        "rid": root.get("rid") or f"s{deck_seed}_p{ply}",
        "deck_seed": deck_seed,
        "ply": ply,
        "root_player": root.get("player_to_move"),
        "phase_bucket": root.get("phase_bucket"),
        "k_dets": k_dets,
        "sims_per_det": sims,
        "wide_window": opt.wide_window,
        "agent_seed": None,
        "ok": False,
        "error": None,
    }

    seat = RootSeat(deck_seed, prefix, geom=opt.geom, wide_window=opt.wide_window,
                    narrow_window=int(getattr(opt, "narrow_window", NARROW_WINDOW)))
    ms = seat.seat()

    # --- fidelity gate: the mirror really IS the banked root ------------------
    cks = root.get("checksum")
    rec["checksum_ok"] = (cks is None) or (ms.string_repr() == cks)
    if not rec["checksum_ok"]:
        rec["error"] = "checksum_mismatch"
        return rec

    n_total, n_over = ms.mask_counts()
    la = ms.legal_actions()
    rec.update({
        "phase": ms.phase(),
        "k_remaining": int(ms.k_remaining()),
        "root_window": list(ms.window_offset()),
        "root_n_total": int(n_total),
        "root_n_overflow": int(n_over),
        "root_n_encoded": len(la),
        "root_truncated": bool(n_over > 0),
        "forced": len(la) == 1,
        "solver_region": bool(str(ms.phase()).lower().startswith("tile")
                              and int(ms.k_remaining()) <= int(spec.exact_max_k)),
    })
    if len(la) != n_total - n_over:
        rec["encode_collision"] = True     # two legal actions sharing one index

    if rec["forced"] or rec["solver_region"]:
        rec["ok"] = True
        rec["skipped"] = "forced" if rec["forced"] else "solver_region"
        rec["secs"] = time.time() - t_start
        return rec

    # --- the champion's own determinizations ---------------------------------
    agent_seed = int(opt.agent_seed)
    if opt.agent_seed_mode == "production":
        try:
            sys.path.insert(0, str(REPO / "scripts" / "jcz_match"))
            import match as JM
            agent_seed = int(JM.agent_seed(deck_seed, int(root.get("player_to_move") or 0)))
        except Exception:
            pass
    rec["agent_seed"] = agent_seed

    fa = carc_rs.FairAgentRs(scfg_n, k_dets, agent_seed,
                             window_size=seat.narrow_window, **opt.geom)
    fa.start_game_from_seed(str(deck_seed))
    for a in seat.narrow_prefix():          # the agent lives in the window under test
        fa.advance(a)
    # ⚠️ move_idx is the AGENT's own decision counter, NOT the ply. The
    # determinization stream is seeded from det_seed_base(seed, move_idx), so a
    # root that wants to reproduce a SPECIFIC decision (the 2026-08-13 crash cell)
    # must carry the champion's counter; `scripts/measurement_infra/
    # reconstruct_crash_root.py` records it. Absent it, ply is used -- fine for a
    # RATE over roots (any determinization draw is a valid sample of the same
    # distribution) but NOT for reproducing a named decision.
    mi = getattr(opt, "move_idx_override", None)
    if mi is None:
        mi = root.get("move_idx")
    mi = ply if mi is None else int(mi)
    rec["move_idx"] = mi
    rec["move_idx_source"] = ("override" if getattr(opt, "move_idx_override", None) is not None
                              else "root" if root.get("move_idx") is not None else "ply")
    fa.set_move_idx(mi)
    worlds = fa.determinizations(mi)
    rec["det_seed_base"] = int(fa.det_seed_base(mi))

    # --- accumulators --------------------------------------------------------
    nodes = 0
    nodes_trunc = 0
    nodes_empty = 0
    dropped_hist: Counter = Counter()
    by_depth: dict = defaultdict(lambda: [0, 0, 0])          # depth -> [n, n_trunc, n_dropped]
    by_nodephase: dict = defaultdict(lambda: [0, 0, 0])
    by_krem: dict = defaultdict(lambda: [0, 0, 0])
    visits_total = 0
    visits_trunc = 0
    sum_dropped = 0
    max_dropped = 0
    digest_gate_fail = 0
    exp_total = 0
    exp_empty_total = 0
    world_errors = []
    examples = []
    pooled_n_narrow: Counter = Counter()
    pooled_w_narrow: dict = defaultdict(float)
    pooled_n_wide: Counter = Counter()
    pooled_w_wide: dict = defaultdict(float)
    replay_secs = 0.0
    search_secs = 0.0

    trace_path = opt.trace_path
    rng = random.Random(0xC0FFEE ^ deck_seed ^ ply)

    for wi, wdeck in enumerate(worlds):
        # ---------------- narrow (production) search, traced -----------------
        m = seat.seat()
        m.set_unseen_deck(wdeck)
        t0 = time.time()
        try:
            res = m.search_single(scfg_n, trace_path, True)
            for a, n, wbits in res["pooled_stats"]:
                pooled_n_narrow[int(a)] += int(n)
                pooled_w_narrow[int(a)] += _f64(wbits)
        except Exception as exc:                       # noqa: BLE001 -- the crash case
            world_errors.append({"world": wi, "side": "narrow", "error": repr(exc)[:400]})
        search_secs += time.time() - t0

        try:
            sims_rec, n_exp, n_exp_empty = parse_trace(trace_path)
        except Exception as exc:                       # noqa: BLE001
            world_errors.append({"world": wi, "side": "trace", "error": repr(exc)[:200]})
            sims_rec, n_exp, n_exp_empty = [], 0, 0
        exp_total += n_exp
        exp_empty_total += n_exp_empty

        # visit weights: every node on every descent path
        visit_by_digest: Counter = Counter()
        for _i, pth, _acts in sims_rec:
            for dg in pth:
                visit_by_digest[dg] += 1

        # ---------------- replay every expanded node -------------------------
        t0 = time.time()
        seen: dict = {}
        for si, pth, acts in sims_rec:
            if opt.replay_fraction < 1.0 and rng.random() > opt.replay_fraction:
                continue
            rm = seat.seat()
            rm.set_unseen_deck(wdeck)
            for a in acts:
                rm.advance(a)
            dg = digest16(rm.string_repr())
            if pth and dg != pth[-1]:
                digest_gate_fail += 1
                continue
            if dg in seen:
                continue
            nt, no = rm.mask_counts()
            enc = nt - no
            depth = len(acts)
            nph = "tiles" if str(rm.phase()).lower().startswith("tile") else "meeples"
            krem = int(rm.k_remaining())
            seen[dg] = (no, depth)

            nodes += 1
            visits = visit_by_digest.get(dg, 0)
            visits_total += visits
            by_depth[depth][0] += 1
            by_nodephase[nph][0] += 1
            by_krem[_phase_bucket_k(krem)][0] += 1
            dropped_hist[no] += 1
            if no > 0:
                nodes_trunc += 1
                sum_dropped += no
                max_dropped = max(max_dropped, no)
                visits_trunc += visits
                by_depth[depth][1] += 1
                by_depth[depth][2] += no
                by_nodephase[nph][1] += 1
                by_nodephase[nph][2] += no
                by_krem[_phase_bucket_k(krem)][1] += 1
                by_krem[_phase_bucket_k(krem)][2] += no
                if enc == 0:
                    nodes_empty += 1
                if len(examples) < opt.max_examples:
                    ex = {"world": wi, "sim": si, "depth": depth, "node_phase": nph,
                          "k_remaining": krem, "n_total": nt, "n_overflow": no,
                          "n_encoded": enc, "window": list(rm.window_offset())}
                    if opt.verify_dropped_are_legal:
                        ex.update(_verify_dropped_legal(seat, wdeck, acts, rm))
                    examples.append(ex)
                elif opt.verify_dropped_are_legal and opt.verify_all_truncated:
                    v = _verify_dropped_legal(seat, wdeck, acts, rm)
                    if not v.get("dropped_all_legal", True):
                        world_errors.append({"world": wi, "side": "verify", "error": v})
        replay_secs += time.time() - t0

        # ---------------- wide (overflow-free) search ------------------------
        if opt.wide:
            mw = seat.seat_wide()
            mw.set_unseen_deck(wdeck)
            t0 = time.time()
            try:
                resw = mw.search_single(scfg_w)
                for a, n, wbits in resw["pooled_stats"]:
                    pooled_n_wide[int(a)] += int(n)
                    pooled_w_wide[int(a)] += _f64(wbits)
            except Exception as exc:                   # noqa: BLE001
                world_errors.append({"world": wi, "side": "wide", "error": repr(exc)[:400]})
            search_secs += time.time() - t0

    # --- decision impact -----------------------------------------------------
    from carcassonne_ai.fair_agent import pooled_q_argmax
    min_pv = 2.0
    pick_n = pick_w = None
    if pooled_n_narrow:
        pick_n = int(pooled_q_argmax(dict(pooled_n_narrow), dict(pooled_w_narrow), min_pv))
    if opt.wide and pooled_n_wide:
        pick_w = int(pooled_q_argmax(dict(pooled_n_wide), dict(pooled_w_wide), min_pv))

    off_n = tuple(rec["root_window"])
    ms_w = seat.seat_wide() if opt.wide else None
    off_w = tuple(ms_w.window_offset()) if ms_w is not None else None
    pick_n_remapped = None
    pooled_identical = None
    if opt.wide and pick_n is not None and off_w is not None:
        pick_n_remapped = remap_action(pick_n, off_n, off_w, rec["phase"])
        pn = {remap_action(a, off_n, off_w, rec["phase"]): (n, pooled_w_narrow[a])
              for a, n in pooled_n_narrow.items()}
        pw = {a: (n, pooled_w_wide[a]) for a, n in pooled_n_wide.items()}
        pooled_identical = (pn == pw)

    total_dropped_anywhere = sum_dropped + int(rec["root_n_overflow"])
    rec.update({
        "ok": True,
        "n_worlds": len(worlds),
        "n_nodes_censused": nodes,
        "n_nodes_truncated": nodes_trunc,
        "n_nodes_empty_mask": nodes_empty,
        "n_exp_records": exp_total,
        "n_exp_empty_va": exp_empty_total,
        "sum_dropped": sum_dropped,
        "max_dropped": max_dropped,
        "dropped_hist": {str(k): v for k, v in sorted(dropped_hist.items())},
        "by_depth": {str(k): v for k, v in sorted(by_depth.items())},
        "by_node_phase": {k: v for k, v in sorted(by_nodephase.items())},
        "by_k_bucket": {k: v for k, v in sorted(by_krem.items())},
        "visits_total": visits_total,
        "visits_through_truncated": visits_trunc,
        "digest_gate_fail": digest_gate_fail,
        "world_errors": world_errors,
        "examples": examples,
        "pick_narrow": pick_n,
        "pick_narrow_remapped": pick_n_remapped,
        "pick_wide": pick_w,
        "pick_changed": (None if (pick_n_remapped is None or pick_w is None)
                         else bool(pick_n_remapped != pick_w)),
        "pooled_identical": pooled_identical,
        # THE built-in null control: 0 truncation anywhere => the two windows must
        # produce bit-identical pooled stats. A False here is an INSTRUMENT BUG.
        "iso_ok": (None if pooled_identical is None or total_dropped_anywhere > 0
                   else bool(pooled_identical)),
        "search_secs": round(search_secs, 3),
        "replay_secs": round(replay_secs, 3),
        "secs": round(time.time() - t_start, 3),
    })
    return rec


def _verify_dropped_legal(seat: RootSeat, wdeck, acts, narrow_mirror) -> dict:
    """Prove, at runtime, that the dropped actions are LEGAL and not merely absent.

    Replays the same descent under the overflow-free window and compares the two
    legal sets in the WIDE index space. `dropped_all_legal` is True iff the narrow
    set is exactly the wide set minus the out-of-window tile placements.
    """
    try:
        mw = seat.seat_wide()
        mw.set_unseen_deck(wdeck)
        gn = seat.seat()
        gn.set_unseen_deck(wdeck)
        for a in acts:
            aw = remap_action(a, gn.window_offset(), mw.window_offset(), gn.phase())
            gn.advance(a)
            mw.advance(aw)
        off_n, off_w = gn.window_offset(), mw.window_offset()
        ph = gn.phase()
        narrow = {remap_action(a, off_n, off_w, ph) for a in gn.legal_actions()}
        wide = set(mw.legal_actions())
        nt, no = gn.mask_counts()
        ntw, now = mw.mask_counts()
        dropped = sorted(wide - narrow)
        coords = []
        W = off_w[2]
        for a in dropped[:12]:
            if str(ph).lower().startswith("tile") and a < W * W * 4:
                cell, rot = divmod(a, 4)
                wr, wc = divmod(cell, W)
                coords.append([wr + off_w[0], wc + off_w[1], rot])
        return {
            "dropped_all_legal": bool(narrow <= wide and len(wide) - len(narrow) == no),
            "wide_n_overflow": int(now),          # MUST be 0
            "wide_n_total": int(ntw), "narrow_n_total": int(nt),
            "n_dropped_by_setdiff": len(wide - narrow),
            "n_extra_in_narrow": len(narrow - wide),   # MUST be 0
            "dropped_coords_rot": coords,
        }
    except Exception as exc:                            # noqa: BLE001
        return {"dropped_all_legal": None, "verify_error": repr(exc)[:200]}


def _f64(bits) -> float:
    import struct
    return struct.unpack("<d", struct.pack("<Q", int(bits) & 0xFFFFFFFFFFFFFFFF))[0]


# --------------------------------------------------------------------------- #
# Worker plumbing                                                              #
# --------------------------------------------------------------------------- #
_SPEC = None
_CFG = None
_OPT = None


def _init(opt_d):
    global _SPEC, _CFG, _OPT
    import carcassonne_ai.champion_factory as CF

    _OPT = _Opt(**opt_d)
    _SPEC = CF.load_production_spec()
    _CFG = CF.production_prior_cfg(_SPEC)
    _OPT.trace_path = os.path.join(_OPT.trace_dir, f"trace_{os.getpid()}.jsonl")


class _Opt:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _cell(root):
    try:
        return census_root(root, _OPT)
    except Exception as exc:                            # noqa: BLE001
        import traceback
        return {"schema": SCHEMA, "ok": False,
                "rid": root.get("rid") or f"s{root.get('deck_seed')}_p{root.get('ply')}",
                "deck_seed": root.get("deck_seed"), "ply": root.get("ply"),
                "error": repr(exc)[:400], "traceback": traceback.format_exc()[-1500:]}


# --------------------------------------------------------------------------- #
# Aggregation                                                                  #
# --------------------------------------------------------------------------- #
def summarize(rows) -> dict:
    ok = [r for r in rows if r.get("ok")]
    ran = [r for r in ok if not r.get("skipped")]
    nodes = sum(r.get("n_nodes_censused", 0) for r in ran)
    trunc = sum(r.get("n_nodes_truncated", 0) for r in ran)
    empty = sum(r.get("n_nodes_empty_mask", 0) for r in ran)
    vis = sum(r.get("visits_total", 0) for r in ran)
    vis_t = sum(r.get("visits_through_truncated", 0) for r in ran)
    by_depth: dict = defaultdict(lambda: [0, 0, 0])
    by_phase: dict = defaultdict(lambda: [0, 0, 0])
    by_k: dict = defaultdict(lambda: [0, 0, 0])
    hist: Counter = Counter()
    for r in ran:
        for d, v in r.get("by_depth", {}).items():
            for i in range(3):
                by_depth[int(d)][i] += v[i]
        for p, v in r.get("by_node_phase", {}).items():
            for i in range(3):
                by_phase[p][i] += v[i]
        for p, v in r.get("by_k_bucket", {}).items():
            for i in range(3):
                by_k[p][i] += v[i]
        for c, n in r.get("dropped_hist", {}).items():
            hist[int(c)] += n
    changed = [r for r in ran if r.get("pick_changed") is not None]
    iso = [r for r in ran if r.get("iso_ok") is not None]
    roots_trunc = [r for r in ran if r.get("n_nodes_truncated", 0) > 0]
    return {
        "schema": SCHEMA + "-summary",
        "n_rows": len(rows), "n_ok": len(ok),
        "n_skipped_forced": sum(1 for r in ok if r.get("skipped") == "forced"),
        "n_skipped_solver_region": sum(1 for r in ok if r.get("skipped") == "solver_region"),
        "n_censused_roots": len(ran),
        # --- root (played-level) truncation, re-measured ---------------------
        "roots_with_root_truncation": sum(1 for r in ok if r.get("root_truncated")),
        "root_truncation_rate": (sum(1 for r in ok if r.get("root_truncated")) / len(ok)) if ok else None,
        # --- search-internal, node-unique ------------------------------------
        "nodes_censused": nodes,
        "nodes_truncated": trunc,
        "node_truncation_rate": (trunc / nodes) if nodes else None,
        "nodes_empty_mask": empty,
        "empty_mask_rate": (empty / nodes) if nodes else None,
        # --- search-internal, visit-weighted ---------------------------------
        "visits_total": vis,
        "visits_through_truncated": vis_t,
        "visit_weighted_truncation_rate": (vis_t / vis) if vis else None,
        # --- per-root incidence ----------------------------------------------
        "roots_with_any_search_truncation": len(roots_trunc),
        "root_incidence_rate": (len(roots_trunc) / len(ran)) if ran else None,
        # --- distributions ----------------------------------------------------
        "dropped_hist": {str(k): v for k, v in sorted(hist.items())},
        "by_depth": {str(k): v for k, v in sorted(by_depth.items())},
        "by_node_phase": dict(sorted(by_phase.items())),
        "by_k_bucket": dict(sorted(by_k.items())),
        # --- decision impact ---------------------------------------------------
        "n_pick_comparable": len(changed),
        "n_pick_changed": sum(1 for r in changed if r["pick_changed"]),
        "pick_change_rate": (sum(1 for r in changed if r["pick_changed"]) / len(changed)) if changed else None,
        # --- gates -------------------------------------------------------------
        "iso_control_n": len(iso),
        "iso_control_violations": sum(1 for r in iso if not r["iso_ok"]),
        "digest_gate_fail": sum(r.get("digest_gate_fail", 0) for r in ran),
        "encode_collisions": sum(1 for r in ok if r.get("encode_collision")),
        "world_errors": sum(len(r.get("world_errors", [])) for r in ran),
        "n_error_rows": sum(1 for r in rows if not r.get("ok")),
        "secs_total": round(sum(r.get("secs", 0) for r in rows), 1),
        "secs_per_root": round(sum(r.get("secs", 0) for r in rows) / max(1, len(rows)), 3),
    }


def load_e4_roots(pattern: str, rules_profile: str, *, per_game: int = 0,
                  sample_seed: int = 0):
    """Roots from the E4 phone archives -- the `fixed_v1` rules epoch.

    The CL-070 bank is `walled` champion self-play; the 2026-08-13 crash was
    observed under `fixed_v1` (centered18 + retail start + redraw + R9). Those are
    DIFFERENT wall geometries -- the start tile sits at row 18 instead of row 6 --
    so a census on one epoch does not speak for the other. Every archive carries
    its own `rules_profile`, and archives from before the fixed_v1 build do not
    carry the field at all (they are excluded, not guessed at).

    `ai_elapsed` records exactly the plies the CHAMPION decided, which is the
    population this census is about.
    """
    import glob as _glob

    paths = sorted(_glob.glob(pattern)) if any(c in pattern for c in "*?[") else \
        sorted(_glob.glob(os.path.join(pattern, "*.json")))
    out = []
    rng = random.Random(sample_seed)
    for pth in paths:
        try:
            d = json.loads(Path(pth).read_text())
        except Exception:                                   # noqa: BLE001
            continue
        if not d.get("ok") or d.get("rules_profile") != rules_profile:
            continue
        acts = [int(x) for x in d.get("actions", [])]
        plies = sorted({int(e["ply"]) for e in d.get("ai_elapsed", []) if 0 < int(e["ply"]) < len(acts)})
        if not plies:
            continue
        if per_game and per_game < len(plies):
            plies = sorted(rng.sample(plies, per_game))
        champ_seat = 1 - int(d.get("human_player", 0))
        label = Path(pth).stem
        for ply in plies:
            out.append({"deck_seed": int(d["deck_seed"]), "ply": ply, "actions": acts,
                        "player_to_move": champ_seat, "rid": f"e4_{label}_p{ply}",
                        "source": "e4_games", "archive": pth,
                        "rules_profile": d["rules_profile"]})
    return out


# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--roots", default=BANK_DEFAULT,
                    help="roots jsonl (format=jsonl) or a glob of E4 android archives "
                         "(format=e4)")
    ap.add_argument("--roots-format", choices=("jsonl", "e4"), default="jsonl",
                    help="'e4' reads measurement/e4_games/*.json (the fixed_v1 rules "
                         "epoch the 2026-08-13 crash was observed in) and turns every "
                         "CHAMPION decision ply into a root")
    ap.add_argument("--e4-plies-per-game", type=int, default=0,
                    help="0 = every champion decision ply")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--n", type=int, default=0, help="0 = all roots")
    ap.add_argument("--sample-seed", type=int, default=20260813)
    ap.add_argument("--sample", choices=("head", "random"), default="random")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--k-dets", type=int, default=0, help="0 = PRODUCTION.yaml")
    ap.add_argument("--sims", type=int, default=0, help="0 = PRODUCTION.yaml")
    ap.add_argument("--rules-profile", default="walled")
    ap.add_argument("--wide-window", type=int, default=WIDE_WINDOW_DEFAULT)
    ap.add_argument("--narrow-window", type=int, default=NARROW_WINDOW,
                    help="the window UNDER TEST. 25 = production. A small value (e.g. 9) "
                         "is the instrument's POSITIVE CONTROL: it forces truncation, so "
                         "a census that reports 0 there is broken, not clean.")
    ap.add_argument("--no-wide", action="store_true",
                    help="skip the decision-impact (overflow-free window) leg")
    ap.add_argument("--replay-fraction", type=float, default=1.0,
                    help="subsample expanded nodes (1.0 = census every one)")
    ap.add_argument("--max-examples", type=int, default=8)
    ap.add_argument("--no-verify-dropped-are-legal", action="store_true")
    ap.add_argument("--verify-all-truncated", action="store_true",
                    help="run the legal-vs-illegal proof on EVERY truncated node, not "
                         "just the recorded examples (slow)")
    ap.add_argument("--move-idx", type=int, default=None,
                    help="force the agent's decision counter (single-root reproduction "
                         "of a NAMED decision; roots may carry their own `move_idx`)")
    ap.add_argument("--agent-seed", type=int, default=101)
    ap.add_argument("--agent-seed-mode", choices=("production", "fixed"), default="production")
    ap.add_argument("--trace-dir", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--resume", action="store_true",
                    help="append to an existing rows.jsonl and skip roots already in it "
                         "(rows are streamed as they complete, so a killed run resumes "
                         "at root granularity)")
    a = ap.parse_args(argv)

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    trace_dir = a.trace_dir or str(out / "_traces")
    Path(trace_dir).mkdir(parents=True, exist_ok=True)

    from carcassonne_ai import rules_profile as RP
    prof = RP.activate(a.rules_profile)
    gk = prof.game_kwargs()
    geom = {}
    if "start_row" in gk:
        geom["start_row"] = int(gk["start_row"])
        geom["start_col"] = int(gk["start_col"])
    if gk.get("fixed_start_tile"):
        geom["start_rule"] = "retail"
    if gk.get("cloister_scan_fix"):
        geom["cloister_scan_fix"] = True
    if gk.get("draw_rule"):
        geom["draw_rule"] = str(gk["draw_rule"])

    if a.roots_format == "e4":
        roots_all = load_e4_roots(a.roots, prof.name, per_game=a.e4_plies_per_game,
                                  sample_seed=a.sample_seed)
    else:
        roots_all = [json.loads(l) for l in open(a.roots) if l.strip()]
    roots = list(roots_all)
    if a.n and a.n < len(roots):
        if a.sample == "random":
            random.Random(a.sample_seed).shuffle(roots)
        roots = roots[:a.n]

    # --- resume: rows are streamed, so a killed run restarts at root granularity
    rows_path = out / "rows.jsonl"
    done_rows: list = []
    if a.resume and rows_path.exists():
        for line in rows_path.read_text().splitlines():
            if line.strip():
                try:
                    done_rows.append(json.loads(line))
                except json.JSONDecodeError:      # a torn last line from a hard kill
                    break
        done_rids = {r.get("rid") for r in done_rows}
        before = len(roots)
        roots = [r for r in roots
                 if (r.get("rid") or f"s{r.get('deck_seed')}_p{r.get('ply')}") not in done_rids]
        print(f"[resume] {len(done_rows)} row(s) already on disk; "
              f"{len(roots)}/{before} root(s) left", flush=True)
    elif rows_path.exists():
        rows_path.unlink()

    opt_d = dict(
        k_dets=a.k_dets, sims=a.sims, geom=geom, wide=not a.no_wide,
        narrow_window=int(a.narrow_window),
        wide_window=int(a.wide_window), replay_fraction=float(a.replay_fraction),
        max_examples=int(a.max_examples),
        verify_dropped_are_legal=not a.no_verify_dropped_are_legal,
        verify_all_truncated=bool(a.verify_all_truncated),
        agent_seed=int(a.agent_seed), agent_seed_mode=a.agent_seed_mode,
        move_idx_override=a.move_idx,
        trace_dir=trace_dir, trace_path="",
    )

    import carcassonne_ai.champion_factory as CF
    spec = CF.load_production_spec()
    manifest = {
        "schema": SCHEMA + "-manifest",
        "written": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "argv": sys.argv,
        "tag": a.tag,
        "roots_path": a.roots, "roots_format": a.roots_format, "n_roots": len(roots),
        "sample": a.sample, "sample_seed": a.sample_seed,
        "rules_profile": prof.as_manifest(),
        "mirror_geom": geom,
        "champion": {"id": spec.champion_id, "k_dets": spec.k_dets,
                     "sims_per_det": spec.sims_per_det, "leaf_hash": spec.yaml_leaf_hash,
                     "exact_max_k": spec.exact_max_k, "backend": spec.backend},
        "k_dets_used": a.k_dets or spec.k_dets,
        "sims_used": a.sims or spec.sims_per_det,
        "narrow_window": a.narrow_window, "wide_window": a.wide_window,
        "wide_leg": not a.no_wide,
        "replay_fraction": a.replay_fraction,
        "move_idx_override": a.move_idx,
        "move_idx_note": ("move_idx is the AGENT's decision counter, not the ply; roots "
                          "without a `move_idx` field fall back to ply, which samples a "
                          "VALID determinization draw but not a NAMED decision's one"),
        "env": {k: os.environ.get(k, "") for k in env_preamble.PROD_ENV},
        "workers": a.workers,
        "note": ("READ-ONLY instrument: no engine/src/rust modification. Truncation is "
                 "measured with MirrorState.mask_counts (n_total, n_overflow) on nodes "
                 "reconstructed from the search's own trace."),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    new_rows: list = []
    t0 = time.time()
    fh = open(rows_path, "a" if a.resume else "w")

    def _emit(i, r):
        new_rows.append(r)
        fh.write(json.dumps(r) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
        print(f"[{i + 1}/{len(roots)}] {r.get('rid')} "
              f"trunc={r.get('n_nodes_truncated')}/{r.get('n_nodes_censused')} "
              f"{r.get('secs')}s", flush=True)

    try:
        if a.workers <= 1:
            _init(opt_d)
            for i, r in enumerate(roots):
                _emit(i, _cell(r))
        else:
            import multiprocessing as mp
            ctx = mp.get_context("spawn")
            with ctx.Pool(a.workers, initializer=_init, initargs=(opt_d,)) as pool:
                for i, r in enumerate(pool.imap_unordered(_cell, roots, chunksize=1)):
                    _emit(i, r)
    finally:
        fh.close()

    rows = done_rows + new_rows
    summ = summarize(rows)
    summ["wall_secs"] = round(time.time() - t0, 1)
    summ["workers"] = a.workers
    summ["n_rows_resumed"] = len(done_rows)
    summ["n_rows_new"] = len(new_rows)
    (out / "summary.json").write_text(json.dumps(summ, indent=2))
    print(json.dumps(summ, indent=2))

    for p in Path(trace_dir).glob("trace_*.jsonl"):
        try:
            p.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
