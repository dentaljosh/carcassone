#!/usr/bin/env python3
"""Doc staleness/coherence linter (born from the 2026-06-12 three-agent doc review).

Catches the mechanically-checkable signatures of doc rot that review found:

  ERRORS (always wrong, block-worthy):
    E1  broken relative markdown link (target doesn't exist)
    E2  tracked doc links to an UNTRACKED file (link breaks on every clone /
        bundle-synced remote — the COMPACT_LEAF_REWRITE_PLAN bug)

  WARNINGS (judgment calls, surface but don't block):
    W1  dated plan/spec doc (docs/NAME_20YY-MM-DD.md) with no status banner in
        its header (the "as-built appended, never closed out" pattern)
    W2  live-state marker ("running right now", "not launched", "RESULT — PENDING",
        "topup running", "in flight", "ETA ~") in a docs/ file whose last git
        commit is older than --stale-days (default 3)
    W3  dead numbered-backlog pointer ("BACKLOG #322" — BACKLOG has no numbers)
    W4  "running"/"pending" text inside governance CSVs (registry rows should be
        closed out when the thing finishes — the CL-005 lag)

Usage:
  python scripts/doc_lint.py                # whole repo
  python scripts/doc_lint.py --staged       # only files staged for commit
  python scripts/doc_lint.py --errors-only  # report/exit on errors alone (hook mode)

Exit codes: 2 = errors found, 1 = warnings found (suppressed by --errors-only), 0 = clean.
Read-only; safe anywhere.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
STALE_MARKERS = re.compile(
    r"(running right now|\bnot launched\b|NOT yet run|RESULT\s*[—-]\s*PENDING"
    r"|topup running|\bin flight\b|\bETA ~)",
    re.IGNORECASE,
)
DEAD_BACKLOG_RE = re.compile(r"BACKLOG\s+#\d+")
DATED_SPEC_RE = re.compile(r"_20\d\d-\d\d-\d\d\.md$")
STATUS_BANNER_RE = re.compile(
    r"(\*\*Status|SUPERSEDED|COMPLETE|HISTORICAL|EXECUTED|DEPLOYED|VERDICT|"
    r"AS-BUILT|ON HOLD|DESIGN ONLY|OUTCOME|✅|⚠️)",
    re.IGNORECASE,
)
GOV_LIVE_RE = re.compile(r"\b(running|pending)\b", re.IGNORECASE)


def _git(args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception:
        return ""


def _tracked() -> set[str]:
    return set(_git(["ls-files"]).splitlines())


def _last_commit_age_days(relpath: str) -> float | None:
    out = _git(["log", "-1", "--format=%ct", "--", relpath]).strip()
    if not out.isdigit():
        return None
    return (time.time() - int(out)) / 86400.0


def _resolve_link(srcfile: Path, target: str) -> Path | None:
    """Return the existing Path a relative link points at, else None."""
    t = target.split("#", 1)[0]
    if not t or t.startswith(("http://", "https://", "mailto:")):
        return Path("/")  # external — not ours to check; sentinel "fine"
    for base in (srcfile.parent, ROOT):
        p = (base / t).resolve()
        if p.exists():
            return p
    return None


def lint(files: list[Path], stale_days: float) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    tracked = _tracked()

    for f in files:
        rel = str(f.relative_to(ROOT))
        try:
            text = f.read_text(errors="replace")
        except Exception:
            continue

        if f.suffix == ".md":
            # E1/E2 — links
            for m in LINK_RE.finditer(text):
                target = m.group(1)
                resolved = _resolve_link(f, target)
                if resolved is None:
                    errors.append(f"E1 {rel}: broken link -> {target}")
                elif resolved != Path("/") and rel in tracked:
                    rt = str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else None
                    if rt and rt not in tracked and not rt.startswith((".claude/",)):
                        errors.append(
                            f"E2 {rel}: links to UNTRACKED file {rt} "
                            f"(breaks on clones/remotes — git add it or fix the link)")

            # W3 — dead numbered backlog pointers
            for m in DEAD_BACKLOG_RE.finditer(text):
                warnings.append(f"W3 {rel}: dead pointer '{m.group(0)}' (BACKLOG has no numbered entries)")

            in_docs = rel.startswith("docs/") and "/research/" not in rel
            if in_docs and DATED_SPEC_RE.search(f.name):
                head = "\n".join(text.splitlines()[:14])
                if not STATUS_BANNER_RE.search(head):
                    warnings.append(
                        f"W1 {rel}: dated spec/plan doc with no status banner in its "
                        f"header — stamp it (DRAFT/RUNNING/COMPLETE/SUPERSEDED/HISTORICAL)")

            # W2 — live-state markers in old docs/ files (STATUS.md is at root => exempt)
            if in_docs:
                hits = sorted({h if isinstance(h, str) else h[0]
                               for h in STALE_MARKERS.findall(text)})
                if hits:
                    age = _last_commit_age_days(rel)
                    if age is not None and age > stale_days:
                        warnings.append(
                            f"W2 {rel}: live-state marker(s) {hits} but last commit "
                            f"{age:.0f}d ago — finished? stamp the outcome")

        elif rel.startswith("governance/") and f.suffix == ".csv":
            for i, line in enumerate(text.splitlines(), 1):
                if GOV_LIVE_RE.search(line):
                    # only flag obvious live-state phrasings, not e.g. "long-running"
                    if re.search(r"(topup running|still running|\brunning\b(?! mean)|PENDING)", line, re.I):
                        warnings.append(
                            f"W4 {rel}:{i}: row text says running/pending — if the thing "
                            f"finished, close the row out")
    return errors, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--staged", action="store_true", help="only lint files staged for commit")
    ap.add_argument("--errors-only", action="store_true", help="hook mode: only errors matter")
    ap.add_argument("--stale-days", type=float, default=3.0)
    args = ap.parse_args()

    if args.staged:
        names = _git(["diff", "--cached", "--name-only"]).splitlines()
        files = [ROOT / n for n in names
                 if (ROOT / n).exists() and (n.endswith(".md") or n.endswith(".csv"))]
    else:
        files = [ROOT / n for n in _tracked()
                 if n.endswith(".md") or (n.startswith("governance/") and n.endswith(".csv"))]
        # outside_review/ is a frozen artifact snapshot — its internal links are
        # expected to be broken at that location; never lint it.
        files = [f for f in files if f.exists() and "engine/" not in str(f)
                 and "outside_review/" not in str(f)]

    errors, warnings = lint(files, args.stale_days)

    for e in errors:
        print(e)
    if not args.errors_only:
        for w in warnings:
            print(w)
    n_w = 0 if args.errors_only else len(warnings)
    if errors or n_w:
        print(f"\ndoc_lint: {len(errors)} error(s), {n_w} warning(s)")
    if errors:
        return 2
    if n_w:
        return 1
    print("doc_lint: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
