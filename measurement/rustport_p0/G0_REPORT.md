# G0 — the determinism substrate (rustport phase P0)

> **STATUS: PASS (local leg, 2026-07-31).** All four primitives are bit-exact
> against the Python/numpy/libc they must reproduce, on the 5900XT box
> (Ubuntu glibc 2.39, x86-64, CPython 3.12.3, numpy 2.4.4, rustc 1.96.0).
> The **fleet legs ran 2026-07-31**: the laptop reproduces the local leg
> count-for-count; **the M5 (arm64 macOS) has NO flavour at 0 mismatches** and is
> the first platform to trip the pre-registered fallback — see
> [Fleet legs](#5-fleet-legs-laptop--m5). The Android leg is deferred to P7 per
> the spec.
>
> Spec of record: [docs/RUSTPORT_BUILD_SPEC_2026-07-31.md](../../docs/RUSTPORT_BUILD_SPEC_2026-07-31.md).
> Raw numbers: the `G0_*.json` files in this directory — **quote those, not this
> prose**, if the two ever disagree.

## Verdict table

| primitive | gate script | scale | mismatches | verdict |
|---|---|---|---|---|
| CPython MT19937 | `reconcile_mt19937.py` | 33,200 checks / 9,965 distinct seeds (max 257 bits, 1,953 ≥ 2⁶⁴) | **0** | **PASS** |
| `math.fsum` | `reconcile_fsum.py` | 1,000,000 multisets / 63,883,944 terms | **0** | **PASS** |
| `np.sum` pairwise | `reconcile_npsum.py` | 10,764 reductions (598 lengths × 9 families × f32+f64) | **0** | **PASS** |
| `np.exp` | `harness_transcendental.py` | 201,525 corpus + 100,000,000 fuzz | **0** *(via `exp64_fma`)* | **PASS** |
| `math.tanh` | `harness_transcendental.py` | 214,333 corpus + 100,000,000 fuzz | **0** *(via flavour `glibc_fma`)* | **PASS** |

The transcendental gate is the one the spec said "decides the libm strategy".
**It decided in favour of full bit-exactness** — the pre-registered ≥99.9%
fallback is *not* needed on this platform. See
[the libm finding](#the-libm-finding-two-axes-not-one).

---

## 1. MT19937 — `G0_mt19937.json`

Checked element-for-element, 0 mismatches over 33,200 checks:

- `random.seed(s); random.shuffle(list(range(n)))` vs Rust `SeedMode::GlobalSeed`
- `random.Random(s).shuffle(...)` vs `SeedMode::RandomInstance`
- the two Python forms against **each other** — the `SeedMode` split is proven a
  no-op rather than assumed (CPython routes both through `random_seed()`)
- `random_seed()`'s little-endian 32-bit word split of `abs(seed)`
- raw `genrand_uint32` streams (64 words × 400 seeds)
- `getrandbits(k)`, k ∈ 0..64
- `Random._randbelow(n)` including the rejection loop

Coverage that matters for the record:

- **seeds**: 0, small, ±2³¹−1, 2³²±1, ±2⁶³, 2⁶⁴±1, 2⁷⁰, 2¹²⁸−1, 2¹⁹¹, 2²⁵⁶ —
  1,953 of the 9,965 are ≥ 2⁶⁴ and are passed to Rust as decimal strings, because
  CPython seeds from the **full** absolute value (no hashing down). Negative
  seeds included (`PyNumber_Absolute`). Plus the `28_000_000_xxx` champ band and
  the `60/76/88e9` claim bands.
- **n**: every value 0..100, the deck lengths **{71, 72}**, and every
  determinization `k_remaining` 1..72.

## 2. `math.fsum` — `G0_fsum.json`

1,000,000 random multisets (63.9M terms), compared on `struct.pack('<d')` bytes so
a `±0.0` disagreement would fail. Six families in roughly equal share: uniform
log-magnitudes over 1e-300..1e300 · leaf-like narrow values · cancellation pairs ·
the CPython `test_math` catastrophic ladder · subnormals · one-huge-plus-many-tiny
(the half-even-fixup case). **0 bit-mismatches.**

The port includes CPython's cross-partial half-even fixup, which is what makes
`math.fsum` commutative — omitting it would have passed a naive test and failed
here.

## 3. numpy pairwise sum — `G0_npsum.json`

**0 bit-mismatches** over 10,764 reductions: every length 1..300, the
block/recursion boundaries (8/16/128/129/136/144/256/257/264/512/1024/2048/4096
and their ±1, +7, +8 neighbours), then stride-sampled to 5,000 — crossed with 9
value families and both `float32` and `float64`.

The reduction order was transcribed from the **numpy 2.4.4 source at the venv's
own git revision** (`be93fe2960dbf49b4647f5783c66d967fb2c65b5`), not from memory.
Three details that memory gets wrong:

1. the `n < 8` base case seeds from **`-0.0`**, not `0.0` (to preserve `-0.0`);
2. the 8-accumulator block reduces as `((r0+r1)+(r2+r3)) + ((r4+r5)+(r6+r7))`,
   with the `n % 8` tail folded into that scalar afterwards;
3. the recursive split is `n2 = n/2; n2 -= n2 % 8` — snapped **down** to a
   multiple of the unroll factor, so it is *not* a plain halving.

Also verified from source: `loops_arithm_fp.dispatch.c.src` takes the
`pairwise_sum` path for the reduce case **unconditionally** (`#if @PW@`, true only
for `add`) — there is no SIMD reduce variant that could reorder it.

## 4. The libm finding: two axes, not one

### What was measured

`harness_transcendental.py` harvested the **real** arguments by replaying 89 games
of `champ_action_logs/champ_games.jsonl` (12,808 plies) through the production
prior evaluator:

| site | expression | n harvested | range | distinct values |
|---|---|---|---|---|
| `np.exp` | `z = Δleaf/τ_p − max(z)`, τ_p = 5.0 | 201,525 | [−7.08, 0] | 1,666 |
| `math.tanh` | `leaf / value_norm`, norm = 15.0 | 214,333 | [−3.12, 2.82] | 2,673 |

(Worth noting for later phases: the leaf is coarse enough that **both sites see a
few-thousand-element discrete set**, not a continuum.)

Plus 10⁸ fuzz values per implementation over the spec's ranges (z ∈ [−100, 0],
tanh arg ∈ [−20, 20]), half uniform-in-value and half uniform-bit-pattern.

### `exp`

`exp64_fma` — ARM optimized-routines `exp.c` (N=128, POLY_ORDER=5) **with FMA
contraction** — is bit-exact:

| implementation | corpus (201,525) | fuzz (10⁸) | max ulp |
|---|---|---|---|
| `exp64` (no contraction) | 7,205 mismatch | 34,788 mismatch | 1 |
| **`exp64_fma`** | **0** | **0** | **0** |

So `np.exp` on a float64 ndarray here **is** glibc's `__exp_fma`, which **is** the
ARM routine compiled with `-mfma`.

### `tanh` — the part that needed source, not guesswork

First pass: `tanh64` (faithful FreeBSD-msun port) was off by 3/214,333. Two steps
localised it:

1. Reconstructing fdlibm `s_tanh` **in Python over the platform's own
   `math.expm1`** reproduced `math.tanh` 214,333/214,333. ⇒ the divergence is
   entirely in `expm1`, not in `tanh`'s wrapper.
2. Reading glibc's `sysdeps/ieee754/dbl-64/s_expm1.c` (rather than assuming it
   equals FreeBSD msun) showed a **different polynomial grouping**, carrying a
   1997 *"Modified by Naohiko Shimizu / Tokai University … for performance
   improvement on pipelined processors"* note:

   ```c
   /* glibc */                          /* FreeBSD msun (fdlibm) */
   R1 = 1 + hxs*Q1;  h2 = hxs*hxs;      r1 = 1 + hxs*(Q1 + hxs*(Q2 + hxs*
   R2 = Q2 + hxs*Q3; h4 = h2*h2;                (Q3 + hxs*(Q4 + hxs*Q5))));
   R3 = Q4 + hxs*Q5;
   r1 = R1 + h2*R2 + h4*R3;
   ```

   Same coefficients, different rounding sequence — a different function, not a
   refactor.

So there are **two independent axes**, enumerated as `compat::LibmFlavor`:

| flavour | polynomial | FMA | expm1 corpus (428,666) | tanh corpus (214,333) | tanh fuzz (10⁸) |
|---|---|---|---|---|---|
| `msun` | Horner | no | 384 | 3 | 131,428 |
| `msun_fma` | Horner | yes | 85 | 0 | 128,877 |
| `glibc` | Shimizu | no | 299 | 3 | 2,843 |
| **`glibc_fma`** | Shimizu | yes | **0** | **0** | **0** |

Max ulp for every losing flavour is ≤ 3.

**Why this is load-bearing beyond the desktop:** bionic's libm is msun-derived,
so **Android and desktop are expected to select different flavours**. The enum is
how P7 picks without a second port. (`msun_fma` already passes the *corpus* while
failing the fuzz — a good illustration of why the corpus alone is not sufficient
evidence.)

### numpy dispatch probe

Ran the same `np.exp`/`np.tanh` vector under `NPY_DISABLE_CPU_FEATURES` at three
levels. numpy build: baseline `X86_V2`, dispatch `X86_V3` found (V4/AVX512 not on
this CPU).

| | default | no AVX512 | no `X86_V3` | no AVX2/FMA3 |
|---|---|---|---|---|
| `np.exp` bits | — | same | **same** | same |
| `np.tanh` bits | — | same | **CHANGED** | same |

- **`np.exp` (float64) is dispatch-invariant** ⇒ numpy has no float64 SIMD `exp`
  kernel in play here; it falls through to libm. The FMA that matters is glibc's
  own ifunc (`__exp_fma`), chosen independently of numpy's dispatch. This is why
  `exp64_fma` matches at all three levels and 10⁸/10⁸.
- **`np.tanh` (float64) IS SIMD-dispatched** and changes bits when `X86_V3` is
  disabled.

### Trap recorded: `np.tanh` is not `math.tanh`

76,644 / 214,333 corpus arguments (≈36%) and ~20% of uniform draws give different
bits, max 2 ulp. **The production value site uses scalar `math.tanh`**, so this
does not bite v1 — but a future site reaching for `np.tanh` would need its own
compat function, *and* that function would be SIMD-dispatch-dependent per the
probe above. `tests/rustport/test_g0_compat.py::test_np_tanh_is_not_math_tanh`
asserts the inequality so nobody "fixes" it into a false equivalence.

---

## 5. Fleet legs (laptop + M5)

Run 2026-07-31 via `harness_transcendental.py compare --via-cli …` (neither box
has maturin). The CLI path was first validated on the local box: `--via-cli`
reproduces the wheel-path corpus counts of §4 exactly, so the transport is not a
variable. Corpus = the same checked-in `transcendental_inputs.npz` (201,525 `z` /
214,333 tanh args / 428,666 expm1 args); fuzz = **10⁷** per implementation
(not 10⁸ — both boxes were carrying live eval load; nice -19).

Raw: `G0_fleet_laptop.json`, `G0_fleet_m5.json`, `G0_fleet_summary.json`
(+ the two `.log` files).

| box | platform | libc | python / numpy |
|---|---|---|---|
| local (§1–4) | WSL2 Ubuntu, x86-64, 5900XT | glibc 2.39 | 3.12.3 / 2.4.4 |
| laptop (`laptop-wsl`) | WSL2 Ubuntu 26.04, x86-64, i7-14650HX | glibc **2.43** | **3.14.4** / 2.4.6 |
| M5 (`Mac`) | macOS 26.5.2, **arm64**, Apple M5 | Apple libSystem 1356.0.0 | 3.12.13 / 2.5.1 |

### Laptop — identical to the local leg, count for count

| leg | exp64 | exp64_fma | msun | msun_fma | glibc | **glibc_fma** |
|---|---|---|---|---|---|---|
| corpus `np.exp` (201,525) | 7,205 | **0** | — | — | — | — |
| corpus `math.tanh` (214,333) | — | — | 3 | **0** | 3 | **0** |
| corpus `math.expm1` (428,666) | — | — | 384 | 85 | 299 | **0** |
| fuzz 10⁷ exp | 3,469 | **0** | — | — | — | — |
| fuzz 10⁷ tanh | — | — | 13,044 | 12,795 | 273 | **0** |

Every corpus number matches §4 **exactly** (7,205 / 3 / 384 / 85 / 299 /
76,644 `np.tanh`≠`math.tanh`) across a glibc bump (2.39→2.43), a CPython bump
(3.12→3.14) and a different Intel CPU. `np.exp`'s 4,096-point digest is also
byte-identical to the local box. Winner: **`exp64_fma` + `glibc_fma`**, i.e. the
same selection the local leg made.

### M5 — no flavour reaches 0; fallback trigger

| leg | exp64 | exp64_fma | msun | msun_fma | glibc | glibc_fma |
|---|---|---|---|---|---|---|
| corpus `np.exp` (201,525) | 7,206 | **1** | — | — | — | — |
| corpus `math.tanh` (214,333) | — | — | **68,377** | 68,380 | **68,377** | 68,380 |
| corpus `math.expm1` (428,666) | — | — | 37,833 | **37,540** | 37,918 | 37,625 |
| fuzz 10⁷ exp | 10,029 | 9,200 | — | — | — | — |
| fuzz 10⁷ tanh | — | — | 163,339 | **163,292** | 176,085 | 176,025 |

Max ulp is 1 (exp, expm1) / 2 (tanh) everywhere — no flavour is *wrong*, none is
*identical*. Three things the table says:

1. **The FMA axis is nearly a no-op here.** `msun` vs `msun_fma` differ by 3 of
   214,333 on the tanh corpus. Apple's libm is a **third implementation**, not
   either ported upstream at either contraction setting — so the existing
   `LibmFlavor` enum cannot be widened to cover macOS by picking a member.
2. **The divergence is not only in `expm1`.** `expm1` misses 8.8% of the corpus
   but `tanh` misses 31.9% — so Apple's `tanh` differs beyond the kernel the
   x86 story lives on (where reconstructing fdlibm `s_tanh` over the platform's
   own `expm1` reproduced `math.tanh` 214,333/214,333).
3. **`np.exp` (float64) differs across the ISA but `np.tanh` does not.** The
   4,096-point `np.exp` digest is `1da2cea9…` on the M5 vs `0c8d0bfa…` on both
   x86 boxes (consistent with the 1-value corpus miss: numpy falls through to
   the platform libm for float64 `exp`). The `np.tanh` digest is
   `dac49bd5…` on **all three** boxes — numpy's own SIMD tanh kernel is
   cross-ISA identical, while scalar `math.tanh` is not. The `np.tanh` ≠
   `math.tanh` corpus gap is therefore 34,978/214,333 (16%) on the M5 vs
   76,644 (36%) on x86 — same numpy kernel, different libm to compare against.
   The dispatch probe is ISA-invariant on the M5 (the `NPY_DISABLE_CPU_FEATURES`
   variants name x86 groups, so the three variant runs are all the default; no
   aarch64 dispatch axis was probed).

**Status of this leg:** the M5 is a bench/exhibition box, not a v1 deployment
target, and this report records the measurement only — the routing decision
(pre-registered ≥99.9% fallback vs an Apple `LibmFlavor` port vs declaring macOS
out of parity scope) is not taken here. What *is* settled: **the x86-64/glibc
deployment path is unaffected**, and the flavour enum's premise (that platforms
select different members) now has a platform where **no member is selectable**.

---

## Reproducing

```bash
.venv/bin/maturin develop --release --manifest-path rust/carc/carc-py/Cargo.toml
cargo test --manifest-path rust/carc/Cargo.toml -p carc-core          # 31 unit tests
.venv/bin/python -m pytest tests/rustport/ -q                          # 104 fast guards
.venv/bin/python scripts/rustport/reconcile_mt19937.py                 # ~10 s
.venv/bin/python scripts/rustport/reconcile_npsum.py                   # ~30 s
.venv/bin/python scripts/rustport/reconcile_fsum.py                    # ~40 s
.venv/bin/python scripts/rustport/harness_transcendental.py all \
    --games 100 --fuzz 100000000                                       # ~2 min
```

Toolchain is pinned in `rust/carc/rust-toolchain.toml` (1.96.0). **Bumping it
invalidates this evidence** — re-run the gates before adopting a new toolchain.
The `exp` data table is checked in and drift-guarded:
`python3 scripts/rustport/gen_exp_table.py --check`.

## Pending

- ~~**Fleet legs (laptop, M5).**~~ **RUN 2026-07-31** — see
  [§5 Fleet legs](#5-fleet-legs-laptop--m5). Laptop = local, count for count;
  the M5 has no bit-exact flavour and is the open item below.
- **M5 / macOS parity routing (open).** No `LibmFlavor` reaches 0 mismatches on
  arm64 macOS (best: 1/201,525 exp via `exp64_fma`; 68,377/214,333 tanh via
  `msun`≡`glibc`, max 2 ulp). This is the first platform to trip the spec's
  pre-registered fallback condition. **No decision taken** — the options as they
  stand are (a) the pre-registered ≥99.9% per-move fallback, (b) an Apple-libm
  `LibmFlavor` member, (c) macOS declared out of parity scope (bench box only).
  Nothing in the x86-64/glibc path depends on the answer.
- **Android/device leg** — deferred to P7 by the spec; E4's ARM↔x86 losslessness
  is the interim evidence.
- **`fsum` non-finite semantics.** The Rust port panics on non-finite input /
  intermediate overflow instead of raising CPython's `OverflowError` /
  `ValueError`. The leaf never feeds those; `fsum_checked()` exposes the full
  semantics as a `Result` if a later phase needs them.
- **numpy buffered reductions.** `npsum` models the *unbuffered* contiguous 1-D
  path (what the two prior sites use). A casting / non-contiguous / >8192-element
  buffered reduce would chunk at `bufsize` and reorder; no such call site is in
  scope for v1.
