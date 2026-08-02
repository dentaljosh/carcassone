#!/usr/bin/env python3
"""GATE (c) — IDENTITY GATE for `oracle_score_pilot --backend rust` (audit A3 / B1).

WHY.  The pilot is a RULER: its number (+0.7375 pts/disagreement, cluster-robust
z +2.97) is a property of the instrument that produced it, so a converted ruler
is a NEW ruler unless the conversion is provably a no-op ON THE RECORD.  It ran
python-only until 2026-08-02 because its continuation is a PERSISTING-TREE search
(it calls `best_action`, which never clears `NeuralMCTS._nodes`) and
`MirrorState.search_single` was fresh-tree only — Gap 2, now closed by
`carc_rs.PersistentSearcher`.

WHAT IS COMPARED.  The instrument's OWN per-position worker, `_process`, is run
TWICE per cell — once with `_G["backend"] = "python"`, once with `"rust"` — and
the two emitted records are diffed FIELD BY FIELD with every float canonicalised
to its raw f64 BIT pattern (the G3 pattern; a decimal comparison hides the 1-ulp
divergence a reconcile gate exists to catch).  Only genuinely time-valued keys
are excluded:

    elapsed_secs   wall clock

Everything else is in scope, and for this instrument that is the whole
measurement: `values_a` / `values_b` (the per-world terminal margins — the oracle
itself), `playout_plies_a/b`, the `afterstate_deck_hash_*` and
`afterstate_board_key_*` CRN witnesses, `crn_verified`, `distinct_afterstates`,
and the `position_delta` block (`delta`, the paired/unpaired variances, the CRN
variance-reduction ratio).  `delta` is the sharpest of these: a mean over M
paired world differences, so it moves on any divergence in any playout.

⚠️ SCOPE.  A green result licenses the CLAIR-PUCT continuation at these knobs on
this revision.  `--oracle-policy tier1-greedy` is out of scope by construction (a
`RuleBasedPlayer` on the v1 OBJECT leaf; carc_rs has no such player, and the
harness refuses it on the Rust backend).

    .venv/bin/python scripts/rustport/gate_oracle_pilot_backend.py --positions 20
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))
sys.path.insert(0, str(REPO / "scripts" / "level2"))

# MUST precede any carcassonne_ai import (import-frozen DEFAULT_CONFIG).
import oracle_score_pilot as O  # noqa: E402

from carcassonne_ai import champion_factory as CF  # noqa: E402

CHAMP_GAMES = REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"
OUT = REPO / "measurement" / "rustport_p6" / "GATE_ORACLE_PILOT_BACKEND.json"

SKIP_FIELDS = {"elapsed_secs"}


def _share(rel: str) -> str:
    for root in ("/mnt/c/carc-shared", "/mnt/carc-shared"):
        if Path(root).is_dir():
            return f"{root}/{rel}"
    return f"/mnt/carc-shared/{rel}"


DEFAULT_BANK = _share("oracle_110k_20260801")
DEFAULT_ROOTS_RUN = _share("classical_search/move_agreement_k4_b28e9")


def canon(x):
    """Floats -> raw f64 bits; dicts/lists walked. The comparison currency."""
    if isinstance(x, bool) or x is None or isinstance(x, (int, str)):
        return x
    if isinstance(x, float):
        return ("f64", struct.unpack("<Q", struct.pack("<d", x))[0])
    if isinstance(x, dict):
        return {k: canon(v) for k, v in sorted(x.items())}
    if isinstance(x, (list, tuple)):
        return [canon(v) for v in x]
    return repr(x)


def load_items(bank: Path, roots_run: Path, n: int) -> list:
    """Scored bank cells joined to their action sequences; champion-game fallback."""
    recs_dir = bank / "score" / "records"
    roots_path = roots_run / "roots.jsonl"
    if recs_dir.is_dir() and roots_path.is_file():
        roots = {}
        for line in roots_path.read_text().splitlines():
            if line.strip():
                o = json.loads(line)
                roots[f"s{int(o['deck_seed'])}_p{int(o['ply'])}"] = o
        items = []
        for p in sorted(recs_dir.glob("s*.json")):
            d = json.loads(p.read_text())
            if not d.get("ok") or d.get("pick_a") is None or d.get("pick_b") is None:
                continue
            r = roots.get(d["root_id"])
            if r is None:
                continue
            it = {k: d.get(k) for k in (
                "rid", "root_id", "deck_seed", "ply", "salt", "pick_a", "pick_b",
                "root_player", "k_remaining", "game_phase", "phase_bucket", "n_legal",
                "h200_top2_q_gap", "solver_region", "level_a", "level_b", "alloc_a",
                "alloc_b", "world_seed_salt")}
            it["actions"] = [int(a) for a in r["actions"]]
            it["checksum"] = r.get("checksum")
            it["source"] = "bank"
            items.append(it)
            if len(items) >= n:
                break
        if items:
            return items
    # Fallback: synthesise cells off the recorded champion games, with the two picks
    # taken from the root's legal set (this gate tests the ENGINE, not the picks).
    import numpy as np

    import root_replay as RR

    out = []
    if not CHAMP_GAMES.is_file():                     # pragma: no cover
        return out
    for g in [json.loads(ln) for ln in CHAMP_GAMES.open() if ln.strip()]:
        acts = [int(a) for a in g["actions"]]
        for ply in (40, 72, 104):
            if ply >= len(acts) or len(out) >= n:
                continue
            game, board = RR.replay_actions(int(g["deck_seed"]), acts, ply)
            legal = [int(x) for x in np.flatnonzero(game.get_valid_moves(board))]
            if len(legal) < 2:
                continue
            out.append({"rid": f"s{g['deck_seed']}_p{ply}_r1",
                        "root_id": f"s{g['deck_seed']}_p{ply}",
                        "deck_seed": int(g["deck_seed"]), "ply": int(ply), "salt": 1,
                        "pick_a": legal[0], "pick_b": legal[-1],
                        "root_player": int(board.state.current_player),
                        "actions": acts, "checksum": None, "k_remaining": None,
                        "game_phase": None, "phase_bucket": None, "n_legal": len(legal),
                        "h200_top2_q_gap": None, "solver_region": False,
                        "level_a": None, "level_b": None, "alloc_a": None,
                        "alloc_b": None, "world_seed_salt": "oracle-pilot-v1",
                        "source": "champ"})
        if len(out) >= n:
            break
    return out


def run_leg(item: dict, *, backend: str, m: int, oracle_sims: int, max_plies: int) -> dict:
    O._G.clear()
    O._init({"level_a": item.get("level_a") or O.LEVEL_A_DEFAULT,
             "level_b": item.get("level_b") or O.LEVEL_B_DEFAULT,
             "alloc_a": O.parse_alloc(item.get("alloc_a"),
                                      item.get("level_a") or O.LEVEL_A_DEFAULT),
             "alloc_b": O.parse_alloc(item.get("alloc_b"),
                                      item.get("level_b") or O.LEVEL_B_DEFAULT),
             "m": int(m), "oracle_sims": int(oracle_sims),
             "world_seed_salt": item.get("world_seed_salt") or "oracle-pilot-v1",
             "oracle_policy": "clair-puct", "wall_cap": 7200,
             "max_plies": int(max_plies), "strict_crn": True, "backend": backend})
    return O._process(dict(item))


def _cell(job: tuple) -> dict:
    """One position, BOTH backends — the unit a worker owns.

    Both legs run in the SAME process so the leaf env, the import-frozen
    DEFAULT_CONFIG and the libm flavour are identical by construction; only the
    engine differs.  (A cross-process comparison would silently add those axes.)
    """
    item, m, oracle_sims, max_plies = job
    out = {"item": item}
    for backend in ("python", "rust"):
        t0 = time.perf_counter()
        out[backend] = run_leg(item, backend=backend, m=m, oracle_sims=oracle_sims,
                               max_plies=max_plies)
        out[f"{backend}_secs"] = time.perf_counter() - t0
    return out


def compare(py: dict, rs: dict, ctx: dict, mismatches: list) -> int:
    keys = (set(py) | set(rs)) - SKIP_FIELDS
    checks = 0
    for f in sorted(keys):
        checks += 1
        a, b = canon(py.get(f, "<absent>")), canon(rs.get(f, "<absent>"))
        if a != b:
            mismatches.append({**ctx, "field": f,
                               "python": str(py.get(f))[:300],
                               "rust": str(rs.get(f))[:300]})
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gate_oracle_pilot_backend")
    ap.add_argument("--positions", type=int, default=20,
                    help="scored cells to re-run on both backends (the gate bar is >=20)")
    ap.add_argument("--m", type=int, default=2,
                    help="CRN deck completions per position. The gate's currency is "
                         "IDENTITY, not power, so a small M buys the same proof cheaper "
                         "— but it must be >=2 or the CRN pairing is not exercised.")
    ap.add_argument("--oracle-sims", type=int, default=100,
                    help="the pilot's own continuation budget")
    ap.add_argument("--max-plies", type=int, default=400)
    ap.add_argument("--workers", type=int, default=1,
                    help="POSITION-parallel fork pool. Each worker runs BOTH backends "
                         "for its position, so the comparison never crosses a process. "
                         "⚠️ the python leg is ~100x the rust leg's wall clock; size W "
                         "to the box and never run this beside a live eval.")
    ap.add_argument("--bank", default=DEFAULT_BANK)
    ap.add_argument("--roots-run", default=DEFAULT_ROOTS_RUN)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)

    if int(args.m) < 2:
        ap.error("--m must be >= 2 (M=1 exercises no CRN pairing)")

    items = load_items(Path(args.bank), Path(args.roots_run), int(args.positions))
    if not items:
        print("FAIL: no cells resolved — a gate that ran on an empty set has gated "
              "nothing")
        return 1

    jobs = [(it, int(args.m), int(args.oracle_sims), int(args.max_plies))
            for it in items]
    if int(args.workers) > 1:
        import multiprocessing as mp

        ctx = mp.get_context("fork")
        with ctx.Pool(min(int(args.workers), len(jobs))) as pool:
            cells = list(pool.imap_unordered(_cell, jobs))
    else:
        cells = [_cell(j) for j in jobs]

    rows, mismatches, checks = [], [], 0
    t_py_total = t_rs_total = 0.0
    for cell in cells:
        item = cell["item"]
        py, t_py = cell["python"], cell["python_secs"]
        rs, t_rs = cell["rust"], cell["rust_secs"]
        t_py_total += t_py
        t_rs_total += t_rs
        if not (py.get("ok") and rs.get("ok")):
            # A cell the HARNESS itself refuses is not a gate failure — but the two
            # backends must refuse it for the SAME reason, or the record set would
            # differ in membership.
            agree = (bool(py.get("ok")) == bool(rs.get("ok"))
                     and py.get("error") == rs.get("error"))
            if not agree:
                mismatches.append({"rid": item["rid"], "field": "<ok>",
                                   "python": str(py.get("error"))[:300],
                                   "rust": str(rs.get("error"))[:300]})
            print(f"  {item['rid']:<26} SKIPPED-BY-HARNESS ({py.get('error')}) "
                  f"{'same on both' if agree else 'DIVERGENT REFUSAL'}", flush=True)
            continue
        n = compare(py, rs, {"rid": item["rid"]}, mismatches)
        checks += n
        same = not any(m.get("rid") == item["rid"] for m in mismatches)
        rows.append({"rid": item["rid"], "source": item.get("source"),
                     "deck_seed": item["deck_seed"], "ply": item["ply"],
                     "m": int(args.m), "fields": n,
                     "delta": py.get("delta"),
                     "values_a": py.get("values_a"), "values_b": py.get("values_b"),
                     "crn_verified": py.get("crn_verified"),
                     "python_secs": round(t_py, 2), "rust_secs": round(t_rs, 2),
                     "speedup": (round(t_py / t_rs, 2) if t_rs > 0 else None),
                     "identical": same})
        print(f"  {item['rid']:<26} delta={py.get('delta'):+.3f} "
              f"crn={py.get('crn_verified')} {n} fields "
              f"{'IDENTICAL' if same else 'MISMATCH'} | py {t_py:.1f}s rs {t_rs:.1f}s "
              f"x{t_py / max(t_rs, 1e-9):.1f}", flush=True)

    ok = bool(rows) and not mismatches
    out = {
        "gate": "rustport A3/B1 — oracle_score_pilot python vs rust continuation",
        "why": "the pilot is a RULER (+0.7375 pts/disagreement, cluster-robust z +2.97); "
               "a converted ruler is a NEW ruler unless the conversion is provably a "
               "no-op ON THE RECORD.",
        "seam": "the CONTINUATION AGENT only (build_continuation_agent -> "
                "champion_factory.build_clairvoyant_champion(backend=...) -> "
                "rust_agent.RustCarryClairvoyantAgent over carc_rs.PersistentSearcher). "
                "World sampling, CRN seed derivation, replay, the determinization draw "
                "and the terminal-score read are the SAME code on both legs.",
        "gap2": "CLOSED — the rust continuation is a PERSISTING-TREE search "
                "(best_action carries), not MirrorState.search_single. Evidence: "
                "GAP2_ORACLE_CONTINUATION_TREE.json (the problem), "
                "GATE_GAP2_PERSISTENT.json (the fix, three-way).",
        "surface": "every record field except " + str(sorted(SKIP_FIELDS)) +
                   ", floats canonicalised to raw f64 bit patterns — per-world terminal "
                   "margins (values_a/values_b), ply counts, the afterstate deck-hash / "
                   "board-key CRN witnesses, and the whole position_delta block",
        "knobs": {"m_worlds": int(args.m), "oracle_sims": int(args.oracle_sims),
                  "max_plies": int(args.max_plies), "oracle_policy": "clair-puct"},
        "positions": len(rows),
        "field_checks": checks,
        "mismatches": mismatches,
        "python_secs": round(t_py_total, 1), "rust_secs": round(t_rs_total, 1),
        "speedup": (round(t_py_total / t_rs_total, 2) if t_rs_total > 0 else None),
        "verdict": "PASS" if ok else "FAIL",
        "scope": "the clair-puct continuation at these knobs on this revision. "
                 "tier1-greedy is out of scope (no Rust RuleBasedPlayer — the harness "
                 "refuses it). Says nothing about Gap 3 (evaluator injection) or the "
                 "snapshot/UCT family, which remain OPEN.",
        "rows": rows,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\n{out['verdict']}: {len(rows)} positions, {checks} field checks, "
          f"{len(mismatches)} mismatches, {out['speedup']}x -> {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
