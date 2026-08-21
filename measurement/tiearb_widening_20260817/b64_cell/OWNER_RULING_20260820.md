# OWNER RULING — the fresh N4 wall-clock ruling licensed by `B-COSTKILL` follow-up (i)

**Date: 2026-08-20 (evening). Owner: Joshua, in-session, verbatim: "I'm buying b64."**

This is the ruling the `B-COSTKILL` branch named as its one live follow-up
([READOUT_B64.md](verdicts/READOUT_B64.md): *"a fresh owner wall-clock ruling on whether the
N4 bar moves above B = 16"*). It is an **owner decision document, not a measurement** — it
changes no number anywhere.

## The ruling

1. **The N4 `rho_wall ≤ 1.20` bar is waived at `B = 64` for DESKTOP production play.**
   The owner accepts the measured cost: `rho_wall(64)` = 2.4897 sequential amortized arbiter
   overhead (≈3.5× total per move, ≈6 s/move against the champion's ~1.8 s baseline; the
   arbiter fires post-search at the root on resolved ties — the extra wall buys no extra
   search). This is consistent with, and now formalizes beyond B=16, the owner's pre-campaign
   Stage-2 §0.D ruling (*"we can afford some wallclock during play, especially if its not
   every tile draw. dont let that be the constraint right now"*, commit `a81b8c72`), whose
   anti-gaming clause bounded it at B=16 — which is why a fresh ruling was required and why
   this document exists.
2. **Deploy of the tie arbiter at `B = 64 / J = 4` into the desktop champion shape is
   AUTHORIZED** on the cell's evidence (results.csv
   `tiearb_widening_b64_gamecell_WIDE_B64_minus_NARROW_B16_n750decks_b139e9`: WIDE
   +63.95 ± 9.12 elo vs the unmodified champion, wr 0.591, n = 1,500; primary
   D = WIDE − NARROW = +1.7167 pts/game deck-paired, z_D +2.6561 over the committed 2σ floor
   +1.427; 13/13 gates PASS). Precedent for a config promotion on an owner "yes" over
   existing gated evidence: the 2026-07-29 k8×1376 budget promotion.

## What this ruling does NOT do

- **It does not rewrite the verdict of record.** The cell's branch remains `B-COSTKILL`
  forever: `W` was FALSE fail-closed because no waiver predated game 1, exactly as the
  prereg was designed. This ruling is the *licensed follow-up*, dated after the read-out.
- **It does not touch the phone.** `rho_phone(64)` ≈ [22.08, 23.9] — a third currency, not
  solved. The mobile profile keeps playing the unmodified champion of record.
- **It does not widen `J`.** rung3_r5 read `X-INCONCLUSIVE`; J stays 4.
- **It does not re-anchor any ruler or eval baseline.** Fixed eval/anchor sides stay the
  unmodified champion (the curve125 ambient-contamination warning pattern applies); whether
  any future ruler adopts the arbiter side is a separate, explicit decision.
- **It mints no claim.** The evidence rows in results.csv are the citation; usual
  self-anchored caveat (elo vs our own champion within band 139e9, not absolute strength).

Recorded by the session orchestrator on the owner's verbatim words; scope reading
("buying" = accepting the wall-clock price and deploying B=64 on desktop) stated back to the
owner in the same conversation for correction if wrong.
