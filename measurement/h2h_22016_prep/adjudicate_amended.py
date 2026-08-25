#!/usr/bin/env python3
"""
22016-vs-11008 DIRECT BUDGET HEAD-TO-HEAD — THE ADJUDICATOR.

Committed in the SAME blind commit as `READ_RULE.md`, BEFORE the band is
claimed, BEFORE game 1, and BEFORE any statistic of this cell exists
(READ_RULE.md's own blind-ordering discipline, §0 / §7). `READ_RULE.md` is
NORMATIVE — this file is a literal implementation of its §3 gate table, §3.1
VOID logic, and §4 branch table. Where this file and `READ_RULE.md` disagree,
`READ_RULE.md` is right and this file has a bug.

There is no separate "frozen analyzer" for this cell: the per-cell ANALYZER OF
RECORD is `scripts/classical_search/eval_fair_puct.py`, which writes each
cell's `summary.json` / `manifest.json`. READ_RULE §7's "witness" convention is
implemented as:

  * ANALYZER value — read verbatim off the cell's `summary.json` (and, via the
    address-resolution helper below, `manifest.json` where the analyzer's real
    field placement differs from where READ_RULE's prose names it).
  * WITNESS value  — recomputed from scratch here, from the raw per-game
    `seed*_a*.json` records, via an independent re-implementation of
    `eval_fair_puct._paired_z`'s per-deck seat-balanced margin
    (`paired_deltas` / `mean_se_z` below).
  * Disagreement beyond float tolerance -> the `RECON` gate FAILs -> VOID.

FIELD-ADDRESS NOTE (read this before trusting any gate's "resolved_address"):
`READ_RULE.md` §3 states several addresses as "cell `summary.json` -> ...".
Reading `scripts/classical_search/eval_fair_puct.py` directly shows this is
only sometimes literally true — e.g. `rules_profile.*`, `cand_tiearb`,
`mixed_builds`, `carc_rs_version` are written at `manifest.json`'s TOP LEVEL
(not inside `summary.json`, and not inside `manifest.json`'s own `config`
block either); `champion.*` / `endgame.*` / `opponent.*` / `backend.*` /
`cand_leaf_hash` / `code_rev` / `seed_start` / `n_decks` /
`seatings_per_deck` live inside `manifest.json`'s `config` block; and
`summary.json` itself carries only flat top-level stats (and spells the game
count `n`, not `n_scored`). `resolve()` below is the ordered
address-resolution helper §3's own text calls for: for each candidate dotted
path it tries, in order, `summary.json` top level, `summary.json` `config.*`,
`manifest.json` top level, then `manifest.json` `config.*` — and records
WHICH of those four resolved. A field absent from all four is FAIL, never a
silent skip (`resolve()` returns `(None, None)` and every gate treats that as
an unmet proposition).

CLI:
    python3 adjudicate.py [--run-dir PATH] [--out PATH] [--selftest]

`--selftest` builds synthetic fixtures under `tempfile.TemporaryDirectory()`
and runs the SAME gate/witness/branch code this file uses for a real cell —
see `run_selftest()`. It must be run and must pass before this file's verdict
on the real archive is trusted (READ_RULE.md §7 item 6).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------- #
# MODULE-LEVEL CONSTANTS NOT CARRIED IN WORKERS.conf.                          #
# Everything that DOES live in WORKERS.conf is read at runtime by             #
# `load_workers_conf()` below and never duplicated here — see that docstring. #
# --------------------------------------------------------------------------- #

# READ_RULE.md §3 G-SAT — the win-rate rail window (a symmetric, wider window
# than d1-rebase's one-sided [0.50,0.90] because this cell grades a champion
# against ITSELF at two budgets, not against a deliberately weaker rung).
G_SAT_LO, G_SAT_HI = 0.35, 0.65

# READ_RULE.md §3 G-N — "a nonzero failure rate < 2% is REPORTED, not
# silently absorbed, and does not by itself void". This is the void bar.
G_N_FAIL_RATE_MAX = 0.02

# READ_RULE.md §4 — every branch bar (H-POSITIVE / H-REVERSED) is at |z| >= 2.0.
Z_BAR = 2.0

# READ_RULE.md §1/§2.2 — the in-family elo-per-point bracket, both endpoints
# already stated in READ_RULE.md §2.2 (not invented here): the closest-analogue
# direct budget head-to-head (`cl060_h2h_k8x1376_vs_deploy_k4x688`, 16.74
# elo/pt) and the same-family width contrast (`width_k4x2752_vs_k8x1376_
# fixed11008_n800_b119e9`, 19.35 elo/pt). Used ONLY as the display-side unit
# conversion for `H-NULL-BOUND`, where this cell's own elo_D/D ratio is a
# quotient of two near-zero, independently-noisy quantities and is not
# reportable (READ_RULE.md §1 "THE ELO CONVERSION IS GUARDED"). Never a
# branch input.
ELO_PER_POINT_BRACKET = (16.74, 19.35)

# READ_RULE.md §3 RECON — analyzer-vs-witness float tolerance (house
# precedent, `track_d1_fair_rebase/adjudicate.py`'s own `close()`).
TOL_REL = 1e-6
TOL_ABS = 1e-9

# The repo-relative path `git show <sha>:<path>` reads for the G-BLIND FROZEN-
# banner check (READ_RULE.md §3 G-BLIND). Matches this file's own location.
READ_RULE_RELPATH = "measurement/h2h_22016_prep/READ_RULE.md"

DEFAULT_RUN_DIR = (
    "/home/doctor/projects/carcassone/measurement/h2h_22016_20260824/"
    "h2h_k16x1376_vs_champ_k8x1376"
)
DEFAULT_OUT_NAME = "ADJUDICATION.json"

SCHEMA_VERSION = 1


# --------------------------------------------------------------------------- #
# WORKERS.conf — simple KEY=VALUE shell-line parser. No second copy of any     #
# pinned constant lives in this file; every numeric/string pin used by a gate #
# below is read from the conf dict at call time.                              #
# --------------------------------------------------------------------------- #

def load_workers_conf(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        # Conservative inline-comment strip: only a "  # ..." with a leading
        # space is treated as a comment (no value in this conf embeds '#').
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def conf_int(conf: dict, key: str) -> int:
    return int(conf[key])


def conf_float(conf: dict, key: str) -> float:
    return float(conf[key])


# --------------------------------------------------------------------------- #
# Small generic dict utilities.                                                #
# --------------------------------------------------------------------------- #

def nested_get(d, dotted: str):
    """Traverse `d` along a dotted path. Returns (value, found)."""
    if not isinstance(d, dict):
        return None, False
    cur = d
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None, False
    return cur, True


# The four addresses READ_RULE.md §3's own text licenses ("read at the
# manifest top level, then at `config.*`") — extended (per this task's
# instructions) to the sibling `manifest.json` as the documented alternate
# spelling, because that is where `eval_fair_puct.py` ACTUALLY places most of
# these fields. See the module docstring's FIELD-ADDRESS NOTE.
_SOURCES = (("summary", ""), ("summary", "config."), ("manifest", ""), ("manifest", "config."))


def resolve(summary: dict, manifest: dict, *candidates: str):
    """Ordered address resolution. Tries each candidate dotted path against
    summary-top, summary.config.*, manifest-top, manifest.config.*, in that
    order; tries the next candidate spelling only after all four sources miss
    the current one. Returns (value, address) or (None, None) — ABSENT IS
    FAIL, never a silent skip; callers must treat `address is None` as a
    failed resolution, not as "value is None but found"."""
    docs = {"summary": summary, "manifest": manifest}
    for cand in candidates:
        for doc_name, prefix in _SOURCES:
            val, found = nested_get(docs[doc_name], prefix + cand)
            if found:
                return val, f"{doc_name}.{prefix}{cand}"
    return None, None


def flatten(o, prefix: str = "") -> dict:
    """Flatten a nested dict/list into {dotted_path: scalar-or-json}."""
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(o, list):
        out[prefix] = json.dumps(o, sort_keys=True, default=str)
    else:
        out[prefix] = o
    return out


def set_path(d: dict, dotted: str, value) -> dict:
    """Mutate `d` in place, creating intermediate dicts as needed, and return it."""
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value
    return d


def hexok(s) -> bool:
    return isinstance(s, str) and len(s) == 40 and all(c in "0123456789abcdef" for c in s.lower())


def close(a, b) -> bool:
    """READ_RULE.md §3 RECON tolerance: rel 1e-6 / abs 1e-9. `None` only closes
    to `None` (an analyzer field that is genuinely absent must witness absent
    too, not merely small)."""
    if a is None or b is None:
        return a is None and b is None
    try:
        af, bf = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    return abs(af - bf) <= max(TOL_ABS, TOL_REL * max(abs(af), abs(bf)))


# --------------------------------------------------------------------------- #
# Statistics — the WITNESS (READ_RULE.md §1 / §7 item 2), an independent      #
# re-implementation of `eval_fair_puct._paired_z`'s per-deck seat-balanced     #
# margin, and `elo_from_wr` (house idiom, `track_d1_fair_rebase/adjudicate.py`).#
# --------------------------------------------------------------------------- #

def paired_deltas(records: list[dict]) -> dict[int, float]:
    """d(seed) = (diff[a_seat=0] + diff[a_seat=1]) / 2, over decks with BOTH
    seatings present. `diff` is candidate-minus-opponent (eval_fair_puct's own
    convention, per-game, from the candidate's a_seat)."""
    by_seed: dict = {}
    for r in records:
        seed, a_seat, diff = r.get("seed"), r.get("a_seat"), r.get("diff")
        if seed is None or a_seat is None or diff is None:
            continue
        by_seed.setdefault(seed, {})[a_seat] = diff
    return {s: (v[0] + v[1]) / 2.0 for s, v in by_seed.items() if 0 in v and 1 in v}


def mean_se_z(vals: list[float]):
    n = len(vals)
    if n < 2:
        return None, None, None, n
    m = sum(vals) / n
    var = sum((x - m) ** 2 for x in vals) / (n - 1)
    se = math.sqrt(var / n)
    z = m / se if se > 0 else float("nan")
    return m, se, z, n


def elo_from_wr(wr, n):
    if wr is None or not n or not (0 < wr < 1):
        return None, None
    elo = 400.0 * math.log10(wr / (1 - wr))
    sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    return elo, sig


# --------------------------------------------------------------------------- #
# git helpers (G-BLIND).                                                       #
# --------------------------------------------------------------------------- #

def _run_git(repo: Path, *args, timeout=15):
    try:
        return subprocess.run(["git", "-C", str(repo), *args],
                               capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def git_is_ancestor(repo: Path, sha: str) -> bool:
    r = _run_git(repo, "merge-base", "--is-ancestor", sha, "HEAD")
    return bool(r) and r.returncode == 0


def git_show(repo: Path, rev: str, relpath: str):
    r = _run_git(repo, "show", f"{rev}:{relpath}")
    return r.stdout if (r is not None and r.returncode == 0) else None


# --------------------------------------------------------------------------- #
# Gate collector — (id, passed, proposition, resolved_address, observed).      #
# --------------------------------------------------------------------------- #

@dataclass
class GateRow:
    id: str
    passed: bool
    proposition: str
    resolved_address: str
    observed: str


def mk(gid, ok, proposition, address, observed) -> GateRow:
    return GateRow(gid, bool(ok), proposition, address, observed)


class Gates:
    def __init__(self):
        self.rows: list[GateRow] = []

    def add(self, row: GateRow) -> GateRow:
        self.rows.append(row)
        return row

    def failed(self) -> list[GateRow]:
        return [r for r in self.rows if not r.passed]

    def by_id(self, gid):
        return next((r for r in self.rows if r.id == gid), None)


# --------------------------------------------------------------------------- #
# §3 GATES.                                                                    #
# --------------------------------------------------------------------------- #

def gate_band(summary, manifest, conf) -> GateRow:
    want_seed = conf_int(conf, "DECK_SEED_START")
    want_ndecks = conf_int(conf, "N_DECKS")
    want_seatings = 2
    checks = {}
    for name, cands, want in (
        ("seed_start", ("seed_start", "band_seed_start"), want_seed),
        ("n_decks", ("n_decks",), want_ndecks),
        ("seatings_per_deck", ("seatings_per_deck",), want_seatings),
    ):
        val, addr = resolve(summary, manifest, *cands)
        checks[name] = (val, addr, want, val == want)
    ok = all(v[3] for v in checks.values())
    observed = "; ".join(f"{k}={v[0]!r}@{v[1]} (want {v[2]!r})" for k, v in checks.items())
    address = "; ".join(f"{k}->{v[1]}" for k, v in checks.items())
    return mk("G-BAND", ok,
               f"config.seed_start=={want_seed}, config.n_decks=={want_ndecks}, "
               f"config.seatings_per_deck=={want_seatings}", address, observed)


def gate_decks(records: list[dict], conf) -> tuple[GateRow, int]:
    lo = conf_int(conf, "DECK_SEED_START")
    hi = conf_int(conf, "DECK_SEED_END")
    want_n = conf_int(conf, "N_DECKS")
    by_seed: dict[int, set] = {}
    for r in records:
        s, a = r.get("seed"), r.get("a_seat")
        if s is None or a is None:
            continue
        by_seed.setdefault(s, set()).add(a)
    out_of_range = sorted(s for s in by_seed if not (lo <= s <= hi))
    singleton = sorted(s for s, seats in by_seed.items() if seats != {0, 1})
    n_common = sum(1 for seats in by_seed.values() if seats == {0, 1})
    ok = (not out_of_range) and (not singleton) and (n_common == want_n)
    observed = (f"n_common={n_common} (want {want_n}); "
                f"out_of_range={out_of_range[:5]}{'...' if len(out_of_range) > 5 else ''}; "
                f"single_seat={singleton[:5]}{'...' if len(singleton) > 5 else ''}")
    row = mk("G-DECKS", ok,
              f"every realized deck_seed in [{lo},{hi}]; every counted deck has both a_seat "
              f"0 and 1; n_common=={want_n}", "raw seed*_a*.json records (adjudicator's own collection)",
              observed)
    return row, n_common


_SINGLEVAR_MUST_DIFFER = (
    ("champion.k_dets", "opponent.k_dets"),
    ("champion.total_sims", "opponent.total_sims"),
)
_SINGLEVAR_MUST_EQUAL = (
    ("champion.sims_per_det", "opponent.sims_per_det"),
    ("cand_leaf_hash", "opponent.leaf_hash"),
    ("champion.c_puct", "opponent.champ_cfg.c_puct"),
    ("champion.tau_p", "opponent.champ_cfg.tau_p"),
    ("champion.leaf_quantize", "opponent.champ_cfg.leaf_quantize"),
    ("champion.final_select", "opponent.champ_cfg.final_select"),
    ("champion.value_norm", "opponent.champ_cfg.value_norm"),
    ("endgame.mode", "opponent.endgame.mode"),
    ("endgame.exact_k", "opponent.endgame.exact_k"),
)


def gate_singlevar(summary, manifest) -> GateRow:
    bad, obs, addrs = [], [], []
    for a_path, b_path in _SINGLEVAR_MUST_DIFFER:
        av, aa = resolve(summary, manifest, a_path)
        bv, ba = resolve(summary, manifest, b_path)
        addrs += [aa, ba]
        obs.append(f"{a_path}={av!r}@{aa} vs {b_path}={bv!r}@{ba} (must DIFFER)")
        if av is None or bv is None or av == bv:
            bad.append(f"{a_path} vs {b_path} did not differ (or one was absent)")
    for a_path, b_path in _SINGLEVAR_MUST_EQUAL:
        av, aa = resolve(summary, manifest, a_path)
        bv, ba = resolve(summary, manifest, b_path)
        addrs += [aa, ba]
        obs.append(f"{a_path}={av!r}@{aa} vs {b_path}={bv!r}@{ba} (must EQUAL)")
        if av is None or bv is None or av != bv:
            bad.append(f"{a_path} vs {b_path} differ (or one was absent)")
    ok = not bad
    return mk("G-SINGLEVAR", ok,
               "candidate/opponent config blocks differ in EXACTLY k_dets + total_sims "
               "(sims_per_det, leaf hash, search knobs, and the endgame handoff are identical)",
               "; ".join(sorted(set(a for a in addrs if a))),
               "; ".join(bad) if bad else "; ".join(obs))


def gate_rev(summary, manifest, prep_dir: Path, conf) -> GateRow:
    pinned_path = prep_dir / conf.get("PINNED_SRC_REV_FILE", "PINNED_SRC_REV")
    pinned = pinned_path.read_text().strip() if pinned_path.exists() else ""
    rev, addr = resolve(summary, manifest, "code_rev")
    srcclean_path = prep_dir / conf.get("SRC_CLEAN_LOG", "SRC_CLEAN.jsonl")
    boundaries: set[str] = set()
    dirty: list[str] = []
    if srcclean_path.exists():
        for line in srcclean_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                dirty.append(f"unparseable SRC_CLEAN.jsonl line: {line[:60]!r}")
                continue
            b = rec.get("boundary")
            boundaries.add(b)
            if not rec.get("src_clean"):
                dirty.append(f"{b}: src_clean=false")
            if rec.get("head") and pinned and rec["head"] != pinned:
                dirty.append(f"{b}: head drift ({rec['head']} != {pinned})")
    has_preflight = "pre-flight" in boundaries
    has_final_pass = any(re.match(r"^after-pass-\d+$", b or "") for b in boundaries)
    # ------------------------------------------------------------------ #
    # AMENDMENT M1 (see AMENDMENTS.md). The frozen gate compares two       #
    # DIFFERENT ENCODINGS and can therefore never pass for ANY archive of  #
    # this design:                                                         #
    #   * PINNED_SRC_REV is a full 40-hex sha (run_cells.sh writes it).    #
    #   * manifest `code_rev` is written by                                #
    #     src/carcassonne_ai/run_manifest.py::code_rev(), whose documented  #
    #     encoding is `git rev-parse --short HEAD` + "-dirty" if           #
    #     `git status --porcelain` over the WHOLE repo is non-empty.       #
    # A run of this design writes ~2,800 of its own artefacts into         #
    # measurement/ inside the repo, so "-dirty" is self-inflicted and      #
    # unavoidable. The selftest never caught this because its fixture      #
    # generator writes an idealised full-40-hex code_rev that the analyzer #
    # of record cannot emit.                                               #
    #                                                                      #
    # The SUBSTANCE of G-REV ("the code that ran is PINNED_SRC_REV, and    #
    # the source tree was clean at every boundary") is discharged by the   #
    # frozen launcher itself: run_cells.sh::assert_rev_pinned compares the #
    # FULL `git rev-parse HEAD` to pinned and FATALs on mismatch, and      #
    # src_is_clean scopes dirtiness to CODE_PATHS =                        #
    # (src engine scripts rust tests pyproject.toml setup.py). Both ran    #
    # fail-closed at all 19 recorded boundaries without firing.            #
    #                                                                      #
    # Amendment: compare in the analyzer's OWN encoding — strip an         #
    # optional "-dirty" suffix, then require the remainder be a >=7-char   #
    # hex PREFIX of the 40-hex pinned sha. The whole-repo dirty flag is    #
    # RECORDED, never silently dropped; the CODE_PATHS-scoped cleanliness  #
    # claim continues to rest on SRC_CLEAN.jsonl, unchanged.               #
    # ------------------------------------------------------------------ #
    rev_txt = rev if isinstance(rev, str) else ""
    whole_repo_dirty = rev_txt.endswith("-dirty")
    rev_hex = rev_txt[:-len("-dirty")] if whole_repo_dirty else rev_txt
    prefix_ok = (
        bool(pinned) and hexok(pinned)
        and len(rev_hex) >= 7
        and all(c in "0123456789abcdefABCDEF" for c in rev_hex)
        and pinned.lower().startswith(rev_hex.lower())
    )
    rev_ok = prefix_ok
    ok = rev_ok and not dirty and has_preflight and has_final_pass
    observed = (f"code_rev={rev!r}@{addr} vs PINNED_SRC_REV={pinned!r}; "
                f"[M1] rev_hex={rev_hex!r} is_prefix_of_pinned={prefix_ok} "
                f"whole_repo_dirty_flag={whole_repo_dirty} "
                f"(CODE_PATHS cleanliness attested by SRC_CLEAN.jsonl, not by this flag); "
                f"boundaries={sorted(b for b in boundaries if b)}; "
                f"has_pre-flight={has_preflight}; has_after-pass-N={has_final_pass}; "
                f"dirty={dirty or 'none'}")
    return mk("G-REV", ok,
               "config.code_rev == PINNED_SRC_REV; SRC_CLEAN.jsonl has a clean 'pre-flight' "
               "boundary and a clean 'after-pass-N' boundary for the final pass",
               f"{addr} + {conf.get('SRC_CLEAN_LOG', 'SRC_CLEAN.jsonl')}", observed)


def gate_blind(prep_dir: Path, repo: Path) -> GateRow:
    bc_path = prep_dir / "BLIND_COMMIT"
    bc = bc_path.read_text().strip() if bc_path.exists() else ""
    literal_pending = (bc == "PENDING")
    is_hex = hexok(bc)
    anc = git_is_ancestor(repo, bc) if is_hex else False
    banner_here = banner_parent = False
    if is_hex:
        cur = git_show(repo, bc, READ_RULE_RELPATH)
        banner_here = bool(cur) and "FROZEN" in cur.split("\n", 1)[0]
        par = git_show(repo, f"{bc}^", READ_RULE_RELPATH)
        banner_parent = bool(par) and "FROZEN" in par.split("\n", 1)[0]
    proof_path = prep_dir / "BLIND_PROOF.json"
    proof = {}
    if proof_path.exists():
        try:
            proof = json.loads(proof_path.read_text())
        except Exception:
            proof = {}
    proof_ok = proof.get("is_ancestor_of_head") is True
    ok = is_hex and not literal_pending and anc and banner_here and (not banner_parent) and proof_ok
    observed = (f"BLIND_COMMIT={bc!r} hex40={is_hex} literal_PENDING={literal_pending} "
                f"ancestor_of_HEAD={anc} introduced_FROZEN_banner={banner_here and not banner_parent} "
                f"BLIND_PROOF.is_ancestor_of_head={proof.get('is_ancestor_of_head')!r}")
    return mk("G-BLIND", ok,
               "BLIND_COMMIT is a 40-hex sha (not the literal PENDING), an ancestor of HEAD, "
               "the commit that introduced this pair's FROZEN banner, and BLIND_PROOF.json agrees",
               "BLIND_COMMIT + BLIND_PROOF.json + `git merge-base --is-ancestor`", observed)


def gate_leaf(summary, manifest, conf) -> GateRow:
    want = conf.get("PROD_LEAF_HASH")
    cand, a1 = resolve(summary, manifest, "cand_leaf_hash")
    opp, a2 = resolve(summary, manifest, "opponent.leaf_hash")
    ok = (cand == want) and (opp == want) and want is not None
    return mk("G-LEAF", ok, f'config.cand_leaf_hash == opponent leaf hash == "{want}"',
               f"{a1} / {a2}", f"cand={cand!r}@{a1}; opp={opp!r}@{a2}; want={want!r}")


def gate_rules(summary, manifest, conf) -> GateRow:
    want = conf.get("RULES_PROFILE")
    name, a1 = resolve(summary, manifest, "rules_profile.name")
    ok_flag, a2 = resolve(summary, manifest, "rules_profile.r9_env_ok")
    obs_flag, a3 = resolve(summary, manifest, "rules_profile.r9_env_observed")
    ok = (name == want) and (ok_flag is True) and (obs_flag is True)
    return mk("G-RULES", ok,
               f'rules_profile.name=="{want}" AND r9_env_ok==true AND r9_env_observed==true',
               a1 or "rules_profile.*",
               f"name={name!r}@{a1}; r9_env_ok={ok_flag!r}@{a2}; r9_env_observed={obs_flag!r}@{a3}")


def gate_backend(summary, manifest) -> GateRow:
    name, a1 = resolve(summary, manifest, "backend.name")
    req, a2 = resolve(summary, manifest, "backend.requested")
    mixed, a3 = resolve(summary, manifest, "mixed_builds")
    conv, a4 = resolve(summary, manifest, "backend.converted_sides")
    conv_ok = isinstance(conv, list) and conv == ["candidate", "opponent"]
    ok = (name == "rust") and (req == "rust") and (mixed is False) and conv_ok
    return mk("G-BACKEND", ok,
               'backend.name=="rust", backend.requested=="rust", mixed_builds==false, '
               'backend.converted_sides==["candidate","opponent"]',
               f"{a1} / {a3} / {a4}",
               f"name={name!r}@{a1}; requested={req!r}@{a2}; mixed_builds={mixed!r}@{a3}; "
               f"converted_sides={conv!r}@{a4}")


def gate_budget(summary, manifest, conf) -> GateRow:
    want_f = (conf_int(conf, "F_K_DETS"), conf_int(conf, "F_SIMS_PER_DET"), conf_int(conf, "F_TOTAL_SIMS"))
    want_e = (conf_int(conf, "E_K_DETS"), conf_int(conf, "E_SIMS_PER_DET"), conf_int(conf, "E_TOTAL_SIMS"))
    fk, a1 = resolve(summary, manifest, "champion.k_dets")
    fs, a2 = resolve(summary, manifest, "champion.sims_per_det")
    ft, a3 = resolve(summary, manifest, "champion.total_sims")
    ek, b1 = resolve(summary, manifest, "opponent.k_dets")
    es, b2 = resolve(summary, manifest, "opponent.sims_per_det")
    et, b3 = resolve(summary, manifest, "opponent.total_sims")
    f_tuple, e_tuple = (fk, fs, ft), (ek, es, et)
    product_ok = (isinstance(fk, (int, float)) and isinstance(fs, (int, float)) and fk * fs == ft
                  and isinstance(ek, (int, float)) and isinstance(es, (int, float)) and ek * es == et)
    ok = (f_tuple == want_f) and (e_tuple == want_e) and product_ok
    return mk("G-BUDGET", ok,
               f"candidate (k_dets,sims_per_det,total_sims)=={want_f}, opponent=={want_e}, "
               "and k*s==total on both sides",
               f"{a1}/{a2}/{a3} ; {b1}/{b2}/{b3}",
               f"candidate={f_tuple} (want {want_f}); opponent={e_tuple} (want {want_e}); "
               f"product_identity_holds={product_ok}")


def gate_tiearb(summary, manifest) -> GateRow:
    enabled, addr = resolve(summary, manifest, "cand_tiearb.enabled")
    cand_ok = (enabled is False) or (enabled is None)
    flat_keys = list(flatten(manifest).keys()) + list(flatten(summary).keys())
    # Scan EVERY path segment, not just the leaf: a stray armed key can be an
    # object several levels down (e.g. a top-level "opp_tiearb": {"enabled":
    # true} flattens to "opp_tiearb.enabled", whose LEAF is "enabled" — only
    # the *middle* segment "opp_tiearb" carries the tell-tale name).
    # ------------------------------------------------------------------ #
    # AMENDMENT M2 (see AMENDMENTS.md). READ_RULE.md §3 G-TIEARB itself    #
    # pre-registers this exact class as a FALSE VOID, verbatim: "A future  #
    # harness that starts emitting a benign disarmed `tiearb`-named field  #
    # would therefore trip this gate; that is a false VOID, which is the   #
    # recoverable direction, and the fix is to amend the gate, never to    #
    # relax it into interpreting armed-ness."                              #
    #                                                                      #
    # eval_fair_puct.py mirrors the CANDIDATE's arbiter config into the    #
    # candidate's own champion block as six flat `tiearb_*` fields, on     #
    # EVERY run, armed or not. Those fields are byte-identical to the      #
    # `cand_tiearb` subtree §3 already exempts — they are an ALIAS of it,  #
    # not a new subtree. DEVIATIONS.md §9 bar 4 records this alias by name #
    # BEFORE game 1 ("cand_tiearb.enabled == false, champion.tiearb_       #
    # enabled == false") and reads it as evidence FOR disarmament.         #
    #                                                                      #
    # So: recognise the alias as part of the exempt subtree, and apply     #
    # §3's OWN conjunct (a) armed-ness test to it. This does NOT relax the #
    # gate into interpreting an unknown key's armed-ness — every other     #
    # tiearb-named path segment (notably `opp_tiearb.*`) still FAILs on    #
    # PRESENCE, exactly as written.                                        #
    # ------------------------------------------------------------------ #
    CAND_ALIAS_PREFIX = "config.champion.tiearb_"
    alias_keys = sorted(k for k in flat_keys if k.startswith(CAND_ALIAS_PREFIX))
    alias_armed, alias_addr = resolve(summary, manifest, "champion.tiearb_enabled")
    alias_ok = (alias_armed is False) or (alias_armed is None)
    stray = sorted({k for k in flat_keys
                     if any(seg != "cand_tiearb" and "tiearb" in seg.lower() for seg in k.split("."))
                     and not k.startswith(CAND_ALIAS_PREFIX)})
    ok = cand_ok and alias_ok and not stray
    observed = (f"cand_tiearb.enabled={enabled!r}@{addr}; "
                f"[M2] cand-alias champion.tiearb_enabled={alias_armed!r}@{alias_addr} "
                f"over alias keys={alias_keys or 'none'}; "
                f"stray tiearb-named keys (alias excluded)={stray or 'none'}")
    return mk("G-TIEARB", ok,
               "cand_tiearb absent or enabled==false, and no other *tiearb* key resolves "
               "anywhere in the manifest/summary (the opponent side is structurally disarmed)",
               addr or "cand_tiearb.enabled", observed)


def gate_exact(summary, manifest, conf) -> GateRow:
    want_k = conf_int(conf, "EXACT_K")
    mode1, a1 = resolve(summary, manifest, "endgame.mode")
    k1, a2 = resolve(summary, manifest, "endgame.exact_k")
    mode2, a3 = resolve(summary, manifest, "opponent.endgame.mode")
    k2, a4 = resolve(summary, manifest, "opponent.endgame.exact_k")
    ok = (mode1 == "marginalized") and (k1 == want_k) and (mode2 == "marginalized") and (k2 == want_k)
    return mk("G-EXACT", ok,
               f'config.endgame.exact_k=={want_k}, mode=="marginalized", identical on the '
               "opponent side",
               f"{a1}/{a2} ; {a3}/{a4}",
               f"candidate: mode={mode1!r}@{a1} exact_k={k1!r}@{a2}; "
               f"opponent: mode={mode2!r}@{a3} exact_k={k2!r}@{a4}")


def gate_n(summary, manifest, n_common: int, conf) -> GateRow:
    want_games = conf_int(conf, "N_GAMES")
    floor = conf_int(conf, "N_COMMON_FLOOR")
    n_val, a1 = resolve(summary, manifest, "n_scored", "n")
    nf_val, a2 = resolve(summary, manifest, "n_failed")
    rate = None
    if isinstance(nf_val, (int, float)) and isinstance(n_val, (int, float)) and (n_val + nf_val) > 0:
        rate = nf_val / (n_val + nf_val)
    short = n_val != want_games
    rate_bad = rate is not None and rate >= G_N_FAIL_RATE_MAX
    floor_bad = n_common < floor
    ok = not (short or rate_bad or floor_bad)
    observed = (f"n_scored(summary)={n_val!r}@{a1} (want {want_games}); n_failed={nf_val!r}@{a2}; "
                f"failure_rate={rate!r} (void bar >= {G_N_FAIL_RATE_MAX:.0%}); "
                f"n_common(records)={n_common} (floor {floor})")
    return mk("G-N", ok,
               f"n_scored=={want_games}; failure rate < {G_N_FAIL_RATE_MAX:.0%}; n_common >= {floor}",
               a1 or "n_scored/n", observed)


def gate_sat(summary, manifest) -> GateRow:
    wr, addr = resolve(summary, manifest, "winrate")
    ok = isinstance(wr, (int, float)) and G_SAT_LO <= wr <= G_SAT_HI
    return mk("G-SAT", ok, f"winrate in [{G_SAT_LO},{G_SAT_HI}]", addr or "winrate", f"winrate={wr!r}@{addr}")


def compute_recon(summary, manifest, witness: dict):
    """READ_RULE.md §3 RECON: analyzer (verbatim off summary.json, via the
    resolver) vs witness (recomputed from raw records). Returns (ok, rows)."""
    checks = [
        ("paired_mean_margin", witness["D"]),
        ("paired_z", witness["z_D"]),
        ("n_paired", None if witness["n_common"] is None else float(witness["n_common"])),
        ("winrate", witness["winrate"]),
        ("elo", witness["elo_D"]),
    ]
    rows, ok = [], True
    for name, wv in checks:
        av, addr = resolve(summary, manifest, name)
        if name == "n_paired":
            agree = close(None if av is None else float(av), wv)
        else:
            agree = close(av, wv)
        ok &= agree
        rows.append({"stat": name, "analyzer": av, "witness": wv, "address": addr, "agree": agree})
    return ok, rows


def gate_recon(summary, manifest, witness: dict) -> tuple[GateRow, list]:
    ok, rows = compute_recon(summary, manifest, witness)
    observed = "; ".join(f"{r['stat']}: analyzer={r['analyzer']!r}@{r['address']} "
                          f"witness={r['witness']!r} agree={r['agree']}" for r in rows)
    row = mk("RECON", ok,
              "the analyzer's own summary.json value and the from-scratch witness recomputation "
              "agree (rel 1e-6 / abs 1e-9) on paired_mean_margin, paired_z, n_paired, winrate, elo",
              "summary.* (and manifest.* via the resolver) vs raw seed*_a*.json records", observed)
    return row, rows


# --------------------------------------------------------------------------- #
# §3.1 VOID.                                                                    #
# --------------------------------------------------------------------------- #

def void_check(gates: Gates, run_dir: Path, prep_dir: Path, conf: dict):
    """READ_RULE.md §3.1: VOID fires on ANY §3 gate FAIL, OR a missing
    DONE_cell sentinel, OR a launcher FAILED_* abort sentinel present in the
    prep dir. Sentinel names match `run_cells.sh`'s own literal conventions:
    `DONE_cell_$OUT_CELL` and `FAILED_*`, both written in the PREP dir (the
    launcher's own `$DIR`), not the run dir."""
    reasons = []
    failed_ids = [r.id for r in gates.rows if not r.passed]
    if failed_ids:
        reasons.append(f"gate(s) FAILED: {', '.join(failed_ids)}")
    out_cell = conf.get("OUT_CELL", "")
    done_sentinel = prep_dir / f"DONE_cell_{out_cell}"
    if not done_sentinel.exists():
        reasons.append(f"missing DONE sentinel: {done_sentinel.name}")
    aborts = sorted(p.name for p in prep_dir.glob("FAILED_*"))
    if aborts:
        reasons.append(f"launcher abort sentinel(s) present in prep dir: {aborts}")
    return bool(reasons), reasons, failed_ids


# --------------------------------------------------------------------------- #
# Branch table (READ_RULE.md §4) + the display-only elo scale (§0/§2).         #
# --------------------------------------------------------------------------- #

def branch_decide(void_fired: bool, z_D):
    if void_fired or z_D is None:
        return "U-UNREADABLE"
    if z_D >= Z_BAR:
        return "H-POSITIVE"
    if z_D <= -Z_BAR:
        return "H-REVERSED"
    return "H-NULL-BOUND"


def compute_display(witness: dict, z_D) -> dict:
    """READ_RULE.md §1 "THE ELO CONVERSION IS GUARDED": this cell's own
    `elo_per_point = elo_D / D` is a quotient of two independently-noisy
    near-zero quantities exactly where H-NULL-BOUND (the branch this design
    expects to land on, §0) makes D ~ 0 by construction — unguarded, that
    ratio is unbounded and sign-unstable, and would turn a division artifact
    into the printed headline elo bound. The rule, branch-dependent:

      |z_D| >= 2.0 (H-POSITIVE / H-REVERSED, D well away from zero):
          limb "own-ratio" — report THIS cell's realized elo_D/D, cross-
          checked (witness only, never a branch input) against the in-family
          ELO_PER_POINT_BRACKET.
      otherwise (H-NULL-BOUND):
          limb "pinned-bracket" — this cell's own ratio is NOT reportable;
          the 2-sigma points bound is instead converted through BOTH pinned
          bracket endpoints as a range, labelled as a unit conversion, not a
          measured scale.

    Never a branch input either way — `display` never feeds `branch_decide`."""
    D, SE_D, elo_D = witness["D"], witness["SE_D"], witness["elo_D"]
    two_sigma_pts = 2 * SE_D if SE_D is not None else None
    lo_b, hi_b = ELO_PER_POINT_BRACKET

    if z_D is not None and abs(z_D) >= Z_BAR and elo_D is not None and D not in (None, 0):
        elo_per_point = elo_D / D
        outside_bracket = not (min(lo_b, hi_b) <= abs(elo_per_point) <= max(lo_b, hi_b))
        two_sigma_elo = abs(elo_per_point) * two_sigma_pts if two_sigma_pts is not None else None
        return {"limb": "own-ratio", "elo_per_point": elo_per_point,
                "elo_per_point_bracket": list(ELO_PER_POINT_BRACKET),
                "elo_per_point_outside_bracket": outside_bracket,
                "elo_D": elo_D, "two_sigma_pts": two_sigma_pts,
                "two_sigma_elo": two_sigma_elo, "two_sigma_elo_lo": None, "two_sigma_elo_hi": None}

    two_sigma_elo_lo = two_sigma_pts * lo_b if two_sigma_pts is not None else None
    two_sigma_elo_hi = two_sigma_pts * hi_b if two_sigma_pts is not None else None
    return {"limb": "pinned-bracket", "elo_per_point": None,
            "elo_per_point_bracket": list(ELO_PER_POINT_BRACKET),
            "elo_per_point_outside_bracket": None,
            "elo_D": elo_D, "two_sigma_pts": two_sigma_pts,
            "two_sigma_elo": None, "two_sigma_elo_lo": two_sigma_elo_lo, "two_sigma_elo_hi": two_sigma_elo_hi}


# --------------------------------------------------------------------------- #
# Archive loading.                                                             #
# --------------------------------------------------------------------------- #

def load_json_safe(path: Path):
    if not path.exists():
        return {}, f"missing: {path}"
    try:
        return json.loads(path.read_text()), None
    except Exception as e:
        return {}, f"unparseable {path}: {e}"


def load_records(run_dir: Path):
    recs, errs = [], []
    for p in sorted(run_dir.glob("seed*_a*.json")):
        try:
            recs.append(json.loads(p.read_text()))
        except Exception as e:
            errs.append(f"{p.name}: {e}")
    return recs, errs


# --------------------------------------------------------------------------- #
# THE ADJUDICATOR — orchestrates gates, witness, VOID, branch, and the emitted #
# ADJUDICATION.json / human read-out. Used identically by a real run and by    #
# every --selftest fixture (READ_RULE.md §7 item 6: "the SAME machinery").     #
# --------------------------------------------------------------------------- #

def adjudicate(run_dir: Path, prep_dir: Path, conf: dict, repo: Path) -> dict:
    summary, summary_err = load_json_safe(run_dir / "summary.json")
    manifest, manifest_err = load_json_safe(run_dir / "manifest.json")
    records, record_errs = load_records(run_dir)

    deltas = paired_deltas(records)
    D, SE_D, z_D, n_pairs = mean_se_z(list(deltas.values()))
    n_common_witness = len(deltas)
    n_scored = len(records)
    W = sum(1 for r in records if r.get("won_by_champ") is True)
    Draws = sum(1 for r in records if r.get("drew") is True)
    L = n_scored - W - Draws
    winrate = (W + 0.5 * Draws) / n_scored if n_scored else None
    elo_D, elo_sig = elo_from_wr(winrate, n_scored)

    witness = {"D": D, "SE_D": SE_D, "z_D": z_D, "n_common": n_common_witness,
               "n_scored": n_scored, "W": W, "Draws": Draws, "L": L,
               "winrate": winrate, "elo_D": elo_D, "elo_sig": elo_sig}

    gates = Gates()
    gates.add(gate_band(summary, manifest, conf))
    decks_row, n_common_decks = gate_decks(records, conf)
    gates.add(decks_row)
    gates.add(gate_singlevar(summary, manifest))
    gates.add(gate_rev(summary, manifest, prep_dir, conf))
    gates.add(gate_blind(prep_dir, repo))
    gates.add(gate_leaf(summary, manifest, conf))
    gates.add(gate_rules(summary, manifest, conf))
    gates.add(gate_backend(summary, manifest))
    gates.add(gate_budget(summary, manifest, conf))
    gates.add(gate_tiearb(summary, manifest))
    gates.add(gate_exact(summary, manifest, conf))
    gates.add(gate_n(summary, manifest, n_common_decks, conf))
    gates.add(gate_sat(summary, manifest))
    recon_row, recon_rows = gate_recon(summary, manifest, witness)
    gates.add(recon_row)

    if summary_err:
        gates.add(mk("LOAD-summary.json", False, "summary.json exists and parses", "summary.json", summary_err))
    if manifest_err:
        gates.add(mk("LOAD-manifest.json", False, "manifest.json exists and parses", "manifest.json", manifest_err))
    if record_errs:
        gates.add(mk("LOAD-records", False, "every seed*_a*.json parses", "seed*_a*.json",
                      f"{len(record_errs)} unreadable record(s): {record_errs[:5]}"))

    void_fired, void_reasons, failed_gate_ids = void_check(gates, run_dir, prep_dir, conf)
    branch = branch_decide(void_fired, z_D)

    display = compute_display(witness, z_D)

    result = {
        "schema_version": SCHEMA_VERSION,
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "branch": branch,
        "statistic": {
            "D": D, "SE_D": SE_D, "z_D": z_D, "n_common": n_common_witness,
            "n_scored": n_scored, "W": W, "D_draws": Draws, "L": L,
            "winrate": winrate, "elo_D": elo_D, "elo_sig_1sigma": elo_sig,
        },
        "display": display,
        "gates": [{"id": r.id, "passed": r.passed, "proposition": r.proposition,
                    "resolved_address": r.resolved_address, "observed": r.observed}
                   for r in gates.rows],
        "recon": recon_rows,
        "void": {"fired": void_fired, "reasons": void_reasons, "gate_ids_failed": failed_gate_ids},
        "workers_conf": dict(conf),
    }
    return result


def print_readout(result: dict) -> None:
    branch = result["branch"]
    st = result["statistic"]
    disp = result["display"]
    print()
    print("=" * 78)
    print(f"BRANCH FIRED (READ_RULE.md §4, first-match-wins, VOID first): {branch}")
    print("=" * 78)
    if branch == "U-UNREADABLE":
        print("VOID fired. No D published. Reasons:")
        for r in result["void"]["reasons"]:
            print(f"  - {r}")
    else:
        print(f"D (paired points margin, candidate-minus-opponent) = {st['D']:+.4f}")
        print(f"SE(D) = {st['SE_D']:.4f}   z_D = {st['z_D']:+.2f}   n_common = {st['n_common']} decks")
        print(f"W/D/L = {st['W']}/{st['D_draws']}/{st['L']} over n_scored={st['n_scored']} games   "
              f"winrate={st['winrate']:.4f}")
        print(f"DISPLAY ONLY (never a branch input) — limb: {disp['limb']}")
        if disp["limb"] == "own-ratio":
            flag = " ⚠️ OUTSIDE the in-family bracket" if disp["elo_per_point_outside_bracket"] else ""
            print(f"  elo_D={disp['elo_D']:+.1f}  elo/pt (this cell's own realized ratio) = "
                  f"{disp['elo_per_point']:+.2f}{flag}  (in-family bracket {ELO_PER_POINT_BRACKET})")
            if disp["two_sigma_elo"] is not None:
                print(f"  2-sigma bound = {disp['two_sigma_pts']:.4f} pts ≈ ±{disp['two_sigma_elo']:.1f} elo")
        else:
            print(f"  this cell's own elo/pt ratio is NOT reportable at D~0 (own-ratio guard, "
                  f"READ_RULE.md §1) — converted through the PINNED bracket {ELO_PER_POINT_BRACKET} instead")
            if disp["two_sigma_elo_lo"] is not None:
                print(f"  2-sigma bound = {disp['two_sigma_pts']:.4f} pts ≈ "
                      f"±{disp['two_sigma_elo_lo']:.1f}..±{disp['two_sigma_elo_hi']:.1f} elo")
        if branch == "H-NULL-BOUND" and disp.get("two_sigma_pts") is not None:
            print()
            if disp["two_sigma_elo_lo"] is not None:
                print(f"headroom above 11008 is capped at ±{disp['two_sigma_pts']:.4f} POINTS "
                      f"(the interval of record) ≈ ±{disp['two_sigma_elo_lo']:.1f}..±"
                      f"{disp['two_sigma_elo_hi']:.1f} elo via the pinned in-family bracket, "
                      f"superseding the decay bound's [−35, +49] elo.")
    print()
    print("GATES:")
    for g in result["gates"]:
        mark = "PASS" if g["passed"] else "FAIL"
        print(f"  [{mark}] {g['id']:<12} @ {g['resolved_address']}")
        print(f"          {g['observed']}")
    print()


# --------------------------------------------------------------------------- #
# --selftest — synthetic fixtures, no real archive, exercising the SAME       #
# gate/witness/branch machinery above.                                        #
# --------------------------------------------------------------------------- #

_FIXTURE_CONF_TEMPLATE = """\
BLIND_COMMIT={blind_commit}
PINNED_SRC_REV_FILE=PINNED_SRC_REV
SRC_CLEAN_LOG=SRC_CLEAN.jsonl
W_LAPTOP=26
NICE=19
RUST_THREADS=1
PREFLIGHT_RAM_FLOOR_MB=2500
RUNTIME_RAM_FLOOR_MB=800
N_GAMES={n_games}
N_DECKS={n_decks}
N_COMMON_FLOOR={n_common_floor}
BAND=148000000000
DECK_SEED_START=148000000000
DECK_SEED_END={deck_seed_end}
BAND_SENTINEL=BAND_CLAIMED
F_K_DETS=16
F_SIMS_PER_DET=1376
F_TOTAL_SIMS=22016
E_K_DETS=8
E_SIMS_PER_DET=1376
E_TOTAL_SIMS=11008
OPPONENT_MODE=fair-champion
BACKEND=rust
INFO_MODE=fair
RULES_PROFILE=fixed_v1
FIX_R9=1
EXACT_K=2
C_PUCT=1.5
TAU_P=5
LEAF_QUANTIZE=float
FINAL_SELECT=visits
PROD_LEAF_HASH=a36d2e15a3b3d71d
TIEARB=off
CHUNK_GAMES=100
PASS_TIMEOUT_SECS=3400
MAX_PASSES=20
CLAIM_STALE_SECS=1800
VOID_RATE_ABORT_PCT=10
REPO_LOCAL={repo}
RUN_ID=h2h_22016_20260824_SELFTEST
OUT_SUBDIR=measurement/h2h_22016_20260824
OUT_CELL=h2h_k16x1376_vs_champ_k8x1376
ADJUDICATOR=measurement/h2h_22016_prep/adjudicate.py
SMOKE_GAMES=2
SMOKE_SEED_START=990000000000
SMOKE_WORKERS=2
"""


def _sf_build_throwaway_repo(root: Path):
    """A throwaway git repo, built inside the temp dir, exercising the SAME
    `git merge-base --is-ancestor` + `git show` code path G-BLIND uses on a
    real repo — no stubbing of the git calls themselves."""
    repo = root / "repo"
    repo.mkdir(parents=True)

    def g(*args):
        subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)

    g("init", "-q")
    g("config", "user.email", "selftest@example.com")
    g("config", "user.name", "selftest")
    rr = repo / "measurement" / "h2h_22016_prep"
    rr.mkdir(parents=True)
    (rr / "READ_RULE.md").write_text("placeholder, pre-freeze\n")
    g("add", "-A")
    g("commit", "-q", "-m", "init")
    (rr / "READ_RULE.md").write_text("> ⛔→✅ **FROZEN 2026-08-24** ...\n\n# READ_RULE\n")
    g("add", "-A")
    g("commit", "-q", "-m", "freeze banner")
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    (repo / "followup.txt").write_text("stamp\n")
    g("add", "-A")
    g("commit", "-q", "-m", "stamp follow-up (so the blind sha is a strict ancestor of HEAD)")
    return repo, sha


def _sf_classify(diff: int):
    return diff > 0, diff == 0


def _sf_record(seed, a_seat, diff, k_dets=16, sims=1376, opponent="fair-champion"):
    won, drew = _sf_classify(diff)
    s0 = 100 + (diff if a_seat == 0 else 0)
    s1 = 100 + (diff if a_seat == 1 else 0)
    return {
        "seed": seed, "a_seat": a_seat, "info": "fair", "exact_k": 2,
        "k_dets": k_dets, "sims": sims, "rung_sims": 800,
        "score_p0": s0, "score_p1": s1, "diff": diff,
        "won_by_champ": won, "drew": drew,
        "elapsed_s": 12.3, "moves": 140, "deck_hash": f"d{seed:012d}",
        "champ_prefix_moves": 70, "champ_exact_moves": 4,
        "champ_prefix_secs": 5.5, "champ_solver_secs": 0.4, "champ_timeouts": 0,
        "rung_moves": 0, "rung_secs": 0.0, "latch_k": None,
        "opponent": opponent,
        "opp_prefix_moves": 70, "opp_exact_moves": 3,
        "opp_prefix_secs": 4.1, "opp_solver_secs": 0.3, "opp_timeouts": 0,
        "opp_latch_k": None, "cand_jf": None, "cand_tiearb": None,
        "wc_tiebreak": False, "wc_tie_resolved": False,
    }


def _sf_gen_records(cell_dir: Path, n_decks: int, seed_start: int, mean_margin: float,
                     sd_deck: float = 3.0, sd_game: float = 0.5, corrupt_seed_index=None,
                     skew_win=None, rng: random.Random | None = None) -> list[dict]:
    """`sd_deck` disperses the per-DECK true margin across decks; `sd_game`
    adds independent per-GAME (per-seat) noise on top. A branch fixture that
    needs a large |z| while staying inside the G-SAT win-rate rail wants a
    SMALL `sd_deck` (so the paired-per-deck margin resolves tightly) and a
    LARGE `sd_game` (so individual games still flip sign often, keeping the
    realized win-rate near 0.5 even though the mean margin is large) — a
    budget edge realistically moves the margin far more than the win-rate."""
    rng = rng or random.Random(12345)
    cell_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(n_decks):
        seed = seed_start + i
        if corrupt_seed_index is not None and i == corrupt_seed_index:
            seed = seed_start + 10_000_000  # deliberately outside the declared band
        base = rng.gauss(mean_margin, sd_deck)
        for a_seat in (0, 1):
            if skew_win is not None:
                diff = int(round(rng.uniform(1, 6))) if rng.random() < skew_win else -int(round(rng.uniform(1, 6)))
            else:
                diff = int(round(base + rng.gauss(0.0, sd_game)))
            rec = _sf_record(seed, a_seat, diff)
            (cell_dir / f"seed{seed:012d}_a{a_seat}.json").write_text(json.dumps(rec))
            out.append(rec)
    return out


def _sf_good_manifest_summary(records: list[dict], conf: dict, code_rev: str) -> tuple[dict, dict]:
    """Build a fully §3-compliant summary.json + manifest.json pair for the
    given records (analyzer stats computed FROM these records, so RECON
    passes by construction)."""
    deltas = paired_deltas(records)
    D, SE_D, z_D, n_pairs = mean_se_z(list(deltas.values()))
    n_scored = len(records)
    W = sum(1 for r in records if r["won_by_champ"])
    Dr = sum(1 for r in records if r["drew"])
    L = n_scored - W - Dr
    winrate = (W + 0.5 * Dr) / n_scored
    elo, elo_sig = elo_from_wr(winrate, n_scored)
    winrate_z = (winrate - 0.5) / math.sqrt(0.25 / n_scored)

    leaf = conf["PROD_LEAF_HASH"]
    champ_cfg = {"c_puct": conf_float(conf, "C_PUCT"), "tau_p": conf_int(conf, "TAU_P"),
                 "leaf_quantize": conf["LEAF_QUANTIZE"], "final_select": conf["FINAL_SELECT"],
                 "value_norm": 15.0}

    summary = {
        "info": "fair", "exact_k": conf_int(conf, "EXACT_K"),
        "k_dets": conf_int(conf, "F_K_DETS"), "sims": conf_int(conf, "F_SIMS_PER_DET"),
        "total_sims": conf_int(conf, "F_TOTAL_SIMS"), "rung_sims": 800,
        "n_failed": 0, "failure_rate": 0.0, "failure_rate_trigger": 0.005,
        "validity_trigger_fired": False, "failed_cells": [], "failed_by_seat": {"0": 0, "1": 0},
        "failed_classes": {}, "n_resolved_failures": 0, "resolved_failed_cells": [],
        "opponent": "fair-champion", "opponent_label": "FairHeuristicPriorAgent",
        "n": n_scored, "W": W, "D": Dr, "L": L, "winrate": winrate, "winrate_z": winrate_z,
        "elo": elo, "elo_sig_1sigma": elo_sig, "avg_diff": sum(r["diff"] for r in records) / n_scored,
        "paired_mean_margin": D, "paired_z": z_D, "n_paired": n_pairs,
        "champ_prefix_ms_per_move": 79.0, "rung_ms_per_move": 41.0,
        "champ_latched_games": n_scored, "solver_secs_per_game": 0.4, "champ_timeouts": 0,
        "wc_tiebreak": False, "wc_tie_resolved_games": 0,
    }

    manifest = {
        "kind": "eval_fair_puct", "game": "carcassonne", "code_rev": code_rev,
        "host": "selftest", "utc": "2026-08-24T00:00:00Z", "leaf_env": {},
        "rules_profile": {
            "name": conf["RULES_PROFILE"], "grid_rule": "engine6", "start_row": 6, "start_col": 15,
            "board_rows": 35, "board_cols": 35, "start_rule": "engine", "window_size": 25,
            "cloister_scan": "drifting", "unplaceable_tile": "next_player", "note": "fixture",
            "r9_env_expected": True, "wc_tiebreak": False, "fixed_start_tile": False,
            "recentred": False, "r9_env_var": "CARCASSONNE_FIX_R9",
            "r9_env_observed": True, "r9_env_ok": True,
        },
        "evaluator": "scripts/classical_search/eval_fair_puct.py",
        "cand_tiearb": {"enabled": False, "B": 0, "J": 0, "mode": "off", "salt": "", "eps": 0.0},
        "rust_toolchain": "stable", "carc_rs_build": "selftest-build",
        "carc_rs_version": "0.1.0-selftest", "carc_rs_binary_sha": "d" * 40,
        "mixed_builds": False, "utc_end": "2026-08-24T01:00:00Z",
        "n_failed": 0, "failure_rate": 0.0, "n_failed_this_leg": 0,
        "validity_trigger_fired": False, "failed_cells": [], "failed_by_seat": {"0": 0, "1": 0},
        "failed_classes": {}, "n_resolved_failures": 0, "resolved_failed_cells": [],
        "config": {
            "info": "fair",
            "champion": {"agent": "FairHeuristicPriorAgent", **champ_cfg,
                         "k_dets": conf_int(conf, "F_K_DETS"), "sims_per_det": conf_int(conf, "F_SIMS_PER_DET"),
                         "total_sims": conf_int(conf, "F_TOTAL_SIMS"), "batch_size": 1,
                         "leaf": "v2.9 curve125 leaf", "value_source": "v2.9 heuristic leaf",
                         "aggregation": "pooled-Q over k_dets determinizations"},
            "endgame": {"mode": "marginalized", "exact_k": conf_int(conf, "EXACT_K"),
                        "exact_budget": 20000, "shared_by_both_arms": True, "tt_cap": None},
            "opponent_mode": conf["OPPONENT_MODE"], "opp_sims": None, "opp_k_dets": None,
            "opponent": {
                "mode": conf["OPPONENT_MODE"], "label": "FairHeuristicPriorAgent (production champion)",
                "agent": "FairHeuristicPriorAgent",
                "priors_source": "heuristic_softmax_dleaf_tau", "value_source": "frozen_v29_curve125_leaf",
                "c": None, "sims": None,
                "k_dets": conf_int(conf, "E_K_DETS"), "sims_per_det": conf_int(conf, "E_SIMS_PER_DET"),
                "total_sims": conf_int(conf, "E_TOTAL_SIMS"),
                "endgame": {"mode": "marginalized", "exact_k": conf_int(conf, "EXACT_K"), "exact_budget": 20000},
                "leaf": "FROZEN v2.9 curve125 production champion leaf", "leaf_hash": leaf,
                "leaf_cfg": {}, "champ_cfg": champ_cfg,
                "production_config_deviations": None,
                "provenance": "governance/PRODUCTION.yaml champion config",
            },
            "result_semantics": {"diff": "candidate - opponent"},
            "rung": None,
            "n": n_scored, "paired": True, "seed_start": conf_int(conf, "DECK_SEED_START"),
            "band_seed_start": conf_int(conf, "DECK_SEED_START"),
            "n_decks": conf_int(conf, "N_DECKS"), "seatings_per_deck": 2,
            "cand_curve_drift_allowed": False, "cand_curve_drift": None,
            "leaf_hash": leaf, "code_rev": code_rev,
            "cand_leaf_json": None, "cand_leaf_cfg": {}, "cand_leaf_hash": leaf,
            "cand_jrules_prior": None, "cand_jrules_filter": None,
            "cand_tiearb": {"enabled": False, "B": 0, "J": 0, "mode": "off", "salt": "", "eps": 0.0},
            "backend": {
                "name": conf["BACKEND"], "default": "python", "requested": conf["BACKEND"],
                "rust_threads": 1, "workers": 26, "threads_policy": "FARM",
                "converted_sides": ["candidate", "opponent"],
                "unconverted_note": "n/a (fixture)", "note": "fixture",
            },
        },
    }
    return summary, manifest


def _sf_write_conf(prep_dir: Path, repo: Path, blind_commit: str, n_decks: int) -> dict:
    text = _FIXTURE_CONF_TEMPLATE.format(
        blind_commit=blind_commit, repo=repo, n_games=n_decks * 2, n_decks=n_decks,
        n_common_floor=max(1, int(round(n_decks * 0.8))),
        deck_seed_end=148000000000 + n_decks - 1,
    )
    (prep_dir / "WORKERS.conf").write_text(text)
    return load_workers_conf(prep_dir / "WORKERS.conf")


def _sf_write_valid_siblings(prep_dir: Path, code_rev: str) -> None:
    (prep_dir / "PINNED_SRC_REV").write_text(code_rev)
    lines = [
        json.dumps({"boundary": "pre-flight", "head": code_rev, "src_clean": True}),
        json.dumps({"boundary": "after-pass-1", "head": code_rev, "src_clean": True}),
    ]
    (prep_dir / "SRC_CLEAN.jsonl").write_text("\n".join(lines) + "\n")


def _sf_write_blind_proof(prep_dir: Path, blind_commit: str, is_ancestor: bool) -> None:
    proof = {"blind_commit": blind_commit, "head_at_launch": "HEAD",
              "is_ancestor_of_head": is_ancestor, "utc": "2026-08-24T00:00:00Z"}
    (prep_dir / "BLIND_PROOF.json").write_text(json.dumps(proof))


def _sf_touch_done(prep_dir: Path, out_cell: str) -> None:
    (prep_dir / f"DONE_cell_{out_cell}").write_text("done\n")


@dataclass
class _Case:
    name: str
    run_dir: Path
    prep_dir: Path
    conf: dict
    repo: Path
    expected_branch: str
    expected_failed_gate_ids: frozenset  # exact set expected in result["void"]["gate_ids_failed"]
    expected_display_limb: str | None = None  # READ_RULE.md §1 elo-guard: "own-ratio" / "pinned-bracket"


def _build_case(root: Path, idx: int, name: str, *, n_decks: int, mean_margin: float,
                 expected_branch: str, expected_failed: frozenset,
                 mutate_manifest=None, mutate_summary=None,
                 blind_commit_override=None, corrupt_seed_index=None, skew_win=None,
                 n_failed_override=None, omit_done=False, add_failed_sentinel=False,
                 sd_deck: float = 3.0, sd_game: float = 0.5,
                 expected_display_limb: str | None = None) -> _Case:
    case_root = root / f"case_{idx:02d}_{name}"
    repo, real_blind_sha = _sf_build_throwaway_repo(case_root)
    prep_dir = case_root / "prep"
    prep_dir.mkdir(parents=True)
    blind_commit = real_blind_sha if blind_commit_override is None else blind_commit_override
    conf = _sf_write_conf(prep_dir, repo, blind_commit, n_decks)
    # The sibling BLIND_COMMIT file is what gate_blind actually reads (READ_RULE.md
    # §3 G-BLIND); WORKERS.conf's own BLIND_COMMIT= key (written above) is a
    # separate, informational copy the launcher sources, mirroring the real deploy
    # where both exist side by side.
    (prep_dir / "BLIND_COMMIT").write_text(blind_commit)
    code_rev = "c" * 40
    _sf_write_valid_siblings(prep_dir, code_rev)
    _sf_write_blind_proof(prep_dir, blind_commit, is_ancestor=(blind_commit == real_blind_sha))
    if not omit_done:
        _sf_touch_done(prep_dir, conf["OUT_CELL"])
    if add_failed_sentinel:
        (prep_dir / "FAILED_cell_h2h_k16x1376_vs_champ_k8x1376").write_text("abort\n")

    run_dir = case_root / "run"
    rng = random.Random(999 + idx)
    records = _sf_gen_records(run_dir, n_decks, conf_int(conf, "DECK_SEED_START"), mean_margin,
                               sd_deck=sd_deck, sd_game=sd_game,
                               corrupt_seed_index=corrupt_seed_index, skew_win=skew_win, rng=rng)
    summary, manifest = _sf_good_manifest_summary(records, conf, code_rev)
    if n_failed_override is not None:
        summary["n_failed"] = n_failed_override
    if mutate_manifest:
        mutate_manifest(manifest)
    if mutate_summary:
        mutate_summary(summary)
    (run_dir / "summary.json").write_text(json.dumps(summary))
    (run_dir / "manifest.json").write_text(json.dumps(manifest))

    return _Case(name, run_dir, prep_dir, conf, repo, expected_branch, expected_failed,
                 expected_display_limb)


def _build_all_cases(root: Path) -> list[_Case]:
    cases = []
    i = 0

    def nxt():
        nonlocal i
        i += 1
        return i

    N = 24  # fixture-scale deck count (fully exercises every gate; real cell uses 700)

    # ---- 3 branch fixtures, ALL §3 gates PASS -------------------------------
    # H-POSITIVE/H-REVERSED need |z_D| >= 2 while the REALIZED win-rate stays
    # inside the G-SAT rail [0.35,0.65] — a tight per-deck dispersion
    # (sd_deck) with large per-game noise (sd_game) does that: the mean
    # margin resolves cleanly across many decks even though single games
    # still flip sign often (a budget edge moves margin far more than
    # win-rate). Tuned+verified at these exact parameters/seeds.
    # READ_RULE.md §1's guarded elo conversion (module docstring / compute_display):
    # H-NULL-BOUND must land on limb "pinned-bracket" (this cell's own elo_D/D
    # is a near-zero/near-zero quotient and is not reportable); H-POSITIVE /
    # H-REVERSED must land on "own-ratio". Asserted explicitly below, not just
    # the branch, so a regression in the guard's branch-dependent limb choice
    # is caught even if the branch itself still comes out right.
    cases.append(_build_case(root, nxt(), "H-NULL-BOUND", n_decks=N, mean_margin=0.05,
                              expected_branch="H-NULL-BOUND", expected_failed=frozenset(),
                              expected_display_limb="pinned-bracket"))
    cases.append(_build_case(root, nxt(), "H-POSITIVE", n_decks=180, mean_margin=5.0,
                              sd_deck=1.0, sd_game=24.0,
                              expected_branch="H-POSITIVE", expected_failed=frozenset(),
                              expected_display_limb="own-ratio"))
    cases.append(_build_case(root, nxt(), "H-REVERSED", n_decks=180, mean_margin=-5.0,
                              sd_deck=1.0, sd_game=24.0,
                              expected_branch="H-REVERSED", expected_failed=frozenset(),
                              expected_display_limb="own-ratio"))

    # ---- 14 single-gate-break fixtures --------------------------------------
    cases.append(_build_case(
        root, nxt(), "G-BAND", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-BAND"}),
        mutate_manifest=lambda m: set_path(m, "config.n_decks", 999)))

    cases.append(_build_case(
        root, nxt(), "G-DECKS", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-DECKS"}), corrupt_seed_index=5))

    # Mutates c_puct (a must-EQUAL pair G-SINGLEVAR checks but G-BUDGET does not
    # touch at all) so this fixture trips G-SINGLEVAR alone. Mutating
    # sims_per_det/k_dets/total_sims instead would ALSO trip G-BUDGET (which
    # pins those same numbers) — that coupling is real but not what this
    # fixture is for; G-BUDGET gets its own dedicated fixture below.
    cases.append(_build_case(
        root, nxt(), "G-SINGLEVAR", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-SINGLEVAR"}),
        mutate_manifest=lambda m: set_path(m, "config.champion.c_puct", 999.0)))

    cases.append(_build_case(
        root, nxt(), "G-REV", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-REV"}),
        mutate_manifest=lambda m: set_path(m, "code_rev", "0" * 40)))

    cases.append(_build_case(
        root, nxt(), "G-BLIND", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-BLIND"}), blind_commit_override="PENDING"))

    # Moves BOTH cand_leaf_hash and the opponent's leaf_hash to the SAME wrong
    # value, so the two sides still agree with each other (G-SINGLEVAR's
    # must-EQUAL leaf-hash check stays satisfied) while neither matches the
    # pinned PROD_LEAF_HASH (G-LEAF fails on its own). eval_fair_puct.py
    # writes the opponent's leaf hash as a clean `opponent.leaf_hash` field
    # for --opponent fair-champion (it is in _HEAD_TO_HEAD, so the harness
    # takes the `else _leaf_hash(opp_leaf_cfg)` branch, not the h800/greedy
    # ones) — no prefix-parsing out of the `leaf` prose string is needed.
    cases.append(_build_case(
        root, nxt(), "G-LEAF", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-LEAF"}),
        mutate_manifest=lambda m: (set_path(m, "config.cand_leaf_hash", "0" * 16),
                                    set_path(m, "config.opponent.leaf_hash", "0" * 16))))

    cases.append(_build_case(
        root, nxt(), "G-RULES", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-RULES"}),
        mutate_manifest=lambda m: set_path(m, "rules_profile.name", "walled")))

    cases.append(_build_case(
        root, nxt(), "G-BACKEND", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-BACKEND"}),
        mutate_manifest=lambda m: set_path(m, "config.backend.converted_sides", ["candidate"])))

    cases.append(_build_case(
        root, nxt(), "G-BUDGET", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-BUDGET"}),
        mutate_manifest=lambda m: set_path(m, "config.champion.total_sims", 12345)))

    # G-TIEARB has two independent ways to fail: the candidate side literally
    # armed, and a stray *tiearb* subtree anywhere else in the manifest (the
    # opponent has no arming flag at all in eval_fair_puct.py, so an
    # `opp_tiearb` key can only appear via a harness/launcher defect — the
    # whole-manifest scan is what catches that class). Both get their own
    # fixture; both must resolve to G-TIEARB failing and nothing else.
    cases.append(_build_case(
        root, nxt(), "G-TIEARB-cand-armed", n_decks=N, mean_margin=0.05,
        expected_branch="U-UNREADABLE", expected_failed=frozenset({"G-TIEARB"}),
        mutate_manifest=lambda m: (
            set_path(m, "config.cand_tiearb",
                      {"enabled": True, "B": 64, "J": 4, "mode": "argmax",
                       "salt": "tiearb2-deploy-v1", "eps": 0.0}),
            set_path(m, "cand_tiearb",
                      {"enabled": True, "B": 64, "J": 4, "mode": "argmax",
                       "salt": "tiearb2-deploy-v1", "eps": 0.0}))))

    cases.append(_build_case(
        root, nxt(), "G-TIEARB-opp-armed", n_decks=N, mean_margin=0.05,
        expected_branch="U-UNREADABLE", expected_failed=frozenset({"G-TIEARB"}),
        mutate_manifest=lambda m: set_path(
            m, "config.opp_tiearb", {"enabled": True, "B": 64, "J": 4, "mode": "argmax"})))

    # Both sides' exact_k moved to the SAME wrong value: the candidate/opponent
    # endgame handoffs still AGREE with each other (G-SINGLEVAR's must-equal
    # check stays satisfied), so only G-EXACT fires — this is the realistic
    # failure mode (a shared misconfiguration), not a candidate/opponent
    # divergence (which is G-SINGLEVAR's own, separately-tested, business).
    cases.append(_build_case(
        root, nxt(), "G-EXACT", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-EXACT"}),
        mutate_manifest=lambda m: (set_path(m, "config.endgame.exact_k", 4),
                                    set_path(m, "config.opponent.endgame.exact_k", 4))))

    cases.append(_build_case(
        root, nxt(), "G-N", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-N"}), n_failed_override=5))

    cases.append(_build_case(
        root, nxt(), "G-SAT", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"G-SAT"}), skew_win=0.92))

    # ---- RECON: analyzer/witness disagreement, must fail RECON ONLY --------
    cases.append(_build_case(
        root, nxt(), "RECON", n_decks=N, mean_margin=0.05, expected_branch="U-UNREADABLE",
        expected_failed=frozenset({"RECON"}),
        mutate_summary=lambda s: s.__setitem__("paired_mean_margin", s["paired_mean_margin"] + 999.0)))

    # ---- bonus: VOID triggers NOT tied to any single §3 gate ----------------
    cases.append(_build_case(
        root, nxt(), "VOID-no-done-sentinel", n_decks=N, mean_margin=0.05,
        expected_branch="U-UNREADABLE", expected_failed=frozenset(), omit_done=True))
    cases.append(_build_case(
        root, nxt(), "VOID-failed-sentinel-present", n_decks=N, mean_margin=0.05,
        expected_branch="U-UNREADABLE", expected_failed=frozenset(), add_failed_sentinel=True))

    return cases


def run_selftest() -> bool:
    all_ok = True
    rows = []
    with tempfile.TemporaryDirectory(prefix="h2h22k_adjudicate_selftest_") as td:
        root = Path(td)
        for case in _build_all_cases(root):
            try:
                result = adjudicate(case.run_dir, case.prep_dir, case.conf, case.repo)
                actual_branch = result["branch"]
                actual_failed = frozenset(result["void"]["gate_ids_failed"])
                actual_limb = result["display"]["limb"]
                ok = (actual_branch == case.expected_branch) and (actual_failed == case.expected_failed_gate_ids)
                if case.expected_display_limb is not None:
                    ok = ok and (actual_limb == case.expected_display_limb)
            except Exception as e:
                actual_branch, actual_failed, actual_limb, ok = f"<EXCEPTION: {e}>", frozenset(), "?", False
            all_ok &= ok
            rows.append((case.name, case.expected_branch, sorted(case.expected_failed_gate_ids),
                         case.expected_display_limb, actual_branch, sorted(actual_failed), actual_limb, ok))

    print()
    print("=" * 100)
    print("SELFTEST FIXTURE TABLE")
    print("=" * 100)
    w1 = max(len(r[0]) for r in rows) + 2
    for name, exp_b, exp_f, exp_limb, act_b, act_f, act_limb, ok in rows:
        mark = "PASS" if ok else "FAIL"
        limb_part = f" limb=(exp={exp_limb!s},act={act_limb!s})" if exp_limb is not None else ""
        print(f"[{mark}] {name:<{w1}} expected=({exp_b}, {exp_f}) actual=({act_b}, {act_f}){limb_part}")
    print("=" * 100)
    n_pass = sum(1 for r in rows if r[-1])
    print(f"{n_pass}/{len(rows)} fixtures PASS")
    print("=" * 100)
    return all_ok


# --------------------------------------------------------------------------- #
# CLI.                                                                         #
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", default=DEFAULT_RUN_DIR)
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    # AMENDMENT M3 (see AMENDMENTS.md): NO gate-logic change. WORKERS.conf's
    # REPO_LOCAL names the path the cell RAN at, where HEAD is the frozen
    # instrument's tip. Adjudicating on any other box, that same path is a
    # different checkout on a different branch, so G-BLIND's ancestor test
    # reads False for a purely environmental reason. This flag lets the
    # ancestor test be pointed at the frozen instrument's own worktree.
    # G-BLIND PASSES UNAMENDED on the laptop; this exists only so the read
    # is reproducible off-box.
    ap.add_argument("--repo", default=None,
                    help="override WORKERS.conf REPO_LOCAL for the G-BLIND git checks")
    args = ap.parse_args(argv)

    here = Path(__file__).resolve().parent

    if args.selftest:
        ok = run_selftest()
        return 0 if ok else 1

    conf = load_workers_conf(here / "WORKERS.conf")
    repo = Path(args.repo or conf.get("REPO_LOCAL", "/home/doctor/projects/carcassone"))
    run_dir = Path(args.run_dir)
    out_path = Path(args.out) if args.out else (here / DEFAULT_OUT_NAME)

    result = adjudicate(run_dir, here, conf, repo)
    out_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    print(f"[ADJUDICATION.json] wrote {out_path}")
    print_readout(result)
    # Exit 0 on any adjudicated branch (U-UNREADABLE included — it adjudicated
    # fine). Nonzero is reserved for an internal error, which would already
    # have raised before this point.
    return 0


if __name__ == "__main__":
    sys.exit(main())
