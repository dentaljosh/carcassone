# READ_RULE — S1 GATE G1 (EXPRESSION)

> # ⛔ COMMITTED BEFORE ANY G1 STATISTIC EXISTS
>
> **Status: PRE-OUTCOME.** At the moment this file was committed, `0` G1 searches
> had been run and no `SUMMARY.json` existed under any G1 out-dir. This is the
> house rule (`CL-079`) and `CL-084`'s binding on S1 (*"no selecting-then-reporting;
> doses, arms and the branch map freeze before game 1"*).
>
> Parent design: [`DESIGN.md`](DESIGN.md) §6.2. Sizing: [`SIZING.md`](SIZING.md) §5.
> **0 games · 0 cells · 0 band · 0 `results.csv` rows · `PRODUCTION.yaml` untouched.**

---

## 1. WHAT G1 IS

G1 asks **one** question, and it is a *kill* question, not a strength question:

> At the budget the champion actually deploys, does `jrules_prior_scope = "opp"`
> **change what the champion does at all**?

It is worth buying first because it is nearly free (~13 worker-h, **0 games, 0
band**) and because a null closes the whole branch: *"opponent-node priors do not
survive 22,016 sims"* is a real, cheap, reusable result.

⭐ **Why S1 needs its own expression gate at all, stated as the mechanism.** Under
`scope=opp` the root's mover **is** the root player, so the boost is OFF at the
root **by design** — the root expansion is byte-identical to the champion's
(pinned by `search::tests::s1_opp_leaves_the_root_priors_identical_to_the_champion`
and by `tests/test_s1_opp_scope.py::test_leg_a_...`). **Every** behavioural
difference is therefore *search-mediated*: it must arrive through interior
opponent expansions and propagate back to the root. That is exactly the kind of
effect the sims-washout (`F4/Gate B`) attenuates, and it is why a `scope=all`
dose calibration does **not** transfer.

---

## 2. THE INSTRUMENT (frozen)

| item | value |
|---|---|
| script | `scripts/classical_search/jrules_priors_e4_replay.py` |
| corpus | the banked E4 archives in `measurement/e4_games/` (`--archive-dir`), **all** of them |
| budget | `--sims 1376 --k-dets 16` ⇒ **22,016 per decision** — `PRODUCTION.yaml` `fair_deploy`, i.e. what the champion actually plays. **Overrides each archive's own stamp**, deliberately: a 2752-era archive stamp would grade a budget nobody deploys. |
| reference arm | the unmodified production champion, re-searched on **every** graded ply |
| CRN | one seed (`--seed 12345`) and the same `_move_idx` on every arm ⇒ all arms search **identical determinized worlds**; a difference is the prior surface's doing and nothing else's |
| graded plies | champion-seat plies with `>1` legal action and `len(deck) > EXACT_MAX_K` (forced and exact-tail plies are skipped, as in every sibling instrument) |
| config of record | `MANIFEST.json`, written **before the first search** |
| statistics of record | `SUMMARY.json` (per-corpus) + `game_*.json` (per-archive) |

**IS-D1 is binding: config is read from `MANIFEST.json`, statistics from
`SUMMARY.json`.** No knob may be quoted from a directory name.

### 2.1 The arms (frozen, four rungs + the champion)

| arm name | dose | mask | scope |
|---|---:|---:|---|
| `s1_d0p25` | 0.25 | 31 | `opp` |
| `s1_d0p5`  | 0.5  | 31 | `opp` |
| `s1_d1p0`  | 1.0  | 31 | `opp` |
| `s1_d2p0`  | 2.0  | 31 | `opp` |

Mask **31** (the frozen `joshua_bot.PRESETS["current"]` J bundle) per the owner's
adopted answer to DESIGN §11 **Q2** — comparability with the banked `all` cell
over content purity. A `J2`-only mask is the **licensed follow-on**, not a rung
of this ladder.

⚠️ The 0.25 rung is **in** the ladder here, unlike surface B where it was a
conditional addition. Reason, stated pre-outcome: the `opp` surface is expected
to express *less*, so a floor rung that exists only if a trigger fires would be
the rung most likely to be needed and least likely to be licensed.

---

## 3. THE TWO STATISTICS (frozen)

* **E1 — root pick-flip rate.** The fraction of graded plies where the armed arm
  plays a different action than the champion. Reported with its **Wilson-95**
  interval, and the **bar is read on the point estimate** (§4), with the interval
  reported alongside as the house style requires.
* **E2 — mean root visit-distribution total-variation distance.** Per graded
  ply, `TV(champion pooled root, armed pooled root)` over the PIMC-pooled root
  visit distributions (`RustFairAgent.last_pooled_visits`), each normalized over
  its own total, summed over the **union** of actions. Pooled across the corpus
  **by ply** (`sum / n`), never as a mean of per-game means. A ply where either
  pool is empty contributes `None`, never `0.0`.

E2 exists because E1 is **lumpy**: it only moves when a change crosses an argmax
boundary. E2 is graded and cannot be zero if the surface is live.

---

## 4. THE READ RULE (FUND-SMALLEST)

> **Fund the SMALLEST dose rung that clears `E1 >= 5 %` OR `E2 >= 0.05`.**
>
> **If no rung clears either bar — including the top rung (2.0) — the branch
> reads `NO-EXPRESSION` and S1 STOPS: no cell, no band, no games.**

Both bars are taken **verbatim from DESIGN §6.2**, which proposed them before
any `opp` number of any kind existed. They are recorded here unchanged.

⚠️ **The honest risk with these bars, stated now rather than discovered later.**
DESIGN §6.2 itself says E1 under `opp` *"will be materially lower than surface
B's 13.05 %"* because every flip is search-mediated, and surface C's recorded
answer (*the champion at deploy depth already plays inside the anchor's hard
rules on ~93 % of decisions*) is an independent prior that expression will be
low. **A 5 % bar may therefore be too high for E1 and E2 may carry the gate
alone.** That is a known property of this rule, not a licence to move the bar
after reading it. If both bars are missed, the recorded answer is
`NO-EXPRESSION` — and a *later* argument that the bar was mis-set is a new
prereg, on a fresh corpus read, not a re-read of this one.

### 4.1 Branches

| branch | condition | consequence |
|---|---|---|
| `G1-EXPRESSES` | some rung clears E1 >= 5 % **or** E2 >= 0.05 | the **smallest** such dose becomes `d*`; G3's three-arm decomposition cell is licensed to be *proposed* to the owner at that dose (a G1 pass **funds nothing by itself** — the cell is a separate owner decision) |
| `G1-STRONG` | the smallest clearing rung reads **E1 >= 15 %** | DESIGN §12: the sims-washout story is dead for this surface, and the cell is worth `n = 1600` from the start. Record it; still an owner decision. |
| `G1-NO-EXPRESSION` | no rung clears either bar | ⛔ **STOP.** Owner's adopted answer to DESIGN §11 **Q6**, verbatim: *stop and record it.* Record "opponent-node priors do not survive 22,016 sims", close the branch, and do **not** escalate to option (i-b) — it shares the surface whose expression just failed. |
| `G1-VOID` | any guard in §5 fails | the read is void. Fix, re-run (resumable, no band, no games), read again. A void run is **not** a `NO-EXPRESSION`. |

---

## 5. GUARDS — every one must pass or the read is `G1-VOID`

1. **Positive control passed on every grading process.** The scope-aware §9.2
   control (`_assert_surface_b_live`) runs once per archive subprocess and
   `SystemExit`s loudly on failure. For `scope=opp` it asserts, in order:
   **(a)** root priors and root leaf value do **NOT** move — *a moved root prior
   is the defect, not the signal*; **(b)** the **pooled root stats** DO move at
   the deploy sims-per-determinization; **(c)** `Own` and `Opp` boost disjoint
   sets whose union is `All`'s, checked within each tree.
2. **Inverted leaf-hash gate.** Every arm's leaf hash **equals** the champion's
   `a36d2e15a3b3d71d`. A *moved* hash means a leaf change was smuggled into a
   prior cell — abort.
3. **Replay checksum clean.** `all_replay_scores_match == true` in
   `SUMMARY.json`. One failing archive voids the whole read.
4. **No stale wheel.** A `carc_rs` predating S1 rejects `scope='opp'` at config
   construction (fail-closed `ValueError`, never a silent champion-vs-champion
   null). The wheel must be rebuilt **per box**.
5. **`partial == false`** in every `game_*.json` — a `--limit-plies` run is a
   wiring smoke and is **never** a G1 read.
6. **`MANIFEST.json` arms match §2.1** exactly — four rungs, mask 31, scope
   `opp`, budget 1376 × 16.

---

## 6. FORBIDDEN READINGS

1. **A flip is not an improvement.** Per DESIGN §7 and the `CL-080` anchor
   (10.09 % flip → **−53.8 elo**), a *bigger* flip rate is a bigger **risk**, not
   a bigger prize. G1 measures **expression**, never quality.
2. **No elo, no margin, no band, no `results.csv` row, no governance write.**
   G1 plays zero games.
3. **`G1-EXPRESSES` does not license adoption, or even the cell** — it licenses
   *proposing* the cell. A screen aims; it does not verdict.
4. **No contrast with the banked surface-B `all` calibration is a statistic.**
   Different scope, different budget (11008-era), different corpus slice. It is
   context only.
5. **The dose that clears is not "the right dose"** — it is the smallest dose
   that is *observable*. Expression is not effect.
6. **Do not re-read this corpus under a moved bar.** See §4's stated risk.

---

## 7. WHAT WOULD MAKE THIS RULE WRONG

* If the positive control passes but E2 is *exactly* `0.0` on every rung, suspect
  the instrument before the mechanism: `0.0` across ~3,000 plies at four doses is
  a plumbing signature, not a physics one. Check `MANIFEST.json`'s resolved
  scopes and the per-ply `tv_*` fields before recording `NO-EXPRESSION`.
* If E1 and E2 disagree in direction across rungs (E1 rising while E2 falls, or
  a non-monotone ladder), the ladder is under-resolved and the honest report is
  "expression is not monotone in dose at this depth" — not a `d*`.
