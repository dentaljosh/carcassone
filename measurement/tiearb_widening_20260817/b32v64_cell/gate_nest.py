#!/usr/bin/env python3
"""`G-NEST` — the nested-CRN witness for the `B` = 32 vs `B` = 64 cell. Emits
`GATE_NEST.json` in THIS directory (`b32v64_cell/`).

A PARAMETERIZED SIBLING of `b64_cell/gate_nest.py` (a SPENT, ADJUDICATED run —
that file is READ here and NEVER edited). Same two halves, same anchor, same
degeneracy control; what changes is the CLAIM and the fact that the two `B`
values are now real CLI parameters instead of module constants nailed to 64/16.

WHAT THE GATE ASSERTS HERE: *at HEAD, for a pinned position/ply/salt, the world
seeds and playout seeds generated at `B` = 64 for `j ∈ 0..31` are byte-identical
to those generated at `B` = 32, and the `build_arms` cap draw and the selection
stream are identical.* ⇒ **`B` = 32's ENTIRE world set is a strict SUBSET of
`B` = 64's**, so `B` = 64 is a strict refinement of `B` = 32 and the two cells
are one increment, not two experiments.

⚠️ **WHY THIS MATTERS MORE THAN A UNIT TEST.** Without nesting, the `B` = 32 and
`B` = 64 cells are two unrelated draws and the whole "increment" framing is void
— the cell would be comparing two independent experiments while reporting a
refinement. It is a PRECONDITION, not a rider.

THE TWO HALVES, and neither substitutes for the other:

  STRUCTURAL — `analyze_b32v64_cell.nest_witness`: the four seeding sites in
    `rust/carc/carc-core/src/tiearb.rs` are pure functions of `j` with NO `B`
    term. That is the *reason* the sets nest — and it is a `B`-FREE reading of
    the source, so it is the same witness for (32, 64) as it was for (16, 64).
    ⭐ REPOINTED 2026-08-21 from `analyze_b64_cell` to THIS cell's own
    adjudicator, discharging DESIGN §13.2 item 7's reported cross-cell
    dependency exactly as that item's own resolution required. The b64 tool is
    UNTOUCHED; the function was COPIED, and one implementation of the site
    regexes still beats two spellings of it.
  RUNTIME (this file's addition) — the same claim on REAL WORLD VALUES: build
    the worlds at `B` = 64 and at `B` = 32 from the pinned position's own
    `state_digest`/`ply` and the deploy salt, and byte-compare.

⭐ **THE ANCHOR THAT STOPS THIS BEING A TAUTOLOGY.** `seed_i64` is not exported
to python, so the runtime half must recompute it — and a recomputation compared
against itself proves nothing. So the emitter first REPRODUCES THE RUST
ARBITER'S OWN CAP DRAW: at a pinned position where the cap genuinely fires
(> `J` distinct afterstates, so the shuffle is actually consulted), the python
`seed_i64` + `carc_rs.shuffle_indices` must reproduce `tiearb_probe`'s `arms`
EXACTLY. If it does not, the witness is FALSE and nothing else is reported —
the seeding function this file uses would not be the one the arbiter uses.

⚠️ **WHAT THE RUNTIME HALF DOES NOT ADD, stated so nobody over-reads it.** It
does not re-derive `arbitrate`'s loop bound from the binary; the loop `for j in
0..b` is read by the STRUCTURAL half. It demonstrates that the seed→world map is
a pure function of `j` and that the real determinized decks are byte-identical
across the two generations. Together the halves cover the claim; separately
neither does.

⛔ ADJUDICATES NOTHING. It is a precondition witness: it licenses the cell's
framing, and it moves no bar, branch or statistic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

TOOL = "[g-nest]"
REPO = Path(__file__).resolve().parents[3]
CELL = Path(__file__).resolve().parent

#: ⭐ THE PINNED INPUTS. The pair says "a pinned position/ply/salt" and pins no
#: values, so they are pinned HERE, in code, and echoed into the artifact.
#: The deck seed and start ply are the cell's OWN control line — the one
#: `scripts/classical_search/tiearb_live.py` already uses for the `G-J13`
#: two-sided liveness assert — so the nest witness and the liveness witness
#: stand on the same pinned position rather than on two unrelated ones.
CONTROL_DECK_SEED = "28000000000"
CONTROL_START_PLY = 30
#: the DEPLOYED salt, pinned by `G-J4`'s resolved dict. Not the instrument's
#: `tiletie-cap|<rid>|20260812` — that is the other stream entirely.
DEPLOY_SALT = "tiearb2-deploy-v1"
DEPLOYED_J = 4
#: ⭐ the cell's two widths: `B_HI` = 64 (the DEPLOYED incumbent), `B_LO` = 32
#: (the cheaper candidate). DEFAULTS ONLY — `--b-hi` / `--b-lo` override them
#: and thread all the way through `generate()` / `compare()` / `build()`, so the
#: tool is parameterized rather than re-hard-coded per cell.
B_HI, B_LO = 64, 32
SCHEMA = "carcassonne-b32v64-gate-nest/v1"


def seed_i64(parts) -> int:
    """`sha256(part_0 | part_1 | …)[:8]` as a non-negative i64.

    A transcription of `tiearb.rs::seed_i64`, VALIDATED at run time against the
    rust arbiter's own cap draw (see `reproduce_cap_draw`) — never trusted
    because it looks right.
    """
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF


def world_seed(salt, digest, ply, j) -> int:
    return seed_i64([salt, digest, ply, j])


def playout_seed(salt, digest, ply, j) -> int:
    return seed_i64([salt, digest, ply, j, "playout"])


def cap_seed(salt, digest, ply) -> int:
    return seed_i64([salt, digest, ply, "cap"])


def select_seed(salt, digest, ply) -> int:
    return seed_i64([salt, digest, ply, "select"])


# --------------------------------------------------------------------------- #
# the pinned position                                                           #
# --------------------------------------------------------------------------- #
def pinned_position(carc_rs, lc, *, deck_seed=CONTROL_DECK_SEED,
                    start_ply=CONTROL_START_PLY, salt=DEPLOY_SALT,
                    j=DEPLOYED_J, max_scan=300) -> dict:
    """Walk the pinned control line to the FIRST ply where the deployed trigger
    fires AND the cap draw is actually consulted.

    ⚠️ `capped` is required, not incidental: on a tie set no larger than `J` the
    shuffle is never called, so the cap-draw anchor below would pass without
    exercising `seed_i64` at all — a validation that cannot fail is the same
    vacuous shape this campaign keeps finding.

    The walk rule (`la[len(la) // 2]`) is `tiearb_live.py`'s, so the position is
    reproducible from the two pinned constants and nothing else.
    """
    ms = carc_rs.MirrorState.from_seed(deck_seed)
    actions, ply = [], 0
    for _ in range(start_ply):
        la = ms.legal_actions()
        a = int(la[len(la) // 2])
        ms.advance(a)
        actions.append(a)
        ply += 1
    for _ in range(max_scan):
        if ms.is_terminal():
            break
        probe = ms.tiearb_probe(lc, -1, j, 0.0, salt, ply)
        if probe.get("fired") and probe.get("capped"):
            return {"deck_seed": deck_seed, "prefix_actions": list(actions),
                    "ply": ply, "state_digest": probe["state_digest"],
                    "seat": probe.get("seat"),
                    "tie_actions": [int(x) for x in probe["tie_actions"]],
                    "arms": [int(x) for x in probe["arms"]],
                    "n_distinct_afterstates": probe.get("n_distinct_afterstates"),
                    "capped": True}
        la = ms.legal_actions()
        a = int(la[len(la) // 2])
        ms.advance(a)
        actions.append(a)
        ply += 1
    raise SystemExit(
        f"{TOOL} REFUSING: no fired-and-capped ply within {max_scan} plies of "
        f"the pinned control line. The witness needs a position where the cap "
        f"draw is actually consulted — without one the seed_i64 anchor cannot "
        f"fail, and an anchor that cannot fail is not an anchor.")


# --------------------------------------------------------------------------- #
# the anchor: reproduce the ARBITER'S OWN cap draw                              #
# --------------------------------------------------------------------------- #
def reproduce_cap_draw(carc_rs, pos: dict, *, salt=DEPLOY_SALT, j=DEPLOYED_J) -> dict:
    """`build_arms`' cap: `shuffle_range(len(candidates))` under
    `MT19937::from_py_int_seed_i64(seed_i64([salt, digest, ply, "cap"]))`, then
    the first `J-1` picks, sorted, appended to the reference arm.

    ⭐ If this reproduces `tiearb_probe`'s `arms` byte-for-byte, then the
    `seed_i64` used by the rest of this file IS the arbiter's. ⚠️ `B`-FREE by
    construction — the cap draw does not depend on `B`, which is part of what is
    being witnessed.
    """
    tie = list(pos["tie_actions"])
    reference, candidates = tie[0], tie[1:]
    seed = cap_seed(salt, pos["state_digest"], pos["ply"])
    perm = carc_rs.shuffle_indices(str(seed), len(candidates), "global")
    chosen = sorted(candidates[i] for i in perm[: max(j, 1) - 1])
    reproduced = [reference] + chosen
    ok = reproduced == list(pos["arms"])
    return {"ok": bool(ok), "cap_seed": seed, "n_candidates": len(candidates),
            "reproduced_arms": reproduced, "arbiter_arms": list(pos["arms"]),
            "why": ("the python seed_i64 + MT19937 shuffle reproduce the RUST "
                    "arbiter's own capped arm set exactly, so the seeding "
                    "function used below is the arbiter's"
                    if ok else
                    "⛔ the reproduction DIFFERS from the arbiter's arms — the "
                    "seeding function transcribed here is NOT the one the "
                    "arbiter uses, so no seed comparison below means anything")}


# --------------------------------------------------------------------------- #
# the runtime twin: REAL worlds at B=b_hi (64) and B=b_lo (32)                   #
# --------------------------------------------------------------------------- #
def generate(carc_rs, pos: dict, b: int, *, salt=DEPLOY_SALT) -> dict:
    """The world set `arbitrate` would draw at this `B` — real determinized
    decks from rust, one per `j`, plus the per-`j` playout seeds."""
    dg, ply = pos["state_digest"], pos["ply"]
    ws, ps, decks = [], [], []
    for j in range(b):
        s = world_seed(salt, dg, ply, j)
        ws.append(s)
        ps.append(playout_seed(salt, dg, ply, j))
        decks.append(list(carc_rs.tier1_world_deck(
            pos["deck_seed"], pos["prefix_actions"], ply, s)))
    return {"b": b, "world_seeds": ws, "playout_seeds": ps, "worlds": decks,
            "cap_seed": cap_seed(salt, dg, ply),
            "select_seed": select_seed(salt, dg, ply)}


def _deck_sha(deck) -> str:
    return hashlib.sha256("|".join(deck).encode()).hexdigest()


def compare(hi: dict, lo: dict) -> dict:
    """Byte-compare `B`=`hi["b"]`'s `j ∈ 0..lo["b"]-1` against `B`=`lo["b"]`'s
    ENTIRE set — i.e. at the defaults, `B`=64's `j ∈ 0..31` against `B`=32's
    whole world set, the strict-subset claim."""
    n = lo["b"]
    seeds_eq = hi["world_seeds"][:n] == lo["world_seeds"]
    playout_eq = hi["playout_seeds"][:n] == lo["playout_seeds"]
    worlds_eq = hi["worlds"][:n] == lo["worlds"]
    first_diff = next((j for j in range(n)
                       if hi["worlds"][j] != lo["worlds"][j]), None)
    return {
        "n_compared": n,
        "world_seeds_identical": bool(seeds_eq),
        "playout_seeds_identical": bool(playout_eq),
        "worlds_byte_identical": bool(worlds_eq),
        "first_differing_j": first_diff,
        "cap_seed_identical": hi["cap_seed"] == lo["cap_seed"],
        "select_seed_identical": hi["select_seed"] == lo["select_seed"],
        # ⚠️ the DISTINCTNESS control: 64 identical worlds would also satisfy
        # "the first 32 match", and would mean the determinization is broken
        # rather than nested. A witness that passes on a degenerate world set is
        # not a witness.
        "n_distinct_worlds_hi": len({_deck_sha(d) for d in hi["worlds"]}),
        "n_distinct_worlds_lo": len({_deck_sha(d) for d in lo["worlds"]}),
        "world_sha_prefix": [_deck_sha(d)[:16] for d in lo["worlds"]],
    }


def build(carc_rs, lc, *, repo=REPO, salt=DEPLOY_SALT, b_hi=B_HI, b_lo=B_LO) -> dict:
    # the two widths are parameters, so they are CHECKED rather than assumed:
    # HEALTHY -> 0 < b_lo < b_hi (e.g. 32 < 64), the subset claim is meaningful.
    # FIRES   -> a non-positive width, or b_lo >= b_hi, where "hi's first b_lo
    #            worlds" is either empty or not a proper prefix.
    if not (isinstance(b_hi, int) and isinstance(b_lo, int)):
        raise SystemExit(f"{TOOL} REFUSING: b_hi/b_lo must be ints")
    if b_hi <= 0 or b_lo <= 0:
        raise SystemExit(f"{TOOL} REFUSING: b_hi={b_hi} b_lo={b_lo} — both must "
                         f"be positive")
    if b_lo >= b_hi:
        raise SystemExit(f"{TOOL} REFUSING: b_lo={b_lo} must be strictly less "
                         f"than b_hi={b_hi} — the witness is a SUBSET claim")

    pos = pinned_position(carc_rs, lc, salt=salt)
    anchor = reproduce_cap_draw(carc_rs, pos, salt=salt)

    doc = {
        "schema": SCHEMA, "gate": "G-NEST", "scope": "[RUN]",
        "marker": "[pre-run]",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claim": (f"B={b_hi}'s worlds j in 0..{b_lo - 1} are byte-identical to "
                  f"B={b_lo}'s ENTIRE world set — B={b_lo} is a strict SUBSET "
                  f"of B={b_hi}"),
        "pinned": {"deck_seed": pos["deck_seed"],
                   "control_start_ply": CONTROL_START_PLY,
                   "ply": pos["ply"], "state_digest": pos["state_digest"],
                   "seat": pos["seat"], "salt": salt, "j": DEPLOYED_J,
                   "b_hi": b_hi, "b_lo": b_lo,
                   "n_prefix_actions": len(pos["prefix_actions"]),
                   "n_tie_actions": len(pos["tie_actions"]),
                   "n_arms": len(pos["arms"]),
                   "n_distinct_afterstates": pos["n_distinct_afterstates"],
                   "cap_actually_fired": pos["capped"],
                   "why_this_position": "the cell's own G-J13 control line, "
                                        "walked to the first ply where the "
                                        "trigger fires AND the cap draw is "
                                        "consulted"},
        "seed_i64_anchor": anchor,
        "adjudicates": "NOTHING — a precondition witness. It licenses the "
                       "cell's increment framing and moves no bar, branch or "
                       "statistic.",
    }
    if not anchor["ok"]:
        # ⛔ FAIL CLOSED, and report NOTHING else: every comparison below would
        # be a python-vs-python identity if the seeding transcription is wrong.
        doc["witness"] = False
        doc["why"] = anchor["why"]
        return doc

    hi = generate(carc_rs, pos, b_hi, salt=salt)
    lo = generate(carc_rs, pos, b_lo, salt=salt)
    cmp_ = compare(hi, lo)
    doc["runtime"] = cmp_

    # the STRUCTURAL half — ONE implementation of the seeding-site regexes, not
    # two spellings of it. It reads `rust/carc/carc-core/src/tiearb.rs` and
    # asserts every seeding site is B-FREE, which is a claim about the SOURCE and
    # not about any pair of B values ⇒ it carries over to (32, 64) unchanged.
    #
    # ⭐ REPOINTED 2026-08-21. This used to import `analyze_b64_cell.nest_witness`
    # — a live dependency on a SPENT run's tooling, which DESIGN §13.2 item 7
    # REPORTED for the orchestrator with its own stated resolution: *"when
    # scripts/tiletie/analyze_b32v64_cell.py is built it should expose the same
    # function rather than restate the regexes, and the import should move
    # there."* The adjudicator is now built and exposes it, so the import has
    # moved. ⛔ `analyze_b64_cell.py` is UNTOUCHED — the function was COPIED into
    # this cell's own adjudicator, not moved out from under a spent run.
    sys.path.insert(0, str(Path(repo) / "scripts" / "tiletie"))
    import analyze_b32v64_cell as AB                           # noqa: PLC0415
    structural = AB.nest_witness(repo)
    doc["structural"] = structural
    doc["structural_source"] = ("scripts/tiletie/analyze_b32v64_cell.py::"
                                "nest_witness — a B-FREE reading of the rust "
                                "seeding sites, owned by THIS cell's adjudicator "
                                "(repointed off the spent b64_cell tool, DESIGN "
                                "§13.2 item 7)")
    doc["sites"] = structural.get("sites")

    conj = {
        "seed_i64_anchor_reproduces_arbiter_arms": anchor["ok"],
        "world_seeds_identical": cmp_["world_seeds_identical"],
        "playout_seeds_identical": cmp_["playout_seeds_identical"],
        "worlds_byte_identical": cmp_["worlds_byte_identical"],
        "cap_draw_identical": cmp_["cap_seed_identical"],
        "select_stream_identical": cmp_["select_seed_identical"],
        "structural_sites_b_free": bool(structural.get("witness")),
        # the degeneracy control, above
        "worlds_are_distinct": (cmp_["n_distinct_worlds_hi"] == b_hi
                                and cmp_["n_distinct_worlds_lo"] == b_lo),
    }
    doc["conjuncts"] = conj
    bad = sorted(k for k, v in conj.items() if not v)
    doc["witness"] = not bad
    doc["why"] = (
        f"B={b_hi}'s worlds 0..{b_lo - 1} are BYTE-IDENTICAL to B="
        f"{b_lo}'s entire set (real determinized decks, not just seeds), "
        f"the cap draw and selection stream are identical, and every seeding "
        f"site is a pure function of j with no B term ⇒ the world sets NEST and "
        f"B={b_hi} is a strict refinement of B={b_lo}"
        if not bad else
        f"⛔ G-NEST FAILED on conjunct(s) {bad} — without nesting, B={b_lo} and "
        f"B={b_hi} are two unrelated draws and the whole increment framing is "
        f"void")
    return doc


def build_arg_parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(CELL / "GATE_NEST.json"))
    ap.add_argument("--repo", default=str(REPO))
    ap.add_argument("--salt", default=DEPLOY_SALT,
                    help="the DEPLOYED salt (G-J4's resolved dict). Changing it "
                         "makes the witness about a different arbiter.")
    ap.add_argument("--b-hi", type=int, default=B_HI,
                    help="the WIDER width, the DEPLOYED incumbent (default 64)")
    ap.add_argument("--b-lo", type=int, default=B_LO,
                    help="the NARROWER width, this cell's candidate (default "
                         "32). Must be strictly less than --b-hi: the witness "
                         "is a SUBSET claim.")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print; write nothing")
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    import carc_rs                                              # noqa: PLC0415
    from carcassonne_ai.rust_agent import leaf_config_rs        # noqa: PLC0415
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: PLC0415
    doc = build(carc_rs, leaf_config_rs(DEFAULT_CONFIG), repo=Path(a.repo),
                salt=a.salt, b_hi=a.b_hi, b_lo=a.b_lo)

    p = doc["pinned"]
    print(f"{TOOL} claim: {doc['claim']}")
    print(f"{TOOL} pinned: deck {p['deck_seed']} ply {p['ply']} digest "
          f"{p['state_digest']} salt {p['salt']} | tie {p['n_tie_actions']} -> "
          f"arms {p['n_arms']} (cap fired: {p['cap_actually_fired']})")
    print(f"{TOOL} seed_i64 anchor: {'OK' if doc['seed_i64_anchor']['ok'] else 'FAILED'}"
          f" — {doc['seed_i64_anchor']['why'][:96]}")
    if "runtime" in doc:
        r = doc["runtime"]
        print(f"{TOOL} runtime: worlds byte-identical for j in 0..{r['n_compared'] - 1}"
              f" = {r['worlds_byte_identical']} | world seeds "
              f"{r['world_seeds_identical']} | playout seeds "
              f"{r['playout_seeds_identical']} | cap {r['cap_seed_identical']} | "
              f"select {r['select_seed_identical']} | distinct "
              f"{r['n_distinct_worlds_hi']}/{a.b_hi}")
    print(f"{TOOL} WITNESS = {doc['witness']}  (ADJUDICATES NOTHING)")
    if not a.dry_run:
        Path(a.out).write_text(json.dumps(doc, indent=2, sort_keys=True))
        print(f"{TOOL} -> {a.out}")
    return 0 if doc["witness"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
