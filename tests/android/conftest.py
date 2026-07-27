"""Make ``android_bridge`` importable for the desktop bridge tests.

``carcassonne_ai`` and ``wingedsheep`` are already importable in the repo venv (both are
editable installs — see ``.venv/lib/python3.12/site-packages/__editable__*.pth``), so the
only path this suite has to add is the app's python srcDir.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BRIDGE_DIR = REPO / "android" / "app" / "src" / "main" / "python"
TOOLS_DIR = REPO / "android" / "tools"

for _p in (BRIDGE_DIR, TOOLS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
