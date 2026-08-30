#!/usr/bin/env python3
"""Run the NEW tier1-greedy selection worlds [j0, j0+m) for the B>64 extension.

Reuses `scripts/tiletie/tier1_rust_leg.score_one` VERBATIM. The only change is
that `oracle_score_pilot.world_seeds` / `.playout_seed` are patched, in each
worker, to the SHIFTED index — so the worlds produced are exactly worlds
`j0 … j0+m-1` of the same `sha256(tag|rid|j|salt)` sequence the banked run used
(PREREG.md §1, G-ID-4). `score_one` takes those functions by function-local
import at call time, so the patch is what it sees.

Banked worlds 0…127 are NEVER regenerated; this writes only the new block, and
`b128_lib.assemble` concatenates.

    python run_ext_leg.py --j0 128 --m 128 --workers 30 \
        --out-dir /mnt/c/carc-shared/b128_offline/ext_j128 --shard 0 --nshards 1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b128_lib as L  # noqa: E402

sys.path.insert(0, os.path.join(L.WT, "scripts", "tiletie"))
import tier1_rust_leg as T1  # noqa: E402

KEEP = ("rid", "values_a", "values_b", "world_seeds", "playout_seeds",
        "crn_verified", "crn_witness", "n_distinct_worlds", "world_deck_hash",
        "checksum_ok", "distinct_afterstates", "ok", "error", "elapsed_secs",
        "m", "pick_a", "pick_b", "playout_plies_a", "playout_plies_b")

_J0 = None


def _init(j0, salt, m):
    """Patch the CRN derivation to the SHIFTED index, then PROVE the patch is live.

    The check compares what a fresh function-local import sees (which is what
    `score_one` will see) against the unshifted truth taken from the pristine
    functions captured before patching.
    """
    global _J0
    _J0 = int(j0)
    import oracle_score_pilot as OSP
    true_world_seeds = OSP.world_seeds          # pristine, captured pre-patch
    ws, ps = L.shifted_seed_fns(int(j0), salt)
    OSP.world_seeds = ws
    OSP.playout_seed = ps
    from oracle_score_pilot import world_seeds as seen  # what score_one will see
    probe = "tt_preflight_probe_p0"
    want = true_world_seeds(probe, int(j0) + int(m), salt)[int(j0):int(j0) + int(m)]
    if seen(probe, int(m), salt) != want:
        raise SystemExit(
            f"[b128] worker seed patch NOT live/correct at j0={j0} — refusing")


def _one(item):
    leg, pos = item
    rec = T1.score_one(pos, m=_G["m"], salt=_G["salt"], max_plies=_G["max_plies"],
                       legal_mask_cache=True, world_deck_witness=True,
                       strict_crn=False, oracle_sims=100)
    out = {k: rec.get(k) for k in KEEP}
    out["leg"] = leg
    out["j0"] = _J0
    return out


_G = {}


def _init2(cfg):
    _G.update(cfg)
    _init(cfg["j0"], cfg["salt"], cfg["m"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--j0", type=int, required=True)
    ap.add_argument("--m", type=int, default=128)
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="smoke: first N items")
    ap.add_argument("--salt", default=L.SALT)
    ap.add_argument("--max-plies", type=int, default=400)
    a = ap.parse_args(argv)

    pre = {"wheel": T1.preflight_wheel(),
           "profile": T1.preflight_profile("walled"),
           "m": T1.preflight_m(a.m)}
    # prefix stability of the UNSHIFTED derivation, asserted before patching
    pre["seeds_unshifted"] = T1.preflight_seeds(a.salt, 128)

    positions = L.load_positions()
    arms = L.load_arms()
    items = []
    for (leg, rid), p in sorted(positions.items()):
        if rid not in arms:
            continue
        items.append((leg, p))
    items = [it for i, it in enumerate(items) if i % a.nshards == a.shard]
    if a.limit:
        items = items[:a.limit]

    os.makedirs(a.out_dir, exist_ok=True)
    todo = []
    for leg, p in items:
        dst = os.path.join(a.out_dir, f"leg{leg}", f"{p['rid']}.json")
        if os.path.exists(dst):
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        todo.append((leg, p))
    print(f"[b128] shard {a.shard}/{a.nshards} items={len(items)} todo={len(todo)} "
          f"j0={a.j0} m={a.m} W={a.workers}", flush=True)

    cfg = {"m": a.m, "salt": a.salt, "max_plies": a.max_plies, "j0": a.j0}
    t0 = time.time()
    n_ok = n_bad = 0
    elapsed_sum = 0.0
    with Pool(a.workers, initializer=_init2, initargs=(cfg,)) as pool:
        for i, rec in enumerate(pool.imap_unordered(_one, todo, chunksize=1), 1):
            dst = os.path.join(a.out_dir, f"leg{rec['leg']}", f"{rec['rid']}.json")
            tmp = dst + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(rec, fh)
            os.replace(tmp, dst)
            n_ok += bool(rec.get("ok"))
            n_bad += not rec.get("ok")
            elapsed_sum += float(rec.get("elapsed_secs") or 0.0)
            if i % 100 == 0 or i == len(todo):
                el = time.time() - t0
                rate = i / el
                print(f"[b128] {i}/{len(todo)} ok={n_ok} bad={n_bad} "
                      f"{rate:.2f} rec/s eta={((len(todo)-i)/rate)/60:.1f} min",
                      flush=True)
    wall = time.time() - t0
    man = {"schema": "carcassonne-b128-ext-leg/v1",
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "preflight": pre,
           "resolved_config": vars(a),
           "n_items": len(items), "n_todo": len(todo),
           "n_ok": n_ok, "n_failed": n_bad,
           "wall_secs": round(wall, 1),
           "elapsed_secs_sum": round(elapsed_sum, 1),
           "n_playouts": len(todo) * a.m * 2,
           "secs_per_playout": (round(elapsed_sum / (len(todo) * a.m * 2), 6)
                                if todo else None),
           "host": os.uname().nodename}
    mp = os.path.join(a.out_dir, f"manifest_shard{a.shard}of{a.nshards}.json")
    with open(mp, "w") as fh:
        json.dump(man, fh, indent=1, sort_keys=True)
    print("[b128] wrote", mp, json.dumps(
        {k: man[k] for k in ("n_ok", "n_failed", "wall_secs", "elapsed_secs_sum",
                             "n_playouts", "secs_per_playout")}), flush=True)
    return 0 if n_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
