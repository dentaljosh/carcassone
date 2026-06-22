# Deepteacher checkpoint-provenance audit (2026-06-17)

**Scope:** resolve, by hashes and runtime artifacts (not eval scores), what the deepteacher
run actually warm-started from and what its sealed/washout baseline actually was. Companion:
[DEEPTEACHER_LINEAGE.csv](DEEPTEACHER_LINEAGE.csv).

---

## VERDICT

**Confirmed warm-start from iter8 (the production champion).** The full per-iteration
parent-hash chain descends cleanly from champion-iter8 with **no silent fallback to
`residual.pt` anywhere in the warm chain.**

**BUT a load-bearing baseline defect:** the run's **sealed and washout "iter0" baselines
were `residual.pt`, NOT iter8** (hash-confirmed from the eval manifests). The published
deepteacher deltas therefore measure **iter12 − residual.pt**, not iter12 − iter8. The
experiment's own question — *did iterating a deep teacher from iter8 beat iter8?* — was
**never measured at the verdict (s800) plane.**

Consequence: neither "deeper teacher failed" nor "deeper teacher worked" is supported by the
sealed/washout numbers. Existing independent-band data (below) actually leans **positive** at
the deep plane (iter2 +53.7/z2.14, iter9 +35.6/z1.21 vs champion-iter8 @s800), but iter12@s800
vs iter8 is the missing cell → Phase 2.

---

## 1. The two checkpoints at issue (hashes)

| id | path | sha256 |
|---|---|---|
| champion iter8 (warm-from) | `flywheel_residual_attempt2/ckpt/iter8.pt` | `0d355002e26a968e913396858aa51b52c95a1903db324c4fbab6849cc279ee2c` |
| residual.pt (baseline used) | `lever_seq/ckpt/residual.pt` | `f1e67cab8a8808184c763c21a8dda7d83fa52b6fa66de5847386166b833b3770` |
| dt iter12 = best.pt (champion of run) | `deepteacher/ckpt/iter12.pt` = `deepteacher/best.pt` | `059e394cb0a2e1e6bf8c5f04bef2e7eb1f3ea8806fccd9819b8ab0aaa55f7d0c` |
| warm.pt (last staged warm) | `deepteacher/warm.pt` | `11872ad3c59e856de39be02a1b15ee171d8a764da719f019f482a2566f8aebbc` (= dt iter10) |

Note `deepteacher/ckpt/iter0.pt` **does not exist** — "iter0" is not a file; it is (a) `best.pt`
initialized by `cp $ITER0_CKPT best.pt`, and (b) the sealed eval target `$ITER0_CKPT`.

## 2. Required determinations (each answered from a runtime artifact)

| Question | Answer | Evidence (artifact) |
|---|---|---|
| SHA of `ITER0_CKPT`-specified ckpt | **Segment-dependent.** iter1-segment: iter8 `0d355002`. Final (iters10-12) segment: residual.pt `f1e67cab` (the launcher default, line 89). | spec launch cmd `docs/DEEPER_TEACHER_SPEC_2026-06-11.md:102`; sealed manifest (below) |
| SHA actually loaded at iter1 | **iter8 `0d355002`** | `deepteacher/ckpt/iter1.metrics.json:provenance.parent_ckpt.sha256` |
| SHA of `deepteacher/ckpt/iter0.pt` | **N/A — file does not exist** | `ls deepteacher/ckpt/` (iter1..iter12 only) |
| Ckpt that generated iteration-1 self-play | **iter8 `0d355002`** (gen used `WARM=$OUT/warm.pt` = copy of `best.pt` = copy of `$ITER0_CKPT`=iter8) | iter1 metrics parent_ckpt; launcher `_gen_launch` |
| Did best.pt / symlinks / copy / fallback silently resolve to residual? | **Warm chain: NO** (all 12 parents trace to iter8). **Sealed/washout baseline: YES** (`$ITER0_CKPT` defaulted to residual in the resume segment). | lineage CSV; sealed/washout manifests |
| Exact live launcher args/env | Reconstructed from artifacts (shell history not preserved — grep returned nothing). iter1 seg: `ITER0_CKPT=…/iter8.pt FLYWHEEL_TAG=deepteacher SIMS=800`. Final seg banner: `TAG=deepteacher ITERS=10..12 SCALE=0.25 GAMES=400` (no ITER0_CKPT → default residual). | `/tmp/flywheel2.log:1`, `/tmp/flywheel_resume.log:1`; metrics `train_command` |
| Parent hash of every dt checkpoint | Full chain verified (see §3 + CSV) | each `iterN.metrics.json:parent_ckpt.sha256`, cross-checked against `sha256sum` of every `iterN.pt` |
| Do manifests suffice to verify independently? | **Yes** — `metrics.json:parent_ckpt{path,sha256}` + eval `manifest.json:evaluator.sides[].checkpoint_sha256` give hash-level provenance. (Caveat: the eval manifest's *top-level* `checkpoint/sims` fields are null; only the `evaluator.sides` block is populated — a schema-completeness gap, not a correctness one.) | the json files |

## 3. Warm-chain integrity (all parent hashes verified)

Every `iterN.pt` SHA was computed with `sha256sum` and matched against the `parent_ckpt.sha256`
recorded by the **next** iteration's metrics:

```
champion_iter8(0d355002) ─┬─► iter1 (cc6109d9, not promoted)
                          └─► iter2 (3cbaad8a, PROMOTED)
iter2(3cbaad8a) ──────────┬─► iter3 (332bd789, rej)
                          ├─► iter4 (1e4ffafd, rej)
                          ├─► iter5 (ed5d7274, rej)
                          └─► iter6 (398917783a, PROMOTED)
iter6(398917783a) ───────────► iter7 (62b95f21, PROMOTED)
iter7(62b95f21) ─────────────► iter8dt (ffb67f57, PROMOTED)   ← NOT champion iter8
iter8dt(ffb67f57) ───────────► iter9 (5f6ac3fc, PROMOTED)
iter9(5f6ac3fc) ─────────────► iter10 (11872ad3, PROMOTED)
iter10(11872ad3) ─────────┬─► iter11 (3a414284, rej)
                          └─► iter12 (059e394c, PROMOTED) == best.pt == champion-of-run
```

No node's parent is `residual.pt`. **Warm-start lineage = iter8-rooted, intact across all
resume segments** (resume reads `best.pt`, which is never re-initialized from `$ITER0_CKPT`).

⚠️ **Naming collision:** `deepteacher/ckpt/iter8.pt` (`ffb67f57`, the run's own 8th iter) is a
*different file* from the production champion `iter8` (`0d355002`). `selection.csv` "best=iter8"
rows refer to the former. Do not conflate.

## 4. The baseline defect (the load-bearing finding)

The sealed confirmation (`run_residual_flywheel_v2.sh:327`) and the manual washout both
evaluate **`$ITER0_CKPT`** as the "iter0" baseline. In the final segment `$ITER0_CKPT` defaulted
to `residual.pt`. Manifest evidence (`evaluator.sides[0].checkpoint_sha256`):

| eval dir | "iter0" ckpt resolved to | sha | plane |
|---|---|---|---|
| `deepteacher/odo/sealed_iter0` | **residual.pt** | `f1e67cab` | s800 |
| `deepteacher/odo/s200_iter0` | **residual.pt** | `f1e67cab` | s200 |

So the headline numbers are **iter12 − residual.pt**, recorded in `experiments/results.csv`:
- `deepteacher_SEALED_*` → Δ(iter12−residual) = **+8.1 / z0.34** @s800 ("tie")
- `deepteacher_WASHOUT_*` → Δ(iter12−residual) = **+82.8 / z3.48** @s200 ("washout")

Both are valid as iter12-vs-residual, but **they do not answer "did the deep teacher beat its
warm-from iter8."** The +82.8 is inflated because residual.pt is unusually weak at s200 (−8.7)
while iter8 is +58.7 there.

## 5. What existing data DOES say about dt-vs-iter8 (independent bands; hash-verified)

| dt candidate | vs | plane | band | n (paired) | Δelo | z | source |
|---|---|---|---|---|---|---|---|
| iter2 | champion-iter8 | s800 | 1.3e9 | 400 | **+53.7** | 2.14 | `confirm_iter2/iter8` manifests (iter2=`3cbaad8a`, iter8=`0d355002`) |
| iter9 | champion-iter8 | s800 | 1.6e9 | 134* | **+35.6** | 1.21 | `sealed_interim/sealed9_{base,champ}` (base=`0d355002`, champ=`5f6ac3fc`) |
| iter12 | champion-iter8 | s800 | — | — | **UNMEASURED** | — | (the gap Phase 2 fills) |
| iter12 | champion-iter8 | s200 | 1.7e9 (spent) | 400 | **+15.3** | 0.68 | re-tally of `attempt2/sealed_champ`(iter8) × `deepteacher/s200_champ`(iter12), common decks |

*sealed9 dropped 2 seat-imbalanced strands → 134 common decks, underpowered.

**Reading (interpretation, not raw):** the deep-plane signals vs iter8 are positive but
band-scattered; iter12@s800 specifically is missing. This is consistent with — but does not
prove — a real deep-plane gain over iter8. A clean fresh-band paired iter8-vs-iter12 at both
planes is required. **Do not promote iter12 on this.**

## 6. Code-provenance caveat

All 12 iters ran with `dirty=True` and the `code_commit` advanced across the run
(`fdc5ff7`→`954bb63`→`b989fa6`→`05f4c93`→`a276ab2`→`2e7b4b8`→`5640a24`→`d3a19e6`→`5cb58f1`).
The leaf/encode code changed under the run. Bit-exactness of the flat/cython leaf was asserted
elsewhere, but the lineage is not single-commit. Flag, not invalidate.

## 7. Missing evidence

None material. Shell history for the launches was **not preserved** (history grep empty), so the
exact argv is *reconstructed* from log banners + metrics `train_command` + manifests rather than
read from a command line — but those artifacts are hash-level and mutually consistent, so the
provenance is fully resolved without it.

## 8. Documents/claims to correct (handed to Phase 3)

- Any text framing deepteacher's **+8.1 (s800)** or **+82.8 (s200)** as "vs iter8" → it is **vs
  residual.pt**. (Includes the pre-compact review packet drafted this session.)
- `results.csv` deepteacher rows are correctly labeled `iter0(=lever_seq/residual.pt)` — keep, but
  add a note that this baseline ≠ the warm-from, so the deltas are not the experiment's question.
- The "washout: policy improved hugely (+82.8) at s200" interpretation must be downgraded:
  vs the actual warm-from iter8 the s200 gain is **+15.3 / z0.68 (within noise)**.
