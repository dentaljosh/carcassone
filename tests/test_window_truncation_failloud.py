"""Contracts for the F-c FAIL-LOUD action-window fix.

`measurement/window_truncation_20260813/DESIGN.md` §6-P3 fired by OCCURRENCE in
production on 2026-08-13, which licenses §7 F-c: the search must say WHY it
reached a node with no valid actions, and a truncation-caused empty action set
must be distinguishable from every other cause.  The fix is
`carc_core::search::window_diag` (built on the ERROR path only) +
`carc_rs.WindowTruncationError` + `carcassonne_ai.window_truncation`.

What each block earns:

  A. BIT-IDENTITY of the no-fire path.  Not a smoke test: the three champion leaf
     fingerprints, and a 208-record golden set of REAL production searches whose
     sha256 was recorded from the PRE-FIX wheel.  If the fix changed one bit of
     move selection, priors, node counts or leaf-eval counts anywhere in that
     set, this fails.
  B. IT FIRES.  A genuinely truncated window (the census's own positive-control
     device, DESIGN §4 `--narrow-window`) must raise the TYPED error and carry a
     payload that names the dropped placements in engine coordinates.
  C. IT DOES NOT FIRE on ordinary play, including on a position with a
     legitimately TINY legal action set -- the case a naive "empty-ish means
     truncated" detector would get wrong.
  D. CAUSE SEPARATION.  `window_truncation` vs `no_engine_actions` vs
     `mask_not_empty`, by exception TYPE and by payload.
  E. ROUND TRIP.  The emitted record is consumed by the EXISTING tooling:
     `window_truncation_census.py` re-seats the position from it, its checksum
     gate passes, it reads `move_idx` off the record (source "root", NOT the ply
     fallback), and it re-derives the same empty-mask event.
  F. THE PLY/`move_idx` TRAP.  The two are never conflated, by construction.

⚠️ Everything here runs at tiny budgets on self-contained synthetic roots, so
the file is fast and needs no share mount.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "src", REPO / "scripts" / "human_anchor",
           REPO / "scripts" / "measurement_infra"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import env_preamble  # noqa: F401,E402

carc_rs = pytest.importorskip("carc_rs")

import window_truncation_census as WTC  # noqa: E402
from carcassonne_ai import champion_factory as CF  # noqa: E402
from carcassonne_ai import rust_agent as RA  # noqa: E402
from carcassonne_ai import window_truncation as WT  # noqa: E402

pytestmark = pytest.mark.skipif(
    not hasattr(carc_rs, "WindowTruncationError"),
    reason="carc_rs predates F-c; rebuild the wheel (docs/CLUSTER_OPS.md)")

# --------------------------------------------------------------------------- #
# A. the pre-fix golden set                                                     #
# --------------------------------------------------------------------------- #
#: Recorded from the PRE-F-c wheel (same source tree, same pinned toolchain
#: 1.96.0, same build flags -- only `search/window_diag.rs` + the `Err` arm of
#: `simulate`'s `select_child_puct` differ).  208 production searches: 2 rules
#: geometries x 4 decks x 26 plies at 400 sims, hashing chosen action, every
#: root child's (action, N, W-bits), the deduped and pooled stats, root priors,
#: node counts and leaf-eval counts.
GOLDEN_SHA256 = "6cd80a92ad2dd7b55d9fd0a2c77252b654f3c5de3492d59131973ba1a73f3d89"
GOLDEN_RECORDS = 208
GOLDEN_LEAF_EVALS = 736607
GOLDEN_NODES = 75886
GOLDEN_SIMS = 400
GOLDEN_SEEDS = ("126000000135", "28000000001", "76000000042", "88000000007")
GOLDEN_PROFILES = (
    dict(window_size=25),
    dict(window_size=25, start_rule="retail", cloister_scan_fix=True,
         draw_rule="redraw"),
)

DECK_SEED = 1260000001
#: The smallest (prefix, window) pair found that drives the SEARCH -- not the
#: played position -- into an empty mask, with a prefix short enough that the
#: census's W=25 -> narrow remap still resolves.  Both are load-bearing: at
#: `FIRE_WINDOW = 5` the same root truncates but never empties (block C).
FIRE_PLIES, FIRE_WINDOW, FIRE_SIMS = 4, 3, 400


@pytest.fixture(scope="module")
def prior_cfg():
    return CF.production_prior_cfg(leaf_cfg=CF.production_leaf_cfg())


def _prefix(n_ply: int, seed: int = 7):
    """A deterministic pseudo-random W=25 playout -- the RECORDED index space,
    exactly the shape `roots.jsonl` / the E4 archives store."""
    ms = carc_rs.MirrorState.from_seed(str(DECK_SEED))
    rng = random.Random(seed)
    pre = []
    for _ in range(n_ply):
        la = ms.legal_actions()
        if not la:
            break
        a = la[rng.randrange(len(la))]
        ms.advance(a)
        pre.append(a)
    return pre, ms


@pytest.fixture(scope="module")
def fire_root():
    """A real root (W=25 indices) + the narrow seat whose SEARCH empties a mask."""
    pre, ms = _prefix(FIRE_PLIES)
    return {"deck_seed": DECK_SEED, "ply": len(pre), "actions": pre,
            "checksum": ms.string_repr(), "player_to_move": ms.current_player(),
            "move_idx": 2, "rid": "failloud_fire"}


def _narrow_seat(root, window):
    return WTC.RootSeat(int(root["deck_seed"]), root["actions"], geom={},
                        wide_window=WTC.WIDE_WINDOW_DEFAULT,
                        narrow_window=int(window)).seat()


# --------------------------------------------------------------------------- #
# A. BIT-IDENTITY                                                              #
# --------------------------------------------------------------------------- #
def test_the_champion_leaf_fingerprints_are_unchanged():
    """The release gate the rebuilt wheel has to clear before anything else."""
    prov = CF.verify_leaf(CF.production_leaf_cfg(), backend="rust")
    assert prov["hashes"] == {
        "harness_leaf_hash": CF.LEAF_HASH_HARNESS,
        "frozen_config_hash_meeple_k0": CF.LEAF_HASH_FROZEN_MK0,
        "frozen_config_hash_meeple_k2": CF.LEAF_HASH_FROZEN_MK2,
    }
    assert (CF.LEAF_HASH_HARNESS, CF.LEAF_HASH_FROZEN_MK2, CF.LEAF_HASH_FROZEN_MK0) == (
        "a36d2e15a3b3d71d", "158f17ff76adaa02", "6dfffd57051690f2")
    assert prov["leaf_value_panel_rust"] == prov["leaf_value_panel"]


def test_the_no_fire_search_is_bit_identical_to_the_pre_fix_wheel(prior_cfg):
    """208 REAL production searches, hashed.  A single differing bit anywhere in
    move selection, priors, visit/value accumulation, node counts or leaf-eval
    counts moves the digest.

    This is the whole default-safety claim of F-c: the diagnostic is built on the
    error path, so a search that does not die cannot tell the fix is there.
    """
    golden = []
    for prof in GOLDEN_PROFILES:
        for seed in GOLDEN_SEEDS:
            ms = carc_rs.MirrorState.from_seed(seed, **prof)
            scfg = RA.search_config_rs(prior_cfg, GOLDEN_SIMS)
            for ply in range(26):
                if ms.is_terminal():
                    break
                r = ms.search_single(scfg)
                golden.append({
                    "seed": seed, "prof": sorted(prof.items()), "ply": ply,
                    "chosen_action": r["chosen_action"],
                    "root_children": r["root_children"],
                    "deduped": r["deduped"],
                    "pooled_stats": r["pooled_stats"],
                    "root_player": r["root_player"],
                    "root_n": r["root_n"],
                    "root_w_bits": r["root_w_bits"],
                    "root_leaf_value_bits": r["root_leaf_value_bits"],
                    "root_priors": r["root_priors"],
                    "node_count": r["node_count"],
                    "leaf_evals": r["leaf_evals"],
                    "mask_counts": ms.mask_counts(),
                    "window_offset": ms.window_offset(),
                    "state_digest": ms.state_digest(),
                })
                ms.advance(int(r["chosen_action"]))
    blob = json.dumps(golden, sort_keys=True, separators=(",", ":"))
    assert len(golden) == GOLDEN_RECORDS
    assert sum(g["leaf_evals"] for g in golden) == GOLDEN_LEAF_EVALS
    assert sum(g["node_count"] for g in golden) == GOLDEN_NODES
    assert hashlib.sha256(blob.encode()).hexdigest() == GOLDEN_SHA256, (
        "the no-fire search path is NOT bit-identical to the pre-F-c wheel")


# --------------------------------------------------------------------------- #
# B. IT FIRES                                                                  #
# --------------------------------------------------------------------------- #
def test_the_detector_fires_on_a_truncated_window(fire_root, prior_cfg):
    """The positive control.  A detector that has only ever reported nothing is
    unfalsifiable (DESIGN §4), so the window is squeezed until the SEARCH -- not
    the played position -- runs out of encodable actions."""
    ms = _narrow_seat(fire_root, FIRE_WINDOW)
    assert ms.string_repr() == fire_root["checksum"]        # same position
    n_total, n_over = ms.mask_counts()
    assert n_total - n_over > 0, (
        "the ROOT must still have encodable moves -- the wall this test is about "
        "is INSIDE the search (DESIGN §2), not at the played position")
    with pytest.raises(carc_rs.WindowTruncationError) as ei:
        ms.search_single(RA.search_config_rs(prior_cfg, FIRE_SIMS))

    exc = ei.value
    assert isinstance(exc, RuntimeError), "must stay catchable by existing guards"
    assert "no valid actions" in str(exc), "the historical message must survive"
    assert WT.is_window_truncation(exc)
    d = WT.parse_diag(exc)
    assert d["cause"] == "window_truncation"
    assert d["n_total"] > 0 and d["n_overflow"] == d["n_total"] and d["n_encoded"] == 0
    assert d["window_size"] == FIRE_WINDOW
    assert d["window_offset"] == [d["window_offset"][0], d["window_offset"][1], FIRE_WINDOW]
    assert d["phase"] in ("tiles", "meeples")
    assert d["player_to_move"] in (0, 1)
    assert d["depth"] >= 1 and len(d["descent_actions"]) == d["depth"]
    assert len(d["node_digest"]) == 16 and int(d["node_digest"], 16) >= 0
    # the dropped placements are named, in ENGINE coordinates, and every one of
    # them really is outside the window that dropped it
    r0, c0, size = d["window_offset"]
    assert d["dropped"], "a truncation that cannot name a coordinate is not a diagnosis"
    for p in d["dropped"]:
        inside = (r0 <= p["row"] < r0 + size) and (c0 <= p["col"] < c0 + size)
        assert not inside, f"{p} is INSIDE the window and cannot have overflowed"


def test_the_typed_error_is_a_runtime_error_subclass():
    """Every existing guard (`h2h._play_cell`, the pools) catches RuntimeError or
    BaseException; F-c must not slip past them."""
    assert issubclass(carc_rs.WindowTruncationError, RuntimeError)
    assert carc_rs.EMPTY_MASK_DIAG_MARKER == WT.DIAG_MARKER


# --------------------------------------------------------------------------- #
# C. IT DOES NOT FIRE ON ORDINARY POSITIONS                                    #
# --------------------------------------------------------------------------- #
def test_it_does_not_fire_at_the_production_window(fire_root, prior_cfg):
    """The same root that fires at W=3 is silent at the production window."""
    ms = _narrow_seat(fire_root, 25)
    r = ms.search_single(RA.search_config_rs(prior_cfg, FIRE_SIMS))
    assert r["chosen_action"] >= 0
    assert ms.mask_counts()[1] == 0


def test_it_does_not_fire_on_a_window_that_truncates_without_emptying(
        fire_root, prior_cfg):
    """DESIGN's P2-vs-P3 distinction, as a test: dropping SOME legal actions is
    the (silent) strength face and must NOT raise.  Only an EMPTY mask is P3."""
    pre, _ = _prefix(16)
    ms = WTC.RootSeat(DECK_SEED, pre, geom={}, wide_window=WTC.WIDE_WINDOW_DEFAULT,
                      narrow_window=5).seat()
    n_total, n_over = ms.mask_counts()
    assert n_over > 0 and n_over < n_total, "fixture must truncate but not empty"
    ms.search_single(RA.search_config_rs(prior_cfg, FIRE_SIMS))     # no raise


def test_it_does_not_fire_on_a_legitimately_small_action_set(prior_cfg):
    """The case a naive detector gets wrong: an ordinary late-game position whose
    legal set is genuinely tiny (1-2 actions) is not a truncation."""
    ms = carc_rs.MirrorState.from_seed(str(DECK_SEED))
    rng = random.Random(11)
    smallest, seen = 99, 0
    scfg = RA.search_config_rs(prior_cfg, 64)
    while not ms.is_terminal():
        la = ms.legal_actions()
        if not la:
            break
        if len(la) <= 2:
            seen += 1
            smallest = min(smallest, len(la))
            assert ms.mask_counts()[1] == 0
            ms.search_single(scfg)                                  # no raise
        ms.advance(la[rng.randrange(len(la))])
    assert seen > 0 and smallest <= 2, "no tiny-action-set position was reached"


# --------------------------------------------------------------------------- #
# D. CAUSE SEPARATION                                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cause,truncation", [
    ("window_truncation", True),
    ("no_engine_actions", False),
    ("mask_not_empty", False),
])
def test_the_classifier_separates_the_causes(cause, truncation):
    """Payload-level classification, for the paths that cross a process boundary
    (a pool worker's exception arrives as text, and a record read back off disk
    has no exception object at all)."""
    msg = ("PUCT reached a node with no valid actions (Python IndexError) "
           + WT.DIAG_MARKER + json.dumps({"cause": cause, "n_total": 4}))
    assert WT.is_empty_mask_error(msg)
    assert WT.diag_cause(msg) == cause
    assert WT.is_window_truncation(msg) is truncation


def test_an_unrelated_error_is_not_claimed_as_a_truncation():
    for e in (RuntimeError("PUCT reached a node with no valid actions (Python IndexError)"),
              ValueError("fair agent asked to move with no legal actions"),
              RuntimeError("rust mirror desync at choose_action")):
        assert WT.parse_diag(e) is None
        assert not WT.is_empty_mask_error(e)
        assert not WT.is_window_truncation(e)


# --------------------------------------------------------------------------- #
# E. ROUND TRIP THROUGH THE EXISTING TOOLING                                   #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def fired(fire_root, prior_cfg):
    """A REAL raise, captured through `window_truncation.capture` exactly as the
    play loop does."""
    class _Agent:                       # the harness reads `move_idx` off the agent
        move_idx = 2

    ms = _narrow_seat(fire_root, FIRE_WINDOW)
    with pytest.raises(carc_rs.WindowTruncationError) as ei:
        with WT.capture(deck_seed=fire_root["deck_seed"], ply=fire_root["ply"],
                        actions=fire_root["actions"],
                        player_to_move=fire_root["player_to_move"],
                        agent=_Agent(), champion_seed=9400540,
                        rules_profile="walled", checksum=fire_root["checksum"],
                        raiser_is_champion=True, sink=os.devnull):
            ms.search_single(RA.search_config_rs(prior_cfg, FIRE_SIMS))
    return ei.value


def test_capture_attaches_a_census_ready_root_and_reraises(fired):
    rec = fired.window_root_record
    # exactly the fields `window_truncation_census.census_root` reads off a root
    for k in ("deck_seed", "ply", "actions", "player_to_move", "checksum",
              "move_idx", "rid"):
        assert k in rec
    # ... and the fields `reconstruct_crash_root.py` emits, so the two are
    # interchangeable inputs to the census
    for k in ("champion_seed", "rules_profile", "raised", "raiser_is_champion",
              "exc_type", "exc", "traceback"):
        assert k in rec
    assert rec["ply"] == len(rec["actions"])
    assert rec["move_idx"] == 2 and rec["move_idx_source"] == "agent"
    assert rec["raised"] is True and rec["window_truncation"] is True
    assert rec["window_diag"]["cause"] == "window_truncation"


def test_the_emitted_record_round_trips_through_the_census(fired, tmp_path):
    """THE round trip: write the record, read it back, and hand it to the
    UNMODIFIED census instrument, which must re-seat the identical position and
    re-derive the same empty-mask event."""
    path = WT.emit_crash_root(fired.window_root_record, sink=tmp_path / "roots.jsonl")
    assert path is not None and path.exists()
    root = json.loads(path.read_text().splitlines()[-1])

    WTC._SPEC = WTC._CFG = None
    opt = WTC._Opt(k_dets=8, sims=FIRE_SIMS, geom={}, wide=False,
                   wide_window=WTC.WIDE_WINDOW_DEFAULT, narrow_window=FIRE_WINDOW,
                   replay_fraction=1.0, max_examples=32,
                   verify_dropped_are_legal=True, verify_all_truncated=True,
                   agent_seed=101, agent_seed_mode="fixed",
                   trace_dir=str(tmp_path), trace_path=str(tmp_path / "t.jsonl"))
    rec = WTC.census_root(dict(root), opt)

    assert rec["checksum_ok"], "the census could not re-seat the recorded position"
    assert rec["move_idx"] == root["move_idx"]
    assert rec["move_idx_source"] == "root", (
        "the census fell back to the PLY -- the recorded move_idx did not survive, "
        "and the determinization draw is therefore a different one")
    assert rec["n_nodes_empty_mask"] > 0 or rec["world_errors"], (
        "the census did not re-derive the empty-mask event from the emitted root")


def test_the_record_is_appended_not_overwritten(fired, tmp_path):
    sink = tmp_path / "roots.jsonl"
    WT.emit_crash_root(fired.window_root_record, sink=sink)
    WT.emit_crash_root(fired.window_root_record, sink=sink)
    assert len(sink.read_text().splitlines()) == 2


# --------------------------------------------------------------------------- #
# F. THE PLY / move_idx TRAP, and the operational guards                       #
# --------------------------------------------------------------------------- #
def test_the_ply_is_never_substituted_for_move_idx():
    """The recorded trap (DESIGN §5.1): `det_seed_base(seed, move_idx)` draws a
    DIFFERENT eight worlds if the ply is fed in, so the crash does not reproduce.
    The builder refuses to guess."""
    exc = RuntimeError("x " + WT.DIAG_MARKER + '{"cause":"window_truncation"}')
    base = dict(deck_seed=1, ply=3, actions=[1, 2, 3], player_to_move=0)
    rec = WT.crash_root_record(exc, move_idx=None, move_idx_source="unavailable", **base)
    assert rec["move_idx"] is None and rec["move_idx_source"] == "unavailable"
    with pytest.raises(ValueError):
        WT.crash_root_record(exc, move_idx=None, move_idx_source="agent", **base)
    with pytest.raises(ValueError):
        WT.crash_root_record(exc, move_idx=7, move_idx_source="unavailable", **base)


def test_the_ply_must_be_the_global_ply():
    """`ply` is the length of the applied-action prefix, full stop -- the census
    slices `actions[:ply]`, so a champion's own decision counter here would seat
    a different position."""
    exc = RuntimeError("x " + WT.DIAG_MARKER + '{"cause":"window_truncation"}')
    with pytest.raises(ValueError, match="GLOBAL ply"):
        WT.crash_root_record(exc, deck_seed=1, ply=59, actions=[1, 2, 3],
                             player_to_move=0, move_idx=59, move_idx_source="caller")


def test_capture_reraises_unrelated_errors_untouched():
    boom = ValueError("not a window problem")
    with pytest.raises(ValueError) as ei:
        with WT.capture(deck_seed=1, ply=0, actions=[], sink=os.devnull):
            raise boom
    assert ei.value is boom
    assert not hasattr(ei.value, "window_root_record")


def test_the_sink_resolves_without_probing_directory_existence(tmp_path, monkeypatch):
    """The recorded share-path trap: `/mnt/c/carc-shared` and `/mnt/carc-shared`
    BOTH exist on the laptop and are different filesystems, so `[ -d ]` cannot
    choose between them.  Resolution is explicit-arg, else env, else the one
    repo-relative default -- never a probe."""
    monkeypatch.delenv("CARCASSONNE_WINDOW_DIAG_DIR", raising=False)
    assert WT.sink_path() == WT.DEFAULT_SINK_DIR / WT.SINK_FILE
    ghost = tmp_path / "does" / "not" / "exist"
    monkeypatch.setenv("CARCASSONNE_WINDOW_DIAG_DIR", str(ghost))
    assert WT.sink_path() == ghost / WT.SINK_FILE       # used even though absent
    assert WT.sink_path(tmp_path / "explicit.jsonl") == tmp_path / "explicit.jsonl"


def test_emitting_is_never_fatal_and_can_be_switched_off(tmp_path, monkeypatch, capsys):
    rec = {"rid": "x"}
    monkeypatch.setenv("CARCASSONNE_WINDOW_DIAG", "0")
    assert WT.emit_crash_root(rec, sink=tmp_path / "a.jsonl") is None
    assert not (tmp_path / "a.jsonl").exists()
    monkeypatch.setenv("CARCASSONNE_WINDOW_DIAG", "1")
    blocked = tmp_path / "file"
    blocked.write_text("i am not a directory")
    assert WT.emit_crash_root(rec, sink=blocked / "nested.jsonl") is None
    assert "FAILED to record" in capsys.readouterr().err


def test_the_h2h_exclusion_record_carries_the_diagnosis(fired, monkeypatch):
    """The 2026-08-13 dossier had only `exc_type` + `exc` and had to replay the
    whole cell to find the position (`reconstruct_crash_root.py`).  An excluded
    cell now says WHY it was excluded, and carries the census root with it."""
    sys.path.insert(0, str(REPO / "scripts" / "joshuabot"))
    import h2h as H2H

    for k, v in (("preset", "current"), ("profile", "fixed_v1"),
                 ("variant_id", "current+j7w0"), ("overrides", {})):
        monkeypatch.setitem(H2H._W, k, v)
    rec = H2H.failed_record((126_000_000_135, 0), fired, 0.0)
    assert rec["failed"] is True and rec["winner"] is None
    assert rec["window_truncation"] is True
    assert rec["window_diag"]["cause"] == "window_truncation"
    assert rec["window_root_record"]["deck_seed"] == DECK_SEED
    json.dumps(rec)                                      # still JSONL-serialisable

    plain = H2H.failed_record((1, 0), RuntimeError("rust mirror desync"), 0.0)
    assert plain["window_truncation"] is False and plain["window_diag"] is None
    assert "window_root_record" not in plain


def test_it_feeds_wall_sentinel_face_five(fired):
    """DESIGN §7 F-c: "give `wall_sentinel` a face-5 counter that the Rust search
    feeds".  Face 5 already exists for the PYTHON engine's WindowOverflowError;
    the rust search-internal event lands in the same counter."""
    from carcassonne_ai import wall_sentinel as WS

    s = WS.GameSentinel()
    assert WT.note_sentinel(s, 119, fired) is True
    assert s.window_overflow == 1 and s.aborted is True
    assert "ply119" in s.abort_reason and "rust search" in s.abort_reason
    assert s.any_event is True
    # and it does NOT fire for an unrelated failure
    s2 = WS.GameSentinel()
    assert WT.note_sentinel(s2, 5, RuntimeError("mirror desync")) is False
    assert s2.window_overflow == 0
