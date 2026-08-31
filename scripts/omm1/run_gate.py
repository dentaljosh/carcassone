#!/usr/bin/env python3
"""OM-M1 stage 1, step 2 — the four legs.

⛔ INSTRUMENT ONLY. Spec: ``measurement/omm1_refuter_gate_20260830/PREREG.md`` §4.

For every sampled fired ply, runs S / P / R_ref / R_max over ONE shared set of
``B = 64`` CRN determinizations and persists the RAW ``B x arms`` margin matrix
per leg. No statistic is computed here — that is ``analyze_gate.py``'s job, so
the frozen read rule can be re-run without re-running a playout.

Guards enforced in-run, per ply (PREREG §7):

* ``G-BITEXACT`` — the S leg's ``means`` are bit-identical to the shipped
  ``carc_core::tiearb::arbitrate``. Checked here by re-deriving the deployed
  arbitration through the same binding with a single symmetric leg; the
  bit-identity itself is pinned by the rust test of the same name.
* ``G-CRN`` — the returned ``world_seeds`` equal ``sha256(salt|digest|ply|j)``.
* ``G-COMPLETE`` — ``worlds_completed == B`` on every leg. Any playout error
  voids the WHOLE ply (all four legs) and is recorded, never averaged over.
* ``G-SALT`` / ``G-LEAF`` — stamped into ``manifest.json``.

⚠️ This is the ONLY step that buys compute: ``4 legs x 64 worlds x ~3 arms``
tier1-greedy playouts per ply, ~137 worker-s/ply at ``c_tier1_rust`` W=30.
It is a DRAM-bound rollout campaign and must not share a box with a live eval
(memory ``feedback_no_agent_compute_beside_eval``).

Usage::

    python3 scripts/omm1/run_gate.py --workers 14 --out-dir <dir> [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import omm1_lib as L  # noqa: E402

_STATE: dict = {}


def _init_worker(profile: str, include_ref: bool, include_max: bool):
    L.prepare_env(profile)
    leaf_rs, _ = L.leaf_of_record()
    _STATE["leaf"] = leaf_rs
    _STATE["legs"] = L.leg_specs(include_ref=include_ref, include_max=include_max)


def run_one(row: dict, leaf_rs, legs, b: int, threads: int, bitexact: bool = True) -> dict:
    """One fired ply, all legs. Returns the raw record or an error record.

    `bitexact` runs the in-run `G-BITEXACT` re-derivation. It costs a FULL extra
    symmetric arbitration (`b x arms` playouts), i.e. ~25 % of a four-leg ply,
    so the launcher strides it (`--bitexact-stride`) rather than paying it at
    every ply: the bit-identity is a STRUCTURAL property pinned by
    `tiearb::tests::symmetric_leg_is_bit_identical_to_the_deployed_arbiter`, and
    the in-run check is corroboration on real positions, not the proof. Plies
    that skip it report `G_BITEXACT: null` and are excluded from the guard's
    denominator — never silently counted as passing.
    """
    import carc_rs

    t0 = time.time()
    try:
        out = carc_rs.tiearb_arbitrate_legs(
            str(row["deck_seed"]),
            list(row["prefix_actions"]),
            int(row["ply"]),
            int(row["champ_pick"]),
            leaf_rs,
            legs,
            b=b,
            j=L.ARM_CAP_J,
            eps=L.EPS,
            salt=L.SALT_OF_RECORD,
            max_plies=L.MAX_PLIES,
            threads=threads,
        )
    except Exception as exc:  # a tier1 playout failure is the whole-ply revert
        return {
            "rid": f"{row['deck_seed']}_p{row['ply']}",
            "corpus": row["corpus"],
            "deck_seed": row["deck_seed"],
            "ply": row["ply"],
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if out is None:
        # The frame said FIRED and the arbiter says it did not: a frame/runtime
        # disagreement is a G-FIRE-class defect, never a silently dropped ply.
        return {
            "rid": f"{row['deck_seed']}_p{row['ply']}",
            "corpus": row["corpus"],
            "deck_seed": row["deck_seed"],
            "ply": row["ply"],
            "ok": False,
            "error": "trigger did not fire at a ply the frame recorded as fired",
        }

    # ---- G-CRN ----------------------------------------------------------- #
    want_seeds = [
        L.stable_seed(L.SALT_OF_RECORD, out["state_digest"], row["ply"], j) for j in range(b)
    ]
    crn_ok = list(out["world_seeds"]) == want_seeds
    # ---- G-COMPLETE ------------------------------------------------------ #
    complete = all(int(lg["worlds_completed"]) == b for lg in out["legs"])
    # ---- G-BITEXACT (strided; see the docstring) -------------------------- #
    bitexact_ok = None
    if bitexact:
        solo = carc_rs.tiearb_arbitrate_legs(
            str(row["deck_seed"]),
            list(row["prefix_actions"]),
            int(row["ply"]),
            int(row["champ_pick"]),
            leaf_rs,
            [(L.LEG_SYM, [], None)],
            b=b,
            j=L.ARM_CAP_J,
            eps=L.EPS,
            salt=L.SALT_OF_RECORD,
            max_plies=L.MAX_PLIES,
            threads=1,
        )
        sym = next(lg for lg in out["legs"] if lg["name"] == L.LEG_SYM)
        bitexact_ok = bool(
            solo is not None
            and list(solo["arms"]) == list(out["arms"])
            and [float(x).hex() for x in solo["legs"][0]["means"]]
            == [float(x).hex() for x in sym["means"]]
        )

    return {
        "rid": f"{row['deck_seed']}_p{row['ply']}",
        "schema": L.SCHEMA,
        "corpus": row["corpus"],
        "deck_seed": row["deck_seed"],
        "game_id": row["game_id"],
        "ply": row["ply"],
        "seat": out["seat"],
        "k_remaining": out["k_remaining"],
        "phase_bucket": out["phase_bucket"],
        "state_digest": out["state_digest"],
        "arms": list(out["arms"]),
        "n_arms": len(out["arms"]),
        "capped": out["capped"],
        "champ_appended": out["champ_appended"],
        "n_distinct_afterstates": out["n_distinct_afterstates"],
        "b": b,
        "world_seeds": list(out["world_seeds"]),
        "n_playouts": out["n_playouts"],
        "legs": {
            lg["name"]: {
                "margins": [list(r) for r in lg["margins"]],
                "means": list(lg["means"]),
                "argmax_arm": lg["argmax_arm"],
                "worlds_completed": lg["worlds_completed"],
            }
            for lg in out["legs"]
        },
        "G_CRN": crn_ok,
        "G_COMPLETE": complete,
        # `None` == not checked at this ply (strided). A skipped check is NOT a
        # pass: the analyzer counts checked/passed separately.
        "G_BITEXACT": bitexact_ok,
        "ok": bool(crn_ok and complete and (bitexact_ok is not False)),
        "elapsed_s": time.time() - t0,
    }


class _Worker:
    """Picklable pool callable carrying `b` and the bit-exact stride. A
    spawn-context child cannot inherit a module global set in the parent after
    startup, so these ride in on the callable while the (expensive) leaf and
    legs are built once by the initializer.

    The stride is applied on a STABLE key — the frame's own row index, passed in
    with the row — so which plies get the `G-BITEXACT` check does not depend on
    `imap_unordered`'s completion order and is reproducible across re-runs."""

    def __init__(self, b: int, stride: int):
        self.b = b
        self.stride = max(1, stride)

    def __call__(self, item):
        idx, row = item
        return run_one(
            row,
            _STATE["leaf"],
            _STATE["legs"],
            self.b,
            1,
            bitexact=(idx % self.stride == 0),
        )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frame", type=Path, default=L.OUT_DIR / "FIRED_PLIES.jsonl")
    ap.add_argument("--out-dir", type=Path, default=L.OUT_DIR / "LEGS")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--threads", type=int, default=1, help="per-arbitration OS threads")
    ap.add_argument("--b", type=int, default=L.B_WORLDS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--profile", default="walled")
    ap.add_argument("--no-ref", action="store_true", help="omit the R_ref leg (smoke only)")
    ap.add_argument("--no-max", action="store_true", help="omit the R_max leg (smoke only)")
    ap.add_argument(
        "--bitexact-stride",
        type=int,
        default=1,
        help="run the in-run G-BITEXACT re-derivation on every Nth frame row "
        "(1 = every ply). It costs a full extra symmetric arbitration, so a "
        "stride trades corroboration breadth for ~25%% of the wall clock; the "
        "identity itself is pinned by a rust test.",
    )
    a = ap.parse_args(argv)

    if a.b != L.B_WORLDS:
        print(
            f"⚠️ DEVIATION: b={a.b} != the prereg's {L.B_WORLDS}. Record it in "
            "DEVIATIONS.md; the frozen bar was sized at B=64.",
            file=sys.stderr,
        )

    rows = [json.loads(x) for x in a.frame.read_text().splitlines() if x.strip()]
    if a.limit:
        rows = rows[: a.limit]

    L.prepare_env(a.profile)
    leaf_rs, leaf_hashes = L.leaf_of_record()
    legs = L.leg_specs(include_ref=not a.no_ref, include_max=not a.no_max)
    _STATE.update(leaf=leaf_rs, legs=legs, b=a.b)

    a.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = a.out_dir / f"legs_{os.uname().nodename}.jsonl"
    t0 = time.time()
    n_ok = 0
    n_done = 0
    with out_path.open("w") as fh:
        if a.workers > 1:
            import multiprocessing as mp

            ctx = mp.get_context("spawn")
            with ctx.Pool(
                a.workers,
                initializer=_init_worker,
                initargs=(a.profile, not a.no_ref, not a.no_max),
            ) as pool:
                worker = _Worker(a.b, a.bitexact_stride)
                for rec in pool.imap_unordered(worker, list(enumerate(rows)), chunksize=1):
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    n_ok += bool(rec.get("ok"))
                    n_done += 1
                    if n_done % 25 == 0:
                        print(
                            f"[{time.strftime('%H:%M:%S')}] {n_done}/{len(rows)} "
                            f"ok={n_ok} elapsed={time.time()-t0:.0f}s",
                            flush=True,
                        )
        else:
            for idx, row in enumerate(rows):
                rec = run_one(
                    row, leaf_rs, legs, a.b, a.threads,
                    bitexact=(idx % max(1, a.bitexact_stride) == 0),
                )
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                n_ok += bool(rec.get("ok"))
                n_done += 1
    elapsed = time.time() - t0

    mani = L.manifest(
        {
            "step": "run_gate",
            "leaf_hashes": leaf_hashes,
            "profile": a.profile,
            "b_used": a.b,
            "legs": [lg[0] for lg in legs],
            "n_rows": len(rows),
            "n_ok": n_ok,
            "n_voided": len(rows) - n_ok,
            "workers": a.workers,
            "threads": a.threads,
            "bitexact_stride": a.bitexact_stride,
            "elapsed_s": elapsed,
            "out": str(out_path),
        }
    )
    (a.out_dir / "manifest.json").write_text(json.dumps(mani, indent=2))
    print(json.dumps({k: mani[k] for k in ("n_rows", "n_ok", "n_voided", "elapsed_s")}, indent=2))
    # ⭐ THE DONE SIGNAL. Written LAST, only after manifest.json is on disk, so
    # its existence means "every row is flushed and the manifest describes them".
    # A watcher polls for this file; it must never be created on a partial run.
    (a.out_dir / "DONE").write_text(
        json.dumps(
            {
                "n_rows": len(rows),
                "n_ok": n_ok,
                "n_voided": len(rows) - n_ok,
                "elapsed_s": elapsed,
                "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "exit": 0 if n_ok == len(rows) else 3,
            },
            indent=2,
        )
    )
    return 0 if n_ok == len(rows) else 3


if __name__ == "__main__":
    raise SystemExit(main())
