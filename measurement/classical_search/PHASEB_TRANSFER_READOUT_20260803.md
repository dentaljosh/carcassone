# F9 PHASE B READ-OUT — the transfer bound (2026-08-03)

> **STATUS: ✅ COMPLETE — branch B1 fires: THE FLAGSHIP CONTRAST TRANSFERS.** Prereg
> [PHASEB_TRANSFER_PREREG_20260803.md](PHASEB_TRANSFER_PREREG_20260803.md) (committed
> before game 1); estimator pre-written before arm F existed. Band 1.02e11 retired.

## The result

| arm | rules | n | W/D/L | elo | paired margin (z) |
|---|---|---|---|---|---|
| W (control) | walled | 400 | 208/7/185 | +20.0 | +1.41 (z +1.65) |
| F | fixed_v1 + R9 | 400 | 220/8/172 | +41.9 | +2.59 (z +2.92) |

**Deck-matched Δ(F−W) over the same 200 decks: +1.18 ± 1.20 pts/deck, z +0.98,
95% CI [−1.17, +3.53]** ≈ **[−18, +53] elo-equivalent** at each arm's margin→elo ratio
(~14–16). |Δ| ≤ 1σ ⇒ **B1: the promotion contrast of record (deeper champion wins)
REPRODUCES under canonical-fidelity rules within the measured bound.** Point estimate
mildly positive (the contrast is, if anything, slightly larger under fixed rules) —
inside noise, not promoted.

## Falsifiers (hard, pre-registered): CLEAN
Zero sentinel wall-events, zero WindowOverflowError, both arms full n=400;
arm F manifest carries `rules_profile: fixed_v1` + `r9_env_ok: true`.

## What this buys
- The walled record's headline CONTRAST class now carries a **measured transfer bound**
  — the publication objection ("nonstandard rules") is answered with data, not argument.
- Scope guard (prereg): this bounds a contrast; ABSOLUTE fixed-rules strength still
  needs the caps/curve re-sweep if rules are globally adopted (J1). The fresh-band arm W
  (+20.0) vs the historical +49.85 (band 32e9) is the known cross-band over-dispersion,
  which is exactly why the same-band control existed.
- Fresh cross-band datum for the over-dispersion file: same config, +49.85 (32e9) vs
  +20.0 (1.02e11), consistent with the measured 1.8–2.2× inflation.
