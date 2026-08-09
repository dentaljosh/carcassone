#!/usr/bin/env python3
"""E4 deck baseline — champion self-play on Joshua's own E4 decks.

Spec (pre-registered BEFORE any game ran):
`measurement/e4_deck_baseline_20260807/SPEC.md`.

WHAT THIS DOES.  For each `fixed_v1`-epoch E4 archive it re-deals the SAME deck
(`random.seed(deck_seed)` -> `Game(**profile.game_kwargs())`, the `root_replay`
contract used by `scripts/analyzer/ev_loss.py`) and plays K champion-vs-champion
games on it.  The mean seat-0 margin over those replicates estimates what the deck
is intrinsically worth to seat 0 — the baseline Joshua's own margin is then read
against as a CONTROL VARIATE (`e4_deck_baseline_analyze.py`).

SIGN CONVENTION, everywhere: **positive = seat 0 = Joshua ahead**
(`scores[0] - scores[1]`).

WHAT IT REUSES (nothing about the agent or the deal is re-implemented here):
  * `scripts/human_anchor/env_preamble.py` — the production leaf env, imported
    before `carcassonne_ai` in every worker,
  * `rules_profile.activate` + `prepare_env`-style R9 latching (R9 is derived at
    `base_deck` import time into a Rust `OnceLock`, so `CARCASSONNE_FIX_R9` MUST be
    in the environment before that import — it is exported in `main()` before any
    worker starts, and re-asserted in the worker),
  * `champion_factory.make_production_champion("fair", ...)` — the champion of
    record at the PRODUCTION.yaml budget (k8 x 1376 = 11008), `verify=True`,
  * `mirror_protocol.resolve_execution` — the rust backend + `rust_threads`,
  * `play_harness.play_game` — THE game loop (mirror seat/advance, telemetry).

PARALLELISM is spent ACROSS games (one game per worker, `rust_threads=1`), never
inside one, so a cell is a clean independent unit of work and a crash costs one game.

CHECKPOINTING is per game: the parent process is the single writer and appends +
fsyncs one JSONL line per finished game.  `--resume` skips any `(deck_seed,
replicate)` cell already in the file, so a dirty box reboot loses only in-flight
games.

Usage:
  # bench ONE game at production knobs (prints s/move; do this before the fleet)
  .venv/bin/python scripts/e4_deck_baseline.py --limit 1 --out /tmp/bench.jsonl

  # the fleet (detached)
  setsid nohup nice -n 19 .venv/bin/python scripts/e4_deck_baseline.py \
      --k 8 --workers 14 --out measurement/e4_deck_baseline_20260807/selfplay.jsonl \
      --resume >> .../driver.log 2>&1 & disown
"""
from __future__ import annotations

# ⚠️ STDLIB ONLY at module level. `carcassonne_ai` must NOT be imported before
# `CARCASSONNE_FIX_R9` is exported (import-latched OnceLock), and this module is
# re-imported by every spawn worker.
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HUMAN_ANCHOR = REPO / "scripts" / "human_anchor"

SCHEMA = "carcassonne-e4-deck-baseline/v1"

#: Agent-seed base for the replicates. Replicate r -> seat0 SEED_BASE+2r,
#: seat1 SEED_BASE+2r+1 (distinct per seat AND per replicate; recorded per game).
SEED_BASE = 7_000_000

DEFAULT_PROFILE = "fixed_v1"
DEFAULT_ARCHIVES = REPO / "measurement" / "e4_games"


def replicate_seeds(replicate: int) -> tuple[int, int]:
    """(seat0_seed, seat1_seed) for replicate index `replicate`. Pre-registered."""
    return SEED_BASE + 2 * int(replicate), SEED_BASE + 2 * int(replicate) + 1


# --------------------------------------------------------------------------- #
# archive selection                                                            #
# --------------------------------------------------------------------------- #
def select_archives(archive_dir=DEFAULT_ARCHIVES, profile: str = DEFAULT_PROFILE) -> list[dict]:
    """The archives whose OWN `rules_profile` stamp equals `profile`.

    ⚠️ Selection is by that stamp and nothing else.  An app build is NEVER
    identified from `(start_rule, grid_rule)` — the Aug-2 build also stamps
    `retail`/`centered18`; the discriminator is `rules_profile`/`cloister_rule`/
    `farm_rule`, whose ABSENCE means a pre-fixed_v1 build."""
    out = []
    for p in sorted(Path(archive_dir).glob("*.json")):
        a = json.loads(p.read_text())
        if a.get("rules_profile") != profile:
            continue
        out.append({
            "path": str(p),
            "file": p.name,
            "deck_seed": int(a["deck_seed"]),
            "human_player": int(a.get("human_player", 0)),
            "scores": [int(x) for x in a["scores"]],
            "margin_seat0_minus_seat1": int(a["scores"][0]) - int(a["scores"][1]),
            "n_actions": len(a.get("actions", [])),
            "rules_profile": a.get("rules_profile"),
        })
    return out


# --------------------------------------------------------------------------- #
# env / worker                                                                 #
# --------------------------------------------------------------------------- #
def export_profile_env(profile: str) -> dict:
    """Export the import-latched env this profile owes. MUST run before any
    `carcassonne_ai.base_deck` import (mirrors `ev_loss.prepare_env`)."""
    sys.path.insert(0, str(REPO / "src"))
    from carcassonne_ai import rules_profile          # cheap: no engine import

    prof = rules_profile.resolve(profile)
    want = "1" if prof.r9_env_expected else "0"
    already = "carcassonne_ai.base_deck" in sys.modules
    if already and rules_profile.r9_env_on() != prof.r9_env_expected:
        raise RuntimeError(
            f"CARCASSONNE_FIX_R9 latched at {rules_profile.r9_env_on()} but profile "
            f"{profile!r} expects {prof.r9_env_expected} — restart the process.")
    os.environ["CARCASSONNE_FIX_R9"] = want
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    return {"CARCASSONNE_FIX_R9": want, "r9_env_expected": prof.r9_env_expected}


_W: dict = {}


def _worker_init(profile: str, rust_threads: int, sims, k_dets) -> None:
    """Spawn-worker bootstrap: env FIRST, then the production leaf, then the engine."""
    export_profile_env(profile)
    if str(HUMAN_ANCHOR) not in sys.path:
        sys.path.insert(0, str(HUMAN_ANCHOR))
    import env_preamble                                # noqa: F401  leaf env, before carcassonne_ai
    import play_harness                                # noqa: F401  (imports env_preamble itself)
    from carcassonne_ai import rules_profile
    from carcassonne_ai.mirror_protocol import resolve_execution

    prof = rules_profile.activate(profile)
    ex = resolve_execution("rust", rust_threads=rust_threads)
    if not ex.is_rust:                                  # the one thing that must not degrade
        raise RuntimeError(f"backend did not resolve to rust: {ex.describe()}")
    _W.update(profile=profile, prof=prof, execution=dict(ex),
              factory_kwargs=ex.factory_kwargs(), sims=sims, k_dets=k_dets,
              play_harness=play_harness, env_resolved=env_preamble.RESOLVED)


def _play_cell(cell: tuple) -> dict:
    """One (deck_seed, replicate) self-play game. Returns the JSONL record."""
    import random  # noqa: F401  (play_game owns the seeding; imported for clarity)

    deck_seed, replicate, meta = cell
    PH = _W["play_harness"]
    prof = _W["prof"]
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game

    s0, s1 = replicate_seeds(replicate)
    t0 = time.time()
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())

    def build(seed):
        return make_production_champion(
            "fair", game=game, seed=int(seed), sims=_W["sims"], k_dets=_W["k_dets"],
            verify=True, **_W["factory_kwargs"])

    agents = {0: build(s0), 1: build(s1)}
    labels = {0: f"champion_s{s0}", 1: f"champion_s{s1}"}
    config = {
        "experiment": "e4_deck_baseline",
        "rules_profile": _W["profile"],
        "rules_manifest": prof.as_manifest(),
        "execution": _W["execution"],
        "sims_override": _W["sims"], "k_dets_override": _W["k_dets"],
        "seat0_seed": s0, "seat1_seed": s1, "replicate": replicate,
        "leaf_env": _W["env_resolved"],
    }
    rec = PH.play_game(game, int(deck_seed), agents, labels, config)

    r, m = rec["result"], rec["manifest"]
    # The RESOLVED budget/leaf, read off the factory's own runtime manifest — never the
    # (None = "use PRODUCTION.yaml") override kwargs, which record nothing.
    cm = (m.get("champion_manifests") or {}).get("0", {}) or {}
    n_moves = int(r["n_moves"])
    paths = {}
    for mv in rec["moves"]:
        paths[mv["path"]] = paths.get(mv["path"], 0) + 1
    return {
        "schema": SCHEMA,
        "deck_seed": int(deck_seed),
        "replicate": int(replicate),
        "seat0_seed": s0, "seat1_seed": s1,
        "scores": list(r["scores"]),
        # SIGN: positive = seat 0 (Joshua's seat) ahead.
        "margin_seat0_minus_seat1": int(r["margin_seat0_minus_seat1"]),
        "winner_seat": int(r["winner_seat"]),
        "n_moves": n_moves,
        "move_paths": paths,
        "wall_secs": float(r["wall_secs"]),
        "secs_per_move": round(float(r["wall_secs"]) / max(n_moves, 1), 4),
        "deck_hash": m["deck_hash"],
        "leaf_hash": m["leaf_hash"],
        "rules_profile": _W["profile"],
        "execution": _W["execution"],
        "champion_id": cm.get("champion_id"),
        "champion_leaf_hash": (cm.get("leaf_hashes") or {}).get("harness_leaf_hash"),
        # ⚠️ NAMED `_of_record`, NOT `_effective`: the factory manifest records the
        # PRODUCTION.yaml config even when `sims`/`k_dets` override it (a smoke). The
        # two agree iff the override fields below are null — which is the fleet's case.
        "total_sims_of_record": (cm.get("fair_deploy") or {}).get("total_sims"),
        "k_dets_of_record": (cm.get("fair_deploy") or {}).get("k_dets"),
        "sims_override": _W["sims"], "k_dets_override": _W["k_dets"],
        "agent_version": m["agent_version"],
        "archive_file": meta.get("file"),
        "human_margin_seat0_minus_seat1": meta.get("margin_seat0_minus_seat1"),
        "finished_at": time.time(),
        "cell_secs": round(time.time() - t0, 2),
    }


# --------------------------------------------------------------------------- #
# driver                                                                       #
# --------------------------------------------------------------------------- #
def load_done(out_path: Path) -> set[tuple[int, int]]:
    done = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:      # a torn last line from a dirty crash
                continue
            if "deck_seed" in d and "replicate" in d:
                done.add((int(d["deck_seed"]), int(d["replicate"])))
    return done


def build_cells(archives: list[dict], k: int, done: set) -> list[tuple]:
    cells = []
    for rep in range(k):                       # replicate-major: every deck gets
        for a in archives:                     # its 1st replicate before any 2nd,
            key = (a["deck_seed"], rep)        # so a killed run is still balanced.
            if key not in done:
                cells.append((a["deck_seed"], rep, a))
    return cells


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archives", default=str(DEFAULT_ARCHIVES))
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--k", type=int, default=8, help="replicates per deck")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--rust-threads", type=int, default=1)
    ap.add_argument("--sims", type=int, default=None, help="override sims_per_det (SMOKE ONLY)")
    ap.add_argument("--k-dets", type=int, default=None, help="override k_dets (SMOKE ONLY)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="stop after N cells (bench)")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    archives = select_archives(args.archives, args.profile)
    if not archives:
        print(f"[e4-deck-baseline] no {args.profile!r} archives under {args.archives}",
              file=sys.stderr)
        return 2

    done = load_done(out_path) if args.resume else set()
    cells = build_cells(archives, args.k, done)
    if args.limit:
        cells = cells[: args.limit]

    # Export the import-latched env in the PARENT too, so it is inherited by every
    # spawn worker even before the worker's own assertion runs.
    env = export_profile_env(args.profile)

    print(f"[e4-deck-baseline] profile={args.profile} {env} "
          f"decks={len(archives)} k={args.k} workers={args.workers} "
          f"rust_threads={args.rust_threads} done={len(done)} todo={len(cells)}",
          flush=True)
    if not cells:
        print("[e4-deck-baseline] nothing to do (all cells present) — exiting 0", flush=True)
        return 0

    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    t0 = time.time()
    n = 0
    with out_path.open("a") as fh:
        with ctx.Pool(processes=max(1, min(args.workers, len(cells))),
                      initializer=_worker_init,
                      initargs=(args.profile, args.rust_threads, args.sims,
                                args.k_dets)) as pool:
            for rec in pool.imap_unordered(_play_cell, cells):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())          # per-GAME checkpoint (dirty-reboot safe)
                n += 1
                el = time.time() - t0
                print(f"[{n}/{len(cells)}] deck={rec['deck_seed']} rep={rec['replicate']} "
                      f"scores={rec['scores']} margin={rec['margin_seat0_minus_seat1']:+d} "
                      f"{rec['secs_per_move']:.2f} s/move  elapsed={el/60:.1f}m",
                      flush=True)
    print(f"[e4-deck-baseline] DONE {n} games in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
