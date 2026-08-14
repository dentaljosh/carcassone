"""On-device battery A/B bench workload — DEBUG BUILDS ONLY.

This module ships only in the debug APK (it lives in ``src/debug/python``, a
Chaquopy debug-sourceset dir) and is called only by the debug-sourceset
``BenchService``. Release builds contain neither.

WHAT IT DOES. Runs N champion decisions headlessly, back-to-back, from a fixed
seeded position stream, timing each decision, and writes one self-describing
JSON result. The host-side driver (``android/tools/battery_bench.sh``) samples
battery current/voltage over the same window and integrates joules; this module
is the workload half plus the *identity witness* (``move_hash``) that proves two
arms did byte-identical work.

WHY THE WORK IS IDENTICAL ACROSS ``rust_threads`` ARMS. The rust search folds
its k determinization worlds deterministically at any thread count
(``rust/carc/carc-core/src/fair/mod.rs::search_worlds`` + its
``thread_count_invariance`` test; re-confirmed by the battery-audit worktree
report at commit 7ae0d742). So two arms started from the same (seed, budget,
rules) play the same moves, and ``move_hash`` — a digest over the full applied
action trace plus the resolved budget and rules profile — must be equal. The
driver ABORTS rather than print energy numbers if it is not.

WHAT IT NEVER TOUCHES:
  * the live app session (``android_bridge._S``) — a private ``_Session`` is
    constructed directly, never installed;
  * the autosave / finished-game archive (``files/current_game.json``,
    ``files/games/``) — those are written by Kotlin (SaveStore/ArchiveStore)
    for real games only; this module refuses an out_dir named ``games``;
  * governance — ``rust_threads`` is overridden on the constructed session
    object AFTER the normal YAML resolution ran; PRODUCTION.yaml is read (by
    the ordinary ``_build_opponent`` path) and never written.

Reuse contract: ``android_bridge._Session`` is used read-only — the subclass
below overrides nothing about seeding, ``_move_idx``, budget resolution or the
mirror protocol; it only replaces the session's resolved ``rust_threads`` value
with the bench arm's, which ``_Session._start_rust_mirror`` then passes to
``carc_rs.FairAgentRs(threads=...)`` exactly as it would the YAML value.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import traceback

import android_bridge as B

SCHEMA = "carc-battery-bench/v1"


class _BenchSession(B._Session):
    """A ``_Session`` whose resolved ``rust_threads`` is the bench arm's.

    ``_Session._build_opponent`` resolves ``rust_threads`` from the YAML mobile
    profile; ``_start_rust_mirror`` reads ``self.rust_threads`` when it builds
    ``FairAgentRs``. Overriding the attribute between those two steps (both run
    inside ``_Session.__init__``) is the narrowest possible hook: budget, leaf,
    seeding and every rule lever resolve exactly as in the real app, and the
    YAML is never edited. Thread count does not change play (see module doc).
    """

    def __init__(self, *, bench_rust_threads: int, **kw):
        t = int(bench_rust_threads)
        if t < 1:
            raise ValueError(f"bench_rust_threads must be >= 1, got {t}")
        self._bench_threads = t
        super().__init__(**kw)

    def _build_opponent(self) -> None:
        super()._build_opponent()
        # Only meaningful on the rust path; after a degrade to python the
        # attribute is unused and the bench aborts anyway (see _run).
        if self.opponent_kind == "champion" and self.backend == B.BACKEND_RUST:
            self.rust_threads = self._bench_threads


def _new_session(seed: int, threads: int, sims, k_dets) -> _BenchSession:
    return _BenchSession(
        bench_rust_threads=threads,
        seed=int(seed),
        human_player=0,
        opponent="champion",
        # None/None = the YAML champion budget (the production workload).
        # Non-None only from desktop tests, which shrink the search to prove
        # the identity mechanism cheaply.
        sims=sims,
        k_dets=k_dets,
        # verify=False: champion_factory's leaf proof is a fixed startup cost
        # proven elsewhere (the shipping app runs it); nothing here is archived
        # as a played game, and the bench window starts after setup anyway.
        verify=False,
        generation=0,
        backend=B.BACKEND_RUST,
        farm_rule=B.FARM_RULE_LATCHED,
    )


def _require_rust(s: _BenchSession) -> None:
    """The bench measures the production (rust) engine or nothing.

    A degraded session would still play — at the k4x688 python floor — which is
    a different workload, so energy numbers from it would silently answer the
    wrong question. Fail loudly instead.
    """
    if s.backend != B.BACKEND_RUST or s.rs is None:
        raise RuntimeError(
            f"rust backend unavailable — bench refuses to measure the python "
            f"fallback (rs_note={s.rs_note!r})")


def _run(n_moves: int, rust_threads: int, seed: int, sims, k_dets) -> dict:
    if n_moves < 1:
        raise ValueError(f"n_moves must be >= 1, got {n_moves}")

    t_setup0 = time.monotonic()
    s = _new_session(seed, rust_threads, sims, k_dets)
    _require_rust(s)
    setup_ms = (time.monotonic() - t_setup0) * 1000.0

    k = int(s.eff_k_dets)
    per_det = int(s.eff_sims)
    rules = s.rules_profile

    per_move_ms: list[float] = []
    trace: list[list[int]] = []      # [game_seed, action_id] per APPLIED action
    forced = 0
    games = [int(seed)]
    rebuild_ms = 0.0

    # The energy window the host integrates over: device epoch millis, the same
    # clock the driver's sampler stamps with `date +%s%3N` on the device.
    t_start_ms = int(time.time() * 1000)
    t_loop0 = time.monotonic()
    while len(per_move_ms) < n_moves:
        if s.board.state.is_terminated():
            # Fixed position stream continues into the next seeded game. With
            # the default n_moves this never happens (a game is ~140 plies);
            # the rebuild cost is recorded so the window is interpretable.
            g = int(seed) + len(games)
            games.append(g)
            t_r0 = time.monotonic()
            s = _new_session(g, rust_threads, sims, k_dets)
            _require_rust(s)
            rebuild_ms += (time.monotonic() - t_r0) * 1000.0
            continue
        gseed = games[-1]
        legal = s.legal_ids()
        if len(legal) == 1:
            # A forced action (single legal move, e.g. a forced pass) is part
            # of the trajectory but not a champion decision — searching it
            # would dilute per-move stats with ~0 ms entries.
            s.apply(legal[0])
            trace.append([gseed, int(legal[0])])
            forced += 1
            continue
        t0 = time.monotonic()
        action = int(s.pick(s.board))
        dt_ms = (time.monotonic() - t0) * 1000.0
        s.apply(action)
        if s.rs is None:
            # apply() degrades to the python floor on a mirror failure rather
            # than crashing the app — right for a game, wrong for a bench.
            raise RuntimeError(
                f"rust mirror degraded mid-bench after "
                f"{len(per_move_ms)} moves (rs_note={s.rs_note!r})")
        per_move_ms.append(dt_ms)
        trace.append([gseed, action])
    loop_wall_ms = (time.monotonic() - t_loop0) * 1000.0
    t_end_ms = int(time.time() * 1000)

    # The identity witness. Everything that defines "the same work" is inside
    # the digest: the resolved budget, the rules profile, and every applied
    # action of every game in the stream (forced actions included).
    hashed = json.dumps(
        {"schema": SCHEMA, "rules_profile": rules,
         "k_dets": k, "sims_per_det": per_det, "trace": trace},
        sort_keys=True, separators=(",", ":"))
    move_hash = hashlib.sha256(hashed.encode()).hexdigest()

    search_ms = sum(per_move_ms)
    return {
        "schema": SCHEMA,
        "ok": True,
        "n_moves": int(n_moves),
        "seed": int(seed),
        "rust_threads": int(rust_threads),
        "backend": s.backend,
        "k_dets": k,
        "sims_per_det": per_det,
        "total_sims": k * per_det,
        "rules_profile": rules,
        "budget_note": s.budget_note,      # non-null only under test budgets
        "move_hash": move_hash,
        "n_actions_applied": len(trace),
        "forced_actions": forced,
        "games_started": games,
        # Window for the host's trapezoid integration (device epoch millis).
        "t_start_ms": t_start_ms,
        "t_end_ms": t_end_ms,
        "setup_ms": round(setup_ms, 1),          # outside the window
        "rebuild_ms": round(rebuild_ms, 1),      # inside the window if nonzero
        "loop_wall_ms": round(loop_wall_ms, 1),
        "search_ms_total": round(search_ms, 1),
        "s_per_move_mean": round(search_ms / len(per_move_ms) / 1000.0, 4),
        "per_move_ms": [round(x, 1) for x in per_move_ms],
    }


def run_bench(n_moves, rust_threads, seed, out_dir, tag,
              sims=None, k_dets=None) -> str:
    """Entry point for ``BenchService`` (and for the desktop tests).

    Runs the workload, writes ``<out_dir>/<tag>.json`` atomically, and returns
    the same JSON string. Never raises across JNI: failures come back (and land
    on disk) as ``{"ok": false, ...}`` so the host driver can report them.

    ``sims``/``k_dets`` exist for the desktop tests only; the on-device service
    never passes them, so the phone always benches the YAML champion budget.
    """
    tag = str(tag)
    out_dir = str(out_dir)
    # Belt-and-braces: the E4 archive dir is files/games/ and this bench must
    # never write there — not results, not even its own error report. A refused
    # out_dir disables the disk write entirely (the JSON is still returned).
    writable = os.path.basename(os.path.normpath(out_dir)) != "games"
    try:
        if not writable:
            raise ValueError(
                f"out_dir {out_dir!r} refused: 'games' is the E4 archive dir")
        if not tag or any(c in tag for c in "/\\\0"):
            raise ValueError(f"bad tag {tag!r}")
        payload = _run(int(n_moves), int(rust_threads), int(seed),
                       sims, k_dets)
    except BaseException as exc:  # noqa: BLE001 — must not raise across JNI
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        payload = {
            "schema": SCHEMA, "ok": False, "tag": tag,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    payload["tag"] = tag
    text = json.dumps(payload, indent=1)
    if not writable:
        return text
    # A malformed tag still gets its error report on disk, under a safe name.
    safe_tag = (tag if tag and not any(c in tag for c in "/\\\0")
                else "bench_error")
    try:
        os.makedirs(out_dir, exist_ok=True)
        tmp = os.path.join(out_dir, f".{safe_tag}.json.tmp")
        with open(tmp, "w") as f:
            f.write(text)
        os.replace(tmp, os.path.join(out_dir, f"{safe_tag}.json"))
    except OSError:
        # Desktop tests pass a writable tmpdir; on device filesDir is writable.
        # If the write itself fails the returned JSON still carries the result.
        pass
    return text
