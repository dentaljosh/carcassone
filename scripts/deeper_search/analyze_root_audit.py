#!/usr/bin/env python3
"""Part D/E analysis — agreement matrices + stability + disagreement mining.

Consumes the root-audit output (all_positions.json) and answers:
  - pairwise top-1 AGREEMENT (h3200~h6400, h6400~h12800, rod1~h6400, rod1~h3200), overall + by phase
  - search SHARPNESS by depth: mean visit entropy + top-share at each sims level (does deeper
    search concentrate, or stay diffuse = noise?)
  - STABILITY of the h3200->h6400->h12800 choice chain per position:
        agree3      all three pick the same action  (search saturated here)
        converged   h6400 != h3200 AND h12800 == h6400  (deeper search found a STABLE new decision)
        unstable    h12800 != h6400 != h3200  (choices keep flipping = search noise)
        partial     other patterns
  - learned-agent placement: rod1 ~ h3200-but-not-h6400 (stuck at shallow ceiling) vs
        rod1 ~ h6400-but-not-h3200 (already deep)
  - DISAGREEMENT LIST for Part E: positions where the deep agent confidently differs from the
        shallow one (deep top_share >= --conf), prioritised late_mid/pre_endgame, deep-confirmed.

  python scripts/deeper_search/analyze_root_audit.py \
      measurement/deeper_search_ruler/root_audit/all_positions.json \
      --out measurement/deeper_search_ruler/root_audit
"""
from __future__ import annotations
import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path

PHASE_ORDER = ["opening", "midgame", "late_mid", "pre_endgame", "endgame"]


def agree(a, b, rec):
    ag = rec["agents"]
    if a not in ag or b not in ag:
        return None
    return ag[a]["chosen"] == ag[b]["chosen"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("allpos")
    ap.add_argument("--conf", type=float, default=0.5, help="deep top_share threshold for 'confident'")
    ap.add_argument("--out", default="measurement/deeper_search_ruler/root_audit")
    args = ap.parse_args(argv)
    recs = [r for r in json.load(open(args.allpos)) if "error" not in r]
    out = Path(args.out)
    present = set()
    for r in recs:
        present.update(r["agents"].keys())
    heur = sorted([a for a in present if a.startswith("h")], key=lambda x: int(x[1:]))

    L = [f"# Part D — root-action deeper-search audit ({len(recs)} positions)", ""]

    # --- search sharpness by depth ---
    L += ["## Search sharpness by depth (mean over all positions)",
          "agent | mean_entropy(nats) | mean_top_share | mean_chosen_share | mean_n_children"]
    L += ["--- | --- | --- | --- | ---"]
    for a in heur + (["rod1"] if "rod1" in present else []):
        rs = [r["agents"][a] for r in recs if a in r["agents"]]
        if not rs:
            continue
        me = sum(x["entropy"] for x in rs) / len(rs)
        mt = sum(x["top_share"] for x in rs) / len(rs)
        mc = sum(x["chosen_share"] for x in rs) / len(rs)
        mn = sum(x["n_children"] for x in rs) / len(rs)
        L.append(f"{a} | {me:.3f} | {mt:.3f} | {mc:.3f} | {mn:.1f}")
    L.append("")

    # --- pairwise agreement overall + by phase ---
    pairs = []
    for i in range(len(heur) - 1):
        pairs.append((heur[i], heur[i + 1]))
    if len(heur) >= 2:
        pairs.append((heur[0], heur[-1]))
    if "rod1" in present:
        for h in heur:
            pairs.append(("rod1", h))
    L += ["## Pairwise top-1 agreement (overall | by phase)",
          "pair | overall | " + " | ".join(PHASE_ORDER), "--- | --- | " + " | ".join("---" for _ in PHASE_ORDER)]
    for a, b in pairs:
        vals = [agree(a, b, r) for r in recs]
        vals = [v for v in vals if v is not None]
        ov = sum(vals) / len(vals) if vals else float("nan")
        cells = []
        for ph in PHASE_ORDER:
            pv = [agree(a, b, r) for r in recs if r["phase"] == ph]
            pv = [v for v in pv if v is not None]
            cells.append(f"{sum(pv)/len(pv):.2f}" if pv else "-")
        L.append(f"{a}~{b} | {ov:.3f} | " + " | ".join(cells))
    L.append("")

    # --- stability of the h3200->h6400->h12800 chain ---
    chain = [a for a in ("h3200", "h6400", "h12800") if a in present]
    if len(chain) == 3:
        cnt = Counter(); by_phase = defaultdict(Counter)
        for r in recs:
            ag = r["agents"]
            if not all(c in ag for c in chain):
                continue
            c0, c1, c2 = (ag[c]["chosen"] for c in chain)
            if c0 == c1 == c2:
                k = "agree3"
            elif c1 != c0 and c2 == c1:
                k = "converged"
            elif c2 != c1 and c1 != c0 and c2 != c0:
                k = "unstable"
            else:
                k = "partial"
            cnt[k] += 1; by_phase[r["phase"]][k] += 1
        tot = sum(cnt.values()) or 1
        L += ["## Stability of h3200->h6400->h12800 choice chain",
              f"- agree3 (search saturated):  {cnt['agree3']}/{tot} ({100*cnt['agree3']/tot:.0f}%)",
              f"- converged (deep STABLE new decision: h6400!=h3200, h12800==h6400):  {cnt['converged']}/{tot} ({100*cnt['converged']/tot:.0f}%)",
              f"- unstable (all three differ = noise):  {cnt['unstable']}/{tot} ({100*cnt['unstable']/tot:.0f}%)",
              f"- partial (other):  {cnt['partial']}/{tot} ({100*cnt['partial']/tot:.0f}%)", "",
              "by phase: " + "  ".join(f"{ph}[{by_phase[ph]['converged']}c/{by_phase[ph]['unstable']}u/{sum(by_phase[ph].values())}]" for ph in PHASE_ORDER), ""]

    # --- learned agent placement ---
    if "rod1" in present and "h3200" in present and "h6400" in present:
        a_h3_not_h6 = a_h6_not_h3 = both = neither = 0
        for r in recs:
            ag = r["agents"]
            if not all(x in ag for x in ("rod1", "h3200", "h6400")):
                continue
            r3 = ag["rod1"]["chosen"] == ag["h3200"]["chosen"]
            r6 = ag["rod1"]["chosen"] == ag["h6400"]["chosen"]
            if r3 and not r6: a_h3_not_h6 += 1
            elif r6 and not r3: a_h6_not_h3 += 1
            elif r3 and r6: both += 1
            else: neither += 1
        L += ["## Learned (RoD1) placement vs the ladder",
              f"- RoD1 == h3200 but != h6400 (stuck at shallow ceiling): {a_h3_not_h6}",
              f"- RoD1 == h6400 but != h3200 (already deep): {a_h6_not_h3}",
              f"- RoD1 == both (h3200==h6400 anyway): {both}",
              f"- RoD1 == neither: {neither}", ""]

    # --- disagreement list for Part E ---
    # NOTE: heur-MCTS visit distributions stay near-UNIFORM even at h12800 (this MCTS refines Q,
    # not visit concentration; the v2.8 leaf rates many placements similarly), so top_share is a
    # WEAK confidence proxy. The robust confidence signal is CONVERGENCE: h6400 AND h12800 (two
    # independent searches: different sims, different seeds) both pick the SAME non-h3200 action.
    deep = "h12800" if "h12800" in present else ("h6400" if "h6400" in present else None)
    shallow = "h3200" if "h3200" in present else None
    have_both_deep = ("h6400" in present and "h12800" in present and "h3200" in present)
    dis = []
    if deep and shallow:
        for r in recs:
            ag = r["agents"]
            if deep not in ag or shallow not in ag:
                continue
            if ag[deep]["chosen"] == ag[shallow]["chosen"]:
                continue
            # convergence = both deep searches agree on the SAME non-shallow move (= stable signal)
            converged = bool(have_both_deep and ag["h6400"]["chosen"] == ag["h12800"]["chosen"]
                             and ag["h12800"]["chosen"] != ag["h3200"]["chosen"])
            dis.append({
                "gen_id": r["gen_id"], "seed": r["seed"], "ply": r["ply"], "k": r["k_remaining"],
                "phase": r["phase"], "legal_n": r["legal_n"], "score_margin_abs": r["score_margin_abs"],
                "meeples_free": r.get("meeples_free"),
                "h3200_chosen": ag["h3200"]["chosen"] if "h3200" in ag else None,
                "h6400_chosen": ag["h6400"]["chosen"] if "h6400" in ag else None,
                "h12800_chosen": ag["h12800"]["chosen"] if "h12800" in ag else None,
                "converged_deep": converged,
                f"{deep}_top_share": ag[deep]["top_share"], f"{shallow}_top_share": ag[shallow]["top_share"],
                "rod1_chosen": ag.get("rod1", {}).get("chosen"),
                "rod1_matches_deep": (ag.get("rod1", {}).get("chosen") == ag[deep]["chosen"]) if "rod1" in ag else None,
            })
        pri = {ph: i for i, ph in enumerate(["pre_endgame", "late_mid", "endgame", "midgame", "opening"])}
        # convergent (stable) disagreements first, then phase priority, then by k
        dis.sort(key=lambda d: (0 if d["converged_deep"] else 1, pri.get(d["phase"], 9), d["k"]))
        with open(out / "disagreements.csv", "w", newline="") as f:
            if dis:
                w = csv.DictWriter(f, fieldnames=list(dis[0].keys())); w.writeheader()
                for d in dis:
                    w.writerow(d)
        n_conv = sum(1 for d in dis if d["converged_deep"])
        L += [f"## Deep disagreements ({deep} != {shallow})",
              f"- total: {len(dis)}/{len(recs)}  ({100*len(dis)/max(len(recs),1):.0f}% of positions)",
              f"- **CONVERGED (h6400==h12800 != h3200 = stable deeper-search preference): {n_conv}/{len(dis)}**",
              f"  by phase: " + ", ".join(f"{ph}:{sum(1 for d in dis if d['phase']==ph and d['converged_deep'])}" for ph in PHASE_ORDER),
              f"- RoD1 sides WITH the deep move on these: {sum(1 for d in dis if d.get('rod1_matches_deep'))}/{len(dis)}",
              f"- written: {out}/disagreements.csv", ""]

    (out / "ROOT_AUDIT_DIGEST.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n[written] {out}/ROOT_AUDIT_DIGEST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
