# 22016 vs 11008 BUDGET H2H — ADJUDICATION READ-OUT

> **BRANCH OF RECORD: `U-UNREADABLE` (READ_RULE.md §4, first-match-wins, `VOID` first).**
> Fired by the **unmodified frozen** `adjudicate.py` at `h2h22k-freeze` tip `e465c8a2`,
> `--selftest` 20/20 PASS, run on the laptop — the box that played the games, where
> `WORKERS.conf::REPO_LOCAL` resolves to the frozen checkout.
> Machine verdict: [`../h2h_22016_prep/ADJUDICATION_laptop_frozen.json`](../h2h_22016_prep/ADJUDICATION_laptop_frozen.json).
>
> **No `D` is published.** Per READ_RULE §4 this is *"not a finding about budget."*
> Two gates failed — `G-REV` and `G-TIEARB` — and **both are defects in the frozen
> instrument's own manifest-reading, not facts about the games.** Diagnosis in §3;
> proposed amendments in [`../h2h_22016_prep/AMENDMENTS.md`](../h2h_22016_prep/AMENDMENTS.md).
> READ_RULE §4 `U-UNREADABLE` explicitly contemplates this: *"Both sides' raw archives are
> kept and are **re-adjudicable after a fix**."*

---

## §1 — GATE TABLE AS FIRED

| gate | result | note |
|---|---|---|
| `G-BAND` | **PASS** | `seed_start=148000000000`, `n_decks=700`, `seatings_per_deck=2` @ `manifest.config.*` |
| `G-DECKS` | **PASS** | `n_common=700`; no out-of-range seed; no single-seat deck |
| `G-SINGLEVAR` | **PASS** | differs in exactly `k_dets` (16 vs 8) + `total_sims` (22016 vs 11008); `sims_per_det=1376` **both** sides; leaf hash, `c_puct`, `tau_p`, `leaf_quantize`, `final_select`, `value_norm`, endgame handoff all identical |
| `G-REV` | **FAIL** | encoding defect — §3.1 |
| `G-BLIND` | **PASS** | `3a0a631b` is 40-hex, ancestor of HEAD, introduced the FROZEN banner, `BLIND_PROOF` agrees. ⚠️ reads FAIL when adjudicated **off-box** — §3.3 |
| `G-LEAF` | **PASS** | cand == opp == `a36d2e15a3b3d71d` |
| `G-RULES` | **PASS** | `fixed_v1`, `r9_env_ok=true`, `r9_env_observed=true` |
| `G-BACKEND` | **PASS** | `rust`, `mixed_builds=false`, `converted_sides=["candidate","opponent"]` — the strengthening held live |
| `G-BUDGET` | **PASS** | `(16,1376,22016)` / `(8,1376,11008)`, product identity holds both sides |
| `G-TIEARB` | **FAIL** | pre-registered false-VOID class — §3.2 |
| `G-EXACT` | **PASS** | `exact_k=2`, `marginalized`, identical both sides |
| `G-N` | **PASS** | `n=1400`, `n_failed=0`, failure rate **0.000%**, `n_common=700 ≥ 560` |
| `G-SAT` | **PASS** | winrate `0.52036` ∈ [0.35, 0.65] |
| `RECON` | **PASS** | analyzer vs from-scratch witness agree to `rel 1e-6 / abs 1e-9` on all five statistics |

**12 PASS / 2 FAIL.** No gate failed on a property of the *games*.

---

## §2 — THE STATISTIC (⚠️ **NOT PUBLISHED AS `D`**)

The frozen `RECON` gate prints the analyzer and witness values in order to compare them, so
these numbers exist in the frozen instrument's own output. They are recorded here as
**gate diagnostics**. **No READ_RULE §4 branch licensing them has fired.**

```
analyzer (summary.json)     witness (recomputed from 1400 raw records)   agree
paired_mean_margin  1.2292857142857143   1.2292857142857143              yes
paired_z            2.5198760650731833   2.5198760650731833              yes
n_paired            700                  700                             yes
winrate             0.5203571428571429   0.5203571428571429              yes
elo                 14.153415640509905   14.153415640509905              yes
```

Derived: `SE = 0.48784 pts`, realized `2σ = ±0.9757 pts`, realized `σ_D = 12.91`.

⚠️ Three things a successor must not misread:

1. **`z = 2.52` is on the `H-POSITIVE` side of the §4 bar** (`z ≥ +2.0`). That branch **did
   not fire**, because §3.1 `VOID` is checked *first* and won. Whether it fires is now a
   question about the two gate amendments in `AMENDMENTS.md`, and that is an **owner
   ratification**, not an adjudicator's call. Nobody may cite `+1.23 pts` as this cell's
   result while the branch of record is `U-UNREADABLE`.
2. **Realized `σ_D = 12.91` came in *below* every sizing model** (A 13.15 / B 13.60 /
   C 14.67 — the cell sized on the conservative C). The instrument resolved slightly
   *tighter* than designed: realized `2σ = ±0.976 pts` against the `±1.109` sizing claim.
3. **The own-ratio elo scale is a witness ANOMALY.** `elo_D / D = 14.153 / 1.2293 =
   **11.51 elo/pt**, which is **outside** the pinned in-family bracket `[16.74, 19.35]`.
   READ_RULE §1 requires this be **FLAGGED as a witness anomaly and never used as a branch
   input** — and it is flagged here. Any elo display, on any future branch, must carry it.
   (For reference only, through the *pinned bracket*: `D` ≈ 20.6 – 23.8 elo; realized `2σ`
   ≈ ±16.3 – 18.9 elo.)

**Per-side witness stats:** W 714 / L 657 / D 29 over 1400 games; `winrate_z = 1.523`
(vs the deck-paired `z = 2.520` — the paired estimator is the powered one, as designed).
`champ_prefix_ms_per_move` (⚠️ the **candidate** side) `3449.2 ms`; `rung_ms_per_move`
(the **opponent**) `1721.3 ms` → realized candidate/opponent ratio **2.00×**.
`champ_timeouts = 0`; `champ_latched_games = 1400/1400`; `solver_secs_per_game = 1.375`;
`failed_by_seat = {0: 0, 1: 0}`; `failed_classes = {}`; `validity_trigger_fired = false`.

---

## §3 — WHY THE TWO GATES FAILED

Both failures share one root cause: **the selftest fixtures model the manifest
`READ_RULE.md` *describes*, not the manifest `eval_fair_puct.py` actually *writes*.** The
fixture generator synthesises idealised fields, so neither defect could ever be caught by
`--selftest`, and both were frozen blind. Neither is reachable by any archive of this design
— i.e. **this instrument could not have returned a readable verdict for any outcome.**

### §3.1 — `G-REV`: two different encodings compared for equality

```
code_rev='e465c8a270-dirty'  vs  PINNED_SRC_REV='e465c8a270350d17b357fd1520abf64685be951a'
```

`PINNED_SRC_REV` is a full 40-hex sha. `manifest.code_rev` is written by
`src/carcassonne_ai/run_manifest.py::code_rev()`, whose encoding is
`git rev-parse --short HEAD` **+ `"-dirty"` if `git status --porcelain` over the *whole
repo* is non-empty**. A run of this design writes ~2,800 of its own artefacts into
`measurement/` *inside the repo*, so `-dirty` is **self-inflicted and unavoidable**.
`e465c8a270` is the exact 10-hex prefix of the pinned sha.

The **substance** of `G-REV` is independently discharged, three ways:

- the frozen launcher's own `assert_rev_pinned()` compares the **full** `git rev-parse HEAD`
  to `PINNED_SRC_REV` and `exit 3`s on mismatch — it ran fail-closed at **all 19 boundaries**
  and never fired;
- `run_cells.sh::src_is_clean()` scopes dirtiness to `CODE_PATHS = (src engine scripts rust
  tests pyproject.toml setup.py)` and likewise never fired;
- `SRC_CLEAN.jsonl` records 19 boundaries (`pre-flight`, `before/after-pass-1..8`,
  `before/after-seal`), **every one `src_clean=true` with no head drift**; the adjudicator's
  own scan reports `dirty=none`;
- live post-run `git status --porcelain` on the laptop: **235 dirty paths, all under
  `measurement/`, plus one stray `cp3_laptop.log` — ZERO under any `CODE_PATH`.**

### §3.2 — `G-TIEARB`: the pre-registered false VOID

```
cand_tiearb.enabled=False    stray keys = config.champion.tiearb_{b,enabled,eps,j,mode,salt}
```

READ_RULE §3 `G-TIEARB` names this class **verbatim, in advance**:

> *"A future harness that starts emitting a benign disarmed `tiearb`-named field would
> therefore trip this gate; that is a **false `VOID`, which is the recoverable direction**,
> and the fix is to **amend the gate**, never to relax it into interpreting armed-ness."*

`eval_fair_puct.py` mirrors the **candidate's** arbiter config into the candidate's own
champion block as six flat `tiearb_*` fields on every run, armed or not. They are
**byte-identical** to the `cand_tiearb` subtree §3 already exempts:

```
cand_tiearb            {enabled: False, B: 16, J: 4, mode: 'argmax', salt: 'tiearb2-deploy-v1', eps: 0.0}
config.champion.tiearb_* {enabled: False, b: 16, j: 4, mode: 'argmax', salt: 'tiearb2-deploy-v1', eps: 0.0}
```

They are an **alias of the exempt subtree, not a new one.** `DEVIATIONS.md` §9 bar 4 records
this alias **by name, before game 1** (*"`cand_tiearb.enabled == false`,
`champion.tiearb_enabled == false`"*) and reads it as evidence **for** disarmament.

**The arbiter is verifiably OFF on both sides:** `cand_tiearb.enabled=false`;
`champion.tiearb_enabled=false`; and the opponent block carries **no `tiearb`-named key of
any spelling** (`opponent.champ_cfg` tiearb keys = `{}`) — consistent with the structural
fact READ_RULE cites, that `eval_fair_puct.py` exposes no `--opp-tiearb-*` flag at all.

### §3.3 — `G-BLIND`: an off-box artefact, **not** a defect

`WORKERS.conf::REPO_LOCAL=/home/doctor/projects/carcassone` names the path the cell **ran**
at. On the laptop that path is the frozen checkout (`HEAD = e465c8a2`, branch
`h2h22k-freeze`) and `G-BLIND` **PASSES**. On the local box the same path is a different
checkout (`HEAD = ecbbc616`, branch `tiearb2-stage2`), so `merge-base --is-ancestor` reads
`False` and the gate FAILs for a purely environmental reason. Verified both ways:

```
git -C /home/doctor/projects/carcassone            merge-base --is-ancestor 3a0a631b HEAD  -> rc=1  (local box)
git -C <wt-h2h22k worktree, HEAD=e465c8a2>          merge-base --is-ancestor 3a0a631b HEAD  -> rc=0
git -C /home/doctor/projects/carcassone (laptop)    merge-base --is-ancestor 3a0a631b HEAD  -> rc=0
```

**Adjudicate this cell on the laptop, or pass an explicit repo override.** The verdict of
record above was taken on the laptop for exactly this reason.

---

## §4 — EXECUTION AND COST

| item | value |
|---|---|
| wall-clock | `07:08:52Z` → `13:54:02Z` = **6 h 45 m 10 s** (6.75 h) |
| projection | **~6.1 h** (`DEVIATIONS.md` re-projection) / 6.6 h (`DESIGN.md` §7.2) — realized **+10.7%** vs 6.1 h, **+2.3%** vs 6.6 h |
| passes | 8 + seal (`MAX_PASSES=20`; 7 timed out at 3400 s and resumed under `--shared-claim`, pass 8 `rc=0` in 508 s) |
| W | 22 (laptop, per amendment **A3**; `nproc=24`) |
| REALIZED worker-s/game | pass 1–7: **385, 381, 372, 381, 385, 379, 377**; pass 8 (24-game tail): 465. **Run-weighted mean ≈ 382** (22 × 24 309 s ÷ 1400) |
| vs models | **−1.5%** vs the 388 like-for-like model · **−13.6%** vs the 442 design model · **+10.4%** vs the 346 smoke re-projection |
| failures | `n_failed = 0`, failure rate **0.000%** (`G-N` bar 2%; launcher breaker 10%) |
| orphan claims | 22 swept after each timed-out pass (one per worker; expected under `--shared-claim` timeout) |
| RAM | `MemAvailable` 10.80–10.87 GB throughout, floor 800 MB — never near |

The 442 model's conservatism was already predicted pre-launch by `DEVIATIONS.md` (~22% at
W22) and traced to the candidate/opponent cost ratio being sublinear at smoke (1.85×). The
**realized** ratio is **2.00×** (3449.2 / 1721.3 ms/move), i.e. the doubling priced almost
exactly linearly in production — so the model's conservatism came from the W2→W22 contention
factor, not from sublinearity.

---

## §5 — LAUNCH DEVIATIONS ON RECORD

`DEVIATIONS.md`: **A1** `CARCASSONNE_FIX_R9=1` exported in the caller env (independently
confirmed by `G-RULES`: `r9_env_observed=true`) · **A2** launcher stdout to a wrapper log
rather than `/dev/null` · **A3** `W_LAPTOP` 26 → 22, a pre-game-1 amendment committed at
`e465c8a2` (= the branch tip and `PINNED_SRC_REV`). Plus one disclosed wording drift (§9
bar 5 names the wrong non-fatal warning string; `G-BUDGET` unaffected and PASSing).

---

## §6 — WHAT IS OWED

- **`docs/LEVER_INDEX.md` budget-headroom decay-bound row** — `DESIGN.md` §10 requires an
  edit **in every branch, `U-UNREADABLE` included**: a *"re-test attempted, void, band not
  spent by the gate failure"* line, so the next reader's grep cannot miss that it was tried.
- **Band `148e9`** — real game records exist on it, so the `RELEASE-IF-NEVER-LAUNCHED`
  clause does **not** apply. The band is spent; a re-adjudication of *this* archive needs no
  new band.
- **Owner ratification of `AMENDMENTS.md`** before any `D` is published. ⚠️ Integrity
  disclosure: the amendments were authored **after** the frozen `RECON` gate printed the
  statistic. That ordering is unavoidable (RECON must print both values to compare them) but
  it is real, and it is why the amendments are a **proposal for owner ruling**, not a
  re-adjudication taken on the adjudicator's own authority.
- **No `results.csv` row, no `PRODUCTION.yaml` change, no `CLAIM_REGISTRY` mint** follows
  from `U-UNREADABLE`.
