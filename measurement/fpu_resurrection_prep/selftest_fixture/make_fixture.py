#!/usr/bin/env python3
"""Build the adjudicator's SELFTEST FIXTURE — a shaped, HEALTHY round at a tiny
deck scale, against which `analyze_fpu.py --selftest` proves the gates FIRE and
the §5 ladder BRANCHES.

⛔⛔ **SYNTHETIC. NOT A CELL. NOT A MEASUREMENT.** Every number here is
hand-made. ⚠️ Do not confuse it with the sibling `OLD.json` / `NEW.json` /
`NEW_FPU02.json`, which are REAL runs (the golden gate's three legs).

⚠️ THE SCALE IS THE ONLY THING THAT DIFFERS from the frozen plan: `SPECS.json`
carries the same cell names, roles, knobs and values, at 12/10/10 decks instead
of 400. `--selftest` ASSERTS that — a fixture may never silently redefine the
round it is supposed to exercise.

⭐ IT IS ALSO SHAPED TO EXERCISE THREE DIFFERENT BRANCHES AT ONCE:
`CELL_FPU02` -> `F-RESURRECT`, `CELL_FPU04` -> `F-REKILL`,
`CELL_CPUCT10` -> `F-UNRESOLVED`. The last is load-bearing: it is the branch on
which §6's funded conditionality must RE-KILL the tau pair, and a fixture whose
c_puct cell fired would never test that.

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

# name, role, knob, value, seed_start, n_decks
FIXTURE_SPECS = [
    ("CELL_FPU02", "local", "fpu_reduction", 0.2, BASE + 0, 12),
    ("CELL_FPU04", "local", "fpu_reduction", 0.4, BASE + 100, 10),
    ("CELL_CPUCT10", "laptop", "c_puct", 1.0, BASE + 200, 10),
]

CHAMP_C_PUCT = 1.5


def manifest(name, role, knob, value, n_decks, seed_start) -> dict:
    cand_fpu = value if knob == "fpu_reduction" else None
    cand_c = value if knob == "c_puct" else None
    # the CANDIDATE's resolved config
    champ = {"k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
             "total_sims": L.TOTAL_SIMS,
             "c_puct": (cand_c if cand_c is not None else CHAMP_C_PUCT),
             "tau_p": 5.0, "value_norm": 15.0, "leaf_quantize": "float",
             "final_select": "visits", "fpu_reduction": cand_fpu}
    # ⚠️ the OPPONENT's knobs live ONE LEVEL DOWN under `champ_cfg`, and it
    # states its fpu POSITIVELY as null — the two shapes G-SINGLEVAR and
    # G-TWOSIDED are written against, taken from a REAL manifest.
    opp_cfg = {"k_dets": L.K_DETS, "sims_per_det": L.SIMS_PER_DET,
               "total_sims": L.TOTAL_SIMS, "c_puct": CHAMP_C_PUCT,
               "tau_p": 5.0, "value_norm": 15.0, "leaf_quantize": "float",
               "final_select": "visits", "fpu_reduction": None}
    return {
        "kind": "eval_fair_puct", "host": HOSTS[role], "code_rev": PIN[:9],
        "BLIND_COMMIT": BLIND,
        "carc_rs_build": "carc_rs-0.1.0+aaaaaaaaaaaa+rustc1.96.0",
        "carc_rs_version": "0.1.0", "carc_rs_binary_sha": SHAS[role],
        "mixed_builds": False, "n_failed": 0,
        "rules_profile": {"name": "fixed_v1", "r9_env_ok": True,
                          "r9_env_observed": True},
        "config": {
            "cand_search": {"fpu_reduction": cand_fpu, "c_puct": cand_c,
                            "shared_c_puct": CHAMP_C_PUCT},
            "cand_tiearb": {"enabled": False, "B": 16, "J": 4,
                            "mode": "argmax", "salt": "tiearb2-deploy-v1",
                            "eps": 0.0, "phase_gate": "all"},
            "cand_leaf_hash": L.LEAF_HASH,
            "opp_leaf_hash": L.LEAF_HASH,
            "cand_leaf_cfg": {"v29_meeple_curve": list(L.LEAF_CURVE125)},
            "band_seed_start": seed_start, "n_decks": n_decks,
            "seatings_per_deck": 2,
            "champion": dict(champ),
            "opponent": {"champ_cfg": opp_cfg, "tiearb_enabled": False,
                         "leaf_hash": L.LEAF_HASH},
            "endgame": {"exact_k": L.EXACT_K, "mode": L.EXACT_MODE},
            "backend": {"name": "rust", "requested": "rust",
                        "mixed_builds": False,
                        "converted_sides": ["candidate", "opponent"]},
        },
    }


def records(seed_start, n_decks, mean, sd, rng):
    """Two seatings per deck whose per-deck average has EXACTLY `(mean, sd)`.

    ⭐⭐ AFFINE-RESCALED, NOT MERELY SAMPLED. A fixture whose BRANCH depends on
    an RNG draw is a fixture that will one day flip and take the selftest with
    it: the first draft sampled `gauss(0.10, 6.0)` for `CELL_CPUCT10` and drew a
    set that read `F-RESURRECT` instead of the `F-UNRESOLVED` the tau RE-KILL
    test needs. Rescaling to the exact target makes the branch a PROPERTY OF THE
    SHAPE rather than of the seed.

    ⭐ The SEAT spread is LARGE and CANCELS in the deck pair — that is what
    deck-pairing buys, and it is what keeps the winrate inside G-SAT's rail
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
    # ⭐ THE SHAPE. Chosen so the three cells land on THREE DIFFERENT branches:
    #   CELL_FPU02   M=4.2 sd=1.2 n=12 -> se 0.346, z 12.1, M >= BAR_M
    #                                     -> F-RESURRECT
    #   CELL_FPU04   M=0.05 sd=0.7 n=10 -> se 0.221, UB95 0.49 < BAR_M 1.381
    #                                     -> F-REKILL
    #   CELL_CPUCT10 M=0.60 sd=6.0 n=10 -> se 1.897, z 0.32 (< 2, no RESURRECT),
    #                                     UB95 4.39 > BAR_M (no REKILL)
    #                                     -> F-UNRESOLVED  ⭐ which is what makes
    #                                     §6's tau RE-KILL testable at all.
    # ⭐ These are EXACT: `records()` affine-rescales to the target (mean, sd),
    # so the branches are properties of the SHAPE, not of the RNG seed.
    shape = {"CELL_FPU02": (4.2, 1.2), "CELL_FPU04": (0.05, 0.7),
             "CELL_CPUCT10": (0.60, 6.0)}
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
                          "purpose": "SYNTHETIC FIXTURE — not a cell"})
    (HERE / "SPECS.json").write_text(json.dumps(specs_out, indent=1))
    (HERE / "PINNED_SRC_REV").write_text(PIN + "\n")
    (HERE / "README.txt").write_text(
        "⛔⛔ SYNTHETIC SELFTEST FIXTURE — NOT A CELL, NOT A MEASUREMENT.\n"
        "The CELL_* subdirectories are hand-made by make_fixture.py. Deck seeds\n"
        "are on the THROWAWAY sub-range 157999999xxx; no claimed band is\n"
        "touched. They exist so analyze_fpu.py --selftest can prove the gates\n"
        "fire and the §5 ladder branches against a real directory tree.\n\n"
        "⚠️ OLD.json / NEW.json / NEW_FPU02.json in this directory are the\n"
        "OPPOSITE: they are REAL runs — the three legs of the GOLDEN GATE,\n"
        "adjudicated into ../FPU_BITEXACT.json by identity_diff.py.\n")
    print(f"[fixture] wrote the healthy round under {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
