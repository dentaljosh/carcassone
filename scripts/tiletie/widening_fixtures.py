#!/usr/bin/env python3
"""Synthetic, engine-free FIXTURES for the tie-arbiter widening instrument.

Used by two callers that must agree byte-for-byte on the artifact SHAPES:

  * `acceptance_widening.py --mode 4a` — DESIGN §9 step 4a's **static schema
    audit of W3/W5/W6 outputs against committed fixtures**, which is how the
    `READOUT::widening.*`, `GATE_DISJOINT`, `GATE_DRAW`, `POSITIONS_PLAN` and
    `ARMS` spellings get audited BEFORE any real corpus exists.
  * `tests/test_tiearb_widening.py` — the unit suite.

Everything here is fabricated from a seeded RNG: **no replay, no playouts, no
engine, no leaf**. The values are meaningless by construction — they exist only
so the emitters have something structurally valid to chew on. The one thing
that is NOT fabricated is the `subset_j4` draw: it is produced by the real
`build_positions._seeded_cap`, so `G-DRAW` is exercised against the actual
identity it will assert on the real corpus.

The fixture strata use the REAL world counts (`M = 128` on S1, `M = 32` on S2)
so the audited ladder spellings are the real ones (`E64`/`E16`, `B1…B64`) and
not a scaled-down stand-in that would audit the wrong keys.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_positions as BP                                       # noqa: E402

JUDGES = ("tier1-greedy", "clair-puct")
PROFILE = "walled"
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"
WORLD_SEED_SALT = "tiletie-v1"


def _vals(rng, m):
    return [round(rng.gauss(0.0, 1.0), 6) for _ in range(m)]


def make_corpus(out_dir, *, n_positions=12, m=128, roots=4, seed=7,
                stratum="selfplay", rid_prefix="fx", capped_every=2,
                champ_outside_every=3, band_lo=135000000000):
    """Write a structurally complete positions dir: `POSITIONS_PLAN.json`,
    `ARMS.json`, `DROPPED_ALL_TRANSPOSITION.json` and a `positions_*_leg1.jsonl`
    board census. Returns the ARMS index."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    arms_index, leg_lines, dropped_rows = {}, [], []
    for i in range(n_positions):
        root = f"{rid_prefix}root{band_lo + (i % roots)}"
        rid = f"{rid_prefix}:{root}:p{i:03d}"
        # ---- the three rid KINDS W8's fixture set must contain -------------- #
        #   i == 0  the CHAMPION-APPEND rid (champ pick outside the tie set)
        #   i == 1  a CAPPED rid (`capped_at_4` true: > 4 deduped arms)
        #   i == 2  an ALL_TRANSPOSITION rid (n_distinct_afterstates == 1)
        # every other rid is ordinary. The kinds are placed EXPLICITLY, not left
        # to a modulus, so the fixture cannot silently lose one.
        if i == 1:
            n_full = 6                             # > 4 ⇒ the J=4 draw BINDS
        elif i == 2:
            n_full = 2
        else:
            n_full = 3 + (i % 3)
        arms_full = [100 + i * 10 + k for k in range(n_full)]
        kept, capped, _ = BP._seeded_cap(rid, arms_full[1:], BP.DEPLOYED_CAP_J)
        subset_j4 = [arms_full[0]] + list(kept)
        arms = list(arms_full)
        champ_outside = (i == 0) or ((i % champ_outside_every) == 0 and i > 2)
        if champ_outside:                          # the intended APPEND
            arms = arms + [900 + i]
            champ_action, champ_index = arms[-1], len(arms) - 1
        else:
            champ_index = 1 % len(arms)
            champ_action = arms[champ_index]
        all_transposition = (i == 2)
        arms_index[rid] = {
            "rid": rid, "root_id": root, "stratum": stratum,
            "rules_profile": PROFILE, "ply": 10 + i,
            "phase_bucket": "mid", "tercile": "mid",
            "arms": arms, "arms_full": arms_full,
            "subset_j4": subset_j4,
            "subset_j4_id": BP._subset_id(rid, subset_j4),
            "capped_at_4": bool(capped) or (i % capped_every == 0),
            "capped": False,
            "cap_seed": BP._stable_seed(BP.CAP_SEED_TAG, rid, BP.CAP_SEED_DATE),
            "champ_action": champ_action,
            "champ_arm_action": champ_action,
            "champ_arm_index": champ_index,
            "champ_outside_tieset": champ_outside,
            "all_transposition": all_transposition,
            "n_distinct_afterstates": 1 if all_transposition else n_full,
            "tie_size_exact": n_full,
        }
        if all_transposition:
            # in the REAL corpus such a ply is an analytic zero and is dropped
            # before ARMS.json is written; the fixture carries it in BOTH places
            # so both spellings get audited.
            dropped_rows.append({"rid": rid, "root_id": root, "stratum": stratum,
                                 "n_distinct_afterstates": 1,
                                 "all_transposition": True,
                                 "action_played_outside_tieset": False})
        leg_lines.append(json.dumps(
            {"rid": rid, "root_id": root, "leg": 1,
             "checksum": f"BOARD::{rid_prefix}::{i:04d}"}))

    (out / "ARMS.json").write_text(json.dumps(arms_index, indent=2, sort_keys=True))
    (out / "DROPPED_ALL_TRANSPOSITION.json").write_text(
        json.dumps({"rows": dropped_rows}, indent=2, sort_keys=True))
    plan = {
        "n_positions": len(arms_index),
        # `cap_j` is null on an uncapped build and `cap_j_label` is its human
        # spelling — TOGETHER they are the witness that makes the null
        # legitimate (READ_RULE §1.2 row 4). `build_positions` emits both.
        "uncapped": True, "cap_j": None,
        "cap_j_label": BP.cap_j_label(None),
        "deployed_cap_j": BP.DEPLOYED_CAP_J,
        "n_positions_capped_at_4": sum(1 for v in arms_index.values()
                                       if v["capped_at_4"]),
        "m_worlds_planned": m,
        "afterstate_dedupe": {"applied": True,
                              "n_dropped_all_transposition": 0},
        "exclude_rids": {"n_requested": 0, "n_removed_from_supply": 0,
                         "n_supply_after_exclusion": len(arms_index)},
        "counts_by_stratum": {stratum: len(arms_index)},
        "sample_seed": 20260819,
    }
    (out / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=2,
                                                        sort_keys=True))
    (out / f"positions_{PROFILE}_leg1.jsonl").write_text(
        "\n".join(leg_lines) + "\n")
    return arms_index


def make_records(share_root, arms_index, *, m=128, seed=11, stratum_dir="s1"):
    """Write `SHARE/<stratum>/<judge>/walled/leg<N>/records/<rid>.json` — ONE
    JSON OBJECT PER RID (there is no `*.jsonl` leg file), plus each leg's
    `manifest.json` in the shape `tier1_rust_leg` emits."""
    share = Path(share_root)
    rng = random.Random(seed)
    for judge in JUDGES:
        legs_seen = set()
        for rid, meta in sorted(arms_index.items()):
            n_arms = len(meta["arms"])
            world_seeds = [int(hashlib.sha256(f"{rid}|{j}|{WORLD_SEED_SALT}"
                                              .encode()).hexdigest()[:8], 16)
                           for j in range(m)]
            playout_seeds = [w ^ 0x5A5A for w in world_seeds]
            va = _vals(rng, m)
            for r in range(1, n_arms):
                legs_seen.add(r)
                d = (share / stratum_dir / judge / PROFILE / f"leg{r}" / "records")
                d.mkdir(parents=True, exist_ok=True)
                rec = {
                    "rid": rid, "leg": r, "ok": True, "m": m,
                    "values_a": va, "values_b": _vals(rng, m),
                    "world_seeds": world_seeds, "playout_seeds": playout_seeds,
                    "crn_verified": True, "checksum_ok": True,
                    "pick_a": meta["arms"][0], "pick_b": meta["arms"][r],
                    "distinct_afterstates": meta["n_distinct_afterstates"],
                    "world_seed_salt": WORLD_SEED_SALT,
                    "rules_profile": PROFILE,
                }
                # the per-world CRN witness differs by judge, BY DESIGN
                if judge == "tier1-greedy":
                    rec["world_deck_hash"] = [f"w{w:x}" for w in world_seeds]
                else:
                    rec["afterstate_deck_hash_a"] = [f"a{w:x}" for w in world_seeds]
                (d / f"{rid.replace('/', '_')}.json").write_text(
                    json.dumps(rec, sort_keys=True))
        for r in sorted(legs_seen):
            leg_dir = share / stratum_dir / judge / PROFILE / f"leg{r}"
            man = {
                "judge": judge, "profile": PROFILE, "leg": r,
                "n_ok": len(arms_index), "n_crn_verified": len(arms_index),
            }
            if judge == "tier1-greedy":
                # resolved_config / preflight.seeds exist ONLY on the ARB leg
                man["resolved_config"] = {
                    "world_seed_salt": WORLD_SEED_SALT, "m": m,
                    "legal_mask_cache": True, "backend": "rust",
                }
                man["preflight"] = {"seeds": {
                    "ok": True,
                    "prefix_stable_at": [b for b in (1, 2, 4, 8, 16, 32, 64, 128)
                                         if b <= m],
                    "derivation": "sha256(tag|rid|j|salt)",
                    "probe_rid": "PROBE",
                    "probe_world_seeds_head": [1, 2, 3, 4],
                    "probe_playout_seeds_head": [5, 6, 7, 8],
                    "salt": WORLD_SEED_SALT, "m": m,
                }}
            (leg_dir / "manifest.json").write_text(json.dumps(man, indent=2,
                                                              sort_keys=True))
    return share


def copy_back_legs(share_root, run_dir, stratum_dir="s1"):
    """W6's copy-back: `RUN/legs/{s1,s2}/<judge>/walled/leg<N>/manifest.json`.
    Only the `tier1-greedy` legs are addressed by any gate, but both are copied
    (DESIGN §8 builder delta 4)."""
    share, run = Path(share_root), Path(run_dir)
    for man in sorted((share / stratum_dir).glob("*/*/leg*/manifest.json")):
        rel = man.relative_to(share / stratum_dir)
        dst = run / "legs" / stratum_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(man.read_text())


def make_run_manifest(path, *, stratum="S1", m=128):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "stratum": stratum,
        "world_seed_salt": WORLD_SEED_SALT,
        "m_worlds": m, "b_ceiling_from_m": m // 2,
        "arb_backend": "rust", "arb_legal_mask_cache": True,
        "resolved_backend_by_leg": {f"tier1-greedy/{PROFILE}": "rust",
                                    f"clair-puct/{PROFILE}": "python"},
        "git_rev": "0123456",
        "preflight": {"checks": {"leaf_hash": {
            "ok": True, "harness_leaf_hash": LEAF_HASH_OF_RECORD,
            "expected": LEAF_HASH_OF_RECORD}}},
    }, indent=2, sort_keys=True))


def make_smoke_manifest(path, *, judge, stratum="S1", m=128, c=0.18):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "judge": judge, "smoke_judge": judge, "profile": PROFILE,
        "m_worlds": m, "arb_backend": "rust", "arb_legal_mask_cache": True,
        "c_worker_secs_per_playout": c,
        # the wall x W figure the emitter's own banner says NOT to cost from —
        # present so a reader can SEE it was not used. A failed smoke (c is
        # None) still emits it, which is exactly the trap REVIEW_R1 §5 names.
        "worker_secs_per_playout": (c * 1.9) if c is not None else 0.42,
        "crn_cross_leg_identical": True,
        "stratum": stratum,
    }, indent=2, sort_keys=True))


def make_champ_games_verify(path, *, lo=135000000000, hi=135000000849, n=850):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "band_ok": True, "seed_band": [lo, hi], "n_games_realized": n,
        "n_out_of_band": 0, "n_duplicate_seeds": 0, "n_distinct_seeds": n,
        "sha256_of_sorted_seeds": hashlib.sha256(b"fixture").hexdigest(),
        "count_ok": True, "n_games_expected": n, "n_games_min_required": n,
        "shortfall_vs_expected": 0, "path": "fixture",
        "seed_min_observed": lo, "seed_max_observed": hi,
    }, indent=2, sort_keys=True))


def make_gen_smoke(path, *, worker_secs_per_game=440.0, n_games=10):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "worker_secs_per_game": worker_secs_per_game, "n_games": n_games,
        "note": "separate timed generation smoke (DESIGN §7.2)",
    }, indent=2, sort_keys=True))


def make_bitexact(path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "gate": "G-BITEXACT", "pass": True, "n_playouts_compared": 15360,
        "n_value_bit_identical": 15360, "n_value_mismatch": 0,
        "legal_mask_cache": True,
        "git_rev": "0123456789abcdef0123456789abcdef01234567",
        "out_path": str(p),
    }, indent=2, sort_keys=True))


def make_stage1b_ladder(path):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "source": "FIXTURE — not the banked Stage-1b ladder",
        "e_worlds": 16,
        "rungs": {str(b): {"arb": 0.0, "se": 1.0} for b in (1, 2, 4, 8, 16)},
    }, indent=2, sort_keys=True))


def make_d_draw(path, *, n_checked=100, n_agree=97, n_unreconstructible=1):
    """W9's `RUN/D_DRAW.json` shape. Reports the MAGNITUDE of rider `I7`'s
    unverified dedupe-partition conditional; adjudicates NOTHING."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "n_checked": n_checked, "n_agree": n_agree,
        "agreement_rate": (n_agree / n_checked) if n_checked else None,
        "n_unreconstructible": n_unreconstructible,
        "git_rev": "0123456789abcdef0123456789abcdef01234567",
        "note": "D-DRAW rider — adjudicates nothing"},
        indent=2, sort_keys=True))


def build_full_fixture(root, *, m_s1=128, m_s2=32, n_s1=12, n_s2=12):
    """A complete, structurally valid RUN/ + SHARE/ pair. Returns
    `{"run": Path, "share": Path, "arms": {...}}`."""
    root = Path(root)
    run, share = root / "shared_run", root / "share"
    corpus = run / "corpus"

    arms_s1 = make_corpus(corpus / "positions_s1", n_positions=n_s1, m=m_s1,
                          seed=7, rid_prefix="s1", band_lo=135000000000)
    arms_s2 = make_corpus(corpus / "positions_s2", n_positions=n_s2, m=m_s2,
                          seed=23, rid_prefix="s2", band_lo=135000000350)
    make_records(share, arms_s1, m=m_s1, seed=11, stratum_dir="s1")
    make_records(share, arms_s2, m=m_s2, seed=13, stratum_dir="s2")
    copy_back_legs(share, run, "s1")
    copy_back_legs(share, run, "s2")

    make_run_manifest(run / "RUN_MANIFEST_S1.json", stratum="S1", m=m_s1)
    make_run_manifest(run / "RUN_MANIFEST_S2.json", stratum="S2", m=m_s2)
    for st, mm in (("S1", m_s1), ("S2", m_s2)):
        for j in JUDGES:
            make_smoke_manifest(run / f"SMOKE_MANIFEST_{st}_{j}.json",
                                judge=j, stratum=st, m=mm,
                                c=0.18 if j == "tier1-greedy" else 2.30)
    make_champ_games_verify(corpus / "CHAMP_GAMES_VERIFY.json")
    make_gen_smoke(corpus / "GEN_SMOKE.json")
    make_bitexact(run / "GATE_BITEXACT_HEAD.json")
    make_stage1b_ladder(root / "stage1b_ladder.json")
    make_d_draw(root / "d_draw.json")
    return {"run": run, "share": share, "root": root,
            "arms": {"S1": arms_s1, "S2": arms_s2},
            "stage1b_ladder": root / "stage1b_ladder.json",
            "d_draw": root / "d_draw.json"}


# --------------------------------------------------------------------------- #
# the COMMITTED fixture set (W8 deliverable, DESIGN §8 builder delta 5)          #
# --------------------------------------------------------------------------- #
REPO = HERE.parents[1]
FIXTURE_DIR = REPO / "tests" / "data" / "tiearb_widening"
FIXTURE_README = """\
# Committed fixture set — tie-arbiter widening instrument (W8 deliverable)

`ARMS.json`, `POSITIONS_PLAN.json` and `per_position_rows.jsonl` for each
stratum. They exist so DESIGN §9 step **4a**'s schema pass can resolve the
`READOUT::widening.*`, `GATE_DISJOINT`, `GATE_DRAW`, `POSITIONS_PLAN` and
`ARMS` spellings **before any real corpus exists**.

The `ARMS.json` fixtures deliberately contain all three rid KINDS:
  * one **champion-append** rid (`champ_outside_tieset`, `len(arms) - len(arms_full) == 1`)
  * one **capped** rid (`capped_at_4`, > 4 deduped arms, so the J=4 draw binds)
  * one **all_transposition** rid (`n_distinct_afterstates == 1`), carried in
    `DROPPED_ALL_TRANSPOSITION.json` as well

⚠️ **Every value here is SYNTHETIC** — produced by a seeded RNG, with no replay,
no playout, no engine and no leaf. These files are a SHAPE contract and are
**never a data source for any statistic**. Regenerate with:

    python scripts/tiletie/widening_fixtures.py --emit
"""


def emit_committed_fixtures(dest=FIXTURE_DIR, *, m_s1=128, m_s2=32,
                            n_rows=4, boot_reps=100):
    """Write the committed fixture set. The `per_position` rows are produced by
    the REAL W3 assembler (`analyze_widening.build_rows`) over a synthetic
    corpus, so the row fixture cannot drift from the emitter's own shape."""
    import shutil
    import tempfile

    import analyze_tiletie as AT                                   # noqa: E402
    import analyze_tiearb as TA                                    # noqa: E402
    import analyze_widening as AW                                  # noqa: E402

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.md").write_text(FIXTURE_README)

    tmp = Path(tempfile.mkdtemp(prefix="widening_fixture_emit_"))
    try:
        for tag, m, seed, prefix, band, e_lev in (
                ("s1", m_s1, 7, "s1", 135000000000, AW.E_LEVELS_S1),
                ("s2", m_s2, 23, "s2", 135000000350, AW.E_LEVELS_S2)):
            src = tmp / f"positions_{tag}"
            arms = make_corpus(src, n_positions=8, m=m, seed=seed,
                               rid_prefix=prefix, band_lo=band)
            make_records(tmp / "share", arms, m=m, seed=seed + 4,
                         stratum_dir=tag)
            out = dest / tag
            out.mkdir(parents=True, exist_ok=True)
            for name in ("ARMS.json", "POSITIONS_PLAN.json",
                         "DROPPED_ALL_TRANSPOSITION.json"):
                shutil.copyfile(src / name, out / name)

            bundle = AT.load_plan(src)
            if_by, _, _, _ = TA.merge_arb_records(
                [tmp / "share" / tag / "clair-puct"])
            arb_by, _, _, _ = TA.merge_arb_records(
                [tmp / "share" / tag / "tier1-greedy"])
            rows, *_ = AW.build_rows(bundle["arms"], if_by, arb_by,
                                     e_levels=e_lev, m_expected=m,
                                     stratum_tag=tag.upper())
            (out / "per_position_rows.jsonl").write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n"
                        for r in rows[:n_rows]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dest


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--emit", action="store_true",
                    help="(re)write the committed fixture set")
    ap.add_argument("--dest", default=str(FIXTURE_DIR))
    a = ap.parse_args(argv)
    if a.emit:
        d = emit_committed_fixtures(a.dest)
        print(f"[fixtures] committed fixture set -> {d}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
