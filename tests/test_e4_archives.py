"""The E4 anchor-eligibility gate — `scripts/e4_archives.py`.

`measurement/e4_games/` is the owner-vs-CHAMPION stream and, since the phone
gained a remote-Carcasum opponent (2026-08-30), it can also receive games the
champion never played. The anchor drawn from that directory
(`A = +13.265 pts/game`) is the single number the Carcasum owner session's whole
adaptation-share discriminator is chained through, so one pooled Carcasum game
would move the answer in the direction that manufactures the headline.

These tests pin the gate AND the empirical fact it rests on: that every archive
on record carries an `opponent` stamp, which is what licenses "absent EXCLUDES"
as a safe default rather than a hopeful one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import e4_archives as EA  # noqa: E402

E4_DIR = REPO / "measurement" / "e4_games"


def test_every_ledger_archive_is_stamped_and_the_anchor_is_the_champion_subset():
    """The empirical premise of `absent excludes`.

    If this ever fails because a genuine champion archive has no `opponent` key,
    do NOT relax the gate — backfill the stamp. The gate is the cheap half; the
    expensive half is a silently pooled game nobody notices for a month.

    ⚠️ RE-POINTED 2026-09-02 (was `test_the_ledger_is_entirely_champion_games_today`,
    asserting `kinds == ["champion"]`). That clause was an empirical statement about
    the ledger's COMPOSITION, not about the gate, and it expired the day the first
    remote Carcasum game was archived — it has been failing on 9 such games. Worse,
    it was written to fail again on every future one, and the "fix the labels"
    ruling (2026-09-02) makes the set of non-champion spellings open-ended.

    What is actually load-bearing survives verbatim: every archive carries a stamp,
    and the anchor set is EXACTLY the champion-stamped subset — nothing unstamped
    and nothing foreign slips in. That is spelling-agnostic, so it keeps holding as
    new opponent labels appear.
    """
    blobs = []
    for p in sorted(E4_DIR.glob("*.json")):
        b = json.loads(p.read_text())
        b["_path"] = p.name
        blobs.append(b)
    assert blobs, "no E4 archives found — the ledger is the fixture here"
    missing = [b["_path"] for b in blobs if EA.opponent_of(b) is None]
    assert not missing, f"archives with no `opponent` stamp: {missing}"

    eligible = [b for b in blobs if EA.is_anchor_eligible(b)]
    assert eligible, "the ledger must still hold champion games"
    # The anchor set is exactly the champion-stamped subset — in both directions.
    assert all(EA.opponent_of(b) == "champion" for b in eligible)
    for b in blobs:
        if EA.opponent_of(b) != "champion":
            assert not EA.is_anchor_eligible(b), b["_path"]
            # Every non-champion archive in the ledger today is a remote game, and
            # each says which one it was — the property the label ruling protects.
            assert EA.opponent_of(b).startswith(EA.REMOTE_CARCASUM_PREFIX), b["_path"]


def test_a_remote_carcasum_game_is_excluded_and_says_why():
    blob = {"opponent": "carcasum_remote_5000ms", "scores": [90, 70]}
    assert not EA.is_anchor_eligible(blob)
    why = EA.rejection_reason(blob)
    assert "carcasum_remote_5000ms" in why
    assert "champion anchor" in why


@pytest.mark.parametrize("label", [
    "carcasum_remote_5000ms",        # every archive written before 2026-09-02
    "carcasum_remote_p103500",       # the server's own label, fixed-playout mode
    "carcasum_remote_2000ms",        # the server's own label, some other budget
    "carcasum_remote",               # the bare kind, belt-and-braces
])
def test_every_remote_label_spelling_is_excluded_and_says_why(label):
    """OWNER RULING 2026-09-02, "fix the labels": the archive's `opponent` stamp is
    now DERIVED from the server's own `/health` label instead of being the
    hardcoded `carcasum_remote_5000ms`, so the set of strings that can appear in
    this field is open-ended.

    That is safe here only because the gate is an ALLOW-LIST — eligible ⟺
    `opponent == "champion"` — so a label nobody has seen before is excluded by
    default rather than needing to be enumerated. This test is the standing proof
    that the new spellings do not slip through, and that the rejection message
    still names the actual opponent so a reader can see WHICH Carcasum played.
    """
    blob = {"opponent": label, "scores": [90, 70]}
    assert not EA.is_anchor_eligible(blob)
    why = EA.rejection_reason(blob)
    assert label in why
    assert "champion anchor" in why


def test_an_unstamped_archive_is_excluded_not_waved_through():
    blob = {"scores": [90, 70]}
    assert EA.opponent_of(blob) is None
    assert not EA.is_anchor_eligible(blob)
    assert "no `opponent` stamp" in EA.rejection_reason(blob)


def test_the_gate_is_an_allow_list_not_a_deny_list():
    """A future opponent nobody has thought of must default to EXCLUDED.

    A deny-list has to be updated for every new opponent and fails SILENTLY when
    someone forgets; an allow-list fails loudly with "0 archives selected".
    """
    assert not EA.is_anchor_eligible({"opponent": "some_future_engine"})
    assert not EA.is_anchor_eligible({"opponent": "tier1"})
    assert EA.is_anchor_eligible({"opponent": "champion"})


def test_filter_reports_every_rejection():
    rejected = []
    kept = EA.filter_anchor(
        [{"opponent": "champion", "i": 0},
         {"opponent": "carcasum_remote_5000ms", "i": 1},
         {"i": 2}],
        on_reject=lambda b, why: rejected.append((b["i"], why)))
    assert [b["i"] for b in kept] == [0]
    assert [i for i, _ in rejected] == [1, 2]
    assert all(why for _, why in rejected)


def test_e4_deck_baseline_conditions_on_the_gate(tmp_path):
    """The house-pattern selector must drop a remote game from the corpus."""
    sys.path.insert(0, str(REPO / "scripts"))
    import e4_deck_baseline as DB

    champ = {"rules_profile": "fixed_v1", "opponent": "champion", "deck_seed": 1,
             "human_player": 0, "scores": [90, 70], "actions": [1, 2, 3]}
    remote = dict(champ, opponent="carcasum_remote_5000ms", deck_seed=2)
    unstamped = {k: v for k, v in champ.items() if k != "opponent"}
    unstamped["deck_seed"] = 3
    (tmp_path / "a.json").write_text(json.dumps(champ))
    (tmp_path / "b.json").write_text(json.dumps(remote))
    (tmp_path / "c.json").write_text(json.dumps(unstamped))

    picked = DB.select_archives(tmp_path, "fixed_v1")
    assert [a["deck_seed"] for a in picked] == [1], picked
