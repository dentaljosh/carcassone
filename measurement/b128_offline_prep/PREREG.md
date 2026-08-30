# PREREG — offline capture ladder extended to B = 128 (tie-arbiter)

**Status:** PRE-REGISTERED 2026-08-29, before any new playout was launched.
**Funded:** owner, 2026-08-30 brief, verbatim *"let's start with offline b128, both boxes"*.
**Instrument:** `measurement/tiearb_widening_20260817/` shared_run_r4, stratum S1.
**Read-side estimator:** `measurement/arb_costopt_prep/phase_b_capture.py` (already
reproduced the published R4 ladder to 4 dp; reused verbatim, not re-derived).
**Games played: 0.** Offline oracle-class instrument ⇒ **no band claim, no
`experiments/results.csv` row** (house precedent for this class).

---

## 0. What is being measured, and what it is not

The tie-arbiter's *offline capture ladder*: for each tied-tile position, the
arbiter selects one of the tied arms using `B` common-random-number (CRN)
tier1-greedy playout worlds, and that pick is then **priced on `E = 64` held-out
CRN oracle (`clair-puct`) worlds** against the champion's own pick. Capture is in
points-per-tied-tile-ply. The published ladder runs `B = 1,2,4,8,16,32,64`.

**This measures one number: the WITHIN-INSTRUMENT rung-to-rung contrast
`B = 64 → 128`.**

> **CL-085 rider, carried with every quotation.** The absolute capture *levels*
> are **in-family judge-priced** (the `clair-puct` pricing judge and the
> `tier1-greedy` arbiter judge are the arbiter's own family) and travel with that
> caveat. The **rung-to-rung CONTRAST** — same positions, same arms, same 64 eval
> worlds, nested selection worlds, CRN-paired within position — is the robust
> class and is what this pre-registration reads.

**Not measured here:** whether B=128 wins games. That is the downstream H2H this
readout is meant to fund or not fund.

---

## 1. Why B = 128 is a legal extension of the SAME instrument

`tier1_rust_leg.preflight_seeds` asserts, and the banked R4 manifests record
(`preflight.seeds.derivation`):

```
world_seed / playout_seed = sha256(tag | rid | j | salt);  M never enters
prefix_stable_at: [1, 2, 4, 8, 16, 32, 64, 128]
```

World `j`'s seed is a function of `j` alone (given `rid`, `salt`). So growing
`M` **appends** worlds and never disturbs worlds `0 … M_old − 1`.

The cross-fit split is `analyze_tiletie.parity_indices(m, base=1)`:
`sel = {j : j odd}`, `eva = {j : j even}`, and `swap=True` exchanges them; every
statistic is the `_sym` mean of the two folds. Selection uses
`sorted(sel)[:B]`; pricing always uses `sorted(eva)[:E]`.

Consequently, at `M = 256`:

| quantity | at M = 128 | at M = 256 | identical? |
|---|---|---|---|
| `sorted(sel)[:64]`, swap=F | {1,3,…,127} | {1,3,…,127} | **yes** |
| `sorted(sel)[:64]`, swap=T | {0,2,…,126} | {0,2,…,126} | **yes** |
| `sorted(eva)[:64]`, swap=F | {0,2,…,126} | {0,2,…,126} | **yes** |
| `sorted(eva)[:64]`, swap=T | {1,3,…,127} | {1,3,…,127} | **yes** |
| `sorted(sel)[:128]`, swap=F | *(n/a)* | {1,3,…,255} | new rung |
| `sorted(sel)[:128]`, swap=T | *(n/a)* | {0,2,…,254} | new rung |

So **B = 1…64 must come out bit-identical at M = 256**, and B = 128 is a strict
super-set of the B = 64 selection sample. That nesting is the identity gate
(§3) — it is not assumed, it is asserted on the realized data.

### 1.1 Which playouts are actually new

* **`tier1-greedy` (ARB / selection judge):** needs worlds 128 … 255, because
  the two folds between them consume both parities. **NEW COMPUTE.**
* **`clair-puct` (IF / pricing judge):** the ladder only ever indexes
  `sorted(eva)[:64] ⊂ {0 … 127}`. **NO new oracle worlds. Banked worlds 0 … 127
  are reused verbatim, never regenerated.** (The oracle leg was ~93 % of the
  original bill; it is not re-paid.)
* The `ora_*` / `rnd_*` companions of the published readout are **not
  recomputed at M = 256** and are **not** part of this pre-registration —
  `ora_*` selects on the full `sel` half and would require oracle worlds
  128 … 255. They are quoted only at their published M = 128 values, as context.

## 2. Design

* **Corpus:** shared_run_r4 stratum S1, `rules_profile = walled`, the same
  n = 1,340 analysed positions over 748 roots that the published ladder reads
  (1,344 planned; the same 4 drop through the published `build_rows` accounting).
  Bands pooled exactly as published: 135e9 (retained, 551) + 137e9 (fresh, 793).
  **Never pooled across corpora** (CL-068).
* **Arm set:** the deployed `J = 4` sub-read (`subset_j4`), key template
  `arb_j4_E64_B{b}` — the R4 read-out's own ladder key. `arb_full_E64_B{b}` is
  carried as a secondary.
* **E = 64** held-out oracle worlds throughout. `E = 16` carried as a sub-read.
* **Estimator:** record mean; **percentile ROOT bootstrap, cluster = `root_id`,
  2,000 reps, seed 20260819** (`phase_b_capture.RootBoot`, the
  `analyze_widening.RootBoot` convention). Every statistic and every contrast
  lives on **one shared resample draw**, so differences are coherent
  replicate-by-replicate.
* **Phase cuts** verbatim from `sample_agreement_roots.py:96`, strict-cut
  fall-through reproduced: `early = 48 < k < 1e9`, `mid = 24 < k < 48`,
  `late = k < 24`; `k == 48` and `k == 24` fall through to `late`.
* **`B_LADDER` = (1, 2, 4, 8, 16, 32, 64, **128**)**; optionally 256 (§6).

## 3. Identity gate — MANDATORY, fires before any new number is read

Failure of **any** of these ⇒ **VOID**. No B = 128 number is quoted.

| gate | assertion | threshold |
|---|---|---|
| **G-ID-1** | The row builder used here, run on the **banked M = 128** matrices, reproduces every `arb_j4_E64_B{b}` and `arb_full_E64_B{b}`, `b ∈ {1,2,4,8,16,32,64}`, in `shared_run_r4/verdicts/per_position_s1.jsonl` | **bit-identical f64** (`struct.pack('<d')`), 1,340/1,340 rows × 7 rungs × 2 arm-sets. Stricter than the 4 dp the brief requires. |
| **G-ID-2** | With the **extended M = 256** matrices, the same `b ∈ {1…64}` rungs are **still** bit-identical to the banked values | bit-identical, 1,340/1,340 |
| **G-ID-3** | Seed prefix-stability on realized data: `world_seeds(rid, 256, salt)[:128]` equals the `world_seeds` recorded in every banked `tier1-greedy` record | 3,328/3,328 records |
| **G-ID-4** | The shifted generator used for the new pass emits exactly `world_seeds(rid, 256, salt)[128:256]` and `playout_seed(rid, j, salt)` for `j ∈ [128,256)` | exact, every record |
| **G-ID-5** | Banked worlds 0…127 are **reused**, never regenerated: new record files carry 128 values each and are **concatenated after** the banked block | by construction + asserted lengths (`len == 256`) |
| **G-ID-6** | Published **B = 64 LEVELS** reproduce: `ALL/early/mid/late` for `arb_j4_E64_B64` match `arb_costopt_prep/PHASE_B_CAPTURE.json` | **4 dp** |
| **G-ID-7** | `carc_rs` binary sha recorded; every new record's `crn_verified == True`, `ok == True`, `n_failed == 0` | 100 % |
| **G-ID-8** | Arm-set / champion plumbing: `n_arms_j4`, `champ_pos`, `arm_order` reproduce the banked row's fields | 1,340/1,340 |

Note on G-ID-7: the tier1 flat-score swap is **proven bit-identical**
(`arb_costopt_prep/BITEXACT_tier1swap.json`, 15,360/15,360 f64-identical, digests
equal), so mixing the pre-swap banked block with post-swap new worlds cannot move
a value. The wheel sha is recorded regardless.

## 4. Primary statistics and the pre-registered branches

Let, per position, `d128 = arb_j4_E64_B128 − arb_j4_E64_B64` (CRN-paired within
position: identical eval worlds, nested selection worlds).

* **PRIMARY-A (pooled):** `Δ_ALL = mean(d128)` over all 1,340 positions.
* **PRIMARY-B (mid+late):** `Δ_midlate = mean(d128 | phase ∈ {mid, late})` —
  the cells the funding brief names ("mid +0.380→+0.434, late +0.263→+0.283").
* **Secondary:** `Δ_early`, `Δ_mid`, `Δ_late` separately; the `arb_full` and
  `E = 16` replicates; the `log₂B` trend slope over rungs 16→128.

All on the one shared root-bootstrap draw. `σ` below = `se_root` from that draw.

### 4.1 Power, stated in advance

Realized paired rung-step SEs on this corpus are **σ ≈ 0.018–0.025 pooled** and
**σ ≈ 0.018 on mid+late** (measured from the banked ladder, `d_32_64` etc.).
The realized `32→64` steps were `Δ_ALL = +0.0073 ± 0.0183 (z = 0.40)` and
`Δ_midlate = +0.0361 ± 0.0185 (z = 1.96)`.

**⚠️ Declared before reading:** at these SEs a *single* 64→128 step of the same
size as the realized 32→64 step is a **z ≈ 2 event at best on mid+late and a
z ≈ 0.4 event pooled**. This instrument is **underpowered to certify a single
rung step at 2σ pooled**, and the pre-registration says so rather than
discovering it afterwards. That is exactly why FLAT is defined as a *bound* and
why UNRESOLVED is a real, expected outcome rather than a formality.

### 4.2 Branches (evaluated in this order; first match fires)

**Reference increment `δ* = 0.030`** — a step materially as large as the realized
`32→64` mid+late step (+0.0361). Fixed here, before reading.

| branch | numeric condition | implication |
|---|---|---|
| **VOID** | any gate in §3 fails | no number quoted; report the gate failure and stop |
| **LADDER-CLIMBS** | `Δ_midlate ≥ 2σ` (z ≥ +2.0) **and** `Δ_midlate > 0` | **the B128-vs-B64 game H2H gets sized and proposed for funding**; the offline ladder has not turned over by B = 128 |
| **LADDER-REGRESSES** | `Δ_midlate ≤ −2σ` (z ≤ −2.0) | H2H **not** funded; the ladder has turned over — over-selection at B = 128 |
| **LADDER-FLAT** | 95 % CI upper bound of `Δ_midlate` `< δ* = 0.030` **and** 95 % CI upper bound of `Δ_ALL` `< δ*` | H2H **not** funded on this evidence: the instrument *excludes* a further step as large as the last one |
| **UNRESOLVED** | none of the above (CI straddles both `0` and `δ*`) | H2H **not** funded on this evidence; report the two-sided bound and the realized cost of buying more precision |

A CLIMBS verdict on `Δ_ALL` alone (z ≥ 2 pooled) also fires CLIMBS; it is a
strictly stronger read and is reported if it occurs.

### 4.3 Implication map (pre-committed)

* **CLIMBS ⇒ the game H2H gets sized.** The readout hands over the per-position
  effect size and the realized selection cost so a powered, deck-paired,
  within-band B128-vs-B64 H2H can be sized.
* **FLAT / REGRESSES / UNRESOLVED ⇒ it does not.** No H2H is proposed off this
  evidence. An offline capture step this instrument cannot separate from zero at
  its own noise floor is not a basis for spending games.
* In no branch does this readout by itself change `governance/PRODUCTION.yaml`
  or any deployed knob. It is a *funding* input.

## 5. What would make this wrong (falsifiers already armed)

1. **Seed derivation drift** — if `world_seeds` ever depended on `M`, every
   sub-read of the banked run would be void. G-ID-3/G-ID-4 assert the realized
   property rather than trusting the docstring.
2. **Estimator drift** — G-ID-1/G-ID-2 require *bit-identity* with the published
   ladder through the same code path that produces B = 128. A re-implementation
   that "looks right" but reorders an arm cannot pass.
3. **Judge family** — the CL-085 rider above. This readout is explicitly a
   *within-family* contrast and is not evidence about the arbiter's value under
   an out-of-family judge (F4 lesson, 2026-08-26).
4. **Silent tenancy contamination** — the compute is not a timing measurement,
   so a co-tenant cannot move a *value*; but the box is censused by full args
   before launch and the realized rate is reported as an interval, not a point.

## 6. Optional same-instrument extension to B = 256 — **agent-initiated**

**Disclosure: the owner named B = 128. B = 256 is proposed by the agent** as a
same-instrument, same-gate extension, and runs **only** if the B = 128 pass
finishes well under budget.

* **Legality:** identical to §1 — at `M = 512`, `sorted(eva)[:64]` and
  `sorted(sel)[:b≤128]` are unchanged, so every rung ≤ 128 stays bit-identical
  and B = 256 is a nested super-set. Gates G-ID-1…8 extend unchanged.
* **Trigger (fixed now):** run it **iff** (a) every §3 gate passes, **and**
  (b) the B = 128 playout pass completes in **< 45 min wall** across the boxes
  actually used. Otherwise it is not run and this section is reported as
  "not triggered".
* **Cost:** worlds 256 … 511 = **2× the B = 128 new-world count**.
* **Read:** `Δ256 = mean(arb_j4_E64_B256 − arb_j4_E64_B128)` on the same draw,
  reported as a **SECONDARY**. It does not alter §4.2's branch — the owner-named
  64→128 contrast fires the branch. It is reported as trend context.

## 7. Cost, stated before launch

New playouts for B = 128: **3,328 records × 128 new worlds × 2 picks =
851,968 playouts** (tier1-greedy only; zero new oracle playouts).

| | value |
|---|---|
| banked R4 tier1 rate (pre-swap, contended) | 0.2249 CPU-s / playout (191,611 CPU-s for 851,968 playouts) |
| post-swap claim (flat-score swap, bit-identical) | ~8.5× cheaper ⇒ ~0.0265 CPU-s / playout |
| **projected B128 cost** | **≈ 22,500 CPU-s ≈ 6.3 CPU-h** |
| projected wall, local only @ W = 30 | **≈ 13 min** |
| projected wall, local + laptop | ≈ 9–10 min |
| worst case (speedup does not materialize) | 191,611 CPU-s ≈ 53 CPU-h ⇒ ≈ 1.8 h wall @ W = 30 |
| optional B256 increment | 2× the above (worlds 256…511) |

**Both-boxes note (owner said "both boxes"):** the split arithmetic is stated
above and the runner is chunked per leg so it splits trivially. If the realized
smoke rate shows the whole pass is a sub-15-minute local job, it is run
local-only and the split is reported as *offered and unnecessary* rather than
performed — the owner's instruction is honoured by disclosing the arithmetic,
not by manufacturing cross-box variance in a run whose values are box-invariant
(bit-identical rust playouts).

## 8. Deliverables

`measurement/b128_offline_prep/` — this `PREREG.md`, `B128_LADDER.json`
(all rungs, all phases, CIs, gates, manifest incl. `carc_rs_binary_sha`),
`READOUT.md` (the branch that fired), `scripts/`.

Owed on close-out, listed verbatim in the final report and **not** edited by
this agent: a `DECISIONS.md` index line and a roadmap stamp.
