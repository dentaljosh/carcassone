"""The Rust MIRROR PROTOCOL, as one import for the desktop harnesses (F-3).

⚠️ NEW MODULE (2026-08-02, F-3 wiring agent) — flagged for merge review. It exists
because `champion_factory.py` / `rust_agent.py` were READ-ONLY for that work and four
harnesses needed the identical five lines. Nothing here is new behaviour: it is the
`scripts/rustport/reconcile_backend.py` reference loop, factored.

WHY ANY OF THIS.  `rust_agent.RustFairAgent` is not a drop-in for the Python champion.
It owns a game state inside Rust that moves ONLY on an explicit `advance()`, for every
applied action of BOTH seats, and since 2026-08-01 `choose_action` hard-raises
`MirrorDesync` on any drift (12.8 us per decision — a correctness guard, not a mode).
Five of the six `make_production_champion` call sites drove the agent as if it were
stateless (measurement/rustport_p6/BACKEND_BYPASS_AUDIT_20260801.md §1), which is why
the factory default is still `backend="python"` and the YAML value is reached only by a
caller that opts in with `backend="auto"` — that opt-in BEING the caller's assertion
that it makes these calls.

The three calls, at the harness's own choke points:

    seat(agents, board)                 # once, on the INITIAL board
    ...
    board, _ = game.get_next_state(board, a)
    advance(agents, a)                  # EVERY applied action, BOTH seats

and, for a harness that starts from a recorded MID-GAME position rather than ply 0:

    reseat(agent, deck_seed=..., actions=prefix, move_idx=len(prefix_own_decisions))

`seat` / `advance` are DUCK-TYPED and unconditional: an agent with no `start_game` /
`advance` (the Python champion, `HumanCLIAgent`, `RuleBasedPlayer`) is skipped. So a
harness wires the protocol ONCE and is correct on either backend — including after a
future flip of the factory default, which is the whole point of F-3.

`resolve_execution` is the OTHER half: `backend="rust"` and `parallel_workers` are
mutually exclusive in the factory (the Rust core splits the same k worlds across OS
threads inside one GIL-released call instead of across spawn processes), so a harness
that reads `deploy_profile(...)["parallel_workers"]` must stop doing that when the
resolved backend is Rust, or the factory raises. It resolves both from one place.
"""
from __future__ import annotations

from typing import Any, Iterable

__all__ = ["is_mirrored", "seat", "advance", "reseat", "resolve_execution",
           "factory_default_backend", "Execution"]


def _iter(agents) -> Iterable[Any]:
    if agents is None:
        return ()
    if isinstance(agents, dict):
        return list(agents.values())
    if hasattr(agents, "choose_action") or hasattr(agents, "advance"):
        return (agents,)
    return list(agents)


def is_mirrored(agent) -> bool:
    """True iff `agent` owns a mirror that this protocol must drive.

    Duck-typed on BOTH halves of the contract, so a half-implemented object is not
    silently half-driven."""
    return hasattr(agent, "advance") and hasattr(agent, "start_game")


def seat(agents, board) -> int:
    """`start_game(board)` every mirrored agent. Returns how many were seated.

    Call ONCE, on the INITIAL board (the mirror reads `[next_tile] + deck` in draw
    order out of it, so it never has to guess how the caller seeded `random`)."""
    n = 0
    for a in _iter(agents):
        if is_mirrored(a):
            a.start_game(board)
            n += 1
    return n


def advance(agents, action: int, board_after=None) -> int:
    """Apply ONE action to every mirrored agent. Returns how many were advanced.

    THE choke point. Call it for every applied action of BOTH seats, immediately
    after the authoritative `game.get_next_state(...)`. `board_after` is optional and
    only read under reconcile mode (`CARC_RS_RECONCILE=1`), where it hard-asserts the
    post-action mirror — a repr per ply, so it is a gate mode, not a play mode."""
    n = 0
    for a in _iter(agents):
        if is_mirrored(a):
            a.advance(int(action), board_after)
            n += 1
    return n


def reseat(agent, *, deck_seed=None, board=None, actions=(), move_idx=None) -> bool:
    """Seat a mirrored agent on a recorded MID-GAME position, by REPLAY.

    The Rust state cannot be constructed from an arbitrary board — only replayed —
    which is exactly why a desync can never be silent. So a harness that jumps to a
    position (a bench root, a restored save) reconstructs it: seat on the game's
    deck, then `advance` the recorded action prefix.

    Pass EITHER `deck_seed` (the lossless `root_replay` contract:
    `random.seed(deck_seed)` fixes the shuffle) OR the initial `board`.

    ⚠️ `move_idx` is not cosmetic. The per-determinization seeds derive from it
    (`det_seed_base(seed, move_idx)`), so a mirror replayed to ply N while its move
    counter still reads 0 searches DIFFERENT worlds than the Python agent it is being
    compared against. `advance()` does not touch the counter (only a decision does),
    so the caller — which owns the move timeline — must seat it. Same contract, same
    spelling, as `FairHeuristicPriorAgent._move_idx`.

    Returns False (a no-op) for a non-mirrored agent, so a caller can call it
    unconditionally on either backend."""
    if not is_mirrored(agent):
        if move_idx is not None and hasattr(agent, "_move_idx"):
            agent._move_idx = int(move_idx)
        return False
    if (deck_seed is None) == (board is None):
        raise ValueError("reseat needs exactly one of deck_seed= or board=")
    if deck_seed is not None:
        agent.start_game_from_seed(deck_seed)
    else:
        agent.start_game(board)
    for a in actions:
        agent.advance(int(a))
    if move_idx is not None:
        agent._move_idx = int(move_idx)
    return True


class Execution(dict):
    """The resolved ENGINE + split for one harness run (a dict, so it drops straight
    into a manifest / game-log `config` block)."""

    @property
    def backend(self) -> str:
        return self["backend"]

    @property
    def is_rust(self) -> bool:
        return self["backend"] == "rust"

    def factory_kwargs(self) -> dict:
        """The kwargs to hand `make_production_champion`, already mutually consistent
        (`parallel_workers` is dropped on Rust, `rust_threads` on Python)."""
        if self.is_rust:
            return {"backend": "rust", "rust_threads": self["rust_threads"]}
        return {"backend": "python", "parallel_workers": self["parallel_workers"]}

    def describe(self) -> str:
        if self.is_rust:
            t = self["rust_threads"]
            return f"backend=rust rust_threads={1 if t is None else t}"
        pw = self["parallel_workers"]
        return ("backend=python parallel_workers="
                + ("None (sequential k-loop)" if pw is None else str(pw)))


def factory_default_backend() -> str:
    """What `make_production_champion` does when a caller says NOTHING about backend.

    Read from the factory's own signature (and resolved through the YAML if that
    default is ``"auto"``), never guessed — which is what lets a harness default to
    ``"inherit"`` and be carried along by a future flip of that default WITHOUT this
    module or the harness being edited again. `champion_factory` stays read-only here:
    this only reads a default value, it does not set one."""
    import inspect

    from .champion_factory import load_production_spec, make_production_champion

    d = inspect.signature(make_production_champion).parameters["backend"].default
    d = str(d)
    return str(load_production_spec().backend) if d == "auto" else d


def resolve_execution(backend: str = "python", *, profile: str | None = None,
                      rust_threads: int | None = None,
                      parallel_workers: int | None = None,
                      no_parallel: bool = False, warn=print) -> Execution:
    """Resolve `backend` / `rust_threads` / `parallel_workers` into ONE consistent set.

    `backend`:
      * ``"python"`` — pin the Python champion,
      * ``"rust"``   — the caller demands `carc_rs`,
      * ``"auto"``   — read `governance/PRODUCTION.yaml`: the named deploy PROFILE's
        `backend` when a profile is given and found, else `fair_deploy.backend`,
      * ``"inherit"`` — whatever `make_production_champion`'s OWN default resolves to
        (today: ``python``). ⚠️ This is the value a converted harness should DEFAULT to.
        It is byte-identical to ``"python"`` right now, and it is the difference between
        a harness that merely tolerates the factory-default flip and one the flip
        actually reaches — the flip is one edit in `champion_factory`, and no caller
        has to be touched again. The resolved literal is still passed explicitly, so
        what the harness resolved and what the factory builds can never disagree.

    FAIL-SAFE, exactly like `play_harness.resolve_parallel_workers`: any failure to
    read the YAML resolves to python + sequential rather than exploding a game. An
    EXPLICIT ``backend="rust"`` is the one thing that never degrades silently — a
    caller asking for Rust and getting Python would be a wrong number, not a slow one.

    ⚠️ The two splits are mutually exclusive by construction: on Rust the k worlds are
    folded across `rust_threads` OS threads inside one GIL-released call, so
    `parallel_workers` is dropped (the factory RAISES on the pair) and the
    profile's process count is NOT reinterpreted as a thread count — a `rust_threads`
    the YAML did not name is 1, the sequential fold."""
    prof = None
    try:
        from .champion_factory import deploy_profile, load_production_spec

        if profile is not None:
            prof = deploy_profile(profile)
        if backend == "inherit":
            backend = factory_default_backend()
        if backend == "auto":
            backend = (prof["backend"] if (prof and prof["found"])
                       else str(load_production_spec().backend))
    except Exception as exc:                                        # noqa: BLE001
        if backend == "rust":
            raise
        if warn:
            warn(f"[warn] could not resolve deploy profile {profile!r} / backend "
                 f"({type(exc).__name__}: {exc}); running backend=python, SEQUENTIAL")
        return Execution(backend="python", rust_threads=None, parallel_workers=None,
                         profile=profile, source="fallback")
    if backend not in ("python", "rust"):
        raise ValueError(f"backend must be 'python'|'rust'|'auto'; got {backend!r}")

    if backend == "rust":
        if rust_threads is None and prof:
            rust_threads = prof["rust_threads"]
        return Execution(backend="rust",
                         rust_threads=(None if rust_threads is None
                                       else int(rust_threads)),
                         parallel_workers=None, profile=profile,
                         source=("profile" if prof and prof["found"] else "explicit"))

    if no_parallel:
        parallel_workers = None
    elif parallel_workers is None and prof:
        parallel_workers = prof["parallel_workers"]
    return Execution(backend="python", rust_threads=None,
                     parallel_workers=(None if parallel_workers is None
                                       else int(parallel_workers)),
                     profile=profile,
                     source=("profile" if prof and prof["found"] else "explicit"))
