"""F1 property: rotation-alias canonicalization. A rotationally-symmetric tile emits >=2
rotation action-ids that fold to the SAME transposition key (= same MCTS node). Invariants:
(1) aliased actions fold to a PLAY-EQUIVALENT child (identical legal mask/scores/phase —
only the raw tile rotation differs); (2) the champion prior mass is conserved (softmax over
legal actions sums to 1, all mass on legal); (3) MCTS does not double-count an aliased
child's visits (the C2 transposition fix). A break here mis-weights symmetric moves."""
import random

import numpy as np

from carcassonne_ai.game_wrapper import Game
from carcassonne_ai.heuristic_prior_mcts import (
    HeuristicPriorConfig,
    make_heuristic_prior_evaluator,
)
from carcassonne_ai.mcts import NeuralMCTS
from wingedsheep.carcassonne.objects.game_phase import GamePhase


def _positions(n_games=8, plies=12):
    for g in range(n_games):
        random.seed(1000 + g)
        game = Game(enable_legal_moves_cache=True)
        b = game.get_init_board()
        rng = random.Random(2000 + g)
        for _ in range(plies):
            if game.get_game_ended(b, 0) != 0.0:
                break
            legal = np.flatnonzero(game.get_valid_moves(b))
            b, _ = game.get_next_state(b, int(rng.choice(legal)))
        if game.get_game_ended(b, 0) == 0.0:
            yield game, b


def _fresh_mask(board):
    """Legal mask computed on a FRESH cache-less Game — so no shared legal-move cache can
    serve a stale sibling mask (which would hide the P1-A3 label fragmentation below)."""
    return Game(enable_legal_moves_cache=False).get_valid_moves(board)


def _alias_groups(game, board):
    """Group legal TILES-phase actions by resulting string_representation. Groups with >1
    member are rotation aliases (distinct action-ids -> same transposition key)."""
    if board.state.phase != GamePhase.TILES:
        return {}
    groups: dict[str, list[int]] = {}
    for a in np.flatnonzero(game.get_valid_moves(board)):
        child, _ = game.get_next_state(board, int(a))
        groups.setdefault(game.string_representation(child), []).append(int(a))
    return {k: v for k, v in groups.items() if len(v) > 1}


def test_rotation_aliases_are_gone_under_the_injective_key():
    """⭐ THE 2026-08-30 FIX, stated as a property: with
    `CARCASSONNE_FIX_LEGAL_CACHE_KEY` ON (the default) NO two distinct tile
    actions fold to one transposition key over this sample. The alias below is
    not a benign canonicalization — the rotations emit DIFFERENT farmer
    action-ids, so folding them made the memo hand out a mask whose farmer bits
    belong to the other rotation (illegal here, and missing the legal one). See
    the flag comment in `game_wrapper` and
    `measurement/legal_cache_key_20260830/`."""
    for game, board in _positions():
        groups = _alias_groups(game, board)
        assert not groups, (
            f"injective key still folds distinct actions together: {groups}")


def test_rotation_aliases_fold_to_same_key_and_play_equivalent_child(legacy_cache_key):
    """HISTORICAL CONTRACT, pinned to the legacy key (`legacy_cache_key`) — kept
    because it documents exactly what the old key did and why the "benign"
    reading below was wrong: it asserted only that the move COUNT matched, which
    is true even when every farmer id is wrong. The count-blindness is why this
    test passed for months while the defect was live.

    Aliased actions (symmetric tile rotations at one coord) fold to the SAME
    transposition key (= same MCTS node) and a PLAY-EQUIVALENT child: same legal-move
    COUNT, scores, phase and mover.

    ⚠️ The raw mask BITS may differ by rotation LABEL: a farmer on the tile's TOP field at
    rot=0 is the SAME physical field as its BOTTOM field at rot=2 (e.g. city_narrow_shield),
    so the meeple action-IDs rotate. That is the KNOWN, accepted P1-A3 'rotation-alias label
    fragmentation' (logged to BACKLOG, below the cost line) — this test MEASURES it (asserts
    the play-invariant, counts the fragmentation) rather than failing on it. A DIFFERING
    move COUNT (or scores/phase) would be a genuinely different position sharing a key — a
    REAL collision — and fails."""
    found = 0
    fragmented = 0
    for game, board in _positions():
        for key, actions in _alias_groups(game, board).items():
            found += 1
            children = [game.get_next_state(board, a)[0] for a in actions]
            masks = [_fresh_mask(c) for c in children]
            counts = {int(m.sum()) for m in masks}
            scores = {tuple(c.state.scores) for c in children}
            phases = {c.state.phase for c in children}
            movers = {c.state.current_player for c in children}
            assert len(counts) == 1, \
                f"alias {actions}: DIFFERING legal-move count {counts} (real key collision)"
            assert len(scores) == 1, f"alias {actions}: differing scores (real collision)"
            assert len(phases) == 1 and len(movers) == 1
            if len({m.tobytes() for m in masks}) > 1:
                fragmented += 1   # P1-A3 label fragmentation (same physical moves, rotated ids)
    assert found > 0, "no rotation aliases observed in the sample (test has no teeth)"
    # (fragmented may be 0 or >0 depending on which symmetric tiles appear — both are fine;
    # the invariant is the play-equivalence asserted above.)


def test_champion_prior_mass_conserved():
    cfg = HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                               final_select="visits")
    for game, board in _positions():
        ev = make_heuristic_prior_evaluator(game, cfg)
        priors, value = ev(board)
        legal = np.flatnonzero(game.get_valid_moves(board))
        assert priors.shape[0] == game.get_action_size()
        assert abs(float(priors.sum()) - 1.0) < 1e-5, "prior mass != 1 over legal actions"
        # all mass on legal actions (zero leaked onto illegal indices).
        illegal_mass = float(priors.sum()) - float(priors[legal].sum())
        assert abs(illegal_mass) < 1e-6, "prior mass leaked onto illegal actions"
        assert -1.0 <= float(value) <= 1.0


def test_mcts_does_not_double_count_aliased_visits(legacy_cache_key):
    """After a search, summing root-child visits per action-SLOT double-counts an aliased
    child (which sits in >=2 slots). The deduped-by-object sum is the honest visit mass;
    they differ exactly when a visited alias exists (the C2 fix).

    Pinned to the LEGACY key: under the injective default there are no aliases left for
    the dedup path to handle (asserted separately above), so this test would have no
    teeth. The C2 dedup stays in the code because a `legal_mask_cache=0` replay of a
    banked corpus still produces aliases."""
    cfg = HeuristicPriorConfig(c_puct=1.5, tau_p=5.0, leaf_quantize="float",
                               final_select="visits")
    saw_collision = False
    for game, board in _positions(n_games=6):
        if not _alias_groups(game, board):
            continue
        ev = make_heuristic_prior_evaluator(game, cfg)
        m = NeuralMCTS(game=game, evaluator=ev, simulations=32, c_puct=1.5, seed=13)
        m.search(board)
        root = m._nodes.get(game.string_representation(board))
        if root is None:
            continue
        raw = sum(ch.N for ch in root.children.values())
        seen, dedup = set(), 0
        for ch in root.children.values():
            if id(ch) in seen:
                continue
            seen.add(id(ch))
            dedup += ch.N
        # a visited alias => raw > dedup (double-counted); never raw < dedup.
        assert raw >= dedup
        if raw > dedup:
            saw_collision = True
    assert saw_collision, "no visited aliased child observed (dedup path untested)"
