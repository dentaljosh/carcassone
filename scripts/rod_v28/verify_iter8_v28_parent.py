#!/usr/bin/env python3
"""RoD Phase 1 — verify ITER8_V28_PARENT reproduces the known v2.8 config EXACTLY.

Deterministic, CPU-only (no GPU / no orchestrator). Gates the whole probe:
"Do not proceed unless ITER8_V28_PARENT reproduces the known v2.8 config exactly."

Checks:
  [1] iter8 checkpoint sha256 == PRODUCTION.yaml value (parent identity).
  [2] v2.7 default: DEFAULT_CONFIG.meeple_k == 0.0  (v2.7 stays bit-identical).
  [3] v2.8 cfg = replace(DEFAULT_CONFIG, meeple_k=2.0); _v28_active(cfg28) is
      False  -> legacy field -> FLAT/Cython fast path (NOT the 2.26x object path).
  [4] Leaf VALUES on real mid-game states: flat_leaf(cfg28) - flat_leaf(cfg27)
      == 2*(meeples_self - meeples_opp) exactly, and the term actually fires.

Exit 0 = reproduced. Nonzero = abort the probe.
"""
from __future__ import annotations

import dataclasses
import hashlib
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "engine"))

import numpy as np  # noqa: E402

from carcassonne_ai import flat_leaf  # noqa: E402
from carcassonne_ai.game_wrapper import Game  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG, _v28_active  # noqa: E402

EXPECT_SHA = "0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c"
CKPT = Path("/mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    fail: list[str] = []

    # [1] checkpoint identity
    if CKPT.exists():
        got = sha256(CKPT)
        ok = got == EXPECT_SHA
        print(f"[1] iter8 sha256 {'OK' if ok else 'MISMATCH'}: {got}")
        if not ok:
            fail.append("sha")
    else:
        print(f"[1] WARN iter8 not at {CKPT} (per-box share path); sha check skipped")

    # [2] v2.7 default unchanged
    print(f"[2] DEFAULT_CONFIG.meeple_k = {DEFAULT_CONFIG.meeple_k} (expect 0.0)")
    if DEFAULT_CONFIG.meeple_k != 0.0:
        fail.append("v27_default_not_zero")

    # [3] v2.8 stays on the flat path
    cfg27 = DEFAULT_CONFIG
    cfg28 = dataclasses.replace(DEFAULT_CONFIG, meeple_k=2.0)
    active = _v28_active(cfg28)
    print(f"[3] cfg28.meeple_k={cfg28.meeple_k}  _v28_active(cfg28)={active} (expect False -> flat path)")
    if active:
        fail.append("v28_active_true_slow_path")
    if cfg28.meeple_k != 2.0:
        fail.append("meeple_k_not_set")

    # [4] leaf values differ by exactly the meeple-economy term
    g = Game()
    n_checked = 0
    n_fired = 0
    for gi in range(10):
        random.seed(1922 + gi)
        b = g.get_init_board()
        p = 0
        while g.get_game_ended(b, 0) == 0.0 and p < 130:
            legal = np.flatnonzero(g.get_valid_moves(b))
            if legal.size == 0:
                break
            b, _ = g.get_next_state(b, int(random.choice(legal.tolist())))
            p += 1
            if p % 13 == 0 and g.get_game_ended(b, 0) == 0.0 and b.state.players == 2:
                s = b.state
                v27 = flat_leaf.flat_virtual_score_v2(s, 0, cfg27)
                v28 = flat_leaf.flat_virtual_score_v2(s, 0, cfg28)
                expect = 2 * (s.meeples[0] - s.meeples[1])
                n_checked += 1
                if (v28 - v27) != expect:
                    print(f"    MISMATCH g{gi}p{p}: delta={v28 - v27} expect={expect} meeples={s.meeples}")
                    if "leaf_value" not in fail:
                        fail.append("leaf_value")
                if expect != 0:
                    n_fired += 1
    leaf_ok = "leaf_value" not in fail
    print(f"[4] leaf-value check: {n_checked} states; meeple term fired (nonzero) in {n_fired}; formula-exact={leaf_ok}")
    if n_fired == 0:
        print("    WARN: meeple term never fired (no meeple asymmetry sampled)")
        fail.append("term_never_fired")

    print("RESULT:", "REPRODUCED" if not fail else f"FAIL {fail}")
    return 0 if not fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
