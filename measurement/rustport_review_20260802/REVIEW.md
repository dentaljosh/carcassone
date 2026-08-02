# RUST PORT REVIEW — 2026-08-02 (read-only, adversarial, 2-skeptic)

> **Status: READ-ONLY REVIEW, 2026-08-02. NO FIXES APPLIED.** Scope: `rust/carc/` (carc-core,
> carc-py, carc-cli), `src/carcassonne_ai/rust_agent.py`, the rust-mirror path in
> `android_bridge.py`, `scripts/rustport/`, `android/tools/build_rust_wheels.py`.
>
> Method: every candidate finding was put to two independent skeptics with the code in hand.
> **CONFIRMED** = neither skeptic could refute it. **CONTESTED** = one of two refuted it; both
> sides are compressed below so nobody re-litigates from scratch.
>
> Two agents were editing `governance/PRODUCTION.yaml` / `champion_factory.py` /
> `android_bridge.py` during this review — line numbers in those three files may have drifted
> by a few lines; the quoted code is the anchor.
>
> Prior art deliberately NOT re-reported: `docs/RUSTPORT_BUILD_SPEC_2026-07-31.md` (G0–G7, all
> PASSED) and `measurement/rustport_p6/BACKEND_BYPASS_AUDIT_20260801.md`.

---

## THE ONE-PARAGRAPH ANSWER

**The port is bit-exact and the gates prove it. What the gates do not touch is (a) the provenance
of the binary that actually ships to the phone, (b) memory and wall-clock on the deployed budget,
and (c) whether a gate artifact saying `PASS` means anything.** The single most urgent item is
#1: the Android wheel is cross-compiled with an *unpinned* rustc — `rust-toolchain.toml` is
never in scope for the cargo invocation — so the first `rustup update` ships a phone binary built
off-gate, with a green content-hash cache and no record anywhere of which compiler built it (#9
is why it would be undetectable after the fact). Behind that sit three measured performance
findings on the exact deployed profile (k=8 × 1376 sims, 4 threads): the search allocates the
multi-KB board-repr key **three times per node** (95 MB peak RSS for one move, #2), SHA-256-hashes
that key on every node for a field only the trace harness reads (8–13% of wall clock, #3), and
builds it with ~350 throwaway `String`s (a further 9.4%, #4). None of these change a single bit of
output — which is exactly why seven green gates say nothing about them.

---

## CONFIRMED — neither skeptic could refute

### 1. Android wheel is cross-compiled with an UNPINNED rustc (HIGH)

`android/tools/build_rust_wheels.py:185`

`build_abi()` runs `cargo build --release --target <triple> -p carc-py --manifest-path
rust/carc/Cargo.toml` through `subprocess.run(cmd, check=True, env=env)` with **no `cwd=`** and no
`RUSTUP_TOOLCHAIN` in `cargo_env()`. rustup resolves toolchain override files from the *current
working directory* upward; `--manifest-path` has no bearing on toolchain selection. Gradle invokes
the script from `android/` (`android/app/build.gradle.kts:187`, `BuildRustWheels.run()`, no
working-dir override), and the script's own documented usage runs it from the repo root. Neither
has `rust/carc/rust-toolchain.toml` as an ancestor, so the device wheel is built with whatever
`rustup default` happens to be. Confirmed empirically in this checkout:

```
rust/carc $ rustup show active-toolchain
1.96.0-x86_64-unknown-linux-gnu (overridden by '.../rust/carc/rust-toolchain.toml')
android/  $ rustup show active-toolchain
stable-x86_64-unknown-linux-gnu (default)          <-- pin NOT applied
```

`ensure_rust_target()` (line 115) has the same defect — `rustup target add <triple>` from the
wrong cwd installs the target into `stable`, not into the pinned 1.96.0.

This is precisely the failure the file's own comment at lines 87–89 says the pin exists to
prevent ("a toolchain bump invalidates the G0 bit-exactness evidence, so it must also invalidate
the wheel"), and the invalidation mechanism it relies on *cannot fire*: `source_version()` hashes
the **declared** pin bytes, which do not change when `stable` moves underneath them.

**Why the gates missed it.** G0–G7 all run against the *host* `carc_rs` built from `rust/carc`,
where the override does apply. No gate builds or inspects the Android wheel's compiler. G7's
device report carries s/move and libm legs only.

**Latent, not live** — today `stable` happens to be 1.96.0. It goes live on the first
`rustup update`.

**Smallest fix.** Pass `cwd=CRATE_DIR` to both `subprocess.run` calls (cargo build and the
`rustup target` probes), or set `env["RUSTUP_TOOLCHAIN"]` by parsing `channel` out of
`rust/carc/rust-toolchain.toml`. Then assert the resolved `rustc --version` into the wheel's
build log so a mismatch is detectable after the fact (see #9).

---

### 2. The node key is heap-allocated three times per node — 95 MB peak RSS on the exact phone profile (HIGH)

`rust/carc/carc-core/src/search/mod.rs:271` (and `:400`, `:165`)

Each search node's `string_representation` (1.2–5.0 KB) is stored three separate times:

- once as `Node::key` (`search/mod.rs:165`, `pub key: Box<str>`),
- again as the `Tree::index` map key — `self.index.insert(node.key.clone(), id)` (`:271`),
- a third time as the `Tree::legal_cache` key — `.insert(key.to_string().into_boxed_str(),
  legal.clone())` (`:400`).

Measured on an instrumented copy of carc-core (VmHWM from `/proc/self/status`):

| ply | nodes | distinct key bytes | key storage / tree |
|---|---|---|---|
| 40 | 931 | 2.43 MB | 7.3 MB |
| 80 | 1368 | 5.85 MB | 17.6 MB |
| 110 | 1122 | 6.23 MB | 18.7 MB |

`FairAgentRs{k_dets:8, threads:4, sims:1376}.choose_action` at ply 80: **0.512 s, peak RSS 95 MB**
(22 MB before the move). The deployed mobile profile in `governance/PRODUCTION.yaml`
(`k_dets=8, sims_per_det=1376, rust_threads=4`) keeps four such trees live concurrently —
`fair::search_worlds` gives each world a fresh `Searcher` with a fresh `Tree`, so nothing is
amortised. Removing just **one** of the three copies (the `legal_cache` insert) drops the same
move to **62 MB peak RSS and 0.398 s** — 33 MB and 22% of the move time were that single
redundant copy.

**Why the gates missed it.** No gate in the port measures memory at all; G7's device report has
s/move and libm legs only. This has never been priced on a device that also hosts the Chaquopy
Python interpreter, the engine mirror and the UI.

**Smallest fix.** Store the key once behind an `Rc<str>` (the tree is per-thread, so `Rc`
suffices) and hand handle-clones to `Tree::index` and `Tree::legal_cache`. Better still for the
index: key it by a precomputed 64-bit hash of the repr, keeping the `Box<str>` on the node only
for collision checks.

---

### 3. Every node pays a SHA-256 over its full multi-KB key for a field only the trace sink reads — 8–13% of search wall clock (HIGH)

`rust/carc/carc-core/src/search/mod.rs:194`

> *Two independently-submitted findings (one medium, one high) were the same defect at the same
> line; merged here at the higher severity with the merged evidence.*

```rust
fn new(key: String, player_to_move: usize, terminal_value: f64) -> Self {
    let digest = sha256_hex(key.as_bytes())[..16].to_string().into_boxed_str();
```

`Node::new` is called from `Tree::intern` for every node. `grep -rn digest` over carc-core and
carc-py shows exactly two consumers — `trace_expand` (`:904`) and `trace_sim` (`:920`) — both of
which begin `match self.trace.as_mut() { None => return, ... }`. **No production path ever
attaches a sink:** `Searcher::new` (`:313-321`) sets `trace: None`; the only `with_trace` call
site in the workspace is `carc-py/src/lib.rs:372`, reachable only via
`MirrorState.search_single(trace_path=...)`. `fair/mod.rs:416` and `:425` both go through
`search::search_single`, so the phone path hashes a 1.2–5.0 KB string with a scalar 64-round
SHA-256 for every node of every world of every move, and throws the result away.

`sha256.rs:144-148` compounds it: the hex is built with a heap-allocating `format!("{b:02x}")`
per byte — 64 `format!` calls and a 64-char `String`, of which the caller discards 48 chars and
re-allocates the remaining 16 via `.to_string()`.

Measured A/B (identical crate, one line changed to `String::new().into_boxed_str()`, release
profile `lto=thin`, 7-rep min, 3 alternating rounds), `search_single` at 1376 sims:

| ply | before | after | delta |
|---|---|---|---|
| 40 | 0.1038–0.1148 s | 0.0911–0.0949 s | −9% |
| 55 | 0.1285–0.1310 s | 0.1153–0.1192 s | −9.5% |
| 80 | 0.1536–0.1664 s | 0.1317–0.1382 s | −13% |

Isolated cost of the wasted call: 5.7 µs at a 1255-byte key, 10.2 µs at 3054 bytes, 17.7 µs at
5010 bytes — times ~1000–1400 nodes per search.

**Why the gates missed it.** The digest is dead output, not wrong output: removing it changes no
bit of any gate artifact. Gates assert identity, never cost. The 1.551 s/move phone budget was
measured *with* the waste, so it reads as "the port's speed" rather than "the port's speed minus
a tenth".

**Smallest fix.** Make `digest` an `Option<Box<str>>` populated only when `self.trace.is_some()`,
or delete the field and compute `sha256_hex(&n.key)[..16]` inside `trace_expand`/`trace_sim`. The
digest is a pure function of `node.key`, so nothing about the trace format changes. Separately,
replace the `format!`-per-byte loop in `sha256_hex` with a nibble lookup table and add a
`sha256_hex_prefix(data, n)`.

---

### 4. `string_representation` builds ~350 throwaway Strings per call — a byte-identical single-pass writer is 9.4% faster end to end (MEDIUM)

`rust/carc/carc-core/src/repr_key.rs:42`

This is the hottest function in the port — it is the transposition key, computed once per
`create_or_get` (~1000–1400× per world, 8 worlds per move) — and it is written as a tree of
`Vec<String>` + `join`. Per placed tile it allocates `row.to_string()`, `col.to_string()`, a
`format!` for the quoted description, **a clone of the `'static` registry's `rot_sig_repr`
String**, and a `py_tuple` join (`repr_key.rs:51-56`; `py_tuple` at `:25-31` allocates again via
`format!`/`join`). At ply 80 that is ~70 tiles × 5 allocations plus the outer joins — ~350 heap
allocations to produce one 4.5 KB string. `RotTile::rot_sig_repr` (`tiles/mod.rs:252`) lives in a
`OnceLock<Vec<RotTile>>` registry (`tiles/mod.rs:424`) and is effectively `'static`, so the clone
is pure waste.

Rewritten as a single `String::with_capacity(6144)` with `write!` appends (no `Vec<String>`, no
`rot_sig_repr` clone), output verified **byte-identical** at ply 55, `search_single` at 1376 sims
over 3 alternating rounds: ply 40 0.1038–0.1148 → 0.0925–0.0960 s; ply 55 0.1285–0.1310 →
0.1155–0.1186 s; ply 80 0.1536–0.1664 → 0.1417–0.1491 s — consistently **−9.4%**. Isolated:
5.1 µs/call at ply 20, 13–15 µs at ply 55, 17–25 µs at ply 100.

**Why the gates missed it.** Same reason as #3 — the rewrite is byte-identical, so every gate is
blind to the difference by construction.

**Smallest fix.** Write into a single pre-sized `String` (or a reusable buffer owned by
`Searcher`, since the key is immediately moved into the node) with `write!`/`push_str`; change
`rot_sig_repr` to `&'static str` or borrow instead of cloning. Keep byte-equality as the test
gate — the measured rewrite already passes it.

---

### 5. `backend="rust"` guard misses env-inherited `meeple_dedup` / `intra_reuse` — a Rust champion gets stamped with a search variant it does not implement (MEDIUM)

`src/carcassonne_ai/champion_factory.py:795`

```python
if backend == "rust" and (meeple_dedup or intra_reuse or parallel_workers):
    raise ValueError("backend='rust' does not carry the python-only search variants ...")
```

Those are the **raw kwargs**, and `None` is their inherit-from-process sentinel:
`meeple_equiv.resolve(None)` returns the module global `MEEPLE_DEDUP`, initialised from
`CARCASSONNE_MEEPLE_DEDUP` (`meeple_equiv.py:51,64`, `resolve` at `:81-83`) and flippable at
runtime via `set_enabled(True)`; `intra_reuse.resolve(None)` likewise returns `INTRA_TURN_REUSE`
from `CARCASSONNE_INTRA_TURN_REUSE` (`intra_reuse.py:62,70,78-80`).

So in a process where the env flag is on and the caller passes nothing, **the guard does not
fire**: `RustFairAgent` is built (carrying neither variant — the raise at `:795` exists precisely
because carc_rs has neither), and then line 857 — `if meeple_equiv.resolve(meeple_dedup):`, which
*does* consult the env — stamps `manifest["meeple_dedup"] = {"enabled": True, ...}` on it. The
result is a manifest asserting a search feature the executing engine does not have: a label
rather than the function, i.e. the R1/R7 class the factory's `verify_leaf` exists to prevent. The
Python branch is consistent (it passes `meeple_dedup=None` down and the agent resolves the same
env), so the divergence is Rust-backend-only.

**Why the gates missed it.** G6/backend runs with the env flags off, so `resolve(None)` and the
raw kwarg agree and the two code paths are indistinguishable.

**Smallest fix.** Resolve before guarding: `if backend == "rust" and
(meeple_equiv.resolve(meeple_dedup) or intra_carry.resolve(intra_reuse) or parallel_workers):
raise` — an env-on process then fails closed instead of stamping a feature the Rust engine lacks.

---

### 6. `reconcile_backend` emits `verdict: PASS` for gate G6/backend with zero agreement evidence (MEDIUM)

`scripts/rustport/reconcile_backend.py:548`

```python
ok = (n_bad == 0
      and (agree_rate == 1.0 if totals["action_checks"] else True))
```

When no agreement games ran — `--leg bench`, or `--games 0` — `jobs` is empty (`:513-514`, jobs
appended only `if "agree" in legs`), `totals` stays `_blank()` (`:119-123`: `action_checks: 0`,
`mismatches: []`), so `n_bad == 0` and `action_checks == 0` and **`ok` is True**. The script then
writes `measurement/rustport_p6/G6_backend_{tag}.json` with `"gate": "G6/backend"`,
`"verdict": "PASS"`, `"action_agreement": null`, `"n_games": 0`, and exits 0 (`:578`).

Because the filename is keyed only on `--tag` (default `"run"`, `:553`), a bench-only invocation
**overwrites a real agreement artifact in place** with a PASS that proves nothing — and both the
exit code and the `verdict` field, the two things a runbook or a later reader greps, report
success. This is the sha-of-empty shape: absence of evidence scored identically to evidence of
identity. `reconcile_fair.py:686` has the same `ok = n_bad == 0` with no non-empty check.

**Why the gates missed it.** This *is* a gate. Nothing audits the gate's own vacuity condition.

**Smallest fix.** Require positive evidence — `ok = n_bad == 0 and totals["action_checks"] > 0
and agree_rate == 1.0` when the agree leg was requested — and emit `verdict: "N/A"` (not PASS)
when it was not. Optionally fold the leg set into the artifact filename so a bench run cannot
clobber an agreement run.

---

### 7. `action_size()` / `tile_action_count()` overflow i32 for large `window_size`, which `GameConfig::resolve` does not bound (MEDIUM)

`rust/carc/carc-core/src/action_space.rs:59`

```rust
pub fn tile_action_count(w: i32) -> i32 { w * w * N_ROTATIONS }
```

i32 arithmetic; the release profile wraps on overflow. `GameConfig::resolve` validates only
`window_size >= 1` (`game.rs:174-176`), and `window_size` is an FFI parameter on
`MirrorState.from_seed`, `MirrorState.from_deck`, `FairAgentRs.__new__`, `resolve_game_config` and
`RustFairAgent(window_size=...)`. Past w = 23170 the product wraps: the legal mask is allocated at
the *wrapped* size, `encode()` computes a wrapped index that happens to land inside it, and
`decode()` maps it back to a completely different coordinate — **encode/decode stop being
inverses, with no error at any point.** Measured:

```
window_size=46341: true action_size = 8,589,953,135; legal_mask_bytes() length = 18543
                   legal_actions() = [9264]   (correct encoded index would be 4,294,976,560)
                   advance(9264) -> PanicException (index out of bounds) at the wrong coordinate
window_size=23171: PanicException: capacity overflow
window_size=50000: builds fine, mask length 1,410,065,419   (1.4 GB allocated on demand)
```

The Python side computes the same expression in arbitrary-precision ints, so it can only ever
raise `MemoryError` on `np.zeros(action_size)` — it cannot mis-index. **Not reachable from the
Android bridge** (which never passes `window_size`), so this is FFI-contract hardening rather
than a live production bug — but it is exactly a hostile-input silent-wrong path.

**Why the gates missed it.** Gates replay the production `window_size` only; nothing fuzzes the
config constructor's numeric range.

**Smallest fix.** Bound `window_size` in `GameConfig::resolve` (require
`1 <= window_size <= BOARD_ROWS.max(BOARD_COLS)`, or at minimum reject anything where
`checked_mul` on `w*w*4 + 11` overflows i32) and use checked arithmetic in
`tile_action_count`/`action_size` so an overflow is an error rather than a wrap.

---

### 8. `content_version_tree` hashes `target/**` and `.chaquopy-cache/**`, contradicting the Gradle input set that claims to match it (MEDIUM)

`android/tools/_chaquopy_common.py:308`

`content_version_tree(roots, suffixes)` does a bare `root.rglob("*")` filtered only on suffix,
with **no directory exclusions**, then hashes the relative path *and* the bytes (`:307-311`).
`build_rust_wheels.VERSION_ROOTS = [CRATE_DIR]` (= `rust/carc`) with
`VERSION_SUFFIXES = (".rs", ".toml", ".lock")` — so the wheel's "content-addressed source version"
includes cargo's build artifacts under `rust/carc/target/` and the extracted Chaquopy archives
under `rust/carc/.chaquopy-cache/`. The Gradle side explicitly excludes both
(`android/app/build.gradle.kts:241-244`, `exclude("target/**", ".chaquopy-cache/**")`) with the
comment *"matches the build script's own VERSION_SUFFIXES"* — a parity claim that is **false**.

In this checkout, `find rust/carc/target -type f \( -name '*.rs' -o -name '*.toml' -o -name
'*.lock' \) | wc -l` = 10, e.g.
`rust/carc/target/debug/incremental/carc_core-3ok4mz56n686i/s-hkx0qkkttd-1lhkiu7.lock` — a
per-compilation *randomized* filename — plus
`rust/carc/target/release/build/target-lexicon-2561de708ab60fa9/out/host.rs`.
`rust/carc/.chaquopy-cache/` holds `target-3.12.12-0-{arm64-v8a,x86_64}{,.zip}`.

Two consequences: the version string is **not reproducible from a git checkout** (a clean clone
and a built tree with identical sources produce different `carc-rs==X.Y.Z`), and it changes on
every local `cargo build`/`cargo test`, churning the pip requirement string and the Chaquopy cache
on every dev build — which erodes the one signal the version is supposed to carry ("the Rust
source changed").

**Why the gates missed it.** Gates never build the wheel and never assert version reproducibility.

**Smallest fix.** Give `content_version_tree` an `exclude_dirs` parameter (or hard-skip any path
with a `target` / `.chaquopy-cache` / `.git` component) and pass the same two exclusions the
Gradle fileTree uses, so the two really are one rule. A unit test hashing a fixture tree with and
without a fake `target/` pins it.

---

### 9. No provenance anywhere records which rustc / profile built the executing `carc_rs`, and `__version__` is a frozen literal (MEDIUM)

`src/carcassonne_ai/rust_agent.py:167`

`backend_provenance()` — described as "the Rust half of the fingerprint guard" (`:167-179`) —
reports `carc_rs.__version__`, `carc_rs.__file__` and the two tile-data digests.
`carc_rs.__version__` is `carc_core::VERSION = env!("CARGO_PKG_VERSION")`
(`rust/carc/carc-core/src/lib.rs:26`), i.e. the workspace `version = "0.1.0"` that has never been
bumped — it distinguishes nothing. `_g0_common.environment()` (`scripts/rustport/_g0_common.py:41-69`),
"the provenance block every G0 result carries", records host, platform, machine, python, numpy,
libc, git_rev and the same static `__version__`. It records `libc` — the thing G0 §2/§3 findings
depend on — but **never `rustc --version`, the target triple, or the release profile.**

`grep -rn "rustc" scripts/rustport/_g0_common.py scripts/rustport/fair_common.py` → no matches.
`grep -rn "1\.96" --include=*.py --include=*.yml --include=*.sh scripts/ android/tools/ .github/`
→ the only hit in the repo is `rust-toolchain.toml` itself: **the pin is declared once and
asserted nowhere.** Given that the file explicitly warns "Bumping this invalidates the G0
bit-exactness evidence", the evidence artifacts cannot be attributed to the toolchain they depend
on — and this is what makes #1 undetectable after the fact: two `carc_rs` builds from different
rustc versions are indistinguishable in every provenance record the repo writes.

**Smallest fix.** Emit build-time provenance into the module (`option_env!` plus a small
`m.add("__build__", ...)` carrying `rustc -vV`, the target triple, opt-level and lto, captured at
compile time). Add it to `environment()` and `backend_provenance()`, and assert the recorded
channel equals `rust-toolchain.toml`'s in a test.

---

### 10. The carc-rs Android wheel version omits the link flags — the exact stale-wheel gap `build_cy_wheels` closed the same day (LOW)

`android/tools/build_rust_wheels.py:90`

`source_version()` content-addresses `rust/carc` over `.rs/.toml/.lock` only (`:88-102`).
Everything that changes the emitted `.so` **without touching those files** sits outside the hash:
`C.PAGE_ALIGN_LDFLAG`, `-L<libdir> -lpython3.12`, `-Wl,-soname`, the `PYO3_CROSS*` settings, the
whole `cargo_env()` body, and any ambient `RUSTFLAGS` (`:171-172` prepends
`env.get("RUSTFLAGS", "")` verbatim). Gradle pins the requirement as
`install("carc-rs==$rustVersion")` (`build.gradle.kts:418`) precisely so a source change busts
Chaquopy's task inputs and pip's cache — but a flag change leaves the version string identical, so
the stale wheel is still resolvable.

The sibling script names this defect explicitly and fixed it on 2026-08-01:
`build_cy_wheels.py:122-126` introduces `LINK_SIGNATURE: bytes = C.PAGE_ALIGN_LDFLAG.encode()`
mixed into `content_version(..., extra=LINK_SIGNATURE)` with the comment *"Add to this string
whenever you add a flag that affects the emitted object"* — after the 16 KiB page-alignment change
proved a flag can ship silently. `build_rust_wheels` has no equivalent.

**Smallest fix.** Give `build_rust_wheels` the same `LINK_SIGNATURE` treatment — hash
`C.PAGE_ALIGN_LDFLAG`, the link-arg list, `C.PYTHON_VERSION`/`C.ANDROID_API` and this script's own
bytes into the version; and either scrub or hash inherited `RUSTFLAGS`.

---

## CONTESTED — one of two skeptics refuted

Each item below survived one skeptic and was refuted by the other. Both sides are compressed so
the next reader can pick up the argument rather than restart it. The counter-cases are stated as
they stand **in the code I read**, not as quotations of the skeptics.

### C-a. Rust panics cross the FFI as `PanicException` (a `BaseException`), so every production `except Exception` is blind to them — HIGH
`android/app/src/main/python/android_bridge.py:1059`

**For.** pyo3 maps a Rust panic to `pyo3_runtime.PanicException`, which derives from
`BaseException`, not `Exception` — verified against the built wheel (all ten panic probes reported
`type(e).__mro__[1].__name__ == 'BaseException'`). The port's own gate tooling knows this
(`scripts/rustport/lockstep_fuzz.py:503`: `except BaseException as exc:  # ... a Rust panic
arrives as pyo3's PanicException, which does not derive from Exception`). Production does the
opposite: `android_bridge.py` wraps every JNI-facing entry point in `except Exception as exc:
return _err(...)` with the comment *"never raise across JNI"* (lines 1509, 1517, 1543, 1608, 1633,
1687, 1726, 1767, 1932, 2012, 2160, 2221, 2246, 2271, 2339, 2386) — none catch a panic, so that
documented guarantee is false for the now-default backend. Worse, `_start_rust_mirror`'s safety
net at `:1059` (`except Exception as exc: self._degrade_to_python(...)`) is the one thing meant to
keep the app playable when the Rust core misbehaves; a panic in `FairAgentRs(...)`,
`start_game_from_deck(...)` or `_assert_mirror(...)` bypasses the degrade path entirely.
`RustFairAgent` has no guard at all.

**Against.** No panic is reachable from the bridge's own call pattern: the bridge never passes
`window_size`, `restore_game` validates action ids against the legal mask before replay, and the
seed reaches `from_seed` already normalised. On that reading the finding is a hardening request
about an unreachable path, and the "amplifier" framing borrows its severity from C-b/C-c, which
are themselves contested.

**Fix shape if adopted.** Catch `BaseException` (re-raising `KeyboardInterrupt`/`SystemExit`) at
the JNI boundary, in `_start_rust_mirror`'s degrade path, and in `RustFairAgent.choose_action`.

### C-b. `Game::advance` applies any *decodable* action without checking legality; `set_tile` writes with an unchecked cast — HIGH
`rust/carc/carc-core/src/engine/mod.rs:384`

**For.** `Game::advance` (`game.rs:295-310`) runs only `decode()`, which validates against the
action-space *layout*, never the legal mask, so any index in `0..action_size(w)` reaches
`state.apply_action`. `set_tile` is the only board accessor with no bounds handling —
`self.board[(coord.row * BOARD_COLS + coord.col) as usize] = id` — where `get_tile`
bounds-checks and `board_direct` reproduces CPython wrap-or-IndexError via `py_index`. On a fresh
game the window origin is `(-6, 3)`, so action 0 decodes to a negative row, the cast becomes a
huge `usize`, and it panics: `index out of bounds: the len is 1225 but the index is
18446744073709551409`. This is a genuine **divergence**, not a shared error contract — CPython's
`board[-6][3]` wraps to row 29 and `Game.get_next_state(board, 0)` *succeeds*, placing the tile
(both halves verified). Separately the same cast **aliases silently** whenever `row >= 0` and
`col >= BOARD_COLS`: with `origin_col >= 11`, `col` lands in `35..47` and `row*35 + col` is a
valid in-range index belonging to `(row+1, col-35)` — a wrong-cell write with no error anywhere.

**Against.** Only reachable by feeding an illegal action id, which is a caller-contract violation;
every production caller (`rust_agent.RustFairAgent.advance`, `_Session.apply`, `restore_game`)
sources its ids from the mask or from a validated log, and G1–G7 replay legal records only because
that *is* the contract. A panic on contract violation is arguably correct behaviour, and matching
CPython's accidental negative-index wrap would be bug-compatibility, not correctness.

**Fix shape if adopted.** Bounds-check in `set_tile` (return `Result` / surface as
`DecodeError`), and have `Game::advance` reject an index not set in `legal_mask()`.

### C-c. Seed parsing accepts empty/whitespace as seed 0 and panics on non-decimal input where Python raises `ValueError` — MEDIUM
`rust/carc/carc-core/src/compat/mt19937.rs:266`

**For.** `seed_words_from_decimal` trims, strips a sign, then iterates chars with
`.expect("seed must be a decimal integer")`. An empty digit string yields an empty limb vector,
which the `if limbs.is_empty() { limbs.push(0); }` fallback fills with 0 — so `from_seed("")`,
`from_seed("  ")` and `from_seed("-0")` all silently deal the **seed-0 deck** where
`random.seed(int(""))` raises. Measured: `deck_descriptions_from_seed('')` == seed 0's deck;
`from_seed('abc')` and `from_seed('1.5')` → `PanicException`. `RustFairAgent.start_game_from_seed`
stringifies its argument, so `start_game_from_seed(None)` → `"None"` and `(1.5)` → `"1.5"` both
reach that panic, uncatchable by `except Exception`. (The sign-stripping itself is *correct* —
CPython's `random_seed()` takes `PyNumber_Absolute`, so `-5` and `5` should and do agree.)

**Against.** Every production seed path is an `int` before it reaches the FFI, so neither branch is
reachable outside a hostile or buggy caller; the empty-string case in particular requires a caller
that already lost its seed. Fixing it is cheap but the severity is contract-hardening, not a live
divergence.

**Fix shape if adopted.** Make the parse fallible (`Result<Vec<u32>, String>`, rejecting an empty
digit string and any non-digit char) and surface it as `PyValueError` from `from_seed` /
`start_game_from_seed` / `deck_descriptions_from_seed`.

### C-d. Peak memory scales linearly with `threads` with no bound — MEDIUM
`rust/carc/carc-core/src/search/mod.rs:266`

**For.** The triple-storage of confirmed finding #2, multiplied: `search_worlds` runs
`min(k, threads)` worlds concurrently, each holding its own `Searcher`/`Tree` for the whole chunk,
so peak RSS is ~8–18 MB × thread count. Nothing in `FairConfig` or the PyO3 constructor bounds it;
`threads` is settable at runtime (`carc-py/src/lib.rs:1269-1276`, rejects only `< 1`) and comes
from a YAML field on the phone (`android_bridge.py:1041`). Raising `rust_threads` 4→8 doubles peak
search memory inside a Chaquopy process.

**Against.** This is finding #2 restated with a multiplier, not an independent defect — the fix is
the same `Rc<str>` change, and once that lands the per-thread figure is small enough that the
scaling is unremarkable. Counted separately it double-counts severity.

### C-e. The repr-keyed legal-move cache served 0 hits in 50,326 lookups yet costs a full key copy per node — MEDIUM
`rust/carc/carc-core/src/search/mod.rs:389`

**For.** `Tree::legal_cache` structurally cannot hit inside a search: its only caller is
`evaluate`, reached only from `expand`, which runs only for a node `create_or_get` just interned
as NEW — the key is fresh by construction. A hit requires a genuine repr collision (the Phase-0.3
rotation family), which is what `legal_cache_collide_check` exists to detect. Measured across 45
searches at 1376 sims over 5 seeds: **0 hits, 50,326 misses.** So it is currently pure cost — one
1.2–5 KB key copy and one `Vec<i32>` per node, ~1/3 of tree memory.

**Against.** It is a deliberate semantics mirror of Python's `Game._legal_cache`, and "0 hits
observed" is exactly the expected reading for a collision guard — measuring zero hits is evidence
it is *working*, not evidence it is dead. Deleting it would change behaviour on a real collision;
the storage complaint is finding #2 again.

**Common ground.** Both sides agree the cache should not pay for a **third copy of the key** —
key it by the same `Rc<str>`/hash handle as `Tree::index`, or by `NodeId`. That keeps the
collision semantics and removes the cost, and is the fix regardless of which reading wins.

### C-f. `possible_playing_positions` re-reads the four neighbour tiles inside the rotation loop — LOW
`rust/carc/carc-core/src/engine/mod.rs:1028`

**For.** `for &(row,col) in &self.open_positions { for turns in 0u8..4 { let top =
self.get_tile(row-1,col); ... } }` — the neighbours are invariant across rotations, so this is 16
bounds-checked board reads per candidate cell where 4 suffice, inside
`possible_actions → legal_mask → legal_actions`, called once per expanded node with
`open_positions` reaching ~30–60 cells late game. Measured `legal_actions`: 1.5–7.2 µs per call,
~1000–1400 calls per search. Purely mechanical hoist, board is not mutated in the loop.

**Against.** No end-to-end A/B was produced; against the 8–13% and 9.4% figures of #3/#4 this is
almost certainly in the noise, and the port's stated rule is not to touch engine code without a
measured win to point at.

### C-g. `search_config_rs()` hard-codes `c_lcb=1.0` and drops `root_select`/`gumbel_*` — MEDIUM
`src/carcassonne_ai/rust_agent.py:137`

**For.** `search_config_rs(cfg, sims)` reads five knobs off `HeuristicPriorConfig` (`c_puct`,
`tau_p`, `value_norm`, `leaf_quantize`, `final_select`) and passes literals for the rest
(`:127-141`, positional args 9–13 = `None, 1.0, True, "glibc_fma", False`). Two are wrong by
construction rather than merely conservative. (1) `c_lcb` is the literal `1.0` **while
`final_select` IS forwarded** — so `HeuristicPriorConfig(final_select="lcb", c_lcb=0.25)` gives
LCB penalty 0.25 in Python and 1.0 in Rust: a silently different move from a config the API
accepts without complaint. The docstring's "`c_lcb` is inert unless `final_select == 'lcb'`" is
true of the *default* and false of the path it describes. (2) `root_select` / `gumbel_m` /
`gumbel_c_visit` / `gumbel_c_scale` / `gumbel_retain_g` have no counterpart in
`carc_core::search::SearchConfig` at all (`grep -n "gumbel\|root_select"
rust/carc/carc-core/src/search/mod.rs` → nothing), so a `root_select="gumbel"` config — a real,
tested Python lever (`heuristic_prior_mcts.py:1097`, `tests/test_heuristic_prior_mcts.py:449-585`)
— silently degrades to plain PUCT. No gate catches either: `trace_search.rs_config` (`:208`)
hard-codes the same `1.0` and its `py_config` (`:180-191`) never sets `c_lcb` or `root_select`, so
both legs sit on the default and the contrast is untested.

**Against.** The Rust backend is documented as a *fair-mode PIMC port*, not a general
`HeuristicPriorConfig` executor; `reuse_tree` is dropped on exactly the same basis and that is
accepted (`trace_search.production_knobs:158-167`). The production spec sets neither `c_lcb` nor
`root_select` away from default, so nothing shippable diverges — the ask is an API-hygiene
raise-don't-ignore change, not a defect.

**Common ground.** Both sides accept `c_lcb=float(cfg.c_lcb)` as free, and a field-parity test
(enumerate `dataclasses.fields(HeuristicPriorConfig)`, require each to be forwarded or explicitly
listed as must-be-default) as the durable fix.

### C-h. `prod_leaf_env` applies the WHOLE production env, not the documented "shape subset" — HIGH
`scripts/rustport/prod_leaf_env.py:42`

**For.** The module's entire stated contract is that it applies leaf SHAPE knobs only, deliberately
NOT dispatch knobs, because "G1–G5 were gated with the dispatch knobs as the scripts found them,
so flipping them here would silently change which implementation a passed gate is evidence about"
(docstring `:17-24`). Line 42 does `import env_preamble`, whose module scope ends with
`RESOLVED = apply()`, which `setdefault`s **every** key of `PROD_ENV` — including
`CARCASSONNE_USE_FLAT_LEAF=1`, `CARCASSONNE_USE_CY_REPR=1`, `CUDA_VISIBLE_DEVICES=""`,
`OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`. The `SHAPE_KEYS` loop is then a pure no-op. Measured:

```
$ env -u CARCASSONNE_USE_CY_REPR -u CARCASSONNE_USE_FLAT_LEAF -u CUDA_VISIBLE_DEVICES \
      -u OMP_NUM_THREADS .venv/bin/python -c "import prod_leaf_env; ..."
CARCASSONNE_USE_FLAT_LEAF = '1'   CARCASSONNE_USE_CY_REPR = '1'
CUDA_VISIBLE_DEVICES = ''         OMP_NUM_THREADS = '1'      CARCASSONNE_V25_CAP = '8'
```

Every importer (`reconcile_engine.py:58`, `reconcile_leaf.py:80`, `trace_search.py:53`,
`lockstep_fuzz.py:119`, `even_shift_property.py:71`, `property_count_final_scores_order.py:60`,
`p7_make_device_assets.py:49`) therefore runs with the Cython repr and flat leaf **forced on**.
Two harms: G1/G2 are evidence about the Cython implementations only while the docstring tells a
reader otherwise; and importing any of these inside a full-tree pytest silently sets
`CUDA_VISIBLE_DEVICES=""` / `OMP_NUM_THREADS=1` for every later test in the process. The false
claim is already load-bearing — `tests/android/test_bridge_backend.py:22-32` cites it to justify
its directory placement.

**Against.** The dispatch knobs it force-sets are *the production values*, and every gate was in
fact run under them, so no gate artifact is mis-attributed in practice — the defect is a stale
docstring, not wrong evidence. Fixing it by *removing* the import would change what the gates run
under and invalidate the passing runs; the correct action is to fix the prose, which drops this
to low.

**Common ground.** Both sides agree the docstring and `tests/android/test_bridge_backend.py:22-32`
must be corrected to state what G1–G5 are actually evidence about (Cython repr + flat leaf). They
differ only on whether the code should change too.

### C-i. Bridge `apply()` advances Python before the mirror with no rollback, and the Rust chooser never re-checks sync — MEDIUM
`android/app/src/main/python/android_bridge.py:1105`

**For.** `_Session.apply()` mutates `self.board`, `self.last_action`, `self.action_log`,
`self.turn` **first**, then calls `self.rs.advance(int(action_id))`, which maps a Rust error to
`PyValueError` (`carc-py/src/lib.rs:1046-1051`). Any FFI failure leaves Python one ply ahead of
the mirror with no rollback — `apply_action` catches at `:1543`, returns error JSON, and **keeps
`_S` live**, so the mirror is permanently stale and nothing detects it: `_assert_mirror` runs at
game start (`:1058`) and per-action only under `_RS_RECONCILE`, a module-level constant read once
at import (`:321`) that defaults off on the phone. The chooser never checks either —
`self.pick = lambda board: int(self.rs.choose_action())` (`:1067`) ignores its `board` argument
entirely. Contrast: `RustFairAgent.choose_action` was deliberately changed on 2026-08-01 to
hard-assert sync on *every* decision, unconditionally, on the argument that 12.8 µs against a
266 ms decision leaves "no budget argument for leaving a correctness guard off"
(`rust_agent.py:319-334`). The one surface a human plays against does not have that guard.

**Against.** This is the stale-mirror silent-wrong class the BACKEND_BYPASS_AUDIT already names
and excludes from re-reporting; the mechanism differs (failure-atomicity vs. callers that never
call `advance`) but the failure mode, the detection gap and the fix are the same, so it is a
refinement of a known item rather than a new finding.

**Common ground.** Advance the mirror first (or snapshot/restore `board`/`action_log`/`turn`), and
degrade to Python on any mirror exception rather than continuing.

### C-j. Bridge's Rust mirror hard-codes three champion knobs the Python anchor reads from the spec — LOW
`android/app/src/main/python/android_bridge.py:1047`

**For.** `_start_rust_mirror` builds `FairAgentRs` with `min_pooled_visits=2.0,
exact_endgame=True, exact_max_k=2` as literals — three lines above the `spec_knob()` calls whose
own docstring says *"no strength number is ever hardcoded here — DESIGN CONTRACT 3"* (`:1074-1076`).
The Python anchor in the same session gets these from the spec (`champion_factory.py:813`
`exact_max_k=spec.exact_max_k`; `fair_agent.py:105,107`). Latent today because the values
coincide; live the moment either moves — and `restore_game` compounds it, computing `latched` from
the **Python** agent's `_exact_max_k` (`:1856-1868`) and seating that answer into the Rust agent
via `s.rs.set_latched(latched)` (`:1917`), so a divergence produces a restored game that plays a
different champion than the live one did.

**Against.** Exactly the "bridge preset/provenance" class the BACKEND_BYPASS_AUDIT already
covers, and the values are pinned equal by tests today; low value against the noise of
re-reporting a known category.

---

## WHAT THE GATES ALREADY COVER / NON-FINDINGS — do not re-litigate

**G0–G7 (all PASSED, `docs/RUSTPORT_BUILD_SPEC_2026-07-31.md`) establish that the Rust port
reproduces the Python engine bit-exactly over the whole game record** — tile deal, board repr,
leaf eval, legal-move generation, search node identity, chosen action, and the full-game lockstep
fuzz. **No finding in this review disputes any of that, and none should be read as a
bit-exactness risk.** Every confirmed finding above is one of exactly three kinds the gates cannot
see by construction: (i) **cost, not output** — #2/#3/#4 change memory and wall clock while
leaving every byte of every artifact identical, so an identity gate is definitionally blind
(the digest is dead output; the repr rewrite is byte-verified equal); (ii) **the binary's
provenance rather than its behaviour** — #1/#9/#10/#8 concern which compiler and which flags
produced the `.so` that ships to the phone and whether that is recorded, and no gate builds or
fingerprints the Android wheel at all; (iii) **the gate machinery and the config plumbing around
it** — #6 is a gate that reports PASS on empty evidence, #5 is a factory guard that reads the raw
kwarg where the manifest reads the resolved env, #7 is an FFI parameter range nothing fuzzes.

Also already known and **deliberately excluded from this review**, per
`measurement/rustport_p6/BACKEND_BYPASS_AUDIT_20260801.md`: the stale-mirror silent-wrong class,
bridge preset-leaf provenance, and the thin-builder backend gaps (the desktop callers that reach
the agent without a `backend` parameter and so keep running full Python). C-i and C-j above touch
that territory and are filed as *contested* precisely because one skeptic reads them as
refinements of those known items rather than as new findings — they are logged for the mechanism
detail, not as fresh discoveries.

Finally, two things that look like defects and are not: the sign-stripping in
`seed_words_from_decimal` is **correct** (CPython's `random_seed()` applies `PyNumber_Absolute`,
so `-5` and `5` must agree, and they do), and `search_config_rs` dropping `reuse_tree` is
**documented and defensible** (`trace_search.production_knobs:158-167` explains it is a no-op in
fair deploy) — only `c_lcb` and `root_select` carry no such justification, which is why C-g is
scoped to those two.
