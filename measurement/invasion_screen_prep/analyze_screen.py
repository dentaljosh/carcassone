#!/usr/bin/env python3
"""ADJUDICATOR — invasion-risk term family, round-1 screen at 2752.

    analyze_screen.py --selftest
    analyze_screen.py --smoke-mode --cell <dir>
    analyze_screen.py --run-dir <root>

**This file DECIDES NOTHING ON ITS OWN.** Every bar, constant, branch table and
cost figure lives in `screen_lib.py`, which the launcher's precondition ladder
imports too — so the launcher's in-flight `IDENT` pre-check and this file's
`G-IDENT` cannot drift apart. What lives HERE is only: how to find a value in an
emitted manifest, and how to render the readout `READ_RULE.md` §4.3 mandates.

The pair is law. `DESIGN.md` + `READ_RULE.md` are the spec; if this file
disagrees with them it is THIS FILE that is wrong.

═══════════════════════════════════════════════════════════════════════════════
WHY EACH DESIGN CHOICE IN HERE IS THE WAY IT IS
═══════════════════════════════════════════════════════════════════════════════

**Two documents per cell, resolved together.** `config.*` lives in
`manifest.json`; the STATISTICS (`paired_mean_margin`, `paired_z`, `n_paired`,
`winrate`, `elo`, `n`, `n_failed`) live in `summary.json`, which carries no
`config` block at all. Verified at freeze against a real emitted archive. Every
gate therefore resolves across BOTH, and prints WHICH document and WHICH address
answered (the house `G-BAND`/`G-J1` precedent). A value found at NO address is
`ABSENT`, and **`ABSENT` is `FAIL`** — never a skip, never a default.

**Records are read NON-RECURSIVELY.** `eval_fair_puct.py` writes successes as
`<cell>/seed%012d_a%d.json` but FAILURES into `<cell>/failed/` with the SAME
filename pattern. A recursive glob would count failures as completions and walk
the adjudicator straight past a broken cell. This is the `-maxdepth 1` rule the
launcher carries, ported.

**`RECON` is a WITNESS, never a branch input.** It recomputes every reported
statistic from the raw records through `screen_lib` and can only VOID a cell,
never move its number. `screen_lib.paired_margin` deliberately accumulates with
`math.fsum` rather than `sum`, because the point of a witness is to be a
DIFFERENT computation.

**`G-IDENT` is round-wide.** A fail makes ALL FOUR cells `U-UNREADABLE`
(`READ_RULE.md` §3.4): a defect that moves a ZERO-weight leaf moves every nonzero
one too, and no A/B/D reading could then be attributed to the term rather than to
the wiring.

**`--smoke-mode` exists to catch gates that cannot read what the harness EMITS.**
It passes iff the ONLY failures are `screen_lib.SMOKE_ALLOWED_FAILURES`. Two real
defects in this pair's own gate text were found exactly this way, at freeze,
against a real manifest — see `READ_RULE.md` §3.3 (the opponent search-knob
aliases live under `config.opponent.champ_cfg.*`, not `config.opponent.*`) and
§3 `G-TIEARB` (a healthy archive emits a TERMINAL `champion.tiearb_enabled`, so
an undifferentiated "no tiearb-named segment" rule would have voided every
healthy cell).

**`--selftest` refuses a synthesized fixture.** It runs against a REAL emitted
archive read off disk. Until the §9 smoke exists, that is `selftest_fixture/` —
a genuine 4-game archive the harness wrote at the cells' exact knobs. It asserts
the SHAPE of the result (which gates could be evaluated at all, which are
structurally satisfiable, that ABSENT is FAIL everywhere) and NOT a PASS verdict:
the fixture is an IDENT-shaped config on a dev seed range, so the band/deck/N
family fails on it by construction.
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

# ⛔ THE BAR LIBRARY IS LOADED **BY PATH**, UNDER A DIRECTORY-QUALIFIED MODULE
# NAME — never as a bare `import screen_lib` off `sys.path`.
#
# ⚠️ ROUNDS 1, 2 AND 3 EACH SHIP A FILE CALLED `screen_lib.py`, and each round's
# adjudicator used to insert its OWN directory on `sys.path` and `import
# screen_lib`. In any process that touches two rounds — the instrument suite is
# exactly that — whichever loaded FIRST won `sys.modules["screen_lib"]`, and the
# second adjudicator then silently adjudicated against the WRONG ROUND'S BARS.
# Found by round 3's suite: the round-2 tests failed only when run alongside
# round 3's, and passed alone.
#
# ⛔ A GATE LIBRARY RESOLVED BY IMPORT ORDER IS NOT A GATE LIBRARY. The name below
# is derived from this file's own directory, so two rounds cannot collide, and the
# module is registered in `sys.modules` BEFORE `exec_module` because `@dataclass`
# resolves its field annotations through `sys.modules[cls.__module__]`.
#
# ⚠️ RETROFITTED 2026-08-29 (import-hygiene chore) from round 3's adjudicator,
# which shipped with this pattern. THIS IS A PURE IMPORT-RESOLUTION CHANGE: the
# same `screen_lib.py`, byte-for-byte, is loaded from the same directory, so NO
# statistic, bar, gate, threshold or verdict of this round moves. It only removes
# the possibility that a co-resident round's `screen_lib` is served instead.
_LIB_NAME = f"screen_lib__{HERE.name}"
if _LIB_NAME in sys.modules:
    L = sys.modules[_LIB_NAME]
else:
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location(_LIB_NAME, HERE / "screen_lib.py")
    L = _ilu.module_from_spec(_spec)
    sys.modules[_LIB_NAME] = L
    _spec.loader.exec_module(L)

MISSING = object()

#: The path whose EXISTENCE at a given rev proves that rev carries the invasion
#: family. `G-WHEEL`'s ancestry conjunct is the only post-hoc check that can
#: catch a stale wheel from the archive alone (DESIGN §7).
INVASION_SOURCE = "rust/carc/carc-core/src/leaf/invasion.rs"

#: `rust_agent.carc_rs_build_id()` emits `carc_rs-<version>+<rev12>+rustc<tc>`.
_BUILD_REV_RE = re.compile(r"^carc_rs-[^+]+\+([0-9a-f]{7,40})\+", re.I)

#: The order in which a gate's addresses are tried. `manifest.json` first for
#: config-shaped addresses; `summary.json` first for statistics. Each gate names
#: its own addresses explicitly, so this is only the DOCUMENT order.
DOCS = ("manifest", "summary")


# ═══════════════════════════════════════════════════════════════════════════ #
# ADDRESS RESOLUTION                                                          #
# ═══════════════════════════════════════════════════════════════════════════ #
def flatten(obj: Any, prefix: str = "") -> dict[str, Any]:
    """`{"a.b.c": value}` over nested mappings. Lists are LEAVES (a manifest's
    `converted_sides` / `v29_meeple_curve` are values, not containers)."""
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

    ⚠️ `G-TIEARB(b)` scans THESE, not leaf names — the freeze-time correction in
    `READ_RULE.md` §3. A healthy archive emits `config.champion.tiearb_enabled`
    (a TERMINAL key containing `tiearb`); scanning terminals would void every
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
# `G-WHEEL`'s ancestry, `G-BLIND`'s ancestry/banner/proof and `G-REV`'s        #
# `SRC_CLEAN.jsonl` reading all need git or a launcher artifact. They are      #
# computed HERE, by the caller, and handed to `run_gates` as VERDICTS — so the #
# gate logic stays a pure function of its inputs and the instrument tests can  #
# drive both limbs without a git repository.                                   #
#                                                                             #
# ⛔ EVERY ONE DEFAULTS TO `None`, AND `None` IS FAIL. A gate that cannot be    #
# computed is ABSENT, and ABSENT is FAIL — never a skip.                       #
# ═══════════════════════════════════════════════════════════════════════════ #
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def wheel_ancestry_facts(repo: Path, build: str | None,
                         branch_tip: str = "HEAD") -> dict:
    """⭐ THE CONJUNCT THAT ACTUALLY CATCHES A STALE WHEEL POST-HOC.

    `WHEEL_PROBE.json` records that a nonzero forward SUCCEEDED at launch time,
    which is the pre-flight half. This is the archive half: the rev embedded in
    the manifest's own `carc_rs_build` must (a) be a rev at which
    `rust/carc/carc-core/src/leaf/invasion.rs` EXISTS — i.e. the wheel was built
    from a tree that carries the family at all — and (b) be an ancestor of the
    branch tip, so it is this lineage's build and not some unrelated rev.

    ⚠️ `carc_rs_version` is permanently "0.1.0" and can never discriminate; the
    embedded rev is the only fingerprint the manifest carries.
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

    ⚠️ `run_cells.sh` writes `BLIND_PROOF.json` at launch; before this conjunct
    existed nothing ever read it back, so a stale or disagreeing proof could sit
    in the directory unnoticed. The live re-check is what makes the artifact
    load-bearing rather than decorative.
    """
    if not blind or not L.is_hex40(blind):
        return {"ok": False, "why": "BLIND_COMMIT is absent or not a 40-hex sha "
                                    "(still the PENDING placeholder?)"}
    live_anc = _git(repo, "merge-base", "--is-ancestor", blind, "HEAD").returncode == 0
    # Did that commit INTRODUCE the FROZEN banner? Look for an ADDED line
    # carrying the banner in either half of the pair.
    show = _git(repo, "show", "--format=", "--unified=0", blind, "--",
                str(design.relative_to(repo)), str(read_rule.relative_to(repo)))
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

    ⚠️ `run_cells.sh` appends to this file at every pass boundary; before this
    conjunct existed nothing read it back either. A mid-round tree move is
    exactly the `track_d2_prep` mixed-rev defect, and this pair is FOUR cells
    long, so the window for one is four times wider.
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
        # A smoke has ONE cell and no seal; it must still record a pre-flight and
        # an after-boundary, and must still be clean at both.
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
    to `None`, and `None` is FAIL — a conjunct that could not be computed is
    ABSENT, never a skip.
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
                  {"band_seed_start": spec.seed_start, "n_decks": n_dk, "seatings_per_deck": sp},
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
    want_keys = set(spec.invasion_keys) if not smoke else set(L.cell_by_name(L.SMOKE_CELL).invasion_keys)
    # TWO-SIDED set equality: an extra differing key FAILS, and an expected-but-
    # identical key FAILS too (a cell whose knob did not reach the leaf).
    leaf_ok = (leaf_diff == want_keys)
    stats["leaf_diff"] = sorted(leaf_diff)
    stats["leaf_diff_empty"] = (len(leaf_diff) == 0)
    sv_ok = (not sv_bad) and leaf_ok
    g.add("G-SINGLEVAR", sv_ok, "manifest:config.champion.* vs config.opponent.* (alias table) "
                                "+ config.cand_leaf_cfg vs config.opp_leaf_cfg",
          {"alias_mismatches": sv_bad, "leaf_diff": sorted(leaf_diff),
           "leaf_diff_expected": sorted(want_keys)},
          "" if sv_ok else "the two sides differ in something other than the cell's frozen "
                           "invasion key set (set equality is TWO-SIDED)")

    # ---- G-LEAF ------------------------------------------------------------
    opp_h, opp_a = cell.resolve("config.opp_leaf_hash", "config.opponent.leaf_hash")
    cand_h, cand_a = cell.resolve("config.cand_leaf_hash")
    curve, curve_a = cell.resolve("config.cand_leaf_cfg.v29_meeple_curve",
                                  "config.champion.leaf_cfg.v29_meeple_curve")
    a_ok = (opp_h == L.PROD_LEAF_HASH)
    b_ok = (isinstance(curve, list) and tuple(curve) == tuple(L.CURVE125))
    want_cand = (L.cell_by_name(L.SMOKE_CELL).cand_leaf_hash if smoke else spec.cand_leaf_hash)
    c_ok = (cand_h == want_cand)
    stats["cand_leaf_hash"] = cand_h
    stats["leaf_hash_is_champion"] = (cand_h == L.PROD_LEAF_HASH)
    leaf_gate_ok = a_ok and b_ok and c_ok
    g.add("G-LEAF", leaf_gate_ok, f"{opp_a} | {cand_a} | {curve_a}",
          {"opp_leaf_hash": opp_h, "cand_leaf_hash": cand_h, "cand_curve_is_curve125": b_ok,
           "cand_leaf_hash_expected": want_cand},
          "" if leaf_gate_ok else
          "(a) opponent hash must be the champion on EVERY cell — it is NOT redundant with the "
          "harness's own check, because --allow-leaf-hash-drift relaxes BOTH sides "
          "(eval_fair_puct.py:3763 candidate, :3777 opponent); (b) the candidate curve must be "
          "curve125; (c) IDENT's candidate hash must EQUAL the champion's and an arm's must NOT")

    # ---- G-INVASION --------------------------------------------------------
    full_leaf, full_a = cell.resolve("config.champion.leaf_cfg")
    full_inv = _invasion_subset(full_leaf)
    want_vals = dict(L.cell_by_name(L.SMOKE_CELL).invasion_values if smoke else spec.invasion_values)
    expected_full = dict(L.INVASION_DEFAULTS)
    expected_full.update(want_vals)
    # `_leaf_dict` DROPS a field at its default, so "absent" IS "default" and both
    # readings must pass — compare only the fields the manifest actually carries.
    inv_ok = all(full_inv.get(k, L.INVASION_DEFAULTS[k]) == v for k, v in expected_full.items())
    cand_inv = _invasion_subset(cand_leaf)
    opp_inv = _invasion_subset(opp_leaf)
    inv_ok = inv_ok and (cand_inv == want_vals) and (opp_inv == {})
    # ⛔ ABSENT IS FAIL. Without this the gate passes VACUOUSLY on an empty
    # archive: "_leaf_dict drops a field at its default" makes every comparison
    # trivially true when there is no leaf dict at all. Caught by --selftest
    # question 4 at freeze; the containers must EXIST before their contents mean
    # anything.
    containers_present = (full_leaf is not MISSING and isinstance(full_leaf, Mapping)
                          and isinstance(cand_leaf, Mapping) and isinstance(opp_leaf, Mapping))
    inv_ok = inv_ok and containers_present
    g.add("G-INVASION", inv_ok, f"{full_a} + config.cand_leaf_cfg + config.opp_leaf_cfg",
          {"champion_leaf_cfg_invasion": full_inv, "cand_leaf_cfg_invasion": cand_inv,
           "opp_leaf_cfg_invasion": opp_inv, "expected": expected_full},
          "" if inv_ok else "a knob is at the wrong value, a second weight is nonzero, or the "
                            "OPPONENT carries an invasion key")

    # ---- G-CAPFWD (DESIGN §2.3) --------------------------------------------
    alpha = float(full_inv.get("invasion_alpha", 0.0) or 0.0)
    cap = float(full_inv.get("invasion_alpha_cap", 0.0) or 0.0)
    stub = int(full_inv.get("invasion_stub_max_tiles", 2) or 2)
    cap_ok = ((cap == 0.0) or (alpha != 0.0)) and ((stub == 2) or (alpha != 0.0))
    # ⛔ ABSENT IS FAIL — same vacuity trap as G-INVASION: a biconditional over
    # three defaulted-to-absent fields is trivially true on an empty archive.
    cap_ok = cap_ok and full_leaf is not MISSING and isinstance(full_leaf, Mapping)
    g.add("G-CAPFWD", cap_ok, full_a,
          {"invasion_alpha": alpha, "invasion_alpha_cap": cap, "invasion_stub_max_tiles": stub},
          "" if cap_ok else "an INERT shape-B knob is set without a nonzero invasion_alpha; "
                            "leaf_config_rs (rust_agent.py:181-185) would DROP it silently and "
                            "the manifest would LIE about the running leaf")

    # ---- G-WHEEL -----------------------------------------------------------
    build, build_a = cell.resolve("carc_rs_build", "config.backend.carc_rs_build")
    bsha, _ = cell.resolve("carc_rs_binary_sha", "config.backend.carc_rs_binary_sha")
    mixed, _ = cell.resolve("mixed_builds", "config.backend.mixed_builds")
    probe_ok, probe_why = L.wheel_probe_ok(wheel_probe)
    # ⭐ THE ANCESTRY CONJUNCT — the archive half of the stale-wheel check.
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
          "" if be_ok else "BOTH sides must be rust-resolved: the invasion family exists ONLY "
                           "in rust, so a python leg raises on a nonzero weight or (worse, on a "
                           "stale-wheel path) serves an invasion-BLIND leaf that reads as a null")

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
          "" if bu_ok else "both sides must be (4, 688, 2752) and the product must multiply out")

    # ---- G-TIEARB (three conjuncts; READ_RULE §3) --------------------------
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
    # trivially true of an archive with no documents at all. The gate therefore
    # additionally requires a manifest to EXIST — a cell with no manifest is
    # unreadable, not disarmed. (--selftest question 4, freeze.)
    ta_ok = a_conj and a2_conj and b_conj and bool(cell.manifest)
    g.add("G-TIEARB", ta_ok, ta_a,
          {"cand_tiearb.enabled": None if ta_en is MISSING else ta_en,
           "armed_tiearb_enabled_leaves": armed_leaves,
           "stray_tiearb_containers": stray},
          "" if ta_ok else "(b) scans CONTAINER segments only — a healthy archive emits a "
                           "TERMINAL config.champion.tiearb_enabled=false, which (a2) checks "
                           "instead (READ_RULE §3, freeze-time correction)")

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
    # ⭐ THE SRC_CLEAN CONJUNCT — the launcher has always WRITTEN SRC_CLEAN.jsonl
    # at every pass boundary; until now nothing READ it back.
    sc = src_clean if isinstance(src_clean, Mapping) else None
    sc_ok = bool(sc and sc.get("ok"))
    sc_why = (sc or {}).get("why", "SRC_CLEAN verdict ABSENT — ABSENT is FAIL")
    _, whole_tree_dirty = L.split_dirty("" if cr is MISSING else str(cr))
    g.add("G-REV", rv_ok and sc_ok, f"{cr_a} + SRC_CLEAN.jsonl",
          {"code_rev": None if cr is MISSING else cr,
           "pinned_src_rev": pinned_src_rev,
           # ⭐ WHOLE-TREE dirt is INFORMATIONAL (the main tree is perpetually
           # dirty with measurement artifacts, which is normal and permanent).
           # The FATAL, code-path-scoped verdict is SRC_CLEAN.jsonl's.
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
    # ⭐ THE ANCESTRY / BANNER / PROOF CONJUNCTS — `run_cells.sh` writes
    # BLIND_PROOF.json at launch; until now nothing read it back, so a stale or
    # disagreeing proof could sit in the directory unnoticed.
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

    # ---- statistics (needed by G-N / G-SAT / G-IDENT / RECON) --------------
    n_scored, _ = cell.resolve("n")
    n_failed, nf_a = cell.resolve("n_failed")
    wr, wr_a = cell.resolve("winrate")
    # Normalise the MISSING sentinel out before any arithmetic. ⚠️ None here still
    # means ABSENT and still FAILS below — this only stops the sentinel object
    # reaching int()/float().
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
              "" if n_ok else f"a failure rate < {L.FAILURE_RATE_VOID:.0%} is REPORTED, never "
                              "silently absorbed; at or above it the cell voids")

    # ---- G-SAT -------------------------------------------------------------
    if smoke:
        g.add("G-SAT", False, wr_a, {"winrate": wr}, L.SMOKE_ALLOWED_REASONS["G-SAT"])
    else:
        lo, hi = L.SAT_WR
        s_ok = (wr is not MISSING and wr is not None and lo <= float(wr) <= hi)
        g.add("G-SAT", s_ok, wr_a, {"winrate": wr, "band": [lo, hi]},
              "" if s_ok else "a RAIL check, not a strength bar: both arms are the same champion "
                              "differing by one leaf term, so a winrate outside this window means "
                              "the two sides are not the agents this design says they are")

    # ---- RECON (witness; can only VOID, never move a number) ---------------
    recon_bad = []
    for s in L.RECON_STATS:
        a, b = rep.get(s), witness.get(s)
        if not L.recon_close(a, b):
            recon_bad.append(f"{s}: reported {a!r} vs witness {b!r}")
    if smoke:
        # only the n_paired half is excusable on a throwaway archive
        hard = [x for x in recon_bad if not x.startswith("n_paired")]
        g.add("RECON", not hard, "summary.json vs raw records",
              {"mismatches": recon_bad},
              L.SMOKE_ALLOWED_REASONS["RECON/n_paired"] if recon_bad else "")
        if recon_bad and not hard:
            g.results["RECON"]["smoke_subcheck"] = "RECON/n_paired"
    else:
        g.add("RECON", not recon_bad, "summary.json vs raw records",
              {"mismatches": recon_bad},
              "" if not recon_bad else "the WITNESS disagrees beyond rel 1e-6 / abs 1e-9 — it can "
                                       "only VOID, never move, the number")

    # ---- G-IDENT (round-wide; filled by the caller for arm cells) ----------
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
    P("INVASION-RISK TERM FAMILY — ROUND-1 SCREEN AT 2752 — ADJUDICATION")
    P("=" * 79)
    P(f"ROUND BRANCH: {report['round_branch']}")
    P("")

    # 1 + 2 + 3 — per cell
    P("--- §4.3(1) PER CELL " + "-" * 57)
    for name in L.CELL_NAMES:
        c = report["cells"].get(name)
        if not c:
            P(f"  {name}: ABSENT from the run directory — U-UNREADABLE")
            continue
        s = c["stats"]
        ci = c.get("ci") or (None, None)
        P(f"  {name:6s} branch={c['branch']:<12s} n_common={s.get('n_common')} "
          f"n_failed={s.get('n_failed')}")
        P(f"         D={_f(s.get('D'))} SE={_f(s.get('se'))} z={_f(s.get('z'))}  "
          f"95% CI [{_f(ci[0])}, {_f(ci[1])}]")
        P(f"         winrate={_f(s.get('winrate'), 4)} W/D/L={s.get('WDL')} "
          f"elo={_f(s.get('elo'), 2)}")
        an = c["se_anomaly"]
        P(f"         §4.3(2) SE realized {_f(an['realized'])} vs modelled "
          f"{_f(an['modelled'])} ratio={_f(an['ratio'])} "
          f"{'⚠️ FLAGGED' if an['flagged'] else 'ok'}  ({an['note']})")
        ed = c["elo_display"]
        P(f"         §4.3(3) elo limb={ed['limb']} — {ed['label']}")
        if ed["limb"] == "own-ratio":
            P(f"                 elo/pt={_f(ed['elo_per_point'], 2)} "
              f"bracket={ed['elo_per_point_bracket']} {ed['anomaly_note']}")
        else:
            P(f"                 2σ bound ±{_f(ed['two_sigma_pts'])} pts ≈ "
              f"±{_f(ed['two_sigma_elo_lo'], 1)}..±{_f(ed['two_sigma_elo_hi'], 1)} elo "
              f"(BRACKET CONVERSION, not a measured scale)")
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
                P(f"    {gid:<12s} ---- not evaluated")
                continue
            mark = "PASS" if r["ok"] else "FAIL"
            P(f"    {gid:<12s} {mark}  @{r['address']}")
            if not r["ok"] and r.get("note"):
                P(f"                 ↳ {r['note']}")
    P("")

    # 4 — power table
    P("--- §4.3(4) POWER (computed BEFORE any answer existed) " + "-" * 23)
    P("  ⛔ A NULL IS A BOUND, NOT A ZERO.")
    for row in L.POWER_TABLE:
        P(f"    Δ={row['true_effect_pts']:+.2f} pts/deck  z={row['z_at_se_0p7335']:.2f}  "
          f"power {row['power']}  {row['note']}")
    P("")

    # 6 — the cost multiplier
    P("--- §4.3(6) INVASION-ARITHMETIC COST MULTIPLIER " + "-" * 30)
    P("  ⛔ DESCRIPTIVE-ONLY — TENANCY-SENSITIVE, NOT A GATE (DESIGN §6.3).")
    for name in L.CELL_NAMES:
        c = report["cells"].get(name)
        if not c:
            continue
        m = c["cost"]
        tag = " (≈1.0 CONTROL)" if name == "IDENT" else ""
        P(f"    {name:6s} candidate {_f(m['cand_ms'], 1)} ms/move  opponent "
          f"{_f(m['opp_ms'], 1)} ms/move  multiplier {_f(m['multiplier'], 3)}{tag}")
    P("")

    # 7 — frozen inputs
    P("--- §4.3(7) THE FROZEN INPUTS, RESTATED " + "-" * 38)
    d = L.FROZEN_DERIVATION
    P(f"  G (champion sibling-move value gap) = {d['G_sibling_p90_minus_p10']} leaf pts")
    P(f"  target = {d['target_fraction_of_G']:.2f} × G = {d['target_contribution_pts']} pts")
    P(f"  M_A={d['M_A']} M_B={d['M_B']} M_D={d['M_D']} (M_C={d['M_C']}, round 2)")
    P(f"  ⇒ beta {L.cell_by_name('A_MID').invasion_values['invasion_beta']} · "
      f"alpha {L.cell_by_name('B_MID').invasion_values['invasion_alpha']} @ cap "
      f"{d['alpha_cap']} · delta_farm "
      f"{L.cell_by_name('D_MID').invasion_values['invasion_delta_farm']}  (all 40.9% of G)")
    P(f"  corroboration: {d['corroboration']}")
    P(f"  band {L.BAND}:")
    for c in L.CELLS:
        P(f"    {c.name:6s} {c.seed_start}..{c.seed_end}  {c.n_decks} decks / {c.n_games} games")
    P("")

    # 8 — round-2 bracket
    P("--- §4.3(8) THE ROUND-2 BRACKET — NAMED, *NOT RUN* " + "-" * 27)
    for k, v in L.ROUND2_BRACKET.items():
        P(f"    {k}: {v['knob']}  low {v['low']} / mid {v['mid']} / high {v['high']}  "
          f"{v.get('note', '')}")
    P("")

    # joint A/D basis, mandatory on any A or D branch
    branches = {n: c["branch"] for n, c in report["cells"].items()}
    if branches.get("A_MID") in ("PROMOTE", "BRACKET", "REVERSED") or \
       branches.get("D_MID") in ("PROMOTE", "BRACKET", "REVERSED"):
        P("--- §4.2 THE JOINT A/D READING BASIS (MANDATORY HERE) " + "-" * 24)
        for k, v in L.AD_JOINT_BASIS.items():
            if k == "readings":
                continue
            P(f"    {k}: (beta, beta+delta_farm) = ({v['beta']:.2f}, "
              f"{v['beta_plus_delta_farm']:.2f}) — {v['reads_as']}")
        a_fired = branches.get("A_MID") in ("PROMOTE", "BRACKET")
        d_fired = branches.get("D_MID") in ("PROMOTE", "BRACKET")
        key = ("A", "D") if (a_fired and d_fired) else \
              ("A", "not D") if a_fired else ("D", "not A") if d_fired else ("neither",)
        P(f"    READING: {L.AD_JOINT_BASIS['readings'][key]}")
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


def adjudicate(run_dir: Path) -> dict:
    pinned = _read_text(HERE / "PINNED_SRC_REV")
    blind = _read_text(HERE / "BLIND_COMMIT")
    probe = _read_json(HERE / L.WHEEL_PROBE_FILENAME)
    repo = _repo_root()
    bproof = blind_facts(repo, blind, _read_json(HERE / "BLIND_PROOF.json"),
                         HERE / "DESIGN.md", HERE / "READ_RULE.md")
    sclean = src_clean_facts(HERE / "SRC_CLEAN.jsonl", [c.name for c in L.CELLS])

    cells: dict[str, dict] = {}
    for spec in L.CELLS:
        path = run_dir / spec.out_subdir
        if not path.is_dir():
            continue
        cell = Cell(spec, path)
        build, _ = cell.resolve("carc_rs_build", "config.backend.carc_rs_build")
        wanc = wheel_ancestry_facts(repo, None if build is MISSING else build)
        gates, stats = run_gates(cell, pinned_src_rev=pinned, blind_commit=blind,
                                 wheel_probe=probe, wheel_ancestry=wanc,
                                 blind_proof=bproof, src_clean=sclean)
        cells[spec.name] = {"gates": gates.results, "stats": stats, "_gates_obj": gates}

    # ---- G-IDENT: computed once, applied ROUND-WIDE (READ_RULE §3.4) -------
    ic = cells.get(L.IDENT_CELL.name)
    if ic is None:
        ident = L.ident_gate(None, None, 0, leaf_hash_ok=False, n_failed=None,
                             leaf_diff_empty=False)
        ident["reading"] = "FAIL — the IDENT cell is ABSENT from the run directory."
    else:
        s = ic["stats"]
        ident = L.ident_gate(s.get("D"), s.get("z"), s.get("n_common"),
                             leaf_hash_ok=bool(s.get("leaf_hash_is_champion")),
                             n_failed=s.get("n_failed"),
                             leaf_diff_empty=bool(s.get("leaf_diff_empty")))
    for name, c in cells.items():
        c["gates"]["G-IDENT"] = {"id": "G-IDENT", "ok": ident["ok"],
                                 "address": "IDENT cell summary + G-LEAF(c) + G-SINGLEVAR(b)",
                                 "observed": {k: ident[k] for k in
                                              ("mean", "z", "n_paired", "bar", "conjuncts")},
                                 "note": "" if ident["ok"] else
                                 ident["reading"] + " " + ident["consequence"]}

    # ---- branches ----------------------------------------------------------
    for name, c in cells.items():
        gates_ok = all(r["ok"] for r in c["gates"].values())
        s = c["stats"]
        spec = L.cell_by_name(name)
        if spec.role == "precondition":
            c["branch"] = "PRECONDITION-PASS" if gates_ok else "U-UNREADABLE"
        else:
            c["branch"] = L.branch_for_cell(s.get("z"), gates_ok)
        se = s.get("se")
        D = s.get("D")
        c["ci"] = ((D - 1.96 * se, D + 1.96 * se)
                   if (se is not None and D is not None) else (None, None))
        c["se_anomaly"] = L.se_anomaly(se, spec.n_decks)
        c["elo_display"] = L.elo_display(s.get("z"), D, s.get("elo"), se)
        c.pop("_gates_obj", None)

    # cost multiplier, read off each cell's summary
    for name, c in cells.items():
        path = run_dir / L.cell_by_name(name).out_subdir
        summ = _read_json(path / "summary.json") or {}
        cand_ms = summ.get("champ_prefix_ms_per_move")
        opp_ms = summ.get("rung_ms_per_move")
        c["cost"] = {"cand_ms": cand_ms, "opp_ms": opp_ms,
                     "multiplier": (cand_ms / opp_ms) if (cand_ms and opp_ms) else None}

    branches = {n: c["branch"] for n, c in cells.items()}
    # IDENT is a PRECONDITION, not a fifth result — map it for round_branch()
    rb_input = {n: ("U-UNREADABLE" if b == "U-UNREADABLE" else b) for n, b in branches.items()}
    rb_input[L.IDENT_CELL.name] = ("U-UNREADABLE"
                                   if branches.get(L.IDENT_CELL.name) == "U-UNREADABLE"
                                   else "NULL")
    round_branch = L.round_branch(rb_input)
    if round_branch == "SCREEN-NULL-family-parks":
        # §4: the kill also requires every arm STRICTLY below +1σ and no REVERSED
        pass
    return {"round_branch": round_branch, "cells": cells, "ident_gate": ident,
            "pinned_src_rev": pinned, "blind_commit": blind}


def smoke_mode(cell_dir: Path) -> int:
    spec = L.cell_by_name(L.SMOKE_CELL)
    cell = Cell(spec, cell_dir)
    pinned = _read_text(HERE / "PINNED_SRC_REV")
    blind = _read_text(HERE / "BLIND_COMMIT")
    probe = _read_json(HERE / L.WHEEL_PROBE_FILENAME)
    repo = _repo_root()
    build, _ = cell.resolve("carc_rs_build", "config.backend.carc_rs_build")
    wanc = wheel_ancestry_facts(repo, None if build is MISSING else build)
    bproof = blind_facts(repo, blind, _read_json(HERE / "BLIND_PROOF.json"),
                         HERE / "DESIGN.md", HERE / "READ_RULE.md")
    # ⚠️ smoke=True on the SRC_CLEAN reading: a smoke has ONE cell and no seal, so
    # it cannot carry a per-cell after-boundary for all four. It must still record
    # a pre-flight and an after-boundary and be CLEAN at both — G-REV is NOT in
    # §3.5's allowed set and must PASS on the smoke.
    sclean = src_clean_facts(HERE / "SRC_CLEAN.jsonl", [spec.name], smoke=True)
    gates, stats = run_gates(cell, pinned_src_rev=pinned, blind_commit=blind,
                             wheel_probe=probe, smoke=True, wheel_ancestry=wanc,
                             blind_proof=bproof, src_clean=sclean)
    gates.add("G-IDENT", False, "smoke", None, L.SMOKE_ALLOWED_REASONS["G-IDENT"])

    failed = set(gates.failed())
    # RECON is decomposed: only the n_paired sub-check is excusable
    allowed = set(L.SMOKE_ALLOWED_FAILURES)
    excusable = {g for g in failed if g in allowed}
    if "RECON" in failed and gates.results["RECON"].get("smoke_subcheck") == "RECON/n_paired":
        excusable.add("RECON")
    blockers = sorted(failed - excusable)

    print("=" * 79)
    print(f"SMOKE-MODE ADJUDICATION — {cell_dir}")
    print("=" * 79)
    for gid in L.GATE_IDS:
        r = gates.results.get(gid)
        if not r:
            continue
        mark = "PASS" if r["ok"] else ("ALLOWED-FAIL" if gid in excusable else "BLOCKER")
        print(f"  {gid:<12s} {mark:<13s} @{r['address']}")
        if not r["ok"]:
            print(f"               ↳ {r['note']}")
    print("")
    print("PINNED ALLOWED SET (READ_RULE §3.5) — why each cannot pass on 16 games:")
    for k, why in L.SMOKE_ALLOWED_REASONS.items():
        print(f"  {k}: {why}")
    print("")
    if blockers:
        print(f"⛔ LAUNCH BLOCKER — gates failed OUTSIDE the pinned allowed set: {blockers}")
        print("   A gate that cannot read what the harness EMITS must be found before 2800")
        print("   games are spent, not after. Fix the gate (or the launcher), re-smoke.")
        return 1
    print("✅ SMOKE ADJUDICATION PASS — every failure is confined to the pinned allowed set.")
    return 0


def selftest() -> int:
    """READ_RULE §3.1 questions 1/2/4, executed against a REAL EMITTED archive."""
    fixture = HERE / "selftest_fixture"
    print("=" * 79)
    print("ANALYZE_SCREEN --SELFTEST")
    print("=" * 79)

    problems = L.sanity_check()
    print(f"[1] screen_lib.sanity_check(): {len(problems)} problem(s)")
    for p in problems:
        print(f"    !!! {p}")
    if problems:
        return 1

    if not fixture.is_dir() or not (fixture / "manifest.json").is_file():
        print(f"!!! REFUSING TO RUN: no REAL manifest at {fixture}.")
        print("!!! READ_RULE §7: the selftest seeds its fixture from a manifest the HARNESS")
        print("!!! EMITTED and refuses a synthesized-only fixture. A gate validated against a")
        print("!!! manifest the DESIGN described rather than one the harness WROTE is exactly")
        print("!!! the defect this rule exists to prevent.")
        return 1
    man = _read_json(fixture / "manifest.json") or {}
    if not man.get("config") or not man.get("code_rev"):
        print("!!! REFUSING TO RUN: the fixture does not look like an emitted manifest.")
        return 1
    print(f"[2] fixture is a REAL emitted archive: {fixture}")
    print(f"    code_rev={man.get('code_rev')} carc_rs_build={man.get('carc_rs_build')} "
          f"records={len(list(fixture.glob('seed*_a*.json')))}")

    # Question 1 — READABLE: every gate resolves an address (or a legitimate ABSENT)
    cell = Cell(L.cell_by_name(L.IDENT_CELL.name), fixture)
    gates, stats = run_gates(cell, pinned_src_rev=None, blind_commit=None,
                             wheel_probe=None, smoke=False)
    missing_ids = [g for g in L.GATE_IDS if g not in gates.results and g != "G-IDENT"]
    print(f"[3] all 18 gate ids evaluated (minus round-wide G-IDENT): "
          f"{'YES' if not missing_ids else missing_ids}")
    if missing_ids:
        return 1
    unresolved = [r["id"] for r in gates.results.values() if r["address"] == "ABSENT"]
    print(f"[4] gates whose address did NOT resolve on a real manifest: {unresolved or 'none'}")

    # Question 2 — SATISFIABLE: on this real archive the structural gates PASS.
    # ⚠️ NOT a PASS verdict: the fixture is an IDENT-shaped config on a DEV seed
    # range, so the band/deck/N family fails BY CONSTRUCTION.
    structural = ("G-SINGLEVAR", "G-LEAF", "G-INVASION", "G-CAPFWD", "G-RULES",
                  "G-BACKEND", "G-BUDGET", "G-TIEARB", "G-EXACT", "RECON")
    bad = [g for g in structural if not gates.results[g]["ok"]]
    print(f"[5] structural gates PASS on the real emitted archive: "
          f"{'YES' if not bad else 'NO -> ' + str(bad)}")
    for g in bad:
        print(f"    !!! {g}: {gates.results[g]['note']}")
        print(f"        observed: {gates.results[g]['observed']}")
    expected_env_fail = {"G-BAND", "G-DECKS", "G-N", "G-SAT", "G-WHEEL", "G-REV", "G-BLIND"}
    got_env_fail = {g for g in gates.results if not gates.results[g]["ok"]}
    print(f"[6] gates failing for ENVIRONMENTAL reasons (dev band / no launch artifacts): "
          f"{sorted(got_env_fail & expected_env_fail)}")

    # Question 4 — ABSENT is FAIL, for every gate.
    empty = Cell(L.cell_by_name(L.IDENT_CELL.name), HERE / "__nonexistent__")
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
