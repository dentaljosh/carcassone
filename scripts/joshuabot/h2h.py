#!/usr/bin/env python3
"""Joshua-bot vs the production champion — the deck-paired H2H driver.

WHY. ``measurement/e4_games`` is the only stream this project has against a
HUMAN, and the human is currently ahead (+10 pts/game lean). One game an evening
can never power that. ``carcassonne_ai.joshua_bot.JoshuaBot`` encodes the eight
rules the owner described on 2026-08-12 (J1..J8, see
``measurement/joshuabot_20260812/SPEC.md``); this driver plays that scripted
strategy against the champion of record at deck-paired volume, so the question
"is the lean IN these rules?" becomes answerable at n=400-800 instead of n=15.

⚠️ **This is an INSTRUMENT, not a strength lever and not a champion candidate.**
Nothing here promotes anything. The output is a margin distribution.

WHAT IT REUSES (nothing about the agent, the deal, or the game loop is
re-implemented here — the same discipline as ``scripts/e4_deck_baseline.py``,
whose structure this file follows deliberately):
  * ``scripts/human_anchor/env_preamble.py`` — the production leaf env, imported
    before ``carcassonne_ai`` in every worker;
  * ``scripts/e4_deck_baseline.export_profile_env`` — the R9 latch (imported, as
    ``scripts/jcz_match/match.py`` does, never copied);
  * ``champion_factory.make_production_champion("fair", ...)`` — the champion of
    record at the PRODUCTION.yaml budget, ``verify=True``;
  * ``mirror_protocol.resolve_execution`` — the rust backend + ``rust_threads``;
  * ``play_harness.play_game`` — THE game loop (mirror seat/advance, telemetry,
    signed manifest). JoshuaBot slots into it with NO harness change: it exposes
    ``choose_action(board) -> int`` plus the telemetry attributes the harness
    snapshots, and has no ``start_game``/``advance``, so ``mirror_protocol``
    correctly skips it.

DECK PAIRING is the whole point (CLAUDE.md n-thresholds: deck-paired ~halves the
variance, and WITHIN-BAND deck-paired contrasts are the robust class). Every deck
seed is played TWICE, seats swapped, and the reported statistic is the per-deck
mean of ``joshua_score - champion_score``. Seat-major ordering means a killed run
is still seat-balanced.

RULES PROFILE. Default ``fixed_v1`` — the epoch the E4 human games are played in
(and the only profile the app stamps since 2026-08-05), so the bot is measured
under the same rules as the human it is imitating. ⚠️ ``fixed_v1`` implies
``CARCASSONNE_FIX_R9=1``, which is NOT the production default: numbers from here
are NOT comparable to walled elo. Pass ``--profile walled`` for an R9-off run.

VARIANT TOURNAMENT. The owner's answer to the SPEC's open questions was "test these
and see what wins empirically", so the three contested axes are CLI flags:
``--j7-weight`` (hesitate vs naive), ``--j8-break-reserve-floor`` (does a pivotal
overcommit break the J3 reserve floor), ``--j9-avoid-cloisters`` (his stated
cloister adaptation), on top of ``--preset``. Every flag lands in the run's
``<out>.manifest.json`` AND on every JSONL record (``joshua_variant_id`` /
``joshua_axes`` / ``joshua_overrides``), so a cell is self-describing. **One
variant per ``--out``** — the driver refuses to append a different variant to an
existing file, because a blended paired margin is not a measurement of anything.

Usage:
    # bench ONE game at production knobs (do this before the fleet)
    .venv/bin/python scripts/joshuabot/h2h.py --decks 1 --limit 1 \
        --out /tmp/jb_bench.jsonl

    # the fleet (detached), n=400 paired decks = 800 games
    setsid nohup nice -n 19 .venv/bin/python scripts/joshuabot/h2h.py \
        --decks 400 --preset current --workers 14 \
        --out measurement/joshuabot_20260812/h2h_current.jsonl \
        --resume >> measurement/joshuabot_20260812/driver.log 2>&1 & disown

    # a tournament arm: naive J7 + chance-taking J8 + cloister caution
    setsid nohup nice -n 19 .venv/bin/python scripts/joshuabot/h2h.py \
        --decks 400 --preset current --j7-weight 0.0 \
        --j8-break-reserve-floor --j9-avoid-cloisters --workers 14 \
        --out measurement/joshuabot_20260812/h2h_j7w0_j8brk_j9av.jsonl \
        --resume >> measurement/joshuabot_20260812/driver.log 2>&1 & disown
"""
from __future__ import annotations

# ⚠️ STDLIB ONLY at module level. `carcassonne_ai` must NOT be imported before
# `CARCASSONNE_FIX_R9` is exported (import-latched into a Rust OnceLock), and this
# module is re-imported by every spawn worker.
import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
HUMAN_ANCHOR = SCRIPTS / "human_anchor"

SCHEMA = "carcassonne-joshuabot-h2h/v1"

#: Champion agent-seed base. Cell (deck_seed, joshua_seat) -> a deterministic
#: seed. JoshuaBot itself takes no seed: it is deterministic by construction, so
#: a re-run of a cell is a genuine repeat of the SAME player on both sides.
SEED_BASE = 9_400_000

DEFAULT_PROFILE = "fixed_v1"
DEFAULT_SEED_BASE = 5_400_000


def champion_seed(deck_seed: int, joshua_seat: int) -> int:
    """Deterministic champion seed for a cell."""
    return SEED_BASE + (int(deck_seed) % 1_000_000) * 4 + int(joshua_seat) * 2


# --------------------------------------------------------------------------- #
# the tournament axes                                                          #
# --------------------------------------------------------------------------- #
def _parse_override(text: str) -> tuple[str, object]:
    """``key=value`` -> a typed (key, value). bool/int/float/str, in that order —
    the escape hatch for any :class:`JoshuaParams` knob that has no named flag."""
    if "=" not in text:
        raise argparse.ArgumentTypeError(f"--override wants key=value, got {text!r}")
    key, _, raw = text.partition("=")
    key, raw = key.strip(), raw.strip()
    low = raw.lower()
    if low in ("true", "false"):
        return key, low == "true"
    for cast in (int, float):
        try:
            return key, cast(raw)
        except ValueError:
            pass
    return key, raw


def build_overrides(args) -> dict:
    """The RESOLVED variant knobs for this run: the three named tournament axes
    first, then any ``--override key=value`` on top (so an explicit override
    always wins). Returned dict goes verbatim into ``JoshuaBot(overrides=...)``,
    the run manifest, and every JSONL record."""
    ov: dict = {
        "j7_weight": float(args.j7_weight),
        "j8_break_reserve_floor": bool(args.j8_break_reserve_floor),
        "j9_avoid_cloisters": bool(args.j9_avoid_cloisters),
    }
    for item in (args.override or []):
        k, v = _parse_override(item)
        ov[k] = v
    return ov


# --------------------------------------------------------------------------- #
# env / worker                                                                 #
# --------------------------------------------------------------------------- #
def export_profile_env(profile: str = DEFAULT_PROFILE) -> dict:
    """Export the import-latched env this profile owes (R9). House pattern —
    IMPORTED from ``scripts/e4_deck_baseline.py``, not re-implemented (the same
    reuse ``scripts/jcz_match/match.py`` makes)."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    from e4_deck_baseline import export_profile_env as _export
    return _export(profile)


_W: dict = {}


def _worker_init(profile: str, rust_threads: int, sims, k_dets, preset: str,
                 overrides: dict) -> None:
    """Spawn-worker bootstrap: env FIRST, then the production leaf, then the engine."""
    export_profile_env(profile)
    if str(HUMAN_ANCHOR) not in sys.path:
        sys.path.insert(0, str(HUMAN_ANCHOR))
    import env_preamble                       # noqa: F401  leaf env, before carcassonne_ai
    import play_harness                       # noqa: F401  (imports env_preamble itself)
    from carcassonne_ai import rules_profile
    from carcassonne_ai.mirror_protocol import resolve_execution

    prof = rules_profile.activate(profile)
    ex = resolve_execution("rust", rust_threads=rust_threads)
    if not ex.is_rust:                        # the one thing that must not degrade
        raise RuntimeError(f"backend did not resolve to rust: {ex.describe()}")
    from carcassonne_ai.joshua_bot import JoshuaBot
    # The variant a FAILED cell must still be able to name (a failed record with
    # no `joshua_variant_id` would make `variants_in` blind to it and let a
    # later --resume of a DIFFERENT variant append into the same file).
    variant_id = JoshuaBot(None, preset=preset, overrides=dict(overrides or {})).variant_id
    _W.update(profile=profile, prof=prof, execution=dict(ex),
              factory_kwargs=ex.factory_kwargs(), sims=sims, k_dets=k_dets,
              preset=preset, overrides=dict(overrides or {}), variant_id=variant_id,
              play_harness=play_harness, env_resolved=env_preamble.RESOLVED)


def failed_record(cell: tuple, exc: BaseException, t0: float) -> dict:
    """The record a cell that RAISED leaves behind.

    ⚠️ House lesson (capoff, DECISIONS 2026-07-31): a game that dies
    deterministically and leaves ZERO records is the dangerous pattern — the loss
    is invisible, and it can be candidate-correlated (capoff's 16 missing games
    were exactly the ones its own style drove into the 25x25 window wall). So a
    raise is DATA: it is written to the same JSONL, with the seed, the seat and
    the exception text, and it is counted in the summary. It carries no
    ``winner``/``margin``, so every statistic in :func:`summarize` skips it by
    construction and no half-game can leak into the paired margin."""
    import traceback

    from carcassonne_ai import window_truncation as _WT
    deck_seed, joshua_seat = int(cell[0]), int(cell[1])
    rec = {
        "schema": SCHEMA + "/failed",
        "failed": True,
        "deck_seed": deck_seed,
        "joshua_seat": joshua_seat,
        "champ_seat": 1 - joshua_seat,
        "joshua_preset": _W.get("preset"),
        "joshua_variant_id": _W.get("variant_id"),
        "joshua_overrides": dict(_W.get("overrides") or {}),
        "champion_seed": champion_seed(deck_seed, joshua_seat),
        "rules_profile": _W.get("profile"),
        "winner": None,                       # keeps it out of every statistic
        "exc_type": type(exc).__name__,
        "exc": str(exc)[:2000],
        "traceback": "".join(traceback.format_exception(exc))[-4000:],
        "finished_at": time.time(),
        "cell_secs": round(time.time() - t0, 2),
    }
    # F-c: an exclusion that says WHY. Before this, the 2026-08-13 dossier had
    # only the exception text and had to reconstruct the root by replaying the
    # whole cell. `window_diag` is the search's own payload (cause / mask
    # counters / window / depth / dropped coordinates) and `window_root_record`
    # is the census-ready root `play_harness` already wrote to the sink.
    rec["window_truncation"] = _WT.is_window_truncation(exc)
    rec["window_diag"] = _WT.parse_diag(exc)
    root = getattr(exc, "window_root_record", None)
    if root is not None:
        rec["window_root_record"] = root
        rec["window_root_path"] = getattr(exc, "window_root_path", None)
    return rec


def _play_cell(cell: tuple) -> dict:
    """One (deck_seed, joshua_seat) game, GUARDED.

    A raise here used to kill ``imap_unordered`` and therefore the whole pool
    (2026-08-13: the J7ZERO confirm died at 269/800 on a rust
    ``NoLegalActionsAtInterior``). One pathological deck must cost one deck, not
    the run — so anything short of an operator interrupt becomes a failed record
    and the pool carries on."""
    t0 = time.time()
    try:
        return _play_cell_inner(cell)
    except (KeyboardInterrupt, SystemExit):    # operator/parent shutdown: propagate
        raise
    except BaseException as exc:               # noqa: BLE001 — incl. pyo3 PanicException
        return failed_record(cell, exc, t0)


def _play_cell_inner(cell: tuple) -> dict:
    """One (deck_seed, joshua_seat) game. Returns the JSONL record."""
    deck_seed, joshua_seat = cell
    PH = _W["play_harness"]
    prof = _W["prof"]
    from carcassonne_ai.champion_factory import make_production_champion
    from carcassonne_ai.game_wrapper import Game
    from carcassonne_ai.joshua_bot import JoshuaBot

    joshua_seat = int(joshua_seat)
    champ_seat = 1 - joshua_seat
    cseed = champion_seed(deck_seed, joshua_seat)
    t0 = time.time()
    game = Game(enable_legal_moves_cache=True, **prof.game_kwargs())

    bot = JoshuaBot(game, preset=_W["preset"], overrides=_W["overrides"])
    champ = make_production_champion(
        "fair", game=game, seed=int(cseed), sims=_W["sims"], k_dets=_W["k_dets"],
        verify=True, **_W["factory_kwargs"])
    agents = {joshua_seat: bot, champ_seat: champ}
    labels = {joshua_seat: f"joshuabot_{bot.variant_id}",
              champ_seat: f"champion_s{cseed}"}
    config = {
        "experiment": "joshuabot_h2h",
        "joshua_preset": _W["preset"],
        "joshua_variant_id": bot.variant_id,
        "joshua_overrides": dict(_W["overrides"]),
        "joshua_axes": bot.manifest["axes"],
        "joshua_seat": joshua_seat,
        "rules_profile": _W["profile"],
        "rules_manifest": prof.as_manifest(),
        "execution": _W["execution"],
        "sims_override": _W["sims"], "k_dets_override": _W["k_dets"],
        "champion_seed": cseed,
        "leaf_env": _W["env_resolved"],
    }
    rec = PH.play_game(game, int(deck_seed), agents, labels, config)

    r, m = rec["result"], rec["manifest"]
    scores = list(r["scores"])
    cm = (m.get("champion_manifests") or {}).get(str(champ_seat), {}) or {}
    n_moves = int(r["n_moves"])
    ms = {"joshua": 0.0, "champion": 0.0}
    nmv = {"joshua": 0, "champion": 0}
    for mv in rec["moves"]:
        who = "joshua" if int(mv["seat"]) == joshua_seat else "champion"
        ms[who] += float(mv["ms"])
        nmv[who] += 1
    return {
        "schema": SCHEMA,
        "deck_seed": int(deck_seed),
        "joshua_seat": joshua_seat,
        "champ_seat": champ_seat,
        "joshua_preset": _W["preset"],
        # the variant, on EVERY record: a cell is self-describing without the
        # sibling manifest.json and without dirname archaeology.
        "joshua_variant_id": bot.variant_id,
        "joshua_axes": bot.manifest["axes"],
        "joshua_overrides": dict(_W["overrides"]),
        "champion_seed": cseed,
        "scores": scores,
        # SIGN, everywhere: positive = Joshua-bot ahead.
        "margin_joshua_minus_champ": int(scores[joshua_seat] - scores[champ_seat]),
        "winner": ("joshua" if scores[joshua_seat] > scores[champ_seat] else
                   "champion" if scores[champ_seat] > scores[joshua_seat] else "draw"),
        "n_moves": n_moves,
        "deck_hash": m["deck_hash"],
        "leaf_hash": m["leaf_hash"],
        "rules_profile": _W["profile"],
        "execution": _W["execution"],
        "champion_id": cm.get("champion_id"),
        "total_sims_of_record": (cm.get("fair_deploy") or {}).get("total_sims"),
        "k_dets_of_record": (cm.get("fair_deploy") or {}).get("k_dets"),
        "sims_override": _W["sims"], "k_dets_override": _W["k_dets"],
        # the audit trail that makes the bot's play checkable after the fact
        "joshua_manifest": bot.manifest,
        "joshua_rule_fires": dict(sorted(bot.rule_fires.items())),
        "ms_per_move_joshua": round(ms["joshua"] / max(nmv["joshua"], 1), 1),
        "ms_per_move_champ": round(ms["champion"] / max(nmv["champion"], 1), 1),
        "agent_version": m["agent_version"],
        "wall_secs": float(r["wall_secs"]),
        "finished_at": time.time(),
        "cell_secs": round(time.time() - t0, 2),
    }


# --------------------------------------------------------------------------- #
# driver                                                                       #
# --------------------------------------------------------------------------- #
def read_records(out_path: Path) -> list[dict]:
    """Every well-formed JSONL record in an output file (a torn last line from a
    dirty crash is skipped, not fatal)."""
    out: list[dict] = []
    if not out_path.exists():
        return out
    for line in out_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def load_done(out_path: Path) -> set[tuple[int, int]]:
    """Every cell already ON DISK — scored OR failed.

    A failed cell counts as done because these failures are DECK-DETERMINISTIC
    (same deck, same seeds, same two deterministic players ⇒ the same raise), so
    a plain --resume would otherwise re-burn a full game-time per pathological
    cell forever. ``--retry-failed`` re-opens them for a code fix that claims to
    have made them playable."""
    done: set[tuple[int, int]] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:      # a torn last line from a dirty crash
                continue
            if "deck_seed" in d and "joshua_seat" in d:
                done.add((int(d["deck_seed"]), int(d["joshua_seat"])))
    return done


def load_failed(out_path: Path, include_resolved: bool = False) -> set[tuple[int, int]]:
    """The cells already on disk as OUTSTANDING failed records.

    ⚠️ RESOLVED failures are excluded by default. A cell that failed on one pass
    and SUCCEEDED on a later ``--retry-failed`` pass has BOTH records in the
    stream (the JSONL is append-only; nothing rewrites the old line) — THE
    SUCCESS RECORD IS THE ARBITER, exactly as in
    ``scripts/classical_search/eval_fair_puct.load_failures`` (commit 2f5d0929),
    where the arbiter is the result FILE. Excluding resolved cells here means a
    second ``--retry-failed`` pass cannot re-open a cell that already completed
    and append a duplicate success record. Pass ``include_resolved=True`` for
    the forensic view (every cell that EVER failed)."""
    failed: set[tuple[int, int]] = set()
    succeeded: set[tuple[int, int]] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "deck_seed" not in d or "joshua_seat" not in d:
                continue
            key = (int(d["deck_seed"]), int(d["joshua_seat"]))
            if d.get("failed"):
                failed.add(key)
            elif d.get("winner"):
                succeeded.add(key)
    return failed if include_resolved else failed - succeeded


def variants_in(out_path: Path) -> set[str]:
    """Every ``joshua_variant_id`` already present in an output file. The guard
    that stops a ``--resume`` with different flags from blending two players into
    one paired margin."""
    seen: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            v = d.get("joshua_variant_id")
            if v:
                seen.add(str(v))
    return seen


def build_cells(seeds, done: set) -> list[tuple]:
    """Deck-paired and seat-major: every deck gets BOTH seatings adjacently, so a
    killed run leaves complete pairs rather than a seat-biased prefix."""
    cells = []
    for s in seeds:
        for seat in (0, 1):
            if (int(s), seat) not in done:
                cells.append((int(s), seat))
    return cells


def summarize(records: list[dict]) -> dict:
    """Raw win rate + the DECK-PAIRED margin (the low-variance statistic).

    Paired = per deck, the mean of ``joshua - champion`` over the two seatings;
    only decks with BOTH seatings scored contribute. This is the number a verdict
    should be read off — never the unpaired mean.

    FAILED cells (``failed: true``, no ``winner``) are excluded from every
    statistic and reported separately as ``n_failed`` / ``failure_rate`` /
    ``failed_cells``. A reader must never have to infer an exclusion from a
    record count that does not add up — the count is stated
    (``n_records == n_scored + n_failed + n_resolved_failures``).

    ⚠️ A RESOLVED failure is not a failure. A cell that failed on one pass and
    SUCCEEDED on a later ``--retry-failed`` pass has BOTH records in the stream —
    the success record is the arbiter (mirrors
    ``scripts/classical_search/eval_fair_puct.py``, commit 2f5d0929, where the
    arbiter is the result file). Counting the stale record would report
    ``n_failed=1`` on a cell that completed cleanly — and ``failure_rate`` is the
    input to the PRE-REGISTERED VALIDITY TRIGGER (>0.5% ⇒ stop and investigate),
    so an overstated rate can void a good cell. The failure record is never
    deleted: its forensics are reported under ``n_resolved_failures`` /
    ``resolved_failed_cells``, so a flaky game stays visible without voiding
    the cell."""
    ok = [r for r in records if r.get("winner")]
    ok_keys = {(int(r["deck_seed"]), int(r["joshua_seat"])) for r in ok}
    allbad = [r for r in records if r.get("failed")]
    # THE SUCCESS RECORD IS THE ARBITER: a failure record whose cell has a
    # success record in the same stream is RESOLVED, not a failure of this run.
    bad = [r for r in allbad
           if (int(r["deck_seed"]), int(r["joshua_seat"])) not in ok_keys]
    fixed = [r for r in allbad
             if (int(r["deck_seed"]), int(r["joshua_seat"])) in ok_keys]
    wins = sum(1 for r in ok if r["winner"] == "joshua")
    draws = sum(1 for r in ok if r["winner"] == "draw")
    by_deck: dict[int, dict[int, list[int]]] = {}
    for r in ok:
        by_deck.setdefault(int(r["deck_seed"]), {}).setdefault(
            int(r["joshua_seat"]), []).append(int(r["margin_joshua_minus_champ"]))
    paired = [sum(sum(v) / len(v) for v in seats.values()) / 2.0
              for seats in by_deck.values() if len(seats) == 2]
    n = len(ok)
    mean_p = sum(paired) / len(paired) if paired else None
    var = (sum((x - mean_p) ** 2 for x in paired) / (len(paired) - 1)
           if paired and len(paired) > 1 else None)
    sem = (var / len(paired)) ** 0.5 if var else None
    fires: dict[str, int] = {}
    for r in records:
        for k, v in (r.get("joshua_rule_fires") or {}).items():
            fires[k] = fires.get(k, 0) + int(v)
    # the failure_rate denominator excludes resolved records (they are neither a
    # scored game nor a failure of this run); on a zero-failure run it is exactly
    # len(records), so nothing changes there.
    n_live = len(records) - len(fixed)
    return {
        "variant_ids": sorted({str(r["joshua_variant_id"]) for r in records
                               if r.get("joshua_variant_id")}),
        "n_records": len(records), "n_scored": n,
        # ⚠️ THE EXCLUSION LINE. Read it before the margin.
        "n_failed": len(bad),
        "failure_rate": (len(bad) / n_live) if n_live else None,
        "failed_cells": [{"deck_seed": int(r["deck_seed"]),
                          "joshua_seat": int(r["joshua_seat"]),
                          "exc_type": r.get("exc_type"),
                          "exc": r.get("exc")} for r in bad],
        "failed_by_seat": {"0": sum(1 for r in bad if int(r["joshua_seat"]) == 0),
                           "1": sum(1 for r in bad if int(r["joshua_seat"]) == 1)},
        # NOT failures of this run — a crash that a later --retry-failed pass
        # played through. Counted separately (never in `failure_rate`, which
        # gates the pre-registered validity trigger) so a flaky game stays
        # visible without voiding the cell. Mirrors eval_fair_puct's
        # `n_resolved_failures` / `resolved_failed_cells`.
        "n_resolved_failures": len(fixed),
        "resolved_failed_cells": [{"deck_seed": int(r["deck_seed"]),
                                   "joshua_seat": int(r["joshua_seat"]),
                                   "exc_type": r.get("exc_type"),
                                   "exc": r.get("exc")} for r in fixed],
        "wins": wins, "draws": draws, "losses": n - wins - draws,
        "win_rate": (wins + 0.5 * draws) / n if n else None,
        "n_paired_decks": len(paired),
        "paired_margin_mean": mean_p,
        "paired_margin_sem": sem,
        "paired_margin_z": (mean_p / sem) if (mean_p is not None and sem) else None,
        "mean_margin_unpaired": (sum(r["margin_joshua_minus_champ"] for r in ok) / n
                                 if n else None),
        "rule_fires_total": dict(sorted(fires.items())),
    }


def close_out(run_manifest: dict, man_path: Path, out_path: Path,
              n_failed_this_leg: int) -> dict:
    """Print the summary, shout the exclusion line, and close the manifest.

    The summary is over the WHOLE output file, not just this leg — a ``--resume``
    must not hide failures banked by an earlier leg."""
    summary = summarize(read_records(out_path))
    print(json.dumps(summary, indent=1))
    if summary["n_resolved_failures"]:
        # Informational, never a trigger: these games ended up PLAYED. The failed
        # records stay in the JSONL (append-only) purely as forensics.
        print(f"\n[joshuabot-h2h] {summary['n_resolved_failures']} earlier failure(s) "
              f"were RESOLVED by a later successful retry — not counted as failures "
              f"(the failed records stay in the JSONL for forensics): "
              f"{[(c['deck_seed'], c['joshua_seat'], c['exc_type']) for c in summary['resolved_failed_cells']]}",
              flush=True)
    if summary["n_failed"]:
        print(f"\n⚠️ [joshuabot-h2h] {summary['n_failed']} FAILED CELL(S) = "
              f"{100.0 * (summary['failure_rate'] or 0.0):.2f}% of "
              f"{summary['n_records']} records — these are EXCLUSIONS, not zeros, "
              f"and a paired deck with one dead seat is dropped ENTIRELY. by seat "
              f"{summary['failed_by_seat']}. Cells: "
              f"{[(c['deck_seed'], c['joshua_seat']) for c in summary['failed_cells']]}",
              flush=True)
    run_manifest["summary"] = summary            # the manifest closes the loop
    run_manifest["n_failed_this_leg"] = int(n_failed_this_leg)
    man_path.write_text(json.dumps(run_manifest, indent=1))
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--decks", type=int, default=400,
                    help="number of deck seeds; each is played BOTH seatings, so "
                         "the game count is 2x this (400 -> 800 games)")
    ap.add_argument("--seed-base", type=int, default=DEFAULT_SEED_BASE)
    ap.add_argument("--preset", default="current", choices=("current", "early"),
                    help="J10 epoch: 'current' (farm-disciplined, the default) or "
                         "'early' (farm-aggressive, his first few games)")
    # --- the tournament axes (SPEC §7; owner: "test these and see what wins") --
    ap.add_argument("--j7-weight", type=float, default=1.0,
                    help="J7 close-vs-farm hesitation. 1.0 (default) counts his 3 "
                         "farm points a SECOND time (the base already pays them "
                         "once) = 'i hesitate'; 0.0 recovers the naive count.")
    ap.add_argument("--j8-break-reserve-floor", action="store_true",
                    help="let a PIVOTAL-feature overcommit break the J3 reserve "
                         "floor ('you have to take chances'). Default off = J3 "
                         "wins the J3/J8 conflict.")
    ap.add_argument("--j9-avoid-cloisters", action="store_true",
                    help="J9 cloister caution: no cloister claim in the first "
                         "j9_cloister_block_frac of the bag unless its 3x3 already "
                         "holds j9_min_surrounding tiles. Default off.")
    ap.add_argument("--override", action="append", metavar="KEY=VALUE",
                    help="any other JoshuaParams knob, repeatable (e.g. "
                         "--override j9_min_surrounding=5). Applied AFTER the "
                         "named axes, so it wins. An unknown knob raises.")
    ap.add_argument("--profile", default=DEFAULT_PROFILE,
                    help="rules profile (default fixed_v1 = the E4 epoch; implies R9=1)")
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--rust-threads", type=int, default=1)
    ap.add_argument("--sims", type=int, default=None, help="SMOKE ONLY: override sims_per_det")
    ap.add_argument("--k-dets", type=int, default=None, help="SMOKE ONLY: override k_dets")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--retry-failed", action="store_true",
                    help="on --resume, re-attempt cells already on disk as FAILED "
                         "records. Default off: these failures are deck-deterministic, "
                         "so a retry just re-burns a game-time. Use after a code fix. "
                         "A cell whose retry already SUCCEEDED is resolved and is "
                         "never re-opened.")
    ap.add_argument("--limit", type=int, default=0, help="stop after N cells (bench)")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seeds = [args.seed_base + i for i in range(max(1, args.decks))]
    overrides = build_overrides(args)
    done = load_done(out_path) if args.resume else set()
    prior_failed = load_failed(out_path)
    if args.retry_failed:
        done -= prior_failed
    # ⚠️ A --resume that CHANGES the variant would silently mix two players into
    # one file, and the paired margin would be a blend of both. Refuse.
    prior = variants_in(out_path)
    cells = build_cells(seeds, done)
    if args.limit:
        cells = cells[: args.limit]

    env = export_profile_env(args.profile)     # inherited by every spawn worker

    # the run manifest: the FULL resolved config, written BEFORE any game
    # (house rule — a result must never need dirname archaeology to interpret).
    from carcassonne_ai.joshua_bot import JoshuaBot   # after export_profile_env
    probe = JoshuaBot(None, preset=args.preset, overrides=overrides)
    variant = probe.variant_id
    if prior - {variant}:
        raise SystemExit(
            f"[joshuabot-h2h] REFUSING to append: {out_path} already holds "
            f"variant(s) {sorted(prior)} and this run is {variant!r}. Use a "
            f"separate --out per variant.")
    run_manifest = {
        "schema": SCHEMA + "/manifest",
        "experiment": "joshuabot_h2h",
        "variant_id": variant,
        "joshua_manifest": probe.manifest,          # full resolved JoshuaParams
        "preset": args.preset, "overrides": overrides,
        "rules_profile": args.profile, "profile_env": env,
        "seed_base": args.seed_base, "decks": len(seeds),
        "sims_override": args.sims, "k_dets_override": args.k_dets,
        "workers": args.workers, "rust_threads": args.rust_threads,
        "argv": list(sys.argv), "utc": time.time(),
    }
    man_path = out_path.with_suffix(out_path.suffix + ".manifest.json")
    man_path.write_text(json.dumps(run_manifest, indent=1))

    print(f"[joshuabot-h2h] variant={variant} profile={args.profile} {env} "
          f"decks={len(seeds)} workers={args.workers} done={len(done)} "
          f"prior_failed={len(prior_failed)} retry_failed={args.retry_failed} "
          f"todo={len(cells)} manifest={man_path}", flush=True)
    if not cells:
        print("[joshuabot-h2h] nothing to do — exiting 0", flush=True)
        # ⚠️ still close the manifest out: the write above REPLACED the previous
        # manifest, and a no-op --resume must not be the thing that erases the
        # summary — least of all its exclusion count.
        close_out(run_manifest, man_path, out_path, 0)
        return 0

    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    t0 = time.time()
    records: list[dict] = []
    n_failed = 0
    with out_path.open("a") as fh:
        with ctx.Pool(processes=max(1, min(args.workers, len(cells))),
                      initializer=_worker_init,
                      initargs=(args.profile, args.rust_threads, args.sims,
                                args.k_dets, args.preset, overrides)) as pool:
            for rec in pool.imap_unordered(_play_cell, cells):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                os.fsync(fh.fileno())          # per-GAME checkpoint (dirty-reboot safe)
                records.append(rec)
                if rec.get("failed"):
                    n_failed += 1
                    print(f"[{len(records)}/{len(cells)}] ⚠️ FAILED CELL "
                          f"deck={rec['deck_seed']} joshua_seat={rec['joshua_seat']} "
                          f"{rec['exc_type']}: {rec['exc']} "
                          f"({n_failed} failed so far — the pool CONTINUES; the cell "
                          f"is an EXCLUSION, see the summary)", flush=True)
                    continue
                print(f"[{len(records)}/{len(cells)}] deck={rec['deck_seed']} "
                      f"joshua_seat={rec['joshua_seat']} scores={rec['scores']} "
                      f"margin={rec['margin_joshua_minus_champ']:+d} "
                      f"joshua={rec['ms_per_move_joshua']}ms/mv "
                      f"champ={rec['ms_per_move_champ']}ms/mv", flush=True)

    print(f"\n[joshuabot-h2h] DONE {len(records)} cells in {(time.time()-t0)/60:.1f} min "
          f"({n_failed} FAILED)")
    close_out(run_manifest, man_path, out_path, n_failed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
