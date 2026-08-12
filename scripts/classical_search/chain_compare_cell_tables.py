#!/usr/bin/env python3
"""Compare the per-box capability cell tables and prove the comparison was MEANINGFUL.

WHY THIS EXISTS (2026-08-12 post-mortem of the BLOCKED_D1 false positive)
------------------------------------------------------------------------
The night chain probes the targeted-denial capability on BOTH boxes and refuses to launch
unless they resolve the SAME candidate leaf hashes. Two boxes computing different candidate
leaves would write games into ONE cell directory, and those games are indistinguishable at
read time — a silently contaminated cell, which is the worst failure mode of the night.

The original gate was `diff -q $SHARE/d1_cells.tsv $LSHARE/d1_cells.tsv`, run on the LOCAL
box. It was broken in two independent ways, and both are guarded here:

  1. FALSE BLOCK. `$LSHARE` (/mnt/carc-shared) is the LAPTOP's mount prefix. On the local
     box that path is an empty stub directory, so `diff` exited 2 ("No such file"), the
     `2>&1` swallowed the reason, and the chain reported "candidate leaf hashes disagree"
     about a file it had never read. The gate could never pass.

  2. VACUOUS PASS (the dangerous half). `$SHARE/x` and `$LSHARE/x` are the SAME physical
     file on one CIFS store. Both probes wrote that one path, the laptop's write simply
     overwrote the local box's, and a fixed-prefix `diff` would then have compared the file
     to ITSELF — passing unconditionally, including when the boxes genuinely disagreed.

So: each box now writes a box-distinct BASENAME (d1_cells.local.tsv / d1_cells.laptop.tsv),
both are addressed with the LOCAL prefix at compare time, and this script refuses to return
"agree" unless it can show the two paths were different files that were both actually read.

Comparison is on PARSED ROWS, not bytes: CRLF and a missing trailing newline must not fake
a contamination block, while any difference in tag / candidate JSON / candidate leaf hash
always blocks. That makes the gate strictly harder to pass than a byte diff on the axis
that matters and strictly less flaky on the axis that does not.

Exit codes (each is a DISTINCT operator story; the chain prints them verbatim):
  0  tables agree AND the comparison was meaningful
  3  the remote table is missing or empty  -> the remote probe never ran / never persisted
  4  the two paths are the SAME physical file -> the gate would be vacuous, refuse
  5  the tables DIFFER -> the two boxes are not computing the same candidate leaf
  6  the local table is missing, empty or malformed
  7  the remote table is malformed
  8  the remote table is STALE (older than --newer-than) -> left over from an earlier run
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RC_OK = 0
RC_REMOTE_MISSING = 3
RC_SAME_FILE = 4
RC_DIFFER = 5
RC_LOCAL_BAD = 6
RC_REMOTE_BAD = 7
RC_REMOTE_STALE = 8

Row = tuple[str, str, str]


def parse_table(text: str) -> list[Row]:
    """tag<TAB>cand_leaf_json<TAB>cand_leaf_hash, one cell per line.

    Tolerates CRLF and a missing/extra trailing newline (transport noise across a CIFS
    share written by two different OSes). Raises ValueError on anything else — a table we
    cannot parse must never be silently treated as agreement.
    """
    rows: list[Row] = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ValueError(f"line {n}: expected 3 tab-separated fields, got {len(parts)}: {line!r}")
        tag, spec, chash = (p.strip() for p in parts)
        if not tag or not spec or not chash:
            raise ValueError(f"line {n}: empty field in {line!r}")
        rows.append((tag, spec, chash))
    if not rows:
        raise ValueError("no cell rows")
    return rows


def _fmt(rows: list[Row]) -> str:
    return "; ".join(f"{t}={h}" for t, _, h in rows)


def describe_difference(local: list[Row], remote: list[Row], remote_label: str) -> str:
    """Name the exact disagreement, so the operator never has to re-derive it by hand."""
    lmap = {t: (s, h) for t, s, h in local}
    rmap = {t: (s, h) for t, s, h in remote}
    bits: list[str] = []
    for tag in sorted(set(lmap) - set(rmap)):
        bits.append(f"cell {tag} present locally, ABSENT on {remote_label}")
    for tag in sorted(set(rmap) - set(lmap)):
        bits.append(f"cell {tag} present on {remote_label}, ABSENT locally")
    for tag in sorted(set(lmap) & set(rmap)):
        ls, lh = lmap[tag]
        rs, rh = rmap[tag]
        if lh != rh:
            bits.append(f"cell {tag}: local cand_leaf_hash {lh} != {remote_label} {rh}")
        elif ls != rs:
            bits.append(f"cell {tag}: same hash but different cand_leaf_json "
                        f"(local {ls} != {remote_label} {rs})")
    return " | ".join(bits) or "row ORDER differs between the boxes"


def compare_cell_tables(local_path: str | os.PathLike,
                        remote_path: str | os.PathLike,
                        remote_label: str = "laptop",
                        newer_than: float | None = None) -> tuple[int, str]:
    """Return (exit_code, human message). Pure — no side effects, so it is unit-testable."""
    lp, rp = Path(local_path), Path(remote_path)

    if not lp.is_file() or lp.stat().st_size == 0:
        return RC_LOCAL_BAD, (f"the LOCAL capability cell table {lp} is missing or empty - the "
                              f"local probe did not persist its cells")
    if not rp.is_file() or rp.stat().st_size == 0:
        return RC_REMOTE_MISSING, (
            f"the {remote_label.upper()} capability cell table is MISSING or EMPTY at {rp}. The "
            f"remote probe either never ran, or ran and failed to persist its cells. An absent "
            f"remote table is NOT a pass: without it the two-box agreement gate has no second "
            f"opinion, and an unverified box plays a large share of every cell.")

    # The gate is only meaningful if the two paths are genuinely two files. $SHARE/x and
    # $LSHARE/x are ONE file on the CIFS store; comparing that to itself always 'agrees'.
    ls, rs = lp.stat(), rp.stat()
    if (ls.st_dev, ls.st_ino) == (rs.st_dev, rs.st_ino):
        return RC_SAME_FILE, (
            f"the local and {remote_label} cell tables are the SAME PHYSICAL FILE "
            f"(dev={ls.st_dev} ino={ls.st_ino}): {lp} and {rp}. The two boxes must write "
            f"box-DISTINCT basenames on the share, or this gate compares a file to itself and "
            f"passes unconditionally - including when the boxes genuinely disagree. Refusing to "
            f"report agreement from a vacuous comparison.")

    if newer_than is not None and rs.st_mtime < newer_than:
        return RC_REMOTE_STALE, (
            f"the {remote_label} cell table {rp} is STALE (mtime {rs.st_mtime:.0f} < required "
            f"{newer_than:.0f}) - it is left over from an EARLIER run, not evidence from this "
            f"one. Treating a stale table as this run's second opinion would re-introduce the "
            f"vacuous pass.")

    try:
        lrows = parse_table(lp.read_text())
    except ValueError as e:
        return RC_LOCAL_BAD, f"the LOCAL cell table {lp} is malformed: {e}"
    try:
        rrows = parse_table(rp.read_text())
    except ValueError as e:
        return RC_REMOTE_BAD, f"the {remote_label.upper()} cell table {rp} is malformed: {e}"

    if lrows != rrows:
        return RC_DIFFER, (
            f"the local and {remote_label} capability probes produced DIFFERENT cell tables. The "
            f"two boxes are not computing the same candidate leaf; a mixed-rev cell is "
            f"contamination, not a slow cell. {describe_difference(lrows, rrows, remote_label)}. "
            f"local: {lp} | {remote_label}: {rp}")

    return RC_OK, (f"{len(lrows)} cell(s) agree on both boxes from two distinct files "
                   f"[{_fmt(lrows)}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--local", required=True, help="cell table written by the LOCAL probe")
    ap.add_argument("--remote", required=True,
                    help="cell table written by the REMOTE probe, addressed with the LOCAL "
                         "mount prefix (this process reads it from the local box)")
    ap.add_argument("--remote-label", default="laptop")
    ap.add_argument("--newer-than", type=float, default=None,
                    help="epoch seconds; the remote table must be at least this fresh")
    a = ap.parse_args()

    rc, msg = compare_cell_tables(a.local, a.remote, a.remote_label, a.newer_than)
    if rc == RC_OK:
        print(f"[cells-gate] PASS: {msg}")
    else:
        print(f"[cells-gate] FAIL(rc={rc}): {msg}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
