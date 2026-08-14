"""Fast guards for the rustport P1 engine slice.

The full G1 gate is `scripts/rustport/reconcile_engine.py --corpus all`
(463 games / ~67k positions, ~10 s at 8 workers).  These are the cheap
always-on subset plus the unit-level contracts that the corpus replay would
only catch indirectly.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "engine", REPO / "scripts" / "measurement_infra",
           REPO / "scripts" / "rustport", REPO / "scripts" / "analyzer"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

carc_rs = pytest.importorskip("carc_rs", reason="build with `maturin develop --release`")

# MUST precede every `carcassonne_ai` import below: `reconcile_engine` imports
# `prod_leaf_env`, which REFUSES to load once `carcassonne_ai` is in sys.modules
# (it shapes the leaf knobs that `virtual_score_v2.DEFAULT_CONFIG` freezes at ITS
# import).  Without this line THIS module imported `carcassonne_ai.action_space`
# first and `import reconcile_engine` then raised, which is a collection ERROR —
# measured 2026-08-13 at 530368de, standalone as well as under `pytest tests/`.
#
# ⚠️ This file was the ONLY `tests/rustport/` module with that ordering bug, and
# this line is NOT owed to any of the others (verified 2026-08-13, correcting an
# earlier version of this comment that claimed it was).  `test_p2_leaf`,
# `test_p3_search`, `test_p5_flags`, `test_lockstep_fuzz` and
# `test_cloister_scan_fix_parity` never `import prod_leaf_env` themselves
# (`grep -c` = 0 in all five) and do not need to: each imports its GATE SCRIPT
# first — `reconcile_leaf` / `trace_search` / `even_shift_property` /
# `lockstep_fuzz` — and those import `prod_leaf_env` at their own module level,
# so the freeze is already won before `carcassonne_ai` is reached.  All five
# collect and pass standalone, both before and after this fix.
#
# The SESSION-level failure was a different thing with the same symptom:
# COLLECTION ORDER.  `tests/android/` sorts before `tests/rustport/` and imports
# `carcassonne_ai` (via `android_bridge`), so by the time any rustport module is
# imported the freeze race is already lost no matter what that module does.
# That is handled once, for the whole session, in `tests/conftest.py` — see the
# `prod_leaf_env` block at the top of it.  Do not "fix" the other five here.
#
# This line is also what makes the R9 re-exec at the bottom of this file work,
# since that runs this module as a script.  Sets exactly the env
# `reconcile_engine` would have set anyway, only early enough to be honoured.
import prod_leaf_env  # noqa: E402,F401

import numpy as np  # noqa: E402

from carcassonne_ai import rules_profile  # noqa: E402
from carcassonne_ai.action_space import action_size, decode, encode  # noqa: E402
from carcassonne_ai.flat_leaf import flat_base_score  # noqa: E402
from carcassonne_ai.rust_agent import mirror_geometry_kwargs  # noqa: E402
from root_replay import replay_actions  # noqa: E402

import reconcile_engine as rec  # noqa: E402

# `scripts/analyzer/ev_loss` owns the ONE archive->rules-profile discriminator
# (`resolve_profile_name`); re-deriving it here is exactly the duplication that
# caused the 2026-08-05 EV-loss retraction, so we import it rather than copy it.
# It re-imports `env_preamble`, which `prod_leaf_env` above has already applied,
# so in practice this adds nothing; the snapshot/restore is a guard so that a
# future knob added to the preamble cannot leak out of this import and into every
# *other* test in the session (`CUDA_VISIBLE_DEVICES=""`, `OMP_NUM_THREADS=1`).
# Safe because the preamble's only effect is `os.environ.setdefault`.
_ENV_BEFORE_EV_LOSS = dict(os.environ)
import ev_loss as _ev_loss  # noqa: E402
os.environ.clear()
os.environ.update(_ENV_BEFORE_EV_LOSS)
del _ENV_BEFORE_EV_LOSS


# --------------------------------------------------------------------------- #
# The E4 phone-archive ledger                                                   #
# --------------------------------------------------------------------------- #
E4_DIR = REPO / "measurement" / "e4_games"
E4_ARCHIVES = sorted(E4_DIR.glob("*.json"))

# A FLOOR, never an equality.  The previous `assert len(paths) == 2` turned this
# whole test into a no-op the day the third archive landed (the phone appends to
# the ledger and nothing prunes it), so 24 games went unreplayed.  A floor lets
# the ledger grow into extra coverage while still catching a ledger that has
# been emptied, moved, or silently unmounted.  Raise it when archives are added.
E4_LEDGER_FLOOR = 26

# The archives straddle three rules epochs and MUST each replay under their own.
# `walled`/`app_aug2` want R9 OFF, `fixed_v1` wants it ON — and R9 is latched at
# IMPORT time (`base_deck` derives the farm data; the Rust tile registry latches
# a `OnceLock`), so one interpreter cannot honour both.  Archives whose epoch
# disagrees with this process's latch are therefore replayed by re-executing
# THIS FILE as a script with the right `CARCASSONNE_FIX_R9`, running the exact
# same `_replay_e4_archive` code — not a weaker in-process approximation.
E4_R9_ENV = rules_profile.R9_ENV_VAR


def _archive_profile(d: dict):
    """The `RulesProfile` an archive was PLAYED under, from its OWN metadata.

    The discriminator is the archive's `rules_profile`/`cloister_rule`/`farm_rule`
    stamp, which only the `fixed_v1` app build writes; its ABSENCE is positive
    evidence of a pre-`fixed_v1` build.  `(start_rule, grid_rule)` is NOT a build
    discriminator — `app_aug2` and `fixed_v1` share that pair — which is why this
    defers to `ev_loss.resolve_profile_name` instead of pattern-matching here.
    Raises on anything it cannot resolve; grading under the wrong profile is a
    silent wrong answer.
    """
    return rules_profile.resolve(_ev_loss.resolve_profile_name(d))


def _representative_archives():
    """One archive per rules profile, oldest-first within each profile.

    Used only by the decode test, whose subject is the action-space
    encode/decode round-trip.  That contract's ONLY rules dependence is board
    GEOMETRY (the window offset moves with `start_row`, and `retail` pre-places
    the start tile), so profile coverage — not archive count — is the axis that
    buys anything, and replaying all 26 would multiply its per-ply x per-legal-
    move cost for no new contract.  An archive whose profile will not resolve
    still gets its own case here so it fails by name rather than vanishing.
    """
    out: dict[str, Path] = {}
    for p in E4_ARCHIVES:
        try:
            key = _ev_loss.resolve_profile_name(json.loads(p.read_text()))
        except Exception:                                          # noqa: BLE001
            key = f"UNRESOLVED::{p.name}"
        out.setdefault(key, p)
    return sorted(out.items())


def _replay_e4_archive(path) -> dict:
    """Full bit-identity replay of ONE archive under ITS OWN rules profile.

    Per-ply lockstep (repr / legal-mask sha256 / scores / both players'
    `flat_base_score`) PLUS the phone's own recorded final scores and
    terminality — the same strictness the two-archive version asserted.
    """
    path = Path(path)
    d = json.loads(path.read_text())
    assert d["schema"] == "carcassonne-android-archive/v1", (
        f"{path.name}: unexpected schema {d.get('schema')!r}")

    prof = _archive_profile(d)
    if rules_profile.r9_env_on() != prof.r9_env_expected:
        raise RuntimeError(
            f"{path.name}: profile {prof.name!r} expects {E4_R9_ENV}="
            f"{int(prof.r9_env_expected)} but this process latched "
            f"{int(rules_profile.r9_env_on())}. R9 is import-latched — restart "
            "the interpreter with the right value.")

    seed, actions = int(d["deck_seed"]), [int(a) for a in d["actions"]]
    _lockstep(seed, actions, game_kwargs=prof.game_kwargs())

    ms = carc_rs.MirrorState.from_seed(str(seed), **_mirror_kwargs(prof))
    for a in actions:
        ms.advance(int(a))
    assert list(ms.scores()) == [int(x) for x in d["result"]["scores"]], (
        f"{path.name}: final scores disagree with the phone's own record "
        f"(profile {prof.name})")
    assert ms.is_terminal(), f"{path.name}: replay did not reach a terminal state"
    return {"path": str(path), "profile": prof.name, "plies": len(actions)}


def _mirror_kwargs(prof) -> dict:
    """The Rust-mirror rules kwargs for `prof`, via the canonical bridge.

    `rust_agent.mirror_geometry_kwargs` derives them from a `Game`, which is the
    contract of record (a mirror mirrors the Game it was handed), so build the
    Game the profile implies and ask it.  Returns `{}` under `walled`.
    """
    from carcassonne_ai.game_wrapper import Game
    return mirror_geometry_kwargs(Game(**prof.game_kwargs()))


def _lockstep(deck_seed: int, actions: list[int], *, game_kwargs: dict | None = None) -> None:
    """Per-ply Python-vs-Rust bit identity.

    `game_kwargs` is a `RulesProfile.game_kwargs()`; the Rust mirror's matching
    setup is DERIVED FROM THE BUILT GAME rather than passed in separately, so the
    two sides cannot drift apart.  `None` (and `walled`, whose `game_kwargs()` is
    `{}`) builds exactly the calls this helper always made.
    """
    game, board = replay_actions(deck_seed, actions, 0, game_kwargs=game_kwargs)
    ms = carc_rs.MirrorState.from_seed(str(deck_seed), **mirror_geometry_kwargs(game))
    for i, a in enumerate(list(actions) + [None]):
        assert game.string_representation(board) == ms.string_repr(), f"repr @ply {i}"
        if not board.state.is_terminated():
            mask = np.asarray(game.get_valid_moves(board), dtype=bool)
            assert hashlib.sha256(mask.tobytes()).hexdigest() == ms.legal_mask_sha256(), (
                f"mask @ply {i}"
            )
        assert [int(x) for x in board.state.scores] == list(ms.scores()), f"scores @ply {i}"
        for p in (0, 1):
            assert int(flat_base_score(board.state, p)) == int(ms.flat_base_score(p)), (
                f"flat_base_score[p{p}] @ply {i}"
            )
        if a is not None:
            board, _ = game.get_next_state(board, int(a))
            ms.advance(int(a))


def test_action_space_layout_matches_python():
    assert action_size(25) == 2511
    ms = carc_rs.MirrorState.from_seed("1")
    assert len(ms.legal_mask_bytes()) == action_size(25)


def test_first_move_is_the_forced_starting_placement():
    ms = carc_rs.MirrorState.from_seed("1")
    game, board = replay_actions(1, [], 0)
    mask = np.asarray(game.get_valid_moves(board), dtype=bool)
    assert ms.legal_actions() == np.flatnonzero(mask).tolist()
    assert len(ms.legal_actions()) == 1


def test_the_e4_ledger_has_not_shrunk_or_gone_unresolvable():
    """The guard the old `assert len(paths) == 2` was pretending to be.

    That equality did not protect the ledger, it froze it: the assert fired on
    archive #3 and the replay below stopped running entirely, so 24 games were
    never replayed by CI.  A floor plus a per-archive profile resolution keeps
    "the ledger grew" as EXTRA coverage and "the ledger vanished" as a failure.
    """
    assert len(E4_ARCHIVES) >= E4_LEDGER_FLOOR, (
        f"the E4 ledger holds {len(E4_ARCHIVES)} archives, below the "
        f"{E4_LEDGER_FLOOR} floor — archives are appended, never pruned, so this "
        f"means {E4_DIR} lost files or is not where it used to be")
    profiles = {p.name: _archive_profile(json.loads(p.read_text())).name
                for p in E4_ARCHIVES}
    assert len(profiles) == len(E4_ARCHIVES)
    # Every archive resolves to a profile the registry knows, and none of the
    # unstamped ones may come out `fixed_v1` (the 2026-08-05 retraction).
    for path in E4_ARCHIVES:
        d = json.loads(path.read_text())
        if not d.get("rules_profile"):
            assert profiles[path.name] != "fixed_v1", (
                f"{path.name} carries no `rules_profile` stamp, so it is from a "
                "PRE-fixed_v1 build and must never resolve to fixed_v1")


@pytest.mark.parametrize("archive", E4_ARCHIVES, ids=lambda p: p.stem)
def test_e4_phone_archive_replays_bit_identically(archive):
    """EVERY archive, per-ply, plus the phone's own recorded final scores.

    One case per archive so a divergence names the offending file instead of
    collapsing the whole ledger into a single assert.  Each replays under the
    rules profile resolved from its OWN metadata; the ones whose epoch needs the
    other R9 latch are re-executed as a subprocess with the correct environment,
    running this same function.
    """
    prof = _archive_profile(json.loads(Path(archive).read_text()))
    if rules_profile.r9_env_on() == prof.r9_env_expected:
        _replay_e4_archive(archive)
        return

    env = dict(os.environ, **{E4_R9_ENV: "1" if prof.r9_env_expected else "0"})
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(archive)],
                          env=env, capture_output=True, text=True)
    assert proc.returncode == 0, (
        f"{Path(archive).name} (profile {prof.name}, replayed in a subprocess at "
        f"{E4_R9_ENV}={env[E4_R9_ENV]}) failed:\n{proc.stdout}\n{proc.stderr}")


def test_golden_frozen_positions_reproduce():
    jobs = [j for j in rec.load_jobs("golden", None)]
    checked = 0
    for job in jobs:
        r = rec.check_game(job)
        assert r["mismatches"] == [], r["mismatches"][:1]
        checked += r["frozen_checked"]
    assert checked == 56, f"expected the fixture's 56 positions, saw {checked}"


def test_champ_sample_replays_bit_identically():
    jobs = rec.load_jobs("champ", None)
    assert len(jobs) == 449
    rng = random.Random(20260731)
    for job in rng.sample(jobs, 6):
        r = rec.check_game(job)
        assert r["mismatches"] == [], r["mismatches"][:1]


@pytest.mark.parametrize("archive", E4_ARCHIVES, ids=lambda p: p.stem)
def test_from_deck_matches_from_seed(archive):
    """The phone path (`start_game_from_deck`) must reach the same states as the
    seeded path — it is the entry point with no RNG dependence at all.

    Parametrized over the whole ledger (it used to pin `sorted(...)[0]`, i.e.
    whichever archive happened to be oldest, on the engine of record).  This is
    a mirror-only test — no Python engine, no R9-sensitive farm scoring below the
    recorded-scores check — but the rules profile still has to be threaded into
    BOTH constructors, because `retail` pre-places the start tile and
    `centered18` moves the grid, which is precisely where the two entry points
    could diverge.  Cheap enough to run on every archive.
    """
    d = json.loads(Path(archive).read_text())
    prof = _archive_profile(d)
    mkw = _mirror_kwargs(prof)
    seed, actions = int(d["deck_seed"]), [int(a) for a in d["actions"]]
    deck = carc_rs.deck_descriptions_from_seed(str(seed))
    a = carc_rs.MirrorState.from_seed(str(seed), **mkw)
    b = carc_rs.MirrorState.from_deck(deck, **mkw)
    for i, act in enumerate(actions):
        assert a.string_repr() == b.string_repr(), f"@ply {i}"
        a.advance(act)
        b.advance(act)
    assert a.string_repr() == b.string_repr()
    assert a.scores() == b.scores()
    if rules_profile.r9_env_on() == prof.r9_env_expected:
        # Final scoring includes farms, so only compare against the phone's own
        # record when this process carries the archive's R9 latch.  The
        # from_deck-vs-from_seed identity above is latch-independent; the
        # recorded-score check is not, and is covered for every archive at the
        # right latch by `test_e4_phone_archive_replays_bit_identically`.
        assert a.scores() == tuple(d["result"]["scores"])


@pytest.mark.parametrize("profile_name,archive", _representative_archives(),
                         ids=lambda v: v if isinstance(v, str) else v.stem)
def test_decode_agrees_with_python_on_every_legal_action(profile_name, archive):
    """Every legal index decodes to the same engine action on both sides — the
    mask alone would not catch a decode that lands on a different rotation.

    Deliberately ONE archive per rules profile rather than all 26 (see
    `_representative_archives`): the subject is the encode/decode round-trip,
    whose only rules dependence is board geometry, and this test costs a decode
    of every legal move at every ply.  Previously it pinned `sorted(...)[0]` with
    no profile threaded, which covered the engine-of-record geometry only by
    accident of that archive happening to be the oldest.
    """
    from carcassonne_ai.action_space import WindowOffset
    from wingedsheep.carcassonne.objects.actions.meeple_action import MeepleAction
    from wingedsheep.carcassonne.objects.actions.pass_action import PassAction
    from wingedsheep.carcassonne.objects.actions.tile_action import TileAction

    d = json.loads(Path(archive).read_text())
    prof = _archive_profile(d)
    assert prof.name == profile_name
    actions = [int(a) for a in d["actions"]]
    game, board = replay_actions(int(d["deck_seed"]), actions, 0,
                                 game_kwargs=prof.game_kwargs())
    ms = carc_rs.MirrorState.from_seed(str(d["deck_seed"]),
                                       **mirror_geometry_kwargs(game))

    for i, a in enumerate(actions):
        off = board.offset
        assert (off.origin_row, off.origin_col, off.size) == ms.window_offset(), f"offset @{i}"
        mask = np.asarray(game.get_valid_moves(board), dtype=bool)
        for idx in np.flatnonzero(mask).tolist():
            act = decode(
                int(idx), off=off, phase=board.state.phase.value,
                next_tile=board.state.next_tile,
                last_tile_coord=(board.state.last_tile_action.coordinate
                                 if board.state.last_tile_action else None),
            )
            # round-trip: encode(decode(idx)) == idx
            assert encode(act, off, board.state.phase.value) == idx
            if isinstance(act, TileAction):
                assert 0 <= act.tile_rotations < 4
            else:
                assert isinstance(act, (MeepleAction, PassAction))
        board, _ = game.get_next_state(board, a)
        ms.advance(a)


def test_count_final_scores_is_order_invariant_smoke():
    """The P1 escalation trigger, in miniature.  The broad run is
    `scripts/rustport/property_count_final_scores_order.py`."""
    import property_count_final_scores_order as prop

    rc = prop.main(["--games", "3", "--plies-per-game", "3", "--perms", "3"])
    assert rc == 0, "count_final_scores became order-sensitive -> ESCALATE"


# --------------------------------------------------------------------------- #
# The R9 re-exec worker.                                                        #
#                                                                               #
# `python tests/rustport/test_p1_engine.py <archive.json>` replays ONE archive  #
# and exits non-zero on any divergence.  It exists so an archive whose rules     #
# epoch disagrees with the pytest process's import-latched CARCASSONNE_FIX_R9    #
# can still be checked at FULL strictness, by the same `_replay_e4_archive`      #
# code, instead of being skipped or graded under the wrong farm adjacency.       #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print(json.dumps(_replay_e4_archive(sys.argv[1])))
