#!/usr/bin/env python3
"""TILE-TIE PRICING — the champion's actual pick at selfplay tile-tie positions
(DESIGN.md §2.3, §3.2, §6 threat 9).

Only the `selfplay` stratum needs this. `e4` positions are free — the champion's
real pick at a champion-played tile ply is already the archive's `action_played`
(the real game, at the real production budget). `selfplay` positions need a
FRESH production search, because CL-070 measured that reseeding ALONE flips
~26-30% of picks at fixed budget — the archived selfplay `action_played` is *a*
champion pick, not necessarily the SAME one a fresh search at these exact knobs
would make today, and DESIGN §2.3 wants the latter.

PLAIN SCRIPT (see `build_positions.py`'s module docstring). Selects its own
positions directly off the census (`stratum=="selfplay" and tie_exact and not
tie_actions_exact_truncated`, filtered to ONE `--rules-profile`, since
`CARCASSONNE_FIX_R9` is import-latched and this process can only run one rules
epoch), builds each `rid` with the EXACT SAME formula `build_positions.rid_for`
uses (`tt_sp_{deck_seed}_p{ply}`), so its output jsonl joins straight onto
`--champ-picks` there without any extra bookkeeping.

THE PICK ITSELF — cloned from `scripts/jcz_mining/mine_disagreements._search_pick`
(NOT imported — that module has heavy unrelated import-time side effects and a
different CLI contract; brief-mandated clone). Every load-bearing detail is
preserved:
  * `make_production_champion("fair", ..., verify=True, **ex.factory_kwargs())`
    with NO explicit `sims=`/`k_dets=` — the budget comes from
    `governance/PRODUCTION.yaml` (k8x1376 today) via the factory's own default,
    never hardcoded here. The RESOLVED values are read back off the built
    agent's own `.manifest["fair_deploy"]` and stamped into every output row.
  * `mirror_protocol.reseat(champ, deck_seed=..., actions=actions[:ply],
    move_idx=ply)` is MANDATORY — the rust mirror can only be REPLAYED onto a
    mid-game position, never constructed there directly, and `move_idx` is not
    cosmetic (the per-determinization seeds derive from it).
  * Execution: `mirror_protocol.resolve_execution("inherit", profile="desktop",
    rust_threads=1)` — the SAME resolution `ev_loss.grade_pass` uses.
    ⚠️ `rust_threads=1` deliberately (no inner parallelism): throughput comes
    from the OUTER `multiprocessing.Pool` of `--workers`, never from
    `parallel_workers`/`rust_threads`, or a W-wide pool would oversubscribe the
    box by 8x (the champion's own k_dets width).
  * Seed: `match.agent_seed(deck_seed, seat)` (scripts/jcz_match/match.py) —
    the exact deterministic seed `_search_pick` uses (`replicate` left at its
    default 0).
  * The root is replayed with `root_replay.replay_actions(deck_seed, actions,
    ply, game_kwargs=...)` and `game.string_representation(board)` is asserted
    == the row's `checksum` BEFORE searching — a desynced replay must never
    silently price the wrong position.

BEST-EFFORT BY CONTRACT (mirrors `_search_pick`'s own docstring: "strictly
best-effort and must never be able to abort a run"): any per-position failure
(checksum mismatch, illegal root, `ProvenanceError`, timeout, engine exception)
is recorded as a row with `error` set and `champ_action=None`; it never takes
the pool down.

THE FREE CL-070 CROSS-CHECK (DESIGN §2.3 footnote / §6 threat 9). For every
processed root, also read the CL-070 bank's own `q_pick_by_level["2752"]`
(the SAME total budget, 11008, but the k4 allocation, not the champion's k8) —
`records/s{deck_seed}_p{ply}_r{salt}.json` for salt in {1,2,3} — and report:
  * `k4_pick_2752`         — [salt1, salt2, salt3] picks (None where absent)
  * `k4_pick_agrees_with_champ` — True iff EVERY available salt's k4 pick
    equals the champion's own fresh pick, False if any disagree, None if no
    salt is available or the champion pick itself failed. (A strict
    ALL-agree definition, not "at least one" — chosen because it is the one
    that is directly falsifiable per-salt and the disagreement COUNT is
    already visible via `k4_pick_2752` itself for a softer read.)
  * `k4_self_agreement`     — True iff the available salts agree with EACH
    OTHER (regardless of the champion), i.e. how often a k4x2752 search agrees
    with its own reseed at this tied position — a direct read of DESIGN §6
    threat 9's question ("how often does the champion-budget search even
    agree with itself inside a tied set").

Output: one jsonl row per rid, `--resume`-able (skips rids already present),
niced. `manifest.json` alongside.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# --- Production leaf env -- byte-identical to oracle_score_pilot._CANON_ENV / --- #
# eval_fair_puct._CANON_ENV. MUST precede any carcassonne_ai import (DEFAULT_CONFIG
# is import-frozen).
_CANON_ENV = {
    "CARCASSONNE_V25_CAP": "8",
    "CARCASSONNE_V25_OPP_CAP": "8",
    "CARCASSONNE_V25_DROP_THREE_OPEN": "0",
    "CARCASSONNE_V29_MEEPLE_CURVE": "-8,-4,-1,0,2,3,4,5",
    "CARCASSONNE_V25_MEEPLE_K": "2.0",
    "CARCASSONNE_V25_VALUE_BLEND": "0",
    "CARCASSONNE_USE_FLAT_LEAF": "1",
    "CARCASSONNE_USE_CY_LEAF": "1",
    "CARCASSONNE_USE_CY_REPR": "1",
    "CUDA_VISIBLE_DEVICES": "",
    "OMP_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
}
for _k, _v in _CANON_ENV.items():
    os.environ.setdefault(_k, _v)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC_ROOT = os.environ.get("CARC_SRC_ROOT") or str(REPO / "src")
for _p in (SRC_ROOT, str(REPO / "scripts" / "measurement_infra"),
          str(REPO / "scripts" / "jcz_match"), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import argparse             # noqa: E402
import json                 # noqa: E402
import multiprocessing as mp  # noqa: E402
import subprocess           # noqa: E402
import time                 # noqa: E402

import build_positions as BP  # noqa: E402

SCHEMA = "carcassonne-tiletie-champ-picks/v1"
DESIGN_DOC = "measurement/tiletie_pricing_20260812/DESIGN.md"

DEFAULT_CENSUS_ROWS = REPO / "measurement/tiletie_pricing_20260812/census/rows.jsonl"
DEFAULT_OUT = REPO / "measurement/tiletie_pricing_20260812/champ_picks/champ_picks.jsonl"
DEFAULT_BANK_RECORDS_DIR = Path(BP._share(
    "classical_search/move_agreement_k4_b28e9/records"))
DEFAULT_K4_LEVEL = "2752"


# --------------------------------------------------------------------------- #
# selfplay position selection -- SAME rid formula as build_positions.rid_for    #
# --------------------------------------------------------------------------- #
def load_selfplay_positions(census_rows_path, rules_profile: str) -> list:
    """Every `stratum=="selfplay"` census row that qualifies for scoring
    (`tie_exact and not tie_actions_exact_truncated`), filtered to ONE
    `rules_profile` (R9 is import-latched: one profile per process)."""
    rows = BP.load_census_rows(census_rows_path)
    selected = BP.select_positions(rows)
    out = []
    n_other_profile = 0
    for row in selected:
        if row["stratum"] != "selfplay":
            continue
        if row["rules_profile"] != rules_profile:
            n_other_profile += 1
            continue
        out.append(row)
    out.sort(key=BP.rid_for)
    return out, n_other_profile


# --------------------------------------------------------------------------- #
# the champion pick -- cloned from mine_disagreements._search_pick               #
# --------------------------------------------------------------------------- #
def champion_search_pick(game, board, deck_seed: int, seat: int, actions, ply: int):
    """The production champion's FULL-SEARCH action at this root. Returns
    (action, k_dets, sims_per_det, backend, secs). Raises on any failure --
    the CALLER wraps this in try/except (best-effort by contract, see module
    docstring)."""
    import match as JM
    from carcassonne_ai import mirror_protocol as MP
    from carcassonne_ai.champion_factory import make_production_champion

    ex = MP.resolve_execution("inherit", profile="desktop", rust_threads=1)
    t0 = time.time()
    champ = make_production_champion(
        "fair", game=game, seed=JM.agent_seed(int(deck_seed), int(seat)),
        verify=True, **ex.factory_kwargs())
    MP.reseat(champ, deck_seed=int(deck_seed), actions=[int(a) for a in actions[:ply]],
             move_idx=int(ply))
    action = int(champ.choose_action(board))
    secs = time.time() - t0
    fd = champ.manifest.get("fair_deploy", {})
    return (action, int(fd.get("k_dets", 0)), int(fd.get("sims_per_det", 0)),
           ex.backend, secs)


# --------------------------------------------------------------------------- #
# worker                                                                        #
# --------------------------------------------------------------------------- #
_G: dict = {}


def _init(game_kwargs: dict, rules_profile: str) -> None:
    _G["game_kwargs"] = dict(game_kwargs or {})
    _G["rules_profile"] = rules_profile


def _cell(item: tuple) -> dict:
    """One selfplay row -> one output record. Best-effort: NEVER raises out of
    this function (mirrors `mine_disagreements._sp_cell` / `_search_pick`'s own
    contract)."""
    rid, root_id, deck_seed, ply, seat, actions, checksum = item
    rec = {"rid": rid, "root_id": root_id, "deck_seed": int(deck_seed),
          "ply": int(ply), "seat": int(seat)}
    t0 = time.time()
    try:
        import root_replay as RR

        game, board = RR.replay_actions(int(deck_seed), actions, int(ply),
                                        game_kwargs=_G.get("game_kwargs"))
        cks = game.string_representation(board)
        if checksum is not None and cks != checksum:
            raise ValueError(f"checksum_mismatch: expected {checksum!r}, got {cks!r}")
        action, k_dets, sims, backend, secs = champion_search_pick(
            game, board, int(deck_seed), int(seat), actions, int(ply))
        rec.update(champ_action=action, champ_secs=round(secs, 3), sims=sims,
                  k_dets=k_dets, backend=backend, error=None)
    except Exception as exc:                                    # noqa: BLE001
        rec.update(champ_action=None, champ_secs=round(time.time() - t0, 3),
                  sims=None, k_dets=None, backend=None,
                  error=f"{type(exc).__name__}: {exc}")
    return rec


# --------------------------------------------------------------------------- #
# the free CL-070 cross-check (DESIGN §2.3 footnote / §6 threat 9)              #
# --------------------------------------------------------------------------- #
def bank_root_key(deck_seed: int, ply: int) -> str:
    """The CL-070 bank's OWN root-id convention (`s{deck_seed}_p{ply}`,
    `load_disagreements` / `gate_oracle_pilot_backend.load_items`) -- a
    DIFFERENT namespace from this module's own `root_id`
    (`build_positions.root_id_for` -> `sp_{deck_seed}`). Do not conflate them:
    the bank's on-disk filenames (`records/s{deck_seed}_p{ply}_r{salt}.json`)
    only resolve under this convention."""
    return f"s{int(deck_seed)}_p{int(ply)}"


def load_k4_picks(records_dir, bank_root: str, level: str = DEFAULT_K4_LEVEL,
                  salts=(1, 2, 3)) -> list:
    """[pick_salt1, pick_salt2, pick_salt3] from the CL-070 bank's own
    `records/{bank_root}_r{salt}.json` (`bank_root` = `bank_root_key(deck_seed,
    ply)`, NOT this module's own `root_id`). `None` where that (root, salt)
    record is absent or has no pick at `level`."""
    out = []
    for salt in salts:
        p = Path(records_dir) / f"{bank_root}_r{salt}.json"
        pick = None
        if p.is_file():
            try:
                d = json.loads(p.read_text())
                q = d.get("q_pick_by_level") or {}
                v = q.get(str(level))
                pick = int(v) if v is not None else None
            except (json.JSONDecodeError, OSError, ValueError, TypeError):
                pick = None
        out.append(pick)
    return out


def k4_cross_check(k4_picks: list, champ_action) -> dict:
    """See module docstring for the exact (documented, not obvious) definitions
    of `k4_pick_agrees_with_champ` (ALL available salts must agree) and
    `k4_self_agreement` (do the available salts agree with EACH OTHER)."""
    available = [v for v in k4_picks if v is not None]
    if not available or champ_action is None:
        agrees = None
    else:
        agrees = all(v == champ_action for v in available)
    self_agree = None if len(available) < 2 else (len(set(available)) == 1)
    return {"k4_pick_2752": k4_picks, "k4_pick_agrees_with_champ": agrees,
           "k4_self_agreement": self_agree}


# --------------------------------------------------------------------------- #
# driver                                                                        #
# --------------------------------------------------------------------------- #
def _git_rev(path) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


def run(args) -> dict:
    from carcassonne_ai import rules_profile as RP

    # Verify (not set -- R9 is import-latched, see the profile CLI docs) that
    # the process env matches the profile this leg is about to score under.
    prof = RP.activate(args.rules_profile)
    if RP.r9_env_on() != prof.r9_env_expected:
        raise SystemExit(
            f"CARCASSONNE_FIX_R9 is latched at {int(RP.r9_env_on())} but profile "
            f"{prof.name!r} expects {int(prof.r9_env_expected)} -- export it before "
            "launch, one process per rules epoch (same discipline as "
            "oracle_score_pilot.py / run_farmwar.py).")

    try:
        os.nice(int(args.nice))
    except OSError:
        pass

    rows, n_other_profile = load_selfplay_positions(args.census_rows, args.rules_profile)
    print(f"[champ_picks] {len(rows)} selfplay tied positions under profile "
         f"{args.rules_profile!r} ({n_other_profile} skipped -- other profiles)")

    items = []
    for row in rows:
        rid = BP.rid_for(row)
        root_id = BP.root_id_for(row)
        items.append((rid, root_id, int(row["deck_seed"]), int(row["ply"]),
                     int(row["seat"]), row["checksum"]))
    if args.limit and int(args.limit) > 0:
        items = items[: int(args.limit)]

    out_path = Path(args.out)
    out_dir = out_path.parent
    records_dir = out_dir / "records"
    records_dir.mkdir(parents=True, exist_ok=True)

    todo = items
    if args.resume:
        todo = [it for it in items if not (records_dir / f"{it[0]}.json").exists()]
        print(f"[champ_picks] resume: {len(items) - len(todo)} already done, "
             f"{len(todo)} to go")

    bank_roots = champ_games = None

    def _actions_for(rid, root_id, deck_seed, ply):
        nonlocal bank_roots, champ_games
        row = row_by_rid[rid]
        if bank_roots is None:
            bank_roots = BP.load_bank_roots(args.bank_roots)
            champ_games = BP.load_champ_games(args.champ_games)
        return BP.resolve_selfplay_actions(row, bank_roots, champ_games)

    row_by_rid = {BP.rid_for(r): r for r in rows}

    jobs = []
    for rid, root_id, deck_seed, ply, seat, checksum in todo:
        actions = _actions_for(rid, root_id, deck_seed, ply)
        jobs.append((rid, root_id, deck_seed, ply, seat, actions, checksum))

    game_kwargs = prof.game_kwargs()
    t0 = time.time()
    if jobs:
        w = max(1, min(int(args.workers), len(jobs)))
        ctx = mp.get_context("fork")
        with ctx.Pool(w, initializer=_init, initargs=(game_kwargs, args.rules_profile)) as pool:
            for i, rec in enumerate(pool.imap_unordered(_cell, jobs), 1):
                p = records_dir / f"{rec['rid']}.json"
                tmp = p.with_suffix(".tmp")
                tmp.write_text(json.dumps(rec))
                os.replace(tmp, p)
                flag = "ok" if rec.get("error") is None else f"FAIL {rec['error']}"
                print(f"[{i}/{len(jobs)}] {rec['rid']} {flag} "
                     f"action={rec.get('champ_action')} {rec.get('champ_secs')}s",
                     flush=True)

    # Re-read every record (so --resume assembles the FULL jsonl, not just this
    # run's slice) and join the free CL-070 cross-check.
    out_rows = []
    n_ok = n_err = 0
    for rid, root_id, deck_seed, ply, seat, checksum in items:
        p = records_dir / f"{rid}.json"
        if not p.is_file():
            continue
        rec = json.loads(p.read_text())
        k4_picks = load_k4_picks(args.bank_records_dir, bank_root_key(deck_seed, ply))
        rec.update(k4_cross_check(k4_picks, rec.get("champ_action")))
        out_rows.append(rec)
        if rec.get("error"):
            n_err += 1
        else:
            n_ok += 1
    out_rows.sort(key=lambda r: r["rid"])
    out_path.write_text("".join(json.dumps(r) + "\n" for r in out_rows))

    manifest = {
        "schema": SCHEMA, "driver": "champ_picks", "design_doc": DESIGN_DOC,
        "census_rows": str(args.census_rows), "rules_profile": args.rules_profile,
        "bank_roots": str(args.bank_roots), "champ_games": str(args.champ_games),
        "bank_records_dir": str(args.bank_records_dir), "out": str(out_path),
        "workers": int(args.workers), "resume": bool(args.resume),
        "limit": int(args.limit) if args.limit else None,
        "n_selfplay_qualifying": len(rows), "n_other_profile_skipped": n_other_profile,
        "n_attempted_this_run": len(jobs), "n_rows_total": len(out_rows),
        "n_ok": n_ok, "n_error": n_err,
        "wall_secs": round(time.time() - t0, 1), "code_rev": _git_rev(REPO),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[champ_picks] {n_ok} ok, {n_err} errors, {len(out_rows)} rows total "
         f"-> {out_path}")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--census-rows", default=str(DEFAULT_CENSUS_ROWS))
    ap.add_argument("--rules-profile", default="walled",
                    help="ONE profile per process (R9 is import-latched); DESIGN "
                         "§3.2: the selfplay stratum is entirely 'walled' today")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--bank-roots", default=BP.DEFAULT_BANK_ROOTS)
    ap.add_argument("--bank-records-dir", default=str(DEFAULT_BANK_RECORDS_DIR))
    ap.add_argument("--champ-games", default=str(BP.DEFAULT_CHAMP_GAMES))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0,
                    help="cap the number of positions processed THIS invocation "
                         "(0 = no cap) -- for smoke-testing; each costs "
                         "~t_champ_secs (DEFAULT_T_CHAMP_SECS in build_positions.py, "
                         "~13.76s) of worker time")
    ap.add_argument("--resume", action="store_true", default=True)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--nice", type=int, default=19)
    args = ap.parse_args(argv)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
