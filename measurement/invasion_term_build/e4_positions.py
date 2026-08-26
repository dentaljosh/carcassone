"""Replay E4 archive games into the RUST `carc_rs.MirrorState`, and pull the
Stage A / Stage B census's KNOWN INVASION PLIES out of
`measurement/e4_exploit_grading_20260825/stage_b_plies.jsonl`.

Why this exists: the invasion-risk shapes (`carc_core::leaf::invasion`, spec
`SHAPES.md` next to this file) are a RUST-ONLY leaf family, so their fixtures
must drive the rust leaf directly. The positions of record are the E4 archive
games the Stage A census graded — in particular the 51 rows whose
`notes.mech == "merge"`, i.e. the measured deliberate invasions (invader claims a
stub, merges into the incumbent's feature, full-points-on-tie pays the invader).

⚠️ RULES EPOCH. Every archive stamps its own `rules_profile`; a game replayed
under the wrong profile does not merely score differently, it panics on the first
placement outside the profile's grid. `mirror_for_archive` resolves the profile
from the archive's own stamp (never from `(start_rule, grid_rule)` — see the
auto-memory rule) and hands `MirrorState.from_seed` exactly that geometry.
`fixed_v1` additionally requires `CARCASSONNE_FIX_R9=1` in the ENVIRONMENT before
the process starts (the rust tile registry latches a `OnceLock`); the loader
checks and refuses rather than replaying a farm-adjacency-wrong board.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
E4_GAMES = REPO / "measurement" / "e4_games"
CENSUS = REPO / "measurement" / "e4_exploit_grading_20260825"
STAGE_B_PLIES = CENSUS / "stage_b_plies.jsonl"


def stage_b_rows(mech: str | None = None) -> list[dict]:
    """The Stage B ply selection, optionally filtered to one `notes.mech`
    (`"merge"` == the measured invasions)."""
    out = []
    for line in STAGE_B_PLIES.open():
        if not line.strip():
            continue
        r = json.loads(line)
        if mech is not None and (r.get("notes") or {}).get("mech") != mech:
            continue
        out.append(r)
    return out


def archive(name: str) -> dict:
    return json.loads((E4_GAMES / name).read_text())


def _profile_kwargs(profile_name: str) -> dict:
    """`MirrorState.from_seed` kwargs for a rules profile, straight off
    `rules_profile.PROFILES` (never a hand-copied geometry)."""
    from carcassonne_ai import rules_profile as rp

    prof = rp.PROFILES[profile_name]
    kw = dict(prof.game_kwargs())
    # `fixed_start_tile` is the Python `Game` spelling of the retail start rule;
    # the rust mirror spells the same thing `start_rule="retail"`.
    if kw.pop("fixed_start_tile", False) or prof.start_rule == "retail":
        kw["start_rule"] = "retail"
    return kw


def r9_ok() -> bool:
    """`CARCASSONNE_FIX_R9` must be in the ENVIRONMENT before import (OnceLock)."""
    return os.environ.get("CARCASSONNE_FIX_R9") == "1"


def mirror_for_archive(arch: dict, upto_ply: int | None = None):
    """Replay `arch`'s action list into a fresh `MirrorState`, stopping BEFORE
    `upto_ply` (None == play the whole game). Returns the MirrorState."""
    import carc_rs

    profile = arch.get("rules_profile")
    if not profile:
        raise ValueError(
            "archive carries no `rules_profile` stamp -> pre-fixed_v1 build; refusing "
            "to guess a rules epoch (see the auto-memory rule: never identify a build "
            "from (start_rule, grid_rule))"
        )
    ms = carc_rs.MirrorState.from_seed(str(arch["deck_seed"]), **_profile_kwargs(profile))
    actions = arch["actions"]
    n = len(actions) if upto_ply is None else min(upto_ply, len(actions))
    for a in actions[:n]:
        ms.advance(int(a))
    return ms


def states_along(arch: dict, plies):
    """Yield `(ply, MirrorState)` at each requested ply of one archive, replaying
    the game ONCE (the mirror is mutated in place, so callers must consume each
    state before advancing to the next)."""
    import carc_rs

    profile = arch["rules_profile"]
    ms = carc_rs.MirrorState.from_seed(str(arch["deck_seed"]), **_profile_kwargs(profile))
    want = sorted({int(p) for p in plies})
    actions = arch["actions"]
    cur = 0
    for target in want:
        if target > len(actions):
            continue
        while cur < target:
            ms.advance(int(actions[cur]))
            cur += 1
        yield target, ms
