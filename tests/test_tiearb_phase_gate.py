"""THE PHASE FIRE-GATE — contract tests (`measurement/phasegate_prep/`).

The gate is a phase WINDOW on the tie arbiter's *fire* decision. What has to be
true, and what this file pins:

  A. **The window is the CANONICAL census axis, bit for bit.** The rust
     `phase_bucket` is asserted against `sample_agreement_roots.phase_bucket`
     ITSELF — the source of record — not against a hand-written table on each
     side that could drift apart while both stayed green (DESIGN §7.5 test 3).
     ⚠️ Including the `k=48` / `k=24` fall-through to `"late"`, which is
     REPRODUCED, NOT REPAIRED: every artefact keyed on `phase_bucket` (the
     CL-070 root bank, `split_tiearb2.py`'s strata, CENSUS.md §6, the Stage-1
     cuts table this round is testing) carries it.
  B. **The clock is `k_remaining` = undrawn deck + the tile in hand**, never
     `deck_len()` (`search/window_diag.rs:156`), which is off by one against
     that axis and would shift every boundary by one tile.
  C. **Fail-closed everywhere.** An unknown/empty gate raises at the dataclass,
     at the rust parse, and at argparse. ⛔ A silently-defaulted `"all"` on the
     `ARB_EARLY` cell would make it *BE* `ARB_FULL` — the round's primary
     becomes a guaranteed-meaningless duplicate of its own anchor that looks
     perfectly healthy on every other gate (DESIGN §7.4).
  D. **The witnesses exist on disk.** `G-GATE` reads `phase_gate` from the
     manifest's resolved config; `G-PHI` reads the per-phase fire counters,
     which are derived from PLAY. `ABSENT` is `FAIL` at both, so the harness
     SUBSCRIPTS those stats keys rather than `.get(..., 0)`-ing them: a stale
     wheel must raise, never look like "that phase had no fires".

⛔ NOTHING HERE PLAYS A CELL. No band, no deck of any registered range, no
margin, no outcome statistic. The bit-exact identity legs (`gate=all` == today's
ungated arbiter; `gate=none` == the unmodified champion) are a WHEEL-level
property and live in `measurement/phasegate_prep/selftest_fixture/`, because
proving them needs the PRE-change wheel and the POST-change wheel side by side —
which a single-interpreter pytest run cannot have.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC_OF_RECORD = REPO / "scripts/measurement_infra/sample_agreement_roots.py"
CENSUS_COPY = REPO / "scripts/tiletie/chain_census.py"
EVAL = REPO / "scripts/classical_search/eval_fair_puct.py"

# The seven values DESIGN §2.2 obtained by EXECUTING the canonical function.
GOLDEN = [(71, "early"), (49, "early"), (48, "late"), (47, "mid"),
          (25, "mid"), (24, "late"), (23, "late")]


def _canonical_phase_bucket(path: Path):
    """Exec ONLY `PHASE_CUTS` + `def phase_bucket` out of the source of record.

    ⭐ Deliberately not an import: `sample_agreement_roots` pulls the whole
    champion stack at module scope. Reading the file and executing exactly those
    two statements tests THE TEXT OF RECORD with no import side effects — and if
    either statement is renamed or deleted, this raises rather than silently
    testing something else.
    """
    tree = ast.parse(path.read_text())
    wanted = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "PHASE_CUTS" for t in node.targets
        ):
            wanted.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "phase_bucket":
            wanted.append(node)
    assert len(wanted) == 2, f"PHASE_CUTS / phase_bucket not both found in {path}"
    ns: dict = {}
    exec(compile(ast.Module(body=wanted, type_ignores=[]), str(path), "exec"), ns)
    return ns["phase_bucket"], ns["PHASE_CUTS"]


# =========================================================================== #
# A. THE WINDOW — canonical python, and rust against it                       #
# =========================================================================== #

def test_the_canonical_cuts_are_what_the_design_froze():
    _, cuts = _canonical_phase_bucket(SRC_OF_RECORD)
    assert cuts == {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}


def test_canonical_golden_table():
    pb, _ = _canonical_phase_bucket(SRC_OF_RECORD)
    assert [(k, pb(k)) for k, _ in GOLDEN] == GOLDEN


def test_the_census_copy_has_not_drifted_from_the_source_of_record():
    """`chain_census.py:63` documents itself as a VERBATIM copy. If the two ever
    disagree, every phase-keyed artefact in the tree is ambiguous."""
    a, cuts_a = _canonical_phase_bucket(SRC_OF_RECORD)
    b, cuts_b = _canonical_phase_bucket(CENSUS_COPY)
    assert cuts_a == cuts_b
    assert [a(k) for k in range(-3, 80)] == [b(k) for k in range(-3, 80)]


def test_the_boundary_is_reproduced_not_repaired():
    """⚠️⚠️ k=48 and k=24 match NO interval (both cut ends are strict) and fall
    through to "late". A build that "fixes" this VOIDS the round: it would no
    longer be measuring the axis the census and the Stage-1 cuts table label."""
    pb, _ = _canonical_phase_bucket(SRC_OF_RECORD)
    assert pb(48) == "late" and pb(24) == "late"
    assert pb(49) == "early" and pb(47) == "mid" and pb(25) == "mid"


# --------------------------------------------------------------------------- #
# The RUST side of the same window, asserted against the python above.         #
# Skipped (never silently passed) on a wheel that predates the gate.           #
# --------------------------------------------------------------------------- #
def _carc_rs_with_gate():
    try:
        import carc_rs
    except Exception:                                     # pragma: no cover
        return None
    return carc_rs if hasattr(carc_rs, "tiearb_phase_bucket") else None


needs_gate_wheel = pytest.mark.skipif(
    _carc_rs_with_gate() is None,
    reason="installed carc_rs predates tiearb_phase_gate (rebuild the wheel)",
)


@needs_gate_wheel
def test_rust_phase_bucket_equals_the_canonical_python_everywhere():
    carc_rs = _carc_rs_with_gate()
    pb, _ = _canonical_phase_bucket(SRC_OF_RECORD)
    # the whole real range (71 -> 0) plus both out-of-range tails
    for k in range(-5, 100):
        assert carc_rs.tiearb_phase_bucket(k) == pb(k), f"k={k}"


@needs_gate_wheel
def test_rust_gate_fires_exactly_on_its_own_bucket():
    carc_rs = _carc_rs_with_gate()
    pb, _ = _canonical_phase_bucket(SRC_OF_RECORD)
    for k in range(0, 72):
        assert carc_rs.tiearb_phase_gate_fires_at("all", k) is True
        assert carc_rs.tiearb_phase_gate_fires_at("none", k) is False
        fired = [w for w in ("early", "mid", "late")
                 if carc_rs.tiearb_phase_gate_fires_at(w, k)]
        assert fired == [pb(k)], f"k={k} fired {fired}, bucket is {pb(k)}"
    # the two fall-through k's belong to `late` and to NOTHING else
    assert carc_rs.tiearb_phase_gate_fires_at("early", 48) is False
    assert carc_rs.tiearb_phase_gate_fires_at("late", 48) is True
    assert carc_rs.tiearb_phase_gate_fires_at("mid", 24) is False
    assert carc_rs.tiearb_phase_gate_fires_at("late", 24) is True


@needs_gate_wheel
def test_rust_gate_parse_is_fail_closed():
    carc_rs = _carc_rs_with_gate()
    for bad in ("", "ALL", "Early", "full", "phase:early", "0", "none "):
        with pytest.raises(ValueError):
            carc_rs.tiearb_phase_gate_fires_at(bad, 40)


# =========================================================================== #
# B. THE CLOCK — k_remaining, never deck_len()                                #
# =========================================================================== #

def test_the_rust_gate_reads_k_remaining_not_deck_len():
    """⛔ The single most consequential line in the build. `window_diag.rs:156`
    sets its own `k_remaining` from `deck_len()` — the deck WITHOUT the tile in
    hand. A gate built from that would shift every boundary by one tile and
    silently mis-slice the whole round."""
    src = (REPO / "rust/carc/carc-core/src/fair/mod.rs").read_text()
    hook = src.split("if !self.cfg.search.tiearb_enabled {", 1)[1]
    hook = hook.split("fn tiearb_arbitrate", 1)[0]
    assert "tiearb_phase_gate" in hook and "fires_at(k_remaining(g))" in hook
    # strip `//` comments before the prohibition — the block deliberately NAMES
    # `deck_len()` in prose to say it must not be used.
    code = "\n".join(ln for ln in hook.splitlines()
                     if not ln.lstrip().startswith("//"))
    assert "deck_len" not in code


def test_python_k_remaining_is_the_same_quantity():
    """The rust doc comment names `fair_agent.k_remaining` as its definition."""
    fa = (REPO / "src/carcassonne_ai/fair_agent.py").read_text()
    assert "len(state.deck) + (1 if state.next_tile is not None else 0)" in fa
    rs = (REPO / "rust/carc/carc-core/src/fair/mod.rs").read_text()
    assert "g.state.deck_len() as i64 + i64::from(g.state.next_tile.is_some())" in rs


# =========================================================================== #
# C. FAIL-CLOSED PLUMBING                                                     #
# =========================================================================== #

def test_config_default_is_all_and_bad_values_raise():
    sys.path.insert(0, str(REPO / "src"))
    from carcassonne_ai.heuristic_prior_mcts import HeuristicPriorConfig as HPC

    c = HPC(c_puct=1.5, tau_p=5.0, value_norm=15.0)
    assert c.tiearb_phase_gate == "all", "the DEFAULT must be the ungated arbiter"
    assert c.as_manifest()["tiearb_phase_gate"] == "all"
    for gate in ("early", "mid", "late", "none", "all"):
        assert HPC(c_puct=1.5, tau_p=5.0, value_norm=15.0,
                   tiearb_phase_gate=gate).tiearb_phase_gate == gate
    # ⛔ validated even when the arbiter is DISABLED, so a typo never rides
    for bad in ("", "ALL", "Early", "full", "phase:early"):
        with pytest.raises(ValueError):
            HPC(c_puct=1.5, tau_p=5.0, value_norm=15.0, tiearb_phase_gate=bad)


def test_the_rust_bridge_passes_the_gate_only_inside_the_enabled_block():
    """`search_config_rs` uses the CONDITIONAL-KEYWORD rule: a wheel predating a
    surface keeps serving every default-off (champion) config unchanged, while
    an ENABLED one raises TypeError instead of silently running WITHOUT it. The
    gate must sit inside that same block — an unconditional kwarg would break
    every champion call against an older wheel."""
    src = (REPO / "src/carcassonne_ai/rust_agent.py").read_text()
    block = src.split("tiearb = {}", 1)[1].split("return carc_rs.SearchConfigRs", 1)[0]
    assert "tiearb_phase_gate=" in block
    assert block.index("if bool(getattr(cfg,") < block.index("tiearb_phase_gate=")


def test_eval_harness_carries_the_gate_at_every_owed_address():
    src = EVAL.read_text()
    # the flag, with the frozen choice set
    assert '"--cand-tiearb-phase-gate"' in src
    assert 'choices=("all", "early", "mid", "late", "none"), default="all"' in src
    # the resolved dict -- G-GATE's address, ALWAYS present (never conditional)
    assert "phase_gate=str(args.cand_tiearb_phase_gate)" in src
    # threaded into the rust config
    assert 'tiearb_phase_gate=str(tiearb.get("phase_gate", "all"))' in src


def test_a_gate_without_an_arbiter_is_refused_at_launch():
    """⛔ The mis-typed-launcher shape: `--cand-tiearb-phase-gate early` with no
    `--cand-tiearb-enabled` is a SILENT NO-OP — champion vs champion wearing a
    gated cell's name, reading as a clean healthy null."""
    src = EVAL.read_text()
    assert 'if _cand_tiearb["phase_gate"] != "all" and not _cand_tiearb["enabled"]:' in src
    guard = src.split('_cand_tiearb["phase_gate"] != "all"', 1)[1][:600]
    assert "ap.error(" in guard


def test_the_champion_factory_stamps_the_gate_and_refuses_one_without_an_arbiter():
    """R5 (merge review). The factory FORWARDS `tiearb["phase_gate"]` into the search
    config, so a gated champion PLAYS differently — the `cand_tiearb` stamp must say
    so, or ARB_EARLY and ARB_FULL are manifest-IDENTICAL and the cell is
    unadjudicable. And `phase_gate != "all"` with `enabled=False` is the same silent
    no-op `eval_fair_puct` refuses at `ap.error`, so the factory refuses it too —
    otherwise a mis-built config yields an honest-looking PLAIN champion."""
    sys.path.insert(0, str(REPO / "src"))
    from carcassonne_ai import champion_factory as CF

    src = (REPO / "src/carcassonne_ai/champion_factory.py").read_text()
    assert '"phase_gate": str(tiearb.get("phase_gate", "all")),' in src

    off = {"enabled": False, "B": 16, "J": 4, "mode": "argmax",
           "salt": "tiearb2-deploy-v1", "eps": 0.0}
    for bad in ("early", "mid", "late", "none"):
        with pytest.raises(ValueError, match="phase_gate"):
            CF.production_prior_cfg(tiearb=dict(off, phase_gate=bad))
    # ⭐ "all" is the UNGATED arbiter, so an off dict spelling it is NOT the
    # contradiction — it must still build the champion byte-for-byte.
    assert (CF.production_prior_cfg(tiearb=dict(off, phase_gate="all"))
            == CF.production_prior_cfg())


@pytest.mark.parametrize("driver", ["jcz_match", "carcasum_match"])
def test_the_external_drivers_resolve_the_gate_like_for_like(driver):
    """R5. `SearchConfigRs.tiearb` emits `phase_gate` UNCONDITIONALLY, and both
    drivers' `_worker_init` probes compare `dict(...tiearb) != dict(tiearb)` EXACTLY.
    A `_resolve_tiearb` without the key kills every armed worker at bootstrap on a
    like-for-unlike compare. The fix is the resolver, never the probe — the probe is
    the stale-wheel guard (a wheel predating the gate would run UNGATED, which on an
    ARB_EARLY cell IS ARB_FULL)."""
    src = (REPO / f"scripts/{driver}/match.py").read_text()
    resolver = src.split("def _resolve_tiearb(args)", 1)[1].split("\ndef ", 1)[0]
    assert '"phase_gate": str(getattr(args, "champ_tiearb_phase_gate", "all")),' \
        in resolver
    assert "if resolved != dict(tiearb):" in src, "the guard must NOT be weakened"


def test_the_telemetry_subscripts_the_counters_so_a_stale_wheel_raises():
    """⛔ `ABSENT is FAIL` (READ_RULE §4). `.get(key, 0)` on a wheel that
    predates the gate would report `fired_early = 0` — indistinguishable from
    "the arbiter fired nowhere early", which is the exact reading the round
    exists to produce. It must RAISE."""
    src = EVAL.read_text()
    body = src.split("def _cand_tiearb_telemetry(champ)", 1)[1].split("\ndef ", 1)[0]
    for key in ("tiearb_phase_gate", "tiearb_fired_early", "tiearb_fired_mid",
                "tiearb_fired_late", "tiearb_pickchanges_early",
                "tiearb_pickchanges_mid", "tiearb_pickchanges_late"):
        assert f's["{key}"]' in body, f"{key} must be SUBSCRIPTED, not .get()"
        assert f's.get("{key}"' not in body


def test_the_summary_carries_the_per_phase_aggregates():
    """`G-PHI` resolves its statistics from summary.json (IS-D1: config lives in
    manifest.json, statistics in summary.json)."""
    src = EVAL.read_text()
    for key in ("tiearb_phase_gates", "tiearb_fired_early_total",
                "tiearb_fired_mid_total", "tiearb_fired_late_total",
                "tiearb_fired_by_phase_sum", "tiearb_fired_share_early"):
        assert f'"{key}"' in src


# =========================================================================== #
# D. THE DESIGN'S OWN PROHIBITIONS, pinned so a later edit trips              #
# =========================================================================== #

def test_the_gate_is_not_the_playout_ceiling():
    """⛔ `tiearb_max_plies` is the PLAYOUT ply ceiling (a guard on one
    `tier1-greedy` rollout), NOT a fire-gate. They are different knobs with
    different types and neither may be implemented in terms of the other."""
    rs = (REPO / "rust/carc/carc-core/src/search/mod.rs").read_text()
    assert "pub tiearb_phase_gate: crate::tiearb::TiearbPhaseGate," in rs
    assert "pub tiearb_max_plies: usize," in rs
    tiearb = (REPO / "rust/carc/carc-core/src/tiearb.rs").read_text()
    gate_impl = tiearb.split("impl TiearbPhaseGate {", 1)[1].split("\n}\n", 1)[0]
    assert "max_plies" not in gate_impl.lower()


def test_the_default_is_all_in_rust_too():
    rs = (REPO / "rust/carc/carc-core/src/search/mod.rs").read_text()
    dflt = rs.split("impl Default for SearchConfig {", 1)[1].split("\n}\n", 1)[0]
    assert "tiearb_phase_gate: crate::tiearb::TiearbPhaseGate::All," in dflt


def test_the_windows_the_read_rule_froze_are_the_windows_implemented():
    """The read rule is law; if it and the code disagree, the code is wrong.
    Assert the code against the DOCUMENT's own table."""
    doc = (REPO / "measurement/phasegate_prep/READ_RULE.md").read_text()
    assert "| `early` | **[49, 71]** |" in doc
    assert "| `mid` | **[25, 47]** |" in doc
    assert "**[0, 23]**" in doc and "`k=48` and `k=24`" in doc
    pb, _ = _canonical_phase_bucket(SRC_OF_RECORD)
    assert {k for k in range(0, 72) if pb(k) == "early"} == set(range(49, 72))
    assert {k for k in range(0, 72) if pb(k) == "mid"} == set(range(25, 48))
    assert {k for k in range(0, 72) if pb(k) == "late"} == set(range(0, 24)) | {24, 48}
