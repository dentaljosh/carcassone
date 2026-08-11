# E4 deck baseline — control-variate adjustment of Joshua's E4 margin

**STATUS: PRE-REGISTERED 2026-08-08 (written and committed BEFORE any self-play game ran).**
Descriptive measurement tooling. **No strength claim, no claim id, PRODUCTION.yaml untouched.**

## The problem

Joshua's 12 `fixed_v1`-epoch E4 games (human seat 0 vs the champion of record) are
**unpaired**: each deck was played once, in one seat assignment. Deck luck is a real
component of the margin — Phase C measured ICC 0.19 (σ_pair 12.8, σ_game ~17.75–19.6) —
so ~19% of the variance in his read is "which deck did I get", not "how did I play".
At n=12 his margin reads **mean −0.17 ± 7.06 points** (`measurement/e4_games/README.md`).

Playing paired games would remove it, but costs human hours. This experiment removes it
**retroactively and with zero human games**: the champion self-plays each of his 12 decks
K=8 times, which estimates what each deck is intrinsically worth to seat 0, and his
observed margin is read against that baseline as a **control variate**.

## Sign convention (stamped everywhere)

**positive = seat 0 = Joshua ahead.** `margin = scores[0] − scores[1]` in every
artifact, both for his archived games and for the self-play replicates.

## Inputs

The 12 archives in `measurement/e4_games/*.json` with `rules_profile == "fixed_v1"`.
The other 3 archives in that directory are **EXCLUDED**: they are different rules epochs
(2 `walled`, 1 pre-`fixed_v1` app build, incl. the 2026-08-05 98–78 win). Selection is by
the archive's own `rules_profile` field — never by `(start_rule, grid_rule)`, which the
Aug-2 build also stamps as `retail`/`centered18`.

## Self-play configuration (the deck-value instrument)

| knob | value | why |
|---|---|---|
| decks | the 12 archived `deck_seed`s | same deck Joshua played: `random.seed(deck_seed)` → `Game(**profile.game_kwargs())`, the `root_replay` contract used by `scripts/analyzer/ev_loss.py` |
| rules profile | `fixed_v1` | the epoch of those 12 games; `CARCASSONNE_FIX_R9=1` exported **before** `carcassonne_ai` imports (import-latched OnceLock) |
| both seats | `make_production_champion("fair", …)` | the champion of record |
| budget | k_dets 8 × sims_per_det 1376 = **11008** | `governance/PRODUCTION.yaml` `fair_deploy` |
| backend | **rust** (`carc_rs`), `rust_threads=1` | parallelism is spent ACROSS games, not inside one |
| leaf env | `scripts/human_anchor/env_preamble.py` PROD_ENV (curve125, flat leaf) | the production leaf, verified at construction (`verify=True`) |
| replicates | **K = 8 per deck** (96 games total) | |
| agent seeds | replicate r ⇒ seat0 `7_000_000 + 2r`, seat1 `7_000_000 + 2r + 1` | deterministic, distinct per seat and per replicate, recorded per game |

Per-game record (one JSONL line, `selfplay.jsonl`): `deck_seed`, `replicate`, both seat
seeds, `scores`, `margin_seat0_minus_seat1`, `n_moves`, `wall_secs`, `secs_per_move`,
`leaf_hash`, `deck_hash`, `rules_profile`, backend/execution, git rev.
**Checkpointing is per game** (append+fsync); `--resume` skips any `(deck_seed, replicate)`
cell already present, so a dirty box reboot loses at most the in-flight games.

## The estimator — PRE-REGISTERED

Let `m_i` = Joshua's margin on deck i (i = 1..12), `d̂_i` = the mean seat-0 margin of the
K=8 self-play replicates of deck i, `se_i = sd_i/√K`, `d̄ = mean_i(d̂_i)`.

Three estimates of his mean margin are reported **side by side**:

1. **unadjusted** — `mean_i(m_i)`, se = `sd(m)/√n`.
2. **β = 1 (naive subtraction)** — `adj_i = m_i − 1·(d̂_i − d̄)`, se = `sd(adj)/√n`.
3. **β̂ (control variate)** — `adj_i = m_i − β̂·(d̂_i − d̄)` with
   `β̂ = Cov(m, d̂)/Var(d̂)` estimated from the same 12 pairs.

**⚠️ The subtlety, stated before seeing results.** Raw subtraction (β=1) *can add
variance*. Var(m − d̂) = Var(m) + Var(d̂) − 2Cov(m, d̂); with ICC only 0.19 and a K=8
baseline that carries its own sampling noise, the `Var(d̂)` term can exceed `2Cov`, and
then the "correction" is strictly worse than doing nothing. The control-variate form with
`β̂` is the version that cannot lose *in expectation*, because β̂ shrinks toward 0 exactly
when the covariance is weak.

**HEADLINE RULE (pre-registered):** the headline estimate is **whichever of `unadjusted`
and `β̂` has the smaller realized se.** That is the only defensible criterion — a control
variate is judged on realized variance reduction, nothing else. β=1 is reported for
completeness and is never the headline.

**Two clarifications added 2026-08-08, still BEFORE any self-play game existed:**

- **The adjustment is CENTERED, so the point estimate cannot move.**
  `mean_i(m_i − β(d̂_i − d̄)) = mean_i(m_i)` for *any* β, because the centred term sums
  to zero. All three "estimates" therefore share one point estimate and differ **only in
  their se**. That is not a defect — precision is the entire deliverable — but the
  readout must say it in those words rather than presenting three numbers that look
  like three different answers.
- **se convention.** `unadjusted` and `β=1` use `sd/√n` with `ddof=1`. The `β̂` se uses
  **`ddof=2`**, paying for the estimated β. This is the conservative choice and is the se
  used in the headline comparison.
- **Supplementary, explicitly NOT the headline:** `mean(d̂)` itself — were his 12 decks
  *collectively* tilted for or against seat 0? — and the uncentred `mean_i(m_i − d̂_i)`,
  which is the "how did he do relative to what the champion scores on these same decks"
  read. Reported as description; the pre-registered headline stays the centred form.

**β̂ at n=12 is itself noisy** (its own se is roughly `sd(resid)/(√n · sd(d̂))`, and the
adjusted se understates by the ~1/(n−2) cost of estimating β). We report β̂ with its se
and do **not** treat a β̂ that differs from 0 or 1 by less than ~2 se as informative.

## Also reported (pre-registered)

- **Spread of deck values**: sd(d̂) against the mean within-deck se — i.e. do these 12
  decks differ *at all* beyond replicate noise? A one-way ANOVA-style read
  (between-deck variance minus the within-deck component) and a self-play ICC.
- **Per-deck table**: `d̂_i ± se_i` vs Joshua's realized `m_i`, so each game is labelled
  **downhill** (d̂_i > 0, the deck favours seat 0) or **uphill** (d̂_i < 0).
- **corr(d̂, m)** — the empirical analogue of the ICC that motivates the whole method.

**If corr(d̂, m) ≈ 0 and the se does not shrink, the readout must say plainly that the
method bought nothing at this n.** That is a legitimate, pre-registered outcome, not a
failure to be re-analysed into significance.

## Caveats owed by the readout

- **n = 12.** Everything here is a 12-point regression; nothing is a verdict.
- **"Deck value" is defined by the CHAMPION's own self-play margin distribution.** A deck
  worth +5 to the champion in seat 0 need not be worth +5 to a human — different players
  exploit different deck shapes. The control variate is valid as a variance reducer under
  any correlation, but its *interpretation* as "deck luck removed from Joshua's read" is
  only as good as that transfer.
- **The human is non-stationary and assisted.** Joshua is improving across these 12 games
  and some carried UI assists (see `measurement/e4_games/README.md`); the adjustment does
  nothing about either confound.
- Self-play margin is measured with both seats at the champion's own budget; the
  champion is not a perfect player, so d̂ is "value to this agent", not "value to optimal
  play".
