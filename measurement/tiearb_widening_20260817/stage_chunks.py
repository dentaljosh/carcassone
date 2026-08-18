#!/usr/bin/env python3
"""PLAN SURGERY for the tie-arbiter WIDENING shared run — the TWO-BOX chunk layer.

It scores NOTHING. It reads no record, no oracle value, no mean, no sd and no
statistic. It only cuts the two already-built corpus plan dirs into the shapes
`run_tiletie.py` consumes, one per (stratum, chunk).

    stage   — write `POSITION_ORDER.json` (ONE seeded shuffle per stratum of that
              stratum's SORTED rid list) and cut each stratum's order into
              `--chunks-s1` / `--chunks-s2` near-equal SEQUENTIAL chunks, one
              `run_tiletie`-shaped plan dir each, under `chunks/<stratum>/chunk<k>/`.
    verify  — re-derive both permutations and assert BYTE-IDENTITY with the
              committed `POSITION_ORDER.json`, plus rid-set identity with every
              staged chunk dir and line counts with every chunk leg file.

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

import build_tiearb_plan as BTP  # noqa: E402  (path insert must precede the import)

RUN_ID = "tiearb_widening_20260817"
CAMPAIGN = REPO / "measurement" / RUN_ID
RUN_DIR = CAMPAIGN / "shared_run"                 # the FROZEN prereg dir — read only
SCHEMA = "carcassonne-tiearb-widening-chunks/v1"
DESIGN_DOC = f"measurement/{RUN_ID}/shared_run/DESIGN.md"
READ_RULE = f"measurement/{RUN_ID}/shared_run/READ_RULE.md"

#: ONE committed seed, one shuffle per stratum, written BEFORE launch.
#: Deliberately NOT the corpus `--sample-seed` (20260819, DESIGN §4): the mining
#: draw and the throughput permutation are different draws and must not be
#: confusable by a later reader.
PERMUTATION_SEED = 20260817

STRATA = ("s1", "s2")

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
                    n_chunks: int, order_sha256: str) -> dict:
    """Write a `run_tiletie`-shaped plan dir restricted to `keep`."""
    out_dir = Path(out_dir)
    unknown = sorted(r for r in keep if r not in source_arms)
    if unknown:
        _die(f"unknown rid(s) in {label}: {unknown[:5]}")

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for key, rows in sorted(leg_rows.items()):
        sel = [line for rid, line in rows if rid in keep]     # SOURCE ORDER kept
        if not sel:
            continue
        path = out_dir / f"positions_{key.replace('/', '_')}.jsonl"
        path.write_text("".join(ln + "\n" for ln in sel))
        files[key] = {"n": len(sel), "path": str(path)}
    if not files:
        _die(f"{label}: no leg lines selected — the chunk would score nothing")

    arms = {r: source_arms[r] for r in sorted(keep)}
    (out_dir / ARMS_NAME).write_text(json.dumps(arms, indent=1))

    if dropped is not None:
        # copied WHOLE, deliberately: the analytic-zero population is a property
        # of the FULL supply (the tiearb2 precedent does the same).
        (out_dir / DROPPED_NAME).write_text(json.dumps(dropped, indent=1))

    plan = subset_plan(source_plan, keep, source_arms, files, label=label,
                       out_dir=out_dir, chunk_index=chunk_index,
                       n_chunks=n_chunks, order_sha256=order_sha256)
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
        m_plan = int(plan["m_worlds"])
        if m_plan != M_BY_STRATUM[stratum] and not a.allow_m_mismatch:
            _die(f"{stratum}: corpus plan m_worlds={m_plan} but DESIGN §4 fixes "
                 f"{M_BY_STRATUM[stratum]} for this stratum. "
                 f"(--allow-m-mismatch only for fixtures.)")
        leg_rows = read_leg_files(src, plan)
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
            "m": m_plan,
            "n": doc["strata"][stratum]["n"],
            "n_roots": doc["strata"][stratum]["n_roots"],
            "chunks": written,
            "whole_rid_invariant": {"ok": True, "n_rids": inv["n_rids"]},
            "totals": {
                "legs": sum(w["legs"] for w in written),
                "playouts": sum(w["playouts"] for w in written),
            },
        }

    summary["governance"] = ("Measurement plumbing only. Scores nothing, reads no "
                             "record, no value and no statistic. No results.csv "
                             "row, no band, no claim id. Writes NOTHING under "
                             "shared_run/.")
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
            for key, info in (cp.get("files") or {}).items():
                p = Path(info["path"])
                if not p.is_file():
                    _die(f"{p} missing (chunk {stratum}/chunk{i}, leg {key})")
                n = sum(1 for ln in p.read_text().splitlines() if ln.strip())
                if n != int(info["n"]):
                    _die(f"{p} has {n} lines, its plan says {info['n']}")
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
                            "(default: the campaign dir, OUTSIDE shared_run/)")
        p.add_argument("--s1-dir", default=None, help="override the S1 corpus dir")
        p.add_argument("--s2-dir", default=None, help="override the S2 corpus dir")
        p.add_argument("--stratum", default=None, choices=list(STRATA))

    s = sub.add_parser("stage", help="write POSITION_ORDER.json + the chunk plan dirs")
    common(s)
    s.add_argument("--chunks-s1", type=int, default=DEFAULT_CHUNKS["s1"])
    s.add_argument("--chunks-s2", type=int, default=DEFAULT_CHUNKS["s2"])
    s.add_argument("--allow-m-mismatch", action="store_true",
                   help="fixtures only: skip the DESIGN §4 m_worlds assertion")
    s.set_defaults(fn=cmd_stage)

    v = sub.add_parser("verify", help="re-derive and assert byte-identity")
    common(v)
    v.set_defaults(fn=cmd_verify)

    c = sub.add_parser("clean", help="remove the staged chunk dirs")
    common(c)
    c.set_defaults(fn=cmd_clean)
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
