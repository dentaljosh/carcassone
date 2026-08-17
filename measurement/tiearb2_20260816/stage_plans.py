#!/usr/bin/env python3
"""PLAN SURGERY for `measurement/tiearb2_20260816` — it scores NOTHING and reads
no oracle VALUE, no mean, no sd and no statistic. It only cuts existing plan dirs
into the shapes `run_tiletie.py` consumes.

Two subcommands:

  `pilot`  — stage `positions_pilot/` from the **SPENT** pricing corpus
             (`measurement/tiletie_pricing_20260812/positions_pooled`), restricted
             to the OOF run's own 20 cost-pilot rids
             (`measurement/tiletie_oof_20260814/PILOT_RIDS.json`). Those positions
             are burned for inference (DESIGN §10) and are used here for a
             plumbing + cost check only.

  `main`   — write `POSITION_ORDER.json` (ONE shuffle, seed 20260816, of the
             SORTED rid list of the FRESH corpus) and cut it into `--chunks`
             near-equal SEQUENTIAL chunks, one `run_tiletie`-shaped plan dir each.

⚠️ WHY THE PERMUTATION EXISTS (DESIGN §10). `oracle_score_pilot.load_positions_jsonl`
sorts by `root_id`, so a *line-order* prefix of a leg file is composition-biased.
Cutting a committed seeded permutation into chunks makes **any completed-chunk
prefix a uniform random subsample**, so a partial run is still an unbiased read at
its realized `n`.

⚠️ CHUNK MEMBERSHIP IS DEFINED ONCE AND SHARED BY BOTH JUDGES. `clair-puct` and
`tier1-greedy` must score the *identical* rid set per chunk or the cross-judge CRN
join (`G-CRN`) and the analyser's per-position pairing break. Every invocation
reads `POSITION_ORDER.json` rather than re-deriving from scratch; `--verify`
re-derives and asserts byte-identity so a drifted order is caught, never silently
used.

The heavy lifting is **imported, not reimplemented**: `build_tiearb_plan.py`'s
`write_plan_dir`, `read_leg_files`, `committed_order` and `chunk_slices` are the
same, already-tested functions that built the Stage-1 plan. Only the run-identity
metadata inside `POSITIONS_PLAN.json` is re-stamped for this run.

Nothing here reads a record, a value or a statistic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))

import build_tiearb_plan as BTP  # noqa: E402  (path insert must precede the import)

RUN_ID = "tiearb2_20260816"
RUN_DIR = REPO / "measurement" / RUN_ID
SCHEMA = "carcassonne-tiearb2-plan/v1"
DESIGN_DOC = f"measurement/{RUN_ID}/DESIGN.md"
READ_RULE = f"measurement/{RUN_ID}/READ_RULE.md"

#: DESIGN §10 — ONE committed seed, one shuffle, written BEFORE launch.
PERMUTATION_SEED = 20260816
DEFAULT_CHUNKS = 4

SPENT_POOLED = REPO / "measurement/tiletie_pricing_20260812/positions_pooled"
OOF_PILOT_RIDS = REPO / "measurement/tiletie_oof_20260814/PILOT_RIDS.json"
FRESH_POSITIONS = RUN_DIR / "corpus/positions"


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #
def _die(msg: str) -> "NoReturn":  # noqa: F821
    raise SystemExit(f"REFUSING: {msg}")


def _load_plan_dir(src: Path) -> tuple:
    for name in ("POSITIONS_PLAN.json", "ARMS.json", "DROPPED_ALL_TRANSPOSITION.json"):
        if not (src / name).is_file():
            _die(f"{src} is not a plan dir (missing {name})")
    plan = json.loads((src / "POSITIONS_PLAN.json").read_text())
    arms = json.loads((src / "ARMS.json").read_text())
    dropped = json.loads((src / "DROPPED_ALL_TRANSPOSITION.json").read_text())
    return plan, arms, dropped


def _restamp(out_dir: Path, *, label: str, source_dir: Path) -> dict:
    """Re-stamp the run identity inside a freshly-written POSITIONS_PLAN.json.

    `build_tiearb_plan.write_plan_dir` hard-codes Stage 1's `design_doc` /
    `read_rule` strings (it was written for that run). Everything else it emits —
    the leg files, ARMS, the dedupe block, the counts — is exactly what this run
    needs, so the plan is re-stamped rather than the writer re-implemented.
    Deterministic: same `json.dumps(indent=1)` shape in and out.
    """
    p = out_dir / "POSITIONS_PLAN.json"
    plan = json.loads(p.read_text())
    plan["schema"] = SCHEMA
    plan["design_doc"] = DESIGN_DOC
    plan["read_rule"] = READ_RULE
    plan["label"] = label
    plan["run_id"] = RUN_ID
    plan["source_plan_dir"] = str(source_dir)
    plan["permutation_seed"] = PERMUTATION_SEED
    # `slice` is Stage-1 vocabulary (dev/holdout). This run has no such carve —
    # the S1/S2 half-split is made by split_tiearb2.py AFTER scoring, on roots.
    plan.pop("slice", None)
    p.write_text(json.dumps(plan, indent=1))
    return plan


def _sha256_list(items) -> str:
    h = hashlib.sha256()
    for s in items:
        h.update(str(s).encode())
        h.update(b"\n")
    return h.hexdigest()


def _read_exclude(path) -> list:
    if not path:
        return []
    p = Path(path)
    if not p.is_file():
        _die(f"--exclude-rids file not found: {p}")
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return sorted(set(out))


def _rid_set(plan_dir: Path) -> set:
    return set(json.loads((plan_dir / "ARMS.json").read_text()))


# --------------------------------------------------------------------------- #
# pilot                                                                        #
# --------------------------------------------------------------------------- #
def cmd_pilot(a) -> int:
    src = Path(a.source_dir)
    out_dir = Path(a.out_dir)
    plan, arms, dropped = _load_plan_dir(src)
    rids = list(json.loads(Path(a.pilot_rids).read_text())["rids"])

    unknown = sorted(r for r in rids if r not in arms)
    if unknown:
        _die(f"pilot rid(s) absent from {src}/ARMS.json: {unknown[:5]}")

    if a.verify:
        if not (out_dir / "ARMS.json").is_file():
            _die(f"--verify: {out_dir} has not been staged yet")
        have = _rid_set(out_dir)
        if have != set(rids):
            _die(f"--verify: {out_dir} holds {len(have)} rids, PILOT_RIDS names "
                 f"{len(set(rids))}; sets differ")
        print(f"[stage_plans] VERIFY OK — {out_dir} holds exactly the "
              f"{len(have)} OOF cost-pilot rids")
        return 0

    leg_rows = BTP.read_leg_files(src, plan)
    # holdout=set() + require_holdout=False -> write_plan_dir's mirror guard
    # ("no kept rid may be a holdout root") is vacuously satisfied. This run has
    # no holdout carve at all; the guard that matters here is the `unknown` check
    # above, which already ran.
    BTP.write_plan_dir(out_dir, set(rids), source_plan=plan, source_arms=arms,
                       dropped=dropped, leg_rows=leg_rows, label="pilot",
                       holdout=set(), require_holdout=False)
    stamped = _restamp(out_dir, label="pilot", source_dir=src)

    summary = {
        "schema": SCHEMA,
        "label": "pilot",
        "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE,
        "note": ("DESIGN §10 cost/integrity pilot. Positions come from the SPENT "
                 "2026-08-12 corpus and are burned for inference; the pilot reads "
                 "ONLY wall-clock / integrity / a bit-reproduction COUNT."),
        "source_plan_dir": str(src),
        "pilot_rids_source": str(a.pilot_rids),
        "n_positions": stamped["n_positions"],
        "n_roots": stamped["n_roots"],
        "total_legs": stamped["total_legs"],
        "total_arm_playouts": stamped["total_arm_playouts"],
        "counts_by_profile_leg": stamped["counts_by_profile_leg"],
        "counts_by_stratum": stamped["counts_by_stratum"],
        "world_seed_salt": stamped["world_seed_salt"],
        "m_worlds": stamped["m_worlds"],
        "out_dir": str(out_dir),
    }
    (RUN_DIR / "PLAN_SUMMARY_pilot.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def build_order_doc(arms: dict, excluded: list, n_chunks: int, exclude_path) -> tuple:
    """The committed order document + the chunk rid lists. Pure and deterministic."""
    excl = set(excluded)
    rids = sorted(r for r in arms if r not in excl)
    if not rids:
        _die("the fresh corpus has no rids left after --exclude-rids")
    order = BTP.committed_order(rids, seed=PERMUTATION_SEED)
    chunks = BTP.chunk_slices(order, n_chunks)
    flat = [r for c in chunks for r in c]
    if sorted(flat) != rids or len(flat) != len(set(flat)):
        _die("chunks do not partition the fresh corpus exactly")
    doc = {
        "schema": SCHEMA,
        "run_id": RUN_ID,
        "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE,
        "seed": PERMUTATION_SEED,
        "n": len(order),
        "n_roots": len({arms[r]["root_id"] for r in order}),
        "chunks": n_chunks,
        "chunk_sizes": [len(c) for c in chunks],
        "note": ("DESIGN §10 — ONE committed shuffle of the SORTED rid list of the "
                 "FRESH corpus, written BEFORE launch. load_positions_jsonl sorts by "
                 "root_id, so partial completion is unbiased at CHUNK granularity "
                 "only. BOTH judges score the identical rid set per chunk — chunk "
                 "membership is defined here and nowhere else."),
        "exclude_rids": {
            "path": str(exclude_path) if exclude_path else None,
            "n": len(excl),
            "sha256": _sha256_list(sorted(excl)) if excl else None,
        },
        "sha256_order": _sha256_list(order),
        "order": order,
    }
    return doc, chunks


def cmd_main(a) -> int:
    src = Path(a.source_dir)
    out = Path(a.out_dir)
    plan, arms, dropped = _load_plan_dir(src)
    excluded = _read_exclude(a.exclude_rids)
    bad = sorted(r for r in excluded if r not in arms)
    if bad:
        _die(f"--exclude-rids names rid(s) not in the fresh corpus: {bad[:5]}")

    doc, chunks = build_order_doc(arms, excluded, a.chunks, a.exclude_rids)
    order_path = out / "POSITION_ORDER.json"
    payload = json.dumps(doc, indent=1) + "\n"

    if a.verify:
        if not order_path.is_file():
            _die(f"--verify: {order_path} does not exist — stage the plan first")
        on_disk = order_path.read_text()
        if on_disk != payload:
            _die(f"--verify: {order_path} is NOT byte-identical to the re-derivation "
                 f"from seed {PERMUTATION_SEED}. The chunk membership on disk does "
                 f"not match this corpus + exclusion list. DO NOT LAUNCH.")
        for i, ch in enumerate(chunks, 1):
            d = out / f"positions_chunk{i}"
            if not (d / "ARMS.json").is_file():
                _die(f"--verify: {d} has not been staged")
            have = _rid_set(d)
            if have != set(ch):
                _die(f"--verify: {d} holds {len(have)} rids, the committed order "
                     f"says {len(ch)}; sets differ. DO NOT LAUNCH.")
            cp = json.loads((d / "POSITIONS_PLAN.json").read_text())
            for key, info in (cp.get("files") or {}).items():
                p = Path(info["path"])
                n = sum(1 for ln in p.read_text().splitlines() if ln.strip())
                if n != int(info["n"]):
                    _die(f"--verify: {p} has {n} lines, its plan says {info['n']}")
        print(f"[stage_plans] VERIFY OK — POSITION_ORDER.json byte-identical "
              f"(seed {PERMUTATION_SEED}, n={doc['n']}, roots={doc['n_roots']}, "
              f"chunks={doc['chunk_sizes']})")
        return 0

    leg_rows = BTP.read_leg_files(src, plan)
    out.mkdir(parents=True, exist_ok=True)
    order_path.write_text(payload)

    written = {}
    for i, ch in enumerate(chunks, 1):
        d = out / f"positions_chunk{i}"
        BTP.write_plan_dir(d, set(ch), source_plan=plan, source_arms=arms,
                           dropped=dropped, leg_rows=leg_rows, label=f"chunk{i}",
                           holdout=set(), require_holdout=False)
        written[f"chunk{i}"] = _restamp(d, label=f"chunk{i}", source_dir=src)

    summary = {
        "schema": SCHEMA,
        "label": "main",
        "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE,
        "permutation_seed": PERMUTATION_SEED,
        "source_plan_dir": str(src),
        "n_positions": doc["n"],
        "n_roots": doc["n_roots"],
        "n_excluded": doc["exclude_rids"]["n"],
        "sha256_order": doc["sha256_order"],
        "chunks": [
            {"name": f"chunk{i}", "n": written[f"chunk{i}"]["n_positions"],
             "roots": written[f"chunk{i}"]["n_roots"],
             "legs": written[f"chunk{i}"]["total_legs"],
             "playouts": written[f"chunk{i}"]["total_arm_playouts"],
             "counts_by_profile_leg": written[f"chunk{i}"]["counts_by_profile_leg"],
             "out_dir": written[f"chunk{i}"]["out_dir"]}
            for i in range(1, a.chunks + 1)],
        "totals": {
            "legs": sum(w["total_legs"] for w in written.values()),
            "playouts": sum(w["total_arm_playouts"] for w in written.values()),
            "mean_arms": plan.get("mean_arms"),
        },
        "governance": ("Measurement only, 0 strength games on every branch. "
                       "No results.csv row, no band, no claim id."),
    }
    (RUN_DIR / "PLAN_SUMMARY.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pilot", help="stage positions_pilot from the SPENT corpus")
    p.add_argument("--source-dir", default=str(SPENT_POOLED))
    p.add_argument("--pilot-rids", default=str(OOF_PILOT_RIDS))
    p.add_argument("--out-dir", default=str(RUN_DIR / "positions_pilot"))
    p.add_argument("--verify", action="store_true",
                   help="assert the staged dir holds exactly the pilot rids")
    p.set_defaults(fn=cmd_pilot)

    m = sub.add_parser("main", help="write POSITION_ORDER.json + the chunk plan dirs")
    m.add_argument("--source-dir", default=str(FRESH_POSITIONS))
    m.add_argument("--out-dir", default=str(RUN_DIR))
    m.add_argument("--chunks", type=int, default=DEFAULT_CHUNKS)
    m.add_argument("--exclude-rids", default=None,
                   help="optional file of rids to drop before the permutation "
                        "(one per line, '#' comments). Recorded in "
                        "POSITION_ORDER.json by count + sha256.")
    m.add_argument("--verify", action="store_true",
                   help="re-derive and assert byte-identity with POSITION_ORDER.json "
                        "and rid-set identity with every chunk dir")
    m.set_defaults(fn=cmd_main)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
