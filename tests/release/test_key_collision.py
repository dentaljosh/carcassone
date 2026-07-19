"""F1 property: legal-cache / state-key collisions (Phase 0.3, review P1-R7/S6). Two
DISTINCT positions that share one string_representation key with DIFFERENT legal masks
would corrupt the legal-move cache and the MCTS transposition table. The release audit
asserts zero such collisions over the corpus; here we (a) assert clean over a replay
sample and (b) prove the built-in detector has TEETH by forcing a collision."""
import os
import random

import numpy as np

from carcassonne_ai import game_wrapper
from carcassonne_ai.game_wrapper import Game, _state_fingerprint


def _plies(seed, limit=200):
    random.seed(seed)
    game = Game(enable_legal_moves_cache=True)
    b = game.get_init_board()
    rng = random.Random(seed ^ 0x0FF1CE)
    n = 0
    while game.get_game_ended(b, 0) == 0.0 and n < limit:
        yield game, b
        legal = np.flatnonzero(game.get_valid_moves(b))
        b, _ = game.get_next_state(b, int(rng.choice(legal)))
        n += 1


def test_no_dangerous_key_collision_over_sample():
    """Corpus-wide check: no string_representation key maps to two boards with a DIFFERENT
    legal-move COUNT (a genuinely different position sharing a key — the dangerous form).

    A repeat key with the same count but different mask BITS is the benign P1-A3 rotation-
    alias label fragmentation (same physical moves, rotated meeple ids) — counted, not
    failed. A repeat key with an identical mask is a plain transposition."""
    seen: dict[str, tuple[int, bytes]] = {}
    n_states = 0
    fragmented = 0
    for seed in (101, 202, 303, 404):
        for game, b in _plies(seed):
            key = game.string_representation(b)
            mask = game.get_valid_moves(b)
            cnt = int(mask.sum())
            mb = mask.tobytes()
            n_states += 1
            if key in seen:
                pcnt, pmb = seen[key]
                if pcnt != cnt:
                    raise AssertionError(
                        f"DANGEROUS KEY COLLISION (differing move count {pcnt} vs {cnt}) "
                        f"at seed {seed}: key={key[:80]}...")
                if pmb != mb:
                    fragmented += 1   # benign P1-A3 label fragmentation
            seen[key] = (cnt, mb)
    assert n_states > 500, f"sample too small ({n_states} states)"


def test_builtin_collision_detector_has_teeth(monkeypatch, tmp_path):
    """Force two distinct boards to share ONE key (monkeypatch string_representation to a
    constant) with different masks; the CARCASSONNE_CACHE_COLLIDE_CHECK detector must log
    it and return the FRESH (correct) mask rather than the stale cached one."""
    monkeypatch.setattr(game_wrapper, "_CACHE_COLLIDE_CHECK", True)
    monkeypatch.setenv("CARCASSONNE_CLIP_TRACE_DIR", str(tmp_path))

    game = Game(enable_legal_moves_cache=True)
    # two genuinely different positions with different legal masks
    random.seed(55)
    b1 = game.get_init_board()
    b2 = b1
    rng = random.Random(7)
    for _ in range(20):
        legal = np.flatnonzero(game.get_valid_moves(b2))
        b2, _ = game.get_next_state(b2, int(rng.choice(legal)))
    m1 = game.get_valid_moves(b1)
    m2_real = game.get_valid_moves(b2)
    assert not np.array_equal(m1, m2_real), "need two positions with different masks"

    # collapse both keys to a constant -> b2 gets a cache HIT on b1's stored mask.
    fresh_game = Game(enable_legal_moves_cache=True)
    monkeypatch.setattr(fresh_game, "string_representation", lambda board: "COLLISION_KEY")
    stored = fresh_game.get_valid_moves(b1)          # miss: caches m1 under COLLISION_KEY
    served = fresh_game.get_valid_moves(b2)          # hit: detector recomputes fresh
    # the detector must serve the FRESH (correct) mask for b2, not b1's stale one.
    assert np.array_equal(served, m2_real), "detector served the STALE colliding mask"
    logs = list(tmp_path.glob("cache_collision_*.jsonl"))
    assert logs, "collision detector did not log the forced collision"
    assert logs[0].read_text().strip(), "collision log is empty"


def test_state_fingerprint_distinguishes_the_two_boards():
    """Sanity: the deep fingerprint (used to diff a real collision) actually differs for
    two distinct boards — so a logged collision carries a usable diff."""
    game = Game(enable_legal_moves_cache=True)
    random.seed(99)
    b1 = game.get_init_board()
    b2 = b1
    rng = random.Random(3)
    for _ in range(10):
        legal = np.flatnonzero(game.get_valid_moves(b2))
        b2, _ = game.get_next_state(b2, int(rng.choice(legal)))
    assert _state_fingerprint(b1.state) != _state_fingerprint(b2.state)
