#!/usr/bin/env python3
"""Step-2 "PeNS" IN-LOOP ScalarMLP value RETRAIN (MEASUREMENT ONLY).

The per-iter value-head retrain for the weaned flywheel. Reads the self-play
.npz that gen_step2.py wrote this iter, pulls the per-ply 89-vec PeNS features +
the per-ply `score_diff_wide` value target, and trains the SAME `ScalarMLP`
(imported from train_warmstart.py) with **plain MSE on score_diff_wide** —
mirroring train_iter.py's `F.mse_loss(value_pred, value_b)`. It warm-starts from
the previous iter's scalar checkpoint (`--warm-from`, default warmstart.pt) and
saves the new checkpoint in the EXACT format warmstart.pt uses, so gen_step2.py's
`--scalar-ckpt` loads it unchanged for the next iter.

Normalization is held FIXED to the warm-from's `col_mean`/`col_std` (NOT
recomputed per-iter) — keeping the z-score frame identical across the whole run
so the wean is a clean lever (a drifting normalization would confound the blend
schedule). The arch (D / hidden / blocks) is also taken from the warm-from so the
state_dict always loads.

========================================================================
THE SEAM with gen_step2.py (the sibling agent owns gen_step2.py; field NAMES may
differ slightly — this is the ONE integration point to reconcile at the smoke):
  * FEATURE field  — the per-ply 89-vec PeNS scalars, shape (n, 89). We try, in
    order, the names in FEAT_FIELD_CANDIDATES (default ['step2_feats',
    'child_scalars', 'pens_feats', 'feat89']). Override with --feat-field.
  * VALUE  field   — score_diff_wide = tanh((p0-p1)/40), current-player POV,
    shape (n,). We try VALUE_FIELD_CANDIDATES (default ['values', 'value']).
    Override with --value-field.
If NEITHER a feature field NOR the value field is present in the .npz, we FAIL
LOUDLY naming exactly what we looked for and what the file actually contains, so
the reconcile is a one-line --feat-field / --value-field fix, not a silent wrong
train. We do NOT block on the exact name.
========================================================================

  python -u scripts/step2_pens/train_value_iter.py \
      --gen-dir /mnt/c/carc-shared/step2_pens/iter02_data/iter_00 \
      --warm-from /home/doctor/carc_step2_pens/warmstart/warmstart.pt \
      --out /mnt/c/carc-shared/step2_pens/scalar/iter_02.pt \
      --epochs 6
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

REPO = Path(__file__).resolve().parent.parent.parent

# value_ranking_train.listnet_loss / kendall_tau_b — the EXACT ranking recipe the
# warmstart used (the +43% gate). step1_train.group_metrics is the per-group regret.
sys.path.insert(0, str(REPO / "scripts"))
from value_ranking_train import listnet_loss, kendall_tau_b  # noqa: E402

# Index of the v2.9 LEAF value column in the 89-vec (FEAT_NAMES "T1_leaf_q_tanh").
# This is the warmstart's `leaf_q` (tanh(vs2/15), root-POV) — the regret-reduction
# baseline for the alpha-sweep (leaf_q + alpha*net vs leaf alone). Resolved by name
# at runtime against build_dataset.FEAT_NAMES (not hard-coded) so a feature-ordering
# change fails loudly instead of silently ranking the wrong column.
ALPHAS = [0.0, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0]

# Import ScalarMLP from THIS package's train_warmstart.py explicitly by path —
# scripts/train_warmstart.py (a different file, no ScalarMLP) is also importable
# and would shadow a plain `import train_warmstart` (same trick gen_step2.py uses).
_tw_spec = _ilu.spec_from_file_location(
    "step2_train_warmstart", str(REPO / "scripts" / "step2_pens" / "train_warmstart.py")
)
_tw = _ilu.module_from_spec(_tw_spec)
_tw_spec.loader.exec_module(_tw)
ScalarMLP = _tw.ScalarMLP  # the EXACT arch the warmstart trainer / gen_step2 use

# --- THE SEAM: documented field-name constants (easy to fix at integration) --- #
# gen_step2.py persists the per-ply 89-vec + value target; the sibling agent may
# name the feature field slightly differently. We probe these in order.
FEAT_FIELD_CANDIDATES = ["pens_features", "step2_feats", "child_scalars", "pens_feats", "feat89"]
VALUE_FIELD_CANDIDATES = ["value_target", "values", "value"]


def _pick_field(npz_files: list[Path], candidates: list[str], override: str | None):
    """Return the first field name present in the FIRST loadable .npz. If an
    override is given it MUST be present (else loud error)."""
    if not npz_files:
        return None, []
    with np.load(npz_files[0], allow_pickle=False) as z:
        present = list(z.files)
    if override:
        if override not in present:
            raise SystemExit(
                f"FATAL: --field override '{override}' not in {npz_files[0].name}; "
                f"fields present = {present}"
            )
        return override, present
    for c in candidates:
        if c in present:
            return c, present
    return None, present


def _load_gen(gen_dir: Path, feat_field: str | None, value_field: str | None):
    """Glob gen .npz, read the per-ply 89-vec + value target by name, concat.

    TOLERATES the seam: if the resolved feature/value field is missing, raises a
    SystemExit naming exactly what was expected and what the file contains."""
    # gen_step2.py writes a companion seed_*_pens.npz holding the per-ply 89-vec
    # (pens_features) + value_target; the main seed_*.npz is the ResNet GameDataset
    # (no 89-vec). PREFER the companion files.
    files = sorted(gen_dir.glob("*_pens.npz"))
    if not files:
        files = sorted(gen_dir.glob("seed_*.npz"))
    if not files:
        # also accept a flat dir of *.npz (some gen layouts)
        files = sorted(p for p in gen_dir.glob("*.npz") if not p.name.startswith("."))
    if not files:
        raise SystemExit(f"FATAL: no gen .npz under {gen_dir} (looked for seed_*.npz / *.npz)")

    ff, present = _pick_field(files, FEAT_FIELD_CANDIDATES, feat_field)
    vf, _ = _pick_field(files, VALUE_FIELD_CANDIDATES, value_field)
    if ff is None:
        raise SystemExit(
            "FATAL: could not find the per-ply 89-vec PeNS feature array in the gen .npz.\n"
            f"  looked for (in order): {FEAT_FIELD_CANDIDATES}\n"
            f"  fields actually present in {files[0].name}: {present}\n"
            "  --> reconcile the seam: pass --feat-field <name> (the sibling agent's "
            "gen_step2.py field for the (n,89) per-ply scalars)."
        )
    if vf is None:
        raise SystemExit(
            "FATAL: could not find the per-ply value target (score_diff_wide) in the gen .npz.\n"
            f"  looked for (in order): {VALUE_FIELD_CANDIDATES}\n"
            f"  fields actually present in {files[0].name}: {present}\n"
            "  --> reconcile the seam: pass --value-field <name>."
        )

    feats, vals = [], []
    n_rows = 0
    for f in files:
        with np.load(f, allow_pickle=False) as z:
            if ff not in z.files or vf not in z.files:
                # a straggler/older file missing the field — skip with a note, do
                # not corrupt the train silently.
                print(f"  [skip] {f.name}: missing {ff!r} or {vf!r} (has {list(z.files)})", flush=True)
                continue
            x = np.asarray(z[ff]).astype(np.float32)
            y = np.asarray(z[vf]).astype(np.float32).reshape(-1)
            if x.ndim != 2:
                raise SystemExit(f"FATAL: {f.name}[{ff}] has shape {x.shape}, expected (n, D)")
            if x.shape[0] != y.shape[0]:
                raise SystemExit(
                    f"FATAL: {f.name}: feature rows {x.shape[0]} != value rows {y.shape[0]} "
                    f"({ff!r} vs {vf!r} are not row-aligned)"
                )
            feats.append(x)
            vals.append(y)
            n_rows += x.shape[0]
    if not feats:
        raise SystemExit(f"FATAL: every gen .npz under {gen_dir} was missing {ff!r}/{vf!r}")
    X = np.concatenate(feats, axis=0)
    Y = np.concatenate(vals, axis=0)
    return X, Y, ff, vf, len(files)


def _load_rank_groups(gen_dir: Path):
    """Load the RANKING companions (seed_*_rank.npz) gen_step2 --emit-ranking-groups
    wrote: per-root sibling groups (each child's 89-vec parent=root, the backed-up
    search-Q ranking target, a shared group_id). Returns (X, Y, G, feat_names) with
    X=(N,89) f32 child feats, Y=(N,) f32 search-Q target, G=(N,) i32 group id."""
    files = sorted(gen_dir.glob("*_rank.npz"))
    if not files:
        raise SystemExit(
            f"FATAL: --objective ranking but no seed_*_rank.npz under {gen_dir}.\n"
            "  gen_step2.py must run with --emit-ranking-groups (the launcher sets "
            "this when VALUE_OBJECTIVE=ranking), and --gen-dir must point at the dir "
            "holding the rank companions."
        )
    feats, tgts, grps = [], [], []
    fnames = None
    for f in files:
        with np.load(f, allow_pickle=False) as z:
            for k in ("child_feats", "child_target", "group_id"):
                if k not in z.files:
                    raise SystemExit(f"FATAL: {f.name} missing {k!r} (has {list(z.files)})")
            cf = np.asarray(z["child_feats"]).astype(np.float32)
            ct = np.asarray(z["child_target"]).astype(np.float32).reshape(-1)
            gg = np.asarray(z["group_id"]).astype(np.int64).reshape(-1)
            if cf.shape[0] == 0:
                continue
            if not (cf.shape[0] == ct.shape[0] == gg.shape[0]):
                raise SystemExit(
                    f"FATAL: {f.name} row mismatch child_feats {cf.shape[0]} / "
                    f"child_target {ct.shape[0]} / group_id {gg.shape[0]}")
            if fnames is None and "feat_names" in z.files:
                fnames = [str(x) for x in z["feat_names"]]
            feats.append(cf); tgts.append(ct); grps.append(gg)
    if not feats:
        raise SystemExit(f"FATAL: every seed_*_rank.npz under {gen_dir} had 0 rows")
    X = np.concatenate(feats, 0)
    Y = np.concatenate(tgts, 0)
    G = np.concatenate(grps, 0)
    return X, Y, G, fnames, len(files)


def _group_metrics(score, oq):
    """Per-group regret + top1 + Kendall-tau (step1_train.group_metrics / the
    warmstart's metric). regret = oq[argmax(oq)] - oq[argmax(score)]: how much
    search-Q the head's pick leaves on the table vs the search-best child."""
    best = int(np.argmax(oq)); pick = int(np.argmax(score))
    return float(oq[best] - oq[pick]), int(pick == best), kendall_tau_b(score, oq)


def _regret_sweep(groups, preds, leaf, oq):
    """The warmstart's alpha-sweep on a set of held-out groups. `groups` is a list
    of index arrays into preds/leaf/oq. Reports net-alone regret/top1/tau + the
    leaf_q+alpha*net/sd sweep (regret reduction vs leaf alone = the +43% metric)."""
    if not groups:
        return None
    allp = np.concatenate([preds[g] for g in groups])
    sd = float(allp.std() + 1e-9)
    na = {"regret": [], "top1": [], "tau": []}
    for g in groups:
        r, t1, ta = _group_metrics(preds[g], oq[g])
        na["regret"].append(r); na["top1"].append(t1); na["tau"].append(ta)
    # RANDOM-pick baseline per group: the expected regret if the leaf picked a
    # uniformly-random sibling (oq[best] - mean(oq)). This is the discrimination
    # floor that is ROBUST even when the leaf already ≈ the in-loop teacher (at low
    # blend the search-Q is heuristic-dominated, so leaf-alone regret →0 and the
    # alpha-sweep saturates at α=0 — see the smoke caveat). net_vs_random tells us
    # the ranking head ORDERS siblings above chance regardless.
    rnd_regret = []
    for g in groups:
        rnd_regret.append(float(oq[g].max() - oq[g].mean()))
    random_regret = float(np.mean(rnd_regret))
    net_regret = float(np.mean(na["regret"]))
    out = {"net_alone": {"regret": net_regret,
                         "top1": float(np.mean(na["top1"])),
                         "tau": float(np.nanmean(na["tau"])), "n": len(groups)},
           "random_pick_regret": random_regret,
           "net_vs_random_reduction_pct": round(
               100 * (random_regret - net_regret) / (random_regret + 1e-12), 2),
           "alpha": {}}
    for a in ALPHAS:
        reg, t1 = [], []
        for g in groups:
            r, o1, _ = _group_metrics(leaf[g] + a * preds[g] / sd, oq[g])
            reg.append(r); t1.append(o1)
        out["alpha"][f"{a}"] = {"regret": float(np.mean(reg)), "top1": float(np.mean(t1))}
    base = out["alpha"]["0.0"]["regret"]
    ba = min(out["alpha"], key=lambda k: out["alpha"][k]["regret"])
    out["leaf_alone_regret"] = base
    out["best_alpha"] = ba
    out["best_alpha_regret"] = out["alpha"][ba]["regret"]
    out["regret_reduction_pct"] = round(100 * (base - out["alpha"][ba]["regret"]) / (base + 1e-12), 2)
    out["beats_leaf"] = bool(ba != "0.0" and out["alpha"][ba]["regret"] < base - 1e-9)
    return out


def _train_ranking(args, dev, wf, D, hidden, blocks, feat_names, col_mean, col_std, outp):
    """--objective ranking: train the ScalarMLP with per-group ListNet over the
    in-loop sibling groups (the warmstart recipe), normalization HELD FIXED to
    warm-from. Reports a HELD-OUT per-group regret-reduction (leaf_q+alpha*net vs
    leaf alone) — the +43% metric — to confirm the ranking objective PRESERVES the
    sibling discrimination MSE erodes. Saves the warmstart.pt format unchanged."""
    rng = np.random.default_rng(args.seed)
    X, Y, G, rfnames, n_files = _load_rank_groups(Path(args.gen_dir))
    if X.shape[1] != D:
        raise SystemExit(
            f"FATAL: rank feature width {X.shape[1]} != warm-from D={D}.")
    # locate the leaf_q column by name (the alpha-sweep baseline)
    names = rfnames if rfnames else feat_names
    if "T1_leaf_q_tanh" not in names:
        raise SystemExit(
            f"FATAL: 'T1_leaf_q_tanh' not in the rank-companion feat_names — the "
            f"leaf_q baseline column for the regret-sweep is gone. names[:12]={names[:12]}")
    leaf_col = names.index("T1_leaf_q_tanh")
    leaf_q_all = X[:, leaf_col].astype(np.float32)

    # group the rows (group_id is globally unique across files by construction)
    by_gid: dict[int, list[int]] = {}
    for i, g in enumerate(G):
        by_gid.setdefault(int(g), []).append(i)
    group_idx = [np.asarray(v, dtype=np.int64) for v in by_gid.values() if len(v) >= 2]
    if not group_idx:
        raise SystemExit("FATAL: no rank group with >=2 children — nothing to rank")
    # held-out split AT THE GROUP level (regret is per-group): val_fraction of groups
    gperm = rng.permutation(len(group_idx))
    n_val_g = max(1, int(round(args.val_fraction * len(group_idx)))) if len(group_idx) >= 2 else 0
    val_groups = [group_idx[i] for i in gperm[:n_val_g]]
    tr_groups = [group_idx[i] for i in gperm[n_val_g:]]
    if not tr_groups:  # tiny smoke: train on all, eval on all
        tr_groups = group_idx; val_groups = group_idx
    print(f"[rank] {n_files} rank files -> {X.shape[0]} child-rows / {len(group_idx)} groups "
          f"(>=2 children); split train {len(tr_groups)} / heldout {len(val_groups)} groups; "
          f"target range [{Y.min():+.3f},{Y.max():+.3f}]", flush=True)

    Xn = (X - col_mean) / col_std
    Xt = torch.from_numpy(Xn.astype(np.float32))
    Yt = torch.from_numpy(Y.astype(np.float32))

    net = ScalarMLP(D, hidden=hidden, blocks=blocks).to(dev)
    net.load_state_dict(wf["state_dict"])
    n_params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    rank_temp = float(wf.get("rank_temp", 0.25))
    print(f"[model] ScalarMLP D={D} params={n_params/1e3:.0f}k warm-started on {dev} "
          f"(LISTNET ranking, temp={rank_temp})", flush=True)

    gpb = args.groups_per_batch

    def run_epoch(groups, train):
        net.train(train)
        order = list(rng.permutation(len(groups)) if train else range(len(groups)))
        tot = 0.0; nb = 0
        for b0 in range(0, len(order), gpb):
            batch = [groups[order[k]] for k in order[b0:b0 + gpb]]
            flat = np.concatenate(batch)
            if train and len(flat) < 2:
                continue  # BatchNorm1d needs >=2
            xb = Xt[flat].to(dev); yb = Yt[flat].to(dev)
            with torch.set_grad_enabled(train):
                pred = net(xb)
                loss = 0.0; off = 0
                for gi in batch:
                    k = len(gi); p = pred[off:off + k]; t = yb[off:off + k]; off += k
                    loss = loss + listnet_loss(p, t, rank_temp)
                loss = loss / len(batch)
                if train:
                    opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
            tot += float(loss.detach()); nb += 1
        return tot / max(nb, 1)

    metrics = {"warm_from": str(args.warm_from), "gen_dir": str(args.gen_dir),
               "objective": "ranking", "rank_temp": rank_temp, "n_files": n_files,
               "n_groups": len(group_idx), "n_train_groups": len(tr_groups),
               "n_heldout_groups": len(val_groups), "D": D, "epochs": []}
    for ep in range(args.epochs):
        t0 = time.time()
        tl = run_epoch(tr_groups, True)
        vl = run_epoch(val_groups, False)
        metrics["epochs"].append({"epoch": ep + 1, "train_listnet": round(tl, 6),
                                  "val_listnet": round(vl, 6), "sec": round(time.time() - t0, 1)})
        print(f"  ep{ep+1}/{args.epochs} train_listnet={tl:.5f} val_listnet={vl:.5f} "
              f"({time.time()-t0:.0f}s)", flush=True)

    # ---- HELD-OUT per-group regret-reduction (the warmstart's +43% metric) ---- #
    net.train(False)
    with torch.no_grad():
        preds = net(Xt.to(dev)).cpu().numpy()
    sweep = _regret_sweep(val_groups, preds, leaf_q_all, Y)
    metrics["heldout_regret_sweep"] = sweep
    if sweep is not None:
        s = sweep
        print(f"\n[HELD-OUT regret] net-alone tau={s['net_alone']['tau']:+.3f} "
              f"top1={s['net_alone']['top1']:.3f} regret={s['net_alone']['regret']:.4f} | "
              f"random-pick regret={s['random_pick_regret']:.4f} | "
              f"combined a*={s['best_alpha']} "
              f"regret {s['leaf_alone_regret']:.4f}->{s['best_alpha_regret']:.4f} "
              f"({s['regret_reduction_pct']:+.1f}%) beats_leaf={s['beats_leaf']} "
              f"(n={s['net_alone']['n']} heldout groups)", flush=True)
        # PRIMARY (robust) signal: net orders siblings above chance — net-alone
        # regret vs a random pick. Stays informative at low blend where the leaf
        # already ≈ the in-loop teacher (so the leaf+alpha sweep saturates at α=0).
        print(f"[KEY] heldout net_vs_random_reduction_pct = "
              f"{s['net_vs_random_reduction_pct']:+.2f}%  (tau={s['net_alone']['tau']:+.3f}); "
              f"leaf+alpha regret_reduction_pct = {s['regret_reduction_pct']:+.2f}%  "
              f"(POSITIVE => ranking objective PRESERVES sibling discrimination)", flush=True)

    # ---- save in the EXACT warmstart.pt format (gen --scalar-ckpt loads it) ---- #
    torch.save({
        "state_dict": net.state_dict(),
        "D": int(D), "feat_names": feat_names,
        "col_mean": col_mean, "col_std": col_std,
        "hidden": hidden, "blocks": blocks,
        "arch": "ScalarMLP",
        "rank_temp": rank_temp,
        "v29_hash": wf.get("v29_hash"),
        "step2_value_retrain": {
            "warm_from": str(args.warm_from), "gen_dir": str(args.gen_dir),
            "objective": "ranking", "epochs": args.epochs,
            "n_groups": len(group_idx), "loss": "listnet_search_q",
            "heldout_regret_reduction_pct": (sweep["regret_reduction_pct"] if sweep else None),
        },
    }, outp)
    (outp.with_suffix(".value_metrics.json")).write_text(json.dumps(metrics, indent=2))
    print(f"\n[saved] {outp}  (+ {outp.with_suffix('.value_metrics.json').name}) "
          f"— ranking objective, warmstart format, normalization preserved", flush=True)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="train_value_iter")
    ap.add_argument("--gen-dir", required=True,
                    help="Dir of this iter's gen .npz (globs seed_*.npz / *.npz). The "
                         "89-vec PeNS features + score_diff_wide value target are read here.")
    ap.add_argument("--warm-from", required=True,
                    help="Previous iter's ScalarMLP ckpt (warmstart.pt format). The arch "
                         "AND the FIXED col_mean/col_std normalization are taken from here.")
    ap.add_argument("--out", required=True, help="Output ScalarMLP ckpt (.pt, warmstart format).")
    ap.add_argument("--objective", default="mse", choices=["mse", "ranking"],
                    help="In-loop value objective. 'mse' (default) = plain MSE on "
                         "the per-ply score_diff_wide target (the cratering run; "
                         "reads seed_*_pens.npz). 'ranking' = per-group ListNet over "
                         "the in-loop sibling groups' backed-up search-Q (reads "
                         "seed_*_rank.npz from --emit-ranking-groups gen) — the arm "
                         "B' test that the warmstart's +43% was sibling-RANKING, not "
                         "outcome-MSE.")
    ap.add_argument("--groups-per-batch", type=int, default=32,
                    help="--objective ranking only: sibling groups per listwise batch.")
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=1024)
    ap.add_argument("--val-fraction", type=float, default=0.05)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    # --- the seam overrides (default = auto-probe FEAT/VALUE_FIELD_CANDIDATES) --- #
    ap.add_argument("--feat-field", default=None,
                    help="Override the gen-npz per-ply 89-vec field name "
                         f"(auto-probe order: {FEAT_FIELD_CANDIDATES}).")
    ap.add_argument("--value-field", default=None,
                    help="Override the gen-npz value-target field name "
                         f"(auto-probe order: {VALUE_FIELD_CANDIDATES}).")
    args = ap.parse_args(argv)

    dev = torch.device(args.device)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    # ---- warm-from: arch + FIXED normalization (do NOT recompute per-iter) ---- #
    wf = torch.load(args.warm_from, map_location="cpu", weights_only=False)
    D = int(wf["D"])
    hidden = int(wf["hidden"])
    blocks = int(wf["blocks"])
    feat_names = [str(x) for x in wf["feat_names"]]
    col_mean = np.asarray(wf["col_mean"], np.float32)
    col_std = np.asarray(wf["col_std"], np.float32)
    col_std = np.where(col_std < 1e-6, 1.0, col_std).astype(np.float32)
    print(f"[warm-from] {args.warm_from}  D={D} hidden={hidden} blocks={blocks} "
          f"objective={args.objective} (normalization HELD FIXED from warm-from)", flush=True)

    # ---- RANKING objective (arm B') — separate path, MSE path below untouched ---- #
    if args.objective == "ranking":
        return _train_ranking(args, dev, wf, D, hidden, blocks,
                              feat_names, col_mean, col_std, outp)

    # ---- gen data (the seam) ---- #
    X, Y, ff, vf, n_files = _load_gen(Path(args.gen_dir), args.feat_field, args.value_field)
    if X.shape[1] != D:
        raise SystemExit(
            f"FATAL: gen feature width {X.shape[1]} (field {ff!r}) != warm-from D={D}. "
            "The 89-vec column count must match the warmstart MLP exactly."
        )
    print(f"[gen] {n_files} files -> {X.shape[0]} plies, D={X.shape[1]} "
          f"(feat_field={ff!r}, value_field={vf!r}); "
          f"value range [{Y.min():+.3f},{Y.max():+.3f}] mean {Y.mean():+.3f}", flush=True)

    # z-score with the FIXED normalization
    Xn = (X - col_mean) / col_std
    Xt = torch.from_numpy(Xn.astype(np.float32))
    Yt = torch.from_numpy(Y.astype(np.float32))

    # train/val split (row-level; MSE is per-row so no group structure needed)
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(X.shape[0])
    n_val = int(round(args.val_fraction * X.shape[0]))
    val_idx = perm[:n_val]
    tr_idx = perm[n_val:]
    do_val = n_val >= args.batch_size or (0 < n_val < args.batch_size and n_val >= 2)
    print(f"[split] train {len(tr_idx)} / val {len(val_idx)} rows "
          f"(val_fraction={args.val_fraction})", flush=True)

    # ---- model: warm-start from the previous scalar ckpt ---- #
    net = ScalarMLP(D, hidden=hidden, blocks=blocks).to(dev)
    net.load_state_dict(wf["state_dict"])
    n_params = sum(p.numel() for p in net.parameters())
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    print(f"[model] ScalarMLP D={D} params={n_params/1e3:.0f}k warm-started on {dev}", flush=True)

    def run(idx, train):
        net.train(train)
        order = rng.permutation(idx) if train else idx
        tot = 0.0
        nb = 0
        for b0 in range(0, len(order), args.batch_size):
            sel = order[b0:b0 + args.batch_size]
            if train and len(sel) < 2:
                continue  # BatchNorm1d needs >=2 in train mode
            xb = Xt[sel].to(dev)
            yb = Yt[sel].to(dev)
            with torch.set_grad_enabled(train):
                pred = net(xb)
                loss = F.mse_loss(pred, yb)  # mirrors train_iter.py value MSE
                if train:
                    opt.zero_grad(set_to_none=True)
                    loss.backward()
                    opt.step()
            tot += float(loss.detach())
            nb += 1
        return tot / max(nb, 1)

    metrics = {"warm_from": str(args.warm_from), "gen_dir": str(args.gen_dir),
               "feat_field": ff, "value_field": vf, "n_files": n_files,
               "n_train": int(len(tr_idx)), "n_val": int(len(val_idx)),
               "D": D, "hidden": hidden, "blocks": blocks, "epochs": []}
    for ep in range(args.epochs):
        t0 = time.time()
        tl = run(tr_idx, True)
        vl = run(val_idx, False) if do_val else float("nan")
        metrics["epochs"].append({"epoch": ep + 1, "train_mse": round(tl, 6),
                                  "val_mse": (round(vl, 6) if do_val else None),
                                  "sec": round(time.time() - t0, 1)})
        vstr = f" val_mse={vl:.5f}" if do_val else ""
        print(f"  ep{ep+1}/{args.epochs} train_mse={tl:.5f}{vstr} ({time.time()-t0:.0f}s)", flush=True)

    # ---- save in the EXACT warmstart.pt format (gen_step2 --scalar-ckpt loads it) ---- #
    torch.save({
        "state_dict": net.state_dict(),
        "D": int(D), "feat_names": feat_names,
        "col_mean": col_mean, "col_std": col_std,
        "hidden": hidden, "blocks": blocks,
        "arch": "ScalarMLP",
        "rank_temp": wf.get("rank_temp", 0.25),
        "v29_hash": wf.get("v29_hash"),
        # provenance for the in-loop retrain (not read by gen; just lineage)
        "step2_value_retrain": {
            "warm_from": str(args.warm_from), "gen_dir": str(args.gen_dir),
            "feat_field": ff, "value_field": vf, "epochs": args.epochs,
            "n_train": int(len(tr_idx)), "loss": "mse_score_diff_wide",
        },
    }, outp)
    (outp.with_suffix(".value_metrics.json")).write_text(json.dumps(metrics, indent=2))
    print(f"\n[saved] {outp}  (+ {outp.with_suffix('.value_metrics.json').name}) "
          f"— warmstart format, normalization preserved", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
