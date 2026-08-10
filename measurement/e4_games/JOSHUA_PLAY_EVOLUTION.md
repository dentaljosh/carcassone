# Joshua's self-reported play evolution vs the champion (E4 anchor context)

> Status: OBSERVATIONAL RECORD — qualitative, no claim minted. Feeds interpretation of the
> E4 ledger (README.md) and priors for leaf-term levers. Recorded verbatim at his request.

## 2026-08-10 ~02:15, mid-streak (4 straight wins, "7 of the last 10", latest +54)

Verbatim:

> "for the record. I can't tell you I know his game or can predict his moves. I think I
> learned from him early on. I respect his game. but I'm not as surprised anymore. I look
> at the remaining bag now a bunch. I keep at least one meeple in hand unless it's very
> late. I don't commit to farms early. but I'll challenge his farms early if they look
> juicy. I guess I'm doing explicit reasoning. not sure there's a gestalt yet. but my net
> is improving."

## Mapping to the program (why this is data, not color)

1. **"Keep at least one meeple in hand unless it's very late"** — a phase-indexed
   meeple-economy policy: reserve value HIGH early, decaying late. This is precisely the
   hypothesis of the Part C β dose ladder (phase multiplier on the meeple curve,
   `f(k;β)=clip(1+β(k−35)/35,0,2)`, E[f]=1): the sign of β his policy corresponds to is
   the arm that up-weights meeple-in-hand early and releases it late. His testimony is an
   independent human prior for the live experiment — recorded BEFORE the ladder verdict
   (attempt 2 pending at write time; band 1.16e11).

2. **"I look at the remaining bag now a bunch"** — note the contrast: bag-aware closure
   probability as a STATIC LEAF TERM was tried for the champion and read null
   (`bag_close`, ties champion; LEVER_INDEX). Joshua uses bag information inside explicit
   lookahead ("will X close before the tiles run out"), i.e. as search conditioning, not
   as a leaf feature — the knowing-vs-using distinction CL-073 formalized (prediction ≠
   discrimination). Human profit from a signal our leaf-term encoding of it couldn't buy.

3. **"Don't commit to farms early / challenge his juicy farms early"** — asymmetric farm
   timing (defensive late-commit + offensive early-contest). Farms are already the ONLY
   >3σ component in his E4 edge (+11.57 pts, z +3.01, epoch n=14 at last close). The
   offensive half is adjacent to the NEVER-TRIED "targeted denial on near-complete large
   opponent features" reframe (LEVER_INDEX, BACKLOG 2026-05-16).

4. **"Not as surprised anymore… my net is improving"** — the anchor is NONSTATIONARY: he
   is adapting to a fixed opponent that cannot adapt back. Measurement consequence: E4
   epoch stats should carry a TREND read (margin vs game index), not only a pooled mean;
   pooling flat understates his current level and overstates the champion's. His "learned
   from him early on" also means early-epoch games partly measure a weaker Joshua.

## Standing interpretation rules this file adds

- When reporting E4 epoch stats, report the pooled mean AND the within-epoch trend.
- If the Part C ladder returns a positive slope in the arm matching policy (1), cite this
  file as the pre-registered-in-spirit human prior (it does NOT strengthen the statistics;
  it is convergent qualitative evidence only).
