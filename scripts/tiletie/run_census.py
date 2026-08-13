#!/usr/bin/env python3
"""Leaf top-2 tie-structure census — the driver.

Runs `chain_census.py`'s TILE-decision leaf-tie census over two strata (`e4`
champion plies from the human-vs-champion archives, `selfplay` champion
self-play plies from the CL-070 root bank + a sampled slice of
`champ_games.jsonl`) and writes `rows.jsonl` / `manifest.json` / `summary.json`
/ `CENSUS.md` under the output directory. Leaf evaluations only — NO search, NO
oracle scoring.

WHY A DRIVER WITH ONE SUBPROCESS PER RULES PROFILE. `CARCASSONNE_FIX_R9` is
derived at import time and latched in a Rust `OnceLock`, so the three rules
epochs among the E4 archives (`walled`, `fixed_v1`, `app_aug2`) cannot share a
process (mirrors `scripts/analyzer/run_farmwar.py`, the house pattern: one
subprocess per (leg), each with the latch exported before launch and
re-verified inside). `selfplay` is `walled`-only and rides in the `walled` leg
alongside that leg's E4 archives. Each leg is a re-invocation of THIS script
with `--leg <profile>` (no separate pilot file — the leg logic lives in
`run_leg()` below); inside a leg a `multiprocessing.Pool` (fork context — the
leaf and rules env are already resolved in the leg's own process by the time
the pool forks, so workers inherit them for free) fans out over that leg's
tasks.

Usage
-----
  run_census.py [--out-dir DIR] [--workers 14] [--n-champgames 1200]
                [--sample-seed 20260812] [--max-per-game 4]
                [--limit-e4-games N] [--limit-bank N]   # smoke-test knobs

Internal (one subprocess per profile re-invokes with these; not for humans):
  run_census.py --leg PROFILE --leg-out DIR --workers W [...same corpus flags]
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

E4_DIR_DEFAULT = REPO / "measurement" / "e4_games"
BANK_PATH_DEFAULT = Path("/mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl")
CHAMPGAMES_PATH_DEFAULT = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT_DIR_DEFAULT = REPO / "measurement" / "tiletie_pricing_20260812" / "census"

SCHEMA = "carcassonne-tiletie-census/v1"


# --------------------------------------------------------------------------- #
# worker globals (fork context — set in the leg's own process BEFORE the Pool  #
# forks, so every worker inherits them for free; no pickling of the leaf/cfg   #
# closures is ever required).                                                  #
# --------------------------------------------------------------------------- #
_LEAF = None


# --------------------------------------------------------------------------- #
# small generic utility, copied+adapted from scripts/analyzer/run_farmwar.py's #
# `split_workers` (same signature/algorithm; only the docstring is trimmed).   #
# --------------------------------------------------------------------------- #
def split_workers(counts: dict, total: int) -> dict:
    """Divide `total` workers across concurrent legs IN PROPORTION to their task
    counts, at least 1 each, never more than a leg has tasks. Largest-remainder
    apportionment so the shares sum to `total` exactly (or to `len(profs)` if
    `total < len(profs)` — every leg still gets its floor of 1).

    FIX vs. `run_farmwar.py`'s original (found running this driver at
    workers=8 against 3 legs of wildly different size — 23 vs 1697 vs 1 tasks):
    the original's remainder loop only ever ADDS leftover workers, so when the
    "at least 1" floor is applied independently per leg, the floors can SUM to
    more than `total` (here: fixed_v1 floors 0.107 up to 1, app_aug2 floors
    0.005 up to 1, walled floors DOWN to 7 -- total 9 for a requested 8) and
    nothing claws it back. Added a trim pass below so the requested `total` is
    always a hard cap, not just a target, which matters when a peer box-census
    caps the aggregate worker count.
    """
    profs = sorted(counts)
    n_tot = sum(counts[p] for p in profs)
    if n_tot <= 0:
        return {p: 1 for p in profs}
    total = max(len(profs), int(total))
    exact = {p: total * counts[p] / n_tot for p in profs}
    share = {p: min(counts[p], max(1, int(exact[p]))) for p in profs}
    left = total - sum(share.values())
    order = sorted(profs, key=lambda p: (-(exact[p] - int(exact[p])), p))
    i = 0
    while left > 0 and order:
        p = order[i % len(order)]
        if share[p] < counts[p]:
            share[p] += 1
            left -= 1
        elif all(share[q] >= counts[q] for q in profs):
            break
        i += 1
    # Claw back any overshoot from the floor step, taking from whichever leg
    # currently holds the largest share (it has the most slack) until the sum
    # is back down to `total`, never below 1 per leg.
    over = sum(share.values()) - total
    while over > 0:
        p = max(share, key=lambda q: share[q])
        if share[p] <= 1:
            break                      # every leg already at its floor
        share[p] -= 1
        over -= 1
    return share


def r9_for(profile: str) -> str:
    """"1"/"0" for `CARCASSONNE_FIX_R9`, mirroring run_farmwar.py's `r9_for` —
    deferred import so this module stays stdlib-only until a leg is chosen."""
    from carcassonne_ai import rules_profile
    return "1" if rules_profile.resolve(profile).r9_env_expected else "0"


# --------------------------------------------------------------------------- #
# E4 profile map (top-level driver only; cheap `rules_profile` import, no R9   #
# concerns since no engine/board work happens in the top-level process).       #
# --------------------------------------------------------------------------- #
def e4_profile_map(e4_dir: Path, limit_e4_games=None) -> list:
    """`[(path, profile_name), ...]` in sorted-path order (deterministic), one
    entry per E4 archive, resolved from the archive itself (never assumed)."""
    sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
    sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
    sys.path.insert(0, str(REPO / "scripts" / "level2"))
    sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
    import ev_loss

    paths = sorted(Path(e4_dir).glob("*.json"))
    if limit_e4_games is not None:
        paths = paths[: int(limit_e4_games)]
    out = []
    for p in paths:
        arch = ev_loss.load_archive(p)
        out.append((p, ev_loss.resolve_profile_name(arch)))
    return out


# --------------------------------------------------------------------------- #
# Pool workers — one function per task kind. Module-level (Pool.map pickles    #
# arguments/return values even under fork; the leaf itself is NOT passed —     #
# `_LEAF` is a module global the fork already carries).                        #
# --------------------------------------------------------------------------- #
def _process_e4_game(item: tuple) -> dict:
    """One E4 archive -> every censused champion-TILE-decision ply, stepping the
    game forward ONCE (root_replay's lossless (deck_seed, actions) contract,
    walked manually via `game.get_next_state` rather than re-replayed from
    scratch per ply — GOAL spec's `e4` stratum instruction)."""
    import random

    import numpy as np
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    import chain_census as CC
    import ev_loss
    from carcassonne_ai.game_wrapper import Game

    path_str, game_kwargs, profile = item
    path = Path(path_str)
    arch = ev_loss.load_archive(path)
    deck_seed = int(arch["deck_seed"])
    champ_seat = 1 - int(arch["human_player"])
    actions = arch["actions"]
    n_plies = len(actions)

    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True, **game_kwargs)
    board = game.get_init_board()
    rows = []
    for ply, played in enumerate(actions):
        st = board.state
        if int(st.current_player) == champ_seat and st.phase == GamePhase.TILES:
            legal = np.flatnonzero(game.get_valid_moves(board))
            n_legal = int(legal.size)
            if n_legal >= 2:
                meta = {
                    "stratum": "e4", "source": "e4_games", "rules_profile": profile,
                    # `path.stem` (not `deck_seed`) keys the id: a handful of E4
                    # archives are same-seed REMATCHES (e.g. deck_seed 523563 was
                    # played twice, two different archive files) -- deck_seed alone
                    # is not unique across e4 archives, the archive filename is.
                    "game_label": path.stem, "root_id": f"{path.stem}_p{ply}",
                    "deck_seed": deck_seed, "ply": ply, "n_plies": n_plies,
                    "action_played": int(played),
                }
                rows.append(CC.census_ply(game, board, champ_seat, _LEAF, meta=meta))
        board, _ = game.get_next_state(board, int(played))

    final_scores = [int(x) for x in board.state.scores]
    recorded = arch.get("recorded_scores")
    scores_match = None if not recorded else (final_scores == recorded)
    return {"path": str(path), "rows": rows, "n_qualifying": len(rows),
            "final_scores": final_scores, "recorded_scores": recorded,
            "replay_scores_match": scores_match}


def _process_bank_root(rec: dict) -> dict:
    """One CL-070 bank root (already TILES-phase, `n_legal>=2` by the bank's own
    construction) -> one censused row. Verifies the bank's own checksum contract
    (`adaptive_k_census.py:336-341`'s pattern) — fails loudly on mismatch."""
    import chain_census as CC
    import root_replay as RR

    deck_seed = int(rec["deck_seed"])
    ply = int(rec["ply"])
    actions = rec["actions"]
    game, board = RR.replay_actions(deck_seed, actions, ply)
    checksum = game.string_representation(board)
    if rec.get("checksum") is not None and checksum != rec["checksum"]:
        raise AssertionError(
            f"bank checksum mismatch at deck_seed={deck_seed} ply={ply}: the roots "
            "bank does not reconstruct against this src tree — STOP (this is the "
            "bank's own verification contract, adaptive_k_census.py:336-341)")
    seat = int(board.state.current_player)
    action_played = int(actions[ply]) if ply < len(actions) else None
    meta = {
        "stratum": "selfplay", "source": "bank", "rules_profile": "walled",
        "game_label": f"bank_{deck_seed}", "root_id": f"{deck_seed}_p{ply}",
        "deck_seed": deck_seed, "ply": ply, "n_plies": len(actions),
        "action_played": action_played,
        "h200_top2_q_gap": rec.get("h200_top2_q_gap"),
        "bank_phase_bucket": rec.get("phase_bucket"),
    }
    row = CC.census_ply(game, board, seat, _LEAF, meta=meta)
    if rec.get("k_remaining") is not None and row["k_remaining"] != int(rec["k_remaining"]):
        raise AssertionError(
            f"bank k_remaining mismatch at deck_seed={deck_seed} ply={ply}: recomputed "
            f"{row['k_remaining']} != bank's own recorded {rec['k_remaining']} — the "
            "fair_agent.k_remaining definition or the replay have drifted from the "
            "bank's generation-time tree. STOP.")
    return row


def _census_champgame_plies(rec: dict) -> dict:
    """PASS 1 (no leaf, no search): which plies of one `champ_games.jsonl` game
    are TILE-decision candidates (`phase==TILES`, `n_legal>=2`). Every ply of a
    champion-self-play game is a champion decision (both seats are the champion
    playing itself) — no seat filter, unlike the `e4` stratum."""
    import random

    import numpy as np
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    from carcassonne_ai.game_wrapper import Game

    deck_seed = int(rec["deck_seed"])
    actions = [int(a) for a in rec["actions"]]
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    qualifying = []
    for ply, a in enumerate(actions):
        st = board.state
        if st.phase == GamePhase.TILES:
            n_legal = int(np.count_nonzero(game.get_valid_moves(board)))
            if n_legal >= 2:
                qualifying.append(ply)
        board, _ = game.get_next_state(board, a)
    return {"deck_seed": deck_seed, "game_id": rec.get("game_id", deck_seed),
            "n_plies": len(actions), "qualifying_plies": qualifying}


def _process_champgame_task(item: tuple) -> list:
    """One `champ_games.jsonl` game + its list of SAMPLED plies -> censused rows,
    stepping the game forward ONCE (mirrors `_process_e4_game`)."""
    import random

    import numpy as np
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    import chain_census as CC
    from carcassonne_ai.game_wrapper import Game

    deck_seed, actions, plies_wanted, game_id = item
    wanted = set(int(p) for p in plies_wanted)
    n_plies = len(actions)
    random.seed(deck_seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True)
    board = game.get_init_board()
    rows = []
    for ply, played in enumerate(actions):
        if ply in wanted:
            st = board.state
            if st.phase != GamePhase.TILES:
                raise AssertionError(
                    f"champ_games deck_seed={deck_seed} ply={ply} was sampled as a "
                    "qualifying TILE ply but is not TILES phase on replay -- the PASS-1 "
                    "census and this replay disagree. STOP.")
            seat = int(st.current_player)
            meta = {
                "stratum": "selfplay", "source": "champ_games", "rules_profile": "walled",
                "game_label": f"champ_{game_id}", "root_id": f"{deck_seed}_p{ply}",
                "deck_seed": deck_seed, "ply": ply, "n_plies": n_plies,
                "action_played": int(played),
            }
            rows.append(CC.census_ply(game, board, seat, _LEAF, meta=meta))
        board, _ = game.get_next_state(board, int(played))
    return rows


# --------------------------------------------------------------------------- #
# the leg                                                                      #
# --------------------------------------------------------------------------- #
def run_leg(profile: str, a) -> int:
    global _LEAF
    t_start = time.time()

    import chain_census as CC
    env_resolved = CC.prepare_env(profile)                    # BEFORE any carcassonne_ai import

    from carcassonne_ai import rules_profile
    prof = rules_profile.activate(profile)
    prof_manifest = prof.as_manifest()
    if not prof_manifest["r9_env_ok"]:
        raise RuntimeError(
            f"leg {profile}: R9 latch mismatch (expected {prof.r9_env_expected}, "
            f"observed {prof_manifest['r9_env_observed']}) — the parent driver "
            "exported CARCASSONNE_FIX_R9 wrong for this leg.")

    leaf, cfg, leaf_hashes, bag_close = CC.build_leaf()
    _LEAF = leaf                                               # set BEFORE any Pool() fork

    sys.path.insert(0, str(REPO / "scripts" / "analyzer"))
    sys.path.insert(0, str(REPO / "scripts" / "human_anchor"))
    sys.path.insert(0, str(REPO / "scripts" / "level2"))
    sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
    import ev_loss

    ctx = mp.get_context("fork")
    game_kwargs = prof.game_kwargs()

    e4_all = sorted(Path(a.e4_dir).glob("*.json"))
    if a.limit_e4_games is not None:
        e4_all = e4_all[: int(a.limit_e4_games)]
    e4_tasks = []
    for p in e4_all:
        arch = ev_loss.load_archive(p)
        if ev_loss.resolve_profile_name(arch) == profile:
            e4_tasks.append(p)

    leg_rows: list = []
    e4_stat = {"n_games": 0, "n_rows": 0, "replay_scores_checked": 0,
              "replay_scores_match_count": 0, "per_game": []}
    t0 = time.time()
    if e4_tasks:
        items = [(str(p), game_kwargs, profile) for p in e4_tasks]
        with ctx.Pool(min(int(a.workers), len(items))) as pool:
            results = pool.map(_process_e4_game, items, chunksize=1)
        for r in results:
            leg_rows.extend(r["rows"])
            e4_stat["per_game"].append({
                "path": r["path"], "n_qualifying": r["n_qualifying"],
                "recorded_scores": r["recorded_scores"],
                "final_scores": r["final_scores"],
                "replay_scores_match": r["replay_scores_match"],
            })
            if r["replay_scores_match"] is not None:
                e4_stat["replay_scores_checked"] += 1
                if r["replay_scores_match"]:
                    e4_stat["replay_scores_match_count"] += 1
        e4_stat["n_games"] = len(e4_tasks)
        e4_stat["n_rows"] = sum(r["n_qualifying"] for r in results)
    e4_secs = time.time() - t0

    bank_stat: dict = {}
    champ_stat: dict = {}
    bank_secs = 0.0
    champ_secs = 0.0
    if profile == "walled":
        # ---- selfplay/bank ----------------------------------------------- #
        bank_all_lines = 0
        bank_records = []
        with open(a.bank_path) as fh:
            for line in fh:
                if not line.strip():
                    continue
                bank_all_lines += 1
                rec = json.loads(line)
                if rec.get("phase") == "TILES":
                    bank_records.append(rec)
        n_bank_tiles_total = len(bank_records)
        if a.limit_bank is not None:
            bank_records = bank_records[: int(a.limit_bank)]

        t0 = time.time()
        if bank_records:
            with ctx.Pool(min(int(a.workers), len(bank_records))) as pool:
                bank_rows = pool.map(_process_bank_root, bank_records, chunksize=1)
        else:
            bank_rows = []
        leg_rows.extend(bank_rows)
        bank_secs = time.time() - t0
        bank_stat = {
            "path": str(a.bank_path), "n_lines_total": bank_all_lines,
            "n_tiles_phase_total": n_bank_tiles_total,
            "limit_bank": a.limit_bank, "n_censused": len(bank_rows),
        }
        bank_keys = {(int(r["deck_seed"]), int(r["ply"])) for r in bank_records}

        # ---- selfplay/champ_games ----------------------------------------- #
        champ_games = [json.loads(l) for l in Path(a.champgames_path).read_text().splitlines()
                       if l.strip()]
        t0 = time.time()
        with ctx.Pool(int(a.workers)) as pool:
            per_game_qual = pool.map(_census_champgame_plies, champ_games, chunksize=4)
        n_qualifying_total = 0
        eligible = []
        for gc in per_game_qual:
            for ply in gc["qualifying_plies"]:
                n_qualifying_total += 1
                if (gc["deck_seed"], ply) in bank_keys:
                    continue
                eligible.append((gc["deck_seed"], ply, gc["game_id"]))
        n_deduped = n_qualifying_total - len(eligible)

        rng = random.Random(int(a.sample_seed))
        order = list(range(len(eligible)))
        rng.shuffle(order)
        per_game_count: Counter = Counter()
        picked = []
        for i in order:
            ds, ply, gid = eligible[i]
            if per_game_count[ds] >= int(a.max_per_game):
                continue
            per_game_count[ds] += 1
            picked.append((ds, ply, gid))
            if len(picked) >= int(a.n_champgames):
                break
        picked.sort(key=lambda t: (t[0], t[1]))

        actions_by_seed = {int(g["deck_seed"]): [int(x) for x in g["actions"]] for g in champ_games}
        grouped: dict = defaultdict(list)
        gid_by_seed = {}
        for ds, ply, gid in picked:
            grouped[ds].append(ply)
            gid_by_seed[ds] = gid
        tasks = [(ds, actions_by_seed[ds], sorted(plies), gid_by_seed[ds])
                for ds, plies in grouped.items()]
        if tasks:
            with ctx.Pool(min(int(a.workers), len(tasks))) as pool:
                nested = pool.map(_process_champgame_task, tasks, chunksize=1)
            champ_rows = [row for sub in nested for row in sub]
        else:
            champ_rows = []
        leg_rows.extend(champ_rows)
        champ_secs = time.time() - t0
        champ_stat = {
            "path": str(a.champgames_path), "n_games_source": len(champ_games),
            "n_qualifying_plies_total": n_qualifying_total,
            "n_deduped_against_bank": n_deduped,
            "n_eligible_after_dedupe": len(eligible),
            "target_n": int(a.n_champgames), "n_sampled": len(picked),
            "n_games_sampled_from": len(grouped), "n_censused": len(champ_rows),
            "sample_seed": int(a.sample_seed), "max_per_game": int(a.max_per_game),
        }

    leg_out = Path(a.leg_out)
    leg_out.mkdir(parents=True, exist_ok=True)
    with (leg_out / "rows.jsonl").open("w") as fh:
        for row in leg_rows:
            fh.write(json.dumps(row) + "\n")

    leg_manifest = {
        "schema": SCHEMA + "-leg",
        "profile": profile,
        "r9_env_var": prof_manifest["r9_env_var"],
        "r9_env_expected": prof_manifest["r9_env_expected"],
        "r9_env_observed": prof_manifest["r9_env_observed"],
        "r9_env_ok": prof_manifest["r9_env_ok"],
        "env_resolved": env_resolved,
        "leaf_hashes": leaf_hashes,
        "leaf_hash_of_record": CC.LEAF_HASH_OF_RECORD,
        "leaf_hash_assert_ok": leaf_hashes.get("harness_leaf_hash") == CC.LEAF_HASH_OF_RECORD,
        "n_rows": len(leg_rows),
        "workers": int(a.workers),
        "e4": e4_stat,
        "bank": bank_stat,
        "champ_games": champ_stat,
        "wall_secs": {"e4": round(e4_secs, 1), "bank": round(bank_secs, 1),
                     "champ_games": round(champ_secs, 1),
                     "total": round(time.time() - t_start, 1)},
    }
    (leg_out / "leg_manifest.json").write_text(json.dumps(leg_manifest, indent=2))
    print(f"[run_census][{profile}] {len(leg_rows)} rows "
          f"(e4={e4_stat['n_rows']}, bank={bank_stat.get('n_censused', 0)}, "
          f"champ_games={champ_stat.get('n_censused', 0)}) -> {leg_out/'rows.jsonl'} "
          f"in {leg_manifest['wall_secs']['total']}s", flush=True)
    return 0


# --------------------------------------------------------------------------- #
# summary tables (GOAL CENSUS.md items 1-6)                                    #
# --------------------------------------------------------------------------- #
def wilson_ci(k: int, n: int, z: float = 1.959963984540054):
    """95% Wilson score interval for a binomial proportion. `None` for n==0."""
    if n <= 0:
        return (None, None)
    k = float(k); n = float(n)
    phat = k / n
    denom = 1.0 + z * z / n
    center = phat + z * z / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    lo = max(0.0, (center - margin) / denom)
    hi = min(1.0, (center + margin) / denom)
    return (lo, hi)


TIE_SIZE_BUCKETS = ("2", "3", "4", "5", "6", "7", "8", "9-12", "13+")


def _tie_size_bucket(size: int) -> str:
    if size <= 8:
        return str(size)
    if size <= 12:
        return "9-12"
    return "13+"


def _quantiles(vals: list, qs=(0.0, 0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 1.0)) -> dict:
    if not vals:
        return {str(q): None for q in qs}
    s = sorted(vals)
    n = len(s)
    out = {}
    for q in qs:
        if n == 1:
            out[str(q)] = s[0]
            continue
        pos = q * (n - 1)
        lo = int(math.floor(pos))
        hi = int(math.ceil(pos))
        frac = pos - lo
        out[str(q)] = s[lo] + (s[hi] - s[lo]) * frac
    return out


def group_summary(rows: list) -> dict:
    """The metrics for ONE group of rows (a stratum/source/profile slice, or a
    pooled union). GOAL CENSUS.md tables 1-5, minus the phase/tercile/n_legal
    split (table 4) which cuts ACROSS groups and is built separately."""
    n = len(rows)
    out = {"n": n}
    if n == 0:
        return out

    n_exact = sum(1 for r in rows if r["tie_exact"])
    lo, hi = wilson_ci(n_exact, n)
    out["exact_tie_rate"] = {"k": n_exact, "n": n, "rate": n_exact / n,
                             "ci95_lo": lo, "ci95_hi": hi}

    by_eps = {}
    for eps_key in rows[0]["by_eps"]:
        k = sum(1 for r in rows if r["by_eps"][eps_key]["tie"])
        lo, hi = wilson_ci(k, n)
        by_eps[eps_key] = {"k": k, "n": n, "rate": k / n, "ci95_lo": lo, "ci95_hi": hi}
    out["by_eps"] = by_eps

    # table 2 — tied-set SIZE distribution (exact ties only)
    tied = [r for r in rows if r["tie_exact"]]
    sizes = [r["tie_size_exact"] for r in tied]
    hist = Counter(_tie_size_bucket(s) for s in sizes)
    out["tie_size_hist"] = {
        "n_tied": len(tied),
        "counts": {b: hist.get(b, 0) for b in TIE_SIZE_BUCKETS},
        "mean": (sum(sizes) / len(sizes)) if sizes else None,
        "median": (sorted(sizes)[len(sizes) // 2] if sizes else None),
        "pct_size2": (hist.get("2", 0) / len(tied)) if tied else None,
        "pct_size_ge5": (sum(hist.get(b, 0) for b in ("5", "6", "7", "8", "9-12", "13+"))
                         / len(tied)) if tied else None,
    }

    # table 3 — top-2 gap distribution among NON-exact-tie plies
    non_tied = [r for r in rows if not r["tie_exact"] and r["gap"] is not None]
    gaps = [r["gap"] for r in non_tied]
    out["gap_quantiles_non_tied"] = {"n": len(gaps), **_quantiles(gaps)}
    # the lattice: top-20 most common EXACT gap values (any row with a gap, incl.
    # ties would be gap==0 trivially — so this is computed over non-tied rows,
    # which is where a non-trivial gap value exists at all).
    gap_counts = Counter(gaps)
    out["gap_top20"] = [{"gap": g, "count": c} for g, c in gap_counts.most_common(20)]

    # table 5 — played-move location relative to the leaf's tie set
    with_played = [r for r in rows if r["action_played"] is not None]
    n_p = len(with_played)
    if n_p:
        n_in_tieset = sum(1 for r in with_played if r["played_in_tieset_exact"])
        n_argmax = sum(1 for r in with_played if r["played_is_argmax"])
        lo1, hi1 = wilson_ci(n_in_tieset, n_p)
        lo2, hi2 = wilson_ci(n_argmax, n_p)
        out["played_in_tieset_exact_rate"] = {"k": n_in_tieset, "n": n_p,
                                              "rate": n_in_tieset / n_p,
                                              "ci95_lo": lo1, "ci95_hi": hi1}
        out["played_is_argmax_rate"] = {"k": n_argmax, "n": n_p, "rate": n_argmax / n_p,
                                        "ci95_lo": lo2, "ci95_hi": hi2}
    else:
        out["played_in_tieset_exact_rate"] = {"k": 0, "n": 0, "rate": None}
        out["played_is_argmax_rate"] = {"k": 0, "n": 0, "rate": None}

    return out


def n_legal_quartile_cuts(rows: list) -> list:
    vals = sorted(r["n_legal"] for r in rows)
    if not vals:
        return [0, 0, 0]
    n = len(vals)

    def pct(q):
        pos = q * (n - 1)
        lo = int(math.floor(pos)); hi = int(math.ceil(pos))
        frac = pos - lo
        return vals[lo] + (vals[hi] - vals[lo]) * frac
    return [pct(0.25), pct(0.50), pct(0.75)]


def n_legal_quartile_bucket(n_legal: int, cuts: list) -> str:
    q1, q2, q3 = cuts
    if n_legal <= q1:
        return "Q1 (<=%.0f)" % q1
    if n_legal <= q2:
        return "Q2 (<=%.0f)" % q2
    if n_legal <= q3:
        return "Q3 (<=%.0f)" % q3
    return "Q4 (>%.0f)" % q3


def phase_trend(rows: list) -> dict:
    """table 4 — exact-tie rate + mean tied size by phase_bucket, by tercile, and
    by n_legal quartile (pooled over the group `rows` belong to)."""
    def _agg(key_fn, order=None):
        buckets: dict = defaultdict(list)
        for r in rows:
            buckets[key_fn(r)].append(r)
        keys = order if order is not None else sorted(buckets)
        out = {}
        for k in keys:
            grp = buckets.get(k, [])
            if not grp:
                out[str(k)] = {"n": 0, "exact_tie_rate": None, "mean_tie_size": None}
                continue
            n_exact = sum(1 for r in grp if r["tie_exact"])
            sizes = [r["tie_size_exact"] for r in grp if r["tie_exact"]]
            out[str(k)] = {
                "n": len(grp), "exact_tie_rate": n_exact / len(grp),
                "mean_tie_size": (sum(sizes) / len(sizes)) if sizes else None,
            }
        return out

    cuts = n_legal_quartile_cuts(rows)
    return {
        "by_phase_bucket": _agg(lambda r: r["phase_bucket"], order=("early", "mid", "late")),
        "by_tercile": _agg(lambda r: r["tercile"], order=(0, 1, 2)),
        "by_n_legal_quartile": _agg(lambda r: n_legal_quartile_bucket(r["n_legal"], cuts),
                                    order=None),
        "n_legal_quartile_cuts": cuts,
    }


def build_summary(rows: list) -> dict:
    groups: dict = {}
    key_fn = lambda r: (r["stratum"], r["source"], r["rules_profile"])  # noqa: E731
    by_key: dict = defaultdict(list)
    for r in rows:
        by_key[key_fn(r)].append(r)

    for (stratum, source, profile), grp in sorted(by_key.items()):
        gk = f"{stratum}|{source}|{profile}"
        groups[gk] = {**group_summary(grp), "phase_trend": phase_trend(grp),
                     "stratum": stratum, "source": source, "rules_profile": profile}

    # convenience unions
    for stratum in ("e4", "selfplay"):
        grp = [r for r in rows if r["stratum"] == stratum]
        if grp:
            gk = f"{stratum}|ALL|ALL"
            groups[gk] = {**group_summary(grp), "phase_trend": phase_trend(grp),
                         "stratum": stratum, "source": "ALL", "rules_profile": "ALL"}
    groups["ALL|ALL|ALL"] = {**group_summary(rows), "phase_trend": phase_trend(rows),
                             "stratum": "ALL", "source": "ALL", "rules_profile": "ALL"}

    return {"schema": SCHEMA + "-summary", "n_rows_total": len(rows), "groups": groups}


# --------------------------------------------------------------------------- #
# CENSUS.md                                                                    #
# --------------------------------------------------------------------------- #
def _fmt_rate(d) -> str:
    if not d or d.get("rate") is None:
        return "n/a"
    lo, hi = d.get("ci95_lo"), d.get("ci95_hi")
    if lo is None:
        return f"{d['rate']*100:.1f}% ({d['k']}/{d['n']})"
    return f"{d['rate']*100:.1f}% [{lo*100:.1f}, {hi*100:.1f}] ({d['k']}/{d['n']})"


def _order_groups(groups: dict) -> list:
    """Report order: e4 by profile, then selfplay/bank, selfplay/champ_games,
    then the union rows, matching the GOAL spec's "split by stratum ... AND by
    rules profile"."""
    priority = {"e4": 0, "selfplay": 1, "ALL": 2}
    def key(item):
        gk, g = item
        return (priority.get(g["stratum"], 9), g["source"], g["rules_profile"])
    return sorted(groups.items(), key=key)


def write_census_md(summary: dict, manifest: dict, path: Path) -> None:
    groups = summary["groups"]
    lines = []
    lines.append("# TILE-decision leaf top-2 tie census — CENSUS.md")
    lines.append("")
    lines.append(f"Generated {manifest['finished_utc']} · git `{manifest['git_rev']}` · "
                f"leaf hash `{manifest['leaf_hash_of_record']}` "
                f"(assert {'OK' if manifest['leaf_hash_assert_ok'] else 'FAILED'}) · "
                f"{summary['n_rows_total']} rows total.")
    lines.append("")
    mean_secs = manifest.get("mean_secs_per_ply")
    lines.append(f"Wall clock: {manifest['wall_secs_total']}s total "
                f"({manifest['workers_total']} workers, "
                f"split {manifest['worker_split']}) · mean seconds/ply (leaf compute only) "
                f"= {mean_secs}.")
    if manifest.get("contention_note"):
        lines.append("")
        lines.append(f"> **Timing caveat:** {manifest['contention_note']}")
    lines.append("")
    lines.append("Question: does the JCZ corpus's reported top-2 exact-tie rate of "
                "**55.1%** (7,817/14,190, `scripts/jcz_mining/mine_disagreements.py`) "
                "replicate on our own position distributions?")
    lines.append("")

    lines.append("## 1. Exact-tie rate (and the full `TIE_EPS_GRID`)")
    lines.append("")
    lines.append("| group | n | exact tie (eps=0.0) 95% CI | eps=0.05 | eps=0.2 | eps=0.5 | eps=1.0 |")
    lines.append("|---|---:|---|---|---|---|---|")
    for gk, g in _order_groups(groups):
        if g["n"] == 0:
            lines.append(f"| {gk} | 0 | n/a | n/a | n/a | n/a | n/a |")
            continue
        be = g["by_eps"]
        lines.append(f"| {gk} | {g['n']} | {_fmt_rate(g['exact_tie_rate'])} | "
                    f"{_fmt_rate(be.get('0.05'))} | {_fmt_rate(be.get('0.2'))} | "
                    f"{_fmt_rate(be.get('0.5'))} | {_fmt_rate(be.get('1.0'))} |")
    lines.append("")
    replicated = []
    for gk, g in _order_groups(groups):
        if g["n"] == 0 or g["source"] == "ALL":
            continue
        r = g["exact_tie_rate"]["rate"]
        lo, hi = g["exact_tie_rate"]["ci95_lo"], g["exact_tie_rate"]["ci95_hi"]
        verdict = "REPLICATES" if (lo is not None and lo <= 0.551 <= hi) else \
                  ("HIGHER" if r > 0.551 else "LOWER")
        replicated.append(f"- `{gk}`: {r*100:.1f}% vs JCZ 55.1% -> **{verdict}**")
    lines.append("\n".join(replicated))
    lines.append("")

    lines.append("## 2. Tied-set SIZE distribution (exact ties only)")
    lines.append("")
    lines.append("| group | n_tied | mean | median | " +
                " | ".join(f"size={b}" for b in TIE_SIZE_BUCKETS) + " |")
    lines.append("|---|---:|---:|---:|" + "---:|" * len(TIE_SIZE_BUCKETS))
    for gk, g in _order_groups(groups):
        h = g.get("tie_size_hist")
        if not h or h["n_tied"] == 0:
            lines.append(f"| {gk} | 0 | n/a | n/a |" + " n/a |" * len(TIE_SIZE_BUCKETS))
            continue
        counts = " | ".join(str(h["counts"][b]) for b in TIE_SIZE_BUCKETS)
        lines.append(f"| {gk} | {h['n_tied']} | {h['mean']:.2f} | {h['median']} | {counts} |")
    lines.append("")
    lines.append("(pct at size 2 vs size >=5, ALL|ALL|ALL): "
                f"{groups['ALL|ALL|ALL']['tie_size_hist']['pct_size2']*100:.1f}% vs "
                f"{groups['ALL|ALL|ALL']['tie_size_hist']['pct_size_ge5']*100:.1f}%"
                if groups["ALL|ALL|ALL"]["tie_size_hist"]["n_tied"] else "(no ties censused)")
    lines.append("")

    lines.append("## 3. Top-2 gap distribution among NON-exact-tie plies")
    lines.append("")
    lines.append("| group | n | min | p1 | p5 | p10 | p25 | p50 | p75 | p90 | max |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for gk, g in _order_groups(groups):
        q = g.get("gap_quantiles_non_tied")
        if not q or q["n"] == 0:
            lines.append(f"| {gk} | 0 |" + " n/a |" * 9)
            continue
        vals = [q["0.0"], q["0.01"], q["0.05"], q["0.1"], q["0.25"], q["0.5"], q["0.75"],
               q["0.9"], q["1.0"]]
        lines.append(f"| {gk} | {q['n']} | " + " | ".join(f"{v:.4f}" for v in vals) + " |")
    lines.append("")
    lines.append("**Top-20 most common exact gap values (`ALL|ALL|ALL`)** — the lattice:")
    lines.append("")
    lines.append("| gap value | count |")
    lines.append("|---:|---:|")
    for item in groups["ALL|ALL|ALL"].get("gap_top20", [])[:20]:
        lines.append(f"| {item['gap']:.6f} | {item['count']} |")
    lines.append("")

    lines.append("## 4. Phase trend — exact-tie rate + mean tied size")
    lines.append("")
    for gk, g in _order_groups(groups):
        if g["n"] == 0:
            continue
        pt = g["phase_trend"]
        lines.append(f"**{gk}** (n={g['n']})")
        lines.append("")
        lines.append("| axis | bucket | n | exact-tie rate | mean tied size |")
        lines.append("|---|---|---:|---:|---:|")
        for bucket, d in pt["by_phase_bucket"].items():
            r = "n/a" if d["exact_tie_rate"] is None else f"{d['exact_tie_rate']*100:.1f}%"
            m = "n/a" if d["mean_tie_size"] is None else f"{d['mean_tie_size']:.2f}"
            lines.append(f"| phase_bucket | {bucket} | {d['n']} | {r} | {m} |")
        for bucket, d in pt["by_tercile"].items():
            r = "n/a" if d["exact_tie_rate"] is None else f"{d['exact_tie_rate']*100:.1f}%"
            m = "n/a" if d["mean_tie_size"] is None else f"{d['mean_tie_size']:.2f}"
            lines.append(f"| tercile | {bucket} | {d['n']} | {r} | {m} |")
        for bucket, d in pt["by_n_legal_quartile"].items():
            r = "n/a" if d["exact_tie_rate"] is None else f"{d['exact_tie_rate']*100:.1f}%"
            m = "n/a" if d["mean_tie_size"] is None else f"{d['mean_tie_size']:.2f}"
            lines.append(f"| n_legal quartile | {bucket} | {d['n']} | {r} | {m} |")
        lines.append("")

    lines.append("## 5. `played_in_tieset_exact` / `played_is_argmax`")
    lines.append("")
    lines.append("| group | n (with action_played) | played in exact tie-set | played == argmax |")
    lines.append("|---|---:|---|---|")
    for gk, g in _order_groups(groups):
        pit = g.get("played_in_tieset_exact_rate", {})
        pia = g.get("played_is_argmax_rate", {})
        n_p = pit.get("n", 0)
        lines.append(f"| {gk} | {n_p} | {_fmt_rate(pit)} | {_fmt_rate(pia)} |")
    lines.append("")

    lines.append("## 6. What this census does NOT show")
    lines.append("")
    lines.append("This is a **leaf-silence** census: it counts how often the production leaf "
                "assigns the SAME value to the top TILE placement(s), and how big that tied "
                "set is. It says **nothing** about whether the tied moves differ in true VALUE "
                "— a leaf tie is consistent with the tied moves being genuinely "
                "equally good, or with the leaf being blind to a real difference between "
                "them. Answering that requires an oracle/search-based scoring pass over the "
                "tied moves, which this census deliberately does not run (leaf evaluations "
                "only, no search, no oracle scoring — see the GOAL spec this census answers "
                "to).")
    lines.append("")

    path.write_text("\n".join(lines))


# --------------------------------------------------------------------------- #
# top-level driver                                                             #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT))
    ap.add_argument("--e4-dir", default=str(E4_DIR_DEFAULT))
    ap.add_argument("--bank-path", default=str(BANK_PATH_DEFAULT))
    ap.add_argument("--champgames-path", default=str(CHAMPGAMES_PATH_DEFAULT))
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--n-champgames", type=int, default=1200,
                    help="target sampled TILE-decision plies from champ_games.jsonl "
                         "(the ADJUSTABLE volume knob — the bank's 495 and all E4 "
                         "plies are mandatory)")
    ap.add_argument("--sample-seed", type=int, default=20260812)
    ap.add_argument("--max-per-game", type=int, default=4)
    ap.add_argument("--limit-e4-games", type=int, default=None, help="smoke-test knob")
    ap.add_argument("--limit-bank", type=int, default=None, help="smoke-test knob")
    ap.add_argument("--contention-note", default=None,
                    help="free-text timing caveat recorded verbatim in manifest.json and "
                         "rendered in CENSUS.md (e.g. box-contention disclosure) -- the "
                         "tie RATES/SIZES are unaffected (deterministic leaf arithmetic), "
                         "only the wall-clock/secs-per-ply figures would be")
    # internal — one subprocess per profile re-invokes with these
    ap.add_argument("--leg", default=None, choices=["walled", "fixed_v1", "app_aug2"])
    ap.add_argument("--leg-out", default=None)
    return ap


def main(argv=None) -> int:
    ap = build_arg_parser()
    a = ap.parse_args(argv)

    if a.leg:
        return run_leg(a.leg, a)

    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    e4_map = e4_profile_map(Path(a.e4_dir), a.limit_e4_games)
    e4_counts = Counter(profile for _p, profile in e4_map)
    n_bank_est = int(a.limit_bank) if a.limit_bank is not None else 495
    counts = dict(e4_counts)
    counts["walled"] = counts.get("walled", 0) + n_bank_est + int(a.n_champgames)
    profiles_needed = sorted(counts)
    shares = split_workers(counts, int(a.workers))

    print(f"[run_census] E4 archives by profile: {dict(e4_counts)} "
          f"(limit_e4_games={a.limit_e4_games})", flush=True)
    print(f"[run_census] leg task-count estimate {counts}, worker split {shares} "
          f"of {a.workers}", flush=True)

    t0 = time.time()
    procs = []
    for profile in profiles_needed:
        leg_out = out_dir / f"leg_{profile}"
        leg_out.mkdir(parents=True, exist_ok=True)
        log_path = leg_out / "leg.log"
        env = dict(os.environ)
        env["CARCASSONNE_FIX_R9"] = r9_for(profile)
        env.setdefault("OPENBLAS_NUM_THREADS", "1")
        env.setdefault("OMP_NUM_THREADS", "1")
        env.setdefault("MKL_NUM_THREADS", "1")
        cmd = ["nice", "-n", "19", sys.executable, "-u", str(HERE / "run_census.py"),
              "--leg", profile, "--leg-out", str(leg_out),
              "--workers", str(shares[profile]),
              "--e4-dir", str(a.e4_dir), "--bank-path", str(a.bank_path),
              "--champgames-path", str(a.champgames_path),
              "--n-champgames", str(a.n_champgames),
              "--sample-seed", str(a.sample_seed),
              "--max-per-game", str(a.max_per_game)]
        if a.limit_e4_games is not None:
            cmd += ["--limit-e4-games", str(a.limit_e4_games)]
        if a.limit_bank is not None:
            cmd += ["--limit-bank", str(a.limit_bank)]
        fh = log_path.open("w")
        p = subprocess.Popen(cmd, cwd=str(REPO), env=env, stdout=fh, stderr=subprocess.STDOUT)
        print(f"[run_census] launched leg {profile} (R9={env['CARCASSONNE_FIX_R9']}, "
              f"W={shares[profile]}, task_est={counts[profile]}) -> {log_path}", flush=True)
        procs.append({"profile": profile, "t0": time.time(), "fh": fh, "p": p,
                      "leg_out": leg_out, "log": log_path})

    legs = []
    failures = []
    for item in procs:
        rc = item["p"].wait()
        item["fh"].close()
        wall = round(time.time() - item["t0"], 1)
        legs.append({"profile": item["profile"], "rc": rc, "wall_secs": wall,
                    "leg_out": str(item["leg_out"]), "log": str(item["log"])})
        print(f"[run_census] leg {item['profile']} done rc={rc} ({wall}s)", flush=True)
        if rc != 0:
            failures.append({"profile": item["profile"], "rc": rc, "log": str(item["log"])})

    # ---- merge ------------------------------------------------------------- #
    all_rows = []
    per_leg_manifests = {}
    replay_checksum_pass = 0
    replay_checksum_total = 0
    for leg in legs:
        leg_out = Path(leg["leg_out"])
        rows_path = leg_out / "rows.jsonl"
        if rows_path.exists():
            with rows_path.open() as fh:
                for line in fh:
                    if line.strip():
                        all_rows.append(json.loads(line))
        man_path = leg_out / "leg_manifest.json"
        if man_path.exists():
            lm = json.loads(man_path.read_text())
            per_leg_manifests[leg["profile"]] = lm
            replay_checksum_total += lm.get("bank", {}).get("n_censused", 0)
            replay_checksum_pass += lm.get("bank", {}).get("n_censused", 0)  # any failure raised, so all-pass or the leg's rc!=0

    (out_dir / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in all_rows))

    def _git_rev():
        try:
            return subprocess.check_output(
                ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                text=True).strip()
        except Exception as exc:                                   # noqa: BLE001
            return f"UNKNOWN ({exc})"

    n_by_group = Counter((r["stratum"], r["source"], r["rules_profile"]) for r in all_rows)
    n_ply_secs = [r["secs"] for r in all_rows if r.get("secs") is not None]
    mean_secs = (sum(n_ply_secs) / len(n_ply_secs)) if n_ply_secs else None

    manifest = {
        "schema": SCHEMA + "-manifest",
        "goal": "leaf top-2 tie census at TILE decisions -- leaf evaluations only, "
               "no search, no oracle scoring",
        "leaf_hash_of_record": per_leg_manifests.get("walled", {}).get(
            "leaf_hash_of_record",
            next(iter(per_leg_manifests.values()), {}).get("leaf_hash_of_record")),
        "leaf_hash_assert_ok": all(m.get("leaf_hash_assert_ok") for m in per_leg_manifests.values()),
        "git_rev": _git_rev(),
        "python": sys.version,
        "n_rows_total": len(all_rows),
        "n_by_group": {f"{s}|{src}|{p}": n for (s, src, p), n in sorted(n_by_group.items())},
        "e4_profile_counts": dict(e4_counts),
        "leg_task_count_estimate": counts,
        "worker_split": shares,
        "workers_total": int(a.workers),
        "sample_seed": int(a.sample_seed), "n_champgames_target": int(a.n_champgames),
        "max_per_game": int(a.max_per_game),
        "limit_e4_games": a.limit_e4_games, "limit_bank": a.limit_bank,
        "source_paths": {
            "e4_dir": str(a.e4_dir), "bank_path": str(a.bank_path),
            "champgames_path": str(a.champgames_path),
        },
        "per_profile_r9": {p: {"expected": m.get("r9_env_expected"),
                               "observed": m.get("r9_env_observed"),
                               "ok": m.get("r9_env_ok")}
                          for p, m in per_leg_manifests.items()},
        "per_leg_env_resolved": {p: m.get("env_resolved") for p, m in per_leg_manifests.items()},
        "legs": legs,
        "failures": failures,
        "wall_secs_total": round(time.time() - t0, 1),
        "mean_secs_per_ply": mean_secs,
        "contention_note": a.contention_note,
        "per_leg_manifests": per_leg_manifests,
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    summary = build_summary(all_rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    write_census_md(summary, manifest, out_dir / "CENSUS.md")

    print(f"\n[run_census] DONE: {len(all_rows)} rows, {len(legs)} legs, "
          f"{manifest['wall_secs_total']}s wall, mean secs/ply "
          f"(leaf compute only) = {mean_secs}", flush=True)
    print(f"[run_census] -> {out_dir}", flush=True)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
