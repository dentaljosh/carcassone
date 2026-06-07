"""Generate the machine-readable SEMANTIC_TEST_REPORT for the clean-eval ruler.

Runs the semantic-contract + provenance test suites under pytest's built-in
`--junitxml` (zero new dependency, offline-safe for the no-DNS cluster), parses
the JUnit XML with the stdlib, and emits:

  clean_eval/SEMANTIC_TEST_REPORT.md     human table (contract -> pass/fail/skip)
  clean_eval/semantic_test_report.json   machine-readable verdict per test

Exit code mirrors the pytest run (0 iff every collected test passed/skipped).

Usage:
  python scripts/gen_semantic_test_report.py
  python scripts/gen_semantic_test_report.py --tests tests/test_semantic_eval_contracts.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "clean_eval"
DEFAULT_TESTS = ["tests/test_semantic_eval_contracts.py", "tests/test_eval_provenance.py"]

# human-readable contract titles, keyed by the cNN prefix in the test name.
CONTRACT_TITLES = {
    "c1": "Higher final score → positive value for that player",
    "c2": "Value antisymmetry AND winner-sign mapping (independent)",
    "c3": "Tied-feature scoring pays all tied owners full",
    "c4": "Farm scoring matches deduped reference",
    "c5": "tile→meeple transition keeps the acting player",
    "c6": "meeple→tile transition advances the acting player",
    "c7": "FPU stored + reorders search (perspective penalty)",
    "c8": "Equivalent-action aliases + visit-mass de-dup (C2)",
    "c9": "visit → replay .npz → streaming trainer-load round trip",
    "c10": "Legal mask shape + policy-index alignment",
    "c11": "Real checkpoint: v2.7 residual leaf actually executes",
}


def _run_pytest(tests, junit_path: Path) -> int:
    cmd = [sys.executable, "-m", "pytest", *tests, "-q",
           f"--junitxml={junit_path}"]
    print("running:", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(REPO)).returncode


def _parse_junit(junit_path: Path) -> list[dict]:
    root = ET.parse(junit_path).getroot()
    # junitxml root may be <testsuites> or a single <testsuite>
    suites = root.findall("testsuite") or [root]
    cases = []
    for suite in suites:
        for tc in suite.findall("testcase"):
            name = tc.get("name", "")
            status, message = "passed", ""
            for tag in ("failure", "error"):
                el = tc.find(tag)
                if el is not None:
                    status = "failed" if tag == "failure" else "error"
                    message = (el.get("message") or el.text or "").strip().splitlines()[0:1]
                    message = message[0] if message else ""
                    break
            if tc.find("skipped") is not None:
                status = "skipped"
                sk = tc.find("skipped")
                message = (sk.get("message") or "").strip()
            m = re.match(r"(test_)?(c\d+)_", name)
            contract = m.group(2) if m else ""
            cases.append({
                "test": name,
                "classname": tc.get("classname", ""),
                "contract": contract,
                "title": CONTRACT_TITLES.get(contract, ""),
                "status": status,
                "time_s": float(tc.get("time", 0.0) or 0.0),
                "message": message,
            })
    return cases


def _write_reports(cases: list[dict], rc: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n = len(cases)
    passed = sum(c["status"] == "passed" for c in cases)
    skipped = sum(c["status"] == "skipped" for c in cases)
    failed = sum(c["status"] in ("failed", "error") for c in cases)
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip() or "unknown"

    summary = {"total": n, "passed": passed, "skipped": skipped, "failed": failed,
               "pytest_returncode": rc, "code_rev": commit, "all_green": failed == 0}
    (OUT / "semantic_test_report.json").write_text(
        json.dumps({"summary": summary, "cases": cases}, indent=2))

    icon = {"passed": "✅", "skipped": "⚪", "failed": "❌", "error": "❌"}
    lines = [
        "# SEMANTIC_TEST_REPORT — evaluation-ruler contracts",
        "",
        f"Generated at code_rev `{commit}`. "
        f"**{passed}/{n} passed**, {skipped} skipped, {failed} failed "
        f"(pytest rc={rc}).",
        "",
        "These deterministic contracts pin the *meaning* of the eval pipeline's",
        "numbers (value sign, tie/farm scoring, phase/turn transitions, FPU,",
        "transposition de-dup, the visit→replay→trainer round trip, mask/index",
        "alignment, and a real-checkpoint proof the v2.7 leaf executes).",
        "",
        "| Contract | Test | Status | Time (s) | Note |",
        "|---|---|---|---|---|",
    ]
    for c in sorted(cases, key=lambda c: (c["contract"] or "zz", c["test"])):
        label = f"{c['contract']} — {c['title']}" if c["title"] else (c["contract"] or "—")
        note = c["message"][:80] if c["message"] else ""
        lines.append(f"| {label} | `{c['test']}` | {icon.get(c['status'], c['status'])} "
                     f"{c['status']} | {c['time_s']:.2f} | {note} |")
    lines.append("")
    lines.append(f"_Source suites: {', '.join(DEFAULT_TESTS)}_")
    (OUT / "SEMANTIC_TEST_REPORT.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT/'SEMANTIC_TEST_REPORT.md'} and {OUT/'semantic_test_report.json'} "
          f"({passed}/{n} passed)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gen_semantic_test_report")
    ap.add_argument("--tests", nargs="*", default=DEFAULT_TESTS)
    ap.add_argument("--junit", type=Path, default=OUT / "semantic_junit.xml")
    args = ap.parse_args(argv)
    args.junit.parent.mkdir(parents=True, exist_ok=True)
    rc = _run_pytest(args.tests, args.junit)
    if not args.junit.is_file():
        print(f"ERROR: junit xml not produced at {args.junit}")
        return rc or 1
    cases = _parse_junit(args.junit)
    _write_reports(cases, rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
