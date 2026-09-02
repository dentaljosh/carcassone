#!/usr/bin/env python3
"""Selftests for the GT-M1 risk-asymmetric world-pooling instrument.

Three families:

  1. **PAIR CONSISTENCY** — `WORKERS.conf` and `cvar_lib.py` state the same
     constants, because the launcher reads one and the adjudicator reads the
     other and a silent disagreement between them is a launcher defect that no
     review catches.
  2. **GATE BEHAVIOUR ON REAL-EMITTER FIXTURES** — every gate PASSES the real
     document and FAILS each single-key mutation of it. ⛔ Fixtures are
     mutations of a genuinely emitted manifest+summary (`selftest_fixture/
     make_fixture.py` explains why that is not a stylistic preference).
  3. **PLUMBING** — the flags exist in the REAL argparse, `cand_search` carries
     the round's keys, and the harness refuses the malformed combinations.

Run:  pytest measurement/cvar_pool_prep/test_cvar_pool.py -q
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FIX = HERE / "selftest_fixture"
sys.path.insert(0, str(HERE))
import adjudicate_cvar_smoke as A  # noqa: E402
import cvar_lib as L  # noqa: E402


def _conf() -> dict:
    """Parse `WORKERS.conf` as `KEY=value` lines.

    ⚠️ Deliberately STRICT about trailing comments: a `KEY=value  # note` line
    has bitten this program three times (the third was 2026-09-01, commit
    981ca55a, on the τ_p leg's band constants). If one appears here the parse
    keeps the comment IN the value and the equality assertions below fail
    loudly, which is the intended behaviour."""
    out = {}
    for line in (HERE / "WORKERS.conf").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


# =========================================================================== #
# 1. PAIR CONSISTENCY                                                          #
# =========================================================================== #

def test_workers_conf_agrees_with_cvar_lib():
    c = _conf()
    assert int(c["BAND_CVAR25"]) == L.BAND_CVAR25
    assert int(c["BAND_CVAR50"]) == L.BAND_CVAR50
    assert int(c["THROWAWAY_BASE"]) == L.THROWAWAY_BASE
    assert int(c["N_DECKS"]) == L.N_DECKS
    assert int(c["N_GAMES"]) == L.N_GAMES
    assert float(c["ALPHA_LOW"]) == L.DOSES["CELL_CVAR25"]
    assert float(c["ALPHA_HIGH"]) == L.DOSES["CELL_CVAR50"]
    assert int(c["K_DETS"]) == L.K_DETS
    assert int(c["SIMS_PER_DET"]) == L.SIMS_PER_DET
    assert int(c["TOTAL_SIMS"]) == L.TOTAL_SIMS
    assert int(c["EXACT_K"]) == L.EXACT_K
    assert c["EXACT_MODE"] == L.EXACT_MODE
    assert c["BACKEND"] == L.BACKEND
    assert c["RULES_PROFILE"] == L.RULES_PROFILE
    assert int(c["W_LAPTOP"]) == L.W_LAPTOP
    assert float(c["G_PER_H_LAPTOP"]) == L.G_PER_H_LAPTOP
    assert int(c["TIEARB_B"]) == L.TIEARB["B"]
    assert int(c["TIEARB_J"]) == L.TIEARB["J"]
    assert c["TIEARB_MODE"] == L.TIEARB["mode"]
    assert c["TIEARB_SALT"] == L.TIEARB["salt"]
    assert float(c["TIEARB_EPS"]) == L.TIEARB["eps"]
    assert c["TIEARB_PHASE_GATE"] == L.TIEARB["phase_gate"]
    assert c["POOL_MODE"] == "cvar"


def test_no_trailing_comments_on_assignment_lines():
    """⛔ THE CONF-PARSER TRAP, THIRD INSTANCE (commit 981ca55a). A trailing
    `# note` on an assignment line is sourced INTO the value by bash only if
    unquoted-and-lucky, and is parsed into the value by every naive reader."""
    bad = []
    for i, line in enumerate((HERE / "WORKERS.conf").read_text().splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        if "#" in s.split("=", 1)[1]:
            bad.append((i, line))
    assert not bad, f"trailing comments on assignment lines: {bad}"


def test_the_two_bands_are_distinct_and_above_the_registry_high_water_mark():
    assert L.BAND_CVAR25 != L.BAND_CVAR50
    reg = (REPO / "governance" / "BAND_REGISTRY.csv").read_text()
    ids = [int(m) for m in re.findall(r"^(\d{10,})", reg, re.M)]
    assert L.BAND_CVAR25 > max(ids), (
        f"proposed band {L.BAND_CVAR25} is not above the registry high-water "
        f"mark {max(ids)} — re-run the sweep and REASSIGN (both of this round's "
        "predecessors had to)")
    assert L.BAND_CVAR50 > max(ids)


def test_the_band_is_proposed_not_claimed():
    """⛔ THIS AGENT CLAIMED NOTHING. The launcher refuses a real cell until the
    orchestrator drops `BAND_CLAIMED`."""
    assert (HERE / "BAND_CLAIMED.placeholder").is_file()


def test_blind_commit_is_pending_or_a_40_hex_sha():
    c = _conf()
    j = json.loads((HERE / "BLIND_COMMIT.json").read_text())
    assert c["BLIND_COMMIT"] == j["blind_commit"], (
        "WORKERS.conf and BLIND_COMMIT.json disagree — the stamping commit must "
        "write BOTH")
    assert (c["BLIND_COMMIT"] == "PENDING"
            or re.fullmatch(r"[0-9a-f]{40}", c["BLIND_COMMIT"]))


# =========================================================================== #
# 2. GATE BEHAVIOUR ON REAL-EMITTER FIXTURES                                   #
# =========================================================================== #

def _case(name):
    d = FIX / name
    m = json.loads((d / "manifest.json").read_text()) if (d / "manifest.json").is_file() else None
    s = json.loads((d / "summary.json").read_text()) if (d / "summary.json").is_file() else None
    return m, s


def test_every_gate_address_exists_in_real_emitter_output():
    """⛔⛔ THE ANTI-VACUOUS-PASS TEST. A gate at a WRONG address returns
    `MISSING`; in a lib that failed OPEN it would pass on every cell forever.
    This asserts each address RESOLVES on a byte-untouched document emitted by
    the real harness — the τ_p leg found three of four obvious guesses wrong,
    and this round's dry cell found `config.opponent.champ_cfg.pool_mode`
    absent (DEVIATIONS D-2)."""
    m = json.loads((FIX / "REALCELL_DRY" / "manifest.json").read_text())
    s = json.loads((FIX / "REALCELL_DRY" / "summary.json").read_text())
    manifest_addrs = [
        "config.cand_search.pool_mode", "config.cand_search.pool_alpha",
        "config.champion.pool_mode", "config.champion.pool_alpha",
        "config.opponent.champ_cfg.pool_mode",
        "config.opponent.champ_cfg.pool_alpha",
        "config.cand_search.fpu_reduction", "config.cand_search.c_puct",
        "config.cand_search.tau_p",
        "config.cand_tiearb", "config.opp_tiearb",
    ] + [a for a, _ in L.BUDGET_CHECKS]
    for a in manifest_addrs:
        assert L.dig(m, a) is not L.MISSING, f"manifest address {a} does not exist"
    for a in ("pool.candidate.cvar_plies", "pool.candidate.pickchanges",
              "pool.candidate.reach_in_play", "pool.candidate.mode",
              "pool.candidate.modes_disagree", "pool.opponent.cvar_plies",
              "pool.opponent.mode"):
        assert L.dig(s, a) is not L.MISSING, f"summary address {a} does not exist"


def test_the_real_dry_cell_passes_the_config_and_reach_gates():
    """The dry cell ran at k2x32, so `G-BUDGET` MUST fail on it — that is the
    gate working, not a defect. Everything else must pass on the real doc."""
    m, s = _case("REALCELL_DRY")
    assert L.gate_pool(m, 0.25) == []
    assert L.gate_singlevar(m) == []
    assert L.gate_arbiter(m) == []
    assert L.gate_reach(s) == []
    assert L.gate_budget(m), "G-BUDGET must FAIL on the k2x32 dry cell"


def test_smoke_pass_case_passes_every_gate():
    m, s = _case("SMOKE_PASS")
    for name, fn in L.MANIFEST_GATES.items():
        problems = fn(m, 0.25) if name == "G-POOL" else fn(m)
        assert problems == [], f"{name} failed on SMOKE_PASS: {problems}"
    assert L.gate_reach(s) == []


@pytest.mark.parametrize("case,gate", [
    ("SMOKE_FAIL_pool_mode_absent", "G-POOL"),
    ("SMOKE_FAIL_pool_mode_mean", "G-POOL"),
    ("SMOKE_FAIL_pool_wrong_dose", "G-POOL"),
    ("SMOKE_FAIL_pool_candidate_unmoved", "G-POOL"),
    ("SMOKE_FAIL_pool_leaked_to_opponent", "G-POOL"),
    ("SMOKE_FAIL_pool_opponent_absent", "G-POOL"),
    ("SMOKE_FAIL_singlevar_fpu_live", "G-SINGLEVAR"),
    ("SMOKE_FAIL_singlevar_cpuct_live", "G-SINGLEVAR"),
    ("SMOKE_FAIL_singlevar_taup_absent", "G-SINGLEVAR"),
    ("SMOKE_FAIL_budget_stale", "G-BUDGET"),
    ("SMOKE_FAIL_rules_walled", "G-BUDGET"),
    ("SMOKE_FAIL_unpaired", "G-BUDGET"),
    ("SMOKE_FAIL_arb_opponent_absent", "G-ARB"),
    ("SMOKE_FAIL_arb_wrong_B", "G-ARB"),
    ("SMOKE_FAIL_arb_candidate_disabled", "G-ARB"),
])
def test_each_manifest_mutation_is_caught_by_its_gate(case, gate):
    m, _ = _case(case)
    fn = L.MANIFEST_GATES[gate]
    problems = fn(m, 0.25) if gate == "G-POOL" else fn(m)
    assert problems, f"{gate} did NOT catch {case}"


@pytest.mark.parametrize("case", [
    "SMOKE_FAIL_reach_zero_pickchanges",
    "SMOKE_FAIL_reach_rule_never_ran",
    "SMOKE_FAIL_reach_opponent_leak",
    "SMOKE_FAIL_reach_mixed_rev",
    "SMOKE_FAIL_reach_block_absent",
    "SMOKE_FAIL_reach_below_floor",
])
def test_g_reach_catches_what_no_config_gate_can(case):
    """⭐⭐ THE POINT OF THIS ROUND'S EXTRA GATE. Every one of these documents
    has a PERFECT manifest — the rule was requested, resolved and stamped — and
    every manifest gate passes it. Only `G-REACH`, which reads PLAY, says the
    candidate never actually differed from the champion."""
    m, s = _case(case)
    for name, fn in L.MANIFEST_GATES.items():
        problems = fn(m, 0.25) if name == "G-POOL" else fn(m)
        assert problems == [], (
            f"{case} was supposed to have a clean manifest; {name} says "
            f"{problems}")
    assert L.gate_reach(s), f"G-REACH did NOT catch {case}"


@pytest.mark.parametrize("case", [
    "SMOKE_EMPTY_CELL", "SMOKE_NO_MANIFEST", "SMOKE_NO_SUMMARY",
    "SMOKE_FAIL_pool_leaked_to_opponent", "SMOKE_FAIL_reach_zero_pickchanges",
])
def test_smoke_adjudicator_exits_nonzero_on_every_failure_shape(case):
    v = A.adjudicate(FIX, case, 0.25)
    assert v["verdict"] == "FAIL", f"{case} adjudicated PASS"
    assert v["fatal"], f"{case} has no fatal reason recorded"


def test_smoke_adjudicator_passes_the_good_case():
    v = A.adjudicate(FIX, "SMOKE_PASS", 0.25)
    assert v["verdict"] == "PASS", v["fatal"]
    assert v["n_records"] == 8
    assert not v["gates_missing"], v["gates_missing"]


def test_an_empty_cell_is_a_fail_not_a_default():
    """⛔ THE R1 DEFECT, REALIZED TWICE (the FPU smoke and phasegate's banked
    SMOKE_local.json both 'passed' over zero adjudicated cells)."""
    v = A.adjudicate(FIX, "SMOKE_EMPTY_CELL", 0.25)
    assert v["verdict"] == "FAIL"
    assert any("ZERO per-game records" in f for f in v["fatal"])


def test_the_smoke_document_emits_no_outcome_key():
    """⛔ The smoke's 8 games decide NOTHING. If an outcome-shaped key ever
    appears in this document someone will eventually read it."""
    v = A.adjudicate(FIX, "SMOKE_PASS", 0.25)
    blob = json.dumps(v).lower()
    for forbidden in ("winrate", "\"elo\"", "paired_mean_margin", "\"z\"",
                      "pts_per_deck", "margin_mean", "verdict_branch"):
        assert forbidden not in blob, f"the smoke document leaked {forbidden!r}"


# =========================================================================== #
# 3. THE READ RULE                                                             #
# =========================================================================== #

@pytest.mark.parametrize("m,se,want", [
    (3.0, 0.68, "P-POOLING-MOVES"),     # LB95 = 1.88 > 1.0
    (2.2, 0.68, "P-POOLING-MOVES"),     # LB95 = 1.081 > 1.0
    (2.0, 0.68, "P-UNRESOLVED"),        # LB95 = 0.881
    (0.0, 0.68, "P-UNRESOLVED"),        # UB95 = 1.119
    (-0.2, 0.68, "P-BOUNDED"),          # UB95 = 0.919 < 1.0
    (-1.5, 0.68, "P-REGRESSION"),       # UB95 = -0.381 < 0
])
def test_read_branch_matches_the_prereg_table(m, se, want):
    assert L.read_branch(m, se) == want


def test_the_bar_is_not_two_sigma_of_the_instrument():
    """⛔ OWNER RULING 2026-08-30. A bar defined as 2*se makes the kill branch
    fire only on a NEGATIVE point estimate."""
    assert L.BAR_M != pytest.approx(2 * L.SE_M_EXPECTED, rel=1e-6)
    assert L.BAR_M == 1.0


def test_the_nulls_read_distribution_matches_the_prereg():
    """The §5.3 table, recomputed. If the bar or the realized SE ever move, the
    prereg's published probabilities must move with them."""
    se = L.SE_M_EXPECTED
    def phi(x):
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    p_regression = phi((L.BAR_REGRESSION - 1.645 * se) / se)
    p_bounded_or_better = phi((L.BAR_M - 1.645 * se) / se)
    p_adopt = 1 - phi((L.BAR_M + 1.645 * se) / se)
    assert p_regression == pytest.approx(0.05, abs=0.01)
    assert p_bounded_or_better == pytest.approx(0.43, abs=0.02)
    assert p_adopt == pytest.approx(0.001, abs=0.001)


# =========================================================================== #
# 4. PLUMBING — the REAL argparse and the REAL config builders                  #
# =========================================================================== #

def _eval_mod():
    sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
    import env_preamble  # noqa: F401
    sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
    import eval_fair_puct
    return eval_fair_puct


def test_the_flags_exist_in_the_real_argparse_and_the_help_renders():
    """⛔ DRIVES `main(['--help'])`, which is the only honest way to ask — the
    parser is built inside `main()`.

    ⚠️⚠️ AND IT IS A REGRESSION TEST FOR A REAL CROSS-BOX DEFECT. Python 3.14's
    argparse VALIDATES help strings through %-formatting (`_check_help`), so a
    bare `%` raises `ValueError: badly formed help string` — at PARSER BUILD
    time, i.e. the harness will not start. The local box runs 3.12 (which does
    not validate) and the LAPTOP, where these cells run, runs 3.14. The first
    golden-gate run died on exactly this. See DEVIATIONS D-3."""
    E = _eval_mod()
    buf = io.StringIO()
    with pytest.raises(SystemExit):
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            E.main(["--help"])
    h = buf.getvalue()
    assert "--cand-pool-mode" in h
    assert "--cand-pool-alpha" in h


def test_help_strings_have_no_unescaped_percent():
    """The static half of the test above, so the reason is greppable even on a
    box whose argparse does not validate."""
    src = (REPO / "scripts" / "classical_search" / "eval_fair_puct.py").read_text()
    block = src[src.index("--cand-pool-mode"):src.index("--cand-tiearb-phase-gate")]
    for m in re.finditer(r"%", block):
        assert block[m.start():m.start() + 2] == "%%", (
            "a bare '%' in an argparse help string raises on python 3.14 "
            "(_check_help) — the LAPTOP runs 3.14")


def test_the_rule_reaches_the_candidate_and_not_the_opponent():
    E = _eval_mod()
    cs = {"fpu_reduction": None, "c_puct": None, "tau_p": None,
          "shared_c_puct": 1.5, "shared_tau_p": 5.0,
          "pool_mode": "cvar", "pool_alpha": 0.25}
    cand = E._build_champ_cfg(1.5, 5.0, "float", "visits", 15.0, None,
                              cand_search=cs)
    assert (cand.pool_mode, cand.pool_alpha) == ("cvar", 0.25)
    opp = E._cfg_from_dict({"c_puct": 1.5, "tau_p": 5.0, "leaf_quantize": "float",
                            "final_select": "visits", "value_norm": 15.0,
                            "fpu_reduction": None}, None)
    assert (opp.pool_mode, opp.pool_alpha) == ("mean", None), (
        "⛔⛔ the pooling rule LEAKED into the shared build path")


def test_the_resolved_rust_config_carries_the_rule():
    """⛔⛔ THE FPU LESSON, AS A TEST. `rust_agent.search_config_rs` is where
    knobs go missing: `fpu_reduction` sat there as a hard-coded `None` for
    months while both legs claimed to implement it. This asserts the RESOLVED
    rust config carries the rule — read off the `pool` GETTER, which returns
    numbers, not off a repr (rust's Display prints 1.0 as '1')."""
    carc_rs = pytest.importorskip("carc_rs")
    if not hasattr(carc_rs.SearchConfigRs, "pool"):
        pytest.skip("the installed carc_rs predates measurement/cvar_pool_prep")
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
    from carcassonne_ai.rust_agent import search_config_rs
    sc = search_config_rs(HeuristicPriorConfig(), 8)
    assert dict(sc.pool) == {"mode": "mean", "alpha": None}
    sc = search_config_rs(
        HeuristicPriorConfig(pool_mode="cvar", pool_alpha=0.25), 8)
    assert dict(sc.pool) == {"mode": "cvar", "alpha": 0.25}


def test_the_config_refuses_every_malformed_request():
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
    for bad in (dict(pool_mode="cvar"),
                dict(pool_mode="mean", pool_alpha=0.25),
                dict(pool_mode="cvar", pool_alpha=0.0),
                dict(pool_mode="cvar", pool_alpha=-0.25),
                dict(pool_mode="cvar", pool_alpha=1.5),
                dict(pool_mode="cvar", pool_alpha=float("nan")),
                dict(pool_mode="CVaR", pool_alpha=0.25),
                dict(pool_mode="nonsense")):
        with pytest.raises(ValueError):
            HeuristicPriorConfig(**bad)


def test_the_manifest_states_the_rule_positively_even_when_off():
    """`pool_mode: "mean"` / `pool_alpha: null` are POSITIVE statements, never
    missing keys — the always-present convention every `cand_search` consumer
    relies on."""
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig
    man = HeuristicPriorConfig().as_manifest()
    assert man["pool_mode"] == "mean"
    assert man["pool_alpha"] is None


def test_the_python_search_path_refuses_the_rule_loudly():
    """⛔ RUST-ONLY. A python-search candidate that quietly dropped the rule
    would play champion-vs-champion and grade a perfect, meaningless null."""
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.heuristic_prior_mcts import (
        HeuristicPriorConfig, make_heuristic_prior_evaluator)
    cfg = HeuristicPriorConfig(pool_mode="cvar", pool_alpha=0.25)
    with pytest.raises(NotImplementedError):
        make_heuristic_prior_evaluator(Game(), cfg)


def test_the_harness_refuses_a_half_specified_request():
    """`--cand-pool-mode cvar` with no alpha, and an alpha with no mode, both
    die at LAUNCH rather than in a worker 6 hours in."""
    # ⚠️ There is no `--dry-run` on this harness. Both refusals fire inside the
    # argument-validation block, which runs long before the out-dir is created
    # or a worker pool is forked, so an invalid invocation costs nothing — and
    # the tiny budget below is belt-and-braces in case a future edit moves the
    # check later.
    base = [sys.executable,
            str(REPO / "scripts" / "classical_search" / "eval_fair_puct.py"),
            "--info", "fair", "--backend", "rust", "--n", "2", "--paired",
            "--k-dets", "2", "--sims", "8"]
    for extra, needle in (
            (["--cand-pool-mode", "cvar"], "requires --cand-pool-alpha"),
            (["--cand-pool-alpha", "0.25"], "without --cand-pool-mode cvar")):
        r = subprocess.run(base + extra, capture_output=True, text=True,
                           cwd=str(REPO), timeout=300)
        assert r.returncode != 0, f"{extra} was accepted"
        assert needle in (r.stderr + r.stdout), (extra, r.stderr[-800:])


# =========================================================================== #
# 5. THE GOLDEN GATE, as banked                                                #
# =========================================================================== #

def test_the_banked_golden_gate_is_a_full_frozen_pass():
    g = json.loads((HERE / "CVAR_BITEXACT.json").read_text())
    assert g["verdict"] == "PASS", g["failed"]
    assert g["full_frozen_set"] is True, (
        f"{g['seeds_played']}/{g['frozen_seed_count']} — a PREVIEW pass may not "
        "authorise a band, and run_cells.sh refuses one")
    names = {c["check"] for c in g["checks"]}
    for required in ("IDENTITY", "POSITIVE", "CANDIDATE-ONLY",
                     "ALPHA1-EQUALWEIGHT-ARM", "MEAN-COUNTERS-ZERO",
                     "WHEEL-SWUNG", "TREE-SWUNG"):
        assert required in names, f"the banked gate has no {required} check"


def test_the_golden_gate_records_that_alpha_one_is_not_the_deployed_mean():
    """⚠️⚠️ THE BUILD BRIEF'S ONE FACTUAL CORRECTION, PINNED. The brief asked
    for 'α=1.0 ⇒ bit-exact with mean'. The census that licensed this lever
    measured that FALSE (DEVIATIONS D-1: the α=1.00 rule changes the pick on
    18.1% of contest-exposed plies by itself, because it weights worlds EQUALLY
    while the deployed rule weights them by VISITS). A future reader who
    'fixes' α=1.0 into an identity has to delete this assertion."""
    g = json.loads((HERE / "CVAR_BITEXACT.json").read_text())
    c = next(c for c in g["checks"] if c["check"] == "ALPHA1-EQUALWEIGHT-ARM")
    assert c["ok"]
    assert c["detail"]["identical_to_mean"] is False, (
        "α=1.0 came out bit-identical to the deployed pool. That is not a "
        "passing identity control — it means the equal-weight rule was "
        "implemented as the visit-weighted one, i.e. the rule is WRONG.")
    assert c["detail"]["games_that_differ_from_mean"] > 0
