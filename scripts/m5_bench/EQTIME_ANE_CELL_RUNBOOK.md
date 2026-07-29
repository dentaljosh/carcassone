# EQTIME/ANE CELL — runbook for the one M5 cell that reopens (or closes) the distilled line

**STATUS: BUILT, NOT RUN. The forward path exists and is contract-tested; nothing on the
Air has been executed. This cell needs Joshua's go and a free M5 (the Air is on the cliff
rung).** Nothing here writes to `governance/`, `experiments/results.csv`, or
`measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md`.

## Why this cell exists

The equal-wall-clock gate
([`../../measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md`](../../measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md))
fired pre-registered **branch C (WASH)**: at a measured cost ratio of 1.00 the distilled
net-priors agent scored **−17.4 ± 17.4 elo** against the deploy champion, and the +35.7
it wins at equal SIMS is bought back in full by the clock. That verdict is about **one
forward path** — batch-1 CUDA through carc-orch, where a forward costs ~3× the simulation
it guides. §6 of that read-out fixed the reopen condition in advance:

> REOPEN the distilled-net line for deploy when the target device's measured
> `r = forward_ms / search_ms_per_sim` is ≤ ~1.5.

The ANE is the only measured path that clears it (**0.42 ms batch-1 fp16, r ≈ 0.73**,
projecting **+11 to +15 elo at equal wall clock**). §6 caveat 1 says exactly what is owed:

> It is a projection, not a measurement of an agent. … The honest next test is one direct
> run — the netprior agent on the M5 at its own equal-time budget (~k4×397 = 1589 sims)
> vs the champion — which would settle it in a single cell.

**This is that cell.** It is also the cell that would KILL the line for good: §7 says an
M5/ANE cell at genuine equal wall clock that still comes back negative means the
equal-sims edge survives no realistic cost model, and the distilled policy becomes a
Phase-5 analyzer asset rather than a deploy asset.

---

## 0. Preconditions — all four, before any game is played

| # | gate | how |
|---|---|---|
| 0a | repo synced to the Air, **Cython leaf built** | §1 |
| 0b | `.mlpackage` exported + sidecar manifest written | §1.3 |
| 0c | **`verify_coreml_evaluator.py` PASS** on ≥60 real positions | §1.4 |
| 0d | budget derived from a **fresh on-Air probe**, not from this document's numbers | §2 |

⚠️ **0a is not a formality.** `r` is a RATIO. If the Cython leaf fails to build, the
search runs ~4.5× slower in pure Python, `search_ms_per_sim` inflates, and `r` *falls* —
which **flatters the ANE** and hands the candidate a budget it has not earned. A broken
build makes this cell look better, not worse, which is the most dangerous direction for a
failure to point. `bench_champion.py` reports `cython.leaf_active`; it must be `true`.

---

## 1. Setup on the Air

### 1.1 Sync

The M5 has **no share mount** (memory `reference_m5_access`) — rsync only. Unlike the
`m5_bench` bundle, this cell runs the **real harness** (`eval_fair_puct.py`), because only
the real harness produces the protocol-compliant output the verdict needs: per-game JSON
records, deck-paired seats, a `manifest.json`, and the in-flight cost-ratio guard.

```bash
rsync -a --info=progress2 \
    --exclude '.venv/' --exclude '.git/' --exclude '__pycache__/' \
    --exclude '*.so' --exclude '*.c' --exclude 'checkpoints/' \
    /home/doctor/projects/carcassone/ \
    joshuaishal@100.64.175.108:~/carc-eqtime-ane/repo/

rsync -a /mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt \
    joshuaishal@100.64.175.108:~/carc-eqtime-ane/iter_03.pt
```

`--exclude '*.so' --exclude '*.c'` is mandatory for the same reason `README_M5.md` gives:
a Linux x86-64 `.so` on an arm64 Mac fails to load while every label still says "built".

### 1.2 Venv + Cython

Per the "Claude Code drops `cd` in SSH" rule, everything below is either absolute or
piped as a script. Write this to `/tmp/setup_ane.sh` and pipe it:

```bash
ssh joshuaishal@100.64.175.108 'bash -s' < /tmp/setup_ane.sh
```

```bash
#!/bin/bash
cd ~/carc-eqtime-ane/repo || exit 1
set -e
python3.12 -m venv ~/carc-eqtime-ane/.venv
~/carc-eqtime-ane/.venv/bin/pip install -U pip
~/carc-eqtime-ane/.venv/bin/pip install numpy pyyaml cython torch coremltools
# The repo builds the two Cython extensions from SEPARATE setup files (the bundle's
# single generated setup_cy.py does not exist in a full-repo checkout).
~/carc-eqtime-ane/.venv/bin/python setup_flat_leaf_cy.py build_ext --inplace
~/carc-eqtime-ane/.venv/bin/python setup_flat_repr_cy.py build_ext --inplace
~/carc-eqtime-ane/.venv/bin/pip install -e .
~/carc-eqtime-ane/.venv/bin/python -c "
import carcassonne_ai; print('pkg', carcassonne_ai.__file__)
from carcassonne_ai import flat_leaf_cy, flat_repr_cy; print('cython ext OK')"
```

If the extension build fails for want of a compiler: `xcode-select --install`, then
re-run. **Do not proceed on a failed build** — see §0.

Then PROVE the Cython leaf and get the champion's own s/move in one shot (§2 needs it):

```bash
ssh joshuaishal@100.64.175.108 \
  '~/carc-eqtime-ane/.venv/bin/python ~/carc-eqtime-ane/repo/scripts/m5_bench/bench_champion.py \
     --bundle ~/m5_bench_20260728/bundle --budgets k4x688 --limit 12'
```

**Read `cython.leaf_active` off the output. If it is false, STOP and fix the build** — see
the warning in §0.

### 1.3 Export the model

Runs on either box (conversion is cross-platform; only `predict` is Darwin-only). Doing it
on the Air is simpler and gives a free reload+predict check:

```bash
ssh joshuaishal@100.64.175.108 \
  '~/carc-eqtime-ane/.venv/bin/python ~/carc-eqtime-ane/repo/scripts/m5_bench/export_cl067_coreml.py \
     --checkpoint ~/carc-eqtime-ane/iter_03.pt \
     --out-dir ~/carc-eqtime-ane/coreml'
```

Produces `cl067_iter03_policy_fp16.mlpackage` + `.manifest.json`. **Check the sidecar's
`source_checkpoint.sha256` starts `6e2679908d79a76c`** — the checkpoint of record from the
gate read-out's configuration table. The sidecar also carries the converter versions and
the `amax`→`max_pool2d` equivalence result (asserted bit-identical before export).

### 1.4 The fidelity gate — this is what the cell cites

```bash
ssh joshuaishal@100.64.175.108 \
  '~/carc-eqtime-ane/.venv/bin/python ~/carc-eqtime-ane/repo/scripts/m5_bench/verify_coreml_evaluator.py \
     --checkpoint ~/carc-eqtime-ane/iter_03.pt \
     --model ~/carc-eqtime-ane/coreml/cl067_iter03_policy_fp16.mlpackage \
     --positions ~/m5_bench_20260728/bundle/positions.jsonl \
     --out ~/carc-eqtime-ane/verify_coreml.json'
```

Acceptance (exit 0): legal-argmax agreement ≥ 0.98, mean top-5 overlap ≥ 0.95, policy
max-abs ≤ 5e-3, over ≥60 positions the champion actually reached.

**A FAIL is informative, not fatal.** It does not kill the line; it changes the CLAIM. A
passing verify licenses "the same agent on a cheaper forward". A failing one means the ANE
agent must be named as a **distinct player** in the read-out, and the cell measures that
player's strength rather than a pure cost intervention. Decide which claim you are making
BEFORE launching, and write it into the pre-registration.

Also record `latency_batch1.coreml_CPU_AND_NE.mean_ms` from the JSON — §2 divides by it.

---

## 2. The budget — MEASURE it, do not divide

The gate's ops note 1 is explicit: the 26-minute probe was worth it, and arithmetic alone
would have mis-set the laptop by 39%. Two independent derivations, and they must agree.

### 2.1 The r-model (picks the trial sims)

```
r                    = forward_ms / search_ms_per_sim
search_ms_per_sim    = champion_ms_per_move / 2752          # k4×688 = 2752 total sims
equal_time_total_sims = 2752 / (1 + r)
candidate sims/det   = round(equal_time_total_sims / 4)     # k_dets held at 4
```

Both inputs come from §1: `champion_ms_per_move` from `bench_champion.py --budgets k4x688`
(§1.2) and `forward_ms` from `verify_coreml_evaluator.py`'s latency block (§1.4).

### MEASURED ON THE AIR 2026-07-29 — use these, not the projection

| | gate §6 projection | **MEASURED (W6, paired probe)** |
|---|---|---|
| champion search ms/sim | 0.5741 | **1.0036** |
| ANE forward ms (single-stream) | 0.420 | **0.427** |
| candidate ms/sim | — | **1.5595** |
| per-sim cost multiple cand/opp | — | **1.554×** (CUDA was 4.2–5.5×) |
| **equal-time budget** | k4×397 | **k4×438** |
| measured cost ratio at that budget | — | **0.9893** → guard **PASS** |

Two things that projection got wrong, both worth carrying forward:

* **Champion search is 1.75× slower than projected** (1.0036 vs 0.5741 ms/sim). The 0.5741
  came from a *single-stream* `bench_champion` run; the cell runs **W6**, and six workers
  on a 10-core M5 contend. Search cost is a function of W.
* **Therefore do NOT compute r from the single-stream forward.** r = 0.427/1.0036 = 0.436
  looks like it licenses k4×479 — but that divides an *uncontended* forward by a
  *contended* search, and under W6 six processes serialise on the ONE shared ANE, so the
  effective forward is not 0.427 ms. The **direct paired ratio already contains every
  contention effect**; scale off it. Measured: k4×395 → 0.9014 (in-band but hugging the
  floor, candidate short-changed 10%); k4×438 → **0.9893**.

The gate's §6 projection, for reference **only** — these are the numbers to REPLACE, not
to reuse:

| | projected (gate §6) |
|---|---|
| search ms/sim | 0.5741 (= 1.58 s/move ÷ 2752) |
| ANE forward ms | 0.420 |
| **r** | **0.73** |
| equal-time total sims | 1589 |
| **candidate budget** | **k4×397** |

⚠️ Note what `forward_ms` must and must not include. The r-model charges the ENCODE and
the host-side masked softmax to the SEARCH, not to the forward — the torch backend pays
them identically, so they cancel. `verify_coreml_evaluator.py` times the raw `predict`
precisely for this reason. Do not substitute an end-to-end evaluator timing.

### 2.2 The direct probe (decides it)

Run a short paired cell at the trial sims and read the **measured** prefix ms/move ratio.
Same accept rule the gate pre-registered: **the ratio must land in [0.90, 1.10]**, else
adjust sims and re-probe.

```bash
# scratch band 99.5e9 (the gate's probe band — never a verdict band)
CAND=397   # <- from §2.1, on the day
~/carc-eqtime-ane/.venv/bin/python ~/carc-eqtime-ane/repo/scripts/classical_search/eval_fair_puct.py \
    --info fair-netprior --opponent fair-champion \
    --net ~/carc-eqtime-ane/iter_03.pt \
    --net-backend coreml \
    --coreml-model ~/carc-eqtime-ane/coreml/cl067_iter03_policy_fp16.mlpackage \
    --coreml-compute-units CPU_AND_NE \
    --exact-k 2 --k-dets 4 --sims "$CAND" --opp-k-dets 4 --opp-sims 688 \
    --batch-size 1 \
    --n 32 --paired --seed-start 99500000000 \
    --workers "$W" \
    --out-root ~/carc-eqtime-ane/out --out-subdir probe_k4x${CAND} \
    --no-results-csv
```

Read `champ_prefix_ms_per_move` (= the **CANDIDATE**) against `rung_ms_per_move` (= the
**OPPONENT**) from `summary.json` — the field semantics are inverted relative to the names
and were taken from the emitter, `eval_fair_puct.py` lines ~1606-1619 (gate read-out
Appendix). The harness also prints the ratio directly.

### 2.3 Choosing `W`, and why it is load-bearing

The gate's ops note 4: *"W16 was load-bearing and must not be 'optimised'. The sims choice
is only valid in the regime it was probed in."* That applies with extra force here, for a
reason the CUDA cell did not have: **the ANE is a single shared device that serialises
requests across processes.** W workers do NOT give W× the forward throughput, so `r` — and
therefore the equal-time budget — is a function of W in a way it was not on the GPU.

- Pick W once (the M5 is 10-core; W ≈ 4-6 is the sane starting bracket, `w_ladder.py` can
  bracket it), and **use the identical W in §2.2 and §3.**
- Do not raise W mid-run. It invalidates the sims choice.
- Pin W explicitly in the launch command and in any watchdog relaunch line.

---

## 3. The cell

**Pre-register before launching** (the gate's pre-registration landed in `df93dcc` BEFORE
any result existed — hold that standard): the band, W, `CAND` sims, the claim being made
(§1.4), and the branch table. Reuse the gate's four branches verbatim — A/B fund the line,
C is a wash, D kills it — so the two cells are directly comparable.

**Band:** claim a fresh, previously-unburned band the way the gate did — enumerate
`/mnt/c/carc-shared/BAND_CLAIMS.txt` **plus every share `manifest.json` with
`seed_start >= 60e9`** (the ledger alone is not sufficient; the gate cross-checked both),
then append the claim to `BAND_CLAIMS.txt` **before** launching. Burned as of the gate:
60/62/64/66/68/70/72/74/76/78/80/**82**/**84**/90/91/99e9, plus 52e9/56e9 (the CL-067
equal-sims cells). 99.5e9 is the scratch probe band and is not a verdict band.

⚠️ The M5 has no share mount. Do the band enumeration and the claim **from a box that can
see `/mnt/c/carc-shared`**, then carry the chosen band over as `BAND=` — do not skip the
claim because the run happens elsewhere.

```bash
#!/bin/bash
# /tmp/eqtime_ane_cell.sh — pipe with: ssh joshuaishal@100.64.175.108 'bash -s' < /tmp/eqtime_ane_cell.sh
cd ~/carc-eqtime-ane/repo || exit 1
# MEASURED + STAGED 2026-07-29 (see §2): k4x438 gives a cost ratio of 0.9893, and band
# 92e9 is verified unburned (ledger + 612 share manifests) and already claimed in
# /mnt/c/carc-shared/BAND_CLAIMS.txt. Override only if you re-probe.
CAND="${CAND:-438}"
BAND="${BAND:-92000000000}"
W="${W:-6}"          # the W the ratio was measured at — changing it invalidates CAND
VENV=~/carc-eqtime-ane/.venv/bin/python

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1 CUDA_VISIBLE_DEVICES="" \
nohup nice -n 19 "$VENV" scripts/classical_search/eval_fair_puct.py \
    --info fair-netprior --opponent fair-champion \
    --net ~/carc-eqtime-ane/iter_03.pt \
    --net-backend coreml \
    --coreml-model ~/carc-eqtime-ane/coreml/cl067_iter03_policy_fp16.mlpackage \
    --coreml-compute-units CPU_AND_NE \
    --exact-k 2 --k-dets 4 --sims "$CAND" --opp-k-dets 4 --opp-sims 688 \
    --batch-size 1 \
    --n 400 --paired --seed-start "$BAND" \
    --workers "$W" \
    --out-root ~/carc-eqtime-ane/out \
    --out-subdir "eqtime_ane_netprior_k4x${CAND}_vs_deploy_b${BAND}" \
    --no-results-csv \
    > ~/carc-eqtime-ane/eqtime_ane_cell.log 2>&1 &
disown
echo "launched pid $!"
```

### Flags that are not negotiable, and why

| flag | why |
|---|---|
| `--net-backend coreml` + `--coreml-model` | the whole point. Without it the run is a torch-CPU cell (`r ≈ 4.5`, already known bad). |
| `--coreml-compute-units CPU_AND_NE` | `ALL` lets CoreML place the graph on the GPU — a **different device** from the one 0.42 ms was measured on. |
| `--batch-size 1` | the artifact is fixed batch-1; `batch_size>1` would engage virtual loss and change the search for zero transport win. The harness `ap.error`s on it, and the batch evaluator raises. **Do not copy `--batch-size 6` off the CUDA gate's command line.** |
| `--net` still required | it anchors the encode rep (81ch/42 sighted, inferred from the checkpoint) and the manifest provenance. In coreml mode it is read once in `main()` and never loaded in a worker. |
| `--opp-sims 688 --opp-k-dets 4` | the deploy champion of `governance/PRODUCTION.yaml`, unchanged from the gate. |
| `--exact-k 2` | marginalized endgame, identical on both sides, excluded from the prefix ms/move the cost guard reads. |
| no `--orch-shm-name` | there is no carc-orch on the Air, and it is a different transport; the harness rejects the combination. |
| `--paired` | deck pairing halves variance (n=400 paired ≈ ±12 elo). Non-negotiable at this effect size. |
| `--no-results-csv` | the six-touch close-out lands the row deliberately, not as a run side effect. |

⚠️ **Detach.** Joshua's Mac→Windows→WSL path means an ssh drop kills a tty-attached job;
`nohup … & disown` above is the minimum. For an overnight run also arm the on-disk
`scripts/measurement_infra/run_watchdog.sh` keyed on **record count** — the gate's ops note
7 found `fair_net_vs_net_orch.sh` exits `rc=1` on a fully SUCCESSFUL run and its sibling
exits `rc=0` after a fatal error. **Do not read success off an exit code; count the
records.** (This cell calls `eval_fair_puct.py` directly rather than through that wrapper,
so the specific `rc=1` bug does not apply — but the discipline does.)

---

## 4. Read-out

Report **both** statistics, as the gate did — a single number is not a verdict here.

1. **Winrate elo** ± 1σ and its z. At n=400 paired, 1σ ≈ ±17 elo unpaired / ≈ ±12 paired.
2. **Deck-paired margin** in pts/deck, its se, and its paired z over 200 decks.
3. **The cost-ratio guard**: candidate vs opponent prefix ms/move. If it is outside
   [0.90, 1.10] the cell is **not** equal-time and the elo cannot be read as an
   equal-clock number — say so rather than quietly reporting it.
4. **Integrity counters**: deck_hash mismatches (want 0/200), timeouts (0/0), endgame
   latches (400/400 both sides), and both sides' leaf hash = `a36d2e15a3b3d71d`.
   The backend stamp is at **`manifest.json` → `config.champion.net_backend`** —
   `run_manifest.write_manifest` nests the harness dict under `config`, so a read of
   `champion.net_backend` returns nothing and looks like a missing stamp (cost me a
   diagnostic on 2026-07-29). Per-game records carry `champ_prefix_secs` /
   `champ_prefix_moves` and `opp_prefix_secs` / `opp_prefix_moves` — there is no
   `*_ms_per_move` field in a record; compute it as `secs/moves*1000`.
5. **The measured `r`** on the day, next to the gate's projected 0.73 — this is the number
   §6's reopen condition is actually stated in, and the first thing a later reader wants.

Then the **six-touch close-out** (CLAUDE.md): results.csv row → DECISIONS index line →
status stamp on this doc → governance row (CL-067 in `CLAIM_REGISTRY.csv`) → STATUS top
block → roadmap line, then `python3 scripts/doc_lint.py`.

### Interpreting it

- **Positive, both statistics ≥ 2σ** → the reopen condition is not just met on paper; the
  binding constraint really was the forward, and G3 unparks as *"get the forward onto a
  cheap accelerator"* rather than its original *"batch the k determinizations"* scope.
- **Wash** → the r-model is directionally right but the slope is optimistic. Note that the
  slope carries the gate's own cross-band caveat (§5.2) and that 1589 sims is
  *interpolation* inside the fitted range, so a wash here is a fair test of the model, not
  a hardware failure.
- **Negative at genuine equal clock** → §7's kill condition. The equal-sims edge survives
  no realistic cost model; the distilled policy becomes a Phase-5 analyzer asset. Say that
  plainly — it is a real, publishable result and it closes an open line.

---

## 5. Known risks, stated before the run

1. **Interleaving contention is unmodelled.** The 1.58 s/move search and the 0.42 ms
   forward were measured *separately*. A real agent alternates them ~1589 times per move;
   ANE wakeups, CPU contention and memory bandwidth may make the combination worse than
   the sum. §2.2's direct probe is what catches this — it measures the combination.
2. **Per-process model load.** Each worker loads its own `MLModel`. First-predict
   compilation latency is paid per worker, and the ANE serialises across them. The §2.2
   probe must run at the SAME W as the cell or the budget is wrong.
3. **fp16 is not the torch player.** Even a passing §1.4 verify allows a small fraction of
   reordered near-ties. At 2511 actions and ~1589 sims/move that is a real, if tiny, search
   perturbation. It is why the manifest stamp says "NOT behaviour-identical".
4. **Thermals.** The Air is fanless. A 400-game run will throttle; the champion side
   throttles too, so the RATIO is partly self-correcting, but a long run's late games are
   not the same clock as its early ones. Prefer running when the box is cool, and check
   whether ms/move drifts across the run.
5. **`r` is W-dependent here.** See §2.3. This is the single most likely way to get a
   budget that is quietly wrong.
