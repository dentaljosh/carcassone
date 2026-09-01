#!/usr/bin/env python3
"""DEFENSE-PRIMARY — the NEW-PLIES census extension.  ⛔ COMPUTES NO PRICES.

WHAT THIS IS
------------
The standing DEFENSE-PRIMARY instrument (`PREREG.md`, frozen 2026-09-01) fires on
a COUNT of new divergent `defense` plies.  This script produces that count, and
the ledger the confirmation will later price, WITHOUT computing a single price.

It is the Stage-A divergent-ply census (`../e4_exploit_grading_20260825/stage_a_census.py`)
plus the champion-counterfactual naming step (`../e4_ply_pricing_20260827/`), run
over the archives that NO prior pricing round has touched, and extended to cover
the owner-vs-Carcasum corpus (`opponent = carcasum_remote_*`), where there is no
champion in the game and the counterfactual is therefore computed FRESH at every
candidate ply.

⛔ THE PRICE WALL.  A price is `delta_pts_mover` — the thing the confirmation
reads.  This script emits classification and identity ONLY.  `G-NOPRICE` refuses
to write any row carrying a price-shaped field, and `test_defense_primary.py`
proves the refusal fires.  Peeking at prices before the trigger fires would make
the trigger a selection on the outcome.

STAGES
------
  --stage classify        pure rules replay, NO search.  Stage-A structural
                          census + the four pre-registered strata -> candidates.jsonl
  --stage counterfactual  ONE unarmed production-champion decision per candidate
                          ply at the PINNED k8 x 1376 = 11008 / exact-K 2 budget
                          -> NEW_PLIES.jsonl (the ledger) + ACCRUAL.json

THE BUDGET IS PINNED, NOT READ FROM PRODUCTION.yaml
---------------------------------------------------
`fair_deploy` moved to k16 x 1376 = 22016 on 2026-08-30.  E-1a and E-1b both ran
the counterfactual at k8 x 1376 = 11008.  A YAML-default champion would name a
DIFFERENT counterfactual move than the one those rounds priced, and the new read
could not be contrasted with them at all.  So the budget is pinned here and
re-asserted from the RESOLVED rust config (`G-BUDGET`); the observed YAML values
and the drift flag go in `manifest.json`, never papered over.

DESIGNED SO PRICING NEEDS NO RE-CENSUS
--------------------------------------
Every ledger row carries everything the pricer needs: game, ply, K, phase, actor,
`played_action`, `counterfactual_action`, `n_legal`, resolved profile, corpus tag,
budget epoch stamps, the archive's own `deck_seed` (the CRN world seed), and the
Stage-A notes that named the stratum.  The confirmation reads this file and
launches; it never re-runs the classifier.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing as mp
import os
import random
import socket
import subprocess
import sys
import time
import zlib
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARCHIVES = REPO / "measurement" / "e4_games"

# --- pre-registered constants (frozen; see PREREG.md §1.2) ------------------ #
SCHEMA = "defense-primary-new-plies/v1"

# INHERITED VERBATIM from ../e4_ply_pricing_20260827/build_targets.py so the
# stratum definitions are the SAME selector E-1a/E-1b's plies were named by.
DEFENSE_WINDOW_PLIES = 8
CONTROL_TARGET_N = 50
CONTROL_SEED = 20260827

# INHERITED from E-1a/E-1b — the counterfactual pin.
PINNED_K_DETS = 8
PINNED_SIMS_PER_DET = 1376
PINNED_EXACT_K = 2
COUNTERFACTUAL_SEED = 0
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: Every target/diff set any prior pricing round selected from.  A game named in
#: ANY of these is OLD: its plies are excluded at GAME level (PREREG §2.1).
PRIOR_TARGET_SETS = (
    "measurement/e4_ply_pricing_20260827/targets_fixed_v1.jsonl",
    "measurement/e4_ply_pricing_20260827/targets_walled.jsonl",
    "measurement/e4_ply_pricing_20260827/targets_app_aug2.jsonl",
    "measurement/e4_ply_pricing_20260827/diffpos_fixed_v1.jsonl",
    "measurement/e4_ply_pricing_20260827/diffpos_walled.jsonl",
    "measurement/e4_ply_pricing_20260827/diffpos_app_aug2.jsonl",
    "measurement/e4_continuation_20260828/targets_continuation.jsonl",
    "measurement/e1b_armed_continuation_20260901/targets_continuation.jsonl",
    "measurement/c1_pricing_prep/targets_c1.jsonl",
)

#: A row carrying any of these is a PRICE.  `G-NOPRICE` refuses to write it.
BANNED_PRICE_FIELDS = frozenset({
    "delta_pts_mover", "price_played", "price_counterfactual", "margin_p0_minus_p1",
    "arm_values", "value", "solve", "final_scores_owner", "final_scores_cf",
    "e1a_price", "price", "pts_delta", "child_values",
})


# --------------------------------------------------------------------------- #
# refusals                                                                      #
# --------------------------------------------------------------------------- #
class Refusal(RuntimeError):
    """A loud gate failure.  Never downgraded to a warning, never a skip."""


def die(gate: str, msg: str):
    raise Refusal(f"{gate}: {msg}")


# --------------------------------------------------------------------------- #
# corpus tagging + eligibility                                                  #
# --------------------------------------------------------------------------- #
def corpus_tag(blob: dict) -> str:
    """champion_game | carcasum_game | carcasum_p103500 — the DECLARED stratifier.

    The tag is read from the archive's own `opponent` stamp and, for the remote
    corpus, from the server's self-labelled playout pin.  `carcasum_p103500` is
    E-5 epoch B (fixed playouts, strength tenancy-invariant); `carcasum_game` is
    epoch A (the 5000 ms wall).  An UNKNOWN opponent refuses — a corpus nothing
    conditions on is a corpus silently pooled.
    """
    opp = blob.get("opponent")
    if opp is None:
        die("G-CORPUS", "archive carries no `opponent` stamp — foreign/truncated file")
    opp = str(opp)
    if opp == "champion":
        return "champion_game"
    if opp.startswith("carcasum_remote"):
        remote = blob.get("remote") or {}
        pl = None
        if isinstance(remote, dict):
            pl = (remote.get("opponent") or {}).get("playouts")
        if pl is None and "p103500" in opp:
            pl = 103500
        return "carcasum_p103500" if pl is not None else "carcasum_game"
    die("G-CORPUS", f"unknown opponent {opp!r} — add a corpus tag before censusing it")


def opponent_kind(tag: str) -> str:
    return "champion" if tag == "champion_game" else "carcasum"


def prior_priced_games(repo: Path) -> tuple[set[str], list[dict]]:
    """Every game any prior pricing round selected a ply from, + provenance."""
    seen: set[str] = set()
    prov = []
    for rel in PRIOR_TARGET_SETS:
        p = repo / rel
        if not p.exists():
            prov.append({"path": rel, "present": False, "n_games": 0, "sha256": None})
            continue
        g = set()
        raw = p.read_bytes()
        for line in raw.decode().splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if isinstance(r, dict) and "game" in r:
                g.add(str(r["game"]))
        seen |= g
        prov.append({"path": rel, "present": True, "n_games": len(g),
                     "sha256": hashlib.sha256(raw).hexdigest()})
    return seen, prov


def eligible_archives(repo: Path):
    """(kept, rejected) — kept = archives NO prior pricing round has touched."""
    old, prov = prior_priced_games(repo)
    kept, rejected = [], []
    for p in sorted((repo / "measurement" / "e4_games").glob("*.json")):
        blob = json.loads(p.read_text())
        if blob.get("schema") not in (None, "carcassonne-android-archive/v1"):
            rejected.append({"game": p.name, "why": f"schema {blob.get('schema')!r}"})
            continue
        if blob.get("ok") is False:
            rejected.append({"game": p.name, "why": "archive `ok` is false"})
            continue
        if p.name in old:
            rejected.append({"game": p.name, "why": "OLD — a prior pricing round "
                                                    "selected a ply from this game"})
            continue
        kept.append(p)
    return kept, rejected, prov


# --------------------------------------------------------------------------- #
# stage A import (worktree-safe)                                                #
# --------------------------------------------------------------------------- #
def load_stage_a():
    """Import the Stage-A census module from THIS tree, then restore path order.

    `stage_a_census.py` hard-codes the MAIN tree in a module-level
    `sys.path.insert`.  In a worktree that would silently give later imports the
    main tree's copy of `scripts/analyzer` — the mixed-rev hazard CLAUDE.md's
    worktree rule exists to prevent.  So: import it by explicit file path, then
    put THIS tree's script dirs back in front.
    """
    src = REPO / "measurement" / "e4_exploit_grading_20260825" / "stage_a_census.py"
    if not src.exists():
        die("G-STAGEA", f"the Stage-A census module is missing at {src}")
    spec = importlib.util.spec_from_file_location("_stage_a_census", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for sub in ("scripts/measurement_infra", "scripts/analyzer", "scripts"):
        d = str(REPO / sub)
        while d in sys.path:
            sys.path.remove(d)
        sys.path.insert(0, d)
    return mod


def assert_worktree_imports():
    """Prove `carcassonne_ai` resolved where we think it did (recorded, not guessed)."""
    import carcassonne_ai
    return {"carcassonne_ai": str(Path(carcassonne_ai.__file__).resolve()),
            "repo": str(REPO), "sys_path_head": sys.path[:4]}


# --------------------------------------------------------------------------- #
# STAGE 1 — classify (pure replay, NO search)                                   #
# --------------------------------------------------------------------------- #
def replay_trace(archive_path, profile_name):
    """Per-ply (k_remaining, phase, actor, action, n_legal).

    Byte-for-byte the trace `../e4_ply_pricing_20260827/build_targets.py` builds.
    """
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game

    prof = rules_profile.resolve(profile_name)
    a = json.loads(Path(archive_path).read_text())
    seed, actions = int(a["deck_seed"]), [int(x) for x in a["actions"]]

    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, include_farm_scalars=True,
                **prof.game_kwargs())
    board = game.get_init_board()
    trace = []
    for i, act in enumerate(actions):
        st = board.state
        k = len(st.deck) + (1 if st.next_tile is not None else 0)
        trace.append({
            "ply": i, "k": int(k),
            "phase": str(getattr(st.phase, "name", st.phase)).lower(),
            "actor": int(st.current_player), "action": int(act),
            "n_legal": int(game.get_valid_moves(board).sum()),
        })
        board, _ = game.get_next_state(board, act)
    return trace, a


def stable_game_salt(stem: str) -> int:
    """⚠️ DEVIATION D-1 (declared, PREREG §2.4).

    `build_targets.py` seeded the control sampler with `hash(stem)`, which Python
    randomises per process (PYTHONHASHSEED).  That selector is NOT reproducible
    across runs, so it is replaced here by a stable CRC32.  It touches ONLY the
    `control` stratum; `defense` — the primary — is fully deterministic and is
    named by no sampler at all.
    """
    return zlib.crc32(stem.encode()) & 0xFFFFFFFF


def _row(stem, profile, t, n_plies, stratum, notes, tag, opp_kind):
    return {
        "schema": SCHEMA, "game": stem, "profile": profile, "stratum": stratum,
        "corpus": tag, "opponent_kind": opp_kind,
        "ply": t["ply"], "k": t["k"], "phase": t["phase"], "actor": t["actor"],
        "played_action": t["action"], "n_legal": t["n_legal"],
        "n_plies": n_plies, "ply_frac": t["ply"] / max(1, n_plies),
        "notes": notes,
    }


def classify_game(stem: str, profile: str, stage_a):
    """One archive -> its candidate plies in the four pre-registered strata.

    Selection keys are outcome-blind census fields throughout: no `winner`,
    `diff`, `margin` or `scores` is read anywhere on this path.
    """
    path = ARCHIVES / stem
    blob = json.loads(path.read_text())
    tag = corpus_tag(blob)
    opp_kind = opponent_kind(tag)
    if int(blob.get("human_player", 0)) != 0:
        die("G-SEAT", f"{stem}: human_player={blob.get('human_player')} — the strata "
                      "are written for owner=seat 0; refusing rather than mis-signing")

    # --- Stage-A structural census (real emitter, no search) ---------------- #
    g = stage_a.census_game(str(path), profile)
    census_rows = stage_a.extract_events(g)
    recon_ok = bool(g["recon_ok"])

    by_row = defaultdict(list)
    for r in census_rows:
        by_row[r["row"]].append(r)

    trace, arc = replay_trace(path, profile)
    by_ply = {t["ply"]: t for t in trace}
    n_plies = len(trace)
    if n_plies != len(g["ply_meta"]):
        die("G-REPLAY", f"{stem}: trace {n_plies} plies vs census {len(g['ply_meta'])}")

    out_rows = []
    flagged: dict[int, str] = {}

    # --- invasion: owner deliberate merge-invasion onsets -------------------- #
    inv_by_ply: dict[int, dict] = {}
    for r in by_row["contest"]:
        if r["invader"] != 0 or r["actor"] != 0:
            continue
        p = int(r["ply"])
        if by_ply.get(p) is None:
            continue
        inv_by_ply.setdefault(p, {"events": []})["events"].append({
            "cls": r["cls"], "mech": r["mech"], "outcome": r["outcome"],
            "n_tiles_at_contest": r["n_tiles_at_contest"],
            "incumbent_tiles_pre": r["incumbent_tiles_pre"],
            "invader_gain": r["invader_gain"],
            "incumbent_denied": r["incumbent_denied"],
            "scored_ply": r["scored_ply"], "scored_kind": r["scored_kind"],
            "feature_pts_final": r["feature_pts_final"],
        })
    for p, agg in sorted(inv_by_ply.items()):
        evs = agg["events"]
        flagged[p] = "invasion"
        notes = dict(evs[0])
        notes.update({
            "n_events": len(evs), "events": evs,
            "invader_gain": sum(e["invader_gain"] for e in evs),
            "incumbent_denied": sum(e["incumbent_denied"] for e in evs),
            "cls": evs[0]["cls"] if len(evs) == 1 else sorted({e["cls"] for e in evs}),
        })
        out_rows.append(_row(stem, profile, by_ply[p], n_plies, "invasion", notes,
                             tag, opp_kind))

    # --- farm_capture: late farm-majority switches caused by an owner move --- #
    for r in by_row["farm"]:
        for sw in (r.get("late_switches") or []):
            p = int(sw["ply"])
            t = by_ply.get(p)
            if t is None or t["actor"] != 0 or p in flagged:
                continue
            flagged[p] = "farm_capture"
            out_rows.append(_row(stem, profile, t, n_plies, "farm_capture", {
                "cls": "farm", "switch_from": sw["from"], "switch_to": sw["to"],
                "farm_n_tiles": r["n_tiles"], "farm_pts": r["pts"],
                "farm_pts_p0": r["pts_p0"], "farm_pts_p1": r["pts_p1"],
                "final_maj": r["final_maj"],
            }, tag, opp_kind))

    # --- defense: the OPPONENT's last tiles ply inside the window ------------ #
    # ⭐ THE PRIMARY STRATUM.  In a champion game the opponent IS the champion, so
    # this is byte-for-byte `build_targets.py`'s definition.  In a Carcasum game
    # the seat-1 agent is Carcasum, and the row is stamped `opponent_kind` so the
    # two can never be pooled without a declared homogeneity check (PREREG §3.2).
    invasion_plies = sorted(p for p, s in flagged.items() if s == "invasion")
    opp_tile_plies = [t["ply"] for t in trace
                      if t["actor"] == 1 and t["phase"] == "tiles"]
    seen_def = set()
    for p in invasion_plies:
        prior = [q for q in opp_tile_plies if q < p]
        if not prior:
            continue
        q = prior[-1]
        if p - q > DEFENSE_WINDOW_PLIES or q in seen_def:
            continue
        seen_def.add(q)
        out_rows.append(_row(stem, profile, by_ply[q], n_plies, "defense", {
            "defends_invasion_ply": p, "gap_plies": p - q,
            "defender_seat": 1, "defender_kind": opp_kind,
        }, tag, opp_kind))

    # --- control: owner tiles plies, decile-matched to this game's invasions -- #
    rng = random.Random(CONTROL_SEED ^ stable_game_salt(stem))
    pool = [t for t in trace
            if t["actor"] == 0 and t["phase"] == "tiles"
            and t["ply"] not in flagged and t["n_legal"] > 1]
    want = max(1, round(CONTROL_TARGET_N / 50.0 * max(1, len(invasion_plies))))
    picks = []
    if invasion_plies and pool:
        for p in invasion_plies:
            dec = min(9, int(10 * p / max(1, n_plies)))
            taken = {x["ply"] for x in picks}
            same = [t for t in pool
                    if min(9, int(10 * t["ply"] / max(1, n_plies))) == dec
                    and t["ply"] not in taken]
            cand = same or [t for t in pool if t["ply"] not in taken]
            if cand:
                picks.append(rng.choice(cand))
    elif pool:
        picks = rng.sample(pool, min(want, len(pool)))
    for t in picks:
        out_rows.append(_row(stem, profile, t, n_plies, "control", {}, tag, opp_kind))

    integrity = {
        "game": stem, "profile": profile, "corpus": tag,
        "n_plies_archive": len(arc["actions"]), "n_plies_replay": n_plies,
        "plies_match": len(arc["actions"]) == n_plies,
        "stage_a_recon_ok": recon_ok,
        "stage_a_recon_notes": g["recon_notes"][:5],
        "replay_scores": g["final_scores"], "recorded_scores": g["recorded_scores"],
        "deck_seed": int(arc["deck_seed"]),
        "budget_note": arc.get("budget_note"),
        "sims_effective": arc.get("sims_effective"),
        "k_dets_effective": arc.get("k_dets_effective"),
        "played_sims_effective": arc.get("played_sims_effective"),
        "played_k_dets_effective": arc.get("played_k_dets_effective"),
        "tiearb_enabled": arc.get("tiearb_enabled"), "tiearb_b": arc.get("tiearb_b"),
        "rules_profile": arc.get("rules_profile"),
        "cloister_rule": arc.get("cloister_rule"), "farm_rule": arc.get("farm_rule"),
        "finished_at": arc.get("finished_at"),
        "n_candidates": len(out_rows),
        "by_stratum": dict(Counter(r["stratum"] for r in out_rows)),
    }
    # Every candidate carries the game's budget/era stamps so no tally can be read
    # without conditioning on the epoch (E-1b PREREG §8.7).
    era = {k: integrity[k] for k in
           ("deck_seed", "budget_note", "sims_effective", "k_dets_effective",
            "played_sims_effective", "played_k_dets_effective",
            "tiearb_enabled", "tiearb_b", "rules_profile", "cloister_rule",
            "farm_rule", "finished_at")}
    for r in out_rows:
        r["archive_era"] = era
        r["stage_a_recon_ok"] = recon_ok
    return out_rows, integrity


def check_no_price(rows):
    """G-NOPRICE — the price wall.  Fires on the row, before anything is written."""
    for r in rows:
        bad = BANNED_PRICE_FIELDS & set(r)
        if bad:
            die("G-NOPRICE", f"row {r.get('game')}#{r.get('ply')} carries price-shaped "
                             f"field(s) {sorted(bad)} — the census may not peek at prices")
        n = r.get("notes")
        if isinstance(n, dict):
            bad = BANNED_PRICE_FIELDS & set(n)
            if bad:
                die("G-NOPRICE", f"notes of {r.get('game')}#{r.get('ply')} carry "
                                 f"{sorted(bad)}")


# --------------------------------------------------------------------------- #
# STAGE 2 — the champion counterfactual (ONE decision per candidate ply)         #
# --------------------------------------------------------------------------- #
def build_pinned_champion(game, threads: int):
    """The UNARMED production champion at E-1a's PINNED budget.

    Unarmed on purpose: E-1b armed the CONTINUATION policy, never the
    counterfactual — `arm_cf` was E-1a's banked champion pick in both rounds.
    Arming here would move two things at once.
    """
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.game_wrapper import Game  # noqa: F401  (typing/clarity)

    return CF.make_production_champion(
        "fair", game=game, seed=COUNTERFACTUAL_SEED,
        sims=PINNED_SIMS_PER_DET, k_dets=PINNED_K_DETS,
        exact_endgame=True, verify=True, backend="rust", rust_threads=int(threads))


def resolved_config(agent) -> dict:
    """The RESOLVED knobs off the rust side — never what we asked for."""
    rs = getattr(agent, "_rs", None)
    if rs is None:
        die("G-BUDGET", "the counterfactual champion has no rust handle — "
                        "a python-backed champion is not the pinned instrument")
    s = rs.stats()
    out = {k: s[k] for k in ("k_dets", "sims_per_det", "exact_max_k", "threads", "seed")
           if k in s}
    for k in ("jrules_prior_dose", "jrules_prior_scope", "jrules_prior_mask"):
        if k in s:
            out[k] = s[k]
    for k in ("tiearb_enabled", "tiearb_b"):
        if k in s:
            out[k] = s[k]
    return out


def gate_budget(cfg: dict):
    """G-BUDGET + G-UNARMED — asserted on the RESOLVED config, every game."""
    for key, want in (("k_dets", PINNED_K_DETS),
                      ("sims_per_det", PINNED_SIMS_PER_DET),
                      ("exact_max_k", PINNED_EXACT_K)):
        if key not in cfg:
            die("G-BUDGET", f"resolved config has no {key!r} — ABSENT is FAIL")
        if int(cfg[key]) != int(want):
            die("G-BUDGET", f"{key}={cfg[key]} but the pin is {want}")
    if int(cfg.get("seed", -1)) != COUNTERFACTUAL_SEED:
        die("G-BUDGET", f"seed={cfg.get('seed')} but the pin is {COUNTERFACTUAL_SEED}")
    dose = float(cfg.get("jrules_prior_dose", 0.0))
    if dose != 0.0:
        die("G-UNARMED", f"the counterfactual champion is ARMED (dose {dose}) — "
                         "the counterfactual is the unarmed champion in E-1a and E-1b")
    if bool(cfg.get("tiearb_enabled", False)):
        die("G-NOARB", "the counterfactual champion has the tie arbiter armed — "
                       "E-1a/E-1b's counterfactual is arbiter-free")


def counterfactual_game(stem: str, profile: str, candidates: list, threads: int):
    """Name the champion's own move at each candidate ply of one archive."""
    from carcassonne_ai import rules_profile
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.mirror_protocol import advance, resolve_execution, seat

    arc = json.loads((ARCHIVES / stem).read_text())
    seed = int(arc["deck_seed"])
    actions = [int(x) for x in arc["actions"]]
    prof = rules_profile.activate(profile)
    ex = resolve_execution("rust", profile="desktop", rust_threads=threads)
    if ex["backend"] != "rust":
        die("G-BACKEND", f"the pinned counterfactual is rust-only: got {dict(ex)}")

    want = {int(t["ply"]): t for t in candidates}
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())
    board = game.get_init_board()
    t_build = time.time()
    champ = build_pinned_champion(game, threads)
    build_s = time.time() - t_build
    cfg = resolved_config(champ)
    gate_budget(cfg)

    hashes = (getattr(champ, "manifest", {}) or {}).get("leaf_hashes") or {}
    if LEAF_HASH_OF_RECORD not in set(map(str, hashes.values())):
        die("G-LEAF", f"{LEAF_HASH_OF_RECORD} not among the verified leaf hashes {hashes}")

    seat(champ, board)
    rows, cf_secs = [], []
    for i, a in enumerate(actions):
        if i in want:
            t = dict(want[i])
            t0 = time.time()
            champ._move_idx = i         # mirror_protocol: the caller owns the timeline
            cf = int(champ.choose_action(board))
            dt = time.time() - t0
            cf_secs.append(dt)
            lm = champ.last_move() or {}
            t.update({
                "counterfactual_action": cf,
                "counterfactual_agrees": (cf == int(t["played_action"])),
                "divergent": (cf != int(t["played_action"])),
                "counterfactual_s": round(dt, 3),
                "counterfactual_flags": {k: lm[k] for k in
                                         ("forced", "exact", "latched", "timeout")
                                         if k in lm},
                "counterfactual_budget": {"k_dets": PINNED_K_DETS,
                                          "sims_per_det": PINNED_SIMS_PER_DET,
                                          "total_sims": PINNED_K_DETS * PINNED_SIMS_PER_DET,
                                          "exact_max_k": PINNED_EXACT_K,
                                          "seed": COUNTERFACTUAL_SEED,
                                          "source": "PINNED (E-1a), not PRODUCTION.yaml"},
                "counterfactual_resolved": cfg,
                "execution": dict(ex),
            })
            rows.append(t)
        board, _ = game.get_next_state(board, a)
        advance(champ, a)
    if hasattr(champ, "close"):
        champ.close()
    if len(rows) != len(want):
        die("G-COVER", f"{stem}: {len(rows)} counterfactuals for {len(want)} candidates")
    check_no_price(rows)
    return rows, {"game": stem, "build_s": round(build_s, 2),
                  "n_cf": len(cf_secs),
                  "cf_s_total": round(sum(cf_secs), 2),
                  "cf_s_mean": round(sum(cf_secs) / len(cf_secs), 3) if cf_secs else None,
                  "cf_s_max": round(max(cf_secs), 3) if cf_secs else None,
                  "resolved": cfg}


# --------------------------------------------------------------------------- #
# workers                                                                       #
# --------------------------------------------------------------------------- #
def _init(profile: str):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    for sub in ("scripts/measurement_infra", "scripts/analyzer", "scripts"):
        d = str(REPO / sub)
        if d not in sys.path:
            sys.path.insert(0, d)
    import ev_loss                                              # noqa: PLC0415
    ev_loss.prepare_env(profile)


def _w_classify(job):
    stem, profile = job
    stage_a = load_stage_a()
    try:
        rows, integ = classify_game(stem, profile, stage_a)
        check_no_price(rows)
        return {"ok": True, "rows": rows, "integrity": integ}
    except Refusal as e:
        return {"ok": False, "game": stem, "error": str(e), "refusal": True}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "game": stem, "error": f"{type(e).__name__}: {e}"}


def _w_counterfactual(job):
    stem, profile, cands, threads = job
    try:
        rows, cost = counterfactual_game(stem, profile, cands, threads)
        return {"ok": True, "rows": rows, "cost": cost}
    except Refusal as e:
        return {"ok": False, "game": stem, "error": str(e), "refusal": True}
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "game": stem, "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- #
# manifest                                                                      #
# --------------------------------------------------------------------------- #
def git_commit(repo: Path) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=20,
                              check=True).stdout.strip()
    except Exception:                                            # noqa: BLE001
        return None


def production_yaml_observed(repo: Path) -> dict:
    """What PRODUCTION.yaml says TODAY — recorded, never used (the pin binds)."""
    try:
        import yaml
        spec = yaml.safe_load((repo / "governance" / "PRODUCTION.yaml").read_text())
        fd = ((spec.get("champion") or {}).get("fair_deploy") or {})
        k, s = fd.get("k_dets"), fd.get("sims_per_det")
        return {"k_dets": k, "sims_per_det": s,
                "total_sims": (k * s) if (k and s) else None,
                "tiearb_enabled": (fd.get("tiearb") or {}).get("enabled"),
                "drift_vs_pin": (k != PINNED_K_DETS or s != PINNED_SIMS_PER_DET),
                "note": "fair_deploy moved to k16x1376=22016 on 2026-08-30, AFTER "
                        "E-1a. This census pins E-1a's budget so its counterfactual "
                        "is the SAME move E-1a and E-1b priced."}
    except Exception as e:                                       # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def build_manifest(args, kept, rejected, prov, env, imports) -> dict:
    return {
        "schema": SCHEMA,
        "written_at": int(time.time()),
        "host": socket.gethostname(),
        "repo": str(REPO),
        "code_commit": git_commit(REPO),
        "stage": args.stage,
        "profile": args.profile,
        "workers": args.workers,
        "rust_threads": args.threads,
        "env": env,
        "imports": imports,
        "constants": {
            "defense_window_plies": DEFENSE_WINDOW_PLIES,
            "control_target_n": CONTROL_TARGET_N,
            "control_seed": CONTROL_SEED,
            "control_salt": "zlib.crc32(stem)  # DEVIATION D-1, PREREG 2.4",
        },
        "budget_pin": {"k_dets": PINNED_K_DETS, "sims_per_det": PINNED_SIMS_PER_DET,
                       "total_sims": PINNED_K_DETS * PINNED_SIMS_PER_DET,
                       "exact_max_k": PINNED_EXACT_K, "seed": COUNTERFACTUAL_SEED,
                       "leaf_hash_of_record": LEAF_HASH_OF_RECORD},
        "production_yaml_observed": production_yaml_observed(REPO),
        "eligibility": {
            "rule": "an archive is NEW iff no prior pricing round selected a ply "
                    "from it (GAME-level exclusion, PREREG 2.1)",
            "prior_target_sets": prov,
            "n_eligible": len(kept),
            "eligible": [p.name for p in kept],
            "n_rejected": len(rejected),
            "rejected": rejected,
        },
        "price_wall": {"banned_fields": sorted(BANNED_PRICE_FIELDS),
                       "gate": "G-NOPRICE"},
    }


# --------------------------------------------------------------------------- #
# accrual                                                                       #
# --------------------------------------------------------------------------- #
def accrual(rows: list) -> dict:
    div = [r for r in rows if r.get("divergent")]
    by_corpus_stratum = Counter((r["corpus"], r["stratum"]) for r in div)
    defense = [r for r in div if r["stratum"] == "defense"]
    return {
        "schema": SCHEMA,
        "n_censused_plies": len(rows),
        "n_divergent_plies": len(div),
        "n_games": len({r["game"] for r in rows}),
        "divergent_by_corpus_stratum": {f"{c}/{s}": n
                                        for (c, s), n in sorted(by_corpus_stratum.items())},
        "DEFENSE_ACCRUAL": {
            "total": len(defense),
            "by_corpus": dict(Counter(r["corpus"] for r in defense)),
            "by_game": dict(Counter(r["game"] for r in defense)),
            "n_games_contributing": len({r["game"] for r in defense}),
        },
        "divergence_rate_by_corpus_stratum": {
            f"{c}/{s}": round(by_corpus_stratum[(c, s)] /
                              max(1, sum(1 for r in rows
                                         if r["corpus"] == c and r["stratum"] == s)), 3)
            for (c, s) in sorted({(r["corpus"], r["stratum"]) for r in rows})
        },
    }


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("classify", "counterfactual"))
    ap.add_argument("--profile", default="fixed_v1")
    ap.add_argument("--out-dir", default=str(HERE))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--threads", type=int, default=1, help="rust threads per worker")
    ap.add_argument("--games", default=None,
                    help="comma-separated archive stems (default: every eligible one)")
    ap.add_argument("--candidates", default=None,
                    help="counterfactual stage: the classify stage's output")
    ap.add_argument("--out", default=None)
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _init(args.profile)
    import ev_loss                                               # noqa: PLC0415
    env = ev_loss.prepare_env(args.profile)
    imports = assert_worktree_imports()

    kept, rejected, prov = eligible_archives(REPO)
    kept = [p for p in kept
            if ev_loss.resolve_profile_name(json.loads(p.read_text())) == args.profile]
    if args.games:
        want = {s.strip() for s in args.games.split(",") if s.strip()}
        unknown = want - {p.name for p in kept}
        if unknown:
            die("G-ELIGIBLE", f"{sorted(unknown)} are not eligible NEW archives under "
                              f"profile {args.profile!r} — refusing to census an OLD "
                              "or foreign game")
        kept = [p for p in kept if p.name in want]
    if not kept:
        die("G-ELIGIBLE", "0 eligible archives — a loud zero, not a silent pass")

    man = build_manifest(args, kept, rejected, prov, env, imports)
    ctx = mp.get_context("spawn")
    t0 = time.time()

    if args.stage == "classify":
        out = Path(args.out or (out_dir / f"candidates_{args.profile}.jsonl"))
        jobs = [(p.name, args.profile) for p in kept]
        rows, integrity, errors = [], [], []
        with ctx.Pool(min(args.workers, len(jobs)), initializer=_init,
                      initargs=(args.profile,)) as pool:
            for res in pool.imap_unordered(_w_classify, jobs):
                if not res["ok"]:
                    errors.append(res)
                    print(f"  !! {res['game']}: {res['error']}", flush=True)
                    continue
                rows.extend(res["rows"])
                integrity.append(res["integrity"])
                i = res["integrity"]
                print(f"  [{len(integrity):2d}/{len(jobs)}] {i['game']} "
                      f"{i['corpus']:18s} recon={i['stage_a_recon_ok']} "
                      f"cands={i['n_candidates']:3d} {i['by_stratum']} "
                      f"({time.time()-t0:.0f}s)", flush=True)
        if errors:
            die("G-CLASSIFY", f"{len(errors)} archive(s) failed to classify: "
                              f"{[e['game'] for e in errors]}")
        bad = [i for i in integrity if not i["stage_a_recon_ok"] or not i["plies_match"]]
        if bad:
            die("G-RECON", f"{[b['game'] for b in bad]} did not reconcile — a game "
                           "whose replay does not reproduce its own archive is "
                           "EXCLUDED loudly, never censused quietly")
        check_no_price(rows)
        rows.sort(key=lambda r: (r["game"], r["ply"]))
        with out.open("w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        man["result"] = {
            "n_games": len(integrity), "n_candidates": len(rows),
            "by_stratum": dict(Counter(r["stratum"] for r in rows)),
            "by_corpus": dict(Counter(r["corpus"] for r in rows)),
            "by_corpus_stratum": {f"{c}/{s}": n for (c, s), n in sorted(
                Counter((r["corpus"], r["stratum"]) for r in rows).items())},
            "integrity": integrity,
            "wall_s": round(time.time() - t0, 1),
        }
        mp_path = Path(args.manifest or (out_dir / "manifest_classify.json"))
        mp_path.write_text(json.dumps(man, indent=1))
        print(json.dumps({k: v for k, v in man["result"].items() if k != "integrity"},
                         indent=1))
        print(f"CANDIDATES {out}")
        return

    # ---- counterfactual ---------------------------------------------------- #
    cand_path = Path(args.candidates or (out_dir / f"candidates_{args.profile}.jsonl"))
    if not cand_path.exists():
        die("G-INPUT", f"no candidates at {cand_path} — run --stage classify first")
    cands = [json.loads(l) for l in cand_path.open() if l.strip()]
    by_game = defaultdict(list)
    for c in cands:
        by_game[c["game"]].append(c)
    stems = [p.name for p in kept if p.name in by_game]
    jobs = [(s, args.profile, by_game[s], args.threads) for s in stems]
    out = Path(args.out or (out_dir / "NEW_PLIES.jsonl"))

    rows, costs, errors = [], [], []
    with ctx.Pool(min(args.workers, len(jobs)), initializer=_init,
                  initargs=(args.profile,)) as pool:
        for res in pool.imap_unordered(_w_counterfactual, jobs):
            if not res["ok"]:
                errors.append(res)
                print(f"  !! {res['game']}: {res['error']}", flush=True)
                continue
            rows.extend(res["rows"])
            costs.append(res["cost"])
            c = res["cost"]
            nd = sum(1 for r in res["rows"] if r["divergent"])
            print(f"  [{len(costs):2d}/{len(jobs)}] {c['game']} n={c['n_cf']:3d} "
                  f"divergent={nd:3d} cf_mean={c['cf_s_mean']}s "
                  f"build={c['build_s']}s ({time.time()-t0:.0f}s)", flush=True)
    if errors:
        die("G-CF", f"{len(errors)} archive(s) failed: {[e['game'] for e in errors]}")
    if len(rows) != len(cands):
        die("G-COVER", f"{len(rows)} ledger rows for {len(cands)} candidates")
    check_no_price(rows)
    rows.sort(key=lambda r: (r["game"], r["ply"]))

    # merge with any previously banked ledger rows (idempotent by (game, ply))
    if out.exists():
        prev = {(r["game"], r["ply"]): r
                for r in (json.loads(l) for l in out.open() if l.strip())}
        for r in rows:
            prev[(r["game"], r["ply"])] = r
        rows = [prev[k] for k in sorted(prev)]
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    acc = accrual(rows)
    acc["cost"] = {"wall_s": round(time.time() - t0, 1), "per_game": costs}
    (out_dir / "ACCRUAL.json").write_text(json.dumps(acc, indent=1))
    man["result"] = {k: v for k, v in acc.items() if k != "cost"}
    man["result"]["wall_s"] = round(time.time() - t0, 1)
    Path(args.manifest or (out_dir / "manifest.json")).write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in acc.items() if k != "cost"}, indent=1))
    print(f"LEDGER {out}")


if __name__ == "__main__":
    main()
