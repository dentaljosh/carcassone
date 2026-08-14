#!/usr/bin/env python3
"""TILE-TIE TERM — the offline discrimination gate
(measurement/tiletie_term_20260814/GATE_READ_RULE.md, committed BEFORE this ran).

Grades the hand-crafted tie-break features of `flat_leaf.flat_tiletie_term`
against the FREE deep-scored corpus of the pooled tile-tie pricing run
(measurement/tiletie_pricing_20260812): 733 positions over 399 roots, every
deduped tied arm scored under M=32 CRN clairvoyant worlds. CL-073 discipline:
the gate is within-tied-set MOVE ORDERING (captured headroom vs the incumbent
lowest-index convention), never outcome prediction.

Two phases, mirroring the read-rule exactly:

  --extract --profile {walled,fixed_v1,app_aug2}
      One subprocess per rules profile (CARCASSONNE_FIX_R9 is import-latched):
      replay every corpus position under its own profile, checksum-assert,
      apply每 scored arm's TILE action, and record the four raw features
      (D_city, D_road, F_perim, F_lib) of the afterstate from the root player's
      POV. Writes features_{profile}.jsonl. LABEL-FREE: oracle values are never
      read in this phase.

  --analyze
      Joins features to the per-arm oracle means (all 32 CRN worlds), runs the
      pre-registered 10-variant menu through the 5-fold root-clustered
      cross-fit, and emits GATE_READOUT.{md,json} with the branch adjudicated
      strictly by the read-rule. Pure arithmetic; no engine import.

  --run
      Orchestrates: 3 extract subprocesses (sequential), then --analyze.

Feature semantics live in ONE place — `flat_leaf._tiletie_wallin` and the
open-position scans match `flat_leaf.flat_tiletie_term` exactly (the gate
grades the same geometry the deployable term computes; the term's bounded map
t/(1+|t|) is strictly monotone, so grading the raw weighted sums is grading
the term's ordering).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for _p in (str(HERE), str(REPO / "scripts" / "measurement_infra")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

MEAS = REPO / "measurement" / "tiletie_term_20260814"
PRICING = REPO / "measurement" / "tiletie_pricing_20260812"
PER_POSITION = PRICING / "readout_POOLED" / "per_position.jsonl"
ARMS_JSON = PRICING / "positions_pooled" / "ARMS.json"
PLAN_DIRS = (PRICING / "positions_stageA", PRICING / "positions_stageB")


def _share(rel: str) -> str:
    for root in ("/mnt/c/carc-shared", "/mnt/carc-shared"):
        if Path(root).is_dir():
            return f"{root}/{rel}"
    return f"/mnt/carc-shared/{rel}"


RECORDS_ROOT = _share("tiletie_pricing_20260812/clair-puct")

SEED = 20260814
N_FOLDS = 5
BOOT_REPS = 10_000

#: the read-rule §3 menu, in its frozen preference order.
VARIANTS = (
    ("city+", (1.0, 0.0, 0.0, 0.0)),
    ("city-", (-1.0, 0.0, 0.0, 0.0)),
    ("road+", (0.0, 1.0, 0.0, 0.0)),
    ("road-", (0.0, -1.0, 0.0, 0.0)),
    ("cityroad+", (1.0, 1.0, 0.0, 0.0)),
    ("cityroad-", (-1.0, -1.0, 0.0, 0.0)),
    ("perim+", (0.0, 0.0, 1.0, 0.0)),
    ("perim-", (0.0, 0.0, -1.0, 0.0)),
    ("lib+", (0.0, 0.0, 0.0, 1.0)),
    ("lib-", (0.0, 0.0, 0.0, -1.0)),
)
FIXED_VARIANT = "cityroad+"          # read-rule §5.1: the mechanism-preferred bundle

#: §4.3-chain constants, verbatim from the pricing readout (readout_POOLED §5).
TIED_PLIES_PER_GAME = 22.96
NON_ADDITIVITY = 3.2
SIGMA_GAME = 20.4
PHI0 = 0.3989422804014327


# --------------------------------------------------------------------------- #
# corpus plumbing (shared by both phases)                                       #
# --------------------------------------------------------------------------- #
def load_per_position() -> dict:
    rows = {}
    for line in PER_POSITION.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["rid"]] = r
    return rows


def load_actions_index(rids_needed: set) -> dict:
    """rid -> {'actions': [...] } or {'archive_path': ...}, from the stage leg1
    plan files (every scored position appears in its stage's leg1)."""
    out = {}
    for pdir in PLAN_DIRS:
        for f in sorted(glob.glob(str(pdir / "positions_*_leg1.jsonl"))):
            for line in Path(f).read_text().splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                rid = r["rid"]
                if rid in rids_needed and rid not in out:
                    out[rid] = r
    missing = rids_needed - set(out)
    if missing:
        raise SystemExit(f"REFUSING: {len(missing)} rids have no leg1 plan row "
                         f"(sample: {sorted(missing)[:3]})")
    return out


# --------------------------------------------------------------------------- #
# phase 1: feature extraction (one subprocess per rules profile)               #
# --------------------------------------------------------------------------- #
def _extract_one(args):
    """(rid, deck_seed, ply, root_player, checksum, actions, arm_actions) ->
    feature rows. Runs inside a fork Pool worker; the profile env/imports were
    latched by the parent before carcassonne_ai was imported."""
    (rid, deck_seed, ply, root_player, checksum, actions, arm_actions, gk) = args
    import root_replay as RR
    from wingedsheep.carcassonne.objects.terrain_type import TerrainType

    from carcassonne_ai import flat_leaf

    game, board = RR.replay_actions(deck_seed, actions, ply, game_kwargs=gk)
    if game.string_representation(board) != checksum:
        return {"rid": rid, "error": "checksum_mismatch"}
    feats = []
    for act in arm_actions:
        b1, _ = game.get_next_state(board, int(act))
        st = b1.state
        d = flat_leaf.decompose(st)
        p = int(root_player)
        wc = flat_leaf._tiletie_wallin(st, d, d.city_side_root,
                                       d.city_root_positions, d.city_root_finished,
                                       d.city_root_open_n, TerrainType.CITY)
        wr = flat_leaf._tiletie_wallin(st, d, d.road_side_root,
                                       d.road_root_positions, d.road_root_finished,
                                       d.road_root_open_n, TerrainType.ROAD)
        brd = st.board
        H = len(brd)
        W = len(brd[0]) if H else 0
        perim = 0
        n_open = 0
        for pos in st.open_positions:
            er, ec = pos.row, pos.column
            n_open += 1
            if er > 0 and brd[er - 1][ec] is not None:
                perim += 1
            if er + 1 < H and brd[er + 1][ec] is not None:
                perim += 1
            if ec > 0 and brd[er][ec - 1] is not None:
                perim += 1
            if ec + 1 < W and brd[er][ec + 1] is not None:
                perim += 1
        feats.append({
            "action": int(act),
            "d_city": wc[1 - p] - wc[p],
            "d_road": wr[1 - p] - wr[p],
            "f_perim": float(perim),
            "f_lib": float(n_open),
        })
    return {"rid": rid, "features": feats}


def cmd_extract(profile: str, workers: int) -> int:
    import chain_census as CC
    CC.prepare_env(profile)                        # BEFORE any carcassonne_ai import
    from carcassonne_ai import rules_profile as RP
    prof = RP.activate(profile)
    gk = prof.game_kwargs() or None

    per = load_per_position()
    arms = json.loads(ARMS_JSON.read_text())
    rids = [r for r, row in per.items() if row["rules_profile"] == profile]
    acts = load_actions_index(set(rids))

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
    out_path = MEAS / f"features_{profile}.jsonl"
    n_err = 0
    with Pool(workers) as pool, open(out_path, "w") as fh:
        for res in pool.imap_unordered(_extract_one, jobs, chunksize=4):
            if "error" in res:
                n_err += 1
                print(f"[extract:{profile}] {res['rid']}: {res['error']}",
                      file=sys.stderr)
            fh.write(json.dumps(res) + "\n")
    print(f"[extract:{profile}] {len(jobs)} positions, {n_err} errors -> {out_path}")
    return 1 if n_err else 0


# --------------------------------------------------------------------------- #
# phase 2: the gate (pure arithmetic)                                           #
# --------------------------------------------------------------------------- #
def load_oracle_means(per: dict, arms: dict) -> dict:
    """rid -> list of per-arm oracle means (all 32 CRN worlds), aligned with
    arms[rid]['arms']. Integrity: every leg present, pick_a/pick_b aligned."""
    recs = defaultdict(dict)
    for f in glob.glob(f"{RECORDS_ROOT}/*/*/records/*.json"):
        leg = f.split("/")[-3]
        r = json.loads(Path(f).read_text())
        recs[r["rid"]][leg] = r
    out = {}
    problems = []
    for rid in per:
        a = arms[rid]["arms"]
        got = recs.get(rid, {})
        if len(got) != len(a) - 1:
            problems.append((rid, "missing_legs"))
            continue
        ok = all(got[f"leg{i}"]["pick_b"] == a[i] and got[f"leg{i}"]["pick_a"] == a[0]
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


def cluster_se(values: list, clusters: list) -> float:
    n = len(values)
    m = math.fsum(values) / n
    sums = defaultdict(list)
    for v, c in zip(values, clusters):
        sums[c].append(v)
    G = len(sums)
    ss = math.fsum((math.fsum(vs) - len(vs) * m) ** 2 for vs in sums.values())
    return math.sqrt(max(0.0, ss * G / (G - 1))) / n


def elo_chain(capture_all_per_ply: float) -> float:
    pts_game = capture_all_per_ply * TIED_PLIES_PER_GAME / NON_ADDITIVITY
    wr = 0.5 + (pts_game / SIGMA_GAME) * PHI0
    wr = min(max(wr, 1e-9), 1 - 1e-9)
    return 400.0 * math.log10(wr / (1.0 - wr))


def cmd_analyze() -> int:
    import random

    per = load_per_position()
    arms = json.loads(ARMS_JSON.read_text())
    oracle, problems = load_oracle_means(per, arms)

    feats = {}
    n_checksum_err = 0
    for profile in ("walled", "fixed_v1", "app_aug2"):
        p = MEAS / f"features_{profile}.jsonl"
        if not p.exists():
            raise SystemExit(f"REFUSING: {p} missing — run --extract first")
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "error" in r:
                n_checksum_err += 1
                continue
            feats[r["rid"]] = {f["action"]: f for f in r["features"]}

    # ---- build the per-position table -------------------------------------- #
    excluded_pool = []
    table = []            # dicts with everything the statistics need
    for rid, row in sorted(per.items()):
        a = arms[rid]
        acts = a["arms"]
        if rid not in oracle or rid not in feats:
            problems.append((rid, "not_joined"))
            continue
        means = oracle[rid]
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
            "acts": acts, "means": means, "pool": pool, "champ_ix": champ_ix,
            "fx": fx,
        })

    # ---- G0 ----------------------------------------------------------------- #
    g0 = {
        "n_positions": len(table),
        "n_problems": len(problems),
        "problems": problems[:10],
        "n_checksum_errors": n_checksum_err,
        "n_excluded_pool_lt2": len(excluded_pool),
        "excluded_pool_lt2": excluded_pool[:10],
    }
    g0_fail = bool(problems) or n_checksum_err > 0 or len(excluded_pool) > 5

    def raw_sum(v_weights, f):
        wc, wr, wp, wl = v_weights
        return (wc * f["d_city"] + wr * f["d_road"]
                + wp * f["f_perim"] + wl * f["f_lib"])

    def pick(entry, v_weights):
        acts, fx, pool = entry["acts"], entry["fx"], entry["pool"]
        best_i = None
        best_key = None
        for i in pool:
            key = (raw_sum(v_weights, fx[int(acts[i])]), -int(acts[i]))
            if best_key is None or key > best_key:
                best_key, best_i = key, i
        return best_i

    vname_ix = {name: i for i, (name, _) in enumerate(VARIANTS)}
    # per-position capture per variant (scale_all applied)
    cap = {name: [] for name, _ in VARIANTS}
    moved = {name: 0 for name, _ in VARIANTS}
    picks = {name: [] for name, _ in VARIANTS}
    for e in table:
        for name, w in VARIANTS:
            i = pick(e, w)
            picks[name].append(i)
            c = (e["means"][i] - e["means"][0]) * e["scale_all"]
            cap[name].append(c)
            if i != 0:
                moved[name] += 1

    roots = [e["root_id"] for e in table]
    n = len(table)

    # ---- cross-fit ----------------------------------------------------------- #
    uniq_roots = sorted(set(roots))
    rng = random.Random(SEED)
    rng.shuffle(uniq_roots)
    fold_of_root = {r: i % N_FOLDS for i, r in enumerate(uniq_roots)}
    fold = [fold_of_root[r] for r in roots]

    heldout = [0.0] * n
    heldout_pick = [0] * n
    fold_selected = []
    for k in range(N_FOLDS):
        train_ix = [i for i in range(n) if fold[i] != k]
        best_name, best_mean = None, None
        for name, _ in VARIANTS:          # frozen preference order breaks ties
            m = math.fsum(cap[name][i] for i in train_ix) / len(train_ix)
            if best_mean is None or m > best_mean:
                best_mean, best_name = m, name
        fold_selected.append(best_name)
        for i in range(n):
            if fold[i] == k:
                heldout[i] = cap[best_name][i]
                heldout_pick[i] = picks[best_name][i]

    primary_mean = math.fsum(heldout) / n
    primary_se = cluster_se(heldout, roots)
    primary_z = primary_mean / primary_se if primary_se else float("nan")

    # bootstrap CI (roots resampled, fold assignment/held-out values fixed)
    by_root = defaultdict(list)
    for v, r in zip(heldout, roots):
        by_root[r].append(v)
    root_list = list(by_root)
    brng = random.Random(SEED)
    boots = []
    for _ in range(BOOT_REPS):
        tot = 0.0
        cnt = 0
        for _ in range(len(root_list)):
            r = root_list[brng.randrange(len(root_list))]
            vs = by_root[r]
            tot += math.fsum(vs)
            cnt += len(vs)
        boots.append(tot / cnt)
    boots.sort()
    ci_lo = boots[int(0.025 * BOOT_REPS)]
    ci_hi = boots[int(0.975 * BOOT_REPS)] if BOOT_REPS > 40 else boots[-1]

    # ---- secondaries ---------------------------------------------------------- #
    def summarize(values):
        m = math.fsum(values) / len(values)
        se = cluster_se(values, roots)
        return {"mean": m, "se_cluster": se,
                "z": (m / se if se else float("nan"))}

    fixed = summarize(cap[FIXED_VARIANT])
    naive_best_name = max(VARIANTS, key=lambda v: math.fsum(cap[v[0]]) / n)[0]
    naive_best = {"variant": naive_best_name,
                  **summarize(cap[naive_best_name]),
                  "note": "audit only, in-sample best-of-menu, never a result"}

    vs_champ = []
    for e, i in zip(table, heldout_pick):
        ci = e["champ_ix"]
        if ci is None:
            continue
        vs_champ.append((e["means"][i] - e["means"][ci]) * e["scale_all"])
    vs_champ_stat = summarize(vs_champ) if vs_champ else None

    per_variant = {name: {"mean_all": math.fsum(cap[name]) / n,
                          "moved_frac": moved[name] / n} for name, _ in VARIANTS}

    def subgroup(pred):
        ix = [i for i, e in enumerate(table) if pred(e)]
        if not ix:
            return None
        vals = [heldout[i] for i in ix]
        cl = [roots[i] for i in ix]
        m = math.fsum(vals) / len(vals)
        se = cluster_se(vals, cl)
        return {"n": len(ix), "mean": m, "se": se,
                "z": (m / se if se else float("nan"))}

    by_phase = {ph: subgroup(lambda e, ph=ph: e["phase"] == ph)
                for ph in ("early", "mid", "late")}
    by_stratum = {st: subgroup(lambda e, st=st: e["stratum"] == st)
                  for st in ("e4", "selfplay")}

    heldout_moved = sum(1 for i in heldout_pick if i != 0) / n

    # ---- branch --------------------------------------------------------------- #
    if g0_fail:
        branch = "G0 UNREADABLE"
    elif primary_z >= 2.0:
        branch = "G-PASS"
    elif primary_z <= -2.0:
        branch = "G-HARMFUL"
    else:
        branch = "G-FAIL (no conviction)"

    # full-corpus selection (deploy variant on G-PASS only)
    full_best = None
    best_mean = None
    for name, _ in VARIANTS:
        m = math.fsum(cap[name]) / n
        if best_mean is None or m > best_mean:
            best_mean, full_best = m, name

    result = {
        "schema": "carcassonne-tiletie-term-gate/v1",
        "read_rule": "measurement/tiletie_term_20260814/GATE_READ_RULE.md",
        "seed": SEED, "n_folds": N_FOLDS, "bootstrap_reps": BOOT_REPS,
        "g0": g0,
        "branch": branch,
        "primary": {
            "statistic": "5-fold root-clustered cross-fit pooled held-out "
                         "capture_all (pts per tied tile ply, all-plies scale)",
            "mean": primary_mean, "se_cluster": primary_se, "z": primary_z,
            "ci95_boot": [ci_lo, ci_hi],
            "n": n, "n_roots": len(uniq_roots),
            "fold_selected_variants": fold_selected,
            "heldout_moved_frac": heldout_moved,
            "elo_extrapolated": elo_chain(primary_mean),
            "elo_ci95_boot": [elo_chain(ci_lo), elo_chain(ci_hi)],
            "elo_note": "§4.3-chain extrapolation, ±1.6× divisor bracket applies "
                        "(NON_ADDITIVITY 3.2 is n=1; low-end divisor 5.23)",
            "realized_2sigma_bound_pts": 2 * primary_se,
            "realized_2sigma_bound_elo": elo_chain(2 * primary_se),
        },
        "ceiling_context": {
            "S2b_leaf_regret_all": 0.2340,
            "S2b_leaf_regret_discriminable": 0.3236,
            "note": "pricing readout: no term can capture more in expectation",
        },
        "secondary": {
            "fixed_variant": {"variant": FIXED_VARIANT, **fixed,
                              "note": "no selection -> unbiased on the full corpus"},
            "naive_best_of_menu": naive_best,
            "capture_vs_champ": vs_champ_stat,
            "by_phase": by_phase,
            "by_stratum": by_stratum,
            "per_variant": per_variant,
            "full_corpus_selected_variant": full_best,
        },
    }
    MEAS.mkdir(parents=True, exist_ok=True)
    (MEAS / "GATE_READOUT.json").write_text(json.dumps(result, indent=1))
    _write_md(result)
    print(json.dumps({"branch": branch, "primary_mean": primary_mean,
                      "z": primary_z, "ci": [ci_lo, ci_hi]}, indent=1))
    return 0


def _write_md(r: dict) -> None:
    p = r["primary"]
    s = r["secondary"]
    lines = [
        "# TILE-TIE TERM — OFFLINE GATE READOUT",
        "",
        f"**Read-rule: [GATE_READ_RULE.md](GATE_READ_RULE.md) (committed before "
        f"this ran). Branch: `{r['branch']}`.** Generated by "
        "`scripts/tiletie/term_gate.py --analyze`; machine-readable twin "
        "`GATE_READOUT.json`. 0 games; no results.csv row, no band, no claim id.",
        "",
        "## G0 integrity",
        "",
        f"- positions entering: **{p['n']}** over **{p['n_roots']}** roots",
        f"- join problems: **{r['g0']['n_problems']}** · checksum errors: "
        f"**{r['g0']['n_checksum_errors']}** · pool<2 exclusions: "
        f"**{r['g0']['n_excluded_pool_lt2']}**",
        "",
        "## PRIMARY — cross-fit captured headroom (pts per tied tile ply, all-plies scale)",
        "",
        "| statistic | value |",
        "|---|---|",
        f"| mean (held-out, pooled) | **{p['mean']:+.4f}** |",
        f"| cluster-robust se | {p['se_cluster']:.4f} |",
        f"| z | **{p['z']:+.2f}** |",
        f"| 95% CI (root bootstrap) | [{p['ci95_boot'][0]:+.4f}, {p['ci95_boot'][1]:+.4f}] |",
        f"| fold-selected variants | {', '.join(p['fold_selected_variants'])} |",
        f"| held-out pick moved vs arm0 | {p['heldout_moved_frac']:.1%} |",
        f"| elo (§4.3 extrapolation, ±1.6× bracket) | {p['elo_extrapolated']:+.1f} "
        f"[{p['elo_ci95_boot'][0]:+.1f}, {p['elo_ci95_boot'][1]:+.1f}] |",
        f"| realized 2σ resolution | ±{p['realized_2sigma_bound_pts']:.4f} pts ≈ "
        f"±{p['realized_2sigma_bound_elo']:.1f} elo |",
        "",
        f"**Ceiling context (mandatory):** the oracle best-of-scored-set leaf "
        f"regret S2b is **+{r['ceiling_context']['S2b_leaf_regret_all']:.4f} pts/ply "
        "(all)** — no term can capture more in expectation.",
        "",
        "## Secondary (reported, never the verdict)",
        "",
        "| read | value |",
        "|---|---|",
        f"| fixed variant `{s['fixed_variant']['variant']}` (unbiased, full corpus) | "
        f"{s['fixed_variant']['mean']:+.4f} ± {s['fixed_variant']['se_cluster']:.4f} "
        f"(z {s['fixed_variant']['z']:+.2f}) |",
        f"| *(audit only)* naive best-of-menu `{s['naive_best_of_menu']['variant']}` | "
        f"{s['naive_best_of_menu']['mean']:+.4f} (in-sample, curse-inflated) |",
    ]
    if s["capture_vs_champ"]:
        lines.append(
            f"| capture vs champion's realized pick (descriptive) | "
            f"{s['capture_vs_champ']['mean']:+.4f} ± "
            f"{s['capture_vs_champ']['se_cluster']:.4f} "
            f"(z {s['capture_vs_champ']['z']:+.2f}) |")
    lines += ["", "### Held-out capture by phase / stratum (descriptive)", "",
              "| slice | n | mean | z |", "|---|---|---|---|"]
    for k, v in {**{f"phase:{k}": v for k, v in s["by_phase"].items()},
                 **{f"stratum:{k}": v for k, v in s["by_stratum"].items()}}.items():
        if v:
            lines.append(f"| {k} | {v['n']} | {v['mean']:+.4f} | {v['z']:+.2f} |")
    lines += ["", "### Per-variant full-corpus capture (descriptive, in-sample)", "",
              "| variant | mean (all-scale) | moved pick |", "|---|---|---|"]
    for name, d in s["per_variant"].items():
        lines.append(f"| {name} | {d['mean_all']:+.4f} | {d['moved_frac']:.1%} |")
    lines += ["",
              f"Full-corpus selected variant (deploys ONLY on G-PASS): "
              f"`{s['full_corpus_selected_variant']}`.", ""]
    (MEAS / "GATE_READOUT.md").write_text("\n".join(lines))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args(argv)
    if a.extract:
        if not a.profile:
            raise SystemExit("--extract needs --profile")
        return cmd_extract(a.profile, a.workers)
    if a.run:
        for prof in ("walled", "fixed_v1", "app_aug2"):
            rc = subprocess.call([sys.executable, str(Path(__file__).resolve()),
                                  "--extract", "--profile", prof,
                                  "--workers", str(a.workers)])
            if rc:
                return rc
        return cmd_analyze()
    if a.analyze:
        return cmd_analyze()
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
