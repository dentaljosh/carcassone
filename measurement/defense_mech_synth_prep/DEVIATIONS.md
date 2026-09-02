# DEVIATIONS — synth mechanism-corroboration cell

## D-LAUNCH-1 — launcher freeze check corrected PRE-LAUNCH (2026-09-02, 0 units played)

`launch_local.sh` refused with `HEAD != BLIND_COMMIT`. That equality can never hold under
the two-commit house pattern (the stamping commit is the freeze commit's child), so the
check as written could never launch any round. Replaced, statistics-blind (no harvest, no
unit, no smoke beyond the build-time DRY smoke existed), by the check the pattern means:
HEAD must DESCEND from the freeze commit and the round directory must be unchanged since
it except `BLIND_COMMIT.json`. The frozen design, selector, bar and branch map are
untouched (`git diff 7a835684 HEAD -- measurement/defense_mech_synth_prep` = the stamp
+ this file + this launcher hunk). The round runs from a detached worktree pinned at the
launching HEAD (the 44k-rung precedent) so later main-tree commits cannot move the pin.
