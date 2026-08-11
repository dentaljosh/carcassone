#!/usr/bin/env python3
"""T3 joint Optuna/TPE knob sweep DRIVER (pre-registered design:
measurement/classical_search/OPTUNA_KNOB_SWEEP_DESIGN.md).

ONE joint 7-knob TPE screen over the classical PUCT champion's knobs, deck-paired
double-CRN vs the PINNED champion sibling (eval_puct_priors.py --opponent puct
--opp-pin-champion), objective = paired_mean_margin (cand - champ), maximized.

Structurally (design §1/§4/§6):
  * STRICTLY SEQUENTIAL trials, ONE driver (local primary). Game-level (NOT trial-
    level) two-box parallelism: each cell is spread across boxes by the harness's
    --shared-claim work-stealing; the laptop helper (optuna_knob_helper.sh) joins the
    cell named in CURRENT_CELL.json. NO SQLite-over-CIFS (corruption-prone) — the study
    lives on LOCAL disk.
  * TPESampler(multivariate=True, n_startup_trials=12, seed=20260714), direction=max.
  * Nested SUCCESSIVE HALVING as DRIVER logic (NOT optuna pruners): rung A n=40 all 32,
    rung B n=120 top-10, rung C n=240 top-4 — nested extensions of the SAME cell on the
    SAME CRN band (the harness per-seed cache replays an extension for free). The optuna
    trial value = the rung-A objective only (uniform fidelity -> unbiased TPE).
  * study.best_trial is NOT the verdict; the rung-C table in T3_OPTUNA_PROGRESS.tsv is.
  * Emission exactness: at scale==1.0 the leaf list/dict is emitted VERBATIM so trial-0
    (the enqueued champion) has leaf hash == the champion hash exactly.

⚠️ NO-TOUCH: governance/PRODUCTION.yaml is never read or written. Stage-1 cells pass
   --no-results-csv (46 sub-screen rows would flood the table; a single summary row is
   written at Stage-1 close-out by the operator, per the design "No-touch").

⚠️ §5(e): the champion side is the CURVE125 champion. This driver EXPORTS the curve125
   leaf env at import (setdefault, BEFORE importing carcassonne_ai) and HARD-GUARDS that
   DEFAULT_CONFIG resolves to the curve125 hash (verify_champion_env) before any compute
   — the harness _CANON_ENV setdefaults the STALE curve100, so a missing export would
   silently run the WRONG champion. The subprocess harness inherits this env.

Usage (design §12/§6):
  # dry-run: print all 32-cell local argv (no compute, in-memory study):
  .venv/bin/python scripts/classical_search/optuna_knob_sweep.py --dry-run
  # LOCAL micro-study (S0b): 3 trials x n=8, scratch dirs, band 2.009e10:
  ... --stage micro --n-trials 3 --rung-a-n 8 --band 20090000000 \
      --study-dir /tmp/t3_micro --share /tmp/t3_micro/share --workers 8 \
      --tsv /tmp/t3_micro/PROGRESS.tsv --no-current-cell
  # full Stage-1 (orchestrator only; detached, nice -n 19, census first):
  nice -n 19 setsid .venv/bin/python scripts/classical_search/optuna_knob_sweep.py \
      --stage s1 --workers 30 </dev/null &
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

# --- §5(e): export the curve125 champion leaf env BEFORE importing carcassonne_ai ---
# (setdefault, so an explicitly-exported curve wins and is caught by verify_champion_env;
#  matches c7_s1_launcher.sh lines 80-83, the ADOPTED champion, NOT the stale curve100.)
_CURVE125_ENV = {
    "CARCASSONNE_V25_CAP": "8", "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-10,-5,-1.25,0,2.5,3.75,5,6.25",
    "CARCASSONNE_V25_MEEPLE_K": "2.0", "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1", "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _CURVE125_ENV.items():
    os.environ.setdefault(_k, _v)

REPO = Path(__file__).resolve().parent.parent.parent
PY = str(REPO / ".venv" / "bin" / "python")
HARNESS = str(REPO / "scripts" / "classical_search" / "eval_puct_priors.py")
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))
sys.path.insert(0, str(REPO / "src"))

import optuna  # noqa: E402
from optuna.trial import TrialState  # noqa: E402

from c5_leaf_override import _leaf_dict, _leaf_hash  # noqa: E402
from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: E402

# ---- Champion anchors (§2). Derived from DEFAULT_CONFIG so emission is exact against
# whatever the resolved champion leaf is; the hash guard below pins it to curve125. ----
CHAMP = {
    "c_puct": 1.5, "tau_p": 5.0, "value_norm": 15.0,
    "curve_scale": 1.0, "pclose_scale": 1.0,
    "bonus_cap": float(DEFAULT_CONFIG.bonus_cap),
    "opp_bonus_cap": float(DEFAULT_CONFIG.opp_bonus_cap),
}
CHAMP_CURVE = tuple(float(x) for x in DEFAULT_CONFIG.v29_meeple_curve)
CHAMP_CLOSURE_P = {int(k): float(v) for k, v in DEFAULT_CONFIG.closure_p.items()}
EXPECTED_CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"   # curve125 (§5e; verified 2026-07-14)

# Trial-1 anchor (§1(5)): curve_scale 1.4-relative = base x1.75 (the known clair plateau
# point), a weak positive/plateau control; every other knob at champion.
CURVE14_PARAMS = {**{k: CHAMP[k] for k in CHAMP}, "curve_scale": 1.4}

# ---- 7-knob space (§2): (low, high, log, round-dp) ----
SPACE = {
    "c_puct":        (1.00, 2.25, False, 2),
    "tau_p":         (3.00, 8.00, True,  2),
    "value_norm":    (10.0, 22.0, True,  2),
    "curve_scale":   (0.80, 1.45, False, 3),
    "pclose_scale":  (0.80, 1.30, False, 3),
    "bonus_cap":     (5.00, 12.0, False, 2),
    "opp_bonus_cap": (6.50, 10.0, False, 2),
}
KNOB_ORDER = list(SPACE)

TSV_HEADER = ["trial", "rung", "status", "n", "W", "D", "L", "elo", "sigma",
              "paired_margin", "paired_z", "ms_ratio", "fresh_margin", "secs",
              "params_json", "ts"]


# --------------------------------------------------------------------------- #
# §5(e) champion-env guard                                                     #
# --------------------------------------------------------------------------- #
def verify_champion_env() -> str:
    """Fail LOUD unless DEFAULT_CONFIG is the curve125 champion (the §5e wrong-champion
    trap: the harness _CANON_ENV setdefaults the stale curve100). Returns the hash."""
    h = _leaf_hash(DEFAULT_CONFIG)
    if h != EXPECTED_CHAMP_LEAF_HASH:
        raise SystemExit(
            f"[t3-optuna] REFUSING TO RUN: champion leaf hash {h} != curve125 "
            f"{EXPECTED_CHAMP_LEAF_HASH}. Export the curve125 env (c7_s1_launcher.sh "
            f"lines 80-83) BEFORE launching — the harness default is the stale curve100. "
            f"resolved curve={list(CHAMP_CURVE)}")
    return h


# --------------------------------------------------------------------------- #
# Parameter suggestion + emission (§2)                                         #
# --------------------------------------------------------------------------- #
def suggest_params(trial: "optuna.Trial") -> dict:
    """Suggest + ROUND the 7 knobs (rounded values ARE the trial, §2), stash the rounded
    dict as a user_attr so a resumed/ranked cell is reproducible from the study alone."""
    out = {}
    for knob in KNOB_ORDER:
        lo, hi, log, dp = SPACE[knob]
        out[knob] = round(trial.suggest_float(knob, lo, hi, log=log), dp)
    trial.set_user_attr("cell_params", out)
    return out


def leaf_json(params: dict) -> dict:
    """Emit the candidate leaf JSON (replace-fields on DEFAULT_CONFIG). EMISSION
    EXACTNESS (§2): at scale==1.0 emit the champion list/dict VERBATIM (no float-repr
    drift) so a scale-1 trial's leaf hash == the champion hash. curve_scale multiplies
    each curve125 entry; pclose_scale multiplies each closure_p value; caps set direct."""
    cs = params["curve_scale"]
    ps = params["pclose_scale"]
    curve = (list(CHAMP_CURVE) if cs == 1.0
             else [round(x * cs, 6) for x in CHAMP_CURVE])
    closure = ({str(k): CHAMP_CLOSURE_P[k] for k in sorted(CHAMP_CLOSURE_P)} if ps == 1.0
               else {str(k): round(CHAMP_CLOSURE_P[k] * ps, 6) for k in sorted(CHAMP_CLOSURE_P)})
    return {
        "v29_meeple_curve": curve,
        "closure_p": closure,
        "bonus_cap": float(params["bonus_cap"]),
        "opp_bonus_cap": float(params["opp_bonus_cap"]),
    }


def cand_leaf_hash(params: dict) -> str:
    """Resolve the emitted leaf JSON to a LeafConfig hash (for the emission-exactness
    gate). Imports the harness parser so the coercion is identical to a real cell."""
    from c5_leaf_override import _load_cand_leaf_cfg
    return _leaf_hash(_load_cand_leaf_cfg(json.dumps(leaf_json(params))))


# --------------------------------------------------------------------------- #
# Harness argv assembly + CURRENT_CELL.json protocol                          #
# --------------------------------------------------------------------------- #
def _knob_args(params: dict) -> list:
    """The candidate-only knob args (search knobs on the CLI, leaf knobs inline JSON).
    value_norm is candidate-only (opponent pinned to CHAMP_PUCT_VALUE_NORM); c_puct/tau_p
    are isolated by --opp-pin-champion. leaf_quantize/final_select are fixed champion."""
    return [
        "--c-puct", f"{params['c_puct']:g}",
        "--tau-p", f"{params['tau_p']:g}",
        "--value-norm", f"{params['value_norm']:g}",
        "--cand-leaf-json", json.dumps(leaf_json(params)),
    ]


def _base_argv(params, n, sub, exp_id, band, out_root, sims, exact_k) -> list:
    """The harness base argv (no worker/claim flags) — used for the launch loop AND the
    final aggregate. Fixed knobs match the C5/C7 screen convention (§6)."""
    return [PY, HARNESS,
            "--candidate", "puct", "--opponent", "puct", "--opp-pin-champion",
            "--leaf-quantize", "float", "--final-select", "visits",
            "--cand-sims", str(sims), "--exact-k", str(exact_k),
            "--n", str(n), "--paired",
            "--seed-start", str(band),
            "--out-root", out_root, "--out-subdir", sub,
            "--exp-id", exp_id, "--no-results-csv"] + _knob_args(params)


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)   # atomic on POSIX — the helper never sees a half-written file


def write_current_cell(cur_path, params, n, sub, exp_id, band, sims, exact_k,
                       trial_num, rung) -> None:
    """Atomically publish the cell the laptop helper should JOIN (design §4). Stores
    share-relative pieces; the helper reconstructs its own SHARE mount + workers 22."""
    _atomic_write_json(Path(cur_path), {
        "status": "active", "trial": trial_num, "rung": rung, "exp_id": exp_id,
        "out_subdir": sub, "n": int(n), "seed_start": int(band),
        "sims": int(sims), "exact_k": int(exact_k),
        "knob_args": _knob_args(params), "ts": time.time(),
    })


def mark_current_cell_done(cur_path) -> None:
    if cur_path:
        _atomic_write_json(Path(cur_path), {"status": "done", "ts": time.time()})


# --------------------------------------------------------------------------- #
# Cell execution (iterate-until-count + aggregate) and reading                 #
# --------------------------------------------------------------------------- #
_SEED_RE = re.compile(r"seed(\d{12})_a(\d)\.json$")


def _count_results(cell_dir: Path) -> int:
    return sum(1 for p in cell_dir.glob("seed*_a*.json") if _SEED_RE.search(p.name))


def _clean_stale_claims(cell_dir: Path, min_age_min: float | None = None) -> None:
    for c in cell_dir.glob("seed*.claim"):
        if min_age_min is not None:
            if (time.time() - c.stat().st_mtime) < min_age_min * 60:
                continue
        if not c.with_suffix(".json").exists():
            c.unlink(missing_ok=True)


def run_cell(params, n, sub, exp_id, band, out_root, sims, exact_k, workers,
             claim_host, claim_stale, max_iter, dry_run_log=None) -> dict | None:
    """Play/aggregate one cell to n paired games and return its summary.json. Primary
    role: iterate the harness (--shared-claim work-stealing, laptop may join) until n
    results exist, then a final no-worker aggregate writes summary.json. The per-seed
    cache makes an extension (rung B/C) replay the already-played decks for free."""
    cell_dir = Path(out_root) / sub
    base = _base_argv(params, n, sub, exp_id, band, out_root, sims, exact_k)
    if dry_run_log is not None:
        # dry-run touches NOTHING on disk (no mkdir) — pure argv preview
        dry_run_log.append(base + ["--workers", str(workers), "--shared-claim",
                                   "--claim-host", claim_host, "--claim-stale-secs",
                                   str(claim_stale)])
        return None
    cell_dir.mkdir(parents=True, exist_ok=True)
    _clean_stale_claims(cell_dir, None)   # primary force-cleans orphan claims at cell start
    it = 0
    while _count_results(cell_dir) < n and it < max_iter:
        log = cell_dir / f"_launch_iter{it}.log"
        with open(log, "w") as fh:
            subprocess.run(base + ["--workers", str(workers), "--shared-claim",
                                   "--claim-host", claim_host,
                                   "--claim-stale-secs", str(claim_stale)],
                           stdout=fh, stderr=subprocess.STDOUT, cwd=str(REPO))
        _clean_stale_claims(cell_dir, 4)
        it += 1
        if _count_results(cell_dir) < n:
            time.sleep(3)
    if _count_results(cell_dir) < n:
        return None   # STALLED — caller flags UNRELIABLE
    # final aggregate (no workers/claim): reads cached -> writes summary.json
    agg = cell_dir / "_aggregate.log"
    with open(agg, "w") as fh:
        subprocess.run(base, stdout=fh, stderr=subprocess.STDOUT, cwd=str(REPO))
    summ_path = cell_dir / "summary.json"
    if not summ_path.exists():
        return None
    return json.loads(summ_path.read_text())


def fresh_slice_margin(cell_dir: Path, band: int, lo_deck: int, hi_deck: int) -> float | None:
    """Paired seat-balanced margin over decks [lo_deck, hi_deck) ONLY (the never-selected-on
    slice; rung-C diagnostic §6). Reads per-seed jsons directly (diff = cand-champ)."""
    by_seed: dict[int, dict[int, float]] = {}
    for p in cell_dir.glob("seed*_a*.json"):
        m = _SEED_RE.search(p.name)
        if not m:
            continue
        seed, a = int(m.group(1)), int(m.group(2))
        deck = seed - band
        if lo_deck <= deck < hi_deck:
            try:
                by_seed.setdefault(seed, {})[a] = float(json.loads(p.read_text())["diff"])
            except (json.JSONDecodeError, KeyError, OSError):
                continue
    ds = [(v[0] + v[1]) / 2.0 for v in by_seed.values() if 0 in v and 1 in v]
    return (sum(ds) / len(ds)) if ds else None


# --------------------------------------------------------------------------- #
# Journaling: TSV (human) + per-trial RUNGS.json (durable per-rung margins)    #
# --------------------------------------------------------------------------- #
def _ms_ratio(summ: dict) -> float:
    c = summ.get("cand_prefix_ms_per_move") or 0.0
    o = summ.get("champ_prefix_ms_per_move") or 0.0
    return (c / o) if o else float("nan")


def _hygiene_ok(summ: dict) -> bool:
    """§4 trial hygiene: game_timeouts > 2% of games -> UNRELIABLE."""
    n = summ.get("n", 0)
    to = summ.get("game_timeouts", 0) or 0
    return (to / (n + to)) <= 0.02 if (n + to) else False


def journal_tsv(tsv_path: Path, trial_num, rung, status, summ, secs,
                params, fresh=None) -> None:
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    if not tsv_path.exists():
        tsv_path.write_text("\t".join(TSV_HEADER) + "\n")
    if summ is None:
        row = [trial_num, rung, status, "-", "-", "-", "-", "-", "-", "-", "-", "-",
               "-", secs, json.dumps(params, sort_keys=True), time.strftime("%F_%T")]
    else:
        pm = summ.get("paired_mean_margin")
        pz = summ.get("paired_z")
        row = [trial_num, rung, status, summ.get("n"), summ.get("W"), summ.get("D"),
               summ.get("L"), f"{summ.get('elo', float('nan')):.1f}",
               f"{summ.get('elo_sig_1sigma', float('nan')):.1f}",
               ("nan" if pm is None else f"{pm:+.3f}"),
               ("nan" if pz is None else f"{pz:+.2f}"),
               f"{_ms_ratio(summ):.2f}",
               ("-" if fresh is None else f"{fresh:+.3f}"),
               secs, json.dumps(params, sort_keys=True), time.strftime("%F_%T")]
    with open(tsv_path, "a") as fh:
        fh.write("\t".join(str(x) for x in row) + "\n")


def rungs_path(study_dir: Path, trial_num: int) -> Path:
    return study_dir / f"t{trial_num:03d}" / "RUNGS.json"


def load_rungs(study_dir: Path, trial_num: int) -> dict:
    p = rungs_path(study_dir, trial_num)
    if p.exists():
        return json.loads(p.read_text())
    return {"trial": trial_num, "rungs": {}}


def save_rung(study_dir: Path, trial_num, params, exp_id, rung, summ, fresh=None) -> None:
    """Durable per-rung margin store (design §4). Ranking + verdict read THIS, not
    summary.json (which reflects only the last-run n and is overwritten by extensions)."""
    rec = load_rungs(study_dir, trial_num)
    rec["params"] = params
    rec["exp_id"] = exp_id
    rec.setdefault("rungs", {})[rung] = {
        "n": summ.get("n"), "W": summ.get("W"), "D": summ.get("D"), "L": summ.get("L"),
        "elo": summ.get("elo"), "paired_margin": summ.get("paired_mean_margin"),
        "paired_z": summ.get("paired_z"), "ms_ratio": _ms_ratio(summ),
        "hygiene_ok": _hygiene_ok(summ), "fresh_margin": fresh,
        "ts": time.strftime("%F_%T"),
    }
    p = rungs_path(study_dir, trial_num)
    _atomic_write_json(p, rec)


def rung_margin(study_dir: Path, trial_num: int, rung: str):
    r = load_rungs(study_dir, trial_num)["rungs"].get(rung)
    if r is None or not r.get("hygiene_ok", True):
        return None
    return r.get("paired_margin")


# --------------------------------------------------------------------------- #
# Study lifecycle + sequential rung driver                                    #
# --------------------------------------------------------------------------- #
def build_study(storage_url, sampler_seed, in_memory=False):
    sampler = optuna.samplers.TPESampler(multivariate=True, n_startup_trials=12,
                                         seed=sampler_seed)
    return optuna.create_study(
        study_name="t3_knob_sweep", direction="maximize", sampler=sampler,
        storage=(None if in_memory else storage_url), load_if_exists=not in_memory)


def enqueue_anchors_if_fresh(study) -> None:
    """Enqueue trial-0 (champion) + trial-1 (curve1.4rel) ONLY on a brand-new study —
    re-enqueue on resume would duplicate the WAITING trials (§1(5)/§4)."""
    if len(study.get_trials(deepcopy=False)) == 0:
        study.enqueue_trial({k: CHAMP[k] for k in KNOB_ORDER})       # trial 0
        study.enqueue_trial({k: CURVE14_PARAMS[k] for k in KNOB_ORDER})  # trial 1


def _n_complete(study) -> int:
    return sum(1 for t in study.get_trials(deepcopy=False)
               if t.state == TrialState.COMPLETE)


def run_rung_A(study, cfg) -> None:
    """Play all n_trials cells at rung-A n, tell the study the paired margin. Resume-safe:
    re-drives crashed RUNNING trials (their params are persisted), skips COMPLETE ones."""
    # re-drive any RUNNING trial left by a crash (params already fixed at ask-time)
    for t in study.get_trials(deepcopy=False):
        if t.state == TrialState.RUNNING:
            params = t.user_attrs.get("cell_params")
            if not params or any(k not in params for k in KNOB_ORDER):
                study.tell(t.number, state=TrialState.FAIL)   # asked but never suggested
                continue
            _play_rung_A_trial(study, t.number, params, cfg, redriving=True)

    # bound total asks so persistent UNRELIABLE cells can't loop forever (design: ~0
    # failures expected at K=2; a runaway here means a harness/env problem — surface it)
    max_total = cfg.n_trials * 2
    while _n_complete(study) < cfg.n_trials:
        if len(study.get_trials(deepcopy=False)) >= max_total:
            print(f"[t3-optuna] ABORT rung A: {len(study.get_trials(deepcopy=False))} trials "
                  f"created but only {_n_complete(study)}/{cfg.n_trials} COMPLETE — persistent "
                  f"UNRELIABLE/stall; investigate the harness/env before continuing.", flush=True)
            raise SystemExit(2)
        trial = study.ask()
        params = suggest_params(trial)
        _play_rung_A_trial(study, trial.number, params, cfg, trial_obj=trial)


def _play_rung_A_trial(study, trial_num, params, cfg, trial_obj=None, redriving=False):
    exp_id = f"t3_opt_t{trial_num:03d}"
    sub = f"{cfg.subdir_prefix}/t{trial_num:03d}"
    tag = "REDRIVE" if redriving else "ask"
    print(f"[t3-optuna] rung A trial {trial_num} ({tag}) params={params}", flush=True)
    if cfg.current_cell:
        write_current_cell(cfg.current_cell, params, cfg.rung_a_n, sub, exp_id,
                           cfg.band, cfg.sims, cfg.exact_k, trial_num, "A")
    t0 = time.time()
    summ = run_cell(params, cfg.rung_a_n, sub, exp_id, cfg.band, cfg.out_root,
                    cfg.sims, cfg.exact_k, cfg.workers, cfg.claim_host,
                    cfg.claim_stale, cfg.max_iter)
    secs = int(time.time() - t0)
    if summ is None or summ.get("paired_mean_margin") is None:
        journal_tsv(cfg.tsv, trial_num, "A", "UNRELIABLE", summ, secs, params)
        save_rung(cfg.study_dir, trial_num, params, exp_id, "A", summ or {})
        study.tell(trial_num, state=TrialState.FAIL)
        return
    status = "DONE" if _hygiene_ok(summ) else "UNRELIABLE"
    journal_tsv(cfg.tsv, trial_num, "A", status, summ, secs, params)
    save_rung(cfg.study_dir, trial_num, params, exp_id, "A", summ)
    if status == "UNRELIABLE":
        study.tell(trial_num, state=TrialState.FAIL)
    else:
        study.tell(trial_num, float(summ["paired_mean_margin"]))


def _rank_by_rung(study, study_dir, rung, keep):
    """Rank COMPLETE trials by their durable rung margin (desc); top `keep`. Reads
    RUNGS.json (not summary.json — extensions overwrite the latter)."""
    scored = []
    for t in study.get_trials(deepcopy=False):
        if t.state != TrialState.COMPLETE:
            continue
        m = rung_margin(study_dir, t.number, rung)
        if m is not None:
            scored.append((m, t.number, t.user_attrs.get("cell_params")))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:keep]


def run_extension_rung(study, cfg, from_rung, this_rung, n, keep) -> list:
    """Rung B/C: extend the top-`keep` cells (by from_rung margin) to n on the SAME
    band/cell (cache replays played decks). Returns [(margin, trial, params), ...]."""
    top = _rank_by_rung(study, cfg.study_dir, from_rung, keep)
    print(f"[t3-optuna] rung {this_rung}: extending top-{keep} by rung-{from_rung} "
          f"margin -> trials {[t[1] for t in top]}", flush=True)
    for margin, trial_num, params in top:
        # resume: skip if this rung already durably recorded for the trial
        existing = load_rungs(cfg.study_dir, trial_num)["rungs"].get(this_rung)
        if existing is not None and existing.get("n", 0) >= n:
            print(f"[t3-optuna]   trial {trial_num} rung {this_rung} cached "
                  f"(n={existing.get('n')})", flush=True)
            continue
        exp_id = f"t3_opt_t{trial_num:03d}"
        sub = f"{cfg.subdir_prefix}/t{trial_num:03d}"
        if cfg.current_cell:
            write_current_cell(cfg.current_cell, params, n, sub, exp_id, cfg.band,
                               cfg.sims, cfg.exact_k, trial_num, this_rung)
        t0 = time.time()
        summ = run_cell(params, n, sub, exp_id, cfg.band, cfg.out_root, cfg.sims,
                        cfg.exact_k, cfg.workers, cfg.claim_host, cfg.claim_stale,
                        cfg.max_iter)
        secs = int(time.time() - t0)
        fresh = None
        if this_rung == "C" and summ is not None:
            # fresh slice = decks [rung_b_n/2, rung_c_n/2) (never selected-on)
            fresh = fresh_slice_margin(Path(cfg.out_root) / sub, cfg.band,
                                       cfg.rung_b_n // 2, cfg.rung_c_n // 2)
        status = ("UNRELIABLE" if (summ is None or not _hygiene_ok(summ)) else "DONE")
        journal_tsv(cfg.tsv, trial_num, this_rung, status, summ, secs, params, fresh)
        save_rung(cfg.study_dir, trial_num, params, exp_id, this_rung, summ or {}, fresh)
    return _rank_by_rung(study, cfg.study_dir, this_rung, keep)


def stage1_verdict(study, cfg) -> None:
    """Read the rung-C table (the verdict — NOT study.best_trial). FIRE = best rung-C
    paired Δ ≥ +30 AND paired_z ≥ +2.0 at rung-C n (§6). Reports the winner's fresh-slice
    diagnostic + top-4 coherence; STOP either way (Stage-2 is a separate operator run)."""
    rows = []
    for t in study.get_trials(deepcopy=False):
        r = load_rungs(cfg.study_dir, t.number)["rungs"].get("C")
        if r and r.get("paired_margin") is not None:
            rows.append((t.number, r))
    if not rows:
        print("[t3-optuna] STAGE-1 VERDICT: no rung-C cells completed — INCONCLUSIVE")
        return
    rows.sort(key=lambda x: x[1]["paired_margin"], reverse=True)
    print("\n=== T3 STAGE-1 rung-C table (THE verdict; study.best_trial is NOT it) ===")
    for num, r in rows:
        pz = r.get("paired_z")
        print(f"  trial {num}: margin {r['paired_margin']:+.3f} pts/deck  "
              f"elo {r.get('elo', float('nan')):+.1f}  z {('nan' if pz is None else f'{pz:+.2f}')}  "
              f"fresh {('-' if r.get('fresh_margin') is None else f'{r['fresh_margin']:+.3f}')}  "
              f"n={r.get('n')}")
    best_num, best = rows[0]
    best_elo = best.get("elo", 0.0)
    best_z = best.get("paired_z") or 0.0
    fire = (best_elo >= 30.0) and (best_z >= 2.0)
    print(f"\n[t3-optuna] STAGE-1 {'FIRE' if fire else 'NULL'}: best trial {best_num} "
          f"elo {best_elo:+.1f} z {best_z:+.2f} (gate +30 / z2.0). "
          f"{'-> operator runs Stage-2 (fresh band 2.01e10, top-3, n=400).' if fire else '-> STOP; six-touch null close-out (§9).'}")


# --------------------------------------------------------------------------- #
# Dry-run: print all n_trials LOCAL argv without compute (in-memory study)     #
# --------------------------------------------------------------------------- #
def do_dry_run(cfg) -> int:
    print(f"[t3-optuna DRY-RUN] champion leaf hash = {verify_champion_env()} (curve125)")
    print(f"[t3-optuna DRY-RUN] trial-0 (champion) cand leaf hash = {cand_leaf_hash(CHAMP)} "
          f"(must == champion {EXPECTED_CHAMP_LEAF_HASH}: "
          f"{'OK' if cand_leaf_hash(CHAMP) == EXPECTED_CHAMP_LEAF_HASH else 'MISMATCH!'})")
    study = build_study(None, cfg.sampler_seed, in_memory=True)
    enqueue_anchors_if_fresh(study)
    print(f"[t3-optuna DRY-RUN] {cfg.n_trials} trials (0-1 enqueued ANCHORS exact; 2-11 "
          f"QMC startup exact; 12+ TPE ILLUSTRATIVE — real params depend on live margins):\n")
    for i in range(cfg.n_trials):
        trial = study.ask()
        params = suggest_params(trial)
        kind = ("ANCHOR" if i < 2 else "startup" if i < 12 else "TPE~illustrative")
        sub = f"{cfg.subdir_prefix}/t{trial.number:03d}"
        log = []
        run_cell(params, cfg.rung_a_n, sub, f"t3_opt_t{trial.number:03d}", cfg.band,
                 cfg.out_root, cfg.sims, cfg.exact_k, cfg.workers, cfg.claim_host,
                 cfg.claim_stale, cfg.max_iter, dry_run_log=log)
        lh = cand_leaf_hash(params)
        print(f"# trial {trial.number:2d} [{kind}] params={params} leaf_hash={lh}")
        print("  " + " ".join(_q(a) for a in log[0]) + "\n")
        study.tell(trial, 0.0)   # dummy so the loop advances (in-memory only)
    return 0


def _q(a: str) -> str:
    return f"'{a}'" if (" " in a or '"' in a or "{" in a) else a


# --------------------------------------------------------------------------- #
class _Cfg:
    pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="optuna_knob_sweep",
                                 description="T3 joint Optuna/TPE knob sweep driver")
    ap.add_argument("--stage", choices=("s1", "micro"), default="s1",
                    help="s1 = full Stage-1 (rungs A/B/C); micro = rung-A only (S0b smoke)")
    ap.add_argument("--n-trials", type=int, default=32, help="total trials (§6: 32)")
    ap.add_argument("--rung-a-n", type=int, default=52)
    ap.add_argument("--rung-b-n", type=int, default=120)
    ap.add_argument("--rung-c-n", type=int, default=240)
    ap.add_argument("--rung-b-keep", type=int, default=10)
    ap.add_argument("--rung-c-keep", type=int, default=4)
    ap.add_argument("--band", type=int, default=20_000_000_000, help="CRN seed band (§4: S1=2.00e10)")
    ap.add_argument("--sims", type=int, default=2750)
    ap.add_argument("--exact-k", type=int, default=2)
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--share", type=str, default="/mnt/c/carc-shared",
                    help="SHARE root; cells land under <share>/classical_search/<subdir-prefix>/t###")
    ap.add_argument("--subdir-prefix", type=str, default="t3_optuna")
    ap.add_argument("--study-dir", type=str,
                    default=str(REPO / "data" / "classical_search" / "t3_optuna"),
                    help="LOCAL disk: study.db + per-trial t###/RUNGS.json (never the CIFS share)")
    ap.add_argument("--tsv", type=str,
                    default=str(REPO / "measurement" / "classical_search" / "T3_OPTUNA_PROGRESS.tsv"))
    ap.add_argument("--current-cell", type=str, default=None,
                    help="CURRENT_CELL.json path for the laptop helper (default: "
                         "<share>/classical_search/<subdir-prefix>/CURRENT_CELL.json)")
    ap.add_argument("--no-current-cell", action="store_true",
                    help="local-only: skip the two-box CURRENT_CELL.json pointer (S0b)")
    ap.add_argument("--claim-host", type=str, default=f"t3-primary-{socket.gethostname()}")
    ap.add_argument("--claim-stale", type=int, default=300)
    ap.add_argument("--max-iter", type=int, default=60, help="max harness re-invocations per cell")
    ap.add_argument("--sampler-seed", type=int, default=20260714)
    ap.add_argument("--dry-run", action="store_true",
                    help="print all n-trials LOCAL argv (in-memory study; no compute, no writes)")
    args = ap.parse_args(argv)

    cfg = _Cfg()
    cfg.n_trials = args.n_trials
    cfg.rung_a_n = args.rung_a_n
    cfg.rung_b_n = args.rung_b_n
    cfg.rung_c_n = args.rung_c_n
    cfg.band = args.band
    cfg.sims = args.sims
    cfg.exact_k = args.exact_k
    cfg.workers = args.workers
    cfg.out_root = str(Path(args.share) / "classical_search")
    cfg.subdir_prefix = args.subdir_prefix
    cfg.study_dir = Path(args.study_dir)
    cfg.tsv = Path(args.tsv)
    cfg.claim_host = args.claim_host
    cfg.claim_stale = args.claim_stale
    cfg.max_iter = args.max_iter
    cfg.sampler_seed = args.sampler_seed
    if args.no_current_cell:
        cfg.current_cell = None
    else:
        cfg.current_cell = args.current_cell or str(
            Path(cfg.out_root) / cfg.subdir_prefix / "CURRENT_CELL.json")

    if args.dry_run:
        return do_dry_run(cfg)

    h = verify_champion_env()
    print(f"[t3-optuna] champion leaf hash {h} (curve125) OK; band {cfg.band} "
          f"stage={args.stage} n_trials={cfg.n_trials} workers={cfg.workers}", flush=True)
    cfg.study_dir.mkdir(parents=True, exist_ok=True)
    storage_url = f"sqlite:///{cfg.study_dir / 'study.db'}"
    study = build_study(storage_url, cfg.sampler_seed)
    enqueue_anchors_if_fresh(study)

    run_rung_A(study, cfg)
    if args.stage == "micro":
        print(f"[t3-optuna] MICRO stage done: {_n_complete(study)} rung-A trials complete "
              f"(study {cfg.study_dir / 'study.db'}, TSV {cfg.tsv})")
        mark_current_cell_done(cfg.current_cell)
        return 0

    run_extension_rung(study, cfg, "A", "B", cfg.rung_b_n, args.rung_b_keep)
    run_extension_rung(study, cfg, "B", "C", cfg.rung_c_n, args.rung_c_keep)
    stage1_verdict(study, cfg)
    mark_current_cell_done(cfg.current_cell)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
