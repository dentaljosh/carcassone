#!/usr/bin/env python3
"""Tests for rung3_r5's scoring launcher.

`run_scoring.sh` (the parent campaign's launcher) derives its campaign root
from `$RUN_ID`, which can only ever resolve to
`measurement/tiearb_widening_20260817/` -- it cannot reach
`rung3_r5/chunks/s2/`, because rung3_r5 is a SUCCESSOR PREREG (its own blind
commit, its own corpus, its own staged layer), not a stratum of the R4.5
pair. This file covers three things built to fix that:

1. `rung3_r5/run_scoring_r5.sh` -- a parameterized sibling with the campaign
   root fixed to `rung3_r5/` explicitly, never derived from `$RUN_ID`. Tested
   via `--dry-run` against a scratch campaign tree (a real venv + real
   `scripts/tiletie/` symlinked in, so the salt/module-constant assertions run
   for real; the STAGED position data is small and synthetic) using the REAL,
   committed `ALLOCATION_R5.conf` unmodified, so the test proves the real
   allocation shape actually launches every chunk it claims to.
2. `rung3_r5/ALLOCATION_R5.conf` -- the worker-hour arithmetic, checked both
   as static comment-table numbers and against the REAL 6,602-pair /
   422,528-playout population `stage_r5_corpus.py` reproduces from real
   inputs (scratch, read-only -- never the tracked rung3_r5/ tree).
3. The parent campaign's `ALLOCATION.conf` -- the s2 rows now point at a
   sentinel that is not a valid chunk id ("poisoned", not merely emptied),
   which trips `run_scoring.sh`'s own `[ -d "$PLAN" ] || FATAL` guard loudly
   the moment anyone actually tries to launch an s2 leg -- whether or not the
   voided R4 S2 population ever gets materialized as real chunk dirs.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CAMPAIGN = REPO / "measurement" / "tiearb_widening_20260817"
RUNG3_R5 = CAMPAIGN / "rung3_r5"
TILETIE = REPO / "scripts" / "tiletie"
if str(TILETIE) not in sys.path:
    sys.path.insert(0, str(TILETIE))

import build_r5_corpus as BR5                                       # noqa: E402
import stage_r5_corpus as SR5                                        # noqa: E402

_REL_LEG = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/positions_walled_leg1.jsonl"
_REL_GD = "measurement/tiearb_widening_20260817/shared_run_r4/GATE_DISJOINT.json"
_REL_ARMS = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/ARMS.json"
_REL_PLAN = "measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/POSITIONS_PLAN.json"
_MAIN_CHECKOUT = Path("/home/doctor/projects/carcassone")


def _first_existing(*candidates):
    for c in candidates:
        if c.is_file():
            return c
    return candidates[0]


REAL_LEG = _first_existing(REPO / _REL_LEG, _MAIN_CHECKOUT / _REL_LEG)
REAL_R4_GATE_DISJOINT = _first_existing(REPO / _REL_GD, _MAIN_CHECKOUT / _REL_GD)
REAL_R4_ARMS = _first_existing(REPO / _REL_ARMS, _MAIN_CHECKOUT / _REL_ARMS)
REAL_R4_SOURCE_PLAN = _first_existing(REPO / _REL_PLAN, _MAIN_CHECKOUT / _REL_PLAN)
_REAL_INPUTS_PRESENT = (REAL_LEG.is_file() and REAL_R4_GATE_DISJOINT.is_file()
                        and REAL_R4_ARMS.is_file() and REAL_R4_SOURCE_PLAN.is_file())

# ⚠️ a git worktree has NO `.venv` of its own -- the venv is editable-installed
# against the MAIN checkout only (CLAUDE.md, worktree-isolation note). Every
# scratch-repo fixture below must symlink the MAIN checkout's `.venv`, never
# `REPO/.venv` (which, inside a worktree, does not exist). `_first_existing`
# above is FILE-only (`.is_file()`), so `.venv` (a directory) is checked here,
# not through it.
REAL_VENV = next((c for c in (REPO / ".venv", _MAIN_CHECKOUT / ".venv")
                  if (c / "bin" / "python").is_file()), REPO / ".venv")
_REAL_VENV_PRESENT = (REAL_VENV / "bin" / "python").is_file()


def _parse_conf(path: Path) -> dict:
    out = {}
    for ln in Path(path).read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        v = v.strip()
        if v.startswith('"'):
            v = v[1:].split('"', 1)[0]
        else:
            v = v.split("#", 1)[0].strip()
        out[k.strip()] = v
    return out


# --------------------------------------------------------------------------- #
# 1. the launchers are present, syntactically valid, and shaped right          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("script", ["run_scoring_r5.sh"])
def test_launcher_is_executable_and_syntactically_valid(script):
    p = RUNG3_R5 / script
    assert p.is_file() and p.stat().st_mode & 0o111, f"{script} not executable"
    assert subprocess.run(["bash", "-n", str(p)]).returncode == 0


def test_launcher_campaign_root_is_hard_coded_to_rung3_r5_never_run_id():
    src = (RUNG3_R5 / "run_scoring_r5.sh").read_text()
    assert 'CAMPAIGN="$REPO/measurement/tiearb_widening_20260817/rung3_r5"' in src
    # the defect this launcher exists to fix: composing the root from a
    # sourced $RUN_ID (functional code only -- the header PROSE names the
    # defect by quoting it, which is not the same as committing it).
    functional_lines = [ln for ln in src.splitlines() if not ln.strip().startswith("#")]
    functional_src = "\n".join(functional_lines)
    assert 'CAMPAIGN="$REPO/measurement/$RUN_ID"' not in functional_src
    assert "$RUN_ID" not in functional_src, (
        "run_scoring_r5.sh must never reference $RUN_ID for its campaign "
        "root -- that is exactly the defect being fixed")


def test_launcher_names_every_binding_knob():
    src = (RUNG3_R5 / "run_scoring_r5.sh").read_text()
    assert "--positions-dir" in src and '"$PLAN"' in src
    assert "--arb-backend" in src and "rust" in src
    assert "--arb-legal-mask-cache" in src
    assert "--only-profiles" in src and "walled" in src
    assert "--m 32" in src
    assert "--oracle-sims 100" in src
    assert "WORLD_SEED_SALT" in src
    assert "SHARE_RUN_LOCAL" in src and "SHARE_RUN_REMOTE" in src
    assert "W_EVAL_LOCAL" in src and "W_EVAL_LAPTOP" in src
    assert "setsid nohup" in src and "disown" in src
    assert "--dry-run" in src
    assert "--gate-out" in src and "--manifest-out" in src
    # both flags write under $CAMPAIGN or a var DERIVED from it ($MANIFESTS =
    # "$CAMPAIGN/chunks/manifests") -- never a separate frozen-prereg concept
    # (rung3_r5 has none; see the file header).
    assert 'MANIFESTS="$CAMPAIGN/chunks/manifests"' in src
    for flag, var in (("--gate-out", "$CAMPAIGN"), ("--manifest-out", "$MANIFESTS")):
        i = src.index(flag)
        line = src[i:src.index("\n", i)]
        assert var in line, f"{flag} must land inside rung3_r5's own dirs (line: {line!r})"


def test_launcher_output_is_namespaced_under_rung3_r5_on_the_share():
    src = (RUNG3_R5 / "run_scoring_r5.sh").read_text()
    assert 'SHARE_RUN_R5="$SHARE_RUN/rung3_r5"' in src, (
        "share output must be namespaced under rung3_r5/ so a real launch "
        "can never collide with the parent's (refused) top-level chunks/s2/")


def test_allocation_r5_conf_present_and_shaped():
    conf = _parse_conf(RUNG3_R5 / "ALLOCATION_R5.conf")
    assert conf["STRATUM_ORDER"] == "s2"
    assert conf["JUDGE_ORDER"] == "tier1-greedy clair-puct"
    assert conf["N_CHUNKS_s2"] == "8"
    for box in ("local", "laptop_side"):
        for judge in ("tier1_greedy", "clair_puct"):
            assert f"ALLOC_s2_{box}_{judge}" in conf


# --------------------------------------------------------------------------- #
# 2. the arithmetic -- both the static comment-table numbers and the REAL     #
#    6,602-pair population `stage_r5_corpus.py` reproduces                    #
# --------------------------------------------------------------------------- #
def test_allocation_r5_covers_every_chunk_exactly_once_per_judge():
    conf = _parse_conf(RUNG3_R5 / "ALLOCATION_R5.conf")
    n = int(conf["N_CHUNKS_s2"])
    for judge in ("tier1_greedy", "clair_puct"):
        got = []
        for box in ("local", "laptop_side"):
            got += conf[f"ALLOC_s2_{box}_{judge}"].split()
        assert sorted(int(x) for x in got) == list(range(1, n + 1)), (
            f"{judge}: allocation is not an exact cover of 1..{n} (got "
            f"{sorted(got)}) — a gap loses rids, an overlap double-scores")


def test_allocation_r5_matches_the_two_box_capacity_ratio_on_the_real_population():
    """local : laptop worker-hours ~= 30 : 22*0.75, priced against the REAL
    422,528-playout population (not the static comment-table estimate)."""
    conf = _parse_conf(RUNG3_R5 / "ALLOCATION_R5.conf")
    c_arb, c_if = float(conf["C_ARB_ASSUMED"]), float(conf["C_IF_ASSUMED"])
    rate = float(conf["LAPTOP_RATE"])
    n_play = 422528              # 6602 pairs x 2 arms x 32 worlds (pinned ladder)
    n = int(conf["N_CHUNKS_s2"])
    wh = {}
    for box in ("local", "laptop_side"):
        tot = 0.0
        for judge, c in (("tier1_greedy", c_arb), ("clair_puct", c_if)):
            ks = conf[f"ALLOC_s2_{box}_{judge}"].split()
            tot += len(ks) / n * n_play * c / 3600.0
        wh[box] = tot
    share_local = wh["local"] / (wh["local"] + wh["laptop_side"])
    ideal = 30.0 / (30.0 + 22.0 * rate)
    assert abs(share_local - ideal) < 0.05, (
        f"local takes {share_local:.3f} of the worker-hours, capacity says {ideal:.3f}")


@pytest.mark.skipif(not _REAL_INPUTS_PRESENT,
                    reason="real R4 corpus inputs not present in this checkout")
def test_allocation_r5_arithmetic_matches_the_real_staged_ladder(tmp_path):
    """The REAL end-to-end (build_r5_corpus + stage_r5_corpus, scratch/
    read-only) reproduces the pinned ladder's total exactly, and
    ALLOCATION_R5.conf's committed worker-hour figures are consistent with
    it."""
    corpus, dupe, arms_r5 = BR5.build(
        leg_path=REAL_LEG, r4_gate_disjoint_path=REAL_R4_GATE_DISJOINT,
        r4_arms_path=REAL_R4_ARMS)
    arms_r5_path = tmp_path / "ARMS_R5.json"
    arms_r5_path.write_text(json.dumps(arms_r5, indent=2, sort_keys=True))
    staged_dir = tmp_path / "run" / "corpus" / "positions_s2"
    report = SR5.stage(
        arms_r5_path=arms_r5_path, leg_path=REAL_LEG,
        r4_source_plan_path=REAL_R4_SOURCE_PLAN, staged_dir=staged_dir,
        stage_chunks_out_root=tmp_path / "run", n_chunks=8)

    assert report["n_total_pairs"] == 6602
    assert report["expected_total_arm_playouts"] == 422528
    assert report["total_arm_playouts_agrees"] is True

    conf = _parse_conf(RUNG3_R5 / "ALLOCATION_R5.conf")
    c_arb, c_if = float(conf["C_ARB_ASSUMED"]), float(conf["C_IF_ASSUMED"])
    n_play = report["expected_total_arm_playouts"]
    arb_wh = n_play * c_arb / 3600.0
    if_wh = n_play * c_if / 3600.0
    assert abs(arb_wh - 20.92) < 0.01
    assert abs(if_wh - 275.82) < 0.01
    assert abs((arb_wh + if_wh) - 296.74) < 0.01


# --------------------------------------------------------------------------- #
# 3. the stale s2 trap in the PARENT campaign's ALLOCATION.conf -- poisoned,  #
#    refuses loudly on any attempt to actually launch it                      #
# --------------------------------------------------------------------------- #
_POISON = "VOID_SEE_RUNG3_R5"


def test_parent_allocation_s2_rows_are_poisoned():
    conf = _parse_conf(CAMPAIGN / "ALLOCATION.conf")
    for box in ("local", "laptop_side"):
        for judge in ("tier1_greedy", "clair_puct"):
            assert conf[f"ALLOC_s2_{box}_{judge}"] == _POISON
    assert conf["STRATUM_ORDER"] == "s1", (
        "the default order must not even attempt the void s2 stratum")


def test_parent_allocation_s2_poison_trips_run_scoring_plan_dir_guard():
    """Reproduces `run_scoring.sh`'s OWN `[ -d "$PLAN" ] || FATAL` guard
    (its per-chunk loop) against the REAL, committed `ALLOC_s2_*` value,
    sourced from the real file -- proving the refusal fires whether or not
    chunks/s2/ was ever materialized, because the sentinel can never be a
    real chunk directory name."""
    script = (
        f'set -eu\n. "{CAMPAIGN}/ALLOCATION.conf"\n'
        'CAMPAIGN_DIR="$(mktemp -d)"\n'
        'S=s2\n'
        'for k in $ALLOC_s2_local_tier1_greedy; do\n'
        '  PLAN="$CAMPAIGN_DIR/chunks/$S/chunk${k}"\n'
        '  if [ -d "$PLAN" ]; then echo "UNEXPECTED-EXISTS $PLAN"; exit 1; fi\n'
        '  echo "[test] FATAL: plan dir $PLAN missing"\n'
        'done\n'
        'rm -rf "$CAMPAIGN_DIR"\n')
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert f"chunk{_POISON}" in r.stdout
    assert "FATAL: plan dir" in r.stdout


def test_run_scoring_sh_unchanged_by_this_round():
    """The fix is confined to the ALLOCATION.conf data layer -- the
    coordinator's own framing ("a disclosed edit to the R4-era throughput
    layer"). run_scoring.sh's generic `[ -d "$PLAN" ] || FATAL` guard is what
    makes the poison work; it needed no new code."""
    src = (CAMPAIGN / "run_scoring.sh").read_text()
    assert '[ -d "$PLAN" ] || { echo "[scoring] FATAL: plan dir $PLAN missing"' in src


# --------------------------------------------------------------------------- #
# 4. the launcher's --dry-run, against a scratch campaign tree built from     #
#    the REAL, committed ALLOCATION_R5.conf (unmodified) -- proves the real   #
#    allocation shape launches every chunk it claims to, and nothing else.    #
# --------------------------------------------------------------------------- #
def _leg_line(rid: str) -> str:
    return json.dumps({
        "rid": rid, "root_id": f"r_{rid}", "deck_seed": 1, "ply": 4,
        "seat": 0, "checksum": "C", "rules_profile": "walled",
        "stratum": "selfplay", "game_label": "g", "champ_action": 1,
        "actions": [1, 2],
        "arms": [{"action": 1, "index": 0}, {"action": 2, "index": 1}],
    })


def _build_scratch_chunk(d: Path, rid: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "ARMS.json").write_text(json.dumps({rid: {"arms": [
        {"action": 1, "index": 0}, {"action": 2, "index": 1}]}}))
    leg_path = d / "positions_walled_leg1.jsonl"
    leg_path.write_text(_leg_line(rid) + "\n")
    plan = {
        "uncapped": True, "cap_j": None, "deployed_cap_j": 4,
        "world_seed_salt": "tiletie-v1",
        "afterstate_dedupe": {"applied": True},
        "m_worlds": 32,
        "files": {"walled/leg1": {"path": str(leg_path), "n": 1}},
    }
    (d / "POSITIONS_PLAN.json").write_text(json.dumps(plan))


def _order_doc(rids: list[str]) -> dict:
    order = list(rids)
    digest = hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()
    return {
        "seed": 20260817,
        "strata": {"s2": {"m": 32, "order": order,
                          "chunk_sizes": [1] * len(order),
                          "sha256_order": digest, "n": len(order)}},
    }


@pytest.fixture
def scratch_repo(tmp_path):
    """A scratch REPO with the real `.venv` and `scripts/` symlinked in (so
    the launcher's salt/module-constant assertion runs for real against the
    real `run_tiletie` module), plus a scratch rung3_r5/ campaign built from
    the REAL, committed `ALLOCATION_R5.conf` and `run_scoring_r5.sh`
    (copied verbatim, never re-typed) with 8 tiny synthetic single-rid
    chunks -- enough to exercise every allocated chunk without needing the
    real 6,602-pair corpus."""
    if not _REAL_VENV_PRESENT:
        pytest.skip("no real .venv found to symlink")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".venv").symlink_to(REAL_VENV)
    (repo / "scripts").symlink_to(REPO / "scripts")

    campaign = repo / "measurement" / "tiearb_widening_20260817"
    campaign.mkdir(parents=True)
    share_local = tmp_path / "share_local"
    share_remote = tmp_path / "share_remote"
    share_local.mkdir()
    share_remote.mkdir()
    (campaign / "WORKERS.conf").write_text(
        "W_EVAL_LOCAL=4\nW_EVAL_LAPTOP=3\nNICE=19\n"
        f'SHARE_RUN_LOCAL="{share_local}"\nSHARE_RUN_REMOTE="{share_remote}"\n'
        f'REPO_LOCAL="{repo}"\nREPO_REMOTE="{repo}"\n')

    r5 = campaign / "rung3_r5"
    r5.mkdir()
    shutil.copy2(RUNG3_R5 / "run_scoring_r5.sh", r5 / "run_scoring_r5.sh")
    (r5 / "run_scoring_r5.sh").chmod(0o755)
    # the REAL, committed allocation -- unmodified, so this test proves the
    # actually-deployed shape launches every chunk it claims to.
    shutil.copy2(RUNG3_R5 / "ALLOCATION_R5.conf", r5 / "ALLOCATION_R5.conf")

    rids = [f"tt_sp_{i}" for i in range(1, 9)]
    (r5 / "POSITION_ORDER.json").write_text(json.dumps(_order_doc(rids)))
    for i, rid in enumerate(rids, 1):
        _build_scratch_chunk(r5 / "chunks" / "s2" / f"chunk{i}", rid)

    return repo, r5


def _run(repo: Path, box: str, *extra: str) -> subprocess.CompletedProcess:
    script = repo / "measurement/tiearb_widening_20260817/rung3_r5/run_scoring_r5.sh"
    return subprocess.run([str(script), box, *extra],
                          capture_output=True, text=True, cwd=str(repo))


def test_dry_run_local_prints_exact_command_for_every_allocated_chunk(scratch_repo):
    repo, r5 = scratch_repo
    conf = _parse_conf(r5 / "ALLOCATION_R5.conf")
    r = _run(repo, "local", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr

    arb_chunks = conf["ALLOC_s2_local_tier1_greedy"].split()
    if_chunks = conf["ALLOC_s2_local_clair_puct"].split()
    assert arb_chunks and if_chunks          # sanity: the real conf allocates both

    for k in arb_chunks:
        assert (f'--positions-dir {r5}/chunks/s2/chunk{k} '
                f'--judges tier1-greedy --m 32') in r.stdout
    for k in if_chunks:
        assert (f'--positions-dir {r5}/chunks/s2/chunk{k} '
                f'--judges clair-puct --m 32') in r.stdout

    n_exact = r.stdout.count("[scoring-r5] EXACT:")
    assert n_exact == len(arb_chunks) + len(if_chunks)
    assert r.stdout.count("DRY-RUN: not executing") == n_exact
    assert "--workers 4" in r.stdout          # W_EVAL_LOCAL from scratch WORKERS.conf

    # a true dry run touches no state
    assert not list((r5 / "chunks" / "stamps").glob("DONE_*"))
    assert not (repo.parent / "share_local" / "rung3_r5").exists()


def test_dry_run_laptop_side_prints_exact_command_for_every_allocated_chunk(scratch_repo):
    repo, r5 = scratch_repo
    conf = _parse_conf(r5 / "ALLOCATION_R5.conf")
    r = _run(repo, "laptop-side", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr

    arb_chunks = conf["ALLOC_s2_laptop_side_tier1_greedy"].split()
    if_chunks = conf["ALLOC_s2_laptop_side_clair_puct"].split()
    assert not arb_chunks and if_chunks       # the real conf: no ARB on laptop

    assert "no chunks allocated — skip" in r.stdout   # tier1-greedy, empty
    for k in if_chunks:
        assert (f'--positions-dir {r5}/chunks/s2/chunk{k} '
                f'--judges clair-puct --m 32') in r.stdout
    assert r.stdout.count("[scoring-r5] EXACT:") == len(if_chunks)
    assert "--workers 3" in r.stdout          # W_EVAL_LAPTOP from scratch WORKERS.conf
    assert not list((r5 / "chunks" / "stamps").glob("DONE_*"))


def test_dry_run_chunk_override_narrows_to_one_chunk(scratch_repo):
    repo, r5 = scratch_repo
    r = _run(repo, "local", "tier1-greedy", "3", "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.count("[scoring-r5] EXACT:") == 1
    assert f"{r5}/chunks/s2/chunk3" in r.stdout


def test_real_run_flag_would_create_state_dry_run_does_not(scratch_repo):
    """Negative control: confirm the harness CAN create DONE stamps / share
    dirs at all (so the dry-run assertions above are not vacuous), by
    checking the script's own logic path -- without actually invoking
    run_tiletie.py (no real corpus/venv work in a unit test). The salt/
    POSITION_ORDER preflight already ran to completion in the dry-run tests
    above; this just confirms the mkdir/touch calls are gated on DRY_RUN, not
    unconditional."""
    src = (RUNG3_R5 / "run_scoring_r5.sh").read_text()
    i = src.index('if [ "$DRY_RUN" -eq 1 ]; then')
    guard = src[i:src.index("continue", i) + len("continue")]
    assert 'echo "[scoring-r5] DRY-RUN' in guard and "continue" in guard
    j = src.index("mkdir -p \"$OUT\"")
    assert j > i, "mkdir -p \"$OUT\" must come AFTER the dry-run bail-out"
