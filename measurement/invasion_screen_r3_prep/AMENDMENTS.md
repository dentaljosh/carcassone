# invasion_screen_r3_prep — post-freeze amendments

**NONE YET.** No cell has run.

This file exists at freeze so that an amendment has somewhere to be recorded the moment it is
made, rather than being written into the pair after the fact. The house class distinction:

- **A PRE-GAME-1 AMENDMENT** is made in the open, with the band unspent, before any real deck is
  played. It is recorded here with its authorisation.
- **AFTER GAME 1 the pair is law.** `READ_RULE.md`'s banner says nothing in it moves after the
  blind commit. A post-game-1 change to a bar, a gate of record or a branch condition is not
  available — the only route is the one round 2 had to take: freeze the verdict as it stands,
  record the defect, and get the OWNER to authorise a re-read of the SAME archive under a named,
  minimal, single-clause correction.
- **EXECUTION-LAYER / STATISTICS-BLIND** deviations — a misaddressed reader, a launcher-side typo,
  a path fix — are NOT amendments and are recorded in [`DEVIATIONS.md`](DEVIATIONS.md).

---

## ⭐⭐ IS-A1 — INHERITED FROM ROUND 2, AND **FOLDED INTO THIS PAIR'S ADJUDICATOR**

Round 2's one post-freeze amendment is the reason round 3's `G-REV` looks different, so it is
carried here in full rather than left behind in a sibling directory.

**What happened (round 2, 2026-08-27).** The frozen adjudicator's cross-box clause compared the two
boxes' **EMITTED SHORT REVS** for string equality:

```python
distinct = {r for r in revs.values() if r}
cross_box_rev_ok = len(distinct) <= 1        # ⛔ THE DEFECT
```

But `git rev-parse --short` chooses its length **per clone** — it lengthens to disambiguate against
that clone's own object database. So the two boxes, sitting at the **IDENTICAL** commit, emitted
`240626a3-dirty` (local) and `240626a31f-dirty` (laptop), and the round **falsely voided**. The
frozen verdict `U-UNREADABLE` **stands unedited on round 2's record**.

**Proof it was one commit.** Both boxes' `PINNED_SRC_REV` files were byte-identical
(`240626a31feeab01e22e73b42230a80a9889ec6f`), and every `SRC_CLEAN.jsonl` boundary was clean against
that pin on both boxes.

**Authorisation.** The owner ruled the re-read (verbatim "option 1 and shit", per the h2h-option-1
precedent). `analyze_screen_amended.py` was the frozen script with **ONE clause canonicalized**;
selftest GREEN; all other gates byte-identical. **AMENDED VERDICT: `BRACKET-CONTINUE`** (A_LOW
BRACKET / A_HIGH REVERSED / B both NULL / C_LOW BRACKET / C_MID NULL / C_HIGH NULL).

**Defect class.** The same as `h2h_22016`'s `G-REV` defect (short-sha-vs-full), in its **cross-box**
variant.

**The lesson, verbatim from round 2's amendment:**

> *canonicalize revs against the pin, never rev-vs-rev.*

### How round 3 folds it in — and where it goes FURTHER

⛔ **The fix is not copied as a patched clause; it is promoted into the bar library**, as
`screen_lib.cross_box_rev_gate()`, which `analyze_screen.py`'s `G-REV` calls. Two conjuncts, in
order:

1. **THE PINS AGREE.** Every box role that published a `PINNED_SRC_REV` must publish the **same**
   40-hex sha. ⭐ **This is the conjunct the amendment script did not have.** It reads *each box's
   own* published pin and states the "both boxes were at one commit" proposition **directly**,
   rather than inferring it from a single local file the boxes never wrote. A laptop that was never
   bundle-synced now fails HERE, loudly, on the right proposition.
2. **EVERY EMITTED REV CANONICALIZES TO THAT PIN** — strip `-dirty`, require ≥ 7 hex characters,
   require a **prefix** match. Short revs of *different lengths* both pass; a different commit does
   not.

⚠️ **And it cannot degenerate into "any prefix passes":** the ≥ 7-hex floor and the 40-hex pin
requirement are both enforced, and `tests/test_invasion_screen_r3_instrument.py` drives the gate
**in both directions** — round 2's exact case (`240626a3` vs `240626a31f` against the shared pin)
must **PASS**, and a genuinely different commit must **FAIL** — plus disagreeing pins, an absent
pin, a sub-7-hex rev, and an eight-distinct-spellings control that proves the verdict is a function
of each rev *separately* rather than of the set.

⚠️ **Why it lives in the library rather than in this file's successor:** round 2's amendment was a
one-off script that had never been exercised by the instrument suite. Moving it into `screen_lib`
means the launcher's precondition ladder and the adjudicator share one implementation, and the
tests drive it — the `track_d2r2_prep` defect this whole library exists against.

---

## What round 2 also learned, carried without needing an amendment

⭐ **`carc_rs_build` IS NOT A WHEEL FINGERPRINT.** Round 2 found this at ITS freeze, by
`--selftest` failing against round 1's own emitted archive: `rust_agent.carc_rs_build_id()` embeds
the **repo rev at call time**, not a compiled-in value, so archives from one wheel carry different
build strings. Round 3 has a third data point for it — round 2's seven cells emitted
`carc_rs-0.1.0+240626a31fee+…` where round 1's carried `ac709c42c6e2` and `47e7cc0ffb31`, and the
`carc_rs_binary_sha` was `a9ac686bca1417f9` on **all eleven**. `G-WHEEL-SAME` keys on the sha
**alone**, in all three rounds. (`screen_lib.R1_WHEEL_BINARY_SHA`'s banner carries the full story.)
