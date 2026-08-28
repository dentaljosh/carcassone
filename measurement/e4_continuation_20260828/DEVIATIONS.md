# DEVIATIONS — E4 CONTINUATION PRICING

Everything that differs from [`PREREG.md`](PREREG.md) or from the funding brief,
recorded as it happens. The PREREG is never edited after the freeze commit.

Freeze branch: `e4-continuation-freeze`. Ceremony: FREEZE commit, then a second
commit stamping its sha into `BLIND_COMMIT.json`.

---

## D-0 — the pre-freeze cost probe produced one visible outcome (DISCLOSED IN PREREG)

**Status: disclosed in `PREREG.md` §0.1 before the freeze commit, not a
post-hoc deviation.** Sizing the compute needed a whole real continuation at
production knobs; three units were launched and killed as soon as the timing
question was answered. One completed — `1787618319_251279.json` ply 4 world 0
(`control`), `delta_pts_mover = +37`. Its two `invasion` companions were killed
mid-flight and produced no outcome. No `invasion` / `defense` / `farm_capture`
outcome existed at freeze time.

The design, target set, estimator and constants were all on disk before the
probe ran. The unit is **kept** in the run: the instrument is deterministic in
`(deck_seed, ply, world, arm)`, so it recomputes bit-identically and serves as a
determinism gate. Dropping it would be a post-hoc filter on a seen outcome.

## D-1 — the arm cap runs at 1800 s CPU, not the nominal `ARM_WALL_CAP_S = 600`

The funding brief asked for a "wall cap ~600 s per continuation-world", and
`ARM_WALL_CAP_S = 600` stays the frozen constant. **The boxes run at
`ARM_CAP_S = 1800`**, which `PREREG.md` §2.4 pre-authorises ("set from the
measured worst-case arm with ≥3× headroom … any box-level value other than the
constant above is recorded in `DEVIATIONS.md`"). This is that record.

Reason, and it is a bias argument rather than a convenience one: the cap is an
`RLIMIT_CPU` cap, and **DRAM-contention stalls are charged to process CPU
time**. The measured worst-case arm is 182 s solo (§0.1 probe, the longest ply
in the set). At `W = 30` / `W = 22` on DRAM-bound work, that same arm can bill
2–3× the CPU. A 600 s cap would then fire on *legitimately slow, contention-hit*
arms — and every fired cap VOIDS a CRN pair, so the attrition would be
correlated with load and would silently bias which plies get priced. 1800 s is
~10× the measured worst arm and ~3× its worst plausible contended cost; it is a
runaway guard, not a budget.

## D-2 — the control decile match is 27/30 exact, 3 filled from the nearest decile

Pre-registered behaviour (`match_controls`'s shortfall rule), reported in
`PREREG.md` §1.1 with the achieved histogram, and repeated here because it is
the one place the frozen set is not exactly what the design asked for: the
59-ply divergent control pool is short in deciles 2 and 4, so 3 of the 30 slots
were filled by the nearest-to-centre rule. Achieved mean ply-fraction **0.297**
against the invasion set's **0.334**.

---

_(further deviations appended below as they occur)_
