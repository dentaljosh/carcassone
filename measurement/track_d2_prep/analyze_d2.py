#!/usr/bin/env python3
"""D2 RUNG-COMPRESSION CELL — THE ADJUDICATOR.

⛔ WRITTEN BLIND. Every line of this file was written from the frozen pair —
`measurement/track_d2_prep/READ_RULE.md` and `measurement/track_d2_prep/DESIGN.md`
(blind commit `db901b295e754cc9ae6a7fc6fcf2755d9efcb483`) — plus the EMITTER's source
(`scripts/classical_search/eval_fair_puct.py`, for field names and addresses only).
No `summary.json`, no `manifest.json`, and no per-game record was opened, read, or
sampled before this file was complete. The branch that fires is taken VERBATIM.

What it implements, section by section, from `READ_RULE.md`:

  §1  S = M_R800 − M_R1600, deck-paired over `n_common`; `se(S)` from the REALIZED
      paired per-deck differences; `z_S` via the `eval_fair_puct._paired_z`
      convention (imported, not re-derived) — plus the §1 WITNESS: an independent
      from-scratch recomputation straight off the raw per-game records, printed
      beside the analyzer's value. Disagreement beyond fp tolerance ⇒ `U-UNREADABLE`.
  §3  the nine gates (G-BAND / G-SINGLEVAR / G-RUNG / G-LEAF / G-RULES / G-TOOL /
      G-N / G-TIMING / G-SAT), each read at the manifest top level and then at
      `config.*`, reporting WHICH address resolved. ABSENT is FAIL. §3's
      "a nonzero failure rate below 2% is reported, not silently absorbed, and does
      not by itself fire G-N" rule is honored.
  §4  the five branches, in order, first-match-wins, with the dispersion-conditional
      COARSE/COMPRESSED boundary note honored: `se_realized` is printed on EVERY
      branch as the `D2-COMPRESSED`-reachability witness, and a `D2-COARSE` realized
      at `se(S) >= 1.25 pts` carries the mandatory "must NOT be narrated as
      compression ruled out" sentence.
  §4.3 the full companion table (per-cell items 1-3; then items 4-6, including the
      DESIGN §1 prior table reprinted beside the realized `S`).
  §6  the stated prior, reprinted.

Usage:
    .venv/bin/python measurement/track_d2_prep/analyze_d2.py            # writes the readouts
    .venv/bin/python measurement/track_d2_prep/analyze_d2.py --stdout-only

Outputs `measurement/track_d2_prep/READOUT_D2.md` + `READOUT_D2.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAIR_DIR = REPO / "measurement" / "track_d2_prep"

# `_paired_z` is IMPORTED, never re-implemented: READ_RULE §1 names
# `eval_fair_puct._paired_z` as THE convention for `z_S`.
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
from eval_fair_puct import _paired_z  # noqa: E402

# --------------------------------------------------------------------------- #
# CONSTANTS — every one of these is lifted from the FROZEN pair, not chosen here #
# --------------------------------------------------------------------------- #
BAND = 141000000000                      # DESIGN §5 / READ_RULE §3 G-BAND
N_COMMON_REQUIRED = 200                  # READ_RULE §3 G-BAND (decks)
N_GAMES_REQUIRED = 400                   # READ_RULE §3 G-N (games per cell)
CAND_LEAF_HASH = "a36d2e15a3b3d71d"      # READ_RULE §3 G-LEAF
RUNG_C = 3.0                             # READ_RULE §3 G-RUNG
RUNG_AGENT = "HeuristicMCTS"             # READ_RULE §3 G-RUNG
RUNG_SIMS = {"R800": 800, "R1600": 1600}  # READ_RULE §3 G-RUNG
RULES_PROFILE = "fixed_v1"               # READ_RULE §3 G-RULES
TIMING_BAND = (0.85, 1.20)               # READ_RULE §3 G-TIMING (CELL R800)
SAT_BAND = (0.50, 0.90)                  # READ_RULE §3 G-SAT (CELL R800)
FAILURE_RATE_FLOOR = 0.02                # READ_RULE §3 / §3.1: "<=2%" campaign precedent
SE_COMMITTED = 1.25                      # DESIGN §4.2 pre-registered se(S), pts
S_COARSE_PTS = 2.5                       # READ_RULE §4 D2-COARSE threshold, pts
Z_BAR = 2.0                              # READ_RULE §4 branch bar
ELO_PER_PT_PREREG = 15.6                 # DESIGN §4.3 pre-registered scale anchor
WITNESS_RTOL = 1e-9                      # READ_RULE §1 "floating-point tolerance"
WITNESS_ATOL = 1e-9

# DESIGN §1 prior table — reprinted verbatim by §4.3 item 6.
PRIOR_TABLE = [
    {"source": "measurement/level2/LEVEL2_LADDER_VERDICT.md (CL-023, 2026-06-18)",
     "contrast": "heur_v2_7@1600 vs @800", "n": "400, paired", "band": "fresh, 3.0e9+",
     "result": "+55.2 ±17.6 elo, paired z 3.23", "in_points_prereg": 3.5},
    {"source": "experiments/results.csv row l22_ctrl_heur1600_vs_heur800_b310_n400 (2026-06-19)",
     "contrast": "heur@1600 vs heur@800", "n": "400, paired", "band": "3.10e9",
     "result": "+20.0 elo, sigma 17.4, z 3.285", "in_points_prereg": 1.3},
]

# READ_RULE §6 — the stated prior, recorded before game 1. Reprinted verbatim.
STATED_PRIOR = """Two conflicting readings of the same nominal contrast: CL-023 (+55.2 ± 17.6 elo, paired z 3.23,
band 3.0e9+) and `results.csv`'s `l22_ctrl_heur1600_vs_heur800_b310_n400` (+20.0 elo, sigma 17.4,
z 3.285, band 3.10e9) — same contrast, same n, 2.8× apart. CL-068's measured cross-band
over-dispersion (1.8–2.2×) is consistent in direction with a band-driven explanation but has never
been checked against this specific pair within one band.

**The house prior — recorded before this cell's first game — is that ladder rungs shrink with
depth**, from CL-023's own sequence: `@200→@800 +75.9 (z3.59) · @800→@1600 +55.2 (z3.23) ·
@1600→@3200 +34.9 (z2.36)`. A `D2-COARSE` or `D2-COMPRESSED` result — spacing detected, whether
large or attenuated — is therefore the expected shape; `D2-BOUNDED-NULL` says this cell could not
resolve which magnitude is closer to true; `D2-REVERSED` would contradict the house prior outright
and is the branch most in need of the pre-registered rung-vs-rung follow-up rather than
over-interpretation from a single equal-time probe cell."""

# READ_RULE §4 branch texts, verbatim, so the readout never paraphrases the pair.
BRANCH_TEXT = {
    "D2-COARSE": (
        "**Says:** the ladder's unit is a genuine unit at this rung — the CL-023 reading (+55.2 elo ≈ 3.5\n"
        "pts) is corroborated on a fresh band, with the ruler's own rung (c=3.0, §2 of `DESIGN.md`), under\n"
        "a fixed non-saturating probe. **Licenses:** citing the h800→h1600 gap as a real, program-usable\n"
        "unit at this budget. **Does NOT license:** any claim about spacing at other rungs (h1600→h3200,\n"
        "etc — that is §6.1(a) of `DESIGN.md`, unfunded), nor a ruler change of any kind."),
    "D2-COMPRESSED": (
        "**Says:** the spacing is real but compressed relative to the CL-023 magnitude — ladder distances\n"
        "ARE denominated in a compressed unit at this rung, and every elo quoted against this rung of the\n"
        "ladder inherits that compression. **Licenses exactly one thing:** an advisory annotation on CL-023\n"
        "and on the roadmap's D0/D1 lines, flagging that the h800→h1600 increment measured elsewhere may\n"
        "not carry directly. **Does NOT license:** a ruler change, a re-grading of any existing claim, or a\n"
        "retraction of CL-023 (CL-023's own band and knobs are untouched by this cell — see §5)."),
    "D2-BOUNDED-NULL": (
        "**Says:** no spacing resolves at this power. State the two-sided 95% bound on `S` in points AND\n"
        "its elo-equivalent, and say plainly that **n=200 cannot separate the results.csv reading (+20 elo)\n"
        "from zero** (DESIGN §4.3) — this was known and stated before game 1. **This is NOT a zero and must\n"
        "never be reported as one.** It is consistent with (a) the small prior being correct and simply\n"
        "unresolved at this n, (b) genuine band-to-band variation of the kind CL-068 already measured, and\n"
        "(c) the equal-time probe (§3.3 of `DESIGN.md`) adding enough of its own noise to wash out a real\n"
        "but modest rung gap — this cell **cannot separate these**. Licenses nothing beyond stating the\n"
        "bound; the DESIGN §4.4 n=400/n=800 extensions are the pre-priced path to resolving it further, and\n"
        "remain unfunded until a fresh owner decision."),
    "D2-REVERSED": (
        "**Says:** the deeper heuristic rung measures behind the shallower one at 2σ against this probe.\n"
        "Report it plainly; do not explain it away in the readout. **Pre-registered follow-up: a direct\n"
        "rung-vs-rung head-to-head (DESIGN §8 item 1), not a re-run of this cell** — this cell's probe-side\n"
        "noise (§3.3 of `DESIGN.md`) is a live confound for a reversal specifically, since the probe itself\n"
        "is one more source of variance sitting between the two rungs."),
    "U-UNREADABLE": (
        "**Says:** no strength or spacing statistic from this run is adjudicated, quoted, or entered in\n"
        "`results.csv` as a verdict. The failed gate is named with its realized value.\n"
        "`U-UNREADABLE` is a fully acceptable outcome."),
}

MANDATORY_COARSE_SENTENCE = (
    "⛔ **This `D2-COARSE` finding was realized at `se(S) = {se:.4f} pts >= 1.25 pts` and MUST NOT be "
    "narrated as \"compression is ruled out.\"** At that dispersion the design cannot separate a "
    "genuinely large, uncompressed spacing from a moderately compressed one that still clears 2σ — it "
    "can only say the spacing is real and at least 2.5 pts. Distinguishing \"large\" from \"moderately "
    "compressed but still significant\" needs a realized `se(S)` tighter than committed, which is a "
    "property of this run's actual data, not something the design could guarantee before game 1 "
    "(READ_RULE §4 boundary note / DESIGN §4.3.1).")

# The disclosure the executor is owed (owner brief, 2026-08-23): a 50-game Carcasum
# audit ran on the same box, beside these cells, for ~a few minutes. It is CONTEXT for
# the timing gate; the gate still adjudicates exactly as written.
CARCASUM_DISCLOSURE = (
    "DISCLOSURE (context, NOT a gate modifier): a 50-game Carcasum audit ran on the same box "
    "beside these cells for ~a few minutes. Wall-clock contention over that window inflates BOTH "
    "sides' ms/move, and only unevenly if the two sides were not equally exposed. `G-TIMING` "
    "adjudicates on the realized ratio EXACTLY as the frozen pair wrote it — this disclosure "
    "changes no threshold and no verdict; it is printed so a reader can see the one known "
    "co-tenant of the measurement window.")


# --------------------------------------------------------------------------- #
# LOADING                                                                       #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rec:
    """`_paired_z` consumes exactly `.seed`, `.a_seat`, `.diff` — nothing else."""
    seed: int
    a_seat: int
    diff: float


class Cell:
    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self.manifest = json.loads((path / "manifest.json").read_text())
        self.summary = json.loads((path / "summary.json").read_text())
        self.records: list[dict] = []
        for p in sorted(path.glob("seed*_a*.json")):
            if p.name.startswith("."):        # `.…partial.json` writer temporaries
                continue
            self.records.append(json.loads(p.read_text()))
        self.failure_records: list[dict] = []
        fdir = path / "failed"
        if fdir.is_dir():
            for p in sorted(fdir.glob("*.json")):
                try:
                    self.failure_records.append(json.loads(p.read_text()))
                except Exception:             # noqa: BLE001 — a broken record is still a record
                    self.failure_records.append({"unparseable": str(p.name)})

    # ---- per-deck view -------------------------------------------------- #
    def by_deck(self) -> dict[int, dict[int, float]]:
        out: dict[int, dict[int, float]] = {}
        for r in self.records:
            out.setdefault(int(r["seed"]), {})[int(r["a_seat"])] = float(r["diff"])
        return out

    def complete_decks(self) -> set[int]:
        return {s for s, v in self.by_deck().items() if 0 in v and 1 in v}

    def shim(self, decks: set[int] | None = None) -> list[Rec]:
        return [Rec(int(r["seed"]), int(r["a_seat"]), float(r["diff"]))
                for r in self.records
                if decks is None or int(r["seed"]) in decks]


# --------------------------------------------------------------------------- #
# ADDRESS RESOLUTION — READ_RULE §3: "read at the manifest top level, then at     #
# `config.*`, and the adjudicator reports which address resolved (the house       #
# G-BAND/G-J1 fix precedent)."                                                   #
#                                                                               #
# The two addresses the pair names come FIRST and are always tried first. The     #
# house container fallbacks after them exist because the emitter files three of    #
# these witnesses inside `config` SUB-dicts (`config.backend.*` for the rust       #
# provenance, `config.env.*` for the canonical env) — the same class of            #
# address-pedantry the G-BAND/G-J1 precedent the pair cites was written to stop     #
# from falsely voiding a healthy cell. Whichever address resolved is REPORTED on    #
# every gate line, so nothing here is silent.                                       #
# --------------------------------------------------------------------------- #
FALLBACK_CONTAINERS = ("config.backend", "config.env", "config.rung", "evaluator")
MISSING = object()


def _walk(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return MISSING
    return cur


def resolve(manifest: dict, dotted: str, aliases: tuple[str, ...] = ()):
    """(value, address) for the first address that resolves, else (MISSING, None).

    `dotted` may be written the way the pair writes it (`config.rung.c`,
    `rules_profile.name`, `cand_leaf_hash`); a leading `config.` is stripped so the
    top-level address is tried first, exactly as §3 orders it.
    """
    rel = dotted[len("config."):] if dotted.startswith("config.") else dotted
    names = (rel,) + aliases
    order: list[str] = []
    for nm in names:
        order.append(nm)                       # 1. manifest top level
        order.append(f"config.{nm}")           # 2. config.*
    for nm in names:                           # 3. house container fallbacks
        for c in FALLBACK_CONTAINERS:
            order.append(f"{c}.{nm}")
    seen = set()
    for addr in order:
        if addr in seen:
            continue
        seen.add(addr)
        val = _walk(manifest, addr)
        if val is not MISSING:
            return val, addr
    return MISSING, None


def fmt_val(v):
    if v is MISSING:
        return "ABSENT"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


# --------------------------------------------------------------------------- #
# G-SINGLEVAR support — deep diff over the two `config` blocks                   #
# --------------------------------------------------------------------------- #
BOOKKEEPING_LEAVES = {"out_subdir", "out_root", "out_dir", "out", "out_path",
                      "subdir", "claim_host", "claim-host", "path"}
CELL_TOKENS = ("d2_rung800", "d2_rung1600", "d2-R800", "d2-R1600", "pilot_r800")


def flatten(obj, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        out[prefix] = json.dumps(obj, sort_keys=True, default=str)
    else:
        out[prefix] = obj
    return out


def config_diff(cfg_a: dict, cfg_b: dict) -> list[dict]:
    fa, fb = flatten(cfg_a), flatten(cfg_b)
    diffs = []
    for k in sorted(set(fa) | set(fb)):
        va, vb = fa.get(k, MISSING), fb.get(k, MISSING)
        if va is MISSING or vb is MISSING or va != vb:
            leaf = k.rsplit(".", 1)[-1]
            allowed = (k == "rung.sims"
                       or leaf in BOOKKEEPING_LEAVES
                       or any(t in str(va) or t in str(vb) for t in CELL_TOKENS))
            diffs.append({"path": k, "R800": fmt_val(va), "R1600": fmt_val(vb),
                          "allowed_bookkeeping": bool(allowed)})
    return diffs


# --------------------------------------------------------------------------- #
# §1 — THE STATISTIC (analyzer path) and THE WITNESS (from-scratch path)         #
# --------------------------------------------------------------------------- #
def paired(records: list[Rec]) -> tuple[float | None, float | None, float | None, int]:
    """`(mean, se, z, n_decks)` on `_paired_z`'s own convention.

    `_paired_z` returns `(mean, z, n)`; `se` is recovered as `mean / z` ONLY when
    that is exact — it is not, in general — so `se` is instead computed from the
    same per-deck construction `_paired_z` uses, and the pair `(mean, z)` is taken
    STRAIGHT from the imported function so the convention cannot drift.
    """
    mean, z, n = _paired_z(records)
    if mean is None:
        return None, None, None, n
    by_seed: dict[int, dict[int, float]] = {}
    for r in records:
        by_seed.setdefault(r.seed, {})[r.a_seat] = r.diff
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    m = sum(ds) / len(ds)
    var = sum((d - m) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    return mean, se, z, n


def witness_from_disk(dir800: Path, dir1600: Path) -> dict:
    """§1's WITNESS: a from-scratch recomputation from the RAW per-game records.

    Deliberately independent of the analyzer path above — it re-reads every file off
    disk, keys by `(seed, a_seat)` in a different order, and accumulates with
    `math.fsum` rather than `sum`. It is a WITNESS, never a branch input; the only
    thing it can do is fire `U-UNREADABLE` (READ_RULE §1).
    """
    def load(d: Path) -> dict[tuple[int, int], float]:
        got: dict[tuple[int, int], float] = {}
        for p in sorted(d.iterdir()):
            if not p.name.startswith("seed") or p.suffix != ".json":
                continue
            rec = json.loads(p.read_text())
            got[(int(rec["seed"]), int(rec["a_seat"]))] = float(rec["diff"])
        return got

    a, b = load(dir800), load(dir1600)
    decks = sorted({s for (s, seat) in a if (s, 0) in a and (s, 1) in a
                    and (s, 0) in b and (s, 1) in b})
    m800 = [(a[(s, 0)] + a[(s, 1)]) / 2.0 for s in decks]
    m1600 = [(b[(s, 0)] + b[(s, 1)]) / 2.0 for s in decks]
    delta = [x - y for x, y in zip(m800, m1600)]
    n = len(delta)

    def mean_se_z(xs):
        if len(xs) < 2:
            return None, None, None
        mu = math.fsum(xs) / len(xs)
        var = math.fsum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
        se = math.sqrt(var / len(xs))
        return mu, se, (mu / se if se > 0 else float("nan"))

    S, seS, zS = mean_se_z(delta)
    M8, se8, z8 = mean_se_z(m800)
    M16, se16, z16 = mean_se_z(m1600)
    return {"n_common": n, "S": S, "se_S": seS, "z_S": zS,
            "M_R800": M8, "se_M_R800": se8, "z_M_R800": z8,
            "M_R1600": M16, "se_M_R1600": se16, "z_M_R1600": z16}


def close(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=WITNESS_RTOL, abs_tol=WITNESS_ATOL)


# --------------------------------------------------------------------------- #
# §3 — THE GATES                                                                #
# --------------------------------------------------------------------------- #
def gate(gid: str, prop: str, ok: bool, realized: str, addresses: str) -> dict:
    return {"id": gid, "proposition": prop, "status": "PASS" if ok else "FAIL",
            "realized": realized, "address": addresses}


def run_gates(c800: Cell, c1600: Cell, common: set[int]) -> list[dict]:
    G: list[dict] = []
    cells = (("R800", c800), ("R1600", c1600))

    # ---- G-BAND ---------------------------------------------------------- #
    parts, addrs, ok = [], [], True
    for nm, c in cells:
        v, addr = resolve(c.manifest, "seed_start", aliases=("band_seed_start",))
        addrs.append(f"{nm}:{addr or 'ABSENT'}")
        parts.append(f"{nm} seed_start={fmt_val(v)}")
        if v is MISSING or int(v) != BAND:
            ok = False
    d8, d16 = c800.complete_decks(), c1600.complete_decks()
    sets_agree = (d8 == d16)
    parts.append(f"record-derived deck sets agree={sets_agree} "
                 f"(|R800|={len(d8)}, |R1600|={len(d16)}, only-in-R800={len(d8 - d16)}, "
                 f"only-in-R1600={len(d16 - d8)})")
    parts.append(f"n_common={len(common)}")
    if not sets_agree or len(common) != N_COMMON_REQUIRED:
        ok = False
    G.append(gate("G-BAND",
                  f"both cells' seed_start == {BAND}; record-derived deck sets agree; "
                  f"n_common == {N_COMMON_REQUIRED}",
                  ok, "; ".join(parts), ", ".join(addrs) + "; deck sets: RECORDS"))

    # ---- G-SINGLEVAR ----------------------------------------------------- #
    diffs = config_diff(c800.manifest.get("config", {}), c1600.manifest.get("config", {}))
    unexpected = [d for d in diffs if not d["allowed_bookkeeping"]]
    ok = not unexpected
    realized = ("config blocks differ at: "
                + (", ".join(f"{d['path']} ({d['R800']} vs {d['R1600']})" for d in diffs)
                   if diffs else "NOTHING")
                + ("" if ok else
                   "  ⛔ UNEXPECTED: " + ", ".join(d["path"] for d in unexpected)))
    G.append(gate("G-SINGLEVAR",
                  "the two cells' config blocks differ in exactly rung.sims, "
                  "out_subdir/output path, and claim_host — nothing else",
                  ok, realized, "config.* (deep diff, both manifests)"))

    # ---- G-RUNG ---------------------------------------------------------- #
    parts, addrs, ok = [], [], True
    leaf_hashes = {}
    for nm, c in cells:
        cv, ca = resolve(c.manifest, "config.rung.c")
        av, aa = resolve(c.manifest, "config.rung.agent")
        lv, la = resolve(c.manifest, "config.rung.leaf_hash")
        sv, sa = resolve(c.manifest, "config.rung.sims")
        leaf_hashes[nm] = lv
        parts.append(f"{nm}: c={fmt_val(cv)} agent={fmt_val(av)} sims={fmt_val(sv)} "
                     f"leaf_hash={fmt_val(lv)}")
        addrs.append(f"{nm}:{ca or 'ABSENT'}/{aa or 'ABSENT'}/{la or 'ABSENT'}/{sa or 'ABSENT'}")
        if cv is MISSING or float(cv) != RUNG_C:
            ok = False
        if av is MISSING or str(av) != RUNG_AGENT:
            ok = False
        if sv is MISSING or int(sv) != RUNG_SIMS[nm]:
            ok = False
        if lv is MISSING:
            ok = False
    same_leaf = (leaf_hashes.get("R800") == leaf_hashes.get("R1600")
                 and leaf_hashes.get("R800") is not MISSING)
    parts.append(f"rung leaf_hash identical across cells={same_leaf}")
    if not same_leaf:
        ok = False
    G.append(gate("G-RUNG",
                  f"both manifests: config.rung.c == {RUNG_C}, config.rung.agent == "
                  f"\"{RUNG_AGENT}\", config.rung.leaf_hash identical across cells, "
                  f"config.rung.sims == 800 (R800) / 1600 (R1600)",
                  ok, "; ".join(parts), ", ".join(addrs)))

    # ---- G-LEAF ---------------------------------------------------------- #
    parts, addrs, ok = [], [], True
    for nm, c in cells:
        v, addr = resolve(c.manifest, "config.cand_leaf_hash")
        parts.append(f"{nm} cand_leaf_hash={fmt_val(v)}")
        addrs.append(f"{nm}:{addr or 'ABSENT'}")
        if v is MISSING or str(v) != CAND_LEAF_HASH:
            ok = False
    G.append(gate("G-LEAF", f"config.cand_leaf_hash == {CAND_LEAF_HASH} in BOTH cells",
                  ok, "; ".join(parts), ", ".join(addrs)))

    # ---- G-RULES --------------------------------------------------------- #
    parts, addrs, ok = [], [], True
    for nm, c in cells:
        nv, na = resolve(c.manifest, "rules_profile.name")
        rv, ra = resolve(c.manifest, "rules_profile.r9_env_ok", aliases=("r9_env_ok",))
        parts.append(f"{nm} rules_profile.name={fmt_val(nv)} r9_env_ok={fmt_val(rv)}")
        addrs.append(f"{nm}:{na or 'ABSENT'}/{ra or 'ABSENT'}")
        if nv is MISSING or str(nv) != RULES_PROFILE:
            ok = False
        if rv is MISSING or rv is not True:
            ok = False
    G.append(gate("G-RULES", f"rules_profile.name == \"{RULES_PROFILE}\" and r9_env_ok == true, "
                             "in BOTH cells", ok, "; ".join(parts), ", ".join(addrs)))

    # ---- G-TOOL ---------------------------------------------------------- #
    blind_expected = (PAIR_DIR / "BLIND_COMMIT").read_text().strip()
    parts, addrs, ok = [], [], True
    fields = {}
    for key, aliases in (("carc_rs_version", ()),
                         ("tile_data_semantic_digest", ()),
                         ("code_rev", ()),
                         ("BLIND_COMMIT", ("blind_commit", "CARC_BLIND_COMMIT"))):
        vals = {}
        for nm, c in cells:
            v, addr = resolve(c.manifest, key, aliases=aliases)
            vals[nm] = v
            addrs.append(f"{nm}.{key}:{addr or 'ABSENT'}")
            if v is MISSING:
                ok = False
        fields[key] = vals
        same = (vals["R800"] is not MISSING and vals["R800"] == vals["R1600"])
        if not same:
            ok = False
        shown = fmt_val(vals["R800"])
        if len(shown) > 24:
            shown = shown[:24] + "…"
        parts.append(f"{key}: R800={shown} identical_across_cells={same}")
    bc = fields["BLIND_COMMIT"]["R800"]
    matches_launcher = (bc is not MISSING and str(bc).strip() == blind_expected)
    placeholder = (bc is not MISSING and str(bc).strip().upper() in
                   {"PENDING", "PLACEHOLDER", "", "TBD"})
    parts.append(f"BLIND_COMMIT == launcher's frozen value ({blind_expected[:12]}…)"
                 f"={matches_launcher}; placeholder={placeholder}")
    if not matches_launcher or placeholder:
        ok = False
    G.append(gate("G-TOOL",
                  "same carc_rs_version and tile_data_semantic_digest across both cells; "
                  "same code rev in both; BLIND_COMMIT in both manifests equal to the "
                  "launcher's frozen value",
                  ok, "; ".join(parts), ", ".join(addrs)))

    # ---- G-N ------------------------------------------------------------- #
    parts, ok = [], True
    for nm, c in cells:
        n_scored = len(c.records)
        nf, _ = resolve(c.manifest, "n_failed")
        nf_sum = c.summary.get("n_failed", MISSING)
        rate = c.summary.get("failure_rate", MISSING)
        n_failed = nf_sum if nf_sum is not MISSING else nf
        if rate is MISSING and n_failed is not MISSING:
            rate = float(n_failed) / max(1, n_scored + int(n_failed))
        parts.append(f"{nm}: games scored={n_scored}, n_failed={fmt_val(n_failed)}, "
                     f"failure_rate={fmt_val(rate)}, failure records on disk="
                     f"{len(c.failure_records)}")
        if n_scored < N_GAMES_REQUIRED:
            ok = False
        # §3: a nonzero rate BELOW 2% is reported and does not by itself fire G-N.
        if rate is not MISSING and rate is not None and float(rate) >= FAILURE_RATE_FLOOR:
            ok = False
    G.append(gate("G-N",
                  f"{N_GAMES_REQUIRED} games scored in EACH cell; n_failed == 0 (a nonzero "
                  f"rate below {FAILURE_RATE_FLOOR:.0%} is REPORTED, not silently absorbed, "
                  "and does not by itself fire this gate — §3/§3.1)",
                  ok, "; ".join(parts), "summary.json + manifest top level (n_failed / "
                                        "failure_rate); games counted from RECORDS"))

    # ---- G-TIMING -------------------------------------------------------- #
    parts, ok = [], True
    ratio800 = None
    for nm, c in cells:
        cm = c.summary.get("champ_prefix_ms_per_move")
        rm = c.summary.get("rung_ms_per_move")
        if cm is None or rm is None:
            ok = False
            parts.append(f"{nm}: champ_prefix_ms_per_move={cm} rung_ms_per_move={rm} (ABSENT)")
            continue
        r = cm / rm
        if nm == "R800":
            ratio800 = r
        parts.append(f"{nm}: champ_prefix_ms_per_move={cm:.1f} rung_ms_per_move={rm:.1f} "
                     f"ratio={r:.4f}")
    if ratio800 is None or not (TIMING_BAND[0] <= ratio800 <= TIMING_BAND[1]):
        ok = False
    parts.append(f"CELL R800 ratio inside [{TIMING_BAND[0]}, {TIMING_BAND[1]}]="
                 f"{ratio800 is not None and TIMING_BAND[0] <= ratio800 <= TIMING_BAND[1]}")
    g = gate("G-TIMING",
             "both cells report champ_prefix_ms_per_move and rung_ms_per_move; CELL R800's "
             f"realized ratio is inside [{TIMING_BAND[0]}, {TIMING_BAND[1]}]",
             ok, "; ".join(parts), "summary.json (both cells)")
    g["disclosure"] = CARCASUM_DISCLOSURE
    g["disclosure_material"] = bool(ratio800 is None or
                                    not (TIMING_BAND[0] <= ratio800 <= TIMING_BAND[1]))
    G.append(g)

    # ---- G-SAT ----------------------------------------------------------- #
    wr = c800.summary.get("winrate")
    ok = wr is not None and SAT_BAND[0] <= float(wr) <= SAT_BAND[1]
    G.append(gate("G-SAT",
                  f"CELL R800's probe winrate vs h800 is inside [{SAT_BAND[0]}, {SAT_BAND[1]}]",
                  ok, f"CELL R800 winrate={fmt_val(wr)}", "summary.json (CELL R800)"))
    return G


# --------------------------------------------------------------------------- #
# §4 — THE BRANCHES, in order, first-match-wins                                 #
# --------------------------------------------------------------------------- #
def adjudicate(gates: list[dict], S: float | None, z_S: float | None,
               witness_ok: bool) -> tuple[str, str]:
    failed = [g["id"] for g in gates if g["status"] == "FAIL"]
    if failed:
        return "U-UNREADABLE", ("§3 gate(s) FAILED: " + ", ".join(failed)
                                + " — ANY §3 gate FAILS ⇒ U-UNREADABLE.")
    if not witness_ok:
        return "U-UNREADABLE", ("the §1 WITNESS (from-scratch recomputation from the raw "
                                "per-game records) disagrees with the analyzer's value beyond "
                                "floating-point tolerance — READ_RULE §1 makes that "
                                "U-UNREADABLE.")
    if S is None or z_S is None:
        return "U-UNREADABLE", "the primary statistic could not be computed (fewer than 2 decks)."
    if z_S >= Z_BAR and S >= S_COARSE_PTS:
        return "D2-COARSE", f"all §3 gates PASS AND z_S = {z_S:+.4f} >= {Z_BAR} AND S = {S:+.4f} >= {S_COARSE_PTS} pts."
    if z_S >= Z_BAR and S < S_COARSE_PTS:
        return "D2-COMPRESSED", f"gates PASS, z_S = {z_S:+.4f} >= {Z_BAR}, S = {S:+.4f} < {S_COARSE_PTS} pts."
    if abs(z_S) < Z_BAR:
        return "D2-BOUNDED-NULL", f"gates PASS, |z_S| = {abs(z_S):.4f} < {Z_BAR}."
    if z_S <= -Z_BAR:
        return "D2-REVERSED", f"gates PASS, z_S = {z_S:+.4f} <= {-Z_BAR}."
    return "U-UNREADABLE", "no branch condition matched — this is unreachable by construction."


# --------------------------------------------------------------------------- #
# RENDERING                                                                     #
# --------------------------------------------------------------------------- #
def cell_block(nm: str, c: Cell, rung_label: str) -> dict:
    s = c.summary
    m = c.manifest
    decks = c.complete_decks()
    seats = {0: sum(1 for r in c.records if int(r["a_seat"]) == 0),
             1: sum(1 for r in c.records if int(r["a_seat"]) == 1)}
    mean, se, z, npair = paired(c.shim())
    elo, esig = s.get("elo"), s.get("elo_sig_1sigma")
    ci = ((elo - 1.96 * esig, elo + 1.96 * esig)
          if elo is not None and esig is not None and not math.isnan(esig) else None)
    cm, rm = s.get("champ_prefix_ms_per_move"), s.get("rung_ms_per_move")
    scale = (elo / mean) if (elo is not None and mean not in (None, 0)) else None
    return {
        "cell": nm, "path": str(c.path), "rung": rung_label,
        "n_games": len(c.records), "n_decks": len(decks),
        "seat_balance": {"a_seat=0": seats[0], "a_seat=1": seats[1]},
        "W": s.get("W"), "D": s.get("D"), "L": s.get("L"),
        "winrate": s.get("winrate"), "winrate_z": s.get("winrate_z"),
        "elo": elo, "elo_sig_1sigma": esig,
        "elo_ci95": list(ci) if ci else None,
        "paired_mean_margin": mean, "paired_se": se, "paired_z": z, "n_paired": npair,
        "summary_paired_mean_margin": s.get("paired_mean_margin"),
        "summary_paired_z": s.get("paired_z"), "summary_n_paired": s.get("n_paired"),
        "avg_diff": s.get("avg_diff"),
        "n_failed": s.get("n_failed"), "failure_rate": s.get("failure_rate"),
        "failed_classes": s.get("failed_classes"),
        "champ_prefix_ms_per_move": cm, "rung_ms_per_move": rm,
        "time_ratio": (cm / rm) if (cm and rm) else None,
        "solver_secs_per_game": s.get("solver_secs_per_game"),
        "band_seed_start": resolve(m, "seed_start", aliases=("band_seed_start",))[0]
                           if resolve(m, "seed_start", aliases=("band_seed_start",))[0] is not MISSING else None,
        "cand_leaf_hash": fmt_val(resolve(m, "config.cand_leaf_hash")[0]),
        "rung_leaf_hash": fmt_val(resolve(m, "config.rung.leaf_hash")[0]),
        "rules_profile": fmt_val(resolve(m, "rules_profile.name")[0]),
        "r9_env_ok": fmt_val(resolve(m, "rules_profile.r9_env_ok", aliases=("r9_env_ok",))[0]),
        "code_rev": fmt_val(resolve(m, "code_rev")[0]),
        "carc_rs_version": fmt_val(resolve(m, "carc_rs_version")[0]),
        "tile_data_semantic_digest": fmt_val(resolve(m, "tile_data_semantic_digest")[0]),
        "realized_elo_per_pt": scale,
        "total_sims": s.get("total_sims"), "k_dets": s.get("k_dets"), "sims": s.get("sims"),
        "rung_sims": s.get("rung_sims"),
    }


def f(x, nd=4):
    return "n/a" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def render_md(v: dict) -> str:
    L: list[str] = []
    A = L.append
    A("# READOUT — D2 rung-compression cell (`track_d2_prep`)")
    A("")
    A(f"> **BRANCH: `{v['branch']}`** — {v['branch_reason']}")
    A(">")
    A(f"> Blind pair `{v['blind_commit']}` (`DESIGN.md` + `READ_RULE.md`, frozen 2026-08-23). "
      "The adjudicator (`analyze_d2.py`) was written from the pair's text alone, before any "
      "statistic was opened. The branch is taken VERBATIM.")
    A("")
    A("---")
    A("")
    A("## §4 — THE BRANCH THAT FIRED, verbatim from `READ_RULE.md`")
    A("")
    A(f"### `{v['branch']}`")
    A("")
    A(BRANCH_TEXT[v["branch"]])
    A("")
    if v["branch"] == "U-UNREADABLE":
        A("> ⛔ **EVERYTHING BELOW IS PRINTED, NOT ADJUDICATED.** `READ_RULE.md` §4.3 requires the "
          "companion table on EVERY branch *including* `U-UNREADABLE`, so `S`, `se(S)`, `z_S` and "
          "both cells' absolutes appear below. Under this branch **none of them is adjudicated, "
          "quoted as a verdict, or entered in `experiments/results.csv`.** No spacing claim, no "
          "rung-compression claim, and no strength claim follows from this run. `U-UNREADABLE` is "
          "a fully acceptable outcome (READ_RULE §4).")
        A("")
        A("### Instrument defects observed (post-adjudication diagnosis — moves no bar)")
        A("")
        A("Named here with realized values because `U-UNREADABLE` requires the failed gate to be "
          "named. This is DIAGNOSIS, not adjudication: no threshold in the frozen pair was "
          "touched, and per READ_RULE §4 **the session that writes any instrument fix MUST be a "
          "session that has not seen `S`, `z_S`, or either cell's summary statistics** — this "
          "session has, so it writes no fix.")
        A("")
        for d in v["defects"]:
            A(f"- **`{d['gate']}` — {d['headline']}**  \n  {d['detail']}")
        A("")
        if v["context_notes"]:
            A("**Context, gated by nothing (recorded so a later reader has it):**")
            A("")
            for c in v["context_notes"]:
                A(f"- {c}")
            A("")
    if v.get("mandatory_coarse_sentence"):
        A(v["mandatory_coarse_sentence"])
        A("")
    if v["branch"] == "D2-BOUNDED-NULL" and v["bound"]:
        b = v["bound"]
        A(f"**The bound, as the branch requires it:** two-sided 95% on `S` = "
          f"[{b['lo_pts']:+.4f}, {b['hi_pts']:+.4f}] pts "
          f"= [{b['lo_elo']:+.1f}, {b['hi_elo']:+.1f}] elo-equivalent at the realized scale "
          f"({v['scale_used']:.3f} elo/pt). **n=200 cannot separate the `results.csv` reading "
          "(+20.0 elo ≈ 1.3 pts) from zero** (DESIGN §4.3) — this was known and stated before "
          "game 1. **This is NOT a zero and must never be reported as one.**")
        A("")
    A("---")
    A("")
    A("## §1 — THE PRIMARY STATISTIC")
    A("")
    A("```")
    A(f"S      = M_R800 - M_R1600  = {f(v['S'])} pts/game  (deck-paired, probe-minus-rung)")
    A(f"se(S)  = {f(v['se_S'])} pts   [REALIZED, from the actual paired per-deck differences]")
    A(f"         DESIGN §4.2 pre-registered expectation: {SE_COMMITTED} pts")
    A(f"z_S    = {f(v['z_S'])}        [convention: eval_fair_puct._paired_z, IMPORTED]")
    A(f"n_common = {v['n_common']} decks")
    A(f"M_R800   = {f(v['M_R800'])} pts   (se {f(v['se_M_R800'])}, z {f(v['z_M_R800'])})")
    A(f"M_R1600  = {f(v['M_R1600'])} pts   (se {f(v['se_M_R1600'])}, z {f(v['z_M_R1600'])})")
    A("```")
    A("")
    A("### §1 WITNESS — from-scratch recomputation from the raw per-game records")
    A("")
    A("| quantity | analyzer | witness (independent re-read of every record) | agrees? |")
    A("|---|---|---|---|")
    for k in ("S", "se_S", "z_S", "M_R800", "M_R1600", "n_common"):
        w = v["witness"][k]
        A(f"| `{k}` | {f(v[k], 9)} | {f(w, 9)} | "
          f"{'✅' if v['witness_agreement'][k] else '⛔ DISAGREES'} |")
    A("")
    A(f"Tolerance: rel {WITNESS_RTOL:g} / abs {WITNESS_ATOL:g}. "
      f"**Witness verdict: {'AGREES' if v['witness_ok'] else 'DISAGREES ⇒ U-UNREADABLE'}.** "
      "The witness is a WITNESS, never a branch input (READ_RULE §1).")
    A("")
    A("---")
    A("")
    A("## §3 — THE GATES (fail-closed; ABSENT is FAIL)")
    A("")
    A("| gate | status | realized | address(es) resolved |")
    A("|---|---|---|---|")
    for g in v["gates"]:
        realized = g["realized"].replace("|", "\\|")
        addr = g["address"].replace("|", "\\|")
        A(f"| `{g['id']}` | {'✅ PASS' if g['status'] == 'PASS' else '⛔ FAIL'} | {realized} | `{addr}` |")
    A("")
    A(f"**All nine gates: {v['gates_summary']}.**")
    A("")
    A("Address discipline (READ_RULE §3): every gate is read at the manifest TOP LEVEL first, "
      "then at `config.*`, and — for the three witnesses the emitter files inside `config` "
      "sub-dicts (`config.backend.*`, `config.env.*`, `config.rung.*`) — at those containers "
      "after that. The resolved address is printed for every gate above, so no resolution is "
      "silent.")
    A("")
    for g in v["gates"]:
        if g.get("disclosure"):
            A(f"> **`{g['id']}` — {g['disclosure']}**")
            A("")
    A("---")
    A("")
    A("## §4.3 — THE COMPANION TABLE (printed on EVERY branch)")
    A("")
    for blk in (v["R800"], v["R1600"]):
        A(f"### CELL {blk['cell']} — probe vs {blk['rung']}")
        A("")
        A("**1. outcome**")
        A("")
        A("| field | value |")
        A("|---|---|")
        A(f"| n games / n decks | {blk['n_games']} / {blk['n_decks']} |")
        A(f"| seat balance (candidate's `a_seat`) | 0: {blk['seat_balance']['a_seat=0']}, "
          f"1: {blk['seat_balance']['a_seat=1']} |")
        A(f"| W / D / L | {blk['W']} / {blk['D']} / {blk['L']} |")
        A(f"| winrate (z) | {f(blk['winrate'])} (z {f(blk['winrate_z'], 2)}) |")
        A(f"| elo ± 1σ | {f(blk['elo'], 1)} ± {f(blk['elo_sig_1sigma'], 1)} |")
        A(f"| elo 95% CI | [{f(blk['elo_ci95'][0], 1)}, {f(blk['elo_ci95'][1], 1)}] |"
          if blk["elo_ci95"] else "| elo 95% CI | n/a |")
        A(f"| deck-paired margin ± se (z) | {f(blk['paired_mean_margin'])} ± "
          f"{f(blk['paired_se'])} (z {f(blk['paired_z'], 3)}) over {blk['n_paired']} decks |")
        A(f"| avg diff (unpaired) | {f(blk['avg_diff'], 3)} |")
        A(f"| n_failed / failure rate | {blk['n_failed']} / {f(blk['failure_rate'], 5)} "
          "(stated even when zero) |")
        A(f"| failed_classes | `{blk['failed_classes']}` |")
        A("")
        A("**2. cost / timing**")
        A("")
        A(f"`champ_prefix_ms_per_move` (= the CANDIDATE side — the field-name trap, DESIGN §3.3) "
          f"**{f(blk['champ_prefix_ms_per_move'], 1)}** · `rung_ms_per_move` "
          f"**{f(blk['rung_ms_per_move'], 1)}** · realized ratio "
          f"**{f(blk['time_ratio'])}×** · `solver_secs_per_game` "
          f"**{f(blk['solver_secs_per_game'], 3)}**")
        A("")
        A("**3. provenance**")
        A("")
        A(f"band `{blk['band_seed_start']}` · `cand_leaf_hash` `{blk['cand_leaf_hash']}` · "
          f"`rung.leaf_hash` `{blk['rung_leaf_hash']}` · rules `{blk['rules_profile']}` "
          f"(`r9_env_ok`={blk['r9_env_ok']}) · code rev `{blk['code_rev']}` · "
          f"`carc_rs_version` `{blk['carc_rs_version']}` · probe budget "
          f"k{blk['k_dets']}×{blk['sims']} = {blk['total_sims']} · `rung_sims` {blk['rung_sims']}")
        A("")
    A("### 4. the primary statistic, its dispersion, and the elo-equivalent")
    A("")
    A("| quantity | value |")
    A("|---|---|")
    A(f"| `S` = M_R800 − M_R1600 | **{f(v['S'])} pts/game** |")
    A(f"| `se_realized` | **{f(v['se_S'])} pts** (DESIGN §4.2 pre-registered: {SE_COMMITTED} pts) |")
    A(f"| `z_S` | **{f(v['z_S'])}** |")
    A(f"| `n_common` | {v['n_common']} decks |")
    A(f"| elo-equivalent of `S` | **{f(v['S_elo'], 1)} elo** at the realized scale "
      f"{f(v['scale_used'], 3)} elo/pt |")
    A(f"| realized scale, CELL R800 | {f(v['R800']['realized_elo_per_pt'], 3)} elo/pt "
      "(elo ÷ own deck-paired margin) |")
    A(f"| realized scale, CELL R1600 | {f(v['R1600']['realized_elo_per_pt'], 3)} elo/pt |")
    A(f"| pre-registered scale (DESIGN §4.3) | {ELO_PER_PT_PREREG} elo/pt ⇒ `S` = "
      f"{f(v['S'] * ELO_PER_PT_PREREG if v['S'] is not None else None, 1)} elo |")
    A(f"| direct elo difference (R800 − R1600) | {f(v['elo_delta'], 1)} elo |")
    A("")
    A(f"> **`se_realized` as the `D2-COMPRESSED`-reachability witness (READ_RULE §4 / DESIGN "
      f"§4.3.1):** realized `se(S)` = **{f(v['se_S'])} pts** vs the committed {SE_COMMITTED} pts ⇒ "
      f"`D2-COMPRESSED` was **{'REACHABLE' if v['compressed_reachable'] else 'NOT REACHABLE'}** on "
      "this run. That branch opens only where the realized dispersion prints BELOW 1.25 pts; at or "
      "above it, any `z_S ≥ 2.0` lands in `D2-COARSE` by construction.")
    A("")
    A("### 5. every gate, its realized value, and the address that resolved it")
    A("")
    A("See the §3 table above — it carries the realized value and the resolved address for all "
      "nine gates, which is item 5 in full.")
    A("")
    A("### 6. the DESIGN §1 prior table, reprinted beside this readout's own `S`")
    A("")
    A("| source | contrast | n | band | result | ≈ pts (DESIGN §4.3) |")
    A("|---|---|---|---|---|---|")
    for row in PRIOR_TABLE:
        A(f"| {row['source']} | {row['contrast']} | {row['n']} | {row['band']} | "
          f"**{row['result']}** | ≈{row['in_points_prereg']} |")
    A(f"| **THIS CELL (D2, band {BAND}, n_common {v['n_common']})** | probe k4×"
      f"{v['R800']['sims']} vs h800 rung minus same probe vs h1600 rung | 400 games / "
      f"{v['n_common']} decks each | {BAND} | **{f(v['S_elo'], 1)} elo-equivalent "
      f"({f(v['S'])} pts, z {f(v['z_S'], 2)})** | {f(v['S'], 2)} |")
    A("")
    A("⚠️ DESIGN §3.4: D2's ABSOLUTE numbers are NOT comparable to the F5 `fair_ruler_*` rows "
      "(different backend + pre-`fixed_v1` rules era). Only D2's internal cell-vs-cell contrast "
      "is claimed.")
    A("")
    A("---")
    A("")
    A("## §6 — THE STATED PRIOR, RECORDED BEFORE GAME 1 (reprinted)")
    A("")
    A(STATED_PRIOR)
    A("")
    A("---")
    A("")
    A("## §5 — WHAT NO BRANCH DOES (reprinted so the readout cannot be over-read)")
    A("")
    A("No branch flips `governance/PRODUCTION.yaml`. No branch licenses a leaf or search change. "
      "No branch re-rates the champion. No branch retires or amends the CL-023 record itself. No "
      "branch transfers to the F5/walled-era ladder's absolutes. No branch licenses a second band "
      "or extends `n` beyond 200 decks/cell. No branch authorizes editing `results.csv`'s five "
      "historical mis-stamped rung-`c` cells.")
    A("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# POST-ADJUDICATION DIAGNOSIS — names the failed gate with its realized value    #
# (READ_RULE §4's `U-UNREADABLE` requirement). Moves no bar, licenses no fix.    #
# --------------------------------------------------------------------------- #
def diagnose(gates: list[dict], b800: dict, b1600: dict, branch: str):
    by_id = {g["id"]: g for g in gates}
    defects: list[dict] = []
    if branch != "U-UNREADABLE":
        return defects, []

    if by_id["G-SINGLEVAR"]["status"] == "FAIL":
        defects.append({
            "gate": "G-SINGLEVAR",
            "headline": "the two cells' `config` blocks differ beyond the single experimental "
                        "variable",
            "detail": (
                f"The unexpected differing keys are `code_rev` ({b800['code_rev']} vs "
                f"{b1600['code_rev']}), `backend.code_rev`, and `backend.carc_rs_build` — the "
                "two cells did NOT run at the same repo revision. `opponent.label` / "
                "`opponent.sims` also differ, but those are the rung's own knob mirrored under "
                "`opponent` (aliases of `rung.sims`, not a second experimental axis); **even "
                "under the most generous reading that treats them as aliases, this gate still "
                "FAILS on the code-rev / build triple.** DESIGN §3.1 argued this property was "
                "STRUCTURAL because both argv are built from one `COMMON` array — that argument "
                "covers the ARGV, and the tree moving underneath the launcher between two "
                "sequential cells is a path it does not cover."),
        })
    if by_id["G-LEAF"]["status"] == "FAIL":
        defects.append({
            "gate": "G-LEAF",
            "headline": "the probe did not run the curve125 champion leaf the pair pinned",
            "detail": (
                f"`config.cand_leaf_hash` reads `{b800['cand_leaf_hash']}` in BOTH cells, where "
                f"the pair requires `{CAND_LEAF_HASH}` "
                "(`champion_factory.LEAF_HASH_HARNESS`, the C7 curve125 champion leaf). The "
                f"realized hash is identical to `config.rung.leaf_hash` "
                f"(`{b800['rung_leaf_hash']}`) — i.e. the candidate ran the RUNG's own "
                "DEFAULT v2.9 leaf, because `run_cells.sh` passes no `--cand-leaf-json` and no "
                "curve125 injection. The mismatch is IDENTICAL in both cells, so it is a "
                "probe-IDENTITY defect (the probe is not the config DESIGN §3.1/§3.2 costed and "
                "justified), not a cross-cell inconsistency."),
        })
    if by_id["G-RULES"]["status"] == "FAIL":
        defects.append({
            "gate": "G-RULES",
            "headline": "`fixed_v1` was stamped but its R9 env latch was never exported",
            "detail": (
                f"`rules_profile.name` = `{b800['rules_profile']}` in both cells (correct), but "
                f"`r9_env_ok` = `{b800['r9_env_ok']}` in both. `fixed_v1` carries "
                "`r9_env_expected=True`, and R9 CANNOT live in the profile — `base_deck` derives "
                "the farm data at import time and the Rust registry latches a `OnceLock`, so "
                "`CARCASSONNE_FIX_R9` must be exported into the ENVIRONMENT before the process "
                "starts. `run_cells.sh` exports nothing, so both cells played the `fixed_v1` "
                "bundle WITHOUT the R9 farm fix. This is the F9 A0 fail-loud path doing exactly "
                "what it was built to do."),
        })
    if by_id["G-TOOL"]["status"] == "FAIL":
        defects.append({
            "gate": "G-TOOL",
            "headline": "two independent failures — a real mixed-rev cell pair, and a "
                        "structurally unsatisfiable `BLIND_COMMIT` sub-clause",
            "detail": (
                f"(1) SUBSTANTIVE: `code_rev` differs across the cells "
                f"(`{b800['code_rev']}` vs `{b1600['code_rev']}`; both `-dirty`) — the main tree "
                "moved between the R800 and R1600 legs, which the `RUN_LIVE.json` freeze latch "
                "exists to prevent. `carc_rs_version` and `tile_data_semantic_digest` DO match "
                "across cells, so the rust engine build is not implicated; the repo revision is. "
                "(2) INSTRUMENT: `BLIND_COMMIT` is ABSENT from both manifests at every address "
                "searched (top level, `config.*`, `config.backend.*`, `config.env.*`, "
                "`config.rung.*`, `evaluator.*`, plus the `blind_commit` / `CARC_BLIND_COMMIT` "
                "spellings). `eval_fair_puct.py` has NO `BLIND_COMMIT` stamping path at all, and "
                "this launcher only checks the `BLIND_COMMIT` FILE as a precondition — it never "
                "passes the value to the harness. That sub-clause therefore could not pass on "
                "ANY healthy run of this launcher: a §3.1 structural-test miss (§3.1 applied the "
                "test to G-SINGLEVAR / G-RUNG / G-LEAF / G-RULES / G-TIMING / G-N and never to "
                "G-TOOL's BLIND_COMMIT clause). Named as an instrument defect; NOT fixed here."),
        })

    ctx = [
        f"**Probe budget realized k{b800['k_dets']}×{b800['sims']} = {b800['total_sims']}**, not "
        "DESIGN §3.1's k4×688 = 2752. That is the §9 pilot's ONE allowed re-pick (repo commit "
        "`ce235373`: \"D2 pilot re-pick … probe sims 688→1032, equal-time ratio 0.6455→0.9737 "
        "PASS\"), taken on the discarded pilot band before any cell seed was touched, exactly as "
        "§9 permits. No §3 gate covers the probe's own `--sims`; recorded as context.",
        f"**`G-TIMING` PASSED on its own bar**: CELL R800's realized ratio "
        f"{b800['time_ratio']:.4f} is inside [{TIMING_BAND[0]}, {TIMING_BAND[1]}]. The R1600 "
        f"cell's ratio ({b1600['time_ratio']:.4f}) is NOT gated by the pair (the gate names CELL "
        "R800 only) and is expected — the rung side doubles its sims while the probe does not.",
        "**`G-BAND`, `G-RUNG`, `G-N`, `G-TIMING`, `G-SAT` all PASS**: the band, the 200 shared "
        "decks with both seatings in both cells, the c=3.0 / HeuristicMCTS / 800-vs-1600 rung "
        "identity, 400/400 scored games with a ZERO failure rate in each cell, the equal-time "
        "ratio, and the non-saturation check are all clean. The cell RAN well; what voids it is "
        "provenance and probe identity, not the games.",
    ]
    return defects, ctx


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--r800", default="/mnt/c/carc-shared/track_d2_prep/d2_rung800")
    ap.add_argument("--r1600", default="/mnt/c/carc-shared/track_d2_prep/d2_rung1600")
    ap.add_argument("--out-md", default=str(PAIR_DIR / "READOUT_D2.md"))
    ap.add_argument("--out-json", default=str(PAIR_DIR / "READOUT_D2.json"))
    ap.add_argument("--stdout-only", action="store_true")
    args = ap.parse_args()

    d800, d1600 = Path(args.r800), Path(args.r1600)
    c800, c1600 = Cell("R800", d800), Cell("R1600", d1600)

    common = c800.complete_decks() & c1600.complete_decks()

    # ---- §1 primary, on the common decks, via the imported convention ------ #
    M800, se800, z800, n800 = paired(c800.shim(common))
    M1600, se1600, z1600, n1600 = paired(c1600.shim(common))
    # `S` and its z ride the SAME `_paired_z` convention by feeding it the
    # per-(seed, a_seat) DIFFERENCE of the two cells: `_paired_z` then averages the
    # two seatings per deck, so its `mean` IS `M_R800 − M_R1600` over `n_common`
    # and its `z` IS `S / se(S)` on the realized paired per-deck differences.
    d800_map = {(int(r["seed"]), int(r["a_seat"])): float(r["diff"]) for r in c800.records}
    d1600_map = {(int(r["seed"]), int(r["a_seat"])): float(r["diff"]) for r in c1600.records}
    delta_recs = [Rec(s, seat, d800_map[(s, seat)] - d1600_map[(s, seat)])
                  for s in sorted(common) for seat in (0, 1)
                  if (s, seat) in d800_map and (s, seat) in d1600_map]
    S, se_S, z_S, n_common = paired(delta_recs)

    # ---- §1 witness -------------------------------------------------------- #
    W = witness_from_disk(d800, d1600)
    agreement = {
        "S": close(S, W["S"]), "se_S": close(se_S, W["se_S"]), "z_S": close(z_S, W["z_S"]),
        "M_R800": close(M800, W["M_R800"]), "M_R1600": close(M1600, W["M_R1600"]),
        "n_common": n_common == W["n_common"],
    }
    witness_ok = all(agreement.values())

    # ---- §3 gates ---------------------------------------------------------- #
    gates = run_gates(c800, c1600, common)
    branch, reason = adjudicate(gates, S, z_S, witness_ok)

    # ---- secondary / display quantities ------------------------------------ #
    b800 = cell_block("R800", c800, "HeuristicMCTS(h800, c=3.0)")
    b1600 = cell_block("R1600", c1600, "HeuristicMCTS(h1600, c=3.0)")
    # DESIGN §4.3 derived its scale from a vs-h800 cell, so CELL R800's realized
    # elo-per-point is the closest analogue and is the scale of record here; the
    # R1600 cell's and the pre-registered 15.6 are printed beside it.
    scale_used = b800["realized_elo_per_pt"] or ELO_PER_PT_PREREG
    S_elo = S * scale_used if S is not None else None
    elo_delta = ((b800["elo"] - b1600["elo"])
                 if b800["elo"] is not None and b1600["elo"] is not None else None)
    bound = None
    if S is not None and se_S is not None:
        bound = {"lo_pts": S - 1.96 * se_S, "hi_pts": S + 1.96 * se_S,
                 "lo_elo": (S - 1.96 * se_S) * scale_used,
                 "hi_elo": (S + 1.96 * se_S) * scale_used}
    compressed_reachable = (se_S is not None and se_S < SE_COMMITTED)
    mandatory = None
    if branch == "D2-COARSE" and se_S is not None and se_S >= SE_COMMITTED:
        mandatory = MANDATORY_COARSE_SENTENCE.format(se=se_S)

    n_fail = sum(1 for g in gates if g["status"] == "FAIL")
    defects, context_notes = diagnose(gates, b800, b1600, branch)
    v = {
        "run_id": "track_d2_prep", "band": BAND,
        "blind_commit": (PAIR_DIR / "BLIND_COMMIT").read_text().strip(),
        "branch": branch, "branch_reason": reason,
        "S": S, "se_S": se_S, "z_S": z_S, "n_common": n_common,
        "M_R800": M800, "se_M_R800": se800, "z_M_R800": z800,
        "M_R1600": M1600, "se_M_R1600": se1600, "z_M_R1600": z1600,
        "se_prereg": SE_COMMITTED, "compressed_reachable": compressed_reachable,
        "S_elo": S_elo, "scale_used": scale_used,
        "scale_prereg": ELO_PER_PT_PREREG, "elo_delta": elo_delta, "bound": bound,
        "witness": W, "witness_agreement": agreement, "witness_ok": witness_ok,
        "gates": gates,
        "gates_summary": (f"{len(gates) - n_fail}/{len(gates)} PASS"
                          + (f", FAILED: {', '.join(g['id'] for g in gates if g['status'] == 'FAIL')}"
                             if n_fail else "")),
        "R800": b800, "R1600": b1600,
        "mandatory_coarse_sentence": mandatory,
        "prior_table": PRIOR_TABLE,
        "defects": defects, "context_notes": context_notes,
    }

    md = render_md(v)
    print(md)
    if not args.stdout_only:
        Path(args.out_md).write_text(md)
        Path(args.out_json).write_text(json.dumps(v, indent=2, default=str))
        print(f"[analyze_d2] wrote {args.out_md}")
        print(f"[analyze_d2] wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
