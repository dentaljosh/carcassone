"""D2-R3 cost-calibration instrument — the burn-in gate and its launcher, tested.

`measurement/track_d2r2_prep` passed eight of nine gates and died on `G-TIMING`:
the quantity a PILOT measured (an equal-time ratio at n=16, W unsaturated) was
not the quantity the CELL realized (n=400, W=22 saturated). D2-R3's fix is that
the LIVE gate and the POST-HOC gate are literally the same code
(`measurement/track_d2r3_prep/d2r3_lib.py`) reading the same per-game records
over a window that is INSIDE the adjudicated games.

This file pins that machinery:

  1. TRANSCRIPTION FIDELITY, ON REAL DATA — `read_full_cell()` over the real
     completed d2r2 archive reproduces that archive's own `summary.json` timing
     figures. This is the test that proves the library's arithmetic really is
     `eval_fair_puct._summary()` and not a plausible re-derivation of it.
  2. the burn-in window is defined by SEED, never by arrival order
  3. fail-closed behaviours of `timing_ratio`
  4. the bars are CLOSED intervals at exactly the frozen endpoints
  5. tenancy needs CONSECUTIVE confirmation, not one transient
  6. the launcher's guards, via its `CARC_D2R3_LIB_ONLY` seam
  7. the shell carries NO second copy of any bar

⛔ Nothing here plays a game, launches anything, or reads a win / loss / margin /
elo field. Test 1 reads exactly three fields of one real `summary.json`:
`champ_prefix_ms_per_move`, `rung_ms_per_move`, `n`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D2R3 = REPO / "measurement" / "track_d2r3_prep"
LAUNCHER = D2R3 / "run_cells.sh"

sys.path.insert(0, str(D2R3))
# Importing from measurement/ must not leave a __pycache__ behind: the freeze
# ceremony commits that directory, and a byte-cache dir is untracked churn in the
# very tree whose cleanliness the launcher asserts.
_DONT_WRITE = sys.dont_write_bytecode
sys.dont_write_bytecode = True
import d2r3_lib as L  # noqa: E402
sys.dont_write_bytecode = _DONT_WRITE

# The completed d2r2 CELL R800 archive — 200 decks on band 144000000000, the
# only real saturated cell this instrument has ever had to read.
D2R2_ARCHIVE = Path("/mnt/c/carc-shared/track_d2r2_prep/d2r2_rung800")
D2R2_BAND = 144000000000
D2R2_DECKS = 200


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _rec(seed: int, a: int, champ_secs: float, champ_moves: int,
         rung_secs: float, rung_moves: int) -> dict:
    return {
        "seed": seed, "a_seat": a,
        "champ_prefix_secs": champ_secs, "champ_prefix_moves": champ_moves,
        "rung_secs": rung_secs, "rung_moves": rung_moves,
    }


def _write(d: Path, seed: int, a: int, **kw) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"seed{seed:012d}_a{a}.json"
    p.write_text(json.dumps(_rec(seed, a, **kw)))
    return p


def _reading(ratio: float | None, complete: bool = True) -> L.RatioReading:
    """A RatioReading with an EXACT ratio, so bar-endpoint tests are exact and
    not hostage to float division of synthesized seconds."""
    return L.RatioReading(
        n_games=80, n_decks=40,
        champ_ms_per_move=ratio, rung_ms_per_move=1.0, ratio=ratio,
        champ_secs_total=0.0, champ_moves_total=0,
        rung_secs_total=0.0, rung_moves_total=0,
        seed_lo=L.BAND, seed_hi=L.BAND + L.N_BURNIN_DECKS - 1,
        complete=complete,
    )


# =========================================================================== #
# 1. TRANSCRIPTION FIDELITY ON REAL DATA — the most important test here.       #
# =========================================================================== #
@pytest.mark.skipif(not D2R2_ARCHIVE.is_dir(),
                    reason=f"real d2r2 archive absent at {D2R2_ARCHIVE}")
def test_read_full_cell_reproduces_the_harness_own_summary_on_a_real_archive():
    """`d2r3_lib`'s arithmetic IS `eval_fair_puct._summary()`.

    If this ever fails, the live burn-in gate and the harness's own summary are
    measuring different things — which is precisely the class of defect that
    killed attempt 2, only one layer deeper.
    """
    summary = json.loads((D2R2_ARCHIVE / "summary.json").read_text())
    want_champ = summary["champ_prefix_ms_per_move"]
    want_rung = summary["rung_ms_per_move"]
    want_n = summary["n"]

    r = L.read_full_cell(D2R2_ARCHIVE, band=D2R2_BAND, n_decks=D2R2_DECKS)

    assert r.n_games == want_n, (r.n_games, want_n)
    assert r.complete, (r.missing[:4], r.malformed[:4])
    assert r.champ_ms_per_move == pytest.approx(want_champ, rel=1e-6)
    assert r.rung_ms_per_move == pytest.approx(want_rung, rel=1e-6)
    # and the derived ratio is the same division the harness would do
    assert r.ratio == pytest.approx(want_champ / want_rung, rel=1e-6)


# =========================================================================== #
# 2. The burn-in window is defined by SEED, not by arrival order.              #
# =========================================================================== #
def test_burnin_seeds_are_exactly_the_first_n_decks_of_the_band():
    seeds = L.burnin_seeds()
    assert seeds == [L.BAND + i for i in range(L.N_BURNIN_DECKS)]
    assert len(seeds) == L.N_BURNIN_DECKS
    assert seeds[0] == L.BAND
    assert seeds[-1] == L.BAND + L.N_BURNIN_DECKS - 1


def test_one_missing_burnin_game_fails_closed_and_the_last_one_flips_it(tmp_path):
    """79 of 80 is an UNKNOWN window, and gating on an unknown window is what a
    gate exists to prevent. The 80th record must flip it, and nothing else."""
    cell = tmp_path / "d2r3_rung800"
    seeds = L.burnin_seeds()
    kw = dict(champ_secs=10.0, champ_moves=100, rung_secs=10.0, rung_moves=100)
    for s in seeds:
        for a in (0, 1):
            if s == seeds[-1] and a == 1:
                continue  # hold back exactly one
            _write(cell, s, a, **kw)

    r = L.read_burnin(cell)
    assert r.n_games == 2 * L.N_BURNIN_DECKS - 1
    assert r.complete is False
    assert r.missing == [f"seed{seeds[-1]:012d}_a1.json"]
    assert L.verdict(r, L.TIMING_LO, L.TIMING_HI)["pass"] is False, \
        "an incomplete window must FAIL even when the ratio it can see is in-bar"

    _write(cell, seeds[-1], 1, **kw)
    r2 = L.read_burnin(cell)
    assert r2.n_games == 2 * L.N_BURNIN_DECKS
    assert r2.complete is True
    assert r2.missing == []
    assert L.verdict(r2, L.TIMING_LO, L.TIMING_HI)["pass"] is True


def test_window_membership_ignores_arrival_order(tmp_path):
    """Records outside the window are excluded no matter when they arrive; the
    pool completes out of order, so an arrival-order window is not reproducible
    by an adjudicator."""
    cell = tmp_path / "cell"
    kw = dict(champ_secs=1.0, champ_moves=10, rung_secs=1.0, rung_moves=10)
    # a deck far past the window lands FIRST
    _write(cell, L.BAND + L.N_BURNIN_DECKS + 7, 0, **kw)
    for s in L.burnin_seeds():
        for a in (0, 1):
            _write(cell, s, a, **kw)
    r = L.read_burnin(cell)
    assert r.n_games == 2 * L.N_BURNIN_DECKS
    assert r.seed_hi == L.BAND + L.N_BURNIN_DECKS - 1
    assert r.complete is True


# =========================================================================== #
# 3. `timing_ratio` fail-closed behaviours.                                    #
# =========================================================================== #
def test_empty_record_set_yields_none_ratio_and_is_out_of_bar():
    r = L.timing_ratio([])
    assert r.ratio is None
    assert r.champ_ms_per_move is None and r.rung_ms_per_move is None
    assert L.in_bar(r.ratio, L.TIMING_LO, L.TIMING_HI) is False
    assert L.verdict(r, L.TIMING_LO, L.TIMING_HI, require_complete=False)["pass"] is False


def test_a_failed_subdir_record_is_never_counted(tmp_path):
    """`<cell>/failed/` carries games that did not finish. A non-recursive glob
    keeps them out of every cost reading."""
    cell = tmp_path / "cell"
    kw = dict(champ_secs=1.0, champ_moves=10, rung_secs=1.0, rung_moves=10)
    _write(cell, L.BAND, 0, **kw)
    _write(cell, L.BAND, 1, **kw)
    # a plausible-looking record in the failed/ subdir, with WILDLY different cost
    _write(cell / "failed", L.BAND + 1, 0,
           champ_secs=999.0, champ_moves=1, rung_secs=0.001, rung_moves=1)

    recs, mal = L.load_records(cell)
    r = L.timing_ratio(recs, malformed=mal)
    assert r.n_games == 2
    assert r.ratio == pytest.approx(1.0)
    assert all("failed" not in m for m in r.malformed)


def test_a_record_missing_a_timing_field_is_malformed_and_forces_incomplete(tmp_path):
    cell = tmp_path / "cell"
    seeds = L.burnin_seeds()
    kw = dict(champ_secs=1.0, champ_moves=10, rung_secs=1.0, rung_moves=10)
    for s in seeds:
        for a in (0, 1):
            _write(cell, s, a, **kw)
    # break exactly one record by dropping a required field
    victim = cell / f"seed{seeds[3]:012d}_a1.json"
    bad = json.loads(victim.read_text())
    bad.pop("rung_moves")
    victim.write_text(json.dumps(bad))

    recs, mal = L.load_records(cell, seed_lo=seeds[0], seed_hi=seeds[-1])
    assert victim.name in mal
    r = L.timing_ratio(recs, expect_seeds=seeds, malformed=mal)
    assert r.complete is False, "a malformed record must not be silently skipped"
    assert victim.name in r.malformed
    assert L.verdict(r, L.TIMING_LO, L.TIMING_HI)["pass"] is False

    # ...and read_burnin, the path the live gate actually uses, agrees.
    rb = L.read_burnin(cell)
    assert rb.complete is False
    assert victim.name in rb.malformed


def test_required_timing_fields_are_the_four_summary_inputs():
    assert set(L.REQUIRED_TIMING_FIELDS) == {
        "champ_prefix_secs", "champ_prefix_moves", "rung_secs", "rung_moves"}


# =========================================================================== #
# 4. The bars are CLOSED intervals at exactly the frozen endpoints.            #
# =========================================================================== #
@pytest.mark.parametrize("ratio", [0.85, 1.20])
def test_verdict_passes_exactly_on_the_endpoints(ratio):
    assert (L.TIMING_LO, L.TIMING_HI) == (0.85, 1.20), \
        "the frozen bar moved — that is a PAIR-level change, not a code change"
    assert L.in_bar(ratio, L.TIMING_LO, L.TIMING_HI) is True
    assert L.verdict(_reading(ratio), L.TIMING_LO, L.TIMING_HI)["pass"] is True


@pytest.mark.parametrize("ratio", [0.8499, 1.2001])
def test_verdict_fails_just_outside_the_endpoints(ratio):
    assert L.in_bar(ratio, L.TIMING_LO, L.TIMING_HI) is False
    assert L.verdict(_reading(ratio), L.TIMING_LO, L.TIMING_HI)["pass"] is False


def test_verdict_records_the_bar_it_used():
    v = L.verdict(_reading(1.0), L.TIMING_LO, L.TIMING_HI)
    assert (v["bar_lo"], v["bar_hi"]) == (L.TIMING_LO, L.TIMING_HI)


# =========================================================================== #
# 5. Tenancy needs CONSECUTIVE confirmation.                                   #
# =========================================================================== #
def _sample(pct: float, utc: str = "t") -> dict:
    return {"utc": utc, "foreign_total_cpu_pct": pct, "foreign_procs": []}


def test_one_isolated_over_bar_sample_is_not_a_cotenant():
    """A transient `git status` or a log rotation must not kill a 2h cell."""
    over = L.FOREIGN_TOTAL_CPU_PCT + 50.0
    roll = L.tenancy_summary([_sample(1.0), _sample(over), _sample(1.0), _sample(2.0)])
    assert roll["max_consecutive_breach_samples"] == 1
    assert roll["exclusive"] is True


def test_two_consecutive_over_bar_samples_are_a_cotenant():
    over = L.FOREIGN_TOTAL_CPU_PCT + 50.0
    roll = L.tenancy_summary([_sample(1.0), _sample(over), _sample(over), _sample(1.0)])
    assert roll["max_consecutive_breach_samples"] >= L.TENANCY_CONFIRM_SAMPLES
    assert roll["exclusive"] is False
    assert roll["breach_windows"], "a confirmed breach must name when it happened"


def test_two_non_consecutive_over_bar_samples_are_not_a_cotenant():
    over = L.FOREIGN_TOTAL_CPU_PCT + 50.0
    roll = L.tenancy_summary(
        [_sample(over), _sample(1.0), _sample(over), _sample(1.0)])
    assert roll["max_consecutive_breach_samples"] == 1
    assert roll["exclusive"] is True
    assert roll["max_foreign_total_cpu_pct"] == pytest.approx(over)


# =========================================================================== #
# 6. The launcher's guards, via the CARC_D2R3_LIB_ONLY seam.                   #
# =========================================================================== #
def _sh(body: str, env: dict | None = None, role: str = "local"):
    """Source the launcher in library mode (nothing runs) and execute `body`."""
    script = (
        "set +e\n"
        f"CARC_D2R3_LIB_ONLY=1 source {LAUNCHER!s} {role}\n"
        "set +e\n"
        f"{body}\n"
    )
    e = {**os.environ, "CARC_PY": sys.executable}
    e.update(env or {})
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          cwd=str(REPO), timeout=300, env=e)


def test_launcher_exports_r9_and_assert_passes():
    r = _sh("assert_r9_env; echo RC=$?")
    assert "RC=0" in r.stdout, r.stdout + r.stderr
    assert "CARCASSONNE_FIX_R9=1" in r.stdout


@pytest.mark.parametrize("mangle", ["unset CARCASSONNE_FIX_R9",
                                    "export CARCASSONNE_FIX_R9=''"])
def test_assert_r9_env_refuses_when_unset_or_empty(mangle):
    r = _sh(f"{mangle}; (assert_r9_env); echo RC=$?")
    assert "RC=3" in r.stdout, r.stdout + r.stderr
    assert "G-RULES" in r.stdout


def test_launcher_refuses_a_real_cell_on_the_placeholder_blind_commit():
    """The pair ships with a placeholder BLIND_COMMIT; a real cell must refuse
    until the executor stamps the real sha after the freeze ceremony."""
    assert (D2R3 / "BLIND_COMMIT").read_text().strip() == \
        "PLACEHOLDER_BLIND_COMMIT_NOT_YET_STAMPED"
    r = _sh("(require_blind_and_band); echo RC=$?")
    assert "RC=2" in r.stdout, r.stdout + r.stderr
    assert "40-hex" in r.stdout


def test_launcher_refuses_the_retired_laptop_role():
    """D2-R3 is single-box by construction: the equal-time budget is calibrated
    against W=22 saturated figures on THIS box."""
    r = subprocess.run(["bash", str(LAUNCHER), "laptop-side", "--dry-run"],
                       capture_output=True, text=True, cwd=str(REPO), timeout=120,
                       env={**os.environ, "CARC_PY": sys.executable})
    assert r.returncode == 2
    out = r.stdout + r.stderr
    assert "the ONLY valid role for D2-R3 is 'local'" in out
    assert "W=22" in out and "shared-claim" in out


def test_launcher_refuses_a_band_that_disagrees_with_the_pair():
    r = subprocess.run(["bash", str(LAUNCHER), "local", "--dry-run",
                        "--band", "999000000000"],
                       capture_output=True, text=True, cwd=str(REPO), timeout=120,
                       env={**os.environ, "CARC_PY": sys.executable})
    assert r.returncode == 2
    assert "disagrees with the pair's PINNED_BAND" in r.stdout + r.stderr


def test_proc_alive_distinguishes_live_from_gone_and_from_a_zombie():
    """The supervisor loop's completion test. A background child that has exited
    is a ZOMBIE until reaped and `kill -0` SUCCEEDS on a zombie, so `kill -0`
    alone would spin forever; `proc_alive` reads the process STATE instead."""
    r = _sh(
        "proc_alive $$ && echo SELF=yes || echo SELF=no;\n"
        "proc_alive '' && echo EMPTY=yes || echo EMPTY=no;\n"
        "sleep 30 & V=$!; kill -KILL $V 2>/dev/null; wait $V 2>/dev/null || true;\n"
        "proc_alive $V && echo DEAD=yes || echo DEAD=no;\n"
        # a REAL zombie: a grandchild whose parent never reaps it
        "setsid bash -c 'sleep 60 & echo $! > /tmp/.d2r3_zpid; sleep 5' "
        "  >/dev/null 2>&1 & sleep 0.5;\n"
        "Z=$(cat /tmp/.d2r3_zpid 2>/dev/null || echo 0);\n"
        "kill -KILL $Z 2>/dev/null; sleep 0.5;\n"
        "st=$(awk '{print $3}' /proc/$Z/stat 2>/dev/null || echo none);\n"
        "echo STATE=$st;\n"
        "if [ \"$st\" = Z ]; then proc_alive $Z && echo ZOMB=yes || echo ZOMB=no; "
        "else echo ZOMB=skipped; fi;\n"
        "rm -f /tmp/.d2r3_zpid"
    )
    assert "SELF=yes" in r.stdout, r.stdout + r.stderr
    assert "EMPTY=no" in r.stdout, r.stdout + r.stderr
    assert "DEAD=no" in r.stdout, r.stdout + r.stderr
    # the zombie leg is best-effort (scheduling-dependent); when it materialises,
    # proc_alive MUST report it dead.
    assert "ZOMB=yes" not in r.stdout, r.stdout + r.stderr


# --------------------------------------------------------------------------- #
# The launcher's argv — the probe axis, the band, and the cell order.          #
# --------------------------------------------------------------------------- #
def _dry_run_argv():
    r = subprocess.run(["bash", str(LAUNCHER), "local", "--dry-run"],
                       capture_output=True, text=True, cwd=str(REPO), timeout=300,
                       env={**os.environ, "CARC_PY": sys.executable})
    assert r.returncode == 0, r.stdout + r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("[dry-run] cell ")]
    assert len(lines) == 2, r.stdout
    return r.stdout, [ln.split(":", 1)[1].split() for ln in lines]


def _argmap(toks):
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


def test_dry_run_cells_differ_in_exactly_the_three_permitted_arguments():
    _, (a, b) = _dry_run_argv()
    da, db = _argmap(a), _argmap(b)
    assert set(da) == set(db)
    differing = {k for k in da if da[k] != db[k]}
    assert differing == {"--rung-sims", "--out-subdir", "--claim-host"}, differing
    assert (da["--rung-sims"], db["--rung-sims"]) == ("800", "1600")
    # R800 is printed FIRST — it carries the gate and is the shorter cell.
    assert da["--out-subdir"] == "d2r3_rung800"
    assert db["--out-subdir"] == "d2r3_rung1600"


def test_dry_run_argv_carries_the_new_probe_axis_and_the_new_band():
    out, (a, b) = _dry_run_argv()
    for toks in (a, b):
        d = _argmap(toks)
        # ⚠️ the probe axis (--sims) is IDENTICAL across the cells and collides
        # numerically with CELL R1600's --rung-sims. Different axes.
        assert d["--sims"] == "1600"
        assert d["--k-dets"] == "4"
        assert d["--seed-start"] == str(L.BAND)
        assert d["--n"] == "400" and d.get("--paired") is True
        assert d["--rules-profile"] == "fixed_v1"
        assert d["--workers"] == "22"
        assert d["--cand-leaf-json"].endswith("champion_leaf_curve125.json")
        assert "--cand-tiearb" not in d, "the tie-arbiter is OFF for this pair"
    assert _argmap(b)["--rung-sims"] == "1600" == _argmap(b)["--sims"], \
        "the collision G-PROBE exists to make checkable"
    assert "CARCASSONNE_FIX_R9=1" in out                                # FIX 1
    assert "a36d2e15a3b3d71d" in out and "42af12fce22e1a0f" in out      # FIX 2
    assert "rev snapshot" in out                                        # FIX 3
    assert "--stamp-key BLIND_COMMIT" in out                            # FIX 4


def test_launcher_never_exports_the_curve_env():
    """Exporting CARCASSONNE_V29_MEEPLE_CURVE would move DEFAULT_CONFIG and so
    move the h800 RUNG to curve125 — silently invalidating the CL-022 ruler."""
    for ln in LAUNCHER.read_text().splitlines():
        s = ln.strip()
        assert not s.startswith("export CARCASSONNE_V29_MEEPLE_CURVE"), ln
        assert not s.startswith(("source ", ". ")) or "champ_env" not in s, ln


# =========================================================================== #
# 7. The shell carries NO second copy of any bar.                              #
# =========================================================================== #
def _code_lines(path: Path):
    """Lines of a shell script with FULL-LINE comments removed.

    Deliberately conservative: every bar/threshold mention in `run_cells.sh`
    lives on a full-comment line, so this is sufficient and cannot be fooled by
    a `#` inside a quoted string.
    """
    for i, ln in enumerate(path.read_text().splitlines(), 1):
        if ln.lstrip().startswith("#"):
            continue
        yield i, ln


BAR_LITERALS = [
    str(L.TIMING_LO),        # 0.85   equal-time floor
    str(L.TIMING_HI),        # 1.2    equal-time ceiling  (also matched as "1.20")
    "1.20",
    str(L.TIMING_FULL_LO),   # 0.75   whole-cell drift floor
    str(L.TIMING_FULL_HI),   # 1.35   whole-cell drift ceiling
    str(L.FOREIGN_TOTAL_CPU_PCT),
    str(L.FOREIGN_PROC_CPU_PCT),
]


@pytest.mark.parametrize("lit", sorted(set(BAR_LITERALS)))
def test_launcher_carries_no_second_copy_of_any_bar(lit):
    """Every bar lives in d2r3_lib.py and nowhere else. A shell that retypes one
    is a shell that can silently disagree with the adjudicator — the exact defect
    class this pair was rebuilt to remove."""
    hits = [(i, ln) for i, ln in _code_lines(LAUNCHER) if lit in ln]
    assert hits == [], f"bar literal {lit!r} duplicated in the shell: {hits}"


def test_launcher_pins_the_band_once_and_it_matches_the_library():
    hits = [(i, ln) for i, ln in _code_lines(LAUNCHER) if str(L.BAND) in ln]
    assert len(hits) == 1, f"the band literal must appear exactly once in code: {hits}"
    assert hits[0][1].strip() == f"PINNED_BAND={L.BAND}", hits[0][1]
    assert L.BAND == 149000000000, "the pair's band moved — that is a PAIR-level change"


def test_launcher_shells_out_for_every_reading_it_gates_on():
    """Positive form of the same rule: the gate/census/sampler paths are the
    library's CLI, not shell arithmetic."""
    src = LAUNCHER.read_text()
    for sub in ("census", "sampler", "watch"):
        assert f'"$LIB" {sub}' in src, f"launcher does not shell out for `{sub}`"
    assert "import d2r3_lib as L" in src, \
        "the launcher's own JSON writers must read the bars from the library"


def test_launcher_uses_set_m_and_guards_the_cell_pgid():
    """`feedback_set_m_not_setsid_for_cell_groups`: never derive a PGID with
    `ps -o pgid= -p $!` after setsid — it can return the DRIVER's group, so the
    driver kills itself and the cell orphans."""
    src = LAUNCHER.read_text()
    assert "set -m" in src and "set +m" in src
    assert 'GROUP_KILL_SAFE=1' in src and 'GROUP_KILL_SAFE=0' in src
    # the guard: observed pgid must equal the cell pid AND differ from the driver's
    assert '"$observed" = "$CELL_PID"' in src
    assert '"$observed" != "$driver"' in src


def test_launcher_smoke_leg_has_no_timing_authority_and_calls_the_adjudicator():
    src = LAUNCHER.read_text()
    # the retired flag survives only as prose in the banner, never as a code path
    pilot_hits = [(i, ln) for i, ln in _code_lines(LAUNCHER) if "--pilot" in ln]
    assert pilot_hits == [], f"the pilot leg is retired; --smoke replaces it: {pilot_hits}"
    assert "NOT A GATE" in src
    assert "--smoke-mode --cell-r800" in src
    assert "analyze_d2r3.py" in src
    assert str(149999999000) in src, "the smoke leg needs its disjoint throwaway range"
