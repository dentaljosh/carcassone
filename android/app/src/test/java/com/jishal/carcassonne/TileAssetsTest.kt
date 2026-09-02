package com.jishal.carcassonne

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The required-asset manifest.
 *
 * `TileAssets.load` cannot be exercised on the JVM (it needs an `AssetManager`),
 * but the thing that actually went wrong was never the decode — it was the LIST:
 * the loader enumerated `assets/tiles/base_game/` and silently accepted whatever
 * happened to be there, so a worktree build that copied only that one directory
 * shipped with every meeple sprite missing and nothing failed until the APK was on
 * the phone. This pins the manifest that `load` now checks against and throws on.
 *
 * The count is also what `unzip -l` on the APK is checked against: 39 files.
 */
class TileAssetsTest {

    @Test
    fun `the base game contributes 24 lettered faces, A through X`() {
        assertEquals(24, TileAssets.LETTERED_TILE_FACES.size)
        assertTrue(
            TileAssets.LETTERED_TILE_FACES.first(),
            TileAssets.LETTERED_TILE_FACES.first().endsWith("Base_Game_C2_Tile_A.png"),
        )
        assertTrue(
            TileAssets.LETTERED_TILE_FACES.last(),
            TileAssets.LETTERED_TILE_FACES.last().endsWith("Base_Game_C2_Tile_X.png"),
        )
        // No 'Y'/'Z': the base deck stops at X, and a 25th name would be a file the
        // generator never writes — i.e. a build that could never succeed.
        assertFalse(
            TileAssets.LETTERED_TILE_FACES.toString(),
            TileAssets.LETTERED_TILE_FACES.any { it.contains("Tile_Y") || it.contains("Tile_Z") },
        )
    }

    @Test
    fun `the eight garden art variants are required too`() {
        assertEquals(8, TileAssets.GARDEN_TILE_FACES.size)
        for (name in TileAssets.GARDEN_TILE_FACES) {
            assertTrue(name, name.startsWith("base_game/Abbot-"))
            assertTrue(name, name.endsWith("_Garden.png"))
        }
    }

    /** 32 tile faces — the same number Gradle's `checkTileAssets` counts. */
    @Test
    fun `there are 32 tile faces and they are distinct`() {
        assertEquals(32, TileAssets.REQUIRED_TILE_FACES.size)
        assertEquals(32, TileAssets.REQUIRED_TILE_FACES.toSet().size)
    }

    /**
     * The regression this whole file exists for: the six meeple colours and
     * `Empty.png` live DIRECTLY in `assets/tiles/`, not under `base_game/`, which
     * is exactly why a partial copy missed them.
     */
    @Test
    fun `all seven loose sprites are required`() {
        assertEquals(7, TileAssets.SPRITE_FILES.size)
        for (colour in listOf("blue", "red", "green", "yellow", "black", "pink")) {
            assertTrue(colour, TileAssets.SPRITE_FILES.contains("${colour}_meeple.png"))
        }
        assertTrue(TileAssets.SPRITE_FILES.contains("Empty.png"))
        assertFalse(
            TileAssets.SPRITE_FILES.toString(),
            TileAssets.SPRITE_FILES.any { it.contains('/') },
        )
    }

    /** 32 + 7 = 39, every path rooted at `tiles/` as the AssetManager sees it. */
    @Test
    fun `the full required set is 39 asset paths under tiles`() {
        assertEquals(39, TileAssets.REQUIRED_ASSETS.size)
        assertEquals(39, TileAssets.REQUIRED_ASSETS.toSet().size)
        for (path in TileAssets.REQUIRED_ASSETS) {
            assertTrue(path, path.startsWith("tiles/"))
            assertTrue(path, path.endsWith(".png"))
        }
    }
}
