# invasion_screen_r3_prep — execution-layer deviations (post-launch)

**NONE YET.** No cell has run.

This file exists at freeze so that a deviation has somewhere to be recorded the moment it happens,
rather than being written into the pair after the fact. The house class distinction, from round 1's
`IS-D1` and the `everyply` `EP-D1..D5` precedent:

- **EXECUTION-LAYER / STATISTICS-BLIND** deviations — a misaddressed reader, a launcher-side typo,
  a path fix — are recorded HERE, with root cause, ground truth verified BEFORE the fix, the fix
  itself, and why the smoke could not catch it. They do **not** touch a bar, a gate of record, or a
  branch condition.
- **ANYTHING THAT WOULD MOVE A BAR OR A BRANCH** is not a deviation. Before game 1 it is a
  **pre-game-1 amendment** to the pair, made in the open with the band unspent
  ([`AMENDMENTS.md`](AMENDMENTS.md)). After game 1 it is not available at all.

---

## What round 1 learned that this round should not have to re-learn

**`IS-D1` (2026-08-26)** — round 1's launcher-side ident-precheck read the `config` block off
`summary.json`, which carries **no config block at all** (the split is: config-shaped addresses →
`manifest.json`; statistics → `summary.json`). `cfg` came back `{}`, so `cand_leaf_hash` came back
`None`, and the precheck fail-closed **voided a healthy cell** — while the same empty dict made a
second conjunct (`leaf_diff_empty`) pass **vacuously** (`{} == {}`), hiding the cause. It cost the
round a stop at ~8 core-h.

**Carried into round 3, both halves, exactly as round 2 carried them:**

1. The per-cell pre-check reads `manifest.json` for config and `summary.json` for `n_failed`
   ([`DESIGN.md`](DESIGN.md) §6.4).
2. ⭐ **The vacuity is structurally impossible**: `screen_lib.leaf_gate()` requires both hashes to
   be present **strings** equal to their pins, not merely equal to each other. An empty config
   fails it loudly instead of passing half of it quietly.

**And round 1's instrument-hardening note, which round 2 acted on and round 3 keeps:** *"any
launcher-side gate that runs only once per round needs its own selftest fixture."* The per-cell
pre-check runs after **every** cell rather than once, and its arithmetic is `screen_lib`'s — the
same `leaf_gate()` the adjudicator calls.

---

## What round 2 learned, and what round 3 does about it

**`IS-A1` (2026-08-27)** — a cross-box `G-REV` short-sha comparison falsely voided a healthy round.
⛔ **That is an AMENDMENT, not a deviation** — it moved a gate of record — and it is written up in
full in [`AMENDMENTS.md`](AMENDMENTS.md), including how round 3 folds the canonicalized form into
`screen_lib.cross_box_rev_gate()` and where round 3 goes further than the amendment script did.

It is mentioned here only so a reader who comes looking for round 2's lesson in the deviations file
is pointed at the right document rather than concluding there wasn't one.

---

## A note on the owner's W constraint, so the ceremony is legible

The owner's **"limit local to w14 starting at 11am"** arrived **while the pair was still being
built — before any blind commit existed and with zero games run.** It is therefore folded into the
freeze itself and is **NOT an amendment**: there was no frozen pair to amend. `W_LOCAL=14`,
`screen_lib.W_LOCAL_NOTE`, the recomputed six-way split table in `DESIGN.md` §6.5(iii), the
resulting cell→box assignment and the raised `PASS_TIMEOUT_SECS` were all written **before** the
blind commit, like every other line of the pair.

Recorded here only so a reader who knows the constraint arrived mid-build does not go looking for
an amendment banner that would have been dishonest to write.
