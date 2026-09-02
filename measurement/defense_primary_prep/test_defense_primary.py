#!/usr/bin/env python3
"""Selftests for the DEFENSE-PRIMARY census classifier and the accrual check.

Run:
    PYTHONPATH=<worktree>/src:<worktree>/engine:<worktree>/scripts \
        .venv/bin/python -m pytest measurement/defense_primary_prep/test_defense_primary.py -q

FIXTURE TRAP.  Every fixture in `selftest_fixture/` is the REAL emitter's output
on a REAL archive (`make_fixture.py`, provenance stamped).  Nothing here is
hand-written, so a test passing means the code agrees with the emitter, not with
whoever wrote the test.

Sections
    1  the frozen constants and the prose agree
    2  eligibility — the GAME-level exclusion, and its loud refusal
    3  corpus tagging
    4  the classifier reproduces its own banked fixture, ply for ply
    5  the defense stratum's contract (THE PRIMARY)
    6  the price wall (G-NOPRICE) and the budget pin (G-BUDGET/G-UNARMED/G-NOARB)
    7  the ledger + the accrual arithmetic and its exit codes
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIX = HERE / "selftest_fixture"
sys.path.insert(0, str(HERE))

import census_new_plies as C                                     # noqa: E402
import accrual_check as A                                        # noqa: E402
from summarize_ledger import budget_epoch                        # noqa: E402

CONST = json.loads((HERE / "PREREG_CONSTANTS.json").read_text())
PREREG = (HERE / "PREREG.md").read_text()


def jl(p: Path):
    return [json.loads(l) for l in p.open() if l.strip()]


# --------------------------------------------------------------------------- #
# 1. the frozen constants and the prose agree                                   #
# --------------------------------------------------------------------------- #
def test_prereg_prose_carries_every_frozen_number():
    """A constant that drifts from its prereg is a silently moved bar."""
    for token in (str(CONST["TRIGGER_N_DEFENSE"]),
                  str(CONST["TRIGGER_N_DEFENSE_CHAMPION_LEG"]),
                  f'+{CONST["BAR_FUND"]}', f'+{CONST["BAR_REOPEN_DEFENSE"]}',
                  str(CONST["BUDGET_PIN"]["total_sims"]),
                  str(CONST["CONTINUATION"]["arm_dose"]),
                  CONST["CONTINUATION"]["arm_scope"],
                  CONST["BUDGET_PIN"]["leaf_hash_of_record"]):
        assert token in PREREG, f"PREREG.md does not carry {token!r}"


def test_bar_is_not_two_sigma_of_the_instrument():
    """The 2026-08-30 owner ruling: a bar is an effect size, never 2*se_model."""
    two_sigma = 2 * CONST["POWER"]["projected_se_at_trigger"]
    assert abs(CONST["BAR_FUND"] - two_sigma) > 0.15, (
        "BAR_FUND has landed exactly on 2*se — re-derive it from the decision")
    assert CONST["BAR_FUND"] > two_sigma, (
        "a bar BELOW 2*se makes the bounded-null branch unreachable")


def test_null_read_distribution_is_declared_and_sums_to_one():
    d = CONST["NULL_READ_DISTRIBUTION"]
    tot = sum(v for k, v in d.items() if k.startswith("DP-"))
    assert 0.98 <= tot <= 1.02, tot
    assert d["DP-NULL-BOUNDED"] > 0.5, (
        "under a true null the round must discharge a bound more often than not "
        "— that is the whole point of the 2026-08-30 ruling")


def test_constants_match_the_code():
    assert C.PINNED_K_DETS == CONST["BUDGET_PIN"]["k_dets"]
    assert C.PINNED_SIMS_PER_DET == CONST["BUDGET_PIN"]["sims_per_det"]
    assert C.PINNED_EXACT_K == CONST["BUDGET_PIN"]["exact_max_k"]
    assert C.LEAF_HASH_OF_RECORD == CONST["BUDGET_PIN"]["leaf_hash_of_record"]
    assert list(C.PRIOR_TARGET_SETS) == CONST["EXCLUSION"]["prior_target_sets"]


# --------------------------------------------------------------------------- #
# 2. eligibility — the GAME-level exclusion                                     #
# --------------------------------------------------------------------------- #
def test_every_e1a_e1b_source_game_is_excluded():
    old = set()
    for r in jl(REPO / "measurement/e1b_armed_continuation_20260901/targets_continuation.jsonl"):
        old.add(r["game"])
    kept, rejected, _prov = C.eligible_archives(REPO)
    names = {p.name for p in kept}
    assert not (names & old), f"E-1a/E-1b source games leaked in: {sorted(names & old)}"
    rej = {r["game"] for r in rejected}
    assert old <= rej, "an E-1a source game was neither kept nor reported as rejected"


def test_eligible_set_is_exactly_the_pricing_untouched_archives():
    kept, rejected, prov = C.eligible_archives(REPO)
    assert len(kept) >= 16
    assert all(p["present"] for p in prov if "e4_ply_pricing" in p["path"] or
               "e4_continuation" in p["path"]), \
        "a prior target set went missing — the exclusion would silently loosen"
    # nothing is dropped silently: kept + rejected covers the whole directory
    n_dir = len(list((REPO / "measurement/e4_games").glob("*.json")))
    assert len(kept) + len(rejected) == n_dir


def test_census_refuses_an_old_game_loudly():
    """Naming an OLD game is a REFUSAL, not a quiet skip."""
    r = subprocess.run(
        [str(HERE / "run_census.sh"), "classify", "--workers", "1",
         "--games", "1785982194_705585.json",
         "--out", "/tmp/_dp_should_not_exist.jsonl"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "G-ELIGIBLE" in (r.stdout + r.stderr)


# --------------------------------------------------------------------------- #
# 3. corpus tagging                                                             #
# --------------------------------------------------------------------------- #
def test_corpus_tags_from_real_archives():
    champ = json.loads((REPO / "measurement/e4_games/1787835876_219596.json").read_text())
    carc = json.loads((REPO / "measurement/e4_games/1788178736_589408.json").read_text())
    assert C.corpus_tag(champ) == "champion_game"
    assert C.corpus_tag(carc) == "carcasum_game"
    assert C.opponent_kind("champion_game") == "champion"
    assert C.opponent_kind("carcasum_game") == "carcasum"


def test_epoch_b_carcasum_gets_its_own_tag():
    """E-5 epoch B (fixed playouts) must not pool with epoch A silently."""
    blob = {"opponent": "carcasum_remote_p103500",
            "remote": {"opponent": {"playouts": 103500}}}
    assert C.corpus_tag(blob) == "carcasum_p103500"


def test_unknown_or_absent_opponent_refuses():
    with pytest.raises(C.Refusal):
        C.corpus_tag({})
    with pytest.raises(C.Refusal):
        C.corpus_tag({"opponent": "some_new_bot"})


# --------------------------------------------------------------------------- #
# 3b. BOTH LABEL SPELLINGS (owner ruling 2026-09-02, "fix the labels")          #
# --------------------------------------------------------------------------- #
# Archives written before 2026-09-02 stamp the phone's CONFIGURED label — always
# `carcasum_remote_5000ms`, whatever the server was really running. Since the
# ruling the stamp is the server's own `/health` label. The corpus tagger has to
# read every existing archive AND every future one, and it must keep epoch A (the
# 5000 ms wall) distinguishable from epoch B (the p103500 pin) across BOTH.
OLD_LABEL = "carcasum_remote_5000ms"          # what every pre-ruling archive says
NEW_LABEL_B = "carcasum_remote_p103500"       # the server's own, fixed-playout mode
NEW_LABEL_A = "carcasum_remote_5000ms"        # the server's own, budget mode


@pytest.mark.parametrize("label", [OLD_LABEL, NEW_LABEL_A, NEW_LABEL_B])
def test_every_label_spelling_is_a_carcasum_game(label):
    """Whichever way the label is spelled, the game is Carcasum — never champion,
    never an unknown that refuses. This is the property the archive's `opponent`
    field is load-bearing for."""
    tag = C.corpus_tag({"opponent": label})
    assert tag in ("carcasum_game", "carcasum_p103500"), tag
    assert C.opponent_kind(tag) == "carcasum"


def test_the_epochs_stay_apart_under_the_new_labels():
    """A budget-mode game and a playout-mode game must not pool, and the label
    alone is enough to tell them apart when there is no `remote` block."""
    assert C.corpus_tag({"opponent": NEW_LABEL_A}) == "carcasum_game"
    assert C.corpus_tag({"opponent": NEW_LABEL_B}) == "carcasum_p103500"


def test_the_playout_pin_outranks_a_stale_label():
    """⛔ THE REASON THE RULING WAS NEEDED, and the reason it is safe to land now.

    Archives exist that say `carcasum_remote_5000ms` while really having run fixed
    playouts — that mislabelling is exactly what the ruling fixes going forward.
    Those archives are still classified correctly, because the epoch is decided by
    `remote.opponent.playouts` (which the manifest block always wrote honestly),
    not by the label. So the fix does not strand the corpus behind it.
    """
    stale = {"opponent": OLD_LABEL, "remote": {"opponent": {"playouts": 103500}}}
    assert C.corpus_tag(stale) == "carcasum_p103500"
    # And the converse: a genuine wall-clock game stays in epoch A under either
    # spelling, because there is no playout pin to find.
    honest = {"opponent": OLD_LABEL, "remote": {"opponent": {"budget_ms": 5000}}}
    assert C.corpus_tag(honest) == "carcasum_game"


def test_a_third_playout_pin_refuses_rather_than_pooling():
    """A `p50000` server is a NEW epoch. Tagging it `carcasum_p103500` would pool
    two strengths into one declared stratum — the failure `corpus_tag`'s final
    refusal exists to prevent, now reachable for the first time because the label
    is derived from the server instead of hardcoded."""
    with pytest.raises(C.Refusal):
        C.corpus_tag({"opponent": "carcasum_remote_p50000"})
    with pytest.raises(C.Refusal):
        C.corpus_tag({"opponent": OLD_LABEL,
                      "remote": {"opponent": {"playouts": 50000}}})


def test_the_ledger_epoch_labels_survive_the_new_spellings():
    """`summarize_ledger.budget_epoch` is the last link in the chain: it turns a
    corpus tag into the epoch name the read-out prints.

    It conditions on `corpus`, never on the raw `opponent` string, so it is label-
    agnostic BY CONSTRUCTION — but epoch A vs epoch B is the distinction the whole
    E-5 contrast rests on, so the chain is tested end to end from the label the
    archive actually carries.
    """
    for label, want in ((OLD_LABEL, "carcasum_A_5000ms"),
                        (NEW_LABEL_A, "carcasum_A_5000ms"),
                        (NEW_LABEL_B, "carcasum_B_p103500")):
        row = {"corpus": C.corpus_tag({"opponent": label})}
        assert budget_epoch(row) == want, (label, row["corpus"])


def test_accrual_counts_no_carcasum_label_as_a_champion_ply():
    """`accrual_check` conditions on `corpus == "champion_game"`, so it is agnostic
    to the label spelling BY CONSTRUCTION — but the accrual number is what the
    DEFENSE-PRIMARY trigger fires on, so "by construction" is worth a test rather
    than an argument."""
    rows = [{"corpus": C.corpus_tag({"opponent": label}), "stratum": "defense",
             "divergent": True}
            for label in (OLD_LABEL, NEW_LABEL_A, NEW_LABEL_B)]
    rows.append({"corpus": "champion_game", "stratum": "defense", "divergent": True})
    champion_rows = [r for r in rows if r["corpus"] == "champion_game"]
    assert len(champion_rows) == 1, "only the champion game accrues"


# --------------------------------------------------------------------------- #
# 4. the classifier reproduces its own banked fixture                           #
# --------------------------------------------------------------------------- #
def test_fixture_provenance_names_a_real_emitter():
    prov = json.loads((FIX / "FIXTURE_PROVENANCE.json").read_text())
    assert prov["emitter"].endswith("census_new_plies.py")
    import hashlib
    for side in ("champion", "carcasum"):
        p = REPO / "measurement/e4_games" / prov["archives"][side]["game"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == \
            prov["archives"][side]["sha256"], \
            f"{side} archive changed under the fixture — regenerate it"


def test_classifier_is_deterministic_against_the_banked_fixture():
    """Re-run the REAL classifier on the REAL archives; demand ply-for-ply equality."""
    stage_a = C.load_stage_a()
    banked = jl(FIX / "candidates_fixture.jsonl")
    prov = json.loads((FIX / "FIXTURE_PROVENANCE.json").read_text())
    got = []
    for side in ("champion", "carcasum"):
        rows, integ = C.classify_game(prov["archives"][side]["game"], "fixed_v1", stage_a)
        assert integ["stage_a_recon_ok"], integ["stage_a_recon_notes"]
        assert integ["plies_match"]
        got.extend(rows)
    got.sort(key=lambda r: (r["game"], r["ply"]))
    assert [json.dumps(r, sort_keys=True) for r in got] == \
           [json.dumps(r, sort_keys=True) for r in sorted(
               banked, key=lambda r: (r["game"], r["ply"]))]


def test_control_sampler_is_reproducible_across_processes():
    """DEVIATION D-1: `hash(stem)` is per-process randomised; CRC32 is not."""
    stem = "1787835876_219596.json"
    a = C.stable_game_salt(stem)
    out = subprocess.run(
        [sys.executable, "-c",
         "import zlib;print(zlib.crc32(b'1787835876_219596.json') & 0xFFFFFFFF)"],
        capture_output=True, text=True, env={"PYTHONHASHSEED": "12345", "PATH": "/usr/bin"})
    assert int(out.stdout.strip()) == a


# --------------------------------------------------------------------------- #
# 5. the defense stratum's contract — THE PRIMARY                               #
# --------------------------------------------------------------------------- #
def test_defense_rows_are_opponent_tiles_plies_inside_the_window():
    rows = jl(FIX / "candidates_fixture.jsonl")
    inv = {(r["game"], r["ply"]) for r in rows if r["stratum"] == "invasion"}
    d = [r for r in rows if r["stratum"] == "defense"]
    assert d, "the fixture must contain defense plies"
    for r in d:
        assert r["actor"] == 1, "a defense ply is the OPPONENT's move"
        assert r["phase"] == "tiles"
        n = r["notes"]
        assert 0 < n["gap_plies"] <= C.DEFENSE_WINDOW_PLIES
        assert (r["game"], n["defends_invasion_ply"]) in inv
        assert n["defends_invasion_ply"] > r["ply"]
        assert n["defender_seat"] == 1
        assert n["defender_kind"] in ("champion", "carcasum")


def test_defense_plies_are_deduplicated_within_a_game():
    rows = jl(FIX / "candidates_fixture.jsonl")
    for g in {r["game"] for r in rows}:
        plies = [r["ply"] for r in rows if r["game"] == g and r["stratum"] == "defense"]
        assert len(plies) == len(set(plies))


def test_strata_are_disjoint_on_plies():
    rows = jl(FIX / "candidates_fixture.jsonl")
    seen = {}
    for r in rows:
        k = (r["game"], r["ply"])
        assert k not in seen, f"{k} classified twice: {seen.get(k)} and {r['stratum']}"
        seen[k] = r["stratum"]


def test_defense_definition_matches_the_inherited_selector():
    """`build_targets.py` is the selector E-1a's defense plies were named by."""
    src = (REPO / "measurement/e4_ply_pricing_20260827/build_targets.py").read_text()
    assert "DEFENSE_WINDOW_PLIES = 8" in src
    assert C.DEFENSE_WINDOW_PLIES == 8
    assert C.CONTROL_SEED == 20260827 and "CONTROL_SEED = 20260827" in src


# --------------------------------------------------------------------------- #
# 6. the price wall and the budget pin                                          #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field", ["delta_pts_mover", "price_played", "solve"])
def test_price_wall_refuses_a_price_shaped_row(field):
    row = {"game": "x", "ply": 1, field: 1.0}
    with pytest.raises(C.Refusal) as e:
        C.check_no_price([row])
    assert "G-NOPRICE" in str(e.value)


def test_price_wall_refuses_a_price_hidden_in_notes():
    with pytest.raises(C.Refusal):
        C.check_no_price([{"game": "x", "ply": 1, "notes": {"delta_pts_mover": 3.47}}])


def test_the_banked_ledger_carries_no_price():
    C.check_no_price(jl(HERE / "NEW_PLIES.jsonl"))
    C.check_no_price(jl(FIX / "ledger_fixture.jsonl"))


def test_budget_gate_refuses_every_drift():
    ok = {"k_dets": 8, "sims_per_det": 1376, "exact_max_k": 2, "seed": 0}
    C.gate_budget(dict(ok))                                    # the pin itself passes
    for bad, gate in ((("k_dets", 16), "G-BUDGET"),
                      (("sims_per_det", 688), "G-BUDGET"),
                      (("exact_max_k", 4), "G-BUDGET"),
                      (("seed", 7), "G-BUDGET"),
                      (("jrules_prior_dose", 0.25), "G-UNARMED"),
                      (("tiearb_enabled", True), "G-NOARB")):
        cfg = dict(ok)
        cfg[bad[0]] = bad[1]
        with pytest.raises(C.Refusal) as e:
            C.gate_budget(cfg)
        assert gate in str(e.value)


def test_absent_budget_key_is_a_failure_not_a_default():
    with pytest.raises(C.Refusal) as e:
        C.gate_budget({"sims_per_det": 1376, "exact_max_k": 2, "seed": 0})
    assert "ABSENT is FAIL" in str(e.value)


def test_pin_verification_reproduced_e1a_counterfactuals():
    """G-PIN: the banked proof that this census IS E-1a's divergence test."""
    v = json.loads((HERE / "PIN_VERIFICATION.json").read_text())
    assert v["PASS"] is True
    assert v["n_checked"] >= 20
    assert v["n_action_match"] == v["n_checked"]
    assert v["n_divergence_verdict_match"] == v["n_checked"]
    assert v["by_stratum"].get("defense", 0) >= 8
    assert v["resolved"]["k_dets"] == 8 and v["resolved"]["sims_per_det"] == 1376


# --------------------------------------------------------------------------- #
# 7. the ledger + the accrual arithmetic                                        #
# --------------------------------------------------------------------------- #
def test_ledger_rows_are_self_describing_and_pricable_without_recensus():
    need = {"game", "ply", "k", "phase", "actor", "played_action",
            "counterfactual_action", "counterfactual_agrees", "divergent",
            "stratum", "corpus", "opponent_kind", "profile", "n_legal",
            "n_plies", "ply_frac", "archive_era", "counterfactual_budget",
            "counterfactual_resolved", "execution", "notes"}
    for r in jl(HERE / "NEW_PLIES.jsonl"):
        assert need <= set(r), sorted(need - set(r))
        assert r["archive_era"]["deck_seed"] is not None, "no CRN world seed"
        assert r["counterfactual_budget"]["total_sims"] == 11008
        assert r["divergent"] == (r["counterfactual_action"] != r["played_action"])
        assert r["counterfactual_agrees"] != r["divergent"]


def test_accrual_counts_only_divergent_defense_plies():
    rows = jl(HERE / "NEW_PLIES.jsonl")
    rep = A.report(rows, CONST["TRIGGER_N_DEFENSE"],
                   CONST["TRIGGER_N_DEFENSE_CHAMPION_LEG"])
    hand = sum(1 for r in rows if r.get("divergent") and r["stratum"] == "defense")
    assert rep["DEFENSE_ACCRUAL"] == hand
    assert rep["REMAINING"] == max(0, CONST["TRIGGER_N_DEFENSE"] - hand)
    assert rep["FIRED"] == (hand >= CONST["TRIGGER_N_DEFENSE"])
    assert sum(rep["by_corpus"].values()) == hand
    assert sum(rep["by_divergence_generator"].values()) == hand
    assert sum(rep["by_budget_epoch"].values()) == hand


def test_accrual_fires_only_at_the_trigger():
    """One below the trigger does not fire; exactly at it does."""
    rows = jl(HERE / "NEW_PLIES.jsonl")
    d = [r for r in rows if r.get("divergent") and r["stratum"] == "defense"]
    assert d, "the banked ledger must contain divergent defense plies"
    n = CONST["TRIGGER_N_DEFENSE"]
    # synthesise a defense population of an exact size by re-stamping the game id
    # (the accrual counts plies; the game id only affects the cluster count)
    def pop(k):
        return [dict(d[i % len(d)], game=f"synthetic_{i}.json") for i in range(k)]
    assert A.report(pop(n - 1), n, 20)["FIRED"] is False
    assert A.report(pop(n - 1), n, 20)["REMAINING"] == 1
    assert A.report(pop(n), n, 20)["FIRED"] is True
    assert A.report(pop(n), n, 20)["REMAINING"] == 0
    # a divergent NON-defense ply never counts toward the trigger
    inv = [dict(r, stratum="invasion") for r in pop(50)]
    assert A.report(inv, n, 20)["DEFENSE_ACCRUAL"] == 0
    # a NON-divergent defense ply never counts either
    nd = [dict(r, divergent=False) for r in pop(50)]
    assert A.report(nd, n, 20)["DEFENSE_ACCRUAL"] == 0


def test_accrual_exit_codes():
    r = subprocess.run([str(HERE / "run_accrual_check.sh"), "--no-update"],
                       capture_output=True, text=True)
    fired = json.loads((HERE / "ACCRUAL.json").read_text())["FIRED"]
    assert r.returncode == (0 if fired else 1), r.stdout[-2000:]
    assert CONST["ACCRUAL_EXIT_CODES"]["0"] == "TRIGGER FIRED"


def test_divergence_generator_separates_the_three_mechanisms():
    rows = [r for r in jl(HERE / "NEW_PLIES.jsonl") if r["divergent"]]
    gens = {A.divergence_generator(r) for r in rows}
    assert gens <= {"same_budget_rebuild", "cross_budget_champion", "cross_agent"}
    for r in rows:
        if r["corpus"] != "champion_game":
            assert A.divergence_generator(r) == "cross_agent"
    # the 2026-09-01 champion pull is the 22k epoch, so its plies are NOT E-1a's
    # generator — the caveat the PREREG's §7.3 rests on, asserted here.
    champ = [r for r in rows if r["corpus"] == "champion_game"]
    if champ:
        assert {budget_epoch(r) for r in champ} == {"champion_22k"}
        assert {A.divergence_generator(r) for r in champ} == {"cross_budget_champion"}
