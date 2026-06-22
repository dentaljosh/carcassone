# v2.8 root-action audit (Phase 4)

> Each v2.8 variant evaluated as a **depth-0 static selector** (argmax of its leaf over legal
> afterstates) on existing labelled datasets — NO net, NO cluster, pure CPU. Harness:
> [scripts/heuristic_v28/v28_root_audit.py](../../scripts/heuristic_v28/v28_root_audit.py).
> Data: [V28_ROOT_AUDIT_RESULTS.csv](V28_ROOT_AUDIT_RESULTS.csv),
> [V28_ROOT_AUDIT_BY_SUBSET.csv](V28_ROOT_AUDIT_BY_SUBSET.csv),
> [V28_ROOT_AUDIT.jsonl](V28_ROOT_AUDIT.jsonl).
>
> **Harness validated:** v27_baseline midgame top-1 vs the heur@3200 teacher = **0.4800**, exactly
> reproducing the known [ROOT_ACTION_RESULTS.csv](../search_policy_mixing/ROOT_ACTION_RESULTS.csv)
> `V27_STATIC_ROOT_ONLY` = 0.48, and the v27_baseline pick matches the labelled `v27_static_choice`
> 60/60 on a spot check. So variant deltas below are measured against a faithful v2.7 selector.

## Headline (FACT)

| variant | midgame top-1 vs teacher (n=1000) | endgame K=2 top-1 EXACT (n=150) | endgame K=2 mean regret |
|---|---|---|---|
| **v27_baseline** | 0.4800 | 0.7632 | 0.5439 |
| v28_farm | 0.4650 (−0.015) | 0.7477 (−0.016) | 0.5676 (worse) |
| v28_meeple | 0.4860 (+0.006) | 0.7632 (=) | 0.5439 (=) |
| **v28_completion** | 0.4760 (−0.004) | **0.8261 (+0.063)** | **0.3913 (−0.150)** |
| v28_denial | 0.4760 (−0.004) | 0.7568 (−0.006) | 0.5586 (worse) |

Note the endgame top-1 absolute (0.763 for v27) is higher than BASELINE_RESULTS' 0.682 because this
audit's selector scores the **meeple-PASS-resolved** afterstate (matching `v27_score_resolved`),
a slightly different selector definition — but it is **identical across variants**, so the
variant-vs-v27 deltas are apples-to-apples.

## Divergence & net effect (midgame, vs the teacher)

| variant | picks ≠ v27 | newly correct | newly wrong | **net** |
|---|---:|---:|---:|---:|
| v28_farm | 56 | 11 | 26 | **−15** |
| v28_meeple | 39 | 13 | 7 | **+6** |
| v28_completion | 16 | 3 | 7 | −4 |
| v28_denial | 19 | 4 | 8 | −4 |

## Target-subset recovery (the addendum's patch-specific test)

Each subset = the Phase-1 v2.7-miss cases tagged to that patch (so v27_baseline = 0.0 by construction);
the question is whether the patch recovers the teacher's pick on **its own** target.

| subset (n) | v28_farm | v28_meeple | v28_completion | v28_denial |
|---|---|---|---|---|
| target:farm (93) | **0.011** | 0.032 | 0.011 | 0.022 |
| target:meeple (22) | 0.0 | **0.091** | 0.0 | 0.0 |
| target:completion (105) | 0.019 | 0.038 | **0.029** | 0.029 |
| v27_correct (480) — *degradation* | **0.946** | 0.985 | 0.985 | 0.983 |

## Per-patch verdict (decision gate)

- **`v28_farm` — KILL.** Broad midgame degradation (net **−15**; v27_correct 1.0→**0.946**, 26 good
  picks flipped wrong), recovers only **1/93** of its OWN farm target, and is **worse** on the exact
  endgame (0.748 vs 0.763). As a static selector the majority gate hurts more than it helps. This is
  consistent with the Phase-3 cap-masking finding: the few times the gate moves the argmax, it removes
  legitimate growth value (the gate fires on near-ties where the credit was load-bearing). **Does not
  advance to search.**
- **`v28_denial` — KILL.** Net −4 midgame, no target movement, worse endgame — exactly the
  pre-committed "kill before search if Phase-4 shows no movement" ([V28_PATCH_PROPOSALS.md](V28_PATCH_PROPOSALS.md)
  Patch 4). Denial value is a search phenomenon, not a static-leaf one. **Does not advance.**
- **`v28_meeple` — ADVANCE (weak).** Net **+6** midgame and the ONLY variant to recover any of the
  meeple target (**2/22**, the right patch on the right subset), with minimal degradation (0.985). But
  the effect is tiny and the meeple term is near-constant across root siblings (so it barely moves the
  static argmax — its real test is in *search*, where it shifts deeper-node values). **Advance to a
  low-budget search pilot.**
- **`v28_completion` — ADVANCE (clearest signal).** The standout: endgame K=2 EXACT top-1
  **0.763→0.826** (+0.063) and mean regret **0.544→0.391** (−0.15), with a clear mechanism (the
  deck-aware `supply_factor` zeroes closures the near-empty endgame deck literally cannot finish, which
  v2.7's flat `closure_p` over-credits). Midgame is ~neutral (net −4, where the deck is plentiful so
  the discount occasionally over-fires). The endgame gain is on EXACT labels — the strongest reference
  in the program. **Advance to a low-budget search pilot.**

## Interpretation (marked separately from the facts above)

- The dominant Phase-4 result is **how little any v2.8 STATIC selector moves** — divergence from v2.7
  is 16–56 / 1000 positions. This is expected and consistent with Phase 1 (~67% of misses are
  search-horizon, not leaf-addressable) and Phase 3 (cap-masking; near-constant-across-siblings terms).
  **Root-action agreement is the wrong instrument for meeple/denial** (which act through search depth),
  and a *mildly* informative one for farm/completion.
- Only **v28_completion** shows a clean, mechanism-supported, exact-label improvement, and it is on the
  ENDGAME — exactly where M2 predicted (deck-aware closure). **v28_meeple** is a marginal positive worth
  one cheap search check. The other two are killed.
- **No patch improved global root agreement materially**, so per the success rule none is promoted on
  imitation alone — survival is decided by the Phase-5 full-game search pilots, not here.

## → Phase 4 outcome

| patch | decision | reason |
|---|---|---|
| v28_completion | **advance to search** | exact-endgame top-1 +0.063 / regret −0.15, mechanism-clear |
| v28_meeple | **advance to search (weak)** | net +6 midgame, recovers its own subset 2/22, search is its real test |
| v28_farm | **KILL** | broad midgame degradation, worse endgame, recovers 1/93 of its own target |
| v28_denial | **KILL** | no movement (pre-committed kill) |

Next: mechanistic autopsy on the two survivors ([MECHANISTIC_AUTOPSIES.md](MECHANISTIC_AUTOPSIES.md)),
then a paired low-budget heur@200 search pilot (v28_completion / v28_meeple vs v2.7).
