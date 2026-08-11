#!/usr/bin/env python3
"""ON-MAC ACCEPTANCE GATE for the CoreML/ANE net-prior forward. Run BEFORE the cell.

Loads BOTH backends against the SAME checkpoint and runs them over >=60 REAL positions
the production champion actually reached, then reports the four numbers the M5
equal-wall-clock cell has to cite:

  1. **policy max-abs**      — largest |coreml - torch| over all legal priors. This is
                               the fp16 error budget, and it is the ONLY term that
                               differs: the mask and softmax are host-side float32 on
                               both sides (coreml_evaluator DESIGN DECISION 1).
  2. **legal-argmax agreement** — fraction of positions where both backends' top move
                               is the same move. This is what actually reaches PUCT.
  3. **top-5 overlap**       — mean |top5_coreml ∩ top5_torch| / 5, over positions with
                               >=5 legal moves. Argmax alone is a coarse instrument on
                               a 2511-action space; a backend that reorders ranks 2-5
                               changes the search even when the argmax survives.
  4. **per-call latency**    — batch-1 ms for each backend, on the box, TODAY. The gate
                               read-out's r-model consumes this directly.

WHY A SEPARATE SCRIPT. The contract tests (``tests/test_coreml_evaluator.py``) pin
everything between the encoder and the runtime with a mocked model, and they run on
Linux. They CANNOT pin fp16 accelerator arithmetic, because that arithmetic only exists
on the Air. This is the other half, and it is the half that decides whether the cell is
worth running: if the ANE reorders the argmax on a meaningful fraction of positions, the
"same agent, cheaper forward" framing is false and the cell would be measuring a
different player without saying so.

ACCEPTANCE (defaults; all three must hold, and all are reported either way):
  * legal-argmax agreement  >= 0.98
  * mean top-5 overlap      >= 0.95
  * policy max-abs          <= 5e-3

These are DIAGNOSTIC thresholds, not a strength claim — a backend that passes is
"plausibly the same player", which is exactly the precondition the cell needs and
nothing more. A FAIL does not necessarily kill the line; it means the honest cell is
"ANE agent vs champion" with the ANE agent named as a distinct player, not "the same
agent on a cheaper forward".

USAGE (on the Air):

    python3 scripts/m5_bench/verify_coreml_evaluator.py \\
        --checkpoint ~/m5_ane_cell/iter_03.pt \\
        --model ~/m5_ane_cell/coreml/cl067_iter03_policy_fp16.mlpackage \\
        --positions ~/m5_bench_20260728/bundle/positions.jsonl \\
        --out ~/m5_ane_cell/verify_coreml.json

Requires: torch (reference backend), coremltools (candidate backend), macOS.
"""
from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def _stats(xs: list[float]) -> dict:
    s = sorted(xs)
    n = len(s)

    def q(p: float) -> float:
        return s[min(n - 1, max(0, int(round(p * n)) - 1))]

    return {"n": n, "mean_ms": sum(s) / n, "min_ms": s[0], "p50_ms": q(0.50),
            "p90_ms": q(0.90), "max_ms": s[-1]}


def load_positions(path: Path, limit: int | None) -> list[dict]:
    rows = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
    if not rows:
        raise SystemExit(f"verify_coreml_evaluator: empty positions file {path}")
    return rows[:limit] if limit else rows


def replay(Game, row: dict):
    """Reconstruct the board at ``row['ply']`` — the root_replay contract, inlined.

    Lossless for ANY policy: the engine consumes the global ``random`` stream in exactly
    one place (the deck shuffle in ``get_init_board``), so (deck_seed, action_prefix)
    determines the position exactly. Same function as ``bench_champion.replay``; see
    ``scripts/measurement_infra/root_replay.py`` for the proof.
    """
    random.seed(int(row["deck_seed"]))
    game = Game(enable_legal_moves_cache=True)
    board = game.get_init_board()
    for a in row["actions"]:
        board, _ = game.get_next_state(board, int(a))
    return game, board


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--checkpoint", type=Path, required=True,
                   help="the .pt the .mlpackage was exported from (the torch reference)")
    p.add_argument("--model", type=Path, required=True, help="the .mlpackage")
    p.add_argument("--positions", type=Path, required=True,
                   help="positions.jsonl from scripts/m5_bench/make_positions.py")
    p.add_argument("-n", "--n-positions", type=int, default=None,
                   help="cap (default: all; the gate wants >=60)")
    p.add_argument("--compute-units", default="CPU_AND_NE")
    p.add_argument("--latency-iters", type=int, default=100)
    p.add_argument("--latency-warmup", type=int, default=20)
    p.add_argument("--min-argmax-agree", type=float, default=0.98)
    p.add_argument("--min-top5-overlap", type=float, default=0.95)
    p.add_argument("--max-policy-abs", type=float, default=5e-3)
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args(argv)

    sys.path.insert(0, str(REPO / "src"))
    import numpy as np  # noqa: PLC0415
    import torch  # noqa: PLC0415

    from carcassonne_ai.coreml_evaluator import (  # noqa: PLC0415
        BOARD_INPUT, SCALARS_INPUT, load_coreml_model, make_coreml_policy_evaluator,
    )
    from carcassonne_ai.evaluators import (  # noqa: PLC0415
        make_single_evaluator_policy_only,
    )
    from carcassonne_ai.game_wrapper import Game  # noqa: PLC0415
    from carcassonne_ai.network import CarcassonneNet  # noqa: PLC0415

    if platform.system() != "Darwin":
        print("verify_coreml_evaluator: WARNING — CoreML predict is macOS-only; this "
              f"is {platform.system()}. Expect the load or the first predict to fail.",
              file=sys.stderr)

    # ---- reference backend: torch on CPU, 1 thread (the honest single-stream regime)
    torch.set_num_threads(1)
    ck = torch.load(a.checkpoint, map_location="cpu", weights_only=False)
    arch = {
        "n_filters": int(ck["n_filters"]), "n_blocks": int(ck["n_blocks"]),
        "n_input_channels": int(ck.get("n_input_channels", 78)),
        "n_scalar_features": int(ck.get("n_scalar_features", 10)),
        "value_global_pool": bool(ck.get("value_global_pool", False)),
    }
    net = CarcassonneNet(**arch).eval()
    net.load_state_dict(ck["model_state"])

    # The encoder MUST be the rep the net was trained on. Inferred from the checkpoint's
    # own input dims rather than assumed — feeding an 81ch net a 78ch encode produces
    # plausible garbage, and this script's whole job is to notice that class of thing.
    sighted = arch["n_input_channels"] != 78 or arch["n_scalar_features"] != 10
    game = Game(sighted=sighted, enable_legal_moves_cache=True)
    torch_ev = make_single_evaluator_policy_only(net, torch.device("cpu"), game)

    # ---- candidate backend: CoreML on CPU_AND_NE
    model = load_coreml_model(a.model, compute_units=a.compute_units)
    coreml_ev = make_coreml_policy_evaluator(model, game)

    rows = load_positions(a.positions, a.n_positions)
    print(f"verify_coreml_evaluator: {len(rows)} positions  "
          f"{arch['n_input_channels']}ch/{arch['n_scalar_features']}sc "
          f"(sighted={sighted})  units={a.compute_units}")
    if len(rows) < 60:
        print(f"  ⚠️  only {len(rows)} positions — the gate asks for >=60.",
              file=sys.stderr)

    max_abs = 0.0
    argmax_agree = 0
    top5_sum = 0.0
    top5_n = 0
    per_pos = []
    for row in rows:
        g, board = replay(Game, row)
        # `g` is the blind replay game; the ENCODER is the rep-correct `game` above.
        # Both evaluators are handed the identical Board, so any difference is the
        # forward.
        p_t, _ = torch_ev(board)
        p_c, _ = coreml_ev(board)
        mask = game.get_valid_moves(board).astype(bool)
        d = float(np.abs(p_c - p_t).max())
        max_abs = max(max_abs, d)
        same_argmax = int(p_c.argmax()) == int(p_t.argmax())
        argmax_agree += int(same_argmax)
        n_legal = int(mask.sum())
        ov = None
        if n_legal >= 5:
            ov = len(set(np.argsort(-p_c)[:5].tolist())
                     & set(np.argsort(-p_t)[:5].tolist())) / 5.0
            top5_sum += ov
            top5_n += 1
        # Illegal actions must be exactly zero on BOTH sides — a nonzero here would
        # mean the mask never reached one of the paths.
        assert float(p_c[~mask].sum()) == 0.0 and float(p_t[~mask].sum()) == 0.0
        per_pos.append({"pos_id": row.get("pos_id"), "ply": row.get("ply"),
                        "phase": row.get("phase"), "n_legal": n_legal,
                        "max_abs": d, "argmax_agree": same_argmax, "top5_overlap": ov})

    agree_frac = argmax_agree / len(rows)
    top5_mean = (top5_sum / top5_n) if top5_n else None

    # ---- latency: batch-1, both backends, on THIS box today. Feeds the r-model.
    W = net.window_size
    ex_board = np.ascontiguousarray(
        np.random.default_rng(0).standard_normal(
            (1, arch["n_input_channels"], W, W)), dtype=np.float32)
    ex_scalars = np.ascontiguousarray(
        np.random.default_rng(1).standard_normal(
            (1, arch["n_scalar_features"])), dtype=np.float32)
    tb, ts = torch.from_numpy(ex_board), torch.from_numpy(ex_scalars)

    lat = {}
    with torch.no_grad():
        for _ in range(a.latency_warmup):
            net.forward_policy_only(tb, ts)
        times = []
        for _ in range(a.latency_iters):
            t0 = time.perf_counter()
            net.forward_policy_only(tb, ts)
            times.append((time.perf_counter() - t0) * 1e3)
    lat["torch_cpu_policy_only"] = _stats(times)

    feed = {BOARD_INPUT: ex_board, SCALARS_INPUT: ex_scalars}
    for _ in range(a.latency_warmup):
        model.predict(feed)
    times = []
    for _ in range(a.latency_iters):
        t0 = time.perf_counter()
        model.predict(feed)
        times.append((time.perf_counter() - t0) * 1e3)
    lat[f"coreml_{a.compute_units}"] = _stats(times)

    # NOTE the honest framing: this is the RAW predict, i.e. what the gate's r-model
    # calls forward_ms. The evaluator adds the encode + host softmax on top, and those
    # are charged to the SEARCH in that model (the torch backend pays them too), so
    # they are deliberately outside this timer.
    passed = {
        "argmax_agreement": agree_frac >= a.min_argmax_agree,
        "top5_overlap": (top5_mean is None or top5_mean >= a.min_top5_overlap),
        "policy_max_abs": max_abs <= a.max_policy_abs,
    }
    verdict = "PASS" if all(passed.values()) else "FAIL"

    result = {
        "schema": "carcassonne-coreml-verify/v1",
        "kind": "coreml_vs_torch_policy_fidelity",
        "claim": "CL-067",
        "verdict": verdict,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machine": {"platform": platform.platform(), "machine": platform.machine(),
                    "python": sys.version.split()[0], "node": platform.node()},
        "checkpoint": {"path": str(a.checkpoint), "arch": arch},
        "model": {"path": str(a.model), "compute_units": a.compute_units,
                  "input_shapes": getattr(model, "carc_input_shapes", {})},
        "positions": {"path": str(a.positions), "n": len(rows)},
        "fidelity": {
            "policy_max_abs": max_abs,
            "legal_argmax_agreement": agree_frac,
            "argmax_agree_count": argmax_agree,
            "top5_overlap_mean": top5_mean,
            "top5_positions": top5_n,
        },
        "thresholds": {"min_argmax_agree": a.min_argmax_agree,
                       "min_top5_overlap": a.min_top5_overlap,
                       "max_policy_abs": a.max_policy_abs},
        "passed": passed,
        "latency_batch1": lat,
        "per_position": per_pos,
        "note": "Fidelity + latency ONLY. This is NOT a strength result and NOT the "
                "equal-wall-clock cell; it is the precondition for running it. The "
                "search-side cost (ms/sim) that the r-model divides by must be measured "
                "separately on the same box — see EQTIME_ANE_CELL_RUNBOOK.md §2.",
    }

    print(f"\n  policy max-abs            {max_abs:.3e}   "
          f"(<= {a.max_policy_abs:g}? {'ok' if passed['policy_max_abs'] else 'FAIL'})")
    print(f"  legal-argmax agreement    {agree_frac:.4f}   "
          f"({argmax_agree}/{len(rows)}; >= {a.min_argmax_agree}? "
          f"{'ok' if passed['argmax_agreement'] else 'FAIL'})")
    print(f"  top-5 overlap (mean)      "
          f"{'n/a' if top5_mean is None else f'{top5_mean:.4f}'}   "
          f"(over {top5_n} positions; >= {a.min_top5_overlap}? "
          f"{'ok' if passed['top5_overlap'] else 'FAIL'})")
    for k, v in lat.items():
        print(f"  {k:<28} mean {v['mean_ms']:.3f} ms  p50 {v['p50_ms']:.3f}  "
              f"p90 {v['p90_ms']:.3f}")
    print(f"\n  VERDICT: {verdict}")

    out = a.out or (HERE / "results" /
                    f"verify_coreml_{platform.node().split('.')[0]}_"
                    f"{time.strftime('%Y%m%dT%H%M%S')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str))
    print(f"verify_coreml_evaluator: wrote {out}")
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
