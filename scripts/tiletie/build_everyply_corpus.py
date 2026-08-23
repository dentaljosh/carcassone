#!/usr/bin/env python3
"""EVERY-PLY ROLLOUT ARBITRATION (SIZE-1) — stage 1 of the pipeline: turn
``SELECTION.jsonl`` into ``run_tiletie``-shaped position/leg inputs.

Pair of record: ``measurement/everyply_probe_20260823/DESIGN.md`` (§3.1 arms,
§3.2 the champion re-search, §5.2 selective pricing, §6.1/§6.3 this build) and
``READ_RULE.md`` (§3 the gates this stage must make satisfiable).

⛔ **NEW FILE ONLY.** DESIGN §6.3 binds: nothing in ``build_positions.py`` /
``champ_picks.py`` / ``analyze_tiearb.py`` may be edited (a run was live in the
main tree when this was written; spawn respawns and every new leg RE-IMPORT from
disk). Every shared seam below is **reused by import, never forked**:

    scripts/measurement_infra/root_replay.py :: replay_actions      (the root)
    scripts/tiletie/build_positions.py       :: dedupe_tie_actions  (afterstate dedupe)
                                              _seeded_cap          (the J=4 subset witness)
                                              build_arms_index     (ARMS.json)
                                              write_leg_files      (positions_<profile>_leg<r>.jsonl)
                                              cost_plan            (POSITIONS_PLAN.json)
                                              load_champ_games     (the action sequences)
    scripts/tiletie/analyze_tiletie.py       :: parity_indices / crossfit_regret
                                                                   (--mode selective's a_arb)
    scripts/tiletie/chain_census.py          :: prepare_env / build_leaf / chain_values
                                                                   (the §3.1 fallback)

TWO MODES
=========

``--mode arms`` (DESIGN §6.1 stage 1) — for each selected non-tied tile ply:

  1. replay ``(deck_seed, actions, ply)`` losslessly and **assert the replayed
     board's own ``string_representation``** is what every downstream leg will
     re-derive (it becomes the leg line's ``checksum``);
  2. run ONE fresh production champion search
     (``champion_factory.make_production_champion("fair", …)`` +
     ``mirror_protocol.reseat``, the ``champ_picks.champion_search_pick`` shape —
     CL-070: the archived ``action_played`` is *a* champion pick, not *the* one);
  3. extract the **pooled root Q ranking** out of that same search —
     ⚠️ ``fair_agent.root_stats_list`` DEDUPS CHILDREN BY NODE IDENTITY and the
     agent stashes only ``last_pooled_visits`` (the pooled ``N``), never the
     pooled ``W``, so there is no pooled-Q attribute to read. The ranking is
     harvested with the house **pool spy**
     (``scripts/measurement_infra/gen_simsplit_off_fixture._PoolSpy``'s pattern:
     wrap ``fair_agent.pooled_q_argmax``, record ``(agg_n, agg_w)``, delegate),
     and the ranking key is byte-identical to ``pooled_q_argmax``'s own
     ``(W/N, N, -action)`` — so ``ranked[0]`` **is** the champion's returned
     action, by construction, not by coincidence. It is asserted per position;
  4. dedupe the position's FULL legal action set by successor board key and take
     the top ``K = 4`` **distinct-afterstate** actions of that ranking, with the
     champion's own pick unioned in and forced to index 0 (``G-COVER``);
  5. emit ``POSITIONS_PLAN.json`` / ``ARMS.json`` /
     ``DROPPED_ALL_TRANSPOSITION.json`` / ``positions_walled_leg<r>.jsonl`` /
     ``CORPUS_SUMMARY.json`` / ``champ_picks.jsonl`` (+ per-rid ``records/``,
     so ``--resume`` never re-pays a 13.8 s champion search).

  The §3.1 **pre-committed fallback** is ``--arm-builder leaf_topk``: arms =
  ``{champ_pick} ∪ top-(K−1) by LEAF value`` from ``chain_census.chain_values``.
  It is **weaker** (it hands the arbiter the leaf's own shortlist) and DESIGN
  §12 rule 3 says it engages ONCE, at the pilot, and then freezes. Which builder
  ran is stamped on the plan **and on every rid**, and the read-out must print it.

``--mode selective`` (DESIGN §5.2) — the 2.19× economy, and the ONLY place the
arm subset shrinks. Reads the **ARB records only** (never a clair-puct value —
that is exactly what keeps the cross-fit non-circular) and emits a reduced IF
plan dir holding, per position,

    arms_to_price(p) = {champ} ∪ {a_arb(fold 1), a_arb(fold 2)}

``a_arb`` is ``analyze_tiletie.crossfit_regret(matrix_arb, sel, eva, champ_pos)``'s
own ``a_plus`` — the identical call and the identical argmax tie-break the
analyser will make, imported, not re-typed. Positions whose subset is a
**singleton** are ``κ[p] = 0`` by identity: they are written into ``ARMS.json``
with a one-element arm list (so ``write_leg_files`` emits no leg for them, which
is the whole saving) and listed in ``--zerofill-out``. They are **ZERO-FILLED,
never dropped** — ``G-ZEROFILL`` is the gate on that.

⛔ Claims no band (DESIGN §8 / BAND_NOTE.md): every position is an offline replay
of the already-claimed, already-retired band ``28000000000``. ``band`` and
``corpus`` are stamped on every rid so no later reader can mistake this corpus
for a fresh one (BAND_NOTE §3).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC_ROOT = os.environ.get("CARC_SRC_ROOT") or str(REPO / "src")
for _p in (SRC_ROOT, str(REPO / "scripts" / "measurement_infra"),
           str(REPO / "scripts" / "jcz_match"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import argparse                 # noqa: E402
import json                     # noqa: E402
import multiprocessing as mp    # noqa: E402
import subprocess               # noqa: E402
import time                     # noqa: E402

import analyze_tiletie as AT    # noqa: E402
import build_positions as BP    # noqa: E402

SCHEMA = "carcassonne-everyply-corpus/v1"
DESIGN_DOC = "measurement/everyply_probe_20260823/DESIGN.md"
READ_RULE_DOC = "measurement/everyply_probe_20260823/READ_RULE.md"

#: DESIGN §3.1 — K = J = 4, the arm cap the whole tie-arbitration family has used
#: since tiletie_pricing_20260812. NOT a new constant.
K_ARMS = 4
#: DESIGN §3.3 / §5.1 — M is the judge launcher's knob; carried here for the plan.
M_WORLDS = 32
#: BAND_NOTE §3 — stamped, never claimed.
BAND = 28000000000
CORPUS = "champ449"
#: DESIGN §10 item 8 — only `walled` may use the rust clair-puct path.
DEFAULT_RULES_PROFILE = "walled"
ARM_BUILDERS = ("pooled_q", "leaf_topk")

DEFAULT_SELECTION = REPO / "measurement/everyply_probe_20260823/SELECTION.jsonl"
DEFAULT_CHAMP_GAMES = REPO / "measurement/champ_action_logs/champ_games.jsonl"

#: The corpus-shape stratum the REUSED seams consume (`write_leg_files` branches
#: e4/selfplay on it; `cost_plan` counts `t_champ` on it). ⚠️ NOT the DESIGN §2.2
#: leaf-gap stratum — that rides as `gap_stratum` and is what κ is reweighted over.
CORPUS_STRATUM = "selfplay"


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _git_rev(path=REPO) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


def load_selection(path, chunk=None, limit=0) -> list:
    """``SELECTION.jsonl`` rows, in the committed order, optionally one chunk.

    ⚠️ The order is load-bearing (DESIGN §2.4): every completed-chunk prefix is a
    uniform random subsample **at CHUNK granularity**, so this never re-sorts.
    """
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if chunk is not None and int(r["chunk"]) != int(chunk):
            continue
        rows.append(r)
    if limit and int(limit) > 0:
        rows = rows[: int(limit)]
    return rows


# --------------------------------------------------------------------------- #
# the pooled root Q ranking — the ONE genuinely new extraction (DESIGN §3.1)     #
# --------------------------------------------------------------------------- #
class PoolSpy:
    """Capture every ``(agg_n, agg_w)`` handed to the pooled-Q pick, in call order.

    Verbatim the pattern of ``scripts/measurement_infra/gen_simsplit_off_fixture
    ._PoolSpy`` — the house way to read the pooled root stats without touching
    ``src/``. The agent itself stashes only ``last_pooled_visits`` (the pooled
    ``N``); the pooled ``W`` — and therefore Q — exists nowhere else.
    """

    def __init__(self, fa):
        self._fa = fa
        self.calls = []
        self._real = fa.pooled_q_argmax

    def __call__(self, agg_n, agg_w, min_visits=None):
        self.calls.append((dict(agg_n), dict(agg_w),
                           self._fa.DEFAULT_MIN_POOLED_VISITS
                           if min_visits is None else min_visits))
        if min_visits is None:
            return self._real(agg_n, agg_w)
        return self._real(agg_n, agg_w, min_visits)

    def install(self):
        self._fa.pooled_q_argmax = self
        return self

    def restore(self):
        self._fa.pooled_q_argmax = self._real


def pooled_ranking(agg_n: dict, agg_w: dict, min_visits: int) -> list:
    """Root actions in DESCENDING pooled-Q order.

    ⚠️ The key is ``fair_agent.pooled_q_argmax``'s OWN key — ``(W/N, N, -action)``
    with the same eligibility rule (pooled ``N >= min_visits``, falling back to
    every visited action if none qualify). Because the key is total, sorting by
    it puts ``pooled_q_argmax``'s ``max`` first: ``ranked[0]`` IS the champion's
    returned action. That identity is what makes ``G-COVER`` true by
    construction rather than by hope, and it is asserted per position.
    """
    if not agg_n:
        raise ValueError("pooled_ranking: no visited root actions to pool")
    eligible = [a for a, n in agg_n.items() if n >= min_visits] or list(agg_n)
    return [int(a) for a in sorted(
        eligible, key=lambda a: (agg_w[a] / agg_n[a], agg_n[a], -a), reverse=True)]


def afterstate_entry(game, board, actions) -> dict:
    """A ``transposition_census``-shaped afterstate map entry for ONE ply.

    Keyed on the TILE successor's ``string_representation``, before the meeple
    decision — the same key ``transposition_census.py`` uses, because the arms
    are tile actions and the leaf's chain value is scored on the outer chain.
    Buckets ascend by their own minimum action, so it drops straight into the
    REUSED ``build_positions.dedupe_tie_actions`` validator.
    """
    by_key: dict = {}
    for a in sorted(int(x) for x in actions):
        s1, _ = game.get_next_state(board, a)
        by_key.setdefault(game.string_representation(s1), []).append(a)
    groups = sorted((sorted(v) for v in by_key.values()), key=lambda g: g[0])
    return {"action_groups": groups, "repr_actions": [g[0] for g in groups],
            "n_distinct_afterstates": len(groups),
            "all_transposition": len(groups) == 1}


def arms_from_ranking(ranked: list, champ_action: int, repr_of: dict,
                      k_arms: int = K_ARMS) -> list:
    """DESIGN §3.1: the top-K **distinct-afterstate** actions of `ranked`, with
    the champion's pick unioned in and forced to arm 0.

    ``repr_of`` is ``dedupe_tie_actions``' own action -> representative map, so
    "distinct" here means exactly what the dedupe means by it. The champion is
    walked first, so it can never be displaced by a transposition partner —
    ``arms[0] == champ_action`` is an invariant of this function.
    """
    champ_action = int(champ_action)
    order = [champ_action] + [a for a in ranked if int(a) != champ_action]
    seen, arms = set(), []
    for a in order:
        g = repr_of.get(int(a), int(a))
        if g in seen:
            continue
        seen.add(g)
        arms.append(int(a))
        if len(arms) >= int(k_arms):
            break
    if arms[0] != champ_action:                       # unreachable; a defect if hit
        raise AssertionError("arm[0] is not the champion pick")
    return arms


# --------------------------------------------------------------------------- #
# worker (mode `arms`)                                                          #
# --------------------------------------------------------------------------- #
_G: dict = {}


def _init(game_kwargs: dict, rules_profile: str, arm_builder: str, k_arms: int,
          nice: int) -> None:
    _G.update(game_kwargs=dict(game_kwargs or {}), rules_profile=rules_profile,
              arm_builder=arm_builder, k_arms=int(k_arms))
    try:
        os.nice(int(nice))
    except OSError:
        pass


def _leaf_ranking(game, board, seat: int) -> list:
    """The §3.1 fallback ranking — ``chain_census.chain_values`` descending.

    Ties resolve to the LOWEST action index (``-a`` in the key), the same
    convention ``chain_census.argmax_chain`` uses, so the fallback's arm 0 is the
    leaf's own argmax whenever the champion agrees with it. The leaf is built
    ONCE per worker (``build_leaf`` re-runs the R1/R7 provenance guard per call).
    """
    import chain_census as CC

    if "leaf" not in _G:
        _G["leaf"] = CC.build_leaf()[0]
    leaf = _G["leaf"]
    vals = CC.chain_values(game, board, int(seat), lambda st: leaf(st, int(seat)))
    return [int(a) for a, _v, _c in sorted(vals, key=lambda t: (t[1], -t[0]),
                                           reverse=True)]


#: DESIGN §3.1's BUILD RISK, made mechanical. The pooled root Q lives only in the
#: PYTHON agent's `fair_agent.pooled_q_argmax` call (the house pool-spy hook); the
#: RUST FairAgent exposes `last_pooled_visits` (pooled N) and no pooled W at all.
POOLED_Q_BACKEND_REFUSAL = """
⛔ REFUSING --arm-builder pooled_q ON A NON-PYTHON CHAMPION BACKEND.

DESIGN §3.1 named this as the build risk; it is REAL and it fires here, before a
single 13.8 s champion search is paid for:

  * the resolved champion execution is backend={backend!r}
    (`mirror_protocol.resolve_execution("inherit", profile="desktop")` ->
     `champion_factory.factory_default_backend()` -> governance/PRODUCTION.yaml
     `champion.fair_deploy.backend`);
  * `champ_picks.champion_search_pick` -- the seam DESIGN §6.3 mandates reusing --
    passes `**ex.factory_kwargs()`, so the search runs in Rust;
  * the pooled root Q is not readable there: `fair_agent.pooled_q_argmax` (the
    python hook the house pool spy wraps) is never called, and the rust agent's
    `stats()` carries `last_pooled_visits` -- pooled N -- with NO pooled W.
  * DESIGN §6.3 states "No rust change is required", and DESIGN §6.3 also forbids
    editing `champ_picks.py` / `build_positions.py` in a live tree.

⇒ THE PRE-COMMITTED §3.1 FALLBACK IS THE INSTRUMENT THAT CAN ACTUALLY RUN:

      --arm-builder leaf_topk

It is WEAKER (it hands the arbiter the leaf's own shortlist) and DESIGN §12 rule 3
says it engages ONCE, at the pilot, and is then FROZEN AND STAMPED. That is an
ORCHESTRATOR decision, not something this builder may take silently -- which is
why this is a refusal and not an automatic downgrade. Whichever builder runs is
stamped on the plan and on every rid, and READ_RULE §4.3 A item 7 requires the
read-out to print it on every branch.
"""


PRODUCTION_YAML = REPO / "governance/PRODUCTION.yaml"


def production_champion_block(path=PRODUCTION_YAML) -> dict:
    """The resolved champion of record, read off ``governance/PRODUCTION.yaml``.

    ⚠️ ``G-CHAMP`` wants the resolved ``tiearb`` block stamped on every row, and
    DESIGN §3.2 quotes it as ``enabled: true, B: 64, J: 4, eps: 0.0``. That block
    is **NOT on the built agent's manifest** here: ``make_production_champion``
    takes ``tiearb`` as a KEYWORD and does not read the YAML block itself, and
    ``champ_picks.champion_search_pick`` (the mandated seam) does not pass it — so
    ``manifest["cand_tiearb"]`` is absent by construction. The governance file is
    therefore the address of record for this stamp, and the read-out says so.
    At a NON-TIED ply this is behaviourally inert either way: ``detect_tie`` is
    false at ``eps = 0.0``, so the arbiter cannot fire on the incumbent's pick.
    """
    import yaml

    ch = yaml.safe_load(Path(path).read_text())["champion"]
    fd = ch.get("fair_deploy") or {}
    return {
        "leaf_hash": ch.get("leaf_hash"),
        "leaf_hash_dialect": "harness_leaf_hash",
        "fair_deploy": {"k_dets": fd.get("k_dets"),
                        "sims_per_det": fd.get("sims_per_det"),
                        "backend": fd.get("backend")},
        "tiearb": {k: (fd.get("tiearb") or {}).get(k)
                   for k in ("enabled", "B", "J", "mode", "salt", "eps")},
        "tiearb_address": ("governance/PRODUCTION.yaml champion.fair_deploy.tiearb "
                           "(NOT the built agent's manifest -- see "
                           "build_everyply_corpus.production_champion_block)"),
        "source": str(path),
    }


def check_arm_builder_backend(arm_builder: str) -> dict:
    """Resolve the champion's execution backend and refuse an unrunnable builder."""
    from carcassonne_ai import mirror_protocol as MP

    ex = MP.resolve_execution("inherit", profile="desktop", rust_threads=1)
    if arm_builder == "pooled_q" and ex.backend != "python":
        raise SystemExit(POOLED_Q_BACKEND_REFUSAL.format(backend=ex.backend))
    return {"backend": ex.backend, "rust_threads": ex.rust_threads,
            "source": ex.source, "arm_builder": arm_builder}


def _cell(item: tuple) -> dict:
    """One SELECTION row -> one champion-pick + arm-set record.

    BEST-EFFORT BY CONTRACT (``champ_picks._cell``'s own contract, verbatim): any
    per-position failure is recorded with ``error`` set and never takes the pool
    down. A position with an ``error`` is DROPPED and COUNTED, never zero-filled —
    zero-fill is the §5.2 economy, which is a different thing entirely.
    """
    rid, deck_seed, ply, seat, actions = item
    rec = {"rid": rid, "deck_seed": int(deck_seed), "ply": int(ply), "seat": int(seat)}
    t0 = time.time()
    try:
        import numpy as np
        import root_replay as RR
        from carcassonne_ai import fair_agent as FA

        import champ_picks as CP

        game, board = RR.replay_actions(int(deck_seed), actions, int(ply),
                                        game_kwargs=_G.get("game_kwargs") or None)
        rec["checksum"] = game.string_representation(board)
        legal = sorted(int(x) for x in np.flatnonzero(game.get_valid_moves(board)))
        if len(legal) < 2:
            raise ValueError(f"n_legal={len(legal)} < 2 -- not an arbitrable ply")
        rec["n_legal_realized"] = len(legal)

        spy = PoolSpy(FA).install()
        try:
            champ_action, k_dets, sims, backend, secs = CP.champion_search_pick(
                game, board, int(deck_seed), int(seat), actions, int(ply))
        finally:
            spy.restore()
        rec.update(champ_action=int(champ_action), champ_secs=round(secs, 3),
                   k_dets=int(k_dets), sims_per_det=int(sims), backend=backend)

        # ---- the arm ranking ------------------------------------------------ #
        if _G["arm_builder"] == "pooled_q":
            if not spy.calls:
                # No pooled stats were produced: a forced move, or the exact
                # endgame latch (k_remaining <= 2), or a rust-mirror search that
                # never crosses `pooled_q_argmax`. Not recoverable per position —
                # the fallback is a RUN-level switch frozen at the pilot (§12.3).
                raise ValueError("no_pooled_stats: pooled_q_argmax was never called")
            agg_n, agg_w, min_visits = spy.calls[-1]
            ranked = pooled_ranking(agg_n, agg_w, min_visits)
            rec["pooled_n_actions"] = len(agg_n)
            rec["pooled_rank_of_champ"] = (ranked.index(int(champ_action))
                                           if int(champ_action) in ranked else None)
            if rec["pooled_rank_of_champ"] != 0:
                # The identity `ranked[0] == pooled_q_argmax(...)` is exact; a
                # violation is an instrument defect, and G-COVER is its detector.
                rec["pooled_rank_defect"] = True
        else:
            ranked = _leaf_ranking(game, board, int(seat))
            rec["pooled_rank_of_champ"] = None

        # ---- afterstate dedupe over the FULL legal set (REUSED) -------------- #
        entry = afterstate_entry(game, board, legal)
        ded = BP.dedupe_tie_actions(legal, entry)
        rec["n_distinct_afterstates"] = ded["n_distinct"]
        rec["all_transposition"] = ded["all_transposition"]
        if ded["n_distinct"] < 2:
            rec.update(ok=False, dropped="lt2_distinct", error=None,
                       elapsed_secs=round(time.time() - t0, 3))
            return rec

        arms = arms_from_ranking(ranked, champ_action, ded["repr_of"], _G["k_arms"])
        if len(arms) < 2:
            rec.update(ok=False, dropped="lt2_arms", error=None,
                       elapsed_secs=round(time.time() - t0, 3))
            return rec

        # PLAN_J_gt_4 §8 requirement (2), the house record shape `build_arms_index`
        # reads: stamp the SEEDED J=4 subset of the deduped candidate pool as a
        # witness. ⚠️ It is a WITNESS, not the arm selector — DESIGN §3.1 selects
        # the top-K by pooled root Q, which is a RANKING, not a seeded draw.
        cands = [a for a in ded["kept"] if a != int(champ_action)]
        sub_j4, capped_at_4, dropped_j4 = BP._seeded_cap(rid, cands, K_ARMS)
        rec.update(
            ok=True, error=None, arms=arms,
            arm_builder=_G["arm_builder"],
            dedupe_kept=ded["kept"], dedupe_dropped_actions=ded["dropped"],
            dropped_actions=[a for a in ded["kept"] if a not in arms],
            capped=bool(len(ded["kept"]) > len(arms)),
            subset_j4=[int(champ_action)] + list(sub_j4),
            capped_at_4=bool(capped_at_4), dropped_j4=list(dropped_j4),
            cap_seed=BP._stable_seed(BP.CAP_SEED_TAG, rid, BP.CAP_SEED_DATE),
            elapsed_secs=round(time.time() - t0, 3))
        return rec
    except Exception as exc:                                     # noqa: BLE001
        rec.update(ok=False, error=f"{type(exc).__name__}: {exc}",
                   elapsed_secs=round(time.time() - t0, 3))
        return rec


# --------------------------------------------------------------------------- #
# assembly (mode `arms`)                                                        #
# --------------------------------------------------------------------------- #
def position_from(row: dict, rec: dict, actions: list, rules_profile: str) -> dict:
    """One ``build_positions``-shaped position dict.

    ⚠️ ``stratum`` is the CORPUS-shape stratum the reused seams branch on
    (``write_leg_files``: e4 -> archive_path, selfplay -> actions;
    ``cost_plan``: n_selfplay pays ``t_champ``). DESIGN §2.2's leaf-gap stratum
    rides as ``gap_stratum`` and is the one κ is population-reweighted over.
    """
    arms = [int(a) for a in rec["arms"]]
    return {
        "rid": row["rid"], "root_id": str(row["game_id"]),
        "deck_seed": int(row["deck_seed"]), "ply": int(row["ply"]),
        "seat": int(row["seat"]), "arms": arms, "checksum": rec["checksum"],
        "rules_profile": rules_profile, "stratum": CORPUS_STRATUM,
        "source": "champ_games", "game_label": str(row["game_id"]),
        "actions": [int(a) for a in actions],
        "champ_action": int(rec["champ_action"]), "champ_arm_index": 0,
        "champ_outside_tieset": False, "champ_pick_missing": False,
        "champ_arm_action": int(rec["champ_action"]),
        "k_remaining": row.get("k_remaining"), "phase_bucket": row.get("phase_bucket"),
        "tercile": row.get("tercile"), "n_legal": row.get("n_legal"),
        "n_cand": rec.get("n_legal_realized"), "tie_size_exact": None,
        "gap": row.get("gap"),
        "capped": bool(rec.get("capped")),
        "dropped_actions": list(rec.get("dropped_actions") or []),
        "dedupe_dropped_actions": list(rec.get("dedupe_dropped_actions") or []),
        "n_distinct_afterstates": int(rec["n_distinct_afterstates"]),
        "arms_full": [int(a) for a in rec.get("dedupe_kept") or arms],
        "subset_j4": [int(a) for a in rec.get("subset_j4") or arms],
        "subset_j4_id": BP._subset_id(row["rid"], rec.get("subset_j4") or arms),
        "capped_at_4": bool(rec.get("capped_at_4")),
        "cap_seed": rec.get("cap_seed"),
        "archive_path": None,
    }


def arms_index_with_extras(positions: list, rows_by_rid: dict, recs_by_rid: dict,
                           arm_builder: str, champ_block: dict | None = None) -> dict:
    """``build_positions.build_arms_index`` (REUSED, unmodified) + the every-ply
    fields the analyser and READ_RULE §3 need on every rid."""
    idx = BP.build_arms_index(positions)
    for rid, entry in idx.items():
        row, rec = rows_by_rid[rid], recs_by_rid[rid]
        entry.update({
            "gap_stratum": row["stratum"],          # DESIGN §2.2 A/B/C
            "slice": row["slice"],                  # DESIGN §6.4 dev/holdout
            "chunk": int(row["chunk"]),
            "champ_pos": 0,                         # G-COVER's address
            "arm_builder": arm_builder,             # §4.3 A item 7
            "pooled_rank_of_champ": rec.get("pooled_rank_of_champ"),
            "champ_k_dets": rec.get("k_dets"),
            "champ_sims_per_det": rec.get("sims_per_det"),
            "champ_backend": rec.get("backend"),
            # G-CHAMP / G-EPOCH stamp every row, never hardcode (champ_picks'
            # own convention). Constant across rows IS the gate.
            "champ_leaf_hash": (champ_block or {}).get("leaf_hash"),
            "champ_tiearb": json.dumps((champ_block or {}).get("tiearb"),
                                       sort_keys=True),
            "rules_profile_stamp": entry.get("rules_profile"),
            "band": BAND, "corpus": CORPUS,         # BAND_NOTE §3
        })
    return idx


def build_arms_mode(args) -> dict:
    from carcassonne_ai import rules_profile as RP

    prof = RP.activate(args.rules_profile)
    if RP.r9_env_on() != prof.r9_env_expected:
        raise SystemExit(
            f"CARCASSONNE_FIX_R9 is latched at {int(RP.r9_env_on())} but profile "
            f"{prof.name!r} expects {int(prof.r9_env_expected)} -- export it before "
            "launch, one process per rules epoch.")

    exec_block = check_arm_builder_backend(args.arm_builder)
    champ_block = production_champion_block()
    print(f"[everyply-corpus] champion: {champ_block['fair_deploy']} "
          f"backend={exec_block['backend']} tiearb={champ_block['tiearb']}", flush=True)

    rows = load_selection(args.selection, args.chunk, args.limit)
    if not rows:
        raise SystemExit(f"REFUSING: no SELECTION rows for chunk={args.chunk!r}")
    champ_games = BP.load_champ_games(args.champ_games)

    out_dir = Path(args.out_dir)
    records_dir = out_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    jobs, rows_by_rid = [], {}
    for row in rows:
        rows_by_rid[row["rid"]] = row
        acts = champ_games.get(int(row["deck_seed"]))
        if acts is None:
            raise SystemExit(f"REFUSING: deck_seed={row['deck_seed']} absent from "
                             f"{args.champ_games}")
        jobs.append((row["rid"], int(row["deck_seed"]), int(row["ply"]),
                     int(row["seat"]), acts))
    todo = [j for j in jobs
            if not (args.resume and (records_dir / f"{j[0]}.json").is_file())]
    print(f"[everyply-corpus] chunk={args.chunk} n={len(jobs)} to_do={len(todo)} "
          f"arm_builder={args.arm_builder}", flush=True)

    t0 = time.time()
    if todo:
        w = max(1, min(int(args.workers), len(todo)))
        ctx = mp.get_context("fork")
        with ctx.Pool(w, initializer=_init,
                      initargs=(prof.game_kwargs(), args.rules_profile,
                                args.arm_builder, args.k_arms, args.nice)) as pool:
            for i, rec in enumerate(pool.imap_unordered(_cell, todo), 1):
                p = records_dir / f"{rec['rid']}.json"
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(rec, sort_keys=True))
                os.replace(tmp, p)
                print(f"[{i}/{len(todo)}] {rec['rid']} "
                      f"{'ok' if rec.get('ok') else rec.get('dropped') or rec.get('error')}"
                      f" arms={rec.get('arms')} {rec.get('elapsed_secs')}s", flush=True)

    # Re-read EVERY record so --resume assembles the full plan, not this slice.
    recs_by_rid, positions = {}, []
    n_dropped_lt2, n_error, n_rank_defect = 0, 0, 0
    dropped_rows = []
    for row in rows:
        p = records_dir / f"{row['rid']}.json"
        if not p.is_file():
            n_error += 1
            continue
        rec = json.loads(p.read_text())
        if rec.get("pooled_rank_defect"):
            n_rank_defect += 1
        if not rec.get("ok"):
            if rec.get("dropped") == "lt2_distinct":
                n_dropped_lt2 += 1
                dropped_rows.append({
                    "rid": row["rid"], "stratum": CORPUS_STRATUM,
                    "gap_stratum": row["stratum"], "root_id": str(row["game_id"]),
                    "reason": "lt2_distinct_afterstates",
                    "n_distinct_afterstates": rec.get("n_distinct_afterstates"),
                    "action_played_outside_tieset": False})
            else:
                n_error += 1
            continue
        recs_by_rid[row["rid"]] = rec
        positions.append(position_from(row, rec, rec_actions(champ_games, row),
                                       args.rules_profile))
    if not positions:
        raise SystemExit("REFUSING: zero positions built -- nothing to price")

    legs = BP.write_leg_files(positions, out_dir)
    plan = BP.cost_plan(positions, cap_j=args.k_arms, sample_seed=args.seed,
                        playout_secs=float(args.playout_secs), m_worlds=args.m,
                        workers=(int(args.workers),))
    n_planned = len(rows)
    plan.update({
        "schema": SCHEMA, "design_doc": DESIGN_DOC, "read_rule": READ_RULE_DOC,
        "mode": "arms", "chunk": args.chunk, "rules_profile": args.rules_profile,
        "files": legs["files"], "max_arms": legs["max_arms"],
        "k_arms": int(args.k_arms), "m_worlds": int(args.m),
        "arm_builder": args.arm_builder,
        "champion": champ_block, "execution": exec_block,
        "band": BAND, "corpus": CORPUS,
        "band_note": ("NO band is claimed on any branch (BAND_NOTE.md): every "
                      "position is an offline replay of the already-claimed, "
                      "already-RETIRED band 28000000000."),
        # `run_tiletie.check_positions` REFUSES a plan built without the DESIGN §6
        # threat-3 dedupe. It is applied here over the FULL legal action set.
        "afterstate_dedupe": {
            "applied": True,
            "scope": "full legal action set at the ply (not a tie set)",
            "key": "game.string_representation of the TILE successor",
            "n_qualifying_before_drop": n_planned,
            "n_dropped_all_transposition": n_dropped_lt2,
            "n_dropped_with_action_played_outside_tieset": 0,
        },
        # G-DISTINCT's substrate, and the §4.3 A item 7 print.
        "everyply": {
            "n_planned": n_planned, "n_built": len(positions),
            "n_dropped_lt2_distinct": n_dropped_lt2,
            "dropped_lt2_distinct_rate": n_dropped_lt2 / n_planned,
            "n_error": n_error, "n_pooled_rank_defect": n_rank_defect,
            "arm_builder": args.arm_builder,
        },
        "code_rev": _git_rev(), "generated_utc": _utc(),
        "wall_secs": round(time.time() - t0, 1),
    })
    (out_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=1, sort_keys=True))
    (out_dir / "ARMS.json").write_text(json.dumps(
        arms_index_with_extras(positions, rows_by_rid, recs_by_rid, args.arm_builder,
                               champ_block),
        indent=1, sort_keys=True))
    (out_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(
        {"schema": SCHEMA, "note": ("positions dropped for < 2 distinct afterstates "
                                    "(G-DISTINCT's substrate) -- counted and reported "
                                    "in EVERY case, never silently discarded."),
         "rows": dropped_rows}, indent=1, sort_keys=True))
    (out_dir / "CORPUS_SUMMARY.json").write_text(json.dumps(
        {"schema": SCHEMA, **plan["everyply"], "chunk": args.chunk,
         "generated_utc": _utc()}, indent=1, sort_keys=True))
    (out_dir / "champ_picks.jsonl").write_text("".join(
        json.dumps(recs_by_rid[r["rid"]], sort_keys=True) + "\n"
        for r in rows if r["rid"] in recs_by_rid))
    print(f"[everyply-corpus] built {len(positions)}/{n_planned} positions "
          f"({n_dropped_lt2} dropped <2 distinct, {n_error} error) -> {out_dir}")
    return plan


def rec_actions(champ_games: dict, row: dict) -> list:
    return champ_games[int(row["deck_seed"])]


def resolve_records_root(root, judge: str) -> Path:
    """Accept either ``<out_root>`` or ``<out_root>/<judge>``.

    ``run_tiletie`` writes ``<out_root>/<judge>/<profile>/leg<r>/records/*.json``
    while ``analyze_tiletie.discover_records`` walks from ``<profile>``, so the
    judge level has to be stepped into. ⚠️ This GENERALISES
    ``analyze_tiearb.resolve_records_root``, which hardcodes ``tier1-greedy`` and
    therefore cannot resolve a ``clair-puct`` root — that generalisation is the
    only reason it is written out rather than imported, and it is the single
    implementation shared by this module and ``analyze_everyply.py``.
    """
    p = Path(root)
    cand = p / judge
    return cand if cand.is_dir() else p


# --------------------------------------------------------------------------- #
# mode `selective` — DESIGN §5.2                                                #
# --------------------------------------------------------------------------- #
def selective_arms(matrix_arb: list, champ_pos: int, m: int, parity_base: int = 1):
    """``{champ} ∪ {a_arb(fold 1), a_arb(fold 2)}`` as ARM-ORDER POSITIONS.

    ``a_arb`` is ``analyze_tiletie.crossfit_regret``'s own ``a_plus`` — the same
    imported call, and therefore the same argmax tie-break, the analyser will
    make. Nothing here reads a clair-puct value: that is precisely what keeps the
    §5.2 economy non-circular (DESIGN §5.2 property 2).
    """
    picks = []
    for swap in (False, True):
        sel, eva = AT.parity_indices(m, base=parity_base, swap=swap)
        _h, a_plus = AT.crossfit_regret(matrix_arb, sel, eva, champ_pos)
        picks.append(int(a_plus))
    keep = sorted({int(champ_pos), *picks})
    return keep, picks


def build_selective_mode(args) -> dict:
    plan_dir = Path(args.plan_dir)
    bundle = AT.load_plan(plan_dir)                    # REUSED (asserts the dedupe)
    arms_index = bundle["arms"]
    arb_by_rid, present, not_ok = AT.discover_records(
        resolve_records_root(args.arb_records, "tier1-greedy"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    positions, zero_rows, counts = [], [], {
        "planned": 0, "absent_arb": 0, "partial_arb": 0, "priced": 0, "zero": 0}
    src_lines = {}
    for key, info in sorted((bundle["plan"].get("files") or {}).items()):
        for ln in Path(info["path"]).read_text().splitlines():
            if ln.strip():
                o = json.loads(ln)
                src_lines.setdefault(o["rid"], o)

    for rid, meta in sorted(arms_index.items()):
        counts["planned"] += 1
        arms = [int(a) for a in meta["arms"]]
        need = list(range(1, len(arms)))
        legs = arb_by_rid.get(rid, {})
        have = sorted(k for k in legs if k in need)
        if not have:
            counts["absent_arb"] += 1
            continue
        if [r for r in need if r not in legs]:
            counts["partial_arb"] += 1
            continue
        ref = legs[have[0]]
        matrix = [list(ref["values_a"])] + [list(legs[r]["values_b"]) for r in have]
        arm_order = [0] + have
        keep_pos, fold_picks = selective_arms(matrix, 0, int(ref["m"]), args.parity_base)
        keep_arms = [arms[arm_order[i]] for i in keep_pos]
        # champ (arm 0) is in `keep_pos` by construction, and `keep_pos` is sorted,
        # so keep_arms[0] is the champion action -- write_leg_files' arm 0 contract.
        src = src_lines.get(rid)
        if src is None:
            raise SystemExit(f"REFUSING: rid {rid!r} has no source leg line in {plan_dir}")
        positions.append({
            "rid": rid, "root_id": meta["root_id"], "deck_seed": int(src["deck_seed"]),
            "ply": int(src["ply"]), "seat": int(src["root_player"]),
            "arms": keep_arms, "checksum": src["checksum"],
            "rules_profile": meta["rules_profile"], "stratum": meta["stratum"],
            "source": meta.get("source", "champ_games"),
            "game_label": meta.get("game_label"), "actions": src["actions"],
            "champ_action": arms[0], "champ_arm_index": 0,
            "champ_outside_tieset": False, "champ_arm_action": arms[0],
            "k_remaining": meta.get("k_remaining"),
            "phase_bucket": meta.get("phase_bucket"), "tercile": meta.get("tercile"),
            "n_legal": meta.get("n_legal"), "n_cand": meta.get("n_cand"),
            "tie_size_exact": meta.get("tie_size_exact"), "gap": meta.get("gap"),
            "capped": bool(meta.get("capped")),
            "dropped_actions": [a for a in arms if a not in keep_arms],
            "dedupe_dropped_actions": meta.get("dedupe_dropped_actions") or [],
            "n_distinct_afterstates": meta.get("n_distinct_afterstates"),
            "arms_full": arms, "subset_j4": meta.get("subset_j4") or arms,
            "subset_j4_id": meta.get("subset_j4_id"),
            "capped_at_4": bool(meta.get("capped_at_4")),
            "cap_seed": meta.get("cap_seed"), "archive_path": None,
            # every-ply extras, carried so the IF ARMS.json is self-describing
            "_extras": {
                "gap_stratum": meta.get("gap_stratum"), "slice": meta.get("slice"),
                "chunk": meta.get("chunk"), "champ_pos": 0,
                "arm_builder": meta.get("arm_builder"),
                "band": BAND, "corpus": CORPUS,
                "arms_to_price": keep_arms,
                "arm_source_index": {str(a): arms.index(a) for a in keep_arms},
                "a_arb_folds": [arms[arm_order[i]] for i in fold_picks],
                "a_arb_fold_positions": fold_picks,
                "zero_filled": len(keep_arms) == 1,
                # carried forward verbatim so the IF plan is self-describing too
                **{k: meta.get(k) for k in (
                    "champ_leaf_hash", "champ_tiearb", "champ_k_dets",
                    "champ_sims_per_det", "champ_backend", "pooled_rank_of_champ")},
            },
        })
        if len(keep_arms) == 1:
            counts["zero"] += 1
            zero_rows.append({"rid": rid, "root_id": meta["root_id"],
                              "gap_stratum": meta.get("gap_stratum"),
                              "slice": meta.get("slice"),
                              "arms_to_price": keep_arms,
                              "a_arb_folds": [arms[arm_order[i]] for i in fold_picks],
                              "kappa": 0.0,
                              "why": ("both parity folds' a_arb ARE the champion arm, "
                                      "so kappa[p] = 0 IDENTICALLY -- no clair-puct "
                                      "value is needed to know it. ZERO-FILLED, never "
                                      "dropped (DESIGN §5.2 property 1 / G-ZEROFILL).")})
        else:
            counts["priced"] += 1

    legs = BP.write_leg_files(positions, out_dir)      # singletons emit NO leg
    plan = BP.cost_plan(positions, cap_j=args.k_arms, sample_seed=args.seed,
                        playout_secs=float(args.playout_secs), m_worlds=args.m,
                        workers=(int(args.workers),))
    idx = BP.build_arms_index(positions)
    for p in positions:
        idx[p["rid"]].update(p["_extras"])
    plan.update({
        "schema": SCHEMA, "design_doc": DESIGN_DOC, "read_rule": READ_RULE_DOC,
        "mode": "selective", "files": legs["files"], "max_arms": legs["max_arms"],
        "k_arms": int(args.k_arms), "m_worlds": int(args.m),
        "source_plan_dir": str(plan_dir), "arb_records": str(args.arb_records),
        "arb_records_present": present, "arb_records_not_ok": not_ok,
        "band": BAND, "corpus": CORPUS,
        "afterstate_dedupe": dict(bundle["plan"]["afterstate_dedupe"]),
        "selective": {**counts,
                      "mean_arms_to_price": (sum(len(p["arms"]) for p in positions)
                                             / len(positions)) if positions else None,
                      "note": ("DESIGN §5.2: arms_to_price = {champ} U {a_arb(fold1), "
                               "a_arb(fold2)}, chosen by tier1-greedy ALONE. No "
                               "clair-puct value influences which arms get priced.")},
        "code_rev": _git_rev(), "generated_utc": _utc(),
    })
    (out_dir / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=1, sort_keys=True))
    (out_dir / "ARMS.json").write_text(json.dumps(idx, indent=1, sort_keys=True))
    (out_dir / "DROPPED_ALL_TRANSPOSITION.json").write_text(json.dumps(
        {"schema": SCHEMA, "note": "carried from the arms plan; nothing is dropped here.",
         "rows": bundle["dropped"]["rows"]}, indent=1, sort_keys=True))
    zf = {"schema": SCHEMA, "design_doc": DESIGN_DOC, "plan_dir": str(plan_dir),
          "n_planned": counts["planned"], "n_priced": counts["priced"],
          "n_zero": counts["zero"], "rows": zero_rows, "generated_utc": _utc()}
    (out_dir / "ZEROFILL.json").write_text(json.dumps(zf, indent=1, sort_keys=True))
    if args.zerofill_out:
        Path(args.zerofill_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.zerofill_out).write_text(json.dumps(zf, indent=1, sort_keys=True))
    print(f"[everyply-corpus] selective: {counts['priced']} priced / "
          f"{counts['zero']} zero-filled of {counts['planned']} -> {out_dir}")
    return plan


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=("arms", "selective"), required=True)
    ap.add_argument("--out-dir", required=True)
    # mode arms
    ap.add_argument("--selection", default=str(DEFAULT_SELECTION))
    ap.add_argument("--chunk", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--rules-profile", default=DEFAULT_RULES_PROFILE)
    ap.add_argument("--champ-games", default=str(DEFAULT_CHAMP_GAMES))
    ap.add_argument("--arm-builder", default="pooled_q", choices=ARM_BUILDERS,
                    help="DESIGN §3.1: `leaf_topk` is the PRE-COMMITTED fallback and "
                         "engages ONCE, at the §12 pilot, then FREEZES.")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    # mode selective
    ap.add_argument("--plan-dir", default=None)
    ap.add_argument("--arb-records", default=None)
    ap.add_argument("--zerofill-out", default=None)
    ap.add_argument("--parity-base", type=int, default=1)
    # shared
    ap.add_argument("--k-arms", type=int, default=K_ARMS)
    ap.add_argument("--m", type=int, default=M_WORLDS)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--nice", type=int, default=19)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--playout-secs", type=float, default=0.178232,
                    help="cost-model c only (DESIGN §5.1 c_ARB); prices nothing")
    a = ap.parse_args(argv)
    if a.mode == "arms" and a.chunk is None and a.limit <= 0:
        raise SystemExit("REFUSING: --mode arms needs --chunk (or --limit for the pilot)")
    if a.mode == "selective" and not (a.plan_dir and a.arb_records):
        raise SystemExit("REFUSING: --mode selective needs --plan-dir and --arb-records")
    return a


def main(argv=None) -> int:
    a = parse_args(argv)
    if a.mode == "arms":
        # MUST precede any carcassonne_ai import (R9 is import-latched and the
        # production leaf env is import-frozen).
        import chain_census as CC

        CC.prepare_env(a.rules_profile)
        build_arms_mode(a)
    else:
        build_selective_mode(a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
