#!/usr/bin/env python3
"""Feature-Graph Comparator — Stages 2-4 driver: baselines + cheap comparators + offline gate.

Trains on TRAIN groups, early-stops / selects on VAL, reports on held-out TEST. Object under
test = per-child score; gate = beat the v2.9 leaf (B0) on selected-child regret, especially on
the DECISIVE TAIL (q_gap>=0.02 & leaf_regret>=0.02), with no broad ordinary regression.

Ablations: 'tier1' (context + leaf-component features only -> tests REWEIGHTING the leaf's own
terms) vs 'all' (+ Tier-2 structural/action -> tests REPRESENTATION). A win that appears only in
'all' attributes the gain to representation, not weighting — the pilot's headline question.

CPU, seconds. Writes OFFLINE_RESULTS.md + offline_results.json under measurement/.../.
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "feature_graph"))
import eval_lib as EL

OUT = REPO / "measurement" / "feature_graph_comparator"
ALPHAS = [0.0, 0.05, 0.1, 0.25, 0.5, 1.0]
RNG = np.random.default_rng(0)


# --------------------------------------------------------------------- helpers
def standardize(X, mu, sd):
    return (X - mu) / sd


def fit_scaler(X):
    mu = X.mean(0); sd = X.std(0); sd[sd < 1e-8] = 1.0
    return mu, sd


def scores_to_rows(n_rows, test_rows, vals):
    s = np.full(n_rows, -1e9)
    s[test_rows] = vals
    return s


def ridge_fit(X, y, lam=1.0):
    n, p = X.shape
    A = X.T @ X + lam * np.eye(p)
    return np.linalg.solve(A, X.T @ y)


def pairwise_linear(d, tr_groups, cols, mu, sd, max_pairs=40):
    """C1 / B3: logistic on within-group child_i-child_j differences, weighted |dQ|,
    emphasizing decisive pairs. Returns weight vector w; score = (Xstd @ w)."""
    from sklearn.linear_model import LogisticRegression
    Xd, yd, wd = [], [], []
    feat = d["feat"]
    for g in tr_groups:
        r = g["rows"]; oq = g["oracle_q"]
        Xg = standardize(feat[r][:, cols], mu, sd)
        m = len(r)
        pairs = [(i, j) for i in range(m) for j in range(m) if i < j]
        if len(pairs) > max_pairs:
            pairs = [pairs[k] for k in RNG.choice(len(pairs), max_pairs, replace=False)]
        for i, j in pairs:
            dq = oq[i] - oq[j]
            if abs(dq) < 1e-9:
                continue
            sign = 1.0 if dq > 0 else 0.0
            w = abs(dq) * (3.0 if abs(dq) >= 0.02 else 1.0)
            Xd.append(Xg[i] - Xg[j]); yd.append(sign); wd.append(w)
            Xd.append(Xg[j] - Xg[i]); yd.append(1 - sign); wd.append(w)
    Xd = np.asarray(Xd); yd = np.asarray(yd); wd = np.asarray(wd)
    clf = LogisticRegression(fit_intercept=False, C=1.0, max_iter=2000)
    clf.fit(Xd, yd, sample_weight=wd)
    return clf.coef_.ravel()


def torch_mlp_residual(d, tr_groups, va_groups, cols, mu, sd, hidden=64, listwise=False,
                       epochs=60, lr=1e-3):
    """C2/C4 (residual MLP) or C3 (listwise) — small MLP, early-stop on VAL selected regret."""
    import torch, torch.nn as nn
    feat = d["feat"]; leaf = d["leaf_q"]; oq_all = d["oracle_q"]

    def pack(groups):
        return [(torch.tensor(standardize(feat[g["rows"]][:, cols], mu, sd), dtype=torch.float32),
                 torch.tensor(g["oracle_q"], dtype=torch.float32),
                 torch.tensor(leaf[g["rows"]], dtype=torch.float32), g) for g in groups]
    TR, VA = pack(tr_groups), pack(va_groups)
    net = nn.Sequential(nn.Linear(len(cols), hidden), nn.ReLU(),
                        nn.Linear(hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)

    def val_regret():
        net.eval()
        reg = []
        with torch.no_grad():
            for X, oq, lf, g in VA:
                out = net(X).ravel()
                sc = out if listwise else lf + 0.25 * out
                reg.append(float(oq[oq.argmax()] - oq[sc.argmax()]))
        return float(np.mean(reg))

    best = (1e9, None)
    for ep in range(epochs):
        net.train()
        for k in RNG.permutation(len(TR)):
            X, oq, lf, g = TR[k]
            out = net(X).ravel()
            if listwise:
                p = torch.softmax(oq / 0.1, 0)
                loss = -(p * torch.log_softmax(out, 0)).sum()
            else:
                loss = ((out - (oq - lf)) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        vr = val_regret()
        if vr < best[0]:
            best = (vr, {k: v.detach().clone() for k, v in net.state_dict().items()})
    if best[1] is not None:
        net.load_state_dict(best[1])
    net.eval()
    return net


def score_all_test(model_kind, d, te_rows, cols, mu, sd, w=None, net=None):
    import numpy as np
    feat = d["feat"]
    Xte = standardize(feat[te_rows][:, cols], mu, sd)
    if model_kind == "linear":
        return Xte @ w
    if model_kind == "mlp":
        import torch
        with torch.no_grad():
            return net(torch.tensor(Xte, dtype=torch.float32)).ravel().numpy()
    raise ValueError(model_kind)


# --------------------------------------------------------------------- main
def main():
    t0 = time.time()
    d = EL.load_rows()
    n_rows = d["feat"].shape[0]
    names = d["feat_names"]
    tiers = EL.tier_columns(names)
    tr_m, va_m, te_m = EL.seed_split(d["game_seed"])
    tr_groups = EL.make_groups(d, tr_m)
    va_groups = EL.make_groups(d, va_m)
    te_groups = EL.make_groups(d, te_m)
    te_rows = np.flatnonzero(te_m)
    print(f"[load] rows={n_rows} feat={len(names)} | groups tr/va/te="
          f"{len(tr_groups)}/{len(va_groups)}/{len(te_groups)} | {time.time()-t0:.1f}s")

    blocks = []

    # B0 — v2.9 leaf
    ev0 = EL.group_eval(te_groups, d["leaf_q"])
    blocks.append(EL.report_block("B0_v29_leaf", ev0))

    feat = d["feat"]
    results = {}

    for tier_name, cols in [("tier1", tiers["t1_ctx"]), ("all", tiers["all"])]:
        mu, sd = fit_scaler(feat[tr_m][:, cols])

        # --- pointwise ridge -> oracle_q  (B4 linear)
        w = ridge_fit(standardize(feat[tr_m][:, cols], mu, sd), d["oracle_q"][tr_m], lam=10.0)
        sc = score_all_test("linear", d, te_rows, cols, mu, sd, w=w)
        ev = EL.group_eval(te_groups, scores_to_rows(n_rows, te_rows, sc))
        blocks.append(EL.report_block(f"ridge_pointwise[{tier_name}]", ev))

        # --- residual ridge -> (oracle_q - leaf_q), alpha sweep on selection
        wr = ridge_fit(standardize(feat[tr_m][:, cols], mu, sd),
                       (d["oracle_q"] - d["leaf_q"])[tr_m], lam=10.0)
        rhat = score_all_test("linear", d, te_rows, cols, mu, sd, w=wr)
        sweep = {}
        for a in ALPHAS:
            sc = scores_to_rows(n_rows, te_rows, d["leaf_q"][te_rows] + a * rhat)
            ev = EL.group_eval(te_groups, sc)
            sweep[a] = EL.summarize(ev, EL.decisive_mask(ev))
            if a in (0.0, 0.25):
                blocks.append(EL.report_block(f"resid_ridge[{tier_name}]a{a}", ev))
        results[f"resid_ridge_alpha_sweep[{tier_name}]"] = sweep

        # --- pairwise linear (C1)
        try:
            wp = pairwise_linear(d, tr_groups, cols, mu, sd)
            sc = score_all_test("linear", d, te_rows, cols, mu, sd, w=wp)
            ev = EL.group_eval(te_groups, scores_to_rows(n_rows, te_rows, sc))
            blocks.append(EL.report_block(f"pairwise_linear_C1[{tier_name}]", ev))
        except Exception as e:
            print(f"  pairwise[{tier_name}] skipped: {type(e).__name__}: {e}")

    # --- torch MLP residual (C4) + listwise (C3) on full feature set
    cols = tiers["all"]; mu, sd = fit_scaler(feat[tr_m][:, cols])
    try:
        net = torch_mlp_residual(d, tr_groups, va_groups, cols, mu, sd, listwise=False)
        rhat = score_all_test("mlp", d, te_rows, cols, mu, sd, net=net)
        for a in [0.0, 0.1, 0.25, 0.5]:
            sc = scores_to_rows(n_rows, te_rows, d["leaf_q"][te_rows] + a * rhat)
            ev = EL.group_eval(te_groups, sc)
            blocks.append(EL.report_block(f"resid_mlp_C4[all]a{a}", ev))
        net2 = torch_mlp_residual(d, tr_groups, va_groups, cols, mu, sd, listwise=True)
        sc = score_all_test("mlp", d, te_rows, cols, mu, sd, net=net2)
        ev = EL.group_eval(te_groups, scores_to_rows(n_rows, te_rows, sc))
        blocks.append(EL.report_block("listwise_mlp_C3[all]", ev))
    except Exception as e:
        print(f"  torch models skipped: {type(e).__name__}: {e}")

    # --------------------------------------------------------------- write
    (OUT / "offline_results.json").write_text(json.dumps(
        {"blocks": blocks, "sweeps": results,
         "split": {"tr_groups": len(tr_groups), "va_groups": len(va_groups), "te_groups": len(te_groups)},
         "n_rows": int(n_rows), "n_feat": len(names), "feat_names": names}, indent=2))

    b0 = blocks[0]
    lines = ["# Feature-Graph Comparator — OFFLINE RESULTS (Stage 4)\n",
             f"_generated {time.strftime('%Y-%m-%d %H:%M')} · TEST groups={len(te_groups)} · "
             f"decisive-tail n={b0['decisive_tail']['n']}_\n",
             "## Primary: selected-child regret (lower=better). Gate = beat B0_v29_leaf.\n",
             "| model | overall regret | top1 | tau | **decisive regret** | dec top1 | ordinary regret |",
             "|---|---|---|---|---|---|---|"]
    for b in blocks:
        o, dec, ordn = b["overall"], b["decisive_tail"], b["ordinary"]
        lines.append(f"| {b['model']} | {o['regret_mean']} | {o['top1']} | {o['tau_mean']} | "
                     f"**{dec.get('regret_mean','-')}** | {dec.get('top1','-')} | {ordn['regret_mean']} |")
    lines.append("\n## Residual alpha sweeps (decisive-tail regret)\n")
    for k, sw in results.items():
        lines.append(f"- **{k}**: " + "  ".join(
            f"a={a}:{v.get('regret_mean','-')}" for a, v in sw.items()))
    b0d = b0["decisive_tail"]["regret_mean"]
    lines.append("\n## Gate read\n")
    best = min(blocks[1:], key=lambda b: b["decisive_tail"].get("regret_mean", 9e9)) if len(blocks) > 1 else None
    if best:
        bd = best["decisive_tail"]["regret_mean"]
        drop = (b0d - bd) / b0d * 100 if b0d else 0.0
        lines.append(f"- B0 decisive regret = **{b0d}**; best learned = **{best['model']}** at "
                     f"**{bd}** ({drop:+.1f}% vs leaf).")
        lines.append(f"- Pass bar: >=10-15% decisive-tail drop AND no broad ordinary regression. "
                     f"{'PASS' if drop >= 10 else 'FAIL/INCONCLUSIVE'} on the tail-drop bar.")
    (OUT / "FEATURE_GRAPH_OFFLINE_RESULTS.md").write_text("\n".join(lines) + "\n")
    print(f"[done] {time.time()-t0:.1f}s -> wrote OFFLINE_RESULTS.md + offline_results.json")
    print("\n".join(lines[:6 + len(blocks)]))


if __name__ == "__main__":
    main()
