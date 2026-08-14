"""Per-box post-rebuild verification for the F-c fail-loud action-window change.

Read-only. Prints, in order:
  * the git HEAD of the tree it was imported from
  * the rustc version baked into the LOADED carc_rs .so
  * whether carc_rs exposes WindowTruncationError, and that it subclasses RuntimeError
  * the three champion leaf fingerprints, recomputed through the RUST backend

Exit 0 only if every check passes. Intended to be run identically on every box that
plays, per the standing per-box build gate (docs/CLUSTER_OPS.md).
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys

EXPECTED_RUSTC = "1.96.0"
EXPECTED = {
    "harness_leaf_hash": "a36d2e15a3b3d71d",
    "frozen_config_hash_meeple_k2": "158f17ff76adaa02",
    "frozen_config_hash_meeple_k0": "6dfffd57051690f2",
}

ok = True


def check(label: str, passed: bool, detail: str = "") -> None:
    global ok
    ok = ok and passed
    print(f"[{'PASS' if passed else 'FAIL'}] {label}" + (f": {detail}" if detail else ""))


repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
print(f"repo      : {repo}")
print(f"git HEAD  : {head}")

# ⚠️ BEFORE any carcassonne_ai import: freezes the PRODUCTION leaf SHAPE, else
# verify_leaf raises bonus_cap=5.0 != 8.0 (see scripts/rustport/prod_leaf_env.py).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prod_leaf_env  # noqa: E402,F401

import carc_rs  # noqa: E402

so = glob.glob(os.path.join(os.path.dirname(carc_rs.__file__), "*.so"))[0]
print(f"carc_rs   : {so}")

# 1. rustc version read off the SHIPPED .so, not off the shell we think built it.
strs = subprocess.run(["strings", "-a", so], capture_output=True, text=True).stdout
vers = sorted({ln.split("rustc version ")[1].split()[0]
               for ln in strs.splitlines() if "rustc version " in ln})
check("rustc version in wheel", vers == [EXPECTED_RUSTC], f"{vers} (want ['{EXPECTED_RUSTC}'])")

# 2. the wheel actually carries the F-c change.
has = hasattr(carc_rs, "WindowTruncationError")
check("carc_rs.WindowTruncationError present", has, str(has))
if has:
    exc = carc_rs.WindowTruncationError
    check("WindowTruncationError subclasses RuntimeError",
          issubclass(exc, RuntimeError), f"mro={[c.__name__ for c in exc.__mro__[:4]]}")

# 3. champion fingerprints, recomputed by the backend that will PLAY.
sys.path.insert(0, os.path.join(repo, "src"))
from carcassonne_ai import champion_factory as cf  # noqa: E402

prov = cf.verify_leaf(cf.production_leaf_cfg(), backend="rust")
for key, want in EXPECTED.items():
    got = prov["hashes"][key]
    check(f"fingerprint {key}", got == want, f"{got}" + ("" if got == want else f" != {want}"))

print("RESULT: " + ("ALL PASS" if ok else "FAILURES ABOVE"))
sys.exit(0 if ok else 1)
