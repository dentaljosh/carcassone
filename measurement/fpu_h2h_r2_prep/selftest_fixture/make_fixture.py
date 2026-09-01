#!/usr/bin/env python3
"""Build the adjudicator's SELFTEST FIXTURE — a shaped, HEALTHY production-H2H
cell at a tiny deck scale, against which `analyze_h2h.py --selftest` proves the
gates FIRE, the §5 ladder BRANCHES, and the IDENT propositions resolve.

⛔⛔ **SYNTHETIC. NOT A CELL. NOT A MEASUREMENT.** Every number here is hand-made.

⭐⭐ **THE MANIFEST SHAPE IS COPIED FROM A REAL EMITTED ARCHIVE** — the
2026-08-31 wiring smoke `/mnt/c/carc-shared/fpu_ladder/SMOKE_ARBON_H2H/
manifest.json`, an `eval_fair_puct` run at `k16x1376` with `--cand-fpu-reduction
0.2` and the arbiter ARMED — and that is the whole point (`PG-A1`). A fixture
written from the DESIGN rather than from EMITTED OUTPUT teaches the gates the
wrong addresses, and the gates then void every healthy cell (or, worse, pass
vacuously). The shapes that matter and that a from-the-design fixture gets WRONG:

  * ⭐ `config.champion` carries the budget (`k_dets` / `sims_per_det` /
    `total_sims`) AND `fpu_reduction` AND the SEVEN `tiearb_*` TERMINALS.
  * ⭐⭐ `config.opponent.champ_cfg` carries ONLY the six search knobs
    (`c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`,
    `fpu_reduction`) — **NOT the budget and NOT the arbiter.** The opponent's
    budget lives one level up at `config.opponent.{k_dets,sims_per_det,
    total_sims}`, and its ARBITER lives at `config.opponent.tiearb` (mirrored at
    `config.opp_tiearb` and, with realized counts patched in at close-out, at
    the top-level `opp_tiearb`). ⛔ `_cfg_from_dict` reads five keys by name, so
    `champ_cfg` CANNOT carry the arbiter — which is exactly why
    `_make_opponent` needed its own `tiearb` parameter.
  * ⭐ `config.opponent.champ_cfg.fpu_reduction` is an EXPLICIT `null`, not an
    absent key — the positive statement `G-TWOSIDED` needs an address for.
  * ⭐ `config.cand_search` = `{fpu_reduction, c_puct, shared_c_puct}`.
  * ⭐ the top-level `cand_tiearb` / `opp_tiearb` carry the seven spec keys AND
    the REALIZED close-out counts (`fired_plies`, `pickchanges`, …). The gate
    reads the SPEC keys only, so a manifest read before or after close-out gates
    identically — `tests/test_opp_tiearb_plumbing.py` pins that and so does this
    fixture, by carrying the counts.

⚠️ THE OPPONENT-SIDE SHAPE IS TAKEN FROM `tests/test_opp_tiearb_plumbing.py`'s
`test_real_run_manifest_shape` (which asserts it against a REAL 2-game run),
because no banked archive predates the 2026-08-31 plumbing. ⛔ That is a
DISCLOSED weakness of this fixture and the reason the launcher's `--smoke` reads
the shape back off a live manifest before the round.

⚠️ THE SCALE IS THE ONLY THING THAT DIFFERS from the frozen plan: `SPECS.json`
carries the same cell name, role, knob and dose, at 12 decks in 4 chunks instead
of 800 decks in 8. `--selftest` ASSERTS that — a fixture may never silently
redefine the round it is supposed to exercise.

⭐⭐ **AND IT IS A TWO-BOX FIXTURE.** Chunks `c0/c1` carry host `laptop-wsl`,
`c2/c3` carry `5800x-box`, with DIFFERENT (box-local) `carc_rs_binary_sha` values
and the SAME `code_rev` and `BLIND_COMMIT`. ⛔ A one-box fixture could not tell a
healthy two-box round from a `G-WHEEL-SAME` violation, and `DESIGN.md` §6.4's
flexible-box clause would be documented rather than tested.

⭐ IT IS SHAPED TO READ `H-ADOPT`, the branch whose riders are longest and whose
consequence (PROPOSING a PRODUCTION.yaml flip) is the one worth exercising.

⛔ The deck seeds are on the THROWAWAY sub-range only. No claimed band is
touched, on paper or on disk.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import screen_lib as L  # noqa: E402

PIN = "a" * 40                     # a valid 40-hex PINNED_SRC_REV
BLIND = "b" * 40
#: ⚠️⚠️ TWO SHAS AND TWO HOSTS, ON PURPOSE. `carc_rs_binary_sha` is BOX-LOCAL by
#: construction (two boxes compiling identical source produce different bytes),
#: so a fixture with ONE sha could not tell a healthy two-box round from a
#: `G-WHEEL-SAME` violation. ⭐ THE FIXTURE IS A TWO-BOX ROUND, so the selftest
#: exercises the flexible-box clause rather than merely documenting it.
SHA_BY_HOST = {"laptop-wsl": "2222222222222222",
               "5800x-box": "3333333333333333"}
#: ⭐ Chunks 0-1 on the laptop, 2-3 on local — the shape the round produces when
#: the owner adds the local box partway through (DESIGN §6.4).
HOST_BY_CHUNK = ("laptop-wsl", "laptop-wsl", "5800x-box", "5800x-box")
BASE = L.THROWAWAY_BASE            # ⛔ the throwaway sub-range, never a band
N_DECKS = 12
N_CHUNKS = 4                       # ⭐ 4 x 3 decks — the sharding, at fixture scale

#: ⭐ THE SHAPE, chosen so the cell reads H-ADOPT and so the branch is a property
#: of the SHAPE rather than of an RNG draw:
#:     M = 3.00, sd = 1.00, n = 12 -> se 0.2887, LB95 +2.42 >= +1.0 -> H-ADOPT
#: ⚠️ The SEAT spread is LARGE and CANCELS in the deck pair — that is what
#: deck-pairing buys, and it is what keeps the winrate inside G-SAT's rail while
#: the paired margin still resolves.
SHAPE_MEAN, SHAPE_SD = 3.00, 1.00

#: The seven-key deployed spec, plus the realized close-out counts the harness
#: patches into the TOP-LEVEL address at the end of a run.
_REALIZED_CAND = {"fired_plies": 240, "fired_early": 72, "fired_mid": 87,
                  "fired_late": 81, "pickchanges": 111,
                  "tiearb_errors_total": 0, "tiearb_error_rate_on_fired": 0.0}
_REALIZED_OPP = {"fired_plies": 228, "fired_early": 70, "fired_mid": 82,
                 "fired_late": 76, "pickchanges": 102,
                 "tiearb_errors_total": 0, "tiearb_error_rate_on_fired": 0.0}


def _spec() -> dict:
    return dict(L.DEPLOYED_TIEARB)


def manifest(n_decks: int, seed_start: int, host: str = "laptop-wsl",
             n_games: int | None = None) -> dict:
    """⭐ THE EMITTED SHAPE, not the designed one. See the module docstring."""
    tie = _spec()
    champ = {
        "agent": "FairHeuristicPriorAgent",
        "c_puct": L.CHAMP_C_PUCT, "tau_p": 5.0, "leaf_quantize": "float",
        "final_select": "visits", "value_norm": 15.0,
        "jrules_prior_dose": 0.0, "jrules_prior_mask": 31,
        "jrules_prior_scope": "all", "jrules_filter_mask": 0,
        # ⭐ the SEVEN terminals the candidate stamps for its own arbiter
        "tiearb_enabled": True, "tiearb_b": tie["B"], "tiearb_j": tie["J"],
        "tiearb_mode": tie["mode"], "tiearb_salt": tie["salt"],
        "tiearb_eps": tie["eps"], "tiearb_phase_gate": tie["phase_gate"],
        "fpu_reduction": 0.2,
        "k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
        "total_sims": L.TOTAL_SIMS,
        "leaf": "FROZEN v2.9 curve125 production champion leaf",
    }
    # ⚠️⚠️ THE OPPONENT'S SIX KNOBS ONLY — no budget and NO ARBITER under
    # champ_cfg (`_cfg_from_dict` reads five keys by name and drops the rest).
    opp_cfg = {"c_puct": L.CHAMP_C_PUCT, "tau_p": 5.0, "leaf_quantize": "float",
               "final_select": "visits", "value_norm": 15.0,
               "fpu_reduction": None}
    return {
        "kind": "eval_fair_puct", "host": host, "code_rev": PIN[:9],
        "BLIND_COMMIT": BLIND,
        "carc_rs_build": "carc_rs-0.1.0+aaaaaaaaaaaa+rustcunpinned",
        "carc_rs_version": "0.1.0",
        "carc_rs_binary_sha": SHA_BY_HOST[host],
        "mixed_builds": False, "n_failed": 0,
        "_fixture_sha_note": "⚠️ the sha differs by HOST on purpose — it is "
                             "BOX-LOCAL, so G-WHEEL-SAME asserts ONE wheel "
                             "WITHIN a box and never compares across boxes",
        # ⭐ TOP-LEVEL: spec keys + REALIZED close-out counts, both seats.
        "cand_tiearb": {**tie, **_REALIZED_CAND},
        "opp_tiearb": {**tie, **_REALIZED_OPP},
        "rules_profile": {"name": "fixed_v1", "r9_env_ok": True,
                          "r9_env_observed": True, "r9_env_expected": True,
                          "grid_rule": "centered18", "start_rule": "retail"},
        "config": {
            "cand_search": {"fpu_reduction": 0.2, "c_puct": None,
                            "shared_c_puct": L.CHAMP_C_PUCT},
            # ⭐ CONFIG addresses: written before game 1, spec keys ONLY.
            "cand_tiearb": dict(tie),
            "opp_tiearb": dict(tie),
            "cand_leaf_hash": L.LEAF_HASH,
            "opp_leaf_hash": L.LEAF_HASH,
            "cand_leaf_cfg": {"v29_meeple_curve": list(L.LEAF_CURVE125),
                              "bonus_cap": 8.0, "opp_bonus_cap": 8.0,
                              "meeple_k": 2.0},
            "band_seed_start": seed_start, "n_decks": n_decks,
            "seatings_per_deck": 2, "paired": True,
            "n": n_games if n_games is not None else n_decks * 2,
            "seed_start": seed_start,
            "champion": dict(champ),
            "opponent": {
                "agent": "FairHeuristicPriorAgent",
                "champ_cfg": opp_cfg,
                # ⭐ the opponent's BUDGET lives here, one level ABOVE champ_cfg
                "k_dets": L.K_DETS, "sims": None,
                "sims_per_det": L.SIMS_PER_DET, "total_sims": L.TOTAL_SIMS,
                # ⭐⭐ and its ARBITER lives HERE — the block's own mirror
                "tiearb": dict(tie),
                "leaf_hash": L.LEAF_HASH,
                "label": "FAIR PRODUCTION CHAMPION (FairHeuristicPriorAgent, "
                         "heuristic priors, curve125 leaf, k16x1376)",
                "mode": "fair-champion",
                "production_config_deviations": [],
            },
            "endgame": {"mode": L.EXACT_MODE, "exact_k": L.EXACT_K,
                        "exact_budget": 2000000, "shared_by_both_arms": True},
            "backend": {"name": "rust", "requested": "rust",
                        "default": "python", "rust_threads": 1,
                        "mixed_builds": False,
                        "converted_sides": ["candidate", "opponent"],
                        "carc_rs_binary_sha": SHA_BY_HOST[host]},
        },
    }


def records(seed_start, n_decks, mean, sd, rng):
    """Two seatings per deck whose per-deck average has EXACTLY `(mean, sd)`.

    ⭐⭐ AFFINE-RESCALED, NOT MERELY SAMPLED. A fixture whose BRANCH depends on
    an RNG draw is a fixture that will one day flip and take the selftest with
    it. Rescaling to the exact target makes the branch a PROPERTY OF THE SHAPE
    rather than of the seed."""
    raw = [rng.gauss(0.0, 1.0) for _ in range(n_decks)]
    m0 = math.fsum(raw) / n_decks
    s0 = math.sqrt(math.fsum((x - m0) ** 2 for x in raw) / (n_decks - 1))
    deck = [mean + sd * (x - m0) / s0 for x in raw]
    out = []
    for i, d in enumerate(deck):
        s = seed_start + i
        spread = rng.gauss(0.0, 30.0)
        for a_seat, diff in ((0, d + spread), (1, d - spread)):
            out.append({"seed": s, "a_seat": a_seat, "diff": diff,
                        "won_by_champ": diff > 0, "drew": diff == 0,
                        "moves": 140 + (i % 5), "deck_hash": f"deck{i:04d}",
                        "score_p0": 90, "score_p1": 90,
                        "elapsed_s": 400.0 + i})
    return out


def _tiearb_summary_block(prefix: str, games: int, realized: dict) -> dict:
    """The per-seat aggregate `_tiearb_side_summary` writes. ⭐ The KEY NAMES are
    a public interface (`eval_fair_puct.TIEARB_CAND_PREFIX` /
    `TIEARB_OPP_PREFIX`); `G-TIEARB-FIRE` reads them and a rename would void live
    evidence, so they are spelled here exactly as the harness spells them."""
    tie = _spec()
    fired = realized["fired_plies"]
    return {
        f"{prefix}games": games,
        f"{prefix}fired_plies_total": fired,
        f"{prefix}tile_plies_total": int(fired / 0.58),
        f"{prefix}phi": fired / max(1, games),
        f"{prefix}fire_rate_on_tile_plies": 0.58,
        f"{prefix}pickchanges_total": realized["pickchanges"],
        f"{prefix}pickchange_rate": realized["pickchanges"] / max(1, fired),
        f"{prefix}mean_arms": 3.11,
        f"{prefix}playouts_total": int(fired * 3.11 * tie["B"]),
        f"{prefix}secs_total": 40.0 * games,
        f"{prefix}secs_per_game": 40.0,
        f"{prefix}modes": [tie["mode"]],
        f"{prefix}B": [tie["B"]],
        f"{prefix}J": [tie["J"]],
        f"{prefix}phi_offline_prior": 22.96,
        f"{prefix}G_FIRE_floor": 1.0,
        # ⚠️ THE FLAG IS THE **VOID** FLAG: the harness sets it when phi < 1.0.
        # `false` is HEALTHY, and a gate that read it as "did it fire?" would
        # void every good cell and pass every dead one.
        f"{prefix}G_FIRE_fired": bool(fired / max(1, games) < 1.0),
        f"{prefix}errors_total": 0,
        f"{prefix}error_rate_on_fired": 0.0,
        f"{prefix}first_error": None,
        f"{prefix}partial_argmax_total": 0,
        f"{prefix}phase_gates": [tie["phase_gate"]],
        f"{prefix}fired_early_total": realized["fired_early"],
        f"{prefix}fired_mid_total": realized["fired_mid"],
        f"{prefix}fired_late_total": realized["fired_late"],
        f"{prefix}max_plies": [400],
    }


def summary(recs) -> dict:
    per_deck = {}
    for r in recs:
        per_deck.setdefault(r["seed"], {})[r["a_seat"]] = r["diff"]
    ds = [(v[0] + v[1]) / 2 for v in per_deck.values() if 0 in v and 1 in v]
    n = len(ds)
    mean = math.fsum(ds) / n
    var = math.fsum((d - mean) ** 2 for d in ds) / (n - 1)
    se = math.sqrt(var / n)
    w = sum(1 for r in recs if r["won_by_champ"])
    d0 = sum(1 for r in recs if r["drew"])
    wr = (w + 0.5 * d0) / len(recs)
    elo = 400.0 * math.log10(wr / (1 - wr)) if 0 < wr < 1 else 800.0
    out = {"n": len(recs), "n_failed": 0, "n_paired": n,
           "paired_mean_margin": mean,
           "paired_z": mean / se if se else float("nan"),
           "winrate": wr, "elo": elo,
           "k_dets": L.K_DETS, "sims": L.SIMS_PER_DET,
           "total_sims": L.TOTAL_SIMS, "exact_k": L.EXACT_K}
    out.update(_tiearb_summary_block("tiearb_", len(recs), _REALIZED_CAND))
    out.update(_tiearb_summary_block("opp_tiearb_", len(recs), _REALIZED_OPP))
    return out


def main() -> int:
    frozen = L.CELLS[0]
    #: ⭐ THE FIXTURE SPEC — the frozen cell's name, box, knob and dose, at
    #: FIXTURE SCALE and FIXTURE CHUNKING. `--selftest` asserts that role, knob
    #: and value match the frozen plan and that ONLY the scale differs.
    spec = L.CellSpec(name=frozen.name, role=frozen.role, knob=frozen.knob,
                      value=frozen.value, seed_start=BASE, n_decks=N_DECKS,
                      purpose="SYNTHETIC FIXTURE — not the cell",
                      n_chunks=N_CHUNKS)
    rng = random.Random(11)
    for stale in HERE.iterdir():
        if stale.is_dir() and stale.name.startswith(frozen.name):
            for f in stale.iterdir():
                f.unlink()
            stale.rmdir()
    recs = records(BASE, N_DECKS, SHAPE_MEAN, SHAPE_SD, rng)
    by_seed = {}
    for r in recs:
        by_seed.setdefault(r["seed"], []).append(r)
    for row in L.chunk_plan(spec):
        d = HERE / row["name"]
        d.mkdir(exist_ok=True)
        host = HOST_BY_CHUNK[row["chunk"]]
        chunk_recs = [r for s in range(row["seed_lo"], row["seed_hi"] + 1)
                      for r in by_seed.get(s, [])]
        for r in chunk_recs:
            (d / f"seed{r['seed']}_a{r['a_seat']}.json").write_text(
                json.dumps(r, indent=1))
        (d / "summary.json").write_text(
            json.dumps(summary(chunk_recs), indent=1))
        (d / "manifest.json").write_text(json.dumps(
            manifest(row["n_decks"], row["seed_lo"], host=host,
                     n_games=row["n_games"]), indent=1))
    (HERE / "SPECS.json").write_text(json.dumps([{
        "name": spec.name, "role": spec.role, "knob": spec.knob,
        "value": spec.value, "seed_start": BASE, "n_decks": N_DECKS,
        "n_chunks": N_CHUNKS,
        "purpose": "SYNTHETIC FIXTURE — not the cell"}], indent=1))
    (HERE / "PINNED_SRC_REV").write_text(PIN + "\n")
    (HERE / "README.txt").write_text(
        "⛔⛔ SYNTHETIC SELFTEST FIXTURE — NOT THE CELL, NOT A MEASUREMENT.\n"
        "CELL_H2H2_FPU02__c0..c3/ are hand-made by make_fixture.py. Deck seeds\n"
        "are on the THROWAWAY sub-range 169999999xxx; no claimed band is\n"
        "touched. It exists so analyze_h2h.py --selftest can prove the gates\n"
        "fire and the cell branches against a real directory tree.\n\n"
        "⭐⭐ IT IS A **TWO-BOX** FIXTURE, ON PURPOSE. Chunks c0/c1 carry host\n"
        "laptop-wsl and c2/c3 carry 5800x-box, with DIFFERENT (box-local)\n"
        "carc_rs_binary_sha values and the SAME code_rev. That is the exact\n"
        "shape DESIGN §6.4's flexible-box clause produces when the owner adds\n"
        "the local box partway through a round, and it is what makes G-CHUNKS,\n"
        "G-NODUP, G-SHARD-IDENT, the provenance-only G-HOST and the per-box\n"
        "G-WHEEL-SAME TESTED rather than merely written down.\n\n"
        "⭐ The MANIFEST SHAPE is copied from a REAL emitted archive\n"
        "(/mnt/c/carc-shared/fpu_ladder/SMOKE_ARBON_H2H/manifest.json,\n"
        "2026-08-31) — PG-A1: a fixture written from the DESIGN teaches the\n"
        "gates wrong addresses. ⚠️ The OPPONENT-side arbiter shape comes from\n"
        "tests/test_opp_tiearb_plumbing.py::test_real_run_manifest_shape,\n"
        "because no banked archive predates the 2026-08-31 plumbing — a\n"
        "DISCLOSED weakness, and the reason the launcher's --smoke reads the\n"
        "shape back off a live manifest before the round.\n\n"
        "⚠️ THE GOLDEN GATE IS NOT HERE AND IS NOT REBUILT BY THIS ROUND: it is\n"
        "INHERITED from ../../fpu_ladder_prep/FPU_BITEXACT_LADDER.json with the\n"
        "wheel re-asserted at launch, and its two named gaps are paid by the\n"
        "launcher's --smoke IDENT legs (DESIGN §9).\n")
    print(f"[fixture] wrote the healthy TWO-BOX {N_CHUNKS}-chunk H2H cell "
          f"under {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
