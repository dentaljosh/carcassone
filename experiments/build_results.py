#!/usr/bin/env python3
"""Build experiments/results.csv — the source-of-truth index of every completed
head-to-head eval for the Carcassonne AZ project.

Each eval wrote an `elo_log.json` (the OUTCOME) but NOT its CONFIG. The config is
recovered here from three sources, in priority order:
  1. The launcher scripts in /mnt/c/carc-shared/code_sync/*.sh and
     ~/launch_*.sh / ~/phase3_continue.sh  (EXACT --c-puct / --new-c-puct /
     --leaf-cap / --leaf-variant / checkpoints flags). Highest trust.
  2. STATUS.md verdict table + DECISIONS.md prose (dates, elo, conclusions).
  3. The directory name (encodes the experiment intent).

Per-game JSONs under <dir>/eval/<matchup>/s<sims>_seed<N>_p<player>.json give the
ACTUAL n (file count), avg score margin (mean diff from the NEW side's POV), and
sims. They do NOT carry c_puct/cap/variant.

Optuna trials (study `eval_time_search_v1`) are the ONE place config is stored in
the data itself (trial.params). OLD side for every trial is fixed
(c=1.5, cap=12, v2_7); NEW side is the trial params; both use iter_B1, sims=200.

Output schema (one row per completed eval / per completed optuna trial):
  exp_id, date, n, new_ckpt, new_c, new_cap, new_var, new_sims,
  old_ckpt, old_c, old_cap, old_var, old_sims,
  W, L, D, elo, sigma, avg_diff, src_dir, confidence, note

sigma = standard error of the elo estimate at this n, computed from the binomial
score s = (W + 0.5*D)/n:  SE(elo) = (400/ln10) * SE(s)/(s*(1-s)), with
SE(s) = sqrt(s*(1-s)/n). This is the logistic-elo delta method; it agrees with
the 400/sqrt(n) rule-of-thumb near s=0.5. We use the binomial form (stated here).
"""
from __future__ import annotations

import csv
import json
import math
import os
import datetime as dt
from glob import glob

SHARED = "/mnt/c/carc-shared"
LAPTOP = "/home/doctor/projects/carcassone/data/laptop_results"
OUT_CSV = "/home/doctor/projects/carcassone/experiments/results.csv"
OPTUNA_DB = "sqlite:////mnt/c/carc-shared/optuna_runs/study.db"
OPTUNA_STUDY = "eval_time_search_v1"

# Canonical checkpoint shorthand -> repo-relative path.
CKPT = {
    "iter_01": "checkpoints/v25_retrain_iter01/iter_00.pt",
    "iter_02": "checkpoints/v25_retrain_iter02/iter_00.pt",
    "iter_B1": "checkpoints/v25_retrain_optionB_iter1/iter_00.pt",
    "iter_B2": "checkpoints/v25_retrain_optionB_iter2/iter_00.pt",
    "iter_B3": "checkpoints/v25_retrain_optionB_iter3/iter_00.pt",
    "iter_B4": "checkpoints/v25_retrain_optionB_iter4/iter_00.pt",
    "iter_B5": "checkpoints/v25_retrain_optionB_iter5/iter_00.pt",
    "deepsearch_v1": "checkpoints/v25_retrain_deepsearch/iter_00.pt",
    "deepsearch_v2": "checkpoints/v25_retrain_deepsearch_v2/iter_00.pt",
    "deepsearch_v3": "checkpoints/v25_retrain_deepsearch_v3/iter_00.pt",
    "af_v1": "checkpoints/v25_anchor_fraction_s200_iter1/iter_00.pt",
}

# Default leaf: v2.7 (env CARCASSONNE_V25_DROP_THREE_OPEN=1, CAP=12), base v2_5.
DEF_CAP = 12
DEF_VAR = "v2_7"

# Hand-recovered config per eval dir. Sources cited in `src`. Each entry sets the
# fields that the per-game JSON / elo_log CANNOT give us. n/W/L/D/avg_diff/date/
# sims are read from the files; everything below is the recovered config + note.
# confidence: high = exact launcher flags found; medium = docs + dirname agree but
# no launcher; low = inference only.
CONFIG = {
    # --- Phase 2 / 2b PUCT sweep: iter_B1 both sides, only c differs. n=400,
    #     sims=200, cap=12, v2_7. Launchers: launch_xeon_phase2_puct.sh /
    #     phase2b_puct.sh (per-side c pairs), STATUS verdict table confirms elo.
    "phase2_puct_c05_vs_c15": dict(new_ckpt="iter_B1", new_c=0.5, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 2b c-sweep; iter_B1 both sides, only eval-side c differs. launch_xeon_phase2_puct.sh."),
    "phase2_puct_c10_vs_c15": dict(new_ckpt="iter_B1", new_c=1.0, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 2b c-sweep. launch_xeon_phase2_puct.sh."),
    "phase2_puct_c25_vs_c15": dict(new_ckpt="iter_B1", new_c=2.5, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 2b c-sweep. launch_xeon_phase2b_puct.sh."),
    "phase2_puct_c30_vs_c15": dict(new_ckpt="iter_B1", new_c=3.0, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 2b c-sweep PEAK (+47.2). iter_B1 both sides. launch_xeon_phase2_puct.sh. SEE CONTRADICTION vs optuna #17."),
    "phase2_puct_c40_vs_c15": dict(new_ckpt="iter_B1", new_c=4.0, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 2b c-sweep. launch_xeon_phase2b_puct.sh."),
    "phase2_puct_c50_vs_c15": dict(new_ckpt="iter_B1", new_c=5.0, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 2b c-sweep. launch_xeon_phase2b_puct.sh."),
    # earlier 2-point c sweep (2026-05-20), iter_01 both sides, c=2.0 vs 1.5.
    "puct_c2_vs_c15": dict(new_ckpt="iter_01", new_c=2.0, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="Early c=2.0 vs 1.5 retro-validation, iter_01 both sides, n=400. launch_xeon_puct_c2_vs_c15_n400.sh. genuine null (+5.2)."),

    # --- Phase 3 (re-test null verdicts at peak c=3) ---
    "phase3_af_c3_vs_iter01": dict(new_ckpt="af_v1", new_c=3.0, old_ckpt="iter_01", old_c=3.0,
        conf="high", note="anchor-fraction af_v1 vs iter_01 at c=3 both sides, sims=200, n=400. launch_xeon_p3_af_c3.sh. RECOVERED +30.5 (was -1 at c=1.5)."),
    "phase3_c3_vs_c15_s800": dict(new_ckpt="iter_B1", new_c=3.0, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="J4: c=3 vs c=1.5 at sims=800, iter_B1 both sides, n=400. launch_xeon_p3_c3_s800.sh. +39.3 (c=3 transfers to sims=800)."),
    "phase3_ds2_c3_vs_iter01_s800": dict(new_ckpt="deepsearch_v2", new_c=3.0, old_ckpt="iter_01", old_c=3.0,
        conf="high", note="J2: deepsearch_v2 vs iter_01 at c=3 both sides, sims=800, n=400. launch_xeon_p3_ds2_c3_s800.sh. confirmed dead -0.9."),
    "phase3_tc_c3_vs_v27": dict(new_ckpt="iter_B1", new_c=3.0, old_ckpt="iter_B1", old_c=3.0,
        new_var="tile_counting", old_var="v2_7",
        conf="high", note="J3: tile_counting leaf vs v2_7 leaf, iter_B1 both sides, c=3 both sides, sims=200, n=400. launch_xeon_p3_tc_c3.sh. confirmed dead -12.2."),

    # --- Phase 4 leaf-cap / value-blend A/B at iter_B1, c=1.5, sims=200 ---
    "phase4_cap20_vs_cap12": dict(new_ckpt="iter_B1", new_c=1.5, old_ckpt="iter_B1", old_c=1.5,
        new_cap=20, old_cap=12,
        conf="high", note="Phase 4a: cap=20 vs cap=12 leaf-cap A/B, iter_B1 both sides, n=400. launch_queue_2026_05_25_5800x.sh (job B). -21.7. CONTRADICTS optuna #5 (+12.2 at n=400)."),
    "phase4_capInf_vs_cap12": dict(new_ckpt="iter_B1", new_c=1.5, old_ckpt="iter_B1", old_c=1.5,
        new_cap=9999, old_cap=12,
        conf="high", note="Phase 4b: cap=inf(9999) vs cap=12, iter_B1 both sides, n=400. launch_queue_2026_05_25_5800x.sh (job C). null -0.9."),
    "phase4_blend05_vs_pure": dict(new_ckpt="iter_B1", new_c=1.5, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Phase 4c: NN value-blend lambda=0.5 (new) vs pure leaf (old), iter_B1 both sides, n=500. launch_queue_2026_05_25_5800x.sh (job D). -18.8 (value-blend dead)."),

    # --- Hygiene re-measurements (2026-05-29, n=1600) settling the 2 flagged contradictions ---
    "hygiene_c3_cap12_n1600": dict(new_ckpt="iter_B1", new_c=3.0, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="HYGIENE n=1600: re-measure the c=3 spike. iter_B1 both sides, sims=200. Settles phase2_puct_c30 (+47.2@n400) vs optuna#17 (+13.9@n100). 5800X+Xeon work-stealing (launch_xeon_hygieneA.sh)."),
    "hygiene_cap20_n1600": dict(new_ckpt="iter_B1", new_c=1.5, old_ckpt="iter_B1", old_c=1.5, new_cap=20, old_cap=12,
        conf="high", note="HYGIENE n=1600: tie-break cap=20 vs cap=12. iter_B1 both sides, c=1.5, sims=200. Settles phase4_cap20 (-21.7) vs optuna#5 (+12.2). laptop solo; rsync /tmp/hygiene_cap20_n1600 -> shared before rebuild."),

    # --- Phase 5 smoke: tile_counting leaf vs v2_7, iter_B1 both sides ---
    "phase5_tilecounting_smoke": dict(new_ckpt="iter_B1", new_c=1.5, old_ckpt="iter_B1", old_c=1.5,
        new_var="tile_counting", old_var="v2_7",
        conf="high", note="Phase 5 leaf A/B smoke: tile_counting vs v2_7 leaf, iter_B1 both sides, n=400, c=1.5. launch_xeon_phase5smoke.sh. +6.1 (within noise)."),

    # --- Option B chain (chain-vs-prev measurements; n~2000) ---
    "optionB_iter2_eval": dict(new_ckpt="iter_B2", new_c=1.5, old_ckpt="iter_B1", old_c=1.5,
        conf="high", note="Option B chain step: B2 vs B1, n=2000, c=1.5. launch_xeon_ev_B2_vs_B1.sh. +11.4 vs PREDECESSOR (looked fine; drift hidden)."),
    "optionB_iter3_eval": dict(new_ckpt="iter_B3", new_c=1.5, old_ckpt="iter_B2", old_c=1.5,
        conf="high", note="Option B chain step: B3 vs B2, n=2000, c=1.5. launch_xeon_ev_B3_vs_B2.sh. +2.4 vs predecessor."),
    "optionB_iter4_eval": dict(new_ckpt="iter_B4", new_c=1.5, old_ckpt="iter_B3", old_c=1.5,
        conf="high", note="Option B chain step: B4 vs B3, n=2000, c=1.5. launch_xeon_ev_B4_vs_B3.sh. +1.4 vs predecessor."),

    # --- Option B direct-anchor evals vs the fixed reference iter_01 ---
    "B2_vs_iter01_anchor": dict(new_ckpt="iter_B2", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="B2 vs FIXED iter_01 anchor, n=400, c=1.5. launch_xeon_B2anchor.sh. -6.1 (chain doesn't even gain in step 1 vs reference)."),
    "B4_vs_iter01_anchor": dict(new_ckpt="iter_B4", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="B4 vs FIXED iter_01 anchor, n=400, c=1.5. launch_xeon_B4anchor.sh. -19.1 (~55 elo drift vs reference while chain looked neutral)."),

    # --- deepsearch (v1) global-best retro-validation, sims=800 ---
    "deepsearch_eval_s800": dict(new_ckpt="deepsearch_v1", new_c=1.5, old_ckpt="iter_01", old_c=1.5, new_sims=800, old_sims=800,
        conf="high", note="deepsearch_v1 vs iter_01 at sims=800, c=1.5, n=380. launch_xeon_deepsearch_s800_n400.sh. +35.8 (sims=800-plane global best)."),

    # --- iter retro-validation revisits (2026-05-20), sims=200, c=1.5 ---
    "iter02_revisit_s200": dict(new_ckpt="iter_02", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="iter_02 vs iter_01, n=400, c=1.5. launch_xeon_iter02_s200_n400.sh. -4.3 genuine null (compounding flattened)."),
    "iter_B1_revisit_s200": dict(new_ckpt="iter_B1", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="iter_B1 vs iter_01, n=400, c=1.5. launch_xeon_iter_B1_s200_n400.sh. +25.2 (sims=200-plane global best, recovered FN)."),

    # --- deepsearch_v2 sims=200 anchor (orphaned /loop train+anchor) ---
    "deepsearch_v2_n400": dict(new_ckpt="deepsearch_v2", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="deepsearch_v2 vs iter_01, sims=200, c=1.5, n=400. launch_xeon_dsv2_n400.sh. +5.2 (null at sims=200; sims=800 data didnt move sims=200)."),
    "deepsearch_v2_eval": dict(new_ckpt="deepsearch_v2", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="medium", note="deepsearch_v2 vs iter_01 n=100 screen (precedes deepsearch_v2_n400). +13.9 @ n=100; same config as deepsearch_v2_n400 (+5.2 @ n=400). c=1.5 assumed (matches the n400 launcher; no separate launcher found)."),

    # --- anchor-fraction v1 evals ---
    "af_v1_s200_n400_reanchor": dict(new_ckpt="af_v1", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="high", note="anchor-fraction af_v1 vs iter_01, sims=200, c=1.5, n=400 (job A of queue_2026_05_25). launch_queue_2026_05_25_5800x.sh. -4.3 at c=1.5 (the false-negative later RECOVERED to +30.5 at c=3 in phase3_af_c3). CONTRADICTION pair."),
    "anchor_fraction_v1_s200_eval": dict(new_ckpt="af_v1", new_c=1.5, old_ckpt="iter_01", old_c=1.5,
        conf="medium", note="anchor-fraction af_v1 vs iter_01 n=100 screen, sims=200. launch_xeon_afv1s200.sh (c=1.5). +6.9 @ n=100; same config as af_v1_s200_n400_reanchor (-4.3 @ n=400)."),

    # --- v3 anchor-gate (deepsearch_v3) ---
    "v3_anchor_gate": dict(new_ckpt="deepsearch_v3", new_c=3.0, old_ckpt="iter_01", old_c=3.0,
        conf="high", note="deepsearch_v3 vs iter_01 anchor, sims=200, c=3.0 (eval c), n=100. Config from /mnt/c/carc-shared/v3_verdict.json (eval_c_puct=3.0, anchor=iter_01). +17.4 marginal (1sigma), doesnt displace iter_B1."),

    # --- laptop overnight: iter_B1 vs deepsearch_v1 at sims=800 c=3 ---
    "b1_vs_ds_s800_n400_c3": dict(new_ckpt="iter_B1", new_c=3.0, old_ckpt="deepsearch_v1", old_c=3.0, new_sims=800, old_sims=800,
        conf="high", note="LAPTOP overnight: iter_B1 vs deepsearch_v1 at sims=800 c=3, n=400. STATUS verdict table. -4.3 = TIED (both checkpoints equivalent at sims=800 c=3 plane).", root=LAPTOP),
}

# Dirs that exist but are NOT completed evals (no elo_log.json) — documented so
# the absence is intentional, not an oversight.
SKIP_DIRS = {
    "checkpoints", "code_sync", "verify", "optuna_runs", "queue_2026_05_25",
    "deepsearch", "network_smoke", "anchor_fraction_v1_s200",
    "optionB_iter2_selfplay", "optionB_iter3_selfplay", "optionB_iter4_selfplay",
    "optionB_iter5_selfplay", "v3_anchor_gate",  # v3_anchor_gate handled via CONFIG below explicitly
    "optionB_iter5_eval",  # 314/2000 games, no elo_log — INCOMPLETE
}
# v3_anchor_gate DOES have an elo_log + CONFIG entry, so don't actually skip it.
SKIP_DIRS.discard("v3_anchor_gate")


def elo_from_wld(W, L, D):
    """Elo delta DERIVED from the win/loss/draw counts in this same row, so elo can
    never be inconsistent with its own W/L/D. elo = 400*log10(s/(1-s)),
    s = (W+0.5D)/n. (Fixes a backfill bug where promoted optuna trials paired the
    n=400 W/L/D with the n=100 screen elo.)"""
    n = W + L + D
    if n == 0:
        return None
    s = (W + 0.5 * D) / n
    if s <= 0:
        return -800.0
    if s >= 1:
        return 800.0
    return round(400.0 * math.log10(s / (1 - s)), 1)


def elo_sigma(W, L, D):
    """Standard error of the elo estimate from the binomial score.
    s = (W + 0.5D)/n ; SE(s) = sqrt(s(1-s)/n) ; SE(elo) = (400/ln10)*SE(s)/(s(1-s)).
    Falls back to 400/sqrt(n) at the s=0.5 limit (where the two coincide)."""
    n = W + L + D
    if n == 0:
        return None
    s = (W + 0.5 * D) / n
    if s <= 0 or s >= 1:
        return round(400.0 / math.sqrt(n), 1)
    se_s = math.sqrt(s * (1 - s) / n)
    se_elo = (400.0 / math.log(10)) * se_s / (s * (1 - s))
    return round(se_elo, 1)


def agg_games(eval_root):
    """Aggregate per-game JSONs: return (n, avg_diff_from_new_pov, sims)."""
    files = glob(os.path.join(eval_root, "**", "s*_seed*_p*.json"), recursive=True)
    diffs, sims_seen, n = [], set(), 0
    for f in files:
        try:
            with open(f) as fh:
                g = json.load(fh)
        except Exception:
            continue
        n += 1
        # diff field is already from the NEW side's POV (score_new - score_old):
        # per-game schema: won_by_new + diff. Confirm sign by new_player.
        d = g.get("diff")
        if d is not None:
            diffs.append(d)
        if "sims" in g:
            sims_seen.add(g["sims"])
    avg_diff = round(sum(diffs) / len(diffs), 2) if diffs else ""
    sims = sims_seen.pop() if len(sims_seen) == 1 else (sorted(sims_seen) if sims_seen else "")
    return n, avg_diff, sims


def dir_date(d, elo_json_path):
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(elo_json_path)).strftime("%Y-%m-%d")
    except Exception:
        return ""


def build_dir_rows():
    rows = []
    seen = set()
    # shared dirs + laptop
    candidates = [(d, SHARED) for d in sorted(os.listdir(SHARED))]
    candidates += [(d, LAPTOP) for d in sorted(os.listdir(LAPTOP))]
    for name, root in candidates:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        elo_path = os.path.join(path, "elo_log.json")
        if not os.path.isfile(elo_path):
            continue  # not a completed eval
        if name in seen:
            continue
        seen.add(name)
        with open(elo_path) as fh:
            log = json.load(fh)
        rec = log[0] if isinstance(log, list) else log
        W, L, D = rec.get("wins", 0), rec.get("losses", 0), rec.get("draws", 0)
        elo = elo_from_wld(W, L, D)  # derive, don't trust the stored elo_delta
        cfg = CONFIG.get(name)
        n_games, avg_diff, sims = agg_games(os.path.join(path, "eval"))
        n_total = W + L + D
        if cfg is None:
            rows.append(dict(
                exp_id=name, date=dir_date(name, elo_path), n=n_total,
                new_ckpt="", new_c="", new_cap="", new_var="", new_sims=sims,
                old_ckpt="", old_c="", old_cap="", old_var="", old_sims="",
                W=W, L=L, D=D, elo=elo, sigma=elo_sigma(W, L, D), avg_diff=avg_diff,
                src_dir=path, confidence="low",
                note="NO config recovered — dir not in mapping table. Outcome only.",
            ))
            continue
        new_var = cfg.get("new_var", DEF_VAR)
        old_var = cfg.get("old_var", DEF_VAR)
        new_cap = cfg.get("new_cap", DEF_CAP)
        old_cap = cfg.get("old_cap", DEF_CAP)
        new_sims = cfg.get("new_sims", sims if sims else 200)
        old_sims = cfg.get("old_sims", sims if sims else 200)
        rows.append(dict(
            exp_id=name, date=dir_date(name, elo_path), n=n_total,
            new_ckpt=CKPT.get(cfg["new_ckpt"], cfg["new_ckpt"]),
            new_c=cfg["new_c"], new_cap=new_cap, new_var=new_var, new_sims=new_sims,
            old_ckpt=CKPT.get(cfg["old_ckpt"], cfg["old_ckpt"]),
            old_c=cfg["old_c"], old_cap=old_cap, old_var=old_var, old_sims=old_sims,
            W=W, L=L, D=D, elo=elo, sigma=elo_sigma(W, L, D), avg_diff=avg_diff,
            src_dir=path, confidence=cfg["conf"], note=cfg["note"],
        ))
    return rows


def build_optuna_rows():
    """One row per COMPLETE optuna trial. OLD side fixed (c=1.5,cap=12,v2_7);
    NEW side = trial params. Both sides iter_B1, sims=200. Config IS in the data."""
    try:
        import optuna
    except ImportError:
        print("optuna not importable — skipping optuna rows")
        return []
    s = optuna.load_study(study_name=OPTUNA_STUDY, storage=OPTUNA_DB)
    rows = []
    for t in s.trials:
        if t.state.name != "COMPLETE":
            continue
        a = t.user_attrs
        W, L, D = a.get("wins"), a.get("losses"), a.get("draws")
        if W is None:
            continue  # running/failed trial with no result
        W, L, D = W or 0, L or 0, D or 0
        elo = elo_from_wld(W, L, D)  # derive from the n=400 (promoted) or n=100 W/L/D — NOT screen_elo
        promoted = a.get("promoted", False)
        n = W + L + D
        promote_n = a.get("promote_n")
        note = (f"Optuna trial #{t.number} ({a.get('worker_id','?')}). "
                f"{'PROMOTED n=' + str(promote_n) if promoted else 'screen-only n=' + str(a.get('screen_n', n))}. "
                f"NEW=trial params, OLD=fixed (c=1.5,cap=12,v2_7); both iter_B1, sims=200. "
                f"Config from trial.params (the one place config is in the data).")
        date = ""
        if t.datetime_complete:
            date = t.datetime_complete.strftime("%Y-%m-%d")
        rows.append(dict(
            exp_id=f"optuna_trial_{t.number:04d}", date=date, n=n,
            new_ckpt=CKPT["iter_B1"], new_c=t.params.get("c_puct"),
            new_cap=t.params.get("leaf_cap"), new_var=t.params.get("leaf_variant"), new_sims=200,
            old_ckpt=CKPT["iter_B1"], old_c=1.5, old_cap=12, old_var="v2_7", old_sims=200,
            W=W, L=L, D=D, elo=elo, sigma=elo_sigma(W, L, D), avg_diff="",
            src_dir=f"{SHARED}/optuna_runs/study.db#trial_{t.number}",
            confidence="high", note=note,
        ))
    return rows


COLS = ["exp_id", "date", "n", "new_ckpt", "new_c", "new_cap", "new_var", "new_sims",
        "old_ckpt", "old_c", "old_cap", "old_var", "old_sims",
        "W", "L", "D", "elo", "sigma", "avg_diff", "src_dir", "confidence", "note"]


def find_contradictions(rows):
    """Group rows by their full (new config) vs (old config) signature and flag
    any signature measured 2+ times with materially different elo (>20 elo apart,
    i.e. roughly >1 pooled sigma). This is the GOLD the table exists to surface."""
    from collections import defaultdict

    def sig(r):
        return (r["new_ckpt"], r["new_c"], r["new_cap"], r["new_var"], r["new_sims"],
                r["old_ckpt"], r["old_c"], r["old_cap"], r["old_var"], r["old_sims"])

    groups = defaultdict(list)
    for r in rows:
        if r["new_ckpt"] and r["old_ckpt"]:
            groups[sig(r)].append(r)
    out = []
    for s, rs in groups.items():
        if len(rs) < 2:
            continue
        elos = [r["elo"] for r in rs if r["elo"] is not None]
        if len(elos) < 2:
            continue
        if max(elos) - min(elos) > 20:
            out.append((s, rs))
    return out


def main():
    rows = build_dir_rows() + build_optuna_rows()
    rows.sort(key=lambda r: (r["confidence"] != "low", r["exp_id"]))
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"wrote {len(rows)} rows to {OUT_CSV}")
    from collections import Counter
    c = Counter(r["confidence"] for r in rows)
    print("confidence breakdown:", dict(c))

    contras = find_contradictions(rows)
    print(f"\n=== {len(contras)} CONFIG SIGNATURES MEASURED 2+ TIMES WITH >20 ELO POINT-SPREAD ===")
    print("(point-spread is a SCREEN for re-measurement candidates; the pooled-sigma")
    print(" separation below says whether the readings are actually inconsistent.)")
    for s, rs in contras:
        print(f"\nsignature: new(ckpt={s[0].split('/')[-2] if '/' in str(s[0]) else s[0]},c={s[1]},cap={s[2]},{s[3]},sims={s[4]})"
              f" vs old(c={s[6]},cap={s[7]},{s[8]},sims={s[9]})")
        for r in rs:
            print(f"  {r['exp_id']:<28} n={r['n']:<5} elo={r['elo']:>6} (sigma {r['sigma']})")
        # Pooled-sigma separation between the two extreme readings — distinguishes
        # a real contradiction from a wide-but-consistent point spread.
        lo = min(rs, key=lambda r: r["elo"]); hi = max(rs, key=lambda r: r["elo"])
        sl, sh = lo["sigma"] or 0, hi["sigma"] or 0
        pooled = math.sqrt(sl * sl + sh * sh)
        if pooled > 0:
            sep = (hi["elo"] - lo["elo"]) / pooled
            tag = ("CONSISTENT (within noise — not a real contradiction)" if sep < 1.0
                   else "MILD tension (re-measure to settle)" if sep < 2.0
                   else "REAL contradiction (>2sigma — something differs)")
            print(f"  -> {hi['elo']-lo['elo']:.1f} elo apart = {sep:.2f}sigma pooled  [{tag}]")


if __name__ == "__main__":
    main()
