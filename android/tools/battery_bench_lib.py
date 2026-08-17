#!/usr/bin/env python3
"""Host-side math + report engine for the on-device battery A/B bench.

``android/tools/battery_bench.sh`` owns everything adb; this module owns
everything testable: the ABAB schedule, current/voltage sign+unit
normalization, trapezoid energy integration, the move-hash identity gate, and
the per-arm summary/report. Pure functions throughout — the pytest suite is
``tests/android/test_battery_bench_lib.py``.

Sampler line format (written by the shell driver, device clock):

    <epoch_ms> <current_now_raw> <voltage_now_raw>

Sign convention: ``current_now`` polarity DIFFERS BY DEVICE (many report
negative while discharging, some positive). The bench runs strictly unplugged,
so discharge is known; the convention is detected from the median sample sign
and normalized so discharge power is positive. Units are assumed µA / µV
(the Pixel kernel convention) and sanity-checked: a voltage median outside
2.5–5.5 V at µV scale fails loudly rather than silently mis-scaling by 1000x.

CLI subcommands (used by the driver):
    schedule      print the interleaved run plan, one "rep arm tag" per line
    report        integrate + summarize; ABORTS (exit 2) on move-hash mismatch
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

SCHEMA = "carc-battery-bench-report/v1"

# µA * µV -> W
_UAUV_TO_W = 1e-12
# Voltage sanity window at µV scale (a Li-ion cell is ~3.0-4.5 V).
_V_LO_UV, _V_HI_UV = 2.5e6, 5.5e6
# Max tolerated gap between the window edge and the nearest sample (ms) before
# the integration is considered untrustworthy.
_MAX_EDGE_GAP_MS = 5000.0
_MIN_WINDOW_SAMPLES = 3


# --------------------------------------------------------------------------- #
# schedule
# --------------------------------------------------------------------------- #
def abab_schedule(arms: list[int], reps: int) -> list[tuple[int, int, str]]:
    """Interleaved (ABAB / ABCABC) plan: every rep cycles through ALL arms.

    Interleaving is the point: thermal drift, battery-SoC drift and background
    noise land on every arm rather than on whichever ran last.
    Returns ``[(rep, arm, tag), ...]`` in run order; tags are unique and
    filesystem-safe (``t<arm>_r<rep>``).
    """
    if reps < 1:
        raise ValueError(f"reps must be >= 1, got {reps}")
    if not arms:
        raise ValueError("arm list is empty")
    if len(set(arms)) != len(arms):
        raise ValueError(f"duplicate arms in {arms}")
    if any(a < 1 for a in arms):
        raise ValueError(f"arms must be >= 1 threads, got {arms}")
    return [(rep, arm, f"t{arm}_r{rep}")
            for rep in range(1, reps + 1) for arm in arms]


def parse_arm(spec) -> tuple[int, int]:
    """``"2"`` -> ``(2, 0)``; ``"2:16"`` -> ``(2, 16)``  (threads, tiearb_B).

    ``tiearb_B == 0`` is the CHAMPION AS DEPLOYED — no arbiter keyword reaches
    the rust search config. A positive B arms the tie arbiter at that many CRN
    worlds. Both arms drive the champion trajectory on device (see
    ``carc_bench``'s module doc), which is what keeps the move-hash gate valid
    across an axis whose whole purpose is to change picks.
    """
    s = str(spec).strip()
    threads, _, b = s.partition(":")
    try:
        t_i = int(threads)
        b_i = int(b) if b else 0
    except ValueError:
        raise ValueError(
            f"bad arm spec {spec!r} — want 'THREADS' or 'THREADS:TIEARB_B'")
    if t_i < 1:
        raise ValueError(f"arm threads must be >= 1, got {t_i} in {spec!r}")
    if b_i < 0:
        raise ValueError(f"arm tiearb_B must be >= 0, got {b_i} in {spec!r}")
    return t_i, b_i


def arm_tag(threads: int, tiearb_b: int, rep: int) -> str:
    """Filesystem-safe, unique, and self-describing: ``t2_r1`` / ``t2b16_r1``.

    The unarmed spelling is deliberately IDENTICAL to the pre-arbiter bench's,
    so a thread-count session's artifacts keep their old names.
    """
    return f"t{threads}{'' if tiearb_b <= 0 else f'b{tiearb_b}'}_r{rep}"


def arm_schedule(specs: list, reps: int) -> list[tuple[int, int, int, str]]:
    """Interleaved plan over (threads, tiearb_B) arms -> ``[(rep, t, b, tag)]``.

    The generalization of :func:`abab_schedule` to the arbiter axis; same
    interleaving rationale (thermal/SoC drift lands on every arm).
    """
    if reps < 1:
        raise ValueError(f"reps must be >= 1, got {reps}")
    if not specs:
        raise ValueError("arm list is empty")
    arms = [parse_arm(s) for s in specs]
    if len(set(arms)) != len(arms):
        raise ValueError(f"duplicate arms in {specs}")
    return [(rep, t, b, arm_tag(t, b, rep))
            for rep in range(1, reps + 1) for (t, b) in arms]


# --------------------------------------------------------------------------- #
# samples
# --------------------------------------------------------------------------- #
def parse_samples(text: str) -> list[tuple[float, float, float]]:
    """Parse sampler lines to ``[(t_ms, current_raw, voltage_raw)]``.

    Malformed lines (adb hiccups, partial writes) are skipped; order is
    enforced by sorting on the timestamp.
    """
    out: list[tuple[float, float, float]] = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            t, i, v = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue
        out.append((t, i, v))
    out.sort(key=lambda s: s[0])
    return out


def detect_sign(samples: list[tuple[float, float, float]]) -> int:
    """+1 if current_now is already positive while discharging, else -1.

    The bench refuses to run plugged in, so every sample is a discharge
    sample; the median sign IS the device's convention. A median of exactly 0
    (dead sampler) is refused.
    """
    if not samples:
        raise ValueError("no samples")
    med = statistics.median(s[1] for s in samples)
    if med == 0:
        raise ValueError("median current is 0 — sampler dead or device idle-clamped")
    return 1 if med > 0 else -1


def check_units(samples: list[tuple[float, float, float]]) -> None:
    """Fail loudly if voltage_now does not look like µV."""
    if not samples:
        raise ValueError("no samples")
    v_med = statistics.median(s[2] for s in samples)
    if not (_V_LO_UV <= v_med <= _V_HI_UV):
        raise ValueError(
            f"voltage_now median {v_med:g} is outside the µV sanity window "
            f"[{_V_LO_UV:g}, {_V_HI_UV:g}] — this device likely reports mV or "
            f"V; teach the normalizer its scale before trusting any joules")


def power_series(samples: list[tuple[float, float, float]],
                 sign: int) -> list[tuple[float, float]]:
    """``[(t_ms, watts)]`` with discharge power normalized positive."""
    return [(t, (sign * i) * v * _UAUV_TO_W) for (t, i, v) in samples]


def integrate_joules(power: list[tuple[float, float]],
                     t0_ms: float, t1_ms: float) -> float:
    """Trapezoid-integrate watts over [t0_ms, t1_ms] -> joules.

    Uses linear interpolation at the window edges when a neighbouring sample
    exists outside the window; refuses windows with too few samples or with an
    edge gap over ``_MAX_EDGE_GAP_MS`` (a died sampler must not silently
    under-report energy).
    """
    if t1_ms <= t0_ms:
        raise ValueError(f"bad window [{t0_ms}, {t1_ms}]")
    pts = [(t, w) for (t, w) in power if t0_ms <= t <= t1_ms]
    if len(pts) < _MIN_WINDOW_SAMPLES:
        raise ValueError(
            f"only {len(pts)} samples inside [{t0_ms:.0f}, {t1_ms:.0f}] "
            f"(need >= {_MIN_WINDOW_SAMPLES}) — sampler gap?")

    def _interp(ta: float, wa: float, tb: float, wb: float, t: float) -> float:
        if tb == ta:
            return wa
        return wa + (wb - wa) * (t - ta) / (tb - ta)

    before = [(t, w) for (t, w) in power if t < t0_ms]
    after = [(t, w) for (t, w) in power if t > t1_ms]
    if before:
        tb, wb = before[-1]
        pts.insert(0, (t0_ms, _interp(tb, wb, pts[0][0], pts[0][1], t0_ms)))
    elif pts[0][0] - t0_ms > _MAX_EDGE_GAP_MS:
        raise ValueError(
            f"first sample {pts[0][0] - t0_ms:.0f} ms after window start "
            f"(> {_MAX_EDGE_GAP_MS:.0f} ms) — sampler started late?")
    if after:
        ta, wa = after[0]
        pts.append((t1_ms, _interp(pts[-1][0], pts[-1][1], ta, wa, t1_ms)))
    elif t1_ms - pts[-1][0] > _MAX_EDGE_GAP_MS:
        raise ValueError(
            f"last sample {t1_ms - pts[-1][0]:.0f} ms before window end "
            f"(> {_MAX_EDGE_GAP_MS:.0f} ms) — sampler died?")

    joules = 0.0
    for (ta, wa), (tb, wb) in zip(pts, pts[1:]):
        joules += 0.5 * (wa + wb) * (tb - ta) / 1000.0
    return joules


def mean_watts(power: list[tuple[float, float]],
               t0_ms: float, t1_ms: float) -> float:
    return integrate_joules(power, t0_ms, t1_ms) / ((t1_ms - t0_ms) / 1000.0)


# --------------------------------------------------------------------------- #
# identity gate
# --------------------------------------------------------------------------- #
def check_hashes(runs: list[dict]) -> tuple[bool, dict[str, str]]:
    """The play-identity witness across arms.

    Every run of the SAME (seed, n_moves, budget) must report the same
    ``move_hash`` regardless of ``rust_threads`` — thread-count invariance of
    the rust search is proven upstream, so a mismatch means the arms did
    DIFFERENT WORK and the energy comparison is void. Returns
    ``(ok, {tag: hash})``.
    """
    by_tag = {str(r.get("tag")): str(r.get("move_hash")) for r in runs}
    if not by_tag:
        return False, by_tag
    if any(h in ("None", "") for h in by_tag.values()):
        return False, by_tag
    return len(set(by_tag.values())) == 1, by_tag


def _fail_runs(runs: list[dict]) -> list[dict]:
    return [r for r in runs if not r.get("ok")]


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #
def _mean_sd(xs: list[float]) -> tuple[float, float]:
    m = statistics.fmean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else float("nan")
    return m, sd


def run_arm(r: dict) -> tuple[int, int]:
    """``(rust_threads, tiearb_B)`` of one run JSON. Pre-arbiter runs -> B=0."""
    ta = r.get("tiearb") or {}
    b = int(ta.get("B", 0) or 0) if ta.get("enabled") else 0
    return int(r["rust_threads"]), b


def arm_key(threads: int, tiearb_b: int) -> str:
    """The `arms` dict key. Unarmed is ``"2"`` — byte-identical to what the
    pre-arbiter bench wrote (JSON stringifies int keys anyway), so a
    thread-count session's `results.json` shape does not move."""
    return f"{threads}" if tiearb_b <= 0 else f"{threads}b{tiearb_b}"


def summarize(runs: list[dict], power: list[tuple[float, float]],
              baseline_w: float | None) -> dict:
    """Per-arm energy/latency summary. Assumes hashes were already gated."""
    arms: dict[str, dict] = {}
    for r in sorted(runs, key=lambda r: (run_arm(r), str(r["tag"]))):
        threads, tb = run_arm(r)
        key = arm_key(threads, tb)
        t0, t1 = float(r["t_start_ms"]), float(r["t_end_ms"])
        joules = integrate_joules(power, t0, t1)
        n = int(r["n_moves"])
        dur_s = (t1 - t0) / 1000.0
        tel = r.get("tiearb_telemetry") or {}
        rec = {
            "tag": r["tag"],
            "n_moves": n,
            "joules": joules,
            "j_per_move": joules / n,
            "watts_mean": joules / dur_s,
            "s_per_move": float(r["s_per_move_mean"]),
            "window_s": dur_s,
            # Arbiter's OWN clock, off the rust per-agent counters.
            "n_fired": int(tel.get("tiearb_fired_plies", 0) or 0),
            "n_tile_plies": int(tel.get("tiearb_tile_plies", 0) or 0),
            "arb_secs": float(tel.get("tiearb_secs", 0.0) or 0.0),
            "arb_errors": int(tel.get("tiearb_errors", 0) or 0),
            "arb_partial_argmax": int(tel.get("tiearb_partial_argmax", 0) or 0),
            "arb_pickchanges": int(tel.get("tiearb_pickchanges", 0) or 0),
            "arb_arms_total": int(tel.get("tiearb_arms_total", 0) or 0),
            "arb_playouts_total": int(tel.get("tiearb_playouts_total", 0) or 0),
        }
        if baseline_w is not None:
            rec["j_per_move_net"] = (joules - baseline_w * dur_s) / n
        blob = arms.setdefault(key, {"runs": [], "rust_threads": threads,
                                     "tiearb_b": tb})
        blob["runs"].append(rec)

    for key, blob in arms.items():
        rr = blob["runs"]
        for k in ("j_per_move", "s_per_move", "watts_mean", "j_per_move_net"):
            vals = [r[k] for r in rr if k in r]
            if vals:
                m, sd = _mean_sd(vals)
                blob[f"{k}_mean"] = m
                blob[f"{k}_sd"] = sd
        blob["n_reps"] = len(rr)
        blob["n_moves_total"] = sum(r["n_moves"] for r in rr)
        blob["n_fired_total"] = sum(r["n_fired"] for r in rr)
        blob["n_tile_plies_total"] = sum(r["n_tile_plies"] for r in rr)
        blob["arb_secs_total"] = sum(r["arb_secs"] for r in rr)
        blob["arb_errors_total"] = sum(r["arb_errors"] for r in rr)
        blob["arb_partial_argmax_total"] = sum(r["arb_partial_argmax"] for r in rr)
        blob["arb_pickchanges_total"] = sum(r["arb_pickchanges"] for r in rr)
        if blob["n_fired_total"]:
            blob["arb_s_per_fired_ply"] = (
                blob["arb_secs_total"] / blob["n_fired_total"])
            blob["arb_mean_arms"] = (
                sum(r["arb_arms_total"] for r in rr) / blob["n_fired_total"])
            blob["arb_playouts_per_fired_ply"] = (
                sum(r["arb_playouts_total"] for r in rr) / blob["n_fired_total"])
        if blob["n_tile_plies_total"]:
            blob["fire_rate_per_tile_ply"] = (
                blob["n_fired_total"] / blob["n_tile_plies_total"])
    return arms


# --------------------------------------------------------------------------- #
# tie-arbiter cost block
# --------------------------------------------------------------------------- #
# Champion decisions per game on the phone — the denominator PHASE_A's own
# reconciliation uses (`1 + (9.57 x phi / 72) / 1.7`), so per-game projections
# here are in the same currency as the desktop cost model they are compared to.
MOVES_PER_GAME = 72
# Fired tied tile plies per game, MEASURED on desktop champion trajectories
# (measurement/tiearb2_stage2_20260817/READOUT.md §4.3, phi_arb = 17.573). The
# phone plays the same rules and budget, and this bench's own fire rate per tile
# ply is reported beside it as the on-device cross-check.
PHI_PER_GAME = 17.573
# ⚠️ THE rho_phone DENOMINATOR OF RECORD: 1.551 s/move, the shipped phone
# champion at rust_threads=2 over WHOLE GAMES (PHASE_A §1). A bench run covers
# only the FIRST n moves of a game, where the board is small and the meeple
# plies are trivial, so this session's own control s/move runs well BELOW 1.551
# and dividing by it would inflate rho_phone against the 5.520 prediction.
# `rho_phone_measured` therefore uses 1.551; the session-control version is
# reported beside it as `rho_phone_vs_session_control`, never instead of it.
T_PHONE_OF_RECORD = 1.551


def tiearb_block(arms: dict, phi: float = PHI_PER_GAME,
                 moves_per_game: int = MOVES_PER_GAME,
                 battery_joules: float | None = None,
                 t_phone_ref: float = T_PHONE_OF_RECORD) -> dict | None:
    """Price the arbiter against the unarmed arm at the SAME thread count.

    Returns ``None`` when no armed arm ran. Two independent latency readings are
    reported on purpose:

    * ``arb_s_per_fired_ply`` — the arbiter's own instrumented clock inside the
      rust agent (``tiearb_secs / tiearb_fired_plies``);
    * ``delta_s_per_fired_ply`` — the arm-to-arm subtraction
      ``Δ(s/move) × n_moves_per_run / n_fired_per_run``.

    They measure the same thing by different routes; a large disagreement means
    the arms drifted (thermal, scheduling) and the energy delta is suspect too.
    Energy has only the subtraction route, so it inherits that caveat — which is
    exactly why the two-clock cross-check is printed rather than one number.
    """
    armed = {k: b for k, b in arms.items() if b["tiearb_b"] > 0}
    if not armed:
        return None
    out = {"phi_per_game": phi, "moves_per_game": moves_per_game,
           "battery_joules": battery_joules, "arms": {}}
    for k, b in sorted(armed.items(), key=lambda kv: kv[1]["tiearb_b"]):
        ctrl_key = arm_key(b["rust_threads"], 0)
        ctrl = arms.get(ctrl_key)
        if ctrl is None:
            out["arms"][k] = {"error": f"no unarmed control arm {ctrl_key!r}"}
            continue
        n_fired = b["n_fired_total"]
        rec = {
            "control": ctrl_key,
            "tiearb_b": b["tiearb_b"],
            "n_fired_total": n_fired,
            "n_tile_plies_total": b["n_tile_plies_total"],
            "fire_rate_per_tile_ply": b.get("fire_rate_per_tile_ply"),
            "mean_arms": b.get("arb_mean_arms"),
            "playouts_per_fired_ply": b.get("arb_playouts_per_fired_ply"),
            "errors": b["arb_errors_total"],
            "partial_argmax": b["arb_partial_argmax_total"],
            "pickchanges": b["arb_pickchanges_total"],
            "arb_s_per_fired_ply": b.get("arb_s_per_fired_ply"),
            "delta_s_per_move": b["s_per_move_mean"] - ctrl["s_per_move_mean"],
            "delta_j_per_move": b["j_per_move_mean"] - ctrl["j_per_move_mean"],
        }
        if "j_per_move_net_mean" in b and "j_per_move_net_mean" in ctrl:
            rec["delta_j_per_move_net"] = (
                b["j_per_move_net_mean"] - ctrl["j_per_move_net_mean"])
        # Per-fired-ply, via the subtraction route. `moves_per_rep` is the
        # per-run move count implied by the reps (all runs share --moves).
        fired_per_move = (n_fired / b["n_moves_total"]
                          if n_fired and b["n_moves_total"] else 0.0)
        rec["fired_per_move"] = fired_per_move
        if fired_per_move > 0:
            rec["delta_s_per_fired_ply"] = rec["delta_s_per_move"] / fired_per_move
            rec["delta_j_per_fired_ply"] = rec["delta_j_per_move"] / fired_per_move
            if "delta_j_per_move_net" in rec:
                rec["delta_j_per_fired_ply_net"] = (
                    rec["delta_j_per_move_net"] / fired_per_move)
        # Per-game projection at the desktop-measured firing rate.
        s_fired = rec.get("arb_s_per_fired_ply")
        if s_fired is not None:
            rec["added_s_per_game"] = phi * s_fired
            # ⚠️ TWO denominators, and only one of them answers the owner's
            # question. `..._of_record` uses the shipped champion's WHOLE-GAME
            # 1.551 s/move, which is what a real game costs; `..._session` uses
            # this bench's opening-phase control and exists only so the reader
            # can see the difference. Dividing by the session control would
            # inflate the ratio ~3x by comparing a whole-game arbiter bill
            # against an opening-phase game.
            rec["baseline_s_per_game_of_record"] = moves_per_game * t_phone_ref
            rec["baseline_s_per_game_session"] = (
                moves_per_game * ctrl["s_per_move_mean"])
            rec["game_s_ratio"] = (
                1.0 + rec["added_s_per_game"] / rec["baseline_s_per_game_of_record"])
            rec["game_s_ratio_session"] = (
                1.0 + rec["added_s_per_game"] / rec["baseline_s_per_game_session"])
        j_fired = rec.get("delta_j_per_fired_ply")
        if j_fired is not None:
            rec["added_j_per_game"] = phi * j_fired
            # ⚠️ OPENING-PHASE REFERENCED, and there is no J/move of record to
            # substitute: this is the only on-device energy figure that exists.
            # A whole game costs MORE per move than these first n, so the
            # baseline %battery/game below is a LOWER BOUND and the added-%
            # column is correspondingly the most pessimistic framing of the
            # ratio between them.
            rec["baseline_j_per_game"] = moves_per_game * ctrl["j_per_move_mean"]
            rec["baseline_j_per_game_is_opening_phase"] = True
            if battery_joules:
                rec["baseline_battery_pct_per_game"] = (
                    100.0 * rec["baseline_j_per_game"] / battery_joules)
                rec["added_battery_pct_per_game"] = (
                    100.0 * rec["added_j_per_game"] / battery_joules)
        # rho_phone, MEASURED: added arbiter seconds on a fired ply as a
        # multiple of one baseline move. PHASE_A predicted this from desktop
        # worker-seconds (5.520 at B=16); this is the phone's own answer.
        t_ref = t_phone_ref
        rec["t_phone_ref_s"] = t_ref
        rec["t_session_control_s_per_move"] = ctrl["s_per_move_mean"]
        if s_fired is not None:
            rec["rho_phone_measured"] = s_fired / t_ref
            rec["rho_phone_vs_session_control"] = (
                s_fired / ctrl["s_per_move_mean"])
        if rec.get("delta_s_per_fired_ply") is not None:
            rec["rho_phone_measured_subtraction"] = (
                rec["delta_s_per_fired_ply"] / t_ref)
        out["arms"][k] = rec
    return out


def _fmt(x: float, digits: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.{digits}f}"


def _armed_anywhere(arms: dict) -> bool:
    return any(b["tiearb_b"] > 0 for b in arms.values())


def markdown_table(arms: dict, baseline_w: float | None) -> str:
    show_arb = _armed_anywhere(arms)
    head = "| rust_threads |" + (" tiearb B |" if show_arb else "") \
        + " reps | J/move (mean ± sd) | s/move (mean ± sd) | mean W |" \
        + (" net J/move |" if baseline_w is not None else "") \
        + (" fires |" if show_arb else "")
    sep = "|---|---|---|---|---|" + ("---|" if baseline_w is not None else "") \
        + ("---|---|" if show_arb else "")
    lines = [head, sep]
    for key in sorted(arms, key=lambda k: (arms[k]["rust_threads"],
                                           arms[k]["tiearb_b"])):
        b = arms[key]
        row = f"| {b['rust_threads']} |"
        if show_arb:
            row += f" {b['tiearb_b'] or '—'} |"
        row += (f" {b['n_reps']} "
                f"| {_fmt(b['j_per_move_mean'])} ± {_fmt(b.get('j_per_move_sd'))} "
                f"| {_fmt(b['s_per_move_mean'])} ± {_fmt(b.get('s_per_move_sd'))} "
                f"| {_fmt(b['watts_mean_mean'], 2)} |")
        if baseline_w is not None:
            row += f" {_fmt(b.get('j_per_move_net_mean'))} |"
        if show_arb:
            row += (f" {b['n_fired_total']}/{b['n_tile_plies_total']} |"
                    if b["tiearb_b"] else " — |")
        lines.append(row)
    return "\n".join(lines)


def markdown_tiearb(block: dict | None) -> str:
    """The arbiter cost readout: what the owner feels, and the rho_phone check."""
    if not block:
        return ""
    out = [
        "",
        "## Tie arbiter — measured on-device cost",
        "",
        f"Projections use `phi` = {block['phi_per_game']} fired tied tile plies "
        f"per game and {block['moves_per_game']} champion decisions per game "
        "(the desktop cost model's own denominator, "
        "measurement/tiearb2_stage2_20260817). Every arm played the CHAMPION "
        "trajectory, so this prices arbitration work — not the arbiter's picks.",
        "",
        "| B | fires/tile plies | mean arms | s/fired ply (arb clock) | "
        "s/fired ply (Δ arms) | ΔJ/fired ply | added s/game | added J/game | "
        "errors | partial_argmax |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for key, r in block["arms"].items():
        if "error" in r:
            out.append(f"| {key} | {r['error']} | | | | | | | | |")
            continue
        out.append(
            f"| {r['tiearb_b']} "
            f"| {r['n_fired_total']}/{r['n_tile_plies_total']} "
            f"({_fmt(r.get('fire_rate_per_tile_ply'), 3)}) "
            f"| {_fmt(r.get('mean_arms'), 2)} "
            f"| {_fmt(r.get('arb_s_per_fired_ply'))} "
            f"| {_fmt(r.get('delta_s_per_fired_ply'))} "
            f"| {_fmt(r.get('delta_j_per_fired_ply'), 2)} "
            f"| {_fmt(r.get('added_s_per_game'), 1)} "
            f"| {_fmt(r.get('added_j_per_game'), 1)} "
            f"| {r['errors']} | {r['partial_argmax']} |")
    out += [
        "",
        "| B | rho_phone MEASURED (arb clock) | rho_phone (Δ arms) | "
        "vs session control | game wall-clock ratio | baseline %batt/game | "
        "added %batt/game |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, r in block["arms"].items():
        if "error" in r:
            continue
        out.append(
            f"| {r['tiearb_b']} "
            f"| {_fmt(r.get('rho_phone_measured'))} "
            f"| {_fmt(r.get('rho_phone_measured_subtraction'))} "
            f"| {_fmt(r.get('rho_phone_vs_session_control'))} "
            f"| {_fmt(r.get('game_s_ratio'))}× "
            f"| {_fmt(r.get('baseline_battery_pct_per_game'), 2)}+ "
            f"| {_fmt(r.get('added_battery_pct_per_game'), 2)} |")
    ctrl_s = next((r.get("t_session_control_s_per_move")
                   for r in block["arms"].values() if "error" not in r), None)
    out += [
        "",
        f"`rho_phone` = added arbiter seconds on a fired ply ÷ **{T_PHONE_OF_RECORD} "
        "s**, the shipped phone champion's whole-game s/move (PHASE_A §1's own "
        "denominator, so this is directly comparable to its **5.520 at B=16** "
        "prediction from desktop worker-seconds at W=30). ⚠️ A bench run covers "
        "only the FIRST n moves of a game, which are cheaper than the game "
        f"average — this session's control measured {_fmt(ctrl_s)} s/move — so "
        "the 'vs session control' column is the larger, early-game-relative "
        "figure and is NOT the number to compare against 5.520. "
        "The two rho routes (the rust agent's internal `tiearb_secs` clock vs "
        "the arm-to-arm subtraction) are independent; a large gap between them "
        "means the arms drifted and the ΔJ column inherits that doubt.",
        "",
        "⚠️ **The opening bias runs AGAINST the arbiter, so these costs are an "
        "upper bound.** A tier-1 arbitration playout runs to a terminal state, "
        "so a tied ply early in the game is priced over ~140 remaining plies "
        "while a late one is priced over a handful — benching the FIRST n moves "
        "therefore measures the most expensive arbitration in the game. The "
        "opening also ties more often (measured fires/tile ply above vs the "
        "whole-game `phi`/72). Read the per-fired-ply and per-game costs as "
        "**ceilings**, not central estimates. "
        "`game wall-clock ratio` divides the whole-game arbiter bill by the "
        f"whole-game champion ({T_PHONE_OF_RECORD} s/move × moves/game); "
        "`baseline %batt/game` is marked `+` because it is referenced to this "
        "session's opening-phase J/move and a full game costs more.",
    ]
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# report (the driver's single analysis entry point)
# --------------------------------------------------------------------------- #
def build_report(runs: list[dict], samples_text: str,
                 baseline: tuple[float, float] | None,
                 battery_joules: float | None = None) -> tuple[dict, str]:
    """(report_dict, markdown). Raises SystemExit(2) on any identity failure —
    deliberately BEFORE any energy number is computed or printed."""
    bad = _fail_runs(runs)
    if bad:
        raise SystemExit(
            "ABORT — failed bench runs (no energy numbers will be printed):\n"
            + "\n".join(f"  {r.get('tag')}: {r.get('error')}" for r in bad))
    ok, by_tag = check_hashes(runs)
    if not ok:
        detail = "\n".join(f"  {t}: {h}" for t, h in sorted(by_tag.items()))
        raise SystemExit(
            "ABORT — move_hash DIFFERS across runs. The arms did not do "
            "identical work, so an energy comparison is meaningless. This "
            "contradicts the proven thread-count invariance of the rust "
            "search — investigate before re-running (mixed app builds? a "
            "run that degraded to the python floor?).\n"
            "No energy numbers were computed.\n" + detail)

    samples = parse_samples(samples_text)
    check_units(samples)
    sign = detect_sign(samples)
    power = power_series(samples, sign)

    baseline_w = None
    if baseline is not None:
        baseline_w = mean_watts(power, baseline[0], baseline[1])

    arms = summarize(runs, power, baseline_w)
    arb = tiearb_block(arms, battery_joules=battery_joules)
    report = {
        "schema": SCHEMA,
        "move_hash": next(iter(by_tag.values())),
        "hash_identical_across_runs": True,
        "replay": runs[0].get("replay", "champion_trajectory"),
        "tiearb_cost": arb,
        "sign_convention": ("current_now positive on discharge" if sign == 1
                            else "current_now negative on discharge (normalized)"),
        "n_samples": len(samples),
        "baseline_watts": baseline_w,
        # Recorded so the report is REPRODUCIBLE from runs/ + samples.csv. It
        # was not, until 2026-08-17: re-running the report step had to guess the
        # idle window and landed 1.2% off on `baseline_watts`. (Every Δ column
        # is baseline-independent, so only the `net` columns were ever at risk.)
        "baseline_window_ms": list(baseline) if baseline else None,
        "workload": {k: runs[0][k] for k in
                     ("n_moves", "seed", "k_dets", "sims_per_det",
                      "total_sims", "rules_profile", "backend")},
        "arms": arms,
        "runs_order": [r["tag"] for r in runs],
    }

    md = (
        "# Battery A/B bench — results\n\n"
        f"Workload: {runs[0]['n_moves']} champion moves/run, seed "
        f"{runs[0]['seed']}, budget k{runs[0]['k_dets']}x"
        f"{runs[0]['sims_per_det']}={runs[0]['total_sims']}, rules "
        f"`{runs[0]['rules_profile']}`, backend `{runs[0]['backend']}`.\n\n"
        f"Identity gate: PASS — all {len(runs)} runs report move_hash "
        f"`{report['move_hash'][:16]}…` (identical play across arms).\n\n"
        + (f"Idle baseline: {baseline_w:.2f} W (subtracted in the net column).\n\n"
           if baseline_w is not None else "")
        + markdown_table(arms, baseline_w)
        + "\n\n*J/move integrates the whole workload window (search + engine "
          "bookkeeping between moves). The J/move-vs-latency trade is the "
          "owner's call — see android/tools/BATTERY_BENCH.md.*\n"
        + markdown_tiearb(arb)
    )
    return report, md


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cmd_schedule(args) -> int:
    specs = args.arms.replace(",", " ").split()
    for rep, threads, tb, tag in arm_schedule(specs, args.reps):
        print(f"{rep} {threads} {tb} {tag}")
    return 0


def _cmd_report(args) -> int:
    runs = []
    run_files = sorted(Path(args.runs_dir).glob("*.json"))
    if not run_files:
        print(f"no run JSONs under {args.runs_dir}", file=sys.stderr)
        return 2
    for p in run_files:
        runs.append(json.loads(p.read_text()))
    samples_text = Path(args.samples).read_text()
    baseline = None
    if args.baseline:
        lo, hi = args.baseline.split(":")
        baseline = (float(lo), float(hi))
    report, md = build_report(runs, samples_text, baseline,
                              battery_joules=args.battery_joules)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(report, indent=1))
    (out / "results.md").write_text(md)
    print(md)
    print(f"\nwrote {out / 'results.json'} and {out / 'results.md'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="battery_bench_lib")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("schedule", help="print the interleaved run plan")
    s.add_argument("--arms", required=True,
                   help='e.g. "4,2,1" (threads) or "2,2:16,2:4" '
                        '(threads[:tiearb_B]; B=0/absent == arbiter OFF)')
    s.add_argument("--reps", type=int, default=3)
    s.set_defaults(fn=_cmd_schedule)

    r = sub.add_parser("report", help="integrate, gate on hashes, summarize")
    r.add_argument("--runs-dir", required=True,
                   help="directory of per-run result JSONs pulled off the phone")
    r.add_argument("--samples", required=True,
                   help="sampler file: '<epoch_ms> <current_now> <voltage_now>' lines")
    r.add_argument("--baseline", default=None,
                   help="idle-baseline window 'T0MS:T1MS' (device epoch ms)")
    r.add_argument("--battery-joules", type=float, default=None,
                   help="full-charge energy of the pack in joules "
                        "(charge_full uAh x nominal V); enables the "
                        "%%battery/game projections")
    r.add_argument("--out-dir", required=True)
    r.set_defaults(fn=_cmd_report)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
