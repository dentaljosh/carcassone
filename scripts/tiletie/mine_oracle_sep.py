#!/usr/bin/env python3
"""TILE-TIE ORACLE-SEPARATION MINING — phase 1 of the DESIGN §7.2 re-open route
(measurement/tiletie_mining_20260814/).

`measurement/tiletie_term_20260814/DESIGN.md` §7.2 names this route after the
guess-first menu G-FAILed: characterize what ACTUALLY separates the oracle-best
arm from the incumbent (lowest-index) pick inside leaf-tied sets, board-level,
and only then hand-craft. This module is the mining instrument; the phase-2
gate lives in `term_gate2.py` and is licensed only by a read-rule committed
AFTER the mining report.

Corpus-reuse discipline (the §7.1 warning made binding):

  * ``--split`` designates ~30%% of the 399 roots (seed ``HOLDOUT_SEED``,
    deterministic shuffle) as the FINAL slice and writes
    ``HOLDOUT_ROOTS.json``. Committed BEFORE any mining statistic exists —
    the git history is the proof of ordering.
  * Mining NEVER reads oracle values for holdout roots: the oracle loader
    skips their record files BY FILENAME (records are named ``<rid>.json``,
    verified) so holdout labels are never even parsed, and the analyzer
    asserts the joined table contains no holdout rid.
  * ``--extract`` is label-free (oracle values untouched) and, in mining mode,
    runs on the dev slice only. `term_gate2.py` reuses the same worker for the
    final slice at gate time.

⚠️ EVERY statistic emitted here is EXPLORATORY. View A conditions on
oracle-vs-incumbent disagreement (selection bias by construction); view B is
in-sample single-feature shopping on the dev slice; nothing here carries a
confirmatory p-value. The only confirmatory number this program ever produces
is `term_gate2.py`'s one-shot FINAL-slice read.

Usage:
    mine_oracle_sep.py --split
    mine_oracle_sep.py --extract --profile walled --workers 12 [--slice dev|final]
    mine_oracle_sep.py --analyze
    mine_oracle_sep.py --run            # 3 dev extracts + analyze
"""
from __future__ import annotations

import argparse
import glob
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

import term_gate as TG  # noqa: E402  (corpus paths, cluster_se, plan index)

MEAS = REPO / "measurement" / "tiletie_mining_20260814"
HOLDOUT_PATH = MEAS / "HOLDOUT_ROOTS.json"
HOLDOUT_SEED = 2026081402          # distinct from the spent gate's 20260814
HOLDOUT_FRAC = 0.30

#: every numeric per-arm feature the extractor emits, in a frozen order.
FEATURE_NAMES = (
    # placement geometry (root board)
    "occ4", "occ8", "dist_centroid", "bbox_expand",
    "dist_own_meeple", "dist_opp_meeple", "adj8_own_meeple", "adj8_opp_meeple",
    # city structure (root-vs-afterstate diff)
    "jc_n", "jc_own", "jc_opp", "jc_cont", "jc_new",
    "cc_own", "cc_opp", "cc_uncl",
    "d_open_c_own", "d_open_c_opp", "big_c_own_d",
    # road structure
    "jr_n", "jr_own", "jr_opp", "jr_new", "cr_own", "cr_opp",
    "d_open_r_own", "d_open_r_opp",
    # farm structure
    "jf_n", "jf_contest", "d_ffc_own", "d_ffc_opp",
    # cloister
    "adj8_own_clo", "adj8_opp_clo",
    # the spent gate's four (contrast set)
    "d_city", "d_road", "f_perim", "f_lib",
)


# --------------------------------------------------------------------------- #
# split                                                                        #
# --------------------------------------------------------------------------- #
def make_split(roots, seed: int = HOLDOUT_SEED, frac: float = HOLDOUT_FRAC):
    """Deterministic (seeded-shuffle) root split -> (dev_roots, holdout_roots),
    both sorted. Pure; no labels involved."""
    import random
    uniq = sorted(set(roots))
    rng = random.Random(seed)
    rng.shuffle(uniq)
    n_hold = int(round(frac * len(uniq)))
    hold = sorted(uniq[:n_hold])
    dev = sorted(uniq[n_hold:])
    return dev, hold


def load_holdout_roots() -> set:
    d = json.loads(HOLDOUT_PATH.read_text())
    return set(d["holdout_roots"])


def cmd_split() -> int:
    per = TG.load_per_position()          # rid -> row; only root_id is used
    roots = [row["root_id"] for row in per.values()]
    dev, hold = make_split(roots)
    MEAS.mkdir(parents=True, exist_ok=True)
    n_pos_hold = sum(1 for row in per.values() if row["root_id"] in set(hold))
    HOLDOUT_PATH.write_text(json.dumps({
        "schema": "carcassonne-tiletie-gate2-holdout/v1",
        "seed": HOLDOUT_SEED, "frac": HOLDOUT_FRAC,
        "n_roots": len(dev) + len(hold),
        "n_holdout_roots": len(hold), "n_dev_roots": len(dev),
        "n_holdout_positions": n_pos_hold,
        "n_dev_positions": len(per) - n_pos_hold,
        "holdout_roots": hold,
        "note": "FINAL slice. Mining (mine_oracle_sep.py) never reads oracle "
                "values for these roots; evaluated exactly once by "
                "term_gate2.py on the single pre-named candidate of "
                "GATE2_READ_RULE.md, and only if the dev screen passes.",
    }, indent=1))
    print(f"[split] {len(dev)} dev roots / {len(hold)} holdout roots "
          f"({n_pos_hold} holdout positions) -> {HOLDOUT_PATH}")
    return 0


# --------------------------------------------------------------------------- #
# feature extraction (label-free)                                              #
# --------------------------------------------------------------------------- #
def classify_owner(counts: dict, root, p: int) -> str:
    """Strict weighted-majority ownership of a component for player p:
    'own' / 'opp' / 'cont' (contested) / 'un' (unclaimed)."""
    e = counts.get(root)
    if not e or (e[0] == 0 and e[1] == 0):
        return "un"
    if e[p] > e[1 - p]:
        return "own"
    if e[p] < e[1 - p]:
        return "opp"
    return "cont"


def _joins(side_root_after: dict, root_positions_after: dict,
           side_root_root: dict, placed) -> list:
    """For the component class keyed by (r, c, side/key...) tuples whose first
    two elements are the cell: every after-component touching the placed cell,
    as (after_root, set_of_joined_root_components)."""
    pr, pc = placed
    after_roots = {v for k, v in side_root_after.items()
                   if k[0] == pr and k[1] == pc}
    out = []
    for ar in after_roots:
        joined = set()
        for k in root_positions_after[ar]:
            if (k[0], k[1]) == (pr, pc):
                continue
            r0 = side_root_root.get(k)
            if r0 is not None:
                joined.add(r0)
        out.append((ar, joined))
    return out


def _extract_one_rich(args):
    """One corpus position -> rich per-arm afterstate-diff features.
    Runs in a fork Pool worker; profile env was latched by the parent."""
    (rid, deck_seed, ply, root_player, checksum, actions, arm_actions, gk) = args
    import root_replay as RR
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    from carcassonne_ai import flat_leaf

    game, board = RR.replay_actions(deck_seed, actions, ply, game_kwargs=gk)
    if game.string_representation(board) != checksum:
        return {"rid": rid, "error": "checksum_mismatch"}
    st0 = board.state
    p = int(root_player)
    d0 = flat_leaf.decompose(st0)
    c0_city, c0_road, c0_farm, _ = flat_leaf._jr_counts(st0, d0)
    brd0 = st0.board
    H = len(brd0)
    W = len(brd0[0]) if H else 0

    occ = [(r, c) for r in range(H) for c in range(W) if brd0[r][c] is not None]
    cen_r = sum(r for r, _ in occ) / len(occ)
    cen_c = sum(c for _, c in occ) / len(occ)
    rmin = min(r for r, _ in occ); rmax = max(r for r, _ in occ)
    cmin = min(c for _, c in occ); cmax = max(c for _, c in occ)

    meeple_cells = {0: set(), 1: set()}
    clo_cells = {0: set(), 1: set()}
    for pl in (0, 1):
        for mp in st0.placed_meeples[pl]:
            cws = mp.coordinate_with_side
            r, c = cws.coordinate.row, cws.coordinate.column
            meeple_cells[pl].add((r, c))
            tile = brd0[r][c]
            if tile is not None:
                t = tile.get_type(cws.side)
                if t == TerrainType.CHAPEL or t == TerrainType.FLOWERS:
                    clo_cells[pl].add((r, c))

    def open_sums(d, counts):
        """(own, opp) sums of open-cell counts over unfinished city comps."""
        so = sp = 0
        for root, open_n in d.city_root_open_n.items():
            if d.city_root_finished.get(root):
                continue
            o = classify_owner(counts, root, p)
            if o == "own":
                so += open_n
            elif o == "opp":
                sp += open_n
        return so, sp

    def open_sums_road(d, counts):
        so = sp = 0
        for root, open_n in d.road_root_open_n.items():
            if d.road_root_finished.get(root):
                continue
            o = classify_owner(counts, root, p)
            if o == "own":
                so += open_n
            elif o == "opp":
                sp += open_n
        return so, sp

    def big_own_city(d, counts):
        best = 0
        for root, coords in d.city_root_coords.items():
            if d.city_root_finished.get(root):
                continue
            if classify_owner(counts, root, p) == "own":
                best = max(best, len(coords))
        return best

    def ffc_sums(d, counts):
        so = sp = 0
        for root, fc in d.farm_root_finished_cities.items():
            o = classify_owner(counts, root, p)
            if o == "own":
                so += fc
            elif o == "opp":
                sp += fc
        return so, sp

    r_oc_own, r_oc_opp = open_sums(d0, c0_city)
    r_or_own, r_or_opp = open_sums_road(d0, c0_road)
    r_big = big_own_city(d0, c0_city)
    r_ffc_own, r_ffc_opp = ffc_sums(d0, c0_farm)

    feats = []
    farm_key_misses = 0
    for act in arm_actions:
        b1, _ = game.get_next_state(board, int(act))
        st1 = b1.state
        brd1 = st1.board
        placed = None
        for r in range(H):
            row0, row1 = brd0[r], brd1[r]
            for c in range(W):
                if row0[c] is None and row1[c] is not None:
                    placed = (r, c)
                    break
            if placed:
                break
        if placed is None:
            return {"rid": rid, "error": f"no_placed_cell_arm{act}"}
        pr, pc = placed

        d1 = flat_leaf.decompose(st1)
        c1_city, c1_road, c1_farm, _ = flat_leaf._jr_counts(st1, d1)

        occ4 = occ8 = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                r2, c2 = pr + dr, pc + dc
                if 0 <= r2 < H and 0 <= c2 < W and brd0[r2][c2] is not None:
                    occ8 += 1
                    if dr == 0 or dc == 0:
                        occ4 += 1

        def min_dist(cells):
            if not cells:
                return None
            return min(abs(pr - r2) + abs(pc - c2) for r2, c2 in cells)

        def adj8(cells):
            return sum(1 for r2, c2 in cells
                       if abs(pr - r2) <= 1 and abs(pc - c2) <= 1)

        # ---- city joins/closures ---------------------------------------- #
        jc_own = jc_opp = jc_cont = jc_new = 0
        cc_own = cc_opp = cc_uncl = 0
        seen_city_roots = set()
        for ar, joined in _joins(d1.city_side_root, d1.city_root_positions,
                                 d0.city_side_root, placed):
            if not joined:
                jc_new += 1
            for rc in joined:
                if rc in seen_city_roots:
                    continue
                seen_city_roots.add(rc)
                o = classify_owner(c0_city, rc, p)
                if o == "own":
                    jc_own += 1
                elif o == "opp":
                    jc_opp += 1
                elif o == "cont":
                    jc_cont += 1
                if (not d0.city_root_finished.get(rc)
                        and d1.city_root_finished.get(ar)):
                    if o == "own":
                        cc_own += 1
                    elif o in ("opp", "cont"):
                        cc_opp += 1
                    else:
                        cc_uncl += 1
        jc_n = len(seen_city_roots)

        # ---- road joins/closures ---------------------------------------- #
        jr_own = jr_opp = jr_new = 0
        cr_own = cr_opp = 0
        seen_road_roots = set()
        for ar, joined in _joins(d1.road_side_root, d1.road_root_positions,
                                 d0.road_side_root, placed):
            if not joined:
                jr_new += 1
            for rc in joined:
                if rc in seen_road_roots:
                    continue
                seen_road_roots.add(rc)
                o = classify_owner(c0_road, rc, p)
                if o == "own":
                    jr_own += 1
                elif o == "opp":
                    jr_opp += 1
                if (not d0.road_root_finished.get(rc)
                        and d1.road_root_finished.get(ar)):
                    if o == "own":
                        cr_own += 1
                    elif o in ("opp", "cont"):
                        cr_opp += 1
        jr_n = len(seen_road_roots)

        # ---- farm joins (stable key: (r, c, farmer_positions[0])) -------- #
        after_farm_roots = {v for k, v in d1.farm_pos0_root.items()
                            if k[0] == pr and k[1] == pc}
        joined_farms = set()
        for k, v in d1.farm_pos0_root.items():
            if v in after_farm_roots and (k[0], k[1]) != (pr, pc):
                r0 = d0.farm_pos0_root.get(k)
                if r0 is None:
                    farm_key_misses += 1
                else:
                    joined_farms.add(r0)
        jf_n = len(joined_farms)
        owners = {classify_owner(c0_farm, rf, p) for rf in joined_farms}
        jf_contest = 1 if ("own" in owners and "opp" in owners) else 0

        a_oc_own, a_oc_opp = open_sums(d1, c1_city)
        a_or_own, a_or_opp = open_sums_road(d1, c1_road)
        a_ffc_own, a_ffc_opp = ffc_sums(d1, c1_farm)

        # ---- the spent gate's four (contrast) ---------------------------- #
        from wingedsheep.carcassonne.objects.terrain_type import TerrainType as TT
        wc = flat_leaf._tiletie_wallin(st1, d1, d1.city_side_root,
                                       d1.city_root_positions,
                                       d1.city_root_finished,
                                       d1.city_root_open_n, TT.CITY)
        wr = flat_leaf._tiletie_wallin(st1, d1, d1.road_side_root,
                                       d1.road_root_positions,
                                       d1.road_root_finished,
                                       d1.road_root_open_n, TT.ROAD)
        perim = 0
        n_open = 0
        H1 = len(brd1)
        W1 = len(brd1[0]) if H1 else 0
        for pos in st1.open_positions:
            er, ec = pos.row, pos.column
            n_open += 1
            if er > 0 and brd1[er - 1][ec] is not None:
                perim += 1
            if er + 1 < H1 and brd1[er + 1][ec] is not None:
                perim += 1
            if ec > 0 and brd1[er][ec - 1] is not None:
                perim += 1
            if ec + 1 < W1 and brd1[er][ec + 1] is not None:
                perim += 1

        feats.append({
            "action": int(act),
            "occ4": occ4, "occ8": occ8,
            "dist_centroid": abs(pr - cen_r) + abs(pc - cen_c),
            "bbox_expand": 1 if (pr < rmin or pr > rmax
                                 or pc < cmin or pc > cmax) else 0,
            "dist_own_meeple": min_dist(meeple_cells[p]),
            "dist_opp_meeple": min_dist(meeple_cells[1 - p]),
            "adj8_own_meeple": adj8(meeple_cells[p]),
            "adj8_opp_meeple": adj8(meeple_cells[1 - p]),
            "jc_n": jc_n, "jc_own": jc_own, "jc_opp": jc_opp,
            "jc_cont": jc_cont, "jc_new": jc_new,
            "cc_own": cc_own, "cc_opp": cc_opp, "cc_uncl": cc_uncl,
            "d_open_c_own": a_oc_own - r_oc_own,
            "d_open_c_opp": a_oc_opp - r_oc_opp,
            "big_c_own_d": big_own_city(d1, c1_city) - r_big,
            "jr_n": jr_n, "jr_own": jr_own, "jr_opp": jr_opp, "jr_new": jr_new,
            "cr_own": cr_own, "cr_opp": cr_opp,
            "d_open_r_own": a_or_own - r_or_own,
            "d_open_r_opp": a_or_opp - r_or_opp,
            "jf_n": jf_n, "jf_contest": jf_contest,
            "d_ffc_own": a_ffc_own - r_ffc_own,
            "d_ffc_opp": a_ffc_opp - r_ffc_opp,
            "adj8_own_clo": adj8(clo_cells[p]),
            "adj8_opp_clo": adj8(clo_cells[1 - p]),
            "d_city": wc[1 - p] - wc[p],
            "d_road": wr[1 - p] - wr[p],
            "f_perim": float(perim),
            "f_lib": float(n_open),
        })
    return {"rid": rid, "farm_key_misses": farm_key_misses, "features": feats}


def cmd_extract(profile: str, workers: int, which: str) -> int:
    """Label-free rich-feature extraction for one rules profile.
    which='dev' (mining) or 'final' (gate time, term_gate2 only)."""
    import chain_census as CC
    CC.prepare_env(profile)                    # BEFORE any carcassonne_ai import
    from carcassonne_ai import rules_profile as RP
    prof = RP.activate(profile)
    gk = prof.game_kwargs() or None

    per = TG.load_per_position()
    arms = json.loads(TG.ARMS_JSON.read_text())
    hold = load_holdout_roots()
    if which == "dev":
        rids = [r for r, row in per.items()
                if row["rules_profile"] == profile and row["root_id"] not in hold]
    elif which == "final":
        rids = [r for r, row in per.items()
                if row["rules_profile"] == profile and row["root_id"] in hold]
    else:
        raise SystemExit(f"unknown --slice {which}")
    acts = TG.load_actions_index(set(rids))

    jobs = []
    for rid in sorted(rids):
        row = acts[rid]
        if "actions" in row:
            actions = [int(x) for x in row["actions"]]
        else:
            actions = [int(x) for x in
                       json.loads(Path(row["archive_path"]).read_text())["actions"]]
        jobs.append((rid, int(row["deck_seed"]), int(row["ply"]),
                     int(row["root_player"]), row["checksum"], actions,
                     arms[rid]["arms"], gk))

    from multiprocessing import Pool
    out_path = MEAS / f"mining_features_{which}_{profile}.jsonl"
    n_err = 0
    with Pool(workers) as pool, open(out_path, "w") as fh:
        for res in pool.imap_unordered(_extract_one_rich, jobs, chunksize=4):
            if "error" in res:
                n_err += 1
                print(f"[extract:{which}:{profile}] {res['rid']}: {res['error']}",
                      file=sys.stderr)
            fh.write(json.dumps(res) + "\n")
    print(f"[extract:{which}:{profile}] {len(jobs)} positions, {n_err} errors "
          f"-> {out_path}")
    return 1 if n_err else 0


# --------------------------------------------------------------------------- #
# oracle loading with the holdout firewall                                     #
# --------------------------------------------------------------------------- #
def load_oracle_means_slice(per_slice: dict, arms: dict):
    """Exactly `term_gate.load_oracle_means`, but record files whose rid is not
    in `per_slice` are skipped BY FILENAME — holdout labels are never parsed
    when `per_slice` is the dev slice."""
    recs = defaultdict(dict)
    for f in glob.glob(f"{TG.RECORDS_ROOT}/*/*/records/*.json"):
        rid = Path(f).stem
        if rid not in per_slice:
            continue
        leg = f.split("/")[-3]
        recs[rid][leg] = json.loads(Path(f).read_text())
    out = {}
    problems = []
    for rid in per_slice:
        a = arms[rid]["arms"]
        got = recs.get(rid, {})
        if len(got) != len(a) - 1:
            problems.append((rid, "missing_legs"))
            continue
        ok = all(got[f"leg{i}"]["pick_b"] == a[i]
                 and got[f"leg{i}"]["pick_a"] == a[0]
                 for i in range(1, len(a)))
        if not ok:
            problems.append((rid, "arm_mismatch"))
            continue
        va = got["leg1"]["values_a"]
        means = [math.fsum(va) / len(va)]
        for i in range(1, len(a)):
            vb = got[f"leg{i}"]["values_b"]
            means.append(math.fsum(vb) / len(vb))
        out[rid] = means
    return out, problems


def build_table(which: str):
    """Join per_position + arms + rich features + oracle means for one slice.
    Returns (table, problems, excluded_pool)."""
    per = TG.load_per_position()
    arms = json.loads(TG.ARMS_JSON.read_text())
    hold = load_holdout_roots()
    if which == "dev":
        per_slice = {r: row for r, row in per.items()
                     if row["root_id"] not in hold}
    else:
        per_slice = {r: row for r, row in per.items() if row["root_id"] in hold}

    feats = {}
    n_checksum_err = 0
    for profile in ("walled", "fixed_v1", "app_aug2"):
        pth = MEAS / f"mining_features_{which}_{profile}.jsonl"
        if not pth.exists():
            raise SystemExit(f"REFUSING: {pth} missing — run --extract first")
        for line in pth.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "error" in r:
                n_checksum_err += 1
                continue
            feats[r["rid"]] = {f["action"]: f for f in r["features"]}

    oracle, problems = load_oracle_means_slice(per_slice, arms)
    if n_checksum_err:
        problems.append(("<extract>", f"{n_checksum_err}_checksum_errors"))

    excluded_pool = []
    table = []
    for rid, row in sorted(per_slice.items()):
        a = arms[rid]
        acts = a["arms"]
        if rid not in oracle or rid not in feats:
            problems.append((rid, "not_joined"))
            continue
        fx = feats[rid]
        if set(fx) != set(int(x) for x in acts):
            problems.append((rid, "feature_arm_mismatch"))
            continue
        pool = list(range(len(acts)))
        champ_ix = a.get("champ_arm_index")
        if a.get("champ_outside_tieset") and champ_ix is not None:
            pool = [i for i in pool if i != champ_ix]
        if len(pool) < 2:
            excluded_pool.append(rid)
            continue
        table.append({
            "rid": rid, "root_id": row["root_id"], "stratum": row["stratum"],
            "phase": row["phase_bucket"], "scale_all": row["scale_all"],
            "acts": acts, "means": oracle[rid], "pool": pool,
            "champ_ix": champ_ix, "fx": fx,
        })
    # the firewall assertion
    for e in table:
        if which == "dev":
            assert e["root_id"] not in hold, "holdout root leaked into dev table"
        else:
            assert e["root_id"] in hold, "dev root leaked into final table"
    return table, problems, excluded_pool


# --------------------------------------------------------------------------- #
# mining statistics (dev slice only, EXPLORATORY)                              #
# --------------------------------------------------------------------------- #
def _summ(values, clusters):
    n = len(values)
    m = math.fsum(values) / n
    se = (TG.cluster_se(values, clusters)
          if len(set(clusters)) > 1 else float("nan"))
    return {"n": n, "mean": m, "se_cluster": se,
            "z": (m / se if se else float("nan"))}


def view_a(table):
    """Oracle-best vs incumbent afterstate diffs, on disagreement rows only.
    SELECTION-BIASED BY CONSTRUCTION (conditions on disagreement)."""
    rows = []
    for e in table:
        pool = e["pool"]
        best = max(pool, key=lambda i: (e["means"][i], -i))
        if best == 0:
            continue
        f_best = e["fx"][int(e["acts"][best])]
        f_inc = e["fx"][int(e["acts"][0])]
        prize = (e["means"][best] - e["means"][0]) * e["scale_all"]
        rows.append((e, f_best, f_inc, prize))

    out = {"n_disagree": len(rows), "n_total": len(table),
           "mean_prize_all_scale": (math.fsum(r[3] for r in rows) / len(rows))
           if rows else None,
           "features": {}}
    for name in FEATURE_NAMES:
        deltas, clusters, phases = [], [], []
        n_none = 0
        for e, fb, fi, _ in rows:
            a, b = fb.get(name), fi.get(name)
            if a is None or b is None:
                n_none += 1
                continue
            deltas.append(a - b)
            clusters.append(e["root_id"])
            phases.append(e["phase"])
        if not deltas:
            continue
        d = _summ(deltas, clusters)
        nz = [x for x in deltas if x != 0]
        d.update({
            "n_skipped_none": n_none,
            "median": sorted(deltas)[len(deltas) // 2],
            "frac_nonzero": len(nz) / len(deltas),
            "frac_pos_of_nonzero": (sum(1 for x in nz if x > 0) / len(nz))
            if nz else None,
        })
        for ph in ("early", "mid", "late"):
            ix = [i for i, x in enumerate(phases) if x == ph]
            if len(ix) >= 5:
                d[f"mean_{ph}"] = math.fsum(deltas[i] for i in ix) / len(ix)
        out["features"][name] = d
    return out


def feature_capture(table, name: str, sign: int):
    """The gate statistic for a single feature used as the pick rule:
    argmax(sign*f) over the pool, exact ties -> lowest index.
    None feature values are treated as 0 (encode 'no meeple on board')."""
    caps, clusters, moved = [], [], 0
    for e in table:
        acts, fx, pool = e["acts"], e["fx"], e["pool"]
        best_i, best_key = None, None
        for i in pool:
            v = fx[int(acts[i])].get(name)
            v = 0.0 if v is None else float(v)
            key = (sign * v, -int(acts[i]))
            if best_key is None or key > best_key:
                best_key, best_i = key, i
        c = (e["means"][best_i] - e["means"][0]) * e["scale_all"]
        caps.append(c)
        clusters.append(e["root_id"])
        if best_i != 0:
            moved += 1
    d = _summ(caps, clusters)
    d["moved_frac"] = moved / len(table)
    return d


def view_b(table):
    """In-sample single-feature captures on the dev slice (both signs).
    EXPLORATORY feature shopping — never confirmatory."""
    out = {}
    for name in FEATURE_NAMES:
        for sign, tag in ((1, "+"), (-1, "-")):
            out[f"{name}{tag}"] = feature_capture(table, name, sign)
    return out


def view_c(table):
    """Within-tied-set centered correlation feature vs oracle mean, pooled
    over positions (each scored arm one point). Descriptive."""
    out = {}
    for name in FEATURE_NAMES:
        sxy = sxx = syy = 0.0
        n_pts = 0
        for e in table:
            pool = e["pool"]
            vals = []
            for i in pool:
                v = e["fx"][int(e["acts"][i])].get(name)
                vals.append(0.0 if v is None else float(v))
            ys = [e["means"][i] for i in pool]
            mx = math.fsum(vals) / len(vals)
            my = math.fsum(ys) / len(ys)
            for v, y in zip(vals, ys):
                sxy += (v - mx) * (y - my)
                sxx += (v - mx) ** 2
                syy += (y - my) ** 2
            n_pts += len(pool)
        r = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0
        out[name] = {"r_within": r,
                     "slope": (sxy / sxx if sxx > 0 else 0.0),
                     "n_points": n_pts}
    return out


#: derived (composite) features, computed by the analyzer from the stored
#: per-arm features. As exploratory as everything else here.
DERIVED = {
    # "toward his meeples, away from mine" (the coherent view-A theme)
    "cmp_meeplediff": lambda f: ((f["dist_own_meeple"] or 0)
                                 - (f["dist_opp_meeple"] or 0)),
}


def augment_derived(table):
    for e in table:
        for f in e["fx"].values():
            for name, fn in DERIVED.items():
                f[name] = fn(f)


def cmd_analyze() -> int:
    global FEATURE_NAMES
    table, problems, excluded_pool = build_table("dev")
    hold = load_holdout_roots()
    assert not any(e["root_id"] in hold for e in table)
    augment_derived(table)
    FEATURE_NAMES = FEATURE_NAMES + tuple(DERIVED)

    a = view_a(table)
    b = view_b(table)
    c = view_c(table)

    by_phase = {}
    for ph in ("early", "mid", "late"):
        sub = [e for e in table if e["phase"] == ph]
        if sub:
            by_phase[ph] = {"n": len(sub), "view_a": view_a(sub),
                            "view_b": view_b(sub)}

    # S2b on the dev slice (context: the ceiling the mining plays for).
    # HONEST ceiling = the pricing run's per-position parity-split
    # `headroom_leaf` (selection on even worlds, evaluation on odd), which is
    # winner's-curse-free. The full-M argmax version is emitted only as
    # `naive` — E[max of noisy means] > max of true means, so it is inflated
    # (the same inflation makes view A's "oracle-best arm" identity noisy:
    # that attenuates feature diffs toward 0, it cannot fake signal).
    per_all = TG.load_per_position()
    caps, caps_naive, clusters = [], [], []
    for e in table:
        row = per_all[e["rid"]]
        caps.append(row["headroom_leaf"] * e["scale_all"])
        best = max(e["pool"], key=lambda i: (e["means"][i], -i))
        caps_naive.append((e["means"][best] - e["means"][0]) * e["scale_all"])
        clusters.append(e["root_id"])
    ceiling = _summ(caps, clusters)
    ceiling_naive = _summ(caps_naive, clusters)
    ceiling_naive["note"] = ("winner's-curse-inflated (argmax of full-M means "
                             "evaluated on the same means); audit only")

    # ---- feature-space reach (EXPLORATORY upper bound) -------------------- #
    # Any deterministic pick rule over these descriptors is constant on arms
    # with identical feature vectors (ties -> lowest index). The best it can
    # possibly do per position is the best lowest-index-representative over
    # the feature-equivalence classes. Computed with the same naive full-M
    # argmax as ceiling_naive, so reach/naive is the meaningful ratio (both
    # curse-inflated the same way); n_indist = positions where the whole pool
    # collapses to ONE class (no rule can move at all).
    reach_caps, n_indist = [], 0
    for e in table:
        classes = {}
        for i in e["pool"]:
            key = tuple(sorted((k, v) for k, v in
                               e["fx"][int(e["acts"][i])].items()
                               if k != "action"))
            if key not in classes or i < classes[key]:
                classes[key] = i
        reps = sorted(classes.values())
        if len(reps) < 2:
            n_indist += 1
        best_rep = max(reps, key=lambda i: (e["means"][i], -i))
        reach_caps.append((e["means"][best_rep] - e["means"][0])
                          * e["scale_all"])
    reach = _summ(reach_caps, clusters)
    reach["n_pools_fully_indistinguishable"] = n_indist
    reach["note"] = ("naive (curse-inflated) like ceiling_naive; the ratio "
                     "reach/naive bounds ANY deterministic static rule over "
                     "the mined descriptor space")

    result = {
        "schema": "carcassonne-tiletie-mining/v1",
        "status": "EXPLORATORY — selection-biased (view A conditions on "
                  "disagreement); in-sample shopping (view B); no confirmatory "
                  "p-values anywhere in this file",
        "slice": "dev (holdout roots firewalled by filename, never parsed)",
        "n_positions": len(table),
        "n_roots": len({e["root_id"] for e in table}),
        "n_problems": len(problems), "problems": problems[:10],
        "n_excluded_pool_lt2": len(excluded_pool),
        "dev_ceiling_S2b_all_scale": ceiling,
        "dev_ceiling_S2b_naive_all_scale": ceiling_naive,
        "feature_space_reach_naive_all_scale": reach,
        "view_a_best_vs_incumbent": a,
        "view_b_single_feature_capture": b,
        "view_c_within_set_correlation": c,
        "view_a_by_phase": by_phase,
    }
    MEAS.mkdir(parents=True, exist_ok=True)
    (MEAS / "MINING_STATS.json").write_text(json.dumps(result, indent=1))

    # quick console digest: top-10 view-B captures
    top = sorted(b.items(), key=lambda kv: -kv[1]["mean"])[:10]
    print(f"[mine] dev slice: {len(table)} positions / "
          f"{result['n_roots']} roots; disagreement "
          f"{a['n_disagree']}/{a['n_total']}; dev S2b ceiling "
          f"{ceiling['mean']:+.4f} ± {ceiling['se_cluster']:.4f}")
    for k, v in top:
        print(f"  {k:<20} capture {v['mean']:+.4f} ± {v['se_cluster']:.4f} "
              f"(z {v['z']:+.2f}, moved {v['moved_frac']:.0%})")
    print(f"-> {MEAS / 'MINING_STATS.json'}")
    return 1 if problems else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--slice", default="dev", choices=("dev", "final"))
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args(argv)
    if a.split:
        return cmd_split()
    if a.extract:
        if not a.profile:
            raise SystemExit("--extract needs --profile")
        return cmd_extract(a.profile, a.workers, a.slice)
    if a.run:
        for prof in ("walled", "fixed_v1", "app_aug2"):
            rc = subprocess.call([sys.executable, str(Path(__file__).resolve()),
                                  "--extract", "--profile", prof,
                                  "--slice", "dev", "--workers", str(a.workers)])
            if rc:
                return rc
        return cmd_analyze()
    if a.analyze:
        return cmd_analyze()
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
