# LIVE QUEUE SNAPSHOT — 2026-08-03 (evening)

> **⚠️ POINT-IN-TIME AUDIT ARTIFACT. This does NOT replace the roadmap.** The single work queue is
> [PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md); the live-state snapshot is
> [STATUS.md](../STATUS.md); Joshua's open calls are [DECISION_QUEUE_20260802.md](DECISION_QUEUE_20260802.md).
> This file is the output of a one-off sweep of every plan/queue/spec doc on 2026-08-03 and goes stale the
> moment anything closes. Every line cites its source doc. **Nothing here is funded or queued to run.**

## (a) Running right now

| What | Where | Source |
|---|---|---|
| **paper-G2 transformer control — `tf_large` arm training** (resnet_scratch + tf_match already 16/16; ruler pass ~1–2 h after training; read `INSTRUMENT_INTEGRITY.PASS` before `HEADLINE.BRANCH`; worktree merge owed at a quiet window) | local box, `/mnt/c/carc-shared/paper_g2_20260803/` | [STATUS.md](../STATUS.md) 2026-08-03 afternoon |

Nothing else. Laptop idle, M5 idle, no `--shared-claim` cells live.

## (b) Fundable / awaiting Joshua's word

| Item | Cost | Source |
|---|---|---|
| **F13 — clairvoyant K2..6 winrate ladder under `fixed_v1`** (prereg DRAFTED + launch-ready; the June exact:K null is powered only through K=3 and era-bound) | ~1–2 box-days, K6 rung overnight | roadmap **F13**; [PREREG_DRAFT](../measurement/exact_k_ladder_20260803/PREREG_DRAFT.md) |
| **APK rebuild + the E4 rules flip** — the Pixel is 4 items behind (bag-counter fix, A3 bridge plumbing, perf-pass+R9 wheel, `fixed_v1` profile) | ~an agent-session, no compute | [STATUS.md](../STATUS.md); roadmap **F9** residue (ii) |
| **Decision-queue item 3 — ANE `n≈2150` cell: CLOSE UNFUNDED** (recommendation stands; the port inflated `r` ~8× past the reopen bar). **Never explicitly acked** — the "1-4 I'll take your recs" of 2026-08-03 covered items 1/2/4 + fixed_v1 + flip + spike, not 3 | one word; flips a CL-067 claim line | [DECISION_QUEUE](DECISION_QUEUE_20260802.md) item 3; DECISIONS 2026-08-03 (morning) |
| **Re-measure the anticipation pair / full component table under `fixed_v1`** (the caps/curve re-sweep closed all-null, so the sequencing precondition is satisfied — no re-tune first) | ~2 h, 8 cells two-box | [BACKLOG.md](../BACKLOG.md) 2026-08-03; roadmap **F9** rider |
| **F7c — hoist the clock-skew guard into `scripts/measurement_infra/`** (still fixed in individual launchers only; a fast client clock silently steals sibling claims) | engineering, 0 compute | roadmap **F7c** |
| **Publications** — advisor memo's 7 questions + the 90-day sequence go/no-go; the related-work sprint the advisor says do FIRST | 1–2 weeks of writing | [DECISION_QUEUE](DECISION_QUEUE_20260802.md) 9–10; [FABLE_ADVISOR](reviews/FABLE_ADVISOR_20260731.md) |
| **F12 — Phase-5 analyzer, slice 2** (slice 1 landed; next slice UNSCOPED, incl. whether coach-mode gating is in scope) | scoping first | roadmap **F12**; [BACKLOG.md](../BACKLOG.md) 2026-07-30 coach mode |

## (c) Parked, with the reopen condition

| Item | Reopen bar | Source |
|---|---|---|
| **rodv3 / CL-072** (leaning-negative, Provisional) | fund the n→800 extension (~7 h two-box) **or** gen@11008 (~35 min gen two-box, train+eval is the tail) | roadmap **G8**; queue item 2 |
| **CUDA-Graph net arm** (spike ran, STOP, shelved with working code) | ≤0.11 ms b8 on target hardware **or** a ≥64-leaves-in-flight design | queue item 3b; [RUST_NET_EVAL_DESIGN](RUST_NET_EVAL_DESIGN_20260802.md) |
| **G1 pondering** (legal, unscoped, highest-value new lever) | registering for an official contest | roadmap **G1** |
| **G3 per-move cost / batching** | funding the distilled-net line, or any learned component entering deploy | roadmap **G3** |
| **C3-intra within-turn tree carry** (+16.2 ± 10.0 combined, CI includes zero) | n ≈ 4800 paired (~32 box-h) if ~+16 elo becomes decision-relevant | roadmap parking lot (6) |
| **WC tie rule** (starting player loses ties) — the ONE rules divergence `fixed_v1` does **not** fix | official-contest registration; needs seat-asymmetric terminal value | [BACKLOG.md](../BACKLOG.md) 2026-07-28 |
| **Farm-growth deletion** (+42.8 screen → unconfirmed) | final: no third cell (Joshua 2026-08-03) — suggestive-unpromoted | queue item 4 |
| **Eff Hans** (rule-variant exploration) — chartered, never started | Joshua's go per variant set; ~a night per variant | [BACKLOG.md](../BACKLOG.md) 2026-07-30 |

## (d) Standing protocol items

- **E4 human-anchor games** — the phone plays the champion of record; archives self-label. **Sizing is now measured: 193 seat-swap deck-paired games at true-wr 0.55 (48 at 0.60)** — run E4 as seat-swap pairs. → [LUCK_FLOOR_fixed_v1](../measurement/f9_phase_c/LUCK_FLOOR_fixed_v1.md), queue item 13.
- **Push** — dozens of commits on `android-app`, never pushed. Standing rule: pushing needs Joshua's word. → queue item 12.
- **Publications** — the no-"superhuman" phrasing rule is standing; the P1 paper draft is a pointer, not a work item. → roadmap P1 pointer.
- **Six-touch close-out + `doc_lint.py`** on every verdict; band registration in `governance/BAND_REGISTRY.csv` before the first game.
- **Engineering hygiene tickets** (no compute, no owner): shared-claim no-progress abort · `run_watchdog.sh` pgrep false-positive · mutation-test order-dependence · `gate_eval_puct_priors_backend.py` sets no leaf env · `test_puct_priors_opponent_backend.py` isolation. → [BACKLOG.md](../BACKLOG.md) 2026-07-31 / 2026-08-02.
