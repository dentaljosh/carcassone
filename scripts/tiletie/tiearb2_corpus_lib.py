#!/usr/bin/env python3
"""tiearb2_20260816 CORPUS ASSEMBLY helpers — mining only, no statistic.

This module is the *support* half of `build_tiearb2_corpus.sh`. It computes NO
strength / headroom / arbitration statistic: it only

  1. VERIFIES the freshly collected champion self-play games (realized game
     count + every `deck_seed` inside the declared band), and
  2. EMITS the spent-corpus rid exclusion list that `build_positions.py
     --exclude-rids` consumes (defence in depth; the two corpora are already
     root-disjoint by band, so `n_removed_from_supply == 0` is the EXPECTED
     outcome, not a bug), and
  3. STAGES a read-only "shadow repo root" so `transposition_census.py` can be
     run UNMODIFIED against a champ-games file it has no flag for.

⚠️ WHY THE SHADOW ROOT EXISTS (a real, verified gap — not a preference)
   `scripts/tiletie/transposition_census.py` resolves the self-play action
   sequences from TWO HARD-CODED paths (see its `main()`):

       /mnt/c/carc-shared/classical_search/move_agreement_k4_b28e9/roots.jsonl
       <REPO>/measurement/champ_action_logs/champ_games.jsonl

   It has **no `--champ-games` flag** (unlike `champ_picks.py` and
   `build_positions.py`, which both do). The tiearb2 corpus lives in a NEW
   deck-seed band (281000000xx) that appears in NEITHER of those files, so every
   row would fail to resolve, be counted in `n_unresolved`, and the script would
   exit 3 with an empty map — which in turn makes `build_positions.py` raise
   `KeyError: afterstate map does not cover ...`.

   `transposition_census.py` MUST NOT be edited (a self-play generation run is
   live). Its `REPO` is `Path(__file__).resolve().parents[2]`, and its only uses
   of `REPO` are the two `sys.path` inserts plus those two data paths. So the
   non-invasive fix is to invoke it through a shadow tree whose `parents[2]` is
   a directory WE control:

       shadow/scripts/tiletie/transposition_census.py   HARD LINK (same inode —
                                                        `.resolve()` does not
                                                        collapse hard links, so
                                                        REPO becomes `shadow`)
       shadow/scripts/tiletie/{build_positions,chain_census}.py   symlinks
       shadow/scripts/measurement_infra                 symlink to the real dir
       shadow/measurement/champ_action_logs/champ_games.jsonl
                                                        symlink to OUR corpus
       shadow/measurement/e4_games                      empty dir (no e4 rows)

   Every imported module still `.resolve()`s to the REAL repo (symlinks are
   followed), so `build_positions` / `chain_census` / `root_replay` keep their
   real `REPO`, their real leaf env and the real `LEAF_HASH_OF_RECORD` assert.
   Only `transposition_census.py`'s own two data paths move. The hard link is
   re-created (and its inode asserted equal) on every run, so the shadow can
   never go stale against the real script.

Subcommands
    verify-champgames   band + count assertion over a collected champ-games jsonl
    emit-exclude-rids   the spent corpus's complete rid list -> newline file
    stage-shadow        build/refresh the shadow root, print the entry script
    split-champgames    carve one collected jsonl into a deck-seed SUB-band (W6)
    select-capped       the S2 <=3-capped-plies-per-root selection (W6)

The last two were added for the tie-arbiter WIDENING run
(`measurement/tiearb_widening_20260817/`), whose corpus is TWO root-disjoint
strata carved out of ONE fresh game set by deck-seed sub-band, with the S2
stratum built two-pass. Both are outcome-blind by construction: the sub-band is
a property of the deck seed and `capped_at_4` is knowable BEFORE any pricing, so
neither can see a statistic.

Nothing here imports the engine, `carcassonne_ai`, numpy or torch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

#: The tiearb2 generation band (`gen_fair_distill.py --seed-start 28100000000
#: --games 850`). Inclusive on both ends.
SEED_LO_DEFAULT = 28100000000
SEED_HI_DEFAULT = 28100000849

#: Modules `transposition_census.py` imports off `REPO/scripts/tiletie` once the
#: shadow root is in play. Symlinked (so they keep the REAL repo as their own
#: `REPO`); only the entry script itself is hard-linked.
SHADOW_TILETIE_SYMLINKS = ("build_positions.py", "chain_census.py")
SHADOW_ENTRY = "transposition_census.py"


# --------------------------------------------------------------------------- #
# 1. champ-games verification (band + realized count)                          #
# --------------------------------------------------------------------------- #
def read_champ_games(path) -> list[dict]:
    """Parse a `collect_action_logs.py --out` jsonl. Blank lines ignored."""
    out = []
    for i, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as exc:                      # noqa: PERF203
            raise ValueError(f"{path}:{i}: not JSON ({exc})") from exc
    return out


def verify_champ_games(path, *, seed_lo: int = SEED_LO_DEFAULT,
                       seed_hi: int = SEED_HI_DEFAULT,
                       expect_games: int | None = None,
                       min_games: int | None = None) -> dict:
    """Assert the collected corpus is the one we think it is.

    Raises `ValueError` (loudly, naming the offending seeds) if ANY `deck_seed`
    falls outside `[seed_lo, seed_hi]`, if any seed is duplicated, or if the
    realized game count is below `min_games`. `expect_games` is the NOMINAL
    target: a shortfall is reported in the returned dict and only fails the
    check when `min_games` (default: `expect_games`) is not met.
    """
    games = read_champ_games(path)
    seeds = [int(g["deck_seed"]) for g in games]
    n = len(games)
    out_of_band = sorted({s for s in seeds if not (seed_lo <= s <= seed_hi)})
    dupes = sorted({s for s in seeds if seeds.count(s) > 1}) if len(set(seeds)) != n else []

    if min_games is None:
        min_games = expect_games

    report = {
        "path": str(path),
        "n_games_realized": n,
        "n_games_expected": expect_games,
        "n_games_min_required": min_games,
        "seed_band": [seed_lo, seed_hi],
        "seed_min_observed": min(seeds) if seeds else None,
        "seed_max_observed": max(seeds) if seeds else None,
        "n_distinct_seeds": len(set(seeds)),
        "n_out_of_band": len(out_of_band),
        "n_duplicate_seeds": len(dupes),
        "band_ok": not out_of_band,
        "count_ok": (min_games is None) or (n >= int(min_games)),
        "shortfall_vs_expected": (None if expect_games is None
                                  else int(expect_games) - n),
        "sha256_of_sorted_seeds": hashlib.sha256(
            "\n".join(str(s) for s in sorted(seeds)).encode()).hexdigest(),
    }

    if n == 0:
        raise ValueError(f"{path}: ZERO games collected — refusing to proceed")
    if out_of_band:
        raise ValueError(
            f"{path}: {len(out_of_band)} deck_seed(s) OUTSIDE the declared band "
            f"[{seed_lo}, {seed_hi}] — e.g. {out_of_band[:5]}. The corpus is not "
            f"the tiearb2 generation; refusing to proceed.")
    if dupes:
        raise ValueError(
            f"{path}: {len(dupes)} duplicated deck_seed(s) — e.g. {dupes[:5]}. "
            f"A duplicated seed would double-weight a game in the census.")
    if not report["count_ok"]:
        raise ValueError(
            f"{path}: only {n} games realized but {min_games} required "
            f"(nominal target {expect_games}). Re-run generation or lower the "
            f"floor DELIBERATELY via --min-games.")
    return report


# --------------------------------------------------------------------------- #
# 2. spent-corpus rid exclusion list                                            #
# --------------------------------------------------------------------------- #
def spent_rids(arms_path) -> list[str]:
    """Every rid of the spent corpus, sorted. `ARMS.json` is a dict keyed by rid
    (`build_positions.build_arms_index`), so the keys ARE the complete rid list —
    never re-derived from the leg files."""
    arms = json.loads(Path(arms_path).read_text())
    if not isinstance(arms, dict):
        raise ValueError(f"{arms_path}: expected a rid-keyed object, got "
                         f"{type(arms).__name__}")
    return sorted(arms)


def emit_exclude_rids(arms_path, out_path) -> list[str]:
    """Write the spent rid list as the newline-delimited file
    `build_positions.py --exclude-rids` parses (it strips `#` comments and blank
    lines, so a header comment is safe and self-documenting)."""
    rids = spent_rids(arms_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    header = (f"# spent tile-tie corpus rid list — {len(rids)} rids\n"
              f"# source: {arms_path}\n"
              f"# consumed by: build_positions.py --exclude-rids (DESIGN §7.3)\n"
              f"# EXPECTED effect on the tiearb2 corpus: n_removed_from_supply == 0\n"
              f"# (the two corpora are root-disjoint by deck-seed band; this file\n"
              f"#  is defence in depth, not the mechanism).\n")
    out_path.write_text(header + "".join(r + "\n" for r in rids))
    return rids


# --------------------------------------------------------------------------- #
# 2b. deck-seed SUB-BAND split (W6) — the S1/S2 root-disjointness MECHANISM     #
# --------------------------------------------------------------------------- #
def split_champ_games(path, out_path, *, seed_lo: int, seed_hi: int) -> dict:
    """Carve the games whose `deck_seed` lies in `[seed_lo, seed_hi]` into their
    own jsonl.

    This IS the widening run's root-disjointness mechanism: S1 takes band
    `+0…+349` and S2 `+350…+849` off ONE generation, so no game can appear in
    both strata and `strata_root_overlap == 0` is true by construction (the W5
    gate then PROVES it rather than asserting it). Outcome-blind: a deck seed is
    a property of the generation, not of any statistic."""
    games = read_champ_games(path)
    keep = [g for g in games if seed_lo <= int(g["deck_seed"]) <= seed_hi]
    if not keep:
        raise ValueError(
            f"{path}: NO game has a deck_seed in [{seed_lo}, {seed_hi}] — the "
            f"sub-band is empty; refusing to write a corpus with no games.")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(json.dumps(g) + "\n" for g in keep))
    seeds = sorted(int(g["deck_seed"]) for g in keep)
    return {"path": str(out_path), "n_in": len(games), "n_kept": len(keep),
            "seed_band": [seed_lo, seed_hi],
            "seed_min_observed": seeds[0], "seed_max_observed": seeds[-1],
            "sha256_of_sorted_seeds": hashlib.sha256(
                "\n".join(str(s) for s in seeds).encode()).hexdigest()}


# --------------------------------------------------------------------------- #
# 2c. the S2 two-pass selection (W6): <= N capped plies per root                #
# --------------------------------------------------------------------------- #
def select_capped_rids(arms_path, *, max_per_root: int = 3,
                       seed: int = 20260819) -> dict:
    """Pick at most `max_per_root` CAPPED rids per root from a pass-1 ARMS.json.

    ⚠️ OUTCOME-BLIND BY CONSTRUCTION. `capped_at_4` is a property of the
    deduped tie-set SIZE, knowable before a single playout — pass 1 is built
    with `--allow-missing-champ-picks` and prices nothing. The within-root order
    is a seeded shuffle keyed on `(root_id, seed)` rather than the rid's
    lexicographic order, so the selection cannot correlate with ply index
    (an early-ply bias would silently re-weight the phase mix).

    Returns `{"selected": [...], "excluded": [...], ...}` — `excluded` is every
    OTHER rid in the file (uncapped rids included: S2 is a capped-only stratum),
    which is what `build_positions.py --exclude-rids` consumes for pass 2, since
    it has no `--include-rids` flag."""
    arms = json.loads(Path(arms_path).read_text())
    if not isinstance(arms, dict):
        raise ValueError(f"{arms_path}: expected a rid-keyed object, got "
                         f"{type(arms).__name__}")
    by_root: dict = {}
    n_capped = 0
    for rid, meta in sorted(arms.items()):
        if not meta.get("capped_at_4"):
            continue
        n_capped += 1
        by_root.setdefault(str(meta["root_id"]), []).append(rid)

    selected = []
    for root, rids in sorted(by_root.items()):
        order = sorted(rids)
        random.Random(_stable_seed_int(root, seed)).shuffle(order)
        selected.extend(sorted(order[:max_per_root]))
    selected = sorted(selected)
    excluded = sorted(set(arms) - set(selected))
    return {
        "arms_path": str(arms_path), "max_per_root": max_per_root, "seed": seed,
        "n_rids_total": len(arms), "n_capped": n_capped,
        "n_roots_with_capped": len(by_root),
        "n_selected": len(selected), "n_excluded": len(excluded),
        "selected": selected, "excluded": excluded,
    }


def _stable_seed_int(*parts) -> int:
    """PYTHONHASHSEED-independent integer seed (the `build_positions`
    discipline: never `random.Random(<tuple>)`)."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFF


def write_rid_list(rids, out_path, header_lines=()) -> int:
    """Write a `build_positions.py --exclude-rids` list (comments allowed)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    head = "".join(f"# {ln}\n" for ln in header_lines)
    out_path.write_text(head + "".join(str(r) + "\n" for r in rids))
    return len(list(rids))


# --------------------------------------------------------------------------- #
# 3. shadow repo root for the unmodified transposition_census.py               #
# --------------------------------------------------------------------------- #
def _link(src: Path, dst: Path, *, hard: bool) -> None:
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    if hard:
        os.link(src, dst)
    else:
        dst.symlink_to(src)


def stage_shadow(shadow_root, *, repo=REPO, champ_games) -> Path:
    """Build/refresh the shadow tree described in the module docstring.

    Returns the path of the entry script to invoke. Raises `RuntimeError` if the
    hard link did not land on the real script's inode, or if `.resolve()` on the
    entry script escapes the shadow root (which would silently restore the real
    `REPO` and re-introduce the wrong champ-games file)."""
    shadow_root = Path(shadow_root).resolve()
    repo = Path(repo)
    champ_games = Path(champ_games).resolve()
    if not champ_games.is_file():
        raise FileNotFoundError(f"champ games file not found: {champ_games}")

    if shadow_root.exists():
        shutil.rmtree(shadow_root)

    tiletie = shadow_root / "scripts" / "tiletie"
    tiletie.mkdir(parents=True)

    real_entry = repo / "scripts" / "tiletie" / SHADOW_ENTRY
    entry = tiletie / SHADOW_ENTRY
    _link(real_entry, entry, hard=True)
    for name in SHADOW_TILETIE_SYMLINKS:
        _link(repo / "scripts" / "tiletie" / name, tiletie / name, hard=False)

    # whole-directory symlink: `root_replay` and its siblings keep the real repo
    _link(repo / "scripts" / "measurement_infra",
          shadow_root / "scripts" / "measurement_infra", hard=False)

    cal = shadow_root / "measurement" / "champ_action_logs"
    cal.mkdir(parents=True)
    _link(champ_games, cal / "champ_games.jsonl", hard=False)
    (shadow_root / "measurement" / "e4_games").mkdir(parents=True)

    if os.stat(entry).st_ino != os.stat(real_entry).st_ino:
        raise RuntimeError(
            f"shadow entry {entry} is NOT the same inode as {real_entry} — the "
            f"hard link failed (different filesystem?), so the shadow would run "
            f"a stale copy. Refusing.")
    if entry.resolve() != entry:
        raise RuntimeError(
            f"shadow entry resolves outside itself ({entry.resolve()}) — an "
            f"ancestor is a symlink, so REPO would fall back to the real tree.")
    if entry.resolve().parents[2] != shadow_root:
        raise RuntimeError(
            f"shadow REPO would be {entry.resolve().parents[2]}, not "
            f"{shadow_root}")
    return entry


# --------------------------------------------------------------------------- #
# CLI                                                                           #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify-champgames")
    v.add_argument("--path", required=True)
    v.add_argument("--seed-lo", type=int, default=SEED_LO_DEFAULT)
    v.add_argument("--seed-hi", type=int, default=SEED_HI_DEFAULT)
    v.add_argument("--expect-games", type=int, default=None)
    v.add_argument("--min-games", type=int, default=None)
    v.add_argument("--out", default=None, help="write the report JSON here")
    v.add_argument("--print-n", action="store_true",
                   help="print ONLY the realized game count (for shell capture)")

    e = sub.add_parser("emit-exclude-rids")
    e.add_argument("--arms", required=True)
    e.add_argument("--out", required=True)

    s = sub.add_parser("stage-shadow")
    s.add_argument("--shadow-root", required=True)
    s.add_argument("--champ-games", required=True)
    s.add_argument("--repo", default=str(REPO))

    sp = sub.add_parser("split-champgames")
    sp.add_argument("--path", required=True)
    sp.add_argument("--out", required=True)
    sp.add_argument("--seed-lo", type=int, required=True)
    sp.add_argument("--seed-hi", type=int, required=True)
    sp.add_argument("--print-n", action="store_true")

    sc = sub.add_parser("select-capped")
    sc.add_argument("--arms", required=True, help="the PASS-1 ARMS.json")
    sc.add_argument("--max-per-root", type=int, default=3)
    sc.add_argument("--seed", type=int, default=20260819)
    sc.add_argument("--out-exclude", required=True,
                    help="rid list for build_positions --exclude-rids (pass 2)")
    sc.add_argument("--out-report", default=None)

    a = ap.parse_args(argv)

    if a.cmd == "verify-champgames":
        rep = verify_champ_games(a.path, seed_lo=a.seed_lo, seed_hi=a.seed_hi,
                                 expect_games=a.expect_games,
                                 min_games=a.min_games)
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(json.dumps(rep, indent=2, sort_keys=True))
        if a.print_n:
            print(rep["n_games_realized"])
        else:
            print(json.dumps(rep, indent=2, sort_keys=True))
            if rep["shortfall_vs_expected"]:
                print(f"[tiearb2] NOTE: {rep['shortfall_vs_expected']} game(s) "
                      f"short of the nominal target — the realized count is "
                      f"what downstream phases must use.", file=sys.stderr)
        return 0

    if a.cmd == "emit-exclude-rids":
        rids = emit_exclude_rids(a.arms, a.out)
        print(f"[tiearb2] wrote {len(rids)} spent rids -> {a.out}")
        return 0

    if a.cmd == "stage-shadow":
        entry = stage_shadow(a.shadow_root, repo=Path(a.repo),
                             champ_games=a.champ_games)
        print(entry)
        return 0

    if a.cmd == "split-champgames":
        rep = split_champ_games(a.path, a.out, seed_lo=a.seed_lo,
                                seed_hi=a.seed_hi)
        if a.print_n:
            print(rep["n_kept"])
        else:
            print(json.dumps(rep, indent=2, sort_keys=True))
        return 0

    if a.cmd == "select-capped":
        rep = select_capped_rids(a.arms, max_per_root=a.max_per_root,
                                 seed=a.seed)
        write_rid_list(rep["excluded"], a.out_exclude, header_lines=(
            f"S2 pass-2 exclusion list: every rid NOT selected as one of the",
            f"<= {a.max_per_root} capped plies of its root (seed {a.seed}).",
            f"{rep['n_selected']} selected / {rep['n_excluded']} excluded of "
            f"{rep['n_rids_total']} pass-1 rids ({rep['n_capped']} capped).",
            "build_positions.py has no --include-rids, so the SELECTION is",
            "expressed as the exclusion of its complement.",
            "OUTCOME-BLIND: capped_at_4 is knowable before any playout."))
        if a.out_report:
            Path(a.out_report).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out_report).write_text(json.dumps(rep, indent=2,
                                                     sort_keys=True))
        print(f"[widening] selected {rep['n_selected']} capped rid(s) over "
              f"{rep['n_roots_with_capped']} root(s); excluded "
              f"{rep['n_excluded']} -> {a.out_exclude}")
        return 0

    raise AssertionError(f"unhandled cmd {a.cmd!r}")


if __name__ == "__main__":
    raise SystemExit(main())
