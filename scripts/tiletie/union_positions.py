#!/usr/bin/env python3
"""Assemble the corpus of record: RETAINED band-135e9 positions + the fresh
137e9 EXTENSION, under the LIVE (R4) prereg dir — rev R4.5.

`PREREG_FAILURE` §3 disposes of the R3.3 run as **pair SPENT, corpus REUSABLE
INPUT**: the run stopped PRE-SCORING, so no `arb`, `ora`, `Δ`, CI or
per-position value was ever computed for band 135e9's positions — not "we did
not look" but "it was never computed". Those positions are therefore valid
input to R4, and R4 sizes its extension on the assumption that they are in hand.

They live under the SPENT pair's directory, which is **READ-ONLY FOREVER**. So
the union is assembled by COPY, never by move, never by writing anything back:

    <banked>/corpus/positions_{s1,s2}     READ-ONLY source (135e9, retained)
    <run>/corpus/positions_{s1,s2}_ext    the extension this driver built (137e9)
    <run>/corpus/positions_{s1,s2}        the UNION — what every gate reads

Two invariants the assembly enforces rather than assumes:

  1. **Excluded rids never enter the union.** R4-3 rule 5 requires exclusions
     applied BEFORE `POSITIONS_PLAN` freezes, and the retained corpus carries
     the one collision that killed R3.3 (`tt_sp_135000000122_p2`) — which is
     excluded in R4 too, under R4's own pre-committed rule, **not
     re-adjudicated**. The exclusion list is applied to the banked side here.
  2. **Rid collisions between the two sides are impossible by band**, so any
     collision is a BUG, not a transposition, and it raises rather than
     silently letting one side win.

The union's `POSITIONS_PLAN.json` records both provenances and the counts, so a
later reader can see exactly how many positions came from which band without
re-deriving it.

──────────────────────────────────────────────────────────────────────────────
⚠️ THE CROSS-LAYER INVARIANT (D4.3, ruling `751bdd12`) — added after the defect
this module caused. The first assembly merged `ARMS.json` (both sides) but left
the LEG FILES extension-only: the plan's `files` block still pointed into
`positions_s1_ext/`, so both judges scored only the fresh rids and the 551
retained rids were never scored by any box. Three "complete" signals were all
TRUE — each of a DIFFERENT population — because **nothing ever asserted that the
leg files enumerate exactly the `ARMS.json` rid set.** Every layer checked
itself against itself.

So the assembly now:

  1. builds the union LEG FILES physically, per plan `files` key, from BOTH
     sides (copied, never symlinked — every byte is re-serialised here);
  2. points `POSITIONS_PLAN.json::files` at those UNION-LOCAL files;
  3. asserts **set equality, in BOTH directions**, between the rids the leg
     files enumerate and the rids `ARMS.json` carries — BEFORE anything is
     written, so a violation leaves no half-corpus behind; and
  4. records a **LEG-LAYER WITNESS** in `CORPUS_UNION.json` (per-leg-file rid
     counts + sha256 digests). The old stamp's failure was not that it lied: it
     asserted at the ARMS layer a property only the leg layer could witness, and
     a reissue without a leg-layer field would repeat that exactly. Any existing
     stamp is PRESERVED BY RENAME, never silently overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

PLAN = "POSITIONS_PLAN.json"
ARMS = "ARMS.json"
DROPPED = "DROPPED_ALL_TRANSPOSITION.json"
#: R4-0.5 §3 — the provenance stamp that makes the union unambiguous. ONE file
#: for the whole corpus, keyed by stratum, so a reader sees the composition of
#: `n` in one place. R4's `n` is a MIXTURE and the read-out must show it.
UNION_STAMP = "CORPUS_UNION.json"
#: v2 = the LEG-LAYER WITNESS (D4.7). A v1 stamp asserted the copy at the ARMS
#: layer for an assembly that never happened at the leg layer.
UNION_SCHEMA = "carcassonne-tiearb-widening-corpus-union/v2"
#: Where a pre-fix (leg-layer-unwitnessed) stamp is preserved to. It is EVIDENCE
#: of the defect and must stay readable — D4.7: "never silently overwrite".
DEFECTIVE_STAMP = "CORPUS_UNION.r4.5-defective.json"
#: The leg files this module assembles: `positions_<profile>_leg<N>.jsonl`, the
#: spelling `build_positions` writes and `stage_chunks` re-writes per chunk.
DEFAULT_LEG_GLOB = "positions_*_leg*.jsonl"


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


#: Returned instead of `None` when the banked artifacts are not in git (a
#: scratch fixture). ⚠️ NOT null: `by_stratum.*.origin_commit` is a read
#: address, and READ_RULE §1.2's allow_null table is CLOSED at four entries.
#: Widening it for one field would be the "this null is fine too" move that
#: turns a fail-closed rule fail-open; a sentinel STRING keeps the address
#: resolving and still says plainly that there is no commit.
UNTRACKED = "untracked"


def origin_commit(path, repo=REPO) -> str:
    """The commit the retained artifacts were last written by — the `origin
    commit` R4-0.5 §3 requires."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "-n", "1", "--format=%H", "--",
             str(path)],
            capture_output=True, text=True, check=True)
        return r.stdout.strip() or UNTRACKED
    except (OSError, subprocess.CalledProcessError):
        return UNTRACKED


class UnionError(RuntimeError):
    """The union cannot be assembled as specified. Never repaired in place."""


def load_rid_exclusions(paths) -> set:
    out = set()
    for p in paths or ():
        p = Path(p)
        if not p.is_file():
            raise UnionError(f"exclusion list not found: {p}")
        for line in p.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(line)
    return out


def leg_key_of(name: str) -> str:
    """`positions_walled_leg1.jsonl` -> `walled/leg1` — the `files` key spelling
    the corpus plan, `stage_chunks` and `merge_legs` all address a leg by."""
    stem = Path(name).name
    if stem.startswith("positions_"):
        stem = stem[len("positions_"):]
    if stem.endswith(".jsonl"):
        stem = stem[: -len(".jsonl")]
    profile, sep, leg = stem.rpartition("_leg")
    if not sep:
        raise UnionError(f"leg file {name!r} is not `positions_<profile>_leg<N>.jsonl`")
    return f"{profile}/leg{leg}"


def leg_filename(key: str) -> str:
    """The inverse of `leg_key_of` — `walled/leg1` -> `positions_walled_leg1.jsonl`."""
    return f"positions_{key.replace('/', '_')}.jsonl"


def _read_leg_rows(path) -> list:
    """[(rid, raw_line), …] preserving SOURCE LINE ORDER.

    Raw text, deliberately: a union leg file's bytes for a given rid are then
    identical to the source leg file's bytes for that rid, which is what makes
    the copy checkable by digest.
    """
    rows = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rows.append((json.loads(line)["rid"], line))
    return rows


def side_leg_rows(side_dir, plan, *, leg_glob=DEFAULT_LEG_GLOB) -> dict:
    """{"<profile>/leg<N>": [(rid, raw_line), …]} for ONE side.

    The side's own `POSITIONS_PLAN.json::files` block is authoritative when it
    has one (it names the legs the corpus is defined over); otherwise the leg
    files are discovered by glob, which is what the retained R3.3 corpus needs
    (its plan predates the `files` block).
    """
    side_dir = Path(side_dir)
    files = ((plan or {}).get("files") or {})
    out: dict = {}
    if files:
        for key, info in sorted(files.items()):
            p = Path(info["path"])
            if not p.is_file():
                p = side_dir / Path(info["path"]).name
            if not p.is_file():
                raise UnionError(
                    f"{side_dir}: POSITIONS_PLAN names leg {key} at "
                    f"{info['path']} but no such file exists — the plan's files "
                    f"block and the directory disagree")
            out[key] = _read_leg_rows(p)
        return out
    for p in sorted(side_dir.glob(leg_glob)):
        out.setdefault(leg_key_of(p.name), []).extend(_read_leg_rows(p))
    return out


def check_leg_layer(arms_rids, leg_rids, *, where: str) -> dict:
    """⭐ THE CROSS-LAYER INVARIANT (D4.3): the leg files must enumerate EXACTLY
    the `ARMS.json` rid set. Checked as a SET EQUALITY in BOTH DIRECTIONS —
    the defect this prevents was a strict SUBSET, which every one-directional
    "are all my leg rids known?" check passes happily."""
    arms_rids, leg_rids = set(arms_rids), set(leg_rids)
    missing = sorted(arms_rids - leg_rids)      # in ARMS, no leg line -> UNSCORABLE
    extra = sorted(leg_rids - arms_rids)        # leg line, not in ARMS -> UNPLANNED
    ok = not missing and not extra
    report = {
        "ok": ok, "both_directions_checked": True,
        "n_arms": len(arms_rids), "n_leg": len(leg_rids),
        "n_in_arms_not_in_legs": len(missing), "n_in_legs_not_in_arms": len(extra),
        "in_arms_not_in_legs": missing[:10], "in_legs_not_in_arms": extra[:10],
    }
    if not ok:
        raise UnionError(
            f"CROSS-LAYER INVARIANT VIOLATED at {where}: the leg files do NOT "
            f"enumerate exactly the ARMS.json rid set — "
            f"{len(missing)} rid(s) in ARMS with NO leg line "
            f"(first: {missing[:3]}), {len(extra)} leg rid(s) NOT in ARMS "
            f"(first: {extra[:3]}). This is the D4 defect: a corpus whose ARMS "
            f"layer and leg layer describe different populations scores the "
            f"SMALLER one while every count reads complete.")
    return report


def assemble(banked_dir, ext_dir, out_dir, *, exclude_rids=(), stratum="s1",
             leg_glob=DEFAULT_LEG_GLOB) -> dict:
    """Build the union. Returns the provenance block written into the plan."""
    banked, ext, out = Path(banked_dir), Path(ext_dir), Path(out_dir)
    if out.resolve() == banked.resolve():
        raise UnionError(
            f"the union would be written INTO the banked (spent) corpus at "
            f"{banked} — it is READ-ONLY FOREVER (rev R4.5)")
    excl = set(exclude_rids)

    sides = {}
    for tag, d in (("banked", banked), ("extension", ext)):
        if not d.is_dir():
            sides[tag] = None
            continue
        a = d / ARMS
        if not a.is_file():
            raise UnionError(f"{tag} side has no {ARMS}: {d}")
        p = d / PLAN
        sides[tag] = {"dir": d, "arms": json.loads(a.read_text()),
                      "plan": json.loads(p.read_text()) if p.is_file() else None}
    if not any(sides.values()):
        raise UnionError(f"neither side exists: {banked} / {ext}")

    merged, dropped_rows = {}, []
    #: {"<profile>/leg<N>": [(rid, raw_line), …]} — the UNION's leg rows, banked
    #: side first then extension, each side in its own source line order.
    union_rows: dict = {}
    #: which side each union leg line came from, for the leg-layer witness
    rows_by_side = {"banked": 0, "extension": 0}
    counts = {"banked_in": 0, "banked_excluded": 0, "banked_kept": 0,
              "extension_in": 0, "extension_excluded": 0, "extension_kept": 0}
    for tag in ("banked", "extension"):
        side = sides[tag]
        if not side:
            continue
        for rid, meta in sorted(side["arms"].items()):
            counts[f"{tag}_in"] += 1
            if rid in excl:
                counts[f"{tag}_excluded"] += 1
                continue
            if rid in merged:
                # impossible by band construction — so it is a BUG, and a bug
                # that silently let one side win would corrupt the corpus
                raise UnionError(
                    f"rid {rid!r} appears in BOTH the banked and the extension "
                    f"side. That is impossible by band construction (135e9 vs "
                    f"137e9), so it is an instrument bug, not a transposition.")
            meta = dict(meta)
            meta.setdefault("provenance", tag)
            merged[rid] = meta
            counts[f"{tag}_kept"] += 1
        dp = side["dir"] / DROPPED
        if dp.is_file():
            dropped_rows += (json.loads(dp.read_text()).get("rows") or [])
        # ⭐ THE LEG LAYER. The first version of this module read only
        # `positions_*_leg1.jsonl` by glob and wrote ONE hard-coded union file
        # that the plan never pointed at — which is exactly how 551 committed
        # rids came to have no leg line in the corpus of record.
        for key, rows in side_leg_rows(side["dir"], side["plan"],
                                       leg_glob=leg_glob).items():
            kept = [(rid, line) for rid, line in rows if rid not in excl]
            if kept:
                union_rows.setdefault(key, []).extend(kept)
                rows_by_side[tag] += len(kept)

    # ⚠️ ASSERTED BEFORE ANYTHING IS WRITTEN, so a violation leaves no
    # half-assembled corpus on disk for a later reader to mistake for a corpus.
    leg_rids = {rid for rows in union_rows.values() for rid, _ in rows}
    leg_check = check_leg_layer(merged, leg_rids, where=f"union {out}")

    out.mkdir(parents=True, exist_ok=True)
    (out / ARMS).write_text(json.dumps(merged, indent=2, sort_keys=True))
    (out / DROPPED).write_text(json.dumps({"rows": dropped_rows}, indent=2,
                                          sort_keys=True))

    # the union's OWN leg files — copied (re-serialised), never symlinked, and
    # named by the same key spelling the plan's `files` block addresses
    union_files, leg_witness = {}, {}
    for key, rows in sorted(union_rows.items()):
        p = out / leg_filename(key)
        p.write_text("".join(line + "\n" for _, line in rows))
        union_files[key] = {"n": len(rows), "path": str(p)}
        leg_witness[key] = {
            "name": p.name, "path": str(p), "n_lines": len(rows),
            "n_rids": len({rid for rid, _ in rows}), "sha256": sha256_file(p),
        }

    # the union's plan: take the extension side's plan as the template (it was
    # built by THIS driver at this rev), then overwrite the counts with the
    # union's own and record BOTH provenances.
    template = None
    for tag in ("extension", "banked"):
        side = sides[tag]
        if side and (side["dir"] / PLAN).is_file():
            template = json.loads((side["dir"] / PLAN).read_text())
            break
    if template is None:
        raise UnionError("neither side carries a POSITIONS_PLAN.json template")
    n_capped = sum(1 for v in merged.values() if v.get("capped_at_4"))
    # ⚠️ COPIED, NEVER SYMLINKED (R4-0.5 §2, explicit): a symlink into a frozen
    # directory invites a WRITE-THROUGH — a later tool that opens the union for
    # append would mutate the spent run's tracked artifacts — and it breaks on
    # any later archive or move. Every byte above was read and re-serialised, so
    # nothing under the union is a link to the banked tree. Asserted, not
    # assumed, because "we only ever read it" is exactly the assumption a
    # write-through violates.
    linked = [str(p) for p in out.rglob("*") if p.is_symlink()]
    if linked:
        raise UnionError(
            f"the union contains SYMLINK(S) {linked[:3]} — R4-0.5 requires the "
            f"retained positions be COPIED, never symlinked: a link into the "
            f"frozen directory invites a write-through and breaks on any later "
            f"archive or move")

    per_file_sha = {}
    for tag, side in (("banked", sides["banked"]), ("extension", sides["extension"])):
        if not side:
            continue
        per_file_sha[tag] = {
            f.name: sha256_file(f)
            for f in sorted(side["dir"].iterdir())
            if f.is_file() and not f.name.startswith(".")
        }

    provenance = {
        "rev": "R4.5",
        "stratum": stratum,
        # R4-0.5 §3's four required fields, per stratum:
        "origin_commit": origin_commit(banked),
        "banked_dir": str(banked),          # the path under the OLD RUN
        "sha256_by_file": per_file_sha,     # a sha256 per copied file
        "n_retained": counts["banked_kept"],
        "n_fresh": counts["extension_kept"],
        "banked_readonly": True,
        "copied_not_symlinked": True,
        "extension_dir": str(ext),
        "union_dir": str(out),
        "n_excluded_rids_applied": len(excl),
        # ⭐ D4.7's REQUIRED NEW FIELD — the LEG-LAYER witness. The v1 stamp
        # asserted `copied_not_symlinked` at the ARMS layer for an assembly that
        # never happened at the leg layer; a reissue without this field would
        # repeat that exactly.
        "leg_layer": {
            "witnessed": True,
            "set_equality": leg_check,
            "n_leg_files": len(leg_witness),
            "n_rids_in_leg_files": len(leg_rids),
            "n_rids_in_arms": len(merged),
            "n_lines_by_side": dict(rows_by_side),
            "files": leg_witness,
            "note": "the union's leg files are PHYSICALLY PRESENT in the union "
                    "dir (copied, never symlinked) and POSITIONS_PLAN.json::files "
                    "points at THEM, not at the extension dir. The rid set they "
                    "enumerate was asserted EQUAL to ARMS.json's in BOTH "
                    "directions before this stamp was written (D4.3).",
        },
        **counts,
        "note": "band 135e9 is REUSABLE INPUT (PREREG_FAILURE §3: the R3.3 run "
                "stopped PRE-SCORING, so no arb/ora/delta/CI/per-position value "
                "was ever computed for these positions). The banked directory "
                "is READ-ONLY FOREVER; this union is assembled by COPY, never "
                "by symlink. ⚠️ Retained positions are NOT pre-cleared: they "
                "enter the probe build and are gated exactly like fresh ones. "
                "'Already gated under R3' is not a status any position holds — "
                "R3's gate FAILED, so nothing was ever passed.",
    }
    template.update({
        "n_positions": len(merged),
        "n_positions_capped_at_4": n_capped,
        # ⭐ the plan now points at the UNION's OWN leg files. Leaving this
        # pointing into `positions_<stratum>_ext/` is the D4 defect itself:
        # every downstream layer (stage_chunks, run_tiletie, merge_legs'
        # completeness denominator) resolves "which positions" through here.
        "files": union_files,
        "counts_by_profile_leg": {k: v["n"] for k, v in sorted(union_files.items())},
        "union_provenance": provenance,
    })
    if "exclude_rids" in template and isinstance(template["exclude_rids"], dict):
        template["exclude_rids"] = dict(template["exclude_rids"],
                                        n_requested=len(excl),
                                        n_supply_after_exclusion=len(merged))
    (out / PLAN).write_text(json.dumps(template, indent=2, sort_keys=True))
    write_union_stamp(out.parent, stratum, provenance)
    return provenance


def _leg_layer_witnessed(doc: dict) -> bool:
    """True only if EVERY stratum block carries a passing leg-layer witness.
    A doc that does not is a PRE-FIX stamp: it asserted at the ARMS layer a
    property only the leg layer could witness."""
    strata = (doc or {}).get("by_stratum") or {}
    if not strata:
        return False
    return all(((v or {}).get("leg_layer") or {}).get("witnessed") is True
               for v in strata.values())


def preserve_defective_stamp(p) -> Path:
    """Move a pre-fix `CORPUS_UNION.json` aside rather than overwriting it.

    D4.7, verbatim: *"preserve the old file renamed … never silently overwrite —
    the false assertion is evidence of the defect and must remain readable."*
    An already-taken archive name is never clobbered either; the counter grows.
    """
    p = Path(p)
    dst = p.parent / DEFECTIVE_STAMP
    n = 2
    while dst.exists():
        dst = p.parent / DEFECTIVE_STAMP.replace(".json", f".{n}.json")
        n += 1
    p.rename(dst)
    return dst


def write_union_stamp(corpus_dir, stratum: str, provenance: dict) -> Path:
    """Merge one stratum's provenance into `RUN/corpus/CORPUS_UNION.json`.

    ONE file for the whole corpus, keyed by stratum (R4-0.5 §3): the union is a
    property of the corpus, not of a directory, and a reader asking "what is `n`
    made of" must not have to find and join two files. Read-modify-write so the
    S1 and S2 assemblies — separate invocations — accumulate rather than
    overwrite.

    ⚠️ A stamp WITHOUT a leg-layer witness on every stratum is a pre-fix stamp
    and is PRESERVED BY RENAME (`CORPUS_UNION.r4.5-defective.json`) before the
    reissue is written. Its blocks are carried forward — marked
    `leg_layer.witnessed = false` — so a stratum that is not being reassembled
    (S2 stays VOID under D4.5 and must NOT be assembled) neither disappears nor
    silently inherits a witness it never had.
    """
    p = Path(corpus_dir) / UNION_STAMP
    doc, superseded = {}, None
    if p.is_file():
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError:
            doc = {}
        if not _leg_layer_witnessed(doc):
            superseded = preserve_defective_stamp(p)
            for s, v in (doc.get("by_stratum") or {}).items():
                if isinstance(v, dict) and "leg_layer" not in v:
                    v["leg_layer"] = {
                        "witnessed": False,
                        "note": "assembled BEFORE the D4.3 cross-layer invariant "
                                "existed — this stratum's leg files were never "
                                "asserted to enumerate the ARMS.json rid set. "
                                "Carried forward unchanged; not re-witnessed.",
                    }
    doc["schema"] = UNION_SCHEMA
    doc.setdefault("rev", "R4.5")
    if superseded is not None:
        doc["superseded_file"] = {
            "path": str(superseded),
            "why": "reissued under D4.7 with a LEG-LAYER witness. The previous "
                   "stamp asserted the copy at the ARMS layer for an assembly "
                   "that did not happen at the leg layer; it is preserved "
                   "because the false assertion is evidence of the defect.",
        }
    doc.setdefault(
        "what", "the composition of the corpus of record: RETAINED band-135e9 "
                "positions (read read-only out of the SPENT R3.3 run and COPIED "
                "in) plus FRESHLY generated 137e9 extension positions. R4's `n` "
                "is a MIXTURE and this is where its composition is stated.")
    doc.setdefault("by_stratum", {})
    doc["by_stratum"][str(stratum).upper()] = provenance
    tot_r = sum(v.get("n_retained", 0) for v in doc["by_stratum"].values())
    tot_f = sum(v.get("n_fresh", 0) for v in doc["by_stratum"].values())
    doc["totals"] = {
        "n_retained": tot_r, "n_fresh": tot_f, "n_total": tot_r + tot_f,
        "retained_fraction": (tot_r / (tot_r + tot_f)) if (tot_r + tot_f) else None,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2, sort_keys=True))
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--banked", required=True,
                    help="the RETAINED 135e9 positions dir (READ-ONLY)")
    ap.add_argument("--extension", required=True,
                    help="the fresh 137e9 extension positions dir")
    ap.add_argument("--out", required=True, help="the UNION dir (corpus of record)")
    ap.add_argument("--exclude-rids", action="append", default=None)
    ap.add_argument("--stratum", default="s1")
    a = ap.parse_args(argv)
    try:
        prov = assemble(a.banked, a.extension, a.out,
                        exclude_rids=load_rid_exclusions(a.exclude_rids),
                        stratum=a.stratum)
    except UnionError as exc:
        print(f"\n{'=' * 70}\n[union] COULD NOT ASSEMBLE: {exc}\n{'=' * 70}",
              file=sys.stderr)
        return 2
    print(f"[union] {a.stratum}: banked {prov['banked_kept']}/{prov['banked_in']} "
          f"+ extension {prov['extension_kept']}/{prov['extension_in']} "
          f"= {prov['banked_kept'] + prov['extension_kept']} "
          f"({prov['banked_excluded'] + prov['extension_excluded']} excluded) "
          f"-> {a.out}")
    leg = prov["leg_layer"]
    print(f"[union] {a.stratum}: LEG LAYER {leg['n_leg_files']} file(s), "
          f"{leg['n_rids_in_leg_files']} rid(s) vs ARMS {leg['n_rids_in_arms']} "
          f"— set equality BOTH directions: OK "
          f"(lines: banked {leg['n_lines_by_side']['banked']}, extension "
          f"{leg['n_lines_by_side']['extension']})")
    for k, v in sorted(leg["files"].items()):
        print(f"[union]   {k}: {v['n_rids']} rid(s) / {v['n_lines']} line(s) "
              f"sha256 {v['sha256'][:12]}… -> {v['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
