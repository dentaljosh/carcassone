# rodv3 turn 1 — pre-registration SKELETON (NOT FUNDED, NOT LAUNCHED)

> **STATUS: SKELETON, 2026-07-30 (early am).** Drafted while the gen W-sweep smokes run
> so the morning GO/NO-GO needs only throughput numbers + Joshua's word. Becomes a real
> pre-registration only when the TBD slots are filled and it is committed BEFORE any
> result exists (house rule). Roadmap: G8. Lineage name: **rodv3** ("Revenge of Demis
> v3", Joshua 2026-07-29).

## The question (one variable)

Does the sighted-flywheel lineage grow when the ONLY change from the refuted 2026-07
run is the gen budget: `NET_SIMS 200 → 688` (k4×200=800 → k4×688=2752)? The recorded
¼-budget confound (HANDOFF ½-budget floor; recipe lever 6) is the thing under test;
CL-067's equal-sims +35.7 ± 12.3 supplies the missing premise (operator > teacher at
2752).

## Arms

- **Arm A (primary): recipe-identical, full-budget gen.** All 7 recipe levers held;
  severed value (frozen curve125 leaf); only the gen budget changes. One variable.
- **Arm B (optional, Joshua's call): + stage-3 value-unlock** — the recipe record's
  own "sharpest restart bet" (lever 1). If funded alongside A, arms are 2 variables
  apart from history but 1 apart from each other; A-vs-B isolates the value channel
  at full budget. If only one arm is funded, fund A (clean resolution of the recorded
  confound beats a new combination).

## Fixed choices (carried from the decided record — do not relitigate at launch)

- Start net: **CL-067 `distill_strong_20260723/ckpt/iter_03.pt`** (modern, fair-trained).
  NOT rod_v2 (decided 2026-07-29: same cost, clairvoyant-trained, −105.6 vs blind
  champion at half budget, and iter_02 is the frozen anchor).
- Gen: fair (blind PIMC), sighted 81ch/42 rep, pooled root-visit policy targets,
  batch 16, exact endgame K≤2, leaf = curve125 (hash dialects: eval `a36d2e15` ≡ gen
  `6dfffd57` per PRODUCTION.yaml — verified 2026-07-29).
- Trainer: the flywheel trainer as-is (window semantics TBD below), warm from iter_03.
- W per box: **the settled W\* from the 2026-07-29/30 smokes** (crude→refine→settle-low
  protocol), never the crude argmax.

## Gate (pre-committed 2026-07-29, before any smoke result)

- **Primary: candidate(turn 1) vs its OWN PARENT (the CL-067 net) at DEPTH (k4×688),
  n=400 deck-paired, FRESH band** (claim via share manifests + BAND_CLAIMS). POC bar =
  positive derivative, NOT champion supremacy. Branches:
  - **ALIVE:** elo ≥ +2σ AND margin sign agrees → fund turn 2 (same prereg, next band).
  - **DEAD:** both statistics ≤ 0 or sign-split at |z|<1 → lever 6 resolved NEGATIVE;
    the ¼-budget confound was not the limiter; lever 1 (value sever) becomes the last
    suspect; STOP (no turn 2 without a new argument).
  - **AMBIGUOUS:** anything else → ONE extension of the same cell (n→800), then verdict.
- Secondary (context, not gates): vs rod_v2 iter_02 anchor at k4×688; low-sims cell
  ONLY as a diagnostic, never citable as growth (washout law).

## TBD — filled from the smoke read-outs before launch

- games/iter (300 vs 450 vs other) and iters funded (1 vs 2) — driven by measured
  s/game at W\* per box and Joshua's wall-clock appetite.
- fleet composition: local-only vs +laptop vs +Air (each arm's games/h and the Air's
  no-orch/batch-1 shape caveat).
- gen wall-clock ETA (+25% if the Air participates) and the watchdog arming
  (run_watchdog.sh on every box with a detached cell — the 2026-07-28 lesson).
- whether LEVER_INDEX item 12 (batch the k dets into ONE request) is worth building
  FIRST: the W12 smoke showed ~40% of worker time is round-trip wait; a ~4× cut in
  sequential round-trips may halve the iter cost. Engineering-before-science call.

## Close-out obligations (six touches + the new rule)

results.csv row(s) · DECISIONS entry · this doc's status banner · CLAIM_REGISTRY (new
CL id) · STATUS top block · roadmap G8 flip — **plus: any null ships with its confound
indexed in LEVER_INDEX the same day** (the 2026-07-29 lesson this lineage exists to
atone for).
