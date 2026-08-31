#!/usr/bin/env python3
"""Build the adjudicator's SELFTEST FIXTURE — a shaped, HEALTHY ladder at a tiny
deck scale, against which `analyze_ladder.py --selftest` proves the gates FIRE,
the §5 rung ladder BRANCHES, and the §5.4 ROUND VERDICT resolves.

⛔⛔ **SYNTHETIC. NOT A CELL. NOT A MEASUREMENT.** Every number here is
hand-made.

⭐⭐ **THE MANIFEST SHAPE IS COPIED FROM A REAL EMITTED ARCHIVE** — the parent
round's `/mnt/c/carc-shared/fpu_resurrection/CELL_FPU02/manifest.json`, read on
2026-08-30 — and that is the whole point (`PG-A1`). A fixture written from the
DESIGN rather than from EMITTED OUTPUT teaches the gates the wrong addresses,
and the gates then void every healthy cell (or, worse, pass vacuously). The
shapes that matter and that a from-the-design fixture gets WRONG:

  * ⭐ `config.champion` carries the budget (`k_dets` / `sims_per_det` /
    `total_sims`) AND `fpu_reduction` AND the terminal `tiearb_enabled: false`.
  * ⭐⭐ `config.opponent.champ_cfg` carries ONLY the six search knobs
    (`c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`,
    `fpu_reduction`) — **NOT the budget.** The opponent's budget lives one level
    up at `config.opponent.{k_dets,sims_per_det,total_sims}`, which is exactly
    why `gate_budget` and `_sides` carry that fallback address. A fixture that
    put the budget under `champ_cfg` would make the fallback untested.
  * ⭐ `config.opponent.champ_cfg.fpu_reduction` is an EXPLICIT `null`, not an
    absent key — the positive statement `G-TWOSIDED` needs an address for.
  * ⭐ `config.cand_search` = `{fpu_reduction, c_puct, shared_c_puct}`.

⚠️ THE SCALE IS THE ONLY THING THAT DIFFERS from the frozen plan: `SPECS.json`
carries the same rung names, roles, knobs and doses, at 12/10/10/10 decks
instead of 400. `--selftest` ASSERTS that — a fixture may never silently
redefine the round it is supposed to exercise.

⭐ IT IS SHAPED SO ALL FOUR RUNG BRANCHES FIRE AT ONCE, and so the ROUND reads
`LADDER-LIVE`:
    `CELL_FPU005` -> `R-BOUNDED`      `CELL_FPU010` -> `R-UNRESOLVED`
    `CELL_FPU015` -> `R-ADOPT-CANDIDATE`   `CELL_FPU030` -> `R-NEGATIVE`

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
SHAS = {"local": "1111111111111111", "laptop": "2222222222222222"}
HOSTS = {"local": "Doctor", "laptop": "laptop-wsl"}
BASE = L.THROWAWAY_BASE            # ⛔ the throwaway sub-range, never a band

# name, role, knob, dose, seed_start, n_decks
FIXTURE_SPECS = [
    ("CELL_FPU005", "local", "fpu_reduction", 0.05, BASE + 0, 12),
    ("CELL_FPU010", "local", "fpu_reduction", 0.10, BASE + 100, 10),
    ("CELL_FPU015", "laptop", "fpu_reduction", 0.15, BASE + 200, 10),
    ("CELL_FPU030", "laptop", "fpu_reduction", 0.30, BASE + 300, 10),
]


def manifest(name, role, knob, value, n_decks, seed_start) -> dict:
    """⭐ THE EMITTED SHAPE, not the designed one. See the module docstring."""
    cand_fpu = value if knob == "fpu_reduction" else None
    # the CANDIDATE's resolved config — budget lives HERE
    champ = {"agent": "FairHeuristicPriorAgent",
             "k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
             "total_sims": L.TOTAL_SIMS,
             "c_puct": L.CHAMP_C_PUCT, "tau_p": 5.0, "value_norm": 15.0,
             "leaf_quantize": "float", "final_select": "visits",
             "fpu_reduction": cand_fpu,
             "jrules_prior_dose": 0.0, "jrules_filter_mask": 0,
             "tiearb_enabled": False, "tiearb_b": 16, "tiearb_phase_gate": "all"}
    # ⚠️⚠️ THE OPPONENT'S SIX KNOBS ONLY — no budget under champ_cfg. The
    # budget sits one level up, and `fpu_reduction` is an EXPLICIT null.
    opp_cfg = {"c_puct": L.CHAMP_C_PUCT, "tau_p": 5.0, "value_norm": 15.0,
               "leaf_quantize": "float", "final_select": "visits",
               "fpu_reduction": None}
    return {
        "kind": "eval_fair_puct", "host": HOSTS[role], "code_rev": PIN[:9],
        "BLIND_COMMIT": BLIND,
        "carc_rs_build": "carc_rs-0.1.0+aaaaaaaaaaaa+rustc1.96.0",
        "carc_rs_version": "0.1.0", "carc_rs_binary_sha": SHAS[role],
        "mixed_builds": False, "n_failed": 0,
        "cand_tiearb": {"enabled": False, "B": 16, "J": 4, "mode": "argmax",
                        "salt": "tiearb2-deploy-v1", "eps": 0.0,
                        "phase_gate": "all"},
        "rules_profile": {"name": "fixed_v1", "r9_env_ok": True,
                          "r9_env_observed": True, "grid_rule": "centered18",
                          "start_rule": "retail"},
        "config": {
            "cand_search": {"fpu_reduction": cand_fpu, "c_puct": None,
                            "shared_c_puct": L.CHAMP_C_PUCT},
            "cand_tiearb": {"enabled": False, "B": 16, "J": 4,
                            "mode": "argmax", "salt": "tiearb2-deploy-v1",
                            "eps": 0.0, "phase_gate": "all"},
            "cand_leaf_hash": L.LEAF_HASH,
            "opp_leaf_hash": L.LEAF_HASH,
            "cand_leaf_cfg": {"v29_meeple_curve": list(L.LEAF_CURVE125),
                              "bonus_cap": 8.0, "meeple_k": 2.0},
            "band_seed_start": seed_start, "n_decks": n_decks,
            "seatings_per_deck": 2, "paired": True, "n": n_decks * 2,
            "seed_start": seed_start,
            "champion": dict(champ),
            # ⭐ the opponent's BUDGET lives here, one level ABOVE champ_cfg
            "opponent": {"agent": "FairHeuristicPriorAgent",
                         "champ_cfg": opp_cfg,
                         "k_dets": L.K_DETS, "sims": L.SIMS_PER_DET,
                         "sims_per_det": L.SIMS_PER_DET,
                         "total_sims": L.TOTAL_SIMS,
                         "tiearb_enabled": False,
                         "leaf_hash": L.LEAF_HASH,
                         "label": "fair-champion", "mode": "fair-champion"},
            "endgame": {"mode": L.EXACT_MODE, "exact_k": L.EXACT_K,
                        "exact_budget": 2000000, "shared_by_both_arms": True},
            "backend": {"name": "rust", "requested": "rust",
                        "default": "python", "rust_threads": 1,
                        "mixed_builds": False,
                        "converted_sides": ["candidate", "opponent"]},
        },
    }


def records(seed_start, n_decks, mean, sd, rng):
    """Two seatings per deck whose per-deck average has EXACTLY `(mean, sd)`.

    ⭐⭐ AFFINE-RESCALED, NOT MERELY SAMPLED. A fixture whose BRANCH depends on
    an RNG draw is a fixture that will one day flip and take the selftest with
    it. Rescaling to the exact target makes the branch a PROPERTY OF THE SHAPE
    rather than of the seed.

    ⭐ The SEAT spread is LARGE and CANCELS in the deck pair — that is what
    deck-pairing buys, and it is what keeps the winrate inside `G-SAT`'s rail
    while the paired margin still resolves."""
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
                        "won_by_champ": diff > 0, "drew": diff == 0})
    return out


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
    return {"n": len(recs), "n_failed": 0, "n_paired": n,
            "paired_mean_margin": mean,
            "paired_z": mean / se if se else float("nan"),
            "winrate": wr, "elo": elo}


def main() -> int:
    # ⭐ THE SHAPE. Chosen so the four rungs land on FOUR DIFFERENT branches and
    # the ROUND reads LADDER-LIVE. Bar = +1.5 pts/deck, read on LB95 / UB95.
    #   CELL_FPU005  M=0.10 sd=0.7 n=12 -> se 0.2021, UB95 0.504 < 1.5
    #                                      -> R-BOUNDED     (⭐ a POSITIVE point
    #                                         estimate that is still BOUNDED —
    #                                         the reading R-BOUNDED's rider
    #                                         insists on)
    #   CELL_FPU010  M=1.00 sd=3.0 n=10 -> se 0.9487, LB95 -0.90, UB95 +2.90
    #                                      -> R-UNRESOLVED
    #   CELL_FPU015  M=4.00 sd=1.0 n=10 -> se 0.3162, LB95 +3.37 >= 1.5
    #                                      -> R-ADOPT-CANDIDATE
    #   CELL_FPU030  M=-2.00 sd=1.5 n=10 -> se 0.4743, z -4.22 <= -2, M <= 0
    #                                      -> R-NEGATIVE
    # ⭐ These are EXACT: `records()` affine-rescales to the target (mean, sd),
    # so the branches are properties of the SHAPE, not of the RNG seed.
    shape = {"CELL_FPU005": (0.10, 0.7), "CELL_FPU010": (1.00, 3.0),
             "CELL_FPU015": (4.00, 1.0), "CELL_FPU030": (-2.00, 1.5)}
    rng = random.Random(11)
    specs_out = []
    for name, role, knob, value, start, n in FIXTURE_SPECS:
        d = HERE / name
        d.mkdir(exist_ok=True)
        for f in d.glob("seed*_a*.json"):
            f.unlink()
        mean, sd = shape[name]
        recs = records(start, n, mean, sd, rng)
        for r in recs:
            (d / f"seed{r['seed']}_a{r['a_seat']}.json").write_text(
                json.dumps(r, indent=1))
        (d / "summary.json").write_text(json.dumps(summary(recs), indent=1))
        (d / "manifest.json").write_text(
            json.dumps(manifest(name, role, knob, value, n, start), indent=1))
        specs_out.append({"name": name, "role": role, "knob": knob,
                          "value": value, "seed_start": start, "n_decks": n,
                          "purpose": "SYNTHETIC FIXTURE — not a rung"})
    (HERE / "SPECS.json").write_text(json.dumps(specs_out, indent=1))
    (HERE / "PINNED_SRC_REV").write_text(PIN + "\n")
    (HERE / "README.txt").write_text(
        "⛔⛔ SYNTHETIC SELFTEST FIXTURE — NOT A RUNG, NOT A MEASUREMENT.\n"
        "The CELL_* subdirectories are hand-made by make_fixture.py. Deck seeds\n"
        "are on the THROWAWAY sub-range 167999999xxx; no claimed band is\n"
        "touched. They exist so analyze_ladder.py --selftest can prove the\n"
        "gates fire and the ladder branches against a real directory tree.\n\n"
        "⭐ The MANIFEST SHAPE is copied from a REAL emitted archive\n"
        "(fpu_resurrection/CELL_FPU02/manifest.json, 2026-08-30) — PG-A1: a\n"
        "fixture written from the DESIGN teaches the gates wrong addresses.\n\n"
        "⚠️ The GOLDEN GATE's real runs live in ../golden_gate/, not here.\n")
    print(f"[fixture] wrote the healthy ladder under {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
