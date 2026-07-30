# PROPOSED (not funded): the unmeasured pair — CL-067 net@2752 vs champion@11008

> **Status: PROPOSED 2026-07-30 ~01:15, awaiting Joshua GO. No band claimed, nothing launched.**
> Drafted during rodv3 turn-1 gen (which this does not touch). Becomes a prereg only
> when funded — at that point fill the band, commit before the first game.

## Why this cell exists

The rodv3 awakening premise was paraphrased as "the operator beats its teacher at 2752."
The measured fact is narrower: net+search@2752 beats the **same-budget classical**
champion@2752 (+35.7 ± 12.3, CL-067, bands 52e9+56e9). The net's actual corpus teacher
ran at **k8×1376 = 11008** (corpus manifest, `distill_strong_20260723/iter_03/manifest.json`);
against *that* player the net is **UNMEASURED in either direction** (no results.csv row;
BURIED_CAVEATS_AUDIT F1 as corrected in 9e00184).

Two cross-band derivations give **opposite signs** — via CL-060's budget-only cell the
net lands ~+8 above its teacher; via CL-067's counterevidence cost-argument, ~14 below.
Both are the transitive-through-a-shared-baseline maneuver the audit's F2 documents
inverting a +50 contrast. Only a direct head-to-head settles it.

## What each outcome funds

- **Net@2752 ≥ teacher@11008** → the flywheel premise is solid in its strong form:
  the operator produces data *above* its own corpus tier at ¼ the compute. Funds the
  gen@11008 escalation debate from evidence, and turn-1's gate reads cleanly.
- **Net@2752 < teacher@11008** → the awakening premise weakens to "above same-budget
  classical only"; gen-at-corpus-teacher-budget (~29 h local / ~20 h fleet) becomes the
  *only* clean lever-6 test, and a DEAD turn-1 gate is expected rather than informative.
  Saves funding that 29 h on a hunch.

## Design (fill band at funding time)

| knob | value |
|---|---|
| candidate | CL-067 net-prior fair agent, k4×688 = 2752 (net_backend torch, orch on local) |
| opponent | production champion `puct_priors_v29_bmild_cap8`, **k8×1376 = 11008**, parallel_workers per PRODUCTION.yaml |
| n | 400 deck-paired (200 decks), fresh band via BAND_CLAIMS.txt — **±12-ish paired σ**; the derived gap candidates (±8, ∓14) sit near 1σ, so treat a |z|<2 result as bracket-narrowing, not a verdict; pre-commit an n→800 extension branch if |elo| lands in [5, 25] |
| stats | paired elo + deck-paired margin, both reported; sign-agreement required for any claim |
| cost | opponent ~2.2 s/move × ~72 moves + candidate ~5.6 s/move × ~72 → est. **~6–8 h two-box** at eval W from the smoke docs; re-smoke 10 games before the full run (pre-flight rule) |
| when | after rodv3 turn-1 gen+train completes (boxes busy until then); can run concurrently with the turn-1 gate on the other box if both are funded |

## What this cell is NOT

Not a strength lever, not part of rodv3 turn 1 (no interaction with its gate), not a
substitute for the gate. It prices the **premise**; the gate measures the **derivative**.
