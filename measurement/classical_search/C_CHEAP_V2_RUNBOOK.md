# C-cheap v2 — RESIDUAL deck-aware value — IN-FLIGHT RUNBOOK

**Status: IN FLIGHT (2026-07-10). Gen ✅ + Train ✅ + Offline-gate ✅ PASSED (A≈B: deck thesis weak, general leaf-correction survives) → ONLINE eval running (orch smoke → λ-bracket → n=200 CRN, +35 gate).**
Code merged `69ac3f7` (evaluator+gen+trainer+eval+kill-gate) on top of scaffold `a89b0f5`. Champion PRODUCTION.yaml UNCHANGED; all new paths default-OFF / bit-exact when no net supplied.

## Why v2 (the fix for CL-049's botch)
C-cheap **v1 = DEAD (CL-049)**: a net FULLY REPLACED the sharp v2.9 heuristic leaf value → W0/L100 catastrophic. **But it was the wrong test.** Fable's root cause: the v1 dataset had **zero sibling contrasts** (one on-trajectory position per ply, ~70 sharing one game label) → no trainer could produce the local afterstate discrimination the fair agent's **pooled-Q** (value-driven) selection needs. The fix is the **residual form**: the heuristic keeps local ranking; the net only nudges subtree-level Q. And a **residual target** whose null (predict 0) == the champion, so overfit/decay/early-stop fail toward "no change," never "lose every game."

## What the code does (69ac3f7)
- `heuristic_prior_mcts.make_heuristic_prior_evaluator_with_residual_value(game,cfg,value_fn,λ)`: `value = clip(tanh(leaf/15) + λ·net, -1,1)`, no re-tanh. **λ=0 BYTE-IDENTICAL to champion** (verified: λ=0 == fair, 40 moves 0 mismatches). CL-049 replace factory untouched.
- `gen_fair_selfplay.py --value-target residual --exact-endgame`: writes `values = clip(z_mover − tanh(leaf/15), -1,1)` + sidecar `seed_*.meta.npz {z, leaf_tanh}`. **Verified gen leaf_tanh == play heur (0 mismatch on 8 non-zero boards).** Clip tripwire is now AGGREGATE (mean per-game >0.15 over ≥30 games; per-game warn >0.9) — the per-game >0.5 version false-halted on one lopsided game (residual is fine: corr(z,leaf_tanh)=+0.56, aggregate clip ~3.3%).
- `train_value_only_sighted.py`: LR param-groups (re-init stem/value 1e-3, warm trunk 1e-4), early-stop patience-3 **save-best-val**, `--zero-bag-scalars` (deck-BLIND control), null-MSE print.
- `eval_fair_puct.py --net-mode {replace,residual} --net-lambda --orch-shm-name`: residual eval + carc-orch SHM GPU-batched net value.
- `scripts/classical_search/kill_gate_blend.py`: the free offline gate.
- `scripts/classical_search/crn_delta_fairnet.py`: CRN-paired verdict vs the cached baseline.

## LIVE STATE (update as it advances)
- **Gen ✅ DONE** (2026-07-10): 3000 shards + 3000 meta sidecars, 0 skipped, clip 0.034, out `/mnt/c/carc-shared/c_cheap_fairgen_v2`. Both boxes drained it (local 2707 + laptop 137 this run + laptop's pre-drop games). (Laptop WSL flapped mid-gen; rebooted + rejoined shared-claim.)
- **Train ✅ DONE** (GPU, warm iter8): A (deck-aware) best val_mse **0.16014** @ ep1, B (bag-blind) **0.16130** @ ep3, null (predict-0) **0.21508**. Both beat null ~25%. `/mnt/c/carc-shared/c_cheap_value_v2/value_A.pt` + `value_B_zerobag.pt`. (⚠️ fixed `iter_game_dataset_files` to skip `*.meta.npz` — commit `e189e6f`.)
- **Offline kill-gate ✅ PASSED** (2026-07-10): A beats null (blended λ=0.5 +18.8%) AND A's gain > B's (+0.0403 vs +0.0382). **BUT A≈B → deck-awareness adds only ~5% of the signal; the residual net is mostly a general leaf-correction, NOT deck-exploiting. C's deck thesis largely falsified offline.** Gate is necessary-not-sufficient → PROCEED to online eval, LOW prior stands + A≈B yellow flag. Offline-best λ=0.5 monotone; online-best λ TBD (bigger λ lowers global MSE but can corrupt local pooled-Q ranking → the bracket is the real test).
- **Online eval IN FLIGHT**: Stage 4 orch bring-up ✅ (parity PASS max diff 1.38e-05, ~360× under tol; CPU presmoke 2/2 clean) + n=20 smoke RUNNING (value_A, λ=0.25, local orch W48, server 'fairnet'). Then λ-bracket n=40, then n=200 CRN.
- **⏱️ 26h AUTONOMOUS WINDOW (Joshua signed off 2026-07-10, authorized "continue improving the net/leaf, local+laptop, keep it going"):** (1) finish C-v2 per this runbook — smoke → bracket → n=200 CRN both-box → verdict; **if ≥+35 fires, draft the promotion proposal but do NOT touch PRODUCTION.yaml** (champion flips wait for Joshua); if dead, 6-touch close-out. (2) Laptop orch bring-up delegated (subagent; 4070m verified cuda-ok) so bracket/n200 work-steal both boxes at W48/26. (3) Next lever queued = **C5 leaf re-tune under PUCT** (design being drafted by a Fable subagent → C5_LEAF_RETUNE_DESIGN.md; launch screens when boxes free). D2 rung-compression (~2h) = idle-gap filler. B1a was found ALREADY DONE (4.75% « 20%, B2 unfunded — roadmap Track-B line was stale, fixed). Zero cloud; champion untouched; pre-registered gates only.
- Champion baseline to beat: **D0 fair +81 vs h800** (`fair_ladder_s2752_vs_h800_k2`, n=200 band 15e9) — the CRN paired denominator. GATE to fire: online elo(fair-net) − elo(fair) ≥ +35.

## REMAINING STAGED PIPELINE (exact commands; `.venv/bin/python`, `nice -n 19`, detach long runs)
**Stage 2 — train A + B (GPU, 5900XT):**
```
python scripts/canonical_az/train_value_only_sighted.py --data-root /mnt/c/carc-shared/c_cheap_fairgen_v2 \
  --warm-from /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
  --output /mnt/c/carc-shared/c_cheap_value_v2/value_A.pt --batch-size 512 --num-workers 6
python scripts/canonical_az/train_value_only_sighted.py --data-root /mnt/c/carc-shared/c_cheap_fairgen_v2 \
  --warm-from /mnt/c/carc-shared/flywheel_residual_attempt2/ckpt/iter8.pt \
  --output /mnt/c/carc-shared/c_cheap_value_v2/value_B_zerobag.pt --zero-bag-scalars --batch-size 512 --num-workers 6
```
**Stage 3 — OFFLINE KILL-GATE (free; run before any eval compute):**
```
python scripts/classical_search/kill_gate_blend.py --net-a /mnt/c/carc-shared/c_cheap_value_v2/value_A.pt \
  --net-b /mnt/c/carc-shared/c_cheap_value_v2/value_B_zerobag.pt --data-root /mnt/c/carc-shared/c_cheap_fairgen_v2
```
GATE: A beats null (predict-0-residual) AND A's gain > B's (deck-awareness) → PROCEED. Else **KILL** — no online eval (a value that can't out-rank the leaf offline never out-plays it; the value-inertness ledger).

**EVAL ARCHITECTURE (Joshua, 2026-07-10):** the eval is **CPU search workers backed by a GPU-resident net via the orch** — NOT net-per-worker. Each game: fair-net agent (calls orch for residual value) vs clairvoyant-h800 (pure-CPU heuristic). SHM is single-box → **each box runs its OWN orch server on its OWN GPU** (local 5900XT + laptop 4070m; the "orch local+laptop high-W" pattern). Workers = CPU search clients hitting their box's local orch. **Work-steal via `--shared-claim`** on the CIFS pool, both boxes claim one n=200 set (per-deck CRN → no deck played on both boxes → cross-box net non-determinism is a non-issue). **Worker counts: 48 local / 26 laptop** (GPU centralized in orch → oversubscribe cores to hide SHM round-trip; 32T→48, 24c→26). ⚠️ Laptop orch on the 4070m is the least-tested link (carc-orch binary IS built on laptop /rust/.../target/release/carc-orch Jul-3; but verify WSL GPU access `/usr/lib/wsl/lib/nvidia-smi` + parity before relying on it). Stand up the laptop orch ONLY after Stage 3 passes; delegate the bring-up to a subagent.

**Stage 4 — orch GPU server + parity + n=20 smoke** (⚠️ verify exact server/export paths — Opus didn't run orch e2e; likely `rust/carc-orch/run_server.sh` + `scripts/export_torchscript.py` + `scripts/canonical_az/verify_sighted_orch_parity.py`). Smoke can be local-only (fast) OR both-box to shake out the laptop orch early:
```
python scripts/canonical_az/verify_sighted_orch_parity.py --checkpoint <VALUE_CKPT>   # MUST pass
python scripts/export_torchscript.py --checkpoint <VALUE_CKPT> --out /tmp/fairnet.ts.pt --device cuda
rust/carc-orch/run_server.sh --model /tmp/fairnet.ts.pt --transport shm --shm-name fairnet \
  --workers 48 --n-ch 81 --n-scalar 42 --device cuda --max-batch 16 --batch-timeout-ms 2.0 --forwarders 4 --watchdog-secs 30 &   # orch slots >= client workers
python scripts/classical_search/eval_fair_puct.py --info fair-net --net <VALUE_CKPT> --orch-shm-name fairnet \
  --net-mode residual --net-lambda 0.25 --exact-k 2 --k-dets 8 --sims 344 --rung-sims 800 --n 20 --paired \
  --seed-start 13000000000 --workers 48 --out-root /mnt/c/carc-shared/classical_search --out-subdir stage4_orch_smoke --allow-selfplay-seeds --no-results-csv
```
**Stage 5 — λ-bracket n=40 × {0.1,0.25,0.5}** (same, `--n 40 --net-lambda <λ> --out-subdir stage5_lam<λ>`); pick best avg paired margin (ties→0.25).
**Stage 6 — full n=200 fair-net-only + verdict** (`--net-lambda <BEST_λ> --n 200 --seed-start 15000000000` = the cached baseline band; `--out-subdir fairnet_v2_n200 --shared-claim`), then:
```
python scripts/classical_search/crn_delta_fairnet.py --fairnet-dir /mnt/c/carc-shared/classical_search/fairnet_v2_n200 \
  --baseline-dir /mnt/c/carc-shared/fair_ladder_s2752_vs_h800_k2 --out /mnt/c/carc-shared/classical_search/fairnet_v2_n200/crn_delta.json
```
**PROMOTE iff** elo(fair-net) − elo(fair) ≥ **+35** AND CRN paired-Δ z clearly >0 AND (Stage-3 A beat null where B didn't). Else close C on the value-inertness ledger.

**Prior:** LOW (probe_b_4a offline null + 6 value-inertness nulls). This is the one properly-shaped shot; kill fast at each gate. Zero cloud, ~1 cluster-day.
