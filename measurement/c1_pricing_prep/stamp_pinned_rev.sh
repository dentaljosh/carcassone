#!/usr/bin/env bash
# Stamp the FREEZE commit's sha into PINNED_SRC_REV.json — the second half of the
# house two-commit pattern. Run immediately after the freeze commit lands, then
# commit this file alone with the message "c1price: stamp PINNED_SRC_REV = <sha>".
set -eu
REPO="${REPO:-/home/doctor/projects/carcassone}"
DIR="$REPO/measurement/c1_pricing_prep"
SHA="$(git -C "$REPO" rev-parse HEAD)"
"${PY:-$REPO/.venv/bin/python}" - "$DIR/PINNED_SRC_REV.json" "$SHA" <<'PYEOF'
import json, sys, time
p, sha = sys.argv[1], sys.argv[2]
d = json.load(open(p))
if d["pinned_src_rev"] != "PENDING_FREEZE_STAMP":
    raise SystemExit(f"already stamped: {d['pinned_src_rev']}")
d["pinned_src_rev"] = sha
d["stamped_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
json.dump(d, open(p, "w"), indent=1)
print("stamped", sha)
PYEOF
