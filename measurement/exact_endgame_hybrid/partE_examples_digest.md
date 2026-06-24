# Part E — endgame mechanism examples (top 40 RoD1-suboptimal K=2 positions)

Solver-grounded (Part B regret): positions where RoD1 plays a SUBOPTIMAL endgame move.
'rod1_regret' = points RoD1 loses vs exact; exact_move = h3200's move where h3200 is
optimal (the common case), else UNKNOWN. Move types are coarse (action-range decode).

## Mechanism histogram
-  24  last-tile placement / scoring-conversion (different placement)
-  16  both-suboptimal (exact differs from both; needs solve)

## h3200 already-optimal on these RoD1 mistakes: **24/40 (60%)** — i.e. the deep heuristic ALREADY makes the fix
the exact solver would; exact play and h3200 mostly agree on how to repair RoD1's leak.

## Top examples (by RoD1 regret)
seed | ply | k | phase | self-opp | meep | legal | RoD1 | h3200 | exact | regret | h3200_opt | mechanism
--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---
3200000129 | 140 | 2 | TILES | 67-64 | 0 | 76 | tile_place | tile_place | UNKNOWN | 9.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000022 | 140 | 2 | TILES | 42-16 | 0 | 50 | tile_place | tile_place | tile_place | 6.0 | True | last-tile placement / scoring-conversion (different placement)
3200000099 | 140 | 2 | TILES | 38-57 | 1 | 47 | tile_place | tile_place | tile_place | 4.0 | True | last-tile placement / scoring-conversion (different placement)
3200000004 | 140 | 2 | TILES | 37-37 | 1 | 75 | tile_place | tile_place | UNKNOWN | 3.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000057 | 140 | 2 | TILES | 41-39 | 0 | 54 | tile_place | tile_place | tile_place | 3.0 | True | last-tile placement / scoring-conversion (different placement)
3200000077 | 140 | 2 | TILES | 32-12 | 0 | 42 | tile_place | tile_place | tile_place | 3.0 | True | last-tile placement / scoring-conversion (different placement)
3200000103 | 140 | 2 | TILES | 21-38 | 0 | 40 | tile_place | tile_place | UNKNOWN | 3.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000127 | 140 | 2 | TILES | 52-58 | 0 | 57 | tile_place | tile_place | UNKNOWN | 3.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000003 | 140 | 2 | TILES | 49-15 | 0 | 45 | tile_place | tile_place | UNKNOWN | 2.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000008 | 140 | 2 | TILES | 80-44 | 1 | 30 | tile_place | tile_place | tile_place | 2.0 | True | last-tile placement / scoring-conversion (different placement)
3200000011 | 140 | 2 | TILES | 44-42 | 0 | 48 | tile_place | tile_place | tile_place | 2.0 | True | last-tile placement / scoring-conversion (different placement)
3200000025 | 140 | 2 | TILES | 31-36 | 0 | 60 | tile_place | tile_place | tile_place | 2.0 | True | last-tile placement / scoring-conversion (different placement)
3200000034 | 140 | 2 | TILES | 62-34 | 0 | 53 | tile_place | tile_place | UNKNOWN | 2.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000074 | 140 | 2 | TILES | 41-28 | 0 | 46 | tile_place | tile_place | UNKNOWN | 2.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000080 | 140 | 2 | TILES | 36-37 | 0 | 54 | tile_place | tile_place | tile_place | 2.0 | True | last-tile placement / scoring-conversion (different placement)
3200000095 | 140 | 2 | TILES | 33-47 | 1 | 33 | tile_place | tile_place | tile_place | 2.0 | True | last-tile placement / scoring-conversion (different placement)
3200000121 | 140 | 2 | TILES | 35-30 | 1 | 24 | tile_place | tile_place | UNKNOWN | 2.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000130 | 140 | 2 | TILES | 18-44 | 0 | 44 | tile_place | tile_place | tile_place | 2.0 | True | last-tile placement / scoring-conversion (different placement)
3200000132 | 140 | 2 | TILES | 18-37 | 0 | 29 | tile_place | tile_place | UNKNOWN | 2.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000005 | 140 | 2 | TILES | 29-40 | 0 | 60 | tile_place | tile_place | UNKNOWN | 1.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000009 | 140 | 2 | TILES | 20-42 | 0 | 66 | tile_place | tile_place | tile_place | 1.0 | True | last-tile placement / scoring-conversion (different placement)
3200000018 | 140 | 2 | TILES | 32-37 | 0 | 51 | tile_place | tile_place | tile_place | 1.0 | True | last-tile placement / scoring-conversion (different placement)
3200000019 | 140 | 2 | TILES | 62-30 | 0 | 43 | tile_place | tile_place | UNKNOWN | 1.0 | False | both-suboptimal (exact differs from both; needs solve)
3200000020 | 140 | 2 | TILES | 53-42 | 1 | 41 | tile_place | tile_place | tile_place | 1.0 | True | last-tile placement / scoring-conversion (different placement)
3200000030 | 140 | 2 | TILES | 33-20 | 0 | 58 | tile_place | tile_place | UNKNOWN | 1.0 | False | both-suboptimal (exact differs from both; needs solve)
