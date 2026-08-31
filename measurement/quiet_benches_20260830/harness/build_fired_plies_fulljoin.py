#!/usr/bin/env python3
"""OM-M1 stage 1, step 1 — the FIRED-PLY frame.

⛔ INSTRUMENT ONLY. Spec: ``measurement/omm1_refuter_gate_20260830/PREREG.md`` §3.

Replays the two banked `walled` champion-selfplay corpora and records every ply
at which the DEPLOYED tie arbiter fires — the trigger is re-derived by
``carc_rs.MirrorState.tiearb_probe``, i.e. by the shipped
``carc_core::tiearb`` code, never by a re-implementation here.

**No playout runs.** This step is leaf-calls-only and costs about a minute at
W=30 (the widening census did the same 1,299 games in 52.2 s). It emits:

* ``FIRED_PLIES.jsonl`` — one row per SAMPLED ply (PREREG §3: at most ONE per
  game, seeded, so the `n` clusters are independent);
* ``FIRE_CENSUS.json`` — the per-game fire counts and the `G-FIRE` verdict.

Usage::

    python3 scripts/omm1/build_fired_plies.py --workers 14 [--limit N]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import omm1_lib as L  # noqa: E402


def _fired_plies_of_game(rec: dict, leaf_rs) -> dict:
    """Every ply of one game at which the deployed arbiter fires.

    The champion's own pick at ply `t` is `actions[t]` — by construction its
    `pooled_q_argmax` pick — which is exactly what `build_arms` appends when the
    `J <= 4` cap excluded it.
    """
    import carc_rs

    seed = str(rec["deck_seed"])
    actions = rec["actions"]
    g = carc_rs.MirrorState.from_seed(seed)
    fired = []
    for t, a in enumerate(actions):
        if g.is_terminal():
            break
        probe = g.tiearb_probe(
            leaf_rs,
            champ_pick=int(a),
            j=L.ARM_CAP_J,
            eps=L.EPS,
            salt=L.SALT_OF_RECORD,
            ply=t,
        )
        if probe.get("fired"):
            fired.append(
                {
                    "ply": t,
                    "seat": int(probe["seat"]),
                    "champ_pick": int(a),
                    "arms": list(probe["arms"]),
                    "n_arms": len(probe["arms"]),
                    "state_digest": probe["state_digest"],
                    "n_distinct_afterstates": int(probe["n_distinct_afterstates"]),
                    "capped": bool(probe["capped"]),
                    "champ_appended": bool(probe["champ_appended"]),
                }
            )
        g.advance(int(a))
    return {
        "corpus": rec["corpus"],
        "game_id": rec.get("game_id", rec["deck_seed"]),
        "deck_seed": rec["deck_seed"],
        "n_plies": rec.get("n_plies", len(actions)),
        "actions": actions,
        "fired": fired,
    }


def _worker(args):
    rec, leaf_kwargs = args
    import carc_rs

    leaf_rs = carc_rs.LeafConfigRs(**leaf_kwargs) if leaf_kwargs else _WORKER_LEAF[0]
    return _fired_plies_of_game(rec, leaf_rs)


_WORKER_LEAF: list = []


def _init_worker(profile: str):
    L.prepare_env(profile)
    leaf_rs, _ = L.leaf_of_record()
    _WORKER_LEAF.clear()
    _WORKER_LEAF.append(leaf_rs)


def _g_fire_join(per_game: list[dict]) -> dict:
    """⭐ `G-FIRE`, the decisive half: an exact per-ply join against the banked
    tile-tie census.

    Every `(deck_seed, ply)` this replay marks FIRED must carry `tie_exact` in
    `tiearb_widening_20260817/census/tile_gap_rows.jsonl` — the deployed trigger
    is a SUBSET of the leaf's exact-tie plies (arm dedupe collapses some tie
    sets to a single arm), so firing where the census says UNTIED is a trigger
    divergence and voids the round.

    This replaced a rate bracket around `22.96 fired plies/game`, which was the
    wrong constant for this population: 22.96 is the **E4 stratum** (597 tied
    plies / 26 phone games), while the census's own `champ449` figure is 45.26
    exact-tied tile plies/game. A rate check alone would have been ~2x off; the
    join is exact and cannot be.

    The census covers `champ449` only, so `tiearb2_850` contributes no joined
    rows — reported, not silently treated as agreement.
    """
    if not L.TILE_CENSUS.exists():
        return {"available": False, "n_joined": 0, "agreement": 1.0, "n_disagree": 0}
    tied: dict[tuple[int, int], bool] = {}
    gap: dict[tuple[int, int], float] = {}
    with L.TILE_CENSUS.open() as fh:
        for line in fh:
            if not line.strip():
                continue
            d = json.loads(line)
            k = (int(d["deck_seed"]), int(d["ply"]))
            tied[k] = bool(d["tie_exact"])
            for gk in ("gap", "tile_gap", "top1_minus_top2", "gap_exact"):
                if gk in d and d[gk] is not None:
                    gap[k] = float(d[gk])
                    break
    n_joined = n_disagree = 0
    examples = []
    # OM-D2 FULL JOIN (quiet re-read 2026-08-30): the banked run capped
    # `examples` at 10, which is exactly the "10 unverifiable keys" caveat —
    # half of the 20 disagreeing plies had no recorded witness. Record EVERY
    # disagreeing key, with the census's own gap, so each is verifiable.
    witnesses = []
    for pg in per_game:
        for f in pg["fired"]:
            key = (int(pg["deck_seed"]), int(f["ply"]))
            if key not in tied:
                continue
            n_joined += 1
            if not tied[key]:
                n_disagree += 1
                if len(examples) < 10:
                    examples.append(list(key))
                g = gap.get(key)
                witnesses.append(
                    {
                        "deck_seed": key[0],
                        "ply": key[1],
                        "corpus": pg["corpus"],
                        "census_gap": g,
                        "gap_recorded": g is not None,
                        "class": (
                            None
                            if g is None
                            else ("ULP" if abs(g) < 1e-9 else "REAL")
                        ),
                    }
                )
    n_witness = sum(1 for w in witnesses if w["gap_recorded"])
    return {
        "available": True,
        "census": str(L.TILE_CENSUS),
        "n_joined": n_joined,
        "n_disagree": n_disagree,
        "agreement": (1.0 - n_disagree / n_joined) if n_joined else 1.0,
        "disagreement_examples": examples,
        "full_join": True,
        "n_disagree_witnessed": n_witness,
        "n_disagree_unverifiable": n_disagree - n_witness,
        "all_witnessed": n_witness == n_disagree,
        "class_counts": {
            "ULP": sum(1 for w in witnesses if w["class"] == "ULP"),
            "REAL": sum(1 for w in witnesses if w["class"] == "REAL"),
            "UNKNOWN": sum(1 for w in witnesses if w["class"] is None),
        },
        "witnesses": witnesses,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="first N games per corpus (smoke only)")
    ap.add_argument("--profile", default="walled")
    ap.add_argument("--out-dir", type=Path, default=L.OUT_DIR)
    ap.add_argument(
        "--allow-missing-corpus",
        action="store_true",
        help="DEVIATION: proceed on the corpora that are present. The readout "
        "records which were skipped; PREREG §3 adjudicates on the POOLED row.",
    )
    a = ap.parse_args(argv)

    L.prepare_env(a.profile)
    leaf_rs, leaf_hashes = L.leaf_of_record()

    games, missing = [], []
    for label, path in L.CORPORA:
        try:
            g = L.load_games(path, label)
        except FileNotFoundError:
            if not a.allow_missing_corpus:
                raise
            missing.append(label)
            continue
        games.extend(g[: a.limit] if a.limit else g)

    t0 = time.time()
    if a.workers > 1:
        import multiprocessing as mp

        with mp.get_context("spawn").Pool(
            a.workers, initializer=_init_worker, initargs=(a.profile,)
        ) as pool:
            per_game = pool.map(_worker, [(r, None) for r in games], chunksize=4)
    else:
        per_game = [_fired_plies_of_game(r, leaf_rs) for r in games]
    elapsed = time.time() - t0

    # --- the sample: at most ONE fired ply per game, seeded (PREREG §3) -------
    rows, n_fired_total, no_fire = [], 0, 0
    for pg in per_game:
        n_fired_total += len(pg["fired"])
        if not pg["fired"]:
            no_fire += 1
            continue
        k = L.stable_seed("omm1-sample-v1", pg["deck_seed"]) % len(pg["fired"])
        f = pg["fired"][k]
        rows.append(
            {
                "schema": L.SCHEMA,
                "corpus": pg["corpus"],
                "game_id": pg["game_id"],
                "deck_seed": pg["deck_seed"],
                "n_fired_in_game": len(pg["fired"]),
                "draw_index": k,
                "prefix_actions": pg["actions"][: f["ply"]],
                **f,
            }
        )

    n_games = len(per_game)
    fire_rate = (n_fired_total / n_games) if n_games else 0.0
    join = _g_fire_join(per_game)
    lo, hi = L.FIRE_RATE_FRACTION_BRACKET
    frac = fire_rate / L.BANKED_TIED_TILE_PLIES_PER_GAME
    g_fire = bool(lo <= frac <= hi) and join["agreement"] >= 0.99

    a.out_dir.mkdir(parents=True, exist_ok=True)
    with (a.out_dir / "FIRED_PLIES.jsonl").open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    census = L.manifest(
        {
            "step": "build_fired_plies",
            "leaf_hashes": leaf_hashes,
            "profile": a.profile,
            "corpora_used": [c for c, _ in L.CORPORA if c not in missing],
            "corpora_missing": missing,
            "limit": a.limit,
            "n_games": n_games,
            "n_games_without_a_fire": no_fire,
            "n_fired_plies_total": n_fired_total,
            "fired_plies_per_game": fire_rate,
            "n_sampled": len(rows),
            "banked_tied_tile_plies_per_game": L.BANKED_TIED_TILE_PLIES_PER_GAME,
            "fired_over_tied_fraction": frac,
            "G_FIRE_fraction_bracket": list(L.FIRE_RATE_FRACTION_BRACKET),
            "G_FIRE_join": join,
            "G_FIRE": "PASS" if g_fire else "FAIL",
            "elapsed_s": elapsed,
        }
    )
    (a.out_dir / "FIRE_CENSUS.json").write_text(json.dumps(census, indent=2))
    print(
        json.dumps(
            {
                k: census[k]
                for k in (
                    "n_games",
                    "n_fired_plies_total",
                    "fired_plies_per_game",
                    "fired_over_tied_fraction",
                    "n_sampled",
                    "G_FIRE",
                    "G_FIRE_join",
                    "elapsed_s",
                )
            },
            indent=2,
        )
    )
    if not g_fire:
        print(
            f"⛔ G-FIRE FAIL: fired/tied fraction {frac:.3f} outside "
            f"{L.FIRE_RATE_FRACTION_BRACKET}, or per-ply join agreement "
            f"{join['agreement']:.4f} < 0.99. The replay is not reproducing the "
            "deployed trigger — OM-VOID.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
