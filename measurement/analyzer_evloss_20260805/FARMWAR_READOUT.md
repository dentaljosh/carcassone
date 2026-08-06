# Farm-war discriminator — READ-OUT

> **Status: SCORING IN FLIGHT (2026-08-06 early hours).** Pre-registration
> [FARMWAR_PREREG.md](FARMWAR_PREREG.md) committed `226a676` before any cell ran and is
> binding. The strata below were fixed before any position was scored; the verdict
> section is written only once `VERDICT.json` exists.

## Stratifier — the PRIMARY rule fired

`stratifier_rule = primary_leaf_term`. The pre-registered fallback was **not** needed:
`LeafConfig.farm_base_off` / `farm_growth_off` are live in `flat_leaf` and in
`carc-core/src/leaf/mod.rs`, and the production leaf's other farm-flavoured term is off by
construction (`v29_farm_flip_k == 0.0`), so the two knockouts sever every live farm term.

| | n | mean \|ΔQ\| |
|---|---|---|
| FARM | 21 | 0.2062 |
| CONTROL | 21 | 0.1987 |

Fifteen further candidate plies had a **degenerate 0/0 share** (the champion's leaf values
the two successors identically) and were dropped into **neither** stratum.

*(Verdict, per-epoch split, Tier-1 sign check and the threat review land here when the run
completes.)*
