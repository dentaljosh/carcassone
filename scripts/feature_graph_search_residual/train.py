#!/usr/bin/env python3
"""FGSR Stage 4/5 — train G0 (graph-lite MLP) and G1 (typed GNN), each with both heads.

Heads trained separately (shared arch, different objective + early-stop signal):
  G3 escalation : per-ROOT logit -> BCE(pos_strong), positives weighted by regret(h200).
                  Early-stop on VAL AUROC(pos_strong).
  G4 reranker   : per-LEGAL-ACTION score; listwise softmax-CE toward q6400 within a root,
                  example-weighted by the root's q_gap_6400 (decisive roots matter more).
                  Early-stop on VAL decisive-tail selected-move regret vs h6400.

Split: psr_lib.seed_split (270/64/66 game-seed split; leak-free). NET-FREE, CPU.
Writes per-model TEST scores to data/scores_{model}.npz (consumed by run_offline_gate.py)
and the checkpoints to data/ck_{model}_{head}.pt (gitignored). Plus a training-curve summary
to data/train_summary.json for FGSR_TRAINING.md.

Run: nice -n 19 python train.py            (trains both models, both heads)
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn

REPO = Path("/home/doctor/projects/carcassone")
sys.path.insert(0, str(REPO / "scripts" / "post_search_residual"))
sys.path.insert(0, str(REPO / "scripts" / "feature_graph_search_residual"))
import psr_lib as P                                          # noqa: E402
import run_adaptive_gate as AG                               # noqa: E402
import model as M                                            # noqa: E402

DATA = REPO / "measurement" / "feature_graph_search_residual" / "data"
SRC = REPO / "measurement" / "post_search_residual" / "data"
ROOTS = SRC / "roots_mcts.jsonl"
FEATB = SRC / "features_mcts.jsonl"
TAIL_GAP, TAIL_REG = 0.02, 0.02
torch.set_num_threads(8)


# ----------------------------------------------------------------- data assembly
def load_all():
    """Per root: action rows (feat50, q200, q6400, action_id), graph, root diag, labels."""
    z = np.load(DATA / "rows_feat.npz", allow_pickle=False)
    import pickle
    graphs = pickle.load(open(DATA / "graphs.pkl", "rb"))
    # psr_lib rows for per-root regret/labels/diag
    proots = {r["group_id"]: r for r in P.load_roots(str(ROOTS))
              if all(np.isfinite(r["regret"][L]) for L in P.LEVELS)}
    fb = {}
    for line in FEATB.read_text().splitlines():
        if line.strip():
            o = json.loads(line); fb[int(o["group_id"])] = o["features"]
    tb_keys = sorted({k for v in fb.values() for k in v})

    gid = z["group_id"]; order = np.argsort(gid, kind="stable")
    gid_s = gid[order]
    feat = z["feat"][order]; aid = z["action_id"][order]
    q200 = z["q200"][order]; q6400 = z["q6400"][order]; leafq = z["leaf_q"][order]
    seed = z["game_seed"][order]; phase = np.array([str(s) for s in z["phase"]])[order]

    roots = []
    start = 0
    for i in range(1, len(gid_s) + 1):
        if i == len(gid_s) or gid_s[i] != gid_s[start]:
            g = int(gid_s[start])
            sl = slice(start, i)
            pr = proots.get(g)
            if pr is None or g not in graphs:
                start = i; continue
            # root diag (Tier-A for G0)
            diag = [pr["top2_q_gap200"], pr["entropy200"], pr["top_share200"],
                    np.log1p(pr["legal_n"])] + [1.0 if pr["phase"] == p else 0.0 for p in P.PHASES]
            tb = [float(fb.get(g, {}).get(k, 0.0)) for k in tb_keys]
            roots.append({
                "gid": g, "seed": int(seed[start]), "phase": str(phase[start]),
                "feat": feat[sl].astype(np.float32),
                "aid": aid[sl].astype(np.int64),
                "q200": q200[sl].astype(np.float32),
                "q6400": q6400[sl].astype(np.float32),
                "leaf_q": leafq[sl].astype(np.float32),
                "diag": np.array(diag, np.float32),
                "tb": np.array(tb, np.float32),
                "pos_strong": float(pr["pos_strong"]),
                "pos_medium": float(pr["pos_medium"]),
                "regret200": float(pr["regret"][200]),
                "q_gap_6400": float(pr["q_gap_6400"]),
                "graph": graphs[g],
            })
            start = i
    return roots, tb_keys, graphs


def split(roots):
    seeds = sorted({r["seed"] for r in roots})

    def bucket(s):
        h = (abs(hash((int(s), 12345))) % 1000) / 1000.0
        return "tr" if h < 0.70 else ("va" if h < 0.85 else "te")
    tag = {s: bucket(s) for s in seeds}
    tr = [r for r in roots if tag[r["seed"]] == "tr"]
    va = [r for r in roots if tag[r["seed"]] == "va"]
    te = [r for r in roots if tag[r["seed"]] == "te"]
    return tr, va, te


# ----------------------------------------------------------------- feature scalers (G0)
def g0_feature(r, fmu, fsd):
    """Per-action input matrix for G0: [feat50_std ‖ diag(repeated) ‖ tb(repeated)]."""
    X = (r["feat"] - fmu) / fsd
    m = X.shape[0]
    extra = np.concatenate([r["diag"], r["tb"]])[None, :].repeat(m, 0)
    return np.concatenate([X, extra], 1).astype(np.float32)


def fit_g0_scaler(tr):
    A = np.concatenate([r["feat"] for r in tr], 0)
    mu = A.mean(0); sd = A.std(0); sd[sd < 1e-6] = 1.0
    return mu.astype(np.float32), sd.astype(np.float32)


# ----------------------------------------------------------------- metrics
def auroc(scores, labels):
    return AG.auroc(np.asarray(scores), np.asarray(labels))


def selected_regret(r, sel_idx):
    """regret of choosing action sel_idx vs h6400 best (in tanh-Q6400)."""
    return float(r["q6400"].max() - r["q6400"][sel_idx])


def h200_selected_idx(r):
    """argmax q200 (ties -> lowest action id), mirroring best_action."""
    q = r["q200"]; aid = r["aid"]
    order = np.lexsort((aid, -q))   # primary -q asc(=q desc), tie lowest aid
    return int(order[0])


def tail_mask(roots):
    return np.array([(r["q_gap_6400"] >= TAIL_GAP and r["regret200"] >= TAIL_REG)
                     for r in roots])


# ----------------------------------------------------------------- G0 training
def pos_weight(r):
    """Mild, capped regret weight on positives (the old 1+30*regret hit ~10 and made the
    loss dominated by a handful of extreme positives -> failed to fit)."""
    return (1.0 + min(10.0 * r["regret200"], 2.0)) if r["pos_strong"] else 1.0


def train_g0_g3(tr, va, fmu, fsd, d_in, epochs=120, lr=1e-3, seed=0, patience=25):
    torch.manual_seed(seed)
    net = M.G0(d_in)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss(reduction="none")
    Xtr = [torch.tensor(g0_feature(r, fmu, fsd)) for r in tr]
    ytr = torch.tensor([r["pos_strong"] for r in tr])
    wtr = torch.tensor([pos_weight(r) for r in tr])
    Xva = [torch.tensor(g0_feature(r, fmu, fsd)) for r in va]
    yva = np.array([r["pos_strong"] for r in va])
    # early-stop on the LESS-NOISY pos_medium AUROC (more val positives than 55 pos_strong)
    yva_med = np.array([r["pos_medium"] for r in va])
    best = (-1.0, None, -1); rng = np.random.default_rng(seed)
    n = len(tr); bs = 256
    idx_all = np.arange(n)
    for ep in range(epochs):
        net.train()
        rng.shuffle(idx_all)
        for b in range(0, n, bs):
            bi = idx_all[b:b + bs]
            ptr = []; rows = []; off = 0
            for k in bi:
                rows.append(Xtr[k]); ptr.append((off, off + Xtr[k].shape[0])); off += Xtr[k].shape[0]
            Xb = torch.cat(rows)
            logit = net.g3_logit_from_groups(Xb, ptr)
            loss = (bce(logit, ytr[bi]) * wtr[bi]).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        # val AUROC
        net.eval()
        with torch.no_grad():
            sv = []
            for k in range(0, len(va), 256):
                chunk = Xva[k:k + 256]
                ptr = []; rows = []; off = 0
                for x in chunk:
                    rows.append(x); ptr.append((off, off + x.shape[0])); off += x.shape[0]
                sv.append(net.g3_logit_from_groups(torch.cat(rows), ptr).numpy())
            sv = np.concatenate(sv)
        a = auroc(sv, yva_med)            # selection signal: pos_medium (less noisy)
        if a is not None and a > best[0]:
            best = (a, {k: v.detach().clone() for k, v in net.state_dict().items()}, ep)
        elif ep - best[2] > patience:
            break
    if best[1] is not None:
        net.load_state_dict(best[1])
    # report the pos_strong val AUROC at the selected checkpoint (the headline metric)
    net.eval()
    with torch.no_grad():
        sv = []
        for k in range(0, len(va), 256):
            chunk = Xva[k:k + 256]; ptr = []; rows = []; off = 0
            for x in chunk:
                rows.append(x); ptr.append((off, off + x.shape[0])); off += x.shape[0]
            sv.append(net.g3_logit_from_groups(torch.cat(rows), ptr).numpy())
        va_strong = auroc(np.concatenate(sv), yva)
    return net, va_strong, best[2]


def train_g0_g4(tr, va, fmu, fsd, d_in, epochs=120, lr=1e-3, seed=0):
    torch.manual_seed(seed)
    net = M.G0(d_in)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    Xtr = [torch.tensor(g0_feature(r, fmu, fsd)) for r in tr]
    qtr = [torch.tensor(r["q6400"]) for r in tr]
    wtr = [r["q_gap_6400"] for r in tr]
    Xva = [torch.tensor(g0_feature(r, fmu, fsd)) for r in va]
    va_tail = tail_mask(va)
    best = (1e9, None, -1); rng = np.random.default_rng(seed)
    order = np.arange(len(tr))
    for ep in range(epochs):
        net.train(); rng.shuffle(order)
        for k in order:
            if Xtr[k].shape[0] < 2:
                continue
            sc = net.g4_score(Xtr[k])
            tgt = torch.softmax(qtr[k] / 0.05, 0)
            logp = torch.log_softmax(sc, 0)
            loss = -(tgt * logp).sum() * (1.0 + min(20.0 * wtr[k], 4.0))
            opt.zero_grad(); loss.backward(); opt.step()
        # val: decisive-tail selected regret
        net.eval()
        with torch.no_grad():
            reg = []
            for i, r in enumerate(va):
                if not va_tail[i]:
                    continue
                sc = net.g4_score(Xva[i]).numpy()
                sel = int(np.argmax(sc))
                reg.append(selected_regret(r, sel))
            vr = float(np.mean(reg)) if reg else 1e9
        if vr < best[0]:
            best = (vr, {k: v.detach().clone() for k, v in net.state_dict().items()}, ep)
    if best[1] is not None:
        net.load_state_dict(best[1])
    return net, best[0], best[2]


# ----------------------------------------------------------------- G1 training
def build_g1_tensors(roots, scal):
    return [M.tensorize_graph(r["graph"], scal) for r in roots]


def root_diag_tensor(r):
    # Tier-A diag for the graph projection (top2gap, entropy, top_share, log_legal, phase 1hot)
    return torch.tensor(r["diag"], dtype=torch.float32)


def _g1_embed_all(net, gt_list, diag_list, bs=128):
    """Batched graph embeddings for a list of graphs (eval; no grad)."""
    out = []
    with torch.no_grad():
        for b in range(0, len(gt_list), bs):
            sub = gt_list[b:b + bs]
            bt = M.collate_graphs(sub)
            d = torch.stack(diag_list[b:b + bs])
            out.append(net.graph_embed_batch(bt, d))
    return torch.cat(out) if out else torch.zeros((0, net.h))


def train_g1_g3(tr, va, gt_tr, gt_va, d_diag, epochs=80, lr=1e-3, seed=0, bs=128, patience=25):
    torch.manual_seed(seed)
    net = M.G1(h=64, layers=3, d_root_diag=d_diag)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    bce = nn.BCEWithLogitsLoss(reduction="none")
    yva = np.array([r["pos_strong"] for r in va])
    yva_med = np.array([r["pos_medium"] for r in va])     # less-noisy early-stop signal
    best = (-1.0, None, -1); rng = np.random.default_rng(seed)
    order = np.arange(len(tr))
    ytr = torch.tensor([r["pos_strong"] for r in tr])
    wtr = torch.tensor([pos_weight(r) for r in tr])
    diag_tr = [root_diag_tensor(r) for r in tr]
    diag_va = [root_diag_tensor(r) for r in va]
    for ep in range(epochs):
        net.train(); rng.shuffle(order)
        for b in range(0, len(tr), bs):
            bi = order[b:b + bs]
            sub = [gt_tr[k] for k in bi]
            bt = M.collate_graphs(sub)
            d = torch.stack([diag_tr[k] for k in bi])
            logit = net.g3_logit(net.graph_embed_batch(bt, d))
            loss = (bce(logit, ytr[bi]) * wtr[bi]).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        net.eval()
        sv = net.g3_logit(_g1_embed_all(net, gt_va, diag_va)).detach().numpy()
        a = auroc(sv, yva_med)
        if ep % 5 == 0:
            print(f"  [G1.g3] ep{ep} val_med_auroc={(a if a else 0):.3f}", flush=True)
        if a is not None and a > best[0]:
            best = (a, {k: v.detach().clone() for k, v in net.state_dict().items()}, ep)
        elif ep - best[2] > patience:
            break
    if best[1] is not None:
        net.load_state_dict(best[1])
    net.eval()
    va_strong = auroc(net.g3_logit(_g1_embed_all(net, gt_va, diag_va)).detach().numpy(), yva)
    return net, va_strong, best[2]


def _seg_logsoftmax_ce(scores, q6400_t, ptr, w):
    """Per-root softmax-CE toward q6400. scores/q6400_t flat over all actions; ptr=(s,e) per
    root; w=(n_root,) weight. Returns scalar weighted mean loss. (vectorized per-root)."""
    total = 0.0
    for j, (s, e) in enumerate(ptr):
        sc = scores[s:e]; q = q6400_t[s:e]
        tgt = torch.softmax(q / 0.05, 0)
        total = total + (-(tgt * torch.log_softmax(sc, 0)).sum()) * (1.0 + min(20.0 * w[j], 4.0))
    return total / len(ptr)


def train_g1_g4(tr, va, gt_tr, gt_va, d_diag, epochs=40, lr=1e-3, seed=0, bs=128):
    torch.manual_seed(seed)
    net = M.G1(h=64, layers=3, d_root_diag=d_diag)
    opt = torch.optim.Adam(net.parameters(), lr=lr, weight_decay=1e-4)
    diag_tr = [root_diag_tensor(r) for r in tr]
    diag_va = [root_diag_tensor(r) for r in va]
    feat_tr = [torch.tensor(r["feat"]) for r in tr]
    feat_va = [torch.tensor(r["feat"]) for r in va]
    q_tr = [torch.tensor(r["q6400"]) for r in tr]
    w_tr = [r["q_gap_6400"] for r in tr]
    va_tail = tail_mask(va)
    best = (1e9, None, -1); rng = np.random.default_rng(seed)
    order = np.arange(len(tr))
    for ep in range(epochs):
        net.train(); rng.shuffle(order)
        for b in range(0, len(tr), bs):
            bi = [k for k in order[b:b + bs] if feat_tr[k].shape[0] >= 2]
            if not bi:
                continue
            sub = [gt_tr[k] for k in bi]
            bt = M.collate_graphs(sub)
            d = torch.stack([diag_tr[k] for k in bi])
            gemb = net.graph_embed_batch(bt, d)             # (G,h)
            feats = torch.cat([feat_tr[k] for k in bi])
            ae = net.act_enc(feats)
            # per-root repeat of gemb
            rep_idx = torch.cat([torch.full((feat_tr[k].shape[0],), j, dtype=torch.long)
                                 for j, k in enumerate(bi)])
            rep = gemb[rep_idx]
            sc = net.g4(torch.cat([rep, ae], dim=1)).squeeze(-1)
            qcat = torch.cat([q_tr[k] for k in bi])
            ptr = []; off = 0
            for k in bi:
                ptr.append((off, off + feat_tr[k].shape[0])); off += feat_tr[k].shape[0]
            wb = [w_tr[k] for k in bi]
            loss = _seg_logsoftmax_ce(sc, qcat, ptr, wb)
            opt.zero_grad(); loss.backward(); opt.step()
        # val decisive-tail regret (batched embed, per-root argmax)
        net.eval()
        gemb_va = _g1_embed_all(net, gt_va, diag_va)
        with torch.no_grad():
            reg = []
            for i, r in enumerate(va):
                if not va_tail[i]:
                    continue
                sc = net.g4_scores(gemb_va[i], feat_va[i]).numpy()
                reg.append(selected_regret(r, int(np.argmax(sc))))
            vr = float(np.mean(reg)) if reg else 1e9
        if ep % 5 == 0:
            print(f"  [G1.g4] ep{ep} val_tail_regret={vr:.5f}", flush=True)
        if vr < best[0]:
            best = (vr, {k: v.detach().clone() for k, v in net.state_dict().items()}, ep)
        elif ep - best[2] > 20:
            break
    if best[1] is not None:
        net.load_state_dict(best[1])
    return net, best[0], best[2]


# ----------------------------------------------------------------- emit TEST scores
def emit_scores(name, te, g3_scores, g4_scores_by_root):
    """Save per-root g3 score + per-action g4 score (aligned to action rows) for the gate."""
    gids = np.array([r["gid"] for r in te], np.int64)
    g3 = np.array(g3_scores, np.float32)
    # flatten per-action g4 scores in the same row order as te concatenation
    g4_flat = np.concatenate([np.asarray(s, np.float32) for s in g4_scores_by_root])
    aid_flat = np.concatenate([r["aid"] for r in te])
    gid_flat = np.concatenate([np.full(r["feat"].shape[0], r["gid"], np.int64) for r in te])
    np.savez(DATA / f"scores_{name}.npz", gid=gids, g3=g3,
             g4=g4_flat, g4_aid=aid_flat, g4_gid=gid_flat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="G0,G1")
    ap.add_argument("--g0-epochs", type=int, default=120)
    ap.add_argument("--g1-epochs", type=int, default=60)
    args = ap.parse_args()
    t0 = time.time()
    roots, tb_keys, graphs = load_all()
    tr, va, te = split(roots)
    print(f"[load] roots={len(roots)} tr={len(tr)} va={len(va)} te={len(te)} "
          f"| tr-seeds={len(set(r['seed'] for r in tr))} te-seeds={len(set(r['seed'] for r in te))} "
          f"| {time.time()-t0:.0f}s")
    print(f"[tail] tr={int(tail_mask(tr).sum())} va={int(tail_mask(va).sum())} "
          f"te={int(tail_mask(te).sum())}  pos_strong tr={sum(r['pos_strong'] for r in tr):.0f}")

    summary = {"n_tr": len(tr), "n_va": len(va), "n_te": len(te),
               "tail": {"tr": int(tail_mask(tr).sum()), "va": int(tail_mask(va).sum()),
                        "te": int(tail_mask(te).sum())},
               "models": {}}
    want = args.models.split(",")

    # G0
    if "G0" in want:
        fmu, fsd = fit_g0_scaler(tr)
        d_in = tr[0]["feat"].shape[1] + len(tr[0]["diag"]) + len(tr[0]["tb"])
        print(f"[G0] d_in={d_in}")
        net3, va_auc, ep3 = train_g0_g3(tr, va, fmu, fsd, d_in, epochs=args.g0_epochs)
        net4, va_reg, ep4 = train_g0_g4(tr, va, fmu, fsd, d_in, epochs=args.g0_epochs)
        # train-fit sanity (AUROC on train for g3)
        net3.eval()
        with torch.no_grad():
            Xtr = [torch.tensor(g0_feature(r, fmu, fsd)) for r in tr]
            str_ = []
            for k in range(0, len(tr), 256):
                chunk = Xtr[k:k + 256]; ptr = []; rows = []; off = 0
                for x in chunk:
                    rows.append(x); ptr.append((off, off + x.shape[0])); off += x.shape[0]
                str_.append(net3.g3_logit_from_groups(torch.cat(rows), ptr).numpy())
            tr_auc = auroc(np.concatenate(str_), [r["pos_strong"] for r in tr])
            g3_te = []
            Xte = [torch.tensor(g0_feature(r, fmu, fsd)) for r in te]
            for k in range(0, len(te), 256):
                chunk = Xte[k:k + 256]; ptr = []; rows = []; off = 0
                for x in chunk:
                    rows.append(x); ptr.append((off, off + x.shape[0])); off += x.shape[0]
                g3_te.append(net3.g3_logit_from_groups(torch.cat(rows), ptr).numpy())
            g3_te = np.concatenate(g3_te)
            net4.eval()
            g4_te = [net4.g4_score(torch.tensor(g0_feature(r, fmu, fsd))).numpy() for r in te]
        te_auc = auroc(g3_te, [r["pos_strong"] for r in te])
        emit_scores("G0", te, g3_te, g4_te)
        torch.save(net3.state_dict(), DATA / "ck_G0_g3.pt")
        torch.save(net4.state_dict(), DATA / "ck_G0_g4.pt")
        params = sum(p.numel() for p in net3.parameters())
        summary["models"]["G0"] = {"d_in": d_in, "params": int(params),
                                   "g3_val_auroc": va_auc, "g3_train_auroc": tr_auc,
                                   "g3_test_auroc": te_auc, "g3_best_epoch": int(ep3),
                                   "g4_val_tail_regret": va_reg, "g4_best_epoch": int(ep4)}
        print(f"[G0] g3 train_auc={tr_auc:.3f} val_auc={va_auc:.3f} test_auc={te_auc:.3f} "
              f"(ep{ep3}) | g4 val_tail_regret={va_reg:.5f} (ep{ep4}) | {time.time()-t0:.0f}s")

    # G1
    if "G1" in want:
        # speed + class balance: keep all signal-bearing roots + a sample of negatives
        # (186/6845 pos imbalance; AUROC is rank-based so subsampling negs is fair, and
        #  val/test stay FULL for honest evaluation). ~3x faster per epoch.
        _tm = tail_mask(tr)
        _keep = set(i for i, r in enumerate(tr) if r["pos_medium"] or r["pos_strong"] or _tm[i])
        _neg = [i for i in range(len(tr)) if i not in _keep]
        _negsamp = set(np.random.default_rng(0).choice(
            _neg, size=min(len(_neg), 2200), replace=False).tolist())
        tr = [tr[i] for i in sorted(_keep | _negsamp)]
        print(f"[G1] train subset: {len(tr)} roots "
              f"({sum(int(r['pos_strong']) for r in tr)} pos_strong) for speed+balance", flush=True)
        scal = M.fit_node_scalers(graphs, [r["gid"] for r in tr])
        print("[G1] tensorizing graphs...")
        gt_tr = build_g1_tensors(tr, scal)
        gt_va = build_g1_tensors(va, scal)
        gt_te = build_g1_tensors(te, scal)
        d_diag = len(tr[0]["diag"])
        print(f"[G1] d_diag={d_diag}  (tensorize done {time.time()-t0:.0f}s)")
        net3, va_auc, ep3 = train_g1_g3(tr, va, gt_tr, gt_va, d_diag, epochs=args.g1_epochs)
        net4, va_reg, ep4 = train_g1_g4(tr, va, gt_tr, gt_va, d_diag, epochs=args.g1_epochs)
        net3.eval(); net4.eval()
        diag_tr = [root_diag_tensor(r) for r in tr]
        diag_te = [root_diag_tensor(r) for r in te]
        with torch.no_grad():
            str_ = net3.g3_logit(_g1_embed_all(net3, gt_tr, diag_tr)).numpy()
            tr_auc = auroc(str_, [r["pos_strong"] for r in tr])
            g3_te = net3.g3_logit(_g1_embed_all(net3, gt_te, diag_te)).numpy()
            te_auc = auroc(g3_te, [r["pos_strong"] for r in te])
            gemb_te = _g1_embed_all(net4, gt_te, diag_te)
            g4_te = [net4.g4_scores(gemb_te[i], torch.tensor(r["feat"])).numpy()
                     for i, r in enumerate(te)]
            # GRAPH ABLATION: zero the graph embedding -> G4 collapses to act_enc-only.
            # If tail regret is unchanged, message passing isn't contributing.
            te_tail = tail_mask(te)
            def _g4_tail_regret(use_graph):
                regs = []
                for i, r in enumerate(te):
                    if not te_tail[i]:
                        continue
                    ge = gemb_te[i] if use_graph else torch.zeros_like(gemb_te[i])
                    sc = net4.g4_scores(ge, torch.tensor(r["feat"])).numpy()
                    regs.append(selected_regret(r, int(np.argmax(sc))))
                return float(np.mean(regs)) if regs else None
            abl_graph = _g4_tail_regret(True)
            abl_zero = _g4_tail_regret(False)
        emit_scores("G1", te, g3_te, g4_te)
        torch.save(net3.state_dict(), DATA / "ck_G1_g3.pt")
        torch.save(net4.state_dict(), DATA / "ck_G1_g4.pt")
        params = sum(p.numel() for p in net3.parameters())
        summary["models"]["G1"] = {"params": int(params), "layers": 3, "h": 64,
                                   "g3_val_auroc": va_auc, "g3_train_auroc": tr_auc,
                                   "g3_test_auroc": te_auc, "g3_best_epoch": int(ep3),
                                   "g4_val_tail_regret": va_reg, "g4_best_epoch": int(ep4),
                                   "g4_ablation_tail_regret_with_graph": abl_graph,
                                   "g4_ablation_tail_regret_zeroed_graph": abl_zero}
        print(f"[G1] graph-ablation G4 tail regret: with_graph={abl_graph:.5f} "
              f"zeroed={abl_zero:.5f} (Δ={abl_zero-abl_graph:+.5f})")
        print(f"[G1] g3 train_auc={tr_auc:.3f} val_auc={va_auc:.3f} test_auc={te_auc:.3f} "
              f"(ep{ep3}) | g4 val_tail_regret={va_reg:.5f} (ep{ep4}) | {time.time()-t0:.0f}s")

    summary["runtime_s"] = round(time.time() - t0, 1)
    (DATA / "train_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print(f"[done] {time.time()-t0:.0f}s -> {DATA/'train_summary.json'}")


if __name__ == "__main__":
    main()
