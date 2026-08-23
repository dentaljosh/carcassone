"""F9 / D3 — tests for `scripts/carcasum_match/match.py` and `stub_driver.py`.

Three layers, cheapest first:

1. Pure functions (`rotate_labels`, `draw_order_for`, manifest/record JSON
   shape) — no subprocess, sub-second.
2. The divergence machinery, driven end-to-end through `play_one_match`
   against `stub_driver.py` wrapped in a small CORRUPTING PROXY (`_proxy.py`,
   written to `tmp_path`): it relays every protocol line verbatim EXCEPT one
   deliberately corrupted field, selected by `CARCASUM_TEST_CORRUPT`. This is
   a KNOWN transcript (a real, complete, self-consistent game, since the proxy
   wraps the real — now bug-fixed — stub) with exactly one controlled fault,
   which is what proves the CLASSIFICATION machinery rather than just the
   plumbing (`test_carcasum_stub_smoke` already covers a clean run).
3. `summarize()` arithmetic on a hand-built record list — no engine at all.

Run: `PYTHONPATH=<repo>/src:<repo>/engine .venv/bin/python -m pytest
tests/test_carcasum_match.py -q` (or via the project's normal pytest
invocation — `carcassonne_ai`/`wingedsheep` must resolve inside THIS worktree;
see CLAUDE.md's worktree-isolation note).
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CARCASUM_MATCH = REPO / "scripts" / "carcasum_match"
for _p in (str(REPO / "src"), str(REPO / "engine"), str(CARCASUM_MATCH)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("CARCASSONNE_FIX_R9", "1")

import match as M  # noqa: E402

STUB = CARCASUM_MATCH / "stub_driver.py"


# =========================================================================
# 1. pure functions
# =========================================================================
class TestRotateLabels:
    """Exhaustive: 4 rotations x (8 half-edges + 4 single edges + CLOISTER)."""

    HALF_EDGES = ["NL", "NR", "EL", "ER", "SL", "SR", "WL", "WR"]
    EDGES = ["N", "E", "S", "W"]

    def test_cloister_is_rotation_invariant(self):
        for q in range(4):
            assert M.rotate_labels(["CLOISTER"], q) == frozenset({"CLOISTER"})

    def test_half_edges_cycle_compass_preserve_suffix(self):
        # N->E->S->W->N, L/R suffix untouched, every quarter turn.
        expect_compass = {"N": ["N", "E", "S", "W"], "E": ["E", "S", "W", "N"],
                          "S": ["S", "W", "N", "E"], "W": ["W", "N", "E", "S"]}
        for lab in self.HALF_EDGES:
            compass, suffix = lab[0], lab[1:]
            for q in range(4):
                got = M.rotate_labels([lab], q)
                want = expect_compass[compass][q] + suffix
                assert got == frozenset({want}), (lab, q, got, want)

    def test_edges_cycle_compass(self):
        cycle = ["N", "E", "S", "W"]
        for lab in self.EDGES:
            i0 = cycle.index(lab)
            for q in range(4):
                got = M.rotate_labels([lab], q)
                assert got == frozenset({cycle[(i0 + q) % 4]})

    def test_four_quarters_is_identity(self):
        for lab in self.HALF_EDGES + self.EDGES + ["CLOISTER"]:
            assert M.rotate_labels([lab], 4) == M.rotate_labels([lab], 0)

    def test_full_set_rotation_matches_jcz_cw_ordering(self):
        # A full 8-half-edge field label set, rotated 1 quarter CW, is still
        # the full set (every half-edge maps to a distinct other half-edge).
        got = M.rotate_labels(self.HALF_EDGES, 1)
        assert got == frozenset(self.HALF_EDGES)

    def test_carcasum_node_key_cloister_maps_to_monastery_I(self):
        key = M.carcasum_node_key("cloister", ["CLOISTER"])
        assert key == ("Monastery", frozenset({"I"}))

    def test_carcasum_node_key_field_passthrough(self):
        key = M.carcasum_node_key("field", ["NL", "WR"])
        assert key == ("Field", frozenset({"NL", "WR"}))

    def test_carcasum_node_key_city_road(self):
        assert M.carcasum_node_key("city", ["N", "W"]) == ("City", frozenset({"N", "W"}))
        assert M.carcasum_node_key("road", ["E", "S"]) == ("Road", frozenset({"E", "S"}))


class TestDrawOrderFor:
    def test_71_entries_multiset_matches_tsv(self):
        """draw_order_for's ints, as a multiset, must equal the deck_count sums
        from TILE_MAPPING.tsv grouped by carcasum_tile_type."""
        import random

        from carcassonne_ai import rules_profile
        from carcassonne_ai.game_wrapper import Game

        prof = rules_profile.activate(M.PROFILE)
        tile_map = M.load_carcasum_tile_mapping()
        random.seed(4_242_424)
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        order = M.draw_order_for(board.state, tile_map)

        assert len(order) == 71
        assert all(isinstance(t, int) for t in order)

        expect_counts: dict[int, int] = {}
        rows = [ln.split("\t") for ln in M.TILE_MAPPING_TSV.read_text().strip().splitlines()[1:]]
        for r in rows:
            ctype, deck_count = int(r[2]), int(r[3])
            expect_counts[ctype] = expect_counts.get(ctype, 0) + deck_count
        # RCr / type 2 is the pre-placed start tile (fixed_v1), consumed before
        # `draw_order_for` — its count is 4 on the TSV but only 3 remain to draw.
        start_type = tile_map[M.START_TILE_DESC][1]
        expect_counts[start_type] -= 1
        assert sum(expect_counts.values()) == 71

        got_counts: dict[int, int] = {}
        for t in order:
            got_counts[t] = got_counts.get(t, 0) + 1
        assert got_counts == expect_counts

    def test_deck_hash_is_order_sensitive_and_stable(self):
        import random

        from carcassonne_ai import rules_profile
        from carcassonne_ai.game_wrapper import Game

        prof = rules_profile.activate(M.PROFILE)
        random.seed(1)
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        h1 = M.deck_hash(game.get_init_board().state)
        random.seed(1)
        h2 = M.deck_hash(Game(enable_legal_moves_cache=True, **prof.game_kwargs()).get_init_board().state)
        random.seed(2)
        h3 = M.deck_hash(Game(enable_legal_moves_cache=True, **prof.game_kwargs()).get_init_board().state)
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 16


class TestTileMapping:
    def test_load_carcasum_tile_mapping_shape(self):
        tm = M.load_carcasum_tile_mapping()
        assert len(tm) == 32
        for kind, (cid, ctype, rot) in tm.items():
            assert isinstance(cid, str) and cid
            assert 0 <= ctype <= 23
            assert 0 <= rot <= 3

    def test_start_tile_is_type_2(self):
        tm = M.load_carcasum_tile_mapping()
        assert tm[M.START_TILE_DESC][1] == 2
        assert tm[M.START_TILE_DESC][0] == "RCr"


# =========================================================================
# JSON round-trip
# =========================================================================
def test_record_and_manifest_round_trip_through_json():
    M.export_profile_env(M.PROFILE)
    rec = M.play_one_match(9_991_111, 0, binary=str(STUB), audit_mode="random",
                           opponent={"budget_ms": 20}, read_timeout_s=15.0)
    blob = json.dumps(rec)
    back = json.loads(blob)
    assert back["schema"] == M.SCHEMA
    assert back["deck_seed"] == 9991111
    assert "manifest" in back
    assert back["manifest"]["schema"] == M.SCHEMA
    assert back["manifest"]["carcasum_binary_sha256"]
    assert isinstance(back["actions"], list)
    assert back["void"] in (None, M.VOID_UNMAPPABLE, M.VOID_DIVERGENT, M.VOID_ERROR)


# =========================================================================
# 2. divergence machinery — a KNOWN transcript through a corrupting proxy
# =========================================================================
_PROXY_SRC = r'''#!/usr/bin/env python3
"""Test-only proxy: relays scripts/carcasum_match/stub_driver.py verbatim,
line for line, except it corrupts exactly ONE thing chosen by
$CARCASUM_TEST_CORRUPT before forwarding to the real caller. This makes the
wrapped session a KNOWN transcript (a real, internally-consistent game) with
one deliberate, precisely-located fault -- proving the CLASSIFICATION
machinery in match.py rather than just the plumbing.
"""
import json, os, subprocess, sys

INNER = os.environ["CARCASUM_TEST_INNER"]
MODE = os.environ.get("CARCASUM_TEST_CORRUPT", "")

# argv MUST be forwarded. match.py calls `<binary> --dump-tiles` once, up front,
# to load the node-label table; a proxy that swallowed argv would leave the inner
# stub waiting for a `new_game` line that never comes, and the whole test would
# fail as an opaque 20s TimeoutExpired rather than as whatever it meant to check.
ARGV = sys.argv[1:]

p = subprocess.Popen([sys.executable, INNER] + ARGV, stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1)

if "--dump-tiles" in ARGV:
    # One-shot mode: relay verbatim and exit. Never corrupted -- the tile table is
    # the harness's map of the opponent, not part of any transcript under test.
    sys.stdout.write(p.stdout.read())
    sys.stdout.flush()
    sys.exit(p.wait())

def relay_stdin_line():
    line = sys.stdin.readline()
    p.stdin.write(line)
    p.stdin.flush()
    return line

# The session opens with the caller's `new_game` line. Relay it BEFORE entering the
# read loop: the inner stub emits nothing until it has been told what game to play,
# so a proxy that went straight to `p.stdout.readline()` would deadlock -- proxy
# waiting on inner, inner waiting on the line the proxy never forwarded. Parse
# `external_seat` out of it too -- corrupting the CHAMPION's own echoed-back move
# is a no-op (match.py never validates x/y on its own move), so the "unmappable"
# corruption must target the OPPONENT specifically.
_new_game_line = relay_stdin_line()
CHAMP_SEAT = json.loads(_new_game_line).get("external_seat")

first_tile_seen = False
while True:
    line = p.stdout.readline()
    if not line.strip():
        break
    msg = json.loads(line)
    t = msg.get("t")

    if (MODE == "unmappable_tile" and t == "ev_move"
            and msg.get("player") is not None and msg.get("player") != CHAMP_SEAT):
        # Only corrupt an OPPONENT move (never our own echoed-back move, which
        # match.py never inverts or validates) -- the first one we see.
        if not first_tile_seen and msg.get("x") is not None:
            msg["x"] = 99999
            first_tile_seen = True

    if MODE == "score_final" and t == "game_over":
        sc = list(msg["scores"])
        sc[0] = int(sc[0]) + 7
        msg["scores"] = sc

    if MODE == "field_only" and t == "game_over":
        # Move N points from city to field in score_detail WITHOUT touching
        # the totals -- the exact "totals agree, one terrain doesn't" case.
        # Applied unconditionally (even negative is fine -- this is a
        # deliberately corrupted transcript, not a plausible one).
        N = 3
        sd = msg.get("score_detail") or {}
        city = list(sd.get("city", [0, 0]))
        field = list(sd.get("field", [0, 0]))
        city[0] -= N
        field[0] += N
        sd["city"], sd["field"] = city, field
        msg["score_detail"] = sd

    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()

    if t in ("req_tile", "req_meeple"):
        relay_stdin_line()

    if t in ("game_over", "fault"):
        # Session over. Stop reading inner stdout -- it has nothing more to say and
        # blocking on it here would hang the proxy past the caller's `quit`.
        break
    if t == "game_over":
        break

try:
    p.stdin.write(json.dumps({"t": "quit"}) + "\n")
    p.stdin.flush()
except Exception:
    pass
p.wait(timeout=5)
'''


@pytest.fixture()
def corrupt_proxy(tmp_path: Path):
    def _make(mode: str) -> Path:
        p = tmp_path / f"proxy_{mode}.py"
        p.write_text(_PROXY_SRC)
        p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        os.environ["CARCASUM_TEST_INNER"] = str(STUB)
        os.environ["CARCASUM_TEST_CORRUPT"] = mode
        return p
    yield _make
    os.environ.pop("CARCASUM_TEST_CORRUPT", None)
    os.environ.pop("CARCASUM_TEST_INNER", None)


def test_carcasum_stub_smoke_clean_game_no_corruption(corrupt_proxy):
    """A real game through the (bug-fixed) stub, no corruption: plumbing alone
    must never produce a REAL divergence class."""
    M.export_profile_env(M.PROFILE)
    proxy = corrupt_proxy("")
    rec = M.play_one_match(1_234_567, 0, binary=str(proxy), audit_mode="random",
                           opponent={"budget_ms": 20}, read_timeout_s=20.0)
    assert rec["real"] == {}, rec.get("void_detail")
    assert rec["void"] is None
    assert rec["n_actions"] > 0
    assert rec["final_agree"] is True
    assert rec["farm_points_ours"] == rec["farm_points_theirs"]


def test_unmappable_opponent_move_voids_and_records_offered_set(corrupt_proxy):
    proxy = corrupt_proxy("unmappable_tile")
    M.export_profile_env(M.PROFILE)
    rec = M.play_one_match(1_234_568, 0, binary=str(proxy), audit_mode="random",
                           opponent={"budget_ms": 20}, read_timeout_s=20.0)
    assert rec["void"] == M.VOID_UNMAPPABLE
    assert rec["void_detail"]["phase"] == "tiles"
    assert "carcasum_move" in rec["void_detail"]
    assert "our_legal_images" in rec["void_detail"]["ours"]
    # a VOID_UNMAPPABLE game is excluded from summarize()'s win_rate but
    # still shows up in voids -- checked properly in TestSummarize below.


def test_final_score_mismatch_classified_score_final(corrupt_proxy):
    proxy = corrupt_proxy("score_final")
    M.export_profile_env(M.PROFILE)
    rec = M.play_one_match(1_234_569, 0, binary=str(proxy), audit_mode="random",
                           opponent={"budget_ms": 20}, read_timeout_s=25.0)
    assert rec["void"] == M.VOID_DIVERGENT, rec.get("void_detail")
    assert "SCORE_FINAL" in rec["real"]
    assert rec["final_agree"] is False


def test_field_only_mismatch_totals_agree_farm_score_final_fires(corrupt_proxy):
    """THE per-terrain case: score_detail moves points from city to field with
    the TOTAL untouched, so SCORE_FINAL must NOT fire, but FARM_SCORE_FINAL
    (our independently-computed farm total vs their score_detail['field'])
    must."""
    proxy = corrupt_proxy("field_only")
    M.export_profile_env(M.PROFILE)
    rec = M.play_one_match(1_234_570, 0, binary=str(proxy), audit_mode="random",
                           opponent={"budget_ms": 20}, read_timeout_s=25.0)
    assert rec["void"] == M.VOID_DIVERGENT, rec.get("void_detail")
    assert "FARM_SCORE_FINAL" in rec["real"]
    assert "SCORE_FINAL" not in rec["real"], (
        "totals were left untouched by the field_only corruption -- a "
        "SCORE_FINAL finding here means the totals check is not independent "
        "of the per-terrain one")
    assert rec["final_agree"] is True


# =========================================================================
# 3. summarize() arithmetic
# =========================================================================
class TestSummarize:
    def _rec(self, deck_seed, champ_seat, margin, winner, void=None):
        return {"deck_seed": deck_seed, "champ_seat": champ_seat,
               "margin_champ_minus_opp": margin, "winner": winner, "void": void,
               "replay_ok": True}

    def test_win_rate_and_voids_counted_separately(self):
        recs = [
            self._rec(1, 0, 10, "champ"),
            self._rec(1, 1, -4, "opp"),
            self._rec(2, 0, 0, "draw"),
            self._rec(3, 0, None, None, void=M.VOID_UNMAPPABLE),
            self._rec(4, 0, None, None, void=M.VOID_DIVERGENT),
        ]
        s = M.summarize(recs)
        assert s["n_records"] == 5
        assert s["n_scored"] == 3
        assert s["wins"] == 1
        assert s["draws"] == 1
        assert s["losses"] == 1
        assert s["win_rate"] == pytest.approx((1 + 0.5) / 3)
        assert s["voids"] == {M.VOID_UNMAPPABLE: 1, M.VOID_DIVERGENT: 1}

    def test_margin_field_is_champion_relative_in_both_seatings(self):
        """Pin the SIGN CONVENTION of the primary estimator, in words and in code.

        ``margin_champ_minus_opp`` is built as
        ``our_final[champ_seat] - our_final[opp_seat]`` — i.e. **champion-minus-
        opponent in EVERY seating, by construction**. It is NOT a seat-0-relative
        score difference that a consumer must negate for seat-1 records.

        This test exists because an earlier draft of the test below assumed the
        opposite and "expected" 4 where the code correctly returns 2. Had that been
        resolved by changing ``summarize`` instead of the test, the fix would have
        introduced a **sign error in the deck-paired margin — the estimator of record
        for the whole cell** — in the one place it is hardest to notice, because a
        sign error in a seat-swapped average still produces a plausible-looking small
        number. Pinning the convention explicitly is cheaper than rediscovering it.
        """
        # champion loses by 2 while seated as player 1 -> the field is -2, not +2.
        assert self._rec(10, 1, -2, "opp")["margin_champ_minus_opp"] == -2
        s = M.summarize([self._rec(10, 0, 6, "champ"), self._rec(10, 1, -2, "opp")])
        assert s["paired_margin_mean"] == pytest.approx((6 + (-2)) / 2.0)

    def test_deck_paired_margin_only_uses_fully_paired_decks(self):
        recs = [
            self._rec(10, 0, 6, "champ"),
            self._rec(10, 1, -2, "opp"),   # champion-relative already: champ lost by 2
            self._rec(11, 0, 8, "champ"),  # unpaired: only one seat scored for deck 11
        ]
        s = M.summarize(recs)
        assert s["n_paired_decks"] == 1
        # Deck 11 contributes to the UNPAIRED mean only -- a half-paired deck would
        # otherwise smuggle raw first-player advantage into the paired statistic,
        # which is the entire thing the pairing exists to remove.
        assert s["paired_margin_mean"] == pytest.approx((6 + (-2)) / 2.0)
        assert s["mean_margin_unpaired"] == pytest.approx((6 - 2 + 8) / 3.0)

    def test_replay_failures_surfaced(self):
        recs = [dict(self._rec(1, 0, 1, "champ"), replay_ok=False, deck_seed=1)]
        s = M.summarize(recs)
        assert s["replay_failures"] == [1]

    def test_empty_records(self):
        s = M.summarize([])
        assert s["n_records"] == 0
        assert s["win_rate"] is None
        assert s["voids"] == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
