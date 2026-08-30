# DEVIATIONS — CL-083 mechanism censuses (2026-08-30)

Every departure from `PREREG.md`, and every correction made after the prereg was
committed, is logged here with what was known at the time. **`PREREG.md` itself has
not been edited since its commit** (`aa07fee0`) — the definitions and bars the
verdicts are read against are the ones committed before any compute ran.

---

## D-1 — the PREREG's α = 1.00 "arithmetic identity control" is not one. DISCLOSED, NOT VOIDED.

**What the prereg said.** Census 1 declared α = 1.00 the identity control: *"α=1.00 is
the mean = the deployed rule and serves as the arithmetic identity control: its pick
MUST equal `a*` on the CVaR-eligible restriction, and any ply where it does not is
flagged as an instrument fault"*, and the instrument-fault list makes that a void
trigger for Census 1.

**What is actually true.** The premise is arithmetically wrong, and I got it wrong when
writing the prereg. CVaR at α = 1.00 is the **equal-weight** mean of the per-world Qs,
`(1/k)·Σ_i q_i(a)`. The deployed pooled Q is the **visit-weighted** mean,
`Σ_i W_i(a) / Σ_i N_i(a)`. These coincide only when `N_i(a)` is constant across worlds,
which PUCT does not deliver — a world that likes an action visits it more. So α = 1.00
is not the deployed rule; it is a *different pooling rule* (equal world weighting), and
its disagreements with `a*` are a real measurement, not a fault.

**How it surfaced.** The α = 1.00 row disagreed with `a*` on a dry run of the analyzer
over the two small non-primary profile legs. That is the control doing its job — it
caught a wrong premise, which happened to be mine rather than the instrument's.

**Resolution.**
1. Census 1 is **NOT voided**. The void trigger rested on a false premise; firing it
   would discard a sound measurement over a bookkeeping error in the control's
   justification.
2. The PRIMARY statistic is unchanged and still exactly what the prereg registered:
   `reach(α)` = CVaR-argmax ≠ **the deployed pick `a*`**, for α ∈ {0.25, 0.50, 0.75},
   and the kill bar is applied to `max_α reach(α)` over that grid. `a*` is read from
   `pooled_q_argmax` on the pooled accumulators, so the primary never depended on the
   α = 1.00 identity claim.
3. The α = 1.00 number is retained and **re-labelled** as the *equal-weight-world
   pooling reach* — a finding, not a control.
4. Two diagnostics are ADDED (post-hoc, and labelled as such wherever they appear):
   - `reach_vs_equalweight(α)` — CVaR-argmax ≠ the α = 1.00 pick. This isolates the
     marginal contribution of **risk aversion** on top of the weighting change, so the
     two mechanisms inside "CVaR pooling" are not conflated.
   - `P_star_cvar_eligible` and `reach_star_eligible_only(α)` — see D-2.

The true arithmetic identity control, which does hold and is checked, is that
`pooled_q_argmax(agg_n, agg_w, 2)` equals the recorded `pooled_argmax` — true by
construction, since the same function object produces both.

## D-2 — `a*` can fall outside the CVaR-eligible set. ADDED DIAGNOSTIC.

The prereg restricts CVaR scoring to actions with `N_i ≥ 2` in **all** k worlds
(an action with no visits in some world has no per-world Q there). Nothing in the
prereg guarantees the deployed pick `a*` clears that bar in every world. When it does
not, `a*` cannot be the CVaR pick and the ply scores as "reached" **mechanically**,
independent of any risk preference.

This is a real property of the lever as the prereg defined it — a CVaR rule genuinely
cannot name an action it cannot score — so the primary statistic keeps counting those
plies. But it is a different cause from "risk aversion prefers a different move", so
`P_star_cvar_eligible` and `reach_star_eligible_only(α)` (reach restricted to plies
where `a*` IS eligible) are reported alongside. Both are POST-HOC and carry no bar.

## D-3 — the `onset` / `extend` split was corrected to the prereg text before the census ran.

**What happened.** The first implementation of `tag_contested_seeds` tested onset as
"some key sits in a both-player component after the action that did not before". That
mis-classifies the ordinary case where a tile joins an **already** contested feature:
the tile contributes brand-new positional keys, those keys are in a both-player
component after and (trivially) were not before, so the action was tagged `onset`
when the prereg's text makes it `extend`.

**How it surfaced.** A 4-ply smoke printed onset counts of 14/44 and 36/52, which is
not what "starts a new contest" should look like.

**Resolution.** The implementation was corrected to the prereg's own words —
- `onset` is tested only over keys that **already existed in the pre-state**, so keys
  the placed tile itself creates cannot manufacture an onset;
- `extend` is a new key joining a component that already contained a contested key.

**`PREREG.md` was not changed**; the code was brought to it. The correction was made
before the census run, so no census statistic was computed under the wrong tagging.
Disclosed here because a 4-ply smoke number was seen before the fix, and the honest
record is that the error was noticed by looking at output rather than by inspection.

## D-4 — profile legs, and what the primary population actually is.

Per the prereg, the primary population for Censuses 1 and 3 is the `fixed_v1` rules
epoch. Realised counts: 277 of the 290 crux plies are `fixed_v1`; 10 are `walled` and
3 are `app_aug2`, run as a separate leg with their own R9 latch and reported
separately, never pooled. For Census 2, of 61 archive files 56 resolve to a rules
profile (`fixed_v1` 53, `walled` 2, `app_aug2` 1); the remainder are not `ok`
archives. Census 2 pools all profiles for its primary as the prereg specifies, and
reports the profile split.

## D-5 — the tie arbiter is OFF.

`governance/PRODUCTION.yaml` carries a B=64 tie arbiter alongside the k8×1376 deploy.
These censuses build the champion with `production_prior_cfg()` and **no** tiearb.
Reasons, both pre-existing: the E4 games in the corpus were played by the unmodified
champion, and the arbiter is a tie-break layer over near-equal arms that does not
change the pooled statistics either census reads. Disclosed because "deploy budget"
in the prereg could otherwise be read as including it.

## D-6 — compute placement.

All compute ran on the **laptop** (24 threads, `nice -n 19`, detached), because the
local box was hosting a live eval round. Scripts were shipped via the share rather
than committed into the laptop's pinned checkout (`CARC_REPO` env override). Nothing
in either census is a timing statistic, so the co-tenancy rule that governs timing
benches does not bind here.
