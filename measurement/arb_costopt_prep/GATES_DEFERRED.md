# GATES_DEFERRED — the tier1 playout scorer swap

> **✅ STATUS 2026-08-30 — §2 BANKED · §3a PASS · §3c PASS · §3b BLOCKED (shared
> box, timing only).** Results, method and the R9 threading decision:
> [`GATES_L0_L1A_20260830.md`](GATES_L0_L1A_20260830.md). The §3b PASS criterion
> (legacy 90–105 ms/playout, factor 6.7–7.9×, EXCLUSIVE tenant) is the one thing
> still owed — it cannot be met while a funded eval shares the box, and the
> contaminated read (9.51×, legacy 296.9 ms) must NOT be recorded as a pass.
> The 2026-08-28 banner below is kept for the record.

> **⚠️ STATUS 2026-08-28 — BRANCH BLOCKED ON THESE GATES.** The swap is landed and
> locally gated on branch `worktree-agent-af441852ab4b1e9fe`
> (`/home/doctor/projects/carcassone/.claude/worktrees/agent-af441852ab4b1e9fe`).
> **It does NOT merge to `main` until §2 and §3 below both PASS.** They are
> deferred only because the local box is saturated by the funded A1 eval round
> (`eval_fair_puct … --workers 30 … ARB_EARLY_L`, load 32/32 at the time of
> writing) — §2 is a 30-worker job and §3 is a timing-sensitive contrast, and
> neither may share the box with that tenant (memory
> `feedback_no_agent_compute_beside_eval`: one niced 1-core DRAM churner inflated
> a saturated W=22 eval ~1.8×/move).

## 0. What changed

`carc_core::tier1::RuleBasedPlayer::best_by_virtual_score` no longer scores each
candidate with `GameState::count_final_scores`. It calls
`leaf::decompose_into` + `leaf::flat_base_score` over **thread-local**
`Decomp`/`Scratch` buffers, with a legacy fallback at the wrapping border
(`tier1::border_wrap_hazard`). Bit-identical replacement — no flag, no config
knob, no strength claim owed. Evidence base:
[`PROFILE_TIER1.md`](PROFILE_TIER1.md) §4.

## 1. Gates already PASSED on the branch (2026-08-28, this box)

| gate | result |
|---|---|
| `cargo test -p carc-core` (full suite, dev) | **205 passed / 0 failed / 5 ignored**, 214.9 s — includes the whole `tiearb::tests` suite (`threading_is_bit_identical_to_sequential`, the order-preserving fold, the first-failure-wins pins) |
| `the_two_scorer_routes_agree_on_every_candidate_of_a_played_corpus` | **2,377 candidate values, 0 divergences**; coverage asserted — farm 4,020 · cloister 3,631 · city 9,679 · road 11,936 meeple-observations, 58 argmax ties, 4/4 games to a deck-exhausted terminal (the terminal position itself is checked separately) |
| `the_scorer_swap_is_trajectory_identical` (always-on, 12 playouts) | `(margin, plies)` identical |
| `the_scorer_swap_is_trajectory_identical_at_scale` (`--ignored`, release) | **256 playouts, `(margin, plies)` identical**, 20 deck seeds × root plies {0,12,30,54,78} × 3 picks; **border fallbacks fired: 0** |
| `the_border_hazard_predicate_routes_to_the_legacy_scorer` | predicate false through a whole game; true on a last-row and a last-column board; the fallback returns the byte-identical legacy value; the accessor asymmetry (`board_direct(-1,·)` wraps, `get_tile(-1,·)` does not) is pinned |
| `cargo check -p carc-py -p carc-cli` | clean |
| `tier1_scorer_bench` (`--ignored`, release, W1) | 296.06 → 29.84 ms/playout, **9.92×** — absolutes inflated ~3.3× by the A1 tenant; the ratio is a back-to-back paired contrast on the same contention. §3 re-reads it clean. |

## 2. ⛔ THE BANKED G-BITEXACT PASS — the merge blocker

The banked judge is the OTHER cache shape. Everything above ran
`legal_mask_cache = None/false` (what `tiearb::arbitrate` deploys);
`G-BITEXACT` grades `legal_mask_cache = true`, whose
`string_representation` collisions moved 57 of 15,360 banked playout values and
are load-bearing (`tier1.rs` module docs). The swap must reproduce those
collisions' downstream values too.

`scripts/tiletie/verify_tier1_rust.py` is the existing machinery; it compares the
**raw f64 bit patterns** of `carc_rs.tier1_leg` against the banked Stage-1b
python judge over a sample committed before it was drawn (240 legs / 15,360
playouts). The reference PASS is
[`../tiearb2_stage2_20260817/BITEXACT.json`](../tiearb2_stage2_20260817/BITEXACT.json).

**Run it against a wheel built from THIS branch, unpacked to a shadow dir — the
main venv's `carc_rs` is NOT to be replaced** (house pattern, copied from
`scripts/classical_search/phase_seam_gate_chunked.sh`):

```bash
# In a QUIET window: no eval_fair_puct, no self-play. Census first:
#   ps -eo pcpu,args --sort=-pcpu | head -5 ; cat /proc/loadavg
set -euo pipefail
REPO=/home/doctor/projects/carcassone
WT=$REPO/.claude/worktrees/agent-af441852ab4b1e9fe        # this branch
OUT=/tmp/tier1swap_gate; mkdir -p "$OUT/wheel" "$OUT/shadow"

# 1. wheel from the BRANCH worktree (site-packages untouched)
nice -n 19 "$REPO/.venv/bin/maturin" build --release \
  -m "$WT/rust/carc/carc-py/Cargo.toml" -o "$OUT/wheel"

# 2. unpack to a shadow dir
WHEEL=$(ls -t "$OUT"/wheel/carc_rs-*.whl | head -1)
"$REPO/.venv/bin/python" -c \
  "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
  "$WHEEL" "$OUT/shadow"

# 3. provenance check — the shadow carc_rs must be the branch build
PYTHONPATH="$OUT/shadow" "$REPO/.venv/bin/python" -c \
  "import carc_rs; print(carc_rs.__file__, getattr(carc_rs,'VERSION','?'))"

# 4. THE GATE (n=30 workers; exclusive tenant)
PYTHONPATH="$OUT/shadow" nice -n 19 "$REPO/.venv/bin/python" \
  "$REPO/scripts/tiletie/verify_tier1_rust.py" \
  --workers 30 --out "$OUT/BITEXACT_tier1swap.json"
```

**PASS criteria — all of them, no partial credit** (the counts are constants in
the script by design; a truncated run must FAIL, not trivially satisfy):

```
pass                    == true
n_legs_found            == 240
n_playouts_compared     == 15360
n_value_bit_identical   == 15360
n_value_mismatch        == 0
n_plies_identical       == 15360
n_plies_mismatch        == 0
n_seed_witness_ok       == 240
digests_equal           == true
sha256_values_rust      == 0c2e39fed5259320bf9891c221796be67b6805c057d98df02f426bc0e6b88e80
```

That sha256 is the banked 2026-08-17 PASS. **The swap is bit-identical iff the
new run reproduces that exact digest** — it is the whole gate in one line.
Compare with:

```bash
python3 - <<'EOF'
import json
new = json.load(open('/tmp/tier1swap_gate/BITEXACT_tier1swap.json'))
old = json.load(open('/home/doctor/projects/carcassone/measurement/tiearb2_stage2_20260817/BITEXACT.json'))
keys = ["pass","n_legs_found","n_playouts_compared","n_value_bit_identical",
        "n_value_mismatch","n_plies_identical","n_plies_mismatch",
        "n_seed_witness_ok","digests_equal","sha256_values_rust","sha256_values_python"]
bad = [k for k in keys if new.get(k) != old.get(k)]
print("GATE PASS" if not bad and new.get("pass") else f"GATE FAIL on {bad}")
EOF
```

⚠️ `RECORDS_ROOT = /mnt/c/carc-shared/tiearb2_20260816/main` must be mounted and
populated, or the script fails the expected-count assertion (correctly).

## 3. Deferred companions (same quiet window, cheap)

**3a. Threaded `arbitrate` identity at production shapes.** The rust suite's
`tiearb::tests::threading_is_bit_identical_to_sequential` already passes on the
branch, but it runs in the dev profile at small `B`. Re-run it release, and
re-run the whole `tiearb` module:

```bash
cd /home/doctor/projects/carcassone/.claude/worktrees/agent-af441852ab4b1e9fe/rust/carc
nice -n 19 cargo test -p carc-core --release -- tiearb::
```
PASS = every `tiearb::` test green, `threading_is_bit_identical_to_sequential`
included. (Why it matters here: the flat scorer's buffers are thread-local, so a
sharing bug would show up as a thread-count-dependent margin — precisely what
this test refuses.)

**3b. Clean W1 bench (exclusive tenant).** Re-read §1's factor without the A1
tenant, so the number that goes into any `rho_wall` arithmetic is honest:

```bash
cd /home/doctor/projects/carcassone/.claude/worktrees/agent-af441852ab4b1e9fe/rust/carc
nice -n 19 cargo test -p carc-core --release -- --ignored --nocapture tier1_scorer_bench
```
EXPECT: legacy ≈ 90–105 ms/playout (the `PROFILE_TIER1.md` / `COST_REMEASURE`
band), factor in the **6.7×–7.9×** bracket the profile brackets it at. A factor
below ~5× on an exclusive box means the in-situ transfer did not happen and the
`rho_wall` arithmetic in `PROFILE_TIER1.md` §4.5 must be re-derived.

**3c. Python-side tiearb tests.** Nothing python was run for this change: the
main venv's `carc_rs` predates the branch, so a python run would grade the OLD
scorer and report a meaningless PASS. Run the python tiearb/tier1 tests under the
same `PYTHONPATH="$OUT/shadow"` as §2, or not at all.

## 4. Not owed

- No elo / strength number. The swap is bit-identical by construction and by
  §1–§2; the threads-arming precedent applies (bit-identical ⇒ no strength claim).
- No `results.csv` row, no claim id, no band, no `PRODUCTION.yaml` edit. This is
  an engine speedup, not an experiment. What a cheaper arbiter *buys* is the
  `tiearb_widening` ladder's question, not this branch's.
