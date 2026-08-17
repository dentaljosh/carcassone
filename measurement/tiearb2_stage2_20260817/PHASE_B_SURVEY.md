# Phase-B integration surface survey (read-only, 2026-08-17)

Read out of the tree at HEAD `55779f1e` by the Phase-B survey agent. Everything here is
descriptive; nothing was modified. Key answers for the Phase-B DESIGN, verified against
live line numbers (older docs cite stale ones — see §2.4 note).

| need | answer |
|---|---|
| harness | `scripts/classical_search/eval_fair_puct.py`, `--info fair --opponent fair-champion --backend rust --k-dets 8 --sims 1376 --opp-k-dets 8 --opp-sims 1376 --exact-k 2 --paired --n 800 --shared-claim` |
| driver template | `measurement/jrules_priors_20260814/run_deploy_jrules_priors.sh` (+ `preflight_surface_b.py`); gates J1-J13 |
| candidate knob shape | new `--cand-tiearb-*` flags -> `SearchConfigRs` kwargs -> `config.cand_tiearb` resolved dict in `manifest.json` (the J4 analogue) |
| primary statistic | `summary.json::paired_z` (`_paired_z`, eval_fair_puct.py:2208 — per-deck seat-balanced margin) |
| extraction | `scripts/classical_search/menu_block_summary.py`, run AFTER the wiring gates |
| cost gate | `ms_ratio_cand_over_opp = champ_prefix_ms_per_move / rung_ms_per_move`; N4 fires > 1.20; `<= 1.05` restores cost-neutral reading |
| trap (CONFIRMED at live lines 2361/2371/2389) | `champ_prefix_ms_per_move` IS the CANDIDATE in eval_fair_puct (opposite of eval_puct_priors) |
| champion | leaf `a36d2e15a3b3d71d`, k8x1376=11008, exact-K 2, c_puct 1.5, tau_p 5.0, 13.7552 s/move sequential (box), 1.551 s/move phone |
| inverted gate | J1 EQUALITY `cand_leaf_hash == a36d2e15a3b3d71d` + J4 resolved-knob liveness field + J13 positive control passed on THIS box before game 1 (per-host `PREFLIGHT_*_${HOST}_FIRST.json`) |
| root hook | `rust/carc/carc-core/src/fair/mod.rs:195-223` `pooled_q_argmax` called from `pimc_move` (~line 507); surface-C's `root_allow` (mod.rs:427-461) is the "default path byte-identical" precedent. RECOMMENDED: rust-side knob (insertion point B), NOT a python wrapper (which would omit arbiter cost from prefix_secs and silently defeat N4) |
| python read-off | `RustFairAgent.last_move()["pooled"] = [(action, N_bits, W_bits)]` (rust_agent.py:863, lib.rs:2101-2126) — visit/Q stats only; NOT the tie predicate |
| tie predicate (corpus definition) | exact f64 equality (eps=0) on the OUTER CHAIN value (tile + best meeple; `chain_census.py:168,216`), TILES phase, champion seat, n_legal>=2; arms: leaf tie-break of record first, dedupe by successor board (afterstate map), cap J=4 by rid-seeded draw (`tiletie-cap` sha256, never index truncation), champ pick appended if outside |
| tie predicate at runtime | NOT available from search stats; needs a rust chain-value detector (no rust `chain_values` exists — grepped). `MirrorState.leaf_value_float` (lib.rs:602) is the primitive; cost is Σ_a (1+n_meeple(a)) leaf calls — cheap vs 11008 sims. Runtime analogue of the rid-seeded cap: state digest + ply |
| runtime-vs-corpus mismatches to pre-register | (a) corpus predicate evaluated on champion's seat at a REPLAYED board; (b) corpus champ_picks are a fresh search — CL-070: reseeding alone flips picks; offline firing rate estimates, not equals, the runtime rate |
| firing rate | 22.96 tied tile plies/game (E4 census, 597/26, `tiletie_pricing_20260812/DESIGN.md:792`) — population rate, n=26; funnel: 65.98% exact-tie rate on tile plies, 40.4% deduped scoreable |
| fresh band | **132000000000** via `scripts/classical_search/claim_next_band.py` (idempotent sentinel; csv.writer; lowest step-aligned band ABOVE high-water 131000000000). Claim immediately before game 1, `decision_influenced=pending` |
| DONE markers | per-cell content-bearing `DONE_<cell>` / `FAILED_<cell>` + 90% VOID rule (exit 11); chain with `;` not `&&` |
| launch invariants | `cd $REPO` mandatory; clock-skew guard abort >60s (claim-steal); bundle sync before 2-box launch (shallow bundle = parentless code_rev); SAME rust toolchain both boxes (RUSTUP_TOOLCHAIN=1.96.0); new carc_rs wheel => rebuild + positive control on EACH box |
| two things not in the tree | (1) rust tiearb probe + `_assert_surface_tiearb_live()` (two-sided: must change the pick at a tied ply AND not move `root_leaf_value_bits`); (2) the runtime chain-value tie detector |

Full prose survey with code excerpts lives in the survey agent's transcript; this table is
the load-bearing extract. The J13 lesson to copy verbatim: "Without this a zeroed dose
grades a perfect champion-vs-champion null wearing the shape of a real cell."
