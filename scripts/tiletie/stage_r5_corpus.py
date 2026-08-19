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
  5. WRITE `positions_s2/POSITIONS_PLAN.json` by COPYING R4's real
     corpus-level plan (never synthesizing) and recomputing ONLY the
     rid-set-dependent keys, via `stage_chunks.subset_plan` — the SAME
     function `stage_chunks.py`'s own chunk-writer uses. Every
     rid-INDEPENDENT key (`afterstate_dedupe` with its `design_ref`/
     `dropped_index_path` provenance, `cap_j`, `uncapped`, `m_worlds`,
     `sample_seed`, …) is carried VERBATIM; the `files` block enumerates the
     leg file that ACTUALLY EXISTS — asserted: every path in `files{}`
     exists on disk and its rid set matches step 4's population. REFUSES
     LOUDLY if the SOURCE plan itself lacks `afterstate_dedupe.applied ==
     true` — a source without it means the corpus genuinely was not
     deduped, and staging must not launder that (the executor's diagnosis:
     a minimal plan can make dedupe true IN FACT but absent from the
     ARTIFACT — the m_worlds-gap class).
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
if str(CAMPAIGN_DIR) not in sys.path:
    sys.path.insert(0, str(CAMPAIGN_DIR))
#: the EXISTING CHECKED TOOL for "deep-copy a corpus plan, recompute ONLY
#: the rid-set-dependent keys, carry everything else verbatim" — imported as
#: a module (not just invoked as the step-6 subprocess) so step 5 can reuse
#: `subset_plan` / `RID_DEPENDENT_KEYS` directly, never re-implementing the
#: partition between "recompute" and "copy-never-synthesize".
import stage_chunks as SC                                           # noqa: E402

DEFAULT_ARMS_R5 = RUN / "ARMS_R5.json"
DEFAULT_LEG_PATH = BR5.DEFAULT_LEG_PATH
#: R4's own corpus-level POSITIONS_PLAN.json — the ADOPTED source every
#: rid-independent key (afterstate_dedupe with its design_ref/
#: dropped_index_path provenance, cap_j, uncapped, m_worlds, sample_seed,
#: …) is COPIED from, never synthesized. Executor finding (the m_worlds-gap
#: class): a minimal hand-built plan makes the property (dedupe was applied
#: to the adopted corpus) true IN FACT but absent from the ARTIFACT.
DEFAULT_R4_SOURCE_PLAN = (REPO / "measurement/tiearb_widening_20260817/"
                          "shared_run_r4/corpus/positions_s2/POSITIONS_PLAN.json")
DEFAULT_STAGED_DIR = RUN / "corpus" / "positions_s2"
DEFAULT_STAGING_OUT = RUN / "STAGING_R5.json"
DEFAULT_STAGE_CHUNKS_OUT_ROOT = RUN
DEFAULT_LEG_FILENAME = "positions_walled_leg1.jsonl"
DEFAULT_LEG_KEY = "walled/leg1"
#: NOT a key R4's source plan carries (verified: absent from the real
#: shared_run_r4/corpus/positions_s2/POSITIONS_PLAN.json) — the six-step
#: recipe (97ca0276) names it explicitly as a value to WRITE, so it is the
#: one deliberate addition on top of the copied+recomputed plan, not a
#: violation of copy-never-synthesize (there is nothing to copy).
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
# the R4 source plan — every rid-independent key is COPIED from here,          #
# NEVER synthesized. Refuses loudly if the source itself lacks the dedupe.     #
# --------------------------------------------------------------------------- #
def load_r4_source_plan(path=DEFAULT_R4_SOURCE_PLAN) -> dict:
    """R4's real corpus-level `POSITIONS_PLAN.json` — the ADOPTED source
    every rid-INDEPENDENT key of the staged plan is copied from verbatim.

    RAISES `StagingError` if `afterstate_dedupe.applied is not True` on the
    SOURCE — a source without it means the adopted corpus genuinely was not
    deduped (built without `--afterstate-map`, or with `--no-dedupe`), and
    staging must not launder that by silently omitting the field: the
    property (dedupe applied) must hold in the ARTIFACT, not just "in fact"
    on whatever corpus happens to be adopted. `run_tiletie.py`'s own
    preflight (`check_positions`) enforces the same rule at launch time —
    this is that check, moved earlier, so a bad source refuses at STAGING,
    not at the first launch attempt."""
    p = Path(path)
    if not p.is_file():
        raise StagingError(f"R4 source POSITIONS_PLAN.json not found: {p}")
    try:
        plan = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise StagingError(f"{p}: not JSON ({exc})") from exc
    dedupe = plan.get("afterstate_dedupe") or {}
    if dedupe.get("applied") is not True:
        raise StagingError(
            f"{p}: afterstate_dedupe.applied is not True -- the R4 source "
            "plan was built WITHOUT the DESIGN threat-3 afterstate dedupe "
            "(or with --no-dedupe). Staging must not launder this: launching "
            "against it would score ~26% known-zero transposition rows. "
            "Rebuild the R4 source with build_positions.py --afterstate-map "
            "before staging R5 (run_tiletie.py's own preflight refuses the "
            "same way, at launch time instead of at staging time).")
    return plan


# --------------------------------------------------------------------------- #
# step 5 — POSITIONS_PLAN.json: COPY the source, recompute ONLY the           #
# rid-set-dependent keys (via stage_chunks.subset_plan), files enumerates     #
# what actually exists                                                        #
# --------------------------------------------------------------------------- #
def write_positions_plan(staged_dir, leg_dest_path, arms_r5: dict,
                         r4_source_plan: dict, *,
                         max_per_game=DEFAULT_MAX_PER_GAME,
                         leg_key=DEFAULT_LEG_KEY) -> tuple:
    """Builds the staged corpus-level plan by COPYING `r4_source_plan`
    (deep copy) and recomputing ONLY `stage_chunks.RID_DEPENDENT_KEYS` over
    the staged population — via `stage_chunks.subset_plan`, the SAME
    function `stage_chunks.py`'s own chunk-writer uses, never a
    re-implementation of "which keys are rid-set-dependent". Every other
    key — including `afterstate_dedupe` with its `design_ref`/
    `dropped_index_path` provenance, `cap_j`, `uncapped`, `m_worlds`,
    `sample_seed`, `deployed_cap_j`, `union_provenance`, … — is carried
    VERBATIM. Returns `(plan_path, plan, carried_keys)`, where `carried_keys`
    is the EXPLICIT enumeration (source keys minus `RID_DEPENDENT_KEYS`) so
    the carried set is reported, not merely trusted."""
    leg_dest_path = Path(leg_dest_path)
    lines = [ln for ln in leg_dest_path.read_text().splitlines() if ln.strip()]
    keep = set(arms_r5)
    files = {leg_key: {"path": str(leg_dest_path), "n": len(lines)}}

    carried_keys = sorted(set(r4_source_plan) - SC.RID_DEPENDENT_KEYS)

    plan = SC.subset_plan(
        r4_source_plan, keep, arms_r5, files,
        label="rung3_r5 staged corpus (the WHOLE population, not a chunk)",
        out_dir=staged_dir, chunk_index=0, n_chunks=1, order_sha256="")
    # "chunk" and "label" are genuinely CHUNK-specific provenance (chunk
    # index/n_chunks/position-order sha) `subset_plan` writes for its real
    # caller (stage_chunks.py's per-chunk plans); they do not apply to this
    # CORPUS-level artifact, which is not a chunk. Every other key
    # `subset_plan` touched (recomputed OR carried verbatim) stays.
    plan.pop("chunk", None)
    plan.pop("label", None)
    # the one deliberate addition with no R4 source equivalent (see
    # DEFAULT_MAX_PER_GAME's own docstring) -- not a copy-never-synthesize
    # violation, since there is nothing in the source to have copied.
    plan["max_per_game"] = int(max_per_game)

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
        if len(file_rids) != len(keep):
            raise StagingError(
                f"POSITIONS_PLAN.files[{key!r}]: {len(file_rids)} distinct "
                f"rid(s) on disk but n_positions={len(keep)}")
    return plan_path, plan, carried_keys


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
         r4_source_plan_path=DEFAULT_R4_SOURCE_PLAN,
         staged_dir=DEFAULT_STAGED_DIR, stage_chunks_out_root=None,
         n_chunks=DEFAULT_N_CHUNKS_S2, max_per_game=DEFAULT_MAX_PER_GAME,
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
    # refuses loudly if the SOURCE itself lacks afterstate_dedupe -- a
    # source without it means the adopted corpus genuinely was not deduped
    r4_source_plan = load_r4_source_plan(r4_source_plan_path)

    copy_witness = stage_arms_copy(arms_r5_path, staged_dir)          # 1-2
    leg_dest, filtered_rids = stage_leg_filter(leg_path, arms_r5_rids, # 3
                                               staged_dir)

    staged_arms = json.loads((staged_dir / "ARMS.json").read_text())
    staged_arms_rids = set(staged_arms)
    cross_layer_witness = cross_layer_invariant(                       # 4
        staged_arms_rids, filtered_rids, where=str(staged_dir))

    plan_path, plan, carried_plan_keys = write_positions_plan(         # 5
        staged_dir, leg_dest, arms_r5, r4_source_plan,
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
        # the executor's diagnosis (the m_worlds-gap class): a minimal plan
        # can make a property true IN FACT (afterstate dedupe was applied to
        # the adopted corpus) but absent from the ARTIFACT. This is the
        # explicit, enumerated carried set -- copied verbatim from the R4
        # source plan, never synthesized -- so the property is checkable
        # here, not just asserted.
        "r4_source_plan_path": str(r4_source_plan_path),
        "carried_plan_keys": carried_plan_keys,
        "afterstate_dedupe_carried": plan.get("afterstate_dedupe"),
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
    ap.add_argument("--r4-source-plan", default=str(DEFAULT_R4_SOURCE_PLAN),
                    help="R4's real corpus-level POSITIONS_PLAN.json -- every "
                         "rid-independent key (afterstate_dedupe, cap_j, "
                         "uncapped, m_worlds, sample_seed, …) is COPIED from "
                         "here, never synthesized. Refuses if it lacks "
                         "afterstate_dedupe.applied == true.")
    ap.add_argument("--staged-dir", default=str(DEFAULT_STAGED_DIR),
                    help="where the positions dir is assembled "
                         "(RUN/corpus/positions_s2)")
    ap.add_argument("--stage-chunks-out-root", default=str(DEFAULT_STAGE_CHUNKS_OUT_ROOT),
                    help="where stage_chunks.py writes POSITION_ORDER.json + "
                         "chunks/ (step 6) -- NEVER the live campaign root "
                         "for a scratch/test run")
    ap.add_argument("--n-chunks-s2", type=int, default=DEFAULT_N_CHUNKS_S2)
    ap.add_argument("--max-per-game", type=int, default=DEFAULT_MAX_PER_GAME,
                    help="R4's source plan carries no equivalent key -- this "
                         "is written directly, not copied (see "
                         "DEFAULT_MAX_PER_GAME)")
    ap.add_argument("--stage-chunks-script", default=str(STAGE_CHUNKS_SCRIPT))
    ap.add_argument("--staging-out", default=str(DEFAULT_STAGING_OUT))
    a = ap.parse_args(argv)

    try:
        report = stage(
            arms_r5_path=a.arms_r5, leg_path=a.leg,
            r4_source_plan_path=a.r4_source_plan, staged_dir=a.staged_dir,
            stage_chunks_out_root=a.stage_chunks_out_root,
            n_chunks=a.n_chunks_s2, max_per_game=a.max_per_game,
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
    print(f"[stage-r5-corpus] carried {len(report['carried_plan_keys'])} key(s) "
          f"verbatim from the R4 source plan (never synthesized): "
          f"{', '.join(report['carried_plan_keys'])}")
    print(f"[stage-r5-corpus] afterstate_dedupe.applied="
          f"{(report['afterstate_dedupe_carried'] or {}).get('applied')}")
    print("[stage-r5-corpus] G-STAGED PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
