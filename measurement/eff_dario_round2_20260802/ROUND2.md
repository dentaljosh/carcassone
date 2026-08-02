# EFF DARIO ROUND 2 — 2026-08-02 (tie-breaks · flip review · governance sweep)

> **Status: ✅ COMPLETE 2026-08-02. READ-ONLY — no code, doc, or governance file was changed by
> this round.** This file is the record of three things: (§1) FINAL verdicts on the ten CONTESTED
> items of [the 2026-08-02 rust-port review](../rustport_review_20260802/REVIEW.md), (§2) the
> confirmed findings of the flip-review pass over the 2026-08-01 backend/budget flips and the
> Android wheel toolchain, and (§3) a governance-correction checklist for the docs the flips left
> behind.
>
> §1 verdicts are **FINAL** — they are the tie-break, not a third opinion. Do not re-litigate a
> CONFIRM/REFUTE below from the REVIEW.md "For/Against" text; that text is now history.

---

## §1 — TIE-BREAK VERDICTS ON THE TEN CONTESTED ITEMS (FINAL)

REVIEW.md §CONTESTED held ten items that one of two skeptics refuted. All ten were re-adjudicated
against the code and the built wheel in this checkout.

**Result: 8 CONFIRM, 2 REFUTE.**

**Now CONFIRM — these move out of CONTESTED and stand alongside REVIEW.md's numbered confirmed
findings: C-a, C-b, C-c, C-e, C-g, C-h, C-i, C-j.**
**REFUTED and closed: C-d, C-f.**

| # | Item | Severity (as filed) | Verdict |
|---|---|---|---|
| C-a | Rust panics cross the FFI as `PanicException` (a `BaseException`), so every production `except Exception` is blind to them | HIGH | **CONFIRM** |
| C-b | `Game::advance` applies any *decodable* action without checking legality; `set_tile` writes with an unchecked cast | HIGH | **CONFIRM** |
| C-c | Seed parsing accepts empty/whitespace as seed 0 and panics on non-decimal input where Python raises `ValueError` | MEDIUM | **CONFIRM** |
| C-d | Peak memory scales linearly with `threads` with no bound | MEDIUM | **REFUTE** |
| C-e | The repr-keyed legal-move cache served 0 hits in 50,326 lookups yet costs a full key copy per node | MEDIUM | **CONFIRM** |
| C-f | `possible_playing_positions` re-reads the four neighbour tiles inside the rotation loop | LOW | **REFUTE** |
| C-g | `search_config_rs()` hard-codes `c_lcb=1.0` and drops `root_select`/`gumbel_*` | MEDIUM | **CONFIRM** |
| C-h | `prod_leaf_env` applies the WHOLE production env, not the documented "shape subset" | HIGH | **CONFIRM** |
| C-i | Bridge `apply()` advances Python before the mirror with no rollback, and the Rust chooser never re-checks sync | MEDIUM | **CONFIRM** |
| C-j | Bridge's Rust mirror hard-codes three champion knobs the Python anchor reads from the spec | LOW | **CONFIRM** |

### The reasoning, one item at a time

**C-a — CONFIRM.** Verified empirically against the installed wheel:
`carc_rs.MirrorState.from_seed('abc')` raises `PanicException` whose MRO is
`[PanicException, BaseException, object]`, and `android_bridge.py` contains 22 `except Exception`
handlers and zero `except BaseException` — including `_start_rust_mirror`'s degrade net and every
JNI entry point documented as "never raise across JNI". The "unreachable path" rebuttal fails on
its own terms: a panic was reached through two public FFI entry points in this checkout (C-b's
`advance`, C-c's `from_seed`), and a safety net whose stated job is to keep the app playable when
the Rust core misbehaves cannot be excused by an audit of currently-known failures.

**C-b — CONFIRM.** Both halves were read and executed. `decode` (`action_space.rs:150-170`)
rejects only `idx < 0 || idx >= action_size`, never the legal mask; `set_tile`
(`engine/mod.rs:383-385`) is the sole board accessor with no bounds handling, while `get_tile`
guards and `board_direct` reproduces CPython's wrap via `py_index`.
`MirrorState.from_seed('12345').advance(0)` panics with *"len is 1225 but the index is
18446744073709551409"* where the Python `Game.get_next_state(board, 0)` succeeds and places the
tile at (29,3). That measured divergence is a real behavioural split, not a shared error contract —
and the same cast's `row>=0, col>=BOARD_COLS` case is strictly worse: an in-range write to the
wrong cell with no error at all, which no caller-contract argument makes acceptable.

**C-c — CONFIRM.** `seed_words_from_decimal` (`mt19937.rs:259-284`) uses
`.expect("seed must be a decimal integer")` per char, and its `if limbs.is_empty() { push(0) }`
fallback swallows an empty digit string. Measured here: `from_seed('')`, `from_seed('  ')` and
`from_seed('-0')` all produce byte-identical state and decks to `from_seed('0')`, while `'abc'`
and `'1.5'` raise `PanicException`. The reachability rebuttal is undercut by
`RustFairAgent.start_game_from_seed(deck_seed: int | str)` doing `str(deck_seed)` at
`rust_agent.py:277` — a string seed is an advertised input, so a lost or blank seed silently plays
the seed-0 deck inside a module whose entire contract is CPython bit-exact emulation.

**C-d — REFUTE.** `search_worlds` (`fair/mod.rs:400-433`) does hold `min(k, threads)` live
`Searcher`/`Tree` instances via `thread::scope`, but that is the correct and expected footprint of
a scoped parallel search: no leak, no unbounded growth in time, and the bound is exactly the
operator-set `threads`. Every ounce of severity here comes from the per-tree size, which is
**confirmed finding #2 (triple key storage)** and carries the identical fix. Counting the
multiplier as an independent defect double-books the same problem.

**C-e — CONFIRM.** The only path into `legal_actions` (`search/mod.rs:389`) is
`expand` → `evaluate`; `expand` returns early on `self.tree.get(id).expanded`, and every node
interned by `create_or_get` is expanded immediately at its interning site (`simulate:659`,
`search:695`), so a key can never be evaluated twice and the cache is *structurally* incapable of
hitting. That also kills the "zero hits proves the collision guard works" rebuttal: on a genuine
repr collision `create_or_get` returns the already-expanded node and `expand` short-circuits
*before* the cache is consulted, so the guard (and its `legal_cache_collide_check`) is dead code
paying a `key.to_string().into_boxed_str()` per node.

**C-f — REFUTE.** The source-level redundancy is real (`engine/mod.rs:1023-1032`, `&self` with no
mutation in the loop), but this is the textbook LICM case — four loop-invariant loads reached
through a `noalias readonly` `&self` inside a constant `0..4` loop — so the claimed 4× read count
very likely does not survive `--release`, and no end-to-end A/B was produced to show otherwise.
Even taking the quoted per-call numbers at face value, `legal_actions` is ~3% of a k8×1376
decision and only part of that is neighbour reads, so the ceiling is ~1% against the port's
explicit rule of no engine edits without a measured win.

**C-g — CONFIRM.** `search_config_rs` (`rust_agent.py:126-141`) forwards `final_select` from the
config but passes positional literals `None, 1.0, True, "glibc_fma", False`, while
`SearchConfigRs` accepts `c_lcb` (`carc-py/src/lib.rs:771,787`) and `carc_core::search` genuinely
uses it (`search/mod.rs:884`). So `HeuristicPriorConfig(final_select="lcb", c_lcb=0.25)` is
silently executed at 1.0 by Rust and 0.25 by Python — a different move from an input the API
accepts. `root_select`/`gumbel_*` are real validated Python levers
(`heuristic_prior_mcts.py:175-195, 1051`) with no counterpart anywhere in the Rust search, and
silently degrading them to PUCT rather than raising is not the same posture as the documented,
justified `reuse_tree` drop.

**C-h — CONFIRM.** Confirmed by reading both files: `prod_leaf_env.py:42` does a module-scope
`import env_preamble`, and `scripts/human_anchor/env_preamble.py` ends with `RESOLVED = apply()`,
which `setdefault`s every `PROD_ENV` key including `CARCASSONNE_USE_FLAT_LEAF`,
`CARCASSONNE_USE_CY_REPR`, `CUDA_VISIBLE_DEVICES=""`, `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1`.
The `SHAPE_KEYS` loop is therefore a no-op and the docstring's central claim ("applies the SHAPE
subset only… flipping them here would silently change which implementation a passed gate is
evidence about") is exactly inverted. The "harmless because those are the production values"
rebuttal does not touch the two live harms: G1/G2 are evidence about the Cython/flat
implementations while seven importers' docs say otherwise, and importing any of them under a
full-tree pytest mutates process-global CUDA/OMP settings for every later test.

**C-i — CONFIRM.** `_Session.apply` (`android_bridge.py:1160-1174`) mutates `board`, `action_log`
and `turn` before calling `self.rs.advance(...)` with no rollback; `_assert_mirror` runs per-ply
only under `_RS_RECONCILE` (a module constant read once at `:361`, default off on the phone); and
`self.pick = lambda board: int(self.rs.choose_action())` (`:1131`) discards its board argument — so
an FFI failure leaves a permanently stale mirror that keeps playing. This is not a restatement of
the audit's known item: that one is about desktop callers who never call `advance`, whereas this is
failure-atomicity plus a missing guard on the one surface a human plays. `RustFairAgent.choose_action`
was deliberately given exactly that unconditional `check_sync` on 2026-08-01 at 0.005% cost
(`rust_agent.py:319-334`).

**C-j — CONFIRM.** `_start_rust_mirror` passes `min_pooled_visits=2.0, exact_endgame=True,
exact_max_k=2` as literals (`android_bridge.py:1102`) roughly thirty lines above `spec_knob`'s
"no strength number is ever hardcoded here — DESIGN CONTRACT 3", while the Python side sources
them from `champion_factory` (`:813 exact_max_k=spec.exact_max_k`) and `fair_agent.EXACT_MAX_K` /
`DEFAULT_MIN_POOLED_VISITS`. The audit's A9 covered the *leaf* preset of this same hand-built
construction and that half was fixed; the knob half is the live residue. `restore_game` compounds
it by computing `latched` from the Python agent's `_exact_max_k` (`:1945-1961`) and seating that
answer into the Rust agent via `set_latched` (`:2004`), so any future divergence yields a restored
game playing a different champion than the live one.

### Standing total after the tie-break

REVIEW.md's §CONFIRMED items **#1–#10** plus the eight upheld here = **18 standing findings**
against the Rust port, with **C-d and C-f closed**. Bit-exactness remains undisputed: every item
in both sets is provenance, safety-net, label-vs-function or performance — none of them changes a
bit of gate output, which is precisely why seven green gates are silent about them.

---

## §2 — FLIP REVIEW: CONFIRMED FINDINGS, RANKED

Scope: the 2026-08-01 backend flip (`champion.fair_deploy.backend: rust`) and mobile budget unpin
(k4×688 → k8×1376), plus the Android wheel toolchain that ships the binary those flips depend on.
**Not clean — 12 confirmed findings** (14 filed; two pairs were duplicate reports of the same
defect and are merged below). None was refuted.

### HIGH

**F-1. The `backend="rust"` incompatibility guard inspects kwargs only, so env-enabled search
variants pass through and the manifest then mislabels the agent.**
`src/carcassonne_ai/champion_factory.py:795`. `if backend == "rust" and (meeple_dedup or
intra_reuse or parallel_workers)` reads the raw kwargs, but the manifest-stamping code 60 lines
later resolves the same features through the ENV-backed globals: `meeple_equiv.resolve(meeple_dedup)`
(`:857`) and `intra_carry.resolve(intra_reuse)` (`:872`) both return the module global when the
kwarg is `None`, and those globals are `MEEPLE_DEDUP = _env_flag()` (`meeple_equiv.py:72`) /
`INTRA_TURN_REUSE = _env_flag()` (`intra_reuse.py:70`). With `CARCASSONNE_MEEPLE_DEDUP=1` (or
`CARCASSONNE_INTRA_TURN_REUSE=1`) and `backend='rust'`, the guard does not fire, `RustFairAgent`
never receives the variant (it has no such parameter, `rust_agent.py:197-203`), yet the manifest is
stamped `meeple_dedup: {enabled: True, …, note: "NON-CHAMPION search variant"}`. The log says a
non-champion variant played when the champion actually played — or, read the other way, a caller
who believed they were A/B-testing a variant got the baseline. Second instance of the same class:
`parallel_workers=0` is falsy so it also slips the guard, and `:914` then stamps a spawn-split
block onto a Rust agent that has no spawn pool.
⚠️ **This independently re-confirms REVIEW.md confirmed finding #5** — two separate passes reached
it by different routes.

**F-2. A game resumed after the backend resolves differently is silently re-budgeted, and the
archive records only the final budget.** `android/app/src/main/python/android_bridge.py:1940`.
`_save_payload` (`:1726-1745`) carries no `backend` and no effective budget (only `req_sims`/
`req_k_dets`, both null for `Difficulty.CHAMPION`), and `restore_game` deliberately re-resolves
from `BACKEND_DEFAULT` when `_S is None` — i.e. on every Resume after an app restart. Since the
2026-08-01 unpin the budget is *conditional on that resolution*, so the same saved game continues at
a different sims/move than it was played at, and `archive_record` (`:1793-1803`) stamps a single
`sims_effective`/`k_dets_effective`/`backend`/`budget_note` describing only the post-restore
session. `_start_rust_mirror`'s catch-all `except Exception` (`:1122`) degrades on ANY mirror
failure, so "played at 11008, resumed at 2752" needs no code change to occur.
`measurement/e4_games/README.md` grades E4 games off exactly those fields. Pre-flip this was
impossible: the mobile profile was pinned unconditionally, so a restore always reproduced the
played budget.

**F-3. `LINK_SIGNATURE` salt covers only the page-align flag — the Cython compiler that actually
generates the shipped `.c` is still invisible to the version.**
`android/tools/build_cy_wheels.py:125`. `LINK_SIGNATURE = C.PAGE_ALIGN_LDFLAG.encode()` is the ONLY
non-source byte mixed into `content_version(..., extra=...)`. The `.so` bytes are determined by the
Cython version that emits the `.c` (`:163-178`), the compile line (`:202-213`, `-O3 -DNDEBUG`,
`--target={triple}{ANDROID_API}`), and `build_config.TARGET_ARTIFACT_VERSION`/`ANDROID_API` (which
pick the Android `Python.h` + `libpython3.12.so`). None enter the hash. Measured on this box:
`local.properties` has no `chaquopy.buildPython`, so buildPython is `/usr/bin/python3.12`, which has
no `cython` module; `find_cython()` (`:141-157`) falls through to `.venv/bin/python -m cython` =
Cython 3.2.5, a machine-local interpreter Gradle knows nothing about. `--print-version` yields
`1.16720.45215`, matching both shipped wheels and the install tree — so `pip install -U Cython`
changes the shipped `.so` with a byte-identical requirement string. Worse, `find_cython()` prefers
`sys.executable`: installing Cython into `/usr/bin/python3.12` silently switches code generators
with no version movement. The declared rule (`_chaquopy_common.py:287`, "A build input that changes
the artefact must change the version") is not met.

**F-4. Gradle wheel tasks declare the per-toolchain script as their only script input — the P7
refactor moved half the build into `_chaquopy_common.py` and the input sets were never widened.**
`android/app/build.gradle.kts:133`. `BuildCyWheels` declares `script` = `build_cy_wheels.py` and
`pyx` = the two `.pyx`; `BuildRustWheels` declares `script` = `build_rust_wheels.py` and `sources`
= the rust crate tree. `android/tools/_chaquopy_common.py` — which owns `MAX_PAGE_SIZE`,
`PAGE_ALIGN_LDFLAG`, `TARGET_ARTIFACT_VERSION`, `ANDROID_API`, `ensure_target`, the ELF gate and
`write_wheel` — is an input to *neither*, and `android/native/carc-cy/build_config.py` is an input
to neither. Neither task has `outputs.upToDateWhen { false }` (contrast `syncPythonFromRepo:81`,
`checkTileAssets:307`). Concrete stale-wheel path, strictly worse than F-3: bump `MAX_PAGE_SIZE` to
65536 in `_chaquopy_common.py` and cy's version moves (via `LINK_SIGNATURE`) so `buildCyWheels`
reruns — but nothing in `buildRustWheels`'s input set changed, so Gradle marks it UP-TO-DATE, cargo
is never invoked, and the APK ships a cy wheel at the new alignment beside a rust wheel at the old
one. Fixing the rust version hash alone does not close this; the task would still be skipped. Same
class, second instance: `cyPyxSources` (`:100`) hardcodes `listOf("flat_leaf_cy", "flat_repr_cy")`
rather than asking the script, duplicating `build_config.MODULES`.

### MEDIUM

**F-5. `resolved_manifest` has no backend whitelist, so a typo'd YAML value stamps a fictional
engine name — the failure b58930f said it was closing.**
`src/carcassonne_ai/champion_factory.py:409`. `make_production_champion` validates the resolved
value (`:765`), but `resolved_manifest` — the public entry point b58930f hardened — validates
nothing, and `load_production_spec` accepts any string (`:156`). With a mistyped
`fair_deploy.backend: rustt`, `resolved_manifest("fair", backend="auto")` resolves to `"rustt"`,
skips the Rust panel re-verification (`:345` branches only on `== "rust"`), then takes the
`if backend != "python"` branch at `:471` and stamps `manifest["backend"]["name"] = "rustt"` with
boilerplate claiming G4/G6 behaviour identity and a re-verified leaf — precisely what the commit
message rejects ("a manifest naming a fictional backend is worse than either real answer"). The
same unvalidated string reaches `ProductionSpec.backend` for every consumer.

**F-6. `production_budget()` — the only budget the Home/Settings UI prints — is backend-blind, so
the UI advertises 11008 sims/move on a device running the 2752 floor.**
`android_bridge.py:2339`. It calls `mobile_budget(spec)` directly and never consults the backend,
even though `mobile_budget`'s own docstring (`:402-425`) warns "a caller that takes total_sims from
here and ignores backend reintroduces exactly the hang the carve-out existed to prevent" and names
`budget_for_backend()` as "the ONE place that resolves the pair". Reproduced: `production_budget()`
→ `{'sims_per_det': 1376, 'k_dets': 8, 'total_sims': 11008}` while `new_game({'backend':'python'})`
in the same process yields `eff_k_dets=4, eff_sims=688`; `budget_for_backend('python')` correctly
returns `{'k_dets':4,'sims_per_det':688,'floored':True}`. `HomeScreen.kt:50-51` and
`SettingsScreen.kt:168` print this straight, `GameViewModel.kt:312` loads it at warm-up, and the
truthful `budget_note` only reaches `GameScreen.kt:1143` after the game starts. The flip-era tests
assert the coupling only at helper level (`test_bridge.py:212`) and session level
(`test_bridge_backend.py:181`), never on the reported budget — `test_bridge.py:205-206` and
`BridgeFlipDeviceTest.kt:84-90` assert it equals the champion of record unconditionally.
*(Merged: two independent reports of this same defect.)*

**F-7. An explicitly requested `backend:"python"` produces a false "no Rust core on this device"
claim in `budget_note` and `opponent_name` — and both are archived into the permanent E4 record.**
`android_bridge.py:964`. `budget_for_backend` sets `floored=True` whenever the session backend is
python and the profile's is rust; it cannot distinguish "the wheel is missing" from "the caller
asked for python". `_build_opponent` keys the note purely on `mob['floored']` and asserts a
hardware fact. Reproduced on this box with the wheel importable:
`new_game({'seed':5,'opponent':'champion','backend':'python','verify':False})` →
`budget_note = "REDUCED — no Rust core on this device…"`, `opponent_name = "Champion(reduced
k4x688)"`, `rs_note = None` (so nothing corrects it); `archive_record:1792` persists it. The
module documents this path as live (`BACKEND_DEFAULT`'s comment: "a test harness pins python that
way"). No test exercises the branch: `test_bridge_backend.py:75` uses `opponent: tier1` (returns
before the note branches) and the two python-pinned tests in `test_bridge.py` (`:380`, `:444`) pass
`**TINY`, which takes the first branch instead. Only the simulated-ImportError test reaches it.
*(Merged: filed separately as a defect and as a test-coverage gap; same branch, same fix.)*

**F-8. The session manifest never records that `carc_rs` played — `get_manifest()` returns a
byte-identical pure-Python manifest under the rust default.** `android_bridge.py:931`.
`_build_opponent` builds the anchor with `backend=BACKEND_PYTHON` and takes `self.manifest` from it
(`:943`); `champion_factory` stamps the `backend` block "ONLY when it is not the python default"
(`champion_factory.py:466-470`), so the manifest the phone carries has no backend key even when
`self.rs` is the move chooser. Reproduced: `new_game({'backend':'rust',…})` →
`st['backend'] == 'rust'`, `_S.rs is not None`, yet `get_manifest()['manifest']` has no `backend`
key. `get_manifest()`'s docstring says it is "the manifest of the agent that is ACTUALLY playing",
and champion_factory's rationale for the block is "a log records which engine played". The bridge
added `backend` to `archive_record` for exactly that reason (2ca65c0) but left the Settings
"resolved AI manifest" sheet asserting Python. (The budget half is fine —
`runtime_budget_override` is stamped correctly.)

**F-9. `elf_info` reads the FOLLOWING program header's Align for every LOAD segment, and the 16 KiB
gate takes `max()` instead of `min()`.** `android/tools/_chaquopy_common.py:204`. The parse loop
(`:204-214`) joins each `LOAD` row with `lines[i+1]` and scans `reversed(tail)` for the first `0x`
token — which is the last hex token of the *next* header, i.e. the next segment's Align. So the
first LOAD's alignment is never sampled and the last LOAD's entry is whatever header follows it.
`assert_links_libpython` (`:259`) then compares `max(aligns)` against `MAX_PAGE_SIZE`, so a single
16 KiB LOAD masks any 4 KiB sibling — it should be a `min` over LOAD rows, since one under-aligned
LOAD breaks `dlopen` on a 16 KiB-page device. Measured against the shipped
`carc_cy/flat_leaf_cy.so` with the repo's own NDK `llvm-readelf`: parsed aligns =
`['0x4000','0x4000','0x4000','0x8']`, where the real headers are four LOADs all at 0x4000 followed
by `DYNAMIC … RW 0x8` — the 4th entry is DYNAMIC's align and LOAD#1's never entered the list.
`load_align_max` returns 0x4000 only because `max()` discards the 0x8. This is the sole automated
check behind the flip-era 16 KiB fix, and it is the function that produced that commit's evidence.

**F-10. `cargo_env` prepends ambient `RUSTFLAGS` into the Android device build — non-hermetic
codegen input, invisible to the version hash and to every gate.**
`android/tools/build_rust_wheels.py:171`. `env = dict(os.environ)` (`:132`) then
`env["RUSTFLAGS"] = f"{prev} {rustflags}"` (`:171-172`). Any `RUSTFLAGS` in the launching shell (a
dev profile export, a CI wrapper) is silently prepended to the cross-compile of the phone binary;
`-C target-feature=…`, `-C opt-level=`, `-C codegen-units=` all change the emitted object, and none
appear in `source_version()` (which hashes only `rust/carc`), in any Gradle input, in any provenance
record, or in `assert_links_libpython`. This is adjacent to REVIEW.md #1 but a separate uncovered
input: pinning `RUSTUP_TOOLCHAIN` does nothing about it. Note also that cargo prefers
`CARGO_ENCODED_RUSTFLAGS` over `RUSTFLAGS`, so an ambient `CARGO_ENCODED_RUSTFLAGS` would discard
the script's `-L{libdir} -lpython3.12 -Wl,-soname -Wl,-z,max-page-size` link args entirely — that
half at least fails loudly at the DT_NEEDED assertion (`:195`); the additive case does not. The
omission is inconsistent rather than deliberate: `:156` already sanitises `PYO3_CROSS_LIB_DIR`, and
`[profile.release]` in `rust/carc/Cargo.toml` pins codegen explicitly "so the two Rust crates are
built with the same codegen settings" — inherited `RUSTFLAGS` overrides that intent without moving
the wheel version.

### LOW

**F-11. `assert_links_libpython`'s docstring still tells readers the shipped cy wheel is 4 KiB
aligned, and `build_cy_wheels`' VERSION section still states the pre-salt rule.**
`_chaquopy_common.py:239`. After fa51344 no caller passes `require_page_align=False` (both
`build_cy_wheels.py:218` and `build_rust_wheels.py:195` pass `True`), yet `:239-242` still reads
"`require_page_align=False` downgrades this one to a warning, which is what the pre-existing cy
wheel needs: it is 4 KiB-aligned today". Same file, same class: `build_cy_wheels.py:52-54`
("`--version` is content-addressed from the .pyx bytes") contradicts `:121-135` eighty lines below,
which is the whole point of the commit. These are the two places someone greps when deciding
whether a new flag needs the salt. Both statements were correct before fa51344 and were not updated
by it.

**F-12. `test_runtime_info_reports_rust` asserts the API against the constant the API returns.**
`tests/android/test_bridge_backend.py:256`. `assert info["rust"]["tanh_flavor"] ==
B.ANDROID_TANH_FLAVOR` compares `runtime_info()`'s output to the module constant that
`runtime_info()` literally interpolates (`android_bridge.py:2410`), so it cannot fail regardless of
what the Rust core is configured with. The behavioural claim that matters — that the flavour
reaching `carc_rs.SearchConfigRs` (`android_bridge.py:1100`) is the msun flavour G7 measured — is
asserted nowhere in the desktop suite. Same shape as the A9 label-not-function pattern the flip
fixed for the leaf config.

---

## §3 — GOVERNANCE CORRECTIONS (ACTIONABLE CHECKLIST)

**Not clean — 26 corrections.** Root cause is uniform: the 2026-08-01 backend + mobile-budget flips
changed `governance/PRODUCTION.yaml` twice and **touch 4 of the six-touch close-out (governance row
flip) was skipped entirely**, while touches 5/6 (STATUS, roadmap) were done in body text but not in
headers. Everything below is a doc/registry edit; no measurement is owed and no number moves.

Do them in this order — the first five are the ones a fresh thread would act on wrongly.

### CRITICAL

- [ ] **G-1. `governance/CHECKPOINT_LINEAGE.csv:18` — champion row still asserts the mobile
      carve-out is OPEN.** The only governance-spine row describing the deployed champion still
      reads "the Android app is PINNED at the pre-promotion k4x688 … E4 phone games must be graded
      against k4x688". Contradicted by `PRODUCTION.yaml:217-224`, `STATUS.md:7`,
      `DECISIONS.md:3535`. Replace the `*** MOBILE CARVE-OUT:` sentence group with: carve-out
      **CLOSED 2026-08-01**; the app was pinned 2026-07-29 → 2026-08-01, when the rustport (G4
      bit-exact / G6 14,384/14,384 / G7 1.551 s/move on the Pixel) allowed
      `deploy_profiles.mobile` → k8×1376 = 11008 with `backend: rust`, `rust_threads: 4`; the phone
      now plays THIS row's champion; behaviour identity transfers strength (CL-071 precedent) and
      **no new strength claim is owed**; **grading epoch** — archives BEFORE the 2026-08-01 build
      grade against k4×688 and carry `runtime_budget_override`, archives from that build onward are
      full-strength and the ABSENCE of `runtime_budget_override` is the marker (they also carry
      `start_rule: retail` and `grid_rule: centered18`). Extend the trailing citation to
      "… roadmap G6; backend+budget execution flips DECISIONS 2026-08-01 (evening), roadmap F8."

### HIGH

- [ ] **G-2. `governance/CLAIM_REGISTRY.csv:72` — CL-071's MOBILE CARVE-OUT block is factually
      false; its own pre-registered unpin experiment fired.** Append to the `claim` field an
      `[AMENDMENT 2026-08-01: THE CARVE-OUT IS CLOSED …]` block recording that rustport P7/G7 met
      this row's own unpin condition *literally* (native Rust core, 4 OS threads in one
      GIL-released call, 1.551 s/move median at 11008 on a Pixel 9 Pro, thermal 1.007×); that the
      ~50-elo on-device deficit is gone with no new strength claim (G6 14,384/14,384 actions, G7
      leg 2 0/3,165 plies); that **E4 grading changed** at the 2026-08-01 build boundary; and that
      the budget is conditional on the backend (11008 on the Python path is ~25 s/move on-device —
      `budget_for_backend()` degrades engine AND budget together). Then: move the
      `MOBILE UNPIN EXPERIMENT` clause in `falsifier_or_decision_experiment` to
      "**FIRED AND SATISFIED 2026-08-01** (rustport G7, 1.551 s/move at 11008 ≤ the 3 s bar)";
      set `last_updated` to 2026-08-01; append to `evidence_files_or_run_ids`:
      `DECISIONS.md 2026-08-01 (evening); measurement/rustport_p7/G7_REPORT.md;
      measurement/rustport_p7/device/flip/; measurement/rustport_p6/G6_backend_g6_k8x1376.json;
      governance/PRODUCTION.yaml (mobile unpin 2026-08-01)`.
- [ ] **G-3. `docs/PROGRAM_ROADMAP_2026-07-07.md:92` — F8 header still reads 🔨 BUILDING** while
      the same line says "THE PORT IS COMPLETE — ALL SEVEN GATES GREEN" and "✅ BOTH FLIPS LANDED".
      Every other concluded item carries a ✅/⛔ header verdict; F8 is the outlier. Change the
      header to `✅ COMPLETE 2026-08-01: ALL SEVEN GATES GREEN in ~38 h (G0 2026-07-31 → G6
      2026-08-01 05:26; G7 on the real Pixel), BOTH FLIPS LANDED 2026-08-01 evening` and append
      `⏭️ RESIDUAL: caller conversion (play_harness / play_vs_tier1_gui / kparallel_latency_bench +
      the thin build_fair_champion builders) and the 2026-08-02 review fix routing.` Leave the
      P0–P7 body unchanged — it is already fully stamped.
- [ ] **G-4. `STATUS.md:7` — the top blocks carry nothing from 2026-08-02.** Five committed
      deliverables are invisible to a fresh thread. Insert one new dated block above line 7
      ("📚 2026-08-02 — …") naming: the rules-fidelity audit (971bd3c,
      `docs/RULES_FIDELITY_AUDIT_20260802.md` — dossier, no rules changed); the Phase-5 analyzer
      first slice (b4b1e9f, `measurement/analyzer_20260802/ANALYZER_REPORT.md` — tooling + report,
      no strength claim); the P1 paper skeleton (01d0e2b,
      `docs/papers/p1_prediction_vs_discrimination/` — draft, publication is Joshua's call); the
      93-agent rust-port review (88136d1, `measurement/rustport_review_20260802/REVIEW.md` —
      read-only, fixes not applied); the post-flip agreement re-check (06d02a0, 1435/1435 actions,
      0 mismatches); and the G6 gate-artifact tracking (4c16a55). State explicitly that
      `PRODUCTION.yaml` and `results.csv` were untouched.
- [ ] **G-5. `docs/PROGRAM_ROADMAP_2026-07-07.md:87` — F7 still blames the capoff n=384 acceptance
      on contention.** That is the pre-correction post-mortem the DECISIONS entry explicitly
      superseded. Replace "(5 at n=400; capoff n=384-accepted after a cross-workload contention
      loop …)" with the corrected version: the 16 missing games crash **deterministically** with
      `action_space.WindowOverflowError` (25×25 centroid window vs the grid wall), a
      **candidate-correlated** exclusion and a **new invisible-border face feeding F9**; worst-case
      bound ±14 elo, the NULL survives; cross-workload contention was a co-factor that stretched
      each crash cycle, not the cause.
- [ ] **G-6. `BACKLOG.md:29` — the launcher-hardening entry carries the superseded
      contention/timeout mechanism.** It is the durable spec for the fix and it describes a failure
      mode measured to be wrong: the games were not pushed past the 3600 s abandon-wall by load —
      the worker raised `WindowOverflowError`, the pool died recordless, and the launcher relaunched
      into the identical deterministic crash (CRN decks). This changes the fix: a wall-clock or
      load-aware guard would not have caught it; only a **no-progress abort** would. Rewrite lines
      28-31 to name the deterministic crash as the root cause (~5 h of relaunches, worker raised
      ~40–60 min in) and demote contention to "only STRETCHED each crash cycle (~11 min → 40–65
      min) and made it look like a timeout problem — the operator-side lesson, not the root cause".
      Keep the existing DECISIONS citation and the Hardening/Addendum paragraphs.

### MEDIUM

- [ ] **G-7. `DECISIONS.md:3563` — the Touches footer says "NOT touched: claim registry", but the
      entry changes facts CL-071 asserts.** Correct for `results.csv`; wrong for the registry (the
      entry closes CL-071's own pre-registered unpin experiment, inverts its E4 grading rule, and
      records a new champion field with no claim row anywhere). After applying G-2, change the
      footer to `**Touches:** … · governance/CLAIM_REGISTRY.csv (CL-071 amended: mobile carve-out
      CLOSED, unpin experiment FIRED, E4 grading rule updated, backend of record recorded).
      **NOT touched:** results.csv, CHECKPOINT_LINEAGE.csv (no elo moves; the Rust core is
      behaviour-identical by gate).`
- [ ] **G-8. No governance row records the Rust backend as the champion's execution backend of
      record.** `PRODUCTION.yaml:180-211` names `champion.fair_deploy.backend: rust` and cites
      G4/G6/G7 inline; the registry ends at CL-074 with no row for it. The "an ENGINE, not a
      player; no elo owed" reasoning justifies not minting a STRENGTH claim, but the identity
      evidence is a governed assertion with a falsifier. Preferred: fold an explicit
      `EXECUTION BACKEND OF RECORD 2026-08-01 = carc_rs (rustport); behaviour-identical by G6 (100
      games, 14,384/14,384 actions, 0/101,088 checks) and G4 (0/305,515); falsifier = any
      RustFairAgent-vs-Python action divergence at production budget, or a MirrorDesync raised in
      production play` sentence into the G-2 amendment. Alternative: mint CL-075
      (category engineering/identity, Active, best_evidence `measurement/rustport_p{0..7}/` gate
      JSONs) with a one-line DECISIONS pointer. Do not leave it asserted only in PRODUCTION.yaml
      prose.
- [ ] **G-9. `docs/INDEX.md:11` — the Rust build-spec row still says BUILDING.** Change the status
      cell to `✅ COMPLETE 2026-08-01 — P0–P7 all green (G0–G7); app + backend flips landed;
      residual = caller conversion + review fix routing`.
- [ ] **G-10. `docs/INDEX.md:17` — the G0_REPORT row says the fleet legs are still open.** They
      landed the same day. Change to `PASS — local + laptop legs 0-mismatch; M5/macOS FAIL (Apple
      libm = third implementation ⇒ macOS is fallback-acceptance territory, not a v1 target);
      bionic MEASURED at G7 (msun + per-ABI exp)`.
- [ ] **G-11. `docs/INDEX.md:43` — the leaf-ablation prereg row still says RUNNING** although F7 is
      closed. Change to `✅ CLOSED 2026-07-31 — 6/6 cells (5×n=400, capoff n=384-accepted), claim
      CL-074, band 96e9 retired; farm cells deferred to F7b`, and add the F7 read-out pointer so
      the row is not prereg-only.
- [ ] **G-12. `docs/INDEX.md` — no row for the G7 on-device acceptance report.**
      `measurement/rustport_p7/G7_REPORT.md` (28e35b6) is the acceptance verdict for the whole
      mobile leg (full k8×1376 on a Pixel 9 Pro at 1.551 s/move median, thermal 1.007×, replay
      0/3,165 both ABIs, bionic libm answered) yet only G0 is indexed. Add a row directly after the
      G0_REPORT row, status `PASS 2026-08-01 (Pixel 9 Pro; ⚠️ Chaquopy's own numpy still 4 KiB
      aligned ⇒ APK not 16 KiB-ready)`.
- [ ] **G-13. The pre-registered champ-vs-10× (110080) oracle screen is unindexed, unqueued, and
      its state is reported nowhere.** `measurement/classical_search/KWIDTH_110K_PREREG_20260801.md`
      was committed before the run (ca5b571) but has no INDEX row (its `KWIDTH_22016`
      prereg/read-out sibling pair does, `docs/INDEX.md:52`), no roadmap line (Track G ends at G9),
      no read-out and no DECISIONS entry; its named landing site
      `/mnt/carc-shared/oracle_110k_20260801/` does not exist on the share. (a) Add a Track-G line
      "G10. Champ vs 10× champ (11008 vs 110080) oracle screen — status: <live on the laptop /
      PARKED>, prereg KWIDTH_110K_PREREG_20260801.md" with the **actual** state; (b) add the INDEX
      row beside the KWIDTH_22016 pair; (c) put the same one-liner in the new 2026-08-02 STATUS
      block so a fresh thread knows whether a job exists.
- [ ] **G-14. `docs/PROGRAM_ROADMAP_2026-07-07.md:94` — F9's stated gate contradicts STATUS.** F9
      reads "GATED ON F8 + the recentring decision" and "recentring choice = still his open
      decision"; both moved on 2026-08-01 (F8 complete, `STATUS.md:9` records "recentring =
      APP-ONLY 6→18 approved"). Restamp as `📋 UNBLOCKED 2026-08-01 (F8 complete; recentring decided
      APP-ONLY 6→18 — the app ships centred, the eval/desktop rules are UNCHANGED, so the
      transfer-bound cell is still owed and the desktop rules option remains Joshua's)` and delete
      the "still his open decision" clause.
- [ ] **G-15. `docs/PROGRAM_ROADMAP_2026-07-07.md:96` — F7d still marked RESEQUENCED-to-post-G6**
      after G6 passed. Restamp `🔓 UNBLOCKED 2026-08-01 (G6 passed) — run ONE crude-3-pt-then-refine
      sweep per box on the Rust-era eval_puct_priors workload; driver
      scripts/classical_search/wsweep_f7d.sh (Python-era fallback no longer needed)`, and mirror
      the flip in the new STATUS block (`STATUS.md:9` repeats the stale wording).
- [ ] **G-16. `docs/PROGRAM_ROADMAP_2026-07-07.md:88` — F7b's blocking rationale contradicts F7's
      own "Rust-severable" note and is priced off the dead Python path.** F7b still says the only
      route is a default-off knockout in `flat_leaf.py` **and** matching gates in
      `flat_leaf_cy.pyx` (+ rebuild both boxes + bit-exactness test) at ~37 h/cell. Since G2/G6 the
      Rust leaf is bit-exact over 3.34M values across all 12 config dialects with 7.98×/7.31×/41.6×
      deploy multipliers. Rewrite the second sentence to name the Rust route as primary ("add the
      default-off knockout to the Rust leaf + the Python reference, re-gate with the G2 three-leg
      bit-exactness harness; the .pyx route is now the fallback") and replace ~37 h/cell with a
      Rust-era estimate, or mark it TBD until benched.
- [ ] **G-17. `measurement/e4_games/README.md:8` — the lead ⚠️ banner states the carve-out in the
      present tense**, contradicting the same file's "Grading-epoch boundary at 2026-08-01" section
      at line 26+. A reader who stops at the ⚠️ lead grades new archives against the wrong budget
      (the analyzer already had to restate the epoch itself,
      `measurement/analyzer_20260802/ANALYZER_REPORT.md:208`). Replace lines 8-10 with an
      epoch-dependent banner: pre-2026-08-01 archives = k4×688 (~50 elo below the champion of
      record); 2026-08-01-build-onward archives = champion of record (k8×1376 = 11008 on the rust
      backend, carve-out CLOSED); every archive records `sims_effective`/`k_dets_effective`, and
      from 2026-08-01 the ABSENCE of `runtime_budget_override` is the full-strength marker.
- [ ] **G-18. `STATUS.md:9` — the second block still presents P3 as in-flight, G1-fuzz/P7 as open,
      and PRODUCTION.yaml as untouched.** STATUS's own rule is "update the blocks below in place /
      do NOT re-stack old epochs". Three concrete contradictions with the block directly above it:
      (a) headline "P3 IN FLIGHT + ABLATION 5/6 DONE (capoff finishing)" — P3–P7 all passed, F7
      closed; (b) "Open halves: G1's 10⁴-game lockstep fuzz + the P7 Android/bionic libm leg" —
      both closed the same window (fuzz 0/1,448,900, G7 green on the Pixel); (c) it ends
      "PRODUCTION.yaml untouched." — it was changed twice on 2026-08-01. Restamp the headline to
      `✅ Earlier (2026-07-31) — RUST PORT P0–P3 GREEN IN ONE DAY + THE LEAF-KNOCKOUT ABLATION
      CLOSED (F7/CL-074). Superseded by the block above`, replace the open-halves sentence with the
      closures (noting the fuzz also found the col-34 fatal border face), and delete the trailing
      "PRODUCTION.yaml untouched."

### LOW

- [ ] **G-19. `governance/BAND_REGISTRY.csv:32` — the 96e9 row puts the claim id in the wrong
      column.** Header is `…,claimed_date,decision_influenced,evidence_or_claim,notes`; every other
      row uses `decision_influenced ∈ {yes,no,not yet}` with the claim id in `evidence_or_claim`
      (e.g. 88e9 → `yes,CL-068 (amendment)`). The ablation row has
      `decision_influenced = "CL-074 (component-value table)"`, so a filter for
      retired-bands-that-influenced-a-decision silently misses the band CL-074 rests on — the exact
      failure the file exists to prevent. Set field 6 to `yes`, field 7 to
      `CL-074 (component-value table)`, and move the PREREG path into `notes`.
- [ ] **G-20. `governance/BAND_REGISTRY.csv:31` — the 94e9 row never got CL-072's id.** It still
      reads `not yet` / `scripts/distill_flywheel/TEACHER_H2H_PREREG.md` although CL-072 was minted
      on it 2026-07-30 (best_evidence "band 94e9, n=400 deck-paired"). Set field 7 to
      `CL-072 (Provisional; scripts/distill_flywheel/TEACHER_H2H_PREREG.md)` and extend notes:
      "CL-072 minted on this band 2026-07-30 (Provisional, n=400); status stays `claimed` because
      the pre-registered n=800 extension draws FRESH decks of THIS band — flip to retired only when
      that extension closes or is abandoned." Leave `decision_influenced = not yet` only if you also
      record that CL-072 is explicitly not-yet-decision-bearing; otherwise set `yes`.
- [ ] **G-21. `governance/CLAIM_REGISTRY.csv:72` — CL-071's counterevidence carries a stale "owed"
      note.** Item (4) ends "NOTE FOR JOSHUA: PRODUCTION.yaml still quotes the 14.3–17.4% band in
      four places … the correction to ~20.6% is owed there." Commit 42b2dbf made that correction
      (`PRODUCTION.yaml:50-51`, `:212`, plus CHECKPOINT_LINEAGE / roadmap G6 / STATUS). Replace the
      sentence with "DONE 2026-07-30 in 42b2dbf: … no occurrence of the old band survives as a live
      figure."
- [ ] **G-22. `governance/BAND_REGISTRY.csv` — G6's 100 identity-gate games consumed seeds 98e9+
      that no registry row and no share manifest records.** The gate self-documents
      `deck_range {base: 98000000000, n: 100}` (and the post-flip re-check reuses base 98e9, n=10),
      but the registry's prescribed discovery is "THIS file plus
      `grep -h seed_start /mnt/c/carc-shared/*/manifest.json`" — these artifacts live in-repo under
      `measurement/rustport_p6/` and key the field `deck_range.base`, so **both** discovery paths
      miss them and a future confirmatory cell could draw 98e9 believing it fresh. Append a row:
      `98000000000,RUST PORT G6 backend identity gate (100 games k8x1376) + 2026-08-01 post-flip
      re-check (10 games),dev,retired,2026-08-01,no,measurement/rustport_p6/G6_backend_g6_k8x1376.json,Identity
      gate - NO strength number and no claim rests on it; registered only so the seeds are not
      silently redrawn. Seeds 98000000000..98000000099 (deck_range.base in the artifact - note the
      key is deck_range.base, NOT seed_start, so the share-manifest grep does not see it).`
- [ ] **G-23. `docs/PROGRAM_ROADMAP_2026-07-07.md:92` — F8's P7 wheel-alignment ⚠️ is left standing
      although the same line records the fix.** The P7 clause warns "shipped carc-cy wheels are
      4 KiB-aligned — rebuild at next app release" while the flip clause ~200 words later says
      "Also fixed: cy wheels 16 KiB-aligned both ABIs … + a LINK_SIGNATURE version salt". Append to
      the P7 warning: `(✅ FIXED 2026-08-01 — see the flip clause below; ⚠️ Chaquopy's own numpy is
      still 4 KiB, so the APK as a whole is not 16 KiB-ready)`.
- [ ] **G-24. The post-flip agreement RE-CHECK is absent from all three governance docs.** Commit
      06d02a0 landed `measurement/rustport_p6/G6_backend_RECHECK_postflip_20260801.json` —
      1435/1435 actions, 0 mismatches, i.e. the evidence that the flip broke nothing *after* the
      code changed — and it appears in neither F8, STATUS, nor INDEX. Add to F8 after the flip
      clause: `✅ POST-FLIP RE-CHECK (2026-08-01): 1435/1435 actions agreed, 0 mismatches`, and cite
      it in the new 2026-08-02 STATUS block.
- [ ] **G-25. The 2026-08-02 deliverables are indexed but never queued in the roadmap.**
      `docs/INDEX.md:13-15` carry the analyzer slice, the P1 paper and the review's fix routing, but
      the roadmap — designated by CLAUDE.md as the single queue where "every new finding/lever lands
      the moment it exists" — has no line for any of them (F-track ends at F9/F7d; E3 "Phase 5" is
      the unrelated Gumbel-flywheel item). Add after F9: `F10. Rust-port review remediation` (with
      the confirmed-finding classes and an owner), `F11. Caller conversion for backend=auto (the F8
      residual)`, `F12. Phase-5 analyzer slice 1 landed 2026-08-02 — next slice / coach-mode
      gating`, plus a pointer line for the P1 paper draft (publication decisions Joshua's).
- [ ] **G-26. `docs/PROGRAM_ROADMAP_2026-07-07.md:13` — the NOW header is still dated 2026-07-10 and
      names E4 as NEXT.** The "## NOW (2026-07-10)" block and the "Recommended execution order"
      block near the tail present E4 human-anchor as next and C-cheap as the last close-out — three
      weeks and two tracks (F, G) behind. Retitle to `## NOW (2026-08-02)` with the current
      three-item next list (F10 review remediation / F11 caller conversion / F9 transfer-bound cell
      + F7d sweep) and stamp the old text "historical, 2026-07-10 — do not action".

### Housekeeping nit found while cross-checking (not from the round-2 data)

- [ ] **`docs/INDEX.md:15` says the rust-port review has "11 confirmed"; `REVIEW.md` §CONFIRMED
      numbers exactly ten (#1–#10).** Reconcile the count when the INDEX row is next touched — and
      note that after §1 above the honest figure is **18 standing findings** (10 numbered + 8
      upheld from CONTESTED).

---

## Provenance

Round 2 of the "Eff Dario" pass, 2026-08-02. Inputs: the ten CONTESTED items of
[`measurement/rustport_review_20260802/REVIEW.md`](../rustport_review_20260802/REVIEW.md)
re-adjudicated against the code and the built wheel in this checkout; a flip review of the
2026-08-01 backend/budget flips and the Android wheel toolchain; and a governance sweep over
[`STATUS.md`](../../STATUS.md), [`DECISIONS.md`](../../DECISIONS.md),
[`BACKLOG.md`](../../BACKLOG.md), [`docs/INDEX.md`](../../docs/INDEX.md),
[`docs/PROGRAM_ROADMAP_2026-07-07.md`](../../docs/PROGRAM_ROADMAP_2026-07-07.md),
[`governance/CLAIM_REGISTRY.csv`](../../governance/CLAIM_REGISTRY.csv),
[`governance/CHECKPOINT_LINEAGE.csv`](../../governance/CHECKPOINT_LINEAGE.csv),
[`governance/BAND_REGISTRY.csv`](../../governance/BAND_REGISTRY.csv) and
[`measurement/e4_games/README.md`](../e4_games/README.md).
**Nothing outside this file was written.** §2 and §3 are read-only findings — routing and
application are Joshua's call.
