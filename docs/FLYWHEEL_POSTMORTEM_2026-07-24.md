# The learned-component ("flywheel") program — POST-MORTEM

**Status: DRAFT, 2026-07-24.** Written while az_zero's final iterations run; its formal PREREG read
lands tonight and the verdict section will be stamped then. Everything else is settled evidence.
Champion / `governance/PRODUCTION.yaml` untouched by any of this.

**Scope.** The program that ran 2026-04 → 2026-07 asking: *can a learned network become the source
of playing strength in Carcassonne?* This covers the value head, the policy head, and the
self-improvement loop that was supposed to compound them. It does not cover the classical search
program (alive) or the analyzer (never started).

---

## 1. The claim, and its fate

`CL-011 — "the system demonstrates an AlphaZero flywheel (compounding self-improvement)"` —
**Disfavored (2026-07-24)**. Three independent attempts, three nulls: the residual flywheel
(+4.8/iter, within noise and ~3× short of its charter bar), the sighted distill flywheel (CL-058 —
the it16 "+88.7 breakout" was a winner's-curse noise crest; −3.5 on a fresh deck band), and the
tabula-rasa arm (az_zero, this file's §4).

## 2. What was tried (full list: `docs/LEVER_INDEX.md`, 165 rows)

Compressed chronology of the *value* line, which is where the program lived and died:

| when | arm | outcome |
|---|---|---|
| 2026-05 | v1–v6 recipes, NN-value leaf | plateaued; superseded by the v2.7 heuristic leaf |
| 2026-05-31 | **Path B** — 24 iters × 600 games, ownership aux on | held-out value corr **0.38 → 0.81**, beating the heuristic's 0.61 — and the value-in-leaf A/B still **hurt** (→ CL-039/042) |
| 2026-06-01 | anchor-fraction (opponent mixing) | +39 elo **overturned** by the ladder → tie |
| 2026-06-04 | search-value targets (`search_value`) | fixed overfitting (corr 0.29 → 0.47); no strength |
| 2026-06-05 | interior/tree targets (`search_value_tree`) | "one-shot is **not enough**" |
| 2026-06-05 | **STEP A / B.0** — decision-ranking probes | **the diagnosis** (§3) |
| 2026-06-05/06 | **STEP B.1** — listwise ranking loss, 6 configs | "**HELPS but INSUFFICIENT**" — no config reached positive marginal |
| 2026-06-06+ | residual (predict leaf + Δ) | first *positive* marginal learned value; became champion for one epoch; did not compound |
| 2026-07-03 | M2 / deck-aware value | REFUTED (CL-049/050) |
| 2026-07-19 | sighted distill flywheel | stage-1 distillation **faithful** (tied champion 100-100-0); **growth refuted** (CL-058) |
| 2026-07-23 | Gate-C learnability probe (C0) | **DEAD** (CL-065) — learned ordering 0.386 vs the leaf's 0.615, from exact-solver labels |
| 2026-07-24 | **az_zero** tabula rasa | §4 |

## 3. Why it failed — the mechanism

Four findings compose into one explanation. None of them is "the net wasn't big enough" or "we
didn't train long enough."

**(a) Value *accuracy* saturates, and saturates early.** Held-out outcome correlation tops out
around **0.81** (Path B's S-curve plateaued there). That ceiling is a property of *Carcassonne* —
tile-draw luck means a mid-game position genuinely does not determine the final margin. No dataset
size moves it.

**(b) Accuracy is the wrong quantity anyway.** MCTS never asks "what will this game's margin be?"
It asks "which of these sibling moves is better," thousands of times per move. STEP A measured that
comparison directly: an MSE-trained value head ranks siblings at **chance (τ = 0.08)** while the
hand-crafted leaf ranks them at **0.58**. STEP B.0 then established this is the **loss form**, not
the target and not the sample size. A head can be simultaneously excellent at (a) and useless at (b)
— and Path B's 0.81-correlation head that made the agent *worse* is exactly that object.

**(c) Ranking losses help but do not close it.** STEP B.1 attacked (b) head-on and shrank the
pure-NN-leaf crater by ~250 elo without ever reaching positive marginal. Re-fired three times since
(CL-021 arm B, CL-033/037 RankNet, CL-064's capacity ladder) — always negative.

**(d) The net is distribution-bound; the leaf is not.** Measured 2026-07-24
(`measurement/az_zero_20260724/PROBE_OFFDIST_20260724.md`): a value head scores **0.906** on games
inside its training window, **0.530** on games from its own *next* policy generation, and **0.437**
on a stronger agent's games — while a neutral control net scores a flat 0.65–0.73 on all three, so
the sets are equally predictable and the collapse is the net's, not the data's. Search spends most
of its budget in hypothetical lines that no game reaches: maximally off-distribution territory. The
heuristic leaf has no such failure mode — **it is a formula, and a formula is correct in any
position it is handed.**

**The structural reading.** Go needed learned value because *Go has no formula*; that is why the
AlphaZero recipe was revolutionary there. Carcassonne's scoring is combinatorial and computable, so
a hand-crafted evaluator is genuinely strong — **we are in the chess regime, not the Go regime**,
where classical eval-plus-search was superhuman for two decades. The one case of a learned evaluator
beating an excellent hand-crafted one (Stockfish NNUE) is instructive about the price: targets drawn
from **deep-search evaluations rather than game outcomes**, at **billions of positions**, with the
resulting small net placed *inside* classical search rather than replacing it. We ran the same idea
(`search_value`) at ~6,000 games.

## 4. The tabula-rasa arm (az_zero) — the confound nobody had removed

Every kill above was measured inside a heuristic-warmstarted lineage, leaving one live objection:
*perhaps nets fail here only because they are raised in the heuristic's basin* — AlphaGo Zero's
thesis. Run 2026-07-24 from a random-init sighted net, pure self-play, no heuristic anywhere in the
loop, against a same-arch heuristic-taught anchor on deck-matched screens.

Result: **flatline.** Margin vs anchor −47.1 (it0) → −32.8 → **−27.5 (it4, peak)** → −34.6 →
−36.1 (it8); the pre-registered ALIVE bar (half the gap) became unreachable at iter 8. The random
floor was solved by iter 2 (0.98) and never converted into anything else.

The probe in §3(d) gives the mechanism, and it is worth stating precisely because it is the
generalizable lesson: **the value head's effective sample size is the number of GAMES, not
positions** — ~144 positions share one outcome label, so window-4 × 300 games is ~**1,200
independent labels** for a 7M-parameter head. It memorized them. AlphaGo hit this exact wall and
solved it by sampling *one position per game across 30 million distinct games*; the remedy requires
the scale that defines the remedy.

**So the AGZ thesis is answered for this project: the chains were not the binding constraint.**
Removing them changed nothing, and the zero-start arm hit the same wall from the other side.

## 5. What the program actually produced (the positive column)

- **Distillation is faithful.** A net *can* copy a strong policy: stage-1 tied the fair champion
  100-100-0 at production budget. Copying works; exceeding does not. This is the foundation the
  live distill-strong-teacher thread stands on.
- **The measurement apparatus.** Deck-pairing, pre-registered bars, out-of-lineage anchors, the
  clean-eval ruler, CRN seed bands. These caught at least three would-be discoveries that were
  noise (the c=3 "+47", the anchor-fraction "+39", the flywheel "+88.7"). The program's most
  reusable output is arguably its epistemics, not its nets.
- **A precise negative theory**, §3 — not "nets don't work" but *which* quantity saturates, *which*
  comparison fails, and *why* a formula beats a function approximator in this game.
- **The leaf is the moat.** Every attempt to replace it failed; the thing that reliably produces
  strength is searching it harder (the +40-elo 4× teacher, CL-060).

## 6. What this closes, and what it does not

**Closed:** learned value as a source of strength (CL-039/042/064/065 + §3); the compounding
self-improvement loop (CL-011, three attempts); the scaffolding-trap hypothesis (§4). The only
value-side lever the record does not foreclose is CL-065's own "LTR objective on the Gate-C feature
representation," which CL-065 itself calls *implausible* — it is listed in `docs/LEVER_INDEX.md`
under never-tried, not because it is promising but so that "absent" never again reads as
"unexplored."

**Not closed, and where the program's energy should go:**
1. **Distill-strong-teacher** (live, running) — the teacher is now *stronger* than deploy (+40) and
   *expensive* (4×). Distillation being faithful is exactly what makes "teacher strength at deploy
   cost" a coherent bet. Note it does not contradict §3: it copies a **policy**, and never asks a
   learned value to evaluate anything.
2. **Search allocation** — the budget curve plateaus ~+40 over deploy by 4×, with allocation
   (width vs depth) worth ~32 elo at fixed budget. Cheap, classical, and the only lever that has
   moved strength this quarter.
3. **The analyzer (Phase 5)** — the original charter's win condition, and the natural home for
   everything this program built: root values, visit distributions, and the per-determinization
   disagreement that is a native uncertainty signal for a hidden-information game.
4. **E4 / human anchor** — still the only measurement that would tell us where we actually stand.
   ⚠️ `scripts/human_anchor/play_harness.py` does not currently run the champion
   (`governance/PRODUCTION.yaml` lines 103-108) — fix before it is needed.

## 7. Process lessons

- **The docs indexed conclusions, not interventions.** On 2026-07-24 an agent proposed five "new"
  levers; four had been killed months earlier, and grep found nothing because the registry stores
  *"net value is inert"*, not *"we tried the ownership auxiliary head."* Fixed by
  `docs/LEVER_INDEX.md` (alias-keyed, includes never-tried rows). The durable version is an
  `interventions` column on `CLAIM_REGISTRY.csv` so the index becomes derivable.
- **A superseded result loses its provenance.** STEP B.1 looked untried for six weeks purely
  because a better lever arrived the next day and it never got its own CL-number.
- **Report the metric the decision needs.** The per-iter `value↔outcome corr` printed by the
  trainer is a within-window number; it was quoted all day as evidence of a crossing that
  held-out data did not support. Instrument what you will be tempted to cite.
