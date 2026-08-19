# S2 STRATUM VOID — disposition, and the scale-dependence finding

> **`G-DISJOINT` conjunct (iii) was violated on S2 and the pre-registered consequence fired:
> the S2 stratum is VOID.** Rung 3's primary (`Δ_ora`, S2-only) has no corpus. **The void is not
> curable by generating more games** (R4-3 rule 7 / §2b(iii)); the answer is a successor prereg.
>
> **Nothing was scored. No `arb`, `ora`, `Δ` or CI exists for any position of this run.** The
> gate fired at the corpus stage, before any leg. Everything below is a **corpus-structure
> count** — the class `PREREG_FAILURE.md` §3.3 already established as non-leaking.
>
> **`governance/PRODUCTION.yaml` untouched. No claim minted. No strength row. No band retires:
> nothing was decision-influenced, because nothing was decided.**
>
> Rulings on what remains readable: [`ADJUDICATION_R4_GATES.md`](ADJUDICATION_R4_GATES.md).

## 1. The numbers, as reported

| stratum | carried | residual | `n_excluded` | rate | bound | void |
|---|---|---|---|---|---|---|
| S1 | 0 | 1 | **1** | 0.00074 | 7 | `False` |
| **S2** | **28** | **1** | **29** | **0.02636** | **6** | **TRUE** |

Every other conjunct of `G-DISJOINT` held: **all seven comparisons zero at the rid and root
layers**, `strata_root_overlap = 0`. Every other gate PASSED — `G-DRAW` **2408/2408** (its
first-ever emission), the N-file `G-BAND` clean across all six files, supply **S1 1344 ≥ 1283**
and **S2 1064 ≥ 1045**, `CORPUS_UNION` clean with the banked tree untouched. **The corpus was not
short and was not leaky. It was degenerate in one specific, measurable way.**

## 2. ⭐ The finding, stated as a first-class result: collision density is NOT a constant of the generator

**All 30 exclusions, both strata, are at ply 2.**

| corpus | games generated | positions | collisions | density |
|---|---|---|---|---|
| S1, banked | 350 | 551 | 1 | 0.181% |
| S1, full | 858 | 1,344 | 1 | 0.074% |
| **S2** | **5,340** | **1,100** | **29** | **2.636%** |

> ⚠️ **CORRECTED 2026-08-19 — this section originally paired "858 games" with "0.181%" and called
> the S2 figure "14.6× the density the bound was calibrated against, from the same generator at the
> same knobs; the only thing that changed is how many games were mined." THAT COMPARISON IS
> CONFOUNDED AND THE QUOTED SENTENCE IS WITHDRAWN.** Two things are wrong with it. **(i)** It pairs
> S1's *full* game count (858) with S1's *banked* rate (1/551) — two different corpora. **(ii)**
> More seriously, it compares **S1 against S2**, which are **different strata with different mining
> predicates**: S1 mines *uniform tied plies* at `--max-per-game 4`, S2 mines *capped-only plies* at
> `--max-per-game 3`. **The knobs did NOT stay the same and the population did not either.**
>
> **What the data actually supports.** ⛔ **RE-CORRECTED 2026-08-19 (second reversal, both errors
> named).** The paragraph that stood here claimed the S1-vs-S2 gap was **confounded between scale
> and stratum**, on the ground that capped plies are *"disproportionately ply-2"*. **That mechanism
> is refuted by the corpora's own `ply` fields: S1 ply-2 share `35/1344 = 2.60%`, S2
> `28/1064 = 2.63%` — identical.** There is no stratum mechanism to invoke.
>
> **And the same-currency contrast the correction said was unavailable does exist**, on the same two
> final builds: internal-dupe density **S1 `1/1344 = 0.074%` @ 858 generated games** vs **S2
> `3/1064 = 0.282%` @ 5,340** — the same quantity at two scales, **3.8× on 6.22× the games**,
> consistent with the fitted `b ≈ 0.906`. ⇒ **THE SCALE-GROWTH READING IS RESTORED in the correct
> currency.**
>
> **Both errors on the record:** (1) the *original* text compared **mismatched** quantities (S1's
> banked rate against S2's) **across strata** — that defect was real and its correction stands;
> (2) the *replacement* generalised **collision** ply to **corpus** ply, which is the same
> inferential error later found in the R5 failed-record expectation. **The fix was to find the
> same-currency contrast, not to invent a mechanism.**
>
> **What survives unchanged.** The **a priori pair-counting argument** in the next paragraph is
> untouched by this: collisions are counted over pairs and grow ~quadratically in games while a
> linear-in-`n` bound grows linearly, so **such a bound must eventually fire for any generator with
> a nonzero revisit rate.** That is theory, not this measurement. **What is withdrawn is the
> empirical magnitude** — the "14.6×", the "6.22× games → 29× collisions", and the "2.34× steeper
> than pair-counting" exponent — all of which read a scale effect off a cross-stratum contrast.
> Disentangling them is now the **primary** purpose of the R5 calibration sweep, not a refinement of
> it ([`rung3_r5/DESIGN.md`](rung3_r5/DESIGN.md) §R5-1.0).

**Mechanism.** Early-game boards are a *small space*. At ply 2 the reachable set is tiny compared
with the number of games drawn from it, so revisits are not an accident — they are the birthday
problem. The more you mine, the more certainly you re-derive a board you have already seen.

**Why this had to break the bound eventually — the structural point.** Collisions are counted over
**pairs** of positions and grow ≈ quadratically in games mined; the bound `⌈0.005 × n⌉` grows
**linearly** in positions, hence linearly in games. ⇒ **For any generator with a nonzero revisit
rate, a linear-in-`n` bound is asymptotically guaranteed to fire.** ⭐ **This is an A PRIORI
argument and it stands on its own** — it needs no measurement, and the correction above does not
touch it. So the R4 bound was not merely calibrated at the wrong scale: **it is the wrong shape.**
⚠️ **What this paragraph originally added — "6.22× more games produced 29× more collisions
(quadratic predicts ≈39, linear ≈6)" — is WITHDRAWN with the correction above**: that ratio is the
cross-stratum contrast, so it cannot date the growth. **The shape argument is theory; the exponent
is not yet measured**, and measuring it within one stratum is what §R5-1.1's sweep is for.

**This is a real property of champion self-play worth carrying forward**, independent of this
campaign: *the "fresh corpus" premise degrades with corpus size, and it degrades first at low
plies.* R4-3 rule 8 pre-registered exactly this reading — "at that density, transposition
degeneracy is a property of the **generator** and 'fresh corpus' is the wrong description — a
different finding, which must surface rather than be absorbed." **It surfaced. The rule worked.**

## 3. What is NOT concluded

- **Nothing about `J > 4`.** Rung 3 is unmeasured, not answered. `X-FREE`, `X-INCONCLUSIVE` and
  every other branch are **not** fired; "the cap was free" and "the cap costs nothing" remain
  **forbidden readings**, as does any claim that the rung was tested.
- **Nothing about rung 2.** See the separate adjudication.
- **No revision to any bar, prediction or branch condition.** The 1.400 / 1.244 multipliers and
  the `sd_Δ` bracket are untouched.

## 4. What a rung-3 successor requires

1. ⭐ **A scale-aware bound.** Either model density against **games mined** and set the bar at the
   scale the run will actually reach, or **calibrate at the governed scale** — never calibrate at
   858 games and govern at 5,340. Given §2's shape argument, a bound of the form `⌈k·n⌉` is
   probably wrong at any `k`; a bound in **collisions per pair**, or an absolute count derived
   from a fitted density-vs-games curve, is the shape that can hold across scales.
2. ⭐ **A mining ply-floor, which removes the degenerate space outright.** All 30 collisions are at
   **ply 2**; a `--min-ply` predicate excludes exactly the region where boards are scarce.
   **Checked this session: no such knob exists** — `run_census.py` has `--max-per-game` and no ply
   predicate, and `build_positions.py` carries `ply` as a *field* on every row (alongside
   `phase_bucket` and `tercile`) but filters on none of them. So the data supports the filter and
   the code does not yet: **a new knob, not a new instrument.**
   ⚠️ **A ply-floor changes the measured population** — it excludes early-game tied plies, which
   are a real part of the arbiter's firing distribution — so it is **not** a free fix: the
   successor must re-derive its supply rates under the floor (they will fall) and state plainly
   that its estimand is *tied plies at ply ≥ k*, not *tied plies*.
3. **The probe→carry loop iterated to a fixed point** (see the residual finding in the
   adjudication): a single probe pass is not guaranteed to converge, because applying exclusions
   admits positions the probe never saw.
4. **Fresh band, fresh corpus, fresh read rule.** The S2 corpus of this run is spent by its void.

## 5. Disposition

- **S2 stratum: VOID.** Not excluded-and-continued, not topped up, not re-gated.
- **Rung 3: UNMEASURED**, awaiting a successor prereg that fixes the bound's *shape* and,
  probably, the mining predicate. **Drafted: [`rung3_r5/DESIGN.md`](rung3_r5/DESIGN.md).**
- ~~**The extension band's S2 sub-range is spent.** A successor claims fresh seeds.~~
  **CORRECTED 2026-08-18** (this line was over-strict): **what is spent is the R4 S2 *stratum* —
  the positions built under R4's read rule — not the *substrate*.** The 5,340 games were **never
  scored**; only structure counts were read; so the same counts-only argument that let R4 retain
  band 135e9 ([`PREREG_FAILURE.md`](PREREG_FAILURE.md) §3) applies identically here. **The games
  are RETAINED INPUT to the successor**, which re-mines them under a ply-floor — producing a
  *different position set* from the same substrate, which is the intended use and is not a re-read
  of anything spent. See [`rung3_r5/DESIGN.md`](rung3_r5/DESIGN.md) §R5-4.
- **The scale-dependence finding stands on its own** and should be carried into any future
  offline-corpus design in this programme, not just rung 3's.
