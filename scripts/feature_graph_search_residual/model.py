#!/usr/bin/env python3
"""FGSR Stage 4 — models. Two models, two heads each. CPU, small.

G0  graph-lite MLP   — input = action 50-scalars (+ per-root diag: top2_q_gap200,
                       entropy200, top_share200, log_legal_n, phase one-hot + Tier-B 21).
                       Strict superset of B5. Shared trunk; two heads.
G1  typed message-passing GNN over the 8-node-type / 8-edge-type board graph
                       (graphs.pkl). Type embeddings, 2-3 hetero conv layers, masked
                       mean+max readout. The G4 head conditions the graph readout on
                       each action's 50 scalars (action nodes are not in the graph).

HEADS (both models):
  G3 escalation : per-ROOT scalar logit = P(h200 materially wrong) -> BCE on pos_strong.
  G4 reranker   : per-LEGAL-ACTION-node score (within a root, argmax -> selected move).

The graph node-type schema (attr order) is frozen here (NODE_SPECS) and standardized
with train-set mean/std passed in at fit time.
"""
from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn

# ----------------------------------------------------------------- graph schema
# (node_type -> ordered list of numeric attr keys). Booleans cast to float.
NODE_SPECS = {
    "tile": ["r_norm", "c_norm", "has_city", "has_road", "has_farm",
             "has_monastery", "shield", "inn"],
    "city_feature": ["completed", "open_edges", "tile_count", "closure_delta",
                     "current_value", "completed_value", "phase_norm_value",
                     "meeples_self", "meeples_opp", "contested_flag", "owner_status"],
    "road_feature": ["completed", "tile_count", "open_ends", "inn_flag",
                     "meeples_self", "meeples_opp", "contested_flag", "owner_status"],
    "farm_feature": ["adjacent_city_roots", "adjacent_finished_cities", "tile_count",
                     "potential_value", "phase_norm_potential", "volatility",
                     "meeples_self", "meeples_opp", "contested_flag", "owner_status"],
    "monastery_feature": ["completed", "surrounding_count", "score_if_now", "owner"],
    "player": ["score", "score_margin_signed", "meeples_free", "meeples_locked",
               "is_current_player", "is_root_player", "player_local"],
    "meeple": ["player_local", "feature_type", "returnable_soon"],
    "deck_bucket": ["k_remaining", "n_distinct_types", "n_city_tiles", "n_road_tiles",
                    "n_monastery_tiles", "n_shield_tiles"],
    "_open": [],   # sentinel; pooled-only, single feature = bias
}
NODE_TYPES = list(NODE_SPECS.keys())
NT_INDEX = {nt: i for i, nt in enumerate(NODE_TYPES)}

EDGE_TYPES = [
    "tile_belongs_to_feature", "city_touches_farm", "feature_touches_feature",
    "meeple_on_feature", "meeple_belongs_to_player", "player_owns_feature",
    "player_contests_feature", "feature_has_open_boundary",
]

_OWNER_MAP = {"none": 0.0, "p0": 1.0, "p1": 2.0, "contested": 3.0, None: 0.0}
_FT_MAP = {"city": 0.0, "road": 1.0, "farm": 2.0, "monastery": 3.0, None: 0.0}


def _attr_val(nt, k, v):
    if k in ("owner_status", "owner"):
        return _OWNER_MAP.get(v, 0.0)
    if k == "feature_type":
        return _FT_MAP.get(v, 0.0)
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def node_matrix(graph, nt):
    """Return (n_nt, d_nt) float32 attr matrix for node type nt (raw, unstandardized)."""
    spec = NODE_SPECS[nt]
    lst = graph["nodes"].get(nt, [])
    if nt == "_open":
        # sentinel: presence count only -> a single 1.0 feature per _open node
        n = _count_open(graph)
        return np.ones((n, 1), np.float32)
    if not lst:
        return np.zeros((0, max(1, len(spec))), np.float32)
    M = np.zeros((len(lst), len(spec)), np.float32)
    for i, nd in enumerate(lst):
        for j, k in enumerate(spec):
            M[i, j] = _attr_val(nt, k, nd.get(k))
    return M


def _count_open(graph):
    mx = -1
    for et in ("feature_has_open_boundary",):
        for (st, si, dt, di) in graph["edges"].get(et, []):
            if dt == "_open":
                mx = max(mx, di)
    return mx + 1 if mx >= 0 else 0


def node_dim(nt):
    return 1 if nt == "_open" else len(NODE_SPECS[nt])


# ----------------------------------------------------------------- standardizer
def fit_node_scalers(graphs, gids):
    """Per-node-type mean/std over a set of graphs (train split only)."""
    acc = {nt: [] for nt in NODE_TYPES}
    for gid in gids:
        g = graphs[gid]
        for nt in NODE_TYPES:
            M = node_matrix(g, nt)
            if len(M):
                acc[nt].append(M)
    scal = {}
    for nt in NODE_TYPES:
        if acc[nt]:
            A = np.concatenate(acc[nt], 0)
            mu = A.mean(0); sd = A.std(0); sd[sd < 1e-6] = 1.0
        else:
            d = node_dim(nt); mu = np.zeros(d, np.float32); sd = np.ones(d, np.float32)
        scal[nt] = (mu.astype(np.float32), sd.astype(np.float32))
    return scal


def tensorize_graph(graph, scal):
    """-> dict: x[nt] standardized tensor; mp = precomputed message-passing index plan.

    The message-passing plan is a flat list of (lin_key, src_type, dst_type, src_idx_tensor,
    dst_idx_tensor) — built ONCE here so HeteroConv.forward has no per-call Python grouping
    (the hot-path cost). Includes both forward and reverse directions per edge type."""
    x = {}
    for nt in NODE_TYPES:
        Mn = node_matrix(graph, nt)
        mu, sd = scal[nt]
        if len(Mn):
            Mn = (Mn - mu) / sd
        x[nt] = torch.tensor(Mn, dtype=torch.float32)
    plan = []
    for et in EDGE_TYPES:
        ed = graph["edges"].get(et, [])
        if not ed:
            continue
        for direction in ("fwd", "rev"):
            lin_key = et + "_" + direction
            by_pair = {}
            for (s_t, s_i, d_t, d_i) in ed:
                if direction == "rev":
                    s_t, s_i, d_t, d_i = d_t, d_i, s_t, s_i
                by_pair.setdefault((s_t, d_t), ([], []))
                by_pair[(s_t, d_t)][0].append(s_i)
                by_pair[(s_t, d_t)][1].append(d_i)
            for (s_t, d_t), (si, di) in by_pair.items():
                plan.append((lin_key, s_t, d_t,
                             torch.tensor(si, dtype=torch.long),
                             torch.tensor(di, dtype=torch.long)))
    return {"x": x, "mp": plan}


# ----------------------------------------------------------------- G0 graph-lite MLP
class G0(nn.Module):
    """MLP trunk over [action 50-scalars ‖ per-root diag ‖ Tier-B 21]. Two heads.
    G3 pools action rows within a root (mean+max) -> root logit.
    G4 scores each action row directly."""
    def __init__(self, d_in, hidden=128, p_drop=0.1):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(d_in, hidden), nn.ReLU(), nn.Dropout(p_drop),
            nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(p_drop),
        )
        self.g4 = nn.Linear(hidden, 1)            # per-action reranker score
        self.g3 = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(),
                                nn.Linear(hidden, 1))   # per-root escalation logit

    def embed(self, X):
        return self.trunk(X)

    def g4_score(self, X):
        return self.g4(self.trunk(X)).squeeze(-1)

    def g3_logit_from_groups(self, X, group_ptr):
        """group_ptr: list of (start,end) row slices per root. Returns (n_root,) logit."""
        h = self.trunk(X)
        outs = []
        for s, e in group_ptr:
            hs = h[s:e]
            outs.append(torch.cat([hs.mean(0), hs.max(0).values]))
        H = torch.stack(outs)
        return self.g3(H).squeeze(-1)


# ----------------------------------------------------------------- G1 hetero GNN
class HeteroConv(nn.Module):
    """One round of typed message passing over the fixed edge-type set (+ reverse).
    Messages are mean-aggregated per (edge_type, direction) with a per-edge-type linear;
    the node update is a RESIDUAL MLP with LayerNorm (h_new = LN(h + MLP([h ‖ agg]))).

    The residual update (vs the original GRUCell) preserves the node's own features through
    depth — the GRU reset gate was zeroing the tiny per-node signal, so a 3-layer stack barely
    fit (diagnosed 2026-06-29: GNN crept trainAUROC 0.60->0.67 over 8 ep even at wd=0). The
    residual MLP fits far faster."""
    def __init__(self, h):
        super().__init__()
        self.h = h
        self.msg = nn.ModuleDict()
        for et in EDGE_TYPES:
            self.msg[et + "_fwd"] = nn.Linear(h, h)
            self.msg[et + "_rev"] = nn.Linear(h, h)
        self.upd = nn.ModuleDict({
            nt: nn.Sequential(nn.Linear(2 * h, h), nn.ReLU(), nn.Linear(h, h))
            for nt in NODE_TYPES})
        self.norm = nn.ModuleDict({nt: nn.LayerNorm(h) for nt in NODE_TYPES})

    def forward(self, hdict, mp):
        agg = {nt: torch.zeros_like(hdict[nt]) for nt in NODE_TYPES}
        cnt = {nt: torch.zeros(hdict[nt].shape[0], 1) for nt in NODE_TYPES}
        for (lin_key, s_t, d_t, si_t, di_t) in mp:
            if hdict[s_t].shape[0] == 0 or hdict[d_t].shape[0] == 0:
                continue
            m = self.msg[lin_key](hdict[s_t][si_t])
            agg[d_t].index_add_(0, di_t, m)
            cnt[d_t].index_add_(0, di_t, torch.ones(di_t.shape[0], 1))
        new = {}
        for nt in NODE_TYPES:
            h0 = hdict[nt]
            if h0.shape[0] == 0:
                new[nt] = h0; continue
            a = agg[nt] / cnt[nt].clamp(min=1.0)
            new[nt] = self.norm[nt](h0 + self.upd[nt](torch.cat([h0, a], dim=1)))
        return new


class G1(nn.Module):
    """Typed GNN. Per-type input encoder + type embedding -> L hetero conv rounds ->
    masked mean+max readout per type -> graph embedding. Action 50-scalars encoded and
    concatenated with the graph embedding for the G4 head; G3 reads the graph embedding."""
    def __init__(self, h=64, layers=3, d_action=50, d_root_diag=0, p_drop=0.1):
        super().__init__()
        self.h = h
        self.enc = nn.ModuleDict({
            nt: nn.Linear(max(1, node_dim(nt)), h) for nt in NODE_TYPES
        })
        self.type_emb = nn.Embedding(len(NODE_TYPES), h)
        self.convs = nn.ModuleList([HeteroConv(h) for _ in range(layers)])
        self.drop = nn.Dropout(p_drop)
        d_graph = 2 * h * len(NODE_TYPES)         # mean+max per type
        self.graph_proj = nn.Sequential(nn.Linear(d_graph + d_root_diag, h), nn.ReLU())
        self.act_enc = nn.Sequential(nn.Linear(d_action, h), nn.ReLU())
        self.g4 = nn.Sequential(nn.Linear(2 * h, h), nn.ReLU(), nn.Linear(h, 1))
        self.g3 = nn.Sequential(nn.Linear(h, h), nn.ReLU(), nn.Linear(h, 1))

    def graph_embed(self, gt, root_diag=None):
        hdict = {}
        for nt in NODE_TYPES:
            x = gt["x"][nt]
            if x.shape[0] == 0:
                hdict[nt] = torch.zeros((0, self.h))
            else:
                hdict[nt] = torch.relu(self.enc[nt](x) + self.type_emb.weight[NT_INDEX[nt]])
        for conv in self.convs:
            hdict = conv(hdict, gt["mp"])
            hdict = {k: self.drop(v) if v.shape[0] else v for k, v in hdict.items()}
        pooled = []
        for nt in NODE_TYPES:
            v = hdict[nt]
            if v.shape[0] == 0:
                pooled.append(torch.zeros(2 * self.h))
            else:
                pooled.append(torch.cat([v.mean(0), v.max(0).values]))
        emb = torch.cat(pooled)
        if root_diag is not None:
            emb = torch.cat([emb, root_diag])
        return self.graph_proj(emb)              # (h,)

    def graph_embed_batch(self, bt, root_diag=None):
        """Batched graph embedding over a union of G graphs (see collate_graphs).
        bt: {"x":{nt:(N_nt,d)}, "mp":[...offset idx...], "batch":{nt:(N_nt,) graph-id},
             "G":int, "counts":{nt:(G,)}}. Returns (G,h)."""
        G = bt["G"]
        hdict = {}
        for nt in NODE_TYPES:
            x = bt["x"][nt]
            if x.shape[0] == 0:
                hdict[nt] = torch.zeros((0, self.h))
            else:
                hdict[nt] = torch.relu(self.enc[nt](x) + self.type_emb.weight[NT_INDEX[nt]])
        for conv in self.convs:
            hdict = conv(hdict, bt["mp"])
            hdict = {k: self.drop(v) if v.shape[0] else v for k, v in hdict.items()}
        pooled = []
        for nt in NODE_TYPES:
            v = hdict[nt]; b = bt["batch"][nt]
            mean = torch.zeros(G, self.h); mx = torch.full((G, self.h), -1e9)
            if v.shape[0] > 0:
                cnt = bt["counts"][nt].clamp(min=1).unsqueeze(1).float()
                mean.index_add_(0, b, v); mean = mean / cnt
                mx = mx.index_reduce(0, b, v, "amax", include_self=True)
            mx = torch.where(mx <= -1e8, torch.zeros_like(mx), mx)
            pooled.append(torch.cat([mean, mx], dim=1))    # (G, 2h)
        emb = torch.cat(pooled, dim=1)                     # (G, 2h*T)
        if root_diag is not None:
            emb = torch.cat([emb, root_diag], dim=1)       # (G, ... + d_diag)
        return self.graph_proj(emb)                        # (G,h)

    def g3_logit(self, gemb):
        return self.g3(gemb).squeeze(-1)

    def g4_scores(self, gemb, action_feats):
        """gemb (h,), action_feats (m,50) -> (m,) scores."""
        ae = self.act_enc(action_feats)          # (m,h)
        rep = gemb.unsqueeze(0).expand(ae.shape[0], -1)
        return self.g4(torch.cat([rep, ae], dim=1)).squeeze(-1)


def collate_graphs(gt_list):
    """Union G tensorized graphs into one batched structure for graph_embed_batch.
    Node indices in the mp plan are offset per graph; batch[nt] maps node->graph."""
    G = len(gt_list)
    xcat = {nt: [] for nt in NODE_TYPES}
    batch = {nt: [] for nt in NODE_TYPES}
    counts = {nt: torch.zeros(G, dtype=torch.long) for nt in NODE_TYPES}
    offset = {nt: 0 for nt in NODE_TYPES}
    mp = []
    for gi, gt in enumerate(gt_list):
        # record node blocks + batch ids
        local_off = {}
        for nt in NODE_TYPES:
            x = gt["x"][nt]; n = x.shape[0]
            local_off[nt] = offset[nt]
            if n:
                xcat[nt].append(x)
                batch[nt].append(torch.full((n,), gi, dtype=torch.long))
            counts[nt][gi] = n
        # offset mp index tensors
        for (lin_key, s_t, d_t, si_t, di_t) in gt["mp"]:
            mp.append((lin_key, s_t, d_t, si_t + local_off[s_t], di_t + local_off[d_t]))
        for nt in NODE_TYPES:
            offset[nt] += gt["x"][nt].shape[0]
    x = {nt: (torch.cat(xcat[nt]) if xcat[nt] else torch.zeros((0, max(1, node_dim(nt)))))
         for nt in NODE_TYPES}
    bidx = {nt: (torch.cat(batch[nt]) if batch[nt] else torch.zeros(0, dtype=torch.long))
            for nt in NODE_TYPES}
    return {"x": x, "mp": mp, "batch": bidx, "G": G, "counts": counts}
