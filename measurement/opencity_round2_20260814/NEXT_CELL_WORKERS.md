# WORKER COUNTS FOR THE NEXT CELL — owner directive, 2026-08-14 ~09:30

**Joshua, verbatim: "for. the next cell. make sure w22 for laptop and w30 for local".**

| box | W for the next cell | how to pass it |
|---|---|---|
| laptop | **22** | already the driver's `W_DEFAULT` for `laptop`; pass explicitly anyway |
| local | **30** | ⚠️ the driver's `W_DEFAULT` for `local` is **14** — W30 MUST be passed as arg 3 |

```
bash run_deploy_opencity_round2.sh laptop <BAND> 22 <CELL_FILTER>
bash run_deploy_opencity_round2.sh local  <BAND> 30 <CELL_FILTER>
```

This applies to the **next** cell launched, not to the two cells in flight when the
directive was given (laptop `Acap3_d2p0` at W22 — already correct; local `C_d16p0`
top-up at W14 — 22 games, finishing in minutes, not worth a restart).

**Why this file and not an edit to the driver:** both boxes were mid-run executing
`run_deploy_opencity_round2.sh` when the directive landed, and bash reads a script
incrementally by byte offset — editing a running script can corrupt its execution.
The driver's `W_DEFAULT` for `local` should be changed to 30 at the next quiet window;
until then this file is the record and the W is passed explicitly.

**Measurement note, not an objection:** absolute `ms/move` and `games/h` are
worker-count-dependent, so throughput figures from a W30 cell are NOT comparable to
the W14/W22 cells on this band. The deck-paired margin and `ms_ratio` are first-order
insensitive (both arms share the pool), which is what the primary statistic rests on.
