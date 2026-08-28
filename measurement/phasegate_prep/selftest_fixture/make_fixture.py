#!/usr/bin/env python3
"""Build the adjudicator's SELFTEST FIXTURE — a shaped, HEALTHY round at a tiny
deck scale, plus the named DEFECT variants each gate exists to catch.

⛔⛔ **SYNTHETIC. NOT A CELL. NOT A MEASUREMENT.** Every number here is
hand-made. It exists so `analyze_phasegate.py --selftest` can prove the gates
FIRE and the ladder BRANCHES against a real directory tree — because a
launcher-side gate that runs once per round is never exercised by the smoke
(IS-D1's instrument-hardening note), and a gate nobody has ever seen fail is a
gate nobody has tested.

⚠️ THE SCALE IS THE ONLY THING THAT DIFFERS from the frozen plan: `SPECS.json`
carries the same cell names, roles, phase gates and pool keys, at 6/10/8/4 decks
instead of 40/400/1037/163. `--selftest` ASSERTS that — a fixture may never
silently redefine the round it is supposed to exercise.

⛔ The deck seeds are on the THROWAWAY sub-range only. No claimed band is
touched, on paper or on disk.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = "a" * 40                     # a valid 40-hex PINNED_SRC_REV
BLIND = "b" * 40
SHA_LOCAL, SHA_LAPTOP = "1111111111111111", "2222222222222222"
BASE = 154_999_999_000             # ⛔ the throwaway sub-range, never the band

# name, role, phase_gate, arb_enabled, seed_start, n_decks, pool_key
FIXTURE_SPECS = [
    ("IDENT", "local", "none", True, BASE + 900, 6, "IDENT"),
    ("ARB_FULL", "laptop", "all", True, BASE, 10, "ARB_FULL"),
    ("ARB_EARLY_L", "local", "early", True, BASE, 8, "ARB_EARLY"),
    ("ARB_EARLY_R", "laptop", "early", True, BASE + 8, 4, "ARB_EARLY"),
]
HOSTS = {"local": "Doctor", "laptop": "laptop-wsl"}
SHAS = {"local": SHA_LOCAL, "laptop": SHA_LAPTOP}


def manifest(name, role, gate_, n_decks, seed_start, fired) -> dict:
    cand_tiearb = {"enabled": True, "B": 16, "J": 4, "mode": "argmax",
                   "salt": "tiearb2-deploy-v1", "eps": 0.0, "phase_gate": gate_}
    champ = {"k_dets": 8, "sims_per_det": 1376, "total_sims": 11008,
             "c_puct": 1.5, "tau_p": 5.0, "value_norm": 15.0,
             "leaf_quantize": "float", "final_select": "visits"}
    return {
        "kind": "eval_fair_puct", "host": HOSTS[role], "code_rev": PIN[:9],
        "BLIND_COMMIT": BLIND,
        "carc_rs_build": "carc_rs-0.1.0+aaaaaaaaaaaa+rustc1.96.0",
        "carc_rs_version": "0.1.0", "carc_rs_binary_sha": SHAS[role],
        "mixed_builds": False, "n_failed": 0,
        "rules_profile": {"name": "fixed_v1", "r9_env_ok": True,
                          "r9_env_observed": True},
        # ⭐ the REALIZED counts patched at close-out live at manifest TOP LEVEL
        # beside the resolved knobs; `config.cand_tiearb` stays CONFIG-ONLY.
        "cand_tiearb": {**cand_tiearb, **{f"fired_{k}": v
                                          for k, v in fired.items()},
                        "fired_plies": sum(fired.values())},
        "config": {
            "cand_tiearb": cand_tiearb,
            "cand_leaf_hash": "a36d2e15a3b3d71d",
            "opp_leaf_hash": "a36d2e15a3b3d71d",
            "cand_leaf_cfg": {"v29_meeple_curve": "curve125"},
            "band_seed_start": seed_start, "n_decks": n_decks,
            "seatings_per_deck": 2,
            "champion": dict(champ),
            # ⚠️ the opponent's knobs live ONE LEVEL DOWN, and it emits a
            # TERMINAL tiearb_enabled=false — the two shapes G-SINGLEVAR and
            # G-TIEARB-ARM are written against.
            "opponent": {"champ_cfg": dict(champ), "tiearb_enabled": False},
            "endgame": {"exact_k": 2, "mode": "marginalized"},
            "backend": {"name": "rust", "requested": "rust",
                        "mixed_builds": False,
                        "converted_sides": ["candidate", "opponent"]},
        },
    }


def records(seed_start, n_decks, mean, rng):
    """Two seatings per deck whose average is `mean` plus noise."""
    out = []
    for i in range(n_decks):
        s = seed_start + i
        d = rng.gauss(mean, 2.0)   # tight ON PURPOSE: the fixture must CONVICT at 10 decks
        # ⭐ the SEAT spread is LARGE and CANCELS in the deck pair — that is what
        # deck-pairing buys, and it is what keeps the winrate inside G-SAT's rail
        # while the paired margin still convicts.
        spread = rng.gauss(0.0, 30.0)
        for a_seat, diff in ((0, d + spread), (1, d - spread)):
            out.append({"seed": s, "a_seat": a_seat, "diff": diff,
                        "won_by_champ": diff > 0, "drew": diff == 0})
    return out


def summary(recs, fired, errors=0) -> dict:
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
    tot = sum(fired.values())
    return {
        "n": len(recs), "n_failed": 0, "n_paired": n,
        "paired_mean_margin": mean, "paired_z": mean / se if se else float("nan"),
        "winrate": wr, "elo": elo,
        "tiearb_games": len(recs),
        "tiearb_fired_plies_total": tot,
        "tiearb_fired_early_total": fired["early"],
        "tiearb_fired_mid_total": fired["mid"],
        "tiearb_fired_late_total": fired["late"],
        "tiearb_fired_by_phase_sum": tot,
        "tiearb_pickchanges_total": tot // 4,
        "tiearb_errors_total": errors,
        "tiearb_error_rate_on_fired": errors / max(1, tot + errors),
        "tiearb_first_error": None,
        "tiearb_phase_gates": [],
    }


def write_round(root: Path, means: dict, fired_by_cell: dict, seed=7) -> None:
    rng = random.Random(seed)
    root.mkdir(parents=True, exist_ok=True)
    specs_out = []
    for name, role, gate_, arb, start, n, pool in FIXTURE_SPECS:
        d = root / name
        d.mkdir(exist_ok=True)
        fired = fired_by_cell[name]
        recs = records(start, n, means[name], rng)
        for r in recs:
            (d / f"seed{r['seed']}_a{r['a_seat']}.json").write_text(
                json.dumps(r, indent=1))
        s = summary(recs, fired)
        s["tiearb_phase_gates"] = [gate_]
        (d / "summary.json").write_text(json.dumps(s, indent=1))
        (d / "manifest.json").write_text(
            json.dumps(manifest(name, role, gate_, n, start, fired), indent=1))
        specs_out.append({"name": name, "role": role, "phase_gate": gate_,
                          "arb_enabled": arb, "seed_start": start,
                          "n_decks": n, "pool_key": pool,
                          "purpose": "SYNTHETIC FIXTURE — not a cell"})
    (root / "SPECS.json").write_text(json.dumps(specs_out, indent=1))
    (root / "PINNED_SRC_REV").write_text(PIN + "\n")
    (root / "README.txt").write_text(
        "⛔⛔ SYNTHETIC SELFTEST FIXTURE — NOT A CELL, NOT A MEASUREMENT.\n"
        "Every number is hand-made by make_fixture.py. Deck seeds are on the\n"
        "THROWAWAY sub-range 154999999xxx and no claimed band is touched.\n"
        "It exists so analyze_phasegate.py --selftest can prove the gates fire\n"
        "and the §5 ladder branches against a real directory tree.\n")


def main() -> int:
    # ⭐ THE HEALTHY ROUND. ARB_FULL convicts (the anchor's hard ordering) and
    # ARB_EARLY sits ABOVE the +0.80 bar, so the ladder must read E-LIVE.
    write_round(
        HERE,
        means={"IDENT": 0.0, "ARB_FULL": 3.07, "ARB_EARLY_L": 2.2,
               "ARB_EARLY_R": 2.2},
        fired_by_cell={
            "IDENT": {"early": 0, "mid": 0, "late": 0},
            "ARB_FULL": {"early": 60, "mid": 55, "late": 63},
            "ARB_EARLY_L": {"early": 48, "mid": 0, "late": 0},
            "ARB_EARLY_R": {"early": 24, "mid": 0, "late": 0},
        })
    print(f"[fixture] wrote the healthy round under {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
