#!/usr/bin/env python3
"""Tests for the tie-arbiter WIDENING run's TWO-BOX chunk + merge layer.

Fast, hermetic, no engine, no scoring. Covers the four properties the frozen
`shared_run_r4/{DESIGN,READ_RULE}.md` pair depends on (rev R4.5):

  1. the permutation is DETERMINISTIC and committed (byte-stable payload);
  2. chunks are WHOLE-RID and partition each stratum exactly;
  3. GATE NEUTRALITY — the CRN seed derivation is a pure function of
     `(rid, j, salt)`, so which box ran a rid cannot change a single seed;
  4. the merge reassembles the exact READ_RULE layout, with a per-rid
     completeness check that fails loudly on any gap or duplicate.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CAMPAIGN = REPO / "measurement" / "tiearb_widening_20260817"
TILETIE = REPO / "scripts" / "tiletie"
INFRA = REPO / "scripts" / "measurement_infra"
for p in (str(CAMPAIGN), str(TILETIE), str(INFRA)):
    if p not in sys.path:
        sys.path.insert(0, p)

import merge_legs as ML                                            # noqa: E402
import stage_chunks as SC                                          # noqa: E402

PROFILE = "walled"
JUDGES = ("tier1-greedy", "clair-puct")


# --------------------------------------------------------------------------- #
# a corpus positions dir in the shape `build_positions.py` writes              #
# --------------------------------------------------------------------------- #
def make_corpus(out_dir: Path, *, n=24, m=128, roots=6, max_arms=4,
                prefix="tt_sp") -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    arms_index, by_leg = {}, {}
    for i in range(n):
        root = f"{prefix}_{135000000000 + (i % roots)}"
        rid = f"{root}_p{i:03d}"
        n_arms = 2 + (i % (max_arms - 1))            # 2..max_arms
        arms = [100 + i * 10 + k for k in range(n_arms)]
        arms_index[rid] = {
            "rid": rid, "root_id": root, "stratum": "selfplay",
            "rules_profile": PROFILE, "ply": 10 + i,
            "arms": arms, "arms_full": arms,
            "subset_j4": arms[:4],
            "capped": False, "capped_at_4": (n_arms > 4),
            "cap_seed": 1000 + i,
            "champ_action": arms[0], "champ_arm_action": arms[0],
            "champ_arm_index": 0, "champ_outside_tieset": False,
            "n_distinct_afterstates": n_arms,
        }
        for r in range(1, n_arms):
            by_leg.setdefault(f"{PROFILE}/leg{r}", []).append(json.dumps(
                {"rid": rid, "root_id": root, "ply": 10 + i,
                 "pick_a": arms[0], "pick_b": arms[r],
                 "rules_profile": PROFILE, "stratum": "selfplay"}))

    files = {}
    for key, lines in sorted(by_leg.items()):
        p = out / f"positions_{key.replace('/', '_')}.jsonl"
        p.write_text("".join(ln + "\n" for ln in sorted(lines)))
        files[key] = {"n": len(lines), "path": str(p)}

    arm_counts = [len(v["arms"]) for v in arms_index.values()]
    total_playouts = sum((c - 1) * 2 * m for c in arm_counts)
    plan = {
        "schema": "carcassonne-tiletie-positions/v1",
        "design_doc": "measurement/tiearb_widening_20260817/shared_run_r4/DESIGN.md",
        "n_positions": len(arms_index),
        "n_e4": 0, "n_selfplay": len(arms_index),
        "counts_by_stratum": {"selfplay": len(arms_index)},
        "counts_by_profile_leg": {k: v["n"] for k, v in files.items()},
        "max_arms": max(arm_counts), "mean_arms": sum(arm_counts) / len(arm_counts),
        # ---- the corpus properties the gates address ------------------------ #
        "cap_j": None, "cap_j_label": "inf", "uncapped": True,
        "deployed_cap_j": 4,
        "world_seed_salt": "tiletie-v1",
        "sample_seed": 20260819,
        "m_worlds": m, "playout_secs": 0.178232, "t_champ_secs": 13.7552,
        "afterstate_dedupe": {"applied": True, "n_dropped_all_transposition": 0},
        "exclude_rids": {"applied": False, "n_requested": 0,
                         "n_removed_from_supply": 0,
                         "n_supply_after_exclusion": len(arms_index)},
        "n_positions_capped": 0,
        "n_positions_capped_at_4": sum(1 for v in arms_index.values()
                                       if v["capped_at_4"]),
        "mean_arms_j4": sum(len(v["subset_j4"]) for v in arms_index.values()) / len(arms_index),
        "total_arm_playouts": total_playouts,
        "oracle_worker_secs": total_playouts * 0.178232,
        "champ_pick_secs": len(arms_index) * 13.7552,
        "total_worker_secs": total_playouts * 0.178232 + len(arms_index) * 13.7552,
        "eta_by_workers": {"W=30": {"wall_secs": 1.0, "wall_hours": 1.0}},
        "files": files,
        "out_dir": str(out),
    }
    (out / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=1))
    (out / "ARMS.json").write_text(json.dumps(arms_index, indent=1))
    (out / "DROPPED_ALL_TRANSPOSITION.json").write_text(
        json.dumps({"n": 0, "rows": []}, indent=1))
    return arms_index


def stage(tmp: Path, corpus: Path, *, chunks=4, stratum="s1"):
    out_root = tmp / "campaign"
    out_root.mkdir(parents=True, exist_ok=True)
    argv = ["stage", "--out-root", str(out_root), f"--{stratum}-dir", str(corpus),
            "--stratum", stratum, f"--chunks-{stratum}", str(chunks),
            "--allow-m-mismatch"]
    assert SC.main(argv) == 0
    return out_root


# --------------------------------------------------------------------------- #
# leg output, in the shape the two leg drivers actually write                   #
# --------------------------------------------------------------------------- #
def write_leg_output(root: Path, plan_dir: Path, *, judges=JUDGES, m=128,
                     chunk_tag="chunk1", box="local", workers=30):
    """`<root>/<judge>/<profile>/leg<N>/{records/<rid>.json, manifest.json}`."""
    plan = json.loads((Path(plan_dir) / "POSITIONS_PLAN.json").read_text())
    for judge in judges:
        for key, info in sorted(plan["files"].items()):
            profile, leg_tag = key.split("/leg")
            leg_dir = Path(root) / judge / profile / f"leg{leg_tag}"
            recs = leg_dir / "records"
            recs.mkdir(parents=True, exist_ok=True)
            rids = [json.loads(ln)["rid"]
                    for ln in Path(info["path"]).read_text().splitlines() if ln.strip()]
            for rid in rids:
                # the CONTENT is a pure function of (rid, leg, judge, m): this is
                # the property the neutrality claim asserts, so the fixture
                # honours it — the merged tree must be byte-identical per rid.
                (recs / f"{rid}.json").write_text(json.dumps(
                    {"rid": rid, "leg": int(leg_tag), "judge": judge, "m": m,
                     "crn_verified": True,
                     "world_seeds": _seeds(rid, m)}, sort_keys=True))
            man = {
                "schema": "carcassonne-tiletie-tier1-rust-leg/v1",
                "driver": "tier1_rust_leg", "git_rev": "abc1234",
                "judge": judge, "profile": profile, "leg": int(leg_tag),
                "generated_utc": "2026-08-18T00:00:00Z",
                "host": box, "python": "/x/.venv/bin/python",
                "resolved_config": {
                    "positions_jsonl": info["path"],
                    "rules_profile": profile, "oracle_policy": judge,
                    "arb_backend": "rust", "m": m,
                    "world_seed_salt": "tiletie-v1",
                    "legal_mask_cache": True,
                    "workers": workers, "n": len(rids),
                    "out_root": str(root), "out_subdir": f"{judge}/{profile}/leg{leg_tag}",
                    "resume": True,
                },
                "preflight": {"seeds": {
                    "ok": True,
                    "prefix_stable_at": [b for b in (1, 2, 4, 8, 16, 32, 64, 128)
                                         if b <= m],
                    "derivation": "sha256(tag|rid|j|salt); M never enters",
                }},
                "n_rows_in": len(rids), "n_scored": len(rids),
                "n_ok": len(rids), "n_failed": 0, "errors": [],
                "n_crn_verified": len(rids),
                "n_playouts": len(rids) * 2 * m,
                "elapsed_secs_sum": round(0.5 * len(rids), 3),
                "wall_secs": round(1.0 * len(rids), 3),
            }
            (leg_dir / "manifest.json").write_text(json.dumps(man, indent=2, sort_keys=True))


def _seeds(rid, m):
    import oracle_score_pilot as OSP
    return OSP.world_seeds(rid, m, "tiletie-v1")


@pytest.fixture()
def corpus(tmp_path):
    d = tmp_path / "corpus" / "positions_s1"
    make_corpus(d)
    return d


# =========================================================================== #
# 1. the permutation                                                          #
# =========================================================================== #
def test_permutation_is_deterministic_and_seed_committed(corpus):
    arms = json.loads((corpus / "ARMS.json").read_text())
    a, _ = SC.build_order_doc({"s1": arms}, {"s1": 4})
    b, _ = SC.build_order_doc({"s1": arms}, {"s1": 4})
    assert a == b
    assert SC.order_payload(a) == SC.order_payload(b)
    assert a["seed"] == SC.PERMUTATION_SEED == 20260817
    # and it is a SHUFFLE of the SORTED list, not the sorted list
    assert sorted(a["strata"]["s1"]["order"]) == sorted(arms)
    assert a["strata"]["s1"]["order"] != sorted(arms)
    other, _ = SC.build_order_doc({"s1": arms}, {"s1": 4}, seed=99)
    assert other["strata"]["s1"]["order"] != a["strata"]["s1"]["order"]


def test_order_digest_matches_the_committed_spelling(corpus):
    import hashlib
    arms = json.loads((corpus / "ARMS.json").read_text())
    doc, _ = SC.build_order_doc({"s1": arms}, {"s1": 4})
    order = doc["strata"]["s1"]["order"]
    # one rid per line WITH a trailing newline — the tiearb2_20260816 spelling
    want = hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()
    assert doc["strata"]["s1"]["sha256_order"] == want


def test_chunks_partition_the_stratum_exactly(corpus):
    arms = json.loads((corpus / "ARMS.json").read_text())
    doc, chunks = SC.build_order_doc({"s1": arms}, {"s1": 5})
    flat = [r for c in chunks["s1"] for r in c]
    assert sorted(flat) == sorted(arms)
    assert len(flat) == len(set(flat))
    assert doc["strata"]["s1"]["chunk_sizes"] == [len(c) for c in chunks["s1"]]
    assert sum(doc["strata"]["s1"]["chunk_sizes"]) == len(arms)


def test_more_chunks_than_rids_is_refused(corpus):
    arms = json.loads((corpus / "ARMS.json").read_text())
    with pytest.raises(SystemExit):
        SC.build_order_doc({"s1": arms}, {"s1": len(arms) + 1})


# =========================================================================== #
# 2. the WHOLE-RID invariant                                                   #
# =========================================================================== #
def test_whole_rid_invariant_holds_on_a_real_cut(corpus):
    plan, arms, _ = SC.load_plan_dir(corpus)
    leg_rows = SC.read_leg_files(corpus, plan)
    _, chunks = SC.build_order_doc({"s1": arms}, {"s1": 4})
    inv = SC.check_whole_rid(chunks["s1"], leg_rows)
    assert inv["ok"], inv
    assert inv["n_rids"] == len(arms)


def test_whole_rid_invariant_DETECTS_a_rid_split_across_chunks(corpus):
    plan, arms, _ = SC.load_plan_dir(corpus)
    leg_rows = SC.read_leg_files(corpus, plan)
    _, chunks = SC.build_order_doc({"s1": arms}, {"s1": 4})
    bad = [list(c) for c in chunks["s1"]]
    victim = bad[0][0]
    bad[1].append(victim)                       # the same rid in two chunks
    inv = SC.check_whole_rid(bad, leg_rows)
    assert not inv["ok"]
    assert victim in inv["problem"]


def test_whole_rid_invariant_detects_an_orphan_rid(corpus):
    plan, arms, _ = SC.load_plan_dir(corpus)
    leg_rows = SC.read_leg_files(corpus, plan)
    _, chunks = SC.build_order_doc({"s1": arms}, {"s1": 4})
    bad = [list(c) for c in chunks["s1"]]
    bad[0] = bad[0][1:]                         # drop one rid from every chunk set
    inv = SC.check_whole_rid(bad, leg_rows)
    assert not inv["ok"]
    assert inv["n_orphan"] >= 1


# =========================================================================== #
# 3. GATE NEUTRALITY — the seed derivation                                     #
# =========================================================================== #
def test_crn_seeds_depend_only_on_rid_j_and_salt():
    """THE neutrality argument, executed.

    `oracle_score_pilot.world_seed/playout_seed` are
    `sha256(tag|rid|j|salt)[:8] & 0x7FFFFFFF`. Neither the chunk, the box, the
    worker count, the position's index in its leg file, nor M appears — which is
    why a rid produced on the laptop is bit-identical to the same rid produced
    locally, and why worlds are prefix-stable in M.
    """
    import oracle_score_pilot as OSP
    rid, salt = "tt_sp_135000000003_p017", "tiletie-v1"
    # (a) pure function of (rid, j, salt)
    assert OSP.world_seed(rid, 7, salt) == OSP.world_seed(rid, 7, salt)
    assert OSP.world_seed(rid, 7, salt) != OSP.world_seed(rid, 8, salt)
    assert OSP.world_seed(rid, 7, salt) != OSP.world_seed(rid + "x", 7, salt)
    assert OSP.world_seed(rid, 7, salt) != OSP.world_seed(rid, 7, salt + "x")
    # (b) world and playout streams are distinct but both pick-independent
    assert OSP.playout_seed(rid, 7, salt) != OSP.world_seed(rid, 7, salt)
    # (c) M NEVER ENTERS: the M=32 ladder is a prefix of the M=128 ladder
    full = OSP.world_seeds(rid, 128, salt)
    for k in (1, 2, 4, 8, 16, 32, 64, 128):
        assert OSP.world_seeds(rid, k, salt) == full[:k]


def test_tier1_rust_leg_imports_the_pilot_seed_functions_not_a_copy():
    """The ARB leg must not re-implement the derivation — `preflight_seeds`
    imports `world_seed`/`playout_seed`/`world_seeds` from `oracle_score_pilot`
    and asserts they agree, fatally, at launch."""
    src = (TILETIE / "tier1_rust_leg.py").read_text()
    assert "from oracle_score_pilot import playout_seed, world_seed, world_seeds" in src
    import tier1_rust_leg as TRL
    seeds = TRL.preflight_seeds("tiletie-v1", 128)
    assert seeds["ok"] is True
    assert set(seeds["prefix_stable_at"]) >= {1, 2, 4, 8, 16, 32, 64, 128}
    assert "M never enters" in seeds["derivation"]


def test_run_tiletie_salt_is_the_module_constant_of_record():
    import run_tiletie as RT
    assert RT.WORLD_SEED_SALT == "tiletie-v1"
    src = (TILETIE / "run_tiletie.py").read_text()
    # passed to BOTH leg drivers, identically
    assert src.count('"--world-seed-salt", WORLD_SEED_SALT') == 2


# =========================================================================== #
# 4. staging                                                                   #
# =========================================================================== #
def test_stage_writes_exact_rid_subsets_and_verify_passes(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    doc = json.loads((out_root / "POSITION_ORDER.json").read_text())
    arms_all = set(json.loads((corpus / "ARMS.json").read_text()))

    union, seen = set(), []
    for k in range(1, 5):
        d = out_root / "chunks" / "s1" / f"chunk{k}"
        got = set(json.loads((d / "ARMS.json").read_text()))
        assert got, f"chunk{k} empty"
        assert not (union & got), "chunks overlap"
        union |= got
        seen.append(len(got))
    assert union == arms_all
    assert seen == doc["strata"]["s1"]["chunk_sizes"]

    assert SC.main(["verify", "--out-root", str(out_root), "--s1-dir", str(corpus),
                    "--stratum", "s1"]) == 0


def test_chunk_plans_carry_the_gate_addressed_corpus_keys_verbatim(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=3)
    src = json.loads((corpus / "POSITIONS_PLAN.json").read_text())
    for k in range(1, 4):
        cp = json.loads((out_root / "chunks" / "s1" / f"chunk{k}" /
                         "POSITIONS_PLAN.json").read_text())
        for key in ("uncapped", "cap_j", "cap_j_label", "deployed_cap_j",
                    "m_worlds", "sample_seed", "world_seed_salt",
                    "afterstate_dedupe", "playout_secs", "t_champ_secs"):
            assert cp[key] == src[key], key
        # ...and the rid-dependent ones ARE recomputed
        assert cp["n_positions"] < src["n_positions"]
        assert cp["total_arm_playouts"] < src["total_arm_playouts"]
        assert cp["files"] and all(Path(v["path"]).is_file() for v in cp["files"].values())
        assert cp["chunk"]["index"] == k
        assert cp["chunk"]["permutation_seed"] == SC.PERMUTATION_SEED


def test_chunk_leg_lines_are_byte_identical_to_the_corpus_lines(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    src_plan = json.loads((corpus / "POSITIONS_PLAN.json").read_text())
    src_lines = {}
    for key, info in src_plan["files"].items():
        for ln in Path(info["path"]).read_text().splitlines():
            if ln.strip():
                src_lines[(key, json.loads(ln)["rid"])] = ln

    seen = set()
    for k in range(1, 5):
        cp = json.loads((out_root / "chunks" / "s1" / f"chunk{k}" /
                         "POSITIONS_PLAN.json").read_text())
        for key, info in cp["files"].items():
            for ln in Path(info["path"]).read_text().splitlines():
                if not ln.strip():
                    continue
                rid = json.loads(ln)["rid"]
                assert ln == src_lines[(key, rid)], "leg line was not carried verbatim"
                assert (key, rid) not in seen, "a leg row appeared in two chunks"
                seen.add((key, rid))
    assert seen == set(src_lines)


def test_verify_refuses_a_tampered_chunk(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=3)
    d = out_root / "chunks" / "s1" / "chunk1"
    arms = json.loads((d / "ARMS.json").read_text())
    arms.pop(sorted(arms)[0])
    (d / "ARMS.json").write_text(json.dumps(arms, indent=1))
    with pytest.raises(SystemExit):
        SC.main(["verify", "--out-root", str(out_root), "--s1-dir", str(corpus),
                 "--stratum", "s1"])


def test_verify_refuses_a_chunk_plan_that_lost_uncapped(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=3)
    p = out_root / "chunks" / "s1" / "chunk2" / "POSITIONS_PLAN.json"
    plan = json.loads(p.read_text())
    plan["uncapped"] = False
    p.write_text(json.dumps(plan, indent=1))
    with pytest.raises(SystemExit):
        SC.main(["verify", "--out-root", str(out_root), "--s1-dir", str(corpus),
                 "--stratum", "s1"])


def test_stage_accepts_a_corpus_plan_whose_m_worlds_is_cost_metadata(tmp_path):
    """⚠️ THIS TEST USED TO ASSERT THE OPPOSITE, AND THAT IS HOW THE DEFECT
    SURVIVED. It required the stage to REFUSE an S1 corpus whose plan carries
    `m_worlds = 32` — but `build_positions` has no `--m` flag, so EVERY corpus
    it writes carries 32, and no S1 corpus this pipeline can build was ever
    stageable. The test locked the bug in: it passed because the code was wrong
    in the same direction.

    `m_worlds` is cost-arithmetic metadata (playout totals, ETA); it never
    enters seeds, positions, arms or digests. The M of record is `G-M`'s, read
    from `RUN_MANIFEST` via `run_tiletie --m`."""
    d = tmp_path / "corpus" / "positions_s1"
    make_corpus(d, m=32)                      # exactly what build_positions writes
    out_root = tmp_path / "campaign"
    out_root.mkdir()
    assert SC.main(["stage", "--out-root", str(out_root), "--s1-dir", str(d),
                    "--stratum", "s1", "--chunks-s1", "2"]) == 0
    doc = json.loads((out_root / "POSITION_ORDER.json").read_text())
    assert doc["strata"]["s1"]["m"] == 128    # the COMMITTED M is what we stamp


# =========================================================================== #
# 5. the merge                                                                 #
# =========================================================================== #
def _run_two_box(tmp_path, corpus, *, chunks=4, local=(1, 2), laptop=(3, 4)):
    """Stage, then fake the per-chunk leg output of a two-box run."""
    out_root = stage(tmp_path, corpus, chunks=chunks)
    share = tmp_path / "share"
    for k in range(1, chunks + 1):
        box = "local" if k in local else "laptop"
        write_leg_output(share / "chunks" / "s1" / f"chunk{k}",
                         out_root / "chunks" / "s1" / f"chunk{k}",
                         chunk_tag=f"chunk{k}", box=box,
                         workers=30 if box == "local" else 22)
    return out_root, share


def test_merge_reassembles_a_complete_tree_both_judges(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    rep = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                           out_dir=share / "s1", positions_dir=corpus)
    assert rep["ok"], rep["problems"]
    plan = json.loads((corpus / "POSITIONS_PLAN.json").read_text())
    for judge in JUDGES:
        for key, info in plan["files"].items():
            profile, leg_tag = key.split("/leg")
            recs = share / "s1" / judge / profile / f"leg{leg_tag}" / "records"
            assert len({p.stem for p in recs.glob("*.json")}) == info["n"]
            assert (recs.parent / "manifest.json").is_file()
            leg = rep["legs"][f"{judge}/{key}"]
            assert leg["ok"] and leg["n_missing"] == 0 and leg["n_duplicate"] == 0
            # every chunk contributed
            assert sum(leg["by_chunk"].values()) == info["n"]


def test_merged_tree_is_byte_identical_to_a_single_box_run(tmp_path, corpus):
    """THE NEUTRALITY CLAIM, end to end: a merged two-box tree and a single-box
    tree over the same corpus agree byte-for-byte, per rid."""
    out_root, share = _run_two_box(tmp_path, corpus, chunks=4)
    assert ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                            out_dir=share / "s1", positions_dir=corpus)["ok"]
    single = tmp_path / "single" / "s1"
    write_leg_output(single, corpus, chunk_tag="whole", box="local", workers=30)

    merged_files = sorted(p.relative_to(share / "s1")
                          for p in (share / "s1").rglob("records/*.json"))
    single_files = sorted(p.relative_to(single)
                          for p in single.rglob("records/*.json"))
    assert merged_files == single_files
    for rel in merged_files:
        assert (share / "s1" / rel).read_bytes() == (single / rel).read_bytes()


def test_merge_fails_loudly_on_a_gap(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    victim = next((share / "chunks" / "s1" / "chunk3").rglob("records/*.json"))
    lost = victim.stem
    victim.unlink()
    rep = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                           out_dir=share / "s1", positions_dir=corpus)
    assert not rep["ok"]
    assert any("MISSING" in p for p in rep["problems"])
    assert any(lost in leg["missing"] for leg in rep["legs"].values())


def test_merge_fails_loudly_on_a_duplicate_across_chunks(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    src = next((share / "chunks" / "s1" / "chunk1").rglob("records/*.json"))
    rel = src.relative_to(share / "chunks" / "s1" / "chunk1")
    dup = share / "chunks" / "s1" / "chunk2" / rel
    dup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dup)
    rep = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                           out_dir=share / "s1", positions_dir=corpus)
    assert not rep["ok"]
    assert any("DUPLICATE" in p for p in rep["problems"])


def test_merge_flags_a_duplicate_whose_bytes_differ(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    src = next((share / "chunks" / "s1" / "chunk1").rglob("records/*.json"))
    rel = src.relative_to(share / "chunks" / "s1" / "chunk1")
    dup = share / "chunks" / "s1" / "chunk2" / rel
    dup.parent.mkdir(parents=True, exist_ok=True)
    dup.write_text(src.read_text() + " ")
    rep = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                           out_dir=share / "s1", positions_dir=corpus)
    assert not rep["ok"]
    leg = next(v for v in rep["legs"].values() if v["n_duplicate"])
    assert leg["n_duplicate_bytes_differ"] == 1


def test_merge_never_parses_a_record(tmp_path, corpus):
    """A record whose bytes are not JSON still merges: the rid comes from the
    FILE NAME and the bytes are copied. That is the blindness property — no
    value, mean, sd, Δ or CI can pass through this layer."""
    out_root, share = _run_two_box(tmp_path, corpus)
    for p in (share / "chunks" / "s1").rglob("records/*.json"):
        p.write_bytes(b"\x00 NOT JSON \xff")
    rep = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                           out_dir=share / "s1", positions_dir=corpus)
    assert rep["ok"], rep["problems"]
    some = next((share / "s1").rglob("records/*.json"))
    assert some.read_bytes() == b"\x00 NOT JSON \xff"


def test_merge_is_idempotent(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    a = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                         out_dir=share / "s1", positions_dir=corpus)
    b = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                         out_dir=share / "s1", positions_dir=corpus)
    assert a["ok"] and b["ok"]
    assert b["n_records_copied"] == 0          # nothing re-copied on the 2nd pass


def test_dry_run_writes_nothing(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    rep = ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                           out_dir=share / "s1", positions_dir=corpus, dry_run=True)
    assert rep["ok"]
    assert not (share / "s1").exists()


# =========================================================================== #
# 6. manifest merging                                                          #
# =========================================================================== #
def test_merged_leg_manifest_sums_counters_and_keeps_gate_fields(tmp_path, corpus):
    out_root, share = _run_two_box(tmp_path, corpus)
    assert ML.merge_stratum(stratum="s1", chunks_root=share / "chunks" / "s1",
                            out_dir=share / "s1", positions_dir=corpus)["ok"]
    plan = json.loads((corpus / "POSITIONS_PLAN.json").read_text())
    key, info = sorted(plan["files"].items())[0]
    profile, leg_tag = key.split("/leg")
    man = json.loads((share / "s1" / "tier1-greedy" / profile / f"leg{leg_tag}" /
                      "manifest.json").read_text())
    assert man["n_ok"] == info["n"]
    assert man["n_crn_verified"] == info["n"]
    assert man["n_playouts"] == info["n"] * 2 * 128
    # gate-addressed fields survive verbatim
    assert man["resolved_config"]["world_seed_salt"] == "tiletie-v1"
    assert man["resolved_config"]["m"] == 128
    assert man["resolved_config"]["legal_mask_cache"] is True
    assert man["preflight"]["seeds"]["ok"] is True
    assert set(man["preflight"]["seeds"]["prefix_stable_at"]) >= {1, 2, 4, 8, 16, 32, 64, 128}
    # chunk-varying fields are NOT silently one box's value
    assert man["resolved_config"]["workers"] is None
    assert man["resolved_config"]["n"] == info["n"]
    assert sorted(int(k) for k in man["merge"]["by_chunk"]) == [1, 2, 3, 4]


def test_manifest_merge_fails_on_a_divergent_gate_field():
    a = {"schema": "x", "git_rev": "abc1234",
         "resolved_config": {"world_seed_salt": "tiletie-v1", "m": 128,
                             "legal_mask_cache": True},
         "n_ok": 5}
    b = json.loads(json.dumps(a))
    b["resolved_config"]["world_seed_salt"] = "tiletie-v2"
    with pytest.raises(ML.MergeError, match="world_seed_salt"):
        ML.merge_manifests({1: a, 2: b})


def test_manifest_merge_fails_on_a_mixed_rev_run():
    a = {"schema": "x", "git_rev": "abc1234", "n_ok": 5}
    b = {"schema": "x", "git_rev": "def5678", "n_ok": 5}
    with pytest.raises(ML.MergeError, match="git_rev"):
        ML.merge_manifests({1: a, 2: b})


def test_manifest_merge_is_fail_closed_on_an_unknown_divergent_key():
    a = {"schema": "x", "git_rev": "abc1234", "surprise": 1}
    b = {"schema": "x", "git_rev": "abc1234", "surprise": 2}
    with pytest.raises(ML.MergeError, match="surprise"):
        ML.merge_manifests({1: a, 2: b})
    merged = ML.merge_manifests({1: a, 2: b}, allow_varying=["surprise"])
    assert merged["merge"]["divergent_keys_allowed"] == ["surprise"]


def test_run_manifest_merge_unions_the_backend_map(tmp_path):
    d = tmp_path / "manifests"
    d.mkdir()
    base = {"schema": "s", "driver": "run_tiletie", "design_doc": "d",
            "git_rev": "abc1234", "world_seed_salt": "tiletie-v1",
            "m_worlds": 128, "m_max": 128, "b_ceiling_from_m": 64,
            "arb_backend": "rust", "arb_legal_mask_cache": True,
            "oracle_sims": 100,
            "preflight": {"checks": {"leaf_hash": {
                "ok": True, "harness_leaf_hash": "a36d2e15a3b3d71d",
                "expected": "a36d2e15a3b3d71d"}}}}
    for judge, legs in (("tier1-greedy", {"tier1-greedy/walled/leg1": "rust"}),
                        ("clair-puct", {"clair-puct/walled/leg1": "rust"})):
        for k in (1, 2):
            m = json.loads(json.dumps(base))
            m["judges"] = [judge]
            m["judge_backend"] = {judge: "rust"}
            m["resolved_backend_by_leg"] = legs
            (d / f"RUN_MANIFEST_S1_{judge}_chunk{k}.json").write_text(json.dumps(m))
    out = tmp_path / "RUN_MANIFEST_S1.json"
    res = ML.merge_run_manifest(stratum="s1", manifests_dir=d, out_path=out)
    assert res["ok"], res["problems"]
    merged = json.loads(out.read_text())
    assert merged["world_seed_salt"] == "tiletie-v1"
    assert merged["m_worlds"] == 128 and merged["b_ceiling_from_m"] == 64
    assert merged["arb_backend"] == "rust" and merged["arb_legal_mask_cache"] is True
    assert merged["preflight"]["checks"]["leaf_hash"]["ok"] is True
    assert set(merged["resolved_backend_by_leg"]) == {
        "tier1-greedy/walled/leg1", "clair-puct/walled/leg1"}
    assert sorted(merged["judges"]) == ["clair-puct", "tier1-greedy"]


# =========================================================================== #
# 7. the allocation + the launchers                                            #
# =========================================================================== #
def _parse_conf(path: Path) -> dict:
    out = {}
    for ln in Path(path).read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        v = v.strip()
        if v.startswith('"'):
            v = v[1:].split('"', 1)[0]
        else:
            v = v.split("#", 1)[0].strip()
        out[k.strip()] = v
    return out


def test_allocation_covers_every_chunk_exactly_once_per_stratum_and_judge():
    conf = _parse_conf(CAMPAIGN / "ALLOCATION.conf")
    for stratum in ("s1", "s2"):
        n = int(conf[f"N_CHUNKS_{stratum}"])
        for judge in ("tier1_greedy", "clair_puct"):
            got = []
            for box in ("local", "laptop_side"):
                got += conf[f"ALLOC_{stratum}_{box}_{judge}"].split()
            assert sorted(int(x) for x in got) == list(range(1, n + 1)), (
                f"{stratum}/{judge}: allocation is not an exact cover of 1..{n} "
                f"(got {sorted(got)}) — a gap loses rids, an overlap double-scores")


def test_allocation_matches_the_two_box_capacity_ratio():
    """local : laptop worker-hours ~= 30 : 22*0.75, per stratum."""
    conf = _parse_conf(CAMPAIGN / "ALLOCATION.conf")
    c_arb, c_if = float(conf["C_ARB_ASSUMED"]), float(conf["C_IF_ASSUMED"])
    rate = float(conf["LAPTOP_RATE"])
    playouts = {"s1": 891993, "s2": 430848}
    for stratum, n_play in playouts.items():
        n = int(conf[f"N_CHUNKS_{stratum}"])
        wh = {}
        for box in ("local", "laptop_side"):
            tot = 0.0
            for judge, c in (("tier1_greedy", c_arb), ("clair_puct", c_if)):
                ks = conf[f"ALLOC_{stratum}_{box}_{judge}"].split()
                tot += len(ks) / n * n_play * c / 3600.0
            wh[box] = tot
        share_local = wh["local"] / (wh["local"] + wh["laptop_side"])
        ideal = 30.0 / (30.0 + 22.0 * rate)
        assert abs(share_local - ideal) < 0.05, (
            f"{stratum}: local takes {share_local:.3f} of the worker-hours, "
            f"capacity says {ideal:.3f}")


@pytest.mark.parametrize("script", ["run_scoring.sh", "merge_scoring.sh"])
def test_launchers_are_executable_and_syntactically_valid(script):
    import subprocess
    p = CAMPAIGN / script
    assert p.is_file() and p.stat().st_mode & 0o111, f"{script} not executable"
    assert subprocess.run(["bash", "-n", str(p)]).returncode == 0


def test_run_scoring_names_every_binding_knob():
    src = (CAMPAIGN / "run_scoring.sh").read_text()
    # DESIGN §0.O — --positions-dir is ALWAYS explicit; the default is the SPENT corpus
    assert "--positions-dir" in src and '"$PLAN"' in src
    assert "--arb-backend" in src and "rust" in src
    assert "--arb-legal-mask-cache" in src
    assert "--only-profiles" in src and "walled" in src
    assert "--m" in src and '"$M"' in src
    assert "m_for()" in src and "echo 128" in src and "echo 32" in src
    # the salt is a module constant, so it is ASSERTED, not passed
    assert "WORLD_SEED_SALT" in src
    # the two boxes' share paths come from WORKERS.conf, never hard-coded
    assert "SHARE_RUN_LOCAL" in src and "SHARE_RUN_REMOTE" in src
    assert "W_EVAL_LOCAL" in src and "W_EVAL_LAPTOP" in src
    # detach discipline is documented in the header
    assert "setsid nohup" in src and "disown" in src
    # nothing may be written into the frozen prereg dir by the launcher
    # rev R4.5: the name is composed from WORKERS.conf::PREREG_DIR_NAME, never
    # re-typed — one place to be wrong beats six.
    assert 'RUN_DIR="$CAMPAIGN/$PREREG_DIR_NAME"' in src


def test_run_scoring_writes_no_per_chunk_artifact_into_the_prereg_dir():
    src = (CAMPAIGN / "run_scoring.sh").read_text()
    for flag in ("--gate-out", "--manifest-out"):
        i = src.index(flag)
        line = src[i:src.index("\n", i)]
        assert "$RUN_DIR" not in line, f"{flag} points into the FROZEN prereg dir"


def test_the_frozen_pair_is_untouched_by_this_layer():
    """Nothing this layer ships lives under EITHER prereg dir."""
    ours = {"stage_chunks.py", "merge_legs.py", "ALLOCATION.conf",
            "run_scoring.sh", "merge_scoring.sh"}
    for name in ours:
        assert (CAMPAIGN / name).is_file()
        assert not (CAMPAIGN / "shared_run" / name).exists()
        assert not (CAMPAIGN / "shared_run_r4" / name).exists()


# --------------------------------------------------------------------------- #
# The S1 STAGE PATH — never exercised until now, because every stage test in    #
# this file passes `--allow-m-mismatch` and the S1 assertion could not pass     #
# without it.                                                                   #
# --------------------------------------------------------------------------- #
def test_s1_stage_succeeds_when_the_corpus_plan_carries_m32(tmp_path):
    """THE EXACT CASE THAT WAS UNRUNNABLE.

    `build_positions` has no `--m` flag: every corpus plan it writes carries
    `m_worlds = 32` from a module constant used only for cost arithmetic. S1 is
    scored at `--m 128`. The old assertion compared the two and died, so NO S1
    corpus this pipeline can build could ever be staged — and S2 passed only
    because 32 coincidentally equals its committed M.
    """
    corpus = tmp_path / "positions_s1"
    make_corpus(corpus, n=24, m=32)   # as build_positions writes it
    out_root = tmp_path / "campaign"
    out_root.mkdir(parents=True, exist_ok=True)
    rc = SC.main(["stage", "--out-root", str(out_root),
                  "--s1-dir", str(corpus), "--stratum", "s1", "--chunks-s1", "4"])
    assert rc == 0, "the S1 stage must run on a corpus plan that says m_worlds=32"

    # POSITION_ORDER.json stamps the COMMITTED M (128), not the plan's 32
    doc = json.loads((out_root / "POSITION_ORDER.json").read_text())
    assert doc["strata"]["s1"]["m"] == 128
    # ... and the chunk plans still carry the corpus plan's own number verbatim,
    # because it is that plan's cost arithmetic and must not be "corrected"
    plan = json.loads((out_root / "chunks" / "s1" / "chunk1"
                       / "POSITIONS_PLAN.json").read_text())
    assert plan["m_worlds"] == 32


def test_s1_stage_reports_the_m_discrepancy_without_failing(tmp_path, capsys):
    """Reported, not asserted — and the report says WHY the field is not a
    defect, so the next reader does not re-assert it."""
    corpus = tmp_path / "positions_s1"
    make_corpus(corpus, n=16, m=32)
    out_root = tmp_path / "campaign"
    out_root.mkdir(parents=True, exist_ok=True)
    assert SC.main(["stage", "--out-root", str(out_root), "--s1-dir", str(corpus),
                    "--stratum", "s1", "--chunks-s1", "2"]) == 0
    out = capsys.readouterr().out
    assert "corpus plan m_worlds=32" in out and "committed m=128" in out
    assert "no --m flag" in out and "cost-arithmetic metadata" in out
    assert "G-M" in out and "run_tiletie --m" in out


def test_stage_summary_separates_committed_m_from_the_plans_cost_metadata(tmp_path):
    corpus = tmp_path / "positions_s1"
    make_corpus(corpus, n=16, m=32)
    out_root = tmp_path / "campaign"
    out_root.mkdir(parents=True, exist_ok=True)
    assert SC.main(["stage", "--out-root", str(out_root), "--s1-dir", str(corpus),
                    "--stratum", "s1", "--chunks-s1", "2"]) == 0
    summary = json.loads((out_root / "CHUNK_SUMMARY.json").read_text())
    s1 = summary["strata"]["s1"]
    assert s1["m"] == 128                     # the committed, stamped M
    assert s1["m_plan_cost_metadata"] == 32   # what build_positions wrote


def test_allow_m_mismatch_is_accepted_and_inert(tmp_path):
    """Kept so existing fixture invocations do not fail on an unknown flag —
    but it no longer gates anything, so passing it changes NOTHING."""
    outs = []
    for flag in ([], ["--allow-m-mismatch"]):
        corpus = tmp_path / f"positions_s1{len(outs)}"
        make_corpus(corpus, n=16, m=32)
        out_root = tmp_path / f"campaign{len(outs)}"
        out_root.mkdir(parents=True, exist_ok=True)
        assert SC.main(["stage", "--out-root", str(out_root),
                        "--s1-dir", str(corpus), "--stratum", "s1",
                        "--chunks-s1", "2", *flag]) == 0
        outs.append(json.loads((out_root / "POSITION_ORDER.json").read_text()))
    assert outs[0]["strata"]["s1"]["sha256_order"] == \
        outs[1]["strata"]["s1"]["sha256_order"]
    assert outs[0]["strata"]["s1"]["m"] == outs[1]["strata"]["s1"]["m"] == 128


def test_a_wrong_stamp_still_dies(tmp_path, monkeypatch):
    """What IS worth asserting: the M stamped into POSITION_ORDER.json, which
    the allocation is read against."""
    corpus = tmp_path / "positions_s1"
    make_corpus(corpus, n=16, m=32)
    out_root = tmp_path / "campaign"
    out_root.mkdir(parents=True, exist_ok=True)
    real = SC.build_order_doc

    def sabotage(*args, **kwargs):
        doc, chunks = real(*args, **kwargs)
        doc["strata"]["s1"]["m"] = 64          # a stamp that disagrees
        return doc, chunks

    monkeypatch.setattr(SC, "build_order_doc", sabotage)
    with pytest.raises(SystemExit) as e:
        SC.main(["stage", "--out-root", str(out_root), "--s1-dir", str(corpus),
                 "--stratum", "s1", "--chunks-s1", "2"])
    assert "stamps m=64" in str(e.value) and "commits m=128" in str(e.value)


# =========================================================================== #
# 8. D3 / D4 — the cross-layer invariant, completion staging, `execution`      #
#    Deviations D3 (`355ceb65`) and D4 (`751bdd12`).                           #
# =========================================================================== #
import union_positions as UP                                       # noqa: E402
import widening_fixtures as WF                                     # noqa: E402


def _union_sides(tmp_path, n_banked=6, n_fresh=5):
    banked = tmp_path / "shared_run" / "corpus" / "positions_s1"
    ext = tmp_path / "shared_run_r4" / "corpus" / "positions_s1_ext"
    out = tmp_path / "shared_run_r4" / "corpus" / "positions_s1"
    WF.make_r4_corpus(banked, n_base=n_banked, n_ext=0, seed=301,
                      base_lo=135000000000)
    WF.make_r4_corpus(ext, n_base=0, n_ext=n_fresh, seed=302,
                      ext_lo=137000000000)
    return banked, ext, out


# --------------------------------------------------------------------------- #
# (a) THE CROSS-LAYER INVARIANT — leg files enumerate exactly the ARMS rid set  #
# --------------------------------------------------------------------------- #
def test_union_assembles_leg_files_for_BOTH_sides_and_points_the_plan_at_them(tmp_path):
    """THE D4 DEFECT, inverted into a test. The union merged ARMS but left the
    leg files extension-only, so 551 committed rids had no leg line and were
    never scored — while every count read complete."""
    banked, ext, out = _union_sides(tmp_path)
    prov = UP.assemble(banked, ext, out, stratum="s1")
    arms = set(json.loads((out / "ARMS.json").read_text()))
    plan = json.loads((out / "POSITIONS_PLAN.json").read_text())
    assert plan["files"], "the union plan must carry a files block"
    leg_rids = set()
    for key, info in plan["files"].items():
        p = Path(info["path"])
        # ⚠️ the plan must point INSIDE the union dir, never at the extension
        assert p.parent == out, f"{key} points at {p.parent}, not the union"
        leg_rids |= {json.loads(ln)["rid"]
                     for ln in p.read_text().splitlines() if ln.strip()}
    assert leg_rids == arms and len(arms) == 11
    leg = prov["leg_layer"]
    assert leg["witnessed"] is True and leg["set_equality"]["ok"] is True
    assert leg["set_equality"]["both_directions_checked"] is True
    assert leg["n_rids_in_leg_files"] == leg["n_rids_in_arms"] == 11
    assert leg["n_lines_by_side"] == {"banked": 6, "extension": 5}
    for v in leg["files"].values():
        assert len(v["sha256"]) == 64 and v["n_rids"] == v["n_lines"]


def test_cross_layer_invariant_fires_when_ARMS_has_a_rid_with_no_leg_line(tmp_path):
    """DIRECTION 1 — the D4 shape exactly: a rid in `ARMS.json` that no leg file
    enumerates is UNSCORABLE, and every one-directional check passes it."""
    banked, ext, out = _union_sides(tmp_path)
    leg = banked / f"positions_{PROFILE}_leg1.jsonl"
    lines = [ln for ln in leg.read_text().splitlines() if ln.strip()]
    victim = json.loads(lines[0])["rid"]
    leg.write_text("".join(ln + "\n" for ln in lines[1:]))       # ARMS keeps it
    with pytest.raises(UP.UnionError) as e:
        UP.assemble(banked, ext, out, stratum="s1")
    assert "CROSS-LAYER INVARIANT VIOLATED" in str(e.value)
    assert "NO leg line" in str(e.value) and victim in str(e.value)
    # and nothing half-assembled is left behind for a later reader to trust
    assert not (out / "ARMS.json").exists()


def test_cross_layer_invariant_fires_when_a_leg_line_is_not_in_ARMS(tmp_path):
    """DIRECTION 2 — a leg line for a rid the plan never committed. Checked
    because a set equality that only looks one way is not a set equality."""
    banked, ext, out = _union_sides(tmp_path)
    leg = ext / f"positions_{PROFILE}_leg1.jsonl"
    with open(leg, "a") as fh:
        fh.write(json.dumps({"rid": "tt_sp_999999999999_p9", "leg": 1}) + "\n")
    with pytest.raises(UP.UnionError) as e:
        UP.assemble(banked, ext, out, stratum="s1")
    assert "CROSS-LAYER INVARIANT VIOLATED" in str(e.value)
    assert "NOT in ARMS" in str(e.value)


def _rewrite_leg(corpus: Path, path: Path, lines) -> None:
    """Rewrite one leg file AND its plan count, so the tampering under test is
    the cross-layer one and not a line-count mismatch caught upstream."""
    path.write_text("".join(ln + "\n" for ln in lines))
    plan = json.loads((corpus / "POSITIONS_PLAN.json").read_text())
    for key, info in plan["files"].items():
        if Path(info["path"]).name == path.name:
            info["n"] = len(lines)
            plan.setdefault("counts_by_profile_leg", {})[key] = len(lines)
    (corpus / "POSITIONS_PLAN.json").write_text(json.dumps(plan, indent=1))


def _drop_rid_from_legs(corpus: Path, rid: str) -> None:
    """THE D4 SHAPE: the rid stays in ARMS.json, its leg lines vanish."""
    for p in corpus.glob("positions_*_leg*.jsonl"):
        keep = [ln for ln in p.read_text().splitlines()
                if ln.strip() and json.loads(ln)["rid"] != rid]
        _rewrite_leg(corpus, p, keep)


def test_stage_refuses_a_corpus_whose_leg_files_miss_a_committed_rid(tmp_path, corpus):
    """Re-checked at the CHUNK layer too: staging off a defective corpus would
    cut the wrong population into 8 pieces and every chunk would look fine."""
    victim = sorted(json.loads((corpus / "ARMS.json").read_text()))[0]
    _drop_rid_from_legs(corpus, victim)
    with pytest.raises(SystemExit) as e:
        SC.main(["stage", "--out-root", str(tmp_path / "campaign"),
                 "--s1-dir", str(corpus), "--stratum", "s1", "--chunks-s1", "4"])
    assert "CROSS-LAYER INVARIANT VIOLATED" in str(e.value)
    assert "NO leg line" in str(e.value) and victim in str(e.value)


def test_stage_refuses_a_corpus_with_a_leg_line_outside_ARMS(tmp_path, corpus):
    p = sorted(corpus.glob("positions_*_leg*.jsonl"))[0]
    lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
    lines.append(json.dumps({"rid": "tt_sp_000000000001_p0", "leg": 1}))
    _rewrite_leg(corpus, p, lines)
    with pytest.raises(SystemExit) as e:
        SC.main(["stage", "--out-root", str(tmp_path / "campaign"),
                 "--s1-dir", str(corpus), "--stratum", "s1", "--chunks-s1", "4"])
    assert "CROSS-LAYER INVARIANT VIOLATED" in str(e.value)
    assert "NOT in ARMS" in str(e.value)


def test_stage_summary_records_the_cross_layer_invariant(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    inv = json.loads((out_root / "CHUNK_SUMMARY.json").read_text())
    inv = inv["strata"]["s1"]["cross_layer_invariant"]
    assert inv["ok"] is True and inv["both_directions_checked"] is True
    assert inv["n_arms"] == inv["n_leg"] == 24


# --------------------------------------------------------------------------- #
# (e) CORPUS_UNION.json — reissued with a leg-layer witness, old file PRESERVED #
# --------------------------------------------------------------------------- #
def test_corpus_union_reissue_preserves_the_defective_stamp(tmp_path):
    """D4.7: *never silently overwrite* — the false assertion is EVIDENCE of the
    defect and must remain readable."""
    banked, ext, out = _union_sides(tmp_path)
    stamp = out.parent / UP.UNION_STAMP
    stamp.parent.mkdir(parents=True, exist_ok=True)
    old = {"schema": "carcassonne-tiearb-widening-corpus-union/v1",
           "by_stratum": {"S1": {"n_retained": 551, "n_fresh": 793,
                                 "copied_not_symlinked": True}},
           "totals": {"n_retained": 551, "n_fresh": 793, "n_total": 1344}}
    stamp.write_text(json.dumps(old, indent=2, sort_keys=True))

    UP.assemble(banked, ext, out, stratum="s1")

    archived = out.parent / UP.DEFECTIVE_STAMP
    assert archived.is_file(), "the pre-fix stamp must be preserved by rename"
    assert json.loads(archived.read_text()) == old, "preserved VERBATIM"
    doc = json.loads(stamp.read_text())
    assert doc["schema"] == UP.UNION_SCHEMA
    assert doc["superseded_file"]["path"] == str(archived)
    assert doc["by_stratum"]["S1"]["leg_layer"]["witnessed"] is True
    assert doc["by_stratum"]["S1"]["leg_layer"]["set_equality"]["ok"] is True
    assert doc["by_stratum"]["S1"]["n_retained"] == 6      # the REISSUED numbers


def test_a_second_stratum_does_not_archive_a_witnessed_stamp(tmp_path):
    """The rename triggers on a PRE-FIX stamp, not on every write: S1 and S2 are
    separate invocations and must still ACCUMULATE into one file."""
    b1, e1, o1 = _union_sides(tmp_path)
    UP.assemble(b1, e1, o1, stratum="s1")
    b2 = tmp_path / "shared_run" / "corpus" / "positions_s2"
    e2 = tmp_path / "shared_run_r4" / "corpus" / "positions_s2_ext"
    o2 = tmp_path / "shared_run_r4" / "corpus" / "positions_s2"
    WF.make_r4_corpus(b2, n_base=3, n_ext=0, seed=311, base_lo=135000000350)
    WF.make_r4_corpus(e2, n_base=0, n_ext=2, seed=312, ext_lo=137000000508)
    UP.assemble(b2, e2, o2, stratum="s2")
    assert not (o1.parent / UP.DEFECTIVE_STAMP).exists()
    doc = json.loads((o1.parent / UP.UNION_STAMP).read_text())
    assert set(doc["by_stratum"]) == {"S1", "S2"}
    assert all(v["leg_layer"]["witnessed"] for v in doc["by_stratum"].values())


# --------------------------------------------------------------------------- #
# (b)/(c) COMPLETION STAGING — exactly `ARMS − already-scored`, deterministic   #
# --------------------------------------------------------------------------- #
def _score_chunks(out_root: Path, chunks, *, stratum="s1"):
    """Write record trees for `chunks` ONLY — the D4 situation in miniature."""
    recs = out_root / "records"
    for k in chunks:
        write_leg_output(recs / f"chunk{k}", SC.chunk_dir(out_root, stratum, k),
                         chunk_tag=f"chunk{k}")
    return recs


def _complete(out_root, corpus, *, chunks=2, stratum="s1", records=(), extra=()):
    argv = ["completion", "--out-root", str(out_root), f"--{stratum}-dir",
            str(corpus), "--stratum", stratum, "--chunks", str(chunks)]
    for r in records:
        argv += ["--records-root", str(r)]
    return SC.main(argv + list(extra))


def test_completion_stages_exactly_the_never_scored_rids(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    assert _complete(out_root, corpus, chunks=2, records=[recs]) == 0

    plan = json.loads((out_root / "COMPLETION_PLAN_s1.json").read_text())
    se = plan["set_equality"]
    assert se["ok"] is True and se["both_directions_checked"] is True
    assert se["n_expected"] == se["n_staged"] == 12
    assert se["n_missing_from_staged"] == se["n_extra_in_staged"] == 0
    assert se["n_overlap_with_scored"] == 0
    assert plan["remainder"]["n_arms"] == 24
    assert plan["remainder"]["n_scored_both_judges"] == 12

    order = json.loads((out_root / "POSITION_ORDER.json").read_text())
    committed = order["strata"]["s1"]["order"]
    scored = set(committed[:12])                     # chunks 1+2 of a 4-way cut
    staged = set()
    for w in plan["chunks"]:
        staged |= set(json.loads((Path(w["dir"]) / "ARMS.json").read_text()))
    assert staged == set(committed) - scored
    assert not (staged & scored), "a completion never re-stages a scored rid"
    assert [w["chunk"] for w in plan["chunks"]] == [5, 6]


def test_completion_set_equality_fires_in_BOTH_directions():
    """D4.2, verbatim: *any rid outside that set, in either direction, voids the
    completion.* Both differences are computed and both refuse."""
    want, scored = {"a", "b", "c"}, {"x", "y"}
    ok = SC.assert_completion_set_equality(want, want, scored)
    assert ok["ok"] is True and ok["both_directions_checked"] is True

    with pytest.raises(SystemExit) as e:            # DIRECTION 1: a rid dropped
        SC.assert_completion_set_equality({"a", "b"}, want, scored)
    assert "COMPLETION VOID" in str(e.value) and "NOT staged" in str(e.value)

    with pytest.raises(SystemExit) as e:            # DIRECTION 2: a rid added
        SC.assert_completion_set_equality(want | {"z"}, want, scored)
    assert "OUTSIDE the remainder" in str(e.value)

    with pytest.raises(SystemExit) as e:            # and never a re-score
        SC.assert_completion_set_equality(want | {"x"}, want | {"x"}, scored)
    assert "already-scored" in str(e.value)


def test_completion_refuses_a_record_tree_holding_a_rid_outside_ARMS(tmp_path, corpus):
    """The record tree and the committed corpus describing different populations
    is the D4 failure class itself — it may not be absorbed silently."""
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    stray = recs / "chunk1" / "tier1-greedy" / PROFILE / "leg1" / "records"
    (stray / "tt_sp_777777777777_p1.json").write_text("{}")
    other = recs / "chunk1" / "clair-puct" / PROFILE / "leg1" / "records"
    (other / "tt_sp_777777777777_p1.json").write_text("{}")
    with pytest.raises(SystemExit) as e:
        _complete(out_root, corpus, chunks=2, records=[recs])
    assert "not in ARMS.json" in str(e.value) and "VOIDS the completion" in str(e.value)


def test_completion_refuses_a_half_scored_rid(tmp_path, corpus):
    """One judge holding a record the other does not makes the remainder
    AMBIGUOUS — `G-CRN` joins the two judges per rid."""
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    victim = sorted((recs / "chunk1" / "clair-puct" / PROFILE / "leg1"
                     / "records").glob("*.json"))[0]
    victim.unlink()
    with pytest.raises(SystemExit) as e:
        _complete(out_root, corpus, chunks=2, records=[recs])
    assert "AMBIGUOUS" in str(e.value)


def test_completion_keeps_the_committed_order_and_never_reshuffles(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    _complete(out_root, corpus, chunks=2, records=[recs])
    st = json.loads((out_root / "POSITION_ORDER.json").read_text())["strata"]["s1"]
    remainder = [r for r in st["order"] if r not in set(st["order"][:12])]
    got = []
    for k in (5, 6):
        d = SC.chunk_dir(out_root, "s1", k)
        assert sorted(d.glob("positions_*_leg*.jsonl")), \
            "a supplementary chunk must carry its own leg files"
        got.append(set(json.loads((d / "ARMS.json").read_text())))
    # the two chunks are the SEQUENTIAL halves of the committed-order remainder
    assert got[0] == set(remainder[:6]) and got[1] == set(remainder[6:])
    plan = json.loads((out_root / "COMPLETION_PLAN_s1.json").read_text())
    assert plan["permutation_seed"] == SC.PERMUTATION_SEED == 20260817
    assert plan["position_order_sha256"] == st["sha256_order"]
    cp = json.loads((SC.chunk_dir(out_root, "s1", 5) / "POSITIONS_PLAN.json").read_text())
    assert cp["chunk"]["completion"]["tranche"] == "supplementary"
    assert cp["chunk"]["position_order_sha256"] == st["sha256_order"]


def test_completion_is_deterministic_and_leaves_scored_chunks_untouched(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    before = {p.relative_to(out_root): p.read_bytes()
              for k in (1, 2)
              for p in SC.chunk_dir(out_root, "s1", k).rglob("*") if p.is_file()}
    _complete(out_root, corpus, chunks=2, records=[recs])
    after = {p.relative_to(out_root): p.read_bytes()
             for k in (1, 2)
             for p in SC.chunk_dir(out_root, "s1", k).rglob("*") if p.is_file()}
    assert before == after, "already-scored chunks are NEVER rewritten"

    # an independent staging of the same corpus reproduces the same tranche
    other = stage(tmp_path / "second", corpus, chunks=4)
    recs2 = _score_chunks(other, (1, 2))
    _complete(other, corpus, chunks=2, records=[recs2])
    for k in (5, 6):
        a = (SC.chunk_dir(out_root, "s1", k) / "ARMS.json").read_text()
        b = (SC.chunk_dir(other, "s1", k) / "ARMS.json").read_text()
        assert a == b


def test_completion_never_overwrites_a_staged_chunk_dir(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    _complete(out_root, corpus, chunks=2, records=[recs])
    with pytest.raises(SystemExit) as e:                 # re-run, same indices
        _complete(out_root, corpus, chunks=2, records=[recs])
    assert "already exists" in str(e.value)


def test_completion_emits_a_two_box_allocation_in_ALLOCATION_conf_shape(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    _complete(out_root, corpus, chunks=4, records=[recs])
    plan = json.loads((out_root / "COMPLETION_PLAN_s1.json").read_text())
    a = plan["allocation"]
    chunks = a["chunks"]
    assert chunks == [5, 6, 7, 8]
    # the same SHAPE as ALLOCATION.conf: local takes ALL the ARB work plus an IF
    # prefix; the laptop takes the IF suffix and no ARB at all
    assert a["local_tier1_greedy"] == chunks
    assert a["laptop_tier1_greedy"] == []
    assert a["local_clair_puct"] + a["laptop_clair_puct"] == chunks
    assert set(a["local_clair_puct"]) & set(a["laptop_clair_puct"]) == set()
    # the arithmetic is DERIVED, not typed
    cap, cost = a["capacity"], a["cost"]
    assert cap["laptop_effective"] == pytest.approx(
        cap["w_eval_laptop"] * cap["laptop_rate"])
    assert cost["total_worker_hours"] == pytest.approx(
        cost["arb_worker_hours"] + cost["if_worker_hours"], abs=0.02)
    assert a["makespan_hours"] >= cost["ideal_makespan_hours"]

    conf = (out_root / "ALLOCATION_COMPLETION_s1.conf").read_text()
    for key in ("ALLOC_s1_local_tier1_greedy", "ALLOC_s1_local_clair_puct",
                "ALLOC_s1_laptop_side_tier1_greedy",
                "ALLOC_s1_laptop_side_clair_puct"):
        assert f"{key}=" in conf, key
    assert 'ALLOC_s1_laptop_side_tier1_greedy=""' in conf
    assert "ideal makespan" in conf and "TRANCHE MAKESPAN" in conf
    assert f'ALLOC_s1_local_tier1_greedy="{" ".join(str(k) for k in chunks)}"' in conf


def test_completion_rechecks_the_cross_layer_invariant_before_staging(tmp_path, corpus):
    """D4.3: the invariant is re-checked BEFORE the first supplementary leg —
    otherwise the fix documents a defect it does not prevent."""
    out_root = stage(tmp_path, corpus, chunks=4)
    recs = _score_chunks(out_root, (1, 2))
    _drop_rid_from_legs(corpus, sorted(json.loads(
        (corpus / "ARMS.json").read_text()))[0])
    with pytest.raises(SystemExit) as e:
        _complete(out_root, corpus, chunks=2, records=[recs])
    assert "CROSS-LAYER INVARIANT VIOLATED" in str(e.value)


def test_completion_refuses_when_nothing_has_been_scored(tmp_path, corpus):
    out_root = stage(tmp_path, corpus, chunks=4)
    empty = tmp_path / "empty_records"
    empty.mkdir()
    with pytest.raises(SystemExit) as e:
        _complete(out_root, corpus, chunks=2, records=[empty])
    assert "not a completion" in str(e.value)


# --------------------------------------------------------------------------- #
# (d) `execution` — D3 §D3.2's key-by-key classification                        #
# --------------------------------------------------------------------------- #
def _man_with_execution(execution: dict) -> dict:
    return {
        "schema": "carcassonne-tiletie-tier1-rust-leg/v1", "git_rev": "58c2b539",
        "judge": "clair-puct", "profile": PROFILE, "leg": 1,
        "n_rows_in": 10, "n_scored": 10, "execution": execution,
    }


BOX_LOCAL_A = {"carc_rs_binary_sha": "a4318fd5" * 8,
               "carc_rs_path": "/x/py3.12/site-packages/carc_rs.so",
               "carc_rs_build": "carc_rs-0.1.0+58c2b5395569+rustcunpinned"}
BOX_LOCAL_B = {"carc_rs_binary_sha": "8ae0b984" * 8,
               "carc_rs_path": "/y/py3.14/site-packages/carc_rs.so",
               "carc_rs_build": "carc_rs-0.1.0+58c2b5395569+rustcunpinned"}


def test_execution_box_local_keys_merge_PER_CHUNK_and_are_recorded():
    """D3 §D3.2: `carc_rs_binary_sha` (JCZ §0.F.2c — the .so is not
    machine-reproducible) and `carc_rs_path` are BOX-LOCAL. PER_CHUNK RECORDS
    them; nulling would discard them."""
    merged = ML.merge_manifests({1: _man_with_execution(dict(BOX_LOCAL_A)),
                                 2: _man_with_execution(dict(BOX_LOCAL_B))})
    ex = merged["execution"]
    assert ex["carc_rs_binary_sha"] == BOX_LOCAL_A["carc_rs_binary_sha"]
    assert ex["carc_rs_build"] == BOX_LOCAL_A["carc_rs_build"]
    by = merged["merge"]["by_chunk"]
    assert by["1"]["execution"]["carc_rs_binary_sha"] == BOX_LOCAL_A["carc_rs_binary_sha"]
    assert by["2"]["execution"]["carc_rs_binary_sha"] == BOX_LOCAL_B["carc_rs_binary_sha"]
    assert by["2"]["execution"]["carc_rs_path"] == BOX_LOCAL_B["carc_rs_path"]
    # the cross-host witness is NOT a per-chunk field
    assert "carc_rs_build" not in by["1"].get("execution", {})


def test_execution_carc_rs_build_is_IDENTITY_REQUIRED():
    """The one value inside `execution` that may legitimately be compared across
    hosts. If it ever differs the merge MUST raise — that is the property R4-7.5
    calls the important one, and blanket PER_CHUNK would have discarded it."""
    b = dict(BOX_LOCAL_B, carc_rs_build="carc_rs-0.1.0+deadbeef+rustcunpinned")
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _man_with_execution(dict(BOX_LOCAL_A)),
                            2: _man_with_execution(b)})
    assert "execution.carc_rs_build" in str(e.value)
    assert "DIVERGES" in str(e.value) and "CROSS-HOST WITNESS" in str(e.value)


def test_execution_keeps_the_fail_closed_raise_on_any_other_key():
    """ANY OTHER key inside `execution` keeps the RAISE default — and
    `--allow-varying` cannot silence it (D3 rejects it for this block)."""
    a = dict(BOX_LOCAL_A, rustc_version="1.80.0")
    b = dict(BOX_LOCAL_B, rustc_version="1.83.0")
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _man_with_execution(a), 2: _man_with_execution(b)},
                           allow_varying=["execution", "rustc_version"])
    assert "execution.rustc_version" in str(e.value)
    assert "UNCLASSIFIED" in str(e.value)


def test_execution_missing_on_one_chunk_still_raises():
    with pytest.raises(ML.MergeError):
        ML.merge_manifests({1: _man_with_execution(dict(BOX_LOCAL_A)),
                            2: _man_with_execution(
                                {k: v for k, v in BOX_LOCAL_B.items()
                                 if k != "carc_rs_build"})})


def test_a_real_two_box_leg_merges_with_the_observed_execution_pair(tmp_path, corpus):
    """End to end: the observed local/laptop pair (differing sha + path, equal
    build) merges clean and the merged tree stays complete."""
    out_root = stage(tmp_path, corpus, chunks=2)
    share = tmp_path / "share" / "chunks" / "s1"
    for k, ex in ((1, BOX_LOCAL_A), (2, BOX_LOCAL_B)):
        write_leg_output(share / f"chunk{k}", SC.chunk_dir(out_root, "s1", k),
                         chunk_tag=f"chunk{k}", box=("local" if k == 1 else "laptop"))
        for man in (share / f"chunk{k}").rglob("manifest.json"):
            d = json.loads(man.read_text())
            d["execution"] = dict(ex)
            man.write_text(json.dumps(d, indent=2, sort_keys=True))
    rep = ML.merge_stratum(stratum="s1", chunks_root=share,
                           out_dir=tmp_path / "share" / "s1",
                           positions_dir=corpus)
    assert rep["ok"] is True, rep["problems"]
    assert all(leg["manifest_ok"] for leg in rep["legs"].values())
    man = json.loads(((tmp_path / "share" / "s1" / "clair-puct" / PROFILE
                       / "leg1" / "manifest.json")).read_text())
    assert man["execution"]["carc_rs_build"] == BOX_LOCAL_A["carc_rs_build"]
    assert (man["merge"]["by_chunk"]["2"]["execution"]["carc_rs_binary_sha"]
            == BOX_LOCAL_B["carc_rs_binary_sha"])


# =========================================================================== #
# 9. D4.11 / D4.12 — the TWO-REV tranche licence (`93f83e26`)                  #
#                                                                             #
# The committed tranche (chunks 1-8) scored at 58c2b539; the completion        #
# tranche (chunks 9-16) scores at 4b24f512 — necessarily, since the staging    #
# code did not exist at the older rev. The licence is an ENUMERATED pair in    #
# code PLUS an instrument witness whose diff this layer RE-DERIVES.            #
# =========================================================================== #
import subprocess                                                  # noqa: E402

import instrument_identity as II                                   # noqa: E402


def _run_git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def _instrument_repo(tmp_path, name="repo"):
    """A repo carrying every instrument path, with TWO commits whose diff over
    those paths is empty (only a doc moved) — the real situation."""
    r = tmp_path / name
    for p in ML.INSTRUMENT_PATHS:
        q = r / p
        if p.endswith("/"):
            q.mkdir(parents=True, exist_ok=True)
            (q / "keep.py").write_text("x = 1\n")
        else:
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_text("# instrument\n")
    (r / "docs").mkdir(parents=True, exist_ok=True)
    (r / "docs" / "note.md").write_text("a\n")
    _run_git(r.parent, "init", "-q", str(r))
    _run_git(r, "config", "user.email", "t@example.com")
    _run_git(r, "config", "user.name", "t")
    _run_git(r, "add", "-A")
    _run_git(r, "commit", "-qm", "instrument at rev A")
    a = _run_git(r, "rev-parse", "HEAD")
    (r / "docs" / "note.md").write_text("b\n")          # NOT an instrument path
    _run_git(r, "add", "-A")
    _run_git(r, "commit", "-qm", "docs only -> rev B")
    b = _run_git(r, "rev-parse", "HEAD")
    return r, a, b


def _instrument_moved(repo):
    """A third commit that DOES touch the instrument — the diff must not be
    empty against it."""
    p = Path(repo) / "scripts" / "measurement_infra" / "oracle_score_pilot.py"
    p.write_text("# instrument CHANGED\n")
    _run_git(repo, "add", "-A")
    _run_git(repo, "commit", "-qm", "instrument moved -> rev C")
    return _run_git(repo, "rev-parse", "HEAD")


def _license(repo, a, b, *, identity_path=None, git_clean_by_chunk=None):
    return ML.RevLicense(repo=repo, identity_path=identity_path,
                         git_clean_by_chunk=git_clean_by_chunk,
                         revs={"committed_tranche": a, "completion_tranche": b})


def _witness(repo, a, b, out, *, boxes=(("local", None),)):
    doc = II.build(repo, boxes=boxes,
                   revs={"committed_tranche": a, "completion_tranche": b})
    Path(out).write_text(json.dumps(doc, indent=2, sort_keys=True))
    return doc


def _rev_manifest(rev, *, judge="clair-puct", git_clean=True, build_rev=None):
    """A leg manifest in the real shape: the rev appears under FOUR spellings.

    `carc_rs_build` is held EQUAL by default so these tests isolate the rev
    licence; `build_rev` reproduces the real cross-tranche shape, which is the
    ⛔ UNRULED blocker exercised below.
    """
    build = ("carc_rs-0.1.0+000000000000+rustcunpinned" if build_rev is None
             else f"carc_rs-0.1.0+{build_rev[:12]}+rustcunpinned")
    man = {
        "schema": "carcassonne-tiletie-oracle-leg/v1", "judge": judge,
        "profile": PROFILE, "leg": 1, "m_worlds": 128,
        "n_rows_in": 10, "n_scored": 10, "n_ok": 10, "n_failed": 0,
        "code_rev": rev[:8],                                  # short
        "git_rev": rev,                                       # full
        "execution": {
            "carc_rs_binary_sha": "a4318fd59d9d8349",
            "carc_rs_path": "/x/py3.12/site-packages/carc_rs.so",
            "carc_rs_build": build,
            "code_rev": f"{rev[:8]}-dirty",                   # the D4.12 form
            "code_rev_dirty": True,
        },
        "champion_manifest": {"schema": "carcassonne-champion-factory/v1",
                              "mode": "clairvoyant",
                              "code_commit": rev},            # full, third place
    }
    if git_clean is not None:
        man["preflight"] = {"checks": {"git_clean": {"ok": bool(git_clean),
                                                     "dirty_paths": []}}}
    return man


@pytest.fixture()
def two_rev(tmp_path):
    repo, a, b = _instrument_repo(tmp_path)
    wit = tmp_path / "INSTRUMENT_IDENTITY.json"
    _witness(repo, a, b, wit)
    return repo, a, b, wit


# --- the licensed path ------------------------------------------------------- #
def test_two_rev_merge_is_licensed_with_pair_witness_and_empty_diff(two_rev):
    """All four spellings of the rev — `git_rev`, `code_rev`,
    `execution.code_rev` (the `-dirty` one) and `champion_manifest.code_commit`
    — merge under the enumerated licence, and every one is RECORDED per chunk."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    merged = ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)},
                                license=lic)
    rl = merged["merge"]["rev_license"]
    assert set(rl["paths"]) == set(ML.REV_LICENSED_PATHS)
    by = merged["merge"]["by_chunk"]
    assert by["1"]["git_rev"] == a and by["9"]["git_rev"] == b
    assert by["1"]["code_rev"] == a[:8] and by["9"]["code_rev"] == b[:8]
    assert by["9"]["execution"]["code_rev"] == f"{b[:8]}-dirty"
    assert by["9"]["champion_manifest"]["code_commit"] == b
    # the merged doc keeps the lowest chunk's value — a real string, never null
    assert merged["git_rev"] == a and merged["code_rev"] == a[:8]
    # ⭐ the diff was RE-DERIVED here, not read out of the witness
    rec = rl["records"][0]["instrument_identity"]
    assert rec["rederived"]["empty"] is True
    assert rec["rederived"]["n_files_changed"] == 0
    assert rec["rederived"]["paths"] == list(ML.INSTRUMENT_PATHS)
    assert rec["sha256"] == ML._sha256_file(wit)


def test_the_dirty_suffix_is_matched_on_the_BASE_rev(two_rev):
    """D4.12: `58c2b539-dirty` and `58c2b539` are the same rev. Exact-string
    matching would refuse a healthy chunk that recorded a clean value."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    assert lic.tranche_of(a) == "committed_tranche"
    assert lic.tranche_of(a[:8]) == "committed_tranche"
    assert lic.tranche_of(f"{a[:8]}-dirty") == "committed_tranche"
    assert lic.tranche_of(f"{b[:12]}-dirty") == "completion_tranche"
    assert lic.tranche_of("deadbeefdeadbeef") is None
    assert lic.tranche_of(a[:4]) is None, "4 hex chars is not evidence of a rev"
    # and a mixed clean/dirty pair still merges
    clean_a = _rev_manifest(a)
    clean_a["execution"]["code_rev"] = a[:8]          # no suffix
    clean_a["execution"]["code_rev_dirty"] = False
    dirty_b = _rev_manifest(b)
    dirty_b["execution"]["code_rev_dirty"] = False    # keep the bool identical
    merged = ML.merge_manifests({1: clean_a, 9: dirty_b}, license=lic)
    assert merged["merge"]["rev_license"]["records"]


# --- every way the licence refuses ------------------------------------------- #
def test_a_third_rev_refuses(two_rev):
    """The licence is a CLOSED enumeration: two revs, no more."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    third = "0" * 40
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b),
                            11: _rev_manifest(third)}, license=lic)
    assert "NOT in the enumerated licence" in str(e.value)
    assert "still refuses" in str(e.value)


def test_an_unlicensed_rev_pair_refuses(two_rev):
    """Neither member enumerated — the default IDENTITY_REQUIRED behaviour."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    x, y = "1" * 40, "2" * 40
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(x), 9: _rev_manifest(y)}, license=lic)
    assert "NOT in the enumerated licence" in str(e.value)


def test_the_licence_refuses_when_the_witness_is_ABSENT(tmp_path):
    """D4.11 Amendment 1: the code holds the pair AND the witness must exist —
    BOTH, or refuse. A hard-coded pair alone asserts nothing about WHY it is
    safe."""
    repo, a, b = _instrument_repo(tmp_path)
    lic = _license(repo, a, b, identity_path=tmp_path / "nope.json")
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)}, license=lic)
    assert ML.INSTRUMENT_IDENTITY_NAME in str(e.value) and "ABSENT" in str(e.value)


def test_the_licence_refuses_when_the_REDERIVED_diff_is_not_empty(tmp_path):
    """⭐ The file is the WHY; the re-derivation is the PROOF. A witness that
    claims an empty diff over revs whose instrument actually moved is refused by
    `git diff`, not by trust."""
    repo, a, b = _instrument_repo(tmp_path)
    c = _instrument_moved(repo)
    wit = tmp_path / "INSTRUMENT_IDENTITY.json"
    doc = II.build(repo, revs={"committed_tranche": a, "completion_tranche": b})
    # a HAND-EDITED witness: the revs now say a..c, the claim still says empty
    doc["revs"]["completion_tranche"]["sha"] = c
    doc["committed_diff"]["rev_b"] = c
    wit.write_text(json.dumps(doc, indent=2, sort_keys=True))
    lic = _license(repo, a, c, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(c)}, license=lic)
    assert "RE-DERIVED INSTRUMENT DIFF IS NOT EMPTY" in str(e.value)
    assert "oracle_score_pilot.py" in str(e.value)


def test_the_licence_refuses_a_witness_naming_a_different_pair(two_rev, tmp_path):
    repo, a, b, wit = two_rev
    doc = json.loads(wit.read_text())
    doc["revs"]["completion_tranche"]["sha"] = "f" * 40
    wit.write_text(json.dumps(doc))
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)}, license=lic)
    assert "code-resident licence enumerates" in str(e.value)


def test_the_licence_refuses_the_VACUOUS_instrument_path_list(two_rev):
    """D4.11 Amendment 2 — the misspelled `scripts/tiletie/oracle_score_pilot.py`
    does not exist, so a witness over it is vacuously true and leaves the file
    that runs 93% of the cost unwitnessed."""
    repo, a, b, wit = two_rev
    doc = json.loads(wit.read_text())
    doc["instrument_paths"] = [p.replace("scripts/measurement_infra/",
                                         "scripts/tiletie/")
                               for p in doc["instrument_paths"]]
    wit.write_text(json.dumps(doc))
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)}, license=lic)
    assert "VACUOUSLY TRUE" in str(e.value)
    assert "scripts/measurement_infra/oracle_score_pilot.py" in str(e.value)


def test_the_licence_refuses_a_dirty_working_tree_on_any_box(two_rev):
    """Amendment 3: `git diff A..B` is blind to uncommitted dirt, so the
    porcelain capture is load-bearing — and a dirty box refuses."""
    repo, a, b, wit = two_rev
    doc = json.loads(wit.read_text())
    doc["working_tree"]["by_box"]["laptop"] = {
        "box": "laptop", "host": "laptop-wsl", "clean": False,
        "porcelain": " M scripts/tiletie/run_tiletie.py", "n_entries": 1}
    wit.write_text(json.dumps(doc))
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)}, license=lic)
    assert "working tree NOT clean" in str(e.value) and "laptop" in str(e.value)


def test_the_licence_refuses_a_witness_with_no_box_captured(two_rev):
    repo, a, b, wit = two_rev
    doc = json.loads(wit.read_text())
    doc["working_tree"]["by_box"] = {}
    wit.write_text(json.dumps(doc))
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)}, license=lic)
    assert "by_box is empty" in str(e.value)


# --- D4.12's per-chunk clean assertion ---------------------------------------- #
def test_git_clean_ok_false_refuses_regardless_of_rev(two_rev):
    """*A chunk with `git_clean.ok` false refuses regardless of rev* — the
    suffix only gestures at what this assertion checks."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a),
                            9: _rev_manifest(b, git_clean=False)}, license=lic)
    assert "git_clean.ok == true" in str(e.value) and "chunk9" in str(e.value)


def test_git_clean_missing_everywhere_refuses(two_rev):
    """The per-LEG manifests do not carry `preflight.checks`; with no per-chunk
    RUN_MANIFEST map either, the evidence simply is not there — and absent
    evidence is a refusal, never a pass."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a, git_clean=None),
                            9: _rev_manifest(b, git_clean=None)}, license=lic)
    assert "git_clean.ok == true" in str(e.value)


def test_git_clean_comes_from_the_RUN_MANIFEST_map_for_leg_manifests(two_rev):
    """The real per-leg manifests have no `preflight.checks`, so the evidence is
    sourced from the per-chunk RUN_MANIFEST files — which do."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit,
                   git_clean_by_chunk={1: {"ok": True}, 9: {"ok": True}})
    merged = ML.merge_manifests({1: _rev_manifest(a, git_clean=None),
                                 9: _rev_manifest(b, git_clean=None)}, license=lic)
    rec = merged["merge"]["rev_license"]["records"][0]
    assert rec["git_clean_by_chunk"]["9"]["source"] == "RUN_MANIFEST"
    # ... and a false entry in the map refuses just the same
    lic2 = _license(repo, a, b, identity_path=wit,
                    git_clean_by_chunk={1: {"ok": True}, 9: {"ok": False}})
    with pytest.raises(ML.MergeError):
        ML.merge_manifests({1: _rev_manifest(a, git_clean=None),
                            9: _rev_manifest(b, git_clean=None)}, license=lic2)


def test_git_clean_map_is_read_from_real_RUN_MANIFEST_files(tmp_path):
    d = tmp_path / "manifests"
    d.mkdir()
    for judge, ok in (("tier1-greedy", True), ("clair-puct", True)):
        (d / f"RUN_MANIFEST_S1_{judge}_chunk9.json").write_text(json.dumps(
            {"preflight": {"checks": {"git_clean": {"ok": ok, "dirty_paths": []}}}}))
    (d / "RUN_MANIFEST_S1_clair-puct_chunk10.json").write_text(json.dumps(
        {"preflight": {"checks": {"git_clean": {"ok": False,
                                                "dirty_paths": ["src/x.py"]}}}}))
    m = ML.git_clean_by_chunk_from_manifests(d, "s1")
    assert m[9]["ok"] is True and len(m[9]["sources"]) == 2
    assert m[10]["ok"] is False and m[10]["dirty_paths"] == ["src/x.py"]


# --- the licence does not leak ------------------------------------------------ #
def test_an_unenumerated_key_holding_a_licensed_sha_still_refuses(two_rev):
    """The licence is keyed on ADDRESSES as well as values: a licensed sha
    appearing somewhere nobody ruled on is still an unclassified divergence."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    ma, mb = _rev_manifest(a), _rev_manifest(b)
    ma["harness"], mb["harness"] = a, b            # not an enumerated address
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: ma, 9: mb}, license=lic)
    assert "'harness'" in str(e.value) and "DIVERGES" in str(e.value)


def test_without_a_licence_object_the_default_refusal_is_unchanged(two_rev):
    """The licence is opt-in at the call site; nothing about the default path
    moved."""
    repo, a, b, wit = two_rev
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)})
    assert "DIVERGES across chunks" in str(e.value)


def test_same_rev_chunks_never_consult_the_licence(tmp_path):
    """INERT UNLESS A REV DIVERGES: no witness, no git, no cost — a single-rev
    merge behaves exactly as before."""
    repo, a, b = _instrument_repo(tmp_path)
    lic = _license(repo, a, b, identity_path=tmp_path / "does_not_exist.json")
    merged = ML.merge_manifests({1: _rev_manifest(a), 2: _rev_manifest(a)},
                                license=lic)
    assert "rev_license" not in merged["merge"]
    assert merged["git_rev"] == a


# =========================================================================== #
# 10. §D4.13 — `carc_rs_build` across tranches, under FOUR conjuncts           #
#                                                                             #
# The field stamps `git rev-parse HEAD` AT PROCESS START, so it is the         #
# CROSS-HOST SOURCE-REV witness; `carc_rs_binary_sha` is the WITHIN-BOX        #
# STALENESS witness. Across tranches HEAD moved and the stamp followed — the   #
# `.so` was not rebuilt, and conjunct (ii) ASSERTS that rather than assuming.  #
# =========================================================================== #
LOCAL_SHA = "a4318fd59d9d8349"        # the real local wheel
LAPTOP_SHA = "8ae0b98427debb2e"       # the real laptop wheel


def _build(rev, *, version="carc_rs-0.1.0", toolchain="rustcunpinned"):
    return f"{version}+{rev[:12]}+{toolchain}"


def _exec_manifest(rev, *, host="Doctor", binary_sha=LOCAL_SHA, build=None,
                   py="python3.12"):
    """A clair-puct-shaped leg manifest: `execution.carc_rs_build` + the
    box-local sha and path."""
    return {
        "schema": "carcassonne-tiletie-oracle-leg/v1", "judge": "clair-puct",
        "profile": PROFILE, "leg": 1, "host": host,
        "n_rows_in": 10, "n_scored": 10,
        "code_rev": rev[:8],
        "preflight": {"checks": {"git_clean": {"ok": True, "dirty_paths": []}}},
        "execution": {
            "carc_rs_binary_sha": binary_sha,
            "carc_rs_path": f"/home/doctor/.venv/lib/{py}/site-packages/carc_rs.so",
            "carc_rs_build": build or _build(rev),
            "code_rev": f"{rev[:8]}-dirty", "code_rev_dirty": True,
        },
    }


def _wheel_manifest(rev, *, binary_sha=LOCAL_SHA, build=None,
                    out_root="/mnt/c/carc-shared/x/chunk1", py="python3.12"):
    """A tier1-greedy-shaped leg manifest: the SECOND address,
    `preflight.wheel.carc_rs_build`. These legs are ALL-LOCAL — single host."""
    return {
        "schema": "carcassonne-tiletie-tier1-rust-leg/v1", "judge": "tier1-greedy",
        "profile": PROFILE, "leg": 1, "git_rev": rev,
        "n_rows_in": 10, "n_scored": 10,
        "resolved_config": {"out_root": out_root},
        "preflight": {
            "seeds": {"ok": True},
            "wheel": {"ok": True, "carc_rs_version": "0.1.0",
                      "carc_rs_binary_sha": binary_sha,
                      "carc_rs_build": build or _build(rev),
                      "carc_rs_file": f"/home/doctor/.venv/lib/{py}/site-packages/carc_rs/__init__.py"},
        },
    }


def test_the_real_observed_pair_merges_under_the_four_conjuncts(tmp_path):
    """⭐ THE REAL SHAPE, end to end against the REAL repo: build fragments
    58c2b5395569 / 4b24f512a083, per-box shas constant across both tranches
    (local a4318fd5…, laptop 8ae0b984…)."""
    real = ML.REPO
    porcelain = subprocess.run(
        ["git", "-C", str(real), "status", "--porcelain", "--", *ML.INSTRUMENT_PATHS],
        capture_output=True, text=True)
    if porcelain.stdout.strip():
        pytest.skip("instrument paths are dirty in this checkout — the witness "
                    "would (correctly) refuse; nothing about the licence to test")
    wit = tmp_path / ML.INSTRUMENT_IDENTITY_NAME
    wit.write_text(json.dumps(II.build(real), indent=2, sort_keys=True))
    A = ML.LICENSED_TRANCHE_REVS["committed_tranche"]
    B = ML.LICENSED_TRANCHE_REVS["completion_tranche"]
    lic = ML.RevLicense(repo=real, identity_path=wit,
                        git_clean_by_chunk={1: {"ok": True}, 9: {"ok": True},
                                            14: {"ok": True}})

    # (a) the clair-puct leg — TWO hosts, so conjunct (iv) is really tested
    merged = ML.merge_manifests({
        1: _exec_manifest(A, host="Doctor", binary_sha=LOCAL_SHA),
        9: _exec_manifest(B, host="Doctor", binary_sha=LOCAL_SHA),
        14: _exec_manifest(B, host="laptop-wsl", binary_sha=LAPTOP_SHA,
                           py="python3.14"),
    }, license=lic)
    rec = [r for r in merged["merge"]["rev_license"]["records"]
           if r["path"] == "execution.carc_rs_build"][0]
    c = rec["conjuncts"]
    assert c["i_only_rev_fragment_differs"]["compared_at_width"] == 12
    assert set(c["i_only_rev_fragment_differs"]["rev_fragments"].values()) == \
        {A[:12], B[:12]} == {"58c2b5395569", "4b24f512a083"}
    assert c["ii_binary_sha_constant_within_box"]["ok"] is True
    assert c["ii_binary_sha_constant_within_box"]["n_boxes"] == 2
    assert c["iii_instrument_identity_rust_scope"]["ok"] is True
    iv = c["iv_within_tranche_cross_host_build_equality"]
    assert iv["committed_tranche"]["status"] == "VACUOUS"      # chunk 1 only
    assert iv["completion_tranche"]["status"] == "PASSED"      # chunks 9 + 14
    assert iv["completion_tranche"]["n_boxes"] == 2
    # the box-local shas were never compared across hosts
    by_box = c["ii_binary_sha_constant_within_box"]["by_box"]
    assert {v["sha"] for v in by_box.values()} == {LOCAL_SHA, LAPTOP_SHA}

    # (b) the tier1 leg — SINGLE host, so (iv) must read VACUOUS, never passed
    merged2 = ML.merge_manifests({1: _wheel_manifest(A), 9: _wheel_manifest(B)},
                                 license=lic)
    rec2 = [r for r in merged2["merge"]["rev_license"]["records"]
            if r["path"] == "preflight.wheel.carc_rs_build"][0]
    iv2 = rec2["conjuncts"]["iv_within_tranche_cross_host_build_equality"]
    assert {v["status"] for v in iv2.values()} == {"VACUOUS"}
    assert all("carries the whole weight" in v["why"] for v in iv2.values())
    assert rec2["conjuncts"]["ii_binary_sha_constant_within_box"]["ok"] is True


def test_R1_an_unlicensed_rev_fragment(two_rev):
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _exec_manifest(a),
                            9: _exec_manifest(b, build=_build("dead" * 3))},
                           license=lic)
    msg = str(e.value)
    assert msg.startswith(ML.R1)
    assert "deaddeaddead" in msg and "parsed[version=" in msg
    assert a[:12] in msg or b[:12] in msg          # the licensed pair is printed


def test_R1_the_WIDTH_TRAP_7_char_collision_still_refuses(two_rev):
    """⚠️ Same sha, three widths. A fragment that matches a licensed rev at the
    `code_rev` SHORT width but differs at the fixed 12-char slice must REFUSE —
    reusing the 7-char comparison here is the spelling failure the ruling
    called out."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    flip = "0" if b[7] != "0" else "1"
    collide = b[:7] + flip + b[8:12]               # 12 chars, 7-char collision
    assert collide[:7] == b[:7] and collide != b[:12]
    assert ML.build_rev_is_licensed(collide, lic.revs) is None
    # ... and the loose short-form matcher WOULD have accepted the 7-char prefix,
    # which is exactly why the two comparisons must not be shared
    assert lic.tranche_of(b[:8]) == "completion_tranche"
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _exec_manifest(a),
                            9: _exec_manifest(b, build=_build(collide))},
                           license=lic)
    assert str(e.value).startswith(ML.R1)
    assert "core.abbrev" in str(e.value) or "per-box" in str(e.value)
    # a fragment SHORTER than 12 is not a licensed fragment either
    assert ML.build_rev_is_licensed(b[:8], lic.revs) is None


def test_R2_binary_sha_moved_within_a_box(two_rev):
    """The `.so` changed under one box between the tranches."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _exec_manifest(a, binary_sha=LOCAL_SHA),
                            9: _exec_manifest(b, binary_sha="ffffffffffffffff")},
                           license=lic)
    msg = str(e.value)
    assert msg.startswith(ML.R2)
    assert LOCAL_SHA in msg and "ffffffffffffffff" in msg
    assert "chunks[1]" in msg and "chunks[9]" in msg
    assert ML.R2_MEANING in msg, "the meaning must be printed VERBATIM"


def test_R2_is_a_STANDING_requirement_even_at_a_SINGLE_rev(tmp_path):
    """⭐ THE HOLE D3 LEFT OPEN. At one rev the stamp cannot move, so
    `carc_rs_build` sees nothing — but the `.so` can still be rebuilt underneath.
    No licence, no witness, one rev: it still refuses."""
    a = "1" * 40
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _exec_manifest(a, binary_sha=LOCAL_SHA),
                            2: _exec_manifest(a, binary_sha="0123456789abcdef")})
    assert str(e.value).startswith(ML.R2)
    assert ML.R2_MEANING in str(e.value)
    assert "STANDING requirement" in str(e.value)
    # the same at the tier1 address, and with the licence absent entirely
    with pytest.raises(ML.MergeError) as e2:
        ML.merge_manifests({1: _wheel_manifest(a, binary_sha=LOCAL_SHA),
                            2: _wheel_manifest(a, binary_sha="0123456789abcdef")})
    assert str(e2.value).startswith(ML.R2)


def test_a_healthy_two_box_single_rev_merge_records_the_standing_check(tmp_path):
    """Two boxes with DIFFERENT shas is normal and must never refuse — the shas
    are compared within a host only (JCZ §0.F.2c)."""
    a = "1" * 40
    merged = ML.merge_manifests({
        1: _exec_manifest(a, host="Doctor", binary_sha=LOCAL_SHA),
        2: _exec_manifest(a, host="laptop-wsl", binary_sha=LAPTOP_SHA,
                          py="python3.14")})
    b = merged["merge"]["binary_sha_within_box"]
    assert b["ok"] is True and b["standing_requirement"] is True
    assert b["n_boxes"] == 2
    assert {v["sha"] for v in b["by_box"].values()} == {LOCAL_SHA, LAPTOP_SHA}
    assert "never across" in b["note"]


def test_R2_refuses_when_the_box_cannot_be_determined():
    """A sha with no derivable box cannot be pooled: pooling two boxes would read
    a legitimate cross-host difference as a rebuild."""
    a = "1" * 40
    m1 = {"schema": "x", "execution": {"carc_rs_binary_sha": LOCAL_SHA}}
    m2 = {"schema": "x", "execution": {"carc_rs_binary_sha": LAPTOP_SHA}}
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: m1, 2: m2})
    assert str(e.value).startswith(ML.R2) and "cannot be determined" in str(e.value)


def test_R3_version_or_toolchain_divergence_is_never_licensed(two_rev):
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    for build in (_build(b, version="carc_rs-9.9.9"),
                  _build(b, toolchain="rustc1.83.0")):
        with pytest.raises(ML.MergeError) as e:
            ML.merge_manifests({1: _exec_manifest(a),
                                9: _exec_manifest(b, build=build)}, license=lic)
        assert str(e.value).startswith(ML.R3)
        assert "NEVER licensed" in str(e.value)
        assert "version=" in str(e.value) and "toolchain=" in str(e.value)


def test_R3_within_tranche_cross_host_inequality(two_rev):
    """Two boxes at the SAME rev must stamp the same build — D3's original
    check, preserved intact by conjunct (iv)."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit,
                   git_clean_by_chunk={k: {"ok": True} for k in (1, 9, 14)})
    bad = _exec_manifest(b, host="laptop-wsl", binary_sha=LAPTOP_SHA,
                         py="python3.14")
    bad["execution"]["carc_rs_build"] = _build(a)      # wrong rev for its tranche
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _exec_manifest(a), 9: _exec_manifest(b),
                            14: bad}, license=lic)
    assert str(e.value).startswith(ML.R3)
    assert "ACROSS BOXES" in str(e.value)


def test_R4_instrument_identity_must_cover_rust(two_rev):
    """Conjunct (iii): this licence is about the COMPILED half, so a witness
    blind to `rust/` cannot support it — in the diff scope OR the porcelain."""
    repo, a, b, wit = two_rev
    # (1) rust/ dropped from the path list
    doc = json.loads(wit.read_text())
    doc["instrument_paths"] = [p for p in doc["instrument_paths"] if p != "rust/"]
    wit.write_text(json.dumps(doc))
    lic = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _exec_manifest(a), 9: _exec_manifest(b)},
                           license=lic)
    # the path-list check fires first (the witness is invalid before it is used)
    assert "instrument_paths" in str(e.value) or str(e.value).startswith(ML.R4)

    # (2) rust/ present but DIRTY in the porcelain
    doc = II.build(repo, revs={"committed_tranche": a, "completion_tranche": b})
    doc["working_tree"]["by_box"]["local"]["porcelain"] = " M rust/carc_rs/src/lib.rs"
    doc["working_tree"]["by_box"]["local"]["n_entries"] = 1
    wit.write_text(json.dumps(doc))
    lic2 = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e2:
        ML.merge_manifests({1: _exec_manifest(a), 9: _exec_manifest(b)},
                           license=lic2)
    # `clean` is False-by-porcelain: the witness gate names the dirty box
    assert "NOT clean" in str(e2.value) or str(e2.value).startswith(ML.R4)

    # (3) rust/ dropped from the PORCELAIN SCOPE only — R4 exactly
    doc = II.build(repo, revs={"committed_tranche": a, "completion_tranche": b})
    doc["working_tree"]["by_box"]["local"]["scope"] = [
        p for p in doc["working_tree"]["by_box"]["local"]["scope"] if p != "rust/"]
    wit.write_text(json.dumps(doc))
    lic3 = _license(repo, a, b, identity_path=wit)
    with pytest.raises(ML.MergeError) as e3:
        ML.merge_manifests({1: _exec_manifest(a), 9: _exec_manifest(b)},
                           license=lic3)
    assert str(e3.value).startswith(ML.R4)
    assert "porcelain scope omits" in str(e3.value)


def test_the_four_refusal_codes_are_distinct_and_spelled_as_ruled():
    for code, tail in ((ML.R1, "CARC_RS_BUILD_UNLICENSED_REV"),
                       (ML.R2, "CARC_RS_BINARY_SHA_MOVED_WITHIN_BOX"),
                       (ML.R3, "CARC_RS_BUILD_VERSION_OR_TOOLCHAIN_DIFFERS"),
                       (ML.R4, "INSTRUMENT_IDENTITY_RUST_SCOPE")):
        assert code.split(" ", 1)[1] == tail
    assert len({ML.R1, ML.R2, ML.R3, ML.R4}) == 4
    assert "the `.so` that executed tranche 1 is not the `.so` that executed " \
           "tranche 2." in ML.R2_MEANING


def test_D4_13_licenses_ONE_field_and_opens_nothing_else(two_rev):
    """Any other key under `execution` / `preflight.wheel` keeps the RAISE."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit)
    m1, m2 = _exec_manifest(a), _exec_manifest(b)
    m1["execution"]["rust_toolchain"] = "1.80.0"
    m2["execution"]["rust_toolchain"] = "1.83.0"
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: m1, 9: m2}, license=lic)
    assert "execution.rust_toolchain" in str(e.value) and "UNCLASSIFIED" in str(e.value)

    lic2 = _license(repo, a, b, identity_path=wit,
                    git_clean_by_chunk={1: {"ok": True}, 9: {"ok": True}})
    w1, w2 = _wheel_manifest(a), _wheel_manifest(b)
    w1["preflight"]["wheel"]["carc_rs_version"] = "0.1.0"
    w2["preflight"]["wheel"]["carc_rs_version"] = "0.2.0"
    with pytest.raises(ML.MergeError) as e2:
        ML.merge_manifests({1: w1, 9: w2}, license=lic2)
    assert "preflight.wheel.carc_rs_version" in str(e2.value)
    assert "opens nothing else" in str(e2.value)


# =========================================================================== #
# 11. §D4.14 — `preflight.checks` ruled 7/7, and the CLASSIFICATION SWEEP      #
# =========================================================================== #
import schema_sweep as SW                                          # noqa: E402


def _checks_manifest(judge, *, census="2026-08-19T04:00:00Z", leaf_ok=True,
                     m=128, arb_note="rust", gate="/x/gate_chunk1.json",
                     rev="1" * 40, build=None):
    """A RUN_MANIFEST-shaped artifact carrying the seven `preflight.checks`."""
    return {
        "schema": "carcassonne-tiletie-run/v1", "judges": [judge],
        "git_rev": rev[:8], "m_worlds": m,
        "preflight": {"ok": True, "checks": {
            "leaf_hash": {"ok": leaf_ok, "harness_leaf_hash": "a36d2e15a3b3d71d",
                          "expected": "a36d2e15a3b3d71d"},
            "m": {"ok": True, "m": m, "m_max": m},
            "process_census": {"ok": True, "at": census, "loadavg": [1.0, 2.0]},
            "gate": {"ok": True, "path": gate},
            "positions": {"ok": True, "dir": f"/x/{gate}"},
            "git_clean": {"ok": True, "git_rev": rev[:8], "dirty_paths": []},
            "arb_backend": {"ok": True, "arb_backend": "rust", "note": arb_note,
                            "wheel": {"carc_rs_build": build or _build(rev)}},
        }},
    }


def test_preflight_checks_process_census_merges_and_is_recorded_per_chunk():
    """TELEMETRY: `ps` + loadavg at launch differ by construction on every
    invocation — the EMITTER itself excludes process_census from `ok`."""
    a = _checks_manifest("clair-puct", census="2026-08-19T04:00:00Z")
    b = _checks_manifest("clair-puct", census="2026-08-19T09:59:59Z")
    merged = ML.merge_manifests({1: a, 9: b})
    assert merged["preflight"]["checks"]["process_census"]["at"] == \
        "2026-08-19T04:00:00Z"                      # lowest chunk's value
    by = merged["merge"]["by_chunk"]
    assert by["1"]["preflight"]["checks"]["process_census"]["at"] != \
        by["9"]["preflight"]["checks"]["process_census"]["at"]
    assert ML.classify_note if False else True      # (no-op: readability)


def test_preflight_checks_gate_and_positions_are_per_chunk():
    a = _checks_manifest("clair-puct", gate="/x/gate_chunk1.json")
    b = _checks_manifest("clair-puct", gate="/x/gate_chunk9.json")
    merged = ML.merge_manifests({1: a, 9: b})
    by = merged["merge"]["by_chunk"]
    assert by["9"]["preflight"]["checks"]["gate"]["path"] == "/x/gate_chunk9.json"
    assert by["9"]["preflight"]["checks"]["positions"]["dir"].endswith("chunk9.json")


def test_preflight_checks_leaf_hash_divergence_REFUSES_and_says_gate_addressed():
    """⚠️ GATE-ADDRESSED: `G-LEAF` reads `preflight.checks.leaf_hash.ok`. It may
    not be reclassified without a ruling, and a divergence must refuse."""
    a = _checks_manifest("clair-puct", leaf_ok=True)
    b = _checks_manifest("clair-puct", leaf_ok=False)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: a, 9: b})
    assert "preflight.checks.leaf_hash" in str(e.value)
    assert "GATE-ADDRESSED" in str(e.value) and "G-LEAF" in str(e.value)


def test_preflight_checks_m_divergence_REFUSES():
    a, b = _checks_manifest("clair-puct"), _checks_manifest("clair-puct")
    b["preflight"]["checks"]["m"] = {"ok": True, "m": 32, "m_max": 32}
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: a, 9: b})
    assert "preflight.checks.m" in str(e.value) and "DESIGN CONSTANT" in str(e.value)


def test_preflight_checks_arb_backend_refuses_a_WITHIN_JUDGE_divergence():
    """⚠️ TRAP 2 — judge-scoped constancy is ASSERTED, never assumed: the class
    is an ACTIVE check."""
    a = _checks_manifest("tier1-greedy", arb_note="rust")
    b = _checks_manifest("tier1-greedy", arb_note="SOMETHING ELSE")
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: a, 9: b}, judge_by_chunk={1: "t", 9: "t"})
    assert "DIVERGES WITHIN a judge" in str(e.value)
    assert "never assumed" in str(e.value)


def test_preflight_checks_arb_backend_tolerates_a_CROSS_JUDGE_difference():
    """Across judges nothing is compared: `clair-puct` records the inert-flag
    note, `tier1-greedy` the wheel block — an equality between them would be
    MEANINGLESS rather than false."""
    a = _checks_manifest("clair-puct", arb_note="the flag is inert")
    b = _checks_manifest("tier1-greedy", arb_note="rust")
    # `judges` is recomputed as a union by merge_run_manifest — mirrored here,
    # since this is the cross-judge RUN_MANIFEST merge
    merged = ML.merge_manifests({1: a, 2: b}, allow_varying=["judges"])
    by = merged["merge"]["by_chunk"]
    assert by["1"]["preflight"]["checks"]["arb_backend"]["note"] != \
        by["2"]["preflight"]["checks"]["arb_backend"]["note"]


def test_preflight_checks_arb_backend_licenses_its_NESTED_build_stamp(two_rev):
    """⭐ FOUND BY THE SWEEP, not by a merge crash: this check dict EMBEDS a
    THIRD address of `carc_rs_build`, so a naive judge-scoped equality would
    refuse the merge for exactly the fact §D4.13 licensed."""
    repo, a, b, wit = two_rev
    lic = _license(repo, a, b, identity_path=wit,
                   git_clean_by_chunk={1: {"ok": True}, 9: {"ok": True}})
    m1 = _checks_manifest("tier1-greedy", rev=a, build=_build(a))
    m2 = _checks_manifest("tier1-greedy", rev=b, build=_build(b))
    merged = ML.merge_manifests({1: m1, 9: m2}, license=lic,
                                judge_by_chunk={1: "t", 9: "t"})
    paths = merged["merge"]["rev_license"]["paths"]
    assert "preflight.checks.arb_backend.wheel.carc_rs_build" in paths
    # the RECORDED value is the original, never the mask
    by = merged["merge"]["by_chunk"]
    assert by["9"]["preflight"]["checks"]["arb_backend"]["wheel"]["carc_rs_build"] \
        == _build(b)
    assert ML._MASKED_BUILD not in json.dumps(merged)
    # ... and the rest of the dict is still actively judge-scoped
    m2b = _checks_manifest("tier1-greedy", rev=b, build=_build(b),
                           arb_note="DIFFERENT")
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: m1, 9: m2b}, license=lic,
                           judge_by_chunk={1: "t", 9: "t"})
    assert "DIVERGES WITHIN a judge" in str(e.value)


def test_preflight_checks_is_a_CLOSED_SET_so_an_eighth_key_is_a_schema_change():
    a, b = _checks_manifest("clair-puct"), _checks_manifest("clair-puct")
    a["preflight"]["checks"]["brand_new_check"] = {"ok": True, "v": 1}
    b["preflight"]["checks"]["brand_new_check"] = {"ok": True, "v": 2}
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: a, 9: b})
    assert "CLOSED SET" in str(e.value) and "SCHEMA CHANGE" in str(e.value)
    assert sorted(ML.PREFLIGHT_CHECKS_CLOSED_SET) == [
        "arb_backend", "gate", "git_clean", "leaf_hash", "m", "positions",
        "process_census"], "the emitter's seven, and no more"


def test_git_clean_is_carried_by_the_merge_and_asserted_by_the_LICENCE(two_rev):
    """Ruled ONCE, not twice: the merge rule says how the field is CARRIED, the
    D4.12 licence says what must be TRUE. The merge never independently compares
    `git_rev` — that would give one condition two differently-worded refusals."""
    repo, a, b, wit = two_rev
    m1 = _checks_manifest("clair-puct", rev=a, build=_build(a))
    m2 = _checks_manifest("clair-puct", rev=b, build=_build(b))
    # no licence: the merge does NOT refuse on git_clean.git_rev differing …
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: m1, 9: m2})
    assert "git_clean" not in str(e.value), \
        "the merge must not raise its own git_rev refusal"
    # … it refuses on the rev fields, under the licence's vocabulary
    lic = _license(repo, a, b, identity_path=wit)
    merged = ML.merge_manifests({1: m1, 9: m2}, license=lic,
                                judge_by_chunk={1: "c", 9: "c"})
    by = merged["merge"]["by_chunk"]
    assert by["1"]["preflight"]["checks"]["git_clean"]["git_rev"] == a[:8]
    assert by["9"]["preflight"]["checks"]["git_clean"]["git_rev"] == b[:8]


def test_the_preflight_arb_backend_trap_does_not_relax_the_TOP_LEVEL_one():
    """⚠️ TRAP 1 — same name, two depths, different objects. `G-BACKEND` reads
    TOP-LEVEL `RUN_MANIFEST::arb_backend`, which stays IDENTITY_REQUIRED."""
    assert "arb_backend" in ML.RUN_MANIFEST_IDENTITY
    assert "arb_backend" in ML.GATE_ADDRESSED_PATHS
    a = dict(_checks_manifest("clair-puct"), arb_backend="rust")
    b = dict(_checks_manifest("clair-puct"), arb_backend="python")
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: a, 9: b},
                           identity_required=ML.RUN_MANIFEST_IDENTITY)
    assert "'arb_backend'" in str(e.value) and "DIVERGES" in str(e.value)


# --- the sweep ---------------------------------------------------------------- #
def test_the_sweep_is_FRESH_the_wired_classification_matches_the_emitted_table():
    """⭐ THE MECHANICAL-DIFF PROPERTY. The committed table must re-derive from
    today's `merge_legs` tables — so a classification change that was not
    re-swept shows up HERE rather than at merge time."""
    p = CAMPAIGN / "SCHEMA_SWEEP.json"
    assert p.is_file(), "SCHEMA_SWEEP.json must be committed beside the merge"
    doc = json.loads(p.read_text())
    drifted = []
    for r in doc["rows"]:
        now = SW.classify(r["path"], r["kind"])
        if now["class"] != r["class"]:
            drifted.append((r["kind"], r["path"], r["class"], now["class"]))
    assert not drifted, (
        "the wired classification no longer matches SCHEMA_SWEEP.json — re-run "
        f"schema_sweep.py and commit the diff: {drifted[:5]}")


def test_the_sweep_reports_a_CLOSED_schema_and_the_gate_converse():
    doc = json.loads((CAMPAIGN / "SCHEMA_SWEEP.json").read_text())
    assert doc["unclassified"] == [], "an unclassified key is a schema change"
    assert doc["gate_addresses_missing_from_schema"] == [], \
        "a gate whose address does not exist reads ABSENT, and absent is FAIL"
    assert doc["would_refuse"] == []
    # both emitters really were enumerated — the schema difference the
    # commission names explicitly
    paths = {(r["kind"], r["path"]) for r in doc["rows"]}
    assert ("leg", "execution.carc_rs_build") in paths          # oracle_score_pilot
    assert ("leg", "preflight.wheel.carc_rs_build") in paths    # tier1_rust_leg
    assert ("RUN_MANIFEST", "preflight.checks.arb_backend") in paths
    assert doc["n_sources"] >= 32


def test_the_sweep_measures_the_axis_rather_than_asserting_it():
    """`observed_axis` is a MEASUREMENT: a value that is a function of the chunk
    reads `chunk`, one that differs per run reads `invocation`."""
    rows = [{"chunk": 1, "judge": "a", "box": "x", "leg": 1, "tranche": "t",
             "kind": "leg", "value": "1"},
            {"chunk": 2, "judge": "a", "box": "x", "leg": 1, "tranche": "t",
             "kind": "leg", "value": "2"}]
    assert SW.observed_axis(rows)["axis"] == "chunk"
    same = [dict(r, value="1") for r in rows]
    assert SW.observed_axis(same)["axis"] == "none"
    census = [dict(rows[0], value="t1"), dict(rows[0], value="t2")]
    assert SW.observed_axis(census)["axis"] == "invocation"


def test_the_sweep_expands_nested_brace_addresses():
    """The c-remeasure address is NESTED-brace; a naive expander turns it into
    phantom paths and then reports them as missing."""
    got = SW._expand_braces("c_remeasure.{legs.{arb,if}.{ok,ratio},halt_fired}")
    assert sorted(got) == sorted([
        "c_remeasure.legs.arb.ok", "c_remeasure.legs.arb.ratio",
        "c_remeasure.legs.if.ok", "c_remeasure.legs.if.ratio",
        "c_remeasure.halt_fired"])


def test_the_merged_RUN_MANIFEST_is_written_NON_DESTRUCTIVELY(tmp_path):
    """⭐ ALSO FOUND BY THE SWEEP'S CONVERSE CHECK. `c_remeasure.py` merges a
    GATE-ADDRESSED block into the same artifact this tool writes; a plain write
    would delete it, and a gate whose address does not exist reads ABSENT."""
    man = tmp_path / "manifests"
    man.mkdir()
    for judge in ("clair-puct", "tier1-greedy"):
        (man / f"RUN_MANIFEST_S1_{judge}_chunk1.json").write_text(json.dumps(
            {"schema": "x", "judges": [judge], "git_rev": "1" * 40}))
    out = tmp_path / "RUN_MANIFEST_S1.json"
    out.write_text(json.dumps({"c_remeasure": {"ok": True, "halt_fired": False},
                               "stub": True}))
    rep = ML.merge_run_manifest(stratum="s1", manifests_dir=man, out_path=out)
    assert rep["ok"] is True
    assert rep["preserved_from_existing"] == ["c_remeasure", "stub"]
    doc = json.loads(out.read_text())
    assert doc["c_remeasure"] == {"ok": True, "halt_fired": False}
    assert doc["merge"]["preserved_from_existing"]["keys"] == ["c_remeasure", "stub"]


def test_without_a_licence_a_build_divergence_still_raises_D3s_message(two_rev):
    repo, a, b, wit = two_rev
    # only the BUILD differs — the rev fields are held equal so the refusal
    # under test is D3's on carc_rs_build, not the D4.11 rev path
    m1, m2 = _exec_manifest(a), _exec_manifest(a)
    m2["execution"]["carc_rs_build"] = _build(b)
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: m1, 9: m2})
    assert str(e.value).startswith(ML.R3)
    assert "CROSS-HOST WITNESS" in str(e.value)
    assert "No two-rev licence is in effect" in str(e.value)


# --- the generator ------------------------------------------------------------ #
def test_generator_emits_a_witness_the_licence_accepts(tmp_path):
    """NEVER HAND-WRITTEN: every field is computed live, and the round trip
    generator -> licence is the contract."""
    repo, a, b = _instrument_repo(tmp_path)
    out = tmp_path / "RUN" / ML.INSTRUMENT_IDENTITY_NAME
    out.parent.mkdir()
    rc = II.main(["--repo", str(repo), "--out", str(out),
                  "--rev", f"committed_tranche={a}",
                  "--rev", f"completion_tranche={b}"])
    assert rc == 0
    doc = json.loads(out.read_text())
    assert doc["schema"] == ML.INSTRUMENT_IDENTITY_SCHEMA
    assert doc["instrument_paths"] == list(ML.INSTRUMENT_PATHS)
    assert doc["committed_diff"]["empty"] is True
    assert "git -C" in doc["committed_diff"]["recipe"]
    assert doc["working_tree"]["by_box"]["local"]["clean"] is True
    # every instrument path exists at BOTH revs — the anti-vacuity check
    for p, rows in doc["path_existence"].items():
        assert len(rows) == 2, p
        assert all(v["present"] and v["n_tracked_files"] > 0 for v in rows.values()), p
    # the round trip: what the generator wrote is what the licence accepts
    lic = _license(repo, a, b, identity_path=out)
    assert ML.merge_manifests({1: _rev_manifest(a), 9: _rev_manifest(b)},
                              license=lic)["merge"]["rev_license"]


def test_generator_refuses_a_vacuous_path(tmp_path, monkeypatch):
    """A path that does not exist at a rev cannot be witnessed — the generator
    dies rather than emitting a vacuous truth."""
    repo, a, b = _instrument_repo(tmp_path)
    monkeypatch.setattr(ML, "INSTRUMENT_PATHS",
                        tuple(ML.INSTRUMENT_PATHS) + ("scripts/tiletie/nope.py",))
    with pytest.raises(SystemExit) as e:
        II.build(repo, revs={"committed_tranche": a, "completion_tranche": b})
    assert "VACUOUSLY TRUE" in str(e.value)


def test_generator_reports_nonzero_when_the_instrument_moved(tmp_path):
    repo, a, _b = _instrument_repo(tmp_path)
    c = _instrument_moved(repo)
    doc = II.build(repo, revs={"committed_tranche": a, "completion_tranche": c})
    assert doc["committed_diff"]["empty"] is False
    assert doc["committed_diff"]["n_files_changed"] == 1
    assert "oracle_score_pilot.py" in doc["committed_diff"]["files_changed"][0]


def test_the_licensed_pair_is_hard_coded_not_a_flag():
    """D4.11: *in CODE, not a CLI allowance* — a flag is invisible in the
    artifact and passable by anyone at any time."""
    src = (CAMPAIGN / "merge_legs.py").read_text()
    assert "58c2b539556916b0f6280d233b48d5dcbed7ca88" in src
    assert "4b24f512a0833b3fe71a126b713c560b2c8c4db1" in src
    assert len(ML.LICENSED_TRANCHE_REVS) == 2
    assert all(len(v) == 40 for v in ML.LICENSED_TRANCHE_REVS.values())
    # no CLI flag may license a rev
    for bad in ("--allow-rev", "--allow-varying-rev", "--license-rev",
                "--allow-two-rev"):
        assert bad not in src
    ap = ML.build_arg_parser()
    opts = {a.option_strings[0] for a in ap._actions if a.option_strings}
    assert "--instrument-identity" in opts       # WHERE the witness is, not a licence
    assert not any("rev" in o for o in opts)


def test_allow_varying_cannot_license_a_rev_at_any_address(two_rev):
    """⭐ D4.11's reason for putting the licence in CODE: *a flag is invisible in
    the artifact and passable by anyone at any time.* So `--allow-varying` must
    not reach a rev at ANY of the four addresses, with or without a witness."""
    repo, a, b, wit = two_rev
    for lic in (None, _license(repo, a, b, identity_path=wit)):
        for addr in ("git_rev", "code_rev", "execution.code_rev",
                     "champion_manifest.code_commit"):
            ma, mb = _rev_manifest(a), _rev_manifest(b)
            if addr == "execution.code_rev":              # isolate one address
                ma["git_rev"] = mb["git_rev"] = a
                ma["code_rev"] = mb["code_rev"] = a[:8]
                ma["champion_manifest"]["code_commit"] = b
                mb["champion_manifest"]["code_commit"] = b
            kwargs = {"allow_varying": [addr, addr.split(".")[0]]}
            if lic is None:
                with pytest.raises(ML.MergeError):
                    ML.merge_manifests({1: ma, 9: mb}, **kwargs)
            else:
                # WITH the licence the merge is legal — but because the code
                # enumerates it, never because a flag was passed
                out = ML.merge_manifests({1: ma, 9: mb}, license=lic, **kwargs)
                assert out["merge"]["rev_license"]["records"]
                assert not out["merge"]["divergent_keys_allowed"], \
                    "a rev must never be carried as an --allow-varying key"


def test_the_licensed_pair_matches_the_real_run(two_rev):
    """The enumerated shas are the run's actual tranche revs — a licence for the
    wrong pair would be worse than none."""
    assert ML.LICENSED_TRANCHE_REVS["committed_tranche"].startswith("58c2b539")
    assert ML.LICENSED_TRANCHE_REVS["completion_tranche"].startswith("4b24f512")
    lic = ML.RevLicense()
    assert lic.tranche_of("58c2b539") == "committed_tranche"
    assert lic.tranche_of("4b24f512-dirty") == "completion_tranche"
    assert lic.tranche_of("58c2b539556916b0f6280d233b48d5dcbed7ca88") == \
        "committed_tranche"


# =========================================================================== #
# 10. D5 (a) — the R5 LICENCE (drafter ruling `3b7cd11a`)                      #
#                                                                             #
# Rung-3 R5 split mid-run: chunks 1-2 scored at 9bc2ab77, chunks 3-8 at       #
# a5aa4a5e (the B64 aggregator commit landed on main while the local leg was  #
# live). Same SHAPE as D4.11, DIFFERENT PAIR — so it is the same code         #
# parameterized by a licence name, never a second script that could drift.    #
#                                                                             #
# ⚠️ The licence is a NAMED, CODE-RESIDENT pair. `--licence R5` SELECTS one of #
# two enumerations; it can never introduce a rev, which is the whole point of  #
# putting the enumeration in code rather than on the command line.            #
# =========================================================================== #
R5_A = "9bc2ab772ee907cdf4278985cf717497b95b2af1"
R5_B = "a5aa4a5e8573754b25476d220bbfe5fda514cf60"


def test_the_R5_pair_is_enumerated_in_code_at_FULL_width():
    revs = ML.LICENSED_TRANCHE_REVS_R5
    assert set(revs.values()) == {R5_A, R5_B}
    # ⚠️ full 40-char shas, so every comparison is abbrev-AGAINST-FULL
    assert all(len(s) == 40 for s in revs.values()), revs
    assert ML.LICENCE_SETS["R5"] is revs
    assert ML.IDENTITY_NAME_BY_LICENCE["R5"] == "INSTRUMENT_IDENTITY_R5.json"
    # the two licences are DISJOINT — no rev is licensed under both
    assert not (set(ML.LICENCE_SETS["R4"].values()) & set(revs.values()))


def test_R5_matches_a_recorded_abbrev_as_a_PREFIX_of_the_full_sha():
    lic = ML.RevLicense(licence="R5")
    for spelling in (R5_A, R5_A[:8], R5_A[:12], f"{R5_A[:8]}-dirty",
                     R5_A[:12].upper()):
        assert lic.tranche_of(spelling) == "r5_chunks_1_2", spelling
    assert lic.tranche_of(R5_B[:12]) == "r5_chunks_3_8"
    # ⚠️ NEVER abbrev-to-abbrev: below the floor nothing matches, so a 7-char
    # coincidence can never license a rev.
    assert ML.MIN_SHA_PREFIX == 8
    assert lic.tranche_of(R5_A[:7]) is None
    assert lic.tranche_of("") is None and lic.tranche_of(None) is None
    assert lic.tranche_of("not-a-sha") is None


def test_the_R4_and_R5_licences_REFUSE_each_others_revs():
    """Cross-licence leakage is the failure that would let an unrelated commit
    ride into a merge under a licence granted for a different split."""
    r4, r5 = ML.RevLicense(), ML.RevLicense(licence="R5")
    assert r5.tranche_of("58c2b539") is None
    assert r5.tranche_of("4b24f512") is None
    assert r4.tranche_of(R5_A[:8]) is None
    assert r4.tranche_of(R5_B[:8]) is None


def test_an_unknown_licence_NAME_refuses_rather_than_defaulting():
    with pytest.raises(ML.MergeError) as e:
        ML.RevLicense(licence="R6")
    assert "R6" in str(e.value) and "R4" in str(e.value) and "R5" in str(e.value)


def test_R5_looks_for_ITS_OWN_witness_file_and_names_it_when_ABSENT(tmp_path):
    """A missing witness must name the R5 file — an error naming the R4 witness
    would send the executor to regenerate the wrong document."""
    lic = ML.RevLicense(licence="R5", campaign=str(tmp_path))
    assert all(p.name == "INSTRUMENT_IDENTITY_R5.json" for p in lic._candidates())
    with pytest.raises(ML.MergeError) as e:
        lic.witness()
    msg = str(e.value)
    assert "INSTRUMENT_IDENTITY_R5.json" in msg and "ABSENT" in msg
    assert "R5 two-rev licence" in msg
    assert "INSTRUMENT_IDENTITY.json\"" not in msg      # not the R4 file


def _r5_repo(tmp_path):
    """An instrument repo whose two commits differ only OUTSIDE the instrument,
    relabelled to the R5 tranche names."""
    repo, a, b = _instrument_repo(tmp_path, name="r5repo")
    return repo, a, b


def test_R5_merges_under_its_own_witness_and_records_the_licence(tmp_path):
    repo, a, b = _r5_repo(tmp_path)
    wit = tmp_path / "INSTRUMENT_IDENTITY_R5.json"
    doc = II.build(repo, boxes=(("local", None),),
                   revs={"r5_chunks_1_2": a, "r5_chunks_3_8": b})
    doc["licence"] = "R5"
    wit.write_text(json.dumps(doc, indent=2, sort_keys=True))

    lic = ML.RevLicense(repo=repo, identity_path=wit, licence="R5",
                        revs={"r5_chunks_1_2": a, "r5_chunks_3_8": b})
    merged = ML.merge_manifests({1: _rev_manifest(a), 5: _rev_manifest(b)},
                                license=lic)
    rl = merged["merge"]["rev_license"]
    assert rl["records"]
    for rec in rl["records"]:
        assert set(rec["licensed_revs"].values()) == {a, b}
        # ⭐ the record NAMES its licence, so a reader of the merged manifest can
        # tell which enumerated pair authorised it without inferring from shas
        assert rec["licence"] == "R5"
        # the diff is RE-DERIVED here, never trusted from the witness
        red = rec["instrument_identity"]["rederived"]
        assert red["empty"] is True and red["n_files_changed"] == 0
        assert {red["rev_a"], red["rev_b"]} == {a, b}


def test_R5_refuses_an_R4_shaped_witness_naming_the_other_pair(tmp_path):
    """The witness must name the pair the CODE enumerates — the two documents
    are not interchangeable just because they share a schema."""
    repo, a, b = _r5_repo(tmp_path)
    wit = tmp_path / "INSTRUMENT_IDENTITY_R5.json"
    other = ML.LICENSED_TRANCHE_REVS
    doc = II.build(repo, boxes=(("local", None),),
                   revs={"committed_tranche": a, "completion_tranche": b})
    doc["revs"] = {k: {"sha": v} for k, v in other.items()}
    wit.write_text(json.dumps(doc, indent=2, sort_keys=True))
    lic = ML.RevLicense(repo=repo, identity_path=wit, licence="R5",
                        revs={"r5_chunks_1_2": a, "r5_chunks_3_8": b})
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 5: _rev_manifest(b)}, license=lic)
    assert "code-resident licence enumerates" in str(e.value)


def test_R5_refuses_when_the_REDERIVED_instrument_diff_is_NOT_empty(tmp_path):
    """The licence's whole content: the two revs must be identical over the
    instrument. R5's diff is EMPTY IN FACT — but that is a re-derived finding,
    not an assumption, and this proves the check can still fail."""
    repo, a, _ = _r5_repo(tmp_path)
    c = _instrument_moved(repo)
    wit = tmp_path / "INSTRUMENT_IDENTITY_R5.json"
    doc = II.build(repo, boxes=(("local", None),),
                   revs={"r5_chunks_1_2": a, "r5_chunks_3_8": c})
    doc["committed_diff"] = {"empty": True, "n_files_changed": 0,
                             "files": []}            # ⚠️ the witness LIES
    wit.write_text(json.dumps(doc, indent=2, sort_keys=True))
    lic = ML.RevLicense(repo=repo, identity_path=wit, licence="R5",
                        revs={"r5_chunks_1_2": a, "r5_chunks_3_8": c})
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 5: _rev_manifest(c)}, license=lic)
    assert "oracle_score_pilot.py" in str(e.value)


def test_a_rev_outside_the_R5_pair_still_refuses(tmp_path):
    repo, a, b = _r5_repo(tmp_path)
    wit = tmp_path / "INSTRUMENT_IDENTITY_R5.json"
    doc = II.build(repo, boxes=(("local", None),),
                   revs={"r5_chunks_1_2": a, "r5_chunks_3_8": b})
    wit.write_text(json.dumps(doc, indent=2, sort_keys=True))
    lic = ML.RevLicense(repo=repo, identity_path=wit, licence="R5",
                        revs={"r5_chunks_1_2": a, "r5_chunks_3_8": b})
    third = "c" * 40
    with pytest.raises(ML.MergeError) as e:
        ML.merge_manifests({1: _rev_manifest(a), 5: _rev_manifest(b),
                            7: _rev_manifest(third)}, license=lic)
    assert "NOT in the enumerated licence" in str(e.value)


def test_the_generator_is_PARAMETERIZED_not_forked(tmp_path):
    """One generator, one licence flag — a second script would be free to drift
    from the enumeration the merge actually enforces."""
    src = (Path(II.__file__)).read_text()
    assert "--licence" in src
    assert "ML.LICENCE_SETS" in src and "ML.IDENTITY_NAME_BY_LICENCE" in src
    # and there is no rival generator alongside it
    sibs = {p.name for p in Path(II.__file__).parent.glob("instrument_identity*.py")}
    assert sibs == {"instrument_identity.py"}, sibs


def test_the_merge_CLI_exposes_the_licence_and_defaults_to_R4():
    src = (Path(ML.__file__)).read_text()
    assert '"--licence"' in src and "choices=sorted(LICENCE_SETS)" in src
    assert 'default="R4"' in src
    assert "licence=a.licence," in src


# --- ruling (c): the executor's merge step is BLESSED, not a TODO ------------- #
def test_the_R5_launcher_carries_the_blessed_merge_invocation():
    sh = (Path(ML.__file__).parent / "rung3_r5" / "run_scoring_r5.sh").read_text()
    # ruling (c): the merge step is spelled out or deleted — never an unbuilt
    # placeholder sitting next to steps the script really performs.
    assert not re.search(r"(?m)^[^#]*\bTODO\b(?!.*reads as an unbuilt)", sh), \
        "an unfilled TODO remains in the launcher"
    assert "merge_legs.py" in sh
    assert "--licence R5" in sh
    assert "INSTRUMENT_IDENTITY_R5.json" in sh
    # the witness is GENERATED before it is consumed, both boxes captured
    assert "instrument_identity.py" in sh
    assert "--box local" in sh and "--box laptop:laptop-wsl" in sh
    assert sh.index("instrument_identity.py") < sh.index("merge_legs.py")
