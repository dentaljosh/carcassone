#!/usr/bin/env python3
"""PLAN SURGERY for the tie-arbiter WIDENING shared run — the TWO-BOX chunk layer.

It scores NOTHING. It reads no record, no oracle value, no mean, no sd and no
statistic. It only cuts the two already-built corpus plan dirs into the shapes
`run_tiletie.py` consumes, one per (stratum, chunk).

    stage      — write `POSITION_ORDER.json` (ONE seeded shuffle per stratum of
                 that stratum's SORTED rid list) and cut each stratum's order into
                 `--chunks-s1` / `--chunks-s2` near-equal SEQUENTIAL chunks, one
                 `run_tiletie`-shaped plan dir each, under
                 `chunks/<stratum>/chunk<k>/`.
    verify     — re-derive both permutations and assert BYTE-IDENTITY with the
                 committed `POSITION_ORDER.json`, plus rid-set identity with every
                 staged chunk dir and line counts with every chunk leg file.
    completion — SUPPLEMENTARY chunks for rids the corpus committed but that no
                 box ever scored (D4). See the COMPLETION section below.

──────────────────────────────────────────────────────────────────────────────
COMPLETION STAGING (`completion`) — D4 ruling `751bdd12`, and its guard rails.

`union_positions.py` merged `ARMS.json` but left the leg files extension-only,
so 551 committed rids were never scored by any box. The ruling licenses scoring
them — as **COMPLETION, not re-registration** — and makes three facts conditions
of that licence, the third of which this subcommand exists to make CHECKABLE
rather than asserted:

    "the supplementary chunks must contain EXACTLY the set
     `ARMS.json rids − already-scored rids`, asserted as a SET EQUALITY …
     Any rid outside that set, in either direction, voids the completion."

So `completion`:

  * derives **already-scored** from the EXISTING RECORD TREES (never from a
    plan, never from a count — the defect was three counts each true of a
    different population). A rid counts as scored only if BOTH judges hold a
    record for it; a rid scored by one judge and not the other makes the
    remainder ambiguous and REFUSES;
  * re-checks the **cross-layer invariant** (leg files enumerate exactly the
    ARMS rid set) before the first supplementary leg, per D4.3;
  * orders the remainder by the **SAME committed `POSITION_ORDER.json`**
    (seed 20260817) — no re-shuffle, no new randomness, and already-scored rids
    keep their chunks, which are never opened or rewritten;
  * asserts the **set equality in BOTH directions** after staging, and that the
    supplementary rid set is DISJOINT from the scored set;
  * emits `ALLOCATION_COMPLETION_<stratum>.conf` — the two-box split of the
    tranche in `ALLOCATION.conf`'s exact key spelling, with the capacity
    arithmetic printed in its header.

Supplementary chunks are numbered AFTER the committed ones (`chunk9…`) in the
SAME `chunks/<stratum>/` tree, so `run_scoring.sh <box> <stratum> <judge> 9 10 …`
and `merge_legs.py` (which globs `chunk*`) need no change at all.

──────────────────────────────────────────────────────────────────────────────
WHY THE PERMUTATION EXISTS (the tiearb2_20260816 precedent, DESIGN §10 there).
`oracle_score_pilot.load_positions_jsonl` sorts by `root_id`, so a *line-order*
prefix of a leg file is composition-biased. Cutting a committed seeded
permutation into chunks makes **any completed-chunk prefix a uniform random
subsample**, so a partial run is still an unbiased read at its realized `n`.

WHY CHUNK MEMBERSHIP IS DEFINED EXACTLY ONCE.  The frozen `READ_RULE.md`
`G-CRN` conjunct joins the two judges per rid, and the analyzer pairs per
position on `rid`.  `clair-puct` and `tier1-greedy` must therefore score the
IDENTICAL rid set per chunk.  Membership lives here and nowhere else;
`ALLOCATION.conf` decides only WHO RUNS WHICH CHUNK, which is throughput and
cannot move a value.

──────────────────────────────────────────────────────────────────────────────
⚠️ GATE-NEUTRALITY — the claim this file is built to keep true.

Both seed streams that a leg consumes are pure functions of `(rid, j, salt)`:

    scripts/measurement_infra/oracle_score_pilot.py
        _sha_int(*parts) = int(sha256("|".join(parts))[:8]) & 0x7FFFFFFF
        world_seed(rid, j, salt)   = _sha_int("world",   rid, j, salt)
        playout_seed(rid, j, salt) = _sha_int("playout", rid, j, salt)
        world_seeds(rid, m, salt)  = [world_seed(rid, j, salt) for j in range(m)]

    scripts/tiletie/tier1_rust_leg.py
        imports those very functions from `oracle_score_pilot` (it does NOT
        re-implement them: `preflight_seeds` asserts `world_seeds()` agrees with
        `world_seed()` and that the ladder is prefix-stable, fatally, at launch).

The derivation mentions NEITHER the chunk, NOR the box, NOR the worker count,
NOR the position's index inside its leg file, NOR M (M never enters — which is
why worlds are prefix-stable and an M=128 run's first 32 worlds are bit-identical
to an M=32 run's).  `run_tiletie.WORLD_SEED_SALT` is a MODULE CONSTANT
(`"tiletie-v1"`), passed identically to both leg drivers.

⇒ For a fixed rid, every leg of that rid — both judges, all M worlds — is
produced with the same CRN seeds no matter which box ran it, PROVIDED the rid is
never split across boxes within a leg.  This file enforces that structurally:
chunks are sets of WHOLE RIDS, and a rid's every leg row travels with it into
exactly one chunk dir.  The merged tree is therefore byte-indistinguishable
per rid from a single-box run.

──────────────────────────────────────────────────────────────────────────────
⚠️ WHAT `run_tiletie.py` ACTUALLY SUPPORTS.  It has NO `--rids-file` and no
subset flag of any kind: the only handle on "which positions" is
`--positions-dir`, whose `POSITIONS_PLAN.json::files` names the per-leg jsonl
paths it launches.  Restriction is therefore MATERIALIZED — a per-chunk
positions dir whose `ARMS.json` / `POSITIONS_PLAN.json` / leg jsonl files are
exact rid-subsets of the corpus dir.  (`run_tiletie.verify_leg_records` also
DEMANDS a leg's records dir hold exactly its own input's rids, so per-chunk
out-roots + a merge step are forced, not chosen.)  `merge_legs.py` reassembles.

Every key of the source `POSITIONS_PLAN.json` that is NOT a function of the rid
set is carried VERBATIM (`uncapped`, `cap_j`, `cap_j_label`, `deployed_cap_j`,
`afterstate_dedupe`, `sample_seed`, `m_worlds`, `world_seed_salt`, …), so a
chunk plan cannot silently disagree with the corpus plan the gates address.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_tiearb_plan as BTP  # noqa: E402  (path insert must precede the import)

import widening_paths as WP  # noqa: E402  (path insert must precede the import)

# the cross-layer invariant is DEFINED ONCE, by the tool that assembles the
# union; this module re-checks it rather than re-implementing it (a second
# spelling of an invariant is how two layers come to disagree about it)
import union_positions as UP  # noqa: E402

import merge_legs as ML  # noqa: E402  (the judge list of record lives there)

RUN_ID = WP.RUN_ID
CAMPAIGN = REPO / "measurement" / RUN_ID
# rev R4.5 — the LIVE prereg pair is `shared_run_r4/`. `shared_run/` is the
# R3.3 pair, SPENT-BY-GATE-FAILURE: frozen history, never amended, revived or
# re-read. The directory name is defined ONCE, in
# WORKERS.conf::PREREG_DIR_NAME, and read here through `widening_paths` so the
# shell launchers and this module cannot drift apart.
RUN_DIR = WP.run_dir(CAMPAIGN)                    # the FROZEN prereg dir — read only
BANKED_RUN_DIR = WP.banked_dir(CAMPAIGN)          # ⚠️ SPENT pair — READ-ONLY FOREVER
SCHEMA = "carcassonne-tiearb-widening-chunks/v1"
# ⚠️ CHUNK PROVENANCE cites the pair the chunks were cut for. Citing the R3.3
# pair would stamp every chunk manifest with the provenance of a prereg that is
# SPENT — a reader reconstructing which rule governed these chunks would be
# sent to the dead document.
DESIGN_DOC = WP.design_doc()
READ_RULE = WP.read_rule()

#: ONE committed seed, one shuffle per stratum, written BEFORE launch.
#: Deliberately NOT the corpus `--sample-seed` (20260819, DESIGN §4): the mining
#: draw and the throughput permutation are different draws and must not be
#: confusable by a later reader.
PERMUTATION_SEED = 20260817

STRATA = ("s1", "s2")

#: The two judges of record. Both must score every committed rid (`G-CRN` joins
#: them per rid), so "already scored" means scored by BOTH.
JUDGES = ML.JUDGES

COMPLETION_SCHEMA = "carcassonne-tiearb-widening-completion/v1"

#: DESIGN §4's graded-knob table. `--m` is the only one of these that
#: `run_tiletie` takes as a flag; it is repeated here so the chunk layer can
#: ASSERT the stratum it is staging matches the corpus plan it was built from.
M_BY_STRATUM = {"s1": 128, "s2": 32}

DEFAULT_CHUNKS = {"s1": 8, "s2": 8}

PLAN_NAME = "POSITIONS_PLAN.json"
ARMS_NAME = "ARMS.json"
DROPPED_NAME = "DROPPED_ALL_TRANSPOSITION.json"


def _die(msg: str) -> "NoReturn":  # noqa: F821
    raise SystemExit(f"REFUSING: {msg}")


def log(msg: str) -> None:
    """A NOTE on the printed surface. Used where a discrepancy is worth SEEING
    but is not a defect — the alternative, staying silent, is how a field's
    nature gets forgotten and re-asserted by the next reader."""
    print(f"[stage_chunks] {msg}")


def corpus_dir(stratum: str) -> Path:
    return RUN_DIR / "corpus" / f"positions_{stratum}"


def chunk_dir(out_root: Path, stratum: str, k: int) -> Path:
    return Path(out_root) / "chunks" / stratum / f"chunk{k}"


# --------------------------------------------------------------------------- #
# loading                                                                      #
# --------------------------------------------------------------------------- #
def load_plan_dir(src: Path) -> tuple:
    src = Path(src)
    for name in (PLAN_NAME, ARMS_NAME):
        if not (src / name).is_file():
            _die(f"{src} is not a positions dir (missing {name})")
    plan = json.loads((src / PLAN_NAME).read_text())
    arms = json.loads((src / ARMS_NAME).read_text())
    dropped_p = src / DROPPED_NAME
    dropped = json.loads(dropped_p.read_text()) if dropped_p.is_file() else None
    return plan, arms, dropped


def read_leg_files(src: Path, plan: dict) -> dict:
    """{"<profile>/leg<r>": [(rid, raw_line), ...]} preserving SOURCE LINE ORDER.

    Lines are carried through as raw text so a chunk leg file's bytes for a
    given rid are identical to the corpus leg file's bytes for that rid.
    """
    src = Path(src)
    out = {}
    for key, info in sorted((plan.get("files") or {}).items()):
        p = Path(info["path"])
        if not p.is_file():
            p = src / Path(info["path"]).name
        if not p.is_file():
            _die(f"missing source leg file for {key}: {info['path']}")
        rows = []
        for line in p.read_text().splitlines():
            if line.strip():
                rows.append((json.loads(line)["rid"], line))
        if len(rows) != int(info["n"]):
            _die(f"{p} has {len(rows)} lines, plan says {info['n']}")
        out[key] = rows
    return out


# --------------------------------------------------------------------------- #
# the committed order                                                          #
# --------------------------------------------------------------------------- #
def sha256_list(items) -> str:
    """Digest of the rid list written one-per-line WITH a trailing newline —
    byte-for-byte the tiearb2_20260816 spelling, so the two runs' order files
    are comparable by the same rule."""
    h = hashlib.sha256()
    for s in items:
        h.update(str(s).encode())
        h.update(b"\n")
    return h.hexdigest()


def committed_order(rids, seed: int = PERMUTATION_SEED) -> list:
    """ONE shuffle of the SORTED rid list. Imported, not re-implemented:
    `build_tiearb_plan.committed_order` is the already-tested function that cut
    Stage 1 and tiearb2."""
    return BTP.committed_order(list(rids), seed=seed)


def chunk_slices(order, chunks: int) -> list:
    return BTP.chunk_slices(list(order), int(chunks))


def build_order_doc(arms_by_stratum: dict, chunk_counts: dict,
                    *, source_dirs: dict | None = None,
                    seed: int = PERMUTATION_SEED) -> tuple:
    """The committed order document + {stratum: [chunk rid lists]}.

    Pure and deterministic: same inputs -> byte-identical `json.dumps(indent=1)`.
    """
    source_dirs = source_dirs or {}
    strata_doc, chunks_by_stratum = {}, {}
    for stratum in STRATA:
        arms = arms_by_stratum.get(stratum)
        if arms is None:
            continue
        n_chunks = int(chunk_counts[stratum])
        rids = sorted(arms)
        if not rids:
            _die(f"{stratum}: the corpus has no rids")
        if n_chunks > len(rids):
            _die(f"{stratum}: --chunks {n_chunks} exceeds n={len(rids)}")
        order = committed_order(rids, seed=seed)
        chunks = chunk_slices(order, n_chunks)

        # the partition property, asserted rather than assumed
        flat = [r for c in chunks for r in c]
        if sorted(flat) != rids or len(flat) != len(set(flat)):
            _die(f"{stratum}: chunks do not partition the corpus exactly")

        chunks_by_stratum[stratum] = chunks
        strata_doc[stratum] = {
            "source_positions_dir": str(source_dirs.get(stratum)
                                        or corpus_dir(stratum)),
            "m": M_BY_STRATUM[stratum],
            "n": len(order),
            "n_roots": len({arms[r]["root_id"] for r in order}),
            "chunks": n_chunks,
            "chunk_sizes": [len(c) for c in chunks],
            "sha256_order": sha256_list(order),
            "order": order,
        }
    doc = {
        "schema": SCHEMA,
        "run_id": RUN_ID,
        "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE,
        "seed": int(seed),
        "note": (
            "ONE committed shuffle PER STRATUM of that stratum's SORTED rid list, "
            "written BEFORE launch, cut into near-equal SEQUENTIAL chunks. "
            "load_positions_jsonl sorts by root_id, so partial completion is "
            "unbiased at CHUNK granularity only. BOTH judges score the identical "
            "rid set per chunk — chunk membership is defined here and nowhere "
            "else; ALLOCATION.conf decides only WHO RUNS WHICH CHUNK, which is "
            "throughput and cannot move a value. Chunks are sets of WHOLE RIDS: "
            "a rid is never split across boxes within a leg, which is what makes "
            "the merged tree byte-indistinguishable per rid from a single-box run "
            "(world/playout seeds are sha256(tag|rid|j|salt) — no chunk, no box, "
            "no M in the derivation)."),
        "strata": strata_doc,
    }
    return doc, chunks_by_stratum


def order_payload(doc: dict) -> str:
    return json.dumps(doc, indent=1) + "\n"


# --------------------------------------------------------------------------- #
# per-chunk plan dirs                                                          #
# --------------------------------------------------------------------------- #
#: Keys of `POSITIONS_PLAN.json` that ARE a function of the rid set and must be
#: recomputed for a subset. Everything else is carried VERBATIM — which is the
#: point: `uncapped`, `cap_j`, `deployed_cap_j`, `afterstate_dedupe`,
#: `sample_seed`, `m_worlds` and `world_seed_salt` are corpus properties the
#: gates address, and a chunk that "recomputed" them could silently disagree.
RID_DEPENDENT_KEYS = frozenset({
    "files", "n_positions", "n_e4", "n_selfplay", "counts_by_stratum",
    "counts_by_profile_leg", "max_arms", "mean_arms", "mean_arms_j4",
    "n_positions_capped", "n_positions_capped_at_4", "total_arm_playouts",
    "oracle_worker_secs", "champ_pick_secs", "total_worker_secs",
    "eta_by_workers", "n_roots", "total_legs", "out_dir", "label",
})


def _eta_keys(source_eta: dict) -> list:
    """Preserve the source's own `eta_by_workers` key spelling (`build_positions`
    writes `W=30`, `build_tiearb_plan` writes `30`) so a chunk plan reads the
    same way as the corpus plan it came from."""
    return list(source_eta or {})


def subset_plan(source_plan: dict, keep: set, arms: dict, files: dict,
                *, label: str, out_dir: Path, chunk_index: int,
                n_chunks: int, order_sha256: str) -> dict:
    """The corpus plan, deep-copied, with ONLY the rid-set-dependent keys
    recomputed over `keep`."""
    plan = json.loads(json.dumps(source_plan))          # deep copy, no aliasing

    kept = sorted(keep)
    sub = {r: arms[r] for r in kept}
    arm_counts = [len(v["arms"]) for v in sub.values()]
    # cost-arithmetic metadata (see the M note in `main`), carried VERBATIM so a
    # chunk plan's playout arithmetic reads the same way as the corpus plan's
    m = int(source_plan["m_worlds"])
    playout_secs = float(source_plan.get("playout_secs") or 0.0)
    t_champ = float(source_plan.get("t_champ_secs") or 0.0)

    strata_counts: dict = {}
    for v in sub.values():
        strata_counts[v["stratum"]] = strata_counts.get(v["stratum"], 0) + 1
    n_selfplay = strata_counts.get("selfplay", 0)

    total_legs = sum(int(i["n"]) for i in files.values())
    total_arm_playouts = sum((c - 1) * 2 * m for c in arm_counts)
    oracle_worker_secs = total_arm_playouts * playout_secs
    champ_pick_secs = n_selfplay * t_champ
    total_secs = oracle_worker_secs + champ_pick_secs

    plan["label"] = label
    plan["n_positions"] = len(kept)
    plan["n_roots"] = len({v["root_id"] for v in sub.values()})
    plan["n_e4"] = strata_counts.get("e4", 0)
    plan["n_selfplay"] = n_selfplay
    plan["counts_by_stratum"] = strata_counts
    plan["counts_by_profile_leg"] = {k: int(v["n"]) for k, v in sorted(files.items())}
    plan["max_arms"] = max(arm_counts) if arm_counts else 0
    plan["mean_arms"] = (sum(arm_counts) / len(arm_counts)) if arm_counts else 0.0
    if "mean_arms_j4" in plan:
        plan["mean_arms_j4"] = (
            (sum(len(v["subset_j4"]) for v in sub.values()) / len(sub))
            if sub and all(v.get("subset_j4") for v in sub.values()) else None)
    plan["n_positions_capped"] = sum(1 for v in sub.values() if v.get("capped"))
    if "n_positions_capped_at_4" in plan:
        plan["n_positions_capped_at_4"] = sum(
            1 for v in sub.values() if v.get("capped_at_4"))
    plan["total_legs"] = total_legs
    plan["total_arm_playouts"] = total_arm_playouts
    plan["oracle_worker_secs"] = oracle_worker_secs
    plan["champ_pick_secs"] = champ_pick_secs
    plan["total_worker_secs"] = total_secs
    plan["eta_by_workers"] = {
        w: {"wall_secs": (total_secs / _w_of(w)),
            "wall_hours": total_secs / (3600.0 * _w_of(w))}
        for w in _eta_keys(source_plan.get("eta_by_workers"))
    }
    plan["files"] = files
    plan["out_dir"] = str(out_dir)

    # provenance — self-describing, so a chunk plan never needs dirname archaeology
    plan["chunk"] = {
        "schema": SCHEMA,
        "run_id": RUN_ID,
        "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE,
        "index": int(chunk_index),
        "n_chunks": int(n_chunks),
        "permutation_seed": PERMUTATION_SEED,
        "position_order_sha256": order_sha256,
        "source_positions_dir": str(source_plan.get("out_dir") or ""),
        "note": ("A THROUGHPUT SUBSET of the corpus plan. Every key that is not a "
                 "function of the rid set is carried VERBATIM from the corpus "
                 "POSITIONS_PLAN.json (uncapped, cap_j, deployed_cap_j, "
                 "afterstate_dedupe, sample_seed, m_worlds, world_seed_salt, …) — "
                 "the gates address the CORPUS plan, and a chunk that recomputed "
                 "those could silently disagree with it."),
    }
    return plan


def _w_of(key) -> float:
    """`eta_by_workers` keys are either `30` or `W=30`."""
    s = str(key)
    if s.startswith("W="):
        s = s[2:]
    try:
        w = float(s)
    except ValueError:
        return 1.0
    return w if w > 0 else 1.0


def write_chunk_dir(out_dir: Path, keep: set, *, source_dir: Path,
                    source_plan: dict, source_arms: dict, dropped,
                    leg_rows: dict, label: str, chunk_index: int,
                    n_chunks: int, order_sha256: str,
                    chunk_meta: dict | None = None) -> dict:
    """Write a `run_tiletie`-shaped plan dir restricted to `keep`."""
    out_dir = Path(out_dir)
    unknown = sorted(r for r in keep if r not in source_arms)
    if unknown:
        _die(f"unknown rid(s) in {label}: {unknown[:5]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    files, selected = {}, set()
    for key, rows in sorted(leg_rows.items()):
        sel = [(rid, line) for rid, line in rows if rid in keep]  # SOURCE ORDER
        if not sel:
            continue
        path = out_dir / f"positions_{key.replace('/', '_')}.jsonl"
        path.write_text("".join(line + "\n" for _, line in sel))
        files[key] = {"n": len(sel), "path": str(path)}
        selected.update(rid for rid, _ in sel)
    if not files:
        _die(f"{label}: no leg lines selected — the chunk would score nothing")
    # ⭐ THE CROSS-LAYER INVARIANT, at chunk granularity (D4.3). A chunk whose
    # ARMS.json carries rids its leg files do not is the D4 defect in miniature:
    # `run_tiletie` scores the leg files, `merge_legs` counts against them, and
    # the rids in the gap are silently never scored while every count reads
    # complete. Checked in BOTH directions.
    if selected != set(keep):
        _die(f"{label}: CROSS-LAYER INVARIANT VIOLATED — the chunk's leg files "
             f"enumerate {len(selected)} rid(s) but its ARMS.json carries "
             f"{len(keep)}: {len(set(keep) - selected)} with NO leg line "
             f"(first: {sorted(set(keep) - selected)[:3]}), "
             f"{len(selected - set(keep))} leg rid(s) not in ARMS "
             f"(first: {sorted(selected - set(keep))[:3]}). The SOURCE corpus "
             f"dir is the defect, not this cut — re-assemble the union first.")

    arms = {r: source_arms[r] for r in sorted(keep)}
    (out_dir / ARMS_NAME).write_text(json.dumps(arms, indent=1))

    if dropped is not None:
        # copied WHOLE, deliberately: the analytic-zero population is a property
        # of the FULL supply (the tiearb2 precedent does the same).
        (out_dir / DROPPED_NAME).write_text(json.dumps(dropped, indent=1))

    plan = subset_plan(source_plan, keep, source_arms, files, label=label,
                       out_dir=out_dir, chunk_index=chunk_index,
                       n_chunks=n_chunks, order_sha256=order_sha256)
    if chunk_meta:
        plan["chunk"].update(chunk_meta)
    (out_dir / PLAN_NAME).write_text(json.dumps(plan, indent=1))
    return plan


# --------------------------------------------------------------------------- #
# whole-rid invariant                                                          #
# --------------------------------------------------------------------------- #
def check_whole_rid(chunks: list, leg_rows: dict) -> dict:
    """THE binding structural invariant: for every leg file, every rid's rows
    land in EXACTLY ONE chunk. A rid split across chunks would be a rid split
    across boxes within a leg — the one thing that could make the merged tree
    differ from a single-box run."""
    owner = {}
    for i, ch in enumerate(chunks, 1):
        for rid in ch:
            if rid in owner:
                return {"ok": False,
                        "problem": f"rid {rid!r} appears in chunk{owner[rid]} AND chunk{i}"}
            owner[rid] = i
    split, orphan = [], []
    for key, rows in sorted(leg_rows.items()):
        seen: dict = {}
        for rid, _ in rows:
            if rid not in owner:
                orphan.append((key, rid))
                continue
            seen.setdefault(rid, set()).add(owner[rid])
        for rid, chs in seen.items():
            if len(chs) != 1:
                split.append((key, rid, sorted(chs)))
    return {"ok": not split and not orphan, "n_rids": len(owner),
            "split": split[:5], "orphan": orphan[:5],
            "n_split": len(split), "n_orphan": len(orphan)}


def check_corpus_leg_layer(arms, leg_rows: dict, *, where: str) -> dict:
    """⭐ D4.3's CROSS-LAYER INVARIANT at the CORPUS layer: the corpus dir's leg
    files must enumerate exactly its `ARMS.json` rid set.

    `check_whole_rid` above is NOT this check and never was: it asks whether
    every LEG rid lands in exactly one chunk — one direction only, over the leg
    layer's own population. A corpus whose ARMS carries 1,344 rids and whose leg
    files carry 793 passes it perfectly. That is precisely how the D4 defect
    survived staging, scoring and merge with three "complete" signals."""
    leg_rids = {rid for rows in leg_rows.values() for rid, _ in rows}
    try:
        return UP.check_leg_layer(arms, leg_rids, where=where)
    except UP.UnionError as exc:
        _die(str(exc))


# --------------------------------------------------------------------------- #
# commands                                                                     #
# --------------------------------------------------------------------------- #
def _resolve_sources(a) -> dict:
    src = {}
    for stratum in STRATA:
        if a.stratum and stratum != a.stratum:
            continue
        d = Path(getattr(a, f"{stratum}_dir") or corpus_dir(stratum)).resolve()
        if not d.is_dir():
            _die(f"{stratum}: corpus positions dir absent: {d} "
                 f"(build_widening_corpus.sh phase 5 has not run)")
        src[stratum] = d
    if not src:
        _die("no stratum selected")
    return src


def cmd_stage(a) -> int:
    # ABSOLUTE, always: POSITIONS_PLAN.json stores its leg paths as written, and
    # run_tiletie's preflight resolves them against the CURRENT WORKING
    # DIRECTORY (the tiearb2_20260816 launch died on both boxes for that).
    out_root = Path(a.out_root).resolve()
    sources = _resolve_sources(a)
    chunk_counts = {"s1": a.chunks_s1, "s2": a.chunks_s2}

    loaded = {s: load_plan_dir(d) for s, d in sources.items()}
    arms_by_stratum = {s: v[1] for s, v in loaded.items()}
    doc, chunks_by_stratum = build_order_doc(arms_by_stratum, chunk_counts,
                                             source_dirs=sources)

    order_path = out_root / "POSITION_ORDER.json"
    order_path.parent.mkdir(parents=True, exist_ok=True)
    order_path.write_text(order_payload(doc))

    summary = {"schema": SCHEMA, "run_id": RUN_ID, "design_doc": DESIGN_DOC,
               "read_rule": READ_RULE, "permutation_seed": PERMUTATION_SEED,
               "position_order": str(order_path), "strata": {}}

    for stratum, (plan, arms, dropped) in loaded.items():
        src = sources[stratum]
        # ---- M: assert what we STAMP, report what the corpus plan CARRIES --- #
        # ⚠️ The old assertion here compared the CORPUS PLAN's `m_worlds`
        # against the stratum's committed M and died on a mismatch. It could
        # never pass on S1, so the S1 stage was unrunnable — and every test
        # passed `--allow-m-mismatch`, which is why nobody found out.
        #
        # `build_positions` has NO `--m` flag. Its `m_worlds` comes from a module
        # constant (`M_WORLDS = 32`) used ONLY for the plan's cost arithmetic —
        # `total_arm_playouts`, `oracle_worker_secs`, `eta_by_workers`. It never
        # reaches a seed, a position, an arm or a digest: world and playout seeds
        # are `sha256(tag|rid|j|salt)`, keyed on the rid and the salt, with no M
        # term at all. So a corpus plan saying 32 while the stratum is scored at
        # 128 is not a defect — it is a cost estimate written by a tool that does
        # not know the scoring budget. S2 "passed" only because 32 happens to
        # equal its committed M.
        #
        # The REAL M gate is `G-M`, which reads `RUN_MANIFEST_{S1,S2}.json::
        # m_worlds` — written by `run_tiletie --m`, the flag that actually sets
        # the scoring budget. Nothing here can or should substitute for it.
        #
        # What IS worth asserting is the M this tool STAMPS into
        # `POSITION_ORDER.json`, which the allocation and the chunk sizing are
        # read against: it must equal the stratum's committed M.
        m_committed = M_BY_STRATUM[stratum]
        m_stamped = int(doc["strata"][stratum]["m"])
        if m_stamped != m_committed:
            _die(f"{stratum}: POSITION_ORDER.json stamps m={m_stamped} but the "
                 f"pair commits m={m_committed} for this stratum. The stamp is "
                 f"what the allocation is read against, so a disagreement here "
                 f"IS a defect.")
        m_plan = int(plan["m_worlds"])
        if m_plan != m_committed:
            log(f"{stratum}: NOTE corpus plan m_worlds={m_plan} vs committed "
                f"m={m_committed}. NOT a defect and NOT asserted: "
                f"build_positions has no --m flag and its m_worlds is "
                f"cost-arithmetic metadata only (it never enters seeds, "
                f"positions, arms or digests). The M of record is G-M's, read "
                f"from RUN_MANIFEST via run_tiletie --m.")
        leg_rows = read_leg_files(src, plan)
        cross = check_corpus_leg_layer(arms, leg_rows, where=f"{stratum} corpus {src}")
        chunks = chunks_by_stratum[stratum]

        inv = check_whole_rid(chunks, leg_rows)
        if not inv["ok"]:
            _die(f"{stratum}: WHOLE-RID INVARIANT VIOLATED — {inv}")

        written = []
        for i, ch in enumerate(chunks, 1):
            d = chunk_dir(out_root, stratum, i)
            p = write_chunk_dir(d, set(ch), source_dir=src, source_plan=plan,
                                source_arms=arms, dropped=dropped,
                                leg_rows=leg_rows, label=f"{stratum}/chunk{i}",
                                chunk_index=i, n_chunks=len(chunks),
                                order_sha256=doc["strata"][stratum]["sha256_order"])
            written.append({"chunk": i, "dir": str(d), "n": p["n_positions"],
                            "roots": p["n_roots"], "legs": p["total_legs"],
                            "playouts": p["total_arm_playouts"],
                            "counts_by_profile_leg": p["counts_by_profile_leg"]})
        summary["strata"][stratum] = {
            "source_positions_dir": str(src),
            "m": m_committed,                  # the committed, stamped M
            # the corpus plan's own number, carried for audit. Cost-arithmetic
            # metadata written by build_positions, NOT the scoring budget.
            "m_plan_cost_metadata": m_plan,
            "n": doc["strata"][stratum]["n"],
            "n_roots": doc["strata"][stratum]["n_roots"],
            "chunks": written,
            "whole_rid_invariant": {"ok": True, "n_rids": inv["n_rids"]},
            "cross_layer_invariant": cross,
            "totals": {
                "legs": sum(w["legs"] for w in written),
                "playouts": sum(w["playouts"] for w in written),
            },
        }

    summary["governance"] = ("Measurement plumbing only. Scores nothing, reads no "
                             "record, no value and no statistic. No results.csv "
                             "row, no band, no claim id. Writes NOTHING under "
                             "shared_run_r4/.")
    (out_root / "CHUNK_SUMMARY.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


def cmd_verify(a) -> int:
    out_root = Path(a.out_root).resolve()
    order_path = out_root / "POSITION_ORDER.json"
    if not order_path.is_file():
        _die(f"{order_path} does not exist — stage first")

    sources = _resolve_sources(a)
    loaded = {s: load_plan_dir(d) for s, d in sources.items()}
    on_disk = json.loads(order_path.read_text())
    chunk_counts = {s: int(on_disk["strata"][s]["chunks"]) if s in on_disk["strata"]
                    else DEFAULT_CHUNKS[s] for s in STRATA}
    doc, chunks_by_stratum = build_order_doc(
        {s: v[1] for s, v in loaded.items()}, chunk_counts,
        source_dirs=sources, seed=int(on_disk.get("seed", PERMUTATION_SEED)))

    if a.stratum is None and order_path.read_text() != order_payload(doc):
        _die(f"{order_path} is NOT byte-identical to the re-derivation from seed "
             f"{doc['seed']}. The chunk membership on disk does not match this "
             f"corpus. DO NOT LAUNCH.")

    for stratum, chunks in chunks_by_stratum.items():
        want_sha = doc["strata"][stratum]["sha256_order"]
        got_sha = (on_disk["strata"].get(stratum) or {}).get("sha256_order")
        if got_sha != want_sha:
            _die(f"{stratum}: committed order digest MISMATCH "
                 f"({got_sha} != {want_sha}). DO NOT LAUNCH.")
        plan, arms, _ = loaded[stratum]
        leg_rows = read_leg_files(sources[stratum], plan)
        check_corpus_leg_layer(arms, leg_rows,
                               where=f"{stratum} corpus {sources[stratum]}")
        inv = check_whole_rid(chunks, leg_rows)
        if not inv["ok"]:
            _die(f"{stratum}: WHOLE-RID INVARIANT VIOLATED — {inv}")
        for i, ch in enumerate(chunks, 1):
            d = chunk_dir(out_root, stratum, i)
            if not (d / ARMS_NAME).is_file():
                _die(f"{d} has not been staged")
            have = set(json.loads((d / ARMS_NAME).read_text()))
            if have != set(ch):
                _die(f"{d} holds {len(have)} rids, the committed order says "
                     f"{len(ch)}; sets differ. DO NOT LAUNCH.")
            cp = json.loads((d / PLAN_NAME).read_text())
            chunk_leg_rids = set()
            for key, info in (cp.get("files") or {}).items():
                p = Path(info["path"])
                if not p.is_file():
                    _die(f"{p} missing (chunk {stratum}/chunk{i}, leg {key})")
                lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
                if len(lines) != int(info["n"]):
                    _die(f"{p} has {len(lines)} lines, its plan says {info['n']}")
                chunk_leg_rids.update(json.loads(ln)["rid"] for ln in lines)
            # the same cross-layer invariant, per chunk (D4.3)
            if chunk_leg_rids != have:
                _die(f"{d}: CROSS-LAYER INVARIANT VIOLATED — its leg files "
                     f"enumerate {len(chunk_leg_rids)} rid(s) against an "
                     f"ARMS.json of {len(have)} "
                     f"({len(have - chunk_leg_rids)} with no leg line, "
                     f"{len(chunk_leg_rids - have)} not in ARMS). DO NOT LAUNCH.")
            # the corpus properties the gates address must survive the subset
            for k in ("uncapped", "cap_j", "deployed_cap_j", "m_worlds",
                      "sample_seed", "world_seed_salt"):
                if k in plan and cp.get(k) != plan.get(k):
                    _die(f"{d}: {k} = {cp.get(k)!r} but the corpus plan says "
                         f"{plan.get(k)!r} — a chunk plan MUST carry it verbatim")
            if (cp.get("afterstate_dedupe") or {}).get("applied") is not True:
                _die(f"{d}: afterstate_dedupe.applied is not True — "
                     f"run_tiletie's preflight would refuse it")
        print(f"[stage_chunks] VERIFY OK — {stratum}: "
              f"n={doc['strata'][stratum]['n']} roots="
              f"{doc['strata'][stratum]['n_roots']} "
              f"chunks={doc['strata'][stratum]['chunk_sizes']} "
              f"(whole-rid invariant holds over {inv['n_rids']} rids)")
    print(f"[stage_chunks] VERIFY OK — POSITION_ORDER.json byte-identical "
          f"(seed {doc['seed']})")
    return 0


# --------------------------------------------------------------------------- #
# completion staging (D4)                                                      #
# --------------------------------------------------------------------------- #
def scored_rids_by_judge(record_roots) -> dict:
    """{judge: {rid, …}} read from the EXISTING RECORD TREES.

    ⚠️ NEVER OPENS A RECORD. A record's rid is its FILE NAME — `merge_legs`'
    blindness discipline verbatim, so no value, mean, `arb`, `ora` or Δ passes
    through the tool that decides what still needs scoring. That matters here
    more than anywhere: D4's licence rests on no outcome having been observed.

    Accepts either a merged stratum tree (`<judge>/<profile>/leg<N>/records/`) or
    a per-chunk tree (`chunk<k>/<judge>/…`) — the judge is the component four
    levels above the record file in both shapes.
    """
    out: dict = {}
    for root in record_roots or ():
        root = Path(root)
        if not root.is_dir():
            _die(f"records root absent: {root}")
        for f in root.rglob("records/*.json"):
            rel = f.relative_to(root).parts
            if len(rel) < 5:
                _die(f"unrecognised record path {f} under {root} — expected "
                     f"<judge>/<profile>/leg<N>/records/<rid>.json")
            out.setdefault(rel[-5], set()).add(f.stem)
    return out


def completion_remainder(arms, order, scored_by_judge: dict) -> tuple:
    """(remainder_in_committed_order, scored_set, report) — or die.

    THE guard of D4.2: the increment must be *the rest*, never *more*. Every way
    that could fail is a refusal here, not a note:

      * a rid scored by one judge and not the other → the remainder is
        AMBIGUOUS (the two judges would need different supplementary sets, and
        `G-CRN` joins them per rid);
      * a scored rid outside `ARMS.json` → the record tree and the committed
        corpus describe different populations;
      * a committed rid absent from `POSITION_ORDER.json` → the order was cut
        for a different corpus, so "no re-shuffle" would be meaningless.
    """
    arms_rids, order = set(arms), list(order)
    if not scored_by_judge:
        _die("no records found under the given --records-root(s). A 'completion' "
             "of a corpus nothing has scored is not a completion — check the "
             "path before staging.")
    missing_judges = sorted(set(JUDGES) - set(scored_by_judge))
    if missing_judges:
        _die(f"no records at all for judge(s) {missing_judges} — both judges "
             f"score every rid (G-CRN joins them per rid), so the remainder "
             f"cannot be derived from one judge's tree")
    per_judge = {j: set(v) for j, v in scored_by_judge.items()}
    both = set.intersection(*per_judge.values())
    either = set.union(*per_judge.values())
    partial = sorted(either - both)
    if partial:
        _die(f"{len(partial)} rid(s) are scored by SOME judges and not others "
             f"(first: {partial[:5]}) — the completion set is AMBIGUOUS. D4's "
             f"set-equality guard cannot be satisfied in both directions until "
             f"this is resolved; escalate rather than staging a guess.")
    outside = sorted(both - arms_rids)
    if outside:
        _die(f"{len(outside)} SCORED rid(s) are not in ARMS.json "
             f"(first: {outside[:5]}) — the record tree and the committed corpus "
             f"describe different populations. Any rid outside the committed set, "
             f"in either direction, VOIDS the completion (D4.2).")
    if set(order) != arms_rids:
        _die(f"POSITION_ORDER.json covers {len(set(order))} rid(s) but ARMS.json "
             f"carries {len(arms_rids)} — the committed order was cut for a "
             f"different corpus. Staging a completion off it would be new "
             f"randomness by another name.")
    remainder = [rid for rid in order if rid not in both]   # COMMITTED ORDER kept
    report = {
        "n_arms": len(arms_rids), "n_scored_both_judges": len(both),
        "n_remainder": len(remainder),
        "scored_by_judge": {j: len(v) for j, v in sorted(per_judge.items())},
        "judges_agree_on_scored_set": True,
        "note": "already-scored = a record under EVERY judge. The remainder is "
                "ARMS.json minus that set, in committed POSITION_ORDER order — "
                "no re-shuffle, no new randomness.",
    }
    return remainder, both, report


def assert_completion_set_equality(staged, want, scored) -> dict:
    """⭐ D4.2's condition, as a check rather than a claim: the supplementary
    chunks must hold EXACTLY `ARMS − already-scored`.

    *"Any rid outside that set, in either direction, voids the completion."* So
    BOTH differences are computed and BOTH refuse — a one-directional check
    would pass a completion that quietly dropped rids, which is the same class
    of miss as the defect it is here to prevent.
    """
    staged, want, scored = set(staged), set(want), set(scored)
    missing, extra = sorted(want - staged), sorted(staged - want)
    overlap = sorted(staged & scored)
    if missing or extra or overlap:
        _die(f"COMPLETION VOID — the supplementary chunks are not exactly "
             f"ARMS − already-scored: {len(missing)} rid(s) of the remainder "
             f"NOT staged (first: {missing[:3]}), {len(extra)} staged rid(s) "
             f"OUTSIDE the remainder (first: {extra[:3]}), {len(overlap)} "
             f"already-scored rid(s) re-staged (first: {overlap[:3]}). D4.2: "
             f"any rid outside that set, in either direction, VOIDS the "
             f"completion.")
    return {
        "ok": True, "both_directions_checked": True,
        "expected": "ARMS.json rids MINUS already-scored rids",
        "n_expected": len(want), "n_staged": len(staged),
        "n_missing_from_staged": 0, "n_extra_in_staged": 0,
        "n_overlap_with_scored": 0,
        "note": "D4.2's third distinguishing fact — the increment is the "
                "pre-committed REMAINDER, not 'more'. Asserted, not claimed.",
    }


def plan_completion_allocation(chunk_playouts, *, w_local, w_laptop,
                               laptop_rate, c_arb, c_if, first_index) -> dict:
    """ALLOCATION.conf's shape, re-derived for the supplementary tranche:
    **local takes ALL the ARB chunks plus a PREFIX of the IF chunks; the laptop
    takes the IF suffix.** The prefix length is chosen to minimise the makespan
    against the same effective-capacity model ALLOCATION.conf is sized on, so
    the arithmetic is derived here rather than typed."""
    n = len(chunk_playouts)
    eff_laptop = w_laptop * laptop_rate
    arb_wh = [p * c_arb / 3600.0 for p in chunk_playouts]
    if_wh = [p * c_if / 3600.0 for p in chunk_playouts]
    total_wh = sum(arb_wh) + sum(if_wh)
    pool = w_local + eff_laptop
    best = None
    for k in range(n + 1):
        local_wh = sum(arb_wh) + sum(if_wh[:k])
        laptop_wh = sum(if_wh[k:])
        h_local = local_wh / w_local if w_local else float("inf")
        h_laptop = (laptop_wh / eff_laptop) if eff_laptop else (
            0.0 if not laptop_wh else float("inf"))
        cand = {
            "n_if_chunks_local": k,
            "local_worker_hours": round(local_wh, 2),
            "laptop_worker_hours": round(laptop_wh, 2),
            "local_hours": round(h_local, 2), "laptop_hours": round(h_laptop, 2),
            "makespan_hours": round(max(h_local, h_laptop), 2),
            "local_share_of_worker_hours": round(local_wh / total_wh, 4) if total_wh else None,
        }
        if best is None or cand["makespan_hours"] < best["makespan_hours"]:
            best = cand
    idx = list(range(first_index, first_index + n))
    best.update({
        "chunks": idx,
        "local_tier1_greedy": idx,                       # ALL the ARB work
        "local_clair_puct": idx[: best["n_if_chunks_local"]],
        "laptop_tier1_greedy": [],
        "laptop_clair_puct": idx[best["n_if_chunks_local"]:],
        "capacity": {
            "w_eval_local": w_local, "w_eval_laptop": w_laptop,
            "laptop_rate": laptop_rate, "laptop_effective": round(eff_laptop, 2),
            "pool_effective": round(pool, 2),
            "ideal_local_share": round(w_local / pool, 4) if pool else None,
        },
        "cost": {
            "c_arb_assumed": c_arb, "c_if_assumed": c_if,
            "playouts_by_chunk": list(chunk_playouts),
            "playouts_total": sum(chunk_playouts),
            "arb_worker_hours": round(sum(arb_wh), 2),
            "if_worker_hours": round(sum(if_wh), 2),
            "total_worker_hours": round(total_wh, 2),
            "ideal_makespan_hours": round(total_wh / pool, 2) if pool else None,
        },
        "note": "throughput ONLY — chunk MEMBERSHIP is fixed by the committed "
                "POSITION_ORDER.json and is identical for both judges. World and "
                "playout seeds are sha256(tag|rid|j|salt): no chunk, no box, no "
                "worker count and no M enters the derivation, so this split "
                "cannot move a value.",
    })
    return best


def allocation_conf_text(stratum: str, alloc: dict) -> str:
    """`ALLOCATION.conf`'s exact key spelling, for the supplementary tranche."""
    cap, cost = alloc["capacity"], alloc["cost"]

    def _lst(v):
        return " ".join(str(x) for x in v)

    return "\n".join([
        f"# ALLOCATION_COMPLETION_{stratum}.conf — the SUPPLEMENTARY tranche's",
        f"# (box x judge x chunk) allocation, emitted by `stage_chunks.py completion`.",
        "#",
        "# ⚠️ SOURCE THIS *INSTEAD OF* ALLOCATION.conf for the supplementary legs, or",
        "# pass the chunk numbers to run_scoring.sh directly — the ALLOC_* keys below",
        "# use the SAME spelling and would otherwise be overridden by the committed",
        "# tranche's values.",
        "#",
        "# ⚠️ THIS FILE CANNOT MOVE A VALUE. " + alloc["note"].replace("\n", " "),
        "#",
        "# --- THE ARITHMETIC -----------------------------------------------------",
        f"#   chunks {alloc['chunks'][0]}..{alloc['chunks'][-1]}  "
        f"({len(alloc['chunks'])} chunks, "
        f"{cost['playouts_total']:,} arm playouts)",
        f"#   IF  {cost['playouts_total']:,} x c_IF  {cost['c_if_assumed']} "
        f"= {cost['if_worker_hours']} wh",
        f"#   ARB {cost['playouts_total']:,} x c_ARB {cost['c_arb_assumed']} "
        f"= {cost['arb_worker_hours']} wh",
        f"#   TRANCHE TOTAL = {cost['total_worker_hours']} wh",
        "#",
        f"#   effective capacity: local W{cap['w_eval_local']} -> "
        f"{cap['w_eval_local']} | laptop W{cap['w_eval_laptop']} x "
        f"{cap['laptop_rate']} -> {cap['laptop_effective']} | pool "
        f"{cap['pool_effective']}",
        f"#   => ideal makespan {cost['ideal_makespan_hours']} h; local should take "
        f"{cap['ideal_local_share']:.1%} of the worker-hours",
        "#",
        f"#   local  : IF chunks {_lst(alloc['local_clair_puct']) or '(none)'} "
        f"+ ARB chunks {_lst(alloc['local_tier1_greedy']) or '(none)'} "
        f"= {alloc['local_worker_hours']} wh",
        f"#            -> {alloc['local_worker_hours']} / {cap['w_eval_local']} "
        f"= {alloc['local_hours']} h",
        f"#   laptop : IF chunks {_lst(alloc['laptop_clair_puct']) or '(none)'} "
        f"= {alloc['laptop_worker_hours']} wh",
        f"#            -> {alloc['laptop_worker_hours']} / "
        f"{cap['laptop_effective']} = {alloc['laptop_hours']} h",
        f"#   => TRANCHE MAKESPAN ~{alloc['makespan_hours']} h "
        f"(local share {alloc['local_share_of_worker_hours']:.1%} vs the "
        f"{cap['ideal_local_share']:.1%} ideal)",
        "#",
        "#   ⚠️ THE LAPTOP GETS NO ARB WORK — load balance, not capability, exactly",
        "#   as in ALLOCATION.conf: ARB is a small share of the bill and far cheaper",
        "#   per playout, so keeping it whole on one box removes a cross-box surface.",
        "",
        f"N_CHUNKS_COMPLETION_{stratum}={len(alloc['chunks'])}",
        f"COMPLETION_CHUNKS_{stratum}=\"{_lst(alloc['chunks'])}\"",
        f"LAPTOP_RATE={cap['laptop_rate']}",
        "",
        f"ALLOC_{stratum}_local_tier1_greedy=\"{_lst(alloc['local_tier1_greedy'])}\"",
        f"ALLOC_{stratum}_local_clair_puct=\"{_lst(alloc['local_clair_puct'])}\"",
        f"ALLOC_{stratum}_laptop_side_tier1_greedy=\"{_lst(alloc['laptop_tier1_greedy'])}\"",
        f"ALLOC_{stratum}_laptop_side_clair_puct=\"{_lst(alloc['laptop_clair_puct'])}\"",
        "",
        "JUDGE_ORDER=\"tier1-greedy clair-puct\"",
        f"STRATUM_ORDER=\"{stratum}\"",
        "",
    ])


def _conf_float(conf: dict, key: str, where: str) -> float:
    if key not in conf:
        _die(f"{where} does not set {key} — the completion allocation is sized "
             f"against it and will not be guessed")
    try:
        return float(conf[key])
    except (TypeError, ValueError):
        _die(f"{where}: {key}={conf[key]!r} is not a number")


def cmd_complete(a) -> int:
    out_root = Path(a.out_root).resolve()
    if not a.stratum:
        _die("completion is staged ONE stratum at a time — pass --stratum")
    stratum = a.stratum
    src = _resolve_sources(a)[stratum]
    plan, arms, dropped = load_plan_dir(src)
    leg_rows = read_leg_files(src, plan)

    # (1) D4.3: the cross-layer invariant, RE-CHECKED before the first
    #     supplementary leg. Staging a completion off a corpus that still has
    #     the defect would produce a second wrong population.
    cross = check_corpus_leg_layer(arms, leg_rows,
                                   where=f"{stratum} corpus {src}")

    # (2) the COMMITTED order, read — never re-derived, never re-shuffled
    order_path = out_root / "POSITION_ORDER.json"
    if not order_path.is_file():
        _die(f"{order_path} does not exist — the committed order is the only "
             f"legal source of the supplementary chunks' ordering")
    doc = json.loads(order_path.read_text())
    st = (doc.get("strata") or {}).get(stratum)
    if st is None:
        _die(f"POSITION_ORDER.json has no stratum {stratum!r}")
    if int(doc.get("seed", -1)) != PERMUTATION_SEED:
        _die(f"POSITION_ORDER.json was cut with seed {doc.get('seed')}, not the "
             f"committed {PERMUTATION_SEED}")
    order = list(st["order"])
    if sha256_list(order) != st["sha256_order"]:
        _die("POSITION_ORDER.json's order does not match its own digest — the "
             "committed permutation changed. DO NOT STAGE.")

    # (3) the remainder = ARMS − already-scored, set-checked both directions
    scored_by_judge = scored_rids_by_judge(a.records_root)
    remainder, scored, rem_report = completion_remainder(arms, order, scored_by_judge)
    if not remainder:
        _die("the remainder is EMPTY — every committed rid already has records "
             "under every judge. There is nothing to complete.")

    n_chunks = int(a.chunks)
    if n_chunks > len(remainder):
        _die(f"--chunks {n_chunks} exceeds the {len(remainder)}-rid remainder")
    chunks = chunk_slices(remainder, n_chunks)

    committed_n = int(st.get("chunks") or len(st.get("chunk_sizes") or []))
    first = int(a.first_index) if a.first_index else committed_n + 1
    existing = [d.name for d in sorted((out_root / "chunks" / stratum).glob("chunk*"))
                if d.is_dir()]
    written = []
    for off, ch in enumerate(chunks):
        k = first + off
        d = chunk_dir(out_root, stratum, k)
        if d.exists():
            _die(f"{d} already exists — a supplementary chunk NEVER overwrites a "
                 f"staged one. Already-scored rids keep their chunks untouched "
                 f"(D4.3); pass --first-index past the existing ones.")
        p = write_chunk_dir(
            d, set(ch), source_dir=src, source_plan=plan, source_arms=arms,
            dropped=dropped, leg_rows=leg_rows, label=f"{stratum}/chunk{k}",
            chunk_index=k, n_chunks=committed_n + n_chunks,
            order_sha256=st["sha256_order"],
            chunk_meta={"completion": {
                "schema": COMPLETION_SCHEMA,
                "tranche": "supplementary",
                "index_within_tranche": off + 1,
                "n_chunks_in_tranche": n_chunks,
                "committed_chunks": committed_n,
                "deviation": "D4 (measurement/tiearb_widening_20260817/"
                             "DEVIATIONS.md) — the union assembled ARMS but not "
                             "leg files, so these rids were committed and never "
                             "scored. Ordering is the SAME committed "
                             "POSITION_ORDER.json (seed 20260817), filtered to "
                             "the not-yet-scored rids: no re-shuffle, no new "
                             "randomness.",
            }})
        written.append({"chunk": k, "dir": str(d), "n": p["n_positions"],
                        "roots": p["n_roots"], "legs": p["total_legs"],
                        "playouts": p["total_arm_playouts"]})

    # (4) ⭐ THE SET-EQUALITY GUARD, BOTH DIRECTIONS (D4.2's condition, not a note)
    staged = set()
    for w in written:
        staged |= set(json.loads((Path(w["dir"]) / ARMS_NAME).read_text()))
    want = set(remainder)
    set_equality = assert_completion_set_equality(staged, want, scored)

    conf = WP.parse_conf(CAMPAIGN / "WORKERS.conf")
    alloc_conf = WP.parse_conf(HERE / "ALLOCATION.conf")
    alloc = plan_completion_allocation(
        [w["playouts"] for w in written],
        w_local=_conf_float(conf, "W_EVAL_LOCAL", "WORKERS.conf"),
        w_laptop=_conf_float(conf, "W_EVAL_LAPTOP", "WORKERS.conf"),
        laptop_rate=_conf_float(alloc_conf, "LAPTOP_RATE", "ALLOCATION.conf"),
        c_arb=_conf_float(alloc_conf, "C_ARB_ASSUMED", "ALLOCATION.conf"),
        c_if=_conf_float(alloc_conf, "C_IF_ASSUMED", "ALLOCATION.conf"),
        first_index=first)
    alloc_path = out_root / f"ALLOCATION_COMPLETION_{stratum}.conf"
    alloc_path.write_text(allocation_conf_text(stratum, alloc))

    summary = {
        "schema": COMPLETION_SCHEMA, "run_id": RUN_ID, "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE, "deviation": "D4",
        "stratum": stratum, "source_positions_dir": str(src),
        "position_order": str(order_path), "permutation_seed": PERMUTATION_SEED,
        "position_order_sha256": st["sha256_order"],
        "records_roots": [str(r) for r in (a.records_root or ())],
        "cross_layer_invariant": cross,
        "remainder": rem_report,
        "set_equality": set_equality,
        "chunks": written,
        "first_chunk_index": first, "n_chunks": n_chunks,
        "committed_chunks": committed_n, "pre_existing_chunk_dirs": existing,
        "allocation": alloc, "allocation_conf": str(alloc_path),
        "ordering": "the SAME committed POSITION_ORDER.json, filtered to the "
                    "not-yet-scored rids and cut into near-equal SEQUENTIAL "
                    "chunks. No re-shuffle, no new seed, already-scored rids' "
                    "chunks untouched.",
        "governance": ("Measurement plumbing only. Scores nothing, opens no "
                       "record, reads no value and no statistic. Writes NOTHING "
                       "under the prereg dir."),
    }
    out_path = out_root / f"COMPLETION_PLAN_{stratum}.json"
    out_path.write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))
    log(f"{stratum}: staged {n_chunks} supplementary chunk(s) "
        f"{first}..{first + n_chunks - 1} over {len(want)} never-scored rid(s) "
        f"(ARMS {rem_report['n_arms']} − scored {rem_report['n_scored_both_judges']}) "
        f"— set equality holds in BOTH directions")
    log(f"{stratum}: allocation -> {alloc_path} "
        f"(local IF {alloc['local_clair_puct']} + ARB {alloc['local_tier1_greedy']}, "
        f"laptop IF {alloc['laptop_clair_puct']}, makespan ~{alloc['makespan_hours']} h)")
    return 0


def cmd_clean(a) -> int:
    """Delete the staged chunk dirs (NOT POSITION_ORDER.json). Plumbing only."""
    out_root = Path(a.out_root)
    for stratum in STRATA:
        if a.stratum and stratum != a.stratum:
            continue
        d = out_root / "chunks" / stratum
        if d.is_dir():
            shutil.rmtree(d)
            print(f"[stage_chunks] removed {d}")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--out-root", default=str(CAMPAIGN),
                       help="where POSITION_ORDER.json and chunks/ live "
                            "(default: the campaign dir, OUTSIDE the prereg dir)")
        p.add_argument("--s1-dir", default=None, help="override the S1 corpus dir")
        p.add_argument("--s2-dir", default=None, help="override the S2 corpus dir")
        p.add_argument("--stratum", default=None, choices=list(STRATA))

    s = sub.add_parser("stage", help="write POSITION_ORDER.json + the chunk plan dirs")
    common(s)
    s.add_argument("--chunks-s1", type=int, default=DEFAULT_CHUNKS["s1"])
    s.add_argument("--chunks-s2", type=int, default=DEFAULT_CHUNKS["s2"])
    s.add_argument("--allow-m-mismatch", action="store_true",
                   help="ACCEPTED AND INERT. The corpus plan's m_worlds is no "
                        "longer asserted against the committed M — it is "
                        "cost-arithmetic metadata, reported not gated — so "
                        "there is nothing left to waive. Kept so existing "
                        "fixture invocations keep working rather than failing "
                        "on an unknown flag.")
    s.set_defaults(fn=cmd_stage)

    v = sub.add_parser("verify", help="re-derive and assert byte-identity")
    common(v)
    v.set_defaults(fn=cmd_verify)

    p = sub.add_parser("completion",
                       help="stage SUPPLEMENTARY chunks for committed rids that "
                            "no box ever scored (deviation D4)")
    common(p)
    p.add_argument("--records-root", action="append", default=None, required=True,
                   help="an existing record tree (SHARE/<RUN_ID>/<stratum> or "
                        "SHARE/<RUN_ID>/chunks/<stratum>); repeatable. Record "
                        "FILE NAMES only are read — never their contents")
    p.add_argument("--chunks", type=int, default=DEFAULT_CHUNKS["s1"],
                   help="how many supplementary chunks to cut the remainder into")
    p.add_argument("--first-index", type=int, default=None,
                   help="first supplementary chunk number (default: one past the "
                        "committed chunk count, so nothing is ever overwritten)")
    p.set_defaults(fn=cmd_complete)

    c = sub.add_parser("clean", help="remove the staged chunk dirs")
    common(c)
    c.set_defaults(fn=cmd_clean)
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
