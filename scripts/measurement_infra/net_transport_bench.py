#!/usr/bin/env python3
"""Net FORWARD-TRANSPORT bench — where should a single-game deploy run the net's forwards?

MEASUREMENT INFRASTRUCTURE (not a strength lever). Roadmap **G3** (per-move cost
reduction), stage "Eff Jensen". This prices the TRANSPORT of one policy forward.
**It does NOT measure strength** — no games are played and no elo is produced.

## The question

For SINGLE-GAME deploy-scale play (1 game, batch-1 forwards, no cross-worker
batching) the CL-067 distilled policy net has to run its forwards *somewhere* on
the 5900XT box:

  * **GPU batch-1** — the measured-bad path (19.4 ms/forward on a LOADED box;
    clean number unknown). Batch-1 is the GPU's worst case: kernel-launch +
    PCIe round-trip dominate, and a single game cannot amortise them because
    `make_remote_single_evaluator` is k=1-per-request and the worker BLOCKS
    (⇒ no batching — see G3 in docs/PROGRAM_ROADMAP_2026-07-07.md).
  * **CPU torch, 1 thread** — 2.6 ms on Joshua's M5; unknown on the 5900XT.
  * **CPU torch, 2 or 4 threads** — does intra-op parallelism help a 7M-param
    6×96 ResNet at batch 1, or does the sync overhead eat it?

Joshua's hypothesis: *"maybe net on cpu isn't so bad if it means everyone stays
in dram"* — CPU inference also **composes with k-parallel workers** (no shared
device to serialise on), which the GPU path does not.

## THE DECISION RULE THESE NUMBERS FEED

    if clean CPU-1t batch-1 latency ≲ 3× clean GPU batch-1 latency,
    single-game deploy should default to NET-ON-CPU
    (it composes with k-parallel workers and frees the GPU entirely).

The batched-CUDA rows (batch 8/32/128) are a *reference* for the contrast the
write-up needs: batch-1 GPU vs the orchestrator (carc-orch) regime that batches
across workers. They are throughput numbers, not deploy numbers.

## What is timed (and why it is the PRODUCTION path, not a proxy)

Per the "profile the production path" rule, the consumption pattern is not
re-implemented here — the bench calls the REAL factories:

  * batch-1  → `carcassonne_ai.evaluators.make_single_evaluator_policy_only`
  * batched  → `carcassonne_ai.evaluators.make_batch_evaluator_policy_only`

which are exactly what `make_fair_net_prior_evaluator` (heuristic_prior_mcts.py)
calls for its per-worker CPU-net path. ⚠️ **Signature note:** that path uses
`forward_policy_only` (the VALUE head is never computed — the value comes from
the frozen v2.9 leaf), and the per-call device→host sync is **NOT** a `.item()`:
it is `probs[0].float().cpu().numpy()`, a full action-space (2511-float) copy,
with the masked softmax executed ON DEVICE. The `.item()` sync only exists on
the net-VALUE evaluators, which the CL-067 netprior agent does not use.

Two timings per row, so the transport can be separated from the featuriser:

  * ``forward_ms`` — numpy → `.to(device)` → `forward_policy_only` → masked
    softmax on device → `.cpu().numpy()`. **This is the transport price.**
  * ``full_ms`` — the whole real evaluator call, i.e. ``forward_ms`` plus
    `get_canonical_form` + `get_valid_moves` (device-independent CPU work).
    This is the per-leaf cost the agent actually pays.

The legal-moves cache is deliberately OFF: in real search every leaf is a
distinct board, so a warm cache over one repeated board would understate the
featuriser.

## Contention guard

The full bench REFUSES to run at loadavg > 4 (``--force`` overrides). Latency
benches are worthless on a contended box — every cost ratio in this project has
moved when re-probed unloaded. ``--smoke`` runs a tiny CPU-only pass (≤100
calls) purely to prove the plumbing emits valid JSON; **smoke numbers are not
measurements** and are flagged as such in the output manifest.

## Usage

    # tonight, contended: plumbing proof only
    python3 scripts/measurement_infra/net_transport_bench.py --smoke \
        --out /path/to/scratch/net_transport_smoke.json

    # tomorrow's quiet window: the real bench
    scripts/measurement_infra/net_transport_bench.sh
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
from pathlib import Path

# CL-067 iter_03 — the distilled policy net whose deploy cost G3 is trying to cut.
DEFAULT_CKPT = "/mnt/c/carc-shared/distill_strong_20260723/ckpt/iter_03.pt"
EXPECTED_SHA256 = "6e2679908d79a76cd2d66789d992676a5bfa85946a1543968982b308873751a1"

LOADAVG_LIMIT = 4.0

# name -> row spec. `device`/`batch`/`threads`/`compile` fully determine the cell.
ROW_SPECS: dict[str, dict] = {
    # --- the deploy question: batch-1, one game, no cross-worker batching -------
    "cuda_b1":         dict(device="cuda", batch=1,   threads=None, compile=False),
    "cpu_1t":          dict(device="cpu",  batch=1,   threads=1,    compile=False),
    "cpu_2t":          dict(device="cpu",  batch=1,   threads=2,    compile=False),
    "cpu_4t":          dict(device="cpu",  batch=1,   threads=4,    compile=False),
    # --- reference: the orchestrator (carc-orch) regime, batching ACROSS workers -
    "cuda_b8":         dict(device="cuda", batch=8,   threads=None, compile=False),
    "cuda_b32":        dict(device="cuda", batch=32,  threads=None, compile=False),
    "cuda_b128":       dict(device="cuda", batch=128, threads=None, compile=False),
    # --- LAST on purpose: torch.compile's warm-up is unbounded-ish, and it must
    #     not be able to delay (or, on a timeout, cost) any decision-bearing row.
    "cpu_1t_compile":  dict(device="cpu",  batch=1,   threads=1,    compile=True),
}
FULL_ROWS = list(ROW_SPECS)
# Plumbing-only cell: exercises the BATCH branch off-GPU so the batched code path
# can be validated without touching a GPU that is busy serving something else.
# Not in FULL_ROWS — it is not a deploy question.
ROW_SPECS["cpu_b8_plumbing"] = dict(device="cpu", batch=8, threads=1, compile=False)
SMOKE_ROWS = ["cpu_1t", "cpu_2t"]
# A stuck torch.compile must not stall the whole bench.
ROW_TIMEOUT_S = 1800


# --------------------------------------------------------------------------- #
# machine state / manifest                                                     #
# --------------------------------------------------------------------------- #
def read_loadavg() -> list[float]:
    with open("/proc/loadavg") as fh:
        return [float(x) for x in fh.read().split()[:3]]


def nvidia_smi() -> dict | None:
    """GPU power/util/mem, or None if nvidia-smi is absent (e.g. the laptop)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,power.draw,utilization.gpu,"
             "memory.used,memory.total,clocks.sm",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    gpus = []
    for line in out.stdout.strip().splitlines():
        f = [p.strip() for p in line.split(",")]
        if len(f) < 6:
            continue
        gpus.append(dict(name=f[0], power_w=_f(f[1]), util_pct=_f(f[2]),
                         mem_used_mib=_f(f[3]), mem_total_mib=_f(f[4]),
                         sm_clock_mhz=_f(f[5])))
    return {"gpus": gpus}


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def machine_state() -> dict:
    la = read_loadavg()
    return {
        "t": time.time(),
        "loadavg": {"1m": la[0], "5m": la[1], "15m": la[2]},
        "nvidia_smi": nvidia_smi(),
    }


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def thread_env_snapshot() -> dict:
    keys = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
            "NUMEXPR_NUM_THREADS", "CUDA_VISIBLE_DEVICES",
            "CARCASSONNE_USE_FLAT_LEAF", "CARCASSONNE_USE_CY_LEAF")
    return {k: os.environ.get(k) for k in keys}


# --------------------------------------------------------------------------- #
# checkpoint loading — mirrors scripts/classical_search/eval_fair_puct.py       #
# _load_net_rep (rep is INFERRED from the ckpt, never assumed; fail loud).      #
# --------------------------------------------------------------------------- #
def load_net_rep(path: str, device: str = "cpu"):
    import torch
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.network import CarcassonneNet

    ck = torch.load(path, map_location=device, weights_only=False)
    n_ch = int(ck.get("n_input_channels", 78))
    n_sc = int(ck.get("n_scalar_features", 10))
    sighted = bool(ck.get("sighted", False))
    include_farm = bool(ck.get("include_farm_scalars", (n_sc > 10) and not sighted))
    probe = Game(sighted=sighted, include_farm_scalars=include_farm)
    exp_ch, exp_sc = probe.get_input_channels(), probe.get_scalar_feature_size()
    if (n_ch, n_sc) != (exp_ch, exp_sc):
        raise SystemExit(
            f"FATAL: checkpoint {path} is internally inconsistent — declares "
            f"sighted={sighted} / include_farm_scalars={include_farm} (implies "
            f"{exp_ch}ch/{exp_sc}sc) but carries {n_ch}ch/{n_sc}sc. "
            "Refusing to guess the representation."
        )
    net = CarcassonneNet(
        n_filters=ck.get("n_filters", 96), n_blocks=ck.get("n_blocks", 6),
        n_input_channels=n_ch, n_scalar_features=n_sc,
        value_global_pool=bool(ck.get("value_global_pool", False)),
    ).to(device)
    net.load_state_dict(ck["model_state"])
    net.eval()
    rep = {
        "sighted": sighted, "n_input_channels": n_ch, "n_scalar_features": n_sc,
        "include_farm_scalars": include_farm,
        "value_global_pool": bool(ck.get("value_global_pool", False)),
        "n_filters": int(ck.get("n_filters", 96)),
        "n_blocks": int(ck.get("n_blocks", 6)),
        "iter": ck.get("iter"), "provenance": ck.get("provenance"),
        "action_size": int(net.action_size),
        "n_params": int(sum(p.numel() for p in net.parameters())),
    }
    return net, rep


# --------------------------------------------------------------------------- #
# board pool                                                                   #
# --------------------------------------------------------------------------- #
def build_board_pool(rep: dict, n_boards: int, deck_seed: int = 20260728):
    """A deterministic pool of mid-game boards at a spread of plies.

    Uses the root_replay contract: the engine consumes the global `random` stream
    only in `Game.get_init_board()`, so seeding it fixes the deck. Move choice
    draws from a SEPARATE `random.Random` so the deck is unaffected.

    ``enable_legal_moves_cache=False`` on purpose — see the module docstring.
    """
    import numpy as np
    from carcassonne_ai.game_wrapper import Game

    random.seed(int(deck_seed))
    game = Game(sighted=rep["sighted"],
                include_farm_scalars=rep["include_farm_scalars"],
                enable_legal_moves_cache=False)
    board = game.get_init_board()
    rng = random.Random(7)

    # spread the sampled plies over the early/mid/late game
    want_plies = sorted({int(round(6 + i * (110 - 6) / max(1, n_boards - 1)))
                         for i in range(n_boards)})
    boards, plies = [], []
    ply = 0
    target = iter(want_plies)
    nxt = next(target, None)
    while nxt is not None:
        if game.get_game_ended(board, 1) != 0:
            break
        legal = np.flatnonzero(game.get_valid_moves(board))
        if legal.size == 0:
            break
        board, _ = game.get_next_state(board, int(rng.choice(legal.tolist())))
        ply += 1
        if ply == nxt:
            boards.append(board)
            plies.append(ply)
            nxt = next(target, None)
    if not boards:
        raise SystemExit("FATAL: board pool is empty — the replay produced no positions")
    return game, boards, plies


# --------------------------------------------------------------------------- #
# one row                                                                      #
# --------------------------------------------------------------------------- #
def _stats(samples_s: list[float]) -> dict:
    ms = sorted(x * 1e3 for x in samples_s)
    n = len(ms)
    return {
        "n": n,
        "mean_ms": statistics.fmean(ms),
        "p50_ms": ms[int(0.50 * (n - 1))],
        "p90_ms": ms[int(0.90 * (n - 1))],
        "p99_ms": ms[int(0.99 * (n - 1))],
        "min_ms": ms[0],
        "max_ms": ms[-1],
        "stdev_ms": statistics.stdev(ms) if n > 1 else 0.0,
    }


def run_row(name: str, spec: dict, ckpt: str, n_calls: int, n_warmup: int,
            n_boards: int) -> dict:
    """Measure one cell. Runs in a CHILD process so its thread/device env is clean."""
    import numpy as np
    import torch

    row = {"row": name, "spec": dict(spec), "state_start": machine_state()}

    if spec["threads"] is not None:
        # belt-and-braces: the OMP_/MKL_ env was already pinned by the parent
        # before this process imported torch (see child_env).
        torch.set_num_threads(int(spec["threads"]))
    row["torch_num_threads"] = torch.get_num_threads()
    row["torch_num_interop_threads"] = torch.get_num_interop_threads()

    device_str = spec["device"]
    if device_str == "cuda" and not torch.cuda.is_available():
        row["skipped"] = "cuda not available"
        row["state_end"] = machine_state()
        return row
    device = torch.device(device_str)

    net, rep = load_net_rep(ckpt, device=device_str)
    row["rep"] = rep
    if device_str == "cuda":
        row["device_name"] = torch.cuda.get_device_name(0)

    if spec["compile"]:
        # ⚠️ `torch.compile(net)` would be a NO-OP here: it only compiles the
        # module's `forward`, and this path never calls `forward` — the netprior
        # evaluator calls `forward_policy_only`. Compile the BOUND METHOD instead
        # (verified: wrapping the module left latency unchanged). The masked
        # softmax stays eager, as in production.
        try:
            t0 = time.perf_counter()
            net.forward_policy_only = torch.compile(net.forward_policy_only)
            row["compile_wrapped_s"] = time.perf_counter() - t0
            row["compile_target"] = "net.forward_policy_only (bound method)"
        except Exception as exc:                      # pragma: no cover - env dep
            row["skipped"] = f"torch.compile unavailable: {type(exc).__name__}: {exc}"
            row["state_end"] = machine_state()
            return row

    game, boards, plies = build_board_pool(rep, n_boards)
    row["board_plies"] = plies

    from carcassonne_ai.evaluators import (make_batch_evaluator_policy_only,
                                           make_single_evaluator_policy_only)

    B = int(spec["batch"])
    if B == 1:
        ev = make_single_evaluator_policy_only(net, device, game)
        call_full = lambda i: ev(boards[i % len(boards)])          # noqa: E731
    else:
        evb = make_batch_evaluator_policy_only(net, device, game)
        batches = [[boards[(k * B + j) % len(boards)] for j in range(B)]
                   for k in range(max(1, len(boards)))]
        call_full = lambda i: evb(batches[i % len(batches)])       # noqa: E731

    # --- pre-encoded tensors for the forward-only (TRANSPORT) timing ---------
    # Same ops as the real evaluator, minus get_canonical_form/get_valid_moves.
    pre = []
    for k in range(len(boards) if B == 1 else max(1, len(boards))):
        bs = [boards[k % len(boards)]] if B == 1 else \
             [boards[(k * B + j) % len(boards)] for j in range(B)]
        obs_l, sc_l, mk_l = [], [], []
        for b in bs:
            o, s = game.get_canonical_form(b, b.state.current_player)
            obs_l.append(o); sc_l.append(s); mk_l.append(game.get_valid_moves(b))
        pre.append((np.stack(obs_l), np.stack(sc_l), np.stack(mk_l).copy()))

    def call_forward(i):
        obs, sc, mk = pre[i % len(pre)]
        obs_t = torch.from_numpy(obs).float().to(device)
        sc_t = torch.from_numpy(sc).float().to(device)
        mk_t = torch.from_numpy(mk).bool().to(device)
        with torch.no_grad():
            logits = net.forward_policy_only(obs_t, sc_t)
            probs = net.policy_softmax_with_mask(logits, mk_t)
        # the real sync: a full action-space device->host copy (NOT .item())
        return probs.float().cpu().numpy()

    # sanity: the forward-only path must reproduce the real evaluator's priors
    ref = call_full(0)[0]
    got = call_forward(0)
    ref0 = ref if ref.ndim == 1 else ref[0]
    got0 = got[0] if got.ndim == 2 else got
    row["forward_matches_evaluator_maxabs"] = float(np.abs(got0 - ref0).max())

    out = {}
    for label, fn in (("full", call_full), ("forward", call_forward)):
        for i in range(n_warmup):
            fn(i)
        if device_str == "cuda":
            torch.cuda.synchronize()
        samples = []
        for i in range(n_calls):
            t0 = time.perf_counter()
            fn(i)
            samples.append(time.perf_counter() - t0)
        out[label] = _stats(samples)
        out[label]["per_item_mean_ms"] = out[label]["mean_ms"] / B
        out[label]["items_per_s"] = B / (out[label]["mean_ms"] / 1e3)
    row["timings"] = out
    row["n_warmup"] = n_warmup
    row["state_end"] = machine_state()
    return row


# --------------------------------------------------------------------------- #
# parent / child plumbing                                                      #
# --------------------------------------------------------------------------- #
def child_env(spec: dict) -> dict:
    env = dict(os.environ)
    if spec["device"] == "cpu":
        # Hard-pin the CPU row's thread budget BEFORE torch imports (set_num_threads
        # alone does not bind the OpenMP/MKL pools), and hide the GPU so no CUDA
        # context is created (a stray context perturbs a latency bench).
        n = str(int(spec["threads"] or 1))
        env.update(OMP_NUM_THREADS=n, MKL_NUM_THREADS=n, OPENBLAS_NUM_THREADS=n,
                   NUMEXPR_NUM_THREADS=n, CUDA_VISIBLE_DEVICES="")
    else:
        env.pop("CUDA_VISIBLE_DEVICES", None)
    return env


def run_row_in_child(name: str, spec: dict, args, out_dir: Path) -> dict:
    tmp = out_dir / f".row_{name}.json"
    cmd = [sys.executable, os.path.abspath(__file__), "--_child-row", name,
           "--ckpt", args.ckpt, "--calls", str(args.calls),
           "--warmup", str(args.warmup), "--boards", str(args.boards),
           "--_child-out", str(tmp)]
    try:
        proc = subprocess.run(cmd, env=child_env(spec), capture_output=True,
                              text=True, timeout=ROW_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"row": name, "spec": dict(spec), "failed": True,
                "skipped": f"row exceeded ROW_TIMEOUT_S={ROW_TIMEOUT_S}s "
                           "(torch.compile is the usual suspect)"}
    if proc.returncode != 0 or not tmp.exists():
        return {"row": name, "spec": dict(spec), "failed": True,
                "returncode": proc.returncode,
                "stderr": proc.stderr[-4000:], "stdout": proc.stdout[-2000:]}
    row = json.loads(tmp.read_text())
    tmp.unlink()
    row["child_env"] = {k: child_env(spec).get(k) for k in
                        ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "CUDA_VISIBLE_DEVICES")}
    return row


def parent_manifest(args, rows_requested: list[str], sha: str) -> dict:
    import torch
    return {
        "script": "scripts/measurement_infra/net_transport_bench.py",
        "purpose": "G3 forward-transport pricing (batch-1 GPU vs CPU-Nt vs batched GPU)",
        "not_a_strength_measurement": True,
        "decision_rule": ("if clean CPU-1t batch-1 <= ~3x clean GPU batch-1, "
                          "single-game deploy should default net-on-CPU "
                          "(composes with k-parallel, frees the GPU)"),
        "ckpt": args.ckpt,
        "ckpt_sha256": sha,
        "ckpt_sha256_expected": EXPECTED_SHA256,
        "smoke": bool(args.smoke),
        "smoke_is_not_a_measurement": bool(args.smoke),
        "forced": bool(args.force),
        "rows_requested": rows_requested,
        "calls": args.calls, "warmup": args.warmup, "boards": args.boards,
        "torch_version": torch.__version__,
        "torch_cuda_version": getattr(torch.version, "cuda", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_names": ([torch.cuda.get_device_name(i)
                               for i in range(torch.cuda.device_count())]
                              if torch.cuda.is_available() else []),
        "cpu_count": os.cpu_count(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "hostname": platform.node(),
        "parent_thread_env": thread_env_snapshot(),
        "git_rev": _git_rev(),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _git_rev() -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(Path(__file__).resolve().parents[2]),
                            "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or None
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--out", default=None, help="output JSON path")
    ap.add_argument("--calls", type=int, default=2000,
                    help="timed calls per row (>=2000 for the real bench)")
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--boards", type=int, default=16,
                    help="distinct positions in the pool (cycled)")
    ap.add_argument("--rows", default=None,
                    help="comma-separated row subset (default: all / smoke set)")
    ap.add_argument("--smoke", action="store_true",
                    help="plumbing proof: CPU-only, <=100 calls. NOT a measurement.")
    ap.add_argument("--force", action="store_true",
                    help="run the full bench even at loadavg > %.0f" % LOADAVG_LIMIT)
    ap.add_argument("--_child-row", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--_child-out", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    # ---- child mode: measure exactly one row, dump JSON, exit ----------------
    if getattr(args, "_child_row"):
        name = getattr(args, "_child_row")
        row = run_row(name, ROW_SPECS[name], args.ckpt, args.calls,
                      args.warmup, args.boards)
        Path(getattr(args, "_child_out")).write_text(json.dumps(row, indent=2))
        return 0

    # ---- contention guard ----------------------------------------------------
    la = read_loadavg()
    if args.smoke:
        args.calls = min(args.calls, 100)
        args.warmup = min(args.warmup, 10)
        args.boards = min(args.boards, 6)
    elif la[0] > LOADAVG_LIMIT and not args.force:
        print(f"REFUSING: 1m loadavg {la[0]:.2f} > {LOADAVG_LIMIT:.0f}. A latency "
              "bench on a contended box is not a measurement — run it in the quiet "
              "window, or pass --force if you really mean it.", file=sys.stderr)
        return 2

    if args.smoke:
        rows = SMOKE_ROWS
    else:
        rows = FULL_ROWS
    if args.rows:
        rows = [r.strip() for r in args.rows.split(",") if r.strip()]
    unknown = [r for r in rows if r not in ROW_SPECS]
    if unknown:
        print(f"unknown rows: {unknown}; known: {FULL_ROWS}", file=sys.stderr)
        return 2

    sha = sha256_of(args.ckpt)
    if sha != EXPECTED_SHA256:
        print(f"FATAL: {args.ckpt} sha256 {sha} != expected {EXPECTED_SHA256} "
              "— that is not CL-067 iter_03.", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else Path.cwd() / "net_transport_bench.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "manifest": parent_manifest(args, rows, sha),
        "state_start": machine_state(),
        "rows": [],
    }
    for name in rows:
        t0 = time.perf_counter()
        row = run_row_in_child(name, ROW_SPECS[name], args, out_path.parent)
        row["wallclock_s"] = time.perf_counter() - t0
        result["rows"].append(row)
        tim = row.get("timings", {})
        if "full" in tim:
            print(f"[{name:16s}] forward {tim['forward']['mean_ms']:8.3f} ms "
                  f"(p50 {tim['forward']['p50_ms']:.3f} / p90 "
                  f"{tim['forward']['p90_ms']:.3f})   full "
                  f"{tim['full']['mean_ms']:8.3f} ms   "
                  f"{tim['full']['items_per_s']:.1f} pos/s")
        else:
            print(f"[{name:16s}] {row.get('skipped') or row.get('stderr','FAILED')[:200]}")
    result["state_end"] = machine_state()
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
