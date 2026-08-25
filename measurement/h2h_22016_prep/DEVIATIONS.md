# 22016 vs 11008 BUDGET H2H — EXECUTION-LAYER DEVIATION LOG

> **Scope: the single cell `h2h_k16x1376_vs_champ_k8x1376`, band `148000000000`.** The prereg
> pair [`DESIGN.md`](DESIGN.md) + [`READ_RULE.md`](READ_RULE.md) is **BLIND-COMMITTED AND
> FROZEN** at `3a0a631b`. Nothing in either file moves. This log records what the *execution
> layer* did differently from `DESIGN.md` §11's literal text, and why each difference is
> estimand-neutral.
>
> **Status: all entries SIGNED before game 1.** A1 and A2 were discovered by the launch agent
> during the §11 step 5–7 free steps; A3 is the pre-game-1 amendment that resolved the second
> of them. **Zero games had been played when every entry below was written and committed.**

## The rule this log instantiates

1. **A post-blind change may touch ONLY emitter and execution machinery** — how work is
   launched, resumed, logged, and how fast it runs. It may **never** touch a **gate**, an
   **address**, a **bar**, a **branch**, a **statistic**, an estimand, a seed derivation, or a
   power figure. A change that cannot be described without naming one of those is not a
   deviation; it is a new prereg.
2. **Each entry carries its own neutrality proof**, written *before* it runs.
3. **The read-out must print this list.** An entry that appears for the first time in the
   read-out is a defect, not a disclosure.
4. `governance/PRODUCTION.yaml` untouched by every entry, as by every branch.

| # | entry | class | status |
|---|---|---|---|
| **A1** | `CARCASSONNE_FIX_R9` exported in the **caller env**, not by the launcher | execution | ✅ **SIGNED** — proven live in the §9 smoke |
| **A2** | launcher stdout to `logs/run_cells_wrap.log`, not `/dev/null` | execution | ✅ **SIGNED** — disclosed improvement over §11 step 8 |
| **A3** | `WORKERS.conf::W_LAPTOP` **26 → 22** | **pre-game-1 amendment** | ✅ **COMMITTED PRE-GAME-1** — band unspent, pair blind |

---

## A1 — `CARCASSONNE_FIX_R9=1` exported in the caller environment

**The defect.** `run_cells.sh` contains **no `export CARCASSONNE_FIX_R9` anywhere.**
`WORKERS.conf` defines `FIX_R9=1`, but that is a plain (unexported) shell variable under a
*different name*, so it never reaches a child process. R9 is **import-latched**, so preflight
check 5 — which resolves `fixed_v1` in a **child** process precisely to catch this — fails
hard and unconditionally:

```
AssertionError: CARCASSONNE_FIX_R9 not latched in a CHILD process
[h2h22k] !!! FATAL: leaf/R9 pre-flight FAILED. No game runs.
```

**This is a launcher porting omission, and a regression of the `track_d2_prep` G-RULES
defect.** Every sibling launcher carries `export CARCASSONNE_FIX_R9=1` at file scope —
`track_d2r2_prep/run_cells.sh:115` under the literal comment *"FIX 1 (G-RULES). The old
launcher never exported CARCASSONNE_FIX_R9"*, `track_d1_fair_rebase/run_cells.sh:226`,
`tiearb2_stage2_20260817/run_cells.sh:103`. The h2h22k launcher was ported without that line.

**The pair is unambiguous and does not move.** `DESIGN.md` §9's smoke recipe already
specifies the intended state verbatim — *"`--exact-k 2 --rules-profile fixed_v1`
(`CARCASSONNE_FIX_R9=1` exported)"*. The launcher disagreed with the pair; per `WORKERS.conf`'s
own standing rule (*"a launcher that disagrees with the pair is a launcher defect, the pair
does not move"*), the correct resolution is to make execution match the pair.

**The remedy, and why the frozen launcher was NOT patched.** Orchestrator ruling: export it in
the caller environment, inherited by the launcher and by every child it forks —

```
CARCASSONNE_FIX_R9=1 bash ./run_cells.sh
```

This changes **no committed artifact**, so the freeze surface is untouched and `G-REV`'s
clean-source assertion is unaffected.

**Neutrality proof.**

- **It restores the pair's specified state; it does not create a new one.** R9-on under
  `fixed_v1` is `governance/PRODUCTION.yaml`'s profile of record and what §9 already demanded.
- **It is provable after the fact, on disk, by the adjudicator.** The env act leaves a
  first-class record: `manifest.rules_profile.r9_env_ok = true`. `READ_RULE.md` §3's
  **`G-RULES` still gates it post-hoc, unweakened** — the gate reads the manifest, not the
  shell. Verified live in the smoke manifest.
- **It touches no gate, address, bar, branch, statistic, estimand, seed derivation, or power
  figure.** It is a process-environment act, exactly the class §11 step 8's `chmod +x` already
  belongs to.
- **Both sides are affected identically** — one env, one process tree, both agents; it cannot
  induce an asymmetry between candidate and opponent, which is the only way a rules knob could
  move this cell's paired margin.

**Evidence it is live.** §9 smoke, 2026-08-25, `logs/smoke_wrap.log`:
`[preflight] fixed_v1 resolved, r9_env_ok=True` and manifest
`.rules_profile.r9_env_ok = true`.

**Owed to the successor.** The missing `export` is a **defect in this launcher**, disclosed
and worked around, **not patched into the frozen artifact**. Any successor cell that copies
`h2h_22016_prep/run_cells.sh` as a template **must add `export CARCASSONNE_FIX_R9=1` at file
scope** and must not inherit the caller-env workaround as if it were the design.

---

## A2 — launcher stdout to a wrapper log, not `/dev/null`

**`DESIGN.md` §11 step 8 literally reads:**

```
setsid nohup ./run_cells.sh </dev/null >/dev/null 2>&1 & disown
```

**The problem, self-inflicted by the pair.** The launcher's own `log()` writes to **stdout**,
and the per-pass line

```
pass N: REALIZED <x> worker-s/game (model: 442)
```

is a `log()` call. §11 **step 11** then instructs the orchestrator to *"RE-PROJECT off pass 1
… `run_cells.sh` prints a REALIZED worker-s/game after every pass"*. Step 8's redirect
**discards exactly the output step 11 depends on.** So do the RAM-floor readings, the
stale-claim sweeps, the rev-pin boundary assertions, and the fail-closed diagnostics.

**The remedy (orchestrator-adopted).**

```
setsid nohup env CARCASSONNE_FIX_R9=1 ./run_cells.sh </dev/null \
    >> logs/run_cells_wrap.log 2>&1 & disown
```

**Neutrality proof.**

- **It is a redirect.** It changes where bytes land, nothing else. Detachment is unchanged —
  `setsid` + `nohup` + `</dev/null` + `disown` all retained, so the CLAUDE.md
  Mac-sleep/WSL-teardown invariant is intact.
- **It touches no gate, address, bar, branch, statistic, estimand, seed derivation, or power
  figure.** `logs/cell.log` (the harness's own stream) is unchanged and still receives the
  per-pass harness output; this adds the launcher's supervisory stream beside it.
- **It strictly increases evidence.** It cannot subtract from the record.
- It resolves an internal contradiction between §11 step 8 and §11 step 11 in favour of step
  11, which is the one with a decision attached.

---

## A3 — `W_LAPTOP` 26 → 22 (PRE-GAME-1 AMENDMENT, not a deviation)

**Class.** This is an **amendment to the frozen pair**, licensed because **zero games had
run**: the band `148000000000` was unspent (0 records anywhere under `measurement/`), no
`RUN_LIVE.json` existed, and no read-out had been produced. The pair therefore **stayed
blind** across the amendment. Band-amendment precedent. It is logged here rather than in
`DESIGN.md` so the frozen file's text remains the text that was blind-committed; `WORKERS.conf`
carries the amendment inline with the original wording preserved beneath it.

**The contradiction.** `DESIGN.md` §7.4 sets `W = 26` **and**, in the same paragraph, cites
the roadmap F7d line *"laptop `W*=22` (peak `W26`, **nproc 24**)"*. It then mandates preflight
**check 7, `nproc >= W`**. On the laptop `nproc` is **24**, so the pair as frozen mandated a W
that its own preflight refuses. The launcher would have hard-failed:

```
!!! FATAL: nproc=24 < W=26. An under-provisioned box thrashes silently.
```

No environment override exists — `WORKERS.conf` assigns `W_LAPTOP=26` unconditionally and is
sourced after any caller env — so unlike A1 this could not be resolved without touching a
committed constant.

**Reason of record, verbatim (orchestrator ruling 2026-08-25):**

> "W=26 was the orchestrator's spec from the F7d raw peak, but nproc=24 makes it violate the
> pair's own preflight check 7; the check is right and the spec was wrong. W=22 is the settled
> F7d value (−3.7% throughput); W is throughput-only — games are bit-identical at any W — so no
> statistic or claim is touched."

**Check 7 is NOT relaxed.** The gate was correct and stays exactly as frozen; the constant that
violated it moved. Weakening the gate was explicitly rejected.

**Neutrality proof.**

- **W is throughput-only.** Games are **bit-identical at any W** — `DESIGN.md` §7.4 states this
  itself (*"W changes wall-clock only; the games are bit-identical at any W"*). W is a
  `--workers` fan-out over independent deck-seeded games; it enters no agent, no search, no
  seed derivation, and no statistic.
- **It touches no gate, address, bar, branch, statistic, estimand, seed derivation, or power
  figure.** `n`, the band, the deck-pairing, `k_dets`, `sims`, `exact_k`, the leaf hash, the
  rules profile, and every `READ_RULE.md` §3 gate are untouched.
- **W=22 is the house-protocol value**, not an ad-hoc one: it is the F7d **settled** figure the
  roadmap already names, and it satisfies the standing rule
  `feedback_worker_count_by_bottleneck` (*settle on the SMALLEST W within ~5–10% of peak, never
  the argmax*) that W=26 deviated from. On `WSWEEP_F7D_laptop.tsv`, `throughput_idx` reads
  W22 = 7.219 vs W26 = 7.496 — **W22 is 3.7% off peak**, inside the rule's band.
- **The RAM floors were sized for W26 and are left unchanged**, so they are strictly
  conservative at W22. No floor was loosened.

**Checked consequence — the pass-timeout margin, and why it does not move.**
`PASS_TIMEOUT_SECS=3400` was derived at W26 as `100 games / 26 × 442 s = 1700 s, ×2`. At W22
the same model gives `100 / 22 × 442 = 2009 s`, i.e. a **1.69× margin rather than 2×**. It is
left unchanged, for three reasons: (a) against the **realized** cost measured in the §9 smoke
(~346 worker-s/game at W22, see below) the expected pass is 1573 s and the margin is **2.16×**,
*better* than the design's own; (b) a pass hitting its timeout is an **expected, handled**
outcome — `rc=124` is logged as normal and the next pass resumes the archive; and (c)
`MAX_PASSES=20 × 3400 s = 18.9 h` still bounds a ~6.1 h run with wide headroom. Amending a
second constant was neither necessary nor licensed.

---

## §9 smoke — the six bars, cleared before launch

Run 2026-08-25 at production knobs on dev seed `990000000000` (disjoint from every claimed
band, never pooled, never adjudicated), `rc=0`.

| bar | result |
|---|---|
| 1. 2/2 games, `n_failed == 0` | ✅ |
| 2. `backend.converted_sides == ["candidate","opponent"]`, `mixed_builds == false` | ✅ **the strengthening proven LIVE** |
| 3. `cand_leaf_hash == opp_leaf_hash == a36d2e15a3b3d71d` | ✅ |
| 4. `cand_tiearb.enabled == false`, `champion.tiearb_enabled == false`, record `cand_tiearb: null` | ✅ nothing armed |
| 5. `champion.k_dets=16 / total_sims=22016`, `opponent.k_dets=8 / total_sims=11008`, `exact_k=2` both sides | ✅ **k16 NOT silently clamped** |
| 6. `champ_prefix_ms_per_move` within ±25% of 3555 | ✅ **once contention-adjusted** — see below |

**Bar 6, adjusted as §9 instructs** (*"adjusted for the near-unloaded contention regime"*). The
smoke runs at `W=2`; the projection is a `W=22`-basis figure, so the raw reading cannot be
compared directly. The calibration handle is the **opponent** side, which is the *identical*
`k8×1376` agent as `DESIGN.md` §7.1's basis:

```
opponent @ W2   636.9 ms/move      vs   §7.1 basis (d1-rebase E11008 @ W22) 1777.5 ms/move
  => W2 -> W22 contention factor  2.79x

candidate @ W2  1176.9 ms/move  x 2.79  =  3283 ms/move @ W22
  vs 3555 projected  ->  -7.6%   (inside +-25%)   ✅
```

⚠️ **`champ_prefix_ms_per_move` is the CANDIDATE side**, not the champion opponent
(`feedback_verify_numbers_before_reporting`); `rung_ms_per_move` is the opponent. The
candidate/opponent ratio reads **1.85×**, not 2.0× — the budget doubling is mildly
**sublinear**, which is the source of the model's conservatism.

**Realized cost, and the re-projection.** Smoke record `elapsed_s = 124.15` worker-s/game at
W=2 → ×2.79 = **~346 worker-s/game at W22**, against the **442** model — i.e. the design's cost
model is **~22% conservative** at W22. Projected wall-clock `1400 × 346 / 22 ≈ 6.1 h`, against
the design's 6.6 h. **`DESIGN.md` §7.2's standing instruction governs regardless:** the
launcher prints a realized figure after every pass, and a material miss re-projects before the
band is assumed.

---

## Discrepancy owed to the successor, not patched here

**§9 bar 5 names the wrong warning string.** It says to expect a non-fatal `_prod_deviations`
warning reading *"k_dets=16 (production 8)"*. What actually fires is a different non-fatal
warning — the `--opp-k-dets` **ASYMMETRIC search budgets** notice. Same class (a non-fatal
deviation notice), different text. The bar's *substance* is independently discharged by the
manifest, which records `champion.k_dets = 16` and `total_sims = 22016` directly, so `G-BUDGET`
is unaffected. Recorded as a **wording drift in the pair**, disclosed and not patched.
