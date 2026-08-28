# DEVIATIONS — microgates_20260828

Everything that changed after the `PREREG.md` freeze commit
(`f6013f49 microgates: FREEZE (pre-outcome)`). PREREG is never edited.

---

## D1 — `notes.cls` is a LIST on multi-event plies (G-DETECT crashed)

**When:** before any gate statistic; the first `--stage gates` invocation raised
`TypeError: unhashable type: 'list'`.

**What:** the banked row's `notes.cls` is a plain string on a single-event ply
and a **list** on a multi-event one, and the per-event classes also live in
`notes.events[*].cls`. `tagged_classes()` now unions both and G-DETECT asks
whether the census fired ANY tagged class at the arm ply.

**Why this is not a loosening:** PREREG §4 already reserved exactly this
allowance ("the handful of banked rows whose tagged event is a multi-event ply —
`notes.n_events > 1` — where the FIRST onset need not be the tagged class") and
set the bar at ≥ 95 %. The realized bar was **82/82 = 1.000**, so the allowance
was never spent.

## D2 — the terminating transition CLEARS EVERY MEEPLE (farm sub-readouts were structurally zero)

**When:** after stage 1 had been run once and aggregated. **The primary gate
statistic `R_contest` = 0.8662 had therefore been seen before this fix.** It is
declared here rather than left to be discovered: nothing in the fix touches the
contest census, which reads `placed_meeples` at every ply while the meeples are
still on the board, and `R_contest` is unchanged by it (the re-run reproduces
it — see `MICROGATES.json`).

**What:** the engine's game-ending transition runs final scoring and returns
every meeple to its owner, so `terminal_board.state.placed_meeples` is EMPTY.
The first implementation read the farm view off that state and consequently saw
no farmers at all: **2,416 / 2,416** root farm components read as control →
`"none"`, and `R_farmer_zeroed_*` came out **identically 0.0** on 4,432
playouts — an all-zeros column, which is a bug signature, not a finding.
Verified directly (`probe4`): pre-scoring state `placed_meeples [7, 7]`,
terminal state `[0, 0]`.

**Fix:** `terminal_farm_view()` reads the **pre-scoring** board (the one
immediately before the terminating transition) whenever the terminal board
carries no meeples. Because the terminating action is a MEEPLES-phase action in
the ordinary case, that board's farm geometry is already the terminal geometry.
The one thing it can miss — a farmer placed BY that final action — is decoded
and injected (`extra_farmer`). Both facts are stamped per unit in
`terminal_farm_flags` (`scoring_state`, `injected_final_farmer`,
`last_action_phase`), so no unit hides which state was read.

**Blast radius:** the farm sub-readouts only (`R_farm_control`,
`R_farmer_zeroed_lost_majority`, `R_farmer_zeroed_no_cities`,
`farm_control_changed`). Those are explicitly NOT branch-deciding — PREREG §3.2:
"inform the written implication, but do not move the branch". `R_contest` and
`D_champ`, the two statistics that decide the branch, are untouched.

**Cost:** stage 1 was deleted and re-run in full (4,432 + 208 units, ~19 min at
W8). The instrument gates were re-run too, since `G-REPEAT` compares whole unit
rows and the rows gained fields.

## D4 — ⚠️ the streaming union-find re-roots, so `contested_seen` went stale (PRIMARY statistic affected)

**When:** after the full stage-1 and stage-2 passes had been run and aggregated,
while characterising the 6,547 onsets the mechanism logic labelled `unknown`.
**`R_contest` = 0.8662 had been seen. The corrected value is in
`MICROGATES.json` and the READOUT, and both numbers are stated there.** This is
the deviation that matters; it is declared, not buried.

**What:** PREREG §2.2 adaptation A1 said the two-pass Stage-A census was
"collapsed into a single streaming pass … the predicate and the ordering are
unchanged". **That claim was wrong in one detail.** Stage A dedups a contest
onset on `fid = uf.find(rep)` and gets away with it because `extract_events`
runs AFTER the whole replay, against the FINAL union-find. Evaluated
incrementally, that identity is not stable: `UF.union(a, b)` re-roots onto
`find(a)`, and `a` is the group's MINIMUM positional key, so a component that
grows a smaller key acquires a NEW root and every `fid` already recorded for it
goes stale. The component is then re-reported as a fresh onset.

Measured on `1785982194_705585.json` ply 60 world 11: a farm already carrying
`[2, 2]` (both seats) was re-reported at plies 106, 110 and 114 as it grew from
29 to 33 tiles — and a fourth "onset" at ply 94 turned out to be a re-report of a
farm that was **already contested at the crux root**, i.e. exactly the
false-positive class that inflates `R_contest`. That playout's onset list went
from 5 entries to 1.

**Fix (adaptation A3, now stated in the code):** component identity is carried by
**key membership**, not by a union-find root. Cities, roads and farms only ever
merge — a component never splits and never loses a positional key — so "have I
already reported this component?" is exactly "does it contain a key I have
already marked contested?". `contested_keys` replaces `contested_seen`, the
union-find is gone from the census, and `pre_parts` matches a previous-ply
component by whether its representative key is one of the current component's
keys (exact, same reason).

**Blast radius:** every G1 statistic. Stage 1 was deleted and re-run in full.
**Stage 2 was NOT re-run:** `D_champ` is computed from arm terminal margins
only, the playouts are byte-identical (same seeds, same policy, the census does
not touch play), and the g2 units' census fields are read by nothing. The
cross-stage determinism check was narrowed to the fields the PLAYOUT determines
(`CROSS_STAGE_KEYS`) so it still tests what it is meant to test — that two
independent passes replay the same game — rather than comparing two generations
of census bookkeeping.

**How it was found:** by chasing the `unknown` mechanism bucket rather than
accepting it. `unknown` was the signature — it means "contested now, but no
previous-ply part carried both seats", which is impossible for a genuinely new
contest and is exactly what a re-report of an already-contested component looks
like.

## D5 — `do_unit` did not check the job's profile against the PROCESS's profile

Found while chasing what looked like cross-process nondeterminism: a `walled`
row replayed inside a `fixed_v1` process read `margin -8` in its own process and
`-14` in the wrong one. `do_unit` tied the ARCHIVE to the JOB but never tied the
JOB to the process, so a mis-routed unit replays a walled game under
centered18 + retail + fixed-cloister + redraw + R9 and returns a plausible wrong
answer silently. **No banked unit was affected** — `run.sh` runs one profile per
process and `jobs_for` filters by profile, so the mis-route only ever happened in
an ad-hoc probe — but the guard is now in `do_unit` and fails loud.

## D3 — the rust `tier1_leg` path was not used

Stated in PREREG §2.1 at freeze time, repeated here because it is the largest
departure from the task brief: `carc_core::tier1::tier1_root` builds its game
with the DEFAULT `GameConfig` (its own docstring: "the walled rules profile,
whose `game_kwargs()` is `{}` by construction"), so it cannot replay a
`fixed_v1` archive — 277 of the 290 crux plies. The python twin
(`RuleBasedPlayer`, the definition `G-BITEXACT` grades the rust port against
over 15,360 playouts) is used instead, at a measured 0.0176 s/continuation ply.
Extending the binding would have meant rebuilding and reinstalling the wheel in
the venv the MAIN tree is editable-installed against, which a worktree-isolated
agent must not do.
