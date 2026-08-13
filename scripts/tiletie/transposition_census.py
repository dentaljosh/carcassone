#!/usr/bin/env python3
"""How much of the leaf's TILE tie rate is genuine blindness, and how much is
the leaf correctly pricing DUPLICATE moves?

MOTIVATION (measured, not hypothetical). The 2026-08-12 production-knob smoke
scored 5 leaf-tied E4 positions and **2 of them came back with
`distinct_afterstates == 0`** -- the two "different" tied tile actions led to
the *same* board in all 32 CRN worlds. For those, a zero oracle delta means the
harness did nothing, NOT that the leaf is blind: the actions transpose (a
rotationally symmetric tile, or a placement whose rotations are equivalent).

`measurement/tiletie_pricing_20260812/DESIGN.md` pre-registers this as threat 3
and as a sensitivity on the scored run. This script answers the cheaper, prior
question directly and with NO oracle and NO search: inside each exact-tie set,
how many of the tied actions are DISTINCT POSITIONS?

Method: replay each tied ply, apply every member of the exact-tie set, and key
the successor by `game.string_representation`. `n_distinct_afterstates` is the
number of unique keys. `tie_is_all_transposition` means the whole tied set
collapses to ONE position -- i.e. the leaf had literally nothing to
discriminate and the "tie" is correct by construction.

⚠️ Keyed on the TILE successor, before the meeple decision, because the tie is
scored on the outer chain value and the oracle's arms are tile actions.

Usage (one profile per process -- CARCASSONNE_FIX_R9 is import-latched):
    python scripts/tiletie/transposition_census.py --profile fixed_v1 --stratum e4
    python scripts/tiletie/transposition_census.py --profile walled  --stratum selfplay
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "tiletie"))
sys.path.insert(0, str(REPO / "scripts" / "measurement_infra"))

import chain_census as CC  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rows", default=str(
        REPO / "measurement/tiletie_pricing_20260812/census/rows.jsonl"))
    ap.add_argument("--profile", required=True)
    ap.add_argument("--stratum", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    CC.prepare_env(a.profile)                      # BEFORE any carcassonne_ai import
    from carcassonne_ai import rules_profile as RP
    import root_replay as RR

    prof = RP.activate(a.profile)
    gk = prof.game_kwargs() or None

    rows = []
    for line in Path(a.rows).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("tie_exact") or r.get("tie_actions_exact_truncated"):
            continue
        if r.get("rules_profile") != a.profile:
            continue
        if a.stratum and r.get("stratum") != a.stratum:
            continue
        rows.append(r)
    if a.limit:
        rows = rows[:a.limit]

    # `actions` are not on the census row -- resolve them from the source corpora.
    e4_actions, sp_actions = {}, {}
    for r in rows:
        if r["stratum"] == "e4" and r["game_label"] not in e4_actions:
            p = REPO / "measurement" / "e4_games" / f"{r['game_label']}.json"
            e4_actions[r["game_label"]] = [int(x) for x in
                                           json.loads(p.read_text())["actions"]]
    if any(r["stratum"] == "selfplay" for r in rows):
        for src, path in (("bank", "/mnt/c/carc-shared/classical_search/"
                                    "move_agreement_k4_b28e9/roots.jsonl"),
                          ("champ_games", str(REPO / "measurement/champ_action_logs/"
                                                     "champ_games.jsonl"))):
            for line in Path(path).read_text().splitlines():
                if not line.strip():
                    continue
                o = json.loads(line)
                ds = int(o["deck_seed"])
                if ds not in sp_actions:
                    sp_actions[ds] = [int(x) for x in o["actions"]]

    out, n_bad = [], 0
    for r in rows:
        acts = (e4_actions[r["game_label"]] if r["stratum"] == "e4"
                else sp_actions.get(int(r["deck_seed"])))
        if acts is None:
            n_bad += 1
            continue
        game, board = RR.replay_actions(int(r["deck_seed"]), acts, int(r["ply"]),
                                        game_kwargs=gk)
        if game.string_representation(board) != r["checksum"]:
            n_bad += 1
            continue
        keys = set()
        for act in r["tie_actions_exact"]:
            s1, _ = game.get_next_state(board, int(act))
            keys.add(game.string_representation(s1))
        out.append({
            "rid": f"{r['stratum']}:{r['game_label']}:{r['ply']}",
            "stratum": r["stratum"], "source": r["source"],
            "phase_bucket": r["phase_bucket"], "tercile": r["tercile"],
            "tie_size_exact": r["tie_size_exact"],
            "n_distinct_afterstates": len(keys),
            "all_transposition": len(keys) == 1,
            "dup_fraction": 1.0 - len(keys) / max(1, r["tie_size_exact"]),
        })

    n = len(out)
    if not n:
        print(f"[transposition] no rows for profile={a.profile} "
              f"stratum={a.stratum}", file=sys.stderr)
        return 3
    all_t = sum(1 for o in out if o["all_transposition"])
    any_dup = sum(1 for o in out if o["n_distinct_afterstates"] < o["tie_size_exact"])
    mean_size = sum(o["tie_size_exact"] for o in out) / n
    mean_distinct = sum(o["n_distinct_afterstates"] for o in out) / n
    by_phase = {}
    for ph in ("early", "mid", "late"):
        sub = [o for o in out if o["phase_bucket"] == ph]
        if sub:
            by_phase[ph] = {
                "n": len(sub),
                "all_transposition_pct": round(100 * sum(
                    1 for o in sub if o["all_transposition"]) / len(sub), 2),
                "mean_tie_size": round(sum(o["tie_size_exact"] for o in sub) / len(sub), 3),
                "mean_distinct": round(sum(
                    o["n_distinct_afterstates"] for o in sub) / len(sub), 3)}
    summary = {
        "profile": a.profile, "stratum": a.stratum,
        "n_tied_positions": n, "n_unresolved": n_bad,
        "all_transposition_n": all_t,
        "all_transposition_pct": round(100 * all_t / n, 2),
        "any_duplicate_pct": round(100 * any_dup / n, 2),
        "mean_tie_size": round(mean_size, 3),
        "mean_distinct_afterstates": round(mean_distinct, 3),
        "effective_shrink": round(mean_distinct / mean_size, 4),
        "distinct_hist": dict(sorted(Counter(
            o["n_distinct_afterstates"] for o in out).items())),
        "by_phase": by_phase,
    }
    print(json.dumps(summary, indent=2))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(
            {"summary": summary, "rows": out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
