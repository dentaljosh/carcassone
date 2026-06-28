#!/usr/bin/env python3
"""Value/Search Autopsy — aggregation.

modes:
  missset    : from an I0 baseline file (iter04 + R2 NMCTS@200 rows) compute the
               reproduction table (per ckpt top1/regret/endgame), define the iter04
               MISS set, stratify it, write misses.jsonl + a MISS_SET.md fragment.
  compare    : given several tagged intervention files (each = miss_harness output on
               the SAME miss seeds), tabulate top1(=h6400)/regret/endgame/fixed-frac
               vs the I0 baseline. (INTERVENTIONS.md fragment.)
  classify   : join interventions by seed, assign each miss a primary bucket, emit the
               bucket x phase table. (RESULTS.md fragment.)

Pure-python (no torch); reads jsonl, writes markdown to stdout.
"""
from __future__ import annotations
import argparse, json
from collections import defaultdict
import numpy as np

ENDGAME = {"pre_endgame", "endgame"}
SHARE_MISS = 0.10   # "low visit share on h6400 top" threshold
REGRET_MISS = 0.02  # decision-relevant regret threshold


def _rid(r):
    """A root is uniquely (seed, ply) — a seed = a whole game with many plies, so
    NEVER key/match on seed alone (conflates all roots of one game)."""
    return (r.get("seed"), r.get("ply"))


def _load(path):
    return [json.loads(l) for l in open(path)]


def _by_ckpt(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["ckpt"]].append(r)
    return d


def _stats(rows):
    """top1(=h6400), mean regret, n, endgame n/top1/regret."""
    n = len(rows)
    if not n:
        return dict(n=0, top1=0, regret=0, egn=0, egtop1=0, egregret=0)
    top1 = np.mean([r["nmcts_top_eq_teacher"] for r in rows])
    regret = np.mean([r["regret"] for r in rows])
    eg = [r for r in rows if r["phase"] in ENDGAME]
    egn = len(eg)
    egtop1 = np.mean([r["nmcts_top_eq_teacher"] for r in eg]) if eg else 0.0
    egregret = np.mean([r["regret"] for r in eg]) if eg else 0.0
    return dict(n=n, top1=top1, regret=regret, egn=egn, egtop1=egtop1, egregret=egregret)


def _is_miss(r):
    return ((not r["nmcts_top_eq_teacher"])
            or r["teacher_best_visit_share"] < SHARE_MISS
            or r["regret"] >= REGRET_MISS)


def cmd_missset(args):
    rows = _load(args.i0)
    bk = _by_ckpt(rows)
    out = []
    out.append(f"## Stage 1 — reproduction (native NMCTS@200 on high-gap pool, gap≥0.02)\n")
    out.append("| ckpt | n | NMCTS top1 (=h6400) | mean regret | eg n | eg top1 | eg regret |")
    out.append("|---|--:|--:|--:|--:|--:|--:|")
    for name, rs in bk.items():
        s = _stats(rs)
        out.append(f"| {name} | {s['n']} | {s['top1']:.3f} | {s['regret']:.4f} | "
                   f"{s['egn']} | {s['egtop1']:.3f} | {s['egregret']:.4f} |")
    out.append("")

    base = bk[args.baseline_ckpt]
    misses = [r for r in base if _is_miss(r)]
    out.append(f"**Miss set** (baseline={args.baseline_ckpt}; "
               f"miss = wrong-argmax OR visit-share<{SHARE_MISS} OR regret≥{REGRET_MISS}): "
               f"**{len(misses)} / {len(base)}** ({len(misses)/max(len(base),1)*100:.1f}%).\n")

    # stratify
    def strat(key_fn, title, order=None):
        d = defaultdict(list)
        for r in misses:
            d[key_fn(r)].append(r)
        keys = order or sorted(d)
        out.append(f"### misses by {title}")
        out.append("| " + title + " | misses | mean regret | not-explored | wrong-argmax |")
        out.append("|---|--:|--:|--:|--:|")
        for k in keys:
            g = d.get(k, [])
            if not g:
                continue
            ne = np.mean([r["teacher_best_N"] == 0 for r in g])
            wa = np.mean([not r["nmcts_top_eq_teacher"] for r in g])
            out.append(f"| {k} | {len(g)} | {np.mean([r['regret'] for r in g]):.4f} | "
                       f"{ne*100:.0f}% | {wa*100:.0f}% |")
        out.append("")

    strat(lambda r: r["phase"], "phase",
          order=["opening", "midgame", "late_mid", "pre_endgame", "endgame"])

    def score_bucket(r):
        m = r.get("score_margin_abs")
        if m is None:
            return "unk"
        return "close(≤4)" if abs(m) <= 4 else ("mid(5-12)" if abs(m) <= 12 else "blowout(>12)")
    strat(score_bucket, "score-state", order=["close(≤4)", "mid(5-12)", "blowout(>12)", "unk"])

    def legal_bucket(r):
        ln = r.get("legal_n") or 0
        return "≤8" if ln <= 8 else ("9-20" if ln <= 20 else ">20")
    strat(legal_bucket, "legal-n", order=["≤8", "9-20", ">20"])

    if args.out_misses:
        with open(args.out_misses, "w") as fh:
            for r in misses:
                fh.write(json.dumps(r) + "\n")
        out.append(f"_misses → {args.out_misses}_\n")
    print("\n".join(out))


def cmd_missprobe(args):
    """Write the action_q-carrying probe rows restricted to the miss seeds — the
    input Stage-2 interventions need (miss_harness re-runs NMCTS per probe row)."""
    ids = {_rid(json.loads(l)) for l in open(args.misses)}
    n = 0
    with open(args.out, "w") as fh:
        for p in args.probe.split(","):
            for line in open(p):
                d = json.loads(line)
                if _rid(d) in ids:
                    fh.write(line if line.endswith("\n") else line + "\n")
                    n += 1
    print(f"[missprobe] {n} probe rows for {len(ids)} miss roots -> {args.out}")


def cmd_compare(args):
    """args.files = 'tag=path,tag=path'; all restricted to baseline miss seeds."""
    base_ids = set()
    if args.miss_seeds:
        base_ids = {_rid(json.loads(l)) for l in open(args.miss_seeds)}
    files = {}
    for tok in args.files.split(","):
        t, p = tok.split("=", 1)
        files[t.strip()] = p.strip()
    out = ["## Stage 2 — intervention comparison (on the iter04 miss set)\n",
           "All rows restricted to the baseline miss seeds; top1 = searched move == h6400 best.\n",
           "| intervention | ckpt | n | top1 (=h6400) | mean regret | Δregret vs I0 | eg top1 | eg regret | fixed-frac |",
           "|---|---|--:|--:|--:|--:|--:|--:|--:|"]
    # baseline regret per ckpt for Δ
    base_reg = {}
    for tag, path in files.items():
        bk = _by_ckpt(_load(path))
        for ck, rs in bk.items():
            if base_ids:
                rs = [r for r in rs if _rid(r) in base_ids]
            s = _stats(rs)
            if tag == args.baseline_tag:
                base_reg[ck] = s["regret"]
    for tag, path in files.items():
        bk = _by_ckpt(_load(path))
        for ck, rs in sorted(bk.items()):
            if base_ids:
                rs = [r for r in rs if _rid(r) in base_ids]
            s = _stats(rs)
            dreg = ""
            if ck in base_reg and base_reg[ck]:
                dreg = f"{(s['regret']-base_reg[ck])/base_reg[ck]*100:+.0f}%"
            fixed = np.mean([r["nmcts_top_eq_teacher"] for r in rs]) if rs else 0.0
            out.append(f"| {tag} | {ck} | {s['n']} | {s['top1']:.3f} | {s['regret']:.4f} | "
                       f"{dreg} | {s['egtop1']:.3f} | {s['egregret']:.4f} | {fixed:.3f} |")
    print("\n".join(out))


def cmd_classify(args):
    """Assign each baseline miss a PRIMARY bucket (with precedence).

    Inputs (all keyed by seed, iter04 ckpt):
      --i0          baseline misses (defines the set; has teacher_best_N, search_q_*)
      --sims-hi     a higher-sims run (e.g. 800)   -> search-budget-sensitive
      --teacher     teacher-prior-injection run     -> prior-sensitive
      --rs0         residual-scale=0 run            -> value-scale-sensitive
      --rs-hi       residual-scale=0.5 run          -> value-scale-sensitive
      --forced      forced-move file (leaf0_picks_teacher) -> horizon
    Precedence: not-explored < undervalued, then 'fixed by' tags, then horizon, then residual-stuck.
    """
    i0 = {_rid(r): r for r in _load(args.i0)}

    def fixed_ids(path):
        if not path:
            return set()
        return {_rid(r) for r in _load(path) if r.get("nmcts_top_eq_teacher")}

    fx_budget = fixed_ids(args.sims_hi)
    fx_prior = fixed_ids(args.teacher)
    fx_rs0 = fixed_ids(args.rs0)
    fx_rshi = fixed_ids(args.rs_hi)
    leaf_ranks_teacher = set()
    if args.forced:
        leaf_ranks_teacher = {_rid(r) for r in _load(args.forced) if r.get("leaf0_picks_teacher")}

    buckets = defaultdict(lambda: defaultdict(int))
    totals = defaultdict(int)
    for rid, r in i0.items():
        ph = "endgame" if r["phase"] in ENDGAME else "non-endgame"
        # primary classification (precedence order)
        if r["teacher_best_N"] == 0:
            b = "1.not-explored"
        elif (r["search_q_teacher_best"] is not None and r["search_q_nmcts_top"] is not None
              and r["search_q_teacher_best"] < r["search_q_nmcts_top"]):
            # visited but search ranks it below the bad move
            b = "2.explored-undervalued"
        else:
            b = "2b.explored-other"  # visited, search-Q ~ tied/higher but argmax/visit miss
        # overlay 'what fixes it' (informational; recorded as the resolving lever)
        fix = []
        if rid in fx_prior:
            fix.append("prior")
        if rid in fx_budget:
            fix.append("budget")
        if rid in (fx_rs0 | fx_rshi):
            fix.append("value")
        if not fix and r["teacher_best_N"] > 0 and rid not in leaf_ranks_teacher:
            # leaf statically undervalues the teacher child AND nothing cheap fixed it
            b = "6.horizon/leaf-blind"
        buckets[b][ph] += 1
        totals[b] += 1
        buckets[b]["_fix:" + ("+".join(fix) if fix else "none")] += 1

    out = ["## Stage 3 — miss classification (primary bucket × phase)\n",
           "| bucket | endgame | non-endgame | total |",
           "|---|--:|--:|--:|"]
    for b in sorted(buckets):
        eg = buckets[b]["endgame"]; neg = buckets[b]["non-endgame"]
        out.append(f"| {b} | {eg} | {neg} | {totals[b]} |")
    out.append(f"| **all** | | | {sum(totals.values())} |")
    out.append("\n### resolving lever (which cheap intervention flips the miss to a hit)")
    lever = defaultdict(int)
    for b in buckets:
        for k, v in buckets[b].items():
            if k.startswith("_fix:"):
                lever[k[5:]] += v
    out.append("| lever | misses fixed |")
    out.append("|---|--:|")
    for k in sorted(lever, key=lambda x: -lever[x]):
        out.append(f"| {k} | {lever[k]} |")
    print("\n".join(out))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("missset"); p.add_argument("--i0", required=True)
    p.add_argument("--baseline-ckpt", default="iter04")
    p.add_argument("--out-misses", default=None); p.set_defaults(fn=cmd_missset)
    p = sub.add_parser("missprobe"); p.add_argument("--misses", required=True)
    p.add_argument("--probe", required=True); p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_missprobe)
    p = sub.add_parser("compare"); p.add_argument("--files", required=True)
    p.add_argument("--miss-seeds", default=None); p.add_argument("--baseline-tag", default="I0")
    p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("classify"); p.add_argument("--i0", required=True)
    p.add_argument("--sims-hi", default=None); p.add_argument("--teacher", default=None)
    p.add_argument("--rs0", default=None); p.add_argument("--rs-hi", default=None)
    p.add_argument("--forced", default=None); p.set_defaults(fn=cmd_classify)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
