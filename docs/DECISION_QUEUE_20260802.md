# Joshua's open decision queue — consolidated 2026-08-02 (post-Eff-Dario)

> Everything below waits on YOU. Nothing here is queued to run without a word from you.
> Kept current until emptied; STATUS points here. (Compiled after the 2026-08-01/02
> weekend: port complete, flips landed, review rounds done.)

## Compute / funding
1. **Champ-vs-10× h2h** — wait for the probe's funding memo (landing ~this morning); its
   pre-registered branch decides the recommendation.
2. **rodv3 menu** (CL-072 leaning-negative): gen@11008 discriminator (now ~4–6 h at Rust
   speeds) · n→800 teacher-h2h extension · or bank the lean and park.
3. **ANE n≈2150 cell** — recommendation: CLOSE UNFUNDED (the port inflated r ~8× past the
   reopen bar; STATUS 2026-08-01 note). Needs your ack to flip the claim line.
4. **F7b farm knockout cells** — cheap post-wiring (Rust-severable). Go/no-go.
5. **F9 rules-fix program** — the big one: global recentring + rules remediation
   (RULES_FIDELITY_AUDIT R1–R8) + transfer-bound cell + fixed-rules descriptives +
   the JCloisterZone oracle (BACKLOG 2026-08-02). When to fund; scope in the audit doc.
6. **Perf pass** on the review's #2–4 (+C-e/C-f riders): ~−22% RSS / −13% wall on the
   champion, all bit-identical, gated by G3/G6 re-runs. Cheap; recommend yes.
7. **Paper G2** — transformer control (~1–2 box-days + GPU day) vs scoping the claim
   "at this scale". Advisor: decide after lit review.
8. **Paper G3** — label-variance decomposition (cheap offline; turns the mechanism claim
   into a figure). Recommend just doing it.

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
