#!/usr/bin/env python3
"""rung3_r5 staging assembler — `G-STAGED` emitter
(`measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md`'s staging recipe,
`READ_RULE.md` §2, drafter commit `97ca0276` — the six-step spec, BLESSED
AS AMENDED, followed here verbatim).

WHY THIS EXISTS. `ARMS_R5.json` (`build_r5_corpus.py`, ruling `a13ed934`) is
the materialized population authority, but `stage_chunks.py` needs a
`build_positions`-shaped "positions dir" — `ARMS.json` (hardcoded filename)
+ `POSITIONS_PLAN.json` + a leg jsonl whose rid set matches. `ARMS_R5.json`
alone is not that. This module assembles it, and — per commit `97ca0276`
ruling (c) — witnesses the assembled directory in its OWN artifact
(`RUN/STAGING_R5.json`), because `CORPUS_R5.json` is written BEFORE staging
exists and cannot witness a layer that did not exist when it was written
(exactly the D4.7 finding: `CORPUS_UNION` "asserted at the ARMS layer a
property only the leg layer could witness").

THE SIX STEPS (97ca0276, verbatim):

  1. `mkdir RUN/corpus/positions_s2/`
  2. COPY `ARMS_R5.json` -> `positions_s2/ARMS.json`. NOT a symlink (R4-0.5:
     write-through hazard, breaks on archive/move) — a NAME ADAPTATION for
     `stage_chunks.py`'s hardcoded `ARMS_NAME`, with byte-identity ASSERTED
     and RECORDED, so there is one authority and one witnessed
     transcription of it, never two populations.
  3. FILTER the R4 leg jsonl to the SAME 1,060 rids -> `positions_s2/
     positions_walled_leg1.jsonl`. MUST run through an EXISTING CHECKED TOOL
     (`build_r5_corpus.assert_rid_sets_equal`) — never an ad-hoc jq/sed/awk
     filter.
  4. THE CROSS-LAYER INVARIANT, asserted AT ASSEMBLY TIME, in BOTH
     DIRECTIONS, via the EXISTING CHECKED TOOL
     (`union_positions.check_leg_layer`): `set(leg rids) == set(staged ARMS
     rids) == set(ARMS_R5.json rids)`. This is D4's missing invariant,
     installed at the layer that lacked it.
  5. WRITE `positions_s2/POSITIONS_PLAN.json` with a `files` block that
     enumerates the leg file that ACTUALLY EXISTS — asserted: every path in
     `files{}` exists on disk and its rid set matches step 4's population.
  6. `stage_chunks.py stage --s2-dir positions_s2` — asserted: stage_chunks'
     OWN re-derivation (from the staged `ARMS.json` it reads independently)
     agrees with step 4's rid set.

Emits `RUN/STAGING_R5.json` — `G-STAGED`'s witness — with EXACTLY the ten
fields `READ_RULE.md`'s address names: `arms_r5_sha256`, `staged_arms_sha256`,
`arms_copy_identical`, `n_leg_rids`, `n_arms_rids`, `rid_sets_equal`,
`missing_in_leg`, `missing_in_arms`, `stage_chunks_rid_set_agrees`,
`n_chunks`.

Usage:
    python scripts/tiletie/stage_r5_corpus.py \\
        --arms-r5 measurement/tiearb_widening_20260817/rung3_r5/ARMS_R5.json \\
        --leg measurement/tiearb_widening_20260817/shared_run_r4/corpus/positions_s2/positions_walled_leg1.jsonl \\
        --staged-dir measurement/tiearb_widening_20260817/rung3_r5/corpus/positions_s2 \\
        --stage-chunks-out-root measurement/tiearb_widening_20260817/rung3_r5 \\
        --staging-out measurement/tiearb_widening_20260817/rung3_r5/STAGING_R5.json

Exit codes
    0   staged; STAGING_R5.json written; G-STAGED clean
    2   an input is missing/malformed, a byte-identity check failed, the
        cross-layer invariant fired, a POSITIONS_PLAN.files assertion
        failed, or stage_chunks' own re-derivation disagreed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

REPO = Path(__file__).resolve().parents[2]

import build_r5_corpus as BR5                                       # noqa: E402
import gate_disjoint as GD                                          # noqa: E402
import union_positions as UP                                        # noqa: E402

RUN = REPO / "measurement/tiearb_widening_20260817/rung3_r5"
CAMPAIGN_DIR = REPO / "measurement/tiearb_widening_20260817"
STAGE_CHUNKS_SCRIPT = CAMPAIGN_DIR / "stage_chunks.py"

DEFAULT_ARMS_R5 = RUN / "ARMS_R5.json"
DEFAULT_LEG_PATH = BR5.DEFAULT_LEG_PATH
DEFAULT_STAGED_DIR = RUN / "corpus" / "positions_s2"
DEFAULT_STAGING_OUT = RUN / "STAGING_R5.json"
DEFAULT_STAGE_CHUNKS_OUT_ROOT = RUN
DEFAULT_LEG_FILENAME = "positions_walled_leg1.jsonl"
DEFAULT_LEG_KEY = "walled/leg1"
#: DESIGN §R5-FINAL: R5's committed M (READ_RULE G-M) and mining ceiling.
DEFAULT_M_WORLDS = 32
DEFAULT_MAX_PER_GAME = 3
#: `stage_chunks.py`'s own default, matched here so a real launch and this
#: staging step price the same chunk count unless overridden.
DEFAULT_N_CHUNKS_S2 = 8


class StagingError(RuntimeError):
    """An input is missing/malformed, or a staging-time assertion failed.
    Fail loud, never silently proceed past a defect this recipe exists to
    catch (that is precisely how D4/D4.7 happened)."""


# --------------------------------------------------------------------------- #
# steps 1-2 — mkdir + the byte-identical ARMS copy (no symlink, R4-0.5)        #
# --------------------------------------------------------------------------- #
def stage_arms_copy(arms_r5_path, staged_dir) -> dict:
    staged_dir = Path(staged_dir)
    staged_dir.mkdir(parents=True, exist_ok=True)                  # step 1
    arms_r5_path = Path(arms_r5_path)
    if not arms_r5_path.is_file():
        raise StagingError(f"ARMS_R5.json not found: {arms_r5_path}")

    dest = staged_dir / "ARMS.json"                                # step 2
    src_bytes = arms_r5_path.read_bytes()
    dest.write_bytes(src_bytes)                                    # COPY, never a symlink
    dest_bytes = dest.read_bytes()

    arms_r5_sha256 = hashlib.sha256(src_bytes).hexdigest()
    staged_arms_sha256 = hashlib.sha256(dest_bytes).hexdigest()
    arms_copy_identical = (arms_r5_sha256 == staged_arms_sha256
                           and src_bytes == dest_bytes)
    if not arms_copy_identical:
        raise StagingError(
            f"staged ARMS.json is NOT byte-identical to {arms_r5_path}: "
            f"staged sha256={staged_arms_sha256} != source sha256="
            f"{arms_r5_sha256} — a NAME ADAPTATION must be byte-identical "
            "or it is a second, divergent population")
    return {
        "arms_r5_sha256": arms_r5_sha256,
        "staged_arms_sha256": staged_arms_sha256,
        "arms_copy_identical": arms_copy_identical,
        "staged_arms_path": str(dest),
    }


# --------------------------------------------------------------------------- #
# step 3 — filter the leg, THROUGH assert_rid_sets_equal, never ad-hoc         #
# --------------------------------------------------------------------------- #
def stage_leg_filter(leg_path, arms_rids: set, staged_dir,
                     filename=DEFAULT_LEG_FILENAME) -> tuple:
    leg_path = Path(leg_path)
    if not leg_path.is_file():
        raise StagingError(f"leg file not found: {leg_path}")
    kept_lines, kept_rids = [], set()
    for line in leg_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StagingError(f"{leg_path}: not JSON ({exc})") from exc
        if "rid" not in rec:
            raise StagingError(f"{leg_path}: a line has no 'rid' field")
        if rec["rid"] in arms_rids:
            kept_lines.append(line)
            kept_rids.add(rec["rid"])

    dest = Path(staged_dir) / filename
    dest.write_text(("\n".join(kept_lines) + "\n") if kept_lines else "")

    # step 3's own correctness check -- the EXISTING CHECKED TOOL, never an
    # ad-hoc jq/sed/awk filter trusted blind.
    BR5.assert_rid_sets_equal(
        kept_rids, set(arms_rids),
        what="filtered leg rid set vs ARMS_R5 rid set (step 3)")
    return dest, kept_rids


# --------------------------------------------------------------------------- #
# step 4 — the cross-layer invariant, BOTH directions, via check_leg_layer     #
# --------------------------------------------------------------------------- #
def cross_layer_invariant(staged_arms_rids: set, filtered_leg_rids: set,
                          *, where: str) -> dict:
    """Runs `union_positions.check_leg_layer` — the EXISTING checked tool,
    never a re-implementation. Its own `UnionError` is caught so this
    function can report the FULL (untruncated) `missing_in_leg` /
    `missing_in_arms` witness lists `STAGING_R5.json` names (the gate's own
    report truncates to 10 for a print banner, not for a persisted witness),
    then re-raises as `StagingError` with the same information."""
    staged_arms_rids, filtered_leg_rids = set(staged_arms_rids), set(filtered_leg_rids)
    try:
        UP.check_leg_layer(staged_arms_rids, filtered_leg_rids, where=where)
        ok = True
    except UP.UnionError:
        ok = False

    # in ARMS, no leg line -> the rid is MISSING FROM THE LEG
    missing_in_leg = sorted(staged_arms_rids - filtered_leg_rids)
    # a leg line not in ARMS -> the rid is MISSING FROM ARMS
    missing_in_arms = sorted(filtered_leg_rids - staged_arms_rids)
    rid_sets_equal = ok and not missing_in_leg and not missing_in_arms
    witness = {
        "n_leg_rids": len(filtered_leg_rids),
        "n_arms_rids": len(staged_arms_rids),
        "rid_sets_equal": rid_sets_equal,
        "missing_in_leg": missing_in_leg,
        "missing_in_arms": missing_in_arms,
    }
    if not rid_sets_equal:
        raise StagingError(
            f"cross-layer invariant violated at {where} (D4's missing "
            f"invariant): {len(missing_in_leg)} rid(s) missing from the leg "
            f"(e.g. {missing_in_leg[:3]}), {len(missing_in_arms)} missing "
            f"from ARMS (e.g. {missing_in_arms[:3]})")
    return witness


# --------------------------------------------------------------------------- #
# step 5 — POSITIONS_PLAN.json, files block enumerating what actually exists  #
# --------------------------------------------------------------------------- #
def write_positions_plan(staged_dir, leg_dest_path, n_positions, *,
                         m_worlds=DEFAULT_M_WORLDS,
                         max_per_game=DEFAULT_MAX_PER_GAME,
                         leg_key=DEFAULT_LEG_KEY) -> tuple:
    leg_dest_path = Path(leg_dest_path)
    lines = [ln for ln in leg_dest_path.read_text().splitlines() if ln.strip()]
    plan = {
        "n_positions": int(n_positions),
        "cap_j": None,
        "uncapped": True,
        "max_per_game": int(max_per_game),
        # ⚠️ stage_chunks.py's cmd_stage reads plan["m_worlds"] directly
        # (KeyError otherwise) -- cost-arithmetic metadata only, never a
        # gated identity (G-M reads RUN_MANIFEST, not this).
        "m_worlds": int(m_worlds),
        "files": {leg_key: {"path": str(leg_dest_path), "n": len(lines)}},
    }
    plan_path = Path(staged_dir) / "POSITIONS_PLAN.json"
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True))

    # ASSERTS: every path in files{} exists on disk, its line count matches,
    # and its rid set matches the population -- D4's defect was a files
    # block pointing at a population the plan did not actually contain.
    for key, info in plan["files"].items():
        p = Path(info["path"])
        if not p.is_file():
            raise StagingError(
                f"POSITIONS_PLAN.files[{key!r}].path does not exist: {p} "
                "-- a plan may never name a population its files do not contain")
        file_lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        if len(file_lines) != int(info["n"]):
            raise StagingError(
                f"POSITIONS_PLAN.files[{key!r}]: plan says n={info['n']} but "
                f"{p} has {len(file_lines)} lines")
        file_rids = {json.loads(ln)["rid"] for ln in file_lines}
        if len(file_rids) != int(n_positions):
            raise StagingError(
                f"POSITIONS_PLAN.files[{key!r}]: {len(file_rids)} distinct "
                f"rid(s) on disk but n_positions={n_positions}")
    return plan_path, plan


# --------------------------------------------------------------------------- #
# step 6 — stage_chunks' own re-derivation, witnessed to agree                 #
# --------------------------------------------------------------------------- #
def run_stage_chunks(staged_dir, *, out_root, n_chunks=DEFAULT_N_CHUNKS_S2,
                     script=STAGE_CHUNKS_SCRIPT) -> dict:
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(script), "stage",
         "--s2-dir", str(staged_dir), "--stratum", "s2",
         "--chunks-s2", str(n_chunks), "--out-root", str(out_root)],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise StagingError(
            f"stage_chunks.py stage failed (exit {r.returncode}): "
            f"{(r.stderr or r.stdout).strip()[-2000:]}")
    order_path = out_root / "POSITION_ORDER.json"
    if not order_path.is_file():
        raise StagingError(
            f"stage_chunks.py exited 0 but wrote no POSITION_ORDER.json at "
            f"{order_path}")
    doc = json.loads(order_path.read_text())
    s2 = (doc.get("strata") or {}).get("s2")
    if s2 is None:
        raise StagingError(f"{order_path}: no strata.s2 -- stage_chunks did "
                          "not stage the s2 stratum")
    return {"order_rids": set(s2["order"]), "n_chunks": int(s2["chunks"]),
           "order_path": str(order_path), "stdout": r.stdout}


# --------------------------------------------------------------------------- #
# the full six-step assembly                                                   #
# --------------------------------------------------------------------------- #
def stage(*, arms_r5_path=DEFAULT_ARMS_R5, leg_path=DEFAULT_LEG_PATH,
         staged_dir=DEFAULT_STAGED_DIR, stage_chunks_out_root=None,
         n_chunks=DEFAULT_N_CHUNKS_S2, m_worlds=DEFAULT_M_WORLDS,
         max_per_game=DEFAULT_MAX_PER_GAME,
         stage_chunks_script=STAGE_CHUNKS_SCRIPT) -> dict:
    """The six-step recipe (drafter commit `97ca0276`), verbatim. Returns the
    `STAGING_R5.json` report. Raises `StagingError` / `build_r5_corpus.
    BuildError` / `gate_disjoint.GateInputError` on any step's failure —
    every step's own ASSERT, not a summary check at the end."""
    staged_dir = Path(staged_dir)
    stage_chunks_out_root = (Path(stage_chunks_out_root) if stage_chunks_out_root
                             else DEFAULT_STAGE_CHUNKS_OUT_ROOT)

    arms_r5 = GD._load_arms(arms_r5_path)              # reused, not re-implemented
    arms_r5_rids = set(arms_r5)

    copy_witness = stage_arms_copy(arms_r5_path, staged_dir)          # 1-2
    leg_dest, filtered_rids = stage_leg_filter(leg_path, arms_r5_rids, # 3
                                               staged_dir)

    staged_arms = json.loads((staged_dir / "ARMS.json").read_text())
    staged_arms_rids = set(staged_arms)
    cross_layer_witness = cross_layer_invariant(                       # 4
        staged_arms_rids, filtered_rids, where=str(staged_dir))

    n_positions = len(arms_r5_rids)
    plan_path, plan = write_positions_plan(                            # 5
        staged_dir, leg_dest, n_positions, m_worlds=m_worlds,
        max_per_game=max_per_game)

    sc = run_stage_chunks(staged_dir, out_root=stage_chunks_out_root,  # 6
                          n_chunks=n_chunks, script=stage_chunks_script)
    stage_chunks_rid_set_agrees = (sc["order_rids"] == arms_r5_rids)
    if not stage_chunks_rid_set_agrees:
        only_stage = sorted(sc["order_rids"] - arms_r5_rids)
        only_r5 = sorted(arms_r5_rids - sc["order_rids"])
        raise StagingError(
            "stage_chunks' own re-derivation does NOT agree with the staged "
            f"population: {len(only_stage)} rid(s) only in stage_chunks' "
            f"order (e.g. {only_stage[:3]}), {len(only_r5)} only in "
            f"ARMS_R5 (e.g. {only_r5[:3]})")

    report = {
        "schema": "carcassonne-rung3-r5-staging/v1",
        "design_doc": "measurement/tiearb_widening_20260817/rung3_r5/DESIGN.md",
        "gate": "G-STAGED",
        "note": "CORPUS_R5.json is written BEFORE staging exists and cannot "
                "witness this layer (drafter ruling (c), the D4.7 finding: "
                "CORPUS_UNION asserted at the ARMS layer a property only "
                "the leg layer could witness). This is that witness.",
        **copy_witness,
        **cross_layer_witness,
        "stage_chunks_rid_set_agrees": stage_chunks_rid_set_agrees,
        "n_chunks": sc["n_chunks"],
        "staged_dir": str(staged_dir),
        "positions_plan_path": str(plan_path),
        "leg_path": str(leg_dest),
        "order_path": sc["order_path"],
    }
    return report


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms-r5", default=str(DEFAULT_ARMS_R5),
                    help="the materialized population authority "
                         "(build_r5_corpus.py's output)")
    ap.add_argument("--leg", default=str(DEFAULT_LEG_PATH),
                    help="the R4 post-exclusion S2 leg1 jsonl to filter")
    ap.add_argument("--staged-dir", default=str(DEFAULT_STAGED_DIR),
                    help="where the positions dir is assembled "
                         "(RUN/corpus/positions_s2)")
    ap.add_argument("--stage-chunks-out-root", default=str(DEFAULT_STAGE_CHUNKS_OUT_ROOT),
                    help="where stage_chunks.py writes POSITION_ORDER.json + "
                         "chunks/ (step 6) -- NEVER the live campaign root "
                         "for a scratch/test run")
    ap.add_argument("--n-chunks-s2", type=int, default=DEFAULT_N_CHUNKS_S2)
    ap.add_argument("--m-worlds", type=int, default=DEFAULT_M_WORLDS)
    ap.add_argument("--max-per-game", type=int, default=DEFAULT_MAX_PER_GAME)
    ap.add_argument("--stage-chunks-script", default=str(STAGE_CHUNKS_SCRIPT))
    ap.add_argument("--staging-out", default=str(DEFAULT_STAGING_OUT))
    a = ap.parse_args(argv)

    try:
        report = stage(
            arms_r5_path=a.arms_r5, leg_path=a.leg, staged_dir=a.staged_dir,
            stage_chunks_out_root=a.stage_chunks_out_root,
            n_chunks=a.n_chunks_s2, m_worlds=a.m_worlds,
            max_per_game=a.max_per_game,
            stage_chunks_script=a.stage_chunks_script)
    except (StagingError, BR5.BuildError, GD.GateInputError, UP.UnionError) as exc:
        print(f"\n{'=' * 70}\n[stage-r5-corpus] COULD NOT STAGE: {exc}\n"
              f"{'=' * 70}", file=sys.stderr)
        return 2

    Path(a.staging_out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.staging_out).write_text(json.dumps(report, indent=2, sort_keys=True))
    print(f"[stage-r5-corpus] STAGING_R5 -> {a.staging_out}")
    print(f"[stage-r5-corpus] arms_copy_identical={report['arms_copy_identical']} "
          f"rid_sets_equal={report['rid_sets_equal']} "
          f"stage_chunks_rid_set_agrees={report['stage_chunks_rid_set_agrees']} "
          f"n_leg_rids={report['n_leg_rids']} n_chunks={report['n_chunks']}")
    print("[stage-r5-corpus] G-STAGED PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
