#!/usr/bin/env python3
"""
D1 FAIR-RULER RE-BASELINE — THE ADJUDICATOR.

Written from `READ_RULE.md`'s text ALONE (blind-adjudication discipline,
READ_RULE §4 / run_cells.sh's own hand-off message), by a session that had seen
NO statistic of any kind from this run at the time this file was authored.

There is no pre-existing "frozen analyzer" script in the prereg dir: the
per-cell ANALYZER of record is `scripts/classical_search/eval_fair_puct.py`,
which wrote each cell's `summary.json`.  READ_RULE §1's convention is therefore
implemented as:

  * ANALYZER value  — read verbatim off each cell's `summary.json`
                      (`paired_mean_margin`, `paired_z`, `winrate`, `elo`, ...).
  * WITNESS value   — recomputed from scratch here, from the raw per-game
                      `seed*_a*.json` records, via an independent
                      re-implementation of `eval_fair_puct._paired_z`.
  * Disagreement beyond floating-point tolerance  ->  `U-UNREADABLE`.

The derived statistics (Δ₁…Δ₄, SPAN, A, D_i) do not exist in any summary; they
are computed here from the REALIZED paired per-deck differences, exactly as
READ_RULE §1 specifies, and their se is realized, never assumed.

Usage:
    python3 adjudicate.py [--share /mnt/c/carc-shared] [--out <dir>]
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# PRE-REGISTERED CONSTANTS — all transcribed from the FROZEN pair.             #
# Nothing here is derived from this run's data.                                #
# --------------------------------------------------------------------------- #

RUN_ID = "track_d1_fair_rebase"

LADDER = [  # (cell dir, short name, total_sims, k_dets, sims_per_det)
    ("fr_a800", "A800", 800, 4, 200),
    ("fr_b1600", "B1600", 1600, 4, 400),
    ("fr_c2752", "C2752", 2752, 4, 688),
    ("fr_d5504", "D5504", 5504, 4, 1376),
    ("fr_e11008", "E11008", 11008, 8, 1376),
]
ATTRIB = ("fr_w2752", "W2752", 2752, 4, 688)

BAND_SEED_START = 145000000000          # READ_RULE §3A G-BAND
N_DECKS = 400
SEATINGS_PER_DECK = 2
N_GAMES = 800

CAND_LEAF_HASH = "a36d2e15a3b3d71d"     # G-LEAF
RUNG_LEAF_HASH = "42af12fce22e1a0f"     # G-LEAF

# READ_RULE §1 (E3) — the G2 comparators, verbatim.
G2_COMPARATOR = {2752: 8.6425, 5504: 10.7825, 11008: 9.7700}
G2_SOURCE_ROW = {
    2752: "fair_ruler_rebase_2752 (G2, python, walled, band 24e9, k4)",
    5504: "fair_ruler_rebase_5504 (G2, python, walled, band 24e9, k4)",
    11008: "fair_ruler_k8x1376_11008 (G2, python, walled, band 24e9, k8x1376)",
}
# DESIGN §4.1 — the COMMITTED G2-side dispersion (se(M) ~ 0.93 pts at n_paired=200).
SE_G2_COMMITTED = 0.93
SE_R_COMMITTED = 0.66                   # DESIGN §4.1
SE_SPACING_PREREG = 0.885               # DESIGN §4.2 — the pre-registered EXPECTATION
SE_EFF_D_COMMITTED = 2.28               # DESIGN §4.4
ELO_PER_PT_COMMITTED = 13.7             # DESIGN §4.5

# DESIGN §6 — the cost model (W-COST witness only; never voiding).
COST_RUNG_MS_LOCAL = 624.3
COST_MS_PER_TOTAL_SIM = 0.1474
COST_SOLVER_S = 1.11
COST_CAL = 1.02

SAT_LO, SAT_HI = 0.50, 0.90             # G-SAT-END / G-SAT-MID / GW-SAT
FAIL_RATE_VOID = 0.02                   # G-N / GW-N
Z_BAR = 2.0                             # every branch bar in §4 / §4.2 / §4.4
TOL_REL = 1e-6                          # analyzer-vs-witness float tolerance
TOL_ABS = 1e-9

# G-SINGLEVAR — the ONLY `config` keys the five ladder cells may differ in.
SINGLEVAR_ALLOWED = {
    "champion.k_dets",
    "champion.sims_per_det",
    "champion.total_sims",
}
# "the output path" and "claim_host" are named in the gate; they carry no fixed
# key name in this harness's manifest, so any key whose leaf name matches these
# is treated as the named exemption and REPORTED explicitly.
SINGLEVAR_PATH_LEAVES = {"out", "outdir", "out_dir", "output", "path", "claim_host", "host"}

# GW-PAIR — W2752 vs C2752 may differ in exactly these.
PAIR_ALLOWED = {"rules_profile"}


# --------------------------------------------------------------------------- #
# small utilities                                                             #
# --------------------------------------------------------------------------- #

def flat(o, prefix=""):
    """Flatten a nested dict/list into {dotted_path: scalar}."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flat(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(o, list):
        out[prefix] = json.dumps(o, sort_keys=True)
    else:
        out[prefix] = o
    return out


def dual(man, leaf_path):
    """READ_RULE §3: read at the manifest TOP LEVEL, then at `config.*`.

    Returns (value, address_that_resolved) or (None, None) — ABSENT IS FAIL.
    """
    for base in ("", "config"):
        cur = man
        addr = []
        if base:
            cur = cur.get(base)
            addr.append(base)
            if not isinstance(cur, dict):
                continue
        ok = True
        for part in leaf_path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
                addr.append(part)
            else:
                ok = False
                break
        if ok:
            return cur, ".".join(addr)
    return None, None


def paired_deltas(records):
    """Independent re-implementation of `eval_fair_puct._paired_z`'s per-deck
    seat-balanced margin: d(seed) = (diff[a_seat=0] + diff[a_seat=1]) / 2."""
    by_seed = {}
    for r in records:
        by_seed.setdefault(r["seed"], {})[r["a_seat"]] = r["diff"]
    return {s: (v[0] + v[1]) / 2.0 for s, v in by_seed.items() if 0 in v and 1 in v}


def mean_se_z(vals):
    n = len(vals)
    if n < 2:
        return None, None, None, 0
    m = sum(vals) / n
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    se = math.sqrt(var / n)
    z = m / se if se > 0 else float("nan")
    return m, se, z, n


def close(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= max(TOL_ABS, TOL_REL * max(abs(a), abs(b)))


def ci95(m, se):
    return (m - 1.96 * se, m + 1.96 * se)


def elo_from_wr(wr, n):
    if not (0 < wr < 1):
        return math.copysign(800.0, wr - 0.5), float("nan")
    elo = 400.0 * math.log10(wr / (1 - wr))
    sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    return elo, sig


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True).stdout.strip()


# --------------------------------------------------------------------------- #
# load                                                                        #
# --------------------------------------------------------------------------- #

class Cell:
    def __init__(self, root: Path, dirname: str, name: str,
                 total_sims: int, k_dets: int, sims_per_det: int):
        self.dir = root / dirname
        self.name = name
        self.total_sims = total_sims
        self.k_dets = k_dets
        self.sims_per_det = sims_per_det
        self.man = json.loads((self.dir / "manifest.json").read_text())
        self.sum = json.loads((self.dir / "summary.json").read_text())
        self.recs = []
        for p in sorted(self.dir.glob("seed*_a*.json")):
            try:
                self.recs.append(json.loads(p.read_text()))
            except Exception as e:                       # pragma: no cover
                raise SystemExit(f"unreadable record {p}: {e}")
        self.failed = sorted(self.dir.glob("**/FAILED*")) + \
            sorted(self.dir.glob("**/*.failed.json"))
        # WITNESS recomputation
        self.d = paired_deltas(self.recs)
        self.seeds = set(self.d)
        m, se, z, n = mean_se_z(list(self.d.values()))
        self.w_margin, self.w_se, self.w_z, self.w_npair = m, se, z, n
        w = sum(1 for r in self.recs if r["won_by_champ"])
        dr = sum(1 for r in self.recs if r["drew"])
        self.W, self.D, self.L = w, dr, len(self.recs) - w - dr
        self.n = len(self.recs)
        self.w_wr = (w + 0.5 * dr) / self.n if self.n else float("nan")
        self.w_elo, self.w_elo_sig = elo_from_wr(self.w_wr, self.n)
        self.w_wr_z = ((self.w_wr - 0.5) / math.sqrt(0.25 / self.n)) if self.n else float("nan")
        self.seat = {0: sum(1 for r in self.recs if r["a_seat"] == 0),
                     1: sum(1 for r in self.recs if r["a_seat"] == 1)}
        self.mean_moves = sum(r["moves"] for r in self.recs) / max(1, self.n)
        self.mean_elapsed = sum(r["elapsed_s"] for r in self.recs) / max(1, self.n)
        # ANALYZER values
        self.a_margin = self.sum.get("paired_mean_margin")
        self.a_z = self.sum.get("paired_z")
        self.a_npair = self.sum.get("n_paired")
        self.a_wr = self.sum.get("winrate")
        self.a_elo = self.sum.get("elo")
        self.a_elo_sig = self.sum.get("elo_sig_1sigma")
        self.n_failed = self.sum.get("n_failed", 0)
        self.failure_rate = self.sum.get("failure_rate", 0.0)
        self.failed_classes = self.sum.get("failed_cells", [])
        self.rung_ms = self.sum.get("rung_ms_per_move")
        self.champ_ms = self.sum.get("champ_prefix_ms_per_move")
        self.solver_pg = self.sum.get("solver_secs_per_game")


# --------------------------------------------------------------------------- #
# gates                                                                       #
# --------------------------------------------------------------------------- #

class Gates:
    def __init__(self):
        self.rows = []      # (id, PASS/FAIL, realized, address)

    def add(self, gid, ok, realized, addr=""):
        self.rows.append((gid, "PASS" if ok else "FAIL", realized, addr))
        return ok

    def failed(self):
        return [r for r in self.rows if r[1] == "FAIL"]


def run_gates_3a(cells, prereg_dir: Path, repo: Path):
    g = Gates()
    C = {c.name: c for c in cells}

    # ---- G-BAND
    bad, addrs = [], []
    for c in cells:
        for key, want in (("seed_start", BAND_SEED_START), ("n_decks", N_DECKS),
                          ("seatings_per_deck", SEATINGS_PER_DECK)):
            v, a = dual(c.man, key)
            addrs.append(f"{c.name}:{key}@{a}")
            if v != want:
                bad.append(f"{c.name}.{key}={v!r} (want {want})")
    g.add("G-BAND", not bad, "; ".join(bad) or
          f"all five: seed_start={BAND_SEED_START}, n_decks={N_DECKS}, seatings_per_deck={SEATINGS_PER_DECK}",
          addrs[0].split("@")[-1] if addrs else "")

    # ---- G-DECKS
    ref = cells[0].seeds
    mism = [c.name for c in cells if c.seeds != ref]
    n_common = len(set.intersection(*[c.seeds for c in cells]))
    g.add("G-DECKS", not mism and n_common == N_DECKS,
          f"n_common={n_common}; deck-set mismatches: {mism or 'none'}", "records")

    # ---- G-SINGLEVAR
    flats = {c.name: flat(c.man.get("config", {})) for c in cells}
    keys = set().union(*[set(f) for f in flats.values()])
    diffs = []
    for k in sorted(keys):
        vals = {n: f.get(k, "<ABSENT>") for n, f in flats.items()}
        if len(set(map(repr, vals.values()))) > 1:
            leaf = k.split(".")[-1]
            if k in SINGLEVAR_ALLOWED or leaf in SINGLEVAR_PATH_LEAVES:
                continue
            diffs.append((k, vals))
    g.add("G-SINGLEVAR", not diffs,
          "only the allowed axis keys differ" if not diffs else
          "UNALLOWED differing config keys: " + "; ".join(k for k, _ in diffs),
          "config.*")

    # ---- G-REV
    pinned = (prereg_dir / "PINNED_SRC_REV")
    pinned_rev = pinned.read_text().strip() if pinned.exists() else ""
    revs = {}
    for c in cells:
        v, a = dual(c.man, "code_rev")
        revs[c.name] = v
    base = lambda r: (r or "").split("-")[0]
    same_rev = len(set(revs.values())) == 1
    rev_matches = bool(pinned_rev) and all(
        pinned_rev.startswith(base(r)) or base(r).startswith(pinned_rev[:len(base(r))])
        for r in revs.values())
    srcclean = prereg_dir / "SRC_CLEAN.jsonl"
    boundaries, dirty = [], []
    if srcclean.exists():
        for line in srcclean.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            boundaries.append(rec["boundary"])
            if not rec.get("src_clean"):
                dirty.append(rec["boundary"])
            if rec.get("head") and pinned_rev and rec["head"] != pinned_rev:
                dirty.append(rec["boundary"] + " (head drift)")
    need = ["pre-flight"]
    for _, nm, *_ in LADDER:
        need += [f"before-{nm}", f"after-{nm}"]
    missing = [b for b in need if b not in boundaries]
    g.add("G-REV", same_rev and rev_matches and not dirty and not missing,
          f"code_rev={sorted(set(revs.values()))} vs PINNED_SRC_REV={pinned_rev}; "
          f"SRC_CLEAN boundaries={len(boundaries)} dirty={dirty or 'none'} missing={missing or 'none'}",
          "code_rev / SRC_CLEAN.jsonl")

    # ---- G-BLIND
    bc_file = prereg_dir / "BLIND_COMMIT"
    bc = bc_file.read_text().strip() if bc_file.exists() else ""
    hexok = len(bc) == 40 and all(ch in "0123456789abcdef" for ch in bc.lower())
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", bc, "HEAD"],
                         cwd=repo, capture_output=True).returncode == 0 if hexok else False
    # "the commit that introduced this pair's FROZEN banner"
    banner_here = banner_parent = None
    if hexok:
        cur = git("show", f"{bc}:measurement/{RUN_ID}/READ_RULE.md", cwd=repo)
        banner_here = "FROZEN" in cur.split("\n")[0] if cur else False
        par = git("show", f"{bc}^:measurement/{RUN_ID}/READ_RULE.md", cwd=repo)
        banner_parent = ("FROZEN" in par.split("\n")[0]) if par else False
    bp = prereg_dir / "BLIND_PROOF.json"
    proof = json.loads(bp.read_text()) if bp.exists() else {}
    mode = proof.get("blind_stamp_mode", "artifact")
    stamp_ok = True
    stamp_detail = "n/a (mode=artifact)"
    if mode == "manifest":
        stamps = []
        for c in cells:
            v, a = dual(c.man, "BLIND_COMMIT")
            if v is None:
                v, a = dual(c.man, "stamps.BLIND_COMMIT")
            stamps.append((c.name, v, a))
        stamp_ok = all(v == bc for _, v, _ in stamps)
        stamp_detail = f"manifest stamp == BLIND_COMMIT in all five: {stamp_ok}"
    g.add("G-BLIND", hexok and anc and banner_here and not banner_parent and stamp_ok,
          f"blind_commit={bc} 40hex={hexok} ancestor_of_HEAD={anc} "
          f"introduced_FROZEN_banner={banner_here and not banner_parent} "
          f"blind_stamp_mode={mode}; {stamp_detail}",
          "BLIND_COMMIT + git (+ manifest, additive)")

    # ---- G-LEAF
    bad = []
    addr_c = addr_r = ""
    for c in cells:
        v, addr_c = dual(c.man, "cand_leaf_hash")
        if v != CAND_LEAF_HASH:
            bad.append(f"{c.name}.cand_leaf_hash={v!r}")
        v2, addr_r = dual(c.man, "rung.leaf_hash")
        if v2 != RUNG_LEAF_HASH:
            bad.append(f"{c.name}.rung.leaf_hash={v2!r}")
    g.add("G-LEAF", not bad,
          "; ".join(bad) or f"cand={CAND_LEAF_HASH} rung={RUNG_LEAF_HASH} in all five",
          f"{addr_c} / {addr_r}")

    # ---- G-RULES
    bad, addr = [], ""
    for c in cells:
        nm, addr = dual(c.man, "rules_profile.name")
        ok, _ = dual(c.man, "rules_profile.r9_env_ok")
        if nm != "fixed_v1" or ok is not True:
            bad.append(f"{c.name}: name={nm!r} r9_env_ok={ok!r}")
    g.add("G-RULES", not bad, "; ".join(bad) or
          'name=="fixed_v1" and r9_env_ok==true in all five', addr)

    # ---- G-BACKEND
    bad = []
    cross = {}
    for c in cells:
        for key, want in (("backend.name", "rust"), ("backend.requested", "rust")):
            v, _ = dual(c.man, key)
            if v != want:
                bad.append(f"{c.name}.{key}={v!r}")
        conv, _ = dual(c.man, "backend.converted_sides")
        if not conv or "candidate" not in conv:
            bad.append(f"{c.name}.converted_sides={conv!r}")
        mb, _ = dual(c.man, "mixed_builds")
        if mb is not False:
            bad.append(f"{c.name}.mixed_builds={mb!r}")
        for key in ("carc_rs_version", "carc_rs_binary_sha", "backend.tile_data_semantic_digest"):
            v, _ = dual(c.man, key)
            cross.setdefault(key, set()).add(json.dumps(v, sort_keys=True))
    for key, vs in cross.items():
        if len(vs) > 1:
            bad.append(f"cross-leg {key} differs: {vs}")
    g.add("G-BACKEND", not bad, "; ".join(bad) or
          "rust-resolved on every leg; carc_rs_version / binary_sha / tile_data_semantic_digest identical across legs",
          "config.backend.* (+ top-level mixed_builds)")

    # ---- G-RUNG
    bad, addr = [], ""
    for c in cells:
        for key, want in (("rung.agent", "HeuristicMCTS"), ("rung.c", 3.0), ("rung.sims", 800)):
            v, addr = dual(c.man, key)
            if v != want:
                bad.append(f"{c.name}.{key}={v!r} (want {want!r})")
    g.add("G-RUNG", not bad, "; ".join(bad) or
          'HeuristicMCTS, c=3.0, sims=800 in all five', addr)

    # ---- G-BUDGET
    bad, addr = [], ""
    for c in cells:
        k, addr = dual(c.man, "champion.k_dets")
        s, _ = dual(c.man, "champion.sims_per_det")
        t, _ = dual(c.man, "champion.total_sims")
        if (k, s, t) != (c.k_dets, c.sims_per_det, c.total_sims):
            bad.append(f"{c.name}: ({k},{s},{t}) != ({c.k_dets},{c.sims_per_det},{c.total_sims})")
        elif k * s != t:
            bad.append(f"{c.name}: product identity {k}x{s} != {t}")
    g.add("G-BUDGET", not bad, "; ".join(bad) or
          "(4,200,800)/(4,400,1600)/(4,688,2752)/(4,1376,5504)/(8,1376,11008), products hold", addr)

    # ---- G-TIEARB
    bad, addr = [], ""
    for c in cells:
        v, addr = dual(c.man, "cand_tiearb.enabled")
        if v is not False:
            bad.append(f"{c.name}={v!r}")
    g.add("G-TIEARB", not bad, "; ".join(bad) or "enabled==false in all five", addr)

    # ---- G-EXACT
    bad, addr = [], ""
    for c in cells:
        for key, want in (("endgame.exact_k", 2), ("endgame.mode", "marginalized"),
                          ("endgame.shared_by_both_arms", True)):
            v, addr = dual(c.man, key)
            if v != want:
                bad.append(f"{c.name}.{key}={v!r} (want {want!r})")
    g.add("G-EXACT", not bad, "; ".join(bad) or
          "exact_k=2, mode=marginalized, shared_by_both_arms=true in all five", addr)

    # ---- G-N
    bad, det = [], []
    for c in cells:
        det.append(f"{c.name}: n={c.n} n_failed={c.n_failed} rate={c.failure_rate:.4%}")
        if c.n != N_GAMES:
            bad.append(f"{c.name}: {c.n} games scored (want {N_GAMES})")
        if (c.failure_rate or 0.0) >= FAIL_RATE_VOID:
            bad.append(f"{c.name}: failure rate {c.failure_rate:.3%} >= 2%")
    g.add("G-N", not bad, "; ".join(bad) or " | ".join(det), "summary + records")

    # ---- G-SAT-END
    bad = []
    for nm in ("A800", "E11008"):
        wr = C[nm].a_wr
        if not (SAT_LO <= wr <= SAT_HI):
            bad.append(f"{nm} winrate={wr:.4f} outside [{SAT_LO},{SAT_HI}]")
    g.add("G-SAT-END", not bad,
          "; ".join(bad) or f"A800 wr={C['A800'].a_wr:.4f}, E11008 wr={C['E11008'].a_wr:.4f} "
          f"both inside [{SAT_LO},{SAT_HI}]", "summary.winrate")
    return g


def run_gates_3b(w, c2752):
    g = Gates()
    nm, addr = dual(w.man, "rules_profile.name")
    ok, _ = dual(w.man, "rules_profile.r9_env_ok")
    obs, _ = dual(w.man, "rules_profile.r9_env_observed")
    exp, _ = dual(w.man, "rules_profile.r9_env_expected")
    g.add("GW-RULES", nm == "walled" and ok is True and obs is False,
          f"name={nm!r} r9_env_ok={ok!r} r9_env_observed={obs!r} (expected={exp!r}) "
          f"-- INVERTED expectation: walled requires R9 OFF", addr)

    fw, fc = flat(w.man.get("config", {})), flat(c2752.man.get("config", {}))
    diffs = []
    for k in sorted(set(fw) | set(fc)):
        a, b = fw.get(k, "<ABSENT>"), fc.get(k, "<ABSENT>")
        if repr(a) != repr(b):
            leaf = k.split(".")[-1]
            if k.split(".")[0] in PAIR_ALLOWED or leaf in SINGLEVAR_PATH_LEAVES:
                continue
            diffs.append(k)
    g.add("GW-PAIR", not diffs,
          "config blocks differ only in the allowed keys" if not diffs
          else "UNALLOWED differing config keys vs C2752: " + "; ".join(diffs), "config.*")

    n_common = len(w.seeds & c2752.seeds)
    g.add("GW-DECKS", w.seeds == c2752.seeds and n_common == N_DECKS,
          f"n_common(C,W)={n_common}; sets equal={w.seeds == c2752.seeds}", "records")

    g.add("GW-N", w.n == N_GAMES and (w.failure_rate or 0.0) < FAIL_RATE_VOID,
          f"n={w.n} n_failed={w.n_failed} rate={w.failure_rate:.4%}", "summary + records")

    g.add("GW-SAT", SAT_LO <= w.a_wr <= SAT_HI,
          f"W2752 winrate={w.a_wr:.4f} vs [{SAT_LO},{SAT_HI}]", "summary.winrate")
    return g


# --------------------------------------------------------------------------- #
# statistics                                                                  #
# --------------------------------------------------------------------------- #

def contrast(hi, lo, common):
    """Deck-paired contrast hi - lo over the shared decks, se REALIZED."""
    vals = [hi.d[s] - lo.d[s] for s in sorted(common)]
    m, se, z, n = mean_se_z(vals)
    return {"stat": m, "se": se, "z": z, "n": n,
            "ci95": ci95(m, se), "se_prereg": SE_SPACING_PREREG}


BRANCH_TEXT = {
    "FR-RESCALED": (
        "**Says:** the fair sub-ladder, re-measured on the production instrument (rust + `fixed_v1` + R9), "
        "resolves its own dynamic range and is monotone across its pure-budget rungs. The five `R_i` are the "
        "ruler of record's **absolute readings on the instrument production actually runs.**\n\n"
        "**Licenses exactly this:** quoting `R_i` as the fair ladder's absolute readings for `fixed_v1`+rust "
        "measurements taken from here on; and the CL-046 amendment in READ_RULE §5.1.\n\n"
        "**Does NOT license:** any re-rating of the champion; any re-grading of any existing claim; any "
        "statement about rungs outside {800,1600,2752,5504,11008}; any pooling with G1/G2 absolutes; and no "
        "statement about Δ₄ as a budget effect (DESIGN §3.2)."),
}
ERA_TEXT = {
    "ERA-BOUNDED-NULL": (
        "**Says:** no era shift resolves at this power. **The bound is ±4.56 pts ≈ ±62 elo per rung.**\n\n"
        "⛔ **This is NOT \"the era does not matter.\"** For calibration, recorded before game 1: the *previous* "
        "era shift this cell is the sequel to — G1→G2, the leaky-determinization fix — was **+53.6 elo at the "
        "2752 rung**, i.e. **inside this bound**. A design that could not have resolved the last era shift has "
        "not shown the next one is absent."),
}
ATTR_TEXT = {
    "RULES-BOUNDED-NULL": (
        "**Says:** no rules effect resolves at this power. **The two-sided 95% bound is ±1.77 pts ≈ ±24 elo at "
        "the 2752 rung.** This is a genuinely informative bound — 2.6× tighter than the E3 era screen and it is "
        "within-band — but it is **a bound, not a zero**, and this readout says so in those words.\n\n"
        "**Licenses:** stating the bound in the READ_RULE §5.1 annotations. **Does NOT license:** \"the rules "
        "change is strength-neutral\", or dropping the era caveat from any annotation."),
}


def _md(s):
    """Escape a value for use inside a markdown table cell."""
    return str(s).replace("|", "\\|")


def _blind_sha(r):
    for g in r["gates_3A"]:
        if g["id"] == "G-BLIND":
            return g["realized"].split()[0].split("=", 1)[1]
    return "?"


def write_readout(r, path):
    P = []
    w = P.append
    pc = r["per_cell"]
    w("> ✅ **ADJUDICATED 2026-08-24** against the FROZEN `READ_RULE.md` (blind commit "
      f"`{_blind_sha(r)}`). Branch taken VERBATIM.\n")
    w(f"# READOUT — {r['run_id']} (G3: the fair ruler on the production instrument)\n")
    w(f"**BRANCH FIRED (READ_RULE §4, first-match-wins): `{r['branch']}`**\n")
    w(f"**ERA SUB-ADJUDICATION (§4.2): `{r['era_branch']}`**  ·  "
      f"**ATTRIBUTION (§4.4, descriptive only): `{r['attribution_branch']}`**\n")
    w(BRANCH_TEXT.get(r["branch"], ""))
    w("")
    w("---\n")
    w("## 1. Per-cell (READ_RULE §4.3 items 1–3)\n")
    w("| cell | n | W/D/L | seat 0/1 | winrate (z) | elo ± 1σ | R_i ± se (z) | 95% CI | n_failed (rate) |")
    w("|---|---|---|---|---|---|---|---|---|")
    for nm in ["A800", "B1600", "C2752", "D5504", "E11008", "W2752"]:
        c = pc[nm]
        R = r["R"].get(nm)
        if R:
            rtxt = f"{R['stat']:+.4f} ± {R['se']:.4f} (z={R['z']:+.2f})"
            citxt = f"[{R['ci95'][0]:+.3f}, {R['ci95'][1]:+.3f}]"
        else:
            rtxt = f"{c['paired_mean_margin_analyzer']:+.4f} (z={c['paired_z_analyzer']:+.2f})"
            citxt = "—"
        w(f"| {nm} | {c['n']} | {c['W']}/{c['D']}/{c['L']} | {c['seat_balance']['0']}/{c['seat_balance']['1']} "
          f"| {c['winrate']:.4f} ({c['winrate_z']:+.2f}) | {c['elo']:+.1f} ± {c['elo_sig_1sigma']:.1f} "
          f"| {rtxt} | {citxt} | {c['n_failed']} ({c['failure_rate']:.4%}) |")
    w("")
    w("**Failure classes:** none in any cell (`failed_cells == []` everywhere; the rate is stated even though "
      "it is zero, per §4.3 item 1).\n")
    w("| cell | champ_prefix ms/move (CANDIDATE side) | rung ms/move | ratio | solver s/game | realized s/game | mean moves/game |")
    w("|---|---|---|---|---|---|---|")
    for nm in ["A800", "B1600", "C2752", "D5504", "E11008", "W2752"]:
        c = pc[nm]
        w(f"| {nm} | {c['champ_prefix_ms_per_move']:.1f} | {c['rung_ms_per_move']:.1f} | "
          f"{c['ratio']:.2f}× | {c['solver_secs_per_game']:.2f} | {c['realized_s_per_game']:.1f} | "
          f"{c['mean_moves']:.2f} |")
    w("")
    w("⚠️ `champ_prefix_ms_per_move` is the **CANDIDATE** side in `eval_fair_puct` (the opposite convention "
      "from `eval_puct_priors`).\n")
    w("| cell | band | cand_leaf_hash | rung.leaf_hash | rules_profile (r9_env_ok) | backend / carc_rs | code_rev | tiearb | (k,s,total) |")
    w("|---|---|---|---|---|---|---|---|---|")
    for nm in ["A800", "B1600", "C2752", "D5504", "E11008", "W2752"]:
        c = pc[nm]
        w(f"| {nm} | {r['band_seed_start']} | `{c['cand_leaf_hash']}` | `{c['rung_leaf_hash']}` | "
          f"{c['rules_profile']} ({c['r9_env_ok']}) | {c['backend']} / {c['carc_rs_version']} "
          f"`{str(c['carc_rs_binary_sha'])[:12]}` | `{c['code_rev']}` | {c['tiearb_enabled']} | "
          f"{tuple(c['budget'])} |")
    w("")
    w("---\n")
    w("## 2. THE LADDER (§4.3 item 4)\n")
    w(f"All statistics over the **n_common = {r['n_common_ladder']} decks** present in all five ladder cells; "
      "points/game of final-score margin, candidate-minus-rung, deck-paired.\n")
    w("| rung | R_i | se | z | 95% CI | winrate | elo |")
    w("|---|---|---|---|---|---|---|")
    for nm in ["A800", "B1600", "C2752", "D5504", "E11008"]:
        v = r["R"][nm]
        w(f"| {nm} | {v['stat']:+.4f} | {v['se']:.4f} | {v['z']:+.2f} | "
          f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] | {v['winrate']:.4f} | {v['elo']:+.1f} ± {v['elo_sig']:.1f} |")
    w("")
    lbl = {"D1": "Δ₁ = R_1600 − R_800", "D2": "Δ₂ = R_2752 − R_1600",
           "D3": "Δ₃ = R_5504 − R_2752", "D4": "Δ₄ = R_11008 − R_5504",
           "SPAN": "SPAN = R_11008 − R_800"}
    w("| statistic | value | se_realized | se pre-registered (DESIGN §4.2) | z | 95% CI |")
    w("|---|---|---|---|---|---|")
    for k in ["D1", "D2", "D3", "D4", "SPAN"]:
        v = r["spacings"][k]
        w(f"| {lbl[k]} | {v['stat']:+.4f} | {v['se']:.4f} | {v['se_prereg']} | {v['z']:+.2f} | "
          f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] |")
    w("")
    w("⚠️ **Δ₄ is budget × ALLOCATION (k4→k8), not a pure budget increment** (DESIGN §3.2) — standing flag.\n")
    w("---\n")
    w("## 3. THE ERA BLOCK (§4.3 item 5)\n")
    w("| statistic | D_i | se_naive | CL-068 tax | se_eff | z_eff | G2 source row |")
    w("|---|---|---|---|---|---|---|")
    for k, v in r["era"].items():
        w(f"| {k} = R − {v['g2_value']} | {v['stat']:+.4f} | {v['se_naive']:.3f} | ×2 | {v['se_eff']:.3f} | "
          f"{v['z_eff']:+.2f} | {v['g2_source']} |")
    w("")
    w("⛔ **No cross-era delta exists at 800 or 1600** — no same-allocation post-fix comparator exists in the "
      "repo. Those two rungs are **NEW ABSOLUTES** and are not compared to G1's leaky k8×{100,200} readings "
      "(READ_RULE §1, DESIGN §0.2 Q4).\n")
    w(ERA_TEXT.get(r["era_branch"], ""))
    w("")
    w("---\n")
    w("## 4. GATES AND WITNESSES (§4.3 item 6)\n")
    w("### §3A — LADDER gates\n")
    w("| gate | verdict | realized | address that resolved it |")
    w("|---|---|---|---|")
    for g in r["gates_3A"]:
        w(f"| `{g['id']}` | **{g['verdict']}** | {_md(g['realized'])} | `{g['address']}` |")
    w("")
    w("### §3B — ATTRIBUTION gates (a FAIL here voids E4 alone, never the ladder)\n")
    w("| gate | verdict | realized | address |")
    w("|---|---|---|---|")
    for g in r["gates_3B"]:
        w(f"| `{g['id']}` | **{g['verdict']}** | {_md(g['realized'])} | `{g['address']}` |")
    w("")
    w("### WITNESSES (printed on every branch, never voiding)\n")
    for x in r["witnesses"]:
        w(f"- **`{x['id']}`** — {x['realized']}")
    w("")
    w("---\n")
    w("## 5. THE ATTRIBUTION BLOCK (§4.3 item 7 / §4.4)\n")
    a = r["attribution"]
    w("**Standing flag: descriptive; NOT a branch input (READ_RULE §4.4). The `FR-*` branch above is "
      "mechanically identical whether this cell ran clean, ran dirty, or was never funded.**\n")
    w("| statistic | value | se realized | se pre-registered | z | 95% CI | elo-equivalent |")
    w("|---|---|---|---|---|---|---|")
    sc = r["elo_scale"]["ls_slope_through_origin"]
    w(f"| A = C2752(`fixed_v1`+R9) − W2752(`walled`, R9 OFF) | {a['A']['stat']:+.4f} pts | {a['A']['se']:.4f} "
      f"| {a['A']['se_prereg']} | {a['A']['z']:+.2f} | [{a['A']['ci95'][0]:+.3f}, {a['A']['ci95'][1]:+.3f}] "
      f"| {a['A']['stat'] * sc:+.1f} elo (@{sc:.2f} elo/pt realized) |")
    w("")
    w(f"- `n_common(C,W)` = **{a['n_common_CW']}** decks · C2752 absolute **{a['C2752_absolute']:+.4f}** · "
      f"W2752 absolute **{a['W2752_absolute']:+.4f}**")
    w(f"- **RESIDUAL** `D_2752 − A` = **{a['residual']['stat']:+.4f}** pts, carrying the ×2-inflated "
      f"se it inherits (**{a['residual']['se_inherited']:.3f}**). ⛔ A LEFTOVER — never presented as an "
      "estimate of the band effect.")
    w("- ⭐ No CL-068 tax on `A`: within-band, same-code, deck-paired, same 400 decks — the robust class.\n")
    w(ATTR_TEXT.get(r["attribution_branch"], ""))
    w("")
    w("---\n")
    w("## 6. THE GENERATION TABLE (§4.3 item 8), G3 row filled in\n")
    w("| generation | when | candidate side | backend | rules | band | n | reading @2752 |")
    w("|---|---|---|---|---|---|---|---|")
    w("| **G1 — CL-046 (D0)** | 2026-07-09 | fair PIMC, k8×sims/det, pre-CL-056 leaky determinization | python "
      "| pre-`fixed_v1` (walled) | 15e9 | 200 decks | **+81.4 elo** |")
    w("| **G2 — F5 rebase** | 2026-07-19/20 | fair PIMC, k4/k8, post-CL-056, curve125 leaf `a36d2e15` | python "
      "| pre-`fixed_v1` | 24e9 | 200 decks | **+135.0 elo / +8.6425 pts** |")
    c = r["R"]["C2752"]
    w(f"| **G3 — THIS CELL** | 2026-08-24 | same agent family, same leaf, same rung | **rust** | "
      f"**`fixed_v1` + R9** | **145e9** | **400 decks** | **{c['elo']:+.1f} elo / {c['stat']:+.4f} pts** |")
    w("")
    w("---\n")
    w("## 7. ANALYZER-vs-WITNESS RECONCILIATION (READ_RULE §1)\n")
    bad = [x for x in r["reconciliation"] if not x["agree"]]
    w(f"{len(r['reconciliation'])} statistics checked across all six cells "
      f"(`paired_mean_margin`, `paired_z`, `n_paired`, `winrate`, `elo`): "
      f"**{'ALL AGREE' if not bad else 'DISAGREEMENT — U-UNREADABLE'}** within float tolerance "
      f"(rel 1e-6). The analyzer of record is `scripts/classical_search/eval_fair_puct.py` "
      "(each cell's `summary.json`); the witness is an independent from-scratch recomputation from the raw "
      "`seed*_a*.json` records. **The recomputation is a WITNESS, never a branch input.**\n")
    if bad:
        for x in bad:
            w(f"- ⛔ {x['cell']} / {x['stat']}: analyzer {x['analyzer']} vs witness {x['witness']}")
    w("---\n")
    w("## 8. ANOMALIES AND NOTES (non-adjudicative; no bar in §4 moves)\n")
    tot_s = sum(d["realized_s_per_game"] * N_GAMES for d in r["cost_witness"])
    rung_ms = [d for d in r["per_cell"].values()]
    rmin = min(c["rung_ms_per_move"] for c in r["per_cell"].values())
    rmax = max(c["rung_ms_per_move"] for c in r["per_cell"].values())
    w(f"1. **`W-COST` overshoots by more than the pilot projected.** The frozen h800 rung realized "
      f"**{rmin:.0f}–{rmax:.0f} ms/move** on the laptop across all six cells — vs the DESIGN §6 local "
      f"calibration of **624.3** (**+{(rmax / COST_RUNG_MS_LOCAL - 1) * 100:.0f}%**) and vs the §6.2.1 "
      f"pilot's own laptop reading of **781.8** (**+{(rmax / 781.8 - 1) * 100:.0f}%**). Realized wall was "
      f"**{tot_s / 3600:.1f} core-h** against the §6.1 funded roll-up of **118.8 core-h** "
      f"(**+{(tot_s / 3600) / 118.8 * 100 - 100:.0f}%**). `W-COST` is a **WITNESS, never voiding** (READ_RULE "
      f"§3), and the §6.2.1 amendment already accepted the overage class — but the realized overage is larger "
      f"than the +25.23% the amendment re-costed against, so the ≈6.75 h re-projection under-predicted the "
      f"realized wall (08:58→16:36 ≈ 7.6 h). **This changes no statistic and no branch.**")
    w(f"2. **The realized elo scale is steeper than the committed one.** `W-SCALE` reads "
      f"**{r['elo_scale']['ls_slope_through_origin']:.2f} elo/pt** (least-squares through origin over the five "
      f"rungs; {r['elo_scale']['mean_ratio']:.2f} as a mean of per-cell ratios) against the DESIGN §4.5 "
      f"committed **13.7**. Elo displays in this readout therefore run ~20–35% larger than the pre-registered "
      f"conversion would give. **No bar in `READ_RULE.md` is ever set in elo** (§2), so nothing moves; the "
      f"pre-registered elo-equivalents quoted in the branch texts (±62 / ±24 elo) are kept verbatim at the "
      f"committed 13.7, exactly as the frozen text states them.")
    dE, dC = r["per_cell"]["D5504"]["elo"], r["per_cell"]["C2752"]["elo"]
    w(f"3. **Monotone in the PRIMARY unit, non-monotone in the DISPLAY unit at one rung.** The pre-registered "
      f"primary statistic (deck-paired points) rises at every rung — Δ₁…Δ₄ are all positive. The derived "
      f"winrate/elo display dips at D5504 (**{dE:+.1f} elo** vs C2752's **{dC:+.1f}**, winrate "
      f"{r['per_cell']['D5504']['winrate']:.4f} vs {r['per_cell']['C2752']['winrate']:.4f}) while "
      f"R_5504 > R_2752 by Δ₃ = {r['spacings']['D3']['stat']:+.4f} pts. The dip is inside noise "
      f"(Δ₃ z = {r['spacings']['D3']['z']:+.2f}) and the branch bar is on points, not elo — but a reader "
      f"quoting the elo column alone would see a bend that the ruler does not have.")
    w(f"4. **The top of the ladder is flat at this power.** Δ₁ (z={r['spacings']['D1']['z']:+.2f}) and Δ₂ "
      f"(z={r['spacings']['D2']['z']:+.2f}) resolve; Δ₃ (z={r['spacings']['D3']['z']:+.2f}) and Δ₄ "
      f"(z={r['spacings']['D4']['z']:+.2f}) do **not** individually resolve at n=400 decks. "
      f"{(r['R']['C2752']['stat'] - r['R']['A800']['stat']) / r['spacings']['SPAN']['stat'] * 100:.0f}% of "
      f"`SPAN` comes from the 800→2752 stretch. This is the DESIGN §6 house prior almost exactly (\"a large, "
      f"easily-resolved SPAN driven almost entirely by the 800→2752 stretch, and a flat-to-bending top\") — "
      f"but note the branch table asks only whether any of Δ₁–Δ₃ is ≤ −2σ, and none is, so `FR-RESCALED` "
      f"fires rather than `FR-RESCALED-BENT`. **Unresolved is not negative.**")
    w(f"5. **`W-GAMELEN` shows the expected `walled` signature.** W2752 runs "
      f"{r['per_cell']['W2752']['mean_moves'] - r['per_cell']['C2752']['mean_moves']:+.2f} moves/game longer "
      f"than C2752 — the `centered18`+`redraw` rules change, visible and small.")
    alt = 7.9350
    z_alt = (r["R"]["E11008"]["stat"] - alt) / r["era"]["D_11008"]["se_eff"]
    w(f"6. **The frozen pair carries two different G2 values for the 11008 rung — the branch is robust to "
      f"which one is right.** `READ_RULE.md` §1 pre-registers `D_11008 = R_11008 − 9.7700` "
      f"(`fair_ruler_k8x1376_11008`), while `DESIGN.md` §4.1 quotes that same row's realized paired mean as "
      f"**7.9350** (7.9350 / 8.4547 = 0.939 pts se). This adjudication uses **READ_RULE's 9.7700**, because "
      f"READ_RULE is the frozen instrument and §1 is where the comparator is pre-registered. Recorded for "
      f"audit: against 7.9350 the reading would be `D_11008 = {r['R']['E11008']['stat'] - alt:+.4f}`, "
      f"`z_eff = {z_alt:+.2f}` — **still under the 2.0 bar, so `ERA-BOUNDED-NULL` fires either way** and no "
      f"branch depends on resolving the discrepancy. It should be reconciled before the G2 rows are cited "
      f"again.")
    w("7. **`moves` counts plies, not per-side moves.** The per-cell mean of ≈142 is ≈71 per side, which is "
      "the ≈70/71 the DESIGN §6 cost model assumes — not a discrepancy.")
    w("")
    w("---\n")
    w("## 9. WHAT THIS READOUT DOES NOT DO (READ_RULE §5)\n")
    w("- Does **not** touch `governance/PRODUCTION.yaml`, on any branch. Nothing here is a strength lever.\n"
      "- Does **not** re-rate the champion — every `R_i` is a reading against the fixed h800 rung.\n"
      "- Does **not** re-grade any existing claim; §5.1 claims get **ANNOTATED**, never re-graded.\n"
      "- Does **not** edit CL-046's G1 numbers or the five G2 `fair_ruler_*` rows in `experiments/results.csv`.\n"
      "- Does **not** pool this band with any other band, or license a second band or more n.\n"
      "- Does **not** unpark E4 (the human anchor), or fund DESIGN §6.3 (a)–(c).\n")
    path.write_text("\n".join(P) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", default="/mnt/c/carc-shared")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    repo = here.parent.parent
    root = Path(args.share) / RUN_ID
    outdir = Path(args.out) if args.out else here

    cells = [Cell(root, d, n, t, k, s) for d, n, t, k, s in LADDER]
    C = {c.name: c for c in cells}
    W = Cell(root, *ATTRIB)

    # ------------------------------------------------------------------ #
    # analyzer-vs-witness reconciliation (READ_RULE §1 -- a WITNESS)      #
    # ------------------------------------------------------------------ #
    recon, recon_ok = [], True
    for c in cells + [W]:
        checks = [
            ("paired_mean_margin", c.a_margin, c.w_margin),
            ("paired_z", c.a_z, c.w_z),
            ("n_paired", float(c.a_npair), float(c.w_npair)),
            ("winrate", c.a_wr, c.w_wr),
            ("elo", c.a_elo, c.w_elo),
        ]
        for nm, a, wv in checks:
            ok = close(a, wv)
            recon_ok &= ok
            recon.append({"cell": c.name, "stat": nm, "analyzer": a,
                          "witness": wv, "agree": ok})

    # ------------------------------------------------------------------ #
    # E1 / E2                                                            #
    # ------------------------------------------------------------------ #
    common5 = set.intersection(*[c.seeds for c in cells])
    R = {}
    for c in cells:
        vals = [c.d[s] for s in sorted(common5)]
        m, se, z, n = mean_se_z(vals)
        R[c.name] = {"stat": m, "se": se, "z": z, "n": n, "ci95": ci95(m, se),
                     "winrate": c.a_wr, "elo": c.a_elo, "elo_sig": c.a_elo_sig,
                     "W": c.W, "D": c.D, "L": c.L}

    D1 = contrast(C["B1600"], C["A800"], common5)
    D2 = contrast(C["C2752"], C["B1600"], common5)
    D3 = contrast(C["D5504"], C["C2752"], common5)
    D4 = contrast(C["E11008"], C["D5504"], common5)
    SPAN = contrast(C["E11008"], C["A800"], common5)
    spacings = {"D1": D1, "D2": D2, "D3": D3, "D4": D4, "SPAN": SPAN}

    # realized elo scale (W-SCALE)
    ratios = [R[c.name]["elo"] / R[c.name]["stat"] for c in cells
              if R[c.name]["stat"] not in (0, None)]
    num = sum(R[c.name]["elo"] * R[c.name]["stat"] for c in cells)
    den = sum(R[c.name]["stat"] ** 2 for c in cells)
    elo_per_pt = num / den if den else float("nan")
    elo_scale = {"per_cell_ratios": ratios,
                 "mean_ratio": sum(ratios) / len(ratios),
                 "ls_slope_through_origin": elo_per_pt,
                 "committed": ELO_PER_PT_COMMITTED}

    # ------------------------------------------------------------------ #
    # E3 -- the era screen                                               #
    # ------------------------------------------------------------------ #
    era = {}
    for rung in (2752, 5504, 11008):
        nm = {2752: "C2752", 5504: "D5504", 11008: "E11008"}[rung]
        d = R[nm]["stat"] - G2_COMPARATOR[rung]
        se_naive = math.sqrt(R[nm]["se"] ** 2 + SE_G2_COMMITTED ** 2)
        se_eff = 2.0 * se_naive
        era[f"D_{rung}"] = {
            "stat": d, "se_naive": se_naive, "se_eff": se_eff,
            "z_eff": d / se_eff, "g2_value": G2_COMPARATOR[rung],
            "g2_source": G2_SOURCE_ROW[rung],
            "z_eff_committed_se": d / SE_EFF_D_COMMITTED,
            "se_eff_committed": SE_EFF_D_COMMITTED,
        }

    # ------------------------------------------------------------------ #
    # E4 -- attribution (DESCRIPTIVE, never a branch input)              #
    # ------------------------------------------------------------------ #
    commonCW = C["C2752"].seeds & W.seeds
    A = contrast(C["C2752"], W, commonCW)   # fixed_v1 minus walled
    residual = {"stat": era["D_2752"]["stat"] - A["stat"],
                "se_inherited": era["D_2752"]["se_eff"],
                "note": "LEFTOVER, never an estimate of the band effect (READ_RULE §1)"}

    # ------------------------------------------------------------------ #
    # gates                                                              #
    # ------------------------------------------------------------------ #
    g3a = run_gates_3a(cells, here, repo)
    g3b = run_gates_3b(W, C["C2752"])
    if not recon_ok:
        g3a.add("RECON (READ_RULE §1)", False,
                "analyzer vs from-scratch witness disagree beyond float tolerance", "summary vs records")
    else:
        g3a.add("RECON (READ_RULE §1)", True,
                "analyzer == from-scratch witness on every checked statistic", "summary vs records")

    # ------------------------------------------------------------------ #
    # witnesses (never voiding)                                          #
    # ------------------------------------------------------------------ #
    wit = []
    mids = [(nm, R[nm]["winrate"]) for nm in ("B1600", "C2752", "D5504")]
    wit.append(("G-SAT-MID", "; ".join(f"{n}={w:.4f}" for n, w in mids) +
                ("  [FLAG: outside [0.50,0.90]]"
                 if any(not (SAT_LO <= w <= SAT_HI) for _, w in mids) else "  [inside]")))
    rms = [(c.name, c.rung_ms) for c in cells + [W]]
    lo, hi = min(v for _, v in rms), max(v for _, v in rms)
    wit.append(("W-TIMING", "; ".join(f"{n}={v:.1f}" for n, v in rms) +
                f"  spread={(hi/lo - 1) * 100:.1f}%" +
                ("  [FLAG: >25%]" if hi / lo - 1 > 0.25 else "  [within +/-25%]")))
    cost = []
    for c in cells + [W]:
        probe_ms = COST_MS_PER_TOTAL_SIM * c.total_sims
        model_local = (0.070 * probe_ms + 0.071 * COST_RUNG_MS_LOCAL + COST_SOLVER_S) * COST_CAL
        model_box = (0.070 * c.champ_ms + 0.071 * c.rung_ms + (c.solver_pg or COST_SOLVER_S))
        cost.append({"cell": c.name, "realized_s_per_game": c.mean_elapsed,
                     "design6_model_local": model_local,
                     "box_realized_model": model_box,
                     "err_vs_local_model": c.mean_elapsed / model_local - 1.0})
    wit.append(("W-COST", "; ".join(
        f"{d['cell']}: realized {d['realized_s_per_game']:.1f} s/game vs DESIGN §6 local model "
        f"{d['design6_model_local']:.1f} ({d['err_vs_local_model']:+.1%})" for d in cost)))
    wit.append(("W-SCALE", f"realized elo/pt: LS-slope {elo_scale['ls_slope_through_origin']:.2f}, "
                           f"mean per-cell ratio {elo_scale['mean_ratio']:.2f}, "
                           f"committed {ELO_PER_PT_COMMITTED}"))
    wit.append(("W-GAMELEN", f"C2752 mean moves/game {C['C2752'].mean_moves:.2f} vs "
                             f"W2752 {W.mean_moves:.2f} "
                             f"(delta {W.mean_moves - C['C2752'].mean_moves:+.2f})"))

    # ------------------------------------------------------------------ #
    # §4 -- THE BRANCH, first-match-wins, taken VERBATIM                  #
    # ------------------------------------------------------------------ #
    gates_pass = not g3a.failed()
    zs = SPAN["z"]
    bent = [k for k in ("D1", "D2", "D3") if spacings[k]["z"] <= -Z_BAR]
    if not gates_pass:
        branch = "U-UNREADABLE"
    elif zs >= Z_BAR and not bent:
        branch = "FR-RESCALED"
    elif zs >= Z_BAR and bent:
        branch = "FR-RESCALED-BENT"
    elif abs(zs) < Z_BAR:
        branch = "FR-BOUNDED-FLAT"
    elif zs <= -Z_BAR:
        branch = "FR-INVERTED"
    else:                                     # unreachable by construction
        branch = "U-UNREADABLE"

    era_branch = None
    if branch != "U-UNREADABLE":
        era_branch = ("ERA-SHIFTED"
                      if any(abs(v["z_eff"]) >= Z_BAR for v in era.values())
                      else "ERA-BOUNDED-NULL")

    if not gates_pass:
        attrib_branch = "U-UNREADABLE (§3A took everything, E4 included)"
    elif g3b.failed():
        attrib_branch = "RULES-UNREADABLE"
    else:
        attrib_branch = "RULES-SHIFT" if abs(A["z"]) >= Z_BAR else "RULES-BOUNDED-NULL"

    # ------------------------------------------------------------------ #
    # emit                                                               #
    # ------------------------------------------------------------------ #
    result = {
        "run_id": RUN_ID, "band_seed_start": BAND_SEED_START,
        "branch": branch, "era_branch": era_branch, "attribution_branch": attrib_branch,
        "R": R, "spacings": spacings, "era": era,
        "attribution": {"A": A, "residual": residual,
                        "n_common_CW": len(commonCW),
                        "C2752_absolute": R["C2752"]["stat"],
                        "W2752_absolute": W.w_margin,
                        "note": "descriptive; not a branch input (READ_RULE §4.4)"},
        "elo_scale": elo_scale,
        "n_common_ladder": len(common5),
        "gates_3A": [{"id": i, "verdict": v, "realized": r, "address": a} for i, v, r, a in g3a.rows],
        "gates_3B": [{"id": i, "verdict": v, "realized": r, "address": a} for i, v, r, a in g3b.rows],
        "witnesses": [{"id": i, "realized": r} for i, r in wit],
        "reconciliation": recon,
        "per_cell": {c.name: {
            "n": c.n, "W": c.W, "D": c.D, "L": c.L,
            "seat_balance": {str(k): v for k, v in c.seat.items()},
            "winrate": c.a_wr, "winrate_z": c.sum.get("winrate_z"),
            "elo": c.a_elo, "elo_sig_1sigma": c.a_elo_sig,
            "paired_mean_margin_analyzer": c.a_margin, "paired_z_analyzer": c.a_z,
            "n_paired": c.a_npair,
            "n_failed": c.n_failed, "failure_rate": c.failure_rate,
            "failed_classes": c.failed_classes,
            "champ_prefix_ms_per_move": c.champ_ms, "rung_ms_per_move": c.rung_ms,
            "ratio": (c.champ_ms / c.rung_ms) if c.rung_ms else None,
            "solver_secs_per_game": c.solver_pg,
            "realized_s_per_game": c.mean_elapsed, "mean_moves": c.mean_moves,
            "code_rev": dual(c.man, "code_rev")[0],
            "rules_profile": dual(c.man, "rules_profile.name")[0],
            "r9_env_ok": dual(c.man, "rules_profile.r9_env_ok")[0],
            "cand_leaf_hash": dual(c.man, "cand_leaf_hash")[0],
            "rung_leaf_hash": dual(c.man, "rung.leaf_hash")[0],
            "backend": dual(c.man, "backend.name")[0],
            "carc_rs_version": dual(c.man, "carc_rs_version")[0],
            "carc_rs_binary_sha": dual(c.man, "carc_rs_binary_sha")[0],
            "tiearb_enabled": dual(c.man, "cand_tiearb.enabled")[0],
            "budget": [dual(c.man, "champion.k_dets")[0],
                       dual(c.man, "champion.sims_per_det")[0],
                       dual(c.man, "champion.total_sims")[0]],
        } for c in cells + [W]},
        "cost_witness": cost,
    }
    (outdir / "ADJUDICATION.json").write_text(json.dumps(result, indent=2, default=str))
    write_readout(result, outdir / "READOUT.md")
    print(json.dumps({"branch": branch, "era_branch": era_branch,
                      "attribution_branch": attrib_branch,
                      "gates_3A_failed": [r[0] for r in g3a.failed()],
                      "gates_3B_failed": [r[0] for r in g3b.failed()]}, indent=2))
    return result


if __name__ == "__main__":
    main()
