#!/usr/bin/env python3
"""Decision core for the measurement work-queue scheduler.

`scripts/scheduler/work_queue.sh` is the long-lived chain; THIS module is every
decision it makes.  Split that way on purpose: the shell does the two things a
shell must do (process census, detached launch, ssh), and every rule that could
be wrong -- is a box free? is an item dispatchable? how many workers right now?
-- is pure-ish Python with pytest coverage (tests/test_scheduler_queue.py).

Stdlib only, no repo imports: the scheduler must keep running across a merge,
a rust rebuild, or a broken venv.

CLI (all read the queue file, default scripts/scheduler/queue.json):

  queue_lib.py validate                       schema-check the queue, exit 2 on error
  queue_lib.py tick --census local=0,laptop=22
                                              the whole decision: writes state.json,
                                              prints one JSON object (see `tick()`)
  queue_lib.py record --item ID --event dispatched --box local --pid N
                                              persist what the shell actually did
  queue_lib.py workers --box local            the wall-clock worker grant for a box
  queue_lib.py status                         human-readable state dump

SAFETY INVARIANTS (asserted by tests/test_scheduler_queue.py):
  * nothing here writes governance/ -- no PRODUCTION.yaml, no band claim, no
    adjudication.  The scheduler READS governance/BAND_REGISTRY.csv to refuse a
    game-playing item whose band is not already on disk, and that is all.
  * an item with plays_games=true and a missing prereg or band is BLOCKED, never
    dispatched.
  * an item whose code is still in an unmerged worktree is NEEDS_MERGE -- the
    scheduler emits a notice for a human/orchestrator and never tries to run it.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE = ROOT / "scripts" / "scheduler" / "queue.json"
DEFAULT_STATE = ROOT / "measurement" / "scheduler_20260813" / "state.json"
BAND_REGISTRY = ROOT / "governance" / "BAND_REGISTRY.csv"

# ---------------------------------------------------------------- statuses ---
# Terminal
DONE = "DONE"
FAILED = "FAILED"
# In flight
DISPATCHED = "DISPATCHED"
# Not dispatchable (each carries a reason string)
NEEDS_MERGE = "NEEDS_MERGE"
BLOCKED = "BLOCKED"
NOT_READY = "NOT_READY"
WAIT_BOX = "WAIT_BOX"
# Dispatchable right now
READY = "READY"

TERMINAL = {DONE, FAILED}
BUSY_STATES = {DISPATCHED}


# ------------------------------------------------------------------ loading --
def load_json(path: Path, default: Any = None) -> Any:
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        if default is not None:
            return default
        raise


def load_queue(path: Path | str = DEFAULT_QUEUE) -> dict:
    q = load_json(Path(path))
    errs = validate_queue(q)
    if errs:
        raise ValueError("invalid queue file %s:\n  %s" % (path, "\n  ".join(errs)))
    return q


def validate_queue(q: Any) -> list[str]:
    """Return a list of human-readable schema errors ([] == valid)."""
    errs: list[str] = []
    if not isinstance(q, dict):
        return ["top level must be an object with 'boxes' and 'items'"]
    boxes = q.get("boxes")
    items = q.get("items")
    if not isinstance(boxes, dict) or not boxes:
        errs.append("'boxes' must be a non-empty object")
        boxes = {}
    if not isinstance(items, list):
        errs.append("'items' must be a list")
        items = []
    for name, b in boxes.items():
        if not isinstance(b, dict):
            errs.append("box %r must be an object" % name)
            continue
        for key in ("host", "marker_dir_local", "workers_schedule"):
            if key not in b:
                errs.append("box %r missing required key %r" % (name, key))
        ws = b.get("workers_schedule")
        if not isinstance(ws, list) or not ws:
            errs.append("box %r workers_schedule must be a non-empty list" % name)
        elif not any("before_hhmm" not in e for e in ws):
            errs.append("box %r workers_schedule needs a final entry with no before_hhmm" % name)
    seen: set[str] = set()
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append("item #%d must be an object" % i)
            continue
        iid = it.get("id")
        if not iid:
            errs.append("item #%d missing 'id'" % i)
            continue
        if iid in seen:
            errs.append("duplicate item id %r" % iid)
        seen.add(iid)
        if not isinstance(it.get("priority"), int):
            errs.append("item %r needs an integer 'priority' (lower runs first)" % iid)
        box = it.get("box", "any")
        if box != "any" and box not in boxes:
            errs.append("item %r targets unknown box %r" % (iid, box))
        if not it.get("launch_cmd"):
            errs.append("item %r missing 'launch_cmd'" % iid)
        if it.get("plays_games") and not (it.get("prereg") and it.get("band")):
            # not a schema error -- it is exactly the BLOCKED case, resolved at tick time
            pass
    return errs


# --------------------------------------------------------------- primitives --
def _abs(root: Path, p: str) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else (root / pp)


def any_exists(root: Path, patterns: Any) -> str | None:
    """First existing path among `patterns` (globs allowed). None if none exist."""
    if not patterns:
        return None
    if isinstance(patterns, str):
        patterns = [patterns]
    for pat in patterns:
        ap = _abs(root, pat)
        if any(ch in str(ap) for ch in "*?["):
            hits = sorted(Path(ap.anchor or "/").glob(str(ap).lstrip("/")))
            if hits:
                return str(hits[0])
        elif ap.exists():
            return str(ap)
    return None


def all_exist(root: Path, paths: Any) -> tuple[bool, list[str]]:
    """(all present?, list of missing) for a list of repo paths."""
    if not paths:
        return True, []
    if isinstance(paths, str):
        paths = [paths]
    missing = [p for p in paths if not _abs(root, p).exists()]
    return (not missing), missing


def band_on_disk(band: str, registry: Path = BAND_REGISTRY) -> bool:
    """True iff `band` appears as a claimed band_seed_start in BAND_REGISTRY.csv.

    Read-only.  The scheduler NEVER claims a band -- a missing band means the
    item is BLOCKED and a human claims it.
    """
    if not band:
        return False
    try:
        with open(registry, newline="") as fh:
            for row in csv.reader(fh):
                if not row:
                    continue
                cell = row[0].strip().strip('"')
                if cell.startswith("#") or cell == "band_seed_start":
                    continue
                if cell == str(band).strip():
                    return True
    except FileNotFoundError:
        return False
    return False


def workers_for(box_cfg: dict, now: float | None = None) -> int:
    """Wall-clock worker grant, e.g. W30 before 11:00 local then W14."""
    lt = time.localtime(now if now is not None else time.time())
    hhmm = lt.tm_hour * 60 + lt.tm_min
    for entry in box_cfg.get("workers_schedule", []):
        before = entry.get("before_hhmm")
        if before is None:
            return int(entry["w"])
        h, m = (int(x) for x in str(before).split(":"))
        if hhmm < h * 60 + m:
            return int(entry["w"])
    return int(box_cfg["workers_schedule"][-1]["w"])


def _resolve_launch(root: Path, item: dict) -> tuple[str | None, str]:
    """Pick the first existing launch command. Returns (path|None, note)."""
    cands = item.get("launch_cmd")
    if isinstance(cands, str):
        cands = [cands]
    tried = []
    for c in cands or []:
        ap = _abs(root, c)
        tried.append(str(ap))
        if not ap.is_file():
            continue
        if os.access(ap, os.X_OK):
            return str(ap), "executable"
        if ap.suffix in (".sh", ".bash"):
            return str(ap), "present but not chmod +x (running via `bash`)"
        return None, "exists but is not executable and is not a shell script: %s" % ap
    return None, "launch command has not landed yet (looked for: %s)" % ", ".join(tried)


# ------------------------------------------------------------ item decisions --
def item_status(
    item: dict,
    root: Path,
    state: dict,
    marker_dirs: dict[str, Path],
    free_boxes: set[str],
    boxes: dict,
) -> dict:
    """Classify one queue item. Pure w.r.t. everything but the filesystem."""
    iid = item["id"]
    prev = state.get("items", {}).get(iid, {})
    reasons: list[str] = []

    # 1. terminal already? scheduler-owned markers first, then the item's own
    #    completion evidence (a sibling may have RUN the thing itself).
    for box_name, mdir in marker_dirs.items():
        if (mdir / ("FAILED_%s" % iid)).exists():
            return {"status": FAILED, "reason": "scheduler FAILED marker present (%s)" % box_name,
                    "box": prev.get("box", box_name)}
        if (mdir / ("DONE_%s" % iid)).exists():
            return {"status": DONE, "reason": "scheduler DONE marker present (%s)" % box_name,
                    "box": prev.get("box", box_name)}
    hit = any_exists(root, item.get("done_if_exists"))
    if hit:
        return {"status": DONE, "reason": "already complete, own evidence on disk: %s" % hit,
                "box": prev.get("box")}

    # 2. in flight (we launched it, no marker yet)
    if prev.get("status") == DISPATCHED:
        return {"status": DISPATCHED,
                "reason": "in flight on %s since %s (pid %s)"
                          % (prev.get("box"), prev.get("dispatched_at"), prev.get("pid")),
                "box": prev.get("box")}

    # 3. unmerged worktree -> never auto-dispatch, emit a merge notice
    ok, missing = all_exist(root, item.get("merge_probe_paths"))
    if not ok:
        return {
            "status": NEEDS_MERGE,
            "reason": "NEEDS HUMAN/ORCHESTRATOR MERGE - built in a worktree, absent from the "
                      "main tree: %s%s" % (", ".join(missing),
                                           "; " + item["merge_note"] if item.get("merge_note") else ""),
            "box": item.get("box", "any"),
        }

    # 4. game-playing work needs a pre-registered prereg AND a claimed band, both on disk
    if item.get("plays_games"):
        prereg = item.get("prereg")
        band = item.get("band")
        if not prereg or not _abs(root, prereg).exists():
            reasons.append("prereg missing (%s)" % (prereg or "not declared"))
        if not band or not band_on_disk(str(band)):
            reasons.append("band not claimed in governance/BAND_REGISTRY.csv (%s)"
                           % (band or "not declared"))
        if reasons:
            return {"status": BLOCKED,
                    "reason": "BLOCKED: prereg/band missing - " + "; ".join(reasons),
                    "box": item.get("box", "any")}

    # 5. has the sibling landed a runnable command?
    if item.get("dir") and not _abs(root, item["dir"]).exists():
        return {"status": NOT_READY,
                "reason": "measurement dir not created yet (%s)" % item["dir"],
                "box": item.get("box", "any")}
    launch, note = _resolve_launch(root, item)
    if launch is None:
        return {"status": NOT_READY, "reason": note, "box": item.get("box", "any")}

    # 6. ready -- is its box free?
    want = item.get("box", "any")
    if want == "any":
        pref = [b for b in ([item["prefer_box"]] if item.get("prefer_box") else []) if b in boxes]
        order = pref + [b for b in boxes if b not in pref]
        target = next((b for b in order if b in free_boxes), None)
    else:
        target = want if want in free_boxes else None
    if target is None:
        return {"status": WAIT_BOX,
                "reason": "ready, waiting for box %s to free" % want,
                "box": want, "launch_cmd": launch, "launch_note": note}
    return {"status": READY, "reason": "dispatchable now on %s (%s)" % (target, note),
            "box": target, "launch_cmd": launch, "launch_note": note}


# ------------------------------------------------------------- box freeness --
def box_state(
    name: str,
    cfg: dict,
    root: Path,
    state: dict,
    census: int | None,
    now: float,
    items_status: dict,
) -> dict:
    """Is this box free? Marker + census + (optional) idle-release."""
    prev = state.get("boxes", {}).get(name, {})
    out = {"name": name, "census": census, "idle_since": prev.get("idle_since")}

    # our own dispatched job owns the box
    mine = [i for i, s in items_status.items() if s["status"] in BUSY_STATES and s.get("box") == name]
    if mine:
        out.update(free=False, reason="scheduler job in flight: %s" % ", ".join(mine))
        return out

    if census is None:
        out.update(free=False, reason="census UNREACHABLE - failing closed, box treated as busy")
        return out
    if census > 0:
        out.update(free=False, idle_since=None,
                   reason="census guard: %d live measurement process(es) on %s" % (census, name))
        return out

    occ = any_exists(root, cfg.get("occupant_markers"))
    if occ:
        out.update(free=True, idle_since=None,
                   reason="occupant '%s' finished (marker %s), census clean"
                          % (cfg.get("occupant_label", "?"), occ))
        return out

    # No occupant marker, but nothing is running.  Either the occupant never
    # launched or it died.  Release only if the box config allows it AND the box
    # has been quiet long enough that we are not racing a sibling's launch.
    idle_since = prev.get("idle_since") or now
    out["idle_since"] = idle_since
    quiet = now - idle_since
    if not cfg.get("allow_idle_release"):
        out.update(free=False,
                   reason="occupant '%s' marker absent (idle %.0f min, idle-release disabled for "
                          "this box)" % (cfg.get("occupant_label", "?"), quiet / 60.0))
        return out
    grace = float(cfg.get("idle_release_secs", 2700))
    if quiet < grace:
        out.update(free=False,
                   reason="occupant '%s' marker absent and box idle %.0f/%.0f min - holding "
                          "(may be between legs, or a sibling is about to launch)"
                          % (cfg.get("occupant_label", "?"), quiet / 60.0, grace / 60.0))
        return out
    out.update(free=True,
               reason="IDLE-RELEASE: occupant '%s' marker NEVER appeared but the box has been "
                      "clean for %.0f min (> %.0f grace) - treating as free"
                      % (cfg.get("occupant_label", "?"), quiet / 60.0, grace / 60.0))
    return out


# -------------------------------------------------------------------- tick ----
def tick(queue: dict, root: Path, state: dict, census: dict[str, int | None],
         now: float | None = None) -> dict:
    """One scheduling decision. Returns the full decision record (also -> state)."""
    now = time.time() if now is None else now
    boxes = queue["boxes"]
    marker_dirs = {n: _abs(root, c["marker_dir_local"]) for n, c in boxes.items()}

    items = sorted(queue["items"], key=lambda it: (it.get("priority", 999), it["id"]))

    # pass 1: classify with NO box free, so we learn each item's intrinsic state
    statuses = {it["id"]: item_status(it, root, state, marker_dirs, set(), boxes) for it in items}

    # box freeness (needs pass-1 statuses to know which boxes we already own)
    box_states = {n: box_state(n, boxes[n], root, state, census.get(n), now, statuses)
                  for n in boxes}
    free = {n for n, b in box_states.items() if b.get("free")}

    # pass 2: re-classify with real free set, and pick the highest-priority READY
    statuses = {it["id"]: item_status(it, root, state, marker_dirs, free, boxes) for it in items}

    dispatch = None
    taken: set[str] = set()
    for it in items:
        st = statuses[it["id"]]
        if st["status"] != READY:
            continue
        if st["box"] in taken:
            statuses[it["id"]] = {**st, "status": WAIT_BOX,
                                  "reason": "ready, but %s was taken by a higher-priority item"
                                            % st["box"]}
            continue
        if dispatch is None:
            box = st["box"]
            dispatch = {
                "item": it["id"],
                "box": box,
                "launch_cmd": st["launch_cmd"],
                "workers": workers_for(boxes[box], now),
                "marker_dir_local": str(marker_dirs[box]),
                "marker_dir_remote": str(boxes[box].get("marker_dir_remote",
                                                        boxes[box]["marker_dir_local"])),
                "priority": it.get("priority"),
                "log": it.get("log") or "measurement/scheduler_20260813/logs/%s.log" % it["id"],
                "item_cfg": it,
                "box_cfg": boxes[box],
            }
            taken.add(box)

    log_lines = []
    for n, b in box_states.items():
        log_lines.append("BOX %-6s %-4s %s" % (n, "FREE" if b.get("free") else "BUSY", b["reason"]))
    for it in items:
        st = statuses[it["id"]]
        log_lines.append("ITEM p%-3s %-22s %-11s %s"
                         % (it.get("priority"), it["id"], st["status"], st["reason"]))
    if dispatch:
        log_lines.append("DISPATCH %s -> %s (W%d) via %s"
                         % (dispatch["item"], dispatch["box"], dispatch["workers"],
                            dispatch["launch_cmd"]))

    pending = [i for i, s in statuses.items() if s["status"] not in TERMINAL]
    return {
        "now": now,
        "boxes": box_states,
        "items": statuses,
        "free_boxes": sorted(free),
        "dispatch": dispatch,
        "drained": not pending,
        "pending": pending,
        "log_lines": log_lines,
    }


def merge_state(state: dict, decision: dict, queue: dict) -> dict:
    """Fold a tick's decision into the persistent state file."""
    out = dict(state)
    out["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(decision["now"]))
    out["queue_items"] = [it["id"] for it in queue["items"]]
    out.setdefault("items", {})
    for iid, st in decision["items"].items():
        prev = out["items"].get(iid, {})
        # never lose dispatch bookkeeping when the status moves on
        merged = {**prev, "status": st["status"], "reason": st["reason"]}
        if st.get("box"):
            merged["box"] = st["box"]
        out["items"][iid] = merged
    out["boxes"] = {n: {k: v for k, v in b.items() if k != "name"}
                    for n, b in decision["boxes"].items()}
    out["free_boxes"] = decision["free_boxes"]
    out["drained"] = decision["drained"]
    return out


def append_history(state: dict, event: str, detail: str, limit: int = 500) -> dict:
    h = list(state.get("history", []))
    h.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, "detail": detail})
    state["history"] = h[-limit:]
    return state


def write_state(state: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, path)


# --------------------------------------------------------------------- CLI ----
def _parse_census(s: str | None) -> dict[str, int | None]:
    """'local=0,laptop=22' -> {'local': 0, 'laptop': 22}; a negative count means
    UNREACHABLE (fail closed)."""
    out: dict[str, int | None] = {}
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        k, _, v = part.partition("=")
        try:
            n = int(v)
        except ValueError:
            n = -1
        out[k.strip()] = None if n < 0 else n
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=["validate", "tick", "record", "workers", "status"])
    ap.add_argument("--queue", default=str(DEFAULT_QUEUE))
    ap.add_argument("--state", default=str(DEFAULT_STATE))
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--census", default="")
    ap.add_argument("--box", default=None)
    ap.add_argument("--item", default=None)
    ap.add_argument("--event", default=None)
    ap.add_argument("--pid", default=None)
    ap.add_argument("--detail", default="")
    a = ap.parse_args(argv)

    root = Path(a.root)
    state_path = Path(a.state)

    if a.cmd == "validate":
        errs = validate_queue(load_json(Path(a.queue)))
        for e in errs:
            print("ERROR: %s" % e, file=sys.stderr)
        print("queue OK: %s" % a.queue if not errs else "queue INVALID")
        return 2 if errs else 0

    queue = load_queue(a.queue)
    state = load_json(state_path, default={})

    if a.cmd == "workers":
        print(workers_for(queue["boxes"][a.box]))
        return 0

    if a.cmd == "status":
        print(json.dumps(state, indent=1))
        return 0

    if a.cmd == "record":
        state.setdefault("items", {})
        rec = state["items"].setdefault(a.item, {})
        if a.event == "dispatched":
            rec.update(status=DISPATCHED, box=a.box, pid=a.pid,
                       dispatched_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                       launch_detail=a.detail)
        elif a.event == "launch_failed":
            rec.update(status=FAILED, box=a.box, reason="launch failed: %s" % a.detail)
        else:
            rec.update(status=a.event or rec.get("status"), reason=a.detail)
        append_history(state, a.event or "record", "%s on %s: %s" % (a.item, a.box, a.detail))
        write_state(state, state_path)
        return 0

    # tick
    decision = tick(queue, root, state, _parse_census(a.census))
    state = merge_state(state, decision, queue)
    if decision["dispatch"]:
        append_history(state, "dispatch_selected",
                       "%s -> %s" % (decision["dispatch"]["item"], decision["dispatch"]["box"]))
    write_state(state, state_path)
    print(json.dumps(decision, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
