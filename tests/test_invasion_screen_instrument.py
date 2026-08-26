"""INSTRUMENT TESTS — invasion-risk term family, round-1 screen at 2752.

Pair under test: `measurement/invasion_screen_prep/` (`DESIGN.md` + `READ_RULE.md`),
its bar library `screen_lib.py`, its adjudicator `analyze_screen.py`, and its
launcher `run_cells.sh`.

Adapted from `tests/test_d2r4_instrument.py`. Three properties are load-bearing
and each has tests below:

1. **BARS LIVE IN ONE IMPLEMENTATION POINT.** Every threshold is `screen_lib`'s,
   and the launcher pins only the BAND as a numeric literal. A launcher that
   drifts from the pair is a launcher defect — so `WORKERS.conf::BAND` and
   `run_cells.sh::PINNED_BAND`-equivalent are asserted equal to `screen_lib.BAND`,
   and the launcher is asserted NOT to hard-code any other bar.

2. **NO SELF-INVALIDATING TESTS.** A test that re-asserts a constant against
   itself proves nothing and silently "passes" through any edit. So the tests
   below check RELATIONSHIPS and BEHAVIOUR — branch transitions AT each bar, the
   two-sidedness of a set equality, that ABSENT is FAIL, that the seed ranges are
   disjoint and contiguous, that the leaf JSONs actually hash to their pinned
   values through the harness's own code path.

3. **THE ADJUDICATOR IS VALIDATED AGAINST A REAL EMITTED MANIFEST**, never a
   synthesized one — `analyze_screen.py --selftest` must exit 0.

⚠️ These tests run against the STALE venv `carc_rs`: nothing here needs the rust
invasion kwargs. The one test that touches the harness only builds LeafConfigs and
hashes them, which is pure Python.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PREP = REPO / "measurement" / "invasion_screen_prep"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


L = _load("screen_lib_under_test", PREP / "screen_lib.py")
A = _load("analyze_screen_under_test", PREP / "analyze_screen.py")


# ═══════════════════════════════════════════════════════════════════════════ #
# 1. THE SPEC IS INTERNALLY CONSISTENT                                        #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_sanity_check_is_clean():
    """`screen_lib.sanity_check()` is the spec's own consistency proof: n_games ==
    2*n_decks, no seed claimed twice, ranges contiguous, the smoke range disjoint,
    IDENT's hash == the champion's and every arm's != it, and the drift-flag
    asymmetry. A typo in a seed range must not survive to launch."""
    assert L.sanity_check() == []


def test_cell_ranges_are_disjoint_and_contiguous():
    """DESIGN §5.1 — disjoint is what `G-DECKS` gates on; contiguous is what makes
    the band a single readable block. Checked as a RELATIONSHIP, not by
    re-asserting the four literals."""
    ordered = sorted(L.CELLS, key=lambda c: c.seed_start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.seed_end < b.seed_start, f"{a.name} overlaps {b.name}"
        assert b.seed_start == a.seed_end + 1, f"gap between {a.name} and {b.name}"
    assert ordered[0].seed_start == L.BAND
    total = sum(c.n_decks for c in L.CELLS)
    assert total == 1400
    assert sum(c.n_games for c in L.CELLS) == 2 * total


def test_every_cell_is_deck_paired():
    for c in L.CELLS:
        assert c.n_games == 2 * c.n_decks


def test_smoke_range_cannot_reach_any_cell():
    smoke = set(range(L.SMOKE_SEED_START, L.SMOKE_SEED_START + L.SMOKE_DECKS))
    for c in L.CELLS:
        assert not (smoke & set(c.seeds)), f"SMOKE range touches {c.name}"


def test_ident_is_a_precondition_not_an_arm():
    """DESIGN §3.1 — no PROMOTE/BRACKET/REVERSED branch may fire on IDENT."""
    assert L.IDENT_CELL.role == "precondition"
    assert L.IDENT_CELL.name not in {c.name for c in L.ARM_CELLS}
    assert len(L.ARM_CELLS) == 3


# ═══════════════════════════════════════════════════════════════════════════ #
# 2. BARS LIVE IN ONE PLACE — the launcher pins only the band                 #
# ═══════════════════════════════════════════════════════════════════════════ #
def _workers_conf() -> dict[str, str]:
    out = {}
    for line in (PREP / "WORKERS.conf").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.split("#")[0].strip()
    return out


def test_workers_conf_band_matches_screen_lib():
    """The launcher's ONE numeric literal that matters must agree with the bar
    library. This is the drift the `require_table_agrees` preflight also checks at
    runtime; here it is checked at build time."""
    assert int(_workers_conf()["BAND"]) == L.BAND


def test_launcher_does_not_hardcode_any_bar():
    """⛔ The launcher must not carry a copy of any THRESHOLD. It may carry the
    band, the budget and operational constants (W, timeouts, RAM floors); the
    bars belong to `screen_lib` alone, which is why the in-flight IDENT pre-check
    imports it instead of re-implementing `|z| <= 2`."""
    sh = (PREP / "run_cells.sh").read_text()
    for forbidden in ("PROMOTE_Z", "BRACKET_Z", "REVERSED_Z", "SIGMA_D_MODEL",
                      "ELO_PER_PT_BRACKET", "N_COMMON_FRAC", "SAT_WR"):
        assert f"{forbidden}=" not in sh, f"launcher hard-codes the bar {forbidden}"
    # it must reach the bar through the library, not around it
    assert "screen_lib.py" in sh
    assert "ident_gate" in sh
    assert "IDENT_ABS_Z_MAX" in sh


def test_launcher_cell_table_agrees_with_screen_lib():
    """`run_cells.sh`'s declare -A tables are a convenience for bash; every field
    must match the library, and the launcher re-checks this at runtime too."""
    sh = (PREP / "run_cells.sh").read_text()
    for c in L.CELLS:
        assert f"[{c.name}]={c.seed_start}" in sh, f"{c.name} seed_start"
        assert f"[{c.name}]={c.n_decks}" in sh, f"{c.name} n_decks"
        assert f"[{c.name}]={c.n_games}" in sh, f"{c.name} n_games"
        assert f"[{c.name}]={c.leaf_json}" in sh, f"{c.name} leaf_json"
        assert f"[{c.name}]={1 if c.allow_leaf_hash_drift else 0}" in sh, f"{c.name} drift"


def _launcher_code() -> str:
    """`run_cells.sh` with COMMENT lines stripped. The pair's prose deliberately
    NAMES the forbidden flags in order to forbid them, so a raw substring scan
    would flag the very comment that documents the rule."""
    out = []
    for line in (PREP / "run_cells.sh").read_text().splitlines():
        s = line.lstrip()
        if s.startswith("#"):
            continue
        out.append(line.split("  #")[0])
    return "\n".join(out)


def _argv_builders() -> str:
    """The bodies of the two places `run_cells.sh` constructs a harness argv —
    `build_argv()` and the smoke's inline array. Scanning THESE (rather than the
    whole file) is the honest test: the pair's prose deliberately NAMES the
    forbidden flags in order to forbid them, and a `log` line that says
    'NO --cand-tiearb-* flag is emitted below' must not itself trip the check."""
    text = (PREP / "run_cells.sh").read_text()
    body = []
    keep = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("build_argv()") or s.startswith("ARGV=(") or s.startswith("SARGV=("):
            keep = True
        if keep:
            body.append(line)
        if keep and s == "}":
            keep = False
    return "\n".join(body)


def test_launcher_table_preflight_actually_runs():
    """⭐ EXECUTE the launcher's `require_table_agrees` python, don't just read it.

    The embedded heredocs are the launcher's real logic and a typo in one is
    invisible until launch — this test found `c.allow_hash_drift` (the field is
    `allow_leaf_hash_drift`) at freeze, in a preflight that would have aborted the
    round on its first real invocation. It also proves the sys.modules
    registration that `@dataclass` needs under a heredoc-fed stdin."""
    src = (PREP / "run_cells.sh").read_text()
    m = re.search(r"<<'TEOF'.*?\n(.*?)\nTEOF", src, re.S)
    assert m, "could not find the TEOF preflight heredoc"
    table = "\n".join(
        "|".join([c.name, str(c.seed_start), str(c.n_decks), str(c.n_games),
                  c.out_subdir, str(int(c.allow_leaf_hash_drift)), c.cand_leaf_hash])
        for c in L.CELLS)
    env = {"CARC_LIB": str(PREP / "screen_lib.py"), "CARC_BAND": str(L.BAND),
           "CARC_TABLE": table}
    r = subprocess.run([sys.executable, "-c", m.group(1)], capture_output=True,
                       text=True, env={**__import__("os").environ, **env})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "cell ranges disjoint" in r.stdout


def test_launcher_table_preflight_rejects_a_drifted_table():
    """The preflight must FAIL closed when the shell table disagrees with the
    library — otherwise it is decoration."""
    src = (PREP / "run_cells.sh").read_text()
    m = re.search(r"<<'TEOF'.*?\n(.*?)\nTEOF", src, re.S)
    rows = []
    for i, c in enumerate(L.CELLS):
        seed = c.seed_start + (7 if i == 0 else 0)     # corrupt ONE field
        rows.append("|".join([c.name, str(seed), str(c.n_decks), str(c.n_games),
                              c.out_subdir, str(int(c.allow_leaf_hash_drift)),
                              c.cand_leaf_hash]))
    env = {"CARC_LIB": str(PREP / "screen_lib.py"), "CARC_BAND": str(L.BAND),
           "CARC_TABLE": "\n".join(rows)}
    r = subprocess.run([sys.executable, "-c", m.group(1)], capture_output=True,
                       text=True, env={**__import__("os").environ, **env})
    assert r.returncode != 0
    assert "seed_start" in r.stdout


def test_launcher_never_arms_the_tie_arbiter():
    """DESIGN §0(d) / G-TIEARB — no `--cand-tiearb-*` flag of any spelling is ever
    EMITTED into a harness argv. (The opponent side has no arming flag at all in
    the harness, so there is nothing to withhold there.)"""
    argv = _argv_builders()
    assert argv.strip(), "could not locate the argv builder in run_cells.sh"
    assert "tiearb" not in argv.lower()


def test_launcher_argv_is_symmetric_in_the_budget():
    """The single-variable property, at the source: `--k-dets`/`--sims` and
    `--opp-k-dets`/`--opp-sims` must be driven by the SAME two shell variables, so
    the two sides cannot drift apart by editing one of them."""
    argv = _argv_builders()
    assert '--k-dets "$K_DETS"' in argv and '--opp-k-dets "$K_DETS"' in argv
    assert '--sims     "$SIMS_PER_DET"' in argv or '--sims "$SIMS_PER_DET"' in argv
    assert '--opp-sims "$SIMS_PER_DET"' in argv


def test_launcher_is_not_executable():
    """The house pattern: tracked at mode 644. `chmod +x` is the ORCHESTRATOR's
    own launch act, never the build's."""
    mode = subprocess.run(["git", "-C", str(REPO), "ls-files", "-s",
                           "measurement/invasion_screen_prep/run_cells.sh"],
                          capture_output=True, text=True).stdout
    if mode.strip():
        assert mode.split()[0] == "100644", f"run_cells.sh is tracked as {mode.split()[0]}"


def test_drift_flag_asymmetry_in_the_launcher():
    """DESIGN §2.2 — the flag is emitted for A/B/D and WITHHELD on IDENT. A
    drift-flag on IDENT would throw away the harness's own strict hash assertion,
    which is a free extra gate there."""
    sh = (PREP / "run_cells.sh").read_text()
    assert "--allow-leaf-hash-drift" in sh
    assert 'CELL_DRIFT=( [IDENT]=0' in sh.replace("declare -A ", "")


# ═══════════════════════════════════════════════════════════════════════════ #
# 3. BRANCH BEHAVIOUR — driven AT each bar, not re-asserted                   #
# ═══════════════════════════════════════════════════════════════════════════ #
@pytest.mark.parametrize("z,expected", [
    (5.00, "PROMOTE"),
    (2.01, "PROMOTE"),
    (2.00, "PROMOTE"),     # READ_RULE §4 writes `z >= +2.0` — the endpoint PROMOTES
    (1.99, "BRACKET"),
    (1.00, "BRACKET"),     # `+1.0 <= z` — the endpoint BRACKETS
    (0.99, "NULL"),
    (0.00, "NULL"),
    (-1.99, "NULL"),
    (-2.00, "REVERSED"),   # `z <= -2.0` — the endpoint REVERSES
    (-2.01, "REVERSED"),
    (-9.00, "REVERSED"),
])
def test_branch_endpoints(z, expected):
    assert L.branch_for_cell(z, gates_ok=True) == expected


def test_a_failed_gate_beats_every_branch():
    """READ_RULE §4's stated order of evaluation: `U-UNREADABLE` FIRST."""
    for z in (5.0, 2.0, 1.0, 0.0, -2.0, -9.0):
        assert L.branch_for_cell(z, gates_ok=False) == "U-UNREADABLE"


def test_absent_z_is_unreadable_not_null():
    """A cell with no statistic is UNREADABLE. Reading it as NULL would convert a
    broken cell into evidence of no effect — the exact inversion §4 forbids."""
    assert L.branch_for_cell(None, gates_ok=True) == "U-UNREADABLE"
    assert L.branch_for_cell(float("nan"), gates_ok=True) == "U-UNREADABLE"


def test_round_branch_kill_requires_every_arm_null():
    assert L.round_branch({"IDENT": "NULL", "A_MID": "NULL", "B_MID": "NULL",
                           "D_MID": "NULL"}) == "SCREEN-NULL-family-parks"
    assert L.round_branch({"IDENT": "NULL", "A_MID": "BRACKET", "B_MID": "NULL",
                           "D_MID": "NULL"}) == "MIXED"
    assert L.round_branch({"IDENT": "NULL", "A_MID": "REVERSED", "B_MID": "NULL",
                           "D_MID": "NULL"}) == "MIXED"


def test_one_unreadable_cell_voids_the_round_branch():
    assert L.round_branch({"IDENT": "U-UNREADABLE", "A_MID": "NULL", "B_MID": "NULL",
                           "D_MID": "NULL"}) == "U-UNREADABLE"


# ═══════════════════════════════════════════════════════════════════════════ #
# 4. G-IDENT                                                                  #
# ═══════════════════════════════════════════════════════════════════════════ #
@pytest.mark.parametrize("z,ok", [(0.0, True), (1.99, True), (2.0, True),
                                  (2.01, False), (-2.0, True), (-2.01, False),
                                  (None, False), (float("nan"), False)])
def test_ident_z_bar_is_two_sided_and_closed(z, ok):
    assert L.ident_z_ok(z) is ok


def test_ident_gate_needs_every_conjunct():
    """Each conjunct alone can fail the gate — so a wiring defect cannot hide
    behind a lucky z, and a lucky z cannot rescue a wiring defect."""
    base = dict(mean=0.1, z=0.3, n_paired=200, leaf_hash_ok=True, n_failed=0,
                leaf_diff_empty=True)
    assert L.ident_gate(base["mean"], base["z"], base["n_paired"],
                        leaf_hash_ok=True, n_failed=0, leaf_diff_empty=True)["ok"]
    for kill in ("leaf_hash_ok", "n_failed", "leaf_diff_empty"):
        kw = dict(leaf_hash_ok=True, n_failed=0, leaf_diff_empty=True)
        kw[kill] = 1 if kill == "n_failed" else False
        assert not L.ident_gate(0.1, 0.3, 200, **kw)["ok"], f"{kill} did not fail the gate"
    assert not L.ident_gate(0.1, 9.9, 200, leaf_hash_ok=True, n_failed=0,
                            leaf_diff_empty=True)["ok"]


def test_ident_failure_is_reported_as_ambiguous_never_as_a_defect():
    """READ_RULE §3.4 — a null bar fails by luck ~5% of the time. The readout must
    NOT assert a defect."""
    r = L.ident_gate(0.1, 9.9, 200, leaf_hash_ok=True, n_failed=0, leaf_diff_empty=True)
    assert "AMBIGUOUS" in r["reading"].upper()
    assert "U-UNREADABLE" in r["consequence"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 5. THE STATISTIC                                                            #
# ═══════════════════════════════════════════════════════════════════════════ #
def _rec(seed, a_seat, diff, won=False, drew=False):
    return {"seed": seed, "a_seat": a_seat, "diff": diff,
            "won_by_champ": won, "drew": drew}


def test_paired_margin_matches_a_hand_computation():
    recs = [_rec(1, 0, 4.0), _rec(1, 1, 2.0), _rec(2, 0, -1.0), _rec(2, 1, -3.0)]
    mean, z, n, se, per = L.paired_margin(recs)
    assert per == [3.0, -2.0]           # (4+2)/2 and (-1-3)/2
    assert n == 2
    assert mean == pytest.approx(0.5)
    sd = math.sqrt(((3.0 - 0.5) ** 2 + (-2.0 - 0.5) ** 2) / 1)
    assert se == pytest.approx(sd / math.sqrt(2))
    assert z == pytest.approx(0.5 / se)


def test_half_paired_decks_are_dropped_never_defaulted():
    """READ_RULE §1 / `_paired_z`'s own `if 0 in v and 1 in v`. A deck seen at one
    seat only must vanish from the estimator, not contribute a one-sided margin."""
    recs = [_rec(1, 0, 4.0), _rec(1, 1, 2.0), _rec(2, 0, 99.0)]
    _, _, n, _, per = L.paired_margin(recs)
    assert n == 1 and per == [3.0]


def test_fewer_than_two_decks_yields_no_z_at_all():
    recs = [_rec(1, 0, 4.0), _rec(1, 1, 2.0)]
    mean, z, n, se, _ = L.paired_margin(recs)
    assert (mean, z, n, se) == (None, None, 1, None)


def test_winrate_elo_uses_the_record_flags_not_the_sign_of_diff():
    """W/D/L classification moves under the WC tie rule while `diff` does not; this
    pair does not run that rule, so the flags are authoritative."""
    recs = [_rec(1, 0, -5.0, won=True), _rec(1, 1, 5.0, won=False),
            _rec(2, 0, 0.0, drew=True), _rec(2, 1, 1.0, won=True)]
    r = L.winrate_elo(recs)
    assert (r["W"], r["D"], r["L"]) == (2, 1, 1)
    assert r["winrate"] == pytest.approx((2 + 0.5) / 4)


def test_recon_none_closes_only_to_none():
    """ABSENT must witness ABSENT — a missing analyzer field must not reconcile
    against a small number."""
    assert L.recon_close(None, None)
    assert not L.recon_close(None, 0.0)
    assert not L.recon_close(0.0, None)
    assert L.recon_close(1.0, 1.0 + 1e-12)
    assert not L.recon_close(1.0, 1.0001)


# ═══════════════════════════════════════════════════════════════════════════ #
# 6. THE GUARDED ELO CONVERSION                                               #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_elo_limb_switches_at_the_bar():
    assert L.elo_display(2.0, 3.0, 55.0, 0.7)["limb"] == "own-ratio"
    assert L.elo_display(1.99, 3.0, 55.0, 0.7)["limb"] == "pinned-bracket"
    assert L.elo_display(-2.0, -3.0, -55.0, 0.7)["limb"] == "own-ratio"


def test_null_limb_refuses_to_print_a_measured_scale():
    """READ_RULE §4.4 — under a null, `elo/D` is a quotient of two noisy near-zero
    quantities. The cell's own ratio must NOT be reportable."""
    d = L.elo_display(0.3, 0.02, 1.0, 0.73)
    assert d["elo_per_point"] is None
    assert d["two_sigma_elo_lo"] is not None and d["two_sigma_elo_hi"] is not None
    assert "NOT A MEASURED SCALE" in d["label"].upper()


def test_own_ratio_limb_flags_a_reading_outside_the_in_family_bracket():
    inside = L.elo_display(3.0, 3.0, 3.0 * 18.0, 0.7)
    assert inside["elo_per_point_outside_bracket"] is False
    outside = L.elo_display(3.0, 3.0, 3.0 * 900.0, 0.7)
    assert outside["elo_per_point_outside_bracket"] is True
    assert "NEVER a branch input" in outside["anomaly_note"]


def test_zero_margin_cannot_reach_the_division():
    assert L.elo_display(9.0, 0.0, 12.0, 0.7)["limb"] == "pinned-bracket"


# ═══════════════════════════════════════════════════════════════════════════ #
# 7. G-SINGLEVAR's set equality is TWO-SIDED                                  #
# ═══════════════════════════════════════════════════════════════════════════ #
def _manifest(cand_inv: dict, opp_inv: dict | None = None) -> dict:
    """A minimal but STRUCTURALLY REAL manifest, shaped like the emitted one."""
    fixture = json.loads((PREP / "selftest_fixture" / "manifest.json").read_text())
    cfg = fixture["config"]
    cfg["cand_leaf_cfg"] = dict(cfg["cand_leaf_cfg"], **cand_inv)
    cfg["opp_leaf_cfg"] = dict(cfg["opp_leaf_cfg"], **(opp_inv or {}))
    return fixture


class _FakeCell(A.Cell):
    def __init__(self, spec, manifest, summary, records):
        self.spec = spec
        self.name = spec.name
        self.path = Path("/nonexistent")
        self.manifest = manifest
        self.summary = summary
        self.records = records
        self.flat = {"manifest": A.flatten(manifest), "summary": A.flatten(summary)}


def _gates_for(spec, cand_inv, opp_inv=None):
    man = _manifest(cand_inv, opp_inv)
    summ = json.loads((PREP / "selftest_fixture" / "summary.json").read_text())
    recs = [json.loads(p.read_text())
            for p in sorted((PREP / "selftest_fixture").glob("seed*_a*.json"))]
    cell = _FakeCell(spec, man, summ, recs)
    g, _ = A.run_gates(cell, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    return g


def test_singlevar_passes_when_the_leaf_diff_is_exactly_the_frozen_key_set():
    a = L.cell_by_name("A_MID")
    g = _gates_for(a, {"invasion_beta": 0.12})
    assert g.results["G-SINGLEVAR"]["ok"], g.results["G-SINGLEVAR"]


def test_singlevar_fails_on_an_EXTRA_differing_key():
    """The obvious direction: a second knob leaked in."""
    a = L.cell_by_name("A_MID")
    g = _gates_for(a, {"invasion_beta": 0.12, "invasion_gamma": 0.5})
    assert not g.results["G-SINGLEVAR"]["ok"]


def test_singlevar_fails_when_the_EXPECTED_key_is_identical_on_both_sides():
    """⭐ THE OTHER DIRECTION, and the one a naive subset check would miss: the
    cell's own knob never reached the leaf, so the two sides are identical and the
    cell silently measures NOTHING. Set equality is two-sided for this reason."""
    a = L.cell_by_name("A_MID")
    g = _gates_for(a, {"invasion_beta": 0.12}, {"invasion_beta": 0.12})
    assert not g.results["G-SINGLEVAR"]["ok"]


def test_singlevar_fails_when_a_search_knob_differs_across_the_sides():
    a = L.cell_by_name("A_MID")
    man = _manifest({"invasion_beta": 0.12})
    man["config"]["opponent"]["champ_cfg"]["c_puct"] = 9.9
    summ = json.loads((PREP / "selftest_fixture" / "summary.json").read_text())
    cell = _FakeCell(a, man, summ, [])
    g, _ = A.run_gates(cell, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    assert not g.results["G-SINGLEVAR"]["ok"]


def test_invasion_gate_rejects_an_opponent_side_knob():
    a = L.cell_by_name("A_MID")
    g = _gates_for(a, {"invasion_beta": 0.12}, {"invasion_delta_farm": 0.3})
    assert not g.results["G-INVASION"]["ok"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 8. G-TIEARB's container/terminal split                                      #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_tiearb_passes_on_a_healthy_archive_with_a_terminal_tiearb_key():
    """⭐ THE FREEZE-TIME CORRECTION. A healthy manifest emits
    `config.champion.tiearb_enabled = false` — a TERMINAL key containing
    'tiearb'. The first draft of the gate scanned all segments and would have
    voided every healthy cell."""
    a = L.cell_by_name("A_MID")
    man = _manifest({"invasion_beta": 0.12})
    assert man["config"]["champion"]["tiearb_enabled"] is False   # the real shape
    g = _gates_for(a, {"invasion_beta": 0.12})
    assert g.results["G-TIEARB"]["ok"], g.results["G-TIEARB"]


def test_tiearb_catches_an_armed_terminal_flag():
    a = L.cell_by_name("A_MID")
    man = _manifest({"invasion_beta": 0.12})
    man["config"]["champion"]["tiearb_enabled"] = True
    summ = json.loads((PREP / "selftest_fixture" / "summary.json").read_text())
    g, _ = A.run_gates(_FakeCell(a, man, summ, []), pinned_src_rev=None,
                       blind_commit=None, wheel_probe=None)
    assert not g.results["G-TIEARB"]["ok"]


def test_tiearb_catches_an_armed_opponent_CONTAINER():
    """An armed opponent block flattens to `opp_tiearb.enabled`, whose LEAF name
    is `enabled` — only the CONTAINER segment carries the tell-tale name."""
    a = L.cell_by_name("A_MID")
    man = _manifest({"invasion_beta": 0.12})
    man["config"]["opp_tiearb"] = {"enabled": True, "B": 16}
    summ = json.loads((PREP / "selftest_fixture" / "summary.json").read_text())
    g, _ = A.run_gates(_FakeCell(a, man, summ, []), pinned_src_rev=None,
                       blind_commit=None, wheel_probe=None)
    assert not g.results["G-TIEARB"]["ok"]


# ═══════════════════════════════════════════════════════════════════════════ #
# 9. ABSENT IS FAIL, for every gate                                           #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_absent_is_fail_for_every_gate():
    """READ_RULE §3.1 question 4. Driven by an EMPTY archive: not one gate may
    pass with no data. This caught three vacuous passes at freeze
    (`G-INVASION`, `G-CAPFWD`, `G-TIEARB`), each of which was a 'nothing bad was
    found' predicate that is trivially true of nothing."""
    empty = _FakeCell(L.cell_by_name("A_MID"), {}, {}, [])
    g, _ = A.run_gates(empty, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    passed = [r["id"] for r in g.results.values() if r["ok"]]
    assert passed == [], f"gates passed with NO data: {passed}"


def test_every_gate_id_in_read_rule_is_implemented():
    empty = _FakeCell(L.cell_by_name("A_MID"), {}, {}, [])
    g, _ = A.run_gates(empty, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    # G-IDENT is applied round-wide by the adjudicator, not per-cell in run_gates
    assert set(L.GATE_IDS) - set(g.results) == {"G-IDENT"}


def test_gate_ids_are_exactly_the_eighteen_read_rule_names():
    assert len(L.GATE_IDS) == 18
    assert len(set(L.GATE_IDS)) == 18


# ═══════════════════════════════════════════════════════════════════════════ #
# 10. THE SMOKE ALLOWED SET                                                   #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_smoke_allowed_set_matches_read_rule_3_5():
    """READ_RULE §3.5's list, verbatim. If this set ever silently WIDENS, a gate
    that cannot read emitted output could slip past the smoke — which is the one
    thing the smoke leg exists to prevent."""
    assert L.SMOKE_ALLOWED_FAILURES == frozenset(
        {"G-BAND", "G-DECKS", "G-N", "G-SAT", "G-IDENT", "RECON/n_paired"})


def test_every_allowed_failure_carries_a_stated_reason():
    """An allowed failure with no reason is an un-auditable exemption."""
    for gid in L.SMOKE_ALLOWED_FAILURES:
        assert L.SMOKE_ALLOWED_REASONS.get(gid), f"{gid} has no stated reason"


def test_the_structural_gates_are_NOT_excusable_on_a_smoke():
    must_pass = {"G-SINGLEVAR", "G-LEAF", "G-INVASION", "G-CAPFWD", "G-WHEEL",
                 "G-RULES", "G-BACKEND", "G-BUDGET", "G-TIEARB", "G-EXACT",
                 "G-REV", "G-BLIND"}
    assert not (must_pass & set(L.SMOKE_ALLOWED_FAILURES))


# ═══════════════════════════════════════════════════════════════════════════ #
# 11. THE LEAF JSONS ROUND-TRIP TO THEIR PINNED HASHES                        #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_leaf_jsons_hash_to_their_pinned_values_through_the_harness():
    """The pinned hashes are not decoration: `G-LEAF(c)` gates on them, and the
    IDENT/arm asymmetry is what proves the drift-flag was applied correctly.
    Computed through the harness's OWN `_load_cand_leaf_cfg` + `_leaf_hash`."""
    sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
    sys.path.insert(0, str(REPO / "src"))
    sys.path.insert(0, str(REPO / "engine"))
    H = pytest.importorskip("eval_fair_puct", reason="harness not importable")
    for c in L.CELLS:
        cfg = H._load_cand_leaf_cfg(str(PREP / c.leaf_json))
        assert H._leaf_hash(cfg) == c.cand_leaf_hash, f"{c.name} leaf hash drifted"
        assert tuple(cfg.v29_meeple_curve) == tuple(L.CURVE125), f"{c.name} is not curve125"


def test_ident_hashes_as_the_champion_and_the_arms_do_not():
    """SHAPES.md §6 — the hash names the leaf FUNCTION, so an explicit-zero
    invasion config IS the champion leaf. This asymmetry is load-bearing for
    DESIGN §2.2's drift-flag rule."""
    assert L.IDENT_CELL.cand_leaf_hash == L.PROD_LEAF_HASH
    for c in L.ARM_CELLS:
        assert c.cand_leaf_hash != L.PROD_LEAF_HASH


def test_every_frozen_knob_is_off_its_default():
    """A knob frozen AT its default would be dropped by `_leaf_dict` and could
    never be observed in a manifest — the cell would measure nothing and
    `G-SINGLEVAR` would (correctly) void it."""
    for c in L.ARM_CELLS:
        for k, v in c.invasion_values.items():
            assert v != L.INVASION_DEFAULTS[k], f"{c.name}.{k} is at its default"


# ═══════════════════════════════════════════════════════════════════════════ #
# 12. THE COST MODEL USES THE TWO-POINT FIT                                   #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_cost_model_is_not_a_naive_linear_per_sim_rate():
    """DESIGN §6.1 — the per-move cost has a ~160 ms FIXED component, so a naive
    `0.159 ms/sim x 2752` under-prices by ~11%. Checked as a RELATIONSHIP: the
    model must be strictly super-linear-at-the-origin, i.e. cost(2N) < 2*cost(N)."""
    assert L.ms_per_move(2752) == pytest.approx(160.0 + 0.12025 * 2752)
    assert L.ms_per_move(2 * 2752) < 2 * L.ms_per_move(2752)


def test_ident_never_carries_the_invasion_margin():
    """DESIGN §6.2 — BOTH of IDENT's sides are weight-0, so it pays no invasion
    arithmetic at all. `project_round_cost` must apply the candidate margin to the
    three ARMS only; IDENT's projection must be identical with and without it."""
    base = L.project_round_cost(cand_margin=0.0)
    marg = L.project_round_cost(cand_margin=L.CAND_MARGIN_TABLE)
    assert base["per_cell"]["IDENT"]["core_hours"] == \
        marg["per_cell"]["IDENT"]["core_hours"]
    for c in L.ARM_CELLS:
        assert marg["per_cell"][c.name]["core_hours"] > \
            base["per_cell"][c.name]["core_hours"]
    assert marg["core_hours"] > base["core_hours"]


def test_cost_scales_with_games_and_the_margin_touches_one_side_only():
    one = L.project_cost(400, cand_margin=0.0)["core_hours"]
    two = L.project_cost(800, cand_margin=0.0)["core_hours"]
    assert two == pytest.approx(2 * one)
    # a +100% candidate margin is +50% per game, because it is HALF the game
    plus = L.project_cost(400, cand_margin=1.0)["core_hours"]
    assert plus == pytest.approx(1.5 * one)


# ═══════════════════════════════════════════════════════════════════════════ #
# 13. THE ADJUDICATOR'S CONTRACT                                              #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_selftest_exits_zero():
    """READ_RULE §7 — and it must be seeded from a REAL emitted manifest."""
    r = subprocess.run([sys.executable, str(PREP / "analyze_screen.py"), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "REAL emitted archive" in r.stdout


def test_selftest_fixture_is_a_real_emitted_archive_not_a_synthesis():
    """A synthesized fixture would let a gate be 'validated' against a manifest the
    DESIGN described rather than one the harness WROTE — the exact defect the
    h2h_22016_prep post-mortem raised."""
    man = json.loads((PREP / "selftest_fixture" / "manifest.json").read_text())
    assert man.get("config") and man.get("code_rev") and man.get("carc_rs_build")
    assert man["config"]["backend"]["name"] == "rust"
    assert man["rules_profile"]["name"] == "fixed_v1"
    assert len(list((PREP / "selftest_fixture").glob("seed*_a*.json"))) >= 4


def test_adjudicator_never_writes_results_csv():
    """⛔ Close-out rows are a human act on the six-touch checklist."""
    src = (PREP / "analyze_screen.py").read_text()
    assert "results.csv" not in src.replace(
        "# ⛔ The adjudicator NEVER writes experiments/results.csv", "")


# ═══════════════════════════════════════════════════════════════════════════ #
# 14. THE PAIR ITSELF                                                         #
# ═══════════════════════════════════════════════════════════════════════════ #
def test_pair_files_all_exist():
    for f in ("DESIGN.md", "READ_RULE.md", "run_cells.sh", "analyze_screen.py",
              "screen_lib.py", "BAND_CLAIM.json", "BLIND_COMMIT", "WORKERS.conf",
              "leaf_ident.json", "leaf_a_mid.json", "leaf_b_mid.json", "leaf_d_mid.json"):
        assert (PREP / f).is_file(), f"missing {f}"


def test_band_claimed_sentinel_is_NOT_present_at_freeze():
    """⛔ THE INTERLOCK. `BAND_CLAIMED` is deliberately NOT created at freeze, and
    the launcher refuses every real cell without it. Claiming the registry row
    protects against a concurrent-session band race; it does not arm anything."""
    assert not (PREP / "BAND_CLAIMED").exists()


def test_band_claim_row_names_this_band_and_parses_as_eight_csv_fields():
    import csv
    import io
    claim = json.loads((PREP / "BAND_CLAIM.json").read_text())
    assert claim["band_seed_start"] == L.BAND
    row = next(csv.reader(io.StringIO(claim["_csv_row"])))
    assert len(row) == 8, f"row has {len(row)} fields"
    assert row[0] == str(L.BAND)


def test_design_and_read_rule_agree_with_the_frozen_weights():
    """`DESIGN.md` §3.2's frozen numbers must be the ones the library ships."""
    design = (PREP / "DESIGN.md").read_text()
    for c in L.ARM_CELLS:
        for k, v in c.invasion_values.items():
            assert str(v) in design, f"{k}={v} is not stated in DESIGN.md"
    assert str(L.FROZEN_DERIVATION["G_sibling_p90_minus_p10"]) in design
    assert str(L.BAND) in design


def test_read_rule_names_every_gate_it_claims_to():
    rr = (PREP / "READ_RULE.md").read_text()
    for gid in L.GATE_IDS:
        assert gid in rr, f"{gid} is implemented but not named in READ_RULE.md"


def test_blind_commit_is_pending_or_a_real_sha():
    v = (PREP / "BLIND_COMMIT").read_text().strip()
    assert v == "PENDING" or L.is_hex40(v), f"BLIND_COMMIT is {v!r}"


def test_rev_matching_is_a_prefix_rule_not_string_equality():
    """READ_RULE §3 G-REV, as corrected at freeze: `code_rev` is the SHORT sha and
    `PINNED_SRC_REV` is the 40-hex one, so literal equality could never hold."""
    full = "2eca4a92fb0012345678901234567890abcdef12"
    assert L.rev_matches("2eca4a92", full)[0]
    assert L.rev_matches("2ECA4A92", full)[0]
    assert not L.rev_matches("2eca4a92-dirty", full)[0]
    assert not L.rev_matches("deadbee", full)[0]
    assert not L.rev_matches("2eca", full)[0]      # shorter than MIN_REV_PREFIX
    assert not L.rev_matches(None, full)[0]
    assert not L.rev_matches("2eca4a92", None)[0]


# ═══════════════════════════════════════════════════════════════════════════ #
# 14. THE THREE THINGS A 4-GAME / EMPTY FIXTURE CANNOT PROVE                  #
#                                                                             #
# Everything above drives gates against the 4-game fixture or against an EMPTY #
# archive. Both are necessary; neither is sufficient for these three:          #
#                                                                             #
#  (a) AN EMPTY ARCHIVE PROVES "ABSENT is FAIL" ONLY WEAKLY. It cannot tell a  #
#      gate that fails because its witness is absent from a gate that fails    #
#      ALWAYS. The sharp form needs a HEALTHY control that passes every gate,  #
#      then one address removed at a time — READ_RULE §3.1 questions 2 and 4   #
#      taken TOGETHER rather than one at a time.                               #
#  (b) `round_branch()` proves the round-level ARITHMETIC. It does not prove   #
#      the ADJUDICATOR wires a failed `G-IDENT` into ALL FOUR cells, which is  #
#      the actual §3.4 obligation and the actual `track_d2_prep` defect.       #
#  (c) A `<cell>/failed/` subdirectory only exists on a real archive, and the  #
#      NON-RECURSIVE read is what stops its records being counted as           #
#      completions.                                                            #
#                                                                             #
# The archives below are re-badges of `selftest_fixture/manifest.json` — a     #
# REAL emitted manifest — onto each cell's frozen band, with per-deck margins  #
# constructed to hit an EXACT z. Nothing here plays a game or spends a deck.   #
# ═══════════════════════════════════════════════════════════════════════════ #
import copy      # noqa: E402
import random    # noqa: E402

_FIXTURE_DIR = PREP / "selftest_fixture"


def _exact_z_margins(n: int, z_target: float, seed: int = 20260826) -> list[float]:
    """`n` per-deck margins whose deck-paired z is EXACTLY `z_target`.

    `se` is shift-invariant, so a pure shift moves the mean without touching the
    dispersion: `m_i = x_i - mean(x) + z_target * se(x)`. That is what lets the
    IDENT-bar test below be exact rather than hostage to a random draw landing
    near `|z| = 2`.
    """
    rng = random.Random(seed)
    xs = [rng.gauss(0.0, 13.0) for _ in range(n)]
    mx = sum(xs) / n
    var = sum((x - mx) ** 2 for x in xs) / (n - 1)
    se = math.sqrt(var / n)
    return [x - mx + z_target * se for x in xs]


def _build_full_cell(root: Path, spec, *, z_target: float = 0.0,
                     blind: str = "b" * 40, pinned: str = "b" * 40) -> Path:
    """A structurally HEALTHY full-size archive for `spec`, re-badged from the
    real emitted manifest onto that cell's own frozen deck range."""
    man = json.loads((_FIXTURE_DIR / "manifest.json").read_text())
    cfg = man["config"]
    champ_leaf = copy.deepcopy(cfg["cand_leaf_cfg"])       # curve125, no invasion keys

    cfg["band_seed_start"] = spec.seed_start
    cfg["seed_start"] = spec.seed_start
    cfg["n_decks"] = spec.n_decks
    cfg["n"] = spec.n_games
    cfg["seatings_per_deck"] = 2
    # ⚠️ `_leaf_dict` DROPS a field at its default, so the cell's knob is the ONLY
    # invasion key on the candidate side — which is exactly what makes IDENT's
    # leaf diff EMPTY and an arm's diff its own frozen key set.
    cfg["cand_leaf_cfg"] = dict(champ_leaf, **dict(spec.invasion_values))
    cfg["cand_leaf_hash"] = spec.cand_leaf_hash
    cfg["opp_leaf_cfg"] = copy.deepcopy(champ_leaf)
    cfg["opp_leaf_hash"] = L.PROD_LEAF_HASH
    # `config.champion.leaf_cfg` is the FULL asdict (nothing dropped) — where
    # G-INVASION and G-CAPFWD read the six invasion fields from.
    cfg["champion"]["leaf_cfg"].update(L.INVASION_DEFAULTS)
    cfg["champion"]["leaf_cfg"].update(spec.invasion_values)
    cfg["stamps"] = {"BLIND_COMMIT": blind}
    cfg["code_rev"] = pinned[:8]
    man["code_rev"] = pinned[:8]

    d = root / spec.out_subdir
    d.mkdir(parents=True, exist_ok=True)
    recs = []
    for i, m in enumerate(_exact_z_margins(spec.n_decks, z_target)):
        s = spec.seed_start + i
        for a in (0, 1):
            # `diff` is candidate-minus-opponent in POINTS; putting the whole
            # per-deck margin on a_seat=0 makes D(d) = (2m + 0)/2 = m.
            recs.append({"seed": s, "a_seat": a,
                         "diff": (2.0 * m) if a == 0 else 0.0,
                         "won_by_champ": ((i + a) % 2 == 0), "drew": False,
                         "deck_hash": f"{s:016x}"})
    for r in recs:
        (d / f"seed{r['seed']:012d}_a{r['a_seat']}.json").write_text(json.dumps(r))

    mean, z, n_paired, _se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    (d / "summary.json").write_text(json.dumps({
        "n": spec.n_games, "n_failed": 0, "failure_rate": 0.0,
        "winrate": we["winrate"], "elo": we["elo"],
        "elo_sig_1sigma": we["elo_sig_1sigma"],
        "paired_mean_margin": mean, "paired_z": z, "n_paired": n_paired,
        "avg_diff": we["avg_diff"],
        "champ_prefix_ms_per_move": 500.0, "rung_ms_per_move": 490.0,
    }, indent=1))
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    return d


def _healthy_probe() -> dict:
    p = {k: True for k in L.WHEEL_PROBE_REQUIRED_TRUE}
    p["carc_rs_build"] = "carc_rs-0.1.0+deadbeefcafe+rustcunpinned"
    return p


def _healthy_wheel_ancestry(rev: str = "deadbeefcafe") -> dict:
    """A PASSING `wheel_ancestry_facts` verdict. The real one shells out to git;
    the gate consumes only the verdict, which is what lets these tests drive both
    limbs without a repository."""
    return {"ok": True, "rev": rev, "invasion_source_present": True,
            "is_ancestor": True, "why": ""}


def _healthy_blind_proof(blind: str = "b" * 40) -> dict:
    return {"ok": True, "blind_commit": blind, "is_ancestor_of_head": True,
            "introduced_frozen_banner": True, "proof_ok": True, "why": ""}


def _healthy_src_clean(cells=None) -> dict:
    names = ["pre-flight"] + [f"{c.name}-after-seal" for c in (cells or L.CELLS)]
    return {"ok": True, "boundaries": names, "dirty_boundaries": [],
            "has_preflight": True, "missing_after": [], "why": ""}


def _gates_on_disk(cell_dir: Path, spec, *, blind="b" * 40, pinned="b" * 40, **over):
    kw = dict(pinned_src_rev=pinned, blind_commit=blind,
              wheel_probe=_healthy_probe(),
              wheel_ancestry=_healthy_wheel_ancestry(),
              blind_proof=_healthy_blind_proof(blind),
              src_clean=_healthy_src_clean())
    kw.update(over)
    return A.run_gates(A.Cell(spec, cell_dir), **kw)


@pytest.fixture(scope="module")
def healthy_ident_archive(tmp_path_factory) -> Path:
    return _build_full_cell(tmp_path_factory.mktemp("invasion_healthy"),
                            L.IDENT_CELL, z_target=0.0)


def test_a_healthy_full_size_archive_passes_every_gate(healthy_ident_archive):
    """⭐ THE SATISFIABILITY CONTROL (READ_RULE §3.1 question 2): *"Can a healthy
    run pass it?"* If a full-size re-badge of a REAL emitted manifest could not
    clear every per-cell gate, the §9 smoke leg would be a PERMANENT launch
    blocker and the ABSENT tests below would be proving nothing."""
    gates, _ = _gates_on_disk(healthy_ident_archive, L.IDENT_CELL)
    failed = gates.failed()
    assert failed == [], json.dumps({g: gates.results[g] for g in failed},
                                    default=str, indent=1)


#: Each gate's OWN witness address(es) in the emitted manifest/summary. Verified
#: against the real fixture, not written from the design.
_ABSENT_PROBES = {
    "G-BAND": ["config.band_seed_start", "config.seed_start"],
    "G-SINGLEVAR": ["config.opponent.champ_cfg.c_puct"],
    "G-LEAF": ["config.opp_leaf_hash", "config.opponent.leaf_hash"],
    "G-INVASION": ["config.champion.leaf_cfg"],
    "G-CAPFWD": ["config.champion.leaf_cfg"],
    "G-WHEEL": ["carc_rs_build", "config.backend.carc_rs_build"],
    "G-RULES": ["rules_profile.r9_env_ok", "config.rules_profile.r9_env_ok"],
    "G-BACKEND": ["config.backend.name"],
    "G-BUDGET": ["config.champion.k_dets"],
    "G-EXACT": ["config.endgame.exact_k"],
    "G-REV": ["config.code_rev", "code_rev"],
    "G-BLIND": ["BLIND_COMMIT", "config.stamps.BLIND_COMMIT"],
    "G-N": ["n"],
    "G-SAT": ["winrate"],
    "RECON": ["paired_mean_margin"],
}


def _drop_address(doc, dotted: str) -> None:
    cur = doc
    for part in dotted.split(".")[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    if isinstance(cur, dict):
        cur.pop(dotted.split(".")[-1], None)


@pytest.mark.parametrize("gid", sorted(_ABSENT_PROBES))
def test_absent_is_fail_against_an_otherwise_healthy_archive(tmp_path, gid):
    """READ_RULE §3.1 question 4, driven the SHARP way: start from an archive
    that passes EVERY gate, remove ONE gate's own witness, and require exactly
    that gate to fail. The empty-archive form above cannot make this distinction
    — a gate that failed unconditionally would satisfy it just as well."""
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.0)
    man = json.loads((d / "manifest.json").read_text())
    summ = json.loads((d / "summary.json").read_text())
    for addr in _ABSENT_PROBES[gid]:
        _drop_address(man, addr)
        _drop_address(man.get("config", {}), addr)
        _drop_address(summ, addr)
    (d / "manifest.json").write_text(json.dumps(man))
    (d / "summary.json").write_text(json.dumps(summ))
    gates, _ = _gates_on_disk(d, L.IDENT_CELL)
    assert gates.results[gid]["ok"] is False, (
        f"{gid} survived the removal of {_ABSENT_PROBES[gid]} — ABSENT became a "
        "skip or a permissive default")


def test_a_failed_g_ident_voids_all_four_cells_end_to_end(tmp_path, monkeypatch):
    """⭐ READ_RULE §3.4, THROUGH THE ADJUDICATOR rather than through the branch
    arithmetic alone.

    A defect that moves a ZERO-weight leaf moves every nonzero one too, so no
    A/B/D reading could be attributed to the term rather than to the wiring.
    Reading A/B/D past a broken `IDENT` would be the `track_d2_prep` mistake with
    a self-inflicted excuse. Four structurally healthy archives are built; the
    ONLY thing that changes between the two adjudications is IDENT's realized z.
    """
    blind = pinned = "c" * 40
    probe = _healthy_probe()
    monkeypatch.setattr(A, "_read_text",
                        lambda p: pinned if p.name == "PINNED_SRC_REV" else blind)
    monkeypatch.setattr(A, "_read_json",
                        lambda p: probe if p.name == L.WHEEL_PROBE_FILENAME
                        else (json.loads(p.read_text()) if p.exists() else None))
    # The three conjuncts that reach OUTSIDE the archive (git ancestry, the blind
    # proof, SRC_CLEAN.jsonl) are stubbed HEALTHY here so that the ONLY thing
    # differing between the two adjudications below is IDENT's realized z. Their
    # own fail-closed behaviour is tested directly further down.
    monkeypatch.setattr(A, "wheel_ancestry_facts",
                        lambda *a, **k: _healthy_wheel_ancestry())
    monkeypatch.setattr(A, "blind_facts", lambda *a, **k: _healthy_blind_proof(blind))
    monkeypatch.setattr(A, "src_clean_facts", lambda *a, **k: _healthy_src_clean())

    for spec in L.CELLS:
        _build_full_cell(tmp_path, spec, z_target=0.0, blind=blind, pinned=pinned)
    clean = A.adjudicate(tmp_path)
    assert clean["ident_gate"]["ok"] is True, (
        "the control arm must be clean, else the assertion below proves nothing: "
        + json.dumps({n: c["gates"] for n, c in clean["cells"].items()},
                     default=str)[:2000])
    assert clean["round_branch"] == "SCREEN-NULL-family-parks"
    assert all(c["branch"] != "U-UNREADABLE" for c in clean["cells"].values())

    # …now break ONLY IDENT's z. Every other cell's archive is untouched.
    _build_full_cell(tmp_path, L.IDENT_CELL, z_target=3.5, blind=blind, pinned=pinned)
    broken = A.adjudicate(tmp_path)
    assert broken["ident_gate"]["ok"] is False
    assert broken["round_branch"] == "U-UNREADABLE"
    for name, cell in broken["cells"].items():
        assert cell["gates"]["G-IDENT"]["ok"] is False, name
        assert cell["branch"] == "U-UNREADABLE", (
            f"{name} was read past a broken IDENT (READ_RULE §3.4)")


def test_a_failed_subdirectory_record_is_never_counted_as_a_completion(tmp_path):
    """⚠️ The harness writes FAILURE records into `<cell>/failed/` using the SAME
    `seed*_a*.json` filename pattern. A recursive glob would count them as
    completions — inflating `n_common`, MOVING THE MARGIN, and turning a broken
    cell into a healthy-looking one. The read must be NON-RECURSIVE."""
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.0)
    before = A.Cell(L.IDENT_CELL, d)
    (d / "failed").mkdir()
    poison = L.IDENT_CELL.seed_end + 1
    for a in (0, 1):
        (d / "failed" / f"seed{poison:012d}_a{a}.json").write_text(json.dumps(
            {"seed": poison, "a_seat": a, "diff": 999.0,
             "won_by_champ": True, "drew": False}))
    after = A.Cell(L.IDENT_CELL, d)
    assert len(after.records) == len(before.records) == L.IDENT_CELL.n_games
    assert poison not in L.per_deck_margins(after.records)
    gates, _ = _gates_on_disk(d, L.IDENT_CELL)
    assert gates.failed() == [], gates.failed()


def test_recon_voids_but_never_moves_the_number(tmp_path):
    """READ_RULE §3 `RECON`: *"The recomputation is a WITNESS, never a branch
    input — it can only void, never move, the number."* The summary's `paired_z`
    is nudged past the tolerance while the raw records are untouched: the gate
    must void, AND the reported statistic must still be the summary's."""
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.5)
    summ = json.loads((d / "summary.json").read_text())
    summ["paired_z"] += 0.01
    (d / "summary.json").write_text(json.dumps(summ))
    gates, stats = _gates_on_disk(d, L.IDENT_CELL)
    assert gates.results["RECON"]["ok"] is False
    assert stats["z"] == pytest.approx(summ["paired_z"]), "RECON MOVED the number"


def test_recon_absorbs_a_summation_order_difference_and_nothing_larger(tmp_path):
    """`screen_lib.paired_margin` accumulates with `math.fsum` and the harness
    with `sum`, so they differ in the last bits BY CONSTRUCTION. The rel-1e-6
    tolerance exists to absorb exactly that, and nothing larger."""
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.5)
    summ = json.loads((d / "summary.json").read_text())
    summ["paired_mean_margin"] *= (1 + 1e-9)
    (d / "summary.json").write_text(json.dumps(summ))
    gates, _ = _gates_on_disk(d, L.IDENT_CELL)
    assert gates.results["RECON"]["ok"] is True


def test_the_witness_reproduces_the_real_archives_own_summary():
    """⭐ TRANSCRIPTION FIDELITY, ON REAL DATA. `screen_lib`'s witness is a
    deliberately INDEPENDENT re-implementation, so the only thing that makes it a
    WITNESS rather than a second opinion is that it reproduces the harness's own
    numbers off a real archive. All five `RECON` statistics, at `RECON`'s own
    tolerance. If this fails, `RECON` is comparing two different statistics."""
    recs = [json.loads(p.read_text())
            for p in sorted(_FIXTURE_DIR.glob("seed*_a*.json"))]
    summary = json.loads((_FIXTURE_DIR / "summary.json").read_text())
    mean, z, n, _se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    for stat, got in (("paired_mean_margin", mean), ("paired_z", z),
                      ("n_paired", n), ("winrate", we["winrate"]),
                      ("elo", we["elo"])):
        assert L.recon_close(summary[stat], got), (
            f"{stat}: harness {summary[stat]!r} vs witness {got!r}")


def test_smoke_allowed_set_is_PARSED_from_read_rule_not_retyped():
    """⛔ THE SELF-INVALIDATING-TEST GUARD. Asserting the set against a literal
    copy of itself passes just as happily after someone edits both. This PARSES
    §3.5's fenced block out of `READ_RULE.md`, so the pair's prose is the
    authority and a silent WIDENING of the allowed set is caught.

    ⚠️ `RECON/n_paired` is a SUB-CHECK id, not a gate id: the deck-count half of
    the reconciliation may be excused on a 16-game throwaway; the margin / z /
    winrate / elo halves may not."""
    md = (PREP / "READ_RULE.md").read_text()
    block = md.split("### §3.5")[1].split("---")[0].split("```")[1]
    named = set(block.split())
    assert named == set(L.SMOKE_ALLOWED_FAILURES), (
        f"READ_RULE §3.5 names {sorted(named)}; screen_lib pins "
        f"{sorted(L.SMOKE_ALLOWED_FAILURES)}")
    assert "RECON/n_paired" in named and "RECON" not in named


def test_workers_conf_leaf_hashes_and_budget_agree_with_the_library():
    """`WORKERS.conf` carries the four pinned candidate hashes and the budget for
    the launcher's own preflight. They are a SECOND copy, so they must be proven
    equal to the library's — drift here would arm the wrong `--cand-leaf-json`
    against the right hash assertion."""
    conf = _workers_conf()
    assert conf["PROD_LEAF_HASH"] == L.PROD_LEAF_HASH
    for c in L.CELLS:
        assert conf[f"CAND_LEAF_HASH_{c.name}"] == c.cand_leaf_hash, c.name
    assert (int(conf["K_DETS"]), int(conf["SIMS_PER_DET"]), int(conf["TOTAL_SIMS"])) \
        == (4, 688, 2752)
    assert int(conf["K_DETS"]) * int(conf["SIMS_PER_DET"]) == int(conf["TOTAL_SIMS"])
    assert int(conf["SMOKE_SEED_START"]) == L.SMOKE_SEED_START
    assert int(conf["SMOKE_GAMES"]) == L.SMOKE_GAMES
    assert conf["SMOKE_CELL"] == L.SMOKE_CELL


def test_the_se_model_is_sigma_over_root_n_not_a_typed_table():
    """READ_RULE §2.1 publishes SE = 1.0374 at 200 decks and 0.7335 at 400. Those
    figures are `14.67/√n` ROUNDED to 4 dp, so the sharp test is the RELATIONSHIP
    the rounding cannot hide: doubling n tightens SE by exactly √2. ⛔ POWER
    ARITHMETIC ONLY — every §4 bar is evaluated at the cell's OWN realized SE."""
    assert L.se_model(200) == pytest.approx(1.0374, abs=1e-4)
    assert L.se_model(400) == pytest.approx(0.7335, abs=1e-4)
    assert L.se_model(200) == pytest.approx(L.SIGMA_D_MODEL / math.sqrt(200), abs=1e-12)
    assert L.se_model(200) / L.se_model(400) == pytest.approx(math.sqrt(2), abs=1e-12)


@pytest.mark.parametrize("ratio,flagged", [(0.70, False), (1.43, False),
                                           (0.6999, True), (1.4301, True)])
def test_the_dispersion_anomaly_band_is_closed_at_its_endpoints(ratio, flagged):
    """READ_RULE §1's `[0.70, 1.43]` flag is a CLOSED interval, and it is
    REPORTED, never a branch input — so a flagged cell's branch is unmoved."""
    out = L.se_anomaly(L.se_model(400) * ratio, 400)
    assert out["flagged"] is flagged
    assert out["ratio"] == pytest.approx(ratio)
    assert L.branch_for_cell(2.5, True) == "PROMOTE"
    assert L.se_anomaly(None, 400)["flagged"] is True, "an ABSENT SE is flagged too"


@pytest.mark.parametrize("drop", sorted(L.WHEEL_PROBE_REQUIRED_TRUE) + ["carc_rs_build"])
def test_the_wheel_probe_contract_fails_closed_on_every_field(drop):
    """⭐ A STALE WHEEL IS THE WORST FAILURE MODE THIS PAIR HAS (DESIGN §7):
    `leaf_config_rs` forwards the invasion kwargs CONDITIONALLY, so a build
    predating the family serves every champion config unchanged and SILENTLY — a
    stale-wheel IDENT would PASS, and a partial mismatch would read as "the term
    is worth nothing" rather than "the term never ran". Every probe field is
    load-bearing, so dropping any one must fail closed."""
    probe = _healthy_probe()
    assert L.wheel_probe_ok(probe)[0] is True
    probe.pop(drop)
    assert L.wheel_probe_ok(probe)[0] is False
    assert L.wheel_probe_ok(None)[0] is False
    assert L.wheel_probe_ok({})[0] is False


def test_b_mid_is_the_only_cell_that_may_carry_a_cap():
    """B is the only cell with `invasion_alpha != 0.0`, so it is the only cell
    whose cap is actually FORWARDED by `leaf_config_rs` — which is why DESIGN §3
    sets one there and nowhere else, and why the §9 smoke runs B's config."""
    caps = {c.name: c.invasion_values.get("invasion_alpha_cap") for c in L.CELLS}
    assert caps == {"IDENT": None, "A_MID": None, "B_MID": 11.0, "D_MID": None}
    assert L.SMOKE_CELL == "B_MID"


# ═══════════════════════════════════════════════════════════════════════════ #
# 15. THE THREE CONJUNCTS ADDED BY THE 2026-08-26 PRE-GAME-1 AMENDMENT        #
#                                                                             #
# Each was STATED in READ_RULE §3 from the start and NOT ENFORCED by the first #
# implementation. Two of them read artifacts `run_cells.sh` had always WRITTEN #
# and nothing had ever READ BACK. Tests below drive both limbs of each.        #
# ═══════════════════════════════════════════════════════════════════════════ #

# ---- G-WHEEL: the ancestry conjunct ---------------------------------------
def test_wheel_ancestry_is_required_for_g_wheel(tmp_path):
    """⭐ THE ONLY CONJUNCT THAT CATCHES A STALE WHEEL POST-HOC, FROM THE ARCHIVE
    ALONE. `WHEEL_PROBE.json` proves a nonzero forward worked at LAUNCH; this
    proves the build that actually PLAYED the games could contain the family."""
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.0)
    ok, _ = _gates_on_disk(d, L.IDENT_CELL)
    assert ok.results["G-WHEEL"]["ok"] is True
    for bad in ({"ok": False, "why": "rev predates the family"}, None):
        g, _ = _gates_on_disk(d, L.IDENT_CELL, wheel_ancestry=bad)
        assert g.results["G-WHEEL"]["ok"] is False, bad


@pytest.mark.parametrize("build,rev", [
    ("carc_rs-0.1.0+2eca4a92fb00+rustcunpinned", "2eca4a92fb00"),
    ("carc_rs-1.59963.20305+abcdef1234567890+rustc1.79", "abcdef1234567890"),
])
def test_wheel_ancestry_extracts_the_embedded_rev(build, rev, tmp_path):
    """`carc_rs_build_id()` emits `carc_rs-<version>+<rev>+rustc<tc>`. The rev is
    the ONLY build fingerprint the manifest carries — `carc_rs_version` is
    permanently '0.1.0'."""
    out = A.wheel_ancestry_facts(tmp_path, build)
    assert out["rev"] == rev


@pytest.mark.parametrize("build", [None, "", "not-a-build-id", "carc_rs-0.1.0"])
def test_wheel_ancestry_fails_closed_without_an_embedded_rev(build, tmp_path):
    out = A.wheel_ancestry_facts(tmp_path, build)
    assert out["ok"] is False and out["rev"] is None


def test_wheel_ancestry_against_the_real_repo():
    """Executed against THIS repository: the merge that landed the invasion build
    carries `invasion.rs` and is an ancestor of HEAD; the commit BEFORE the family
    existed does not carry the file and must fail the conjunct."""
    repo = REPO
    good = A.wheel_ancestry_facts(repo, "carc_rs-0.1.0+2eca4a92fb00+rustcunpinned")
    assert good["invasion_source_present"] is True, good
    assert good["is_ancestor"] is True, good
    assert good["ok"] is True
    # a rev that predates the family: the merge's FIRST parent's parent side.
    pre = subprocess.run(["git", "-C", str(repo), "rev-parse", "2eca4a92^1"],
                         capture_output=True, text=True).stdout.strip()
    if pre:
        bad = A.wheel_ancestry_facts(repo, f"carc_rs-0.1.0+{pre[:12]}+rustcunpinned")
        assert bad["invasion_source_present"] is False, (
            "the pre-family rev unexpectedly carries invasion.rs")
        assert bad["ok"] is False


# ---- G-BLIND: ancestry / banner / proof ------------------------------------
def test_blind_conjuncts_are_required_for_g_blind(tmp_path):
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.0)
    ok, _ = _gates_on_disk(d, L.IDENT_CELL)
    assert ok.results["G-BLIND"]["ok"] is True
    for bad in ({"ok": False, "why": "not an ancestor"}, None):
        g, _ = _gates_on_disk(d, L.IDENT_CELL, blind_proof=bad)
        assert g.results["G-BLIND"]["ok"] is False, bad


def test_blind_facts_rejects_a_pending_or_short_sha(tmp_path):
    for blind in (None, "", "PENDING", "abc123"):
        assert A.blind_facts(tmp_path, blind, None, tmp_path / "d.md",
                             tmp_path / "r.md")["ok"] is False


def test_blind_facts_requires_the_proof_to_agree_with_a_live_recheck():
    """⚠️ `run_cells.sh` has always WRITTEN BLIND_PROOF.json; until the amendment
    nothing read it back, so a stale or disagreeing proof could sit unnoticed."""
    repo = REPO
    blind = (PREP / "BLIND_COMMIT").read_text().strip()
    if not L.is_hex40(blind):
        pytest.skip("BLIND_COMMIT is still PENDING in this tree")
    good = A.blind_facts(repo, blind, {"blind_commit": blind,
                                       "is_ancestor_of_head": True},
                         PREP / "DESIGN.md", PREP / "READ_RULE.md")
    assert good["is_ancestor_of_head"] is True
    assert good["introduced_frozen_banner"] is True, (
        "the blind commit must be the one that INTRODUCED the FROZEN banner")
    assert good["ok"] is True
    # absent proof
    assert A.blind_facts(repo, blind, None, PREP / "DESIGN.md",
                         PREP / "READ_RULE.md")["ok"] is False
    # proof naming a DIFFERENT commit
    assert A.blind_facts(repo, blind, {"blind_commit": "d" * 40,
                                       "is_ancestor_of_head": True},
                         PREP / "DESIGN.md", PREP / "READ_RULE.md")["ok"] is False
    # proof DISAGREEING with the live re-check
    assert A.blind_facts(repo, blind, {"blind_commit": blind,
                                       "is_ancestor_of_head": False},
                         PREP / "DESIGN.md", PREP / "READ_RULE.md")["ok"] is False


# ---- G-REV: the SRC_CLEAN conjunct ----------------------------------------
def test_src_clean_is_required_for_g_rev(tmp_path):
    d = _build_full_cell(tmp_path, L.IDENT_CELL, z_target=0.0)
    ok, _ = _gates_on_disk(d, L.IDENT_CELL)
    assert ok.results["G-REV"]["ok"] is True
    for bad in ({"ok": False, "why": "dirty at pre-flight"}, None):
        g, _ = _gates_on_disk(d, L.IDENT_CELL, src_clean=bad)
        assert g.results["G-REV"]["ok"] is False, bad


def _write_src_clean(p: Path, rows) -> Path:
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_src_clean_facts_requires_clean_at_every_boundary(tmp_path):
    names = ["pre-flight"] + [f"{c.name}-after-seal" for c in L.CELLS]
    cells = [c.name for c in L.CELLS]
    good = _write_src_clean(tmp_path / "a.jsonl",
                            [{"boundary": n, "src_clean": True} for n in names])
    assert A.src_clean_facts(good, cells)["ok"] is True
    # ONE dirty boundary voids it — a mid-round tree move is the track_d2_prep defect
    rows = [{"boundary": n, "src_clean": (n != names[2])} for n in names]
    dirty = _write_src_clean(tmp_path / "b.jsonl", rows)
    out = A.src_clean_facts(dirty, cells)
    assert out["ok"] is False and out["dirty_boundaries"] == [names[2]]


def test_src_clean_facts_requires_a_preflight_and_a_per_cell_after_boundary(tmp_path):
    cells = [c.name for c in L.CELLS]
    # no pre-flight
    p = _write_src_clean(tmp_path / "c.jsonl",
                         [{"boundary": f"{c}-after-seal", "src_clean": True}
                          for c in cells])
    assert A.src_clean_facts(p, cells)["ok"] is False
    # a cell with no after-boundary
    rows = [{"boundary": "pre-flight", "src_clean": True}] + [
        {"boundary": f"{c}-after-seal", "src_clean": True} for c in cells[:-1]]
    p2 = _write_src_clean(tmp_path / "d.jsonl", rows)
    out = A.src_clean_facts(p2, cells)
    assert out["ok"] is False and out["missing_after"] == [cells[-1]]


def test_src_clean_facts_absent_or_empty_is_fail(tmp_path):
    assert A.src_clean_facts(tmp_path / "nope.jsonl", ["IDENT"])["ok"] is False
    empty = tmp_path / "e.jsonl"
    empty.write_text("")
    assert A.src_clean_facts(empty, ["IDENT"])["ok"] is False
    bad = tmp_path / "f.jsonl"
    bad.write_text("{not json}\n")
    assert A.src_clean_facts(bad, ["IDENT"])["ok"] is False


def test_src_clean_smoke_mode_relaxes_only_the_per_cell_requirement(tmp_path):
    """A smoke has ONE cell and no seal, so it cannot carry a per-cell
    after-boundary for all four. ⛔ The CLEAN requirement does NOT relax."""
    rows = [{"boundary": "pre-flight", "src_clean": True},
            {"boundary": "smoke-after", "src_clean": True}]
    p = _write_src_clean(tmp_path / "g.jsonl", rows)
    assert A.src_clean_facts(p, [c.name for c in L.CELLS])["ok"] is False
    assert A.src_clean_facts(p, ["B_MID"], smoke=True)["ok"] is True
    rows[1]["src_clean"] = False
    p2 = _write_src_clean(tmp_path / "h.jsonl", rows)
    assert A.src_clean_facts(p2, ["B_MID"], smoke=True)["ok"] is False


# ---- the smoke-blocker fix -------------------------------------------------
def test_the_smoke_leg_writes_its_own_launch_artifacts():
    """⭐ THE SMOKE-BLOCKER FIX. Running the smoke from the main tree exited 11:
    G-REV read 'PINNED_SRC_REV ABSENT — ABSENT is FAIL' on EVERY smoke, because
    only a real launch wrote that file. The fix SUPPLIES THE WITNESS; it must not
    widen §3.5's allowed set."""
    src = (PREP / "run_cells.sh").read_text()
    smoke = src.split("run_smoke() {")[1].split("\n}\n")[0]
    assert 'rev-parse HEAD > "$DIR/$PINNED_SRC_REV_FILE"' in smoke, \
        "the smoke leg does not write PINNED_SRC_REV"
    assert "write_blind_proof" in smoke, "the smoke leg does not write BLIND_PROOF.json"
    assert 'record_src_boundary "pre-flight"' in smoke
    assert "record_src_boundary" in smoke.split('record_src_boundary "pre-flight"')[1], \
        "the smoke leg records no CLOSING SRC_CLEAN boundary"


def test_the_amendment_did_not_widen_the_smoke_allowed_set():
    """⛔ ABSENT-IS-FAIL STAYS SACRED. The smoke-blocker was fixed by supplying
    the witness, never by excusing its absence — so G-REV and G-BLIND must STILL
    be outside the allowed set after the amendment."""
    assert "G-REV" not in L.SMOKE_ALLOWED_FAILURES
    assert "G-BLIND" not in L.SMOKE_ALLOWED_FAILURES
    assert "G-WHEEL" not in L.SMOKE_ALLOWED_FAILURES
    assert L.SMOKE_ALLOWED_FAILURES == frozenset(
        {"G-BAND", "G-DECKS", "G-N", "G-SAT", "G-IDENT", "RECON/n_paired"})


def test_read_rule_records_the_pre_game_1_amendment():
    """The house pre-game-1 pattern: an amendment made at zero games is an
    AMENDMENT TO THE PAIR and must be recorded in the pair, dated, with its
    reason — not applied silently."""
    rr = (PREP / "READ_RULE.md").read_text()
    assert "PRE-GAME-1 AMENDMENT" in rr
    assert "2026-08-26" in rr
    for token in ("PINNED_SRC_REV", "BLIND_PROOF.json", "SRC_CLEAN.jsonl",
                  "ANCESTRY", "ABSENT-is-FAIL stays sacred"):
        assert token in rr, f"the amendment note does not mention {token}"
    design = (PREP / "DESIGN.md").read_text()
    assert "PRE-GAME-1 AMENDMENT" in design


def test_g_leaf_stricter_form_is_declared_canonical():
    """Item 4: the implementation pins each cell's EXACT hash, which is stricter
    than the pair's original 'champion vs not-champion' asymmetry. The stricter
    form is now the canonical text."""
    rr = (PREP / "READ_RULE.md").read_text()
    assert "STRICTER FORM IS CANONICAL" in rr
    for c in L.CELLS:
        assert c.cand_leaf_hash in rr, f"{c.name}'s pinned hash is not in READ_RULE"


def test_design_margin_wording_matches_the_published_table():
    """Item 4: §6.2's prose said '0% to +50% on the candidate half, i.e. 0% to
    +25% per game', a WIDER envelope than the table it introduced. The table is
    canonical: cand_margin=0.25 on the candidate HALF is +12.5% per game."""
    design = (PREP / "DESIGN.md").read_text()
    assert "THE PUBLISHED TABLE IS CANONICAL" in design
    assert "+12.5% per game" in design
    base = L.project_round_cost(cand_margin=0.0)
    marg = L.project_round_cost(cand_margin=L.CAND_MARGIN_TABLE)
    arm = L.cell_by_name("A_MID").name
    ratio = marg["per_cell"][arm]["s_per_game"] / base["per_cell"][arm]["s_per_game"]
    assert ratio == pytest.approx(1.125), "the table is not +12.5% per game"
