"""The JCZ provenance stamp on every match record: the JAR HASH is the witness.

WHY THIS FILE EXISTS. A two-box JCZ match was VOIDED on 2026-08-17 partly because
``match.py`` stamped JCZ provenance as ``_git_rev(jcz_repo)`` and ``_git_rev``
returned ``None`` on any subprocess failure. The laptop had been provisioned by
copying the pinned, sha-verified ``Engine.jar`` + shim classes over the share instead
of cloning the JCZ repo — deliberately, because byte-identical bytecode beats a second
unverified build — so ``git -C ~/jcz_spike/JCloisterZone rev-parse HEAD`` answered
*fatal: not a git repository* and 370 of 800 records per cell carried
``jcz_git_rev: null`` **while running exactly the right artifact**. The gate could
never pass on that box.

The fix these tests guard: the jar's **full sha256 is the primary witness** — it
hashes the bytes that actually executed and needs nothing but the jar — while the git
rev is demoted to secondary/best-effort, kept present-and-null (never fabricated) with
the reason recorded beside it.

Cheap by construction: no JVM, no game, no search, no rust wheel. Every "jar" here is
a few bytes in ``tmp_path``.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MATCH_DIR = REPO / "scripts" / "jcz_match"
for _p in (str(REPO / "src"), str(MATCH_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import match as M  # noqa: E402


JAR_BYTES = b"PK\x03\x04 not a real jar, but the bytes are what get hashed\n" * 40
EXPECT_SHA = hashlib.sha256(JAR_BYTES).hexdigest()


@pytest.fixture(autouse=True)
def _clean_cache():
    """The sha cache is module state (per-worker in production) — isolate each test."""
    M._FILE_SHA256_CACHE.clear()
    yield
    M._FILE_SHA256_CACHE.clear()


class _Prof:
    """The two things ``build_manifest`` asks of a resolved rules profile."""

    name = "fixed_v1"

    @staticmethod
    def as_manifest() -> dict:
        return {"profile": "fixed_v1", "r9_env_expected": True, "r9_env_ok": True}


def _jar_in(root: Path, *, contents: bytes = JAR_BYTES) -> Path:
    """``<root>/build/Engine.jar`` — the real layout, so ``jar.parents[1]`` (the repo
    ``build_manifest`` probes for a git rev) is ``root``."""
    jar = root / "build" / "Engine.jar"
    jar.parent.mkdir(parents=True, exist_ok=True)
    jar.write_bytes(contents)
    return jar


def _tiles_in(root: Path) -> Path:
    tiles = root / "tiles.xml"
    tiles.write_text("<tiles/>\n")
    return tiles


def _manifest(jar: Path, tiles: Path) -> dict:
    return M.build_manifest(
        jar=jar, tiles=tiles, ai_class="com.jcloisterzone.ai.AiEngine",
        ai_config={}, champ_manifest=None, execution=None, sims=None, k_dets=None,
        prof=_Prof(), ai_classes=None, ai_cmd=["java", "-cp", str(jar), "X"])


# --------------------------------------------------------------------------- #
# 1. the primary witness                                                       #
# --------------------------------------------------------------------------- #
def test_full_jar_sha256_is_stamped_and_is_the_hash_of_the_bytes(tmp_path):
    man = _manifest(_jar_in(tmp_path), _tiles_in(tmp_path))

    assert isinstance(man["jcz_jar_sha256"], str)
    assert len(man["jcz_jar_sha256"]) == 64
    assert all(c in "0123456789abcdef" for c in man["jcz_jar_sha256"])
    assert man["jcz_jar_sha256"] == EXPECT_SHA
    # …and it is named as the authoritative one, so a reader never has to guess which
    # of two provenance fields a gate should key on.
    assert man["jcz_provenance_witness"] == "jar_sha256"


def test_truncated_key_is_unchanged_for_the_20260809_archive_readers(tmp_path):
    """`jcz_jar_sha256_16` must keep its exact old value: the adjudicator resolves the
    jar witness through it (prefix-compared against the WORKERS.conf pin)."""
    man = _manifest(_jar_in(tmp_path), _tiles_in(tmp_path))

    assert man["jcz_jar_sha256_16"] == EXPECT_SHA[:16]
    assert len(man["jcz_jar_sha256_16"]) == 16
    assert man["jcz_jar_sha256"].startswith(man["jcz_jar_sha256_16"])


# --------------------------------------------------------------------------- #
# 2-3. the git rev, demoted but never fabricated                               #
# --------------------------------------------------------------------------- #
def test_no_git_repo_keeps_the_key_null_with_a_reason_and_still_hashes_the_jar(tmp_path):
    """THE 2026-08-17 CASE, in a test: a copied-jar box. `jcz_git_rev` stays present
    and null (absent would be a schema change; a substituted value would be a lie),
    the unavailability is stated, and the record is still fully witnessed by the jar."""
    assert not (tmp_path / ".git").exists()
    man = _manifest(_jar_in(tmp_path), _tiles_in(tmp_path))

    assert "jcz_git_rev" in man
    assert man["jcz_git_rev"] is None
    assert man["jcz_git_rev_available"] is False
    assert isinstance(man["jcz_git_rev_unavailable_reason"], str)
    assert man["jcz_git_rev_unavailable_reason"].strip()
    # the whole point: provenance is NOT lost when the rev is
    assert man["jcz_jar_sha256"] == EXPECT_SHA
    assert man["jcz_provenance_witness"] == "jar_sha256"


def test_a_real_checkout_still_resolves_the_rev(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    root = tmp_path / "JCloisterZone"
    root.mkdir()
    env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, env=env,
                   capture_output=True, timeout=60)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "x"],
                   check=True, env=env, capture_output=True, timeout=60)

    man = _manifest(_jar_in(root), _tiles_in(tmp_path))

    assert man["jcz_git_rev_available"] is True
    assert isinstance(man["jcz_git_rev"], str) and len(man["jcz_git_rev"]) >= 40
    assert man["jcz_git_rev_unavailable_reason"] is None
    assert man["jcz_jar_sha256"] == EXPECT_SHA


def test_git_rev_detail_reports_the_reason_verbatim(tmp_path):
    rev, reason = M._git_rev_detail(tmp_path)

    assert rev is None
    assert "not a git repository" in reason.lower()
    # the back-compat wrapper still answers the old way for `our_git_rev`
    assert M._git_rev(tmp_path) is None


# --------------------------------------------------------------------------- #
# 4. computed ONCE per worker, not once per game                               #
# --------------------------------------------------------------------------- #
def test_the_jar_is_hashed_once_per_process_not_once_per_record(tmp_path, monkeypatch):
    """A worker plays many games and the shaded jar is ~28 MB; the stamp must be a
    cache lookup after the first read. Counted at the READER, so the assertion is
    about I/O, not about which digest object was used."""
    jar, tiles = _jar_in(tmp_path), _tiles_in(tmp_path)
    calls: list[str] = []
    real = M._sha256_stream

    def counting(p):
        calls.append(str(p))
        return real(p)

    monkeypatch.setattr(M, "_sha256_stream", counting)

    a = _manifest(jar, tiles)
    b = _manifest(jar, tiles)

    assert len(calls) == 1, f"jar re-hashed per record: {calls}"
    assert a["jcz_jar_sha256"] == b["jcz_jar_sha256"] == EXPECT_SHA
    assert M._FILE_SHA256_CACHE[str(jar)] == EXPECT_SHA

    # …and the cache is keyed by PATH, so a genuinely different jar is not aliased.
    other = _jar_in(tmp_path / "other", contents=b"different bytes")
    assert M.jar_sha256(other) == hashlib.sha256(b"different bytes").hexdigest()
    assert len(calls) == 2
    assert M.jar_sha256(other) != M.jar_sha256(jar)
    assert len(calls) == 2


# --------------------------------------------------------------------------- #
# 5. a jar that cannot be hashed is a HARD error, never a null stamp           #
# --------------------------------------------------------------------------- #
def test_missing_jar_raises_rather_than_stamping_null(tmp_path):
    missing = tmp_path / "build" / "Engine.jar"

    with pytest.raises(FileNotFoundError, match="Engine.jar"):
        M.jar_sha256(missing)
    with pytest.raises(FileNotFoundError, match="Engine.jar"):
        _manifest(missing, _tiles_in(tmp_path))


def test_a_directory_where_the_jar_should_be_raises(tmp_path):
    """`is_file()`, not `exists()` — a directory is not a readable artifact."""
    d = tmp_path / "build" / "Engine.jar"
    d.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        M.jar_sha256(d)


def test_unreadable_jar_raises_rather_than_stamping_null(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("running as root: mode 000 is still readable")
    jar = _jar_in(tmp_path)
    jar.chmod(0o000)
    try:
        with pytest.raises(OSError):
            M.jar_sha256(jar)
    finally:
        jar.chmod(0o600)


def test_a_failed_hash_is_not_cached(tmp_path):
    """A transient read failure must not poison the process for the rest of the run."""
    jar = tmp_path / "build" / "Engine.jar"
    with pytest.raises(FileNotFoundError):
        M.jar_sha256(jar)
    assert str(jar) not in M._FILE_SHA256_CACHE

    _jar_in(tmp_path)
    assert M.jar_sha256(jar) == EXPECT_SHA


# --------------------------------------------------------------------------- #
# 6. the record schema the downstream readers see                              #
# --------------------------------------------------------------------------- #
def test_the_manifest_types_are_what_the_adjudicator_reads(tmp_path):
    man = _manifest(_jar_in(tmp_path), _tiles_in(tmp_path))

    assert isinstance(man["jcz_jar_sha256"], str)
    assert isinstance(man["jcz_jar_sha256_16"], str)
    assert isinstance(man["jcz_provenance_witness"], str)
    assert isinstance(man["jcz_git_rev_available"], bool)
    assert man["jcz_git_rev"] is None or isinstance(man["jcz_git_rev"], str)
    assert (man["jcz_git_rev_unavailable_reason"] is None
            or isinstance(man["jcz_git_rev_unavailable_reason"], str))
    # nothing the pre-existing consumers read has moved
    for k in ("schema", "our_git_rev", "jcz_repo", "jcz_jar", "jcz_ai_class",
              "jcz_ai_config", "tiles_xml", "tiles_sha256_16", "tile_set",
              "rules_profile", "rules_manifest", "r9_env", "champion_manifest"):
        assert k in man, f"{k} disappeared from the manifest"
    assert man["tile_set"] == "basic:2"
    assert man["rules_profile"] == "fixed_v1"
