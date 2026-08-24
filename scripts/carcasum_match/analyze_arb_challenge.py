#!/usr/bin/env python3
"""Read-out for the CARCASUM ARBITER-TRANSFER CHALLENGE — the analyzer named in
``measurement/carcasum_arb_challenge_prep/DESIGN.md`` §7/§10 and cited by
``READ_RULE.md`` and ``WORKERS.conf::ADJUDICATOR``.

Two arms, ONE shared deck band: ARM-OFF (the production champion, no tie-arbiter,
byte-identical config to `carcasum_match_r1`) and ARM-ON (the SAME champion + the
root tie-arbiter exactly as `governance/PRODUCTION.yaml fair_deploy.tiearb`
specifies: B=64, J=4, argmax, salt tiearb2-deploy-v1, eps 0.0), both vs the SAME
Carcasum `MCTSPlayer<PortionUtility,RandomPlayout>@5000ms/turn` config.

PRIMARY statistic: the deck-paired difference of margins, `D = M_ON - M_OFF`, over
decks common to both arms (READ_RULE.md §1). This is a difference-of-differences —
NOT either arm's own absolute margin vs Carcasum — so it needs its own analyzer
rather than reusing `match.py`'s own `summarize()` or rung 2's `analyze_ladder.py`
(neither computes a cross-ARM paired statistic; both operate within a single
opponent-config axis).

Nine structural gates, all fail-closed (READ_RULE.md §3): G-BINARY, G-RULES,
G-BUDGET, G-CHAMP-OFF, G-CHAMP-ON, G-SINGLEVAR, G-N, G-SHARED-DECKS, G-TIMING.
`G-SINGLEVAR` is new to this family (ported from the `track_d2_prep` lesson,
`results.csv d2_rung_compression_U_UNREADABLE...b141e9`: the two arms' manifests
must agree on EVERYTHING except the arbiter block, checked here rather than only
asserted in prose) and `G-CHAMP` is split into `G-CHAMP-OFF`/`G-CHAMP-ON` because,
uniquely in this cell, one arm is SUPPOSED to have the arbiter present.

Branch table (READ_RULE.md §4): T-TRANSFER / W-WASHOUT / N-NEGATIVE (a brief
deviation, flagged in READ_RULE.md's own preamble) / one-time top-up / U-UNREADABLE,
first-match-wins, `D` (void-contaminated) checked first.

Usage (real read-out, once games exist):
    .venv/bin/python scripts/carcasum_match/analyze_arb_challenge.py \\
        --arm-off measurement/carcasum_arb_challenge_20260824/arm_off/games.jsonl \\
        --arm-on  measurement/carcasum_arb_challenge_20260824/arm_on/games.jsonl

Usage (math self-test, no archives, no band spent):
    .venv/bin/python scripts/carcasum_match/analyze_arb_challenge.py --selftest
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: READ_RULE.md §3.1 — imported vocabulary, not redefined; the arbiter's presence
#: or absence is a search-time knob, not a rules knob, so the taxonomy is unchanged
#: from r1/rung2.
REAL_DIVERGENCE_CLASSES = frozenset({
    "SCORE_FINAL", "FARM_SCORE_FINAL", "MEEPLE_LEGALITY", "MEEPLE_SLOT_UNMAPPED",
    "LEGALITY_OURS_EXTRA", "HARNESS_ERROR", "DRIVER_REJECT", "SEAT_DESYNC",
    "COORD_FRAME_MISMATCH",
})

VOID_RATE_BAR = 0.01              # READ_RULE.md §3.1 — 1% of an ARM's own games
G_N_FLOOR_FRACTION = 0.80         # READ_RULE.md §3 G-N
G_TIMING_TOLERANCE_PCT = 10.0     # READ_RULE.md §3 G-TIMING (looser than rung2's
                                   # playout-mode G-MODE ±5% — TIME mode is thread-CPU
                                   # time and can drift under real contention)
EQUIVALENCE_BAR_PTS = 2.0         # READ_RULE.md §4 — reused verbatim from r1's own
                                   # Branch B numeric bar (same units, same family)
Z_BAR = 2.0                       # READ_RULE.md §4 T/N branch z threshold

#: Pinned reference values (READ_RULE.md §3), sourced from r1's own frozen corpus
#: and governance/PRODUCTION.yaml, both independently agreeing.
PROD_LEAF_HASH = "a36d2e15a3b3d71d"
ARMED_TIEARB_SPEC = {"enabled": True, "B": 64, "J": 4, "mode": "argmax",
                     "salt": "tiearb2-deploy-v1", "eps": 0.0}
#: DESIGN.md §4 — the shared 250-seed band (200 primary + 50 reserved top-up),
#: reused verbatim by BOTH arms (within-pair CRN); per-arm separation is by
#: OUTPUT PATH, not seed offset.
SHARED_DECK_SEED_LO = 147_000_000_000
SHARED_DECK_SEED_HI = 147_000_000_249

#: The opponent config held fixed across BOTH arms (DESIGN.md §2), byte-identical
#: to r1's own configuration.
EXPECTED_OPPONENT = {
    "kind": "mcts", "budget_ms": 5000, "playouts": None, "cp": 0.5,
    "reuse_tree": False, "node_priors": False, "progressive_widening": False,
    "progressive_bias": False, "utility": "portion", "playout": "random",
}


# --------------------------------------------------------------------------- #
# loading                                                                      #
# --------------------------------------------------------------------------- #
def load(path: Path | str) -> list[dict]:
    out = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _wr_to_elo(wr: float) -> float | None:
    if wr <= 0.0 or wr >= 1.0:
        return None
    return -400.0 * math.log10(1.0 / wr - 1.0)


def _first_manifest(records: list[dict]) -> dict | None:
    """games.jsonl line 1's manifest — the address READ_RULE.md §3 names for every
    structural gate below. Absent records or a non-dict manifest are both FAIL,
    never a skip (fail-closed, per the table)."""
    if not records:
        return None
    m = records[0].get("manifest")
    return m if isinstance(m, dict) else None


# --------------------------------------------------------------------------- #
# per-arm stats (win rate/elo, void ledger, per-deck-per-seat margin, G-TIMING) #
# --------------------------------------------------------------------------- #
def per_arm_stats(records: list[dict]) -> dict:
    voids: dict[str, int] = {}
    real_divergences: dict[str, int] = {}
    for r in records:
        if r.get("void"):
            voids[r["void"]] = voids.get(r["void"], 0) + 1
        for cls, n in (r.get("counts") or {}).items():
            if cls in REAL_DIVERGENCE_CLASSES and n:
                real_divergences[cls] = real_divergences.get(cls, 0) + int(n)

    ok = [r for r in records if not r.get("void") and r.get("winner")]
    wins = sum(1 for r in ok if r["winner"] == "champ")
    draws = sum(1 for r in ok if r["winner"] == "draw")
    n = len(ok)

    # per-deck, per-seat margin (a deck's 0/1-seat games averaged only once BOTH
    # seats exist — the seat-pairing rung 1/rung 2 already use).
    by_deck: dict[int, dict[int, list[int]]] = {}
    for r in ok:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["champ_seat"]), []).append(int(r["margin_champ_minus_opp"]))
    paired_by_deck: dict[int, float] = {}
    for deck, seats in by_deck.items():
        if len(seats) == 2:
            paired_by_deck[deck] = sum(sum(v) / len(v) for v in seats.values()) / 2.0
    paired = list(paired_by_deck.values())
    mean_p = sum(paired) / len(paired) if paired else None
    var_p = (sum((x - mean_p) ** 2 for x in paired) / (len(paired) - 1)
             if paired and len(paired) > 1 else None)
    sem_p = (var_p / len(paired)) ** 0.5 if var_p is not None else None

    # G-TIMING: median realized opp_driver ms/turn, pooled from move_log's
    # `carcasum_ms` field (the per-move driver-reported wall cost of a real
    # opponent turn — same address rung2 used for `carcasum_playouts`).
    pooled_ms = [
        m["carcasum_ms"]
        for r in records if not r.get("void")
        for m in (r.get("moves") or [])
        if isinstance(m.get("carcasum_ms"), (int, float)) and m["carcasum_ms"] > 0
    ]
    median_ms = st.median(pooled_ms) if pooled_ms else None
    g_timing_dev_pct = (100.0 * abs(median_ms - 5000.0) / 5000.0
                        if median_ms is not None else None)
    g_timing_pass = (g_timing_dev_pct is not None
                     and g_timing_dev_pct <= G_TIMING_TOLERANCE_PCT)

    void_rate = (sum(voids.values()) / len(records)) if records else None
    real_rate = (sum(real_divergences.values()) / len(records)) if records else None

    deck_seeds = {int(r["deck_seed"]) for r in records if "deck_seed" in r}

    return {
        "n_records": len(records), "n_scored": n, "voids": voids,
        "real_divergences": real_divergences,
        "void_rate": void_rate, "real_divergence_rate": real_rate,
        "wins": wins, "draws": draws, "losses": n - wins - draws,
        "win_rate": (wins + 0.5 * draws) / n if n else None,
        "elo_from_win_rate": _wr_to_elo((wins + 0.5 * draws) / n) if n else None,
        "n_paired_decks": len(paired),
        "paired_margin_mean": mean_p,
        "paired_margin_sem": sem_p,
        "paired_margin_by_deck": paired_by_deck,
        "deck_seeds": deck_seeds,
        "pooled_opp_turns": len(pooled_ms),
        "median_opp_ms_per_turn": median_ms,
        "g_timing_deviation_pct": g_timing_dev_pct,
        "g_timing_pass": g_timing_pass,
    }


def gate_d_void(stats: dict) -> bool:
    vr = stats.get("void_rate") or 0.0
    rr = stats.get("real_divergence_rate") or 0.0
    return vr <= VOID_RATE_BAR and rr <= VOID_RATE_BAR


def gate_g_n(stats: dict, n_decks_target: int) -> bool:
    return stats["n_paired_decks"] >= math.floor(G_N_FLOOR_FRACTION * n_decks_target)


# --------------------------------------------------------------------------- #
# structural gates (READ_RULE.md §3) — every one fail-closed, ABSENT is FAIL   #
# --------------------------------------------------------------------------- #
def gate_g_binary(off_records: list[dict], on_records: list[dict]) -> tuple[bool, str]:
    """Cross-ARM consistency, not equality to a hardcoded constant — the two arms
    must have run the SAME driver binary (a different binary between arms would
    confound the arbiter contrast with a build difference)."""
    mo, mn = _first_manifest(off_records), _first_manifest(on_records)
    if mo is None or mn is None:
        return False, "manifest absent on at least one arm"
    sha_off = mo.get("carcasum_binary_sha256")
    sha_on = mn.get("carcasum_binary_sha256")
    if not sha_off or not sha_on:
        return False, "carcasum_binary_sha256 absent on at least one arm"
    if sha_off != sha_on:
        return False, f"binary sha differs between arms: OFF={sha_off} ON={sha_on}"
    return True, "ok"


def gate_g_rules(off_records: list[dict], on_records: list[dict]) -> tuple[bool, str]:
    for label, records in (("OFF", off_records), ("ON", on_records)):
        m = _first_manifest(records)
        if m is None:
            return False, f"manifest absent on ARM-{label}"
        rm = m.get("rules_manifest")
        if not isinstance(rm, dict):
            return False, f"ARM-{label}: rules_manifest absent"
        if rm.get("name") != "fixed_v1":
            return False, f"ARM-{label}: rules_manifest.name={rm.get('name')!r} != 'fixed_v1'"
        if rm.get("r9_env_ok") is not True:
            return False, f"ARM-{label}: r9_env_ok={rm.get('r9_env_ok')!r} != True"
    return True, "ok"


def gate_g_budget(off_records: list[dict], on_records: list[dict]) -> tuple[bool, str]:
    for label, records in (("OFF", off_records), ("ON", on_records)):
        m = _first_manifest(records)
        if m is None:
            return False, f"manifest absent on ARM-{label}"
        opp = m.get("opponent")
        if not isinstance(opp, dict):
            return False, f"ARM-{label}: opponent absent"
        for k, want in EXPECTED_OPPONENT.items():
            got = opp.get(k)
            if got != want:
                return False, f"ARM-{label}: opponent.{k}={got!r} != {want!r}"
    return True, "ok"


def gate_g_champ_off(off_records: list[dict]) -> tuple[bool, str]:
    m = _first_manifest(off_records)
    if m is None:
        return False, "manifest absent"
    cm = m.get("champion_manifest")
    if not isinstance(cm, dict):
        return False, "champion_manifest absent"
    lh = (cm.get("leaf_hashes") or {}).get("harness_leaf_hash")
    if lh != PROD_LEAF_HASH:
        return False, f"leaf hash mismatch: got {lh!r}"
    if cm.get("cand_tiearb"):
        return False, "cand_tiearb PRESENT on ARM-OFF (arbiter leaked ON)"
    return True, "ok"


def gate_g_champ_on(on_records: list[dict]) -> tuple[bool, str]:
    m = _first_manifest(on_records)
    if m is None:
        return False, "manifest absent"
    cm = m.get("champion_manifest")
    if not isinstance(cm, dict):
        return False, "champion_manifest absent"
    lh = (cm.get("leaf_hashes") or {}).get("harness_leaf_hash")
    if lh != PROD_LEAF_HASH:
        return False, f"leaf hash mismatch: got {lh!r}"
    ta = cm.get("cand_tiearb")
    if not isinstance(ta, dict):
        return False, "cand_tiearb ABSENT on ARM-ON (arbiter leaked OFF)"
    if ta != ARMED_TIEARB_SPEC:
        return False, f"cand_tiearb != the pinned deployed spec: got {ta!r}"
    return True, "ok"


def gate_g_singlevar(off_records: list[dict], on_records: list[dict]) -> tuple[bool, str]:
    """The `track_d2_prep` lesson, ported: the two arms' manifests must agree on
    EVERYTHING except the arbiter block. Checked here, not merely asserted in prose
    (`results.csv d2_rung_compression_U_UNREADABLE...b141e9` is what a launcher-shape
    diff without a code-level check costs)."""
    mo, mn = _first_manifest(off_records), _first_manifest(on_records)
    if mo is None or mn is None:
        return False, "manifest absent on at least one arm"
    diffs = []
    if mo.get("our_git_rev") != mn.get("our_git_rev"):
        diffs.append(f"our_git_rev: {mo.get('our_git_rev')!r} vs {mn.get('our_git_rev')!r}")
    if mo.get("rules_profile") != mn.get("rules_profile"):
        diffs.append("rules_profile differs")
    if mo.get("opponent") != mn.get("opponent"):
        diffs.append("opponent config differs")
    if mo.get("sims_override") != mn.get("sims_override"):
        diffs.append("sims_override differs")
    if mo.get("k_dets_override") != mn.get("k_dets_override"):
        diffs.append("k_dets_override differs")
    ex_o, ex_n = mo.get("execution") or {}, mn.get("execution") or {}
    if ex_o.get("backend") != "rust" or ex_n.get("backend") != "rust":
        diffs.append(f"execution.backend not both 'rust': OFF={ex_o.get('backend')!r} "
                     f"ON={ex_n.get('backend')!r}")
    if diffs:
        return False, "; ".join(diffs)
    return True, "ok"


def gate_g_shared_decks(off_records: list[dict], on_records: list[dict]) -> tuple[bool, str]:
    bad = []
    for label, records in (("OFF", off_records), ("ON", on_records)):
        seeds = {int(r["deck_seed"]) for r in records if "deck_seed" in r}
        out_of_range = sorted(s for s in seeds
                              if not (SHARED_DECK_SEED_LO <= s <= SHARED_DECK_SEED_HI))
        if out_of_range:
            bad.append(f"ARM-{label}: {len(out_of_range)} deck_seed(s) outside range, "
                       f"e.g. {out_of_range[:5]}")
    if bad:
        return False, "; ".join(bad)
    return True, "ok"


def gate_g_timing(off_stats: dict, on_stats: dict) -> tuple[bool, str]:
    bad = [label for label, s in (("OFF", off_stats), ("ON", on_stats))
           if not s.get("g_timing_pass")]
    if bad:
        return False, f"outside +/-{G_TIMING_TOLERANCE_PCT:.0f}% on arm(s): {bad}"
    return True, "ok"


def structural_gates(off_records: list[dict], on_records: list[dict],
                     off_stats: dict, on_stats: dict) -> dict[str, tuple[bool, str]]:
    return {
        "G-BINARY": gate_g_binary(off_records, on_records),
        "G-RULES": gate_g_rules(off_records, on_records),
        "G-BUDGET": gate_g_budget(off_records, on_records),
        "G-CHAMP-OFF": gate_g_champ_off(off_records),
        "G-CHAMP-ON": gate_g_champ_on(on_records),
        "G-SINGLEVAR": gate_g_singlevar(off_records, on_records),
        "G-N": (gate_g_n(off_stats, 200) and gate_g_n(on_stats, 200),
               f"OFF n_paired={off_stats['n_paired_decks']} ON n_paired={on_stats['n_paired_decks']}"),
        "G-SHARED-DECKS": gate_g_shared_decks(off_records, on_records),
        "G-TIMING": gate_g_timing(off_stats, on_stats),
    }


# --------------------------------------------------------------------------- #
# THE PRIMARY STATISTIC: D = M_ON - M_OFF, deck-paired across ARMS             #
# (READ_RULE.md §1) — over the INTERSECTION of decks common to both arms.     #
# --------------------------------------------------------------------------- #
def cross_arm_diff(off_stats: dict, on_stats: dict) -> dict:
    off_by_deck = off_stats["paired_margin_by_deck"]
    on_by_deck = on_stats["paired_margin_by_deck"]
    common = sorted(set(off_by_deck) & set(on_by_deck))
    diffs = [on_by_deck[d] - off_by_deck[d] for d in common]
    n = len(diffs)
    if n == 0:
        return {"D": None, "SE_D": None, "z_D": None, "n_common_decks": 0,
                "D_by_deck": {}}
    D = sum(diffs) / n
    if n > 1:
        var_D = sum((x - D) ** 2 for x in diffs) / (n - 1)
        SE_D = (var_D / n) ** 0.5
    else:
        SE_D = None
    z_D = D / SE_D if SE_D else None
    return {"D": D, "SE_D": SE_D, "z_D": z_D, "n_common_decks": n,
            "D_by_deck": dict(zip(common, diffs))}


# --------------------------------------------------------------------------- #
# READ_RULE.md §4 branch decision                                             #
# --------------------------------------------------------------------------- #
def decide_branch(D: float | None, z_D: float | None) -> dict:
    """First-match-wins, D-void already checked by the caller before this is
    reached. Sign convention: D = M_ON - M_OFF > 0 means the arbiter helped.

    ⚠️ N is a flagged ADDITION beyond the task brief's literal T/W/U enumeration
    (READ_RULE.md §4 preamble) — a credible negative transfer is a real finding,
    not the same thing as "no strength number could be produced."."""
    if D is None or z_D is None:
        return {"branch": "U-UNREADABLE",
                "reason": "D/z_D undefined (no common decks, or SE_D undefined at n<2)."}

    if D >= EQUIVALENCE_BAR_PTS and z_D >= Z_BAR:
        return {"branch": "T-TRANSFER",
                "reason": ("the arbiter's internal gain transfers to this external "
                           "opponent.")}
    if D <= -EQUIVALENCE_BAR_PTS and z_D <= -Z_BAR:
        return {"branch": "N-NEGATIVE-TRANSFER",
                "reason": ("the arbiter measurably HURTS against this external "
                           "opponent — a real, reportable finding (READ_RULE.md §4 "
                           "preamble), not an unreadable cell.")}
    if abs(D) <= EQUIVALENCE_BAR_PTS and abs(z_D) < Z_BAR:
        return {"branch": "W-WASHOUT",
                "reason": ("the arbiter's internal gain does not measurably "
                           "transfer — the win may be champion-mirror-specific.")}
    if abs(z_D) < Z_BAR and abs(D) > EQUIVALENCE_BAR_PTS:
        return {"branch": "TOPUP",
                "reason": ("neither the equivalence region nor a confident read — "
                           "consume the reserved 50-deck top-up ONCE and re-read.")}
    # By §2's own construction (SE_D <= ~1.4 at n>=200 under either sigma_D model),
    # |z_D| >= 2.0 should always imply |D| > 2.0 too, so this branch should be
    # unreachable in practice — kept as a fail-closed catch-all, not silently folded
    # into any of the above (a real disagreement here is itself worth surfacing).
    return {"branch": "U-UNREADABLE",
            "reason": ("no branch condition matched cleanly (D and z_D disagree with "
                       "§2's own consistency argument) — review by hand.")}


# --------------------------------------------------------------------------- #
# self-test                                                                    #
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    # ---- D / SE_D / z_D, hand-computed ----------------------------------------
    off_stats = {"paired_margin_by_deck": {1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0, 5: 10.0}}
    on_stats = {"paired_margin_by_deck": {1: 6.0, 2: 8.0, 3: 10.0, 4: 12.0, 5: 14.0}}
    d = cross_arm_diff(off_stats, on_stats)
    assert d["n_common_decks"] == 5, d
    assert abs(d["D"] - 4.0) < 1e-9, d          # every deck's diff is exactly +4.0
    assert d["SE_D"] == 0.0 or d["SE_D"] is not None
    # zero-variance case: SE_D computed as 0.0, z_D would divide by zero -> guarded
    if d["SE_D"] == 0.0:
        assert d["z_D"] is None, d
    print("[selftest] D/SE_D hand-computed OK: D=%.4f n=%d" % (d["D"], d["n_common_decks"]))

    # a case with real dispersion, hand-verifiable
    off2 = {"paired_margin_by_deck": {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}}
    on2 = {"paired_margin_by_deck": {1: 2.0, 2: 4.0, 3: 6.0, 4: 8.0}}
    d2 = cross_arm_diff(off2, on2)
    # diffs = [2,4,6,8], mean=5, sample var = ((2-5)^2+(4-5)^2+(6-5)^2+(8-5)^2)/3
    #        = (9+1+1+9)/3 = 20/3; SE = sqrt((20/3)/4) = sqrt(5/3) = 1.290994...
    assert abs(d2["D"] - 5.0) < 1e-9, d2
    assert abs(d2["SE_D"] - (5.0 / 3.0) ** 0.5) < 1e-9, d2
    assert abs(d2["z_D"] - (5.0 / ((5.0 / 3.0) ** 0.5))) < 1e-9, d2
    print("[selftest] D/SE_D/z_D dispersed case OK: D=%.4f SE_D=%.4f z_D=%.4f"
          % (d2["D"], d2["SE_D"], d2["z_D"]))

    # only decks common to BOTH arms count
    off3 = {"paired_margin_by_deck": {1: 1.0, 2: 2.0, 99: 100.0}}
    on3 = {"paired_margin_by_deck": {1: 3.0, 2: 5.0}}
    d3 = cross_arm_diff(off3, on3)
    assert d3["n_common_decks"] == 2, d3
    assert set(d3["D_by_deck"]) == {1, 2}, d3
    print("[selftest] cross_arm_diff intersection-only OK")

    # n=0 / n=1 edge cases
    assert cross_arm_diff({"paired_margin_by_deck": {}}, {"paired_margin_by_deck": {}})["D"] is None
    d_one = cross_arm_diff({"paired_margin_by_deck": {1: 1.0}}, {"paired_margin_by_deck": {1: 3.0}})
    assert d_one["n_common_decks"] == 1 and d_one["SE_D"] is None and d_one["z_D"] is None, d_one
    print("[selftest] cross_arm_diff n=0/n=1 edge cases OK")

    # ---- branch decision, one case per branch ----------------------------------
    t = decide_branch(D=3.0, z_D=2.5)
    assert t["branch"] == "T-TRANSFER", t
    n_ = decide_branch(D=-3.0, z_D=-2.5)
    assert n_["branch"] == "N-NEGATIVE-TRANSFER", n_
    w = decide_branch(D=0.5, z_D=0.6)
    assert w["branch"] == "W-WASHOUT", w
    up = decide_branch(D=3.0, z_D=1.5)
    assert up["branch"] == "TOPUP", up
    u = decide_branch(D=None, z_D=None)
    assert u["branch"] == "U-UNREADABLE", u
    print("[selftest] branch decision T/N/W/TOPUP/U all OK")

    # ---- structural gates, real record shapes (dict, as load() produces) -------
    good_opp = dict(EXPECTED_OPPONENT)
    good_off_manifest = {
        "carcasum_binary_sha256": "deadbeef" * 4,
        "rules_manifest": {"name": "fixed_v1", "r9_env_ok": True},
        "champion_manifest": {"leaf_hashes": {"harness_leaf_hash": PROD_LEAF_HASH}},
        "opponent": good_opp, "our_git_rev": "abc123", "rules_profile": "fixed_v1",
        "sims_override": None, "k_dets_override": None,
        "execution": {"backend": "rust"},
    }
    good_on_manifest = {
        **good_off_manifest,
        "champion_manifest": {"leaf_hashes": {"harness_leaf_hash": PROD_LEAF_HASH},
                              "cand_tiearb": dict(ARMED_TIEARB_SPEC)},
    }
    off_recs = [{"deck_seed": 147000000000, "manifest": good_off_manifest}]
    on_recs = [{"deck_seed": 147000000000, "manifest": good_on_manifest}]

    assert gate_g_binary(off_recs, on_recs)[0] is True
    bad_bin = [{"deck_seed": 1, "manifest": {**good_on_manifest, "carcasum_binary_sha256": "x" * 32}}]
    assert gate_g_binary(off_recs, bad_bin)[0] is False
    print("[selftest] G-BINARY pass/cross-arm-mismatch OK")

    assert gate_g_rules(off_recs, on_recs)[0] is True
    bad_rules = [{"deck_seed": 1, "manifest": {**good_off_manifest,
                                               "rules_manifest": {"name": "walled", "r9_env_ok": True}}}]
    assert gate_g_rules(bad_rules, on_recs)[0] is False
    print("[selftest] G-RULES pass/fail OK")

    assert gate_g_budget(off_recs, on_recs)[0] is True
    bad_budget = [{"deck_seed": 1, "manifest": {**good_off_manifest,
                                                "opponent": {**good_opp, "cp": 1.0}}}]
    assert gate_g_budget(bad_budget, on_recs)[0] is False
    print("[selftest] G-BUDGET pass/fail OK")

    assert gate_g_champ_off(off_recs)[0] is True
    off_with_tiearb = [{"deck_seed": 1, "manifest": {**good_off_manifest,
                                                     "champion_manifest": {
                                                         "leaf_hashes": {"harness_leaf_hash": PROD_LEAF_HASH},
                                                         "cand_tiearb": dict(ARMED_TIEARB_SPEC)}}}]
    assert gate_g_champ_off(off_with_tiearb)[0] is False
    print("[selftest] G-CHAMP-OFF pass/leaked-arbiter-fail OK")

    assert gate_g_champ_on(on_recs)[0] is True
    on_missing_tiearb = [{"deck_seed": 1, "manifest": good_off_manifest}]  # no cand_tiearb
    assert gate_g_champ_on(on_missing_tiearb)[0] is False
    on_wrong_b = [{"deck_seed": 1, "manifest": {**good_on_manifest,
                                                "champion_manifest": {
                                                    "leaf_hashes": {"harness_leaf_hash": PROD_LEAF_HASH},
                                                    "cand_tiearb": {**ARMED_TIEARB_SPEC, "B": 16}}}}]
    assert gate_g_champ_on(on_wrong_b)[0] is False
    print("[selftest] G-CHAMP-ON pass/absent-arbiter-fail/wrong-B-fail OK")

    assert gate_g_singlevar(off_recs, on_recs)[0] is True
    mixed_rev = [{"deck_seed": 1, "manifest": {**good_on_manifest, "our_git_rev": "different"}}]
    assert gate_g_singlevar(off_recs, mixed_rev)[0] is False
    print("[selftest] G-SINGLEVAR pass/mixed-revision-fail OK")

    assert gate_g_shared_decks(off_recs, on_recs)[0] is True
    out_of_range = [{"deck_seed": 999, "manifest": good_on_manifest}]
    assert gate_g_shared_decks(off_recs, out_of_range)[0] is False
    print("[selftest] G-SHARED-DECKS pass/out-of-range-fail OK")

    good_timing = {"g_timing_pass": True}
    bad_timing = {"g_timing_pass": False}
    assert gate_g_timing(good_timing, good_timing)[0] is True
    assert gate_g_timing(good_timing, bad_timing)[0] is False
    print("[selftest] G-TIMING pass/fail OK")

    # ---- D-void gate (per arm, 1% bar) ------------------------------------------
    assert gate_d_void({"void_rate": 0.0, "real_divergence_rate": 0.0}) is True
    assert gate_d_void({"void_rate": 0.02, "real_divergence_rate": 0.0}) is False
    assert gate_d_void({"void_rate": 0.0, "real_divergence_rate": 0.02}) is False
    print("[selftest] D-void gate pass/fail OK")

    print("\n[selftest] ALL OK")
    return 0


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm-off", default=None, help="ARM-OFF's games.jsonl")
    ap.add_argument("--arm-on", default=None, help="ARM-ON's games.jsonl")
    ap.add_argument("--n-decks-target", type=int, default=200)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.arm_off or not args.arm_on:
        print("FATAL: --arm-off and --arm-on are both required unless --selftest",
              file=sys.stderr)
        return 2

    off_records = load(args.arm_off)
    on_records = load(args.arm_on)
    off_stats = per_arm_stats(off_records)
    on_stats = per_arm_stats(on_records)

    report: dict = {"arms": {"arm_off": off_stats, "arm_on": on_stats}}

    # --- D (void-contaminated), checked FIRST, before any structural gate --------
    d_void_off = gate_d_void(off_stats)
    d_void_on = gate_d_void(on_stats)
    g_n_off = gate_g_n(off_stats, args.n_decks_target)
    g_n_on = gate_g_n(on_stats, args.n_decks_target)
    if not (d_void_off and d_void_on):
        report["branch"] = "U-UNREADABLE"
        report["reason"] = (f"D (void-contaminated) fired: void/REAL-divergence rate "
                             f"exceeds {VOID_RATE_BAR:.0%} on at least one arm "
                             f"(OFF pass={d_void_off}, ON pass={d_void_on}).")
        _emit(report, args.json)
        return 0
    if not (g_n_off and g_n_on):
        report["branch"] = "U-UNREADABLE"
        report["reason"] = (f"D fired: fewer than 2 of the 4 new rungs — an arm "
                             f"failed to reach the G-N floor "
                             f"(OFF n_paired={off_stats['n_paired_decks']}, "
                             f"ON n_paired={on_stats['n_paired_decks']}, "
                             f"floor={math.floor(G_N_FLOOR_FRACTION * args.n_decks_target)}).")
        _emit(report, args.json)
        return 0

    # --- structural gates --------------------------------------------------------
    gates = structural_gates(off_records, on_records, off_stats, on_stats)
    report["structural_gates"] = gates
    failed = [gid for gid, (passed, _r) in gates.items() if not passed]
    if failed:
        report["branch"] = "U-UNREADABLE"
        report["reason"] = f"D fired: structural gate(s) failed: {failed}"
        _emit(report, args.json)
        return 0

    # --- the primary statistic ----------------------------------------------------
    diff = cross_arm_diff(off_stats, on_stats)
    report["primary"] = diff
    decision = decide_branch(diff["D"], diff["z_D"])
    report["branch"] = decision["branch"]
    report["reason"] = decision["reason"]

    _emit(report, args.json)
    return 0


def _emit(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=1, default=str))
        return
    for arm_name, stats in report.get("arms", {}).items():
        print(f"[{arm_name}] n_scored={stats['n_scored']} paired_margin="
              f"{stats['paired_margin_mean']} +/- {stats['paired_margin_sem']} "
              f"wr={stats['win_rate']} elo={stats['elo_from_win_rate']} "
              f"median_opp_ms={stats['median_opp_ms_per_turn']} "
              f"g_timing_pass={stats.get('g_timing_pass')}")
    if "structural_gates" in report:
        for gid, (passed, reason) in report["structural_gates"].items():
            print(f"  {gid}: {'PASS' if passed else 'FAIL'} ({reason})")
    if "primary" in report:
        p = report["primary"]
        print(f"PRIMARY: D={p['D']} SE_D={p['SE_D']} z_D={p['z_D']} "
              f"n_common_decks={p['n_common_decks']}")
    print(f"\nBRANCH: {report.get('branch')}")
    print(f"REASON: {report.get('reason')}")


if __name__ == "__main__":
    raise SystemExit(main())
