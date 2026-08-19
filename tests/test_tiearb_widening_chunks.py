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
