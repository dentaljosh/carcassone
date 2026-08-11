#!/usr/bin/env python3
"""FREE PASS #2 — the leaf's error against EXACT SOLVER TRUTH (hypothesis-only).

⚠️ ENDGAME-BOUNDED. Every root here is `k_remaining = 3` from the F3 public-state-oracle
suite. This set is mechanically incapable of passing or failing the PREREG.md §5 gate; it
exists to validate the pipeline end to end and to see which features look alive. No
threshold, no multiple-comparisons correction and no verdict is derived from it.

Difference from free pass #1 (`--roots-file` through `mine_residual.py`): the target here is
the EXACT marginalized-solver value `vstar`, i.e. TRUTH, not a deep search's belief:

    resid_exact = mover_pov(vstar) - leaf(root, mover)        [POINTS, not tanh units]

No search is run — the solves are already on disk in
`measurement/f3_public_state_oracle/records_k3/`. Only the 216 `completed` records are used
(the other 138 hit the node budget; using them would select for easy positions).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1", "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
from multiprocessing import get_context  # noqa: E402

import numpy as np  # noqa: E402

from carcassonne_ai import champion_factory as CF, flat_leaf  # noqa: E402
import gen_endgame_positions as GEP  # noqa: E402
import root_replay as RR  # noqa: E402
import leaf_features as LF  # noqa: E402
import analyze_residual as AR  # noqa: E402

_CFG = None


def _init(cfg):
    global _CFG
    _CFG = cfg


def _one(path: str):
    d = json.loads(Path(path).read_text())
    if not d.get("completed"):
        return None
    try:
        if d.get("deck_seed") is not None and d.get("actions"):
            game, board = RR.replay_actions(int(d["deck_seed"]), d["actions"], int(d["ply"]))
        else:
            game, board = GEP.replay_to(int(d["seed"]), int(d["ply"]))
        if game.string_representation(board) != d["checksum"]:
            return {"root_id": d["root_id"], "ok": False, "error": "checksum_mismatch"}
        st = board.state
        mover = int(st.current_player)
        assert mover == int(d["to_move"])
        leaf_cfg = _CFG.leaf_cfg
        leaf_mover = float(flat_leaf.flat_virtual_score_v2_float(st, mover, leaf_cfg, False))
        vstar_p0 = float(d["vstar"])
        vstar_mover = vstar_p0 if mover == 0 else -vstar_p0
        feats, aux = LF.root_features(st, mover, leaf_cfg, d["root_id"],
                                      int(d.get("legal_n", 0)), 1)
        # POINTS-space residual (exact truth minus leaf), plus the tanh-space version
        # so the two free passes are on comparable axes.
        return {
            "root_id": d["root_id"], "ok": True,
            "deck_seed": int(d.get("seed") or d.get("deck_seed")),
            "ply": int(d["ply"]), "k_remaining": int(d["k_remaining"]),
            "mover": mover, "features": feats, "aux": aux,
            "v_leaf": aux["v_leaf"],
            "resid": {"exact_points": vstar_mover - leaf_mover,
                      "exact_tanh": math.tanh(vstar_mover / 15.0) - aux["v_leaf"]},
            "leaf_points": leaf_mover, "vstar_mover": vstar_mover,
        }
    except Exception as e:  # noqa
        return {"root_id": d.get("root_id"), "ok": False, "error": f"{type(e).__name__}: {e}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default=str(REPO / "measurement/f3_public_state_oracle/records_k3"))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / "freepass_f3_exact.jsonl"))
    args = ap.parse_args(argv)

    files = sorted(str(p) for p in Path(args.records).glob("s*.json"))
    cfg = CF.production_prior_cfg()
    ctx = get_context("fork")
    out = []
    with ctx.Pool(args.workers, initializer=_init, initargs=(cfg,)) as pool:
        for r in pool.imap_unordered(_one, files, chunksize=4):
            if r is not None:
                out.append(r)
    ok = [r for r in out if r.get("ok")]
    Path(args.out).write_text("\n".join(json.dumps(r) for r in out) + "\n")
    print(f"[f3] records={len(files)} completed={len(out)} ok={len(ok)} -> {args.out}")

    # ---- the SAME estimator as the primary analysis, on an ENDGAME-BOUNDED set --- #
    for tgt in ("exact_points", "exact_tanh"):
        print(f"\n################ FREE PASS (HYPOTHESIS ONLY, ENDGAME K=3) "
              f"target={tgt} ################")
        AR.analyse(ok, tgt, f"freepass_f3_exact[{tgt}]", boot=1000)
    print("\n⚠️  ENDGAME-BOUNDED, HYPOTHESIS-ONLY. No gate is evaluated on this set.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
