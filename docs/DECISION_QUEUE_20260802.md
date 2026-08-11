# Joshua's open decision queue — consolidated 2026-08-02 (post-Eff-Dario)

> Everything below waits on YOU. Nothing here is queued to run without a word from you.
> Kept current until emptied; STATUS points here. (Compiled after the 2026-08-01/02
> weekend: port complete, flips landed, review rounds done.)
>
> **📌 SWEEP 2026-08-03 (evening) — where this queue stands.** CLOSED: 1 (not funded) · 2
> (rodv3 parked) · 3b (spike STOP) · 3c + 11 (the flip landed) · 4 (farm-growth final) ·
> 5 (F9 fully closed) · 6 (perf pass merged) · 8 (paper G3 done). **STILL OPEN: 3** (the ANE
> ack — never given, see below) · **7** (paper G2 — funded and RUNNING, verdict owed) ·
> **9/10** (publications) · **12** (push) · **13** (E4 + the APK rebuild). **New since this
> file was written:** roadmap **F13**, the clairvoyant K2..6 ladder, is fundable and
> launch-ready (~1–2 box-days) — it is not an item below because it postdates the compile.
> Full audit → [LIVE_QUEUE_SNAPSHOT_20260803.md](LIVE_QUEUE_SNAPSHOT_20260803.md).

## Compute / funding
1. **Champ-vs-10× h2h** — ✅ READ-OUT LANDED 2026-08-02
   ([KWIDTH_110K_READOUT_20260802.md](../measurement/classical_search/KWIDTH_110K_READOUT_20260802.md)):
   pre-registered branch = **UNDERPOWERED/INCONCLUSIVE → default DO NOT FUND** (+19.4
   elo-equiv, 95% CI [−5.7, +44.6] vs the 25-elo bar — couldn't exclude a fundable
   effect, couldn't detect one). ✅ JOSHUA ACCEPTED THE DEFAULT 2026-08-03 ("1-4 I'll take your recs"): NOT FUNDED. Closed.
2. **rodv3 menu** (CL-072 leaning-negative): gen@11008 discriminator — **REPRICED with
   MEASURED gen throughput (2026-08-02 gen W-sweep, production knobs k8×1376 rust): ~260
   games/h laptop-only, ~314 games/h local-only, wall-parallel both boxes ⇒ the 300-game
   gen is ~35 min (two boxes) / <1 h (either box alone)** — down from the ~4–6 h estimate
   and the 29 h python-era price. The blocking cost is now the TRAIN + eval tail, not gen.
   ✅ JOSHUA 2026-08-03: PARKED (rec accepted). CL-072 stays Provisional/Open with the lean banked.
3. **ANE n≈2150 cell** — recommendation: CLOSE UNFUNDED (the port inflated r ~8× past the
   reopen bar; STATUS 2026-08-01 note). ✅ **JOSHUA ACKED 2026-08-03 evening ("ANE closed for
   now as we dont need anand anymore"): CLOSED UNFUNDED.** CL-067 claim line amended. Closed.
   ⚠️ **STILL UN-ACKED as of the 2026-08-03 evening sweep — the one item that fell through
   the cracks.** Your "1-4 I'll take your recs" (DECISIONS 2026-08-03 morning) was booked as
   items 1/2/4 + fixed_v1 + the flip + the spike; item 3 is not named in that entry and
   CL-067's claim line is unchanged. One word closes it.
3b. **NEW — the CUDA-Graph net-arm spike (~half a day, port-5 memo):** desktop torch+Graph
   at batch-8 lands cost_ratio **2.12×, inside the netprior break-even for the first time**
   (the right statistic is 0.5+r, not 1+r — netprior deletes the classical child sweep).
   The go/no-go: reach CUDA-Graph from Rust via ort IOBinding; if batch-8 ≥ ~0.18 ms, stop.
   This REOPENS (on new grounds, desktop-only) what the ANE post-mortem closed — it does
   not contradict 3: the ANE r-bar stays failed. → docs/RUST_NET_EVAL_DESIGN_20260802.md,
   LEVER_INDEX 16–17. ✅ SPIKE RAN 2026-08-03 (funded): **STOP** — CUDA-Graph reached from Rust (0.152 ms b8, 4.4% off torch, faithfulness clean) but the census-clean denominator is 1.55× faster than the memo's loaded-box figure ⇒ cost_ratio 3.06, outside break-even; even the memo's torch row recomputes dead (2.95). SHELVED with working code; reopen: ≤0.11 ms b8 on target hardware or a ≥64-leaves-in-flight design. Durable rider: box-state moves search_ms_per_sim 2.1× — every r-shaped claim needs a census-clean denominator (LEVER_INDEX 18a). CLOSED.
3c. **NEW — backend default flip readiness (F11 done):** all four desktop callers wired +
   injection-proven; remaining pre-flip blockers (port-3 list): (i) factory must resolve
   per-mode or clairvoyant builds raise — top item; (ii) tests/release/test_factory_manifest
   re-check; (iii) the flip moves only the 6 make_production_champion sites (the eval fleet
   rides build_fair_champion's own default). ~~Flip when you say so.~~ ✅ **YOU SAID SO AND IT
   FLIPPED 2026-08-03**: `make_production_champion(backend="auto")` resolving PER MODE
   (fair → rust, clairvoyant → python FAIL CLOSED, python-only capabilities → python); all
   three blockers discharged; two omitted-kwarg bugs found and fixed en route (incl. the
   python oracle of every rustport gate). DECISIONS 2026-08-03; roadmap F11. CLOSED.
4. **F7b farm knockout cells** — ✅ RAN 2026-08-02 (funded by your "lets do the farm knockout cells"): farm base **−142 elo** (z −9.4, verdict); farm-growth **+42.8 (z +1.87) — the champion LEANS BETTER WITHOUT it**. CONFIRM RAN 2026-08-03 (you funded): **UNCONFIRMED** — +10.4 ± 17.4, margin dead flat (z −0.07); the +42.8 was a winner's-curse crest (the project's 5th screen-shrink). Parked suggestive-unpromoted. ✅ JOSHUA 2026-08-03: no third cell (rec accepted). CLOSED — parked suggestive-unpromoted, final.
5. **F9 rules-fix program** — ✅ **FULLY CLOSED 2026-08-03 (all phases).** A+B complete +
   **fixed_v1 ADOPTED** (CL-075 transfer bound; W2 by probe; all five fixes flag-gated).
   The three tail runs all landed the same day: caps/curve re-sweep **ALL-NULL** (optima
   transfer ⇒ absolute fixed-rules claims UNGATED, band 1.03e11 retired), D1 JCZ replay
   oracle **43/43**, Phase C descriptives **DONE** + the seat-swap luck floor (ICC 0.19,
   σ_pair 12.8 ⇒ **E4 sizing = 193 seat-swap paired games at true-wr 0.55**). CLOSED.
   ⏭️ Only residue: the E4 phone flip to fixed_v1 rides the next APK (see item 13).
6. **Perf pass** on the review's #2–4 (+C-e/C-f riders): ~−22% RSS / −13% wall on the
   champion, all bit-identical, gated by gate re-runs. ✅ **FIRED 2026-08-02 afternoon**
   (wiring went green, not cancelled): Opus agent in an isolated worktree, per-change
   commits each gated (cargo + pytest + G3-pattern reconcile + G6-pattern 10-game
   identity). Merge happens only after orchestrator review — cancelling mid-flight just
   means not merging. ✅ **MERGED 2026-08-02 evening (`55f7eea`)**: wall −20–30%, peak RSS
   −50–60%, all bit-exact; rider C-f REFUTED-BY-MEASUREMENT. CLOSED.
7. **Paper G2** — transformer control (~1–2 box-days + GPU day) vs scoping the claim
   "at this scale". Advisor: decide after lit review. ✅ **FUNDED AND RUNNING** — three arms
   (resnet_scratch + tf_match trained 16/16; tf_large 28M is the long pole), ruler pass
   ~1–2 h after training, **verdict owed**. Read `INSTRUMENT_INTEGRITY.PASS` before
   `HEADLINE.BRANCH`; worktree merge owed at a quiet window. ⚠️ Name collision: this
   "G2" is a *paper gap*, not roadmap Track-G **G2** (the budget/pareto curve, CL-068).
8. **Paper G3** — ✅ **DONE 2026-08-02** (Joshua's fresh-budget go): the label-variance
   decomposition landed in `measurement/paper_g3_20260802/` (`G3_VARIANCE_DECOMP.md`
   + `.json` + `G3_FIGURE_DATA.csv` + 4 reproducible scripts) and **CLAIMS_LEDGER gap G3
   is flipped to Closed — ledger claim D1 is now MEASURED, not interpretation**
   (99.72% of child-value variance is between roots, 0.28% between siblings). Commit
   `ae90648`. ⚠️ Same name-collision caveat: not roadmap Track-G **G3** (per-move cost).

## Publication / outreach (all parked pre-Shabbat, still parked)
9. The advisor memo's 7 questions (docs/reviews/FABLE_ADVISOR_20260731.md) + the 90-day
   sequence go/no-go; preprint timing; the no-"superhuman" phrasing rule is standing.
10. **Related-work sprint** (1–2 weeks; the paper's only unwritten load-bearing part).
    Advisor says do it FIRST. Who/when.

## Config / technical defaults
11. **Desktop backend default** — ✅ **FLIPPED 2026-08-03** (funded, built, landed): the
    per-mode resolution + release-test recheck shipped and `make_production_champion`'s
    default is now `"auto"`. See item 3c. CLOSED.
12. **Push** — dozens of commits on `android-app`, never pushed (standing rule). Say the
    word when you want origin updated.
13. **E4 protocol restart** — the phone now plays the champion of record on a centered
    board with the retail tile. Your games from here are the human-anchor data the
    program has wanted since E4 was named. Play when ready; archives self-label.
    ⏳ **Two updates 2026-08-03.** (i) **The sizing is now MEASURED, not guessed:** deck-luck
    ICC 0.19, σ_pair 12.8 ⇒ **193 seat-swap deck-paired games at true-wr 0.55** (48 at 0.60)
    — so play E4 as seat-swap pairs, not singles
    ([LUCK_FLOOR_fixed_v1](../measurement/f9_phase_c/LUCK_FLOOR_fixed_v1.md)).
    (ii) **The APK is 4 items behind** (bag-counter fix, A3 bridge plumbing, perf-pass+R9
    wheel, `fixed_v1` profile) — a rebuild is offered and bundles naturally with the E4
    rules flip. Your call on both.

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
