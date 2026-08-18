#!/usr/bin/env python3
"""TILE-TIE PRICING — the RUST `tier1-greedy` (ARB judge) leg runner.

Instrument work item **W1** of the tie-arbiter widening campaign
(`measurement/tiearb_widening_20260817/PLAN_B_gt_16.md` §0.3, §3; `CAMPAIGN.md`
ruling 2): the ARB judge's playouts move from the python `RuleBasedPlayer`
continuation to the Phase-A rust port, which `G-BITEXACT` proved value-identical
15,360/15,360 (`measurement/tiearb2_stage2_20260817/PHASE_A.md`).

**This is PURE PYTHON WIRING.** Nothing under `rust/` is touched: the installed
`carc_rs` wheel already exposes `tier1_leg`, and this module drives it with the
call pattern `scripts/tiletie/verify_tier1_rust.py` used for the gate — same
argument order, same `legal_mask_cache` discipline, same `_f64_bits` comparison
currency.

WHAT IT REPLACES, AND WHAT IT DOES NOT
--------------------------------------
It replaces exactly one leg: `oracle_score_pilot --oracle-policy tier1-greedy
--backend python`. The `clair-puct` pricing judge is untouched and still runs
through `oracle_score_pilot` (it is ~93% of the shared run's bill; see
PLAN_B_gt_16 §0.3). `run_tiletie.py --arb-backend rust` is the switch; the
default stays `python`, so no existing invocation changes behaviour.

THE CRN CONTRACT IS THE PYTHON ONE, IMPORTED NOT REIMPLEMENTED
---------------------------------------------------------------
World and playout seeds come from `oracle_score_pilot.world_seed` /
`playout_seed` — the very functions the python leg calls. `M` never enters the
derivation (`sha256(tag|rid|j|salt)`), so worlds are **prefix-stable**: the first
32 worlds of an `M = 128` run are bit-identical to a banked `M = 32` run
(PLAN_B_gt_16 §0.1). `preflight_seeds()` asserts that property rather than
trusting it, and refuses to run if it ever stops holding — the J13 lesson: a
stale wheel or a drifted derivation must FAIL, never silently price as something
else.

`carc_rs.tier1_leg` builds ONE determinized world per `world_seeds[j]` and shares
it across both picks, which is the CRN. The python leg witnesses that with
`afterstate_deck_hash_a == afterstate_deck_hash_b`; the rust leg cannot produce
that field (the FFI returns values and plies), so it emits a DIFFERENT, honest
witness — `world_deck_hash`, the sha256 of the determinized world's unseen deck
from `carc_rs.tier1_world_deck` — and names it in `crn_witness`. **No field is
fabricated**: `afterstate_deck_hash_a/b` are simply absent from a rust record.
`run_tiletie.check_crn_cross_leg` reads whichever witness a leg carries and fails
loudly if a set of legs mixes the two.

⚠️ `legal_mask_cache` (default **True**). The python judge memoizes the legal
mask per record (`game_wrapper.Game._legal_cache`) on a key that is not injective
for 180°-symmetric tiles, so it occasionally serves a colliding mask. Bit-
identity with the python leg REQUIRES reproducing that memo (57 of Phase A's
15,360 values moved on it). `--no-legal-mask-cache` runs the honest recomputed
mask and is **NOT python-comparable** — the manifest records which was used and
`run_tiletie`'s parity smoke refuses the honest mask.

⚠️ RULES PROFILE. `tier1_leg` replays the prefix under the default `GameConfig`,
i.e. the `walled` profile (`game_kwargs()` == `{}`). Any other profile FAILS
LOUDLY here, exactly as the clairvoyant rust ruler does in `run_tiletie`
(`RUST_OK_PROFILES`).

Usage (drop-in for the pilot's leg interface):

    .venv/bin/python scripts/tiletie/tier1_rust_leg.py \\
        --positions-jsonl <leg>.jsonl --rules-profile walled \\
        --m 128 --world-seed-salt tiletie-v1 --workers 30 --n <lines> \\
        --out-root /mnt/c/carc-shared/<run> --out-subdir tier1-greedy/walled/leg1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

for _p in (str(HERE), str(REPO / "scripts" / "measurement_infra")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCHEMA = "carcassonne-tiletie-tier1-rust-leg/v1"
DESIGN_DOC = "measurement/tiearb_widening_20260817/PLAN_B_gt_16.md"

#: The judge this module implements. One value only — it is not a policy switch.
ORACLE_POLICY = "tier1-greedy"

#: `carc_rs.tier1_leg` replays under the default `GameConfig`. Only the profile
#: whose `game_kwargs()` is `{}` may use it.
RUST_OK_PROFILES = frozenset({"walled"})

#: PLAN_B_gt_16 §0.2: the cross-fit parity halves cap usable `B` at `M/2`, so
#: `B ∈ {16,32,64}` needs `M = 128`. Above that nothing in the campaign asks for
#: worlds, and a typo'd `--m` must not silently buy a 10x run.
M_MAX = 128

MAX_PLIES = 400

#: Phase A's finding, carried verbatim. See the module docstring.
DEFAULT_LEGAL_MASK_CACHE = True

CRN_WITNESS_RUST = "world_deck_hash"
CRN_WITNESS_PYTHON = "afterstate_deck_hash"

_WHEEL_MISSING = (
    "carc_rs is not importable, or the installed wheel has no `tier1_leg`. "
    "REFUSING to run: the whole point of --arb-backend rust is that the ARB "
    "judge is priced by the Phase-A port; falling back to the python "
    "continuation here would silently produce a 12x-costlier leg under a "
    "manifest that claims 'rust'. Rebuild/reinstall the wheel "
    "(rust/carc/carc-py) and re-run.")


# --------------------------------------------------------------------------- #
# preflight — every one of these FAILS LOUD                                     #
# --------------------------------------------------------------------------- #
def _f64_bits(x) -> int:
    """Raw f64 bit pattern — `run_tiletie._f64_bits` / the rustport gate's own
    comparison currency. NEVER `==`/approx on the float itself."""
    return struct.unpack("<Q", struct.pack("<d", float(x)))[0]


def preflight_wheel() -> dict:
    """`carc_rs` imports AND carries the Phase-A entry points. Raises SystemExit
    otherwise — never returns a 'degraded' verdict the caller might ignore."""
    try:
        import carc_rs  # noqa: PLC0415
    except Exception as exc:                                       # noqa: BLE001
        raise SystemExit(f"[tier1_rust_leg] {_WHEEL_MISSING}\n  ({type(exc).__name__}: {exc})")
    missing = [n for n in ("tier1_leg", "tier1_world_deck", "MirrorState")
               if not hasattr(carc_rs, n)]
    if missing:
        raise SystemExit(f"[tier1_rust_leg] {_WHEEL_MISSING}\n  missing: {missing}")
    out = {"ok": True, "carc_rs_file": carc_rs.__file__,
           "carc_rs_version": getattr(carc_rs, "__version__", None)}
    try:
        sys.path.insert(0, str(REPO / "src"))
        from carcassonne_ai import rust_agent as RA  # noqa: PLC0415

        out["carc_rs_build"] = RA.carc_rs_build_id()
        out["carc_rs_binary_sha"] = RA.carc_rs_binary_sha()
    except Exception as exc:                                       # noqa: BLE001
        # Provenance is desirable, not load-bearing for correctness; the gate
        # above already proved the entry points exist.
        out["build_id_error"] = f"{type(exc).__name__}: {exc}"
    return out


def preflight_profile(profile: str) -> dict:
    if profile not in RUST_OK_PROFILES:
        raise SystemExit(
            f"[tier1_rust_leg] rules profile {profile!r} cannot be scored by the "
            f"rust tier1 continuation: `carc_rs.tier1_leg` replays the prefix "
            f"under the DEFAULT GameConfig, which only {sorted(RUST_OK_PROFILES)} "
            "matches (its game_kwargs() is {}). Run this profile with "
            "--arb-backend python, or the port must learn to forward geometry/"
            "rules config first.")
    return {"ok": True, "rules_profile": profile}


def preflight_seeds(salt: str, m: int, probe_rid: str = "tt_preflight_probe_p0") -> dict:
    """The CRN derivation is the PYTHON one and is PREFIX-STABLE in `M`.

    Two independent assertions, both hard:
      1. `world_seed`/`playout_seed` are imported from `oracle_score_pilot` (not
         reimplemented here), and re-derive to the same values as
         `oracle_score_pilot.world_seeds(rid, m, salt)`.
      2. `M` does not enter the derivation: the first `k` seeds at `M = m` equal
         the seeds at `M = k`, for every `k` on a ladder up to `m`. This is
         PLAN_B_gt_16 §0.1, and it is what makes every `B <= M/2` a sub-read of
         one paid run — if it ever stops holding, every sub-read is void.
    """
    from oracle_score_pilot import playout_seed, world_seed, world_seeds  # noqa: PLC0415

    full_w = world_seeds(probe_rid, m, salt)
    if full_w != [world_seed(probe_rid, j, salt) for j in range(m)]:
        raise SystemExit("[tier1_rust_leg] world_seeds() disagrees with world_seed() "
                         "— the CRN derivation is not self-consistent; refusing to run")
    full_p = [playout_seed(probe_rid, j, salt) for j in range(m)]
    ladder = [k for k in (1, 2, 4, 8, 16, 32, 64, 128) if k <= m]
    for k in ladder:
        if world_seeds(probe_rid, k, salt) != full_w[:k]:
            raise SystemExit(
                f"[tier1_rust_leg] PREFIX-STABILITY VIOLATED at M={k} vs M={m}: the "
                "world seeds depend on M, so no B <= M/2 sub-read of this run is "
                "valid (PLAN_B_gt_16 §0.1). Refusing to run.")
    return {"ok": True, "salt": salt, "m": int(m),
            "prefix_stable_at": ladder,
            "derivation": "oracle_score_pilot.world_seed/playout_seed "
                          "= sha256(tag|rid|j|salt); M never enters",
            "probe_rid": probe_rid,
            "probe_world_seeds_head": full_w[:4],
            "probe_playout_seeds_head": full_p[:4]}


def preflight_m(m: int) -> dict:
    if not (1 <= int(m) <= M_MAX):
        raise SystemExit(f"[tier1_rust_leg] --m {m} out of range 1..{M_MAX} "
                         f"(PLAN_B_gt_16 §0.2 sizes the campaign at M=128)")
    return {"ok": True, "m": int(m), "m_max": M_MAX}


# --------------------------------------------------------------------------- #
# worker                                                                        #
# --------------------------------------------------------------------------- #
_G: dict = {}


def _init(cfg: dict) -> None:
    _G.update(cfg)


def _deck_hash_from_descriptions(descriptions) -> str:
    """The determinized world's deck witness. Same shape as the python leg's
    `oracle_score_pilot._deck_hash` (sha256 over NUL-separated descriptions,
    truncated to 16 hex chars) but computed over the RUST world's unseen deck —
    so it is a within-run/cross-leg witness, NOT a cross-backend one."""
    h = hashlib.sha256()
    for d in descriptions:
        h.update(str(d).encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


def score_one(item: dict, *, m: int, salt: str, max_plies: int,
              legal_mask_cache: bool, world_deck_witness: bool,
              strict_crn: bool = False, oracle_sims: int | None = None) -> dict:
    """Score ONE leg (one position, two picks, `m` CRN worlds) in rust.

    Pure apart from the `carc_rs` calls, so the unit tests can drive it directly
    on a banked fixture. Returns the `records/<rid>.json` document.
    """
    import carc_rs  # noqa: PLC0415
    from oracle_score_pilot import (playout_seed, position_delta,  # noqa: PLC0415
                                    world_seeds)

    rid = item["rid"]
    rec = {k: item.get(k) for k in (
        "rid", "root_id", "deck_seed", "ply", "salt", "pick_a", "pick_b",
        "root_player", "k_remaining", "game_phase", "phase_bucket", "n_legal",
        "h200_top2_q_gap", "solver_region")}
    for k in ("stratum", "rules_profile", "game_label", "bucket", "phase", "delta_q",
              "abs_delta_q", "action_played", "action_best", "stratifier_rule"):
        if k in item:
            rec[k] = item[k]
    rec.update({
        "schema": SCHEMA,
        "m": int(m), "oracle_policy": ORACLE_POLICY,
        # Recorded for record-shape parity with the python leg. A 1-ply argmax
        # continuation runs no search, so this knob is INERT here by construction
        # -- it is provenance, never a config the values depend on.
        "oracle_sims": oracle_sims,
        "world_seed_salt": salt,
        "arb_backend": "rust",
        "max_plies": int(max_plies),
        "legal_mask_cache": bool(legal_mask_cache),
    })
    t0 = time.time()
    try:
        deck_seed = str(int(item["deck_seed"]))
        actions = [int(a) for a in item["actions"]]
        ply = int(item["ply"])

        # --- root replay in the mirror: the checksum + legality gate the python
        # leg runs, done on the rust side so the two agree about the ROOT before
        # anything is priced.
        ms = carc_rs.MirrorState.from_seed(deck_seed)
        for a in actions[:ply]:
            ms.advance(int(a))
        rec["checksum_ok"] = bool(item.get("checksum") is None
                                  or ms.string_repr() == item["checksum"])
        if not rec["checksum_ok"]:
            rec.update(ok=False, error="checksum_mismatch")
            return rec
        legal = set(int(x) for x in ms.legal_actions())
        for tag in ("pick_a", "pick_b"):
            if int(item[tag]) not in legal:
                rec.update(ok=False, error=f"{tag}_illegal_at_root")
                return rec

        ws = world_seeds(rid, int(m), salt)
        ps = [playout_seed(rid, j, salt) for j in range(int(m))]
        rec["world_seeds"] = ws
        rec["playout_seeds"] = ps

        va, vb, pa, pb, cache_stats = carc_rs.tier1_leg(
            deck_seed, actions, ply,
            int(item["pick_a"]), int(item["pick_b"]), int(item["root_player"]),
            ws, ps, int(max_plies), bool(legal_mask_cache))

        rec["values_a"] = [float(x) for x in va]
        rec["values_b"] = [float(x) for x in vb]
        rec["playout_plies_a"] = [int(x) for x in pa]
        rec["playout_plies_b"] = [int(x) for x in pb]
        rec["legal_mask_cache_hits"] = int(cache_stats[0])
        rec["legal_mask_cache_misses"] = int(cache_stats[1])

        # --- CRN witness. `tier1_leg` builds ONE world per seed and hands it to
        # BOTH picks, so the pairing is structural; the recorded witness is the
        # world's own deck, which is what "same world" means here.
        rec["crn_witness"] = CRN_WITNESS_RUST if world_deck_witness else "structural"
        rec["crn_verified"] = True
        if world_deck_witness:
            wdh = [_deck_hash_from_descriptions(
                       carc_rs.tier1_world_deck(deck_seed, actions, ply, int(s)))
                   for s in ws]
            rec["world_deck_hash"] = wdh
            # A degenerate world draw (every seed producing the same completion)
            # would silently collapse the CRN sample to n=1. Recorded, not
            # asserted -- late plies legitimately have a 0- or 1-tile deck.
            rec["n_distinct_worlds"] = len(set(wdh))
            if len(wdh) != int(m):
                rec.update(ok=False, error="world_deck_witness_length_mismatch")
                return rec
        rec["crn_witness_note"] = (
            "carc_rs.tier1_leg determinizes ONCE per world_seeds[j] and plays "
            "both picks from that one world, so the CRN pairing is structural, "
            "not checked-after-the-fact. `world_deck_hash` records that world's "
            "unseen deck (carc_rs.tier1_world_deck). The python leg's "
            "afterstate_deck_hash_a/b are NOT emitted rather than faked — they "
            "are a different quantity computed on a different object graph.")

        # --- NO-OP WITNESS: do the two picks reach DIFFERENT boards? A zero
        # delta from two picks that transpose to one board means "the harness did
        # nothing", not "the moves are equivalent", so the python leg records it
        # per world. Here ONE comparison settles all M: `string_repr` differs
        # between worlds only through `len(deck)` / `next_tile`, and BOTH picks
        # share those within a world, so pick_a == pick_b is world-invariant.
        #
        # ⚠️ The keys themselves are computed on the ROOT deck, not on a
        # determinized world, so they are NOT comparable to the python leg's
        # per-world `afterstate_board_key_a/b`. Named apart for that reason.
        ka = ms                                   # `ms` is finished with; reuse it
        kb = carc_rs.MirrorState.from_seed(deck_seed)
        for a in actions[:ply]:
            kb.advance(int(a))
        ka.advance(int(item["pick_a"]))
        kb.advance(int(item["pick_b"]))
        key_a, key_b = ka.string_repr(), kb.string_repr()
        rec["afterstate_board_key_a_root"] = hashlib.sha256(
            key_a.encode()).hexdigest()[:16]
        rec["afterstate_board_key_b_root"] = hashlib.sha256(
            key_b.encode()).hexdigest()[:16]
        rec["distinct_afterstates"] = 0 if key_a == key_b else int(m)
        rec["distinct_afterstates_note"] = (
            "0 or m: the two picks either transpose to one board or they do not, "
            "and that answer is the same in every world. Root-deck board keys, "
            "NOT the python leg's per-world afterstate_board_key_a/b.")

        if strict_crn and not rec["crn_verified"]:
            rec.update(ok=False, error="crn_world_deck_mismatch")
            return rec

        rec.update(position_delta(rec["values_a"], rec["values_b"]))
        rec["ok"] = True
        return rec
    except Exception as exc:                                       # noqa: BLE001
        rec.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        return rec
    finally:
        rec["elapsed_secs"] = round(time.time() - t0, 3)


def _one(item: dict) -> dict:
    return score_one(item, m=_G["m"], salt=_G["salt"], max_plies=_G["max_plies"],
                     legal_mask_cache=_G["legal_mask_cache"],
                     world_deck_witness=_G["world_deck_witness"],
                     strict_crn=_G["strict_crn"],
                     oracle_sims=_G.get("oracle_sims"))


# --------------------------------------------------------------------------- #
# manifest                                                                      #
# --------------------------------------------------------------------------- #
def _git_rev() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                              # noqa: BLE001
        return None


def build_manifest(args, preflights: dict, rows_n: int, results: list,
                   wall: float) -> dict:
    """Fully-resolved config + provenance. House rule: every eval writes one, so
    a result never needs dirname archaeology."""
    ok = [r for r in results if r.get("ok")]
    bad = [r for r in results if not r.get("ok")]
    return {
        "schema": SCHEMA, "driver": "tier1_rust_leg", "design_doc": DESIGN_DOC,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_rev": _git_rev(),
        "python": sys.executable,
        "resolved_config": {
            "positions_jsonl": str(args.positions_jsonl),
            "rules_profile": args.rules_profile,
            "oracle_policy": ORACLE_POLICY,
            "arb_backend": "rust",
            "m": int(args.m), "m_max": M_MAX,
            "world_seed_salt": args.world_seed_salt,
            "oracle_sims": int(args.oracle_sims),
            "oracle_sims_note": "INERT: tier1-greedy is a 1-ply argmax, no search",
            "max_plies": int(args.max_plies),
            "legal_mask_cache": bool(args.legal_mask_cache),
            "world_deck_witness": bool(args.world_deck_witness),
            "strict_crn": bool(args.strict_crn),
            "workers": int(args.workers),
            "n": int(args.n),
            "resume": bool(args.resume),
            "out_root": str(args.out_root), "out_subdir": str(args.out_subdir),
        },
        "preflight": preflights,
        "n_rows_in": rows_n,
        "n_scored": len(results), "n_ok": len(ok), "n_failed": len(bad),
        "errors": sorted({r.get("error") for r in bad if r.get("error")}),
        "n_crn_verified": sum(1 for r in ok if r.get("crn_verified")),
        "elapsed_secs_sum": round(sum(float(r.get("elapsed_secs") or 0.0)
                                      for r in results), 3),
        "wall_secs": round(wall, 3),
        "cost_note": ("c = Σ elapsed_secs / n_playouts is the currency of record "
                      "(analyze_tiearb2.cost_block::c_from_elapsed_secs). It is "
                      "NOT computed here: a timing number is only meaningful on "
                      "an uncontended box, so cost is re-measured deliberately, "
                      "never harvested from a production leg."),
        "n_playouts": len(ok) * 2 * int(args.m),
    }


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--positions-jsonl", required=True)
    ap.add_argument("--rules-profile", default="walled")
    ap.add_argument("--m", type=int, default=32,
                    help=f"CRN worlds per position (1..{M_MAX}). The campaign's "
                         "shared run is M=128 (PLAN_B_gt_16 §0.2).")
    ap.add_argument("--world-seed-salt", default="tiletie-v1")
    ap.add_argument("--oracle-sims", type=int, default=100,
                    help="INERT for this judge (a 1-ply argmax continuation runs "
                         "no search). Accepted and recorded so the leg command "
                         "and the record shape match the pilot's.")
    ap.add_argument("--workers", "-W", type=int, default=14)
    ap.add_argument("--n", type=int, default=0,
                    help="0 = every line in --positions-jsonl. ALWAYS pass the "
                         "leg's own line count explicitly from a launcher: a "
                         "DIFFERENT subsample per leg destroys the cross-leg CRN "
                         "pairing the design rests on.")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--out-subdir", default="tier1-greedy")
    ap.add_argument("--max-plies", type=int, default=MAX_PLIES)
    ap.add_argument("--legal-mask-cache", action="store_true",
                    default=DEFAULT_LEGAL_MASK_CACHE)
    ap.add_argument("--no-legal-mask-cache", dest="legal_mask_cache",
                    action="store_false",
                    help="run the HONEST recomputed legal mask. NOT bit-comparable "
                         "with the python judge (which memoizes on a non-injective "
                         "key); see the module docstring.")
    ap.add_argument("--world-deck-witness", action="store_true", default=True)
    ap.add_argument("--no-world-deck-witness", dest="world_deck_witness",
                    action="store_false")
    ap.add_argument("--strict-crn", action="store_true", default=False)
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    return ap


def main(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.strict_crn and not args.world_deck_witness:
        raise SystemExit(
            "[tier1_rust_leg] --strict-crn with --no-world-deck-witness is a "
            "contradiction: with no recorded witness the CRN check has nothing "
            "to fail on and would pass vacuously. Drop one of the two flags.")

    preflights = {
        "m": preflight_m(args.m),
        "wheel": preflight_wheel(),
        "profile": preflight_profile(args.rules_profile),
        "seeds": preflight_seeds(args.world_seed_salt, int(args.m)),
    }
    for name, p in preflights.items():
        print(f"[tier1_rust_leg] preflight {name}: PASS "
              f"{ {k: v for k, v in p.items() if k != 'ok'} }", flush=True)

    from oracle_score_pilot import load_positions_jsonl  # noqa: PLC0415

    rows = load_positions_jsonl(args.positions_jsonl)
    if args.n:
        if int(args.n) != len(rows):
            print(f"[tier1_rust_leg] WARNING: --n {args.n} != {len(rows)} lines in "
                  f"{args.positions_jsonl}; scoring the first {args.n}", file=sys.stderr)
        rows = rows[:int(args.n)]

    out_dir = Path(args.out_root) / args.out_subdir
    (out_dir / "records").mkdir(parents=True, exist_ok=True)
    todo = rows
    if args.resume:
        todo = [r for r in rows
                if not (out_dir / "records" / f"{r['rid']}.json").exists()]
    print(f"[tier1_rust_leg] {len(rows)} rows ({len(todo)} to score) M={args.m} "
          f"W={args.workers} -> {out_dir}", flush=True)

    cfg = {"m": int(args.m), "salt": args.world_seed_salt,
           "max_plies": int(args.max_plies),
           "legal_mask_cache": bool(args.legal_mask_cache),
           "world_deck_witness": bool(args.world_deck_witness),
           "strict_crn": bool(args.strict_crn),
           "oracle_sims": int(args.oracle_sims)}
    t0 = time.time()
    if int(args.workers) <= 1 or len(todo) <= 1:
        _init(cfg)
        results = [_one(it) for it in todo]
    else:
        import multiprocessing as mp  # noqa: PLC0415

        with mp.Pool(int(args.workers), initializer=_init, initargs=(cfg,)) as pool:
            results = pool.map(_one, todo, chunksize=1)
    wall = time.time() - t0

    for rec in results:
        p = out_dir / "records" / f"{rec['rid']}.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rec, indent=2, sort_keys=True))
        os.replace(tmp, p)

    manifest = build_manifest(args, preflights, len(rows), results, wall)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"[tier1_rust_leg] scored={manifest['n_scored']} ok={manifest['n_ok']} "
          f"failed={manifest['n_failed']} wall={wall:.1f}s -> {out_dir}/manifest.json",
          flush=True)
    if manifest["n_failed"]:
        print(f"[tier1_rust_leg] errors: {manifest['errors']}", file=sys.stderr)
    return 0 if manifest["n_failed"] == 0 else 1


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    raise SystemExit(main())
