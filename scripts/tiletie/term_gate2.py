#!/usr/bin/env python3
"""TILE-TIE GATE 2 — the mined-candidate offline discrimination gate
(measurement/tiletie_mining_20260814/GATE2_READ_RULE.md, committed BEFORE this
ran; commit 93db1117).

Attempt 2 of the tile-tie gate, per DESIGN §7.2 of the spent attempt: the menu
is the MINED three (dist_own_meeple+ / dist_centroid- / occ4+), the dev
cross-fit is a SCREEN ONLY (the mining shopped the dev labels), and conviction
is reserved for the never-touched FINAL slice — evaluated exactly once, on the
single pre-named candidate `dist_own_meeple+`, and only if the screen passes.
A screen fail leaves the FINAL slice unburned: `run_gate` takes the FINAL
table as a LOADER CALLABLE that is invoked only inside the screen-passed
branch (enforced by test).

Usage:
    term_gate2.py --run          # screen (+ final iff screen passes) + readout
    term_gate2.py --cost         # the §4 leaf-cost predictor read only
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "scripts" / "measurement_infra")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mine_oracle_sep as M  # noqa: E402
import term_gate as TG       # noqa: E402  (cluster_se, elo_chain)

MEAS = M.MEAS
READ_RULE = "measurement/tiletie_mining_20260814/GATE2_READ_RULE.md"

#: read-rule §2 — exactly three mined candidates, frozen preference order.
MENU = (
    ("dist_own_meeple+", ("dist_own_meeple", 1.0)),
    ("dist_centroid-", ("dist_centroid", -1.0)),
    ("occ4+", ("occ4", 1.0)),
)
FINAL_CANDIDATE = "dist_own_meeple+"     # read-rule §2, pre-named
FOLD_SEED = 2026081403                   # read-rule §3 (fresh seed)
N_FOLDS = 5
BOOT_REPS = 10_000
Z_SCREEN = 2.0
Z_FINAL = 2.0


# --------------------------------------------------------------------------- #
# pure arithmetic (unit-tested)                                                #
# --------------------------------------------------------------------------- #
def captures_for(table, feature: str, sign: float):
    """Per-position (capture_all, pick) under argmax(sign*feature), exact ties
    -> lowest action index; None feature values read as 0 (read-rule §2)."""
    caps, picks = [], []
    for e in table:
        acts, fx, pool = e["acts"], e["fx"], e["pool"]
        best_i, best_key = None, None
        for i in pool:
            v = fx[int(acts[i])].get(feature)
            v = 0.0 if v is None else float(v)
            key = (sign * v, -int(acts[i]))
            if best_key is None or key > best_key:
                best_key, best_i = key, i
        caps.append((e["means"][best_i] - e["means"][0]) * e["scale_all"])
        picks.append(best_i)
    return caps, picks


def crossfit_screen(table, menu=MENU, seed=FOLD_SEED, n_folds=N_FOLDS):
    """Read-rule §3 SCREEN: 5-fold root-clustered cross-fit over the menu."""
    import random
    n = len(table)
    roots = [e["root_id"] for e in table]
    cap = {}
    picks = {}
    for name, (feat, sign) in menu:
        cap[name], picks[name] = captures_for(table, feat, sign)

    uniq_roots = sorted(set(roots))
    rng = random.Random(seed)
    rng.shuffle(uniq_roots)
    fold_of_root = {r: i % n_folds for i, r in enumerate(uniq_roots)}
    fold = [fold_of_root[r] for r in roots]

    heldout = [0.0] * n
    moved = 0
    fold_selected = []
    for k in range(n_folds):
        train_ix = [i for i in range(n) if fold[i] != k]
        best_name, best_mean = None, None
        for name, _ in menu:                 # frozen preference order
            m = math.fsum(cap[name][i] for i in train_ix) / len(train_ix)
            if best_mean is None or m > best_mean:
                best_mean, best_name = m, name
        fold_selected.append(best_name)
        for i in range(n):
            if fold[i] == k:
                heldout[i] = cap[best_name][i]
                if picks[best_name][i] != 0:
                    moved += 1

    mean = math.fsum(heldout) / n
    se = TG.cluster_se(heldout, roots)
    return {
        "statistic": "5-fold root-clustered cross-fit pooled held-out "
                     "capture_all (dev slice) — SCREEN ONLY, contaminated by "
                     "mining-time selection (read-rule §3)",
        "n": n, "n_roots": len(uniq_roots),
        "mean": mean, "se_cluster": se,
        "z": (mean / se if se else float("nan")),
        "fold_selected": fold_selected,
        "heldout_moved_frac": moved / n,
        "per_candidate_mean_insample": {name: math.fsum(cap[name]) / n
                                        for name, _ in menu},
        "realized_2sigma_pts": 2 * se,
    }


def eval_final(table, menu=MENU, candidate=FINAL_CANDIDATE, seed=FOLD_SEED,
               boot_reps=BOOT_REPS):
    """Read-rule §3 FINAL: the pre-named candidate, once, with bootstrap CI."""
    import random
    feat, sign = dict(menu)[candidate]
    caps, picks = captures_for(table, feat, sign)
    roots = [e["root_id"] for e in table]
    n = len(caps)
    mean = math.fsum(caps) / n
    se = TG.cluster_se(caps, roots)

    by_root = defaultdict(list)
    for v, r in zip(caps, roots):
        by_root[r].append(v)
    root_list = list(by_root)
    rng = random.Random(seed)
    boots = []
    for _ in range(boot_reps):
        tot = 0.0
        cnt = 0
        for _ in range(len(root_list)):
            r = root_list[rng.randrange(len(root_list))]
            vs = by_root[r]
            tot += math.fsum(vs)
            cnt += len(vs)
        boots.append(tot / cnt)
    boots.sort()
    return {
        "statistic": f"FINAL untouched-slice capture_all, candidate "
                     f"`{candidate}`, evaluated exactly once",
        "candidate": candidate,
        "n": n, "n_roots": len(root_list),
        "mean": mean, "se_cluster": se,
        "z": (mean / se if se else float("nan")),
        "ci95_boot": [boots[int(0.025 * boot_reps)],
                      boots[int(0.975 * boot_reps)]],
        "moved_frac": sum(1 for p in picks if p != 0) / n,
        "elo_extrapolated": TG.elo_chain(mean),
        "elo_note": "§4.3-chain extrapolation, ±1.6× divisor bracket applies",
    }


def adjudicate(z_dev: float, z_fin) -> str:
    """Read-rule §5 branches (G2-0 is handled by the caller)."""
    if z_dev <= -Z_SCREEN:
        return "G2-HARMFUL"
    if z_dev < Z_SCREEN:
        return "G2-SCREEN-FAIL"
    assert z_fin is not None, "screen passed but FINAL was not evaluated"
    if z_fin <= 0:
        return "G2-FAIL-FINAL"
    if z_fin < Z_FINAL:
        return "G2-WEAK"
    return "G2-PASS"


def run_gate(dev_table, final_table_loader, menu=MENU,
             candidate=FINAL_CANDIDATE):
    """The gate. `final_table_loader` is a CALLABLE invoked only if the screen
    passes — a screen fail provably never touches the FINAL slice."""
    screen = crossfit_screen(dev_table, menu)
    z_dev = screen["z"]
    final = None
    if z_dev >= Z_SCREEN:
        final = eval_final(final_table_loader(), menu, candidate)
    branch = adjudicate(z_dev, final["z"] if final else None)
    return {"screen": screen, "final": final, "branch": branch}


# --------------------------------------------------------------------------- #
# cost (read-rule §4, informational)                                           #
# --------------------------------------------------------------------------- #
def cmd_cost(n_positions: int = 60, reps: int = 5) -> dict:
    """Predictor: (leaf + candidate features) / leaf, median over trials, on
    replayed corpus afterstates (arm 0 of the first n dev walled positions)."""
    import time
    import chain_census as CC
    CC.prepare_env("walled")
    import root_replay as RR

    per = TG.load_per_position()
    arms = json.loads(TG.ARMS_JSON.read_text())
    hold = M.load_holdout_roots()
    rids = sorted(r for r, row in per.items()
                  if row["rules_profile"] == "walled"
                  and row["root_id"] not in hold)[:n_positions]
    acts_ix = TG.load_actions_index(set(rids))

    leaf, cfg, hashes, bag_close = CC.build_leaf()

    states = []          # (state, seat, placed_cell, meeple_cells)
    for rid in rids:
        row = acts_ix[rid]
        actions = ([int(x) for x in row["actions"]] if "actions" in row else
                   [int(x) for x in json.loads(
                       Path(row["archive_path"]).read_text())["actions"]])
        game, board = RR.replay_actions(int(row["deck_seed"]), actions,
                                        int(row["ply"]))
        if game.string_representation(board) != row["checksum"]:
            raise SystemExit(f"checksum mismatch on {rid}")
        p = int(row["root_player"])
        act = int(arms[rid]["arms"][0])
        b1, _ = game.get_next_state(board, act)
        brd0, brd1 = board.state.board, b1.state.board
        placed = None
        for r in range(len(brd0)):
            for c in range(len(brd0[0])):
                if brd0[r][c] is None and brd1[r][c] is not None:
                    placed = (r, c)
        cells = set()
        for mp in b1.state.placed_meeples[p]:
            co = mp.coordinate_with_side.coordinate
            cells.add((co.row, co.column))
        states.append((b1.state, p, placed, cells))

    def feature(st, p, placed, cells):
        pr, pc = placed
        # dist_own_meeple (the FINAL candidate) + occ4 + centroid, i.e. the
        # full menu's marginal work, conservatively including the meeple scan
        dmin = min((abs(pr - r) + abs(pc - c) for r, c in cells), default=0)
        brd = st.board
        H = len(brd)
        W = len(brd[0])
        o4 = 0
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            r2, c2 = pr + dr, pc + dc
            if 0 <= r2 < H and 0 <= c2 < W and brd[r2][c2] is not None:
                o4 += 1
        return dmin + o4

    ratios = []
    for _ in range(reps):
        t0 = time.perf_counter()
        for st, p, placed, cells in states:
            leaf(st, p)
        t_leaf = time.perf_counter() - t0
        t0 = time.perf_counter()
        for st, p, placed, cells in states:
            leaf(st, p)
            feature(st, p, placed, cells)
        t_both = time.perf_counter() - t0
        ratios.append(t_both / t_leaf)
    ratios.sort()
    out = {"trials": ratios, "median_ratio": ratios[len(ratios) // 2],
           "n_states": len(states),
           "note": "predictor: (leaf + menu features)/(leaf), python flat "
                   "leaf, quiet box; read-rule §4"}
    print(json.dumps(out, indent=1))
    return out


# --------------------------------------------------------------------------- #
# orchestration + readout                                                      #
# --------------------------------------------------------------------------- #
def _g0(problems, excluded_pool):
    return {"n_problems": len(problems), "problems": problems[:10],
            "n_excluded_pool_lt2": len(excluded_pool)}


def cmd_run(workers: int) -> int:
    dev_table, dev_problems, dev_excluded = M.build_table("dev")
    g0 = {"dev": _g0(dev_problems, dev_excluded)}
    if dev_problems or len(dev_excluded) > 5:
        branch = "G2-0 UNREADABLE"
        result = {"schema": "carcassonne-tiletie-gate2/v1",
                  "read_rule": READ_RULE, "g0": g0, "branch": branch}
        (MEAS / "GATE2_READOUT.json").write_text(json.dumps(result, indent=1))
        print(json.dumps({"branch": branch, "g0": g0}, indent=1))
        return 1

    def final_loader():
        # label-free feature extraction for the FINAL slice happens only here,
        # then the oracle records for holdout roots are opened for the first
        # and only time.
        for prof in ("walled", "fixed_v1", "app_aug2"):
            rc = subprocess.call(
                [sys.executable, str(HERE / "mine_oracle_sep.py"),
                 "--extract", "--profile", prof, "--slice", "final",
                 "--workers", str(workers)])
            if rc:
                raise SystemExit(f"final extract failed for {prof}")
        final_table, fin_problems, fin_excluded = M.build_table("final")
        g0["final"] = _g0(fin_problems, fin_excluded)
        if fin_problems or len(fin_excluded) > 5:
            raise SystemExit(f"G2-0 UNREADABLE on final slice: {g0['final']}")
        return final_table

    r = run_gate(dev_table, final_loader)
    cost = cmd_cost()

    result = {
        "schema": "carcassonne-tiletie-gate2/v1",
        "read_rule": READ_RULE,
        "menu": [name for name, _ in MENU],
        "final_candidate": FINAL_CANDIDATE,
        "fold_seed": FOLD_SEED, "n_folds": N_FOLDS,
        "bootstrap_reps": BOOT_REPS,
        "g0": g0,
        "branch": r["branch"],
        "screen_dev": r["screen"],
        "final": r["final"],
        "final_slice_burned": r["final"] is not None,
        "cost": cost,
        "ceiling_context": {
            "dev_honest_ceiling": 0.1986, "pooled_S2b_all": 0.2340,
            "note": "read-rule §3; no rule can capture more in expectation",
        },
    }
    (MEAS / "GATE2_READOUT.json").write_text(json.dumps(result, indent=1))
    _write_md(result)
    print(json.dumps({"branch": r["branch"], "z_dev": r["screen"]["z"],
                      "final": (None if r["final"] is None
                                else {"mean": r["final"]["mean"],
                                      "z": r["final"]["z"]})}, indent=1))
    return 0


def _write_md(res: dict) -> None:
    s = res["screen_dev"]
    lines = [
        "# TILE-TIE GATE 2 — READOUT",
        "",
        f"**Read-rule: [GATE2_READ_RULE.md](GATE2_READ_RULE.md) (committed "
        f"before this ran). Branch: `{res['branch']}`.** Generated by "
        "`scripts/tiletie/term_gate2.py --run`; machine twin "
        "`GATE2_READOUT.json`. 0 games; no results.csv row, no band, no "
        "claim id.",
        "",
        "## G0 integrity",
        "",
        f"- dev: problems **{res['g0']['dev']['n_problems']}**, pool<2 "
        f"exclusions **{res['g0']['dev']['n_excluded_pool_lt2']}**"
        + (f" · final: problems **{res['g0']['final']['n_problems']}**, "
           f"pool<2 **{res['g0']['final']['n_excluded_pool_lt2']}**"
           if "final" in res["g0"] else " · final slice: NOT OPENED"),
        "",
        "## SCREEN (dev cross-fit — contaminated by mining-time selection, "
        "never confirmatory)",
        "",
        "| statistic | value |",
        "|---|---|",
        f"| mean (held-out, pooled) | **{s['mean']:+.4f}** |",
        f"| cluster se | {s['se_cluster']:.4f} |",
        f"| z_dev | **{s['z']:+.2f}** (screen bar +2.0) |",
        f"| fold-selected | {', '.join(s['fold_selected'])} |",
        f"| held-out pick moved | {s['heldout_moved_frac']:.1%} |",
        f"| realized 2σ resolution | ±{s['realized_2sigma_pts']:.4f} pts |",
        "",
        "In-sample per-candidate means (disclosed, curse-adjacent): "
        + ", ".join(f"`{k}` {v:+.4f}"
                    for k, v in s["per_candidate_mean_insample"].items()),
        "",
    ]
    if res["final"] is None:
        lines += [
            "## FINAL slice",
            "",
            "**NOT EVALUATED — the screen did not pass; the 211-position "
            "holdout stays unburned for any future attempt.**",
        ]
    else:
        f = res["final"]
        lines += [
            "## FINAL (untouched slice, evaluated exactly once — the only "
            "confirmatory number)",
            "",
            "| statistic | value |",
            "|---|---|",
            f"| candidate | `{f['candidate']}` (pre-named) |",
            f"| n | {f['n']} over {f['n_roots']} roots |",
            f"| mean | **{f['mean']:+.4f}** |",
            f"| cluster se | {f['se_cluster']:.4f} |",
            f"| z_fin | **{f['z']:+.2f}** (bar +2.0) |",
            f"| 95% CI (root bootstrap) | [{f['ci95_boot'][0]:+.4f}, "
            f"{f['ci95_boot'][1]:+.4f}] |",
            f"| moved vs incumbent | {f['moved_frac']:.1%} |",
            f"| elo (§4.3 extrapolation, ±1.6× bracket) | "
            f"{f['elo_extrapolated']:+.1f} |",
        ]
    c = res["cost"]
    lines += [
        "",
        "## Cost (read-rule §4, predictor)",
        "",
        f"median ratio (leaf+features)/(leaf) = **{c['median_ratio']:.4f}** "
        f"over {c['n_states']} states × {len(c['trials'])} trials "
        f"({', '.join(f'{t:.3f}' for t in c['trials'])}).",
        "",
        f"**Ceiling context (mandatory):** honest dev ceiling "
        f"+{res['ceiling_context']['dev_honest_ceiling']:.4f}, pooled S2b "
        f"+{res['ceiling_context']['pooled_S2b_all']:.4f} pts/tied ply.",
        "",
    ]
    (MEAS / "GATE2_READOUT.md").write_text("\n".join(lines))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--cost", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args(argv)
    if a.run:
        return cmd_run(a.workers)
    if a.cost:
        cmd_cost()
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
