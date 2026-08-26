#!/usr/bin/env python3
"""D2-R2 RUNG-COMPRESSION CELL (instrument-fix successor) — THE ADJUDICATOR.

⛔ PROVENANCE OF THIS FILE — read before trusting a single line of it.

This adjudicator is a **mechanical port of the predecessor pair's
`measurement/track_d2_prep/analyze_d2.py`**, which was itself WRITTEN BLIND from the
frozen pair text before any statistic existed. The port is legitimate precisely
because `READ_RULE.md` §1–§6 of THIS pair are **VERBATIM identical** to the
predecessor's (the successor's own §0 banner enumerates the exhaustive list of
changes: run id, band, launcher reference, the banner, and the §3.1 structural
re-test — no bar, gate, threshold or branch condition moved). Every constant,
gate predicate, branch condition and first-match-wins ordering below is therefore
BYTE-IDENTICAL to the blind original.

What this port changed, exhaustively:
  1. run id / pair dir  `track_d2_prep` -> `track_d2r2_prep`
  2. `BAND`             141000000000 -> 144000000000 (READ_RULE §3 G-BAND)
  3. `CELL_TOKENS`      the cell output-path tokens (`d2r2_rung800/1600`)
  4. output filenames   `READOUT_D2R2.{md,json}`
  5. `config_diff`      an explicit, narrow MIRROR allowance for `G-SINGLEVAR`
                        (see the comment at `config_diff` — it implements the
                        frozen §3.1's own committed answer for that gate, and it
                        does not change this run's branch either way)
  6. `diagnose()`       rewritten data-driven, since the predecessor's defect
                        prose named the FIRST attempt's four realized failures
  7. the co-tenancy disclosure, restated for THIS run's actual measurement window
No constant in the CONSTANTS block other than `BAND` was touched; no gate predicate
was touched; `adjudicate()` is untouched.

⚠️ The session that RAN this port is an ADJUDICATING session and has now seen the
statistics. Per READ_RULE §4 it therefore writes NO instrument fix — any fix is a
fresh, statistics-blind session's job.

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
    .venv/bin/python measurement/track_d2r2_prep/analyze_d2r2.py            # writes the readouts
    .venv/bin/python measurement/track_d2r2_prep/analyze_d2r2.py --stdout-only

Outputs `measurement/track_d2r2_prep/READOUT_D2R2.md` + `READOUT_D2R2.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAIR_DIR = REPO / "measurement" / "track_d2r2_prep"

# `_paired_z` is IMPORTED, never re-implemented: READ_RULE §1 names
# `eval_fair_puct._paired_z` as THE convention for `z_S`.
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
from eval_fair_puct import _paired_z  # noqa: E402

# --------------------------------------------------------------------------- #
# CONSTANTS — every one of these is lifted from the FROZEN pair, not chosen here #
# --------------------------------------------------------------------------- #
BAND = 144000000000                      # DESIGN §5 / READ_RULE §3 G-BAND
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

# REALIZED COST — read off the launcher's own cell logs (`logs/cells_R*.log`, the final
# cumulative "N/400 played (X s/game)" line) and the cell mtimes. NOT a statistic and not
# a gate input; printed as an appendix because DESIGN §6 priced this cell and §0 item 6
# warned in advance that §6's arithmetic reads LOW.
COST_REALIZED = {
    "W": 22,
    "R800": {"s_per_game": 6.7, "n": 400, "window": "19:06-19:51 EDT 2026-08-25"},
    "R1600": {"s_per_game": 10.2, "n": 400, "window": "19:51-20:58 EDT 2026-08-25"},
    "design_s6_core_h": {"R800": 6.5, "R1600": 9.6, "total": 16.1},
    "design_s6_wall_h_at_W22": 0.75,
}

# CO-TENANCY DISCLOSURE for THIS run's window, established from filesystem evidence
# after adjudication. It is CONTEXT for the timing gate; the gate still adjudicates
# exactly as the frozen pair wrote it.
CARCASUM_DISCLOSURE = (
    "DISCLOSURE (context, NOT a gate modifier): the local box was NOT an exclusive tenant for "
    "the whole of CELL R800. CELL R800 ran ~19:06-19:51 EDT 2026-08-25; within its final ~10 "
    "minutes an ANDROID BUILD ran on the same box — `android/native/carc-cy/build/android/*.c` "
    "and the cross-compiled Cython wheels stamp 19:47, the rust wheels and the gradle/kotlin "
    "outputs 19:48, and the finished APK landed on the share at 19:51 "
    "(`/mnt/c/carc-shared/apk/app-debug-22k-20260825.apk`); `tests/android/*` pytest artifacts "
    "stamp 19:35-19:41. A cross-compile + gradle build is a heavy multi-core co-tenant, and the "
    "house rule `feedback_no_agent_compute_beside_eval` says a TIMING measurement is an "
    "EXCLUSIVE tenant. Contention inflates BOTH sides' ms/move and does so UNEVENLY when the two "
    "sides have different bottlenecks (the python `HeuristicMCTS` rung is DRAM-latency-bound; the "
    "rust probe is not), so the DIRECTION of any bias on the champ/rung ratio is not determined "
    "by this evidence and is NOT asserted here. (The `evloss_autopsy_20260824` shards that touch "
    "the share at 20:51-20:56 ran on laptop-wsl, a DIFFERENT box, and fall in CELL R1600's "
    "window, which `G-TIMING` does not gate.) `G-TIMING` adjudicates on the realized ratio "
    "EXACTLY as the frozen pair wrote it — this disclosure changes no threshold and no verdict; "
    "it is printed so a reader can see the known co-tenancy of the measurement window.")


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
CELL_TOKENS = ("d2r2_rung800", "d2r2_rung1600", "d2r2-R800", "d2r2-R1600", "pilot_r800")


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


def is_rung_sims_mirror(va, vb, rs_a, rs_b) -> bool:
    """Is this differing key a provable MIRROR of the ONE experimental variable?

    ⚠️ THE ONE INTERPRETIVE ADDITION IN THIS PORT — narrow, mechanical, and printed.

    `eval_fair_puct.py` echoes the rung's `--rung-sims` into a SECOND place in the
    manifest, `config.opponent.{sims,label}`. Those are not a second experimental
    axis; they are the same `--rung-sims` written twice by the emitter. A LITERAL
    key-set reading of `G-SINGLEVAR` ("differ in exactly `rung.sims`, output path,
    and `claim_host` — nothing else") would therefore FAIL on EVERY healthy run of
    this launcher, because the two cells differ in `--rung-sims` BY DESIGN and the
    emitter always mirrors it.

    "Would this gate fail on every healthy run?" is exactly the §3.1 structural test,
    and the FROZEN pair answered it for this gate BEFORE game 1: **NO** — "guaranteed
    by the launcher building both cells' argv from one shared `COMMON` array; the
    property is structural, not clerical." That pre-registered answer is only
    consistent with the reading in which an emitter mirror of the single experimental
    argument is that argument, not a second one. This function implements that
    reading, and nothing wider:

      - NUMERIC mirror: the key's two values ARE the two cells' `rung.sims`.
      - STRING mirror: the two values become the SAME string once each cell's own
        `rung.sims` token is normalised away (`HeuristicMCTS(h800)` vs
        `HeuristicMCTS(h1600)`).

    Anything else — any key whose two values are not reconstructible from
    `rung.sims` alone — is still UNEXPECTED and still fails the gate. Every key
    allowed by this rule is named in the gate's realized text, and the LITERAL
    key-set reading is printed beside it, so a reader can adjudicate both ways.
    """
    try:
        if int(va) == int(rs_a) and int(vb) == int(rs_b):
            return True
    except (TypeError, ValueError):
        pass
    sa, sb, ra, rb = str(va), str(vb), str(rs_a), str(rs_b)
    if ra in sa and rb in sb:
        tok = "\x00RUNG_SIMS\x00"
        if sa.replace(ra, tok) == sb.replace(rb, tok):
            return True
    return False


def config_diff(cfg_a: dict, cfg_b: dict,
                rung_sims: tuple[object, object] | None = None) -> list[dict]:
    fa, fb = flatten(cfg_a), flatten(cfg_b)
    rs_a, rs_b = rung_sims if rung_sims else (None, None)
    diffs = []
    for k in sorted(set(fa) | set(fb)):
        va, vb = fa.get(k, MISSING), fb.get(k, MISSING)
        if va is MISSING or vb is MISSING or va != vb:
            leaf = k.rsplit(".", 1)[-1]
            experimental = (k == "rung.sims")
            bookkeeping = (leaf in BOOKKEEPING_LEAVES
                           or any(t in str(va) or t in str(vb) for t in CELL_TOKENS))
            mirror = bool(rs_a is not None and not experimental and not bookkeeping
                          and va is not MISSING and vb is not MISSING
                          and is_rung_sims_mirror(va, vb, rs_a, rs_b))
            reason = ("the single experimental variable" if experimental else
                      "bookkeeping / output path" if bookkeeping else
                      "emitter MIRROR of rung.sims" if mirror else "UNEXPECTED")
            diffs.append({"path": k, "R800": fmt_val(va), "R1600": fmt_val(vb),
                          "allowed_bookkeeping": bool(experimental or bookkeeping or mirror),
                          "mirror_of_rung_sims": mirror, "reason": reason})
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
    rs_pair = (resolve(c800.manifest, "config.rung.sims")[0],
               resolve(c1600.manifest, "config.rung.sims")[0])
    diffs = config_diff(c800.manifest.get("config", {}), c1600.manifest.get("config", {}),
                        rung_sims=rs_pair)
    unexpected = [d for d in diffs if not d["allowed_bookkeeping"]]
    mirrors = [d for d in diffs if d["mirror_of_rung_sims"]]
    ok = not unexpected
    realized = ("config blocks differ at: "
                + (", ".join(f"{d['path']} ({d['R800']} vs {d['R1600']}) [{d['reason']}]"
                             for d in diffs) if diffs else "NOTHING")
                + ("" if ok else
                   "  ⛔ UNEXPECTED: " + ", ".join(d["path"] for d in unexpected)))
    if mirrors:
        realized += ("  ⚠️ MIRROR READING APPLIED to "
                     + ", ".join(d["path"] for d in mirrors)
                     + " — these are the emitter's second copy of --rung-sims, not a second "
                       "experimental axis; the frozen §3.1 answered NO for this gate "
                       "('structural, not clerical'), which only holds under this reading. "
                       "Under a LITERAL key-set reading this gate would read FAIL — and would "
                       "read FAIL on EVERY healthy run of this launcher, which is the §3.1 "
                       "defect class itself. Both readings are printed; see the readout.")
    G.append(gate("G-SINGLEVAR",
                  "the two cells' config blocks differ in exactly rung.sims, "
                  "out_subdir/output path, and claim_host — nothing else",
                  ok, realized, "config.* (deep diff, both manifests)"))
    G[-1]["mirror_paths"] = [d["path"] for d in mirrors]
    G[-1]["literal_reading_status"] = "FAIL" if (unexpected or mirrors) else "PASS"

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
    A("# READOUT — D2-R2 rung-compression cell (`track_d2r2_prep`), "
      "the instrument-fix successor")
    A("")
    A(f"> **BRANCH: `{v['branch']}`** — {v['branch_reason']}")
    A(">")
    A(f"> Blind pair `{v['blind_commit']}` (`DESIGN.md` + `READ_RULE.md`, frozen 2026-08-23; "
      "band `144000000000` claimed 2026-08-24; probe budget amended pre-game-1 to k4×1376 at "
      "`d3c720cf`). The adjudicator (`analyze_d2r2.py`) is a **mechanical port of the "
      "predecessor pair's `../track_d2_prep/analyze_d2.py`**, which WAS written from the frozen "
      "pair's text alone before any statistic was opened; the port is sound because this pair's "
      "READ_RULE §1–§6 are VERBATIM identical to the predecessor's, and every constant, gate "
      "predicate and branch condition is carried byte-identical (the file's own module docstring "
      "enumerates the seven changes). The branch is taken VERBATIM.")
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
    A("## APPENDIX — COST REALIZED vs DESIGN §6 (not a statistic, not a gate input)")
    A("")
    A("| cell | wall | core-h at W=22 | DESIGN §6 projection | ratio |")
    A("|---|---|---|---|---|")
    tot_wall = tot_core = 0.0
    for nm in ("R800", "R1600"):
        c = COST_REALIZED[nm]
        wall = c["s_per_game"] * c["n"]
        core = wall * COST_REALIZED["W"] / 3600.0
        tot_wall += wall
        tot_core += core
        proj = COST_REALIZED["design_s6_core_h"][nm]
        A(f"| CELL {nm} ({c['window']}) | {wall / 60:.0f} min ({c['s_per_game']} s/game "
          f"× {c['n']}) | {core:.1f} | {proj} core-h | {core / proj:.2f}× |")
    A(f"| **TOTAL** | **{tot_wall / 3600:.2f} h** | **{tot_core:.1f}** | "
      f"**{COST_REALIZED['design_s6_core_h']['total']} core-h** "
      f"(wall ≈{COST_REALIZED['design_s6_wall_h_at_W22']} h at W=22) | "
      f"**{tot_core / COST_REALIZED['design_s6_core_h']['total']:.2f}×** |")
    A("")
    A("The overrun was ANTICIPATED, in two named pieces, and needs no explaining away: "
      "**(1)** DESIGN §0 item 6 states outright that §6's arithmetic is the k4×688-era figure "
      "and reads LOW — the probe actually ran k4×1376 = 5504, **2× §6's 2752 probe sims**; "
      "**(2)** DESIGN §0 item 9 (the pre-game-1 amendment) measured that FIX 1's "
      "`CARCASSONNE_FIX_R9` export makes the frozen python `HeuristicMCTS` rung **~58% more "
      "expensive per move** (553.8 → 877.2 ms/move on the same rung, leaf, rev and box), and "
      "§6 was costed against the non-R9 rung. A third piece is NOT pre-priced: the realized "
      "rung cost on the 400-game cell (1103.1 ms/move) is a further **+25.8%** over the "
      "amendment's own 877.2 ms/move bench — the same gap that moved the timing ratio from the "
      "pilot's in-bar 0.9428 to the cell's out-of-bar 0.8382.")
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
    """Name the failed gate(s) with realized values — READ_RULE §4's `U-UNREADABLE`
    requirement. DIAGNOSIS ONLY: moves no bar, licenses no fix, and (per READ_RULE §4)
    the session running this has seen the statistics, so it writes no instrument fix.

    Rewritten data-driven for this successor. The predecessor's prose named the FIRST
    attempt's four realized failures; those four gates are exactly what FIX 1-4 closed,
    so hard-coded prose would be wrong here on every line.
    """
    by_id = {g["id"]: g for g in gates}
    defects: list[dict] = []
    if branch != "U-UNREADABLE":
        return defects, []

    # ---- G-TIMING: the equal-time precondition, re-checked on the REAL cell ---- #
    if by_id["G-TIMING"]["status"] == "FAIL":
        r = b800["time_ratio"]
        lo, hi = TIMING_BAND
        if r is None:
            detail = ("`champ_prefix_ms_per_move` and/or `rung_ms_per_move` is ABSENT from a "
                      "cell's `summary.json`; ABSENT is FAIL (READ_RULE §3).")
            headline = "the timing fields the gate reads are absent"
        else:
            side = "BELOW" if r < lo else "ABOVE"
            edge = lo if r < lo else hi
            detail = (
                f"CELL R800's realized equal-time ratio is **{r:.4f}** "
                f"(`champ_prefix_ms_per_move` {b800['champ_prefix_ms_per_move']:.1f} — the "
                f"CANDIDATE side, the field-name trap of DESIGN §3.3 — over `rung_ms_per_move` "
                f"{b800['rung_ms_per_move']:.1f}), which is {side} the frozen interval "
                f"[{lo}, {hi}] by {abs(r - edge):.4f} ({abs(r - edge) / edge:.2%} of the "
                f"{'floor' if r < lo else 'ceiling'}). This is the §9 pilot's own bar re-checked "
                "on the real cell, exactly as READ_RULE §3 requires, and it is the check whose "
                "absence on the real cells the successor's §3.1 explicitly refused to grant "
                "('a real precondition, not a formality'). "
                f"THE PILOT PASSED IT: the §9 pilot at this same budget (k{b800['k_dets']}×"
                f"{b800['sims']}) read 831/881 = 0.9428, comfortably in-bar. The gap between "
                "pilot and cell is on the RUNG side — the python `HeuristicMCTS(h800)` rung cost "
                f"881 ms/move on a 16-game pilot and {b800['rung_ms_per_move']:.1f} ms/move on "
                f"the 400-game cell (+{b800['rung_ms_per_move'] / 881.0 - 1:.1%}), while the "
                f"rust probe moved 831 -> {b800['champ_prefix_ms_per_move']:.1f} "
                f"(+{b800['champ_prefix_ms_per_move'] / 831.0 - 1:.1%}). A 16-game pilot does "
                "not saturate 22 workers; a 400-game cell does, and the two sides do not "
                "degrade equally under saturation. **The pilot is therefore not a valid "
                "predictor of the cell's ratio at this W** — stated as a mechanism observation, "
                "not as a fix. See also the co-tenancy disclosure on this gate: an Android "
                "cross-compile + gradle build occupied the same box for the final ~10 minutes "
                "of this cell, whose effect on the ratio is real in magnitude and undetermined "
                "in direction.")
            headline = ("CELL R800's realized equal-time ratio is outside the frozen "
                        f"[{lo}, {hi}] interval")
        defects.append({"gate": "G-TIMING", "headline": headline, "detail": detail})

    # ---- the other eight, named generically from their own realized text ------- #
    GENERIC = {
        "G-BAND": "the band / deck-set / n_common precondition",
        "G-SINGLEVAR": "the single-experimental-variable precondition",
        "G-RUNG": "the rung's identity (c, agent, leaf hash, sims)",
        "G-LEAF": "the probe's leaf identity (the curve125 champion leaf)",
        "G-RULES": "the rules profile + its R9 environment latch",
        "G-TOOL": "one-instrument provenance (rust build, code rev, BLIND_COMMIT)",
        "G-N": "the completed-games / failure-rate precondition",
        "G-SAT": "the non-saturation precondition",
    }
    for gid, what in GENERIC.items():
        g = by_id.get(gid)
        if g is None or g["status"] != "FAIL":
            continue
        defects.append({
            "gate": gid,
            "headline": f"{what} FAILED",
            "detail": (f"Realized: {g['realized']}  \n  Resolved at: `{g['address']}`. "
                       "ABSENT is FAIL (READ_RULE §3, fail-closed)."),
        })

    # ---- CONTEXT: what the cell DID establish, gated by nothing ---------------- #
    passed = [g["id"] for g in gates if g["status"] == "PASS"]
    sv = by_id.get("G-SINGLEVAR", {})
    ctx = [
        f"**FIX 1-4 — the whole point of this successor — all VERIFIED on the real cells.** "
        f"`G-RULES` reads `rules_profile.name`=`{b800['rules_profile']}` with "
        f"`r9_env_ok`=`{b800['r9_env_ok']}` in both cells (FIX 1); `G-LEAF` reads "
        f"`cand_leaf_hash`=`{b800['cand_leaf_hash']}` = the pinned champion curve125 leaf, "
        f"DISTINCT from the rung's `{b800['rung_leaf_hash']}` (FIX 2); `G-TOOL` reads ONE code "
        f"rev `{b800['code_rev']}` in both cells (FIX 3) and `BLIND_COMMIT` present and equal to "
        "the launcher's frozen value at BOTH searched addresses, manifest top level AND "
        "`config.stamps.*` (FIX 4). The four gates that voided the first attempt all PASS.",
        f"**Probe budget realized k{b800['k_dets']}×{b800['sims']} = {b800['total_sims']}**, "
        "which is DESIGN §0 item 9 (AMENDMENT 2026-08-25, `d3c720cf`) — the orchestrator's "
        "pair-level re-pick from k4×1032 after the §9 pilot read 0.659 on BOTH boxes, taken "
        "with the band UNSPENT and under READ_RULE §179-183's own delegation. No §3 gate covers "
        "the probe's own `--sims`; recorded as context.",
        f"**The R1600 cell's ratio ({b1600['time_ratio']:.4f}) is NOT gated** — the frozen gate "
        "names CELL R800 only, and the R1600 ratio is expected to sit low because the rung side "
        "doubles its sims while the probe does not.",
        f"**Gates that PASS: {', '.join(passed) if passed else 'NONE'}.** In particular the cell "
        f"RAN clean: {b800['n_games']}/{b800['n_decks']}-deck and "
        f"{b1600['n_games']}/{b1600['n_decks']}-deck cells, `n_failed` "
        f"{b800['n_failed']}/{b1600['n_failed']}, failure rate "
        f"{b800['failure_rate']}/{b1600['failure_rate']}, band "
        f"{b800['band_seed_start']} in both, and CELL R800's probe winrate "
        f"{b800['winrate']} sits well inside the `G-SAT` interval "
        f"[{SAT_BAND[0]}, {SAT_BAND[1]}]. What voids this run is a COST-CALIBRATION "
        "precondition, not the games and not the instrument fixes.",
    ]
    if sv.get("mirror_paths"):
        ctx.append(
            "⚠️ **A LATENT §3.1 DEFECT, found while adjudicating and reported for the "
            "orchestrator (not fixed here).** `G-SINGLEVAR` reads PASS under the mirror "
            "reading this port implements, but the emitter mirrors `--rung-sims` into "
            + ", ".join(f"`{p}`" for p in sv["mirror_paths"])
            + ", so under a LITERAL key-set reading of the gate's own words ('nothing else') "
              "it would read FAIL — and would read FAIL on EVERY healthy run of this launcher, "
              "because the two cells differ in `--rung-sims` by design and the emitter always "
              "echoes it. That is the same defect CLASS as the first attempt's unsatisfiable "
              "`G-TOOL` sub-clause, surviving a §3.1 re-test that was explicitly re-run over all "
              "nine gates. The frozen §3.1's own committed answer for this gate ('structural, "
              "not clerical' — i.e. NO, it does not fail on a healthy run) is what makes the "
              "mirror reading the pre-registered one, so this run's branch is unaffected; a "
              "future pair should nevertheless say so in the gate's TEXT rather than leave it "
              "to an adjudicator's reading. **This run's branch does not turn on it either "
              "way** — `G-TIMING` fails independently.")
    return defects, ctx

# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--r800", default="/mnt/c/carc-shared/track_d2r2_prep/d2r2_rung800")
    ap.add_argument("--r1600", default="/mnt/c/carc-shared/track_d2r2_prep/d2r2_rung1600")
    ap.add_argument("--out-md", default=str(PAIR_DIR / "READOUT_D2R2.md"))
    ap.add_argument("--out-json", default=str(PAIR_DIR / "READOUT_D2R2.json"))
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
        "run_id": "track_d2r2_prep", "band": BAND,
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
        print(f"[analyze_d2r2] wrote {args.out_md}")
        print(f"[analyze_d2r2] wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
