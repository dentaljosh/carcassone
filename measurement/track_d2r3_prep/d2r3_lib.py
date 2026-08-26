#!/usr/bin/env python3
"""
d2r3_lib.py -- THE ONE IMPLEMENTATION of D2-R3's cost-calibration primitives.

⭐ WHY THIS FILE EXISTS AT ALL.  D2's second attempt (`../track_d2r2_prep/`) died
because the quantity a PILOT measured (an equal-time ratio at n=16, W unsaturated)
was not the quantity the CELL realized (the same ratio at n=400, W=22 saturated).
The fix is not a better pilot; it is to make the LIVE gate and the POST-HOC gate
literally the same code, reading the same records, over a window that is INSIDE
the adjudicated games.

Two consumers import this module and NEITHER carries its own copy of the
arithmetic or the thresholds:

  * `run_cells.sh` -> `burnin_watch` (live): polls the cell's per-game records,
    adjudicates the burn-in window the moment it is complete, and KILLS the cell
    on FAIL so a cost-calibration void costs ~8% of a pair instead of 100% (MEASURED against
    attempt 2's archive: the gate could have fired with 81 of 400 games played).
  * `analyze_d2r3.py` (post-hoc): recomputes the SAME window from the SAME
    records and reports it as gate `G-TIMING`.

If those two ever disagree, it is a bug in the caller, not a judgement call --
there is exactly one `timing_ratio()` in this pair.

⚠️ FIELD-NAME TRAP (DESIGN §3.3, inherited verbatim from the jcz precedent):
in `eval_fair_puct`, `champ_prefix_*` is the CANDIDATE side and `rung_*` is the
OPPONENT side -- the opposite convention from `eval_puct_priors`. The ratio is
CANDIDATE / RUNG. A readout that swaps them inverts the timing reading.

The arithmetic below is a transcription of `eval_fair_puct._summary()`
(scripts/classical_search/eval_fair_puct.py lines 2589-2603), so that a ratio
computed here over ALL of a cell's records is bit-comparable with the harness's
own `summary.json` figure:

    champ_ms = sum(champ_prefix_secs) / sum(champ_prefix_moves) * 1000
    rung_ms  = sum(rung_secs)         / sum(rung_moves)         * 1000
    ratio    = champ_ms / rung_ms

No statistic of strength, margin, winrate or elo is computed anywhere in this
file, and nothing here reads a `diff`/`result` field. This module is COST ONLY.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# =============================================================================
# FROZEN CONSTANTS -- the pair's bars live HERE and nowhere else.
# READ_RULE.md §3 is the binding text; these are its machine-readable form, and
# `analyze_d2r3.py --selftest` asserts the two agree.
# =============================================================================

BAND = 149000000000
N_DECKS = 200                    # per cell; 400 games at --paired
N_BURNIN_DECKS = 40              # the burn-in window: decks BAND+0 .. BAND+39
SEATINGS_PER_DECK = 2

# G-TIMING -- the BINDING equal-time interval, on the BURN-IN WINDOW.
# CARRIED VERBATIM from ../track_d2_prep and ../track_d2r2_prep. This number has
# not moved across three attempts; only the window it is read over has.
TIMING_LO = 0.85
TIMING_HI = 1.20

# G-TIMING-FULL -- the WHOLE-CELL drift envelope. Wider on purpose: it is a
# guard against a REGIME CHANGE after the enforced window, not a second attempt
# at equal time. DESIGN §3.5 derives the width.
TIMING_FULL_LO = 0.75
TIMING_FULL_HI = 1.35

# G-TENANCY -- exclusive-tenancy thresholds. `feedback_no_agent_compute_beside_eval`:
# a TIMING measurement is an EXCLUSIVE tenant. An Android cross-compile + gradle
# build shared the box with attempt 2's CELL R800 for its final ~10 minutes.
FOREIGN_PROC_CPU_PCT = 50.0      # per-process: at/above this a foreign proc is NAMED
FOREIGN_TOTAL_CPU_PCT = 100.0    # aggregate: at/above this the box is NOT exclusive
                                 # (100% == one core of 32 -- generous; a gradle
                                 #  build reads 800%+, an idle box reads <20%)
TENANCY_CONFIRM_SAMPLES = 2      # consecutive samples required to ABORT (a single
                                 # transient `git status` must not kill a 2h cell)
TENANCY_SAMPLE_SECS = 60         # sampler cadence during a cell
CPU_SAMPLE_INTERVAL = 2.0        # seconds between the two /proc reads of one sample

# Processes that are ours-by-construction and can never be "foreign", matched on
# the full command line. This is an ALLOWLIST OF OUR OWN TOOLING, not a list of
# things we tolerate: anything not descended from the launcher's process group
# and not matching these is foreign.
SELF_PATTERNS = (
    r"eval_fair_puct\.py",
    r"d2r3_lib\.py",
    r"analyze_d2r3\.py",
    r"run_cells\.sh",
)
_SELF_RE = re.compile("|".join(SELF_PATTERNS))

# Known heavy compute belonging to OTHER measurement tracks -- named explicitly so
# a census failure says WHICH sibling run is in the way (the h2h precedent's
# `require_box_free` list, extended).
SIBLING_COMPUTE_PATTERNS = (
    r"eval_puct_priors\.py",
    r"gen_fair_distill",
    r"carcasum_driver",
    r"carcasum_match/match\.py",
    r"ladder_rung_eval\.py",
    r"eval_net_vs_heuristic",
    r"reconcile_exact_solver\.py",   # observed live on the box 2026-08-25 during this pair's build
    r"run_selfplay_iter\.py",
    r"train_iter\.py",
    r"eval_hybrid_handoff\.py",
    r"mine_roots\.py",
)

# ⚠️ THIS LIST IS A LABELLING CONVENIENCE, NOT THE DETECTOR. A process is FOREIGN
# because it is not in the launcher's process tree and is burning CPU -- not
# because it matches a name here. Matching only sets `sibling_measurement_run`
# so a census failure can say WHICH sibling run is in the way instead of just
# printing a pid. A co-tenant this list has never heard of (a gradle build, an
# APK cross-compile, a pytest run, someone's `cargo build`) is caught exactly the
# same way, which is the whole point -- attempt 2's contaminant was an ANDROID
# BUILD, and no name-pattern list would have had it.
_SIBLING_RE = re.compile("|".join(SIBLING_COMPUTE_PATTERNS))


# =============================================================================
# PER-GAME RECORDS
# =============================================================================

# `eval_fair_puct._result_path` -- one JSON per (seed, a_seat), flat in the cell
# dir, written ATOMICALLY as each game finishes (tmp.replace). Failure records
# live in a `failed/` SUBDIR and are excluded by this non-recursive glob.
RECORD_GLOB = "seed*_a*.json"
_RECORD_RE = re.compile(r"^seed(\d{12})_a(\d+)\.json$")

# Every field the ratio needs. ABSENT is FAIL -- a record missing any of these is
# reported, never silently skipped (a silently-skipped record is how a timing
# window quietly becomes a different window).
REQUIRED_TIMING_FIELDS = (
    "champ_prefix_secs",
    "champ_prefix_moves",
    "rung_secs",
    "rung_moves",
)


@dataclass
class Record:
    seed: int
    a_seat: int
    path: Path
    champ_prefix_secs: float
    champ_prefix_moves: int
    rung_secs: float
    rung_moves: int


@dataclass
class RatioReading:
    """A cost reading over some set of records. Carries its own provenance."""

    n_games: int
    n_decks: int
    champ_ms_per_move: float | None
    rung_ms_per_move: float | None
    ratio: float | None
    champ_secs_total: float
    champ_moves_total: int
    rung_secs_total: float
    rung_moves_total: int
    seed_lo: int | None
    seed_hi: int | None
    complete: bool
    missing: list[str] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = {
            "n_games": self.n_games,
            "n_decks": self.n_decks,
            "champ_prefix_ms_per_move": self.champ_ms_per_move,
            "rung_ms_per_move": self.rung_ms_per_move,
            "ratio": self.ratio,
            "champ_prefix_secs_total": round(self.champ_secs_total, 6),
            "champ_prefix_moves_total": self.champ_moves_total,
            "rung_secs_total": round(self.rung_secs_total, 6),
            "rung_moves_total": self.rung_moves_total,
            "seed_lo": self.seed_lo,
            "seed_hi": self.seed_hi,
            "complete": self.complete,
            "n_missing": len(self.missing),
            "n_malformed": len(self.malformed),
        }
        if self.missing:
            d["missing_sample"] = sorted(self.missing)[:8]
        if self.malformed:
            d["malformed_sample"] = sorted(self.malformed)[:8]
        return d


def parse_record_name(name: str) -> tuple[int, int] | None:
    m = _RECORD_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def load_records(
    cell_dir: str | os.PathLike,
    seed_lo: int | None = None,
    seed_hi: int | None = None,
) -> tuple[list[Record], list[str]]:
    """Load per-game records from `cell_dir`, optionally restricted to a CLOSED
    seed interval [seed_lo, seed_hi].

    Returns (records, malformed_names). The glob is NON-RECURSIVE on purpose:
    `<cell>/failed/seed*_a*.json` carries `"failed": true` and no timing fields
    of this shape, and must never enter a cost reading.
    """
    d = Path(cell_dir)
    out: list[Record] = []
    malformed: list[str] = []
    if not d.is_dir():
        return out, malformed
    for p in sorted(d.glob(RECORD_GLOB)):
        if not p.is_file():
            continue
        parsed = parse_record_name(p.name)
        if parsed is None:
            malformed.append(p.name)
            continue
        seed, a_seat = parsed
        if seed_lo is not None and seed < seed_lo:
            continue
        if seed_hi is not None and seed > seed_hi:
            continue
        try:
            raw = json.loads(p.read_text())
        except Exception:
            # A torn read is possible in principle only if the harness stopped
            # writing atomically; it is recorded, never averaged over.
            malformed.append(p.name)
            continue
        if raw.get("failed"):
            malformed.append(p.name)
            continue
        if any(k not in raw for k in REQUIRED_TIMING_FIELDS):
            malformed.append(p.name)
            continue
        try:
            out.append(
                Record(
                    seed=seed,
                    a_seat=a_seat,
                    path=p,
                    champ_prefix_secs=float(raw["champ_prefix_secs"]),
                    champ_prefix_moves=int(raw["champ_prefix_moves"]),
                    rung_secs=float(raw["rung_secs"]),
                    rung_moves=int(raw["rung_moves"]),
                )
            )
        except (TypeError, ValueError):
            malformed.append(p.name)
    return out, malformed


def timing_ratio(
    records: Iterable[Record],
    expect_seeds: Iterable[int] | None = None,
    seatings: int = SEATINGS_PER_DECK,
    malformed: Iterable[str] | None = None,
) -> RatioReading:
    """THE cost arithmetic. Transcribed from `eval_fair_puct._summary()`.

    `expect_seeds`, when given, makes the reading COMPLETENESS-AWARE: every
    (seed, a_seat) in the expected cross-product must be present or the reading
    reports `complete=False` and names what is missing. A caller that gates on
    an incomplete reading is gating on an unknown window.
    """
    recs = list(records)
    mal = list(malformed or [])
    champ_s = sum(r.champ_prefix_secs for r in recs)
    champ_m = sum(r.champ_prefix_moves for r in recs)
    rung_s = sum(r.rung_secs for r in recs)
    rung_m = sum(r.rung_moves for r in recs)

    champ_ms = (champ_s / champ_m * 1e3) if champ_m > 0 else None
    rung_ms = (rung_s / rung_m * 1e3) if rung_m > 0 else None
    ratio = (champ_ms / rung_ms) if (champ_ms is not None and rung_ms) else None

    seeds_present = {r.seed for r in recs}
    missing: list[str] = []
    complete = True
    if expect_seeds is not None:
        want = sorted(set(expect_seeds))
        have = {(r.seed, r.a_seat) for r in recs}
        for s in want:
            for a in range(seatings):
                if (s, a) not in have:
                    missing.append(f"seed{s:012d}_a{a}.json")
        complete = not missing and not mal

    return RatioReading(
        n_games=len(recs),
        n_decks=len(seeds_present),
        champ_ms_per_move=champ_ms,
        rung_ms_per_move=rung_ms,
        ratio=ratio,
        champ_secs_total=champ_s,
        champ_moves_total=champ_m,
        rung_secs_total=rung_s,
        rung_moves_total=rung_m,
        seed_lo=min(seeds_present) if seeds_present else None,
        seed_hi=max(seeds_present) if seeds_present else None,
        complete=complete,
        missing=missing,
        malformed=mal,
    )


def burnin_seeds(band: int = BAND, n_burnin: int = N_BURNIN_DECKS) -> list[int]:
    """The burn-in window, defined by SEED and never by arrival order.

    `eval_fair_puct._build_work` with `--paired` enumerates
    (seed_start+i, 0), (seed_start+i, 1) for i in range(n//2) -- so the cell's
    first `n_burnin` DECKS are exactly BAND+0 .. BAND+n_burnin-1, and both
    seatings of each. Defining the window by seed (not by "the first 80 records
    to land") is what makes the live gate and the post-hoc gate the same reading:
    the pool completes out of order, so an arrival-order window is not
    reproducible by an adjudicator.
    """
    return [band + i for i in range(n_burnin)]


def read_burnin(
    cell_dir: str | os.PathLike,
    band: int = BAND,
    n_burnin: int = N_BURNIN_DECKS,
) -> RatioReading:
    seeds = burnin_seeds(band, n_burnin)
    recs, mal = load_records(cell_dir, seed_lo=seeds[0], seed_hi=seeds[-1])
    return timing_ratio(recs, expect_seeds=seeds, malformed=mal)


def read_full_cell(
    cell_dir: str | os.PathLike,
    band: int = BAND,
    n_decks: int = N_DECKS,
) -> RatioReading:
    seeds = [band + i for i in range(n_decks)]
    recs, mal = load_records(cell_dir, seed_lo=seeds[0], seed_hi=seeds[-1])
    return timing_ratio(recs, expect_seeds=seeds, malformed=mal)


def in_bar(ratio: float | None, lo: float, hi: float) -> bool:
    """FAIL-CLOSED. `None` (no reading) is FAIL, never 'skip'."""
    if ratio is None:
        return False
    return lo <= ratio <= hi


def verdict(reading: RatioReading, lo: float, hi: float, require_complete: bool = True) -> dict:
    ok = in_bar(reading.ratio, lo, hi)
    if require_complete and not reading.complete:
        ok = False
    d = reading.as_dict()
    d.update({"bar_lo": lo, "bar_hi": hi, "pass": bool(ok)})
    return d


# =============================================================================
# EXCLUSIVE TENANCY
# =============================================================================
#
# CLOSEOUT item 4, verbatim: "Exclusive tenancy is a precondition, not a
# courtesy." Attempt 2 disclosed an Android cross-compile + gradle build on the
# same box during CELL R800's final ~10 minutes. A PREFLIGHT alone would NOT
# have caught that -- the build STARTED after the cell did. So tenancy is
# enforced in two places: a preflight census that refuses to start, and a
# SAMPLER that runs for the whole cell and aborts if a foreign tenant appears.
#
# ⚠️ `ps -o %cpu` is an average over a process's WHOLE LIFETIME, not an
# instantaneous rate -- a long-lived process that was once busy reads high
# forever. This module therefore computes instantaneous CPU% itself, from two
# reads of /proc/<pid>/stat separated by CPU_SAMPLE_INTERVAL. That is the
# difference between a census that works and one that is decorative.

_CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def _proc_snapshot() -> dict[int, tuple[int, int, int, str]]:
    """pid -> (jiffies_used, ppid, pgid, cmdline)."""
    snap: dict[int, tuple[int, int, int, str]] = {}
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        try:
            stat = Path(entry.path, "stat").read_text()
            # comm may contain spaces/parens -- split on the LAST ')'
            rp = stat.rindex(")")
            fields = stat[rp + 2 :].split()
            ppid = int(fields[1])
            pgid = int(fields[2])
            utime = int(fields[11])
            stime = int(fields[12])
            try:
                cl = Path(entry.path, "cmdline").read_bytes().replace(b"\0", b" ").decode(
                    "utf-8", "replace"
                ).strip()
            except OSError:
                cl = ""
            if not cl:
                cl = f"[{stat[stat.index('(') + 1 : rp]}]"
            snap[pid] = (utime + stime, ppid, pgid, cl)
        except (OSError, ValueError, IndexError):
            continue
    return snap


def _descendants(snap: dict[int, tuple[int, int, int, str]], roots: set[int]) -> set[int]:
    """Every pid whose ancestry reaches any pid in `roots`."""
    kids: dict[int, list[int]] = {}
    for pid, (_, ppid, _, _) in snap.items():
        kids.setdefault(ppid, []).append(pid)
    seen = set()
    stack = [r for r in roots if r in snap or r in kids]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(kids.get(p, []))
    return seen


def sample_tenancy(
    own_pids: Iterable[int] = (),
    own_pgids: Iterable[int] = (),
    interval: float = CPU_SAMPLE_INTERVAL,
) -> dict:
    """ONE tenancy sample: instantaneous per-process CPU%, partitioned into
    OURS (the launcher's process tree / process group) and FOREIGN.

    Returns a JSON-able dict. `foreign_total_cpu_pct` is the gated quantity.
    """
    own_pids = set(own_pids) | {os.getpid()}
    own_pgids = set(own_pgids)

    a = _proc_snapshot()
    t0 = time.monotonic()
    time.sleep(interval)
    b = _proc_snapshot()
    dt = max(1e-6, time.monotonic() - t0)

    ours = _descendants(b, own_pids)
    foreign: list[dict] = []
    mine_total = 0.0
    foreign_total = 0.0

    for pid, (j1, ppid, pgid, cmd) in b.items():
        if pid not in a:
            continue
        dj = j1 - a[pid][0]
        if dj <= 0:
            continue
        pct = (dj / _CLK_TCK) / dt * 100.0
        is_ours = (
            pid in ours
            or pgid in own_pgids
            or bool(_SELF_RE.search(cmd))
        )
        if is_ours:
            mine_total += pct
            continue
        foreign_total += pct
        if pct >= FOREIGN_PROC_CPU_PCT:
            foreign.append(
                {
                    "pid": pid,
                    "ppid": ppid,
                    "pgid": pgid,
                    "cpu_pct": round(pct, 1),
                    "sibling_measurement_run": bool(_SIBLING_RE.search(cmd)),
                    "cmd": cmd[:220],
                }
            )

    try:
        la1, la5, la15 = (float(x) for x in Path("/proc/loadavg").read_text().split()[:3])
    except Exception:
        la1 = la5 = la15 = -1.0

    foreign.sort(key=lambda r: -r["cpu_pct"])
    return {
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "interval_s": round(dt, 3),
        "loadavg_1m": la1,
        "loadavg_5m": la5,
        "loadavg_15m": la15,
        "own_cpu_pct": round(mine_total, 1),
        "foreign_total_cpu_pct": round(foreign_total, 1),
        "foreign_procs": foreign[:12],
        "exclusive": foreign_total < FOREIGN_TOTAL_CPU_PCT,
        "bar_foreign_total_cpu_pct": FOREIGN_TOTAL_CPU_PCT,
    }


def foreign_run_live_sentinels(repo: str | os.PathLike, own_dir: str | os.PathLike) -> list[str]:
    """Any OTHER measurement run's freeze-latch sentinel. The h2h precedent's
    first tenancy signal: a live sibling declares itself on disk."""
    own = Path(own_dir).resolve() / "RUN_LIVE.json"
    hits = []
    mroot = Path(repo) / "measurement"
    if not mroot.is_dir():
        return hits
    for p in mroot.rglob("RUN_LIVE.json"):
        if p.resolve() != own:
            hits.append(str(p))
    return sorted(hits)


def tenancy_summary(samples: Iterable[dict]) -> dict:
    """Roll a sampler's JSONL up into the shape `G-TENANCY` adjudicates.

    A cell is an exclusive tenant iff NO run of `TENANCY_CONFIRM_SAMPLES`
    CONSECUTIVE samples ever showed foreign CPU at or above the bar. One
    isolated transient (a `git status`, a log rotation) is not a co-tenant; two
    in a row is.
    """
    ss = list(samples)
    worst = 0.0
    run = 0
    max_run = 0
    offenders: dict[str, float] = {}
    breach_windows: list[dict] = []
    for s in ss:
        f = float(s.get("foreign_total_cpu_pct", 0.0) or 0.0)
        worst = max(worst, f)
        for pr in s.get("foreign_procs", []) or []:
            key = str(pr.get("cmd", ""))[:120]
            offenders[key] = max(offenders.get(key, 0.0), float(pr.get("cpu_pct", 0.0)))
        if f >= FOREIGN_TOTAL_CPU_PCT:
            run += 1
            max_run = max(max_run, run)
            if run == TENANCY_CONFIRM_SAMPLES:
                breach_windows.append({"utc": s.get("utc"), "foreign_total_cpu_pct": f})
        else:
            run = 0
    top = sorted(offenders.items(), key=lambda kv: -kv[1])[:8]
    return {
        "n_samples": len(ss),
        "max_foreign_total_cpu_pct": round(worst, 1),
        "max_consecutive_breach_samples": max_run,
        "confirm_samples_required": TENANCY_CONFIRM_SAMPLES,
        "bar_foreign_total_cpu_pct": FOREIGN_TOTAL_CPU_PCT,
        "breach_windows": breach_windows[:8],
        "top_foreign_by_cpu": [{"cmd": c, "peak_cpu_pct": round(v, 1)} for c, v in top],
        "exclusive": max_run < TENANCY_CONFIRM_SAMPLES,
    }


def read_tenancy_jsonl(path: str | os.PathLike) -> list[dict]:
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


# =============================================================================
# CLI -- used by run_cells.sh. No behaviour lives in the shell.
# =============================================================================

def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="D2-R3 cost-calibration primitives")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("burnin", help="adjudicate the burn-in window from records")
    p_b.add_argument("--cell-dir", required=True)
    p_b.add_argument("--band", type=int, default=BAND)
    p_b.add_argument("--n-burnin", type=int, default=N_BURNIN_DECKS)
    p_b.add_argument("--out", default=None)

    p_w = sub.add_parser("watch", help="poll until the burn-in window completes, then adjudicate")
    p_w.add_argument("--cell-dir", required=True)
    p_w.add_argument("--band", type=int, default=BAND)
    p_w.add_argument("--n-burnin", type=int, default=N_BURNIN_DECKS)
    p_w.add_argument("--out", required=True)
    p_w.add_argument("--poll-secs", type=float, default=20.0)
    p_w.add_argument("--timeout-secs", type=float, default=5400.0)

    p_c = sub.add_parser("census", help="one-shot exclusive-tenancy census (preflight)")
    p_c.add_argument("--repo", required=True)
    p_c.add_argument("--own-dir", required=True)
    p_c.add_argument("--own-pgid", type=int, action="append", default=[])
    p_c.add_argument("--samples", type=int, default=TENANCY_CONFIRM_SAMPLES)
    p_c.add_argument("--out", default=None)

    p_s = sub.add_parser("sampler", help="append tenancy samples to a JSONL for the cell's life")
    p_s.add_argument("--out", required=True)
    p_s.add_argument("--own-pgid", type=int, action="append", default=[])
    p_s.add_argument("--cadence-secs", type=float, default=TENANCY_SAMPLE_SECS)
    p_s.add_argument("--stop-file", default=None)
    p_s.add_argument("--abort-file", default=None)

    a = ap.parse_args()

    if a.cmd == "burnin":
        r = read_burnin(a.cell_dir, a.band, a.n_burnin)
        v = verdict(r, TIMING_LO, TIMING_HI)
        print(json.dumps(v, indent=2, sort_keys=True))
        if a.out:
            Path(a.out).write_text(json.dumps(v, indent=2, sort_keys=True))
        return 0 if v["pass"] else 1

    if a.cmd == "watch":
        deadline = time.monotonic() + a.timeout_secs
        seeds = burnin_seeds(a.band, a.n_burnin)
        want = len(seeds) * SEATINGS_PER_DECK
        while True:
            r = read_burnin(a.cell_dir, a.band, a.n_burnin)
            if r.complete:
                v = verdict(r, TIMING_LO, TIMING_HI)
                v["window"] = "burn-in"
                v["decided_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                Path(a.out).write_text(json.dumps(v, indent=2, sort_keys=True))
                print(json.dumps(v, indent=2, sort_keys=True))
                return 0 if v["pass"] else 1
            if time.monotonic() > deadline:
                v = verdict(r, TIMING_LO, TIMING_HI)
                v["window"] = "burn-in"
                v["pass"] = False
                v["timeout"] = True
                v["note"] = (
                    f"burn-in window incomplete after {a.timeout_secs}s "
                    f"({r.n_games}/{want} games) -- FAIL-CLOSED"
                )
                Path(a.out).write_text(json.dumps(v, indent=2, sort_keys=True))
                print(json.dumps(v, indent=2, sort_keys=True))
                return 2
            print(f"[burnin-watch] {r.n_games}/{want} burn-in games on disk; waiting", flush=True)
            time.sleep(a.poll_secs)

    if a.cmd == "census":
        sentinels = foreign_run_live_sentinels(a.repo, a.own_dir)
        samples = [sample_tenancy(own_pgids=a.own_pgid) for _ in range(max(1, a.samples))]
        roll = tenancy_summary(samples)
        rep = {
            "foreign_run_live_sentinels": sentinels,
            "samples": samples,
            "rollup": roll,
            "pass": (not sentinels) and roll["exclusive"],
        }
        print(json.dumps(rep, indent=2, sort_keys=True))
        if a.out:
            Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True))
        return 0 if rep["pass"] else 1

    if a.cmd == "sampler":
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        streak = 0
        while True:
            if a.stop_file and Path(a.stop_file).exists():
                return 0
            s = sample_tenancy(own_pgids=a.own_pgid)
            with out.open("a") as fh:
                fh.write(json.dumps(s, sort_keys=True) + "\n")
            if s["foreign_total_cpu_pct"] >= FOREIGN_TOTAL_CPU_PCT:
                streak += 1
            else:
                streak = 0
            if streak >= TENANCY_CONFIRM_SAMPLES and a.abort_file:
                Path(a.abort_file).write_text(
                    json.dumps(
                        {
                            "reason": "G-TENANCY: foreign compute on the box",
                            "confirm_samples": TENANCY_CONFIRM_SAMPLES,
                            "sample": s,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 1
            time.sleep(a.cadence_secs)

    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
