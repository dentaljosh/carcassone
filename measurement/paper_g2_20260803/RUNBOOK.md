# G2 — RUNBOOK / resumption note

> **STATUS: ✅ SPENT 2026-08-03 — all three arms trained, ruler pass complete,
> verdict `C_GRAY`.** Steps 1–5 below all ran; nothing here is live. Kept for the
> reproduction path and the resume machinery (both would be reused if the control
> is ever extended). Verdict: **[READOUT.md](READOUT.md)** · bars + adjudication:
> [PREREG.md](PREREG.md) · rationale: [DESIGN_MEMO.md](DESIGN_MEMO.md).
>
> *(original banner, retained)* **🟡 TRAINING IN FLIGHT (launched 2026-08-03).**
> This file exists so a fresh session can pick the run up without reconstructing
> anything.

## Where everything is

| what | path |
|---|---|
| worktree (the code that is running) | `/home/doctor/projects/carcassone/.claude/worktrees/agent-a1860cb7f9dc6f899` |
| training outputs (checkpoints, history, manifest) | `/mnt/c/carc-shared/paper_g2_20260803/<arm>/` |
| chain log | `/mnt/c/carc-shared/paper_g2_20260803/chain.log` |
| watchdog heartbeat | `/mnt/c/carc-shared/paper_g2_20260803/watchdog.log` |
| staged corpus (local ext4, off 9p) | `/tmp/g2_stage/{train,val}` |
| ruler report (written later) | `measurement/paper_g2_20260803/solver_score_g2.json` |

Arms, in chain order: `resnet_scratch` → `tf_match` → `tf_large`. Every arm
writes `epoch_NN.pt`, `last.pt`, `best.pt`, `final.pt`, `history.json`,
`manifest.json`, `train_state.pt`.

**Launched 2026-08-03 06:59 EDT.** Chain PID group under
`scripts/paper_g2/run_g2_chain.sh`; watchdog armed at 07:00 (15-min heartbeat).

**ETA, revised on a MEASURED epoch** (the pre-flight bench's compute-only figures
were optimistic by ~30% once the fp32 validation passes and the dataloader are
counted; the 1-epoch `tf_match` smoke ran **356.3 s**):

| arm | min/epoch | 16 epochs |
|---|---|---|
| `resnet_scratch` | ≈3.5 | ≈0.9 h |
| `tf_match` | 5.9 (measured) | ≈1.6 h |
| `tf_large` | ≈31 (bench + val) | ≈8.3 h |

**≈11 h total**, finishing ≈2026-08-03 18:00 EDT if uninterrupted.

⚠️ **A CPU re-sweep farm (`capscurve_resweep_launcher.sh`, ~28 workers) is live on
this box.** That is expected and has priority — the G2 chain is GPU work with only
4 dataloader workers, all at `nice -n 19`. Do NOT raise `--num-workers` to fight
it, and do NOT start the ruler pass (16 CPU workers) while the farm is up.

## Is it alive?

```bash
pgrep -af "paper_g2/train_g2.py" || echo "not running"
tail -5 /mnt/c/carc-shared/paper_g2_20260803/watchdog.log
tail -20 /mnt/c/carc-shared/paper_g2_20260803/chain.log
nvidia-smi --query-gpu=utilization.gpu,power.draw,memory.used --format=csv
```

## If it died (dirty reboot, WSL teardown, OOM)

The chain is idempotent — just relaunch it. Arms with `final.pt` are skipped;
the in-progress arm resumes from `last.pt` + `train_state.pt`, losing at most one
epoch.

```bash
setsid nohup /home/doctor/projects/carcassone/.claude/worktrees/agent-a1860cb7f9dc6f899/scripts/paper_g2/run_g2_chain.sh \
  >> /mnt/c/carc-shared/paper_g2_20260803/chain.log 2>&1 < /dev/null &
```

The watchdog (`scripts/paper_g2/g2_watchdog.sh`, 15-min interval) does exactly
this on its own; check `watchdog.log` before intervening by hand.

## When training completes — the eval chain (nothing here is optional)

1. **Check the training gates BEFORE looking at any ruler number** (PREREG §4.1
   convergence, §4.2 did-it-fit). `analyze_g2.py` computes both off
   `history.json`; an arm that fails §4.2 cannot support Branch A, and an arm
   that fails §4.1 gets **one** +16-epoch extension:
   ```bash
   G2_EPOCHS=32 .../run_g2_chain.sh     # resumes; cosine re-anneals over 32
   ```

2. **Run the ruler** — one pass, all rankers, ≈1–2 h on 16 CPU workers,
   `nice -n 19`, pure CPU (the harness masks CUDA). Do NOT run it beside a live
   eval on this box (memory `feedback_no_agent_compute_beside_eval`).
   ```bash
   setsid nohup env W=16 .../scripts/paper_g2/run_g2_ruler.sh \
     > /mnt/c/carc-shared/paper_g2_20260803/ruler.log 2>&1 < /dev/null &
   ```

3. **Adjudicate**:
   ```bash
   .../.venv/bin/python .../scripts/paper_g2/analyze_g2.py \
     > measurement/paper_g2_20260803/VERDICT.json
   ```
   Read `INSTRUMENT_INTEGRITY.PASS` first — if false, the pass is **VOID**
   (PREREG §4.3) and no G2 number may be reported. Then `TRAINING_GATES`, then
   `HEADLINE.BRANCH`.

4. **Write the read-out** (`READOUT.md`, house style: scope up front, the
   pre-registration cited by commit `ffd9319`, the verdict, then the honest
   scope), fill PREREG §7, and run `python3 scripts/doc_lint.py`.

5. **Close-out touches** (CLAUDE.md's six, minus the two that do not apply):
   DECISIONS index line · status stamp on DESIGN_MEMO/PREREG · CLAIMS_LEDGER row
   **G2** flipped from "funding decision for Joshua" to the outcome ·
   OUTLINE §9.3 rewritten per the fired branch · roadmap line ·
   STATUS top block. **No `results.csv` row and no `PRODUCTION.yaml` touch** —
   this is an offline instrument; the paper ledger + this directory carry it.
   If **Branch B** fired, additionally raise the strength-program flag in STATUS
   and stop: next steps are Joshua's, not the agent's.

## Standing constraints on this run

- Measurement only. No champion change, no promotion, no online/game eval, no
  blend — whatever the result (PREREG §6).
- No metric may be defined after commit `ffd9319`.
- Merge the worktree back to `android-app` only at a quiet window (no live local
  run), per CLAUDE.md's worktree-isolation norm. Nothing here edits
  `src/carcassonne_ai/` or `engine/`; the only shared-file change is an additive
  `--g2-checkpoint` flag on `scripts/canonical_az/solver_score.py`.
- **Never push.**
