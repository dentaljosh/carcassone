# c1_pricing_prep — execution-layer deviations

## C1-D1 — 2026-08-29 ~05:1xZ: preflight crashed on an API guess (fixed pre-launch)

`preflight_c1.py:77` called `prof.r9_env_on()` — but `r9_env_on` is a MODULE
function in `carcassonne_ai.rules_profile`, not a `RulesProfile` method. The
design agent disclosed it could not execute the preflight pre-freeze (boxes
saturated by the A1 round); first execution was in the post-A2 window as its own
DESIGN instructed. One-line fix at the site, commented; execution-layer,
statistics-blind (an env-latch health check upstream of any statistic).

Post-fix result: **PASS, zero drops** — G-LEGAL drop_rate 0.0 in every stratum
(farm_capture 14/14 retained); the legal-mask epoch hazard the design flagged
did not materialize. VOID_TRIGGERED: [].
