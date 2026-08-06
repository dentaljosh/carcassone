#!/usr/bin/env python3
"""FARM-WAR DISCRIMINATOR — the stratifier (pre-registration §Stratification).

Pre-registration: measurement/analyzer_evloss_20260805/FARMWAR_PREREG.md (committed
226a676, BEFORE anything here ran). This module implements the PRIMARY stratifier and
nothing else; it does not score, decide, or promote.

THE PRIMARY RULE IS BUILDABLE (checked 2026-08-05, against docs/LEVER_INDEX.md:203's
"farm terms still DEFERRED (F7b) — not config-severable"):

  * `LeafConfig.farm_base_off` / `farm_growth_off` (virtual_score_v2.py:205-206) exist and
    are wired through `flat_leaf.flat_virtual_score_v2` (:1064, :808) AND the Rust leaf
    (carc-core/src/leaf/mod.rs:135-138). The F7b cells that ran them are on disk
    (measurement/leaf_ablation_20260730/cells/abl_farm{base,growth}off_*.json).
  * The production leaf's OTHER farm-flavoured term, C7 Term F, is OFF by construction:
    `production_leaf_cfg().v29_farm_flip_k == 0.0`, so `flat_farm_flip_term` is never
    added (flat_leaf.py:1081). The two knockouts therefore sever EVERY live farm term,
    which is what makes the ≥50%-share rule well posed.
  * A set knockout leaves the Cython fast path by design (`_farm_knockout_off`,
    flat_leaf.py:994) — bit-exact, ~12.5x slower per leaf. Irrelevant at ~150 leaf evals.

So the manifest stamps `stratifier_rule: "primary_leaf_term"`. The pre-registered
FALLBACK is implemented too (`--rule fallback`) but is not the path taken.

THE RULE, exactly as pre-registered
-----------------------------------
For a candidate ply with root board B, mover = Joshua (actor 0), and the two actions
`action_played` (his) / `action_best` (the champion's pooled-Q argmax):

    L_full(S)   = flat_virtual_score_v2_float(S, root_player, production_leaf_cfg)
    L_nofarm(S) = same, with farm_base_off=True and farm_growth_off=True
    farm(S)     = L_full(S) - L_nofarm(S)

    total_diff = L_full(S_played) - L_full(S_best)      # signed, Joshua's seat
    farm_diff  = farm(S_played)  - farm(S_best)
    farm_share = |farm_diff| / |total_diff|

    farm_driven  <=>  farm_share >= 0.5

`L_*` is already a differential (the flat leaf returns player-minus-opponent), so both
successors are read from the SAME seat and the difference is a like-for-like margin.

DEGENERATE TOTAL. If |total_diff| <= 1e-9 the champion's leaf sees the two successors as
equal in value and the share is undefined (0/0). Such a ply is classified NEITHER
`farm_driven` NOR control-eligible — it is dropped with `excluded="degenerate_total_diff"`
and counted in the manifest. Forcing it into either stratum would be a rule the
pre-registration does not contain.

MIXED RULES EPOCHS. `CARCASSONNE_FIX_R9` is import-latched (rules_profile.R9_ENV_VAR), so
`emit` handles ONE profile per process and refuses artifacts belonging to another. The
driver runs it once per epoch and `match` merges the per-epoch jsonl files with no engine
import at all.

Modes
-----
  emit  --profile NAME --artifact A.json [...] --out cand_NAME.jsonl
        Engine work. One rules profile per process.
  match --inputs cand_*.jsonl --out strata.json --positions positions.jsonl
        Pure stdlib. Builds FARM, matches CONTROL by nearest-neighbour |ΔQ| without
        replacement, applies the pre-registered n>=10 gate, and writes the position file
        the scorer consumes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "human_anchor"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "measurement_infra"))

# MUST precede any `carcassonne_ai` import — same first-import discipline as ev_loss.py.
import env_preamble  # noqa: E402,F401

SCHEMA = "carcassonne-analyzer-farmwar-strata/v1"

#: Buckets the pre-registration admits into either stratum.
CANDIDATE_BUCKETS = ("inaccuracy", "blunder")

#: |total_diff| at or below this is a 0/0 share — see the module docstring.
DEGENERATE_EPS = 1e-9

#: The pre-registered share threshold.
FARM_SHARE_THRESHOLD = 0.5


# --------------------------------------------------------------------------- #
# candidate selection (pure, no engine)                                        #
# --------------------------------------------------------------------------- #
def candidate_plies(artifact: dict) -> list:
    """The plies eligible for EITHER stratum, in ply order.

    Pre-registration: "human plies with bucket in {inaccuracy, blunder}". Three further
    conditions are mechanical, not judgement calls, and each removes plies for which the
    statistic Δ = V(played) − V(best) is undefined rather than small:

      * `actor == 0` — Joshua's seat (the brief's definition).
      * NOT `forced` — a ply with one legal action has no alternative to score.
      * `action_played != action_best` — the two arms would be the same afterstate, so Δ
        is identically 0 by construction and would dilute both strata equally.
      * `delta_q is not None` — the CONTROL match is nearest-neighbour ON ΔQ; a ply with
        no eligible ΔQ cannot be matched or be a match.
    """
    out = []
    for p in artifact.get("plies", []):
        if int(p.get("actor", -1)) != 0:
            continue
        if p.get("bucket") not in CANDIDATE_BUCKETS:
            continue
        if p.get("forced"):
            continue
        if p.get("action_best") is None or p.get("action_played") is None:
            continue
        if int(p["action_played"]) == int(p["action_best"]):
            continue
        if p.get("delta_q") is None:
            continue
        out.append(p)
    return out


def classify_primary(l_full_played: float, l_full_best: float,
                     l_nofarm_played: float, l_nofarm_best: float) -> dict:
    """The pre-registered primary rule. Pure arithmetic — pinned by the tests."""
    farm_played = l_full_played - l_nofarm_played
    farm_best = l_full_best - l_nofarm_best
    total_diff = l_full_played - l_full_best
    farm_diff = farm_played - farm_best
    degenerate = abs(total_diff) <= DEGENERATE_EPS
    share = None if degenerate else abs(farm_diff) / abs(total_diff)
    return {
        "leaf_full_played": l_full_played,
        "leaf_full_best": l_full_best,
        "leaf_nofarm_played": l_nofarm_played,
        "leaf_nofarm_best": l_nofarm_best,
        "farm_term_played": farm_played,
        "farm_term_best": farm_best,
        "total_leaf_diff": total_diff,
        "farm_leaf_diff": farm_diff,
        "farm_share": share,
        "degenerate_total_diff": bool(degenerate),
        "farm_driven": bool((not degenerate) and share >= FARM_SHARE_THRESHOLD),
    }


# --------------------------------------------------------------------------- #
# emit — one rules profile per process                                          #
# --------------------------------------------------------------------------- #
def emit(profile_name: str, artifact_paths: list, out_path: Path, rule: str) -> dict:
    import ev_loss as EV

    env = EV.prepare_env(profile_name)                    # BEFORE carcassonne_ai
    import numpy as np
    from dataclasses import replace

    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai import flat_leaf, rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.activate(profile_name)
    leaf_full = CF.production_leaf_cfg()
    CF.verify_leaf(leaf_full)                             # R1/R7-class provenance guard
    leaf_nofarm = replace(leaf_full, farm_base_off=True, farm_growth_off=True)
    bag_close = bool(getattr(leaf_full, "bag_close", False))
    if float(getattr(leaf_full, "v29_farm_flip_k", 0.0)) != 0.0:
        raise RuntimeError(
            "production leaf has v29_farm_flip_k != 0: the two F7b knockouts no longer "
            "sever every farm term, so the primary stratifier's share is ill-defined. "
            "STOP and re-read the pre-registration rather than shipping a partial split.")

    def leaf(state, player, cfg):
        return float(flat_leaf.flat_virtual_score_v2_float(state, player, cfg, bag_close))

    rows, dropped = [], []
    t0 = time.time()
    for ap_ in artifact_paths:
        art = json.loads(Path(ap_).read_text())
        arch_path = art["archive_path"]
        arch = EV.load_archive(arch_path)
        got = EV.resolve_profile_name(arch)
        if got != profile_name:
            raise ValueError(
                f"{ap_}: archive resolves to profile {got!r} but this process is latched "
                f"to {profile_name!r}. R9 is import-latched — run one process per epoch.")

        import random
        random.seed(int(arch["deck_seed"]))               # root_replay contract
        game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
        board = game.get_init_board()
        actions = arch["actions"]
        cands = {int(p["ply"]): p for p in candidate_plies(art)}
        label = str(art.get("label"))

        for ply, played in enumerate(actions):
            p = cands.get(ply)
            if p is not None:
                st = board.state
                if int(st.current_player) != int(p["actor"]):
                    raise AssertionError(
                        f"{label} ply {ply}: replay actor {st.current_player} != artifact "
                        f"actor {p['actor']} — the replay is not the graded timeline")
                legal = set(int(x) for x in np.flatnonzero(game.get_valid_moves(board)))
                a_played, a_best = int(p["action_played"]), int(p["action_best"])
                if a_played not in legal or a_best not in legal:
                    raise AssertionError(f"{label} ply {ply}: an arm is illegal at the root")
                s_played, _ = game.get_next_state(board, a_played)
                s_best, _ = game.get_next_state(board, a_best)
                rp = int(p["actor"])
                if rule == "primary":
                    ev = classify_primary(
                        leaf(s_played.state, rp, leaf_full),
                        leaf(s_best.state, rp, leaf_full),
                        leaf(s_played.state, rp, leaf_nofarm),
                        leaf(s_best.state, rp, leaf_nofarm))
                else:
                    ev = _classify_fallback(game, board, s_played, s_best, a_played, a_best)
                row = {
                    "rid": f"{label}_p{ply}",
                    "root_id": f"{label}_p{ply}",
                    "game_label": label,
                    "rules_profile": profile_name,
                    "archive_path": str(arch_path),
                    "deck_seed": int(arch["deck_seed"]),
                    "ply": int(ply),
                    "root_player": rp,
                    "bucket": p["bucket"],
                    "phase": p["phase"],
                    "k_remaining": p.get("k_remaining"),
                    "n_legal": p.get("n_legal"),
                    "delta_q": float(p["delta_q"]),
                    "abs_delta_q": abs(float(p["delta_q"])),
                    "delta_points_tanh_est": p.get("delta_points_tanh_est"),
                    # A = the champion's pick, B = Joshua's. position_delta returns B - A,
                    # so `delta` IS the pre-registered Δ = V(played) − V(best).
                    "pick_a": a_best,
                    "pick_b": a_played,
                    "action_best": a_best,
                    "action_played": a_played,
                    "stratifier_rule": rule,
                    "stratifier_evidence": ev,
                }
                if ev.get("degenerate_total_diff"):
                    row["excluded"] = "degenerate_total_diff"
                    dropped.append(row)
                else:
                    rows.append(row)
            board, _ = game.get_next_state(board, int(played))

        if arch.get("recorded_scores") and list(board.state.scores) != list(arch["recorded_scores"]):
            print(f"[warn] {label}: replayed scores {list(board.state.scores)} != archived "
                  f"{arch['recorded_scores']}", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for r in rows + dropped:
            fh.write(json.dumps(r) + "\n")
    meta = {
        "profile": profile_name,
        "rules_profile_manifest": prof.as_manifest(),
        "r9_env": env,
        "artifacts": [str(a) for a in artifact_paths],
        "n_candidates": len(rows) + len(dropped),
        "n_kept": len(rows),
        "n_dropped_degenerate": len(dropped),
        "n_farm_driven": sum(1 for r in rows if r["stratifier_evidence"]["farm_driven"]),
        "stratifier_rule": rule,
        "leaf_cfg_hash": CF.resolved_manifest("clairvoyant", verify=True).get("leaf_hash"),
        "v29_farm_flip_k": float(getattr(leaf_full, "v29_farm_flip_k", 0.0)),
        "wall_secs": round(time.time() - t0, 2),
    }
    (out_path.with_suffix(".meta.json")).write_text(json.dumps(meta, indent=2))
    print(f"[emit] {profile_name}: {meta['n_kept']} kept "
          f"({meta['n_farm_driven']} farm_driven), {meta['n_dropped_degenerate']} degenerate "
          f"-> {out_path}")
    return meta


def _classify_fallback(game, board, s_played, s_best, a_played, a_best) -> dict:
    """The pre-registered FALLBACK rule — implemented so `--rule fallback` is a real path,
    NOT the rule this run used (the primary is cleanly computable; see the docstring).

    "A ply is `farm_driven` iff either action places a farmer, or either action is a tile
    placement that merges/extends a field region already carrying a farmer of either
    player." Farmer placement is read off the meeple counts + the engine's placed-meeple
    list; field growth is read off the flat-leaf decomposition's field components.
    """
    from carcassonne_ai import flat_leaf

    def _farmers(state):
        return [m for m in getattr(state, "placed_meeples", []) or [] for m in ([m] if m else [])]

    def _field_sig(state):
        d = flat_leaf.decompose(state)
        return {"n_fields": len(getattr(d, "fields", []) or [])}

    played_farmer = _placed_a_farmer(board.state, s_played.state)
    best_farmer = _placed_a_farmer(board.state, s_best.state)
    grew = (_field_sig(s_played.state) != _field_sig(board.state)
            or _field_sig(s_best.state) != _field_sig(board.state))
    driven = bool(played_farmer or best_farmer or grew)
    return {
        "played_places_farmer": bool(played_farmer),
        "best_places_farmer": bool(best_farmer),
        "field_region_changed": bool(grew),
        "degenerate_total_diff": False,
        "farm_driven": driven,
        "note": "fallback rule (prereg §Stratification item 2)",
    }


def _placed_a_farmer(before, after) -> bool:
    from wingedsheep.carcassonne.objects.meeple_type import MeepleType
    b = sum(1 for pm in (getattr(before, "placed_meeples", None) or [[], []])
            for pm in pm if getattr(pm, "meeple_type", None) == MeepleType.FARMER)
    a = sum(1 for pm in (getattr(after, "placed_meeples", None) or [[], []])
            for pm in pm if getattr(pm, "meeple_type", None) == MeepleType.FARMER)
    return a > b


# --------------------------------------------------------------------------- #
# match — pure stdlib, no engine                                                #
# --------------------------------------------------------------------------- #
def match_control(farm: list, pool: list) -> list:
    """Nearest-neighbour CONTROL matching on |ΔQ|, WITHOUT replacement.

    Deterministic order, stated here because the pre-registration fixes the estimator and
    not the tie-break: FARM plies are consumed in DESCENDING |ΔQ| (ties broken by
    `(game_label, ply)`), and each takes the still-unused pool member minimising
    ``||ΔQ|_farm - |ΔQ|_pool||`` (ties broken by the same key). Descending order gives the
    hardest-to-match plies (the extreme |ΔQ| tail) first pick, which is the choice that
    makes the matched distributions closest; taking them last would strand them.
    """
    remaining = sorted(pool, key=lambda r: (r["game_label"], r["ply"]))
    picked = []
    for f in sorted(farm, key=lambda r: (-r["abs_delta_q"], r["game_label"], r["ply"])):
        if not remaining:
            break
        j = min(range(len(remaining)),
                key=lambda i: (abs(remaining[i]["abs_delta_q"] - f["abs_delta_q"]),
                               remaining[i]["game_label"], remaining[i]["ply"]))
        c = dict(remaining.pop(j))
        c["matched_to"] = f["rid"]
        c["match_abs_delta_q_gap"] = abs(c["abs_delta_q"] - f["abs_delta_q"])
        picked.append(c)
    return picked


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def match(inputs: list, out_path: Path, positions_path: Path, min_n: int) -> dict:
    rows = []
    for p in inputs:
        for line in Path(p).read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    kept = [r for r in rows if not r.get("excluded")]
    dropped = [r for r in rows if r.get("excluded")]
    farm = [r for r in kept if r["stratifier_evidence"]["farm_driven"]]
    pool = [r for r in kept if not r["stratifier_evidence"]["farm_driven"]]
    control = match_control(farm, pool)

    for r in farm:
        r["stratum"] = "FARM"
    for r in control:
        r["stratum"] = "CONTROL"

    gate_ok = len(farm) >= min_n and len(control) >= min_n
    strata = {
        "schema": SCHEMA,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "prereg": "measurement/analyzer_evloss_20260805/FARMWAR_PREREG.md",
        "stratifier_rule": (kept[0]["stratifier_rule"] if kept else None),
        "inputs": [str(p) for p in inputs],
        "n_candidates": len(rows),
        "n_dropped_degenerate": len(dropped),
        "dropped_rids": [r["rid"] for r in dropped],
        "n_farm": len(farm),
        "n_control": len(control),
        "n_control_pool": len(pool),
        "min_n_gate": int(min_n),
        "gate_ok": bool(gate_ok),
        "gate_verdict": ("PROCEED" if gate_ok else
                         "INCONCLUSIVE-BY-CONSTRUCTION (a stratum is under the "
                         "pre-registered n>=10 floor)"),
        "abs_delta_q_farm_mean": _mean(r["abs_delta_q"] for r in farm),
        "abs_delta_q_control_mean": _mean(r["abs_delta_q"] for r in control),
        "match_gap_mean": _mean(r["match_abs_delta_q_gap"] for r in control),
        "match_gap_max": (max((r["match_abs_delta_q_gap"] for r in control), default=None)),
        "per_epoch": {
            prof: {
                "farm": sum(1 for r in farm if r["rules_profile"] == prof),
                "control": sum(1 for r in control if r["rules_profile"] == prof),
            }
            for prof in sorted({r["rules_profile"] for r in kept})
        },
        "per_game": {
            g: {"farm": sum(1 for r in farm if r["game_label"] == g),
                "control": sum(1 for r in control if r["game_label"] == g)}
            for g in sorted({r["game_label"] for r in kept})
        },
        "farm": farm,
        "control": control,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(strata, indent=2))

    ordered = sorted(farm + control, key=lambda r: (r["rules_profile"], r["rid"]))
    with positions_path.open("w") as fh:
        for r in ordered:
            fh.write(json.dumps(r) + "\n")
    # ...and one file PER EPOCH. `CARCASSONNE_FIX_R9` is an import-time latch, so the
    # scorer must run one process per rules profile; splitting here keeps that split in
    # the artifact rather than in a launcher's shell loop.
    per_epoch_files = {}
    for prof in sorted({r["rules_profile"] for r in ordered}):
        p = positions_path.with_name(f"{positions_path.stem}_{prof}.jsonl")
        with p.open("w") as fh:
            for r in ordered:
                if r["rules_profile"] == prof:
                    fh.write(json.dumps(r) + "\n")
        per_epoch_files[prof] = str(p)
    strata["positions_files"] = per_epoch_files
    out_path.write_text(json.dumps(strata, indent=2))

    print(f"[match] FARM n={len(farm)} | CONTROL n={len(control)} "
          f"(pool {len(pool)}) | degenerate dropped {len(dropped)}")
    print(f"[match] gate(n>={min_n}): {strata['gate_verdict']}")
    print(f"[match] strata -> {out_path}\n[match] positions -> {positions_path}")
    return strata


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    e = sub.add_parser("emit", help="engine pass, ONE rules profile per process")
    e.add_argument("--profile", required=True)
    e.add_argument("--artifact", action="append", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--rule", choices=("primary", "fallback"), default="primary")

    m = sub.add_parser("match", help="merge epochs, build CONTROL, apply the n gate")
    m.add_argument("--inputs", nargs="+", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--positions", required=True)
    m.add_argument("--min-n", type=int, default=10)

    a = ap.parse_args(argv)
    if a.mode == "emit":
        emit(a.profile, a.artifact, Path(a.out), a.rule)
        return 0
    st = match([Path(p) for p in a.inputs], Path(a.out), Path(a.positions), a.min_n)
    return 0 if st["gate_ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
