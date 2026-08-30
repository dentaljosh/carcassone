# invasion_screen_r2_prep — execution-layer deviations (post-launch)

**NONE YET.** No cell has run.

This file exists at freeze so that a deviation has somewhere to be recorded the moment it happens,
rather than being written into the pair after the fact. The house class distinction, from round 1's
`IS-D1` and the `everyply` `EP-D1..D5` precedent:

- **EXECUTION-LAYER / STATISTICS-BLIND** deviations — a misaddressed reader, a launcher-side typo, a
  path fix — are recorded HERE, with root cause, ground truth verified BEFORE the fix, the fix
  itself, and why the smoke could not catch it. They do **not** touch a bar, a gate of record, or a
  branch condition.
- **ANYTHING THAT WOULD MOVE A BAR OR A BRANCH** is not a deviation. Before game 1 it is a
  **pre-game-1 amendment** to the pair, made in the open with the band unspent. After game 1 it is
  not available at all: the pair is law and `READ_RULE.md`'s banner says nothing in it moves after
  the blind commit.

## What round 1 learned that this round should not have to re-learn

**`IS-D1` (2026-08-26)** — round 1's launcher-side ident-precheck read the `config` block off
`summary.json`, which carries **no config block at all** (the split is: config-shaped addresses →
`manifest.json`; statistics → `summary.json`). `cfg` came back `{}`, so `cand_leaf_hash` came back
`None`, and the precheck fail-closed **voided a healthy cell** — while the same empty dict made a
second conjunct (`leaf_diff_empty`) pass **vacuously** (`{} == {}`), hiding the cause. It cost the
round a stop at ~8 core-h.

**Carried into round 2, both halves:**

1. The per-cell pre-check reads `manifest.json` for config and `summary.json` for `n_failed`
   ([`DESIGN.md`](DESIGN.md) §6.4).
2. ⭐ **The vacuity is now structurally impossible**: `screen_lib.leaf_gate()` requires both hashes
   to be present **strings** equal to their pins, not merely equal to each other. An empty config
   fails it loudly instead of passing half of it quietly.

**And round 1's instrument-hardening note, which round 2 acted on:** *"any launcher-side gate that
runs only once per round needs its own selftest fixture."* Round 2's pre-check runs after **every**
cell rather than once, and its arithmetic is `screen_lib`'s — the same `leaf_gate()` the adjudicator
calls — so it is exercised by the instrument suite rather than first executed in anger.

## A note on the two-box directive, so the ceremony is legible

The owner's "get round 2 on both local and laptop" arrived **while the pair was still being
built — before any blind commit existed and with zero games run.** It is therefore folded into the
freeze itself and is **NOT an amendment**: there was no frozen pair to amend. `DESIGN.md` §6.5,
`READ_RULE.md`'s `G-HOST` row, the launcher's `--host` role and the nineteenth gate were all
written before the blind commit, like every other line of the pair.

Recorded here only so a reader who knows the directive came later does not go looking for an
amendment banner that would have been dishonest to write.

## A round-2 finding, recorded here because it is the same class

⭐ **`carc_rs_build` IS NOT A WHEEL FINGERPRINT.** Found at freeze, by `--selftest` failing against
round 1's own emitted archive. It is documented in full in [`DESIGN.md`](DESIGN.md) §3.1a and
`screen_lib.py`'s `R1_WHEEL_BINARY_SHA` banner, and it moved a brand-new gate **before** it could
void a healthy round. It is **not** a deviation — nothing had launched and no bar existed to move —
but it belongs in the same lineage of lessons: **point a new gate at real emitted output before you
trust it**, and let the archive win.

## Bar-library import hardened to round 3's by-path form (2026-08-29, statistics-blind)

Same class as round 1's `IS-D2`, applied to **both** of this round's adjudicators
(`analyze_screen.py` and `analyze_screen_amended.py`). Both loaded the bar library as a bare
`import screen_lib` off a `sys.path` insertion; rounds 1/2/3 each ship a different
`screen_lib.py` (sha256 `6168b325…` / `0824a3e2…` / `47c01830…`), so in a process holding two
rounds the first loaded won `sys.modules["screen_lib"]` and the second adjudicator read the
**wrong round's bars**. Round 3 shipped with the fix; this round did not.

Now loaded **by path** under `screen_lib__invasion_screen_r2_prep`, registered in `sys.modules`
before `exec_module`. The two files in this directory deliberately share one module instance —
that is the same `screen_lib.py` either way, which is the intended collision-free behaviour.

**Statistics-blind:** the identical bar library is loaded from the identical path; only the
module name changes. No bar, gate, threshold, branch table, statistic or verdict of round 2
moves, and the round's verdict of record stands unaltered.

**Verification:** `--selftest` GREEN on both files (0 sanity problems, all 19 gate ids
evaluated, ABSENT-is-FAIL holds). The three instrument suites run **together** went from 50
failures to 4, and those 4 are precisely the failures each suite already produces standalone
(the `BAND_CLAIMED` freeze-time interlocks, now tripping because the bands have since been
claimed, plus this round's pre-existing wheel-preflight failure) — none of them in the code
this edit touched.
