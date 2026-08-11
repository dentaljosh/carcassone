#!/usr/bin/env python3
"""Prepare tile/meeple art for the Android app.

Reads the engine's PNGs (base game tiles + meeples), normalizes every tile to
an exact square, upscales with Lanczos, and writes them under
android/app/src/main/assets/tiles/ preserving the relative paths the bridge
reports (e.g. "base_game/Base_Game_C2_Tile_A.png").

The source art is ~104px; phones want more. Upscaling can't add detail but
Lanczos at 4x keeps edges clean enough for a 60-300px on-screen tile.

Usage:
    python3 android/tools/prepare_assets.py [--size 416] [--repo PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

MEEPLE_FILES = [
    "blue_meeple.png",
    "red_meeple.png",
    "black_meeple.png",
    "yellow_meeple.png",
    "green_meeple.png",
    "pink_meeple.png",
    "Empty.png",
]


def main() -> None:
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, default=here.parents[2])
    ap.add_argument("--out", type=Path, default=None,
                    help="default: <repo>/android/app/src/main/assets/tiles")
    ap.add_argument("--size", type=int, default=416,
                    help="output tile edge in px (tiles are forced square)")
    args = ap.parse_args()

    images = args.repo / "engine" / "wingedsheep" / "carcassonne" / "resources" / "images"
    out = args.out or args.repo / "android" / "app" / "src" / "main" / "assets" / "tiles"
    if not images.is_dir():
        raise SystemExit(f"engine images dir not found: {images}")

    n_tiles = 0
    tile_out = out / "base_game"
    tile_out.mkdir(parents=True, exist_ok=True)
    for src in sorted((images / "base_game").glob("*.png")):
        img = Image.open(src).convert("RGBA")
        img = img.resize((args.size, args.size), Image.LANCZOS)
        img.save(tile_out / src.name)
        n_tiles += 1

    n_meeples = 0
    for name in MEEPLE_FILES:
        src = images / name
        if not src.exists():
            print(f"WARN: missing {src}")
            continue
        img = Image.open(src).convert("RGBA")
        # Meeples keep their aspect ratio; scale so the longest edge is size/2
        # (a meeple is drawn at roughly a quarter of a tile).
        scale = (args.size // 2) / max(img.size)
        img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
        img.save(out / name)
        n_meeples += 1

    print(f"prepare_assets: {n_tiles} tiles -> {tile_out}, {n_meeples} sprites -> {out} "
          f"(size={args.size})")


if __name__ == "__main__":
    main()
