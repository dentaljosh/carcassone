# Part E — mechanism classification (462 deep-vs-h3200 disagreements)

## Move-type histogram (NOTE: suite is TILES-phase roots only, so meeple/farm decisions are
## downstream and never the audited root choice — all disagreements are tile-PLACEMENT geometry,
## mirroring the exact-endgame finding that the leak is placement, not meeple mgmt)
- 462  tile placement (same phase, different square = blocking/conversion/tempo)

## Immediate board-effect sub-classification (apply each move, compare mover's resulting score)
- deep captures MORE immediate pts: 6/462  (shallow leaves points on the table)
- deep scores LESS immediate (positional/tempo sacrifice): 15/462
- equal immediate score (pure geometry / blocking / future-equity): 441/462
- mean (deep - shallow) immediate pts: -0.08

  - 441  equal turn scoring (positional / blocking / future-equity, no completion diff)
  -   4  deep forgoes 6 completion pts this turn (positional / tempo / setup)
  -   4  deep forgoes 4 completion pts this turn (positional / tempo / setup)
  -   3  deep forgoes 3 completion pts this turn (positional / tempo / setup)
  -   2  deep completes +2 more pts this turn (shallow leaves a completion / conversion)
  -   1  deep completes +10 more pts this turn (shallow leaves a completion / conversion)
  -   1  deep forgoes 1 completion pts this turn (positional / tempo / setup)
  -   1  deep forgoes 9 completion pts this turn (positional / tempo / setup)
  -   1  deep completes +7 more pts this turn (shallow leaves a completion / conversion)
  -   1  deep forgoes 2 completion pts this turn (positional / tempo / setup)
  -   1  deep completes +9 more pts this turn (shallow leaves a completion / conversion)
  -   1  deep completes +1 more pts this turn (shallow leaves a completion / conversion)
  -   1  deep forgoes 8 completion pts this turn (positional / tempo / setup)

## By phase
  opening:62  midgame:83  late_mid:72  pre_endgame:108  endgame:137

## Representative examples
seed | ply | k | phase | legal | margin | h3200 | deep | conv | rod1==dp | dNow | sub_mechanism
--- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---
1925000039 | 128 | 8 | pre_endgame | 52 | 6 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000061 | 128 | 8 | pre_endgame | 40 | 38 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000009 | 128 | 8 | pre_endgame | 50 | 26 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000048 | 128 | 8 | pre_endgame | 64 | 10 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000036 | 128 | 8 | pre_endgame | 38 | 4 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000051 | 128 | 8 | pre_endgame | 51 | 16 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000042 | 124 | 10 | pre_endgame | 39 | 14 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000032 | 124 | 10 | pre_endgame | 29 | 16 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000052 | 124 | 10 | pre_endgame | 26 | 4 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000036 | 124 | 10 | pre_endgame | 29 | 4 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000068 | 124 | 10 | pre_endgame | 38 | 16 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000079 | 124 | 10 | pre_endgame | 33 | 13 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000004 | 124 | 10 | pre_endgame | 60 | 42 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000063 | 124 | 10 | pre_endgame | 60 | 13 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000087 | 124 | 10 | pre_endgame | 41 | 34 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000002 | 124 | 10 | pre_endgame | 60 | 14 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000024 | 124 | 10 | pre_endgame | 37 | 2 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000089 | 124 | 10 | pre_endgame | 44 | 4 | tile_place | tile_place | True | False | 10 | deep completes +10 more pts this turn (shallow l
1925000021 | 120 | 12 | pre_endgame | 30 | 1 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000036 | 120 | 12 | pre_endgame | 40 | 4 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000064 | 120 | 12 | pre_endgame | 37 | 50 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000011 | 120 | 12 | pre_endgame | 60 | 19 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000089 | 120 | 12 | pre_endgame | 41 | 4 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000040 | 120 | 12 | pre_endgame | 45 | 21 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000033 | 120 | 12 | pre_endgame | 33 | 49 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000018 | 120 | 12 | pre_endgame | 109 | 16 | tile_place | tile_place | True | False | -1 | deep forgoes 1 completion pts this turn (positio
1925000059 | 120 | 12 | pre_endgame | 35 | 4 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000074 | 120 | 12 | pre_endgame | 46 | 26 | tile_place | tile_place | True | True | 0 | equal turn scoring (positional / blocking / futu
1925000077 | 120 | 12 | pre_endgame | 32 | 25 | tile_place | tile_place | True | False | 0 | equal turn scoring (positional / blocking / futu
1925000039 | 120 | 12 | pre_endgame | 60 | 10 | tile_place | tile_place | True | True | -6 | deep forgoes 6 completion pts this turn (positio
