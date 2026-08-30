"""S1 §9.2(c) `R7` — the J-RULES-PRIOR EXPANSION CENSUS, harness side.

Merge-review finding R7 (2026-08-30): a played `jrules_prior_scope='opp'` cell
had NO play-derived witness that its arm bound. `carc_core::search` counted the
expansions, but `fair::search_worlds` discarded the counters, `FairAgentRs.stats`
never emitted them, and a cell's manifest is only a CONFIG ECHO — the exact
shape that burned the FPU knob (never bound) and the phasegate smoke
(adjudicated nothing). Surface B is especially good at hiding it: it moves no
leaf hash, and under `scope="opp"` it moves no ROOT prior either, so a
dead-wired arm plays as the champion and passes every other gate looking well.

The rust legs live in `carc_core`:
  * `search::tests::s1_*`               — the partition inside ONE tree
  * `fair::tests::s1_jr_expansion_census_folds_over_worlds_and_decisions`
                                        — the same identity ON THE PIMC FOLD
  * `search::session::tests::r6_*`      — the R6 carried-session refusal

This file pins the HARNESS half — the aggregation from `FairAgentRs.stats()` to
the exact `summary.json` shape the S1 G3 gate reads — with a STUBBED stats dict,
so it needs no `carc_rs` wheel and cannot go stale against one.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "classical_search"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

efp = importlib.import_module("eval_fair_puct")


ZERO = {"total": 0, "own_mover": 0, "boosted": 0}


def _stub(stats: dict | None, *, wrapped: bool = False):
    """An agent whose `stats()` returns `stats`. `wrapped=True` hides the rust
    agent behind `._prefix`, the `_MarginalizedHandoff` shape; `stats=None`
    means no rust agent at all (the python backend)."""
    if stats is None:
        return SimpleNamespace()
    rs = SimpleNamespace(stats=lambda: dict(stats))
    return SimpleNamespace(_prefix=SimpleNamespace(_rs=rs)) if wrapped \
        else SimpleNamespace(_rs=rs)


def _armed_stats(total=900, own=400, boosted=500):
    """A scope="opp" side's stats(): boosted == total - own_mover."""
    return {"jr_expansions_total": total, "jr_expansions_own_mover": own,
            "jr_expansions_boosted": boosted, "move_idx": 7}


# --------------------------------------------------------------------------- #
# 1. the per-side read                                                        #
# --------------------------------------------------------------------------- #
def test_telemetry_returns_exactly_the_three_int_keys():
    got = efp._jr_expansions_telemetry(_stub(_armed_stats()), side="candidate",
                                       armed=True)
    assert got == {"total": 900, "own_mover": 400, "boosted": 500}
    assert all(type(v) is int for v in got.values())


def test_telemetry_finds_the_agent_behind_a_handoff_wrapper():
    """The python backend wraps the agent in `_MarginalizedHandoff._prefix`;
    the rust candidate IS the agent. Both must resolve."""
    bare = efp._jr_expansions_telemetry(_stub(_armed_stats()), side="c", armed=True)
    wrapped = efp._jr_expansions_telemetry(_stub(_armed_stats(), wrapped=True),
                                           side="c", armed=True)
    assert bare == wrapped == {"total": 900, "own_mover": 400, "boosted": 500}


def test_an_unarmed_side_reads_all_zero_and_never_a_missing_key():
    """⚠️ The counters live inside the `dose != 0` branch, so an unarmed side —
    the opponent of every S1 cell — reports all-zero. Its assertable invariant
    is `boosted == 0`, NOT `total > 0`. Both the no-rust-agent case (python
    backend) and the pre-R7-wheel case must still yield the full key set."""
    assert efp._jr_expansions_telemetry(_stub(None), side="opponent",
                                        armed=False) == ZERO
    stale = {"move_idx": 3, "heur_moves": 40}   # a wheel predating R7
    assert efp._jr_expansions_telemetry(_stub(stale), side="opponent",
                                        armed=False) == ZERO
    # A champion side that DOES carry the counters reads its real zeros.
    champ = {"jr_expansions_total": 0, "jr_expansions_own_mover": 0,
             "jr_expansions_boosted": 0}
    assert efp._jr_expansions_telemetry(_stub(champ), side="opponent",
                                        armed=False) == ZERO


@pytest.mark.parametrize("stats,match", [
    (None, "no FairAgentRs"),
    ({"move_idx": 3}, "STALE"),
])
def test_an_armed_side_fails_loud_rather_than_stamping_zeros(stats, match):
    """Zeros on an ARMED side would grade a champion-vs-champion null wearing
    the arm's name — the J13 lesson. Raise instead."""
    with pytest.raises(RuntimeError, match=match):
        efp._jr_expansions_telemetry(_stub(stats), side="candidate", armed=True)


# --------------------------------------------------------------------------- #
# 2. the cell-level sum                                                       #
# --------------------------------------------------------------------------- #
def test_sum_treats_a_legacy_record_as_zeros_not_as_absent():
    recs = [
        SimpleNamespace(cand_jr_expansions={"total": 10, "own_mover": 4, "boosted": 6}),
        SimpleNamespace(cand_jr_expansions=None),            # pre-R7 record
        SimpleNamespace(),                                    # field never existed
        SimpleNamespace(cand_jr_expansions={"total": 5, "own_mover": 2, "boosted": 3}),
    ]
    assert efp._jr_expansions_sum(recs, "cand_jr_expansions") == \
        {"total": 15, "own_mover": 6, "boosted": 9}
    # The partition survives the sum term by term (scope="opp").
    got = efp._jr_expansions_sum(recs, "cand_jr_expansions")
    assert got["boosted"] == got["total"] - got["own_mover"]


# --------------------------------------------------------------------------- #
# 3. THE CONTRACT — the exact summary.json shape the G3 gate reads            #
# --------------------------------------------------------------------------- #
def _result(seed, a_seat, *, cand=None, opp=None):
    return efp.GameResult(
        seed=seed, a_seat=a_seat, info="fair", exact_k=4, k_dets=4, sims=256,
        rung_sims=800, score_p0=90, score_p1=80, diff=10, won_by_champ=True,
        drew=False, elapsed_s=1.0, moves=70,
        cand_jr_expansions=cand, opp_jr_expansions=opp)


def _summarize(results):
    return efp._summary(results, "fair", 4, 4, 256, 800)


def test_summary_emits_the_per_side_census_at_both_addresses():
    cand = {"total": 900, "own_mover": 400, "boosted": 500}
    opp = dict(ZERO)
    summ = _summarize([_result(1, 0, cand=cand, opp=opp),
                       _result(1, 1, cand=cand, opp=opp)])
    want_c = {"total": 1800, "own_mover": 800, "boosted": 1000}
    # Nested per-side form...
    assert summ["jr_expansions"] == {"candidate": want_c, "opponent": dict(ZERO)}
    # ...and the flat aliases (same numbers, two spellings on purpose — voiding
    # a real cell on a key spelling is worse than a duplicated dict).
    assert summ["cand_jr_expansions"] == want_c
    assert summ["opp_jr_expansions"] == dict(ZERO)
    # The scoping bit the G3 gate asserts for scope="opp".
    assert want_c["boosted"] == want_c["total"] - want_c["own_mover"]


def test_summary_block_is_unconditional_so_absent_can_only_mean_stale_harness():
    """3-state convention (wc_tiebreak's): armed-and-fired / armed-and-inert /
    never-armed must be distinguishable, so a cell that never touched the
    surface still STATES its zeros. An ABSENT block means a pre-R7 harness."""
    summ = _summarize([_result(1, 0), _result(1, 1)])   # no census at all
    for addr in ("cand_jr_expansions", "opp_jr_expansions"):
        assert summ[addr] == dict(ZERO)
    assert summ["jr_expansions"]["candidate"] == dict(ZERO)
    assert summ["jr_expansions"]["opponent"] == dict(ZERO)
    assert set(summ["jr_expansions"]["candidate"]) == {"total", "own_mover", "boosted"}


def test_the_census_round_trips_through_the_per_game_record_on_disk(tmp_path):
    """`_save`/`_try_load` must not drop the field — the cell's sum is over the
    RELOADED records on a resumed pass."""
    cand = {"total": 12, "own_mover": 5, "boosted": 7}
    r = _result(1234, 0, cand=cand, opp=dict(ZERO))
    p = efp._result_path(tmp_path, 1234, 0)
    efp._save(p, r)
    back = efp._try_load(p)
    assert back.cand_jr_expansions == cand
    assert back.opp_jr_expansions == dict(ZERO)
