# E4 autopsy — disagreement census

Generated 2026-08-12T23:39:18Z · design: [DESIGN.md](DESIGN.md)

**779 disagreement plies** over **26 games** (Joshua's seat; forced, exact-tail and agreeing plies excluded).

## Primary strata

| stratum | n | games | mean \|ΔQ\| | opening/mid/end | tile/meeple | F6 behind/level/ahead | F9 champ/his | F2 champ/his |
|---|---:|---:|---:|---|---|---|---|---|
| DEG | 276 | 26 | 0.0926 | 96/70/110 | 247/29 | 96/107/73 | 77/58 | 39/26 |
| FARM | 252 | 26 | 0.1440 | 105/95/52 | 156/96 | 64/114/74 | 70/45 | 42/30 |
| CLOISTER | 59 | 24 | 0.1329 | 26/19/14 | 41/18 | 16/28/15 | 14/17 | 9/11 |
| CITY | 120 | 26 | 0.1230 | 44/51/25 | 66/54 | 35/48/37 | 11/15 | 7/8 |
| ROAD | 72 | 25 | 0.0913 | 37/25/10 | 14/58 | 19/38/15 | 5/5 | 1/2 |
| NEUTRAL | 0 | 0 | — | 0/0/0 | 0/0 | 0/0/0 | 0/0 | 0/0 |

## Marginals (a ply counts once per type EITHER arm touches)

| type | touched | of which contested |
|---|---:|---:|
| farm | 451 | 353 |
| cloister | 211 | 87 |
| city | 344 | 149 |
| road | 370 | 70 |

## Meeple economy (meeple plies only, `champion -> Joshua`)

- champion commits a meeple, he passes: **120**
- he commits a meeple, champion passes: **64**
- both commit, different targets: **71**

Full axis table: `{'road->pass': 48, 'pass->farm': 32, 'farm->pass': 30, 'city->pass': 23, 'pass->city': 21, 'cloister->pass': 19, 'city->city': 17, 'farm->city': 12, 'pass->road': 11, 'city->farm': 9, 'road->city': 8, 'road->road': 7, 'farm->road': 5, 'road->farm': 5, 'cloister->farm': 3, 'farm->farm': 2, 'city->road': 2, 'cloister->road': 1}`

## Mechanism tags (pro-strategy scan F6 / F3 / F9 / F2)

- **F6** running score differential, his seat: `{'level': 335, 'behind': 230, 'ahead': 214}`
- **F3** mean unplaced-meeple reserve — his 2.64 · champion 2.06 · diff +0.59
- **F9** reinforces a losing/tied majority — champion arm **177** vs his arm **140**
- **F2** newly joins a structure where the opponent holds sole majority — champion arm **98** vs his arm **77**
- **F7** cross-world spread: **UNAVAILABLE** (pooled-only artifacts; see DESIGN.md §5.4)

## Covariates

- phase third: `{'opening': 308, 'middle': 260, 'endgame': 211}`
- decision type: `{'tile': 524, 'meeple': 255}`
- EV-loss bucket: `{'within_noise': 463, 'blunder': 160, 'inaccuracy': 156}`
- rules epoch: `{'fixed_v1': 687, 'walled': 63, 'app_aug2': 29}`
- degenerate fraction: **0.354**
