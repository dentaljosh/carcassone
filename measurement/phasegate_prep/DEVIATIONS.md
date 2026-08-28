# phasegate_prep — execution-layer deviations (launch + post-launch)

The house class distinction, carried from `IS-D1` (invasion round 1) and the `everyply` `EP-D1..D5`
precedent:

- **EXECUTION-LAYER / STATISTICS-BLIND** deviations — a misaddressed reader, a launcher-side typo, a
  path fix, a worker count — are recorded **here**, with root cause, ground truth verified BEFORE
  the fix, the fix itself, and why the smoke could not catch it. They do **not** touch a bar, a gate
  of record, or a branch condition.
- **ANYTHING THAT WOULD MOVE A BAR OR A BRANCH** is not a deviation. Before game 1 it is a
  pre-game-1 amendment to the pair, made in the open with the band unspent. After game 1 it is not
  available at all — only round 2's route (freeze the verdict, record the defect, OWNER authorises a
  named single-clause re-read of the SAME archive).

⛔ **Nothing below moves a bar, a gate of record, or a branch condition.**

---

## PG-D1 — `test_the_band_is_proposed_not_claimed` inverts at authorization (expected)

**2026-08-28, pre-launch.** `tests/test_phasegate_instrument.py::test_the_band_is_proposed_not_claimed`
asserts the **build-time** state — that `BAND_CLAIMED`, `BLIND_COMMIT`, `PINNED_SRC_REV` and
`RUN_LIVE.json` are all **absent** from `measurement/phasegate_prep/`. Every one of those four is an
artifact the launch is *required* to create, so the test **necessarily fails once the round is
authorized**, and it is not a defect in either direction.

**Ground truth verified before proceeding:** with the four artifacts absent (`PINNED_SRC_REV` moved
aside), `tests/test_tiearb_phase_gate.py` + `tests/test_phasegate_instrument.py` = **48 passed, 0
failed**. The pin was then restored. The rust workspace was green in the same window (**201 passed,
3 ignored, 0 failed**).

**Why the smoke could not catch it:** it is a repo-state assertion, not a code path the smoke
exercises. Statistics-blind — it reads no archive and feeds no gate.

**Standing note for the adjudication:** re-running that one test after launch is expected RED and
proves only that the round is authorized. Run the pair's suites at a commit where the four artifacts
are absent if a clean green is wanted.

---

## PG-D2 — `W_LOCAL` 14 → 30 (owner override)

**2026-08-28, pre-launch.** `WORKERS.conf` shipped `W_LOCAL=14` (the design-time figure behind
DESIGN §6.4's realized 1.45:1 fleet ratio and §6.5's 13.5 h balanced wall). The owner's ratified
Shabbos envelope sets the defaults verbatim: *"we should default to w22 laptop w30 local"*.
`W_LOCAL=30`, `W_LAPTOP=22` unchanged.

**Why it is statistics-blind:** `W` is throughput-only. Games are bit-identical at any `W` and **no
gate in this pair reads a clock** (READ_RULE header; DESIGN §6.4). It moves wall clock, and it makes
the design's ETA conservative rather than optimistic — the cell→box assignment is **not** recomputed,
because the assignment is frozen in `screen_lib.CELLS` and is a gate input (`G-HOST`).

---

## PG-D3 — the wheel: DESIGN §7.7 prose vs. the implemented `G-WHEEL-SAME`

**2026-08-28, pre-launch.** DESIGN §7.7 instructs *"Install the SAME WHEEL FILE on both boxes …
NEVER a laptop-local `maturin build`"*, on the stated reason that a per-box build would move
`carc_rs_binary_sha` and `G-WHEEL-SAME` would refuse. The **implemented** gate does not work that
way: `analyze_phasegate.py:481–500` asserts `G-WHEEL-SAME` **per box** (`by_role`), documenting that
`carc_rs_binary_sha` is box-local and that `carc_rs_build` is the cross-box witness — and READ_RULE
§4's `G-WHEEL-SAME` row says the same in its own parenthesis.

**Resolution — satisfy BOTH readings, deviate from neither:** one wheel file was built on the local
box (`maturin build --release -m rust/carc/carc-py/Cargo.toml`, rustc 1.96.0) and the **same file**
was copied to the laptop and installed there. The wheel is `abi3` (`cp312-abi3-manylinux_2_34_x86_64`),
so it installs against the laptop's Python 3.14 as well as local's 3.12. No laptop-local `cargo`
build was performed — the laptop has no `rustc` on its non-interactive `PATH` in any case.

**Statistics-blind:** it is a build-transport choice; both readings of the gate pass under it.

---

## PG-D4 — the installed wheel's sha ≠ `IDENT_BITEXACT.json`'s build-time sha

**2026-08-28, pre-launch.** `IDENT_BITEXACT.json` records `carc_rs_binary_sha =
eff20530854d914a` for the wheel built **in the build worktree**. The wheel deployed for the round,
rebuilt from merged `HEAD` on the main tree, is `05fe19ecb65d06a1`. Rust release builds are not
byte-reproducible across build directories, so a differing sha for identical source is expected.

**Why this is not an identity failure:** `IDENT-BITEXACT` proves a property of the **source** —
`gate=all` reproduces the ungated arbiter's action sequences and `gate=none` reproduces the
champion's, both bit-for-bit — and that proof is carried by the merged source, not by a particular
`.so`. `G-WHEEL-SAME` binds **across this round's own cells** on each box, never against the build
fixture. The round additionally carries its own `IDENT` **game** cell, which is what DESIGN §7.7's
`G-WHEEL-SAME` re-owe rule actually requires of a wheel change.

---

## PG-D5 — `HEAD` moved under the preflight (docs only)

**2026-08-28, pre-launch.** `HEAD` was `2d0ecdde` (the phasegate build merge) when the preflight
opened and `f52978b5` a few minutes later — an orchestrator commit touching
`docs/PROGRAM_ROADMAP_2026-07-07.md` and nothing else (`git diff --stat 2d0ecdde..f52978b5` = 1 file,
1 insertion, 1 deletion). No code path moved; `run_cells.sh`'s `assert_rev` cleanliness check
(`src engine scripts rust tests`) was clean at every boundary.

**Handling:** `PINNED_SRC_REV` is (re)written from `git rev-parse HEAD` on **each box** after the
last launch commit, so the pin names the launch `HEAD` on both boxes and `G-REV`'s cross-box clause
(`screen_lib.cross_box_rev_gate`) sees one 40-hex pin.

---

## PG-D6 — no `RUN_LIVE.json` and no watchdog in this instrument

**2026-08-28, pre-launch.** Unlike `invasion_screen_r3_prep/run_cells.sh` (1,586 lines, which drops
its own `RUN_LIVE.json` freeze-latch sentinel and censuses foreign ones), this round's
`run_cells.sh` is a 246-line launcher that creates **no** `RUN_LIVE.json` and ships **no** watchdog.

**Handling:** the executor drops `RUN_LIVE.json` by hand after the last launch commit, so the
house-wide freeze-latch hook protects the round in the usual way. ⛔ **No watchdog was improvised** —
none exists for this instrument, and inventing one at launch is exactly the class of launcher-side
change that has no selftest behind it. The orchestrator owns liveness monitoring for this round.
