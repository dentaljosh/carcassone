# POWERED CONFIRM OF THE β=+0.3 PHASE LEAN — PRE-REGISTRATION

> **STATUS: ✅ RAN AND CLOSED 2026-08-10 — pre-registered branch **P2** fired: THE LEAN DOES NOT
> CONFIRM.** n=800 deck-paired on band 1.17e11 (retired): W378/D24/L398, elo **−8.688 ± 12.288**,
> paired margin **−0.4975 pts/deck**, **primary statistic margin z −0.7845** (|z| < 2.0). All §wiring
> gates verified from the manifest before any number was read; completion 800/800. ⇒ **CL-077 stands,
> its falsifier is DISCHARGED-NEGATIVE, the phase axis stays closed; effect-size floor ~±1.2 pts/deck
> ≈ ±20 elo at 2σ.** The n=200 lean (+33.1 / z +1.39) regressed to a *sign-flipped* null at 4× the
> sample — the house noise signature, third confirmed instance. `PRODUCTION.yaml` untouched.
> results.csv `curvephase_b0p3_power_fixed_v1_vs_champ_n800`; DECISIONS 2026-08-10 (~10:00).
> *Deviation on the record: executed on TWO boxes (local W=30 + laptop W=22 work-stealing, ~3.1 h)
> rather than the design line's "local W=14, laptop excluded" — a resource-plan change, not a
> statistical term; the laptop was bundle-synced + capability-verified before joining. The
> deviation was OWNER-DIRECTED mid-run (Joshua, in-session: "I'm not using the box this
> morning. and you can work steal on laptop"), not an operator improvisation.*
>
> **STATUS (original, at funding): FUNDED 2026-08-10 morning (Joshua: "let's power 0.3"). Written BEFORE game 1.**
> This is CL-077's own falsifier, exercised: the C-KILL ladder's +0.3 cell read +33.1 elo /
> paired margin +1.960 (z +1.39) at n=200 — recorded as an UNRESOLVED LEAN (largest single
> cell, direction of the owner's self-described play policy, but sub-2σ and non-monotone:
> +0.6 fell back to flat). Re-open bar from CL-077: n≥800 paired in β∈[+0.2,+0.4].
> `governance/PRODUCTION.yaml` untouched on every branch of this document.

## Design

ONE cell: **β=+0.3, n=800 deck-paired (400 decks × 2 seatings), fresh band `1.17e11`**,
vs the production champion, everything else identical to Part C attempt 2
([PREREG_DRAFT.md](PREREG_DRAFT.md) §3 + AMENDMENTS 1–2): fair PIMC k8×1376=11008 both arms,
`fixed_v1`+R9, rust backend, cell JSON `cells_phase/curvephase_b0p3_fixed_v1_vs_fairchamp11008.json`
(pinned norm 1.00825), `--allow-cand-curve-drift` (stamping path). Local box W=14 (the only box
carrying the merged+built seam substrate; laptop deliberately excluded, same reason as attempt 2).

Why a single cell and not a mini-ladder: +0.3 is already BRACKETED (0.0 and +0.6 both read
lower in attempt 2), so the cheap informative test is the peak cell alone. If it confirms,
the neighborhood sweep is the NEXT experiment, not this one; if it nulls, no neighbor was
going to rescue it.

## Wiring / validity gates (checked from the manifest before any number is read)

- `cand_leaf_hash` MUST equal **`0283a702b8f5af51`** (attempt 2's b0p3 hash — same injected
  leaf, bit-for-bit) and `opp_leaf_hash` `a36d2e15a3b3d71d`; `v29_phase_beta` 0.3,
  `v29_phase_norm` 1.00825; `rules_profile` fixed_v1, `r9_env_ok` true, backend rust,
  `band_seed_start` 117000000000.
- Completion ≥ 90% of 800 or the cell is VOID (the C5 hang rule).
- No identity gate (this is not an identity cell); the injection path's inertness and
  liveness were both established in attempt 2.

## Primary statistic and pre-registered readings (stated before any game)

**PRIMARY: the cell's own deck-paired margin z** (candidate − champion, per deck, both
seatings). Expected se ≈ 0.59 pts/deck (measured per-deck margin sd ≈ 11.8 over 400 decks).
⚠️ NO POOLING with the n=200 attempt-2 cell — different band, and cross-band pooling is
forbidden (CL-068 amendment). This cell stands alone.

| # | condition | verdict |
|---|---|---|
| P1 | margin z ≥ +2.0 **and** elo sign agrees | **LEAN CONFIRMED — CL-077's falsifier FIRES.** The phase axis re-opens; flip CL-077 per its falsifier field. Next steps (NOT authorized by this doc): neighborhood optimization (β grid around +0.3), then the standard promotion gates. Nothing is promoted on this cell. |
| P2 | \|margin z\| < 2.0 | **LEAN DOES NOT CONFIRM.** CL-077 stands, falsifier discharged-negative; the +33.1 was the noise signature the house rule predicted. Record the effect-size floor (~±1.2 pts/deck ≈ ±20 elo at 2σ). Axis stays closed. |
| P3 | margin z ≤ −2.0 | **SIGN-REVERSAL** — the strongest possible noise confirmation; close permanently, note the winner's-curse anatomy alongside intra_reuse's (+40.1 → +16.2 → CI includes 0). |

Riders: the ply-k/leaf-k norm caveat (AMENDMENT 2) applies verbatim — a P1 confirm inherits
it and the ≤5–17 elo magnitude-trade must be quantified before any promotion talk. The
sims-washout and CL-051 consumer-binding riders apply. Cost: ~3.2 h at W=14 (800 games at
the measured ~14.2 s/game).
