#!/usr/bin/env python3
"""Adjudicate `measurement/tiearb_widening_20260817/b64_cell/READ_RULE.md` — the
`B = 64` GAME cell.

Two cells, `WIDE` (`B` = 64) and `NARROW` (`B` = 16), `J` = 4, mode `argmax`,
salt `tiearb2-deploy-v1`, `n` = 1,500 deck-paired games each on ONE fresh band,
at production budget k8x1376, against the unmodified champion.

    M_w, M_n   = summary.json::paired_mean_margin   ⚠️ READ, NEVER RECOMPUTED
    z_w, z_n   = summary.json::paired_z             secondary, adjudicates nothing
    D          = M_w − M_n, DECK-PAIRED over the decks completed in BOTH cells
    z_D        = D / se(D)  — ⭐ THE PRIMARY, computed exactly as `paired_z` is
    f0         = fraction of common decks with D_i EXACTLY 0.0  (G-DIVERGE)

then evaluates §3's preconditions (which VOID the run), fires §4's branch table in
the committed order, and writes `READOUT_B64.{json,md}` carrying every item of the
mandatory companion table §4.3.

⚠️ NOTHING HERE INVENTS AN ESTIMATOR. The paired arithmetic, the two-level manifest
resolution, the phi/arbiter-error blocks and the record loader are IMPORTED from
`analyze_tiearb2_stage2` — Stage 2's adjudicator, whose conventions this pair
inherits by reference. A second convention for `z` would make the three z's
incomparable, which is the one thing §2 forbids.

⚠️ THE PAIR IS FROZEN. Where the spec and the buildable disagree, this tool REPORTS
the mismatch (`spec_vs_buildable`) and adjudicates nothing on it. It never resolves
a disagreement by changing what the pair says.

MODES
    adjudicate   the read-out (default)
    knowngood    ⭐ THE LAUNCH PRECONDITION (DESIGN §13.1): evaluate every §3 row
                 against Stage 2's COMPLETED artifacts and classify each
                 PASS / FAIL / N-A(reason). A row that fails a known-good run is a
                 drafting defect — this campaign's THIRD unsatisfiable-gate catch
                 (`G-TOOL`) was found exactly this way. ⚠️ A row that cannot be
                 evaluated is NAMED `N-A`, never silently counted as covered.
    nest-witness emit `GATE_NEST.json` — the §1.3 structural witness, read off the
                 seeding source at HEAD.
    smoke-check  validate a `SMOKE.json` against §9.2's FAIL-CLOSED whitelist.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# ⚠️ imported, never re-implemented — see the module docstring
import analyze_tiearb2_stage2 as S2  # noqa: E402

CELL_DIR = REPO / "measurement" / "tiearb_widening_20260817" / "b64_cell"
STAGE2_DIR = REPO / "measurement" / "tiearb2_stage2_20260817"

CELLS = ("WIDE", "NARROW")
B_BY_CELL = {"WIDE": 64, "NARROW": 16}
J_EXPECTED = 4
MODE_EXPECTED = "argmax"
SALT_EXPECTED = "tiearb2-deploy-v1"
EPS_EXPECTED = 0.0
CHAMP_LEAF_HASH = S2.CHAMP_LEAF_HASH

# ---- §2 bars, and they are not new constants ------------------------------- #
Z_BAR = 2.0            # Stage 1 / 1b / Stage 2 Phase B / E-FLAT / W-FLAT, verbatim
Z_PRESENT = 1.0        # Stage 2 Phase B's presentation split — NOT an adjudicating bar

# ---- §3 floors ------------------------------------------------------------- #
N_COMMON_FLOOR = 600           # DECKS
CELL_GAMES_FLOOR = 1200        # games (the SAME 80% bar: 1,200 games IS 600 decks)
CELL_GAMES_PLANNED = 1500
PHI_EFFECTIVE_FLOOR = 1.0      # G-FIRE
DIVERGE_FLOOR = 0.10           # G-DIVERGE, on 1 − f0
DIVERGE_EXPECTED = 1.0         # ⭐ ≈1.0 — printed BESIDE the realized on every branch
FAILED_RATE_BAR = 0.02         # G-FAILED clause 1
KNOWN_FAILURE_CLASS = "WindowTruncationError"

# ---- §4 cost constants — COMMITTED ARITHMETIC, not measurements to come ----- #
RHO_WALL_16 = 0.6224           # Phase A, measured
RHO_WALL_64 = 2.4897           # ×4, exact linearity in B
RHO_WALL_32 = 1.2449           # ⚠️ ALSO exceeds the bar, by 3.7%
N4_BAR = 1.20
RHO_PHONE_64 = (23.90, 22.08)  # NOT SOLVED, a third currency
SE_D_COMMITTED = 0.7133        # §6.2
D_FLOOR_2SIGMA = 1.427         # §6.2, at rho = 0
EFFECT_BRACKET = (0.368, 1.435)  # §5.2
WORKER_S_COMMITTED = {"WIDE": 958.794, "NARROW": 429.612}   # §7.2
MS_RATIO_PREDICTED = {"WIDE": 6.50, "NARROW": 2.42}          # §9.4
PHI_PRIOR_OFFLINE = 22.96
PHI_STAGE2_REALIZED = (17.5725, 17.865)
WALL_COMMITTED_H = 13.24       # §7.4

#: §4.0.1 conjunct 3 — the COMMITTED pattern. Matched, never interpreted.
WAIVER_REGEX = re.compile(
    r'^> OWNER WAIVER \(N4 rho_wall, B > 16\), (20[0-9]{2}-[01][0-9]-[0-3][0-9]): "(.+)"$')
WAIVER_FILE = "OWNER_WAIVER.md"

#: §9.2's FAIL-CLOSED whitelist. An unlisted key is a REFUSAL, not a warning.
SMOKE_WHITELIST = frozenset({
    "wall_secs", "secs_per_game", "worker_secs_per_game", "games_per_sec",
    "workers", "champ_prefix_ms_per_move", "rung_ms_per_move",
    "ms_ratio_cand_over_opp", "tiearb_phi", "tiearb_fired_plies_total",
    "tiearb_tile_plies_total", "tiearb_fire_rate_on_tile_plies",
    "tiearb_pickchange_rate", "tiearb_mean_arms", "tiearb_playouts_total",
    "tiearb_secs_per_game", "tiearb_errors_total", "tiearb_first_error",
    "tiearb_partial_argmax_total", "cand_leaf_hash", "carc_rs_build",
    "carc_rs_binary_sha", "rust_toolchain", "n_failed",
    # §9.1's condition of acceptance — the throwaway band declares itself
    "band_seed_start", "band_tier", "band_registry_claimed",
})
#: ⛔ THE OUTCOME KEYS §9.2 forbids outright. ⚠️ `f0` is MARGIN-DERIVED and is
#: forbidden at the smoke — named so a well-meaning implementation cannot add it
#: "because it's just a count".
SMOKE_FORBIDDEN_EXAMPLES = ("paired_mean_margin", "paired_z", "elo", "winrate",
                            "W", "D", "L", "f0", "z_D", "per_deck_margin")
SMOKE_OUTCOME_FORBIDDEN = frozenset({
    "paired_mean_margin", "paired_z", "elo", "elo_sig_1sigma", "winrate",
    "winrate_z", "wr", "wr_z", "W", "D", "L", "f0", "z_D", "se_D",
    "per_deck_margin", "by_deck", "margins", "diff",
})
#: A key whose NAME says outcome even under a house suffix. Matched on the whole
#: key, so a counts key that merely contains "margin" as a word-part is not swept
#: up by accident.
SMOKE_OUTCOME_RE = re.compile(
    r"(?:^|_)(margin|elo|winrate|wr_z|paired_z|z_D|f0)(?:$|_)", re.I)
SMOKE_HALT_MULTIPLE = 1.50     # §9.3, one-sided

#: §9.3's bar, derived rather than typed twice.
SMOKE_HALT_BAR = SMOKE_HALT_MULTIPLE * WORKER_S_COMMITTED["WIDE"]

#: The four seeding sites §1.3 rests on. The nesting is true IFF none of them
#: takes `B` — the seed is a pure function of `j`.
TIEARB_RS = "rust/carc/carc-core/src/tiearb.rs"
NEST_SITES = (
    ("world_seed", r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*&js\]\)'),
    ("playout_seed",
     r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*&js,\s*"playout"\]\)'),
    ("build_arms_cap",
     r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*"cap"\]\)'),
    ("select_stream",
     r'seed_i64\(&\[salt,\s*digest,\s*&ply\.to_string\(\),\s*"select"\]\)'),
)

BRANCH_ORDER = ("U-UNREADABLE", "B-REVERSED", "B-CONFIRMED", "B-COSTKILL",
                "B-PRESENT", "B-FLAT")

BRANCH_TEXT = {
    "B-REVERSED": (
        "⛔ WIDENING THE SELECTION WORLDS FROM 16 TO 64 MAKES THE ARBITER WORSE IN "
        "GAMES, AT 2σ, ON A FRESH BAND.",
        "MANDATORY RIDER, never separated from the verdict: this is a DIRECT TENSION "
        "with the offline W-RISING read (Δ(16→64) = +0.0670, CI95 [+0.0215, +0.1111], "
        "z +2.94, n 1,340 plies / 748 roots, committed floor +0.04). Print both, and "
        "do NOT present the tension as resolved. The offline read stands as "
        "adjudicated and this branch does not re-adjudicate it; what it establishes "
        "is that the offline→game map fails in THIS direction too, which is a "
        "first-class finding about the map. Nothing closes and nothing is licensed; "
        "the deployed B = 16 shape is untouched, and this branch DOES license a "
        "decision for the owner TO LEAVE IT UNTOUCHED."),
    "B-CONFIRMED": (
        "⭐ WIDENING TO B = 64 BUYS GAME POINTS OVER THE DEPLOYED ARBITER, RESOLVED "
        "AT 2σ ON A FRESH BAND, AT A RUNG THE OWNER HAS RULED AFFORDABLE.",
        "⛔ UNREACHABLE UNLESS W IS TRUE (§4.0). Licenses (does NOT do) exactly one "
        "thing: a production-flip DECISION for the owner, from B = 16 to B = 64, put "
        "to him carrying the realized ms_ratio_w at its true magnitude, rho_wall(64) "
        "= 2.4897 against the N4 bar of 1.20, and rho_phone(64) ∈ {23.90, 22.08} "
        "labelled NOT SOLVED. It does not flip PRODUCTION.yaml, does not license an "
        "on-device deploy, does not license a leaf term, does not resolve the "
        "ladder's shape, and does not license a second cell."),
    "B-COSTKILL": (
        "⛔ THE WIDENING WINS AND THE RUNG IS UNAFFORDABLE — A WIN THAT CANNOT BE "
        "BOUGHT.",
        "⭐ THE EXPECTED BRANCH ON A WIN (§4.0). z_D ≥ +2.0, and rho_wall(64) = "
        "2.4897, 2.07× the house N4 bar of 1.20, with no owner waiver on the record "
        "predating game 1. LICENSES NOTHING DEPLOYABLE. It licenses exactly two "
        "things, both needing a fresh preregistration or a fresh owner ruling: (i) a "
        "fresh owner wall-clock ruling on whether the N4 bar moves above B = 16; and "
        "(ii) a ladder question this cell DID NOT MEASURE in game points and which no "
        "branch may infer from two points. ⛔ AND THE LADDER IS NOT A CHEAPER ROUTE: "
        "rho_wall(32) = 1.2449 ALSO EXCEEDS 1.20 (by 3.7%), so a B = 32 win would "
        "ALSO be B-COSTKILL. ⛔ On-device is dead at this rung regardless "
        "(rho_phone(64) ≈ 24, a third currency, out of scope)."),
    "B-PRESENT": (
        "PRESENT BUT NOT CONVICTED — UNRESOLVED.",
        "The direction is there and the bar is not met. Nothing closes and nothing is "
        "licensed. Report both cells, D, se_D, z_D, rho, f0, both phi, both ms_ratio, "
        "and the n that would convict at the REALIZED dispersion — printed beside "
        "DESIGN §6.3's pre-registered figure so the reader can see whether the "
        "dispersion model held."),
    "B-FLAT": (
        "WIDENING FROM 16 TO 64 DID NOT EXPRESS AS DECK-PAIRED GAME POINTS AT "
        "n = 1,500 PER CELL ON A FRESH BAND.",
        "MANDATORY SCOPE SENTENCE, quoted with the verdict and never separated from "
        "it: \"This is a BOUNDED null, not an exclusion, and it does NOT refute "
        "W-RISING. DESIGN §6.2 states before the run that n = 1,500 deck-paired per "
        "cell resolves a 2σ floor of +1.427 pts/game at ρ = 0, while §5.2's "
        "pre-registered effect bracket is [+0.368, +1.435] pts/game — a 3.9× band "
        "whose lower ~74% this cell cannot reach. Convicting the naive floor (+0.368) "
        "needs n ≈ 22,540 games/cell ≈ 8,693 worker-h. The honest claim is 'widening "
        "B from 16 to 64 did not express as deck-paired game points at n = 1,500 on "
        "this band', NOT 'widening is worth nothing'. W-RISING is an OFFLINE "
        "per-tied-ply read on a different corpus in a different currency, it stands "
        "as adjudicated, and this branch does not re-adjudicate it.\""),
    "U-UNREADABLE": (
        "U-UNREADABLE — A §3 PRECONDITION FAILED.",
        "Report cost, integrity, firing rates, divergence, the failed-record "
        "accounting, and WHICHEVER GATE(S) FAILED — all of them, never "
        "short-circuited at the first. Nothing closes, nothing is licensed, nothing "
        "is re-labelled."),
}


def _f(x, spec="+.4f"):
    try:
        return format(float(x), spec)
    except (TypeError, ValueError):
        return "n/a"


# --------------------------------------------------------------------------- #
# §4.0.1 — `W`, mechanical in all three conjuncts                              #
# --------------------------------------------------------------------------- #
def _git_commit_epoch(path, repo=REPO):
    """The file's git commit timestamp (epoch seconds), or None if untracked."""
    import subprocess
    r = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%ct", "--",
                        str(path)], capture_output=True, text=True)
    out = (r.stdout or "").strip()
    return int(out) if r.returncode == 0 and out.isdigit() else None


def waiver_predicate(cell_dir=CELL_DIR, band_claim_path=None, repo=REPO) -> dict:
    """§4.0.1 `W` — TRUE iff EXISTENCE ∧ ORDERING ∧ CONTENT. Fail-closed.

    ⚠️ Conjunct 3 is what makes `W` mechanical rather than a human judgement
    wearing a file check's clothes: the pattern is matched, the quote is NOT read
    for meaning. Composing a conforming line is the OWNER's act, never the
    adjudicator's.
    """
    p = Path(cell_dir) / WAIVER_FILE
    out = {"W": False, "file": str(p), "conjuncts": {
        "existence": False, "ordering": False, "content": False},
        "captured_date": None, "captured_quote": None,
        "regex": WAIVER_REGEX.pattern,
        "why": "no OWNER_WAIVER.md — W is FALSE (fail-closed)"}
    if not p.is_file():
        return out
    # ⚠️ ALL THREE conjuncts are evaluated, never short-circuited: the read-out
    # prints the captured date and quote on every branch, and a reader must be
    # able to see WHICH conjunct failed rather than only that W is false.
    tracked = _git_commit_epoch(p, repo)
    out["waiver_commit_epoch"] = tracked
    out["conjuncts"]["existence"] = tracked is not None   # exists AND is tracked

    claim_epoch = None
    if band_claim_path and Path(band_claim_path).is_file():
        claim_epoch = _git_commit_epoch(band_claim_path, repo)
        if claim_epoch is None:
            try:
                claim_epoch = int(Path(band_claim_path).stat().st_mtime)
            except OSError:
                claim_epoch = None
    out["band_claim_epoch"] = claim_epoch
    out["conjuncts"]["ordering"] = bool(
        claim_epoch is not None and tracked is not None and tracked < claim_epoch)

    for line in p.read_text().splitlines():
        m = WAIVER_REGEX.match(line)
        if m:
            out["conjuncts"]["content"] = True
            out["captured_date"], out["captured_quote"] = m.group(1), m.group(2)
            break

    out["W"] = all(out["conjuncts"].values())
    out["why"] = ("all three conjuncts hold" if out["W"] else
                  "FALSE — " + ", ".join(k for k, v in out["conjuncts"].items()
                                         if not v) + " absent (fail-closed)")
    return out


def reachable_branches(W: bool) -> dict:
    """§4.0 — the reachable set, stated as a SET before the run.

    ⚠️ An unreachable headline branch must be visible BEFORE the run, not
    discovered in the read-out (the Stage-2 `G-N` lesson applied prospectively)."""
    if W:
        return {"W": True, "reachable": list(BRANCH_ORDER), "unreachable": [],
                "note": "a conforming, pre-dated OWNER_WAIVER.md is on the record"}
    return {
        "W": False,
        "reachable": ["B-REVERSED", "B-COSTKILL", "B-PRESENT", "B-FLAT",
                      "U-UNREADABLE"],
        "unreachable": ["B-CONFIRMED"],
        "note": "⛔ B-CONFIRMED is UNREACHABLE: A is decided entirely by W, and "
                "rho_wall(64) = 2.4897 > 1.20 makes A's first disjunct FALSE "
                "before game 1. A z_D ≥ +2.0 win fires B-COSTKILL and licenses "
                "nothing deployable.",
    }


# --------------------------------------------------------------------------- #
# §3 — the preconditions. Each a pure function so a test can fail exactly one.  #
# --------------------------------------------------------------------------- #
def gate_j1(cells: dict) -> tuple:
    """`G-J1` `[PER-CELL]` — INVERTED: a DIFFERENCE from the champion's leaf hash
    is an ABORT, not a finding."""
    obs, ok = {}, True
    for c in CELLS:
        h, where = S2._manifest_get((cells.get(c) or {}).get("manifest", {}),
                                    "cand_leaf_hash")
        obs[c] = {"cand_leaf_hash": h, "resolved_at": where}
        ok &= (h == CHAMP_LEAF_HASH)
    return bool(ok), {"expected_equal": CHAMP_LEAF_HASH, "observed": obs,
                      "read_at": "top level, then config.* (two-level, §2)",
                      "semantics": "EQUALITY gate — a difference ABORTS; ABSENT "
                                   "under both levels also fails"}


def gate_j4(cells: dict, b_by_cell=None) -> tuple:
    """`G-J4` `[PER-CELL]` — the resolved knob is EXACTLY the deployed shape with
    only `B` differing, and the cell's realized `tiearb_B` is the SINGLETON `[B]`.

    ⚠️ A mixed-`B` cell is a VOID, not a finding."""
    b_by_cell = b_by_cell or B_BY_CELL
    obs, ok = {}, True
    for c in CELLS:
        m = (cells.get(c) or {}).get("manifest", {})
        s = (cells.get(c) or {}).get("summary", {})
        cfg, where = S2._tiearb_cfg(m)
        want = {"enabled": True, "B": b_by_cell[c], "J": J_EXPECTED,
                "mode": MODE_EXPECTED, "salt": SALT_EXPECTED, "eps": EPS_EXPECTED}
        cfg_ok = isinstance(cfg, dict) and all(
            cfg.get(k) == v for k, v in want.items())
        sing_b = s.get("tiearb_B")
        sing_j = s.get("tiearb_J")
        modes = s.get("tiearb_modes")
        realized_ok = (sing_b == [b_by_cell[c]] and sing_j == [J_EXPECTED]
                       and modes == [MODE_EXPECTED])
        obs[c] = {"resolved_at": where, "cand_tiearb": cfg, "expected": want,
                  "config_ok": bool(cfg_ok), "tiearb_B": sing_b,
                  "tiearb_J": sing_j, "tiearb_modes": modes,
                  "singletons_ok": bool(realized_ok),
                  "ok": bool(cfg_ok and realized_ok)}
        ok &= obs[c]["ok"]
    return bool(ok), {"observed": obs,
                      "semantics": "a mixed-B cell is a VOID, not a finding"}


#: ⚠️ The pair requires the control at BOTH `B` values per host but NAMES NO
#: ADDRESS for `B` inside the preflight file. Resolution order, documented rather
#: than guessed, and an unreadable `B` is ABSENT (which fails) — never coerced.
PREFLIGHT_B_PATHS = ("B", "j13_witness.B", "expected.B", "tiearb.B")


def _preflight_B(doc: dict):
    for dotted in PREFLIGHT_B_PATHS:
        cur = doc
        for part in dotted.split("."):
            cur = cur.get(part) if isinstance(cur, dict) else None
            if cur is None:
                break
        if cur is not None:
            return cur
    return None


def gate_j13(preflights: list, expect_hosts=("Doctor", "laptop-wsl"),
             expect_b=(64, 16)) -> tuple:
    """`G-J13` `[PER-CELL]`/`[pre-run]` — the TWO-SIDED positive control passed on
    EACH host, at BOTH `B` values, BEFORE that host's game 1: the arbiter must
    CHANGE THE PICK at a constructed tied ply AND leave `root_leaf_value_bits`
    UNCHANGED. ⚠️ Absent file ⇒ fail."""
    by_host = {}
    for d in preflights or ():
        host = d.get("host") or d.get("hostname")
        b = _preflight_B(d)
        changed, unchanged = S2._j13_sides(d)
        by_host.setdefault(str(host), {})[str(b)] = {
            "pick_changed": changed, "leaf_bits_unchanged": unchanged,
            "two_sided_ok": bool(changed and unchanged),
            "source": d.get("_path")}
    ok = True
    detail = {}
    for host in expect_hosts:
        rows = by_host.get(host, {})
        per_b = {}
        for b in expect_b:
            r = rows.get(str(b))
            per_b[str(b)] = r or {"two_sided_ok": False, "why": "ABSENT"}
            ok &= bool((r or {}).get("two_sided_ok"))
        detail[host] = per_b
    return bool(ok), {"by_host": detail, "expected_hosts": list(expect_hosts),
                      "expected_B": list(expect_b),
                      "semantics": "two-sided (pick CHANGES, leaf bits DO NOT), "
                                   "per host AND per B value; absent ⇒ fail"}


def nest_witness(repo=REPO) -> dict:
    """⭐ `G-NEST`'s structural witness, read off the seeding source at HEAD.

    §1.3: `world_seed(j) = seed_i64([salt, digest, ply, j])` and
    `playout_seed(j) = …, j, "playout"`, with `j` running `0..B` — **the seed is a
    pure function of `j`, never of `B`.** ⇒ `B` = 64's worlds 0..15 are
    byte-identical to `B` = 16's entire world set, and the `build_arms` cap draw
    and the selection stream likewise do not depend on `B`.

    ⚠️ Without nesting, `WIDE` and `NARROW` are two unrelated draws and the whole
    "increment" framing is void — which is why this is a precondition, not a rider.
    """
    src_path = Path(repo) / TIEARB_RS
    out = {"source": TIEARB_RS, "present": src_path.is_file(), "sites": {},
           "witness": False}
    if not src_path.is_file():
        out["why"] = f"{TIEARB_RS} absent — the witness cannot be taken"
        return out
    src = src_path.read_text()
    ok = True
    for name, pattern in NEST_SITES:
        m = re.search(pattern, src)
        found = bool(m)
        expr = m.group(0) if m else None
        # the load-bearing property: the seed expression takes NO `B` term
        b_free = bool(found and not re.search(r'\bB\b|\bb_worlds\b|&b\b', expr))
        out["sites"][name] = {"found": found, "expression": expr,
                              "b_free": b_free}
        ok &= (found and b_free)
    out["witness"] = bool(ok)
    out["why"] = ("every seeding site is a pure function of j (no B term) ⇒ the "
                  "world sets NEST" if ok else
                  "a seeding site is absent or takes B — the nesting does NOT hold")
    out["scope"] = ("SOURCE-LEVEL witness at HEAD over the four seeding sites. "
                    "The pair's GATE_NEST.json additionally records the pinned "
                    "position/ply/salt byte-identity run; this tool emits the "
                    "structural half and names the behavioural half.")
    return out


def gate_nest(gate_nest_doc) -> tuple:
    """`G-NEST` `[RUN]`/`[pre-run]` — `GATE_NEST.json` absent, or its witness
    false, voids the run."""
    if not isinstance(gate_nest_doc, dict):
        return False, {"present": False,
                       "why": "GATE_NEST.json ABSENT — absence is a FAIL, never a "
                              "pass (§3)"}
    w = gate_nest_doc.get("witness")
    return bool(w is True), {"present": True, "witness": w,
                             "sites": gate_nest_doc.get("sites"),
                             "why": gate_nest_doc.get("why")}


def gate_fire(cells: dict) -> tuple:
    """`G-FIRE` `[PER-CELL]` — `phi_effective < 1.0` in either cell means the
    arbitration surface is inert and the cell grades a champion-vs-champion null
    wearing the shape of a real cell."""
    obs, ok = {}, True
    for c in CELLS:
        cell = cells.get(c) or {}
        phi = (cell.get("phi") or {}).get("phi") if isinstance(cell.get("phi"), dict) \
            else cell.get("phi")
        err = (cell.get("summary") or {}).get("tiearb_error_rate_on_fired")
        eff = S2.phi_effective(phi, err)
        good = eff is not None and eff >= PHI_EFFECTIVE_FLOOR
        obs[c] = {"phi": phi, "error_rate_on_fired": err, "phi_effective": eff,
                  "floor": PHI_EFFECTIVE_FLOOR, "ok": bool(good)}
        ok &= good
    return bool(ok), obs


def f0_block(wide_by_deck: dict, narrow_by_deck: dict) -> dict:
    """`f0` — the fraction of COMMON decks whose `D_i` is EXACTLY 0.0, and the
    §4.3 item 3 divergence block.

    ⚠️ MEASUREMENT DISCLOSURE, carried: `f0` is measured as "`D_i` exactly 0.0",
    which OVERCOUNTS identity (two different games can coincide on margin) ⇒
    `1 − f0` UNDERCOUNTS divergence ⇒ **the floor is CONSERVATIVE**: it can only
    fire early, never late.
    """
    common = sorted(set(wide_by_deck) & set(narrow_by_deck))
    n = len(common)
    identical = sum(1 for s in common
                    if (wide_by_deck[s] - narrow_by_deck[s]) == 0.0)
    f0 = (identical / n) if n else None
    one_minus = (1.0 - f0) if f0 is not None else None
    dilution = math.sqrt(one_minus) if one_minus not in (None,) and one_minus >= 0 \
        else None
    return {
        "f0": f0, "one_minus_f0": one_minus, "n_common_decks": n,
        "n_identical_decks": identical,
        "floor": DIVERGE_FLOOR, "expected_one_minus_f0": DIVERGE_EXPECTED,
        "headroom_x": (DIVERGE_EXPECTED / DIVERGE_FLOOR),
        "dilution_sqrt_one_minus_f0": dilution,
        "anomaly": bool(one_minus is not None
                        and one_minus >= DIVERGE_FLOOR
                        and one_minus < 0.5 * DIVERGE_EXPECTED),
        "anomaly_note": ("⚠️ A realized 1 − f0 materially below ≈1.0 that still "
                         "clears 0.10 is an ANOMALY and must be reported as one, "
                         "never as a pass."),
        "measurement_disclosure": (
            "f0 is measured as 'D_i exactly 0.0', which OVERCOUNTS identity (two "
            "different games can coincide on margin) ⇒ 1 − f0 UNDERCOUNTS "
            "divergence ⇒ the floor is CONSERVATIVE: it can only fire early, "
            "never late."),
        "nested_crn": ("B = 64's worlds 0..15 are byte-identical to B = 16's "
                       "entire world set (DESIGN §1.3); WIDE is a strict "
                       "refinement of NARROW, so a large identical fraction is a "
                       "POWER LOSS (z_D ∝ √(1−f0)), not a power win."),
    }


def gate_diverge(fb: dict) -> tuple:
    """`G-DIVERGE` `[RUN]` — `1 − f0 < 0.10` voids: the widening surface is inert
    relative to the deployed one."""
    v = fb.get("one_minus_f0")
    ok = v is not None and v >= DIVERGE_FLOOR
    return bool(ok), {**{k: fb.get(k) for k in
                         ("f0", "one_minus_f0", "n_common_decks",
                          "n_identical_decks", "expected_one_minus_f0",
                          "anomaly")},
                      "floor": DIVERGE_FLOOR,
                      "why": ("inert: ≥90% of the paired sample contributes exactly "
                              "zero to D by construction" if not ok else
                              "the surface diverges above the inertness floor")}


def gate_band(cells: dict, band_claim: dict) -> tuple:
    """`G-BAND` `[RUN]` — claimed from `BAND_REGISTRY.csv` BEFORE game 1, and the
    two cells ran on the SAME band and the SAME decks."""
    starts, decks = {}, {}
    for c in CELLS:
        v, where = S2._manifest_get((cells.get(c) or {}).get("manifest", {}),
                                    "band_seed_start")
        starts[c] = {"band_seed_start": v, "resolved_at": where}
        decks[c] = set((cells.get(c) or {}).get("deck_seeds") or ())
    same_band = len({s["band_seed_start"] for s in starts.values()}) == 1 and \
        starts[CELLS[0]]["band_seed_start"] is not None
    same_decks = decks[CELLS[0]] == decks[CELLS[1]] and bool(decks[CELLS[0]])
    claimed = bool((band_claim or {}).get("claimed_before_game_1"))
    return bool(same_band and same_decks and claimed), {
        "band_seed_start": starts, "same_band": same_band,
        "same_decks": same_decks,
        "n_decks": {c: len(decks[c]) for c in CELLS},
        "decks_only_in": {CELLS[0]: sorted(decks[CELLS[0]] - decks[CELLS[1]])[:5],
                          CELLS[1]: sorted(decks[CELLS[1]] - decks[CELLS[0]])[:5]},
        "band_claim": band_claim, "claimed_before_game_1": claimed}


def gate_n(n_common, n_games: dict, deck_floor=N_COMMON_FLOOR,
           games_floor=CELL_GAMES_FLOOR) -> tuple:
    """`G-N` — `n_common < 600` DECKS, or either cell under 1,200 of its 1,500
    paired GAMES.

    Both clauses are the SAME 80% bar in two units (1,200 games IS 600 decks); the
    deck clause is INDEPENDENTLY BINDING because two cells can each clear 1,200
    games while overlapping on fewer than 600 COMMON decks."""
    try:
        nc_ok = n_common is not None and n_common >= deck_floor
    except TypeError:
        nc_ok = False
    cell_ok = all(v is not None and v >= games_floor for v in n_games.values())
    return bool(nc_ok and cell_ok), {
        "n_common": n_common, "n_common_floor": deck_floor,
        "n_common_units": "DECKS", "n_games": dict(n_games),
        "cell_games_floor": games_floor, "cell_games_planned": CELL_GAMES_PLANNED,
        "same_80pct_bar": f"{games_floor} games IS {deck_floor} decks",
        "deck_clause_independently_binding": (
            "two cells can each clear the game floor while overlapping on fewer "
            "than the deck floor of COMMON decks — that weakens D and still voids")}


def gate_failed(cells: dict) -> tuple:
    """`G-FAILED` — DESIGN §8's three clauses; ANY one fires ⇒ `U-UNREADABLE`.

    1 RATE (not count): `F/n_attempted > 0.02` in either cell.
    2 CANDIDATE-CORRELATION: `max(F) ≥ 5` AND `max(F) > 3 × max(min(F), 1)` — the
      `capoff` pattern, which biases `D` in an unknown direction.
    3 QUALITATIVE: ANY failure whose class is not `WindowTruncationError` ⇒ RAISE
      and escalate REGARDLESS OF COUNT.
    """
    per, F = {}, {}
    for c in CELLS:
        s = (cells.get(c) or {}).get("summary", {})
        f = s.get("n_failed")
        att = s.get("n_attempted") or s.get("n") or (cells.get(c) or {}).get("n_games")
        rate = (f / att) if (isinstance(f, (int, float)) and att) else None
        classes = sorted({str(x) for x in (s.get("failed_classes") or [])})
        per[c] = {"n_failed": f, "n_attempted": att, "rate": rate,
                  "rate_bar": FAILED_RATE_BAR,
                  "clause1_ok": bool(rate is not None and rate <= FAILED_RATE_BAR),
                  "diagnostic_classes": classes}
        F[c] = f if isinstance(f, (int, float)) else 0
    fmax, fmin = max(F.values()), min(F.values())
    clause2 = bool(fmax >= 5 and fmax > 3 * max(fmin, 1))
    unknown = sorted({cl for c in CELLS for cl in per[c]["diagnostic_classes"]
                      if cl != KNOWN_FAILURE_CLASS})
    ok = all(per[c]["clause1_ok"] for c in CELLS) and not clause2 and not unknown
    return bool(ok), {
        "per_cell": per, "F_wide": F["WIDE"], "F_narrow": F["NARROW"],
        "clause2_candidate_correlated": clause2,
        "clause2_rule": "max(F) >= 5 AND max(F) > 3 × max(min(F), 1)",
        "clause3_unknown_classes": unknown,
        "known_class": KNOWN_FAILURE_CLASS,
        "clause3_rule": "ANY failure of an unknown class ⇒ RAISE, regardless of count",
        "selection_effect": (
            "window-truncation failures fire at extreme board extents, so any "
            "dropped set is CORRELATED WITH BOARD GEOMETRY — late-game, "
            "large-extent positions — and that correlation is DISCLOSED rather "
            "than argued away."),
        "wide_exposure_note": ("⚠️ WIDE carries ~4× the per-ply exposure to the "
                               "window-refusal class, so clause 2 is the one most "
                               "likely to bind — and it binds in the direction "
                               "that protects the reading.")}


def gate_tool(preflights: list, cells: dict) -> tuple:
    """`G-TOOL` `[RUN]` — ⭐ THE CONJUNCT IS EQUALITY OF `carc_rs_build` ACROSS
    BOXES, AND NOTHING ELSE.

    ⛔ `+rustcunpinned` is NOT a failure and NOT a sentinel — it is the NORMAL
    production value (`rust_agent.py:372`), and D4.13 records BOTH boxes emitting
    it on the R4 run. `unpinned` PASSES provided it is EQUAL on both boxes. This
    row is the campaign's THIRD unsatisfiable-gate catch (DESIGN §13.1) and must
    never be re-tightened into a pinnedness requirement.

    ⚠️ The authoritative cross-box witness is the two `PREFLIGHT_*_${HOST}_FIRST`
    files, NOT the manifests: under `--shared-claim` the second box writes no
    manifest, so a manifest's `mixed_builds` is the writer's own observation and
    cannot see the other box. `carc_rs_binary_sha` is BOX-LOCAL and is never
    compared across boxes.
    """
    builds = {}
    for d in preflights or ():
        host = str(d.get("host") or d.get("hostname"))
        b = d.get("carc_rs_build") or ((d.get("execution") or {})
                                       .get("carc_rs_build"))
        builds.setdefault(host, set()).add(b)
    per_host = {h: sorted(v) for h, v in sorted(builds.items())}
    distinct = {b for v in builds.values() for b in v}
    mixed_in_host = {h: v for h, v in per_host.items() if len(v) > 1}
    ok = bool(per_host) and len(distinct) == 1 and not mixed_in_host \
        and None not in distinct
    return bool(ok), {
        "carc_rs_build_by_host": per_host,
        "distinct_builds": sorted(x for x in distinct if x is not None),
        "mixed_within_a_host": mixed_in_host,
        "conjunct": "EQUALITY of carc_rs_build across boxes, AND NOTHING ELSE",
        "unpinned_is_normal": (
            "⛔ '+rustcunpinned' is the NORMAL production value "
            "(rust_agent.py:372) and PASSES provided both boxes emit it — "
            "DESIGN §13.1, this campaign's THIRD unsatisfiable-gate catch"),
        "binary_sha_rule": ("carc_rs_binary_sha is BOX-LOCAL and is NEVER compared "
                            "across boxes (the .so is not machine-reproducible)"),
        "authority": "PREFLIGHT_*_${HOST}_FIRST.json, not the manifests"}


def gate_ply(cells: dict) -> tuple:
    """`G-PLY` `[PER-CELL]` — `tiearb_partial_argmax_total` ABSENT (unknown, not
    zero) or NON-ZERO in either cell voids: an argmax over a partial world set
    means the CRN pairing across arms was broken during play."""
    obs, ok = {}, True
    for c in CELLS:
        v = (cells.get(c) or {}).get("summary", {}).get("tiearb_partial_argmax_total")
        good = v == 0
        obs[c] = {"tiearb_partial_argmax_total": v, "ok": bool(good),
                  "semantics": "ABSENT is unknown-not-zero and FAILS"}
        ok &= good
    return bool(ok), obs


def gate_stat(z_D, D, se_D, z_w, z_n) -> tuple:
    """`G-STAT` `[RUN]` — any of `z_D`, `D`, `se_D`, `z_w`, `z_n` NaN or absent.

    ⚠️ Evaluated in §3, BEFORE any branch comparison, so no branch is ever entered
    on a NaN comparison (§4.1)."""
    vals = {"z_D": z_D, "D": D, "se_D": se_D, "z_WIDE": z_w, "z_NARROW": z_n}
    bad = {k: v for k, v in vals.items()
           if v is None or (isinstance(v, float) and v != v)}
    return not bad, {"values": vals, "nan_or_absent": sorted(bad),
                     "precedence": "evaluated in §3 BEFORE any branch comparison"}


def smoke_whitelist_check(smoke: dict) -> dict:
    """§9.2 — COUNTS-AND-COST ONLY, and the whitelist is FAIL-CLOSED.

    ⛔ `paired_mean_margin`, `paired_z`, `elo`, `winrate`, W/D/L and any per-deck
    margin may not be read, computed, printed or stored. ⚠️ `f0` is MARGIN-DERIVED
    and is therefore FORBIDDEN at the smoke — named explicitly so a well-meaning
    implementation cannot add it "because it's just a count"."""
    keys = sorted(k for k in (smoke or {}) if not str(k).startswith("_"))
    forbidden = [k for k in keys if k not in SMOKE_WHITELIST]
    return {"ok": not forbidden, "keys": keys, "forbidden_present": forbidden,
            "whitelist": sorted(SMOKE_WHITELIST),
            "forbidden_examples": list(SMOKE_FORBIDDEN_EXAMPLES),
            "mode": "FAIL-CLOSED: an unlisted key is a REFUSAL, not a warning",
            "f0_note": "f0 is MARGIN-DERIVED and is FORBIDDEN at the smoke"}


def smoke_outcome_scan(doc, path="") -> list:
    """Every FORBIDDEN OUTCOME key in the artefact, at ANY depth.

    ⚠️ This is the GATE's surface and it is NOT the emitter's whitelist. §9.2
    gives two rules on two surfaces: the **emitter** is whitelisted and fails
    closed on an unlisted key, while `G-SMOKE` fires on *"any forbidden OUTCOME
    key"*. Conflating them makes a healthy artefact fail on its own structural
    envelope (`headline`, `kind`, `cells`) — see `SPEC_VS_BUILDABLE`.
    """
    hits = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            here = f"{path}.{k}" if path else str(k)
            if str(k) in SMOKE_OUTCOME_FORBIDDEN or SMOKE_OUTCOME_RE.search(str(k)):
                hits.append(here)
            hits += smoke_outcome_scan(v, here)
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            hits += smoke_outcome_scan(v, f"{path}[{i}]")
    return hits


def gate_smoke(smoke: dict, halted: bool = None, launched_anyway: bool = False) -> tuple:
    """`G-SMOKE` `[RUN]` — the smoke did not run at production knobs before game 1,
    or it HALTed on §9.3 and the cells were launched anyway, or `SMOKE.json`
    carries any forbidden outcome key."""
    if not isinstance(smoke, dict) or not smoke:
        return False, {"present": False,
                       "why": "SMOKE.json ABSENT — the smoke is a precondition"}
    wl = smoke_whitelist_check(smoke)
    outcome = smoke_outcome_scan(smoke)
    realized = smoke.get("worker_secs_per_game")
    halt = (halted if halted is not None else
            bool(realized is not None and realized > SMOKE_HALT_BAR))
    # ⚠️ the GATE fires on a forbidden OUTCOME key, not on the emitter whitelist
    # (two surfaces, §9.2 — see SPEC_VS_BUILDABLE). The whitelist result is
    # REPORTED beside it so the emitter's own contract stays visible.
    ok = bool(not outcome and not (halt and launched_anyway))
    return ok, {"present": True, "whitelist": wl,
                "forbidden_outcome_keys": outcome,
                "surfaces": ("EMITTER: fail-closed whitelist (§9.2 sentence 2). "
                             "GATE: any forbidden OUTCOME key (§3 G-SMOKE row). "
                             "This gate evaluates the GATE surface."),
                "worker_secs_per_game": realized,
                "halt_bar": SMOKE_HALT_BAR,
                "halt_bar_derivation": f"{SMOKE_HALT_MULTIPLE} × "
                                       f"{WORKER_S_COMMITTED['WIDE']} (§7.2)",
                "halted": halt, "launched_anyway": bool(launched_anyway),
                "one_sided": "an overrun HALTS, an underrun proceeds"}


# --------------------------------------------------------------------------- #
# §4 — the branch table, fired in the committed order                          #
# --------------------------------------------------------------------------- #
def decide_branch(z_D, preconditions: dict, A: bool) -> dict:
    """§4, verbatim and in order. `U-UNREADABLE` pre-empts everything; `B-REVERSED`
    is second and pre-empts the rest.

    On the complement the four partition `z_D ∈ (−2.0, +∞)` exactly, so **exactly
    one branch matches every possible read** and the match does not depend on
    presentation order (§4.1)."""
    failed = sorted(k for k, v in (preconditions or {}).items() if not v)
    if failed:
        return {"branch": "U-UNREADABLE", "reason": "a §3 precondition failed",
                "failed_preconditions": failed, "z_D": z_D, "A": A}
    if z_D is None or (isinstance(z_D, float) and z_D != z_D):
        # unreachable: G-STAT is a precondition and fires first (§4.1)
        return {"branch": "U-UNREADABLE",
                "reason": "z_D is NaN/absent and G-STAT did not fire — a defect",
                "failed_preconditions": ["G-STAT"], "z_D": z_D, "A": A}
    if z_D <= -Z_BAR:
        return {"branch": "B-REVERSED", "reason": f"z_D {z_D:+.4f} <= -{Z_BAR}",
                "z_D": z_D, "A": A}
    if z_D >= Z_BAR:
        b = "B-CONFIRMED" if A else "B-COSTKILL"
        return {"branch": b,
                "reason": f"z_D {z_D:+.4f} >= +{Z_BAR} and A is {A}",
                "z_D": z_D, "A": A}
    if z_D >= Z_PRESENT:
        return {"branch": "B-PRESENT",
                "reason": f"+{Z_PRESENT} <= z_D {z_D:+.4f} < +{Z_BAR}",
                "z_D": z_D, "A": A}
    return {"branch": "B-FLAT",
            "reason": f"-{Z_BAR} < z_D {z_D:+.4f} < +{Z_PRESENT}",
            "z_D": z_D, "A": A}


def affordability(waiver: dict) -> dict:
    """§4's `A` — `rho_wall(64) <= 1.20` OR `W`.

    ⭐ `rho_wall(64)` = 2.4897 is a COMMITTED ARITHMETIC CONSTANT, not a
    measurement to come ⇒ the first disjunct is FALSE, and this rule says so
    before game 1. `A` is therefore decided entirely by `W`."""
    first = RHO_WALL_64 <= N4_BAR
    W = bool((waiver or {}).get("W"))
    return {"A": bool(first or W), "first_disjunct": first,
            "rho_wall_64": RHO_WALL_64, "n4_bar": N4_BAR, "W": W,
            "note": "the first disjunct is FALSE before game 1 — rho_wall(64) = "
                    "2.4897 is a committed arithmetic constant (Phase A measured "
                    "rho_wall(16) = 0.6224; the arbiter's cost is exactly linear "
                    "in B). A is decided entirely by W.",
            "waiver": waiver}


# --------------------------------------------------------------------------- #
# ⭐ THE KNOWN-GOOD GATE EVALUATION — DESIGN §13.1's launch precondition        #
# --------------------------------------------------------------------------- #
#: Rows with no Stage-2 analogue, NAMED rather than silently counted as covered.
KNOWNGOOD_NA = {
    "G-NEST": "a [pre-run] CODE witness over the seeding source — Stage 2 has no "
              "GATE_NEST.json analogue (its two cells differ by MODE, not by B, so "
              "no nesting property was ever asserted for them)",
    "G-DIVERGE": "no f0 analogue exists: Stage 2's ARB/RND cells are DIFFERENT-MODE "
                 "cells, not a nested refinement, so 'the fraction of decks where "
                 "the two cells coincide' is not the same quantity and grading this "
                 "row on it would be a false pass",
}


def knowngood_eval(stage2_dir=STAGE2_DIR, share=None, repo=REPO) -> dict:
    """Evaluate every §3 row against Stage 2's COMPLETED artifacts.

    ⚠️ TWO KINDS OF SUBSTITUTION, both DISCLOSED per row rather than silent:
      * `scaled`  — a SCALE constant (n floors) replaced by the known-good run's
        own equivalent, because Stage 2 is a 800-game/400-deck run and B64's 1,200
        / 600 floors are unreachable on it BY SIZE. Grading the row verbatim would
        report a FAIL that says nothing about the row's machinery.
      * `mapped`  — a cell/knob identity substituted (Stage 2 has no B = 64 cell,
        and its RND cell is mode `random` while this pair requires `argmax` in
        both). Both B64 cells are mapped onto Stage 2's ARB cell.
    A row whose machinery cannot be exercised at all is `N-A` and is NAMED.
    """
    share = Path(share) if share else Path("/mnt/c/carc-shared/tiearb2_stage2_20260817")
    stage2_dir = Path(stage2_dir)
    rows, notes = {}, []

    def row(gid, status, detail, **kw):
        rows[gid] = {"status": status, "detail": detail, **kw}

    arb_dir = share / "tiearb_ARB_B16J4_deploy11008"
    rnd_dir = share / "tiearb_RND_B16J4_deploy11008"
    if not (arb_dir / "summary.json").is_file():
        return {"ok": False, "error": f"Stage 2 ARB cell not found under {share}",
                "rows": {}}

    arb = S2.load_cell("ARB", arb_dir / "summary.json", arb_dir / "manifest.json")
    rnd = S2.load_cell("RND", rnd_dir / "summary.json", rnd_dir / "manifest.json")
    # ⚠️ MAPPED: both B64 cells onto Stage 2's ARB cell — it is the only argmax
    # cell, and this pair requires argmax in BOTH.
    cells = {"WIDE": arb, "NARROW": arb}
    both = {"WIDE": arb, "NARROW": rnd}

    ok, d = gate_j1(cells)
    row("G-J1", "PASS" if ok else "FAIL", d, mapped="both cells ← Stage 2 ARB")

    ok, d = gate_j4(cells, b_by_cell={"WIDE": 16, "NARROW": 16})
    row("G-J4", "PASS" if ok else "FAIL", d,
        mapped="both cells ← Stage 2 ARB", scaled="B: 64→16 (no B=64 artifact "
        "exists on a completed run — the row's MACHINERY is what is under test)")

    pre = S2.load_preflights(sorted(
        (stage2_dir / "verdicts").glob("PREFLIGHT_*_FIRST.json")))
    ok, d = gate_j13(pre, expect_hosts=("Doctor", "laptop-wsl"), expect_b=(16,))
    row("G-J13", "PASS" if ok else "FAIL", d,
        scaled="expected_B: (64,16)→(16,) — Stage 2 ran one B value; the "
               "TWO-SIDED and PER-HOST clauses are what is exercised")

    row("G-NEST", "N-A", {"why": KNOWNGOOD_NA["G-NEST"],
                          "structural_witness_at_HEAD": nest_witness(repo)})

    ok, d = gate_fire(cells)
    row("G-FIRE", "PASS" if ok else "FAIL", d, mapped="both cells ← Stage 2 ARB")

    row("G-DIVERGE", "N-A", {"why": KNOWNGOOD_NA["G-DIVERGE"]})

    # ⚠️ the house claim artefact is a THREE-LINE PLAIN-TEXT shape as often as
    # JSON — S2's loader knows both and never invents a claim
    claim = S2.load_band_claim(stage2_dir / "BAND_CLAIM.json")
    ok, d = gate_band(both, claim)
    row("G-BAND", "PASS" if ok else "FAIL", d,
        mapped="WIDE ← ARB, NARROW ← RND (the same-band/same-decks clause needs "
               "TWO real cells, and Stage 2's two are band- and deck-matched)")

    common = len(set(arb["by_deck"]) & set(rnd["by_deck"]))
    ok, d = gate_n(common, {"WIDE": arb["n_games"], "NARROW": rnd["n_games"]},
                   deck_floor=320, games_floor=640)
    row("G-N", "PASS" if ok else "FAIL", d,
        scaled="floors 600 decks/1,200 games → Stage 2's own 320/640 (the SAME "
               "80% bar at its own n). ⚠️ Verbatim floors are unreachable on an "
               "800-game run BY SIZE — grading them here would report a FAIL "
               "about Stage 2's scale, not about this row",
        verbatim_would_be="FAIL (by size)")

    ok, d = gate_failed(both)
    row("G-FAILED", "PASS" if ok else "FAIL", d,
        mapped="WIDE ← ARB, NARROW ← RND (clause 2 compares the TWO cells)")

    ok, d = gate_tool(pre, both)
    row("G-TOOL", "PASS" if ok else "FAIL", d,
        note="⭐ THE ROW THE PRECONDITION EXISTS FOR — the drafted version treated "
             "'+rustcunpinned' as a sentinel and would have failed this healthy run")

    ok, d = gate_ply(cells)
    row("G-PLY", "PASS" if ok else "FAIL", d, mapped="both cells ← Stage 2 ARB")

    dpd = S2.deck_paired_D(arb["by_deck"], rnd["by_deck"])
    ok, d = gate_stat(dpd["z_D"], dpd["D"], dpd["se_D"], arb["z"], rnd["z"])
    row("G-STAT", "PASS" if ok else "FAIL", d,
        mapped="z_D from Stage 2's own ARB−RND contrast")

    smoke_p = stage2_dir / "SMOKE.json"
    smoke = json.loads(smoke_p.read_text()) if smoke_p.is_file() else {}
    wl = smoke_whitelist_check(smoke)
    ok, d = gate_smoke(smoke, halted=False, launched_anyway=False)
    row("G-SMOKE", "PASS" if ok else "FAIL", d,
        note=("the whitelist is evaluated against Stage 2's own SMOKE.json; keys "
              "outside this pair's §9.2 list are reported"),
        whitelist_forbidden_present=wl["forbidden_present"])

    evaluated = {g: r for g, r in rows.items() if r["status"] != "N-A"}
    na = {g: r for g, r in rows.items() if r["status"] == "N-A"}
    failed = sorted(g for g, r in evaluated.items() if r["status"] == "FAIL")
    return {
        "schema": "carcassonne-b64-knowngood/v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "precondition": "DESIGN §13.1 — every §3 row must PASS on a known-good run "
                        "BEFORE the blind commit. A row that fails a healthy run is "
                        "a drafting defect.",
        "known_good_run": str(stage2_dir),
        "share": str(share),
        "n_rows": len(rows), "n_evaluated": len(evaluated), "n_na": len(na),
        "n_pass": sum(1 for r in evaluated.values() if r["status"] == "PASS"),
        "n_fail": len(failed),
        "failed_rows": failed,
        "na_rows": sorted(na),
        "all_evaluable_rows_pass": not failed,
        "meaning": ("'all rows pass' means every row WITH a known-good analogue "
                    "passes AND the rows without one are NAMED. A row that cannot "
                    "be evaluated NEVER silently counts as covered."),
        "rows": rows,
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# the read-out                                                                 #
# --------------------------------------------------------------------------- #
def build_readout(args) -> dict:
    cells = {}
    for c, summ, man, recs in (("WIDE", args.wide_summary, args.wide_manifest,
                                args.wide_records),
                               ("NARROW", args.narrow_summary,
                                args.narrow_manifest, args.narrow_records)):
        cells[c] = S2.load_cell(c, summ, man, recs)

    dpd = S2.deck_paired_D(cells["WIDE"]["by_deck"], cells["NARROW"]["by_deck"])
    fb = f0_block(cells["WIDE"]["by_deck"], cells["NARROW"]["by_deck"])

    pre = S2.load_preflights(args.preflight or [])
    gn = json.loads(Path(args.gate_nest).read_text()) if (
        args.gate_nest and Path(args.gate_nest).is_file()) else None
    claim = S2.load_band_claim(args.band_claim) if args.band_claim else {
        "claimed_before_game_1": False, "note": "no --band-claim given"}
    smoke = json.loads(Path(args.smoke).read_text()) if (
        args.smoke and Path(args.smoke).is_file()) else {}

    gates = {}
    gates["G-J1"] = gate_j1(cells)
    gates["G-J4"] = gate_j4(cells)
    gates["G-J13"] = gate_j13(pre)
    gates["G-NEST"] = gate_nest(gn)
    gates["G-FIRE"] = gate_fire(cells)
    gates["G-DIVERGE"] = gate_diverge(fb)
    gates["G-BAND"] = gate_band(cells, claim)
    gates["G-N"] = gate_n(dpd["n_common_decks"],
                          {c: cells[c]["n_games"] for c in CELLS})
    gates["G-FAILED"] = gate_failed(cells)
    gates["G-TOOL"] = gate_tool(pre, cells)
    gates["G-PLY"] = gate_ply(cells)
    gates["G-STAT"] = gate_stat(dpd["z_D"], dpd["D"], dpd["se_D"],
                                cells["WIDE"]["z"], cells["NARROW"]["z"])
    gates["G-SMOKE"] = gate_smoke(smoke, launched_anyway=args.launched_after_halt)

    preconditions = {g: ok for g, (ok, _d) in gates.items()}
    waiver = waiver_predicate(Path(args.cell_dir), args.band_claim)
    A = affordability(waiver)
    branch = decide_branch(dpd["z_D"], preconditions, A["A"])
    head, body = BRANCH_TEXT[branch["branch"]]

    rho = None
    try:
        se_w = cells["WIDE"]["recomputed"]["se"]
        se_n = cells["NARROW"]["recomputed"]["se"]
        if all(v not in (None, 0) for v in (se_w, se_n, dpd["se_D"])):
            rho = (se_w ** 2 + se_n ** 2 - dpd["se_D"] ** 2) / (2 * se_w * se_n)
    except (TypeError, KeyError):
        rho = None

    return {
        "schema": "carcassonne-b64-cell-readout/v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "read_rule": "measurement/tiearb_widening_20260817/b64_cell/READ_RULE.md",
        "design": "measurement/tiearb_widening_20260817/b64_cell/DESIGN.md",
        "branch": branch["branch"],
        "branch_headline": head,
        "branch_body": body,
        "branch_detail": branch,
        "reachable_set": reachable_branches(waiver["W"]),
        "affordability": A,
        "D_block": {**dpd, "rho": rho,
                    "se_D_committed": SE_D_COMMITTED,
                    "floor_2sigma_committed": D_FLOOR_2SIGMA,
                    "n_to_convict_at_realized_dispersion": S2.n_to_reach(
                        dpd["n_common"], dpd["z_D"], Z_BAR),
                    "effect_bracket_committed": list(EFFECT_BRACKET)},
        "divergence": fb,
        "cells": {c: {k: cells[c].get(k) for k in
                      ("M", "z", "n_paired", "elo", "elo_sig_1sigma", "wr", "wr_z",
                       "W", "D_draws", "L", "n_games", "n_decks_seat_balanced",
                       "n_failed", "ms_ratio", "champ_prefix_ms_per_move",
                       "rung_ms_per_move", "phi", "arbiter_errors",
                       "seat_balance", "recomputed")}
                  for c in CELLS},
        "gates": {g: {"ok": ok, "detail": d} for g, (ok, d) in gates.items()},
        "gates_all_pass": all(preconditions.values()),
        "cost_facts": {
            "rho_wall_16_measured": RHO_WALL_16, "rho_wall_64": RHO_WALL_64,
            "rho_wall_32": RHO_WALL_32, "n4_bar": N4_BAR,
            "rho_phone_64": list(RHO_PHONE_64),
            "rho_phone_label": "NOT SOLVED — a third currency",
            "worker_s_committed": WORKER_S_COMMITTED,
            "ms_ratio_predicted": MS_RATIO_PREDICTED,
            "wall_committed_h": WALL_COMMITTED_H,
            "field_name_trap": ("⚠️ champ_prefix_ms_per_move IS THE CANDIDATE SIDE "
                                "in eval_fair_puct (lines 2361/2371/2389). A "
                                "read-out that swaps them inverts the cost verdict."),
            "ms_ratio_is_never_a_branch_input": True,
            "cost_immunity": ("WIDE and NARROW are NOT cost-matched to each other, "
                              "but neither candidate's SEARCH BUDGET moves: both run "
                              "the identical champion at k8×1376 and the arbiter "
                              "fires AFTER the search, at the root, on an "
                              "already-resolved tie ⇒ the extra cost buys no extra "
                              "search. It is a WALL-CLOCK ASYMMETRY and is disclosed "
                              "as one on every branch."),
        },
        "phi_block": {c: {"phi": cells[c].get("phi")} for c in CELLS} | {
            "offline_prior": PHI_PRIOR_OFFLINE,
            "stage2_realized": list(PHI_STAGE2_REALIZED)},
        "carried_verbatim": {
            "W-RISING": ("lower(CI)>0, d>=0.04, arb_64 convicts, arb(64)>arb(16) — "
                         "Δ(16→64) = 0.0670 CI95 [0.0215, 0.1111]"),
            "W-RISING_scope_fence": (
                "a null here would have meant 'no rung above 16 is worth ≥ +0.04 "
                "pts/tied ply', NOT Δ = 0 … the saturating-exp (+0.017) and "
                "√B-noise (+0.021) models are NOT resolved by this design"),
            "translation_caveat": (
                "Stage 1b's +0.1441 pts/tied ply predicts +0.79 pts/game … Phase B "
                "realized +3.07 — a 3.9× under-prediction. So Δ(16→64) = +0.064 maps "
                "to anywhere from +0.35 (naive) to +1.4 (realized-ratio) pts/game."),
            "translation_caveat_both_ways": (
                "the offline→game map is unestablished and +0.0670 × 3.9 is not a "
                "projection either"),
            "offline_ratio_disclaimer": (
                "⛔ arb64/arb16 = 0.2015/0.1345 = 1.498 may be printed as a "
                "DESCRIPTION of the offline ladder and MUST NOT be presented as a "
                "projection of the game effect."),
        },
        "spec_vs_buildable": SPEC_VS_BUILDABLE,
        "governance": ("PRODUCTION.yaml untouched on every branch. This read-rule is "
                       "SPENT when the read-out lands, on every branch, and the band "
                       "retires from confirmatory use."),
    }


#: ⚠️ Spec-vs-buildable mismatches are REPORTED, never resolved by changing the
#: frozen pair. Populated at build time; empty means none was found.
SPEC_VS_BUILDABLE = [
    {
        "where": "READ_RULE §3 G-FAILED clause 3 / DESIGN §8 clause 3",
        "issue": "the diagnostic class of a failed GAME has no named address in "
                 "the pair: §2's table routes n_failed to summary.json but no key "
                 "is named for the per-failure CLASS, and eval_fair_puct's summary "
                 "does not emit one today.",
        "adjudicator_behaviour": "reads `summary.json::failed_classes` if present; "
                                 "with n_failed == 0 the clause is vacuous and the "
                                 "gate passes. With n_failed > 0 and no class "
                                 "field, clause 3 CANNOT be evaluated — REPORTED "
                                 "here, not resolved.",
        "resolution": "owner/drafter call — either name the address in the pair or "
                      "have the harness emit it before game 1",
    },
    {
        "where": "READ_RULE §3 G-J13 / DESIGN §3",
        "issue": "the pair requires the two-sided control at BOTH B values per "
                 "host, but names ONE file per host "
                 "(PREFLIGHT_*_${HOST}_FIRST.json) and names NO address for the B "
                 "value inside it. On the known-good artefact B sits at "
                 "`j13_witness.B` / `expected.B`, at neither of the two levels §2's "
                 "manifest rule would suggest. ⚠️ And ONE file per host cannot "
                 "carry TWO B values without a shape the pair does not specify.",
        "adjudicator_behaviour": "resolves B over a documented order "
                                 f"{list(PREFLIGHT_B_PATHS)} and treats an "
                                 "unreadable B as ABSENT (fail, never coerced).",
        "resolution": "name the field, or emit one preflight file per (host, B) — "
                      "drafter call, not resolved here",
    },
    {
        "where": "READ_RULE §3 G-SMOKE / DESIGN §9.2",
        "issue": "⭐ FOUND BY THE KNOWN-GOOD EVALUATION. §9.2 states TWO rules on "
                 "TWO surfaces — the EMITTER 'is whitelisted to the keys above and "
                 "must fail closed on an unlisted key', while the G-SMOKE row fires "
                 "on 'any forbidden OUTCOME key'. Read as ONE whitelist over the "
                 "artefact, the row FAILS a known-good smoke: Stage 2's SMOKE.json "
                 "carries structural keys (headline, kind, cells, throwaway_band, "
                 "cost_reference, production_knobs, eta_for_the_real_cells, "
                 "phi_reference, cell_band_untouched) and suffixes the "
                 "field-name-trap keys (champ_prefix_ms_per_move_IS_THE_CANDIDATE). "
                 "NONE is an outcome key. This is DESIGN §13.1's own class: a "
                 "fail-closed rule that fails a healthy run.",
        "adjudicator_behaviour": "the GATE fires on forbidden OUTCOME keys at any "
                                 "depth; the EMITTER whitelist is evaluated and "
                                 "REPORTED beside it, never as the gate verdict.",
        "resolution": "drafter call — either scope the row's whitelist to the "
                      "emitter (as the two sentences already imply) or enumerate "
                      "the structural envelope. NOT resolved here; the pair is "
                      "frozen.",
    },
]


def render(v: dict) -> str:
    L = [f"# `B = 64` GAME CELL — READ-OUT", "",
         f"generated: {v['generated_utc']}", "",
         f"## BRANCH: `{v['branch']}`", "",
         f"**{v['branch_headline']}**", "", v["branch_body"], ""]

    rs = v["reachable_set"]
    L += ["## §4.0 — the reachable branch set, stated BEFORE the run", "",
          f"- `W` = **{rs['W']}** · reachable {rs['reachable']}",
          f"- unreachable: **{rs['unreachable'] or 'none'}**", f"- {rs['note']}", "",
          "## §3 gates — ALL of them, never short-circuited", "",
          "| gate | ok |", "|---|---|"]
    for g, row in sorted(v["gates"].items()):
        L.append(f"| `{g}` | {'PASS' if row['ok'] else '**FAIL**'} |")

    d = v["D_block"]
    L += ["", "## The `D` block — THE PRIMARY", "",
          f"- `D` = {_f(d['D'])} · `se_D` = {_f(d['se_D'], '.4f')} · "
          f"**`z_D` = {_f(d['z_D'], '+.4f')}** · `n_common` = {d['n_common']} decks",
          f"- realized `rho` = {_f(d.get('rho'), '+.4f')} · committed `se(D)` = "
          f"{SE_D_COMMITTED} · committed 2σ floor = +{D_FLOOR_2SIGMA} pts/game",
          f"- `n` to convict at the REALIZED dispersion: "
          f"{d['n_to_convict_at_realized_dispersion']} decks", ""]

    f = v["divergence"]
    L += ["## §4.3 item 3 — the divergence block", "",
          f"- `f0` = {_f(f['f0'], '.4f')} · `1 − f0` = {_f(f['one_minus_f0'], '.4f')} "
          f"vs floor {f['floor']} — **and beside the EXPECTED ≈{f['expected_one_minus_f0']}**",
          f"- dilution `√(1−f0)` = {_f(f['dilution_sqrt_one_minus_f0'], '.4f')} · "
          f"headroom ≈{f['headroom_x']:.0f}×",
          (f"- ⚠️ **ANOMALY: a realized `1 − f0` materially below ≈1.0 that still "
           f"clears the floor is an ANOMALY, not a pass.**" if f["anomaly"] else
           "- (not flagged anomalous)"),
          f"- {f['measurement_disclosure']}", "",
          "## Cost — reported on every branch, a branch input NOWHERE", ""]
    cf = v["cost_facts"]
    L += [f"- `rho_wall(16)` {cf['rho_wall_16_measured']} (measured) · "
          f"`rho_wall(64)` **{cf['rho_wall_64']}** vs the N4 bar **{cf['n4_bar']}** · "
          f"`rho_wall(32)` {cf['rho_wall_32']} (ALSO above the bar)",
          f"- `rho_phone(64)` {cf['rho_phone_64']} — **{cf['rho_phone_label']}**",
          f"- {cf['field_name_trap']}", f"- {cf['cost_immunity']}", ""]

    cv = v["carried_verbatim"]
    L += ["## Carried VERBATIM", ""]
    L += [f"- **{k}**: {t}" for k, t in cv.items()]
    if v.get("spec_vs_buildable"):
        L += ["", "## ⚠️ SPEC-vs-BUILDABLE mismatches — REPORTED, never resolved here", ""]
        for m in v["spec_vs_buildable"]:
            L += [f"- **{m['where']}** — {m['issue']}",
                  f"  - adjudicator: {m['adjudicator_behaviour']}",
                  f"  - resolution: {m['resolution']}"]
    L += ["", f"*{v['governance']}*", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="mode")

    a = sub.add_parser("adjudicate", help="the read-out")
    a.add_argument("--wide-summary", required=True)
    a.add_argument("--wide-manifest", required=True)
    a.add_argument("--wide-records", default=None)
    a.add_argument("--narrow-summary", required=True)
    a.add_argument("--narrow-manifest", required=True)
    a.add_argument("--narrow-records", default=None)
    a.add_argument("--preflight", action="append", default=None)
    a.add_argument("--gate-nest", default=None)
    a.add_argument("--band-claim", default=None)
    a.add_argument("--smoke", default=None)
    a.add_argument("--cell-dir", default=str(CELL_DIR))
    a.add_argument("--launched-after-halt", action="store_true")
    a.add_argument("--out-dir", required=True)

    k = sub.add_parser("knowngood", help="DESIGN §13.1's launch precondition")
    k.add_argument("--stage2-dir", default=str(STAGE2_DIR))
    k.add_argument("--share", default=None)
    k.add_argument("--out", default=None)

    n = sub.add_parser("nest-witness", help="emit GATE_NEST.json")
    n.add_argument("--out", default=None)

    s = sub.add_parser("smoke-check", help="§9.2's fail-closed whitelist")
    s.add_argument("--smoke", required=True)
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    mode = a.mode or "adjudicate"

    if mode == "knowngood":
        doc = knowngood_eval(a.stage2_dir, a.share)
        out = Path(a.out or (CELL_DIR / "KNOWNGOOD_EVAL.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")
        for g, r in sorted(doc.get("rows", {}).items()):
            mark = {"PASS": "PASS", "FAIL": "**FAIL**", "N-A": "N-A "}[r["status"]]
            extra = r.get("scaled") or r.get("mapped") or ""
            print(f"[knowngood] {mark:8s} {g:10s} "
                  + (f"({extra[:70]})" if extra else ""))
        print(f"[knowngood] {doc['n_pass']}/{doc['n_evaluated']} evaluable rows PASS; "
              f"{doc['n_na']} N-A: {doc['na_rows']}")
        print(f"[knowngood] -> {out}")
        return 0 if doc["all_evaluable_rows_pass"] else 1

    if mode == "nest-witness":
        doc = nest_witness()
        out = Path(a.out or (CELL_DIR / "GATE_NEST.json"))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print(f"[nest] witness = {doc['witness']} — {doc['why']}")
        print(f"[nest] -> {out}")
        return 0 if doc["witness"] else 1

    if mode == "smoke-check":
        doc = smoke_whitelist_check(json.loads(Path(a.smoke).read_text()))
        print(json.dumps(doc, indent=1))
        if not doc["ok"]:
            print(f"\n[smoke] ⛔ REFUSING: forbidden key(s) "
                  f"{doc['forbidden_present']} — §9.2 is COUNTS-AND-COST ONLY and "
                  f"its whitelist is FAIL-CLOSED.", file=sys.stderr)
        return 0 if doc["ok"] else 1

    v = build_readout(a)
    out_dir = Path(a.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "READOUT_B64.json").write_text(
        json.dumps(v, indent=2, sort_keys=True, default=str))
    (out_dir / "READOUT_B64.md").write_text(render(v))
    print(f"[b64] branch = {v['branch']} | z_D = {_f(v['D_block']['z_D'])} | "
          f"gates_all_pass = {v['gates_all_pass']}")
    print(f"[b64] -> {out_dir / 'READOUT_B64.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
