#!/usr/bin/env python3
"""`adjudicate_budget44k` — THE 44032 BUDGET-RUNG ROUND's ADJUDICATOR.

⛔ **THE PAIR IS LAW.** [`PREREG.md`](PREREG.md). If this file disagrees with
it, **this file is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 real games exist at
freeze.**

The order of business:

  1. Load a cell as a POOL OF CHUNKS. This round is chunk/resume-friendly by
     construction (`PREREG.md` §6.2, the `fpu_h2h_r2_prep` flexible-round
     precedent): each cell is played as N independent, disjoint deck blocks,
     each with its own out-dir, its own `manifest.json` and its own
     `summary.json`. There is NO pooled summary on disk, so every pooled
     statistic here is recomputed from the RAW `seed*_a*.json` records and
     RECONCILED chunk-by-chunk against each chunk's own summary.
  2. Every gate in `PREREG.md` §5. `ABSENT` is `FAIL`, never a skip and never
     a default. Config-shaped gates run PER CHUNK and must pass on EVERY
     chunk; a cell is only as clean as its dirtiest chunk.
  3. The branch ladder (`PREREG.md` §4.2), on the cell's OWN REALIZED SE.
  4. The SECONDARY width contrast (`PREREG.md` §4.5) across the two cells'
     common decks — REPORTED, never licensing.
  5. `--smoke-mode`: adjudicate a throwaway `SMOKE_*` archive against the
     magnitude-free required gates only and exit NONZERO on an empty read.
     The `fpu_resurrection_prep` R1 defect (an unreachable `|| DIE` because
     `--smoke-mode` silently adjudicated zero cells) is guarded explicitly
     rather than assumed inherited.
  6. `--selftest`: the library's own arithmetic, the branch grid, the shipped
     REAL-EMITTER fixtures, and the named DEFECT variants.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import screen_lib as L  # noqa: E402


# =========================================================================== #
# LOADING — A CELL IS A POOL OF CHUNKS                                        #
# =========================================================================== #

CHUNK_RE = re.compile(r"__c(\d+)$")


def load_chunk(root: Path) -> dict:
    """Read ONE chunk dir. Missing documents are recorded as `None` and reach
    the gates as ABSENT — this never raises past a gate."""
    man, summ = root / "manifest.json", root / "summary.json"
    recs = []
    for p in sorted(root.glob("seed*_a*.json")):
        try:
            recs.append(json.loads(p.read_text()))
        except Exception:                                        # noqa: BLE001
            recs.append({"_unreadable": str(p)})
    return {"name": root.name, "root": str(root),
            "manifest": json.loads(man.read_text()) if man.is_file() else None,
            "summary": json.loads(summ.read_text()) if summ.is_file() else None,
            "records": recs,
            "done": (root / "DONE").is_file()}


def load_cell(out_root: Path, cell_name: str) -> dict:
    """Pool every `<out_root>/<cell_name>__c<N>` chunk, in chunk-index order.

    ⚠️ A DIRECTORY THAT EXISTS BUT IS EMPTY IS STILL A CHUNK. It is loaded (as
    all-ABSENT) rather than skipped, so a half-written chunk surfaces at
    `G-CHUNKS`/`G-N` as a defect instead of silently shrinking the pool."""
    chunks = []
    if out_root.is_dir():
        for d in sorted(out_root.iterdir()):
            if not d.is_dir():
                continue
            if not d.name.startswith(cell_name + "__c"):
                continue
            chunks.append(load_chunk(d))
    chunks.sort(key=lambda c: int(CHUNK_RE.search(c["name"]).group(1))
                if CHUNK_RE.search(c["name"]) else 10**9)
    records = [r for c in chunks for r in c["records"]]
    return {"cell": cell_name, "out_root": str(out_root), "chunks": chunks,
            "records": records}


def load_single_dir_as_cell(root: Path, cell_name: str) -> dict:
    """A ONE-CHUNK cell from an explicit directory — the `--smoke-mode` shape,
    and the shape the shipped fixtures take."""
    return {"cell": cell_name, "out_root": str(root.parent),
            "chunks": [load_chunk(root)], "records": load_chunk(root)["records"]}


def _docs(chunk: dict) -> dict:
    return {"manifest": chunk.get("manifest") or {},
            "summary": chunk.get("summary") or {}}


def read_claimed_band() -> int | None:
    """The band the ORCHESTRATOR claimed, parsed from the sibling
    `BAND_CLAIMED` file (no extension — the placeholder is `.placeholder`).
    `None` if that file does not exist yet (pre-launch state, or `--smoke`)."""
    p = HERE / "BAND_CLAIMED"
    if not p.is_file():
        return None
    m = re.search(r"BAND CLAIMED:\s*(\d+)", p.read_text())
    return int(m.group(1)) if m else None


# =========================================================================== #
# PER-CHUNK GATES — PREREG.md §5.1                                            #
# =========================================================================== #

def _simple(gid, chunk, checks, address_note) -> dict:
    d = _docs(chunk)
    rows, bad = {}, []
    for alias, want, label in checks:
        v, a = L.resolve(d, *alias)
        rows[label] = {"value": None if v is L.MISSING else v, "address": a}
        if v is L.MISSING:
            bad.append(f"{label} ABSENT")
        elif callable(want):
            if not want(v):
                bad.append(f"{label} = {v!r}")
        elif v != want:
            bad.append(f"{label} = {v!r}, want {want!r}")
    return L.gate(gid, not bad, rows, address_note,
                  "ok" if not bad else f"⛔ {gid} FAILED: " + "; ".join(bad))


def gate_budget(chunk, cell_name) -> dict:
    return L.budget_gate(chunk.get("manifest") or {},
                         chunk.get("summary") or {}, cell_name)


def gate_budget_ratio(chunk, cell_name) -> dict:
    return L.budget_ratio_gate(chunk.get("manifest") or {},
                               chunk.get("summary") or {}, cell_name)


def gate_tiearb_sides(chunk, cell_name=None) -> dict:
    return L.tiearb_sides_gate(chunk.get("manifest") or {})


def gate_tiearb_fired(chunk, cell_name=None) -> dict:
    return L.tiearb_fired_gate(chunk.get("summary") or {})


def gate_exact(chunk, cell_name=None) -> dict:
    return _simple("G-EXACT", chunk, [
        (("manifest:config.endgame.exact_k",), L.EXACT_K, "exact_k"),
        (("manifest:config.endgame.mode",), L.EXACT_MODE, "mode"),
    ], "manifest:config.endgame.*")


def gate_rules(chunk, cell_name=None) -> dict:
    return _simple("G-RULES", chunk, [
        (("manifest:rules_profile.name",), L.RULES_PROFILE, "rules_profile.name"),
        (("manifest:rules_profile.r9_env_ok",), True, "r9_env_ok"),
        (("manifest:rules_profile.r9_env_observed",), True, "r9_env_observed"),
    ], "manifest:rules_profile.* (⚠️ R9 is env-latched at IMPORT)")


def gate_backend(chunk, cell_name=None) -> dict:
    return _simple("G-BACKEND", chunk, [
        (("manifest:config.backend.name",), L.BACKEND, "name"),
        (("manifest:config.backend.requested",), L.BACKEND, "requested"),
        (("manifest:config.backend.mixed_builds", "manifest:mixed_builds"),
         lambda v: v is False, "mixed_builds"),
    ], "manifest:config.backend.*")


def gate_wheel(chunk, cell_name=None) -> dict:
    """`G-WHEEL` — the rust wheel is present and identified. The CROSS-CHUNK
    identity of the wheel is a separate gate (`G-SHARD-IDENT`): a round that
    spans a wheel rebuild is a mixed-era pool, which is precisely the defect
    a chunked round is exposed to and a single-shot round is not."""
    return _simple("G-WHEEL", chunk, [
        (("manifest:carc_rs_build",),
         lambda v: bool(v) and "unavailable" not in str(v), "carc_rs_build"),
        (("manifest:carc_rs_binary_sha",), lambda v: bool(v), "carc_rs_binary_sha"),
        (("manifest:mixed_builds",), lambda v: v is False, "mixed_builds"),
    ], "manifest — carc_rs_version is a constant, not a discriminator")


def gate_leaf(chunk, cell_name=None) -> dict:
    d = _docs(chunk)
    ch, ca = L.resolve(d, "manifest:config.cand_leaf_hash")
    oh, oa = L.resolve(d, "manifest:config.opp_leaf_hash",
                       "manifest:config.opponent.leaf_hash")
    same = (ch is not L.MISSING and ch == oh)
    right = ch == L.LEAF_HASH
    ok = same and right
    return L.gate("G-LEAF", ok,
                  {"cand_leaf_hash": None if ch is L.MISSING else ch,
                   "opp_leaf_hash": None if oh is L.MISSING else oh,
                   "expected": L.LEAF_HASH},
                  ca or oa,
                  ("both sides carry the frozen leaf" if ok else
                   f"⛔ G-LEAF FAILED: cand={ch!r} opp={oh!r} expected {L.LEAF_HASH!r}"))


def gate_host(chunk, cell_name=None) -> dict:
    """`G-HOST` — the round is OWNER-FUNDED FOR THE LOCAL BOX ("fund 44k at
    w30"), so the box is part of the frozen design, not merely provenance. A
    box change is a pre-launch amendment, not a runtime choice."""
    v, a = L.resolve(_docs(chunk), "manifest:host")
    ok, why = L.host_matches_box(None if v is L.MISSING else v, "local")
    return L.gate("G-HOST", ok, {"host": None if v is L.MISSING else v,
                                 "frozen_role": "local", "frozen_W": L.W_LOCAL},
                  a, why)


def gate_recon(chunk, cell_name=None) -> dict:
    """`RECON` — a `math.fsum` witness recomputed from THIS CHUNK's raw records
    against THIS CHUNK's own `summary.json`. Per chunk, deliberately: there is
    no pooled summary on disk, and a chunk whose summary disagrees with its own
    records is unusable regardless of how the pool reads."""
    recs = chunk.get("records") or []
    m, z, n, se, _ = L.paired_margin(recs)
    we = L.winrate_elo(recs)
    d = _docs(chunk)
    rows, bad = {}, []
    for label, mine, aliases in (
        ("paired_mean_margin", m, ("summary:paired_mean_margin",)),
        ("paired_z", z, ("summary:paired_z",)),
        ("n_paired", n, ("summary:n_paired",)),
        ("winrate", we["winrate"], ("summary:winrate",)),
        ("elo", we["elo"], ("summary:elo",)),
    ):
        theirs, a = L.resolve(d, *aliases)
        t = None if theirs is L.MISSING else theirs
        agree = L.recon_close(mine, t)
        rows[label] = {"witness": mine, "summary": t, "agree": agree, "address": a}
        if not agree:
            bad.append(f"{label}: witness {mine!r} vs summary {t!r}")
    return L.gate("RECON", not bad, rows, "summary.json vs the raw records",
                  ("the fsum witness agrees on all five statistics" if not bad
                   else "⛔ RECON DISAGREES — the chunk VOIDS: " + "; ".join(bad)))


def gate_rev(chunk, pinned_src_rev: str | None) -> dict:
    v, a = L.resolve(_docs(chunk), "manifest:code_rev")
    if v is L.MISSING:
        return L.gate("G-REV", False, {"code_rev": None,
                                       "PINNED_SRC_REV": pinned_src_rev},
                      a, "⛔ code_rev ABSENT — ABSENT is FAIL")
    ok, why = L.rev_matches(v, pinned_src_rev)
    return L.gate("G-REV", ok, {"code_rev": v, "PINNED_SRC_REV": pinned_src_rev},
                  a, why)


def gate_blind(chunk) -> dict:
    blind, ba = L.resolve(_docs(chunk), "manifest:BLIND_COMMIT")
    ok = blind is not L.MISSING and L.is_hex40(blind)
    return L.gate("G-BLIND", ok,
                  {"BLIND_COMMIT": None if blind is L.MISSING else blind}, ba,
                  "a single 40-hex BLIND_COMMIT is stamped into the manifest — "
                  "a read that was not blind is not a read" if ok else
                  "⛔ G-BLIND FAILED: BLIND_COMMIT absent or malformed")


#: Per-chunk gates that need only the chunk (+ the cell name).
_CHUNK_GATES = (gate_budget, gate_budget_ratio, gate_tiearb_sides,
                gate_tiearb_fired, gate_exact, gate_rules, gate_backend,
                gate_wheel, gate_leaf, gate_host, gate_recon)

#: The magnitude-free subset a SMOKE archive is legitimately asked to pass.
#: ⛔ A smoke legitimately FAILS gates about the REAL ROUND (`G-BUDGET` — a
#: reduced-budget smoke; `G-BLIND` — unstamped by design; `G-N`/`G-BAND`/
#: `G-DECKS` — the throwaway range and a handful of games), so "all gates ok"
#: is the wrong bar for a smoke. `G-BUDGET-RATIO` is in the list precisely
#: because it states the flag-wiring protection in a magnitude-free form.
SMOKE_REQUIRED_GATES = ("G-BUDGET-RATIO", "G-TIEARB-SIDES", "G-TIEARB-FIRED",
                        "G-EXACT", "G-RULES", "G-BACKEND", "G-LEAF")


# =========================================================================== #
# POOL-LEVEL GATES — PREREG.md §5.2                                           #
# =========================================================================== #

def gate_chunks(cell: dict) -> dict:
    """`G-CHUNKS` — every planned chunk exists, carries BOTH documents, and is
    marked `DONE`. A chunked round's characteristic failure is a silently
    short pool: four chunks planned, three on disk, and every per-chunk gate
    green."""
    spec = L.CELLS[cell["cell"]]
    want = spec["chunks"]
    got = cell["chunks"]
    bad = []
    idx = []
    for c in got:
        m = CHUNK_RE.search(c["name"])
        idx.append(int(m.group(1)) if m else None)
        if c["manifest"] is None:
            bad.append(f"{c['name']}: manifest.json ABSENT")
        if c["summary"] is None:
            bad.append(f"{c['name']}: summary.json ABSENT")
        if not c["done"]:
            bad.append(f"{c['name']}: no DONE marker — the chunk did not "
                       "complete, or completed and was not stamped")
    if len(got) != want:
        bad.append(f"{len(got)} chunk dir(s) on disk, {want} planned")
    expected_idx = list(range(1, want + 1))
    if sorted(i for i in idx if i is not None) != expected_idx:
        bad.append(f"chunk indices {sorted(i for i in idx if i is not None)} "
                   f"!= the planned {expected_idx}")
    return L.gate("G-CHUNKS", not bad,
                  {"planned": want, "found": len(got),
                   "names": [c["name"] for c in got],
                   "done": [c["done"] for c in got]},
                  "the chunk dirs themselves",
                  (f"all {want} chunks present, documented and DONE" if not bad
                   else "⛔ G-CHUNKS FAILED: " + "; ".join(bad)))


def gate_shard_ident(cell: dict) -> dict:
    """`G-SHARD-IDENT` — every chunk resolved THE SAME TWO AGENTS. A chunked
    round can straddle a wheel rebuild, a leaf re-tune, a rules-profile change
    or a re-pin; pooling across any of those silently makes a mixed-era cell.

    ⚠️ This is the chunked-round analogue of the standing "no mid-round
    re-pinning" rule (auto-memory `reference_freeze_latch_hook`'s blind spot:
    "re-pinning is NOT a fix — it makes a cross-cell rev split")."""
    keys = (("manifest:carc_rs_binary_sha", "wheel sha"),
            ("manifest:config.cand_leaf_hash", "cand leaf"),
            ("manifest:config.opp_leaf_hash", "opp leaf"),
            ("manifest:config.champion.total_sims", "cand total_sims"),
            ("manifest:config.champion.k_dets", "cand k_dets"),
            ("manifest:config.opponent.total_sims", "opp total_sims"),
            ("manifest:config.opponent.k_dets", "opp k_dets"),
            ("manifest:rules_profile.name", "rules profile"),
            ("manifest:code_rev", "code_rev"),
            ("manifest:BLIND_COMMIT", "BLIND_COMMIT"))
    rows, bad = {}, []
    for addr, label in keys:
        seen = {}
        for c in cell["chunks"]:
            v, _ = L.resolve(_docs(c), addr)
            seen.setdefault("ABSENT" if v is L.MISSING else json.dumps(
                v, sort_keys=True, default=str), []).append(c["name"])
        rows[label] = {k: v for k, v in seen.items()}
        if len(seen) > 1:
            bad.append(f"{label} DIFFERS across chunks: "
                       + "; ".join(f"{k} in {v}" for k, v in seen.items()))
        elif "ABSENT" in seen:
            bad.append(f"{label} ABSENT on every chunk — ABSENT is FAIL")
    if not cell["chunks"]:
        bad.append("no chunks at all — nothing to check identity across")
    return L.gate("G-SHARD-IDENT", not bad, rows,
                  "every chunk's manifest.json",
                  ("every chunk resolved the same two agents, the same wheel "
                   "and the same pinned rev" if not bad else
                   "⛔ G-SHARD-IDENT FAILED: " + "; ".join(bad)))


def gate_nodup(cell: dict) -> dict:
    """`G-NODUP` — the chunks' realized deck ranges are pairwise DISJOINT and
    every `(deck, seat)` appears EXACTLY ONCE in the pool. A resume that
    re-ran a chunk instead of skipping it would otherwise double-weight those
    decks and silently tighten the SE."""
    seen: dict[tuple[int, int], list[str]] = {}
    per_chunk_ranges = {}
    for c in cell["chunks"]:
        seeds = set()
        for r in c["records"]:
            if not isinstance(r, dict):
                continue
            s, a = r.get("seed"), r.get("a_seat")
            if s is None or a is None:
                continue
            seeds.add(int(s))
            seen.setdefault((int(s), int(a)), []).append(c["name"])
        per_chunk_ranges[c["name"]] = ([min(seeds), max(seeds)] if seeds
                                       else None)
    dups = {f"{k[0]}@seat{k[1]}": v for k, v in seen.items() if len(v) > 1}
    overlaps = []
    names = list(per_chunk_ranges)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = per_chunk_ranges[names[i]], per_chunk_ranges[names[j]]
            if a and b and not (a[1] < b[0] or b[1] < a[0]):
                overlaps.append(f"{names[i]}{a} overlaps {names[j]}{b}")
    bad = []
    if not seen:
        # ⛔ ABSENT is FAIL, never a vacuous pass. A gate cannot certify
        # uniqueness over an empty pool — "no duplicates found" in zero
        # records is not evidence, and the standing convention of this tree
        # is that an empty archive fails EVERY gate.
        bad.append("no (deck,seat) records at all — ABSENT is FAIL; "
                   "uniqueness cannot be certified over an empty pool")
    if dups:
        bad.append(f"{len(dups)} (deck,seat) pair(s) appear in more than one "
                   f"chunk: {list(dups.items())[:5]}")
    if overlaps:
        bad.append("chunk seed ranges overlap: " + "; ".join(overlaps[:5]))
    return L.gate("G-NODUP", not bad,
                  {"chunk_seed_ranges": per_chunk_ranges,
                   "duplicated": dict(list(dups.items())[:20])},
                  "raw seed*_a*.json across the chunk pool",
                  ("chunk ranges disjoint, every (deck,seat) exactly once"
                   if not bad else "⛔ G-NODUP FAILED: " + "; ".join(bad)))


def gate_n(cell: dict) -> dict:
    """`G-N` — the POOLED game count matches the frozen plan, the pooled
    failure rate is under the void threshold, and `n_common` clears the floor."""
    spec = L.CELLS[cell["cell"]]
    want_games = spec["n_games"]
    recs = [r for r in cell["records"] if isinstance(r, dict) and "diff" in r]
    n_pool = len(recs)
    nc = len(L.per_deck_margins(cell["records"]))
    bad, notes = [], []
    if n_pool != want_games:
        bad.append(f"pooled scored records {n_pool} != frozen {want_games} games")
    n_failed_total, n_missing_summ = 0, 0
    for c in cell["chunks"]:
        nf, _ = L.resolve(_docs(c), "summary:n_failed", "manifest:n_failed")
        if nf is L.MISSING:
            n_missing_summ += 1
        else:
            n_failed_total += int(nf)
    if n_missing_summ:
        bad.append(f"{n_missing_summ} chunk(s) have no n_failed — ABSENT is FAIL")
    rate = (n_failed_total / want_games) if want_games else 1.0
    if n_failed_total:
        notes.append(f"⚠️ pooled n_failed = {n_failed_total} ({rate:.4%}) — "
                     "REPORTED, never silently absorbed")
    if rate >= L.FAILURE_RATE_VOID:
        bad.append(f"pooled failure rate {rate:.4%} >= {L.FAILURE_RATE_VOID:.0%}")
    floor = L.N_COMMON_FLOOR_FRACTION * spec["n_decks"]
    if nc < floor:
        bad.append(f"n_common {nc} < {L.N_COMMON_FLOOR_FRACTION:.0%} of "
                   f"{spec['n_decks']} ({floor:.0f})")
    return L.gate("G-N", not bad,
                  {"pooled_games": n_pool, "frozen_games": want_games,
                   "pooled_n_failed": n_failed_total, "failure_rate": rate,
                   "n_common": nc, "n_common_floor": floor,
                   "frozen_decks": spec["n_decks"], "notes": notes},
                  "the pooled records + each chunk's summary.json",
                  ("; ".join(notes) or "pooled n, n_failed and n_common at the "
                   "frozen plan") if not bad else
                  "⛔ G-N FAILED: " + "; ".join(bad))


def gate_band(cell: dict, claimed_band: int | None) -> dict:
    """`G-BAND` — every chunk names the claimed band as its `band_seed_start`
    base, and the cell's registered deck window is the one that was played."""
    spec = L.CELLS[cell["cell"]]
    bad, rows = [], {}
    if claimed_band is None:
        bad.append("no BAND_CLAIMED file found — the round has not been "
                   "claimed yet; a real cell may not be adjudicated as such")
    for c in cell["chunks"]:
        start, a = L.resolve(_docs(c), "manifest:config.band_seed_start",
                             "manifest:band_seed_start",
                             "manifest:config.seed_start")
        m = CHUNK_RE.search(c["name"])
        cidx = int(m.group(1)) if m else None
        want = (None if (claimed_band is None or cidx is None) else
                claimed_band + spec["deck_offset"]
                + (cidx - 1) * spec["decks_per_chunk"])
        rows[c["name"]] = {"band_seed_start": None if start is L.MISSING else start,
                           "expected": want, "address": a}
        if start is L.MISSING:
            bad.append(f"{c['name']}: band_seed_start ABSENT")
        elif want is not None and int(start) != want:
            bad.append(f"{c['name']}: band_seed_start {start} != expected {want}")
    return L.gate("G-BAND", not bad,
                  {"claimed_band": claimed_band, "chunks": rows,
                   "deck_window": (None if claimed_band is None else
                                   [claimed_band + spec["deck_offset"],
                                    claimed_band + spec["deck_offset"]
                                    + spec["n_decks"] - 1])},
                  "manifest:config.band_seed_start per chunk",
                  (f"every chunk starts at its planned offset inside the "
                   f"claimed band" if not bad else
                   "⛔ G-BAND FAILED: " + "; ".join(bad)))


def gate_decks(cell: dict, claimed_band: int | None) -> dict:
    """`G-DECKS` — every deck played BOTH seatings, every seed sits inside the
    cell's registered window, and `n_common` is exactly the frozen count."""
    spec = L.CELLS[cell["cell"]]
    recs = cell["records"]
    by_deck = L._by_deck(recs)
    seeds = sorted(by_deck)
    half = sorted(s for s, v in by_deck.items() if not (0 in v and 1 in v))
    n_common = len(L.per_deck_margins(recs))
    out_of_range = []
    if claimed_band is not None:
        lo = claimed_band + spec["deck_offset"]
        hi = lo + spec["n_decks"] - 1
        out_of_range = [s for s in seeds if not (lo <= s <= hi)]
    bad = []
    if half:
        bad.append(f"{len(half)} deck(s) played at ONE seat only")
    if n_common != spec["n_decks"]:
        bad.append(f"n_common {n_common} != frozen {spec['n_decks']}")
    if out_of_range:
        bad.append(f"{len(out_of_range)} seed(s) outside the registered window")
    return L.gate("G-DECKS", not bad,
                  {"n_seeds": len(seeds), "n_common": n_common,
                   "frozen_decks": spec["n_decks"],
                   "half_played_decks": half[:20],
                   "out_of_range": out_of_range[:20]},
                  "raw seed*_a*.json across the chunk pool",
                  ("every seed inside the window, both seatings present, "
                   f"n_common == {spec['n_decks']}" if not bad else
                   "⛔ G-DECKS FAILED: " + "; ".join(bad)))


def gate_sat(cell: dict) -> dict:
    """`G-SAT` — a RAIL, not a strength bar: the pooled winrate recomputed from
    the raw records sits inside the healthy band for a single-variable
    symmetric cell."""
    we = L.winrate_elo(cell["records"])
    wr = we["winrate"]
    if wr is None:
        return L.gate("G-SAT", False, {"winrate": None}, None,
                      "⛔ pooled winrate uncomputable (no scored records) — "
                      "ABSENT is FAIL")
    lo, hi = L.SAT_BAND
    ok = lo <= float(wr) <= hi
    return L.gate("G-SAT", ok, {"winrate": wr, "band": list(L.SAT_BAND),
                                "W": we["W"], "D": we["D"], "L": we["L"]},
                  "recomputed from the pooled raw records",
                  ("inside the rail" if ok else
                   f"⛔ pooled winrate {wr} outside {L.SAT_BAND}"))


# =========================================================================== #
# ADJUDICATION                                                                 #
# =========================================================================== #

def adjudicate_cell(cell: dict, claimed_band: int | None,
                    pinned_src_rev: str | None) -> dict:
    cell_name = cell["cell"]
    spec = L.CELLS[cell_name]

    per_chunk = []
    for c in cell["chunks"]:
        gs = [g(c, cell_name) for g in _CHUNK_GATES]
        gs.append(gate_rev(c, pinned_src_rev))
        gs.append(gate_blind(c))
        per_chunk.append({"chunk": c["name"], "gates": gs,
                          "failed_gates": [g["gate"] for g in gs if not g["ok"]],
                          "ok": all(g["ok"] for g in gs)})

    pool_gates = [gate_chunks(cell), gate_shard_ident(cell), gate_nodup(cell),
                  gate_n(cell), gate_band(cell, claimed_band),
                  gate_decks(cell, claimed_band), gate_sat(cell)]

    chunk_gates_ok = bool(per_chunk) and all(pc["ok"] for pc in per_chunk)
    pool_gates_ok = all(g["ok"] for g in pool_gates)
    gates_ok = chunk_gates_ok and pool_gates_ok

    m, z, n, se, per_deck = L.paired_margin(cell["records"])
    we = L.winrate_elo(cell["records"])
    se_elo = we["elo_sig_1sigma_paired"]
    branch = L.branch_for_cell(m, se, gates_ok=gates_ok)

    riders = list(L.RIDERS_ALWAYS) + list(L.RIDERS_BY_BRANCH.get(branch, ()))

    se_plan = L.se_model(spec["n_decks"])
    mde80 = L.mde(se_plan)
    typem = (m is not None and 0 < m < mde80)

    out = {
        "cell": cell_name, "role": spec["role"],
        "allocation": {"k_dets": spec["k_dets"],
                       "sims_per_det": spec["sims_per_det"],
                       "total_sims": spec["total_sims"],
                       "shape": spec["allocation"]},
        "opponent": {"k_dets": L.OPP_K_DETS,
                     "sims_per_det": L.OPP_SIMS_PER_DET,
                     "total_sims": L.OPP_TOTAL_SIMS},
        "per_chunk_gates": per_chunk,
        "pool_gates": pool_gates,
        "gates_ok": gates_ok,
        "chunk_gates_ok": chunk_gates_ok, "pool_gates_ok": pool_gates_ok,
        "failed_gates": sorted(
            {g for pc in per_chunk for g in pc["failed_gates"]}
            | {g["gate"] for g in pool_gates if not g["ok"]}),
        "stats": {
            "branch_z": L.BRANCH_Z, "bar_M": L.BAR_M,
            "margin": {
                "M": m, "se_realized": se, "z": z, "n_paired": n,
                "LB95": None if (m is None or se is None) else m - L.BRANCH_Z * se,
                "UB95": None if (m is None or se is None) else m + L.BRANCH_Z * se,
                "adopt_condition": None if (m is None or se is None) else
                    ((m - L.BRANCH_Z * se) > 0.0 and m >= L.BAR_M),
                "regression_condition": None if (m is None or se is None) else
                    (m + L.BRANCH_Z * se) <= 0.0,
                "null_bounded_condition": None if (m is None or se is None) else
                    (m + L.BRANCH_Z * se) < L.BAR_M,
            },
            "elo_coread": {
                "elo": we["elo"], "footing": we["elo_footing"],
                "se_realized": se_elo,
                "se_planning_wr05": L.elo_sigma_paired(0.5, spec["n_games"]),
                "LB95": None if (we["elo"] is None or se_elo is None)
                    else we["elo"] - L.BRANCH_Z * se_elo,
                "UB95": None if (we["elo"] is None or se_elo is None)
                    else we["elo"] + L.BRANCH_Z * se_elo,
                "winrate": we["winrate"], "W": we["W"], "D": we["D"],
                "L": we["L"],
                "note": "⛔ REPORTED, NEVER A BRANCH INPUT. The deck-paired "
                        "margin is the single PRIMARY statistic (PREREG §4.1): "
                        "at these n the margin leg is ~1.5x better powered "
                        "than elo, so adding elo as a co-primary would cost a "
                        "multiplicity correction and buy nothing. Elo is here "
                        "because it is the deployment-relevant currency and "
                        "because a sign disagreement with the margin is a "
                        "hand-review trigger.",
            },
        },
        "coherence": {
            "margin_sign": None if m is None else (1 if m > 0 else -1 if m < 0 else 0),
            "elo_sign": None if we["elo"] is None else
                (1 if we["elo"] > 0 else -1 if we["elo"] < 0 else 0),
            "agree": None if (m is None or we["elo"] is None) else
                ((m > 0) == (we["elo"] > 0)),
            "note": "a margin/elo SIGN DISAGREEMENT is a hand-review trigger "
                    "before any branch is acted on — it is not a gate and does "
                    "not change the branch label.",
        },
        "type_m": {
            "mde80_planning": mde80,
            "realized_below_own_mde": typem,
            "note": "⚠️ if `realized_below_own_mde` is true the MAGNITUDE is "
                    "biased UPWARD (winner's curse); the SIGN is the reliable "
                    "part. This is the same rider the 11008->22016 row carries "
                    "and it must be propagated, not laundered.",
        },
        "se_anomaly_margin": L.se_anomaly(se, max(1, n)),
        "se_anomaly_elo": L.elo_se_anomaly(se_elo, spec["n_games"]),
        "power_at_realized_se": {
            label: L.power_cell(delta, se if (se and se > 0) else se_plan)
            for label, delta in L.POWER_PRIORS},
        "branch": branch, "riders": riders,
        "_per_deck_margins": L.per_deck_margins(cell["records"]),
    }
    if branch == "U-VOID-INSTRUMENT":
        out["void_banner"] = ("⛔ U-VOID-INSTRUMENT — the instrument, not the "
                              "world. Statistics above are a COMPANION TABLE "
                              "only; no reading is taken.")
    return out


def width_contrast(primary_result: dict, screen_result: dict) -> dict:
    """⭐ THE SECONDARY WIDTH READ (`PREREG.md` §4.5). `W = D_K32 - D_SIMS` over
    the decks BOTH cells played — a WITHIN-BAND, DECK-MATCHED difference, which
    is the robust class under the cross-band ~2x humility rule.

    ⛔ REPORTED, NEVER LICENSING. No bar is pre-registered for it; it reads as a
    direction with a CI, and it is the FIRST direct measurement of the width
    axis at any budget above 2752 in either direction."""
    a = primary_result.get("_per_deck_margins") or {}
    b = screen_result.get("_per_deck_margins") or {}
    mean, z, n, se, _ = L.paired_difference(a, b)
    both_ok = bool(primary_result.get("gates_ok") and screen_result.get("gates_ok"))
    return {
        "statistic": "W = D(CELL_K32, k32x1376) - D(CELL_SIMS, k16x2752), "
                     "pts/deck, over the decks BOTH cells played",
        "W": mean, "se_realized": se, "z": z, "n_common_decks": n,
        "expected_n_common_decks": L.WIDTH_CONTRAST_DECKS,
        "LB95": None if (mean is None or se is None) else mean - L.BRANCH_Z * se,
        "UB95": None if (mean is None or se is None) else mean + L.BRANCH_Z * se,
        "direction": ("WIDTH (k32x1376) reads higher" if (mean or 0) > 0 else
                      "DEPTH (k16x2752) reads higher" if (mean or 0) < 0 else
                      "no direction"),
        "both_cells_gates_ok": both_ok,
        "riders": (
            "⛔ SECONDARY AND NON-LICENSING. No pre-registered bar; this is a "
            "third statistic on the same games and a directional read only.",
            "⭐ It is nevertheless the FIRST direct fixed-budget width contrast "
            "ever run above 2752 in this program — CL-054 measured the axis at "
            "2752 (inverted-U peaked at k4, k32 significantly worse) and "
            "CL-060 bounded it as a null at 11008. Whatever it reads, log it "
            "on those two claims and on docs/LEVER_INDEX.md.",
            "⚠️ The two cells are NOT independent (shared band, screen decks a "
            "subset of the primary's). That is what makes this contrast "
            "deck-matched and tight; it is also why NEITHER cell's own branch "
            "may be read as a replication of the other's.",
        ),
    }


def adjudicate(out_root: Path, claimed_band: int | None = None,
               pinned_src_rev: str | None = None) -> dict:
    results = {}
    for name in L.CELLS:
        cell = load_cell(out_root, name)
        results[name] = adjudicate_cell(cell, claimed_band, pinned_src_rev)
    return {
        "round": "budget44k (2 cells, ONE band, common deployed opponent) — "
                 "does the post-wheel budget doubling 22016 -> 44032 pay, and "
                 "at which allocation?",
        "pair": ["measurement/budget44k_prep/PREREG.md"],
        "owner_funding": "Joshua, 2026-09-01, verbatim: \"fund 44k at w30.\" "
                         "LOCAL box, W=30 (explicit override of the W=32 "
                         "logical-threads default; throughput-only).",
        "opponent": {"k_dets": L.OPP_K_DETS, "sims_per_det": L.OPP_SIMS_PER_DET,
                     "total_sims": L.OPP_TOTAL_SIMS,
                     "source": "governance/PRODUCTION.yaml champion.fair_deploy"},
        "bar_M": L.BAR_M,
        "bar_derivation": "decay-anchored: r x D_prev = 0.675 x 1.2293 = 0.8298 "
                          "-> +0.80 pts/deck. NOT 2*sigma-hat (owner ruling "
                          "2026-08-30).",
        "branch_z": L.BRANCH_Z,
        "planning": {
            "SE_primary_n800decks": L.SE_PRIMARY,
            "SE_screen_n400decks": L.SE_SCREEN,
            "MDE80_primary": L.mde(L.SE_PRIMARY),
            "MDE80_screen": L.mde(L.SE_SCREEN),
            "priors": {label: delta for label, delta in L.POWER_PRIORS},
            "power_primary": {label: L.power_cell(delta, L.SE_PRIMARY)
                              for label, delta in L.POWER_PRIORS},
            "power_screen": {label: L.power_cell(delta, L.SE_SCREEN)
                             for label, delta in L.POWER_PRIORS},
        },
        "eta_at_W30": {
            "g_per_h_44k_model": L.g_per_h_44k(),
            "cost_ratio_vs_22016_game": L.cost_ratio_44k_game(),
            "hours_primary": L.eta_hours(L.CELLS[L.PRIMARY_CELL]["n_games"]),
            "hours_screen": L.eta_hours(L.CELLS[L.SCREEN_CELL]["n_games"]),
            "hours_round": L.eta_hours(sum(c["n_games"] for c in L.CELLS.values())),
            "note": "MODEL. Re-derive from the round's own first completed "
                    "chunk (feedback_eta_before_launch); the launcher prints "
                    "that re-derivation.",
        },
        "results": results,
        "width_contrast": width_contrast(results[L.PRIMARY_CELL],
                                         results[L.SCREEN_CELL]),
        "width_prior": L.WIDTH_PRIOR_NOTE,
    }


# =========================================================================== #
# SMOKE MODE                                                                   #
# =========================================================================== #

def smoke_problems(cell: dict) -> list[str]:
    """Non-empty == the smoke FAILED == a nonzero exit."""
    probs: list[str] = []
    chunks = cell.get("chunks") or []
    if not chunks or not any(c.get("manifest") for c in chunks):
        probs.append("⛔⛔ NO manifest.json FOUND — nothing was read, so "
                     "nothing was proven. Check --root and that the harness "
                     "actually ran.")
        return probs
    if not any(c.get("records") for c in chunks):
        probs.append("⛔⛔ ZERO per-game records — the harness produced a "
                     "manifest but played nothing.")
    ran_any = False
    for c in chunks:
        gates = [g(c, cell["cell"]) for g in _CHUNK_GATES]
        by_id = {g["gate"]: g for g in gates}
        ran = [gid for gid in SMOKE_REQUIRED_GATES if gid in by_id]
        if ran:
            ran_any = True
        for gid in ran:
            if not by_id[gid]["ok"]:
                probs.append(f"⛔ [{c['name']}] {gid} FAILED: {by_id[gid]['why']}")
    if not ran_any:
        probs.append("⛔⛔ THE SMOKE ADJUDICATED ZERO REQUIRED GATES — the "
                     "fpu_resurrection_prep R1 defect (an unreachable "
                     "|| DIE because the smoke silently adjudicated nothing).")
    return probs


# =========================================================================== #
# SELFTEST                                                                     #
# =========================================================================== #

#: Each defect MUTATES a healthy real-emitter fixture and must fail its NAMED
#: gate. `chunk` mutations apply to the single loaded chunk.
FIXTURE_DEFECTS = (
    ("opp_budget_flag_forgotten__symmetric_cell",
     lambda c: (c["manifest"]["config"]["opponent"].update(
         k_dets=c["manifest"]["config"]["champion"]["k_dets"],
         sims_per_det=c["manifest"]["config"]["champion"]["sims_per_det"],
         total_sims=c["manifest"]["config"]["champion"]["total_sims"]),
         c["summary"].update(
             opp_k_dets=c["summary"]["candidate_k_dets"],
             opp_sims=c["summary"]["candidate_sims"],
             opp_total_sims=c["summary"]["candidate_total_sims"])),
     "G-BUDGET-RATIO"),
    ("asymmetric_budgets_flag_false",
     lambda c: c["summary"].update(asymmetric_budgets=False),
     "G-BUDGET"),
    ("summary_budget_disagrees_with_manifest",
     lambda c: c["summary"].update(opp_total_sims=99999),
     "G-BUDGET"),
    ("candidate_budget_not_double",
     lambda c: (c["manifest"]["config"]["champion"].update(
         sims_per_det=c["manifest"]["config"]["champion"]["sims_per_det"] + 1),
         c["manifest"]["config"]["champion"].update(
             total_sims=c["manifest"]["config"]["champion"]["k_dets"]
             * (c["manifest"]["config"]["champion"]["sims_per_det"]))),
     "G-BUDGET-RATIO"),
    ("cand_arb_disarmed",
     lambda c: c["manifest"]["cand_tiearb"].update(enabled=False),
     "G-TIEARB-SIDES"),
    ("opp_arb_disarmed",
     lambda c: c["manifest"]["opp_tiearb"].update(enabled=False),
     "G-TIEARB-SIDES"),
    ("opp_arb_wrong_B",
     lambda c: c["manifest"]["opp_tiearb"].update(B=32),
     "G-TIEARB-SIDES"),
    ("cand_arb_wrong_B",
     lambda c: c["manifest"]["cand_tiearb"].update(B=16),
     "G-TIEARB-SIDES"),
    ("cand_arb_never_fired",
     lambda c: c["summary"].update(tiearb_fired_plies_total=0),
     "G-TIEARB-FIRED"),
    ("opp_arb_never_fired",
     lambda c: c["summary"].update(opp_tiearb_fired_plies_total=0),
     "G-TIEARB-FIRED"),
    ("opp_arb_container_absent_in_play",
     lambda c: c["summary"].update(opp_tiearb_games=0),
     "G-TIEARB-FIRED"),
    ("leaf_hashes_differ",
     lambda c: c["manifest"]["config"].update(opp_leaf_hash="deadbeef"),
     "G-LEAF"),
    ("rules_profile_walled",
     lambda c: c["manifest"]["rules_profile"].update(name="walled"),
     "G-RULES"),
    ("r9_env_not_observed",
     lambda c: c["manifest"]["rules_profile"].update(r9_env_ok=False),
     "G-RULES"),
    ("exact_k_wrong",
     lambda c: c["manifest"]["config"]["endgame"].update(exact_k=4),
     "G-EXACT"),
    ("endgame_mode_wrong",
     lambda c: c["manifest"]["config"]["endgame"].update(mode="alphabeta"),
     "G-EXACT"),
    ("backend_python",
     lambda c: c["manifest"]["config"]["backend"].update(name="python"),
     "G-BACKEND"),
    ("wheel_unavailable",
     lambda c: c["manifest"].update(carc_rs_build="unavailable"),
     "G-WHEEL"),
    ("mixed_builds",
     lambda c: c["manifest"].update(mixed_builds=True),
     "G-WHEEL"),
    ("wrong_host_laptop",
     lambda c: c["manifest"].update(host="laptop-wsl"),
     "G-HOST"),
    ("recon_disagrees",
     lambda c: c["summary"].update(paired_mean_margin=99.0),
     "RECON"),
)

#: Pool-level defects need the whole cell, not one chunk.
POOL_DEFECTS = (
    ("a_deck_played_one_seat_only",
     lambda cell: cell["chunks"][0]["records"].pop(),
     "G-DECKS"),
    ("chunk_not_marked_done",
     lambda cell: cell["chunks"][0].update(done=False),
     "G-CHUNKS"),
    ("chunk_summary_absent",
     lambda cell: cell["chunks"][0].update(summary=None),
     "G-CHUNKS"),
)


def _deep_copy(obj):
    return json.loads(json.dumps(obj))


def _resync(cell: dict) -> dict:
    """Re-derive the pooled `records` list after a chunk-level mutation."""
    cell["records"] = [r for c in cell["chunks"] for r in c["records"]]
    return cell


def _load_fixture(cell_name: str):
    """`(cell, pinned, band)` for one shipped fixture, or `None`."""
    fx = HERE / "selftest_fixture" / cell_name
    if not (fx.is_dir() and (fx / "manifest.json").is_file()):
        return None
    pin_f, band_f = fx / "PINNED_SRC_REV", fx / "CLAIMED_BAND"
    pin = pin_f.read_text().strip() if pin_f.is_file() else None
    band = int(band_f.read_text().strip()) if band_f.is_file() else None
    return load_single_dir_as_cell(fx, cell_name), pin, band


def selftest() -> int:
    problems = list(L.sanity_check())
    report: dict = {}

    # ------------------------------------------------------------------ #
    # 1. The branch ladder, re-derived independently (a witness, not a copy)
    # ------------------------------------------------------------------ #
    for m100 in range(-400, 401, 4):
        M = m100 / 100.0
        for se100 in (12, 25, 35, 49, 69, 95, 140):
            se = se100 / 100.0
            b = L.branch_for_cell(M, se, gates_ok=True)
            reg = (M + L.BRANCH_Z * se) <= 0.0
            adopt = (M - L.BRANCH_Z * se) > 0.0 and M >= L.BAR_M
            nullb = (M + L.BRANCH_Z * se) < L.BAR_M
            expect = ("B-REGRESSION" if reg else "B-ADOPT" if adopt else
                      "B-NULL-BOUNDED" if nullb else "B-UNRESOLVED")
            if b != expect:
                problems.append(f"branch({M},{se}) = {b}, expected {expect}")

    # ------------------------------------------------------------------ #
    # 2. ABSENT is FAIL on an empty pool
    # ------------------------------------------------------------------ #
    for name in L.CELLS:
        empty = {"cell": name, "out_root": "<empty>", "chunks": [], "records": []}
        r = adjudicate_cell(empty, claimed_band=None, pinned_src_rev=None)
        if r["gates_ok"]:
            problems.append(f"{name}: an EMPTY pool passed the gates — "
                            "ABSENT must be FAIL")
        for g in r["pool_gates"]:
            if g["ok"]:
                problems.append(f"{name}: {g['gate']} passed on an EMPTY pool "
                                "(vacuous pass)")
        if r["branch"] != "U-VOID-INSTRUMENT":
            problems.append(f"{name}: an empty cell read {r['branch']}, not "
                            "U-VOID-INSTRUMENT")

    # ------------------------------------------------------------------ #
    # 3. THE SHIPPED FIXTURES — real emitter output, healthy + defects
    # ------------------------------------------------------------------ #
    any_fixture = False
    for cell_name in L.CELLS:
        loaded = _load_fixture(cell_name)
        if loaded is None:
            problems.append(
                f"selftest_fixture/{cell_name}/ is missing manifest.json — the "
                "FIXTURE-TRAP: fixtures must come from a REAL emitter's smoke "
                "output, never hand-authored. Run "
                "`./launch_budget44k.sh --smoke` once and copy its archives "
                "here (see selftest_fixture/README.md).")
            continue
        any_fixture = True
        healthy, pin, band = loaded
        v = adjudicate_cell(healthy, claimed_band=band, pinned_src_rev=pin)
        by_id = {g["gate"]: g["ok"]
                 for pc in v["per_chunk_gates"] for g in pc["gates"]}
        report[cell_name] = {"branch": v["branch"],
                             "failed_gates": v["failed_gates"],
                             "required_gates": {gid: by_id.get(gid)
                                                for gid in SMOKE_REQUIRED_GATES}}
        for gid in SMOKE_REQUIRED_GATES:
            if gid not in by_id:
                problems.append(f"{cell_name}: the healthy fixture never ran {gid}")
            elif not by_id[gid]:
                problems.append(
                    f"{cell_name}: the healthy fixture FAILED {gid} — it is "
                    "supposed to be a clean, real-emitter output")
        # The fixture is a TINY reduced-budget smoke, so the magnitude gate
        # MUST fail on it. If it ever passes, the fixture has silently become
        # a real cell (or G-BUDGET has stopped checking magnitudes).
        if by_id.get("G-BUDGET"):
            problems.append(
                f"{cell_name}: G-BUDGET PASSED on the reduced-budget fixture — "
                "either the fixture is no longer reduced-budget or G-BUDGET "
                "has stopped pinning the frozen 44032/22016 magnitudes")
        if smoke_problems(healthy):
            problems.append(f"{cell_name}: smoke_problems() non-empty on the "
                            f"healthy fixture: {smoke_problems(healthy)}")

        for dname, mutate, expect_gate in FIXTURE_DEFECTS:
            broken = _resync(_deep_copy(healthy))
            try:
                mutate(broken["chunks"][0])
            except Exception as e:                               # noqa: BLE001
                problems.append(f"{cell_name}/{dname}: could not apply: {e}")
                continue
            _resync(broken)
            bv = adjudicate_cell(broken, claimed_band=band, pinned_src_rev=pin)
            bid = {g["gate"]: g["ok"]
                   for pc in bv["per_chunk_gates"] for g in pc["gates"]}
            if bid.get(expect_gate, True):
                problems.append(
                    f"{cell_name}/{dname}: did NOT fail its own gate "
                    f"{expect_gate!r} (failed: {bv['failed_gates']})")
            if bv["gates_ok"]:
                problems.append(f"{cell_name}/{dname}: left gates_ok True")

        for dname, mutate, expect_gate in POOL_DEFECTS:
            broken = _resync(_deep_copy(healthy))
            try:
                mutate(broken)
            except Exception as e:                               # noqa: BLE001
                problems.append(f"{cell_name}/{dname}: could not apply: {e}")
                continue
            _resync(broken)
            bv = adjudicate_cell(broken, claimed_band=band, pinned_src_rev=pin)
            pid = {g["gate"]: g["ok"] for g in bv["pool_gates"]}
            if pid.get(expect_gate, True):
                problems.append(
                    f"{cell_name}/{dname}: did NOT fail its own pool gate "
                    f"{expect_gate!r} (failed: {bv['failed_gates']})")

    # ------------------------------------------------------------------ #
    # 4. A SYNTHETIC TWO-CHUNK POOL, built by DUPLICATING a real fixture —
    #    the chunk-pooling machinery cannot be exercised by a one-chunk
    #    fixture, and G-NODUP's whole job is to catch exactly this.
    # ------------------------------------------------------------------ #
    loaded = _load_fixture(L.PRIMARY_CELL)
    if loaded is not None:
        healthy, pin, band = loaded
        dup = _resync(_deep_copy(healthy))
        c2 = _deep_copy(dup["chunks"][0])
        c2["name"] = L.PRIMARY_CELL + "__c2"
        dup["chunks"].append(c2)
        _resync(dup)
        dv = adjudicate_cell(dup, claimed_band=band, pinned_src_rev=pin)
        pid = {g["gate"]: g["ok"] for g in dv["pool_gates"]}
        if pid.get("G-NODUP", True):
            problems.append("G-NODUP did NOT fail on a pool containing the "
                            "same (deck,seat) twice — the resume-double-count "
                            "defect would go undetected")
        # ...and a chunk whose wheel differs must fail G-SHARD-IDENT
        drift = _resync(_deep_copy(dup))
        drift["chunks"][1]["manifest"]["carc_rs_binary_sha"] = "0" * 16
        dv2 = adjudicate_cell(drift, claimed_band=band, pinned_src_rev=pin)
        pid2 = {g["gate"]: g["ok"] for g in dv2["pool_gates"]}
        if pid2.get("G-SHARD-IDENT", True):
            problems.append("G-SHARD-IDENT did NOT fail on a pool whose chunks "
                            "carry different wheel shas")

    # ------------------------------------------------------------------ #
    # 5. The width contrast is computable and non-licensing
    # ------------------------------------------------------------------ #
    fake_a = {"_per_deck_margins": {1: 3.0, 2: 5.0, 3: 1.0}, "gates_ok": True}
    fake_b = {"_per_deck_margins": {1: 1.0, 2: 1.0, 3: 1.0}, "gates_ok": True}
    wc = width_contrast(fake_a, fake_b)
    if wc["n_common_decks"] != 3 or abs((wc["W"] or 0) - 2.0) > 1e-9:
        problems.append(f"width_contrast on a fixture gave {wc['W']} over "
                        f"{wc['n_common_decks']} decks, want 2.0 over 3")
    if "W" not in wc or "branch" in wc:
        problems.append("width_contrast must report a statistic and NEVER a "
                        "branch — it is non-licensing by design")

    if not any_fixture:
        problems.append("NO fixtures at all — the selftest proved nothing "
                        "about the real emitter's manifest shape.")

    if problems:
        print(f"⛔ SELFTEST FAILED ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("selftest OK:", json.dumps(report, default=str, indent=1))
    return 0


# =========================================================================== #
# CLI                                                                          #
# =========================================================================== #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", type=str, default=None,
                    help="the SHARE root holding <CELL>__c<N>/ chunk dirs")
    ap.add_argument("--root", type=str, default=None,
                    help="--smoke-mode only: ONE archive dir to adjudicate")
    ap.add_argument("--cell", type=str, default=None,
                    choices=sorted(L.CELLS),
                    help="--smoke-mode only: which cell's shape --root is")
    ap.add_argument("--smoke-mode", action="store_true")
    ap.add_argument("--pinned-src-rev", type=str, default=None)
    ap.add_argument("--out", type=str, default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.smoke_mode:
        if not args.root or not args.cell:
            print("⛔ --smoke-mode needs --root and --cell", file=sys.stderr)
            return 2
        cell = load_single_dir_as_cell(Path(args.root), args.cell)
        probs = smoke_problems(cell)
        chunk = cell["chunks"][0]
        d = _docs(chunk)
        v = {"smoke_mode": True, "root": args.root, "cell": args.cell,
             "problems": probs,
             "resolved_budgets": {
                 "manifest_candidate": [
                     None if x is L.MISSING else x
                     for x in L._budget_triple(d, "candidate")[:3]],
                 "manifest_opponent": [
                     None if x is L.MISSING else x
                     for x in L._budget_triple(d, "opponent")[:3]],
                 "summary_asymmetric_budgets":
                     (lambda x: None if x is L.MISSING else x)(
                         L.resolve(d, "summary:asymmetric_budgets")[0]),
             },
             "resolved_tiearb": {
                 "cand": (lambda x: None if x is L.MISSING else x)(
                     L.resolve(d, "manifest:cand_tiearb",
                               "manifest:config.cand_tiearb")[0]),
                 "opp": (lambda x: None if x is L.MISSING else x)(
                     L.resolve(d, "manifest:opp_tiearb",
                               "manifest:config.opp_tiearb")[0]),
             },
             "gates": [g(chunk, args.cell) for g in _CHUNK_GATES
                       if g(chunk, args.cell)["gate"] in SMOKE_REQUIRED_GATES]}
        if args.out:
            Path(args.out).write_text(json.dumps(v, indent=2, default=str))
        print(json.dumps(v, indent=2, default=str))
        return 0 if not probs else 1

    if not args.out_root:
        print("⛔ --out-root is required outside --selftest/--smoke-mode",
              file=sys.stderr)
        return 2
    v = adjudicate(Path(args.out_root), claimed_band=read_claimed_band(),
                   pinned_src_rev=args.pinned_src_rev)
    if args.out:
        Path(args.out).write_text(json.dumps(v, indent=2, default=str))
    print(json.dumps(v, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
