"""Tests for the measurement work-queue scheduler's decision core.

Everything the scheduler could get WRONG lives in scripts/scheduler/queue_lib.py
(the shell only does census / detached launch / ssh), so this is where the safety
rules are pinned:

  * a game-playing item with no prereg or no claimed band is BLOCKED, never READY
  * an item whose code is still in an unmerged worktree is NEEDS_MERGE, never READY
  * an item whose launch command has not landed is NOT_READY (skip, loud log)
  * two jobs never go to one box; the laptop is never used before its DONE marker
  * a dirty process census overrides a DONE marker (a marker can lie)
  * the wall-clock worker grant (W30 before 11:00, else W14)
  * nothing in the scheduler writes governance/
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SDIR = REPO / "scripts" / "scheduler"
sys.path.insert(0, str(SDIR))

import queue_lib as ql  # noqa: E402


# ------------------------------------------------------------------ fixtures --
def _box(**kw):
    b = {
        "host": "local",
        "occupant_label": "occupant",
        "occupant_markers": ["OCC_DONE"],
        "census_patterns": ["x"],
        "allow_idle_release": False,
        "workers_schedule": [{"before_hhmm": "11:00", "w": 30}, {"w": 14}],
        "marker_dir_local": "markers",
    }
    b.update(kw)
    return b


def _item(**kw):
    it = {"id": "i1", "priority": 10, "box": "local", "launch_cmd": ["run.sh"]}
    it.update(kw)
    return it


def _queue(items, boxes=None):
    return {"boxes": boxes or {"local": _box()}, "items": items}


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "markers").mkdir()
    return tmp_path


def _mk(root: Path, rel: str, mode: int = 0o644, body: str = "#!/bin/sh\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    p.chmod(mode)
    return p


def _tick(queue, root, state=None, census=None, now=None):
    return ql.tick(queue, root, state or {}, census or {"local": 0}, now=now)


# ---------------------------------------------------------------- validation --
def test_shipped_queue_file_is_valid():
    q = ql.load_json(SDIR / "queue.json")
    assert ql.validate_queue(q) == []


def test_shipped_queue_priorities_are_the_owner_order():
    q = ql.load_json(SDIR / "queue.json")
    order = [i["id"] for i in sorted(q["items"], key=lambda x: x["priority"])]
    assert order[0] == "window_truncation_census", "the cheap suspected-defect census runs first"
    assert order == ["window_truncation_census", "j13_pregate", "jrules_on_search"]


def test_validate_catches_missing_fields():
    errs = ql.validate_queue({"boxes": {}, "items": [{"id": "x"}]})
    assert any("non-empty" in e for e in errs)
    assert any("priority" in e for e in errs)


def test_validate_catches_duplicate_ids_and_unknown_box():
    errs = ql.validate_queue(_queue([_item(), _item(box="mars")]))
    assert any("duplicate item id" in e for e in errs)
    assert any("unknown box" in e for e in errs)


def test_validate_requires_a_default_workers_entry():
    errs = ql.validate_queue(
        _queue([_item()], {"local": _box(workers_schedule=[{"before_hhmm": "11:00", "w": 30}])}))
    assert any("no before_hhmm" in e for e in errs)


# ------------------------------------------------------------- worker grants --
def test_workers_follow_the_wall_clock_grant():
    b = _box()
    before = time.mktime(time.strptime("2026-08-13 09:54", "%Y-%m-%d %H:%M"))
    after = time.mktime(time.strptime("2026-08-13 11:30", "%Y-%m-%d %H:%M"))
    assert ql.workers_for(b, before) == 30
    assert ql.workers_for(b, after) == 14
    # exactly 11:00 is already "after"
    at11 = time.mktime(time.strptime("2026-08-13 11:00", "%Y-%m-%d %H:%M"))
    assert ql.workers_for(b, at11) == 14


def test_laptop_grant_is_flat():
    assert ql.workers_for(_box(workers_schedule=[{"w": 22}])) == 22


# ------------------------------------------------------------- item statuses --
def test_ready_when_command_landed_and_box_free(root):
    _mk(root, "run.sh", 0o755)
    _mk(root, "OCC_DONE")
    d = _tick(_queue([_item()]), root)
    assert d["items"]["i1"]["status"] == ql.READY
    assert d["dispatch"]["item"] == "i1"
    assert d["dispatch"]["launch_cmd"].endswith("run.sh")


def test_not_ready_when_launch_command_has_not_landed(root):
    _mk(root, "OCC_DONE")
    d = _tick(_queue([_item()]), root)
    assert d["items"]["i1"]["status"] == ql.NOT_READY
    assert "has not landed" in d["items"]["i1"]["reason"]
    assert d["dispatch"] is None


def test_not_ready_when_measurement_dir_absent(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item(dir="measurement/nope")]), root)
    assert d["items"]["i1"]["status"] == ql.NOT_READY
    assert "dir not created" in d["items"]["i1"]["reason"]


def test_non_executable_shell_script_still_dispatches_with_a_note(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o644)
    d = _tick(_queue([_item()]), root)
    assert d["items"]["i1"]["status"] == ql.READY
    assert "not chmod +x" in d["items"]["i1"]["launch_note"]


def test_non_executable_non_script_is_refused(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.bin", 0o644)
    d = _tick(_queue([_item(launch_cmd=["run.bin"])]), root)
    assert d["items"]["i1"]["status"] == ql.NOT_READY


def test_first_existing_launch_candidate_wins(root):
    _mk(root, "OCC_DONE")
    _mk(root, "b.sh", 0o755)
    d = _tick(_queue([_item(launch_cmd=["a.sh", "b.sh"])]), root)
    assert d["dispatch"]["launch_cmd"].endswith("b.sh")


# --------------------------------------------------------------- safety: games --
def test_game_playing_item_without_prereg_or_band_is_blocked(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item(plays_games=True)]), root)
    st = d["items"]["i1"]
    assert st["status"] == ql.BLOCKED
    assert "BLOCKED: prereg/band missing" in st["reason"]
    assert d["dispatch"] is None


def test_game_playing_item_with_prereg_but_no_band_is_still_blocked(root, monkeypatch):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    _mk(root, "PREREG.md")
    monkeypatch.setattr(ql, "band_on_disk", lambda b, **k: False)
    d = _tick(_queue([_item(plays_games=True, prereg="PREREG.md", band="1.24e11")]), root)
    assert d["items"]["i1"]["status"] == ql.BLOCKED
    assert "band not claimed" in d["items"]["i1"]["reason"]


def test_game_playing_item_with_prereg_and_claimed_band_is_ready(root, monkeypatch):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    _mk(root, "PREREG.md")
    monkeypatch.setattr(ql, "band_on_disk", lambda b, **k: True)
    d = _tick(_queue([_item(plays_games=True, prereg="PREREG.md", band="1.24e11")]), root)
    assert d["items"]["i1"]["status"] == ql.READY


def test_band_on_disk_reads_the_real_registry():
    reg = REPO / "governance" / "BAND_REGISTRY.csv"
    assert reg.exists(), "BAND_REGISTRY.csv must exist (doc_lint E3 fails closed on it)"
    assert not ql.band_on_disk("this-band-does-not-exist", reg)
    with open(reg, newline="") as fh:
        rows = [r[0].strip().strip('"') for r in csv.reader(fh) if r]
    real = [r for r in rows if r and not r.startswith("#") and r != "band_seed_start"]
    if real:
        assert ql.band_on_disk(real[0], reg)


def test_band_on_disk_false_when_registry_missing(tmp_path):
    assert not ql.band_on_disk("1e9", tmp_path / "nope.csv")


# --------------------------------------------------------------- safety: merge --
def test_unmerged_worktree_item_is_needs_merge_not_ready(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item(merge_probe_paths=["measurement/x/DESIGN.md"],
                            merge_note="needs a rust wheel rebuild")]), root)
    st = d["items"]["i1"]
    assert st["status"] == ql.NEEDS_MERGE
    assert "NEEDS HUMAN/ORCHESTRATOR MERGE" in st["reason"]
    assert "rust wheel" in st["reason"]
    assert d["dispatch"] is None


def test_merge_gate_precedes_the_prereg_gate(root):
    """An unmerged, game-playing item reports the merge notice first -- that is the
    action a human can actually take."""
    _mk(root, "OCC_DONE")
    d = _tick(_queue([_item(plays_games=True, merge_probe_paths=["gone.md"])]), root)
    assert d["items"]["i1"]["status"] == ql.NEEDS_MERGE


def test_merged_probe_present_falls_through_to_the_prereg_gate(root):
    _mk(root, "OCC_DONE")
    _mk(root, "DESIGN.md")
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item(plays_games=True, merge_probe_paths=["DESIGN.md"])]), root)
    assert d["items"]["i1"]["status"] == ql.BLOCKED


# ------------------------------------------------------------- box freeness ----
def test_box_busy_until_occupant_marker_exists(root):
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item()]), root)
    assert d["free_boxes"] == []
    assert d["items"]["i1"]["status"] == ql.WAIT_BOX
    assert "idle-release disabled" in d["boxes"]["local"]["reason"]


def test_dirty_census_overrides_a_done_marker(root):
    """A marker can lie -- a watchdog may have relaunched the occupant."""
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item()]), root, census={"local": 3})
    assert d["free_boxes"] == []
    assert "census guard" in d["boxes"]["local"]["reason"]
    assert d["dispatch"] is None


def test_unreachable_census_fails_closed(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    d = _tick(_queue([_item()]), root, census={"local": None})
    assert d["free_boxes"] == []
    assert "UNREACHABLE" in d["boxes"]["local"]["reason"]


def test_idle_release_holds_inside_the_grace_window(root):
    _mk(root, "run.sh", 0o755)
    q = _queue([_item()], {"local": _box(allow_idle_release=True, idle_release_secs=2700)})
    now = 1_000_000.0
    d1 = _tick(q, root, now=now)
    assert d1["free_boxes"] == []
    state = ql.merge_state({}, d1, q)
    d2 = ql.tick(q, root, state, {"local": 0}, now=now + 600)
    assert d2["free_boxes"] == [], "10 min of quiet must not release the box"
    assert "holding" in d2["boxes"]["local"]["reason"]


def test_idle_release_fires_after_the_grace_window(root):
    _mk(root, "run.sh", 0o755)
    q = _queue([_item()], {"local": _box(allow_idle_release=True, idle_release_secs=2700)})
    now = 1_000_000.0
    state = ql.merge_state({}, _tick(q, root, now=now), q)
    d = ql.tick(q, root, state, {"local": 0}, now=now + 3000)
    assert d["free_boxes"] == ["local"]
    assert "IDLE-RELEASE" in d["boxes"]["local"]["reason"]
    assert d["dispatch"]["item"] == "i1"


def test_idle_clock_resets_when_something_starts_running(root):
    _mk(root, "run.sh", 0o755)
    q = _queue([_item()], {"local": _box(allow_idle_release=True, idle_release_secs=2700)})
    now = 1_000_000.0
    state = ql.merge_state({}, _tick(q, root, now=now), q)
    state = ql.merge_state(state, ql.tick(q, root, state, {"local": 5}, now=now + 1000), q)
    d = ql.tick(q, root, state, {"local": 0}, now=now + 1100)
    assert d["free_boxes"] == [], "the idle clock must restart after a busy observation"


def test_laptop_never_released_by_idle_even_when_totally_quiet(root):
    _mk(root, "run.sh", 0o755)
    q = _queue([_item(box="laptop")],
               {"laptop": _box(host="laptop-wsl", allow_idle_release=False)})
    now = 1_000_000.0
    state = ql.merge_state({}, ql.tick(q, root, {}, {"laptop": 0}, now=now), q)
    d = ql.tick(q, root, state, {"laptop": 0}, now=now + 86400)
    assert d["free_boxes"] == [], "the laptop is owner-gated on its DONE marker"


# ------------------------------------------------------------- scheduling ------
def test_highest_priority_ready_item_wins(root):
    _mk(root, "OCC_DONE")
    _mk(root, "a.sh", 0o755)
    _mk(root, "b.sh", 0o755)
    q = _queue([_item(id="low", priority=99, launch_cmd=["a.sh"]),
                _item(id="high", priority=1, launch_cmd=["b.sh"])])
    d = _tick(q, root)
    assert d["dispatch"]["item"] == "high"
    assert d["items"]["low"]["status"] == ql.WAIT_BOX
    assert "taken by a higher-priority item" in d["items"]["low"]["reason"]


def test_never_two_jobs_on_one_box(root):
    _mk(root, "OCC_DONE")
    _mk(root, "a.sh", 0o755)
    q = _queue([_item(id="one", priority=1, launch_cmd=["a.sh"]),
                _item(id="two", priority=2, launch_cmd=["a.sh"])])
    state = ql.merge_state({}, _tick(q, root), q)
    state["items"]["one"] = {"status": ql.DISPATCHED, "box": "local", "pid": 1}
    d = ql.tick(q, root, state, {"local": 0})
    assert d["dispatch"] is None
    assert d["items"]["one"]["status"] == ql.DISPATCHED
    assert "in flight" in d["boxes"]["local"]["reason"]


def test_a_blocked_item_does_not_stop_a_lower_priority_ready_one(root):
    _mk(root, "OCC_DONE")
    _mk(root, "a.sh", 0o755)
    q = _queue([_item(id="blocked", priority=1, launch_cmd=["a.sh"], plays_games=True),
                _item(id="fine", priority=2, launch_cmd=["a.sh"])])
    d = _tick(q, root)
    assert d["items"]["blocked"]["status"] == ql.BLOCKED
    assert d["dispatch"]["item"] == "fine"


def test_any_box_item_prefers_its_prefer_box(root):
    _mk(root, "OCC_DONE")
    _mk(root, "LAP_DONE")
    _mk(root, "a.sh", 0o755)
    boxes = {"local": _box(), "laptop": _box(host="laptop-wsl", occupant_markers=["LAP_DONE"])}
    q = _queue([_item(box="any", prefer_box="laptop", launch_cmd=["a.sh"])], boxes)
    d = ql.tick(q, root, {}, {"local": 0, "laptop": 0})
    assert d["dispatch"]["box"] == "laptop"


def test_any_box_item_falls_back_when_preferred_box_busy(root):
    _mk(root, "OCC_DONE")
    _mk(root, "a.sh", 0o755)
    boxes = {"local": _box(), "laptop": _box(host="laptop-wsl", occupant_markers=["LAP_DONE"])}
    q = _queue([_item(box="any", prefer_box="laptop", launch_cmd=["a.sh"])], boxes)
    d = ql.tick(q, root, {}, {"local": 0, "laptop": 0})
    assert d["dispatch"]["box"] == "local"


# ---------------------------------------------------------------- completion ---
def test_scheduler_done_marker_makes_an_item_terminal(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    _mk(root, "markers/DONE_i1")
    d = _tick(_queue([_item()]), root)
    assert d["items"]["i1"]["status"] == ql.DONE
    assert d["drained"] is True
    assert d["dispatch"] is None


def test_scheduler_failed_marker_is_terminal_and_not_retried(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    _mk(root, "markers/FAILED_i1")
    d = _tick(_queue([_item()]), root)
    assert d["items"]["i1"]["status"] == ql.FAILED
    assert d["dispatch"] is None


def test_item_that_ran_itself_is_detected_via_done_if_exists(root):
    """The J13 pre-gate may RUN itself while being built -- notice, do not re-run."""
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    _mk(root, "READOUT.md")
    d = _tick(_queue([_item(done_if_exists=["READOUT.md"])]), root)
    assert d["items"]["i1"]["status"] == ql.DONE
    assert "own evidence on disk" in d["items"]["i1"]["reason"]


def test_dispatched_item_completes_when_its_marker_lands(root):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    q = _queue([_item()])
    state = {"items": {"i1": {"status": ql.DISPATCHED, "box": "local", "pid": 42}}}
    assert ql.tick(q, root, state, {"local": 1})["items"]["i1"]["status"] == ql.DISPATCHED
    _mk(root, "markers/DONE_i1")
    assert ql.tick(q, root, state, {"local": 0})["items"]["i1"]["status"] == ql.DONE


# ---------------------------------------------------------------- state file ---
def test_state_round_trips_and_keeps_dispatch_bookkeeping(root, tmp_path):
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    q = _queue([_item()])
    state = {"items": {"i1": {"status": ql.DISPATCHED, "box": "local", "pid": 7,
                              "dispatched_at": "2026-08-13T10:00:00"}}}
    state = ql.merge_state(state, ql.tick(q, root, state, {"local": 1}), q)
    assert state["items"]["i1"]["pid"] == 7
    assert state["items"]["i1"]["dispatched_at"] == "2026-08-13T10:00:00"
    p = tmp_path / "state.json"
    ql.write_state(state, p)
    assert json.loads(p.read_text())["items"]["i1"]["pid"] == 7


def test_history_is_capped(root):
    s: dict = {}
    for i in range(20):
        s = ql.append_history(s, "e", str(i), limit=5)
    assert len(s["history"]) == 5
    assert s["history"][-1]["detail"] == "19"


# ------------------------------------------------------------------ CLI --------
def test_cli_validate_and_tick_on_the_shipped_queue(tmp_path):
    assert ql.main(["validate", "--queue", str(SDIR / "queue.json")]) == 0
    state = tmp_path / "state.json"
    rc = ql.main(["tick", "--queue", str(SDIR / "queue.json"), "--state", str(state),
                  "--census", "local=0,laptop=99"])
    assert rc == 0
    s = json.loads(state.read_text())
    assert "laptop" in s["boxes"] and s["boxes"]["laptop"]["free"] is False


def test_cli_workers_prints_an_int():
    out = subprocess.run(
        [sys.executable, str(SDIR / "queue_lib.py"), "workers", "--box", "laptop"],
        capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "22"


def test_parse_census_treats_negatives_and_garbage_as_unreachable():
    assert ql._parse_census("local=0,laptop=-1") == {"local": 0, "laptop": None}
    assert ql._parse_census("local=x") == {"local": None}
    assert ql._parse_census("") == {}


# ------------------------------------------------------------ safety: writes ---
GOV_WRITE_RE = re.compile(
    r"(open\([^)]*governance[^)]*[\"']w"       # python write-open under governance/
    r"|>>?\s*\S*governance/"                    # shell redirect into governance/
    r"|sed -i\S*\s[^\n]*governance/"            # in-place edit
    r"|(cp|mv|rm|touch|tee)\s[^\n]*governance/)")


def test_scheduler_sources_never_write_governance():
    """Hard invariant: the scheduler READS governance/BAND_REGISTRY.csv (to refuse a
    game-playing item whose band is not claimed) and writes NOTHING under governance/
    -- no PRODUCTION.yaml edit, no band claim, no adjudication, no results.csv row."""
    for f in ("queue_lib.py", "work_queue.sh", "work_queue_watchdog.sh", "queue.json"):
        text = (SDIR / f).read_text()
        hit = GOV_WRITE_RE.search(text)
        assert hit is None, f"{f} appears to WRITE under governance/: {hit and hit.group(0)}"
    src = (SDIR / "queue_lib.py").read_text()
    # the only governance path the scheduler knows, and it is opened read-only
    assert 'BAND_REGISTRY = ROOT / "governance" / "BAND_REGISTRY.csv"' in src
    assert 'open(registry, newline="")' in src, "the band check must be a plain read"
    # CODE lines only -- the shell headers legitimately say "NEVER edits
    # governance/PRODUCTION.yaml", which is the invariant, not a violation of it.
    for f in ("work_queue.sh", "work_queue_watchdog.sh"):
        code = "\n".join(ln for ln in (SDIR / f).read_text().splitlines()
                         if not ln.lstrip().startswith("#"))
        for banned in ("PRODUCTION.yaml", "CLAIM_REGISTRY", "CHECKPOINT_LINEAGE",
                       "results.csv", "append_result_row", "governance/"):
            assert banned not in code, f"{f} must not reference {banned} in code"


def test_shell_scripts_parse():
    for f in ("work_queue.sh", "work_queue_watchdog.sh"):
        subprocess.run(["bash", "-n", str(SDIR / f)], check=True)


def test_dispatch_never_targets_a_busy_box_under_random_census(root):
    """Property-ish: for any census > 0, no dispatch is ever produced."""
    _mk(root, "OCC_DONE")
    _mk(root, "run.sh", 0o755)
    q = _queue([_item()])
    for n in (1, 2, 5, 22, 30):
        assert ql.tick(q, root, {}, {"local": n})["dispatch"] is None
