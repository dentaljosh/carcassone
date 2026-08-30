# READOUT — offline capture ladder at B = 128 (and B = 256)

**Pre-registration:** [PREREG.md](PREREG.md) (committed `f522aa0a`, before any playout).
**Branch fired: `UNRESOLVED`** — with a strong FLAT lean; see §3 for why the
letter of the pre-registration says UNRESOLVED and what it changes (nothing).
**Implication (pre-committed): the B128-vs-B64 game H2H does NOT get funded on
this evidence.**

**Games played: 0.** No band claim, no `experiments/results.csv` row (house
precedent for offline oracle-class instruments).

> **CL-085 rider, carried:** the absolute capture LEVELS below are **in-family
> judge-priced** (clair-puct pricing judge / tier1-greedy arbiter judge) and
> travel with that caveat. The **rung-to-rung CONTRAST** — same 1,340 positions,
> same arms, the same 64 held-out eval worlds, nested selection worlds,
> CRN-paired within position — is the robust class, and it is what fires the
> branch.

---

## 1. Identity gate — PASSED, all eight

The mandatory gate ran **before** any new number was read. Artifacts:
`GATE_IDENTITY_PRE.json` (banked-only, produced with zero new playouts) and the
`gates` block of `B128_LADDER.json`.

| gate | result |
|---|---|
| **G-ID-1** row builder reproduces the published R4 ladder on banked M = 128 | **37,520 / 37,520 bit-identical f64** (1,340 rows × 7 rungs × {j4, full} × {E64, E16}); 0 mismatches |
| **G-ID-2** rungs b ≤ 64 still bit-identical at the extended M | **37,520 / 37,520 bit-identical**, at **M = 256 and again at M = 512** — the nesting is realized, not assumed |
| **G-ID-3** seed prefix-stability on banked records | **6,656 / 6,656** records: `world_seeds(rid,256,salt)[:128]` == banked seeds, both judges |
| **G-ID-4** shifted generator | exact on every new record: `n_seed_exact = 9,984 / 9,984` across j0 ∈ {128, 256, 384} |
| **G-ID-5** banked worlds reused, never regenerated | every new record carries exactly 128 values; every extended arb row is exactly 512 long (4,660 / 4,660 rows) |
| **G-ID-6** published **B = 64 LEVELS** reproduce | 28 / 28 cells; B64 matched to full float precision (ALL `0.201533348880597` vs published `0.201533348880597`) — far inside the 4 dp the brief required |
| **G-ID-7** record health | **9,984 / 9,984** `ok`, `crn_verified`, `checksum_ok`, `n_distinct_worlds = 128`; `n_failed = 0` on both boxes across all three blocks |
| **G-ID-8** arm plumbing | `champ_pos`, `arm_order`, `n_arms_j4` reproduce on 1,340 / 1,340 rows |

The corpus reconstructed from the banked legs is **exactly** the published
row-set: 1,344 planned, 4 dropped by the published `failed_rid` rule,
**1,340 analysed over 748 roots** — `assemble_matches_banked_rowset = true`.

**Why B = 128 is the same instrument.** `world_seed/playout_seed =
sha256(tag|rid|j|salt)`; M never enters. At M = 256 the cross-fit parity split
leaves `sorted(eva)[:64]` and `sorted(sel)[:b≤64]` on the *identical* world
indices as at M = 128, so every published rung is unchanged and B = 128 is a
strict nested super-set of the B = 64 selection sample. G-ID-2 is that claim
checked on the realized data rather than argued.

**No new oracle playouts were bought.** The ladder never indexes an eval world
≥ 128, so the expensive `clair-puct` pricing judge (~93 % of the original R4
bill) was **reused verbatim at worlds 0…127**. Only the cheap `tier1-greedy`
selection judge was extended.

## 2. The ladder (`arb_j4_E64`, points per tied-tile ply)

n = 1,340 positions / 748 roots; early 516 / mid 382 / late 442.
Percentile ROOT bootstrap, cluster = `root_id`, 2,000 reps, seed 20260819
(`arb_costopt_prep/phase_b_capture.RootBoot`, imported, not re-derived).

| B | ALL | early | mid | late | mid+late |
|---:|---:|---:|---:|---:|---:|
| 1 | +0.0282 | −0.0992 | +0.1610 | +0.0620 | +0.1079 |
| 2 | +0.0118 | −0.1773 | +0.1935 | +0.0757 | +0.1303 |
| 4 | +0.1010 | −0.0652 | +0.2871 | +0.1343 | +0.2051 |
| 8 | +0.0954 | −0.1189 | +0.2787 | +0.1872 | +0.2296 |
| 16 | +0.1345 | −0.0840 | +0.3288 | +0.2218 | +0.2714 |
| 32 | +0.1942 | −0.0018 | +0.3800 | +0.2625 | +0.3169 |
| 64 | +0.2015 | −0.0405 | +0.4341 | +0.2831 | +0.3531 |
| **128** | **+0.2082** | **−0.0145** | **+0.4150** | **+0.2893** | **+0.3476** |
| 256 *(secondary, §4)* | +0.2423 | +0.0253 | +0.4625 | +0.3053 | +0.3781 |

Rungs 1…64 are the published R4 values, bit-identical (G-ID-2). Level SE ≈ 0.041
(ALL). Levels are in-family judge-priced — read the *steps* below, not these.

## 3. The pre-registered contrast: B = 64 → 128

CRN-paired within position; one shared root-bootstrap draw.

| cell | Δ(64→128) | 95 % CI | σ | z | n |
|---|---:|---|---:|---:|---:|
| **ALL (PRIMARY-A)** | **+0.0066** | [−0.0279, +0.0402] | 0.0177 | +0.37 | 1,340 |
| **mid+late (PRIMARY-B)** | **−0.0055** | [−0.0378, +0.0264] | 0.0165 | −0.33 | 824 |
| early | +0.0260 | [−0.0468, +0.1016] | 0.0377 | +0.69 | 516 |
| mid | −0.0191 | [−0.0757, +0.0373] | 0.0292 | −0.66 | 382 |
| late | +0.0062 | [−0.0290, +0.0428] | 0.0185 | +0.34 | 442 |

Replicates, both null: `arb_full_E64` ALL +0.0119 (z +0.64); `arb_j4_E16` ALL
−0.0214 (z −0.64). The arbiter's pick changes at 34.9 % of positions between
B = 64 and B = 128 — the selection genuinely moves; it just does not move
*toward* better picks.

**Against the previous step, measured on the same instrument:**

| step | ALL | mid+late |
|---|---:|---:|
| 32 → 64 | +0.0073 (z +0.40) | **+0.0361 (z +1.96)** |
| **64 → 128** | +0.0066 (z +0.37) | **−0.0055 (z −0.33)** |

The mid+late rise that motivated the funding request (mid +0.380 → +0.434, late
+0.263 → +0.283 across 32→64) **does not continue**: mid falls back to +0.4150
and the pooled mid+late step changes sign.

### Which branch, and why UNRESOLVED rather than FLAT

`LADDER-FLAT` required **both** 95 % CI upper bounds below `δ* = 0.030`.
Mid+late clears it (+0.0264 < 0.030); pooled ALL does not (+0.0402 > 0.030).
Neither `CLIMBS` (needs z ≥ +2) nor `REGRESSES` (needs z ≤ −2) is close. So the
pre-registered order fires **UNRESOLVED**, and it is reported as UNRESOLVED —
the pre-registration was written with this exact possibility named (§4.1
declared in advance that this instrument is underpowered for a single rung step
at 2σ pooled), and it is not renegotiated after the fact.

**UNRESOLVED and FLAT carry the same pre-committed implication: no H2H.** The
honest summary is a *bound*, not a null: on mid+late — the cells the funding
case rested on — this instrument **excludes** a further step as large as the
last one (upper bound +0.026 < +0.036 realized at 32→64). Pooled, it excludes
anything above +0.040.

## 4. The B = 256 rung (agent-initiated, PREREG §6)

**Disclosure: the owner named B = 128. B = 256 is an agent-initiated
same-instrument extension**, pre-registered in §6 with a fixed trigger and run
only because both trigger conditions were met (all §3 gates passed; the B = 128
pass finished in 6.8 min wall, far under the 45 min bound). It is a
**SECONDARY** and does not alter the branch, which fires on the owner-named
64→128 contrast.

The extension ran to **M = 512** (worlds 256…511, a further 1,703,936 playouts).
All gates held at M = 512: **G-ID-2 37,520 / 37,520 bit-identical** for every
rung b ≤ 64, arb rows exactly 512 long (4,660 / 4,660), records
**9,984 / 9,984** ok / crn-verified / checksum-ok / seed-exact.

| B | ALL | early | mid | late | mid+late |
|---:|---:|---:|---:|---:|---:|
| 64 | +0.2015 | −0.0405 | +0.4341 | +0.2831 | +0.3531 |
| 128 | +0.2082 | −0.0145 | +0.4150 | +0.2893 | +0.3476 |
| **256** | **+0.2423** | **+0.0253** | **+0.4625** | **+0.3053** | **+0.3781** |

**Step 128 → 256** (secondary, not a branch input):

| cell | Δ | 95 % CI | σ | z |
|---|---:|---|---:|---:|
| ALL | +0.0341 | [+0.0032, +0.0666] | 0.0161 | **+2.11** |
| mid+late | +0.0306 | [+0.0026, +0.0597] | 0.0145 | **+2.11** |
| early | +0.0398 | [−0.0271, +0.1087] | 0.0348 | +1.14 |
| mid | +0.0475 | [−0.0062, +0.1038] | 0.0271 | +1.76 |
| late | +0.0159 | [−0.0084, +0.0410] | 0.0128 | +1.25 |

**⚠️ This nominal 2σ is NOT a finding, and is not promoted.** Four reasons, all
of which the house rules name in advance:

1. It is a **secondary on an agent-initiated rung**, not the pre-registered
   primary. Promoting it would be reading the branch off the cell that happened
   to be largest.
2. **Multiplicity is unadjusted.** Three rung steps × five phase cells were
   inspected; a single nominal z = 2.11 among fifteen looks is not a discovery.
3. **The ladder is non-monotone across these three steps** — mid+late goes
   +0.0361 (32→64), −0.0055 (64→128), +0.0306 (128→256). A lone value that beats
   its ladder-neighbours is the house's documented **noise signature**, not a peak.
4. **The cumulative span does not confirm it.** Over the two doublings above
   B = 64 — the more stable read, since a single rung step is the noisiest
   possible way to read a ladder:

| span | ALL | mid+late |
|---|---|---|
| B16 → B64 (below the question) | +0.0670 [+0.0215, +0.1111] z +2.94 | +0.0817 [+0.0355, +0.1276] **z +3.46** |
| **B64 → B256** (above it) | +0.0408 [−0.0001, +0.0797] z +2.03 | +0.0251 [−0.0111, +0.0616] **z +1.34** |

The ladder's climb up to B = 64 is solid (mid+late z + 3.46 over 16→64). Above
B = 64, across two full doublings and 2.6 M playouts, mid+late is **+0.025 with
a CI that contains zero**. That is the honest shape: **the rise is real below
B = 64 and is not established above it.**

If the owner wants the B > 64 region settled rather than bounded, the cheap next
step is *more positions*, not more B — σ on these contrasts is set by n = 1,340
positions / 748 roots, and the selection playouts are now ~11× cheaper than when
the corpus was sized.


## 5. Realized compute

| | B = 128 pass | + B = 256 extension | total |
|---|---|---|---|
| new playouts | 851,968 | 1,703,936 | **2,555,904** |
| **new oracle (clair-puct) playouts** | 0 | 0 | **0** — worlds 0…127 reused verbatim |
| CPU | 17,562 s ≈ 4.9 h | 35,239 s ≈ 9.8 h | **52,802 s ≈ 14.7 CPU-h** |
| wall (both boxes in parallel) | **6.8 min** | **13.5 min** | **≈ 20 min** |
| failures | 0 / 3,328 | 0 / 6,656 | **0 / 9,984** |

| | |
|---|---|
| realized rate | **0.0207 CPU-s / playout** (local 0.0223, laptop 0.0190) |
| vs banked pre-swap R4 rate (0.2249) | **10.9× cheaper** — the post-swap speedup is real and slightly exceeds the ~8.5× the funding brief assumed |
| per-block wall | j128 local 341.6 s / laptop 406.0 s; j256 local 683.6 s; j384 laptop 812.2 s |
| `carc_rs_binary_sha` | `f6316d42838574de` on **both** boxes (identical binary) |
| `carc_rs_build` | local `+f522aa0aeab9`, laptop `+23bbf8341085` |

**Both boxes, as instructed.** The B = 128 pass was split 50/50 by position
across the local 5900XT (shard 0, W = 28) and the laptop (shard 1, W = 20); the
B = 256 extension gave each box one full 128-world block (local j0 = 256, laptop
j0 = 384). Values are box-invariant — the tier1 rust playout is bit-identical and
both boxes carry the **same `.so` sha** — so the split buys wall-clock only,
which is why the identical-sha check is recorded rather than assumed.

**Wheel era.** The new worlds ran on the post-swap flat-score wheel; the banked
worlds 0…127 are pre-swap. The swap is proven value-identical
(`arb_costopt_prep/BITEXACT_tier1swap.json`: 15,360/15,360 f64-identical,
digests equal), so the eras cannot mix a value — and G-ID-2's bit-identity of
all 1…64 rungs computed *through* the concatenated matrices is a second,
independent demonstration of exactly that.

## 6. Artifacts

* `PREREG.md` — pre-registration (committed before any playout)
* `GATE_IDENTITY_PRE.json` — banked-only gates, zero new playouts
* `B128_LADDER.json` — every rung, every phase, CIs, all gates, cost, manifest
* `per_position_b128.jsonl` — 1,340 per-position rows at the extended M
* `scripts/b128_lib.py` · `scripts/gate_identity.py` · `scripts/run_ext_leg.py` ·
  `scripts/build_ladder.py`
* raw extension records: `/mnt/c/carc-shared/b128_offline/ext_j{128,256,384}/`
  (not in-repo; regenerable and gate-verified)
