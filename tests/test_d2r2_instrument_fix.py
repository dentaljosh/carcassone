"""D2-R2 instrument fix — the four gate repairs, tested.

`measurement/track_d2_prep`'s first attempt adjudicated `U-UNREADABLE` on four
INSTRUMENT gates. `measurement/track_d2r2_prep/` is the pre-registered successor.
This file pins the machinery each fix rests on:

  FIX 1 (G-RULES)  the launcher exports CARCASSONNE_FIX_R9 and refuses without it
  FIX 2 (G-LEAF)   the champion curve125 leaf reaches the CANDIDATE via
                   --cand-leaf-json, hashes a36d2e15a3b3d71d, and leaves the rung
                   on the CL-022 ruler 42af12fce22e1a0f
  FIX 3 (G-TOOL a) the launcher pins the repo rev + code dirt across both cells
  FIX 4 (G-TOOL b) eval_fair_puct's new --stamp-key writes BLIND_COMMIT to BOTH
                   manifest addresses a house read-rule searches

Nothing here plays a game, launches anything, or reads a run statistic.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D2R2 = REPO / "measurement" / "track_d2r2_prep"
LAUNCHER = D2R2 / "run_cells.sh"
HARNESS = REPO / "scripts" / "classical_search" / "eval_fair_puct.py"

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"
RUNG_RULER_LEAF_HASH = "42af12fce22e1a0f"
BAND = "144000000000"

sys.path.insert(0, str(REPO / "scripts" / "classical_search"))


# --------------------------------------------------------------------------- #
# FIX 4 — run_manifest.write_manifest(extra=...)                               #
# --------------------------------------------------------------------------- #
def test_write_manifest_extra_lands_at_top_level(tmp_path):
    from carcassonne_ai.run_manifest import write_manifest

    p = write_manifest(tmp_path, kind="t", game="base", config={"a": 1},
                       extra={"BLIND_COMMIT": "0" * 40})
    m = json.loads(Path(p).read_text())
    assert m["BLIND_COMMIT"] == "0" * 40
    assert m["config"] == {"a": 1}


def test_write_manifest_extra_absent_is_byte_identical(tmp_path):
    from carcassonne_ai.run_manifest import write_manifest

    a = tmp_path / "a"
    b = tmp_path / "b"
    m1 = json.loads(Path(write_manifest(a, kind="t", game="base", config={"a": 1})).read_text())
    m2 = json.loads(Path(write_manifest(b, kind="t", game="base", config={"a": 1},
                                        extra=None)).read_text())
    m1.pop("utc"), m2.pop("utc")
    assert m1 == m2
    assert "stamps" not in m1.get("config", {})


@pytest.mark.parametrize("key", ["code_rev", "config", "rules_profile", "leaf_env", "kind"])
def test_write_manifest_extra_refuses_reserved_keys(tmp_path, key):
    from carcassonne_ai.run_manifest import write_manifest

    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_manifest(tmp_path / key, kind="t", game="base", config={},
                       extra={key: "hijacked"})


def test_write_manifest_extra_refuses_evaluator_collision(tmp_path):
    from carcassonne_ai.run_manifest import write_manifest

    with pytest.raises(ValueError, match="refusing to overwrite"):
        write_manifest(tmp_path, kind="t", game="base", config={},
                       evaluator={"x": 1}, extra={"evaluator": "hijacked"})


# --------------------------------------------------------------------------- #
# FIX 4 — eval_fair_puct._parse_stamp_keys                                     #
# --------------------------------------------------------------------------- #
def _parse():
    import eval_fair_puct as H
    return H._parse_stamp_keys


def test_stamp_keys_parse_basic():
    f = _parse()
    assert f(None) == {}
    assert f([]) == {}
    assert f(["BLIND_COMMIT=abc123"]) == {"BLIND_COMMIT": "abc123"}
    assert f(["A=1", "B=2"]) == {"A": "1", "B": "2"}


def test_stamp_key_value_keeps_equals_and_stays_a_string():
    f = _parse()
    assert f(["RUN=k=v=w"]) == {"RUN": "k=v=w"}
    assert f(["N=0123"])["N"] == "0123"       # never coerced to an int


@pytest.mark.parametrize("bad", [
    "NOEQUALS",           # no separator
    "=value",             # empty key
    "9LEADING=x",         # must start with a letter
    "has-dash=x",         # not [A-Za-z0-9_]
    "has space=x",
    "café=x",             # non-ascii
])
def test_stamp_keys_reject_malformed(bad):
    with pytest.raises(ValueError):
        _parse()([bad])


@pytest.mark.parametrize("forbidden", [
    "code_rev", "config", "rules_profile", "leaf_env", "kind", "host", "utc",
    "n_failed", "cand_tiearb", "carc_rs_version", "utc_end", "mixed_builds",
])
def test_stamp_keys_reject_harness_owned_keys(forbidden):
    with pytest.raises(ValueError, match="manifest key this harness writes"):
        _parse()([f"{forbidden}=hijacked"])


def test_stamp_keys_reject_duplicates_and_oversize():
    f = _parse()
    with pytest.raises(ValueError, match="duplicate"):
        f(["A=1", "A=2"])
    with pytest.raises(ValueError, match="longer than 64"):
        f(["A" * 65 + "=1"])
    with pytest.raises(ValueError, match="longer than 4096"):
        f(["A=" + "x" * 4097])


def test_stamp_key_flag_is_wired_into_the_parser_and_fails_loud():
    """A malformed stamp must abort at argv parse, not after 800 games."""
    r = subprocess.run(
        [sys.executable, str(HARNESS), "--stamp-key", "NOEQUALS", "--smoke"],
        capture_output=True, text=True, cwd=str(REPO), timeout=180,
        env={**os.environ, "PYTHONPATH": f"{REPO/'src'}:{REPO/'engine'}"},
    )
    assert r.returncode != 0
    assert "--stamp-key must be KEY=VALUE" in (r.stderr + r.stdout)


def test_harness_writes_the_stamp_to_both_searched_addresses():
    """G-TOOL reads at manifest TOP LEVEL then at `config.*`. The harness must
    write BOTH, or the gate is satisfiable only under one reading of the rule."""
    tree = ast.parse(HARNESS.read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "write_manifest"]
    assert len(calls) == 1, "expected exactly one write_manifest call site"
    assert "extra" in {k.arg for k in calls[0].keywords}, \
        "the top-level stamp address is gone — G-TOOL(b) becomes unsatisfiable again"
    src = HARNESS.read_text()
    assert 'man_cfg["stamps"] = dict(_stamps)' in src, \
        "the config.* stamp address is gone — G-TOOL(b) half-satisfiable"


# --------------------------------------------------------------------------- #
# FIX 2 — the champion leaf, resolved exactly as the launcher's pre-flight does #
# --------------------------------------------------------------------------- #
def test_cand_leaf_json_resolves_the_champion_and_leaves_the_rung_alone():
    import eval_fair_puct as H

    cand = H._load_cand_leaf_cfg(str(D2R2 / "champion_leaf_curve125.json"))
    H._assert_cy_float_path(cand)
    assert H._leaf_hash(cand) == CHAMP_LEAF_HASH
    assert H._leaf_hash(H.DEFAULT_CONFIG) == RUNG_RULER_LEAF_HASH
    assert H._leaf_hash(cand) != H._leaf_hash(H.DEFAULT_CONFIG)
    # and it is the SAME object the harness auto-injects for the arms that get it
    assert H._leaf_hash(cand) == H._leaf_hash(H._curve125_leaf_cfg())
    assert H._leaf_hash(cand) == H.CURVE125_LEAF_HASH


def test_champion_leaf_json_is_exactly_the_curve125_override():
    d = json.loads((D2R2 / "champion_leaf_curve125.json").read_text())
    assert set(d) == {"v29_meeple_curve"}, \
        "the cell overrides the CURVE and nothing else — any extra field is a new leaf"
    import eval_fair_puct as H
    assert tuple(float(x) for x in d["v29_meeple_curve"]) == H.CURVE125


# --------------------------------------------------------------------------- #
# The launcher's guards, called directly via its library-mode seam.            #
# --------------------------------------------------------------------------- #
def _sh(body: str, env: dict | None = None, role: str = "local"):
    """Source the launcher in library mode (nothing runs) and execute `body`."""
    script = (
        "set +e\n"
        f"CARC_D2R2_LIB_ONLY=1 source {LAUNCHER!s} {role}\n"
        "set +e\n"
        f"{body}\n"
    )
    e = {**os.environ, "CARC_PY": sys.executable}
    e.update(env or {})
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          cwd=str(REPO), timeout=300, env=e)


def test_launcher_exports_r9_and_assert_passes():
    r = _sh("assert_r9_env; echo RC=$?")
    assert "RC=0" in r.stdout
    assert "CARCASSONNE_FIX_R9=1" in r.stdout


def test_assert_r9_env_refuses_when_unset():
    r = _sh("unset CARCASSONNE_FIX_R9; (assert_r9_env); echo RC=$?")
    assert "RC=3" in r.stdout
    assert "G-RULES" in r.stdout or "r9_env_ok=False" in r.stdout


@pytest.mark.parametrize("bad", ["", "0", "no", "off"])
def test_assert_r9_env_refuses_non_truthy(bad):
    r = _sh(f"CARCASSONNE_FIX_R9='{bad}'; (assert_r9_env); echo RC=$?")
    assert "RC=3" in r.stdout


def test_launcher_source_actually_exports_r9_to_children():
    """The export must be at FILE SCOPE, so every child process inherits it —
    an assertion alone would not have fixed G-RULES."""
    r = _sh("python3 -c \"import os; print('CHILD_R9=' + repr(os.environ.get('CARCASSONNE_FIX_R9')))\"")
    assert "CHILD_R9='1'" in r.stdout


def test_preflight_leaf_passes_and_names_both_hashes():
    r = _sh("preflight_leaf; echo RC=$?")
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    assert CHAMP_LEAF_HASH in r.stdout
    assert RUNG_RULER_LEAF_HASH in r.stdout


def test_preflight_leaf_refuses_a_non_champion_leaf(tmp_path):
    bad = tmp_path / "not_the_champion.json"
    bad.write_text(json.dumps({"v29_meeple_curve": [-8, -4, -1, 0, 2, 3, 4, 5]}))
    r = _sh(f"CAND_LEAF_JSON={bad!s}; (preflight_leaf); echo RC=$?")
    assert "RC=4" in r.stdout
    assert "G-LEAF WOULD VOID" in r.stdout or "SAME leaf" in r.stdout


def test_preflight_leaf_refuses_a_moved_rung_ruler():
    """Exporting the curve env moves DEFAULT_CONFIG — i.e. moves the RUNG. That is
    the failure the in-process injection exists to make impossible, and the
    pre-flight must catch it if someone does it anyway."""
    r = _sh("export CARCASSONNE_V29_MEEPLE_CURVE=-10,-5,-1.25,0,2.5,3.75,5,6.25; "
            "(preflight_leaf); echo RC=$?")
    assert "RC=4" in r.stdout
    assert "G-RUNG WOULD VOID" in r.stdout or "SAME leaf" in r.stdout


def test_require_clean_code_refuses_dirty_code_paths():
    r = _sh("code_dirty_list() { printf 'M src/carcassonne_ai/mcts.py\\n'; }; "
            "(require_clean_code); echo RC=$?")
    assert "RC=6" in r.stdout
    assert "CODE PATHS ARE DIRTY" in r.stdout


def test_require_clean_code_passes_on_clean_code_paths():
    r = _sh("code_dirty_list() { :; }; require_clean_code; echo RC=$?")
    assert "RC=0" in r.stdout


def test_dirty_override_needs_a_reason():
    body = "code_dirty_list() { printf 'M src/x.py\\n'; }; (require_clean_code); echo RC=$?"
    r = _sh(body, env={"LAUNCH_DIRTY": "1"})
    assert "RC=6" in r.stdout
    assert "requires LAUNCH_DIRTY_REASON" in r.stdout

    r2 = _sh(body, env={"LAUNCH_DIRTY": "1", "LAUNCH_DIRTY_REASON": "hotfix under review"})
    assert "RC=0" in r2.stdout
    assert "hotfix under review" in r2.stdout


def test_assert_rev_unmoved_refuses_a_moved_rev():
    r = _sh("snapshot_rev >/dev/null; SNAP_REV=deadbeef; "
            "(assert_rev_unmoved 'cell R1600'); echo RC=$?")
    assert "RC=5" in r.stdout
    assert "rev MOVED between cells" in r.stdout
    assert "deadbeef" in r.stdout


def test_assert_rev_unmoved_refuses_changed_code_dirt():
    r = _sh("snapshot_rev >/dev/null; SNAP_CODE_DIRTY=notthefingerprint; "
            "(assert_rev_unmoved 'cell R1600'); echo RC=$?")
    assert "RC=5" in r.stdout
    assert "dirty-state CHANGED" in r.stdout


def test_assert_rev_unmoved_passes_when_nothing_moved():
    r = _sh("snapshot_rev >/dev/null; assert_rev_unmoved 'cell R1600'; echo RC=$?")
    assert "RC=0" in r.stdout


# --------------------------------------------------------------------------- #
# The launcher's argv — G-SINGLEVAR, the band, and the four fixes in place.    #
# --------------------------------------------------------------------------- #
def _dry_run_argv():
    r = subprocess.run(["bash", str(LAUNCHER), "local", "--dry-run"],
                       capture_output=True, text=True, cwd=str(REPO), timeout=300,
                       env={**os.environ, "CARC_PY": sys.executable})
    assert r.returncode == 0, r.stdout + r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("[dry-run] cell ")]
    assert len(lines) == 2, r.stdout
    return r.stdout, [ln.split(":", 1)[1].split() for ln in lines]


def test_dry_run_cells_differ_in_exactly_the_three_permitted_arguments():
    _, (a, b) = _dry_run_argv()

    def argmap(toks):
        d, i = {}, 0
        while i < len(toks):
            if toks[i].startswith("--"):
                nxt = toks[i + 1] if i + 1 < len(toks) else None
                if nxt is not None and not nxt.startswith("--"):
                    d[toks[i]] = nxt
                    i += 2
                    continue
                d[toks[i]] = True
            i += 1
        return d

    da, db = argmap(a), argmap(b)
    assert set(da) == set(db)
    differing = {k for k in da if da[k] != db[k]}
    assert differing == {"--rung-sims", "--out-subdir", "--claim-host"}, differing
    assert (da["--rung-sims"], db["--rung-sims"]) == ("800", "1600")


def test_dry_run_argv_carries_every_fix():
    out, (a, _b) = _dry_run_argv()
    joined = " ".join(a)
    assert f"--seed-start {BAND}" in joined                       # fresh band
    assert "--cand-leaf-json" in joined                            # FIX 2
    assert "champion_leaf_curve125.json" in joined
    assert "--rules-profile fixed_v1" in joined
    assert "--k-dets 4" in joined and "--sims 1032" in joined      # the carried re-pick
    assert "--n 400" in joined and "--paired" in joined
    assert "--cand-tiearb" not in joined                           # arbiter OFF (§0(d))
    assert "CARCASSONNE_FIX_R9=1" in out                           # FIX 1
    assert CHAMP_LEAF_HASH in out and RUNG_RULER_LEAF_HASH in out  # FIX 2 pre-flight
    assert "rev snapshot" in out                                   # FIX 3
    assert "--stamp-key BLIND_COMMIT" in out                       # FIX 4 (named in the note)


def test_launcher_never_exports_the_curve_env():
    """Exporting CARCASSONNE_V29_MEEPLE_CURVE would move DEFAULT_CONFIG and so move
    the h800 RUNG to curve125 — silently invalidating the CL-022 ruler."""
    for ln in LAUNCHER.read_text().splitlines():
        s = ln.strip()
        assert not s.startswith("export CARCASSONNE_V29_MEEPLE_CURVE"), ln
        assert not s.startswith(("source ", ". ")) or "champ_env" not in s, ln
    # and the running launcher genuinely adds none of its own. (Scrubbed env: an
    # earlier `import eval_fair_puct` in this same process applies the harness's
    # _CANON_ENV — which sets the curve100 RULER value — to os.environ.)
    script = (f"CARC_D2R2_LIB_ONLY=1 source {LAUNCHER!s} local\n"
              "python3 -c \"import os; print('CURVE=' + repr(os.environ.get("
              "'CARCASSONNE_V29_MEEPLE_CURVE')))\"\n")
    clean = {k: v for k, v in os.environ.items()
             if k != "CARCASSONNE_V29_MEEPLE_CURVE"}
    clean["CARC_PY"] = sys.executable
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       cwd=str(REPO), timeout=300, env=clean)
    assert "CURVE=None" in r.stdout, r.stdout + r.stderr


def test_launcher_refuses_a_band_that_disagrees_with_the_pair():
    r = subprocess.run(["bash", str(LAUNCHER), "local", "--dry-run", "--band", "999000000000"],
                       capture_output=True, text=True, cwd=str(REPO), timeout=120,
                       env={**os.environ, "CARC_PY": sys.executable})
    assert r.returncode == 2
    assert "disagrees with the pair's PINNED_BAND" in r.stderr + r.stdout


def test_blind_commit_placeholder_refuses_a_real_cell():
    """The pair ships with a placeholder BLIND_COMMIT; a real cell must refuse
    until the orchestrator stamps the real sha."""
    r = _sh("(require_blind_and_band); echo RC=$?")
    assert "RC=2" in r.stdout
    assert "40-hex-char sha" in r.stdout


# --------------------------------------------------------------------------- #
# The successor pair itself — the parts a reader must be able to trust.        #
# --------------------------------------------------------------------------- #
def test_successor_pair_carries_the_bars_verbatim():
    """Bars do not move. Spot-check every threshold the branches key on."""
    rr = (D2R2 / "READ_RULE.md").read_text()
    old = (REPO / "measurement" / "track_d2_prep" / "READ_RULE.md").read_text()
    for bar in ["`z_S ≥ 2.0` **AND** `S ≥ 2.5 pts`", "`z_S ≥ 2.0`, `S < 2.5 pts`",
                "`|z_S| < 2.0`", "`z_S ≤ −2.0`", "se(S) = 1.25 pts",
                "`[0.85, 1.20]`", "`[0.50, 0.90]`"]:
        assert bar in rr, bar
        assert bar in old, f"{bar} — not a verbatim bar of the original"
    # the four branch names and U-UNREADABLE, unchanged
    for br in ["D2-COARSE", "D2-COMPRESSED", "D2-BOUNDED-NULL", "D2-REVERSED", "U-UNREADABLE"]:
        assert br in rr


def test_successor_read_rule_structural_test_covers_all_nine_gates():
    """The miss that let the first attempt ship: §3.1 audited 4 of 9 gates."""
    rr = (D2R2 / "READ_RULE.md").read_text()
    sec = rr.split("### §3.1")[1].split("## §4")[0]
    for gate in ["G-BAND", "G-SINGLEVAR", "G-RUNG", "G-LEAF", "G-RULES",
                 "G-TOOL", "G-N", "G-TIMING", "G-SAT"]:
        assert gate in sec, f"§3.1 does not audit {gate}"


def test_successor_banner_declares_blindness_and_the_four_fixes():
    d = (D2R2 / "DESIGN.md").read_text()
    banner = d.split("# RUNG COMPRESSION")[0]
    assert "STATISTICS-BLIND" in banner
    assert "U-UNREADABLE" in banner
    assert "k4×1032" in banner            # the carried §9 re-pick
    for gate in ["G-RULES", "G-LEAF", "G-TOOL"]:
        assert gate in banner
    assert 'manifest["BLIND_COMMIT"]' in banner


def test_successor_band_is_consistent_everywhere():
    for f in ["DESIGN.md", "READ_RULE.md", "BAND_CLAIM_DRAFT.json", "run_cells.sh"]:
        txt = (D2R2 / f).read_text()
        assert BAND in txt, f
        assert "141000000000" not in txt or f in ("DESIGN.md", "READ_RULE.md",
                                                  "BAND_CLAIM_DRAFT.json")
    assert "PINNED_BAND=144000000000" in (D2R2 / "run_cells.sh").read_text()


def test_band_claim_is_drafted_not_claimed():
    d = json.loads((D2R2 / "BAND_CLAIM_DRAFT.json").read_text())
    assert d["status"] == "DRAFT-NOT-CLAIMED"
    assert d["band_seed_start"] == BAND
    assert not (D2R2 / "BAND_CLAIMED").exists(), \
        "BAND_CLAIMED is the EXECUTOR's sentinel; this pair must not ship it"
    registry = (REPO / "governance" / "BAND_REGISTRY.csv").read_text()
    assert not registry.startswith(BAND) and f"\n{BAND}," not in registry, \
        "the band was APPENDED — this session plans the row, it does not claim it"
