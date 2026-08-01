#!/usr/bin/env python3
"""G7 leg 1 (native half) — which ``LibmFlavor`` is the DEVICE's scalar libm?

G0 pre-registered this leg and deferred it to P7. The G0 fleet amendment is the
reason it cannot be skipped or assumed: the M5 showed a platform can be a THIRD
implementation, neither msun nor glibc at either contraction setting, so
"bionic is msun-derived therefore msun matches" is a hypothesis, not a fact.
P3 §3 is the reason a search-sized gate cannot stand in for it: the search is
nearly libm-blind (wrong tanh flavours touch 2/720 root children and never the
action), so only a direct transcendental comparison pins the flavour.

WHAT THIS MEASURES
------------------
The two scalar sites CPython reaches through the platform libm:

    math.tanh   -> libm tanh    (production: value_norm)
    math.expm1  -> libm expm1   (tanh's kernel, and the axis the whole
                                 msun/glibc divergence was localized to at G0)
    math.exp    -> libm exp     (NOT the production np.exp site; reported
                                 because it prices exp64/exp64_fma against the
                                 platform's own scalar exp)

``scripts/rustport/bionic_libm_probe.c``, cross-compiled with NDK clang and run
under ``adb shell``, IS the device's libm: CPython's ``math_tanh`` etc. are thin
wrappers that pass finite arguments straight through. This gives the answer for
those three sites without needing a Python interpreter on the device.

The np.exp production site is numpy's OWN SIMD kernel, not libm, so it is NOT
covered here — it needs the device's numpy, i.e. the Chaquopy leg
(``android/tools/device_python_probe/``). Both halves are required for a
complete G7 leg-1 verdict; this script prints which half it is.

USAGE
-----
    python3 scripts/rustport/device_libm_probe.py \
        --serial 100.64.4.100:38025 --fuzz 10000000
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
DEFAULT_INPUTS = REPO / "measurement" / "rustport_p0" / "transcendental_inputs.npz"
OUTDIR = REPO / "measurement" / "rustport_p7"
DEVDIR = "/data/local/tmp/carcp7"
FLAVORS = ["msun", "msun_fma", "glibc", "glibc_fma"]


def log(msg: str) -> None:
    print(f"[device_libm] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# adb plumbing
# --------------------------------------------------------------------------- #
class Adb:
    def __init__(self, serial: str | None):
        self.base = ["adb"] + (["-s", serial] if serial else [])

    def sh(self, cmd: str, check: bool = True) -> str:
        r = subprocess.run(self.base + ["shell", cmd], capture_output=True,
                           text=True)
        if check and r.returncode != 0:
            raise SystemExit(f"adb shell failed ({r.returncode}): {cmd}\n{r.stderr}")
        return r.stdout

    def push(self, local: Path, remote: str) -> None:
        subprocess.run(self.base + ["push", str(local), remote],
                       check=True, capture_output=True, text=True)

    def pull(self, remote: str, local: Path) -> None:
        subprocess.run(self.base + ["pull", remote, str(local)],
                       check=True, capture_output=True, text=True)


def ulp_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Elementwise |a - b| in ULPs (same mapping as harness_transcendental)."""
    ai = a.view(np.int64).astype(np.int64)
    bi = b.view(np.int64).astype(np.int64)
    ai = np.where(ai < 0, np.int64(-(2**63)) - ai, ai)
    bi = np.where(bi < 0, np.int64(-(2**63)) - bi, bi)
    return np.abs(ai - bi).astype(np.uint64)


def write_hex(path: Path, xs: np.ndarray) -> None:
    """One 16-hex-digit f64 bit pattern per line — the carc-cli wire format."""
    bits = np.ascontiguousarray(xs, dtype=np.float64).view(np.uint64)
    # np.savetxt is far too slow at 10^7 rows; build the buffer directly.
    with open(path, "wb") as f:
        for i in range(0, bits.size, 1_000_000):
            chunk = bits[i:i + 1_000_000]
            f.write(("\n".join(f"{v:016x}" for v in chunk) + "\n").encode())


def read_hex(path: Path) -> np.ndarray:
    txt = path.read_bytes().split()
    return np.array([int(t, 16) for t in txt], dtype=np.uint64).view(np.float64)


def _leg(name: str, want: np.ndarray, got: np.ndarray) -> dict:
    same = want.view(np.uint64) == got.view(np.uint64)
    n_mis = int((~same).sum())
    d = ulp_diff(want, got)
    hist: dict[int, int] = {}
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


# --------------------------------------------------------------------------- #
# one comparison block (device reference vs every Rust flavour)
# --------------------------------------------------------------------------- #
def run_block(adb: Adb, tag: str, fn: str, xs: np.ndarray, work: Path,
              cross_check: bool) -> dict:
    """Compute ``fn`` on the device with bionic AND with every carc-core flavour.

    Everything -- reference, every flavour, and the ulp comparison -- runs ON THE
    DEVICE over one input file, so (a) nothing about the host's libm, numpy or
    float formatting can leak into the comparison, and (b) only a JSON summary
    crosses the wire. The link is a ~110 ms tailscale hop at ~140 KB/s; pulling
    the fuzz outputs instead measured out at hours.

    ``cross_check`` pulls the raw outputs and re-derives the same summary with
    numpy, which is how the on-device comparator earns its trust. Used on the
    (small) corpus legs; off for the fuzz.
    """
    in_local = work / f"{tag}_in.hex"
    write_hex(in_local, xs)
    remote_in = f"{DEVDIR}/{tag}_in.hex"
    t0 = time.time()
    adb.push(in_local, remote_in)
    log(f"{tag}: pushed {xs.size} args ({in_local.stat().st_size >> 20} MiB, "
        f"{time.time() - t0:.1f}s)")

    out: dict = {"n": int(xs.size), "fn": fn}

    # -- the device's own libm (== what math.<fn> returns inside Chaquopy) ----
    adb.sh(f"{DEVDIR}/bionic_libm_probe {fn} < {remote_in} > {DEVDIR}/{tag}_bionic.hex")

    # -- every LibmFlavor, computed on-device by carc-cli --------------------
    variants: list[tuple[str, str]]
    if fn == "exp":
        variants = [("exp64", "exp"), ("exp64_fma", "exp --fma")]
    else:
        variants = [(f, f"{fn} --flavor {f}") for f in FLAVORS]
    for name, argstr in variants:
        adb.sh(f"{DEVDIR}/carc-cli {argstr} < {remote_in} > {DEVDIR}/{tag}_{name}.hex")

    legs: dict[str, dict] = {}
    for name, _ in variants:
        raw = adb.sh(f"{DEVDIR}/bionic_libm_probe ulp "
                     f"{DEVDIR}/{tag}_bionic.hex {DEVDIR}/{tag}_{name}.hex").strip()
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            raise SystemExit(f"{tag}/{name}: device comparator said {raw!r}")
        if d["length_mismatch"]:
            raise SystemExit(f"{tag}/{name}: output lengths differ on device")
        if d["n"] != int(xs.size):
            raise SystemExit(f"{tag}/{name}: compared {d['n']} != {xs.size} values")
        legs[name] = {
            "impl": name,
            "n": d["n"],
            "n_bit_mismatch": d["n_bit_mismatch"],
            "frac_bit_mismatch": d["n_bit_mismatch"] / d["n"] if d["n"] else 0.0,
            "max_ulp": d["max_ulp"],
            "mean_ulp": d["mean_ulp"],
            "ulp_histogram_of_mismatches": {int(k): v for k, v in d["hist"].items()},
            "bit_exact": d["n_bit_mismatch"] == 0,
        }

    # -- host cross-check of the device comparator ---------------------------
    if cross_check:
        adb.pull(f"{DEVDIR}/{tag}_bionic.hex", work / f"{tag}_bionic.hex")
        want = read_hex(work / f"{tag}_bionic.hex")
        for name, _ in variants:
            adb.pull(f"{DEVDIR}/{tag}_{name}.hex", work / f"{tag}_{name}.hex")
            got = read_hex(work / f"{tag}_{name}.hex")
            host = _leg(name, want, got)
            for k in ("n", "n_bit_mismatch", "max_ulp"):
                if host[k] != legs[name][k]:
                    raise SystemExit(
                        f"{tag}/{name}: device comparator {k}={legs[name][k]} != "
                        f"host numpy {k}={host[k]} — the on-device ulp code is wrong")
            (work / f"{tag}_{name}.hex").unlink()
        (work / f"{tag}_bionic.hex").unlink()
        out["host_cross_checked"] = True

    out["legs"] = legs
    out["bit_exact_flavors"] = [k for k, v in legs.items() if v["bit_exact"]]
    in_local.unlink()
    adb.sh(f"rm -f {DEVDIR}/{tag}_*.hex")
    return out


def fuzz_args(rng, lo: float, hi: float, k: int) -> np.ndarray:
    """Half uniform over the production range, half uniform bit patterns clipped
    in — the same recipe harness_transcendental uses, so the two fuzz legs are
    comparable."""
    half = k // 2
    a = rng.uniform(lo, hi, half)
    bits = rng.integers(0, 1 << 63, k - half, dtype=np.uint64)
    b = bits.view(np.float64)
    b = b[np.isfinite(b)]
    b = np.clip(b, lo, hi)
    if b.size < k - half:
        b = np.concatenate([b, rng.uniform(lo, hi, k - half - b.size)])
    return np.ascontiguousarray(np.concatenate([a, b]), dtype=np.float64)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default=os.environ.get("CARC_ADB_SERIAL"))
    ap.add_argument("--inputs", type=Path, default=DEFAULT_INPUTS)
    ap.add_argument("--fuzz", type=int, default=10_000_000,
                    help="fuzz args per site (0 disables); G0 used 1e8 on desktop")
    ap.add_argument("--fuzz-chunk", type=int, default=5_000_000)
    ap.add_argument("--seed", type=int, default=20260731)
    ap.add_argument("--probe", type=Path, required=True,
                    help="host path to the built bionic_libm_probe (arm64)")
    ap.add_argument("--carc-cli", type=Path, required=True,
                    help="host path to the built carc-cli (arm64)")
    ap.add_argument("--work", type=Path, default=Path("/tmp/carc_p7_libm"))
    ap.add_argument("--out", type=Path, default=OUTDIR / "G7_libm_device.json")
    a = ap.parse_args()

    a.work.mkdir(parents=True, exist_ok=True)
    adb = Adb(a.serial)
    adb.sh(f"mkdir -p {DEVDIR}")
    adb.push(a.probe, f"{DEVDIR}/bionic_libm_probe")
    adb.push(a.carc_cli, f"{DEVDIR}/carc-cli")
    adb.sh(f"chmod 755 {DEVDIR}/bionic_libm_probe {DEVDIR}/carc-cli")

    dev = {
        "abi": adb.sh("getprop ro.product.cpu.abi").strip(),
        "model": adb.sh("getprop ro.product.model").strip(),
        "sdk": adb.sh("getprop ro.build.version.sdk").strip(),
        "release": adb.sh("getprop ro.build.version.release").strip(),
        "fingerprint": adb.sh("getprop ro.build.fingerprint").strip(),
        "kernel": adb.sh("uname -r").strip(),
        "carc_cli_selftest": adb.sh(f"{DEVDIR}/carc-cli selftest").strip(),
        "probe_selftest": adb.sh(f"{DEVDIR}/bionic_libm_probe selftest").strip(),
    }
    log(f"device {dev['model']} {dev['abi']} sdk{dev['sdk']} ({dev['release']})")

    payload: dict = {"device": dev, "corpus": {}, "fuzz": {}}

    # ---- corpus leg --------------------------------------------------------
    d = np.load(a.inputs)
    z = np.ascontiguousarray(d["z"], dtype=np.float64)
    targ = np.ascontiguousarray(d["tanh_arg"], dtype=np.float64)
    # expm1's arguments as tanh's kernel sees them (harness_transcendental's
    # construction, kept identical so the desktop and device legs compare).
    eargs = np.ascontiguousarray(
        np.concatenate([2 * np.abs(targ), -2 * np.abs(targ)]), dtype=np.float64)

    payload["corpus"]["inputs"] = {
        "path": str(a.inputs.relative_to(REPO)) if a.inputs.is_relative_to(REPO)
        else str(a.inputs),
        "n_z": int(z.size), "n_tanh": int(targ.size), "n_expm1": int(eargs.size),
        "z_range": [float(z.min()), float(z.max())],
        "tanh_range": [float(targ.min()), float(targ.max())],
    }
    payload["corpus"]["tanh"] = run_block(adb, "corpus_tanh", "tanh", targ, a.work, True)
    payload["corpus"]["expm1"] = run_block(adb, "corpus_expm1", "expm1", eargs, a.work, True)
    payload["corpus"]["exp_scalar"] = run_block(adb, "corpus_exp", "exp", z, a.work, True)

    # ---- fuzz leg ----------------------------------------------------------
    if a.fuzz:
        rng = np.random.default_rng(a.seed)
        acc: dict[str, dict] = {}
        done = 0
        t0 = time.time()
        while done < a.fuzz:
            k = min(a.fuzz_chunk, a.fuzz - done)
            blocks = [
                ("tanh", "tanh", fuzz_args(rng, -20.0, 20.0, k)),
                ("expm1", "expm1", fuzz_args(rng, -40.0, 40.0, k)),
                ("exp", "exp", fuzz_args(rng, -100.0, 0.0, k)),
            ]
            for tag, fn, xs in blocks:
                r = run_block(adb, f"fuzz_{tag}", fn, xs, a.work, False)
                slot = acc.setdefault(tag, {})
                for name, leg in r["legs"].items():
                    s = slot.setdefault(name, {"n": 0, "n_bit_mismatch": 0,
                                               "max_ulp": 0, "hist": {}})
                    s["n"] += leg["n"]
                    s["n_bit_mismatch"] += leg["n_bit_mismatch"]
                    s["max_ulp"] = max(s["max_ulp"], leg["max_ulp"])
                    for kk, vv in leg["ulp_histogram_of_mismatches"].items():
                        s["hist"][str(kk)] = s["hist"].get(str(kk), 0) + vv
            done += k
            log(f"fuzz {done}/{a.fuzz} ({time.time() - t0:.0f}s)")
        for tag, slot in acc.items():
            for name, s in slot.items():
                s["frac_bit_mismatch"] = s["n_bit_mismatch"] / s["n"] if s["n"] else 0.0
                s["bit_exact"] = s["n_bit_mismatch"] == 0
                s["ulp_histogram_of_mismatches"] = s.pop("hist")
        payload["fuzz"] = {
            "n_per_site": a.fuzz, "seed": a.seed, "wall_s": round(time.time() - t0, 1),
            "ranges": {"tanh": [-20.0, 20.0], "expm1": [-40.0, 40.0],
                       "exp": [-100.0, 0.0]},
            "legs": acc,
        }

    # ---- verdict -----------------------------------------------------------
    def hits(section: str, site: str) -> list[str]:
        if section == "corpus":
            return payload["corpus"].get(site, {}).get("bit_exact_flavors", [])
        legs = payload.get("fuzz", {}).get("legs", {}).get(site, {})
        return [k for k, v in legs.items() if v.get("bit_exact")]

    corpus_tanh = hits("corpus", "tanh")
    corpus_expm1 = hits("corpus", "expm1")
    corpus_exp = payload["corpus"]["exp_scalar"]["bit_exact_flavors"]
    fuzz_tanh = hits("fuzz", "tanh")
    fuzz_expm1 = hits("fuzz", "expm1")
    fuzz_exp = hits("fuzz", "exp")
    # The G0 cautionary tale: msun_fma passed the corpus and failed the fuzz.
    # Only a flavour that survives BOTH is a claim.
    surviving_tanh = [f for f in corpus_tanh if not a.fuzz or f in fuzz_tanh]
    surviving_expm1 = [f for f in corpus_expm1 if not a.fuzz or f in fuzz_expm1]
    payload["verdict"] = {
        "half": "native (bionic scalar libm). The np.exp production site needs "
                "the Chaquopy leg — see android/tools/device_python_probe.",
        "corpus_tanh_bit_exact_flavors": corpus_tanh,
        "corpus_expm1_bit_exact_flavors": corpus_expm1,
        "corpus_scalar_exp_bit_exact_impls": corpus_exp,
        "fuzz_tanh_bit_exact_flavors": fuzz_tanh,
        "fuzz_expm1_bit_exact_flavors": fuzz_expm1,
        "fuzz_scalar_exp_bit_exact_impls": fuzz_exp,
        "tanh_flavor_surviving_both": surviving_tanh,
        "expm1_flavor_surviving_both": surviving_expm1,
        "bionic_math_tanh_parity_achieved": bool(surviving_tanh),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(payload, indent=2) + "\n")
    log(f"wrote {a.out}")
    v = payload["verdict"]
    log(f"VERDICT tanh flavours surviving corpus+fuzz: {surviving_tanh or 'NONE'}")
    log(f"        expm1 flavours surviving corpus+fuzz: {surviving_expm1 or 'NONE'}")
    log(f"        scalar exp (corpus/fuzz): {corpus_exp or 'NONE'} / {fuzz_exp or 'NONE'}")
    return 0 if v["bionic_math_tanh_parity_achieved"] else 1


if __name__ == "__main__":
    sys.exit(main())
