#!/usr/bin/env python3
"""Offline E4-replay read for the TARGETED-DENIAL leaf term (BACKLOG 2026-05-16
item 3; LEVER_INDEX "targeted denial"; the free evidence read that runs BEFORE
any strength cell).

    scripts/classical_search/denial_e4_replay.py \
        -o measurement/denial_e4_replay_20260811 [--doses 0.5,1.0] \
        [--limit-games 1] [--limit-plies 0] [--archive-dir measurement/e4_games]

Replays the E4 human-vs-champion phone archives and, at every CHAMPION decision
ply, runs the production search once per arm — the production leaf, plus one
denial leaf per dose (`LeafConfig.denial_dose`, thresholds at their defaults
8/2 unless --size-min/--open-max) — with CRN determinizations (SAME agent seed
and SAME `_move_idx` on every arm, so all arms search identical worlds and a
pick flip is attributable to the leaf, not the draw). Reports the pick-flip
rate overall and exactly WHICH plies flip (game id, ply, phase, k_remaining).

What this does NOT do: play any games, measure any elo, or touch governance.
It answers "does the term change the champion's play at all at plausible
doses?" for free, so the dose screen (measurement/denial_screen_20260811/
PREREG_DRAFT.md) is only bought if the answer is not 'never'.

Design points, all inherited from the ev_loss grader (scripts/analyzer/
ev_loss.py — the archive-replay precedent of record):

* **The rules profile is resolved FROM each archive** (`resolve_profile_name`),
  never from a flag — a walled-era archive is graded under `walled` (R9 OFF).
  R9 is import-latched, so the orchestrator mode spawns ONE SUBPROCESS PER
  ARCHIVE (`--single`), each with a fresh latch. Mixed-profile corpora are
  therefore fine.
* **Budget defaults to the archive's own stamp** (`k_dets_effective` x
  `sims_effective`) — the champion's own opinion at the budget it played;
  --sims/--k-dets override for smokes.
* **Exact-tail plies are skipped** (k_remaining <= EXACT_MAX_K): the agent
  latches to the marginalized endgame solver there, which scores the TRUE final
  score — the leaf (and hence denial) cannot flip those plies by construction.
  Forced plies (one legal action) are skipped for the same reason.
* **Resumable**: one `plies_<stem>.jsonl` per archive, appended per graded ply;
  on restart, already-graded plies are replayed WITHOUT searching (the arms are
  deterministic given seed+move_idx, so nothing is lost) and grading resumes at
  the first missing ply. A `game_<stem>.json` summary marks a finished archive;
  the orchestrator skips those.

⚠️ Requires a DENIAL-CAPABLE carc_rs build (the term ships in the Rust leaf;
`rust_agent.leaf_config_rs` raises TypeError on a stale build rather than
silently searching an intact leaf — run with the worktree wheel on PYTHONPATH
until the build is installed). The champion arm is `make_production_champion(
verify=True)`; the denial arms are the same RustFairAgent construction with
ONLY the leaf replaced (verified below by leaf-hash stamping).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "analyzer"))

# ev_loss pulls in env_preamble (production leaf env) BEFORE any carcassonne_ai
# import and carries the archive/profile machinery this script reuses verbatim.
import ev_loss  # noqa: E402

SCHEMA = "carcassonne-denial-e4-replay/v1"
DEFAULT_ARCHIVE_DIR = REPO / "measurement" / "e4_games"


# --------------------------------------------------------------------------- #
# arms                                                                         #
# --------------------------------------------------------------------------- #
def _make_arms(game, spec, ex, seed, sims, k_dets, doses, size_min, open_max):
    """The champion arm (verify=True) + one denial arm per dose.

    The denial arms replicate `make_production_champion`'s rust branch —
    RustFairAgent with the SAME game geometry, sims, k_dets, seed, exact
    settings — with ONLY the embedded leaf replaced, so a pick flip is the
    leaf's doing and nothing else's."""
    import dataclasses as dc

    from carcassonne_ai.champion_factory import (make_production_champion,
                                                 production_leaf_cfg,
                                                 production_prior_cfg)
    from carcassonne_ai.rust_agent import RustFairAgent

    if not ex.is_rust:
        raise SystemExit(
            f"[denial_e4] execution resolved to backend={ex['backend']!r}; the denial "
            "arms are rust-only (the term's production backend). Fix PRODUCTION.yaml "
            "resolution or pass a rust-capable environment.")

    champ = make_production_champion("fair", game=game, seed=int(seed), sims=sims,
                                     k_dets=k_dets, verify=True, **ex.factory_kwargs())

    def _geom(g):
        geom: dict = {"window_size": int(getattr(g, "window_size", 25))}
        if getattr(g, "recentred", False):
            geom["start_row"] = int(g.start_row)
            geom["start_col"] = int(g.start_col)
        if getattr(g, "fixed_start_tile", False):
            geom["start_rule"] = "retail"
        if getattr(g, "cloister_scan_fix", False):
            geom["cloister_scan_fix"] = True
        dr = getattr(g, "draw_rule", None)
        if dr is not None and dr != "engine":
            geom["draw_rule"] = str(dr)
        return geom

    base_leaf = production_leaf_cfg(spec)
    arms = {}
    for d in doses:
        leaf_d = dc.replace(base_leaf, denial_dose=float(d),
                            denial_size_min=float(size_min),
                            denial_open_max=int(open_max))
        cfg_d = production_prior_cfg(spec, leaf_d)
        arms[f"d{d:g}"] = RustFairAgent(
            game, cfg_d,
            sims=(spec.sims_per_det if sims is None else int(sims)),
            k_dets=(spec.k_dets if k_dets is None else int(k_dets)),
            seed=int(seed), exact_endgame=True, exact_max_k=spec.exact_max_k,
            threads=(1 if ex["rust_threads"] is None else int(ex["rust_threads"])),
            **_geom(game))
    return champ, arms, base_leaf


# --------------------------------------------------------------------------- #
# one archive                                                                  #
# --------------------------------------------------------------------------- #
def grade_archive(archive_path: Path, out_dir: Path, *, doses, size_min, open_max,
                  seed, sims, k_dets, rust_threads, limit_plies=0) -> dict:
    import random

    import numpy as np

    arch = ev_loss.load_archive(archive_path)
    profile_name = ev_loss.resolve_profile_name(arch["provenance"])
    env_stamp = ev_loss.prepare_env(profile_name)

    from carcassonne_ai import fair_agent, rules_profile
    from carcassonne_ai.champion_factory import load_production_spec
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, reseat, resolve_execution

    prof = rules_profile.activate(profile_name)
    spec = load_production_spec()
    ex = resolve_execution("inherit", profile="desktop", rust_threads=rust_threads)

    sims_eff = sims or int(arch["sims_effective"] or 0) or None
    k_eff = k_dets or int(arch["k_dets_effective"] or 0) or None
    if sims_eff is None or k_eff is None:
        raise SystemExit(f"[denial_e4] {archive_path.name}: archive stamps no budget; "
                         "pass --sims/--k-dets")

    actions = arch["actions"][: limit_plies or None]
    deck_seed = arch["deck_seed"]
    champ_seat = 1 - arch["human_player"]

    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    champ, arms, base_leaf = _make_arms(game, spec, ex, seed, sims_eff, k_eff,
                                        doses, size_min, open_max)
    all_agents = [champ, *arms.values()]
    for a in all_agents:
        reseat(a, deck_seed=deck_seed, actions=(), move_idx=0)

    stem = archive_path.stem
    ply_path = out_dir / f"plies_{stem}.jsonl"
    done_plies = {}
    if ply_path.exists():
        for line in ply_path.open():
            if line.strip():
                r = json.loads(line)
                done_plies[int(r["ply"])] = r

    exact_max_k = int(fair_agent.EXACT_MAX_K)
    recs = list(done_plies.values())
    t0 = time.time()
    n_searched = 0
    with ply_path.open("a") as fh:
        for ply, played in enumerate(actions):
            st = board.state
            legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
            if played not in legal:
                raise ValueError(f"archive action {played} illegal at ply {ply}")
            graded = (st.current_player == champ_seat and len(legal) > 1
                      and len(st.deck) > exact_max_k)
            if graded and ply not in done_plies:
                rec = {"ply": ply, "phase": st.phase.value,
                       "k_remaining": len(st.deck), "n_legal": len(legal),
                       "action_played": int(played)}
                for a in all_agents:
                    a._move_idx = ply                    # CRN: same worlds every arm
                s0 = time.time()
                champ_pick = int(champ.choose_action(board))
                rec["champ_pick"] = champ_pick
                rec["champ_agrees_archive"] = bool(champ_pick == int(played))
                for name, agent in arms.items():
                    pick = int(agent.choose_action(board))
                    rec[f"pick_{name}"] = pick
                    rec[f"flip_{name}"] = bool(pick != champ_pick)
                rec["secs"] = round(time.time() - s0, 3)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                recs.append(rec)
                n_searched += 1
                if n_searched % 8 == 0:
                    print(f"  [{stem}] ply {ply}/{len(actions)} graded={n_searched} "
                          f"{time.time()-t0:.0f}s", flush=True)
            board, _ = game.get_next_state(board, int(played))
            advance(all_agents, int(played))

    recs.sort(key=lambda r: r["ply"])
    arm_names = [f"d{d:g}" for d in doses]
    summary = {
        "schema": SCHEMA,
        "archive": archive_path.name,
        "deck_seed": deck_seed,
        "rules_profile": profile_name,
        "human_player": arch["human_player"],
        "champion_seat": champ_seat,
        "recorded_scores": arch["recorded_scores"],
        "replayed_scores": ([int(x) for x in board.state.scores]
                            if not limit_plies else None),
        "replay_scores_match": (arch["recorded_scores"] is not None and not limit_plies
                                and list(board.state.scores) == arch["recorded_scores"]),
        "budget": {"sims_per_det": sims_eff, "k_dets": k_eff,
                   "source": ("archive" if not (sims or k_dets) else "CLI override")},
        "seed": int(seed),
        "doses": list(doses),
        "denial_size_min": float(size_min),
        "denial_open_max": int(open_max),
        "leaf_hash_production": _leaf_hash_of(base_leaf),
        "n_plies_total": len(actions),
        "n_graded": len(recs),
        "n_searched_this_run": n_searched,
        "champ_agrees_archive": sum(1 for r in recs if r["champ_agrees_archive"]),
        "flips": {n: sum(1 for r in recs if r.get(f"flip_{n}")) for n in arm_names},
        "flip_plies": {n: [{k: r[k] for k in ("ply", "phase", "k_remaining",
                                              "champ_pick", f"pick_{n}")}
                           for r in recs if r.get(f"flip_{n}")] for n in arm_names},
        "mean_secs_per_graded_ply": (round(sum(r["secs"] for r in recs) / len(recs), 3)
                                     if recs else None),
        "env": env_stamp,
        "wall_secs": round(time.time() - t0, 1),
    }
    (out_dir / f"game_{stem}.json").write_text(json.dumps(summary, indent=1))
    fl = {n: summary["flips"][n] for n in arm_names}
    print(f"[denial_e4] {stem}: profile={profile_name} graded={len(recs)} "
          f"flips={fl} agree_archive={summary['champ_agrees_archive']}/{len(recs)} "
          f"({summary['wall_secs']}s)", flush=True)
    return summary


def _leaf_hash_of(cfg) -> str:
    """The a36d2e15 harness dialect (provenance stamp)."""
    from carcassonne_ai.alphabeta_agent import _leaf_hash
    return _leaf_hash(cfg)


# --------------------------------------------------------------------------- #
def _rollup(out_dir: Path) -> None:
    games = sorted(out_dir.glob("game_*.json"))
    if not games:
        return
    summaries = [json.loads(p.read_text()) for p in games]
    arm_names = sorted({n for s in summaries for n in s["flips"]})
    total = sum(s["n_graded"] for s in summaries)
    roll = {
        "schema": SCHEMA + "/rollup",
        "n_games": len(summaries),
        "n_graded_plies": total,
        "flip_rate": {n: (sum(s["flips"].get(n, 0) for s in summaries) / total
                          if total else None) for n in arm_names},
        "flips_total": {n: sum(s["flips"].get(n, 0) for s in summaries)
                        for n in arm_names},
        "champ_agrees_archive_rate": (sum(s["champ_agrees_archive"] for s in summaries)
                                      / total if total else None),
        "by_game": [{"archive": s["archive"], "profile": s["rules_profile"],
                     "n_graded": s["n_graded"], "flips": s["flips"],
                     "recorded_scores": s["recorded_scores"],
                     "human_player": s["human_player"],
                     "flip_plies": s["flip_plies"]} for s in summaries],
    }
    (out_dir / "SUMMARY.json").write_text(json.dumps(roll, indent=1))
    print(f"[denial_e4] rollup: {len(summaries)} games, {total} graded plies, "
          f"flip rates { {n: roll['flip_rate'][n] for n in arm_names} } "
          f"-> {out_dir/'SUMMARY.json'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-dir", default=str(DEFAULT_ARCHIVE_DIR))
    ap.add_argument("--single", default=None,
                    help="grade ONE archive in THIS process (internal: the "
                         "orchestrator spawns one subprocess per archive so each "
                         "gets a fresh R9 import latch)")
    ap.add_argument("-o", "--out-dir", required=True)
    ap.add_argument("--doses", default="0.5,1.0",
                    help="comma-separated denial doses (default 0.5,1.0)")
    ap.add_argument("--size-min", type=float, default=8.0)
    ap.add_argument("--open-max", type=int, default=2)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--sims", type=int, default=0,
                    help="sims per determinization (0 = the archive's own stamp)")
    ap.add_argument("--k-dets", type=int, default=0,
                    help="determinizations (0 = the archive's own stamp)")
    ap.add_argument("--rust-threads", type=int, default=None)
    ap.add_argument("--limit-games", type=int, default=0,
                    help="grade only the N NEWEST archives (smoke)")
    ap.add_argument("--limit-plies", type=int, default=0,
                    help="first N plies only (wiring smoke; summary marked partial)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doses = tuple(float(x) for x in args.doses.split(",") if x.strip())
    if not doses or any(d == 0.0 for d in doses):
        raise SystemExit("--doses must be nonzero (dose 0.0 IS the champion arm)")

    if args.single:
        grade_archive(Path(args.single), out_dir, doses=doses,
                      size_min=args.size_min, open_max=args.open_max,
                      seed=args.seed, sims=args.sims, k_dets=args.k_dets,
                      rust_threads=args.rust_threads,
                      limit_plies=args.limit_plies)
        return

    archives = sorted(Path(args.archive_dir).glob("*.json"),
                      key=lambda p: p.name, reverse=True)
    if args.limit_games:
        archives = archives[: args.limit_games]
    todo = [p for p in archives if not (out_dir / f"game_{p.stem}.json").exists()]
    print(f"[denial_e4] {len(archives)} archives, {len(archives)-len(todo)} already "
          f"done, {len(todo)} to grade; doses={list(doses)} "
          f"size_min={args.size_min} open_max={args.open_max}", flush=True)
    for p in todo:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--single", str(p),
               "-o", str(out_dir), "--doses", args.doses,
               "--size-min", str(args.size_min), "--open-max", str(args.open_max),
               "--seed", str(args.seed), "--sims", str(args.sims),
               "--k-dets", str(args.k_dets)]
        if args.rust_threads is not None:
            cmd += ["--rust-threads", str(args.rust_threads)]
        if args.limit_plies:
            cmd += ["--limit-plies", str(args.limit_plies)]
        rc = subprocess.call(cmd)
        if rc != 0:
            raise SystemExit(f"[denial_e4] subprocess failed rc={rc} on {p.name} — "
                             "stopping (fail loud; the jsonl is resumable)")
    _rollup(out_dir)


if __name__ == "__main__":
    os.nice(19)
    main()
