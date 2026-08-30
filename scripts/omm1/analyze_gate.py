#!/usr/bin/env python3
"""OM-M1 stage 1, step 3 — the frozen read rule.

⛔ INSTRUMENT ONLY. Spec: ``measurement/omm1_refuter_gate_20260830/PREREG.md``
§4.4 (statistics), §5 (the bar), §6 (the branches).

Reads ``LEGS/*.jsonl`` (raw ``B x arms`` margin matrices) and emits
``READOUT.json`` / ``READOUT.md``. Every number here is arithmetic over banked
matrices — re-running this script never runs a playout, so the read rule is
auditable and re-runnable.

⚠️ The branch this script prints is ADVISORY. A human adjudicates against
PREREG §6, on the POOLED row, `R_max` first. That is the house rule
(`meeple_tie_census.BRANCH_BARS`'s own comment) and it is not decorative: the
script cannot see a guard failure that happened outside its inputs.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import omm1_lib as L  # noqa: E402


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _argmax_arm(means, arms):
    """Strict-`>` argmax over the arm order — a tie keeps the EARLIEST arm,
    which is the incumbent leaf tie-break and exactly what
    ``arbitrate_core`` does. Any other rule would invent flips."""
    best = 0
    for i in range(1, len(means)):
        if means[i] > means[best]:
            best = i
    return arms[best]


def _leg_means(margins, lo, hi, n_arms):
    """Mean per arm over worlds ``[lo, hi)``, folded in ascending world then
    ascending arm — the same order the rust folds in (f64 addition is not
    associative)."""
    sums = [0.0] * n_arms
    for j in range(lo, hi):
        row = margins[j]
        for i in range(n_arms):
            sums[i] += row[i]
    d = float(hi - lo)
    return [s / d for s in sums]


def _two_leg_means(sym, other, split, b, n_arms):
    """PREREG §4.4: ``1/2 * mean_{j<split}(S) + 1/2 * mean_{j>=split}(other)``."""
    a = _leg_means(sym, 0, split, n_arms)
    c = _leg_means(other, split, b, n_arms)
    return [0.5 * a[i] + 0.5 * c[i] for i in range(n_arms)]


def analyze_row(rec: dict, split: int) -> dict:
    """All of PREREG §4.4 for one fired ply."""
    arms = rec["arms"]
    n = len(arms)
    b = rec["b"]
    legs = rec["legs"]
    sym = legs[L.LEG_SYM]["margins"]

    out = {
        "rid": rec["rid"],
        "corpus": rec["corpus"],
        "deck_seed": rec["deck_seed"],
        "ply": rec["ply"],
        "n_arms": n,
        "phase_bucket": rec.get("phase_bucket"),
        "k_remaining": rec.get("k_remaining"),
    }
    a_sym = _argmax_arm(_leg_means(sym, 0, b, n), arms)
    out["A_sym"] = a_sym
    # The DEPLOYED B=16 pick, free: the first 16 worlds of the same run.
    if b >= L.B_DEPLOYED:
        out["A_sym_b16"] = _argmax_arm(_leg_means(sym, 0, L.B_DEPLOYED, n), arms)

    for name in (L.LEG_PLACEBO, L.LEG_REF, L.LEG_MAX):
        if name not in legs:
            continue
        m = legs[name]["margins"]
        a_two = _argmax_arm(_two_leg_means(sym, m, split, b, n), arms)
        # The swap replication: halves exchanged, same matrices, zero cost.
        swap = [
            0.5 * x + 0.5 * y
            for x, y in zip(
                _leg_means(sym, split, b, n), _leg_means(m, 0, split, n)
            )
        ]
        a_swap = _argmax_arm(swap, arms)
        a_pure = _argmax_arm(_leg_means(m, 0, b, n), arms)
        out[name] = {
            "A_two": a_two,
            "flip": int(a_two != a_sym),
            "A_swap": a_swap,
            "flip_swap": int(a_swap != a_sym),
            "swap_same_arm": int(a_swap == a_two),
            "A_pure": a_pure,
            "flip_pure": int(a_pure != a_sym),
        }
    return out


def summarize(rows: list[dict], label: str) -> dict:
    n = len(rows)
    placebo = [r[L.LEG_PLACEBO]["flip"] for r in rows if L.LEG_PLACEBO in r]
    p_placebo = _mean(placebo) if placebo else float("nan")
    out = {"label": label, "n": n, "p_flip_placebo": p_placebo}
    for name in (L.LEG_REF, L.LEG_MAX):
        present = [r for r in rows if name in r and L.LEG_PLACEBO in r]
        if not present:
            continue
        f = [r[name]["flip"] for r in present]
        p = [r[L.LEG_PLACEBO]["flip"] for r in present]
        p_flip = _mean(f)
        # McNemar paired-discordance se (PREREG §4.4).
        bb = sum(1 for x, y in zip(f, p) if x and not y)
        cc = sum(1 for x, y in zip(f, p) if y and not x)
        se = math.sqrt(bb + cc) / len(present) if present else float("nan")
        delta = p_flip - _mean(p)
        flipped = [r for r in present if r[name]["flip"]]
        rho = (
            _mean([r[name]["swap_same_arm"] and r[name]["flip_swap"] for r in flipped])
            if flipped
            else float("nan")
        )
        out[name] = {
            "n": len(present),
            "p_flip_two_leg": p_flip,
            "delta_flip": delta,
            "se_delta": se,
            "delta_plus_2se": delta + 2 * se,
            "discordant_b": bb,
            "discordant_c": cc,
            "swap_replication_rho": rho,
            "n_flipped": len(flipped),
            "p_flip_pure_B": _mean([r[name]["flip_pure"] for r in present]),
            # PREREG §5: `delta * F * R_x`, in which `F` cancels —
            # `F * R_x == G_arb / P_ARB_NE_RND`. Written in the cancelled form
            # so no fire-rate constant enters the number.
            "implied_pts_per_game": delta * L.G_ARB_PTS_PER_GAME / L.P_ARB_NE_RND,
        }
    return out


def branch(pooled: dict) -> tuple[str, str]:
    """PREREG §6, in order. ADVISORY — a human adjudicates."""
    m = pooled.get(L.LEG_MAX)
    if not m:
        return "OM-VOID", "no R_max leg in the pooled row"
    if m["delta_plus_2se"] < L.BAR_DELTA_FLIP:
        return (
            "OM-DEAD",
            f"delta_hat {m['delta_flip']:+.4f} + 2se {2*m['se_delta']:.4f} = "
            f"{m['delta_plus_2se']:.4f} < bar {L.BAR_DELTA_FLIP} (§6.1)",
        )
    if m["delta_flip"] >= L.BAR_DELTA_FLIP and m["swap_replication_rho"] >= L.BAR_SWAP_REPLICATION:
        r = pooled.get(L.LEG_REF)
        if r and r["delta_plus_2se"] < L.BAR_DELTA_FLIP:
            return (
                "OM-EXPRESSES + OM-DOSE-ONLY",
                "R_max clears the bar but R_ref (the built invader of record) is "
                "bounded below it — §6.4: stage 2 is NOT funded without a dose argument",
            )
        return "OM-EXPRESSES", "§6.2 — stage-2 prereg (§9) activates, UNFUNDED"
    if m["delta_flip"] >= L.BAR_DELTA_FLIP:
        return (
            "OM-UNRESOLVED",
            f"point estimate clears the bar but swap replication rho="
            f"{m['swap_replication_rho']:.3f} < {L.BAR_SWAP_REPLICATION} (§6.2 conjunct)",
        )
    return "OM-UNRESOLVED", "§6.3 — the narrow band; ONE n-extension is pre-authorised"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--legs-dir", type=Path, default=L.OUT_DIR / "LEGS")
    ap.add_argument("--out-dir", type=Path, default=L.OUT_DIR)
    ap.add_argument("--split", type=int, default=L.SPLIT)
    a = ap.parse_args(argv)

    raw, voided = [], []
    for p in sorted(a.legs_dir.glob("*.jsonl")):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            (raw if rec.get("ok") else voided).append(rec)
    if not raw:
        print("no usable leg records", file=sys.stderr)
        return 1

    rows = [analyze_row(r, a.split) for r in raw]
    pooled = summarize(rows, "POOLED")
    per_corpus = {
        c: summarize([r for r in rows if r["corpus"] == c], c)
        for c in sorted({r["corpus"] for r in rows})
    }
    br, why = branch(pooled)

    readout = L.manifest(
        {
            "step": "analyze_gate",
            "n_records": len(raw),
            "n_voided": len(voided),
            "voided_rids": [v.get("rid") for v in voided][:50],
            "pooled": pooled,
            "per_corpus": per_corpus,
            "branch_advisory": br,
            "branch_reason": why,
        }
    )
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "READOUT.json").write_text(json.dumps(readout, indent=2))
    (a.out_dir / "READOUT.md").write_text(_render_md(readout))
    print(json.dumps({"branch_advisory": br, "reason": why, "pooled": pooled}, indent=2))
    return 0


def _render_md(r: dict) -> str:
    p = r["pooled"]
    lines = [
        "# OM-M1 — refuter-leg arbitration, first kill-gate READOUT",
        "",
        f"Instrument: `{r['spec']}`. Records **{r['n_records']}** "
        f"(voided {r['n_voided']}). `B = {r['b_worlds']}`, split at "
        f"{r['split']}, salt `{r['salt']}`, J={r['arm_cap_j']}, eps={r['eps']}.",
        "",
        f"> **Branch (ADVISORY): `{r['branch_advisory']}`** — {r['branch_reason']}",
        ">",
        "> Adjudicate against `PREREG.md` §6 on the POOLED row, `R_max` first.",
        "",
        "## The bar, and where it came from",
        "",
        f"`bar = {r['bar_derivation']['target_pts_per_game']} pts/game x "
        f"(1 - 1/{r['bar_derivation']['mean_arms']}) / "
        f"{r['bar_derivation']['G_arb_pts_per_game']} pts/game = "
        f"{r['bar_derivation']['derived']:.5f}` -> frozen at "
        f"**{r['bar_delta_flip']}**` — the effect size the decision cares about, "
        "NOT 2 sigma-hat of the instrument (house rule, 2026-08-30).",
        "",
        "⭐ **The fire rate cancels out of the bar.** The naive form is "
        "`target / (F x R_x)`, but `R_x = G_arb / (F x P)`, so `F` appears in "
        "both halves. That matters: the `22.96 fired plies/game` figure in the "
        "tiearb plans is the **E4 stratum** (597 plies / 26 phone games), while "
        "this gate's own walled corpora bank **45.26** exact-tied tile "
        "plies/game — a bar that depended on `F` would have been ~2x wrong.",
        "",
        "## POOLED",
        "",
        f"- `p_flip(placebo)` = **{p['p_flip_placebo']:.4f}** (n {p['n']}) — the null: "
        "the flip rate a re-seeded tie-break stream produces on its own.",
        "",
        "| leg | n | p_flip(two-leg) | Δ_flip | se(Δ) | Δ+2se | ρ (swap) | implied pts/game |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in (L.LEG_MAX, L.LEG_REF):
        m = p.get(name)
        if not m:
            continue
        lines.append(
            f"| `{name}` | {m['n']} | {m['p_flip_two_leg']:.4f} | "
            f"**{m['delta_flip']:+.4f}** | {m['se_delta']:.4f} | "
            f"{m['delta_plus_2se']:+.4f} | {m['swap_replication_rho']:.3f} | "
            f"{m['implied_pts_per_game']:+.3f} |"
        )
    lines += ["", "## Per-corpus (diagnostic — never the branch input)", ""]
    for c, s in r["per_corpus"].items():
        m = s.get(L.LEG_MAX)
        if m:
            lines.append(
                f"- `{c}`: n {s['n']}, Δ_flip(R_max) {m['delta_flip']:+.4f} "
                f"± {m['se_delta']:.4f}, ρ {m['swap_replication_rho']:.3f}"
            )
    lines += [
        "",
        "## What this does NOT say",
        "",
        "A nonzero flip rate is **not** a claim that the flipped picks are better. "
        "Pricing them is PREREG §9's stage 2 — CL-084 independent-world "
        "selection/pricing split, then CL-085 out-of-family corroboration, then and "
        "only then a game cell. Nothing here enters `governance/PRODUCTION.yaml`.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
