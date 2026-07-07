# PHASE 1.1b — TRANSITIVITY ROUND-ROBIN (the RPS test) — PRE-REGISTRATION

**Status: COMPLETE 2026-07-07 06:31 — BOTH GATES PASS. RPS hypothesis RETIRED; +148.2 is transitive strength.**

| candidate | vs neural iter_02 (band 9.5e9) | vs h12800 (band 9.6e9) |
|---|---|---|
| **PUCT@2750** | **M1 = +230.2** (155/6/39, z11.0) | **M3 = +149.3** (139/3/58, z6.7) |
| **h6400 champion** | **M2 = +36.6** (109/3/88, z1.4) | **M4 = −8.7** (96/3/101, z−1.0) |

- **G1 (RPS gate) PASS:** M1−M2 = +193.6 (σ_diff≈39) vs transitivity's predicted ~+148 — PUCT *over*-delivers by ~1σ against the independent neural lineage. An h6400-specific exploit would show M1 *under* M2's implied level; the opposite happened.
- **G2 (compute-odds) PASS:** PUCT@2750 beats h12800 (+149.3, z6.7) while giving it ~2.3× compute. The kicker — **M4 = −8.7 (tie): the champion cannot beat a doubled version of itself.** HeuristicMCTS is search-SATURATED; the +148 is algorithmic (priors+expand-all+visit-select), not a compute or depth artifact. (M4 also n=200-confirms — and REVERSES the sign of — the old h12800>h6400 screen wr0.605: at equal *leaf/config* vs our candidate's decks, more sims of random-expansion buys nothing.)
- M2 (+36.6) independently replicates the historical h6400-vs-rodv2 margin (+22..+32, chain autopsy) → harness measures the same world.

Numbers: `ROUND_ROBIN_PROGRESS.tsv` + per-cell `summary.json` under `puct_roundrobin/rr_rr{1..4}_k2/`. **Consequence: the champion-flip proposal is on transitive footing; proceed to sign + K=3 + re-anchor.**

---
**Original question (2026-07-06):** is the confirmed +148.2 (z10.17, n=400, `b3d3312`) a *transitive* strength gain, or a non-transitive matchup exploit (RPS) against the one opponent we measured — the HeuristicMCTS champion the whole ruler is calibrated to? **→ ANSWERED: transitive.**

**Why this outranks everything else:** if non-transitive, the champion flip, the ruler re-anchor, and any further config tuning are all built on a matchup artifact. Establish the advantage is real before optimizing or acting on it. (Config sweeps: DROPPED — within-plateau tuning ≤~20 elo, gates nothing, re-opens the multiple-comparisons surface. τ bracket: DROPPED per Joshua 2026-07-06. `value_norm` is the only mechanistically distinct axis and is deferred until after this test.)

## Design — 4 cells, 2 candidates × 2 opponents, CRN

Candidate config FROZEN at the confirmed cell: `c1.5/τ5/visits/float/2750` (sweeping config here would confound the transitivity read). Baseline candidate = production champion `HeuristicMCTS h6400 v2.9 Bmild_cap8 + exact-K≤2` (same endgame both candidates, as in the confirm). All cells deck-paired, clairvoyant matched-mode, per-opponent SHARED fresh band (CRN: the margin *difference* between candidates is what matters, so both candidates see identical decks per opponent).

| cell | candidate | opponent | n | band |
|---|---|---|---|---|
| RR-1 | PUCT-priors@2750 | **rod_v2 iter_02** (neural, independent lineage) | 200 | 9.50e9 |
| RR-2 | h6400 (champion) | rod_v2 iter_02 | 200 | 9.50e9 (same decks) |
| RR-3 | PUCT-priors@2750 | **h12800** (2× champion compute) | 200 | 9.60e9 |
| RR-4 | h6400 (champion) | h12800 | 200 | 9.60e9 (same decks) |

**Opponent picks:**
- **rod_v2 iter_02** (`/mnt/c/carc-shared/rod_v2_flywheel/ckpt/iter_02.pt`) — the established independent-lineage game-play anchor (≈h3200 tier, memory `reference_rodv2_iter2_eval_anchor`), a *learned* policy+value = genuinely different decision process. This is the RPS-decisive axis. Exact anchor config (sims, residual scale, leaf) pinned from the rod_v2 eval harness at execution; recorded in manifest. Runs under carc-orch high-W (neural forwards).
- **h12800** — same family but 2× the champion's compute (results.csv h12800-vs-h6400 screen wr 0.605/z2.27/n=100 ≈ +74). PUCT@2750 is equal-time to *h6400*, so RR-3 gives the candidate **~2.3× compute odds against it**. Beating a deeper searcher it was never tuned against ≈ not exploiting h6400's specific depth. RR-4 doubles as the n=200 re-confirm of the h12800>h6400 screen (a STATUS 2026-07-05 leftover).

## Pre-registered read-out (single read at n=200/cell; margins M1..M4 in paired elo)

Under transitivity: **M1 ≈ M2 + ~148** and **M3 ≈ 148 − M4**.

- **G1 (RPS gate, primary):** RPS FLAG if `M1 < M2 − 2σ_diff` (σ_diff ≈ √(σ₁²+σ₂²) ≈ ~35 elo at n=200/cell near even wr; report wr-space z alongside — elo σ inflates at lopsided wr). PASS if M1 ≥ M2 within that noise.
- **G2 (compute-odds gate):** PASS if M3 > 0 at 2σ (candidate at ~0.43× the opponent's compute still wins). M3 in (0, 2σ) = inconclusive-positive; M3 ≤ 0 = flag (not necessarily RPS — h12800 may genuinely out-search it — but the "beats the classical frontier" claim weakens to "beats h6400's config").
- **Combined verdict:** both PASS → transitive win; proceed to flip review + Phase-3 re-anchor with confidence. G1 FLAG → the +148 is (at least partly) matchup-specific → do NOT flip; autopsy which positions drive the h6400-specific edge.
- No peeking, no band re-rolls, no extra cells without a new pre-registration line.

## Cost / ops
- **APPROVED (Joshua 2026-07-06): local + laptop, work-stealing. W30 local / W22 laptop for the CPU-only cells (RR-3/4); W48 local / W26 laptop under the rust orchestrator for the neural-opponent cells (RR-1/2).** Launcher: `scripts/classical_search/run_round_robin.sh`.
- ETA (per confirm-calibrated game costs: h6400-equivalent side ≈ 650s/game): RR-1/2 ≈ ~35–45 min each at orch W74 combined; RR-3/4 (h12800 side ~1300s) ≈ ~2h each at W52 combined. **Total ≈ ~5h split local+laptop.** Order: RR-1/2 first (fast + RPS-decisive), RR-3/4 overnight.
- **Prerequisites:** (1) laptop bundle-sync to `b3d3312` (it's at `b9ad65d`; confirm games were still clean — no game-code commits in between — but sync before any new run). (2) Harness: `eval_puct_priors.py` grows an `--opponent {h<sims>|net:<ckpt>}` flag (or the rod_v2 net-vs-net harness gains the PUCT-priors agent) + smoke at production knobs. (3) Pre-launch census both boxes.
- **RAM guard (the 2026-07-06 WSL-crash lesson):** K stays ≤2 here (cheap). Any future K≥3 run: `CARCASSONNE_TT_CAP` set + W sized to VM RAM (the K=4 W10 run grew TTs ~3.5h until the WSL VM died — it was memory, not thermal).

## Deferred / rescoped (recorded so the queue reflects reality)
- **K=4 endgame check** — crashed at 16/200; was mis-scoped (~40h at W16, ~13min/game). Rescope AFTER the round-robin: **K=3 n=200** (~80s/game extra ≈ ~4h, answers most of the endgame-depth question) with K=4 n=100 TT-capped as a weekend option only if K=3 moves the margin.
- **τ∈{3,8} bracket** — DROPPED (Joshua 2026-07-06): gates nothing, config already confirmed at τ=5.
- Config broadening (c/τ/quant/multi-var sweeps) — DROPPED; see header.
