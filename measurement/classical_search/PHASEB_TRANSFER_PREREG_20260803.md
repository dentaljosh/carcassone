# F9 PHASE B — THE TRANSFER-BOUND CELL — PRE-REGISTRATION (committed before game 1)

> **STATUS: AUTHORIZED under Joshua's F9 funding ("then f9") + bench-then-commit go;
> launched 2026-08-03 ~03:20 immediately after this commit.** Spec:
> [docs/F9_BUILD_SPEC_20260802.md](../../docs/F9_BUILD_SPEC_20260802.md) Phase B, incl.
> its load-bearing correction (BOTH arms on ONE fresh band — the cross-band form is
> underpowered at the measured 1.8–2.2× over-dispersion). PRODUCTION.yaml untouched;
> NOTHING is adopted by this run.

## Question
Does the promotion contrast of record — champion k8×1376 vs deploy-sibling k4×688,
**+49.85 ± 17.55 (CL-060/CL-071, band 32e9, walled)** — reproduce under the fixed-rules
bundle? The answer prices the transfer error of the entire walled record.

## Arms (one band, same 200 decks each, deck-paired within arm, n=400 each)
- **ARM W (walled control):** the pair under `--rules-profile walled` — re-prices the
  band+era so the F−W contrast is within-band, deck-matched (the robust class).
- **ARM F (fixed rules):** the pair under `--rules-profile fixed_v1`
  (centered18 + retail start + cloister_scan fixed + unplaceable redraw) **+
  `CARCASSONNE_FIX_R9=1`** (env-latched; `r9_env_ok: true` required in the manifest —
  the only proof the fix was live). Geometry = W2 per the probe (0/400 sentinel events;
  DECISIONS 2026-08-03 night).

Both arms: eval_fair_puct `--info fair --opponent fair-champion --exact-k 2
--k-dets 8 --sims 1376 --opp-k-dets 4 --opp-sims 688 --paired --backend rust`,
`--no-results-csv` (bench-tier recording; the readout doc is the artifact of record).
Arm W local W=32, arm F laptop W=24 — box-arm assignment is fixed here; each arm is
internally deck-paired so the box difference cannot enter the contrast.

## Band: `1.02e11` (seeds 102,000,000,000..199) — registered in this same commit.

## Pre-registered decision map
- **B1 (bound):** |Δ(F−W)| ≤ 1σ of the paired difference (~±17–25 elo at n=400/arm) ⇒
  the walled record's flagship contrast TRANSFERS; quote the CI as the bound.
- **B2 (material move):** |Δ| ≥ 2σ ⇒ RE-BASELINING TRIGGER — report only; every
  adoption/next step is Joshua's.
- **B3:** neither ⇒ inconclusive; the n→800 extension is PRICED (~2.5 h two-box) and
  NOT auto-run.
- **Hard falsifiers:** any sentinel wall-event in arm F, or any WindowOverflowError in
  either arm, VOIDS the affected cell (no partial acceptance — exclusions here are
  rules-correlated by construction). Sentinel counters are in every manifest.
- ⚠️ Scope: this bounds the transfer of a CONTRAST. Absolute fixed-rules strength is
  out of scope (the leaf's farm caps were tuned under R9-bug and walled geometry —
  spec §2.4; a global adoption triggers the caps/curve re-sweep rider).
