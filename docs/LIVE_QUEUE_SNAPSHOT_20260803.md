# LIVE QUEUE SNAPSHOT — 2026-08-03 (late evening refresh)

> **⚠️ POINT-IN-TIME AUDIT ARTIFACT. This does NOT replace the roadmap.** The single work queue is
> [PROGRAM_ROADMAP_2026-07-07.md](PROGRAM_ROADMAP_2026-07-07.md); the live-state snapshot is
> [STATUS.md](../STATUS.md); Joshua's open calls are [DECISION_QUEUE_20260802.md](DECISION_QUEUE_20260802.md).
> First written by the 2026-08-03 evening doc sweep; **refreshed same night ~19:45 after Joshua's
> directive batch** ("apk go for it · ANE closed · anticipation go · f7c launch · g1/g3 moot · wc
> tie we'll update · push"). Goes stale the moment anything closes. Every line cites its source.

## (a) Running right now

| What | Where | Source |
|---|---|---|
| ~~paper-G2~~ — **✅ CLOSED C_GRAY 2026-08-03 night** (no architecture escapes / no scratch arm fits — both halves per the ledger wording lock; D5 warm-start datum) | merged `e30dc16` | [READOUT](../measurement/paper_g2_20260803/READOUT.md); DECISIONS 2026-08-03 night |
| **CL-074 component-table remeasure under `fixed_v1`** — 7/8 cells LANDED, **table TRANSFERS incl. the anticipation-pair null**; final cell (farmgrowthoff) finishing; close-out owed on exit (rows check → CL-074 amendment → band retire → DECISIONS) | both boxes, minutes out | [F7C_PREREG](../measurement/leaf_ablation_20260730/F7C_PREREG.md) *(misnamed F7C — it is the CL-074 remeasure)*; STATUS night block |
| **Marginalized solver frontier bench** — fair K=4/5 n=20 + K=6 probes, 1 h caps (answers "is fair K=5/6 an option?") | laptop W4, overnight worst-case | `/mnt/carc-shared/marg_bench_20260803/`; DECISIONS 2026-08-03 solver entry |

## (b) Awaiting Joshua's hands or word

| Item | Cost | Source |
|---|---|---|
| ~~Sideload the fixed_v1 APK~~ — **✅ DONE ~20:00: re-paired, installed, `connectedDebugAndroidTest` 13/13 on the Pixel. E4 now plays under fixed_v1.** | — | DECISIONS 2026-08-03 evening batch |
| **F13 — clairvoyant K2..6 winrate ladder** (prereg launch-ready; recommendation = leave shelved: the fair headroom that matters is F3-bounded tiny, so even a clairvoyant fire has a weak deployment path) | ~1–2 box-days | roadmap **F13**; [PREREG_DRAFT](../measurement/exact_k_ladder_20260803/PREREG_DRAFT.md) |
| **Publications** — advisor's 7 questions + 90-day go/no-go; related-work sprint FIRST | 1–2 weeks of writing | [DECISION_QUEUE](DECISION_QUEUE_20260802.md) 9–10 |
| **F12 — analyzer slice 2** (unscoped; coach-mode gating question) | scoping first | roadmap **F12** |
| **WC tie-break flag** — APPROVED 2026-08-03 ("fine we'll update"), unscheduled; measure tie frequency in the Phase C corpora first | ~an agent-session + A3-style gates | [BACKLOG.md](../BACKLOG.md) 2026-08-03 |

## (c) Parked, with the reopen condition

| Item | Reopen bar | Source |
|---|---|---|
| **rodv3 / CL-072** (leaning-negative, Provisional) | fund n→800 (~7 h) **or** gen@11008 (~35 min gen) | roadmap **G8** |
| **CUDA-Graph net arm** (STOP, working code shelved) | ≤0.11 ms b8 on target hardware **or** ≥64 leaves in flight | queue item 3b |
| **ANE / equal-clock distilled-policy question** — **CLOSED UNFUNDED 2026-08-03** ("we dont need anand anymore"); CL-067 amended | a learned component re-entering deploy with viable r | queue item 3 ✅ |
| **G1 pondering — MOOT** (Joshua 2026-08-03) | contest registration AND fresh budget-buys-elo evidence | roadmap **G1** |
| **G3 per-move cost — MOOT** (trigger counterfactual) | a learned component re-entering the deploy path | roadmap **G3** |
| **C3-intra tree carry** (+16.2 ± 10.0, CI incl. 0) | n≈4800 paired (~32 box-h) if ~+16 elo becomes decision-relevant | roadmap parking lot |
| **Farm-growth deletion** — final: suggestive-unpromoted, no third cell | (final) | queue item 4 |
| **Specialized endgame net** (named 2026-08-03) | the F13 ladder firing at K≥5 | [LEVER_INDEX](LEVER_INDEX.md) row |
| **claim.py-level skew check** (the deeper F7c fix) | "claim-side skew check" trigger | [BACKLOG.md](../BACKLOG.md) 2026-08-03 |
| **Eff Hans** (rule variants, never started) | Joshua's go per variant | [BACKLOG.md](../BACKLOG.md) 2026-07-30 |

## (d) Standing protocol items

- **E4 games** — play as **seat-swap deck-pairs**; measured sizing 193 paired games @ true-wr 0.55 (48 @ 0.60). → [LUCK_FLOOR_fixed_v1](../measurement/f9_phase_c/LUCK_FLOOR_fixed_v1.md).
- **Push** — ✅ first push executed 2026-08-03 (`android-app` on origin). Future pushes still per-ask.
- **Publications phrasing** — the no-"superhuman" rule is standing.
- **Six-touch close-out + `doc_lint.py`** on every verdict; band registration before game 1; **W default for rust workloads = threads − 2** (Joshua 2026-08-03).
- **Engineering hygiene tickets** (no owner): shared-claim no-progress abort · `run_watchdog.sh` pgrep false-positive · mutation-test order-dependence · gate-script leaf-env · test isolation · **cy-wheel content-version depends on `.venv` presence** (new 2026-08-03). → [BACKLOG.md](../BACKLOG.md).

## Closed since the first snapshot (same evening)

F7c skew guard (62 launchers + coverage test) · ANE ack (item 3) · G1/G3 moot rulings · WC tie
approved-unscheduled · APK built+staged (install pending) · fixed_v1 luck floor measured (ICC 0.19 ·
σ_pair 12.8) · first push · component remeasure launched · marg frontier bench launched · F13 prereg
drafted.
