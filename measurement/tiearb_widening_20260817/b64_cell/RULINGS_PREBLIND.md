# B64 CELL — PRE-BLIND DRAFTING RULINGS, 2026-08-19

> **Dated pre-blind text amendments on a signed-but-not-yet-blind pair.** Three spec-vs-buildable
> mismatches from the builder's report (`c4bf293c`, worktree `agent-a7173eaf014b5c81d`; 468 tests,
> known-good partition **11/11 PASS** + `G-NEST`/`G-DIVERGE` **N-A with reasons**, `W` false today
> so `B-CONFIRMED` correctly flagged unreachable — the `N-A (reason)` classification my sign-off
> required is present).
>
> **None of these changes a bar, a branch condition, or a statistic.** All three are address /
> surface questions on gates whose *content* is unchanged.

## RULING 1 — `G-SMOKE` / §9.2: **the row's whitelist governs OUTCOME KEYS ONLY. Builder's reading CONFIRMED.**

The pair states two rules on two surfaces and they were being read as one:

| surface | rule | governs |
|---|---|---|
| **emitter** (`SMOKE.json` writer) | **fail-closed on unlisted keys** — the writer may only emit what the whitelist names | what gets **written** |
| **gate row** `G-SMOKE` | fires on **forbidden OUTCOME keys at any depth** | what may be **read** |

⭐ **Read as one whitelist over the artifact, the gate row fails a known-good smoke on its own
structural keys** (`headline`, `kind`, `cells`, `throwaway_band`, …) — the fail-always class, and
the builder was right to refuse that reading. **The emitter whitelist is a WRITE discipline; the
gate is a READ discipline, and they have different jobs**: the first stops an outcome ever being
serialised, the second stops one being consumed if it somehow was. Collapsing them makes the strict
one govern both and voids healthy runs.

**Adopted:** gate = **forbidden-outcome-keys-at-any-depth**; the emitter whitelist result is
**reported beside it** and is not a gate input.

⚠️ **The pair needs ONE clarifying sentence pre-blind** — the ambiguity is real, not the builder's
misreading, and leaving it to a runbook would re-open it. Add to §9.2 and to the `G-SMOKE` row:

> *"§9.2 defines TWO surfaces. The **emitter** whitelist is fail-closed on unlisted keys and governs
> what `SMOKE.json` may contain. The **`G-SMOKE` row** fires only on forbidden **outcome** keys, at
> any depth. Structural keys are expected and never fire the row. A reading that applies the
> emitter whitelist to the row fails a known-good smoke."*

## RULING 2 — `G-J13`: **PIN the key path in the pair. Documented resolution order is NOT enough here.**

The pair requires the two-sided control **at both `B` values per host** but names **one file per
host** with **no address for `B` inside it**. On the known-good artifact `B` sits at
`j13_witness.B` / `expected.B`.

**Ruled: pin the exact key path**, do not accept a documented resolution order. Grounds: `G-J13` is
the gate that proves the arbiter **changed the pick at both `B` values** — the liveness evidence for
the whole contrast — and a resolution order is a place for a reader to choose. This campaign has
spent three reviews on addresses that resolved somewhere unintended; **the one gate that proves the
instrument is live should not be the one left to search.**

**Adopted address, per host file `PREFLIGHT_*_${HOST}_FIRST.json`:**

```
j13_witness.B          -- the B the control ran at        (int, 64 or 16)
expected.B             -- the B the control asserted      (int, must equal j13_witness.B)
j13_witness.pick_changed        (bool, must be true)
j13_witness.root_leaf_value_bits_unchanged  (bool, must be true)
```

**and the row's conjunct becomes: for EACH host, BOTH `B ∈ {64, 16}` appear across that host's
witness records, each with both booleans true.** ⚠️ **Absent `B` ⇒ FAIL** (not "assume the file's
`B`"), because a file with no `B` cannot evidence *"at both `B` values"* — the exact claim the gate
exists to make.

## RULING 3 — `G-FAILED` clause 3: **NARROW it, with the reason on record. Do not add a harness field now.**

Clause 3 requires a per-failure **diagnostic class** that the pair routes nowhere and the harness
does not emit ⇒ **vacuous at `n_failed == 0`, unevaluable with failures.**

**Ruled: NARROW clause 3** rather than commission the harness addition, on three grounds:

1. ⭐ **The pair is signed and one step from blind commit.** A new emitter field is a code change
   whose output no one has seen, added to the artifact a gate reads, *after* sign-off. That is how
   the three unsatisfiable gates got shipped — and D4.18's own qualitative trigger was authored
   against a class the harness **already emitted** (`WindowTruncationError` from the window-truncation
   study). Here it does not.
2. **The clause's protective content survives narrowing.** What it exists to prevent is *silently
   absorbing an unknown failure mode into a numeric bound*. That is preserved by making **any**
   failure a disclosure obligation with an **escalation trigger**, without requiring a machine-readable
   class.
3. **Clauses 1 and 2 are untouched and remain live** — the 2% rate bound and the
   candidate-correlated-exclusion (`capoff`) pattern both evaluate on quantities the harness emits.

**Adopted clause 3, replacing the current text:**

> *"**(3)** If `F_w + F_n > 0`, the read-out must print, for every failed game, the harness's raw
> failure record verbatim (message and traceback tail as emitted), and the run **HALTS for owner
> escalation before adjudication** unless every failure is manually confirmed to be the known
> `WindowTruncationError` class. **The confirmation is a human act recorded in the read-out, and it
> is the one place this rule admits one** — it gates escalation, never a branch."*

⚠️ **That is a deliberate, disclosed exception to "no owner call adjudicates any outcome":** it
adjudicates **nothing** — no branch, no bar, no statistic moves on it — it decides only whether the
run pauses. **Recorded as an exception rather than hidden as a convention.**

**Carried forward instead of built now:** a `diagnostic_class` field on the failure record is the
right long-run fix and belongs in the **harness**, pre-registered by the next pair that needs it —
`rung3_r5` already carries D4.18's class trigger and can adopt it first, on a corpus where the
failure mode is understood.

---

**None of the three moves a bar or a branch.** Ruling 1 clarifies which surface a whitelist governs;
ruling 2 pins an address; ruling 3 narrows a clause that could not be evaluated and records why.
**The B64 chain is unblocked: blind commit → band claim → smoke → launch.**
