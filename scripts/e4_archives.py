#!/usr/bin/env python3
"""Who the phone archive was played AGAINST — the E4 anchor-eligibility gate.

## The hazard this exists to close

`measurement/e4_games/` is the owner-vs-CHAMPION stream. Every number the program
draws from it — the `A = +13.265 pts/game` anchor the Carcasum owner session is
chained through (`measurement/carcasum_owner_session_prep/PROTOCOL.md` §4), the
trend reads, the farm anomaly, the EV-loss grading — is a statement about the
CHAMPION. From 2026-08-30 the app can also play a **remote Carcasum** opponent
(`scripts/carcasum_remote/server.py`), and those games land in the SAME on-device
directory and come off the phone in the SAME `adb` pull. A single Carcasum game
silently pooled into that stream would move the one anchor the session's whole
discriminator hangs off, in the direction that manufactures a result.

The app stamps `opponent` in every archive (it always has — all 56 archives on
record carry `opponent: "champion"`), so the label is available. **A label
nothing conditions on protects nothing**, which is what this module is for.

## The rule, and why it is ABSENT-EXCLUDES rather than absent-includes

    anchor-eligible  <=>  blob["opponent"] == "champion"

An archive with **no** `opponent` key is EXCLUDED and reported, not waved
through. That is safe by measurement, not by hope: every archive in the ledger
today carries the field (verified in `tests/test_e4_archives.py`), so absence can
only mean a foreign, hand-edited, or truncated file — none of which belongs in
an anchor. The same reasoning the ledger already applies to `rules_profile`:
"the discriminator is the archive's own stamp, and its ABSENCE means a different
build" (`measurement/e4_games/README.md`).

Note this is deliberately an ALLOW-list of one value, not a deny-list of
`carcasum_remote_*`. A deny-list has to be updated every time a new opponent
appears, and the failure mode of forgetting is silent pooling; the failure mode
of forgetting an allow-list entry is a loud "0 archives selected".

## Who conditions on it

Wired into the directory-scanning readers that produce anchor statistics:

* `scripts/e4_deck_baseline.select_archives` — the house-pattern selector, also
  used by `scripts/e4_deck_baseline_analyze.py` and `tests/test_e4_deck_baseline.py`
* `scripts/analyzer/j13_pregate.py`
* `scripts/e1_winobj/e1_pregate.py`
* `measurement/e4_ply_pricing_20260827/price_plies.py`

Readers that take an EXPLICIT single archive path (`scripts/analyzer/ev_loss.py`,
`scripts/analyzer/e4_diff.py`) are not wired: the caller has already chosen the
game, and grading one remote game on purpose is legitimate. Readers that use the
directory as a POSITION CORPUS rather than a tally (`scripts/tiletie/build_positions.py`,
`scripts/rustport/reconcile_*.py`, `scripts/measurement_infra/window_truncation_census.py`,
`scripts/classical_search/*_e4_replay.py`) are also not wired — a remote game is
still a valid `fixed_v1` position stream — but they should carry the
`game_label`/`source` through so a corpus stays sortable. If you add a new reader
that produces a MARGIN, a RECORD or a TREND, wire it here.
"""
from __future__ import annotations

import json
from pathlib import Path

#: The one opponent the E4 champion anchor is about.
CHAMPION_OPPONENT = "champion"

#: What the remote-opponent server's games are stamped with. Listed for
#: readability and for error messages ONLY — the gate is the allow-list above,
#: never a deny-list containing this.
REMOTE_CARCASUM_PREFIX = "carcasum_remote"


def opponent_of(blob: dict) -> str | None:
    """The archive's own `opponent` stamp, or None when it carries none."""
    v = blob.get("opponent")
    return None if v is None else str(v)


def is_anchor_eligible(blob: dict) -> bool:
    """True iff this archive belongs in the owner-vs-CHAMPION anchor."""
    return opponent_of(blob) == CHAMPION_OPPONENT


def rejection_reason(blob: dict) -> str | None:
    """A human-readable reason, or None when the archive is eligible."""
    opp = opponent_of(blob)
    if opp == CHAMPION_OPPONENT:
        return None
    if opp is None:
        return ("no `opponent` stamp — every archive in the ledger carries one, so "
                "an unstamped file is foreign/hand-edited/truncated and is excluded "
                "from the champion anchor")
    if opp.startswith(REMOTE_CARCASUM_PREFIX):
        return (f"played against {opp!r} (the remote Carcasum opponent, "
                "scripts/carcasum_remote/server.py) — NOT the champion; excluded "
                "from the champion anchor by construction")
    return f"played against {opp!r}, not {CHAMPION_OPPONENT!r}"


def filter_anchor(blobs, *, on_reject=None) -> list:
    """Keep only anchor-eligible archives; report every rejection.

    `on_reject(blob, reason)` is called for each dropped archive. The default
    prints to stderr — a silent drop is the failure mode this module exists to
    prevent, so there is deliberately no quiet mode.
    """
    import sys

    kept = []
    for b in blobs:
        why = rejection_reason(b)
        if why is None:
            kept.append(b)
            continue
        if on_reject is not None:
            on_reject(b, why)
        else:
            name = b.get("_path") or b.get("finished_at") or "<archive>"
            sys.stderr.write(f"[e4_archives] EXCLUDED {name}: {why}\n")
    return kept


def load_dir(archive_dir, *, anchor_only: bool = True) -> list[dict]:
    """Every `*.json` in `archive_dir`, each with its path under `_path`.

    `anchor_only=False` returns everything, for tooling that legitimately wants
    the remote games too (a Carcasum-session tally, say).
    """
    out = []
    for p in sorted(Path(archive_dir).glob("*.json")):
        try:
            blob = json.loads(p.read_text())
        except Exception as exc:                                  # noqa: BLE001
            raise RuntimeError(f"{p} is not readable JSON: {exc}") from None
        blob["_path"] = str(p)
        out.append(blob)
    return filter_anchor(out) if anchor_only else out
