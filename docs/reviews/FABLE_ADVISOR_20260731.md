# FABLE ADVISOR MEMO — publication portfolio & project calibration (2026-07-31)

> **⚠️ ADVISORY ONLY.** Commissioned by Joshua ("I guess I'm ready to stop chasing strength…
> this is a good time to reflect"). Nothing in this memo is a decision; every recommendation
> is a proposal awaiting Joshua's call. No config, governance row, or measurement was touched
> in its preparation. Reviewer: senior-advisor pass (Claude Fable 5), reading-only, one evening,
> against the live tree at branch `android-app` (leaf-ablation overnight run in progress).

**Grounding:** [CLAUDE.md](../../CLAUDE.md) · [ORIGINAL_PROMPT.md](../ORIGINAL_PROMPT.md) ·
[STATUS.md](../../STATUS.md) · [PROGRAM_ROADMAP_2026-07-07.md](../PROGRAM_ROADMAP_2026-07-07.md) ·
[CLAIM_REGISTRY.csv](../../governance/CLAIM_REGISTRY.csv) · [LEVER_INDEX.md](../LEVER_INDEX.md) ·
[CLEAN_EVAL_AUDIT.md](../../clean_eval/CLEAN_EVAL_AUDIT.md) ·
[BURIED_CAVEATS_AUDIT_20260730.md](BURIED_CAVEATS_AUDIT_20260730.md) ·
[FALSE_NEGATIVE_SWEEP_20260730.md](FALSE_NEGATIVE_SWEEP_20260730.md) ·
[value_unlock READOUT](../../measurement/value_unlock_20260730/READOUT.md) ·
[CLIFF_LADDER_88E9_READOUT_20260729.md](../../measurement/classical_search/CLIFF_LADDER_88E9_READOUT_20260729.md) ·
[TOURNAMENT_LANDSCAPE_MEMO_20260728.md](../../measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md) ·
commit `b7d61ab` (the border root-cause) · [BACKLOG.md](../../BACKLOG.md) 2026-07-30 charters.

---

## 1. Executive summary

**This project contains two publishable papers today, a third within ~90 days, and several
satellites that are blog posts, not papers.** The two real papers are (P1) the negative
result — *outcome prediction is not move discrimination*: a pre-registered, multi-front kill
ladder showing no learned value function beats a hand-crafted leaf at move ranking, closed
representation-independently and with the mechanism isolated
([CL-073](../../measurement/value_unlock_20260730/READOUT.md): a value head that predicts
outcomes *better* than the heuristic, r 0.680 vs 0.61, still loses sibling discrimination
2.1×, sign-z −17.4) — and (P2) the measurement-methodology corpus (deck pairing, band
registries, the measured 1.8–2.2× cross-band over-dispersion with an identity control, the
~50% false-negative rate among underpowered kills and its "instrument, not n" lesson).
Neither needs a human anchor. The conditional third (P3) is Carcassonne game science (luck
floor 6.25%, self-churn ~30%, budget knee, the leaf-knockout ablation running tonight) —
publishable only after the walled-variant issue (67.8% of games touched an invisible board
edge; commit `b7d61ab`) is remediated or sensitivity-bounded, and it is the paper the
original prompt predicted.

**Calibration, honestly:** the empirical core and experimental hygiene are at or above PhD-
dissertation standard and above common practice in industrial labs; the *scope* (one game,
one rule set, in-ecosystem elo, ≤10M-param nets, hobby compute) is what keeps this from
being a lab-scale result. "Superhuman" is not claimable and should not appear in any
manuscript. Recommended posture: stop chasing strength (as Joshua intends), spend the next
90 days converting the record into P1 → P2 → analyzer/E4 (which feeds P3 and is the
project's original win condition).

---

## 2. How advanced is this project? (level assessment)

### 2.1 Against a Masters thesis
**Far above.** The field's existing theses on this exact game — Heeringa & Steyvers 2009
(Maastricht, classical features) and Jappert 2022 (Basel, UCT tuning), both cited in the
[original prompt](../ORIGINAL_PROMPT.md) — are each smaller than single *sub-programs* here
(e.g., the C5 leaf re-tune arc alone, CL-051, is a complete tuned-and-confirmed study with
pre-registration and a fair/clairvoyant split). A Masters student who produced just the
Level-2/exact-solver evaluation suite ([LEVEL2_L23_VERDICT.md](../../measurement/level2/LEVEL2_L23_VERDICT.md))
would graduate comfortably.

### 2.2 Against a PhD dissertation
**Comparable in volume and rigor to the empirical core of a solid dissertation; missing the
chapters that make a dissertation defensible.** What exists maps to 3–4 strong chapters:
measurement methodology (P2), the learned-evaluation negative result (P1), game science
(P3), and systems (k-parallel/ANE). The claim registry's falsifier discipline and the two
self-audits ([BURIED_CAVEATS_AUDIT_20260730.md](BURIED_CAVEATS_AUDIT_20260730.md),
[FALSE_NEGATIVE_SWEEP_20260730.md](FALSE_NEGATIVE_SWEEP_20260730.md)) exceed what most
committees ever see. What is missing: (a) **related-work positioning** — almost no
engagement with the literature exists anywhere in the tree (comparison training goes back
to Tesauro 1989; ranking-vs-regression for evaluation functions has a literature; NNUE and
pre-NNUE Stockfish are the obvious frame for "hand-crafted leaf beats learned value at
shallow-search move ordering"); (b) **external validity** — every elo is in-ecosystem
(§5.3); (c) **generality** — one game, one rule set, and technically a non-canonical
variant (§5.1). As a dissertation it is ~"results chapters done, introduction, related
work, and external-validation chapter unwritten."

### 2.3 Against a commercial lab (DeepMind-style games team)
**The experimental governance is above typical industrial practice; the compute and model
scale are ~3 orders of magnitude below it, and the conclusions are honestly scale-bounded.**
A serious lab would recognize: pre-registration actually adhered to (preregs committed
before first game, e.g. `f2e11ca`, `f6a6ff9`); an identity control that prices the noise
floor (the [cliff ladder](../../measurement/classical_search/CLIFF_LADDER_88E9_READOUT_20260729.md));
a measured over-dispersion phenomenon most eval pipelines never notice; and a champion
promotion (CL-071) resting on exactly the robust statistical class. They would also note:
nets ≤10M params (CL-064's capacity ladder tops at ~10M), self-play corpora of 2,400–3,600
games where AlphaZero used millions (CL-066 says this itself: "compute-bounded null"), and
a strength outcome — classical PIMC search over a hand-tuned leaf, learned value inert,
learned policy priors real at equal sims but bought back by the clock (CL-067) — that a
games team would read as consistent with the pre-NNUE era rather than a challenge to it.
The piece a lab would actually want is P2's pathology catalog and P1's mechanism, not the
bot. Fair one-line summary: **a rigorous, well-governed solo research sprint that produced
two publishable findings and a strong hobby-grade engine — not a lab-scale result, and the
record never pretends otherwise.**

---

## 3. Paper portfolio

| # | Paper | Core claim | Readiness | Venue (in order) | Human anchor needed? |
|---|---|---|---|---|---|
| P1 | **Outcome prediction ≠ move discrimination** (negative result + mechanism) | No learned value beats the hand-crafted leaf at sibling move-ranking, across targets/capacity/representation/tabula-rasa/strongest-corpus; the failure is discrimination, not prediction | **~85%** — evidence complete; lit review + framing missing | arXiv → IEEE Trans. on Games; CoG fallback | No |
| P2 | **Trustworthy self-play evaluation on hobby compute** (methodology) | Deck pairing, band registry, identity controls, cross-band over-dispersion 1.8–2.2×, false-negative audit ("the instrument, not n") | **~75%** — evidence complete; mechanism open; lit review missing | arXiv → IEEE ToG or CoG | No |
| P3 | **Carcassonne game science** (luck floor, decision density, budget knee, leaf ablation, folk claims) | Quantified skill/luck structure of 2p Base+Farmers + the relative value of strategic concepts | **~40%** — key inputs exist; walled-variant remediation + Track A folk-claims study outstanding | CoG + community writeup (BGG/r/Carcassonne) | Partially (for human-contrast rows only) |
| P4 | Exact-solver-grounded evaluation + clairvoyance tax | K≤2 marginalized solver as non-circular ruler; endgame skill decoupled from full-game elo; ~120–156 elo persistent tax | Section-of-P1/P2 or workshop note | CoG workshop / arXiv note | No |
| P5 | Systems: k-parallel PIMC (6.37×, behavior-identical), ANE batch-1 tax deletion, DRAM wall | Engineering, not science | Blog post / short paper at most | Blog; CoG short if desired | No |
| P6 | The meta-paper: an AI-agent-executed research program with governance | Case study (claim registry, prereg, self-audits, ~3 months) | Optional; Joshua's comfort decides | Blog / agents-workshop | No |

**Answer to "how many papers": two now (P1, P2), three if the 90-day program below runs (add
P3). P4–P6 should be folded in or published as non-academic writeups — publishing them
separately would be salami-slicing and would weaken P1/P2.**

### P1 — "Outcome prediction is not move discrimination" (rank 1)

**What exists** (all in [CLAIM_REGISTRY.csv](../../governance/CLAIM_REGISTRY.csv); cite the
kill set, not CL-010, per CLAUDE.md):
- **CL-039/CL-042** — the scoped route closure across scalar/structured/clairvoyant/fair
  targets, with the honest "reopening, not death" autopsy arc.
- **CL-064** — capacity is not the constraint: 386K→10M params, solver-ruler tau 0.133 →
  0.083 (vs leaf 0.615), pre-registered DEAD gate satisfied.
- **CL-065** — representation-independence: handed the leaf's *own* union-find features and
  exact-solver labels, no learner beats the leaf's ordering (best held-out tau 0.386 vs
  0.615; free re-weighting of the leaf's own 4 terms only ties, 0.6157).
- **CL-066** — tabula-rasa flatline at this compute scale (12 iters × 300 games; best
  gap-closure 43% vs 50% bar), explicitly a compute-bounded null.
- **CL-073** ([READOUT](../../measurement/value_unlock_20260730/READOUT.md)) — the mechanism,
  on the strongest corpus the project can produce (2,400 games / 345K rows at the 11008
  champion budget): held-out value↔outcome r = 0.6795, *above* both its parent (0.6564) and
  the 0.61 heuristic reference — and solver regret 1.995 vs the leaf's 0.951, top-1 0.067 vs
  0.610, tau 0.019 vs 0.615, paired sign-z −17.43 on 1,119 exact-solver roots.
- **The depth-conditional ladder** (CL-010's one durable artifact): the same learned
  champion reads +40.1 / +24.4 / −28.7 vs matched-leaf heuristic search at 800/1600/3200
  sims — "beats the heuristic" claims reverse as the opponent deepens.
- **Positive controls that defend the instrument:** the same apparatus *does* detect learned
  wins where they exist — policy-prior distillation (CL-067: +42.8 and +28.7 on disjoint
  bands at equal sims) and a leaf tune (CL-051: +48.8 fair, z 3.13). The value nulls are not
  a blind ruler. CL-072 (net at deploy budget vs its 4×-budget corpus teacher, −20.9 ± 17.4,
  extension pending) completes the deployment picture.

**What's missing:** (1) related work — comparison training (Tesauro), evaluation-function
learning in games (Buro, NNUE and its ancestors), learning-to-rank for search, the
AlphaZero-value-target literature; the project's own LTR history (CL-034/CL-037: positive
offline, never converts through search — see [LEVER_INDEX.md](../LEVER_INDEX.md) item 6) is
itself a finding to report; (2) a framing decision — this must be written as a *mechanism*
paper (prediction ≠ discrimination, with the tanh/±2 F13 side-story resolved empirically in
the READOUT), not as "we failed at AlphaZero"; (3) optionally, one bounded modern-
architecture control (a transformer-style ranker at the same data budget) to blunt the
predictable referee objection — CL-064 answers capacity, not architecture family.

**Estimated additional work:** 2–4 weeks of writing; the optional control is ~1–2 box-days
plus a GPU day. **Publishable without any new measurement** if the compute-bounded scope is
stated as plainly in the paper as it is in the registry.

### P2 — the measurement-methodology corpus (rank 2, most transferable)

**What exists:**
- **Deck pairing / CRN** as the standing variance-halving design; n-threshold discipline
  (n=400 paired ≈ ±12 elo) in CLAUDE.md's results-discipline block.
- **Band registry + burn discipline** ([BAND_REGISTRY.csv](../../governance/BAND_REGISTRY.csv)),
  and the headline finding: **cross-band over-dispersion, measured** — the same config reads
  +0.9 / −53.4 / +20.9 elo on three bands (sd 38.45 vs nominal 17.5 = 2.20× on elo, 1.83× on
  the margin), the "different decks" explanation arithmetically excluded, harness exonerated
  by an **identity control** (candidate byte-identical to opponent ⇒ true value exactly 0)
  ([CLIFF_LADDER_88E9_READOUT_20260729.md](../../measurement/classical_search/CLIFF_LADDER_88E9_READOUT_20260729.md)).
- **The false-negative reservoir audit** ([FALSE_NEGATIVE_SWEEP_20260730.md](FALSE_NEGATIVE_SWEEP_20260730.md)
  + LEVER_INDEX §0): kill error rate measured ~50% twice among underpowered kills; the
  decisive defect was **the instrument, not the sample size** in every examined case; the
  single densest instance (meeple_K killed at n=20, later worth +179.5 ± 27.9 elo and the
  founding term of the production leaf lineage) is a memorable, teachable case.
- **The clean-ruler audit** ([CLEAN_EVAL_AUDIT.md](../../clean_eval/CLEAN_EVAL_AUDIT.md)):
  two structural evaluator defects (R1/R7), runtime-verified provenance, 11 semantic
  contracts, and the re-adjudication of every prior claim under the clean ruler.
- **Ruler pathologies:** saturation refuted then re-found as depth-conditionality (L2-1/L2-2);
  sims-washout (net gains vanish under deep search); the out-of-lineage anchor's measured
  ceiling (RoD-v2 mis-orders a +50 contrast by ~70 elo *including the sign* — CL-070's
  amendment); elo-compression vs fixed opponents and the move-agreement probe with a
  same-budget reseed null ([MOVE_AGREEMENT_PREREG.md](../../measurement/classical_search/MOVE_AGREEMENT_PREREG.md)).
- **Winner's-curse discipline** (selecting cell excluded from pools; the it16 "+88.7" crest
  refuted by pre-registered fresh-deck extension).

**What's missing:** (1) the over-dispersion **mechanism** is enumerated-not-adjudicated —
either fund the systematic look (~a few box-days) or frame it as a measured open problem
(defensible; the practice rule "inflate σ 1.5–2× cross-band, prefer within-band pairing" is
the actionable contribution either way); (2) positioning against the chess-engine testing
ecosystem (SPRT/fishtest, paired openings in computer chess — deck pairing is the
stochastic-game analog) and against variance-reduction literature; (3) a generality
argument (everything is one game — the honest claim is "a case study with transferable
instruments," which is enough for ToG/CoG).

**Estimated additional work:** 3–5 weeks of writing; mechanism study optional.

### P3 — Carcassonne game science (conditional; the paper the original prompt predicted)

[ORIGINAL_PROMPT.md](../ORIGINAL_PROMPT.md) Phase 6: *"This is the phase that could plausibly
become an arXiv preprint or IEEE CoG paper."* That prediction was right — and this is the
one paper materially damaged by the border bug (§5.1).

**What exists:** luck floor 6.25% pooled [4.27, 9.06] (champ-vs-greedy, deck-paired,
replicated on a second band and platform; [LUCK_FLOOR.md](../../measurement/human_anchor/LUCK_FLOOR.md));
decision density / self-churn (CL-070: the champion self-disagrees 26–30% at fixed budget,
44.9% in the narrow-gap stratum; budget's own contribution to move change is only ~4pp,
z 6.72); the budget-elo curve (steep rise 688→1376, z +4.85 within-band; flat 2752→5504;
+49.85 z 3.48 for 11008; marginal value of width collapsing 13.5× above 11008 —
[KWIDTH_22016_READOUT_20260729.md](../../measurement/classical_search/KWIDTH_22016_READOUT_20260729.md));
the persistent ~120–156 elo clairvoyance tax that does not close with search
([CLAIRVOYANCE_GAP_VERDICT.md](../../measurement/clairvoyance/CLAIRVOYANCE_GAP_VERDICT.md),
roadmap D0/CL-048); endgame-skill decoupling (the full-game elo champion was the *worst* of
six agents at exact-solver endgame top-1); the **leaf-component knockout ablation**
([PREREG.md](../../measurement/leaf_ablation_20260730/PREREG.md), running tonight) — the
"relative value of strategic concepts" table, i.e., Phase 6's flagship exhibit; and the
descriptive-stats catalog + folk-claims machinery chartered in [BACKLOG.md](../../BACKLOG.md)
(2026-07-30).

**What's missing:** (1) **walled-variant remediation** — these are claims about *Carcassonne*,
and the engine measured a variant (§5.1); headline stats need re-measurement or sensitivity
bounds on the recentred engine; (2) **Track A folk claims** — the ~15–20 paired-constraint
verdicts the original prompt specified were never run (the instruments all exist); (3) the
ablation readout; (4) optionally the E4 human-vs-champion descriptive contrasts (needs E4
volume; n=2 archived games today).

**Estimated additional work:** 2–3 months elapsed including compute windows; the single
biggest item is the post-fix re-baseline, which the project would want anyway for the app.

### P4–P6 — satellites
- **P4 (solver-grounded eval + clairvoyance tax):** genuinely nice instruments (K≤2
  marginalized solver as a non-circular ruler; sibling-regret; the PIMC/determinization
  angle connects to the ISMCTS/PIMC literature) but thin as a standalone paper — fold into
  P1 (ruler) and P2 (methodology), or write as a workshop note.
- **P5 (systems):** the k-parallel determinization split (6.37× at k8×1376, behavior-
  identical with a paired action-and-root-stats proof, [EFFJENSEN_BENCH_BATCH_20260729.md](../../measurement/EFFJENSEN_BENCH_BATCH_20260729.md))
  and the ANE batch-1 result (0.42 ms fp16 on-NPU vs 2.6 ms torch-CPU; Pixel NPU
  unreachable) are solid engineering notes. Root parallelism and NPU deployment are not
  novel research; a blog post (or the [EFF_POSTMORTEMS_2026-07.md](../EFF_POSTMORTEMS_2026-07.md)
  expanded) serves them best.
- **P6 (the meta-paper):** the governance spine — claim registry with falsifiers, evidence
  epochs, pre-registration compliance, two same-day-actioned self-audits, largely executed
  by AI agents under human direction — is, candidly, the most *unusual* artifact here, and
  there is appetite in the agents/AI-for-science community for honest case studies. It is
  also personal (workflow, family project). Entirely Joshua's call; a blog post captures
  most of the value at none of the exposure.

---

## 4. Publish now, or do more work first?

**Per paper:**

- **P1 — publish-track now.** No new measurement is required. The evidence chain is closed,
  pre-registered, and internally replicated; the missing work is scholarship (lit review,
  framing) not science. The optional architecture control is worth ~1 referee objection.
  Sequence: arXiv preprint when written; then IEEE ToG (journal, rolling) — the result is
  more journal-shaped than conference-shaped because its strength is the closure ladder.
- **P2 — publish-track now, one open question declared.** Publishable with over-dispersion
  as a measured open problem; stronger with a mechanism adjudication. Do not gate on the
  mechanism — the identity-control instrument and the practice rules are the contribution.
- **P3 — more work first, categorically.** Without the border remediation its headline
  claims are about an undisclosed variant; with remediation it is a clean CoG paper plus
  the community writeup the competitive scene would actually read.
- **P4/P5/P6 — no urgency;** fold in or blog at leisure.

**The external-anchor question, head-on.** The project has **no external human anchor**:
Tier-1 references are saturated; elo is self-anchored within one ecosystem; the only
out-of-lineage bot anchors were sub-greedy (S2 scoping) or measurably unreliable above
their tier (RoD-v2, CL-070 amendment); E4 human play consists of **3 phone games (0–3),
2 archived** (commits `acb107d`, STATUS 2026-07-30), against the *carved-out* k4×688 phone
budget, by one related, untitled player. The
[tournament memo](../../measurement/TOURNAMENT_LANDSCAPE_MEMO_20260728.md) shows no cheap
fix: WC is an exact scope match but there is no duplicate-deck play anywhere, BGA's ToS is
closed to bots, and prize money is zero — so a credible human calibration requires an
*arranged* exam (the memo's regret-exam + pro-match sequence).

What this means per paper: **P1 and P2 do not need the anchor** — their claims are
internal-comparative (learned-vs-heuristic under identical search; instrument behavior),
and solver-grounded where absolute. **P3 needs it only for its human-contrast rows**; the
game-science core (luck floor, churn, budget structure, ablation) is anchor-free.
**No paper should contain the word "superhuman," and none needs it.** The honest published
strength sentence is: "a classical PIMC agent, measured within its own ecosystem with the
following instruments and pathologies, with a 6.25% deck-luck floor against a greedy
baseline." If Joshua wants a human-anchored strength claim *ever*, that is a separate
funded project (the E4 arc), and it should be driven by the analyzer/coach goals — not
resurrected strength-chasing.

---

## 5. Threats to validity a reviewer will raise (and what to do)

1. **The walled variant (the big one).** The vendored engine's start tile sits at
   `Coordinate(6, 15)` on a 35×35 grid — 6 rows of headroom above vs 28 below — so
   rule-legal placements above row 0 were silently never offered: **67.8% of games had ≥1
   denied placement, 21.7% of tile plies, 2.6% of all legal placements, 100% of denials on
   one side, 0 forced passes** (commit `b7d61ab`, 400-game paired diagnosis; found by
   Joshua *playing the app*, 2026-07-30). Every self-play game, training corpus, and eval
   ever run lived inside this wall. Mitigations that hold: it is symmetric between players,
   so **all paired contrasts (the entire kill set, the promotions, the methodology results)
   remain internally valid** — both arms played the same variant. What does not hold:
   any claim phrased as being about canonical Carcassonne, and any absolute game-science
   statistic (P3). **Action: disclose in every manuscript; fix the engine (even-shift
   recentring, per the commit's analysis) as a governed evidence-epoch boundary; re-measure
   or sensitivity-bound P3's headline stats.** For P1/P2 this is a limitations paragraph,
   not a wound — but only if disclosed proactively.
2. **Vendored-engine provenance.** The engine is a patched fork of an unmaintained repo,
   and the project *itself* found a farm-scoring correctness bug mid-flight (the
   `TRT→BRB` involution fix, DECISIONS 2026-05-29) plus two known rules-fidelity
   divergences deliberately parked (fixed start tile; WC tie rule — BACKLOG 2026-07-28).
   A reviewer will ask "why should I trust the rules?" **Action: a rule-conformance test
   suite against canonical scoring examples, cited in the papers** (much of this exists in
   tests; it needs to be presented as such).
3. **Self-anchored elo.** All elo is within one ecosystem; the one out-of-lineage anchor
   mis-orders contrasts above its tier including the sign. The defense is that the program
   *knows* this (it is structural blocker #1, [MEASUREMENT_FIRST_SPEC](../MEASUREMENT_FIRST_SPEC_2026-06-18.md))
   and the papers' claims are comparative or solver-grounded. State it; never quote an
   absolute elo without its ruler.
4. **Cross-band over-dispersion is unexplained.** A reviewer can ask whether *any* error
   bar is honest. The answer is the identity control: within-band deck-paired contrasts are
   the defended class, the promotion rests on that class, and cross-band σ gets the 1.5–2×
   inflation rule. This is P2's own subject matter — in P1, apply the rule visibly.
5. **Multiplicity / garden of forking paths.** Dozens of screens ran. Defenses that exist
   and should be foregrounded: pre-registration before first game, screen-vs-confirm
   separation, selecting-cell exclusion from pools, the documented winner's-curse
   refutations, and the false-negative audit cutting the *other* way.
6. **"You didn't try hard enough" (scale/architecture) against P1.** CL-064 (capacity),
   CL-065 (representation), CL-066 (tabula rasa, explicitly compute-bounded) are the
   answers on record; the residual exposure is architecture family and data scale. Either
   run the bounded control or scope the claim as "at hobby scale" — both are acceptable;
   silence is not.
7. **Single-author reproducibility.** One person + AI agents, a private repo, a bespoke
   3-box cluster. The F1 release-integrity machinery (champion factory, manifests,
   deck-seed replay) is most of an artifact-evaluation package already. **Action: a public
   release cut** (engine fork is MIT; include manifests, bands, seeds, and the golden-gate
   fixtures) — this is the highest-leverage credibility purchase available, and it is
   mostly packaging work.
8. **AI-agent authorship.** Most code, analysis, and prose were produced by AI agents under
   Joshua's direction. Venues increasingly require disclosure; disclose plainly (it is also
   part of what makes P6 interesting). This is a policy exposure to check per-venue, not a
   scientific one.

---

## 6. Recommended 90-day sequence (given "stop chasing strength")

No new strength levers; compute only where it serves publication or the analyzer. Every
run below is Joshua's spend call — this is a proposed order, not a queue.

- **Days 1–7 — close the open loops that are already paid for.** Land the leaf-ablation
  readout (running tonight; it is P3's flagship table). Decide CL-072's disposition on
  *stop-chasing-strength* grounds: recommend **bank the lean, leave Provisional** — the
  n→800 extension answers a question the program no longer needs. Decide the border fix:
  recommend **approve recentring as an evidence-epoch boundary** (the governance machinery
  for exactly this exists), with old bands retired and the app carrying the fix.
- **Weeks 2–5 — write P1.** Lit review first (it will sharpen the framing), then the
  manuscript around the kill-ladder figure and the CL-073 mechanism table. Decide the
  optional architecture control after the lit review, not before. arXiv on completion.
- **Weeks 4–8 — write P2.** The identity control, the over-dispersion measurement, and the
  false-negative audit are the spine; the meeple_K story is the opener. Decide whether to
  fund the over-dispersion mechanism study (~few box-days) — it upgrades the paper but
  does not gate it. arXiv on completion.
- **Weeks 4–12, interleaved — return to the original win condition.** Analyzer/coach MVP
  (the BACKLOG 2026-07-30 charter is well-scoped, CL-070 already calibrates the blunder
  thresholds), uncoached E4 accumulation on the phone, the descriptive-stats catalog, and
  Track A folk claims on the *fixed* engine. This is simultaneously: the project's original
  purpose, the E4 data P3 wants, and the family payoff.
- **Weeks 8–13 — P3 assembly begins** (post-fix sensitivity re-runs → luck floor and one
  within-band contrast first), targeting IEEE CoG 2027 (deadline historically ~Jan–Feb)
  with the community writeup released alongside.
- **Throughout:** the public release cut (§5.7) whenever writing needs a break; Eff Hans
  stays chartered-but-parked unless P3 finishes early — it is a *second* game-science
  paper if ever executed (the DeepMind–Kramnik precedent applies, and "we accidentally ran
  a walled variant, then made variants deliberate" is an honest, charming arc).

---

## 7. Open questions only Joshua can answer

1. **Name and venue posture.** Publish under his own name, on arXiv, in his field-adjacent
   public identity? (Everything above assumes yes to arXiv + one peer-reviewed venue.)
2. **Public code release.** Is he willing to publish the repo (or a release cut)?
   Reproducibility credibility (§5.7) hangs on this more than on any experiment.
3. **Compute appetite post-pivot.** Which of the optional cells get funded: border-fix
   sensitivity re-runs (needed for P3), the P1 architecture control, the over-dispersion
   mechanism study, the CL-072 n→800 extension (recommended: no)?
4. **Does the human anchor still matter to him at all** — as science (P3's contrasts), as
   the exam the tournament memo scoped, or not anymore? "Stop chasing strength" is
   compatible with all three answers, but the papers should be framed knowing which.
5. **The kids and E4 data.** Family games feed the analyzer and P3; are those games (even
   anonymized) publishable data?
6. **AI-agent authorship disclosure** — comfortable stating it plainly in papers? And is
   P6 (the process case study) wanted at all?
7. **What is the project now?** If the answer is "an analyzer and a coach for my family,
   plus a publication record of what we learned," the sequence above serves it. If any
   strength ambition survives, say it out loud so it gets a prereg and a budget rather
   than a drift.

---

*Prepared 2026-07-31 by Claude Fable 5 (advisory). File under docs/reviews/; indexed in
[docs/INDEX.md](../INDEX.md) "Research & audits."*
