# G7 — Android wheel + on-device (rust port P7)

**STATUS: MEASURED 2026-08-01. No PRODUCTION.yaml change, no strength claim, no
change to what the app plays.** The phone still runs the Python `k4x688` path;
the Rust backend ships in the APK but is inert until a caller opts in.

Device of record for every on-device number below:

| | |
|---|---|
| model | Pixel 9 Pro (`caiman`), arm64-v8a |
| android | 17, sdk 37, kernel `6.1.157-android14-11-gbd23337e42e7-ab14791245` |
| python | Chaquopy 17 CPython 3.12.12 (Clang 18.0.4) |
| numpy | **1.26.2** (Chaquopy's build — note: the desktop legs ran 2.4.4) |
| carc_rs | 0.1.0, `requirements/carc_rs.so`, rustc 1.96.0 |
| reached via | adb over tailscale, `100.64.4.100:38025` |

Raw artifacts: `G7_libm_device.json` (native leg), `device/p7/*.json` (Chaquopy
legs, pulled off the phone). Those files are authoritative over this prose.

---

## Leg 1 — the libm flavour. **ANSWERED: bionic is `msun`; no fallback needed.**

This is the leg the phase existed to settle, and the G0 fleet amendment is why it
could not be assumed: the M5 showed a platform can be a **third** implementation
that no `LibmFlavor` member matches, which would have put Android in
pre-registered-fallback territory. P3 §3 is why no other gate could stand in for
it — the search is nearly libm-blind, so a search-sized gate passes with the
wrong flavour.

It is measured in two halves because the two production sites reach two different
pieces of code:

| site | who implements it | leg |
|---|---|---|
| `math.tanh` (value_norm) | **bionic** libm, via CPython's thin wrapper | native |
| `math.expm1` | bionic (tanh's kernel; the axis G0 localised the divergence to) | native |
| `np.exp` on a float64 ndarray (softmax prior) | **numpy's own SIMD kernel**, NOT libm | Chaquopy |

### 1a — native half (`bionic_libm_probe` + `carc-cli`, NDK-built, over adb)

Reference and all four flavours computed **on the device**, compared **on the
device** (the tailscale link pulls at ~140 KB/s; pulling a 10⁷ fuzz leg measured
out at hours). The on-device comparator is itself gated: on the corpus legs the
raw outputs were pulled and the same summary re-derived with numpy, and the two
must agree or the run aborts. All three corpus legs are `host_cross_checked`.

| site | flavour | corpus mismatches | 10⁷ fuzz mismatches | max ulp |
|---|---|---|---|---|
| `tanh` | **msun** | **0 / 214,333** | **0 / 10,000,000** | 0 |
| | msun_fma | 3 | 278 | 3 |
| | glibc | **0** | **12,867** | 3 |
| | glibc_fma | 3 | 13,111 | 3 |
| `expm1` | **msun** | **0 / 428,666** | **0 / 10,000,000** | 0 |
| | msun_fma | 299 | 1,866 | 1 |
| | glibc | 85 | 701 | 1 |
| | glibc_fma | 384 | 2,374 | 1 |
| `exp` (scalar) | **exp64_fma** | **0 / 201,525** | **0 / 10,000,000** | 0 |
| | exp64 | 7,205 | 3,487 | 1 |

**G0's cautionary tale reproduced on a second platform.** `glibc` is bit-exact on
the entire 214,333-argument production tanh corpus and then fails on 12,867 of
10⁷ fuzz arguments. A corpus-only gate would have selected the wrong flavour
here, exactly as `msun_fma` would have been selected on the desktop. Do not
re-derive this flavour from a corpus run.

### 1b — Chaquopy half (device numpy + `math`, inside the app process)

| site | impl | corpus mismatches | 2×10⁶ fuzz | verdict |
|---|---|---|---|---|
| **`np.exp` (production)** | **exp64_fma** | **0 / 201,525** | **0** | bit-exact |
| | exp64 | 7,205 | 1,389 | — |
| `math.tanh` | **msun** | **0 / 214,333** | **0** | bit-exact |
| | glibc | 0 | 36 | corpus-only |
| | msun_fma / glibc_fma | 3 / 3 | 90 / 110 | — |
| `math.expm1` | **msun** | **0 / 428,666** | — | bit-exact |

`platform_parity_achieved: true`.

Also reproduced from G0 §3, now on ARM: **`np.tanh` ≠ `math.tanh`** on
76,641 / 214,333 corpus args (35.8%, ≤2 ulp). Production uses scalar `math.tanh`,
so v1 is unaffected — recorded so nobody "fixes" the difference into a false
equivalence.

### The answer

> **Android's production config is `tanh_flavor = "msun"`, `exp_fma = true`.**
> Both are existing `compat::LibmFlavor` members — **no second port, no widening
> of the enum, and the spec's pre-registered fallback is NOT invoked.**

It **differs from the desktop** (`glibc_fma` / `exp_fma=true`, G0 §2), which is
precisely what G0 predicted when it said "bionic is msun-derived, so Android is
expected to select a different flavour — the enum is the mechanism". The flavour
is a `SearchConfigRs` knob, so this costs a config value, not code. It is written
down in exactly two places: `android_bridge.ANDROID_TANH_FLAVOR` and
`RustPortDeviceTest.TANH_FLAVOR`.

---

## Leg 2 — replay identity vs desktop. **PASS, 0 mismatches / 3,165 plies.**

Both E4 phone archives + 20 champ games, replayed through the Android
`carc_rs` wheel, compared per ply against digests frozen on the desktop by
`scripts/rustport/p7_make_device_assets.py`.

| | |
|---|---|
| records | 22 (2 × E4 archive, 20 × `champ_games.jsonl`) |
| plies | 3,165 |
| per-ply `sha256(string_representation)` | **all match** |
| per-ply scores | **all match** |
| final scores / terminal flag | **all match** |
| `all_identical` | **true** (0.2 s) |

This extends the E4 ARM↔x86 losslessness precedent to the Rust core: the same
bytes, on a different ISA, from a different libm, under a different numpy.

A second check fell out of building the assets: the desktop generator refuses to
freeze an E4 record whose replayed final scores disagree with the archive's own
recorded scores. Both archives passed, so the two phone games *the champion
actually played* still replay exactly.

---

## Leg 3 — s/move. **PASS: k8×1376 median 1.50 s (bar ≤ 2 s).**

20 midgame positions (ply 60 of 20 distinct champ games), replayed from
`(deck_seed, prefix)`, one agent per position, `threads=4`.

| budget | sims/move | median | mean | min | max | p90 |
|---|---|---|---|---|---|---|
| **k8×1376 (champion of record)** | 11,008 | **1.5045 s** | 1.4991 | 1.2115 | 1.7765 | 1.607 |
| k4×688 (current mobile carve-out) | 2,752 | **0.4755 s** | — | — | — | — |

Two things worth stating plainly:

1. **The full champion budget is now cheaper on the phone than the carve-out was
   in Python.** 11,008 sims at 1.50 s/move against the deployed Python k4×688 at
   1.7 s/move (memory `reference_android_app`) — **4× the search for 0.88× the
   clock.** That is what the phase was for.
2. At the *same* budget the port is **~3.6×** (0.4755 s vs 1.7 s). The gap
   between 3.6× and the desktop's 9.4× t1 is unexamined and is a phone/desktop
   question (cores, memory system, governor), not a correctness one.

**No strength claim is made or implied.** Behaviour identity is what transfers
strength (the CL-071 precedent), and leg 2 is the identity evidence; whether to
spend the headroom on budget is Joshua's call, and it needs a
`PRODUCTION.yaml` `deploy_profiles.mobile` change that this phase did not make.

---

## Leg 4 — 50-move thermal soak at k8×1376. **Throttle ≈ 1.007×, i.e. none.**

Run twice, because the obvious version of this leg measures the wrong thing.

| | walk-forward | **fixed position** |
|---|---|---|
| what | 50 consecutive moves from ply 60 | the SAME position searched 50× |
| moves | 50 / 50, 0 errors | 50 repeats |
| wall | 51.8 s | 68.7 s |
| first-10 mean | 0.6952 s | 1.3753 s |
| last-10 mean | 1.1435 s | 1.3851 s |
| ratio | 1.645 | **1.007** |
| min / max | — | 1.2854 / 1.542 s |

**The walk-forward 1.645 is not throttling — it is the board filling up.** That
soak advances `k_remaining` 72 → 47, and per-leaf cost grows with placed meeples
(CLAUDE.md's own engine note: more farm/city util calls). Heat and board fill are
perfectly confounded in it, so on its own it can only bound throttling from
above.

The fixed-position run removes the confound: same position, `move_idx` pinned, so
every repeat is bit-identical work and the only free variable is how fast the
phone does it. All 50 repeats returned the same action (`1467` — asserted, since
a differing action would mean the work was *not* identical and the curve would be
meaningless), and the curve is flat across 68.7 s of continuous full-budget
search:

```
 0- 9: 1.350 1.321 1.459 1.357 1.353 1.432 1.368 1.407 1.363 1.343
40-49: 1.339 1.357 1.314 1.431 1.337 1.349 1.542 1.384 1.403 1.395
```

**⇒ thermal throttling over ~69 s of sustained k8×1376 search is 0.7%,
inside the noise.** The walk-forward curve's entire slope is positional. Every
move in both soaks stayed under the 2 s bar.

Caveat on duration: 69 s is a long *turn sequence*, not a long *session*. A
multi-hour game with the screen on is a different thermal question and this does
not answer it.

**The phone's thermal zones are not readable from the app** (SELinux; `_thermal()`
returns `{}` on this device), so the s/move curve is the only throttle evidence
available from inside the process. `logcat` does carry the platform's own
`pixel-thermal VIRTUAL-SKIN` readings (~27-28 °C throughout this session) and
would be the better instrument if this ever needs a real thermal answer.

---

## Leg 5 — x86_64 emulator smoke

See `G7_emulator.log` / `device_emu/`. The AVD (`carc35`, android-35 google_apis
x86_64, KVM available) exists on this box, so the x86_64 wheel is exercised
rather than merely built. The Pixel legs are the ones that matter; this leg only
answers "does the x86_64 artefact load and replay".

---

## Build-tooling findings

1. **`PYO3_CROSS_LIB_DIR` is not settable against Chaquopy's artifact.** The
   `com.chaquo.python:target` zip ships `include/`, `jniLibs/` and `lib-dynload/`
   and **no stdlib**, so there is no `_sysconfigdata*.py` and pyo3's build script
   hard-fails. The flag's purpose (resolve against the target's libpython, never
   the host's) is carried instead by an explicit `-L<jniLibs/abi> -lpython3.12`
   plus a readelf `DT_NEEDED` assertion. This corrects the spec's P7 line.

2. **⚠️ NDK r27.3 does NOT default to 16 KiB page alignment.** Measured: a
   trivial `clang --target=aarch64-linux-android21 -shared` lands at `p_align
   0x1000`; adding `-Wl,-z,max-page-size=16384` moves it to `0x4000`. So **the
   shipped `carc-cy` wheels are 4 KiB-aligned and would not load on a 16 KiB-page
   device.** It is latent, not live — the Pixel 9 Pro runs 4 KiB pages by default
   — and the cy link flags were left frozen so the refactor could be proved
   byte-identical. The new Rust wheel passes the flag and asserts it. **This is a
   decision for Joshua**, not something P7 took: fixing cy means changing shipped
   bytes.

3. **Wheel naming: `cp312-cp312`, not `abi3`.** The object *is* abi3-clean
   (carc-py enables pyo3's `abi3-py312`), so `cp312-abi3` would also be honest —
   but Chaquopy 17 bundles exactly one interpreter, the wheel version is
   content-addressed and rebuilt per APK, and `cp312-cp312-android_21_<abi>` is
   the exact shape of Chaquopy's own wheels and of the already-shipping `carc-cy`
   wheel. A cp312 tag on an abi3-clean object is a *narrower* claim than the
   truth, so it is always correct; the reverse would not be. The desktop maturin
   wheel stays `abi3-py312`. Flip `ABI_TAG` in `build_rust_wheels.py` if Chaquopy
   ever ships two interpreter versions.

4. **The cy refactor is byte-identical.** `build_cy_wheels.py` now sits on
   `_chaquopy_common.py`; both ABI wheels rebuild to the same sha256 as before
   the refactor (`b663f6b0…`, `535934f5…`).

5. **`tests/android` and `tests/rustport` cannot be collected in one pytest
   process** — pre-existing, reproduced with `pytest tests/android/test_bridge.py
   tests/rustport/test_p1_engine.py --co` on an otherwise clean tree. Importing
   `android_bridge` pulls in `carcassonne_ai`, which trips `prod_leaf_env`'s
   import-order guard for every rustport module. Each suite is green standalone
   (android 96, rustport 269). Not fixed here: the honest fix is a decision about
   whether the whole `tests/` tree should run under the production leaf env.

---

## What did NOT change

`governance/PRODUCTION.yaml`, `experiments/results.csv`, the claim registry, and
the app's default behaviour. `android_bridge`'s backend defaults to `"python"`;
`carc_rs` ships in the APK but nothing imports it unless a game asks for
`backend: "rust"`. The phone keeps playing the Python k4×688 path until Joshua
flips it.
