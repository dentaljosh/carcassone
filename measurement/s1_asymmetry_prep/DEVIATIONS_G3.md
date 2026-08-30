## G3-D1 (2026-08-30, pre-launch, statistics-blind, execution-layer)
The launcher's stale-wheel probe grepped `dir(carc_rs)` for `jr_expansions` — the R7 fields
are dict KEYS returned by `stats()`, invisible to `dir()` by construction, so the probe
refused a healthy wheel (`ad211fd3…`) whose own emitted smoke carried the real counters
(SMOKE_OPP candidate boosted 4,528,040 / opponent 0; the smoke's G-WITNESS — the binding
check by the launcher's own words — PASSED). Replaced with an honest probe: one throwaway
8-sim search, then assert the three keys on the returned stats dict. No statistic of the
round existed; the smoke's adjudication is untouched. PG-D7..D9 class.
