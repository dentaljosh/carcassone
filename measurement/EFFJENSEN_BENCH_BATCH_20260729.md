# Eff Jensen bench batch — 2026-07-29 quiet window

**STATUS: MEASURED 2026-07-29.** Five queued benches executed back-to-back on the
local 5900XT box during the first genuinely quiet window since the CL-067
equal-wall-clock gate freed both cluster boxes. Every number below is read off a
committed JSON/manifest on disk; nothing here is extrapolated unless it says so.

This is a **measurement-infrastructure** read-out. No games decide anything here,
no elo is produced, no champion or claim changes. It settles four engineering
questions that were blocking roadmap **G3** (per-move cost) and **G6**
(k-parallel inference).

| # | Bench | Decision rule | Verdict |
|---|---|---|---|
| 1 | k-parallel merge + fixes | suites green, behavior identical | ✅ merged, 265 tests green |
| 2 | k-parallel latency | is the split's speedup real? | ✅ **YES — 3.16× at deploy (W4), 6.37× at k8×1376 (W8)**; k8×1376 falls from 91% of clock to **14.3%** ⇒ tournament-legal by engineering |
| 3 | net transport | CPU-1t ≲ 3× GPU b1 ⇒ net-on-CPU | ❌ **NO — 5.8×, fails by ~2×.** And the headline: clean GPU batch-1 is **2.0 ms, not 19.4 ms** (9.7× overstatement) |
| 4 | WSL vs native Windows | is there a hypervisor tax? | ❌ **NO — sign inverted.** Native Windows is **25% slower** on search, 6% on GPU b1 ⇒ lever dead |
| 5 | clean 5900XT single-stream | M5-vs-5900XT clean ratio | ✅ **1.74× at deploy** (not the contended 2.85×) — ratio flat across 86× sims |

---

## 0. Pre-flight — the box really was quiet

Censused immediately before the first bench and re-censused between every step:

```
python processes : 0
loadavg          : 0.00 0.05 0.01
GPU              : RTX 5060 Ti, 0% util, 5.98 W, no compute apps
cores            : 32 threads (5900XT, 16C/32T)
```

This matters more than usual: every bench in this batch is a **latency**
measurement, and the whole reason four of them were queued rather than run is
that the box was carrying the CL-067 gate's 16 spawn workers (`loadavg` ~13) when
the questions were first asked.

⚠️ **The box did NOT stay this quiet.** From 12:54Z another agent ran `pytest tests/`
for over an hour at ~1 core of 32. §2 finished before it started and is clean; §3 was
re-run twice to bound the effect; §4 and §5 carry it. **Per-step contention disclosure
is in §7** — read it before quoting any absolute number from §3–§5.

---

## 1. k-parallel merge (G6 stage 1) + two filed one-liners

**Merged** `worktree-agent-abca7b7d76a3b2bcc` (`4768b32`, "G6 stage 1:
behavior-identical k-process split") into `android-app`.

The main tree had advanced 12 commits past the worktree's base `39fb114` (the M5
campaign, the Pixel NPU probe, the eff_linus staging). Only two files overlapped
and both were docs:

* `docs/LEVER_INDEX.md` — auto-merged clean.
* `docs/PROGRAM_ROADMAP_2026-07-07.md` — **one conflict**, in the G3/G6 block.
  Resolved keeping **both sides' content**, which is what the two edits actually
  were: HEAD's G3 line had gained the `eff_linus` hypervisor-tax paragraph, and
  the worktree's G6 line had gained the "STAGE 1 BUILT + SMOKED" status. Disjoint
  edits that collided only because they are adjacent list items.

Source files (`fair_agent.py`, `champion_factory.py`) had **no** competing edits,
so the k-parallel implementation merged unmodified.

### Test suites — counts match the worktree's report

Run on the quiet box after the merge:

```
265 passed in 118.78s
```

| suite | collected | worktree reported |
|---|---|---|
| `tests/test_kparallel.py` | 12 | 12 ✅ |
| `tests/test_fair_agent.py` | 20 | green ✅ |
| `tests/golden/` | 194 | green ✅ |
| `tests/test_intra_reuse.py` | 39 | green ✅ |
| **total** | **265** | |

`test_kparallel` is the load-bearing one: it steps a sequential and a parallel
champion through full games side by side and asserts the chosen action **and**
the pooled root `(N, W)` are equal at every move, endgame latch included. The
behavior-identity claim is proven, not asserted.

### Fix (a) — `eval_fair_puct --smoke` crashed without `--games`

Applied from the filed patch
`scripts/m5_bench/patches/0001-eval_fair_puct-bare-smoke-games-none.patch`.

`_smoke()` read `args.games`, which argparse leaves `None` when the caller used
`--n` (the `--games` → `--n` alias resolves the *other* way), so a bare `--smoke`
died with `TypeError: '>' not supported between instances of 'NoneType' and 'int'`
before playing a single game. Falls back to **one** game — deliberately not
`args.n`, whose default of 100 would turn a wiring proof into a ~2 h run.

Platform-independent (it reproduces on Linux; it was simply first *hit* on
darwin-arm64). The M5 campaign cells were unaffected — both were smoked with an
explicit `--games N`, so that harness ran byte-unmodified.

**Verified:** `--smoke --sims 8 --k-dets 2` with no `--games` now runs 1 game,
rc=0, fair plumbing + marginalized endgame confirmed.

### Fix (b) — `champion_factory` could not load the champion on Windows

`load_production_spec()` called `path.read_text()` with no encoding.
`Path.read_text()` then uses `locale.getpreferredencoding()`, which is **cp1252**
on a stock Windows CPython.

This is not cosmetic. `governance/PRODUCTION.yaml` carries **167 non-ASCII
bytes** (`±`, `×`, `–`, `—`, `→`, `⇒`, `∈`, `−`, `≈`, `⚠`, `✅`) and cp1252
**hard-fails** on byte `0x8f` at offset 1967:

```
UnicodeDecodeError: 'charmap' codec can't decode byte 0x8f in position 1967
```

So the native-Windows arm of the eff_linus A/B could never have loaded the
champion at all. Found by the Eff Linus agent. Fixed by passing
`encoding="utf-8"` explicitly.

**Verified:** the leaf still hash-verifies under the canonical v2.9 Bmild_cap8
leaf env — `make_production_champion("fair", verify=True)` builds clean and

```
harness_leaf_hash            a36d2e15a3b3d71d   (== PRODUCTION.yaml leaf_hash)
frozen_config_hash_meeple_k0 6dfffd57051690f2
frozen_config_hash_meeple_k2 158f17ff76adaa02
```

⚠️ **A note for whoever verifies this next.** My first verification attempt
reported a `ProvenanceError` *fingerprint drift*. It was **my invocation**, not a
defect: I had set only `CARCASSONNE_V25_CAP/OPP_CAP` and omitted
`DROP_THREE_OPEN`, `V29_MEEPLE_CURVE`, `MEEPLE_K` and `VALUE_BLEND`, which builds
a different `LeafConfig` and therefore a different hash. Confirmed pre-existing
and unrelated to the merge by reproducing the identical failure, byte for byte,
on pre-merge `efb3365` in a throwaway worktree. **Use the full
`env_preamble.PROD_ENV` knob set** (or `scripts/m5_bench/bench_champion.py`'s
`_CANON_ENV`) when hand-verifying the leaf; a partial env silently reshapes the
fingerprint.

---

## 2. k-parallel latency (G6 stage 1) — **the split is real: 3.16× at deploy, 6.37× at k8**

`scripts/measurement_infra/kparallel_latency_bench.py`, full run, 30 replayed real
mid-game roots (ply 0.35–0.70 of real champion games via lossless deck-seed replay).
Artifacts: `measurement/kparallel_bench_20260729/{manifest.json,rows.csv,rows.json}`.

⚠️ **This is a cold re-run.** The first attempt died with a Claude session restart at
~60 % complete; its partial numbers were **discarded, not salvaged**. Where the two runs
overlap they agree to within 5 % (seq k4×688 3.390 → 3.228 s, W2 1.75× → 1.73×, W4
3.22× → 3.16×), which is a free reproducibility check.

| budget | mode | mean s/move | p90 s/move | speedup (mean) | speedup (p90) | transport ms/move | actions == sequential |
|---|---|---|---|---|---|---|---|
| **k4×688** (2752, deploy) | sequential | 3.2276 | 4.0357 | — | — | — | (baseline) |
| | W=2 | 1.8634 | 2.2602 | **1.73×** | 1.79× | 5.62 | ✅ |
| | W=4 | **1.0200** | 1.3394 | **3.16×** | 3.01× | 6.34 | ✅ |
| **k8×1376** (11008, CL-068 shape) | sequential | 13.7552 | 16.7833 | — | — | — | (baseline) |
| | W=4 | 3.8247 | 4.5783 | **3.60×** | 3.67× | 5.99 | ✅ |
| | W=8 | **2.1595** | 2.6167 | **6.37×** | 6.41× | 7.24 | ✅ |

### Verdict — **YES, the speedup is real, and it beats the "~3× not 4×" prior**

* **Decision number, k4×688 at W=4: `3.164×` wall-clock** (p90 `3.013×`). The DRAM-wall
  prior said "expect ~3×, don't assume 4×" — measured **79 % parallel efficiency**, at the
  top of that expectation.
* **k8×1376 at W=8: `6.370×`**, i.e. **80 % efficiency on 8 workers** — the efficiency does
  *not* collapse as workers double, which was the live risk.
* **Behavior identity re-verified at production budget.** All four parallel rows chose the
  **identical action on all 30 roots** (`actions_match_sequential: true`). The bench fails
  loudly otherwise, so this is a real assertion, not an absence of evidence.
* **Transport is a rounding error**: 5.6–7.2 ms/move parent-side (pickle + permutation +
  scheduling), i.e. **0.6 % of the deploy move and 0.3 % of the k8 move**. The gap from
  linear speedup is memory-bandwidth/DRAM, *not* IPC — so batching the transport would buy
  nothing.
* Efficiency is *higher* at the bigger budget (k8 W4 = 90 % vs k4 W4 = 79 %): more work per
  world amortises the fixed per-move overhead better.

### The clock closure — what fraction of the CL-068 91 % figure remains

CL-068 closed the budget question at fixed clock under an unstated **single-stream**
assumption, recording k8×1376 = 11008 sims at **91 % of clock**. Applying the measured
8-way split ratio (`2.1595 / 13.7552 = 0.157`):

> **91 % × 0.157 = `14.3 %` of clock.**
> The k8×1376 configuration now consumes **15.7 % of what CL-068 priced it at** — it goes
> from *nearly the whole clock* to *about a seventh of it*. The roadmap's advance guess of
> "~12–15 % split 8-way" is **confirmed**, at the low end.

⚠️ **One inconsistency, surfaced not smoothed.** The roadmap's two clock anchors are not
mutually consistent with what we measured. It records deploy k4×688 at **26 %** of clock
and k8×1376 at **91 %** — a ratio of 3.5×, whereas the *measured* sequential cost ratio is
**4.262×** (13.7552 / 3.2276) for a 4.000× sims ratio. Anchoring instead on the 26 % figure
gives clock ≈ 12.41 s/move, which puts k8×1376 sequential at **111 %** of clock (not 91 %)
and the W=8 split at **17.4 %**.

**So the honest band is `14.3 %`–`17.4 %` of clock, depending on which published anchor you
trust.** The G6 conclusion is insensitive to the choice — both are far under 100 %, so
**k8×1376 becomes tournament-legal through engineering alone**, which is exactly the prize
G6 was named for. But somebody should reconcile the 26 %/91 % pair before either is quoted
again; this bench cannot do it, because the clock's own definition lives outside it.

**Caveat that limits this section:** latency only. The split is behavior-identical, so it
needs no strength re-eval — but "tournament-legal" is a *clock* claim, and CL-060's +49.9
for this configuration was graded by a ruler (RoD-v2) that CL-070 showed to be ~70 elo
unreliable on this contrast. Cheap clock ≠ established strength.

---

## 3. Net forward-transport (G3) — **net-on-CPU is REFUTED at 1 thread; the old GPU number was a contention artifact**

`scripts/measurement_infra/net_transport_bench.sh`, CL-067 `iter_03.pt`
(sha256 `6e26799…3751a1`, verified by the bench), batch-1 = the real
`make_single_evaluator_policy_only` path, 2000 calls / 200 warmup per row.

The CUDA rows were code-path-unverified (built on a loaded box), so a
`--rows cuda_b1 --calls 15` sanity ran first: **1.780 ms, path green.**

**The bench then ran twice**, because another agent's `pytest tests/` started ~90 s into the
first run. Rather than discard it, the second run at a 3× lower loadavg turns the accident
into a **load-sensitivity check**:

| row | run A (`loadavg` 3.85) | run B (`loadavg` 1.19) | Δ |
|---|---|---|---|
| **cuda_b1** | **1.975 ms** | **2.017 ms** | +2.1 % |
| **cpu_1t** | **11.532 ms** | **11.751 ms** | +1.9 % |
| cpu_2t | 7.008 | 7.787 | +11 % |
| cpu_4t | 4.871 | 4.778 | −1.9 % |
| cuda_b8 | 2.348 | 3.135 | +34 % |
| cuda_b32 | 4.481 | 4.417 | −1.4 % |
| cuda_b128 | 19.789 | 19.356 | −2.2 % |
| cpu_1t_compile | 10.812 | 10.504 | −2.9 % |

The two decision rows agree within **2 % across a 3× loadavg change**, so the verdict below
is robust to the contention that was present. (The noisier rows — cpu_2t, cuda_b8 — are the
ones where a single stray core matters most; they are not decision rows.)

### Verdict — **NO. Do not default single-game deploy to net-on-CPU.**

The pre-registered rule is *"if clean CPU-1t ≲ 3× clean GPU batch-1, default to net-on-CPU."*

> **Measured: `11.64 ms / 2.00 ms` = `5.8×`.** The rule requires ≲3×. **It fails by ~2×.**
> GPU batch-1 wins decisively for single-game deploy.

Two things worth carrying forward:

1. 🚨 **The headline correction: clean GPU batch-1 is `~2.0 ms`, not the `19.4 ms` on
   record — a `9.7×` overstatement.** The 19.4 ms figure was taken on a loaded box and is
   an artifact; every argument that leaned on "batch-1 is the GPU's worst case, ~19 ms"
   needs re-examining, including the r = forward/search cost ratio in the CL-067 gate's
   reopen condition. *(Noted without claiming it: `cuda_b128`'s forward here is
   **19.36–19.79 ms** — numerically almost exactly the old figure. That may be coincidence,
   but it is the kind of coincidence worth one person's five minutes.)*
2. **`cpu_4t` at `4.83 ms` = `2.4×` GPU batch-1 — which *does* clear the ≲3× bar.** So
   net-on-CPU is not dead in general, only at 1 thread. But 4 intra-op threads is precisely
   what the composability argument was trying to avoid: those are the cores G6's k-parallel
   split wants for search. **CPU-4t and k-parallel are competing for the same silicon**, so
   this is a genuine trade, not a free win, and it cannot be settled by a transport bench.
3. Batching still dominates throughput (`cuda_b32` = 1169 pos/s vs `cuda_b1` = 329 pos/s),
   which is the orchestrator's regime and unchanged by any of this — those rows are the
   contrast, not deploy numbers.

---

## 4. eff_linus — WSL2 vs native Windows — **the hypervisor tax is REFUTED, with the sign inverted**

`scripts/measurement_infra/wsl_vs_native_ab.sh`, full run: 3 reps × 2 arms × 4 cells = 24
cells, all `rc=0`. Artifacts:
`measurement/eff_linus/run_20260729/wsl_vs_native_ab_20260729_093612.json` (290 KB, 48 cell
files, 24 ndjson rows). **`audit.ab_valid: true`, zero failures** — the merger's own check
that the two arms differ *only* by virtualisation.

| cell | metric | WSL2 | native Windows | **ratio (win/wsl)** | spread wsl / win |
|---|---|---|---|---|---|
| `champ_k1x32` | p50 s/move | 0.1135 | 0.1429 | **1.259×** | 22.3 % / 1.1 % |
| `champ_k4x172` | p50 s/move | 2.7045 | 3.3829 | **1.251×** | 1.2 % / 1.4 % |
| `net_cuda_b1` | forward p50 ms | 2.1042 | 2.2305 | **1.060×** | 12.6 % / 0.6 % |
| `net_cpu_1t` | forward p50 ms | 11.2477 | 12.7901 | **1.137×** | 2.7 % / 0.4 % |

### Verdict — **NO tax. Both hypotheses die, and the effect runs the other way.**

* **H1 — the CPU/DRAM nested-paging tax** (predicted: WSL2 **5–20 % slower** on the
  pointer-chasing search, because a Hyper-V guest pays two-dimensional page walks).
  **Measured: WSL2 is `25 %` FASTER** (`1.251×` on the trustworthy `champ_k4x172` cell,
  `1.259×` on `k1x32`). Not merely absent — **the sign is inverted**, and the two
  independent champion cells agree to within 0.8 pp.
* **H2 — the GPU batch-1 `/dev/dxg` paravirtualisation tax** (predicted: WSL2 slower on
  exactly the batch-1 path G3 cares about). **Measured: WSL2 is `6 %` FASTER.** The
  smallest effect in the table, and still the wrong direction for the hypothesis.
* **The contended smoke was right about nothing but the direction it was told not to
  claim.** The staging smoke had shown native Windows slower by 1.03–1.19× and was
  explicitly flagged "n=1 on a loaded box, do not cite". Clean, at n=3 with alternating
  A/B/B/A ordering, that direction **holds and gets larger** (1.06–1.26×). The caution was
  correct procedure; the number it produced happened to survive.

**⇒ Nothing to reclaim here. WSL2 is not costing this project anything, so "move the
hot path to native Windows" is dead as a performance lever** — and the roadmap's third
forward-tax route (after the Pixel NPU and the Apple ANE) closes negative. That is a real
result: it removes an entire hypothesis class from G3 rather than deferring it.

**Free cross-validation.** The A/B's WSL arm re-measures the same two net cells as §3
through a *different* venv (`/home/doctor/carc-wsl-bench`, CPython 3.13) and a different
harness path, and reproduces them: `cuda_b1` **2.104 ms** here vs **2.017 ms** in §3;
`cpu_1t` **11.248 ms** vs **11.751 ms**. Two independent stacks agreeing within ~4 % is
much stronger evidence for the §3 verdict than either run alone.

### Caveats that bound this verdict

1. **Pure-Python leaf on BOTH arms** (`leaf_active: false`, asserted by the driver). The
   bundle ships Linux `.so`s and there is no Windows `.pyd`, so leaving Cython on would
   have compared a compiled leaf to an interpreted one and called the 4.5× difference
   "virtualisation". The **ratio** is the deliverable and it is honest; whether it survives
   under the Cython path is the **round-2 question, still blocked on MSVC Build Tools
   (needs admin — an open question for Joshua).**
2. `champ_k1x32`'s WSL spread is **22.3 %** — it is a 32-sim cell where startup noise
   dominates. `champ_k4x172` (spread 1.2 % / 1.4 %) is the cell to quote.
3. Interpreters are 3.13.**12** (WSL) vs 3.13.**14** (Windows) — same minor, a patch apart.
   The design pinned the minor deliberately; a patch difference is not plausibly worth 25 %.

### Disk reclaim (pre-agreed, executed after results were on disk)

`C:\Users\Doctor\carc-win-bench\.venv` deleted via `powershell.exe Remove-Item -Recurse
-Force`; the directory is confirmed empty (0 bytes). This was done **only after** the
merged JSON, all 48 cell files and the ndjson were verified on disk — note it makes the
`win` arm non-reproducible without re-provisioning (recipe is in the script header).

> **C: free space: `12.95 GiB`** (Windows `Get-PSDrive`, authoritative), up from `12 G` as
> `df -h` reported before.
>
> ⚠️ **Honest caveat: the observed gain is smaller than the 4.4 GiB the venv `du`'d at.** I
> did not capture a byte-precise "before" (only `df -h`'s rounded `12G`), and C: is a live
> Windows volume with Defender, the page file and updates writing to it throughout a
> ~1 h window, so a clean attribution is not available. What is verified: the venv
> directory is gone, and C: is no longer under the ~12 GiB it was at. The A/B's own staging
> onto C: is only 5.9 MB and does not explain the gap.

---

## 5. Clean 5900XT single-stream reference — **the M5 is `1.74×`, not `2.85×`**

The M5 read-out recorded a debt in as many words: *"A quiet-window 5900XT rerun of the same
bundle is owed, and until it lands the honest statement is 'the M5 is somewhere up to
~2.85× faster than a **contended** 5900XT at k1×32', not 'the M5 is 2.85× a 5900XT'."*
This pays it.

Same bundle, same `positions.jsonl` (60 positions, md5 `e36c4d2a…`), same `--repeat 3`,
same `seed 101`, same four budgets, **`leaf path: CYTHON`** — and critically the same
**CPython 3.13.12** the earlier local rows used. Artifact:
`measurement/m5_bench_20260728/bench_champion_5900XT_CLEAN_20260729.json`
(`loadavg` 1.16 / 1.11 / 1.42 at capture; `n=178` decisions per rung on both boxes).

| budget | sims/move | **5900XT (clean)** | Apple M5 (idle) | **ratio M5-favour** |
|---|---|---|---|---|
| k1×32 | 32 | 0.024521 | 0.013526 | **1.813×** |
| k4×172 | 688 | 0.664817 | 0.370452 | **1.795×** |
| k4×344 | 1376 | 1.374647 | 0.793738 | **1.732×** |
| **k4×688 (deploy)** | **2752** | **2.746945** | **1.575565** | **1.743×** |

### Verdict — **the M5 is ~1.74× a clean 5900XT at the deploy budget**

* **The `2.85×` figure was `1.57×` contention.** At the identical k1×32 rung the contended
  local grand mean was `0.0386 s/move`; clean it is `0.024521`. The gate's 16 workers were
  inflating the denominator by **1.57×**, and essentially all of the gap between `2.85×`
  and the true `1.81×` is that artifact. **The M5 read-out's warning not to quote `2.85×`
  bare was correct, and the corrected number should replace it.**
* **The ratio is flat across an 86× range of sims** (1.813 → 1.795 → 1.732 → 1.743). That
  flatness is the quality signal: a single contended cell can produce any ratio, but four
  rungs agreeing within ±2.5 pp across two orders of magnitude of work is a real
  architectural constant, not a measurement.
* **The k4×688 comparison now exists at all** — the M5 read-out recorded that it "does not
  exist" and that the run book's `~3.4 s/move` for the loaded 5900XT was an *extrapolation
  from the k1×32 rung, not a measurement*. Measured clean: **2.747 s/move**. So the
  extrapolation was ~24 % high, and it was extrapolating from a contaminated base.
* **A fanless MacBook Air is ~1.74× a 16-core desktop on single-stream champion latency.**
  That is a smaller, more defensible claim than the one on record, and it is still a
  striking one.

⚠️ **Do not cross-quote this against §2.** The k-parallel bench measures `3.228 s/move`
sequential at the same k4×688 budget, against `2.747` here. Both are correct: they use
**different position slices** (§2 replays real mid-game roots at ply 0.35–0.70, which carry
more placed meeples and therefore cost more per leaf; §5 uses the 60-position bundle
spanning the whole game). Ratios *within* a section are comparable; absolute s/move
*across* sections is not.

### Re-run of the contended torch batch-1 GPU forward

Covered by §3 rather than re-measured separately, as instructed: **`cuda_b1` forward is
`1.975`/`2.017 ms` clean, against the `19.4 ms` taken on a loaded box — a `9.7×`
overstatement.** Same lesson as the 2.85×, one order of magnitude louder.

---

## 6. What this batch changed, and what it did not

**Two numbers this project has been reasoning from were contention artifacts**, and both
moved in the same direction — the box was slower than we thought it was, so the *hardware*
looked worse than it is:

| number on record | measured clean | overstatement |
|---|---|---|
| GPU batch-1 forward `19.4 ms` | **`2.0 ms`** | **9.7×** |
| M5 vs 5900XT `2.85×` (k1×32) | **`1.81×`** | 1.57× |
| 5900XT k4×688 `~3.4 s/move` (extrapolated) | **`2.747 s/move`** | 1.24× |

The common cause is the CL-067 gate's 16 spawn workers. **The standing lesson — "every cost
ratio in this project has moved when re-probed unloaded" — held for a third time**, and the
harnesses that recorded their own `loadavg` are the reason we can prove it rather than
suspect it.

**One lever opened, two closed:**

* **G6 k-parallel — OPENED.** 3.16× at deploy, 6.37× at k8×1376, behavior-identical on all
  30 roots, transport negligible. The clock closure that CL-068 decided under a
  single-stream assumption is genuinely reopened.
* **G3 net-on-CPU — CLOSED at 1 thread** (5.8× vs a ≲3× bar). Left ajar at 4 threads
  (2.4×), but those threads are the ones k-parallel wants.
* **eff_linus hypervisor tax — CLOSED NEGATIVE.** Not "no effect": the effect runs
  backwards by 25%. Third forward-tax route to close, after the Pixel NPU and the ANE.

**What this batch cannot support.** Every cell here is latency. Nothing measures strength,
no elo moved, and "k8×1376 is now tournament-legal" is a *clock* statement — CL-060's
+49.9 for that configuration was graded by a ruler CL-070 showed to be ~70 elo unreliable
on exactly this contrast. Cheap ≠ strong.

## 7. Provenance and honesty notes

* **Wall-clock:** ~2 h 05 m end to end (first census 12:38Z → last artifact 14:30Z),
  including a full re-run of §2 after a session restart and a second run of §3.
* **Every number above is read off a committed JSON/manifest**, not from console
  scrollback. The one place scrollback existed (the killed §2 run) was **discarded**.
* **Contention disclosure.** The batch was promised an exclusive box. It did not get one:
  another agent's `pytest tests/` ran from 12:54Z for >1 h at ~1 core of 32.
  * **§2 (k-parallel) is clean** — it finished at 12:50:48Z, before that pytest started.
  * **§3 was affected**, so it was **run twice**, at `loadavg` 3.85 and 1.19. The two
    decision rows agree within **2%**, which bounds the contention effect and is why the
    §3 verdict stands.
  * **§4 and §5** ran with that ~1-core load present (`loadavg` ~1.2–2.1, recorded in each
    artifact). §4 is an alternating A/B, so a constant background load largely cancels in
    the ratio; §5's ratio is flat across four rungs, which a varying contention would not
    produce. Neither is as clean as §2, and that is stated rather than smoothed.
* **`§4`'s `win` arm is no longer reproducible** without re-provisioning the deleted venv.
* **Not touched, by instruction:** `STATUS.md`, `DECISIONS.md`, the roadmap, `results.csv`,
  `governance/`. The main session owns close-out. The only doc edits here are this file and
  its `docs/INDEX.md` row.
