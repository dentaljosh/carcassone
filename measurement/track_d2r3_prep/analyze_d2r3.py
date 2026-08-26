#!/usr/bin/env python3
"""D2-R3 RUNG-COMPRESSION CELL (cost-calibration successor) — THE ADJUDICATOR.

⛔ PROVENANCE OF THIS FILE — read before trusting a single line of it.

This adjudicator is a **port of `../track_d2r2_prep/analyze_d2r2.py`**, which was
itself a mechanical port of the blind original (`../track_d2_prep/analyze_d2.py`).
The port is legitimate because `READ_RULE.md` §1, §2, §5 and §6 of THIS pair, and
the FIVE BRANCH BLOCKS of §4, are carried verbatim from the predecessor (this
pair's §0 banner enumerates the exhaustive change list; `--selftest` MECHANICALLY
re-checks the §4 claim with a `diff` and FAILS if a branch condition moved).
Every branch condition, the first-match-wins ordering, `Z_BAR`, `S_COARSE_PTS`,
`SE_COMMITTED` and the `D2-COMPRESSED`-reachability note are therefore
byte-identical to the blind original.

WHAT THIS PORT CHANGED vs `analyze_d2r2.py`, EXHAUSTIVELY
=========================================================
 1. run id / pair dir      `track_d2r2_prep` -> `track_d2r3_prep`; outputs
                           `READOUT_D2R3.{md,json}`.
 2. `BAND`                 144000000000 -> 149000000000 — **and it is no longer
                           typed here at all**: it is IMPORTED from `d2r3_lib`,
                           which is the pair's single machine-readable copy of
                           every bar (READ_RULE §3.2: "neither carries its own
                           arithmetic or its own thresholds").
 3. THRESHOLD OWNERSHIP    `TIMING_LO/HI`, `TIMING_FULL_LO/HI`, `N_DECKS`,
                           `N_BURNIN_DECKS`, `SEATINGS_PER_DECK`,
                           `TENANCY_CONFIRM_SAMPLES`, `FOREIGN_TOTAL_CPU_PCT`
                           are IMPORTED from `d2r3_lib`, never re-typed. The
                           predecessor's local `TIMING_BAND = (0.85, 1.20)`
                           tuple is GONE. `--selftest` asserts object identity
                           with `d2r3_lib`'s, so a second copy cannot creep back.
 4. THREE NEW GATES        `G-PROBE`, `G-TIMING-FULL`, `G-TENANCY` (READ_RULE §3).
                           Nine gates -> TWELVE.
 5. `G-TIMING` REWRITTEN   It no longer reads `summary.json`'s whole-cell ratio.
                           It is now the **BURN-IN WINDOW** gate of READ_RULE
                           §3.2: `d2r3_lib.read_burnin(cell_r800)` +
                           `d2r3_lib.verdict(..., TIMING_LO, TIMING_HI)`, with
                           `complete` REQUIRED, **plus a cross-check against the
                           live watcher's own `BURNIN_R800.json`** — the same
                           code over the same records, so a disagreement means
                           the records moved and is itself a FAIL.
 6. `G-SINGLEVAR` REWRITTEN, ALIAS-AWARE (READ_RULE §3.3). The predecessor's
                           `is_rung_sims_mirror()` heuristic + `BOOKKEEPING_LEAVES`
                           + `CELL_TOKENS` exemptions are GONE. The gate now
                           requires the literal key-set diff to be EXACTLY
                           `{rung.sims, opponent.sims, opponent.label}` and adds
                           the §3.3 CROSS-CHECK (`opponent.sims == rung.sims`,
                           `opponent.label == "HeuristicMCTS(h"+rung.sims+")"`)
                           inside each cell. BOTH readings are printed.
 7. `G-N` gained the `champ_timeouts == 0` clause (READ_RULE §3.4), read from
                           `summary.json` AND re-summed from the records.
 8. §4.1 SUPPRESSION       On a burn-in-aborted / short pair (`n_common` short of
                           the pre-registered 200 decks, or no R1600 cell at all)
                           **no `S` is computed** and the readout says so
                           explicitly instead of printing a one-cell number.
 9. `--smoke-mode`         NEW. The launcher's smoke leg ends by running this
                           adjudicator against the 16-game smoke archive and
                           requires it to fail ONLY on the gates a smoke archive
                           cannot satisfy by construction (`SMOKE_ALLOWED_FAILURES`).
                           The h2h standing rule (`../h2h_22016_prep/AMENDMENTS.md`).
10. `--selftest`           NEW, and it is the point of this file. The passing
                           fixture is **SEEDED FROM A REAL manifest.json +
                           summary.json read off disk**, never synthesized from
                           READ_RULE's prose — the h2h post-mortem's "20/20 green
                           selftest certified an instrument that could not read
                           any real archive". Refuses to run at all if no real
                           manifest is reachable.
11. CLI                    `--cell-r800/--cell-r1600/--out-root/--prep-dir/
                           --json/--md`, replacing `--r800/--r1600/--out-md/
                           --out-json`.
12. `diagnose()`           re-datafied for the twelve gates; the predecessor's
                           attempt-2-specific G-TIMING prose is GONE (it named
                           attempt 2's pilot-vs-cell numbers; those are COST
                           figures and are quoted only where READ_RULE §0 item 3
                           licenses them, i.e. nowhere in a gate).
13. CO-TENANCY            the predecessor's hand-written `CARCASUM_DISCLOSURE`
                           and hand-written `COST_REALIZED` block are GONE. Both
                           are now MEASURED: tenancy from the sampler's JSONL via
                           `d2r3_lib.tenancy_summary`, cost from the records'
                           own `elapsed_s` (§4.3 item 8).

⛔ **STATISTICS PROVENANCE OF THIS FILE.** No number from attempts 1 or 2's cells
appears anywhere below — no `S`, no `z_S`, no elo, no margin, no winrate.
READ_RULE §5: "No branch adjudicates, quotes, or carries any statistic from
attempts 1 or 2." The only attempt-2 artifact this file touches is the
`--selftest` fixture SEED, and it takes the seed summary's KEY SET only (every
outcome value is overwritten with a fixture-computed one before any gate sees it
— see `_fixture_summary`).

What it implements, section by section, from `READ_RULE.md`:

  §1   `S = M_R800 − M_R1600`, deck-paired over `n_common`; `se(S)` from the
       REALIZED paired per-deck differences; `z_S` via the
       `eval_fair_puct._paired_z` convention (IMPORTED, not re-derived) — plus
       the §1 WITNESS: an independent from-scratch recomputation straight off the
       raw per-game records, printed beside the analyzer's value. Disagreement
       beyond fp tolerance ⇒ `U-UNREADABLE`. Suppressed entirely under §4.1.
  §3   the TWELVE gates, each read at the manifest top level and then at
       `config.*` and then at the emitter's `config` sub-dict containers,
       reporting WHICH address resolved. ABSENT is FAIL, never a silent skip.
  §4   the five branches, in order, first-match-wins, with the
       dispersion-conditional COARSE/COMPRESSED boundary note honored.
  §4.3 the full companion table, all EIGHT items.
  §6   the stated prior, reprinted.

Usage:
    analyze_d2r3.py --cell-r800 DIR --cell-r1600 DIR --out-root DIR [--json X] [--md Y]
    analyze_d2r3.py --smoke-mode --cell-r800 DIR
    analyze_d2r3.py --selftest [--fixture-manifest DIR]
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PAIR_DIR = HERE

# `_paired_z` is IMPORTED, never re-implemented: READ_RULE §1 names
# `eval_fair_puct._paired_z` as THE convention for `z_S`. Same import convention
# as the predecessor `analyze_d2r2.py`.
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
from eval_fair_puct import _paired_z  # noqa: E402

# The pair's ONE copy of every timing/tenancy constant and of the burn-in
# arithmetic. READ_RULE §3.2: the live gate and the post-hoc gate are the SAME
# CODE. Nothing below re-types any of these.
sys.path.insert(0, str(HERE))
import d2r3_lib  # noqa: E402
from d2r3_lib import (  # noqa: E402
    BAND,
    FOREIGN_TOTAL_CPU_PCT,
    N_BURNIN_DECKS,
    N_DECKS,
    SEATINGS_PER_DECK,
    TENANCY_CONFIRM_SAMPLES,
    TIMING_FULL_HI,
    TIMING_FULL_LO,
    TIMING_HI,
    TIMING_LO,
    burnin_seeds,
    read_burnin,
    read_full_cell,
    read_tenancy_jsonl,
    tenancy_summary,
    verdict,
)

# --------------------------------------------------------------------------- #
# CONSTANTS — every one is lifted from the FROZEN pair, not chosen here.        #
# Anything that ALSO lives in `d2r3_lib.py` is imported above and NOT retyped.   #
# --------------------------------------------------------------------------- #
N_GAMES_REQUIRED = N_DECKS * SEATINGS_PER_DECK   # READ_RULE §3 G-N: 400 per cell
N_COMMON_REQUIRED = N_DECKS                      # READ_RULE §3 G-BAND: 200 decks

CAND_LEAF_HASH = "a36d2e15a3b3d71d"      # READ_RULE §3 G-LEAF
RUNG_C = 3.0                             # READ_RULE §3 G-RUNG
RUNG_AGENT = "HeuristicMCTS"             # READ_RULE §3 G-RUNG
RUNG_SIMS = {"R800": 800, "R1600": 1600}  # READ_RULE §3 G-RUNG
RULES_PROFILE = "fixed_v1"               # READ_RULE §3 G-RULES

# READ_RULE §3 G-PROBE — the probe budget, FROZEN by the blind commit (§3.2's
# NO-RE-PICK clause). `k_dets × sims_per_det == total_sims` is checked as an
# identity, not assumed.
PROBE_K_DETS = 4
PROBE_SIMS_PER_DET = 1600
PROBE_TOTAL_SIMS = 6400
PROBE_C_PUCT = 1.5
PROBE_EXACT_K = 2
PROBE_BACKEND = "rust"

SAT_BAND = (0.50, 0.90)                  # READ_RULE §3 G-SAT (CELL R800)
FAILURE_RATE_FLOOR = 0.02                # READ_RULE §3 / §3.1: "<=2%" precedent
SE_COMMITTED = 1.25                      # DESIGN §4.2 pre-registered se(S), pts
S_COARSE_PTS = 2.5                       # READ_RULE §4 D2-COARSE threshold, pts
Z_BAR = 2.0                              # READ_RULE §4 branch bar
ELO_PER_PT_PREREG = 15.6                 # DESIGN §4.3 pre-registered scale anchor
WITNESS_RTOL = 1e-9                      # READ_RULE §1 "floating-point tolerance"
WITNESS_ATOL = 1e-9
FULL_XCHECK_RTOL = 1e-6                  # READ_RULE §3 G-TIMING-FULL: "1e-6 relative"

GATE_IDS = (
    "G-BAND", "G-SINGLEVAR", "G-PROBE", "G-RUNG", "G-LEAF", "G-RULES",
    "G-TOOL", "G-N", "G-TIMING", "G-TIMING-FULL", "G-TENANCY", "G-SAT",
)

# --------------------------------------------------------------------------- #
# SMOKE MODE — the h2h standing rule (`../h2h_22016_prep/AMENDMENTS.md`):        #
#   "the launcher's smoke step must end by running the cell's own adjudicator    #
#    against the smoke archive, and must require it to fail *only* on band/N     #
#    gates."                                                                    #
#                                                                               #
# PINNED HERE, EXPLICITLY, so the allowed-failure set is auditable and cannot    #
# quietly widen. A 16-game throwaway archive on a DISJOINT seed range cannot     #
# satisfy these BY CONSTRUCTION — the reason is spelled out per gate:            #
# --------------------------------------------------------------------------- #
SMOKE_ALLOWED_FAILURES: dict[str, str] = {
    "G-BAND": "the smoke leg runs on the DISJOINT smoke range (149999999000..007), "
              "never the claimed band, and has 8 decks not 200.",
    "G-N": "a smoke is --n 16, not 400.",
    "G-SINGLEVAR": "the LITERAL key-set half needs TWO cells; a smoke has one. "
                   "⚠️ the ALIAS CROSS-CHECK half is single-cell checkable and is "
                   "enforced separately as `G-SINGLEVAR/alias`, which is NOT "
                   "allowed to fail.",
    "G-TIMING": "the burn-in window is 80 games at seeds BAND+0..39; a smoke on a "
                "disjoint range has none of them, so the window is incomplete and "
                "fail-closed. A smoke also runs at unsaturated W, which is the very "
                "regime READ_RULE §3.2 says cannot predict this ratio.",
    "G-TIMING-FULL": "the from-records cross-check reads the 200-deck band window, "
                     "which a smoke archive does not populate.",
    "G-TENANCY": "no `TENANCY_R800.jsonl` sampler log is written for a smoke leg.",
    "G-SAT": "a 16-game winrate is a property of the DATA (READ_RULE §3.1 says so "
             "explicitly for this gate) at a sample size that cannot establish a "
             "saturation property; a smoke must not be able to block a launch on a "
             "coin-flip. ⚠️ This assignment is THIS FILE's call — the brief's "
             "allowed family named band/N/paired-cell/timing/tenancy and left "
             "`G-SAT` unassigned; it is recorded here rather than left implicit.",
}
SMOKE_BLOCKING_GATES = tuple(g for g in GATE_IDS if g not in SMOKE_ALLOWED_FAILURES) + (
    "G-SINGLEVAR/alias",
)

# --------------------------------------------------------------------------- #
# DESIGN §1 prior table — reprinted verbatim by §4.3 item 7.                     #
# (Carried VERBATIM from the predecessor: these are the two PRIOR readings this  #
#  cell adjudicates BETWEEN, published 2026-06-18/19, and READ_RULE §6 reprints  #
#  them. They are not attempt-1/attempt-2 statistics.)                           #
# --------------------------------------------------------------------------- #
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

# READ_RULE §4 branch texts, VERBATIM, so the readout never paraphrases the pair.
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
    "(READ_RULE §4 boundary note).")

NO_S_SENTENCE = (
    "⛔ **NO `S` EXISTS FOR THIS RUN, AND NONE IS PRINTED.** READ_RULE §4.1: on a burn-in-aborted "
    "or short pair there is no second cell to difference against, so `S` is not computed at all — "
    "\"the readout must say that rather than printing a one-cell number that a later reader could "
    "mistake for one.\" The per-cell deck-paired margins below are each cell's OWN §4.3 item-1 "
    "statistic and are NOT `S`, NOT a spacing, and NOT adjudicated. Reason: {reason}")


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
    """One cell archive. Absent files are recorded, never invented — ABSENT is FAIL
    at the gate, so a missing `summary.json` becomes `{}` here and fails loudly
    there rather than raising and hiding the other eleven gates' readings."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = Path(path)
        self.manifest_present = (self.path / "manifest.json").is_file()
        self.summary_present = (self.path / "summary.json").is_file()
        self.manifest = (json.loads((self.path / "manifest.json").read_text())
                         if self.manifest_present else {})
        self.summary = (json.loads((self.path / "summary.json").read_text())
                        if self.summary_present else {})
        self.records: list[dict] = []
        if self.path.is_dir():
            for p in sorted(self.path.glob("seed*_a*.json")):
                if p.name.startswith("."):        # `.…partial.json` writer temporaries
                    continue
                try:
                    self.records.append(json.loads(p.read_text()))
                except Exception:                 # noqa: BLE001 — recorded, never skipped
                    self.records.append({"unparseable": p.name})
        self.failure_records: list[dict] = []
        fdir = self.path / "failed"
        if fdir.is_dir():
            for p in sorted(fdir.glob("*.json")):
                try:
                    self.failure_records.append(json.loads(p.read_text()))
                except Exception:                 # noqa: BLE001
                    self.failure_records.append({"unparseable": str(p.name)})

    # ---- per-deck view -------------------------------------------------- #
    def scored(self) -> list[dict]:
        return [r for r in self.records if "seed" in r and "diff" in r]

    def by_deck(self) -> dict[int, dict[int, float]]:
        out: dict[int, dict[int, float]] = {}
        for r in self.scored():
            out.setdefault(int(r["seed"]), {})[int(r["a_seat"])] = float(r["diff"])
        return out

    def complete_decks(self) -> set[int]:
        return {s for s, v in self.by_deck().items() if 0 in v and 1 in v}

    def shim(self, decks: set[int] | None = None) -> list[Rec]:
        return [Rec(int(r["seed"]), int(r["a_seat"]), float(r["diff"]))
                for r in self.scored()
                if decks is None or int(r["seed"]) in decks]


# --------------------------------------------------------------------------- #
# ADDRESS RESOLUTION — READ_RULE §3: "read at the manifest top level, then at     #
# `config.*`, then — for the witnesses the emitter files inside `config` sub-     #
# dicts — at those containers, and the adjudicator reports which address           #
# resolved (the house `G-BAND`/`G-J1` fix precedent)."                            #
#                                                                               #
# ⚠️ VERIFIED AGAINST A REAL EMITTED MANIFEST, not against a design document      #
# (the h2h `G-TIEARB` lesson). The container list below is exactly where the      #
# `eval_fair_puct` emitter actually files this pair's twelve gates' witnesses:    #
#   config.backend.*  -> carc_rs_version, tile_data_semantic_digest, name        #
#   config.champion.* -> k_dets, sims_per_det, total_sims, c_puct, tiearb_*      #
#   config.endgame.*  -> exact_k                                                 #
#   config.stamps.*   -> BLIND_COMMIT                                            #
#   config.rung.*     -> c, agent, sims, leaf_hash                               #
#   config.opponent.* -> sims, label                                             #
#   config.env.*      -> canonical env echo                                      #
# --------------------------------------------------------------------------- #
FALLBACK_CONTAINERS = ("config.backend", "config.champion", "config.endgame",
                       "config.stamps", "config.env", "config.rung",
                       "config.opponent", "evaluator")
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
    for nm in names:                           # 3. emitter container fallbacks
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


# --------------------------------------------------------------------------- #
# §1 — THE STATISTIC (analyzer path) and THE WITNESS (from-scratch path)         #
# --------------------------------------------------------------------------- #
def paired(records: list[Rec]) -> tuple[float | None, float | None, float | None, int]:
    """`(mean, se, z, n_decks)` on `_paired_z`'s own convention.

    The pair `(mean, z)` is taken STRAIGHT from the imported `_paired_z` so the
    convention cannot drift; `se` is recomputed from the same per-deck
    construction that function uses.
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
        if not Path(d).is_dir():
            return got
        for p in sorted(Path(d).iterdir()):
            if not p.name.startswith("seed") or p.suffix != ".json":
                continue
            try:
                rec = json.loads(p.read_text())
            except Exception:                     # noqa: BLE001
                continue
            if "seed" not in rec or "diff" not in rec:
                continue
            got[(int(rec["seed"]), int(rec["a_seat"]))] = float(rec["diff"])
        return got

    a, b = load(dir800), load(dir1600)
    decks = sorted({s for (s, _seat) in a if (s, 0) in a and (s, 1) in a
                    and (s, 0) in b and (s, 1) in b})
    m800 = [(a[(s, 0)] + a[(s, 1)]) / 2.0 for s in decks]
    m1600 = [(b[(s, 0)] + b[(s, 1)]) / 2.0 for s in decks]
    delta = [x - y for x, y in zip(m800, m1600)]

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
    return {"n_common": len(delta), "S": S, "se_S": seS, "z_S": zS,
            "M_R800": M8, "se_M_R800": se8, "z_M_R800": z8,
            "M_R1600": M16, "se_M_R1600": se16, "z_M_R1600": z16}


def close(a, b) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=WITNESS_RTOL, abs_tol=WITNESS_ATOL)


# --------------------------------------------------------------------------- #
# §3 — THE GATES                                                                #
# --------------------------------------------------------------------------- #
def gate(gid: str, prop: str, ok: bool, realized: str, addresses: str, **extra) -> dict:
    g = {"id": gid, "proposition": prop, "status": "PASS" if ok else "FAIL",
         "realized": realized, "address": addresses}
    g.update(extra)
    return g


# --- G-SINGLEVAR ----------------------------------------------------------- #
# READ_RULE §3.3, verified against a real emitted manifest pair on 2026-08-25:
# the emitter's config-block diff between two healthy cells of this launcher is
# EXACTLY these three keys and nothing else. So the gate is written literally —
# no bookkeeping exemption list, no heuristic mirror detector.
SINGLEVAR_EXPECTED_DIFF = frozenset({"rung.sims", "opponent.sims", "opponent.label"})
SINGLEVAR_MIRRORS = {
    "opponent.sims": "eval_fair_puct.py:4395 — `args.rung_sims if args.opponent == \"h800\" else None`",
    "opponent.label": "eval_fair_puct.py:_opp_label, 1532-1535 — `f\"HeuristicMCTS(h{args.rung_sims})\"`",
}


def opp_label_for(rung_sims) -> str:
    """The emitter's own rendering (`_opp_label`), reproduced for the cross-check."""
    return f"HeuristicMCTS(h{rung_sims})"


def singlevar_alias_crosscheck(manifest: dict) -> dict:
    """READ_RULE §3.3 half (b): WITHIN one cell, both mirrors must be consistent
    with `rung.sims`. Single-cell checkable — which is why the smoke leg enforces
    it even though the literal key-set half needs two cells."""
    rs, rs_addr = resolve(manifest, "config.rung.sims")
    os_, os_addr = resolve(manifest, "config.opponent.sims")
    ol, ol_addr = resolve(manifest, "config.opponent.label")
    sims_ok = (rs is not MISSING and os_ is not MISSING and int(os_) == int(rs))
    label_ok = (rs is not MISSING and ol is not MISSING
                and str(ol) == opp_label_for(int(rs)))
    return {
        "rung_sims": fmt_val(rs), "opponent_sims": fmt_val(os_), "opponent_label": fmt_val(ol),
        "expected_label": opp_label_for(int(rs)) if rs is not MISSING else "n/a",
        "sims_mirror_consistent": sims_ok, "label_mirror_consistent": label_ok,
        "ok": bool(sims_ok and label_ok),
        "addresses": f"{rs_addr or 'ABSENT'} / {os_addr or 'ABSENT'} / {ol_addr or 'ABSENT'}",
    }


def gate_singlevar(c800: Cell, c1600: Cell | None) -> dict:
    cross = {"R800": singlevar_alias_crosscheck(c800.manifest)}
    if c1600 is not None:
        cross["R1600"] = singlevar_alias_crosscheck(c1600.manifest)
    alias_ok = all(v["ok"] for v in cross.values())

    if c1600 is None:
        literal_ok = False
        diff_keys: list[str] = []
        literal_txt = ("LITERAL key-set diff: NOT COMPUTABLE — only one cell present "
                       "(single-cell / smoke archive). ABSENT is FAIL.")
    else:
        fa = flatten(c800.manifest.get("config", {}))
        fb = flatten(c1600.manifest.get("config", {}))
        diff_keys = sorted(k for k in set(fa) | set(fb)
                           if fa.get(k, MISSING) is MISSING
                           or fb.get(k, MISSING) is MISSING
                           or fa[k] != fb[k])
        literal_ok = (set(diff_keys) == set(SINGLEVAR_EXPECTED_DIFF))
        shown = ", ".join(
            f"{k} ({fmt_val(fa.get(k, MISSING))} vs {fmt_val(fb.get(k, MISSING))})"
            for k in diff_keys) or "NOTHING"
        extra = sorted(set(diff_keys) - SINGLEVAR_EXPECTED_DIFF)
        absent = sorted(SINGLEVAR_EXPECTED_DIFF - set(diff_keys))
        literal_txt = f"LITERAL key-set diff = {{{shown}}}"
        if extra:
            literal_txt += f"  ⛔ FOURTH+ DIFFERING KEY(S): {', '.join(extra)}"
        if absent:
            literal_txt += f"  ⛔ EXPECTED-BUT-IDENTICAL: {', '.join(absent)}"

    alias_txt = "ALIAS-AWARE reading (§3.3): " + "; ".join(
        f"{nm}: rung.sims={v['rung_sims']}, opponent.sims={v['opponent_sims']} "
        f"(consistent={v['sims_mirror_consistent']}), opponent.label={v['opponent_label']} "
        f"vs expected {v['expected_label']} (consistent={v['label_mirror_consistent']})"
        for nm, v in cross.items())
    mirror_txt = ("MIRROR SOURCES (named before game 1, READ_RULE §3.3): "
                  + "; ".join(f"{k} <- {v}" for k, v in SINGLEVARS_SORTED()))
    ok = bool(literal_ok and alias_ok)
    return gate(
        "G-SINGLEVAR",
        "the two cells' config blocks differ in EXACTLY {rung.sims, opponent.sims, "
        "opponent.label} — the one experimental variable plus its two named emitter "
        "mirrors — AND in each cell opponent.sims == rung.sims and "
        "opponent.label == \"HeuristicMCTS(h\"+str(rung.sims)+\")\"",
        ok,
        literal_txt + "  |  " + alias_txt + "  |  " + mirror_txt,
        "config.* (deep flatten, both manifests) + config.rung.sims / config.opponent.{sims,label}",
        literal_diff_keys=diff_keys,
        literal_reading_status="PASS" if literal_ok else "FAIL",
        alias_crosscheck=cross,
        alias_reading_status="PASS" if alias_ok else "FAIL",
    )


def SINGLEVARS_SORTED():
    return sorted(SINGLEVAR_MIRRORS.items())


def gate_probe(cells) -> dict:
    """READ_RULE §3 G-PROBE. ⚠️ Every address below was VERIFIED against a real
    emitted `eval_fair_puct` manifest — `config.champion.{k_dets,sims_per_det,
    total_sims,c_puct}`, `config.endgame.exact_k`, `config.backend.name`, and the
    two tie-arbiter addresses `config.champion.tiearb_enabled` /
    `config.cand_tiearb.enabled`. That is the h2h `G-TIEARB` lesson applied."""
    parts, addrs, ok = [], [], True
    for nm, c in cells:
        kv, ka = resolve(c.manifest, "config.champion.k_dets")
        sv, sa = resolve(c.manifest, "config.champion.sims_per_det")
        tv, ta = resolve(c.manifest, "config.champion.total_sims")
        pv, pa = resolve(c.manifest, "config.champion.c_puct")
        ev, ea = resolve(c.manifest, "config.endgame.exact_k")
        bv, ba = resolve(c.manifest, "config.backend.name", aliases=("backend",))
        for got, want in ((kv, PROBE_K_DETS), (sv, PROBE_SIMS_PER_DET),
                          (tv, PROBE_TOTAL_SIMS), (ev, PROBE_EXACT_K)):
            if got is MISSING or int(got) != want:
                ok = False
        if pv is MISSING or float(pv) != PROBE_C_PUCT:
            ok = False
        backend_name = bv.get("name") if isinstance(bv, dict) else bv
        if backend_name is MISSING or str(backend_name) != PROBE_BACKEND:
            ok = False
        product_ok = (kv is not MISSING and sv is not MISSING and tv is not MISSING
                      and int(kv) * int(sv) == int(tv))
        if not product_ok:
            ok = False
        # tie-arbiter: ABSENT-or-DISARMED at either documented address, and NO
        # stray armed `tiearb`-named key anywhere (the h2h stray scan).
        ta_en, ta_addr = resolve(c.manifest, "config.champion.tiearb_enabled")
        ct_en, ct_addr = resolve(c.manifest, "config.cand_tiearb.enabled")
        arb_ok = (ta_en in (MISSING, False, None)) and (ct_en in (MISSING, False, None))
        stray = sorted({k for k in flatten(c.manifest)
                        if "tiearb" in k.lower() and k.endswith("enabled")
                        and flatten(c.manifest)[k] is True})
        if not arb_ok or stray:
            ok = False
        parts.append(
            f"{nm}: k_dets={fmt_val(kv)} sims_per_det={fmt_val(sv)} total_sims={fmt_val(tv)} "
            f"(product identity {fmt_val(kv)}×{fmt_val(sv)}=={fmt_val(tv)}: {product_ok}); "
            f"c_puct={fmt_val(pv)}; exact_k={fmt_val(ev)}; backend={fmt_val(backend_name)}; "
            f"cand tie-arbiter champion.tiearb_enabled={fmt_val(ta_en)} / "
            f"cand_tiearb.enabled={fmt_val(ct_en)} (absent-or-disarmed={arb_ok}); "
            f"stray ARMED tiearb keys={stray or 'none'}")
        addrs.append(f"{nm}:{ka or 'ABSENT'}/{sa or 'ABSENT'}/{ta or 'ABSENT'}/"
                     f"{pa or 'ABSENT'}/{ea or 'ABSENT'}/{ba or 'ABSENT'}/"
                     f"{ta_addr or 'ABSENT'}+{ct_addr or 'ABSENT'}")
    # identity ACROSS cells
    if len(cells) == 2:
        for key in ("config.champion.k_dets", "config.champion.sims_per_det",
                    "config.champion.total_sims", "config.champion.c_puct",
                    "config.endgame.exact_k"):
            a = resolve(cells[0][1].manifest, key)[0]
            b = resolve(cells[1][1].manifest, key)[0]
            if a is MISSING or a != b:
                ok = False
                parts.append(f"⛔ {key} differs across cells: {fmt_val(a)} vs {fmt_val(b)}")
    return gate(
        "G-PROBE",
        f"both cells, identically: config.champion.k_dets == {PROBE_K_DETS}, "
        f"sims_per_det == {PROBE_SIMS_PER_DET}, total_sims == {PROBE_TOTAL_SIMS} "
        f"(and k_dets × sims_per_det == total_sims); c_puct == {PROBE_C_PUCT}; "
        f"exact_k == {PROBE_EXACT_K}; backend {PROBE_BACKEND}; candidate tie-arbiter "
        "absent or disarmed",
        ok, "; ".join(parts), ", ".join(addrs))


def gate_timing(cell_r800: Cell, out_root: Path) -> dict:
    """READ_RULE §3 G-TIMING / §3.2 — the BURN-IN WINDOW gate.

    The arithmetic and the bar are `d2r3_lib`'s; this function contains neither.
    It additionally cross-checks the LIVE watcher's own `BURNIN_R800.json`: the
    same code over the same records, so a disagreement means the records moved
    between the two readings, and READ_RULE §3.1 says that "would itself be the
    finding" — it is reported LOUDLY and it FAILS.
    """
    reading = read_burnin(cell_r800.path)
    v = verdict(reading, TIMING_LO, TIMING_HI)          # require_complete=True
    seeds = burnin_seeds()
    live_path = Path(out_root) / "BURNIN_R800.json"
    live = None
    if live_path.is_file():
        try:
            live = json.loads(live_path.read_text())
        except Exception:                                # noqa: BLE001
            live = {"unparseable": True}
    agree_fields = ("ratio", "champ_prefix_ms_per_move", "rung_ms_per_move",
                    "complete", "pass", "n_games")
    if live is None:
        agreement = {"present": False}
        agree_ok = False
        agree_txt = (f"⛔ the live watcher's `{live_path.name}` is ABSENT from --out-root "
                     "— ABSENT is FAIL (READ_RULE §3); the live gate and the post-hoc "
                     "gate must be the same reading and there is nothing to compare to.")
    else:
        agreement = {"present": True, "fields": {}}
        agree_ok = True
        for k in agree_fields:
            mine, theirs = v.get(k), live.get(k)
            same = (close(mine, theirs) if isinstance(mine, float) or isinstance(theirs, float)
                    else mine == theirs)
            agreement["fields"][k] = {"post_hoc": mine, "live": theirs, "agree": bool(same)}
            if not same:
                agree_ok = False
        agree_txt = ("live watcher BURNIN_R800.json AGREES with the post-hoc recomputation "
                     "on " + ", ".join(agree_fields)
                     if agree_ok else
                     "⛔⛔ LIVE/POST-HOC DISAGREEMENT — " + "; ".join(
                         f"{k}: live={agreement['fields'][k]['live']!r} vs "
                         f"post-hoc={agreement['fields'][k]['post_hoc']!r}"
                         for k in agree_fields if not agreement["fields"][k]["agree"])
                     + ". These are the SAME CODE over the SAME RECORDS (READ_RULE §3.2), "
                       "so a disagreement means THE RECORDS MOVED between the two readings. "
                       "That is itself the finding, and it FAILS this gate.")
    ok = bool(v["pass"] and agree_ok)
    realized = (
        f"burn-in window seeds {seeds[0]}..{seeds[-1]} × {SEATINGS_PER_DECK} seatings "
        f"= {N_BURNIN_DECKS * SEATINGS_PER_DECK} games; on disk {v['n_games']} "
        f"(complete={v['complete']}, missing={v['n_missing']}, malformed={v['n_malformed']}); "
        f"champ_prefix_ms_per_move={fmt_val(v['champ_prefix_ms_per_move'])} "
        f"rung_ms_per_move={fmt_val(v['rung_ms_per_move'])} "
        f"ratio={fmt_val(v['ratio'])} vs bar [{TIMING_LO}, {TIMING_HI}] -> "
        f"in-bar={v['pass']}. " + agree_txt)
    return gate(
        "G-TIMING",
        f"CELL R800's BURN-IN WINDOW (decks BAND+0..BAND+{N_BURNIN_DECKS - 1}, both "
        f"seatings, {N_BURNIN_DECKS * SEATINGS_PER_DECK} games), recomputed by "
        f"d2r3_lib.read_burnin, is COMPLETE and its realized ratio is inside "
        f"[{TIMING_LO}, {TIMING_HI}]",
        ok, realized,
        f"per-game RECORDS in {cell_r800.path} (d2r3_lib.read_burnin) + "
        f"{live_path} (live watcher)",
        burnin=v, live_agreement=agreement)


def gate_timing_full(cell_r800: Cell) -> dict:
    """READ_RULE §3 G-TIMING-FULL — the whole-cell DRIFT envelope, taken from
    `summary.json` AND cross-checked against `d2r3_lib.read_full_cell` to 1e-6
    relative."""
    cm = cell_r800.summary.get("champ_prefix_ms_per_move")
    rm = cell_r800.summary.get("rung_ms_per_move")
    summary_ratio = (cm / rm) if (cm not in (None, 0) and rm not in (None, 0)) else None
    rec = read_full_cell(cell_r800.path)
    rec_ratio = rec.ratio
    in_bar = summary_ratio is not None and TIMING_FULL_LO <= summary_ratio <= TIMING_FULL_HI
    if summary_ratio is None or rec_ratio is None:
        xcheck_ok = False
        xtxt = "⛔ one of the two computations produced NO ratio — ABSENT is FAIL."
    else:
        rel = abs(summary_ratio - rec_ratio) / abs(rec_ratio)
        xcheck_ok = rel <= FULL_XCHECK_RTOL
        xtxt = (f"summary-vs-from-records relative difference {rel:.3e} "
                f"(tolerance {FULL_XCHECK_RTOL:g}) -> agree={xcheck_ok}")
    ok = bool(in_bar and xcheck_ok)
    realized = (
        f"summary.json champ_prefix_ms_per_move={fmt_val(cm)} (the CANDIDATE side — the "
        f"field-name trap, READ_RULE §2) / rung_ms_per_move={fmt_val(rm)} -> ratio="
        f"{fmt_val(summary_ratio)}; d2r3_lib.read_full_cell over {rec.n_games} records "
        f"({rec.n_decks} decks, complete={rec.complete}) -> ratio={fmt_val(rec_ratio)}; "
        f"{xtxt}; bar [{TIMING_FULL_LO}, {TIMING_FULL_HI}] -> in-bar={in_bar}")
    return gate(
        "G-TIMING-FULL",
        f"CELL R800's whole-cell ratio, from summary.json and cross-checked against a "
        f"from-records recomputation agreeing to {FULL_XCHECK_RTOL:g} relative, is inside "
        f"[{TIMING_FULL_LO}, {TIMING_FULL_HI}]",
        ok, realized,
        "summary.json (CELL R800) + per-game RECORDS (d2r3_lib.read_full_cell)",
        summary_ratio=summary_ratio, records_ratio=rec_ratio,
        records_reading=rec.as_dict(), xcheck_ok=xcheck_ok, in_bar=in_bar)


def read_tenancy(out_root: Path, cell: str) -> tuple[Path, list[dict], dict]:
    p = Path(out_root) / f"TENANCY_{cell}.jsonl"
    samples = read_tenancy_jsonl(p)
    return p, samples, tenancy_summary(samples)


def gate_tenancy(out_root: Path) -> dict:
    """READ_RULE §3 G-TENANCY — CELL R800 only (§3.4 scopes it), from the
    sampler's JSONL via `d2r3_lib`. An ABSENT or EMPTY log is FAIL: "an absent or
    truncated sampler log" is named in the gate's own VOIDS-on column."""
    path, samples, roll = read_tenancy(out_root, "R800")
    present = path.is_file()
    ok = bool(present and samples and roll["exclusive"])
    realized = (
        f"log {path} present={present}, n_samples={roll['n_samples']}; "
        f"max_foreign_total_cpu_pct={roll['max_foreign_total_cpu_pct']} "
        f"(bar {FOREIGN_TOTAL_CPU_PCT}); max consecutive over-bar samples="
        f"{roll['max_consecutive_breach_samples']} (confirm threshold "
        f"{TENANCY_CONFIRM_SAMPLES}); exclusive={roll['exclusive']}; "
        f"top foreign by peak CPU: "
        + (", ".join(f"{t['cmd'][:60]}@{t['peak_cpu_pct']}%"
                     for t in roll["top_foreign_by_cpu"]) or "none"))
    if not present:
        realized = f"⛔ sampler log {path} ABSENT — ABSENT is FAIL (READ_RULE §3). " + realized
    elif not samples:
        realized = f"⛔ sampler log {path} is EMPTY/truncated — FAIL. " + realized
    return gate(
        "G-TENANCY",
        f"CELL R800's tenancy sampler ran for the cell's whole window, and no "
        f"{TENANCY_CONFIRM_SAMPLES} consecutive samples show foreign CPU >= "
        f"{FOREIGN_TOTAL_CPU_PCT}% of one core",
        ok, realized, str(path), rollup=roll)


def run_gates(c800: Cell, c1600: Cell | None, common: set[int],
              out_root: Path, blind_expected: str | None,
              smoke: bool = False) -> list[dict]:
    """All TWELVE gates, fail-closed, ABSENT is FAIL, address reported on each.

    `c1600 is None` is the SMOKE / burn-in-abort shape: every two-cell conjunct
    becomes a FAIL (never a silent skip), and the readout says which.
    """
    G: list[dict] = []
    cells = [("R800", c800)] + ([("R1600", c1600)] if c1600 is not None else [])

    # ---- G-BAND ---------------------------------------------------------- #
    parts, addrs, ok = [], [], True
    for nm, c in cells:
        v, addr = resolve(c.manifest, "seed_start", aliases=("band_seed_start",))
        addrs.append(f"{nm}:{addr or 'ABSENT'}")
        parts.append(f"{nm} seed_start={fmt_val(v)}")
        if v is MISSING or int(v) != BAND:
            ok = False
    d8 = c800.complete_decks()
    d16 = c1600.complete_decks() if c1600 is not None else None
    if d16 is None:
        parts.append("record-derived deck sets agree=N/A — only ONE cell present "
                     "(single-cell / smoke / burn-in-abort archive); ABSENT is FAIL")
        parts.append(f"|R800|={len(d8)}; n_common={len(common)}")
        ok = False
    else:
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
    G.append(gate_singlevar(c800, c1600))

    # ---- G-PROBE --------------------------------------------------------- #
    G.append(gate_probe(cells))

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
    # `ok_single` = the conjuncts a SINGLE-cell archive can check. The
    # cross-cell "leaf_hash identical" conjunct is not one of them; a smoke leg
    # must not be blocked by a proposition it structurally cannot satisfy —
    # that is the §3.1 defect class applied to the smoke leg itself.
    ok_single = ok
    if c1600 is None:
        parts.append("rung leaf_hash identical across cells=N/A — only ONE cell present; "
                     "ABSENT is FAIL (⚠️ cross-cell conjunct; NOT counted in --smoke-mode)")
        ok = False
    else:
        same_leaf = (leaf_hashes.get("R800") == leaf_hashes.get("R1600")
                     and leaf_hashes.get("R800") is not MISSING)
        parts.append(f"rung leaf_hash identical across cells={same_leaf}")
        if not same_leaf:
            ok = False
            ok_single = False
    G.append(gate("G-RUNG",
                  f"both manifests: config.rung.c == {RUNG_C}, config.rung.agent == "
                  f"\"{RUNG_AGENT}\", config.rung.leaf_hash identical across cells, "
                  f"config.rung.sims == 800 (R800) / 1600 (R1600)",
                  ok, "; ".join(parts), ", ".join(addrs),
                  smoke_status="PASS" if ok_single else "FAIL"))

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
    # ⚠️ BLIND_COMMIT is checked at BOTH searched addresses EXPLICITLY (manifest
    # top level AND `config.stamps.BLIND_COMMIT`) rather than through resolve()'s
    # first-wins, because READ_RULE §3 requires it "in both manifests, at BOTH
    # searched addresses".
    parts, addrs, ok, ok_single = [], [], True, True
    fields = {}
    for key, aliases in (("carc_rs_version", ()),
                         ("tile_data_semantic_digest", ()),
                         ("code_rev", ())):
        vals = {}
        for nm, c in cells:
            v, addr = resolve(c.manifest, key, aliases=aliases)
            vals[nm] = v
            addrs.append(f"{nm}.{key}:{addr or 'ABSENT'}")
            if v is MISSING:                      # PRESENCE is single-cell checkable
                ok = False
                ok_single = False
        fields[key] = vals
        if c1600 is None:
            # ⚠️ cross-cell conjunct; NOT counted in --smoke-mode (see G-RUNG).
            same = "N/A(one cell) ⚠️ cross-cell conjunct, not counted in --smoke-mode"
            ok = False
        else:
            same = (vals["R800"] is not MISSING and vals["R800"] == vals.get("R1600"))
            if not same:
                ok = False
        shown = fmt_val(vals["R800"])
        if len(shown) > 24:
            shown = shown[:24] + "…"
        parts.append(f"{key}: R800={shown} identical_across_cells={same}")
    # ⚠️ BLIND_COMMIT AND THE SMOKE LEG. READ_RULE §3 VOIDS on "a manifest carrying
    # the placeholder", so the placeholder test is SUBSTRING-based, not an exact
    # match against a guessed spelling — the frozen file's real placeholder text is
    # `PLACEHOLDER_BLIND_COMMIT_NOT_YET_STAMPED`, which an exact-match test would
    # have waved through. But the sha is stamped in the FOLLOW-UP commit, AFTER the
    # smoke leg runs (READ_RULE §0; `run_cells.sh` documents the smoke as exempt
    # from the blind precondition), so on a smoke this conjunct is structurally
    # unsatisfiable and must not block a launch. It therefore contributes to the
    # SMOKE verdict only when it is actually checkable: a real stamp on both sides.
    blind_is_placeholder = (
        blind_expected is None
        or any(t in blind_expected.upper()
               for t in ("PLACEHOLDER", "PENDING", "TBD", "NOT_YET", "NOT-YET")))
    for nm, c in cells:
        top = _walk(c.manifest, "BLIND_COMMIT")
        stamp = _walk(c.manifest, "config.stamps.BLIND_COMMIT")
        addrs.append(f"{nm}.BLIND_COMMIT:BLIND_COMMIT+config.stamps.BLIND_COMMIT")
        both_present = top is not MISSING and stamp is not MISSING
        placeholder = any(
            v is not MISSING and (str(v).strip() == "" or any(
                t in str(v).upper() for t in ("PLACEHOLDER", "PENDING", "TBD",
                                              "NOT_YET", "NOT-YET")))
            for v in (top, stamp))
        matches = (both_present and blind_expected is not None
                   and str(top).strip() == blind_expected
                   and str(stamp).strip() == blind_expected)
        conjunct_ok = both_present and not placeholder and matches
        smoke_applicable = both_present and not blind_is_placeholder
        parts.append(f"{nm} BLIND_COMMIT top={fmt_val(top)[:12]}… stamps="
                     f"{fmt_val(stamp)[:12]}… both_addresses_present={both_present} "
                     f"placeholder={placeholder} matches_launcher={matches}"
                     + ("" if smoke_applicable else
                        " ⚠️ NOT YET STAMPED — this conjunct is N/A in --smoke-mode "
                        "(the sha lands in the follow-up commit, after the smoke leg)"))
        if not conjunct_ok:
            ok = False
            if smoke_applicable:
                ok_single = False
    if blind_expected is None:
        parts.append("⛔ the launcher's frozen BLIND_COMMIT file is ABSENT from --prep-dir "
                     "— nothing to compare against; ABSENT is FAIL (READ_RULE §3).")
        ok = False
    elif blind_is_placeholder:
        parts.append(f"⛔ the launcher's frozen BLIND_COMMIT file still carries a PLACEHOLDER "
                     f"({blind_expected[:40]!r}) — READ_RULE §3 VOIDS on a manifest carrying "
                     "the placeholder, so a real cell adjudicated against it FAILS. (Expected "
                     "before the freeze ceremony stamps the sha; N/A in --smoke-mode.)")
        ok = False
    else:
        parts.append(f"launcher's frozen value = {blind_expected[:12]}…")
    G.append(gate("G-TOOL",
                  "same carc_rs_version and tile_data_semantic_digest across both cells; "
                  "same code rev in both; BLIND_COMMIT in both manifests, at BOTH searched "
                  "addresses, equal to the launcher's frozen value",
                  ok, "; ".join(parts), ", ".join(addrs),
                  smoke_status="PASS" if ok_single else "FAIL"))

    # ---- G-N ------------------------------------------------------------- #
    parts, ok = [], True
    for nm, c in cells:
        n_scored = len(c.scored())
        nf_manifest, _ = resolve(c.manifest, "n_failed")
        nf_sum = c.summary.get("n_failed", MISSING)
        rate = c.summary.get("failure_rate", MISSING)
        n_failed = nf_sum if nf_sum is not MISSING else nf_manifest
        if rate is MISSING and n_failed is not MISSING:
            rate = float(n_failed) / max(1, n_scored + int(n_failed))
        to_sum = c.summary.get("champ_timeouts", MISSING)
        to_rec = sum(int(r.get("champ_timeouts", 0) or 0) for r in c.scored())
        parts.append(f"{nm}: games scored FROM RECORDS={n_scored}, n_failed="
                     f"{fmt_val(n_failed)}, failure_rate={fmt_val(rate)}, failure records "
                     f"on disk={len(c.failure_records)}, champ_timeouts(summary)="
                     f"{fmt_val(to_sum)} / (re-summed from records)={to_rec}")
        if n_scored < N_GAMES_REQUIRED:
            ok = False
        # §3: a nonzero rate BELOW 2% is reported and does not by itself fire G-N.
        if rate is not MISSING and rate is not None and float(rate) >= FAILURE_RATE_FLOOR:
            ok = False
        # §3.4: champ_timeouts == 0 in BOTH cells — the ONLY channel by which box
        # load could reach a game OUTCOME rather than only its clock. ABSENT is FAIL.
        if to_sum is MISSING or int(to_sum) != 0 or to_rec != 0:
            ok = False
    if c1600 is None:
        parts.append("⛔ only ONE cell present — the gate names EACH cell; ABSENT is FAIL")
        ok = False
    G.append(gate("G-N",
                  f"{N_GAMES_REQUIRED} games scored in EACH cell (counted FROM RECORDS); "
                  f"n_failed == 0 (a nonzero rate below {FAILURE_RATE_FLOOR:.0%} is REPORTED "
                  "and does not by itself fire this gate — §3/§3.1); champ_timeouts == 0 in "
                  "BOTH cells (§3.4)",
                  ok, "; ".join(parts),
                  "RECORDS (game count, champ_timeouts re-sum) + summary.json + manifest "
                  "top level (n_failed / failure_rate / champ_timeouts)"))

    # ---- G-TIMING (burn-in window, §3.2) --------------------------------- #
    G.append(gate_timing(c800, out_root))

    # ---- G-TIMING-FULL --------------------------------------------------- #
    G.append(gate_timing_full(c800))

    # ---- G-TENANCY ------------------------------------------------------- #
    G.append(gate_tenancy(out_root))

    # ---- G-SAT ----------------------------------------------------------- #
    wr = c800.summary.get("winrate")
    ok = wr is not None and SAT_BAND[0] <= float(wr) <= SAT_BAND[1]
    G.append(gate("G-SAT",
                  f"CELL R800's probe winrate vs h800 is inside [{SAT_BAND[0]}, {SAT_BAND[1]}]",
                  ok, f"CELL R800 winrate={fmt_val(wr if wr is not None else MISSING)}",
                  "summary.json (CELL R800)"))

    assert [g["id"] for g in G] == list(GATE_IDS), "gate order/ids drifted from READ_RULE §3"
    return G


# --------------------------------------------------------------------------- #
# §4 — THE BRANCHES, in order, first-match-wins                                 #
# CARRIED BYTE-IDENTICAL from `analyze_d2r2.py` except for the §4.1 clause,      #
# which is an ADDITION of this pair's READ_RULE and cannot change any branch     #
# condition (it can only route to `U-UNREADABLE`, which a short pair already     #
# reaches through `G-BAND`/`G-N`).                                              #
# --------------------------------------------------------------------------- #
def adjudicate(gates: list[dict], S: float | None, z_S: float | None,
               witness_ok: bool, s_suppressed_reason: str | None = None) -> tuple[str, str]:
    failed = [g["id"] for g in gates if g["status"] == "FAIL"]
    if failed:
        return "U-UNREADABLE", ("§3 gate(s) FAILED: " + ", ".join(failed)
                                + " — ANY §3 gate FAILS ⇒ U-UNREADABLE.")
    if s_suppressed_reason:
        return "U-UNREADABLE", ("READ_RULE §4.1 — no `S` exists for this run: "
                                + s_suppressed_reason)
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
# §4.3 — PER-CELL COMPANION BLOCK                                               #
# --------------------------------------------------------------------------- #
def cell_block(nm: str, c: Cell, rung_label: str, out_root: Path) -> dict:
    s = c.summary
    m = c.manifest
    decks = c.complete_decks()
    seats = {0: sum(1 for r in c.scored() if int(r["a_seat"]) == 0),
             1: sum(1 for r in c.scored() if int(r["a_seat"]) == 1)}
    mean, se, z, npair = paired(c.shim())
    elo, esig = s.get("elo"), s.get("elo_sig_1sigma")
    ci = ((elo - 1.96 * esig, elo + 1.96 * esig)
          if elo is not None and esig is not None and not math.isnan(esig) else None)
    cm, rm = s.get("champ_prefix_ms_per_move"), s.get("rung_ms_per_move")
    scale = (elo / mean) if (elo is not None and mean not in (None, 0)) else None
    full = read_full_cell(c.path)
    # §4.3 item 2 — CELL R800 additionally reports its BURN-IN window.
    burn = verdict(read_burnin(c.path), TIMING_LO, TIMING_HI) if nm == "R800" else None
    seeds = burnin_seeds()
    _, ten_samples, ten_roll = read_tenancy(out_root, nm)
    # §4.3 item 8 — realized cost, MEASURED from the records' own `elapsed_s`.
    el = [float(r["elapsed_s"]) for r in c.scored() if r.get("elapsed_s") is not None]
    workers = _walk(m, "config.backend.workers")
    return {
        "cell": nm, "path": str(c.path), "rung": rung_label,
        "manifest_present": c.manifest_present, "summary_present": c.summary_present,
        "n_games": len(c.scored()), "n_decks": len(decks),
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
        "champ_timeouts": s.get("champ_timeouts"),
        "champ_timeouts_from_records": sum(int(r.get("champ_timeouts", 0) or 0)
                                           for r in c.scored()),
        "champ_prefix_ms_per_move": cm, "rung_ms_per_move": rm,
        "time_ratio": (cm / rm) if (cm and rm) else None,
        "time_ratio_from_records": full.ratio,
        "solver_secs_per_game": s.get("solver_secs_per_game"),
        "burnin": burn,
        "burnin_seed_range": [seeds[0], seeds[-1]] if nm == "R800" else None,
        "tenancy": ten_roll, "tenancy_n_samples": len(ten_samples),
        "band_seed_start": (lambda t: None if t[0] is MISSING else t[0])(
            resolve(m, "seed_start", aliases=("band_seed_start",))),
        "cand_leaf_hash": fmt_val(resolve(m, "config.cand_leaf_hash")[0]),
        "rung_leaf_hash": fmt_val(resolve(m, "config.rung.leaf_hash")[0]),
        "rules_profile": fmt_val(resolve(m, "rules_profile.name")[0]),
        "r9_env_ok": fmt_val(resolve(m, "rules_profile.r9_env_ok", aliases=("r9_env_ok",))[0]),
        "code_rev": fmt_val(resolve(m, "code_rev")[0]),
        "carc_rs_version": fmt_val(resolve(m, "carc_rs_version")[0]),
        "tile_data_semantic_digest": fmt_val(resolve(m, "tile_data_semantic_digest")[0]),
        "realized_elo_per_pt": scale,
        "k_dets": fmt_val(resolve(m, "config.champion.k_dets")[0]),
        "sims_per_det": fmt_val(resolve(m, "config.champion.sims_per_det")[0]),
        "total_sims": fmt_val(resolve(m, "config.champion.total_sims")[0]),
        "rung_sims": fmt_val(resolve(m, "config.rung.sims")[0]),
        "workers": None if workers is MISSING else workers,
        "wall_core_secs_sum": (math.fsum(el) if el else None),
        "mean_elapsed_s": (math.fsum(el) / len(el)) if el else None,
        "ms_per_total_sim": ((cm / PROBE_TOTAL_SIMS) if cm else None),
    }


def f(x, nd=4):
    return "n/a" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


# --------------------------------------------------------------------------- #
# RENDERING                                                                     #
# --------------------------------------------------------------------------- #
def render_md(v: dict) -> str:
    L: list[str] = []
    A = L.append
    A("# READOUT — D2-R3 rung-compression cell (`track_d2r3_prep`), "
      "the cost-calibration successor")
    A("")
    A(f"> **BRANCH: `{v['branch']}`** — {v['branch_reason']}")
    A(">")
    A(f"> Blind pair `{v['blind_commit']}` (`DESIGN.md` + `READ_RULE.md`; band "
      f"`{BAND}`). The adjudicator (`analyze_d2r3.py`) is a port of "
      "`../track_d2r2_prep/analyze_d2r2.py`, itself a port of the blind original; the "
      "port is sound because this pair's READ_RULE §1/§2/§5/§6 and §4's five branch "
      "blocks are carried verbatim, and the file's own module docstring enumerates the "
      "thirteen changes exhaustively. The branch is taken VERBATIM.")
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
          "companion table on EVERY branch *including* `U-UNREADABLE`. Under this branch **nothing "
          "below is adjudicated, quoted as a verdict, or entered in `experiments/results.csv`.** "
          "No spacing claim, no rung-compression claim, and no strength claim follows from this "
          "run. `U-UNREADABLE` is a fully acceptable outcome (READ_RULE §4).")
        A("")
        A("### Instrument defects observed (post-adjudication diagnosis — moves no bar)")
        A("")
        A("Named here with realized values because `U-UNREADABLE` requires the failed gate to be "
          "named. This is DIAGNOSIS, not adjudication: no threshold in the frozen pair was "
          "touched, and per READ_RULE §4 **the session that writes any instrument fix MUST be a "
          "session that has not seen `S`, `z_S`, or either cell's summary statistics.**")
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
    if v["s_suppressed_reason"]:
        A(NO_S_SENTENCE.format(reason=v["s_suppressed_reason"]))
        A("")
        A("```")
        A("S      = NOT COMPUTED (READ_RULE §4.1)")
        A("se(S)  = NOT COMPUTED")
        A("z_S    = NOT COMPUTED")
        A(f"n_common = {v['n_common']} decks  [the two cells' shared complete decks; the "
          f"pre-registered requirement is {N_COMMON_REQUIRED}]")
        A(f"M_R800   = {f(v['M_R800'])} pts   (se {f(v['se_M_R800'])}, z {f(v['z_M_R800'])})"
          "   <- CELL R800's OWN margin, not a spacing")
        A(f"M_R1600  = {f(v['M_R1600'])} pts   (se {f(v['se_M_R1600'])}, z {f(v['z_M_R1600'])})"
          "   <- CELL R1600's OWN margin, not a spacing")
        A("```")
    else:
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
    A("## §3 — THE GATES (twelve; fail-closed; ABSENT is FAIL, never a silent skip)")
    A("")
    A("| gate | status | realized | address(es) resolved |")
    A("|---|---|---|---|")
    for g in v["gates"]:
        realized = g["realized"].replace("|", "\\|")
        addr = g["address"].replace("|", "\\|")
        A(f"| `{g['id']}` | {'✅ PASS' if g['status'] == 'PASS' else '⛔ FAIL'} | {realized} | `{addr}` |")
    A("")
    A(f"**All twelve gates: {v['gates_summary']}.**")
    A("")
    A("Address discipline (READ_RULE §3): every gate is read at the manifest TOP LEVEL first, "
      "then at `config.*`, then at the emitter's `config` sub-dict containers "
      "(`config.backend/champion/endgame/stamps/rung/opponent/env.*`). The resolved address is "
      "printed for every gate above, so no resolution is silent. `G-SINGLEVAR`'s two readings — "
      "the LITERAL key-set diff and the ALIAS-AWARE cross-check of READ_RULE §3.3 — are BOTH "
      "printed, so no future adjudicator has to win an argument about which was intended.")
    A("")
    A("---")
    A("")
    A("## §4.3 — THE COMPANION TABLE (all EIGHT items, printed on EVERY branch)")
    A("")
    for blk in v["cell_blocks"]:
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
        A(f"| own deck-paired margin ± se (z) | {f(blk['paired_mean_margin'])} ± "
          f"{f(blk['paired_se'])} (z {f(blk['paired_z'], 3)}) over {blk['n_paired']} decks |")
        A(f"| avg diff (unpaired) | {f(blk['avg_diff'], 3)} |")
        A(f"| n_failed / failure rate | {blk['n_failed']} / {f(blk['failure_rate'], 5)} "
          "(stated even when zero) |")
        A(f"| failed_classes | `{blk['failed_classes']}` |")
        A(f"| `champ_timeouts` (summary / re-summed from records) | "
          f"{blk['champ_timeouts']} / {blk['champ_timeouts_from_records']} |")
        A("")
        A("**2. cost / timing**")
        A("")
        A(f"`champ_prefix_ms_per_move` (= the CANDIDATE side — the field-name trap, READ_RULE §2) "
          f"**{f(blk['champ_prefix_ms_per_move'], 1)}** · `rung_ms_per_move` "
          f"**{f(blk['rung_ms_per_move'], 1)}** · realized whole-cell ratio "
          f"**{f(blk['time_ratio'])}×** (from-records **{f(blk['time_ratio_from_records'])}×**) · "
          f"`solver_secs_per_game` **{f(blk['solver_secs_per_game'], 3)}**")
        A("")
        if blk["burnin"] is not None:
            b = blk["burnin"]
            A(f"**BURN-IN WINDOW (CELL R800 only, READ_RULE §3.2):** seeds "
              f"`{blk['burnin_seed_range'][0]}..{blk['burnin_seed_range'][1]}` × "
              f"{SEATINGS_PER_DECK} seatings = {N_BURNIN_DECKS * SEATINGS_PER_DECK} games; "
              f"on disk **{b['n_games']}** (complete=**{b['complete']}**, missing "
              f"{b['n_missing']}, malformed {b['n_malformed']}); "
              f"`champ_prefix_ms_per_move` **{f(b['champ_prefix_ms_per_move'], 1)}** · "
              f"`rung_ms_per_move` **{f(b['rung_ms_per_move'], 1)}** · ratio "
              f"**{f(b['ratio'])}×** vs bar [{b['bar_lo']}, {b['bar_hi']}] ⇒ "
              f"**{'PASS' if b['pass'] else 'FAIL'}**")
            A("")
        A("**3. provenance**")
        A("")
        A(f"band `{blk['band_seed_start']}` · `cand_leaf_hash` `{blk['cand_leaf_hash']}` · "
          f"`rung.leaf_hash` `{blk['rung_leaf_hash']}` · rules `{blk['rules_profile']}` "
          f"(`r9_env_ok`={blk['r9_env_ok']}) · code rev `{blk['code_rev']}` · "
          f"`carc_rs_version` `{blk['carc_rs_version']}` · `tile_data_semantic_digest` "
          f"`{str(blk['tile_data_semantic_digest'])[:16]}…` · probe budget "
          f"k{blk['k_dets']}×{blk['sims_per_det']} = {blk['total_sims']} · `rung_sims` "
          f"{blk['rung_sims']}")
        A("")
        A("**4. tenancy roll-up** "
          + ("(GATED — `G-TENANCY` reads CELL R800 only, §3.4)" if blk["cell"] == "R800"
             else "(printed, NOT gated — §3.4 scopes the gate to CELL R800)"))
        A("")
        t = blk["tenancy"]
        A(f"samples **{t['n_samples']}** · peak foreign CPU **{t['max_foreign_total_cpu_pct']}%** "
          f"(bar {t['bar_foreign_total_cpu_pct']}%) · longest consecutive over-bar run "
          f"**{t['max_consecutive_breach_samples']}** (confirm threshold "
          f"{t['confirm_samples_required']}) · exclusive **{t['exclusive']}**")
        A("")
        A("| top foreign process by peak CPU | peak % |")
        A("|---|---|")
        if t["top_foreign_by_cpu"]:
            for row in t["top_foreign_by_cpu"]:
                A(f"| `{str(row['cmd'])[:110].replace('|', '\\|')}` | {row['peak_cpu_pct']} |")
        else:
            A("| *(none at or above the per-process naming threshold)* | — |")
        A("")
    A("### 5. the primary statistic, its dispersion, and the elo-equivalent")
    A("")
    if v["s_suppressed_reason"]:
        A(NO_S_SENTENCE.format(reason=v["s_suppressed_reason"]))
        A("")
    else:
        A("| quantity | value |")
        A("|---|---|")
        A(f"| `S` = M_R800 − M_R1600 | **{f(v['S'])} pts/game** |")
        A(f"| `se_realized` | **{f(v['se_S'])} pts** (DESIGN §4.2 pre-registered: {SE_COMMITTED} pts) |")
        A(f"| `z_S` | **{f(v['z_S'])}** |")
        A(f"| `n_common` | {v['n_common']} decks |")
        A(f"| elo-equivalent of `S` | **{f(v['S_elo'], 1)} elo** at the realized scale "
          f"{f(v['scale_used'], 3)} elo/pt |")
        A(f"| realized scale, CELL R800 | {f(v['cell_blocks'][0]['realized_elo_per_pt'], 3)} "
          "elo/pt (elo ÷ own deck-paired margin) |")
        if len(v["cell_blocks"]) > 1:
            A(f"| realized scale, CELL R1600 | "
              f"{f(v['cell_blocks'][1]['realized_elo_per_pt'], 3)} elo/pt |")
        A(f"| pre-registered scale (DESIGN §4.3) | {ELO_PER_PT_PREREG} elo/pt ⇒ `S` = "
          f"{f(v['S'] * ELO_PER_PT_PREREG if v['S'] is not None else None, 1)} elo |")
        A(f"| direct elo difference (R800 − R1600) | {f(v['elo_delta'], 1)} elo |")
        A("")
        A(f"> **`se_realized` as the `D2-COMPRESSED`-reachability witness (READ_RULE §4 "
          f"boundary note):** realized `se(S)` = **{f(v['se_S'])} pts** vs the committed "
          f"{SE_COMMITTED} pts ⇒ `D2-COMPRESSED` was "
          f"**{'REACHABLE' if v['compressed_reachable'] else 'NOT REACHABLE'}** on this run. "
          "That branch opens only where the realized dispersion prints BELOW 1.25 pts; at or "
          "above it, any `z_S ≥ 2.0` lands in `D2-COARSE` by construction.")
        A("")
    A("### 6. every gate, its realized value, and the address that resolved it")
    A("")
    A("See the §3 table above — it carries the realized value and the resolved address for all "
      "twelve gates, which is item 6 in full.")
    A("")
    A("### 7. the DESIGN §1 prior table, reprinted beside this readout's own `S`")
    A("")
    A("| source | contrast | n | band | result | ≈ pts (DESIGN §4.3) |")
    A("|---|---|---|---|---|---|")
    for row in PRIOR_TABLE:
        A(f"| {row['source']} | {row['contrast']} | {row['n']} | {row['band']} | "
          f"**{row['result']}** | ≈{row['in_points_prereg']} |")
    b0 = v["cell_blocks"][0]
    this_cell = ("**NO `S` — READ_RULE §4.1**" if v["s_suppressed_reason"]
                 else f"**{f(v['S_elo'], 1)} elo-equivalent ({f(v['S'])} pts, "
                      f"z {f(v['z_S'], 2)})**")
    A(f"| **THIS CELL (D2-R3, band {BAND}, n_common {v['n_common']})** | probe k{b0['k_dets']}×"
      f"{b0['sims_per_det']} vs h800 rung minus same probe vs h1600 rung | 400 games / "
      f"{v['n_common']} decks each | {BAND} | {this_cell} | "
      f"{'n/a' if v['s_suppressed_reason'] else f(v['S'], 2)} |")
    A("")
    A("⚠️ DESIGN §3.4: D2's ABSOLUTE numbers are NOT comparable to the F5 `fair_ruler_*` rows "
      "(different backend + pre-`fixed_v1` rules era). Only D2's internal cell-vs-cell contrast "
      "is claimed. READ_RULE §5: no statistic from attempts 1 or 2 is quoted or carried here.")
    A("")
    A("### 8. the cost ledger — realized wall / core-h, and the probe's ms per total-sim")
    A("")
    A("| cell | games | mean `elapsed_s`/game | Σ `elapsed_s` (core-s) | core-h | `champ_prefix_ms_per_move` | ms per TOTAL-SIM |")
    A("|---|---|---|---|---|---|---|")
    tot_core_h = 0.0
    for blk in v["cell_blocks"]:
        core_s = blk["wall_core_secs_sum"]
        core_h = (core_s / 3600.0) if core_s else None
        if core_h:
            tot_core_h += core_h
        A(f"| CELL {blk['cell']} | {blk['n_games']} | {f(blk['mean_elapsed_s'], 2)} | "
          f"{f(core_s, 1)} | {f(core_h, 2)} | {f(blk['champ_prefix_ms_per_move'], 1)} | "
          f"{f(blk['ms_per_total_sim'], 5)} |")
    A(f"| **TOTAL** | | | | **{tot_core_h:.2f}** | | |")
    A("")
    A(f"`elapsed_s` is per-GAME wall on one worker, so Σ`elapsed_s` IS core-seconds; the box ran "
      f"at W={b0['workers']}. **The `ms per TOTAL-SIM` column is the quantity READ_RULE §4.3 item "
      f"8 names for a future equal-time pairing to calibrate against** — `champ_prefix_ms_per_move` "
      f"÷ {PROBE_TOTAL_SIMS} total sims. This is a COST ledger, not a statistic and not a gate "
      "input.")
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
      "historical mis-stamped rung-`c` cells. **Added for this pair, and binding:** no branch "
      "licenses a `--sims` re-pick, a resumed or salvaged burn-in-aborted cell, or a fourth "
      "attempt (§3.2). No branch adjudicates, quotes, or carries any statistic from attempts 1 "
      "or 2.")
    A("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- #
# POST-ADJUDICATION DIAGNOSIS — names the failed gate with its realized value    #
# --------------------------------------------------------------------------- #
GENERIC_DEFECT = {
    "G-BAND": "the band / deck-set / n_common precondition",
    "G-SINGLEVAR": "the single-experimental-variable precondition (literal key-set diff "
                   "and/or the §3.3 alias cross-check)",
    "G-PROBE": "the probe's own budget and search identity (k_dets × sims_per_det = "
               "total_sims, c_puct, exact_k, backend, tie-arbiter disarmed)",
    "G-RUNG": "the rung's identity (c, agent, leaf hash, sims)",
    "G-LEAF": "the probe's leaf identity (the curve125 champion leaf)",
    "G-RULES": "the rules profile + its R9 environment latch",
    "G-TOOL": "one-instrument provenance (rust build, code rev, BLIND_COMMIT at BOTH addresses)",
    "G-N": "the completed-games / failure-rate / champ_timeouts precondition",
    "G-TIMING": "the BURN-IN equal-time precondition (READ_RULE §3.2)",
    "G-TIMING-FULL": "the whole-cell timing DRIFT envelope and its from-records cross-check",
    "G-TENANCY": "the exclusive-tenancy precondition (READ_RULE §3.4)",
    "G-SAT": "the non-saturation precondition",
}


def diagnose(gates: list[dict], blocks: list[dict], branch: str,
             s_suppressed_reason: str | None):
    """Name the failed gate(s) with realized values — READ_RULE §4's `U-UNREADABLE`
    requirement. DIAGNOSIS ONLY: moves no bar, licenses no fix."""
    by_id = {g["id"]: g for g in gates}
    defects: list[dict] = []
    if branch != "U-UNREADABLE":
        return defects, []

    if s_suppressed_reason:
        defects.append({
            "gate": "READ_RULE §4.1",
            "headline": "no second cell / short pair — no `S` exists and none was computed",
            "detail": (f"{s_suppressed_reason} Per READ_RULE §4.1 this is a `U-UNREADABLE`, not a "
                       "new branch, and the readout prints the §4.3 companion table for "
                       "everything that exists **without** printing a one-cell number that a "
                       "later reader could mistake for `S`."),
        })

    b800 = blocks[0]
    if by_id.get("G-TIMING", {}).get("status") == "FAIL":
        b = by_id["G-TIMING"].get("burnin", {})
        r = b.get("ratio")
        if r is None or not b.get("complete", False):
            headline = ("the burn-in window is INCOMPLETE or its timing fields are absent "
                        "— FAIL-CLOSED")
            detail = (f"Realized: {by_id['G-TIMING']['realized']}  \n  READ_RULE §3.2: \"an "
                      "unreadable window is not a passed window\".")
        else:
            lo, hi = b["bar_lo"], b["bar_hi"]
            side = "BELOW" if r < lo else ("ABOVE" if r > hi else "INSIDE")
            edge = lo if r < lo else hi
            detail = (
                f"CELL R800's realized BURN-IN equal-time ratio is **{r:.4f}** "
                f"(`champ_prefix_ms_per_move` {b['champ_prefix_ms_per_move']:.1f} — the "
                f"CANDIDATE side, the field-name trap of READ_RULE §2 — over `rung_ms_per_move` "
                f"{b['rung_ms_per_move']:.1f}), {side} the frozen interval [{lo}, {hi}]"
                + (f" by {abs(r - edge):.4f} ({abs(r - edge) / edge:.2%} of the "
                   f"{'floor' if r < lo else 'ceiling'})" if side != "INSIDE" else "")
                + ". This bar is CARRIED VERBATIM from both prior pairs; READ_RULE §3.2 moved the "
                  "WINDOW, not the bar, so that this outcome costs ~11% of a pair instead of "
                  "100%. ⛔ READ_RULE §3.2's NO-RE-PICK clause: a burn-in FAIL is a "
                  "fourth-attempt decision for the owner, not a knob for anyone else, and band "
                  f"`{BAND}` is RETIRED with its records on it.")
            headline = ("CELL R800's realized BURN-IN equal-time ratio is outside the frozen "
                        f"[{lo}, {hi}] interval")
        defects.append({"gate": "G-TIMING", "headline": headline, "detail": detail})

    for gid, what in GENERIC_DEFECT.items():
        g = by_id.get(gid)
        if g is None or g["status"] != "FAIL" or gid == "G-TIMING":
            continue
        defects.append({
            "gate": gid,
            "headline": f"{what} FAILED",
            "detail": (f"Realized: {g['realized']}  \n  Resolved at: `{g['address']}`. "
                       "ABSENT is FAIL (READ_RULE §3, fail-closed)."),
        })

    passed = [g["id"] for g in gates if g["status"] == "PASS"]
    sv = by_id.get("G-SINGLEVAR", {})
    ctx = [
        f"**Gates that PASS: {', '.join(passed) if passed else 'NONE'}** "
        f"({len(passed)}/{len(gates)}).",
        f"**`G-SINGLEVAR`'s two readings** — literal key-set: "
        f"{sv.get('literal_reading_status', 'n/a')}; §3.3 alias cross-check: "
        f"{sv.get('alias_reading_status', 'n/a')}. READ_RULE §3.3 wrote this gate alias-aware "
        "from the start precisely so no adjudicator has to interpret it; both readings are "
        "printed above.",
        f"**CELL R800 ran** {b800['n_games']} games over {b800['n_decks']} decks, `n_failed` "
        f"{b800['n_failed']}, failure rate {b800['failure_rate']}, `champ_timeouts` "
        f"{b800['champ_timeouts']}, band {b800['band_seed_start']}, probe winrate "
        f"{b800['winrate']} against the `G-SAT` interval [{SAT_BAND[0]}, {SAT_BAND[1]}].",
    ]
    return defects, ctx


# --------------------------------------------------------------------------- #
# DRIVER                                                                        #
# --------------------------------------------------------------------------- #
def read_blind_commit(prep_dir: Path) -> str | None:
    p = Path(prep_dir) / "BLIND_COMMIT"
    if not p.is_file():
        return None
    val = p.read_text().strip()
    return val or None


def run_analysis(cell_r800: Path, cell_r1600: Path | None, out_root: Path,
                 prep_dir: Path, smoke: bool = False,
                 witness_fn=witness_from_disk) -> dict:
    """The one analysis path. `--smoke-mode` uses it with `cell_r1600=None`.

    `witness_fn` is a NAMED SEAM, present only so `--selftest` can drive the §1
    WITNESS-disagreement case through the real wiring (a genuine disagreement is
    impossible to synthesize on disk — the witness re-reads the same records).
    It is never overridden on any real adjudication path.
    """
    c800 = Cell("R800", cell_r800)
    c1600 = Cell("R1600", cell_r1600) if cell_r1600 is not None else None
    blind_expected = read_blind_commit(prep_dir)

    common = (c800.complete_decks() & c1600.complete_decks()) if c1600 else set()

    # ---- READ_RULE §4.1 — is there an `S` at all? -------------------------- #
    s_suppressed_reason = None
    if c1600 is None:
        s_suppressed_reason = (
            "CELL R1600 is ABSENT (no `--cell-r1600`, or the pair aborted at the burn-in gate "
            "before it started).")
    elif not c1600.complete_decks():
        s_suppressed_reason = "CELL R1600 carries ZERO complete decks."
    elif len(common) != N_COMMON_REQUIRED:
        s_suppressed_reason = (
            f"the pair is SHORT: n_common = {len(common)} decks against the pre-registered "
            f"{N_COMMON_REQUIRED} (READ_RULE §3 `G-BAND`).")

    M800 = se800 = z800 = M1600 = se1600 = z1600 = None
    n800 = n1600 = 0
    S = se_S = z_S = None
    n_common = len(common)
    if s_suppressed_reason is None:
        M800, se800, z800, n800 = paired(c800.shim(common))
        M1600, se1600, z1600, n1600 = paired(c1600.shim(common))
        d800_map = {(int(r["seed"]), int(r["a_seat"])): float(r["diff"]) for r in c800.scored()}
        d1600_map = {(int(r["seed"]), int(r["a_seat"])): float(r["diff"]) for r in c1600.scored()}
        delta_recs = [Rec(s, seat, d800_map[(s, seat)] - d1600_map[(s, seat)])
                      for s in sorted(common) for seat in range(SEATINGS_PER_DECK)
                      if (s, seat) in d800_map and (s, seat) in d1600_map]
        S, se_S, z_S, n_common = paired(delta_recs)
    else:
        # Each cell's OWN margin is still a §4.3 item-1 quantity and is printed;
        # it is NOT `S` and the readout says so in as many words.
        M800, se800, z800, n800 = paired(c800.shim())
        if c1600 is not None:
            M1600, se1600, z1600, n1600 = paired(c1600.shim())

    # ---- §1 witness -------------------------------------------------------- #
    W = witness_fn(cell_r800, cell_r1600 if cell_r1600 is not None else Path(os.devnull))
    if s_suppressed_reason is None:
        agreement = {
            "S": close(S, W["S"]), "se_S": close(se_S, W["se_S"]), "z_S": close(z_S, W["z_S"]),
            "M_R800": close(M800, W["M_R800"]), "M_R1600": close(M1600, W["M_R1600"]),
            "n_common": n_common == W["n_common"],
        }
    else:
        # Nothing to witness: no `S` was computed. Recorded as vacuously true so
        # the WITNESS cannot be the thing that fires a branch §4.1 already owns.
        agreement = {k: True for k in ("S", "se_S", "z_S", "M_R800", "M_R1600", "n_common")}
    witness_ok = all(agreement.values())

    # ---- §3 gates ---------------------------------------------------------- #
    gates = run_gates(c800, c1600, common, out_root, blind_expected, smoke=smoke)
    branch, reason = adjudicate(gates, S, z_S, witness_ok, s_suppressed_reason)

    blocks = [cell_block("R800", c800, "HeuristicMCTS(h800, c=3.0)", out_root)]
    if c1600 is not None:
        blocks.append(cell_block("R1600", c1600, "HeuristicMCTS(h1600, c=3.0)", out_root))
    scale_used = blocks[0]["realized_elo_per_pt"] or ELO_PER_PT_PREREG
    S_elo = S * scale_used if S is not None else None
    elo_delta = ((blocks[0]["elo"] - blocks[1]["elo"])
                 if len(blocks) > 1 and blocks[0]["elo"] is not None
                 and blocks[1]["elo"] is not None else None)
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
    defects, context_notes = diagnose(gates, blocks, branch, s_suppressed_reason)
    return {
        "run_id": "track_d2r3_prep", "band": BAND,
        "blind_commit": blind_expected or "ABSENT",
        "branch": branch, "branch_reason": reason,
        "s_suppressed_reason": s_suppressed_reason,
        "S": S, "se_S": se_S, "z_S": z_S, "n_common": n_common,
        "M_R800": M800, "se_M_R800": se800, "z_M_R800": z800, "n_R800": n800,
        "M_R1600": M1600, "se_M_R1600": se1600, "z_M_R1600": z1600, "n_R1600": n1600,
        "se_prereg": SE_COMMITTED, "compressed_reachable": compressed_reachable,
        "S_elo": S_elo, "scale_used": scale_used,
        "scale_prereg": ELO_PER_PT_PREREG, "elo_delta": elo_delta, "bound": bound,
        "witness": W, "witness_agreement": agreement, "witness_ok": witness_ok,
        "gates": gates,
        "gates_summary": (f"{len(gates) - n_fail}/{len(gates)} PASS"
                          + (f", FAILED: {', '.join(g['id'] for g in gates if g['status'] == 'FAIL')}"
                             if n_fail else "")),
        "cell_blocks": blocks,
        "mandatory_coarse_sentence": mandatory,
        "prior_table": PRIOR_TABLE,
        "defects": defects, "context_notes": context_notes,
    }


# --------------------------------------------------------------------------- #
# SMOKE MODE                                                                    #
# --------------------------------------------------------------------------- #
def smoke_mode(cell_dir: Path, prep_dir: Path) -> int:
    """READ_RULE §3.3 / the h2h standing rule: the launcher's smoke leg ends here.

    Exits 0 iff the ONLY failing gates are those in `SMOKE_ALLOWED_FAILURES`.
    A failure of any BLOCKING gate is a LAUNCH BLOCKER — the whole point is to
    discover a gate that cannot read what the harness emits BEFORE game 1.
    """
    print("=" * 100)
    print("SMOKE ADJUDICATION — analyze_d2r3.py --smoke-mode")
    print(f"  archive   : {cell_dir}")
    print(f"  prep-dir  : {prep_dir}")
    print("=" * 100)
    print()
    print("ALLOWED-TO-FAIL SET (pinned at module scope as `SMOKE_ALLOWED_FAILURES`):")
    for gid, why in SMOKE_ALLOWED_FAILURES.items():
        print(f"  · {gid:<15} {why}")
    print()
    print("BLOCKING GATES (a FAIL here blocks the launch): "
          + ", ".join(SMOKE_BLOCKING_GATES))
    print()
    print("⚠️ CROSS-CELL CONJUNCT CARVE-OUT. `G-RUNG` and `G-TOOL` each carry ONE conjunct that")
    print("   compares the TWO cells (`rung.leaf_hash` identical; `carc_rs_version` /")
    print("   `tile_data_semantic_digest` / `code_rev` identical). A single-cell smoke archive")
    print("   cannot satisfy those BY CONSTRUCTION, so they are recorded N/A and are NOT counted")
    print("   in the smoke verdict — that is the §3.1 defect class ('would this fail on every")
    print("   healthy run?') applied to the smoke leg itself. EVERY single-cell-checkable")
    print("   conjunct of both gates — including BLIND_COMMIT at both addresses — still BLOCKS.")
    print("   The column below reports the single-cell status for those two gates.")
    print()

    v = run_analysis(Path(cell_dir), None, Path(cell_dir), Path(prep_dir), smoke=True)
    gates = v["gates"]
    by_id = {g["id"]: g for g in gates}

    print("-" * 100)
    print(f"{'gate':<16} {'status':<7} realized value / resolved address")
    print("-" * 100)
    for g in gates:
        eff = g.get("smoke_status", g["status"])   # cross-cell conjuncts carved out
        if eff == "PASS":
            tag = "PASS" if g["status"] == "PASS" else "PASS†"
        else:
            tag = "FAIL*" if g["id"] in SMOKE_ALLOWED_FAILURES else "FAIL"
        print(f"{g['id']:<16} {tag:<7} {g['realized'][:2000]}")
        print(f"{'':<16} {'':<7} @ {g['address']}")
    # the alias half of G-SINGLEVAR is single-cell checkable and BLOCKS.
    alias_status = by_id["G-SINGLEVAR"].get("alias_reading_status", "FAIL")
    print(f"{'G-SINGLEVAR/alias':<16} {alias_status:<7} "
          f"{json.dumps(by_id['G-SINGLEVAR'].get('alias_crosscheck', {}), sort_keys=True)}")
    print("-" * 100)
    print("  (FAIL* = a FAIL a 16-game throwaway archive cannot avoid by construction.)")
    print("  (PASS† = every single-cell-checkable conjunct passed; the gate's cross-cell "
          "conjunct is N/A on one cell.)")
    print()

    blocking_failures = [g["id"] for g in gates
                         if g.get("smoke_status", g["status"]) == "FAIL"
                         and g["id"] not in SMOKE_ALLOWED_FAILURES]
    if alias_status != "PASS":
        blocking_failures.append("G-SINGLEVAR/alias")
    unexpected_passes = []  # informational only; a PASS never blocks

    if blocking_failures:
        print("⛔ SMOKE ADJUDICATION FAILED — LAUNCH BLOCKER.")
        print("   Blocking gate failures: " + ", ".join(blocking_failures))
        print("   These gates are checkable on a 16-game smoke archive and did not pass, which "
              "means a gate cannot read what the harness EMITS. That is exactly the defect "
              "class this leg exists to catch (h2h AMENDMENTS.md; READ_RULE §3.1/§3.3).")
        return 1
    print("✅ SMOKE ADJUDICATION OK — the adjudicator can read this harness's real archive.")
    print("   Every gate that a 16-game smoke can satisfy DID. Failures are confined to "
          "the pinned allowed set: "
          + (", ".join(g["id"] for g in gates
                       if g.get("smoke_status", g["status"]) == "FAIL") or "none"))
    if unexpected_passes:
        print("   note: " + ", ".join(unexpected_passes))
    return 0


# --------------------------------------------------------------------------- #
# SELFTEST                                                                      #
# ⭐ THE CRITICAL DIFFERENCE FROM THE PREDECESSOR.                               #
#                                                                               #
# The h2h post-mortem (`../h2h_22016_prep/AMENDMENTS.md`): "the selftest fixture #
# generator synthesises the manifest READ_RULE.md describes, rather than one the #
# analyzer of record actually emits. A 20/20 green selftest therefore certified  #
# an instrument that could not read any real archive. The house fix is cheap and #
# general: seed the passing fixture from a real (smoke) manifest."               #
#                                                                               #
# So the PASSING fixture here is a REAL `manifest.json` + the KEY SET of a real  #
# `summary.json`, read off disk, minimally mutated. If no real manifest is       #
# reachable, `--selftest` REFUSES TO RUN — a synthesized-only selftest is not    #
# acceptable for this pair.                                                      #
# --------------------------------------------------------------------------- #
DEFAULT_FIXTURE_SEED_DIR = "/mnt/c/carc-shared/track_d2r2_prep/d2r2_rung800"
FIXTURE_BLIND = "0" * 40
FIXTURE_RNG_SEED = 20260825

# Fixture cost model: both sides at ~1000 ms/move over 70 moves => ratio ~1.00,
# comfortably inside BOTH the burn-in bar and the whole-cell envelope.
_FIX_MOVES = 70
_FIX_CHAMP_MS = 1000.0
_FIX_RUNG_MS = 1000.0

# ⚠️ OUTCOME FIELDS OF THE SEED SUMMARY ARE NEVER READ. `_fixture_summary` takes
# the seed summary's KEY SET only and fills every value itself, so no statistic
# from attempt 2 can reach a fixture, a gate, or this file. READ_RULE §5.
_FIXTURE_SUMMARY_STRUCTURAL_DEFAULTS = {
    "info": "fair", "failure_rate_trigger": 0.005, "validity_trigger_fired": False,
    "failed_cells": [], "failed_by_seat": {"0": 0, "1": 0}, "failed_classes": {},
    "n_resolved_failures": 0, "resolved_failed_cells": [], "wc_tiebreak": False,
    "wc_tie_resolved_games": 0, "opponent": "h800", "champ_latched_games": 400,
    "exact_k": PROBE_EXACT_K, "k_dets": PROBE_K_DETS, "sims": PROBE_SIMS_PER_DET,
    "total_sims": PROBE_TOTAL_SIMS, "n_failed": 0, "failure_rate": 0.0,
    "champ_timeouts": 0, "solver_secs_per_game": 1.49, "n": N_GAMES_REQUIRED,
}


def _deep(o):
    return json.loads(json.dumps(o))


def _set(d: dict, dotted: str, value):
    cur = d
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _fixture_manifest(seed_manifest: dict, rung_sims: int, blind: str) -> dict:
    """The REAL manifest, minimally mutated to this pair's frozen knobs."""
    m = _deep(seed_manifest)
    _set(m, "config.seed_start", BAND)
    _set(m, "config.band_seed_start", BAND)
    _set(m, "config.n", N_GAMES_REQUIRED)
    _set(m, "config.n_decks", N_DECKS)
    _set(m, "config.seatings_per_deck", SEATINGS_PER_DECK)
    _set(m, "config.paired", True)
    _set(m, "config.champion.k_dets", PROBE_K_DETS)
    _set(m, "config.champion.sims_per_det", PROBE_SIMS_PER_DET)
    _set(m, "config.champion.total_sims", PROBE_TOTAL_SIMS)
    _set(m, "config.champion.c_puct", PROBE_C_PUCT)
    _set(m, "config.endgame.exact_k", PROBE_EXACT_K)
    _set(m, "config.backend.name", PROBE_BACKEND)
    _set(m, "config.cand_leaf_hash", CAND_LEAF_HASH)
    _set(m, "config.rung.c", RUNG_C)
    _set(m, "config.rung.agent", RUNG_AGENT)
    _set(m, "config.rung.sims", rung_sims)
    _set(m, "config.opponent.sims", rung_sims)
    _set(m, "config.opponent.label", opp_label_for(rung_sims))
    _set(m, "rules_profile.name", RULES_PROFILE)
    _set(m, "rules_profile.r9_env_ok", True)
    _set(m, "BLIND_COMMIT", blind)
    _set(m, "config.stamps.BLIND_COMMIT", blind)
    _set(m, "n_failed", 0)
    _set(m, "failure_rate", 0.0)
    # the two cells differ ONLY in the three §3.3 addresses; scrub the per-leg
    # timestamps so nothing else can differ (they are top-level, not in `config`,
    # so G-SINGLEVAR does not read them either way — scrubbed for tidiness).
    _set(m, "utc", "2026-08-26T00:00:00+00:00")
    _set(m, "utc_end", "2026-08-26T01:00:00+00:00")
    return m


def _fixture_summary(seed_summary: dict, records: list[dict], rung_sims: int,
                     winrate: float) -> dict:
    """Build the fixture summary from the seed summary's KEY SET ONLY.

    Every value starts as `None` and is filled from the FIXTURE's own records or
    from `_FIXTURE_SUMMARY_STRUCTURAL_DEFAULTS`. No outcome value from the seed
    archive is read, so no attempt-2 statistic can reach any gate.
    """
    s = {k: None for k in seed_summary}
    s.update(_FIXTURE_SUMMARY_STRUCTURAL_DEFAULTS)
    cs = math.fsum(r["champ_prefix_secs"] for r in records)
    cmv = sum(r["champ_prefix_moves"] for r in records)
    rs = math.fsum(r["rung_secs"] for r in records)
    rmv = sum(r["rung_moves"] for r in records)
    s["champ_prefix_ms_per_move"] = cs / cmv * 1e3
    s["rung_ms_per_move"] = rs / rmv * 1e3
    s["rung_sims"] = rung_sims
    s["opponent_label"] = opp_label_for(rung_sims)
    n = len(records)
    wins = sum(1 for r in records if r["diff"] > 0)
    draws = sum(1 for r in records if r["diff"] == 0)
    s["W"], s["D"], s["L"] = wins, draws, n - wins - draws
    s["winrate"] = winrate
    s["winrate_z"] = 6.8
    s["avg_diff"] = math.fsum(r["diff"] for r in records) / n
    by = {}
    for r in records:
        by.setdefault(r["seed"], {})[r["a_seat"]] = float(r["diff"])
    ds = [(v[0] + v[1]) / 2.0 for v in by.values() if 0 in v and 1 in v]
    mu = math.fsum(ds) / len(ds)
    var = math.fsum((d - mu) ** 2 for d in ds) / (len(ds) - 1)
    se = math.sqrt(var / len(ds))
    s["paired_mean_margin"] = mu
    s["paired_z"] = mu / se if se else float("nan")
    s["n_paired"] = len(ds)
    # a display-only elo, derived from THIS fixture's own winrate.
    s["elo"] = -400.0 * math.log10(1.0 / max(1e-6, min(1 - 1e-6, winrate)) - 1.0)
    s["elo_sig_1sigma"] = 18.5
    return s


def _fixture_records(rng: random.Random, margins: list[list[float]],
                     champ_ms=_FIX_CHAMP_MS, rung_ms=_FIX_RUNG_MS) -> list[dict]:
    out = []
    for i, seats in enumerate(margins):
        seed = BAND + i
        for a_seat, diff in enumerate(seats):
            jitter_c = 1.0 + (rng.random() - 0.5) * 0.02
            jitter_r = 1.0 + (rng.random() - 0.5) * 0.02
            out.append({
                "seed": seed, "a_seat": a_seat, "info": "fair",
                "exact_k": PROBE_EXACT_K, "k_dets": PROBE_K_DETS,
                "sims": PROBE_SIMS_PER_DET,
                "diff": int(diff), "won_by_champ": bool(diff > 0), "drew": bool(diff == 0),
                "score_p0": 100 + int(diff), "score_p1": 100,
                "elapsed_s": 135.0, "moves": 142, "deck_hash": f"{seed:016x}",
                "champ_prefix_moves": _FIX_MOVES,
                "champ_prefix_secs": champ_ms * _FIX_MOVES / 1e3 * jitter_c,
                "champ_exact_moves": 2, "champ_solver_secs": 0.025, "champ_timeouts": 0,
                "rung_moves": _FIX_MOVES,
                "rung_secs": rung_ms * _FIX_MOVES / 1e3 * jitter_r,
                "latch_k": 1, "opponent": "h800",
                "opp_prefix_moves": 0, "opp_exact_moves": 0, "opp_prefix_secs": 0.0,
                "opp_solver_secs": 0.0, "opp_timeouts": 0,
            })
    return out


def _margins(rng: random.Random, S_target: float, se_target: float):
    """Deterministic per-deck margins for both cells with a controlled paired
    difference. `d1600 = d800 - delta`, delta constant across the two seatings of
    a deck, so the per-deck paired difference is exactly `delta_i`."""
    sd = se_target * math.sqrt(N_DECKS)
    m800, m1600 = [], []
    for _ in range(N_DECKS):
        base = rng.gauss(6.0, 12.0)
        seats800 = [round(base + rng.gauss(0, 4.0)) for _ in range(SEATINGS_PER_DECK)]
        delta = round(S_target + rng.gauss(0, sd))
        m800.append(seats800)
        m1600.append([x - delta for x in seats800])
    return m800, m1600


def _write_cell(d: Path, manifest: dict, summary: dict, records: list[dict]):
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (d / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    for r in records:
        (d / f"seed{r['seed']:012d}_a{r['a_seat']}.json").write_text(
            json.dumps(r, sort_keys=True))


def _write_burnin(out_root: Path, cell_dir: Path):
    """Exactly what `d2r3_lib watch` writes — the same code over the same records."""
    v = verdict(read_burnin(cell_dir), TIMING_LO, TIMING_HI)
    v["window"] = "burn-in"
    v["decided_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(0))
    (Path(out_root) / "BURNIN_R800.json").write_text(json.dumps(v, indent=2, sort_keys=True))


def _write_tenancy(out_root: Path, cell: str, breach: bool = False):
    rows = []
    for i in range(30):
        foreign = 5.0
        if breach and i in (10, 11):
            foreign = FOREIGN_TOTAL_CPU_PCT + 250.0
        rows.append({
            "utc": f"2026-08-26T00:{i:02d}:00Z", "interval_s": 2.0,
            "loadavg_1m": 22.0, "loadavg_5m": 22.0, "loadavg_15m": 22.0,
            "own_cpu_pct": 2100.0, "foreign_total_cpu_pct": foreign,
            "foreign_procs": ([{"pid": 999, "ppid": 1, "pgid": 999,
                                "cpu_pct": foreign, "sibling_measurement_run": False,
                                "cmd": "gradle --daemon assembleDebug"}] if breach and i in (10, 11)
                              else []),
            "exclusive": foreign < FOREIGN_TOTAL_CPU_PCT,
            "bar_foreign_total_cpu_pct": FOREIGN_TOTAL_CPU_PCT,
        })
    (Path(out_root) / f"TENANCY_{cell}.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")


def build_fixture(root: Path, seed_manifest: dict, seed_summary: dict,
                  S_target: float = 5.0, se_target: float = 1.5,
                  winrate: float = 0.67) -> dict:
    """The ALL-PASS fixture, seeded from a REAL manifest/summary read off disk."""
    root = Path(root)
    rng = random.Random(FIXTURE_RNG_SEED)
    m800, m1600 = _margins(rng, S_target, se_target)
    r800 = _fixture_records(rng, m800)
    r1600 = _fixture_records(rng, m1600)
    d800 = root / "d2r3_rung800"
    d1600 = root / "d2r3_rung1600"
    _write_cell(d800, _fixture_manifest(seed_manifest, 800, FIXTURE_BLIND),
                _fixture_summary(seed_summary, r800, 800, winrate), r800)
    _write_cell(d1600, _fixture_manifest(seed_manifest, 1600, FIXTURE_BLIND),
                _fixture_summary(seed_summary, r1600, 1600, winrate), r1600)
    (root / "BLIND_COMMIT").write_text(FIXTURE_BLIND + "\n")
    _write_burnin(root, d800)
    _write_tenancy(root, "R800")
    _write_tenancy(root, "R1600")
    return {"root": root, "r800": d800, "r1600": d1600, "prep": root}


# ---- fixture BREAKERS: exactly one field broken per case -------------------- #
#
# ⚠️ BREAKS THAT LAND INSIDE `config` ARE APPLIED TO **BOTH** CELLS, ON PURPOSE.
# `G-SINGLEVAR`'s literal half diffs the two `config` blocks, so mutating a
# `config` key in ONE cell is ALSO — correctly — a fourth-differing-key failure.
# That collateral FAIL is the gate doing its job, and it was observed on the
# first selftest run; the breakers are symmetric so that each case isolates the
# ONE gate it names. (`rules_profile.*` and top-level `BLIND_COMMIT` sit OUTSIDE
# `config`, so those two breaks are naturally single-cell.)
def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def _save(p: Path, o: dict):
    p.write_text(json.dumps(o, indent=2, sort_keys=True))


def _both(fx, fn):
    for key in ("r800", "r1600"):
        p = fx[key] / "manifest.json"
        if p.is_file():
            m = _load(p)
            fn(m)
            _save(p, m)


def break_band(fx):
    def mut(m):
        _set(m, "config.seed_start", BAND + 1)
        _set(m, "config.band_seed_start", BAND + 1)
    _both(fx, mut)


def break_singlevar_literal(fx):
    m = _load(fx["r1600"] / "manifest.json")
    _set(m, "config.champion.tau_p", 7.0)          # a FOURTH differing key
    _save(fx["r1600"] / "manifest.json", m)


def break_singlevar_alias(fx):
    m = _load(fx["r1600"] / "manifest.json")
    _set(m, "config.opponent.label", "HeuristicMCTS(h800)")   # mirror drifted
    _save(fx["r1600"] / "manifest.json", m)


def break_probe(fx):
    # breaks the VALUE and the k_dets × sims_per_det == total_sims identity
    _both(fx, lambda m: _set(m, "config.champion.total_sims", 5504))


def break_rung(fx):
    _both(fx, lambda m: _set(m, "config.rung.c", 1.5))


def break_leaf(fx):
    _both(fx, lambda m: _set(m, "config.cand_leaf_hash", "deadbeefdeadbeef"))


def break_rules(fx):
    m = _load(fx["r1600"] / "manifest.json")       # outside `config` — single-cell
    _set(m, "rules_profile.r9_env_ok", False)
    _save(fx["r1600"] / "manifest.json", m)


def break_tool(fx):
    m = _load(fx["r1600"] / "manifest.json")       # outside `config` — single-cell
    _set(m, "BLIND_COMMIT", "f" * 40)
    _save(fx["r1600"] / "manifest.json", m)


def break_n(fx):
    s = _load(fx["r800"] / "summary.json")
    s["champ_timeouts"] = 1                        # READ_RULE §3.4
    _save(fx["r800"] / "summary.json", s)


def break_timing(fx):
    """Inflate the RUNG side inside the burn-in window only, so the burn-in ratio
    drops below the floor while the whole-cell envelope still holds."""
    for seed in burnin_seeds():
        for a in range(SEATINGS_PER_DECK):
            p = fx["r800"] / f"seed{seed:012d}_a{a}.json"
            r = _load(p)
            r["rung_secs"] = r["rung_secs"] * 1.30
            _save(p, r)
    _write_burnin(fx["root"], fx["r800"])          # the live watcher re-reads the same records
    s = _load(fx["r800"] / "summary.json")         # keep summary consistent with records
    recs = [_load(p) for p in sorted(fx["r800"].glob("seed*_a*.json"))]
    s["rung_ms_per_move"] = (math.fsum(r["rung_secs"] for r in recs)
                             / sum(r["rung_moves"] for r in recs) * 1e3)
    _save(fx["r800"] / "summary.json", s)


def break_timing_live_disagree(fx):
    """The live watcher's verdict no longer matches the records — READ_RULE §3.2
    says that means the records moved, and it FAILS."""
    b = _load(fx["root"] / "BURNIN_R800.json")
    b["ratio"] = (b["ratio"] or 1.0) * 1.05
    _save(fx["root"] / "BURNIN_R800.json", b)


def break_timing_full(fx):
    s = _load(fx["r800"] / "summary.json")
    s["champ_prefix_ms_per_move"] = s["rung_ms_per_move"] * 1.50   # outside [0.75, 1.35]
    _save(fx["r800"] / "summary.json", s)


def break_tenancy(fx):
    _write_tenancy(fx["root"], "R800", breach=True)


def break_sat(fx):
    s = _load(fx["r800"] / "summary.json")
    s["winrate"] = 0.95
    _save(fx["r800"] / "summary.json", s)


def break_no_r1600(fx):
    shutil.rmtree(fx["r1600"])


# ---- READ_RULE cross-audits ------------------------------------------------ #
def audit_constants() -> list[tuple[str, bool, str]]:
    """(a) every threshold this file uses that ALSO lives in `d2r3_lib` must be
    the SAME OBJECT (imported, not re-typed); (b) READ_RULE.md §3's own text must
    still carry the literals this file gates on."""
    rows: list[tuple[str, bool, str]] = []
    for nm in ("BAND", "N_DECKS", "N_BURNIN_DECKS", "SEATINGS_PER_DECK",
               "TIMING_LO", "TIMING_HI", "TIMING_FULL_LO", "TIMING_FULL_HI",
               "TENANCY_CONFIRM_SAMPLES", "FOREIGN_TOTAL_CPU_PCT"):
        mine = globals()[nm]
        theirs = getattr(d2r3_lib, nm)
        rows.append((f"constant {nm} IS d2r3_lib.{nm} (imported, not a second copy)",
                     mine is theirs, f"{mine!r} vs {theirs!r}"))
    rr = (HERE / "READ_RULE.md").read_text()
    try:
        sec3 = rr.split("## §3 — PRECONDITIONS")[1].split("## §4 — THE BRANCHES")[0]
    except IndexError:
        rows.append(("READ_RULE.md §3 section is locatable", False, "split failed"))
        return rows
    for label, needle in (
        ("G-BAND band", str(BAND)),
        ("G-BAND n_common", f"`n_common` == {N_COMMON_REQUIRED}"),
        ("G-PROBE k_dets", f"`config.champion.k_dets` == {PROBE_K_DETS}"),
        ("G-PROBE sims_per_det", f"`config.champion.sims_per_det` == {PROBE_SIMS_PER_DET}"),
        ("G-PROBE total_sims", f"`config.champion.total_sims` == {PROBE_TOTAL_SIMS}"),
        ("G-PROBE c_puct", f"`c_puct` == {PROBE_C_PUCT}"),
        ("G-PROBE exact_k", f"`exact_k` == {PROBE_EXACT_K}"),
        ("G-PROBE backend", f"backend `{PROBE_BACKEND}`"),
        ("G-RUNG c", f"`config.rung.c` == {RUNG_C}"),
        ("G-RUNG agent", f"`\"{RUNG_AGENT}\"`"),
        ("G-LEAF hash", CAND_LEAF_HASH),
        ("G-RULES profile", f"`\"{RULES_PROFILE}\"`"),
        ("G-N games", f"{N_GAMES_REQUIRED} games scored in EACH cell"),
        ("G-N champ_timeouts", "`champ_timeouts` == 0 in BOTH cells"),
        ("G-TIMING bar", f"[{TIMING_LO:.2f}, {TIMING_HI:.2f}]"),
        ("G-TIMING-FULL bar", f"[{TIMING_FULL_LO:.2f}, {TIMING_FULL_HI:.2f}]"),
        # READ_RULE writes exponents without the leading zero ("1e-6"); python's
        # `%g` writes "1e-06". Normalised so the audit compares NUMBERS, not
        # formatting — the constant is still the single source.
        ("G-TIMING-FULL rtol", f"{FULL_XCHECK_RTOL:g}".replace("e-0", "e-") + " relative"),
        ("G-TENANCY confirm", f"`TENANCY_CONFIRM_SAMPLES` (={TENANCY_CONFIRM_SAMPLES})"),
        ("G-SAT bar", f"[{SAT_BAND[0]:.2f}, {SAT_BAND[1]:.2f}]"),
        ("burn-in window", f"{N_BURNIN_DECKS}"),
    ):
        rows.append((f"READ_RULE §3 text still carries: {label} ({needle!r})",
                     needle in sec3, "found" if needle in sec3 else "NOT FOUND in §3"))
    return rows


SEC4_SED = "/^## §4 — THE BRANCHES/,/^## §4.3/p"
# READ_RULE §0's own recommended reviewer check, reproduced exactly. ⚠️ This pair's
# §4 is NOT byte-identical to the predecessor's: it ADDS the §4.1 blockquote (the
# burn-in-abort clause). That is an ADDITION and it changes no branch name,
# condition, threshold or licence text — so the audit below asserts the strictly
# checkable property instead: every line of the predecessor's §4 survives, in
# order, and every EXTRA line lives inside the §4.1 blockquote. A CHANGED or
# REMOVED line is a FAIL.
SEC4_ALLOWED_ADDITION_MARKER = "§4.1"


def _section(path: Path, start_prefix: str, end_prefix: str | None) -> list[str]:
    """The `sed -n '/^START/,/^END/p'` range, reproduced in python so the audit is
    portable and does not shell out. `end_prefix=None` means "to end of file"
    (the `$p` form)."""
    txt = Path(path).read_text().splitlines()
    out, on = [], False
    for line in txt:
        if line.startswith(start_prefix):
            on = True
        if on:
            out.append(line)
        if on and end_prefix is not None and line.startswith(end_prefix) \
                and not line.startswith(start_prefix):
            break
    return out


def audit_sections(pred_read_rule: Path) -> list[tuple[str, bool, str, list[str]]]:
    """READ_RULE §0's blindness disclosure makes THREE mechanically checkable
    claims. All three are asserted here, and the realized diff is printed, so a
    reader sees them pass rather than taking anyone's word for it.

      §0 claim 1  — §4's branch names, conditions, thresholds and licence text are
                    BYTE-IDENTICAL to `../track_d2r2_prep/READ_RULE.md` §4.
                    ⚠️ MEASURED: this is TRUE of the five branch blocks and FALSE of
                    the §4 SECTION, which appends a `§4.1` blockquote (the
                    burn-in-abort clause). §0's own recommended reviewer command
                    therefore does NOT come out empty. The audit below asserts the
                    strictly checkable property instead: NOTHING changed or
                    removed, and every ADDED line lives inside the §4.1 block.
      §0 claim 2  — §1, §2, §5 and §6 are likewise VERBATIM. §1 and §6 are checked
                    here as genuine EMPTY-DIFF assertions.
    """
    import difflib
    out: list[tuple[str, bool, str, list[str]]] = []
    if not Path(pred_read_rule).is_file():
        return [("predecessor READ_RULE reachable", False,
                 f"NOT FOUND at {pred_read_rule}", [])]
    mine = HERE / "READ_RULE.md"

    def rng(start, end, label):
        a = _section(pred_read_rule, start, end)
        b = _section(mine, start, end)
        return a, b, list(difflib.unified_diff(a, b, f"d2r2/{label}", f"d2r3/{label}",
                                               lineterm="", n=0))

    # ---- claim 1: §4 --------------------------------------------------------- #
    _a, _b, diff4 = rng("## §4 — THE BRANCHES", "## §4.3", "§4")
    removed = [ln for ln in diff4 if ln.startswith("-") and not ln.startswith("---")]
    added = [ln for ln in diff4 if ln.startswith("+") and not ln.startswith("+++")]
    additions_are_41 = (
        bool(added)
        and all(ln[1:].strip() == "" or ln[1:].lstrip().startswith(">") for ln in added)
        and any(SEC4_ALLOWED_ADDITION_MARKER in ln for ln in added))
    ok4 = (not removed) and (not added or additions_are_41)
    if not diff4:
        note4 = "§4 is BYTE-IDENTICAL to the predecessor's (empty diff)."
    elif ok4:
        note4 = (f"§4: {len(added)} ADDED line(s), ALL inside the §4.1 blockquote "
                 f"(the burn-in-abort clause); 0 changed, 0 removed. ⚠️ FOR THE OWNER: "
                 f"READ_RULE §0's own recommended command "
                 f"`diff <(sed -n '{SEC4_SED}' ../track_d2r2_prep/READ_RULE.md) "
                 f"<(sed -n '{SEC4_SED}' READ_RULE.md)` therefore does NOT come out empty. "
                 f"§0's byte-identity claim is TRUE of the branch blocks and FALSE of the "
                 f"§4 section as a whole.")
    else:
        note4 = ("⛔ §4 DIFFERS beyond an added §4.1 blockquote — a branch name, condition, "
                 "threshold or licence text MOVED. That voids the port's premise.")
    out.append(("§0 claim 1 — §4 branch blocks verbatim (additions confined to §4.1)",
                ok4, note4, diff4))

    # ---- claim 2: §1 and §6, genuine EMPTY-DIFF assertions ------------------- #
    for label, start, end in (
        ("§1", "## §1 — THE STATISTIC", "## §2 — UNITS"),
        ("§6", "## §6 — THE STATED PRIOR", None),
    ):
        _a, _b, d = rng(start, end, label)
        out.append((f"§0 claim 2 — {label} VERBATIM (diff MUST be empty)", not d,
                    f"{label}: {'empty diff' if not d else f'{len(d)} diff line(s) ⛔'}", d))
    return out


# ---- the selftest driver --------------------------------------------------- #
def selftest(fixture_dir: str | None) -> int:
    seed_dir = Path(fixture_dir or DEFAULT_FIXTURE_SEED_DIR)
    mpath = seed_dir / "manifest.json" if seed_dir.is_dir() else seed_dir
    spath = (mpath.parent / "summary.json")
    print("=" * 100)
    print("analyze_d2r3.py --selftest")
    print("=" * 100)
    if not mpath.is_file() or not spath.is_file():
        print()
        print("⛔ SELFTEST REFUSED — NO REAL MANIFEST IS REACHABLE.")
        print(f"   looked for: {mpath}")
        print(f"          and: {spath}")
        print()
        print("   A SYNTHESIZED-ONLY SELFTEST IS NOT ACCEPTABLE FOR THIS PAIR.")
        print("   READ_RULE §3.3 requires the passing fixture to be SEEDED FROM A REAL manifest")
        print("   read off disk. The h2h post-mortem (../h2h_22016_prep/AMENDMENTS.md): 'the")
        print("   selftest fixture generator synthesises the manifest READ_RULE.md describes,")
        print("   rather than one the analyzer of record actually emits. A 20/20 green selftest")
        print("   therefore certified an instrument that could not read any real archive.'")
        print("   Point --fixture-manifest at a real archive of this harness and re-run.")
        return 2
    seed_manifest = json.loads(mpath.read_text())
    seed_summary = json.loads(spath.read_text())
    print(f"fixture SEED (real, off disk): {mpath}")
    print(f"                               {spath}  [KEY SET ONLY — no outcome value is read]")
    print(f"seed manifest kind={seed_manifest.get('kind')!r}, "
          f"config keys={len(flatten(seed_manifest.get('config', {})))}, "
          f"summary keys={len(seed_summary)}")
    print()

    results: list[tuple[str, str, str, bool, str]] = []

    def case(name: str, expect_branch: str, expect_fail: set[str] | None,
             breaker=None, witness_fn=witness_from_disk, **kw):
        tmp = Path(tempfile.mkdtemp(prefix="d2r3_selftest_"))
        try:
            fx = build_fixture(tmp, seed_manifest, seed_summary, **kw)
            if breaker:
                breaker(fx)
            r1600 = fx["r1600"] if fx["r1600"].is_dir() else None
            v = run_analysis(fx["r800"], r1600, fx["root"], fx["prep"],
                             witness_fn=witness_fn)
            got_fail = {g["id"] for g in v["gates"] if g["status"] == "FAIL"}
            ok = (v["branch"] == expect_branch)
            detail = f"branch={v['branch']}"
            if expect_fail is not None:
                ok = ok and (got_fail == expect_fail)
                detail += f", FAILED={sorted(got_fail) or ['none']}"
            else:
                detail += f", FAILED={sorted(got_fail) or ['none']}"
            if expect_branch != "U-UNREADABLE":
                detail += (f", S={v['S']:+.3f}, se={v['se_S']:.3f}, z={v['z_S']:+.3f}"
                           if v["S"] is not None else ", S=None")
            # every branch must render without raising — §4.3 on EVERY branch.
            render_md(v)
            results.append((name, expect_branch,
                            f"{sorted(expect_fail) if expect_fail is not None else 'any'}",
                            ok, detail))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    NONE: set[str] = set()
    # 1 — the all-PASS case (and the D2-COARSE branch).
    case("ALL-PASS / D2-COARSE", "D2-COARSE", NONE, S_target=5.0, se_target=1.5)
    # 2..13 — one single-gate break per gate, twelve of them.
    case("break G-BAND", "U-UNREADABLE", {"G-BAND"}, break_band)
    case("break G-SINGLEVAR (literal: 4th key)", "U-UNREADABLE", {"G-SINGLEVAR"},
         break_singlevar_literal)
    case("break G-PROBE", "U-UNREADABLE", {"G-PROBE"}, break_probe)
    case("break G-RUNG", "U-UNREADABLE", {"G-RUNG"}, break_rung)
    case("break G-LEAF", "U-UNREADABLE", {"G-LEAF"}, break_leaf)
    case("break G-RULES", "U-UNREADABLE", {"G-RULES"}, break_rules)
    case("break G-TOOL", "U-UNREADABLE", {"G-TOOL"}, break_tool)
    case("break G-N (champ_timeouts=1)", "U-UNREADABLE", {"G-N"}, break_n)
    case("break G-TIMING (burn-in below floor)", "U-UNREADABLE", {"G-TIMING"}, break_timing)
    case("break G-TIMING-FULL", "U-UNREADABLE", {"G-TIMING-FULL"}, break_timing_full)
    case("break G-TENANCY", "U-UNREADABLE", {"G-TENANCY"}, break_tenancy)
    case("break G-SAT", "U-UNREADABLE", {"G-SAT"}, break_sat)
    # extra coverage the twelve do not reach
    case("break G-SINGLEVAR (alias mirror drift)", "U-UNREADABLE", {"G-SINGLEVAR"},
         break_singlevar_alias)
    case("break G-TIMING (live watcher disagrees)", "U-UNREADABLE", {"G-TIMING"},
         break_timing_live_disagree)
    # 14 — the §1 WITNESS disagreement case.
    def bad_witness(a, b):
        w = witness_from_disk(a, b)
        w["S"] = (w["S"] or 0.0) + 1.0
        return w
    case("§1 WITNESS disagrees", "U-UNREADABLE", NONE, witness_fn=bad_witness)
    # 15..18 — one case per §4 branch.
    case("branch D2-COMPRESSED", "D2-COMPRESSED", NONE, S_target=1.5, se_target=0.40)
    case("branch D2-BOUNDED-NULL", "D2-BOUNDED-NULL", NONE, S_target=0.0, se_target=1.0)
    case("branch D2-REVERSED", "D2-REVERSED", NONE, S_target=-6.0, se_target=1.0)
    case("branch U-UNREADABLE (§4.1: no R1600 cell)", "U-UNREADABLE",
         {"G-BAND", "G-SINGLEVAR", "G-RUNG", "G-TOOL", "G-N"}, break_no_r1600)

    print("-" * 118)
    print(f"{'#':<3} {'case':<44} {'expect branch':<17} {'expect FAIL':<28} {'ok':<4} realized")
    print("-" * 118)
    n_bad = 0
    for i, (name, eb, ef, ok, detail) in enumerate(results, 1):
        if not ok:
            n_bad += 1
        print(f"{i:<3} {name:<44} {eb:<17} {ef[:27]:<28} {'✅' if ok else '⛔':<4} {detail}")
    print("-" * 118)
    print(f"fixture cases: {len(results) - n_bad}/{len(results)} as expected")
    print()

    # ---- audit A: constants are IMPORTED, not re-typed --------------------- #
    print("AUDIT A — constant parity with `d2r3_lib` + READ_RULE §3 literals")
    print("-" * 118)
    a_bad = 0
    for label, ok, note in audit_constants():
        if not ok:
            a_bad += 1
        print(f"  {'✅' if ok else '⛔'} {label:<86} {note}")
    print()

    # ---- audit B: the mechanical BLINDNESS audit (§4, §1, §6) -------------- #
    print("AUDIT B — READ_RULE.md vs ../track_d2r2_prep/READ_RULE.md "
          "(the pair's mechanical blindness audit, READ_RULE §0)")
    print("-" * 118)
    pred = REPO / "measurement" / "track_d2r2_prep" / "READ_RULE.md"
    b_bad = 0
    for label, ok, note, diff in audit_sections(pred):
        if not ok:
            b_bad += 1
        print(f"  {'✅' if ok else '⛔'} {label}")
        print(f"     {note}")
        if diff:
            print("     --- unified diff (n=0) ---")
            for ln in diff:
                print("       " + ln)
    print()

    # ---- audit C: the SMOKE leg cannot spuriously block a launch ----------- #
    # The h2h standing rule is only useful if a HEALTHY single-cell archive
    # clears every BLOCKING gate. This audit proves it: run the smoke verdict
    # over one cell of the all-PASS fixture and require an EMPTY blocking set.
    # (The blocking gates read manifest/summary STRUCTURE only, never n or the
    #  band, so a 200-deck fixture cell is a faithful stand-in for a 16-game one
    #  on exactly the propositions that block.)
    print("AUDIT C — the smoke leg's blocking set is EMPTY on a healthy single-cell archive")
    print("-" * 118)
    c_ok = True

    def smoke_case(label: str, prep_blind: str, strip_stamp: bool):
        nonlocal c_ok
        tmp = Path(tempfile.mkdtemp(prefix="d2r3_selftest_smoke_"))
        try:
            fx = build_fixture(tmp, seed_manifest, seed_summary)
            (fx["prep"] / "BLIND_COMMIT").write_text(prep_blind + "\n")
            if strip_stamp:
                m = _load(fx["r800"] / "manifest.json")
                m.pop("BLIND_COMMIT", None)
                m.get("config", {}).pop("stamps", None)
                _save(fx["r800"] / "manifest.json", m)
            sv = run_analysis(fx["r800"], None, fx["root"], fx["prep"], smoke=True)
            blockers = [g["id"] for g in sv["gates"]
                        if g.get("smoke_status", g["status"]) == "FAIL"
                        and g["id"] not in SMOKE_ALLOWED_FAILURES]
            alias = next(g for g in sv["gates"] if g["id"] == "G-SINGLEVAR")
            if alias.get("alias_reading_status") != "PASS":
                blockers.append("G-SINGLEVAR/alias")
            allowed = [g["id"] for g in sv["gates"]
                       if g.get("smoke_status", g["status"]) == "FAIL"]
            ok = not blockers
            c_ok = c_ok and ok
            print(f"  {'✅' if ok else '⛔'} {label}")
            print(f"     blocking failures: {blockers or 'NONE'}   "
                  f"(allowed-set failures, as designed: {allowed})")
            if not ok:
                print("     ⛔ A HEALTHY SMOKE WOULD BLOCK THE LAUNCH — that is the §3.1 "
                      "defect class in the smoke leg itself, and must be fixed BEFORE game 1.")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    smoke_case("healthy single-cell archive, BLIND_COMMIT already stamped",
               FIXTURE_BLIND, strip_stamp=False)
    # ⚠️ THE REALISTIC SHAPE. `run_cells.sh` runs the smoke leg BEFORE the freeze
    # ceremony stamps the sha, and documents the smoke as exempt from the blind
    # precondition — so at smoke time the frozen file still reads
    # `PLACEHOLDER_BLIND_COMMIT_NOT_YET_STAMPED` and the archive carries no stamp.
    smoke_case("realistic PRE-FREEZE smoke: placeholder BLIND_COMMIT file, unstamped archive",
               "PLACEHOLDER_BLIND_COMMIT_NOT_YET_STAMPED", strip_stamp=True)
    print()

    total_bad = n_bad + a_bad + b_bad + (0 if c_ok else 1)
    print("=" * 118)
    if total_bad:
        print(f"⛔ SELFTEST FAILED — {total_bad} mismatch(es).")
    else:
        print(f"✅ SELFTEST PASSED — {len(results)} fixture cases, "
              f"{len(audit_constants())} constant/READ_RULE audits, blindness audit OK, "
              "smoke-leg audit OK.")
        print("   The passing fixture was SEEDED FROM A REAL manifest read off disk "
              f"({mpath}),")
        print("   not synthesized from READ_RULE's prose — the h2h post-mortem's house fix.")
    print("=" * 118)
    return 1 if total_bad else 0


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cell-r800", help="CELL R800 archive directory")
    ap.add_argument("--cell-r1600", default=None,
                    help="CELL R1600 archive directory (omit on a burn-in-aborted pair; "
                         "READ_RULE §4.1 then suppresses S entirely)")
    ap.add_argument("--out-root", default=None,
                    help="the run's output root — where BURNIN_R800.json and "
                         "TENANCY_R*.jsonl live (default: the parent of --cell-r800)")
    ap.add_argument("--prep-dir", default=str(PAIR_DIR),
                    help="the pair directory holding the launcher's frozen BLIND_COMMIT file")
    ap.add_argument("--md", default=str(PAIR_DIR / "READOUT_D2R3.md"))
    ap.add_argument("--json", default=str(PAIR_DIR / "READOUT_D2R3.json"))
    ap.add_argument("--stdout-only", action="store_true",
                    help="print the markdown readout, write nothing")
    ap.add_argument("--smoke-mode", action="store_true",
                    help="adjudicate a single 16-game smoke archive; exit 0 iff the only "
                         "failing gates are in SMOKE_ALLOWED_FAILURES")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--fixture-manifest", default=None,
                    help="directory (or manifest.json path) of a REAL archive to seed the "
                         f"--selftest fixture from (default {DEFAULT_FIXTURE_SEED_DIR})")
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.fixture_manifest)

    if not args.cell_r800:
        ap.error("--cell-r800 is required (or use --selftest)")
    cell800 = Path(args.cell_r800)
    out_root = Path(args.out_root) if args.out_root else cell800.parent

    if args.smoke_mode:
        return smoke_mode(cell800, Path(args.prep_dir))

    if not args.cell_r1600:
        print("[analyze_d2r3] ⚠️ --cell-r1600 not given: adjudicating a SINGLE-CELL archive. "
              "READ_RULE §4.1 — no `S` will be computed.", file=sys.stderr)
    v = run_analysis(cell800,
                     Path(args.cell_r1600) if args.cell_r1600 else None,
                     out_root, Path(args.prep_dir))
    md = render_md(v)
    print(md)
    if not args.stdout_only:
        Path(args.md).write_text(md)
        Path(args.json).write_text(json.dumps(v, indent=2, default=str))
        print(f"[analyze_d2r3] wrote {args.md}")
        print(f"[analyze_d2r3] wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
