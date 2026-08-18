# Committed fixture set — tie-arbiter widening instrument (W8 deliverable)

`ARMS.json`, `POSITIONS_PLAN.json` and `per_position_rows.jsonl` for each
stratum. They exist so DESIGN §9 step **4a**'s schema pass can resolve the
`READOUT::widening.*`, `GATE_DISJOINT`, `GATE_DRAW`, `POSITIONS_PLAN` and
`ARMS` spellings **before any real corpus exists**.

DESIGN §0.G adds two more, because it moved the four judge smokes OFF 4a (they
are not corpus-free: `select_smoke_positions` reads `ARMS.json` /
`POSITIONS_PLAN.json`, and `--positions-dir` DEFAULTS to the SPENT corpus):

  * `legs/s1/tier1-greedy/walled/leg1/manifest.json` — the LEG-MANIFEST fixture
    (`resolved_config.*`, `preflight.seeds.*`; these exist ONLY on the ARB leg)
  * `SMOKE_MANIFEST_{S1,S2}_{clair-puct,tier1-greedy}.json` — the SMOKE-MANIFEST
    fixture (`c_worker_secs_per_playout`, `crn_cross_leg_identical`)

so every spelling those addresses use is still audited BEFORE the pair freezes.

The `ARMS.json` fixtures deliberately contain all three rid KINDS:
  * one **champion-append** rid (`champ_outside_tieset`, `len(arms) - len(arms_full) == 1`)
  * one **capped** rid (`capped_at_4`, > 4 deduped arms, so the J=4 draw binds)
  * one **all_transposition** rid (`n_distinct_afterstates == 1`), carried in
    `DROPPED_ALL_TRANSPOSITION.json` as well

⚠️ **Every value here is SYNTHETIC** — produced by a seeded RNG, with no replay,
no playout, no engine and no leaf. These files are a SHAPE contract and are
**never a data source for any statistic**. Regenerate with:

    python scripts/tiletie/widening_fixtures.py --emit
