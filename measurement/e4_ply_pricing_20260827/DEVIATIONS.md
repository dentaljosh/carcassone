# DEVIATIONS — E4 ply pricing

Every departure from [`PREREG.md`](PREREG.md) after the blind commit, with its
reason and its blast radius. Empty sections are stated as empty on purpose:
"nothing deviated" is a claim this file has to make explicitly.

## Before the freeze (design decisions, not deviations)

* **D-0 (2026-08-27).** The brief named "the census's ~90 merge rows + farm
  captures" as stratum (a). Realized as **90 `invasion` + 27 `farm_capture`** rows:
  the census carries 90 owner-deliberate contest onsets and 27 owner-caused late
  farm-majority switches, and the two are kept as SEPARATE strata rather than
  merged, because Stage A found they overlap (40 of the invasions are already farm
  invasions) and pooling them would double-count the shared mechanism. Farm rows
  whose ply is already an invasion ply are dropped from `farm_capture`.
* **D-1 (2026-08-27).** The brief asked for "~50" control plies; the decile-matched
  rule yields **91** (one control per invasion ply, matched within game and decile).
  Kept at 91 rather than sub-sampled to 50: a per-invasion matched partner is the
  robust within-game contrast the house prefers, and the extra rows are cheap
  (controls are almost all above the exact cut, so they cost a counterfactual move
  and archive arithmetic, not a solve).
* **D-2 (2026-08-27).** The brief's defense definition ("champion plies where an
  invasion threat materialized within the following N plies") is realized as *the
  champion's most recent TILES-phase ply before each invasion onset, if within
  `N = DEFENSE_WINDOW_PLIES = 8` plies*, de-duplicated. Taking every champion ply
  in the window would have made the defense stratum a near-copy of the invasion
  stratum's neighbourhood; one ply per invasion keeps it a 1:1 contrast.
* **D-5 (2026-08-27).** The brief guessed the exact cut would land "likely 6–9".
  **Measured, it lands at K ≤ 5** (`MODE_CUT.json`, `COST_PROBE_laptop.json`):
  marginalized grows ~10–30× per K and costs 290 s at K=4, so K=5 projects over the
  ~1800 s/solve cap; clairvoyant+ab is 10–35× cheaper at the same K and buys exactly
  one more. Exact coverage is therefore 13 of 290 plies (4.5 %), not the ~9 % the
  K-histogram alone suggested. The cut was set from the measured tail BEFORE any
  price existed and is frozen in the blind commit.
* **D-6 (2026-08-27).** The `exact_clairvoyant_M` mode was restructured to run its
  `m_worlds + 1` solves as **separately isolated children, one per world**, rather
  than one capped child for the whole average. With a single child, one pathological
  deck order at the cap would have voided the ply's entire price; per-world it is
  skipped alone and `m_worlds_ok` records how many landed. This is a strengthening
  of the brief's "per-solve caps, skip-and-record over the cap", not a relaxation.
* **D-7 (2026-08-27).** The rust-vs-python gate is run at **K ≤ 3 on real E4
  positions across all three profiles** (30 checks, 0 mismatches) plus a dedicated
  `fixed_v1` marginalized leg at K=4 — not at every K the instrument solves at.
  Reason: the PYTHON oracle is the expensive side (it costs ~20× the Rust it gates,
  measured), so re-gating depth here would have cost more than the whole pricing
  run. DEPTH is instead inherited from the standing `reconcile_exact_solver`
  campaign (`G7_exact_solver_run2.json`: 457 checks, 0 mismatches, incl.
  `k3:marginalized` ×74 and `k4:clairvoyant+ab` ×48), and the RULES PROFILE is what
  the E4 legs add. Named here because "we gated the profile, not the depth" is the
  kind of thing a reader must not have to infer.
* **D-4 (2026-08-27).** **The census's 90 invasion EVENTS live on 86 distinct
  PLIES.** Four owner moves each open two contest onsets at once (one merge
  connecting the stub to two different incumbent features). The ply is the unit of
  pricing — one move gets one price — so those events are GROUPED onto their ply
  (`notes.n_events`, `notes.events`, gross fields summed) rather than emitted as
  duplicate rows. Pricing 90 rows would have double-counted 4 moves. The stratum
  therefore reports as "86 plies covering 90 census events", and
  `test_invasion_rows_cover_all_90_census_events_on_86_distinct_plies` pins both
  numbers so the census total is never lost.
* **D-3 (2026-08-27).** K is defined as `len(deck) + (next_tile is not None)` — the
  exact solver's convention — NOT `ev_loss`'s `len(deck)`. The two differ by one
  and the cut is a solver cut, so the solver's convention governs.

## After the freeze

*(nothing yet)*
