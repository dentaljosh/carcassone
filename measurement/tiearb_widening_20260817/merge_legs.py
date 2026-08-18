#!/usr/bin/env python3
"""MERGE the per-chunk scoring output of the tie-arbiter WIDENING two-box run
back into the EXACT layout the frozen `READ_RULE.md` addresses.

    SHARE/<RUN_ID>/chunks/<stratum>/chunk<k>/<judge>/<profile>/leg<N>/records/<rid>.json
        ->  SHARE/<RUN_ID>/<stratum>/<judge>/<profile>/leg<N>/records/<rid>.json
    ... plus one merged per-leg `manifest.json`, and one merged
        `RUN/RUN_MANIFEST_{S1,S2}.json`.

`build_widening_corpus.sh` phase 6 then copies every `manifest.json` from
`SHARE/<RUN_ID>/<stratum>/` back to `RUN/legs/<stratum>/…` — the address
`G-SALT` / `G-M` / `G-BACKEND` / `G-PREFIX` read.  `G-CRN`'s per-record fallback
reads `SHARE/{s1,s2}/tier1-greedy/walled/leg<N>/records/<rid>.json` directly,
which is exactly what this script assembles.

──────────────────────────────────────────────────────────────────────────────
⚠️ BLINDNESS.  This script NEVER OPENS A RECORD.  A record's rid is taken from
its FILE NAME (`records/<rid>.json`) and its bytes are copied with `shutil.copy2`,
so no value, mean, sd, `arb`, `ora`, `Δ` or CI passes through this process.  The
per-leg `summary.json` that `oracle_score_pilot` writes DOES carry outcome
statistics; it is copied verbatim to `summary_chunk<k>.json` and is **never
parsed and never aggregated** — a merged summary would be a computed statistic,
which this layer has no licence to produce.

⚠️ COMPLETENESS IS THE POINT.  Every rid the corpus plan places on a leg must
appear on that leg EXACTLY ONCE, for BOTH judges.  A gap or a duplicate exits
non-zero and names the rids.  A duplicate whose bytes differ is a hard error
(two boxes produced different output for one rid — the neutrality claim would be
false); a duplicate whose bytes are IDENTICAL is still an error, because it means
a chunk was merged twice or the allocation double-assigned it.

⚠️ IDENTITY-REQUIRED MANIFEST FIELDS.  The gate-addressed fields of a per-leg
manifest (`resolved_config.world_seed_salt`, `.m`, `.legal_mask_cache`,
`preflight.seeds.{ok,prefix_stable_at,derivation}`, `git_rev`, …) are asserted
EQUAL across every contributing chunk before the merged manifest carries them.
They are properties of `(salt, m)` and of the code revision, never of the box, so
divergence means a mixed-rev or mis-configured run and MUST fail loudly rather
than be averaged away.  Counters are summed; per-chunk-varying fields
(`workers`, `host`, wall clocks, paths) move into the merged `merge` block.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

RUN_ID = "tiearb_widening_20260817"
CAMPAIGN = REPO / "measurement" / RUN_ID
RUN_DIR = CAMPAIGN / "shared_run"
SCHEMA = "carcassonne-tiearb-widening-merge/v1"

STRATA = ("s1", "s2")
JUDGES = ("tier1-greedy", "clair-puct")
PROFILE = "walled"

#: `RUN_MANIFEST_{S1,S2}.json` — the READ_RULE spells the stratum UPPERCASE.
RUN_MANIFEST_NAME = {"s1": "RUN_MANIFEST_S1.json", "s2": "RUN_MANIFEST_S2.json"}


# --------------------------------------------------------------------------- #
# manifest-merge policy                                                        #
# --------------------------------------------------------------------------- #
#: Summed across chunks. Pure counters — no statistic, no value.
AGGREGATE_SUM = frozenset({
    "n_rows_in", "n_scored", "n_ok", "n_failed", "n_crn_verified",
    "n_playouts", "elapsed_secs_sum", "wall_secs",
})

#: Set-unioned and sorted.
AGGREGATE_UNION = frozenset({"errors"})

#: Legitimately per-chunk. Recorded under `merge.by_chunk`, and the merged
#: manifest carries the LOWEST-INDEXED chunk's value so the key keeps its type.
PER_CHUNK = frozenset({
    "generated_utc", "started_utc", "finished_utc", "python", "host",
    "workers", "n", "out_root", "out_subdir", "sampling", "source",
    "positions_jsonl", "positions_plan_path", "arms_path",
    "positions_plan_sha256", "arms_sha256", "legs", "resume",
    "wall_cap_secs",
})

#: Nested paths inside `resolved_config` that legitimately vary per chunk.
RESOLVED_CONFIG_PER_CHUNK = frozenset({
    "positions_jsonl", "n", "workers", "out_root", "out_subdir", "resume",
})

#: Dotted paths that MUST agree across every chunk of a leg. A divergence here
#: is a mixed-rev / mis-configured run, never a throughput artefact.
IDENTITY_REQUIRED = (
    "schema", "driver", "harness", "design_doc", "git_rev", "code_rev",
    "judge", "profile", "leg", "m_worlds", "rules_profile", "max_plies",
    "resolved_config.world_seed_salt",
    "resolved_config.m",
    "resolved_config.legal_mask_cache",
    "resolved_config.rules_profile",
    "resolved_config.oracle_policy",
    "resolved_config.arb_backend",
    "preflight.seeds.ok",
    "preflight.seeds.prefix_stable_at",
    "preflight.seeds.derivation",
    "crn.seed_derivation",
    "oracle.policy",
)

#: The same discipline for the per-invocation `RUN_MANIFEST_*` files. These are
#: the exact scalars READ_RULE §2 addresses (G-SALT / G-M / G-BACKEND / G-LEAF).
RUN_MANIFEST_IDENTITY = (
    "schema", "driver", "design_doc", "git_rev",
    "world_seed_salt", "m_worlds", "m_max", "b_ceiling_from_m",
    "arb_backend", "arb_legal_mask_cache", "oracle_sims",
    "preflight.checks.leaf_hash.ok",
    "preflight.checks.leaf_hash.harness_leaf_hash",
    "preflight.checks.leaf_hash.expected",
)

_MISSING = object()


def _get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return _MISSING
        cur = cur[part]
    return cur


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _canon(v) -> str:
    return json.dumps(v, sort_keys=True, default=str)


class MergeError(RuntimeError):
    pass


def merge_manifests(by_chunk: dict, *, identity_required=IDENTITY_REQUIRED,
                    allow_varying=()) -> dict:
    """Merge {chunk_index: manifest dict} into one.

    Fail-closed: an unclassified key whose value differs across chunks raises.
    """
    if not by_chunk:
        raise MergeError("merge_manifests called with zero manifests")
    order = sorted(by_chunk)
    first = by_chunk[order[0]]
    allow = set(allow_varying)

    # 1) identity-required paths
    for dotted in identity_required:
        vals = {k: _get(m, dotted) for k, m in by_chunk.items()}
        present = {k: v for k, v in vals.items() if v is not _MISSING}
        if not present:
            continue
        if len(present) != len(vals):
            missing = sorted(k for k, v in vals.items() if v is _MISSING)
            raise MergeError(
                f"identity-required path {dotted!r} is present on some chunks but "
                f"absent on {missing} — a leg cannot be half-configured")
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) != 1:
            raise MergeError(
                f"identity-required path {dotted!r} DIVERGES across chunks: "
                + "; ".join(f"chunk{k}={_canon(v)}" for k, v in sorted(present.items())))

    merged = json.loads(json.dumps(first))
    keys = sorted({k for m in by_chunk.values() for k in m})
    per_chunk_block: dict = {str(k): {} for k in order}
    divergent = []

    for key in keys:
        vals = {k: m.get(key, _MISSING) for k, m in by_chunk.items()}
        present = {k: v for k, v in vals.items() if v is not _MISSING}
        if key in AGGREGATE_SUM:
            nums = [v for v in present.values() if isinstance(v, (int, float))]
            merged[key] = round(sum(nums), 3) if any(
                isinstance(v, float) for v in nums) else sum(nums)
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            continue
        if key in AGGREGATE_UNION:
            acc = set()
            for v in present.values():
                acc.update(v or [])
            merged[key] = sorted(acc)
            continue
        if key in PER_CHUNK:
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            merged[key] = present[min(present)]
            continue
        if key == "resolved_config":
            merged[key] = _merge_resolved_config(present, per_chunk_block)
            continue
        distinct = {_canon(v) for v in present.values()}
        if len(distinct) == 1 and len(present) == len(vals):
            merged[key] = present[min(present)]
            continue
        if key in allow:
            for k, v in present.items():
                per_chunk_block[str(k)][key] = v
            merged[key] = present[min(present)]
            divergent.append(key)
            continue
        raise MergeError(
            f"key {key!r} differs across chunks and has no merge rule "
            f"(classify it in AGGREGATE_SUM / PER_CHUNK / IDENTITY_REQUIRED, or "
            f"pass --allow-varying {key}). "
            + "; ".join(f"chunk{k}={_canon(v)[:120]}" for k, v in sorted(present.items())))

    merged["merge"] = {
        "schema": SCHEMA,
        "run_id": RUN_ID,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chunks": order,
        "note": ("A TWO-BOX merge of per-chunk legs. Counters are summed; "
                 "gate-addressed fields were asserted IDENTICAL across chunks "
                 "before being carried. Per-chunk values are below. "
                 "wall_secs is a SUM across chunks that ran on different boxes "
                 "and possibly concurrently — it is NOT a wall clock and is not "
                 "the cost currency of record (DESIGN §7 costs from "
                 "elapsed_secs)."),
        "by_chunk": per_chunk_block,
        "wall_secs_max": max(
            [float(m.get("wall_secs") or 0.0) for m in by_chunk.values()] or [0.0]),
        "divergent_keys_allowed": sorted(divergent),
    }
    return merged


def _merge_resolved_config(present: dict, per_chunk_block: dict) -> dict:
    order = sorted(present)
    merged = json.loads(json.dumps(present[order[0]]))
    keys = sorted({k for v in present.values() for k in v})
    for key in keys:
        vals = {k: v.get(key, _MISSING) for k, v in present.items()}
        have = {k: v for k, v in vals.items() if v is not _MISSING}
        if key in RESOLVED_CONFIG_PER_CHUNK:
            for k, v in have.items():
                per_chunk_block[str(k)].setdefault("resolved_config", {})[key] = v
            if key == "n":
                merged[key] = sum(v for v in have.values() if isinstance(v, int))
            elif key == "resume":
                merged[key] = any(bool(v) for v in have.values())
            else:
                merged[key] = None       # explicitly NOT one chunk's value
            continue
        distinct = {_canon(v) for v in have.values()}
        if len(distinct) != 1:
            raise MergeError(
                f"resolved_config.{key} diverges across chunks and is not in "
                f"RESOLVED_CONFIG_PER_CHUNK: "
                + "; ".join(f"chunk{k}={_canon(v)}" for k, v in sorted(have.items())))
        merged[key] = have[min(have)]
    return merged


# --------------------------------------------------------------------------- #
# expected rid sets — read from the CORPUS plan, not from what happened to run  #
# --------------------------------------------------------------------------- #
def expected_leg_rids(positions_dir: Path) -> dict:
    """{"<profile>/leg<r>": {rid, ...}} from the CORPUS positions dir.

    This is the denominator of the completeness check: what the run was
    SUPPOSED to produce, independent of which chunks reported.
    """
    plan = json.loads((Path(positions_dir) / "POSITIONS_PLAN.json").read_text())
    out = {}
    for key, info in sorted((plan.get("files") or {}).items()):
        p = Path(info["path"])
        if not p.is_file():
            p = Path(positions_dir) / Path(info["path"]).name
        if not p.is_file():
            raise MergeError(f"missing corpus leg file for {key}: {info['path']}")
        rids = set()
        for ln in p.read_text().splitlines():
            if ln.strip():
                rids.add(json.loads(ln)["rid"])
        if len(rids) != int(info["n"]):
            raise MergeError(f"{p}: {len(rids)} distinct rids but plan says {info['n']}")
        out[key] = rids
    return out


def chunk_dirs(chunks_root: Path) -> dict:
    """{chunk_index: dir} for every `chunk<k>` under `chunks_root`."""
    out = {}
    root = Path(chunks_root)
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name.startswith("chunk"):
            try:
                out[int(d.name[len("chunk"):])] = d
            except ValueError:
                continue
    return out


# --------------------------------------------------------------------------- #
# the merge                                                                    #
# --------------------------------------------------------------------------- #
def merge_stratum(*, stratum: str, chunks_root: Path, out_dir: Path,
                  positions_dir: Path, judges=JUDGES, dry_run: bool = False,
                  allow_varying=()) -> dict:
    chunks_root, out_dir = Path(chunks_root), Path(out_dir)
    expected = expected_leg_rids(positions_dir)
    cdirs = chunk_dirs(chunks_root)
    report = {
        "schema": SCHEMA, "run_id": RUN_ID, "stratum": stratum,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chunks_root": str(chunks_root), "out_dir": str(out_dir),
        "positions_dir": str(positions_dir),
        "chunks_found": sorted(cdirs),
        "expected_legs": {k: len(v) for k, v in sorted(expected.items())},
        "judges": list(judges), "dry_run": bool(dry_run),
        "legs": {}, "problems": [], "ok": False,
        "n_records_copied": 0, "n_records_present": 0,
    }
    if not cdirs:
        report["problems"].append(f"no chunk dirs under {chunks_root}")
        return report

    for judge in judges:
        for leg_key, want in sorted(expected.items()):
            profile, leg_tag = leg_key.split("/leg")
            dst_leg = out_dir / judge / profile / f"leg{leg_tag}"
            dst_records = dst_leg / "records"
            owner: dict = {}
            dupes, mismatched = [], []
            copied = 0

            for k in sorted(cdirs):
                src_records = cdirs[k] / judge / profile / f"leg{leg_tag}" / "records"
                if not src_records.is_dir():
                    continue
                for f in sorted(src_records.glob("*.json")):
                    rid = f.stem                       # ⚠️ NEVER opened for values
                    if rid in owner:
                        dupes.append({"rid": rid, "chunks": [owner[rid][0], k]})
                        if _sha256_file(owner[rid][1]) != _sha256_file(f):
                            mismatched.append(rid)
                        continue
                    owner[rid] = (k, f)
                    if not dry_run:
                        dst_records.mkdir(parents=True, exist_ok=True)
                        target = dst_records / f.name
                        if target.exists() and _sha256_file(target) == _sha256_file(f):
                            pass                       # idempotent re-merge
                        else:
                            shutil.copy2(f, target)
                            copied += 1

            got = set(owner)
            missing = sorted(want - got)
            extra = sorted(got - want)
            leg_report = {
                "n_expected": len(want), "n_present": len(got),
                "n_copied": copied,
                "n_missing": len(missing), "missing": missing[:20],
                "n_extra": len(extra), "extra": extra[:20],
                "n_duplicate": len(dupes), "duplicates": dupes[:20],
                "n_duplicate_bytes_differ": len(mismatched),
                "duplicates_bytes_differ": mismatched[:20],
                "by_chunk": {str(k): sum(1 for v in owner.values() if v[0] == k)
                             for k in sorted(cdirs)},
                "ok": not missing and not extra and not dupes,
            }
            report["legs"][f"{judge}/{leg_key}"] = leg_report
            report["n_records_copied"] += copied
            report["n_records_present"] += len(got)
            if missing:
                report["problems"].append(
                    f"{judge}/{leg_key}: {len(missing)} rid(s) MISSING "
                    f"(first: {missing[:3]})")
            if extra:
                report["problems"].append(
                    f"{judge}/{leg_key}: {len(extra)} rid(s) NOT in the corpus plan "
                    f"(first: {extra[:3]})")
            if dupes:
                report["problems"].append(
                    f"{judge}/{leg_key}: {len(dupes)} DUPLICATE rid(s) across chunks "
                    f"({len(mismatched)} with differing bytes) — a chunk was merged "
                    f"twice or the allocation double-assigned it")

            # ---- per-leg manifest merge ------------------------------------ #
            mans, man_paths = {}, {}
            for k in sorted(cdirs):
                mp = cdirs[k] / judge / profile / f"leg{leg_tag}" / "manifest.json"
                if mp.is_file():
                    mans[k] = json.loads(mp.read_text())
                    man_paths[k] = mp
            if mans:
                try:
                    merged = merge_manifests(mans, allow_varying=allow_varying)
                except MergeError as exc:
                    report["problems"].append(f"{judge}/{leg_key}: manifest merge: {exc}")
                    leg_report["manifest_ok"] = False
                    leg_report["manifest_error"] = str(exc)
                else:
                    merged["merge"]["sources"] = {
                        str(k): {"path": str(p), "sha256": _sha256_file(p)}
                        for k, p in sorted(man_paths.items())}
                    merged["merge"]["records_by_chunk"] = leg_report["by_chunk"]
                    leg_report["manifest_ok"] = True
                    if not dry_run:
                        dst_leg.mkdir(parents=True, exist_ok=True)
                        (dst_leg / "manifest.json").write_text(
                            json.dumps(merged, indent=2, sort_keys=True))
            else:
                leg_report["manifest_ok"] = None

            # ---- summary.json: copied VERBATIM, never parsed ---------------- #
            if not dry_run:
                for k in sorted(cdirs):
                    sp = cdirs[k] / judge / profile / f"leg{leg_tag}" / "summary.json"
                    if sp.is_file():
                        dst_leg.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(sp, dst_leg / f"summary_chunk{k}.json")

    report["ok"] = not report["problems"]
    return report


def merge_run_manifest(*, stratum: str, manifests_dir: Path, out_path: Path,
                       judges=JUDGES, dry_run: bool = False,
                       allow_varying=()) -> dict:
    """Merge the per-(judge, chunk) `RUN_MANIFEST_*` files into the single
    `RUN/RUN_MANIFEST_{S1,S2}.json` the READ_RULE addresses."""
    manifests_dir = Path(manifests_dir)
    S = stratum.upper()
    found = {}
    for judge in judges:
        for p in sorted(manifests_dir.glob(f"RUN_MANIFEST_{S}_{judge}_chunk*.json")):
            k = p.name.split("_chunk")[-1][: -len(".json")]
            found[f"{judge}#{k}"] = (p, json.loads(p.read_text()))
    out = {"schema": SCHEMA, "stratum": S, "out_path": str(out_path),
           "n_sources": len(found), "sources": sorted(str(p) for p, _ in found.values()),
           "ok": False, "problems": []}
    if not found:
        out["problems"].append(f"no RUN_MANIFEST_{S}_*_chunk*.json under {manifests_dir}")
        return out
    try:
        merged = merge_manifests(
            {i: m for i, (_, m) in enumerate(
                (v for _, v in sorted(found.items())), start=1)},
            identity_required=RUN_MANIFEST_IDENTITY,
            # these four are recomputed below (union / superset), so a
            # per-invocation difference is expected rather than a defect
            allow_varying=set(allow_varying) | {"judges", "judge_backend",
                                                "r9_by_profile",
                                                "resolved_backend_by_leg"})
    except MergeError as exc:
        out["problems"].append(f"RUN_MANIFEST merge: {exc}")
        return out

    # resolved_backend_by_leg is a UNION across (judge, chunk) invocations —
    # G-BACKEND requires every `tier1-greedy/walled` entry to read `rust`, and no
    # single invocation carries them all.
    union, conflicts = {}, []
    for _, (_p, m) in sorted(found.items()):
        for k, v in (m.get("resolved_backend_by_leg") or {}).items():
            if k in union and union[k] != v:
                conflicts.append({"leg": k, "values": sorted({union[k], v})})
            union[k] = v
    if conflicts:
        out["problems"].append(f"resolved_backend_by_leg CONFLICTS: {conflicts[:5]}")
        return out
    merged["resolved_backend_by_leg"] = dict(sorted(union.items()))
    merged["judges"] = sorted({j for _p, m in found.values()
                               for j in (m.get("judges") or [])})
    merged["judge_backend"] = {}
    for _, (_p, m) in sorted(found.items()):
        merged["judge_backend"].update(m.get("judge_backend") or {})
    merged["merge"]["sources"] = {
        key: {"path": str(p), "sha256": _sha256_file(p)}
        for key, (p, _) in sorted(found.items())}
    merged["merge"]["note"] += (
        " RUN_MANIFEST flavour: resolved_backend_by_leg is the UNION over every "
        "(judge, chunk) invocation — no single invocation carries every leg, and "
        "G-BACKEND quantifies over all of them.")

    if not dry_run:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(merged, indent=2, sort_keys=True))
    out["ok"] = True
    return out


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stratum", required=True, choices=list(STRATA))
    ap.add_argument("--chunks-root", required=True,
                    help="SHARE/<RUN_ID>/chunks/<stratum>")
    ap.add_argument("--out-dir", required=True, help="SHARE/<RUN_ID>/<stratum>")
    ap.add_argument("--positions-dir", default=None,
                    help="the CORPUS positions dir (default: "
                         "shared_run/corpus/positions_<stratum>) — the "
                         "completeness DENOMINATOR")
    ap.add_argument("--manifests-dir", default=str(CAMPAIGN / "chunks" / "manifests"),
                    help="where run_scoring.sh wrote the per-chunk RUN_MANIFEST_*")
    ap.add_argument("--run-manifest-out", default=None,
                    help="default: shared_run/RUN_MANIFEST_{S1,S2}.json")
    ap.add_argument("--report", default=None,
                    help="default: <campaign>/MERGE_REPORT_<stratum>.json")
    ap.add_argument("--judges", nargs="+", default=list(JUDGES))
    ap.add_argument("--allow-varying", nargs="*", default=[],
                    help="manifest keys allowed to differ across chunks "
                         "(recorded in merge.by_chunk instead of failing)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only: copy nothing, write nothing")
    ap.add_argument("--no-run-manifest", action="store_true",
                    help="skip the RUN_MANIFEST merge (leg merge only)")
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    stratum = a.stratum
    positions_dir = Path(a.positions_dir or (RUN_DIR / "corpus" / f"positions_{stratum}"))
    report_path = Path(a.report or (CAMPAIGN / f"MERGE_REPORT_{stratum}.json"))

    rep = merge_stratum(stratum=stratum, chunks_root=Path(a.chunks_root),
                        out_dir=Path(a.out_dir), positions_dir=positions_dir,
                        judges=tuple(a.judges), dry_run=a.dry_run,
                        allow_varying=a.allow_varying)

    if not a.no_run_manifest and not rep["problems"]:
        out_path = Path(a.run_manifest_out or (RUN_DIR / RUN_MANIFEST_NAME[stratum]))
        rm = merge_run_manifest(stratum=stratum, manifests_dir=Path(a.manifests_dir),
                                out_path=out_path, judges=tuple(a.judges),
                                dry_run=a.dry_run, allow_varying=a.allow_varying)
        rep["run_manifest"] = rm
        rep["problems"].extend(rm["problems"])
        rep["ok"] = not rep["problems"]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(rep, indent=1) + "\n")

    print(json.dumps({k: v for k, v in rep.items() if k != "legs"}, indent=1))
    for name, leg in sorted(rep["legs"].items()):
        flag = "ok" if leg["ok"] else "FAIL"
        print(f"[merge] {flag:4s} {name}: present={leg['n_present']}/"
              f"{leg['n_expected']} copied={leg['n_copied']} "
              f"missing={leg['n_missing']} extra={leg['n_extra']} "
              f"dupes={leg['n_duplicate']} by_chunk={leg['by_chunk']}")
    print(f"[merge] report -> {report_path}")

    if not rep["ok"]:
        print(f"\n[merge] FATAL: {len(rep['problems'])} problem(s) — "
              f"the merged tree is NOT complete. DO NOT ANALYSE.", file=sys.stderr)
        for p in rep["problems"]:
            print(f"  - {p}", file=sys.stderr)
        return 1
    print(f"[merge] COMPLETE — every rid present exactly once on every leg, "
          f"both judges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
