#!/usr/bin/env python3
"""RoD v2.8 OVERNIGHT FLYWHEEL — per-iteration cheap screen + manifest/log/csv updater.

Called by scripts/rod_v28/run_overnight_flywheel.sh after each iter's train (+ optional
smoke). It is the SINGLE place that:
  1. reads the train .metrics.json (loss curves, entropy, value corr, provenance),
  2. hashes the new checkpoint,
  3. (optional) parses the tiny net-vs-net SMOKE dir (A=new vs B=parent) — a CATASTROPHE
     DETECTOR ONLY, never a strength verdict (n is far too small),
  4. runs the cheap health screens (collapse / entropy-floor / NaN / val-loss blowup),
  5. APPENDS rows to the deliverables: CHECKPOINT_MANIFEST.json, TRAINING_LOG_SUMMARY.md,
     CHEAP_SCREEN_RESULTS.csv (idempotent on --iter; re-running replaces that iter's row),
  6. prints `VERDICT=HEALTHY|COLLAPSE|AMBIGUOUS` and exits 0 (healthy/ambiguous, keep going)
     or 3 (collapse → the driver STOPS the chain and preserves artifacts).

NO production edits, NO promotion — pure measurement bookkeeping.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _isnan(x):
    try:
        return math.isnan(float(x))
    except (TypeError, ValueError):
        return True


def parse_smoke(smoke_dir):
    """A=new checkpoint, B=parent. Returns dict with W/L/D for A, winrate, rough elo, n.
    Reads v28_net_vs_net_orch.py per-game json (keys: won_by_a, drew)."""
    if not smoke_dir or not os.path.isdir(smoke_dir):
        return None
    w = d = n = 0
    import glob

    for jf in glob.glob(os.path.join(smoke_dir, "*.json")):
        if jf.endswith(".partial.json"):
            continue
        try:
            r = json.load(open(jf))
        except Exception:
            continue
        n += 1
        if r.get("drew"):
            d += 1
        elif r.get("won_by_a"):
            w += 1
    if n == 0:
        return None
    losses = n - w - d
    wr = (w + 0.5 * d) / n
    eps = 0.5 / n
    wrc = min(1 - eps, max(eps, wr))
    elo = 400 * math.log10(wrc / (1 - wrc))
    sig = (400 / math.log(10)) * math.sqrt(wrc * (1 - wrc) / n) / (wrc * (1 - wrc))
    return {"a_w": w, "a_l": losses, "a_d": d, "n": n, "wr": wr, "elo": elo, "sigma": sig}


def screen(metrics, smoke, smoke_catastrophe_wr, val_pol_collapse_thresh=1.0):
    """Return (verdict, reasons[]). verdict in HEALTHY|COLLAPSE|AMBIGUOUS.

    ``val_pol_collapse_thresh`` (default 1.0) is the absolute val_pol_loss COLLAPSE
    threshold for check #3a. The 1.0 default is tuned for SHARP self-play MCTS policy
    targets (healthy ~0.27). SOFT targets — e.g. a fair-champion POOLED-visit
    distillation, whose target entropy alone is ~1.35 — must raise it (the CE floor
    exceeds 1.0 for a perfectly-healthy fit); those runs rely on the distribution-
    agnostic collapse guards instead (#1 NaN, #2 entropy-floor, #3b relative rise)."""
    reasons = []
    catastrophe = False
    ambiguous = False

    ent = metrics.get("policy_entropy")
    base = metrics.get("baseline_policy_entropy")
    floor = 0.5 * base if base else None  # train_iter --entropy-floor-frac default 0.5
    epochs = metrics.get("epochs", [])

    # 1. NaN check across all reported losses
    loss_keys = ("train_pol_loss", "train_val_loss", "val_pol_loss", "val_val_loss")
    if any(_isnan(e.get(k)) for e in epochs for k in loss_keys):
        catastrophe = True
        reasons.append("NaN loss detected")

    # 2. entropy collapse vs floor (0.5 * baseline)
    if ent is not None and floor is not None and ent < floor:
        catastrophe = True
        reasons.append(f"policy_entropy {ent:.4f} < floor {floor:.4f} (0.5*baseline) — COLLAPSE")
    elif ent is not None and base is not None and ent < 0.65 * base:
        ambiguous = True
        reasons.append(f"policy_entropy {ent:.4f} low ({ent/base:.2f}*baseline) — watch")

    # 3. val policy loss blow-up (healthy sits ~0.27; >1.0 = broken fit)
    if epochs:
        vlast = epochs[-1].get("val_pol_loss")
        if not _isnan(vlast) and float(vlast) > val_pol_collapse_thresh:
            catastrophe = True
            reasons.append(f"val_pol_loss {vlast} > {val_pol_collapse_thresh} — broken policy fit")
        # diverging across epochs (last > 1.5x first) is a soft flag
        vfirst = epochs[0].get("val_pol_loss")
        if not _isnan(vfirst) and not _isnan(vlast) and float(vlast) > 1.5 * float(vfirst) + 0.05:
            ambiguous = True
            reasons.append(f"val_pol_loss rising {vfirst}->{vlast} across epochs — watch")

    # 4. smoke catastrophe: new plays catastrophically worse than parent
    if smoke is not None:
        if smoke["wr"] < smoke_catastrophe_wr:
            catastrophe = True
            reasons.append(
                f"smoke wr(new vs parent) {smoke['wr']:.3f} < {smoke_catastrophe_wr} "
                f"(n={smoke['n']}) — catastrophic play regression"
            )

    if catastrophe:
        return "COLLAPSE", reasons
    if ambiguous:
        return "AMBIGUOUS", reasons
    return "HEALTHY", reasons or ["all cheap screens nominal"]


def update_manifest(path, entry, leaf_label=None, branch=None, doc_str=None):
    if os.path.exists(path):
        doc = json.load(open(path))
    else:
        doc = {
            "_meta": {
                "doc": doc_str or "RoD v2.8 overnight flywheel — checkpoint manifest (appended per iter)",
                "branch": branch or "rod_v28_overnight_flywheel",
                "status": "MEASUREMENT ONLY — exploratory; no promotion, PRODUCTION.yaml unchanged, v2.7 frozen, v2.8 opt-in",
                "leaf": leaf_label or "v2.8 = v2.7 + meeple_k=2.0 (CARCASSONNE_V25_MEEPLE_K=2.0, legacy field, flat fast path)",
                "lineage": "latest-chain: warm-from previous iter (unless catastrophic)",
            },
            "checkpoints": [],
        }
    ck = doc["checkpoints"]
    ck[:] = [c for c in ck if c.get("iter") != entry["iter"]]  # idempotent on iter
    ck.append(entry)
    ck.sort(key=lambda c: c.get("iter", 0))
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, path)


def append_csv(path, row, header):
    new = not os.path.exists(path)
    # idempotent: drop any existing row for this iter, then rewrite
    rows = []
    if not new:
        with open(path) as f:
            rd = csv.reader(f)
            existing_header = next(rd, None)
            for r in rd:
                if r and r[0] != str(row[0]):
                    rows.append(r)
    rows.append([str(x) for x in row])
    rows.sort(key=lambda r: int(r[0]) if r and r[0].lstrip("-").isdigit() else 0)
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)


def append_log(path, iter_idx, block):
    # idempotent-ish: if a block for this iter already exists, leave it (append-only log);
    # the driver only calls once per successful iter. We just append.
    marker = f"## iter_{iter_idx:02d}"
    existing = open(path).read() if os.path.exists(path) else ""
    if marker in existing:
        return
    with open(path, "a") as f:
        if not existing:
            f.write(
                "# RoD v2.8 Overnight Flywheel — Training Log Summary\n\n"
                "> Appended per iteration by `scripts/rod_v28/overnight_iter_screen.py`. "
                "MEASUREMENT ONLY. Cheap screens are catastrophe detectors, **not strength verdicts** "
                "(real evals run tomorrow on selected checkpoints).\n\n"
            )
        f.write(block)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--metrics", required=True)
    ap.add_argument("--parent-ckpt", required=True)
    ap.add_argument("--parent-id", required=True)
    ap.add_argument("--measure-dir", required=True)
    ap.add_argument("--sp-seed", required=True)
    ap.add_argument("--games", type=int, required=True)
    ap.add_argument("--gen-npz", type=int, default=0)
    ap.add_argument("--gen-sec", type=float, default=0.0)
    ap.add_argument("--train-sec", type=float, default=0.0)
    ap.add_argument("--smoke-dir", default="")
    ap.add_argument("--smoke-seed", default="")
    ap.add_argument("--smoke-catastrophe-wr", type=float, default=0.25)
    ap.add_argument("--val-pol-collapse-thresh", type=float, default=1.0,
                    help="absolute val_pol_loss COLLAPSE threshold (check #3a). Default 1.0 "
                         "(sharp self-play targets). Raise for SOFT targets (fair-champion "
                         "pooled-visit distillation: target entropy ~1.35 > 1.0).")
    ap.add_argument("--crashes", default="none")
    # Record labels — defaults preserve the v2.8 overnight behavior; RoD v2 overrides
    # these to the frozen v2.9 substrate so the manifest/csv are honest (the
    # authoritative leaf is prov_selfplay_leaf from the checkpoint metrics regardless).
    ap.add_argument("--leaf-label", default="v2.8 (v2.7 + meeple_k=2.0; CARCASSONNE_V25_MEEPLE_K=2.0, flat fast path)")
    ap.add_argument("--id-prefix", default="RoD")
    ap.add_argument("--manifest-branch", default="rod_v28_overnight_flywheel")
    ap.add_argument("--manifest-doc", default="RoD v2.8 overnight flywheel — checkpoint manifest (appended per iter)")
    args = ap.parse_args()

    metrics = json.load(open(args.metrics))
    prov = metrics.get("provenance", {})
    epochs = metrics.get("epochs", [])
    ck_sha = sha256(args.ckpt)
    smoke = parse_smoke(args.smoke_dir) if args.smoke_dir else None
    verdict, reasons = screen(metrics, smoke, args.smoke_catastrophe_wr,
                              args.val_pol_collapse_thresh)

    total_steps = sum(int(e.get("n_batches", 0)) for e in epochs)
    train_sec_metrics = sum(float(e.get("wallclock_sec", 0.0)) for e in epochs)
    val_pol = [e.get("val_pol_loss") for e in epochs]
    train_pol = [e.get("train_pol_loss") for e in epochs]
    train_val = [e.get("train_val_loss") for e in epochs]
    ent = metrics.get("policy_entropy")
    base_ent = metrics.get("baseline_policy_entropy")
    vcorr = metrics.get("value_outcome_corr")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "iter": args.iter,
        "id": f"{args.id_prefix}_iter_{args.iter:02d}",
        "path_local": args.ckpt,
        "path_remote": args.ckpt.replace("/mnt/c/carc-shared", "/mnt/carc-shared"),
        "sha256": ck_sha,
        "size_bytes": os.path.getsize(args.ckpt),
        "parent": args.parent_id,
        "parent_sha256": prov.get("parent_ckpt", {}).get("sha256"),
        "warm_from": args.parent_ckpt,
        "code_commit_at_train": prov.get("code_commit"),
        "arch": prov.get("arch"),
        "crashes_resumes": args.crashes,
        "leaf": args.leaf_label,
        "selfplay_gen": {
            "games_target": args.games,
            "npz_produced": args.gen_npz,
            "sims": 200,
            "c_puct": 3.0,
            "residual_scale": 0.25,
            "value_target": "residual",
            "leaf_eval_flag": "v2_5 (meeple_k from env)",
            "seed_start": args.sp_seed,
            "boxes": "5800x orch + laptop orch (carc-orch SHM, shared-claim work-stealing)",
            "gen_wallclock_sec": round(args.gen_sec, 1),
        },
        "training": {
            "script": "scripts/train_iter.py",
            "batch_size": 256,
            "epochs": 3,
            "value_loss_weight": prov.get("loss_weights", {}).get("value"),
            "lr": prov.get("loss_weights", {}).get("lr"),
            "weight_decay": prov.get("loss_weights", {}).get("weight_decay"),
            "window": 10,
            "warmstart_mix_fraction": metrics.get("warmstart_mix_fraction"),
            "n_train_positions": metrics.get("n_train_positions"),
            "n_val_positions": metrics.get("n_val_positions"),
            "total_optimizer_steps": total_steps,
            "train_wallclock_sec_metrics": round(train_sec_metrics, 1),
            "train_wallclock_sec_measured": round(args.train_sec, 1),
            "train_pol_loss": train_pol,
            "val_pol_loss": val_pol,
            "train_val_loss": train_val,
            "policy_entropy": ent,
            "baseline_policy_entropy": base_ent,
            "entropy_floor_0p5": round(0.5 * base_ent, 4) if base_ent else None,
            "value_outcome_corr": vcorr,
            "dataset_fingerprint": prov.get("dataset", {}).get("fingerprint"),
            "prov_selfplay_leaf": prov.get("selfplay_leaf"),
            "prov_value_target": prov.get("value_target"),
            "prov_run_tag": prov.get("run_tag"),
        },
        "cheap_screen": {
            "verdict": verdict,
            "reasons": reasons,
            "smoke": (
                {
                    "label": f"RoD_iter_{args.iter:02d} (A) vs {args.parent_id} (B), v2.8 leaf, paired, sims200",
                    "seed_start": args.smoke_seed,
                    "n_games": smoke["n"],
                    "a_w_l_d": [smoke["a_w"], smoke["a_l"], smoke["a_d"]],
                    "a_winrate": round(smoke["wr"], 4),
                    "a_elo_vs_parent": round(smoke["elo"], 1),
                    "a_elo_sigma": round(smoke["sigma"], 1),
                    "DISCLAIMER": "SMOKE ONLY (catastrophe detector) — n far too small for a strength verdict",
                }
                if smoke
                else None
            ),
        },
        "stamped_utc": now,
    }

    update_manifest(os.path.join(args.measure_dir, "CHECKPOINT_MANIFEST.json"), entry,
                    leaf_label=args.leaf_label, branch=args.manifest_branch, doc_str=args.manifest_doc)

    # --- CSV row ---
    sm_wr = f"{smoke['wr']:.3f}" if smoke else ""
    sm_elo = f"{smoke['elo']:+.1f}" if smoke else ""
    sm_n = smoke["n"] if smoke else ""
    csv_header = [
        "iter", "ckpt_id", "parent_id", "sha256_12", "games", "npz", "gen_sec", "train_sec",
        "opt_steps", "n_train_pos", "train_pol_last", "val_pol_last", "policy_entropy",
        "baseline_entropy", "entropy_floor", "value_corr", "smoke_n", "smoke_wr_vs_parent",
        "smoke_elo_vs_parent", "verdict", "code_commit",
    ]
    csv_row = [
        args.iter, f"{args.id_prefix}_iter_{args.iter:02d}", args.parent_id, ck_sha[:12], args.games,
        args.gen_npz, round(args.gen_sec, 1), round(args.train_sec, 1), total_steps,
        metrics.get("n_train_positions"),
        train_pol[-1] if train_pol else "", val_pol[-1] if val_pol else "",
        ent, base_ent, round(0.5 * base_ent, 4) if base_ent else "", vcorr,
        sm_n, sm_wr, sm_elo, verdict, (prov.get("code_commit") or "")[:12],
    ]
    append_csv(os.path.join(args.measure_dir, "CHEAP_SCREEN_RESULTS.csv"), csv_row, csv_header)

    # --- markdown log block ---
    smoke_md = (
        f"- **Smoke (n={smoke['n']}, catastrophe detector ONLY):** RoD_iter_{args.iter:02d} vs "
        f"{args.parent_id} = {smoke['a_w']}W/{smoke['a_l']}L/{smoke['a_d']}D, "
        f"wr {smoke['wr']:.3f}, elo {smoke['elo']:+.1f}±{smoke['sigma']:.0f} (NOT a verdict)\n"
        if smoke
        else "- **Smoke:** not run / no games\n"
    )
    block = (
        f"## iter_{args.iter:02d}  (warm-from {args.parent_id})  —  **{verdict}**\n\n"
        f"- ckpt `{ck_sha[:12]}…` ({entry['size_bytes']} B) · code `{(prov.get('code_commit') or '')[:12]}`\n"
        f"- gen: {args.gen_npz}/{args.games} npz, {args.gen_sec/60:.1f} min · "
        f"train: {total_steps} steps, {args.train_sec/60:.1f} min (metrics {train_sec_metrics/60:.1f})\n"
        f"- train_pol {train_pol} · val_pol {val_pol} · train_val {train_val}\n"
        f"- policy_entropy {ent} (baseline {base_ent}, floor {0.5*base_ent:.4f}) · value_corr {vcorr}\n"
        f"{smoke_md}"
        f"- screens: {'; '.join(reasons)}\n\n"
    )
    append_log(os.path.join(args.measure_dir, "TRAINING_LOG_SUMMARY.md"), args.iter, block)

    print(f"VERDICT={verdict}")
    for r in reasons:
        print(f"  - {r}")
    sys.exit(3 if verdict == "COLLAPSE" else 0)


if __name__ == "__main__":
    main()
