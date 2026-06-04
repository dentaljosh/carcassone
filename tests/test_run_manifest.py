"""Tests for carcassonne_ai.run_manifest (provenance stamping — D21)."""
import json

from carcassonne_ai.run_manifest import code_rev, game_tag, write_manifest


class _FakeTS:
    def __init__(self, name):
        self.name = name


def test_game_tag_base_vs_river():
    assert game_tag([_FakeTS("BASE")]) == "base"
    assert game_tag([_FakeTS("BASE"), _FakeTS("THE_RIVER")]) == "river"
    assert game_tag([_FakeTS("BASE"), _FakeTS("INNS_AND_CATHEDRALS")]) == "base"


def test_game_tag_accepts_game_object():
    from carcassonne_ai.game_wrapper import Game
    assert game_tag(Game()) == "base"  # River dropped 2026-06-02


def test_code_rev_nonempty():
    rev = code_rev()
    assert isinstance(rev, str) and rev  # 'unknown' or a hash, never empty


def test_write_manifest_writes_and_is_race_safe(tmp_path):
    p = write_manifest(tmp_path, kind="eval_net_vs_heuristic", game="base",
                       config={"sims": 200, "n": 100})
    assert p.exists()
    m = json.loads(p.read_text())
    assert m["kind"] == "eval_net_vs_heuristic"
    assert m["game"] == "base"
    assert m["config"]["sims"] == 200
    assert "code_rev" in m and "utc" in m and "host" in m
    # skip-if-exists: a racing second writer must not clobber the first
    write_manifest(tmp_path, kind="OTHER", game="river", config={"sims": 999})
    assert json.loads(p.read_text())["kind"] == "eval_net_vs_heuristic"
    # overwrite=True forces a rewrite
    write_manifest(tmp_path, kind="OTHER", game="river", config={"sims": 999},
                   overwrite=True)
    assert json.loads(p.read_text())["kind"] == "OTHER"
