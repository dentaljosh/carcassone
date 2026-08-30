# E-3 PREREG — new-farm-plies out-of-sample pricing (frozen 2026-08-30, owner-funded "I'm funding")

> ⛔ COMMITTED BEFORE THE TRIGGER DATA EXISTS. Fires only when the E4 archive holds ≥30 NEW
> divergent farm_capture plies (plies not among the 14 already priced by C1/continuation —
> those two reads are r=0.775 correlated on 12 shared plies and are ONE signal).

* **Trigger:** ≥30 new divergent farm_capture plies in `measurement/e4_games/` (Stage-A census
  definition, same selector), none overlapping the 2026-08-27/28 priced sets.
* **Instrument:** the C1 outcome-pricing harness VERBATIM (continuation price at M=16,
  CRN world discipline, world-index salt split per CL-084 — selection and pricing on
  independent worlds). No harness changes without a fresh prereg.
* **Statistic:** the new-plies-only stratum mean price, se over plies. Worlds cannot move the
  se (farm sd across plies 5.22 at M=8 vs 6.36 at M≤64 — between-ply variance dominates);
  ONLY new plies do — that is the point of this prereg.
* **Branches:** z ≥ 2 ⇒ amend CL-083's per-move clause and fund the farm leaf term (standard
  entry fee: ablation cell + neighbor re-sweep); z < 1 ⇒ the farm_capture WATCH thread dies
  with power and the counterevidence clause is retired; else ⇒ extend only by MORE NEW PLIES,
  never by re-reading the old 14.
* **Cost at trigger:** pricing <0.1 two-box hours; the real cost is owner game-time
  (~50–70 more E4 games to accumulate the plies).
