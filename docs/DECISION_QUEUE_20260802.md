# Joshua's open decision queue — consolidated 2026-08-02 (post-Eff-Dario)

> Everything below waits on YOU. Nothing here is queued to run without a word from you.
> Kept current until emptied; STATUS points here. (Compiled after the 2026-08-01/02
> weekend: port complete, flips landed, review rounds done.)

## Compute / funding
1. **Champ-vs-10× h2h** — ✅ READ-OUT LANDED 2026-08-02
   ([KWIDTH_110K_READOUT_20260802.md](../measurement/classical_search/KWIDTH_110K_READOUT_20260802.md)):
   pre-registered branch = **UNDERPOWERED/INCONCLUSIVE → default DO NOT FUND** (+19.4
   elo-equiv, 95% CI [−5.7, +44.6] vs the 25-elo bar — couldn't exclude a fundable
   effect, couldn't detect one). Your call: accept the default, or fund the overrule
   sizing (~610 deck-paired games, one seat at 10×) / a cheaper intermediate rung first.
2. **rodv3 menu** (CL-072 leaning-negative): gen@11008 discriminator — **REPRICED with
   MEASURED gen throughput (2026-08-02 gen W-sweep, production knobs k8×1376 rust): ~260
   games/h laptop-only, ~314 games/h local-only, wall-parallel both boxes ⇒ the 300-game
   gen is ~35 min (two boxes) / <1 h (either box alone)** — down from the ~4–6 h estimate
   and the 29 h python-era price. The blocking cost is now the TRAIN + eval tail, not gen.
   Menu unchanged: gen@11008 · n→800 teacher-h2h extension · or bank the lean and park.
3. **ANE n≈2150 cell** — recommendation: CLOSE UNFUNDED (the port inflated r ~8× past the
   reopen bar; STATUS 2026-08-01 note). Needs your ack to flip the claim line.
3b. **NEW — the CUDA-Graph net-arm spike (~half a day, port-5 memo):** desktop torch+Graph
   at batch-8 lands cost_ratio **2.12×, inside the netprior break-even for the first time**
   (the right statistic is 0.5+r, not 1+r — netprior deletes the classical child sweep).
   The go/no-go: reach CUDA-Graph from Rust via ort IOBinding; if batch-8 ≥ ~0.18 ms, stop.
   This REOPENS (on new grounds, desktop-only) what the ANE post-mortem closed — it does
   not contradict 3: the ANE r-bar stays failed. → docs/RUST_NET_EVAL_DESIGN_20260802.md,
   LEVER_INDEX 16–17. Fund/park.
3c. **NEW — backend default flip readiness (F11 done):** all four desktop callers wired +
   injection-proven; remaining pre-flip blockers (port-3 list): (i) factory must resolve
   per-mode or clairvoyant builds raise — top item; (ii) tests/release/test_factory_manifest
   re-check; (iii) the flip moves only the 6 make_production_champion sites (the eval fleet
   rides build_fair_champion's own default). Flip when you say so.
4. **F7b farm knockout cells** — ✅ RAN 2026-08-02 (funded by your "lets do the farm knockout cells"): farm base **−142 elo** (z −9.4, verdict); farm-growth **+42.8 (z +1.87) — the champion LEANS BETTER WITHOUT it**. NEW SUB-DECISION: fund the ~15-min fresh-band n=400 CONFIRM of the farm-growth deletion (if it holds ≥2σ it is a free ~+40 elo + 4% cheaper leaf — the first positive strength lever since curve125). No leaf change until then.
5. **F9 rules-fix program** — the big one: global recentring + rules remediation
   (RULES_FIDELITY_AUDIT R1–R8) + transfer-bound cell + fixed-rules descriptives +
   the JCloisterZone oracle (BACKLOG 2026-08-02). When to fund; scope in the audit doc.
6. **Perf pass** on the review's #2–4 (+C-e/C-f riders): ~−22% RSS / −13% wall on the
   champion, all bit-identical, gated by gate re-runs. ✅ **FIRED 2026-08-02 afternoon**
   (wiring went green, not cancelled): Opus agent in an isolated worktree, per-change
   commits each gated (cargo + pytest + G3-pattern reconcile + G6-pattern 10-game
   identity). Merge happens only after orchestrator review — cancelling mid-flight just
   means not merging.
7. **Paper G2** — transformer control (~1–2 box-days + GPU day) vs scoping the claim
   "at this scale". Advisor: decide after lit review.
8. **Paper G3** — ✅ LAUNCHED 2026-08-02 (Joshua's fresh-budget go): offline decomposition
   running; lands in measurement/paper_g3_20260802/ + CLAIMS_LEDGER update.

## Publication / outreach (all parked pre-Shabbat, still parked)
9. The advisor memo's 7 questions (docs/reviews/FABLE_ADVISOR_20260731.md) + the 90-day
   sequence go/no-go; preprint timing; the no-"superhuman" phrasing rule is standing.
10. **Related-work sprint** (1–2 weeks; the paper's only unwritten load-bearing part).
    Advisor says do it FIRST. Who/when.

## Config / technical defaults
11. **Desktop backend default** — currently the SAFE form (yaml backend-of-record = rust,
    reached via opt-in; harness conversion in flight). After the wiring agent lands +
    burns in: flip `backend="auto"` to the factory default, or keep opt-in?
12. **Push** — dozens of commits on `android-app`, never pushed (standing rule). Say the
    word when you want origin updated.
13. **E4 protocol restart** — the phone now plays the champion of record on a centered
    board with the retail tile. Your games from here are the human-anchor data the
    program has wanted since E4 was named. Play when ready; archives self-label.

## What the weekend's bugs MEAN (the assessment behind the queue)

Four classes, four different consequences:

**(1) Rules-fidelity divergences** (walled board · cloister completion deferral + monk
pinned forever · unplaceable-tile turn loss · start tile · WC tie rule): all SYMMETRIC ⇒
**every relative measurement of record survives** — promotions, ablations, elo contrasts,
CL-060/071/074, the kill set. What changes: (a) absolute/descriptive claims carry the
walled-variant caveat (already the advisor's P3 gate); (b) "we play C3 with WC scoring,
every amount correct, on nonstandard geometry/procedure" is the honest one-liner; (c) the
cloister bug is a genuine **strength opportunity** — the champion permanently strands a
monk on ~10% of cloister completions, a meeple-economy leak invisible to score-based
instruments; fixing it (F9) plausibly buys real strength vs humans at canonical rules,
and re-triggers the bug-fix-shifts-optima re-sweep.

**(2) Integration/contract hazards** (stale-mirror silent-wrong, restore re-budget,
bridge chooser guard, PanicException blindness): none fired in anything recorded — the
audit/review caught them BEFORE the default flip could expose them. The lesson is
structural: **guards, not vigilance** (the 12.8 µs unconditional desync check is the
model). All routed to the wiring agent; the phone's archived E4 games predate the rust
bridge path and are clean.

**(3) Vacuous instruments** (the collide-check that cannot fire, bench-mode's false
PASS): philosophically the worst class — diagnostics that always say fine. None
invalidated a real gate (gates used different paths, and the mutation probes prove the
gates themselves CAN fail). Standing rule worth adopting: **every diagnostic needs its
own can-it-fail demonstration**, same as gates get mutation probes.

**(4) Label-not-function / provenance** (preset-leaf stamp, kwarg-vs-env guard,
hardcoded knobs, unpinned Android rustc): the recurring project disease (R1/R7 class).
All caught pre-exposure; fixes in the wiring stack. The port's provenance gaps close
with them.

**Net:** nothing measured is invalidated; one caveat class is now fully mapped with a
funded fix path (F9); one real strength lever surfaced (cloister); and the review spend
converted unknown-unknowns into a fix list before any of them cost a night of debugging.
