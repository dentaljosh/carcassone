#!/usr/bin/env python3
"""ARBCOST component (iii) — phase-resolved cost model and option pricing.

Banked inputs only. No timing is measured here; the constants are carried verbatim
from COST_REMEASURE.json and the published rho identities. See PREREG.md section 3.5.

Emits: COST_MODEL.json
"""
from __future__ import annotations

import json
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# --- carried verbatim (scripts/tiletie/bench_tier1_rust.py:54-58,
#     scripts/tiletie/analyze_tiearb2.py:78-79) --------------------------------
A_BAR = 3.0022            # POSITIONS_PLAN.json::mean_arms
T_CHAMP = 13.7552         # champion k8x1376, SEQUENTIAL single-box, s/move
T_PHONE = 1.551           # shipped phone champion at rust_threads: 2, s/move
PHI_PRIOR = 22.96         # offline tied TILE plies/game (E4 census, n = 26)
MOVES_PER_GAME = 72.0
RHO_BAR = 1.20            # the retired N4 affordability bar

COST = json.load(open(os.path.join(
    REPO, "measurement/tiearb2_stage2_20260817/COST_REMEASURE.json")))
C_W30 = COST["c_tier1_rust_w30"]      # 0.17823232 worker-s / playout
C_W1 = COST["c_tier1_rust_w1"]        # 0.09376926 worker-s / playout

# --- deployed shape (governance/PRODUCTION.yaml, tiearb block) ----------------
DEPLOY = {
    "desktop": {"enabled": True, "B": 64, "J": 4, "mode": "argmax",
                "threads": 8, "threads_speedup_measured": [6.5, 6.8]},
    "mobile": {"enabled": False,
               "note": "PRODUCTION.yaml: 'MOBILE: still no arbiter at all'. "
                       "rho_phone(64) ~ 22-24, unsolved third currency. The "
                       "funding brief's 'B=32 mobile' does not exist."},
    "desktop_stated_ms_per_move": {
        "armed_total_s": 6.0, "champion_baseline_s": 1.8,
        "source": "governance/PRODUCTION.yaml tiearb WIRING note, lines 200-201: "
                  "'~3.5x per move sequential (~6 s/move vs the ~1.8 s champion "
                  "baseline), fires on tied plies only'"},
}

PHASES = ["early", "mid", "late"]
PHASE_CUTS = {"early": (48, 10 ** 9), "mid": (24, 48), "late": (-1, 24)}


def phase_bucket(k):
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k < hi:
            return name
    return "late"


# --------------------------------------------------------------------------- #
def census_block():
    """phi_p (fired tile plies per game) and Abar_p from the banked census."""
    path = os.path.join(
        REPO, "measurement/tiearb_widening_20260817/census/tile_gap_rows.jsonl")
    games = set()
    n_ply = defaultdict(int)
    n_fire = defaultdict(int)
    arms_sum = defaultdict(float)
    arms_sum_uncapped = defaultdict(float)
    for line in open(path):
        d = json.loads(line)
        games.add(d["game_id"])
        p = d["phase_bucket"]
        n_ply[p] += 1
        if d["tie_exact"]:
            n_fire[p] += 1
            arms_sum[p] += min(int(d["tie_size_exact"]), 4)   # J = 4 cap
            arms_sum_uncapped[p] += int(d["tie_size_exact"])
    g = len(games)
    out = {"source": os.path.relpath(path, REPO), "n_games": g,
           "n_tile_plies": sum(n_ply.values()), "J_cap": 4, "by_phase": {}}
    for p in PHASES:
        out["by_phase"][p] = {
            "tile_plies_per_game": n_ply[p] / g,
            "fired_plies_per_game_phi": n_fire[p] / g,
            "fire_rate": n_fire[p] / max(1, n_ply[p]),
            "Abar_capped_J4": arms_sum[p] / max(1, n_fire[p]),
            "Abar_uncapped": arms_sum_uncapped[p] / max(1, n_fire[p]),
            "n_fired": n_fire[p], "n_plies": n_ply[p],
        }
    phi_tot = sum(out["by_phase"][p]["fired_plies_per_game_phi"] for p in PHASES)
    abar_tot = (sum(out["by_phase"][p]["fired_plies_per_game_phi"]
                    * out["by_phase"][p]["Abar_capped_J4"] for p in PHASES)
                / phi_tot)
    out["phi_total_measured"] = phi_tot
    out["phi_prior_of_record"] = PHI_PRIOR
    out["phi_ratio_measured_over_prior"] = phi_tot / PHI_PRIOR
    out["Abar_total_measured_J4"] = abar_tot
    out["Abar_of_record"] = A_BAR
    out["Abar_ratio"] = abar_tot / A_BAR
    out["falsifier_4_fired"] = bool(
        out["phi_ratio_measured_over_prior"] > 2 or
        out["phi_ratio_measured_over_prior"] < 0.5)
    out["note"] = ("corpus champ449, rules_profile walled, eps 0.0 exact ties "
                   "(the deployed tiearb eps). TILE plies only -- the deployed "
                   "arbiter's cost model of record (phi = 22.96 tied TILE plies) "
                   "excludes the meeple rung (4.82/game, not deployed).")
    return out


def ply_length_block():
    """r_p = mean playout plies in phase p / mean over all, + the seconds check."""
    import glob
    base = os.path.join(REPO, "measurement/tiearb_widening_20260817/rung3_r5")
    arms = json.load(open(os.path.join(base, "corpus/positions_s2/ARMS.json")))
    plies = defaultdict(list)
    secs = defaultdict(list)
    for f in glob.glob(os.path.join(
            base, "legs/s2/tier1-greedy/walled/leg*/records/*.json")):
        d = json.load(open(f))
        a = arms.get(d["rid"])
        if not a:
            continue
        p = a["phase_bucket"]
        pl = float(np.mean(list(d["playout_plies_a"]) + list(d["playout_plies_b"])))
        plies[p].append(pl)
        plies["ALL"].append(pl)
        e = d.get("elapsed_secs")
        if e:
            per = float(e) / (2 * int(d["m"]))
            secs[p].append(per)
            secs["ALL"].append(per)
    out = {"source": "rung3_r5 legs s2/tier1-greedy (6,602 records)",
           "by_phase": {}, "r_from_plies": {}, "r_from_secs": {}}
    m_pl = float(np.mean(plies["ALL"]))
    m_sc = float(np.mean(secs["ALL"]))
    for p in PHASES + ["ALL"]:
        out["by_phase"][p] = {
            "n_records": len(plies[p]),
            "mean_playout_plies": float(np.mean(plies[p])),
            "mean_worker_secs_per_playout_contended": float(np.mean(secs[p])),
        }
        out["r_from_plies"][p] = float(np.mean(plies[p])) / m_pl
        out["r_from_secs"][p] = float(np.mean(secs[p])) / m_sc
    out["max_abs_rel_disagreement"] = max(
        abs(out["r_from_plies"][p] - out["r_from_secs"][p])
        / out["r_from_secs"][p] for p in PHASES)
    out["falsifier_5_threshold"] = 0.15
    out["falsifier_5_fired"] = bool(out["max_abs_rel_disagreement"] > 0.15)
    out["r_used"] = (out["r_from_secs"] if out["falsifier_5_fired"]
                     else out["r_from_plies"])
    out["r_used_which"] = ("r_from_secs (PREREG 3.5 fallback fired)"
                           if out["falsifier_5_fired"] else "r_from_plies")
    out["seconds_caveat"] = ("mean_worker_secs_per_playout_contended is measured "
                             "under the rung3_r5 run's own W-parallel contention "
                             "and is used ONLY as a RATIO cross-check; the absolute "
                             "cost constant of record stays COST_REMEASURE's c.")

    # --- THIRD, INDEPENDENT cost-curve model (DECLARED DEVIATION, see below) --
    # measurement/arb_costopt_prep/PROFILE_TIER1.md (branch
    # worktree-agent-aa60f233af0253f99), section 3: an EXCLUSIVE-TENANT sequential
    # bench, 480 playouts over 10 root plies, identity-gated 480/480 against
    # production tier1_playout. ms/playout by root ply, mapped to a phase by the
    # SAME PHASE_CUTS (k_remaining = 72 - ply//2).
    profile_ms = {6: 96.67, 14: 100.23, 22: 103.52, 30: 103.44, 40: 100.47,
                  50: 96.10, 60: 102.47, 72: 83.84, 86: 73.21, 100: 50.36}
    prof = defaultdict(list)
    for ply, ms in profile_ms.items():
        prof[phase_bucket(72 - ply // 2)].append(ms)
    out["profile_ms_by_phase"] = {
        p: {"root_plies": sorted(72 - 2 * 0 for _ in prof[p]),
            "n_grid_points": len(prof[p]),
            "mean_ms_per_playout": float(np.mean(prof[p]))} for p in prof}
    out["profile_grid_map"] = {str(ply): phase_bucket(72 - ply // 2)
                               for ply in sorted(profile_ms)}
    out["r_from_profile_unnormalised"] = {
        p: float(np.mean(prof[p])) for p in PHASES}
    out["profile_caveat"] = (
        "the LATE bucket has ONE grid point (root ply 100, k_remaining 22) and it "
        "sits at the shallow edge of late; deeper-late roots are cheaper still, so "
        "r_late from this model is an UPPER bound and the early share it implies is "
        "a LOWER bound. Different box (laptop i7-14650HX) -- used as a RATIO only.")
    out["profile_source"] = ("measurement/arb_costopt_prep/PROFILE_TIER1.md section 3 "
                             "(branch worktree-agent-aa60f233af0253f99), 480 playouts, "
                             "exclusive tenancy, identity gate 480/480")
    return out


# --------------------------------------------------------------------------- #
def worker_secs_per_game(cens, r, B_by_phase, race_frac_by_phase, c, kphi=1.0):
    """S = sum_p kphi*phi_p * Abar_p * B_p * c * r_p * race_p (worker-s/game)."""
    tot = 0.0
    parts = {}
    for p in PHASES:
        cp = cens["by_phase"][p]
        s = (kphi * cp["fired_plies_per_game_phi"] * cp["Abar_capped_J4"]
             * B_by_phase[p] * c * r[p] * race_frac_by_phase[p])
        parts[p] = s
        tot += s
    return tot, parts


def main():
    cens = census_block()
    plen = ply_length_block()
    r = plen["r_used"]
    r_alt = (plen["r_from_plies"] if plen["falsifier_5_fired"]
             else plen["r_from_secs"])
    # normalise the profile model against the census FIRE mix so it is on the
    # same footing as r_from_secs / r_from_plies (whose denominators are the
    # rung3_r5 record mix, phase-balanced by construction: 2221/2156/2225)
    fires = {p: cens["by_phase"][p]["fired_plies_per_game_phi"] for p in PHASES}
    ftot = sum(fires.values())
    pu = plen["r_from_profile_unnormalised"]
    pnorm = sum(fires[p] / ftot * pu[p] for p in PHASES)
    r_prof = {p: pu[p] / pnorm for p in PHASES}
    plen["r_from_profile"] = r_prof
    race = json.load(open(os.path.join(HERE, "RACING_SIM.json")))

    flat = {p: 1.0 for p in PHASES}
    B64 = {p: 64 for p in PHASES}

    # --- phi CALIBRATION -----------------------------------------------------
    # The census fire predicate is a LEAF top-1 tie (1-ply v2.9 leaf, eps 0.0),
    # not the deployed arbiter's POST-SEARCH root tie. It measures 45.26 fired
    # tile plies/game against the 22.96 figure the deployed rho model of record
    # uses. The PHASE SHARES are what this package needs from the census; the
    # absolute level is taken from the record. K_PHI rescales phi_p so the total
    # reproduces 22.96 while leaving every share and every RATIO untouched.
    K_PHI = PHI_PRIOR / cens["phi_total_measured"]

    out = {
        "artifact": "COST_MODEL",
        "prereg": "measurement/arb_costopt_prep/PREREG.md",
        "generated_by": "measurement/arb_costopt_prep/cost_model.py",
        "constants": {"A_BAR_of_record": A_BAR, "T_CHAMP_s_per_move": T_CHAMP,
                      "T_PHONE_s_per_move": T_PHONE, "PHI_PRIOR": PHI_PRIOR,
                      "MOVES_PER_GAME": MOVES_PER_GAME, "RHO_BAR": RHO_BAR,
                      "c_tier1_rust_w30": C_W30, "c_tier1_rust_w1": C_W1,
                      "c_source": "measurement/tiearb2_stage2_20260817/"
                                  "COST_REMEASURE.json (G-BITEXACT PASS)"},
        "identities_of_record": {
            "worker_secs_per_tied_ply(B)": "Abar * B * c",
            "rho_wall(B)": "Abar * B * c / 13.7552",
            "rho_amortized(B)": "rho_wall(B) * 22.96 / 72",
            "rho_phone(B)": "Abar * B * c / 1.551",
            "source": "scripts/tiletie/bench_tier1_rust.py::ladder, "
                      "scripts/tiletie/analyze_tiearb2.py::rho_ladder"},
        "deploy_shape": DEPLOY,
        "declared_deviation_r_from_profile": (
            "PREREG 3.5 named TWO r_p models (plies, seconds) and a fallback rule. "
            "A THIRD, independently measured model arrived mid-analysis: "
            "PROFILE_TIER1.md section 3 (sibling instrument, exclusive tenancy, "
            "480 identity-gated playouts). It is REPORTED as corroboration and is "
            "NOT substituted for the PREREG-mandated primary -- which is legitimate "
            "precisely because the two AGREE (early share 0.4200 vs 0.4256). No "
            "estimator was shopped: the fallback fired on the pre-registered 15% "
            "rule before this model existed."),
        "ratio_composability": (
            "every multiplier here is a RATIO against the current deployed shape, "
            "so it composes multiplicatively with any constant-factor engine change "
            "-- e.g. the separately-gated 7.90x bit-identical count_final_scores "
            "swap (PROFILE_TIER1.md section 4). Absolute worker-seconds are quoted "
            "at TODAY's engine and would divide by that factor if it lands. NOTE: "
            "the swap's factor is itself occupancy-dependent (4.7x on a near-empty "
            "board, 8.2x at 65-77 placed tiles), so it does NOT cancel out of the "
            "phase shares -- it would shift them FURTHER toward early."),
        "census": cens,
        "playout_length": plen,
        "phase_cost_share_at_current_deploy": {},
        "options": {},
    }

    # --- reproduce the published rho ladder as a self-check ------------------
    out["published_rho_reproduction"] = {
        f"B{b}": {"worker_secs_per_tied_ply": A_BAR * b * C_W30,
                  "rho_wall": A_BAR * b * C_W30 / T_CHAMP,
                  "rho_amortized": A_BAR * b * C_W30 / T_CHAMP * PHI_PRIOR / MOVES_PER_GAME,
                  "rho_phone": A_BAR * b * C_W30 / T_PHONE}
        for b in (1, 2, 4, 8, 16, 32, 64)}
    out["published_rho_reproduction"]["check"] = (
        "rho_wall(64) here vs PRODUCTION.yaml's stated 2.4897 and rho_phone(64) "
        "vs its stated '~22-24'")

    # --- phase cost shares at the CURRENT deploy -----------------------------
    base_s30, base_parts30 = worker_secs_per_game(cens, r, B64, flat, C_W30, K_PHI)
    base_s1, base_parts1 = worker_secs_per_game(cens, r, B64, flat, C_W1, K_PHI)
    _, alt_parts = worker_secs_per_game(cens, r_alt, B64, flat, C_W30, K_PHI)
    alt_tot = sum(alt_parts.values())
    _, prof_parts = worker_secs_per_game(cens, r_prof, B64, flat, C_W30, K_PHI)
    prof_tot = sum(prof_parts.values())
    out["phi_calibration"] = {
        "K_PHI": K_PHI,
        "phi_measured_total": cens["phi_total_measured"],
        "phi_of_record": PHI_PRIOR,
        "why": ("the census fire predicate is a LEAF top-1 exact tie (1-ply v2.9 "
                "leaf, eps 0.0); the deployed arbiter fires on a POST-SEARCH root "
                "tie. The census supplies the PHASE SHARES; the absolute fired-plies"
                "-per-game level is taken from the record (22.96). Every ratio and "
                "multiplier in this file is INVARIANT to K_PHI."),
        "residual_risk": ("if the post-search tie rate is not phase-proportional to "
                          "the leaf tie rate, the SHARES are biased and this package "
                          "cannot say by how much. NOT measurable from banked data."),
    }
    out["phase_cost_share_at_current_deploy"] = {
        "worker_secs_per_game_W30": base_s30,
        "worker_secs_per_game_W1": base_s1,
        "rho_amortized_reproduced": base_s30 / MOVES_PER_GAME / T_CHAMP,
        "rho_amortized_of_record_B64": A_BAR * 64 * C_W30 / T_CHAMP
                                       * PHI_PRIOR / MOVES_PER_GAME,
        "share_PRIMARY_r_from_secs": {p: base_parts30[p] / base_s30 for p in PHASES},
        "share_SENSITIVITY_r_from_plies": {p: alt_parts[p] / alt_tot for p in PHASES},
        "share_CORROBORATION_r_from_profile": {p: prof_parts[p] / prof_tot
                                               for p in PHASES},
        "three_model_note": (
            "r_from_plies is the ADVISORY's model and is REFUTED by two independent "
            "cost measurements: this package's contended per-record seconds "
            "(rung3_r5, n=6,602) and the exclusive-tenant sequential profile "
            "(PROFILE_TIER1.md section 3, n=480, identity-gated). Both say cost is "
            "NOT proportional to remaining plies -- per-ply cost rises ~1.8x as the "
            "board fills, so the long early playouts run on cheap small boards. The "
            "two measured models agree on the early share to within 1 percentage "
            "point; the ply model over-states it by ~14 points."),
        "share_if_r_ignored": {
            p: (cens["by_phase"][p]["fired_plies_per_game_phi"]
                * cens["by_phase"][p]["Abar_capped_J4"])
               / sum(cens["by_phase"][q]["fired_plies_per_game_phi"]
                     * cens["by_phase"][q]["Abar_capped_J4"] for q in PHASES)
            for p in PHASES},
        "advisory_56pct_reconciliation": (
            "the 2026-08-28 advisory's 'early ~56% of arbiter cost' is the "
            "r_from_plies (playout-LENGTH) model. The PREREG-mandated fallback "
            "(r_from_secs, fired because the two models disagree 35.6% > 15%) puts "
            "early at share_PRIMARY_r_from_secs. Mechanism: early playouts are "
            "~1.68x LONGER but each ply runs on a SMALLER board, so measured "
            "worker-seconds scale by only ~1.27x. Both are printed; the seconds "
            "model is the one with a stopwatch behind it and is the CONSERVATIVE "
            "one for the gate proposal."),
        "note": ("share_if_r_ignored is the fires-only share, printed so the two "
                 "mechanisms (more fires vs costlier playouts) stay separable"),
    }

    # --- the options ---------------------------------------------------------
    def add(name, B_by_phase, race_by_phase, desc, loss_note):
        s30, parts30 = worker_secs_per_game(cens, r, B_by_phase, race_by_phase,
                                            C_W30, K_PHI)
        s1, _ = worker_secs_per_game(cens, r, B_by_phase, race_by_phase,
                                     C_W1, K_PHI)
        alt30, _ = worker_secs_per_game(cens, r_alt, B_by_phase, race_by_phase,
                                        C_W30, K_PHI)
        pro30, _ = worker_secs_per_game(cens, r_prof, B_by_phase, race_by_phase,
                                        C_W30, K_PHI)
        mult = s30 / base_s30
        stated = DEPLOY["desktop_stated_ms_per_move"]
        arb_s_per_move_now = stated["armed_total_s"] - stated["champion_baseline_s"]
        out["options"][name] = {
            "description": desc,
            "B_by_phase": dict(B_by_phase),
            "race_fraction_by_phase": dict(race_by_phase),
            "cost_multiplier_vs_current": mult,
            "cost_multiplier_sensitivity_r_from_plies": alt30 / alt_tot,
            "cost_multiplier_corroboration_r_from_profile": pro30 / prof_tot,
            "speedup_vs_current": (1.0 / mult) if mult else None,
            "eval_cell_worker_s_per_game_W30": s30,
            "eval_cell_worker_s_per_game_W1": s1,
            "eval_cell_worker_s_saved_per_game_W30": base_s30 - s30,
            "desktop_s_per_move_total_stated_calibration": (
                stated["champion_baseline_s"] + arb_s_per_move_now * mult),
            "desktop_arbiter_s_per_move": arb_s_per_move_now * mult,
            "desktop_rho_amortized_equivalent": (
                s30 / MOVES_PER_GAME / T_CHAMP),
            "phone_hypothetical_s_per_game_kappa1_W1": s1,
            "phone_hypothetical_min_per_game_kappa1_W1": s1 / 60.0,
            "phone_rho_phone_equivalent": s30 / PHI_PRIOR / T_PHONE,
            "capture_at_risk": loss_note,
        }

    add("current_B64_all_phases", B64, flat,
        "the deployed desktop shape (PRODUCTION.yaml: B=64, J=4, threads=8)",
        "none -- this is the incumbent")

    add("gate_off_early", {"early": 0, "mid": 64, "late": 64}, flat,
        "do not fire the arbiter at all when k_remaining > 48",
        "the early-bucket capture, PHASE_B_CAPTURE.json::corpus_A.ladder.B64.early")

    add("B16_early", {"early": 16, "mid": 64, "late": 64}, flat,
        "fire at B=16 when k_remaining > 48, B=64 otherwise",
        "early(B64) - early(B16), PHASE_B_CAPTURE.json::corpus_A.ladder")

    add("B16_early_B32_mid", {"early": 16, "mid": 32, "late": 64}, flat,
        "B=16 early, B=32 mid, B=64 late",
        "early(B64)-early(B16) and mid(B64)-mid(B32)")

    for z in (1.5, 2.0, 2.5, 3.0):
        fr = race["j4_race"]["ALL"][f"z{z}"]["playout_fraction"]["value"]
        fr_p = {"early": race["j4_race"]["EARLY"][f"z{z}"]["playout_fraction"]["value"],
                "mid": race["j4_race"]["MIDLATE"][f"z{z}"]["playout_fraction"]["value"],
                "late": race["j4_race"]["MIDLATE"][f"z{z}"]["playout_fraction"]["value"]}
        add(f"racing_z{z}", B64, fr_p,
            f"paired sequential stopping at z={z}, first check at 4 worlds "
            f"(MEASURED at m=32; the deployed B=64 fraction is BRACKETED, see "
            f"RACING_SIM.json::b64_worlds_fraction_{{lower,upper}}_bound)",
            f"flip rate {race['j4_race']['ALL'][f'z{z}']['sign_flip_rate']['value']:.4f}"
            f", capture-weighted loss (ARBITER currency) "
            f"{race['j4_race']['ALL'][f'z{z}']['capture_weighted_loss_arbiter_currency']['value']:.4f}"
            f" pts/fire")
        fr_pr = {"early": race["j4_prune"]["EARLY"][f"z{z}"]["playout_fraction"]["value"],
                 "mid": race["j4_prune"]["MIDLATE"][f"z{z}"]["playout_fraction"]["value"],
                 "late": race["j4_prune"]["MIDLATE"][f"z{z}"]["playout_fraction"]["value"]}
        add(f"racing_prune_z{z}", B64, fr_pr,
            f"racing + trailing-arm pruning at t in {{8,16}}, z={z} (m=32)",
            f"flip rate {race['j4_prune']['ALL'][f'z{z}']['sign_flip_rate']['value']:.4f}")
        add(f"gate_off_early_plus_racing_z{z}", {"early": 0, "mid": 64, "late": 64},
            fr_p,
            f"phase gate OFF early + racing z={z} on mid/late",
            "early capture + the mid/late flip loss, both cited above")

    # --- B=64 bracket versions of the racing options -------------------------
    out["racing_b64_bracket"] = {}
    for z in (1.5, 2.0, 2.5, 3.0):
        lo = {"early": race["j4_race"]["EARLY"][f"z{z}"]["b64_worlds_fraction_lower_bound"]["value"],
              "mid": race["j4_race"]["MIDLATE"][f"z{z}"]["b64_worlds_fraction_lower_bound"]["value"],
              "late": race["j4_race"]["MIDLATE"][f"z{z}"]["b64_worlds_fraction_lower_bound"]["value"]}
        hi = {"early": race["j4_race"]["EARLY"][f"z{z}"]["b64_worlds_fraction_upper_bound"]["value"],
              "mid": race["j4_race"]["MIDLATE"][f"z{z}"]["b64_worlds_fraction_upper_bound"]["value"],
              "late": race["j4_race"]["MIDLATE"][f"z{z}"]["b64_worlds_fraction_upper_bound"]["value"]}
        s_lo, _ = worker_secs_per_game(cens, r, B64, lo, C_W30, K_PHI)
        s_hi, _ = worker_secs_per_game(cens, r, B64, hi, C_W30, K_PHI)
        g_lo, _ = worker_secs_per_game(cens, r, {"early": 0, "mid": 64, "late": 64},
                                       lo, C_W30, K_PHI)
        g_hi, _ = worker_secs_per_game(cens, r, {"early": 0, "mid": 64, "late": 64},
                                       hi, C_W30, K_PHI)
        out["racing_b64_bracket"][f"z{z}"] = {
            "cost_multiplier_bracket_vs_current": [s_lo / base_s30, s_hi / base_s30],
            "speedup_bracket": [base_s30 / s_hi, base_s30 / s_lo],
            "gate_off_early_plus_racing_multiplier_bracket": [
                g_lo / base_s30, g_hi / base_s30],
            "gate_off_early_plus_racing_speedup_bracket": [
                base_s30 / g_hi, base_s30 / g_lo],
            "why_a_bracket": ("a z-threshold on a paired mean fires at an ABSOLUTE "
                              "world index; the banked matrices stop at m=32, so a "
                              "position that never fired by 32 has a true fire index "
                              "in (32, 64] or never. LOWER assumes 32, UPPER assumes "
                              "64. The truth is inside."),
        }

    dst = os.path.join(HERE, "COST_MODEL.json")
    with open(dst, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote", dst)


if __name__ == "__main__":
    main()
