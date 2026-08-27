#!/usr/bin/env python3
"""ADJUDICATOR — invasion-risk term family, round-2 bracket at 2752.

    analyze_screen.py --selftest
    analyze_screen.py --smoke-mode --cell <dir>
    analyze_screen.py --run-dir <root>

**This file DECIDES NOTHING ON ITS OWN.** Every bar, constant, branch table and
cost figure lives in `screen_lib.py`, which the launcher's precondition ladder
imports too — so the launcher's in-flight per-cell pre-check and this file's
gates cannot drift apart. What lives HERE is only: how to find a value in an
emitted manifest, and how to render the readout `READ_RULE.md` §4.3 mandates.

The pair is law. `DESIGN.md` + `READ_RULE.md` are the spec; if this file
disagrees with them it is THIS FILE that is wrong.

═══════════════════════════════════════════════════════════════════════════════
INHERITED FROM ROUND 1 — and the four things that had to change
═══════════════════════════════════════════════════════════════════════════════
This is `measurement/invasion_screen_prep/analyze_screen.py` adapted. Round 1's
adjudicator survived three smoke rounds, two pre-game-1 amendments and a clean
2800-game adjudication; its address resolution, its ABSENT-is-FAIL discipline,
its RECON witness, its `G-TIEARB` container/terminal split and its guarded elo
conversion are carried VERBATIM. What round 2 required:

1. **`G-LEAF` IS PER-CELL AND TWO-SIDED.** Round 1 could write conjunct (a) as
   the CONSTANT `opp_leaf_hash == a36d2e15a3b3d71d`. Three of round 2's seven
   cells play a SHAPE-B AGENT, so every hash pin now comes off the cell's own
   spec, through `screen_lib.leaf_gate()` — one implementation, shared with the
   launcher's per-cell pre-check.

2. **`G-INVASION` AND `G-CAPFWD` READ BOTH SIDES.** Round 1's opponent-side rule
   was "no invasion key at all". On a C cell the opponent is SUPPOSED to carry
   `invasion_alpha 0.09 @ cap 11.0`, and the cap biconditional has to hold over
   there too — the opponent's leaf goes through the same
   `rust_agent.leaf_config_rs` conditional kwargs the candidate's does.

3. **`G-IDENT` IS GONE; `G-WHEEL-SAME` HAS ITS SLOT.** Round 2 runs no IDENT
   cell — it INHERITS round 1's PASS — and the inheritance is mechanised as a
   ROUND-LEVEL gate on the wheel fingerprint. A fail voids all seven cells,
   exactly as a failed `G-IDENT` voided all four.

4. **THE READ IS A BRACKET READ.** `§4.5`'s pre-registered within-round
   low-vs-high contrast, `§4.6`'s defence reading for C, `§4.7`'s
   endpoint/noise-signature rules, and round 1's mids as a DESCRIPTIVE OVERLAY
   that is never pooled and never z-combined.

**Two documents per cell, resolved together.** `config.*` lives in
`manifest.json`; the STATISTICS live in `summary.json`, which carries no
`config` block at all (round 1's deviation IS-D1 was a reader that got this
wrong — the fixed address is carried here). Every gate resolves across BOTH and
prints WHICH document and WHICH address answered. A value found at NO address is
`ABSENT`, and **`ABSENT` is `FAIL`** — never a skip, never a default.

**Records are read NON-RECURSIVELY.** `eval_fair_puct.py` writes successes as
`<cell>/seed%012d_a%d.json` but FAILURES into `<cell>/failed/` with the SAME
filename pattern. A recursive glob would count failures as completions.

**`RECON` is a WITNESS, never a branch input.**

**`--selftest` refuses a synthesized fixture** and runs against
`selftest_fixture/` — round 1's own §9 smoke archive, 16 real games the harness
emitted, described by `screen_lib.FIXTURE_SPEC`.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import screen_lib as L  # noqa: E402

MISSING = object()

#: The path whose EXISTENCE at a given rev proves that rev carries the invasion
#: family. `G-WHEEL`'s ancestry conjunct is the only post-hoc check that can
#: catch a stale wheel from the archive alone (DESIGN §7).
INVASION_SOURCE = "rust/carc/carc-core/src/leaf/invasion.rs"

#: `rust_agent.carc_rs_build_id()` emits `carc_rs-<version>+<rev12>+rustc<tc>`.
_BUILD_REV_RE = re.compile(r"^carc_rs-[^+]+\+([0-9a-f]{7,40})\+", re.I)

#: The order in which a gate's addresses are tried.
DOCS = ("manifest", "summary")


# ═══════════════════════════════════════════════════════════════════════════ #
# ADDRESS RESOLUTION                                                          #
# ═══════════════════════════════════════════════════════════════════════════ #
def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """`{"a.b.c": value}` over nested mappings. Lists are LEAVES."""
    out: dict[str, Any] = {}
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            kk = f"{prefix}{k}"
            if isinstance(v, Mapping):
                out.update(flatten(v, kk + "."))
            else:
                out[kk] = v
    return out


def container_segments(obj: Any, prefix: str = "") -> list[str]:
    """Every NON-TERMINAL path segment, as a dotted path.

    ⚠️ `G-TIEARB(b)` scans THESE, not leaf names — round 1's freeze-time
    correction. A healthy archive emits `config.champion.tiearb_enabled` (a
    TERMINAL key containing 'tiearb'); scanning terminals would void every
    healthy cell. An ARMED opponent block emits the CONTAINER `opp_tiearb`,
    which this does catch.
    """
    out: list[str] = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            kk = f"{prefix}{k}"
            if isinstance(v, Mapping):
                out.append(kk)
                out.extend(container_segments(v, kk + "."))
    return out


def dig(doc: Any, address: str) -> Any:
    cur = doc
    for part in address.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


# ═══════════════════════════════════════════════════════════════════════════ #
# THE THREE CONJUNCTS THAT NEED SOMETHING OUTSIDE THE ARCHIVE                 #
#                                                                             #
# ⛔ EVERY ONE DEFAULTS TO `None`, AND `None` IS FAIL. A gate that cannot be    #
# computed is ABSENT, and ABSENT is FAIL — never a skip.                       #
# ═══════════════════════════════════════════════════════════════════════════ #
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def wheel_ancestry_facts(repo: Path, build: str | None,
                         branch_tip: str = "HEAD") -> dict:
    """⭐ THE CONJUNCT THAT CATCHES A STALE WHEEL POST-HOC, FROM THE ARCHIVE
    ALONE. `WHEEL_PROBE.json` records that a nonzero forward SUCCEEDED at launch;
    this is the archive half — the rev embedded in the manifest's own
    `carc_rs_build` must (a) be a rev at which `invasion.rs` EXISTS and (b) be an
    ancestor of the branch tip.

    ⚠️ `carc_rs_version` is permanently "0.1.0" and can never discriminate.
    """
    if not build or not isinstance(build, str):
        return {"ok": False, "why": "carc_rs_build ABSENT — ABSENT is FAIL",
                "rev": None}
    m = _BUILD_REV_RE.match(build.strip())
    if not m:
        return {"ok": False, "rev": None,
                "why": f"carc_rs_build {build!r} carries no embedded git rev"}
    rev = m.group(1)
    has_src = _git(repo, "cat-file", "-e", f"{rev}:{INVASION_SOURCE}").returncode == 0
    is_anc = _git(repo, "merge-base", "--is-ancestor", rev, branch_tip).returncode == 0
    ok = has_src and is_anc
    why = "wheel rev carries the invasion family and is in this lineage" if ok else (
        f"rev {rev}: invasion.rs present={has_src}, ancestor-of-{branch_tip}={is_anc} — "
        "a wheel built before the family serves every champion config unchanged and "
        "SILENTLY, so a stale-wheel cell reads as 'the term is worth nothing' rather "
        "than 'the term never ran'")
    return {"ok": ok, "rev": rev, "invasion_source_present": has_src,
            "is_ancestor": is_anc, "why": why}


def blind_facts(repo: Path, blind: str | None, proof: Mapping | None,
                design: Path, read_rule: Path) -> dict:
    """READ_RULE §3 `G-BLIND`, in full: a 40-hex sha, an ANCESTOR of HEAD, the
    commit that INTRODUCED this pair's FROZEN banner, and a `BLIND_PROOF.json`
    that agrees with a LIVE re-check.
    """
    if not blind or not L.is_hex40(blind):
        return {"ok": False, "why": "BLIND_COMMIT is absent or not a 40-hex sha "
                                    "(still the PENDING placeholder?)"}
    live_anc = _git(repo, "merge-base", "--is-ancestor", blind, "HEAD").returncode == 0
    try:
        d_rel, r_rel = str(design.relative_to(repo)), str(read_rule.relative_to(repo))
    except ValueError:
        d_rel, r_rel = str(design), str(read_rule)
    show = _git(repo, "show", "--format=", "--unified=0", blind, "--", d_rel, r_rel)
    banner = any(ln.startswith("+") and "STATUS: FROZEN" in ln
                 for ln in show.stdout.splitlines())
    proof_ok, proof_why = True, "BLIND_PROOF.json agrees with the live re-check"
    if proof is None:
        proof_ok, proof_why = False, "BLIND_PROOF.json ABSENT — ABSENT is FAIL"
    else:
        if str(proof.get("blind_commit", "")).strip() != blind:
            proof_ok, proof_why = False, "BLIND_PROOF.json names a DIFFERENT blind commit"
        elif bool(proof.get("is_ancestor_of_head")) is not live_anc:
            proof_ok, proof_why = False, ("BLIND_PROOF.json's is_ancestor_of_head "
                                          "DISAGREES with a live git re-check")
    ok = live_anc and banner and proof_ok
    return {"ok": ok, "blind_commit": blind, "is_ancestor_of_head": live_anc,
            "introduced_frozen_banner": banner, "proof_ok": proof_ok,
            "why": proof_why if not proof_ok else (
                "" if ok else
                f"ancestor-of-HEAD={live_anc}, introduced-FROZEN-banner={banner}")}


def src_clean_facts(path: Path, cell_names, *, smoke: bool = False) -> dict:
    """READ_RULE §3 `G-REV`'s second half: `SRC_CLEAN.jsonl` must record the code
    paths CLEAN at EVERY boundary, with a `pre-flight` boundary and an `after-…`
    boundary for each cell's final pass.

    ⚠️ A mid-round tree move is the `track_d2_prep` mixed-rev defect, and round 2
    is SEVEN cells long — the window for one is seven times wider than round 1's
    four and nearly twice round 1's own.
    """
    if not path.is_file():
        return {"ok": False, "why": f"{path.name} ABSENT — ABSENT is FAIL",
                "boundaries": []}
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            return {"ok": False, "why": f"{path.name} has an unparseable line",
                    "boundaries": []}
    if not rows:
        return {"ok": False, "why": f"{path.name} is empty", "boundaries": []}
    names = [str(r.get("boundary", "")) for r in rows]
    dirty = [n for n, r in zip(names, rows) if r.get("src_clean") is not True]
    has_preflight = any(n == "pre-flight" or n.endswith("pre-flight") for n in names)
    if smoke:
        missing_after = [] if any("after" in n for n in names) else ["<smoke-after>"]
    else:
        missing_after = [c for c in cell_names
                         if not any(n.startswith(f"{c}-after") for n in names)]
    ok = (not dirty) and has_preflight and not missing_after
    return {"ok": ok, "boundaries": names, "dirty_boundaries": dirty,
            "has_preflight": has_preflight, "missing_after": missing_after,
            "why": "" if ok else (
                f"dirty at {dirty}; " if dirty else "") + (
                "" if has_preflight else "no pre-flight boundary; ") + (
                f"no after-boundary for {missing_after}" if missing_after else "")}


class Cell:
    """One cell's two documents plus its raw records."""

    def __init__(self, spec, path: Path):
        self.spec = spec
        self.name = getattr(spec, "name", "SMOKE")
        self.path = path
        self.manifest = self._load(path / "manifest.json")
        self.summary = self._load(path / "summary.json")
        # ⚠️ NON-RECURSIVE: <cell>/failed/ holds failure records with the SAME
        # filename pattern and must never be counted as completions.
        self.records = []
        for p in sorted(path.glob("seed*_a*.json")):
            try:
                self.records.append(json.loads(p.read_text()))
            except Exception:
                pass
        self.flat = {"manifest": flatten(self.manifest), "summary": flatten(self.summary)}

    @staticmethod
    def _load(p: Path) -> dict:
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}

    def resolve(self, *addresses: str) -> tuple[Any, str]:
        """First address that resolves, in `DOCS` order per address.
        Returns `(value, "<doc>:<address>")`, or `(MISSING, "ABSENT")`."""
        for addr in addresses:
            for doc in DOCS:
                v = dig(getattr(self, doc), addr)
                if v is not MISSING:
                    return v, f"{doc}:{addr}"
        return MISSING, "ABSENT"


# ═══════════════════════════════════════════════════════════════════════════ #
# GATE PLUMBING                                                               #
# ═══════════════════════════════════════════════════════════════════════════ #
class Gates:
    def __init__(self):
        self.results: dict[str, dict] = {}

    def add(self, gid: str, ok: bool, address: str, observed, note: str = ""):
        self.results[gid] = {"id": gid, "ok": bool(ok), "address": address,
                             "observed": observed, "note": note}
        return self.results[gid]

    def failed(self) -> list[str]:
        return [g for g, r in self.results.items() if not r["ok"]]

    def all_ok(self) -> bool:
        return not self.failed()


def _eq(cell: Cell, gates: Gates, gid: str, addresses, want, note: str = "") -> bool:
    """Resolve, compare, record. ABSENT is FAIL."""
    if isinstance(addresses, str):
        addresses = (addresses,)
    got, addr = cell.resolve(*addresses)
    if got is MISSING:
        gates.add(gid, False, addr, None, f"ABSENT is FAIL — tried {list(addresses)}. {note}")
        return False
    ok = (got == want)
    gates.add(gid, ok, addr, got, note if ok else f"want {want!r}, got {got!r}. {note}")
    return ok


def _invasion_subset(d) -> dict:
    if not isinstance(d, Mapping):
        return {}
    return {k: v for k, v in d.items() if k in L.INVASION_DEFAULTS}


def _nondefault_invasion(d) -> dict:
    """The invasion fields a `_leaf_dict`-style block carries AWAY from default.
    `_leaf_dict` DROPS a field at its default, so "absent" IS "default" and both
    readings must pass — this normalises them to one."""
    sub = _invasion_subset(d)
    return {k: v for k, v in sub.items() if v != L.INVASION_DEFAULTS[k]}


def _cap_biconditional(inv: Mapping) -> bool:
    """DESIGN §2.3. `rust_agent.leaf_config_rs` (`rust_agent.py:181-185`) forwards
    `invasion_alpha_cap` and `invasion_stub_max_tiles` ONLY when
    `invasion_alpha != 0.0`, so a side that set an inert shape-B knob without a
    nonzero alpha would have it SILENTLY DROPPED while the manifest still showed
    it — a manifest that lies about the running leaf."""
    alpha = float(inv.get("invasion_alpha", 0.0) or 0.0)
    cap = float(inv.get("invasion_alpha_cap", 0.0) or 0.0)
    stub = int(inv.get("invasion_stub_max_tiles", 2) or 2)
    return ((cap == 0.0) or (alpha != 0.0)) and ((stub == 2) or (alpha != 0.0))


# ═══════════════════════════════════════════════════════════════════════════ #
# THE EIGHTEEN GATES (READ_RULE.md §3)                                        #
# ═══════════════════════════════════════════════════════════════════════════ #
def run_gates(cell: Cell, *, pinned_src_rev: str | None, blind_commit: str | None,
              wheel_probe: Mapping | None, smoke: bool = False,
              wheel_ancestry: Mapping | None = None,
              blind_proof: Mapping | None = None,
              src_clean: Mapping | None = None) -> tuple[Gates, dict]:
    """Every gate, fail-closed, each reporting its resolved address.

    `wheel_ancestry` / `blind_proof` / `src_clean` are the VERDICTS computed by
    `wheel_ancestry_facts` / `blind_facts` / `src_clean_facts`. ⛔ Each defaults
    to `None`, and `None` is FAIL.
    """
    g = Gates()
    spec = cell.spec
    stats: dict[str, Any] = {}

    # ---- G-BAND ------------------------------------------------------------
    if smoke:
        g.add("G-BAND", False, "smoke", None, L.SMOKE_ALLOWED_REASONS["G-BAND"])
    else:
        ok = _eq(cell, g, "G-BAND", ("config.band_seed_start", "config.seed_start"),
                 spec.seed_start)
        n_dk, a1 = cell.resolve("config.n_decks")
        sp, a2 = cell.resolve("config.seatings_per_deck")
        if ok:
            sub_ok = (n_dk == spec.n_decks and sp == 2)
            g.add("G-BAND", sub_ok, f"{a1} + {a2}",
                  {"band_seed_start": spec.seed_start, "n_decks": n_dk,
                   "seatings_per_deck": sp},
                  "" if sub_ok else f"want n_decks={spec.n_decks}, seatings_per_deck=2")

    # ---- G-DECKS -----------------------------------------------------------
    seeds = sorted({int(r["seed"]) for r in cell.records if r.get("seed") is not None})
    per_deck = L.per_deck_margins(cell.records)
    n_common = len(per_deck)
    stats["seeds"] = seeds
    stats["n_common"] = n_common
    if smoke:
        g.add("G-DECKS", False, "records", {"n_common": n_common},
              L.SMOKE_ALLOWED_REASONS["G-DECKS"])
    else:
        rng = set(spec.seeds)
        out_of_range = [s for s in seeds if s not in rng]
        half = [s for s, v in L._by_deck(cell.records).items() if not (0 in v and 1 in v)]
        ok = (not out_of_range) and (not half) and n_common == spec.n_decks
        g.add("G-DECKS", ok, "raw seed*_a*.json records",
              {"n_seeds": len(seeds), "n_common": n_common,
               "out_of_range": out_of_range[:8], "half_paired": half[:8]},
              "" if ok else "seeds outside this cell's own range, decks counted at one "
                            "seat only, or n_common != the frozen deck count")

    # ---- G-SINGLEVAR (READ_RULE §3.3) --------------------------------------
    # ⚠️ The addresses were VERIFIED against a real emitted manifest, not written
    # from the design: the opponent's search knobs live one level down under
    # `config.opponent.champ_cfg.*`, not `config.opponent.*` (round 1's freeze
    # correction — a gate written from the design would have voided every cell).
    alias_pairs = (
        ("config.champion.k_dets", "config.opponent.k_dets"),
        ("config.champion.sims_per_det", "config.opponent.sims_per_det"),
        ("config.champion.total_sims", "config.opponent.total_sims"),
        ("config.champion.c_puct", "config.opponent.champ_cfg.c_puct"),
        ("config.champion.tau_p", "config.opponent.champ_cfg.tau_p"),
        ("config.champion.leaf_quantize", "config.opponent.champ_cfg.leaf_quantize"),
        ("config.champion.final_select", "config.opponent.champ_cfg.final_select"),
        ("config.champion.value_norm", "config.opponent.champ_cfg.value_norm"),
        ("config.endgame.exact_k", "config.opponent.endgame.exact_k"),
        ("config.endgame.mode", "config.opponent.endgame.mode"),
    )
    sv_bad = []
    for ca, oa in alias_pairs:
        cv, _ = cell.resolve(ca)
        ov, _ = cell.resolve(oa)
        # ⚠️ A MISSING opponent address is a FAIL, not a skip (READ_RULE §3.3).
        if cv is MISSING or ov is MISSING:
            sv_bad.append(f"{ca} / {oa}: MISSING ({cv is not MISSING}/{ov is not MISSING})")
        elif cv != ov:
            sv_bad.append(f"{ca}={cv!r} != {oa}={ov!r}")
    cand_leaf, _ = cell.resolve("config.cand_leaf_cfg")
    opp_leaf, _ = cell.resolve("config.opp_leaf_cfg")
    cand_flat = flatten(cand_leaf) if isinstance(cand_leaf, Mapping) else {}
    opp_flat = flatten(opp_leaf) if isinstance(opp_leaf, Mapping) else {}
    leaf_diff = {k for k in set(cand_flat) | set(opp_flat)
                 if cand_flat.get(k, MISSING) != opp_flat.get(k, MISSING)}
    want_keys = set(spec.leaf_diff_keys)
    # TWO-SIDED set equality: an extra differing key FAILS, and an expected-but-
    # identical key FAILS too (a side whose knob did not reach the leaf).
    # ⚠️ ROUND 2's SET IS BIGGER ON A C CELL — three keys, because the OPPONENT
    # carries alpha + cap and the candidate carries gamma. "The two sides differ
    # in exactly the pre-registered term knobs" is the round-2 statement of the
    # single-variable property; round 1's "the cell's ONE knob" no longer holds.
    leaf_ok = (leaf_diff == want_keys)
    stats["leaf_diff"] = sorted(leaf_diff)
    stats["leaf_diff_empty"] = (len(leaf_diff) == 0)
    sv_ok = (not sv_bad) and leaf_ok
    g.add("G-SINGLEVAR", sv_ok,
          "manifest:config.champion.* vs config.opponent.* (alias table) "
          "+ config.cand_leaf_cfg vs config.opp_leaf_cfg",
          {"alias_mismatches": sv_bad, "leaf_diff": sorted(leaf_diff),
           "leaf_diff_expected": sorted(want_keys), "opponent": spec.opponent},
          "" if sv_ok else "the two sides differ in something other than this cell's "
                           "pre-registered term knobs (set equality is TWO-SIDED)")

    # ---- G-LEAF (per-cell, TWO-SIDED; screen_lib.leaf_gate is the ONE impl) --
    opp_h, opp_a = cell.resolve("config.opp_leaf_hash", "config.opponent.leaf_hash")
    cand_h, cand_a = cell.resolve("config.cand_leaf_hash")
    curve, curve_a = cell.resolve("config.cand_leaf_cfg.v29_meeple_curve",
                                  "config.champion.leaf_cfg.v29_meeple_curve")
    lg = L.leaf_gate(spec,
                     None if cand_h is MISSING else cand_h,
                     None if opp_h is MISSING else opp_h,
                     None if curve is MISSING else curve)
    stats["cand_leaf_hash"] = None if cand_h is MISSING else cand_h
    stats["opp_leaf_hash"] = None if opp_h is MISSING else opp_h
    stats["leaf_gate"] = lg
    g.add("G-LEAF", lg["ok"], f"{opp_a} | {cand_a} | {curve_a}",
          {"conjuncts": lg["conjuncts"],
           "cand_leaf_hash": lg["cand_leaf_hash"],
           "cand_leaf_hash_expected": lg["cand_leaf_hash_expected"],
           "opp_leaf_hash": lg["opp_leaf_hash"],
           "opp_leaf_hash_expected": lg["opp_leaf_hash_expected"],
           "opponent": lg["opponent"]},
          "" if lg["ok"] else lg["why"])

    # ---- G-INVASION (BOTH SIDES, per cell) ---------------------------------
    full_leaf, full_a = cell.resolve("config.champion.leaf_cfg")
    full_inv = _invasion_subset(full_leaf)
    want_cand = dict(spec.cand_invasion)
    want_opp = dict(spec.opp_invasion)
    # (i) the CANDIDATE's FULL asdict block: its own knob at the frozen value and
    #     EVERY other invasion field at its default.
    expected_full = dict(L.INVASION_DEFAULTS)
    expected_full.update(want_cand)
    inv_ok = all(full_inv.get(k, L.INVASION_DEFAULTS[k]) == v
                 for k, v in expected_full.items())
    # (ii) the two `_leaf_dict` blocks, normalised so "absent" == "default".
    cand_inv = _nondefault_invasion(cand_leaf)
    opp_inv = _nondefault_invasion(opp_leaf)
    inv_ok = inv_ok and (cand_inv == want_cand) and (opp_inv == want_opp)
    # ⛔ ABSENT IS FAIL. Without this the gate passes VACUOUSLY on an empty
    # archive: "_leaf_dict drops a field at its default" makes every comparison
    # trivially true when there is no leaf dict at all.
    containers_present = (full_leaf is not MISSING and isinstance(full_leaf, Mapping)
                          and isinstance(cand_leaf, Mapping) and isinstance(opp_leaf, Mapping))
    inv_ok = inv_ok and containers_present
    g.add("G-INVASION", inv_ok, f"{full_a} + config.cand_leaf_cfg + config.opp_leaf_cfg",
          {"champion_leaf_cfg_invasion": full_inv,
           "cand_invasion": cand_inv, "cand_invasion_expected": want_cand,
           "opp_invasion": opp_inv, "opp_invasion_expected": want_opp,
           "opponent": spec.opponent},
          "" if inv_ok else
          "a knob is at the wrong value, a second weight is nonzero, or a side's "
          "invasion block is not the one this cell pre-registered. ⚠️ ROUND 2's "
          "OPPONENT EXPECTATION IS PER-CELL: the A/B cells' opponent carries NO "
          "invasion key; the C cells' opponent MUST carry invasion_alpha 0.09 @ "
          "cap 11.0 (the shape-B agent) and an EMPTY opponent block there means "
          "the env regime did not reach the harness")

    # ---- G-CAPFWD (BOTH SIDES; DESIGN §2.3) --------------------------------
    cap_cand = _cap_biconditional(full_inv)
    cap_opp = _cap_biconditional(opp_inv)
    # ⛔ ABSENT IS FAIL — same vacuity trap as G-INVASION: a biconditional over
    # defaulted-to-absent fields is trivially true on an empty archive.
    cap_ok = cap_cand and cap_opp and containers_present
    g.add("G-CAPFWD", cap_ok, f"{full_a} + config.opp_leaf_cfg",
          {"candidate_side_ok": cap_cand, "opponent_side_ok": cap_opp,
           "candidate_invasion": full_inv, "opponent_invasion": opp_inv},
          "" if cap_ok else "an INERT shape-B knob is set without a nonzero "
                            "invasion_alpha on one of the sides; leaf_config_rs "
                            "(rust_agent.py:181-185) would DROP it silently and the "
                            "manifest would LIE about the running leaf. ⚠️ ROUND 2 "
                            "CHECKS THE OPPONENT SIDE TOO — the C cells' opponent is "
                            "the only leaf in this program's history to carry a "
                            "nonzero alpha on the reference side")

    # ---- G-WHEEL -----------------------------------------------------------
    build, build_a = cell.resolve("carc_rs_build", "config.backend.carc_rs_build")
    bsha, bsha_a = cell.resolve("carc_rs_binary_sha", "config.backend.carc_rs_binary_sha")
    mixed, _ = cell.resolve("mixed_builds", "config.backend.mixed_builds")
    probe_ok, probe_why = L.wheel_probe_ok(wheel_probe)
    anc = wheel_ancestry if isinstance(wheel_ancestry, Mapping) else None
    anc_ok = bool(anc and anc.get("ok"))
    anc_why = (anc or {}).get("why", "wheel-ancestry verdict ABSENT — ABSENT is FAIL")
    w_ok = bool(build) and build is not MISSING and bsha not in (MISSING, None) \
        and mixed is False and probe_ok and anc_ok
    g.add("G-WHEEL", w_ok, f"{build_a} + {L.WHEEL_PROBE_FILENAME} + git ancestry",
          {"carc_rs_build": None if build is MISSING else build,
           "carc_rs_binary_sha": None if bsha is MISSING else bsha,
           "mixed_builds": None if mixed is MISSING else mixed,
           "wheel_probe": probe_why,
           "embedded_rev": (anc or {}).get("rev"),
           "invasion_source_present": (anc or {}).get("invasion_source_present"),
           "is_ancestor": (anc or {}).get("is_ancestor")},
          "" if w_ok else "⚠️ carc_rs_version is permanently '0.1.0' and is NOT a build "
                          "discriminator; the fingerprint is carc_rs_build's embedded rev "
                          f"+ the launcher's recorded NONZERO-kwarg forward. {anc_why}")

    # ---- G-WHEEL-SAME (⭐ ROUND-LEVEL; round 1's IDENT, inherited) ----------
    same_ok, same_why = L.wheel_is_r1s(None if bsha is MISSING else bsha,
                                       None if build is MISSING else build)
    g.add("G-WHEEL-SAME", same_ok, f"{bsha_a} + {build_a}",
          {"carc_rs_binary_sha": None if bsha is MISSING else bsha,
           "expected_binary_sha": L.R1_WHEEL_BINARY_SHA,
           # ⛔ INFORMATIONAL — the build string embeds the REPO REV AT CALL TIME,
           # not a compiled-in value, so it is NOT a wheel discriminator and is
           # NOT compared. The code-rev question is G-REV's.
           "carc_rs_build_informational": None if build is MISSING else build,
           "round_1_build_informational": L.R1_WHEEL_BUILD_INFORMATIONAL,
           "inherited_ident": L.R1_IDENT},
          "" if same_ok else same_why)

    # ---- G-HOST (⭐ the frozen two-box assignment, checked) -----------------
    host, host_a = cell.resolve("host", "config.host")
    if smoke:
        g.add("G-HOST", False, host_a, {"host": None if host is MISSING else host},
              L.SMOKE_ALLOWED_REASONS["G-HOST"])
    else:
        h_ok, h_why = L.host_matches_box(None if host is MISSING else host, spec.box)
        g.add("G-HOST", h_ok, host_a,
              {"host": None if host is MISSING else host,
               "frozen_box": spec.box,
               "box_label": L.BOXES[spec.box]["label"],
               "cells_frozen_to_this_box": [c.name for c in L.cells_of_box(spec.box)]},
              "" if h_ok else h_why)

    # ---- G-RULES -----------------------------------------------------------
    rn, rn_a = cell.resolve("rules_profile.name", "config.rules_profile.name")
    r9ok, _ = cell.resolve("rules_profile.r9_env_ok", "config.rules_profile.r9_env_ok")
    r9obs, _ = cell.resolve("rules_profile.r9_env_observed",
                            "config.rules_profile.r9_env_observed")
    ru_ok = (rn == "fixed_v1" and r9ok is True and r9obs is True)
    g.add("G-RULES", ru_ok, rn_a,
          {"name": rn, "r9_env_ok": r9ok, "r9_env_observed": r9obs},
          "" if ru_ok else "fixed_v1 wants R9 ON (non-inverted expectation)")

    # ---- G-BACKEND ---------------------------------------------------------
    bn, bn_a = cell.resolve("config.backend.name")
    br, _ = cell.resolve("config.backend.requested")
    cs, _ = cell.resolve("config.backend.converted_sides")
    be_ok = (bn == "rust" and br == "rust" and mixed is False
             and isinstance(cs, list) and set(cs) == {"candidate", "opponent"})
    g.add("G-BACKEND", be_ok, bn_a,
          {"name": bn, "requested": br, "converted_sides": cs, "mixed_builds": mixed},
          "" if be_ok else "BOTH sides must be rust-resolved: the invasion family exists "
                           "ONLY in rust, so a python leg raises on a nonzero weight or "
                           "(worse, on a stale-wheel path) serves an invasion-BLIND leaf "
                           "that reads as a null. ⚠️ ROUND 2 NEEDS THIS ON THE OPPONENT "
                           "SIDE AS MUCH AS THE CANDIDATE'S: the C cells' OPPONENT carries "
                           "a nonzero weight, so an unconverted opponent leg would either "
                           "raise or silently play the plain champion — which is exactly "
                           "the cell SHAPES.md §3 forbids")

    # ---- G-BUDGET ----------------------------------------------------------
    bud = {}
    for side, base in (("candidate", "config.champion"), ("opponent", "config.opponent")):
        k, _ = cell.resolve(f"{base}.k_dets")
        s, _ = cell.resolve(f"{base}.sims_per_det")
        t, _ = cell.resolve(f"{base}.total_sims")
        bud[side] = {"k_dets": k, "sims_per_det": s, "total_sims": t}
    bu_ok = all(
        v["k_dets"] == 4 and v["sims_per_det"] == 688 and v["total_sims"] == 2752
        and v["k_dets"] * v["sims_per_det"] == v["total_sims"]
        for v in bud.values()
        if not any(x is MISSING for x in v.values())
    ) and not any(x is MISSING for v in bud.values() for x in v.values())
    g.add("G-BUDGET", bu_ok, "manifest:config.champion.* / config.opponent.*", bud,
          "" if bu_ok else "both sides must be (4, 688, 2752) and the product must "
                           "multiply out")

    # ---- G-TIEARB (three conjuncts; carried verbatim) ----------------------
    ta_en, ta_a = cell.resolve("cand_tiearb.enabled", "config.cand_tiearb.enabled")
    a_conj = (ta_en is MISSING) or (ta_en is False)
    armed_leaves = []
    for doc in DOCS:
        for k, v in cell.flat[doc].items():
            if k.split(".")[-1] == "tiearb_enabled" and v is True:
                armed_leaves.append(f"{doc}:{k}")
    a2_conj = not armed_leaves
    stray = []
    for doc in DOCS:
        for seg in container_segments(getattr(cell, doc)):
            last = seg.split(".")[-1]
            if "tiearb" in last and last != "cand_tiearb":
                stray.append(f"{doc}:{seg}")
    b_conj = not stray
    # ⛔ ABSENT IS FAIL. All three conjuncts are "nothing bad was found", which is
    # trivially true of an archive with no documents at all.
    ta_ok = a_conj and a2_conj and b_conj and bool(cell.manifest)
    g.add("G-TIEARB", ta_ok, ta_a,
          {"cand_tiearb.enabled": None if ta_en is MISSING else ta_en,
           "armed_tiearb_enabled_leaves": armed_leaves,
           "stray_tiearb_containers": stray},
          "" if ta_ok else "(b) scans CONTAINER segments only — a healthy archive emits a "
                           "TERMINAL config.champion.tiearb_enabled=false, which (a2) "
                           "checks instead (round 1's freeze-time correction)")

    # ---- G-EXACT -----------------------------------------------------------
    ek, ek_a = cell.resolve("config.endgame.exact_k")
    em, _ = cell.resolve("config.endgame.mode")
    oek, _ = cell.resolve("config.opponent.endgame.exact_k")
    oem, _ = cell.resolve("config.opponent.endgame.mode")
    ex_ok = (ek == 2 and em == "marginalized" and oek == 2 and oem == "marginalized")
    g.add("G-EXACT", ex_ok, ek_a,
          {"exact_k": ek, "mode": em, "opp_exact_k": oek, "opp_mode": oem},
          "" if ex_ok else "K=3/4 are clairvoyant-only; a fair cell cannot run them")

    # ---- G-REV -------------------------------------------------------------
    cr, cr_a = cell.resolve("config.code_rev", "code_rev")
    rv_ok, rv_why = L.rev_matches(None if cr is MISSING else cr, pinned_src_rev)
    sc = src_clean if isinstance(src_clean, Mapping) else None
    sc_ok = bool(sc and sc.get("ok"))
    sc_why = (sc or {}).get("why", "SRC_CLEAN verdict ABSENT — ABSENT is FAIL")
    _, whole_tree_dirty = L.split_dirty("" if cr is MISSING else str(cr))
    g.add("G-REV", rv_ok and sc_ok, f"{cr_a} + SRC_CLEAN.jsonl",
          {"code_rev": None if cr is MISSING else cr,
           "pinned_src_rev": pinned_src_rev,
           # ⭐ WHOLE-TREE dirt is INFORMATIONAL (the main tree is perpetually
           # dirty with measurement artifacts). The FATAL, code-path-scoped
           # verdict is SRC_CLEAN.jsonl's.
           "whole_tree_dirty_marker": whole_tree_dirty,
           "whole_tree_dirty_is_informational": True,
           "code_paths_clean_at_every_boundary": (sc or {}).get("ok"),
           "boundaries": (sc or {}).get("boundaries"),
           "dirty_boundaries": (sc or {}).get("dirty_boundaries"),
           "missing_after": (sc or {}).get("missing_after")},
          rv_why if not rv_ok else ("" if sc_ok else f"rev OK, but {sc_why}"))

    # ---- G-BLIND -----------------------------------------------------------
    stamp, st_a = cell.resolve("BLIND_COMMIT", "config.stamps.BLIND_COMMIT")
    stamped_ok = bool(blind_commit) and L.is_hex40(blind_commit or "") \
        and (stamp is not MISSING) and str(stamp) == blind_commit
    bp = blind_proof if isinstance(blind_proof, Mapping) else None
    bp_ok = bool(bp and bp.get("ok"))
    bp_why = (bp or {}).get("why", "blind-ancestry verdict ABSENT — ABSENT is FAIL")
    bl_ok = stamped_ok and bp_ok
    g.add("G-BLIND", bl_ok, f"{st_a} + BLIND_PROOF.json + git ancestry",
          {"BLIND_COMMIT_file": blind_commit,
           "stamped_in_manifest": None if stamp is MISSING else stamp,
           "is_ancestor_of_head": (bp or {}).get("is_ancestor_of_head"),
           "introduced_frozen_banner": (bp or {}).get("introduced_frozen_banner"),
           "proof_ok": (bp or {}).get("proof_ok")},
          "" if bl_ok else ("BLIND_COMMIT must be a 40-hex sha, an ANCESTOR of HEAD, the "
                            "commit that introduced the FROZEN banner, agreed by "
                            "BLIND_PROOF.json, and every cell must carry it as a "
                            f"--stamp-key. {'' if stamped_ok else 'stamp mismatch. '}{bp_why}"))

    # ---- statistics (needed by G-N / G-SAT / RECON / the branches) ---------
    n_scored, _ = cell.resolve("n")
    n_failed, nf_a = cell.resolve("n_failed")
    wr, wr_a = cell.resolve("winrate")
    if n_scored is MISSING:
        n_scored = None
    if n_failed is MISSING:
        n_failed = None
    if wr is MISSING:
        wr = None
    rep = {s: cell.resolve(s)[0] for s in L.RECON_STATS}
    w_mean, w_z, w_n, w_se, _ = L.paired_margin(cell.records)
    w_elo = L.winrate_elo(cell.records)
    witness = {"paired_mean_margin": w_mean, "paired_z": w_z, "n_paired": w_n,
               "winrate": w_elo["winrate"], "elo": w_elo["elo"]}
    rep = {k: (None if v is MISSING else v) for k, v in rep.items()}
    stats.update({"n_scored": n_scored, "n_failed": n_failed, "winrate": wr,
                  "reported": rep, "witness": witness,
                  "D": rep.get("paired_mean_margin"), "z": rep.get("paired_z"),
                  "se": w_se, "WDL": (w_elo["W"], w_elo["D"], w_elo["L"]),
                  "elo": rep.get("elo")})

    # ---- G-N ---------------------------------------------------------------
    if smoke:
        g.add("G-N", False, nf_a, {"n": n_scored, "n_failed": n_failed},
              L.SMOKE_ALLOWED_REASONS["G-N"])
    else:
        # ⚠️ ABSENT is FAIL: a missing n_failed does NOT become a permissive 0.
        nf = None if n_failed is None else int(n_failed)
        denom = max(int(n_scored or 0) + (nf or 0), 1)
        rate = (nf / denom) if nf is not None else None
        n_ok = (n_scored == spec.n_games and nf == 0
                and n_common >= math.floor(L.N_COMMON_FRAC * spec.n_decks))
        stats["failure_rate"] = rate
        g.add("G-N", n_ok, nf_a,
              {"n": n_scored, "n_failed": nf, "failure_rate": rate, "n_common": n_common,
               "n_common_floor": math.floor(L.N_COMMON_FRAC * spec.n_decks)},
              "" if n_ok else f"a failure rate < {L.FAILURE_RATE_VOID:.0%} is REPORTED, "
                              "never silently absorbed; at or above it the cell voids")

    # ---- G-SAT -------------------------------------------------------------
    if smoke:
        g.add("G-SAT", False, wr_a, {"winrate": wr}, L.SMOKE_ALLOWED_REASONS["G-SAT"])
    else:
        lo, hi = L.SAT_WR
        s_ok = (wr is not MISSING and wr is not None and lo <= float(wr) <= hi)
        g.add("G-SAT", s_ok, wr_a, {"winrate": wr, "band": [lo, hi]},
              "" if s_ok else "a RAIL check, not a strength bar: both sides are the same "
                              "search differing only by the pre-registered leaf terms, so "
                              "a winrate outside this window means the two sides are not "
                              "the agents this design says they are")

    # ---- RECON (witness; can only VOID, never move a number) ---------------
    recon_bad = []
    for s in L.RECON_STATS:
        a, b = rep.get(s), witness.get(s)
        if not L.recon_close(a, b):
            recon_bad.append(f"{s}: reported {a!r} vs witness {b!r}")
    if smoke:
        hard = [x for x in recon_bad if not x.startswith("n_paired")]
        g.add("RECON", not hard, "summary.json vs raw records",
              {"mismatches": recon_bad},
              L.SMOKE_ALLOWED_REASONS["RECON/n_paired"] if recon_bad else "")
        if recon_bad and not hard:
            g.results["RECON"]["smoke_subcheck"] = "RECON/n_paired"
    else:
        g.add("RECON", not recon_bad, "summary.json vs raw records",
              {"mismatches": recon_bad},
              "" if not recon_bad else "the WITNESS disagrees beyond rel 1e-6 / abs 1e-9 "
                                       "— it can only VOID, never move, the number")

    return g, stats


# ═══════════════════════════════════════════════════════════════════════════ #
# RENDERING (READ_RULE.md §4.3 — MANDATORY on every branch)                   #
# ═══════════════════════════════════════════════════════════════════════════ #
def _f(x, nd=4):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return "nan" if math.isnan(x) else f"{x:+.{nd}f}"
    return str(x)


def render(report: dict) -> str:
    o: list[str] = []
    P = o.append
    P("=" * 79)
    P("INVASION-RISK TERM FAMILY — ROUND-2 BRACKET AT 2752 — ADJUDICATION")
    P("=" * 79)
    P(f"ROUND BRANCH: {report['round_branch']}")
    P("")

    # ---- the inherited IDENT, stated on every branch -----------------------
    P("--- §3.4 THE INHERITED IDENT (round 2 runs NO identity cell) " + "-" * 17)
    ws = report.get("wheel_same") or {}
    P(f"  round 1's IDENT: n={L.R1_IDENT['n_games']} games, D={_f(L.R1_IDENT['D'])}, "
      f"z={_f(L.R1_IDENT['z'])} (bar |z| <= {L.R1_IDENT['bar']}) -> "
      f"{L.R1_IDENT['verdict']}")
    P(f"  the inheritance is valid iff the WHEEL has not moved: G-WHEEL-SAME "
      f"{'PASS' if ws.get('ok') else 'FAIL'}")
    P(f"    observed binary_sha {ws.get('binary_sha')!r} vs round 1's "
      f"{L.R1_WHEEL_BINARY_SHA!r}")
    if not ws.get("ok"):
        P(f"    ⛔ {ws.get('why')}")
    P("  ⚠️ the SAME wheel FILE is installed on BOTH boxes, so this sha is "
      "expected to be")
    P("     identical on every cell regardless of host. ⛔ A laptop-local REBUILD "
      "would")
    P("     produce different bytes, a different sha, and this gate would REFUSE "
      "— correctly.")
    P("")

    # ---- §6.5 the two-box split -------------------------------------------
    P("--- §6.5 THE TWO-BOX SPLIT " + "-" * 51)
    P(f"  {L.BOX_ASSIGNMENT_RULE}")
    for role in L.BOX_ROLES:
        names = [c.name for c in L.cells_of_box(role)]
        pv = (report.get("provenance") or {}).get(role, {})
        P(f"    {role:7s} W={L.BOXES[role]['W']:<3d} {L.BOXES[role]['label']}")
        P(f"            cells {names}")
        P(f"            provenance {'PER-BOX' if pv.get('is_per_box') else 'FALLBACK (adjudicator dir)'} "
          f"@ {pv.get('dir')}")
        P(f"            PINNED_SRC_REV {pv.get('pinned_src_rev')}")
    P(f"  ONE CODE REV ACROSS BOTH BOXES: "
      f"{'PASS' if report.get('cross_box_rev_ok') else '⛔ FAIL'}  "
      f"{report.get('code_revs')}")
    P(f"  ⚠️ {L.LAPTOP_RATIO_NOTE}")
    P("  REALIZED per-box cost (from each cell's own summary; compare against the")
    P(f"     assumed {L.LAPTOP_RATIO_ASSUMED}x and REPORT the discrepancy):")
    for role in L.BOX_ROLES:
        obs = [report["cells"][c.name]["cost"]
               for c in L.cells_of_box(role) if c.name in report["cells"]]
        ms = [o["cand_ms"] + o["opp_ms"] for o in obs
              if o.get("cand_ms") and o.get("opp_ms")]
        P(f"    {role:7s} mean (cand+opp) ms/move over its cells: "
          f"{(sum(ms) / len(ms)) if ms else float('nan'):.1f}")
    P("")

    # 1 + 2 + 3 — per cell
    P("--- §4.3(1) PER CELL " + "-" * 57)
    for name in L.CELL_NAMES:
        c = report["cells"].get(name)
        spec = L.cell_by_name(name)
        if not c:
            P(f"  {name}: ABSENT from the run directory — U-UNREADABLE")
            continue
        s = c["stats"]
        ci = c.get("ci") or (None, None)
        P(f"  {name:6s} [{spec.shape} {spec.rung}: {spec.knob}={spec.weight}] "
          f"vs {spec.opponent.upper()}  box={spec.box}  "
          f"branch={c['branch']:<12s} "
          f"n_common={s.get('n_common')} n_failed={s.get('n_failed')}")
        P(f"         D={_f(s.get('D'))} SE={_f(s.get('se'))} z={_f(s.get('z'))}  "
          f"95% CI [{_f(ci[0])}, {_f(ci[1])}]")
        P(f"         winrate={_f(s.get('winrate'), 4)} W/D/L={s.get('WDL')} "
          f"elo={_f(s.get('elo'), 2)}")
        P(f"         leaves: cand {s.get('cand_leaf_hash')} vs opp "
          f"{s.get('opp_leaf_hash')}  (pinned {spec.cand_leaf_hash} / "
          f"{spec.opp_leaf_hash})")
        an = c["se_anomaly"]
        P(f"         §4.3(2) SE realized {_f(an['realized'])} vs modelled "
          f"{_f(an['modelled'])} ratio={_f(an['ratio'])} "
          f"{'⚠️ FLAGGED' if an['flagged'] else 'ok'}  ({an.get('direction')})")
        ed = c["elo_display"]
        P(f"         §4.3(3) elo limb={ed['limb']} — {ed['label']}")
        if ed["limb"] == "own-ratio":
            P(f"                 elo/pt={_f(ed['elo_per_point'], 2)} "
              f"bracket={ed['elo_per_point_bracket']} {ed['anomaly_note']}")
        else:
            P(f"                 2σ bound ±{_f(ed['two_sigma_pts'])} pts ≈ "
              f"±{_f(ed['two_sigma_elo_lo'], 1)}..±{_f(ed['two_sigma_elo_hi'], 1)} elo "
              f"(BRACKET CONVERSION, not a measured scale)")
        if spec.shape == "C":
            P(f"         §4.6 DEFENCE READING: {c.get('c_reading')}")
    P("")

    # ⭐ 4.5 — the pre-registered within-round contrast
    P("--- §4.5 THE PRE-REGISTERED WITHIN-ROUND LOW-vs-HIGH CONTRAST " + "-" * 16)
    P("  ⛔ NOT A PROMOTION INPUT — a SHAPE reading and a round-3 input. Promotion")
    P("     is per-cell, against ZERO, at the cell's own realized SE.")
    for sh in L.SHAPES:
        ct = report["contrasts"].get(sh) or {}
        lad = L.LADDER[sh]
        P(f"    {sh} ({lad['knob']} {lad['low']} -> {lad['high']}): "
          f"Δ={_f(ct.get('delta'))} SE={_f(ct.get('se'))} z={_f(ct.get('z'))} "
          f"-> {ct.get('verdict')}")
        if ct.get("readable"):
            lo, hi = ct["ci95"]
            P(f"        95% CI [{_f(lo)}, {_f(hi)}]  ({ct.get('direction')})")
        else:
            P(f"        {ct.get('why')}")
    P(f"    {L.shape_contrast(None, None)['why']}")
    P("    power, computed BEFORE any answer existed:")
    for row in L.CONTRAST_POWER:
        P(f"      σ={row['sigma_model']}: SE(Δ)={row['se_delta']:.4f}, "
          f"2σ-resolvable at |Δ| >= {row['mde_2sigma_pts']:.4f} pts/deck "
          f"({row['note']})")
    P("")

    # ⭐ the r1 overlay
    P("--- §4.5b ROUND 1's MIDS — DESCRIPTIVE OVERLAY ONLY " + "-" * 27)
    P(f"  {L.R1_OVERLAY_RULE}")
    for sh in ("A", "B", "D"):
        m = L.R1_MIDS[sh]
        lad = L.LADDER[sh]
        row = []
        for rung in ("low", "mid", "high"):
            if rung == "mid":
                row.append(f"{lad['mid']}=r1:{m['D']:+.4f}(z{m['z']:+.3f})")
            else:
                cn = next((c.name for c in L.cells_of_shape(sh) if c.rung == rung), None)
                cell = report["cells"].get(cn) if cn else None
                if cell:
                    row.append(f"{lad[rung]}=r2:{cell['stats'].get('D'):+.4f}"
                               f"(z{cell['stats'].get('z'):+.3f})")
                else:
                    row.append(f"{lad[rung]}=NOT RUN")
        P(f"    {sh} {lad['knob']}: " + "  |  ".join(row))
    P(f"    {L.D_NOT_RUN}")
    P("")

    # ⭐ 4.7 — the ladder rules
    P("--- §4.7 THE LADDER RULES " + "-" * 52)
    P(f"  {L.AB_ENDPOINT_RULE}")
    P(f"  {L.C_INTERIOR_RULE}")
    ns = report.get("noise_signature") or {}
    P(f"  C interior noise-signature check: applicable={ns.get('applicable')} "
      f"fired={ns.get('fired')}")
    P(f"    {ns.get('why')}")
    P("")

    # 5 — gates
    P("--- §4.3(5) GATES (all 18, every cell) " + "-" * 39)
    for name in L.CELL_NAMES:
        c = report["cells"].get(name)
        if not c:
            continue
        P(f"  [{name}]")
        for gid in L.GATE_IDS:
            r = c["gates"].get(gid)
            if not r:
                P(f"    {gid:<14s} ---- not evaluated")
                continue
            mark = "PASS" if r["ok"] else "FAIL"
            P(f"    {gid:<14s} {mark}  @{r['address']}")
            if not r["ok"] and r.get("note"):
                P(f"                   ↳ {r['note']}")
    P("")

    # 4 — power table
    P("--- §4.3(4) POWER (computed BEFORE any answer existed) " + "-" * 23)
    P("  ⛔ A NULL IS A BOUND, NOT A ZERO.")
    P(f"  frozen model σ_D={L.SIGMA_D_MODEL} -> SE={L.se_model(400):.4f} at n=400;")
    P(f"  round 1 REALIZED σ_D {L.R1_REALIZED_SIGMA_D} -> SE≈0.5987 on its B arm.")
    for row in L.POWER_TABLE:
        P(f"    Δ={row['true_effect_pts']:+.2f} pts/deck  "
          f"model z={row['z_at_model_se']:.2f} power {row['power_model']:>5s}  |  "
          f"realized z={row['z_at_realized_se']:.2f} power {row['power_realized']:>5s}"
          f"  {row['note']}")
    P("")

    # 6 — the cost multiplier
    P("--- §4.3(6) INVASION-ARITHMETIC COST MULTIPLIER " + "-" * 30)
    P("  ⛔ DESCRIPTIVE-ONLY — TENANCY-SENSITIVE, NOT A GATE (DESIGN §6.3).")
    P(f"  round 1's IDENT control: {L.R1_IDENT['cost_multiplier']:.3f} "
      f"(both sides weight-0)")
    for name in L.CELL_NAMES:
        c = report["cells"].get(name)
        if not c:
            continue
        m = c["cost"]
        spec = L.cell_by_name(name)
        tag = ("  ⚠️ BOTH SIDES pay invasion arithmetic on a C cell — the ratio is "
               "gamma-vs-alpha, NOT term-vs-plain" if spec.shape == "C" else "")
        P(f"    {name:6s} [{spec.box}] candidate {_f(m['cand_ms'], 1)} ms/move  "
          f"opponent {_f(m['opp_ms'], 1)} ms/move  "
          f"multiplier {_f(m['multiplier'], 3)}  "
          f"projected {m['projected_s_per_game']:.1f} s/game "
          f"(local-equiv {m['projected_s_per_game_local_equiv']:.1f}){tag}")
    P("")

    # 7 — frozen inputs
    P("--- §4.3(7) THE FROZEN INPUTS, RESTATED " + "-" * 38)
    d = L.FROZEN_DERIVATION
    P(f"  G (champion sibling-move value gap) = {d['G_sibling_p90_minus_p10']} leaf pts")
    P(f"  target = {d['target_fraction_of_G']:.2f} × G = {d['target_contribution_pts']} pts")
    P(f"  M_A={d['M_A']} M_B={d['M_B']} M_C={d['M_C']} M_D={d['M_D']}")
    P(f"  ladder rule: {d['ladder_rule']}")
    P(f"  corroboration: {d['corroboration']}")
    P(f"  band {L.BAND}:")
    for c in L.CELLS:
        P(f"    {c.name:6s} {c.seed_start}..{c.seed_end}  {c.n_decks} decks / "
          f"{c.n_games} games  cand {c.cand_leaf_hash} vs opp {c.opp_leaf_hash}")
    P("")

    # 8 — the ladder as run
    P("--- §4.3(8) THE LADDER AS RUN " + "-" * 48)
    for k, v in L.LADDER.items():
        P(f"    {k}: {v['knob']}  low {v['low']} / mid {v['mid']} / high {v['high']}  "
          f"[mid: {v.get('mid_source', '')}] {v.get('note', '')}")
    P("")

    P("--- §4.6 SHAPE C'S OPPONENT " + "-" * 50)
    P(f"  {L.C_OPPONENT_NOTE}")
    P(f"  {L.C_NEVER_PROMOTES_ALONE}")
    P("")

    P("--- §5 WHAT NO BRANCH DOES " + "-" * 51)
    for line in L.NO_BRANCH_DOES:
        P(f"    · {line}")
    P("")
    P("--- §6 THE STATED PRIOR (recorded BEFORE game 1) " + "-" * 29)
    P(f"    {L.STATED_PRIOR}")
    P("")
    P("=" * 79)
    return "\n".join(o)


# ═══════════════════════════════════════════════════════════════════════════ #
# MODES                                                                       #
# ═══════════════════════════════════════════════════════════════════════════ #
def _read_text(p: Path) -> str | None:
    try:
        return p.read_text().strip()
    except Exception:
        return None


def _read_json(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def _repo_root() -> Path:
    r = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else HERE.parents[1]


def _box_provenance(run_dir: Path, role: str) -> Path:
    """⭐ WHERE A CELL'S LAUNCH ARTIFACTS LIVE IN A TWO-BOX ROUND.

    Each box writes `PINNED_SRC_REV`, `SRC_CLEAN.jsonl`, `BLIND_PROOF.json` and
    `WHEEL_PROBE.json` into ITS OWN repo checkout — which the LOCAL adjudicator
    cannot see. So each launcher also copies them to
    `<out-root>/_provenance/<role>/` on the SHARE, and `G-REV`, `G-BLIND` and
    `G-WHEEL` evaluate every cell against **its own box's** artifacts.

    ⚠️ FALLS BACK to this directory when no per-box copy exists, so a single-box
    run, the §9 smoke and `--selftest` all keep working unchanged.
    """
    p = run_dir / L.provenance_subdir(role)
    return p if p.is_dir() else HERE


def adjudicate(run_dir: Path) -> dict:
    repo = _repo_root()

    # ---- per-box launch artifacts (§6.5) -----------------------------------
    prov: dict[str, dict] = {}
    for role in L.BOX_ROLES:
        d = _box_provenance(run_dir, role)
        pinned = _read_text(d / "PINNED_SRC_REV")
        blind = _read_text(d / "BLIND_COMMIT") or _read_text(HERE / "BLIND_COMMIT")
        prov[role] = {
            "dir": str(d), "is_per_box": d != HERE,
            "pinned_src_rev": pinned, "blind_commit": blind,
            "wheel_probe": _read_json(d / L.WHEEL_PROBE_FILENAME),
            "blind_facts": blind_facts(repo, blind,
                                       _read_json(d / "BLIND_PROOF.json"),
                                       HERE / "DESIGN.md", HERE / "READ_RULE.md"),
            "src_clean": src_clean_facts(
                d / "SRC_CLEAN.jsonl", [c.name for c in L.cells_of_box(role)]),
        }

    cells: dict[str, dict] = {}
    for spec in L.CELLS:
        path = run_dir / spec.out_subdir
        if not path.is_dir():
            continue
        cell = Cell(spec, path)
        build, _ = cell.resolve("carc_rs_build", "config.backend.carc_rs_build")
        wanc = wheel_ancestry_facts(repo, None if build is MISSING else build)
        pv = prov[spec.box]
        gates, stats = run_gates(cell, pinned_src_rev=pv["pinned_src_rev"],
                                 blind_commit=pv["blind_commit"],
                                 wheel_probe=pv["wheel_probe"], wheel_ancestry=wanc,
                                 blind_proof=pv["blind_facts"],
                                 src_clean=pv["src_clean"])
        cells[spec.name] = {"gates": gates.results, "stats": stats, "box": spec.box}

    # ⭐ ONE CODE REV ACROSS BOTH BOXES. `G-REV` checks each cell against its own
    # box's PINNED_SRC_REV; this checks that the two boxes were at the SAME rev,
    # which is what the git-bundle sync exists to guarantee and the property that
    # makes seven cells one round rather than two.
    revs = {n: (c["gates"].get("G-REV", {}).get("observed") or {}).get("code_rev")
            for n, c in cells.items()}
    # AMENDMENT IS-A1 (2026-08-27, owner-authorized re-read per the h2h-option-1
    # precedent): the frozen clause compared the boxes' EMITTED short revs for
    # string equality — but `git rev-parse --short` length varies PER CLONE
    # (disambiguation), so two boxes at the IDENTICAL commit can emit
    # '240626a3-dirty' vs '240626a31f-dirty' and falsely void a single-rev
    # round. Canonical form: strip '-dirty', then each rev must be a PREFIX of
    # the shared 40-hex PINNED_SRC_REV (both boxes' pin files verified
    # byte-identical: 240626a31feeab01e22e73b42230a80a9889ec6f). Same defect
    # class as h2h G-REV (short-sha-vs-full) — cross-box variant.
    pin = (HERE / "PINNED_SRC_REV").read_text().strip() if (HERE / "PINNED_SRC_REV").exists() else ""
    def _canon_ok(rv):
        if not rv: return False
        base = rv[:-6] if rv.endswith("-dirty") else rv
        return bool(pin) and pin.startswith(base)
    distinct = {r for r in revs.values() if r}
    cross_box_rev_ok = (len(distinct) <= 1) or all(_canon_ok(r) for r in distinct)
    if not cross_box_rev_ok:
        for n, c in cells.items():
            r = c["gates"].get("G-REV")
            if r is not None:
                r["ok"] = False
                r["note"] = (f"⛔ CROSS-BOX REV DISAGREEMENT: the round's cells "
                             f"report {sorted(distinct)}. The two boxes were NOT "
                             "at the same commit, so this is a mixed-rev round "
                             "(the track_d2_prep defect, across machines). The "
                             "git-bundle sync exists to prevent exactly this. "
                             + (r.get("note") or ""))

    # ---- G-WHEEL-SAME: ROUND-WIDE (READ_RULE §3.4) -------------------------
    # ⭐ THE ROUND-LEVEL GATE, applied exactly as round 1 applied G-IDENT: it is
    # computed per cell (every manifest carries the fingerprint) but a FAIL on
    # ANY cell voids EVERY cell, because the proposition is about the wheel the
    # round ran on, not about one archive.
    if not cells:
        wheel_same = {"ok": False, "binary_sha": None, "build": None,
                      "why": ("no cell archive exists — the wheel fingerprint cannot "
                              "be read. ABSENT is FAIL.")}
    else:
        per_cell = {}
        for name, c in cells.items():
            r = c["gates"].get("G-WHEEL-SAME") or {}
            per_cell[name] = bool(r.get("ok"))
        first = cells[next(iter(cells))]["gates"].get("G-WHEEL-SAME", {})
        obs = first.get("observed", {}) or {}
        wheel_same = {
            "ok": all(per_cell.values()),
            "per_cell": per_cell,
            "binary_sha": obs.get("carc_rs_binary_sha"),
            "build_informational": obs.get("carc_rs_build_informational"),
            "expected_binary_sha": L.R1_WHEEL_BINARY_SHA,
            "why": first.get("note", ""),
            "inherited_ident": L.R1_IDENT,
        }
    for name, c in cells.items():
        # a fail ANYWHERE voids EVERYWHERE
        r = c["gates"].get("G-WHEEL-SAME")
        if r is not None and not wheel_same["ok"]:
            r["ok"] = False
            if not r["note"]:
                r["note"] = ("another cell's wheel fingerprint failed — a wheel move "
                             "voids the WHOLE round, not one cell (READ_RULE §3.4)")

    # ---- branches ----------------------------------------------------------
    for name, c in cells.items():
        gates_ok = all(r["ok"] for r in c["gates"].values())
        s = c["stats"]
        spec = L.cell_by_name(name)
        c["branch"] = L.branch_for_cell(s.get("z"), gates_ok)
        se = s.get("se")
        D = s.get("D")
        c["ci"] = ((D - 1.96 * se, D + 1.96 * se)
                   if (se is not None and D is not None) else (None, None))
        c["se_anomaly"] = L.se_anomaly(se, spec.n_decks)
        c["elo_display"] = L.elo_display(s.get("z"), D, s.get("elo"), se)
        if spec.shape == "C":
            c["c_reading"] = L.c_reading(c["branch"], s.get("z"))

    # ---- §4.5 the within-round contrasts -----------------------------------
    contrasts = {}
    for sh in L.SHAPES:
        lo = next((c for c in L.cells_of_shape(sh) if c.rung == "low"), None)
        hi = next((c for c in L.cells_of_shape(sh) if c.rung == "high"), None)
        contrasts[sh] = L.shape_contrast(
            (cells.get(lo.name) or {}).get("stats") if lo else None,
            (cells.get(hi.name) or {}).get("stats") if hi else None)

    # ---- §4.7 the noise-signature check on C's INTERIOR rung ---------------
    def _st(n):
        return (cells.get(n) or {}).get("stats")
    noise = L.noise_signature(_st("C_MID"), _st("C_LOW"), _st("C_HIGH"))

    # cost multiplier, read off each cell's summary
    for name, c in cells.items():
        spec = L.cell_by_name(name)
        path = run_dir / spec.out_subdir
        summ = _read_json(path / "summary.json") or {}
        cand_ms = summ.get("champ_prefix_ms_per_move")
        opp_ms = summ.get("rung_ms_per_move")
        proj = L.project_cell_cost(spec)
        c["cost"] = {
            "cand_ms": cand_ms, "opp_ms": opp_ms,
            "multiplier": (cand_ms / opp_ms) if (cand_ms and opp_ms) else None,
            "projected_s_per_game": proj["s_per_game"],
            "projected_s_per_game_local_equiv": proj["s_per_game_local_equiv"],
            "box": spec.box, "box_ratio_assumed": proj["box_ratio"],
            "box_ratio_is_measured": proj["box_ratio_is_measured"],
        }

    branches = {n: c["branch"] for n, c in cells.items()}
    round_branch = L.round_branch(branches)
    return {"round_branch": round_branch, "cells": cells,
            "wheel_same": wheel_same, "contrasts": contrasts,
            "noise_signature": noise,
            "provenance": {r: {k: v for k, v in p.items()
                               if k in ("dir", "is_per_box", "pinned_src_rev",
                                        "blind_commit")}
                           for r, p in prov.items()},
            "cross_box_rev_ok": cross_box_rev_ok,
            "code_revs": revs,
            "pinned_src_rev": {r: p["pinned_src_rev"] for r, p in prov.items()},
            "blind_commit": {r: p["blind_commit"] for r, p in prov.items()}}


def _smoke_spec_for(cell_dir: Path):
    """⭐ EACH BOX SMOKES ITS OWN CELL'S CONFIG (§9), so `--smoke-mode` has to work
    out WHICH. The archive's own `--out-subdir` names it (`smoke_<out_subdir>`),
    which is what the launcher builds; the laptop's C_MID is the default when the
    directory name says nothing."""
    stem = cell_dir.name
    for role, sm in L.SMOKE_BY_BOX.items():
        c = L.cell_by_name(sm["cell"])
        if stem.endswith(c.out_subdir):
            return c, role
    return L.cell_by_name(L.SMOKE_CELL), "laptop"


def smoke_mode(cell_dir: Path) -> int:
    spec, smoke_role = _smoke_spec_for(cell_dir)
    cell = Cell(spec, cell_dir)
    pinned = _read_text(HERE / "PINNED_SRC_REV")
    blind = _read_text(HERE / "BLIND_COMMIT")
    probe = _read_json(HERE / L.WHEEL_PROBE_FILENAME)
    repo = _repo_root()
    build, _ = cell.resolve("carc_rs_build", "config.backend.carc_rs_build")
    wanc = wheel_ancestry_facts(repo, None if build is MISSING else build)
    bproof = blind_facts(repo, blind, _read_json(HERE / "BLIND_PROOF.json"),
                         HERE / "DESIGN.md", HERE / "READ_RULE.md")
    # ⚠️ smoke=True on the SRC_CLEAN reading: a smoke has ONE cell and no seal.
    # It must still record a pre-flight and an after-boundary and be CLEAN at
    # both — G-REV is NOT in §3.5's allowed set and must PASS on the smoke.
    sclean = src_clean_facts(HERE / "SRC_CLEAN.jsonl", [spec.name], smoke=True)
    gates, stats = run_gates(cell, pinned_src_rev=pinned, blind_commit=blind,  # noqa: E501
                             wheel_probe=probe, smoke=True, wheel_ancestry=wanc,
                             blind_proof=bproof, src_clean=sclean)

    failed = set(gates.failed())
    allowed = set(L.SMOKE_ALLOWED_FAILURES)
    excusable = {g for g in failed if g in allowed}
    if "RECON" in failed and gates.results["RECON"].get("smoke_subcheck") == "RECON/n_paired":
        excusable.add("RECON")
    blockers = sorted(failed - excusable)

    print("=" * 79)
    print(f"SMOKE-MODE ADJUDICATION — {cell_dir}")
    print(f"  smoke cell config: {spec.name} "
          f"({spec.shape} {spec.rung}: {spec.knob}={spec.weight}) vs "
          f"{spec.opponent.upper()}")
    print(f"  box: {smoke_role} — {L.BOXES[smoke_role]['label']}")
    print(f"  ⭐ ONE SMOKE PER BOX (§9): {L.SMOKE_BY_BOX[smoke_role]['why']}")
    print("=" * 79)
    for gid in L.GATE_IDS:
        r = gates.results.get(gid)
        if not r:
            continue
        mark = "PASS" if r["ok"] else ("ALLOWED-FAIL" if gid in excusable else "BLOCKER")
        print(f"  {gid:<14s} {mark:<13s} @{r['address']}")
        if not r["ok"]:
            print(f"                 ↳ {r['note']}")
    print("")
    print("PINNED ALLOWED SET (READ_RULE §3.5) — why each cannot pass on 16 games:")
    for k, why in L.SMOKE_ALLOWED_REASONS.items():
        print(f"  {k}: {why}")
    print("")
    print("⛔ G-WHEEL-SAME IS **NOT** IN THE ALLOWED SET — a TIGHTENING over round 1,")
    print("   which had no such gate. The smoke runs on the same wheel the cells will,")
    print("   so it MUST pass there, and it is the check that carries round 1's IDENT")
    print("   PASS forward in place of an identity cell.")
    print("")
    if blockers:
        print(f"⛔ LAUNCH BLOCKER — gates failed OUTSIDE the pinned allowed set: {blockers}")
        print("   A gate that cannot read what the harness EMITS must be found before 5600")
        print("   games are spent, not after. Fix the gate (or the launcher), re-smoke.")
        return 1
    print("✅ SMOKE ADJUDICATION PASS — every failure is confined to the pinned allowed set.")
    return 0


def selftest() -> int:
    """READ_RULE §3.1 questions 1/2/4, executed against a REAL EMITTED archive."""
    fixture = HERE / "selftest_fixture"
    spec = L.FIXTURE_SPEC
    print("=" * 79)
    print("ANALYZE_SCREEN --SELFTEST  (round-2 bracket)")
    print("=" * 79)

    problems = L.sanity_check()
    print(f"[1] screen_lib.sanity_check(): {len(problems)} problem(s)")
    for p in problems:
        print(f"    !!! {p}")
    if problems:
        return 1

    if not fixture.is_dir() or not (fixture / "manifest.json").is_file():
        print(f"!!! REFUSING TO RUN: no REAL manifest at {fixture}.")
        print("!!! READ_RULE §7: the selftest seeds its fixture from a manifest the")
        print("!!! HARNESS EMITTED and refuses a synthesized-only fixture. A gate")
        print("!!! validated against a manifest the DESIGN described rather than one the")
        print("!!! harness WROTE is exactly the defect this rule exists to prevent.")
        return 1
    man = _read_json(fixture / "manifest.json") or {}
    if not man.get("config") or not man.get("code_rev"):
        print("!!! REFUSING TO RUN: the fixture does not look like an emitted manifest.")
        return 1
    print(f"[2] fixture is a REAL emitted archive: {fixture}")
    print(f"    code_rev={man.get('code_rev')} carc_rs_build={man.get('carc_rs_build')} "
          f"records={len(list(fixture.glob('seed*_a*.json')))}")
    print(f"    described by screen_lib.FIXTURE_SPEC ({spec.shape} {spec.rung}, "
          f"{spec.knob}={spec.weight}, opponent={spec.opponent}) — ⛔ NOT a round-2 cell")

    # Question 1 — READABLE: every gate resolves an address (or a legitimate ABSENT)
    cell = Cell(spec, fixture)
    gates, stats = run_gates(cell, pinned_src_rev=None, blind_commit=None,
                             wheel_probe=None, smoke=False)
    missing_ids = [g for g in L.GATE_IDS if g not in gates.results]
    print(f"[3] all {len(L.GATE_IDS)} gate ids evaluated: "
          f"{'YES' if not missing_ids else missing_ids}")
    if missing_ids:
        return 1
    unresolved = [r["id"] for r in gates.results.values() if r["address"] == "ABSENT"]
    print(f"[4] gates whose address did NOT resolve on a real manifest: {unresolved or 'none'}")

    # Question 2 — SATISFIABLE: on this real archive the structural gates PASS.
    # ⚠️ NOT a PASS verdict: the fixture is a 16-game throwaway on a round-1 dev
    # range, so the band/deck/N/SAT family fails BY CONSTRUCTION, and the launch
    # artifacts (PINNED_SRC_REV / BLIND_COMMIT / WHEEL_PROBE.json) do not exist
    # in a frozen, never-launched pair.
    structural = ("G-SINGLEVAR", "G-LEAF", "G-INVASION", "G-CAPFWD", "G-WHEEL-SAME",
                  "G-HOST", "G-RULES", "G-BACKEND", "G-BUDGET", "G-TIEARB",
                  "G-EXACT", "RECON")
    bad = [g for g in structural if not gates.results[g]["ok"]]
    print(f"[5] structural gates PASS on the real emitted archive: "
          f"{'YES' if not bad else 'NO -> ' + str(bad)}")
    for g in bad:
        print(f"    !!! {g}: {gates.results[g]['note']}")
        print(f"        observed: {gates.results[g]['observed']}")
    print("    ⭐ G-WHEEL-SAME PASSES here, and that is not an accident: the fixture IS")
    print("       round 1's own emitted archive, so its wheel fingerprint is round 1's")
    print("       by construction — which proves the gate is READABLE and SATISFIABLE")
    print("       on output the harness actually wrote.")
    expected_env_fail = {"G-BAND", "G-DECKS", "G-N", "G-SAT", "G-WHEEL", "G-REV",
                         "G-BLIND"}
    got_env_fail = {g for g in gates.results if not gates.results[g]["ok"]}
    print(f"[6] gates failing for ENVIRONMENTAL reasons (throwaway range / no launch "
          f"artifacts): {sorted(got_env_fail & expected_env_fail)}")

    # Question 4 — ABSENT is FAIL, for every gate.
    empty = Cell(spec, HERE / "__nonexistent__")
    eg, _ = run_gates(empty, pinned_src_rev=None, blind_commit=None, wheel_probe=None)
    survivors = [r["id"] for r in eg.results.values() if r["ok"]]
    print(f"[7] ABSENT is FAIL — gates that PASS on an EMPTY archive: {survivors or 'none'}")

    ok = (not bad) and (not missing_ids) and not survivors
    print("")
    print("SELFTEST " + ("GREEN" if ok else "RED"))
    if not ok and survivors:
        print("!!! a gate passed with NO data — ABSENT must be FAIL, never a skip.")
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--smoke-mode", action="store_true")
    ap.add_argument("--cell", type=str, default=None)
    ap.add_argument("--run-dir", type=str, default=None)
    ap.add_argument("--json-out", type=str, default=None)
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if a.smoke_mode:
        if not a.cell:
            print("FATAL: --smoke-mode needs --cell <dir>", file=sys.stderr)
            return 2
        return smoke_mode(Path(a.cell))
    if a.run_dir:
        rep = adjudicate(Path(a.run_dir))
        print(render(rep))
        out = Path(a.json_out) if a.json_out else Path(a.run_dir) / "ADJUDICATION.json"
        out.write_text(json.dumps(rep, indent=2, sort_keys=True, default=str))
        print(f"wrote {out}")
        # ⛔ The adjudicator NEVER writes experiments/results.csv — close-out rows
        # are a human act on the six-touch checklist.
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
