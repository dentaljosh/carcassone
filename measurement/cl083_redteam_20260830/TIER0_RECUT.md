# Tier-0 adaptation re-cut — READ_RULE'd home (ran 2026-08-30 inside the red-team workflow, read-only)

Corpus: the banked E4 archives ordered by `finished_at`, conditioned on budget epoch
(53 games at sims_effective=1376; 2 stragglers at 688 and 1 at the 22k mobile note excluded
from the margin row). Statistics pre-named by the workflow prompt before computation.

| statistic | first half | second half / last-15 | contrast |
|---|---|---|---|
| owner margin (11k epoch, n=53) | +11.1 | +16.2 | +5.1, se 6.9, z +0.75 |
| owner invasion plies/game (priced-ply proxy) | 1.76 | 1.68 | −0.08, se 0.30, z −0.27 |
| agreement gradient (invasion − control) | +0.394 (z 4.05) | +0.416 (z 4.37); last-15 +0.360 (z 2.78) | flat |

Reading (frozen with the numbers): NO within-corpus adaptation ramp is visible in the three
cheapest banked statistics — the owner expressed the exploit at full rate from the start of E4
and the gradient is time-stable. UNDERPOWERED to exclude a ramp (~±14 pts on the half-difference
at 2σ); says nothing about pre-corpus adaptation. Mild tension with
measurement/e4_exploit_grading_20260825/COMPOSITION.md ("the learning curve is on the
CHAMPION's side", champion city-share −8.1pp): the composition signature moved, the margin
did not resolve. First evidence row for CL-086.
