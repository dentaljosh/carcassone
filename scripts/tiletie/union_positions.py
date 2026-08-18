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


def assemble(banked_dir, ext_dir, out_dir, *, exclude_rids=(), stratum="s1",
             leg_glob="positions_*_leg1.jsonl") -> dict:
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
        sides[tag] = {"dir": d, "arms": json.loads(a.read_text())}
    if not any(sides.values()):
        raise UnionError(f"neither side exists: {banked} / {ext}")

    merged, dropped_rows, kept_lines = {}, [], []
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
        for leg in sorted(side["dir"].glob(leg_glob)):
            for line in leg.read_text().splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("rid") in excl:
                    continue
                kept_lines.append(json.dumps(rec))

    out.mkdir(parents=True, exist_ok=True)
    (out / ARMS).write_text(json.dumps(merged, indent=2, sort_keys=True))
    (out / DROPPED).write_text(json.dumps({"rows": dropped_rows}, indent=2,
                                          sort_keys=True))
    (out / f"positions_walled_leg1.jsonl").write_text(
        "".join(x + "\n" for x in kept_lines))

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
        "union_provenance": provenance,
    })
    if "exclude_rids" in template and isinstance(template["exclude_rids"], dict):
        template["exclude_rids"] = dict(template["exclude_rids"],
                                        n_requested=len(excl),
                                        n_supply_after_exclusion=len(merged))
    (out / PLAN).write_text(json.dumps(template, indent=2, sort_keys=True))
    write_union_stamp(out.parent, stratum, provenance)
    return provenance


def write_union_stamp(corpus_dir, stratum: str, provenance: dict) -> Path:
    """Merge one stratum's provenance into `RUN/corpus/CORPUS_UNION.json`.

    ONE file for the whole corpus, keyed by stratum (R4-0.5 §3): the union is a
    property of the corpus, not of a directory, and a reader asking "what is `n`
    made of" must not have to find and join two files. Read-modify-write so the
    S1 and S2 assemblies — separate invocations — accumulate rather than
    overwrite."""
    p = Path(corpus_dir) / UNION_STAMP
    doc = {}
    if p.is_file():
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError:
            doc = {}
    doc.setdefault("schema", "carcassonne-tiearb-widening-corpus-union/v1")
    doc.setdefault("rev", "R4.5")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
