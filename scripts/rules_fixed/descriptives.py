#!/usr/bin/env python3
"""F9 Phase C — the decision-density descriptive (docs/F9_BUILD_SPEC_20260802.md §3).

The spec's C-full table lists three descriptives and says of this one: **"no
instrument exists"**. This is that instrument. It answers, for one champion-play
corpus: how many decisions does a game actually contain, how many of them are
*searched* (more than one legal action) rather than forced, how wide is the
branching, and when are meeples committed — all split by game phase.

    scripts/rules_fixed/descriptives.py CORPUS [-o OUT.json] [--markdown OUT.md] \
        [--label L] [--rules-profile NAME] [--workers 4] [--limit N]

CORPUS is either

  * a `gen_fair_distill.py --actions-only` output DIR (`manifest.json` +
    `actions/seed_*.json`, one root_replay GameRecord per file) — e.g.
    `/mnt/c/carc-shared/f9_wall_probe_20260802/fixed_v1/`; or
  * a games JSONL (the root_replay contract) — e.g.
    `measurement/champ_action_logs/champ_games.jsonl`.

Both are handled by the same code path; the only difference is where the
manifest lives and how the records are read.

## It is a REPLAY, not a search (and that is the whole cost argument)

Every number here comes from `(deck_seed, actions)` replay through the
`scripts/measurement_infra/root_replay` contract — the engine consumes the global
random stream only in the deck shuffle, so the recorded action sequence
reconstructs the exact game. No MCTS, no leaf eval, no network. ~0.1 s/game.

## RULES PROFILE — read from the corpus, never assumed

A corpus generated under `centered18` or `fixed_v1` replays to a DIFFERENT game
under `walled` (the start tile sits elsewhere, the wall denies different
placements, the cloister scan and the draw rule differ), and the failure is
silent: the actions decode, the replay runs, the numbers are wrong. So the
profile is read from the corpus manifest (`rules_profile.name`), published to the
environment BEFORE the engine is imported — `game_wrapper.Game` resolves
`rules_profile.active()` for anything the caller left unsaid — and re-verified on
the constructed `Game`. An explicit `--rules-profile` that disagrees with the
manifest is a hard error, not an override.

**R9 rides outside the profile** (`CARCASSONNE_FIX_R9`): `base_deck` derives the
farm data at IMPORT time and the Rust registry latches a `OnceLock`, so it can
only be set before the first import. This script therefore sets it from the
corpus manifest's `rules_profile.r9_env_observed` before importing anything, and
then asserts the latch (`base_deck.R9_FIELD_ON_CITY_EDGE_FIX`) came up the way
the corpus was generated. A `fixed_v1` corpus whose manifest says `r9_env_ok:
false` is refused outright — its farm scoring is the unfixed data whatever the
profile name says.

## Descriptive only — Gate C

No claim id, no band, no results.csv row, no PRODUCTION.yaml. The metric set is
fixed by the spec before any corpus was looked at; `run_phase_c.py` reports every
metric side by side regardless of direction.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

SCHEMA = "carcassonne-f9-decision-density/v1"


def _use_repo_tree() -> None:
    """Put THIS tree's src/ + engine/ ahead of the editable install.

    The venv is editable-installed against the main checkout, so a worktree run
    would otherwise import the main tree's engine. (CLAUDE.md worktree-isolation
    rule; harmless in the main tree.)
    """
    for sub in ("src", "engine", "scripts/measurement_infra"):
        p = str(REPO / sub)
        if p not in sys.path:
            sys.path.insert(0, p)

DEFINITIONS = {
    "replay": "Pure (deck_seed, actions) replay via scripts/measurement_infra/root_replay "
              "under the corpus's own rules profile. No search, no leaf eval, no net.",
    "ply": "One recorded action. A turn is a TILES ply followed (usually) by a MEEPLES ply.",
    "decision": "A ply at which the agent had to choose. `searched` = >=2 legal actions "
                "(the search actually ran over alternatives); `forced` = exactly 1 legal "
                "action (no choice existed, whatever the agent spent on it).",
    "tile_pass_ply": "A TILES-phase ply whose played action is the tile-phase PassAction — "
                     "the engine's unplaceable-tile path (A3's subject matter). Counted "
                     "separately from placements.",
    "legal_actions": "int(get_valid_moves(board).sum()) at the ply, i.e. the branching "
                     "factor the agent faced, in the window-relative action space.",
    "tercile": "early/mid/late by thirds of THIS game's TILE-ply count (tiles placed). A "
               "meeple ply inherits the tercile of the tile ply it follows. Matches "
               "scripts/analyzer/replay_stats.tercile's convention (thirds of the game's "
               "own length), keyed on tiles rather than turns so the two corpora are "
               "comparable when one of them redraws.",
    "meeple_commit": "A MEEPLES-phase ply whose action is not the meeple-phase pass: "
                     "`normal` (city/road side), `monk` (CENTER = cloister) or `farmer` "
                     "(one of the four corner slots).",
    "meeples_free": "state.meeples[player] — the supply still in hand, summed over both "
                    "seats (14 at the start of a 2-player game).",
    "replay_scores_match": "The replayed terminal scores equal the scores recorded by the "
                           "generator. False anywhere means format/profile drift — the run "
                           "fails loudly rather than reporting.",
}

TERCILES = ("early", "mid", "late")
PLY_KINDS = ("tile", "meeple")


# --------------------------------------------------------------------------- #
# corpus loading — the two on-disk shapes, one representation                   #
# (json only; deliberately no engine import, because the profile/R9 environment #
#  must be published BEFORE anything imports base_deck)                         #
# --------------------------------------------------------------------------- #
class CorpusFormatError(RuntimeError):
    """The corpus is not a shape this instrument can read. Always raised."""


def _read_json(p: Path):
    try:
        return json.loads(Path(p).read_text())
    except Exception as e:  # noqa: BLE001 - context matters more than the type
        raise CorpusFormatError(f"unreadable JSON at {p}: {e}") from None


def load_corpus(path, limit: int = 0) -> dict:
    """Read a corpus DIR or JSONL into {kind, path, manifest, games:[record...]}.

    `games` records are the root_replay GameRecord dict shape:
    {game_id, deck_seed, actions, n_plies, ...meta}.
    """
    p = Path(path)
    if p.is_dir():
        mf = p / "manifest.json"
        adir = p / "actions"
        if not adir.is_dir():
            raise CorpusFormatError(
                f"{p} is a directory but has no actions/ subdir — a "
                "`gen_fair_distill.py --actions-only` corpus is expected")
        manifest = _read_json(mf) if mf.exists() else {}
        files = sorted(adir.glob("seed_*.json"))
        if not files:
            raise CorpusFormatError(f"no actions/seed_*.json under {p}")
        if limit:
            files = files[:limit]
        games = [_read_json(f) for f in files]
        kind = "gen_fair_distill_dir"
    elif p.is_file():
        manifest = {}
        for cand in (p.parent / "CORPUS_MANIFEST.json", p.parent / "manifest.json"):
            if cand.exists():
                manifest = _read_json(cand)
                break
        games = []
        for line in p.read_text().splitlines():
            if line.strip():
                games.append(json.loads(line))
                if limit and len(games) >= limit:
                    break
        if not games:
            raise CorpusFormatError(f"no records in {p}")
        kind = "games_jsonl"
    else:
        raise CorpusFormatError(f"no such corpus: {p}")

    for g in games:
        if "actions" not in g or ("deck_seed" not in g and "seed" not in g):
            raise CorpusFormatError(
                f"record without actions/deck_seed in {p} (keys: {sorted(g)[:8]})")
        g.setdefault("deck_seed", g.get("seed"))
        g.setdefault("game_id", g["deck_seed"])
    return {"kind": kind, "path": str(p), "manifest": manifest, "games": games}


def resolve_corpus_profile(corpus: dict, cli_profile: str | None) -> dict:
    """Decide which rules profile this corpus must be replayed under.

    Returns {name, source, r9_expected, r9_observed, manifest_block}. Fails loud
    on a manifest/CLI disagreement and on a corpus whose own `r9_env_ok` is False.
    """
    block = dict((corpus.get("manifest") or {}).get("rules_profile") or {})
    mf_name = block.get("name")
    if mf_name and cli_profile and cli_profile != mf_name:
        raise CorpusFormatError(
            f"--rules-profile {cli_profile!r} disagrees with the corpus manifest "
            f"({mf_name!r}). The manifest is the truth about how the games were "
            "generated; replaying under another profile decodes a different game. "
            "Refusing.")
    if block.get("r9_env_ok") is False:
        raise CorpusFormatError(
            "corpus manifest says rules_profile.r9_env_ok=false — the generating "
            "leg did not honour its own CARCASSONNE_FIX_R9 contract, so its farm "
            "scoring is not the data the profile name claims. Refusing to describe it.")
    name = mf_name or cli_profile
    if name is None:
        raise CorpusFormatError(
            "the corpus manifest carries no rules_profile and no --rules-profile "
            "was given. Pass one explicitly (pre-F9 corpora are `walled` by "
            "construction — every elo of record is a walled number — but say so "
            "on the command line so the artifact records the assumption).")
    if mf_name:
        source = "corpus manifest (rules_profile.name)"
    else:
        source = "--rules-profile (corpus manifest predates F9 A0 stamping)"
    # r9_env_observed is what the generator's process actually had latched; it is
    # the thing a replay must reproduce. Older manifests predate the stamp — fall
    # back to the profile's declared expectation.
    r9_obs = block.get("r9_env_observed")
    r9_exp = block.get("r9_env_expected")
    return {"name": name, "source": source, "manifest_block": block,
            "r9_expected": r9_exp, "r9_observed": r9_obs}


def r9_env_value(prof_info: dict) -> bool:
    """What CARCASSONNE_FIX_R9 must be for this replay (observed beats expected)."""
    if prof_info.get("r9_observed") is not None:
        return bool(prof_info["r9_observed"])
    if prof_info.get("r9_expected") is not None:
        return bool(prof_info["r9_expected"])
    # No stamp at all: only `fixed_v1` owes the env var, and a corpus that old
    # cannot be a fixed_v1 corpus (the profile registry is younger than the stamp).
    return False


def publish_environment(profile_name: str, r9_on: bool) -> None:
    """Set the two process-wide latches BEFORE the engine is imported."""
    os.environ["CARCASSONNE_RULES_PROFILE"] = profile_name
    os.environ["CARCASSONNE_FIX_R9"] = "1" if r9_on else "0"


def verify_environment(profile_name: str, r9_on: bool) -> dict:
    """Assert the latches actually came up as asked. Post-import, fail-loud."""
    from carcassonne_ai import rules_profile as rp
    from wingedsheep.carcassonne.tile_sets import base_deck

    active = rp.active()
    if active.name != profile_name:
        raise CorpusFormatError(
            f"rules profile latched as {active.name!r}, asked for {profile_name!r}")
    latched = bool(base_deck.R9_FIELD_ON_CITY_EDGE_FIX)
    if latched != bool(r9_on):
        raise CorpusFormatError(
            f"CARCASSONNE_FIX_R9 latched {latched} but the corpus needs {bool(r9_on)}. "
            "base_deck derives the farm data at import time, so this cannot be "
            "fixed after the fact — re-run with the env var set before python starts.")
    return {"profile": active.as_manifest(), "r9_latched": latched,
            "game_kwargs": active.game_kwargs()}


# --------------------------------------------------------------------------- #
# the per-game replay                                                           #
# --------------------------------------------------------------------------- #
def tercile_of(tile_idx: int, n_tiles: int) -> str:
    """Tile ordinal -> early/mid/late by thirds of this game's tile count."""
    if n_tiles <= 0:
        return "early"
    f = tile_idx / n_tiles
    if f < 1.0 / 3.0:
        return "early"
    if f < 2.0 / 3.0:
        return "mid"
    return "late"


def game_decision_stats(deck_seed: int, actions, recorded_scores=None,
                        game_id=None) -> dict:
    """Replay one game and return its decision-density record.

    One pass. Terciles need the game's tile count, which is only known at the end,
    so per-ply rows are collected first and binned afterwards.
    """
    import random

    from carcassonne_ai import action_space as A
    from carcassonne_ai.game_wrapper import Game
    from wingedsheep.carcassonne.objects.game_phase import GamePhase

    actions = [int(a) for a in actions]
    random.seed(int(deck_seed))
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=False)
    board = game.get_init_board()

    W = game.window_size
    TILE_PASS = A.tile_pass_index(W)
    M_NORMAL = A.meeple_normal_base(W)
    M_FARMER = A.meeple_farmer_base(W)
    M_PASS = A.meeple_pass_index(W)
    # NORMAL_SIDES = (TOP, RIGHT, BOTTOM, LEFT, CENTER); CENTER is the cloister monk.
    M_MONK = M_NORMAL + A.NORMAL_SIDES.index(A.Side.CENTER)

    rows = []          # per ply: (kind, n_legal, action, tile_idx_before, meeple_kind)
    free_by_ply = []   # sum of state.meeples over seats, at the START of the ply
    n_tiles = 0
    for a in actions:
        state = board.state
        kind = "tile" if state.phase == GamePhase.TILES else "meeple"
        n_legal = int(game.get_valid_moves(board).sum())
        mk = None
        if kind == "meeple":
            if a == M_PASS:
                mk = "pass"
            elif a == M_MONK:
                mk = "monk"
            elif M_FARMER <= a < M_PASS:
                mk = "farmer"
            elif M_NORMAL <= a < M_FARMER:
                mk = "normal"
            else:
                raise CorpusFormatError(
                    f"game {game_id}: action {a} in the MEEPLES phase is outside the "
                    f"meeple block [{M_NORMAL},{M_PASS}] — format drift")
        else:
            mk = "tile_pass" if a == TILE_PASS else "place"
        rows.append((kind, n_legal, int(a), n_tiles, mk))
        free_by_ply.append(sum(int(x) for x in state.meeples))
        if kind == "tile" and a != TILE_PASS:
            n_tiles += 1
        board, _ = game.get_next_state(board, int(a))

    final = [int(x) for x in board.state.scores]
    scores_match = None
    if recorded_scores is not None:
        scores_match = [int(x) for x in recorded_scores] == final

    # ---- bin ---------------------------------------------------------------- #
    samples = {k: {t: [] for t in TERCILES} for k in PLY_KINDS}
    forced = {k: {t: 0 for t in TERCILES} for k in PLY_KINDS}
    commits = {t: {"normal": 0, "monk": 0, "farmer": 0, "pass": 0} for t in TERCILES}
    tile_pass_plies = 0
    free_sum = {t: [] for t in TERCILES}
    for (kind, n_legal, a, tidx, mk), free in zip(rows, free_by_ply):
        band = tercile_of(tidx, n_tiles)
        samples[kind][band].append(n_legal)
        if n_legal <= 1:
            forced[kind][band] += 1
        if kind == "meeple":
            commits[band][mk] += 1
        elif mk == "tile_pass":
            tile_pass_plies += 1
        free_sum[band].append(free)

    def _tot(d):
        return sum(d.values()) if isinstance(d, dict) else d

    rec = {
        "game_id": game_id, "deck_seed": int(deck_seed),
        "n_plies": len(actions), "n_tile_plies": sum(1 for r in rows if r[0] == "tile"),
        "n_meeple_plies": sum(1 for r in rows if r[0] == "meeple"),
        "n_tiles_placed": n_tiles, "tile_pass_plies": tile_pass_plies,
        "final_scores": final, "margin": final[0] - final[1] if len(final) == 2 else None,
        "replay_scores_match": scores_match,
        "samples": {k: {t: samples[k][t] for t in TERCILES} for k in PLY_KINDS},
        "forced": forced,
        "commits": commits,
        "meeples_free_end": free_by_ply[-1] if free_by_ply else None,
        "meeples_free_mean_by_band": {
            t: (statistics.fmean(free_sum[t]) if free_sum[t] else None) for t in TERCILES},
    }
    # per-game roll-ups the aggregate quotes directly
    for k in PLY_KINDS:
        allc = [c for t in TERCILES for c in samples[k][t]]
        rec[f"{k}_decisions"] = len(allc)
        rec[f"{k}_forced"] = sum(forced[k].values())
        rec[f"{k}_searched"] = len(allc) - sum(forced[k].values())
        rec[f"{k}_branching_mean"] = statistics.fmean(allc) if allc else None
        srch = [c for c in allc if c >= 2]
        rec[f"{k}_branching_mean_searched"] = statistics.fmean(srch) if srch else None
    rec["decisions"] = rec["tile_decisions"] + rec["meeple_decisions"]
    rec["searched"] = rec["tile_searched"] + rec["meeple_searched"]
    rec["forced_total"] = rec["tile_forced"] + rec["meeple_forced"]
    rec["meeples_committed"] = sum(
        commits[t][m] for t in TERCILES for m in ("normal", "monk", "farmer"))
    rec["farmers_committed"] = sum(commits[t]["farmer"] for t in TERCILES)
    return rec


def _one(job):
    gid, seed, actions, recorded = job
    return game_decision_stats(seed, actions, recorded_scores=recorded, game_id=gid)


# --------------------------------------------------------------------------- #
# aggregation                                                                   #
# --------------------------------------------------------------------------- #
def _dist(xs) -> dict:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0}
    s = sorted(xs)

    def q(f):
        if len(s) == 1:
            return float(s[0])
        i = f * (len(s) - 1)
        lo = int(math.floor(i))
        hi = min(lo + 1, len(s) - 1)
        return float(s[lo] + (s[hi] - s[lo]) * (i - lo))

    mean = statistics.fmean(s)
    sd = statistics.pstdev(s) if len(s) > 1 else 0.0
    return {"n": len(s), "mean": mean, "sd": sd,
            "sem": (sd / math.sqrt(len(s))) if len(s) > 1 else 0.0,
            "median": q(0.5), "p10": q(0.10), "p90": q(0.90),
            "min": float(s[0]), "max": float(s[-1])}


GAME_METRICS = (
    "n_plies", "n_tile_plies", "n_meeple_plies", "n_tiles_placed", "tile_pass_plies",
    "decisions", "searched", "forced_total",
    "tile_decisions", "tile_searched", "tile_forced",
    "meeple_decisions", "meeple_searched", "meeple_forced",
    "tile_branching_mean", "tile_branching_mean_searched",
    "meeple_branching_mean", "meeple_branching_mean_searched",
    "meeples_committed", "farmers_committed", "meeples_free_end", "margin",
)


def aggregate(records, label, corpus, prof_info, env_info, note="") -> dict:
    pooled = {k: {t: [] for t in ("all",) + TERCILES} for k in PLY_KINDS}
    forced_pool = {k: {t: 0 for t in ("all",) + TERCILES} for k in PLY_KINDS}
    commits = {t: {"normal": 0, "monk": 0, "farmer": 0, "pass": 0} for t in TERCILES}
    for r in records:
        for k in PLY_KINDS:
            for t in TERCILES:
                pooled[k][t].extend(r["samples"][k][t])
                pooled[k]["all"].extend(r["samples"][k][t])
                forced_pool[k][t] += r["forced"][k][t]
                forced_pool[k]["all"] += r["forced"][k][t]
        for t in TERCILES:
            for m in commits[t]:
                commits[t][m] += r["commits"][t][m]

    n = len(records)
    branching = {}
    for k in PLY_KINDS:
        branching[k] = {}
        for t in ("all",) + TERCILES:
            d = _dist(pooled[k][t])
            d["forced_plies"] = forced_pool[k][t]
            d["forced_frac"] = (forced_pool[k][t] / d["n"]) if d["n"] else None
            srch = [c for c in pooled[k][t] if c >= 2]
            d["searched_plies"] = len(srch)
            d["mean_searched"] = statistics.fmean(srch) if srch else None
            branching[k][t] = d

    mism = [r["game_id"] for r in records if r["replay_scores_match"] is False]
    cat = {
        "schema": SCHEMA,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "label": label,
        "note": note,
        "corpus": {"path": corpus["path"], "kind": corpus["kind"], "n_games": n},
        "rules_profile": {
            "name": prof_info["name"], "source": prof_info["source"],
            "r9_env": bool(env_info["r9_latched"]),
            "resolved": env_info["profile"],
            "game_kwargs": {k: str(v) for k, v in env_info["game_kwargs"].items()},
        },
        "definitions": DEFINITIONS,
        "per_game": {m: _dist([r.get(m) for r in records]) for m in GAME_METRICS},
        "branching": branching,
        "meeple_commits_by_band": {
            t: dict(commits[t],
                    per_game={m: commits[t][m] / n for m in commits[t]} if n else {})
            for t in TERCILES},
        "meeples_free_mean_by_band": {
            t: _dist([r["meeples_free_mean_by_band"][t] for r in records])
            for t in TERCILES},
        "integrity": {
            "replay_scores_match": sum(1 for r in records if r["replay_scores_match"] is True),
            "replay_scores_mismatch": len(mism),
            "replay_scores_unchecked": sum(1 for r in records
                                           if r["replay_scores_match"] is None),
            "mismatch_game_ids": mism[:20],
        },
    }
    return cat


def _f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def to_markdown(cat) -> str:
    L = []
    A = L.append
    pg, br = cat["per_game"], cat["branching"]
    A(f"### Decision density — `{cat['label']}`")
    A("")
    A(f"Corpus `{cat['corpus']['path']}` · n={cat['corpus']['n_games']} games · "
      f"rules_profile **{cat['rules_profile']['name']}** "
      f"(from {cat['rules_profile']['source']}) · "
      f"R9 farm fix {'ON' if cat['rules_profile']['r9_env'] else 'off'}")
    itg = cat["integrity"]
    A(f"Integrity: replayed scores match {itg['replay_scores_match']}/"
      f"{cat['corpus']['n_games']} (mismatch {itg['replay_scores_mismatch']}, "
      f"unchecked {itg['replay_scores_unchecked']}).")
    A("")
    A("| per game | mean | sd | median | p10 | p90 |")
    A("|---|---:|---:|---:|---:|---:|")
    for m in GAME_METRICS:
        d = pg[m]
        if not d.get("n"):
            continue
        A(f"| {m} | {_f(d['mean'])} | {_f(d['sd'])} | {_f(d['median'])} | "
          f"{_f(d['p10'])} | {_f(d['p90'])} |")
    A("")
    A("**Legal-action count (branching) by ply kind and phase tercile**")
    A("")
    A("| ply kind | phase | plies | mean | median | p90 | max | forced | forced% | "
      "mean(searched) |")
    A("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k in PLY_KINDS:
        for t in ("all",) + TERCILES:
            d = br[k][t]
            if not d.get("n"):
                continue
            ff = d["forced_frac"]
            A(f"| {k} | {t} | {d['n']} | {_f(d['mean'])} | {_f(d['median'],1)} | "
              f"{_f(d['p90'],1)} | {_f(d['max'],0)} | {d['forced_plies']} | "
              f"{'—' if ff is None else f'{100*ff:.1f}%'} | {_f(d['mean_searched'])} |")
    A("")
    A("**Meeples committed by phase tercile** (per game)")
    A("")
    A("| phase | normal | monk | farmer | pass | free meeples (mean, both seats) |")
    A("|---|---:|---:|---:|---:|---:|")
    for t in TERCILES:
        c = cat["meeple_commits_by_band"][t]["per_game"]
        fr = cat["meeples_free_mean_by_band"][t]
        A(f"| {t} | {_f(c['normal'])} | {_f(c['monk'])} | {_f(c['farmer'])} | "
          f"{_f(c['pass'])} | {_f(fr.get('mean'))} |")
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
def run(corpus_path, label=None, rules_profile=None, workers=4, limit=0,
        note="") -> dict:
    """Load, replay, aggregate. Importable — `run_phase_c.py` calls this directly."""
    corpus = load_corpus(corpus_path, limit=limit)
    prof = resolve_corpus_profile(corpus, rules_profile)
    r9 = r9_env_value(prof)
    publish_environment(prof["name"], r9)
    _use_repo_tree()
    env_info = verify_environment(prof["name"], r9)

    jobs = [(g["game_id"], g["deck_seed"], g["actions"],
             ([g["score_p0"], g["score_p1"]] if "score_p0" in g and "score_p1" in g
              else None))
            for g in corpus["games"]]
    t0 = time.time()
    if workers > 1 and len(jobs) > 1:
        import multiprocessing as mp
        with mp.Pool(min(workers, len(jobs))) as pool:
            records = pool.map(_one, jobs, chunksize=4)
    else:
        records = [_one(j) for j in jobs]
    dt = time.time() - t0

    cat = aggregate(records, label or Path(str(corpus_path)).name, corpus, prof,
                    env_info, note=note)
    cat["timing"] = {"replay_seconds": round(dt, 1), "workers": workers,
                     "seconds_per_game": round(dt / max(1, len(jobs)), 3)}
    if cat["integrity"]["replay_scores_mismatch"]:
        raise CorpusFormatError(
            f"{cat['integrity']['replay_scores_mismatch']} of {len(records)} games "
            "replayed to DIFFERENT terminal scores than the generator recorded "
            f"(first: {cat['integrity']['mismatch_game_ids']}). Either the rules "
            "profile is wrong for this corpus or the engine has drifted since it "
            "was generated. Refusing to report descriptives from it.")
    return cat


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="F9 Phase C — decision density over a champion-play corpus")
    ap.add_argument("corpus", help="corpus DIR (gen_fair_distill --actions-only) or games JSONL")
    ap.add_argument("--label", default=None, help="short label for the artifact")
    ap.add_argument("--rules-profile", default=None,
                    help="required only when the corpus manifest carries none "
                         "(pre-F9 corpora: pass `walled` explicitly)")
    ap.add_argument("-o", "--json-out", default=None, help="write the JSON catalog here")
    ap.add_argument("--markdown", default=None, help="write the markdown table here")
    ap.add_argument("--workers", type=int, default=4,
                    help="replay workers (keep <=6; the box is usually busy)")
    ap.add_argument("--limit", type=int, default=0, help="first N games only")
    ap.add_argument("--note", default="", help="one-line provenance for the artifact")
    args = ap.parse_args(argv)

    if args.workers > 6:
        print(f"[descriptives] refusing --workers {args.workers}: cap is 6 "
              "(a GPU/eval run usually owns the box)", file=sys.stderr)
        return 2
    cat = run(args.corpus, label=args.label, rules_profile=args.rules_profile,
              workers=args.workers, limit=args.limit, note=args.note)
    md = to_markdown(cat)
    if args.json_out:
        p = Path(args.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cat, indent=1))
        print(f"[descriptives] wrote {p}")
    if args.markdown:
        p = Path(args.markdown)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md)
        print(f"[descriptives] wrote {p}")
    print(md)
    print(f"[descriptives] {cat['corpus']['n_games']} games in "
          f"{cat['timing']['replay_seconds']}s "
          f"({cat['timing']['seconds_per_game']}s/game, W={args.workers})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
