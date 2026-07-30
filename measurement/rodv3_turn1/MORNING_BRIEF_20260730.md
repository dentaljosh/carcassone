# Morning brief — rodv3 night of 2026-07-29 → 30

> Written ~02:30 while the teacher h2h runs. **The h2h verdict slot at the bottom is
> filled in when the cell completes (~08:15).** Everything else here is settled fact.

## The one-paragraph version

You asked one question about a four-month-old caveat and it turned into the night: the
flywheel's null had a pre-recorded, never-indexed confound (gen at ¼ budget); CL-067's
equal-sims +35.7 made resolving it rational; three W-sweeps priced the fleet; rodv3
turn 1 launched; a buried-caveats audit then found the *new* run's premise was itself a
paraphrase ("beats its teacher" — its real corpus teacher was the 11008 champion, and
that pair is UNMEASURED); the prereg was amended pre-gate; and at your "run the eval
first" the boxes swapped: **the unmeasured pair is being measured directly, first.**

## Running right now

| what | where | state |
|---|---|---|
| **Teacher h2h**: CL-067 net k4×688 vs champion k8×1376=11008, n=400 paired, band 94e9 | local W20 (02:08) + laptop W12 (02:27, memory-capped) | **ETA ~08:50** (67/400 at 03:58; dual-window rate 64 rec/h, windows agree to 0.5%) |
| rodv3 gen (net-on-net self-play corpus) | PARKED losslessly at **65/300**, claims at parity | resumes per verdict |
| Air gen W-sweep (real net-on-net numbers via CoreML port) | M5 | W4 = 30.1 games/h measured; **box fell asleep mid-W6 ~02:21 DESPITE untimed `caffeinate -dimsu` — 2nd occurrence** (also at 377/400 on 2026-07-29). Results safe on its disk. Hypothesis to check: lid-close sleep, which caffeinate cannot block — `pmset -g log` in the morning. No long Air run should be funded until understood. |

## The decision menu, keyed by the h2h

- **Net ≥ teacher** → premise solid in strong form (above corpus tier at ¼ compute).
  Resume gen full-fleet (local+laptop ≈ 86.7 games/h ⇒ ~3.1 h for the remaining 267),
  train, then the pre-registered gate. The 11008-gen escalation stays unnecessary.
- **Net < teacher** → awakening premise weakens to "above same-budget classical only."
  The 2752 corpus is below-tier; a DEAD gate is expected, not informative. Real choices:
  fund gen@11008 (~29 h local / ~20 h fleet — the only clean lever-6 test left), or stop
  and bank the night as measurement. The 33 banked games keep provenance either way.
- **|z| < 2 in [5,25] elo** → pre-committed n→800 extension fires (prereg f2e11ca).

## Decisions parked for you (unchanged from last night)

Gate GO (after h2h) · Air-in-corpus for any turn 2 (mixed-teacher call, fp16 fraction
pre-stated) · gen@11008 discriminator · audit triage (16 findings, 13 are text edits —
`docs/reviews/BURIED_CAVEATS_AUDIT_20260730.md`, F1 corrected in `9e00184`) · outreach
packet / preprint (from the tournament memo) · CoreML worktree merges at a quiet window.

## Quiet-window fix list (main-tree, blocked while cells run)

1. `eval_fair_puct.py` PROD_KNOBS banner **inverted since CL-071** (flags true-champion
   cells as deviant, blesses superseded k4×688 as "production").
2. Upstream watchdog `.json` hardcode (audit F7 — tonight's share-side copy is safe).
3. Audit's 13 text-edit findings (F9 stale surfaces, F2 anchor mis-order, F11 wrong
   aggregates, CL-010/CL-059 adjudications…).
4. Laptop SHM orphan `carc_fairnvnClaptop-wsl` (2026-07-28) — reap.
5. Merge queue: CoreML eval worktree + gen-port branch (`worktree-agent-ab5a1b2ebdfc6dd85`).

## The night's error ledger (all caught before contaminating anything)

- My "6–8 h" h2h estimate: **3.6× low** (deploy 2.16 s/move is 8-way k-parallel; eval
  farms run the champion sequential ~13.8). Caught by the pre-flight smoke.
- My "37 s/game" gen estimate: ~7× low (source doc's own baseline was an
  order-statistic artifact). Caught by the W-sweep smoke.
- Audit F1's "+14.1": verbatim quote of a **derived** cross-band figure (arithmetic
  collision — +14.1 appears twice in CL-067 meaning different things). Caught by
  field-level re-verification; prereg amended (`d9cce65` + correction), memo `9e00184`.
- "Laptop GPU 4.5× worse": batch-1-only property; under batched orch the laptop is a
  **peer** (45.6 vs 41.1 games/h). Caught by measuring instead of citing.
- Air eval-shaped proxy ~25% optimistic vs real net-on-net gen. Caught by the re-sweep.

## H2H VERDICT (filled at completion)

**PENDING — cell running.**
