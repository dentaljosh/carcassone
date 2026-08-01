"""G7 on-device probe — the Chaquopy half of the P7 gate.

⚠️ DIAGNOSTIC ONLY. Nothing in the app imports this module: it is driven from the
instrumented test ``RustPortDeviceTest.kt`` and from nothing else. It never
touches ``android_bridge``'s session, never writes a save, and changes no default.
It ships in the APK because Chaquopy's source asset is the only way to get a
Python module onto the device, and it is small.

WHY IT EXISTS AT ALL
--------------------
Three of the four G7 device legs need things that only exist INSIDE the app's
Python environment and cannot be reached from ``adb shell``:

* leg 1b — the device's **numpy**. ``np.exp`` on a float64 ndarray is numpy's OWN
  SIMD kernel, not libm's ``exp``, so the native ``bionic_libm_probe`` leg (which
  answers ``math.tanh``/``math.expm1``/``math.exp``) cannot answer it. G0 §3
  measured np.exp's bits to be ISA-dependent, so aarch64 has to be measured.
* legs 3/4 — s/move and thermal soak must run through the same ``carc_rs`` wheel
  Chaquopy installs, on the phone's own governor, not a shell binary.
* leg 2 — the replay identity claim is about the WHEEL, so it must run against
  the wheel.

Every function returns a JSON string. The Kotlin side only ferries them to a file.
"""
from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

FLAVORS = ("msun", "msun_fma", "glibc", "glibc_fma")


def _import_carc_rs():
    import carc_rs
    return carc_rs


# --------------------------------------------------------------------------- #
# leg 1b — the device's numpy + math vs every compat flavour                    #
# --------------------------------------------------------------------------- #
def _ulp_diff(a, b):
    import numpy as np

    ai = a.view(np.int64).astype(np.int64)
    bi = b.view(np.int64).astype(np.int64)
    ai = np.where(ai < 0, np.int64(-(2 ** 63)) - ai, ai)
    bi = np.where(bi < 0, np.int64(-(2 ** 63)) - bi, bi)
    return np.abs(ai - bi).astype(np.uint64)


def _leg(name, want, got):
    import numpy as np

    same = want.view(np.uint64) == got.view(np.uint64)
    n_mis = int((~same).sum())
    d = _ulp_diff(want, got)
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


def libm_report(npz_path: str, fuzz: int = 2_000_000, seed: int = 20260731) -> str:
    """Is the DEVICE's np.exp / math.tanh / math.expm1 one of the ported flavours?

    Mirrors ``scripts/rustport/harness_transcendental.py::compare`` exactly, so the
    numbers line up with the desktop and fleet legs field for field.
    """
    import numpy as np

    carc_rs = _import_carc_rs()
    d = np.load(npz_path)
    z = np.ascontiguousarray(d["z"], dtype=np.float64)
    targ = np.ascontiguousarray(d["tanh_arg"], dtype=np.float64)

    def rs_exp(x, fma):
        return np.frombuffer(carc_rs.exp64_buf(x.tobytes(), fma), dtype=np.float64)

    def rs_tanh(x, fl):
        return np.frombuffer(carc_rs.tanh64_buf(x.tobytes(), fl), dtype=np.float64)

    def rs_expm1(x, fl):
        return np.frombuffer(carc_rs.expm1_64_buf(x.tobytes(), fl), dtype=np.float64)

    legs = {}
    # np.exp called EXACTLY as heuristic_prior_mcts.evaluator calls it: on a
    # float64 ndarray, so numpy dispatches its own kernel.
    want_exp = np.exp(z)
    legs["corpus_exp_vs_exp64"] = _leg("exp64", want_exp, rs_exp(z, False))
    legs["corpus_exp_vs_exp64_fma"] = _leg("exp64_fma", want_exp, rs_exp(z, True))

    want_tanh = np.array([math.tanh(v) for v in targ], dtype=np.float64)
    for fl in FLAVORS:
        legs[f"corpus_tanh_vs_tanh64_{fl}"] = _leg(f"tanh64[{fl}]", want_tanh,
                                                   rs_tanh(targ, fl))
    eargs = np.ascontiguousarray(
        np.concatenate([2 * np.abs(targ), -2 * np.abs(targ)]), dtype=np.float64)
    want_expm1 = np.array([math.expm1(v) for v in eargs], dtype=np.float64)
    for fl in FLAVORS:
        legs[f"corpus_expm1_vs_expm1_{fl}"] = _leg(f"expm1[{fl}]", want_expm1,
                                                   rs_expm1(eargs, fl))
    # Not the production call, but G0 §3 found np.tanh SIMD-dispatched and
    # unequal to math.tanh on x86; re-measuring it here keeps anyone from
    # "fixing" the difference into a false equivalence on ARM.
    legs["corpus_nptanh_vs_mathtanh"] = _leg("np.tanh", want_tanh, np.tanh(targ))

    # ---- fuzz: the leg that actually discriminates ------------------------
    # G0's cautionary tale: msun_fma passed the corpus and failed the fuzz, so a
    # corpus-only gate would have shipped a latent divergence.
    rng = np.random.default_rng(seed)
    acc = {}
    done = 0
    chunk = 250_000
    t0 = time.time()
    while done < fuzz:
        k = min(chunk, fuzz - done)
        zx = np.ascontiguousarray(rng.uniform(-100.0, 0.0, k), dtype=np.float64)
        tx = np.ascontiguousarray(rng.uniform(-20.0, 20.0, k), dtype=np.float64)
        we = np.exp(zx)
        wt = np.array([math.tanh(v) for v in tx], dtype=np.float64)
        pairs = [("exp64", we, rs_exp(zx, False)),
                 ("exp64_fma", we, rs_exp(zx, True))]
        pairs += [(f"tanh64[{f}]", wt, rs_tanh(tx, f)) for f in FLAVORS]
        for name, want, got in pairs:
            r = _leg(name, want, got)
            a = acc.setdefault(name, {"n": 0, "n_bit_mismatch": 0, "max_ulp": 0})
            a["n"] += r["n"]
            a["n_bit_mismatch"] += r["n_bit_mismatch"]
            a["max_ulp"] = max(a["max_ulp"], r["max_ulp"])
        done += k
    for a in acc.values():
        a["bit_exact"] = a["n_bit_mismatch"] == 0
        a["frac_bit_mismatch"] = a["n_bit_mismatch"] / a["n"] if a["n"] else 0.0
    legs["fuzz"] = acc

    exp_hit = [k for k in ("corpus_exp_vs_exp64", "corpus_exp_vs_exp64_fma")
               if legs[k]["bit_exact"]]
    tanh_hit = [k[len("corpus_tanh_vs_tanh64_"):] for k in legs
                if k.startswith("corpus_tanh_vs_tanh64_") and legs[k]["bit_exact"]]
    expm1_hit = [k[len("corpus_expm1_vs_expm1_"):] for k in legs
                 if k.startswith("corpus_expm1_vs_expm1_") and legs[k]["bit_exact"]]
    fuzz_exp = [k for k in ("exp64", "exp64_fma") if acc.get(k, {}).get("bit_exact")]
    fuzz_tanh = [k[len("tanh64["):-1] for k in acc
                 if k.startswith("tanh64[") and acc[k]["bit_exact"]]
    return json.dumps({
        "half": "chaquopy (device numpy + math)",
        "numpy": __import__("numpy").__version__,
        "python": sys.version,
        "machine": platform.machine(),
        "fuzz_n_per_impl": fuzz,
        "fuzz_wall_s": round(time.time() - t0, 1),
        "legs": legs,
        "verdict": {
            "corpus_np_exp_bit_exact_impls": exp_hit,
            "corpus_math_tanh_bit_exact_flavors": tanh_hit,
            "corpus_math_expm1_bit_exact_flavors": expm1_hit,
            "fuzz_np_exp_bit_exact_impls": fuzz_exp,
            "fuzz_math_tanh_bit_exact_flavors": fuzz_tanh,
            "exp_surviving_both": [f for f in exp_hit
                                   if f.replace("corpus_exp_vs_", "") in fuzz_exp],
            "tanh_surviving_both": [f for f in tanh_hit if f in fuzz_tanh],
            # The primary acceptance criterion of the build spec, evaluated for
            # THIS platform. False routes to the pre-registered fallback; it is a
            # finding to report, not a failure to hide.
            "platform_parity_achieved": bool(exp_hit) and bool(tanh_hit),
        },
    })


# --------------------------------------------------------------------------- #
# knob plumbing shared by legs 2-4                                              #
# --------------------------------------------------------------------------- #
def _leaf_cfg(knobs):
    carc_rs = _import_carc_rs()
    lc = knobs["leaf_cfg"]
    cfg = carc_rs.LeafConfigRs(
        [(int(a), float(b)) for a, b in lc["closure_p"]],
        float(lc["bonus_cap"]),
        float(lc["opp_bonus_cap"]),
        float(lc["meeple_k"]),
        None if lc["v29_meeple_curve"] is None else [float(x) for x in lc["v29_meeple_curve"]],
        float(lc["soft_cap_slope"]),
        float(lc["opp_soft_cap_slope"]),
        float(lc["v29_meeple_return_k"]),
        float(lc["v29_farm_flip_k"]),
        bool(lc["bag_close"]),
        bool(lc["tile_counting_closure"]),
        float(lc["closure_continuous_slack"]),
    )
    # Two independent paths to the champion leaf: the YAML-derived one above and
    # the Rust-side constant. A green gate against the WRONG leaf is worse than a
    # red one (P4's war story), so they are compared, not assumed.
    ref = carc_rs.LeafConfigRs.curve125()
    if repr(cfg) != repr(ref):
        raise RuntimeError(
            f"device leaf mismatch:\n  from knobs.json: {cfg!r}\n  curve125():      {ref!r}")
    return cfg


def _search_cfg(knobs, sims, exp_fma, tanh_flavor):
    carc_rs = _import_carc_rs()
    return carc_rs.SearchConfigRs(
        _leaf_cfg(knobs),
        int(sims),
        float(knobs["c_puct"]),
        float(knobs["tau_p"]),
        float(knobs["value_norm"]),
        float(knobs["score_norm_scale"]),
        str(knobs["leaf_quantize"]),
        str(knobs["final_select"]),
        None,            # fpu_reduction: NeuralMCTS default (legacy q=0)
        1.0,             # c_lcb (inert unless final_select == "lcb")
        bool(exp_fma),
        str(tanh_flavor),
        False,
    )


def _agent(knobs, sims, k_dets, seed, threads, exp_fma, tanh_flavor,
           exact_budget=100_000):
    carc_rs = _import_carc_rs()
    return carc_rs.FairAgentRs(
        _search_cfg(knobs, sims, exp_fma, tanh_flavor),
        k_dets=int(k_dets),
        seed=int(seed),
        min_pooled_visits=2.0,
        exact_endgame=True,
        exact_max_k=2,
        # The bridge's ANDROID_EXACT_BUDGET, not the desktop 2e6: a phone must
        # never be able to hang uncancellably inside a solve.
        exact_budget=int(exact_budget),
        tt_cap=0,
        chance_drop="type",
        threads=int(threads),
    )


# --------------------------------------------------------------------------- #
# leg 2 — replay identity against the frozen desktop digests                    #
# --------------------------------------------------------------------------- #
def replay_report(expect_path: str) -> str:
    carc_rs = _import_carc_rs()
    recs = json.loads(Path(expect_path).read_text())
    out = []
    t0 = time.time()
    for r in recs:
        g = carc_rs.MirrorState.from_seed(str(r["deck_seed"]),
                                          start_rule=r["start_rule"])
        first_bad = None
        shas = []
        for i, a in enumerate(r["actions"]):
            g.advance(int(a))
            sha = hashlib.sha256(g.string_repr().encode()).hexdigest()
            shas.append(sha)
            exp = r["expect"]["plies"][i]
            if first_bad is None and (sha != exp["repr_sha"]
                                      or list(g.scores()) != exp["scores"]):
                first_bad = {"ply": i, "want_sha": exp["repr_sha"], "got_sha": sha,
                             "want_scores": exp["scores"], "got_scores": list(g.scores())}
        chain = hashlib.sha256("".join(shas).encode()).hexdigest()
        out.append({
            "name": r["name"],
            "n_plies": len(shas),
            "chain_sha_match": chain == r["expect"]["chain_sha"],
            "final_scores_match": list(g.scores()) == r["expect"]["final_scores"],
            "terminal_match": bool(g.is_terminal()) == r["expect"]["is_terminal"],
            "first_divergent_ply": first_bad,
        })
    n_ply = sum(o["n_plies"] for o in out)
    ok = all(o["chain_sha_match"] and o["final_scores_match"] and o["terminal_match"]
             for o in out)
    return json.dumps({
        "records": out,
        "n_records": len(out),
        "n_plies": n_ply,
        "wall_s": round(time.time() - t0, 1),
        "all_identical": ok,
    })


# --------------------------------------------------------------------------- #
# legs 3/4 — s/move battery and thermal soak                                    #
# --------------------------------------------------------------------------- #
def _thermal() -> dict:
    """Best-effort CPU thermal-zone read. Unreadable on a locked-down device, so
    the soak's real throttle evidence is the s/move CURVE, not this."""
    out = {}
    try:
        for zone in Path("/sys/class/thermal").glob("thermal_zone*"):
            try:
                t = (zone / "type").read_text().strip()
                v = int((zone / "temp").read_text().strip())
                if "cpu" in t.lower() or "tsens" in t.lower() or "soc" in t.lower():
                    out[t] = v / 1000.0
            except Exception:  # noqa: BLE001
                continue
    except Exception:  # noqa: BLE001
        pass
    return out


def bench_report(knobs_path: str, battery_path: str, *, sims: int, k_dets: int,
                 threads: int, exp_fma: bool, tanh_flavor: str,
                 n: int = 0, seed: int = 12345) -> str:
    """Median s/move over the midgame battery at one budget.

    One agent per position, replayed from ``(deck_seed, prefix)`` — no board state
    is ever serialised, so this cannot drift from the engine of record.
    """
    import statistics

    knobs = json.loads(Path(knobs_path).read_text())
    positions = json.loads(Path(battery_path).read_text())
    if n:
        positions = positions[:n]
    rows = []
    for i, p in enumerate(positions):
        ag = _agent(knobs, sims, k_dets, seed + i, threads, exp_fma, tanh_flavor)
        ag.start_game_from_seed(str(p["deck_seed"]))
        for a in p["prefix"]:
            ag.advance(int(a))
        t0 = time.perf_counter()
        action = ag.choose_action()
        dt = time.perf_counter() - t0
        st = ag.stats()
        rows.append({
            "name": p["name"],
            "s": round(dt, 4),
            "action": int(action),
            "phase": ag.phase(),
            "k_remaining": ag.k_remaining(),
            "latched": bool(st.get("latched", False)),
        })
    secs = [r["s"] for r in rows]
    return json.dumps({
        "config": {"sims": sims, "k_dets": k_dets, "total_sims": sims * k_dets,
                   "threads": threads, "exp_fma": exp_fma,
                   "tanh_flavor": tanh_flavor, "n_positions": len(rows)},
        "s_per_move": {
            "median": round(statistics.median(secs), 4),
            "mean": round(statistics.fmean(secs), 4),
            "min": round(min(secs), 4),
            "max": round(max(secs), 4),
            "p90": round(sorted(secs)[max(0, int(0.9 * len(secs)) - 1)], 4),
        },
        "thermal_after": _thermal(),
        "rows": rows,
    })


def soak_report(knobs_path: str, battery_path: str, *, sims: int, k_dets: int,
                threads: int, exp_fma: bool, tanh_flavor: str,
                moves: int = 50, seed: int = 777) -> str:
    """50 consecutive moves from ONE game — the throttle curve.

    A battery re-seats the agent every position and lets the SoC breathe; a soak
    is the thing that actually heats a phone, so this is the leg that decides
    whether the median above survives real play.
    """
    knobs = json.loads(Path(knobs_path).read_text())
    positions = json.loads(Path(battery_path).read_text())
    p = positions[0]
    ag = _agent(knobs, sims, k_dets, seed, threads, exp_fma, tanh_flavor)
    ag.start_game_from_seed(str(p["deck_seed"]))
    rows = []
    t_start = time.perf_counter()
    for i in range(moves):
        if ag.is_terminal():
            break
        t0 = time.perf_counter()
        try:
            ag.choose_and_advance()
        except Exception as exc:  # noqa: BLE001
            rows.append({"i": i, "error": f"{type(exc).__name__}: {exc}"})
            break
        rows.append({
            "i": i,
            "s": round(time.perf_counter() - t0, 4),
            "t_elapsed": round(time.perf_counter() - t_start, 2),
            "temp": _thermal(),
        })
    good = [r["s"] for r in rows if "s" in r]
    first10 = good[:10]
    last10 = good[-10:]
    return json.dumps({
        "config": {"sims": sims, "k_dets": k_dets, "total_sims": sims * k_dets,
                   "threads": threads, "moves_requested": moves,
                   "moves_done": len(good)},
        "total_wall_s": round(time.perf_counter() - t_start, 1),
        # The throttle number: how much slower the tail is than the head.
        "first10_mean_s": round(sum(first10) / len(first10), 4) if first10 else None,
        "last10_mean_s": round(sum(last10) / len(last10), 4) if last10 else None,
        "throttle_ratio": (round((sum(last10) / len(last10)) /
                                 (sum(first10) / len(first10)), 3)
                           if first10 and last10 else None),
        "curve": rows,
    })


def environment_report() -> str:
    """What actually loaded on this device — the first thing to read if a leg
    behaves oddly (e.g. carc_rs missing means the wheel never installed)."""
    info = {"python": sys.version, "machine": platform.machine(),
            "platform": platform.platform()}
    for mod in ("numpy", "carc_rs", "carc_cy"):
        try:
            m = __import__(mod)
            info[mod] = {"ok": True,
                         "version": getattr(m, "__version__", None),
                         "file": getattr(m, "__file__", None)}
        except Exception as exc:  # noqa: BLE001
            info[mod] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        import carc_rs
        info["libm_flavors"] = list(carc_rs.libm_flavors())
        info["tile_data_digests"] = list(carc_rs.tile_data_digests())
    except Exception:  # noqa: BLE001
        pass
    info["thermal"] = _thermal()
    return json.dumps(info)
