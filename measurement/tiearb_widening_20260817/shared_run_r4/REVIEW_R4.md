# REVIEW_R4 — focused pass on rev R4's changed sections (commit b46cefd3). VERDICT: FAIL (3 blocking, all local to R4-3/R4-6)

Supply chain + cost roll-up REBUILT FROM PRIMITIVES this round (the named miss class):
53/54 figures exact — games-needed inversion 6/6, cost columns 24/24 (incl. correctly
dropping D-DRAW on S1-ONLY), power ladder 10/10, R4-5 all exact, S2 chain closes
(0.168 vs 0.1807 = z 0.84σ on n=613: "agrees" is justified; the R3 target was a 10×
internal contradiction, confirmed). Bonus cross-check worth adding to the doc: S1
realizes 39.4% of its mining ceiling, S2 40.9% — agreement to 1.5pp is direct evidence
the qualification×dedupe reduction is ceiling-independent, which licenses the two rates.
Blindness disclosure: sufficient in substance (see R3 below for the sentence that makes
it airtight). W-code delta: clean — exactly three conjunct changes, all three declared.

## BLOCKING

B1. Intra-stratum CROSS-BAND digest collisions (S1-base 135e9 ↔ S1-extension 137e9)
   are neither ruled nor measured: exclusion rule 1 covers spent-corpus collisions only,
   rule 2 covers S1↔S2 only; G-DISJOINT's five comparisons include no base_vs_extension
   and no within-stratum comparison (impossible in R3's contiguous band; possible now).
   At observed 0.18% density the expected base↔extension count at FULL is order-1+.
   FIX: sixth comparison base_vs_extension (per stratum, all three layers) + extend
   rule 1 to a total order ("between two R4 positions from different bands, the higher
   band number is excluded" — 135e9 < 137e9 < 138e9 resolves every case incl. top-up).
   NOTE: this adds to W5's delta list.

B2. The extension band's S1/S2 split is UNCOMMITTED while strata_root_overlap == 0 is
   a gate conjunct: +games is a sum of two disjoint requirements, but R4-6 commits one
   scalar range and FLOORS.json carries only games_extension — mining both strata from
   the whole range (the natural reading) fails §2b(iv) on a healthy corpus. R3 split
   135e9 at +349/+350 implicitly; R4 dropped it when parameterising.
   FIX: FLOORS.json carries games_extension_s1/games_extension_s2 + the two sub-ranges;
   R4-6's band table shows the split (e.g. FULL → 137e9 +0…+507 S1, +508…+5347 S2).

B3. The exclusion bound is stated at two values: DESIGN "≤0.5% AND ≤15 absolute" vs
   READ_RULE "⌈0.005 × qualifying_deduped⌉" (6 vs 7 at n₁=1350; 5 vs 6 at n₂=1100).
   FIX: one spelling in both files; recommend the ⌈·⌉ form; see C1 on the inert clause.

## WRONG-NUMBER (non-propagating)

A1. The S1 chain's stated factors don't produce its own count: 1,400×0.54×0.735=555.66
   printed as →556→"realized 551"; measured composite is 551/1400=0.3936; if 756 is the
   exact qualifying count the dedupe factor is 0.7288 not 0.735; 5 positions
   unaccounted (the exclusion explains 1). No downstream number is touched (r_S1 comes
   from the terminus) — but §7a.1 requires the read-out to PRINT this chain and R4-7
   threat 1 leans on it. FIX: print the three measured integers and back-derive factors
   marked "≈", or show 0.3936 as the measured composite.

## REQUIRED

R1. Close the bound's one gaming channel (the denominator grows with corpus size and
   threat 1 contemplates generating more): add "the bound is evaluated once, at the
   first POSITIONS_PLAN freeze, against the denominator recorded in FLOORS.json; a
   VOID is not curable by generating additional games."
R2. Write the ordering that makes floor-choice ungameable: c_IF remeasure → owner picks
   floor → FLOORS.json written → blind commit (pair + FLOORS.json, one commit) →
   extension band claimed. Currently implied, not stated.
R3. Add to §3.4: "the one supply statistic correlated with effect size — the capped
   fraction — was already a pre-registered constant (0.1807, Stage-1b); the realized
   0.168 confirmed it at 0.84σ and revised no bar, prediction or branch condition."

## COSMETIC (ride or fix)

C1. "≤15 absolute" never binds below n=3,000 — inert clause, delete or note.
C2. Bound tightness is floor-dependent: at S2@400 the bound is 2 and the false-VOID
   probability at observed density ≈3.7% (Poisson) — the owner picking the cheapest
   floor buys the highest spurious-VOID rate; STATE this in the floor menu.
C3. TOTAL ≠ gen+scoring without the unshown champ-picks + D-DRAW addends — footnote.
C4. "committed FLOORS" row label invites misreading target-vs-floor — rename or state
   the resulting ⌈0.95·n⌉ gate floors (1219/993).
C5. N=700 sits at the 30.6th percentile of [0.9,1.4] — "roughly the optimistic third,"
   not "half."
