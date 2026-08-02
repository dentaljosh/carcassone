#!/usr/bin/env python3
"""G3 / step 4 — assemble the three decompositions into one self-describing JSON
plus the publication figure's data table (CSV).  Pure arithmetic on the three
step JSONs; adds no new measurement, only derived ratios (each with its formula).
"""
from __future__ import annotations

import csv
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path("/home/doctor/projects/carcassone")

CORPUS = json.loads((HERE / "g3_corpus_decomp.json").read_text())
SIB = json.loads((HERE / "g3_sibling_decomp.json").read_text())
PHASE = json.loads((HERE / "g3_phase_curve.json").read_text())

# Numbers imported from prior, already-committed measurement (NOT recomputed here).
READOUT = REPO / "measurement" / "value_unlock_20260730" / "READOUT.md"
IMPORTED = {
    "value_unlock_v1_value_outcome_r_heldout": {
        "value": 0.6795,
        "source": str(READOUT) + " §2 (train log, `value↔outcome corr`)",
        "caveat": "within-window, position-level (READOUT §2 caveats a/b)",
    },
    "value_unlock_v1_solver_tau_within_root": {
        "value": 0.0190,
        "source": str(REPO / "measurement/value_unlock_20260730/VERDICT.json") + " / READOUT §4.1",
    },
    "iter_03_value_outcome_r_heldout": {"value": 0.6564, "source": "READOUT §2"},
    "iter_03_solver_tau_within_root": {"value": 0.0177, "source": "READOUT §4.1"},
    "heuristic_leaf_value_outcome_r_reference": {
        "value": 0.61, "source": "scripts/train_iter.py:706 (project reference), via READOUT §2",
    },
    "leaf_solver_tau_within_root": {"value": 0.6153, "source": "READOUT §4.1 (curve125 row)"},
    "value_unlock_v1_heldout_value_mse_best_epoch": {
        "value": 0.2708, "source": "READOUT §2 loss curve, epoch 2 val",
    },
}


def g(d, *ks):
    for k in ks:
        d = d[k]
    return d


def main() -> None:
    dy_pts = g(SIB, "decomposition", "solver_child_value_points")
    dy_tanh = g(SIB, "decomposition", "solver_child_value_tanh15")
    dl = g(SIB, "decomposition", "heuristic_leaf_value_tanh15")
    corpus_sd = g(CORPUS, "label_moments_all_rows", "sd")

    within_var_tanh = dy_tanh["var_total"] * dy_tanh["frac_within_root"]

    derived = {
        "sibling_residual_sd_over_training_label_sd": {
            "value": dy_tanh["sd_within_root"] / corpus_sd,
            "formula": "sd_within_root(tanh(solver_child_value/15)) / sd(training outcome label)",
            "inputs": [dy_tanh["sd_within_root"], corpus_sd],
        },
        "sibling_residual_var_over_heldout_value_mse": {
            "value": within_var_tanh / IMPORTED["value_unlock_v1_heldout_value_mse_best_epoch"]["value"],
            "formula": "var_within_root(tanh(solver_child_value/15)) / heldout value MSE of value_unlock_v1",
            "inputs": [within_var_tanh,
                       IMPORTED["value_unlock_v1_heldout_value_mse_best_epoch"]["value"]],
            "caveat": "CROSS-INSTRUMENT and indicative only: the numerator is exact-solver "
                      "variance on 1,119 K=2 endgame roots; the denominator is a held-out MSE "
                      "against sampled game outcomes over all plies of 120 val games. Same units "
                      "(tanh(score_diff/15)), different distributions.",
        },
        "leaf_within_root_advantage_over_value_head_tau": {
            "value": IMPORTED["leaf_solver_tau_within_root"]["value"]
                     / IMPORTED["value_unlock_v1_solver_tau_within_root"]["value"],
            "formula": "leaf tau / value_unlock_v1 tau (both within-root, same 1,119 roots)",
        },
        "position_level_ceiling_r2": {
            "value": dy_pts["frac_between_root"],
            "formula": "frac_between_root of the exact solver child value == R^2 of a predictor "
                       "that knows every root's mean exactly and nothing else",
        },
    }

    out = {
        "kind": "p1_paper_G3_label_variance_decomposition",
        "purpose": "Turn CLAIMS_LEDGER row D1 from interpretation into a measured decomposition: "
                   "how much of the outcome-label variance lives at the level an outcome-regression "
                   "value head can learn from, vs the between-sibling level move discrimination "
                   "actually consumes.",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "code_rev": subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                                   capture_output=True, text=True).stdout.strip(),
        "house_rules": "offline arithmetic only — no games, no search, no net forward, no GPU; "
                       "every number traceable to an input file named in `parts[*].inputs`.",
        "headline": {
            "training_corpus_outcome_label": {
                "n_games": g(CORPUS, "counts", "n_games"),
                "n_rows": g(CORPUS, "counts", "n_rows"),
                "frac_variance_at_game_x_side_level": g(CORPUS, "decomposition", "L2_game_x_side", "frac_between"),
                "frac_variance_at_position_level": g(CORPUS, "decomposition", "L2_game_x_side", "frac_within"),
                "frac_variance_at_sibling_level": 0.0,
                "sibling_level_note": "0 by construction — the corpus stores one row per decision "
                                      "(group_id == -1 on all 345,333 rows); sibling sets are absent.",
            },
            "exact_solver_child_value_K2_bank": {
                "n_roots": dy_pts["n_roots"],
                "n_children": dy_pts["n_children"],
                "frac_variance_between_root": dy_pts["frac_between_root"],
                "frac_variance_within_root": dy_pts["frac_within_root"],
                "frac_variance_within_root_tanh_units": dy_tanh["frac_within_root"],
            },
            "heuristic_leaf_value_same_bank": {
                "frac_variance_between_root": dl["frac_between_root"],
                "frac_variance_within_root": dl["frac_within_root"],
                "within_root_kendall_tau_vs_solver": g(SIB, "cross_level_agreement_leaf_vs_solver",
                                                       "within_root_kendall_tau_mean"),
            },
            "one_sentence": (
                "Of the label an outcome-trained value head sees, 100.0%% of the variance is fixed "
                "at the (game x side-to-move) level and 0.0%% varies across positions within a game; "
                "and even with perfect counterfactual labels, only %.3f%% of the exact-solver child-value "
                "variance on the 1,119-root bank lies between siblings — so a predictor explaining "
                "%.3f%% of the label variance can still carry zero move-ordering information."
                % (100 * dy_pts["frac_within_root"], 100 * dy_pts["frac_between_root"])
            ),
        },
        "derived": derived,
        "imported_from_prior_measurement": IMPORTED,
        "parts": {
            "corpus": CORPUS,
            "sibling_bank": SIB,
            "phase_curve_supplementary": PHASE,
        },
    }
    (HERE / "G3_VARIANCE_DECOMP.json").write_text(json.dumps(out, indent=2) + "\n")

    # ------------------------------------------------------------------ figure
    rows = []

    def add(panel, series, x, y, label, unit, source):
        rows.append({"panel": panel, "series": series, "x": x, "y": y,
                     "label": label, "unit": unit, "source": source})

    # Panel A — variance share by level (stacked bar, 4 quantities)
    A = "A_variance_share_by_level"
    add(A, "coarse_level", "training outcome label (345,333 rows / 2,400 games)",
        g(CORPUS, "decomposition", "L2_game_x_side", "frac_between"),
        "game x side-to-move", "fraction of total variance", "g3_corpus_decomp.json")
    add(A, "sibling_level", "training outcome label (345,333 rows / 2,400 games)",
        0.0, "between siblings", "fraction of total variance",
        "g3_corpus_decomp.json (group_id == -1: no sibling sets in the corpus)")
    add(A, "position_level", "training outcome label (345,333 rows / 2,400 games)",
        g(CORPUS, "decomposition", "L2_game_x_side", "frac_within"),
        "between positions within (game x side)", "fraction of total variance",
        "g3_corpus_decomp.json")
    for name, d, src in (
        ("exact solver child value (1,119 K=2 roots, tanh units)", dy_tanh, "g3_sibling_decomp.json"),
        ("heuristic leaf value (same 50,637 children)", dl, "g3_sibling_decomp.json"),
        ("h6400 search Q, all phases (10,067 roots) [supplementary]",
         PHASE["overall"], "g3_phase_curve.json"),
    ):
        add(A, "coarse_level", name, d["frac_between_root"], "between roots",
            "fraction of total variance", src)
        add(A, "sibling_level", name, d["frac_within_root"], "between siblings",
            "fraction of total variance", src)

    # Panel B — within-root variance fraction vs k_remaining
    B = "B_within_sibling_share_vs_game_phase"
    for k, d in sorted(PHASE["by_k_remaining"].items(), key=lambda kv: int(kv[0])):
        add(B, "h6400_search_Q", int(k), d["frac_within_root"],
            "k_remaining=%s (n_roots=%d)" % (k, d["n_roots"]),
            "fraction of total variance", "g3_phase_curve.json")
    add(B, "exact_solver", 2, dy_tanh["frac_within_root"],
        "exact solver, K=2 (n_roots=1119)", "fraction of total variance",
        "g3_sibling_decomp.json")

    # Panel C — position-level skill vs sibling-level skill, per ranker
    C = "C_position_skill_vs_sibling_skill"
    add(C, "value_outcome_r", "value_unlock_v1 (CL-073 head)",
        IMPORTED["value_unlock_v1_value_outcome_r_heldout"]["value"], "held-out r",
        "pearson r", "READOUT.md §2")
    add(C, "solver_tau", "value_unlock_v1 (CL-073 head)",
        IMPORTED["value_unlock_v1_solver_tau_within_root"]["value"], "within-root tau",
        "kendall tau-b", "VERDICT.json")
    add(C, "value_outcome_r", "iter_03 (warm parent)",
        IMPORTED["iter_03_value_outcome_r_heldout"]["value"], "held-out r",
        "pearson r", "READOUT.md §2")
    add(C, "solver_tau", "iter_03 (warm parent)",
        IMPORTED["iter_03_solver_tau_within_root"]["value"], "within-root tau",
        "kendall tau-b", "READOUT.md §4.1")
    add(C, "value_outcome_r", "hand-crafted leaf",
        IMPORTED["heuristic_leaf_value_outcome_r_reference"]["value"], "held-out r (reference)",
        "pearson r", "train_iter.py:706 via READOUT §2")
    add(C, "solver_tau", "hand-crafted leaf",
        IMPORTED["leaf_solver_tau_within_root"]["value"], "within-root tau",
        "kendall tau-b", "READOUT.md §4.1")
    add(C, "value_outcome_r", "root-mean oracle (position-level perfect)",
        1.0, "R^2 = %.5f of label variance" % dy_pts["frac_between_root"],
        "pearson r", "g3_sibling_decomp.json position_level_oracle")
    add(C, "solver_tau", "root-mean oracle (position-level perfect)",
        0.0, "within-root tau = 0 by construction", "kendall tau-b",
        "g3_sibling_decomp.json position_level_oracle")
    add(C, "value_outcome_r", "pooled-MSE ridge on the leaf's own features [supplementary]",
        g(SIB, "supplementary_pooled_mse_ridge", "r2_pooled"), "cross-fit R^2 (pooled)",
        "r^2", "g3_sibling_decomp.json")
    add(C, "solver_tau", "pooled-MSE ridge on the leaf's own features [supplementary]",
        g(SIB, "supplementary_pooled_mse_ridge", "within_root_kendall_tau_mean"),
        "within-root tau", "kendall tau-b", "g3_sibling_decomp.json (== CL-065 gate_full_ridge)")

    with open(HERE / "G3_FIGURE_DATA.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["panel", "series", "x", "y", "label", "unit", "source"],
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(out["headline"]["one_sentence"])
    print("rows in figure table:", len(rows))


if __name__ == "__main__":
    main()
