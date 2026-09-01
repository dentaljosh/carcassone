"""Tests for carcassonne_ai.run_manifest (provenance stamping — D21)."""
import json
import subprocess

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


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                    capture_output=True, text=True)


def test_code_rev_untracked_file_is_not_dirty(tmp_path):
    """G3-A1: an untracked file must NOT trigger the -dirty suffix."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "tracked.txt").write_text("hello\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "initial")

    # baseline: clean tree -> no -dirty suffix
    assert not code_rev(repo=repo).endswith("-dirty")

    # untracked measurement-dir-style churn -> must stay clean
    (repo / "untracked_churn.log").write_text("noise\n")
    assert not code_rev(repo=repo).endswith("-dirty")


def test_code_rev_tracked_modification_is_dirty(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "tracked.txt").write_text("hello\n")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "initial")

    # modify the tracked file -> -dirty
    (repo / "tracked.txt").write_text("changed\n")
    assert code_rev(repo=repo).endswith("-dirty")


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
