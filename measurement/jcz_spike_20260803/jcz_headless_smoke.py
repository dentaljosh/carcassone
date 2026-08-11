#!/usr/bin/env python3
"""Spike question 1: is JCloisterZone drivable HEADLESSLY, with a forced deck order?

Drives the built `Engine.jar` over its stdin/stdout JSON line protocol:

    %load <abs path to basic.xml>            (directive: tile-definition file)
    {"type":"GAME_SETUP","payload":{...}}    (sets / players / rules / annotations)
    {"type":"PLACE_TILE","payload":{...}}    (one per ply)
    {"type":"PASS"|"DEPLOY_MEEPLE",...}

After every message the engine prints ONE line of JSON: the whole game state --
`players[].points` (running score), `action` (the LEGAL MOVE SET for the player to
act), `features` (every City/Road/Field feature and the tile-places it spans),
`placedTiles`, `deployedMeeples`, `history` (scoring events). That is all three
oracle checks (farm regions / legality / scoring) from one stream.

`gameAnnotations.tilePack = ForcedDrawTilePack` pins the draw order, so our
`(deck_seed, actions)` archives replay deterministically with no RNG matching.

Env: JCZ_JAR (default ~/jcz_spike/JCloisterZone/build/Engine.jar)
Usage: .venv/bin/python measurement/jcz_spike_20260803/jcz_headless_smoke.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JAR = os.environ.get("JCZ_JAR", os.path.expanduser("~/jcz_spike/JCloisterZone/build/Engine.jar"))
TILES = os.path.join(HERE, "jcz_basic_5x.xml")

# A short forced deck: start tile then a few draws. "#END" stops the pack.
DRAW_ORDER = ["BA/RCr", "BA/RCr", "BA/C", "BA/Rr", "#END"]

SETUP = {
    "type": "GAME_SETUP",
    "payload": {
        "players": 2,
        "initialRandom": 0.5,
        "sets": {"basic:2": 1},
        "elements": {"small-follower": 7, "farmers": True},
        "rules": {},
        "start": [{"tile": "BA/RCr", "x": 0, "y": 0, "rotation": 0}],
        "gameAnnotations": {
            "tilePack": {
                "className": "com.jcloisterzone.debug.ForcedDrawTilePack",
                "params": {"drawOrder": DRAW_ORDER},
            }
        },
    },
}


def main():
    if not os.path.exists(JAR):
        print(f"missing jar: {JAR}\nbuild with:  mvn -B -DskipTests package", file=sys.stderr)
        return 2

    p = subprocess.Popen(["java", "-jar", JAR], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)

    def send(line):
        p.stdin.write(line + "\n")
        p.stdin.flush()

    def recv():
        line = p.stdout.readline()
        return json.loads(line) if line.strip() else None

    send(f"%load {TILES}")
    send(json.dumps(SETUP))
    st = recv()
    if st is None:
        print("no state emitted; stderr:\n" + p.stderr.read(), file=sys.stderr)
        return 3

    print("=== initial state ===")
    print("  phase          :", st.get("phase"))
    print("  tiles in pack  :", st.get("tilePack"))
    print("  placedTiles    :", st.get("placedTiles"))
    print("  scores         :", [pl.get("points") for pl in st.get("players", {}).get("players", [])]
          if isinstance(st.get("players"), dict) else st.get("players"))
    print("  legal action   :", json.dumps(st.get("action")))
    print("  feature kinds  :", sorted({f.get("type") for f in (st.get("features") or [])}))
    print()
    print("=== full top-level keys of the emitted state ===")
    print(" ", sorted(st.keys()))
    print()

    # Show the FIELD features -- this is the farm-region oracle signal.
    fields = [f for f in (st.get("features") or []) if f.get("type") == "Field"]
    print(f"=== Field features on the start tile: {len(fields)} ===")
    for f in fields:
        print("  ", json.dumps(f))

    # One real ply: place the drawn RCr at [1,0] rotated 180 -- i.e. city-to-city
    # against the start tile. That is exactly the configuration our engine merges
    # the two under-city field strips on (see rcr_merge_probe.py).
    print()
    print("=== ply 1: PLACE_TILE BA/RCr @ [0,-1] rot R180 (the two cities meet) ===")
    send(json.dumps({"type": "PLACE_TILE",
                     "payload": {"tileId": "BA/RCr", "rotation": "R180", "position": [0, -1]}}))
    st = recv()
    print("  phase        :", st.get("phase"))
    fields = [f for f in (st.get("features") or []) if f.get("type") == "Field"]
    print(f"  Field features now: {len(fields)}")
    for f in fields:
        print("   ", json.dumps(f))
    print()
    print("  ^ JCZ keeps the two under-city strips as SEPARATE Field features.")
    print("    Our find_farm merges them into one (see rcr_merge_probe.py).")

    p.stdin.close()
    p.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
