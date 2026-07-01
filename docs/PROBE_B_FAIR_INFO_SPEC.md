# PROBE B — FAIR-INFORMATION FLYWHEEL (the deployable regime) — 2026-06-30 (flywheel bet CLOSED 2026-07-01; B1 ships)

Pre-registered design spec for the second of two post-Gate-B AlphaZero-family probes. Read with the companion
[PROBE_A_STRUCTURED_VALUE_SPEC.md](PROBE_A_STRUCTURED_VALUE_SPEC.md), the fair-information measurement design in
[MEASUREMENT_FIRST_SPEC_2026-06-18.md](MEASUREMENT_FIRST_SPEC_2026-06-18.md), the clairvoyance-gap result
(CL-022), and the charter's abandonment criteria ([PROJECT_CHARTER.md](../PROJECT_CHARTER.md)).

> **OUTCOME — flywheel bet CLOSED on the LEDGER (2026-07-01, commit `be538a7`); B1 ships as the deployable
> artifact.** Gate zero done (`fair_isolate` leak fix, 0 stale reuse; fair-target range ADEQUATE, `451fadb`).
> The §4A fair-target diagnostic ([measurement/probe_b_4a/PROBE_B_4A_RESULTS.md](../measurement/probe_b_4a/PROBE_B_4A_RESULTS.md))
> ran full-n (n_test=1544): **all six arms inert**, and the n=150 preview's "clair non-inert" was 8-group noise.
> **§4A is DEPTH-SATURATED / inconclusive on its own** — the clean H-4A-inert test needs a non-inert clair
> baseline, but clair@800 is also inert (CL-037's α=0.05 needed the deep h6400 teacher; at play depth even
> clairvoyant targets give the value no residual over the leaf). Clairvoyance-vs-depth is **deliberately left
> unresolved, out-of-scope.** → **The flywheel bet closes NOT on this screen but on the accumulated
> value-inertness ledger** (CL-029/032/033/034/036, Gate-B CL-038, Probe-A §3A — scalar+structured on
> clairvoyant targets — plus Gate-B's offline→online mechanism; §4A only *extends* it to fair targets). The
> AZ-value route is exhausted across scalar / structured / clairvoyant / fair → **ship the analyzer** (endgame-2),
> **with B1 (the fair-info agent) as the deployable, human-anchorable deliverable** — Probe B's non-empty failure
> path. Champion / PRODUCTION.yaml / v2.7 / v2.9 UNCHANGED.

> **Status: SPEC ONLY — no implementation, no runs, no cluster spend.** Pre-registers hypotheses, gates, and
> kill criteria before any run. Nothing executes until Joshua signs off on the plan and the shared time-box (§7).

> **⚠️ MAJOR reconciliation vs the brief (verified in code 2026-06-30).** The brief's Probe-B "gate zero" — *"the
> deck order is in the state key, so determinized children merge; every fair-info number is garbage until you add
> deck-order/seed to the zobrist key"* — is **substantially stale**:
> - [`string_representation`](../src/carcassonne_ai/game_wrapper.py#L379-L438) **already excludes deck order** (keys
>   on `len(deck)` + `next_tile` only). The V5 "no-leak" property holds **by construction today**.
> - `fair_chance` is **wired and tested** ([mcts.py:518-525](../src/carcassonne_ai/mcts.py#L518-L525),
>   `tests/test_clairvoyance_wrapper.py`); CL-022 already ran with it, staying sound by `clear()`-ing the tree
>   between each of its K determinizations.
> - The brief's proposed fix — *add* deck order so children *don't* merge — is the **opposite** of what IS-MCTS
>   (B2) needs (there you *want* info-set merging).
>
> So gate-zero is **reframed** (§3): not "fix a bug," but "**pin the invariant with the V5 no-leak test AND a
> flywheel-regime leak test**; build a fix only if that test actually fails." The real residual risk lives in the
> **flywheel-gen path** (persistent tree, K=1, per-move reshuffle — rider 1), not in CL-022's clear-between config.

---

## 0. Framing (honest prior + boxing rules)

**Prior is modestly-positive-at-best**, and Probe B's strength claim is smaller than A's by construction: the
fair-info agent starts **~25–30 elo behind** the clairvoyant one (CL-022) *by design* — that gap is expected and
is **not** the question. The question is whether a **value-driven fair-info flywheel climbs** in its own regime.
Boxing rules 1–6 as in [Probe A §0](PROBE_A_STRUCTURED_VALUE_SPEC.md) apply verbatim; the ones with Probe-B
specifics:
- **Rule 4 (exceed/climb, not parity):** measured **fair-vs-fair only**, never fair-vs-clairvoyant (see §5).
- **Rule 6 (clean failure path):** even a flywheel-negative result leaves a usable deliverable — the deployable
  fair-information agent (§6). Probe B is the **only** probe whose failure still ships something.

**Do NOT respec cleanly-killed levers.** Probe B is a **search-regime + value-target** change, orthogonal to the
dead objects (scalar leaf CL-038, CL-034 reranker, CL-030/031 policy distillation, CL-035 scheduler, CL-036
GNN). It reuses the fair-chance wrapper and the clairvoyance determinizer; it does not rebuild them.

---

## 1. Hypothesis (pre-registered)

The learned value lost to a **strong clairvoyant** leaf partly *because it competed against a near-oracle that
sees the future deck*. In a **fair-information** regime — root-determinized / IS-MCTS search + **fair value
targets**, neither side seeing the future — the learned value is on equal footing and may have room to drive a
flywheel. And this agent is the **deployable** one (humans don't see the deck) and the one the Step-7 human
anchor requires, so the probe yields value even on a partial result.

**Two sub-hypotheses, sequenced:**
- **H-B1:** a K-determinization (PIMC) fair-info agent with a **fair value target** shows a *positive
  multi-iteration derivative* vs a fair heuristic-leaf baseline.
- **H-B2 (only if B1 shows signal):** an IS-MCTS agent (re-determinize per simulation) removes B1's strategy
  fusion and does at least as well.

**Null:** the fair value adds nothing over a **fair heuristic leaf** and the flywheel is flat across two bands.
Then the flywheel bet is closed — but B1 still ships as the deployable agent (§6).

---

## 2. Reuse map (verified paths)

| Piece | Path | Role in Probe B |
|---|---|---|
| Fair-chance root reshuffle | [`src/carcassonne_ai/mcts.py:506-525`](../src/carcassonne_ai/mcts.py#L506-L525) `_reshuffled_root` / `fair_chance` | the non-clairvoyant search primitive (preserve multiset, permute unseen order, keep `next_tile`). |
| Sparse transposition key | [`src/carcassonne_ai/game_wrapper.py:379-438`](../src/carcassonne_ai/game_wrapper.py#L379-L438) `string_representation` | already excludes deck order → V5 no-leak by construction (§3). |
| Clairvoyance-gap harness (CL-022) | [`scripts/clairvoyance_gap.py`](../scripts/clairvoyance_gap.py) `_choose_action` (K-loop, `clear()`, pool root visits, consensus vote) | **the B1 search wrapper** — root-determinization + K-pooling, already built. |
| Fair-info measurement design | [`docs/MEASUREMENT_FIRST_SPEC_2026-06-18.md`](MEASUREMENT_FIRST_SPEC_2026-06-18.md) §5 (V1–V7, V5 no-leak, Level-1/2) | the pre-registration frame + the V5 no-leak test spec + the ladder anchors. |
| Determinizer | the clairvoyance-gap determinization machinery (K fresh permutations of the known remaining bag) | **fair value-target labels** (determinization-averaged / chance-node), §4. |
| Wean/eval harness | [`scripts/step2_pens/train_warmstart.py`](../scripts/step2_pens/train_warmstart.py), [`eval_step2.py`](../scripts/step2_pens/eval_step2.py) | the training loop + paired-games screen, reused for fair-vs-fair. |

---

## 3. Gate zero — pin the TT invariant (reframed; cheap; owed regardless of A)

Not "fix F-B2b." The key already excludes deck order. Gate zero **pins** the invariant and probes the one place
it can still break — the flywheel-gen path.

**3a. V5 no-leak unit test (lock the existing property).** Two states differing *only* in unrevealed deck order
must hash-identical (`string_representation`). This is true today; the test **locks** it against regression
(per [MEASUREMENT_FIRST_SPEC §5](MEASUREMENT_FIRST_SPEC_2026-06-18.md) V5).

**3b. Flywheel-regime leak test (the real gate — rider 1).** CL-022 is sound because it `clear()`s the tree
between each of its K determinizations. The flywheel-gen path is **different**: a persistent tree, **K=1
`fair_chance` search per move, no `clear()` between moves**. Test that scenario directly:
- One `NeuralMCTS`, persistent `_nodes`, advance a real game move-by-move, one `fair_chance` search per move.
- **Assert:** move *t+1*'s search does **not** inherit move *t*'s determinized future through a shared interior
  node. Concretely — an interior node created under move-*t*'s reshuffled deck order, reached again at move *t+1*
  after a fresh reshuffle, must not back up values conditioned on move-*t*'s (now-counterfactual) future.
- **Instrument** the leak: run the same game with (i) persistent tree + per-move reshuffle vs (ii) clear-per-move,
  and measure divergence in root Q / chosen action. Non-trivial divergence attributable to stale-future reuse = leak.

**Pass/fail & the fix menu (only if 3b leaks):**
- **PASS (no material leak):** gate zero clears **free**; B1 proceeds on the existing wrapper. Say so explicitly.
- **FAIL (leak):** the correct fix is regime-specific and is **not** "deck order in the key":
  - **B1 / PIMC:** clear or **re-root on advance** so each move's search starts from a fresh determinized subtree
    (accept the tree-reuse cost, or re-root to the played child), OR run each move's search tree-isolated. Cheapest
    correct fix; no key change.
  - **B2 / IS-MCTS:** keep the sparse key (merging is *wanted*) and add **chance-node handling** so a node's value
    is a proper expectation over determinizations rather than a biased average of whatever orders happened to descend.
- **Anti-pattern (do not do):** adding deck-order/seed to the transposition key. It breaks IS-MCTS info-set
  merging and only papers over the PIMC case that re-rooting solves correctly.

**Deliverable:** V5 test (passing), the flywheel-regime leak test + its verdict, and — only if it leaks — the
chosen regime-specific fix. This gate is owed for *any* future fair-info work, so it runs regardless of Probe A.

---

## 4. Fair value targets (charter "fair labels", pulled in)

The value **must** be trained on *fair* labels — **determinization-averaged / chance-node targets** — not
single-true-deck. Training a value on clairvoyant single-future targets and deploying it fair is a train/serve
mismatch by construction.

- **Pipeline:** for each labeled root, draw K determinizations of the known remaining bag (reuse the clairvoyance
  determinizer), run the fair search, and take the **determinization-averaged** value/target (or a chance-node
  expectation) as the label. Deck-order excluded from the key means these average cleanly.
- **Dynamic-range guard (open question 7.2):** determinization-averaged targets risk **near-zero range** (the
  residual-target problem that bit CL-036/CL-004). Pre-register a range check on the label distribution *before*
  training — if the averaged targets are near-degenerate, that is a **kill of the target design**, not a training
  failure, and must be caught at the label-build step.

---

## 4A. Fair-target value arm — the controlled Gate-B diagnostic (charter "Step 4")

A pre-registered arm, **separate from §4's flywheel labels**: train **one value head on fair
(determinization-averaged) targets instead of the single-true-deck clairvoyant targets, holding everything else
identical to the Gate-B value config** — same value-head architecture, same eval/α-sweep protocol, same 10,067
h6400_v2.9 sibling sets. **One variable changes: targets fair vs clairvoyant, nothing else.** This is a
*diagnostic on Gate-B itself*, not part of building the deployable B1 agent (that's §4/§5). It reuses the same
fair-label machinery §4 defines (the clairvoyance-harness determinizer — do **not** rebuild it).

**Two pre-registered hypotheses, each with a metric, an n, and a branch:**

**H-4A-inert — does Gate-B's "value is inert" survive fair targets?** (the potential **fourth nail**)
- **Metric:** inert = α stays 0 in the α-sweep **and** interior-τ stays flat across search depth (the exact
  Gate-B / Step-1 protocol — same α-sweep, same interior-τ measurement).
- **n / read-out:** the Step-1 sibling-ranking n (n_test = 1544 groups); read **offline, after the fair-target head
  trains, before any in-loop** (this is an offline diagnostic, not a game screen).
- **Branch:**
  - **Inert HOLDS on fair targets** (α≈0, τ flat) → **FOURTH NAIL**: Gate-B was *not* a clairvoyance artifact, the
    scalar-value-leaf ceiling conclusion **strengthens**. B1 continues as a *deployable-only* artifact; the
    flywheel bet is weaker.
  - **Inert BREAKS on fair targets** (α>0, τ rises) → part of Gate-B was a **clairvoyance artifact**; the
    conclusion **changes** — the fair-info regime has room the clairvoyant regime hid → strengthens the B1 in-loop
    case (and would warrant revisiting the Gate-B verdict's scope).

**H-4A-bag — does the bag-composition input's contribution GROW under fair targets?**
- **Mechanism under test:** clairvoyant targets may **suppress** bag reasoning — the teacher already *sees* the
  closures the bag would predict, so the bag counter has no gradient. Fair targets (teacher blind to the future
  deck) should **restore** the gradient — *if* the mechanism is clairvoyance-suppression rather than the CL-037
  finding of genuine heuristic-closure redundancy.
- **Metric:** bag-contribution = the **ablation delta** (offline regret improvement) **with vs without the 32-dim
  bag histogram**, measured **under fair targets**, compared to the same ablation delta **under clairvoyant
  targets** (CL-037's bag-only −19.7% is the clairvoyant reference on the same sibling sets). Same n_test=1544.
- **Branch:**
  - **Bag-contribution GROWS under fair targets** (fair bag-delta materially exceeds the clairvoyant bag-delta) →
    the CL-037 redundancy was **partly a clairvoyance artifact**; bag reasoning has a real fair-target gradient →
    the fair-info agent should carry the bag input prominently.
  - **Bag-contribution DOES NOT grow** → the redundancy is **genuine heuristic-closure redundancy**, not
    clairvoyance-suppression — the CL-037 conclusion is regime-invariant.

**Why this is NOT a repeat of the Step-0 determinization check.** Step 0 (per Joshua's framing — the exact
DECISIONS/charter line was not pinned in this pass; verify the citation before finalizing) ran a **hygiene** check
and found determinization **noise** "secondary, not binding" — i.e. *does injecting determinization noise perturb
the existing pipeline*. This arm is the **stronger, different** test: a full value-head **retrain on fair
(determinization-averaged) TARGETS** — a target-distribution swap, not a noise-robustness probe. Step 0 asked
"does det. noise break things"; §4A asks "does training the value on *fair targets* change the inert verdict and
revive bag reasoning." They differ in what's varied (noise-in-pipeline vs target-distribution) and in strength
(hygiene vs full retrain).

**Relationship to §4 / Probe A (not duplication).** §4 builds fair labels for the **deployable B1 agent**; §4A
uses the *same* fair-label machinery for a **controlled diagnostic on Gate-B's inert conclusion + bag reasoning**.
And it does not duplicate Probe A's farm/bag independence gate (PROBE_A §3A): there the variable is
scalar-vs-structured head on **clairvoyant** targets; here it is fair-vs-clairvoyant **targets** on the
**same-arch** (Gate-B) head. Orthogonal one-variable comparisons.

---

## 5. B1 / B2 designs + what "success" measures

**B1 — root-determinization / PIMC (built; reuse `clairvoyance_gap.py`).** K≈8–16 fresh permutations of the known
remaining bag per move; run the existing search per determinization; pool root visit counts; play consensus. Mild
strategy fusion (acknowledge it — symmetric one-tile-per-turn hidden info, no opponent-belief state, so fusion is
"mild" per the measurement spec's tractability argument). Train/serve the **fair value target** (§4) as the leaf.

**B2 — IS-MCTS (scope only; sequence AFTER B1 shows signal).** One info-set tree, re-determinize per simulation;
sounder, kills most strategy fusion; bigger build (needs the chance-node handling from §3). **Do not build B2
first.** It is designed here so B1's result can trigger it, not so it runs in parallel.

**Strength measurement (rule 4, sharpened):**
- **fair-vs-fair only.** The strength claim is the fair agent (learned value) vs the fair **heuristic-leaf**
  baseline, both non-clairvoyant, both K-determinized identically. **Never** fair-vs-clairvoyant for the strength
  claim (the ~25–30 elo CL-022 gap is expected and off-question).
- Paired games (deck both seats), fresh seed bands, n pre-registered to the effect (n=400 paired → ±12 elo; the
  climb signal is a *derivative* across ≥2 bands, so size each band to resolve a per-iter step, not a single ±20).

---

## 6. Pre-registered success / kill (+ the non-empty failure path)

**Read-out:** pre-committed at the fair-vs-fair derivative across **two fresh bands** (Step-2 kill-window: no kill
on a scary early band, no resurrection on a hopeful first band). Measured at the sims the value actually drives
(low-sims; the sims-washout trap applies here too).

- **SUCCESS:** a value-driven fair-info flywheel shows a **positive multi-iteration derivative** vs the fair
  heuristic-leaf baseline on fresh bands (the learned value earns its place in the fair regime) — **and/or** B1 is
  delivered as a clean, deployable, human-anchorable fair-info agent.
- **KILL:** fair value adds nothing over the fair heuristic leaf **and** the flywheel is flat across two bands →
  fair-info does not unlock the value either; the **flywheel bet is closed.**

**Deployability payoff (state explicitly — rule 6).** Even on a flywheel-negative result, **B1 ships** as the
fair-information agent that (a) is what we would actually run vs humans, and (b) is required for the Step-7
human/bot anchor. So Probe B's failure still leaves a usable artifact — unlike Probe A, whose kill routes
straight to the analyzer. If **both** A and B fail their flywheel/exceed gates, the AZ-family value route is
exhausted across **scalar, structured, clairvoyant, and fair-info** — a clean, publishable "we truly exhausted
AlphaZero" result — and we **ship the analyzer** (endgame-2), now with both a sighted value head *and* a
deployable fair-info agent in hand.

---

## 7. Time-box (inside the shared ~10-day single-attempt envelope with Probe A)

Same envelope note as [Probe A §7](PROBE_A_STRUCTURED_VALUE_SPEC.md): ratified "1 attempt / ≤10 days" relaxed
2026-06-08, no fresh numeric budget post-Gate-B; A+B boxed as one ~10-day single-attempt envelope.

| Stage | Budget | Notes |
|---|---|---|
| Gate zero (V5 + flywheel leak test) | ~0.5–1 day | **owed regardless of A**; front-loaded |
| Fair value-target pipeline + range guard | ~1 day | reuse determinizer; kill early if range degenerate |
| Offline fair-vs-fair value screen | ~1.5 days | parallel with Probe A's additive screen |
| B1 in-loop flywheel (only if offline passes) | ~4–6 days | derivative across 2 bands |
| B2 IS-MCTS | **not budgeted here** | triggered only by a B1 signal; separate budget decision |

**Envelope trigger (rider 2):** in-loop budget goes to **at most one probe**. If both A and B clear their offline
pre-gates, that is an **explicit budget decision for Joshua**, not a silent overrun (Probe A is sequenced first).
No cluster spend before sign-off.

---

## 8. Open questions the build must resolve

1. **K for B1** — cost vs strategy-fusion tradeoff. Propose K≈8–16; pre-register the sweep and the cost ceiling.
2. **Determinization-averaged target dynamic range** — do fair labels have enough range to train against, or do
   they collapse toward zero (the residual-target problem)? Range check is a §4 gate.
3. **Is B2 worth the build** given B1's strategy fusion is "mild" here (symmetric one-tile hidden info, no
   opponent-belief state)? Default: build B2 only if B1 shows signal *and* a fusion diagnostic says fusion is
   material.
4. **Flywheel-gen leak** (§3b) — does the persistent-tree K=1 path actually leak, and if so is re-rooting on
   advance cheap enough to keep tree-reuse worthwhile, or is clear-per-move acceptable at these sims?
