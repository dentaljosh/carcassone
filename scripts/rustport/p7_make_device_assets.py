#!/usr/bin/env python3
"""Build the asset bundle the G7 on-device legs consume.

The phone runs Chaquopy, which has no repo checkout: every input an on-device leg
needs has to arrive as a file. This script produces one self-contained directory
that ``android/app/src/androidTest/assets/`` picks up, and it produces the DESKTOP
side of every comparison at the same time — so the device leg is a comparison
against a frozen desktop artefact, not against a second live computation whose
own correctness would then be in question.

Contents
--------
``knobs.json``          PRODUCTION.yaml's champion knobs + the resolved leaf of
                        record, in the exact field shape ``carc_rs.LeafConfigRs``
                        and ``SearchConfigRs`` take. The device rebuilds the same
                        objects from this and cross-checks against
                        ``LeafConfigRs.curve125()``.
``replay_expect.json``  Per-ply sha256 of ``string_representation`` plus the
                        running scores, for both E4 phone archives and N champ
                        games, computed HERE with desktop carc_rs. G7 leg 2 is
                        "the device reproduces these bytes".
``battery.json``        Midgame positions as ``(deck_seed, prefix_actions)`` —
                        the 20-position s/move battery (leg 3) and the soak seed
                        (leg 4). Replayed, never serialised as board state.
``transcendental_inputs.npz``  copied from measurement/rustport_p0.

Usage
-----
    .venv/bin/python scripts/rustport/p7_make_device_assets.py \
        --out android/app/src/androidTest/assets/p7
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "rustport"))

# MUST precede every carcassonne_ai import in this process (root_replay pulls the
# package in). P4's war story: without it the "production" leaf resolves to the
# import-frozen cap-5/meeple_k-0 default and the assets would freeze the WRONG
# champion's knobs, silently.
import prod_leaf_env  # noqa: E402,F401

CHAMP = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
E4_DIR = REPO / "measurement" / "e4_games"
NPZ = REPO / "measurement" / "rustport_p0" / "transcendental_inputs.npz"

# Leaf fields, in the order LeafConfigRs.__new__ takes them.
LEAF_FIELDS = (
    "closure_p", "bonus_cap", "opp_bonus_cap", "meeple_k", "v29_meeple_curve",
    "soft_cap_slope", "opp_soft_cap_slope", "v29_meeple_return_k",
    "v29_farm_flip_k", "bag_close", "tile_counting_closure",
    "closure_continuous_slack",
)


def leaf_to_json(cfg) -> dict:
    out = {}
    for f in LEAF_FIELDS:
        v = getattr(cfg, f, None)
        if f == "closure_p":
            # dict{int: float} on the Python side; carc_rs wants [(int, float)].
            v = ([[int(k), float(x)] for k, x in sorted(v.items())]
                 if isinstance(v, dict) else
                 [[int(a), float(b)] for a, b in (v or [])])
        elif f in ("v29_meeple_curve",):
            v = None if v is None else [float(x) for x in v]
        elif isinstance(v, bool):
            v = bool(v)
        elif isinstance(v, (int, float)):
            v = float(v)
        out[f] = v
    return out


def make_knobs() -> dict:
    import trace_search as T

    k = T.production_knobs()
    return {
        "champion_id": k["champion_id"],
        "c_puct": k["c_puct"],
        "tau_p": k["tau_p"],
        "value_norm": k["value_norm"],
        "score_norm_scale": k["score_norm_scale"],
        "leaf_quantize": k["leaf_quantize"],
        "final_select": k["final_select"],
        "sims_per_det": k["sims_per_det"],
        "k_dets": k["k_dets"],
        "leaf_fingerprint": k["leaf"],
        "leaf_cfg": leaf_to_json(k["leaf_cfg"]),
        # The DESKTOP answer to G7 leg 1's other half. The device leg re-derives
        # its own; a disagreement is the finding.
        "desktop_exp_fma": True,
        "desktop_tanh_flavor": "glibc_fma",
    }


def replay_digests(deck_seed: int, actions: list[int], start_rule: str | None) -> dict:
    """Per-ply sha256(string_representation) + scores, via desktop carc_rs.

    Hashing rather than shipping the reprs keeps the asset small; sha256 over the
    exact bytes is still a byte-equality claim (G1's repr_key gate is what makes
    those bytes the Python engine's)."""
    import carc_rs

    g = carc_rs.MirrorState.from_seed(str(deck_seed), start_rule=start_rule)
    plies = []
    for a in actions:
        g.advance(int(a))
        plies.append({
            "repr_sha": hashlib.sha256(g.string_repr().encode()).hexdigest(),
            "scores": list(g.scores()),
        })
    return {
        "n_plies": len(plies),
        "final_scores": list(g.scores()),
        "is_terminal": bool(g.is_terminal()),
        "plies": plies,
        # A single rolling digest so the device can report one line, and the
        # per-ply list so a mismatch can be localised without a second run.
        "chain_sha": hashlib.sha256(
            "".join(p["repr_sha"] for p in plies).encode()).hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--champ-games", type=int, default=20,
                    help="how many champ_games.jsonl games to freeze (gate bar: >=20)")
    ap.add_argument("--battery", type=int, default=20)
    ap.add_argument("--battery-ply", type=int, default=60,
                    help="prefix length for a midgame position (even = TILES phase)")
    a = ap.parse_args()

    from measurement_infra.root_replay import load_games

    a.out.mkdir(parents=True, exist_ok=True)

    knobs = make_knobs()
    (a.out / "knobs.json").write_text(json.dumps(knobs, indent=1) + "\n")
    print(f"knobs: champion {knobs['champion_id']} leaf {knobs['leaf_fingerprint']} "
          f"k{knobs['k_dets']}x{knobs['sims_per_det']}")

    # ---- replay expectations ------------------------------------------------
    records: list[dict] = []
    for p in sorted(E4_DIR.glob("*.json")):
        d = json.loads(p.read_text())
        # An archive with no `start_rule` predates the retail start and therefore
        # replays under the ENGINE rule — the same fallback android_bridge applies
        # to a save without the field. Getting this wrong decodes a DIFFERENT game
        # from the same (deck_seed, actions).
        records.append({
            "name": f"e4/{p.stem}",
            "deck_seed": int(d["deck_seed"]),
            "actions": [int(x) for x in d["actions"]],
            "start_rule": d.get("start_rule"),
            "expect_scores": list(d["scores"]),
        })
    games = load_games(CHAMP)[:a.champ_games]
    for g in games:
        records.append({
            "name": f"champ/{g.game_id}",
            "deck_seed": int(g.deck_seed),
            "actions": [int(x) for x in g.actions],
            "start_rule": None,
            "expect_scores": None,
        })

    expect = []
    for r in records:
        dig = replay_digests(r["deck_seed"], r["actions"], r["start_rule"])
        if r["expect_scores"] is not None and dig["final_scores"] != r["expect_scores"]:
            raise SystemExit(
                f"{r['name']}: desktop replay scores {dig['final_scores']} != the "
                f"archive's own {r['expect_scores']} — the record does not replay, "
                f"so it cannot be a device gate")
        expect.append({**{k: r[k] for k in ("name", "deck_seed", "actions", "start_rule")},
                       "expect": dig})
    (a.out / "replay_expect.json").write_text(json.dumps(expect) + "\n")
    print(f"replay_expect: {len(expect)} records "
          f"({sum(e['expect']['n_plies'] for e in expect)} plies)")

    # ---- s/move battery -----------------------------------------------------
    battery = []
    for g in load_games(CHAMP):
        if len(battery) >= a.battery:
            break
        if len(g.actions) <= a.battery_ply + 4:
            continue
        battery.append({
            "name": f"champ/{g.game_id}@{a.battery_ply}",
            "deck_seed": int(g.deck_seed),
            "prefix": [int(x) for x in g.actions[:a.battery_ply]],
            "start_rule": None,
        })
    if len(battery) < a.battery:
        raise SystemExit(f"only {len(battery)} battery positions available")
    (a.out / "battery.json").write_text(json.dumps(battery) + "\n")
    print(f"battery: {len(battery)} positions at ply {a.battery_ply}")

    shutil.copy2(NPZ, a.out / "transcendental_inputs.npz")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
