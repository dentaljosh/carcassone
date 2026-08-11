#!/usr/bin/env python3
"""G0 gate (strategic) — is the platform's ``exp``/``tanh`` the one we ported?

This is the gate that *decides the libm strategy*, and unlike the other three G0
gates it is a MEASUREMENT, not a pass/fail port check. ``carc-core::compat::
libm_compat`` is a faithful port of two named upstreams (ARM optimized-routines
``exp``; fdlibm ``tanh``/``expm1``). Whether a given platform's ``np.exp`` and
``math.tanh`` actually *are* those upstreams is an empirical question with a
different answer per box, per libc, and per SIMD dispatch level.

The spec pre-registers the fallback if parity proves unattainable, so a mismatch
here is a finding, not a failure. What matters is that the numbers are real.

Stages
------
harvest   Replay ``measurement/champ_action_logs/champ_games.jsonl`` through the
          PRODUCTION prior evaluator and collect the actual arguments the two
          call sites see:
            * ``z``        = (Delta_leaf / tau_p) - max(...)  -> fed to ``np.exp``
            * ``tanh_arg`` = leaf / value_norm                -> fed to ``math.tanh``
          Both parent and child leaf values are recorded for the tanh site: every
          child of an expanded node is itself expanded during search, so the
          child leaves are genuine tanh arguments.
          Written to ``measurement/rustport_p0/transcendental_inputs.npz``.

compare   ``np.exp`` (called EXACTLY as the code calls it: on a float64 ndarray,
          so numpy's own SIMD dispatch applies) and scalar ``math.tanh`` vs
          ``exp64`` / ``exp64_fma`` / ``tanh64``, on
            (a) the harvested corpus, and
            (b) a uniform-bit-pattern fuzz over the realistic ranges
                (z in [-100, 0], tanh arg in [-20, 20]).
          Reports total, bit-mismatches, max ulp, and the mismatch histogram.

dispatch  Probe which numpy implementation actually ran: CPU baseline/dispatch
          lists, and a re-run under ``NPY_DISABLE_CPU_FEATURES`` to see whether
          disabling SIMD changes ``np.exp``'s bits.

Fleet legs
----------
This script is self-contained: copy the repo (or just this file plus the .npz)
to another box and run

    python3 harness_transcendental.py compare --inputs transcendental_inputs.npz

with either the ``carc_rs`` dev wheel importable, or -- on a box with no maturin
-- ``--via-cli /path/to/carc-cli`` (the ``carc-cli exp|tanh`` subcommands speak
hex float bits on stdin/stdout for exactly this reason).

Usage
-----
    .venv/bin/python scripts/rustport/harness_transcendental.py all
    .venv/bin/python scripts/rustport/harness_transcendental.py harvest --games 60
    .venv/bin/python scripts/rustport/harness_transcendental.py compare --fuzz 100000000
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _g0_common import OUTDIR, REPO, verdict, write_result  # noqa: E402

INPUTS = OUTDIR / "transcendental_inputs.npz"
CORPUS = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"


# --------------------------------------------------------------------------- #
# ulp helper
# --------------------------------------------------------------------------- #
def ulp_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Elementwise |a - b| in ULPs, via the monotone-int mapping of IEEE-754."""
    ai = a.view(np.int64).astype(np.int64)
    bi = b.view(np.int64).astype(np.int64)
    # map negatives onto a monotone ordering: INT64_MIN - v
    ai = np.where(ai < 0, np.int64(-(2**63)) - ai, ai)
    bi = np.where(bi < 0, np.int64(-(2**63)) - bi, bi)
    return np.abs(ai - bi).astype(np.uint64)


# --------------------------------------------------------------------------- #
# harvest
# --------------------------------------------------------------------------- #
def harvest(n_games: int, max_z: int) -> dict:
    sys.path.insert(0, str(REPO / "scripts"))
    from carcassonne_ai import champion_factory, flat_leaf
    from carcassonne_ai.heuristic_prior_mcts import make_heuristic_prior_evaluator
    from measurement_infra.root_replay import load_games, replay_actions

    cfg = champion_factory.production_prior_cfg()
    leaf_cfg = cfg.resolved_leaf_cfg()
    bag_close = bool(getattr(leaf_cfg, "bag_close", False))
    tau, norm = float(cfg.tau_p), float(cfg.value_norm)

    games = load_games(CORPUS)
    zs: list[np.ndarray] = []
    tanh_parent: list[float] = []
    tanh_child: list[np.ndarray] = []
    n_z = 0
    n_ply = 0
    t0 = time.time()

    for gi, rec in enumerate(games[:n_games]):
        game, board = replay_actions(rec.deck_seed, rec.actions, 0)
        ev = make_heuristic_prior_evaluator(game, cfg)
        for a in rec.actions:
            legal, zraw = ev.root_logits(board)
            if legal.size:
                z = zraw - zraw.max()          # EXACTLY what evaluator() feeds np.exp
                zs.append(np.ascontiguousarray(z, dtype=np.float64))
                n_z += z.size
                lp = flat_leaf.flat_virtual_score_v2_float(
                    board.state, board.state.current_player, leaf_cfg, bag_close)
                tanh_parent.append(lp / norm)
                # child leaves are the tanh args of the next expansion
                tanh_child.append((lp + zraw * tau) / norm)
            board, _ = game.get_next_state(board, int(a))
            n_ply += 1
        if n_z >= max_z:
            break

    z_all = np.concatenate(zs) if zs else np.zeros(0)
    t_all = np.concatenate([np.asarray(tanh_parent, dtype=np.float64)] + tanh_child)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        INPUTS,
        z=z_all,
        tanh_arg=t_all,
        tanh_parent=np.asarray(tanh_parent, dtype=np.float64),
    )
    meta = {
        "corpus": str(CORPUS.relative_to(REPO)),
        "games_used": min(n_games, gi + 1),
        "plies": n_ply,
        "n_z": int(z_all.size),
        "n_tanh_arg": int(t_all.size),
        "tau_p": tau,
        "value_norm": norm,
        "leaf_quantize": cfg.leaf_quantize,
        "z_range": [float(z_all.min()), float(z_all.max())] if z_all.size else None,
        "z_distinct": int(np.unique(z_all).size),
        "tanh_range": [float(t_all.min()), float(t_all.max())],
        "tanh_distinct": int(np.unique(t_all).size),
        "wall_s": round(time.time() - t0, 1),
        "path": str(INPUTS.relative_to(REPO)),
    }
    print(json.dumps(meta, indent=2))
    return meta


# --------------------------------------------------------------------------- #
# rust callers
# --------------------------------------------------------------------------- #
class RustViaWheel:
    kind = "wheel"

    def __init__(self):
        import carc_rs

        self.m = carc_rs
        self.version = carc_rs.__version__

    def exp(self, x: np.ndarray, fma: bool) -> np.ndarray:
        out = self.m.exp64_buf(x.tobytes(), fma)
        return np.frombuffer(out, dtype=np.float64)

    def tanh(self, x: np.ndarray, flavor: str) -> np.ndarray:
        out = self.m.tanh64_buf(x.tobytes(), flavor)
        return np.frombuffer(out, dtype=np.float64)

    def expm1(self, x: np.ndarray, flavor: str) -> np.ndarray:
        out = self.m.expm1_64_buf(x.tobytes(), flavor)
        return np.frombuffer(out, dtype=np.float64)

    @property
    def flavors(self):
        return list(self.m.libm_flavors())


class RustViaCli:
    kind = "cli"

    def __init__(self, path: str):
        self.path = path
        self.version = subprocess.run(
            [path, "selftest"], capture_output=True, text=True, check=True
        ).stdout.strip()

    def _run(self, args, x):
        payload = "\n".join(f"{v:016x}" for v in x.view(np.uint64)) + "\n"
        out = subprocess.run([self.path, *args], input=payload,
                             capture_output=True, text=True, check=True).stdout
        bits = np.array([int(t, 16) for t in out.split()], dtype=np.uint64)
        return bits.view(np.float64)

    def exp(self, x, fma):
        return self._run(["exp", "--fma"] if fma else ["exp"], x)

    def tanh(self, x, flavor: str):
        return self._run(["tanh", "--flavor", flavor], x)

    def expm1(self, x, flavor: str):
        return self._run(["expm1", "--flavor", flavor], x)

    @property
    def flavors(self):
        return ["msun", "msun_fma", "glibc", "glibc_fma"]


# --------------------------------------------------------------------------- #
# compare
# --------------------------------------------------------------------------- #
def _leg(name: str, want: np.ndarray, got: np.ndarray) -> dict:
    """Bit / ulp summary for one implementation against the reference."""
    same = want.view(np.uint64) == got.view(np.uint64)
    n_mis = int((~same).sum())
    d = ulp_diff(want, got)
    hist = {}
    if n_mis:
        vals, cnts = np.unique(d[~same], return_counts=True)
        hist = {int(v): int(c) for v, c in zip(vals[:16], cnts[:16])}
    return {
        "impl": name,
        "n": int(want.size),
        "n_bit_mismatch": n_mis,
        "frac_bit_mismatch": (n_mis / want.size) if want.size else 0.0,
        "max_ulp": int(d.max()) if want.size else 0,
        "mean_ulp": float(d.mean()) if want.size else 0.0,
        "ulp_histogram_of_mismatches": hist,
        "bit_exact": n_mis == 0,
    }


def _fuzz_block(rng, lo, hi, k) -> np.ndarray:
    """Uniform over the value range plus uniform-bit-pattern draws clipped in."""
    half = k // 2
    a = rng.uniform(lo, hi, half)
    bits = rng.integers(0, 1 << 63, k - half, dtype=np.uint64)
    b = bits.view(np.float64)
    b = b[np.isfinite(b)]
    b = np.clip(b, lo, hi)
    if b.size < k - half:
        b = np.concatenate([b, rng.uniform(lo, hi, k - half - b.size)])
    return np.ascontiguousarray(np.concatenate([a, b]), dtype=np.float64)


def compare(inputs: Path, fuzz_n: int, chunk: int, via_cli: str | None,
            seed: int) -> dict:
    rust = RustViaCli(via_cli) if via_cli else RustViaWheel()
    d = np.load(inputs)
    z = np.ascontiguousarray(d["z"], dtype=np.float64)
    targ = np.ascontiguousarray(d["tanh_arg"], dtype=np.float64)

    res = {"rust_backend": rust.kind, "rust_version": str(rust.version), "legs": {}}

    # ---- (a) harvested corpus --------------------------------------------
    # np.exp called the way heuristic_prior_mcts.evaluator calls it: on a
    # float64 ndarray (numpy dispatches its own SIMD kernel, NOT libm's exp).
    want_exp = np.exp(z)
    res["legs"]["corpus_exp_vs_exp64"] = _leg("exp64", want_exp, rust.exp(z, False))
    res["legs"]["corpus_exp_vs_exp64_fma"] = _leg("exp64_fma", want_exp, rust.exp(z, True))
    # math.tanh is a SCALAR libm call. Four platform hypotheses are priced --
    # msun{,_fma} is the bionic/Android side, glibc{,_fma} the desktop side.
    want_tanh = np.array([math.tanh(v) for v in targ], dtype=np.float64)
    for fl in rust.flavors:
        res["legs"][f"corpus_tanh_vs_tanh64_{fl}"] = _leg(
            f"tanh64[{fl}]", want_tanh, rust.tanh(targ, fl))
    res["legs"]["corpus_tanh_vs_tanh64"] = res["legs"]["corpus_tanh_vs_tanh64_glibc_fma"]
    # expm1 is tanh's kernel and the axis the whole tanh divergence lives on
    eargs = np.ascontiguousarray(
        np.concatenate([2 * np.abs(targ), -2 * np.abs(targ)]), dtype=np.float64)
    want_expm1 = np.array([math.expm1(v) for v in eargs], dtype=np.float64)
    for fl in rust.flavors:
        res["legs"][f"corpus_expm1_vs_expm1_{fl}"] = _leg(
            f"expm1[{fl}]", want_expm1, rust.expm1(eargs, fl))
    # cross-check: np.tanh (not the production call, but tells us if numpy's
    # vector tanh differs from libm's scalar one -- a trap for a future port)
    res["legs"]["corpus_nptanh_vs_mathtanh"] = _leg("np.tanh", want_tanh, np.tanh(targ))
    res["corpus"] = {
        "n_z": int(z.size), "n_tanh": int(targ.size),
        "z_range": [float(z.min()), float(z.max())],
        "z_distinct": int(np.unique(z).size),
        "tanh_range": [float(targ.min()), float(targ.max())],
        "tanh_distinct": int(np.unique(targ).size),
    }

    # ---- (b) range fuzz ---------------------------------------------------
    rng = np.random.default_rng(seed)
    keys = ["exp64", "exp64_fma"] + [f"tanh64[{f}]" for f in rust.flavors]
    acc = {k: {"n": 0, "n_bit_mismatch": 0, "max_ulp": 0, "sum_ulp": 0.0,
               "hist": {}} for k in keys}
    t0 = time.time()
    done = 0
    while done < fuzz_n:
        k = min(chunk, fuzz_n - done)
        zx = _fuzz_block(rng, -100.0, 0.0, k)
        tx = _fuzz_block(rng, -20.0, 20.0, k)
        we = np.exp(zx)
        wt = np.array([math.tanh(v) for v in tx], dtype=np.float64)
        legs = [("exp64", we, rust.exp(zx, False)),
                ("exp64_fma", we, rust.exp(zx, True))]
        legs += [(f"tanh64[{f}]", wt, rust.tanh(tx, f)) for f in rust.flavors]
        for key, want, got in legs:
            same = want.view(np.uint64) == got.view(np.uint64)
            dd = ulp_diff(want, got)
            a = acc[key]
            a["n"] += int(want.size)
            a["n_bit_mismatch"] += int((~same).sum())
            a["max_ulp"] = max(a["max_ulp"], int(dd.max()))
            a["sum_ulp"] += float(dd.sum())
            if (~same).any():
                vals, cnts = np.unique(dd[~same], return_counts=True)
                for v, c in zip(vals[:16], cnts[:16]):
                    a["hist"][int(v)] = a["hist"].get(int(v), 0) + int(c)
        done += k
        if done % (20 * chunk) == 0:
            print(f"  ... fuzz {done}/{fuzz_n} ({time.time() - t0:.0f}s)", file=sys.stderr)
    for key, a in acc.items():
        a["frac_bit_mismatch"] = a["n_bit_mismatch"] / a["n"] if a["n"] else 0.0
        a["mean_ulp"] = a["sum_ulp"] / a["n"] if a["n"] else 0.0
        a["bit_exact"] = a["n_bit_mismatch"] == 0
        a.pop("sum_ulp")
        a["ulp_histogram_of_mismatches"] = a.pop("hist")
    res["legs"]["fuzz"] = acc
    res["fuzz"] = {"n_per_impl": fuzz_n, "z_range": [-100.0, 0.0],
                   "tanh_range": [-20.0, 20.0], "wall_s": round(time.time() - t0, 1),
                   "seed": seed}
    return res


# --------------------------------------------------------------------------- #
# numpy dispatch probe
# --------------------------------------------------------------------------- #
PROBE = r"""
import json, sys
import numpy as np
from numpy._core import _multiarray_umath as mu
x = np.linspace(-100.0, 0.0, 4096, dtype=np.float64)
y = np.exp(x)
t = np.tanh(np.linspace(-20.0, 20.0, 4096, dtype=np.float64))
print(json.dumps({
    "baseline": getattr(mu, "__cpu_baseline__", None),
    "dispatch": getattr(mu, "__cpu_dispatch__", None),
    "features_on": [k for k, v in getattr(mu, "__cpu_features__", {}).items() if v],
    "exp_sha": __import__("hashlib").sha256(y.tobytes()).hexdigest()[:32],
    "tanh_sha": __import__("hashlib").sha256(t.tobytes()).hexdigest()[:32],
    "numpy": np.__version__,
}))
"""


def dispatch_probe() -> dict:
    out = {"variants": {}}
    variants = {
        "default": {},
        # numpy 2.x only accepts names from __cpu_dispatch__/__cpu_features__;
        # on x86 the dispatchable groups are X86_V3 (AVX2+FMA3) and X86_V4/AVX512*.
        "no_avx512": {"NPY_DISABLE_CPU_FEATURES": "X86_V4 AVX512F AVX512_SKX AVX512_ICL AVX512_SPR"},
        "no_x86_v3": {"NPY_DISABLE_CPU_FEATURES": "X86_V3 X86_V4 AVX512F AVX512_SKX AVX512_ICL AVX512_SPR"},
        "no_avx2_fma3": {"NPY_DISABLE_CPU_FEATURES": "AVX2 FMA3 AVX512F"},
    }
    for name, extra in variants.items():
        env = dict(os.environ, **extra)
        r = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                           text=True, env=env)
        if r.returncode != 0:
            out["variants"][name] = {"error": (r.stderr or "").strip()[-400:]}
            continue
        out["variants"][name] = json.loads(r.stdout)
    shas = {k: v.get("exp_sha") for k, v in out["variants"].items() if "exp_sha" in v}
    out["exp_bits_change_with_simd"] = len(set(shas.values())) > 1
    out["exp_sha_by_variant"] = shas
    tshas = {k: v.get("tanh_sha") for k, v in out["variants"].items() if "tanh_sha" in v}
    out["tanh_bits_change_with_simd"] = len(set(tshas.values())) > 1
    out["tanh_sha_by_variant"] = tshas
    try:
        import numpy as np

        cfg = np.show_config(mode="dicts")
        out["numpy_build"] = {
            "compilers": cfg.get("Compilers"),
            "simd_extensions": cfg.get("SIMD Extensions"),
        }
    except Exception as exc:
        out["numpy_build"] = f"unavailable: {exc}"
    return out


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["harvest", "compare", "dispatch", "all"])
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--max-z", type=int, default=200_000)
    ap.add_argument("--inputs", type=Path, default=INPUTS)
    ap.add_argument("--fuzz", type=int, default=100_000_000)
    ap.add_argument("--chunk", type=int, default=1_000_000)
    ap.add_argument("--via-cli", default=None,
                    help="path to the carc-cli binary (for boxes without maturin)")
    ap.add_argument("--seed", type=int, default=20260731)
    a = ap.parse_args()

    payload: dict = {}
    if a.stage in ("harvest", "all"):
        payload["harvest"] = harvest(a.games, a.max_z)
    if a.stage in ("dispatch", "all"):
        payload["dispatch"] = dispatch_probe()
    if a.stage in ("compare", "all"):
        payload["compare"] = compare(a.inputs, a.fuzz, a.chunk, a.via_cli, a.seed)

    if a.stage == "harvest":
        path = write_result("transcendental_harvest", payload)
        return verdict("transcendental_harvest", True,
                       f"{payload['harvest']['n_z']} z + "
                       f"{payload['harvest']['n_tanh_arg']} tanh args", path)

    path = write_result("transcendental", payload)

    # The verdict line reports the MEASUREMENT; PASS means "the port is
    # bit-identical to the platform at BOTH production sites", which is the
    # primary acceptance criterion. Anything else routes to the pre-registered
    # fallback and is stated as such.
    c = payload.get("compare", {})
    legs = c.get("legs", {})
    if not legs:
        return verdict("transcendental", True, "dispatch probe only", path)
    exp_hit = [k for k in ("corpus_exp_vs_exp64", "corpus_exp_vs_exp64_fma")
               if legs[k]["bit_exact"]]
    tanh_hit = [k[len("corpus_tanh_vs_tanh64_"):]
                for k in legs
                if k.startswith("corpus_tanh_vs_tanh64_") and legs[k]["bit_exact"]]
    expm1_hit = [k[len("corpus_expm1_vs_expm1_"):]
                 for k in legs
                 if k.startswith("corpus_expm1_vs_expm1_") and legs[k]["bit_exact"]]
    fuzz = payload["compare"]["legs"].get("fuzz", {})
    fuzz_exp_hit = [k for k in ("exp64", "exp64_fma") if fuzz.get(k, {}).get("bit_exact")]
    fuzz_tanh_hit = [k for k in fuzz if k.startswith("tanh64[") and fuzz[k]["bit_exact"]]
    ok = bool(exp_hit) and bool(tanh_hit)
    payload["verdict"] = {
        "corpus_exp_bit_exact_impls": exp_hit,
        "corpus_tanh_bit_exact_flavors": tanh_hit,
        "corpus_expm1_bit_exact_flavors": expm1_hit,
        "fuzz_exp_bit_exact_impls": fuzz_exp_hit,
        "fuzz_tanh_bit_exact_flavors": fuzz_tanh_hit,
        "platform_parity_achieved": ok,
    }
    write_result("transcendental", payload)
    detail = (
        f"corpus exp: bit-exact via {exp_hit or 'NONE'} "
        f"(exp64 {legs['corpus_exp_vs_exp64']['n_bit_mismatch']}/"
        f"{legs['corpus_exp_vs_exp64']['n']} max "
        f"{legs['corpus_exp_vs_exp64']['max_ulp']} ulp; exp64_fma "
        f"{legs['corpus_exp_vs_exp64_fma']['n_bit_mismatch']}/"
        f"{legs['corpus_exp_vs_exp64_fma']['n']}); "
        f"corpus tanh: bit-exact via {tanh_hit or 'NONE'}; "
        f"fuzz exp {fuzz_exp_hit or 'NONE'}, fuzz tanh {fuzz_tanh_hit or 'NONE'}"
    )
    return verdict("transcendental", ok, detail, path)


if __name__ == "__main__":
    raise SystemExit(main())
